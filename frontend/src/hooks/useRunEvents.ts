import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { TraceEvent } from "../api/types";

const TERMINAL = new Set(["run_completed", "run_failed", "run_cancelled"]);

export interface RunEventsState {
  events: TraceEvent[];
  /** Streamed tokens per LLM span (live only). */
  tokens: Record<string, string>;
  live: boolean;
  finished: boolean;
}

/** Subscribe to a run's SSE stream (replay + live). */
export function useRunEvents(runId: string | null): RunEventsState {
  const [state, setState] = useState<RunEventsState>({ events: [], tokens: {}, live: false, finished: false });
  const seen = useRef<Set<number>>(new Set());

  useEffect(() => {
    setState({ events: [], tokens: {}, live: false, finished: false });
    seen.current = new Set();
    if (!runId) return;

    const es = new EventSource(api.streamUrl(runId));
    es.onopen = () => setState((s) => ({ ...s, live: true }));

    es.addEventListener("trace", (msg) => {
      const ev = JSON.parse((msg as MessageEvent).data) as TraceEvent;
      if (ev.type === "llm_token") {
        const key = ev.span_id ?? "llm";
        setState((s) => ({ ...s, tokens: { ...s.tokens, [key]: (s.tokens[key] ?? "") + (ev.payload.token ?? "") } }));
        return;
      }
      if (seen.current.has(ev.seq)) return;
      seen.current.add(ev.seq);
      const done = TERMINAL.has(ev.type);
      setState((s) => ({ ...s, events: [...s.events, ev], finished: s.finished || done, live: done ? false : s.live }));
      if (done) es.close();
    });

    // The server closes the stream when there is nothing more to send; the
    // browser would then reconnect forever, so we stop here.
    es.onerror = () => {
      es.close();
      setState((s) => ({ ...s, live: false }));
    };
    return () => es.close();
  }, [runId]);

  return state;
}
