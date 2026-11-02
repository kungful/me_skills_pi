/**
 * 脑图 / 节点逻辑图编辑器 —— pi-web-ui 界面插件（客户端视图）。
 *
 * 移植自 pi-web-custom（`agegr/pi-web` 分叉）里的 `MindMapPanel.tsx`：
 * 同样的节点类型、同样的序列化大纲格式、同样的交互（拖节点、右侧圆点拉线、
 * 拖到空白处弹类型菜单、滚轮缩放、双击空白新建、自动整理、文本导入、
 * 提示生成、图片节点），只是把 React 换成了原生 DOM + SVG。
 *
 * 宿主只给两个通道（ctx.send / ctx.onData），所以插件自己负责：
 *   - 顶栏 tab 里的编辑器（mount 目标）
 *   - 输入框控制条上的「🧠 脑图」按钮（挂到 .input-tools，CSS order 靠左）
 *   - 点按钮打开的全屏浮层
 *   - 「插入输入框」：直接写宿主 textarea（原生 setter + input 事件，React 认）
 */
import {
	MINDMAP_KINDS,
	MINDMAP_NODE_HEIGHT as NODE_H,
	MINDMAP_NODE_WIDTH as NODE_W,
	autoLayoutMindMap,
	connectMindMapNodes,
	createMindMapNode,
	deserializeMindMap,
	dropNodePositions,
	emptyMindMap,
	nextNodeId,
	promptToMindMap,
	reindexMindMap,
	serializeMindMap,
} from "./mindmap.mjs";
import { parseAiGraph } from "./ai.mjs";
import { format, getStrings } from "./i18n.mjs";

const KIND_COLORS = {
	goal: "#f59e0b",
	condition: "#38bdf8",
	step: "#22c55e",
	idea: "#a855f7",
	risk: "#ef4444",
	result: "#14b8a6",
	image: "#e879f9",
};

const MIN_SCALE = 0.35;
const MAX_SCALE = 2;
const MAX_IMAGE_EDGE = 720;
const MAX_IMAGE_CHARS = 900_000;
const STORAGE_KEY = "pi-web-ui:mindmap:graph";
const SAVE_DEBOUNCE_MS = 250;

// 模块被宿主 import 即可用：即使没点开 tab，也能挂上输入框旁的小按钮
globalThis.__piMindmapLoaded = true;

const S = getStrings();
const LABELS = { header: S.header, hint: S.hint, cross: S.cross, detail: S.detail, image: S.labelImage, kinds: S.kinds };

// ---------------------------------------------------------------------------
// 模型：一份共享状态（tab 视图与浮层视图共用），改动落到 localStorage
// ---------------------------------------------------------------------------

function loadGraph() {
	try {
		const raw = window.localStorage.getItem(STORAGE_KEY);
		if (!raw) return emptyMindMap();
		const parsed = JSON.parse(raw);
		if (!parsed || !Array.isArray(parsed.nodes)) return emptyMindMap();
		const nodes = parsed.nodes
			.filter((n) => n && typeof n.id === "string")
			.map((n) => ({
				id: n.id,
				kind: MINDMAP_KINDS.includes(n.kind) ? n.kind : "idea",
				title: typeof n.title === "string" ? n.title : "",
				detail: typeof n.detail === "string" ? n.detail : "",
				x: Number.isFinite(n.x) ? n.x : 0,
				y: Number.isFinite(n.y) ? n.y : 0,
				...(typeof n.image === "string" ? { image: n.image } : {}),
				...(typeof n.imageName === "string" ? { imageName: n.imageName } : {}),
			}));
		const ids = new Set(nodes.map((n) => n.id));
		const edges = (Array.isArray(parsed.edges) ? parsed.edges : [])
			.filter((e) => e && ids.has(e.from) && ids.has(e.to) && e.from !== e.to)
			.map((e) => ({
				id: typeof e.id === "string" ? e.id : `e${e.from}-${e.to}`,
				from: e.from,
				to: e.to,
				label: typeof e.label === "string" ? e.label : "",
			}));
		return { nodes, edges };
	} catch {
		return emptyMindMap();
	}
}

const store = (() => {
	let graph = loadGraph();
	let timer = null;
	const listeners = new Set();
	const save = () => {
		if (timer !== null) window.clearTimeout(timer);
		timer = window.setTimeout(() => {
			timer = null;
			try {
				if (graph.nodes.length === 0 && graph.edges.length === 0) window.localStorage.removeItem(STORAGE_KEY);
				else window.localStorage.setItem(STORAGE_KEY, JSON.stringify(graph));
			} catch {
				// 存储满或被禁：这一份仍然可用，只是刷新后不保留
			}
		}, SAVE_DEBOUNCE_MS);
	};
	return {
		get: () => graph,
		/** `opts.source` 是改动发起者；`opts.rebuild === false` 表示只需重画连线/位置 */
		set(next, opts = {}) {
			graph = next;
			save();
			for (const fn of listeners) {
				try {
					fn(graph, opts);
				} catch (err) {
					console.error("[mindmap] listener failed:", err);
				}
			}
		},
		subscribe(fn) {
			listeners.add(fn);
			return () => listeners.delete(fn);
		},
	};
})();

const serializedText = () => serializeMindMap(store.get(), LABELS);

// ---------------------------------------------------------------------------
// 宿主输入框桥
// ---------------------------------------------------------------------------

function composerTextarea() {
	const all = [...document.querySelectorAll("textarea")];
	const visible = all.filter((el) => el.offsetParent !== null);
	const inComposer = document.querySelector(".inputbox-row textarea, .inputbox textarea");
	const looksLikeComposer = (el) => (el.getAttribute("placeholder") || "").includes("pi");
	// 宿主对话面板被切到别的 tab 时 textarea 仍在 DOM（只是不可见），照样能写入草稿。
	if (inComposer) return inComposer;
	return visible.find(looksLikeComposer) ?? all.find(looksLikeComposer) ?? visible[visible.length - 1] ?? null;
}

/** 把大纲追加到草稿尾部（空行分隔），不发送。返回是否成功。 */
function insertIntoComposer(text) {
	if (!text) return false;
	const area = composerTextarea();
	if (!area) return false;
	const current = area.value ?? "";
	const joined = current.trim() ? `${current.replace(/[ \t]+$/, "")}\n\n${text}` : text;
	const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set;
	if (setter) setter.call(area, joined);
	else area.value = joined;
	area.dispatchEvent(new Event("input", { bubbles: true }));
	try {
		area.focus();
		area.setSelectionRange(joined.length, joined.length);
	} catch {
		// 不支持的浏览器无所谓
	}
	return true;
}

async function copyText(text) {
	try {
		await navigator.clipboard.writeText(text);
		return true;
	} catch {
		const area = document.createElement("textarea");
		area.value = text;
		area.style.cssText = "position:fixed;left:-9999px;top:0";
		document.body.appendChild(area);
		area.select();
		let ok = false;
		try {
			ok = document.execCommand("copy");
		} catch {
			ok = false;
		}
		area.remove();
		return ok;
	}
}

// ---------------------------------------------------------------------------
// 样式
// ---------------------------------------------------------------------------

