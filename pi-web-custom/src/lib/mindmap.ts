/**
 * Mind map (logic graph) model for the chat composer.
 *
 * The graph is a plain data structure: nodes carry a kind, a one-line title and
 * an optional detail; edges carry direction and an optional relation label.
 * `serializeMindMap` turns it into compact, indented text that a model reads as
 * a reasoning outline, so the graph never needs its own message type.
 */

export const MINDMAP_KINDS = ["goal", "condition", "step", "idea", "risk", "result", "image"] as const;

export type MindMapNodeKind = (typeof MINDMAP_KINDS)[number];

export interface MindMapNode {
  id: string;
  kind: MindMapNodeKind;
  title: string;
  detail: string;
  x: number;
  y: number;
  /** Data URL of an attached image (kind "image" only); kept out of the outline. */
  image?: string;
  /** Original file name of the attached image, for the outline and the card. */
  imageName?: string;
}

export interface MindMapEdge {
  id: string;
  from: string;
  to: string;
  label: string;
}

export interface MindMapGraph {
  nodes: MindMapNode[];
  edges: MindMapEdge[];
}

export interface MindMapLabels {
  /** Heading line placed above the outline. */
  header: string;
  /** One-line instruction telling the model how to read the outline. */
  hint: string;
  /** Heading for relations that the outline could not express as nesting. */
  cross: string;
  /** Prefix for a node's free-form detail line. */
  detail: string;
  /** Prefix carrying an attached file's name. */
  image: string;
  /** Human label per node kind. */
  kinds: Record<MindMapNodeKind, string>;
}

export const MINDMAP_NODE_WIDTH = 236;
export const MINDMAP_NODE_HEIGHT = 122;

export function emptyMindMap(): MindMapGraph {
  return { nodes: [], edges: [] };
}

export function createMindMapNode(
  kind: MindMapNodeKind,
  x: number,
  y: number,
  id: string,
  title = "",
): MindMapNode {
  return { id, kind, title, detail: "", x: Math.round(x), y: Math.round(y) };
}

export function nextNodeId(graph: MindMapGraph): string {
  let max = 0;
  for (const node of graph.nodes) {
    const match = /^n(\d+)$/.exec(node.id);
    if (match) max = Math.max(max, Number(match[1]));
  }
  return `n${max + 1}`;
}

/**
 * 生成下一个节点 id，供连续新建时不必回读图状态。
 * @param id 刚用掉的 id
 * @returns 递增后的 id
 */
export function bumpNodeId(id: string): string {
  const match = /^n(\d+)$/.exec(id);
  return match ? `n${Number(match[1]) + 1}` : "n1";
}

export function dropNodePositions(graph: MindMapGraph, removedId: string): MindMapGraph {
  return {
    nodes: graph.nodes.filter((node) => node.id !== removedId),
    edges: graph.edges.filter((edge) => edge.from !== removedId && edge.to !== removedId),
  };
}

/** Rejects self-loops and duplicate edges; returns the graph unchanged when invalid. */
export function connectMindMapNodes(graph: MindMapGraph, from: string, to: string, edgeId: string): MindMapGraph {
  if (from === to) return graph;
  if (!graph.nodes.some((node) => node.id === from)) return graph;
  if (!graph.nodes.some((node) => node.id === to)) return graph;
  if (graph.edges.some((edge) => edge.from === from && edge.to === to)) return graph;
  return { nodes: graph.nodes, edges: [...graph.edges, { id: edgeId, from, to, label: "" }] };
}

/**
 * Layered layout: depth from the roots becomes the column, sibling order the
 * row. Cycles and detached nodes are placed at depth 0 so nothing is lost.
 */
