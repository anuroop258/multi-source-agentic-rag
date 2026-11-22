# Cloudflare Pages deployment guide

This guide follows the repository-root Pages + Pages Functions + D1 pattern used in the CareerAgent Cloud Deployment Playbook. The local Windows app remains FastAPI + LangGraph + ChromaDB. The hosted Pages adapter is JavaScript and does not replace the local implementation.

## 1. What will run on Cloudflare

```text
Browser
  |
  v
Cloudflare Pages (React/Vite static assets + Basic Auth)
  |
  +-- Pages Functions: /api/*
          |
          +-- D1: conversations + document metadata
          |
          +-- Cloudflare AI Search REST API: document storage,
          |   hybrid semantic/keyword retrieval and reranking
          |
          +-- Groq API: answer generation and tool calling
          +-- DuckDuckGo / optional Tavily / public source APIs
```

There is no separate FastAPI server, Python Worker, Render service, or always-on VM in this Pages deployment. The original local FastAPI/LangGraph/ChromaDB app remains unchanged.

## 2. Before you start

You need a Cloudflare account, the GitHub repository `anuroop258/multi-source-agentic-rag`, a Groq API key, Git, Node.js/npm and the Wrangler CLI (use it through `npx wrangler`). Do not commit API keys, `.env`, local databases, uploads or model cache files.

Open PowerShell in the local clone:

```powershell
cd "$HOME\GitHub\multi-source-agentic-rag"
git status --short
git branch --show-current
git log -1 --oneline
```

The working tree should be clean and the branch should be `main` before you begin the deployment setup.

## 3. Verify the frontend locally

```powershell
cd frontend
npm ci
npm run build
cd ..
```

The Pages build command uses the same clean install and production build. A successful local Vite build is one gate only; it does not verify Pages Functions, D1 or AI Search.

## 4. Create the D1 database

Authenticate Wrangler:

```powershell
npx wrangler login
```

Create the database:

```powershell
npx wrangler d1 create multi-source-agentic-rag-db
```

Keep the returned database name and ID. You will bind it to the Pages project in Step 6.

## 5. Create a Cloudflare AI Search instance

In the Cloudflare dashboard, open **AI → AI Search** and create one instance with this exact ID:

```text
multi-source-agentic-rag-kb
```

Use the default `default` namespace and leave hybrid vector + keyword retrieval enabled. The Pages API requests reranking on document searches.

Create a custom Cloudflare API token under **My Profile → API Tokens**. Grant only these account permissions:

- AI Search:Edit
- AI Search:Run

Copy the token once and keep it private. The application calls the AI Search REST API from a Pages Function; the browser never receives this token.

Find your Cloudflare Account ID in the dashboard. You will enter it as a Pages secret.

Official references:
- https://developers.cloudflare.com/ai-search/get-started/api/
- https://developers.cloudflare.com/ai-search/api/items/rest-api/
- https://developers.cloudflare.com/ai-search/api/search/rest-api/

## 6. Create the Pages project and connect GitHub

In **Cloudflare Dashboard → Workers & Pages → Create application → Pages → Connect to Git**, choose:

```text
Repository: anuroop258/multi-source-agentic-rag
Production branch: main
```

Set the build configuration exactly as follows:

| Setting | Value |
|---|---|
| Project name | `multi-source-agentic-rag` |
| Production branch | `main` |
| Root directory | Leave blank (repository root) |
| Build command | `cd frontend && npm ci && npm run build` |
| Build output directory | `frontend/dist` |

Do not set the root directory to `frontend`. The top-level `functions/` directory must remain discoverable by Pages, as described in the CareerAgent playbook.

Create the Pages project. The first deployment may fail until the D1 binding and secrets are configured; that is expected at this stage.

## 7. Bind D1 to Pages

Open the Pages project → **Settings → Bindings → Add → D1 database**.

Set:

```text
Variable name: DB
D1 database: multi-source-agentic-rag-db
```

Save the binding. The binding name is case-sensitive and must be exactly `DB`.

Apply the schema from the repository root:

```powershell
npx wrangler d1 execute multi-source-agentic-rag-db --remote --file=cloudflare/migrations/0001_rag_schema.sql
```

Verify the two application tables exist:

```powershell
npx wrangler d1 execute multi-source-agentic-rag-db --remote --command="SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
```

