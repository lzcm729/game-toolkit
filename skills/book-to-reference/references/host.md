# 宿主与运行隔离

运行器只负责调度和记录，不把存在输出文件当作完成。最终事件必须是成功的 result，
没有错误且回答非空，meta 的 batch_id 还必须属于本批。失败或半截输出归档为
`.stale-<n>` 再跑；模型、提示词或插件路径变化也不能沿用旧回答。

使用支持 Skill、stream-json 和 init 中模型及版本字段的 Claude Code。
旧流程实测的版本是 2.1.319；其他版本先做加载与读取冒烟，再记录实际版本。
模型 ID 和 Claude Code 版本从 init 事件保存到 meta。普通 pytest 只运行假 CLI。

每批创建全新的 CLAUDE_CONFIG_DIR，各次运行使用全新的空工作目录。
不用 `--bare`：旧流程里它会移除 Skill 工具，失去自然激活链。
runs-root 不得在用户主目录下，向上读取用户 CLAUDE.md 会污染实验；还应选在没有
项目级祖先配置的地方。CLI 会拒绝用户主目录内的 runs-root。
`--add-dir` 让 Read 可以读取被测插件，只有 `--plugin-dir` 时读取可能被拒。
工具仅为 Read、Glob、Grep、Skill；不赋予写入或 shell 工具。

API key 只从环境变量继承，不读取凭证文件，不把环境变量值写入 meta。
`--budget` 是每次运行的美元上限，整批报价还要乘题数、版本数和重复数。
命令路径在 Windows 也使用 `/`，含空格的命令路径要放在引号里。

```text
python runner.py prompts.tsv runs --variant baseline=baseline --variant candidate=candidate --reps 2 --lanes 2 --budget 1 --runs-root isolated-runs --batch-id frozen-batch --model MODEL
python chain.py counts runs/baseline runs/candidate --card-prefix book-
python chain.py per-question baseline=runs/baseline candidate=runs/candidate --card-prefix book-
```

顺序是每道题→每个重复→每个版本；两版本同批交错，减少日期造成的混淆，不能消除随机性。
只有对应成功 tool_result 的 Read 才算读到；请求被拒或没有结果不算。
failed 单列，不进入其他激活分类；runs 是包含失败的总数。
激活指本插件任一 skill，不能只数 game-design-theory。

复核、出题和评分必须在没见过上一轮判断或答案的独立上下文执行。
Codex 宿主没有独立上下文时照常保留产物，但相关步骤标“未独立验证”，不能宣称验收通过。
以后 `claude plugin eval` 可以接替加载隔离、执行和工具观测；只有满足同批、完整性和
独立性的契约才可替换，默认评分不能替代口径 B 或消费链验收。
