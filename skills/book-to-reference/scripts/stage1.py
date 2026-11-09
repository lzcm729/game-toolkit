"""用任务清单审计候选，保留坏输入的证据，不能把解析失败当成没有问题。"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path
import re
import sys

import yaml

from bookconf import open_workdir, resolve


KINDS = ("framework", "principle", "case", "counter_example", "term")


@dataclass
class CoverageResult:
    by_task: dict[str, dict[str, int]]
    problems: list[str]
    scope: dict[str, dict] = field(default_factory=dict)


def read_tasks(overview_md: str) -> dict[str, str]:
    tasks = {}
    duplicates = set()
    for line in overview_md.splitlines():
        match = re.match(r"^\|\s*(t\d{2}-\d{2})\s*\|\s*([^|]*)\|", line)
        if match:
            task, description = match.groups()
            if task in tasks:
                duplicates.add(task)
            tasks[task] = description.strip()
    if duplicates:
        raise ValueError(f"duplicate task ids: {', '.join(sorted(duplicates))}")
    return tasks


def named_yaml(directory: Path, name: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name):
        raise ValueError(f"不安全的组或批次名: {name}")
    path = directory / f"{name}.yaml"
    if not path.resolve().is_relative_to(directory.resolve()):
        raise ValueError(f"输出路径逃出目录: {path}")
    return path


def candidate_sources(cfg, workdir: Path) -> dict[str, list[Path]]:
    directory = resolve(cfg, workdir, "candidates")
    sources = {}
    for kind, stem in (("framework", "frameworks"), ("principle", "principles")):
        # parts 和合并文件含相同记录；优先读取 parts，避免双重计数。
        parts = sorted((directory / "parts").glob(f"{stem}-*.md"))
        sources[kind] = parts or [directory / f"{stem}.md"]
    sources.update({"case": [directory / "cases.md"],
                    "counter_example": [directory / "counter-examples.md"],
                    "term": [resolve(cfg, workdir, "glossary")]})
    return sources


def candidates(cfg, workdir: Path) -> tuple[dict[str, list[dict]], list[str]]:
    data = {kind: [] for kind in KINDS}
    problems = []
    for kind, paths in candidate_sources(cfg, workdir).items():
        seen = set()
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for number, block in enumerate(re.findall(r"```yaml[ \t]*\n(.*?)```", text, re.S), 1):
                try:
                    value = yaml.safe_load(block)
                except yaml.YAMLError as exc:
                    problems.append(f"{path.name} block {number}: YAML {exc}")
                    continue
                for item in value if isinstance(value, list) else [value]:
                    if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                        problems.append(f"{path.name} block {number}: candidate missing id")
                        continue
                    if item["id"] in seen:
                        problems.append(f"{kind}: duplicate candidate id {item['id']}")
                    seen.add(item["id"])
                    data[kind].append(item)
    return data, problems


def scope_dispositions(path: Path, tasks: dict[str, str]) -> tuple[dict[str, dict], list[str]]:
    if not path.exists():
        return {}, []
    try:
        entries = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return {}, [f"scope: {exc}"]
    if not isinstance(entries, list):
        return {}, ["scope 必须是 list"]
    adopted, problems, seen = {}, [], set()
    for number, item in enumerate(entries, 1):
        if not isinstance(item, dict):
            problems.append(f"scope {number}: 必须是 mapping")
            continue
        task = item.get("task_id")
        if not isinstance(task, str) or task not in tasks:
            problems.append(f"scope {number}: unknown task_id {task}")
            continue
        if task in seen:
            problems.append(f"scope: duplicate task_id {task}")
            continue
        seen.add(task)
        if item.get("decision") not in ("reference_only", "out_of_scope"):
            problems.append(f"scope {task}: decision 无效")
            continue
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            problems.append(f"scope {task}: reason 必须非空")
            continue
        adopted[task] = item
    return adopted, problems


def coverage(cfg, workdir: Path) -> CoverageResult:
    tasks = read_tasks(resolve(cfg, workdir, "overview").read_text(encoding="utf-8"))
    data, problems = candidates(cfg, workdir)
    scope_path = resolve(cfg, workdir, "scope")
    scope, scope_problems = scope_dispositions(scope_path, tasks)
    problems.extend(scope_problems)
    columns = ("framework", "principle", "case", "counter", "term")
    by_task = {task: dict.fromkeys(columns, 0) for task in tasks}
    for kind, items in data.items():
        for item in items:
            task_ids = item.get("task_ids") or []
            if isinstance(task_ids, str):
                task_ids = [task_ids]
            for task in task_ids:
                task = str(task).strip()
                if task not in tasks:
                    problems.append(f"{item['id']}: unknown task_id {task}")
                else:
                    column = "counter" if kind == "counter_example" else kind
                    by_task[task][column] += 1
    rows = ["# 阶段 1 覆盖审计（脚本生成）", "",
            "| task_id | 任务 | framework | principle | case | counter | term | 状态 |",
            "|---|---|---|---|---|---|---|---|"]
    for task, counts in by_task.items():
        if counts["framework"] + counts["principle"]:
            status = "有可执行候选"
        else:
            status = "仅支持材料" if any(counts.values()) else "无候选"
            if task in scope:
                status = scope[task]["decision"]
            else:
                problems.append(f"{task}: {status}，没有可执行候选")
        cells = " | ".join(str(counts[kind]) for kind in columns)
        rows.append(f"| {task} | {tasks[task][:40]} | {cells} | {status} |")
    if not tasks:
        problems.append("任务表为空")
    if scope_path.exists():
        rows.extend(["", "## 范围处置（不等于内容已交付）", ""])
        for task, item in scope.items():
            reason = item["reason"].replace("|", "／").replace("\n", " ")
            rows.append(f"- {task}: {item['decision']}；{reason}；pages={item.get('pages', [])}")
        if not scope:
            rows.append("无")
    rows.extend(["", "## 问题", "", *(problems or ["无"])])
    destination = resolve(cfg, workdir, "candidates") / "_coverage-stage1.md"
    destination.write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    return CoverageResult(by_task, problems, scope)


def chapter_key(source_chapter: str, mapping: dict[str, str] | None = None) -> str | None:
    if mapping and source_chapter in mapping:
        return mapping[source_chapter]
    text = str(source_chapter).lower()
    match = re.search(r"\bch(?:apter)?\s*(\d+)", text)
    if match:
        return str(int(match.group(1)))
    if re.fullmatch(r"\d+", text):
        return str(int(text))
    if text in {"pre", "quiz", "end", "books", "sources"} or re.fullmatch(r"p\d+", text):
        return text
    if "preface" in text:
        return "pre"
    match = re.search(r"\bpart\s+(one|two|three|four|five|\d+|iii|ii|i)\b", text)
    if match:
        number = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "i": 1, "ii": 2, "iii": 3}.get(match.group(1), match.group(1))
        return f"p{number}"
    for word, key in (("endgame", "end"), ("quiz", "quiz"), ("recommended", "books"), ("sources", "sources")):
        if word in text:
            return key
    return None


def split_candidates(cfg, workdir: Path) -> dict[str, dict[str, list]]:
    data, problems = candidates(cfg, workdir)
    buckets = {group: {kind: [] for kind in KINDS} for group in cfg.verify_groups}
    groups = {key: group for group, keys in cfg.verify_groups.items() for key in keys}
    for kind, items in data.items():
        for item in items:
            key = chapter_key(item.get("source_chapter", ""), cfg.chapter_map)
            group = groups.get(key)
            if group is None:
                problems.append(f"{item['id']}: unmapped chapter {key!r}: {item.get('source_chapter')}")
            else:
                buckets[group][kind].append(item)
    if problems:
        raise ValueError("\n".join(problems))
    directory = resolve(cfg, workdir, "verify_in")
    destinations = {group: named_yaml(directory, group) for group in buckets}
    directory.mkdir(parents=True, exist_ok=True)
    for group, data in buckets.items():
        destinations[group].write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=200),
                                       encoding="utf-8", newline="\n")
    return buckets


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["tasks", "coverage", "split"])
    parser.add_argument("workdir", type=Path)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = open_workdir(args.workdir)
        if args.command == "tasks":
            tasks = read_tasks(resolve(cfg, args.workdir, "overview").read_text(encoding="utf-8"))
            for task, description in tasks.items():
                print(f"{task}: {description}")
            if not tasks:
                raise ValueError("任务表为空")
        elif args.command == "coverage":
            result = coverage(cfg, args.workdir)
            print(f"tasks: {len(result.by_task)}; problems: {len(result.problems)}")
            for task, item in result.scope.items():
                print(f"scope {task}: {item['decision']}; {item['reason']}; pages={item.get('pages', [])}")
            for problem in result.problems:
                print(problem)
            return 1 if result.problems else 0
        else:
            for group, data in split_candidates(cfg, args.workdir).items():
                print(group, {kind: len(items) for kind, items in data.items()})
    except (OSError, ValueError, TypeError, yaml.YAMLError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
