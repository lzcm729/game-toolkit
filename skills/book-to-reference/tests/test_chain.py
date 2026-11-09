"""读取请求不等于读到文件；失败运行不能混入自然链路的有效题。"""
from pathlib import Path

import chain

RUNS = Path(__file__).parent / "fixtures/runs"
MARKER = "/game-design-theory/references/"


def test_denied_read_not_counted():
    run = chain.parse_run(RUNS / "denied.jsonl")
    assert run.ok and run.reads == []
    assert chain.counts([run], MARKER, "micro-")["skill_and_card"] == 0


def test_backslash_read_detected():
    run = chain.parse_run(RUNS / "windows-read.jsonl")
    assert "\\" not in run.reads[0]
    assert chain.counts([run], MARKER, "micro-")["skill_and_card"] == 1


def test_failed_runs_separate():
    runs = [chain.parse_run(RUNS / name) for name in ("error.jsonl", "partial.jsonl", "no-skill.jsonl")]
    counts = chain.counts(runs, MARKER, "micro-")
    assert counts["runs"] == 3 and counts["failed"] == 2
    assert counts["no_skill"] == 1 and counts["skill"] == 0
    assert runs[0].answer is None and runs[1].answer is None


def test_success_pairs_two_reads():
    run = chain.parse_run(RUNS / "success.jsonl")
    assert len(run.reads) == 2
    assert run.model == "fake-model" and run.cc_version == "0.fake"
    assert chain.counts([run], MARKER, "micro-")["skill"] == 1


def test_result_must_be_final(tmp_path):
    path = tmp_path / "appended.jsonl"
    path.write_text((RUNS / "success.jsonl").read_text(encoding="utf-8") + '{"type":"assistant"}\n', encoding="utf-8", newline="\n")
    assert not chain.parse_run(path).ok


def test_unrelated_skill_is_not_plugin_activation(tmp_path):
    path = tmp_path / "other.jsonl"
    text = (RUNS / "success.jsonl").read_text(encoding="utf-8").replace("game-toolkit:design-discuss", "another-plugin:helper")
    path.write_text(text, encoding="utf-8", newline="\n")
    counts = chain.counts([chain.parse_run(path)], MARKER, "micro-")
    assert counts["skill"] == 0 and counts["no_skill"] == 1


def test_parse_run_tolerates_string_message():
    run = chain.parse_run(RUNS / "string-message.jsonl")
    assert run.ok
    assert run.skills == [] and run.reads == []


def test_parse_run_tolerates_mixed_event_shapes():
    run = chain.parse_run(RUNS / "mixed-shapes.jsonl")
    assert run.ok
    assert run.skills == ["game-toolkit:design-discuss"]
    assert run.reads == ["plugin/skills/game-design-theory/references/micro-shutter-test.md"]
    assert run.cost == 0 and run.model == "" and run.cc_version == ""
