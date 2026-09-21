# asset-config 冷启动评测

让一个**没有本插件开发上下文**的 AI，只照着 `skills/asset-config/SKILL.md` 从零建一份配置，
看它会在哪里走偏。

## 为什么要有这个

指引和校验器是同一份契约的两面。我们自己读指引时脑子里有上下文，会自动补上它没写的部分；
一个**照字面执行**的外人才会撞上「指引没说」「指引和校验器说的不一样」。

4.4.0 的五处修正全是这么撞出来的：TODO 写进 prompt 会原样发给模型、check 只查图在不在
不查是不是图、dry-run 让人以为已存在的图会重画…… 我们自己读了那份指引几十遍，一处都没看出来。

## 什么时候跑

改了下面任何一个之后，发版前跑一次：

- `skills/asset-config/SKILL.md`（指引本身）
- `skills/asset-config/scripts/check_config.py`（校验器）
- `skills/generate-assets/examples/README.md`（字段说明，指引会让 AI 去读）

**不进普通测试套件**：要调外部 AI、要联网、花钱，两轮合计约 15 分钟，结果也不确定。

## 怎么跑

```bash
python evals/asset-config-cold-start/run_eval.py
```

缺省用 `codex`（要先装好并登录）。换别的 AI CLI：

```bash
python evals/asset-config-cold-start/run_eval.py \
  --agent-cmd "mycli --cwd {workdir} --prompt-file {prompt_file} --out {output}"
```

它要能在 `{workdir}` 里读写文件、跑命令；最终回答写进 `{output}`，没写的话它的 stdout 会被存进去。

跑完会打印报告，同时存一份 `report.md`。结果目录在系统临时目录下，路径会打出来。
只想对某次结果重新评分：

```bash
python evals/asset-config-cold-start/run_eval.py --grade-only <那次的结果目录>
```

（重新评分只能评第二轮 —— 第一轮要在第二轮动工作区之前评，事后复现不了。）

## 怎么读结果

**自动项全过不等于评测通过。**报告分两块：

1. **自动项**：`grade.py` 能机械判定的考点 —— adapter 取值、`item_overrides`、图落在哪、
   check 退码、用户的答案有没有落进配置、有没有越界写文件或提交。标「启发式」的只是
   关键词命中，说明提到了，问得好不好还得看
2. **人工核对**：必问三项是不是真的**问**了而不是替用户定了；是不是先问能力再问后端；
   验收条件具不具体；有没有宣称已经完成。对着 `rubric.md` 看

**最有价值的是第二轮最终回答的最后一节**：它指出的「指引拿不准 / 指引和校验器不一致」。
每一条都去核实，属实就修。

## 文件

| 文件 | 作用 |
|---|---|
| `rubric.md` | 评分标准，跑之前写定 |
| `fixture/` | 仿真 UE 工程。`gitignore.txt` 复制出去时会改回 `.gitignore` —— 原名放在插件仓库里会让插件仓库自己也忽略 `fixture/SourceArt/` |
| `prompts/round1.md` | 第一轮：读项目、交草稿和问题，**不写配置** |
| `prompts/round2.md` | 第二轮：用户的回答（按事情写，不按题号），写配置、跑校验 |
| `grade.py` | 自动评分。判断「图落在哪」用的是插件自己的 `asset_plan`，不另算一份 |
| `run_eval.py` | 铺工程、两轮调 AI、评分、出报告 |
| `test_grade.py` | 评分器自己的测试 —— 每条考点都配一个故意做错的输入。这个进普通测试套件 |

两轮之间开新会话，不续上一轮：续会话不是每个 AI CLI 都有，而第一轮的草稿都在
`QUESTIONS.md` 里，从盘上读就够了。
