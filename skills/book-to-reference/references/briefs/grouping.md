# 冻结现行插件能力与 O/N 分组

这一步在看到新卡和任何两版回答前做。主执行方填只读基线快照、工作目录、任务表和本次改入口影响范围。
分组员只看冻结基线及 `Paths.overview` 中的读者任务表，不读候选、验证、卡片、测试答案或新版本。
先读 [../acceptance.md](../acceptance.md)，按现行整个插件支持的判断或行动分组，不能只查本书关键词。

第一步通读基线中的相关 skills 正文与资料、agent 自带知识和消费引用，列工作目录 `grouping/capabilities.yaml`：

```yaml
capabilities:
  - id: c001
    source: Microbook
    supports: 固定观察条件后比较影子。
    depth: method
    locations: ["skills/game-design-theory/references/old.md:12-20"]
entry_sensitive:
  - ids: [c001]
    reason: 主要靠入口速查找到。
```

depth 为 method（有步骤/判据）、summary（要点）、mention（提及）。同一能力多处出现合为一条，保留所有位置。
其他书受入口影响的能力也列入；entry_sensitive 写理由，不用新卡决定保护哪些旧能力。

第二步逐任务回查能力原文，写 `grouping/groups.yaml`：

```yaml
- task_id: t01-01
  group: O-partial
  capabilities: [c001]
  supported: 支持固定条件。
  missing: 尚未提供记录方式。
  reason: 基线可给出部分具体行动，保守计入旧覆盖。
```

O 是已支持，O-partial 和拿不准的归属计入 O 并写已支持/缺失部分，N 是读者任务减去 O。
每条带能力号和可回查出处；不因新卡支持了某任务就把它挪到新增组。
主执行方核全量任务、重复/遗漏、位置及其他书受保护能力，然后冻结版本、分组和权重。
没有自动语义分组脚本，不能把抽样或编号检查说成分组已核。
范围未齐、分组证据缺失或独立性不足就停，不能进入回答对比。
交回：文件、各组数量、覆盖面、最不确定三条及原因；不改基线。
