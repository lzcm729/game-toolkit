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


# 3.6：临时镜像、基线与 Git 对象；不改仓库历史或真实项目。
import json
import os
import shutil


def write_manifest(root, revision=1, sheets=None):
    data = {"exported_at": "2026-01-01T00:00:00", "docs": [
        {"file": "规格.md", "node_token": "doc-token", "revision_id": revision}], "sheets": sheets or []}
    (root / "_manifest.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8-sig")
    return data


def feature(requirement="自动保存数据（规格.md:2）", status=None, docs=None, key=None):
    return {"#": "1", "key": key or gap.mint_key(requirement, docs), "status": status or gap.STATUSES[0],
            "requirement": requirement, "match_text": gap.normalized(gap.split_requirement(requirement)[0])}


def test_key_determinism_numeric_and_punctuation_insensitivity():
    one = gap.mint_key("消耗 10.5 点，恢复 ２ 秒！（规格.md:20）")
    assert one == gap.mint_key("消耗99点恢复3秒（规格.md:500）")
    assert one == gap.mint_key("消耗 10.5 点，恢复 ２ 秒！（规格.md:20）")
    assert one != gap.mint_key("消耗点恢复速度（规格.md:20）")


@pytest.mark.parametrize("heading,anchor", [("# 1. 一次流程", "1"), ("## 4.4 消耗", "4.4"),
                                           ("### 2.3 抽取", "2.3"), ("## 无 编号：标题！", "无编号标题")])
def test_markdown_anchors(tmp_path, heading, anchor):
    (tmp_path / "规格.md").write_text(f"# 0 父标题\n{heading}\n正文\n", encoding="utf-8-sig")
    assert gap.mint_key("要求（规格.md:3）", gap.Documents(tmp_path)).split("#")[1] == anchor


def test_anchor_stays_after_line_drift_and_skips_fenced_heading(tmp_path):
    file = tmp_path / "规格.md"
    file.write_text("## 2.3 规则\n```md\n# 9 示例\n```\n正文\n", encoding="utf-8")
    old = gap.mint_key("要求（规格.md:5）", gap.Documents(tmp_path))
    file.write_text("新增文字\n\n" + file.read_text(encoding="utf-8"), encoding="utf-8")
    assert old == gap.mint_key("要求（规格.md:7）", gap.Documents(tmp_path))
    assert "#2.3#" in old


def test_missing_file_and_no_heading_are_l0(tmp_path):
    (tmp_path / "规格.md").write_text("正文\n正文", encoding="utf-8")
    docs = gap.Documents(tmp_path)
    assert "#L0#" in gap.mint_key("要求（规格.md:2）", docs)
    assert "#L0#" in gap.mint_key("要求（不存在.md:22）", docs)


@pytest.mark.parametrize("citation,anchor", [("表甲.csv 第1行 名字列、描述列", "r1"),
                                            ("表乙.csv 第 14 行 作用列", "r14")])
def test_csv_anchor(citation, anchor):
    assert f"#{anchor}#" in gap.mint_key(f"要求（{citation}）")


def test_manifest_identity_docs_sheets_and_first_citation(tmp_path):
    write_manifest(tmp_path, sheets=[{"file": "子目录/表.csv", "node_token": "sheet-token", "revision": 7}])
    docs = gap.Documents(tmp_path)
    assert gap.mint_key("要求（规格.md:57、97；第二页.md:9）", docs).startswith("doc-token#")
    assert gap.mint_key("要求（表.csv 第1行 名字列）", docs).startswith("sheet-token#r1#")
    assert gap.mint_key("要求（规格.md:2）").startswith("规格#")
    assert gap.mint_key("要求（未知.md:2）", docs).startswith("未知#")


def test_nested_citation_and_windows_relative_path(tmp_path):
    (tmp_path / "子目录").mkdir()
    (tmp_path / "子目录/规格（新版）.md").write_text("## 1.2 规则\n正文", encoding="utf-8")
    text = "要求（子目录\\规格（新版）.md:2「说明（嵌套）」；其他.md:9）"
    assert gap.split_requirement(text)[0] == "要求"
    assert gap.mint_key(text, gap.Documents(tmp_path)).startswith("规格（新版）#1.2#")


