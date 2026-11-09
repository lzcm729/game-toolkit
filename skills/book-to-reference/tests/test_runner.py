"""回放进程验证隔离和重跑，不调用真实 Claude CLI。"""
import json
from pathlib import Path
import shutil
import sys

import pytest

import runner

FIXTURES = Path(__file__).parent / "fixtures"


def test_plan_jobs_interleaves(tmp_path):
    jobs = runner.plan_jobs([("q1", "one"), ("q2", "two")], {"a": tmp_path, "b": tmp_path}, 2)
    assert [job.variant for job in jobs[:4]] == ["a", "b", "a", "b"]
    assert [(job.prompt_id, job.rep) for job in jobs[:4]] == [("q1", 1), ("q1", 1), ("q1", 2), ("q1", 2)]


def put_run(tmp_path, name, batch="batch"):
    path = tmp_path / "q1-r1.jsonl"
    shutil.copyfile(FIXTURES / "runs" / name, path)
    Path(str(path) + ".meta.json").write_text(json.dumps({"batch_id": batch}), encoding="utf-8", newline="\n")
    return path


def test_partial_run_not_success(tmp_path):
    assert not runner.is_success(put_run(tmp_path, "partial.jsonl"), "batch")


def test_error_result_not_success(tmp_path):
    assert not runner.is_success(put_run(tmp_path, "error.jsonl"), "batch")


def test_other_batch_not_success(tmp_path):
    assert not runner.is_success(put_run(tmp_path, "success.jsonl", "older"), "batch")


def test_runs_root_under_home_rejected():
    with pytest.raises(ValueError, match="主目录"):
        runner.check_runs_root(Path.home() / "runs")


def test_rerun_replaces_partial(tmp_path, monkeypatch):
    # pytest 的默认临时目录在真实主目录里；假进程测试用一个明确的模拟主目录。
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    log = tmp_path / "fake.log"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    out_dir = tmp_path / "out"
    (out_dir / "a").mkdir(parents=True)
    partial = out_dir / "a/q1-r1.jsonl"
    shutil.copyfile(FIXTURES / "runs/partial.jsonl", partial)
    jobs = runner.plan_jobs([("q1", "answer")], {"a": tmp_path, "b": tmp_path}, 1)
    paths = runner.run_batch(jobs, out_dir, tmp_path / "runs", "batch", 1, .1, "fake-model",
                             [sys.executable, str(FIXTURES / "fake_claude.py")])
    assert Path(str(partial) + ".stale-1").is_file()
    assert all(runner.is_success(path, "batch") for path in paths)
    calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert len(calls) == 2 and all(not call["cwd_entries"] for call in calls)
    assert calls[0]["cwd"] != calls[1]["cwd"]
    assert calls[0]["config_dir"] == calls[1]["config_dir"]
    assert "--add-dir" in calls[0]["args"] and "--no-session-persistence" in calls[0]["args"]
    assert "Read,Glob,Grep,Skill" in calls[0]["args"]
    assert "--bare" not in calls[0]["args"]
    meta = json.loads(Path(str(paths[0]) + ".meta.json").read_text(encoding="utf-8"))
    assert meta["model"] == "fake-model" and meta["cc_version"] == "0.fake"
    runner.run_batch(jobs, out_dir, tmp_path / "runs", "batch", 1, .1, "fake-model",
                     [sys.executable, str(FIXTURES / "fake_claude.py")])
    assert len(log.read_text(encoding="utf-8").splitlines()) == 2


def test_batch_continues_after_job_error(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    log = tmp_path / "fake.log"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    prompts = tmp_path / "prompts.tsv"
    prompts.write_text("q1\tx\tinvalid-once\nq2\tx\tanswer\n", encoding="utf-8", newline="\n")
    out = tmp_path / "out"
    args = [str(prompts), str(out), "--variant", f"a={tmp_path}", "--variant", f"b={tmp_path}",
            "--reps", "1", "--lanes", "1", "--budget", ".1", "--batch-id", "batch",
            "--runs-root", str(tmp_path / "runs"), "--claude",
            f'"{sys.executable}" "{FIXTURES / "fake_claude.py"}"']
    assert runner.main(args) == 1
    paths = [out / variant / f"{qid}-r1.jsonl" for qid in ("q1", "q2") for variant in ("a", "b")]
    assert all(path.is_file() for path in paths)
    assert [runner.is_success(path, "batch") for path in paths] == [False, True, True, True]
    meta = json.loads(Path(str(paths[0]) + ".meta.json").read_text(encoding="utf-8"))
    assert meta["error"]["type"] == "ValueError" and meta["error"]["message"]
    assert "synthetic non-JSON" in paths[0].read_text(encoding="utf-8")
    printed = capsys.readouterr().out
    assert "failed: 1" in printed and paths[0].as_posix() in printed
    untouched = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths[1:]}
    assert runner.main(args) == 0
    assert all(runner.is_success(path, "batch") for path in paths)
    assert len(log.read_text(encoding="utf-8").splitlines()) == 5
    assert all((path.read_bytes(), path.stat().st_mtime_ns) == state for path, state in untouched.items())


def test_batch_records_parser_exception(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(tmp_path / "fake.log"))
    original = runner.parse_run

    def parse(path):
        if path.name == "q1-r1.jsonl":
            raise RuntimeError("synthetic parser failure")
        return original(path)

    monkeypatch.setattr(runner, "parse_run", parse)
    jobs = runner.plan_jobs([("q1", "answer"), ("q2", "answer")], {"a": tmp_path}, 1)
    paths = runner.run_batch(jobs, tmp_path / "out", tmp_path / "runs", "batch", 2, .1,
                             "fake-model", [sys.executable, str(FIXTURES / "fake_claude.py")])
    meta = json.loads(Path(str(paths[0]) + ".meta.json").read_text(encoding="utf-8"))
    assert meta["error"] == {"type": "RuntimeError", "message": "synthetic parser failure"}
    assert not runner.is_success(paths[0], "batch")
    assert runner.is_success(paths[1], "batch")


def test_batch_records_launch_error(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    jobs = runner.plan_jobs([("q1", "answer"), ("q2", "answer")], {"a": tmp_path}, 1)
    paths = runner.run_batch(jobs, tmp_path / "out", tmp_path / "runs", "batch", 1, .1,
                             "fake-model", [str(tmp_path / "missing-executable")])
    assert len(paths) == 2
    for path in paths:
        meta = json.loads(Path(str(path) + ".meta.json").read_text(encoding="utf-8"))
        assert meta["error"]["type"] == "FileNotFoundError"
        assert not runner.is_success(path, "batch")
