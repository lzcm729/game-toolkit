"""laozhang 极简后端的协议层：不打真 API。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKENDS_DIR = Path(__file__).resolve().parent.parent / "scripts" / "backends"
if str(BACKENDS_DIR) not in sys.path:
    sys.path.insert(0, str(BACKENDS_DIR))

import laozhang_backend as lb


def _batch(tmp_path: Path, assets: list, defaults: dict | None = None) -> Path:
    p = tmp_path / "batch.json"
    p.write_text(json.dumps({
        "$schema_version": 2,
        "defaults": defaults or {},
        "assets": assets,
    }, ensure_ascii=False), encoding="utf-8")
    return p


def _read_summary(capsys) -> dict:
    """summary 必须是 stdout 的最后一行。"""
    out = capsys.readouterr().out.strip().splitlines()
    return json.loads(out[-1])


def test_dry_run_makes_no_request_and_writes_nothing(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    called = []
    monkeypatch.setattr(lb, "_generate_one", lambda *a, **k: called.append(1) or b"x")
    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}])
    out = tmp_path / "out"
    out.mkdir()

    rc = lb.main([str(batch), "--output-dir", str(out), "--dry-run"])

    assert rc == 0
    assert called == []
    assert list(out.iterdir()) == []
    assert _read_summary(capsys)["total"] == 1


def test_rejects_unknown_schema_version(tmp_path, capsys, monkeypatch):
    """不认识的 schema 直接报错，不要猜。"""
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    p = tmp_path / "batch.json"
    p.write_text(json.dumps({"$schema_version": 99, "defaults": {}, "assets": []}), encoding="utf-8")
    rc = lb.main([str(p), "--output-dir", str(tmp_path)])
    assert rc == 1
    assert "99" in capsys.readouterr().err


def test_missing_api_key_explains_how_to_set_it(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("LAOZHANG_API_KEY", raising=False)
    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}])
    rc = lb.main([str(batch), "--output-dir", str(tmp_path)])
    assert rc == 1
    assert "LAOZHANG_API_KEY" in capsys.readouterr().err


def test_existing_file_is_skipped_without_force(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    calls = []
    monkeypatch.setattr(lb, "_generate_one", lambda *a, **k: calls.append(1) or b"png")
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.png").write_bytes(b"old")
    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}])

    rc = lb.main([str(batch), "--output-dir", str(out)])

    assert rc == 0
    assert calls == []
    assert (out / "a.png").read_bytes() == b"old"
    s = _read_summary(capsys)
    assert (s["skipped"], s["success"], s["total"]) == (1, 0, 1)


def test_force_overwrites(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    monkeypatch.setattr(lb, "_generate_one", lambda *a, **k: b"new")
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.png").write_bytes(b"old")
    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}])

    rc = lb.main([str(batch), "--output-dir", str(out), "--force"])

    assert rc == 0
    assert (out / "a.png").read_bytes() == b"new"
    assert _read_summary(capsys)["success"] == 1


def test_one_failure_does_not_abort_batch(tmp_path, capsys, monkeypatch):
    """一张 429 不该毁掉 50 张的批次；部分失败退 2。"""
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")

    def flaky(prompt, **kwargs):
        if "boom" in prompt:
            raise RuntimeError("HTTP 429")
        return b"png"

    monkeypatch.setattr(lb, "_generate_one", flaky)
    out = tmp_path / "out"
    out.mkdir()
    batch = _batch(tmp_path, [
        {"name": "a", "filename": "a.png", "prompt": "ok"},
        {"name": "b", "filename": "b.png", "prompt": "boom"},
        {"name": "c", "filename": "c.png", "prompt": "ok"},
    ])

    rc = lb.main([str(batch), "--output-dir", str(out)])

    assert rc == 2
    s = _read_summary(capsys)
    assert (s["total"], s["success"], s["failed"]) == (3, 2, 1)
    assert "b" in json.dumps(s["failed_assets"])
    assert (out / "c.png").exists()      # 失败之后仍继续跑完


def test_all_failed_exits_1(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")

    def always_fail(prompt, **kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr(lb, "_generate_one", always_fail)
    out = tmp_path / "out"
    out.mkdir()
    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}])
    assert lb.main([str(batch), "--output-dir", str(out)]) == 1


def test_item_level_overrides_beat_defaults(tmp_path, monkeypatch):
    """asset 上的 aspect_ratio / seed 优先于 defaults。"""
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    seen = {}

    def capture(prompt, **kwargs):
        seen.update(kwargs)
        return b"png"

    monkeypatch.setattr(lb, "_generate_one", capture)
    out = tmp_path / "out"
    out.mkdir()
    batch = _batch(
        tmp_path,
        [{"name": "a", "filename": "a.png", "prompt": "p", "aspect_ratio": "4:5", "seed": 7}],
        defaults={"aspect_ratio": "1:1", "seed": 1},
    )
    lb.main([str(batch), "--output-dir", str(out)])
    assert seen["aspect_ratio"] == "4:5"
    assert seen["seed"] == 7


def test_too_many_references_is_fatal(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    refs = [str(tmp_path / f"r{i}.png") for i in range(lb.MAX_REFERENCES + 1)]
    batch = _batch(
        tmp_path,
        [{"name": "a", "filename": "a.png", "prompt": "p"}],
        defaults={"reference_paths": refs},
    )
    assert lb.main([str(batch), "--output-dir", str(tmp_path)]) == 1
    assert str(lb.MAX_REFERENCES) in capsys.readouterr().err
