---
name: sync-docs-ahead
description: >
  Full design-document vs code gap analysis. Compares all design docs against
  actual code to identify implemented, partial, missing, and divergent features.
  Design document location is read from CLAUDE.md.
  Outputs a structured report to docs/gap-analysis/{date}/.
  Use when user says "gap analysis", "差距分析", "设计vs代码对比",
  "哪些功能还没实现", "实现了多少", "代码覆盖了哪些设计".
---

# 设计对代码差距分析

按系统发现文档，每系统一名分析者落盘、一名独立复核者改判，脚本校验后按根因综合。
主流程只协调任务与读取产物，不凭子 agent 的口头计数发布结论。

## Workflow

### Phase 1：发现

1. 读项目根的 `game-toolkit.yaml`：通过 `layer-contracts` 的 `scripts/project_env.py check`
   获取 `declared` 与来源，按其「项目环境声明」节处理缺项与冲突。声明文件所在目录与
   `project_root` 解析后的工程根分开传递；后者统一记作 `{projectRoot}`。
   同时读可选 `doc_feedback`，各路径相对工程根解析。缺块时后续只写报告，不路由账本；
   块内缺某个目标就只省略该路由，路径报错则明示该目标不可用，不自行猜位置。
2. Read CLAUDE.md，沿设计文档指针找到目录；项目已有文档位置与出处规则沿指针读取，
   不在 skill 内指定项目路径。若没有本地目录（设计保存在远程文档或知识库），先取得
   用户提供的本地导出目录或远程位置。**没有本地文档不等于没有设计**，不能拿空输入判缺失。
   远程导出由项目相应文档同步 skill 负责，导出后在 CLAUDE.md 登记指针，再从下一步继续。
3. 有工程根下的 `gap-analysis.config.yaml` 就按配置的 `systems` 分派：`docs` 评分、`refs` 只参考，
   `scope` 定边界、`code` 作源码线索；`docs_root` 缺省沿 CLAUDE.md 指针，解析后传给脚本。
   配置格式见 [examples/README.md](examples/README.md)。自动发现只在无配置时兜底：
   Glob 设计目录下全部 `**/*.md`，并纳入各系统的 CSV 内容表。按文件名取系统名：
   括号里有英文时取英文系统名；有数字前缀时去掉前缀、使用余下名称；否则用去扩展名的文件名。
   不凭空翻译成另一套系统身份。将实际系统清单留给 Phase 3 的 `--expect`。

   **目录即系统，不是一文件一系统。** 嵌套镜像把入口放在 `<系统>/<系统>.md`，
   同目录其他 `.md` 是该系统的子规格，树内 `.csv`（含 `*.embedded/*.csv`）是内容表；
   全部交给同一个系统分析者。容纳其他系统目录的索引或总览页不是独立系统，跳过评分。
   导出目录有 `_manifest.json` 时用节点 token 维持系统身份，标题改名不改身份。
   曾把一棵镜像的每个文件各当一个系统，既重复分析，又漏掉全部内容表。
   同名系统用身份映射消歧，落盘名须是合法单个文件名；报告标题与落盘名保持一致。
4. 文档名或首行状态的默认排除词为「已废弃」「勿引」「旧版」「Demo 不做」「候选」「不是 SSOT」；
   `{doc_feedback.exclude_markers}` 若给出则整体覆盖，空列表也有效。归档页排除并留清单，
   版本历史只作溯源；草稿单列为参考，不能把未定草稿当现行需求基线。
   有 `{doc_feedback.rulings_ledger}` 就读裁决日期，最新为准；已建专表的数值以专表为准、汇总页只留依据，
   规格页与总览的权威关系从项目指针和页内声明读取，不写死页面名。

只选择一次输出目录，之后每阶段统一使用 `{OUTPUT_DIR}`。输出基目录默认是工程根下的
`docs/gap-analysis/`（description 里的约定），本次任务或项目文档另有指定时从其指定。
在基目录下以本次日期建新目录；同日重跑加时间，同分钟重跑再加递增后缀，直到名称未被占用。
创建时若发现已存在就重新选名。**绝不写进已经存在的运行目录，也不清空旧结果**：旧报告可能有
人工改判，新一轮失败时它还是唯一证据。后续子任务不得自行拼另一条带日期的路径。

有基线时先生成增量计划（基线由本轮任务指定或从历史运行目录选定，明确记录路径）：

```bash
python <本 skill>/scripts/collect_gap.py --plan --baseline DIR --config FILE --project-root DIR [--docs-root DIR] [--force 系统A,系统B] [--json]
python <本 skill>/scripts/collect_gap.py --carry --baseline DIR --systems 系统A,系统B {OUTPUT_DIR}
```

只对 `rerun` 系统执行分析与复核；`carry` 用脚本复制，第二行标注本轮未重跑，已有同名文件拒绝覆盖。
无配置、无基线、基线无 RUN.json 或 Git 不可用时全部重跑并说明原因；无配置时可用 `--expect`
传入实际系统名。计划只比较文档版本与已提交的代码，工作区修改要纳入本轮时用 `--force`。
沿用完成后仍执行 Phase 3，全系统（含沿用）的实际清单都传给 `--expect`。

### Phase 2：分析

每系统启动一个可 Read / Glob / Grep / Write 的 `general-purpose` 子 agent，
使用本 skill 的 [references/analysis-prompt.md](references/analysis-prompt.md)。传入文档全集、
参考清单、评分范围、源码线索、声明与出处、工程根、系统名和同一个 `{OUTPUT_DIR}`。
同时给分析者与复核者传 `{BASELINE_REPORT}`（对应基线报告路径或「无」）；未变要求保留措辞和顺序，
新增追加，状态和 code_ref 每行重新核。agent 不写键、不算哈希。
源码线索只是搜索起点，不是源码全集。每份报告必须有 `### Features`、`### Summary`、
`### Scan Scope`、`### Code-only mechanics`；严格表格、五状态和出处格式以模板为准。
子 agent 缺声明时把结构化缺口交回主流程，不猜引擎、不把未知当未实现。

