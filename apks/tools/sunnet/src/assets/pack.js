// ============================================================================
// pack.js —— 「清单方案包」数据层（格式名 sunnet.pack，版本 1）
//
// 作用：把 App 里「散装」页的所有数据（采购清单 / 接线表 / 组装步骤 / 引脚表 …）
//       统一成一种 JSON 格式。于是：
//         1) 换个产品（自动浇花、鱼缸、卷帘…）时，把规范交给别的 AI，
//            它吐一份 JSON 回来 → App 里粘贴导入 → 直接变成新的购买清单；
//         2) App 里「导出方案」把当前数据吐成同一个格式，可以交给 AI 改。
//
// 格式定义见项目根目录：清单数据规范.md
// 这份文件只做数据：解析 / 校验 / 归一化 / 存取。渲染在 app.js 里。
// ============================================================================
'use strict';

const PACK_FORMAT = 'sunnet.pack';
const PACK_VER = 1;
const PACK_KEY = 'sunnet.pack.current';   // 导入的方案存这里

// ----------------------------------------------------------------- 富文本
// 允许 AI 用少量行内标签做强调，其余一律转义，避免把页面结构搞乱。
const RICH_TAGS = /<\/?(b|strong|i|em|code|br)\s*\/?>/gi;

function richText(s) {
  if (s == null) return '';
  let t = String(s);
  const keep = [];
  t = t.replace(RICH_TAGS, (m) => { keep.push(m); return '\u0000' + (keep.length - 1) + '\u0000'; });
  t = t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return t.replace(/\u0000(\d+)\u0000/g, (m, i) => keep[+i]);
}

// ----------------------------------------------------------------- 解析 / 校验
function packFail(msg) {
  const e = new Error(msg);
  e.packErr = true;
  throw e;
}

// 容忍 AI 的常见坏习惯：```json 围栏、前后废话、末尾多余逗号、全角引号
function parsePackText(text) {
  let t = String(text == null ? '' : text).trim();
  if (!t) packFail('内容是空的');
  t = t.replace(/^\uFEFF/, '');
  const fence = t.match(/```(?:json|JSON)?\s*([\s\S]*?)```/);
  if (fence) t = fence[1].trim();
  const a = t.indexOf('{');
  const b = t.lastIndexOf('}');
  if (a < 0 || b <= a) packFail('没找到 JSON 对象（要以 { 开头、} 结尾）');
  t = t.slice(a, b + 1);
  t = t.replace(/[\u201c\u201d]/g, '"').replace(/[\uff0c]/g, ',');
  t = t.replace(/,\s*([}\]])/g, '$1');   // 去掉 }, 或 ], 这种尾逗号
  try {
    return JSON.parse(t);
  } catch (err) {
    packFail('JSON 语法错误：' + err.message + '（检查引号、逗号、括号是否配对）');
  }
}

function pkStr(v, d) { return v == null ? (d == null ? '' : d) : String(v); }
function pkInt(v, d) {
  const n = Math.round(parseFloat(String(v)));   // 容忍 "2 个" / "2pcs"
  return isFinite(n) && n > 0 ? n : d;
}

// 条目：对象，或数组简写 [名称, 搜索词, 数量, 单价, 规格]
function normalizeItem(raw, where) {
  if (Array.isArray(raw)) {
    raw = { name: raw[0], kw: raw[1], qty: raw[2], price: raw[3], spec: raw[4], volt: raw[5], part: raw[6], why: raw[7] };
  }
  if (!raw || typeof raw !== 'object') packFail(where + ' 不是对象，也不是数组简写');
  const name = pkStr(raw.name).trim();
  if (!name) packFail(where + ' 缺少 name（零件名称）');
  let price = raw.price;
  if (typeof price === 'string') price = price.trim();
  else { const n = Number(price); price = isFinite(n) ? n : 0; }
  const links = (raw.links && typeof raw.links === 'object') ? {
    taobao: pkStr(raw.links.taobao), pdd: pkStr(raw.links.pdd), '1688': pkStr(raw.links['1688']),
  } : null;
  const it = {
    id: pkStr(raw.id).trim(),
    name: name,
    qty: pkInt(raw.qty, 1),
    price: price,
    kw: pkStr(raw.kw).trim(),
    volt: pkStr(raw.volt).trim(),
    spec: pkStr(raw.spec).trim(),
    part: pkStr(raw.part).trim(),
    why: pkStr(raw.why).trim(),
  };
  if (links && (links.taobao || links.pdd || links['1688'])) it.links = links;
  return it;
}

