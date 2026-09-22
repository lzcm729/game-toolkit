#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 裁决单.json 和用户的选择按 id 对上，打出复述表骨架。

    python read_rulings.py <裁决单.json> <裁决结果.json>
    python read_rulings.py <裁决单.json> --text <贴回来的结果文字.txt>   # 页面「复制结果文字」的兜底

「我打算怎么落」那一列留空给 agent 填；非倾向项和备注单独点名，提醒要复述。
结果文件的 id 或选项键对不上裁决单、date 对不上，都当成拿错了文件：退出码 1。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 结果文字一行长这样：E1 装备栏要不要单独做：A（做两格装备栏）   或   …：（未选）
TEXT_LINE = re.compile(r"：(?:(?P<key>[A-Za-z0-9]+)（[^（）]*）|（未选）)\s*$")
NOTE_LINE = re.compile(r"^\s*备注：(?P<note>.*)$")


def index_page(data: dict) -> dict:
    """id → {group, title, opts: {key: (label, rec)}}"""
    out = {}
    for g in data.get("groups", []):
        for d in g.get("items", []):
            out[d["id"]] = {
                "group": g.get("title", ""),
                "title": d.get("title", ""),
                "opts": {o[0]: (o[1], bool(len(o) > 3 and o[3])) for o in d.get("opts", [])},
            }
    return out


def parse_text(text: str) -> dict:
    choices, notes, last = {}, {}, None
    for raw in text.splitlines():
        line = raw.rstrip()
        m = NOTE_LINE.match(line)
        if m and last:
            notes[last] = m.group("note").strip()
            continue
        m = TEXT_LINE.search(line)
        if not m:
            continue
        head = line.strip().split(None, 1)[0]
        did = head.split("：", 1)[0]
        last = did
        if m.group("key"):
            choices[did] = m.group("key")
    return {"choices": choices, "notes": notes, "done": None, "date": None}


def restate(page: dict, result: dict) -> "tuple[str, list]":
    """返回 (复述表文本, 错误列表)。"""
    items = index_page(page)
    errors = []
    pdate = page.get("page", {}).get("date")
    if result.get("date") and pdate and result["date"] != pdate:
        errors.append("date 对不上：裁决单是 %s，结果是 %s —— 拿错文件了？" % (pdate, result["date"]))
    choices = result.get("choices") or {}
    notes = result.get("notes") or {}
    for did, key in choices.items():
        if did not in items:
            errors.append("结果里的题 %s 不在裁决单上 —— 拿错文件了？" % did)
        elif key not in items[did]["opts"]:
            errors.append("题 %s 选了不存在的选项 %r（有的是 %s）" % (did, key, "/".join(items[did]["opts"])))
    if errors:
        return "", errors

    if result.get("done") is None:
        done_text = "未知（贴回的文字）"
    elif result.get("done"):
        done_text = "已点「我选好了」"
    else:
        done_text = "没点「我选好了」"
    lines = ["# 复述表 · %s · %s" % (page["page"].get("title", ""), pdate or ""),
             "", "完成标记：%s" % done_text,
             "", "| 题号 | 题目 | 用户选的 | 倾向？ | 备注 | 我打算怎么落 |", "|---|---|---|---|---|---|"]
    unanswered, non_rec, noted = [], [], []
    for did, meta in items.items():
        key = choices.get(did)
        note = (notes.get(did) or "").replace("\r", "")
        note_flat = " / ".join(s.strip() for s in note.split("\n") if s.strip())
        if not key:
            unanswered.append(did)
            lines.append("| %s | %s | （未选） | | %s | |" % (did, meta["title"], note_flat))
            continue
        label, rec = meta["opts"][key]
        if not rec:
            non_rec.append(did)
        if note_flat:
            noted.append(did)
        lines.append("| %s | %s | %s %s | %s | %s | |" % (did, meta["title"], key, label, "是" if rec else "否", note_flat))
    lines.append("")
    if unanswered:
        lines.append("未选：%s —— 问用户是漏了还是有意跳过。" % ", ".join(unanswered))
    if non_rec:
        lines.append("非倾向项：%s —— 每条在表后写一句「我理解为……」。" % ", ".join(non_rec))
    if noted:
        lines.append("有备注：%s —— 每条在表后写一句「我读成……」；读不懂的写成问句，不猜。" % ", ".join(noted))
    if not (unanswered or non_rec or noted):
        lines.append("全部选了倾向、没有备注 —— 表照写，这不是跳过复述的理由。")
    return "\n".join(lines), []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="裁决单 + 结果 → 复述表")
    ap.add_argument("page", help="裁决单.json")
    ap.add_argument("result", nargs="?", help="裁决结果.json")
    ap.add_argument("--text", help="贴回来的结果文字文件（- 读 stdin）")
    args = ap.parse_args(argv)
    if not args.result and not args.text:
        ap.error("要给 裁决结果.json，或 --text 结果文字")

    try:
        page = json.loads(Path(args.page).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("读不了裁决单 %s：%s" % (args.page, exc), file=sys.stderr)
        return 1
    if args.text:
        text = sys.stdin.read() if args.text == "-" else Path(args.text).read_text(encoding="utf-8")
        result = parse_text(text)
    else:
        try:
            result = json.loads(Path(args.result).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print("读不了结果 %s：%s" % (args.result, exc), file=sys.stderr)
            return 1
    table, errors = restate(page, result)
    if errors:
        print("对不上，先别复述：\n  - " + "\n  - ".join(errors), file=sys.stderr)
        return 1
    print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
