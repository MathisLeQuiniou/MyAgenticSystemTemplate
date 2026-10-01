import type { GraphDescription, GraphSummary, ModelProfile, Run, RunCreate, TraceEvent } from "./types";

const BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  graphs: () => request<GraphSummary[]>("/graphs"),
  graph: (name: string) => request<GraphDescription>(`/graphs/${encodeURIComponent(name)}`),
  models: () => request<ModelProfile[]>("/models"),
  runs: (graph?: string) => request<Run[]>(`/runs${graph ? `?graph=${encodeURIComponent(graph)}` : ""}`),
  run: (id: string) => request<Run>(`/runs/${id}`),
  events: (id: string) => request<TraceEvent[]>(`/runs/${id}/events`),
  createRun: (body: RunCreate) => request<Run>("/runs", { method: "POST", body: JSON.stringify(body) }),
  cancelRun: (id: string) => request<{ cancelled: boolean }>(`/runs/${id}/cancel`, { method: "POST" }),
  streamUrl: (id: string) => `${BASE}/runs/${id}/stream`,
};
