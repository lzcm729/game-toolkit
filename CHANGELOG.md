# Changelog

`game-toolkit` Claude Code plugin — shared game development skills, agents, and commands for game projects.

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

## 当前状态（2026-05-03）

| 类别 | 数量 | 列表 |
|---|---|---|
| Skills | 11 | book-to-reference / design-discuss / design-iterate / doc-consistency-check / game-design-theory / game-ui-design / generate-assets / parallel-implement / react-game-ui / sync-code-ahead / sync-docs-ahead |
| Agents | 15 | build-error-resolver / content / design-review-agent / doc-updater / e2e-runner / framework / frontend-performance-reviewer / game-designer / interaction / planner / pragmatic-code-review-subagent / refactor-cleaner / security-reviewer / tdd-guide / visual-debugger |
| Commands | 17 | build-fix / code-review (+ subdir) / design-review (+ subdir) / e2e / new-backend / new-fullstack / new-valdi / new-website / plan / project-setup / refactor-clean / security-review (+ subdir) / tdd / test-coverage / update-codemaps / update-docs |

## 命名约定

- **Version bump**：feat / refactor 大改 → minor bump（X.Y.0）；fix → patch bump（X.Y.Z）
- **Tag**：每次 release 打 `vX.Y.Z` tag（已有 `v1.6.0`）
- **Commit message**：`feat: ...` / `fix: ...` / `refactor: ...` / `chore: ...` / `rename: ...` 前缀
