import { useState } from "react";
import type { Span } from "../lib/trace";
import { formatDuration } from "../lib/trace";

interface Props {
  spans: Span[];
  selectedSpan: string | null;
  onSelectSpan: (span: Span) => void;
  /** Only show spans of this graph node (and its children). */
  nodeFilter: string | null;
  tokens: Record<string, string>;
}

const KIND_LABEL = { node: "NODE", llm: "LLM", tool: "TOOL", custom: "EVENT" } as const;
const SKILL_TOOLS = new Set(["load_skill", "read_skill_file"]);

/** Badge + label of a span; skill loads get their own "SKILL" badge. */
function describe(span: Span): { badge: string; badgeClass: string; label: string } {
  if (span.kind === "tool" && SKILL_TOOLS.has(span.name)) {
    const input = span.start.payload.input ?? {};
    const label = span.name === "load_skill" ? String(input.name ?? "?") : `${input.name ?? "?"}/${input.path ?? "?"}`;
    return { badge: "SKILL", badgeClass: "kind-skill", label };
  }
  const label = span.kind === "node" && span.nodePath ? span.nodePath : span.name;
  return { badge: KIND_LABEL[span.kind], badgeClass: `kind-${span.kind}`, label };
}

function matchesFilter(span: Span, filter: string | null): boolean {
  if (!filter) return true;
  return span.nodePath === filter || filter.startsWith(span.nodePath + ":") || !!span.nodePath?.startsWith(filter + ":");
}

function SpanRow({ span, depth, props }: { span: Span; depth: number; props: Props }) {
  const [open, setOpen] = useState(true);
  const usage = span.end?.payload?.usage;
  const live = span.kind === "llm" && span.status === "running" ? props.tokens[span.id] : undefined;
  const children = span.children.filter((c) => c.kind !== "node" || matchesFilter(c, props.nodeFilter));
  const { badge, badgeClass, label } = describe(span);

  return (
    <>
      <div
        className={`span-row status-${span.status} ${props.selectedSpan === span.id ? "selected" : ""}`}
        style={{ paddingLeft: 8 + depth * 18 }}
        onClick={() => props.onSelectSpan(span)}
      >
        <button
          className="toggle"
          style={{ visibility: children.length ? "visible" : "hidden" }}
          onClick={(e) => {
            e.stopPropagation();
            setOpen(!open);
          }}
        >
          {open ? "▾" : "▸"}
        </button>
        <span className={`kind ${badgeClass}`}>{badge}</span>
        <span className="span-name">{label}</span>
        {span.kind === "llm" && span.start.payload.agent && <span className="muted">· {span.start.payload.agent}</span>}
        <span className="spacer" />
        {usage?.total_tokens ? <span className="muted">{usage.total_tokens} tok</span> : null}
        <span className="duration">{span.status === "running" ? <span className="spinner" /> : formatDuration(span.durationMs)}</span>
      </div>
      {live && (
        <div className="live-tokens" style={{ marginLeft: 36 + depth * 18 }}>
          {live}
        </div>
      )}
      {open && children.map((c) => <SpanRow key={c.id} span={c} depth={depth + 1} props={props} />)}
    </>
  );
}

export function Timeline(props: Props) {
  const roots = props.spans.filter((s) => matchesFilter(s, props.nodeFilter));
  if (roots.length === 0) return <div className="empty">No steps yet.</div>;
  return (
    <div className="timeline">
      {roots.map((s) => (
        <SpanRow key={s.id} span={s} depth={0} props={props} />
      ))}
    </div>
  );
}
