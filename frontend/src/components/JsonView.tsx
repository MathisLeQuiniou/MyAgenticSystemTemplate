import { useState } from "react";

/** Collapsible pretty-printed JSON. */
export function JsonView({ value, label, open = false }: { value: unknown; label?: string; open?: boolean }) {
  const [isOpen, setOpen] = useState(open);
  if (value === undefined) return null;
  const text = typeof value === "string" ? value : JSON.stringify(value, null, 2);
  return (
    <div className="json-view">
      <button className="link" onClick={() => setOpen(!isOpen)}>
        {isOpen ? "▾" : "▸"} {label ?? "JSON"}
      </button>
      {isOpen && <pre>{text}</pre>}
    </div>
  );
}
