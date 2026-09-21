"""asset_plan — 生成计划（校验器验证它、dry-run 展示它、执行器消费它）。"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
import yaml

import asset_context
import image_backend
from asset_plan import MAX_ITEM_ERRORS, build_category_plan


def _ctx(tmp_path: Path, conf: dict) -> "asset_context.AssetContext":
    conf = {"adapter": "filesystem", "output_root": "art", **conf}
    p = tmp_path / "asset-config.yaml"
    p.write_text(yaml.safe_dump(conf, sort_keys=False, allow_unicode=True),
                 encoding="utf-8")
    return asset_context.load_context(p)


def _items(tmp_path: Path, data: dict) -> dict:
    (tmp_path / "items.json").write_text(json.dumps(data, ensure_ascii=False),
                                         encoding="utf-8")
    return {"type": "json_dict", "path": "items.json"}


def _simple(tmp_path: Path, items: dict, **cat) -> "asset_context.AssetContext":
    spec = {"data_source": _items(tmp_path, items),
            "prompt_template": "Icon of {visual}.", **cat}
    return _ctx(tmp_path, {"categories": {"ing": spec}})


# -------------------- 全部条目都渲染，不是只渲染第一条 --------------------

def test_renders_every_item(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x"}, "b": {"visual": "y"}})
    plan = build_category_plan(ctx, "ing")
    assert plan.ok
    assert [a.item_id for a in plan.assets] == ["a", "b"]
    assert plan.assets[1].prompt == "Icon of y."


def test_second_item_missing_field_is_caught(tmp_path):
    """**回归**：以前只渲染第一个条目，第 2 条起的模板问题要等真跑才暴露。

    那时候已经在按张烧钱了 —— 第一张成功、第二张炸，钱花了一半。
    """
    ctx = _simple(tmp_path, {"a": {"visual": "x"}, "b": {"other": "y"}})
    plan = build_category_plan(ctx, "ing")
    assert not plan.ok
    assert any("item='b'" in e and "渲染失败" in e for e in plan.errors)
    # 第一条仍然算得出来，报告里不该因为第二条坏就丢掉它
    assert [a.item_id for a in plan.assets] == ["a"]


def test_item_errors_are_capped(tmp_path):
    """一千条同类错误会把别的问题顶没。超过上限只留一条汇总。"""
    items = {f"i{n}": {"other": "y"} for n in range(MAX_ITEM_ERRORS + 7)}
    ctx = _simple(tmp_path, items)
    plan = build_category_plan(ctx, "ing")
    assert len(plan.errors) == MAX_ITEM_ERRORS + 1
    assert "另有 7 条同类错误未列出" in plan.errors[-1]


def test_missing_id_is_error_not_crash(tmp_path):
    """json_dict 里显式写了 id: null 时 key 补不进去 —— 得报错，不能 traceback。"""
    ctx = _simple(tmp_path, {"a": {"visual": "x", "id": None}})
    plan = build_category_plan(ctx, "ing")
    assert any("缺 id" in e for e in plan.errors)


# -------------------- 输出位置 --------------------

def test_output_path_is_output_root_plus_subdir(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x"}}, output_subdir="icons")
    plan = build_category_plan(ctx, "ing")
    assert plan.output_dir == (tmp_path / "art" / "icons").resolve()
    assert plan.assets[0].output_path == plan.output_dir / "a.png"


def test_output_subdir_defaults_to_category_name(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x"}})
    plan = build_category_plan(ctx, "ing")
    assert plan.output_dir == (tmp_path / "art" / "ing").resolve()


def test_output_subdir_cannot_escape_output_root(tmp_path):
    """`../../x` 会把图写到工程外面 —— 实测连 dry-run 的日志都写出去了。"""
    ctx = _simple(tmp_path, {"a": {"visual": "x"}}, output_subdir="../../escaped")
    plan = build_category_plan(ctx, "ing")
    assert not plan.ok
    assert any("output_root 之外" in e for e in plan.errors)


def test_output_ext_is_honoured(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x"}}, output_ext="webp")
    plan = build_category_plan(ctx, "ing")
    assert plan.assets[0].filename == "a.webp"


def test_duplicate_filename_is_error(tmp_path):
    (tmp_path / "items.json").write_text(
        json.dumps([{"id": "a", "visual": "x"}, {"id": "a", "visual": "y"}]),
        encoding="utf-8")
    spec = {"data_source": {"type": "json_list", "path": "items.json"},
            "prompt_template": "Icon of {visual}."}
    ctx = _ctx(tmp_path, {"categories": {"ing": spec}})
    plan = build_category_plan(ctx, "ing")
    assert any("同一个文件" in e for e in plan.errors)


# -------------------- 过滤与截断 --------------------

def test_name_filter_applies_before_limit(tmp_path):
    """顺序要紧：先按 id 挑再取前 N，反过来 --names 指定的条目可能落在 N 之外。"""
    items = {f"i{n}": {"visual": f"v{n}"} for n in range(5)}
    ctx = _simple(tmp_path, items)
    plan = build_category_plan(ctx, "ing", name_filter={"i3", "i4"}, limit=1)
    assert [a.item_id for a in plan.assets] == ["i3"]


def test_total_items_counts_before_filtering(tmp_path):
    items = {f"i{n}": {"visual": f"v{n}"} for n in range(5)}
    ctx = _simple(tmp_path, items)
    plan = build_category_plan(ctx, "ing", limit=2)
    assert plan.total_items == 5
    assert len(plan.assets) == 2


def test_empty_data_source_is_note_not_error(tmp_path):
    ctx = _simple(tmp_path, {})
    plan = build_category_plan(ctx, "ing")
    assert plan.ok
    assert any("没有条目" in n for n in plan.notes)


# -------------------- 参考图与底图 --------------------

def test_bare_relative_reference_resolves_under_output_root(tmp_path):
    (tmp_path / "art").mkdir()
    (tmp_path / "art" / "anchor.png").write_bytes(b"x")
    ctx = _simple(tmp_path, {"a": {"visual": "x"}},
                  reference_paths=["anchor.png"])
    plan = build_category_plan(ctx, "ing")
    assert plan.defaults["reference_paths"] == [str((tmp_path / "art" / "anchor.png").resolve())]
    assert plan.input_paths[0][1] == (tmp_path / "art" / "anchor.png").resolve()


def test_category_reference_overrides_global(tmp_path):
    spec = {"data_source": _items(tmp_path, {"a": {"visual": "x"}}),
            "prompt_template": "Icon of {visual}.",
            "reference_paths": ["cat.png"]}
    ctx = _ctx(tmp_path, {"style": {"reference_paths": ["global.png"]},
                          "categories": {"ing": spec}})
    plan = build_category_plan(ctx, "ing")
    assert [Path(p).name for p in plan.defaults["reference_paths"]] == ["cat.png"]


def test_skip_global_style_drops_global_reference(tmp_path):
    spec = {"data_source": _items(tmp_path, {"a": {"visual": "x"}}),
            "prompt_template": "Icon of {visual}.",
            "skip_global_style": True}
    ctx = _ctx(tmp_path, {"style": {"reference_paths": ["global.png"],
                                    "prompt_prefix": "PRE"},
                          "categories": {"ing": spec}})
    plan = build_category_plan(ctx, "ing")
    assert "reference_paths" not in plan.defaults
    assert not plan.assets[0].prompt.startswith("PRE")


def test_image_and_reference_paths_are_mutually_exclusive(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x", "image": "base.png"}},
                  reference_paths=["anchor.png"])
    plan = build_category_plan(ctx, "ing")
    assert any("互斥" in e for e in plan.errors)


def test_item_image_overrides_category_image(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x", "image": "mine.png"}},
                  image="cat.png", item_overrides={"image": "image"})
    plan = build_category_plan(ctx, "ing")
    assert Path(plan.assets[0].payload["image"]).name == "mine.png"


# -------------------- 字段优先级 --------------------

def test_item_model_lands_on_asset(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x", "model": "m-item"}},
                  item_overrides={"model": "model"})
    plan = build_category_plan(ctx, "ing")
    assert plan.assets[0].payload["model"] == "m-item"


def test_category_model_beats_top_level(tmp_path):
    spec = {"data_source": _items(tmp_path, {"a": {"visual": "x"}}),
            "prompt_template": "Icon of {visual}.", "model": "m-cat"}
    ctx = _ctx(tmp_path, {"model": "m-top", "categories": {"ing": spec}})
    plan = build_category_plan(ctx, "ing")
    assert plan.defaults["model"] == "m-cat"


def test_model_ignores_skip_global_style(tmp_path):
    """skip_global_style 关的是风格，模型是后端配置 —— 不该被一起关掉。"""
    spec = {"data_source": _items(tmp_path, {"a": {"visual": "x"}}),
            "prompt_template": "Icon of {visual}.", "skip_global_style": True}
    ctx = _ctx(tmp_path, {"model": "m-top", "categories": {"ing": spec}})
    plan = build_category_plan(ctx, "ing")
    assert plan.defaults["model"] == "m-top"


def test_extra_fields_do_not_override_item(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "mine"}},
                  extra_fields={"visual": {"a": "injected"}})
    plan = build_category_plan(ctx, "ing")
    assert plan.assets[0].prompt == "Icon of mine."


def test_extra_fields_fill_missing(tmp_path):
    spec = {"data_source": _items(tmp_path, {"a": {"other": "z"}}),
            "prompt_template": "Icon of {visual}.",
            "extra_fields": {"visual": {"a": "injected"}}}
    ctx = _ctx(tmp_path, {"categories": {"ing": spec}})
    plan = build_category_plan(ctx, "ing")
    assert plan.assets[0].prompt == "Icon of injected."


def test_extra_fields_must_be_mapping(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x"}}, extra_fields={"visual": "nope"})
    plan = build_category_plan(ctx, "ing")
    assert any("必须是 dict" in e for e in plan.errors)


# -------------------- 后端能力 --------------------

def _with_backend(ctx, backend):
    return asset_context.AssetContext(**{**ctx.__dict__, "backend": backend})


def test_unsupported_field_on_defaults_is_an_error(tmp_path):
    """丢掉风格链，产出的就不是你要的那件事了 —— 默认阻止，不是告警。"""
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x"}}, chain="fancy"), image_backend.LAOZHANG)
    plan = build_category_plan(ctx, "ing")
    assert not plan.ok
    assert any("不支持 chain" in e and "fancy" in e for e in plan.errors)


def test_unsupported_field_on_item_is_an_error(tmp_path):
    """只扫 defaults 的话，「只在某个 item 上配了 model」会静默失效。"""
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x", "model": "m"}},
                item_overrides={"model": "model"}), image_backend.IMAGE_GEN)
    plan = build_category_plan(ctx, "ing")
    assert any("item=a" in e and "不支持 model" in e for e in plan.errors)


def test_allow_degrade_turns_it_back_into_a_warning(tmp_path):
    """「切个后端试一下」要明说 —— 它不再是默认。"""
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x"}}, chain="fancy"), image_backend.LAOZHANG)
    plan = build_category_plan(ctx, "ing", allow_degrade=True)
    assert plan.ok
    assert any("--allow-degrade" in w for w in plan.warnings)


def test_seed_is_degrade_tolerant(tmp_path):
    """seed 只影响可复现性，不影响画的是什么 —— 丢了照旧只告警。"""
    backend = dataclasses.replace(
        image_backend.LAOZHANG,
        supports=image_backend.LAOZHANG.supports - {"seed"})
    ctx = _with_backend(_simple(tmp_path, {"a": {"visual": "x"}}, seed=7), backend)
    plan = build_category_plan(ctx, "ing")
    assert plan.ok
    assert any("不支持 seed" in w for w in plan.warnings)


def test_custom_backend_capability_is_unknown_not_supported(tmp_path):
    """自定义后端既不报降级，也不假装查过 —— 「没发现」和「没看」得分开。"""
    backend = dataclasses.replace(
        image_backend.LAOZHANG, name="custom:x", capability_known=False)
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x"}}, chain="fancy"), backend)
    plan = build_category_plan(ctx, "ing")
    assert plan.ok
    assert plan.warnings == []


def test_supported_field_does_not_warn(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x"}}, seed=7)
    ctx = asset_context.AssetContext(**{**ctx.__dict__, "backend": image_backend.LAOZHANG})
    plan = build_category_plan(ctx, "ing")
    assert not plan.warnings


def test_backend_declares_model_capability_conflict(tmp_path):
    """能力冲突问后端自己要，上层不按后端名特判、不碰后端私有函数。"""
    (tmp_path / "art").mkdir()
    (tmp_path / "art" / "anchor.png").write_bytes(b"x")
    spec = {"data_source": _items(tmp_path, {"a": {"visual": "x"}}),
            "prompt_template": "Icon of {visual}.",
            "reference_paths": ["anchor.png"]}
    ctx = _ctx(tmp_path, {"model": "gpt-image-1", "categories": {"ing": spec}})
    ctx = asset_context.AssetContext(**{**ctx.__dict__, "backend": image_backend.LAOZHANG})
    plan = build_category_plan(ctx, "ing")
    assert any("OpenAI 路径" in e for e in plan.errors)


def test_item_level_model_conflict_is_caught(tmp_path):
    (tmp_path / "art").mkdir()
    (tmp_path / "art" / "anchor.png").write_bytes(b"x")
    spec = {"data_source": _items(tmp_path, {"a": {"visual": "x", "model": "gpt-image-1"}}),
            "prompt_template": "Icon of {visual}.",
            "reference_paths": ["anchor.png"]}
    ctx = _ctx(tmp_path, {"categories": {"ing": spec}})
    ctx = asset_context.AssetContext(**{**ctx.__dict__, "backend": image_backend.LAOZHANG})
    plan = build_category_plan(ctx, "ing")
    assert any("OpenAI 路径" in e and "item=a" in e for e in plan.errors)


def test_gemini_model_with_references_is_fine(tmp_path):
    (tmp_path / "art").mkdir()
    (tmp_path / "art" / "anchor.png").write_bytes(b"x")
    spec = {"data_source": _items(tmp_path, {"a": {"visual": "x"}}),
            "prompt_template": "Icon of {visual}.",
            "reference_paths": ["anchor.png"]}
    ctx = _ctx(tmp_path, {"model": "gemini-3-pro-image", "categories": {"ing": spec}})
    ctx = asset_context.AssetContext(**{**ctx.__dict__, "backend": image_backend.LAOZHANG})
    plan = build_category_plan(ctx, "ing")
    assert plan.ok


# -------------------- batch 序列化 --------------------

def test_to_batch_matches_protocol(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x"}}, aspect_ratio="16:9")
    batch = build_category_plan(ctx, "ing").to_batch()
    assert batch["$schema_version"] == 2
    assert batch["defaults"]["aspect_ratio"] == "16:9"
    assert batch["assets"] == [{"name": "a", "filename": "a.png", "prompt": "Icon of x."}]


def test_missing_prompt_template_is_error(tmp_path):
    spec = {"data_source": _items(tmp_path, {"a": {"visual": "x"}})}
    ctx = _ctx(tmp_path, {"categories": {"ing": spec}})
    plan = build_category_plan(ctx, "ing")
    assert any("缺 prompt_template" in e for e in plan.errors)


def test_unknown_category_is_error(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x"}})
    plan = build_category_plan(ctx, "nope")
    assert not plan.ok


def test_bad_data_source_is_error_not_crash(tmp_path):
    spec = {"data_source": {"type": "json_dict", "path": "missing.json"},
            "prompt_template": "x"}
    ctx = _ctx(tmp_path, {"categories": {"ing": spec}})
    plan = build_category_plan(ctx, "ing")
    assert any("数据源加载失败" in e for e in plan.errors)


# -------------------- 数据列 vs 生成参数 --------------------

def test_undeclared_control_column_is_an_error(tmp_path):
    """4.0.0：配置的行为不该依赖没人声明过的巧合。

    一列没声明的 model 改变生成内容的程度，和后端丢掉一个声明过的 model
    一模一样 —— 3.20.0 已经把后者定成阻止，两者没理由一个拦一个放。
    """
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x", "model": "m-from-data"}}),
        image_backend.LAOZHANG)
    plan = build_category_plan(ctx, "ing")
    assert not plan.ok
    assert any("'model'" in e and "item_overrides" in e for e in plan.errors)


def test_allow_implicit_overrides_turns_it_back_into_a_warning(tmp_path):
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x", "model": "m-from-data"}}),
        image_backend.LAOZHANG)
    plan = build_category_plan(ctx, "ing", allow_implicit_overrides=True)
    assert plan.ok
    assert plan.assets[0].payload["model"] == "m-from-data"
    assert any("--allow-implicit-overrides" in w for w in plan.warnings)


def test_plain_data_produces_no_governance_issue(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x", "rarity": "common"}})
    plan = build_category_plan(ctx, "ing")
    assert plan.governance == []


def test_declared_override_maps_a_named_column(tmp_path):
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x", "gen_model": "m-declared"}},
                item_overrides={"model": "gen_model"}),
        image_backend.LAOZHANG)      # image-gen 不认 model，会撞上另一条检查
    plan = build_category_plan(ctx, "ing")
    assert plan.assets[0].payload["model"] == "m-declared"
    assert plan.ok, plan.errors


def test_declaring_overrides_closes_the_implicit_channel(tmp_path):
    """**这是显式声明的全部意义**：声明是封闭的，别的同名字段是普通数据。

    策划表里加一列 model 表示游戏里的模型类型，不该顺手改掉生图模型。
    """
    ctx = _simple(tmp_path, {"a": {"visual": "x", "model": "业务数据",
                                   "gen_model": "m-declared"}},
                  item_overrides={"model": "gen_model"})
    plan = build_category_plan(ctx, "ing")
    assert plan.assets[0].payload["model"] == "m-declared"


def test_empty_item_overrides_turns_the_channel_off(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x", "model": "业务数据"}},
                  item_overrides={})
    plan = build_category_plan(ctx, "ing")
    assert plan.ok, plan.errors
    assert "model" not in plan.assets[0].payload


def test_declared_source_column_missing_is_a_note(tmp_path):
    """声明了却没有一个条目带那个字段，多半是列名写错了。"""
    ctx = _simple(tmp_path, {"a": {"visual": "x"}},
                  item_overrides={"model": "gen_modle"})
    plan = build_category_plan(ctx, "ing")
    assert plan.ok
    assert any("gen_modle" in n and "写错" in n for n in plan.notes)


def test_blank_cell_is_not_an_override(tmp_path):
    """CSV 短行会把缺的字段补成空字符串 —— 不该给后端送个空模型名。"""
    ctx = _simple(tmp_path, {"a": {"visual": "x", "gen_model": "  "}},
                  item_overrides={"model": "gen_model"})
    plan = build_category_plan(ctx, "ing")
    assert "model" not in plan.assets[0].payload


def test_declared_image_column(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x", "base_art": "mine.png"}},
                  item_overrides={"image": "base_art"})
    plan = build_category_plan(ctx, "ing")
    assert Path(plan.assets[0].payload["image"]).name == "mine.png"


def test_declared_overrides_ignore_undeclared_image_column(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x", "image": "业务数据.png"}},
                  item_overrides={"model": "gen_model"}, image="cat.png")
    plan = build_category_plan(ctx, "ing")
    assert Path(plan.assets[0].payload["image"]).name == "cat.png"


def test_unknown_override_param_is_an_error(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x"}},
                  item_overrides={"prompt": "col"})
    plan = build_category_plan(ctx, "ing")
    assert any("不是可逐项覆盖的" in e for e in plan.errors)


def test_override_source_must_be_a_string(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x"}},
                  item_overrides={"model": 7})
    plan = build_category_plan(ctx, "ing")
    assert any("应为数据字段名" in e for e in plan.errors)


def test_item_overrides_must_be_a_mapping(tmp_path):
    ctx = _simple(tmp_path, {"a": {"visual": "x"}}, item_overrides=["model"])
    plan = build_category_plan(ctx, "ing")
    assert any("item_overrides 应为映射" in e for e in plan.errors)


def test_backend_without_edit_support_rejects_image(tmp_path):
    """编辑底图也是能力的一种。后端不支持就该拦住 —— 丢掉底图等于换了个任务。

    两个内置后端都支持 image，所以这条只有造一个不支持的后端才测得到。
    """
    backend = dataclasses.replace(
        image_backend.LAOZHANG,
        supports=image_backend.LAOZHANG.supports - {"image"})
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x"}}, image="base.png"), backend)
    plan = build_category_plan(ctx, "ing")
    assert not plan.ok
    assert any("不支持 image" in e for e in plan.errors)


def test_backend_with_edit_support_accepts_image(tmp_path):
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x"}}, image="base.png"),
        image_backend.LAOZHANG)
    plan = build_category_plan(ctx, "ing")
    assert plan.ok
    assert Path(plan.assets[0].payload["image"]).name == "base.png"


# -------------------- 治理判定是配置属性，不是本次运行属性 --------------------

def test_implicit_override_check_scans_every_item(tmp_path):
    """**又一个 items[0]**：3.16.0 存在的全部理由就是抽第一条不够，
    而治理判定自己也差点这么干。带 model 的是第二条。
    """
    (tmp_path / "items.json").write_text(
        json.dumps([{"id": "a", "visual": "x"},
                    {"id": "b", "visual": "y", "model": "业务数据"}]),
        encoding="utf-8")
    spec = {"data_source": {"type": "json_list", "path": "items.json"},
            "prompt_template": "Icon of {visual}."}
    ctx = _with_backend(_ctx(tmp_path, {"categories": {"ing": spec}}),
                        image_backend.LAOZHANG)
    plan = build_category_plan(ctx, "ing")
    assert any("'model'" in e for e in plan.errors)


def test_implicit_override_check_survives_limit_and_names(tmp_path):
    """--limit 1 恰好跳过带 model 的那条，不代表这份配置没有隐式控制通道。"""
    (tmp_path / "items.json").write_text(
        json.dumps([{"id": "a", "visual": "x"},
                    {"id": "b", "visual": "y", "model": "业务数据"}]),
        encoding="utf-8")
    spec = {"data_source": {"type": "json_list", "path": "items.json"},
            "prompt_template": "Icon of {visual}."}
    ctx = _with_backend(_ctx(tmp_path, {"categories": {"ing": spec}}),
                        image_backend.LAOZHANG)
    plan = build_category_plan(ctx, "ing", limit=1)
    assert len(plan.assets) == 1
    assert any("'model'" in e for e in plan.errors)


def test_extra_fields_model_is_not_an_implicit_channel(tmp_path):
    """extra_fields 注入的 model 明明写在配置里，不该判成「没声明过」。"""
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x"}},
                extra_fields={"model": {"a": "m-from-config"}}),
        image_backend.LAOZHANG)
    plan = build_category_plan(ctx, "ing")
    assert plan.ok, plan.errors
    assert plan.assets[0].payload["model"] == "m-from-config"


# -------------------- 假绿补课：3.20.0 的严重度分档 --------------------

@pytest.mark.parametrize("field, value", [
    ("aspect_ratio", "16:9"),
    ("preset", "fancy"),
    ("reference_paths", ["anchor.png"]),
])
def test_every_meaning_changing_field_blocks(tmp_path, field, value):
    """3.20.0 的表里六个阻止类字段，原来只测了 chain / model / image 三个。"""
    if field == "reference_paths":
        (tmp_path / "art").mkdir(exist_ok=True)
        (tmp_path / "art" / "anchor.png").write_bytes(b"x")
    backend = dataclasses.replace(
        image_backend.LAOZHANG,
        # 先补齐再减掉那一个 —— 反过来写会把 preset 又加回来（第一版就是这样，
        # 于是 preset 那一档恰好测了个寂寞）
        supports=(image_backend.LAOZHANG.supports | {"chain", "preset"}) - {field})
    ctx = _with_backend(_simple(tmp_path, {"a": {"visual": "x"}}, **{field: value}),
                        backend)
    plan = build_category_plan(ctx, "ing")
    assert not plan.ok, plan.warnings
    assert any(f"不支持 {field}" in e for e in plan.errors)


def test_custom_backend_from_env_is_capability_unknown(tmp_path, monkeypatch):
    """**假绿补课**：以前只用 dataclasses.replace 手搓后端测这条，
    真正产生自定义后端的代码路径（select → _custom）零覆盖。
    """
    script = tmp_path / "my_backend.py"
    script.write_text("# stub", encoding="utf-8")
    monkeypatch.setenv(image_backend.SCRIPT_ENV, str(script))
    ctx = _simple(tmp_path, {"a": {"visual": "x"}}, chain="fancy")
    assert ctx.backend.capability_known is False
    assert any("能力未知" in n for n in ctx.notes)
    plan = build_category_plan(ctx, "ing")
    assert plan.ok and plan.warnings == []


# -------------------- 后端自己知道的降级，能力层也要知道 --------------------

def test_openai_model_with_non_native_ratio_is_caught(tmp_path):
    """后端运行时会 [warn] 说「近似成 X，边缘被裁掉」—— 但那已经在生成了。

    批量按张烧钱，该在发请求之前说。
    """
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x"}}, aspect_ratio="16:9",
                model="gpt-image-1"),
        image_backend.LAOZHANG)
    plan = build_category_plan(ctx, "ing")
    assert not plan.ok
    assert any("就近裁切" in e for e in plan.errors)


def test_openai_model_with_native_ratio_is_fine(tmp_path):
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x"}}, aspect_ratio="2:3",
                model="gpt-image-1"),
        image_backend.LAOZHANG)
    assert build_category_plan(ctx, "ing").ok


def test_edit_mode_with_aspect_ratio_is_caught(tmp_path):
    """给了 image 时输出尺寸跟随底图，aspect_ratio 不生效。"""
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x"}}, image="base.png",
                aspect_ratio="16:9", model="gemini-3-pro-image"),
        image_backend.LAOZHANG)
    plan = build_category_plan(ctx, "ing")
    assert not plan.ok
    assert any("跟随底图" in e for e in plan.errors)


def test_capability_conflict_is_reported_once_not_per_item(tmp_path):
    """整批同因同果，说一遍就够 —— 逐条刷屏会把别的问题顶没。"""
    items = {f"i{n}": {"visual": f"v{n}"} for n in range(6)}
    ctx = _with_backend(
        _simple(tmp_path, items, aspect_ratio="16:9", model="gpt-image-1"),
        image_backend.LAOZHANG)
    plan = build_category_plan(ctx, "ing")
    assert len([e for e in plan.errors if "就近裁切" in e]) == 1


def test_allow_degrade_covers_capability_conflicts(tmp_path):
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x"}}, aspect_ratio="16:9",
                model="gpt-image-1"),
        image_backend.LAOZHANG)
    plan = build_category_plan(ctx, "ing", allow_degrade=True)
    assert plan.ok
    assert any("--allow-degrade" in w for w in plan.warnings)


def test_unreadable_backend_rules_speak_up(tmp_path, monkeypatch):
    """**「没发现」和「没看」得分开** —— 这是本仓库自己立的规矩，
    而这条路径以前静默返回空，check 一句话都不说。
    """
    monkeypatch.setattr(image_backend, "_laozhang_rules", lambda: None)
    ctx = _with_backend(
        _simple(tmp_path, {"a": {"visual": "x"}}, aspect_ratio="16:9",
                model="gpt-image-1"),
        image_backend.LAOZHANG)
    plan = build_category_plan(ctx, "ing")
    assert not plan.ok
    assert any("没检查" in e for e in plan.errors)
