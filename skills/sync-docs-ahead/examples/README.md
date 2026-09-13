# gap-analysis.config.yaml — Schema 文档

`sync-docs-ahead` 的项目级配置文件。一份 YAML 描述系统与设计、参考、范围、代码的关系，
项目特化只放在配置里。配置优先，自动发现只在无配置时兜底。

## 文件位置

默认在工程根：`gap-analysis.config.yaml`；也可通过 `--config FILE` 指定。
工程根由项目的 `game-toolkit.yaml` 解析后作为 `--project-root DIR` 传入，不从配置文件位置推测。

## 顶层结构

```yaml
$schema_version: 1
docs_root: design-export
manifest: design-export/_manifest.json
systems:
  - name: 系统甲
    docs: [系统甲/规格.md, 系统甲/内容表/*.csv]
    refs: [参考/参数依据.md]
    scope: 规格与内容表全篇，参考页不单独评分。
    code: [src/system-a/**, config/rules.yaml]
```

## 配置说明

| 字段 | 类型 | 说明 |
|---|---|---|
| `$schema_version` | integer，必填 | 当前为 `1` |
| `docs_root` | string，可选 | 设计目录，相对工程根；缺省由主流程沿 CLAUDE.md 指针取得，再传 `--docs-root`，脚本不猜自然语言指针 |
| `manifest` | string，可选 | manifest 文件，相对工程根；缺省读 `docs_root/_manifest.json`，显式配置但文件不存在时报错。命令行给了 `--docs-root` 且其下有 `_manifest.json` 时以那份为准，这样对历史快照目录补记运行记录时不会读到当前清单 |
| `systems` | array，必填 | 每项对应一份系统报告；可把同一规则页按范围分给多个系统 |
| `systems[].name` | string，必填 | 系统名，也是报告文件名（不含 `.md`）；须唯一、合法单个文件名，不能用汇总保留名或下划线开头 |
| `systems[].docs` | string[] | 评分文件或 glob，相对 docs_root；不填或未匹配时无法确认版本，计划重跑 |
| `systems[].refs` | string[]，缺省 `[]` | 只参考、不评分，相对 docs_root；说明放 scope，不夹带在路径中 |
| `systems[].scope` | string，必填 | 一句话说明评分范围与排除边界 |
| `systems[].code` | string[]，缺省 `[]` | 路径、目录或 glob，相对工程根；空列表表示未配置源码范围 |

路径允许 `/` 或 Windows `\`，YAML 中含反斜线时用单引号。系统路径不得绝对化或用 `..` 越界。
`--docs-root` 优先于配置的 docs_root；配置文件本身的路径按命令当前目录解析。
跨系统共享文件可以重复列入，但 scope 须明确各自评分边界。

## 稳定要求键与运行记录

脚本从要求末尾括注取第一个文件，manifest 的 docs／sheets／embedded_sheets 都按 `file` 匹配，优先完整路径，
否则按文件名匹配并取路径排序后的第一项；无匹配时用文件名去扩展名。同名内容表应尽量引用完整相对路径。
Markdown 锚点取引用行处或之前最近的标题：有编号取编号，否则取标题正文前 12 字符去空白、标点及符号。
读不到文件或没有标题为 `L0`；CSV 为 `r<行号>`。要求去末尾出处、数字、标点、符号、空白后取 SHA1 前八位。
数值变了键不变；同节内行号漂移不换键，章节改编号或 CSV 插行仍可能换键。
支持 `规格.md rev106:65-70`、`规格.md（revision_id: 106）:65`、`表.csv 第2-6行 名称列`，范围以首行定位。
新报告逐行写文件名和正行号；出处无法解析或缺少 Code-only 节会失败。旧报告若只写 `:行号`，
通过 `--legacy` 兼容读取并告警，已有 RUN 的 `unknown#L0#<h8>` 保留，不按系统名猜文档。
同名文件的歧义与归一化后相同文本也可能产生重复键，匹配仍保持一对一。

`--write-summary` 校验通过后写 `SUMMARY.md` 与 `RUN.json`；有基线再写 `TRANSITIONS.md`，均遵守 `--out`。
RUN 顶层为 `schema_version: 1 / output_dir / exported_at / project_head / baseline / systems`。
`systems` 按系统名索引，每项保存 docs 的 `file / sha256 / identity` 与 `revision_id`／`revision`（manifest 有才填）、code、
`total / implemented / partial / missing / divergent / unverifiable` 六计数，以及 rows、carried_from。
每行保存 `# / key / status / requirement`（前 80 字）；另存完整归一化 `match_text` 供二级匹配，避免截断影响匹配。
每系统另存 `scope / refs / code_only / code_only_present`，支持范围变更判断及没有基线报告文件时的机制对比。
code_only 新记录为 `{"mechanism": "描述", "code_ref": "file:line"}`；旧字符串记录兼容，若当轮 Markdown
仍在，只为同描述补该轮 code_ref；否则明确「旧记录未保存，待核」，不从当前源码补历史证据。
新增 `validation_version: 2` 与 `inputs`（内部 version 为 1）：docs/refs 的实际 SHA256、project_inputs
（game-toolkit.yaml 与配置的四类 doc_feedback 文件）、scan_refs、scan、有效 code 范围及 problems/notes/code_dirty。
manifest revision 仅显示，不作内容未变的证明；无 revision 仍能以字节指纹比较。token 改变会使身份失效。
旧 RUN 顶层 schema 仍可读取，无需迁移；旧记录不补指纹，不自动获得增量沿用资格。
缺少 manifest 导出时间或 Git HEAD 时相应字段为 null；非沿用系统的 carried_from 为 null。

