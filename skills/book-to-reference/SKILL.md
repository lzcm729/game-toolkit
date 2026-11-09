---
name: book-to-reference
description: >-
  维护本插件源码的书籍资料导入与迁移流程：仅在向本插件源码中的 game-design-theory 导入新书、补齐书籍方法或迁移旧参考时使用。覆盖原文核对、验证、写卡、接入和按任务验收。普通读书摘要、整理个人笔记、导入到自己的其他 skill 不触发。
---

# 向 game-design-theory 导入书籍资料

这是维护者流程，交付给本插件源码副本中的 `skills/game-design-theory/`，按用户意图分卡，共用现有入口。
普通读书摘要、个人笔记和其他 skill 的资料整理不走这条流程。

## 开工先做三件事

1. **核目标。** 先读目标源码的 CLAUDE.md。按 [references/workdir.md](references/workdir.md) 在仓库外建立 book.yaml，
   target_root 指明源码副本：有 .git、插件清单和 game-design-theory，不能是安装缓存或 marketplace。
   必填 display_author、display_title；mask_names 只管盲评遮蔽。先核配置，再做任何生成。
2. **分开材料和交付。** 工作目录和 Paths 的全部结果都在目标源码及脚本所在仓库外，书全文、分段、候选和验证记录不进公开仓库。
   公开卡保留按页核过的原文摘句和自译。Python 3.11、PyYAML 是脚本依赖，转 PDF 另需 PyMuPDF；已有可靠的带页码文本可直接用。
3. **报全流程胃口。** 先按书长、提取分工、验证范围和运行题数估 token、费用、必测/可选与停止条件，用户拍板后开工。
   Sylvester 全书提取到写卡约 1690 万子代理 token；接入与验收另计，这不是下一本书的固定报价。
   授权范围内沿用已定取舍，不重复确认；改变方向、超胃口或新的重大取舍才交回用户。

以下命令从本 skill 目录执行，替换尖括号参数；工作材料的路径显式从 `<workdir>` 起。

```text
python scripts/bookconf.py check <workdir>
python scripts/pdf_convert.py survey <pdf>
python scripts/pdf_convert.py convert <workdir> <pdf>
python scripts/pdf_convert.py page <workdir> "Keep the lantern still"
```

先 survey 再按本书定 convert 参数，不照搬另一书字体；page 的短语来自编造的微型书示例，换成待抽查原句。
转换后抽查印刷页码、节标题、引文/表格和缺图；未通过就修转换配置或材料，不带缺陷进入提取。

## 按阶段执行

按需读取对应任务书，主执行方在分派前填范围、输入文件、交付位置和可写范围；所有工作产物都在工作目录内。
独立复核、出题、评分使用没见过旧判断、期望卡或版本答案的新上下文。
宿主做不到时照常记录产物，但相关步骤标「未独立验证」，不能据此宣称验收通过；
前置淘汰时已知不满足验收前提，就停在这一步交回限制。

