# 独立出题：从任务写真实处境

主执行方先指定模式（可达/回答对比）、工作目录内的只读任务文件、题数、输出文件和长度要求。
出题员只读获派的 id/task 清单和本说明，不读插件、书、卡、机械期望、分组依据、评分项或已有回答。
复用旧题只能作回归，新题才作新一轮验收；保存 used 清单和种子。

可达模式由主执行方选任务，参考答案与出题材料分开保存：

```text
python scripts/reach.py pick <workdir> --seed 42 --per-card 2 --out-dir <workdir>/reach
```

只交 `reach/tasks-for-prompt-writer.yaml` 给出题员，不交 expected.json。
主执行方另外从冻结能力清单选受保护的其他书能力，补同样的 id/task 清单，并单独存 p- 开头的期望；
机械卡期望用 slug，受保护期望用完整文件名或 SKILL.md，诱饵 x/d 开头。
可达题建议一两句、40–90 汉字；诱饵按冻结数量覆盖代码、打包、绘图操作等非设计判断问题，避免撞题。

回答对比由主执行方按 answer_compare 配额抽样，给出题员仅 id/task 文件：

```text
python scripts/grading.py pick <workdir> --groups <workdir>/grouping/groups.yaml --capabilities <workdir>/grouping/capabilities.yaml --seed 42 --out-dir <workdir>/compare
```

只交 `compare/items-for-writer.yaml`，不交 items.json 的组别和必测身份。
回答对比题建议两三句、60–140 汉字，让好回答有具体行动可给；不另加未冻结的诱饵。

两种模式都要保留触发方法的关键条件，例如尚无观测数据时不能暗改成已有数据；
一题只问一件事，用开发者处境和现象改写任务，不提作者、书名、方法名、卡名或「理论/框架」。
不要把答案写进题面，也不要暗示调用哪个 skill。
写 `prompts-raw.yaml`，格式为 `item_id: "问题"`；键与获派任务一一对应，诱饵按约定另列。

主执行方核题面条件、缺漏、长度、答案暗示、身份词。可达模式先在工作目录准备 items mapping：
每个 item_id 有 task、group（task/protected/decoy）、required、source；回答对比直接用 pick 的 items.json。
以下以回答对比为例，生成 TSV 和身份映射：

```text
python scripts/grading.py prompts <workdir> --items <workdir>/compare/items.json --prompts-raw <workdir>/compare/prompts-raw.yaml --out-dir <workdir>/compare
```

可达模式也用此命令，换成可达 items 文件与输出目录；两个版本自然运行都用同一 TSV，不塞选卡答案。
可达运行后由主执行方评分；p- 和 x/d 的附加期望与任务期望分别存 JSON，可同时传入：

```text
python scripts/reach.py score <workdir> --runs-dir <workdir>/reach/runs/candidate --id-map <workdir>/reach/id_map.json --expected <workdir>/reach/expected.json <workdir>/reach/protected.json --out <workdir>/reach/score.json
```

FAILED 必须补完整运行；STRICT/ANY 只是机械命中，OTHER 要独立读题与资料判断能否完成任务，不能直接算错。
NONE、受保护 MISS、诱饵 FIRED 须查真实路由和题面；不靠换题迎合卡号。未解决的必要路线停止回答对比。
交回：题数、文件、键/长度/身份自查、最难写两三题和原因，说明上下文独立性。
