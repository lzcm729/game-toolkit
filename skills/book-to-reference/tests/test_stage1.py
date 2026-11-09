"""覆盖审计不能把坏 YAML 或只有支持材料的任务算成通过。"""
import subprocess
import sys

import pytest
import yaml

import bookconf
import stage1


def clean_candidates(workdir):
    path = workdir / "candidates/frameworks.md"
    path.write_text(path.read_text(encoding="utf-8").split("## 故意写坏")[0], encoding="utf-8", newline="\n")


def test_duplicate_task_id_rejected():
    with pytest.raises(ValueError, match="t01-01"):
        stage1.read_tasks("| t01-01 | 第一项 |\n| t01-01 | 第二项 |\n")


def test_coverage_counts(microbook):
    clean_candidates(microbook)
    result = stage1.coverage(bookconf.open_workdir(microbook), microbook)
    assert result.problems == []
    assert result.by_task["t01-01"] == {"framework": 1, "principle": 1, "case": 1, "counter": 0, "term": 1}
    assert result.by_task["t02-01"]["counter"] == 1


def test_coverage_reports_bad_yaml(microbook):
    result = stage1.coverage(bookconf.open_workdir(microbook), microbook)
    assert any("YAML" in problem for problem in result.problems)
    command = [sys.executable, stage1.__file__, "coverage", str(microbook)]
    assert subprocess.run(command, capture_output=True).returncode == 1


def test_unmapped_chapter_rejected(microbook):
    clean_candidates(microbook)
    path = microbook / "candidates/frameworks.md"
    path.write_text(path.read_text(encoding="utf-8").replace("Chapter 1", "Chapter 99"), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="99"):
        stage1.split_candidates(bookconf.open_workdir(microbook), microbook)


def test_non_numeric_chapter_key(microbook):
    clean_candidates(microbook)
    path = microbook / "candidates/frameworks.md"
    path.write_text(path.read_text(encoding="utf-8").replace("Chapter 1 Observe", "Part One 引言"), encoding="utf-8", newline="\n")
    result = stage1.split_candidates(bookconf.open_workdir(microbook), microbook)
    assert list(result) == ["G2", "G1"]
    assert result["G1"]["framework"][0]["id"] == "f1-01"


def test_coverage_requires_executable_candidate(microbook):
    clean_candidates(microbook)
    for name in ("frameworks.md", "principles.md"):
        path = microbook / "candidates" / name
        path.write_text(path.read_text(encoding="utf-8").replace("task_ids: [t01-01]", "task_ids: []"), encoding="utf-8", newline="\n")
    result = stage1.coverage(bookconf.open_workdir(microbook), microbook)
    assert any("t01-01" in problem for problem in result.problems)


def test_split_bad_yaml_does_not_write(microbook):
    directory = microbook / "verify/input"
    before = {p.name: p.read_bytes() for p in directory.iterdir()}
    with pytest.raises(ValueError, match="YAML"):
        stage1.split_candidates(bookconf.open_workdir(microbook), microbook)
    assert before == {p.name: p.read_bytes() for p in directory.iterdir()}


def write_scope(workdir, entries):
    (workdir / "candidates/_scope.yaml").write_text(
        yaml.safe_dump(entries, allow_unicode=True), encoding="utf-8", newline="\n")


@pytest.mark.parametrize("decision", ["reference_only", "out_of_scope"])
def test_scope_disposition_clears_gap(microbook, decision, capsys):
    clean_candidates(microbook)
    overview = microbook / "BOOK_OVERVIEW.md"
    overview.write_text(overview.read_text(encoding="utf-8") + "| t03-02 | 了解灯的象征 | 第 3 章 |\n",
                        encoding="utf-8", newline="\n")
    entry = {"task_id": "t03-02", "decision": decision, "reason": "补读后仅有观点，没有可执行步骤", "pages": [9]}
    write_scope(microbook, [entry])
    result = stage1.coverage(bookconf.open_workdir(microbook), microbook)
    assert result.problems == [] and result.scope == {"t03-02": entry}
    assert stage1.main(["coverage", str(microbook)]) == 0
    assert "t03-02" in capsys.readouterr().out
    assert decision in (microbook / "candidates/_coverage-stage1.md").read_text(encoding="utf-8")


def test_scope_unknown_task_rejected(microbook):
    clean_candidates(microbook)
    write_scope(microbook, [{"task_id": "t99-01", "decision": "reference_only", "reason": "only reference"}])
    result = stage1.coverage(bookconf.open_workdir(microbook), microbook)
    assert any("unknown task_id t99-01" in problem for problem in result.problems)


@pytest.mark.parametrize("reason", [None, "", "  "])
def test_scope_requires_reason(microbook, reason):
    clean_candidates(microbook)
    entry = {"task_id": "t03-01", "decision": "reference_only"}
    if reason is not None:
        entry["reason"] = reason
    write_scope(microbook, [entry])
    assert any("reason" in p for p in stage1.coverage(bookconf.open_workdir(microbook), microbook).problems)


@pytest.mark.parametrize("entries, marker", [
    ([{"task_id": "t03-01", "decision": "skip", "reason": "reason"}], "decision"),
    ([{"task_id": "t03-01", "decision": "reference_only", "reason": "reason"}] * 2, "duplicate"),
    ({"task_id": "t03-01"}, "list"),
    ([None], "mapping"),
])
def test_scope_invalid_records_block(microbook, entries, marker):
    clean_candidates(microbook)
    write_scope(microbook, entries)
    assert any(marker in p for p in stage1.coverage(bookconf.open_workdir(microbook), microbook).problems)
