/**
 * 单实例互斥（Windows 安全版）。
 *
 * 踩过的坑：最初用"绑一个回环端口"当互斥，在 Linux/macOS 上成立，但在 Windows 上
 * Node 的 net 默认带 SO_REUSEADDR，**两个进程能绑同一个 addr:port 且都成功**，
 * 于是互斥形同虚设（verify.mjs 的 C1 就是因此误报"看门狗没起来"）。
 *
 * 改用独占创建锁文件（O_EXCL）+ PID 存活校验：
 *   - 抢到 wx 创建 → 我的
 *   - 已存在 → 读 pid，process.kill(pid, 0) 探活
 *       · 活着 → 真有实例在跑，退出
 *       · 死了 → 陈旧锁，删掉重抢
 */
import { closeSync, existsSync, openSync, readFileSync, unlinkSync, writeSync } from "node:fs";

function pidAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    // EPERM = 进程在，但不属于我 → 也算活着
    return error.code === "EPERM";
  }
}

/**
 * @param {string} lockPath
 * @returns {{ ok: true, release: () => void } | { ok: false, holderPid: number|null }}
 */
export function acquireSingleInstance(lockPath) {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    let fd;
    try {
      fd = openSync(lockPath, "wx"); // O_CREAT | O_EXCL
      writeSync(fd, String(process.pid));
      closeSync(fd);
      const release = () => {
        try {
          // 只删自己写的锁
          if (existsSync(lockPath) && readFileSync(lockPath, "utf8").trim() === String(process.pid)) {
            unlinkSync(lockPath);
          }
        } catch {
          /* 无所谓 */
        }
      };
      process.once("exit", release);
      process.once("SIGINT", () => { release(); process.exit(130); });
      process.once("SIGTERM", () => { release(); process.exit(143); });
      return { ok: true, release };
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      let holderPid = null;
      try {
        holderPid = Number(readFileSync(lockPath, "utf8").trim());
      } catch {
        /* 读不到就是坏锁 */
      }
      if (pidAlive(holderPid)) return { ok: false, holderPid };
      // 陈旧锁：持有者已经没了，删掉重抢
      try {
        unlinkSync(lockPath);
      } catch {
        /* 竞争中被别人删了，下一轮重试即可 */
      }
    }
  }
  return { ok: false, holderPid: null };
}
