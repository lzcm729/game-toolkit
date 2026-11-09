# 能力卡、计划与元数据

工作稿放在仓库外的 `Paths.cards`、`Paths.meta`，先写 `Paths.card_plan`。
卡按用户意图命名，用小写英文与连字符的 slug；发布文件为 `<prefix><slug>.md`，
prefix 通常用作者姓氏加 `-`。微型书例：`micro-steady-shadow.md`。
Rouse 的旧 `player-psychology.md` 没有作者前缀，是保留的旧文件例外；新导入仍用前缀。

## 先定计划

每个 verified 单元恰好分入一张卡，每个单元有分支；reference、needs_review 不作执行分支。
单元属于同一用户意图才合卡，不按章机械合并。计划表保持以下列顺序和单元号形式，脚本据此解析：

```markdown
| # | slug | 卡名 | 用户在问什么 | 单元（分支） | 写卡批 |
|---|---|---|---|---|---|
| 1 | steady-shadow | 比较影子 | 怎么固定比较条件 | u01-01 | W1 |
```

非执行内容另列参考去向，不能塞进「单元（分支）」列逃过审计。
公开 notes 把参考摘要、处置理由和适用限制分别说清，不能靠截取首句消去限制。范围处置没有单元号，可在 `_scope.yaml` 用 `related: [steady-shadow]` 指定计划内卡；没写时相关卡为「—」，不承诺自动推导。
发布生成器按单元最多的章分组；平票优先真实章而非 `00`，再取较小章号。
`entry_groups` 必须覆盖所有分支的两位章号，组序依配置；未映射时写文件前报错。

## 卡正文

不加 YAML frontmatter。卡头、标题、用法句、六段依次排列。
用法句唯一来源是 [card-usage.md](card-usage.md)，写卡时原样粘贴；接入仅在没有「怎么用这张卡」用法句时补入，不再叠加另一句。
以下都是编造示例；摘句应替换成实际原文，不能照抄示例当证据。

```markdown
<!-- capability_id: cap.microbook.steady-shadow | revision: 1 | status: active | units: u01-01 -->

# 比较影子

<!-- 此处粘贴 card-usage.md 的完整用法句 -->

## R — 原文 (Reading)

> Keep the lantern still while you compare the shadows.
>
> 译：比较影子时保持灯的位置不动。
>
> — Mira Example, *The Lantern Workshop*, Ch1 Observe / Shadows, p.1

## I — 方法骨架 (Interpretation)

比较前固定观察条件，避免把条件改变误认为被测对象的效果。
解释必要术语，以及分支之间的先后、分流或独立关系。

## A1 — 书中案例 (Past Application)

原书未提供案例，以下是合成演练：固定灯和屏幕，比较换挡板前后的影子。
合成演练展示已知规则，不证明真实项目会取得同样结果。

## A2 — 触发场景 (Future Trigger)

- 你换了挡板，却分不清影子变化来自哪里；compare shadows。

**与相邻卡的区分**
- 与记录卡的区别：本卡控制比较条件，记录卡整理观察结果；两条路线可组合。

## E — 执行 (Execution)

### 先选分支

| 你的问题像…… | 走 |
|---|---|
| 两次影子无法比较 | 分支 1 |

### 分支 1：固定比较条件（u01-01）

- **输入**：两次观察和同一盏灯；缺少观察条件先问。
- **步骤**：
  1. 固定灯的位置，完成标准是比较过程中灯没有移动。(p.1)
  2. 把两次观察写进同一张表，列「条件、影子差异」。（约定）
- **判停 / 转向**：灯移动了就不能把变化只归因于挡板；先重做比较。
- **输出**：条件记录和影子差异；原书未说明记录表格式。

## B — 边界 (Boundary)

- 整卡限制只放对所有分支都成立的条件。
- 分支 1：若图在转换时丢失而正文不足以重建，标「原图缺失（转换时丢失）」并停止该判断。
```

