"""消费链只记录观察到的成功读取，归因不能改变质量判定。"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import sys


REFS_MARKER = "/game-design-theory/references/"


@dataclass
class Run:
    path: Path
    ok: bool
    skills: list[str]
    reads: list[str]
    cost: float
    answer: str | None
    model: str
    cc_version: str


def successful(events: list[dict]) -> bool:
    if not events:
        return False
    final = events[-1]
    return (isinstance(final, dict) and final.get("type") == "result" and final.get("subtype") == "success"
            and not final.get("is_error") and isinstance(final.get("result"), str)
            and bool(final["result"].strip()))


def parse_run(jsonl: Path) -> Run:
    jsonl = Path(jsonl)
    events = []
    valid = True
    try:
        for line in jsonl.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                event = json.loads(line)
                if not isinstance(event, dict):
                    continue
                events.append(event)
    except (OSError, ValueError):
        valid = False
    skills = []
    read_calls = {}
    read_success = set()
    model = version = ""
    for event in events:
        if event.get("type") == "system" and event.get("subtype") == "init":
            model = event.get("model") if isinstance(event.get("model"), str) else ""
            version = event.get("claude_code_version") if isinstance(event.get("claude_code_version"), str) else ""
        message = event.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and event.get("type") == "assistant":
                inputs = block.get("input")
                if not isinstance(inputs, dict):
                    continue
                if block.get("name") == "Skill":
                    skill = inputs.get("skill")
                    if isinstance(skill, str) and skill:
                        skills.append(skill)
                elif block.get("name") == "Read":
                    call_id, path = block.get("id"), inputs.get("file_path")
                    if isinstance(call_id, str) and call_id and isinstance(path, str):
                        read_calls[call_id] = path.replace("\\", "/")
            elif block.get("type") == "tool_result":
                call_id = block.get("tool_use_id")
                if not isinstance(call_id, str) or not call_id:
                    continue
                if not block.get("is_error"):
                    read_success.add(call_id)
                else:
                    read_success.discard(call_id)
    reads = [path for key, path in read_calls.items() if key in read_success and path]
    ok = valid and successful(events)
    final = events[-1] if events and events[-1].get("type") == "result" else {}
    # 费用元数据的形态变化不能掩盖已经观察到的调用和成功回答。
    try:
        cost = float(final.get("total_cost_usd") or 0)
    except (TypeError, ValueError, OverflowError):
        cost = 0.0
    if not math.isfinite(cost):
        cost = 0.0
    return Run(jsonl, ok, skills, reads, cost, final["result"] if ok else None, model, version)


def counts(runs: list[Run], refs_marker: str, card_prefix: str) -> dict[str, int]:
    result = dict.fromkeys(("runs", "failed", "skill", "skill_and_any_book_ref", "skill_and_card",
                            "skill_but_no_book_ref", "no_skill"), 0)
    for run in runs:
        result["runs"] += 1
        if not run.ok:
            result["failed"] += 1
            continue
        if not any(skill.startswith("game-toolkit:") for skill in run.skills):
            result["no_skill"] += 1
            continue
        result["skill"] += 1
        refs = [path for path in run.reads if refs_marker in path]
        result["skill_and_any_book_ref"] += bool(refs)
        result["skill_and_card"] += any(path.rsplit("/", 1)[-1].startswith(card_prefix) for path in refs)
        result["skill_but_no_book_ref"] += not refs
    return result


def per_question(dirs: dict[str, Path], card_prefix: str) -> str:
    lines = ["| 题与重复 | 版本 | 完成 | 本插件激活 | 读卡 | 成功读取的文件 | 美元 |",
             "|---|---|---|---|---|---|---|"]
    for variant, directory in dirs.items():
        for path in sorted(Path(directory).glob("*.jsonl")):
            run = parse_run(path)
            row = counts([run], REFS_MARKER, card_prefix)
            reads = "<br>".join(run.reads).replace("|", "／") or "—"
            lines.append(f"| {path.stem} | {variant} | {run.ok} | {row['skill']} | {row['skill_and_card']} | {reads} | {run.cost:.3f} |")
    return "\n".join(lines) + "\n"


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("counts", "per-question"):
        command = commands.add_parser(name)
        command.add_argument("dirs", nargs="+")
        command.add_argument("--card-prefix", required=True)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "counts":
            failed = False
            for directory in args.dirs:
                path = Path(directory)
                if not path.is_dir():
                    raise ValueError(f"运行目录不存在: {path}")
                runs = [parse_run(file) for file in sorted(path.glob("*.jsonl"))]
                result = counts(runs, REFS_MARKER, args.card_prefix)
                print(path.as_posix(), json.dumps(result, ensure_ascii=False))
                failed |= bool(result["failed"]) or not runs
            return 1 if failed else 0
        dirs = dict(item.split("=", 1) for item in args.dirs)
        print(per_question(dirs, args.card_prefix), end="")
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
