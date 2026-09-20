"""data_source.py — 加载 + filter 测试。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from data_source import load_data_source, _match_column


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
        load_data_source({"type": "xlsx"}, tmp_path)


def test_missing_type(tmp_path):
    with pytest.raises(ValueError, match="缺少 'type'"):
        load_data_source({}, tmp_path)


def test_non_dict_spec(tmp_path):
    with pytest.raises(ValueError, match="必须是 dict"):
        load_data_source("not-dict", tmp_path)


# -------------------- csv 列名匹配 --------------------

def test_match_column_exact():
    head = ["fish_id", "名字", "重量/KG"]
    assert _match_column("名字", head, where="id_column") == "名字"


def test_match_column_prefix():
    """策划表的表头常带括注，配置里只写短名。"""
    head = ["fish_id（资产文件名，如 Fish_RiverPattern）", "力量系数K（KG*K=力量）"]
    assert _match_column("fish_id", head, where="id_column") == head[0]
    assert _match_column("力量系数K", head, where="id_column") == head[1]


def test_match_column_exact_beats_prefix():
    """同时有「名字」和「名字（旧）」时，找「名字」必须命中精确的那个。

    注意精确的那个故意放在后面：如果实现只做前缀匹配取第一个，这条会红。
    """
    head = ["名字（旧）", "名字"]
    assert _match_column("名字", head, where="id_column") == "名字"


def test_match_column_ambiguous_prefix_raises():
    head = ["重量（kg）", "重量（lb）"]
    with pytest.raises(ValueError) as ei:
        _match_column("重量", head, where="columns 的键")
    msg = str(ei.value)
    assert "重量（kg）" in msg and "重量（lb）" in msg   # 列出歧义候选
    assert "columns 的键" in msg


def test_match_column_not_found_lists_available():
    head = ["fish_id", "名字"]
    with pytest.raises(ValueError) as ei:
        _match_column("体重", head, where="id_column")
    msg = str(ei.value)
    assert "体重" in msg
    assert "fish_id" in msg and "名字" in msg           # 列出可用列名


# -------------------- csv --------------------

def _write_csv(tmp_path, rel: str, text: str, *, bom: bool = False,
               encoding: str = "utf-8") -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode(encoding)
    if bom:
        data = b"\xef\xbb\xbf" + data
    p.write_bytes(data)
    return p


def _csv_spec(**extra):
    spec = {"type": "csv", "path": "fish.csv", "id_column": "fish_id"}
    spec.update(extra)
    return spec


def test_csv_basic(tmp_path):
    _write_csv(tmp_path, "fish.csv",
               "fish_id,名字,重量\nF_A,河纹鱼,0.4~3\nF_B,小银鱼,0.05~0.4\n")
    items = load_data_source(_csv_spec(), tmp_path)
    assert [it["id"] for it in items] == ["F_A", "F_B"]
    assert items[0]["名字"] == "河纹鱼"


def test_csv_handles_bom(tmp_path):
    """在线表格导出的 CSV 常带 BOM，用 utf-8 读会让第一个列名多出 \\ufeff。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n", bom=True)
    items = load_data_source(_csv_spec(), tmp_path)
    assert items[0]["id"] == "F_A"


def test_csv_id_column_matched_by_prefix(tmp_path):
    _write_csv(tmp_path, "fish.csv",
               '"fish_id（资产文件名，如 Fish_RiverPattern）",名字\nF_A,河纹鱼\n')
    items = load_data_source(_csv_spec(), tmp_path)
    assert items[0]["id"] == "F_A"


def test_csv_columns_mapping(tmp_path):
    """长列名当占位符不好用（DSL 的字段参数还只认 ASCII），映射成短名。"""
    _write_csv(tmp_path, "fish.csv",
               '"fish_id（资产文件名）","图鉴描述（给玩家看的一句话）"\nF_A,一条会反光的鱼\n')
    items = load_data_source(
        _csv_spec(columns={"图鉴描述": "description"}), tmp_path)
    assert items[0]["description"] == "一条会反光的鱼"


def test_csv_mapped_column_keeps_original_name_too(tmp_path):
    """映射过的列，原始列名也保留 —— 两边都能在模板里引用。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n")
    items = load_data_source(_csv_spec(columns={"名字": "name"}), tmp_path)
    assert items[0]["name"] == "河纹鱼"
    assert items[0]["名字"] == "河纹鱼"


def test_csv_unmapped_columns_keep_original_name(tmp_path):
    """没映射的列也要保留，derived_fields 可能要用。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字,稀有度\nF_A,河纹鱼,普通\n")
    items = load_data_source(_csv_spec(columns={"名字": "name"}), tmp_path)
    assert items[0]["稀有度"] == "普通"


def test_csv_values_stay_strings(tmp_path):
    """不做类型推断：转了就丢原始表示（001、前导零、0.4~3 这种范围写法）。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,力量,编号,重量\nF_A,6,001,0.4~3\n")
    items = load_data_source(_csv_spec(), tmp_path)
    assert items[0]["力量"] == "6"          # 字符串，不是 int
    assert items[0]["编号"] == "001"        # 前导零还在
    assert items[0]["重量"] == "0.4~3"


def test_csv_skips_blank_rows(tmp_path):
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n\n,\nF_B,小银鱼\n")
    items = load_data_source(_csv_spec(), tmp_path)
    assert [it["id"] for it in items] == ["F_A", "F_B"]


def test_csv_empty_id_reports_physical_line(tmp_path):
    """行号必须是文件里的物理行，且断言完整片段 —— 只断言数字会被路径里的数字满足。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n,小银鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    msg = str(ei.value)
    assert "第 3 行" in msg
    assert "fish_id" in msg


