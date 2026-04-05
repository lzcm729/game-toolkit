# Implementation Checklist Format

## 文件头

```markdown
# 实现清单

> **来源**: {设计评审目录路径}
> **存放位置**: {评审目录}/implementation-checklist.md
> **生成日期**: {日期}
> **合并顺序**: {系统1} → {系统2} → {系统3} → ...
```

## 基础变更（Phase 1）

```markdown
## 基础变更（Phase 1 — main 分支）

| ID | 任务 | 代码层 | 状态 | 备注 |
|----|------|--------|------|------|
| B-1 | 通关目标改为 $500,000 | framework | pending | config/game.toml + systems/game/config.ts |
| B-2 | 新增 XXX action type | framework | pending | store/actions/types.ts |
```

## 系统任务

每个系统一个章节，任务按代码层分组：

```markdown
## {系统名}（worktree: feat/{分支名}）

**设计文档**: `{Designer/ 路径}`
**版本**: v{X.Y}

### Framework 层

| ID | 评审# | 任务描述 | 设计文档章节 | 状态 | 依赖 |
|----|-------|---------|-------------|------|------|
| S1-F1 | #11 | 赎回率规则重构 | 4.3节 | pending | - |
| S1-F2 | #12 | 新增稀有遭遇逻辑 | 11.2节 | pending | - |

### Interaction 层

| ID | 评审# | 任务描述 | 设计文档章节 | 状态 | 依赖 |
|----|-------|---------|-------------|------|------|
| S1-I1 | #13 | 升级购买分层反馈UI | 6章 | pending | S1-F1 |

### Content 层

| ID | 评审# | 任务描述 | 设计文档章节 | 状态 | 依赖 |
|----|-------|---------|-------------|------|------|
| S1-C1 | #46 | 填充专属文案模板 | 10节 | pending | - |
```

## ID 命名规则

- `B-N`: 基础变更
- `S{系统序号}-F{N}`: 系统 N 的 Framework 任务
- `S{系统序号}-I{N}`: 系统 N 的 Interaction 任务
- `S{系统序号}-C{N}`: 系统 N 的 Content 任务

## 状态值

| 状态 | 含义 |
|------|------|
| `pending` | 未开始 |
| `in-progress` | 进行中 |
| `done` | 已完成并验证 |
| `blocked` | 被依赖项阻塞 |
| `merged` | 已合并到主分支 |
