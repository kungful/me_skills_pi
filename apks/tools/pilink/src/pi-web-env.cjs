// Ensure pi-web's Next.js server can identify the Pi package that owns the session.
// This is loaded through NODE_OPTIONS before both pi-web and its Next child start.
//
// 分享版：不再写死任何人的 node_modules 绝对路径，改为运行时按优先级探测：
//   1) PI_PACKAGE_ROOT 环境变量（显式指定，最高优先）
//   2) `npm root -g` 的输出
//   3) node 可执行文件所在目录 / 它的上级目录（nvm-windows、Volta、fnm 等常见布局）
//   4) PATH 里 pi-web 可执行文件所在目录的各级上级
// 每个候选根目录依次尝试 <root>/@agegr/pi-web/node_modules/@earendil-works/pi-coding-agent
// 和 <root>/@earendil-works/pi-coding-agent。
// 全都找不到就什么都不设（pi-web 仍能起来，只是子代理包识别可能失败），只打一行日志。
const { execFileSync } = require("node:child_process");
const { existsSync } = require("node:fs");
const { delimiter, dirname, join, resolve } = require("node:path");

const PKG_RELATIVE = ["@earendil-works", "pi-coding-agent"];
const WEB_RELATIVE = ["@agegr", "pi-web", "node_modules", ...PKG_RELATIVE];

function npmGlobalRoot() {
  const bin = process.platform === "win32" ? "npm.cmd" : "npm";
  try {
    return execFileSync(bin, ["root", "-g"], { encoding: "utf8", timeout: 20_000 }).trim();
  } catch {
    return "";
  }
}

function whichPiWeb() {
  const finder = process.platform === "win32" ? "where" : "which";
  try {
    return execFileSync(finder, ["pi-web"], { encoding: "utf8", timeout: 10_000 })
      .split(/\r?\n/)
      .map((s) => s.trim())
      .filter(Boolean);
  } catch {
    return [];
  }
}

/** 收集所有可能的全局 node_modules 根目录（去重、保持优先级） */
function candidateRoots() {
  const roots = [];
  const push = (p) => {
    if (!p) return;
    const abs = resolve(p);
    if (!roots.includes(abs)) roots.push(abs);
  };

  if (process.env.PI_PACKAGE_ROOT) push(process.env.PI_PACKAGE_ROOT);
  push(process.env.NODE_PATH?.split(delimiter).find((s) => s.includes("node_modules")));
  push(npmGlobalRoot());

  // node 本体目录与它的上级（nvm-windows: <ver>\node.exe，node_modules 在同级）
  let dir = dirname(process.execPath);
  for (let i = 0; i < 3 && dir; i += 1) {
    push(join(dir, "node_modules"));
    dir = dirname(dir);
  }

  // PATH 上的 pi-web 所在目录的各级上级
  for (const exe of whichPiWeb()) {
    let d = dirname(exe);
    for (let i = 0; i < 4 && d; i += 1) {
      push(join(d, "node_modules"));
      d = dirname(d);
    }
  }
  return roots;
}

function resolvePiPackageRoot() {
  for (const root of candidateRoots()) {
    for (const rel of [WEB_RELATIVE, PKG_RELATIVE]) {
      const p = join(root, ...rel);
      if (existsSync(p)) return p;
    }
  }
  return "";
}

const piPackageRoot = resolvePiPackageRoot();
if (piPackageRoot) {
  process.env.PI_SUBAGENTS_PI_CODING_AGENT_PACKAGE_ROOT = piPackageRoot;
  process.env.PI_PACKAGE_DIR = piPackageRoot;
  console.log(`[pi-web-env] pi 包根目录：${piPackageRoot}`);
} else {
  console.warn(
    "[pi-web-env] 未能定位 @earendil-works/pi-coding-agent，跳过包根目录注入" +
      "（如需请设 PI_PACKAGE_ROOT 环境变量指向它）",
  );
}
