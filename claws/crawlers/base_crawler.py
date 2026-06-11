"""
Abstract base crawler with shared crawl-loop logic.
Concrete crawlers extend this and implement extract_content and discover_links.
"""

import logging
from abc import ABC, abstractmethod

from claws.url_utils import normalize_url, is_skippable, url_to_filepath, extract_base_netloc
from claws.storage import save_markdown

logger = logging.getLogger(__name__)


class BaseCrawler(ABC):
    """
    Abstract base for wiki-specific crawlers.

    Subclasses must implement:
        extract_content(url) -> str          (fetch page, return Markdown)
        discover_links(url, html, base) -> list  (find new URLs to crawl)
    """

    def __init__(self, seed_url, config, session_manager, state, output_root):
        self.seed_url = seed_url
        self.config = config
        self.session = session_manager
        self.state = state
        self.output_root = output_root
        self.domain = extract_base_netloc(seed_url)
        self.base_url = seed_url
        self._cancelled = False

    # ---- Public API ----

    def crawl(self, max_pages=None, depth=0, max_depth=None):
        """
        Start crawling from seed_url.

        Args:
            max_pages: Stop after crawling this many pages (None = unlimited).
            depth: Current recursion depth (used internally).
            max_depth: Maximum crawl depth (None = unlimited).
        """
        pages_crawled = 0
        queue = [(self.seed_url, 0)]  # (url, depth)
        seen_in_queue = {self.seed_url}

        while queue and not self._cancelled:
            url, current_depth = queue.pop(0)

            # Check limits
            if max_pages and pages_crawled >= max_pages:
                logger.info(f"Reached max_pages limit ({max_pages})")
                break
            if max_depth is not None and current_depth > max_depth:
                continue

            # Skip already visited or failed
            if self.state.is_visited(url):
                continue

            logger.info(f"[{pages_crawled + 1}] Crawling (depth {current_depth}): {url}")

            # Mark in progress, fetch, and save
            self.state.mark_in_progress(url)

            try:
                md_content = self.extract_content(url)
            except Exception as e:
                logger.warning(f"Failed to extract content from {url}: {e}")
                self.state.mark_failed(url, str(e))
                self.state.save()
                continue

            if not md_content or not md_content.strip():
                logger.warning(f"Empty content from {url}, skipping")
                self.state.mark_failed(url, "empty content")
                self.state.save()
                continue

            # Save to disk
            filepath = url_to_filepath(url, self.base_url, self.output_root)
            try:
                save_markdown(md_content, filepath)
            except Exception as e:
                logger.error(f"Failed to save {filepath}: {e}")
                self.state.mark_failed(url, f"save error: {e}")
                self.state.save()
                continue

            self.state.mark_visited(url)
            pages_crawled += 1

            # Save state periodically
            if pages_crawled % 5 == 0:
                self.state.save()

            # Discover new links
            try:
                new_urls = self.discover_links(url)
            except Exception as e:
                logger.warning(f"Link discovery failed for {url}: {e}")
                continue

            # Filter and enqueue
            for new_url in new_urls:
                new_url = normalize_url(new_url, base_url=url)
                if self._should_crawl(new_url) and new_url not in seen_in_queue:
                    seen_in_queue.add(new_url)
                    queue.append((new_url, current_depth + 1))

            # Check if queue is complete
            remaining = len(queue)
            if remaining > 0 and remaining % 20 == 0:
                logger.info(f"  Queue: {remaining} pages remaining")

        # Final state save
        self.state.save()

        stats = self.state.stats()
        logger.info(f"Crawl complete for {self.domain}: "
                     f"{stats['visited']} visited, {stats['failed']} failed")
        return stats

    def cancel(self):
        """Signal the crawl loop to stop."""
        self._cancelled = True

    # ---- Subclass interface ----

    @abstractmethod
    def extract_content(self, url):
        """Fetch a page and return its Markdown content."""
        ...

    @abstractmethod
    def discover_links(self, url):
        """Find internal page URLs from a crawled page. Return list of URLs."""
        ...

    # ---- Helpers ----

    def _should_crawl(self, url):
        """Check if a URL should be added to the crawl queue."""
        if is_skippable(url, self.config.get("skip_patterns")):
            return False
        if self.state.is_visited(url):
            return False
        if self.state.has_failed(url):
            return False
        return True
