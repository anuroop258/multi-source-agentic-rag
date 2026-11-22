"""Dependency-free validation for the Pages D1 migration."""
import sqlite3
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CloudflareSchemaTests(unittest.TestCase):
    def test_migration_applies_and_creates_expected_columns(self):
        sql = (ROOT / "cloudflare" / "migrations" / "0001_rag_schema.sql").read_text(encoding="utf-8")
        db = sqlite3.connect(":memory:")
        db.executescript(sql)
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn("documents", tables)
        self.assertIn("messages", tables)
        doc_columns = {row[1] for row in db.execute("PRAGMA table_info(documents)")}
        msg_columns = {row[1] for row in db.execute("PRAGMA table_info(messages)")}
        self.assertTrue({"name", "item_id", "size_bytes", "content_type", "chunk_count", "index_status", "created_at"}.issubset(doc_columns))
        self.assertTrue({"id", "conversation_id", "role", "content", "created_at", "trace_json"}.issubset(msg_columns))
        db.execute("INSERT INTO documents(name,item_id,created_at) VALUES(?,?,?)", ("sample.txt", "item-1", "2026-11-22T00:00:00Z"))
        db.execute("INSERT INTO messages(conversation_id,role,content,created_at) VALUES(?,?,?,?)", ("conversation123", "user", "hello", "2026-11-22T00:00:00Z"))
        self.assertEqual(db.execute("SELECT COUNT(*) FROM documents").fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 1)
        db.close()


if __name__ == "__main__":
    unittest.main()
