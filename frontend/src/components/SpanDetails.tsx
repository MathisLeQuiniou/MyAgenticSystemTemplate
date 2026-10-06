import type { Span } from "../lib/trace";
import { formatDuration, formatTime } from "../lib/trace";
import { JsonView } from "./JsonView";
import { contentToText, Messages } from "./Messages";
import { StatusBadge } from "./StatusBadge";

export function SpanDetails({ span, onClose }: { span: Span; onClose: () => void }) {
  const start = span.start.payload;
  const end = span.end?.payload ?? {};

  return (
    <div className="span-details">
      <div className="row between">
        <h3>
          <span className={`kind kind-${span.kind}`}>{span.kind.toUpperCase()}</span> {span.name}
        </h3>
        <button className="link" onClick={onClose}>
          ✕
        </button>
      </div>
      <div className="details-meta">
        {span.kind !== "custom" && <StatusBadge status={span.status === "running" ? "running" : span.status} />}
        <span>start {formatTime(span.start.timestamp)}</span>
        <span>duration {formatDuration(span.durationMs)}</span>
        {span.nodePath && <span>node {span.nodePath}</span>}
      </div>

      {span.kind === "llm" && (
        <>
          <div className="details-meta">
            <span>model {start.model}</span>
            {start.provider && <span>provider {start.provider}</span>}
            {end.usage && (
              <span>
                tokens {end.usage.input_tokens ?? "?"} in / {end.usage.output_tokens ?? "?"} out
              </span>
            )}
          </div>
          <h4>Input</h4>
          <Messages messages={start.messages ?? []} />
          {end.output && (
            <>
              <h4>Output</h4>
              <Messages messages={[end.output]} />
            </>
          )}
        </>
      )}

      {span.kind === "tool" && (
        <>
          <h4>Arguments</h4>
          <pre>{JSON.stringify(start.input, null, 2)}</pre>
          <h4>Result</h4>
          <pre>{contentToText(end.output)}</pre>
        </>
      )}

      {span.kind === "node" && (
        <>
          <JsonView label="Input (state)" value={start.input} />
          <JsonView label="Output (state update)" value={end.output} open />
        </>
      )}

      {span.kind === "custom" && <pre>{JSON.stringify(start.data, null, 2)}</pre>}
      {end.error && <div className="error-box">{end.error}</div>}
    </div>
  );
}
