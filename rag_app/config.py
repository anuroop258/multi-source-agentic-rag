from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

def _path_env(name: str, default: str) -> Path:
    value = Path(os.getenv(name, default)).expanduser()
    return value if value.is_absolute() else ROOT_DIR / value

APP_USERNAME = os.getenv("APP_USERNAME", "").strip()
APP_PASSWORD = os.getenv("APP_PASSWORD", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
GROQ_REASONING_EFFORT = os.getenv("GROQ_REASONING_EFFORT", "low").strip().lower()
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "duckduckgo").strip().lower()
DDGS_REGION = os.getenv("DDGS_REGION", "in-en").strip()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "").strip()
TAVILY_ENABLED = os.getenv("TAVILY_ENABLED", "false").lower() == "true"
GROQ_BROWSER_SEARCH_ENABLED = os.getenv("GROQ_BROWSER_SEARCH_ENABLED", "false").lower() == "true"
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "").strip()
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "multi-source-agentic-rag").strip()

DATA_DIR = _path_env("DATA_DIR", "data")
CHROMA_DIR = _path_env("CHROMA_DIR", "data/chroma")
SQLITE_PATH = _path_env("SQLITE_PATH", "data/conversations.sqlite3")
UPLOAD_DIR = DATA_DIR / "uploads"
for _p in (DATA_DIR, CHROMA_DIR, SQLITE_PATH.parent, UPLOAD_DIR):
    _p.mkdir(parents=True, exist_ok=True)

# LangSmith automatically traces LangGraph runs when enabled. It remains opt-in.
if LANGSMITH_TRACING and LANGSMITH_API_KEY:
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT
else:
    os.environ["LANGSMITH_TRACING"] = "false"
