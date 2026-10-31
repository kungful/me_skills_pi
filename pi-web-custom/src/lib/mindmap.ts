/**
 * Mind map (logic graph) model for the chat composer.
 *
 * The graph is a plain data structure: nodes carry a kind, a one-line title and
 * an optional detail; edges carry direction and an optional relation label.
 * `serializeMindMap` turns it into compact, indented text that a model reads as
 * a reasoning outline, so the graph never needs its own message type.
 */

export const MINDMAP_KINDS = ["goal", "condition", "step", "idea", "risk", "result"] as const;

export type MindMapNodeKind = (typeof MINDMAP_KINDS)[number];

export interface MindMapNode {
  id: string;
  kind: MindMapNodeKind;
  title: string;
  detail: string;
  x: number;
  y: number;
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
