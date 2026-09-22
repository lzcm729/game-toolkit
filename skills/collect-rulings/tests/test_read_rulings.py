# -*- coding: utf-8 -*-
"""read_rulings.py：把 裁决单.json 和 裁决结果 按 id 对上，出复述表骨架。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import read_rulings as rr  # noqa: E402

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "裁决单.example.json"


def _page(tmp_path):
    p = tmp_path / "裁决单.json"
    p.write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    return p


def _result(tmp_path, choices, notes=None, done=True, date="2026-09-22"):
    p = tmp_path / "裁决结果.json"
    p.write_text(json.dumps({"date": date, "choices": choices, "notes": notes or {}, "done": done},
                            ensure_ascii=False), encoding="utf-8")
    return p


def test_table_marks_recommended_and_notes(tmp_path, capsys):
    page = _page(tmp_path)
    res = _result(tmp_path, {"E1": "A", "E2": "B"}, {"E2": "18 格\n理由：先试试"})
    assert rr.main([str(page), str(res)]) == 0
    out = capsys.readouterr().out
    assert "| E1 |" in out and "| 是 |" in out          # E1 选的是倾向
    assert "| E2 |" in out and "| 否 |" in out          # E2 选的不是倾向
    assert "18 格 / 理由：先试试" in out               # 备注压成一行
    assert "未选：F1" in out                            # 没选的列出来
    assert "我理解为" in out and "我读成" in out         # 提醒要复述的两类


def test_all_recommended_still_demands_table(tmp_path, capsys):
    page = _page(tmp_path)
    res = _result(tmp_path, {"E1": "A", "E2": "A", "F1": "A"})
    assert rr.main([str(page), str(res)]) == 0
    assert "这不是跳过复述的理由" in capsys.readouterr().out


def test_unknown_id_means_wrong_file(tmp_path, capsys):
    page = _page(tmp_path)
    res = _result(tmp_path, {"Z9": "A"})
    assert rr.main([str(page), str(res)]) == 1
    assert "Z9" in capsys.readouterr().err


def test_date_mismatch_is_rejected(tmp_path, capsys):
    page = _page(tmp_path)
    res = _result(tmp_path, {"E1": "A"}, date="2026-01-01")
    assert rr.main([str(page), str(res)]) == 1
    assert "date" in capsys.readouterr().err


def test_unknown_option_key_is_rejected(tmp_path, capsys):
    page = _page(tmp_path)
    res = _result(tmp_path, {"E1": "Q"})
    assert rr.main([str(page), str(res)]) == 1


def test_pasted_text_fallback(tmp_path, capsys):
    page = _page(tmp_path)
    text = tmp_path / "贴回来的.txt"
    text.write_text("【背包与装备栏】\nE1 装备栏要不要单独做：A（做两格装备栏）\nE2 背包多少格（E1＝A 时）：B（另定）\n"
                    "    备注：18 格\n【战斗】\nF1 倒地后能不能被队友拉起：（未选）\n", encoding="utf-8")
    assert rr.main([str(page), "--text", str(text)]) == 0
    out = capsys.readouterr().out
    assert "| E1 |" in out and "| E2 |" in out and "18 格" in out and "未选：F1" in out
    assert "未知（贴回的文字）" in out
