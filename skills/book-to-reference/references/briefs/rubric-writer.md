# 独立写评分项

主执行方填只读 prompts-raw.yaml、id/task 清单、题数和输出文件，均在工作目录内。
评分项作者只看这两个文件和本说明，不读插件、卡、书、分组/必测身份、版本或任何回答。
先写并冻结评分项，再运行模型；有改动要重新冻结，不能看完答案改尺子。

每个 item_id 写：

- need：题目要的一个判断或行动。
- must：2–4 条可检查的具体判断、做法或必须问清的条件，不用「全面」「深入」当标准。
- good：1–3 条有用但非必须的补充。
- red_flags：具体错误，如编数字/研究/出处、建议与处境冲突、关键步骤缺失或把帮助全推回用户。
- routes：能完成任务的合理路线，任一路线都可，不限定某书或新卡的方法。

引用和页码本身不加分，编造扣分；不以回答长短、格式或语气代替任务质量。
若题面条件不足以立判，交回主执行方澄清并在看到回答前冻结，不能私自添答案条件。

```yaml
t01-01:
  need: 分清两次影子变化是否可比较。
  must: [检查两次观察条件, 给出下一次比较的具体做法]
  good: [提供简短的差异记录格式]
  red_flags: [编造亮度阈值, 只说由用户判断而不给考量]
  routes: [控制变量后比较, 先排查测量条件再设计比较]
```

以下示例用工作目录的 `compare/rubric.yaml`；本批另定目录时同步替换命令参数。
自查所有题恰好一条、must 数量、条件与替代路线，不能读运行结果做自查。
主执行方准备评分包时脚本会遮蔽题目、评分项和回答中的身份标记：

```text
python scripts/grading.py packets <workdir> --id-map <workdir>/compare/id_map.json --rubric <workdir>/compare/rubric.yaml --prompts-raw <workdir>/compare/prompts-raw.yaml --baseline <workdir>/compare/runs/baseline --candidate <workdir>/compare/runs/candidate --reps 2 --n-graders 2 --seed 42 --out-dir <workdir>/compare/grading
python scripts/grading.py leaks <workdir> <workdir>/compare/grading/packets/packet-1.md <workdir>/compare/grading/packets/packet-2.md
```

任一运行未成功或仍泄露身份就停，补运行或补 mask_names 后重建，不能把失败片段包装成答案。
只交 packets 下的评分包，key 留在其外，不交评分员。
交回：条数、自查、最难定必须项的两题及理由、独立性。