const CSS = `
.mmp { display: flex; flex-direction: column; height: 100%; min-height: 0; color: var(--text); font-family: var(--sans); background: var(--bg); position: relative; outline: none; }
.mmp-head { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; padding: 10px 14px 8px; border-bottom: 1px solid var(--border-soft, var(--border)); }
.mmp-heading { display: flex; align-items: center; gap: 8px; min-width: 0; }
.mmp-title { font-size: 13px; font-weight: 650; display: flex; align-items: center; gap: 6px; white-space: nowrap; }
.mmp-counts { font-size: 11px; color: var(--text-dim); font-family: var(--mono, monospace); white-space: nowrap; }
.mmp-sub { flex: 1 1 100%; order: 3; font-size: 11px; color: var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mmp-actions { margin-left: auto; display: flex; flex-wrap: nowrap; align-items: center; gap: 6px; overflow-x: auto; padding-bottom: 1px; }
.mmp-btn { display: inline-flex; align-items: center; gap: 5px; padding: 4px 9px; font: inherit; font-size: 11.5px; line-height: 1.4; border-radius: 6px; border: 1px solid var(--border); background: var(--bg-elev, var(--bg-elev2, transparent)); color: var(--text-dim); cursor: pointer; white-space: nowrap; }
.mmp-btn:hover { color: var(--text); border-color: var(--text-faint, var(--border)); }
.mmp-btn.primary { background: var(--accent); border-color: transparent; color: #fff; }
.mmp-btn.primary:hover { color: #fff; filter: brightness(1.08); }
.mmp-btn:disabled { opacity: .45; cursor: default; }
.mmp-btn.danger-armed { color: #fff; background: var(--red, #ef4444); border-color: transparent; }
.mmp-body { flex: 1 1 auto; min-height: 0; display: flex; }
.mmp-canvas { position: relative; flex: 1 1 auto; min-width: 0; overflow: hidden; cursor: grab; background: radial-gradient(circle at 1px 1px, color-mix(in srgb, var(--border) 60%, transparent) 1px, transparent 0) 0 0 / 22px 22px; touch-action: none; }
.mmp-canvas.panning { cursor: grabbing; }
.mmp-world { position: absolute; left: 0; top: 0; width: 0; height: 0; transform-origin: 0 0; }
.mmp-svg { position: absolute; left: 0; top: 0; width: 1px; height: 1px; overflow: visible; pointer-events: none; z-index: 0; }
.mmp-svg .hit { pointer-events: stroke; stroke: transparent; stroke-width: 16; fill: none; cursor: pointer; }
.mmp-svg .wire { fill: none; stroke: var(--text-faint, #6b7280); stroke-width: 1.6; }
.mmp-svg .wire.sel { stroke: var(--accent); stroke-width: 2.6; }
.mmp-svg .temp { fill: none; stroke: var(--accent); stroke-width: 2; stroke-dasharray: 5 4; }
.mmp-node { position: absolute; z-index: 1; display: flex; flex-direction: column; gap: 5px; padding: 7px 9px 8px; box-sizing: border-box; border-radius: 10px; background: var(--bg); border: 1px solid var(--border); box-shadow: 0 6px 16px rgba(0,0,0,.16); pointer-events: auto; }
.mmp-node.sel { box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 32%, transparent), 0 8px 20px rgba(0,0,0,.22); }
.mmp-node-head { display: flex; align-items: center; gap: 6px; flex-shrink: 0; cursor: grab; }
.mmp-kind { padding: 1px 6px; font-size: 10px; font-weight: 600; line-height: 1.5; border-radius: 5px; cursor: pointer; background: transparent; }
.mmp-nid { margin-left: auto; font-size: 10px; color: var(--text-dim); font-family: var(--mono, monospace); }
.mmp-x { width: 16px; height: 16px; padding: 0; display: flex; align-items: center; justify-content: center; border: 0; background: none; color: var(--text-dim); cursor: pointer; font-size: 13px; line-height: 1; }
.mmp-x:hover { color: var(--red, #ef4444); }
.mmp-title-in, .mmp-detail-in, .mmp-caption-in { width: 100%; box-sizing: border-box; border: 0; outline: none; background: transparent; font: inherit; }
.mmp-title-in { color: var(--text); font-size: 12.5px; font-weight: 600; padding: 0; }
.mmp-detail-in { flex: 1 1 auto; min-height: 0; resize: none; color: var(--text-dim); font-size: 11px; line-height: 1.35; padding: 0; }
.mmp-caption-in { color: var(--text-dim); font-size: 10.5px; padding: 0; }
.mmp-port { position: absolute; right: -9px; top: 50%; width: 18px; height: 18px; margin-top: -9px; border-radius: 50%; border: 2px solid var(--accent); background: color-mix(in srgb, var(--bg) 78%, transparent); cursor: crosshair; padding: 0; transition: transform .12s, background .12s; }
.mmp-port::after { content: ""; position: absolute; inset: 4px; border-radius: 50%; background: var(--accent); opacity: .55; }
.mmp-port:hover, .mmp-node:hover .mmp-port { background: var(--accent); transform: scale(1.12); }
.mmp-port:hover::after, .mmp-node:hover .mmp-port::after { opacity: 1; background: var(--bg); }
.mmp-kbd { margin-left: auto; padding: 0 4px; font-size: 9px; line-height: 1.5; border-radius: 4px; border: 1px solid var(--border); color: var(--text-dim); font-family: var(--mono, monospace); }
.mmp-imgbox { position: relative; flex: 1 1 auto; min-height: 0; border-radius: 6px; overflow: hidden; background: color-mix(in srgb, var(--border) 26%, transparent); }
.mmp-imgbox img { width: 100%; height: 100%; object-fit: contain; display: block; cursor: pointer; }
.mmp-imgpick { width: 100%; height: 100%; border: 0; background: none; color: var(--text-dim); font: inherit; font-size: 11px; cursor: pointer; }
.mmp-preview { flex: 0 0 auto; width: min(420px, 38%); border-left: 1px solid var(--border-soft, var(--border)); display: flex; flex-direction: column; min-height: 0; }
.mmp-preview[hidden] { display: none; }
.mmp-preview-head { padding: 8px 12px; font-size: 11px; color: var(--text-dim); border-bottom: 1px solid var(--border-soft, var(--border)); }
.mmp-preview pre { flex: 1 1 auto; min-height: 0; overflow: auto; margin: 0; padding: 10px 12px; font-family: var(--mono, monospace); font-size: 11.5px; line-height: 1.55; white-space: pre-wrap; word-break: break-word; color: var(--text); }
.mmp-empty { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; padding: 24px; text-align: center; color: var(--text-dim); font-size: 12px; pointer-events: none; }
.mmp-help { padding: 6px 14px 8px; font-size: 10.5px; color: var(--text-faint, var(--text-dim)); border-top: 1px solid var(--border-soft, var(--border)); }
.mmp-toast { position: absolute; left: 50%; bottom: 46px; transform: translateX(-50%); max-width: 80%; padding: 6px 12px; border-radius: 999px; background: var(--bg-elev2, #222); border: 1px solid var(--border); color: var(--text); font-size: 11.5px; box-shadow: 0 6px 20px rgba(0,0,0,.28); opacity: 0; transition: opacity .16s; pointer-events: none; }
.mmp-toast.show { opacity: 1; }
.mmp-modal { position: absolute; inset: 0; background: rgba(0,0,0,.42); display: flex; align-items: center; justify-content: center; padding: 20px; z-index: 5; }
.mmp-modal[hidden] { display: none; }
.mmp-dialog { width: min(560px, 100%); max-height: 100%; display: flex; flex-direction: column; gap: 10px; padding: 16px; border-radius: 12px; background: var(--bg-elev2, var(--bg)); border: 1px solid var(--border); box-shadow: 0 18px 48px rgba(0,0,0,.45); }
.mmp-dialog h3 { margin: 0; font-size: 13.5px; }
.mmp-dialog p { margin: 0; font-size: 11.5px; color: var(--text-dim); line-height: 1.5; }
.mmp-dialog textarea { width: 100%; box-sizing: border-box; min-height: 132px; resize: vertical; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--border); background: var(--bg); color: var(--text); font-family: var(--mono, monospace); font-size: 11.5px; line-height: 1.5; }
.mmp-dialog .row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.mmp-check { display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--text-dim); }
.mmp-check[hidden] { display: none; }
.mmp-status { flex: 1 1 140px; min-width: 0; font-size: 11px; color: var(--text-dim); overflow-wrap: anywhere; }
.mmp-status.running { color: var(--accent); }
.mmp-status.error { color: var(--red, #ef4444); }
.mmp-status.warn { color: var(--amber, #f59e0b); }
.mmp-raw { font-size: 11px; color: var(--text-dim); }
.mmp-raw[hidden] { display: none; }
.mmp-raw pre { max-height: 160px; overflow: auto; margin: 6px 0 0; padding: 8px; border-radius: 8px; background: var(--code-bg, rgba(0,0,0,.2)); border: 1px solid var(--border); white-space: pre-wrap; word-break: break-word; font-family: var(--mono, monospace); font-size: 11px; color: var(--text); }
.mmp-dialog .row .grow { flex: 1 1 auto; font-size: 11px; color: var(--text-dim); }
.mmp-kindmenu { position: fixed; z-index: 10001; display: flex; flex-direction: column; gap: 2px; padding: 6px; border-radius: 10px; background: var(--bg-elev2, #1b1b22); border: 1px solid var(--border); box-shadow: 0 12px 32px rgba(0,0,0,.4); min-width: 132px; }
.mmp-kindmenu .label { font-size: 10px; color: var(--text-dim); padding: 2px 6px 4px; }
.mmp-kindmenu button { display: flex; align-items: center; gap: 7px; min-width: 128px; padding: 5px 8px; border: 0; border-radius: 6px; background: none; color: var(--text); font: inherit; font-size: 12px; cursor: pointer; text-align: left; }
.mmp-kindmenu button:hover { background: var(--row-active, color-mix(in srgb, var(--accent) 18%, transparent)); }
.mmp-kindmenu .dot { width: 8px; height: 8px; border-radius: 50%; flex: 0 0 auto; }
.mmp-overlay { position: fixed; inset: 0; z-index: 9000; background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center; padding: 3vh 3vw; }
.mmp-overlay-frame { width: 100%; height: 100%; max-width: 1400px; display: flex; flex-direction: column; border-radius: 14px; overflow: hidden; background: var(--bg); border: 1px solid var(--border); box-shadow: 0 24px 64px rgba(0,0,0,.5); }
.mmp-fab { display: inline-flex; align-items: center; gap: 4px; order: -1; margin-right: 2px; padding: 3px 8px; border-radius: 999px; border: 1px solid var(--border); background: transparent; color: var(--text-dim); font: inherit; font-size: 11px; cursor: pointer; white-space: nowrap; }
.mmp-fab:hover { color: var(--text); border-color: var(--accent); background: var(--accent-soft, color-mix(in srgb, var(--accent) 14%, transparent)); }
.mmp-fab.floating { position: fixed; order: 0; z-index: 60; box-shadow: 0 6px 18px rgba(0,0,0,.3); background: var(--bg-elev2, #1b1b22); }
`;

