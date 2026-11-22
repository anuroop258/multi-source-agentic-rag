from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone


class ConversationMemory:
    def __init__(self, db_path: Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute("""CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user','assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )""")
            con.execute("CREATE INDEX IF NOT EXISTS idx_messages_thread ON messages(conversation_id, id)")
            # Lightweight migration: tool trace is stored with assistant messages so the UI
            # can show tool activity after a reload.
            cols = {row[1] for row in con.execute("PRAGMA table_info(messages)")}
            if "trace" not in cols:
                con.execute("ALTER TABLE messages ADD COLUMN trace TEXT")

    def _connect(self):
        con = sqlite3.connect(self.db_path, timeout=30)
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def add(self, conversation_id: str, role: str, content: str, trace: list | None = None) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("Only user and assistant messages can be persisted.")
        with self._connect() as con:
            con.execute(
                "INSERT INTO messages(conversation_id, role, content, created_at, trace) VALUES(?,?,?,?,?)",
                (conversation_id, role, content, datetime.now(timezone.utc).isoformat(),
                 json.dumps(trace, ensure_ascii=False) if trace else None),
            )

    def history(self, conversation_id: str, limit: int = 12) -> list[dict[str, str]]:
        """Role/content pairs for feeding the model."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]

    def messages(self, conversation_id: str, limit: int = 500) -> list[dict]:
        """Full messages (with trace and timestamp) for rendering in the UI."""
        with self._connect() as con:
            rows = con.execute(
                "SELECT id, role, content, created_at, trace FROM messages "
                "WHERE conversation_id=? ORDER BY id DESC LIMIT ?",
                (conversation_id, limit),
            ).fetchall()
        out = []
        for mid, role, content, created_at, trace in reversed(rows):
            item = {"id": mid, "role": role, "content": content, "created_at": created_at}
            if trace:
                try:
                    item["trace"] = json.loads(trace)
                except ValueError:
                    pass
            out.append(item)
        return out

    def list_conversations(self, limit: int = 100) -> list[dict]:
        with self._connect() as con:
            rows = con.execute(
                """SELECT m.conversation_id,
                          MAX(m.id) AS last_id,
                          MAX(m.created_at) AS updated_at,
                          COUNT(*) AS n,
                          (SELECT content FROM messages f
                            WHERE f.conversation_id = m.conversation_id AND f.role = 'user'
                            ORDER BY f.id ASC LIMIT 1) AS first_user
                   FROM messages m GROUP BY m.conversation_id
                   ORDER BY last_id DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        result = []
        for cid, _last_id, updated_at, n, first_user in rows:
            title = " ".join((first_user or "New conversation").split())
            result.append({
                "id": cid,
                "title": title if len(title) <= 60 else title[:57].rstrip() + "...",
                "updated_at": updated_at,
                "message_count": n,
            })
        return result

    def clear(self, conversation_id: str) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))

    delete = clear
