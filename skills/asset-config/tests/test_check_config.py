"""check_config — 配置校验。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from check_config import check_config


def _write(tmp_path: Path, conf: dict, *, name: str = "asset-config.yaml") -> Path:
    """写配置。

    safe_dump 出来的 yaml 没有注释，而「必须询问」档的字段要求写来源注释。
    这里统一补上 —— 那条检查有自己的一组测试（用 _write_raw 直接写原文），
    别的测试不该被它干扰。
    """
    text = yaml.safe_dump(conf, sort_keys=False, allow_unicode=True)
    lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        name_part = stripped.split(":")[0] if ":" in stripped else ""
        if name_part in ("backend", "model", "chain", "aspect_ratio", "id_column"):
            indent = line[: len(line) - len(stripped)]
            lines.append(f"{indent}# 来源：测试夹具")
        lines.append(line)
    p = tmp_path / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
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


# -------------------- 决策来源 --------------------
# 「必须询问」档的字段要写明值从哪来。挡不住一个决心撒谎的 AI，但挡得住
# 「顺手填了忘了问」—— 而后者才是实际会发生的。

def _write_raw(tmp_path: Path, text: str) -> Path:
    (tmp_path / "items.json").write_text(
        json.dumps({"pearl": {"visual": "black pearls"}}), encoding="utf-8")
    p = tmp_path / "asset-config.yaml"
    p.write_text(text, encoding="utf-8")
    return p


_BASE = """$schema_version: 1
adapter: generic
output_root: art
categories:
  ingredients:
    data_source:
      type: json_dict
      path: items.json
    prompt_template: "Icon of {visual}."
"""


def test_must_ask_field_without_source_is_an_error(tmp_path):
    cfg = _write_raw(tmp_path, _BASE + "backend: laozhang\n")
    report = check_config(cfg, tmp_path)
    assert not report.ok
    msg = _messages(report)
    assert "backend" in msg
    assert "来源" in msg


def test_must_ask_field_with_source_passes(tmp_path):
    cfg = _write_raw(tmp_path, _BASE + """
# 来源：用户选定（候选 image-gen / laozhang）
backend: laozhang
""")
    report = check_config(cfg, tmp_path)
    assert report.ok, report.errors


def test_source_can_sit_in_a_multiline_comment_block(tmp_path):
    """来源那行不必紧贴字段，同一个注释块里就行。"""
    cfg = _write_raw(tmp_path, _BASE + """
# 生图后端。laozhang 随插件安装，需要 LAOZHANG_API_KEY
# 来源：用户选定
# （image-gen 那条要另外装，这个项目没装）
backend: laozhang
""")
    assert check_config(cfg, tmp_path).ok


def test_blank_line_breaks_the_comment_block(tmp_path):
    """隔了空行的注释是在说别的事，不能算这个字段的来源。"""
    cfg = _write_raw(tmp_path, _BASE + """
# 来源：用户选定

backend: laozhang
""")
    assert not check_config(cfg, tmp_path).ok


def test_category_level_field_also_needs_source(tmp_path):
    cfg = _write_raw(tmp_path, """$schema_version: 1
adapter: generic
output_root: art
categories:
  ingredients:
    aspect_ratio: "4:3"
    data_source:
      type: json_dict
      path: items.json
    prompt_template: "Icon of {visual}."
""")
    report = check_config(cfg, tmp_path)
    assert not report.ok
    assert "aspect_ratio" in _messages(report)


def test_id_column_needs_source_too(tmp_path):
    """复用既有决定也算来源 —— 要写的是「从哪来」，不是「问过谁」。"""
    (tmp_path / "f.csv").write_text("fid,v\na,x\n", encoding="utf-8")
    cfg = _write_raw(tmp_path, """$schema_version: 1
adapter: generic
output_root: art
categories:
  c:
    data_source:
      type: csv
      path: f.csv
      # 来源：沿用 Knowledge/Schema/xxx.yaml 的 identity_column
      id_column: fid
    prompt_template: "{v}"
