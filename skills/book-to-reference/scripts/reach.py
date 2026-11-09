"""可达测试的机械参考答案；相邻路线是否足够完成任务仍由人判断。"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import re
import sys

import yaml

from bookconf import open_workdir, resolve
from chain import REFS_MARKER, parse_run
from stage1 import read_tasks


def expected_cards(cfg, workdir: Path) -> dict[str, list[str]]:
    plan = resolve(cfg, workdir, "card_plan").read_text(encoding="utf-8")
    unit_card = {}
    for match in re.finditer(r"^\| \d+ \| ([a-z0-9-]+) \|(?:[^|]*\|){2}([^|]*)\|", plan, re.M):
        for uid in re.findall(r"u\d\d-\d\d", match.group(2).split("（")[0]):
            unit_card[uid] = match.group(1)
    data = [yaml.safe_load(path.read_text(encoding="utf-8"))
            for path in sorted(resolve(cfg, workdir, "verify_out").glob("*.yaml"))]
    verified = {unit["unit_id"] for group in data for unit in group["units"] if unit["decision"] == "verified"}
    result = defaultdict(set)
    for group in data:
        for task, row in (group.get("coverage") or {}).items():
            for uid in row.get("units") or []:
                if uid in verified and uid in unit_card:
                    result[task].add(unit_card[uid])
    return {task: sorted(result[task]) for task in sorted(result)}


def pick(expected, per_card: int, seed: int, used: set[str]) -> list[str]:
    if per_card < 1:
        raise ValueError("per_card 必须大于 0")
    rng = random.Random(seed)
    by_card = defaultdict(list)
    for task in sorted(expected):
        for card in sorted(expected[task]):
            by_card[card].append(task)
    picked = []
    for card in sorted(by_card):
        tasks = sorted(by_card[card], key=lambda task: (task in used, len(expected[task]), rng.random()))
        for task in tasks:
            if task not in picked and sum(card in expected[prior] for prior in picked) < per_card:
                picked.append(task)
    rng.shuffle(picked)
    return picked


def score(runs_dir: Path, id_map: dict, expected: dict, card_prefix: str) -> dict[str, str]:
    result = {}
    for qid, item in sorted(id_map.items()):
        run = parse_run(Path(runs_dir) / f"{qid}-r1.jsonl")
        if not run.ok:
            result[qid] = "FAILED"
            continue
        names = [path.rsplit("/", 1)[-1] for path in run.reads]
        fired = any(skill.split(":")[-1] == "game-design-theory" for skill in run.skills)
        if item.startswith(("d", "x")):
            result[qid] = "FIRED" if fired or any(REFS_MARKER in path for path in run.reads) else "REJECT"
        elif item.startswith("p-"):
            accepted = expected.get(item, [])
            hit = any("/references/" in path and path.rsplit("/", 1)[-1] in accepted
                      and path.rsplit("/", 1)[-1] != "SKILL.md" for path in run.reads)
            result[qid] = "HIT" if hit else "MISS"
        else:
            cards = [name[len(card_prefix):-3] for name in names
                     if name.startswith(card_prefix) and name.endswith(".md") and name != card_prefix + "notes.md"]
            accepted = set(expected.get(item, []))
            result[qid] = ("STRICT" if cards and cards[0] in accepted else "ANY" if accepted.intersection(cards)
                           else "OTHER" if cards else "NONE")
    return result


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("expected", "pick", "score"):
        command = commands.add_parser(name)
        command.add_argument("workdir", type=Path)
        command.add_argument("--out", type=Path)
        if name == "pick":
            command.add_argument("--per-card", type=int, default=2)
            command.add_argument("--seed", type=int, required=True)
            command.add_argument("--used", type=Path)
            command.add_argument("--out-dir", type=Path, required=True)
        elif name == "score":
            command.add_argument("--runs-dir", required=True, type=Path)
            command.add_argument("--id-map", required=True, type=Path)
            command.add_argument("--expected", required=True, type=Path, nargs="+")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = open_workdir(args.workdir)
        from bookconf import check_work_output
        for name in ("out", "out_dir"):
            if getattr(args, name, None) is not None:
                setattr(args, name, check_work_output(getattr(args, name), cfg))
        if args.command == "score":
            expected = {}
            for path in args.expected:
                expected.update(json.loads(path.read_text(encoding="utf-8")))
            result = score(args.runs_dir, json.loads(args.id_map.read_text(encoding="utf-8")),
                           expected, cfg.prefix)
        else:
            result = expected_cards(cfg, args.workdir)
            if args.command == "pick":
                used = json.loads(args.used.read_text(encoding="utf-8")) if args.used else []
                used = set(used.values() if isinstance(used, dict) else used)
                selected = pick(result, args.per_card, args.seed, used)
                tasks = read_tasks(resolve(cfg, args.workdir, "overview").read_text(encoding="utf-8"))
                result = {task: result[task] for task in selected}
                args.out_dir.mkdir(parents=True, exist_ok=True)
                writer = [{"id": task, "task": tasks.get(task, "?")} for task in selected]
                (args.out_dir / "tasks-for-prompt-writer.yaml").write_text(
                    yaml.safe_dump(writer, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8", newline="\n")
                (args.out_dir / "expected.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
                print(f"picked: {len(selected)}; writer tasks and expected cards saved separately")
                return 0
        text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8", newline="\n")
        else:
            print(text, end="")
        return 1 if args.command == "score" and "FAILED" in result.values() else 0
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
