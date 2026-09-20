"""数据源加载 + filter（json_dict / json_list / inline / csv）。

每个 loader 返回 list[dict]，每个 dict 至少含 "id"（json_dict 和 inline 用 key 当 id）。
filter 用 hardcoded operator dict（toppings_len / 字段值相等）。
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


# -------------------- 数据源加载 --------------------

def load_data_source(spec: dict, project_root: Path) -> list[dict]:
    """根据 spec.type 分派到 loader。

    spec 字段：
      - type: "json_dict" / "json_list" / "inline" / "csv"
      - path: (json_* / csv) 相对 project_root 的文件路径
      - items: (inline) yaml 内嵌 dict
      - id_column: (csv) 哪一列当 id，按精确/唯一前缀匹配表头
      - columns: (csv, 可选) {表里的列名: item 里的字段名}
      - encoding: (csv, 可选) 缺省 utf-8-sig
      - filter: (可选) 简单 dict，过滤条件（见 _apply_filter）

    返回：list[dict]，每个 dict 必含 "id" 字段。
    """
    if not isinstance(spec, dict):
        raise ValueError(f"data_source 必须是 dict，得到 {type(spec).__name__}")

    src_type = spec.get("type")
    if src_type is None:
        raise ValueError("data_source 缺少 'type' 字段")

    if src_type == "json_dict":
        items = _load_json_dict(spec, project_root)
    elif src_type == "json_list":
        items = _load_json_list(spec, project_root)
    elif src_type == "inline":
        items = _load_inline(spec)
    elif src_type == "csv":
        items = _load_csv(spec, project_root)
    else:
        raise ValueError(
            f"未知 data_source type: {src_type!r}"
            "（支持：json_dict / json_list / inline / csv）"
        )

    flt = spec.get("filter")
    if flt:
        items = _apply_filter(items, flt)

    return items


def _resolve_path(rel: str, project_root: Path) -> Path:
    """解析相对路径（接受 res:// 前缀）。"""
    if rel.startswith("res://"):
        rel = rel[len("res://"):]
    p = Path(rel)
    if p.is_absolute():
        return p
    return project_root / p


def _match_column(name: str, header: list[str], *, where: str) -> str:
    """把配置里写的列名匹配到表头里的实际列名。

    精确优先，其次唯一前缀 —— 策划表的表头常带括注
    （「力量系数K（KG*K=力量）」），配置里只写短名。

    与使用方项目 check_fish_table_vs_definition.py 的 match_col 同策略：
    同一份 CSV 在两个工具里对不上列，是那个项目明令禁止的双口径。
    差别只在匹配失败时本函数抛错而不是返回 None —— 配置错误该在开跑前报，
    不该拖到渲染阶段变成一个看不懂的 KeyError。

    「精确优先」不是多余的：表里同时有「名字」和「名字（旧）」时，
    找「名字」必须命中前者，而不是报前缀歧义。
    """
    exact = [h for h in header if h == name]
    if exact:
        return exact[0]

    prefixed = [h for h in header if h.startswith(name)]
    if len(prefixed) == 1:
        return prefixed[0]
    if len(prefixed) > 1:
        raise ValueError(
            "{} 里的列名 {!r} 匹配到多列，无法判断用哪个：{}。"
            "把它写得更长一些以区分。".format(where, name, prefixed)
        )
    raise ValueError(
        "{} 里的列名 {!r} 在表头里找不到。可用列名：{}".format(where, name, header)
    )


