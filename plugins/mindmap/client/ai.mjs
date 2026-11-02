/**
 * 把模型返回的文本解析成节点图。
 *
 * 约定给模型的「专业格式」是这段 JSON（见 index.mjs 的 SYSTEM_PROMPT）：
 *
 *   {"nodes":[{"id":"n1","kind":"goal","title":"…","detail":"…"}],
 *    "edges":[{"from":"n1","to":"n2","label":"可选"}]}
 *
 * 但模型不总是老实：可能包 ```json 围栏、可能前后加解释、可能直接吐我们
 * 序列化出来的缩进大纲。所以这里按优先级降级：
 *   1) 围栏/花括号里能 JSON.parse 的部分 → 严格校验 + 兜底修正
 *   2) 解析失败就当成大纲文本交给 deserializeMindMap
 *   3) 都不行 → 返回 error，由界面提示
 */
import { MINDMAP_KINDS, autoLayoutMindMap, deserializeMindMap, emptyMindMap } from "./mindmap.mjs";

const MAX_NODES = 40;
const MAX_TITLE = 120;
const MAX_DETAIL = 600;

function stripFences(text) {
	return String(text)
		.replace(/^\uFEFF/, "")
		.replace(/```(?:json|JSON)?\s*/g, "")
		.replace(/```/g, "")
		.trim();
}

/** 从一段可能带前后缀的文本里抠出 JSON 主体。 */
function jsonSlice(text) {
	const clean = stripFences(text);
	const start = clean.indexOf("{");
	const end = clean.lastIndexOf("}");
	if (start < 0 || end <= start) return null;
	return clean.slice(start, end + 1);
}

function asString(value, max) {
	if (typeof value !== "string") return "";
	return value.replace(/\s+/g, " ").trim().slice(0, max);
}

function kindOf(value) {
	const raw = asString(value, 20).toLowerCase();
	if (MINDMAP_KINDS.includes(raw)) return raw;
	// 模型偶尔会写中文/大写/复数
	const aliases = {
		目标: "goal", goal: "goal", objective: "goal",
		条件: "condition", condition: "condition", prerequisite: "condition", constraint: "condition",
		步骤: "step", step: "step", task: "step", action: "step",
		想法: "idea", idea: "idea", note: "idea", insight: "idea",
		风险: "risk", risk: "risk", concern: "risk",
		结论: "result", result: "result", outcome: "result", deliverable: "result",
		图片: "image", image: "image",
	};
	return aliases[raw] ?? "idea";
}

/**
 * @param {string} raw 模型原始输出
 * @param {object} labels 序列化标签（用于大纲兜底）
 * @returns {{graph: object, source: "json"|"outline"|null, warnings: string[], error?: string}}
 */
export function parseAiGraph(raw, labels) {
	const text = String(raw ?? "");
	if (!text.trim()) return { graph: emptyMindMap(), source: null, warnings: [], error: "AI 返回为空" };

	const slice = jsonSlice(text);
	if (slice) {
		let parsed = null;
		try {
			parsed = JSON.parse(slice);
		} catch {
			// 常见毛病：尾逗号、单引号
			try {
				parsed = JSON.parse(slice.replace(/,\s*([}\]])/g, "$1").replace(/'/g, '"'));
			} catch {
				parsed = null;
			}
		}
		if (parsed && Array.isArray(parsed.nodes) && parsed.nodes.length > 0) {
			const graph = fromJson(parsed);
			if (graph.nodes.length > 0) return { graph, source: "json", warnings: graph.warnings ?? [] };
		}
	}

	// 退一步：当成大纲
	if (labels) {
		const { graph, warnings } = deserializeMindMap(text, labels);
		if (graph.nodes.length > 0) return { graph, source: "outline", warnings };
	}
	return { graph: emptyMindMap(), source: null, warnings: [], error: "AI 输出无法解析成节点图" };
}

function fromJson(parsed) {
	const warnings = [];
	const seen = new Set();
	const nodes = [];
	for (const raw of parsed.nodes.slice(0, MAX_NODES)) {
		if (!raw || typeof raw !== "object") continue;
		const id = asString(raw.id, 32) || `n${nodes.length + 1}`;
		if (seen.has(id)) continue;
		seen.add(id);
		const title = asString(raw.title ?? raw.name ?? raw.text, MAX_TITLE);
		const detail = asString(raw.detail ?? raw.note ?? raw.description, MAX_DETAIL);
		nodes.push({
			id,
			kind: kindOf(raw.kind ?? raw.type),
			title,
			detail,
			x: 0,
			y: 0,
		});
	}
	if (nodes.length === 0) return { ...emptyMindMap(), warnings: ["AI 输出没有合法节点"] };
	if (parsed.nodes.length > MAX_NODES) warnings.push(`节点过多，已截断到 ${MAX_NODES} 个`);

	const edges = [];
	const edgeKeys = new Set();
	for (const raw of Array.isArray(parsed.edges) ? parsed.edges : []) {
		if (!raw || typeof raw !== "object") continue;
		const from = asString(raw.from ?? raw.source, 32);
		const to = asString(raw.to ?? raw.target, 32);
		if (!from || !to || from === to) continue;
		if (!seen.has(from) || !seen.has(to)) {
			warnings.push(`丢弃指向不存在节点的边 ${from}→${to}`);
			continue;
		}
		const key = `${from}->${to}`;
		if (edgeKeys.has(key)) continue;
		edgeKeys.add(key);
		edges.push({ id: `e${from}-${to}`, from, to, label: asString(raw.label ?? raw.relation, 24) });
	}

	// 全被指向（环）也照收：序列化会把环降级成「额外关联」，不至于丢信息
	if (nodes.length > 0 && !nodes.some((n) => !edges.some((e) => e.to === n.id))) {
		warnings.push("AI 给的图没有根节点（成环），大纲会把它展开成多棵树");
	}

	return { ...autoLayoutMindMap({ nodes, edges }), warnings };
}
