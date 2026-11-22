import type { AppStatus, ChatMessage, ConversationSummary, DocInfo, Settings, StreamEvent } from "./types";

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail ?? detail; } catch { /* ignore */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json();
}

export const api = {
  status: () => fetch("/api/status").then(j<AppStatus>),
  documents: () => fetch("/api/documents").then(j<{ documents: DocInfo[] }>).then((r) => r.documents),
  upload: (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return fetch("/api/documents", { method: "POST", body: fd }).then(
      j<{ indexed: { name: string; chunks: number; status?: string }[]; rejected: { name: string; reason: string }[] }>,
    );
  },
  deleteDocument: (name: string) => fetch(`/api/documents/${encodeURIComponent(name)}`, { method: "DELETE" }).then(j),
  clearIndex: () => fetch("/api/documents", { method: "DELETE" }).then(j),
  conversations: () => fetch("/api/conversations").then(j<{ conversations: ConversationSummary[] }>).then((r) => r.conversations),
  newConversationId: () => fetch("/api/conversations", { method: "POST" }).then(j<{ id: string }>).then((r) => r.id),
  conversation: (id: string) =>
    fetch(`/api/conversations/${id}`).then(
      j<{ messages: { id: number; role: "user" | "assistant"; content: string; trace?: ChatMessage["trace"] }[] }>,
    ),
  deleteConversation: (id: string) => fetch(`/api/conversations/${id}`, { method: "DELETE" }).then(j),
};

/** POST /api/chat and parse the server-sent event stream. */
export async function streamChat(
  body: { conversation_id: string; message: string } & { settings: Settings },
  onEvent: (e: StreamEvent) => void,
  signal: AbortSignal,
) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      conversation_id: body.conversation_id,
      message: body.message,
      search_provider: body.settings.searchProvider,
      browser_search: body.settings.browserSearch,
    }),
    signal,
  });
  if (!res.ok || !res.body) await j(res); // throws with server detail
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (line) onEvent(JSON.parse(line.slice(5).trim()) as StreamEvent);
    }
  }
}
