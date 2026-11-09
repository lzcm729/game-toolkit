"""匿名评分包和冻结协议的确定性部分；质量计数与链路归因分开。"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import fnmatch
import json
from pathlib import Path
import random
import re
import sys
from typing import Literal

import yaml

from bookconf import MaskNames, open_workdir, resolve
from chain import parse_run
from stage1 import read_tasks


@dataclass
class Row:
    qid: str
    item_id: str
    group: str
    required: bool
    verdict: str
    regression: str
    difference: str
    plugin_use: dict | None


@dataclass
class AggregateResult:
    per_question: list[Row]
    counts: dict[tuple[str, str], int]
    substantive: list[str]
    status: Literal["pass", "fail", "incomplete"]
    problems: list[str]


PAGE = r"\bpp?\.\s*\d+(?:\s*[–-]\s*\d+)?"
REFERENCE = r"`?[a-z0-9-]+\.md`?"


def mask(text: str, names: MaskNames) -> str:
    text = re.sub(PAGE, "p.?", text)
    text = re.sub(REFERENCE, "[参考文件]", text)
    for title in sorted(set(names.titles), key=lambda value: (-len(value), value)):
        text = text.replace(title, "[书]")
    for author in sorted(set(names.authors), key=lambda value: (-len(value), value)):
        text = re.sub(r"(?<!\w)" + re.escape(author) + r"(?!\w)", "[作者]", text)
    return text


def leaks(packet_md: str, names: MaskNames) -> int:
    patterns = [PAGE, REFERENCE]
    patterns += [re.escape(name) for name in names.authors + names.titles if name]
    return sum(len(re.findall(pattern, packet_md)) for pattern in patterns)


def pick_items(groups: dict, capabilities: dict, tasks: dict, used: set[str], cfg_answer: dict, seed: int,
               old_pool: str = "all") -> dict[str, dict]:
    if old_pool not in ("all", "migration"):
        raise ValueError("old_pool 必须是 all 或 migration")
    rng = random.Random(seed)
    group_rows = groups["tasks"] if isinstance(groups, dict) and "tasks" in groups else groups
    cap_rows = capabilities["capabilities"]
    caps = {cap["id"]: cap for cap in cap_rows}
    target = str(cfg_answer.get("target_source", "")).casefold()
    if old_pool == "migration" and not target:
        raise ValueError("历史 migration 抽样须写 answer_compare.target_source")
    quotas = cfg_answer["quotas"]
    old_group = next(group for group in quotas if group not in ("N", "O-other"))
    exclude = cfg_answer.get("exclude_items", [])

    def excluded(item):
        return item in used or any(fnmatch.fnmatchcase(item, pattern) for pattern in exclude)

    def sources(cid):
        source = caps[cid]["source"]
        return set(source if isinstance(source, list) else [source])

    def has_target(cid):
        return target in {source.casefold() for source in sources(cid)}

    def spread(candidates, count, key):
        if count == 0:
            return []
        rng.shuffle(candidates)
        picked = []
        seen = set()
        for candidate in candidates:
            value = key(candidate)
            if value not in seen:
                picked.append(candidate)
                seen.add(value)
            if len(picked) == count:
                return picked
        for candidate in candidates:
            if candidate not in picked:
                picked.append(candidate)
            if len(picked) == count:
                break
        if len(picked) != count:
            raise ValueError(f"quota {count} exceeds eligible pool {len(picked)}")
        return picked

    # YAML 中的清单顺序是冻结输入的一部分；shuffle 只使用局部随机数生成器。
    eligible_old = [row for row in group_rows if row["group"] in ("O", "O-partial") and not excluded(row["task_id"])
                    and (old_pool == "all" or any(has_target(cid) for cid in row.get("capabilities") or [] if cid in caps))]
    new_pool = [row for row in group_rows if row["group"] == "N" and not excluded(row["task_id"])]
    old = spread(eligible_old, sum(quotas[old_group]), lambda row: row["task_id"][:3])
    new = spread(new_pool, sum(quotas["N"]), lambda row: row["task_id"][:3])
    books = cfg_answer.get("other_books", {})
    used_caps = {item[2:] for item in used if item.startswith("p-")}
    sensitive_ids = list(dict.fromkeys(cid for entry in capabilities.get("entry_sensitive", []) for cid in entry["ids"]))
    other_ids = [cid for cid in sensitive_ids if cid in caps and sources(cid).intersection(books)
                 and not has_target(cid) and cid not in used_caps and not excluded("p-" + cid)]
    fallback = {book: minimum for book, minimum in books.items() if not any(book in sources(cid) for cid in other_ids)}
    count_sensitive = sum(quotas["O-other"]) - sum(fallback.values())
    if count_sensitive < 0:
        raise ValueError("other_books minimum exceeds O-other quota")
    protected = spread([{"cid": cid, "book": sorted(sources(cid))[0]} for cid in other_ids],
                       count_sensitive, lambda row: row["book"])
    for book, minimum in fallback.items():
        pool = [cap["id"] for cap in cap_rows if sources(cap["id"]) == {book} and cap.get("depth") == "method"
                and cap["id"] not in used_caps and not excluded("p-" + cap["id"])]
        for _ in range(minimum):
            if not pool:
                raise ValueError(f"no unused method capability for {book}")
            cid = rng.choice(pool)
            pool.remove(cid)
            protected.append({"cid": cid, "book": book})
    if any(sum(book in sources(row["cid"]) for row in protected) < minimum for book, minimum in books.items()):
        raise ValueError("protected selection does not meet other_books minimum")
    items = {}
    for group, rows in ((old_group, old), ("N", new)):
        for index, row in enumerate(rows):
            item = row["task_id"]
            if item not in tasks:
                raise ValueError(f"task description missing: {item}")
            items[item] = {"task": tasks[item].strip(), "group": group, "required": index < quotas[group][0], "source": row["group"]}
        if group == old_group:
            for index, row in enumerate(protected):
                items["p-" + row["cid"]] = {"task": caps[row["cid"]]["supports"], "group": "O-other",
                                           "required": index < quotas["O-other"][0], "source": row["book"]}
    return items


def _json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")


def make_prompts(items: dict, prompts_raw: dict, out_dir: Path, prefix: str = "a") -> tuple[Path, Path, Path]:
    if not re.fullmatch(r"[A-Za-z]+", prefix):
        raise ValueError("qid prefix 必须是字母")
    lines = []
    id_map = {}
    meta = {}
    for index, (item, info) in enumerate(items.items(), 1):
        prompt = prompts_raw[item]
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"empty prompt: {item}")
        qid = f"{prefix}{index:03d}"
        id_map[qid] = item
        meta[item] = {key: info[key] for key in ("group", "required", "source")}
        lines.append(f"{qid}\t{info['group']}\t" + " ".join(prompt.split()))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    prompts = out_dir / "prompts.tsv"
    mapping = out_dir / "id_map.json"
    metadata = out_dir / "items_meta.json"
    prompts.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    _json(mapping, id_map)
    _json(metadata, meta)
    return prompts, mapping, metadata


def build_packets(id_map: dict, rubric: dict, prompts_raw: dict, arms: dict[str, Path], reps: int,
                  n_graders: int, seed: int, names: MaskNames, forced: dict[str, Path] | None = None) -> tuple[list[str], dict]:
    if set(arms) != {"baseline", "candidate"} or (forced is not None and set(forced) != set(arms)):
        raise ValueError("arms/forced 必须恰有 baseline 和 candidate")
    if reps < 1 or n_graders < 1:
        raise ValueError("reps 和 n_graders 必须大于 0")
    rng = random.Random(seed)
    qids = sorted(id_map)
    rng.shuffle(qids)
    packets = [[] for _ in range(n_graders)]
    key = {}
    all_labels = list("甲乙丙丁戊己庚辛壬癸")
    all_labels += [f"编号{number}" for number in range(11, 2 * reps + 3)]
    for index, qid in enumerate(qids):
        item = id_map[qid]
        slots = [(arm, rep, False) for arm in ("baseline", "candidate") for rep in range(1, reps + 1)]
        if forced is not None:
            slots.extend((arm, 1, True) for arm in ("baseline", "candidate"))
        rng.shuffle(slots)
        labels = all_labels[:len(slots)]
        label_order = {label: number for number, label in enumerate(labels)}
        block = [f"## 题 {qid}", "", f"**问题**：{prompts_raw[item]}", "", "**评分项**", "", "```yaml",
                 yaml.safe_dump(rubric[item], allow_unicode=True, sort_keys=False, width=200).rstrip(), "```", ""]
        label_of = {}
        for label, (arm, rep, is_forced) in zip(labels, slots):
            key[f"{qid}|{label}"] = {"arm": arm, "rep": rep, "forced": is_forced}
            label_of[(arm, rep, is_forced)] = label
            directory = forced[arm] if is_forced else arms[arm]
            path = Path(directory) / f"{qid}-r{rep}.jsonl"
            run = parse_run(path)
            if not run.ok:
                raise ValueError(f"failed run cannot enter grading: {path}")
            block.extend([f"### 回答{label}", "", mask(run.answer, names).strip(), ""])
        groups = {arm: "、".join(sorted((label_of[(arm, rep, False)] for rep in range(1, reps + 1)), key=label_order.get))
                  for arm in ("baseline", "candidate")}
        x, y = rng.sample(["baseline", "candidate"], 2)
        key[f"{qid}|cmp1"] = {"X": x, "Y": y}
        if forced is not None:
            fx, fy = rng.sample(["baseline", "candidate"], 2)
            key[f"{qid}|cmp2"] = {"X": fx, "Y": fy}
        block.extend(["**要做的比较**", ""])
        if forced is None:
            block.extend([f"- X 组 = 回答{groups[x]}，Y 组 = 回答{groups[y]}", ""])
        else:
            block.extend([f"- 比较 1：X 组 = 回答{groups[x]}，Y 组 = 回答{groups[y]}",
                          f"- 比较 2：X = 回答{label_of[(fx, 1, True)]}，Y = 回答{label_of[(fy, 1, True)]}", ""])
        packets[index % n_graders].append(mask("\n".join(block), names))
    return ["\n\n---\n\n".join(blocks) + "\n" for blocks in packets], key


def legacy_key(key: dict, baseline: str, candidate: str, with_forced: bool = False) -> dict:
    """只用于历史字节复现；新协议的 key 保留 arm/rep/forced 字段。"""
    names = {"baseline": baseline, "candidate": candidate}
    result = {}
    for identity, row in key.items():
        if "X" in row:
            result[identity] = {side: names[row[side]] for side in ("X", "Y")}
        elif with_forced:
            result[identity] = {"variant": names[row["arm"]], "arm": "forced" if row["forced"] else "natural", "rep": row["rep"]}
        else:
            if row["forced"]:
                raise ValueError("forced answers need the historical forced schema")
            result[identity] = {"variant": names[row["arm"]], "rep": row["rep"]}
    return result


def _arm(name):
    aliases = {"baseline": "baseline", "candidate": "candidate", "accepted": "baseline", "release": "candidate", "proto": "candidate"}
    if name not in aliases:
        raise ValueError(f"unknown key arm: {name}")
    return aliases[name]


def aggregate(grades: list[dict], key: dict, id_map: dict, meta: dict, protocol: Literal["B", "pooled-required"],
              chain_by_q: dict[str, dict[str, list[bool]]] | None = None,
              requirements: dict | None = None) -> AggregateResult:
    if protocol not in ("B", "pooled-required"):
        raise ValueError(f"unknown protocol: {protocol}")
    problems = []
    per_q = {}
    for grade in grades:
        qid = grade.get("q")
        if qid not in id_map:
            problems.append(f"unknown grade qid: {qid}")
        per_q.setdefault(qid, []).append(grade)
    if len(set(id_map.values())) != len(id_map):
        problems.append("duplicate item_id in id_map")
    rows = []
    counts = Counter()
    substantive = []
    for qid, item in sorted(id_map.items()):
        info = meta.get(item)
        if not isinstance(info, dict) or not isinstance(info.get("required"), bool):
            problems.append(f"{qid}: missing or invalid items_meta")
            info = {"group": "?", "required": True}
        group = info.get("group", "?")
        cohort = "O" if group.startswith("O") else "N" if group == "N" else "?"
        if cohort == "?":
            problems.append(f"{qid}: invalid group {group}")
        candidates = per_q.get(qid, [])
        verdict = "undecided"
        regression = "none"
        difference = ""
        if len(candidates) != 1:
            problems.append(f"{qid}: {'missing' if not candidates else 'duplicate'} grade")
        else:
            comparison = candidates[0].get("cmp1") or {}
            for field in ("difference", "regression"):
                if not isinstance(comparison.get(field), str) or not comparison[field].strip():
                    problems.append(f"{qid}: missing or invalid {field}")
            regression = str(comparison.get("regression") or "none")
            difference = str(comparison.get("difference") or "")
            try:
                sides = key[qid + "|cmp1"]
                if {_arm(sides[side]) for side in ("X", "Y")} != {"baseline", "candidate"}:
                    raise ValueError("comparison sides are not two distinct arms")
                value = comparison.get("verdict")
                if value == "same":
                    verdict = "same"
                elif value in ("unclear", "undecided"):
                    verdict = "undecided"
                elif value in ("X_better", "Y_better"):
                    verdict = "better" if _arm(sides[value[0]]) == "candidate" else "worse"
                else:
                    raise ValueError(f"invalid verdict {value}")
            except (KeyError, ValueError) as exc:
                problems.append(f"{qid}: {exc}")
        if verdict == "undecided":
            problems.append(f"{qid}: undecided")
        row = Row(qid, item, group, info["required"], verdict, regression, difference,
                  chain_by_q.get(qid) if chain_by_q else None)
        rows.append(row)
        if row.required:
            counts[(cohort, verdict)] += 1
            if verdict == "worse" and regression.casefold().strip() not in ("none", "", "null"):
                substantive.append(qid)
    if not id_map:
        problems.append("empty id_map")
    if protocol == "B":
        frozen = requirements or {}
        actual = {group: {row.item_id for row in rows if row.required and
                          ("O" if row.group.startswith("O") else row.group) == group} for group in ("O", "N")}
        quotas = frozen.get("quotas", {})
        required_items = frozen.get("required_items")
        if required_items is None and not quotas:
            problems.append("B requires frozen required_items or quotas in answer_compare")
        for group in ("O", "N"):
            if isinstance(required_items, dict):
                expected = required_items.get(group)
                if not isinstance(expected, list) or len(expected) != len(set(expected)) or set(expected) != actual[group]:
                    problems.append(f"{group}: frozen required_items mismatch")
            elif quotas:
                expected_count = sum(value[0] for key, value in quotas.items()
                                     if ("O" if key.startswith("O") else key) == group)
                if expected_count != len(actual[group]):
                    problems.append(f"{group}: frozen required quota {expected_count} != {len(actual[group])}")
            if not actual[group]:
                reason = frozen.get("empty_groups", {}).get(group)
                if not isinstance(reason, str) or not reason.strip():
                    problems.append(f"{group}: zero required questions without explicit empty-group reason")
    if problems:
        status = "incomplete"
    elif protocol == "B":
        failed = any(counts[(group, "worse")] > counts[(group, "better")] for group in ("O", "N"))
        status = "fail" if failed or substantive else "pass"
    else:
        status = "fail" if sum(count for (group, verdict), count in counts.items() if verdict == "worse") > sum(count for (group, verdict), count in counts.items() if verdict == "better") else "pass"
    return AggregateResult(rows, dict(counts), substantive, status, problems)


def _load(path: Path):
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pick = commands.add_parser("pick")
    pick.add_argument("workdir", type=Path)
    pick.add_argument("--groups", type=Path, required=True)
    pick.add_argument("--capabilities", type=Path, required=True)
    pick.add_argument("--used", type=Path, action="append", default=[])
    pick.add_argument("--seed", type=int, required=True)
    pick.add_argument("--out-dir", type=Path, required=True)
    pick.add_argument("--old-pool", choices=["all", "migration"], default="all",
                      help="migration 仅用于历史迁移抽样复现")
    prompts = commands.add_parser("prompts")
    prompts.add_argument("workdir", type=Path)
    prompts.add_argument("--items", type=Path, required=True)
    prompts.add_argument("--prompts-raw", type=Path, required=True)
    prompts.add_argument("--out-dir", type=Path, required=True)
    prompts.add_argument("--prefix", default="a")
    packets = commands.add_parser("packets")
    packets.add_argument("workdir", type=Path)
    for name in ("id-map", "rubric", "prompts-raw", "baseline", "candidate", "out-dir"):
        packets.add_argument("--" + name, type=Path, required=True)
    packets.add_argument("--reps", type=int, required=True)
    packets.add_argument("--n-graders", type=int, required=True)
    packets.add_argument("--seed", type=int, required=True)
    packets.add_argument("--forced-baseline", type=Path)
    packets.add_argument("--forced-candidate", type=Path)
    packets.add_argument("--legacy-baseline")
    packets.add_argument("--legacy-candidate")
    aggregation = commands.add_parser("aggregate")
    aggregation.add_argument("workdir", type=Path)
    for name in ("id-map", "items-meta", "key"):
        aggregation.add_argument("--" + name, type=Path, required=True)
    aggregation.add_argument("--grades", type=Path, nargs="+", required=True)
    aggregation.add_argument("--protocol", choices=["B", "pooled-required"], required=True)
    aggregation.add_argument("--chain", type=Path)
    aggregation.add_argument("--out", type=Path)
    leakage = commands.add_parser("leaks")
    leakage.add_argument("workdir", type=Path)
    leakage.add_argument("files", nargs="+", type=Path)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = open_workdir(args.workdir)
        if args.command == "pick":
            used = set()
            for path in args.used:
                data = _load(path)
                used.update(data.values() if isinstance(data, dict) else data)
            tasks = read_tasks(resolve(cfg, args.workdir, "overview").read_text(encoding="utf-8"))
            items = pick_items(_load(args.groups), _load(args.capabilities), tasks, used, cfg.answer_compare, args.seed, args.old_pool)
            args.out_dir.mkdir(parents=True, exist_ok=True)
            _json(args.out_dir / "items.json", items)
            # 出题者只收到任务文字；分组和必测标记在后续 make_prompts 固定。
            writer = [{"id": item, "task": row["task"]} for item, row in items.items()]
            (args.out_dir / "items-for-writer.yaml").write_text(yaml.safe_dump(writer, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8", newline="\n")
            print(f"picked: {len(items)}")
        elif args.command == "prompts":
            for path in make_prompts(_load(args.items), _load(args.prompts_raw), args.out_dir, args.prefix):
                print(path.as_posix())
        elif args.command == "packets":
            forced = None
            if args.forced_baseline or args.forced_candidate:
                if not args.forced_baseline or not args.forced_candidate:
                    raise ValueError("forced 的两个版本都必须提供")
                forced = {"baseline": args.forced_baseline, "candidate": args.forced_candidate}
            packets, key = build_packets(_load(args.id_map), _load(args.rubric), _load(args.prompts_raw),
                                         {"baseline": args.baseline, "candidate": args.candidate}, args.reps,
                                         args.n_graders, args.seed, cfg.mask_names, forced)
            leaked = sum(leaks(packet, cfg.mask_names) for packet in packets)
            if leaked:
                raise ValueError(f"评分包仍有 {leaked} 处身份标记")
            destination = args.out_dir / "packets"
            destination.mkdir(parents=True, exist_ok=True)
            for number, packet in enumerate(packets, 1):
                (destination / f"packet-{number}.md").write_text(packet, encoding="utf-8", newline="\n")
            if args.legacy_baseline or args.legacy_candidate:
                if not args.legacy_baseline or not args.legacy_candidate:
                    raise ValueError("历史序列化须提供两个旧版本名")
                _json(args.out_dir / "key-current.json", key)
                key = legacy_key(key, args.legacy_baseline, args.legacy_candidate, forced is not None)
            _json(args.out_dir / "key.json", key)
            print(f"questions: {len(_load(args.id_map))}; graders: {len(packets)}; leaks: 0")
        elif args.command == "aggregate":
            grades = []
            for path in args.grades:
                paths = sorted(path.glob("grades-*.yaml")) if path.is_dir() else [path]
                for file in paths:
                    grades.extend(_load(file))
            result = aggregate(grades, _load(args.key), _load(args.id_map), _load(args.items_meta), args.protocol,
                               _load(args.chain) if args.chain else None, requirements=cfg.answer_compare)
            data = {"per_question": [asdict(row) for row in result.per_question], "counts": {},
                    "substantive": result.substantive, "status": result.status, "problems": result.problems}
            for (group, verdict), count in sorted(result.counts.items()):
                data["counts"].setdefault(group, {})[verdict] = count
            if args.out:
                args.out.parent.mkdir(parents=True, exist_ok=True)
                _json(args.out, data)
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return 0 if result.status == "pass" else 1
        else:
            total = 0
            for path in args.files:
                count = leaks(path.read_text(encoding="utf-8"), cfg.mask_names)
                total += count
                print(f"{path.as_posix()}: {count}")
            return 1 if total else 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration, yaml.YAMLError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
