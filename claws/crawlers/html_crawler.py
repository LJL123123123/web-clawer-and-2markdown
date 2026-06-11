"""
Generic HTML crawler — works for ANY HTML-based website.

Uses readability-lxml for content extraction (works across all layouts),
chardet for encoding detection, and html2text for Markdown conversion.

This replaces the separate DeepWiki and Marxists crawlers.
Suitable for: static HTML sites, Next.js SPAs, documentation sites,
GitBook, Docsify, VuePress, custom wikis, and any general webpage.
"""

import logging
import random
import time
from urllib.parse import urljoin, urlparse

import requests as req
from bs4 import BeautifulSoup

from claws.crawlers.base_crawler import BaseCrawler
from claws.content_extractor import extract_content as readability_extract, decode_html
from claws.html_to_md import convert_html_to_md

logger = logging.getLogger(__name__)

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


class HtmlCrawler(BaseCrawler):
    """
    Generic crawler for any HTML-based website.

    Features:
    - Automatic encoding detection via chardet
    - Content extraction via readability-lxml (Mozilla's algorithm)
    - Configurable CSS selector fallbacks
    - Configurable link filtering
    - Per-domain rate limiting with jitter
    - Retry on transient network errors
    """

    def __init__(self, seed_url, config, session_manager, state, output_root):
        super().__init__(seed_url, config, session_manager, state, output_root)
        self._delay = config.get("delay", 1.5)
        self._jitter = config.get("jitter", 0.5)
        self._last_request = 0.0
        self._encoding_fallbacks = config.get("encoding_fallbacks",
                                               ["utf-8", "gb18030", "gbk", "big5",
                                                "shift_jis", "latin-1"])
        self._encoding = config.get("encoding", "auto")
        self._relative_links_only = config.get("relative_links_only", False)
        self._keep_domains = config.get("keep_domains", None)  # extra domains to crawl

    def _rate_wait(self):
        now = time.time()
        elapsed = now - self._last_request
        delay = self._delay + random.uniform(0, self._jitter)
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self._last_request = time.time()

    def _fetch(self, url, retries=2):
        """Fetch a page with rate limiting, encoding detection, and retry."""
        self._rate_wait()
        headers = {
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }
        last_err = None
        for attempt in range(retries + 1):
            try:
                resp = req.get(url, headers=headers, timeout=30)
                resp.raise_for_status()

                # Decode with proper charset detection
                if self._encoding == "auto":
                    text = decode_html(resp, fallback_encodings=self._encoding_fallbacks)
                else:
                    resp.encoding = self._encoding
                    text = resp.text

                resp._decoded_text = text
                return resp
            except (req.ConnectionError, req.Timeout,
                    ConnectionResetError, TimeoutError) as e:
                last_err = e
                if attempt < retries:
                    logger.debug(f"Retry {attempt+1}/{retries} for {url}: {e}")
                    time.sleep(2 * (attempt + 1))
        raise last_err

    # ---- Content extraction ----

    def extract_content(self, url):
        resp = self._fetch(url)
        html_text = getattr(resp, '_decoded_text', resp.text)

        title, content_html = readability_extract(
            html_text,
            url=url,
            content_selectors=self.config.get("content_selectors"),
        )

        if not content_html:
            logger.warning(f"No content extracted for {url}")
            return f"# {title}\n\n*(无法提取内容)*\n"

        md = convert_html_to_md(content_html, self.config.get("html2text_opts", {}))
        return f"# {title}\n\n{md}"

    # ---- Link discovery ----

    def discover_links(self, url):
        resp = self._fetch(url)
        html_text = getattr(resp, '_decoded_text', resp.text)
        soup = BeautifulSoup(html_text, "lxml")

        links = set()
        visited_nets = set()

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()

            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue

            # Resolve URL
            if href.startswith(("http://", "https://", "//")):
                full_url = href if not href.startswith("//") else f"https:{href}"
            elif href.startswith("/"):
                if self._relative_links_only:
                    continue  # Marxists mode: skip root-relative
                full_url = f"https://{self.domain}{href}"
            else:
                full_url = urljoin(url, href)

            parsed = urlparse(full_url)

            # Domain filtering
            allowed_domains = {self.domain}
            if self._keep_domains:
                allowed_domains.update(self._keep_domains)

            if parsed.netloc not in allowed_domains:
                continue

            # Skip non-page resources
            path = parsed.path.lower()
            skip_exts = (".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
                         ".css", ".js", ".json", ".xml", ".pdf", ".zip",
                         ".mp3", ".mp4", ".ico", ".woff", ".woff2", ".ttf")
            if any(path.endswith(ext) for ext in skip_exts):
                continue

            links.add(full_url)

        logger.info(f"  Discovered {len(links)} links from {url}")
        return list(links)
