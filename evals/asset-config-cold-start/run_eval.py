#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""asset-config 冷启动评测：让一个**没有本插件开发上下文**的 AI，只照着
`skills/asset-config/SKILL.md` 从零建一份配置，看它会在哪里走偏。

为什么要有这个：指引和校验器是同一份契约的两面。我们自己读指引时脑子里有上下文，
会自动补上它没写的部分；一个照字面执行的外人才会撞上「指引没说」「指引和校验器
说的不一样」。4.4.0 的五处修正全是这么撞出来的。

**不进普通测试套件**：要调外部 AI、要联网、花钱，一轮约 7 分钟，结果也不确定。
改了 `asset-config/SKILL.md` 或 `check_config.py` 之后手动跑一次。

用法：

    python evals/asset-config-cold-start/run_eval.py                  # 缺省用 codex
    python evals/asset-config-cold-start/run_eval.py --agent-cmd "<命令模板>"
    python evals/asset-config-cold-start/run_eval.py --grade-only <上次的结果目录>

`--agent-cmd` 是别的 AI CLI 的命令模板，可用占位符 `{workdir}` `{prompt_file}`
`{output}`。它要能在 `{workdir}` 里读写文件、跑命令；最终回答写进 `{output}`，
没写的话把它的 stdout 存进去。

