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
