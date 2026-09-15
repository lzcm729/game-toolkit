#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把摘要构建成可发布的页面：加横幅、按平台 profile 修正标记、写到输出目录并生成索引。

    python build_summary_pages.py --summaries <摘要目录> --out <输出目录> --rev <仓库版本>
                                  [--manifest <清单.json>] [--ssot-root Knowledge/Design]
                                  [--profile plain|feishu] [--date YYYY-MM-DD] [--banner-template <文件>]

输出目录里每份页面与摘要同名同路径；另写 index.json（file / out / node_token / rev / date），
项目侧适配器按它逐页发布。构建不碰平台，也不改摘要原文。

profile：
- plain   不改标记（新平台先用它发一页试，回读看哪些标记变了字面字符）
- feishu  正文里的 **x** 改成 <b>x</b>（贴着全角标点的加粗会失效），表格行里的加粗去掉标记
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import re
import sys
from pathlib import Path

CRLF = "\r\n"
LF = "\n"
FRONT = re.compile(r"^---\n.*?\n---\n", re.S)
TITLE = re.compile(r"^\s*<title>.*?</title>\s*\n", re.S)
BOLD = re.compile(r"(?<!\\)\*\*(.+?)(?<!\\)\*\*")
DEFAULT_BANNER = ("> **规则版摘要**（{date}，据仓库 {rev}）。本页帮你快速建立心智模型，不保证与仓库同步；"
                  "判定细节、数值与出处以仓库 `{ssot_root}/{file}` 为准，改设计只改仓库。")


def read_text(p: Path) -> str:
    return io.open(p, "rb").read().decode("utf-8-sig").replace(CRLF, LF)


def strip_head(text: str) -> str:
    text = FRONT.sub("", text, count=1)
    text = TITLE.sub("", text, count=1)
    return text.strip(LF)


def fix_feishu(text: str) -> str:
    out = []
    for line in text.split(LF):
        if line.lstrip().startswith("|"):
            line = BOLD.sub(lambda m: m.group(1), line)
        else:
            line = BOLD.sub(lambda m: "<b>" + m.group(1) + "</b>", line)
        out.append(line)
    return LF.join(out)


PROFILES = {"plain": lambda t: t, "feishu": fix_feishu}


def render_banner(template: str, *, date: str, rev: str, ssot_root: str, file: str, profile: str) -> str:
    banner = template.format(date=date, rev=rev, ssot_root=ssot_root.rstrip("/"), file=file)
    return PROFILES[profile](banner)


def build_one(summary_text: str, *, banner: str, profile: str) -> str:
    body = PROFILES[profile](strip_head(summary_text))
    return banner + LF + LF + body + LF


def build(summaries: Path, out: Path, *, rev: str, ssot_root: str, profile: str, date: str,
          manifest: dict | None, banner_template: str) -> list[dict]:
    if profile not in PROFILES:
        raise ValueError(f"未知 profile：{profile}（可选 {', '.join(PROFILES)}）")
    docs = {d["file"]: d for d in (manifest or {}).get("docs", []) if d.get("file")}
    files = sorted(docs) if docs else sorted(str(p.relative_to(summaries)).replace("\\", "/") for p in summaries.rglob("*.md"))
    index = []
    for rel in files:
        src = summaries / rel
        if not src.is_file():
            continue
        banner = render_banner(banner_template, date=date, rev=rev, ssot_root=ssot_root, file=rel, profile=profile)
        page = build_one(read_text(src), banner=banner, profile=profile)
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        io.open(dst, "w", encoding="utf-8", newline=LF).write(page)
        entry = {"file": rel, "out": str(dst), "rev": rev, "date": date, "profile": profile}
        if rel in docs:
            entry["node_token"] = docs[rel].get("node_token")
        index.append(entry)
    out.mkdir(parents=True, exist_ok=True)
    io.open(out / "index.json", "w", encoding="utf-8", newline=LF).write(json.dumps(index, ensure_ascii=False, indent=1) + LF)
    return index


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summaries", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rev", required=True, help="仓库版本：短 hash 或版本号")
    ap.add_argument("--manifest", help="清单 JSON；给了就只构建清单里的文档并带上页身份")
    ap.add_argument("--ssot-root", default="Knowledge/Design", help="横幅里真值路径的前缀")
    ap.add_argument("--profile", default="plain", choices=sorted(PROFILES))
    ap.add_argument("--date", default=dt.date.today().isoformat())
    ap.add_argument("--banner-template", help="横幅模板文件，占位 {date} {rev} {ssot_root} {file}")
    a = ap.parse_args(argv)
    summaries = Path(a.summaries)
    if not summaries.is_dir():
        print(f"摘要目录不存在：{summaries}")
        return 1
    manifest = json.loads(read_text(Path(a.manifest))) if a.manifest else None
    template = read_text(Path(a.banner_template)).strip(LF) if a.banner_template else DEFAULT_BANNER
    index = build(summaries, Path(a.out), rev=a.rev, ssot_root=a.ssot_root, profile=a.profile, date=a.date,
                  manifest=manifest, banner_template=template)
    print(f"构建 {len(index)} 页 → {a.out}（profile={a.profile}，rev={a.rev}）")
    for e in index:
        print("  ", e["file"], "" if e.get("node_token") else "（清单里没有页身份）")
    return 0 if index else 1


if __name__ == "__main__":
    sys.exit(main())