export function autoLayoutMindMap(graph: MindMapGraph): MindMapGraph {
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const incoming = new Map<string, number>();
  const outgoing = new Map<string, string[]>();
  for (const node of graph.nodes) {
    incoming.set(node.id, 0);
    outgoing.set(node.id, []);
  }
  for (const edge of graph.edges) {
    if (!byId.has(edge.from) || !byId.has(edge.to)) continue;
    incoming.set(edge.to, (incoming.get(edge.to) ?? 0) + 1);
    outgoing.get(edge.from)!.push(edge.to);
  }

  const depth = new Map<string, number>();
  const roots = graph.nodes.filter((node) => (incoming.get(node.id) ?? 0) === 0);
  const queue: string[] = [];
  for (const root of roots) {
    depth.set(root.id, 0);
    queue.push(root.id);
  }
  while (queue.length > 0) {
    const id = queue.shift()!;
    const current = depth.get(id) ?? 0;
    for (const child of outgoing.get(id) ?? []) {
      const seen = depth.get(child);
      if (seen !== undefined) continue;
      depth.set(child, current + 1);
      queue.push(child);
    }
  }

  const columns = new Map<number, MindMapNode[]>();
  for (const node of graph.nodes) {
    const column = depth.get(node.id) ?? 0;
    const bucket = columns.get(column);
    if (bucket) bucket.push(node);
    else columns.set(column, [node]);
  }

  const positions = new Map<string, { x: number; y: number }>();
  for (const [column, bucket] of columns) {
    const sorted = [...bucket].sort((a, b) => a.y - b.y || a.x - b.x);
    sorted.forEach((node, row) => {
      positions.set(node.id, {
        x: 48 + column * (MINDMAP_NODE_WIDTH + 76),
        y: 48 + row * (MINDMAP_NODE_HEIGHT + 32),
      });
    });
  }

  return {
    nodes: graph.nodes.map((node) => {
      const position = positions.get(node.id);
      return position ? { ...node, x: position.x, y: position.y } : node;
    }),
    edges: graph.edges,
  };
}

function nodeLine(node: MindMapNode, labels: MindMapLabels): string {
  const kind = labels.kinds[node.kind] ?? node.kind;
  const title = node.title.trim() || "—";
  return `[${kind}] ${title}`;
}

/** Extra outline line naming the file behind an image node. */
function fileLine(node: MindMapNode, labels: MindMapLabels): string | null {
  const name = node.imageName?.trim();
  return name ? `${labels.image}: ${name}` : null;
}

/**
 * Renders the graph as an indented outline (nesting = edge direction) plus a
 * trailing list for back-edges and cycles. With an empty graph this returns
 * an empty string, so callers can skip inserting anything.
 */
export function serializeMindMap(graph: MindMapGraph, labels: MindMapLabels): string {
  if (graph.nodes.length === 0) return "";
  const byId = new Map(graph.nodes.map((node) => [node.id, node]));
  const outgoing = new Map<string, MindMapEdge[]>();
  const incoming = new Map<string, number>();
  for (const node of graph.nodes) {
    outgoing.set(node.id, []);
    incoming.set(node.id, 0);
  }
  for (const edge of graph.edges) {
    if (!byId.has(edge.from) || !byId.has(edge.to)) continue;
    outgoing.get(edge.from)!.push(edge);
    incoming.set(edge.to, (incoming.get(edge.to) ?? 0) + 1);
  }
  for (const edges of outgoing.values()) {
    edges.sort((a, b) => {
      const left = byId.get(a.to)!;
      const right = byId.get(b.to)!;
      return left.y - right.y || left.x - right.x;
    });
  }

  const lines: string[] = [];
  const crossLines: string[] = [];
  const visited = new Set<string>();

  const walk = (node: MindMapNode, depth: number) => {
    visited.add(node.id);
    const pad = "  ".repeat(depth);
    lines.push(`${pad}${depth === 0 ? "●" : "•"} ${nodeLine(node, labels)}`);
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
      const target = byId.get(edge.to)!;
      if (visited.has(target.id)) {
        const relation = edge.label.trim() ? `${edge.label.trim()}: ` : "";
        crossLines.push(`${nodeLine(node, labels)} → ${relation}${nodeLine(target, labels)}`);
        continue;
      }
      walk(target, depth + 1);
    }
  };

  const roots = graph.nodes
    .filter((node) => (incoming.get(node.id) ?? 0) === 0)
    .sort((a, b) => a.y - b.y || a.x - b.x);
  for (const root of roots) walk(root, 0);
  // Cycles leave no root: every remaining component starts a new tree.
  for (const node of [...graph.nodes].sort((a, b) => a.y - b.y || a.x - b.x)) {
    if (!visited.has(node.id)) walk(node, 0);
  }

  const blocks = [labels.header, labels.hint, lines.join("\n")];
  if (crossLines.length > 0) blocks.push(`${labels.cross}\n${crossLines.map((line) => `- ${line}`).join("\n")}`);
  return blocks.filter((block) => block.trim()).join("\n\n");
}

/** Count of edges the serializer had to demote to a cross-link, used by tests. */
export function countMindMapCycleEdges(graph: MindMapGraph): number {
  return Math.max(0, graph.edges.length - (graph.nodes.length - countMindMapComponents(graph)));
}

