from types import SimpleNamespace

from rag_app import graph
from rag_app.tools import ToolRegistry


def _msg(content="", calls=None):
    return SimpleNamespace(content=content, tool_calls=calls)


def _call(args='{"expression": "6*7"}'):
    return SimpleNamespace(model_dump=lambda exclude_none=True: {
        "id": "call_1", "type": "function", "function": {"name": "calculator", "arguments": args}})


class FakeClient:
    def __init__(self):
        self.n = 0
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
    def create(self, **kw):
        self.n += 1
        m = _msg(calls=[_call()]) if self.n == 1 else _msg("The answer is 42.")
        return SimpleNamespace(choices=[SimpleNamespace(message=m)])


def test_stream_emits_tool_events_then_answer(monkeypatch):
    monkeypatch.setattr(graph, "GROQ_API_KEY", "k")
    agent = graph.MultiSourceAgent(ToolRegistry())
    agent.client = FakeClient()
    events = list(agent.stream([{"role": "user", "content": "6*7?"}]))
    assert [e["type"] for e in events] == ["tool_start", "tool_done", "answer"]
    assert events[0]["calls"][0]["id"] == "call_1"
    assert events[1]["result_preview"] == "42" and events[1]["id"] == "call_1"
    assert events[2]["answer"] == "The answer is 42."
    assert len(events[2]["tool_trace"]) == 1
