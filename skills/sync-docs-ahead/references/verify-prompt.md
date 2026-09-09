Phase 2b 的独立复核者读本模板；占位符为 `{systemName}`、`{reportPath}`、`{docPaths}`、`{reviewScope}`、`{codeHints}`、`{declared}`、`{declarationPath}`、`{projectRoot}`、`{doc_feedback}`。

# 复核者

报告 `{reportPath}` 由另一名分析者写成，你的任务是尝试驳倒它，不是复述它。
系统 `{systemName}`；设计全集 `{docPaths}`；范围 `{reviewScope}`；代码起点 `{codeHints}`。
工程根 `{projectRoot}`；声明 `{declared}`，来源 `{declarationPath}`；回填配置 `{doc_feedback}`。
先读本 skill 的 `references/analysis-prompt.md`，沿用其基线、引用、五状态、公式与检查边界。
只允许用 Edit 改 `{reportPath}`；源码、镜像、账本和其他报告均只读。

1. Read 完整报告，对 **每一行** ❌／🔄／⚠️ 独立找实现。换类名/字段名、事件名、标签、
   中文注释、配置段名等多搜几次，再打开命中与调用链。找到正式链上的实现，改判 ✅ 或 ⚠️
   并给 file:line；证实源存在但当前手段查不了，改 ❓ 并说明缺哪个检查动作；确认没有则维持，
   把搜过的关键词和排除理由写 Notes。只在测试里出现不等于已接运行链。
2. 从 ✅ 抽至少五行，优先查 Code Reference 单一、Notes 空或语义跨度大的行。
   Read 每个 file:line，确认位置存在且语义满足设计，不能只核文件名。
3. 从 ❓ 抽至少五行，查是否把声明里可文本检查的代码、配置、结构与引用推给了「查不了」。
   能查而没查就自己查完改判；运行行为需其他手段的限制仍保留。每类不足五行则全查，
   写实际数量；没有该状态则写零，不虚构抽样。
4. 对照设计标题、子规格与内容表找漏要求；重要漏项补行，# 接着编，原行号不重排。
   同时核 Code-only mechanics 是否漏了代码超前机制，每条补 code_ref 与「补文档还是删代码」的问题。
5. 有 `{doc_feedback.rulings_ledger}` 就核最新日期；若更晚裁决已改变设计，以新裁决重判。
   有 `{doc_feedback.engineering_log}` 就核现有条目日期和编号，偏离即使登记过也仍是 🔄；
   仅登记完成不能替代代码证据。未配置的可选目标不猜、不读取。
6. 用 Edit 改 Status / Code Reference / Notes，必要时纠正 Design Requirement 出处或补漏行，
   保持五列；重算 Summary 八行和两个比例，更新实际 Scan Scope。
   文末追加以下节，即使一行没改也记录实际抽验行与依据。

```markdown
### 复核记录

{检查了哪些行、各状态抽验数量、未能完成的检查与原因}

| # | 原判 | 改判 | 依据 |
|---|---|---|---|
| {报告行号} | {原状态} | {新状态} | {file:line 与原文含义，或实际搜索词及排除理由} |
```

状态未变时两格写相同状态，证据更正写「依据」列，不把附注塞进改判列；脚本逐格比较统计改判。
补行的原判写「新增」，新判写五状态之一；表内竖线转义。已有复核节时在原节补记录，不重复标题。
不能完成全量待驳行或抽样时向主流程报告未完成，不用空复核节伪装通过。

返回结构：`system`、`checked_rows`（去重后的实际行数）、`upheld`、
`changes`（`id / from / to / reason`）、`final`（重算后的六个计数）、`notes`。