def _load_json_dict(spec: dict, project_root: Path) -> list[dict]:
    path = spec.get("path")
    if not path:
        raise ValueError("data_source.type=json_dict 必须设 'path'")
    full = _resolve_path(path, project_root)
    if not full.exists():
        raise FileNotFoundError(f"data_source 路径不存在: {full}")
    with full.open(encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(
            f"data_source.type=json_dict 期望 JSON 顶层为 dict，{full} 实际为 {type(raw).__name__}"
        )
    items: list[dict] = []
    for key, value in raw.items():
        if not isinstance(value, dict):
            raise ValueError(
                f"json_dict 的 value 必须是 dict（key={key!r}），实际 {type(value).__name__}"
            )
        item = dict(value)
        # key 当 id；如果 value 已含 id 且不一致，尊重 value.id 但仍以 key 为 dict-key
        item.setdefault("id", key)
        items.append(item)
    return items


def _load_json_list(spec: dict, project_root: Path) -> list[dict]:
    path = spec.get("path")
    if not path:
        raise ValueError("data_source.type=json_list 必须设 'path'")
    full = _resolve_path(path, project_root)
    if not full.exists():
        raise FileNotFoundError(f"data_source 路径不存在: {full}")
    with full.open(encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise ValueError(
            f"data_source.type=json_list 期望 JSON 顶层为 list，{full} 实际为 {type(raw).__name__}"
        )
    items: list[dict] = []
    for i, value in enumerate(raw):
        if not isinstance(value, dict):
            raise ValueError(
                f"json_list 第 {i} 个元素必须是 dict，实际 {type(value).__name__}"
            )
        if "id" not in value:
            raise ValueError(f"json_list 第 {i} 个元素缺少 'id' 字段: {value!r}")
        items.append(dict(value))
    return items


def _load_inline(spec: dict) -> list[dict]:
    items_raw = spec.get("items")
    if items_raw is None:
        raise ValueError("data_source.type=inline 必须设 'items'")
    if not isinstance(items_raw, dict):
        raise ValueError(
            f"data_source.type=inline 的 items 必须是 dict，实际 {type(items_raw).__name__}"
        )
    items: list[dict] = []
    for key, value in items_raw.items():
        if not isinstance(value, dict):
            raise ValueError(
                f"inline 的 value 必须是 dict（key={key!r}），实际 {type(value).__name__}"
            )
        item = dict(value)
        item.setdefault("id", key)
        items.append(item)
    return items


def _load_csv(spec: dict, project_root: Path) -> list[dict]:
    """读策划表。

    列名按 _match_column 的规则匹配（精确优先、其次唯一前缀），所以配置里
    写短名即可，不必抄表头里那一长串括注。

    单元格值一律保持字符串：CSV 没有类型信息，一旦转换就丢了原始表示
    （"001" 的前导零、"0.4~3" 这种范围写法），而且同一列的取值类型会变得
    不稳定。注意现有 derived_fields 的 DSL 只有 join/upper/lower/title，
    没有数值转换，字段参数也只认 ASCII 标识符。

    宁可报错不要静默丢数据：重复列名、超宽行、别名撞车都直接抛，
    因为它们会让 prompt 里的 {字段} 和输出文件名对不上，那种 bug 极难查。
    """
    path = spec.get("path")
    if not path:
        raise ValueError("data_source.type=csv 必须设 'path'")
    id_column = spec.get("id_column")
    if not id_column:
        raise ValueError(
            "data_source.type=csv 必须设 'id_column' —— id 决定输出文件名，"
            "没法从表里猜"
        )

    full = _resolve_path(path, project_root)
    if not full.exists():
        raise FileNotFoundError(f"data_source 路径不存在: {full}")

    # utf-8-sig：在线表格导出的 CSV 常带 BOM，用 utf-8 读会让第一个列名
    # 多出 ﻿，前缀匹配随之失效且报错完全看不出原因。
    # 它也能正确读不带 BOM 的文件。
    encoding = spec.get("encoding") or "utf-8-sig"
    with full.open(encoding=encoding, newline="") as f:
        reader = csv.reader(f)
        # 记录每条记录的**起始物理行**：单元格里可以有换行，
        # 「第几条记录」和「第几行」会错开，报错要按人看得到的行号说。
        records: list[tuple[int, list[str]]] = []
        prev_end = 0
        for row in reader:
            records.append((prev_end + 1, row))
            prev_end = reader.line_num

    if not records:
        raise ValueError(f"CSV 是空的，读不到表头: {full}")

    header = [h.strip() for h in records[0][1]]
    if not any(header):
        raise ValueError(
            f"{full} 的表头是空的（第 1 行没有任何列名）。"
            "开头如果有空行，删掉它 —— 表头必须是第一行。"
        )

    seen_cols: dict[str, int] = {}
    for idx, col in enumerate(header):
        if not col:
            continue
        if col in seen_cols:
            raise ValueError(
                "{} 的表头有重复列名 {!r}（第 {} 列和第 {} 列）。"
                "重复列会让 id 取自前一列、字段值取自后一列，"
                "prompt 里的占位符和输出文件名就对不上了。".format(
                    full, col, seen_cols[col] + 1, idx + 1
                )
            )
        seen_cols[col] = idx

    id_col = _match_column(id_column, header, where="id_column")
    id_idx = header.index(id_col)

    # columns: {表里的列名(短名): item 里的字段名}
    mapping_raw = spec.get("columns")
    if mapping_raw is None:
        mapping_raw = {}
    if not isinstance(mapping_raw, dict):
        raise ValueError(
            f"data_source.columns 必须是映射（列名 → 字段名），"
            f"实际是 {type(mapping_raw).__name__}"
        )

    renames: dict[str, str] = {}
    alias_from: dict[str, str] = {}
    for src_name, dst_name in mapping_raw.items():
        actual = _match_column(str(src_name), header, where="columns 的键")
        dst = str(dst_name)
        if dst == "id":
            raise ValueError(
                "columns 不能把 {!r} 映射成 'id' —— id 是保留字段，"
                "由 id_column 决定。".format(actual)
            )
        if dst in seen_cols:
            raise ValueError(
                "columns 把 {!r} 映射成 {!r}，但表里已经有一列叫 {!r}。"
                "谁覆盖谁取决于列顺序，所以这里直接拒绝：换个别名。".format(
                    actual, dst, dst
                )
            )
        if dst in alias_from:
            raise ValueError(
                "columns 把 {!r} 和 {!r} 都映射成了 {!r}，只能留一个。".format(
                    alias_from[dst], actual, dst
                )
            )
        if actual in renames:
            # 两个键前缀匹配到同一列（如「名字」和「名」都命中「名字」），
            # 不拦的话后写的别名会静默覆盖前一个
            raise ValueError(
                "columns 里有两个键都匹配到列 {!r}（别名 {!r} 和 {!r}），"
                "把键写得更长一些以区分。".format(actual, renames[actual], dst)
            )
        alias_from[dst] = actual
        renames[actual] = dst

    items: list[dict] = []
    for line_no, row in records[1:]:
        if not any((cell or "").strip() for cell in row):
            continue        # 整行空：导出的 CSV 常带尾部空行

        if len(row) > len(header):
            raise ValueError(
                "{} 第 {} 行有 {} 个单元格，表头只有 {} 列。"
                "多出来的会被丢掉，所以这里直接报错 —— 检查这行是不是多了逗号。"
                .format(full, line_no, len(row), len(header))
            )

        item: dict[str, Any] = {}
        for i, col in enumerate(header):
            if not col:
                continue
            value = row[i] if i < len(row) else ""
            item[col] = value
            if col in renames:
                item[renames[col]] = value

        raw_id = (row[id_idx] if id_idx < len(row) else "").strip()
        if not raw_id:
            raise ValueError(
                "{} 第 {} 行的 {!r} 是空的。id 决定输出文件名，不能为空 —— "
                "删掉这行或补上 id。".format(full, line_no, id_col)
            )
        item["id"] = raw_id
        items.append(item)

    return items


# -------------------- filter --------------------

# 已知的 *_len suffix operator
_LEN_SUFFIX = "_len"


def _apply_filter(items: list[dict], flt: dict) -> list[dict]:
    """简单条件过滤。每个 (key, expected) 必须满足。

    支持的 key 形式：
      - "field_len": int → len(item.get("field") or []) == int
      - "field": value → item.get("field") == value
    """
    if not isinstance(flt, dict):
        raise ValueError(f"filter 必须是 dict，得到 {type(flt).__name__}")

    out: list[dict] = []
    for item in items:
        if _matches_filter(item, flt):
            out.append(item)
    return out


def _matches_filter(item: dict, flt: dict) -> bool:
    for key, expected in flt.items():
        if not _matches_one(item, key, expected):
            return False
    return True


def _matches_one(item: dict, key: str, expected: Any) -> bool:
    # *_len → 长度比较
    if key.endswith(_LEN_SUFFIX):
        field = key[: -len(_LEN_SUFFIX)]
        seq = item.get(field)
        if seq is None:
            return False
        try:
            actual_len = len(seq)
        except TypeError:
            return False
        return actual_len == expected

    # 直接 equality
    return item.get(key) == expected
