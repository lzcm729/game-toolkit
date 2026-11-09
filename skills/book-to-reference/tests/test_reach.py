"""可达评分必须拒绝不完整运行，机械命中只是人工判定的参考。"""
from pathlib import Path
import shutil

import bookconf
import reach

RUNS = Path(__file__).parent / "fixtures/runs"


def test_reach_decoy_fired(tmp_path):
    shutil.copyfile(RUNS / "success.jsonl", tmp_path / "a001-r1.jsonl")
    assert reach.score(tmp_path, {"a001": "d1"}, {}, "micro-") == {"a001": "FIRED"}


def test_reach_failed_run(tmp_path):
    shutil.copyfile(RUNS / "partial.jsonl", tmp_path / "a001-r1.jsonl")
    assert reach.score(tmp_path, {"a001": "t01-01"}, {"t01-01": ["a"]}, "micro-") == {"a001": "FAILED"}


def test_reach_expected_and_pick(microbook):
    expected = reach.expected_cards(bookconf.open_workdir(microbook), microbook)
    assert expected["t01-01"] == ["steady-shadow"]
    assert reach.pick(expected, 1, 42, set()) == reach.pick(expected, 1, 42, set())
    assert set(reach.pick(expected, 1, 42, set())) == set(expected)


def test_reach_protected_and_rejected(tmp_path):
    shutil.copyfile(RUNS / "no-skill.jsonl", tmp_path / "a001-r1.jsonl")
    assert reach.score(tmp_path, {"a001": "x1"}, {}, "micro-")["a001"] == "REJECT"
    assert reach.score(tmp_path, {"a001": "p-other"}, {"p-other": ["other.md"]}, "micro-")["a001"] == "MISS"


def test_reach_writer_does_not_receive_expected_cards(microbook, tmp_path):
    directory = tmp_path / "selected"
    assert reach.main(["pick", str(microbook), "--seed", "42", "--out-dir", str(directory)]) == 0
    writer = (directory / "tasks-for-prompt-writer.yaml").read_text(encoding="utf-8")
    assert "steady-shadow" not in writer
    assert "steady-shadow" in (directory / "expected.json").read_text(encoding="utf-8")
