# 传播核对与定点修卡

核查员不应是这些卡的作者。材料是工作目录下的 `Paths.cards`、`Paths.card_plan`、
`Paths.source` 和完整单元/原始复核记录；先读 [../method.md](../method.md) 与 [../card-format.md](../card-format.md)。

```text
python scripts/verify_units.py show <workdir> u01-01
```

逐卡逐分支核下面六项，意思到位即可，不要求逐字复制复核：

1. narrowing 是否落实到输入、步骤、完成标准或判停，卡是否承诺得更宽。
2. must_go_to_boundary 是否逐条在对应分支或 B 中出现。
3. reconstructed/invented 是否被写成原书给出的规则；回页码分辨直接改写、足以重建与无依据添加。
4. gaps 的原书未说明与原图缺失是否分开；反向查作者已给的条件是否被错标为未说明。
5. reference/needs_review 的内容是否进入编号执行步骤或完成标准。
6. 只对一个分支成立的限制是否误成整卡禁用；整卡限制须对所有分支成立。

不在此核措辞、排版、卡该怎么拆合或摘句逐字性；后者有脚本，但本轮要核语义传播。
核查员只写工作目录的 `propagation/findings-<批>.yaml`，不改卡：

```yaml
cards_checked: [steady-shadow]
findings:
  - card: steady-shadow
    branch: 1
    unit: u01-01
    check: 1
    where: E 段分支 1 步骤 2
    problem: 卡给了亮度阈值，复核只支持固定条件后比较。
    fix: 删掉阈值承诺，保留差异记录。
clean: []
```

主执行方确认发现后交修卡方定点修复：收窄步骤；补分支限制；回原文核 reconstructed，
实质有据可 kept 并写页码及短证据；仅为格式的添加标约定，缺图按转换缺失标，不用约定掩盖编造的判断。
待核查内容移出 E 成为依据不足的对照，分支限制移回分支，保留有效的其他路线。
修卡方只改获派位置和 meta，revision 同步加一；不新增引文或分支，R 原文和翻译通常不动。
若发现 R 也有错，单独交回处理，不能为了保留原文而放过错误。

修卡记录写 `propagation/fixes-<批>.yaml`，每条包含 card、finding、action（fixed/kept/not_fixed）、change、evidence。
修后运行，核查员再核发现对应的分支：

```text
python scripts/check_cards.py <workdir>
```

未修、语义核查未过或脚本失败就停，不进入公开化候选的冻结验收。
交回：核卡数、六类发现数、fixed/kept/not_fixed 数、命令结果、未决及最不确定两项。
