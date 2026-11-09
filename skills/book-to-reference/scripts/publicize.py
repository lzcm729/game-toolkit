"""把流程用语换成读者可用的文字，保留来源性质和限制。"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

from bookconf import Ruling, open_workdir


PIPELINE_TERMS = [
    ("复核划定的边界", "适用限制与推导说明"),
    ("BOOK_OVERVIEW 批判节", "编者评注，非原书"),
    ("BOOK_OVERVIEW 第 4 节", "编者评注，非原书"),
    ("BOOK_OVERVIEW", "编者评注"),
    ("（批判节）", "（编者评注，非原书）"),
    ("批判节「", "编者评注「"), ("批判节：", "编者评注："),
    ("批判节认为", "编者评注认为"), ("批判节", "编者评注"),
    ("V2 未过", "原书没给可执行的步骤"),
    ("但这个单元复核未通过（needs_review）：", "但原书依据不足："),
    ("与本分支不一致，该单元待核查，只列在", "与本分支不一致、依据不足，只列在"),
    ("。单元复核据「", "。本卡据「"),
    ("这是复核者的判断", "这是整理时的判断"),
    ("needs_review", "依据不足"),
    ("作者总纲（参考单元）", "作者总纲（只作参考）"),
    ("（参考单元）", "（只作参考）"), ("（参考单元，p.", "（只作参考，p."),
    ("（任务表已注明）", ""), ("，进参考区", "，只作参考"),
    ("按方法论先转待核", "所以不写成步骤"),
    ("单元承诺的", "这条承诺的"),
    ("本单元作 B 段边界和交叉引用，不单独成卡", "这条写进相关卡的边界（B 段）和交叉引用，不单独成卡"),
    ("本章其他单元承接", "本章其他卡承接"), ("别的单元里", "别的卡里"),
    ("演练只得出", "照着做一遍只得出"), ("演练只得到", "照着做一遍只得到"),
    ("演练只能得出", "照着做一遍只能得出"),
    ("缺失，演练做不完", "缺失，无法据此写成完整步骤"),
    ("待核单元：", "依据不足的内容："),
]
RESIDUE_PATTERNS = [
    "单元", "复核", "待核查", "参考单元", "提取器", "任务表", "overview", "批判节",
    r"u\d\d-\d\d", r"p\d-\d\d", r"g-\d+", r"t\d\d-\d\d",
    "补读", r"(?:本次|此次|本轮|最终|按计划|待|准备|完成|进入)交付", r"交付(?:物|清单|检查|目录|阶段|流程|结果)",
]


def _dedupe(text: str) -> str:
    def one_list(match):
        return "、".join(dict.fromkeys(re.findall(r"`[^`]+`", match.group(0))))
    text = re.sub(r"(`[^`]+`) 至 \1", r"\1", text)
    return re.sub(r"`[^`]+`(?:、`[^`]+`)+", one_list, text)


def apply(text: str, rulings: list[Ruling], scope: str) -> str:
    out = []
    for line in text.split("\n"):
        if line.startswith(">"):
            out.append(line)
            continue
        for rule in rulings:
            if rule.scope in (scope, "all"):
                line = line.replace(rule.find, rule.replace)
        if line.startswith("#"):
            line = re.sub(r"（u\d\d-\d\d[^）]*）", "", line).rstrip()
        line = re.sub(r"（?复核 ?R[A-Za-z0-9_-]+：", "", line)
        for before, after in PIPELINE_TERMS:
            # 旧 notes 的“编者评注”已说明来源；卡片的括注另明确“非原书”。
            if scope == "notes" and before == "（批判节）":
                continue
            line = line.replace(before, after)
        line = re.sub(r"（(?:单元 )?u\d\d-\d\d）", "", line)
        out.append(_dedupe(line))
    return "\n".join(out)


def scan(text: str, allow: list[str]) -> list[tuple[int, str]]:
    problems = []
    for number, line in enumerate(text.splitlines(), 1):
        if number == 1 and line.startswith("<!--"):
            continue
        remaining = line
        for phrase in sorted(allow, key=lambda value: (-len(value), value)):
            if phrase:
                remaining = remaining.replace(phrase, "")
        if any(re.search(pattern, remaining, re.I) for pattern in RESIDUE_PATTERNS):
            problems.append((number, line))
    return problems


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("scan")
    check.add_argument("workdir", type=Path)
    check.add_argument("files", nargs="+", type=Path)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = open_workdir(args.workdir)
        bad = False
        for path in args.files:
            path = args.workdir / path
            for line, text in scan(path.read_text(encoding="utf-8"), cfg.residue_allow):
                print(f"{path.as_posix()}:{line}: {text}")
                bad = True
        return 1 if bad else 0
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
