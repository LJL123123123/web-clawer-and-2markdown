"""
Central configuration for the multi-wiki crawler.

Site-specific overrides go in WIKI_CONFIGS keyed by domain.
Unknown domains use the "default" config — works for most sites.
"""

import os

# ---- Paths ----
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_ROOT = os.path.join(BASE_DIR, "output")

# ---- User-Agent Pool ----
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
]

# ==============================================================
# Default config — applied to any domain without a specific entry.
# Uses readability-lxml for content extraction, chardet for encoding.
# Works for 90%+ of websites without any customization.
# ==============================================================

DEFAULT_CONFIG = {
    "name": "Generic HTML",
    "crawler": "html",          # "html" | "mediawiki" | "auto"
    "delay": 1.5,
    "jitter": 0.5,
    "encoding": "auto",         # "auto" = chardet detection
    "encoding_fallbacks": ["utf-8", "gb18030", "gbk", "big5",
                            "shift_jis", "euc-jp", "latin-1"],
    # Content selectors: readability-lxml is primary, these are fallbacks
    "content_selectors": [
        "article", "main",
        "[class*='content']", "[class*='article']", "[class*='post']",
        ".content", "#content", "#bodyContent", ".mw-body-content",
        ".markdown-body", ".prose", "body",
    ],
    "html2text_opts": {
        "body_width": 0,
        "ignore_links": False,
        "ignore_images": False,
        "skip_internal_links": False,
    },
    "relative_links_only": False,
    "skip_patterns": [
        "javascript:", "mailto:", "#",
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".css", ".js", ".json", ".xml",
        ".pdf", ".zip", ".tar.gz", ".mp3", ".mp4",
    ],
}

# ==============================================================
# Per-domain overrides — tune delay, selectors, encoding per site.
# Only add entries that DIFFER from the default config.
# ==============================================================

WIKI_CONFIGS = {
    # DeepWiki: Next.js SPA, needs more specific selectors
    "deepwiki.com": {
        "name": "DeepWiki",
        "delay": 1.0,
        "jitter": 0.5,
        "encoding": "utf-8",
        "content_selectors": [
            "div[class*='prose'][class*='max-w-none']",
            "div[class*='prose']",
            "article", "main", "[class*='content']", "body",
        ],
    },

    # Marxists.org: GB2312 encoding, relative links only
    "www.marxists.org": {
        "name": "Marxists.org",
        "delay": 2.0,
        "jitter": 1.0,
        "encoding": "auto",
        "encoding_fallbacks": ["gb18030", "gbk", "utf-8", "latin-1"],
        "relative_links_only": False,
        "content_selectors": ["body"],
    },

    # Moegirlpedia: MediaWiki with restricted API
    "zh.moegirl.org.cn": {
        "name": "Moegirlpedia",
        "crawler": "mediawiki",
        "delay": 1.5,
        "jitter": 0.5,
        "action_api": "https://zh.moegirl.org.cn/api.php",
        "skip_namespaces": [
            "Category:", "Template:", "File:", "Help:",
            "MediaWiki:", "Special:", "User:", "Talk:",
            "User talk:", "Template talk:", "Category talk:",
            "File talk:", "MediaWiki talk:", "Help talk:",
            "Module:", "Module talk:", "Gadget:", "Gadget talk:",
            "TimedText:", "TimedText talk:", "Topic:", "Project:",
            "萌娘百科:", "Help talk:", "Template:", "模块:",
        ],
    },

    # Wikipedia: MediaWiki with open API
    "en.wikipedia.org": {
        "name": "Wikipedia EN",
        "crawler": "mediawiki",
        "delay": 2.0,
        "jitter": 1.0,
    },
    "zh.wikipedia.org": {
        "name": "Wikipedia ZH",
        "crawler": "mediawiki",
        "delay": 2.0,
        "jitter": 1.0,
    },
}
