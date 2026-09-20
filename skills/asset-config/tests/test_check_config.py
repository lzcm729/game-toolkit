"""check_config — 配置校验。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from check_config import check_config


def _write(tmp_path: Path, conf: dict, *, name: str = "asset-config.yaml") -> Path:
    p = tmp_path / name
    p.write_text(yaml.safe_dump(conf, sort_keys=False, allow_unicode=True),
                 encoding="utf-8")
    return p


def _minimal(tmp_path: Path, **override) -> dict:
    (tmp_path / "items.json").write_text(
        json.dumps({"pearl": {"visual": "black pearls"}}), encoding="utf-8")
    conf = {
        "$schema_version": 1,
        "adapter": "generic",
        "output_root": "art",
        "categories": {
            "ingredients": {
                "data_source": {"type": "json_dict", "path": "items.json"},
                "prompt_template": "Icon of {visual}.",
            }
        },
    }
    conf.update(override)
    return conf


def _messages(report) -> str:
    return "\n".join(report.errors + report.notes)


# -------------------- 通过的情况 --------------------

def test_valid_config_passes(tmp_path):
    cfg = _write(tmp_path, _minimal(tmp_path))
    report = check_config(cfg, tmp_path)
    assert report.errors == [], report.errors
    assert report.ok


def test_missing_output_dir_is_not_an_error(tmp_path):
    """输出目录还没建出来很正常 —— 生成时会自己 mkdir。"""
    conf = _minimal(tmp_path)
    conf["output_root"] = "art/not/created/yet"
    cfg = _write(tmp_path, conf)
    assert check_config(cfg, tmp_path).ok


# -------------------- 数据源 --------------------

def test_missing_data_source_file(tmp_path):
    conf = _minimal(tmp_path)
    conf["categories"]["ingredients"]["data_source"]["path"] = "nope.json"
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    assert not report.ok
    msg = _messages(report)
    assert "ingredients" in msg and "nope.json" in msg


def test_duplicate_ids_reported(tmp_path):
    (tmp_path / "list.json").write_text(json.dumps([
        {"id": "dup", "visual": "a"}, {"id": "dup", "visual": "b"},
    ]), encoding="utf-8")
    conf = _minimal(tmp_path)
    conf["categories"]["ingredients"]["data_source"] = {
        "type": "json_list", "path": "list.json"}
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    assert not report.ok
    assert "dup" in _messages(report)


def test_colliding_output_filenames_reported(tmp_path):
    """两个 item 产出同名文件，后写的覆盖先写的。"""
    (tmp_path / "list.json").write_text(json.dumps([
        {"id": "a", "visual": "x"}, {"id": "a", "visual": "y"},
    ]), encoding="utf-8")
    conf = _minimal(tmp_path)
    conf["categories"]["ingredients"]["data_source"] = {
        "type": "json_list", "path": "list.json"}
    cfg = _write(tmp_path, conf)
    assert not check_config(cfg, tmp_path).ok


# -------------------- 模板 --------------------

def test_template_referencing_missing_field(tmp_path):
    """语法没问题，但字段在真实条目上不存在 —— 只查 YAML 语法查不出来。"""
    conf = _minimal(tmp_path)
    conf["categories"]["ingredients"]["prompt_template"] = "Icon of {nonexistent}."
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    assert not report.ok
    msg = _messages(report)
    assert "nonexistent" in msg
    assert "visual" in msg          # 列出可用字段


def test_missing_prompt_template(tmp_path):
    conf = _minimal(tmp_path)
    del conf["categories"]["ingredients"]["prompt_template"]
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    assert not report.ok
    assert "prompt_template" in _messages(report)


def test_derived_field_failure_reported(tmp_path):
    conf = _minimal(tmp_path)
    conf["categories"]["ingredients"]["derived_fields"] = {"x": "upper(nope)"}
    cfg = _write(tmp_path, conf)
    assert not check_config(cfg, tmp_path).ok


# -------------------- 路径与后端相容 --------------------

def test_game_prefix_with_generic_adapter(tmp_path):
    conf = _minimal(tmp_path)
    conf["output_root"] = "/Game/Art"
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    assert not report.ok
    assert "/Game/" in _messages(report)


def test_model_with_image_gen_backend(tmp_path):
    """image-gen 用 chain 表达模型选择，不认 model。"""
    conf = _minimal(tmp_path)
    conf["backend"] = "image-gen"
    conf["model"] = "gemini-3-pro-image"
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    msg = _messages(report)
    assert "model" in msg and "chain" in msg


def test_model_with_laozhang_backend_is_fine(tmp_path):
    conf = _minimal(tmp_path)
    conf["backend"] = "laozhang"
    conf["model"] = "gemini-3-pro-image"
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    assert "不支持 model" not in _messages(report)


def test_image_and_reference_paths_conflict(tmp_path):
    """两个文件都真实存在，把「文件不存在」这条干扰排除掉。

    第一版这条测试是假绿：两个路径都不存在，「文件不存在」的报错里同样含
    image 和 reference_paths 字样，断言被它满足了 —— 把互斥检查整个删掉，
    测试照样通过。
    """
    (tmp_path / "art").mkdir()
    (tmp_path / "art" / "anchor.png").write_bytes(b"png")
    (tmp_path / "art" / "base.png").write_bytes(b"png")
    conf = _minimal(tmp_path)
    conf["style"] = {"reference_paths": ["anchor.png"]}
    conf["categories"]["ingredients"]["image"] = "base.png"
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    assert not report.ok
    assert any("互斥" in e for e in report.errors)      # 断言这条检查本身


# -------------------- 未完成标记 --------------------

def test_todo_in_prompt_template_is_a_note_not_error(tmp_path):
    """创作性未定稿：能出图，只是风格还没满意 —— 不该拦住人。"""
    conf = _minimal(tmp_path)
    conf["categories"]["ingredients"]["prompt_template"] = "TODO: 描述画面 {visual}"
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    assert report.ok                       # 不报错
    assert any("TODO" in n for n in report.notes)


def test_todo_in_style_is_a_note(tmp_path):
    conf = _minimal(tmp_path)
    conf["style"] = {"prompt_prefix": "TODO: 定全局风格"}
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    assert report.ok
    assert any("TODO" in n for n in report.notes)


def test_empty_style_prefix_is_not_an_error(tmp_path):
    """风格可以写在 category 里，或用 skip_global_style —— 不强制非空。"""
    conf = _minimal(tmp_path)
    conf["style"] = {}
    cfg = _write(tmp_path, conf)
    assert check_config(cfg, tmp_path).ok


# -------------------- 配置本身 --------------------

def test_missing_config_file(tmp_path):
    report = check_config(tmp_path / "nope.yaml", tmp_path)
    assert not report.ok
    assert "nope.yaml" in _messages(report)


def test_no_categories(tmp_path):
    conf = _minimal(tmp_path)
    conf["categories"] = {}
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    assert not report.ok
    assert "categories" in _messages(report)


def test_unknown_backend_name(tmp_path):
    conf = _minimal(tmp_path)
    conf["backend"] = "midjourney"
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    assert not report.ok
    assert "midjourney" in _messages(report)


def test_global_reference_path_reported_once(tmp_path):
    """全局参考图缺失只该报一次，不该每个 category 报一遍。"""
    conf = _minimal(tmp_path)
    conf["style"] = {"reference_paths": ["missing-anchor.png"]}
    conf["categories"]["second"] = {
        "data_source": {"type": "json_dict", "path": "items.json"},
        "prompt_template": "Another {visual}.",
    }
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    hits = [e for e in report.errors if "missing-anchor.png" in e]
    assert len(hits) == 1, f"报了 {len(hits)} 次：{hits}"


# -------------------- 模型能力与配置相容 --------------------

def test_openai_model_with_reference_paths_is_an_error(tmp_path):
    """gpt-image-* 走 OpenAI 路径，没有多图 reference —— 配了风格锚必然全军覆没。

    这是配置层就能静态判定的事，不该拖到烧钱的运行时才发现。
    """
    (tmp_path / "art").mkdir()
    (tmp_path / "art" / "anchor.png").write_bytes(b"png")
    conf = _minimal(tmp_path)
    conf["backend"] = "laozhang"
    conf["model"] = "gpt-image-2.5-flare"
    conf["style"] = {"reference_paths": ["anchor.png"]}
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    assert not report.ok
    msg = _messages(report)
    assert "gpt-image-2.5-flare" in msg
    assert "reference_paths" in msg
    assert "gemini" in msg          # 指出出路


def test_openai_model_at_category_level_also_checked(tmp_path):
    """category 级的 model 同样要查 —— 顶层配 gemini 不代表每个 category 都是。"""
    (tmp_path / "art").mkdir()
    (tmp_path / "art" / "anchor.png").write_bytes(b"png")
    conf = _minimal(tmp_path)
    conf["backend"] = "laozhang"
    conf["model"] = "gemini-3-pro-image"
    conf["style"] = {"reference_paths": ["anchor.png"]}
    conf["categories"]["ingredients"]["model"] = "gpt-image-2.5-flare"
    cfg = _write(tmp_path, conf)
    assert not check_config(cfg, tmp_path).ok


def test_openai_model_without_reference_is_fine(tmp_path):
    """不配风格锚时 gpt-image-* 完全可用，别误报。"""
    conf = _minimal(tmp_path)
    conf["backend"] = "laozhang"
    conf["model"] = "gpt-image-2.5-flare"
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    assert report.ok, report.errors


def test_openai_model_with_image_is_fine(tmp_path):
    """image（单张编辑底图）走的是 edits 端点，OpenAI 路径支持。"""
    (tmp_path / "art").mkdir()
    (tmp_path / "art" / "base.png").write_bytes(b"png")
    conf = _minimal(tmp_path)
    conf["backend"] = "laozhang"
    conf["model"] = "gpt-image-2.5-flare"
    conf["categories"]["ingredients"]["image"] = "base.png"
    cfg = _write(tmp_path, conf)
    report = check_config(cfg, tmp_path)
    assert report.ok, report.errors
