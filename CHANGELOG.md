# Changelog

`game-toolkit` Claude Code plugin — game design contracts, design-doc workflows, and a Godot asset pipeline.
（3.0.0 起不再提供 slash command；历史版本的记载保持原样。）

## 3.4.1 (2026-09-07)

一轮 codex 独立评审的修复。全部是「上一版引入的、自己没查出来的问题」，
其中第一条是数据丢失。

### fix: `project_env.py` 会吃掉读不回来的配置文件

3.4.0 的 `load_config` 在 YAML 解析失败时兜底返回 `{}`。`write` 拿这个空 dict
当「已有内容」去合并，结果是：**本次改的字段活下来，其他字段全变回「待核实」，
用户自己加的字段直接消失。**触发条件很日常 —— 手改配置时漏个引号、括号没闭合。

比这更糟的是，3.4.0 的测试把这个行为锁成了「正确」：有一条用例断言损坏文件
被重写后只剩新字段，还写着「符合预期」。写测试的人（我）当时认为覆盖率够了。

修法不是「让它合并得更聪明」，而是**让它不动手**：

- `load_config` 返回 `(data, error)` 三态 —— 文件不存在 / 文件损坏 / 读到了。
  「读不出来」和「里面是空的」不再是同一个返回值。
- 文件损坏时 `write` 直接退出，一个字节都不改，除非显式 `--force`。
- 渲染完的内容先自己解析一遍，parse 不回来就不落盘。
- 落盘走 tempfile + 原子替换，写一半断电不会留下半个配置。

回归用例 `test_write_refuses_to_clobber_a_broken_file` 逐字节比对原文件。

### fix: 三件套 agent 被要求用它没有的工具

`layer-contracts` 写着「不确定就用 AskUserQuestion 问」，`framework.md` 的
Edge Case 也这么写。但 `content` / `framework` / `interaction` 三个 agent 的
`tools` 白名单里**没有** AskUserQuestion —— 照着做会撞上工具不存在。

改为：主流程（主 agent）用 AskUserQuestion；实现 agent 遇到要拍板的事**回报给主流程**，
不自己问。三个 agent 各加一段醒目提示说明这件事。

### fix: `sync-docs-ahead` 把「查不了」报成「未实现」

报告协议只有 OK/缺失 两态，Blueprint 图逻辑这类文本搜索证明不了的东西只能落进「缺失」。
新增 `Unverifiable` 状态，并把单一覆盖率拆成两个数：`Inspectable`（多大比例能查）
与 `Coverage of inspected`（查得了的里面实现了多少）。混成一个百分比会同时
低估实现度、高估检查力。

### 其他

- `generate-assets` 的 CLI **不读** `game-toolkit.yaml`。SKILL.md 新增「调用前：
  把工程根接上」：先 `project_env.py check` 取 `project_root`、解析成绝对路径，
  再传 `--project-root`。否则配置放在 `tools/` 下时脚本会把 `tools/` 当工程根。
- `engine_adapter.py` 撞见 `res://` 时原本提示「把 config 的 engine 改成 godot」，
  而 config 里已有 `adapter` 时这么改会触发「两者不一致」报错 —— 照提示做更错了。
  改为提示改 `adapter`，并说明旧 `engine` 字段要一并删掉。
- `README.md` 补上 PyYAML 依赖（`layer-contracts` 与 `generate-assets` 的脚本都要）。
- `layer-contracts` 新增「从 3.3.0 的 Markdown 声明迁过来」三步；两边都在且不一致时
  以 `game-toolkit.yaml` 为准并报告冲突。
- `detect` 把 `Intermediate/` `Saved/` `Binaries/` `DerivedDataCache/` `Build/` `.git/`
  的计数与源码分开；多个引擎标记同时命中时不给单一候选。日期值（YAML 会把
  `2026-09-07` 读成 `date` 对象）不再让 JSON 输出崩掉；数字型 `engine_version`
  会被点名（`5.10` 不加引号读成 `5.1`）。

