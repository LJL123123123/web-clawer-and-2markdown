"""
URL normalization, validation, and path-to-filename conversion utilities.
"""

import re
import os
from urllib.parse import urljoin, urlparse, urlunparse, unquote


# Characters unsafe on Windows filesystems (NTFS)
_WINDOWS_UNSAFE = re.compile(r'[\\/:*?"<>|]')

# Max filename segment length (NTFS max is 255, leave headroom)
_MAX_FILENAME_SEGMENT = 200


def normalize_url(url, base_url=None):
    """
    Normalize a URL: resolve relative to base, strip fragment,
    normalize trailing slash, decode percent-encoding for display.
    """
    if base_url:
        url = urljoin(base_url, url)

    parsed = urlparse(url)

    # Rebuild without fragment
    clean = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path.rstrip("/") or "/",
        parsed.params,
        parsed.query,
        "",  # drop fragment
    ))
    return clean


def is_internal(url, base_netloc):
    """Check if a URL belongs to the same domain as base_netloc."""
    parsed = urlparse(url)
    return parsed.netloc == base_netloc or not parsed.netloc


def is_skippable(url, skip_patterns=None):
    """
    Check if a URL should be skipped based on common patterns
    (mailto, javascript, media files, PDFs, etc.).
    """
    if not url:
        return True

    url_lower = url.lower()

    # Always skip these
    if any(url_lower.startswith(p) for p in ("javascript:", "mailto:", "tel:", "#")):
        return True

    if skip_patterns:
        for pat in skip_patterns:
            if pat in url_lower:
                return True

    return False


def url_to_filepath(url, base_url, output_root):
    """
    Convert a URL to a filesystem-safe file path under output_root.

    The path structure mirrors the URL path components.
    Index pages (root path or trailing slash) get 'index.md'.
    All other pages get their path component(s) as directory + filename.

    Examples:
        https://deepwiki.com/a/b/1-overview  -> output_root/a/b/1-overview.md
        https://example.com/                 -> output_root/index.md
        https://example.com/foo/bar          -> output_root/foo/bar.md
    """
    parsed = urlparse(url)
    path = parsed.path.strip("/")

    if not path:
        return os.path.join(output_root, "index.md")

    # Split into segments, sanitize each
    segments = path.split("/")
    safe_segments = [_sanitize_segment(s) for s in segments if s]

    if not safe_segments:
        return os.path.join(output_root, "index.md")

    # Build path: all but last segment are directories, last is the file
    *dirs, filename = safe_segments

    # Ensure filename has .md extension
    if not filename.endswith(".md"):
        filename = _sanitize_segment(filename) + ".md"
    else:
        filename = _sanitize_segment(filename)

    # For .htm/.html URLs, replace extension with .md
    filename = re.sub(r'\.html?(\.md)?$', '.md', filename)

    full_dir = os.path.join(output_root, *dirs) if dirs else output_root
    return os.path.join(full_dir, filename)


def _sanitize_segment(segment):
    """Replace Windows-unsafe characters and truncate long names."""
    # Decode percent-encoding
    try:
        segment = unquote(segment)
    except Exception:
        pass
    # Replace unsafe chars with underscore
    segment = _WINDOWS_UNSAFE.sub("_", segment)
    # Truncate if too long
    if len(segment) > _MAX_FILENAME_SEGMENT:
        segment = segment[:_MAX_FILENAME_SEGMENT]
    # Strip leading/trailing whitespace and dots
    segment = segment.strip(" .")
    return segment or "page"


def extract_base_netloc(url):
    """Get the netloc (domain) from a URL."""
    return urlparse(url).netloc