Expected application tables include `documents` and `messages` (plus SQLite's internal sequence table).

## 8. Add Pages variables and secrets

Open Pages project → **Settings → Variables and Secrets**. Add these to the **Production** environment.

| Name | Type | Value |
|---|---|---|
| `APP_USERNAME` | Secret | Your chosen login name |
| `APP_PASSWORD` | Secret | A long, unique password (20+ characters recommended) |
| `GROQ_API_KEY` | Secret | Your Groq API key |
| `CLOUDFLARE_ACCOUNT_ID` | Secret | Your Cloudflare account ID |
| `CLOUDFLARE_AI_SEARCH_TOKEN` | Secret | The AI Search:Edit + AI Search:Run token |
| `AI_SEARCH_INSTANCE_ID` | Variable | `multi-source-agentic-rag-kb` |
| `GROQ_MODEL` | Variable | `openai/gpt-oss-120b` |
| `TAVILY_API_KEY` | Secret (optional) | Only if you choose Tavily search |

Do not use `VITE_*` names for secrets. Vite variables are bundled into browser JavaScript and are public. Do not put secret values in `wrangler.jsonc`, GitHub, this guide or chat.

Save the values and trigger a new deployment so the runtime receives the D1 binding and secrets.

## 9. Verify the live deployment

Use the `*.pages.dev` URL shown on the Pages project. The `/healthz` endpoint is intentionally public and checks D1 only. The rest of the site and API require the Basic Auth username/password.

From PowerShell, set your URL and credentials:

```powershell
$base = "https://YOUR-PROJECT.pages.dev"
$username = Read-Host "Pages username"
$securePassword = Read-Host "Pages password" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try { $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
$basic = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("$username`:$password"))
$headers = @{ Authorization = "Basic $basic" }
```

Health and read APIs:

```powershell
Invoke-RestMethod "$base/healthz"
Invoke-RestMethod "$base/api/status" -Headers $headers | ConvertTo-Json -Depth 6
Invoke-RestMethod "$base/api/documents" -Headers $headers | ConvertTo-Json -Depth 6
Invoke-RestMethod "$base/api/conversations" -Headers $headers | ConvertTo-Json -Depth 6
```

Expected gates:

- `/healthz` returns HTTP 200 with `database_configured: true`.
- `/api/status` returns JSON, `groq_configured: true` and `cloud_storage.configured: true`.
- `/api/documents` and `/api/conversations` return JSON, not the SPA's `index.html`.
- An unauthenticated request to `/api/status` returns HTTP 401.

Test one document upload (a small PDF/TXT/DOCX/CSV file under 4 MB):

```powershell
$pair = "$username`:$password"
curl.exe -u $pair -F "files=@C:\path\to\small-sample.pdf" "$base/api/documents"
Invoke-RestMethod "$base/api/documents" -Headers $headers | ConvertTo-Json -Depth 6
```

Wait until the document reports `index_status: completed`, then open the site and ask a question whose answer is clearly contained in that sample file. Confirm the response's tool trace includes `document_search` and its answer cites the uploaded file. Also test a web-search question and an ordinary follow-up chat to verify the D1 conversation persists after refresh.

Finally, check Pages → Deployments and confirm the latest deployment's source commit matches the commit you just pushed and its status is **Success**. A successful build alone is not full RAG verification.

## 10. Supported cloud behavior and limitations

The cloud adapter is intentionally narrower than the local app:

- Cloud document retrieval uses AI Search hybrid retrieval and optional reranking, not local ChromaDB + Sentence Transformers + BM25 + CrossEncoder.
- The hosted cloud chat has a bounded Groq tool loop. The local LangGraph graph and optional Yahoo Finance stock lookup are not deployed here.
- Supported cloud uploads are PDF, DOCX, TXT, Markdown, RST and CSV. Markdown is sent as plain text with the original file name retained as metadata. This deployment caps every file at 4 MB, even though AI Search allows larger plain-text files.
- The frontend/API uses one shared Basic Auth login. This is suitable for a personal demo, not multi-user account management or fine-grained per-user access.
- The `/healthz` route is public and exposes only basic service/database health. All other pages and API routes are protected by Basic Auth.

## 11. Free-tier and billing warning

This is a free-tier target, not an unlimited-free guarantee. Cloudflare's current Workers Free limit is 100,000 requests/day and 10 ms CPU per request. Pages Functions run on the Workers platform, so avoid CPU-heavy local embedding/model work in Functions; this cloud adapter deliberately delegates embedding, vector/keyword retrieval and reranking to AI Search. Groq usage remains subject to your Groq account's own plan and limits.

As of November 22, 2026, Cloudflare AI Search lists these monthly included amounts per account: 5 million ingestion tokens, 10 GB-month storage, 1,000 semantic queries and 1,000 full-text queries. AI Search billing begins December 1, 2026. Published overage rates are $0.75 per million base ingestion tokens, $2.00 per GB-month storage, $0.75 per 1,000 semantic/vector/hybrid queries and $0.10 per 1,000 full-text queries. Workers AI embeddings and reranking are included in AI Search usage; Groq and optional Tavily are billed/limited separately by those providers. Review the current official page and configure spending controls before adding large document collections or sharing the site widely:

- https://developers.cloudflare.com/workers/platform/limits/
- https://developers.cloudflare.com/ai-search/platform/limits-pricing/

Do not enable paid Groq/Tavily options unless you have checked the provider's current plan and limits.

## 12. Troubleshooting

| Symptom | First check |
|---|---|
| Pages build fails | `cd frontend && npm ci && npm run build` locally; inspect the exact Cloudflare build log. |
| `/api/*` returns HTML or 404 | Keep Pages root at repository root; verify top-level `functions/` was deployed. |
| `/healthz` says D1 not configured | Check Pages Settings → Bindings; binding must be named `DB`; redeploy. |
| `/api/status` says AI Search not configured | Check `CLOUDFLARE_ACCOUNT_ID`, `AI_SEARCH_INSTANCE_ID` and `CLOUDFLARE_AI_SEARCH_TOKEN` in Production. |
| Upload is rejected | Check file extension, filename length and the 4 MB application limit. |
| Index stays queued/running | Inspect the AI Search instance Items page and indexing logs. |
| Chat says Groq key missing or Groq HTTP error | Verify `GROQ_API_KEY`, model name and account quota. |
| `/api/status` returns 401 | Expected without the Pages Basic Auth credentials; do not remove authentication to make the test pass. |
| Worker CPU limit error | Inspect Pages Function logs; AI Search calls should handle retrieval remotely, not local model inference. |

## 13. Rollback

Cloudflare Pages → Deployments lets you roll back to a previously successful deployment. Keep the last known-good Git commit and do not overwrite the original local FastAPI/LangGraph project while diagnosing the cloud adapter.
