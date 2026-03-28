"""Unit tests for the HN Extras fetch_article tool."""

import pytest

from hn_extras.fetch import _extract_text, fetch_article

FETCH_URL = "https://example.com/article"


@pytest.mark.asyncio
async def test_fetch_article_returns_body(httpx_mock):
    """Successful HTML fetch returns title, url, and plain-text body."""
    httpx_mock.add_response(
        url=FETCH_URL,
        status_code=200,
        content=b"<html><body><h1>Hello</h1><p>World content here.</p></body></html>",
        headers={"content-type": "text/html"},
    )

    result = await fetch_article(url=FETCH_URL)

    assert result["url"] == FETCH_URL
    assert result["status_code"] == 200
    assert "Hello" in result["body"]
    assert "World content here" in result["body"]
    assert result["truncated"] is False


@pytest.mark.asyncio
async def test_fetch_article_strips_script_and_style(httpx_mock):
    """Script, style, nav, footer content must be stripped from output."""
    html = b"""
    <html>
      <head><style>body { color: red; }</style></head>
      <body>
        <nav>Site navigation links</nav>
        <main><p>The real article content.</p></main>
        <script>alert('ads')</script>
        <footer>Copyright 2025</footer>
      </body>
    </html>
    """
    httpx_mock.add_response(
        url=FETCH_URL, status_code=200, content=html,
        headers={"content-type": "text/html"},
    )

    result = await fetch_article(url=FETCH_URL)

    assert "real article content" in result["body"]
    assert "alert" not in result["body"]
    assert "color: red" not in result["body"]
    assert "Site navigation links" not in result["body"]
    assert "Copyright" not in result["body"]


@pytest.mark.asyncio
async def test_fetch_article_truncates_at_max_chars(httpx_mock):
    """Body is capped at max_chars and truncated flag is set."""
    long_text = "word " * 2000   # ~10000 chars
    html = f"<html><body><p>{long_text}</p></body></html>".encode()
    httpx_mock.add_response(
        url=FETCH_URL, status_code=200, content=html,
        headers={"content-type": "text/html"},
    )

    result = await fetch_article(url=FETCH_URL, max_chars=500)

    assert len(result["body"]) <= 520  # 500 + "[truncated]" suffix
    assert result["truncated"] is True
    assert "truncated" in result["body"]


@pytest.mark.asyncio
async def test_fetch_article_returns_error_on_http_failure(httpx_mock):
    """HTTP error response returns error dict, does not raise."""
    httpx_mock.add_response(url=FETCH_URL, status_code=404, content=b"Not found")

    result = await fetch_article(url=FETCH_URL)

    assert "error" in result
    assert result["url"] == FETCH_URL


@pytest.mark.asyncio
async def test_fetch_article_handles_plain_text(httpx_mock):
    """Non-HTML responses (plain text, JSON) are returned as-is."""
    httpx_mock.add_response(
        url=FETCH_URL,
        status_code=200,
        content=b'{"key": "value"}',
        headers={"content-type": "application/json"},
    )

    result = await fetch_article(url=FETCH_URL)

    assert "key" in result["body"]


def test_extract_text_from_simple_html():
    """_extract_text returns readable text from basic HTML."""
    html = "<html><body><h1>Title</h1><p>Some text.</p></body></html>"
    text = _extract_text(html)
    assert "Title" in text
    assert "Some text" in text


def test_extract_text_skips_nested_script():
    """_extract_text handles nested skip-tag content."""
    html = "<div><p>Good</p><script>bad()</script><p>Also good</p></div>"
    text = _extract_text(html)
    assert "Good" in text
    assert "Also good" in text
    assert "bad()" not in text
