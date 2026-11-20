# 本地扩展画廊

打开根目录的 `index.html` 或启动本地 HTTP 服务。图库总数和筛选项由全量索引生成。「仅精选」用于筛出原画廊已精选的主图，默认开启。

## 准备环境

使用 Python 3.9 或更新版本，并确保 `curl` 在 PATH 中。下面以 Windows PowerShell 为例。

```powershell
py -3.9 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt playwright
.\.venv\Scripts\python.exe -m http.server 8766 --bind 127.0.0.1
```

如果已装有 Chrome 或 Edge，导入器会使用它渲染 arXiv HTML 中由多个面板组成的图。也可以传入 `--browser`，或使用 `python -m playwright install chromium` 安装浏览器。单张位图直接从 HTML 下载。

## 导入 DiagramBank

```powershell
.\.venv\Scripts\python.exe scripts/expand_gallery.py diagram-bank --plan
.\.venv\Scripts\python.exe -u scripts/expand_gallery.py diagram-bank
.\.venv\Scripts\python.exe scripts/expand_gallery.py status
```

脚本校验固定发布版的元数据 SHA-256，只读取明确录用论文的 Figure 1。录用校验同时使用论文决定和归档分组，ICML 的 Poster、Oral 和 Spotlight 等正式展示类别也视为录用。脚本按会议、年份和标准化标题与原库查重。图片解出后会逐步写入本地目录，刷新画廊即可看到。大型归档按 HTTP Range 续传，中断后重跑可继续。如果本机访问官方入口不稳定，可给 `diagram-bank` 加 `--hub https://hf-mirror.com`。手头已有归档时可使用 `--metadata`、`--archives` 和 `--local-only`。

[DiagramBank 论文](https://arxiv.org/html/2604.20857) · [固定的数据发布版](https://huggingface.co/datasets/ghzlmc/DiagramBank/tree/8d8d408b4ccff03d76e8cbd7b2f39a0914405c7e)

## 按录用名单补图

```powershell
.\.venv\Scripts\python.exe scripts/expand_gallery.py conferences --years 2017:2026 --plan
.\.venv\Scripts\python.exe -u scripts/expand_gallery.py conferences --years 2017:2026
.\.venv\Scripts\python.exe scripts/expand_gallery.py status
```

- 默认处理原画廊的 ICLR、ICML、NeurIPS、CVPR、ACL 和 AAAI。用 `--venues cvpr,acl` 和 `--years 2024:2026` 可以选择批次，`--refresh-rosters` 可重新拉取名单。缺失或部分名单会写入导入日志。
- 导入器先检查论文记录里的 arXiv 链接，再利用本地候选池、Paper Copilot 对照和 arXiv 标题查询匹配预印本。可用 `--arxiv-metadata <文件>` 传入 arXiv 的 JSONL、gzip 或 zip 元数据快照，以减少逐篇查询。
- 找到 arXiv 版本后优先取 HTML 的完整 Figure 1 或 teaser。多面板图按 HTML 布局整体渲染。HTML 不提供完整图时，使用原项目的 PDF 图注裁剪方法。日志会保留未成功补图的条目，重跑会跳过已入库的图。
- `status` 按已有名单列出每届含图论文数和名单总数，也显示已入库图片的来源。部分名单的分母以本机实际拿到的记录为准。

## 奖项与展示

Best / Outstanding 筛选包含最佳论文、杰出论文和官方荣誉提名。它与 Oral、Spotlight 独立。一篇获奖的 Oral 论文可以通过两种筛选找到。ICLR 2023 沿用原画廊的 Notable Top 5% → Oral、Notable Top 25% → Spotlight 对照，卡片显示官方名称。TMLR 的 Outstanding Certification 进入 Best / Outstanding 筛选，并以期刊原名显示。

扩展图库的名单依据和标签保存在 `data/gallery_distinctions.json`，用会议、年份和标准化标题匹配。导出索引时合并这些字段。历史公开名单缺失或无法确认的条目保留已有录用信息。

## 代码与本地数据

源码位于 `main`，发布入口见 [README](../README.md)。生成的 `gallery-local/` 包含图片、SQLite 记录和页面使用的索引。工作缓存位于 `.gallery-cache/`，这两个目录已加入 Git 忽略列表。

```powershell
.\.venv\Scripts\python.exe scripts/test_expand_gallery.py
.\.venv\Scripts\python.exe scripts/validate_gallery.py
```
