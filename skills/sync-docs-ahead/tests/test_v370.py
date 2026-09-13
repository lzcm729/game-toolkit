"""3.7 回归：输入失效、语义检查、历史兼容、漂移及两个方向的派活边界。"""
import json
from pathlib import Path
import shlex

import pytest

from test_collect_gap import gap, make_report, rewrite, feature, git_project, write_manifest


@pytest.mark.parametrize("citation,file,line,csv", [
    ("环境与氛围.md rev106:65", "环境与氛围.md", 65, False),
    ("规格.md（revision_id: 106）:65-70", "规格.md", 65, False),
    ("规格.md (revision 106):65–70", "规格.md", 65, False),
    ("规格.md v1.37:65", "规格.md", 65, False),
    ("规格.md:2～6", "规格.md", 2, False),
    ("道具.csv 第2-6行 名称列", "道具.csv", 2, True),
    ("子目录/道具.csv 第 2 至 6 行 名称列", "子目录/道具.csv", 2, True),
    ("`规格.md` rev106:65；第二页.md:2", "规格.md", 65, False),
])
def test_version_and_range_sources(citation, file, line, csv):
    assert gap.source_ref(f"要求（{citation}）") == (file, line, csv)
    assert not gap.mint_key(f"要求（{citation}）").startswith("unknown#")


@pytest.mark.parametrize("citation", [":65", "第2-6行", "规格.md", "规格.md:0", "表.csv 第6-2行", "规格.md:6-2"])
def test_unresolved_sources_strict_fail_legacy_warn(tmp_path, citation):
    path = make_report(tmp_path)
    rewrite(path, "规格.md:1", citation)
    strict, old = gap.inspect_report(path), gap.inspect_report(path, legacy=True)
    assert any("出处无法解析" in p for p in strict.problems)
    assert not old.problems
    assert any("出处无法解析" in p for p in old.warnings)
    assert old.counts == strict.counts


@pytest.mark.parametrize("change", ["missing", "empty", "duplicate"])
def test_code_only_required_only_for_new_reports(tmp_path, change):
    path = make_report(tmp_path)
    if change == "missing":
        rewrite(path, "### Code-only mechanics", "### 旧材料")
    elif change == "empty":
        rewrite(path, "未发现。", "")
    else:
        rewrite(path, "### Code-only mechanics", "### Code-only mechanics\n### Code-only mechanics")
    assert gap.inspect_report(path).problems
    old = gap.inspect_report(path, legacy=True)
    assert not old.problems and any("Code-only" in p for p in old.warnings)


def test_three_review_categories_and_evidence_only(tmp_path):
    path = make_report(tmp_path)
    with path.open("a", encoding="utf-8") as stream:
        stream.write("| 6 | 新增 | ❌ Missing | 要求补行 |\n"
                     "| Code-only | 新增 | — | 机制补项 |\n"
                     "| 其余 | 原状态 | 维持 | 抽验说明 |\n"
                     "| 3 | ✅ Implemented | ✅ Implemented | 证据改了 |\n")
    report = gap.inspect_report(path)
    assert not report.problems
    assert (report.changed, report.added, report.other) == (1, 1, 2)
    summary = gap.summary_text([report], [])
    assert "| 1 | 1 | 2 | 通过 |" in summary


@pytest.mark.parametrize("before,after,expected", [
    ("❌", "**改判 ⚠️ Partial**", (2, 0, 0)),
    ("—（漏项）", "**补行 🔄 Divergent**", (1, 1, 0)),
    ("（原稿无此行）", "✅ Implemented（新增）", (1, 1, 0)),
    ("❌ Missing", "❌ Missing（补证据）", (1, 0, 1)),
    ("⚠️/❌", "维持", (1, 0, 1)),
    ("Code-only", "新增", (1, 0, 1)),
])
def test_legacy_review_spellings_are_classified_without_guessing(tmp_path, before, after, expected):
    path = make_report(tmp_path)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"| 6 | {before} | {after} | 旧式表述 |\n")
    report = gap.inspect_report(path, legacy=True)
    assert not report.problems
    assert (report.changed, report.added, report.other) == expected


