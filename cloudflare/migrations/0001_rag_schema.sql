-- Application metadata and conversation memory.
-- Document bytes and hybrid vector/keyword indexes are held by Cloudflare AI Search.
CREATE TABLE IF NOT EXISTS documents (
  name TEXT PRIMARY KEY,
  item_id TEXT NOT NULL UNIQUE,
  size_bytes INTEGER NOT NULL DEFAULT 0,
  content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
  chunk_count INTEGER NOT NULL DEFAULT 0,
  index_status TEXT NOT NULL DEFAULT 'queued',
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at DESC);

CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
  content TEXT NOT NULL,
  created_at TEXT NOT NULL,
  trace_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(conversation_id, id);
