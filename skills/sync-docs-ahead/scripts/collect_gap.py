#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复核后报告的格式、计数与比例校验；仅在要求时写汇总，不改系统报告。"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re
import sys

STATUSES = ("✅ Implemented", "⚠️ Partial", "❌ Missing", "🔄 Divergent", "❓ Unverifiable")
SUMMARY_KEYS = ("Total features", *STATUSES, "Inspectable", "Coverage of inspected")
FEATURE_HEADER = ["#", "Design Requirement", "Status", "Code Reference", "Notes"]
SKIP = {"SUMMARY.md", "回填清单.md"}


def table_cells(line: str) -> list[str]:
    """仅未转义的竖线分列，反斜线奇偶决定是否转义。"""
    cells, current = [], []
    for char in line.strip():
        if char == "|":
            slashes = len(current) - len("".join(current).rstrip("\\"))
            if slashes % 2:
                current.pop()
                current.append(char)
            else:
                cells.append("".join(current).strip())
                current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    if cells and not cells[0]:
        cells.pop(0)
    if cells and not cells[-1] and line.strip().endswith("|"):
        cells.pop()
    return cells


def section(lines: list[str], heading: str) -> list[str]:
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        return []
    end = next((i for i in range(start + 1, len(lines))
                if re.match(r"^#{1,3}\s", lines[i].strip())), len(lines))
    return lines[start + 1:end]


def table_rows(lines: list[str]) -> list[list[str]]:
    rows = []
    for line in lines:
        if not line.strip().startswith("|"):
            continue
        cells = table_cells(line)
        if cells and not all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            rows.append(cells)
    return rows


def ratios(counts: Counter) -> tuple[float, float]:
    total = sum(counts.values())
    inspected = total - counts[STATUSES[4]]
    return (100 * inspected / total if total else 0,
            100 * (counts[STATUSES[0]] + .5 * counts[STATUSES[1]]) / inspected if inspected else 0)


@dataclass
class Report:
    name: str
    counts: Counter
    changed: int
    problems: list[str]


def inspect_report(path: Path) -> Report:
    problems: list[str] = []
    counts: Counter = Counter({status: 0 for status in STATUSES})
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        return Report(path.stem, counts, 0, [f"读取失败：{exc}"])
    for heading in (f"## {path.stem}", "### Features", "### Summary", "### Scan Scope", "### 复核记录"):
        occurrences = sum(line.strip() == heading for line in lines)
        if not occurrences:
            problems.append(f"缺标题 {heading}")
        elif occurrences != 1:
            problems.append(f"标题重复：{heading}")
    if not any(line.strip() for line in section(lines, "### Scan Scope")):
        problems.append("Scan Scope 扫描范围必须非空")

    rows = table_rows(section(lines, "### Features"))
    if not rows or rows[0] != FEATURE_HEADER:
        problems.append("Features 缺少五列表头或列名不符")
    features = rows[1:] if rows and rows[0] == FEATURE_HEADER else rows
    for number, cells in enumerate(features, 1):
        if len(cells) != 5:
            problems.append(f"Features 第 {number} 行应为五列，实际 {len(cells)}")
            continue
        if cells[2] not in STATUSES:
            problems.append(f"Status 不在五个允许值内：{cells[2]}")
        else:
            counts[cells[2]] += 1

    summary_lines = [line.strip() for line in section(lines, "### Summary") if line.strip()]
    if len(summary_lines) != 8:
        problems.append(f"Summary 块应恰好 8 行，实际 {len(summary_lines)}")
    summary = {}
    for line in summary_lines:
        match = re.fullmatch(r"-\s+([^:]+):\s*(.*)", line)
        if not match:
            problems.append(f"Summary 行格式错误：{line}")
            continue
        key, value = match.groups()
        if key in summary:
            problems.append(f"Summary 重复字段：{key}")
        summary[key] = value
    if set(summary) != set(SUMMARY_KEYS):
        problems.append("Summary 必须包含 Total、五状态和两个百分比，且无其他字段")
    expected_counts = {"Total features": len(features), **counts}
    for key, expected in expected_counts.items():
        value = summary.get(key, "")
        if not re.fullmatch(r"\d+", value):
            problems.append(f"Summary {key} 计数解析失败：{value!r}")
        elif int(value) != expected:
            problems.append(f"{key} 表格 {expected} 行 vs Summary {value}")
    for key, expected in zip(SUMMARY_KEYS[-2:], ratios(counts)):
        # 兼容保留公式并在末尾追加 = NN.N% 的报告，取最后一个百分比。
        matches = re.findall(r"(-?\d+(?:\.\d+)?)\s*%", summary.get(key, ""))
        value = float(matches[-1]) if matches else None
        if value is None or not 0 <= value <= 100 or abs(value - expected) > 1 + 1e-9:
            problems.append(f"{key} 百分比 {value} 应为 {expected:.1f}%（容差 ±1%）")

    changed = 0
    review = section(lines, "### 复核记录")
    found_review = False
    in_review = False
    for line in review:
        if not line.strip().startswith("|"):
            in_review = False
            continue
        cells = table_cells(line)
        if cells[:3] == ["#", "原判", "改判"] and len(cells) >= 4:
            found_review = in_review = True
        elif cells and all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            continue
        elif in_review and len(cells) >= 4:
            # 旧报告的依据里可能有未转义的管道命令；只比较前两格状态。
            # 空行之后的独立抽验表没有「改判」列，不参与统计。
            if cells[1] != cells[2]:
                changed += 1
    if not found_review:
        problems.append("复核记录缺少四列表头（# | 原判 | 改判 | 依据）")
    return Report(path.stem, counts, changed, problems)


