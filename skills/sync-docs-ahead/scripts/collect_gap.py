#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复核后报告校验、稳定要求键、基线迁移与增量计划；默认只读。"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import subprocess
import sys
import unicodedata

import yaml

STATUSES = ("✅ Implemented", "⚠️ Partial", "❌ Missing", "🔄 Divergent", "❓ Unverifiable")
SUMMARY_KEYS = ("Total features", *STATUSES, "Inspectable", "Coverage of inspected")
FEATURE_HEADER = ["#", "Design Requirement", "Status", "Code Reference", "Notes"]
SKIP = {"SUMMARY.md", "TRANSITIONS.md", "回填清单.md"}


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
    valid_header = bool(rows) and rows[0] in (FEATURE_HEADER, FEATURE_HEADER + ["Key"])
    if not valid_header:
        problems.append("Features 缺少五列或六列表头或列名不符")
    features = rows[1:] if valid_header else rows
    width = len(rows[0]) if valid_header else 5
    for number, cells in enumerate(features, 1):
        if len(cells) != width:
            problems.append(f"Features 第 {number} 行应为 {width} 列，实际 {len(cells)}")
            continue
        if width == 6 and not re.fullmatch(r"[^#]+#[^#]+#[0-9a-f]{8}", cells[5]):
            problems.append(f"Features 第 {number} 行 Key 格式错误")
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


def split_requirement(requirement: str) -> tuple[str, str]:
    """从末尾配对括号取出处，容忍出处内还有括号、文件名带括号。"""
    text = requirement.rstrip()
    if not text or text[-1] not in ")）":
        return text, ""
    depth = 0
    for i in range(len(text) - 1, -1, -1):
        if text[i] in ")）":
            depth += 1
        elif text[i] in "(（":
            depth -= 1
            if depth == 0:
                return text[:i].rstrip(), text[i + 1:-1]
    return text, ""


def normalized(text: str) -> str:
    return "".join(c for c in text if not c.isspace()
                   and unicodedata.category(c)[0] not in "NPSZ")


def source_ref(requirement: str) -> tuple[str, int, bool]:
    _, citation = split_requirement(requirement)
    first = re.split("[；;]", citation, maxsplit=1)[0]
    match = re.search(r"(.+?\.(md|csv))\s*(?:[:：]\s*(\d+)|第\s*(\d+)\s*行)", first, re.I)
    if not match:
        return "unknown", 0, False
    file, ext, md_line, csv_line = match.groups()
    return file.strip(" `\"“”「」"), int(md_line or csv_line), ext.lower() == "csv"


def posix(path: str) -> str:
    return path.replace("\\", "/")


class Documents:
    """一次运行共用文件索引和标题缓存；同名文件按完整路径排序确定性选择。"""

    def __init__(self, root: Path | None = None, manifest_path: Path | None = None):
        self.root = root
        manifest_path = manifest_path or (root / "_manifest.json" if root else None)
        self.manifest = read_json(manifest_path) if manifest_path and manifest_path.exists() else {}
        # 内嵌表（docx 里的 <sheet>）也有 file 与 revision，漏了它们会让整个系统因「缺少版本」永远重跑。
        self.entries = sorted((entry for kind in ("docs", "sheets", "embedded_sheets")
                               for entry in self.manifest.get(kind, []) if entry.get("file")),
                              key=lambda entry: posix(entry["file"]))
        self.files = sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.as_posix()) if root and root.is_dir() else []
        self.headings: dict[Path, list[tuple[int, str]]] = {}

    def entry(self, file: str) -> dict | None:
        file = posix(file)
        exact = next((e for e in self.entries if posix(e["file"]) == file), None)
        return exact or next((e for e in self.entries if PurePosixPath(posix(e["file"])).name == PurePosixPath(file).name), None)

    def anchor(self, file: str, line: int) -> str:
        if not self.root or line < 1:
            return "L0"
        entry = self.entry(file)
        path = self.root / posix(entry["file"] if entry else file)
        if not path.is_file():
            path = next((p for p in self.files if p.name == PurePosixPath(posix(file)).name), path)
        if path not in self.headings:
            headings = []
            try:
                fence = None
                for number, text in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
                    fenced = re.match(r"^\s{0,3}(`{3,}|~{3,})", text)
                    if fenced:
                        mark = fenced[1]
                        if fence is None:
                            fence = mark
                        elif mark[0] == fence[0] and len(mark) >= len(fence):
                            fence = None
                        continue
                    match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", text)
                    if match and fence is None:
                        title = match[1]
                        numbered = re.match(r"^(\d+(?:\.\d+)*)", title)
                        anchor = numbered[1] if numbered else normalized(title[:12]) or "L0"
                        headings.append((number, anchor))
            except (OSError, UnicodeError):
                pass
            self.headings[path] = headings
        return next((anchor for number, anchor in reversed(self.headings[path]) if number <= line), "L0")


