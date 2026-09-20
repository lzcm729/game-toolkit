"""后端注册表与选择。"""
from __future__ import annotations

from pathlib import Path

import pytest

import image_backend


def test_default_is_image_gen(tmp_path, monkeypatch):
    """config 没写 backend 且没有环境变量 → image-gen（保持既有行为）。"""
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    be = image_backend.select({}, tmp_path)
    assert be.name == "image-gen"


def test_env_var_wins_over_config(tmp_path, monkeypatch):
    """IMAGE_GEN_SCRIPT 优先级最高——conftest 的 mock fixture 依赖这条。"""
    script = tmp_path / "fake.py"
    script.write_text("# stub\n", encoding="utf-8")
    monkeypatch.setenv("IMAGE_GEN_SCRIPT", str(script))
    be = image_backend.select({"backend": "laozhang"}, tmp_path)
    assert be.resolve_script() == script
    # 环境变量指过来的脚本能力未知，按全集处理，不误报降级
    assert be.supports == image_backend.ALL_FIELDS


def test_config_backend_name(tmp_path, monkeypatch):
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    be = image_backend.select({"backend": "laozhang"}, tmp_path)
    assert be.name == "laozhang"
    assert "chain" not in be.supports
    assert "reference_paths" in be.supports


def test_unknown_backend_lists_options(tmp_path, monkeypatch):
    """报错必须列出可选项——只说'不认识'的话人还得去翻源码。"""
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    with pytest.raises(ValueError) as ei:
        image_backend.select({"backend": "midjourney"}, tmp_path)
    msg = str(ei.value)
    assert "midjourney" in msg
    assert "image-gen" in msg and "laozhang" in msg


def test_path_backend_relative_to_project_root(tmp_path, monkeypatch):
    """相对路径以 project_root 为基准，不是 cwd、不是 config 目录。"""
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    script = tmp_path / "tools" / "my_backend.py"
    script.parent.mkdir(parents=True)
    script.write_text("# stub\n", encoding="utf-8")
    be = image_backend.select({"backend": "tools/my_backend.py"}, tmp_path)
    assert be.resolve_script() == script.resolve()
    assert be.supports == image_backend.ALL_FIELDS


def test_path_backend_missing_reports_path(tmp_path, monkeypatch):
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    be = image_backend.select({"backend": "tools/absent.py"}, tmp_path)
    assert be.resolve_script() is None
    assert "absent.py" in be.install_hint


def test_env_script_relative_path_is_absolutized(tmp_path, monkeypatch):
    """后端在 project_root 下跑，脚本路径若留作相对的，两边基准就不一致：
    存在性检查按调用者 CWD 过了，子进程却去 project_root 下找。"""
    launcher = tmp_path / "launcher"
    (launcher / "tools").mkdir(parents=True)
    (launcher / "tools" / "backend.py").write_text("# real\n", encoding="utf-8")
    game = tmp_path / "game"
    game.mkdir()

    monkeypatch.chdir(launcher)
    monkeypatch.setenv("IMAGE_GEN_SCRIPT", "tools/backend.py")

    script = image_backend.select({}, game).resolve_script()
    assert script is not None
    assert script.is_absolute(), f"必须绝对化，否则子进程解析基准不同：{script}"
    assert script == (launcher / "tools" / "backend.py").resolve()
