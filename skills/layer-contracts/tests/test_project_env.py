# -*- coding: utf-8 -*-
"""project_env.py 的回归测试。

这个脚本会写进别人项目的 game-toolkit.yaml，所以「重写整个文件时不丢用户加的
字段」「多行文本能原样往返」这两条必须锁住。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import project_env as pe  # noqa: E402


def _check(root, capsys):
    pe.main(["check", str(root)])
    return json.loads(capsys.readouterr().out)


def _write_yaml(root: Path, data: dict):
    (root / pe.CONFIG_NAME).write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _load(root: Path) -> dict:
    return yaml.safe_load((root / pe.CONFIG_NAME).read_text(encoding="utf-8"))


# -------------------- 状态判定 --------------------

def test_no_config_is_missing(tmp_path, capsys):
    out = _check(tmp_path, capsys)
    assert out["status"] == "missing"
    assert out["config_exists"] is False
    assert set(out["missing_required"]) == {"engine", "engine_version", "project_root"}


def test_complete_declaration_is_ok(tmp_path, capsys):
    _write_yaml(tmp_path, {"engine": "unreal", "engine_version": "5.8", "project_root": "."})
    out = _check(tmp_path, capsys)
    assert out["status"] == "ok"
    assert out["missing_required"] == []
    assert out["declared"]["engine"] == "unreal"


def test_placeholder_counts_as_missing(tmp_path, capsys):
    """写「待核实」不等于填了。"""
    _write_yaml(tmp_path, {"engine": "unreal", "engine_version": "待核实", "project_root": "."})
    out = _check(tmp_path, capsys)
    assert out["status"] == "incomplete"
    assert out["missing_required"] == ["engine_version"]


def test_malformed_yaml_does_not_crash(tmp_path, capsys):
    (tmp_path / pe.CONFIG_NAME).write_text("engine: [unclosed\n", encoding="utf-8")
    out = _check(tmp_path, capsys)
    assert out["status"] == "missing"          # 读不出来就当没声明，不抛异常


def test_yaml_that_is_not_a_mapping_is_ignored(tmp_path, capsys):
    (tmp_path / pe.CONFIG_NAME).write_text("- 就是个列表\n", encoding="utf-8")
    out = _check(tmp_path, capsys)
    assert out["declared"] == {}


# -------------------- 探测 --------------------

def test_detects_unreal_and_version(tmp_path, capsys):
    (tmp_path / "Game.uproject").write_text(
        json.dumps({"EngineAssociation": "5.8",
                    "Modules": [{"Name": "Game"}, {"Name": "GameEditor"}]}),
        encoding="utf-8")
    out = _check(tmp_path, capsys)
    assert out["detected"]["engine"] == "unreal"
    assert out["detected"]["engine_version"] == "5.8"
    assert any("Game, GameEditor" in e for e in out["detected"]["evidence"])


def test_non_numeric_engine_association_is_not_a_version(tmp_path, capsys):
    """源码版引擎的 EngineAssociation 是 GUID，不能当版本号填进去。"""
    (tmp_path / "Game.uproject").write_text(
        json.dumps({"EngineAssociation": "{A1B2C3D4-0000-0000-0000-000000000000}"}),
        encoding="utf-8")
    out = _check(tmp_path, capsys)
    assert "engine_version" not in out["detected"]
    assert any("需人工确认" in e for e in out["detected"]["evidence"])


def test_multiple_uprojects_flagged(tmp_path, capsys):
    for name in ("A.uproject", "B.uproject"):
        (tmp_path / name).write_text(json.dumps({"EngineAssociation": "5.8"}), encoding="utf-8")
    out = _check(tmp_path, capsys)
    assert any("需人工指定" in e for e in out["detected"]["evidence"])


def test_sln_next_to_uproject_is_called_out(tmp_path, capsys):
    """UE 会自动生成 .sln —— 不能据此推断这是 .NET 项目。"""
    (tmp_path / "Game.uproject").write_text(json.dumps({"EngineAssociation": "5.8"}), encoding="utf-8")
    (tmp_path / "Game.sln").write_text("", encoding="utf-8")
    out = _check(tmp_path, capsys)
    assert any("dotnet build" in e for e in out["detected"]["evidence"])


def test_detects_godot(tmp_path, capsys):
    (tmp_path / "project.godot").write_text(
        'config/features=PackedStringArray("4.3", "GL Compatibility")\n', encoding="utf-8")
    out = _check(tmp_path, capsys)
    assert out["detected"]["engine"] == "godot"
    assert out["detected"]["engine_version"] == "4.3"


def test_binary_assets_produce_inspectability_hint(tmp_path, capsys):
    (tmp_path / "Game.uproject").write_text(json.dumps({"EngineAssociation": "5.8"}), encoding="utf-8")
    content = tmp_path / "Content"
    content.mkdir()
    (content / "BP_A.uasset").write_bytes(b"\x00")
    (content / "Main.umap").write_bytes(b"\x00")
    out = _check(tmp_path, capsys)
    assert "查不了" in out["detected"]["inspectability_hint"]


# -------------------- 写入 --------------------

def test_write_creates_valid_yaml(tmp_path, capsys):
    pe.main(["write", str(tmp_path), "--engine", "unreal", "--engine-version", "5.8"])
    data = _load(tmp_path)
    assert data["engine"] == "unreal"
    assert data["engine_version"] == "5.8"
    assert data["project_root"] == "待核实"      # 必填项缺失时留占位，不静默省略


def test_write_keeps_comments_and_is_idempotent(tmp_path):
    for _ in range(3):
        pe.main(["write", str(tmp_path), "--engine", "unreal", "--engine-version", "5.8"])
    text = (tmp_path / pe.CONFIG_NAME).read_text(encoding="utf-8")
    assert text.count("# Game Toolkit 项目环境声明") == 1   # 不重复堆头部
    assert "# 引擎：godot / unreal" in text                 # 注释每次都在
    assert yaml.safe_load(text)["engine"] == "unreal"


def test_write_merges_with_existing_fields(tmp_path):
    pe.main(["write", str(tmp_path), "--engine", "unreal", "--engine-version", "5.8",
             "--project-root", "."])
    pe.main(["write", str(tmp_path), "--verify-entry", "尚未登记"])
    data = _load(tmp_path)
    assert data["engine"] == "unreal"          # 上一轮的值没被冲掉
    assert data["verify_entry"] == "尚未登记"


def test_unknown_fields_survive_rewrite(tmp_path):
    """整文件重渲染不能吃掉用户自己加的字段。"""
    _write_yaml(tmp_path, {"engine": "godot", "engine_version": "4.3",
                           "project_root": ".", "我自己加的": "别删我"})
    pe.main(["write", str(tmp_path), "--verify-entry", "gdunit4"])
    data = _load(tmp_path)
    assert data["我自己加的"] == "别删我"
    assert data["verify_entry"] == "gdunit4"


def test_multiline_value_round_trips(tmp_path):
    long = "C++ 可按文本扫；\nBlueprint / .uasset 查不了 —— 不得据文本结果判定缺失"
    pe.main(["write", str(tmp_path), "--engine", "unreal", "--inspectability", long])
    assert _load(tmp_path)["inspectability"] == long


def test_write_requires_at_least_one_field(tmp_path):
    assert pe.main(["write", str(tmp_path)]) == 2


def test_check_on_missing_dir_returns_error(tmp_path, capsys):
    assert pe.main(["check", str(tmp_path / "nope")]) == 2
    assert "目录不存在" in capsys.readouterr().out
