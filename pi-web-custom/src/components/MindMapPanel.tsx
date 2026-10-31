"use client";

/**
 * Mind-map overlay for the chat composer.
 *
 * A ComfyUI-style node canvas: drag nodes, drag from a node's right port onto
 * another node to connect them, then insert the serialized outline into the
 * textarea. The panel is fully self-contained — it owns its own state, keeps
 * the graph in localStorage and only touches the composer through `onInsert`.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "@/hooks/useI18n";
import {
  MINDMAP_KINDS,
  MINDMAP_NODE_HEIGHT,
  MINDMAP_NODE_WIDTH,
  autoLayoutMindMap,
  bumpNodeId,
  connectMindMapNodes,
  createMindMapNode,
  dropNodePositions,
  emptyMindMap,
  nextNodeId,
  serializeMindMap,
  type MindMapGraph,
  type MindMapLabels,
  type MindMapNode,
  type MindMapNodeKind,
} from "@/lib/mindmap";

const KIND_COLORS: Record<MindMapNodeKind, string> = {
  goal: "#f59e0b",
  condition: "#38bdf8",
  step: "#22c55e",
  idea: "#a855f7",
  risk: "#ef4444",
  result: "#14b8a6",
};

const MIN_SCALE = 0.35;
const MAX_SCALE = 2;

interface Props {
  /** localStorage key so each session/draft keeps its own graph. */
  storageKey: string;
  onInsert: (text: string) => void;
  onClose: () => void;
}

interface Viewport {
  x: number;
  y: number;
  scale: number;
}

function loadGraph(storageKey: string): MindMapGraph {
  if (typeof window === "undefined") return emptyMindMap();
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return emptyMindMap();
    const parsed = JSON.parse(raw) as Partial<MindMapGraph> | null;
    if (!parsed || !Array.isArray(parsed.nodes) || !Array.isArray(parsed.edges)) return emptyMindMap();
    const nodes = parsed.nodes
      .filter((node): node is MindMapNode => Boolean(node) && typeof node.id === "string")
      .map((node) => ({
        id: node.id,
        kind: MINDMAP_KINDS.includes(node.kind) ? node.kind : "idea",
        title: typeof node.title === "string" ? node.title : "",
        detail: typeof node.detail === "string" ? node.detail : "",
        x: Number.isFinite(node.x) ? node.x : 48,
        y: Number.isFinite(node.y) ? node.y : 48,
      }));
    const ids = new Set(nodes.map((node) => node.id));
    const edges = parsed.edges
      .filter((edge) => Boolean(edge) && typeof edge.id === "string" && ids.has(edge.from) && ids.has(edge.to))
      .map((edge) => ({ id: edge.id, from: edge.from, to: edge.to, label: typeof edge.label === "string" ? edge.label : "" }));
    return { nodes, edges };
  } catch {
    return emptyMindMap();
  }
}

