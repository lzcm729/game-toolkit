#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 裁决单.json 校验后注入模板，生成单文件 裁决单.html。

    python build_page.py <裁决单.json> [--out <裁决单.html>] [--template <template.html>]

校验不过就不出页（退出码 1），错误逐条打到 stderr；只是提醒的（标题、ctx 里疑似代码名）
照出页、退出码 0。默认输出与输入同目录同名 .html。生成的页面不依赖网络，浏览器直接打开。

裁决单.json 的形状见 ../examples/裁决单.example.json；字段含义见 SKILL.md「写题」。
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE.parent / "template.html"
DATA_BEGIN = "/* DATA-BEGIN */"
DATA_END = "/* DATA-END */"

# 「不在这张单上的」六个组：分拣表每一档的去向。组名可以带括号补一句，前缀要对上。
OUTSIDE_GROUPS = ("程序已经修好的", "数值我定了", "直接进工程台账", "我会顺手改的",
                  "别的会话已改掉的", "其余仍开着的")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}[a-z]?$")
OPT_KEY = re.compile(r"^[A-Z][A-Z0-9]*$")
# 代码名只该进 refs：类名::方法、带扩展名的文件、CamelCase、snake_case
CODE_NAME = re.compile(r"::|\b\w+\.(?:cpp|hpp|h|cs|gd|py|ts|js|json|yaml|ini)\b"
                       r"|\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b|\b[a-z]+_[a-z0-9_]+\b")


def storage_key(page: dict) -> str:
    """本浏览器兜底存储的键。file:// 下所有本地页共用一个 origin，所以要按页区分。"""
    digest = hashlib.sha1(("%s\n%s" % (page.get("title", ""), page.get("eyebrow", ""))).encode("utf-8")).hexdigest()
    return "rulings-%s-%s" % (page.get("date", ""), digest[:8])


