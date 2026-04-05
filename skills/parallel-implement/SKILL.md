---
name: parallel-implement
description: |
  Git worktree 并行实现工具。从设计评审的采纳清单出发，使用 git worktree 并行实现多个系统的代码变更。
  触发场景：
  (1) 用户说"并行实现"、"开始实现"、"用 worktree 实现"
  (2) 用户提供设计评审目录或实现清单路径，要求开始代码实现
  (3) 用户说"把设计文档的改动实现到代码里"
  不适用：单个系统的实现（直接用对应的 agent）、设计讨论、评审。
---

# Parallel Implement — Git Worktree 并行实现

**设计评审采纳清单 → 实现清单 → Worktree 并行开发 → 顺序合并 → 验证**

## 架构：单 Team + 角色间直接通信

**角色定义从 CLAUDE.md 读取。** CLAUDE.md 中应定义 agent 角色、各角色的代码范围（允许修改的目录）、以及角色间的依赖关系。如果 CLAUDE.md 未定义角色，默认使用单角色 `general-purpose`。

典型配置示例（2 角色，有依赖）：
```
我 (coordinator)
├── TeamCreate("impl-batch-N") — 1 个 team
├── TaskCreate × (角色数 × 系统数)，按 CLAUDE.md 依赖关系设置 blockedBy
├── 并行 spawn 所有 agent:
│   ├── role1-A (wt-A)  ─── 立即工作（无依赖的角色）
│   ├── role1-B (wt-B)  ─── 立即工作
│   ├── role2-A (wt-A)  ── 💤 idle 等 role1-A（有依赖的角色）
│   └── role2-B (wt-B)  ── 💤 idle 等 role1-B
│
│ role1-A 完成 → SendMessage(role2-A, "改了这些接口...")
│ role2-A 有疑问 → SendMessage(role1-A, "类型？")
│
├── 全部 tasks completed
├── 我逐个 merge worktree branches → 解决冲突 → 构建验证
└── TeamDelete + commit
```

单角色配置（无依赖）：每个系统只有 1 个 task + 1 个 agent，无 SendMessage 通信。

**核心优势：**
- 无 leader 中间层，省 N 个 agent
- 角色间直接 SendMessage（第一手信息，不经转述）
- 双向通信（后续角色可反问前置角色）
- 快系统不等慢系统

---

## 流程总览

```
Phase 0: 生成实现清单
Phase 1: 基础变更（main 分支）
Phase 2: 创建 Worktrees
Phase 3: 并行实现（单 Team + 角色间直接通信）
Phase 4: 顺序合并（merge → tsc → commit）
Phase 5: 清理（worktree + branch + Team）
```

---

## Phase 0: 生成实现清单

**输入**：设计评审目录路径（含 `采纳索引.md` + `整合评估.md`）或 gap analysis WORKPLAN

1. **优先读取 `采纳索引.md`**（由 `design-iterate` Phase 4 自动生成）
   - 索引包含每个采纳项的：原编号、变更摘要、设计文档章节、代码影响层
   - 直接以索引为任务来源，无需反向推断
   - **兼容旧批次**：如果目录下没有 `采纳索引.md`（旧流程产物），回退到读取 `待定与下轮处理.md` 排除法
2. 读取对应的设计文档章节，将每个采纳项转化为可执行的实现任务
3. 为每个任务标注：
   - **代码层**：对应 CLAUDE.md 定义的 agent 角色（可多层）
   - **所属系统**：对应的 worktree 分支
   - **设计文档章节**：供 agent 定位阅读
   - **依赖项**：是否依赖其他任务先完成
4. 识别**跨系统共享变更**（如全局配置修改、共享类型定义），标记为 Phase 1 基础变更
5. 输出到 `{评审目录}/implementation-checklist.md`
6. **向用户确认**清单内容和合并顺序

---

## Phase 1: 基础变更（main 分支）

在创建 worktree 之前，先在 main（或当前开发分支）上完成所有**跨系统共享变更**。

识别标准：
- 全局配置变更
- 共享类型定义变更
- 共享工具函数变更

执行步骤：
1. 从清单中提取所有标记为"基础变更"的任务
2. 启动 general-purpose agent 实现（或 CLAUDE.md 指定的角色）
3. `tsc --noEmit` 验证
4. 提交到当前分支

---

## Phase 2: 创建 Worktrees

```bash
# worktree 目录约定：项目上级目录下
git branch {分支名} HEAD
git worktree add ../wt-{系统名} {分支名}
```

每个系统一个 worktree。创建后：
- `node_modules` 用 **junction** 共享（Windows 兼容）：
  ```bash
  cd {主项目上级目录} && cmd //c "mklink /J wt-{系统名}\node_modules {主项目目录名}\node_modules"
  ```
- 验证构建：`cd wt-{系统名} && node ./node_modules/typescript/bin/tsc --noEmit`（TypeScript 项目）或项目对应的构建检查命令

**重要**：向用户确认 worktree 路径。

---

## Phase 3: 并行实现（单 Team + 角色间直接通信）

### 3.1 读取角色定义

从 CLAUDE.md 读取：
- 角色列表（如 `framework`, `interaction`, `content` 或自定义）
- 每个角色的代码范围（允许修改的目录列表）
- 角色间依赖关系（谁先谁后，如 `interaction` blocked by `framework`）

如果 CLAUDE.md 未定义角色，使用单角色 `general-purpose`，每个系统 1 个 task。

### 3.2 创建 Team + Tasks

```
TeamCreate("impl-batch-N")

为每个系统创建 (角色数) 个 task，按依赖关系设置 blockedBy：
  Task role1-A: "系统A {角色1名} 实现" (无依赖)
  Task role2-A: "系统A {角色2名} 实现" (blockedBy: role1-A)
  ...
```

