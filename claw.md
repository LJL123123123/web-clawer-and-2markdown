一、先明确前提
绝大多数 Wiki 站点（MediaWiki、GitBook Wiki、Obsidian 在线库、自建 Wiki 等）分两类：
MediaWiki（维基百科、多数开源项目 Wiki）：最主流
静态站点 Wiki（GitBook、Docsify、VuePress 等）
下面分别给对应方案。
三、方案 2：通用爬虫脚本（Python，适配任意网页 Wiki）
不区分 Wiki 类型，基于 requests + beautifulsoup 递归爬取页面、提取正文、转 MD，纯通用爬虫。
1. 安装依赖
bash
运行
pip install requests beautifulsoup4 html2text
2. 递归爬取 + 转 MD 完整代码
使用说明
修改 BASE_URL 为你的 Wiki 首页地址
根据页面正文容器修改 soup.find(class_="content")：
浏览器 F12 查看正文所在 div 的 class /id
运行后自动递归所有子页面，按 URL 路径生成对应 MD 文件，完美匹配你 wiki -> A/aa、B/bb 的层级结构。
四、补充实用技巧
权限 / 登录 Wiki
如果 Wiki 需要登录：在 Python 脚本里加上 requests.Session()，带入 Cookie / 登录态即可爬取。
去冗余、优化格式
html2text / mw2md 转换后少量格式错乱，可手动微调
不想保留样式：设置 h.ignore_images = True、h.ignore_links = True
Windows 运行注意
wget/pandoc 务必加入系统环境变量
路径不要含中文、特殊字符，避免编码错误
限速防封禁
在爬虫代码 crawl 函数内加 time.sleep(1)，每次请求间隔 1 秒。
五、快速选型建议
表格
Wiki 类型	推荐方案
MediaWiki（标准维基）	Python mwclient 脚本
GitBook/Docsify 静态站	wget + pandoc 批量转换
不知名自定义网页 Wiki	通用 Python 爬虫（requests 版）
按你的目录结构需求，以上所有方案都会递归保留层级，最终本地文件树和线上 Wiki 完全一致。