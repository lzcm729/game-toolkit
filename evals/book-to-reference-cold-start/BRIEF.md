# 执行任务

从本仓库的 `skills/book-to-reference/SKILL.md` 开始，按它及随包链接完成本次导入。

先在仓库外、用户主目录以外选一个全新的父目录，从仓库根运行：

```text
python evals/book-to-reference-cold-start/prepare.py <父目录>
```

它打印工作目录、插件副本和日志目录。输入在工作目录，目标为插件副本；只改这次准备的材料和副本。
可以在插件副本里做 Git 操作，包括暂存比较；原仓库是只读来源，不得在原仓库写文件或做 Git 写操作。
本评测的入口取舍已由 book.yaml 的 description_file 给定，按该文件接入插件副本。
运行本 skill 的脚本一律经日志包装器，命令中的脚本路径使用插件副本里的版本：

```text
python evals/book-to-reference-cold-start/run_logged.py <日志目录> -- python <插件副本>/skills/book-to-reference/scripts/<脚本名>.py <参数...>
```

先按完整流程完成理解、提取、验证、复核、写卡、传播核对和内容评审，接入插件副本，
再跑一小批无界面运行看实际消费。runner 的输出放在 `<日志目录>/runs/`，宿主空工作目录放在该日志目录下另一个子目录。
API key 从环境变量取。如果有派子代理的工具，需要独立上下文的步骤就派子代理做。
独立性不足（不能派子代理）时，本评测允许照常做完，相关步骤标「未独立验证」；不能据此宣称独立验收通过。
这是本评测对独立性不足的例外；其余前置条件不满足时按 SKILL.md 停止并交回限制。

完整流程及消费记录完成后，再依次处理工作目录 `stops/01-quotes/`、`stops/02-propagation/`、`stops/03-entry/`。
每次先读该目录的 `CONTINUE.md`，采用其中材料继续；运行检查仍经同一个日志包装器，保留命令、修改和复查记录。
