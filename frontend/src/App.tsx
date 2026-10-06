import { useCallback } from "react";
import { api } from "./api/client";
import type { Run } from "./api/types";
import { NewRunForm } from "./components/NewRunForm";
import { RunDetail } from "./components/RunDetail";
import { RunList } from "./components/RunList";
import { useSelectedRun } from "./hooks/useHashRoute";
import { usePolling } from "./hooks/usePolling";

export default function App() {
  const [runId, selectRun] = useSelectedRun();
  const { data: runs, error, refresh } = usePolling(() => api.runs(), 3000);

  const onCreated = useCallback(
    (id: string) => {
      selectRun(id);
      refresh();
    },
    [selectRun, refresh],
  );
  const onRunChanged = useCallback((_: Run) => refresh(), [refresh]);
  const currentThread = runs?.find((r) => r.id === runId)?.thread_id ?? null;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <img src="/favicon.svg" alt="" width={22} height={22} />
          Agentic Observer
        </div>
        <NewRunForm onCreated={onCreated} currentThread={currentThread} />
        <div className="sidebar-title">Runs</div>
        {error && <div className="error-box">API unreachable: {error}</div>}
        <RunList runs={runs ?? []} selected={runId} onSelect={selectRun} />
      </aside>
      <main className="main">
        {runId ? (
          <RunDetail key={runId} runId={runId} onRunChanged={onRunChanged} />
        ) : (
          <div className="empty big">Start a run or select one from the list.</div>
        )}
      </main>
    </div>
  );
}
