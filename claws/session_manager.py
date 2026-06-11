"""
HTTP session manager with User-Agent rotation, retry logic,
and encoding auto-detection.

Fixed: encoding is now handled via strict decode instead of
requests' lossy errors='replace' default.
"""

import random
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from claws.content_extractor import decode_html


class SessionManager:
    """
    Wraps requests.Session with:
    - User-Agent rotation per request
    - Retry with exponential backoff on transient errors
    - Proper encoding handling (strict decode, not lossy)
    """

    def __init__(self, user_agents, rate_limiter, max_retries=3):
        self._user_agents = user_agents
        self._rate_limiter = rate_limiter
        self._session = self._build_session(max_retries)

    @staticmethod
    def _build_session(max_retries):
        session = requests.Session()

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        return session

    def _random_ua(self):
        return random.choice(self._user_agents)

    def get(self, url, domain, timeout=30, **kwargs):
        """
        Perform a rate-limited GET request.
        Returns the raw response object — encoding handled by caller.
        """
        self._rate_limiter.wait(domain)

        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", self._random_ua())
        headers.setdefault("Accept",
                           "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
        headers.setdefault("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8")
        headers.setdefault("Accept-Encoding", "gzip, deflate, br")

        resp = self._session.get(
            url,
            headers=headers,
            timeout=timeout,
            **kwargs,
        )
        resp.raise_for_status()
        return resp

    def get_text(self, url, domain, timeout=30, fallback_encodings=None, **kwargs):
        """
        Perform a rate-limited GET and return properly decoded text.

        Uses chardet + fallback encodings with STRICT error handling
        to avoid the silent corruption of requests.Response.text.
        """
        resp = self.get(url, domain, timeout=timeout, **kwargs)
        return decode_html(resp, fallback_encodings=fallback_encodings)

    def get_json(self, url, domain, timeout=30, **kwargs):
        """
        Perform a rate-limited GET and parse JSON response.
        """
        self._rate_limiter.wait(domain)

        headers = kwargs.pop("headers", {})
        headers.setdefault("User-Agent", self._random_ua())
        headers.setdefault("Accept", "application/json")

        resp = self._session.get(
            url,
            headers=headers,
            timeout=timeout,
            **kwargs,
        )
        resp.raise_for_status()
        return resp.json()

    def close(self):
        """Close the underlying session."""
        self._session.close()
