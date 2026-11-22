"""Start the app: python run.py  (serves API + built frontend on http://127.0.0.1:8000)"""
import argparse
import webbrowser
import uvicorn

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--reload", action="store_true", help="auto-reload on backend changes (dev)")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    if not a.no_browser and not a.reload:
        webbrowser.open(f"http://{a.host}:{a.port}")
    uvicorn.run("rag_app.server:app", host=a.host, port=a.port, reload=a.reload)
