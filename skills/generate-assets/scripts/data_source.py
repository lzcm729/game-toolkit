"""数据源加载 + filter（v1：json_dict / json_list / inline）。

每个 loader 返回 list[dict]，每个 dict 至少含 "id"（json_dict 和 inline 用 key 当 id）。
filter 用 hardcoded operator dict（toppings_len / 字段值相等）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# -------------------- 数据源加载 --------------------

def load_data_source(spec: dict, project_root: Path) -> list[dict]:
    """根据 spec.type 分派到 loader。

    spec 字段：
      - type: "json_dict" / "json_list" / "inline"
      - path: (json_*) 相对 project_root 的 JSON 路径
      - items: (inline) yaml 内嵌 dict
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
    else:
        raise ValueError(
            f"未知 data_source type: {src_type!r}（v1 仅支持 json_dict / json_list / inline）"
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