let styleInjected = false;
function injectStyle() {
	if (styleInjected) return;
	const tag = document.createElement("style");
	tag.dataset.piMindmap = "1";
	tag.textContent = CSS;
	document.head.appendChild(tag);
	styleInjected = true;
}

// 模块被 import 就用得上样式（输入框按钮、浮层）
injectStyle();

// ---------------------------------------------------------------------------
// 编辑器（tab 视图 / 浮层 各一份实例，共享 store）
// ---------------------------------------------------------------------------

function el(tag, className, text) {
	const node = document.createElement(tag);
	if (className) node.className = className;
	if (text !== undefined) node.textContent = text;
	return node;
}

function svgEl(tag, attrs) {
	const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
	for (const [key, value] of Object.entries(attrs ?? {})) node.setAttribute(key, String(value));
	return node;
}

function createEditor(host, opts = {}) {
	const overlay = Boolean(opts.overlay);
	const root = el("div", "mmp");
	root.tabIndex = -1;
	root.innerHTML = "";

	let view = { x: 40, y: 40, scale: 1 };
	let selected = null; // {type:'node'|'edge', id}
	let previewOpen = false;
	let clearArmed = false;
	let clearTimer = null;
	let dragState = null;
	let toastTimer = null;
	let kindMenuEl = null;
	let kindMenuOff = null;
	let imageTargetId = null; // 文件选择器是为哪个节点打开的（null = 新建）
	let destroying = false;
	const offs = [];

	// ---- 骨架 ----
	const head = el("div", "mmp-head");
	const heading = el("div", "mmp-heading");
	const titleRow = el("div", "mmp-title");
	titleRow.append(el("span", "", "🧠"), el("span", "", S.title));
	const counts = el("span", "mmp-counts");
	titleRow.append(counts);
	heading.append(titleRow);
	const sub = el("div", "mmp-sub", S.subtitle);
	const actions = el("div", "mmp-actions");
	head.append(heading, sub, actions);

	const btn = (label, act, className = "mmp-btn") => {
		const b = el("button", className, label);
		b.type = "button";
		b.dataset.act = act;
		return b;
	};
	const bAdd = btn(`＋ ${S.addNode}`, "add");
	const bLayout = btn(`⇲ ${S.autoLayout}`, "layout");
	const bImage = btn(`🖼 ${S.addImage}`, "image");
	const bImport = btn(`⠿ ${S.import}`, "import");
	const bPrompt = btn(`✨ ${S.prompt}`, "prompt");
	const bCopy = btn(`⧉ ${S.copy}`, "copy");
	const bPreview = btn(`◫ ${S.preview}`, "preview");
	const bInsert = btn(`↵ ${S.insert}`, "insert", "mmp-btn primary");
	const bClear = btn(`␡ ${S.clear}`, "clear");
	actions.append(bAdd, bLayout, bImage, bImport, bPrompt, bCopy, bPreview, bInsert, bClear);
	if (overlay && typeof opts.onClose === "function") actions.append(btn("✕", "close"));

	const body = el("div", "mmp-body");
	const canvas = el("div", "mmp-canvas");
	const world = el("div", "mmp-world");
	const svg = svgEl("svg", { class: "mmp-svg" });
	const defs = svgEl("defs");
	const marker = svgEl("marker", {
		id: "mmp-arrow",
		viewBox: "0 0 10 10",
		refX: 9,
		refY: 5,
		markerWidth: 5,
		markerHeight: 5,
		orient: "auto-start-reverse",
	});
	marker.append(svgEl("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "var(--text-faint, #6b7280)" }));
	defs.append(marker);
	svg.append(defs);
	const empty = el("div", "mmp-empty", S.emptyGraph);
	world.append(svg);
	canvas.append(world, empty);

	const preview = el("aside", "mmp-preview");
	preview.hidden = true;
	const previewHead = el("div", "mmp-preview-head", S.preview);
	const pre = el("pre");
	preview.append(previewHead, pre);

	body.append(canvas, preview);
	const help = el("div", "mmp-help", S.help);
	const toast = el("div", "mmp-toast");
	root.append(head, body, help, toast);
	host.append(root);

	const fileInput = el("input");
	fileInput.type = "file";
	fileInput.accept = "image/*";
	fileInput.style.display = "none";
	root.append(fileInput);

	const showToast = (message) => {
		toast.textContent = message;
		toast.classList.add("show");
		if (toastTimer !== null) window.clearTimeout(toastTimer);
		toastTimer = window.setTimeout(() => {
			toastTimer = null;
			toast.classList.remove("show");
		}, 2200);
	};

	// ---- 视图辅助 ----
	const canvasPoint = (clientX, clientY) => {
		const rect = canvas.getBoundingClientRect();
		return {
			x: (clientX - rect.left - view.x) / view.scale,
			y: (clientY - rect.top - view.y) / view.scale,
		};
	};
	const viewCenter = () => {
		const rect = canvas.getBoundingClientRect();
		return {
			x: (rect.width / 2 - view.x) / view.scale - NODE_W / 2,
			y: (rect.height / 2 - view.y) / view.scale - NODE_H / 2,
		};
	};
	const freeSpot = (base) => {
		const graph = store.get();
		const taken = (candidate) =>
			graph.nodes.some((n) => Math.abs(n.x - candidate.x) < NODE_W * 0.7 && Math.abs(n.y - candidate.y) < NODE_H * 0.7);
		let spot = base;
		for (let i = 0; i < 40 && taken(spot); i += 1) spot = { x: spot.x + 30, y: spot.y + 30 };
		return spot;
	};
	const applyView = () => {
		world.style.transform = `translate(${view.x}px, ${view.y}px) scale(${view.scale})`;
	};

	// ---- 渲染 ----
	function renderCounts() {
		const graph = store.get();
		counts.textContent = `${format(S.nodes, { count: graph.nodes.length })} · ${format(S.edges, { count: graph.edges.length })}`;
	}

	function renderEdges() {
		const graph = store.get();
		const byId = new Map(graph.nodes.map((n) => [n.id, n]));
		for (const node of [...svg.querySelectorAll(".hit, .wire, .temp, .elabel")]) node.remove();

		for (const edge of graph.edges) {
			const from = byId.get(edge.from);
			const to = byId.get(edge.to);
			if (!from || !to) continue;
			const path = edgePath(from, to);
			const hit = svgEl("path", { class: "hit", d: path });
			hit.dataset.edge = edge.id;
			hit.addEventListener("pointerdown", (event) => {
				event.stopPropagation();
				selected = { type: "edge", id: edge.id };
				renderNodes();
				renderEdges();
			});
			const wire = svgEl("path", {
				class: `wire${selected && selected.type === "edge" && selected.id === edge.id ? " sel" : ""}`,
				d: path,
				"marker-end": "url(#mmp-arrow)",
			});
			svg.append(hit, wire);
			if (edge.label) {
				const mid = pathMid(from, to);
				const label = svgEl("text", { class: "elabel", x: mid.x, y: mid.y, "font-size": 10, fill: "var(--text-dim)", "text-anchor": "middle" });
				label.textContent = edge.label;
				svg.append(label);
			}
		}
	}

	function renderNodes() {
		const graph = store.get();
		const existing = new Map([...world.querySelectorAll(".mmp-node")].map((n) => [n.dataset.id, n]));
		const seen = new Set();

		for (const node of graph.nodes) {
			seen.add(node.id);
			let card = existing.get(node.id);
			const isNew = !card;
			if (isNew) {
				card = el("div", "mmp-node");
				card.dataset.id = node.id;
				card.style.width = `${NODE_W}px`;
				card.style.height = `${NODE_H}px`;
				world.append(card);
				bindCard(card, node);
			}
			card.classList.toggle("sel", Boolean(selected && selected.type === "node" && selected.id === node.id));
			card.style.left = `${node.x}px`;
			card.style.top = `${node.y}px`;
			card.style.borderTop = `3px solid ${KIND_COLORS[node.kind] ?? "var(--border)"}`;
			if (isNew) buildCardContent(card, node);
			refreshCardContent(card, node);
		}
		for (const [id, card] of existing) if (!seen.has(id)) card.remove();
		empty.style.display = graph.nodes.length === 0 ? "flex" : "none";
		renderCounts();
	}

	function buildCardContent(card, node) {
		card.innerHTML = "";
		const color = KIND_COLORS[node.kind] ?? "var(--border)";

		const headRow = el("div", "mmp-node-head");
		const kindBtn = el("button", "mmp-kind", S.kinds[node.kind] ?? node.kind);
		kindBtn.type = "button";
		kindBtn.title = S.cycleKind;
		kindBtn.style.color = color;
		kindBtn.style.border = `1px solid color-mix(in srgb, ${color} 55%, transparent)`;
		kindBtn.style.background = `color-mix(in srgb, ${color} 16%, transparent)`;
		kindBtn.addEventListener("pointerdown", (event) => event.stopPropagation());
		kindBtn.addEventListener("click", (event) => {
			event.stopPropagation();
			cycleKind(node.id);
		});
		const idText = el("span", "mmp-nid", node.id);
		const del = el("button", "mmp-x", "×");
		del.type = "button";
		del.title = S.deleteNode;
		del.addEventListener("pointerdown", (event) => event.stopPropagation());
		del.addEventListener("click", (event) => {
			event.stopPropagation();
			deleteNode(node.id);
		});
		headRow.append(kindBtn, idText, del);
		headRow.dataset.role = "head";
		card.append(headRow);

		if (node.kind === "image") {
			const box = el("div", "mmp-imgbox");
			card.append(box);
			const caption = el("input", "mmp-caption-in");
			caption.placeholder = S.imageCaption;
			caption.addEventListener("pointerdown", (event) => event.stopPropagation());
			caption.addEventListener("input", () => patchNode(node.id, { title: caption.value }));
			card.append(caption);
		} else {
			const titleIn = el("input", "mmp-title-in");
			titleIn.placeholder = S.nodeTitle;
			titleIn.addEventListener("pointerdown", (event) => event.stopPropagation());
			titleIn.addEventListener("input", () => patchNode(node.id, { title: titleIn.value }));
			titleIn.addEventListener("focus", () => select("node", node.id, { rebuild: false }));
			const detailIn = el("textarea", "mmp-detail-in");
			detailIn.placeholder = S.nodeDetail;
			detailIn.rows = 2;
			detailIn.addEventListener("pointerdown", (event) => event.stopPropagation());
			detailIn.addEventListener("input", () => patchNode(node.id, { detail: detailIn.value }));
			card.append(titleIn, detailIn);
		}

		const port = el("button", "mmp-port");
		port.type = "button";
		port.title = S.port;
		port.addEventListener("pointerdown", (event) => startLink(event, node.id));
		card.append(port);
	}

	function refreshCardContent(card, node) {
		const color = KIND_COLORS[node.kind] ?? "var(--border)";
		const kindBtn = card.querySelector(".mmp-kind");
		if (kindBtn) {
			kindBtn.textContent = S.kinds[node.kind] ?? node.kind;
			kindBtn.style.color = color;
			kindBtn.style.border = `1px solid color-mix(in srgb, ${color} 55%, transparent)`;
			kindBtn.style.background = `color-mix(in srgb, ${color} 16%, transparent)`;
		}
		const titleIn = card.querySelector(".mmp-title-in");
		const caption = card.querySelector(".mmp-caption-in");
		if (titleIn && document.activeElement !== titleIn) titleIn.value = node.title;
		if (caption && document.activeElement !== caption) caption.value = node.title;
		const detailIn = card.querySelector(".mmp-detail-in");
		if (detailIn && document.activeElement !== detailIn) detailIn.value = node.detail;
		const box = card.querySelector(".mmp-imgbox");
		if (box) {
			box.innerHTML = "";
			if (node.image) {
				const img = el("img");
				img.src = node.image;
				img.alt = node.title || node.imageName || "";
				img.title = S.imageReplace;
				img.addEventListener("pointerdown", (event) => event.stopPropagation());
				img.addEventListener("click", () => pickImageFor(node.id));
				box.append(img);
			} else {
				const pick = el("button", "mmp-imgpick", S.imagePick);
				pick.type = "button";
				pick.addEventListener("pointerdown", (event) => event.stopPropagation());
				pick.addEventListener("click", () => pickImageFor(node.id));
				box.append(pick);
			}
		}
	}

	function renderAll() {
		applyView();
		renderNodes();
		renderEdges();
		refreshPreview();
		refreshButtons();
	}

	function refreshPreview() {
		if (!previewOpen) return;
		const text = serializedText();
		pre.textContent = text || S.previewEmpty;
	}

	function refreshButtons() {
		const text = serializedText();
		bInsert.disabled = !text;
		bCopy.disabled = !text;
		bPreview.textContent = previewOpen ? `◫ ${S.previewHide}` : `◫ ${S.preview}`;
		bClear.textContent = clearArmed ? `⚠ ${S.clearConfirm}` : `␡ ${S.clear}`;
		bClear.classList.toggle("danger-armed", clearArmed);
	}

	// ---- 图操作 ----
	const commit = (next, opts2 = {}) => store.set(next, opts2);
	/** 结构性改动（增删节点/连线/换类型/整图替换）：需要重画卡片 */
	const commitStructural = (next) => store.set(next, { source: root, rebuild: true });

	function patchNode(id, patch, opts2 = { rebuild: false }) {
		const graph = store.get();
		commit(
			{ nodes: graph.nodes.map((n) => (n.id === id ? { ...n, ...patch } : n)), edges: graph.edges },
			{ source: root, ...opts2 },
		);
	}

	function deleteNode(id) {
		commitStructural(dropNodePositions(store.get(), id));
		if (selected && selected.id === id) selected = null;
	}

	function cycleKind(id) {
		const graph = store.get();
		const node = graph.nodes.find((n) => n.id === id);
		if (!node) return;
		const index = MINDMAP_KINDS.indexOf(node.kind);
		const nextKind = MINDMAP_KINDS[(index + 1) % MINDMAP_KINDS.length];
		const needsImage = nextKind === "image" && !node.image;
		const next = { ...node, kind: nextKind };
		if (nextKind !== "image") {
			delete next.image;
			delete next.imageName;
		}
		commitStructural({ nodes: graph.nodes.map((n) => (n.id === id ? next : n)), edges: graph.edges });
		if (needsImage) pickImageFor(id);
	}

	function addNode(kind = "idea", position = null) {
		const graph = store.get();
		const spot = freeSpot(position ?? (() => {
			const center = viewCenter();
			const offset = (graph.nodes.length % 3) * 28;
			return { x: center.x + offset, y: center.y + offset };
		})());
		const id = nextNodeId(graph);
		const node = createMindMapNode(kind, spot.x, spot.y, id, "");
		commitStructural({ nodes: [...graph.nodes, node], edges: graph.edges });
		select("node", id, { rebuild: false });
		const card = world.querySelector(`.mmp-node[data-id="${id}"]`);
		const titleIn = card?.querySelector(".mmp-title-in");
		if (titleIn) titleIn.focus();
		return id;
	}

	function select(type, id, opts2 = {}) {
		selected = { type, id };
		if (opts2.rebuild === false) {
			for (const card of world.querySelectorAll(".mmp-node")) card.classList.toggle("sel", type === "node" && card.dataset.id === id);
			renderEdges();
		} else {
			renderNodes();
			renderEdges();
		}
	}

	// ---- 连线 ----
	function edgePath(from, to) {
		const sx = from.x + NODE_W;
		const sy = from.y + NODE_H / 2;
		const tx = to.x;
		const ty = to.y + NODE_H / 2;
		const bend = Math.max(50, Math.abs(tx - sx) * 0.45);
		return `M ${sx} ${sy} C ${sx + bend} ${sy}, ${tx - bend} ${ty}, ${tx} ${ty}`;
	}

	function pathMid(from, to) {
		return {
			x: (from.x + NODE_W + to.x) / 2,
			y: (from.y + to.y) / 2 + NODE_H / 2,
		};
	}

	function startLink(event, fromId) {
		event.preventDefault();
		event.stopPropagation();
		const graph = store.get();
		const from = graph.nodes.find((n) => n.id === fromId);
		if (!from) return;
		const sx = from.x + NODE_W;
		const sy = from.y + NODE_H / 2;
		const temp = svgEl("path", { class: "temp", d: `M ${sx} ${sy} L ${sx} ${sy}` });
		svg.append(temp);

		const move = (moveEvent) => {
			const point = canvasPoint(moveEvent.clientX, moveEvent.clientY);
			const bend = Math.max(40, Math.abs(point.x - sx) * 0.45);
			temp.setAttribute("d", `M ${sx} ${sy} C ${sx + bend} ${sy}, ${point.x - bend} ${point.y}, ${point.x} ${point.y}`);
		};

		const up = (upEvent) => {
			window.removeEventListener("pointermove", move, true);
			window.removeEventListener("pointerup", up, true);
			temp.remove();
			const targetEl = document.elementFromPoint(upEvent.clientX, upEvent.clientY)?.closest?.("[data-id]");
			const targetId = targetEl?.dataset?.id ?? null;
			if (targetId && targetId !== fromId) {
				const current = store.get();
				const next = connectMindMapNodes(current, fromId, targetId, `e${fromId}-${targetId}`);
				if (next !== current) commitStructural(next);
				return;
			}
			// 拖到空白处：弹类型菜单，选中即新建并连上
			const point = canvasPoint(upEvent.clientX, upEvent.clientY);
			openKindMenu(upEvent.clientX, upEvent.clientY, (kind) => {
				const current = store.get();
				const id = nextNodeId(current);
				const node = createMindMapNode(kind, point.x, point.y, id, "");
				const withNode = { nodes: [...current.nodes, node], edges: current.edges };
				const withEdge = connectMindMapNodes(withNode, fromId, id, `e${fromId}-${id}`);
				commitStructural(withEdge);
				select("node", id, { rebuild: false });
				if (kind === "image") pickImageFor(id);
			});
		};

		window.addEventListener("pointermove", move, true);
		window.addEventListener("pointerup", up, true);
	}

	function openKindMenu(clientX, clientY, onPick) {
		closeKindMenu();
		const menu = el("div", "mmp-kindmenu");
		menu.append(el("div", "label", S.pickKind));
		MINDMAP_KINDS.forEach((kind, index) => {
			const item = el("button");
			item.type = "button";
			item.dataset.kind = kind;
			const dot = el("span", "dot");
			dot.style.background = KIND_COLORS[kind];
			item.append(dot, el("span", "", S.kinds[kind]), el("kbd", "mmp-kbd", String(index + 1)));
			item.addEventListener("click", () => {
				closeKindMenu();
				onPick(kind);
			});
			menu.append(item);
		});
		document.body.append(menu);
		const rect = menu.getBoundingClientRect();
		menu.style.left = `${Math.max(8, Math.min(clientX, window.innerWidth - rect.width - 8))}px`;
		menu.style.top = `${Math.max(8, Math.min(clientY, window.innerHeight - rect.height - 8))}px`;
		kindMenuEl = menu;

		// 点外面关掉；1-7 直接选；Esc 取消。注意：只对「当前这个菜单」生效——
		// 之前每次开菜单都挂一个闭包在 window 上，旧闭包会把新菜单一起关掉（真实鼠标
		// 事件下表现为「菜单弹出来但点不动」）。
		const onDown = (event) => {
			if (kindMenuEl !== menu) return;
			if (!menu.contains(event.target)) closeKindMenu();
		};
		const onKey = (event) => {
			if (kindMenuEl !== menu) return;
			if (event.key === "Escape") {
				event.stopPropagation();
				event.preventDefault();
				closeKindMenu();
				return;
			}
			const n = Number(event.key);
			if (Number.isInteger(n) && n >= 1 && n <= MINDMAP_KINDS.length) {
				event.stopPropagation();
				event.preventDefault();
				closeKindMenu();
				onPick(MINDMAP_KINDS[n - 1]);
			}
		};
		window.addEventListener("pointerdown", onDown, true);
		window.addEventListener("keydown", onKey, true);
		kindMenuOff = () => {
			window.removeEventListener("pointerdown", onDown, true);
			window.removeEventListener("keydown", onKey, true);
		};
	}

	function closeKindMenu() {
		if (kindMenuOff) {
			kindMenuOff();
			kindMenuOff = null;
		}
		if (kindMenuEl) {
			kindMenuEl.remove();
			kindMenuEl = null;
		}
	}

	/** 把画布坐标夹进可视区，保证新建的节点不会落到视野外。 */
	function clampToView(point) {
		const rect = canvas.getBoundingClientRect();
		const minX = (8 - view.x) / view.scale;
		const minY = (8 - view.y) / view.scale;
		const maxX = Math.max(minX, (rect.width - 8 - view.x) / view.scale - NODE_W);
		const maxY = Math.max(minY, (rect.height - 8 - view.y) / view.scale - NODE_H);
		return {
			x: Math.min(Math.max(point.x, minX), maxX),
			y: Math.min(Math.max(point.y, minY), maxY),
		};
	}

	// ---- 卡片拖动 ----
	function bindCard(card, node) {
		card.addEventListener("pointerdown", (event) => {
			if (event.button !== 0) return;
			if (event.target.closest("input, textarea, .mmp-x, .mmp-kind, .mmp-port, img, button")) return;
			event.stopPropagation();
			select("node", node.id, { rebuild: false });
			const startX = event.clientX;
			const startY = event.clientY;
			const originX = node.x;
			const originY = node.y;
			const move = (moveEvent) => {
				const nextX = Math.round(originX + (moveEvent.clientX - startX) / view.scale);
				const nextY = Math.round(originY + (moveEvent.clientY - startY) / view.scale);
				card.style.left = `${nextX}px`;
				card.style.top = `${nextY}px`;
				patchNode(node.id, { x: nextX, y: nextY });
			};
			const up = () => {
				window.removeEventListener("pointermove", move, true);
				window.removeEventListener("pointerup", up, true);
			};
			window.addEventListener("pointermove", move, true);
			window.addEventListener("pointerup", up, true);
		});
	}

	// ---- 画布：平移 / 缩放 / 双击新建 / 拖入图片 ----
	canvas.addEventListener("pointerdown", (event) => {
		if (event.button !== 0) return;
		closeKindMenu();
		const startX = event.clientX;
		const startY = event.clientY;
		const originX = view.x;
		const originY = view.y;
		let moved = false;
		canvas.classList.add("panning");
		const move = (moveEvent) => {
			const dx = moveEvent.clientX - startX;
			const dy = moveEvent.clientY - startY;
			if (!moved && Math.abs(dx) + Math.abs(dy) > 3) moved = true;
			if (!moved) return;
			view = { ...view, x: originX + dx, y: originY + dy };
			applyView();
		};
		const up = () => {
			window.removeEventListener("pointermove", move, true);
			window.removeEventListener("pointerup", up, true);
			canvas.classList.remove("panning");
			if (!moved) {
				selected = null;
				renderNodes();
				renderEdges();
			}
		};
		window.addEventListener("pointermove", move, true);
		window.addEventListener("pointerup", up, true);
	});

	canvas.addEventListener("dblclick", (event) => {
		if (event.target.closest(".mmp-node")) return;
		const point = canvasPoint(event.clientX, event.clientY);
		addNode("idea", { x: point.x - NODE_W / 2, y: point.y - NODE_H / 2 });
	});

	// 右键空白：直接挑类型再落节点（和拉线到空白同一套菜单）
	canvas.addEventListener("contextmenu", (event) => {
		if (event.target.closest(".mmp-node")) return;
		event.preventDefault();
		const point = clampToView({
			x: canvasPoint(event.clientX, event.clientY).x - NODE_W / 2,
			y: canvasPoint(event.clientX, event.clientY).y - NODE_H / 2,
		});
		openKindMenu(event.clientX, event.clientY, (kind) => {
			const id = addNode(kind, { x: point.x, y: point.y });
			if (kind === "image" && id) pickImageFor(id);
		});
	});

	canvas.addEventListener(
		"wheel",
		(event) => {
			event.preventDefault();
			const rect = canvas.getBoundingClientRect();
			const px = event.clientX - rect.left;
			const py = event.clientY - rect.top;
			const factor = event.deltaY < 0 ? 1.1 : 1 / 1.1;
			const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, view.scale * factor));
			const ratio = scale / view.scale;
			view = { scale, x: px - (px - view.x) * ratio, y: py - (py - view.y) * ratio };
			applyView();
		},
		{ passive: false },
	);

	canvas.addEventListener("dragover", (event) => {
		if (!event.dataTransfer?.types?.includes("Files")) return;
		event.preventDefault();
	});
	canvas.addEventListener("drop", (event) => {
		const files = [...(event.dataTransfer?.files ?? [])].filter((f) => f.type.startsWith("image/"));
		if (files.length === 0) return;
		event.preventDefault();
		const point = canvasPoint(event.clientX, event.clientY);
		void (async () => {
			const graph = store.get();
			const id = nextNodeId(graph);
			const node = createMindMapNode("image", point.x - NODE_W / 2, point.y - NODE_H / 2, id, "");
			commitStructural({ nodes: [...graph.nodes, node], edges: graph.edges });
			await attachImage(id, files[0]);
			showToast(S.imageDropped);
		})();
	});

	// ---- 图片 ----
	function pickImageFor(nodeId) {
		imageTargetId = nodeId;
		fileInput.click();
	}
	fileInput.addEventListener("change", () => {
		const file = fileInput.files?.[0];
		fileInput.value = "";
		if (!file) return;
		const target = imageTargetId;
		imageTargetId = null;
		if (target) void attachImage(target, file);
	});

	async function attachImage(nodeId, file) {
		try {
			const shrunk = await shrinkImage(file);
			patchNode(nodeId, { image: shrunk, imageName: file.name }, { rebuild: true });
		} catch {
			showToast(format(S.imageFailed, { name: file.name }));
		}
	}

	// ---- 工具栏动作 ----
	actions.addEventListener("click", (event) => {
		const target = event.target.closest("button[data-act]");
		if (!target) return;
		const act = target.dataset.act;
		if (act === "add") addNode("idea");
		else if (act === "layout") commitStructural(autoLayoutMindMap(store.get()));
		else if (act === "image") {
			const id = addNode("image");
			if (id) pickImageFor(id);
		} else if (act === "import") openImportModal();
		else if (act === "prompt") openPromptModal();
		else if (act === "copy") {
			void copyText(serializedText()).then((ok) => showToast(ok ? S.copied : S.insertFallback));
		} else if (act === "preview") {
			previewOpen = !previewOpen;
			preview.hidden = !previewOpen;
			refreshPreview();
			refreshButtons();
		} else if (act === "insert") {
			const text = serializedText();
			if (insertIntoComposer(text)) showToast(S.insertDone);
			else void copyText(text).then(() => showToast(S.insertFallback));
		} else if (act === "clear") {
			if (!clearArmed) {
				clearArmed = true;
				refreshButtons();
				if (clearTimer !== null) window.clearTimeout(clearTimer);
				clearTimer = window.setTimeout(() => {
					clearTimer = null;
					clearArmed = false;
					if (!destroying) refreshButtons();
				}, 3000);
				return;
			}
			clearArmed = false;
			if (clearTimer !== null) window.clearTimeout(clearTimer);
			clearTimer = null;
			selected = null;
			commitStructural(emptyMindMap());
			refreshButtons();
		} else if (act === "close") {
			if (typeof opts.onClose === "function") opts.onClose();
		}
	});

	// ---- 弹窗 ----
	function openDialog({ title, hint, placeholder, actionLabel, secondaryLabel, onApply, liveSummary }) {
		const modal = el("div", "mmp-modal");
		const dialog = el("div", "mmp-dialog");
		dialog.append(el("h3", "", title));
		if (hint) dialog.append(el("p", "", hint));
		const area = el("textarea");
		area.placeholder = placeholder ?? "";
		area.value = "";
		dialog.append(area);
		const row = el("div", "row");
		const summary = el("span", "grow", "");
		const cancel = el("button", "mmp-btn", S.cancel);
		cancel.type = "button";
		const apply = el("button", "mmp-btn primary", actionLabel);
		apply.type = "button";
		row.append(summary, cancel, apply);
		if (secondaryLabel) {
			const secondary = el("button", "mmp-btn", secondaryLabel);
			secondary.type = "button";
			secondary.addEventListener("click", () => {
				const value = area.value;
				close();
				onApply(value, "secondary");
			});
			row.insertBefore(secondary, apply);
		}
		dialog.append(row);
		modal.append(dialog);
		root.append(modal);
		area.focus();

		const update = () => {
			if (liveSummary) summary.textContent = liveSummary(area.value);
		};
		area.addEventListener("input", update);
		update();

		const close = () => {
			modal.remove();
			window.removeEventListener("keydown", onKey, true);
		};
		const onKey = (event) => {
			if (event.key === "Escape") {
				event.stopPropagation();
				event.preventDefault();
				close();
			}
		};
		window.addEventListener("keydown", onKey, true);
		cancel.addEventListener("click", close);
		apply.addEventListener("click", () => {
			const value = area.value;
			close();
			onApply(value, "primary");
		});
		modal.addEventListener("pointerdown", (event) => {
			if (event.target === modal) close();
		});
		return { close };
	}

	function openImportModal() {
		const parse = (text) => deserializeMindMap(text, LABELS);
		openDialog({
			title: S.importTitle,
			hint: S.importHint,
			placeholder: S.importPlaceholder,
			actionLabel: S.importApply,
			liveSummary: (text) => {
				if (!text.trim()) return S.importNothing;
				const { graph, warnings } = parse(text);
				if (graph.nodes.length === 0) return S.importEmpty;
				const base = format(S.importSummary, { nodes: graph.nodes.length, edges: graph.edges.length });
				return warnings.length > 0 ? `${base} · ${warnings.length} ?` : base;
			},
			onApply: (text) => {
				if (!text.trim()) return;
				const { graph } = parse(text);
				if (graph.nodes.length === 0) {
					showToast(S.importEmpty);
					return;
				}
				selected = null;
				commitStructural(graph);
				showToast(format(S.importDone, { nodes: graph.nodes.length, edges: graph.edges.length }));
			},
		});
	}

	/** 把一版草稿落进图：接到选中节点，或整图替换。 */
	function applyDraft(draft, { attachTo = null } = {}) {
		if (!draft || draft.nodes.length === 0) return false;
		if (attachTo) {
			const current = store.get();
			const reindexed = reindexMindMap(draft, nextNodeId(current));
			let graph = {
				nodes: [...current.nodes, ...reindexed.nodes],
				edges: [...current.edges, ...reindexed.edges],
			};
			const rootNode = reindexed.nodes.find((n) => !reindexed.edges.some((e) => e.to === n.id));
			if (rootNode) graph = connectMindMapNodes(graph, attachTo, rootNode.id, `e${attachTo}-${rootNode.id}`);
			commitStructural(graph);
		} else {
			selected = null;
			commitStructural(draft);
		}
		return true;
	}

	function openPromptModal() {
		const modal = el("div", "mmp-modal");
		const dialog = el("div", "mmp-dialog");
		dialog.append(el("h3", "", S.promptTitle));
		dialog.append(el("p", "", S.aiHint));

		const area = el("textarea");
		area.placeholder = S.promptPlaceholder;
		dialog.append(area);

		const hasSelection = Boolean(selected && selected.type === "node");
		const attachRow = el("label", "mmp-check");
		const attachBox = el("input");
		attachBox.type = "checkbox";
		attachBox.checked = hasSelection;
		attachRow.append(attachBox, el("span", "", S.attachSelected));
		attachRow.hidden = !hasSelection;
		dialog.append(attachRow);

		const status = el("div", "mmp-status");
		const rawDetails = el("details", "mmp-raw");
		rawDetails.hidden = true;
		const rawPre = el("pre");
		rawDetails.append(el("summary", "", S.aiRawTitle), rawPre);
		dialog.append(status, rawDetails);

		const row = el("div", "row");
		const cancel = el("button", "mmp-btn", S.cancel);
		cancel.type = "button";
		const local = el("button", "mmp-btn", S.localSplit);
		local.type = "button";
		const ai = el("button", "mmp-btn primary", `\u2728 ${S.aiGenerate}`);
		ai.type = "button";
		row.append(el("span", "grow", ""), cancel, local, ai);
		dialog.append(row);

		modal.append(dialog);
		root.append(modal);
		area.focus();

		const close = () => {
			modal.remove();
			window.removeEventListener("keydown", onDialogKey, true);
		};
		const onDialogKey = (event) => {
			if (event.key === "Escape") {
				event.stopPropagation();
				event.preventDefault();
				close();
			}
		};
		window.addEventListener("keydown", onDialogKey, true);
		cancel.addEventListener("click", close);
		modal.addEventListener("pointerdown", (event) => {
			if (event.target === modal) close();
		});

		const setBusy = (busy) => {
			cancel.disabled = busy;
			local.disabled = busy;
			ai.disabled = busy;
			area.readOnly = busy;
			ai.textContent = busy ? `\u23f3 ${S.aiGenerating}` : `\u2728 ${S.aiGenerate}`;
		};
		const setStatus = (text, tone) => {
			status.textContent = text;
			status.className = `mmp-status${tone ? ` ${tone}` : ""}`;
		};

		// 图里有东西且没勾「接到选中节点」= 会整图替换，先说清楚
		const existingNodes = store.get().nodes.length;
		if (existingNodes > 0 && !attachBox.checked) setStatus(format(S.replaceWarning, { count: existingNodes }), "warn");

		local.addEventListener("click", () => {
			const text = area.value.trim();
			if (!text) {
				setStatus(S.promptEmpty, "warn");
				return;
			}
			const draft = promptToMindMap(text);
			if (!applyDraft(draft, { attachTo: attachBox.checked ? selected?.id : null })) {
				setStatus(S.promptEmpty, "warn");
				return;
			}
			close();
			showToast(format(S.promptDone, { count: draft.nodes.length, nodes: draft.nodes.length }));
		});

		ai.addEventListener("click", async () => {
			const text = area.value.trim();
			if (!text) {
				setStatus(S.promptEmpty, "warn");
				return;
			}
			setBusy(true);
			setStatus(S.aiGenerating, "running");
			rawDetails.hidden = true;
			const startedAt = Date.now();
			let data = null;
			try {
				const response = await fetch("/plugins-api/mindmap/generate", {
					method: "POST",
					headers: { "content-type": "application/json" },
					body: JSON.stringify({ prompt: text, lang: S.lang }),
				});
				data = await response.json().catch(() => null);
				if (!response.ok || !data || data.ok !== true) {
					throw new Error(data?.error || `HTTP ${response.status}`);
				}
				const parsed = parseAiGraph(data.raw, LABELS);
				if (parsed.graph.nodes.length === 0) throw new Error(parsed.error || "无法解析 AI 输出");
				if (!applyDraft(parsed.graph, { attachTo: attachBox.checked ? selected?.id : null })) {
					throw new Error("图是空的");
				}
				const seconds = ((Date.now() - startedAt) / 1000).toFixed(1);
				close();
				showToast(`${format(S.aiDone, { count: parsed.graph.nodes.length })} · ${data.model ?? "pi"} · ${seconds}s`);
			} catch (err) {
				setBusy(false);
				setStatus(format(S.aiFailed, { error: err?.message ?? String(err) }), "error");
				if (typeof data?.raw === "string" && data.raw.trim()) {
					rawPre.textContent = data.raw.slice(0, 8000);
					rawDetails.hidden = false;
				}
			}
		});
	}

	// ---- 键盘 ----
	const onKeyDown = (event) => {
		if (!root.contains(document.activeElement) && document.activeElement !== root) return;
		if (event.key === "Escape") {
			if (kindMenuEl) {
				closeKindMenu();
				event.stopPropagation();
				return;
			}
			if (selected) {
				selected = null;
				renderNodes();
				renderEdges();
				event.stopPropagation();
				return;
			}
			if (overlay && typeof opts.onClose === "function") opts.onClose();
			return;
		}
		if (event.key !== "Delete" && event.key !== "Backspace") return;
		const active = document.activeElement;
		if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.isContentEditable)) return;
		if (!selected) return;
		event.preventDefault();
		if (selected.type === "node") {
			deleteNode(selected.id);
		} else {
			const graph = store.get();
			commitStructural({ nodes: graph.nodes, edges: graph.edges.filter((e) => e.id !== selected.id) });
			selected = null;
		}
	};
	window.addEventListener("keydown", onKeyDown, true);
	offs.push(() => window.removeEventListener("keydown", onKeyDown, true));

	// ---- store 订阅 ----
	offs.push(
		store.subscribe((graph, opts2) => {
			if (opts2.source === root && !opts2.rebuild) {
				// 自己发起的增量改动（拖动位置 / 输入标题备注）：DOM 已经就地更新
				renderEdges();
				renderCounts();
				refreshPreview();
				refreshButtons();
				return;
			}
			renderAll();
		}),
	);

	renderAll();

	return {
		root,
		destroy() {
			destroying = true;
			closeKindMenu();
			if (toastTimer !== null) window.clearTimeout(toastTimer);
			if (clearTimer !== null) window.clearTimeout(clearTimer);
			for (const off of offs) {
				try {
					off();
				} catch {
					/* 忽略 */
				}
			}
			root.remove();
		},
	};
}

