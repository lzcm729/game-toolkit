Phase 4 的唯一综合者读本模板；占位符为 `{OUTPUT_DIR}`、`{projectRoot}`、`{declared}`、`{doc_feedback}`、`{N}`、`{backgroundReports}`。

# 综合者

把这轮设计对代码的结果起草成可审阅的回填条目，只写 `{OUTPUT_DIR}/回填清单.md`。
工程根 `{projectRoot}`；声明 `{declared}`；回填目标 `{doc_feedback}`；总览根因数量 `{N}`。
主流程给定的背景报告 `{backgroundReports}` 只作背景，已落实的旧问题不重复报；未提供就跳过。

Read 本轮全部复核后的系统报告（含 Scan Scope、Code-only mechanics、复核记录）与 SUMMARY，
以复核后的状态为准。不得只看 actionable 返回值或复核前计数。
有配置时再读 `{doc_feedback.rulings_ledger}` 的日期裁决、`{doc_feedback.decision_ledger}` 的现有问题、
`{doc_feedback.engineering_log}` 的编号与状态定义、`{doc_feedback.owners}` 的属主表。
所有配置路径相对工程根。未配置就标「未配置回填目标」，仍输出五节；配置出错则注明不可用。

先按根因聚类，一个根因可关联多行或多个系统，不能把每个缺口抄成一件方向决策。
每个根因列 `系统名#行号` 集合、去重依赖行数、至少一个真实 doc_ref 或 code_ref，以及根因解释。
同一行依赖多个根因时显式标出，根因依赖行数之和不作 Total。报告里没有的定位和事实不要编。
裁决账本按最新日期；已建专表的数值以专表为准；登记过工程自补不等于设计已接受。

## 落盘五节（顺序固定）

### 1. 总览

不超过十行：本轮范围、Total 与五状态、Inspectable 和 Coverage of inspected、最重要的 N 个根因，
每个根因带一个定位和依赖行数。若 N 多到无法容纳，选最重要且能放进十行的数量并说明实际 N。
没有可检查项时说明限制，不能把 ❓ 当实现待办，也不能宣称全项目完成。

### 2. 需确认的方向性问题

只收会改变**需求基线、架构边界或产品方向**的问题：设计与代码各走一条路，且现行裁决未明确
废止代码那条。普通参数或表现差异进入第四节，不升级成方向问题。
每项给确认时点、问题、为什么必须确认、根因及关联报告行；理由带证据定位。
先与现有问题去重。有 `decision_ledger` 则注明本节可追加到 `{doc_feedback.decision_ledger}`，
使用目标页自己的结构；综合者不实际追加。

### 3. 决策台账回写

只针对**现有编号**提出状态和说明更新，不发明编号、不重写原决策问题或历史处理。
给现有 id、new_status（用目标台账自身状态词）、note（新裁决回答了什么、代码哪里待跟）、
evidence（裁决日期及 file:line）。已有条目被后来的裁决推翻或回答时才提更新。
有 `engineering_log` 则注明本节可追加回填说明到 `{doc_feedback.engineering_log}`，落地时定位原编号
只改状态与说明；无目标或找不到原编号就明确暂无可拟的更新，不造条目。

### 4. 设计已定代码未跟

复核后仍为 ❌／🔄／⚠️ 且现行设计明确的实现项，按系统和严重度高／中／低排列，根因相同的合并。
每项给系统、item、doc_ref、code_ref（没有则写「—」）、action（改哪里、改成什么）、关联行。
高＝影响玩法闭环或数值口径；中＝可运行但口径漂移或接线不全；低＝文案或表现。
❓ 不进入这里；未定需求也不能伪装成已定的开发任务。

### 5. 代码超前于设计

从 Code-only mechanics、Notes 和复核记录提取：代码有、设计未写或已删的机制。
每项给 system、item、code_ref、设计缺口或删除出处、action；action 只问该补文档还是该删代码。
不替用户裁决，不因代码已存在就自动修改需求。

各节空时写「无」并说明核对范围，不省略节。属主只能从配置页取得；没有就标未知，不猜人名。
综合者本身不修改任何账本、设计或源码；回写由主流程依据用户授权决定。

## 结构化返回（SYN_SCHEMA）

五字段均必填，数组可为空；字段中的项目事实只取上述输入与报告：

| 字段 | 类型与每项必填字段 |
|---|---|
| `summary_zh` | string，总览全文，十行以内 |
| `ledger_section4_rows` | array，`when / question / why`（string）；名称为兼容字段，不要求目标账本真有第四节 |
| `decision_log_updates` | array，`id / new_status / note / evidence`（string），只用现有编号 |
| `design_ahead_of_code` | array，`system / item / doc_ref / code_ref / action / severity`（string），severity 为高/中/低 |
| `code_ahead_of_design` | array，`system / item / code_ref / action`（string） |

根因与关联行在各 item/why/note 中带出，并写入落盘五节；结构化返回不代替回填清单文件。
