"""filter 边界 — 用 data_source 内部 helper 直接测。"""
from __future__ import annotations

import pytest

from data_source import _apply_filter, _matches_one


def test_match_eq_string():
    assert _matches_one({"k": "v"}, "k", "v") is True


def test_match_eq_int():
    assert _matches_one({"k": 1}, "k", 1) is True


def test_match_eq_mismatch():
    assert _matches_one({"k": "x"}, "k", "y") is False


def test_match_eq_missing_field():
    assert _matches_one({}, "k", "v") is False


def test_match_eq_none_field():
    assert _matches_one({"k": None}, "k", None) is True


def test_match_len_basic():
    assert _matches_one({"toppings": ["x"]}, "toppings_len", 1) is True


def test_match_len_zero():
    assert _matches_one({"toppings": []}, "toppings_len", 0) is True


def test_match_len_mismatch():
    assert _matches_one({"toppings": ["a", "b"]}, "toppings_len", 1) is False


def test_match_len_missing_field():
    assert _matches_one({}, "toppings_len", 1) is False


def test_match_len_field_is_string():
    """字符串也有 len，但语义不预期；至少不应崩。"""
    assert _matches_one({"x": "ab"}, "x_len", 2) is True


def test_match_len_field_is_int_returns_false():
    """int 没 len → 视为不匹配（不抛）。"""
    assert _matches_one({"x": 5}, "x_len", 5) is False


def test_apply_filter_keeps_order():
    items = [{"id": "a", "k": 1}, {"id": "b", "k": 2}, {"id": "c", "k": 1}]
    out = _apply_filter(items, {"k": 1})
    assert [it["id"] for it in out] == ["a", "c"]


def test_apply_filter_must_be_dict():
    with pytest.raises(ValueError, match="必须是 dict"):
        _apply_filter([{"k": 1}], "not-dict")  # type: ignore[arg-type]
