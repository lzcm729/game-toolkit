#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复核后报告校验、稳定要求键、基线迁移与增量计划；默认只读。"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
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
    added: int = 0
    other: int = 0
    warnings: list[str] = field(default_factory=list)


def review_status(value: str) -> str | None:
    """兼容旧复核表的图标、加粗与明确改判前缀；组合状态/自然语言不猜。"""
    value = re.sub(r"^(?:改判|维持|补行)\s*", "", value.strip(" *`"))
    for status in STATUSES:
        icon, label = status.split()
        if re.match(rf"^{re.escape(icon)}(?:\s+{label})?(?=\s*[（(]|\s*维持|$)", value):
            return status
    return None


def review_addition(value: str) -> bool:
    return bool(re.fullmatch(r"新增|[（(]原(?:稿|报告)无此行[）)]|—[（(](?:漏列|漏项|漏|缺行)[）)]|[（(]漏收，新增[）)]",
                             value.strip(" *`")))


def inspect_report(path: Path, stage: str = "review", legacy: bool = False) -> Report:
    if stage not in ("analysis", "review"):
        raise ValueError("stage 须为 analysis 或 review")
    problems: list[str] = []
    warnings = ["旧报告兼容读取；新语义约束只告警，不追认历史输入指纹。"] if legacy else []
    counts: Counter = Counter({status: 0 for status in STATUSES})
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeError) as exc:
        return Report(path.stem, counts, 0, [f"读取失败：{exc}"])
    headings = [f"## {path.stem}", "### Features", "### Summary", "### Scan Scope"]
    if stage == "review":
        headings.append("### 复核记录")
    for heading in headings:
        occurrences = sum(line.strip() == heading for line in lines)
        if not occurrences:
            problems.append(f"缺标题 {heading}")
        elif occurrences != 1:
            problems.append(f"标题重复：{heading}")
    if not any(line.strip() for line in section(lines, "### Scan Scope")):
        problems.append("Scan Scope 扫描范围必须非空")
    semantic = warnings if legacy else problems
    occurrences = sum(line.strip() == "### Code-only mechanics" for line in lines)
    if occurrences != 1:
        semantic.append("缺标题 ### Code-only mechanics" if not occurrences else "标题重复：### Code-only mechanics")
    elif not any(line.strip() for line in section(lines, "### Code-only mechanics")):
        semantic.append("Code-only mechanics 必须填写机制或未发现及查阅范围")

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
        file, line, _ = source_ref(cells[1])
        if file == "unknown" or line < 1:
            semantic.append(f"Features 第 {number} 行出处无法解析：须逐行写文件名和正行号，不得省成 :行号")
        if width == 6 and cells[5].split("#", 1)[0] == "unknown":
            semantic.append(f"Features 第 {number} 行 Key 使用 unknown 身份")
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

    changed = added = other = 0
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
            # 旧报告的依据里可能有未转义的管道命令；仅分类原判、改判。
            # 空行之后的独立抽验表没有「改判」列，不参与统计。
            if cells[1] != cells[2]:
                before, after = review_status(cells[1]), review_status(cells[2])
                if before and after and before != after:
                    changed += 1
                elif review_addition(cells[1]) and after:
                    added += 1
                else:
                    other += 1
    if stage == "review" and not found_review:
        problems.append("复核记录缺少四列表头（# | 原判 | 改判 | 依据）")
    return Report(path.stem, counts, changed, problems, added, other, warnings)