def mint_key(requirement: str, docs: Documents | None = None) -> str:
    docs = docs or Documents()
    text, _ = split_requirement(requirement)
    file, line, csv = source_ref(requirement)
    entry = docs.entry(file)
    doc = entry.get("node_token") if entry else None
    doc = doc or PurePosixPath(posix(file)).stem
    anchor = f"r{line}" if csv else docs.anchor(file, line)
    digest = hashlib.sha1(normalized(text).encode("utf-8")).hexdigest()[:8]
    return f"{doc}#{anchor}#{digest}"


def read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON 顶层应为对象：{path}")
    return data


def report_paths(directory: Path) -> tuple[list[Path], list[str]]:
    paths, skipped = [], []
    for path in sorted(directory.glob("*.md")):
        if path.name in SKIP or path.name.startswith("_"):
            continue
        try:
            heads = {line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines()}
            is_report = bool(heads & {"### Features", "### Summary", f"## {path.stem}"})
        except (OSError, UnicodeError):
            is_report = True
        if is_report:
            paths.append(path)
        else:
            skipped.append(path.name)
    return paths, skipped


def report_data(path: Path, docs: Documents, use_stamped: bool = False) -> dict:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    rows = []
    for cells in table_rows(section(lines, "### Features"))[1:]:
        if len(cells) not in (5, 6):
            continue
        rows.append({"#": cells[0], "key": cells[5] if use_stamped and len(cells) == 6 else mint_key(cells[1], docs),
                     "status": cells[2], "requirement": cells[1][:80],
                     "match_text": normalized(split_requirement(cells[1])[0])})
    mechanics = table_rows(section(lines, "### Code-only mechanics"))
    mechanism_column = mechanics[0].index("机制") if mechanics and "机制" in mechanics[0] else 0
    carried = next((re.fullmatch(r"> 沿用基线 (.+)，本轮未重跑：文档与代码均未变", line) for line in lines
                    if line.startswith("> 沿用基线 ")), None)
    return {"rows": rows, "code_only": [row[mechanism_column] for row in mechanics[1:] if len(row) > mechanism_column],
            "code_only_present": "### Code-only mechanics" in lines,
            "carried_from": carried[1] if carried else None}


def load_baseline(directory: Path, docs: Documents) -> dict:
    if not directory.is_dir():
        raise ValueError(f"基线目录不存在：{directory}")
    run_path = directory / "RUN.json"
    if run_path.exists():
        run = read_json(run_path)
        if run.get("schema_version") != 1 or not isinstance(run.get("systems"), dict):
            raise ValueError(f"不支持的 RUN.json schema：{run_path}")
        for name, data in run["systems"].items():
            if not valid_system(name) or not isinstance(data, dict) or not isinstance(data.get("rows"), list):
                raise ValueError(f"RUN.json 系统记录格式错误：{name}")
            for row in data["rows"]:
                if (not isinstance(row, dict) or any(not isinstance(row.get(k), str) for k in ("key", "status", "requirement"))
                        or "#" not in row or row["status"] not in STATUSES
                        or not re.fullmatch(r"[^#]+#[^#]+#[0-9a-f]{8}", row["key"])):
                    raise ValueError(f"RUN.json 行记录格式错误：{name}")
            path = directory / (name + ".md")
            if "code_only_present" not in data and path.is_file():
                extra = report_data(path, docs)
                data.update({k: extra[k] for k in ("code_only", "code_only_present")})
        return run
    systems = {}
    for path in report_paths(directory)[0]:
        report = inspect_report(path)
        if report.problems:
            raise ValueError(f"基线 {path.stem} 校验不通过：{'；'.join(report.problems)}")
        systems[path.stem] = report_data(path, docs, use_stamped=True)
    return {"systems": systems}