function normalizeGroup(raw, gi) {
  if (!raw || typeof raw !== 'object') packFail('groups[' + gi + '] 不是对象');
  const items = Array.isArray(raw.items) ? raw.items : null;
  if (!items || !items.length) packFail('groups[' + gi + '] 的 items 为空（每个方案至少要有 1 个零件）');
  const g = {
    id: pkStr(raw.id, 'g' + gi).trim() || ('g' + gi),
    title: pkStr(raw.title, '方案 ' + gi).trim(),
    sub: pkStr(raw.sub).trim(),
    kind: pkStr(raw.kind, 'plain').trim() === 'check' ? 'check' : 'plain',
    intro: pkStr(raw.intro).trim(),
    foot: pkStr(raw.foot).trim(),
    skip: Array.isArray(raw.skip) ? raw.skip.map((s) => pkStr(s).trim()).filter(Boolean) : [],
    items: items.map((it, ii) => normalizeItem(it, 'groups[' + gi + '].items[' + ii + ']')),
  };
  // id 去重：没写 id 的用 序号 补，勾选状态才有地方存
  const seen = {};
  g.items.forEach((it, ii) => {
    let id = it.id || (g.id + '-' + (ii + 1));
    while (seen[id]) id = id + '_';
    seen[id] = 1;
    it.id = id;
  });
  return g;
}

// 接线行：对象，或数组简写 [位号, 模块/说明, GPIO, 电压, 备注]
function normalizeWire(raw, i) {
  if (Array.isArray(raw)) raw = { part: raw[0], mod: raw[1], gpio: raw[2], volt: raw[3], note: raw[4] };
  if (!raw || typeof raw !== 'object') packFail('wiring[' + i + '] 不是对象');
  return {
    part: pkStr(raw.part).trim(),
    mod: pkStr(raw.mod || raw.why).trim(),
    gpio: pkStr(raw.gpio).trim(),
    volt: pkStr(raw.volt).trim(),
    note: pkStr(raw.note).trim(),
  };
}

function normalizeStep(raw, i) {
  if (Array.isArray(raw)) raw = { t: raw[0], d: raw[1] };
  if (typeof raw === 'string') raw = { t: raw, d: '' };
  if (!raw || typeof raw !== 'object') packFail('steps[' + i + '] 不是对象');
  return { t: pkStr(raw.t || raw.title).trim(), d: pkStr(raw.d || raw.text).trim() };
}

function normalizeNote(raw, i) {
  if (typeof raw === 'string') raw = { text: raw };
  if (!raw || typeof raw !== 'object') packFail('notes[' + i + '] 不是对象');
  const lv = pkStr(raw.level, 'warn').trim();
  return { level: (lv === 'info' || lv === 'tip') ? 'info' : 'warn', text: pkStr(raw.text).trim() };
}

// 主入口：字符串/对象 → 干净可用的方案包
function normalizePack(raw) {
  if (typeof raw === 'string') raw = parsePackText(raw);
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) packFail('顶层必须是一个 JSON 对象');
  if (raw.format && pkStr(raw.format).trim() !== PACK_FORMAT) {
    packFail('format 必须是 "' + PACK_FORMAT + '"，你给的是 "' + raw.format + '"');
  }
  const ver = Number(raw.ver);
  if (raw.ver != null && isFinite(ver) && ver > PACK_VER) {
    packFail('ver=' + raw.ver + ' 比本 App 支持的 v' + PACK_VER + ' 新，请升级 App');
  }
  if (!Array.isArray(raw.groups) || !raw.groups.length) {
    packFail('缺少 groups（要一个数组，每项是一个方案分组，至少 1 组）');
  }
  const meta = raw.meta && typeof raw.meta === 'object' ? raw.meta : {};
  const volt = raw.volt && typeof raw.volt === 'object' ? raw.volt : {};
  const cmp = raw.compare && typeof raw.compare === 'object' ? raw.compare : {};

  const pack = {
    format: PACK_FORMAT,
    ver: PACK_VER,
    meta: {
      id: pkStr(meta.id, 'custom').trim() || 'custom',
      title: pkStr(meta.title, '采购方案').trim(),
      product: pkStr(meta.product).trim(),
      subtitle: pkStr(meta.subtitle).trim(),
      currency: pkStr(meta.currency, 'CNY').trim() || 'CNY',
      updated: pkStr(meta.updated).trim(),
      note: pkStr(meta.note).trim(),
    },
    groups: raw.groups.map(normalizeGroup),
    volt: {
      note: pkStr(volt.note).trim(),
      rows: (Array.isArray(volt.rows) ? volt.rows : []).map((r, i) => {
        if (Array.isArray(r)) return { v: pkStr(r[0]), who: pkStr(r[1]), how: pkStr(r[2]), warn: pkStr(r[3]) };
        if (!r || typeof r !== 'object') packFail('volt.rows[' + i + '] 不是对象');
        return { v: pkStr(r.v), who: pkStr(r.who), how: pkStr(r.how), warn: pkStr(r.warn) };
      }),
    },
    power: pkStr(raw.power),
    wiring: (Array.isArray(raw.wiring) ? raw.wiring : []).map(normalizeWire),
    steps: (Array.isArray(raw.steps) ? raw.steps : []).map(normalizeStep),
    notes: (Array.isArray(raw.notes) ? raw.notes : []).map(normalizeNote),
    pinPatch: pkStr(raw.pinPatch),
    compare: {
      head: (Array.isArray(cmp.head) ? cmp.head : ['项目', '原方案', '本方案']).map((s) => pkStr(s)),
      rows: (Array.isArray(cmp.rows) ? cmp.rows : []).map((r, i) => {
        if (Array.isArray(r)) return { k: pkStr(r[0]), a: pkStr(r[1]), b: pkStr(r[2]), good: 'b' };
        if (!r || typeof r !== 'object') packFail('compare.rows[' + i + '] 不是对象');
        return { k: pkStr(r.k), a: pkStr(r.a), b: pkStr(r.b), good: pkStr(r.good, 'b') === 'a' ? 'a' : 'b' };
      }),
    },
    extraCards: (Array.isArray(raw.extraCards) ? raw.extraCards : []).map((c, i) => {
      if (!c || typeof c !== 'object') packFail('extraCards[' + i + '] 不是对象');
      return { title: pkStr(c.title, '补充 ' + (i + 1)).trim(), html: pkStr(c.html) };
    }),
  };
  return pack;
}

