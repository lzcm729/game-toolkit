# -*- coding: utf-8 -*-
"""project_env.py 的回归测试。

这个脚本会写进别人项目的 CLAUDE.md，所以「更新而不是重复追加」「不碰同文件
其他内容」这两条必须锁住。
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import project_env as pe  # noqa: E402


def _run_check(root, capsys):
    pe.main(["check", str(root)])
    return json.loads(capsys.readouterr().out)


# -------------------- 状态判定 --------------------

def test_no_claude_md_is_missing(tmp_path, capsys):
    out = _run_check(tmp_path, capsys)
    assert out["status"] == "missing"
    assert out["claude_md_exists"] is False
    assert set(out["missing_required"]) == {"engine", "engine_version", "project_root"}


def test_complete_declaration_is_ok(tmp_path, capsys):
    (tmp_path / "CLAUDE.md").write_text(
        "# X\n\n## Game Toolkit 项目环境\n\n"
        "- 引擎：unreal\n- 引擎版本：5.8\n- 工程根：.\n",
        encoding="utf-8")
    out = _run_check(tmp_path, capsys)
    assert out["status"] == "ok"
    assert out["missing_required"] == []
    assert out["declared"]["engine"] == "unreal"


def test_placeholder_counts_as_missing(tmp_path, capsys):
    """写「待核实」不等于填了 —— 否则占位符会被当成已确认。"""
    (tmp_path / "CLAUDE.md").write_text(
        "## Game Toolkit 项目环境\n\n- 引擎：unreal\n- 引擎版本：待核实\n- 工程根：.\n",
        encoding="utf-8")
    out = _run_check(tmp_path, capsys)
    assert out["status"] == "incomplete"
    assert out["missing_required"] == ["engine_version"]


def test_other_sections_are_not_parsed_as_declaration(tmp_path, capsys):
    """段落解析不能越界吃到下一个 ## 的内容。"""
    (tmp_path / "CLAUDE.md").write_text(
        "## Game Toolkit 项目环境\n\n- 引擎：godot\n\n## 别的段落\n\n- 引擎版本：9.9\n",
        encoding="utf-8")
    out = _run_check(tmp_path, capsys)
    assert out["declared"].get("engine") == "godot"
    assert "engine_version" not in out["declared"]


# -------------------- 探测 --------------------

def test_detects_unreal_and_version(tmp_path, capsys):
    (tmp_path / "Game.uproject").write_text(
        json.dumps({"EngineAssociation": "5.8",
                    "Modules": [{"Name": "Game"}, {"Name": "GameEditor"}]}),
        encoding="utf-8")
    out = _run_check(tmp_path, capsys)
    assert out["detected"]["engine"] == "unreal"
    assert out["detected"]["engine_version"] == "5.8"
    assert any("Game, GameEditor" in e for e in out["detected"]["evidence"])


def test_non_numeric_engine_association_is_not_a_version(tmp_path, capsys):
    """源码版引擎的 EngineAssociation 是 GUID，不能当版本号填进去。"""
    (tmp_path / "Game.uproject").write_text(
        json.dumps({"EngineAssociation": "{A1B2C3D4-0000-0000-0000-000000000000}"}),
        encoding="utf-8")
    out = _run_check(tmp_path, capsys)
    assert "engine_version" not in out["detected"]
    assert any("需人工确认" in e for e in out["detected"]["evidence"])


def test_multiple_uprojects_flagged(tmp_path, capsys):
    for name in ("A.uproject", "B.uproject"):
        (tmp_path / name).write_text(json.dumps({"EngineAssociation": "5.8"}), encoding="utf-8")
    out = _run_check(tmp_path, capsys)
    assert any("需人工指定" in e for e in out["detected"]["evidence"])


def test_sln_next_to_uproject_is_called_out(tmp_path, capsys):
    """UE 会自动生成 .sln —— 不能据此推断这是 .NET 项目。"""
    (tmp_path / "Game.uproject").write_text(json.dumps({"EngineAssociation": "5.8"}), encoding="utf-8")
    (tmp_path / "Game.sln").write_text("", encoding="utf-8")
    out = _run_check(tmp_path, capsys)
    assert any("dotnet build" in e for e in out["detected"]["evidence"])


def test_detects_godot(tmp_path, capsys):
    (tmp_path / "project.godot").write_text(
        'config/features=PackedStringArray("4.3", "GL Compatibility")\n', encoding="utf-8")
    out = _run_check(tmp_path, capsys)
    assert out["detected"]["engine"] == "godot"
    assert out["detected"]["engine_version"] == "4.3"


def test_binary_assets_produce_inspectability_hint(tmp_path, capsys):
    (tmp_path / "Game.uproject").write_text(json.dumps({"EngineAssociation": "5.8"}), encoding="utf-8")
    content = tmp_path / "Content"
    content.mkdir()
    (content / "BP_A.uasset").write_bytes(b"\x00")
    (content / "Main.umap").write_bytes(b"\x00")
    out = _run_check(tmp_path, capsys)
    assert "查不了" in out["detected"]["inspectability_hint"]


# -------------------- 写入 --------------------

def test_write_creates_file(tmp_path, capsys):
    pe.main(["write", str(tmp_path), "--engine", "unreal", "--engine-version", "5.8"])
    text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "## Game Toolkit 项目环境" in text
    assert "- 引擎：unreal" in text
    assert "- 工程根：待核实" in text          # 必填项缺失时留占位，不静默省略


def test_write_is_idempotent_and_preserves_other_content(tmp_path):
    p = tmp_path / "CLAUDE.md"
    p.write_text("# 项目\n\n## 别的约定\n\n- 保留我\n", encoding="utf-8")
    for _ in range(3):
        pe.main(["write", str(tmp_path), "--engine", "unreal", "--engine-version", "5.8"])
    text = p.read_text(encoding="utf-8")
    assert text.count("## Game Toolkit 项目环境") == 1   # 不重复追加
    assert "- 保留我" in text                            # 不碰别的段落


def test_write_merges_with_existing_fields(tmp_path):
    pe.main(["write", str(tmp_path), "--engine", "unreal", "--engine-version", "5.8",
             "--project-root", "."])
    pe.main(["write", str(tmp_path), "--verify-entry", "尚未登记"])
    text = (tmp_path / "CLAUDE.md").read_text(encoding="utf-8")
    assert "- 引擎：unreal" in text          # 上一轮的值没被冲掉
    assert "- 验证入口：尚未登记" in text


def test_write_requires_at_least_one_field(tmp_path):
    assert pe.main(["write", str(tmp_path)]) == 2


def test_check_on_missing_dir_returns_error(tmp_path, capsys):
    assert pe.main(["check", str(tmp_path / "nope")]) == 2
    assert "目录不存在" in capsys.readouterr().out