### 新增：`scripts/verify_release.py`

发布前自检，**校验 commit 而不是工作区**：

```bash
python scripts/verify_release.py --version 3.4.1
```

比对指定 commit 里的三处 manifest 版本、CHANGELOG 最新段、拟建 tag 的状态。
3.3.0 那次事故正是「工作区是对的、commit 是错的」——
生成 CHANGELOG 的脚本报错退出了，同一条命令里的 `git commit && git push` 照跑，
推出去一个版本号还停在上一版的 commit，tag 却打成了新版本。
只看工作区的检查对这种情况一点用没有。

已存在且指向别处的 tag 一律报错，**默认不移动已推送的 tag** —— 别人本地的 tag、
插件缓存和已安装版本不会跟着变，要修就发修正版本。

测试：`layer-contracts` 32（+14）、`generate-assets` 132、validations 66 用例 0 不符。

## 3.4.0 (2026-09-07)

项目环境声明从「CLAUDE.md 里的一段 Markdown」改成项目根的 **`game-toolkit.yaml`**。

### 为什么改

3.3.0 按 codex 的建议放在 CLAUDE.md 固定段落，理由是「主要消费者是 agent」。
但 3.3.0 自己就带来了第二个消费者 —— `project_env.py` 要读写它。用 Markdown 列表
承载就得靠正则去啃，人改一下排版（换成表格、加个缩进、把冒号写成半角）就解析不出来。
既然已经有程序在读，就该用严格格式。

codex 当时也留了这个口子：「只有未来多个程序都需要自动读取同一份项目事实时，
再引入 game-toolkit.yaml」。现在这个条件到了。

### 改了什么

- 声明文件：项目根 `game-toolkit.yaml`。字段名从中文标签换成 `engine` /
  `engine_version` / `project_root` / `tech_stack` / `source_scope` /
  `inspectability` / `verify_entry` / `asset_config`。
- `project_env.py` 改为 YAML 读写。整文件重渲染（注释每次都在），合并已有字段，
  **用户自己加的未知字段原样保留**（重渲染不能吃掉别人写的东西）。
- CLAUDE.md 里只留一行指针。三个消费方（`parallel-implement` / `sync-code-ahead` /
  `sync-docs-ahead`）改为直接点名 `game-toolkit.yaml`，少一跳。

### fix

写 YAML 时踩到一个坑：`yaml.safe_dump` 对**纯标量**文档会补一行 `...`
（YAML 的文档结束标记），拼进配置文件就把结构破坏了，生成的文件根本解析不回来。
改为包成 dict 再取值部分 —— 该加的引号照样加，又不带文档标记。

### CatFishing

声明已迁到 `D:/LocalGameProject/Unreal/Catfishing/game-toolkit.yaml`，7 个字段齐全。
该工程的 `AGENTS.md` 里「适用于 D:/develop/Catfishing」是过期路径，改为「本仓库」——
写死路径迟早会再过期。

18 个测试（+3）：新增 YAML 畸形不崩、非映射被忽略、未知字段重写后仍在、多行文本往返。

## 3.3.0 (2026-09-07)

项目环境声明做成脚本：`layer-contracts/scripts/project_env.py`。

### feat

- **`check`** —— 只读，输出 JSON：缺哪些必填项 + 探测到的候选值。识别 `.uproject`
  （含 EngineAssociation）、`project.godot`（config/features）、Unity 的
  ProjectVersion.txt；统计源码构成；对二进制资产给出「查不了」提示。
- **`write`** —— 把确认后的值写回项目 CLAUDE.md。同名段落**替换**不追加，可反复跑；
  合并已有字段，不冲掉上一轮的值；不碰同文件其他段落。

