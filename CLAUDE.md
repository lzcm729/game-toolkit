# game-toolkit

Claude Code 插件源码仓库。当前版本 v3.0.0，游戏设计文档工具箱：分层契约、设计文档工作流、Godot 资源管线。

**GitHub**: https://github.com/lzcm729/game-toolkit
**作者**: lzcm729

## 这个目录的定位

这是插件的**开发主目录**（位于 OneDrive，跨机器同步源码）。真正被 Claude Code 加载运行的是另外两个副本：

| 角色 | 路径 | 说明 |
|---|---|---|
| 开发主目录（此处） | `C:\Users\lzcm7\OneDrive\GameRelated\game-toolkit` | 改动在这里发生，push 到 GitHub |
| Marketplace 源 | `C:\Users\lzcm7\.claude\plugins\marketplaces\game-toolkit` | Claude 从此拉取发布版本 |
| 运行时缓存 | `C:\Users\lzcm7\.claude\plugins\cache\game-toolkit\game-toolkit\<version>` | 实际被加载的只读副本 |

## 开发回路

```
1. 在此目录修改 agents/ skills/ commands/
2. 更新 version（遵循 semver）——plugin.json 一处 + marketplace.json 两处，三处要一起改
3. 补 CHANGELOG.md 条目
4. git commit + push（commit message 参考 git log 风格：feat/fix/chore 前缀）
     git tag -a vX.Y.Z -m "..." && git push origin main --follow-tags
5. 把 marketplace 镜像对齐到 origin/main：
     M=C:/Users/lzcm7/.claude/plugins/marketplaces/game-toolkit
     git -C "$M" fetch origin main && git -C "$M" reset --hard origin/main
   直接 git pull 会报 refusing to merge unrelated histories——这个镜像是
   shallow clone，拉不到共同祖先。首次可先 git -C "$M" fetch --unshallow。
   镜像没有本地改动，reset --hard 安全。
6. 重启 Claude Code 或运行 /plugin update game-toolkit 让新版本生效
   ——运行时缓存按 version 号建目录，不改 version 就不会重装
```

发版节奏上，git 历史里的约定是：功能性改动用 `feat:` / `fix:`，版本号单独一条 `chore: bump version to X.Y.Z`。

## 目录结构

```
.claude-plugin/plugin.json      # 插件清单（name/version/description/author）
.claude-plugin/marketplace.json # marketplace 清单（两处 version 要和 plugin.json 一起改）
agents/                         # 4 个 sub-agent（.md，frontmatter + 系统提示词）
skills/                         # 12 个 skill（每个一个子目录，含 SKILL.md 和资源）
CHANGELOG.md                    # 版本记录，每次 bump 同步补条目

（3.0.0 起没有 commands/ —— 11 个 slash command 连同 11 个 agent 一起移除，
 原因见下方「3.0.0 砍掉了什么」）
```

### agents/（按功能分组）

- **分层三件套**：`framework.md`（规则与权威状态）、`content.md`（实例与数值）、`interaction.md`（玩家输入与反馈）——职责边界见 `layer-contracts` skill，别交叉
- **设计评审**：`game-designer.md`（被 design-iterate 委派或用户明确要求独立执行时用；开放式讨论走 design-discuss skill）

### skills/

- **共享定义**：`layer-contracts/`（三件套与 split-doc-layers 共用的分层定义与 A 层契约门槛，不直接面向用户）
- **设计流程**：`design-discuss/`（讨论+收录）、`design-iterate/`（多视角评审迭代）、`doc-consistency-check/`（文档矛盾检查）、`split-doc-layers/`（Framework/Content/Interface 三层拆分）
- **知识/理论**：`game-design-theory/`（四本设计书知识库）、`game-ui-design/`（引擎无关的游戏 UI 原则）、`book-to-reference/`
- **代码/文档同步**：`sync-code-ahead/`（代码→文档）、`sync-docs-ahead/`（文档→代码 gap 分析）
- **实现执行**：`parallel-implement/`（git worktree 并行实现）、`generate-assets/`（Godot schema-driven 资源管线）

### 3.0.0 砍掉了什么

一次性移除 23 个组件（11 agent + 11 command + 1 skill + docs/workflows），占当时正文的 61%。

- **整体来自另一个项目**：`e2e-runner` / `tdd-guide` / `build-error-resolver` /
  `refactor-cleaner` / `doc-updater` 及其配套命令。它们的示例里是
  `searchMarkets('election')`、`.from('markets')`、`HeaderWallet`、Solana wallet、
  MetaMask/Phantom 连接 —— 从一个预测市场 dApp 的 `.claude/` 整体搬来，示例一行没换。
  不是「偏 Web」，是根本不是为游戏写的。
- **绑死浏览器技术栈**：`visual-debugger`、`frontend-performance-reviewer`、
  `design-review-agent` 及其命令、`react-game-ui`。Godot / UE 用不上，
  且与已装的 `example-skills:webapp-testing`、`browser-use`、playwright MCP 重复。
- **与官方重复**：`security-reviewer`、`pragmatic-code-review-subagent`、`planner`
  及其命令 —— 官方 `/security-review`、`/code-review`、`Plan` agent 都更成熟。
  这条判断本插件早就做过（见 2.x 的「架构设计与通用代码评审已移除」），
  只是当时没执行完。

更早的移除：Web/Node 脚手架（`new-website` 等 5 个）与撞名的通用 `code-review.md`，2.0.0。

## 插件组件编写约定

- **agent** 文件：前置 YAML frontmatter（`name`、`description`、`tools`），正文是系统提示词。description 必须讲清楚何时触发、何时不用
- **skill** 目录：一个 `SKILL.md` 作为入口（frontmatter 同 agent），可挂脚本/模板/参考资料到同级文件
- **slash command**：单 markdown 文件，YAML frontmatter 定义参数与行为。**`description` 必填**——缺了它命令不进列表，Claude 不会主动挑到；`commands/` 下只放命令，说明文档去 `docs/`
- 需要脚手架或规范时直接调用官方 `plugin-dev` 插件的 skill（`plugin-dev:agent-development` / `skill-development` / `command-development`）

## 协作注意事项

- 中文沟通
- agents/skills 描述里对"何时使用 / 何时不使用"都要写清楚——Claude 是靠 description 判断是否触发的，含糊就会漏触发或乱触发
- 不要随手 `--no-verify` 跳过 hook
- `.orphaned_at` 由 Claude Code 自己写，已在 `.gitignore`，不要 commit