def summary_text(reports: list[Report], missing: list[str]) -> str:
    lines = ["# 差距分析汇总", "",
             "| 系统 | Total | ✅ | ⚠️ | ❌ | 🔄 | ❓ | Inspectable | Coverage of inspected | 复核改判 | 要求补行 | 其他复核差异 | 校验 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]

    def row(name, counts, changed, added, other, verdict):
        insp, cov = ratios(counts)
        name = name.replace("|", r"\|")
        values = [name, str(sum(counts.values())), *(str(counts[s]) for s in STATUSES),
                  f"{insp:.1f}%", f"{cov:.1f}%", str(changed), str(added), str(other), verdict]
        return "| " + " | ".join(values) + " |"

    total: Counter = Counter({status: 0 for status in STATUSES})
    for report in reports:
        lines.append(row(report.name, report.counts, report.changed, report.added, report.other,
                         "不通过" if report.problems else "通过（有警告）" if report.warnings else "通过"))
        total.update(report.counts)
    for name in missing:
        lines.append("| " + name.replace("|", r"\|") + " | 未产出 | | | | | | | | | | | 不通过 |")
    passed = not missing and bool(reports) and not any(r.problems for r in reports)
    lines.append(row("合计", total, sum(r.changed for r in reports), sum(r.added for r in reports),
                     sum(r.other for r in reports), "通过（有警告）" if passed and any(r.warnings for r in reports)
                     else "通过" if passed else "不通过"))
    lines += ["", "合计按 Features 表中合法状态重算；比例以合计计数计算，不平均系统百分比。",
              "复核改判只计五状态之间变化；要求补行计「新增 → 五状态」；其余两格不同单列其他复核差异。",
              "旧复核表兼容单状态图标、加粗/改判前缀与明确漏行标记；组合状态或仅写维持不推断改判。"]
    for report in reports:
        lines.extend(f"- 警告 {report.name}：{warning}" for warning in report.warnings)
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
    # 只读第一个明确出处，范围以首行铸锚点；版本属于出处元数据，不属于文件名。
    version = r"(?:rev(?:ision(?:_id)?)?\s*[:=]?\s*\d+|v\d+(?:\.\d+)*)"
    match = re.fullmatch(
        rf'\s*(.+?\.(md|csv))[`"”」]*\s*(?:(?:[（(]\s*{version}\s*[）)]|{version})\s*)?'
        r"(?:[:：]\s*(\d+)(?:\s*[-–—~～至]\s*(\d+))?|第\s*(\d+)(?:\s*[-–—~～至]\s*(\d+))?\s*行).*",
        first, re.I)
    if not match:
        return "unknown", 0, False
    file, ext, md_line, md_end, csv_line, csv_end = match.groups()
    start, end = int(md_line or csv_line), md_end or csv_end
    if start < 1 or end and int(end) < start:
        return "unknown", 0, False
    return file.strip(" `\"“”「」"), start, ext.lower() == "csv"


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


def display_path(path: Path | None, root: Path | None) -> str | None:
    """产物里的路径一律写成相对工程根。

    报告、RUN.json 与 TRANSITIONS.md 都会提交进仓库、被别人读到，绝对路径对别人是错的
    （也会随工作副本搬家而过期）。拿不到工程根、或路径不在工程根下时退回绝对路径，不猜。
    """
    if path is None:
        return None
    resolved = path.resolve()
    if root is not None:
        try:
            return resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            pass
    return str(resolved)


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
    reference_column = mechanics[0].index("code_ref") if mechanics and "code_ref" in mechanics[0] else None
    carried = next((re.fullmatch(r"> 沿用基线 (.+)，本轮未重跑：文档与代码均未变", line) for line in lines
                    if line.startswith("> 沿用基线 ")), None)
    return {"rows": rows, "code_only": [{"mechanism": row[mechanism_column],
            "code_ref": row[reference_column] if reference_column is not None and len(row) > reference_column else None}
            for row in mechanics[1:] if len(row) > mechanism_column],
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
            legacy = data.get("validation_version", 1) < 2
            if legacy:
                print(f"警告：基线 {name} 为旧 RUN，兼容读取；历史输入依赖不追认。", file=sys.stderr)
            unknown = sum(row["key"].split("#", 1)[0] == "unknown" for row in data["rows"])
            if unknown:
                if not legacy:
                    raise ValueError(f"新 RUN {name} 含 {unknown} 行 unknown 身份")
                print(f"警告：基线 {name} 含 {unknown} 行 unknown 身份，保留旧键。", file=sys.stderr)
            path = directory / (name + ".md")
            if path.is_file():
                extra = report_data(path, docs)
                if "code_only_present" not in data:
                    data.update({k: extra[k] for k in ("code_only", "code_only_present")})
                else:
                    # 旧 RUN 仅存描述：只为同描述补回当轮 Markdown 的证据，绝不从当前源码补历史事实。
                    refs = {item["mechanism"]: item["code_ref"] for item in extra["code_only"]}
                    data["code_only"] = [{**item, "code_ref": item.get("code_ref") or refs.get(item["mechanism"])}
                                         for item in code_only_entries(data)]
            if not data.get("code_only_present", False):
                if not legacy:
                    raise ValueError(f"新 RUN {name} 缺少 Code-only mechanics")
                print(f"警告：基线 {name} 没有 Code-only mechanics，无法确认历史机制差异。", file=sys.stderr)
        return run
    systems = {}
    for path in report_paths(directory)[0]:
        report = inspect_report(path, legacy=True)
        if report.problems:
            raise ValueError(f"基线 {path.stem} 校验不通过：{'；'.join(report.problems)}")
        for warning in report.warnings:
            print(f"警告：基线 {path.stem}：{warning}", file=sys.stderr)
        systems[path.stem] = report_data(path, docs, use_stamped=True)
    return {"systems": systems}


def match_rows(current: list[dict], baseline: list[dict], threshold: float = .6) -> list[tuple[dict | None, dict | None, int]]:
    """同键 → 同 doc/h8 唯一漂移 → 同 doc/anchor 相似度 → 剩余；每行只用一次。

    漂移的标记为 4，保留既有 1/2/3 的接口含义；执行顺序并非标记数值顺序。
    """
    used_current, used_baseline, matches = set(), set(), []
    for ci, row in enumerate(current):
        bi = next((i for i, old in enumerate(baseline) if i not in used_baseline and old["key"] == row["key"]), None)
        if bi is not None:
            used_current.add(ci)
            used_baseline.add(bi)
            matches.append((row, baseline[bi], 1))
    def identities(rows, used):
        groups = {}
        for i, row in enumerate(rows):
            doc, anchor, digest = row["key"].split("#")
            if i not in used and doc != "unknown":
                groups.setdefault((doc, digest), []).append(i)
        return groups
    current_groups = identities(current, used_current)
    baseline_groups = identities(baseline, used_baseline)
    for identity, candidates in current_groups.items():
        previous = baseline_groups.get(identity, [])
        if len(candidates) == len(previous) == 1:
            ci, bi = candidates[0], previous[0]
            used_current.add(ci)
            used_baseline.add(bi)
            matches.append((current[ci], baseline[bi], 4))
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


TRANSITION_COUNTS = ("未变", "退步", "修复", "其他变化", "改写", "锚点漂移", "新增", "消失")


def code_only_entries(data: dict) -> list[dict]:
    """兼容旧 RUN 的字符串；缺失证据保留未知。"""
    return [dict(item) if isinstance(item, dict) else {"mechanism": item, "code_ref": None}
            for item in data.get("code_only", [])]


def transitions_text(current: dict, baseline: dict, baseline_dir: Path, threshold: float = .6,
                     root: Path | None = None) -> tuple[str, list[str]]:
    lines = ["# 基线迁移", "", f"基线：{display_path(baseline_dir, root)}", "",
             "匹配顺序：完全同键 → 同文档同 h8 唯一锚点漂移 → 同文档同锚点措辞改写 → 新增／消失。",
             "改写与锚点漂移独立计数，可同时计入状态变化；只有一级同键同状态计未变。", ""]
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
                elif level == 4:
                    counts["锚点漂移"] += 1
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
                           f"{previous['status'] if previous else '—'} → {row['status'] if row else '—'}",
                           f"锚点漂移（{previous['key']} → {row['key']}）" if level == 4
                           else {1: "①", 2: "② 措辞改写", 3: "③"}[level]])) + " |")
        totals.update(counts)
        subtotal = "／".join(f"{key} {counts[key]}" for key in TRANSITION_COUNTS)
        notices.append(f"{name}：{subtotal}")
        lines += [f"## {name}", "", subtotal, "", "| 键 | 要求 | 基线状态 → 本轮状态 | 匹配级 |", "|---|---|---|---|", *changed, "",
                  "### Code-only mechanics", ""]
        if not old.get("code_only_present", False):
            lines.append("基线报告没有该节，无法确认机制新增／消失。")
        elif not now.get("code_only_present", False):
            lines.append("本轮报告没有该节，无法确认机制新增／消失。")
        else:
            current_entries, old_entries = code_only_entries(now), code_only_entries(old)
            current_descriptions = {item["mechanism"] for item in current_entries}
            old_descriptions = {item["mechanism"] for item in old_entries}
            added = [item for item in current_entries if item["mechanism"] not in old_descriptions]
            removed = [item for item in old_entries if item["mechanism"] not in current_descriptions]
            lines += ["描述差异、待核机制变化：以下仅对比文字，由复核／综合核源码与属主裁决后确认。",
                      "| 描述来源 | 机制描述 | code_ref |", "|---|---|---|"]
            for label, items in (("本轮独有描述", added), ("基线独有描述", removed)):
                lines.extend(f"| {label} | {md_cell(item['mechanism'])} | {md_cell(item.get('code_ref') or '旧记录未保存，待核')} |"
                             for item in items)
            if not added and not removed:
                lines.append("描述无差异；不据此断言机制未变。")
        lines.append("")
        if now.get("carried_from"):
            carried.append(f"- {name}：{now['carried_from']}")
    total_rows = sum(len(s.get("rows", [])) for s in baseline.values())
    stability = f"{100 * totals['level1'] / total_rows:.1f}%" if total_rows else "不适用（基线总行数为 0）"
    total = ("合计：" + "／".join(f"{key} {totals[key]}" for key in TRANSITION_COUNTS)
             + f"；稳定率 {stability}（一级 {totals['level1']} ÷ 基线 {total_rows}）；锚点漂移找回 {totals['level4']}，二级改写 {totals['level2']}，新增 {totals['新增']}，消失 {totals['消失']}")
    lines += ["## 沿用基线的系统", "", *(carried or ["无。"]), "", total]
    return "\n".join(lines) + "\n", notices + [total]


