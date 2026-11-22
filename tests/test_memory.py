from pathlib import Path
from rag_app.memory import ConversationMemory

def test_memory_round_trip(tmp_path):
    mem = ConversationMemory(tmp_path / "chat.db")
    mem.add("thread-1", "user", "Hello")
    mem.add("thread-1", "assistant", "Hi")
    assert mem.history("thread-1") == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ]
    mem.clear("thread-1")
    assert mem.history("thread-1") == []
