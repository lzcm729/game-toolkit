# book-to-reference 执行型冷启动

把 BRIEF.md 交给没有本会话上下文的执行者。它从新 SKILL.md 出发，用编造的三章、20 页微型书实际走到接入和消费，
然后依次接续三份中间状态。预计 50–100 万 token、几美元 API；按实际宿主和小批题数报价。
prepare、日志包装器、评分器及普通 pytest 都不调模型，只有执行者使用 runner 的真实运行会花费。

## 怎么跑

从仓库根执行 `python evals/book-to-reference-cold-start/prepare.py <父目录>`，或者由冷启动执行者按 BRIEF 自行准备。
父目录必须在源码仓库和用户主目录外，并且没有已有 book、plugin、logs 子目录。
准备脚本复制当前工作区，不只复制 Git 已跟踪文件；排除源 .git、evals/*/results 和 .env*，不读取凭证文件。
插件副本现场 git init 并建唯一的初始提交，原仓库不变；Git 准备命令的原始输出也留在日志目录。
使用没有其他项目祖先配置的父目录，API key 从环境变量继承。

准备出的树是 `book/`、`plugin/`、`logs/`。book 里有 source、book.yaml、SETUP.md 和 stops；
三份 stops 的 target_root 也指向同一个插件副本。skill_md 的插入锚点由执行者在副本中增设，保留原有书籍入口。
完整流程的评审记录保存成 book/review.md，供交接查阅；正文不是自动语义评分的依据。
如果不能派子代理，照常完成产物并标「未独立验证」；评分器不因此判失败，也不因此判独立验收通过。

运行本 skill 的脚本和第二份续跑的传播探针，一律经：

```text
python evals/book-to-reference-cold-start/run_logged.py <日志目录> -- python <脚本路径> <参数...>
```

包装器保留当前 cwd，原样传递命令参数；路径有空格时用 shell 的引号包住。
每次命令顺序执行，记录 commands.jsonl、command-NNNN.out、开始/结束 UTC 时间、退出码、输出哈希，
以及工作目录和插件副本运行前后每个文件的 SHA-256。快照含 .git；.env* 不打开，符号链接报错，不跟随到树外。
真实 runner 的输出放 logs/runs，包装器另记录该目录的文件哈希，评分时不接受日志后替换的运行。
文件编辑可以用宿主编辑工具；前后两次检查的快照应能证明相关文件在失败之后、复查之前变化。
失败命令保留非零退出码，不要覆盖日志；launch 失败记录 127 和异常类型/消息。

## 怎么评

```text
python evals/book-to-reference-cold-start/grade.py grade <工作目录> <插件副本> <日志目录>
python -m pytest evals/book-to-reference-cold-start/test_book_cold_start_grade.py -q
```

grade.grade(workdir, plugin_copy, log_dir) 返回 Check(name, ok, detail) 列表；CLI 任一项不过退出 1。

| 检查 | 机械证据 | 反例测试 |
|---|---|---|
| logs.valid | session 根路径、连续序号、时间次序、输出 SHA-256、前后快照形态 | test_grade_rejects_bad_log |
| flow.artifacts | 笔记、overview、五类候选、覆盖审计、验证/复核、卡/计划/meta、传播记录、分组与 review 文件非空 | test_grade_missing_artifact |
| flow.cards_check | 完整流程最后一次不带 --only 的 check_cards 退出 0 | test_grade_requires_last_successful_check |
| flow.integrate | 完整流程最后一次 integrate 退出 0 | test_grade_requires_last_successful_check |
| flow.integrated | 最近一次采用输入的发布卡和 notes、选卡表直链在副本，生成范围无残留 | test_grade_missing_integrated_card、test_grade_residue |
| flow.scope | 任务表中至少一项有效 reference_only 处置 | test_grade_requires_scope |
| consumption | 经 runner 留下本批 meta，最终成功、调用本插件任一 skill、成功 Read 新卡；文件与当时哈希相同 | test_grade_requires_successful_consumption |
| stop.01-quotes | 采用输入哈希未提前变，卡片检查失败，相关卡变更，同命令通过 | test_grade_stop_negative_cases |
| stop.02-propagation | 采用输入哈希未提前变，传播探针失败，相关卡变更，同命令通过 | test_grade_stop_negative_cases |
| stop.03-entry | 采用输入哈希未提前变，integrate 失败，配置变更，同命令通过 | test_grade_stop_negative_cases |

完整流程按默认工作目录布局留产物，候选内容评审保存 review.md；精确文件和模式清单在 grade.py 的 FLOW_FILES、FLOW_GLOBS。
三份续跑按顺序在完整流程和消费之后进行。比较采用输入时直接用 fixture/stops 的原始字节；
book.yaml 只把 target_root 按准备器规则替换为本次插件路径后再算哈希，不能因此改其他配置。
第二份的 `grade.py check-propagation <续跑目录>` 是固定材料的局部限制探针，允许改写措辞，
只筛局部泊位条件是否进入执行段及已知越界承诺是否还在。它不能替代六类人工语义核对。

自动全绿只说明列出的执行证据成立。范围处置是否给用户看、页码是否支持判断、语义传播、独立性与内容质量另由审核方核。
评分器不修改产物，也不调模型。测试的全对输入是人工构造的局部回放，不算执行型冷启动结果。
执行者若改了模型可见内容，后续由审核方按新上下文完整重跑；description 改动另重跑触发冒烟。

## 上次运行