| 阶段 | 输入 | 做什么 | 产出 | 检查 | 不过就停 | 用户确认 |
|---|---|---|---|---|---|---|
| 准备 | 原书、目标、报价 | 核配置、转换和抽查 | book.yaml、Paths.source、缺损记录 | bookconf check；pdf_convert page 与原 PDF 抽核 | 路径、页码或材料缺损未解决不提取 | 胃口及必测范围 |
| 前置淘汰 | 冻结现行版本、宿主 | 按 [宿主说明](references/host.md) 小跑加载/读取；先按 [分组任务书](references/briefs/grouping.md) 列旧能力基准 | 模型/宿主版本、消费记录、能力清单、入口预算 | runner 成功最终事件；chain 激活与成功 Read；独立性和 description 长度 | 插件加载、可观察性、独立上下文或入口容量不足就停 | 新的重大取舍才问 |
| 0 整书理解与分组 | Paths.source、旧能力清单 | 按 [整书任务书](references/briefs/stage0-notes.md) 完整读，合并任务，再冻结 O/N | Paths.overview、任务表、分组依据 | stage1 tasks；人工核来源和分组全量 | 编号重复、漏读、任务/旧覆盖基准未齐不提取 | 范围和重点 |
| 1 提取 | 已确认 overview、原文 | 按 [提取任务书](references/briefs/stage1-extract.md) 查五类、回查跨章条件 | Paths.candidates、Paths.glossary、分组输入 | stage1 coverage、split | 坏 YAML、遗漏或无候选先补读；合法参考缺口先处置范围，不造方法过关 | 改范围才问 |
| 1.5 验证 | 分组候选、原文、任务 | 按 [验证任务书](references/briefs/stage15-verify.md) 三重验证，逐项定去向 | Paths.verify_out、coverage-audit、flags | verify_units aggregate；人工核具体演练 | 汇总问题、重要缺口未处置或无 verified 时不凑卡 | 新的范围取舍 |
| 对抗复核 | 精简输入、原文 | 按 [复核任务书](references/briefs/recheck.md) 从头判每一步，应用并汇总 | Paths.recheck_out、收窄与边界 | verify_units apply-recheck、aggregate；独立性 | 记录缺失、未独立或应用失败不拿来放行 | 复核范围/合卡粒度有默认照默认 |
| 2 写卡 | 采用的单元、原始复核 | 按 [写卡任务书](references/briefs/card-writing.md) 按意图合卡，各分支保留契约 | Paths.card_plan、Paths.cards、Paths.meta | check_cards 的 quotes、steps、plan；人工核摘句词数 | 摘句、步骤标记或计划失败，修后重跑 | 无新取舍不问 |
| 传播核对 | 卡和原始复核 | 按 [传播任务书](references/briefs/propagation.md) 核收窄、缺口和作用域，定点修卡 | findings、fixes、修订卡 | verify_units show；逐分支语义核对；check_cards 重跑 | 参考内容进了执行步骤、分支限制错位或未修就停 | 新的内容取舍才问 |
| 3 接入与公开化 | 采用卡、notes 来源、配置 | 按 [消费方任务书](references/briefs/consumers.md) 生成入口，改引用及冲突旧摘要 | 卡、notes、选卡表、description、消费引用 | integrate；本次文件残留扫描；重复生成/引用链测试和抽读 | 残留、断链、语义走样或不复现就修，不改期望 | 不据生成批准迁移 |
| 4 候选内容评审 | 公开化候选、差异、检查证据 | 按 [评审任务书](references/briefs/content-review.md) 独立读，集中修复再冻结 | 意见、修复、冻结候选 | 重跑受影响的确定性检查和语义核对 | 必须改未解决不进入付费验收 | 新的重大取舍才问 |
| 5 可达测试 | 冻结任务/旧保护能力、候选 | 按 [出题任务书](references/briefs/question-writer.md) 独立出新题，旧题单列回归；测入口与消费方 | 激活/读卡统计、路线判断、诱饵记录 | reach score；chain；OTHER 按能否完成任务人工核 | FAILED 补完整运行；必要路线或保护能力未解决不进回答对比 | 超报价先问 |
| 5 回答对比 | 冻结两版、O/N、题目、必测范围 | 独立 [写评分项](references/briefs/rubric-writer.md)、同批交错运行、遮蔽后 [盲评](references/briefs/grader.md) | 逐题质量、两组计数、归因和费用 | grading leaks、aggregate --protocol B；完整性与可核性三项 | 必测不全、未决、实质退步或任一组不过，不批准原范围 | 按三种走向收口 |
| 6 交付与发版 | 验收过的实际组合 | 记录验证边界、删除/保留的任务和导出提醒；按目标仓库开发回路交付 | 经授权的发布组合与交接 | 相关回归、引用链、全仓库测试及发版校验 | 验收后模型可见修改使相关证据失效，冻结修复后同批重验 | 回归不过的走向；发布按授权 |

失败先修对应输入或实现，再跑同一检查；不能先跳到更贵阶段，也不通过改期望或削必测范围来通过原范围。
阶段 1 的纯参考任务会触发覆盖警报，书面说明不等于脚本过；先保留缺口并完成范围处置。
方法口径看 [references/method.md](references/method.md)，五类字段看 [references/candidate-schema.md](references/candidate-schema.md)，
六段卡、命名、计划和元数据看 [references/card-format.md](references/card-format.md)。

## 检查能证明什么

脚本通过只说明它查的那件事成立。摘句命中全文不等于命中标注页；页码在场不等于那页支持该动作；
任务映射齐不等于内容能完成任务；残留为零不等于改写没改坏句意；运行文件存在不等于有最终成功回答。
分别核摘句、步骤来源、复核结论传播，再测 description 激活、选路、成功读卡、回答实际用上，以及消费方按引用读卡。
只作参考的内容要有读者能读到的 notes 去处；私有目录里的存档不能算已交付。

## 生成与验收的四条约束

- **确定性复现。** 冻结源材料、采用的模型产物、配置和工具版本后，确定性生成须可复现；模型重新提取不承诺逐字节一致，采用结果单独保存。
- **读者可用与语义保真。** 公开化单独核读者可用性和语义保真，通用替换与有 why 的具体裁决分开，原文摘句不替换，限制不抹去。
- **修改后重验。** 修改模型看得见的入口、资料、消费指令或运行条件，相关证据失效；集中修复后两版同批交错重跑，保留旧批结论。
- **质量与归因分开。** 先盲评质量再解释消费链；自然链未调用/未读卡的差题仍计入，好的也不能归功于未读材料，强制查阅只作诊断。

完整冻结规则、两种历史/现行协议及报告口径见 [references/acceptance.md](references/acceptance.md)。
口径 B 要求必测旧覆盖组 O、新增组 N 各自不差，且没有确认的单题实质退步；缺失、未决不放行。
可核性还须核关键判断和行动的正确来源、全部摘句的版本与页段、复核收窄/缺口/转换缺失传到卡上。

走向互斥：全部迁移需两组、可核性和最终消费链都过；部分迁移只适用于可定位的局部问题，保留该任务旧参考，
并用事先预留的一次验收测最终混合版本；新增组整体退步、保护能力受损、证据不足或必要验证不全则不迁移。
钱紧只能砍事先标为可选的探索题，必测未齐只能记未完成。走向由用户定，不把脚本 pass 直接当发布授权。

## 交回

交回采用输入和候选快照、各阶段产物路径、实际命令/退出码、确定性检查、语义与独立性边界、
O/N 逐题判定及两组计数、未决/缺口、消费链和费用，以及实际交付范围。
例子用编造的微型书，公开仓库不带本机路径、私有任务材料或书全文。
提醒 Codex 用户重新导出 agent 并开新会话；插件更新不会自动改项目里的导出副本。
