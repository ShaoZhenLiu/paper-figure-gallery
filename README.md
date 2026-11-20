# Paper Figure Gallery

[打开画廊](https://shaozhenliu.github.io/paper-figure-gallery/) · [查看全部图片](https://shaozhenliu.github.io/paper-figure-gallery/?c=all)

浏览论文的 Figure 1 和 Teaser。画廊支持 ICLR、ICML、NeurIPS、CVPR、ACL、AAAI 和 TMLR，按发表来源、年份、奖项与展示形式、图形模式筛选。点击卡片可以打开大图和原论文。

「仅精选」默认开启，可与其他筛选组合。页面顶部的总数和筛选项基于全量索引，结果栏显示匹配数量与图库总数。

## 仓库结构

- `main` 保存画廊源码和导入脚本。`data/figures.json` 与 `assets/figures.js` 记录精选图片，`data/gallery_distinctions.json` 保存附有来源的奖项与展示标签。
- `gh-pages` 保存可部署的静态快照和大部分图片。`gallery-assets` 保存超出 GitHub Pages 容量预算的图片。静态快照使用对应提交的图片地址。
- 本地扩展图片、SQLite 目录和抓取缓存放在 `gallery-local/` 和 `.gallery-cache/`。

## 本地运行和发布

```powershell
py -3.9 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt playwright
.\.venv\Scripts\python.exe -m http.server 8766 --bind 127.0.0.1
```

打开 [本地画廊](http://127.0.0.1:8766/)。[导入说明](docs/LOCAL_GALLERY.md)包含 DiagramBank 和按会议补图的命令。导入时会生成本地扩展索引。

发布前提交 `main` 的页面和源码。发布脚本从当前提交取页面，可用 `--snapshot` 传入本地已复核的图库 JSON 数组，根据目录大小生成发布提交。

```powershell
git fetch origin
.\.venv\Scripts\python.exe scripts/publish_gallery.py --repository ShaoZhenLiu/paper-figure-gallery --snapshot reviewed-figures.json
$release = Get-Content -LiteralPath '.gallery-cache/publication.json' -Raw | ConvertFrom-Json
git push origin "$($release.assets):refs/heads/gallery-assets"
git push origin "$($release.pages):refs/heads/gh-pages"
```

## 来源

本项目基于 [Top-Conf Figure Gallery](https://github.com/qwdwqfwq/topconf-paper-figure-gallery) 的 MIT 代码独立维护，扩展了数据库、录用名单、标签和页面筛选。主图来源包括论文集、arXiv 和 [DiagramBank](https://huggingface.co/datasets/ghzlmc/DiagramBank)。原论文及图片的权益归相应作者和出版方。详见 [LICENSE](LICENSE)、[NOTICE](NOTICE.md) 和 [图片政策](IMAGES_POLICY.md)。
