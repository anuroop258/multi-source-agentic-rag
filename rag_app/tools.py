from __future__ import annotations
import ast
import operator
import json
from typing import Callable
from rag_app.web_sources import web_search, fetch_webpage, wikipedia_search, read_rss_feed, discover_sitemap

_ALLOWED_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow, ast.USub: operator.neg, ast.UAdd: operator.pos,
}

def safe_calculate(expression: str):
    if len(expression) > 180:
        raise ValueError("Expression is too long.")
    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            if abs(node.value) > 1e100:
                raise ValueError("Numeric value is too large.")
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPERATORS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("Exponent magnitude must not exceed 10.")
            result = _ALLOWED_OPERATORS[type(node.op)](left, right)
            if isinstance(result, (int, float)) and abs(result) > 1e100:
                raise ValueError("Result is too large.")
            return result
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[type(node.op)](visit(node.operand))
        raise ValueError("Only basic arithmetic (+, -, *, /, //, %, **) is allowed. No names or function calls.")
    return visit(ast.parse(expression, mode="eval"))

class ToolRegistry:
    def __init__(self, retriever=None, search_provider="duckduckgo", tavily_api_key=""):
        self.retriever = retriever
        self.search_provider = search_provider
        self.tavily_api_key = tavily_api_key
        self.functions: dict[str, Callable] = {
            "web_search": self._web_search,
            "fetch_url": self._fetch_url,
            "wikipedia_search": self._wikipedia,
            "read_rss_feed": self._rss,
            "discover_sitemap": self._sitemap,
            "document_search": self._document_search,
            "calculator": self._calculator,
            "stock_lookup": self._stock_lookup,
        }
        self.schemas = [
            self._schema("web_search", "Search the public web for newly published or relevant pages. Use for discovery when the user has not supplied a URL.", {"query": {"type": "string", "description": "Specific web search query"}}, ["query"]),
            self._schema("fetch_url", "Fetch and extract readable text from one specific public webpage URL. Use when a URL is provided or discovered.", {"url": {"type": "string", "description": "Full http or https URL"}}, ["url"]),
            self._schema("wikipedia_search", "Search Wikipedia for encyclopedia/background information.", {"query": {"type": "string"}}, ["query"]),
            self._schema("read_rss_feed", "Read recent entries from a public RSS or Atom feed URL.", {"feed_url": {"type": "string"}}, ["feed_url"]),
            self._schema("discover_sitemap", "Find public page URLs in a website sitemap. Supply a website root URL or sitemap XML URL.", {"site_url": {"type": "string"}}, ["site_url"]),
            self._schema("document_search", "Search uploaded local documents using dense vector retrieval, BM25 keyword retrieval, RRF fusion, and Cross-Encoder reranking.", {"query": {"type": "string"}}, ["query"]),
            self._schema("calculator", "Evaluate a basic arithmetic expression. Use for exact arithmetic; only numeric arithmetic is permitted.", {"expression": {"type": "string"}}, ["expression"]),
            self._schema("stock_lookup", "Look up a stock ticker's recent daily price history using yfinance if installed. Data may be delayed/incomplete; not investment advice.", {"ticker": {"type": "string"}}, ["ticker"]),
        ]

    @staticmethod
    def _schema(name: str, description: str, properties: dict, required: list[str]) -> dict:
        return {"type": "function", "function": {
            "name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
        }}

    def invoke(self, name: str, arguments: dict) -> str:
        fn = self.functions.get(name)
        if not fn:
            return f"Tool error: unknown tool '{name}'."
        try:
            result = fn(**arguments)
            return str(result)[:16000]
        except Exception as exc:
            return f"Tool error ({type(exc).__name__}): {exc}"

    def _web_search(self, query: str) -> str:
        return web_search(query, self.search_provider, self.tavily_api_key)

    def _fetch_url(self, url: str) -> str:
        return fetch_webpage(url)

    def _wikipedia(self, query: str) -> str:
        return wikipedia_search(query)

    def _rss(self, feed_url: str) -> str:
        return read_rss_feed(feed_url)

    def _sitemap(self, site_url: str) -> str:
        return discover_sitemap(site_url)

    def _document_search(self, query: str) -> str:
        if self.retriever is None or self.retriever.count() == 0:
            return "No documents are indexed. Ask the user to upload and index PDF/DOCX/TXT/MD/CSV files."
        hits = self.retriever.search(query, k=5)
        if not hits:
            return "No relevant passages were found in the indexed documents."
        return "\n\n".join(
            f"[SOURCE: {h['metadata'].get('source', 'unknown')}; PAGE: {h['metadata'].get('page', 0)}; CHUNK: {h['metadata'].get('chunk_index', 0)}]\n{h['text']}"
            for h in hits
        )

    def _calculator(self, expression: str) -> str:
        return str(safe_calculate(expression))

    def _stock_lookup(self, ticker: str) -> str:
        try:
            import yfinance as yf
        except ImportError:
            return "Stock lookup is optional. Install it with: pip install -r requirements-finance.txt"
        symbol = ticker.strip().upper()
        if not symbol or len(symbol) > 16:
            return "Provide a valid stock ticker symbol."
        hist = yf.Ticker(symbol).history(period="5d", interval="1d")
        if hist.empty:
            return f"No recent price rows returned for {symbol}."
        row = hist.iloc[-1]
        return (f"{symbol} latest returned daily bar: date={hist.index[-1]}, close={row.get('Close')}, "
                f"open={row.get('Open')}, volume={row.get('Volume')}. Source: Yahoo Finance via yfinance. "
                "Data may be delayed/incomplete; not investment advice.")
