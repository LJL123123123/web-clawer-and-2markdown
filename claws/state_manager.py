"""
JSON-based crawl state persistence for resume capability.
Tracks visited URLs, failed URLs, and in-progress state per wiki.
"""

import json
import os
import time


class CrawlState:
    """
    Manages crawl progress for a single wiki.
    Saves to `_state.json` inside the wiki's output directory.
    """

    def __init__(self, state_file_path):
        self._path = state_file_path
        self.visited_urls = set()
        self.failed_urls = {}    # url -> reason string
        self.in_progress = None
        self.last_updated = None
        self._load()

    # ---- Persistence ----

    def _load(self):
        """Load state from disk if it exists."""
        if os.path.exists(self._path):
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.visited_urls = set(data.get("visited_urls", []))
                self.failed_urls = data.get("failed_urls", {})
                self.in_progress = data.get("in_progress")
                self.last_updated = data.get("last_updated")
            except (json.JSONDecodeError, IOError):
                # Corrupted state — start fresh
                self.visited_urls = set()
                self.failed_urls = {}
                self.in_progress = None

    def save(self):
        """Persist current state to disk."""
        data = {
            "visited_urls": sorted(self.visited_urls),
            "failed_urls": self.failed_urls,
            "in_progress": self.in_progress,
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ---- State mutations ----

    def mark_visited(self, url):
        """Record a URL as successfully crawled."""
        self.visited_urls.add(url)
        self.in_progress = None

    def mark_failed(self, url, reason):
        """Record a URL that failed to crawl."""
        self.failed_urls[url] = reason
        self.in_progress = None

    def mark_in_progress(self, url):
        """Record the URL currently being crawled."""
        self.in_progress = url

    # ---- Queries ----

    def is_visited(self, url):
        """Check if a URL has already been successfully crawled."""
        return url in self.visited_urls

    def has_failed(self, url):
        """Check if a URL previously failed."""
        return url in self.failed_urls

    def stats(self):
        """Return a summary dict of crawl progress."""
        return {
            "visited": len(self.visited_urls),
            "failed": len(self.failed_urls),
            "in_progress": self.in_progress,
        }
