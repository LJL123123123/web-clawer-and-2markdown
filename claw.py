#!/usr/bin/env python3
"""
Multi-Wiki Crawler — 通用 Wiki 爬虫工具。

自动检测站点类型（MediaWiki / 普通 HTML），
提取正文并转换为 Markdown，按域名分类储存。

用法:
    python claw.py                        # 爬取 wiki_list.md 中所有链接
    python claw.py --max-pages 10         # 每站限 10 页（测试用）
    python claw.py --site wikipedia       # 只爬匹配域名的站点
    python claw.py --fresh                # 忽略进度重新爬
    python claw.py --delay 2.0            # 自定义请求间隔

添加新站点:
    编辑 wiki_list.md，每行一个 URL 即可。无需修改代码。
    如需调优（选择器/编码/延迟），在 claws/config.py 添加域名配置。
"""

import argparse
import logging
import os
import signal
import sys

from claws.config import WIKI_CONFIGS, DEFAULT_CONFIG, OUTPUT_ROOT
from claws.state_manager import CrawlState
from claws.url_utils import extract_base_netloc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("claw")

# ---- Graceful shutdown ----
_active_crawlers = []


def _signal_handler(_sig, _frame):
    logger.info("\n收到中断信号，正在保存进度...")
    for crawler in _active_crawlers:
        crawler.cancel()
        crawler.state.save()


signal.signal(signal.SIGINT, _signal_handler)


# ---- Auto-detection ----

def detect_wiki_type(seed_url):
    """
    Auto-detect whether a URL is a MediaWiki site.

    First checks the per-domain config for an explicit 'crawler' setting.
    Otherwise probes /api.php to check for MediaWiki.

    Returns:
        'mediawiki' or 'html'
    """
    domain = extract_base_netloc(seed_url)

    # Check explicit config
    domain_config = WIKI_CONFIGS.get(domain, {})
    crawler_type = domain_config.get("crawler", "auto")

    if crawler_type in ("mediawiki", "html"):
        logger.info(f"  [{domain}] 使用配置指定类型: {crawler_type}")
        return crawler_type

    # Auto-detect: check for MediaWiki API
    from claws.crawlers.mediawiki_crawler import MediaWikiCrawler
    api_url = MediaWikiCrawler.detect(seed_url)
    if api_url:
        logger.info(f"  [{domain}] 检测到 MediaWiki API: {api_url}")
        return "mediawiki"

    logger.info(f"  [{domain}] 通用 HTML 站点，使用 readability 提取")
    return "html"


def get_config(domain):
    """Get merged config: per-domain overrides merged onto defaults."""
    base = dict(DEFAULT_CONFIG)
    domain_specific = WIKI_CONFIGS.get(domain, {})
    # Deep merge for nested dicts
    for key, value in domain_specific.items():
        if isinstance(value, dict) and key in base and isinstance(base[key], dict):
            merged = dict(base[key])
            merged.update(value)
            base[key] = merged
        else:
            base[key] = value
    return base


# ---- Crawler factory ----

def create_crawler(seed_url, output_root, resume=True):
    """
    Auto-detect wiki type and create the appropriate crawler.

    Returns:
        BaseCrawler instance, or None on failure.
    """
    domain = extract_base_netloc(seed_url)
    config = get_config(domain)
    crawler_type = detect_wiki_type(seed_url)

    # Output directory
    domain_slug = domain.replace(".", "_").replace(":", "_")
    wiki_output = os.path.join(output_root, domain_slug)

    # State (resume support)
    state_file = os.path.join(wiki_output, "_state.json")
    if not resume and os.path.exists(state_file):
        os.remove(state_file)
    state = CrawlState(state_file)
    if resume and state.visited_urls:
        logger.info(f"  恢复进度：已有 {len(state.visited_urls)} 个已爬取页面")

    # Create crawler based on type
    if crawler_type == "mediawiki":
        # Default max_depth=1 for MediaWiki to avoid crawling entire wiki
        if config.get("max_depth") is None:
            config["max_depth"] = 1
        from claws.crawlers.mediawiki_crawler import MediaWikiCrawler
        return MediaWikiCrawler(seed_url, config, None, state, wiki_output)

    # Default: generic HTML crawler
    from claws.crawlers.html_crawler import HtmlCrawler
    return HtmlCrawler(seed_url, config, None, state, wiki_output)


