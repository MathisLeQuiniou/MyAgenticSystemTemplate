import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { RunDeletePreview } from "../api/types";

interface Props {
  runId: string;
  onCancel: () => void;
  onDeleted: () => void;
}

/** Modal asking "Are you sure?" before irreversibly deleting a run. */
export function ConfirmDeleteDialog({ runId, onCancel, onDeleted }: Props) {
  const [preview, setPreview] = useState<RunDeletePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api
      .deleteRunPreview(runId)
      .then(setPreview)
      .catch((e) => setError(String(e.message ?? e)));
  }, [runId]);

  // Escape closes the dialog (unless a delete is in flight).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !busy && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [busy, onCancel]);

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.deleteRun(runId);
      onDeleted();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  const others = preview?.other_runs_on_thread ?? 0;

  return (
    <div className="modal-backdrop" onClick={() => !busy && onCancel()}>
      <div className="modal" role="alertdialog" aria-modal="true" aria-labelledby="confirm-delete-title" onClick={(e) => e.stopPropagation()}>
        <h3 id="confirm-delete-title">Are you sure you want to delete this run?</h3>
        <p>This action is irreversible.</p>
        {!preview && !error && <p className="muted">Checking what will be deleted…</p>}
        {preview && (
          <ul className="modal-list">
            <li>The run and its trace events will be removed from the application database.</li>
            {preview.checkpoints_will_be_deleted ? (
              <li>
                Its LangGraph checkpoints (thread <code>{preview.thread_id.slice(0, 8)}</code>) will be deleted too.
              </li>
            ) : (
              <li>
                {others} other run{others > 1 ? "s" : ""} share{others > 1 ? "" : "s"} this thread
                (<code>{preview.thread_id.slice(0, 8)}</code>): its checkpoints will be kept.
              </li>
            )}
          </ul>
        )}
        {preview?.active && <div className="error-box">This run is still in progress. Cancel it first.</div>}
        {error && <div className="error-box">{error}</div>}
        <div className="modal-actions">
          <button className="secondary" onClick={onCancel} disabled={busy} autoFocus>
            No
          </button>
          <button className="danger" onClick={confirm} disabled={busy || !preview || preview.active}>
            {busy ? "Deleting…" : "Yes, delete"}
          </button>
        </div>
      </div>
    </div>
  );
}
