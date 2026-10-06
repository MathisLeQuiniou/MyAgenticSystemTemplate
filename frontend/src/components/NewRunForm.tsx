import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { GraphSummary, ModelProfile } from "../api/types";

interface Props {
  onCreated: (runId: string) => void;
  /** Thread of the selected run, to continue the conversation. */
  currentThread: string | null;
}

export function NewRunForm({ onCreated, currentThread }: Props) {
  const [graphs, setGraphs] = useState<GraphSummary[]>([]);
  const [models, setModels] = useState<ModelProfile[]>([]);
  const [graph, setGraph] = useState("");
  const [model, setModel] = useState("");
  const [message, setMessage] = useState("");
  const [continueThread, setContinueThread] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([api.graphs(), api.models()])
      .then(([g, m]) => {
        setGraphs(g);
        setModels(m);
        setGraph((cur) => cur || g[0]?.name || "");
      })
      .catch((e) => setError(String(e.message ?? e)));
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!graph || !message.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const run = await api.createRun({
        graph,
        input: { message: message.trim() },
        model_profile: model || null,
        thread_id: continueThread && currentThread ? currentThread : null,
      });
      setMessage("");
      onCreated(run.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const defaultModel = models.find((m) => m.is_default);

  return (
    <form className="new-run" onSubmit={submit}>
      <div className="row">
        <label>
          Graph
          <select value={graph} onChange={(e) => setGraph(e.target.value)}>
            {graphs.map((g) => (
              <option key={g.name} value={g.name} title={g.description}>
                {g.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Model
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            <option value="">default{defaultModel ? ` (${defaultModel.name})` : ""}</option>
            {models.map((m) => (
              <option key={m.name} value={m.name}>
                {m.name} · {m.model || m.provider}
              </option>
            ))}
          </select>
        </label>
      </div>
      <textarea
        placeholder="Message… (Ctrl+Enter to run)"
        value={message}
        rows={3}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(e);
        }}
      />
      <div className="row between">
        <label className="checkbox" title={currentThread ?? "Select a run to continue its thread"}>
          <input
            type="checkbox"
            disabled={!currentThread}
            checked={continueThread && !!currentThread}
            onChange={(e) => setContinueThread(e.target.checked)}
          />
          Continue the thread of the displayed run
        </label>
        <button type="submit" disabled={busy || !message.trim() || !graph}>
          {busy ? "…" : "Run"}
        </button>
      </div>
      {error && <div className="error-box">{error}</div>}
    </form>
  );
}
