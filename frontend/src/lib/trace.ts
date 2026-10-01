import type { GraphDescription, TraceEvent } from "../api/types";

export type SpanKind = "node" | "llm" | "tool" | "custom";
export type SpanStatus = "running" | "ok" | "error";

export interface Span {
  id: string;
  kind: SpanKind;
  name: string;
  nodePath: string | null;
  status: SpanStatus;
  start: TraceEvent;
  end?: TraceEvent;
  children: Span[];
  durationMs: number | null;
}

const kindOf = (type: string): SpanKind | null => {
  if (type.startsWith("node_")) return "node";
  if (type.startsWith("llm_")) return "llm";
  if (type.startsWith("tool_")) return "tool";
  if (type === "custom") return "custom";
  return null;
};

/** Rebuild the span tree (node > llm/tool/custom) from the flat event list. */
export function buildSpanTree(events: TraceEvent[]): Span[] {
  const spans = new Map<string, Span>();
  const roots: Span[] = [];

  for (const ev of events) {
    const kind = kindOf(ev.type);
    if (!kind || !ev.span_id) continue;
    const isStart = ev.type.endsWith("_started") || kind === "custom";
    if (isStart) {
      const span: Span = {
        id: ev.span_id,
        kind,
        name: ev.name,
        nodePath: ev.node_path,
        status: kind === "custom" ? "ok" : "running",
        start: ev,
        children: [],
        durationMs: null,
      };
      spans.set(ev.span_id, span);
      const parent = ev.parent_span_id ? spans.get(ev.parent_span_id) : undefined;
      (parent ? parent.children : roots).push(span);
    } else {
      const span = spans.get(ev.span_id);
      if (!span) continue;
      span.end = ev;
      span.status = ev.type.endsWith("_failed") ? "error" : "ok";
      span.durationMs = ev.duration_ms;
    }
  }
  return roots;
}

export interface NodeVisit {
  nodeId: string;
  order: number[]; // 1-based positions in the path
  status: SpanStatus;
}

/**
 * Ordered path of *leaf* graph nodes visited by the run, as ids of the graph
 * description ("router", "researcher:agent", ...). Container nodes of
 * subgraphs ("researcher") are skipped since their inner nodes are shown.
 */
export function computePath(events: TraceEvent[], graph: GraphDescription | null) {
  const containers = new Set((graph?.nodes ?? []).map((n) => n.parent).filter(Boolean) as string[]);
  const path: string[] = [];
  const visits = new Map<string, NodeVisit>();
  const runningSpans = new Map<string, string>(); // span -> node

  for (const ev of events) {
    if (!ev.node_path || containers.has(ev.node_path)) continue;
    if (ev.type === "node_started") {
      path.push(ev.node_path);
      const v = visits.get(ev.node_path) ?? { nodeId: ev.node_path, order: [], status: "running" as SpanStatus };
      v.order.push(path.length);
      v.status = "running";
      visits.set(ev.node_path, v);
      if (ev.span_id) runningSpans.set(ev.span_id, ev.node_path);
    } else if (ev.type === "node_completed" || ev.type === "node_failed") {
      const v = visits.get(ev.node_path);
      if (v) v.status = ev.type === "node_failed" ? "error" : "ok";
    }
  }
  return { path, visits };
}

/**
 * Edges traversed between consecutive nodes of the path. Transitions may go
 * through the implicit __start__/__end__ nodes of (sub)graphs, so we search
 * the shortest route whose intermediate nodes are only start/end nodes.
 */
export function traversedEdges(path: string[], graph: GraphDescription | null, finished: boolean): Set<string> {
  const result = new Set<string>();
  if (!graph || path.length === 0) return result;
  const kind = new Map(graph.nodes.map((n) => [n.id, n.kind]));
  const out = new Map<string, string[]>();
  for (const e of graph.edges) out.set(e.source, [...(out.get(e.source) ?? []), e.target]);

  const link = (from: string, to: string) => {
    const prev = new Map<string, string>([[from, ""]]);
    const queue = [from];
    while (queue.length) {
      const cur = queue.shift()!;
      if (cur === to) break;
      if (cur !== from && kind.get(cur) === "node") continue; // only pass through start/end
      for (const nxt of out.get(cur) ?? []) {
        if (!prev.has(nxt)) {
          prev.set(nxt, cur);
          queue.push(nxt);
        }
      }
    }
    if (!prev.has(to)) return;
    for (let cur = to; cur !== from; cur = prev.get(cur)!) result.add(`${prev.get(cur)}->${cur}`);
  };

  link("__start__", path[0]);
  for (let i = 1; i < path.length; i++) link(path[i - 1], path[i]);
  if (finished) link(path[path.length - 1], "__end__");
  return result;
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "–";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.floor(ms / 60_000)} min ${Math.round((ms % 60_000) / 1000)} s`;
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function timeAgo(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "à l'instant";
  if (s < 3600) return `il y a ${Math.floor(s / 60)} min`;
  if (s < 86400) return `il y a ${Math.floor(s / 3600)} h`;
  return new Date(iso).toLocaleDateString();
}