**脚本不与人交互，这是设计不是限制。** 它在 agent 的 Bash 工具里跑，stdin 接空设备，
`input()` 只会拿到 EOF。分工固定三步：`check` 报告缺口与候选 → **agent 用
AskUserQuestion 交给人确认** → `write` 写回。预填候选让人确认比从零填好；引擎与版本
仍由人拍板 —— 探测认得出 `.uproject`，认不出「一个仓库里哪个工程才是本次要动的」
「EngineAssociation 是版本号还是源码版引擎的 GUID」「Blueprint 能不能按文本扫」。

### 在真实项目上验证过

CatFishing 的 UE 5.8 工程（`D:/LocalGameProject/Unreal/Catfishing`）：探测出
`unreal` / `5.8`、453 个 .cpp + 606 个 .h + **1707 个 .uasset + 12 个 .umap**，
并正确指出 `Catfishing.sln` / `Automation_Catfishing.sln` 是 UE 自动生成的、
不能据此推 `dotnet build` —— 这正是 3.2.0 修掉的那个误判的活样本。

走完 check → 确认 → write 给该工程建了声明。「可检查程度」记为「C++ 可按文本扫；
Blueprint / .uasset / .umap 查不了」—— 1707 个二进制资产，按文本扫描结果判定
功能缺失会是大规模误报。

15 个测试：状态判定、段落解析不越界、占位符不算已填、UE/Godot/Unity 探测、
GUID 不当版本号、多工程提示、`.sln` 反例，以及写入的幂等性与不破坏其他段落。

## 3.2.0 (2026-09-07)

引擎与版本改为**人工声明**，作为项目级配置。起因是 `generate-assets` 加了 `engine`
字段后发现：四个 skill 各写了一套引擎探测，问的问题还不一样。

### 一个被推翻的论据

我原本的论据是「`sync-docs-ahead` 认出 UE、`generate-assets` 退到 generic，
同一个插件对同一个项目给出两种答案」。codex 复核指出**这两个结果可以同时正确** ——
前者回答「实现代码可能在哪」，后者回答「这个生成器能提供什么路径与导入支持」。
`generic` 不是引擎身份，是**适配器**身份；是字段起名叫 `engine` 才让两个维度看起来冲突。
它还指出 `package.json` / `Cargo.toml` / `go.mod` 识别的是语言与工具链，
不该和游戏引擎放进同一个互斥枚举。

所以「探测四次」本身不是问题。真正要修的是**错误推断**：

### fix

- **`parallel-implement`：`.sln` 不能推出 `dotnet build`** —— UE 项目也会生成 `.sln`。
  构建命令改为只从项目声明的「验证入口」读，读不到就问，**不从工程文件反推命令**。
  验证入口是项目的选择不是引擎的属性 —— 同是 Godot 项目，脚本解析、导出检查、
  玩法测试是三种不同的验证。
- **`sync-docs-ahead`：`.uasset` 能 Glob 到不等于读得懂** —— Blueprint 逻辑、预制体
  连线属于「有源码但当前查不了」，此前会被算进扫描范围然后报成 missing，引发重复实现。
  现在必须按声明的「可检查程度」分三档：正常评级 / `无法检查` / 语言不在扫描范围。
- **`generate-assets`：工程根不再靠 config 位置猜** —— 把 config 挪个子目录，
  相对路径基准就变了。新增 `--project-root` 与 config 的 `project_root`，
  优先级：显式 > 声明 > 适配器探测 > 位置推断。
- **报错把人指进死循环** —— generic 撞见 `/Game/` 时提示「把 engine 设成 unreal」，
  但注册表里没有 unreal，照做会得到「未知的 engine」。认出前缀属于哪个引擎
  ≠ 支持那个引擎的操作。现在按有无适配分支给不同建议。补 2 个回归测试。

### feat