def _is_str(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def validate(data: dict) -> "tuple[list, list]":
    """返回 (errors, warnings)。errors 非空就不该出页。"""
    errors, warnings = [], []
    page = data.get("page")
    if not isinstance(page, dict):
        return ["缺 page 块"], warnings
    if not _is_str(page.get("title")):
        errors.append("page.title 要有")
    if not _is_str(page.get("date")) or not DATE.match(page["date"]):
        errors.append("page.date 要是 YYYY-MM-DD（同一天第二张单加字母后缀，如 2026-09-22b）")
    if not isinstance(page.get("intro", []), list) or not all(isinstance(x, str) for x in page.get("intro", [])):
        errors.append("page.intro 要是字符串列表")

    groups = data.get("groups")
    if not isinstance(groups, list) or not groups:
        errors.append("groups 至少一组")
        groups = []
    seen = {}
    for gi, g in enumerate(groups):
        where = "groups[%d]" % gi
        if not isinstance(g, dict):
            errors.append("%s 要是 mapping" % where)
            continue
        if not _is_str(g.get("id")) or not _is_str(g.get("title")):
            errors.append("%s 要有 id 和 title" % where)
        items = g.get("items")
        if not isinstance(items, list) or not items:
            errors.append("%s 至少一题" % where)
            continue
        for ii, d in enumerate(items):
            w = "%s.items[%d]" % (where, ii)
            if not isinstance(d, dict):
                errors.append("%s 要是 mapping" % w)
                continue
            did = d.get("id")
            if not _is_str(did):
                errors.append("%s 缺 id" % w)
            elif did in seen:
                errors.append("题 id 重复：%s（%s 和 %s）" % (did, seen[did], w))
            else:
                seen[did] = w
            label = did if _is_str(did) else w
            if not _is_str(d.get("title")):
                errors.append("%s 缺 title" % label)
            if not _is_str(d.get("ctx")):
                errors.append("%s 缺 ctx：读者没看过代码，要写现在是什么样、为什么要拍" % label)
            for field in ("refs", "facts"):
                v = d.get(field, [])
                if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                    errors.append("%s.%s 要是字符串列表" % (label, field))
            quotes = d.get("quotes", [])
            if not isinstance(quotes, list) or not all(
                    isinstance(q, list) and len(q) == 2 and all(isinstance(x, str) for x in q) for q in quotes):
                errors.append("%s.quotes 要是 [[出处, 原文], …]" % label)
            opts = d.get("opts")
            if not isinstance(opts, list) or not (2 <= len(opts) <= 3):
                errors.append("%s 的选项要 2～3 个" % label)
                opts = []
            keys, recs = [], 0
            for oi, o in enumerate(opts):
                if not isinstance(o, list) or not (3 <= len(o) <= 4) or not all(isinstance(x, str) for x in o[:3]):
                    errors.append("%s.opts[%d] 要是 [键, 短标签, 选了会发生什么, 倾向标记?]" % (label, oi))
                    continue
                if not OPT_KEY.match(o[0]):
                    errors.append("%s.opts[%d] 键要是大写字母（A/B/C）" % (label, oi))
                keys.append(o[0])
                if not _is_str(o[1]):
                    errors.append("%s.opts[%d] 短标签不能空" % (label, oi))
                if len(o) == 4 and o[3]:
                    recs += 1
            if len(keys) != len(set(keys)):
                errors.append("%s 的选项键重复" % label)
            if opts and recs != 1:
                errors.append("%s 要恰好一个倾向（现在 %d 个）：只给选项不给倾向，用户没法比" % (label, recs))
            for field in ("title", "ctx"):
                v = d.get(field)
                if isinstance(v, str):
                    m = CODE_NAME.search(v)
                    if m:
                        warnings.append("%s.%s 里疑似代码名「%s」：代码名进 refs，正文写玩家看得到的行为"
                                        % (label, field, m.group(0)))

    outside = data.get("outside", [])
    if not isinstance(outside, list):
        errors.append("outside 要是 [[组名, [行, …]], …]")
    else:
        for oi, entry in enumerate(outside):
            if not (isinstance(entry, list) and len(entry) == 2 and isinstance(entry[0], str)
                    and isinstance(entry[1], list) and all(isinstance(x, str) for x in entry[1])):
                errors.append("outside[%d] 要是 [组名, [行, …]]" % oi)
                continue
            if not entry[0].startswith(OUTSIDE_GROUPS):
                errors.append("outside[%d] 组名「%s」不在六个之内：%s" % (oi, entry[0], "／".join(OUTSIDE_GROUPS)))
            if not entry[1]:
                errors.append("outside[%d]「%s」没有内容就删掉这一组" % (oi, entry[0]))
    return errors, warnings


def _js(obj) -> str:
    # </script> 出现在字符串里会提前结束脚本块；JSON 允许 \/ 这个转义
    return json.dumps(obj, ensure_ascii=False, indent=1).replace("</", "<\\/")


def render(data: dict, template: str) -> str:
    if DATA_BEGIN not in template or DATA_END not in template:
        raise ValueError("模板里找不到 %s … %s 标记" % (DATA_BEGIN, DATA_END))
    page = dict(data["page"])
    page["storageKey"] = storage_key(page)
    page.setdefault("intro", [])
    page.setdefault("eyebrow", "")
    block = "const PAGE = %s;\nconst GROUPS = %s;\nconst OUTSIDE = %s;" % (
        _js(page), _js(data["groups"]), _js(data.get("outside", [])))
    head, rest = template.split(DATA_BEGIN, 1)
    _, tail = rest.split(DATA_END, 1)
    out = head + block + tail
    out = re.sub(r"<title>.*?</title>", "<title>%s</title>" % html.escape(page["title"]), out, count=1, flags=re.S)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="裁决单.json → 裁决单.html")
    ap.add_argument("source", help="裁决单.json")
    ap.add_argument("--out", default=None, help="输出 html；默认与输入同目录同名")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    args = ap.parse_args(argv)

    src = Path(args.source)
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("读不了 %s：%s" % (src, exc), file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print("%s 顶层要是 mapping" % src, file=sys.stderr)
        return 1
    errors, warnings = validate(data)
    for w in warnings:
        print("提醒：" + w, file=sys.stderr)
    if errors:
        print("校验不过，没有出页：\n  - " + "\n  - ".join(errors), file=sys.stderr)
        return 1
    template = Path(args.template).read_text(encoding="utf-8")
    out = Path(args.out) if args.out else src.with_suffix(".html")
    out.write_text(render(data, template), encoding="utf-8")
    n_items = sum(len(g["items"]) for g in data["groups"])
    print("已生成 %s：%d 组 %d 题；不在单上的 %d 组。浏览器直接打开。"
          % (out, len(data["groups"]), n_items, len(data.get("outside", []))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
