# 阶段 1.5：三重验证与去向

先读 [../method.md](../method.md) 的三重验证及严格复核口径。
材料是工作目录下 `Paths.verify_in/<组>.yaml`、`Paths.overview`、`Paths.source`；分组来自 verify_groups。
本组五类列表全部读完，回原文核整节及跨章条件，不能仅信候选摘要。
主执行方指定输出为 `Paths.verify_out/<组>.yaml`，只写负责组。

同一方法的 framework/principle 合并并保留候选号；清单合成一份可执行检查，独立规则拆开。
一个方法单元有自己的输入、步骤或判断、输出，不设单元数量目标。
V1 检查每步依据；V2 固定书外输入和完成标准，纸面演练标 walkthrough；V3 写可检查的任务帮助。
从首轮就按「现在能否写出 E 段每步」判：缺判据要收窄，不能以常识补出流程。
只剩观点判 reference，缺关键条件判 needs_review，错误归因或完整重复判 rejected。

下面是编造的结构示例；所有理由、证据和演练要按本组实际内容填写。

```yaml
group: G1
units:
  - unit_id: u01-01
    title: 比较影子
    type: framework
    one_liner: 固定灯再比较影子。
    merged_from: [f1-01, p1-01]
    source_evidence:
      - location: "Ch1 Observe / Shadows, p.1"
        quote: "Keep the lantern still while you compare the shadows."
    V1_source_sufficiency: {passed: true, reason: 原文给出固定条件与比较动作。}
    V2_executability: {passed: true, check_mode: walkthrough, input: "合成演练：换一块挡板", expected: 影子差异记录, observed: 得到差异记录。}
    V3_task_utility: {passed: true, expected_benefit: 避免把条件变化误作挡板效果。}
    decision: verified
    decision_reason: 证据支持限定范围内的比较。
    gaps: []
    importance: high
    importance_reason: 比较条件失控会使结果无意义。
    task_ids: [t01-01]
    supports: {cases: [c-01], counter_examples: [ce-01], terms: [g-01]}
candidate_disposition:
  f1-01: u01-01
  p1-01: u01-01
unattached_support: {}
coverage:
  t01-01: {units: [u01-01], status: covered, note: ""}
```

本组每个 framework/principle 恰好一条 disposition：值为单元号，或 `{rejected: 理由}`。
每个任务恰好一行 coverage，status 为 covered/reference_only/needs_review/gap，不拿待核查算可执行覆盖。
case 挂 supports.cases 并保留 example_kind；反例挂 counter_examples，术语挂 terms；挂不上的支持材料在 unattached_support 写原因。
needs_review 必填具体 gaps 和补读/询问事项。importance 取 critical/high/medium/low 并写任务依据。

```text
python scripts/verify_units.py aggregate <workdir>
```

主执行方等各组齐后汇总，问题非空就停，修后重跑；flags 只筛自述存疑，不代替复核。
无 verified 不凑卡。参考和重要缺口要有实际交付去向，必要时交回用户调整范围。
交回：各去向数、gap 任务、脚本结果、最拿不准的两处，标明独立性是否满足。
