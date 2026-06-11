"""
HTML-to-Markdown converter.
Supports html2text (primary) and markdownify (alternative).
"""

import html2text
import re

# Try importing markdownify as an alternative backend
try:
    from markdownify import markdownify as mdify
    _has_markdownify = True
except ImportError:
    _has_markdownify = False


def convert_html_to_md(html_content, opts=None):
    """
    Convert an HTML string to Markdown.

    Uses html2text by default. Falls back to markdownify if available
    and specified in opts.

    Args:
        html_content: HTML string or BeautifulSoup element.
        opts: dict of configuration options.
            - backend: 'html2text' (default) or 'markdownify'
            - body_width, ignore_links, ignore_images, etc. (html2text options)

    Returns:
        Markdown string.
    """
    opts = opts or {}
    backend = opts.get("backend", "html2text")

    # Convert BeautifulSoup element to string if needed
    if hasattr(html_content, "prettify"):
        html_str = str(html_content)
    else:
        html_str = html_content

    if backend == "markdownify" and _has_markdownify:
        md = mdify(html_str)
    else:
        md = _html2text_convert(html_str, opts)

    # Post-process: collapse excessive blank lines
    lines = md.split("\n")
    cleaned = []
    blank_count = 0
    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                cleaned.append(line)
        else:
            blank_count = 0
            cleaned.append(line)

    result = "\n".join(cleaned).strip() + "\n"

    # Remove markdown links that point to the same document (#fragments)
    result = re.sub(r'\[([^\]]*)\]\(#[^\)]*\)', r'\1', result)

    return result


def _html2text_convert(html_str, opts):
    """Convert using html2text library."""
    h = html2text.HTML2Text()

    h.body_width = opts.get("body_width", 0)
    h.ignore_links = opts.get("ignore_links", False)
    h.ignore_images = opts.get("ignore_images", False)
    h.skip_internal_links = opts.get("skip_internal_links", False)
    h.ignore_emphasis = opts.get("ignore_emphasis", False)
    h.ignore_tables = opts.get("ignore_tables", False)
    h.unicode_snob = True   # Preserve Unicode characters
    h.bypass_tables = False  # Convert tables, don't bypass

    return h.handle(html_str)
