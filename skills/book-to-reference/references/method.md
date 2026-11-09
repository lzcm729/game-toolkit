# 从整书理解到可执行的方法

本文件的「整书理解」「五类候选」「三重验证」「六段卡」改写自
[cangjie-skill](https://github.com/kangarooking/cangjie-skill) 的阶段 0、1、1.5、2 方法说明。
严格复核、按意图合卡及分支边界来自本插件的导入实践；不采用一书一 skill、晋级门或外部编译器。
改写部分的 MIT 许可全文在文末。候选字段见 [candidate-schema.md](candidate-schema.md)，
卡与元数据见 [card-format.md](card-format.md)。

## 阅读与证据

路径都从仓库外工作目录的 `book.yaml` 解析，字段见 [workdir.md](workdir.md)。
`[p.N]` 是印刷页码；前置页可能为 `[p.fm-N]`，不能拿 PDF 文件页序替代印刷页码。
先检查转换质量，记录缺图、缺表、误标为引文的表格，以及所用版本。
按自然章节分段完整读 `Paths.source`，每次取宿主能完整显示的范围；输出截断就缩小范围重读。
Read 或终端均可，选择能保留长行的方式。用 Grep 找关键词后回读整节、相邻段、图表说明和脚注；
检索不能替代负责范围的完整阅读。跨章搜索关键判据、阈值、单位及反例，冲突并列保存。
只依据材料，不用对该书的记忆补缺口。自己的推断标「我的判断」，不能充当作者证据。

## 整书理解（阶段 0，改写自 cangjie-skill）

先弄清作者在回答什么问题，再提取方法：

1. 结构：书的类型、主旨、主要论点，以及它们并列、递进或反驳的关系。
2. 解释：作者特有的术语、核心命题、论证和证据；定义按作者用法，不按字典义。
3. 批判：文本支持的时代前提、立场盲点、未证假设和最强反驳。无证据时记待核，不凑批判条数。
4. 应用：哪些内容能支持判断或行动，哪些只作背景或参考；列全读者任务，不从已通过单元反推范围。

`Paths.overview` 的任务表每条含 task_id、读者任务、原文位置、预期交付物、重要性依据和缺条件。
任务号用 `t01-01` 这类两位章号加两位序号；前言与非章节部分可用 `t00-01`、`t99-01`，跨段统一编号。
用户确认范围和重点后提取；已有委托覆盖该取舍时直接沿用。确认范围不能替代来源验证。

## 五类候选（阶段 1，改写自 cangjie-skill）

保留方法、原则、案例、反例、术语五种视角；可以按章组织工作，但每章五类都要检查。
宁多收有证据的候选，去重和去向留给验证。不要求重复出现或作者独创；一次完整说明也可能有用。
不同候选指向同一段原文不算多份独立证据。跨段合并时保留所有出处、前置条件和原候选号。
覆盖优先于省 token，空结果要说明检查过什么，不靠提高或降低数量过关。

## 三重验证（阶段 1.5，改写自 cangjie-skill）

| 检查 | 要回答的问题 | 不能怎样放行 |
|---|---|---|
| V1 来源充分性 | 可定位的原文是否支持限定范围内的每一步、条件、公式和判断？ | 名称、口号、半条规则不够；重复转述不增加独立证据 |
| V2 可执行性 | 固定一组书外的合法输入和完成标准，能否走完并检查输出？ | 不用演练补造规则；纸面 walkthrough 不称真实宿主实测 |
| V3 任务增益 | 固化后具体减少什么遗漏、统一什么口径、帮助什么判断？ | 不要求新颖，不凭自评宣布比基线好 |

输入、单位、分支、输出、失败与判停都要核；计算给可复算预期和容差。
一处完整说明可过，分散的公式和单位也可合读。依据冲突未解决时保留冲突及位置。
案例、反例、术语通常是支持材料；升成方法仍需可执行规则。

| decision | 使用条件 | 下游 |
|---|---|---|
| verified | 三关均过 | 可进入写卡计划 |
| reference | 有来源价值，但只剩观点、态度或空泛结论 | 写进读者能读到的 notes，不伪装成执行步骤 |
| needs_review | 关键规则缺失、转换缺损或证据冲突 | 写具体 gaps、补读位置，不进执行分支 |
| rejected | 无依据、错误归因或被完整覆盖 | 留理由；重复项指向保留的单元 |

关键任务的缺口不能从分母里消失。任务去向要有实际交付路径和完成状态，映射齐不等于完成。
没有 verified 时不凑卡，交回参考与缺口，停止写卡。

## 严格复核（本插件口径）

逐个回答：「现在照原文写 E 段，每一步写得出来吗？」先读整节，再列步骤和来源等级：

| support | 含义 |
|---|---|
| quoted | 原文明说，可定位句子 |
| paraphrase | 原文直接表达这个意思，只换说法 |
| reconstructed | 文字足以重建，必须写出推导及边界 |
| invented | 必须靠常识、推测或其他书补出 |

关键判断缺判据时，只有收窄成「列出作者给的考量，由设计者判断」仍有具体用处才保留 verified。
核心步骤 invented 且收窄后无法执行，判 needs_review；只剩观点则 reference。
经验数字标作者的经验估计；依赖其判停的限制单列。缺图而正文不足以重建不能猜图。
一次完整案例不是降级理由，也不证明普适。作者明确说没有算法的，不能给他造算法。
复核员只见精简输入和原文，不见首轮去向、理由、flags 或别人的答案；没有独立上下文就标「未独立验证」。
无降级配额，也不要求通过率。样本既含存疑信号，也含未自报存疑的内容。

## 六段卡与按意图合卡（六段定义改写自 cangjie-skill）

R 是原文和自译；I 是自己的方法骨架；A1 是有性质标记的原书案例或合成演练；
A2 是具体触发处境及近邻区分；E 是输入、步骤、判停和输出；B 是失败边界和来源限制。
本插件按用户意图合卡，每个 verified 单元保留独立分支，不把相邻章节强拼成作者没有的流程。
分支自己的输入、步骤、输出、收窄和退出条件不能被合卡抹掉。
只对一个分支成立的限制写在该分支或 B 段点名分支；「整卡不适用」只放所有分支共有的限制。
补读只列依赖和组合，近邻区分帮助选路，不排除同样有效的另一条路线。

卡和入口都说明：先围绕用户处境给专业判断和具体做法，卡是方法与依据的来源之一，不是回答模板；
书外建议照常给，但标明不出自本书。原书未说明不等于 agent 不能帮忙。
公开化保留依据不足、经验估计、合成演练和转换缺失；原文摘句不参与措辞替换。
传播核对与内容评审在冻结候选前做，验收规则见 [acceptance.md](acceptance.md)。

## cangjie-skill 许可声明

MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
