/**
 * 生成派发台（console-server.mjs）需要的图标，输出到 web/。
 *
 * 为什么自己写 PNG 编码：项目到现在为止零依赖（不装 sharp/canvas），
 * 而图标只是「圆角方块 + 一个 π 字」，用 4× 超采样手搓就够干净了。
 *
 * 产物：
 *   web/favicon.png            32×32   浏览器标签页
 *   web/icon-192.png           192×192 Android「添加到主屏幕」
 *   web/icon-512.png           512×512 同上，高分屏 / 应用抽屉
 *   web/icon-maskable-512.png  512×512 maskable（满幅底 + 缩小字形，防被拉起裁掉）
 *   web/apple-touch-icon.png   180×180 iOS / 微信里加到桌面
 *   web/manifest.webmanifest   PWA 清单（standalone，桌面图标 + 独立窗口）
 *
 * 用法：node make-icons.mjs
 */
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { deflateSync } from "node:zlib";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "web");

// ── 颜色 ─────────────────────────────────────────────────────────────────
const BG = [0x0f, 0x76, 0x6e]; // 和 App 主色一致（teal）
const FG = [0xff, 0xff, 0xff];

// ── PNG 编码（8bit RGBA） ─────────────────────────────────────────────────
const CRC_TABLE = (() => {
  const t = new Int32Array(256);
  for (let n = 0; n < 256; n += 1) {
    let c = n;
    for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c;
  }
  return t;
})();

function crc32(buf) {
  let c = -1;
  for (let i = 0; i < buf.length; i += 1) c = CRC_TABLE[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ -1) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length, 0);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body), 0);
  return Buffer.concat([len, body, crc]);
}

function encodePng(size, rgba) {
  const stride = size * 4;
  const raw = Buffer.alloc((stride + 1) * size);
  for (let y = 0; y < size; y += 1) {
    raw[y * (stride + 1)] = 0; // filter: none
    rgba.copy(raw, y * (stride + 1) + 1, y * stride, (y + 1) * stride);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 6; // color type: RGBA
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", deflateSync(raw, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

// ── 画图（4× 超采样，边缘自然带抗锯齿） ────────────────────────────────────
const SS = 4;

/** 圆角矩形：radius=0 就是直角（maskable 用满幅） */
function insideRounded(x, y, w, h, r) {
  if (x < 0 || y < 0 || x >= w || y >= h) return false;
  if (r <= 0) return true;
  const rx = Math.min(x, w - x);
  const ry = Math.min(y, h - y);
  if (rx >= r || ry >= r) return true;
  const dx = r - rx;
  const dy = r - ry;
  return dx * dx + dy * dy <= r * r;
}

/** π 的三根圆角横竖杠，坐标按画布边长比例给 */
function piParts(n, scale) {
  const c = n / 2;
  const s = (v) => c + (v - c) * scale;
  const T = n * 0.085; // 笔画粗细
  const parts = [
    // 顶横
    { x0: n * 0.27, y0: n * 0.31, x1: n * 0.73, y1: n * 0.31 + T, r: T * 0.42 },
    // 左腿
    { x0: n * 0.335, y0: n * 0.36, x1: n * 0.335 + T, y1: n * 0.71, r: T * 0.42 },
    // 右腿
    { x0: n * 0.58, y0: n * 0.36, x1: n * 0.58 + T, y1: n * 0.71, r: T * 0.42 },
  ];
  return parts.map((p) => ({
    x0: s(p.x0), y0: s(p.y0), x1: s(p.x1), y1: s(p.y1), r: p.r * scale,
  }));
}

function paint(n) {
  const glyph = piParts(n, 1);
  return glyph;
}

function insideGlyph(x, y, parts) {
  for (const p of parts) {
    if (x >= p.x0 && x <= p.x1 && y >= p.y0 && y <= p.y1) {
      if (insideRounded(x - p.x0, y - p.y0, p.x1 - p.x0, p.y1 - p.y0, p.r)) return true;
    }
  }
  return false;
}

/**
 * @param {number} size 输出边长
 * @param {"rounded"|"maskable"} shape rounded=带圆角（桌面）；maskable=满幅底（防遮罩裁掉字形）
 */
function makeIcon(size, shape) {
  const n = size * SS;
  const radius = shape === "rounded" ? n * 0.235 : 0;
  const glyph = shape === "rounded" ? paint(n) : paint(n).map((p) => {
    // maskable：字形缩到 72%，落在安全区内
    const c = n / 2;
    const k = 0.72;
    return {
      x0: c + (p.x0 - c) * k, y0: c + (p.y0 - c) * k,
      x1: c + (p.x1 - c) * k, y1: c + (p.y1 - c) * k, r: p.r * k,
    };
  });

  const out = Buffer.alloc(size * size * 4);
  const total = SS * SS;

  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      let sr = 0, sg = 0, sb = 0, covered = 0;
      for (let sy = 0; sy < SS; sy += 1) {
        for (let sx = 0; sx < SS; sx += 1) {
          const px = x * SS + sx + 0.5;
          const py = y * SS + sy + 0.5;
          if (!insideRounded(px, py, n, n, radius)) continue;
          const col = insideGlyph(px, py, glyph) ? FG : BG;
          sr += col[0]; sg += col[1]; sb += col[2];
          covered += 1;
        }
      }
      const i = (y * size + x) * 4;
      if (covered === 0) continue;
      out[i] = Math.round(sr / covered);
      out[i + 1] = Math.round(sg / covered);
      out[i + 2] = Math.round(sb / covered);
      out[i + 3] = Math.round((covered / total) * 255);
    }
  }
  return encodePng(size, out);
}

// ── 写盘 ─────────────────────────────────────────────────────────────────
mkdirSync(OUT, { recursive: true });

const files = [
  ["favicon.png", makeIcon(32, "rounded")],
  ["apple-touch-icon.png", makeIcon(180, "rounded")],
  ["icon-192.png", makeIcon(192, "rounded")],
  ["icon-512.png", makeIcon(512, "rounded")],
  ["icon-maskable-512.png", makeIcon(512, "maskable")],
];

for (const [name, buf] of files) {
  writeFileSync(join(OUT, name), buf);
  console.log(`  ${name.padEnd(26)} ${String(buf.length).padStart(7)} 字节`);
}

const manifest = {
  name: "pi 派发台",
  short_name: "派发台",
  description: "把任务派给 pi，看会话状态，管理通知订阅",
  start_url: "/",
  scope: "/",
  display: "standalone",
  background_color: "#14161a",
  theme_color: "#14161a",
  icons: [
    { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
    { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
    { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
  ],
};
writeFileSync(join(OUT, "manifest.webmanifest"), `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`  ${"manifest.webmanifest".padEnd(26)} ${String(JSON.stringify(manifest).length).padStart(7)} 字节`);
console.log(`\n图标已写入 ${OUT}`);
