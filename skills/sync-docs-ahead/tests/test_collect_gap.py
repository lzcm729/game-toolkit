# -*- coding: utf-8 -*-
"""用临时报告验证收集器的判分边界与落盘行为。"""
from collections import Counter
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "collect_gap.py"
spec = importlib.util.spec_from_file_location("collect_gap", SCRIPT)
gap = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gap
spec.loader.exec_module(gap)


def make_report(tmp_path, name="系统甲", statuses=None, bom=False):
    statuses = list(statuses if statuses is not None else gap.STATUSES)
    counts = Counter(statuses)
    insp, cov = gap.ratios(counts)
    text = f"## {name}\n\n### Features\n\n"
    text += "| # | Design Requirement | Status | Code Reference | Notes |\n|---|---|---|---|---|\n"
    for i, status in enumerate(statuses, 1):
        text += f"| {i} | 需求（规格.md:{i}） | {status} | 实现.txt:{i} | 依据 |\n"
    text += "\n### Summary\n"
    text += f"- Total features: {len(statuses)}\n"
    text += "".join(f"- {s}: {counts[s]}\n" for s in gap.STATUSES)
    text += f"- Inspectable: {insp:.1f}%\n- Coverage of inspected: {cov:.1f}%\n"
    text += "\n### Scan Scope\n\n实现目录的文本；搜索后阅读；跳过生成物与运行行为。\n"
    text += "\n### Code-only mechanics\n\n未发现。\n"
    text += "\n### 复核记录\n\n| # | 原判 | 改判 | 依据 |\n|---|---|---|---|\n"
    text += "| 1 | ❌ Missing | ✅ Implemented | 实现.txt:1 |\n"
    text += "| 2 | ⚠️ Partial | ⚠️ Partial | 维持原判 |\n"
    path = tmp_path / f"{name}.md"
    path.write_text(text, encoding="utf-8-sig" if bom else "utf-8")
    return path


def rewrite(path, old, new):
    text = path.read_text(encoding="utf-8-sig")
    assert old in text
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_valid_report_and_bom(tmp_path, capsys):
    path = make_report(tmp_path, bom=True)
    assert gap.main([str(tmp_path)]) == 0
    assert "全部通过" in capsys.readouterr().out
    report = gap.inspect_report(path)
    assert report.counts == Counter(gap.STATUSES)
    assert report.changed == 1


@pytest.mark.parametrize("heading", ["## 系统甲", "### Features", "### Summary"])
def test_missing_heading(tmp_path, heading):
    path = make_report(tmp_path)
    rewrite(path, heading, "### 错误标题")
    assert any("缺标题 " + heading in p for p in gap.inspect_report(path).problems)
    assert gap.main([str(tmp_path)]) == 1


@pytest.mark.parametrize("status", ["✅", "✅ Implemented extra", "unknown", "✅ Implemented / ❌ Missing"])
def test_invalid_status(tmp_path, status):
    path = make_report(tmp_path)
    rewrite(path, "| ✅ Implemented | 实现", f"| {status} | 实现")
    assert any("Status" in p for p in gap.inspect_report(path).problems)


def test_wrong_summary_line_count(tmp_path):
    path = make_report(tmp_path)
    rewrite(path, "### Summary\n", "### Summary\n- extra: 1\n")
    assert any("恰好 8 行" in p for p in gap.inspect_report(path).problems)


def test_counts_disagree_even_when_summary_parts_sum_to_total(tmp_path):
    path = make_report(tmp_path)
    rewrite(path, "- ✅ Implemented: 1", "- ✅ Implemented: 2")
    rewrite(path, "- ❌ Missing: 1", "- ❌ Missing: 0")
    assert any("表格 1 行 vs Summary 2" in p for p in gap.inspect_report(path).problems)


@pytest.mark.parametrize("key,value", [("Total features", "6"), ("✅ Implemented", "-1"), ("✅ Implemented", "1x")])
def test_bad_summary_count(tmp_path, key, value):
    path = make_report(tmp_path)
    old = "5" if key == "Total features" else "1"
    rewrite(path, f"- {key}: {old}", f"- {key}: {value}")
    assert gap.inspect_report(path).problems


@pytest.mark.parametrize("key,old,new", [("Inspectable", "80.0", "90.0"), ("Coverage of inspected", "37.5", "40.0")])
def test_wrong_percentage(tmp_path, key, old, new):
    path = make_report(tmp_path)
    rewrite(path, f"{key}: {old}%", f"{key}: {new}%")
    assert any(key + " 百分比" in p for p in gap.inspect_report(path).problems)


def test_formula_last_percentage_and_tolerance(tmp_path):
    path = make_report(tmp_path)
    rewrite(path, "Inspectable: 80.0%", "Inspectable: (Total - Unverifiable) / Total * 100% = 81.0%")
    rewrite(path, "Coverage of inspected: 37.5%", "Coverage of inspected: formula * 100% = 36.5%")
    assert not gap.inspect_report(path).problems


