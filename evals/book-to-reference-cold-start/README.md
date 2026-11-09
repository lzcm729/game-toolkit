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
fixture/book/description.txt 是预先给定的入口取舍：压缩四本既有书的主要触发，并加入本微型书的任务信号。
book.yaml 的 description_file 指向它，只用于评测副本，不修改本仓库的 game-design-theory description。
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
运行 skill 脚本时，`inputs.before/after` 记录当时解析的工作目录及全部 Paths 绝对路径；
配置解析失败则记录 error。检查与接入必须使用相同的 source、cards、meta、card_plan、verify_out 路径及内容。
无关的 notes 裁定或入口配置变化不影响这项绑定；旧日志缺 Paths 证据时明确不能绑定，不按当前配置回填。
消费还须用运行 meta 的 `plugin_sha256` 对上接入后的插件快照摘要，不能用命令结束时看见的缓存文件代替执行证据。
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
| flow.cards_check | 最后一次完整 check_cards 退出 0，卡/meta/计划/原文/验证单元的哈希仍对应当前输入 | test_grade_requires_last_successful_check、test_grade_hash_bindings_reject_changed_inputs |
| flow.integrate | 最后一次 integrate 退出 0，输入绑定接入前最近一次完整卡检查 | test_grade_hash_bindings_reject_changed_inputs |
| flow.integrated | 最近一次采用输入的发布卡和 notes、选卡表直链在副本，生成范围无残留 | test_grade_missing_integrated_card、test_grade_residue |
| flow.scope | 任务表中至少一项有效 reference_only 处置 | test_grade_requires_scope |
| consumption | runner 的 meta/输出哈希可信，最终成功、Skill 成功激活且 Read 新卡；消费前后插件等于接入产物 | test_grade_requires_successful_consumption、test_grade_hash_bindings_reject_changed_inputs |
| stop.01-quotes | 采用输入哈希未提前变，卡片检查失败，相关卡变更，同命令通过 | test_grade_stop_negative_cases |
| stop.02-propagation | 采用输入哈希未提前变，传播探针失败，相关卡变更，同命令通过 | test_grade_stop_negative_cases |
| stop.03-entry | 采用输入哈希未提前变，integrate 失败，配置变更，同命令通过 | test_grade_stop_negative_cases |

完整流程按默认工作目录布局留产物，候选内容评审保存 review.md；精确文件和模式清单在 grade.py 的 FLOW_FILES、FLOW_GLOBS。
三份续跑按顺序在完整流程和消费之后进行。比较采用输入时直接用 fixture/stops 的原始字节；
历史运行优先使用其插件副本里被首条日志哈希冻结的 fixture 版本，避免用改过的现行夹具误判旧输入。
book.yaml 只把 target_root 按准备器规则替换为本次插件路径后再算哈希，不能因此改其他配置。
第二份的 `grade.py check-propagation <续跑目录>` 是固定材料的局部限制探针，允许改写措辞，
只筛局部泊位条件是否进入执行段及已知越界承诺是否还在。它不能替代六类人工语义核对。

自动全绿只说明列出的执行证据成立。范围处置是否给用户看、页码是否支持判断、语义传播、独立性与内容质量另由审核方核。
评分器不修改产物，也不调模型。测试的全对输入是人工构造的局部回放，不算执行型冷启动结果。
stops 的起点只取第一份续跑之前的主流程检查和消费；之后恢复主流程不影响续跑顺序，但恢复后的主流程绑定仍须成立。
成功检查绑定各自输入，成功后再改卡或 meta 会使证据失效。消费绑定插件内容时排除 Git 内部文件、Python 字节码和 pytest 缓存。
模型可见修改后的历史冷启动不证明新版本已冷启动通过；是否再跑取决于用户的停止规则和授权。

## 上次运行

2026-11-09，审核方实际运行了两次全新上下文的微型书冷启动。第二次有独立子代理，可达的三道任务均读到新卡，两道保护题 HIT，诱饵 REJECT。修正评分器后在原始 54 条日志上重评为 10/10；三份续跑均按失败、修改、复查通过完成，末尾恢复主流程不再误判顺序。

第一次在原始 53 条日志上重评为 8/10：消费失败，且传播续跑的卡/meta 在成功检查后再改，不能绑定最终版。消费前修改过插件引用链测试，也不满足新增的冻结绑定要求。

上述 10/10、8/10 是前一版评分器的历史结果。补上执行时 Paths 和运行插件内容摘要后，
两次原日志重评均为 2/10：旧日志缺 Paths 证据，不能追认检查、接入、消费及续跑的绑定；
旧配置也缺现行必填的 when_to_use_end，使发布产物和 scope 检查无法按现行配置加载。
这不表示历史执行没有完成修复步骤；也不能用历史成功输出证明当前要求的版本绑定。现场未补写证据或改配置。

这些运行使用修复前的插件副本；最后一轮产品修复仅做确定性回归，按用户停止规则未再次冷启动。微型书直接使用页码文本、入口取舍预先给定，少量消费检查不代表完整口径 B，也不代表下一本真书适用性或质量已验证。
