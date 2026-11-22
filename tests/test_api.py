import json
from fastapi.testclient import TestClient

from rag_app import server
from rag_app.memory import ConversationMemory


class FakeRetriever:
    def __init__(self):
        self.data = {}
    def count(self): return sum(self.data.values())
    def sources(self): return dict(self.data)
    def add_chunks(self, chunks, replace_sources=None, **_):
        for s in replace_sources or []:
            self.data.pop(s, None)
        for c in chunks:
            self.data[c.metadata["source"]] = self.data.get(c.metadata["source"], 0) + 1
        return len(chunks)
    def delete_source(self, name): self.data.pop(name, None)
    def clear(self): self.data.clear()


class FakeAgent:
    def __init__(self, *a, **k): pass
    def stream(self, history):
        yield {"type": "tool_start", "calls": [{"id": "c1", "name": "calculator", "arguments": '{"expression": "2+2"}'}]}
        yield {"type": "tool_done", "id": "c1", "name": "calculator", "arguments": '{"expression": "2+2"}', "result_preview": "4"}
        yield {"type": "answer", "answer": "It is 4.", "tool_trace": [{"id": "c1", "name": "calculator", "arguments": "{}", "result_preview": "4"}]}


def make_client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "UPLOAD_DIR", tmp_path / "uploads")
    (tmp_path / "uploads").mkdir()
    monkeypatch.setattr(server, "_retriever", FakeRetriever())
    monkeypatch.setattr(server, "_memory", ConversationMemory(tmp_path / "c.db"))
    monkeypatch.setattr(server, "APP_USERNAME", "test-user")
    monkeypatch.setattr(server, "APP_PASSWORD", "test-password")
    monkeypatch.setattr(server, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(server, "MultiSourceAgent", FakeAgent)
    return TestClient(server.app, auth=("test-user", "test-password"))


def test_status(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    body = c.get("/api/status").json()
    assert body["groq_configured"] is True and body["indexed_chunks"] == 0


def test_document_lifecycle(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    r = c.post("/api/documents", files=[("files", ("notes.txt", b"hello world\n\nsecond paragraph", "text/plain")),
                                         ("files", ("evil.exe", b"x", "application/octet-stream"))])
    body = r.json()
    assert body["indexed"][0]["name"] == "notes.txt"
    assert body["rejected"][0]["name"] == "evil.exe"
    docs = c.get("/api/documents").json()["documents"]
    assert docs[0]["name"] == "notes.txt" and docs[0]["indexed"]
    assert c.delete("/api/documents/notes.txt").status_code == 200
    assert c.get("/api/documents").json()["documents"] == []


def test_chat_streams_and_persists(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    cid = "a" * 32
    with c.stream("POST", "/api/chat", json={"conversation_id": cid, "message": "2+2?"}) as r:
        events = [json.loads(l[5:]) for l in r.iter_lines() if l.startswith("data:")]
    assert [e["type"] for e in events] == ["tool_start", "tool_done", "answer", "done"]
    msgs = c.get(f"/api/conversations/{cid}").json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["trace"][0]["name"] == "calculator"
    convs = c.get("/api/conversations").json()["conversations"]
    assert convs[0]["title"] == "2+2?"
    c.delete(f"/api/conversations/{cid}")
    assert c.get("/api/conversations").json()["conversations"] == []


def test_chat_rejects_bad_id_and_missing_key(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    assert c.post("/api/chat", json={"conversation_id": "../x", "message": "hi"}).status_code == 400
    monkeypatch.setattr(server, "GROQ_API_KEY", "")
    assert c.post("/api/chat", json={"conversation_id": "b" * 32, "message": "hi"}).status_code == 400


def test_path_traversal_blocked(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    assert c.delete("/api/documents/..%2F..%2Fsecret.txt").status_code in (400, 404, 405)
