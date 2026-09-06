# Changelog

`game-toolkit` Claude Code plugin — shared game development skills, agents, and commands for game projects.

## Unreleased

一轮完整评审（自审 + codex 独立第三方评审）后的修复。**尚未发版**，版本号仍为
2.0.0，待本地验证后再决定 bump 到哪个版本。

### fix

- **死引用与安装后失效的路径** — `qa-tester` / `programmer` / `game-system-review`
  三个 agent 和 `/build-and-fix` / `tdd-workflow` 都不存在却被引用；11 处
  `.claude/skills/...` 在插件安装后指向不存在的位置。理论与 UI 参考统一改为用
  Skill 工具调用对应 skill，并给 `framework` / `game-designer` 补 Skill 权限。
- **`generate-assets`** — `res://` 解析把 `output_root` 当项目根，参考图路径拼成
  `art/art/...` 静默失效；全局 `style.chain` 被忽略（README 已承诺透传）；
  一个 category 全失败会让成功的图片拿不到 `.import` 提示。补 5 个测试，115 → 120。
- **`game-ui-design`** — 22 条 regex 规则里 7 条与自带用例矛盾（`16px` 判过小、
  `"Press A"` 检测不到、已有 `navigation` 仍报缺失等），全部修正；新增
  `scripts/check_validations.py` 回归 harness，49 个用例现在全通过。
- **`sync-code-ahead`** — 检查点用单个 `last_synced_commit` 同时表示「扫描到哪里」
  和「全部处理完」，部分同步后暂缓项永久丢失。拆成 `scan` + `pending` 两段，
  改用 tree 比较（rebase / squash 安全），去掉 `feat:` 前缀过滤和 `git log --all`。
- **`sync-docs-ahead`** — 未声明架构时只搜 `.ts/.tsx/.py/.js`，Godot / Unity 项目
  会把已实现的功能全报成 missing。改为按项目技术栈确定范围。
- **`parallel-implement`** — 后半段写死 `tsc`，非 TS 项目会被卡住；中断恢复
  「有未提交变更就 commit 再 merge」会把半成品送进主分支。
- **`e2e-runner`** — `browser.startTracing` 是 Chromium CDP tracing 而非 Playwright
  Trace Viewer，`videosPath` 不是合法配置项。
- **`frontend-performance-reviewer`** — LCP / CLS / longtask 用 `getEntriesByType`
  取不到，空数组 reduce 成 0，慢页面会得到满分假象；TBT 定义也错了。
- **codemap 双产物** — `/update-codemaps` 写 `codemaps/`、`doc-updater` 写
  `docs/CODEMAPS/`，交替使用会产生两套地图。统一到后者。
- **Schell 透镜编号** — 速查表说 #9 Unification，references 里 #9 是 Elemental
  Tetrad、#11 才是 Unification。以 references 为准修正 3 处。
- **知识库数量漂移** — `game-designer` 仍称「三本书 / 23 个参考文件」，实际四本 29 个。
- **`design-iterate` 恢复状态** — Phase 0 恢复表缺「Teams 讨论已开始但综合报告未
  生成」这个中断状态；评审文件完整性阈值三处不一致（>5KB / >10KB / <5KB），统一为 5KB。

### refactor

- **去项目耦合** — `design-iterate` 的愿景判据原先写死「典当行经营外壳＋道德困境
  内核」，任何项目跑评审都会拿它当尺子。改为主流程解析一次「项目愿景上下文」
  （resolved / missing / conflicting 三态），委派时传绝对路径；找不到愿景时降级为
  「目标明确性检查」，不得推断「项目没有愿景」，也不得因无法证明符合就判定偏离。
  `theory-framework` 的 5 组示例表格、`idea-format` 的作者机器绝对路径一并中性化。
- **路由边界** — `design-discuss` 与 `game-designer` 的 description 原本争抢同一批
  请求。改为按交互方式划分：主对话协作走 skill，边界明确的独立委派走 agent；
  `game-designer` 补执行契约（review 不问采纳、只写指定输出文件、不自建目录）。
