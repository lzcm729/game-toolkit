# 工作目录与每本书的配置

工作目录放在仓库外，里面的 `book.yaml` 指向交付的插件源码副本。
源码副本要有 `.git`（worktree 的文件也可以）、`.claude-plugin/plugin.json`、
`skills/game-design-theory/`，路径不能含 `plugins/cache` 或 `plugins/marketplaces`。
工作目录和 `Paths` 的每个解析结果都不能位于目标源码或加载脚本的源码仓库内；
绝对路径覆盖也要经过检查。所有脚本 CLI 在写文件前调用 `open_workdir`。

```text
book.yaml
source/<book_id>.md
BOOK_OVERVIEW.md
candidates/                  # 五类候选和 glossary.md
candidates/_scope.yaml       # 可选的纯参考/不收范围处置
verify/input/                # 分组候选
verify/out/                  # 首轮验证
verify/recheck/input/        # 独立复核输入
verify/recheck/out/          # 复核记录
stage2/CARD-PLAN.md
cards/
meta/
landing/notes.md
```

## 机械参数

`book_id` 是默认源文件名，`prefix` 是发布卡文件名前缀，`target_root` 是交付源码。
`display_author`、`display_title` 是必填的非空字符串，明确 notes 标题的作者显示名和书名。
相对路径以工作目录为起点；路径中的反斜杠按 `/` 处理。
`paths` 可覆盖上面各路径：`source`、`overview`、`candidates`、`verify_in`、
`verify_out`、`recheck_in`、`recheck_out`、`card_plan`、`cards`、`meta`、`glossary`、`notes_out`、`scope`。
未覆盖的字段取上图默认值。

`mask_names.authors` 和 `mask_names.titles` 列出盲评需要遮蔽的全部作者和书名，含另外三本书。
它们只管遮蔽，可列全名、姓氏和书名别称；顺序不影响 notes 标题。
`verify_groups` 和 `entry_groups` 按 YAML 文件顺序保留，键空间不同：

- `verify_groups` 的值是候选 `source_chapter` 解析出的章标签：数字章 `"1"` 等，
  非数字部分的规范键 `pre`、`p1`…`p3`、`quiz`、`end`、`books`、`sources`，按书增减。
- `entry_groups` 的值是单元号的两位章号，如 `"00"`、`"01"`。它用于发布选卡表。

同一套分组里一个章标签只能出现一次。数字标签必须加引号，以免 YAML 读成整数。
复核批次按文件名自然排序，后面的批次生效；`batches` 只筛选、不重排，重跑旧批次不回滚新结论。
覆盖 `verify_in` 时，判宽信号文件写到 `verify_in.parent/_flags.md`。
`old_files` 是待接替参考文件名的列表。

`skill_md` 描述目标 SKILL.md 的替换位置：`quick_ref_start/end` 包围旧速查，
`quick_ref_file` 提供新速查；`table_start/end` 包围选卡表，`table_heading` 提供标题；
`when_to_use_anchor` 和 `when_to_use_end` 是本书触发行槽位的前后锚点，`when_to_use_line` 提供替换行；
`description_file` 为可选描述文件路径，`null` 表示不替换描述。

`convert` 不带任何书的排版默认值；只有文本时可为空，调用 PDF convert 时以下字段全部必填。
start_page 是从 1 起的 PDF 文件页序，stop_page 是不包含的终点，null 表示到末尾；
page_offset 从 PDF 页序减去得到印刷页，偏移之前输出 fm-N。字体规则按顺序匹配，size 为 null 时不比较字号。
page_number 仅去掉匹配该字体及整行 pattern 的页码字形；classes 可显式为空，不代表自动识别字体。
title_min_size 是跳过大标题的字号阈值；header_max_y 是页眉上界；para_indent_x 是段首缩进横坐标。
outline 明确目录标题的两条匹配规则；不需要目录识别时填永不匹配的 `(?!)`。header 是可选的文件说明前缀。

```yaml
convert:
  start_page: 1
  stop_page: null
  page_offset: 0
  title_min_size: 22
  header_max_y: 30
  para_indent_x: 90
  classes:
    - {kind: h3, font_contains: ExampleBold, size: 14, tol: 0.2}
  page_number: {font_contains: ExampleRegular, pattern: '\s*\d+\s*'}
  outline: {part_pattern: '(?!)', chapter_pattern: '^(\d+) (.*)$'}
  header: '# 编造的灯光手册\n\n'
```

classes.kind 只支持 h3、h4、callout、vignette、skip，其他排版先显式报错，不推测恢复。
`answer_compare` 留给冻结的回答对比协议。两者是 mapping，由对应阶段解释。
回答抽样默认按冻结 O/O-partial 任务取旧池；`answer_compare.target_source` 只作来源信息。
`grading pick --old-pool migration` 才按 target_source（不区分大小写）过滤，专供历史迁移复现，不能作为新书默认。
`quotas` 是 `组名: [必测数, 可选数]`，包括本书旧覆盖组、`O-other` 和 `N`。
`exclude_items` 可用通配符，`other_books` 指定其他书的最少题数。
输入 YAML 清单顺序和 seed 一起冻结；目标书和其他书没有在抽样脚本里写死。
口径 B 汇总必须从冻结的 answer_compare 核必测范围：可用 quotas，或用更严格的
`required_items: {O: [t01-01], N: [t02-01]}` 写必测 item_id 清单（含 p- 保护题）。
某组必测为零时须有 `empty_groups: {N: 本书冻结范围没有新增任务}` 这样的非空理由，否则 incomplete。
不能从已收到的成绩反推配额或空组理由；看到答案前冻结配置，缺 difference/regression 的成绩不放行。
`residue_allow` 列出允许保留的书内短语，扫描只豁免命中的片段。
除列出的必填字段外，列表默认 `[]`、这两个阶段配置默认 `{}`；未知配置字段报错，避免拼错后静默使用默认值。

