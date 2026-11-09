"""机械核对摘句、步骤页码和卡片计划；通过不代表原文支持每一步。"""
from __future__ import annotations

import argparse
import bisect
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Literal

import yaml

from bookconf import open_workdir, resolve
from page_labels import MARKER, cited_pages, page_value


SLACK = 0
MARK = re.compile(r"p\.\s*(?:fm-)?\d|约定|原书未说明|由设计者判断|设计者判断|原图缺失|作者的经验估计|本卡|合成演练|交还设计者|由团队")
PLAN_ROW = re.compile(r"^\| (\d+) \| ([a-z0-9-]+) \|(?:[^|]*\|){2}([^|]*)\|")
UNIT = r"u\d{2}-\d{2}"


@dataclass
class QuoteResult:
    card_line: int
    pages_claimed: frozenset[int | str]
    found_on: list[int | str]
    status: str


@dataclass
class StepResult:
    line: int
    text: str
    ok: bool


def pages_of(attribution: str) -> frozenset[int | str]:
    return cited_pages(attribution)


def _norm(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[—–-]", " ", text)
    text = re.sub(r"\*\*|\[Callout\]|^>\s?", " ", text, flags=re.M)
    text = re.sub(r"[^a-z0-9' ]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def quote_pages(source_md: str, card_md: str) -> list[QuoteResult]:
    parts = MARKER.split(source_md)
    starts = [0]
    pages = [0]
    buffer = [_norm(parts[0]) + " "]
    position = len(buffer[0])
    for index in range(1, len(parts), 2):
        starts.append(position)
        pages.append(page_value(parts[index]))
        text = _norm(parts[index + 1]) + " "
        buffer.append(text)
        position += len(text)
    source = "".join(buffer)
    quotes = []
    section = re.search(r"^## R\b.*?(?=^## [A-Z]\b|\Z)", card_md, re.M | re.S)
    if not section:
        return [QuoteResult(0, frozenset(), [], "EMPTY: 缺 R 段")]
    lines = section.group(0).splitlines()
    base_line = card_md.count("\n", 0, section.start())
    index = 0
    while index < len(lines):
        if lines[index].startswith(">"):
            end = index
            while end < len(lines) and lines[end].startswith(">"):
                end += 1
            block = lines[index:end]
            pending = []
            waiting = []
            pending_line = 0

            def flush_quote():
                if pending:
                    waiting.append((" ".join(pending), pending_line))
                    pending.clear()

            def attribute(text):
                allowed = pages_of(text)
                quotes.extend((quote, allowed, line) for quote, line in waiting)
                waiting.clear()

            for offset, line in enumerate(block):
                body = line.lstrip("> ").strip()
                if body.startswith(("—", "-- ")):
                    flush_quote()
                    attribute(body)
                    continue
                if body.startswith(("译：", "译:")):
                    flush_quote()
                    continue
                if not body:
                    flush_quote()
                    continue
                if not pending:
                    pending_line = base_line + index + offset + 1
                pending.append(body)
            flush_quote()
            attribute("")
            index = end
            continue
        index += 1

    results = []
    for quote, allowed, line in quotes:
        manual = re.search(r"<!-- quote-manual:\s*(\S.*?)\s*-->", quote)
        quote = re.sub(r"<!-- quote-manual:.*?-->", "", quote).strip()
        if not any(char.isalpha() for char in quote):
            results.append(QuoteResult(line, allowed, [], "EMPTY: 人工标记不是摘句"))
            continue
        unsupported = (len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)*", quote)) < 5
                       or any(character.isalpha() and ord(character) > 127 for character in quote))
        if not allowed or unsupported:
            status = "NOPAGE" if not allowed else "MANUAL" if manual else "UNSUPPORTED: 非英文或少于五词，须人工核对标记"
            results.append(QuoteResult(line, allowed, [], status))
            continue
        segments = [_norm(part) for part in re.split(r"…|\.\.\.", quote) if _norm(part)]
        status = "OK" if allowed else "NOPAGE"
        found = set()
        expanded = allowed
        for segment in segments:
            hits = []
            offset = source.find(segment)
            while offset >= 0:
                first = bisect.bisect_right(starts, offset) - 1
                last = bisect.bisect_right(starts, offset + len(segment) - 1) - 1
                # 跨页摘句只认实际经过的页标记，不能把离散页补成连续范围。
                hit = set(pages[first:last + 1])
                hits.append(hit)
                found.update(hit)
                offset = source.find(segment, offset + 1)
            if not hits:
                status = "MISS"
            elif allowed and not any(hit & expanded for hit in hits):
                status = "OFFPAGE"
        results.append(QuoteResult(line, allowed, sorted(found, key=str), status))
    return results or [QuoteResult(base_line + 1, frozenset(), [], "EMPTY: R 段没有块摘句")]


def step_pages(card_md: str) -> list[StepResult]:
    section = re.search(r"^## E\b.*?(?=^## B\b|\Z)", card_md, flags=re.M | re.S)
    if not section:
        return [StepResult(0, "no E section", False)]
    results = []
    for match in re.finditer(r"^\s+\d+\.\s+(?P<text>.+)$", section.group(0), flags=re.M):
        text = match.group("text")
        line = card_md.count("\n", 0, section.start() + match.start("text")) + 1
        results.append(StepResult(line, text, bool(MARK.search(text))))
    return results


def plan_problems(cfg, workdir: Path) -> list[str]:
    problems = []
    rows = {}
    for line in resolve(cfg, workdir, "card_plan").read_text(encoding="utf-8").splitlines():
        match = PLAN_ROW.match(line)
        if match:
            slug = match.group(2)
            if slug in rows:
                problems.append(f"duplicate plan slug: {slug}")
            rows[slug] = re.findall(UNIT, match.group(3).split("（")[0])
    if not rows:
        problems.append("plan has no card rows")
    assigned = Counter(uid for units in rows.values() for uid in units)
    decisions = {}
    for path in sorted(resolve(cfg, workdir, "verify_out").glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        for unit in data["units"]:
            uid = unit["unit_id"]
            if uid in decisions:
                problems.append(f"duplicate unit id: {uid}")
            decisions[uid] = unit["decision"]
    verified = {uid for uid, decision in decisions.items() if decision == "verified"}
    for uid in sorted(verified - set(assigned)):
        problems.append(f"verified but unassigned: {uid}")
    for uid, count in sorted(assigned.items()):
        if count != 1:
            problems.append(f"unit assigned {count} times: {uid}")
        if uid not in verified:
            problems.append(f"assigned but not verified: {uid} ({decisions.get(uid)})")
    cards = resolve(cfg, workdir, "cards")
    meta_dir = resolve(cfg, workdir, "meta")
    for slug, units in rows.items():
        card = cards / f"{slug}.md"
        meta = meta_dir / f"{slug}.yaml"
        if not card.is_file() or not meta.is_file():
            problems.append(f"{slug}: missing card or meta")
            continue
        data = yaml.safe_load(meta.read_text(encoding="utf-8"))
        text = card.read_text(encoding="utf-8")
        if sorted(data.get("units") or []) != sorted(units):
            problems.append(f"{slug}: meta units {data.get('units')} != plan {units}")
        header = text.splitlines()[0] if text else ""
        if sorted(re.findall(UNIT, header)) != sorted(units):
            problems.append(f"{slug}: card header units != plan {units}")
        for uid in units:
            if not re.search(rf"^### 分支 \d+[^\n]*{re.escape(uid)}", text, flags=re.M):
                problems.append(f"{slug}: no branch heading for {uid}")
        refs = set(re.findall(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`", text)) - {slug}
        unknown = sorted(refs - set(rows))
        if unknown:
            problems.append(f"{slug}: unknown backticked refs {unknown}")
    extra = sorted(path.stem for path in cards.glob("*.md") if path.stem not in rows)
    if extra:
        problems.append(f"extra card files: {extra}")
    return problems


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workdir", type=Path)
    parser.add_argument("--only", choices=["quotes", "steps", "plan"])
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    bad = False
    try:
        cfg = open_workdir(args.workdir)
        cards = sorted(resolve(cfg, args.workdir, "cards").glob("*.md"))
        if args.only in (None, "quotes", "steps") and not cards:
            print("no card files", file=sys.stderr)
            bad = True
        if args.only in (None, "quotes"):
            source = resolve(cfg, args.workdir, "source").read_text(encoding="utf-8")
            results = []
            for path in cards:
                quotes = quote_pages(source, path.read_text(encoding="utf-8"))
                results.extend(quotes)
                for quote in quotes:
                    if quote.status not in ("OK", "MANUAL"):
                        print(f"{path.name}:{quote.card_line}: {quote.status}; cited={sorted(quote.pages_claimed, key=str)}; found={quote.found_on}")
            good = sum(quote.status in ("OK", "MANUAL") for quote in results)
            manual_count = sum(quote.status == "MANUAL" for quote in results)
            print(f"quotes {good}/{len(results)} accepted; manual={manual_count}")
            bad |= good != len(results)
        if args.only in (None, "steps"):
            results = []
            for path in cards:
                steps = step_pages(path.read_text(encoding="utf-8"))
                results.extend(steps)
                for step in steps:
                    if not step.ok:
                        print(f"{path.name}:{step.line}: {step.text[:100]}")
            good = sum(step.ok for step in results)
            total = sum(step.line > 0 for step in results)
            print(f"steps {good}/{total} with page or explicit non-book mark")
            bad |= any(not step.ok for step in results)
        if args.only in (None, "plan"):
            problems = plan_problems(cfg, args.workdir)
            for problem in problems:
                print(problem)
            print(f"plan problems: {len(problems)}")
            bad |= bool(problems)
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(exc, file=sys.stderr)
        bad = True
    print("页码在场不等于那一页支持这一步")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
