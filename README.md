# Claw — 通用 Wiki 爬虫工具

自动检测站点类型（MediaWiki / 普通 HTML），提取正文并转换为 Markdown，按域名分类储存。

## 快速开始

```bash
pip install -r requirements.txt
python claw.py                    # 爬取 wiki_list.md 中所有链接
python claw.py --max-pages 10     # 每站限 10 页（测试用）
python claw.py --site wikipedia   # 只爬匹配域名的站点
python claw.py --fresh            # 忽略进度重新爬
```

## 添加新站点

编辑 `wiki_list.md`，每行一个 URL 即可。**无需修改代码**：

```
https://en.wikipedia.org/wiki/Python_(programming_language)
https://your-wiki.example.com/
```

系统自动：
- 探测站点类型（MediaWiki / 通用 HTML）
- 选择最佳内容提取策略
- 按域名分类储存到 `output/<domain>/`

## 支持的站点类型

| 类型 | 说明 | 自动检测 |
|------|------|:------:|
| **MediaWiki** | Wikipedia, Fandom, Moegirlpedia 等 | ✅ |
| **通用 HTML** | 任意网页、文档站、静态 Wiki | ✅（默认） |

### MediaWiki 站点

- 自动探测 `api.php` 或 `/w/api.php`
- 支持语言前缀（如 `/zh/api.php`）
- 优先使用 `extracts` API（HTML → Markdown）
- 自动回退到 wikitext（`revisions` API → wikitext → Markdown）

### 通用 HTML 站点

- 使用 [readability-lxml](https://github.com/buriy/python-readability)（Mozilla Readability 算法，同 Firefox 阅读模式）提取正文
- 使用 [chardet](https://github.com/chardet/chardet) 自动检测编码
- 使用 [html2text](https://github.com/Alir3z4/html2text) 转换 HTML → Markdown

## 限速防封禁

- **按域名独立延迟**：每个站点独立跟踪请求间隔
- **随机 jitter**：基础延迟 + 随机 0~N 秒抖动
- **User-Agent 轮换**：5 个现代浏览器 UA 随机选择
- **指数退避重试**：网络错误自动重试 2 次
- **429 处理**：读取 `Retry-After` 响应头并按指示等待

## 爬取范围控制

自动限制爬取范围，避免爬出整个域名：

- **HTML 站点**：路径前缀约束。如 `deepwiki.com/a/b` → 只爬 `a/b/*`，不爬其他仓库
- **MediaWiki 站点**：深度限制（默认 depth=1，种子页 + 直链页）。通过 `--max-depth` 调整

```bash
python claw.py --max-depth 2    # 更深（种子页 + 子页 + 孙页）
python claw.py --max-depth 0    # 只爬种子页
```

## 断点续爬

- 每个站点在 `output/<domain>/_state.json` 保存进度
- 中断后重新运行自动跳过已爬取的页面
- `--fresh` 参数可强制重新爬取

## 项目结构

```
claw.py                     # 主入口：读取 wiki_list.md，调度爬虫
wiki_list.md                # 待爬取 URL 列表（一行一个）
requirements.txt            # Python 依赖
claws/
  config.py                 # 站点配置（默认配置 + 按域名覆盖）
  content_extractor.py      # readability-lxml 内容提取 + 编码检测
  html_to_md.py             # HTML → Markdown（html2text / markdownify）
  wikitext_to_md.py         # MediaWiki 源码 → Markdown
  rate_limiter.py           # 按域名令牌桶限速器
  url_utils.py              # URL 规范化、路径映射
  state_manager.py          # JSON 进度持久化
  session_manager.py        # HTTP Session 管理
  storage.py                # 文件写入
  crawlers/
    html_crawler.py         # 通用 HTML 爬虫（适用于 90%+ 站点）
    mediawiki_crawler.py    # MediaWiki 爬虫（自动探测 API）
    base_crawler.py         # 抽象基类
output/                     # 分类输出目录
  deepwiki_com/             # 按域名组织
  zh_wikipedia_org/
  en_wikipedia_org/
  ...
```

## 按域名定制配置

在 `claws/config.py` 的 `WIKI_CONFIGS` 中添加域名专属配置：

```python
"example.com": {
    "name": "示例 Wiki",
    "crawler": "html",           # "html" | "mediawiki" | "auto"
    "delay": 2.0,                # 请求间隔（秒）
    "jitter": 1.0,               # 随机抖动（秒）
    "encoding": "gbk",           # 编码（"auto" = chardet 自动检测）
    "content_selectors": [       # CSS 选择器（readability 的回退）
        "article", ".content", "body"
    ],
},
```

## 已验证站点

| 站点 | 类型 | 状态 |
|------|------|:----:|
| deepwiki.com | HTML (Next.js SPA) | ✅ |
| marxists.org | HTML (GB2312 编码) | ✅ |
| zh.moegirl.org.cn | MediaWiki (受限 API) | ✅ |
| yugioh.fandom.com | MediaWiki (Fandom/Wikia) | ✅ |
| zh.wikipedia.org | MediaWiki (开放 API) | ✅ |
| en.wikipedia.org | MediaWiki (开放 API) | ✅ |

## 依赖

- `requests` — HTTP 请求
- `beautifulsoup4` + `lxml` — HTML 解析
- `html2text` / `markdownify` — HTML → Markdown
- `readability-lxml` — Mozilla Readability 内容提取
- `chardet` — 编码检测
- `mwparserfromhell` — MediaWiki wikitext 解析

## License

MIT