- **`layer-contracts` 新增「项目环境声明」节** —— 约定项目 CLAUDE.md 里的固定段落
  `## Game Toolkit 项目环境`。**引擎与引擎版本必须人工填**：探测认得出
  `project.godot`，认不出「这个仓库里哪个才是本次要动的工程」「哪个大版本」
  「Blueprint 能不能按文本扫」。
  规定了**三种「没有」必须分开写**：未知（还没查）/ 不适用（结构上就没有）/
  查不了（有但验证不了）—— 最后一种被当成「未实现」正是上面 `.uasset` 那个 bug 的根源。
  另附边界：它是兜底事实不是能力白名单、只读本次任务要用的字段、
  **子 agent 不会自动继承主流程读过的声明**、声明变化导致扫描范围变化要触发全量对账。
- **`adapter` 与 `engine` 语义分离** —— config 里选的是**适配器能力**，
  项目声明里的才是**引擎身份**。UE 项目声明「引擎：unreal」而 config 写
  `adapter: generic` 并不矛盾。旧 `engine:` 按 `adapter:` 处理（兼容期），
  两者同时存在且不同则报错，不替用户猜。
- `parallel-implement` 的委派模板新增「项目环境」段，主流程把已解析的事实传给子 agent。
- README 新增「项目侧要做一件事」，给出声明样板。

129 → 132 passed。

## 3.1.0 (2026-09-07)

三条产品决策的落地。

### feat

- **`generate-assets` 的引擎特化抽成适配层** —— 此前 description 里就写死「适用任何
  Godot 引擎游戏项目」「非 Godot 项目不适用」，而主项目用的是 UE5，等于插件里唯一的
  资源管线用不了。耦合其实很浅（只依赖 `godot_utils` 的 4 个函数），现在收进
  `engine_adapter.py`：工程根探测 / 路径前缀解析 / 生成后检查。
  config 加 `engine` 字段（`godot` / `generic`），未声明则探测，历史行为不变。
  **`generic` 撞见 `res://` 或 `/Game/` 会报错**，不再硬拼成 `<root>/res:/art`。
  UE / Unity 项目用 `generic` 即可跑通生成流程。加引擎 = 加一个 `EngineAdapter`
  实例并注册，主流程不动。（没有 UE 项目可验证，故不凭空写 UE 适配。）
  124 → 127 passed。

- **`react-game-ui` 恢复** —— 3.0.0 误删，codex 复核判定。它是 React 游戏 UI 的
  实现模式（资源条、动画计数器、卡牌、金币弹出、HUD 布局、读屏播报…），测试类工具
  替代不了。不是原样恢复：唯一一处项目特化 `<MetaPotPanel />` 改为 `<SidePanel />`，
  description 重写为「可选的技术适配」并划清三条边界（原则去 `game-ui-design`、
  其他引擎用各自 UI 系统、非游戏界面去 `frontend-design`）。skills 12 → 13。

### docs

- **新增 README.md** —— 此前仓库根目录只有 `agents/`、`skills/`、`CHANGELOG.md`
  和一份写满个人路径的 `CLAUDE.md`，别人打开这个仓库不知道它是什么、怎么装。
  README 讲：解决什么问题、两条正交轴的核心概念、安装、组件清单、四个典型入口、
  依赖、以及**不适用什么**（3.0.0 移除的那批去哪找）。
- **CLAUDE.md 泛化** —— 三处硬编码个人路径改为 `~/.claude/...`（Claude Code 的固定
  位置）与「你 clone 的位置」；顶部标明本文是维护者文档，用插件的人看 README。
  组件正文扫过，没有单人语境残留（扫出的「我的」全是 Meadows 书籍引文）。

## 3.0.1 (2026-09-06)

codex 对 3.0.0 做的独立复核（第三轮）。它确认删除本身清理干净、剩余 16 个组件
无断链，但找出两个真问题、一处误判和四处收尾没做完。

### fix

- **检查点模板不是合法 JSON** —— 2.1.0 引入的回归。`sync-code-ahead/SKILL.md:42`
  的 `"id"` 后加了 `// 首次发现时分配` 注释，标准 JSON 不允许注释，codex 实测
  `json.loads` 抛 `JSONDecodeError`。按模板落盘后普通 JSON 读取会失败。注释移出代码块。
