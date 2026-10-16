/**
 * pi-android-link 看门狗 —— 这条链路里唯一"新增"的组件，也是真正补上缺口的那块。
 *
 * 为什么必须有它：pi-web 自己的推送是在进程内发的（lib/rpc-manager.ts:2143 →
 * lib/web-push.ts），进程被杀 / PC 重启 / OOM 时它发不出任何东西。而且它只有
 * 一句"任务已完成"，实测 234 个会话里有 13 个是以 stop=error 结束的、7 个
 * stop=aborted、5 个停在 toolUse —— 这些它一律报"任务已完成"，是错的。
 *
 * 本看门狗的判定完全确定，不靠观感：
 *   1. GET /api/sessions → 拿 runningSessionIds（进程内真相）+ 会话清单
 *   2. 不在 running 里 + 文件已静默 settleGraceMs → 读文件尾部判定（lib/classify.mjs）
 *   3. 排在 running 里但文件 hangMs 没动 → 疑卡死
 *   4. 上一轮有会话在跑、这一轮 pi-web 连不上 → 进程失联
 *
 * 出口是 lib/broker.mjs（发到派发台的 /pi/publish，不经过任何第三方）。
 *
 * 用法：
 *   node watchdog.mjs            # 常驻
 *   node watchdog.mjs --once     # 跑一轮就退出（调试）
 *   node watchdog.mjs --once --dry   # 只打印不推送
 */
import { join } from "node:path";
import { config, consoleLink, deepLink, LOCAL_CONFIG, STATE_DIR } from "./config.mjs";
import { readAndClassify, readSessionHeader } from "./lib/classify.mjs";
import { planAuthFailed, planNotification, planPiWebDown, planStall } from "./lib/notify-plan.mjs";
import { publish } from "./lib/broker.mjs";
import { listSessions, PiWebAuthError } from "./lib/piweb.mjs";
import { acquireSingleInstance } from "./lib/single-instance.mjs";
import { loadState, log, saveState } from "./lib/store.mjs";

const argv = new Set(process.argv.slice(2));
const ONCE = argv.has("--once");
const DRY = argv.has("--dry");