- **删空承诺** — `framework` / `interaction` 声称完成后 orchestrator 会启动
  `qa-tester` 并自动提交，该编排并不存在。改为如实描述信号语义。
- **常驻成本** — 砍掉 `game-designer` description 里的三个 example 块，
  收紧 `game-ui-design` 过宽的触发词（`console` / `accessibility` 等裸关键词）。

### chore

- 删除误入库的 `skills/sync-code-ahead/.sync-checkpoint`（带着作者项目的 commit
  hash），并加进 `.gitignore`。

### 三件套契约改写（A/B/C 边界落地）

此前几轮做的都是「让现有设计正确运行」（修死引用、路径、正则、API 误用），
职责边界本身一直没动。这一批才是边界工作。

新增 **`layer-contracts` skill**，作为三件套与 `split-doc-layers` 共用的分层定义真值源：

- 两条**正交轴**：引擎耦合度（A 游戏语义与实现契约 / B 工作流编排 / C 技术适配）
  × 游戏职责（Framework / Content / Interface）。三者都贯穿 A/B/C —— 不能把
  Framework 整体当 A、Content 当数据适配、Interface 当纯渲染，也不能用 hooks /
  reducers / 文件扩展名决定游戏职责。
- **A 层交付门槛**七项，每项给可实施粒度（状态与所有权 / 命令与前置条件 /
  转换与原子性 / 拒绝与恢复 / 事件与副作用 / 不变量与判据 / 跨职责接缝）。
  明令「不能只写『管理状态』『处理失败』」。
- **执行模型必须显式声明**：时间与固定步长、坐标与连续运动、确定性与网络权威、
  动画与音频时序。其中一条：动画标记若影响命中，命中时刻须成为 Framework 契约，
  不能由素材默认长度决定。引擎无关不等于抹掉执行模型。
- 一个购买事务的完整示例（10 条带具体数字的验收场景、判定优先级、requestId 去重、
  原子提交、过期预演重判、持久化失败语义），并标明「示例不作其他游戏的默认规则」。

三件套据此改写：`framework` 的职责域从「目录结构 / hooks / TypeScript types」
换成「权威状态、命令、规则评估、转换、拒绝原因、领域事件、不变量」；
`interaction` 的语义职责统一为 Interface（玩家输入与反馈），明确局部交互状态与
权威游戏状态的边界；`content` 删掉「工具脚本一律用 Python」，改为字段含义 /
单位 / 范围 / 关系 / 内容验收，并规定新操作符与新失败分支必须交回 Framework。
三者各加一段「由项目 / 技术适配提供」，把构建命令、文件位置、引擎对象映射标出去，
并写明：缺少技术能力是要上报的缺口，不是弱化契约的许可。

术语裂缝一并弥合：`split-doc-layers` 此前同一文件里混用 Interface（怎么呈现）与
Interaction（玩家怎么玩），现统一为 Interface；组件名保留 `interaction`。

**共享定义为什么独立成 skill**：初版放在 `split-doc-layers/references/` 下，
三件套要绕道调用该 skill 才能读到 —— 为拿 1524 词的定义先注入 2614 词的拆分流程，
额外 1.7 倍，且语义上让一个消费者拥有了共用真值源。独立后 description 常驻
64 词、正文按需注入 1524 词，一个会话内调用一次即回本。

### 复审（codex 第二轮 + 自查）后的第二批修复

第一批修完后又做了一轮独立复审，重点看「修复本身有没有引入回归」。结论：有两处。

- **`generate-assets` 的 res:// 修复弄坏了裸相对路径** —— 两种相对路径的基准不同
  （`res://` 相对项目根，裸路径相对 `output_root`），原代码共用一个 root 导致前者错，
  我改传 `project_root` 后变成后者错。已拆成 `_resolve_reference()` 分别处理。
  这条 codex 判了「已解决」，是自查发现的。
- **`.import` 提示漏掉「全部 skipped」** —— 图片已存在时 `success=0`，但那些 PNG
  同样可能还没被 Godot 导入。codex 实测复现。
- **`validations` 的 focus 规则扩大匹配范围后产生新漏报** —— `button { outline: none; }
  input:focus-visible {...}` 不再命中。回到同规则块内查找，宁可多报。