- **worktree 依赖准备无条件执行 Windows/Node 命令** —— `parallel-implement`
  的 Phase 2 让每个 worktree 都跑 `cmd //c "mklink /J …node_modules…"`，没有操作系统
  或项目类型条件。macOS / Linux 找不到 `cmd`，纯 Godot 项目也会建一个没用的链接。
  这是 3.0.0 保留下来的既有问题，不是删除造成的。改为按项目实际情况分支，
  并写明判据是「worktree 能不能跑起构建检查命令」。

### refactor

- **2.1.0 的契约门槛没进并行实现入口** —— 三件套被直接调用时必须给出契约场景与
  验证证据，但走 `design-iterate → parallel-implement` 时启动的是 `general-purpose`，
  模板只注入目录白名单和构建命令，只凭编译通过就能标记完成并进入合并。
  **单项实现与批量实现的验收标准不一致。** 模板现在要求：先读 `layer-contracts`、
  注入本任务契约、逐条核对验收场景并给证据、契约缺口交回主流程不得自行补造规则。
  （沿用 `general-purpose` 而非换成三件套 —— 后者没声明团队流程需要的
  `SendMessage` / `TaskUpdate`。）
- **代码范围从「目录白名单」改为「语义所有权」** —— 原模板按目录禁止跨界，
  与 `layer-contracts` 明确允许的「实现可共处一个文件、按语义所有权划分」冲突。
  Godot 里一个脚本同时承载规则与呈现很常见，按目录划会让人要么越界要么拒做本职工作。

### docs

3.0.0 的删除判据说得比实际保留边界更绝对，逐条修正：

- 第一类「整体来自另一个项目」：成立的是**默认上下文被那个 dApp 污染**，
  不是「这些内容毫无游戏开发价值」。TDD 方法、最小化修复、测试稳定性、codemap
  思路仍可复用，`update-codemaps` 这轮也已改成按项目探测语言，并非全部未经修改。
- 第二类「绑死浏览器」：**浏览器也是游戏平台**，这条只说明不适合放核心。
  尤其 **`react-game-ui` 是误判** —— 它是 React 游戏 UI 的实现模式（资源条、
  动态数值反馈、卡牌、奖励弹出、HUD 布局、读屏播报），测试类工具替代不了，
  `game-ui-design` 也明确只管原则不管实现。迁移表补上：**没有等价替代入口**，
  需要时从 `83dbce7:skills/react-game-ui/SKILL.md` 取回重整。
- 第三类「与官方重复」：改为「这类通用能力可以外包」，不再声称官方必然更成熟。

定位描述同步改为「游戏设计与实现契约工具箱：分层契约、设计文档工作流、配套编排、
明确列出的技术适配」—— 原来的「只留设计文档工具」解释不了三件套的代码实现职责
和 worktree 合并。

另修四处收尾：CLAUDE.md 开发回路仍要求改 `commands/`、command 编写约定未标注废弃、
CHANGELOG 介绍仍写包含 commands、`sync-code-ahead` 内部引用「阶段 7」应为「阶段 8」、
`design-iterate` 写「Phase 5 衔接」实际入口在 Phase 4 第 6 步。

## 3.0.0 (2026-09-06)

**移除 23 个组件，占当时正文的 61%**（5572 / 9119 行），常驻 description 省下 656 词。
插件从「游戏开发工具箱」收敛为「游戏设计文档工具箱」：只留分层契约、设计文档工作流、
设计理论知识库、Godot 资源管线。**`commands/` 目录整个消失** —— 11 个 slash command
连同 11 个 agent 一起移除。

### breaking

移除的三类，各有各的理由：

**一、整体来自另一个项目（12 个组件 / 3135 行）**

`e2e-runner` + `e2e`、`tdd-guide` + `tdd` + `test-coverage`、`build-error-resolver` +
`build-fix`、`refactor-cleaner` + `refactor-clean`、`doc-updater` + `update-codemaps` +
`update-docs`。

