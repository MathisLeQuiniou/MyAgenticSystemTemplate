import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import type { GraphDescription, Run } from "../api/types";
import { useRunEvents } from "../hooks/useRunEvents";
import { buildSpanTree, computePath, formatDuration, traversedEdges, type Span } from "../lib/trace";
import { GraphView } from "./GraphView";
import { SpanDetails } from "./SpanDetails";
import { StatusBadge } from "./StatusBadge";
import { Timeline } from "./Timeline";

const graphCache = new Map<string, Promise<GraphDescription>>();
const loadGraph = (name: string) => {
  if (!graphCache.has(name)) graphCache.set(name, api.graph(name));
  return graphCache.get(name)!;
};

export function RunDetail({ runId, onRunChanged }: { runId: string; onRunChanged: (run: Run) => void }) {
  const [run, setRun] = useState<Run | null>(null);
  const [graph, setGraph] = useState<GraphDescription | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedSpan, setSelectedSpan] = useState<Span | null>(null);
  const { events, tokens, live, finished } = useRunEvents(runId);

  // Load run + graph structure.
  useEffect(() => {
    setRun(null);
    setSelectedNode(null);
    setSelectedSpan(null);
    setError(null);
    api
      .run(runId)
      .then((r) => {
        setRun(r);
        return loadGraph(r.graph_name).then(setGraph);
      })
      .catch((e) => setError(String(e.message ?? e)));
  }, [runId]);

  // Refresh run metadata when it ends.
  useEffect(() => {
    if (!finished) return;
    api.run(runId).then((r) => {
      setRun(r);
      onRunChanged(r);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [finished, runId]);

  const spans = useMemo(() => buildSpanTree(events), [events]);
  const { path, visits } = useMemo(() => computePath(events, graph), [events, graph]);
  const edgesTaken = useMemo(
    () => traversedEdges(path, graph, events.some((e) => e.type === "run_completed")),
    [path, graph, events],
  );

  // Keep the selected span in sync with new events (status/duration updates).
  const liveSelected = useMemo(() => {
    if (!selectedSpan) return null;
    const find = (list: Span[]): Span | null => {
      for (const s of list) {
        if (s.id === selectedSpan.id) return s;
        const c = find(s.children);
        if (c) return c;
      }
      return null;
    };
    return find(spans) ?? selectedSpan;
  }, [spans, selectedSpan]);

  if (error) return <div className="error-box">{error}</div>;
  if (!run) return <div className="empty">Chargement…</div>;

  const runEnd = [...events].reverse().find((e) => ["run_completed", "run_failed", "run_cancelled"].includes(e.type));
  const status = runEnd
    ? (({ run_completed: "completed", run_failed: "failed", run_cancelled: "cancelled" } as const)[runEnd.type as "run_completed"] ?? run.status)
    : events.length
      ? "running"
      : run.status;
  const answer = runEnd?.payload?.output?.answer ?? run.output?.answer;
  const errorMsg = runEnd?.payload?.error ?? run.error;
  const tokensTotal = runEnd?.payload?.total_tokens ?? run.total_tokens;
  const duration = runEnd?.payload?.duration_ms ?? (run.started_at && run.finished_at ? new Date(run.finished_at).getTime() - new Date(run.started_at).getTime() : null);

  return (
    <div className="run-detail">
      <header className="run-header">
        <div>
          <h2>{run.graph_name}</h2>
          <div className="run-question">{String(run.input?.message ?? JSON.stringify(run.input))}</div>
        </div>
        <div className="run-stats">
          <StatusBadge status={status} />
          {live && <span className="live-pill">LIVE</span>}
          <span>{formatDuration(duration)}</span>
          <span>{tokensTotal} tokens</span>
          <span>{run.model_profile ?? "modèle par défaut"}</span>
          <span className="muted" title="thread_id">
            thread {run.thread_id.slice(0, 8)}
          </span>
          {status === "running" && (
            <button className="danger" onClick={() => api.cancelRun(run.id)}>
              Annuler
            </button>
          )}
        </div>
      </header>

      {(answer || errorMsg) && (
        <section className={`answer ${errorMsg && !answer ? "answer-error" : ""}`}>
          <h4>{answer ? "Réponse finale" : "Erreur"}</h4>
          <div>{answer ?? errorMsg}</div>
        </section>
      )}

      <div className="run-body">
        <section className="panel graph-panel">
          <div className="panel-title">
            Chemin parcouru
            <span className="muted">
              {path.length} étape{path.length > 1 ? "s" : ""}
              {selectedNode ? ` · filtre : ${selectedNode}` : " · clique un nœud pour filtrer"}
            </span>
          </div>
          {graph && (
            <GraphView graph={graph} visits={visits} edgesTaken={edgesTaken} selectedNode={selectedNode} onSelectNode={setSelectedNode} />
          )}
          <div className="path-strip">
            {path.map((p, i) => (
              <span key={i} className={`path-step ${visits.get(p)?.status === "error" ? "error" : ""}`}>
                {p}
              </span>
            ))}
          </div>
        </section>

        <section className="panel timeline-panel">
          <div className="panel-title">
            Trace
            <span className="muted">{events.length} événements</span>
          </div>
          <Timeline
            spans={spans}
            selectedSpan={liveSelected?.id ?? null}
            onSelectSpan={setSelectedSpan}
            nodeFilter={selectedNode}
            tokens={tokens}
          />
          {liveSelected && <SpanDetails span={liveSelected} onClose={() => setSelectedSpan(null)} />}
        </section>
      </div>
    </div>
  );
}
