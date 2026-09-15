#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查规则版摘要：结构、超长规则、死概念、与清单一一对应。

    python check_summaries.py --summaries <摘要目录> [--manifest <清单.json>] [--dead-words <词表>]
                              [--max-rule-len 60] [--exempt <相对路径> ...] [--json]

退出码 0 = 全过；1 = 有问题或缺文件。只查结构与词表，查不出规则写反了。

摘要目录里的文件按详稿的相对路径命名；给了清单就要求 docs[].file 每份都有摘要，
没给清单就检查目录里全部 .md。词表一行一个词，`#` 开头是注释。
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

REQUIRED = ("# 一句话", "# 规则")
CRLF = "\r\n"
LF = "\n"


def read_text(p: Path) -> str:
    return io.open(p, "rb").read().decode("utf-8-sig").replace(CRLF, LF)


def load_dead_words(p: Path | None) -> list[str]:
    if not p:
        return []
    words = []
    for line in read_text(p).split(LF):
        line = line.strip()
        if line and not line.startswith("#"):
            words.append(line)
    return words


def manifest_files(p: Path | None, key: str = "docs") -> list[str] | None:
    if not p:
        return None
    data = json.loads(read_text(p))
    return [d["file"] for d in data.get(key, []) if d.get("file")]


def check_text(text: str, max_rule_len: int, dead_words: list[str]) -> dict:
    lines = text.split(LF)
    rules = [l for l in lines if l.startswith("- ")]
    groups = [l[3:] for l in lines if l.startswith("## ")]
    problems: list[str] = []
    for req in REQUIRED:
        if not any(l.rstrip() == req for l in lines):
            problems.append(f"缺 {req}")
    if "**" in text:
        problems.append("有加粗")
    if any(l.startswith("|") for l in lines):
        problems.append("有表格")
    if any(re.match(r"^\s+[-*] ", l) for l in lines):
        problems.append("有嵌套列表")
    if any(l.startswith("> ") for l in lines):
        problems.append("有引用块")
    if any(re.match(r"^#{3,} ", l) for l in lines):
        problems.append("有三级以上标题")
    if not rules:
        problems.append("没有规则条")
    long = [l for l in rules if len(l) - 2 > max_rule_len]
    if long:
        problems.append(f"{len(long)} 条超 {max_rule_len} 字")
    # 分组下至少一条规则
    cur, empty = None, []
    for l in lines + ["# "]:
        if l.startswith("# ") or l.startswith("## "):
            if cur is not None and cur[1] == 0:
                empty.append(cur[0])
            cur = (l, 0) if l.startswith("## ") else None
        elif cur is not None and l.startswith("- "):
            cur = (cur[0], cur[1] + 1)
    if empty:
        problems.append("空分组:" + "/".join(e[3:] for e in empty))
    dead = [w for w in dead_words if w in text]
    if dead:
        problems.append("死概念:" + "/".join(dead))
    return {"rules": len(rules), "groups": len(groups), "problems": problems}


def check_dir(summaries: Path, expected: list[str] | None, max_rule_len: int,
              dead_words: list[str], exempt: set[str]) -> dict:
    if expected is None:
        expected = sorted(str(p.relative_to(summaries)).replace("\\", "/") for p in summaries.rglob("*.md"))
    report, missing = [], []
    for rel in expected:
        p = summaries / rel
        if not p.is_file():
            missing.append(rel)
            continue
        r = check_text(read_text(p), max_rule_len, [] if rel in exempt else dead_words)
        r["file"] = rel
        report.append(r)
    ok = not missing and all(not r["problems"] for r in report)
    return {"ok": ok, "missing": missing, "report": report}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summaries", required=True, help="摘要目录")
    ap.add_argument("--manifest", help="清单 JSON（docs[].file）")
    ap.add_argument("--manifest-key", default="docs")
    ap.add_argument("--dead-words", help="死概念词表，一行一个")
    ap.add_argument("--max-rule-len", type=int, default=60)
    ap.add_argument("--exempt", nargs="*", default=[], help="不查死概念的摘要（相对路径）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    a = ap.parse_args(argv)
    summaries = Path(a.summaries)
    if not summaries.is_dir():
        print(f"摘要目录不存在：{summaries}")
        return 1
    result = check_dir(summaries, manifest_files(Path(a.manifest) if a.manifest else None, a.manifest_key),
                       a.max_rule_len, load_dead_words(Path(a.dead_words) if a.dead_words else None), set(a.exempt))
    if a.json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
    else:
        print(f"摘要 {len(result['report'])} 份；缺 {len(result['missing'])}")
        for f in result["missing"]:
            print("  缺:", f)
        for r in result["report"]:
            flag = ("   ⚠ " + "；".join(r["problems"])) if r["problems"] else ""
            print(f"  {r['rules']:3d} 条 {r['groups']:2d} 组  {r['file']}{flag}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