def git_output(root: Path | None, *args: str, input_text: str | None = None) -> str | None:
    if root is None or not root.is_dir():
        return None
    try:
        # 仅本次只读调用信任显式工程根，不改用户的全局 Git 配置。
        result = subprocess.run(["git", "-c", f"safe.directory={root.resolve().as_posix()}", "-C", str(root), *args],
                                input=input_text, capture_output=True, encoding="utf-8", errors="replace", timeout=30)
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
        fingerprint = file_fingerprint(docs.root / file, file, problems)
        revisions.append({**fingerprint, **fields,
                          "identity": (entry or {}).get("node_token") or PurePosixPath(file).stem})
    return revisions, problems


def file_fingerprint(path: Path, name: str, problems: list[str], optional: bool = False) -> dict:
    try:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError:
        digest = None
        if not optional:
            problems.append(f"输入文件不存在：{name}")
    except OSError as exc:
        digest = None
        problems.append(f"输入文件无法读取：{name}：{exc}")
    return {"file": name, "sha256": digest}


def safe_patterns(values) -> bool:
    return (isinstance(values, list) and all(isinstance(v, str) and v.strip()
            and not PureWindowsPath(v).drive and not PurePosixPath(posix(v)).is_absolute()
            and ".." not in PurePosixPath(posix(v)).parts for v in values))