R：1–3 条核心摘句，每条至多 60 个英文词、整卡至多 150 词；逐字、标版本和印刷页码，自译中文。
R 段摘句用 `>` 块，不同摘句用空的 `>` 行分开；换行续写的同一段合并核对。
自动核对只支持至少五个英文词的摘句；短句、非英文或双语原文必须人工逐页核对原文、译文及页码，
在该条摘句末尾写 `<!-- quote-manual: 核对说明及不支持自动核验的原因 -->`，非空说明才放行，输出单列 manual 数。
不得用标记跳过可自动核对的摘句。前置页写 `p.fm-2`，正文写 `p.2`，范围可写 `p.fm-2–fm-3`；R 空或无摘句会失败。
I：5–15 行解释骨架，不再复述 E。A1：注明作者亲历、转述或例题，书里没说结果就写未说明。
没有案例可用明确标注的合成演练，不冒充作者经历或独立证据。
A2：3–5 条真实处境，中英语言信号和近邻区分；有效的相邻路线不应被排除。
E：每分支保留输入、完成标准、判停/转向和输出，每步有支持它的页码，或明确的非原书标记。
B：逐条承接复核的 narrowing、must_go_to_boundary、gaps 和原文的反例；只影响一个分支的限制要点名分支。

## 来源与缺损说明不能混

| 标记 | 用途 |
|---|---|
| 约定 | 为交付方便加的字段、排版等实现安排；不冒充作者的判断规则 |
| 原书未说明 | 查过跨章条件后，作者确实没给判据、阈值或做法 |
| 原书未附图 | 原文自己说明该图未收入书中；这是原书的范围，不是转换丢失 |
| 原图缺失（转换时丢失） | 内容在缺失的图表中，正文不足以恢复；不能写成作者没说 |
| 合成演练 | 书外构造的输入和演示，只检验已知规则能否走通 |

原文自述未附图时用「原书未附图」；原 PDF 有图而转换结果丢了才用「原图缺失（转换时丢失）」。
只有文本、又无原文自述时，不猜丢失发生在哪一步，记录「无 PDF 可核」及可见缺口；正文不足以支持的判断仍须停止。

作者的经验数字标「作者的经验估计」，不写成普适阈值；两处冲突并列，不替作者挑一个。
原文只给考量就只承诺列出考量、由设计者判断；自己的建议标不出自本书。
公开化改写内部去向和状态，但不能删掉这些来源性质和限制；原文摘句不参与替换。

2–3 分支目标 3000–5500 字符；4–5 分支不超过 7500 字符。先删段间重复，不能为变短删条件。
短书的小方法按实际内容写，不为凑篇幅添规则。

## 元数据

工作目录下的 `Paths.meta/<slug>.yaml` 是独立文件；卡头与元数据的 units、revision 同步。
intents 用设计者会问的话，also_read 只放必要依赖或组合，选择表同时说明近邻差别。
每卡给两三条实际问法；接入会拒绝缺失、全空或类型错误的 intents。
A2 的 `**与相邻卡的区分**` 后用列表写近邻差别，首条用于选卡表；同组多卡不能留空，单卡组可用“—”。
单元的 supports.terms 列实际用到的术语编号，notes 据此选入术语。
不设置独立 skill 的 promotion 字段。

```yaml
capability_id: cap.microbook.steady-shadow
revision: 1
status: active
slug: steady-shadow
title: 比较影子
units: [u01-01]
importance: high
importance_rationale: 对应 t01-01，条件变化会让比较失效。
one_liner: 先固定观察条件，再比较影子。
intents: [两次影子为什么无法比较, 换挡板时怎么固定比较条件]
keywords: [影子, compare shadows]
also_read: []
card: cards/steady-shadow.md
frontmatter:
  description: 比较条件是否一致时用；只要整理记录时看记录卡。
  tags: [observation]
source_evidence:
  - source_id: microbook
    location: "Ch1 Observe / Shadows, p.1"
```

```text
python scripts/verify_units.py show <workdir> u01-01
python scripts/check_cards.py <workdir>
```

更细的语义核对见 [briefs/propagation.md](briefs/propagation.md)。脚本不会证明页码支持了该动作，
也不核全部篇幅、英文词数和语义承接，这些仍须人工检查。

六段定义沿用 cangjie-skill，经本插件的多分支格式改写；许可如下。

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