def test_three_matching_levels():
    old = [feature(), feature("存储用户资料（规格.md:2）"), feature("退出（别页.md:1）")]
    now = [feature(), feature("存储用户信息（规格.md:2）"), feature("启动（新页.md:1）")]
    matches = gap.match_rows(now, old)
    assert [m[2] for m in matches] == [1, 2, 3, 3]
    assert matches[-1][0] is None
    assert matches[-2][1] is None


def test_similarity_threshold_boundary():
    old, now = feature("abcde（规格.md:1）"), feature("abcxy（规格.md:1）")
    assert gap.match_rows([now], [old], .6)[0][2] == 2
    assert [m[2] for m in gap.match_rows([now], [old], .60001)] == [3, 3]


def test_baseline_row_once_greedy_and_exact_priority():
    old = feature("abcdefghij（规格.md:1）")
    near = feature("abcdefghiX（规格.md:1）")
    far = feature("abcdefgXYZ（规格.md:1）")
    matched = gap.match_rows([far, near], [old])
    assert matched[0] == (near, old, 2)
    assert matched[1] == (far, None, 3)
    assert gap.match_rows([near, old], [old])[0] == (old, old, 1)
    duplicate = gap.match_rows([old, old], [old])
    assert [m[2] for m in duplicate] == [1, 3]


def test_transition_categories_mechanics_carried_and_stability():
    old_statuses = [gap.STATUSES[i] for i in (0, 0, 2, 3, 1, 4)]
    new_statuses = [gap.STATUSES[i] for i in (0, 2, 0, 0, 0, 0)]
    old = [feature(status=s, key=f"doc#section#{i:08x}") for i, s in enumerate(old_statuses)]
    now = [feature(status=s, key=f"doc#section#{i:08x}") for i, s in enumerate(new_statuses)]
    now += [feature("新要求（新文件.md:1）")]
    previous = {"甲": {"rows": old, "code_only_present": True, "code_only": ["已移除机制"]}, "乙": {"rows": []}}
    current = {"甲": {"rows": now, "code_only_present": True, "code_only": ["新增机制"], "carried_from": "旧目录"}, "乙": {"rows": []}}
    text, notices = gap.transitions_text(current, previous, Path("旧目录"))
    assert "未变 1／退步 1／修复 3／其他变化 1" in text
    assert "稳定率 100.0%（一级 6 ÷ 基线 6）" in notices[-1]
    for part in ("## 甲", "## 乙", "| 键 |", "①", "③", "## 沿用基线的系统", "基线报告没有该节",
                 "| 新增 | 新增机制 |", "| 消失 | 已移除机制 |"):
        assert part in text
    assert "doc#section#00000000 |" not in text  # 未变行不进明细


def test_transition_rewrite_disappearance_and_zero_denominator():
    old = {"甲": {"rows": [feature("存储用户资料（规格.md:1）")]}, "乙": {"rows": [feature()]}}
    now = {"甲": {"rows": [feature("存储用户信息（规格.md:1）")]}}
    text, notices = gap.transitions_text(now, old, Path("基线"))
    assert "改写 1" in text and "消失 1" in text and "②" in text and "③" in text
    assert "稳定率 0.0%" in notices[-1]
    assert "不适用" in gap.transitions_text({}, {}, Path("基线"))[0]


def test_run_fields_full_matching_text_and_custom_manifest(tmp_path):
    reports, docs, output = tmp_path / "reports", tmp_path / "docs", tmp_path / "out"
    reports.mkdir()
    docs.mkdir()
    (docs / "规格.md").write_text("# 1 规则\n正文", encoding="utf-8")
    manifest = write_manifest(docs)
    (docs / "_manifest.json").rename(tmp_path / "mirror.json")
    config = tmp_path / "config.yaml"
    config.write_text('$schema_version: 1\ndocs_root: docs\nmanifest: mirror.json\nsystems:\n  - name: 系统甲\n    docs: [规格.md]\n    scope: 全篇\n    code: [src/**]\n', encoding="utf-8-sig")
    path = make_report(reports)
    rewrite(path, "需求（", "长要求" * 40 + "（")
    assert gap.main([str(reports), "--write-summary", "--out", str(output), "--config", str(config), "--project-root", str(tmp_path)]) == 0
    run = gap.read_json(output / "RUN.json")
    assert run["schema_version"] == 1 and run["output_dir"] == str(reports.resolve())
    assert run["exported_at"] == manifest["exported_at"] and run["project_head"] is None and run["baseline"] is None
    data = run["systems"]["系统甲"]
    assert data["docs"] == [{"file": "规格.md", "revision_id": 1}]
    assert data["code"] == ["src/**"] and data["total"] == 5
    assert all(data[k] == 1 for k in ("implemented", "partial", "missing", "divergent", "unverifiable"))
    assert data["carried_from"] is None
    assert len(data["rows"][0]["requirement"]) == 80 and len(data["rows"][0]["match_text"]) == 120