// ---------------------------------------------------------------------------
// 图片压缩（存 localStorage，大纲里只带文件名）
// ---------------------------------------------------------------------------

function readFileAsDataURL(file) {
	return new Promise((resolve, reject) => {
		const reader = new FileReader();
		reader.onload = () => resolve(String(reader.result));
		reader.onerror = () => reject(reader.error ?? new Error("read failed"));
		reader.readAsDataURL(file);
	});
}

async function shrinkImage(file) {
	const raw = await readFileAsDataURL(file);
	if (file.type === "image/svg+xml" || file.type === "image/gif") return raw;
	const img = await new Promise((resolve, reject) => {
		const image = new Image();
		image.onload = () => resolve(image);
		image.onerror = () => reject(new Error("decode failed"));
		image.src = raw;
	});
	const scale = Math.min(1, MAX_IMAGE_EDGE / Math.max(img.width || 1, img.height || 1));
	const width = Math.max(1, Math.round((img.width || 1) * scale));
	const height = Math.max(1, Math.round((img.height || 1) * scale));
	const canvas = document.createElement("canvas");
	canvas.width = width;
	canvas.height = height;
	const ctx = canvas.getContext("2d");
	if (!ctx) return raw;
	ctx.drawImage(img, 0, 0, width, height);
	let out = canvas.toDataURL("image/jpeg", 0.72);
	if (out.length > MAX_IMAGE_CHARS) out = canvas.toDataURL("image/jpeg", 0.5);
	return out;
}