- **Phase 0 恢复不经过新增的 Phase 2 前置** —— 旧批次直接恢复到 Phase 3.5 时，
  Teams 模板会去读一个不存在的愿景上下文文件。

其余复审发现：

- `parallel-implement` 里我新写的 `godot --headless --check-only` **不成立**
  —— 该选项必须配 `--script <文件>`，只能逐脚本解析，不能当项目级构建检查
- `frontend-performance-reviewer` 换了 Observer 采集，但外层 MCP 调用参数仍是错的
  （`browser_wait_for` 传 `selector/state/timeout`、`browser_evaluate` 传 `script`，
  实际 schema 是 `text/textGone/time` 和 `function`），按模板执行会在采集前就失败；
  指标未测到时仍返回 0 会呈现「满分假象」，改为 `null` 并写明 CLS/TBT 的口径限制
- `sync-code-ahead` 固定了扫描快照 H/T，读源码却仍用普通 Read —— 工作区里未提交的
  撤销会让 `pending` 被误删且再也扫不到。改为从 `git show <H>:<path>` 读
- `sync-code-ahead` 存在两套执行顺序（阶段 4→5 先确认后写 vs 阶段 7 先落盘后选），
  合并为一套；`pending` 的 `id` 明确为首次发现时分配、此后不变
- Teams 恢复拿整合评估的**全部**议题比对，会把用户跳过的议题判成缺失待补跑；
  改为对照评审计划里回写的用户确认清单
- 评审文件完整性从「>5KB」改为「含必需结构」—— 发现数量已改成按证据决定，
  按大小判会让一份完整的短报告被无谓补跑
- `validations` 10 条无用例规则里，实测出 **7 条必然误报**（已有 text-shadow /
  已加 CanvasScaler / 已设 raycastTarget=false / 同文件已 connect 的正确代码统统命中）。
  它们判的是跨作用域条件，正则表达不了，改标为 `heuristic` 并写明「命中只说明
  值得看一眼，不构成缺陷判定」；余下 3 条补齐用例

现状：15 条 regex 规则全部有用例覆盖（66 个用例，0 不符）+ 7 条 heuristic；
generate-assets 124 passed；组件引用 lint 0 问题。

### 评审中未采纳的一条

codex 认为「多 category 总退码取最大」违反 0/1/2 语义。核对后不改 ——
`examples/README.md:174` 与 `SKILL.md:152` 都明确写着取最大，且
`test_exit_code_max_across_categories` 锁定该行为，是有意设计而非实现漂移。

## 2.0.0 (2026-09-05)

### breaking

- **移除 5 个 Web/Node 脚手架命令**：`new-website` / `new-backend` / `new-fullstack` / `new-valdi` / `project-setup`——全仓库零引用，内容只是跑几条 npx，与游戏工具箱定位无关
- **移除 `commands/code-review.md`**：与 `commands/code-review/` 目录撞名，且与 Claude Code 官方 `/code-review` 重复。`e2e.md` / `plan.md` / `tdd.md` 里的 `/code-review` 引用自此落到官方命令上

### fix

- **11 个 slash command 全部可被发现**：`build-fix` / `refactor-clean` / `test-coverage` / `update-codemaps` / `update-docs` 此前无 `description` frontmatter，不进命令列表
- **`design-iterate` 入口改回 `SKILL.md`**：此前是小写 `skill.md`，Windows 上大小写不敏感所以一直能加载，Linux / macOS 上该 skill 会静默消失
- **修 5 处死链**：3 个 `.yml`（`claude-code-review.yml` / `claude-code-review-custom.yml` / `security.yml`）从未进过本仓库，2 个 `.md` 实际在 `agents/` 下

### refactor

- **`commands/` 只放命令**：3 个 `README.md` + `design-principles-example.md` + `design-review-claude-md-snippet.md` 移到 `docs/workflows/`
- **定位去 Web 化**：`plugin.json` / `marketplace.json` 的 description 与 keywords 改为反映实际（设计文档工作流 / Godot 资源管线 / 评审）

