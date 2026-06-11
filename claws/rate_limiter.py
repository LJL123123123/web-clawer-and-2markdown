"""
Token-bucket rate limiter with per-domain tracking and random jitter.
"""

import time
import random


class RateLimiter:
    """Tracks request timing per domain to enforce crawl delays."""

    def __init__(self, default_delay=1.5, default_jitter=0.5):
        self._last_request = {}       # domain -> timestamp
        self._base_delays = {}        # domain -> base delay
        self._jitter_ranges = {}      # domain -> jitter max
        self._default_delay = default_delay
        self._default_jitter = default_jitter

    def configure(self, domain, base_delay, jitter):
        """Set delay and jitter for a specific domain."""
        self._base_delays[domain] = base_delay
        self._jitter_ranges[domain] = jitter

    def wait(self, domain):
        """
        Sleep if necessary to maintain the per-domain rate limit.
        Must be called before each request to the domain.
        """
        base = self._base_delays.get(domain, self._default_delay)
        jitter = self._jitter_ranges.get(domain, self._default_jitter)
        delay = base + random.uniform(0, jitter)

        now = time.time()
        if domain in self._last_request:
            elapsed = now - self._last_request[domain]
            if elapsed < delay:
                sleep_time = delay - elapsed
                time.sleep(sleep_time)

        self._last_request[domain] = time.time()

    def last_request_time(self, domain):
        """Return the timestamp of the last request to `domain`, or None."""
        return self._last_request.get(domain)