def match_rows(current: list[dict], baseline: list[dict], threshold: float = .6) -> list[tuple[dict | None, dict | None, int]]:
    """先耗尽一级，再全局按相似度贪心二级；下标打破平分，重复键也一对一。"""
    used_current, used_baseline, matches = set(), set(), []
    for ci, row in enumerate(current):
        bi = next((i for i, old in enumerate(baseline) if i not in used_baseline and old["key"] == row["key"]), None)
        if bi is not None:
            used_current.add(ci)
            used_baseline.add(bi)
            matches.append((row, baseline[bi], 1))
    candidates = []
    for ci, row in enumerate(current):
        if ci in used_current:
            continue
        for bi, old in enumerate(baseline):
            if bi in used_baseline or row["key"].rsplit("#", 1)[0] != old["key"].rsplit("#", 1)[0]:
                continue
            ratio = SequenceMatcher(None, old.get("match_text", normalized(split_requirement(old["requirement"])[0])),
                                    row.get("match_text", normalized(split_requirement(row["requirement"])[0]))).ratio()
            if ratio >= threshold:
                candidates.append((-ratio, ci, bi))
    for _, ci, bi in sorted(candidates):
        if ci not in used_current and bi not in used_baseline:
            used_current.add(ci)
            used_baseline.add(bi)
            matches.append((current[ci], baseline[bi], 2))
    matches.extend((row, None, 3) for i, row in enumerate(current) if i not in used_current)
    matches.extend((None, old, 3) for i, old in enumerate(baseline) if i not in used_baseline)
    return matches


def md_cell(value: str) -> str:
    return str(value).replace("|", r"\|").replace("\n", " ")


TRANSITION_COUNTS = ("未变", "退步", "修复", "其他变化", "改写", "新增", "消失")


