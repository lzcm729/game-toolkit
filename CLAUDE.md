# game-toolkit

Claude Code 插件源码仓库。当前版本 v2.0.0，游戏开发/设计工具箱：设计文档工作流、资源管线、评审。

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
agents/                         # 15 个 sub-agent（.md，frontmatter + 系统提示词）
commands/                       # 11 个 slash command（部分嵌套：code-review/ design-review/ security-review/）
skills/                         # 12 个 skill（每个一个子目录，含 SKILL.md 和资源）
docs/workflows/                 # 三套评审 workflow 的说明与模板（非命令，别放回 commands/）
CHANGELOG.md                    # 版本记录，每次 bump 同步补条目
```

### agents/（按功能分组）

- **分层实现三件套**：`framework.md`（业务逻辑/系统设计）、`content.md`（数据/叙事/数值）、`interaction.md`（UI/样式/交互）——职责边界明确，别交叉
- **规划/评审**：`planner.md`、`pragmatic-code-review-subagent.md`、`design-review-agent.md`、`security-reviewer.md`、`frontend-performance-reviewer.md`
  - 架构设计与通用代码评审已移除（与官方 `feature-dev:code-architect` / `pr-review-toolkit:code-reviewer` 重复），请直接使用官方版本
- **工具/维护**：`build-error-resolver.md`、`refactor-cleaner.md`、`doc-updater.md`、`tdd-guide.md`、`e2e-runner.md`、`visual-debugger.md`
- **设计理论**：`game-designer.md`（整合 game-design-theory skill）

### skills/

- **设计流程**：`design-discuss/`（讨论+收录）、`design-iterate/`（多视角评审迭代）、`doc-consistency-check/`（文档矛盾检查）、`split-doc-layers/`（Framework/Content/Interface 三层拆分）
- **知识/理论**：`game-design-theory/`（四本设计书知识库）、`game-ui-design/`、`react-game-ui/`、`book-to-reference/`
- **代码/文档同步**：`sync-code-ahead/`（代码→文档）、`sync-docs-ahead/`（文档→代码 gap 分析）
- **实现执行**：`parallel-implement/`（git worktree 并行实现）、`generate-assets/`（Godot schema-driven 资源管线）

### commands/

- **工作流**：`plan.md`、`tdd.md`、`build-fix.md`、`refactor-clean.md`、`test-coverage.md`、`e2e.md`
- **评审**：`code-review/`、`design-review/`、`security-review/`——各一个 slash command，配套说明与模板在 `docs/workflows/`
- **文档维护**：`update-codemaps.md`、`update-docs.md`
- Web/Node 脚手架（`new-website` 等 5 个）与通用 `code-review.md` 已在 2.0.0 移除：前者与游戏工具箱定位无关，后者和 Claude Code 官方 `/code-review` 重复且与 `code-review/` 目录撞名

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
