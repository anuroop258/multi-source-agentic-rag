export interface ToolStep {
  id?: string;
  name: string;
  arguments: string;
  result_preview?: string;
  status?: "running" | "done";
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  trace?: ToolStep[];
  error?: boolean;
  pending?: boolean;
}

export interface ConversationSummary {
  id: string;
  title: string;
  updated_at: string;
  message_count: number;
}

export interface DocInfo {
  name: string;
  size: number | null;
  chunks: number;
  indexed: boolean;
  index_status?: "queued" | "running" | "completed" | "error" | "skipped" | "outdated" | string;
}

export interface AppStatus {
  model: string;
  groq_configured: boolean;
  indexed_chunks: number;
  indexed_documents?: number;
  retrieval_error: string | null;
  cloud_storage: { provider: "cloudflare_ai_search" | string; configured: boolean };
  search: { default_provider: "duckduckgo" | "tavily"; tavily_available: boolean; browser_search_default: boolean };
}

export interface Settings {
  searchProvider: "duckduckgo" | "tavily";
  browserSearch: boolean;
}

export type StreamEvent =
  | { type: "tool_start"; calls: { id: string; name: string; arguments: string }[] }
  | ({ type: "tool_done" } & ToolStep)
  | { type: "answer"; answer: string; tool_trace: ToolStep[] }
  | { type: "error"; message: string }
  | { type: "done" };
