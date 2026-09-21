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


@pytest.fixture(autouse=True)
def _never_hit_real_api(monkeypatch):
    """兜底：任何测试都不许真发 HTTP。

    凭证隔离靠逐条测试自觉，漏一条就可能在别人机器上真扣费 —— 这已经发生过
    两次（一次是没隔离 CWD 下的 .env，一次是只删了三把 key 中的一把）。
    要测请求本身的用例会自己 monkeypatch 覆盖这两个桩。
    """
    def boom(*a, **k):
        pytest.fail("测试试图发真实 HTTP 请求 —— 检查凭证与 CWD 隔离")
    monkeypatch.setattr(lb.requests, "post", boom)
    monkeypatch.setattr(lb.requests, "get", boom)


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
    # 必须隔离 CWD 与 home：后端会向上找 .env，只删进程变量的话，
    # 跑测试的目录祖先里有 .env 就会读到真 key、真发请求、真扣费。
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(lb.Path, "home", staticmethod(lambda: tmp_path / "nohome"))
    monkeypatch.delenv("LAOZHANG_API_KEY", raising=False)
    monkeypatch.delenv("LAOZHANG_OFFICIAL_API_KEY", raising=False)
    # 兜底：万一隔离失效也不许真发请求
    monkeypatch.setattr(lb, "_generate_one", lambda *a, **k: pytest.fail("不该走到生图"))
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


def test_dry_run_works_without_api_key(tmp_path, capsys, monkeypatch):
    """dry-run 不发请求，就不该要 key——新用户想先看看会出什么图。"""
    monkeypatch.delenv("LAOZHANG_API_KEY", raising=False)
    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}])
    out = tmp_path / "out"
    out.mkdir()

    rc = lb.main([str(batch), "--output-dir", str(out), "--dry-run"])

    assert rc == 0
    assert _read_summary(capsys)["total"] == 1


# -------------------- .env 查找 --------------------
# key 放在项目 .env 里是常见做法，image-gen 的 env.py 就这么找。
# 后端只读 os.environ 的话，「装了插件设个 key 就能跑」在那种环境里不成立。


def test_find_env_value_searches_cwd_upward(tmp_path, monkeypatch):
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (tmp_path / ".env").write_text("LAOZHANG_API_KEY=sk-upward\n", encoding="utf-8")
    monkeypatch.chdir(deep)
    monkeypatch.delenv("LAOZHANG_API_KEY", raising=False)
    assert lb._find_env_value("LAOZHANG_API_KEY") == "sk-upward"