export function countMindMapComponents(graph: MindMapGraph): number {
  const parent = new Map<string, string>();
  const find = (id: string): string => {
    let current = id;
    while (parent.get(current) !== current) current = parent.get(current)!;
    return current;
  };
  for (const node of graph.nodes) parent.set(node.id, node.id);
  for (const edge of graph.edges) {
    if (!parent.has(edge.from) || !parent.has(edge.to)) continue;
    const a = find(edge.from);
    const b = find(edge.to);
    if (a !== b) parent.set(a, b);
  }
  const roots = new Set<string>();
  for (const node of graph.nodes) roots.add(find(node.id));
  return roots.size;
}

/**
 * Kind labels in every locale we write, so an outline still parses when it is
 * pasted back into a UI running another language.
 */
const KIND_ALIASES: Record<string, MindMapNodeKind> = {
  goal: "goal",
  目标: "goal",
  目標: "goal",
  condition: "condition",
  条件: "condition",
  條件: "condition",
  step: "step",
  步骤: "step",
  步驟: "step",
  idea: "idea",
  想法: "idea",
  risk: "risk",
  风险: "risk",
  風險: "risk",
  result: "result",
  结果: "result",
  結果: "result",
  image: "image",
  图片: "image",
  圖片: "image",
  文件: "image",
  file: "image",
};

const BULLET = /^([ \t]*)([●•▪◦*+-])\s+(.*)$/;
const ARROW = /\s*(?:→|->|=>|⇒)\s*/;
const CROSS_HEADINGS = ["额外关联", "额外关系", "extra links", "cross links"];

function indentDepth(prefix: string): number {
  let width = 0;
  for (const ch of prefix) width += ch === "\t" ? 2 : 1;
  return Math.floor(width / 2);
}

function matchKind(text: string): { kind: MindMapNodeKind; rest: string } | null {
  const match = /^\[([^\]]*)\]\s*(.*)$/.exec(text.trim());
  if (!match) return null;
  const label = match[1].trim().toLowerCase();
  const kind = KIND_ALIASES[label] ?? KIND_ALIASES[match[1].trim()];
  if (!kind) return null;
  return { kind, rest: match[2].trim() };
}

function startsWithAny(text: string, prefixes: string[]): boolean {
  const lower = text.toLowerCase();
  return prefixes.some((prefix) => prefix && lower.startsWith(prefix.toLowerCase()));
}

export interface MindMapParseResult {
  graph: MindMapGraph;
  /** Human-readable notes about lines that could not be used. */
  warnings: string[];
}

/**
 * Rebuild a graph from the outline `serializeMindMap` produced (or any similar
 * hand-written outline): bullets nest by indentation, `备注:` lines become the
 * detail, `图片:` lines name an attached file and the trailing extra-links block
 * becomes back-edges. Positions are recomputed with `autoLayoutMindMap`.
 */