def transitions_text(current: dict, baseline: dict, baseline_dir: Path, threshold: float = .6) -> tuple[str, list[str]]:
    lines = ["# 基线迁移", "", f"基线：{baseline_dir}", "",
             "改写是二级匹配的独立计数，可同时计入退步／修复／其他变化；同状态改写不计未变。", ""]
    notices, carried, totals = [], [], Counter()
    for name in sorted(current.keys() | baseline.keys()):
        now, old = current.get(name, {}), baseline.get(name, {})
        counts, changed = Counter(), []
        for row, previous, level in match_rows(now.get("rows", []), old.get("rows", []), threshold):
            totals[f"level{level}"] += 1
            if previous is None:
                counts["新增"] += 1
            elif row is None:
                counts["消失"] += 1
            else:
                if level == 2:
                    counts["改写"] += 1
                before, after = previous["status"], row["status"]
                if before != after:
                    category = ("退步" if before == STATUSES[0] else "修复"
                                if before in STATUSES[1:4] and after == STATUSES[0] else "其他变化")
                    counts[category] += 1
                elif level == 1:
                    counts["未变"] += 1
                    continue
            display = row or previous
            changed.append("| " + " | ".join(map(md_cell, [display["key"], display["requirement"],
                           f"{previous['status'] if previous else '—'} → {row['status'] if row else '—'}", "①②③"[level - 1]])) + " |")
        totals.update(counts)
        subtotal = "／".join(f"{key} {counts[key]}" for key in TRANSITION_COUNTS)
        notices.append(f"{name}：{subtotal}")
        lines += [f"## {name}", "", subtotal, "", "| 键 | 要求 | 基线状态 → 本轮状态 | 匹配级 |", "|---|---|---|---|", *changed, "",
                  "### Code-only mechanics", ""]
        if not old.get("code_only_present", False):
            lines.append("基线报告没有该节，无法确认机制新增／消失。")
        elif name in current and not now.get("code_only_present", False):
            lines.append("本轮报告没有该节，无法确认机制新增／消失。")
        else:
            added = sorted(set(now.get("code_only", [])) - set(old.get("code_only", [])))
            removed = sorted(set(old.get("code_only", [])) - set(now.get("code_only", [])))
            lines += ["| 变化 | 机制 |", "|---|---|", *(f"| 新增 | {md_cell(x)} |" for x in added),
                      *(f"| 消失 | {md_cell(x)} |" for x in removed)]
            if not added and not removed:
                lines.append("未变。")
        lines.append("")
        if now.get("carried_from"):
            carried.append(f"- {name}：{now['carried_from']}")
    total_rows = sum(len(s.get("rows", [])) for s in baseline.values())
    stability = f"{100 * totals['level1'] / total_rows:.1f}%" if total_rows else "不适用（基线总行数为 0）"
    total = ("合计：" + "／".join(f"{key} {totals[key]}" for key in TRANSITION_COUNTS)
             + f"；稳定率 {stability}（一级 {totals['level1']} ÷ 基线 {total_rows}）；二级 {totals['level2']}，新增 {totals['新增']}，消失 {totals['消失']}")
    lines += ["## 沿用基线的系统", "", *(carried or ["无。"]), "", total]
    return "\n".join(lines) + "\n", notices + [total]


def git_output(root: Path | None, *args: str) -> str | None:
    if root is None or not root.is_dir():
        return None
    try:
        # 仅本次只读调用信任显式工程根，不改用户的全局 Git 配置。
        result = subprocess.run(["git", "-c", f"safe.directory={root.resolve().as_posix()}", "-C", str(root), *args],
                                capture_output=True, encoding="utf-8", errors="replace", timeout=30)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def valid_system(name: str) -> bool:
    return (isinstance(name, str) and bool(name.strip()) and name not in (".", "..")
            and not re.search(r'[<>:"/\\|?*\x00-\x1f]', name) and not name.endswith((".", " "))
            and not PureWindowsPath(name + ".md").is_reserved()
            and name + ".md" not in SKIP and not name.startswith("_"))


def load_config(path: Path | None) -> dict:
    if path is None:
        return {}
    config = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict) or config.get("$schema_version") != 1 or not isinstance(config.get("systems"), list):
        raise ValueError("配置必须含 $schema_version: 1 与 systems 列表")
    names = set()
    for system in config["systems"]:
        if not isinstance(system, dict) or not valid_system(system.get("name", "")) or system["name"] in names:
            raise ValueError("systems.name 须为不重复的合法报告文件名")
        names.add(system["name"])
        if not isinstance(system.get("scope"), str) or not system["scope"].strip():
            raise ValueError(f"{system['name']} 缺少 scope")
        for key in ("docs", "refs", "code"):
            values = system.get(key, [])
            if not isinstance(values, list) or any(not isinstance(v, str) or not v.strip() for v in values):
                raise ValueError(f"{system['name']}.{key} 须为路径字符串列表")
            if any(PureWindowsPath(v).is_absolute() or PurePosixPath(posix(v)).is_absolute()
                   or PureWindowsPath(v).drive or ".." in PurePosixPath(posix(v)).parts for v in values):
                raise ValueError(f"{system['name']}.{key} 路径须相对配置约定的根目录，不能越界")
    for key in ("docs_root", "manifest"):
        if key in config and (not isinstance(config[key], str) or not config[key].strip()
                              or PureWindowsPath(config[key]).drive or PurePosixPath(posix(config[key])).is_absolute()):
            raise ValueError(f"{key} 须为相对工程根的路径")
    return config