""")
    assert check_config(cfg, tmp_path).ok


def test_absent_field_needs_no_source(tmp_path):
    """没写的字段用默认值，不需要注释。"""
    cfg = _write_raw(tmp_path, _BASE)
    assert check_config(cfg, tmp_path).ok


# -------------------- 与生成器共用同一份解析 --------------------

def _write_at(path: Path, conf: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(conf, sort_keys=False, allow_unicode=True),
                    encoding="utf-8")
    return path


def test_project_root_comes_from_config_not_config_dir(tmp_path):
    """**回归**：工程根按 config 的声明算，不是按 config 所在目录。

    以前校验器硬填 `config_path.parent`，生成器却走四级回退。config 放在
    子目录时，两者的相对路径基准不同 —— 校验通过的那份配置，跑起来读的是
    另一个位置的参考图，写的是另一个位置的输出目录。

    这里的参考图放在真正的工程根下；按旧口径会去 tools/art/ 找，报不存在。
    """
    (tmp_path / "art").mkdir()
    (tmp_path / "art" / "anchor.png").write_bytes(b"x")
    (tmp_path / "tools").mkdir(exist_ok=True)
    (tmp_path / "tools" / "items.json").write_text(
        json.dumps({"pearl": {"visual": "black pearls"}}), encoding="utf-8")

    conf = {
        "adapter": "generic",
        "project_root": "..",
        "output_root": "art",
        "style": {"reference_paths": ["anchor.png"]},
        "categories": {
            "ing": {
                "data_source": {"type": "json_dict", "path": "tools/items.json"},
                "prompt_template": "Icon of {visual}.",
            }
        },
    }
    cfg = _write_at(tmp_path / "tools" / "asset-config.yaml", conf)

    report = check_config(cfg)          # 不传 project_root —— 让它自己按规则定
    assert report.ok, _messages(report)
    assert any(str(tmp_path.resolve()) in n for n in report.notes)


def test_explicit_project_root_still_overrides(tmp_path):
    """--project-root 仍然能覆盖本次校验，并且覆盖来源要说出来。"""
    cfg = _write(tmp_path, _minimal(tmp_path))
    other = tmp_path / "other"
    other.mkdir()
    (other / "items.json").write_text(
        json.dumps({"pearl": {"visual": "x"}}), encoding="utf-8")
    report = check_config(cfg, other)
    assert any("--project-root" in n for n in report.notes)


def test_every_item_is_rendered_not_just_the_first(tmp_path):
    """**回归**：以前只在第一个条目上试渲染，后面的模板问题要等真跑才暴露。"""
    cfg = _write(tmp_path, _minimal(tmp_path, categories={
        "ing": {
            "data_source": {"type": "json_dict", "path": "items.json"},
            "prompt_template": "Icon of {visual}.",
        }
    }))
    # _minimal 自己会写一份 items.json，所以这份要后写才不被盖掉
    (tmp_path / "items.json").write_text(
        json.dumps({"a": {"visual": "x"}, "b": {"other": "y"}}), encoding="utf-8")
    report = check_config(cfg, tmp_path)
    assert not report.ok
    assert "item='b'" in _messages(report)


def test_output_subdir_escape_is_caught(tmp_path):
    """越界的 output_subdir 会把图写到工程外面。校验以前完全不查这一项。"""
    cfg = _write(tmp_path, _minimal(tmp_path, categories={
        "ing": {
            "data_source": {"type": "json_dict", "path": "items.json"},
            "prompt_template": "Icon of {visual}.",
            "output_subdir": "../../escaped",
        }
    }))
    report = check_config(cfg, tmp_path)
    assert not report.ok
    assert "output_root 之外" in _messages(report)


def test_missing_global_reference_reported_once(tmp_path):
    """全局参考图进了每个 category 的计划 —— 不能有几个 category 就报几遍。"""
    cat = {
        "data_source": {"type": "json_dict", "path": "items.json"},
        "prompt_template": "Icon of {visual}.",
    }
    cfg = _write(tmp_path, _minimal(
        tmp_path,
        style={"reference_paths": ["missing.png"]},
        categories={"one": dict(cat), "two": dict(cat)},
    ))
    report = check_config(cfg, tmp_path)
    hits = [e for e in report.errors if "missing.png" in e]
    assert len(hits) == 1, report.errors


def test_unused_global_reference_still_checked(tmp_path):
    """所有 category 都 skip_global_style 时它不进任何计划，但路径写错仍值得说。"""
    cfg = _write(tmp_path, _minimal(
        tmp_path,
        style={"reference_paths": ["missing.png"]},
        categories={"one": {
            "data_source": {"type": "json_dict", "path": "items.json"},
            "prompt_template": "Icon of {visual}.",
            "skip_global_style": True,
        }},
    ))
    report = check_config(cfg, tmp_path)
    assert any("missing.png" in e for e in report.errors)


def test_item_level_model_capability_conflict_is_caught(tmp_path):
    """能力冲突问后端自己要 —— item 级的 model 以前也在检查范围外。"""
    (tmp_path / "art").mkdir(exist_ok=True)
    (tmp_path / "art" / "anchor.png").write_bytes(b"x")
    cfg = _write(tmp_path, _minimal(
        tmp_path,
        backend="laozhang",
        style={"reference_paths": ["anchor.png"]},
        categories={"ing": {
            "data_source": {"type": "json_dict", "path": "items.json"},
            "prompt_template": "Icon of {visual}.",
        }},
    ))
    # _minimal 自己会写一份 items.json，所以这份要后写才不被盖掉
    (tmp_path / "items.json").write_text(
        json.dumps({"a": {"visual": "x", "model": "gpt-image-1"}}), encoding="utf-8")
    report = check_config(cfg, tmp_path)
    assert "OpenAI 路径" in _messages(report)


def test_main_does_not_hard_fill_project_root(tmp_path, monkeypatch, capsys):
    """**回归**：缺陷原本在 CLI 入口 —— 不给 --project-root 时它硬填 config 的父目录。

    走函数入口的测试看不到这条路径，所以这里跑真正的 main()。
    """
    import check_config as cc

    (tmp_path / "art").mkdir()
    (tmp_path / "art" / "anchor.png").write_bytes(b"x")
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "items.json").write_text(
        json.dumps({"pearl": {"visual": "x"}}), encoding="utf-8")

    conf = {
        "adapter": "generic",
        "project_root": "..",
        "output_root": "art",
        "style": {"reference_paths": ["anchor.png"]},
        "categories": {"ing": {
            "data_source": {"type": "json_dict", "path": "tools/items.json"},
            "prompt_template": "Icon of {visual}.",
        }},
    }
    cfg = _write_at(tmp_path / "tools" / "asset-config.yaml", conf)

    assert cc.main(["--config", str(cfg)]) == 0
    assert str(tmp_path.resolve()) in capsys.readouterr().out


def test_main_finds_config_in_cwd(tmp_path, monkeypatch):
    """不给 --config 时按共享的默认位置找，和生成器同一套顺序。"""
    import check_config as cc

    cfg = _write(tmp_path, _minimal(tmp_path))
    assert cfg.name == "asset-config.yaml"
    monkeypatch.chdir(tmp_path)
    assert cc.main([]) == 0
