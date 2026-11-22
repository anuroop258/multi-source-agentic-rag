from __future__ import annotations
from urllib.parse import urlparse, urljoin
import ipaddress
import socket
import xml.etree.ElementTree as ET
import httpx
from bs4 import BeautifulSoup

USER_AGENT = "MultiSourceAgenticRAG/1.0 (local research assistant)"
MAX_PAGE_BYTES = 3_000_000

def validate_public_url(url: str) -> str:
    """Allow public HTTP(S) URLs only. Blocks common SSRF targets and local networks."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only complete http:// or https:// URLs are allowed.")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded credentials are not allowed.")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal", ".test")):
        raise ValueError("Local/private hostnames are not allowed.")
    try:
        ip = ipaddress.ip_address(host)
        if not ip.is_global:
            raise ValueError("Private, loopback, link-local, and reserved IPs are blocked.")
    except ValueError as exc:
        if "blocked" in str(exc):
            raise
        # It was a hostname; resolve it and reject any non-public answer.
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, None)}
        except socket.gaierror as dns_exc:
            raise ValueError(f"Could not resolve hostname: {host}") from dns_exc
        for address in addresses:
            if not ipaddress.ip_address(address).is_global:
                raise ValueError("Hostname resolves to a private or reserved IP address.")
    return url

def fetch_bytes(url: str, max_bytes: int = MAX_PAGE_BYTES) -> tuple[bytes, str, str]:
    current = validate_public_url(url)
    with httpx.Client(timeout=httpx.Timeout(18.0, connect=8.0), follow_redirects=False, headers={"User-Agent": USER_AGENT}) as client:
        for _ in range(4):
            with client.stream("GET", current) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise RuntimeError("Redirect response did not include a Location header.")
                    current = validate_public_url(urljoin(current, location))
                    continue
                response.raise_for_status()
                content_length = response.headers.get("content-length")
                if content_length and content_length.isdigit() and int(content_length) > max_bytes:
                    raise ValueError(f"Page exceeds the {max_bytes // 1_000_000} MB fetch limit.")
                chunks = bytearray()
                for part in response.iter_bytes():
                    chunks.extend(part)
                    if len(chunks) > max_bytes:
                        raise ValueError(f"Page exceeds the {max_bytes // 1_000_000} MB fetch limit.")
                content_type = response.headers.get("content-type", "")
                return bytes(chunks), current, content_type
    raise RuntimeError("Too many redirects while fetching URL.")

def _render_with_playwright(url: str, max_chars: int) -> str:
    """Optional JS-rendered fallback. Install requirements-browser.txt and Chromium to enable."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            def guard_route(route):
                request = route.request
                if request.resource_type in {"image", "media", "font"}:
                    route.abort()
                    return
                request_url = request.url
                if request_url.startswith(("data:", "blob:", "about:")):
                    route.continue_()
                    return
                try:
                    validate_public_url(request_url)
                except ValueError:
                    route.abort()
                    return
                route.continue_()
            page.route("**/*", guard_route)
            page.goto(url, wait_until="domcontentloaded", timeout=18000)
            final_url = validate_public_url(page.url)
            title = page.title() or final_url
            text = page.locator("body").inner_text(timeout=7000)
            if not text.strip():
                return ""
            return f"Title: {title}\nURL: {final_url}\n\n{text[:max_chars]}"
        finally:
            browser.close()

def fetch_webpage(url: str, max_chars: int = 14000) -> str:
    static_result = ""
    try:
        data, final_url, content_type = fetch_bytes(url)
        if not any(kind in content_type.lower() for kind in ("text/html", "application/xhtml", "text/plain", "application/xml")):
            raise ValueError(f"This URL did not return a supported text or HTML page ({content_type or 'unknown content type'}).")
        html = data.decode("utf-8", errors="replace")
        try:
            import trafilatura
            text = trafilatura.extract(html, url=final_url, include_links=True, include_tables=True)
        except ImportError:
            text = ""
        if not text:
            soup = BeautifulSoup(html, "html.parser")
            for node in soup(["script", "style", "noscript", "svg"]):
                node.decompose()
            text = soup.get_text("\n", strip=True)
        title = BeautifulSoup(html, "html.parser").title
        title_text = title.get_text(strip=True) if title else final_url
        if text.strip():
            static_result = f"Title: {title_text}\nURL: {final_url}\n\n{text[:max_chars]}"
    except Exception as static_error:
        static_result = f"Static fetch note: {type(static_error).__name__}: {static_error}"
    if len(static_result) > 550:
        return static_result
    try:
        rendered = _render_with_playwright(url, max_chars)
        if len(rendered) > len(static_result):
            return rendered
    except Exception as browser_error:
        if not static_result:
            static_result = f"JavaScript-rendered fetch unavailable: {type(browser_error).__name__}: {browser_error}"
    if static_result and not static_result.startswith("Static fetch note:"):
        return static_result
    if static_result:
        raise RuntimeError(static_result)
    raise ValueError("No readable page text could be extracted from this URL.")

