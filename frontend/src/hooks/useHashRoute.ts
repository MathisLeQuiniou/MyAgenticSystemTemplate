import { useEffect, useState } from "react";

/** Minimal router: `#/runs/<id>` -> selected run id. */
export function useSelectedRun(): [string | null, (id: string | null) => void] {
  const parse = () => window.location.hash.match(/^#\/runs\/([\w-]+)/)?.[1] ?? null;
  const [runId, setRunId] = useState<string | null>(parse);

  useEffect(() => {
    const onHash = () => setRunId(parse());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const select = (id: string | null) => {
    window.location.hash = id ? `#/runs/${id}` : "";
  };
  return [runId, select];
}