def test_single_report_stage_and_neighbor_isolation(tmp_path, capsys):
    path = make_report(tmp_path)
    path.write_text(path.read_text(encoding="utf-8").split("### 复核记录")[0], encoding="utf-8")
    (tmp_path / "系统乙.md").write_text("## 系统乙\n### Features\nunfinished", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert gap.main(["--report", str(path), "--stage", "analysis"]) == 0
    assert "系统乙" not in capsys.readouterr().out
    assert gap.main(["--report", str(path), "--stage", "review"]) == 1
    assert "复核记录" in capsys.readouterr().out
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize("args", [["--stage", "analysis"], ["--report", "one.md", "--write-summary"],
                                  ["--report", "one.md", "--expect", "乙"], ["--legacy", "--stamp-keys"]])
def test_stage_flags_do_not_bypass_final_collection(tmp_path, args):
    with pytest.raises(SystemExit) as exc:
        gap.main(([str(tmp_path)] if "--report" not in args else []) + args)
    assert exc.value.code == 2


def test_drift_precedes_fuzzy_and_keeps_primary_stability():
    old = feature("不可食用（鱼.csv 第13行 用途列）")
    drift = feature("不可食用（鱼.csv 第10行 用途列）")
    rewrite_row = feature("不可食用物（鱼.csv 第13行 用途列）")
    matches = gap.match_rows([rewrite_row, drift], [old])
    assert matches == [(drift, old, 4), (rewrite_row, None, 3)]
    text, notices = gap.transitions_text({"鱼": {"rows": [drift]}}, {"鱼": {"rows": [old]}}, Path("base"))
    assert "锚点漂移 1" in text and "改写 0" in text
    assert "稳定率 0.0%（一级 0 ÷ 基线 1）" in notices[-1]
    assert old["key"] in text and drift["key"] in text


@pytest.mark.parametrize("doc", ["unknown", "doc"])
@pytest.mark.parametrize("counts", [(1, 2), (2, 1), (2, 2)])
def test_drift_ambiguous_or_unknown_does_not_pair(doc, counts):
    old = [feature(key=f"{doc}#old{i}#12345678") for i in range(counts[0])]
    now = [feature(key=f"{doc}#new{i}#12345678") for i in range(counts[1])]
    assert all(level == 3 for _, _, level in gap.match_rows(now, old))


def test_unknown_unique_drift_excluded_and_exact_still_first():
    old = feature(key="unknown#L0#12345678")
    now = feature(key="unknown#r2#12345678")
    assert [m[2] for m in gap.match_rows([now], [old])] == [3, 3]
    same = feature(key="doc#1#12345678")
    drift = feature(key="doc#2#12345678", status=gap.STATUSES[0])
    assert [m[2] for m in gap.match_rows([drift, same], [same])] == [1, 3]


def test_markdown_anchor_drift_with_status_change():
    old = feature(key="shop-token#3.1.2#12345678", status=gap.STATUSES[0])
    now = feature(key="shop-token#2#12345678", status=gap.STATUSES[2])
    assert gap.match_rows([now], [old]) == [(now, old, 4)]
    text = gap.transitions_text({"商店": {"rows": [now]}}, {"商店": {"rows": [old]}}, Path("base"))[0]
    assert "退步 1" in text and "锚点漂移 1" in text and "改写 0" in text


def test_code_only_description_differences_keep_both_refs():
    ref = "CatShopKioskActor.cpp:87-102"
    old = {"rows": [], "code_only_present": True, "code_only": [{"mechanism": "摊位距离证明", "code_ref": ref}]}
    now = {"rows": [], "code_only_present": True, "code_only": [{"mechanism": "到摊位的交互距离校验", "code_ref": ref}]}
    text = gap.transitions_text({"商店": now}, {"商店": old}, Path("base"))[0]
    assert text.count(ref) == 2
    assert "描述差异、待核机制变化" in text
    assert "| 新增 |" not in text and "| 消失 |" not in text
    assert "| 本轮独有描述 | 到摊位的交互距离校验 |" in text
    assert "| 基线独有描述 | 摊位距离证明 |" in text


def test_legacy_mechanism_ref_enrichment_uses_only_same_description(tmp_path, capsys):
    path = make_report(tmp_path)
    rewrite(path, "未发现。", "| 机制 | code_ref | 文档 | 问题 |\n|---|---|---|---|\n| 相同描述 | src/a.cpp:8 | — | 待核 |")
    data = gap.report_data(path, gap.Documents())
    data["code_only"] = ["相同描述", "仅在旧RUN中"]
    (tmp_path / "RUN.json").write_text(json.dumps({"schema_version": 1, "systems": {path.stem: data}}), encoding="utf-8")
    run = gap.load_baseline(tmp_path, gap.Documents())
    assert run["systems"][path.stem]["code_only"] == [
        {"mechanism": "相同描述", "code_ref": "src/a.cpp:8"}, {"mechanism": "仅在旧RUN中", "code_ref": None}]
    assert "旧 RUN" in capsys.readouterr().err


def plan_for(project):
    root, docs, baseline, config, run, _ = project
    return gap.make_plan(config, run, baseline, root, gap.Documents(docs), [], [])


def refresh_snapshot(project):
    root, docs, baseline, config, run, _ = project
    path = baseline / "系统甲.md"
    run["systems"]["系统甲"] = gap.collect_system(path, gap.inspect_report(path), gap.Documents(docs), config, root)


def test_stale_manifest_body_change_invalidates(git_project):
    root, docs, baseline, config, run, _ = git_project
    manifest = (docs / "_manifest.json").read_bytes()
    assert plan_for(git_project)["carry"] == ["系统甲"]
    (docs / "规格.md").write_text("# 1 规则\n正文改变但 manifest 没改", encoding="utf-8")
    assert (docs / "_manifest.json").read_bytes() == manifest
    plan = plan_for(git_project)
    assert plan["rerun"] == ["系统甲"]
    assert "设计文件内容/身份或集合指纹与基线不同" in plan["reasons"]["系统甲"]


def test_revision_metadata_alone_does_not_invalidate(git_project):
    root, docs, *_ = git_project
    before = (docs / "规格.md").read_bytes()
    write_manifest(docs, revision=999)
    assert (docs / "规格.md").read_bytes() == before
    assert plan_for(git_project)["carry"] == ["系统甲"]


def test_no_manifest_can_prove_unchanged_actual_input(git_project):
    (git_project[1] / "_manifest.json").unlink()
    refresh_snapshot(git_project)
    assert plan_for(git_project)["carry"] == ["系统甲"]


@pytest.mark.parametrize("kind", ["refs", "rulings_ledger", "decision_ledger", "engineering_log", "owners", "scan_refs"])
def test_reference_and_ledger_bytes_invalidate(git_project, kind):
    root, docs, baseline, config, run, _ = git_project
    path = (docs if kind == "refs" else root) / "参考.md"
    path.write_text("旧依据", encoding="utf-8")
    if kind == "refs":
        config["systems"][0]["refs"] = ["参考.md"]
    elif kind == "scan_refs":
        rewrite(baseline / "系统甲.md", '"refs": []', '"refs": ["参考.md"]')
    else:
        (root / "game-toolkit.yaml").write_text(f"doc_feedback:\n  {kind}: 参考.md\n", encoding="utf-8")
    refresh_snapshot(git_project)
    assert plan_for(git_project)["carry"] == ["系统甲"]
    path.write_text("新依据", encoding="utf-8")
    assert plan_for(git_project)["rerun"] == ["系统甲"]
    path.unlink()
    assert plan_for(git_project)["rerun"] == ["系统甲"]


@pytest.mark.parametrize("change", ["add", "delete", "rename"])
def test_document_glob_membership_invalidates(git_project, change):
    docs, config = git_project[1], git_project[3]
    config["systems"][0]["docs"] = ["*.md"]
    refresh_snapshot(git_project)
    if change == "add":
        (docs / "新页.md").write_text("新页", encoding="utf-8")
    elif change == "delete":
        (docs / "规格.md").unlink()
    else:
        (docs / "规格.md").rename(docs / "另一个名字.md")
    assert plan_for(git_project)["rerun"] == ["系统甲"]


def test_old_run_missing_fingerprints_is_conservative(git_project):
    data = git_project[4]["systems"]["系统甲"]
    del data["inputs"]
    plan = plan_for(git_project)
    assert plan["carry"] == [] and plan["rerun"] == ["系统甲"]
    assert any("旧 RUN 缺少实际输入指纹" in r for r in plan["reasons"]["系统甲"])


def test_actual_extra_code_scope_invalidates_on_committed_change(git_project):
    baseline, snapshot = git_project[2], git_project[5]
    rewrite(baseline / "系统甲.md", '"code": ["code.py"]', '"code": ["code.py", "other.py"]')
    refresh_snapshot(git_project)
    assert plan_for(git_project)["carry"] == ["系统甲"]
    snapshot(other="changed outside configured code hints")
    plan = plan_for(git_project)
    assert plan["rerun"] == ["系统甲"] and "代码路径有已提交变化" in plan["reasons"]["系统甲"]


def test_uncovered_evidence_expands_to_whole_project(git_project):
    path = git_project[2] / "系统甲.md"
    rewrite(path, "code.py:1", "other.py:1")
    refresh_snapshot(git_project)
    inputs = git_project[4]["systems"]["系统甲"]["inputs"]
    assert inputs["code"] == ["."]
    assert "other.py" in inputs["notes"][0]
    git_project[5](other="evidence changed")
    assert "代码路径有已提交变化" in plan_for(git_project)["reasons"]["系统甲"]


@pytest.mark.parametrize("body", ["", '{"code": [], "refs": ["../outside.md"]}', "invalid json"])
def test_missing_or_invalid_actual_dependencies_cannot_carry(git_project, body):
    path = git_project[2] / "系统甲.md"
    original = '```gap-inputs\n{"code": ["code.py"], "refs": []}\n```'
    rewrite(path, original, f"```gap-inputs\n{body}\n```" if body else "")
    refresh_snapshot(git_project)
    assert git_project[4]["systems"]["系统甲"]["inputs"]["code"] == ["."]
    assert plan_for(git_project)["rerun"] == ["系统甲"]


def test_uncommitted_code_cannot_carry(git_project):
    (git_project[0] / "code.py").write_text("uncommitted change", encoding="utf-8")
    assert plan_for(git_project)["rerun"] == ["系统甲"]
    assert "代码依赖有未提交或未跟踪修改" in plan_for(git_project)["reasons"]["系统甲"]


def test_unresolved_external_dependencies_cannot_carry(git_project):
    path = git_project[2] / "系统甲.md"
    rewrite(path, '"refs": []}', '"refs": [], "unresolved": ["外部引擎适配源码"]}')
    refresh_snapshot(git_project)
    plan = plan_for(git_project)
    assert plan["rerun"] == ["系统甲"]
    assert "实际依赖未能记录，保守重跑：外部引擎适配源码" in plan["reasons"]["系统甲"]


def test_historical_replay_preserves_saved_keys_and_never_mints_inputs(tmp_path):
    source, output = tmp_path / "source", tmp_path / "out"
    source.mkdir()
    path = make_report(source)
    data = gap.report_data(path, gap.Documents())
    # 模拟历史解析器把明确版本出处记为 unknown；回放不能用新解析器重铸历史键。
    data["rows"][0]["key"] = "unknown#L0#12345678"
    rewrite(path, "规格.md:1", "规格.md rev106:1")
    (source / "RUN.json").write_text(json.dumps({"schema_version": 1, "project_head": "original-head",
        "exported_at": "original-date", "systems": {path.stem: data}}), encoding="utf-8")
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    assert gap.main([str(source), "--legacy", "--baseline", str(source), "--write-summary", "--out", str(output)]) == 0
    saved = gap.read_json(output / "RUN.json")["systems"][path.stem]
    assert gap.read_json(output / "RUN.json")["project_head"] == "original-head"
    assert gap.read_json(output / "RUN.json")["exported_at"] == "original-date"
    assert saved["rows"] == data["rows"]
    assert saved["validation_version"] == 1 and "inputs" not in saved
    assert before == {p.name: p.read_bytes() for p in source.iterdir()}
    assert "稳定率 100.0%" in (output / "TRANSITIONS.md").read_text(encoding="utf-8")
    assert "警告" in (output / "SUMMARY.md").read_text(encoding="utf-8")


def test_legacy_flag_does_not_relax_new_run(tmp_path):
    path = make_report(tmp_path)
    assert gap.main([str(tmp_path), "--write-summary"]) == 0
    rewrite(path, "规格.md:1", ":1")
    assert gap.main([str(tmp_path), "--legacy"]) == 1


@pytest.mark.parametrize("field", ["scan", "code", "code_dirty", "project_inputs", "refs", "scan_refs", "docs"])
def test_partial_input_records_cannot_carry(git_project, field):
    del git_project[4]["systems"]["系统甲"]["inputs"][field]
    assert plan_for(git_project)["rerun"] == ["系统甲"]


@pytest.mark.parametrize("path,patterns,expected", [
    ("src/core/a.py", ["src/core/"], True), ("src/core/a.py", ["src/**"], True),
    ("other/src/a.py", ["src/**"], False), ("src/a.py", ["src/**/*.py"], True),
    ("src/deep/a.py", ["src/*.py"], False), ("src/a.py", ["."], True),
    ("src/ab.py", ["src/a?.py"], True),
])
def test_evidence_scope_path_matching(path, patterns, expected):
    assert gap.path_covered(path, patterns) is expected


@pytest.mark.parametrize("relative", ["SKILL.md", "examples/README.md"])
def test_documented_carry_command_executes_with_project_root(tmp_path, relative):
    skill = Path(__file__).resolve().parents[1]
    line = next(line for line in (skill / relative).read_text(encoding="utf-8").splitlines()
                if line.startswith("python ") and "--carry" in line)
    assert "--project-root" in shlex.split(line)
    root, baseline, output = tmp_path / "project", tmp_path / "project/base", tmp_path / "project/output"
    baseline.mkdir(parents=True)
    make_report(baseline, "系统乙")
    # 将文档示例占位参数实例化，验证路径确实传进 carry，而不是只检查提示词中的文字。
    tokens = shlex.split(line.split("collect_gap.py", 1)[1])
    values = {"--baseline": str(baseline), "--systems": "系统乙", "--project-root": str(root)}
    args = ["--carry"]
    for key in values:
        assert key in tokens
        args.extend([key, values[key]])
    assert gap.main([*args, str(output)]) == 0
    saved = gap.read_json(output / "RUN.json")["systems"]["系统乙"]
    assert saved["carried_from"] == "base"


def test_synthesis_owner_gate_contract():
    # 提示词规则的静态护栏：防止后续编辑移除派活前置；语义场景评估另记在实施报告，不冒充自动执行结果。
    skill = Path(__file__).resolve().parents[1]
    text = (skill / "references/synthesis-prompt.md").read_text(encoding="utf-8")
    gate = text.split("## 派活前的属主依据核对", 1)[1].split("## 落盘五节", 1)[0]
    assert all(word in gate for word in ("属主规格", "现行裁决", "补实现／删除／属主不承诺", "冲突未解决不得进入第四节"))
    assert "不能从「未实现」反推「已裁定删除」" in gate
    assert "描述差异、待核机制变化" in gate


def test_reverse_candidate_review_contract():
    skill = Path(__file__).resolve().parents[2]
    text = (skill / "sync-code-ahead/SKILL.md").read_text(encoding="utf-8")
    gate = text.split("### 阶段 3b：", 1)[1].split("### 阶段 4：", 1)[0]
    assert all(word in gate for word in ("全部旧 pending", "固定 H", "属主设计", "目标文档", "rulings_ledger",
                                         "获准补文档", "待设计判断", "应回代码修正", "保留 pending", "不得进入阶段 6"))
    assert "仅执行阶段 3b 获准补文档的项" in text
    assert '如果代码实现与设计意图有差异，在文档中注明"基于代码同步"' not in text