def test_find_env_value_falls_back_to_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / ".env").write_text("LAOZHANG_API_KEY=sk-home\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setattr(lb.Path, "home", staticmethod(lambda: home))
    monkeypatch.delenv("LAOZHANG_API_KEY", raising=False)
    assert lb._find_env_value("LAOZHANG_API_KEY") == "sk-home"


def test_find_env_value_falls_back_to_environ(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setattr(lb.Path, "home", staticmethod(lambda: tmp_path / "nohome"))
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-environ")
    assert lb._find_env_value("LAOZHANG_API_KEY") == "sk-environ"


def test_dotenv_wins_over_environ(tmp_path, monkeypatch):
    """与 image-gen 同序：.env 优先。同一台机器上两个后端行为得一致。"""
    work = tmp_path / "work"
    work.mkdir()
    (work / ".env").write_text("LAOZHANG_API_KEY=sk-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(work)
    monkeypatch.setattr(lb.Path, "home", staticmethod(lambda: tmp_path / "nohome"))
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-environ")
    assert lb._find_env_value("LAOZHANG_API_KEY") == "sk-dotenv"


def test_env_file_tolerates_quotes_and_export(tmp_path, monkeypatch):
    work = tmp_path / "work"
    work.mkdir()
    (work / ".env").write_text(
        '# comment\nexport LAOZHANG_API_KEY="sk-quoted"\nOTHER=x\n', encoding="utf-8"
    )
    monkeypatch.chdir(work)
    monkeypatch.setattr(lb.Path, "home", staticmethod(lambda: tmp_path / "nohome"))
    monkeypatch.delenv("LAOZHANG_API_KEY", raising=False)
    assert lb._find_env_value("LAOZHANG_API_KEY") == "sk-quoted"


def test_main_picks_up_key_from_dotenv(tmp_path, capsys, monkeypatch):
    """端到端：key 只在 .env 里，main 不该再报「缺 LAOZHANG_API_KEY」。"""
    monkeypatch.delenv("LAOZHANG_API_KEY", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    (work / ".env").write_text("LAOZHANG_API_KEY=sk-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(work)
    monkeypatch.setattr(lb.Path, "home", staticmethod(lambda: tmp_path / "nohome"))

    seen = {}

    def capture(prompt, **kwargs):
        seen.update(kwargs)
        return b"png"

    monkeypatch.setattr(lb, "_generate_one", capture)
    batch = _batch(work, [{"name": "a", "filename": "a.png", "prompt": "p"}])
    out = work / "out"
    out.mkdir()

    assert lb.main([str(batch), "--output-dir", str(out)]) == 0
    assert seen["api_key"] == "sk-dotenv"


# -------------------- 重试 --------------------
# laozhang 网关实测会间歇抛 SSLEOFError（curl 同一请求却正常）。
# image-gen 有 --retries 2 兜底，所以平时感觉不到。「极简」指的是不做
# chain/fallback/preset，不该连基本的网络重试都没有。


def test_retries_on_network_error_then_succeeds(monkeypatch):
    import requests as _rq

    calls = []

    def flaky(*a, **k):
        calls.append(1)
        if len(calls) < 3:
            raise _rq.exceptions.SSLError("EOF occurred in violation of protocol")
        return _FakeResp(payload=_image_payload())

    monkeypatch.setattr(lb.requests, "post", flaky)
    monkeypatch.setattr(lb.time, "sleep", lambda s: None)

    data = lb._generate_one(
        "p", model="m", api_key="k", base_url="https://x",
        aspect_ratio="1:1", seed=None, reference_paths=[], timeout_s=5.0,
    )
    assert data == b"hi"
    assert len(calls) == 3      # 失败两次后第三次成功


def test_retries_on_429(monkeypatch):
    calls = []

    def rate_limited(*a, **k):
        calls.append(1)
        if len(calls) < 2:
            return _FakeResp(status=429, text="rate limited")
        return _FakeResp(payload=_image_payload())

    monkeypatch.setattr(lb.requests, "post", rate_limited)
    monkeypatch.setattr(lb.time, "sleep", lambda s: None)

    assert lb._generate_one(
        "p", model="m", api_key="k", base_url="https://x",
        aspect_ratio="1:1", seed=None, reference_paths=[], timeout_s=5.0,
    ) == b"hi"
    assert len(calls) == 2


def test_does_not_retry_on_400(monkeypatch):
    """参数错误重试多少次都一样，白花时间。"""
    calls = []

    def bad_request(*a, **k):
        calls.append(1)
        return _FakeResp(status=400, text="invalid prompt")

    monkeypatch.setattr(lb.requests, "post", bad_request)
    monkeypatch.setattr(lb.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError):
        lb._generate_one(
            "p", model="m", api_key="k", base_url="https://x",
            aspect_ratio="1:1", seed=None, reference_paths=[], timeout_s=5.0,
        )
    assert len(calls) == 1


def test_gives_up_after_retries_exhausted(monkeypatch):
    import requests as _rq

    calls = []

    def always_down(*a, **k):
        calls.append(1)
        raise _rq.exceptions.ConnectionError("connection reset")

    monkeypatch.setattr(lb.requests, "post", always_down)
    monkeypatch.setattr(lb.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError) as ei:
        lb._generate_one(
            "p", model="m", api_key="k", base_url="https://x",
            aspect_ratio="1:1", seed=None, reference_paths=[], timeout_s=5.0,
        )
    assert "connection reset" in str(ei.value)
    assert len(calls) == lb.DEFAULT_RETRIES + 1


# -------------------- model 选择 --------------------
# 优先级：asset.model > defaults.model > LAOZHANG_MODEL > 内置默认。
# 配置文件压过环境变量，与 .env 那条同序。


def _run_capture_model(tmp_path, monkeypatch, *, defaults=None, asset_extra=None):
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    seen = {}

    def capture(prompt, **kwargs):
        seen.update(kwargs)
        return b"png"

    monkeypatch.setattr(lb, "_generate_one", capture)
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    asset = {"name": "a", "filename": "a.png", "prompt": "p"}
    asset.update(asset_extra or {})
    batch = _batch(tmp_path, [asset], defaults=defaults)
    assert lb.main([str(batch), "--output-dir", str(out), "--force"]) == 0
    return seen["model"]


def test_model_from_batch_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("LAOZHANG_MODEL", raising=False)
    assert _run_capture_model(
        tmp_path, monkeypatch, defaults={"model": "gpt-image-2.5-flare"}
    ) == "gpt-image-2.5-flare"


def test_asset_model_overrides_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv("LAOZHANG_MODEL", raising=False)
    assert _run_capture_model(
        tmp_path, monkeypatch,
        defaults={"model": "gemini-3.1-flash-image"},
        asset_extra={"model": "gemini-3-pro-image"},
    ) == "gemini-3-pro-image"


def test_env_model_used_when_batch_declares_none(tmp_path, monkeypatch):
    monkeypatch.setenv("LAOZHANG_MODEL", "gemini-2.5-flash-image")
    assert _run_capture_model(tmp_path, monkeypatch) == "gemini-2.5-flash-image"


def test_batch_model_wins_over_env(tmp_path, monkeypatch):
    """与 .env 同序：配置文件压过环境变量。"""
    monkeypatch.setenv("LAOZHANG_MODEL", "gemini-2.5-flash-image")
    assert _run_capture_model(
        tmp_path, monkeypatch, defaults={"model": "gpt-image-2.5-flare"}
    ) == "gpt-image-2.5-flare"


def test_falls_back_to_builtin_default(tmp_path, monkeypatch):
    monkeypatch.delenv("LAOZHANG_MODEL", raising=False)
    assert _run_capture_model(tmp_path, monkeypatch) == lb.DEFAULT_MODEL


# -------------------- 两条 API 路径 --------------------
# gemini-* 走 Gemini native（支持多图 reference 与单图 edit）；
# gpt-image-* 走 OpenAI style（只有单图 edit，没有多图 reference）。


def _png(tmp_path, name="base.png"):
    p = tmp_path / name
    p.write_bytes(b"\x89PNG-fake")
    return p


def test_gemini_edit_uses_inline_data_and_image_modality(tmp_path, monkeypatch):
    """edit 模式输出尺寸跟随输入图，不该再传 aspectRatio。"""
    base = _png(tmp_path)
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        seen["url"] = url
        seen["body"] = json
        return _FakeResp(payload=_image_payload())

    monkeypatch.setattr(lb.requests, "post", fake_post)
    lb._generate_one(
        "make it barren", model="gemini-3.1-flash-image", api_key="k",
        base_url="https://x", aspect_ratio="16:9", seed=None,
        reference_paths=[], image_path=str(base), timeout_s=30.0,
    )
    assert ":generateContent" in seen["url"]
    parts = seen["body"]["contents"][0]["parts"]
    assert "inline_data" in parts[0]
    assert parts[-1]["text"] == "make it barren"
    cfg = seen["body"]["generationConfig"]
    assert cfg["responseModalities"] == ["IMAGE", "TEXT"]
    assert "imageConfig" not in cfg


def test_gpt_image_edit_posts_multipart_to_edits(tmp_path, monkeypatch):
    base = _png(tmp_path)
    seen = {}

    def fake_post(url, headers=None, files=None, timeout=None, **kw):
        seen["url"] = url
        seen["files"] = files
        seen["timeout"] = timeout
        return _FakeResp(payload={"data": [{"b64_json": "aGk="}]})

    monkeypatch.setattr(lb.requests, "post", fake_post)
    data = lb._generate_one(
        "make it barren", model="gpt-image-2.5-flare", api_key="k",
        base_url="https://x", aspect_ratio="16:9", seed=None,
        reference_paths=[], image_path=str(base), timeout_s=30.0,
    )
    assert data == b"hi"
    assert seen["url"] == "https://x/v1/images/edits"
    assert seen["files"]["model"][1] == "gpt-image-2.5-flare"
    assert seen["files"]["prompt"][1] == "make it barren"
    assert seen["files"]["size"][1] == "1536x1024"      # 16:9
    assert seen["timeout"] >= 360                        # 这条路慢，得放宽


def test_gpt_image_without_base_goes_to_generations(monkeypatch):
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        seen["url"] = url
        seen["body"] = json
        return _FakeResp(payload={"data": [{"b64_json": "aGk="}]})

    monkeypatch.setattr(lb.requests, "post", fake_post)
    lb._generate_one(
        "a pebble", model="gpt-image-2.5-sunburst", api_key="k",
        base_url="https://x", aspect_ratio="1:1", seed=None,
        reference_paths=[], image_path=None, timeout_s=30.0,
    )
    assert seen["url"] == "https://x/v1/images/generations"
    assert seen["body"]["size"] == "1024x1024"


def test_gpt_image_rejects_reference_paths(tmp_path, monkeypatch):
    """OpenAI 路径没有多图 reference——说清楚，别静默丢掉风格锚。"""
    monkeypatch.setattr(lb.requests, "post", lambda *a, **k: _FakeResp())
    with pytest.raises(RuntimeError) as ei:
        lb._generate_one(
            "p", model="gpt-image-2.5-flare", api_key="k", base_url="https://x",
            aspect_ratio="1:1", seed=None, reference_paths=[str(_png(tmp_path))],
            image_path=None, timeout_s=30.0,
        )
    msg = str(ei.value)
    assert "reference" in msg and "gemini" in msg.lower()


def test_openai_response_url_is_downloaded(monkeypatch):
    monkeypatch.setattr(
        lb.requests, "post",
        lambda *a, **k: _FakeResp(payload={"data": [{"url": "https://cdn/x.png"}]}),
    )

    class _Img:
        content = b"downloaded"
        headers = {"Content-Type": "image/png"}
        status_code = 200
        ok = True

        def raise_for_status(self):
            pass

    monkeypatch.setattr(lb.requests, "get", lambda *a, **k: _Img())
    assert lb._generate_one(
        "p", model="gpt-image-2.5-flare", api_key="k", base_url="https://x",
        aspect_ratio="1:1", seed=None, reference_paths=[], image_path=None,
        timeout_s=30.0,
    ) == b"downloaded"


def test_api_key_env_differs_by_model_family(tmp_path, monkeypatch):
    """gpt-image-* 在 official 分组，用另一把 key。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(lb.Path, "home", staticmethod(lambda: tmp_path / "nohome"))
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-normal")
    monkeypatch.setenv("LAOZHANG_OFFICIAL_API_KEY", "sk-official")
    assert lb._resolve_api_key("gemini-3.1-flash-image") == "sk-normal"
    assert lb._resolve_api_key("gpt-image-2.5-flare") == "sk-official"


def test_gpt_image_falls_back_to_normal_key(tmp_path, monkeypatch):
    """没配 official key 就用普通的——别直接判定不可用。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(lb.Path, "home", staticmethod(lambda: tmp_path / "nohome"))
    monkeypatch.delenv("LAOZHANG_OFFICIAL_API_KEY", raising=False)
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-normal")
    assert lb._resolve_api_key("gpt-image-2.5-flare") == "sk-normal"


def test_main_passes_image_through(tmp_path, monkeypatch):
    base = _png(tmp_path)
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    seen = {}

    def capture(prompt, **kwargs):
        seen.update(kwargs)
        return b"png"

    monkeypatch.setattr(lb, "_generate_one", capture)
    out = tmp_path / "out"
    out.mkdir()
    batch = _batch(tmp_path, [
        {"name": "a", "filename": "a.png", "prompt": "p", "image": str(base)}
    ])
    assert lb.main([str(batch), "--output-dir", str(out)]) == 0
    assert seen["image_path"] == str(base)


def test_openai_warns_when_aspect_ratio_is_only_approximated(monkeypatch, capsys):
    """OpenAI 只有 1:1 / 2:3 / 3:2 三档，其余都是近似，会裁掉边缘。"""
    monkeypatch.setattr(
        lb.requests, "post",
        lambda *a, **k: _FakeResp(payload={"data": [{"b64_json": "aGk="}]}),
    )
    lb._generate_one(
        "p", model="gpt-image-2.5-flare", api_key="k", base_url="https://x",
        aspect_ratio="16:9", seed=None, reference_paths=[], image_path=None,
        timeout_s=30.0,
    )
    err = capsys.readouterr().err
    assert "16:9" in err and "1536x1024" in err


def test_openai_silent_on_exact_aspect_ratio(monkeypatch, capsys):
    monkeypatch.setattr(
        lb.requests, "post",
        lambda *a, **k: _FakeResp(payload={"data": [{"b64_json": "aGk="}]}),
    )
    lb._generate_one(
        "p", model="gpt-image-2.5-flare", api_key="k", base_url="https://x",
        aspect_ratio="3:2", seed=None, reference_paths=[], image_path=None,
        timeout_s=30.0,
    )
    assert "近似" not in capsys.readouterr().err


# -------------------- codex 评审发现的缺陷 --------------------


def test_cdn_download_failure_does_not_regenerate(monkeypatch):
    """#3 图已生成（已计费），下载失败不该重新 POST 生图。"""
    import requests as _rq
    posts, gets = [], []

    def fake_post(*a, **k):
        posts.append(1)
        return _FakeResp(payload={"data": [{"url": "https://cdn/x.png"}]})

    def fake_get(*a, **k):
        gets.append(1)
        raise _rq.exceptions.ConnectionError("cdn down")

    monkeypatch.setattr(lb.requests, "post", fake_post)
    monkeypatch.setattr(lb.requests, "get", fake_get)
    monkeypatch.setattr(lb.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError):
        lb._generate_one(
            "p", model="gpt-image-2.5-flare", api_key="k", base_url="https://x",
            aspect_ratio="1:1", seed=None, reference_paths=[], image_path=None,
            timeout_s=30.0,
        )
    assert len(posts) == 1, f"重新生图了 {len(posts)} 次，应该只有 1 次"
    assert len(gets) > 1, "下载本身该重试"


def test_cdn_download_403_is_not_retried(monkeypatch):
    """403 是永久错误，重试只是浪费时间。"""
    gets = []

    class _Forbidden:
        status_code = 403
        ok = False
        headers = {}
        content = b""

        def raise_for_status(self):
            import requests as _rq
            raise _rq.exceptions.HTTPError("403 Forbidden", response=self)

    def fake_get(*a, **k):
        gets.append(1)
        return _Forbidden()

    monkeypatch.setattr(
        lb.requests, "post",
        lambda *a, **k: _FakeResp(payload={"data": [{"url": "https://cdn/x.png"}]}),
    )
    monkeypatch.setattr(lb.requests, "get", fake_get)
    monkeypatch.setattr(lb.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError):
        lb._generate_one(
            "p", model="gpt-image-2.5-flare", api_key="k", base_url="https://x",
            aspect_ratio="1:1", seed=None, reference_paths=[], image_path=None,
            timeout_s=30.0,
        )
    assert len(gets) == 1, f"403 被重试了 {len(gets)} 次"


def test_existing_file_skipped_even_without_key(tmp_path, capsys, monkeypatch):
    """#5 目标已存在就该 skip，不该因为缺 key 把整批拦在门外。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(lb.Path, "home", staticmethod(lambda: tmp_path / "nohome"))
    for var in ("LAOZHANG_API_KEY", "LAOZHANG_OFFICIAL_API_KEY", "LAOZHANG_MODEL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(lb, "_generate_one",
                        lambda *a, **k: pytest.fail("已存在的文件不该走到生图"))
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.png").write_bytes(b"old")
    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}])

    rc = lb.main([str(batch), "--output-dir", str(out)])

    assert rc == 0
    s = _read_summary(capsys)
    assert (s["skipped"], s["total"]) == (1, 1)


def test_missing_key_still_fatal_when_work_remains(tmp_path, capsys, monkeypatch):
    """但真有活要干时，缺 key 仍须在开跑前拦住。

    凭证隔离要删干净：只删 LAOZHANG_API_KEY 的话，环境里若有
    LAOZHANG_MODEL=gpt-image-* 加 official key，这条「缺 key」测试
    反而具备了生图所需的全部凭证，会真发请求。
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(lb.Path, "home", staticmethod(lambda: tmp_path / "nohome"))
    for var in ("LAOZHANG_API_KEY", "LAOZHANG_OFFICIAL_API_KEY", "LAOZHANG_MODEL"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(lb, "_generate_one",
                        lambda *a, **k: pytest.fail("缺 key 时不该走到生图"))
    out = tmp_path / "out"
    out.mkdir()
    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}])
    assert lb.main([str(batch), "--output-dir", str(out)]) == 1
    assert "LAOZHANG_API_KEY" in capsys.readouterr().err


def test_unmapped_aspect_ratio_picks_nearest(monkeypatch):
    """#8 21:9 该落到最接近的横向档，而不是正方形。"""
    seen = {}
    monkeypatch.setattr(
        lb.requests, "post",
        lambda url, headers=None, json=None, timeout=None, **k: (
            seen.update(json or {}) or _FakeResp(payload={"data": [{"b64_json": "aGk="}]})
        ),
    )
    lb._generate_one(
        "p", model="gpt-image-2.5-flare", api_key="k", base_url="https://x",
        aspect_ratio="21:9", seed=None, reference_paths=[], image_path=None,
        timeout_s=30.0,
    )
    assert seen["size"] == "1536x1024"


def test_seed_ignored_on_openai_path_warns(monkeypatch, capsys):
    """#4 OpenAI 路径没有 seed 字段，丢掉就得说，别让人以为复现生效了。"""
    monkeypatch.setattr(
        lb.requests, "post",
        lambda *a, **k: _FakeResp(payload={"data": [{"b64_json": "aGk="}]}),
    )
    lb._generate_one(
        "p", model="gpt-image-2.5-flare", api_key="k", base_url="https://x",
        aspect_ratio="1:1", seed=12345, reference_paths=[], image_path=None,
        timeout_s=30.0,
    )
    err = capsys.readouterr().err
    assert "seed" in err and "12345" in err


def test_aspect_ratio_ignored_in_gemini_edit_warns(tmp_path, monkeypatch, capsys):
    """#4 edit 模式输出跟随底图，显式比例不生效——得说一声。"""
    base = _png(tmp_path)
    monkeypatch.setattr(
        lb.requests, "post",
        lambda *a, **k: _FakeResp(payload=_image_payload()),
    )
    lb._generate_one(
        "p", model="gemini-3.1-flash-image", api_key="k", base_url="https://x",
        aspect_ratio="16:9", seed=None, reference_paths=[], image_path=str(base),
        timeout_s=30.0,
    )
    err = capsys.readouterr().err
    assert "aspect_ratio" in err and "16:9" in err


def test_download_429_is_retried(monkeypatch):
    """#3 429 是 4xx 但属于限流，该退避重试；一次就放弃等于白丢一张已生成的图。"""
    gets = []

    class _Resp:
        def __init__(self, code):
            self.status_code = code
            self.ok = code < 400
            self.content = b"img" if code < 400 else b""
            self.headers = {}

        def raise_for_status(self):
            pass

    def fake_get(*a, **k):
        gets.append(1)
        return _Resp(429 if len(gets) == 1 else 200)

    monkeypatch.setattr(
        lb.requests, "post",
        lambda *a, **k: _FakeResp(payload={"data": [{"url": "https://cdn/x.png"}]}),
    )
    monkeypatch.setattr(lb.requests, "get", fake_get)
    monkeypatch.setattr(lb.time, "sleep", lambda s: None)

    data = lb._generate_one(
        "p", model="gpt-image-2.5-flare", api_key="k", base_url="https://x",
        aspect_ratio="1:1", seed=None, reference_paths=[], image_path=None,
        timeout_s=30.0,
    )
    assert data == b"img"
    assert len(gets) == 2


def test_download_retry_count_is_exact(monkeypatch):
    """耗尽时的 GET 次数要精确，不能只断言 >1 —— 那样重试减成一次也发现不了。"""
    import requests as _rq
    gets = []

    def always_fail(*a, **k):
        gets.append(1)
        raise _rq.exceptions.ConnectionError("down")

    monkeypatch.setattr(
        lb.requests, "post",
        lambda *a, **k: _FakeResp(payload={"data": [{"url": "https://cdn/x.png"}]}),
    )
    monkeypatch.setattr(lb.requests, "get", always_fail)
    monkeypatch.setattr(lb.time, "sleep", lambda s: None)

    with pytest.raises(RuntimeError):
        lb._generate_one(
            "p", model="gpt-image-2.5-flare", api_key="k", base_url="https://x",
            aspect_ratio="1:1", seed=None, reference_paths=[], image_path=None,
            timeout_s=30.0,
        )
    assert len(gets) == lb.DEFAULT_RETRIES + 1


def test_key_rechecked_right_before_generate(tmp_path, capsys, monkeypatch):
    """#5 预检时文件还在（因而没查这个模型的 key），轮到它时文件没了 ——
    不能把空 key 递给 _generate_one 换一个费解的 401。"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(lb.Path, "home", staticmethod(lambda: tmp_path / "nohome"))
    monkeypatch.delenv("LAOZHANG_API_KEY", raising=False)
    monkeypatch.delenv("LAOZHANG_OFFICIAL_API_KEY", raising=False)
    out = tmp_path / "out"
    out.mkdir()
    target = out / "a.png"
    target.write_bytes(b"old")

    real_exists = Path.exists
    state = {"n": 0}

    def flaky_exists(self):
        if self == target:
            state["n"] += 1
            return state["n"] == 1     # 预检时在，循环里没了
        return real_exists(self)

    monkeypatch.setattr(lb.Path, "exists", flaky_exists)
    monkeypatch.setattr(lb, "_generate_one",
                        lambda *a, **k: pytest.fail("缺 key 时不该调生图"))

    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}])
    rc = lb.main([str(batch), "--output-dir", str(out)])

    assert rc == 1
    s = _read_summary(capsys)
    assert s["failed"] == 1
    assert "LAOZHANG_API_KEY" in json.dumps(s["failed_assets"], ensure_ascii=False)


def test_backend_rejects_image_with_reference_paths(tmp_path, monkeypatch):
    """#9 协议规定互斥，后端被单独调用时也得自己拦，不能只靠上层。"""
    monkeypatch.setattr(lb.requests, "post",
                        lambda *a, **k: pytest.fail("该在发请求前就拒绝"))
    with pytest.raises(RuntimeError) as ei:
        lb._generate_one(
            "p", model="gemini-3.1-flash-image", api_key="k", base_url="https://x",
            aspect_ratio="1:1", seed=None,
            reference_paths=[str(_png(tmp_path, "ref.png"))],
            image_path=str(_png(tmp_path, "base.png")), timeout_s=30.0,
        )
    assert "互斥" in str(ei.value)


def test_no_aspect_warning_when_user_did_not_set_it(tmp_path, monkeypatch, capsys):
    """#4 用户没配比例时补的默认值不该反过来警告用户。"""
    base = _png(tmp_path)
    monkeypatch.setattr(lb.requests, "post",
                        lambda *a, **k: _FakeResp(payload=_image_payload()))
    lb._generate_one(
        "p", model="gemini-3.1-flash-image", api_key="k", base_url="https://x",
        aspect_ratio=None, seed=None, reference_paths=[], image_path=str(base),
        timeout_s=30.0,
    )
    assert "aspect_ratio" not in capsys.readouterr().err


def test_reference_image_encoded_once_per_process(tmp_path, monkeypatch):
    """风格锚在整批里只读一次、编码一次。

    锚图常有几 MB，base64 后更大。16 张图各自重读重编，等于把同一份数据
    来回搓 16 遍 —— 后端一个进程跑完整批，缓存在进程内就有效。
    """
    ref = _png(tmp_path, "anchor.png")
    reads = {"n": 0}
    real_read = Path.read_bytes

    def counting_read(self):
        if self.name == "anchor.png":
            reads["n"] += 1
        return real_read(self)

    monkeypatch.setattr(lb.Path, "read_bytes", counting_read)
    monkeypatch.setattr(lb.requests, "post",
                        lambda *a, **k: _FakeResp(payload=_image_payload()))
    lb._REF_CACHE.clear()

    for _ in range(3):
        lb._generate_one(
            "p", model="gemini-3.1-flash-image", api_key="k", base_url="https://x",
            aspect_ratio="1:1", seed=None, reference_paths=[str(ref)],
            image_path=None, timeout_s=5.0,
        )
    assert reads["n"] == 1, f"读了 {reads['n']} 次，应该只读 1 次"


def test_reference_cache_keyed_by_path(tmp_path, monkeypatch):
    """不同的锚图不能串味。"""
    a = _png(tmp_path, "a.png")
    b = tmp_path / "b.png"
    b.write_bytes(b"\x89PNG-different")
    seen = []

    def capture(url, headers=None, json=None, timeout=None, **k):
        parts = json["contents"][0]["parts"]
        seen.append(parts[0]["inline_data"]["data"])
        return _FakeResp(payload=_image_payload())

    monkeypatch.setattr(lb.requests, "post", capture)
    lb._REF_CACHE.clear()
    for ref in (a, b):
        lb._generate_one(
            "p", model="gemini-3.1-flash-image", api_key="k", base_url="https://x",
            aspect_ratio="1:1", seed=None, reference_paths=[str(ref)],
            image_path=None, timeout_s=5.0,
        )
    assert seen[0] != seen[1]


# -------------------- 进度与耗时 --------------------

def test_progress_shows_position_and_elapsed(tmp_path, capsys, monkeypatch):
    """跑十几张要几十分钟，得让人估得出还要多久。

    只打「[ok] 名字」不够 —— 看不出跑到第几张、单张多慢。
    """
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    monkeypatch.setattr(lb, "_generate_one", lambda *a, **k: b"png")
    out = tmp_path / "out"
    out.mkdir()
    batch = _batch(tmp_path, [
        {"name": f"n{i}", "filename": f"n{i}.png", "prompt": "p"} for i in range(3)
    ])
    lb.main([str(batch), "--output-dir", str(out)])

    out_text = capsys.readouterr().out
    assert "1/3" in out_text and "3/3" in out_text      # 位置
    assert "s)" in out_text                              # 单张耗时


def test_large_reference_warns_once(tmp_path, capsys, monkeypatch):
    """几 MB 的锚图每次请求都要传，值得提醒一句 —— 但只提醒一次，不是每张都吵。"""
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    big = tmp_path / "big.png"
    big.write_bytes(b"\x89PNG" + b"x" * (3 * 1024 * 1024))
    monkeypatch.setattr(lb, "_generate_one", lambda *a, **k: b"png")
    out = tmp_path / "out"
    out.mkdir()
    batch = _batch(
        tmp_path,
        [{"name": f"n{i}", "filename": f"n{i}.png", "prompt": "p"} for i in range(3)],
        defaults={"reference_paths": [str(big)]},
    )
    lb.main([str(batch), "--output-dir", str(out)])

    err = capsys.readouterr().err
    assert err.count("参考图") == 1          # 只说一次
    assert "MB" in err


def test_small_reference_does_not_warn(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    small = _png(tmp_path, "small.png")
    monkeypatch.setattr(lb, "_generate_one", lambda *a, **k: b"png")
    out = tmp_path / "out"
    out.mkdir()
    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}],
                   defaults={"reference_paths": [str(small)]})
    lb.main([str(batch), "--output-dir", str(out)])
    assert "参考图" not in capsys.readouterr().err



# -------------------- 4.4.0：mime 看内容；dry-run 按跳过规则计数 --------------------

@pytest.mark.parametrize("name, data, want", [
    ("a.webp", b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),   # 以前被标成 image/jpeg
    ("a.png", b"\xff\xd8\xff\xe0rest", "image/jpeg"),            # 改过扩展名的 JPEG
    ("a.jpg", b"\x89PNG\r\n\x1a\nrest", "image/png"),
    ("a.png", b"????????", "image/png"),                             # 认不出：退回按扩展名
    ("a.bin", b"????????", "image/jpeg"),
])
def test_mime_follows_content_not_extension(name, data, want):
    import laozhang_backend as lb
    assert lb._sniff_mime(data, name) == want


def test_dry_run_counts_existing_targets_as_skipped(tmp_path, capsys):
    """以前 dry-run 先打 [plan] 再判断跳过，于是永远 skipped=0。"""
    import laozhang_backend as lb
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.png").write_bytes(b"old")
    batch = tmp_path / "b.json"
    batch.write_text(json.dumps({"$schema_version": 2, "defaults": {}, "assets": [
        {"name": "a", "filename": "a.png", "prompt": "x"},
        {"name": "b", "filename": "b.png", "prompt": "y"},
    ]}), encoding="utf-8")
    lb.main([str(batch), "--output-dir", str(out), "--dry-run"])
    captured = capsys.readouterr().out
    summary = json.loads(captured.strip().splitlines()[-1])
    assert summary["skipped"] == 1
    assert "正式跑会跳过" in captured


def test_gpt_image_edit_labels_base_image_by_content(tmp_path, monkeypatch):
    """OpenAI 编辑路径也按内容定 mime。

    变异验证抓出来的：上面那条测试截获了 files，却从没看过底图的 mime ——
    把这条路径改回按扩展名，全部测试照样绿。
    """
    base = tmp_path / "renamed.png"
    base.write_bytes(bytes([0xFF, 0xD8, 0xFF, 0xE0]) + b"jpeg-body")   # 其实是 JPEG
    seen = {}

    def fake_post(url, headers=None, files=None, timeout=None, **kw):
        seen["files"] = files
        return _FakeResp(payload={"data": [{"b64_json": "aGk="}]})

    monkeypatch.setattr(lb.requests, "post", fake_post)
    lb._generate_one(
        "edit", model="gpt-image-2.5-flare", api_key="k",
        base_url="https://x", aspect_ratio="1:1", seed=None,
        reference_paths=[], image_path=str(base), timeout_s=30.0,
    )
    assert seen["files"]["image"][2] == "image/jpeg"