export function deserializeMindMap(text: string, labels: MindMapLabels): MindMapParseResult {
  const warnings: string[] = [];
  const nodes: MindMapNode[] = [];
  const edges: MindMapEdge[] = [];
  const lines = text.replace(/\r\n?/g, "\n").split("\n");

  const crossAt = lines.findIndex((line) => {
    const trimmed = line.trim();
    return trimmed === labels.cross.trim() || startsWithAny(trimmed, CROSS_HEADINGS);
  });
  const bodyLines = crossAt >= 0 ? lines.slice(0, crossAt) : lines;
  const crossLines = crossAt >= 0 ? lines.slice(crossAt + 1) : [];

  const stack: { depth: number; id: string }[] = [];
  let current: MindMapNode | null = null;
  let counter = 0;

  const detailPrefixes = [labels.detail, "备注", "备注:", "註", "备注：", "note", "notes"];
  const filePrefixes = [labels.image, "图片", "圖片", "文件", "image", "file"];

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

    // `前缀: 值` lines belong to the node above them.
    const separator = trimmed.search(/[:：]/);
    const prefix = separator >= 0 ? trimmed.slice(0, separator).trim() : "";
    const value = separator >= 0 ? trimmed.slice(separator + 1).trim() : "";

    if (current && prefix && startsWithAny(prefix, filePrefixes)) {
      current.imageName = value;
      continue;
    }
    if (current && prefix && startsWithAny(prefix, detailPrefixes)) {
      current.detail = current.detail ? `${current.detail}\n${value}` : value;
      continue;
    }
    if (current) {
      // Loose prose between bullets is treated as more detail rather than dropped.
      current.detail = current.detail ? `${current.detail}\n${trimmed}` : trimmed;
      continue;
    }
    if (counter === 0 && trimmed) warnings.push(trimmed.slice(0, 80));
  }

  const byLine = new Map<string, MindMapNode>();
  for (const node of nodes) byLine.set(nodeLine(node, labels).toLowerCase(), node);
  const byTitle = new Map<string, MindMapNode>();
  for (const node of nodes) {
    const key = node.title.trim().toLowerCase();
    if (key && !byTitle.has(key)) byTitle.set(key, node);
  }
  const resolveRef = (value: string): MindMapNode | null => {
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
    let tail = parts.slice(1).join(" → ").trim();
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

/**
 * Prompt → graph, the reverse of `serializeMindMap`: one sentence about what the
 * user wants becomes a first-draft node graph they can edit. It runs locally on
 * keyword rules — instant and free — so it never blocks on a model round trip.
 */

const PROMPT_KIND_RULES: { kind: MindMapNodeKind; pattern: RegExp }[] = [
  { kind: "risk", pattern: /风险|担心|隐患|坑|失败|阻力|问题|risk|concern|worry/i },
  { kind: "condition", pattern: /如果|假如|前提|条件|除非|只要|if |unless/i },
  { kind: "result", pattern: /结果|最终|产出|交付|验收|上线|完成|result|outcome|deliver/i },
  {
    kind: "step",
    pattern: /先|首先|然后|接着|之后|再|同时|顺便|其次|最后|下一步|步骤|step|then|next|first/i,
  },
  { kind: "goal", pattern: /目标|目的|想要|我想|我要|打算|希望|计划|愿景|goal|want|wish|aim/i },
];

/** A comma before a linking word starts a new clause: 「先做A，同时做B」 */
const PROMPT_CONNECTOR =
  /[，,]?\s*(然后|接着|之后|同时|另外|其次|最后|而且|并且|以及|但是|不过|所以|因为|首先|先|风险|担心|隐患|前提|条件|如果|除非|只要|目标|目的|结果|问题)\s*/g;

const PROMPT_TITLE_MAX = 26;
const PROMPT_MAX_CLAUSES = 14;
const PROMPT_LEAD =
  /^(首先|然后|接着|之后|同时|另外|其次|最后|而且|并且|以及|但是|不过|所以|因为|先|风险是|风险|担心|目的是|目的|目标是|目标|结果是|结果|问题是|问题|前提是|前提|条件是|条件)\s*[，,]?\s*/;

function splitPromptClauses(prompt: string): string[] {
  return prompt
    .replace(/\r\n?/g, "\n")
    .replace(PROMPT_CONNECTOR, "。$1")
    .split(/[。！？；;\n]+/)
    .map((part) => part.trim().replace(/^[、，,\s]+/, "").replace(/[、，,\s]+$/, ""))
    .filter((part) => part.replace(/[^\p{L}\p{N}]/gu, "").length >= 2)
    .slice(0, PROMPT_MAX_CLAUSES);
}

function classifyPromptClause(clause: string): MindMapNodeKind {
  for (const rule of PROMPT_KIND_RULES) {
    if (rule.pattern.test(clause)) return rule.kind;
  }
  return "idea";
}

function promptClauseTitle(clause: string): string {
  const trimmed = clause.replace(PROMPT_LEAD, "").trim() || clause.trim();
  return trimmed.length > PROMPT_TITLE_MAX ? `${trimmed.slice(0, PROMPT_TITLE_MAX - 1)}…` : trimmed;
}

/**
 * Turns a prompt into a goal-rooted graph: the first clause becomes the root,
 * the rest hang off it in order, and 「因为/所以」 clauses nest under the clause
 * they explain. Long clauses keep their full text as the node detail.
 */
export function promptToMindMap(prompt: string): MindMapGraph {
  const clauses = splitPromptClauses(prompt);
  if (clauses.length === 0) return emptyMindMap();

  const nodes: MindMapNode[] = [];
  const edges: MindMapEdge[] = [];
  const add = (kind: MindMapNodeKind, clause: string, index: number) => {
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

/** Re-indexes a graph so its ids continue after `nextId` (used when appending). */
export function reindexMindMap(graph: MindMapGraph, nextId: string): MindMapGraph {
  const start = Number(/^n(\d+)$/.exec(nextId)?.[1] ?? 1);
  const map = new Map<string, string>();
  graph.nodes.forEach((node, index) => {
    map.set(node.id, `n${start + index}`);
  });
  return {
    nodes: graph.nodes.map((node) => ({ ...node, id: map.get(node.id) ?? node.id })),
    edges: graph.edges.map((edge) => {
      const from = map.get(edge.from) ?? edge.from;
      const to = map.get(edge.to) ?? edge.to;
      return { ...edge, id: `e${from}-${to}`, from, to };
    }),
  };
}
