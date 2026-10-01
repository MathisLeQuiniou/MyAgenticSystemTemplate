// Mirrors backend/schemas/*.py. Run `npm run gen:types` to generate the full
// OpenAPI types if you prefer (src/api/openapi.d.ts).

export type RunStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export type EventType =
  | "run_started" | "run_completed" | "run_failed" | "run_cancelled"
  | "node_started" | "node_completed" | "node_failed"
  | "llm_started" | "llm_completed" | "llm_failed" | "llm_token"
  | "tool_started" | "tool_completed" | "tool_failed"
  | "custom";

export interface TraceEvent {
  run_id: string;
  seq: number;
  type: EventType;
  name: string;
  node_path: string | null;
  span_id: string | null;
  parent_span_id: string | null;
  timestamp: string;
  duration_ms: number | null;
  payload: Record<string, any>;
}

export interface Run {
  id: string;
  graph_name: string;
  thread_id: string;
  status: RunStatus;
  model_profile: string | null;
  input: Record<string, any>;
  output: { answer?: string | null; state?: Record<string, any> } | null;
  error: string | null;
  total_tokens: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface GraphSummary {
  name: string;
  description: string;
}

export interface GraphNode {
  id: string;
  label: string;
  parent: string | null;
  kind: "node" | "start" | "end";
}

export interface GraphEdge {
  source: string;
  target: string;
  conditional: boolean;
  label: string | null;
}

export interface GraphDescription extends GraphSummary {
  nodes: GraphNode[];
  edges: GraphEdge[];
  mermaid: string | null;
}

export interface ModelProfile {
  name: string;
  provider: string;
  model: string;
  is_default: boolean;
}

export interface RunCreate {
  graph: string;
  input: Record<string, any>;
  model_profile?: string | null;
  thread_id?: string | null;
}
