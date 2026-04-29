"""prompt_render.py — 模板 + derived DSL 测试。"""
from __future__ import annotations

import pytest

from prompt_render import (
    compose_prompt,
    evaluate_derived,
    list_helpers,
    render_template,
)


# -------------------- render_template --------------------

def test_render_basic():
    out = render_template("Hello {name}", {"name": "world"})
    assert out == "Hello world"


def test_render_multiple_fields():
    out = render_template("{a} + {b} = {c}", {"a": 1, "b": 2, "c": 3})
    assert out == "1 + 2 = 3"


def test_render_missing_field_raises():
    with pytest.raises(KeyError, match="不存在的字段"):
        render_template("Hello {missing}", {"name": "x"})


def test_render_with_id_in_error():
    with pytest.raises(KeyError, match="item.id='abc'"):
        render_template("{absent}", {"id": "abc"})


def test_render_template_must_be_string():
    with pytest.raises(ValueError, match="必须是字符串"):
        render_template(None, {})  # type: ignore[arg-type]


def test_render_positional_placeholder_rejected():
    with pytest.raises(ValueError, match="位置占位符"):
        render_template("Hello {0}", {"name": "x"})


def test_render_extra_fields_ignored():
    """item 多出的字段不报错。"""
    out = render_template("{a}", {"a": 1, "b": 2, "id": "x"})
    assert out == "1"


# -------------------- compose_prompt --------------------

def test_compose_full():
    out = compose_prompt(
        "middle text",
        global_prefix="PREFIX",
        global_suffix="SUFFIX",
    )
    assert out == "PREFIX middle text SUFFIX"


def test_compose_skip_global():
    out = compose_prompt(
        "only middle",
        global_prefix="PREFIX",
        global_suffix="SUFFIX",
        skip_global=True,
    )
    assert out == "only middle"


def test_compose_empty_prefix_suffix():
    out = compose_prompt("middle")
    assert out == "middle"


def test_compose_strips_whitespace():
    out = compose_prompt(
        "  middle  ",
        global_prefix="  PREFIX  ",
        global_suffix="  SUFFIX  ",
    )
    assert out == "PREFIX middle SUFFIX"


def test_compose_empty_middle():
    out = compose_prompt("", global_prefix="P", global_suffix="S")
    assert out == "P S"


# -------------------- derived: helpers list --------------------

def test_list_helpers_includes_join():
    helpers = list_helpers()
    assert "join" in helpers
    assert "upper" in helpers
    assert "lower" in helpers
    assert "title" in helpers


# -------------------- derived: join --------------------

def test_derived_join_basic():
    out = evaluate_derived(
        {"toppings": ["pearl", "taro"]},
        {"toppings_str": 'join(toppings, ", ")'},
    )
    assert out["toppings_str"] == "pearl, taro"


def test_derived_join_single():
    out = evaluate_derived(
        {"toppings": ["pearl"]},
        {"toppings_str": 'join(toppings, ", ")'},
    )
    assert out["toppings_str"] == "pearl"


def test_derived_join_empty_list():
    out = evaluate_derived(
        {"toppings": []},
        {"toppings_str": 'join(toppings, ", ")'},
    )
    assert out["toppings_str"] == ""


def test_derived_join_double_quoted():
    out = evaluate_derived(
        {"items": ["a", "b"]},
        {"r": 'join(items, " | ")'},
    )
    assert out["r"] == "a | b"


def test_derived_join_missing_field():
    with pytest.raises(KeyError, match="不存在"):
        evaluate_derived(
            {"x": 1},
            {"r": 'join(toppings, ", ")'},
        )


def test_derived_join_non_list_field():
    with pytest.raises(ValueError, match="必须是 list/tuple"):
        evaluate_derived(
            {"toppings": "string-not-list"},
            {"r": 'join(toppings, ", ")'},
        )


def test_derived_join_arity_error():
    with pytest.raises(ValueError, match="需要 2 个参数"):
        evaluate_derived({"x": [1]}, {"r": "join(x)"})


# -------------------- derived: simple helpers --------------------

def test_derived_upper():
    out = evaluate_derived({"name": "alpha"}, {"u": "upper(name)"})
    assert out["u"] == "ALPHA"


def test_derived_lower():
    out = evaluate_derived({"name": "ALPHA"}, {"l": "lower(name)"})
    assert out["l"] == "alpha"


def test_derived_title():
    out = evaluate_derived({"name": "the lord of"}, {"t": "title(name)"})
    assert out["t"] == "The Lord Of"


def test_derived_simple_arity_error():
    with pytest.raises(ValueError, match="需要 1 个"):
        evaluate_derived({"name": "x"}, {"r": "upper(name, extra)"})


def test_derived_simple_field_must_be_word():
    with pytest.raises(ValueError, match="bareword"):
        evaluate_derived({"name": "x"}, {"r": 'upper("literal")'})


# -------------------- derived: error cases --------------------

def test_derived_unknown_helper():
    with pytest.raises(ValueError, match="未知 derived_fields helper"):
        evaluate_derived({"x": 1}, {"r": "frobnicate(x)"})


def test_derived_invalid_expr_no_parens():
    with pytest.raises(ValueError, match="无效的"):
        evaluate_derived({"x": 1}, {"r": "join"})


def test_derived_expr_must_be_string():
    with pytest.raises(ValueError, match="必须是字符串"):
        evaluate_derived({"x": 1}, {"r": 42})  # type: ignore[dict-item]


def test_derived_chained_uses_already_derived():
    """先生成的 derived 字段可被后续 derived 引用（按 dict 插入顺序）。"""
    out = evaluate_derived(
        {"toppings": ["a", "b"]},
        {
            "toppings_str": 'join(toppings, ", ")',
            "toppings_upper": "upper(toppings_str)",
        },
    )
    assert out["toppings_str"] == "a, b"
    assert out["toppings_upper"] == "A, B"


def test_derived_does_not_mutate_input():
    item = {"x": "a"}
    evaluate_derived(item, {"y": "upper(x)"})
    assert "y" not in item


def test_derived_none_spec_returns_copy():
    item = {"x": 1}
    out = evaluate_derived(item, None)
    assert out == {"x": 1}
    assert out is not item


def test_derived_empty_spec_returns_copy():
    item = {"x": 1}
    out = evaluate_derived(item, {})
    assert out == {"x": 1}


# -------------------- end-to-end via render --------------------

def test_render_uses_derived():
    item = evaluate_derived(
        {"id": "cup1", "label": "Pearl Cup", "toppings": ["pearl"]},
        {"toppings_str": 'join(toppings, ", ")'},
    )
    out = render_template("'{label}' contains {toppings_str}", item)
    assert out == "'Pearl Cup' contains pearl"
