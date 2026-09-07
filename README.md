# game-toolkit

给用 Claude Code 做游戏的人：**把设计意图变成可实施的契约，再变成代码。**

不是通用工程工具箱 —— 构建、测试、代码评审这些请用 Claude Code 官方命令或别的插件。
本插件只做一件事：让「设计文档 → 实现契约 → 代码」这条链不丢失信息。

## 解决什么问题

游戏项目的设计文档有两个老毛病：

- **越写越乱** —— 机制算法、实例清单、精确数值混在一页里，改个数值要同步三处
- **写了等于没写** —— 文档说「管理玩家状态」，实现的人还得自己决定状态是什么、失败怎么办

前者靠职责分层解决，后者靠实现契约解决。这是本插件的两条主线。

## 核心概念：两条正交轴

| | Framework 怎么运转 | Content 有什么 | Interface 怎么输入与反馈 |
|---|---|---|---|
| **A 语义与契约** | 权威状态、命令、规则、拒绝、事件、不变量 | 实例身份、字段含义/单位/范围、关系 | 输入到命令的映射、反馈时序、可达性 |
| **B 编排** | 规则依赖、契约缺口、验收状态 | 内容清单、真值源指针 | 输入/结果覆盖、体验验收 |
| **C 技术适配** | 状态承载、调度机制、代码位置 | 序列化、资源路径、导入器 | 设备绑定、视图对象、渲染载体 |

三个职责都贯穿 A/B/C —— Framework 不等于「底层代码」，Interface 也不等于「渲染」。
完整定义见 `layer-contracts` skill。

**判据**：换个引擎，允许改变承载方式，不应重写游戏行为。

## 装

```bash
/plugin marketplace add lzcm729/game-toolkit
/plugin install game-toolkit@game-toolkit
```

装完 `/reload-plugins`，或重启 Claude Code。

## 有什么

**4 个 agent**

| agent | 做什么 |
|---|---|
| `framework` | 规则与权威状态：命令、转换、拒绝、事件、不变量 |
| `content` | 实例与数值：字段含义、单位、范围、关系、内容验收 |
| `interaction` | 玩家输入与反馈：输入映射、局部交互状态、反馈时序 |
| `game-designer` | 边界明确的独立设计任务（单视角评审、整合、按已采纳决定改写文档） |

**13 个 skill**

- **共享定义** — `layer-contracts`（两条轴、A 层交付门槛、执行模型要求、四问自检）
- **设计流程** — `design-discuss`（主对话里讨论与收录）、`design-iterate`（多视角并行评审 + 用户裁决）、`doc-consistency-check`（跨文档矛盾检查）、`split-doc-layers`（把混写的文档按职责拆开）
- **知识/理论** — `game-design-theory`（Rouse / Sylvester / Schell / Meadows 四本书，29 份参考）、`game-ui-design`（引擎无关的游戏 UI 原则）、`book-to-reference`（把书导入成参考文件）
- **文档 ↔ 代码** — `sync-code-ahead`（代码改了、文档没跟）、`sync-docs-ahead`（文档写了、代码没实现）
- **实现执行** — `parallel-implement`（git worktree 并行实现 + 顺序合并）
- **资源管线** — `generate-assets`（schema-driven 批量生成，引擎适配当前支持 Godot / generic）
- **可选技术适配** — `react-game-ui`（Web 栈的游戏 UI 实现模式，只在项目确实用 React 时才用）

## 项目侧要做一件事

在项目根放一个 `game-toolkit.yaml`。**引擎和版本必须人工填** —— 工具能认出
`project.godot` 或 `.uproject`，但认不出「这个仓库里哪个才是本次要动的工程」
「用的哪个大版本」「Blueprint 能不能按文本扫」，猜错的代价比问一句大得多。

```yaml
engine: unreal
engine_version: '5.8'
project_root: .
tech_stack: C++ / Blueprint
inspectability: C++ 可按文本扫；Blueprint / .uasset 查不了，不得据文本结果判定缺失
verify_entry: 尚未登记，使用前读项目构建说明
```

**有脚本，不用手抄**：

```bash
python <layer-contracts>/scripts/project_env.py check <项目根>
```

它报告缺哪些必填项，并从 `.uproject` / `project.godot` / `ProjectVersion.txt`
探测候选值。**候选不是结论** —— Claude 会把它们弹给你确认（引擎和版本必须人拍板），
确认后用 `write` 写回；同名段落是替换不是追加，可反复跑。

字段含义、可选项、以及「未知 / 不适用 / 查不了」三者为什么必须分开写，
见 `layer-contracts` skill。不声明也能用，只是每次都要回答同样的问题。

## 从哪开始

**设计文档乱了** → 说「拆一下 XX 系统的设计文档」，走 `split-doc-layers`

**想评审某份设计** → 说「跑一轮 XX 的设计迭代」，走 `design-iterate`：
多个视角并行评审 → 整合报告 → 你裁决 → 更新原文档 → 可选衔接 `parallel-implement`

**要实现某个系统** → 让 `framework` 先给契约（状态、命令、拒绝、不变量、验收场景），
再落到具体引擎。契约不完整时它会把缺口交回来，而不是自己编。

**批量出图** → 项目根放 `asset-config.yaml`，说「按 yaml 跑 batch」

## 依赖

- `generate-assets` 依赖 `image-gen` skill（底层生图 SDK，需单独安装）
- 其余组件无外部依赖

## 不适用

- 构建修复、死代码清理、测试生成、代码/安全评审 → 用官方 `/code-review`、`/security-review`、`/simplify`，或 superpowers、mattpocock-skills 等插件
- E2E 与浏览器调试 → `webapp-testing`、`browser-use`、playwright MCP
- 通用网页/应用界面设计 → `frontend-design`

这些在 3.0.0 从本插件移除过一次，理由和迁移去向见 CHANGELOG。

## 维护

改插件本身看 `CLAUDE.md`（开发回路、组件编写约定、版本发布流程）。

MIT-ish：随便用，出问题自己担着。
