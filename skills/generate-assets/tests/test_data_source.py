"""data_source.py — 加载 + filter 测试。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_source import load_data_source


# -------------------- json_dict --------------------

def test_json_dict_basic(tmp_path, write_json):
    write_json("data.json", {
        "a": {"label": "Alpha", "color": "#fff"},
        "b": {"label": "Beta", "color": "#000"},
    })
    items = load_data_source(
        {"type": "json_dict", "path": "data.json"},
        tmp_path,
    )
    assert len(items) == 2
    ids = sorted(it["id"] for it in items)
    assert ids == ["a", "b"]
    assert any(it["label"] == "Alpha" for it in items)


def test_json_dict_explicit_id_kept(tmp_path, write_json):
    """value 已含 id 字段时保留 value.id（不被 key 覆盖）。"""
    write_json("data.json", {"key1": {"id": "explicit_id", "x": 1}})
    items = load_data_source({"type": "json_dict", "path": "data.json"}, tmp_path)
    assert items[0]["id"] == "explicit_id"


def test_json_dict_value_must_be_dict(tmp_path, write_json):
    write_json("data.json", {"a": "string-not-dict"})
    with pytest.raises(ValueError, match="必须是 dict"):
        load_data_source({"type": "json_dict", "path": "data.json"}, tmp_path)


def test_json_dict_top_level_must_be_dict(tmp_path, write_json):
    write_json("data.json", ["a", "b"])
    with pytest.raises(ValueError, match="顶层为 dict"):
        load_data_source({"type": "json_dict", "path": "data.json"}, tmp_path)


def test_json_dict_path_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_data_source({"type": "json_dict", "path": "nope.json"}, tmp_path)


def test_json_dict_no_path(tmp_path):
    with pytest.raises(ValueError, match="必须设 'path'"):
        load_data_source({"type": "json_dict"}, tmp_path)


def test_json_dict_res_prefix(tmp_path, write_json):
    write_json("art/data.json", {"x": {"y": 1}})
    items = load_data_source(
        {"type": "json_dict", "path": "res://art/data.json"},
        tmp_path,
    )
    assert items[0]["id"] == "x"


# -------------------- json_list --------------------

def test_json_list_basic(tmp_path, write_json):
    write_json("data.json", [
        {"id": "a", "x": 1},
        {"id": "b", "x": 2},
    ])
    items = load_data_source({"type": "json_list", "path": "data.json"}, tmp_path)
    assert len(items) == 2
    assert items[0]["id"] == "a"


def test_json_list_missing_id(tmp_path, write_json):
    write_json("data.json", [{"x": 1}])
    with pytest.raises(ValueError, match="缺少 'id'"):
        load_data_source({"type": "json_list", "path": "data.json"}, tmp_path)


def test_json_list_top_level_must_be_list(tmp_path, write_json):
    write_json("data.json", {"a": 1})
    with pytest.raises(ValueError, match="顶层为 list"):
        load_data_source({"type": "json_list", "path": "data.json"}, tmp_path)


def test_json_list_element_must_be_dict(tmp_path, write_json):
    write_json("data.json", ["not-dict"])
    with pytest.raises(ValueError, match="必须是 dict"):
        load_data_source({"type": "json_list", "path": "data.json"}, tmp_path)


# -------------------- inline --------------------

def test_inline_basic(tmp_path):
    items = load_data_source({
        "type": "inline",
        "items": {
            "pearl": {"main": "#1e1b4b"},
            "taro": {"main": "#4a1942"},
        }
    }, tmp_path)
    assert len(items) == 2
    assert {it["id"] for it in items} == {"pearl", "taro"}


def test_inline_no_items(tmp_path):
    with pytest.raises(ValueError, match="必须设 'items'"):
        load_data_source({"type": "inline"}, tmp_path)


def test_inline_items_must_be_dict(tmp_path):
    with pytest.raises(ValueError, match="必须是 dict"):
        load_data_source({"type": "inline", "items": ["a"]}, tmp_path)


def test_inline_value_must_be_dict(tmp_path):
    with pytest.raises(ValueError, match="必须是 dict"):
        load_data_source({"type": "inline", "items": {"k": "v"}}, tmp_path)


# -------------------- filter --------------------

def test_filter_field_eq(tmp_path):
    spec = {
        "type": "inline",
        "items": {
            "a": {"weakness": "pearl"},
            "b": {"weakness": "taro"},
            "c": {"weakness": "pearl"},
        },
        "filter": {"weakness": "pearl"},
    }
    items = load_data_source(spec, tmp_path)
    assert {it["id"] for it in items} == {"a", "c"}


def test_filter_len_suffix(tmp_path):
    spec = {
        "type": "inline",
        "items": {
            "a": {"toppings": ["x"]},
            "b": {"toppings": ["x", "y"]},
            "c": {"toppings": []},
        },
        "filter": {"toppings_len": 1},
    }
    items = load_data_source(spec, tmp_path)
    assert [it["id"] for it in items] == ["a"]


def test_filter_len_missing_field(tmp_path):
    """字段不存在视为不匹配。"""
    spec = {
        "type": "inline",
        "items": {"a": {"foo": 1}},
        "filter": {"toppings_len": 1},
    }
    items = load_data_source(spec, tmp_path)
    assert items == []


def test_filter_multi_conditions_all_must_match(tmp_path):
    spec = {
        "type": "inline",
        "items": {
            "a": {"k": 1, "tags": ["x"]},
            "b": {"k": 1, "tags": ["x", "y"]},
            "c": {"k": 2, "tags": ["x"]},
        },
        "filter": {"k": 1, "tags_len": 1},
    }
    items = load_data_source(spec, tmp_path)
    assert [it["id"] for it in items] == ["a"]


def test_filter_empty_dict_keeps_all(tmp_path):
    spec = {
        "type": "inline",
        "items": {"a": {"x": 1}, "b": {"x": 2}},
        "filter": {},
    }
    items = load_data_source(spec, tmp_path)
    assert len(items) == 2


# -------------------- 顶层 --------------------

def test_unknown_type(tmp_path):
    with pytest.raises(ValueError, match="未知 data_source type"):
        load_data_source({"type": "csv"}, tmp_path)


def test_missing_type(tmp_path):
    with pytest.raises(ValueError, match="缺少 'type'"):
        load_data_source({}, tmp_path)


def test_non_dict_spec(tmp_path):
    with pytest.raises(ValueError, match="必须是 dict"):
        load_data_source("not-dict", tmp_path)
