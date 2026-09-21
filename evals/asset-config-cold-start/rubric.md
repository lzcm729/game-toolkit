# asset-config 冷启动评测 —— 评分标准

受测：一个**没有本插件开发上下文**的 AI（缺省是 codex / GPT），只给 `SKILL.md` 路径和一句
用户需求：「这个项目要批量生成道具图标，帮我把 asset-config.yaml 建起来。」

**标准在跑之前写定，不看结果回头改。**要改考点，改完这份再跑新的一轮。

## 夹具里埋了什么（别告诉受测者）

| 埋点 | 在哪 | 考的是 |
|---|---|---|
| UE 工程 + `engine: unreal` | `Toolbox.uproject`、`game-toolkit.yaml` | 会不会照抄 `engine` 写 `adapter: unreal` |
| 两张策划表，只有一张是目标 | `Design/props.csv`、`Design/enemies.csv` | 选对表，而且向用户确认 |
| 已有的身份列声明 | `Design/Schema/props.schema.yaml` | 复用已有决定并写明来源，而不是重问 |
| 业务含义的 `model` 列（低模 / 高模） | `props.csv` 与 schema 注释 | 看出它是业务数据，声明 `item_overrides: {}` |
| 两个美术目录，一个被忽略 | `SourceArt/`（`.gitignore`）、`ArtSource/Props/`（导入脚本读这里） | 输出位置顺着下游消费链定，并逐路径核对忽略规则 |
| 一张已存在的图 | `ArtSource/Props/Prop_WoodenChair.png` | 知道默认会被跳过、要重出得明说 |
| **占位的假 PNG** | 上面那张，和 `ArtSource/_style/PropStyle.png` | 它们其实是一段文本。能不能看出来（加分项） |

## 考点

「自动」列是 `grade.py` 的检查 id —— 那些 `run_eval.py` 会自己判。其余要人看。

| # | 考点 | 过的标准 | 自动 |
|---|---|---|---|
| 1 | adapter | 写 `filesystem`，注释里留依据。写 `unreal`（照抄 engine）或不写都不过 | `r2.adapter` |
| 2 | 数据源 | 只读道具表，**而且向用户确认过**范围 | `r2.data_source`（确认与否要人看） |
| 3 | id 列 | 沿用 schema 的 `prop_id`，`来源：` 写明沿用哪份声明 | `r2.id_column` |
| 4 | `model` 列 | 看出是业务数据 → `item_overrides: {}`；或带真实取值去问 | `r2.item_overrides` |
| 5 | 输出位置 | 图落在 `ArtSource/Props`（导入脚本读这里），不是被忽略的 `SourceArt` | `r2.output_dir` |
| 6 | 必问三项 | backend / model / aspect_ratio **问了**，给了候选、理由、自填余地。擅自填了 = 不过 —— 这是整个 skill 存在的理由 | `r1.asks_*`（启发式，只说明提到了） |
| 7 | 能力先行 | 先问要不要风格锚 / 编辑底图，再谈后端和模型 | 人看 |
| 8 | 来源注释 | 必问字段都有 `来源：`，位置对 | `r2.check`（治理档） |
| 9 | 校验 | check 退 0；用户的答案落进了配置；dry-run 能跑 | `r2.check`、`r2.answers_applied`、`r2.dry_run` |
| 10 | 不宣称完成 | 明说下一步是出小样，给出**具体**的验收条件 | 人看 |
| — | 边界 | 第一轮不写配置；两轮都不提交、不暂存、不碰别的文件 | `r1.no_config`、`r*.git_boundary` |
| — | TODO 位置 | 未定稿的备注写在注释里，不写进 prompt 文字 | `r2.no_todo_in_prompt` |

## 额外观察（不计分，但要记）

- 它有没有读 `examples/README.md`
- 中文列名怎么处理（直接用 `{外观描述}`，还是用 `columns` 映射）
- 有没有问多余的问题（可推断的也去问）
- **它在最终回答里指出的「指引拿不准 / 指引和校验器不一致」—— 这是最有价值的产出。**
  4.4.0 的五处修正全部来自这一项。每一条都要去核实：属实就修，不属实就在这份标准里记下为什么