### 3.3 并行 spawn 所有 agent

一次性 spawn 全部 agent（无依赖角色立即工作，有依赖角色 idle 等待）：

```
每个 Task:
  subagent_type: general-purpose
  team_name: impl-batch-N
  name: {角色缩写}-{系统缩写}
  model: opus
  mode: bypassPermissions
  run_in_background: true
  prompt: （见下方通用 prompt 模板，注入角色信息和代码范围约束）
```

### 3.4 等待完成

所有 agent 通过 SendMessage 自动通信：
1. 前置角色完成 → TaskUpdate completed → SendMessage 给依赖它的后续角色（变更摘要）
2. 后续角色被唤醒 → 开始工作 → 有疑问可 SendMessage 反问前置角色
3. 全部角色完成 → TaskUpdate completed

我等待所有 tasks 变为 completed → 进入 Phase 4。

---

## Agent Prompt 模板（通用，按角色注入参数）

```
你是 team "{team_name}" 的成员 {name}，负责在 worktree 中实现 {系统名} 系统的 {角色职责描述}。

## 关键：工作目录

你的项目根目录是：`{worktree 绝对路径}`
（不是主项目目录！worktree 是隔离的工作副本。）

所有文件操作必须用此路径前缀：
- Read/Write/Edit: {worktree 绝对路径}/...
- Glob/Grep: path 参数设为 {worktree 绝对路径}/
- Bash: cd {worktree bash 路径} && ...
- 构建验证: cd {worktree bash 路径} && {构建检查命令}

## 你的任务（Task #{N}）

{具体任务描述，含 gap 编号、设计文档引用、代码位置}

## 代码范围

**允许修改：** {角色允许的目录列表，从 CLAUDE.md 读取}
**禁止修改：** {其他角色负责的目录}

## 完成后

1. 运行构建检查确保编译通过
2. 用 TaskUpdate 标记 Task #{N} 为 completed
3. 如果有后续依赖角色：用 SendMessage 发送给 {后续角色 agent name}，内容包括：
   - 你新增/修改了哪些类型和接口
   - 后续角色需要适配的部分
   - 注意事项
4. 保持在线，其他角色可能会有问题问你

## 等待指令（仅对有前置依赖的角色）

你的 Task #{N} 被 Task #{前置任务ID} ({前置角色 agent name}) 阻塞。
**请等待 {前置角色 agent name} 通过 SendMessage 发送变更信息后再开始工作。**
如果有疑问，可以 SendMessage 反问 {前置角色 agent name}。
```

---

## Phase 4: 顺序合并

**逐个合并到主分支。每次合并后验证。**

### 合并顺序

优先合并：
1. 被其他系统依赖的（先合底层）
2. 改动最小的（降低冲突概率）
3. 最独立的

### 单系统合并

```bash
# 先在 worktree 中 commit（如果 agent 没 commit）
cd {worktree} && git add -A && git commit -m "feat: implement {系统名} gaps — {摘要}"

# 回到主项目 merge
cd {主项目} && git merge {分支名} --no-edit
node ./node_modules/typescript/bin/tsc --noEmit
```

- **构建通过** → 继续下一个
- **合并冲突** → 手动解决（原则：保留更完整的版本）→ 构建验证
- **构建失败** → 在主分支修复，不回退

### 合并后审查

**重要：** 每次 merge 后检查是否有与先前合并的系统冲突的内容（如重复的 breach 逻辑、已删除标签被重新添加等）。

---

## Phase 5: 清理

1. 向所有 agent 发送 `shutdown_request`
2. `TeamDelete`
3. 清理 worktree：
```bash
rm -rf {worktree 路径}
git worktree prune
git branch -d {分支名}
```

最终 `tsc --noEmit` 验证。

---

## 分批策略

当任务量较大时，将系统分为多批执行：
- **同批条件**：文件无重叠、无跨系统依赖的系统可放同一批
- **分批条件**：有共享状态/共享模块结构变更的系统放后续批次
- 每批走完 Phase 3→4→5 完整流程后再启动下一批

---

## 中断恢复

1. 读取 `implementation-checklist.md` 或 `WORKPLAN.md` 检查进度
2. `git worktree list` 检查现有 worktrees
3. 对每个 worktree `git log --oneline -5` 和 `git status --short` 了解状态
4. 检查活跃 Team（`~/.claude/teams/`）
5. 从中断点继续：
   - worktree 已存在但无 commit → 从 Phase 3 开始
   - 有未提交变更 → 先 commit 再 merge
   - 部分 merged → 继续 Phase 4 合并剩余

---

## 权限配置（必须）

**在 `~/.claude/settings.json` 的 `permissions.allow` 中必须包含：**
```json
"Edit",
"Write"
```

否则 team 成员的 Edit/Write 操作会弹出权限请求打断用户。
`mode: "bypassPermissions"` 和 `defaultMode: "acceptEdits"` 对 team 成员不够。

---

## 约束

- Phase 1 必须在创建 worktree 前完成
- 合并必须逐个进行，不可批量
- 遵循 CLAUDE.md 的 agent 分工规则（各角色的代码范围边界）
- 每个角色只修改自己被允许的目录，不越界
- agent 只操作自己的 worktree，不触碰主项目或其他 worktree
- merge 只由主对话（我）执行，agent 不做 merge
- worktree 中 `npx` 和 `npm run build` 可能不可用（Windows junction 导致 .bin shim 失效），需直接调用可执行文件（如 `node ./node_modules/typescript/bin/tsc --noEmit`）
