# 五类候选格式

字段与五种视角改写自 [cangjie-skill](https://github.com/kangarooking/cangjie-skill) 的五类候选提取说明；
文末保留 MIT 许可。这里补本插件的任务映射、分组键及无专用索引的阅读方式。
例子均来自编造的微型书，不是任何真实书籍的引文。

## 文件与共用约定

在工作目录下的 `Paths.candidates` 写 `frameworks.md`、`principles.md`、`cases.md`、
`counter-examples.md`；术语写到 `Paths.glossary`。每个文件用 yaml 围栏包住列表，条目以 `- id:` 起头。
分段提取时 framework、principle 可先放 `Paths.candidates/parts/frameworks-<段>.md` 和
`parts/principles-<段>.md`；该类存在 parts 时审计只读 parts，不再读合并文件，避免双计。
其他三类由主执行方合并为上述单一文件；没有条目的类也保留空列表围栏并说明查过的位置。

每条都有稳定、唯一的 `id`、`source_chapter`、`task_ids`；说明写中文，原文逐字保留。
方法和原则号如 `f1-01`、`p1-01`，案例 `c-01`，反例 `ce-01`，术语 `g-01`。
`source_chapter` 统一写 `Ch1 Observe / Shadows, p.1` 这类可解析的章/节/印刷页码；
非数字部分使用 `pre`、`p1`、`quiz`、`end`、`books`、`sources` 等已在 `verify_groups` 配置的规范键。
任务号来自 `Paths.overview`，没有对应任务时填 `[]` 并写 `task_note`，不能编一个任务号糊过去。

原文 `source_quote`（术语的 `author_definition`）逐字核对；英文不超过 100 词、中文摘句不超过 150 字，
可用 … 省略但不改词。记录版本和来源位置，可另加 `source_id`；不能只有书名。
`summary` 用自己的话说明机制，`tags` 至少一个。反例的说明由下面的专门字段承载。
`chunk_id` 是可选的历史定位信息，本流程不要求建立块索引。
缺图、缺表、缺单位、条件冲突写 `missing_conditions`，不从常识补全。

## 方法：frameworks.md

负责思维结构、决策框架、流程和排障路径；同章独立的方法拆开，跨章同一方法保留所有出处。
流程候选补 `inputs`、`outputs`、`steps`；排障保留症状、判断条件、动作和升级处理。
只抄到方法名也可记候选线索，但必须明确缺什么，不能宣称完整。

```yaml
- id: f1-01
  title: 比较影子的变化
  type: framework
  source_chapter: "Ch1 Observe / Shadows, p.1"
  source_quote: "Keep the lantern still while you compare the shadows."
  summary: 固定灯的位置，再比较遮挡前后的影子。
  inputs: [同一盏灯, 两次观察]
  steps: [固定灯的位置, 比较两次影子]
  outputs: [影子差异记录]
  missing_conditions: [原书未说明记录表格式]
  tags: [observation, shadows]
  task_ids: [t01-01]
```

## 原则：principles.md

负责原则、清单、具体规则、公式、指标和工作模板。描述性的感叹不能直接包装成规则。
计算补 `inputs`、`formula`、`units`、`output`；表格保留字段含义、填写及核验规则。
type 可为 `principle`、`checklist`、`calculation`、`template`，五类列表中的归属仍是 principle。

```yaml
- id: p2-01
  title: 一次只改一项
  type: principle
  source_chapter: "Ch2 Test / Shutters, p.2"
  source_quote: "Change one shutter at a time."
  summary: 比较前后只改变一块挡板，避免无法分清变化来源。
  tags: [test, shutters]
  task_ids: [t02-01]
```

## 案例：cases.md

`example_kind` 必填 `firsthand`（作者亲历）、`reported_case`（作者转述）或 `worked_example`（原书例题）。
`bound_to` 是所说明的方法主题列表，验证后由 supports 对应到单元；纯背景说明原因。
结果只写原书交代的；没说就写「原书未说明结果」，例题不冒充真实事件。

```yaml
- id: c-01
  title: 挡板试验例题
  type: case
  example_kind: worked_example
  source_chapter: "Ch2 Test / Shutters, p.2"
  source_quote: "The second screen shows a narrower shadow."
  summary: 书内例题比较两块屏幕上的影子，不是作者报告的真实项目结果。
  bound_to: [一次只改一项]
  outcome: 第二块屏幕上的影子较窄。
  tags: [case, shutters]
  task_ids: [t02-01]
```

## 反例：counter-examples.md

记录作者明确警告的失败、错误机制、反面典型；一般吐槽不等于有机制的反例。
`failure_mode`、`mechanism` 必填，没讲机制就明确原书未说明；`warning_signs` 和 `bound_to` 用列表。
候选 type 写 `counter-example`；分组 YAML 的列表键是 `counter_example`，两者不要混。

```yaml
- id: ce-01
  title: 移动灯造成比较失效
  type: counter-example
  source_chapter: "Ch1 Observe / Shadows, p.1"
  source_quote: "Moving the lantern changes the comparison."
  failure_mode: 把灯的位置变化误判成挡板的效果。
  mechanism: 两次观察之间的条件不再相同。
  warning_signs: [灯的位置没有固定]
  bound_to: [比较影子的变化]
  tags: [counter-example, observation]
  task_ids: [t01-01]
```

## 术语：Paths.glossary

收作者明确定义、用法特殊或构成核心论点的词，不给一般词汇凑术语数。
`term` 是词名；`author_definition` 是原文定义；`key_distinction` 讲与常用义的差别，
`why_it_matters` 说明误读会怎样影响任务。没有差异就如实写，不造区别。

```yaml
- id: g-01
  term: stable shadow
  type: term
  source_chapter: "Ch1 Observe / Shadows, p.1"
  author_definition: "A stable shadow stays in the same place."
  key_distinction: 这里指位置稳定，不是指影子更暗。
  why_it_matters: 比较时不能把位置变化当亮度变化。
  tags: [term, observation]
  task_ids: [t01-01]
```

## 自查与交接

完整读完负责范围，再检索关键词并回读相邻段；覆盖优先于省 token。
五种视角可重叠，一处完整依据可以保留，不按出现次数或自评新颖性筛选。
阶段 1 只出候选，不写卡、不提前判 verified。主执行方运行：

```text
python scripts/stage1.py coverage <workdir>
python scripts/stage1.py split <workdir>
```

YAML 解析、未知任务和未映射章标签须修正。仅支持材料或无候选也会使覆盖审计退出 1：
先补读；确实没有可执行内容时交回参考去向和范围缺口，不能造方法来消警报，也不能把书面解释称为脚本通过。
未经范围处置不继续花下一阶段成本。详情见 [briefs/stage1-extract.md](briefs/stage1-extract.md)。

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
