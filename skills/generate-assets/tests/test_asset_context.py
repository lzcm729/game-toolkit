"""asset_context — 项目上下文解析（校验器和生成器共用的那一份）。"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import asset_context
import engine_adapter


def _write(path: Path, conf: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(conf, sort_keys=False, allow_unicode=True),
                    encoding="utf-8")
    return path


# -------------------- locate_config --------------------

def test_locate_prefers_top_level(tmp_path):
    (tmp_path / "asset-config.yaml").write_text("a: 1", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "asset-config.yaml").write_text("a: 2", encoding="utf-8")
    assert asset_context.locate_config(None, cwd=tmp_path) == tmp_path / "asset-config.yaml"


def test_locate_falls_back_to_assets_dir(tmp_path):
    (tmp_path / "assets").mkdir()
    p = tmp_path / "assets" / "asset-config.yaml"
    p.write_text("a: 1", encoding="utf-8")
    assert asset_context.locate_config(None, cwd=tmp_path) == p


def test_locate_explicit_missing_returns_none(tmp_path):
    """显式给了就只认那一个 —— 不能悄悄改去用默认位置的另一份配置。"""
    (tmp_path / "asset-config.yaml").write_text("a: 1", encoding="utf-8")
    assert asset_context.locate_config(tmp_path / "nope.yaml") is None


def test_locate_none_when_nothing_found(tmp_path):
    assert asset_context.locate_config(None, cwd=tmp_path) is None


# -------------------- load_config --------------------

def test_load_config_reports_line_number(tmp_path):
    p = tmp_path / "asset-config.yaml"
    p.write_text("a: 1\nb: [unclosed\n", encoding="utf-8")
    with pytest.raises(asset_context.ContextError, match="第 "):
        asset_context.load_config(p)


def test_load_config_rejects_non_mapping(tmp_path):
    p = tmp_path / "asset-config.yaml"
    p.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(asset_context.ContextError, match="顶层必须是映射"):
        asset_context.load_config(p)


def test_load_config_empty_file_is_empty_mapping(tmp_path):
    p = tmp_path / "asset-config.yaml"
    p.write_text("", encoding="utf-8")
    assert asset_context.load_config(p) == {}


def test_load_config_missing_file(tmp_path):
    with pytest.raises(asset_context.ContextError, match="不存在"):
        asset_context.load_config(tmp_path / "nope.yaml")


# -------------------- resolve_project_root 的四级优先级 --------------------

def test_root_explicit_wins(tmp_path):
    cfg = _write(tmp_path / "asset-config.yaml", {"project_root": "sub"})
    other = tmp_path / "elsewhere"
    other.mkdir()
    root, source = asset_context.resolve_project_root(
        cfg, {"project_root": "sub"}, engine_adapter.GENERIC, explicit=other)
    assert root == other.resolve()
    assert "--project-root" in source


def test_root_declared_is_relative_to_config_dir(tmp_path):
    """config 里的 project_root 相对 config 所在目录 —— 不是相对 CWD。"""
    cfg = _write(tmp_path / "tools" / "asset-config.yaml", {"project_root": ".."})
    root, source = asset_context.resolve_project_root(
        cfg, {"project_root": ".."}, engine_adapter.GENERIC)
    assert root == tmp_path.resolve()
    assert "project_root" in source


def test_root_falls_back_to_adapter_detection(tmp_path):
    (tmp_path / "project.godot").write_text("[application]\n", encoding="utf-8")
    cfg = _write(tmp_path / "assets" / "asset-config.yaml", {"adapter": "godot"})
    root, source = asset_context.resolve_project_root(cfg, {"adapter": "godot"},
                                                      engine_adapter.GODOT)
    assert root == tmp_path.resolve()
    assert "探测" in source


def test_root_assets_dir_implies_parent(tmp_path):
    cfg = _write(tmp_path / "assets" / "asset-config.yaml", {"adapter": "generic"})
    root, source = asset_context.resolve_project_root(cfg, {"adapter": "generic"},
                                                      engine_adapter.GENERIC)
    assert root == tmp_path.resolve()
    assert "assets/" in source


def test_root_plain_dir_is_config_dir(tmp_path):
    cfg = _write(tmp_path / "asset-config.yaml", {"adapter": "generic"})
    root, _ = asset_context.resolve_project_root(cfg, {"adapter": "generic"},
                                                 engine_adapter.GENERIC)
    assert root == tmp_path.resolve()


# -------------------- load_context 整体 --------------------

def test_context_honours_declared_project_root(tmp_path):
    """**回归**：工程根来自 config 的声明，不是 config 的父目录。

    3.16.0 之前校验器直接取 config 父目录，生成器走四级回退。config 放在
    子目录时两者算出的根不同，于是所有相对路径（output_root、参考图、
    数据源）的基准都不同 —— 同一份配置检查一个位置、跑另一个位置。
    """
    conf = {"adapter": "generic", "project_root": "..", "output_root": "art",
            "categories": {}}
    cfg = _write(tmp_path / "tools" / "asset-config.yaml", conf)
    ctx = asset_context.load_context(cfg)
    assert ctx.project_root == tmp_path.resolve()
    assert ctx.output_root == (tmp_path / "art").resolve()


def test_context_explicit_override_is_reported(tmp_path):
    conf = {"adapter": "generic", "project_root": "..", "output_root": "art"}
    cfg = _write(tmp_path / "tools" / "asset-config.yaml", conf)
    other = tmp_path / "other"
    other.mkdir()
    ctx = asset_context.load_context(cfg, explicit_project_root=other)
    assert ctx.project_root == other.resolve()
    # 覆盖了就得说出来 —— 悄悄换基准和解析错基准一样难查
    assert "--project-root" in ctx.project_root_source


def test_context_output_root_must_be_string(tmp_path):
    cfg = _write(tmp_path / "asset-config.yaml",
                 {"adapter": "generic", "output_root": ["a"]})
    with pytest.raises(asset_context.ContextError, match="output_root 应为字符串"):
        asset_context.load_context(cfg)


def test_context_rejects_engine_prefix_under_generic(tmp_path):
    cfg = _write(tmp_path / "asset-config.yaml",
                 {"adapter": "generic", "output_root": "res://art"})
    with pytest.raises(asset_context.ContextError, match="output_root 解析失败"):
        asset_context.load_context(cfg)


def test_context_propagates_unknown_backend(tmp_path):
    cfg = _write(tmp_path / "asset-config.yaml",
                 {"adapter": "generic", "backend": "nope"})
    with pytest.raises(asset_context.ContextError, match="未知的 backend"):
        asset_context.load_context(cfg)


def test_context_propagates_adapter_conflict(tmp_path):
    cfg = _write(tmp_path / "asset-config.yaml",
                 {"adapter": "generic", "engine": "godot"})
    with pytest.raises(asset_context.ContextError, match="engine 是 adapter 的旧名"):
        asset_context.load_context(cfg)


def test_context_reuses_preloaded_config(tmp_path):
    """给了 config 就不再读盘 —— 调用方已经读过一遍的不该读第二遍。"""
    cfg = tmp_path / "asset-config.yaml"
    cfg.write_text("!!! not yaml at all: [", encoding="utf-8")
    ctx = asset_context.load_context(cfg, config={"adapter": "generic"})
    assert ctx.adapter.name == "generic"
