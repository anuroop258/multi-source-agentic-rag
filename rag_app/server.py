"""FastAPI backend: JSON + SSE API for the web frontend, and static hosting of the built UI."""
from __future__ import annotations
import base64
import hmac
import json
import re
import threading
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from rag_app.config import (
    APP_PASSWORD, APP_USERNAME, CHROMA_DIR, GROQ_API_KEY, GROQ_BROWSER_SEARCH_ENABLED, GROQ_MODEL, ROOT_DIR,
    SEARCH_PROVIDER, SQLITE_PATH, TAVILY_API_KEY, TAVILY_ENABLED, UPLOAD_DIR,
)
from rag_app.documents import load_and_chunk
from rag_app.graph import MultiSourceAgent
from rag_app.memory import ConversationMemory
from rag_app.retrieval import HybridRetriever
from rag_app.tools import ToolRegistry

ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".csv"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
DIST_DIR = ROOT_DIR / "frontend" / "dist"
_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")

app = FastAPI(title="Multi-Source Agentic RAG", docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.get("/healthz", include_in_schema=False)
def healthz():
    """Lightweight platform health check; deliberately avoids loading ML models."""
    return {"status": "ok"}


@app.middleware("http")
async def require_app_login(request, call_next):
    """Protect the public demo with HTTP Basic Auth; keep platform health checks public."""
    if request.url.path == "/healthz":
        return await call_next(request)
    if not APP_USERNAME or not APP_PASSWORD:
        from fastapi.responses import JSONResponse
        return JSONResponse({"detail": "Application login is not configured."}, status_code=503)
    header = request.headers.get("authorization", "")
    try:
        scheme, encoded = header.split(" ", 1)
        if scheme.lower() != "basic":
            raise ValueError("unsupported auth scheme")
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
        username, password = decoded.split(":", 1)
    except (ValueError, UnicodeDecodeError):
        username, password = "", ""
    valid = hmac.compare_digest(username, APP_USERNAME) and hmac.compare_digest(password, APP_PASSWORD)
    if not valid:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            {"detail": "Authentication required."}, status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Multi-Source Agentic RAG"'},
        )
    return await call_next(request)

_retriever: HybridRetriever | None = None
_memory: ConversationMemory | None = None
_init_lock = threading.Lock()


def get_retriever() -> HybridRetriever:
    global _retriever
    with _init_lock:
        if _retriever is None:
            _retriever = HybridRetriever(CHROMA_DIR)
        return _retriever


def get_memory() -> ConversationMemory:
    global _memory
    with _init_lock:
        if _memory is None:
            _memory = ConversationMemory(SQLITE_PATH)
        return _memory


def _check_id(conversation_id: str) -> str:
    if not _ID_RE.match(conversation_id):
        raise HTTPException(400, "Invalid conversation id.")
    return conversation_id


# ---------------------------------------------------------------- status
@app.get("/api/status")
def status():
    try:
        chunks = get_retriever().count()
        retrieval_error = None
    except Exception as exc:  # noqa: BLE001
        chunks, retrieval_error = 0, f"{type(exc).__name__}: {exc}"
    return {
        "model": GROQ_MODEL,
        "groq_configured": bool(GROQ_API_KEY),
        "indexed_chunks": chunks,
        "retrieval_error": retrieval_error,
        "search": {
            "default_provider": "tavily" if (SEARCH_PROVIDER == "tavily" and TAVILY_ENABLED and TAVILY_API_KEY) else "duckduckgo",
            "tavily_available": bool(TAVILY_API_KEY),
            "browser_search_default": GROQ_BROWSER_SEARCH_ENABLED,
        },
    }


# ------------------------------------------------------------- documents
def _doc_path(name: str) -> Path:
    safe = Path(name).name
    if not safe or safe != name:
        raise HTTPException(400, "Invalid file name.")
    return UPLOAD_DIR / safe


@app.get("/api/documents")
def list_documents():
    counts = get_retriever().sources()
    files = {p.name: p for p in UPLOAD_DIR.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES}
    names = sorted(set(files) | set(counts), key=str.lower)
    return {"documents": [
        {"name": n, "size": files[n].stat().st_size if n in files else None, "chunks": counts.get(n, 0),
         "indexed": counts.get(n, 0) > 0}
        for n in names
    ]}


