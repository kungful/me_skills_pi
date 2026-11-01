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
  deserializeMindMap,
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
  image: "#e879f9",
};

const MIN_SCALE = 0.35;
const MAX_SCALE = 2;
/** Longest edge kept when a photo is shrunk before landing in localStorage. */
const MAX_IMAGE_EDGE = 720;
/** Above this the data URL is re-encoded as JPEG so storage does not overflow. */
const MAX_IMAGE_CHARS = 900_000;

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
      .map((node) => {
        const restored: MindMapNode = {
          id: node.id,
          kind: MINDMAP_KINDS.includes(node.kind) ? node.kind : "idea",
          title: typeof node.title === "string" ? node.title : "",
          detail: typeof node.detail === "string" ? node.detail : "",
          x: Number.isFinite(node.x) ? node.x : 48,
          y: Number.isFinite(node.y) ? node.y : 48,
        };
        if (typeof node.image === "string" && node.image) restored.image = node.image;
        if (typeof node.imageName === "string" && node.imageName) restored.imageName = node.imageName;
        return restored;
      });
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
  const [linkMenu, setLinkMenu] = useState<{
    from: string;
    canvas: { x: number; y: number };
    screen: { x: number; y: number };
  } | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  // Set when the file picker was opened from inside an existing image node.
  const imageNodeRef = useRef<string | null>(null);
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
    image: t("chat.mindmap.label.image"),
    kinds: {
      goal: t("chat.mindmap.kind.goal"),
      condition: t("chat.mindmap.kind.condition"),
      step: t("chat.mindmap.kind.step"),
      idea: t("chat.mindmap.kind.idea"),
      risk: t("chat.mindmap.kind.risk"),
      result: t("chat.mindmap.kind.result"),
      image: t("chat.mindmap.kind.image"),
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

  /** Canvas-space centre of the viewport, used when nothing better is known. */
  const viewCenter = useCallback(() => {
    const rect = canvasRef.current?.getBoundingClientRect();
    const current0 = viewRef.current;
    if (!rect) return { x: 80, y: 80 };
    return {
      x: (rect.width / 2 - current0.x) / current0.scale - MINDMAP_NODE_WIDTH / 2,
      y: (rect.height / 2 - current0.y) / current0.scale - MINDMAP_NODE_HEIGHT / 2,
    };
  }, []);

  /** Slides a spot down-right until it does not land on an existing node card. */
  const freeSpot = useCallback(
    (base: { x: number; y: number }) => {
      const taken = (candidate: { x: number; y: number }) =>
        graph.nodes.some(
          (node) =>
            Math.abs(node.x - candidate.x) < MINDMAP_NODE_WIDTH * 0.7 &&
            Math.abs(node.y - candidate.y) < MINDMAP_NODE_HEIGHT * 0.7,
        );
      let spot = base;
      for (let attempt = 0; attempt < 40 && taken(spot); attempt += 1) {
        spot = { x: spot.x + 30, y: spot.y + 30 };
      }
      return spot;
    },
    [graph.nodes],
  );

  /** Creates a node and, when `fromId` is given, the edge that points at it. */
  const createNode = useCallback(
    (kind: MindMapNodeKind, spot: { x: number; y: number }, fromId?: string, extra?: Partial<MindMapNode>) => {
      const id = nextIdRef.current;
      nextIdRef.current = bumpNodeId(id);
      const created: MindMapNode = { ...createMindMapNode(kind, spot.x, spot.y, id), ...extra };
      setGraph((current) => {
        const withNode: MindMapGraph = { ...current, nodes: [...current.nodes, created] };
        return fromId ? connectMindMapNodes(withNode, fromId, id, `e${fromId}-${id}`) : withNode;
      });
      setSelected({ type: "node", id });
      return id;
    },
    [],
  );

  const addNode = useCallback((position?: { x: number; y: number }, kind?: MindMapNodeKind) => {
    const offset = (graph.nodes.length % 3) * 28;
    const center = viewCenter();
    const spot = position ?? freeSpot({ x: center.x + offset, y: center.y + offset });
    createNode(kind ?? (graph.nodes.length === 0 ? "goal" : "step"), spot);
  }, [createNode, freeSpot, graph.nodes.length, viewCenter]);

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
      if (targetId && targetId !== from) {
        setGraph((current) => connectMindMapNodes(current, from, targetId, `e${from}-${targetId}`));
        setSelected({ type: "edge", id: `e${from}-${targetId}` });
        return;
      }
      // Released over empty canvas: offer the node kinds right there (ComfyUI
      // style) instead of demanding a second "new node" click.
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return;
      const point = toCanvas(upEvent.clientX, upEvent.clientY);
      setLinkMenu({
        from,
        canvas: { x: point.x, y: point.y },
        screen: { x: upEvent.clientX - rect.left, y: upEvent.clientY - rect.top },
      });
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
        // Innermost layer first: kind menu, then the import sheet, then the panel.
        if (linkMenu) {
          setLinkMenu(null);
          return;
        }
        if (importOpen) {
          setImportOpen(false);
          return;
        }
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
  }, [deleteSelection, importOpen, linkMenu, onClose, selected]);

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

  /** Reads a picked file into a data URL, re-encoding oversized photos. */
  const readImage = useCallback((file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("read failed"));
      reader.onload = () => {
        const url = String(reader.result ?? "");
        if (!url) {
          reject(new Error("empty"));
          return;
        }
        if (url.length <= MAX_IMAGE_CHARS) {
          resolve(url);
          return;
        }
        const image = new window.Image();
        image.onerror = () => resolve(url);
        image.onload = () => {
          const ratio = Math.min(1, MAX_IMAGE_EDGE / Math.max(image.width, image.height));
          const canvas = document.createElement("canvas");
          canvas.width = Math.max(1, Math.round(image.width * ratio));
          canvas.height = Math.max(1, Math.round(image.height * ratio));
          const context = canvas.getContext("2d");
          if (!context) {
            resolve(url);
            return;
          }
          context.drawImage(image, 0, 0, canvas.width, canvas.height);
          resolve(canvas.toDataURL("image/jpeg", 0.82));
        };
        image.src = url;
      };
      reader.readAsDataURL(file);
    });
  }, []);

  /** Turns dropped/picked files into nodes: images preview, anything else lists. */
  const placeFiles = useCallback(
    async (files: File[], spot?: { x: number; y: number }) => {
      if (files.length === 0) return;
      const images = files.filter((file) => file.type.startsWith("image/"));
      const others = files.filter((file) => !file.type.startsWith("image/"));
      const base = spot ?? freeSpot(viewCenter());
      let index = 0;
      for (const file of images) {
        try {
          const dataUrl = await readImage(file);
          createNode("image", { x: base.x + index * 26, y: base.y + index * 26 }, undefined, {
            title: "",
            image: dataUrl,
            imageName: file.name,
          });
        } catch {
          setNotice(t("chat.mindmapImageFailed", { name: file.name }));
        }
        index += 1;
      }
      for (const file of others) {
        createNode("idea", { x: base.x + index * 26, y: base.y + index * 26 }, undefined, {
          title: file.name,
          detail: `${Math.max(1, Math.round(file.size / 1024))} KB`,
        });
        index += 1;
      }
    },
    [createNode, freeSpot, readImage, t, viewCenter],
  );

  const attachImage = useCallback(
    async (nodeId: string, file: File) => {
      try {
        const dataUrl = await readImage(file);
        updateNode(nodeId, { kind: "image", image: dataUrl, imageName: file.name });
      } catch {
        setNotice(t("chat.mindmapImageFailed", { name: file.name }));
      }
    },
    [readImage, t, updateNode],
  );

  const parsedImport = useMemo(() => deserializeMindMap(importText, labels), [importText, labels]);

  const applyImport = useCallback(() => {
    if (parsedImport.graph.nodes.length === 0) {
      setNotice(t("chat.mindmapImportEmpty"));
      return;
    }
    const imported = parsedImport.graph;
    nextIdRef.current = nextNodeId(imported);
    setGraph(imported);
    setSelected(null);
    setView({ x: 40, y: 40, scale: 1 });
    setImportOpen(false);
    setNotice(t("chat.mindmapImportDone", { nodes: imported.nodes.length, edges: imported.edges.length }));
  }, [parsedImport, t]);

  // Notices are transient: they only explain a failed pick or a finished import.
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 2800);
    return () => window.clearTimeout(timer);
  }, [notice]);

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
          position: "relative",
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
          <button
            type="button"
            style={buttonStyle}
            title={t("chat.mindmapImageHint")}
            onClick={() => {
              imageNodeRef.current = null;
              fileInputRef.current?.click();
            }}
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <rect x="3" y="4" width="18" height="16" rx="2" />
              <circle cx="8.5" cy="9.5" r="1.6" />
              <path d="M21 16l-5-5-9 9" />
            </svg>
            {t("chat.mindmapAddImage")}
          </button>
          <button
            type="button"
            style={buttonStyle}
            title={t("chat.mindmapImportHint")}
            onClick={() => {
              setImportText(serialized);
              setImportOpen(true);
            }}
          >
            <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M12 15V4" />
              <polyline points="7 9 12 4 17 9" />
              <path d="M4 15v3a2 2 0 002 2h12a2 2 0 002-2v-3" />
            </svg>
            {t("chat.mindmapImport")}
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
            onDragOver={(event) => event.preventDefault()}
            onDrop={(event) => {
              event.preventDefault();
              event.stopPropagation();
              const files = Array.from(event.dataTransfer?.files ?? []);
              if (files.length === 0) return;
              const point = toCanvas(event.clientX, event.clientY);
              void placeFiles(files, {
                x: point.x - MINDMAP_NODE_WIDTH / 2,
                y: point.y - MINDMAP_NODE_HEIGHT / 2,
              });
            }}
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
                    {node.kind === "image" ? (
                      <>
                        <div
                          style={{
                            position: "relative",
                            flex: "1 1 auto",
                            minHeight: 0,
                            borderRadius: 6,
                            overflow: "hidden",
                            background: "color-mix(in srgb, var(--border) 26%, transparent)",
                          }}
                        >
                          {node.image ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                              src={node.image}
                              alt={node.title || node.imageName || ""}
                              title={t("chat.mindmapImageReplace")}
                              onPointerDown={(event) => event.stopPropagation()}
                              onClick={() => {
                                imageNodeRef.current = node.id;
                                fileInputRef.current?.click();
                              }}
                              style={{
                                width: "100%",
                                height: "100%",
                                objectFit: "contain",
                                display: "block",
                                cursor: "pointer",
                              }}
                            />
                          ) : (
                            <button
                              type="button"
                              onPointerDown={(event) => event.stopPropagation()}
                              onClick={() => {
                                imageNodeRef.current = node.id;
                                fileInputRef.current?.click();
                              }}
                              style={{
                                width: "100%",
                                height: "100%",
                                border: "none",
                                background: "none",
                                color: "var(--text-dim)",
                                fontSize: 11,
                                cursor: "pointer",
                              }}
                            >
                              {t("chat.mindmapImagePick")}
                            </button>
                          )}
                        </div>
                        <input
                          value={node.title}
                          onChange={(event) => updateNode(node.id, { title: event.target.value })}
                          onPointerDown={(event) => event.stopPropagation()}
                          onFocus={() => setSelected({ type: "node", id: node.id })}
                          placeholder={t("chat.mindmapImageCaption")}
                          style={{
                            width: "100%",
                            flexShrink: 0,
                            border: "none",
                            outline: "none",
                            background: "transparent",
                            color: "var(--text-muted)",
                            fontSize: 10.5,
                            padding: 0,
                            boxSizing: "border-box",
                          }}
                        />
                      </>
                    ) : (
                      <>
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
                      </>
                    )}
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

            {linkMenu && (() => {
              // ComfyUI-style: the released wire turns into a node picker right
              // where the pointer let go, and the new node is already connected.
              const rect = canvasRef.current?.getBoundingClientRect();
              const menuWidth = 168;
              const menuHeight = 34 + MINDMAP_KINDS.length * 26;
              const left = Math.max(6, Math.min(linkMenu.screen.x, (rect?.width ?? 0) - menuWidth - 6));
              const top = Math.max(6, Math.min(linkMenu.screen.y, (rect?.height ?? 0) - menuHeight - 6));
              return (
                <>
                  <div
                    style={{ position: "absolute", inset: 0, zIndex: 5 }}
                    onPointerDown={() => setLinkMenu(null)}
                  />
                  <div
                    style={{
                      position: "absolute",
                      left,
                      top,
                      zIndex: 6,
                      width: menuWidth,
                      padding: 5,
                      borderRadius: 9,
                      background: "var(--bg)",
                      border: "1px solid var(--border)",
                      boxShadow: "0 14px 34px rgba(0,0,0,0.32)",
                    }}
                  >
                    <div style={{ padding: "3px 6px 5px", fontSize: 10.5, color: "var(--text-dim)" }}>
                      {t("chat.mindmapPickKind")}
                    </div>
                    {MINDMAP_KINDS.map((kind) => (
                      <button
                        key={kind}
                        type="button"
                        onClick={() => {
                          createNode(
                            kind,
                            {
                              x: linkMenu.canvas.x - MINDMAP_NODE_WIDTH / 2,
                              y: linkMenu.canvas.y - MINDMAP_NODE_HEIGHT / 2,
                            },
                            linkMenu.from,
                          );
                          setLinkMenu(null);
                        }}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          width: "100%",
                          padding: "4px 7px",
                          border: "none",
                          borderRadius: 6,
                          background: "none",
                          color: "var(--text)",
                          fontSize: 11.5,
                          textAlign: "left",
                          cursor: "pointer",
                        }}
                        onMouseEnter={(event) => {
                          event.currentTarget.style.background = "var(--bg-panel)";
                        }}
                        onMouseLeave={(event) => {
                          event.currentTarget.style.background = "none";
                        }}
                      >
                        <span
                          style={{
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            background: KIND_COLORS[kind],
                            flexShrink: 0,
                          }}
                        />
                        {labels.kinds[kind]}
                      </button>
                    ))}
                  </div>
                </>
              );
            })()}

            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              hidden
              onChange={(event) => {
                const files = Array.from(event.target.files ?? []);
                event.target.value = "";
                const target = imageNodeRef.current;
                imageNodeRef.current = null;
                if (target && files[0]) {
                  void attachImage(target, files[0]);
                  return;
                }
                void placeFiles(files);
              }}
            />
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

        {notice && (
          <div
            style={{
              position: "absolute",
              left: "50%",
              bottom: 16,
              transform: "translateX(-50%)",
              maxWidth: "80%",
              padding: "6px 12px",
              borderRadius: 8,
              background: "var(--bg-panel)",
              border: "1px solid var(--border)",
              fontSize: 11.5,
              color: "var(--text)",
              boxShadow: "0 8px 20px rgba(0,0,0,0.25)",
              pointerEvents: "none",
            }}
          >
            {notice}
          </div>
        )}

        {importOpen && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              zIndex: 20,
              background: "rgba(0,0,0,0.42)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              padding: 18,
              boxSizing: "border-box",
            }}
            onPointerDown={(event) => {
              if (event.target === event.currentTarget) setImportOpen(false);
            }}
          >
            <div
              style={{
                width: "min(760px, 100%)",
                maxHeight: "100%",
                display: "flex",
                flexDirection: "column",
                gap: 9,
                padding: 14,
                borderRadius: 12,
                background: "var(--bg)",
                border: "1px solid var(--border)",
                boxShadow: "0 20px 50px rgba(0,0,0,0.35)",
                boxSizing: "border-box",
              }}
            >
              <strong style={{ fontSize: 13 }}>{t("chat.mindmapImportTitle")}</strong>
              <span style={{ fontSize: 11.5, lineHeight: 1.5, color: "var(--text-dim)" }}>
                {t("chat.mindmapImportHint")}
              </span>
              <textarea
                value={importText}
                onChange={(event) => setImportText(event.target.value)}
                onKeyDown={(event) => {
                  event.stopPropagation();
                  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                    event.preventDefault();
                    applyImport();
                  }
                }}
                placeholder={t("chat.mindmapImportPlaceholder")}
                spellCheck={false}
                style={{
                  flex: "1 1 auto",
                  minHeight: 240,
                  resize: "vertical",
                  padding: 10,
                  borderRadius: 8,
                  border: "1px solid var(--border)",
                  background: "var(--bg-panel)",
                  color: "var(--text)",
                  fontFamily: "var(--font-mono)",
                  fontSize: 11.5,
                  lineHeight: 1.55,
                  outline: "none",
                  boxSizing: "border-box",
                }}
              />
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{ fontSize: 11.5, color: "var(--text-dim)" }}>
                  {parsedImport.graph.nodes.length > 0
                    ? t("chat.mindmapImportSummary", {
                        nodes: parsedImport.graph.nodes.length,
                        edges: parsedImport.graph.edges.length,
                      })
                    : importText.trim()
                      ? t("chat.mindmapImportNothing")
                      : ""}
                </span>
                <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
                  <button
                    type="button"
                    style={{ ...buttonStyle, color: "var(--text-muted)" }}
                    onClick={() => setImportOpen(false)}
                  >
                    {t("chat.mindmapCancel")}
                  </button>
                  <button
                    type="button"
                    disabled={parsedImport.graph.nodes.length === 0}
                    onClick={applyImport}
                    style={{
                      ...buttonStyle,
                      background: parsedImport.graph.nodes.length > 0 ? "var(--accent)" : "var(--bg-panel)",
                      borderColor: parsedImport.graph.nodes.length > 0 ? "var(--accent)" : "var(--border)",
                      color: parsedImport.graph.nodes.length > 0 ? "#fff" : "var(--text-dim)",
                      fontWeight: 600,
                    }}
                  >
                    {t("chat.mindmapImportApply")}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default MindMapPanel;