def test_csv_line_number_survives_multiline_cell(tmp_path):
    """多行单元格会让「第几条记录」和「第几行」错开，必须按物理行报。"""
    _write_csv(tmp_path, "fish.csv",
               'fish_id,描述\nF_A,"第一行\n第二行"\n,缺少ID\n')
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    assert "第 4 行" in str(ei.value)


def test_csv_duplicate_header_raises(tmp_path):
    """重复列名会让 id 取自前列、字段值取自后列，prompt 和文件名对不上。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,fish_id,名字\nF_A,F_B,河纹鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    msg = str(ei.value)
    assert "fish_id" in msg
    assert "重复" in msg


def test_csv_duplicate_header_after_strip_raises(tmp_path):
    """去空白之后才重复的也要抓到。"""
    _write_csv(tmp_path, "fish.csv", "fish_id, fish_id ,名字\nF_A,F_B,河纹鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    assert "重复" in str(ei.value)          # 别被其他 ValueError 假满足


def test_csv_alias_colliding_with_existing_column_raises(tmp_path):
    """别名撞上已有列名：谁覆盖谁取决于列顺序，必须拒绝而不是碰运气。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字,name\nF_A,河纹鱼,RiverFish\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(columns={"名字": "name"}), tmp_path)
    assert "name" in str(ei.value)


def test_csv_two_sources_to_same_alias_raises(tmp_path):
    _write_csv(tmp_path, "fish.csv", "fish_id,名字,别名\nF_A,河纹鱼,小河鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(
            _csv_spec(columns={"名字": "label", "别名": "label"}), tmp_path)
    assert "label" in str(ei.value)         # 别被其他 ValueError 假满足


def test_csv_two_keys_matching_same_column_raises(tmp_path):
    """两个键前缀匹配到同一列时，后写的别名会静默覆盖前一个。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(
            _csv_spec(columns={"名字": "full", "名": "short"}), tmp_path)
    assert "名字" in str(ei.value)


def test_csv_alias_to_id_raises(tmp_path):
    """id 是保留字段，由 id_column 决定。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(columns={"名字": "id"}), tmp_path)
    assert "id" in str(ei.value)


def test_csv_row_wider_than_header_raises(tmp_path):
    """多出来的单元格静默丢掉的话，数据错了也没人知道。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼,多余的\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    assert "第 2 行" in str(ei.value)


def test_csv_short_row_fills_empty(tmp_path):
    """短行补空字符串，这是常见且无害的。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字,稀有度\nF_A,河纹鱼\n")
    items = load_data_source(_csv_spec(), tmp_path)
    assert items[0]["稀有度"] == ""


def test_csv_missing_id_column_raises(tmp_path):
    _write_csv(tmp_path, "fish.csv", "名字,重量\n河纹鱼,0.4\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    assert "fish_id" in str(ei.value)


def test_csv_requires_id_column_field(tmp_path):
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source({"type": "csv", "path": "fish.csv"}, tmp_path)
    assert "id_column" in str(ei.value)


def test_csv_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_data_source(_csv_spec(path="nope.csv"), tmp_path)


def test_csv_empty_file_raises(tmp_path):
    _write_csv(tmp_path, "fish.csv", "")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    assert "表头" in str(ei.value)


def test_csv_blank_header_raises(tmp_path):
    """开头的空行会被当成表头，这跟数据区的空行不一样，得报出来。"""
    _write_csv(tmp_path, "fish.csv", ",,\nfish_id,名字\nF_A,河纹鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    assert "表头" in str(ei.value)


def test_csv_columns_not_a_dict_raises(tmp_path):
    """`or {}` 会让 [] 和 "" 绕过类型检查，必须显式判断。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n")
    for bad in ([], "", ["名字"]):
        with pytest.raises(ValueError) as ei:
            load_data_source(_csv_spec(columns=bad), tmp_path)
        assert "columns" in str(ei.value)


def test_csv_custom_encoding(tmp_path):
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n", encoding="gbk")
    items = load_data_source(_csv_spec(encoding="gbk"), tmp_path)
    assert items[0]["名字"] == "河纹鱼"


def test_csv_filter_still_works(tmp_path):
    """filter 是所有数据源共用的，csv 不该例外。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,稀有度\nF_A,普通\nF_B,稀有\n")
    items = load_data_source(_csv_spec(filter={"稀有度": "稀有"}), tmp_path)
    assert [it["id"] for it in items] == ["F_B"]


def test_csv_filter_is_string_comparison(tmp_path):
    """CSV 值是字符串，filter 用严格相等 —— 写 6 匹配不到 "6"。

    这是当前行为，文档里要写明，免得有人以为 filter 会帮忙转类型。
    """
    _write_csv(tmp_path, "fish.csv", "fish_id,力量\nF_A,6\n")
    assert load_data_source(_csv_spec(filter={"力量": 6}), tmp_path) == []
    assert len(load_data_source(_csv_spec(filter={"力量": "6"}), tmp_path)) == 1
