"""pytest fixtures：把 skill scripts 加进 sys.path + mock subprocess.run。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """空白 Godot 项目（含 project.godot），返回项目根。"""
    (tmp_path / "project.godot").write_text(
        "; engine=4.6\n[application]\nconfig/name=\"test\"\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def write_json(tmp_path: Path):
    """工厂：在 tmp 里写 JSON，返回 path。"""
    def _write(rel: str, data) -> Path:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return p
    return _write


@pytest.fixture
def fake_image_gen_summary():
    """构造一个"成功"的 image-gen JSON summary。"""
    def _make(*, total=1, success=1, failed=0, skipped=0):
        return {
            "total": total,
            "success": success,
            "failed": failed,
            "skipped": skipped,
            "failed_assets": [],
            "manifest": "/tmp/manifest.jsonl",
        }
    return _make


@pytest.fixture
def mock_subprocess_run(monkeypatch, fake_image_gen_summary):
    """替换 subprocess.run，记录调用并返回伪 stdout（含 JSON summary）。

    用法：
        def test_x(mock_subprocess_run):
            calls, set_result = mock_subprocess_run
            set_result(returncode=0, summary={"total": 3, "success": 3, ...})
            ...
            assert len(calls) == 1
    """
    import subprocess as _sp

    state = {
        "returncode": 0,
        "summary": fake_image_gen_summary(),
        "stderr": "",
    }
    calls: list[dict] = []

    def set_result(*, returncode=0, summary=None, stderr=""):
        state["returncode"] = returncode
        if summary is not None:
            state["summary"] = summary
        state["stderr"] = stderr

    class FakeProc:
        def __init__(self, args, returncode, stdout, stderr):
            self.args = args
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(cmd, *args, **kwargs):
        calls.append({"cmd": list(cmd), "args": args, "kwargs": kwargs})
        body = "[mock image-gen] running...\n"
        body += json.dumps(state["summary"]) + "\n"
        return FakeProc(cmd, state["returncode"], body, state["stderr"])

    monkeypatch.setattr(_sp, "run", fake_run)
    # 同时给主模块导入路径里的 subprocess 也打 patch
    import generate_assets as ga  # noqa: WPS433
    monkeypatch.setattr(ga.subprocess, "run", fake_run)

    return calls, set_result
