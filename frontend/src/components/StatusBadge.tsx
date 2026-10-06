import type { RunStatus } from "../api/types";

const LABELS: Record<string, string> = {
  pending: "Pending",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
  ok: "OK",
  error: "Error",
};

export function StatusBadge({ status }: { status: RunStatus | "ok" | "error" }) {
  return (
    <span className={`badge badge-${status}`}>
      <span className="dot" />
      {LABELS[status] ?? status}
    </span>
  );
}
