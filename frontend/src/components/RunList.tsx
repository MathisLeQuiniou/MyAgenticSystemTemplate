import type { Run } from "../api/types";
import { formatDuration, timeAgo } from "../lib/trace";
import { StatusBadge } from "./StatusBadge";

interface Props {
  runs: Run[];
  selected: string | null;
  onSelect: (id: string) => void;
}

export function RunList({ runs, selected, onSelect }: Props) {
  if (runs.length === 0) return <div className="empty">No runs yet.</div>;
  return (
    <ul className="run-list">
      {runs.map((r) => {
        const duration =
          r.started_at && r.finished_at ? new Date(r.finished_at).getTime() - new Date(r.started_at).getTime() : null;
        return (
          <li key={r.id} className={r.id === selected ? "selected" : ""} onClick={() => onSelect(r.id)}>
            <div className="row between">
              <span className="run-graph">{r.graph_name}</span>
              <StatusBadge status={r.status} />
            </div>
            <div className="run-message">{String(r.input?.message ?? JSON.stringify(r.input))}</div>
            <div className="run-meta">
              {timeAgo(r.created_at)} · {formatDuration(duration)} · {r.total_tokens} tokens
              {r.model_profile ? ` · ${r.model_profile}` : ""}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
