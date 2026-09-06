#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 validations.md 自带的 Test Cases 回归测试每条 regex 规则。

改过 references/validations.md 里的任何 Pattern 之后必须跑一遍：
    python scripts/check_validations.py
退出码 0 = 全部规则与其用例一致；1 = 有漏报、误报或字段缺失。

两个踩过的坑，改这个脚本时别踩回去：

1. 规则块的标题带缩进（`  #### **Should Match**`），lookahead 必须容忍前导空白。
   不容忍会把 Should Not Match 的用例并进 Should Match 组，得到一份看起来
   「错得很厉害」但其实是解析错误的报告。
2. 字段缺失不能静默 continue。否则编辑时删坏 Id / Type / Pattern，
   脚本照样给一份绿色报告。
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

STOP = r"(?=\n\s*#{3,4} |\n## |\Z)"


def _field(block: str, name: str) -> str | None:
    m = re.search(r"\s*### \*\*%s\*\*\n(.*?)%s" % (name, STOP), block, re.S)
    return m.group(1).strip() if m else None


def _cases(block: str, which: str) -> list[str]:
    m = re.search(r"\s*#### \*\*%s\*\*\n(.*?)%s" % (re.escape(which), STOP), block, re.S)
    if not m:
        return []
    return [l.strip()[2:].strip() for l in m.group(1).split("\n") if l.strip().startswith("- ")]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    path = Path(argv[0]) if argv else Path(__file__).resolve().parent.parent / "references" / "validations.md"
    text = io.open(path, encoding="utf-8", errors="replace").read().replace("\r\n", "\n")

    rules = cases = bad = covered = 0
    uncovered: list[str] = []
    others: list[tuple[str, str]] = []

    for block in re.split(r"\n## ", text)[1:]:
        title = block.split("\n")[0].strip()
        rid = _field(block, "Id")
        rtype = _field(block, "Type")
        pattern = _field(block, "Pattern")

        if rid is None or rtype is None:
            print(f"  字段缺失  {title}: Id={rid!r} Type={rtype!r}")
            bad += 1
            continue
        if rtype != "regex":
            others.append((rid, rtype))
            continue
        if not pattern:
            print(f"  字段缺失  {rid}: Type=regex 但没有 Pattern")
            bad += 1
            continue

        rules += 1
        matches, non_matches = _cases(block, "Should Match"), _cases(block, "Should Not Match")
        if matches or non_matches:
            covered += 1
        else:
            uncovered.append(rid)

        try:
            rx = re.compile(pattern)
        except re.error as e:
            print(f"  编译失败  {rid}: {e}")
            bad += 1
            continue

        for s in matches:
            cases += 1
            if not rx.search(s):
                print(f"  漏报  {rid}: {s!r}")
                bad += 1
        for s in non_matches:
            cases += 1
            hit = rx.search(s)
            if hit:
                print(f"  误报  {rid}: {s!r}  → 命中 {hit.group(0)!r}")
                bad += 1

    print(f"\n{rules} 条 regex 规则（{covered} 条有用例覆盖）, {cases} 个用例, {bad} 个不符")
    if others:
        kinds = sorted({k for _, k in others})
        print(f"  另有 {len(others)} 条非 regex 规则（{', '.join(kinds)}），不做正则回归")
    if uncovered:
        print(f"  无用例、改动时没有回归保护: {', '.join(uncovered)}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
