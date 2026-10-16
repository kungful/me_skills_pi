/**
 * pi-android-link 监管者 —— 把 watchdog + 派发台收进一个终端 / 一棵进程树。
 *
 * 为什么是这个形状（隐患最小）：
 *   1. watchdog.mjs / console-server.mjs 一行都不改 —— 判定、协议、锁、
 *      日志、verify.mjs 的全部断言都不受影响；
 *   2. 本文件只做 spawn + 日志双写 + 崩溃重启，不碰任何业务逻辑；
 *   3. 子进程还是各自拿各自的锁（watchdog.lock / console.lock）；
 *      调试单组件时直接前台跑 node watchdog.mjs / node console-server.mjs；
 *   4. pi-web 保持独立（它死了要靠 watchdog 报警，绝不能合进来）。
 *
 * 用法：
 *   node link-supervisor.mjs          # 前台，一个终端同时跑两个服务
 *   run-link.bat                      # 同上（双击 / 开机启动项都调它）
 *
 * 日志：
 *   子进程 stdout/stderr → 前台按行打前缀，同时追加到各自的 .out.log
 *   （watchdog.out.log / console.out.log，路径与原来两个 .bat 一致）；
 *   监管者自己的消息 → 前台 + link.out.log。
 */
import { spawn } from "node:child_process";
import { appendFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { STATE_DIR } from "./config.mjs";

const ROOT = import.meta.dirname;
const LINK_LOG = join(STATE_DIR, "link.out.log");

mkdirSync(STATE_DIR, { recursive: true });

function logSelf(line) {
  const stamped = `[${new Date().toISOString()}] [supervisor] ${line}`;
  console.log(stamped);
  try {
    appendFileSync(LINK_LOG, `${stamped}\n`, "utf8");
  } catch {
    /* 日志写不进去也不能影响主流程 */
  }
}

const CHILDREN = [
  // 先起中转，再起看门狗：watchdog 启动时会 probeBroker() 自检出口，
  // 中转晚起几百毫秒就会自检失败（verify.mjs C5）。顺序即依赖。
  {
    name: "console",
    script: "console-server.mjs",
    outLog: join(STATE_DIR, "console.out.log"),
    prefix: "[console]",
    quickFails: 0,
    child: null,
  },
  {
    name: "watchdog",
    script: "watchdog.mjs",
    outLog: join(STATE_DIR, "watchdog.out.log"),
    prefix: "[watchdog]",
    quickFails: 0,
    child: null,
  },
];

let shuttingDown = false;

/** 子进程一行输出 → 前台（带前缀）+ 原来的 .out.log（追加，与旧 .bat 一致） */
function fanout(spec, chunk, isErr) {
  const text = chunk.toString("utf8");
  const lines = text.split(/\r?\n/);
  for (const line of lines) {
    if (!line) continue;
    const stamped = `${spec.prefix} ${line}`;
    if (isErr) console.error(stamped);
    else console.log(stamped);
    try {
      appendFileSync(spec.outLog, `${line}\n`, "utf8");
    } catch {
      /* 无所谓 */
    }
  }
}

function startChild(spec) {
  if (shuttingDown) return;
  const startedAt = Date.now();
  logSelf(`starting ${spec.name} (${spec.script})...`);
  let child;
  try {
    child = spawn(process.execPath, [join(ROOT, spec.script)], {
      cwd: ROOT,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    });
  } catch (error) {
    logSelf(`XXX spawn ${spec.name} failed: ${error.message}, retry in 5s`);
    setTimeout(() => startChild(spec), 5000);
    return;
  }
  spec.child = child;

  child.stdout.on("data", (chunk) => fanout(spec, chunk, false));
  child.stderr.on("data", (chunk) => fanout(spec, chunk, true));
  child.on("error", (error) => {
    logSelf(`XXX ${spec.name} spawn error: ${error.message}`);
  });
  child.on("close", (code, signal) => {
    spec.child = null;
    if (shuttingDown) {
      logSelf(`${spec.name} stopped (supervisor shutting down)`);
      return;
    }
    const uptime = Date.now() - startedAt;
    // 快速退出（<10s）大概率是锁 contention（老进程还活着）或启动失败，
    // 用退避重启：2s → 4s → 8s ... 上限 30s，无限重试（老进程死了就能接管）。
    // exit 0 + 秒退时多半是"已有实例在跑"，打一行提示免得人懵。
    let delay = 2000;
    if (uptime < 10_000) {
      spec.quickFails += 1;
      delay = Math.min(30_000, 2000 * 2 ** (spec.quickFails - 1));
      if (code === 0) {
        logSelf(
          `${spec.name} exited in ${(uptime / 1000).toFixed(1)}s (code 0, likely single-instance lock held by old process). ` +
            `retry in ${delay / 1000}s — stop the old link-supervisor first if this repeats.`,
        );
      } else {
        logSelf(`${spec.name} crashed (code=${code} signal=${signal}) after ${(uptime / 1000).toFixed(1)}s, retry in ${delay / 1000}s`);
      }
    } else {
      spec.quickFails = 0;
      logSelf(`${spec.name} exited (code=${code} signal=${signal}) after ${(uptime / 1000).toFixed(1)}s, restart in 2s`);
    }
    setTimeout(() => startChild(spec), delay);
  });
}

function shutdown(signal) {
  if (shuttingDown) return;
  shuttingDown = true;
  logSelf(`received ${signal}, stopping children...`);
  for (const spec of CHILDREN) {
    try {
      spec.child?.kill("SIGTERM");
    } catch {
      /* 已经没了 */
    }
  }
  // 给子进程 3s 优雅退出，超时直接走（Windows 上 SIGTERM 本来就是强杀语义）
  setTimeout(() => {
    logSelf("supervisor exit");
    process.exit(0);
  }, 3000).unref();
}

for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
  process.on(signal, () => shutdown(signal));
}
process.on("exit", () => {
  for (const spec of CHILDREN) {
    try {
      spec.child?.kill("SIGTERM");
    } catch {
      /* ignore */
    }
  }
});

logSelf(`link-supervisor start pid=${process.pid} node=${process.execPath}`);
// 错峰启动：console 先起，watchdog 晚 2.5s —— 否则 watchdog 的 probeBroker()
// 会打在中转 listen 之前，verify.mjs C5 必挂（刚才是并行 spawn 撞上的）。
startChild(CHILDREN[0]);
setTimeout(() => startChild(CHILDREN[1]), 2500);
