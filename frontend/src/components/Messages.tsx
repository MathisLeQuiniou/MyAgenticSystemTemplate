/** Renders LangChain messages (as serialised by the backend). */

interface Msg {
  type: string;
  content: unknown;
  name?: string;
  tool_calls?: { name: string; args: unknown; id?: string }[];
  tool_call_id?: string;
}

const ROLE: Record<string, string> = { system: "system", human: "user", ai: "assistant", tool: "tool" };

export function contentToText(content: unknown): string {
  if (typeof content === "string") return content;
  if (Array.isArray(content))
    return content.map((c) => (typeof c === "string" ? c : c?.text ?? JSON.stringify(c))).join("\n");
  return JSON.stringify(content, null, 2);
}

export function Messages({ messages }: { messages: Msg[] }) {
  return (
    <div className="messages">
      {messages.map((m, i) => (
        <div key={i} className={`msg msg-${m.type}`}>
          <div className="msg-role">
            {ROLE[m.type] ?? m.type}
            {m.name ? ` · ${m.name}` : ""}
          </div>
          {contentToText(m.content) && <div className="msg-content">{contentToText(m.content)}</div>}
          {m.tool_calls?.map((tc, j) => (
            <div key={j} className="msg-toolcall">
              → {tc.name}({JSON.stringify(tc.args)})
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