def document_revisions(system: dict, docs: Documents) -> tuple[list[dict], list[str]]:
    files, problems = set(), []
    for pattern in system.get("docs", []):
        matches = sorted(p for p in docs.root.glob(posix(pattern)) if p.is_file()) if docs.root and docs.root.is_dir() else []
        if not matches:
            problems.append(f"设计文件未匹配或 docs_root 未提供：{pattern}")
        files.update(p.relative_to(docs.root).as_posix() for p in matches)
    revisions = []
    for file in sorted(files):
        # 版本快照必须按完整相对路径，不能把同名 CSV 的版本混起来。
        entry = next((e for e in docs.entries if posix(e["file"]) == file), None)
        fields = {key: entry[key] for key in ("revision_id", "revision") if entry and entry.get(key) is not None}
        if fields:
            revisions.append({"file": file, **fields})
        else:
            problems.append(f"manifest 缺少版本：{file}")
    return revisions, problems


def make_plan(config: dict, baseline: dict | None, baseline_dir: Path | None, root: Path | None,
              docs: Documents, force: list[str], names: list[str]) -> dict:
    systems = {s["name"]: s for s in config.get("systems", [])}
    names = list(dict.fromkeys([*systems, *names]))
    if not systems:
        names = list(dict.fromkeys([*names, *(baseline or {}).get("systems", {})]))
    common = []
    if not config:
        common.append("无配置，不能确认文档与代码范围")
    if baseline_dir is None:
        common.append("无基线")
    elif not (baseline_dir / "RUN.json").is_file():
        common.append("基线没有 RUN.json")
    if git_output(root, "rev-parse", "--is-inside-work-tree") != "true":
        common.append("工程根不是 git 仓库或 git 不可用")
    elif not git_output(root, "rev-parse", "HEAD"):
        common.append("工程根没有可读取的 HEAD")
    result = {"rerun": [], "carry": [], "reasons": {}}
    for name in names:
        reasons = common.copy()
        system, previous = systems.get(name, {}), (baseline or {}).get("systems", {}).get(name)
        if name in force:
            reasons.append("--force 指定重跑")
        if previous is None:
            reasons.append("基线没有该系统")
        if not reasons:
            revisions, problems = document_revisions(system, docs)
            reasons.extend(problems)
            if not system.get("docs"):
                reasons.append("未配置评分文档")
            if revisions != sorted(previous.get("docs", []), key=lambda e: e["file"]):
                reasons.append("设计文件集合或 revision 与基线不同")
            if system.get("code", []) != previous.get("code", []):
                reasons.append("代码范围与基线不同")
            if ("scope" in previous and previous["scope"] != system.get("scope")
                    or "refs" in previous and previous["refs"] != system.get("refs", [])):
                reasons.append("评分范围或参考清单与基线不同")
            head = (baseline or {}).get("project_head")
            if not head:
                reasons.append("基线没有 project_head")
            else:
                paths = [posix(p) for p in system.get("code", [])]
                # 空 code 明确表示无源码路径；不把空 pathspec 误当全仓库。
                diff = git_output(root, "diff", "--name-only", head, "HEAD", "--", *paths) if paths else git_output(root, "cat-file", "-e", head + "^{commit}")
                if diff is None:
                    reasons.append("无法比较基线提交（可能已不可用）")
                elif diff:
                    reasons.append("代码路径有已提交变化")
        decision = "rerun" if reasons else "carry"
        result[decision].append(name)
        result["reasons"][name] = reasons or ["文档版本与代码均未变"]
    if not names:
        result["reasons"]["*"] = common + ["无可发现系统；先沿 CLAUDE.md 指针发现系统并用 --expect 传入"]
    unknown = set(force) - set(names)
    if unknown:
        raise ValueError("--force 含未知系统：" + "、".join(sorted(unknown)))
    return result


