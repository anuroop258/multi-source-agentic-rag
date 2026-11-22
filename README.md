# Multi-Source Agentic RAG System

A local-first agentic research assistant built around **GPT-OSS 120B on Groq**, **LangGraph**, **ChromaDB**, **BM25**, **Cross-Encoder reranking**, and **SQLite conversation memory**. It can answer from uploaded files, discover information on the public web, read specific webpages, query Wikipedia, consume RSS feeds, inspect sitemaps, calculate arithmetic, and optionally look up stock data.

> **Cost design:** the default setup uses the Groq API on the account plan you choose, local open-source retrieval components, and DuckDuckGo search through the `ddgs` library. Tavily and Groq-hosted browser search are optional and disabled by default. This repository does not contain payment details, does not ask for card information, and does not automatically turn on paid providers. Free-tier terms and availability are controlled by each provider and can change.

## Features

- **Agent orchestration:** LangGraph state graph with bounded tool-calling loop and tool trace display.
- **LLM:** Groq `openai/gpt-oss-120b`; the 120B model runs remotely, not on your laptop.
- **Hybrid RAG:** local Sentence Transformers embeddings + persistent ChromaDB dense search + BM25 sparse keyword search + Reciprocal Rank Fusion + local Cross-Encoder reranking.
- **Files:** PDF, DOCX, TXT, Markdown, and CSV upload, extraction, chunking and indexing.
- **Web research:** DuckDuckGo search by default (no API key); optional Tavily provider; direct URL fetch/extraction with optional Playwright rendering; Wikipedia; RSS/Atom feeds; sitemap URL discovery.
- **Other tools:** safe arithmetic calculator; optional Yahoo Finance lookup via `yfinance`.
- **Memory:** persistent conversation history in SQLite.
- **Evaluation:** optional RAGAS script; evaluation calls use Groq API quota and scores depend on your dataset.
- **Web UI:** React + Tailwind single-page app with live streaming tool activity, conversation history, drag-and-drop document manager, dark mode and mobile layout. Served by FastAPI.
- **Observability:** optional LangSmith tracing; disabled by default.

## Requirements

- Windows 11, macOS, or Linux
- **Python 3.11 or 3.12 recommended**
- Internet connection for Groq inference, search, and first-time model downloads
- 8 GB RAM minimum recommended; 16 GB is more comfortable
- No local GPU required. Embedding and reranking models run on CPU.

The first indexing/search run downloads two small Hugging Face models: `sentence-transformers/all-MiniLM-L6-v2` and `cross-encoder/ms-marco-MiniLM-L-6-v2`. They are then cached locally. Initial model downloads and indexing can take a few minutes.

## Windows 11 installation

1. Extract the ZIP.
2. Open PowerShell in the extracted `multi_source_agentic_rag` folder.
3. Create and activate a virtual environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

4. Create your environment file:

```powershell
Copy-Item .env.example .env
```

5. Open `.env` and set your local login credentials and Groq API key. Replace the example password with a long, unique password:

```env
APP_USERNAME=admin
APP_PASSWORD=replace-with-a-long-unique-password
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
```