def scan_inputs(path: Path) -> tuple[dict | None, list[str]]:
    """扫描者声明搜索范围（包括零命中的搜索）与补读参考，不从自然语言猜完整性。"""
    scope = "\n".join(section(path.read_text(encoding="utf-8-sig").splitlines(), "### Scan Scope"))
    blocks = re.findall(r"^```gap-inputs\s*\n(.*?)\n```\s*$", scope, re.M | re.S)
    if len(blocks) != 1:
        return None, ["Scan Scope 缺少唯一 gap-inputs 依赖块，实际依赖不完整；代码比较扩大到全工程"]
    try:
        data = json.loads(blocks[0])
    except ValueError:
        return None, ["gap-inputs 必须为 JSON 对象；代码比较扩大到全工程"]
    if not isinstance(data, dict) or any(not safe_patterns(data.get(k)) for k in ("code", "refs")):
        return None, ["gap-inputs.code / refs 须为相对工程根、不越界的路径列表；代码比较扩大到全工程"]
    if not isinstance(data.get("unresolved", []), list) or any(not isinstance(v, str) or not v.strip()
                                                            for v in data.get("unresolved", [])):
        return None, ["gap-inputs.unresolved 须为未能记录的依赖说明列表；代码比较扩大到全工程"]
    return data, []