def search_duckduckgo(query: str, max_results: int = 6) -> str:
    from ddgs import DDGS
    from rag_app.config import DDGS_REGION
    rows = DDGS().text(query, region=DDGS_REGION, max_results=max_results, backend="auto")
    if not rows:
        return "No search results were returned. Try a more specific query or use a direct URL."
    formatted = []
    for i, row in enumerate(rows, start=1):
        title = row.get("title", "Untitled")
        url = row.get("href") or row.get("url") or ""
        body = row.get("body", "")
        formatted.append(f"{i}. {title}\nURL: {url}\nSnippet: {body}")
    return "\n\n".join(formatted)

def search_tavily(query: str, api_key: str, max_results: int = 5) -> str:
    if not api_key:
        raise ValueError("Tavily is selected but TAVILY_API_KEY is not set.")
    response = httpx.post(
        "https://api.tavily.com/search",
        json={"api_key": api_key, "query": query, "search_depth": "basic", "max_results": max_results,
              "include_answer": False, "include_raw_content": False},
        timeout=20.0,
    )
    if response.status_code == 429:
        raise RuntimeError("Tavily free/API quota limit reached (HTTP 429). Switch to DuckDuckGo or wait for reset.")
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("results", [])
    if not rows:
        return "Tavily returned no search results."
    return "\n\n".join(
        f"{i}. {r.get('title', 'Untitled')}\nURL: {r.get('url', '')}\nSnippet: {r.get('content', '')}"
        for i, r in enumerate(rows, start=1)
    )

def web_search(query: str, provider: str = "duckduckgo", tavily_api_key: str = "") -> str:
    if provider == "tavily":
        try:
            return search_tavily(query, tavily_api_key)
        except Exception as exc:
            # Free fallback only; never switch to a paid provider automatically.
            fallback = search_duckduckgo(query)
            return f"Tavily was unavailable ({type(exc).__name__}: {exc}). Fell back to DuckDuckGo (no API key).\n\n{fallback}"
    return search_duckduckgo(query)

def wikipedia_search(query: str) -> str:
    import wikipedia
    titles = wikipedia.search(query, results=4)
    if not titles:
        return "No Wikipedia pages found for that query."
    parts = []
    for title in titles[:3]:
        try:
            page = wikipedia.page(title, auto_suggest=False, redirect=True)
            parts.append(f"{page.title}\nURL: {page.url}\n{page.summary[:1800]}")
        except Exception:
            continue
    return "\n\n".join(parts) if parts else "Wikipedia results could not be opened."

def read_rss_feed(feed_url: str, max_items: int = 8) -> str:
    import feedparser
    data, final_url, _ = fetch_bytes(feed_url, max_bytes=1_500_000)
    parsed = feedparser.parse(data)
    if not parsed.entries:
        return f"No RSS/Atom entries found at {final_url}."
    items = []
    for entry in parsed.entries[:max_items]:
        title = entry.get("title", "Untitled")
        link = entry.get("link", "")
        summary = BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(" ", strip=True)
        items.append(f"{title}\nURL: {link}\nSummary: {summary[:900]}")
    return f"Feed: {final_url}\n\n" + "\n\n".join(items)

def discover_sitemap(site_url: str, max_urls: int = 25) -> str:
    parsed = urlparse(validate_public_url(site_url))
    sitemap_url = site_url if parsed.path.lower().endswith(".xml") else f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
    collected: list[str] = []
    visited_sitemaps: set[str] = set()

    def read_sitemap(target: str, depth: int = 0) -> None:
        if target in visited_sitemaps or len(collected) >= max_urls or depth > 2:
            return
        visited_sitemaps.add(target)
        data, final_url, _ = fetch_bytes(target, max_bytes=2_000_000)
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            raise ValueError(f"The sitemap response at {final_url} was not valid XML.") from exc
        root_name = root.tag.rsplit("}", 1)[-1].lower()
        child_locs = []
        for node in root.iter():
            if node.tag.rsplit("}", 1)[-1].lower() == "loc" and node.text:
                candidate = node.text.strip()
                try:
                    child_locs.append(validate_public_url(candidate))
                except ValueError:
                    continue
        if root_name == "sitemapindex":
            for nested in child_locs[:5]:
                if len(collected) >= max_urls:
                    break
                read_sitemap(nested, depth + 1)
        else:
            for candidate in child_locs:
                if candidate not in collected:
                    collected.append(candidate)
                if len(collected) >= max_urls:
                    break

    read_sitemap(sitemap_url)
    if not collected:
        return (f"No page URLs were found in sitemap {sitemap_url}. It may not exist, may be blocked, "
                "or may use a non-standard location. Try the site's robots.txt or provide a feed URL.")
    return f"Sitemap: {sitemap_url}\nFound {len(collected)} page URL(s):\n" + "\n".join(f"- {u}" for u in collected)