匹配依次为同键、同文档同 h8 的唯一锚点漂移、同文档同锚点且相似度达阈值、剩余新增／消失；基线行只能使用一次。
漂移不限定 CSV，排除 unknown 与多候选；先耗尽一级，再按剩余行的唯一性配对，优先于模糊匹配。
二级按相似度从高到低贪心，平分按本轮与基线行顺序。改写与状态变化可同时计数；
同状态改写/漂移各计本类，一级同状态才计未变。稳定率是一级行数 ÷ 基线总行数，漂移找回不计一级，分母零时标不适用。
Code-only 两轮描述集合差仅显示「本轮独有描述 / 基线独有描述」，交复核/综合确认机制变化。

## 增量与沿用

```bash
python <本 skill>/scripts/collect_gap.py --plan --baseline <基线目录> --config <配置文件> --project-root <工程根>
python <本 skill>/scripts/collect_gap.py --plan --baseline <基线目录> --config <配置文件> --project-root <工程根> --force 系统甲 --json
python <本 skill>/scripts/collect_gap.py --carry --baseline <基线目录> --systems 系统乙 --project-root <工程根> <本轮目录>
python <本 skill>/scripts/collect_gap.py <本轮目录> --write-summary --baseline <基线目录> --config <配置文件> --project-root <工程根> --stamp-keys
```

`--plan` 默认人读表；`--json` 输出纯 JSON：`{"rerun": [], "carry": [], "reasons": {"系统名": ["原因"]}}`。
文档集合/身份/实际内容、参考、裁决或实际补读依赖变化、代码路径内提交差异、系统新增、force 都重跑。
无配置／无基线／基线无 RUN／不是 Git 仓库全部重跑；没有系统清单时主流程先发现，再用 `--expect` 传入。
旧 RUN 缺实际输入记录、旧提交不可读也重跑；代码范围、已记录的 scope 或 refs 变化同样重跑。
refs 仍不评分，但实际内容会影响结论，必须比较指纹。Git 比较 `<基线 project_head> HEAD`，
并检查依赖范围内未提交/未跟踪代码；基线分析时有这类修改也不能证明可沿用。

分析/复核者在 Scan Scope 中维护一个 `gap-inputs` JSON 代码块，`code` 和 `refs` 都是相对工程根的路径列表。
code 须覆盖实际补扫目录及零命中搜索，refs 包含配置清单以外的补读参考；示例见 analysis-prompt.md。
有效代码依赖是配置 code 与实际 code 的并集。出现无法唯一解析或未覆盖的代码证据时扩大到 `.`，
缺块时同时标记依赖不完整并保守重跑；不从自然语言扫描说明猜完整范围。
根外或无法记录的实际输入写入 gap-inputs 的可选 `unresolved` 字符串列表；非空时保守重跑，不以本地指纹代替外部依赖。

单报告只读检查：`--report FILE --stage analysis` 无需复核记录，`--stage review` 要求复核记录；
两者均执行新语义校验。最终目录汇总仍必须提供全系统 `--expect`，不得用 analysis 阶段绕过复核。
历史目录重汇总用 `--legacy --write-summary --out DIR`：警告写入 stdout 与 SUMMARY，已有键保留，
不补历史指纹，不允许同时 `--stamp-keys`；新 RUN 明示 validation_version 后不能以 legacy 放宽。

`--carry` 预检全部系统后复制报告，在标题下一行标注沿用来源，拒绝覆盖同名报告和已有系统记录。
它写入本轮 RUN 的沿用系统记录；全部重跑与沿用完成后仍须 `--write-summary`，才能记录本轮 HEAD 并完成汇总。
沿用行的键、状态、文档版本保留基线值。`--stamp-keys` 才会修改 Features 为六列，重复执行不追加第七列。
无基线 RUN 时可以现场读五列旧报告铸键作对比，但不能据此判定增量沿用。

## 完整示例

- [gap-analysis.config.yaml](gap-analysis.config.yaml)：占位系统、共享规则页分范围、CSV glob 与共享代码路径。