# ---- Main ----

def main():
    parser = argparse.ArgumentParser(
        description="Multi-Wiki Crawler — 通用 Wiki 爬虫工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python claw.py                              # 爬取所有站点
  python claw.py --max-pages 10               # 每站最多 10 页
  python claw.py --site wikipedia             # 只爬匹配域名的站点
  python claw.py --fresh                      # 忽略进度重新爬
  python claw.py --delay 3.0                  # 自定义延迟

添加新站点: 编辑 wiki_list.md，每行一个 URL。
        """,
    )
    parser.add_argument("--max-pages", type=int, default=None,
                        help="每个站点最多爬取页数（默认无限制）")
    parser.add_argument("--max-depth", type=int, default=None,
                        help="最大递归深度（默认无限制）")
    parser.add_argument("--delay", type=float, default=None,
                        help="请求间隔（秒），覆盖配置")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="输出目录（默认 ./output）")
    parser.add_argument("--site", type=str, default=None,
                        help="只爬取匹配域名的站点（如 wikipedia / marxists / moegirl）")
    parser.add_argument("--fresh", action="store_true",
                        help="忽略之前进度，重新爬取")
    parser.add_argument("--no-resume", action="store_true",
                        help="不续爬（同 --fresh）")

    args = parser.parse_args()

    output_root = args.output_dir or OUTPUT_ROOT
    resume = not (args.fresh or args.no_resume)

    # Load wiki list
    wiki_list_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wiki_list.md")
    if not os.path.exists(wiki_list_path):
        logger.error(f"找不到 wiki_list.md：{wiki_list_path}")
        sys.exit(1)

    with open(wiki_list_path, "r", encoding="utf-8") as f:
        seed_urls = [line.strip() for line in f if line.strip().startswith("http")]

    if not seed_urls:
        logger.error("wiki_list.md 中没有找到任何 URL")
        sys.exit(1)

    # Filter by --site
    if args.site:
        keyword = args.site.lower()
        seed_urls = [url for url in seed_urls if keyword in url.lower()]
        if not seed_urls:
            logger.error(f"没有匹配 '--site {args.site}' 的 URL")
            sys.exit(1)

    # Apply global --delay override
    if args.delay is not None:
        for domain in WIKI_CONFIGS:
            WIKI_CONFIGS[domain]["delay"] = args.delay
        DEFAULT_CONFIG["delay"] = args.delay

    logger.info(f"输出目录：{output_root}")
    logger.info(f"将爬取 {len(seed_urls)} 个站点：")
    for url in seed_urls:
        logger.info(f"  • {url}")
    logger.info("")

    # Crawl each site
    total_stats = []
    for i, seed_url in enumerate(seed_urls, 1):
        logger.info(f"{'='*60}")
        logger.info(f"[{i}/{len(seed_urls)}] {seed_url}")
        logger.info(f"{'='*60}")

        crawler = create_crawler(seed_url, output_root, resume=resume)
        if crawler is None:
            continue

        _active_crawlers.append(crawler)

        # max_depth: CLI arg takes priority, then per-domain config, then unlimited
        max_depth = args.max_depth
        if max_depth is None:
            max_depth = crawler.config.get("max_depth")

        try:
            stats = crawler.crawl(max_pages=args.max_pages, max_depth=max_depth)
            total_stats.append((seed_url, stats))
        except KeyboardInterrupt:
            logger.info(f"\n中断于：{seed_url}")
            crawler.state.save()
            break
        except Exception as e:
            logger.error(f"爬取异常：{e}", exc_info=True)
            crawler.state.save()
        finally:
            _active_crawlers.remove(crawler)

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("爬取完成！汇总：")
    logger.info(f"{'='*60}")
    for url, stats in total_stats:
        logger.info(f"  {url}")
        logger.info(f"    已爬取: {stats['visited']}  失败: {stats['failed']}")


if __name__ == "__main__":
    main()