Commits: `41d6a4d`, `804dd23`, `407fc92`

## 1.8.1 (2026-06-30)

### feat

- **`split-doc-layers`** 补 Interface / Interaction 层处理专节

### chore

- `marketplace.json` 版本与 `plugin.json` 对齐（1.6.0 → 1.8.1）

Commits: `7068925`, `d455f46`

## 1.8.0 (2026-06-22)

### feat

- **`split-doc-layers`** 补 auto-dump 落地指引：引擎无关 4 步 pipeline + 文本中介统一引擎差异 + 数值进目录的边界 + 指向 `generate-assets`

Commits: `6e82e53`

## 1.7.2 (2026-06-22)

### fix

- **`split-doc-layers`** Phase 3 补「先定实例单位」步——verify 暴露了多维系统的实例边界盲区（如物种 x 稀有度）

Commits: `922ea69`

## 1.7.1 (2026-06-22)

### fix

- **`split-doc-layers`** 修 reviewer findings：试点分支 / 读者值对齐 / `semantic_field=none` / auto-dump 跳过 / 防双维护等
- **`split-doc-layers`** 修第二个项目 dogfood 暴露的 3 个盲区：`semantic_field=none` 的提炼路径、`data_ssot` 双层 SSOT、DriftPredictor fallback；新增 `project-egg` 示例

Commits: `326cc9d`, `d581fbb`

## 1.7.0 (2026-06-22)

### feat

- **`split-doc-layers`**（新 skill）设计文档三层拆分，配置驱动。识别文档里混写的 Framework（怎么运转）/ Content（有什么）/ Interface（怎么呈现），以最独立的 Content 层为起点建独立内容目录 + 双向指针，消除实例清单与精确数值混写导致的文档漂移

### docs

- 补 `CHANGELOG.md`，回溯记录 1.0.0 -> 1.6.0

Commits: `f112944`, `12bd151`

## 1.6.0 (2026-04-30)

### feat

- **`generate-assets` v2** — 重写为 Godot 通用 schema-driven asset orchestrator（替代 v1 PawnShop 三状态特化 items/characters/backgrounds）
  - yaml → batch JSON 翻译器 + image-gen 调度器
  - 所有项目特化（风格 / prompt 模板 / 数据源映射 / category 列表）从 Python 代码移到项目级 `asset-config.yaml`
  - 新增 `scripts/data_source.py`：3 种 type loader（json_dict / json_list / inline）+ filter（field_len / 字段相等）
  - 新增 `scripts/prompt_render.py`：`str.format` 模板 + derived_fields mini DSL

Commits: `e693fb4`

## 1.5.0 (2026-04-21)

### feat

- **`game-design-theory`** 加入 Donella Meadows 的 *Thinking in Systems: A Primer* 作为第 4 本参考书
  - 6 份 reference 覆盖：`meadows-fundamentals`（stocks/flows / balancing & reinforcing loops）+ 系统思考全套理论框架
  - 与现有 Schell《艺术》/ Salen《玩法》/ Costikyan《游戏设计基础》并列

Commits: `5fb0f29`

## 1.4.0 (2026-04-21)

### refactor

- **drop `architect` + `code-reviewer` agents** — 这两个 generic / boilerplate agent 已被官方 plugin 完全覆盖：
  - `code-reviewer` → 用 `pr-review-toolkit:code-reviewer`（confidence-filtered）
  - `architect` → 用 `feature-dev:code-architect`（blueprint-driven）
- 更新 cross-references in `build-error-resolver` / `design-review` README / `CLAUDE.md`

### chore

- 加入 `CLAUDE.md` + `.gitignore`（仓内贡献约定）
- bump version → 1.4.0

Commits: `70ab0b6` / `a23c923` / `4bdda65`

## 1.3.0 (2026-04-08)

### feat

- **`generate-assets`** 通用资源生成 skill（首发）
  - Data-driven asset generation via Gemini API
  - Items: 读 CSV + per-item prompts.json
  - Characters: 读 `assets/characters/characters.json`
  - Backgrounds: 读 `assets/backgrounds/backgrounds.json`
  - Style configurable via `assets/style.json`（watercolor defaults）
  - Auto-detect project root + flexible CSV column names

