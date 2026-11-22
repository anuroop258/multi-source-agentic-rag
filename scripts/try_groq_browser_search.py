"""Optional test for Groq-hosted browser_search. Disabled in the main app by default."""
from __future__ import annotations
from dotenv import load_dotenv
from pathlib import Path
import os
from groq import Groq
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
key = os.getenv("GROQ_API_KEY", "").strip()
if not key:
    raise SystemExit("GROQ_API_KEY is missing")
print("This test invokes Groq's server-side browser_search. Check current account usage/billing terms first.")
confirm = input("Type ENABLE to proceed: ").strip()
if confirm != "ENABLE":
    raise SystemExit("Cancelled; no API request sent.")
client = Groq(api_key=key)
resp = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[{"role": "user", "content": "Search the web for one recent official announcement about LangGraph and summarize it with source URLs."}],
    tools=[{"type": "browser_search"}],
    tool_choice="required",
    max_completion_tokens=1500,
    reasoning_effort="low",
)
print(resp.choices[0].message.content)
