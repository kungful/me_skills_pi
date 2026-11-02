const MINDMAP_KINDS = ["goal", "condition", "step", "idea", "risk", "result", "image"];
const MINDMAP_NODE_WIDTH = 236;
const MINDMAP_NODE_HEIGHT = 122;
function emptyMindMap() {
  return { nodes: [], edges: [] };
}
function createMindMapNode(kind, x, y, id, title = "") {
  return { id, kind, title, detail: "", x: Math.round(x), y: Math.round(y) };
}
function nextNodeId(graph) {
  let max = 0;
  for (const node of graph.nodes) {
    const match = /^n(\d+)$/.exec(node.id);
    if (match) max = Math.max(max, Number(match[1]));
  }
  return `n${max + 1}`;
}
function bumpNodeId(id) {
  const match = /^n(\d+)$/.exec(id);
  return match ? `n${Number(match[1]) + 1}` : "n1";
}
function dropNodePositions(graph, removedId) {
  return {
    nodes: graph.nodes.filter((node) => node.id !== removedId),
    edges: graph.edges.filter((edge) => edge.from !== removedId && edge.to !== removedId)
  };
}
function connectMindMapNodes(graph, from, to, edgeId) {
  if (from === to) return graph;
  if (!graph.nodes.some((node) => node.id === from)) return graph;
  if (!graph.nodes.some((node) => node.id === to)) return graph;
  if (graph.edges.some((edge) => edge.from === from && edge.to === to)) return graph;
  return { nodes: graph.nodes, edges: [...graph.edges, { id: edgeId, from, to, label: "" }] };
}
function autoLayoutMindMap(graph) {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const incoming = /* @__PURE__ */ new Map();
  const outgoing = /* @__PURE__ */ new Map();
  for (const node of graph.nodes) {
    incoming.set(node.id, 0);
    outgoing.set(node.id, []);
  }
  for (const edge of graph.edges) {
    if (!byId.has(edge.from) || !byId.has(edge.to)) continue;
    incoming.set(edge.to, (incoming.get(edge.to) ?? 0) + 1);
    outgoing.get(edge.from).push(edge.to);
  }
  const depth = /* @__PURE__ */ new Map();
  const roots = graph.nodes.filter((node) => (incoming.get(node.id) ?? 0) === 0);
  const queue = [];
  for (const root of roots) {
    depth.set(root.id, 0);
    queue.push(root.id);
  }
  while (queue.length > 0) {
    const id = queue.shift();
    const current = depth.get(id) ?? 0;
    for (const child of outgoing.get(id) ?? []) {
      const seen = depth.get(child);
      if (seen !== void 0) continue;
      depth.set(child, current + 1);
      queue.push(child);
    }
  }
  const columns = /* @__PURE__ */ new Map();
  for (const node of graph.nodes) {
    const column = depth.get(node.id) ?? 0;
    const bucket = columns.get(column);
    if (bucket) bucket.push(node);
    else columns.set(column, [node]);
  }
  const positions = /* @__PURE__ */ new Map();
  for (const [column, bucket] of columns) {
    const sorted = [...bucket].sort((a, b) => a.y - b.y || a.x - b.x);
    sorted.forEach((node, row) => {
      positions.set(node.id, {
        x: 48 + column * (MINDMAP_NODE_WIDTH + 76),
        y: 48 + row * (MINDMAP_NODE_HEIGHT + 32)
      });
    });
  }
  return {
    nodes: graph.nodes.map((node) => {
      const position = positions.get(node.id);
      return position ? { ...node, x: position.x, y: position.y } : node;
    }),
    edges: graph.edges
  };
}
function nodeLine(node, labels) {
  const kind = labels.kinds[node.kind] ?? node.kind;
  const title = node.title.trim() || "\u2014";
  return `[${kind}] ${title}`;
}
function fileLine(node, labels) {
  const name = node.imageName?.trim();
  return name ? `${labels.image}: ${name}` : null;
}
function serializeMindMap(graph, labels) {
  if (graph.nodes.length === 0) return "";
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const outgoing = /* @__PURE__ */ new Map();
  const incoming = /* @__PURE__ */ new Map();
  for (const node of graph.nodes) {
    outgoing.set(node.id, []);
    incoming.set(node.id, 0);
  }
  for (const edge of graph.edges) {
    if (!byId.has(edge.from) || !byId.has(edge.to)) continue;
    outgoing.get(edge.from).push(edge);
    incoming.set(edge.to, (incoming.get(edge.to) ?? 0) + 1);
  }
  for (const edges of outgoing.values()) {
    edges.sort((a, b) => {
      const left = byId.get(a.to);
      const right = byId.get(b.to);
      return left.y - right.y || left.x - right.x;
    });
  }
  const lines = [];
  const crossLines = [];
  const visited = /* @__PURE__ */ new Set();
  const walk = (node, depth) => {
    visited.add(node.id);
    const pad = "  ".repeat(depth);
    lines.push(`${pad}${depth === 0 ? "\u25CF" : "\u2022"} ${nodeLine(node, labels)}`);
    const file = fileLine(node, labels);
    if (file) lines.push(`${pad}  ${file}`);
    const detail = node.detail.trim();
    if (detail) {
      for (const detailLine of detail.split(/\r?\n/)) {
        const text = detailLine.trim();
        if (text) lines.push(`${pad}  ${labels.detail}: ${text}`);
      }
    }
    for (const edge of outgoing.get(node.id) ?? []) {
      const target = byId.get(edge.to);
      if (visited.has(target.id)) {
        const relation = edge.label.trim() ? `${edge.label.trim()}: ` : "";
        crossLines.push(`${nodeLine(node, labels)} \u2192 ${relation}${nodeLine(target, labels)}`);
        continue;
      }
      walk(target, depth + 1);
    }
  };
  const roots = graph.nodes.filter((node) => (incoming.get(node.id) ?? 0) === 0).sort((a, b) => a.y - b.y || a.x - b.x);
  for (const root of roots) walk(root, 0);
  for (const node of [...graph.nodes].sort((a, b) => a.y - b.y || a.x - b.x)) {
    if (!visited.has(node.id)) walk(node, 0);
  }
  const blocks = [labels.header, labels.hint, lines.join("\n")];
  if (crossLines.length > 0) blocks.push(`${labels.cross}
${crossLines.map((line) => `- ${line}`).join("\n")}`);
  return blocks.filter((block) => block.trim()).join("\n\n");
}
function countMindMapCycleEdges(graph) {
  return Math.max(0, graph.edges.length - (graph.nodes.length - countMindMapComponents(graph)));
}
function countMindMapComponents(graph) {
  const parent = /* @__PURE__ */ new Map();
  const find = (id) => {
    let current = id;
    while (parent.get(current) !== current) current = parent.get(current);
    return current;
  };
  for (const node of graph.nodes) parent.set(node.id, node.id);
  for (const edge of graph.edges) {
    if (!parent.has(edge.from) || !parent.has(edge.to)) continue;
    const a = find(edge.from);
    const b = find(edge.to);
    if (a !== b) parent.set(a, b);
  }
  const roots = /* @__PURE__ */ new Set();
  for (const node of graph.nodes) roots.add(find(node.id));
  return roots.size;
}
const KIND_ALIASES = {
  goal: "goal",
  \u76EE\u6807: "goal",
  \u76EE\u6A19: "goal",
  condition: "condition",
  \u6761\u4EF6: "condition",
  \u689D\u4EF6: "condition",
  step: "step",
  \u6B65\u9AA4: "step",
  \u6B65\u9A5F: "step",
  idea: "idea",
  \u60F3\u6CD5: "idea",
  risk: "risk",
  \u98CE\u9669: "risk",
  \u98A8\u96AA: "risk",
  result: "result",
  \u7ED3\u679C: "result",
  \u7D50\u679C: "result",
  image: "image",
  \u56FE\u7247: "image",
  \u5716\u7247: "image",
  \u6587\u4EF6: "image",
  file: "image"
};
const BULLET = /^([ \t]*)([●•▪◦*+-])\s+(.*)$/;
const ARROW = /\s*(?:→|->|=>|⇒)\s*/;
const CROSS_HEADINGS = ["\u989D\u5916\u5173\u8054", "\u989D\u5916\u5173\u7CFB", "extra links", "cross links"];
function indentDepth(prefix) {
  let width = 0;
  for (const ch of prefix) width += ch === "	" ? 2 : 1;
  return Math.floor(width / 2);
}
function matchKind(text) {
  const match = /^\[([^\]]*)\]\s*(.*)$/.exec(text.trim());
  if (!match) return null;
  const label = match[1].trim().toLowerCase();
  const kind = KIND_ALIASES[label] ?? KIND_ALIASES[match[1].trim()];
  if (!kind) return null;
  return { kind, rest: match[2].trim() };
}
function startsWithAny(text, prefixes) {
  const lower = text.toLowerCase();
  return prefixes.some((prefix) => prefix && lower.startsWith(prefix.toLowerCase()));
}
function deserializeMindMap(text, labels) {
  const warnings = [];
  const nodes = [];
  const edges = [];
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  const crossAt = lines.findIndex((line) => {
    const trimmed = line.trim();
    return trimmed === labels.cross.trim() || startsWithAny(trimmed, CROSS_HEADINGS);
  });
  const bodyLines = crossAt >= 0 ? lines.slice(0, crossAt) : lines;
  const crossLines = crossAt >= 0 ? lines.slice(crossAt + 1) : [];
  const stack = [];
  let current = null;
  let counter = 0;
  const detailPrefixes = [labels.detail, "\u5907\u6CE8", "\u5907\u6CE8:", "\u8A3B", "\u5907\u6CE8\uFF1A", "note", "notes"];
  const filePrefixes = [labels.image, "\u56FE\u7247", "\u5716\u7247", "\u6587\u4EF6", "image", "file"];
  for (const raw of bodyLines) {
    if (!raw.trim()) continue;
    const bullet = BULLET.exec(raw);
    if (bullet) {
      const rest = bullet[3].trim();
      if (startsWithAny(rest, CROSS_HEADINGS)) continue;
      const parsedKind = matchKind(rest);
      const depth = indentDepth(bullet[1]);
      counter += 1;
      const node = createMindMapNode(parsedKind?.kind ?? "idea", 0, 0, `n${counter}`, parsedKind?.rest ?? rest);
      nodes.push(node);
      current = node;
      while (stack.length > 0 && stack[stack.length - 1].depth >= depth) stack.pop();
      const parent = stack[stack.length - 1];
      if (parent) edges.push({ id: `e${parent.id}-${node.id}`, from: parent.id, to: node.id, label: "" });
      stack.push({ depth, id: node.id });
      continue;
    }
    const trimmed = raw.trim();
    if (trimmed === labels.header.trim() || trimmed.startsWith(labels.hint.trim().slice(0, 12))) {
      continue;
    }
    const separator = trimmed.search(/[:：]/);
    const prefix = separator >= 0 ? trimmed.slice(0, separator).trim() : "";
    const value = separator >= 0 ? trimmed.slice(separator + 1).trim() : "";
    if (current && prefix && startsWithAny(prefix, filePrefixes)) {
      current.imageName = value;
      continue;
    }
    if (current && prefix && startsWithAny(prefix, detailPrefixes)) {
      current.detail = current.detail ? `${current.detail}
${value}` : value;
      continue;
    }
    if (current) {
      current.detail = current.detail ? `${current.detail}
${trimmed}` : trimmed;
      continue;
    }
    if (counter === 0 && trimmed) warnings.push(trimmed.slice(0, 80));
  }
  const byLine = /* @__PURE__ */ new Map();
  for (const node of nodes) byLine.set(nodeLine(node, labels).toLowerCase(), node);
  const byTitle = /* @__PURE__ */ new Map();
  for (const node of nodes) {
    const key = node.title.trim().toLowerCase();
    if (key && !byTitle.has(key)) byTitle.set(key, node);
  }
  const resolveRef = (value) => {
    const exact = byLine.get(value.trim().toLowerCase());
    if (exact) return exact;
    const parsed = matchKind(value);
    const title = (parsed?.rest ?? value).trim().toLowerCase();
    return byTitle.get(title) ?? null;
  };
  for (const raw of crossLines) {
    const line = raw.replace(/^\s*[-*•]\s*/, "").trim();
    if (!line) continue;
    const parts = line.split(ARROW);
    if (parts.length < 2) {
      warnings.push(line.slice(0, 80));
      continue;
    }
    const from = resolveRef(parts[0]);
    let relation = "";
    let tail = parts.slice(1).join(" \u2192 ").trim();
    const colon = tail.lastIndexOf(": ");
    if (colon >= 0 && tail.slice(colon + 2).trimStart().startsWith("[")) {
      relation = tail.slice(0, colon).trim();
      tail = tail.slice(colon + 2).trim();
    }
    const to = resolveRef(tail);
    if (!from || !to || from.id === to.id) {
      warnings.push(line.slice(0, 80));
      continue;
    }
    if (edges.some((edge) => edge.from === from.id && edge.to === to.id)) continue;
    edges.push({ id: `e${from.id}-${to.id}`, from: from.id, to: to.id, label: relation });
  }
  return { graph: autoLayoutMindMap({ nodes, edges }), warnings };
}
const PROMPT_KIND_RULES = [
  { kind: "risk", pattern: /风险|担心|隐患|坑|失败|阻力|问题|risk|concern|worry/i },
  { kind: "condition", pattern: /如果|假如|前提|条件|除非|只要|if |unless/i },
  { kind: "result", pattern: /结果|最终|产出|交付|验收|上线|完成|result|outcome|deliver/i },
  {
    kind: "step",
    pattern: /先|首先|然后|接着|之后|再|同时|顺便|其次|最后|下一步|步骤|step|then|next|first/i
  },
  { kind: "goal", pattern: /目标|目的|想要|我想|我要|打算|希望|计划|愿景|goal|want|wish|aim/i }
];
const PROMPT_CONNECTOR = /[，,]?\s*(然后|接着|之后|同时|另外|其次|最后|而且|并且|以及|但是|不过|所以|因为|首先|先|风险|担心|隐患|前提|条件|如果|除非|只要|目标|目的|结果|问题)\s*/g;
const PROMPT_TITLE_MAX = 26;
const PROMPT_MAX_CLAUSES = 14;
const PROMPT_LEAD = /^(首先|然后|接着|之后|同时|另外|其次|最后|而且|并且|以及|但是|不过|所以|因为|先|风险是|风险|担心|目的是|目的|目标是|目标|结果是|结果|问题是|问题|前提是|前提|条件是|条件)\s*[，,]?\s*/;
function splitPromptClauses(prompt) {
  return prompt.replace(/\r\n?/g, "\n").replace(PROMPT_CONNECTOR, "\u3002$1").split(/[。！？；;\n]+/).map((part) => part.trim().replace(/^[、，,\s]+/, "").replace(/[、，,\s]+$/, "")).filter((part) => part.replace(/[^\p{L}\p{N}]/gu, "").length >= 2).slice(0, PROMPT_MAX_CLAUSES);
}
function classifyPromptClause(clause) {
  for (const rule of PROMPT_KIND_RULES) {
    if (rule.pattern.test(clause)) return rule.kind;
  }
  return "idea";
}
function promptClauseTitle(clause) {
  const trimmed = clause.replace(PROMPT_LEAD, "").trim() || clause.trim();
  return trimmed.length > PROMPT_TITLE_MAX ? `${trimmed.slice(0, PROMPT_TITLE_MAX - 1)}\u2026` : trimmed;
}
function promptToMindMap(prompt) {
  const clauses = splitPromptClauses(prompt);
  if (clauses.length === 0) return emptyMindMap();
  const nodes = [];
  const edges = [];
  const add = (kind, clause, index) => {
    const title = promptClauseTitle(clause);
    const node = createMindMapNode(kind, 0, 0, `n${index + 1}`, title);
    const detail = clause.trim();
    if (detail && detail !== title) node.detail = detail;
    nodes.push(node);
    return node;
  };
  const firstKind = classifyPromptClause(clauses[0]);
  const root = add(firstKind === "step" || firstKind === "result" ? "goal" : firstKind, clauses[0], 0);
  let previous = root;
  for (let index = 1; index < clauses.length; index += 1) {
    const clause = clauses[index];
    const node = add(classifyPromptClause(clause), clause, index);
    const parent = /^(因为|所以)/.test(clause) ? previous : root;
    edges.push({ id: `e${parent.id}-${node.id}`, from: parent.id, to: node.id, label: "" });
    previous = node;
  }
  return autoLayoutMindMap({ nodes, edges });
}
function reindexMindMap(graph, nextId) {
  const start = Number(/^n(\d+)$/.exec(nextId)?.[1] ?? 1);
  const map = /* @__PURE__ */ new Map();
  graph.nodes.forEach((node, index) => {
    map.set(node.id, `n${start + index}`);
  });
  return {
    nodes: graph.nodes.map((node) => ({ ...node, id: map.get(node.id) ?? node.id })),
    edges: graph.edges.map((edge) => {
      const from = map.get(edge.from) ?? edge.from;
      const to = map.get(edge.to) ?? edge.to;
      return { ...edge, id: `e${from}-${to}`, from, to };
    })
  };
}
export {
  MINDMAP_KINDS,
  MINDMAP_NODE_HEIGHT,
  MINDMAP_NODE_WIDTH,
  autoLayoutMindMap,
  bumpNodeId,
  connectMindMapNodes,
  countMindMapComponents,
  countMindMapCycleEdges,
  createMindMapNode,
  deserializeMindMap,
  dropNodePositions,
  emptyMindMap,
  nextNodeId,
  promptToMindMap,
  reindexMindMap,
  serializeMindMap
};
