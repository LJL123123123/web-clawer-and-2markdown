"""
MediaWiki crawler — auto-detects MediaWiki sites and uses the action=query API.

Works for: Wikipedia, Moegirlpedia, Fandom/Wikia, any MediaWiki site with
an accessible /api.php endpoint.
"""

import logging
import random
import time
from urllib.parse import urlparse, unquote

import requests as req

from claws.crawlers.base_crawler import BaseCrawler
from claws.html_to_md import convert_html_to_md
from claws.url_utils import url_to_filepath
from claws.storage import save_markdown

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
]

# Namespace prefixes to skip
_DEFAULT_SKIP_NS = [
    "Category:", "Template:", "File:", "Help:",
    "MediaWiki:", "Special:", "User:", "Talk:",
    "User talk:", "Template talk:", "Category talk:",
    "File talk:", "MediaWiki talk:", "Help talk:",
    "Module:", "Module talk:", "Gadget:", "Gadget talk:",
    "TimedText:", "TimedText talk:", "Topic:", "Project:",
    "Wikipedia:", "WP:", "Portal:", "Draft:", "Draft talk:",
]


class MediaWikiCrawler(BaseCrawler):
    """
    Generic MediaWiki crawler.

    Uses action=query API for:
    - Content: prop=extracts (HTML format)
    - Link discovery: prop=links (main namespace only)

    Automatically detects and respects namespace filtering.
    Falls back to HTML scraping if API is restricted.
    """

    def __init__(self, seed_url, config, session_manager, state, output_root):
        super().__init__(seed_url, config, session_manager, state, output_root)

        self._action_api = config.get("action_api") or self._detect_api(seed_url)
        self._delay = config.get("delay", 1.5)
        self._jitter = config.get("jitter", 0.5)
        self._last_request = 0.0
        self._skip_ns = config.get("skip_namespaces", _DEFAULT_SKIP_NS)
        self._links_limit = config.get("links_limit", 500)

        # Extract initial page title from seed URL
        parsed = urlparse(seed_url)
        path = unquote(parsed.path.strip("/"))  # URL-decode (e.g. %E6%98%9F → 星)
        # Remove /wiki/ or /w/ prefix if present (common MediaWiki patterns)
        for prefix in ("wiki/", "w/", "zh/wiki/", "zh-cn/", "zh-tw/"):
            if path.startswith(prefix):
                path = path[len(prefix):]
                break
        self._page_title = path.split("/")[-1] if path else "Main_Page"

        if not self._page_title:
            self._page_title = "Main_Page"

        # Try to get page title from index.php?title= format
        from urllib.parse import parse_qs
        query = parse_qs(parsed.query)
        if "title" in query:
            self._page_title = unquote(query["title"][0])

        self._visited_titles = set()
        self._title_queue = [self._page_title]

        logger.info(f"MediaWiki detected: {self.domain}, starting from '{self._page_title}'")

    @staticmethod
    def _detect_api(base_url):
        """Detect the MediaWiki API endpoint from a base URL."""
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        # Extract language/prefix path from URL (e.g., /zh/wiki/Page → /zh/api.php)
        path = parsed.path
        api_paths = ["/api.php", "/w/api.php"]
        # If URL has a language prefix before /wiki/, also try that prefix
        # e.g., yugioh.fandom.com/zh/wiki/Page → /zh/api.php
        if "/wiki/" in path:
            prefix = path.split("/wiki/")[0].lstrip("/")
            if prefix:
                api_paths.insert(0, f"/{prefix}/api.php")
        for api_path in api_paths:
            api_url = base + api_path
            try:
                resp = req.get(
                    api_url,
                    params={"action": "query", "meta": "siteinfo", "format": "json"},
                    headers={"User-Agent": random.choice(_USER_AGENTS)},
                    timeout=10,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if "query" in data and "general" in data.get("query", {}):
                        return api_url
            except Exception:
                continue
        return base + "/api.php"  # default fallback

    @staticmethod
    def detect(base_url):
        """
        Check if a URL points to a MediaWiki site.
        Returns the api.php URL if detected, None otherwise.
        """
        api_url = MediaWikiCrawler._detect_api(base_url)
        try:
            resp = req.get(
                api_url,
                params={"action": "query", "meta": "siteinfo", "format": "json"},
                headers={"User-Agent": random.choice(_USER_AGENTS)},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                if "query" in data and "general" in data.get("query", {}):
                    return api_url
        except Exception:
            pass
        return None

    # ---- API helpers ----

    def _rate_wait(self):
        now = time.time()
        elapsed = now - self._last_request
        delay = self._delay + random.uniform(0, self._jitter)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request = time.time()

    def _api_get(self, params, retries=3):
        """Make a rate-limited GET to the action API with retry and 429 handling."""
        self._rate_wait()
        headers = {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "application/json",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        last_err = None
        for attempt in range(retries + 1):
            try:
                resp = req.get(self._action_api, params=params, headers=headers, timeout=30)
                if resp.status_code == 429:
                    # Rate limited — honor Retry-After header
                    retry_after = resp.headers.get("Retry-After", "5")
                    try:
                        wait_s = int(retry_after)
                    except ValueError:
                        wait_s = 5
                    logger.debug(f"429 rate limited, waiting {wait_s}s")
                    time.sleep(wait_s + random.uniform(0, 2))
                    continue
                resp.raise_for_status()
                return resp.json()
            except (req.ConnectionError, req.Timeout,
                    ConnectionResetError, TimeoutError) as e:
                last_err = e
                if attempt < retries:
                    time.sleep(2 * (attempt + 1))
        raise last_err

    # ---- Crawl loop (title-driven) ----

    def crawl(self, max_pages=None, depth=0, max_depth=None):
        """Crawl via API, driven by page titles."""
        pages_crawled = 0
        seen_in_queue = {self._page_title}

        while self._title_queue and not self._cancelled:
            if max_pages and pages_crawled >= max_pages:
                logger.info(f"Reached max_pages limit ({max_pages})")
                break

            title = self._title_queue.pop(0)

            if title in self._visited_titles:
                continue

            page_url = f"https://{self.domain}/wiki/{title.replace(' ', '_')}"

            if self.state.is_visited(page_url):
                self._visited_titles.add(title)
                continue

            logger.info(f"[{pages_crawled + 1}] Crawling: {title}")

            self.state.mark_in_progress(page_url)

            try:
                md_content = self._extract_by_title(title)
            except Exception as e:
                logger.warning(f"Failed to extract '{title}': {e}")
                self.state.mark_failed(page_url, str(e))
                self.state.save()
                continue

            if not md_content or not md_content.strip():
                logger.warning(f"Empty content for '{title}', skipping")
                self.state.mark_failed(page_url, "empty content")
                self.state.save()
                continue

            filepath = self._title_to_filepath(title)
            try:
                save_markdown(md_content, filepath)
            except Exception as e:
                logger.error(f"Failed to save {filepath}: {e}")
                self.state.mark_failed(page_url, f"save error: {e}")
                self.state.save()
                continue

            self.state.mark_visited(page_url)
            self._visited_titles.add(title)
            pages_crawled += 1

            if pages_crawled % 5 == 0:
                self.state.save()

            try:
                new_titles = self._discover_by_title(title)
            except Exception as e:
                logger.warning(f"Link discovery failed for '{title}': {e}")
                continue

            for nt in new_titles:
                if nt not in seen_in_queue and nt not in self._visited_titles:
                    seen_in_queue.add(nt)
                    self._title_queue.append(nt)

        self.state.save()
        stats = self.state.stats()
        logger.info(f"Crawl complete for {self.domain}: "
                     f"{stats['visited']} visited, {stats['failed']} failed")
        return stats

    # ---- Content extraction ----

    def _extract_by_title(self, title):
        """Fetch page content — extracts first, fall back to wikitext."""
        # 1. Try extracts API (fast, clean HTML)
        params = {
            "action": "query",
            "prop": "extracts",
            "titles": title,
            "explaintext": 0,
            "exintro": 0,
            "format": "json",
        }
        try:
            data = self._api_get(params)
            pages = data.get("query", {}).get("pages", {})
            for _pid, page_data in pages.items():
                if "missing" in page_data:
                    return ""
                html = page_data.get("extract", "")
                if html:
                    md = convert_html_to_md(html, self.config.get("html2text_opts", {}))
                    return f"# {title}\n\n{md}"
        except Exception as e:
            logger.debug(f"Extracts failed for '{title}': {e}")

        # 2. Fallback: get wikitext via revisions
        try:
            from claws.wikitext_to_md import convert_wikitext_to_md
            params2 = {
                "action": "query",
                "prop": "revisions",
                "titles": title,
                "rvprop": "content",
                "rvslots": "main",
                "format": "json",
            }
            data2 = self._api_get(params2)
            pages2 = data2.get("query", {}).get("pages", {})
            for _pid, page_data in pages2.items():
                if "missing" in page_data:
                    return ""
                revisions = page_data.get("revisions", [])
                if revisions:
                    wikitext = revisions[0].get("slots", {}).get("main", {}).get("*", "")
                    if not wikitext:
                        wikitext = revisions[0].get("*", "")
                    if wikitext:
                        return convert_wikitext_to_md(wikitext, title=title)
        except Exception as e:
            logger.warning(f"Wikitext fallback also failed for '{title}': {e}")

        return ""

    # ---- Link discovery ----

    def _discover_by_title(self, title):
        """Use action=query&prop=links to find linked articles."""
        titles = []
        plcontinue = None

        while True:
            params = {
                "action": "query",
                "prop": "links",
                "titles": title,
                "plnamespace": 0,
                "pllimit": self._links_limit,
                "format": "json",
            }
            if plcontinue:
                params["plcontinue"] = plcontinue

            try:
                data = self._api_get(params)
            except Exception as e:
                logger.warning(f"Link query failed for '{title}': {e}")
                break

            pages = data.get("query", {}).get("pages", {})
            for _pid, page_data in pages.items():
                links = page_data.get("links", [])
                for link in links:
                    lt = link.get("title", "")
                    if self._valid_title(lt):
                        titles.append(lt)

            plcontinue = data.get("continue", {}).get("plcontinue")
            if not plcontinue:
                break

        return titles

    def _valid_title(self, title):
        """Check if a page title is a valid crawl target."""
        if not title:
            return False
        for prefix in self._skip_ns:
            if title.startswith(prefix):
                return False
        if ":" in title:
            prefix = title.split(":", 1)[0]
            for sp in self._skip_ns:
                if sp.rstrip(":") == prefix:
                    return False
        return True

    # ---- Helpers ----

    def _title_to_filepath(self, title):
        page_url = f"https://{self.domain}/wiki/{title.replace(' ', '_')}"
        return url_to_filepath(page_url, f"https://{self.domain}/wiki/", self.output_root)

    def extract_content(self, url):
        """Legacy interface."""
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        for prefix in ("wiki/", "w/"):
            if path.startswith(prefix):
                path = path[len(prefix):]
                break
        title = path.split("/")[-1] if path else self._page_title
        return self._extract_by_title(title)

    def discover_links(self, url):
        """Legacy interface."""
        titles = self._discover_by_title(self._page_title)
        return [f"https://{self.domain}/wiki/{t.replace(' ', '_')}" for t in titles]