/** 取 `--flag value` 的值 */
function flagValue(flag) {
  const index = process.argv.indexOf(flag);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

const SIMULATE = flagValue("--simulate");
/** 模拟用的假原因，让 verify.mjs 能把 5 种判定逐个走一遍真实发布链路 */
const SIM_REASONS = {
  complete: "正常收尾（模拟）",
  model_error: "模型报错：模拟的 Connection error.",
  aborted: "已中止（模拟）",
  truncated: "输出达到长度上限被截断（模拟）",
  interrupted_tool: "2 个工具调用没有返回结果（模拟）",
  auth_failed: "模拟的鉴权失败",
};
/** 单实例锁文件。用文件而不是端口，原因见 lib/single-instance.mjs 注释 */
const LOCK_FILE = join(STATE_DIR, "watchdog.lock");

/** 连续鉴权失败到几次就停手（绝不把 pi-web 的登录限流刷满） */
const AUTH_FAILURE_LIMIT = 3;
/** 停手时长；即使有守护进程不断重启看门狗，这段时间内也拒绝启动 */
const AUTH_GIVE_UP_MS = 30 * 60_000;

/** 通知带的动作按钮。用 view 而不是 http：Android 对明文 http 动作可能被
 *  cleartext 策略拦掉，view 是交给浏览器打开，稳。 */
function actionsFor(sessionId) {
  const actions = [
    { action: "view", label: "打开会话", url: deepLink(sessionId), clear: true },
    { action: "view", label: "派发台", url: consoleLink() },
  ];
  if (sessionId) {
    actions.push({
      action: "view",
      label: "让它继续跑",
      url: consoleLink(`do=resume&session=${encodeURIComponent(sessionId)}`),
    });
  }
  return actions;
}

async function emit({ kind, title, body, sessionId, group, actions }) {
  // 正文尾巴带上时间。同一会话每轮结束都会推一条，而标题取的是"会话首条消息"，
// 所以多条通知标题长得一模一样；而我们的中转没有 pi-web Web Push 那种"同 tag 替换"能力，不加时间的话手机上一堆通知看着像重复推送。
  // 能力，不加时间的话手机上一堆通知看着像重复推送。
  const stamped = `${body} · ${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`;
  const line = `推送 [${kind}] ${title} — ${stamped}`;
  if (DRY) {
    log(`DRY ${line}`);
    return { ok: true, dry: true };
  }
  const result = await publish({ kind, title, body: stamped, click: sessionId ? deepLink(sessionId) : undefined, group, actions });
  log(result.ok ? line : `${line} → ★★★ 推送失败: ${result.error}（出口 ${config.broker.base}）`);
  return result;
}

/**
 * pi-web 鉴权失败的处理。这一段存在的唯一目的：
 * **绝不把 pi-web 的登录限流刷满**。该限流是全局共享的（lib/auth-throttle.ts），
 * 且被限流期间连正确密码也一律拒给访问 —— 看门狗把限流刷满的代价是
 * 用户自己用浏览器也登不进 pi-web。所以：少量退避重试，到阈值就告警并停手。
 */
async function handleAuthFailure(state, error) {
  state.authFailures = (state.authFailures ?? 0) + 1;
  state.piWebFailures = 0; // 这不是"进程失联"，别混为一谈
  log(`pi-web 鉴权失败第 ${state.authFailures} 次（HTTP ${error.status}${error.retryAfterMs ? `，Retry-After ${Math.round(error.retryAfterMs / 1000)}s` : ""}）`);

  if (state.authFailures >= AUTH_FAILURE_LIMIT) {
    if (!state.authNotified) {
      await emit({
        ...planAuthFailed({
          throttled: Boolean(error.throttled),
          attempts: state.authFailures,
          passwordConfigured: Boolean(config.piWeb.password),
          configPath: LOCAL_CONFIG,
        }),
        group: "pi-web-critical",
        actions: [],
      });
      state.authNotified = true;
    }
    state.authGiveUpUntil = Date.now() + AUTH_GIVE_UP_MS;
    saveState(state);
    log(`已停手，暂停到 ${new Date(state.authGiveUpUntil).toISOString()}（修好密码后用 --force 立即重试）`);
    process.exit(0);
  }

  const waitMs = Math.max(config.authRetryMs, error.retryAfterMs || 0);
  log(`退避 ${Math.round(waitMs / 1000)}s 后再试（不会连打，避免把限流刷满）`);
  await new Promise((resolve) => setTimeout(resolve, waitMs));
}

async function tick(state) {
  const now = Date.now();
  // 首次运行（或 --prime）：把历史会话的尾部结果全部标记为"已知"，不补推。
  // 否则第一次启动会一口气弹出二十多条旧报错，直接把这套东西用废。
  const priming = !state.primed || argv.has("--prime");
  let primed = 0;

  // ── 1. 拿快照 ──────────────────────────────────────────────────────────
  let snapshot;
  try {
    snapshot = await listSessions();
  } catch (error) {
    if (error instanceof PiWebAuthError) {
      await handleAuthFailure(state, error);
      return;
    }
    state.piWebFailures += 1;
    log(`pi-web 不可达（第 ${state.piWebFailures} 次）: ${error.message}`);
    if (state.lastRunning.length > 0 && !state.piWebDownNotified) {
      await emit({
        ...planPiWebDown(state.lastRunning.length, state.lastRunning[0]),
        group: "pi-web-critical",
        actions: actionsFor(state.lastRunning[0]),
      });
      state.piWebDownNotified = true;
    }
    return;
  }
  state.piWebFailures = 0;
  state.piWebDownNotified = false;
  state.authFailures = 0;
  state.authNotified = false;

  const sessions = Array.isArray(snapshot.sessions) ? snapshot.sessions : [];
  const running = new Set(snapshot.runningSessionIds ?? []);
  const quiet = new Set([
    ...(snapshot.completionNotificationSuppressedSessionIds ?? []),
  ]);
  state.lastRunning = [...running];

  // ── 2. 正在跑的会话：卡死检测 ──────────────────────────────────────────
  for (const id of running) {
    const session = sessions.find((item) => item.id === id);
    if (!session?.path) continue;
    const modified = session.modified;
    const tracked = state.active[id];
    if (!tracked || tracked.modified !== modified) {
      state.active[id] = { modified, since: now };
      continue;
    }
    const quietMs = now - Date.parse(modified);
    if (quietMs > config.hangMs) {
      const key = `${id}:stall:${modified}`;
      if (!state.notified[key]) {
        const header = readSessionHeader(session.path);
        await emit({
          ...planStall(session, header, Math.round(quietMs / 60000)),
          sessionId: id,
          group: "pi-web",
          actions: actionsFor(id),
        });
        state.notified[key] = now;
      }
    }
  }
  for (const id of Object.keys(state.active)) {
    if (!running.has(id)) delete state.active[id];
  }

  // ── 3. 已停下的近期会话：尾部判定 ──────────────────────────────────────
  let classified = 0;
  for (const session of sessions) {
    if (!session?.path || !session?.id) continue;
    if (running.has(session.id)) continue; // 还在跑，等它停
    if (session.transient === true) continue;

    const modifiedMs = Date.parse(session.modified);
    if (!Number.isFinite(modifiedMs)) continue;
    if (now - modifiedMs > config.recentSessionMs) continue; // 太老的会话不关心

    // 【先算判定，再决定等多久】这是把通知延迟从 20~35s 压到 2~7s 的关键。
    //   末条 assistant 带最终 stopReason（stop/length/error/aborted）
    //     → 文件里已经有硬证据说明本回合结束了，只需极短静默防半行
    //   末条停在 toolUse（工具可能还在跑）→ 才等满 settleGraceMs
    // 旧写法是“先无条件等 20s 再看”，于是任何时候都要多等廿秒。
    const cached = state.tailCache[session.id];
    let verdict;
    if (cached && cached.modified === session.modified) {
      verdict = cached.verdict;
    } else {
      verdict = readAndClassify(session.path, config.tailBytes);
      state.tailCache[session.id] = { modified: session.modified, verdict };
      classified += 1;
    }

    const quietMs = now - modifiedMs;
    const definitive = Boolean(verdict?.stopReason) && verdict.stopReason !== "toolUse";
    if (quietMs < (definitive ? config.fastSettleMs : config.settleGraceMs)) continue;
    if (!verdict?.entryId) continue;

    const key = `${session.id}:${verdict.entryId}`;
    if (state.notified[key]) continue;

    // 子代理/被抑制的会话：只在真出问题时才吵你，正常完成不打扰
    if (quiet.has(session.id) && verdict.kind === "complete") {
      state.notified[key] = now;
      continue;
    }

    if (priming) {
      state.notified[key] = now;
      primed += 1;
      continue;
    }

    const header = readSessionHeader(session.path);
    const plan = planNotification(verdict, session, header);
    if (!plan) continue;

    await emit({ ...plan, sessionId: session.id, group: "pi-web", actions: actionsFor(session.id) });
    state.notified[key] = now;
  }

  if (priming) {
    state.primed = true;
    log(`首次运行：把 ${primed} 个历史会话尾标记为已知（不补推旧消息），从下一轮起只推新的收尾/中断。`);
  }

  // ── 4. 清理 tailCache ─────────────────────────────────────────────────
  const known = new Set(sessions.map((item) => item.id));
  for (const id of Object.keys(state.tailCache)) {
    if (!known.has(id)) delete state.tailCache[id];
  }

  log(
    `轮询完成：会话 ${sessions.length}，在跑 ${running.size}，本轮新判定 ${classified}，`
    + `已记录 ${Object.keys(state.notified).length} 条${primed ? `（本轮首次标记 ${primed}）` : ""}`,
  );
}

/**
 * 启动时自检出口：确认消息中转真的可达。
 *
 * 这个坑真踩过：看门狗是开机自启的常驻进程，改完 broker 地址（8080 → 8787）后
 * 没重启它 —— 它就一直往已经停掉的旧地址发，**每条推送都 fetch failed**，
 * 而失败只写在 watchdog.log 里没人看。外在表现就是"手机上一条通知都收不到"，
 * 但你去查 App、查中转、查网络，全都是好的。
 */
async function probeBroker() {
  const base = config.broker.base;
  try {
    const response = await fetch(`${base}/api/state?t=${encodeURIComponent(config.broker.token)}`, {
      signal: AbortSignal.timeout(5000),
    });
    if (response.ok) {
      log(`出口自检：中转可达 ${base}`);
      return true;
    }
    log(`★★★ 出口自检失败：${base} 返回 HTTP ${response.status} —— 接下来所有推送都会失败！`);
    return false;
  } catch (error) {
    log(`★★★ 出口自检失败：${base} 连不上（${error.message}）—— 接下来所有推送都会失败！`);
    log('      排查：派发台在跑吗（run-link.bat）？local.json 的 lan.consolePort 对不对？');
    return false;
  }
}

async function main() {
  if (SIMULATE) {
    // 把某一种判定走一遍真实发布路径。让 verify.mjs 能够确定性地覆盖
    // 「近期真实会话里恰好没有报错/中止」这种数据运气问题。
    const fake = { id: null, cwd: "C:/pi-work", firstMessage: `链路自检 ${SIMULATE}` };
    const plan = SIMULATE === "stall"
      ? planStall(fake, null, 12)
      : SIMULATE === "piweb_down"
        ? planPiWebDown(3, null)
        : SIMULATE === "auth_failed"
          ? planAuthFailed({ throttled: false, attempts: 3, passwordConfigured: true, configPath: LOCAL_CONFIG })
          : planNotification({ kind: SIMULATE, reason: SIM_REASONS[SIMULATE] ?? "模拟" }, fake, null);
    if (!plan) {
      log(`--simulate 不支持的种类：${SIMULATE}（可用：${[...Object.keys(SIM_REASONS), "stall", "piweb_down"].join(", ")}）`);
      process.exitCode = 2;
      return;
    }
    await emit({ ...plan, group: "pi-link-verify", actions: [] });
    return;
  }

  // 单实例锁：没有这个的话，计划任务 + 启动文件夹双份启动会推两遍通知。
  if (!argv.has("--force")) {
    const lock = acquireSingleInstance(LOCK_FILE);
    if (!lock.ok) {
      log(`已有看门狗在跑（pid=${lock.holderPid ?? "?"}，锁 ${LOCK_FILE}），本次退出`);
      return;
    }
  } else {
    log("按 --force 跳过单实例锁");
  }

  log(`看门狗启动 pid=${process.pid} 状态目录=${STATE_DIR} 轮询间隔=${config.pollMs}ms${DRY ? "（DRY RUN）" : ""}`);
  await probeBroker();
  const state = loadState();

  // 上次因鉴权失败主动停手：任何守护进程把看门狗拉起来也不开工。
  // --force 视为"密码已经改好了"，直接清掉暂停标记。
  if (state.authGiveUpUntil && Date.now() < state.authGiveUpUntil) {
    if (argv.has("--force")) {
      log("按 --force 清除鉴权暂停标记，立即重试");
      state.authGiveUpUntil = 0;
      state.authFailures = 0;
      state.authNotified = false;
    } else {
      const leftMin = Math.ceil((state.authGiveUpUntil - Date.now()) / 60_000);
      log(`上次因 pi-web 鉴权失败主动暂停，还剩 ${leftMin} 分钟。修好 local.json 里的密码后用 --force 立即重试。`);
      return;
    }
  }

  if (state.lastRunning?.length) {
    log(`上次退出时有 ${state.lastRunning.length} 个会话在跑，开始核查: ${state.lastRunning.join(", ")}`);
  }

  for (;;) {
    try {
      await tick(state);
    } catch (error) {
      log(`轮询异常（已吞掉，继续下一轮）: ${error?.stack ?? error}`);
    }
    saveState(state);
    if (ONCE) break;
    await new Promise((resolve) => setTimeout(resolve, config.pollMs));
  }
  log("看门狗退出");
}

main().catch((error) => {
  log(`看门狗致命错误: ${error?.stack ?? error}`);
  process.exit(1);
});