两轮之间**开新会话**、不续上一轮 —— 续会话不是每个 CLI 都有，而第一轮的草稿都在
`QUESTIONS.md` 里，从盘上读就够了。第二轮的答案按事情写、不按题号写，换个 AI
问题编号对不上也不影响。
"""
from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import grade  # noqa: E402

REPO = grade.REPO
FIXTURE = HERE / "fixture"
PROMPTS = HERE / "prompts"

# 夹具里有些文件不能照原名放进插件仓库：嵌套的 .gitignore 会让插件仓库自己
# 也忽略 fixture/SourceArt/，那张被忽略的旧稿就提交不进来了。复制时再改回去。
_RENAMES = {"gitignore.txt": ".gitignore"}
# git 不跟踪空目录，但「Content/ 存在且为空」是夹具的一部分（UE 导入后的资产目录）
_EMPTY_DIRS = ("Content",)

ROUND_TIMEOUT_S = 40 * 60


def _posix(p: Path) -> str:
    return str(p).replace("\\", "/")


def prepare(base: Path) -> Path:
    """把夹具铺成一个干净的 git 仓库，只有一个初始提交。"""
    workdir = base / "project"
    shutil.copytree(FIXTURE, workdir)
    for src, dst in _RENAMES.items():
        if (workdir / src).exists():
            (workdir / src).rename(workdir / dst)
    for d in _EMPTY_DIRS:
        (workdir / d).mkdir(exist_ok=True)

    def git(*args):
        subprocess.run(["git", "-c", "safe.directory=*", "-C", str(workdir), *args],
                       check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "eval@example.invalid")
    git("config", "user.name", "eval")
    git("config", "core.autocrlf", "false")
    git("add", "-A")
    git("commit", "-q", "-m", "init")
    return workdir


def render(name: str, python: str) -> str:
    text = (PROMPTS / name).read_text(encoding="utf-8")
    return text.format(
        skill=_posix(REPO / "skills" / "asset-config" / "SKILL.md"),
        readme=_posix(REPO / "skills" / "generate-assets" / "examples" / "README.md"),
        check=_posix(grade.CHECK),
        generate=_posix(grade.GENERATE),
        python=_posix(Path(python)),
    )


def run_agent(workdir: Path, prompt_file: Path, output: Path, log: Path,
              agent_cmd: "str | None") -> int:
    with open(prompt_file, "rb") as stdin, open(log, "wb") as out:
        if agent_cmd:
            cmd = shlex.split(agent_cmd.format(
                workdir=str(workdir), prompt_file=str(prompt_file), output=str(output)),
                posix=(sys.platform != "win32"))
        else:
            codex = shutil.which("codex")
            if codex is None:
                raise SystemExit("[fatal] 找不到 codex。装好它，或用 --agent-cmd 指定别的 AI CLI。")
            # 指令从 stdin 进（`-`）：多行 prompt 走命令行参数，在 Windows 上经
            # npm 的 .cmd 包装一道会被弄坏换行；stdin 读到文件末尾也就自然关闭，
            # 不会像接了个不关的管道那样挂住。
            cmd = [codex, "exec", "-s", "workspace-write", "-C", str(workdir),
                   "-o", str(output), "-"]
        try:
            r = subprocess.run(cmd, stdin=stdin, stdout=out, stderr=subprocess.STDOUT,
                               timeout=ROUND_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return 124
    if not output.exists():
        output.write_bytes(log.read_bytes())
    return r.returncode


def _table(checks) -> list:
    rows = ["| 考点 | 结果 | 说明 |", "|---|---|---|"]
    for c in checks:
        tag = "（启发式）" if c.heuristic else ""
        rows.append(f"| `{c.id}`{tag} | {c.mark} | {c.detail} |")
    return rows


def report(base: Path, workdir: Path, r1: list, r2: list, codes: dict) -> "tuple[str, bool]":
    ok = not any(c.passed is False for c in r1 + r2)
    p1, f1, n1 = grade.summarize(r1)
    p2, f2, n2 = grade.summarize(r2)
    lines = [
        "# asset-config 冷启动评测结果",
        "",
        f"- 工程：`{workdir}`",
        f"- 退码：第一轮 {codes.get('r1', '—')}，第二轮 {codes.get('r2', '—')}",
        f"- 自动项：第一轮 过 {p1} / 不过 {f1} / 判不了 {n1}；"
        f"第二轮 过 {p2} / 不过 {f2} / 判不了 {n2}",
        "",
        "**自动项全过不等于评测通过。**下面「人工核对」那几条只能对着 `rubric.md` 看；"
        "最有价值的产出往往是 AI 在最终回答里指出的「指引拿不准 / 指引和校验器不一致」。",
        "",
        "## 第一轮（只该交草稿和问题）",
        "",
        *_table(r1),
        "",
        "## 第二轮（写配置、过校验）",
        "",
        *_table(r2),
        "",
        "## 人工核对（对着 rubric.md）",
        "",
        f"- 第一轮的草稿与问题：`{workdir / 'QUESTIONS.md'}`",
        f"- 第一轮最终回答：`{base / 'round1.answer.md'}`",
        f"- 第二轮最终回答：`{base / 'round2.answer.md'}` —— **先看它最后一节**",
        f"- 评分标准：`{HERE / 'rubric.md'}`",
        "",
        "要人看的几条：必问的三项是不是真的**问**了（给了候选和理由），而不是替用户定了；"
        "是不是先问能力、再问后端和模型；验收条件具体不具体；有没有宣称已经完成。",
    ]
    return "\n".join(lines) + "\n", ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="asset-config 冷启动评测")
    ap.add_argument("--agent-cmd", help="别的 AI CLI 的命令模板（占位符 {workdir} {prompt_file} {output}）")
    ap.add_argument("--grade-only", metavar="DIR", help="只对一次已有的结果评分（run_eval 输出的那个目录）")
    ap.add_argument("--python", default=sys.executable, help="给 AI 用、也给评分用的 Python（要有 PyYAML）")
    args = ap.parse_args(argv)

    if args.grade_only:
        base = Path(args.grade_only)
        workdir = base / "project"
        r1 = grade.grade_round1(workdir) if not (workdir / "asset-config.yaml").exists() else []
        r2 = grade.grade_round2(workdir, args.python)
        text, ok = report(base, workdir, r1, r2, {})
        print(text)
        return 0 if ok else 1

    base = Path(tempfile.mkdtemp(prefix="asset-config-eval-"))
    workdir = prepare(base)
    print(f"[eval] 工程铺在 {workdir}", flush=True)

    codes = {}
    for rnd in ("round1", "round2"):
        prompt_file = base / f"{rnd}.prompt.md"
        prompt_file.write_text(render(f"{rnd}.md", args.python), encoding="utf-8")
        print(f"[eval] {rnd} 开跑（约 7 分钟）…", flush=True)
        codes[rnd[:1] + rnd[-1]] = run_agent(
            workdir, prompt_file, base / f"{rnd}.answer.md", base / f"{rnd}.log", args.agent_cmd)
        if rnd == "round1":
            # 第一轮的评分要在第二轮改动工作区**之前**做
            r1 = grade.grade_round1(workdir)

    r2 = grade.grade_round2(workdir, args.python)
    text, ok = report(base, workdir, r1, r2, codes)
    (base / "report.md").write_text(text, encoding="utf-8")
    print(text)
    print(f"[eval] 报告：{base / 'report.md'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