Get the key from [Groq Console](https://console.groq.com/). A Groq API key is required for LLM answers. Whether a Groq request is free depends on your current Groq account plan and its rate limits. To stay on a free plan, do not upgrade or configure paid billing. Check your own Limits dashboard; exact allowances are subject to change.

6. Verify packages and key configuration:

```powershell
python scripts\smoke_test.py
python scripts\check_groq_connection.py
```

7. Launch:

```powershell
python run.py
```

This serves the API and the prebuilt UI at `http://127.0.0.1:8000` and opens your browser. The browser will request the `APP_USERNAME` and `APP_PASSWORD` values from `.env`. As a shortcut, run `setup_windows.bat` once, edit `.env` with all three values, then launch with `start_app.bat`.

### Frontend development (optional)

The built UI is committed in `frontend/dist`, so Node.js is **not** required to run the app. To change the UI:

```powershell
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api to the backend
npm run build    # rewrites frontend/dist
```

Run the backend alongside with `python run.py --no-browser` (add `--reload` while editing Python).

## Free cloud demo deployment (Render)

This repository includes a Render Blueprint and Dockerfile for a no-card free-tier demo. The service builds the React frontend and serves it from the same FastAPI origin, so the existing relative `/api` requests and SSE stream continue to work without a separate frontend API URL.

1. Push this repository to GitHub (keep it private initially; make it public only after reviewing the source and `.env.example`).
2. In Render, choose **New → Blueprint**, connect the repository, and apply `render.yaml`.
3. Set `APP_USERNAME`, `APP_PASSWORD` and `GROQ_API_KEY` in the Render environment settings. Use a unique strong password; never commit these values. The app uses HTTP Basic Auth to protect the UI and every API route, while `/healthz` remains public for the platform health check.
4. Deploy and verify `/healthz`, `/api/status`, `/api/docs`, document upload, retrieval and SSE chat.

**Free-tier limitations:** Render free web services sleep after 15 minutes without inbound traffic and can take about a minute to wake. Their filesystem is ephemeral: uploaded documents, ChromaDB indexes and SQLite conversations are lost on restart, redeploy or spin-down. The free service also has a 512 MB RAM limit, so the local embedding/reranking stack may exceed available memory during first model load or indexing. This configuration is a demo/test deployment, not reliable persistent hosting. Do not upload confidential documents. For durable use, the project needs external persistent storage and more memory, which may incur cost.

The `/healthz` endpoint is intentionally lightweight and does not load ChromaDB or the ML models. A successful health check proves the web process is reachable; it does **not** prove model initialization, indexing or chat inference works.

## Using the app

1. Drag PDF, DOCX, TXT, MD or CSV files onto the **Knowledge base** box in the sidebar (or click it). Files are indexed immediately; the first run downloads local embedding/reranking models.
3. Ask a question about the uploaded documents; the agent should call `document_search`.
4. Ask a question about recent information; the agent can call `web_search` (DuckDuckGo by default).
5. Paste a public URL and ask the agent to read it; the agent can call `fetch_url`.
6. Ask for background on a topic; the agent can call Wikipedia.
7. Give an RSS/Atom feed URL or a site URL to read its feed or discover sitemap pages.
8. Use the calculator for exact arithmetic.

Each answer shows the tools the agent called, live as they run; expand a step to see a preview of its result. The sliders icon in the header switches search provider and the optional Groq browser search.

## Search providers and cost controls

### Default: DuckDuckGo search

- `SEARCH_PROVIDER=duckduckgo` is the default. `DDGS_REGION=in-en` targets English-language results for India; change it in `.env` if needed.
- Uses the open-source `ddgs` client package; no search API key is required.
- This is not an official guaranteed search API. Requests may be throttled, challenged, or temporarily unavailable. Direct URL, Wikipedia and RSS tools remain separately available.

### Optional: Tavily

- Create a Tavily key only if you want it.
- Set `SEARCH_PROVIDER=tavily`, `TAVILY_ENABLED=true`, and `TAVILY_API_KEY=...` in `.env`.
- Then pick Tavily in the web research settings (sliders icon). It is only called when selected there and a key is present; otherwise the app uses DuckDuckGo.
- Tavily advertises a free-credit tier, but free-credit availability and billing settings are account-specific and may change. Confirm your dashboard and disable paid usage before adding a key. The app never upgrades your account.
- If Tavily returns HTTP 429 or another error, the app falls back to DuckDuckGo, not to another paid provider.

### Optional: Groq built-in browser search

Groq currently documents browser search for GPT-OSS 120B. This app includes a separate opt-in setting, **off by default**. The documented feature is a server-side tool; check current Groq pricing, limits and account terms before enabling it. It is not required for the default search path. To enable by environment, set `GROQ_BROWSER_SEARCH_ENABLED=true`; the checkbox in the web research settings can also enable it for your browser.

### Direct website access

The `fetch_url` tool reads one known public URL. It does not discover unknown websites by itself. The app blocks localhost/private-network URLs and checks redirects to reduce SSRF risk. Static extraction uses HTTPX, Trafilatura and BeautifulSoup. For JavaScript-rendered sites, install the optional browser fallback:

```powershell
pip install -r requirements-browser.txt
playwright install chromium
```

The Playwright fallback blocks local/private URLs and nonessential media requests, but some sites still block automation or require sign-in. Use it only for pages you are allowed to access.

### RSS and sitemaps

RSS/Atom feeds return recent entries for sites that publish feeds. Sitemap discovery lists public URLs declared by a site's sitemap; it does not crawl the entire website automatically.

## Architecture

```text
React web UI (frontend/)  <--SSE-->  FastAPI backend (rag_app/server.py)
   |
   +--> SQLite conversation history
   |
   +--> LangGraph state graph (tool-calling loop)
           |
           +--> Groq GPT-OSS 120B
           |
           +--> document_search
           |      +--> Sentence Transformers embeddings (local CPU)
           |      +--> ChromaDB dense retrieval
           |      +--> BM25 sparse retrieval
           |      +--> Reciprocal Rank Fusion
           |      +--> Cross-Encoder reranking
           |
           +--> web_search (DuckDuckGo default / optional Tavily)
           +--> fetch_url (HTTPX + Trafilatura + BeautifulSoup)
           +--> Wikipedia
           +--> RSS / Atom
           +--> sitemap discovery
           +--> safe calculator
           +--> optional stock lookup
```

## Optional integrations

### Stock lookup

Install only if you need the stock tool:

```powershell
pip install -r requirements-finance.txt
```

`yfinance` is an unofficial interface to Yahoo Finance data; it can be delayed, incomplete, or unavailable. It is not investment advice.

### LangSmith tracing

LangSmith is optional. Add `LANGSMITH_API_KEY=...` and set `LANGSMITH_TRACING=true` in `.env`. Traces may contain prompts, retrieved text, and tool outputs; do not enable tracing for confidential content unless permitted. Check the current plan limits before using it.

### RAGAS evaluation

Copy the example evaluation set and replace the placeholders with questions and reference answers grounded in your own uploaded test corpus:

```powershell
Copy-Item evaluation_questions.example.json evaluation_questions.json
pip install -r requirements-eval.txt
python scripts\evaluate_rag.py
```

Evaluation uses Groq model calls and therefore consumes your Groq API quota. Do not claim any Context Precision/Recall score unless you reproduce it on a documented dataset and preserve the result file. RAGAS APIs and metrics can change across versions; this optional requirements file pins the 0.2 series.

## Tests

```powershell
pip install pytest
pytest -q
```

Tests cover arithmetic safety, text chunking, URL safety, SQLite memory, the HTTP/SSE API (with a stubbed agent) and graph event streaming. They do not test live Groq/search provider connectivity; use `scripts\check_groq_connection.py` for a live Groq connection test.

## Troubleshooting

- **`GROQ_API_KEY is missing`:** copy `.env.example` to `.env`, add the key, and restart the server.
- **Groq `401`:** confirm the key is copied correctly and has not been revoked.
- **Groq `429`:** a rate/token limit has been reached; wait for reset or lower request volume. No paid upgrade is necessary to resume on the free plan.
- **Groq `400` on tool call:** ensure the configured model is `openai/gpt-oss-120b`; check Groq model/tool docs for current compatibility.
- **DuckDuckGo search unavailable:** the public search backend may throttle requests. Try a more specific query, wait, read a direct URL, use Wikipedia/RSS, or explicitly configure Tavily.
- **Tavily quota error:** app falls back to DuckDuckGo; review Tavily account settings before retrying.
- **Model download/CPU memory:** close memory-heavy applications and retry. The models are downloaded once and cached by Sentence Transformers.
- **Chroma index needs rebuilding:** stop the server, back up `data/uploads`, then remove `data/chroma` and re-index original files. This deletes only the vector index.
- **Page says "Frontend not built":** run `cd frontend && npm install && npm run build`.
- **PDF has no extracted text:** it may be scanned/image-only. OCR is not included in this initial version.

## Security and privacy

- Never commit `.env` or expose API keys.
- If a key is exposed, revoke it in its provider console and generate a replacement.
- Documents and SQLite memory are stored locally under `data/` by default.
- When asking Groq, prompts and selected document passages are sent to Groq for model inference. Search queries are sent to the selected search provider. Only enable external integrations for data you are allowed to share.
- Direct URL fetching blocks local/private URLs, but no URL security layer is perfect; use only trusted public URLs.
- Retrieved webpage/document content is treated as data, not instructions.

## Official references

- Groq GPT-OSS 120B model: https://console.groq.com/docs/model/openai/gpt-oss-120b
- Groq browser search for GPT-OSS: https://console.groq.com/docs/tool-use/built-in-tools/browser-search
- Groq rate limits: https://console.groq.com/docs/rate-limits
- LangGraph Python: https://docs.langchain.com/oss/python/langgraph/overview
- Chroma: https://docs.trychroma.com/
- Sentence Transformers: https://www.sbert.net/
- RAGAS: https://docs.ragas.io/
- LangSmith: https://docs.smith.langchain.com/
- Tavily pricing: https://www.tavily.com/pricing
