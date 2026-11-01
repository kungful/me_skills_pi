import assert from "node:assert/strict";
import test from "node:test";
import { createJiti } from "jiti";

const {
  MINDMAP_NODE_WIDTH,
  autoLayoutMindMap,
  connectMindMapNodes,
  countMindMapComponents,
  createMindMapNode,
  dropNodePositions,
  deserializeMindMap,
  emptyMindMap,
  nextNodeId,
  serializeMindMap,
} = await createJiti(import.meta.url).import("./mindmap.ts");

const labels = {
  header: "[map]",
  hint: "hint",
  cross: "cross",
  detail: "note",
  image: "file",
  kinds: {
    goal: "goal",
    condition: "condition",
    step: "step",
    idea: "idea",
    risk: "risk",
    result: "result",
    image: "image",
  },
};

const node = (id, kind, title, x = 0, y = 0, detail = "") => ({ ...createMindMapNode(kind, x, y, id, title), detail });

test("an empty graph serializes to nothing so the composer is left untouched", () => {
  assert.equal(serializeMindMap(emptyMindMap(), labels), "");
});

test("nesting follows edge direction and detail lines land under their node", () => {
  const graph = {
    nodes: [node("n1", "goal", "ship the shop", 0, 0), node("n2", "step", "小红书先起量", 300, 0, "每周 3 条\n- 图集为主")],
    edges: [{ id: "e1", from: "n1", to: "n2", label: "" }],
  };
  const text = serializeMindMap(graph, labels);
  const [header, hint, outline] = text.split("\n\n");
  assert.equal(header, "[map]");
  assert.equal(hint, "hint");
  assert.deepEqual(outline.split("\n"), [
    "● [goal] ship the shop",
    "  • [step] 小红书先起量",
    "    note: 每周 3 条",
    "    note: - 图集为主",
  ]);
});

test("cycles and back-edges are reported once instead of recursing forever", () => {
  const graph = {
    nodes: [node("n1", "goal", "A", 0, 0), node("n2", "step", "B", 300, 0), node("n3", "result", "C", 600, 0)],
    edges: [
      { id: "e1", from: "n1", to: "n2", label: "" },
      { id: "e2", from: "n2", to: "n3", label: "" },
      { id: "e3", from: "n3", to: "n1", label: "反馈" },
    ],
  };
  const text = serializeMindMap(graph, labels);
  assert.ok(text.includes("● [goal] A"));
  assert.ok(text.includes("[result] C → 反馈: [goal] A"));
  assert.equal(countMindMapComponents(graph), 1);
});

test("a pure cycle still produces a tree instead of an empty outline", () => {
  const graph = {
    nodes: [node("n1", "idea", "A", 0, 0), node("n2", "idea", "B", 200, 0)],
    edges: [
      { id: "e1", from: "n1", to: "n2", label: "" },
      { id: "e2", from: "n2", to: "n1", label: "" },
    ],
  };
  const text = serializeMindMap(graph, labels);
  assert.ok(text.includes("● [idea] A"));
  assert.ok(text.includes("• [idea] B"));
});

test("detached nodes are kept as their own trees", () => {
  const graph = {
    nodes: [node("n1", "goal", "A", 0, 0), node("n2", "step", "B", 300, 0), node("n9", "risk", "orphan", 0, 400)],
    edges: [{ id: "e1", from: "n1", to: "n2", label: "" }],
  };
  const text = serializeMindMap(graph, labels);
  assert.equal(text.split("● ").length - 1, 2);
  assert.ok(text.includes("● [risk] orphan"));
  assert.equal(countMindMapComponents(graph), 2);
});

test("connecting rejects self loops and duplicates", () => {
  const base = { nodes: [node("n1", "goal", "A"), node("n2", "step", "B")], edges: [] };
  const once = connectMindMapNodes(base, "n1", "n2", "e1");
  assert.equal(once.edges.length, 1);
  assert.equal(connectMindMapNodes(once, "n1", "n2", "e2").edges.length, 1);
  assert.equal(connectMindMapNodes(once, "n1", "n1", "e3").edges.length, 1);
  assert.equal(connectMindMapNodes(once, "n1", "missing", "e4").edges.length, 1);
});