def fingerprint_patterns(base: Path | None, patterns: list[str], problems: list[str]) -> list[dict]:
    files = set()
    for pattern in patterns:
        matches = list(base.glob(posix(pattern))) if base and base.is_dir() else []
        found = {file for p in matches for file in (p.rglob("*") if p.is_dir() else [p]) if file.is_file()}
        if not found:
            problems.append(f"依赖文件未匹配：{pattern}")
        files.update(found)
    return [file_fingerprint(p, p.relative_to(base).as_posix(), problems) for p in sorted(files)]


def path_covered(file: str, patterns: list[str]) -> bool:
    # 与配置的目录 / glob 约定一致，不能让 PurePath.match 的尾部匹配把别的目录算进来。
    for pattern in patterns:
        pattern = posix(pattern).rstrip("/")
        if pattern == "." or file == pattern or file.startswith(pattern + "/"):
            return True
        regex = ""
        i = 0
        while i < len(pattern):
            if pattern[i:i + 3] == "**/":
                regex += "(?:.*/)?"
                i += 3
            elif pattern[i:i + 2] == "**":
                regex += ".*"
                i += 2
            else:
                regex += "[^/]*" if pattern[i] == "*" else "[^/]" if pattern[i] == "?" else re.escape(pattern[i])
                i += 1
        if re.fullmatch(regex, file):
            return True
    return False


