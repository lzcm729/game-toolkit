"""engine_adapter — 工程探测、路径解析、导入提示、适配器选择。

3.17.0 把这四件从一个 EngineAdapter 里拆开了，所以测试也按四件分组：
「切换路径处理能力」不该顺带换掉工程根，这是拆分的全部理由。
"""
from __future__ import annotations

from pathlib import Path

import pytest

import engine_adapter


def _uproject(d: Path) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "Catfishing.uproject").write_text("{}", encoding="utf-8")
    return d


def _godot(d: Path) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "project.godot").write_text("[application]\n", encoding="utf-8")
    return d


# -------------------- 工程探测：与选哪个适配器无关 --------------------

def test_detect_unreal_project(tmp_path):
    _uproject(tmp_path)
    assert engine_adapter.detect_project(tmp_path) == ("unreal", tmp_path.resolve())


def test_detect_godot_project(tmp_path):
    _godot(tmp_path)
    assert engine_adapter.detect_project(tmp_path) == ("godot", tmp_path.resolve())


def test_detect_walks_up_from_subdirectory(tmp_path):
    """config 放子目录时，工程根仍要向上找 —— 否则所有相对路径的基准全错。"""
    _uproject(tmp_path)
    deep = tmp_path / "tools" / "assets"
    deep.mkdir(parents=True)
    assert engine_adapter.detect_project(deep) == ("unreal", tmp_path.resolve())


def test_detect_accepts_a_file_as_start(tmp_path):
    _godot(tmp_path)
    f = tmp_path / "sub" / "asset-config.yaml"
    f.parent.mkdir()
    f.write_text("a: 1", encoding="utf-8")
    assert engine_adapter.detect_project(f) == ("godot", tmp_path.resolve())


def test_detect_returns_none_when_no_marker(tmp_path):
    assert engine_adapter.detect_project(tmp_path) == (None, None)


def test_detect_stops_at_the_nearest_project(tmp_path):
    """嵌套时取最近的那个 —— 一次走完、每层看全部标志，才不会两种搜索给出不同答案。"""
    _uproject(tmp_path)
    inner = _godot(tmp_path / "SubGame")
    assert engine_adapter.detect_project(inner) == ("godot", inner.resolve())


def test_project_kind_does_not_walk_up(tmp_path):
    """project_kind 只看这一层。工程根已经定下来之后，问的是「这里是什么」。"""
    _uproject(tmp_path)
    sub = tmp_path / "sub"
    sub.mkdir()
    assert engine_adapter.project_kind(sub) is None
    assert engine_adapter.project_kind(tmp_path) == "unreal"


# -------------------- 路径解析：只管路径 --------------------

def test_godot_resolves_res_prefix(tmp_path):
    assert engine_adapter.GODOT.resolve_path("res://art/x.png", tmp_path) == \
        (tmp_path / "art" / "x.png").resolve()


def test_generic_accepts_plain_relative_path(tmp_path):
    assert engine_adapter.GENERIC.resolve_path("ArtSource/Fish", tmp_path) == \
        (tmp_path / "ArtSource" / "Fish").resolve()


def test_generic_accepts_absolute_path(tmp_path):
    target = tmp_path / "out"
    assert engine_adapter.GENERIC.resolve_path(str(target), tmp_path) == target


def test_generic_suggests_switching_to_godot_for_res(tmp_path):
    """godot 真的认 res://，这条建议有效。"""
    with pytest.raises(ValueError) as ei:
        engine_adapter.GENERIC.resolve_path("res://art", tmp_path)
    assert "adapter 改成 godot" in str(ei.value)


def test_generic_rejects_game_prefix_as_post_import_path(tmp_path):
    """/Game/ 不是「换个适配器就能用」，是根本不该出现在源文件配置里。

    所以不能说「没有 unreal 适配」—— 那会让人去找一个并不存在的开关。
    """
    with pytest.raises(ValueError) as ei:
        engine_adapter.GENERIC.resolve_path("/Game/Art", tmp_path)
    msg = str(ei.value)
    assert "导入" in msg and "Content" in msg
    assert "没有任何适配器认它" in msg
    assert "adapter 改成 unreal" not in msg
    assert "没有 unreal" not in msg


# -------------------- 导入提示：按探测到的工程给 --------------------

def test_import_hint_for_unreal_states_the_boundary(tmp_path):
    hint = engine_adapter.import_hint("unreal", tmp_path)
    assert hint is not None
    assert "导入" in hint and str(tmp_path) in hint
    # 它陈述边界，不伪装成检查结果
    assert "不检查导入状态" in hint


def test_import_hint_for_godot_counts_import_files(tmp_project):
    out = tmp_project / "art"
    out.mkdir()
    (out / "a.png").write_bytes(b"png")
    hint = engine_adapter.import_hint("godot", out)
    assert hint is not None and ".import" in hint


def test_import_hint_none_when_kind_unknown(tmp_path):
    assert engine_adapter.import_hint(None, tmp_path) is None


def test_unreal_project_using_generic_adapter_still_gets_the_hint(tmp_path):
    """**这是拆分换来的能力**：提示跟着工程走，不跟着适配器走。

    以前只有 `adapter: unreal` 能拿到那句提示；UE 项目写 generic
    （完全正常的选择）就什么都看不到。
    """
    assert engine_adapter.select({"adapter": "generic"}, "unreal") is engine_adapter.GENERIC
    assert engine_adapter.import_hint("unreal", tmp_path) is not None


# -------------------- 选择 --------------------

def test_select_defaults_to_godot_for_godot_project():
    assert engine_adapter.select({}, "godot") is engine_adapter.GODOT


def test_select_defaults_to_generic_for_unreal_project():
    """多对一是正常的：只有 Godot 需要一套自己的路径写法。"""
    assert engine_adapter.select({}, "unreal") is engine_adapter.GENERIC


def test_select_defaults_to_generic_when_undetected():
    assert engine_adapter.select({}, None) is engine_adapter.GENERIC


def test_declared_adapter_beats_detection():
    """Godot 项目显式选 generic 是合法的，不该被探测结果推翻。"""
    assert engine_adapter.select({"adapter": "generic"}, "godot") is engine_adapter.GENERIC


def test_legacy_unreal_maps_to_generic():
    assert engine_adapter.select({"adapter": "unreal"}, None) is engine_adapter.GENERIC


def test_legacy_unreal_is_not_in_the_adapter_registry():
    """它不再是一个可选适配器，只是仍然被接受的旧值。"""
    assert "unreal" not in engine_adapter.ADAPTERS
    assert engine_adapter.LEGACY_ADAPTERS["unreal"] == "generic"


def test_legacy_note_explains_the_equivalence():
    note = engine_adapter.legacy_note({"adapter": "unreal"})
    assert note is not None
    assert "兼容值" in note and "generic" in note


def test_legacy_note_is_none_for_current_values():
    assert engine_adapter.legacy_note({"adapter": "generic"}) is None
    assert engine_adapter.legacy_note({}) is None


def test_engine_is_accepted_as_the_old_name():
    assert engine_adapter.select({"engine": "godot"}, None) is engine_adapter.GODOT


def test_conflicting_adapter_and_engine_is_an_error():
    with pytest.raises(ValueError, match="engine 是 adapter 的旧名"):
        engine_adapter.select({"adapter": "generic", "engine": "godot"}, None)


def test_unknown_adapter_lists_options_and_legacy(tmp_path):
    with pytest.raises(ValueError) as ei:
        engine_adapter.select({"adapter": "unity"}, None)
    msg = str(ei.value)
    assert "generic" in msg and "godot" in msg
    assert "unreal" in msg and "兼容值" in msg
