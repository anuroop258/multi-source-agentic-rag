from __future__ import annotations
import importlib.util
import os
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
MODULES = ["fastapi", "uvicorn", "multipart", "groq", "langgraph", "chromadb", "sentence_transformers", "rank_bm25", "pypdf", "docx", "httpx", "bs4", "trafilatura", "feedparser", "ddgs", "wikipedia"]
def main():
    print("Python modules:")
    failed = False
    for module in MODULES:
        ok = importlib.util.find_spec(module) is not None
        print(f"  [{'OK' if ok else 'MISSING'}] {module}")
        failed = failed or not ok
    print("\nConfiguration:")
    print("  GROQ_API_KEY configured:", bool(os.getenv("GROQ_API_KEY")))
    print("  TAVILY_API_KEY configured:", bool(os.getenv("TAVILY_API_KEY")))
    print("  GROQ_BROWSER_SEARCH_ENABLED:", os.getenv("GROQ_BROWSER_SEARCH_ENABLED", "false"))
    if not os.getenv("GROQ_API_KEY"):
        print("  Add GROQ_API_KEY to .env before running the chatbot.")
    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
