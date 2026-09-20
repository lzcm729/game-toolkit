"""engine_adapter — 适配器选择、路径解析、工程根探测。"""
from __future__ import annotations

from pathlib import Path

import pytest

import engine_adapter


# -------------------- unreal 工程根探测 --------------------

def test_unreal_detects_uproject(tmp_path):
    (tmp_path / "Catfishing.uproject").write_text("{}", encoding="utf-8")
    assert engine_adapter.UNREAL.detect_root(tmp_path) == tmp_path.resolve()


def test_unreal_detects_from_subdirectory(tmp_path):
    """config 放在子目录时，工程根靠 generic 的 fallback 会推成子目录本身。"""
    (tmp_path / "Catfishing.uproject").write_text("{}", encoding="utf-8")
    deep = tmp_path / "tools" / "assets"
    deep.mkdir(parents=True)
    assert engine_adapter.UNREAL.detect_root(deep) == tmp_path.resolve()


def test_unreal_detect_root_returns_none_when_absent(tmp_path):
    assert engine_adapter.UNREAL.detect_root(tmp_path) is None


# -------------------- unreal 路径解析 --------------------

def test_unreal_rejects_game_prefix_with_reason(tmp_path):
    """/Game/ 是导入后的资产路径，这里产出的是导入前的源图片。"""
    with pytest.raises(ValueError) as ei:
        engine_adapter.UNREAL.resolve_path("/Game/Art/Fish", tmp_path)
    msg = str(ei.value)
    assert "/Game/" in msg
    assert "导入" in msg          # 说清为什么不支持
    assert "Content" in msg       # 指出它实际指向哪


def test_unreal_accepts_plain_relative_path(tmp_path):
    got = engine_adapter.UNREAL.resolve_path("ArtSource/Fish", tmp_path)
    assert got == (tmp_path / "ArtSource" / "Fish").resolve()


def test_unreal_accepts_absolute_path(tmp_path):
    target = tmp_path / "out"
    assert engine_adapter.UNREAL.resolve_path(str(target), tmp_path) == target


def test_unreal_still_rejects_res_prefix(tmp_path):
    """别的引擎的前缀照样不认。"""
    with pytest.raises(ValueError) as ei:
        engine_adapter.UNREAL.resolve_path("res://art", tmp_path)
    assert "res://" in str(ei.value)


# -------------------- generic 撞见 /Game/ 时不该指错路 --------------------

def test_generic_does_not_suggest_switching_to_unreal(tmp_path):
    """unreal 注册了，但它同样不认 /Game/ —— 不能建议人切过去。"""
    with pytest.raises(ValueError) as ei:
        engine_adapter.GENERIC.resolve_path("/Game/Art", tmp_path)
    msg = str(ei.value)
    assert "adapter 改成 unreal" not in msg
    assert "普通相对路径" in msg


def test_generic_still_suggests_switching_to_godot(tmp_path):
    """godot 真的认 res://，这条建议仍然有效。"""
    with pytest.raises(ValueError) as ei:
        engine_adapter.GENERIC.resolve_path("res://art", tmp_path)
    assert "adapter 改成 godot" in str(ei.value)


# -------------------- 注册与选择 --------------------

def test_unreal_is_registered():
    assert engine_adapter.ADAPTERS["unreal"] is engine_adapter.UNREAL


def test_select_unreal_by_name(tmp_path):
    assert engine_adapter.select({"adapter": "unreal"}, tmp_path) is engine_adapter.UNREAL


def test_unknown_adapter_lists_unreal(tmp_path):
    with pytest.raises(ValueError) as ei:
        engine_adapter.select({"adapter": "unity"}, tmp_path)
    assert "unreal" in str(ei.value)


# -------------------- 生成后提示 --------------------

def test_unreal_hint_mentions_import(tmp_path):
    hint = engine_adapter.UNREAL.post_generate_hint(tmp_path)
    assert hint is not None
    assert "导入" in hint
    assert str(tmp_path) in hint


def test_godot_hint_unaffected(tmp_project):
    """加 unreal 不该影响 godot 的行为。"""
    out = tmp_project / "art"
    out.mkdir()
    (out / "a.png").write_bytes(b"png")
    hint = engine_adapter.GODOT.post_generate_hint(out)
    assert hint is not None and ".import" in hint
