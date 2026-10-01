import type { RunStatus } from "../api/types";

const LABELS: Record<string, string> = {
  pending: "En attente",
  running: "En cours",
  completed: "Terminé",
  failed: "Échec",
  cancelled: "Annulé",
  ok: "OK",
  error: "Erreur",
};

export function StatusBadge({ status }: { status: RunStatus | "ok" | "error" }) {
  return (
    <span className={`badge badge-${status}`}>
      <span className="dot" />
      {LABELS[status] ?? status}
    </span>
  );
}