// ----------------------------------------------------------------- 内置默认方案
// 用 bom.js 里的老数据拼一份标准包（老数据支持数组简写，这里一并归一化）
function buildDefaultPack() {
  return normalizePack({
    format: PACK_FORMAT,
    ver: PACK_VER,
    meta: {
      id: 'sunnet',
      title: '太阳网控制器 · 散装模块方案',
      product: '风光雨自动控制太阳网（遮阳网）',
      subtitle: '全部买现成模块，不画板不贴片',
      currency: 'CNY',
      updated: '2026-10-16',
      note: '价格是 2026 年淘宝散件中位价，下单前按搜索词自己比价',
    },
    groups: [
      { id: 'A', title: '散装采购清单', sub: '全部买现成模块，不画板不贴片', kind: 'check',
        intro: '点一行 = 勾上「已买」，勾选存在手机里。用的还是同一套固件（只改引脚表），所以这个 App 直接能用。',
        skip: BOM_MIN_SKIP, items: BOM_A },
      { id: 'B', title: '方案 B · 室外长年运行', sub: '约 ¥380', kind: 'plain',
        intro: '风吹日晒一年以上，把怕氧化的、怕水的换成工业件。', items: BOM_B },
      { id: 'C', title: '方案 C · 网机是 220V 交流', sub: '别用 DRV8871', kind: 'plain',
        intro: '220V 电机用继电器/接触器，强弱电分开走。', items: BOM_C,
        foot: '换成继电器后，电机就是「有/无」两态，需要把 motor_drv8871.cpp 换成一个继电器输出实现（约 30 行）。220V 侧单独走电器盒 + 漏保。' },
      { id: 'D', title: '方案 D · 完全不动手', sub: '买成品', kind: 'plain',
        intro: '优点：0 开发。缺点：协议不开放，这个 App 连不上它。', items: BOM_D },
    ],
    volt: { note: VOLT_NOTE, rows: VOLT_SYS },
    power: POWER_TEXT,
    wiring: WIRING,
    steps: STEPS,
    notes: NOTES,
    pinPatch: PIN_PATCH,
    compare: COMPARE,
  });
}

// ----------------------------------------------------------------- 存取
let PACK = null;

function packLoad() {
  try {
    const raw = localStorage.getItem(PACK_KEY);
    if (!raw) return null;
    return normalizePack(raw);
  } catch (e) {
    console.warn('本地方案包读不了，回到默认', e);
    return null;
  }
}

function activePack() {
  if (!PACK) PACK = packLoad() || buildDefaultPack();
  return PACK;
}

function packSave(p) {
  PACK = p;
  try { localStorage.setItem(PACK_KEY, JSON.stringify(p)); } catch (e) { toast('本地存不下：' + e.message, true); }
}

function packReset() {
  try { localStorage.removeItem(PACK_KEY); } catch (e) {}
  PACK = null;
  return activePack();
}

function packJson(p) {
  return JSON.stringify(p || activePack(), null, 2);
}

// 只导出「能再导入」的最小结构（渲染时补的字段不导出）
function packExportable() {
  const p = activePack();
  return {
    format: PACK_FORMAT, ver: PACK_VER,
    meta: p.meta,
    groups: p.groups.map((g) => ({
      id: g.id, title: g.title, sub: g.sub, kind: g.kind, intro: g.intro, foot: g.foot, skip: g.skip,
      items: g.items.map((it) => {
        const o = { id: it.id, name: it.name, qty: it.qty, price: it.price };
        if (it.kw) o.kw = it.kw;
        if (it.volt) o.volt = it.volt;
        if (it.spec) o.spec = it.spec;
        if (it.part) o.part = it.part;
        if (it.why) o.why = it.why;
        if (it.links) o.links = it.links;
        return o;
      }),
    })),
    volt: p.volt, power: p.power, wiring: p.wiring, steps: p.steps,
    notes: p.notes, pinPatch: p.pinPatch, compare: p.compare, extraCards: p.extraCards,
  };
}

// 导入：文本 → 校验 → 存 → 返回 {pack, warn}
function packImport(text) {
  const p = normalizePack(text);
  packSave(p);
  return p;
}
