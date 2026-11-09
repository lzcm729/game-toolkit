# 独立复核：现在能写出每一步吗

主执行方先从 flags、重要任务和未自报存疑的单元中定样本，不设降级配额。
用下面命令准备精简输入；例子是微型书，批次和单元号按本书实际替换。

```text
python scripts/verify_units.py recheck-input <workdir> R1 u01-01
```

复核员在新上下文中只读这份说明、[../method.md](../method.md)、工作目录下
`Paths.recheck_in/<批>.yaml`、`Paths.overview` 和 `Paths.source`。
不要读 Paths.verify_out、verified.md、references.md、needs-review.md、flags、其他批的判定或最终卡。
输入里的旧摘句仅是线索，不能当成立的证明。宿主不能提供未见旧判断的上下文时标「未独立验证」。

逐单元回原文读整节，检索跨章判据，列将来 E 段的步骤。每步标 quoted/paraphrase/reconstructed/invented。
找最关键的判断：选哪个、何时够、阈值多少、什么时候转向。判据缺失时，收窄后仍能产出具体结果才 verified；
核心靠 invented 且收窄后不能执行则 needs_review；只剩观点则 reference；完全重复或依据错位则 rejected。
经验数字、单处案例、缺图、作者明确没有算法、跨节强拼流程，按 method 的严格口径逐个判断。
另做合成演练，优先挑缺判据会卡住的输入，不补造规则、不冒充现实验证。

写工作目录下 `Paths.recheck_out/<批>.yaml`，每个输入单元恰好一条：

```yaml
batch: R1
units:
  - unit_id: u01-01
    decision_after: verified
    steps:
      - step: 固定灯的位置。
        support: paraphrase
        location: p.1
    key_judgment: 原文要求固定灯；记录表格式没有规定。
    narrowing: 只承诺固定条件后的比较，不给出亮度阈值。
    walkthrough: {input: "合成演练：更换挡板", observed: 得到条件与影子差异, breaks_at: 无}
    must_go_to_boundary: [记录表是实现约定，不是作者给的格式。]
    gaps: []
    covered_by: null
    reason: 收窄后仍能完成可检查的比较。
```

needs_review 写具体 gaps；rejected 且被覆盖时 covered_by 指向保留单元。
完成后由主执行方应用并汇总，复核员不自行读取旧判定核结果：

```text
python scripts/verify_units.py apply-recheck <workdir> R1 --dry
python scripts/verify_units.py apply-recheck <workdir> R1
python scripts/verify_units.py aggregate <workdir>
```

批次自然排序、后批生效，筛选批次不重排；第一次改动前备份，重复应用应无变化。
记录不全或应用/汇总失败就停，修后重跑。向写卡方传递 narrowing、must_go_to_boundary、gaps 和逐步来源等级。
交回：各去向数、收窄数、检查结果、独立性、最不确定两项；不贴完整 YAML。
