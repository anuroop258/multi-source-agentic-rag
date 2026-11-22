from __future__ import annotations
from dotenv import load_dotenv
from pathlib import Path
import os
from groq import Groq
load_dotenv(Path(__file__).resolve().parents[1] / ".env")
key = os.getenv("GROQ_API_KEY", "").strip()
if not key:
    raise SystemExit("GROQ_API_KEY is missing from .env")
client = Groq(api_key=key)
response = client.chat.completions.create(
    model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
    messages=[{"role": "user", "content": "Reply with exactly: Groq connection successful."}],
    max_completion_tokens=80,
    reasoning_effort="low",
)
print(response.choices[0].message.content)