Commits: `b804282`

## 1.2.0 (2026-04-07)

### fix

- **`sync-code-ahead`** sync-checkpoint 路径参数化
  - 从 CLAUDE.md 读 checkpoint path / fallback `.claude/.sync-checkpoint`
  - 移除 hardcoded `.claude/skills/code-to-docs-sync/` 路径

Commits: `ecb51c2` / `0189502`

## 1.1.0 (2026-04-06)

### feat

- **三柱 agent 体系**（按游戏结构分工，而非人类角色）：
  - `framework` — "How the game works"（系统设计 / 业务逻辑）
  - `content` — "What's in the game"（数据 / 叙事 / 数值 / 资源）
  - `interaction` — "How players play"（UI 组件 / 视觉层）
- **`game-designer` agent** — 从 PawnShop 项目特化抽取到 shared plugin（替换 "The Pawn's Dilemma" 为通用项目引用 / 参数化设计文档路径）

### rename（语义对称命名 — 反映 directionality）

- `gap-analysis` → `sync-docs-ahead`（设计文档领先，检查 code 缺什么）
- `code-to-docs-sync` → `sync-code-ahead`（code 领先，更新 docs 跟上）

### refactor — generalize skills

- `design-iterate`：参数化设计文档路径 + conditional external doc handling
- `code-to-docs-sync`：移除 hardcoded subdirectory assumption
- `gap-analysis`：从 CLAUDE.md 读路径替代 Designer/ 结构 hardcode
- `parallel-implement`：替换 fixed fw/ui 角色为 CLAUDE.md 配置的 N 角色 / 参数化项目名 + build 命令 / 合并 prompt 模板
- 移除 `package-portable` + `generate-assets`（移回 PawnShop 作项目特化）

Commits: `4f29c5a` / `3920d92` / `47404d0` / `839a99c` / `8f09ccf`

## 1.0.0 (2026-04-06)

### Initial commit — 12 skills + 13 agents + commands

**Skills (12)**：含设计 / 文档同步 / 资源生成 / 并行实现等基础工具集

**Agents (13)**：
- `architect` / `code-reviewer`（later removed in 1.4.0）
- `build-error-resolver` / `design-review-agent` / `doc-updater` / `e2e-runner` / `frontend-performance-reviewer` / `planner` / `pragmatic-code-review-subagent` / `refactor-cleaner` / `security-reviewer` / `tdd-guide` / `visual-debugger`

**Commands**：build-fix / code-review (+ subdir) / design-review (+ subdir + design-principles-example + claude-md-snippet) / e2e + 其他

**Plugin metadata**：`.claude-plugin/plugin.json` + `marketplace.json`

Commits: `6cee947`

---

## 当前状态（2026-09-05）

| 类别 | 数量 | 列表 |
|---|---|---|
| Skills | 12 | book-to-reference / design-discuss / design-iterate / doc-consistency-check / game-design-theory / game-ui-design / generate-assets / parallel-implement / react-game-ui / split-doc-layers / sync-code-ahead / sync-docs-ahead |
| Agents | 15 | build-error-resolver / content / design-review-agent / doc-updater / e2e-runner / framework / frontend-performance-reviewer / game-designer / interaction / planner / pragmatic-code-review-subagent / refactor-cleaner / security-reviewer / tdd-guide / visual-debugger |
| Commands | 11 | build-fix / e2e / plan / refactor-clean / tdd / test-coverage / update-codemaps / update-docs + 三个嵌套评审命令（code-review/ design-review/ security-review/） |

三类组件的 `description` 都必填：缺了它不进列表，Claude 不会主动挑到。

## 命名约定

- **Version bump**：feat / refactor 大改 → minor bump（X.Y.0）；fix → patch bump（X.Y.Z）
- **Tag**：每次 release 打 `vX.Y.Z` tag（已有 `v1.6.0`）
- **Commit message**：`feat: ...` / `fix: ...` / `refactor: ...` / `chore: ...` / `rename: ...` 前缀
