"""汇总错误必须阻断；复核输入去判断，原始复核仍要可追溯。"""
import subprocess
import sys

import pytest
import yaml

import bookconf
import verify_units as vu


def dump(path, data):
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=200), encoding="utf-8", newline="\n")


def test_recheck_input_strips_verdicts(microbook):
    cfg = bookconf.open_workdir(microbook)
    path = vu.recheck_input(cfg, microbook, "R2", ["u01-01"])
    text = path.read_text(encoding="utf-8")
    assert all(word not in text for word in ("decision", "decision_reason", "gaps", "V1"))
    unit, = yaml.safe_load(text)["units"]
    assert set(unit) == set(vu.KEEP)
    assert unit["unit_id"] == "u01-01"
    assert not path.read_bytes().count(b"\r")


def test_apply_recheck_idempotent(microbook):
    cfg = bookconf.open_workdir(microbook)
    path = microbook / "verify/out/G1.yaml"
    before = path.read_bytes()
    assert vu.apply_recheck(cfg, microbook, None, True)
    assert path.read_bytes() == before
    assert vu.apply_recheck(cfg, microbook, None, False)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["units"][0]["decision"] == "reference"
    assert data["coverage"]["t01-01"]["status"] == "reference_only"
    after = path.read_bytes()
    assert vu.apply_recheck(cfg, microbook, None, False) == []
    assert path.read_bytes() == after
    backups = list((microbook / "verify/out").glob("*.pre-recheck.bak"))
    assert len(backups) == 1 and backups[0].read_bytes() == before


def test_aggregate_problems_block(microbook):
    path = microbook / "verify/out/G1.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    del data["candidate_disposition"]["f1-01"]
    dump(path, data)
    result = vu.aggregate(bookconf.open_workdir(microbook), microbook)
    assert any("disposition missing" in problem for problem in result.problems)
    command = [sys.executable, vu.__file__, "aggregate", str(microbook)]
    assert subprocess.run(command, capture_output=True).returncode == 1


def test_show_includes_raw_recheck(microbook):
    text = vu.show(bookconf.open_workdir(microbook), microbook, ["u01-01"])
    assert "reconstructed" in text and "steps:" in text
    assert "V1_source_sufficiency" in text
    assert "c-01" in text and "两次影子比较" in text
    assert "ce-01" in text and "同时移动两片挡板" in text
    assert "g-01" in text and "稳定影子" in text


def test_aggregate_success_and_determinism(microbook):
    cfg = bookconf.open_workdir(microbook)
    result = vu.aggregate(cfg, microbook)
    assert result.problems == []
    assert result.counts["verified"] == 3
    names = ["verified.md", "references.md", "needs-review.md", "coverage-audit.md", "verify/_flags.md"]
    before = [(microbook / name).read_bytes() for name in names]
    vu.aggregate(cfg, microbook)
    assert before == [(microbook / name).read_bytes() for name in names]
    assert all(b"\r" not in text for text in before)


@pytest.mark.parametrize("defect", ["duplicate", "coverage"])
def test_aggregate_reports_other_integrity_errors(microbook, defect):
    path = microbook / "verify/out/G1.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if defect == "duplicate":
        data["units"].append(data["units"][0].copy())
    else:
        del data["coverage"]["t01-01"]
    dump(path, data)
    problems = vu.aggregate(bookconf.open_workdir(microbook), microbook).problems
    assert any(("duplicate unit" if defect == "duplicate" else "without coverage") in problem for problem in problems)


def test_apply_unknown_unit_does_not_write(microbook):
    path = microbook / "verify/recheck/out/R1.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["units"][0]["unit_id"] = "u99-99"
    dump(path, data)
    before = (microbook / "verify/out/G1.yaml").read_bytes()
    with pytest.raises(ValueError, match="u99-99"):
        vu.apply_recheck(bookconf.open_workdir(microbook), microbook, None, False)
    assert (microbook / "verify/out/G1.yaml").read_bytes() == before


def test_recheck_overlapping_batches_are_idempotent(microbook):
    record = yaml.safe_load((microbook / "verify/recheck/out/R1.yaml").read_text(encoding="utf-8"))
    record["batch"] = "R2"
    record["units"][0]["decision_after"] = "needs_review"
    dump(microbook / "verify/recheck/out/R2.yaml", record)
    cfg = bookconf.open_workdir(microbook)
    assert len(vu.apply_recheck(cfg, microbook, None, False)) == 2
    path = microbook / "verify/out/G1.yaml"
    before = path.read_bytes()
    assert vu.apply_recheck(cfg, microbook, None, False) == []
    assert vu.apply_recheck(cfg, microbook, ["R1"], False) == []
    assert path.read_bytes() == before
