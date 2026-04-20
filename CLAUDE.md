# game-toolkit

Claude Code 插件源码仓库。当前版本 v1.5.0，面向 Web 游戏项目的通用开发/设计工具箱。

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
2. 更新 .claude-plugin/plugin.json 的 version（遵循 semver）
3. git commit + push（commit message 参考 git log 风格：feat/fix/chore 前缀）
4. 在 marketplace 目录 git pull：
     git -C "C:/Users/lzcm7/.claude/plugins/marketplaces/game-toolkit" pull
5. 重启 Claude Code 或运行 /plugin update game-toolkit 让新版本生效
```

发版节奏上，git 历史里的约定是：功能性改动用 `feat:` / `fix:`，版本号单独一条 `chore: bump version to X.Y.Z`。

## 目录结构

```
.claude-plugin/plugin.json    # 插件清单（name/version/description/author）
agents/                       # 17 个 sub-agent（.md，frontmatter + 系统提示词）
commands/                     # 17 个 slash command（部分嵌套：code-review/ design-review/ security-review/）
skills/                       # 11 个 skill（每个一个子目录，含 SKILL.md 和资源）
```

### agents/（按功能分组）

- **分层实现三件套**：`framework.md`（业务逻辑/系统设计）、`content.md`（数据/叙事/数值）、`interaction.md`（UI/样式/交互）——职责边界明确，别交叉
- **规划/评审**：`planner.md`、`pragmatic-code-review-subagent.md`、`design-review-agent.md`、`security-reviewer.md`、`frontend-performance-reviewer.md`
  - 架构设计与通用代码评审已移除（与官方 `feature-dev:code-architect` / `pr-review-toolkit:code-reviewer` 重复），请直接使用官方版本
- **工具/维护**：`build-error-resolver.md`、`refactor-cleaner.md`、`doc-updater.md`、`tdd-guide.md`、`e2e-runner.md`、`visual-debugger.md`
- **设计理论**：`game-designer.md`（整合 game-design-theory skill）

### skills/

- **设计流程**：`design-discuss/`（讨论+收录）、`design-iterate/`（多视角评审迭代）、`doc-consistency-check/`（文档矛盾检查）
- **知识/理论**：`game-design-theory/`（三本设计书知识库）、`game-ui-design/`、`react-game-ui/`、`book-to-reference/`
- **代码/文档同步**：`sync-code-ahead/`（代码→文档）、`sync-docs-ahead/`（文档→代码 gap 分析）
- **实现执行**：`parallel-implement/`（git worktree 并行实现）、`generate-assets/`（Gemini 图片资源）

### commands/

- **脚手架**：`new-website.md`、`new-backend.md`、`new-fullstack.md`、`new-valdi.md`、`project-setup.md`
- **工作流**：`plan.md`、`tdd.md`、`build-fix.md`、`refactor-clean.md`、`test-coverage.md`、`e2e.md`
- **评审**（有 README）：`code-review/`、`design-review/`、`security-review/`
- **文档维护**：`update-codemaps.md`、`update-docs.md`

## 插件组件编写约定

- **agent** 文件：前置 YAML frontmatter（`name`、`description`、`tools`），正文是系统提示词。description 必须讲清楚何时触发、何时不用
- **skill** 目录：一个 `SKILL.md` 作为入口（frontmatter 同 agent），可挂脚本/模板/参考资料到同级文件
- **slash command**：单 markdown 文件，YAML frontmatter 定义参数与行为
- 需要脚手架或规范时直接调用官方 `plugin-dev` 插件的 skill（`plugin-dev:agent-development` / `skill-development` / `command-development`）

## 协作注意事项

- 中文沟通
- agents/skills 描述里对"何时使用 / 何时不使用"都要写清楚——Claude 是靠 description 判断是否触发的，含糊就会漏触发或乱触发
- 不要随手 `--no-verify` 跳过 hook
- `.orphaned_at` 由 Claude Code 自己写，已在 `.gitignore`，不要 commit