def run_record(output_dir: Path, systems: dict, docs: Documents, root: Path | None, baseline: Path | None) -> dict:
    return {"schema_version": 1, "output_dir": str(output_dir.resolve()),
            "exported_at": docs.manifest.get("exported_at"), "project_head": git_output(root, "rev-parse", "HEAD"),
            "baseline": str(baseline.resolve()) if baseline else None, "systems": systems}


def collect_system(path: Path, report: Report, docs: Documents, config: dict) -> dict:
    system = next((s for s in config.get("systems", []) if s["name"] == report.name), {})
    data = report_data(path, docs)
    if system:
        revisions = document_revisions(system, docs)[0]
    else:
        cited = [source_ref(cells[1])[0] for cells in table_rows(section(path.read_text(encoding="utf-8-sig").splitlines(), "### Features"))[1:] if len(cells) >= 2]
        entries = {posix(entry["file"]): entry for file in cited if (entry := docs.entry(file))}
        revisions = [{"file": file, **{k: entry[k] for k in ("revision_id", "revision") if k in entry}}
                     for file, entry in sorted(entries.items())]
    data.update({"docs": revisions, "code": system.get("code", []), "scope": system.get("scope"), "refs": system.get("refs", []),
                 "total": sum(report.counts.values()), **dict(zip(("implemented", "partial", "missing", "divergent", "unverifiable"),
                                                                  (report.counts[s] for s in STATUSES)))})
    return data


def stamp_keys(path: Path, rows: list[dict]) -> None:
    """仅改 Features 表，保留其他行及表内原始转义。"""
    lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
    inside, index = False, 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "### Features":
            inside = True
            continue
        if inside and re.match(r"^#{1,3}\s", stripped):
            break
        if not inside or not stripped.startswith("|"):
            continue
        cells = table_cells(line)
        if cells[:5] == FEATURE_HEADER:
            value = "Key"
        elif all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            value = "---"
        else:
            value = rows[index]["key"]
            index += 1
        # 五列追加；六列只换最后一格，前五列连转义写法都不变。
        prefix = stripped[:-1].rstrip() if stripped.endswith("|") else stripped
        if len(cells) == 6:
            prefix = prefix.rsplit("|", 1)[0].rstrip()
        ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        lines[i] = prefix + " | " + value + " |" + ending
    path.write_text("".join(lines), encoding="utf-8", newline="")