def input_snapshot(system: dict, docs: Documents, root: Path | None, scan: dict | None,
                   scan_problems: list[str], evidence: str = "") -> dict:
    """实际字节是失效依据；manifest revision 仅作显示，不能替正文证明未变。"""
    revisions, problems = document_revisions(system, docs)
    problems.extend(scan_problems)
    problems.extend(f"实际依赖未能记录，保守重跑：{item}" for item in (scan or {}).get("unresolved", []))
    refs = fingerprint_patterns(docs.root, system.get("refs", []), problems)
    project_inputs = []
    if root is None:
        problems.append("未提供工程根，无法记录声明、裁决与代码依赖")
    else:
        declaration = root / "game-toolkit.yaml"
        project_inputs.append(file_fingerprint(declaration, "game-toolkit.yaml", problems, optional=True))
        if declaration.is_file():
            try:
                declared = yaml.safe_load(declaration.read_text(encoding="utf-8-sig"))
                feedback = declared.get("doc_feedback", {}) if isinstance(declared, dict) else None
                if not isinstance(feedback, dict):
                    raise ValueError("doc_feedback 须为 mapping")
                for key in ("rulings_ledger", "decision_ledger", "engineering_log", "owners"):
                    if key not in feedback:
                        continue
                    if not safe_patterns([feedback[key]]):
                        raise ValueError(f"doc_feedback.{key} 路径无效")
                    project_inputs.extend(fingerprint_patterns(root, [feedback[key]], problems))
            except (OSError, ValueError, yaml.YAMLError) as exc:
                problems.append(f"项目声明依赖无法读取：{exc}")
    extra_refs = fingerprint_patterns(root, (scan or {}).get("refs", []), problems)
    code = sorted(set(posix(p) for p in [*system.get("code", []), *(scan or {}).get("code", [])]))
    notes = []
    if scan is None:
        code = ["."]
    elif evidence and root:
        # 明确的项目文件出处必须在声明范围内。裸文件名无法唯一解析时扩大范围，绝不假设已覆盖。
        inventory = git_output(root, "ls-files", "-z")
        files = (inventory or "").split("\0")
        citations = re.findall(r'([^\s`|「」“”（）；;,]+\.(?:cpp|h|hpp|c|cs|gd|ts|tsx|js|py|ps1|ini|uasset|umap))(?=[:：`\s]|$)', evidence, re.I)
        for citation in citations:
            citation = posix(citation).strip("()[]\"'")
            candidates = [f for f in files if f == citation or f.endswith("/" + citation)]
            if not candidates and (root / citation).is_file():
                candidates = [citation]
            if len(candidates) != 1 or not path_covered(candidates[0], code):
                code = ["."]
                notes.append(f"代码证据未被范围唯一覆盖：{citation}；比较扩大到全工程")
                break
    return {"version": 1, "docs": [{k: d[k] for k in ("file", "sha256", "identity")} for d in revisions],
            "refs": refs, "project_inputs": project_inputs, "scan_refs": extra_refs,
            "scan": scan, "code": code, "problems": problems, "notes": notes}


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
            snapshot = previous.get("inputs")
            if not isinstance(snapshot, dict) or snapshot.get("version") != 1:
                reasons.append("旧 RUN 缺少实际输入指纹、参考/裁决及实际代码依赖记录，保守重跑")
            else:
                if (not isinstance(snapshot.get("scan"), dict)
                        or any(not safe_patterns(snapshot["scan"].get(k)) for k in ("code", "refs"))
                        or not safe_patterns(snapshot.get("code")) or snapshot.get("code_dirty") is None):
                    reasons.append("基线实际依赖记录不完整，保守重跑")
                reasons.extend(snapshot.get("problems", []))
                if snapshot.get("code_dirty"):
                    reasons.append("基线分析时代码依赖有未提交或未跟踪修改，不能证明沿用")
                scan = snapshot.get("scan")
                current_inputs = input_snapshot(system, docs, root, scan if isinstance(scan, dict) else None, [])
                reasons.extend(current_inputs["problems"])
                for key, label in (("docs", "设计文件内容/身份或集合"), ("refs", "参考文件内容或集合"),
                                   ("project_inputs", "项目声明/裁决/账本"), ("scan_refs", "实际补读参考文件")):
                    if key not in snapshot or current_inputs[key] != snapshot[key]:
                        reasons.append(f"{label}指纹与基线不同")
            if not system.get("docs"):
                reasons.append("未配置评分文档")
            if system.get("code", []) != previous.get("code", []):
                reasons.append("代码范围与基线不同")
            if ("scope" in previous and previous["scope"] != system.get("scope")
                    or "refs" in previous and previous["refs"] != system.get("refs", [])):
                reasons.append("评分范围或参考清单与基线不同")
            head = (baseline or {}).get("project_head")
            if not head:
                reasons.append("基线没有 project_head")
            else:
                # 旧 RUN 无证据范围时查全工程；新 RUN 用已核实的搜索范围（包含阴性搜索）。
                paths = snapshot.get("code", ["."]) if isinstance(snapshot, dict) else ["."]
                # 空 code 明确表示无源码路径；不把空 pathspec 误当全仓库。
                diff = git_output(root, "diff", "--name-only", head, "HEAD", "--", *paths) if paths else git_output(root, "cat-file", "-e", head + "^{commit}")
                if diff is None:
                    reasons.append("无法比较基线提交（可能已不可用）")
                elif diff:
                    reasons.append("代码路径有已提交变化")
                if isinstance(snapshot, dict):
                    dirty = code_dirty(root, paths)
                    if dirty is None:
                        reasons.append("无法核对代码依赖的工作区状态")
                    elif dirty:
                        reasons.append("代码依赖有未提交或未跟踪修改")
        decision = "rerun" if reasons else "carry"
        result[decision].append(name)
        result["reasons"][name] = list(dict.fromkeys(reasons)) or ["实际文档/参考/裁决指纹与已覆盖的代码依赖均未变"]
    if not names:
        result["reasons"]["*"] = common + ["无可发现系统；先沿 CLAUDE.md 指针发现系统并用 --expect 传入"]
    unknown = set(force) - set(names)
    if unknown:
        raise ValueError("--force 含未知系统：" + "、".join(sorted(unknown)))
    return result


def run_record(output_dir: Path, systems: dict, docs: Documents, root: Path | None, baseline: Path | None) -> dict:
    return {"schema_version": 1, "output_dir": display_path(output_dir, root),
            "exported_at": docs.manifest.get("exported_at"), "project_head": git_output(root, "rev-parse", "HEAD"),
            "baseline": display_path(baseline, root), "systems": systems}


def code_dirty(root: Path | None, paths: list[str]) -> bool | None:
    if not paths:
        return False
    tree = git_output(root, "ls-tree", "-rz", "--full-tree", "HEAD")
    untracked = git_output(root, "ls-files", "-z", "--others", "--exclude-standard")
    if tree is None or untracked is None:
        return None
    tracked = {}
    for entry in tree.split("\0"):
        if entry:
            meta, name = entry.split("\t", 1)
            tracked[name] = meta.split()
    if any(name not in tracked and path_covered(name, paths) for name in untracked.split("\0") if name):
        return True
    selected = {name: meta for name, meta in tracked.items() if path_covered(name, paths)}
    if any(meta[1] != "blob" or meta[0] == "120000" or not (root / name).is_file() for name, meta in selected.items()):
        return True
    if not selected:
        return False
    # 比较实际工作文件与 HEAD，不能让暂存区状态代替正文；hash-object 不带 -w，不写对象/索引。
    hashes = git_output(root, "hash-object", "--stdin-paths", input_text="".join(
        json.dumps((root / name).resolve().as_posix(), ensure_ascii=False) + "\n" for name in selected))
    if hashes is None or len(hashes.splitlines()) != len(selected):
        return None
    return any(digest != meta[2] for digest, meta in zip(hashes.splitlines(), selected.values()))


