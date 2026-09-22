# Claude Code 快车道：发布成 Artifact，从共享存储读回

只在工具列表里有 Artifact 工具时走这条路；用户说「出本地文件」就不走。
产物和本地路一样（`裁决单.html`、`裁决结果-<date>.json`），多的只是传输方式：
用户不用下载文件，agent 直接读到选择。

## 发布

1. 先按 Artifact 工具的规矩调一次 `quickstart`（`intent: "other"`），走「普通页面」那条路。
   设计上直接用 `build_page.py` 生成好的 `裁决单.html`，它已满足页面约定
   （双主题、窄屏、无外部脚本、无外部样式）。
2. 发布前加载 `artifact-capabilities`，发布带 `capabilities: {db: {}}`、`icon`、一句 `description`。
   页面里的 `window.claude.use("db")` 钩子只在这条路上生效，把选择存到 `rulings/<page.date>`。
3. 报 403 就原样重试一次；再不行退回本地路，给文件路径。
4. `裁决单.json` 改了就重新 build，用同一个 url 重发，链接不变。

## 读回

1. 用户说「选好了」→ `ArtifactData` `get`，`collection: "rulings"`，`doc_id: <page.date>`。
2. 把读到的 `{choices, notes, done, updatedAt}` 加上 `date`、`title`，写成评审目录的
   `裁决结果-<date>.json`，然后回 SKILL.md 第四节跑 `read_rulings.py`。
3. 读不到（没开 db、用户在别的浏览器打开的）→ 请用户点页底「下载结果文件」或「复制结果文字」，走本地路。