它们的示例是 `searchMarkets('election')`、`.from('markets')`、`HeaderWallet`、
`app/markets/`、「Solana wallet integration」「Market trading logic」、
MetaMask / Phantom 钱包连接、place buy order —— 一个预测市场 dApp 的真实代码，
从那个项目的 `.claude/` 整体搬来。`e2e-runner` 里这类内容有 135 处、整段占约 160 行。

**成立的是「默认上下文被那个项目污染」，不是「这些内容毫无游戏开发价值」。**
TDD 方法、最小化修复策略、测试稳定性处理、codemap 生成思路本身仍可复用；
`update-codemaps` 这轮也已改成按项目探测语言，并非全部未经修改。
移除的判断基于：清理污染的成本高于这些方法的边际价值，且外部已有成熟替代。

**二、绑死浏览器技术栈（5 个组件 / 1340 行）**

`visual-debugger`（Web 命中密度 0.41，全插件最高）、`frontend-performance-reviewer`、
`design-review-agent` + `design-review` 命令、`react-game-ui`。
Playwright 只能测浏览器，Godot 用 GUT / gdUnit4、UE 用 Automation，都不走这条路；
调试、性能、视觉评审这三项与已装的 `example-skills:webapp-testing`、`browser-use`、
playwright MCP 重复。

**但浏览器也是游戏平台，这条判据只说明「不适合放在核心」，不说明「无价值」。**
`react-game-ui` 尤其要单独看 —— 它是 React 游戏 UI 的**实现模式**
（资源条、动态数值反馈、卡牌、奖励弹出动画、HUD 布局、读屏播报），
测试类工具替代不了它，保留下来的 `game-ui-design` 也明确只管原则不管实现。
移除它是「移出核心」，**目前没有等价替代入口**；将来若做 Web 小游戏，
宜整理成独立的可选 React 适配 skill，而不是原样恢复那 448 行
（旧文里还带着 `MetaPotPanel` 这类项目特化示例）。

**三、与官方重复（6 个组件 / 1097 行）**

`security-reviewer` + 命令、`pragmatic-code-review-subagent` + 命令、`planner` + 命令。
官方 `/security-review`、`/code-review`、`Plan` agent 提供同类能力。
理由是「这类通用能力可以外包，不必由游戏插件承载」——
回读也确认这三个包装层没有必须由本插件持有的独有契约。
这条判断本插件 2.x 就写过（「架构设计与通用代码评审已移除，与官方重复」），
只是当时没执行完 —— 这次执行完了。

配套的 `docs/workflows/`（5 个说明与模板文件）随之移除。

### 迁移

- E2E / 浏览器调试 / 前端性能 → `example-skills:webapp-testing`、`browser-use`、playwright MCP
- TDD → `superpowers:test-driven-development`、`mattpocock-skills:tdd`
- 代码评审 / 安全评审 / 计划 → 官方 `/code-review`、`/security-review`、`Plan` agent
- 构建修复、死代码清理、codemap → 官方 `/simplify` 覆盖一部分；其余按项目自身工具链处理
- **React 游戏 UI 实现模式（`react-game-ui`）→ 没有等价替代入口。** 已装的 `frontend-design`
  管的是通用视觉方向，`game-ui-design` 管的是引擎无关的 UI 原则，都不覆盖 React 组件实现。
  需要时从 git 历史 `83dbce7:skills/react-game-ui/SKILL.md` 取回并重整

### 保留

4 个 agent（三件套 + `game-designer`）、12 个 skill（`layer-contracts`、
设计文档六件套、`game-design-theory`、`game-ui-design`、`book-to-reference`、
`generate-assets`、`parallel-implement`）。

## 2.1.0 (2026-09-06)

两轮独立评审（自审 + codex 第三方评审 + codex 复审）后的修复，外加三件套的
职责契约改写。没有删除组件、没有改变调用方式；`sync-code-ahead` 的检查点格式
从 YAML 单水位换成 JSON scan+pending，读到旧格式会先做一次全量对账再迁移。

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
