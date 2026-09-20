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


class _FakeResp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _image_payload(b64: str = "aGk=") -> dict:
    return {"candidates": [{"content": {"parts": [{"inlineData": {"data": b64}}]}}]}


def test_generate_one_posts_gemini_native_shape(monkeypatch):
    """必须走 /v1beta/...:generateContent —— OpenAI 路径不支持多图 reference。"""
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        seen["url"] = url
        seen["headers"] = headers
        seen["body"] = json
        return _FakeResp(payload=_image_payload())

    monkeypatch.setattr(lb.requests, "post", fake_post)

    data = lb._generate_one(
        "a cat", model="gemini-3.1-flash-image-preview", api_key="sk-x",
        base_url="https://api.laozhang.ai", aspect_ratio="4:5", seed=None,
        reference_paths=[], timeout_s=30.0,
    )

    assert data == b"hi"
    assert seen["url"] == (
        "https://api.laozhang.ai/v1beta/models/gemini-3.1-flash-image-preview:generateContent"
    )
    assert seen["headers"]["Authorization"] == "Bearer sk-x"
    cfg = seen["body"]["generationConfig"]
    assert cfg["imageConfig"]["aspectRatio"] == "4:5"
    assert "seed" not in cfg          # seed 为 None 时不该出现在请求里
    parts = seen["body"]["contents"][0]["parts"]
    assert parts[-1]["text"] == "a cat"


def test_generate_one_inlines_references_before_prompt(tmp_path, monkeypatch):
    """参考图以 inline_data 排在 prompt 之前。"""
    ref = tmp_path / "anchor.png"
    ref.write_bytes(b"\x89PNG-fake")
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        seen["body"] = json
        return _FakeResp(payload=_image_payload())

    monkeypatch.setattr(lb.requests, "post", fake_post)

    lb._generate_one(
        "a cat", model="m", api_key="k", base_url="https://x",
        aspect_ratio="1:1", seed=42, reference_paths=[str(ref)], timeout_s=30.0,
    )

    parts = seen["body"]["contents"][0]["parts"]
    assert "inline_data" in parts[0]
    assert parts[0]["inline_data"]["mime_type"] == "image/png"
    assert parts[-1]["text"] == "a cat"
    assert seen["body"]["generationConfig"]["seed"] == 42


def test_generate_one_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(
        lb.requests, "post",
        lambda *a, **k: _FakeResp(status=429, text="rate limited"),
    )
    with pytest.raises(RuntimeError) as ei:
        lb._generate_one(
            "p", model="m", api_key="k", base_url="https://x",
            aspect_ratio="1:1", seed=None, reference_paths=[], timeout_s=5.0,
        )
    assert "429" in str(ei.value)


def test_generate_one_raises_when_no_image_in_response(monkeypatch):
    """只回了文字没回图 —— 不能当成功。"""
    monkeypatch.setattr(
        lb.requests, "post",
        lambda *a, **k: _FakeResp(
            payload={"candidates": [{"content": {"parts": [{"text": "sorry"}]}}]}
        ),
    )
    with pytest.raises(RuntimeError) as ei:
        lb._generate_one(
            "p", model="m", api_key="k", base_url="https://x",
            aspect_ratio="1:1", seed=None, reference_paths=[], timeout_s=5.0,
        )
    assert "没有图像" in str(ei.value)
