#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 validations.md 自带的 Test Cases 回归测试每条 regex 规则。

改过 references/validations.md 里的任何 Pattern 之后必须跑一遍：
    python scripts/check_validations.py
退出码 0 = 全部规则与其用例一致；1 = 有漏报或误报。

规则块的标题带缩进（`  #### **Should Match**`），所以 lookahead 要容忍前导空白 ——
这一点踩过坑：不容忍缩进会把 Should Not Match 的用例并进 Should Match 组，
得到一份看起来「错得很厉害」但其实是解析错误的报告。
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

    rules = cases = bad = 0
    for block in re.split(r"\n## ", text)[1:]:
        rid = _field(block, "Id") or block.split("\n")[0].strip()
        if _field(block, "Type") != "regex":
            continue
        pattern = _field(block, "Pattern")
        if not pattern:
            continue
        rules += 1
        try:
            rx = re.compile(pattern)
        except re.error as e:
            print(f"  编译失败  {rid}: {e}")
            bad += 1
            continue
        for s in _cases(block, "Should Match"):
            cases += 1
            if not rx.search(s):
                print(f"  漏报  {rid}: {s!r}")
                bad += 1
        for s in _cases(block, "Should Not Match"):
            cases += 1
            hit = rx.search(s)
            if hit:
                print(f"  误报  {rid}: {s!r}  → 命中 {hit.group(0)!r}")
                bad += 1

    print(f"\n{rules} 条 regex 规则, {cases} 个用例, {bad} 个不符")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