@app.post("/api/documents")
def upload_documents(files: list[UploadFile] = File(...)):
    saved: list[Path] = []
    rejected: list[dict] = []
    for up in files:
        name = Path(up.filename or "").name
        if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
            rejected.append({"name": name or "(unnamed)", "reason": "Unsupported type. Use PDF, DOCX, TXT, MD or CSV."})
            continue
        data = up.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            rejected.append({"name": name, "reason": "File is larger than 50 MB."})
            continue
        target = UPLOAD_DIR / name
        target.write_bytes(data)
        saved.append(target)
    indexed: list[dict] = []
    if saved:
        retriever = get_retriever()
        for path in saved:
            try:
                count = retriever.add_chunks(load_and_chunk([path]), replace_sources=[path.name])
                if count == 0:
                    rejected.append({"name": path.name, "reason": "No extractable text (scanned PDFs need OCR, which is not included)."})
                else:
                    indexed.append({"name": path.name, "chunks": count})
            except Exception as exc:  # noqa: BLE001
                rejected.append({"name": path.name, "reason": f"{type(exc).__name__}: {exc}"})
    return {"indexed": indexed, "rejected": rejected}


@app.delete("/api/documents/{name}")
def delete_document(name: str):
    path = _doc_path(name)
    get_retriever().delete_source(path.name)
    if path.exists():
        path.unlink()
    return {"ok": True}


@app.delete("/api/documents")
def clear_documents():
    """Clears the vector index only; uploaded files stay on disk (same as the old UI)."""
    get_retriever().clear()
    return {"ok": True}


# --------------------------------------------------------- conversations
@app.get("/api/conversations")
def list_conversations():
    return {"conversations": get_memory().list_conversations()}


@app.post("/api/conversations")
def new_conversation():
    return {"id": uuid.uuid4().hex}


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str):
    return {"id": _check_id(conversation_id), "messages": get_memory().messages(conversation_id)}


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str):
    get_memory().delete(_check_id(conversation_id))
    return {"ok": True}


# ------------------------------------------------------------------ chat
class ChatRequest(BaseModel):
    conversation_id: str
    message: str = Field(min_length=1, max_length=20000)
    search_provider: str = "duckduckgo"
    browser_search: bool | None = None


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


@app.post("/api/chat")
def chat(req: ChatRequest):
    conversation_id = _check_id(req.conversation_id)
    prompt = req.message.strip()
    if not prompt:
        raise HTTPException(400, "Message is empty.")
    if not GROQ_API_KEY:
        raise HTTPException(400, "GROQ_API_KEY is missing. Add it to .env and restart the server.")

    provider = "tavily" if (req.search_provider == "tavily" and TAVILY_API_KEY) else "duckduckgo"
    memory = get_memory()

    def events():
        try:
            registry = ToolRegistry(get_retriever(), search_provider=provider,
                                    tavily_api_key=TAVILY_API_KEY if provider == "tavily" else "")
            agent = MultiSourceAgent(registry, enable_browser_search=req.browser_search)
            history = memory.history(conversation_id, limit=10)
            history.append({"role": "user", "content": prompt})
            final: dict | None = None
            for event in agent.stream(history):
                if event["type"] == "answer":
                    final = event
                else:
                    yield _sse(event)
            if final is None:
                raise RuntimeError("The agent returned no answer.")
            memory.add(conversation_id, "user", prompt)
            memory.add(conversation_id, "assistant", final["answer"], trace=final["tool_trace"])
            yield _sse({"type": "answer", "answer": final["answer"], "tool_trace": final["tool_trace"]})
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        yield _sse({"type": "done"})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------- static front end
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        candidate = (DIST_DIR / path).resolve()
        if path and candidate.is_file() and DIST_DIR.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def no_build():
        return {"message": "Frontend not built. Run `npm install && npm run build` in ./frontend, "
                           "or `npm run dev` for development. API docs: /api/docs"}
