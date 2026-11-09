"""汇总验证与复核；审计表可重算，原始复核记录始终单独保留。

组和复核批次按文件名自然排序（G2 在 G10 前）；同一单元以较后批次为准。
指定 batches 是筛选，不改变先后关系，重跑旧批次也不能覆盖已应用的新批次。
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import sys

import yaml

from bookconf import open_workdir, resolve
from stage1 import candidate_sources, named_yaml, read_tasks


KEEP = ("unit_id", "title", "type", "one_liner", "source_evidence", "task_ids")
DOUBT = re.compile(r"偏宽|收窄|拿不准|我的判断|我归纳|原图缺失|图缺失|无判据|没有判据|未给|没给|没有给|只有一个|经验阈值|重建|也可(以)?(改)?判|也说得通|类推|勉强")
DECISIONS = ("verified", "reference", "needs_review", "rejected")


@dataclass
class AggregateResult:
    problems: list[str]
    counts: dict[str, int]


def _natural(path: Path):
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", path.stem))


def _read(path: Path) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: expected YAML mapping")
    return data


def _groups(cfg, workdir: Path) -> dict[str, dict]:
    paths = sorted(resolve(cfg, workdir, "verify_out").glob("*.yaml"), key=_natural)
    if not paths:
        raise ValueError("no verification output files")
    return {path.stem: _read(path) for path in paths}


def _dump(data) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=200)


def _dump_unit(unit) -> str:
    return "```yaml\n" + _dump({key: value for key, value in unit.items() if not key.startswith("_")}) + "```\n"


def _doubt_text(unit) -> str:
    keys = ("decision_reason", "gaps", "V1_source_sufficiency", "V2_executability", "V3_task_utility")
    return " ".join(str(unit.get(key, "")) for key in keys)


def aggregate(cfg, workdir: Path) -> AggregateResult:
    workdir = Path(workdir).resolve()
    groups = _groups(cfg, workdir)
    units = []
    dispositions = {}
    covered = {}
    problems = []
    inputs = resolve(cfg, workdir, "verify_in")
    missing_groups = sorted(path.stem for path in inputs.glob("*.yaml") if path.stem not in groups)
    if missing_groups:
        problems.append(f"groups without verification output: {missing_groups}")
    for group, out in groups.items():
        inp = _read(named_yaml(inputs, group))
        candidate_ids = {item["id"] for kind in ("framework", "principle") for item in inp[kind]}
        for unit in out["units"]:
            units.append({**unit, "_group": group})
            if unit.get("decision") not in DECISIONS:
                problems.append(f"{unit.get('unit_id')}: invalid decision {unit.get('decision')}")
        disposition = out.get("candidate_disposition") or {}
        missing = candidate_ids - set(disposition)
        extra = set(disposition) - candidate_ids
        if missing or extra:
            problems.append(f"{group}: disposition missing {sorted(missing)[:8]} extra {sorted(extra)[:8]}")
        repeated = set(dispositions) & set(disposition)
        if repeated:
            problems.append(f"{group}: duplicate dispositions {sorted(repeated)}")
        dispositions.update(disposition)
        for task, row in (out.get("coverage") or {}).items():
            if task in covered:
                problems.append(f"{group}: task {task} also covered by another group")
            covered[task] = row
    id_count = Counter(unit["unit_id"] for unit in units)
    duplicates = sorted(uid for uid, count in id_count.items() if count > 1)
    if duplicates:
        problems.append(f"duplicate unit ids: {duplicates}")
    for candidate, target in dispositions.items():
        if isinstance(target, str) and target not in id_count:
            problems.append(f"candidate {candidate} -> unknown unit {target}")
        elif not isinstance(target, str) and not (isinstance(target, dict) and "rejected" in target):
            problems.append(f"candidate {candidate}: invalid disposition {target!r}")
    tasks = read_tasks(resolve(cfg, workdir, "overview").read_text(encoding="utf-8"))
    missing_tasks = sorted(set(tasks) - set(covered))
    if missing_tasks:
        problems.append(f"tasks without coverage row: {missing_tasks}")
    if not tasks:
        problems.append("任务表为空")
    for task, row in covered.items():
        if task not in tasks:
            problems.append(f"unknown coverage task: {task}")
        for uid in row.get("units") or []:
            if uid not in id_count:
                problems.append(f"{task}: coverage refers to unknown unit {uid}")
    by_decision = defaultdict(list)
    for unit in units:
        by_decision[unit.get("decision")].append(unit)
    flags = [unit for unit in by_decision["verified"] if DOUBT.search(_doubt_text(unit))]

    def write(name, title, items):
        body = [f"# {title}", "", f"共 {len(items)} 个单元（阶段 1.5 汇总，脚本生成；来源 verify/out/G*.yaml）", ""]
        for unit in sorted(items, key=lambda item: item["unit_id"]):
            body.extend([f"## {unit['unit_id']} {unit.get('title', '')}（{unit['_group']}）", "", _dump_unit(unit)])
        (workdir / name).write_text("\n".join(body), encoding="utf-8", newline="\n")

    write("verified.md", "verified — 三重验证通过", by_decision["verified"])
    write("references.md", "reference — 有来源价值但不可独立执行", by_decision["reference"])
    write("needs-review.md", "needs_review — 缺关键条件，不进入 active 能力池", by_decision["needs_review"])
    rejected = workdir / "rejected"
    rejected.mkdir(exist_ok=True)
    for candidate, target in sorted(dispositions.items()):
        if isinstance(target, dict) and "rejected" in target:
            path = named_yaml(rejected, candidate).with_suffix(".md")
            path.write_text(f"# {candidate}\n\n{target['rejected']}\n", encoding="utf-8", newline="\n")
    for unit in sorted(by_decision["rejected"], key=lambda item: item["unit_id"]):
        path = named_yaml(rejected, unit["unit_id"]).with_suffix(".md")
        path.write_text(_dump_unit(unit), encoding="utf-8", newline="\n")
    decisions = {unit["unit_id"]: unit.get("decision") for unit in units}
    rows = ["# coverage-audit（阶段 1.5，脚本生成）", "", "| task_id | 读者任务 | 单元 | 单元去向 | 任务状态 | 备注 |", "|---|---|---|---|---|---|"]
    for task, description in tasks.items():
        row = covered.get(task) or {}
        ids = row.get("units") or []
        rows.append(f"| {task} | {description[:36]} | {', '.join(ids)} | {', '.join(str(decisions.get(uid)) for uid in ids)} | {row.get('status')} | {str(row.get('note', ''))[:60]} |")
    (workdir / "coverage-audit.md").write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    lines = ["# 待复核：判了 verified、但自述理由里有存疑信号的单元（脚本按关键词筛出）", ""]
    for unit in flags:
        signals = sorted({match.group(0) for match in DOUBT.finditer(_doubt_text(unit))})
        lines.append(f"- {unit['unit_id']}（{unit['_group']}，{unit.get('importance')}）{unit.get('title')} — 信号：{signals}")
    # _flags 属于 verify 这一阶段，不跟随首轮输出目录的最后一层名称。
    flags_path = inputs.parent / "_flags.md"
    flags_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    counts = {decision: len(by_decision[decision]) for decision in DECISIONS}
    counts.update(groups=len(groups), units=len(units), candidates=len(dispositions), flagged=len(flags))
    return AggregateResult(problems, counts)


def recheck_input(cfg, workdir: Path, batch: str, ids: list[str]) -> Path:
    want = set(ids)
    rows = []
    found = set()
    for group, data in _groups(cfg, workdir).items():
        for unit in data["units"]:
            uid = unit["unit_id"]
            if uid in want or group in want:
                found.update({uid, group})
                if unit.get("decision") == "verified":
                    rows.append({key: unit.get(key) for key in KEEP})
    if want - found:
        raise ValueError(f"unknown unit or group: {sorted(want - found)}")
    destination = named_yaml(resolve(cfg, workdir, "recheck_in"), batch)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_dump({"batch": batch, "units": rows}), encoding="utf-8", newline="\n")
    return destination


def apply_recheck(cfg, workdir: Path, batches: list[str] | None, dry: bool) -> list[str]:
    groups = _groups(cfg, workdir)
    units = {}
    where = {}
    for group, data in groups.items():
        for unit in data["units"]:
            uid = unit["unit_id"]
            if uid in units:
                raise ValueError(f"duplicate unit id: {uid}")
            units[uid] = unit
            where[uid] = group
    paths = sorted(resolve(cfg, workdir, "recheck_out").glob("*.yaml"), key=_natural)
    records = [(index, path, _read(path)) for index, path in enumerate(paths)]
    applied_through = {}
    for index, path, data in records:
        batch = data.get("batch", path.stem)
        for record in data["units"]:
            uid = record["unit_id"]
            if uid in units and (units[uid].get("recheck") or {}).get("batch") == batch:
                applied_through[uid] = index
    if batches:
        unknown = set(batches) - {path.stem for path in paths}
        if unknown:
            raise ValueError(f"unknown recheck batch: {sorted(unknown)}")
        records = [row for row in records if row[1].stem in batches]
    changes = []
    touched = set()
    changed_ids = set()
    for index, path, data in records:
        batch = data.get("batch", path.stem)
        for record in data["units"]:
            uid = record["unit_id"]
            if uid not in units:
                raise ValueError(f"UNKNOWN unit {uid}")
            # 一条单元可能先后复核多次；重跑不能先退回旧批次再套新批次。
            if index <= applied_through.get(uid, -1):
                continue
            unit = units[uid]
            if (unit.get("recheck") or {}).get("batch") == batch:
                continue
            before = unit["decision"]
            after = record["decision_after"]
            if after not in DECISIONS:
                raise ValueError(f"{uid}: invalid decision_after {after}")
            unit["recheck"] = {
                "batch": batch, "decision_before": before, "decision_after": after,
                "key_judgment": record.get("key_judgment"), "narrowing": record.get("narrowing"),
                "must_go_to_boundary": record.get("must_go_to_boundary") or [],
                "covered_by": record.get("covered_by"), "reason": record.get("reason"),
            }
            unit["decision"] = after
            unit["decision_reason"] = f"{unit.get('decision_reason', '')}（复核 {path.stem}：{record.get('reason', '')}）"
            if record.get("gaps"):
                unit["gaps"] = list(unit.get("gaps") or []) + [f"复核：{gap}" for gap in record["gaps"]]
            touched.add(where[uid])
            if before != after:
                changed_ids.add(uid)
            narrowed = str(record.get("narrowing") or "无").strip() not in ("无", "", "None")
            changes.append(f"{uid}: {before} -> {after}{'  [narrowed]' if narrowed else ''}")
    for group, data in groups.items():
        for task, row in (data.get("coverage") or {}).items():
            ids = row.get("units") or []
            if not set(ids) & changed_ids:
                continue
            decisions = {units[uid]["decision"] for uid in ids if uid in units}
            new = ("covered" if "verified" in decisions else "needs_review" if "needs_review" in decisions
                   else "reference_only" if "reference" in decisions else "gap")
            old = row.get("status")
            if new != old:
                row["status"] = new
                row["note"] = f"{row.get('note', '')}（复核前 {old}，复核后 {new}）".strip()
                touched.add(group)
    if not dry:
        directory = resolve(cfg, workdir, "verify_out")
        for group in sorted(touched):
            path = named_yaml(directory, group)
            backup = path.with_suffix(".yaml.pre-recheck.bak")
            if not backup.exists():
                shutil.copyfile(path, backup)
            path.write_text(_dump(groups[group]), encoding="utf-8", newline="\n")
    return changes


def show(cfg, workdir: Path, ids: list[str]) -> str:
    want = set(ids)
    selected = {}
    found = set()
    support_ids = {uid for uid in want if re.match(r"(?:c|ce|g)-", uid)}
    for group, data in _groups(cfg, workdir).items():
        for unit in data["units"]:
            uid = unit["unit_id"]
            if uid in want or group in want:
                selected[uid] = unit
                found.update({uid, group})
                for entries in (unit.get("supports") or {}).values():
                    support_ids.update(entries or [])
    out = []
    for uid, unit in selected.items():
        out.extend([f"########## {uid}", _dump(unit)])
    for path in sorted(resolve(cfg, workdir, "recheck_out").glob("*.yaml"), key=_natural):
        data = _read(path)
        for record in data["units"]:
            if record["unit_id"] in selected:
                out.extend([f"---------- raw recheck {data.get('batch', path.stem)}: {record['unit_id']}", _dump(record)])
    for kind, paths in candidate_sources(cfg, workdir).items():
        if kind not in ("case", "counter_example", "term"):
            continue
        for path in paths:
            for block in re.findall(r"```yaml[ \t]*\n(.*?)```", path.read_text(encoding="utf-8"), re.S):
                data = yaml.safe_load(block)
                for item in data if isinstance(data, list) else [data]:
                    if isinstance(item, dict) and item.get("id") in support_ids:
                        found.add(item["id"])
                        out.extend([f"########## {path.name}: {item['id']}", _dump(item)])
    if want - found:
        raise ValueError(f"unknown unit, group or support: {sorted(want - found)}")
    return "\n".join(out)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    aggregation = commands.add_parser("aggregate")
    aggregation.add_argument("workdir", type=Path)
    recheck = commands.add_parser("recheck-input")
    recheck.add_argument("workdir", type=Path)
    recheck.add_argument("batch")
    recheck.add_argument("ids", nargs="+")
    apply = commands.add_parser("apply-recheck")
    apply.add_argument("workdir", type=Path)
    apply.add_argument("batches", nargs="*")
    apply.add_argument("--dry", action="store_true")
    display = commands.add_parser("show")
    display.add_argument("workdir", type=Path)
    display.add_argument("ids", nargs="+")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = open_workdir(args.workdir)
        if args.command == "aggregate":
            result = aggregate(cfg, args.workdir)
            print(result.counts)
            print("problems:", result.problems or "none")
            return 1 if result.problems else 0
        if args.command == "recheck-input":
            print(recheck_input(cfg, args.workdir, args.batch, args.ids).as_posix())
        elif args.command == "apply-recheck":
            changes = apply_recheck(cfg, args.workdir, args.batches or None, args.dry)
            print("\n".join(changes) if changes else "[]")
        else:
            print(show(cfg, args.workdir, args.ids))
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