def test_baseline_run_preferred_and_legacy_self_compare_readonly(tmp_path, capsys):
    source, output = tmp_path / "source", tmp_path / "out"
    source.mkdir()
    make_report(source)
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    assert gap.main([str(source), "--write-summary", "--out", str(output), "--baseline", str(source)]) == 0
    assert "稳定率 100.0%" in capsys.readouterr().out
    assert {p.name: p.read_bytes() for p in source.iterdir()} == before
    assert "未变 5" in (output / "TRANSITIONS.md").read_text(encoding="utf-8")
    # RUN 独立保存完整迁移所需信息，不依赖基线目录内仍有 Markdown。
    run = gap.load_baseline(output, gap.Documents())
    assert len(run["systems"]["系统甲"]["rows"]) == 5
    assert run["baseline"] == str(source.resolve())


@pytest.fixture
def git_project(tmp_path):
    if not shutil.which("git"):
        pytest.skip("git 不可用")
    root = tmp_path / "project"
    root.mkdir()
    env = {**os.environ, "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}

    def git(*args, input=None):
        result = subprocess.run(["git", "-C", str(root), *args], input=input.encode("utf-8") if input is not None else None,
                                capture_output=True, env=env)
        assert result.returncode == 0, result.stderr
        return result.stdout.decode("utf-8").strip()

    git("init")

    def snapshot(code="first", other="first"):
        # plumbing 造提交对象与 detached HEAD，不调用 add / commit / checkout，不建分支。
        files = {"code.py": code, "other.py": other}
        entries = []
        for name, content in sorted(files.items()):
            blob = git("hash-object", "-w", "--stdin", input=content)
            entries.append(f"100644 blob {blob}\t{name}\n")
            (root / name).write_text(content, encoding="utf-8")
        tree = git("mktree", input="".join(entries))
        commit = git("commit-tree", tree, input="test snapshot\n")
        git("update-ref", "--no-deref", "HEAD", commit)
        return commit

    head = snapshot()
    docs = root / "design"
    docs.mkdir()
    (docs / "规格.md").write_text("# 1 规则\n正文", encoding="utf-8")
    write_manifest(docs)
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    report = make_report(baseline)
    system = {"name": "系统甲", "docs": ["规格.md"], "refs": [], "scope": "全篇", "code": ["code.py"]}
    config = {"$schema_version": 1, "docs_root": "design", "systems": [system]}
    data = gap.collect_system(report, gap.inspect_report(report), gap.Documents(docs), config)
    run = gap.run_record(baseline, {"系统甲": data}, gap.Documents(docs), root, None)
    assert run["project_head"] == head
    (baseline / "RUN.json").write_text(json.dumps(run, ensure_ascii=False), encoding="utf-8-sig")
    return root, docs, baseline, config, run, snapshot


def test_plan_carry_and_unrelated_committed_code(git_project):
    root, docs, baseline, config, run, snapshot = git_project
    assert gap.make_plan(config, run, baseline, root, gap.Documents(docs), [], [])["carry"] == ["系统甲"]
    snapshot(other="changed")
    assert gap.make_plan(config, run, baseline, root, gap.Documents(docs), [], [])["carry"] == ["系统甲"]
    del run["systems"]["系统甲"]["scope"]
    del run["systems"]["系统甲"]["refs"]
    assert gap.make_plan(config, run, baseline, root, gap.Documents(docs), [], [])["carry"] == ["系统甲"]


@pytest.mark.parametrize("change,reason", [("code", "已提交变化"), ("docs", "revision"),
                                          ("force", "--force"), ("new", "没有该系统"), ("missing_head", "project_head")])
def test_plan_rerun_reasons(git_project, change, reason):
    root, docs, baseline, config, run, snapshot = git_project
    force = []
    if change == "code":
        snapshot(code="changed")
    elif change == "docs":
        write_manifest(docs, revision=2)
    elif change == "force":
        force = ["系统甲"]
    elif change == "new":
        run["systems"] = {}
    else:
        run["project_head"] = None
    plan = gap.make_plan(config, run, baseline, root, gap.Documents(docs), force, [])
    assert plan["rerun"] == ["系统甲"] and reason in "；".join(plan["reasons"]["系统甲"])


@pytest.mark.parametrize("missing,reason", [("config", "无配置"), ("baseline", "无基线"),
                                           ("run", "没有 RUN.json"), ("git", "不是 git 仓库")])
def test_plan_fallbacks(git_project, missing, reason):
    root, docs, baseline, config, run, _ = git_project
    if missing == "config":
        config = {}
    elif missing == "baseline":
        baseline, run = None, None
    elif missing == "run":
        (baseline / "RUN.json").unlink()
        run = gap.load_baseline(baseline, gap.Documents(docs))
    else:
        # Git 在子目录也有效，改用仓库之外的基线目录。
        root = baseline
    plan = gap.make_plan(config, run, baseline, root, gap.Documents(docs), [], ["系统甲"])
    assert plan["rerun"] == ["系统甲"] and reason in "；".join(plan["reasons"]["系统甲"])


def test_plan_cli_json_and_auto_config(git_project, capsys):
    root, docs, baseline, config, _, _ = git_project
    (root / "gap-analysis.config.yaml").write_text(gap.yaml.safe_dump(config, allow_unicode=True), encoding="utf-8-sig")
    assert gap.main(["--plan", "--baseline", str(baseline), "--project-root", str(root), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["carry"] == ["系统甲"]


def test_plan_missing_revision_and_deleted_document(git_project):
    root, docs, baseline, config, run, _ = git_project
    (docs / "_manifest.json").unlink()
    plan = gap.make_plan(config, run, baseline, root, gap.Documents(docs), [], [])
    assert "manifest 缺少版本" in "；".join(plan["reasons"]["系统甲"])
    (docs / "规格.md").unlink()
    assert gap.make_plan(config, run, baseline, root, gap.Documents(docs), [], [])["rerun"] == ["系统甲"]


def test_carry_marker_record_and_refuses_overwrite(git_project, tmp_path):
    root, docs, baseline, config, run, _ = git_project
    output = tmp_path / "output"
    original = (baseline / "系统甲.md").read_bytes()
    assert gap.main(["--carry", "--baseline", str(baseline), "--systems", "系统甲", str(output)]) == 0
    path = output / "系统甲.md"
    assert path.read_text(encoding="utf-8").splitlines()[1].startswith("> 沿用基线 ")
    assert not gap.inspect_report(path).problems
    carried = gap.read_json(output / "RUN.json")["systems"]["系统甲"]
    assert carried["carried_from"] == str(baseline.resolve()) and carried["rows"] == run["systems"]["系统甲"]["rows"]
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    assert gap.main(["--carry", "--baseline", str(baseline), "--systems", "系统甲", str(output)]) == 1
    assert {p.name: p.read_bytes() for p in output.iterdir()} == before
    assert (baseline / "系统甲.md").read_bytes() == original
    assert gap.main([str(output), "--write-summary", "--baseline", str(baseline), "--project-root", str(root)]) == 0
    assert gap.read_json(output / "RUN.json")["systems"]["系统甲"]["docs"] == carried["docs"]
    rewrite(path, "需求（", "改写后的需求（")
    assert gap.main([str(output), "--write-summary", "--baseline", str(baseline), "--project-root", str(root)]) == 1


def test_carry_preflight_and_repeated_carry_has_single_marker(tmp_path):
    base, first, second = (tmp_path / name for name in ("base", "first", "second"))
    base.mkdir()
    make_report(base)
    assert gap.main(["--carry", "--baseline", str(base), "--systems", "系统甲,不存在", str(first)]) == 1
    assert not first.exists()
    gap.carry_reports(first, base, ["系统甲"], gap.Documents())
    gap.carry_reports(second, first, ["系统甲"], gap.Documents())
    assert (second / "系统甲.md").read_text(encoding="utf-8").count("> 沿用基线 ") == 1
    assert not gap.inspect_report(second / "系统甲.md").problems


def test_stamp_six_columns_idempotent_preserves_escaped_pipes(tmp_path):
    path = make_report(tmp_path, bom=True)
    rewrite(path, "需求（", r"需求 a\|b（")
    before = path.read_text(encoding="utf-8").split("### Summary", 1)[1]
    assert gap.main([str(tmp_path), "--stamp-keys"]) == 0
    assert not gap.inspect_report(path).problems
    text = path.read_text(encoding="utf-8")
    assert "| Notes | Key |" in text and r"需求 a\|b" in text
    assert text.split("### Summary", 1)[1] == before
    assert gap.main([str(tmp_path), "--stamp-keys"]) == 0
    assert path.read_text(encoding="utf-8") == text


def test_refuse_writing_baseline_and_invalid_config(tmp_path):
    make_report(tmp_path)
    assert gap.main([str(tmp_path), "--baseline", str(tmp_path), "--stamp-keys"]) == 1
    assert gap.main([str(tmp_path), "--baseline", str(tmp_path), "--write-summary"]) == 1
    config = tmp_path / "bad.yaml"
    config.write_text('$schema_version: 1\nsystems:\n  - name: ../越界\n    scope: 全篇\n', encoding="utf-8")
    assert gap.main(["--plan", "--config", str(config)]) == 1


def test_manifest_embedded_sheets_provide_identity_and_version(tmp_path):
    """docx 内嵌表在 manifest 的 embedded_sheets 里，也要能给版本，否则含内嵌表的系统永远「缺少版本」重跑。"""
    manifest = {"exported_at": "2026-01-01T00:00:00", "docs": [{"file": "规格.md", "node_token": "doc-token", "revision_id": 4}],
                "sheets": [], "embedded_sheets": [{"file": "规格.embedded/abc.csv", "token": "tok", "sheet_id": "abc", "revision": 5, "header": ["a"]}]}
    (tmp_path / "_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    docs = gap.Documents(tmp_path)
    assert docs.entry("规格.embedded/abc.csv")["revision"] == 5
    assert docs.entry("abc.csv")["revision"] == 5
    assert gap.mint_key("要求（abc.csv 第2行 a列）", docs).startswith("abc#r2#")


def test_explicit_docs_root_manifest_wins_over_config_manifest(tmp_path, capsys):
    """--docs-root 指向历史快照时，用快照自带的 _manifest.json，不用配置里指向当前镜像的那份。"""
    root = tmp_path / "project"
    (root / "current").mkdir(parents=True)
    (root / "snapshot").mkdir()
    for folder, rev, stamp in (("current", 9, "2026-02-02T00:00:00"), ("snapshot", 3, "2026-01-01T00:00:00")):
        (root / folder / "规格.md").write_text("# 1 规则\n正文\n正文", encoding="utf-8")
        (root / folder / "_manifest.json").write_text(json.dumps({"exported_at": stamp, "docs": [{"file": "规格.md", "node_token": "doc-token", "revision_id": rev}], "sheets": []}, ensure_ascii=False), encoding="utf-8")
    (root / "gap-analysis.config.yaml").write_text(
        "$schema_version: 1\ndocs_root: current\nmanifest: current/_manifest.json\nsystems:\n  - name: 系统甲\n    docs: [规格.md]\n    refs: []\n    scope: 全篇\n    code: []\n", encoding="utf-8")
    reports = tmp_path / "reports"
    reports.mkdir()
    make_report(reports)
    out = tmp_path / "out"
    assert gap.main([str(reports), "--write-summary", "--out", str(out), "--docs-root", str(root / "snapshot"), "--project-root", str(root)]) == 0
    run = json.loads((out / "RUN.json").read_text(encoding="utf-8"))
    assert run["exported_at"] == "2026-01-01T00:00:00"
    assert any(d.get("revision_id") == 3 for d in run["systems"]["系统甲"]["docs"])
