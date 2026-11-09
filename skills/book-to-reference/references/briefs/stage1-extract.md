# 阶段 1：五类候选

主执行方填工作目录、负责范围和五类分工。先读 [../method.md](../method.md) 和
[../candidate-schema.md](../candidate-schema.md)，再读工作目录下的 `Paths.overview`、负责范围的全部 `Paths.source`。
按自然章节分段读，截断要重读；Grep 找线索后回读相邻段及整节。跨章找条件、单位、阈值和反例。
覆盖优先于省 token，不以关键词零命中宣布整章无内容。

五个视角分别找方法/流程/排障、原则/清单/公式、案例、反例、术语。
可按章合并读写，但交付仍分五类；不预先宣称这种分工能降本。
宁可多收有依据的候选，重复交给验证去重；不筛 verified，不写卡，不设数量目标。
一处完整说明可以收，重复引用同一事件不当多份独立证据。

候选放工作目录下的 `Paths.candidates`，术语放 `Paths.glossary`，格式和文件名照 schema。
source_chapter、原文逐字摘句和 task_ids 必填；对不上任务时 task_ids 为空并说明。
作者没给条件与转换缺图分开记。原书表格被误标成引文时回查，不把转换标记当作者保证。
五类的编造例子见 schema，不能把例子的内容当这本书的证据。

```text
python scripts/stage1.py coverage <workdir>
python scripts/stage1.py split <workdir>
```

主执行方汇总全部分段再审计、分组。坏 YAML、重复号、未知任务、未映射章节先修；无可执行候选的任务先补读。
补读后确实没有可执行内容的任务，写进 `Paths.scope`（默认 `candidates/_scope.yaml`），
逐项写 task_id、decision（reference_only 或 out_of_scope）、非空 reason，可加 pages。
在阶段 0 确认范围时或之后把处置给用户看，不能静默；参考内容写明读者可达的 notes 去处。
重跑 coverage，确认处置单列且没有问题，再下推；不造方法过关，范围处置不等于已交付。
合并文件与 parts 的优先规则见 schema，别把旧 parts 留着让审计读到过期内容。
交回：文件、五类数量、覆盖章节、命令和退出码、补读与剩余缺口。正文保存在文件中。