export function MindMapPanel({ storageKey, onInsert, onClose }: Props) {
  const { t } = useI18n();
  const [graph, setGraph] = useState<MindMapGraph>(() => loadGraph(storageKey));
  const [view, setView] = useState<Viewport>({ x: 40, y: 40, scale: 1 });
  const [selected, setSelected] = useState<{ type: "node" | "edge"; id: string } | null>(null);
  const [linking, setLinking] = useState<{ from: string; x: number; y: number } | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [copied, setCopied] = useState(false);
  const [resetArmed, setResetArmed] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const viewRef = useRef(view);
  const pushTimerRef = useRef<number | null>(null);
  // Ids come from a counter, not from re-reading `graph`: two clicks in the same
  // tick would otherwise both see the old graph and mint the same id.
  const nextIdRef = useRef(nextNodeId(graph));
  viewRef.current = view;

  const labels = useMemo<MindMapLabels>(() => ({
    header: t("chat.mindmap.header"),
    hint: t("chat.mindmap.hint"),
    cross: t("chat.mindmap.cross"),
    detail: t("chat.mindmap.detail"),
    kinds: {
      goal: t("chat.mindmap.kind.goal"),
      condition: t("chat.mindmap.kind.condition"),
      step: t("chat.mindmap.kind.step"),
      idea: t("chat.mindmap.kind.idea"),
      risk: t("chat.mindmap.kind.risk"),
      result: t("chat.mindmap.kind.result"),
    },
  }), [t]);

  const serialized = useMemo(() => serializeMindMap(graph, labels), [graph, labels]);

  // Focus the dialog so the first Tab lands inside it instead of the composer.
  useEffect(() => {
    rootRef.current?.focus();
  }, []);

  // Re-key the panel when the composer switches draft/session.
  const storageKeyRef = useRef(storageKey);
  useEffect(() => {
    if (storageKeyRef.current === storageKey) return;
    storageKeyRef.current = storageKey;
    const loaded = loadGraph(storageKey);
    nextIdRef.current = nextNodeId(loaded);
    setGraph(loaded);
    setSelected(null);
  }, [storageKey]);

  // Persist, debounced: dragging a node fires a state update per pointer move.
  useEffect(() => {
    if (pushTimerRef.current !== null) window.clearTimeout(pushTimerRef.current);
    pushTimerRef.current = window.setTimeout(() => {
      pushTimerRef.current = null;
      try {
        if (graph.nodes.length === 0 && graph.edges.length === 0) window.localStorage.removeItem(storageKey);
        else window.localStorage.setItem(storageKey, JSON.stringify(graph));
      } catch {
        // Storage full or blocked: the graph still works for this open panel.
      }
    }, 250);
    return () => {
      if (pushTimerRef.current !== null) {
        window.clearTimeout(pushTimerRef.current);
        pushTimerRef.current = null;
      }
    };
  }, [graph, storageKey]);

  const toCanvas = useCallback((clientX: number, clientY: number) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    const current = viewRef.current;
    if (!rect) return { x: 0, y: 0 };
    return {
      x: (clientX - rect.left - current.x) / current.scale,
      y: (clientY - rect.top - current.y) / current.scale,
    };
  }, []);

  // Wheel zoom needs a non-passive listener; React's root wheel handler is passive.
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = el.getBoundingClientRect();
      const px = event.clientX - rect.left;
      const py = event.clientY - rect.top;
      setView((current) => {
        const factor = event.deltaY < 0 ? 1.1 : 1 / 1.1;
        const scale = Math.min(MAX_SCALE, Math.max(MIN_SCALE, current.scale * factor));
        const ratio = scale / current.scale;
        return {
          scale,
          x: px - (px - current.x) * ratio,
          y: py - (py - current.y) * ratio,
        };
      });
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  const addNode = useCallback((position?: { x: number; y: number }) => {
    const id = nextIdRef.current;
    nextIdRef.current = bumpNodeId(id);
    const rect = canvasRef.current?.getBoundingClientRect();
    const current0 = viewRef.current;
    const center = rect
      ? {
          x: (rect.width / 2 - current0.x) / current0.scale - MINDMAP_NODE_WIDTH / 2,
          y: (rect.height / 2 - current0.y) / current0.scale - MINDMAP_NODE_HEIGHT / 2,
        }
      : { x: 80, y: 80 };
    const offset = (graph.nodes.length % 3) * 28;
    const spot = position ?? { x: center.x + offset, y: center.y + offset };
    const kind: MindMapNodeKind = graph.nodes.length === 0 ? "goal" : "step";
    const created = createMindMapNode(kind, spot.x, spot.y, id);
    setGraph((current) => ({ ...current, nodes: [...current.nodes, created] }));
    setSelected({ type: "node", id });
  }, [graph]);

  const startNodeDrag = useCallback((event: React.PointerEvent, node: MindMapNode) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    setSelected({ type: "node", id: node.id });
    const startX = event.clientX;
    const startY = event.clientY;
    const originX = node.x;
    const originY = node.y;
    const move = (moveEvent: PointerEvent) => {
      const scale = viewRef.current.scale;
      const nextX = Math.round(originX + (moveEvent.clientX - startX) / scale);
      const nextY = Math.round(originY + (moveEvent.clientY - startY) / scale);
      setGraph((current) => ({
        ...current,
        nodes: current.nodes.map((item) => (item.id === node.id ? { ...item, x: nextX, y: nextY } : item)),
      }));
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }, []);

  const startLink = useCallback((event: React.PointerEvent, node: MindMapNode) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    const from = node.id;
    const update = (clientX: number, clientY: number) => {
      const point = toCanvas(clientX, clientY);
      setLinking({ from, x: point.x, y: point.y });
    };
    update(event.clientX, event.clientY);
    const move = (moveEvent: PointerEvent) => update(moveEvent.clientX, moveEvent.clientY);
    const up = (upEvent: PointerEvent) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      setLinking(null);
      const target = document.elementFromPoint(upEvent.clientX, upEvent.clientY)?.closest("[data-mindmap-node]");
      const targetId = target?.getAttribute("data-mindmap-node") ?? null;
      if (!targetId || targetId === from) return;
      setGraph((current) => connectMindMapNodes(current, from, targetId, `e${from}-${targetId}`));
      setSelected({ type: "edge", id: `e${from}-${targetId}` });
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }, [toCanvas]);

  const startPan = useCallback((event: React.PointerEvent) => {
    if (event.button !== 0 && event.button !== 1) return;
    setSelected(null);
    const startX = event.clientX;
    const startY = event.clientY;
    const originX = viewRef.current.x;
    const originY = viewRef.current.y;
    const move = (moveEvent: PointerEvent) => {
      setView((current) => ({
        ...current,
        x: originX + (moveEvent.clientX - startX),
        y: originY + (moveEvent.clientY - startY),
      }));
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  }, []);

  const deleteSelection = useCallback(() => {
    if (!selected) return;
    if (selected.type === "node") setGraph((current) => dropNodePositions(current, selected.id));
    else setGraph((current) => ({ nodes: current.nodes, edges: current.edges.filter((edge) => edge.id !== selected.id) }));
    setSelected(null);
  }, [selected]);

  // Escape and Delete belong to the panel while it is open. A capture listener
  // keeps working after a canvas click leaves focus on <body>, and swallowing
  // the keys it handles stops the composer's shortcuts from firing behind it.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Delete" && event.key !== "Backspace") return;
      const target = event.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || target?.isContentEditable) return;
      if (!selected) return;
      event.preventDefault();
      event.stopPropagation();
      deleteSelection();
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [deleteSelection, onClose, selected]);

  const cycleKind = useCallback((nodeId: string) => {
    setGraph((current) => ({
      ...current,
      nodes: current.nodes.map((node) => {
        if (node.id !== nodeId) return node;
        const index = MINDMAP_KINDS.indexOf(node.kind);
        const kind = MINDMAP_KINDS[(index + 1) % MINDMAP_KINDS.length];
        return { ...node, kind };
      }),
    }));
  }, []);

  const updateNode = useCallback((nodeId: string, patch: Partial<MindMapNode>) => {
    setGraph((current) => ({
      ...current,
      nodes: current.nodes.map((node) => (node.id === nodeId ? { ...node, ...patch } : node)),
    }));
  }, []);

  const handleCopy = useCallback(async () => {
    if (!serialized) return;
    try {
      await navigator.clipboard.writeText(serialized);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  }, [serialized]);

  const handleInsert = useCallback(() => {
    if (!serialized) return;
    onInsert(serialized);
    onClose();
  }, [serialized, onInsert, onClose]);

  const nodeById = useMemo(() => new Map(graph.nodes.map((node) => [node.id, node])), [graph.nodes]);

  const buttonStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 6,
    height: 30,
    padding: "0 11px",
    background: "var(--bg-panel)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    color: "var(--text)",
    fontSize: 12,
    cursor: "pointer",
    whiteSpace: "nowrap",
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t("chat.mindmapTitle")}
      ref={rootRef}
      tabIndex={-1}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 240,
        background: "rgba(0,0,0,0.42)",
        backdropFilter: "blur(2px)",
        outline: "none",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
        boxSizing: "border-box",
      }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "min(1180px, 100%)",
          height: "min(820px, 100%)",
          display: "flex",
          flexDirection: "column",
          background: "var(--bg)",
          border: "1px solid var(--border)",
          borderRadius: 14,
          boxShadow: "0 24px 60px rgba(0,0,0,0.32)",
          overflow: "hidden",
        }}
      >
        <header style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "12px 14px",
          borderBottom: "1px solid var(--border)",
          flexShrink: 0,
        }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
            <strong style={{ fontSize: 14 }}>{t("chat.mindmapTitle")}</strong>
            <span style={{ fontSize: 11, color: "var(--text-dim)" }}>
              {t("chat.mindmapSubtitle")}
            </span>
          </div>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 11, color: "var(--text-dim)", whiteSpace: "nowrap" }}>
              {t("chat.mindmapNodes", { count: graph.nodes.length })} · {t("chat.mindmapEdges", { count: graph.edges.length })}
            </span>
            <button
              type="button"
              onClick={onClose}
              title={t("chat.mindmapClose")}
              aria-label={t("chat.mindmapClose")}
              style={{ ...buttonStyle, width: 30, padding: 0, justifyContent: "center" }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </header>

        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "9px 14px",
          borderBottom: "1px solid var(--border)",
          flexWrap: "wrap",
          flexShrink: 0,
        }}>
          <button type="button" style={buttonStyle} onClick={() => addNode()}>
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            {t("chat.mindmapAddNode")}
          </button>
          <button type="button" style={buttonStyle} onClick={() => setGraph((current) => autoLayoutMindMap(current))}>
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="4" y1="6" x2="14" y2="6" />
              <line x1="4" y1="12" x2="18" y2="12" />
              <line x1="4" y1="18" x2="10" y2="18" />
            </svg>
            {t("chat.mindmapAutoLayout")}
          </button>
          <button
            type="button"
            style={{
              ...buttonStyle,
              color: resetArmed ? "#ef4444" : "var(--text-muted)",
              borderColor: resetArmed ? "rgba(239,68,68,0.45)" : "var(--border)",
            }}
            onClick={() => {
              if (!resetArmed) {
                setResetArmed(true);
                window.setTimeout(() => setResetArmed(false), 2500);
                return;
              }
              setResetArmed(false);
              setGraph(emptyMindMap());
              setSelected(null);
            }}
          >
            {resetArmed ? t("chat.mindmapClearConfirm") : t("chat.mindmapClear")}
          </button>
          <span style={{ fontSize: 11, color: "var(--text-dim)", marginLeft: 4 }}>
            {t("chat.mindmapEmpty")}
          </span>
          <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
            <button type="button" style={buttonStyle} onClick={() => void handleCopy()} disabled={!serialized}>
              {copied ? t("chat.mindmapCopied") : t("chat.mindmapCopy")}
            </button>
            <button
              type="button"
              onClick={handleInsert}
              disabled={!serialized}
              style={{
                ...buttonStyle,
                background: serialized ? "var(--accent)" : "var(--bg-panel)",
                borderColor: serialized ? "var(--accent)" : "var(--border)",
                color: serialized ? "#fff" : "var(--text-dim)",
                fontWeight: 600,
              }}
            >
              {t("chat.mindmapInsert")}
            </button>
          </div>
        </div>

        <div style={{ flex: "1 1 auto", minHeight: 0, display: "flex", flexDirection: "column" }}>
          <div
            ref={canvasRef}
            onPointerDown={startPan}
            onDoubleClick={(event) => {
              const point = toCanvas(event.clientX, event.clientY);
              addNode({ x: point.x - MINDMAP_NODE_WIDTH / 2, y: point.y - MINDMAP_NODE_HEIGHT / 2 });
            }}
            style={{
              position: "relative",
              flex: "1 1 auto",
              minHeight: 0,
              overflow: "hidden",
              cursor: "grab",
              backgroundColor: "var(--bg-panel)",
              backgroundImage: "radial-gradient(circle, color-mix(in srgb, var(--border) 85%, transparent) 1px, transparent 1px)",
              backgroundSize: `${22 * view.scale}px ${22 * view.scale}px`,
              backgroundPosition: `${view.x}px ${view.y}px`,
            }}
          >
            <div style={{
              position: "absolute",
              inset: 0,
              transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})`,
              transformOrigin: "0 0",
              pointerEvents: "none",
            }}>
              <svg width={1} height={1} style={{ position: "absolute", left: 0, top: 0, overflow: "visible", pointerEvents: "none" }}>
                {graph.edges.map((edge) => {
                  const from = nodeById.get(edge.from);
                  const to = nodeById.get(edge.to);
                  if (!from || !to) return null;
                  const x1 = from.x + MINDMAP_NODE_WIDTH;
                  const y1 = from.y + MINDMAP_NODE_HEIGHT / 2;
                  const x2 = to.x;
                  const y2 = to.y + MINDMAP_NODE_HEIGHT / 2;
                  const bend = Math.max(40, Math.abs(x2 - x1) * 0.45);
                  const path = `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`;
                  const active = selected?.type === "edge" && selected.id === edge.id;
                  return (
                    <g key={edge.id}>
                      <path
                        d={path}
                        fill="none"
                        stroke={active ? "var(--accent)" : "var(--text-dim)"}
                        strokeWidth={active ? 2.4 : 1.6}
                        strokeOpacity={active ? 1 : 0.7}
                      />
                      <path
                        d={path}
                        fill="none"
                        stroke="transparent"
                        strokeWidth={14}
                        style={{ pointerEvents: "stroke", cursor: "pointer" }}
                        onPointerDown={(event) => {
                          event.stopPropagation();
                          setSelected({ type: "edge", id: edge.id });
                        }}
                      />
                      <circle cx={x2} cy={y2} r={3} fill={active ? "var(--accent)" : "var(--text-dim)"} fillOpacity={active ? 1 : 0.8} />
                    </g>
                  );
                })}
                {linking && (() => {
                  const from = nodeById.get(linking.from);
                  if (!from) return null;
                  const x1 = from.x + MINDMAP_NODE_WIDTH;
                  const y1 = from.y + MINDMAP_NODE_HEIGHT / 2;
                  const bend = Math.max(40, Math.abs(linking.x - x1) * 0.45);
                  return (
                    <path
                      d={`M ${x1} ${y1} C ${x1 + bend} ${y1}, ${linking.x - bend} ${linking.y}, ${linking.x} ${linking.y}`}
                      fill="none"
                      stroke="var(--accent)"
                      strokeWidth={2}
                      strokeDasharray="6 4"
                    />
                  );
                })()}
              </svg>

              {graph.nodes.map((node) => {
                const color = KIND_COLORS[node.kind];
                const active = selected?.type === "node" && selected.id === node.id;
                return (
                  <div
                    key={node.id}
                    data-mindmap-node={node.id}
                    onPointerDown={(event) => {
                      // Selecting is the node's job; panning belongs to the empty
                      // canvas, so a click on the card never deselects.
                      event.stopPropagation();
                      setSelected({ type: "node", id: node.id });
                    }}
                    style={{
                      position: "absolute",
                      left: node.x,
                      top: node.y,
                      width: MINDMAP_NODE_WIDTH,
                      height: MINDMAP_NODE_HEIGHT,
                      display: "flex",
                      flexDirection: "column",
                      gap: 5,
                      padding: "7px 9px 8px",
                      borderRadius: 10,
                      background: "var(--bg)",
                      border: `1px solid ${active ? color : "var(--border)"}`,
                      borderTop: `3px solid ${color}`,
                      boxShadow: active
                        ? `0 0 0 2px color-mix(in srgb, ${color} 32%, transparent), 0 8px 20px rgba(0,0,0,0.22)`
                        : "0 6px 16px rgba(0,0,0,0.16)",
                      pointerEvents: "auto",
                      boxSizing: "border-box",
                    }}
                  >
                    <div
                      onPointerDown={(event) => startNodeDrag(event, node)}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                        cursor: "grab",
                        flexShrink: 0,
                      }}
                    >
                      <button
                        type="button"
                        title={t("chat.mindmapCycleKind")}
                        onPointerDown={(event) => event.stopPropagation()}
                        onClick={() => cycleKind(node.id)}
                        style={{
                          padding: "1px 6px",
                          fontSize: 10,
                          fontWeight: 600,
                          lineHeight: 1.5,
                          borderRadius: 5,
                          border: `1px solid color-mix(in srgb, ${color} 55%, transparent)`,
                          background: `color-mix(in srgb, ${color} 16%, transparent)`,
                          color,
                          cursor: "pointer",
                        }}
                      >
                        {labels.kinds[node.kind]}
                      </button>
                      <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--text-dim)", fontFamily: "var(--font-mono)" }}>
                        {node.id}
                      </span>
                      <button
                        type="button"
                        title={t("chat.mindmapDeleteNode")}
                        onPointerDown={(event) => event.stopPropagation()}
                        onClick={() => setGraph((current) => dropNodePositions(current, node.id))}
                        style={{
                          width: 16,
                          height: 16,
                          padding: 0,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          border: "none",
                          background: "none",
                          color: "var(--text-dim)",
                          cursor: "pointer",
                        }}
                      >
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                          <line x1="18" y1="6" x2="6" y2="18" />
                          <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                      </button>
                    </div>
                    <input
                      value={node.title}
                      onChange={(event) => updateNode(node.id, { title: event.target.value })}
                      onPointerDown={(event) => event.stopPropagation()}
                      onFocus={() => setSelected({ type: "node", id: node.id })}
                      placeholder={t("chat.mindmapNodeTitle")}
                      style={{
                        width: "100%",
                        border: "none",
                        outline: "none",
                        background: "transparent",
                        color: "var(--text)",
                        fontSize: 12.5,
                        fontWeight: 600,
                        padding: 0,
                        boxSizing: "border-box",
                      }}
                    />
                    <textarea
                      value={node.detail}
                      onChange={(event) => updateNode(node.id, { detail: event.target.value })}
                      onPointerDown={(event) => event.stopPropagation()}
                      onFocus={() => setSelected({ type: "node", id: node.id })}
                      placeholder={t("chat.mindmapNodeDetail")}
                      rows={2}
                      style={{
                        flex: "1 1 auto",
                        width: "100%",
                        minHeight: 0,
                        resize: "none",
                        border: "none",
                        outline: "none",
                        background: "transparent",
                        color: "var(--text-muted)",
                        fontSize: 11,
                        lineHeight: 1.4,
                        padding: 0,
                        fontFamily: "inherit",
                        boxSizing: "border-box",
                      }}
                    />
                    <div
                      onPointerDown={(event) => startLink(event, node)}
                      title={t("chat.mindmapPort")}
                      style={{
                        position: "absolute",
                        right: -7,
                        top: MINDMAP_NODE_HEIGHT / 2 - 7,
                        width: 14,
                        height: 14,
                        borderRadius: "50%",
                        background: "var(--bg)",
                        border: `2px solid ${color}`,
                        cursor: "crosshair",
                        pointerEvents: "auto",
                      }}
                    />
                    <div style={{
                      position: "absolute",
                      left: -5,
                      top: MINDMAP_NODE_HEIGHT / 2 - 5,
                      width: 10,
                      height: 10,
                      borderRadius: "50%",
                      background: color,
                      opacity: 0.75,
                      pointerEvents: "none",
                    }} />
                  </div>
                );
              })}
            </div>

            {graph.nodes.length === 0 && (
              <div style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                pointerEvents: "none",
                color: "var(--text-dim)",
                fontSize: 12.5,
              }}>
                {t("chat.mindmapEmptyGraph")}
              </div>
            )}

            <div style={{
              position: "absolute",
              left: 10,
              bottom: 10,
              display: "flex",
              alignItems: "center",
              gap: 6,
              fontSize: 11,
              color: "var(--text-dim)",
            }}>
              <button
                type="button"
                onClick={() => setView({ x: 40, y: 40, scale: 1 })}
                style={{ ...buttonStyle, height: 24, fontSize: 11, padding: "0 8px" }}
              >
                {Math.round(view.scale * 100)}%
              </button>
            </div>
          </div>

          <div style={{ borderTop: "1px solid var(--border)", flexShrink: 0 }}>
            <button
              type="button"
              onClick={() => setShowPreview((v) => !v)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                width: "100%",
                padding: "8px 14px",
                background: "none",
                border: "none",
                color: "var(--text-muted)",
                fontSize: 11.5,
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              <svg width="9" height="9" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"
                style={{ transform: showPreview ? "rotate(90deg)" : "none", transition: "transform 0.12s" }}>
                <polyline points="3 1 7 5 3 9" />
              </svg>
              {showPreview ? t("chat.mindmapPreviewHide") : t("chat.mindmapPreview")}
            </button>
            {showPreview && (
              <pre style={{
                margin: 0,
                maxHeight: 200,
                overflow: "auto",
                padding: "0 14px 12px",
                fontSize: 11.5,
                lineHeight: 1.55,
                color: "var(--text-muted)",
                fontFamily: "var(--font-mono)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}>
                {serialized || t("chat.mindmapEmptyGraph")}
              </pre>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default MindMapPanel;
