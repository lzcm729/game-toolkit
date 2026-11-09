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
`when_to_use_anchor` 定位触发说明，`when_to_use_line` 提供新触发句；
`description_file` 为可选描述文件路径，`null` 表示不替换描述。

`convert` 留给 PDF 字体、页段、页码偏移和说明文字等参数。
`answer_compare` 留给冻结的回答对比协议。两者是 mapping，由对应阶段解释。
回答抽样时 `answer_compare.target_source` 是能力清单里的本书来源，比较时不区分大小写；
`quotas` 是 `组名: [必测数, 可选数]`，包括本书旧覆盖组、`O-other` 和 `N`。
`exclude_items` 可用通配符，`other_books` 指定其他书的最少题数。
输入 YAML 清单顺序和 seed 一起冻结；目标书和其他书没有在抽样脚本里写死。
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
