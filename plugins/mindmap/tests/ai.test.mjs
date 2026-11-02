import assert from "node:assert/strict";
import test from "node:test";

const { parseAiGraph } = await import("../client/ai.mjs");
const { serializeMindMap } = await import("../client/mindmap.mjs");

const labels = {
	header: "[map]",
	hint: "hint",
	cross: "cross",
	detail: "note",
	image: "file",
	kinds: { goal: "goal", condition: "condition", step: "step", idea: "idea", risk: "risk", result: "result", image: "image" },
};

const json = {
	nodes: [
		{ id: "n1", kind: "goal", title: "转线上", detail: "6 个月内 30%" },
		{ id: "n2", kind: "step", title: "小红书每周三条" },
		{ id: "n3", kind: "risk", title: "产能跟不上" },
	],
	edges: [
		{ from: "n1", to: "n2" },
		{ from: "n1", to: "n3" },
	],
};

test("plain JSON becomes a laid-out graph", () => {
	const result = parseAiGraph(JSON.stringify(json), labels);
	assert.equal(result.source, "json");
	assert.equal(result.graph.nodes.length, 3);
	assert.equal(result.graph.edges.length, 2);
	// autoLayout 之后不再全部堆在原点
	const xs = new Set(result.graph.nodes.map((n) => n.x));
	assert.ok(xs.size >= 2, "expected layered columns");
});

test("code fences and surrounding prose are tolerated", () => {
	const raw = `好的，下面是图：\n\n\`\`\`json\n${JSON.stringify(json, null, 2)}\n\`\`\`\n\n需要调整再说。`;
	const result = parseAiGraph(raw, labels);
	assert.equal(result.source, "json");
	assert.equal(result.graph.nodes.length, 3);
});

test("trailing commas and single quotes are repaired", () => {
	const raw = "{'nodes':[{'id':'n1','kind':'goal','title':'A',},{'id':'n2','kind':'step','title':'B',}],'edges':[{'from':'n1','to':'n2',}],}";
	const result = parseAiGraph(raw, labels);
	assert.equal(result.source, "json");
	assert.equal(result.graph.nodes.length, 2);
	assert.equal(result.graph.edges.length, 1);
});

test("unknown kinds fall back to idea and Chinese labels are understood", () => {
	const raw = JSON.stringify({
		nodes: [
			{ id: "n1", kind: "目标", title: "A" },
			{ id: "n2", kind: "风险", title: "B" },
			{ id: "n3", kind: "whatever", title: "C" },
		],
		edges: [],
	});
	const result = parseAiGraph(raw, labels);
	assert.deepEqual(
		result.graph.nodes.map((n) => n.kind),
		["goal", "risk", "idea"],
	);
});

test("edges to missing nodes, self loops and duplicates are dropped", () => {
	const raw = JSON.stringify({
		nodes: [
			{ id: "n1", kind: "goal", title: "A" },
			{ id: "n2", kind: "step", title: "B" },
		],
		edges: [
			{ from: "n1", to: "n2" },
			{ from: "n1", to: "n2" },
			{ from: "n1", to: "n1" },
			{ from: "n1", to: "n9" },
		],
	});
	const result = parseAiGraph(raw, labels);
	assert.equal(result.graph.edges.length, 1);
	assert.ok(result.warnings.some((w) => w.includes("n9")));
});

test("node count is capped and reported", () => {
	const nodes = Array.from({ length: 60 }, (_, i) => ({ id: `n${i + 1}`, kind: "step", title: `s${i + 1}` }));
	const result = parseAiGraph(JSON.stringify({ nodes, edges: [] }), labels);
	assert.equal(result.graph.nodes.length, 40);
	assert.ok(result.warnings.some((w) => w.includes("截断")));
});

test("duplicate ids are ignored", () => {
	const raw = JSON.stringify({
		nodes: [
			{ id: "n1", kind: "goal", title: "A" },
			{ id: "n1", kind: "step", title: "B" },
		],
		edges: [],
	});
	assert.equal(parseAiGraph(raw, labels).graph.nodes.length, 1);
});

test("an outline answer still imports through deserializeMindMap", () => {
	const outline = serializeMindMap(
		{
			nodes: [
				{ id: "n1", kind: "goal", title: "转线上", detail: "", x: 0, y: 0 },
				{ id: "n2", kind: "step", title: "小红书", detail: "", x: 400, y: 0 },
			],
			edges: [{ id: "e1", from: "n1", to: "n2", label: "" }],
		},
		labels,
	);
	const result = parseAiGraph(outline, labels);
	assert.equal(result.source, "outline");
	assert.equal(result.graph.nodes.length, 2);
	assert.equal(result.graph.edges.length, 1);
});

test("garbage is reported instead of silently producing an empty graph", () => {
	const result = parseAiGraph("抱歉，我无法回答这个问题。", labels);
	assert.equal(result.graph.nodes.length, 0);
	assert.ok(result.error);
});

test("empty answer is an error", () => {
	assert.ok(parseAiGraph("   ", labels).error);
});