// ---------------------------------------------------------------------------
// 输入框控制条上的「脑图」按钮 + 全屏浮层
// ---------------------------------------------------------------------------

let overlayHandle = null;

function openOverlay() {
	if (overlayHandle) return;
	injectStyle();
	const mask = el("div", "mmp-overlay");
	const frame = el("div", "mmp-overlay-frame");
	mask.append(frame);
	document.body.append(mask);
	const editor = createEditor(frame, {
		overlay: true,
		onClose: () => closeOverlay(),
	});
	const onKey = (event) => {
		if (event.key === "Escape" && !frame.querySelector(".mmp-modal")) {
			event.stopPropagation();
			closeOverlay();
		}
	};
	window.addEventListener("keydown", onKey, true);
	mask.addEventListener("pointerdown", (event) => {
		if (event.target === mask) closeOverlay();
	});
	overlayHandle = {
		close() {
			window.removeEventListener("keydown", onKey, true);
			editor.destroy();
			mask.remove();
		},
	};
}

function closeOverlay() {
	if (!overlayHandle) return;
	const handle = overlayHandle;
	overlayHandle = null;
	handle.close();
}

function mountComposerButton() {
	const fab = el("button", "mmp-fab");
	fab.type = "button";
	fab.title = S.open;
	fab.append(el("span", "", "🧠"), el("span", "", S.tab));
	fab.addEventListener("click", (event) => {
		event.preventDefault();
		event.stopPropagation();
		openOverlay();
	});

	const ensure = () => {
		const bar = document.querySelector(".input-tools");
		if (bar && fab.parentElement !== bar) {
			fab.classList.remove("floating");
			fab.style.left = "";
			fab.style.top = "";
			bar.append(fab);
		} else if (!bar && fab.parentElement !== document.body) {
			fab.classList.add("floating");
			document.body.append(fab);
		}
		if (fab.classList.contains("floating")) {
			const composer = document.querySelector(".inputbox");
			const rect = composer?.getBoundingClientRect();
			if (rect) {
				fab.style.left = `${Math.max(8, rect.left - 4)}px`;
				fab.style.top = `${Math.max(8, rect.top - 30)}px`;
			}
		}
	};

	ensure();
	const timer = window.setInterval(ensure, 800);
	return () => {
		window.clearInterval(timer);
		fab.remove();
	};
}

// ---------------------------------------------------------------------------
// 插件入口
// ---------------------------------------------------------------------------

const state = { tabEditor: null, stopComposerButton: null };

/** 模块被 import（浏览器 attach 时）就挂上输入框旁的小按钮，不必先点开 tab。 */
function ensureComposerButton() {
	if (state.stopComposerButton) return;
	try {
		state.stopComposerButton = mountComposerButton();
	} catch (err) {
		console.error("[mindmap] composer button failed:", err);
	}
}
ensureComposerButton();

export default {
	mount(container, ctx) {
		injectStyle();
		container.innerHTML = "";
		ensureComposerButton();
		if (state.tabEditor) state.tabEditor.destroy();
		state.tabEditor = createEditor(container, {});
		try {
			ctx?.send?.({ type: "mindmap_ready" });
		} catch {
			// 通道异常不影响本地编辑
		}
		return () => {
			if (state.tabEditor) {
				state.tabEditor.destroy();
				state.tabEditor = null;
			}
			closeOverlay();
		};
	},
};