def carry_reports(output: Path, baseline_dir: Path, names: list[str], docs: Documents) -> None:
    if not names or any(not valid_system(name) for name in names):
        raise ValueError("--systems 须为合法系统名列表")
    baseline = load_baseline(baseline_dir, docs)
    prepared = []
    # 全部预检再写；目标用 x 模式，即使预检后出现同名文件也不覆盖。
    for name in names:
        source, target = baseline_dir / (name + ".md"), output / (name + ".md")
        if target.exists():
            raise ValueError(f"拒绝覆盖已有报告：{target}")
        report = inspect_report(source)
        if report.problems:
            raise ValueError(f"基线 {name} 校验不通过：{'；'.join(report.problems)}")
        data = collect_system(source, report, docs, {})
        data.update(baseline.get("systems", {}).get(name, {}))
        data["carried_from"] = str(baseline_dir.resolve())
        lines = source.read_text(encoding="utf-8-sig").splitlines()
        lines = [line for line in lines if not re.fullmatch(r"> 沿用基线 .+，本轮未重跑：文档与代码均未变", line)]
        title = next(i for i, line in enumerate(lines) if line.strip() == f"## {name}")
        lines.insert(title + 1, f"> 沿用基线 {baseline_dir.resolve()}，本轮未重跑：文档与代码均未变")
        prepared.append((name, target, "\n".join(lines) + "\n", data))
    run_path = output / "RUN.json"
    record = read_json(run_path) if run_path.exists() else run_record(output, {}, docs, None, baseline_dir)
    for name, _, _, _ in prepared:
        if name in record["systems"]:
            raise ValueError(f"拒绝覆盖 RUN.json 中已有系统：{name}")
    output.mkdir(parents=True, exist_ok=True)
    for name, target, text, data in prepared:
        with target.open("x", encoding="utf-8") as stream:
            stream.write(text)
        record["systems"][name] = data
    run_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="校验差距报告并收集汇总")
    parser.add_argument("output_dir", type=Path, nargs="?", help="系统报告目录（--plan 可省略）")
    parser.add_argument("--write-summary", action="store_true", help="写入 SUMMARY.md")
    parser.add_argument("--out", type=Path, help="汇总输出目录，默认使用系统报告目录")
    parser.add_argument("--expect", help="预期系统名，以逗号分隔；省略时只检查现有报告")
    parser.add_argument("--baseline", type=Path, help="基线报告目录，优先读取 RUN.json")
    parser.add_argument("--docs-root", type=Path, help="本地设计镜像目录")
    parser.add_argument("--project-root", type=Path, help="工程根，用于配置相对路径与 git 快照")
    parser.add_argument("--config", type=Path, help="gap-analysis.config.yaml")
    parser.add_argument("--match-threshold", type=float, default=.6, help="二级匹配阈值，默认 0.6")
    parser.add_argument("--stamp-keys", action="store_true", help="把脚本铸造的 Key 写到报告第六列")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="只输出增量计划")
    mode.add_argument("--carry", action="store_true", help="复制指定基线报告，拒绝覆盖")
    parser.add_argument("--json", action="store_true", help="计划输出为纯 JSON；默认输出人读表")
    parser.add_argument("--force", help="强制重跑的系统，以逗号分隔")
    parser.add_argument("--systems", help="沿用基线的系统，以逗号分隔")
    args = parser.parse_args(argv)
    if not 0 <= args.match_threshold <= 1:
        parser.error("--match-threshold 须在 0 到 1 之间")
    if not args.plan and args.output_dir is None:
        parser.error("需要 OUTPUT_DIR")
    if args.carry and (not args.baseline or not args.systems):
        parser.error("--carry 需要 --baseline 和 --systems")
    if (args.plan or args.carry) and (args.stamp_keys or args.write_summary or args.out):
        parser.error("--plan / --carry 与收集写入参数分开运行")
    if (args.json or args.force) and not args.plan:
        parser.error("--json / --force 仅用于 --plan")
    if args.systems and not args.carry:
        parser.error("--systems 仅用于 --carry")
    try:
        config_path = args.config
        if config_path is None and args.project_root:
            candidate = args.project_root / "gap-analysis.config.yaml"
            if candidate.is_file():
                config_path = candidate
        config = load_config(config_path)
        if any(config.get(k) for k in ("docs_root", "manifest")) and not args.project_root:
            raise ValueError("配置相对路径需要 --project-root")
        docs_root = args.docs_root or (args.project_root / posix(config["docs_root"]) if config.get("docs_root") else None)
        manifest = args.project_root / posix(config["manifest"]) if config.get("manifest") else None
        if args.docs_root and (args.docs_root / "_manifest.json").is_file():
            # 显式 --docs-root（比如从 git 取出的历史快照）自带的清单优先于配置里指向工程当前镜像的那份，
            # 否则历史快照会被当前版本号污染，基线记的就不是当时的文档状态。
            manifest = args.docs_root / "_manifest.json"
        if manifest and not manifest.is_file():
            raise ValueError(f"配置的 manifest 不存在：{manifest}")
        docs = Documents(docs_root, manifest)
        names = list(dict.fromkeys(x.strip() for x in (args.expect or "").split(",") if x.strip()))
        if args.plan:
            baseline = None
            if args.baseline and args.baseline.is_dir():
                # 计划缺 RUN 时只需系统清单；旧报告即使残缺也不能阻止「全部重跑」兜底。
                baseline = (load_baseline(args.baseline, docs) if (args.baseline / "RUN.json").is_file()
                            else {"systems": {p.stem: {} for p in report_paths(args.baseline)[0]}})
            if not config and args.output_dir and args.output_dir.is_dir():
                names.extend(p.stem for p in report_paths(args.output_dir)[0])
            plan = make_plan(config, baseline, args.baseline, args.project_root, docs,
                             [x.strip() for x in (args.force or "").split(",") if x.strip()], names)
            if args.json:
                print(json.dumps(plan, ensure_ascii=False, indent=2))
            else:
                print("| 系统 | 决定 | 原因 |\n|---|---|---|")
                for decision in ("rerun", "carry"):
                    for name in plan[decision]:
                        print(f"| {md_cell(name)} | {decision} | {md_cell('；'.join(plan['reasons'][name]))} |")
                if not plan["rerun"] and not plan["carry"]:
                    print("；".join(plan["reasons"]["*"]))
            return 0
        if args.carry:
            carry_reports(args.output_dir, args.baseline, list(dict.fromkeys(x.strip() for x in args.systems.split(",") if x.strip())), docs)
            print(f"已沿用基线报告并记录 RUN.json：{args.systems}")
            return 0
        baseline = load_baseline(args.baseline, docs) if args.baseline else None
        if args.baseline:
            if args.stamp_keys and args.output_dir.resolve() == args.baseline.resolve():
                raise ValueError("拒绝把 Key 写进基线目录；请先复制到新目录")
            if args.write_summary and (args.out or args.output_dir).resolve() == args.baseline.resolve():
                raise ValueError("拒绝把汇总写进基线目录；请指定 --out 新目录")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"不通过：{exc}", file=sys.stderr)
        return 1
    if not args.output_dir.is_dir():
        print(f"不通过：报告目录不存在：{args.output_dir}")
        return 1
    paths, skipped = report_paths(args.output_dir)
    reports = [inspect_report(path) for path in paths]
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
    passed = bool(reports) and not missing and not any(r.problems for r in reports)
    run, transitions = None, None
    if passed:
        try:
            systems = {report.name: collect_system(path, report, docs, config) for path, report in zip(paths, reports)}
            carried_run = args.output_dir / "RUN.json"
            saved = read_json(carried_run).get("systems", {}) if carried_run.is_file() else {}
            for name, data in systems.items():
                if data.get("carried_from"):
                    old = saved.get(name) or (baseline or {}).get("systems", {}).get(name)
                    if old is None:
                        raise ValueError(f"{name} 有沿用标记但缺少基线记录，请重新 --carry")
                    def signature(row):
                        return (str(row["#"]), row["status"], row.get("match_text", normalized(split_requirement(row["requirement"])[0])))
                    if [signature(row) for row in data["rows"]] != [signature(row) for row in old["rows"]]:
                        raise ValueError(f"{name} 沿用报告已改动；请去掉沿用标记并重新核对，不能沿用旧状态")
                    marker = data["carried_from"]
                    data.update(old)
                    data["carried_from"] = marker
            run = run_record(args.output_dir, systems, docs, args.project_root, args.baseline)
            if baseline is not None:
                transitions, notices = transitions_text(systems, baseline["systems"], args.baseline, args.match_threshold)
                for notice in notices:
                    print(notice)
            if args.stamp_keys:
                for path in paths:
                    stamp_keys(path, systems[path.stem]["rows"])
        except (OSError, ValueError) as exc:
            print(f"不通过：运行记录或键生成失败：{exc}")
            return 1
    if args.write_summary:
        destination = (args.out or args.output_dir) / "SUMMARY.md"
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(rendered, encoding="utf-8")
            if run is not None:
                (destination.parent / "RUN.json").write_text(json.dumps(run, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if transitions is not None:
                (destination.parent / "TRANSITIONS.md").write_text(transitions, encoding="utf-8")
        except OSError as exc:
            print(f"不通过：汇总写入失败：{exc}")
            return 1
        print(f"已写入 {destination}")
    print("总评：" + ("全部通过" if passed else "有不通过项"))
    return 0 if passed else 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