def summary_text(reports: list[Report], missing: list[str]) -> str:
    lines = ["# 差距分析汇总", "",
             "| 系统 | Total | ✅ | ⚠️ | ❌ | 🔄 | ❓ | Inspectable | Coverage of inspected | 复核改判 | 校验 |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]

    def row(name, counts, changed, verdict):
        insp, cov = ratios(counts)
        name = name.replace("|", r"\|")
        values = [name, str(sum(counts.values())), *(str(counts[s]) for s in STATUSES),
                  f"{insp:.1f}%", f"{cov:.1f}%", str(changed), verdict]
        return "| " + " | ".join(values) + " |"

    total: Counter = Counter({status: 0 for status in STATUSES})
    for report in reports:
        lines.append(row(report.name, report.counts, report.changed, "不通过" if report.problems else "通过"))
        total.update(report.counts)
    for name in missing:
        lines.append("| " + name.replace("|", r"\|") + " | 未产出 | | | | | | | | | 不通过 |")
    passed = not missing and bool(reports) and not any(r.problems for r in reports)
    lines.append(row("合计", total, sum(r.changed for r in reports), "通过" if passed else "不通过"))
    lines += ["", "合计按 Features 表中合法状态重算；比例以合计计数计算，不平均系统百分比。",
              "复核改判按复核表中「原判 ≠ 改判」的行数计，旧报告的附注差异也会计入。"]
    if not passed:
        lines += ["", "校验未通过：以下数字仅供排错，不作为完成结论。"]
        for report in reports:
            lines.extend(f"- {report.name}：{problem}" for problem in report.problems)
        lines.extend(f"- {name}：未产出" for name in missing)
        if not reports:
            lines.append("- 没有可收集的系统报告")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="校验差距报告并收集汇总")
    parser.add_argument("output_dir", type=Path, help="系统报告目录")
    parser.add_argument("--write-summary", action="store_true", help="写入 SUMMARY.md")
    parser.add_argument("--out", type=Path, help="汇总输出目录，默认使用系统报告目录")
    parser.add_argument("--expect", help="预期系统名，以逗号分隔；省略时只检查现有报告")
    args = parser.parse_args(argv)
    if not args.output_dir.is_dir():
        print(f"不通过：报告目录不存在：{args.output_dir}")
        return 1
    reports, skipped = [], []
    for path in sorted(args.output_dir.glob("*.md")):
        if path.name in SKIP or path.name.startswith("_"):
            continue
        try:
            heads = {line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines()}
            # 带任一报告标题的都当报告去校验（残缺的报告要报错）；一个都没有的才是补充材料。
            is_report = bool(heads & {"### Features", "### Summary", f"## {path.stem}"})
        except (OSError, UnicodeError):
            is_report = True  # 读不了也当报告，让 inspect_report 报出读取失败
        if is_report:
            reports.append(inspect_report(path))
        else:
            skipped.append(path.name)
    for name in skipped:
        # 同目录里的补充材料（发布映射、备忘）没有 Features 表，不是系统报告；
        # 靠 --expect 兜底：本该是报告却没写出 Features 的系统会在缺失清单里出现。
        print(f"跳过（非报告，无 ### Features）：{name}")
    names = {report.name for report in reports}
    missing = [name for name in dict.fromkeys(x.strip() for x in (args.expect or "").split(","))
               if name and name not in names]
    for report in reports:
        counts = " ".join(f"{s.split()[0]}{report.counts[s]}" for s in STATUSES)
        print(f"{'不通过' if report.problems else '通过'} {report.name}：Total {sum(report.counts.values())} {counts}；复核改判 {report.changed}")
        for problem in report.problems:
            print(f"  - {problem}")
    for name in missing:
        print(f"不通过 {name}：未产出")
    if not reports:
        print("不通过：没有可收集的系统报告")
    rendered = summary_text(reports, missing)
    print(next(line for line in rendered.splitlines() if line.startswith("| 合计 |")))
    if args.write_summary:
        destination = (args.out or args.output_dir) / "SUMMARY.md"
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(f"不通过：汇总写入失败：{exc}")
            return 1
        print(f"已写入 {destination}")
    passed = bool(reports) and not missing and not any(r.problems for r in reports)
    print("总评：" + ("全部通过" if passed else "有不通过项"))
    return 0 if passed else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