def test_escaped_pipes_in_both_tables(tmp_path):
    path = make_report(tmp_path)
    rewrite(path, "需求（", r"需求 a\|b（")
    rewrite(path, "| 依据 |", r"| a\|b 的依据 |")
    rewrite(path, "| 实现.txt:1 |", r"| 实现.txt:1 中 a\|b |")
    result = gap.inspect_report(path)
    assert not result.problems
    assert result.changed == 1
    assert sum(result.counts.values()) == 5


def test_review_ignores_separate_sampling_table_and_allows_evidence_pipe(tmp_path):
    path = make_report(tmp_path)
    rewrite(path, "| 维持原判 |", "| 搜索 a | b |")
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n抽验：\n\n| # | 原判 | 抽验依据 |\n|---|---|---|\n| 3 | ✅ | file:3 |\n")
    result = gap.inspect_report(path)
    assert not result.problems
    assert result.changed == 1


def test_supplementary_markdown_is_skipped_with_notice(tmp_path, capsys):
    """同目录的补充材料（没有任何报告标题）跳过并打印说明；--expect 点名它时按缺失报错。"""
    make_report(tmp_path)
    (tmp_path / "发布映射.md").write_text("# 附加校验报告", encoding="utf-8")
    assert gap.main([str(tmp_path)]) == 0
    assert "跳过（非报告" in capsys.readouterr().out
    assert gap.main([str(tmp_path), "--expect", "发布映射"]) == 1


def test_broken_report_with_partial_headings_still_fails(tmp_path):
    """有报告标题但残缺的文件仍算报告，要报错，不能当补充材料跳过。"""
    make_report(tmp_path)
    (tmp_path / "半成品.md").write_text("## 半成品\n\n### Summary\n- Total features: 0\n", encoding="utf-8")
    assert gap.main([str(tmp_path)]) == 1


@pytest.mark.parametrize("heading", ["### Scan Scope", "### 复核记录"])
def test_missing_scope_or_review(tmp_path, heading):
    path = make_report(tmp_path)
    rewrite(path, heading, "### 不相关节")
    assert any("缺标题 " + heading in p for p in gap.inspect_report(path).problems)


def test_empty_scope(tmp_path):
    path = make_report(tmp_path)
    rewrite(path, "实现目录的文本；搜索后阅读；跳过生成物与运行行为。", "")
    assert any("扫描范围必须非空" in p for p in gap.inspect_report(path).problems)


def test_features_stop_at_next_section(tmp_path):
    path = make_report(tmp_path)
    rewrite(path, "### Summary", "### 旁证\n| 100 | 旁证 | ❌ Missing | — | — |\n\n### Summary")
    assert not gap.inspect_report(path).problems


def test_expect_missing(tmp_path, capsys):
    make_report(tmp_path)
    assert gap.main([str(tmp_path), "--expect", "系统甲,系统乙"]) == 1
    assert "系统乙：未产出" in capsys.readouterr().out


def test_out_does_not_write_source_and_totals_are_weighted(tmp_path):
    source = tmp_path / "输入 报告"
    source.mkdir()
    make_report(source)
    make_report(source, "系统乙", [gap.STATUSES[0]] * 3)
    old_summary = source / "SUMMARY.md"
    old_summary.write_text("原始汇总", encoding="utf-8")
    dest = tmp_path / "输出 汇总"
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    assert gap.main([str(source), "--write-summary", "--out", str(dest)]) == 0
    assert {p.name: p.read_bytes() for p in source.iterdir()} == before
    text = (dest / "SUMMARY.md").read_text(encoding="utf-8")
    assert "| 合计 | 8 | 4 | 1 | 1 | 1 | 1 | 87.5% | 64.3% | 2 | 通过 |" in text


def test_default_summary_and_skipped_files(tmp_path):
    make_report(tmp_path)
    for name in ["SUMMARY.md", "回填清单.md", "_notes.md"]:
        (tmp_path / name).write_text("不是报告", encoding="utf-8")
    assert gap.main([str(tmp_path), "--write-summary"]) == 0
    assert "| 合计 | 5 | 1 | 1 | 1 | 1 | 1 | 80.0% | 37.5% | 1 | 通过 |" in (tmp_path / "SUMMARY.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("statuses", [[], [gap.STATUSES[4]]])
def test_zero_denominators(tmp_path, statuses):
    path = make_report(tmp_path, statuses=statuses)
    assert not gap.inspect_report(path).problems


def test_empty_or_missing_directory(tmp_path):
    assert gap.main([str(tmp_path)]) == 1
    assert gap.main([str(tmp_path / "不存在")]) == 1


def test_cli_exit_codes_and_utf8(tmp_path):
    make_report(tmp_path)
    result = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path)], capture_output=True, encoding="utf-8")
    assert result.returncode == 0
    assert "全部通过" in result.stdout
    result = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path), "--expect", "不存在"], capture_output=True, encoding="utf-8")
    assert result.returncode == 1
    assert "未产出" in result.stdout