### Phase 2b：复核

每份报告完成后交给另一名复核者，使用本 skill 的
[references/verify-prompt.md](references/verify-prompt.md)。逐行驳 ❌／🔄／⚠️，换关键词多搜；
从 ✅ 至少抽五行核 file:line，从 ❓ 至少抽五行查是否把可文本检查的推给「查不了」；
某状态不足五行则全查并记实际数量。补漏行，只用 Edit 改自己那份报告，重算 Summary 八行。
文末必须有 `### 复核记录` 表（# | 原判 | 改判 | 依据），即使没有改判也记抽验行与依据。

### Phase 3：收集

等全部分析和复核完成后运行本 skill 的脚本：

```bash
python <本 skill>/scripts/collect_gap.py {OUTPUT_DIR} --write-summary [--out DIR] [--expect 系统A,系统B,…] [--baseline DIR] [--docs-root DIR] [--project-root DIR] [--config FILE] [--stamp-keys]
```

方括号表示可选参数，不原样传给 shell；带空格的路径加引号。主流程将 Phase 1 的实际系统名
用逗号连接传给 `--expect`，缺产物、超时或未复核均不能藏进合计。脚本校验 Features 表、
Summary 八行、五状态计数、两个比例、非空 Scan Scope 与复核记录，跳过汇总、回填清单与
下划线开头的辅助文件。无 `--expect` 时仅检查现有报告。默认写 `{OUTPUT_DIR}/SUMMARY.md`，
`--out DIR` 把汇总与运行记录写到 DIR。退出码非零时交回对应复核者修正，再收集；不得进入成功综合。
汇总合计从行数重算，不平均各系统百分比；「复核改判」按原判与改判两格不同的行数统计。

校验接受五列与加了第六列 `Key` 的报告；键只由脚本铸造，默认不改报告，`--stamp-keys` 才落列。
`--docs-root` 提供标题锚点与 manifest 身份；键为 `<doc>#<anchor>#<h8>`，数值变化不换键。
`--write-summary` 同时写 `RUN.json`，记录文档版本、`--project-root` 的 HEAD、逐行键与状态、沿用来源。
有 `--baseline` 时优先读基线 RUN.json，没有则现场从报告铸键；同键优先，同文档同锚点再按相似度
贪心一对一匹配（`--match-threshold` 默认 0.6），其余记新增／消失。汇总目录同时写 `TRANSITIONS.md`，
stdout 给各系统变化小计与稳定率；稳定率为一级匹配行数 ÷ 基线总行数，不代表实现覆盖率。

### Phase 4：综合

只启动一个综合者，使用本 skill 的
[references/synthesis-prompt.md](references/synthesis-prompt.md)，读全部复核报告与 SUMMARY，
传入 `{TRANSITIONS}`（TRANSITIONS.md 路径或「无」），有基线先讲退步与修复，
按根因聚类（一根因可关联多系统多行），写 `{OUTPUT_DIR}/回填清单.md` 五节：
总览、需确认的方向性问题、决策台账回写、设计已定代码未跟、代码超前于设计。
有 `decision_ledger` 时注明第二节可追加到该目标，有 `engineering_log` 时注明第三节
可追加说明到该目标（已有编号只提状态与说明更新）。**综合者不改任何账本**，只生成可审阅草稿；
改不改由主流程和用户决定。缺块或目标时仍完成五节报告，明示该节未配置回填目标。

### Phase 5：给用户

有基线时先报退步／修复及迁移表位置，区分重跑与沿用，再报根因；无基线按下面的现有写法。
给出根因 Top N，每个根因带一个可跳转定位及依赖行数（按系统＋行号去重），N 由本次任务
指定或按实际重要根因数量选择。同时给出合计 Total、五状态、可检查比例和可检查部分覆盖率，
附 SUMMARY 与回填清单位置。一个报告行可依赖多个根因，依赖行数不可当总行数累加。
不得用最低覆盖率系统榜代替根因解释，不能把可检查部分的比例说成全项目完成度。

## 编排

有 Workflow 工具时，对系统清单执行 `pipeline(分析 → 复核)`；一个系统分析落盘即可进入它的复核，
所有分支完成并通过 Phase 3 后再综合。没有时用后台子 agent，依赖顺序相同：独立系统可并发，
同一报告不能被分析者与复核者同时写。并发上限按环境，不写死模型、线程数或系统数。
通过任务通知或可用的 TaskOutput 等待结束，核对预期系统和实际产物；失败分支标出原因并续做，
不得因为收到了部分通知就发布成功总评。已有失败产物保留在本轮目录内供修正。

## Notes

- 只读源码、设计文档和项目账本；写入仅限本轮报告目录及显式 `--out` 的汇总目录。
- 跨系统总纲检查整体架构模式，不强行拆成具体功能条目。
- 项目声明范围内的测试文件只作旁证，不算运行链；仅在测试或未接入的旧模型中出现、
  正式链路没接的算 ⚠️，写清缺的接线。测试目录位置来自 `source_scope`，不按某个引擎目录猜。
- `❓` 定义不变：源存在但当前手段查不了。它不等于未实现、没搜过或不在扫描范围；
  能读出结构不等于能证明运行行为，能用文本核的部分也不能整个推给「查不了」。

反向条目交给 `sync-code-ahead`：将本轮 `### Code-only mechanics` 或回填清单第五节作为接收入口，
保留机制、code_ref 与设计缺口出处，由反向 skill 核对后进 pending；本流程不直接改设计或检查点。