def collect_system(path: Path, report: Report, docs: Documents, config: dict,
                   root: Path | None = None, legacy: bool = False) -> dict:
    system = next((s for s in config.get("systems", []) if s["name"] == report.name), {})
    data = report_data(path, docs, use_stamped=legacy)
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
    data["validation_version"] = 1 if legacy else 2
    if not legacy:
        scan, problems = scan_inputs(path)
        snapshot = input_snapshot(system, docs, root, scan, problems, path.read_text(encoding="utf-8-sig"))
        snapshot["code_dirty"] = code_dirty(root, snapshot["code"])
        if snapshot["code_dirty"] is None:
            snapshot["problems"].append("无法记录代码工作区状态")
        data["inputs"] = snapshot
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


def carry_reports(output: Path, baseline_dir: Path, names: list[str], docs: Documents,
                  root: Path | None = None) -> None:
    if not names or any(not valid_system(name) for name in names):
        raise ValueError("--systems 须为合法系统名列表")
    baseline = load_baseline(baseline_dir, docs)
    prepared = []
    # 全部预检再写；目标用 x 模式，即使预检后出现同名文件也不覆盖。
    for name in names:
        source, target = baseline_dir / (name + ".md"), output / (name + ".md")
        if target.exists():
            raise ValueError(f"拒绝覆盖已有报告：{target}")
        report = inspect_report(source, legacy=baseline.get("systems", {}).get(name, {}).get("validation_version", 1) < 2)
        if report.problems:
            raise ValueError(f"基线 {name} 校验不通过：{'；'.join(report.problems)}")
        data = collect_system(source, report, docs, {}, root, legacy=True)
        data.update(baseline.get("systems", {}).get(name, {}))
        data["carried_from"] = display_path(baseline_dir, root)
        lines = source.read_text(encoding="utf-8-sig").splitlines()
        lines = [line for line in lines if not re.fullmatch(r"> 沿用基线 .+，本轮未重跑：文档与代码均未变", line)]
        title = next(i for i, line in enumerate(lines) if line.strip() == f"## {name}")
        lines.insert(title + 1, f"> 沿用基线 {display_path(baseline_dir, root)}，本轮未重跑：文档与代码均未变")
        prepared.append((name, target, "\n".join(lines) + "\n", data))
    run_path = output / "RUN.json"
    record = read_json(run_path) if run_path.exists() else run_record(output, {}, docs, root, baseline_dir)
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
    mode.add_argument("--report", type=Path, help="只读校验一份报告，不扫描同目录其他系统")
    parser.add_argument("--stage", choices=("analysis", "review"), default="review", help="单报告阶段，默认 review")
    parser.add_argument("--legacy", action="store_true", help="显式兼容读取历史报告，告警并保留已有 RUN 行键；不补历史输入指纹")
    parser.add_argument("--json", action="store_true", help="计划输出为纯 JSON；默认输出人读表")
    parser.add_argument("--force", help="强制重跑的系统，以逗号分隔")
    parser.add_argument("--systems", help="沿用基线的系统，以逗号分隔")
    args = parser.parse_args(argv)
    if not 0 <= args.match_threshold <= 1:
        parser.error("--match-threshold 须在 0 到 1 之间")
    if not args.plan and not args.report and args.output_dir is None:
        parser.error("需要 OUTPUT_DIR")
    if args.report and any((args.output_dir, args.write_summary, args.out, args.expect, args.baseline,
                            args.stamp_keys, args.json, args.force, args.systems)):
        parser.error("--report 是单报告只读入口，不与目录、汇总、基线或写入参数混用")
    if args.stage != "review" and not args.report:
        parser.error("--stage analysis 仅用于 --report，目录汇总必须完成复核")
    if args.legacy and (args.plan or args.carry or args.stamp_keys):
        parser.error("--legacy 仅用于历史报告读取/重汇总，不写 Key；基线与 carry 自动按原记录兼容")
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
        if args.report:
            report = inspect_report(args.report, args.stage, args.legacy)
            for warning in report.warnings:
                print(f"警告：{warning}")
            for problem in report.problems:
                print(f"不通过：{problem}")
            print(f"{report.name} {args.stage}：" + ("不通过" if report.problems else "通过"))
            return 1 if report.problems else 0
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
            carry_reports(args.output_dir, args.baseline,
                list(dict.fromkeys(x.strip() for x in args.systems.split(",") if x.strip())), docs, args.project_root)
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
    try:
        source_run = args.output_dir / "RUN.json"
        saved = (load_baseline(args.output_dir, docs).get("systems", {}) if args.legacy and source_run.is_file()
                 else read_json(source_run).get("systems", {}) if source_run.is_file() else {})
    except (OSError, ValueError) as exc:
        print(f"不通过：{exc}", file=sys.stderr)
        return 1
    def is_legacy(path):
        data = saved.get(path.stem, {})
        # --legacy 不能放宽已标记为新契约的报告。沿用旧报告保留兼容，不因换目录升级契约。
        return data.get("validation_version", 1) < 2 and (args.legacy or bool(data.get("carried_from")))
    reports = [inspect_report(path, legacy=is_legacy(path)) for path in paths]
    for name in skipped:
        # 同目录里的补充材料（发布映射、备忘）没有 Features 表，不是系统报告；
        # 靠 --expect 兜底：本该是报告却没写出 Features 的系统会在缺失清单里出现。
        print(f"跳过（非报告，无 ### Features）：{name}")
    names = {report.name for report in reports}
    missing = [name for name in dict.fromkeys(x.strip() for x in (args.expect or "").split(","))
               if name and name not in names]
    for report in reports:
        counts = " ".join(f"{s.split()[0]}{report.counts[s]}" for s in STATUSES)
        print(f"{'不通过' if report.problems else '通过'} {report.name}：Total {sum(report.counts.values())} {counts}；复核改判 {report.changed}／要求补行 {report.added}／其他 {report.other}")
        for problem in report.problems:
            print(f"  - {problem}")
        for warning in report.warnings:
            print(f"  警告：{warning}")
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
            systems = {report.name: collect_system(path, report, docs, config, args.project_root, is_legacy(path))
                       for path, report in zip(paths, reports)}
            for name, data in systems.items():
                if data.get("carried_from") or args.legacy and name in saved:
                    old = saved.get(name) or (baseline or {}).get("systems", {}).get(name)
                    if old is None:
                        raise ValueError(f"{name} 有沿用标记但缺少基线记录，请重新 --carry")
                    def signature(row):
                        return (str(row["#"]), row["status"], row.get("match_text", normalized(split_requirement(row["requirement"])[0])))
                    if [signature(row) for row in data["rows"]] != [signature(row) for row in old["rows"]]:
                        raise ValueError(f"{name} 历史/沿用报告与 RUN 行记录不一致；请重新核对，不能沿用旧状态")
                    if data.get("carried_from"):
                        marker = data["carried_from"]
                        data.update(old)
                        data["carried_from"] = marker
                    else:
                        # 历史回放只重算汇总/迁移，不用今天的设计锚点或文件指纹替换当轮身份与输入。
                        data.update(old)
                        data["docs"] = old.get("docs", [])
                        data.setdefault("validation_version", 1)
                        if old.get("validation_version", 1) < 2:
                            data.pop("inputs", None)
                for warning in data.get("inputs", {}).get("problems", []) + data.get("inputs", {}).get("notes", []):
                    print(f"增量警告 {name}：{warning}")
            run = run_record(args.output_dir, systems, docs, args.project_root, args.baseline)
            if args.legacy and source_run.is_file():
                original = read_json(source_run)
                for key in ("project_head", "exported_at"):
                    run[key] = original.get(key)
            if baseline is not None:
                transitions, notices = transitions_text(systems, baseline["systems"], args.baseline, args.match_threshold,
                    args.project_root)
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
