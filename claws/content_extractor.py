"""
Content extraction using readability-lxml (Mozilla's Readability algorithm).
This is the industry-standard approach used by Firefox Reader View and
virtually all browser extensions for web-to-Markdown conversion.

Pipeline: Raw HTML → readability → clean HTML → Markdown
"""

import chardet
from readability import Document


def extract_content(html, url="", content_selectors=None):
    """
    Extract the main content from an HTML page using readability-lxml.

    Falls back to CSS selectors if readability produces no useful content.

    Args:
        html: Raw HTML string (must be properly decoded).
        url: Source URL (helps readability resolve relative links).
        content_selectors: Optional list of CSS selectors as fallback.

    Returns:
        (title, content_html) tuple where content_html is a cleaned HTML string.
    """
    if not html or not html.strip():
        return ("Untitled", "")

    doc = Document(html, url=url)

    # Readability extraction
    title = doc.title() or "Untitled"
    summary_html = doc.summary()

    # Check if readability produced meaningful content
    if summary_html and _has_meaningful_content(summary_html):
        return (title, summary_html)

    # Fallback: try CSS selectors
    if content_selectors:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem and _has_meaningful_content(elem.get_text()):
                return (title, str(elem))

    # Ultimate fallback: return the body
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")
    body = soup.find("body") or soup
    return (title, str(body))


def decode_html(response_or_bytes, fallback_encodings=None):
    """
    Decode raw HTTP response bytes to a Unicode string with proper charset detection.

    Uses chardet FIRST (most accurate), then apparent_encoding, then fallbacks.
    Avoids requests.Response.encoding which often defaults to ISO-8859-1
    and silently corrupts non-Latin text.

    Args:
        response_or_bytes: Either a requests.Response or raw bytes.
        fallback_encodings: Encodings to try if detection fails.

    Returns:
        Properly decoded Unicode string.
    """
    if hasattr(response_or_bytes, 'content'):
        raw = response_or_bytes.content
        resp_obj = response_or_bytes
    else:
        raw = response_or_bytes
        resp_obj = None

    if not raw:
        return ""

    # 1. Try chardet detection FIRST (most accurate for Chinese/Japanese/etc.)
    detected = chardet.detect(raw)
    if detected and detected.get('encoding'):
        enc = detected['encoding']
        try:
            return raw.decode(enc, errors='strict')
        except (UnicodeDecodeError, LookupError):
            pass

    # 2. Try requests' apparent_encoding (also uses chardet internally)
    if resp_obj and hasattr(resp_obj, 'apparent_encoding') and resp_obj.apparent_encoding:
        try:
            return raw.decode(resp_obj.apparent_encoding, errors='strict')
        except (UnicodeDecodeError, LookupError):
            pass

    # 3. Try fallback encodings
    for enc in (fallback_encodings or ["utf-8", "gb18030", "gbk", "big5", "shift_jis", "latin-1"]):
        try:
            return raw.decode(enc, errors='strict')
        except (UnicodeDecodeError, LookupError):
            continue

    # 4. Last resort: decode UTF-8 with replacement chars
    return raw.decode("utf-8", errors="replace")


def _has_meaningful_content(text):
    """Check if extracted text has enough meaningful content."""
    if not text:
        return False
    # Strip HTML tags for analysis
    import re
    plain = re.sub(r'<[^>]+>', '', str(text)).strip()
    # Need at least 100 non-whitespace characters
    return len(plain) > 100