## 内容裁决

`Paths.scope` 默认 `candidates/_scope.yaml`，是可选的列表。补读后确实没有可执行内容的任务，
每项写 `task_id`、`decision`（`reference_only` 或 `out_of_scope`）、非空 `reason`，可加 `pages`。
未知任务、重复任务、非法 decision、空 reason 都使 coverage 失败；没有此文件时仍要求可执行候选。
有效处置单独列在 coverage 输出中，只免除该任务的可执行候选缺口，不免除坏 YAML 等问题。
在阶段 0 确认范围时或之后把处置给用户看，不能静默缩范围；只作参考的内容仍须落到读者可达的 notes。

```yaml
- task_id: t03-02
  decision: reference_only
  reason: 补读后只有灯的象征观点，没有可执行步骤；交付到 notes
  pages: [9]
```

`rulings` 单独保存针对具体内容的文字裁决，每条有 `find`、`replace`、`why`、
`scope`（`cards`、`notes` 或 `all`）。`why` 必须非空，说明这条转换的来由。
通用措辞规则留在公开化脚本，具体裁决不能混进去。

## 微型书完整例子

以下书、人名和内容均为编造；目标路径以本机实际源码副本替换。

```yaml
book_id: microbook
display_author: Mira Example
display_title: The Lantern Workshop
prefix: micro-
target_root: ../plugin
mask_names:
  authors: [Mira Example]
  titles: [The Lantern Workshop]
verify_groups:
  G2: ['2', '3']
  G1: ['pre', 'p1', '1']
entry_groups:
  灯光试验: ['02', '03']
  起步: ['00', '01']
old_files: [old.md]
paths: {}
skill_md:
  quick_ref_start: '<!-- QUICK START -->'
  quick_ref_end: '<!-- QUICK END -->'
  quick_ref_file: stage2/quick-ref.md
  table_start: '<!-- TABLE START -->'
  table_end: '<!-- TABLE END -->'
  table_heading: '## 按任务选卡'
  when_to_use_anchor: '## 何时使用'
  when_to_use_end: '旧触发句。'
  when_to_use_line: '需要做灯光试验时使用。'
  description_file: null
rulings: []
residue_allow: []
convert: {}
answer_compare: {}
```

先运行 `python scripts/bookconf.py check <workdir>`（脚本路径相对本 skill）。
检查失败退出 1，不创建任何文件。

随包命令示例从本 skill 目录执行；`scripts/` 指随包脚本，`<workdir>` 替换成仓库外的工作目录。
任务书中的 `compare/`、`reach/`、`grouping/` 等材料都在该工作目录下，命令参数显式带 `<workdir>/`。
`<baseline>`、`<candidate>` 是隔离并冻结的插件源码快照；含空格的路径加引号。
这些占位参数要先替换，不能把示例路径当真实交付目标。

### 章节标签与跨组任务

`chapter_map` 可把原始 `source_chapter` 全文标签显式映射到 `verify_groups` 的规范键，例如 `{"第一章": "1", "Appendix A": "appendix-a", "Part VI": "p6"}`。先查精确映射，再用既有数字章/英文 Part 标签解析；不能解析或未分组就失败，不猜其他标签。

跨组任务的 coverage 只归一个组：由主执行方指定 `verify_groups` 顺序中第一个含该任务候选的组为归属组，该行列出跨组的全部单元 ID；其余组保留单元但不重复 coverage 行。汇总仍检查全局引用和唯一归属。

复核应用前要求同名 input/out 的 batch 与文件名一致，单元集合相等、无重复。输入字段为去判断后的六字段；输出需有复核任务书示例的全部字段：unit_id、decision_after、steps、key_judgment、narrowing、walkthrough、must_go_to_boundary、gaps、covered_by、reason；steps、must_go_to_boundary、gaps 必须是列表，reason 非空。`verify/recheck/_applied.yaml` 保存输入和输出原始字节的联合摘要；已应用批次任何改动都须换新批次。旧产物若已标应用而没有摘要，不能追认，须建新批次。

所有显式工作产物输出参数也禁止落在本源码仓库、配置的 target_root 或其他插件源码副本内；接入的公开交付文件由 integrate 单独管理。

### 公开 notes 与入口重跑

`notes` 是保留 slug，不能用作卡名。notes 的显示标题也经过 scope 为 notes/all 的 rulings。参考条目完整保留公开摘要和独立的处置理由，不按第一句或字数截断适用限制。范围处置的 reason 也需写成公开语言；「补读」等流程残留会失败，可用带 why 的 rulings 改写，不能以删掉适用限制消除问题。

`_scope.yaml` 的 reference_only 项可写 `related: [steady-shadow]`，只能引用计划中的卡 slug；未提供时相关卡写「—」。范围条目没有单元，不承诺自动推导相关卡。

`skill_md.when_to_use_anchor` 与必填的 `when_to_use_end` 指定本书触发行槽位前后保留的完整行，必须各自唯一且按此顺序出现。接入替换两锚点之间的整段，首次槽位可空，重复接入或改文案都不累积。两锚点之间只能有本书那一行，不能夹其他书的触发项。例：前锚点 `- Compare lantern shadows`，后锚点 `- Plan a playtest`，生成的微型书行放在它们之间。缺字段或锚点时明确失败；不猜哪行属于本书。

apply-recheck 不筛选批次时，复核输入必须都有输出；没有输出批次、输入输出皆空也会失败。对缺少冻结摘要的旧已应用记录，保留原始记录，显式指定一个新批次重新复核；只给本次实际应用的批次记摘要，不为旧记录追认摘要。batches 仍只筛选，不重排。
