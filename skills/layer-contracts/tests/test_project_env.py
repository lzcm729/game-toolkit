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


def test_malformed_yaml_is_invalid_not_missing(tmp_path, capsys):
    """曾经把「读不出来」当成「没声明」，于是 write 把损坏文件当空配置覆盖掉。"""
    (tmp_path / pe.CONFIG_NAME).write_text("engine: [unclosed\n", encoding="utf-8")
    out = _check(tmp_path, capsys)
    assert out["status"] == "invalid"
    assert "YAML 解析失败" in out["error"]


def test_yaml_that_is_not_a_mapping_is_invalid(tmp_path, capsys):
    (tmp_path / pe.CONFIG_NAME).write_text("- 就是个列表\n", encoding="utf-8")
    out = _check(tmp_path, capsys)
    assert out["status"] == "invalid"
    assert "顶层不是键值映射" in out["error"]


def test_write_refuses_to_clobber_a_broken_file(tmp_path):
    """核心回归：只改一个字段，不能把读不回来的原文件整个重写掉。"""
    p = tmp_path / pe.CONFIG_NAME
    original = ("engine: unreal\nengine_version: '5.8'\nproject_root: .\n"
                "我的自定义字段: 很重要别删\nbroken: [unclosed\n")
    p.write_text(original, encoding="utf-8")
    assert pe.main(["write", str(tmp_path), "--engine-version", "5.9"]) == 1
    assert p.read_text(encoding="utf-8") == original      # 一个字都没动


def test_force_overrides_the_refusal(tmp_path):
    p = tmp_path / pe.CONFIG_NAME
    p.write_text("broken: [unclosed\n", encoding="utf-8")
    assert pe.main(["write", str(tmp_path), "--force", "--engine", "godot"]) == 0
    assert _load(tmp_path)["engine"] == "godot"


def test_type_errors_are_reported(tmp_path, capsys):
    """engine: [] 和 engine_version: false 曾经照样返回 ok。"""
    _write_yaml(tmp_path, {"engine": [], "engine_version": False, "project_root": ["absent"]})
    out = _check(tmp_path, capsys)
    assert out["status"] == "invalid"
    assert len(out["issues"]) == 3


def test_numeric_version_is_flagged(tmp_path, capsys):
    """5.10 不加引号会被 YAML 读成 5.1 —— 静默固化成错误版本。"""
    (tmp_path / pe.CONFIG_NAME).write_text(
        "engine: unreal\nengine_version: 5.10\nproject_root: .\n", encoding="utf-8")
    out = _check(tmp_path, capsys)
    assert out["status"] == "invalid"
    assert any("加引号" in i for i in out["issues"])


def test_date_value_does_not_break_json_output(tmp_path, capsys):
    """PyYAML 把 2026-09-07 读成 date 对象，json.dumps 会抛 TypeError。"""
    (tmp_path / pe.CONFIG_NAME).write_text(
        "engine: unreal\nengine_version: '5.8'\nproject_root: .\nreviewed_at: 2026-09-07\n",
        encoding="utf-8")
    out = _check(tmp_path, capsys)
    assert out["declared"]["reviewed_at"] == "2026-09-07"


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


def test_text_serialized_assets_are_not_lumped_with_binary(tmp_path, capsys):
    """.tscn 是文本，能读节点和属性 —— 跟 .uasset 归成一句「都读不懂」会白挡掉可做的检查。"""
    (tmp_path / "project.godot").write_text("config/features=PackedStringArray(\"4.3\")\n",
                                            encoding="utf-8")
    (tmp_path / "Main.tscn").write_text("[gd_scene]\n", encoding="utf-8")
    hint = _check(tmp_path, capsys)["detected"]["inspectability_hint"]
    assert "可读节点" in hint
    assert "二进制资产" not in hint


def test_generated_dirs_counted_separately(tmp_path, capsys):
    """Intermediate / Saved 里的文件不能算进正式源码范围。"""
    (tmp_path / "Game.uproject").write_text(json.dumps({"EngineAssociation": "5.8"}), encoding="utf-8")
    for d, n in (("Source", 2), ("Intermediate", 5)):
        (tmp_path / d).mkdir()
        for i in range(n):
            (tmp_path / d / ("f%d.cpp" % i)).write_text("", encoding="utf-8")
    det = _check(tmp_path, capsys)["detected"]
    assert det["source_counts"][".cpp"] == 2
    assert det["generated_or_ignored"][".cpp"] == 5


def test_multiple_engine_markers_give_no_single_candidate(tmp_path, capsys):
    """两个工程版本不同时，不能只报排序第一个的版本。"""
    (tmp_path / "A.uproject").write_text(json.dumps({"EngineAssociation": "5.6"}), encoding="utf-8")
    (tmp_path / "B.uproject").write_text(json.dumps({"EngineAssociation": "5.8"}), encoding="utf-8")
    det = _check(tmp_path, capsys)["detected"]
    assert "engine_version" not in det
    assert len(det["candidates"]) == 2
    assert {c.get("engine_version") for c in det["candidates"]} == {"5.6", "5.8"}


def test_detection_follows_declared_project_root(tmp_path, capsys):
    """声明了 project_root 就该去那儿探测，而不是配置文件所在目录。"""
    game = tmp_path / "Game"
    game.mkdir()
    (game / "Inner.uproject").write_text(json.dumps({"EngineAssociation": "5.8"}), encoding="utf-8")
    _write_yaml(tmp_path, {"engine": "unreal", "engine_version": "5.8", "project_root": "Game"})
    det = _check(tmp_path, capsys)["detected"]
    assert det["scanned"].endswith("Game")
    assert det["engine"] == "unreal"


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


@pytest.mark.parametrize("value", [
    "C++ 可按文本扫；\nBlueprint / .uasset 查不了 —— 不得据文本结果判定缺失",
    "  首行带缩进\n第二行",          # 手拼块标量时这个会生成解析不回来的 YAML
    "末尾有换行\n",                  # rstrip("\n") 会把它吃掉
    "含冒号: 和 # 井号",
])
def test_tricky_values_round_trip(tmp_path, value):
    pe.main(["write", str(tmp_path), "--engine", "unreal", "--inspectability", value])
    assert _load(tmp_path)["inspectability"] == value


def test_null_valued_unknown_field_survives(tmp_path):
    """过滤 None 会让 custom: null 在下一次写入时消失。"""
    (tmp_path / pe.CONFIG_NAME).write_text(
        "engine: unreal\nengine_version: '5.8'\nproject_root: .\ncustom: null\n",
        encoding="utf-8")
    pe.main(["write", str(tmp_path), "--verify-entry", "x"])
    assert "custom" in _load(tmp_path)


def test_written_file_always_parses_back(tmp_path):
    """写入前自校验：绝不落一个自己都读不回来的文件。"""
    pe.main(["write", str(tmp_path), "--engine", "unreal",
             "--source-scope", "带 'single' 和 \"double\" 引号\n以及换行"])
    data = _load(tmp_path)
    assert data["source_scope"].startswith("带 'single'")


def test_write_requires_at_least_one_field(tmp_path):
    assert pe.main(["write", str(tmp_path)]) == 2


def test_check_on_missing_dir_returns_error(tmp_path, capsys):
    assert pe.main(["check", str(tmp_path / "nope")]) == 2
    assert "目录不存在" in capsys.readouterr().out