test("deleting a node drops its edges and ids keep increasing", () => {
  const graph = {
    nodes: [node("n1", "goal", "A"), node("n2", "step", "B")],
    edges: [{ id: "e1", from: "n1", to: "n2", label: "" }],
  };
  const trimmed = dropNodePositions(graph, "n1");
  assert.equal(trimmed.nodes.length, 1);
  assert.equal(trimmed.edges.length, 0);
  assert.equal(nextNodeId(graph), "n3");
});

test("auto layout places children one column right of their parent", () => {
  const graph = {
    nodes: [node("n1", "goal", "A", 500, 500), node("n2", "step", "B", 10, 10), node("n3", "step", "C", 20, 400)],
    edges: [
      { id: "e1", from: "n1", to: "n2", label: "" },
      { id: "e1b", from: "n1", to: "n3", label: "" },
    ],
  };
  const laid = autoLayoutMindMap(graph);
  const byId = new Map(laid.nodes.map((item) => [item.id, item]));
  assert.equal(byId.get("n1").x, 48);
  assert.equal(byId.get("n2").x, 48 + MINDMAP_NODE_WIDTH + 76);
  assert.equal(byId.get("n3").x, 48 + MINDMAP_NODE_WIDTH + 76);
  assert.ok(byId.get("n3").y > byId.get("n2").y);
});

test("an outline reads back into the same graph and serializes identically", () => {
  const graph = {
    nodes: [
      node("n1", "goal", "ship the shop", 0, 0),
      node("n2", "step", "小红书先起量", 300, 0, "每周 3 条\n- 图集为主"),
      node("n3", "risk", "产能跟不上", 300, 200),
    ],
    edges: [
      { id: "e1", from: "n1", to: "n2", label: "" },
      { id: "e2", from: "n1", to: "n3", label: "" },
      { id: "e3", from: "n3", to: "n2", label: "blocks" },
    ],
  };
  const text = serializeMindMap(graph, labels);
  const parsed = deserializeMindMap(text, labels);
  assert.equal(parsed.graph.nodes.length, 3);
  assert.equal(parsed.graph.edges.length, 3);
  assert.equal(parsed.warnings.length, 0);
  assert.equal(serializeMindMap(parsed.graph, labels), text);
  // Layout is recomputed, so positions are the tidy columns and not the input ones.
  const byTitle = new Map(parsed.graph.nodes.map((item) => [item.title, item]));
  assert.equal(byTitle.get("ship the shop").x, 48);
});

test("a hand-written outline without kind tags still becomes nodes", () => {
  const text = [
    "● 先做内容",
    "  • 每周 3 条",
    "    备注: 图集为主",
    "  • 同时谈 2 个经销商",
  ].join("\n");
  const parsed = deserializeMindMap(text, labels);
  assert.deepEqual(parsed.graph.nodes.map((item) => item.title), ["先做内容", "每周 3 条", "同时谈 2 个经销商"]);
  assert.deepEqual(parsed.graph.edges.map((edge) => `${edge.from}->${edge.to}`), ["n1->n2", "n1->n3"]);
  assert.equal(parsed.graph.nodes[1].detail, "图集为主");
});

test("image nodes keep their file name through the outline", () => {
  const graph = {
    nodes: [
      { ...node("n1", "image", "包装打样"), image: "data:image/png;base64,AAAA", imageName: "draft.png" },
    ],
    edges: [],
  };
  const text = serializeMindMap(graph, labels);
  assert.match(text, /\[image\] 包装打样/);
  assert.match(text, /file: draft\.png/);
  const parsed = deserializeMindMap(text, labels);
  assert.equal(parsed.graph.nodes[0].kind, "image");
  assert.equal(parsed.graph.nodes[0].imageName, "draft.png");
  // The bytes stay local: only the name travels in the outline.
  assert.equal(parsed.graph.nodes[0].image, undefined);
});

test("a cross link that names nothing is reported instead of invented", () => {
  const text = ["[map]", "hint", "", "● [goal] A", "", "cross", "- [goal] A → [step] ghost"].join("\n");
  const parsed = deserializeMindMap(text, labels);
  assert.equal(parsed.graph.nodes.length, 1);
  assert.equal(parsed.graph.edges.length, 0);
  assert.equal(parsed.warnings.length, 1);
});

test("text without any bullet line imports nothing", () => {
  const parsed = deserializeMindMap("随便一段话，没有节点", labels);
  assert.equal(parsed.graph.nodes.length, 0);
  assert.equal(serializeMindMap(parsed.graph, labels), "");
});
