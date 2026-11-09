# 盲评：质量先判，归因后看

主执行方填匿名评分包和交付文件。评分员只读本说明和自己的评分包；不读 key、版本、运行链、书或插件。
包里每题有问题、冻结评分项、匿名回答，以及 X/Y 组别；不要猜身份。
默认每版两次回答；若计划另定次数，以包中全部标签为准。

先对每份回答给四项 0–3 分：correct（判断/建议符合处境）、specific（落到具体做法）、
no_fabrication（无编造数字/研究/引文/出处）、helps（给出实际帮助，不把判断全推回用户）。
主要看 must，routes 里任何合理路线都算对；不因引用加分，不因篇幅或语气判好。

再比较 X 组与 Y 组全部重复回答，判 X_better/same/Y_better，并指出具体的判断或行动差别。
说不出内容差别就 same；组内波动或两次比较矛盾使整体说不清，判 unclear，不取平均强行放行。
落后一组有实质退步时写具体类型：丢关键诊断、错误行动、漏必要步骤、把本可给的帮助全推回用户；无则 none。
评分员不知道哪边是候选，不能因猜到版本而改判。

```yaml
- q: a001
  scores:
    甲: {correct: 3, specific: 2, no_fabrication: 3, helps: 2}
    乙: {correct: 3, specific: 3, no_fabrication: 3, helps: 3}
    丙: {correct: 3, specific: 2, no_fabrication: 3, helps: 2}
    丁: {correct: 3, specific: 3, no_fabrication: 3, helps: 3}
  cmp1: {verdict: same, difference: 两组都给出控制观察条件的做法。, regression: none}
```

以下示例写工作目录的 `compare/grading/grades-<编号>.yaml`；每题一条，所有标签都打分，缺题交回，不自己补题。
多评分员默认分题；若同题交多名评分员须事先定仲裁，先存原始评分、解决冲突后由协调者生成每题唯一 adopted 成绩文件。
aggregate 把重复 q 当未完成，不会自动投票或平均。强制查阅的 cmp2 只作内容诊断，不替代自然 cmp1。

由主执行方解 key、汇总并另看链路，评分员不参与看到身份后的改分：

```text
python scripts/grading.py aggregate <workdir> --id-map <workdir>/compare/id_map.json --items-meta <workdir>/compare/items_meta.json --key <workdir>/compare/grading/key.json --grades <workdir>/compare/grading --protocol B --out <workdir>/compare/result.json
python scripts/chain.py per-question baseline=<workdir>/compare/runs/baseline candidate=<workdir>/compare/runs/candidate --card-prefix micro-
```

按 [../acceptance.md](../acceptance.md) 判：必测 O/N 各自 worse 不多于 better，且无确认的实质退步、无未决缺失。
fail/incomplete 停止批准迁移；脚本标实质退步交人核实，不能只因未调用或未读卡而剔除差题。
质量判定与 plugin_use 分列，好坏对称；原因不明不放行。旧合并计数协议只用于历史复现。
交回：题数、判定分布、最不确定一题和原因、独立性；只写获派文件，不改资料。
