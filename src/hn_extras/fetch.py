"""Article fetch tool — reads the full text of any URL.

Designed to complement HN Pulse: when the agent finds a story URL in HN
search results, it can fetch the linked article and include its content
in the answer rather than summarising only the HN metadata.
"""

import logging
from html.parser import HTMLParser
from typing import Annotated

import httpx
from arcade_mcp_server import MCPApp

logger = logging.getLogger(__name__)

# Strip these tags and their content entirely (not just the tags)
_SKIP_TAGS = {"script", "style", "nav", "footer", "header", "aside", "noscript"}

MAX_FETCH_CHARS: int = 4000
_USER_AGENT = "HNPulse-Fetch/1.0 (+https://github.com/AnkamAndy/hn-pulse)"


class _TextExtractor(HTMLParser):
    """Minimal HTML → plain-text extractor using stdlib only."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag.lower() in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._parts.append(text)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _extract_text(html: str) -> str:
    """Extract readable text from an HTML document."""
    parser = _TextExtractor()
    parser.feed(html)
    return parser.get_text()


async def fetch_article(
    url: Annotated[str, "URL of the article to fetch and read"],
    max_chars: Annotated[
        int, "Maximum characters of article text to return (default 4000)"
    ] = MAX_FETCH_CHARS,
) -> dict:  # type: ignore[type-arg]
    """Fetch the full text of a web article by URL.

    Use this when you have a story URL from Hacker News and want to read the
    actual article content rather than just the HN metadata.
    Returns the page title, URL, and a truncated plain-text body.
    """
    max_chars = max(200, min(max_chars, 8000))
    logger.debug("fetching article: %s (max_chars=%d)", url, max_chars)

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            r = await client.get(url)
            r.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("fetch failed for %s: %s", url, exc)
        return {"error": f"Could not fetch URL: {exc}", "url": url}

    content_type = r.headers.get("content-type", "")
    text = _extract_text(r.text) if "html" in content_type else r.text

    truncated = len(text) > max_chars
    body = text[:max_chars] + ("…[truncated]" if truncated else "")

    return {
        "url": str(r.url),
        "status_code": r.status_code,
        "content_type": content_type,
        "body": body,
        "truncated": truncated,
    }


# ── MCP Server ───────────────────────────────────────────────────────────────

app = MCPApp(
    name="hn_fetch",
    version="1.0.0",
    instructions="Fetches the full text of web articles by URL.",
    log_level="INFO",
)
app.add_tool(fetch_article)  # type: ignore[arg-type]
