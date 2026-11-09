"""从已采用的卡、单元和配置生成发布文件；先检查分组和目标，再写文件。"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
import re
import sys

import yaml

from bookconf import open_workdir, resolve
import publicize
from stage1 import read_tasks


USAGE = ("> **怎么用这张卡**：它是方法和书中依据的来源之一，不是回答的模板。回答围绕用户的处境：先给你自己的专业判断和具体做法，"
         "书外的实操（算一个例子、查数据、估成本）照常给；再用这张卡补方法、校正判断。不要按卡的分段复述这本书；卡里没写的，不等于不能答。"
         "书名和页码只在用户要出处时给。")


@dataclass
class IntegrateReport:
    written: list[Path]
    deleted: list[Path]
    residue: list[tuple[Path, int, str]]


def main_chapter(units: list[str]) -> str:
    chapters = [re.fullmatch(r"u(\d\d)-\d\d", uid).group(1) for uid in units]
    if not chapters:
        raise ValueError("card has no units")
    counts = Counter(chapters)
    return max(sorted(counts), key=lambda chapter: (counts[chapter], chapter != "00", -int(chapter)))


def safe_cut(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = limit - 1
    for match in re.finditer(r"`[^`]*`", text):
        if match.start() < cut < match.end():
            cut = match.end()
            break
    return text if cut >= len(text) else text[:cut].rstrip("，；、 ") + "…"


def _first_sentence(text, limit=160):
    text = " ".join(str(text or "").split())
    for stop in ("。", "；"):
        index = text.find(stop)
        if 0 < index < limit:
            return text[:index + 1]
    if len(text) <= limit:
        return text
    cut = limit
    for match in re.finditer(r"`[^`]*`", text):
        if match.start() < cut < match.end():
            cut = match.end()
            break
    return text[:cut] + ("…" if cut < len(text) else "")


def _notes(cfg, workdir, unit_card):
    units = {}
    for path in sorted(resolve(cfg, workdir, "verify_out").glob("*.yaml")):
        for unit in yaml.safe_load(path.read_text(encoding="utf-8"))["units"]:
            units[unit["unit_id"]] = unit
    task_units = defaultdict(set)
    for unit in units.values():
        for task in unit.get("task_ids") or []:
            task_units[task].add(unit["unit_id"])

    def public(text):
        return publicize.apply(str(text or ""), cfg.rulings, "notes")

    def readable(text):
        def substitute(match):
            slug = unit_card.get(match.group(0))
            return f"`{cfg.prefix}{slug}.md`" if slug else "另一条只作参考的观点"
        return re.sub(r"u\d\d-\d\d", substitute, str(text or ""))

    def chapter(unit):
        location = (unit.get("source_evidence") or [{}])[0].get("location", "")
        name = location.split(" / ")[0] if location else unit["unit_id"][:3]
        name = re.sub(r"[,，]?\s*p\.\s*[\d–-]+.*$", "", name)
        return re.sub(r"\s*(（Callout）|Callout)$", "", name).strip()

    def chapter_order(name):
        match = re.match(r"Ch(\d+)", name)
        return (0, int(match.group(1))) if match else (-1 if "Intro" in name or "Part" in name else 1, 0)

    author = cfg.mask_names.authors[0]
    title = cfg.mask_names.titles[0]
    lines = [f"# {author}《{title}》：术语与只作参考的观点", "",
             "> 能照着做的方法在能力卡里（见 SKILL.md 的选卡表）。这里放两类卡外的内容：",
             "> 术语的意思，以及原书讲了、但没给出能照着执行的步骤的观点。用它们时说明是作者观点，不当规则。", "", "## 术语", ""]
    glossary = resolve(cfg, workdir, "glossary").read_text(encoding="utf-8")
    terms = []
    for block in re.split(r"(?m)^(?=- id: )", glossary):
        if not block.startswith("- id: "):
            continue
        keep = [block.splitlines()[0]]
        for line in block.splitlines()[1:]:
            if line and not line.startswith(" "):
                break
            keep.append(line)
        item = yaml.safe_load("\n".join(keep))
        terms.append(item[0] if isinstance(item, list) else item)
    used = {term for unit in units.values() if unit["decision"] != "rejected"
            for term in ((unit.get("supports") or {}).get("terms") or [])}
    names = {term.get("id"): term.get("term", term.get("title", "")) for term in terms}
    for term in terms:
        if term.get("id") not in used:
            continue
        parts = [part.strip().strip("；;，,、 ") for part in str(term.get("key_distinction", "")).splitlines()
                 if part.strip().strip("；;，,、 ")]
        definition = ""
        for part in parts:
            definition += part if not definition or definition.endswith(("：", ":")) else "；" + part
        definition = re.sub(r"g-\d+", lambda match: f"「{names.get(match.group(0), match.group(0))}」", definition)
        definition = re.sub(r"[（(]?(?:见|对应)?\s*t\d\d-\d\d[）)]?", "", definition)
        pages = re.findall(r"p\.\s*[\d–-]+", str(term.get("source_chapter", "")))
        lines.append(f"- **{names[term['id']]}**（{', '.join(pages) or '页码见原书'}）：{public(definition)}")
    lines.extend(["", "## 只作参考的作者观点", "",
                  "每条：要点；为什么不写成能力卡（「只作参考」= 原书没给可执行的步骤或判据，「依据不足」= 原书两处说法冲突或缺判据）；页码；相关的卡。", ""])
    by_chapter = defaultdict(list)
    for unit in units.values():
        if unit["decision"] in ("reference", "needs_review"):
            by_chapter[chapter(unit)].append(unit)
    for ch in sorted(by_chapter, key=chapter_order):
        lines.extend([f"### {ch}", ""])
        for unit in sorted(by_chapter[ch], key=lambda item: item["unit_id"]):
            related = sorted({unit_card[uid] for task in unit.get("task_ids") or []
                              for uid in task_units[task] if uid in unit_card})[:4]
            cards = "、".join(f"`{cfg.prefix}{slug}.md`" for slug in related) or "—"
            recheck = unit.get("recheck") or {}
            if recheck.get("reason") and recheck.get("decision_after") != "verified":
                reason = recheck["reason"]
            else:
                reason = re.sub(r"^\s*三关都过[。，；]?", "", str(unit.get("decision_reason") or ""))
            reason = public(readable(reason))
            pages = []
            for evidence in unit.get("source_evidence") or []:
                for page in re.findall(r"p\.\s*[\d–-]+", evidence.get("location", "")):
                    if page not in pages:
                        pages.append(page)
            status = "依据不足" if unit["decision"] == "needs_review" else "只作参考"
            line = (f"- **{unit['title']}**（{status}，{', '.join(pages)}）：{_first_sentence(public(readable(unit.get('one_liner'))))}"
                    f" 原因：{_first_sentence(reason, 140)} 相关：{cards}")
            lines.append(public(line))
        lines.append("")
    return "\n".join(lines)


def _between(text, start, end, replacement):
    first = text.index(start)
    last = text.index(end, first + len(start))
    if start.startswith("<!--"):
        replacement = start + "\n" + replacement
    return text[:first] + replacement + text[last:]


def run(workdir: Path) -> IntegrateReport:
    workdir = Path(workdir).resolve()
    cfg = open_workdir(workdir)
    read_tasks(resolve(cfg, workdir, "overview").read_text(encoding="utf-8"))
    if not re.fullmatch(r"[A-Za-z0-9_-]+", cfg.prefix):
        raise ValueError("prefix 必须是文件名前缀")
    if not cfg.mask_names.authors or not cfg.mask_names.titles:
        raise ValueError("mask_names 需要本书作者和书名，首项用于 notes 标题")
    gdt = cfg.target_root / "skills/game-design-theory"
    refs = gdt / "references"

    def destination(name):
        path = refs / name
        if not path.resolve().is_relative_to(refs.resolve()) or Path(name).name != name:
            raise ValueError(f"交付文件名逃出 references: {name}")
        if not path.resolve().is_relative_to(cfg.target_root):
            raise ValueError(f"交付路径逃出源码: {path}")
        return path

    plan = resolve(cfg, workdir, "card_plan").read_text(encoding="utf-8")
    rows = re.findall(r"^\| \d+ \| ([a-z0-9-]+) \|[^|]*\|[^|]*\| ([^|]+) \|", plan, re.M)
    slugs = [slug for slug, _ in rows]
    if not slugs or len(set(slugs)) != len(slugs):
        raise ValueError("卡片计划为空或 slug 重复")
    unit_card = {uid: slug for slug, cell in rows for uid in re.findall(r"u\d\d-\d\d", cell.split("（")[0])}
    known = set(slugs)

    def rewrite(text):
        return re.sub(r"`([a-z0-9-]+)`", lambda match: f"`{cfg.prefix}{match.group(1)}.md`" if match.group(1) in known else match.group(0), text)

    def public(text):
        return publicize.apply(text, cfg.rulings, "cards")

    generated = {}
    groups = {group: [] for group in cfg.entry_groups}
    chapter_group = {chapter: group for group, chapters in cfg.entry_groups.items() for chapter in chapters}
    unmapped = set()
    for slug in slugs:
        card = (resolve(cfg, workdir, "cards") / f"{slug}.md").read_text(encoding="utf-8")
        meta = yaml.safe_load((resolve(cfg, workdir, "meta") / f"{slug}.yaml").read_text(encoding="utf-8"))
        units = re.findall(r"u\d\d-\d\d", card.splitlines()[0])
        # 所有参与卡片的章号都必须有组，不能只检查占多数的章。
        unmapped.update(uid[1:3] for uid in units if uid[1:3] not in chapter_group)
        chapter = main_chapter(units)
        if chapter not in chapter_group:
            continue
        lines = rewrite(card).split("\n")
        if USAGE not in card:
            index = next(index for index, line in enumerate(lines) if line.startswith("# "))
            lines = lines[:index + 1] + ["", USAGE] + lines[index + 1:]
        generated[destination(f"{cfg.prefix}{slug}.md")] = public("\n".join(lines))
        neighbour = re.search(r"\*\*与相邻卡的区分[^*]*\*\*\s*\n((?:\s*- .*\n)+)", card)
        neighbour = neighbour.group(1).strip().splitlines()[0].lstrip("- ").strip() if neighbour else "—"
        neighbour = safe_cut(public(rewrite(neighbour)), 90).replace("|", "／")
        intents = "；".join(meta.get("intents", [])[:3]).replace("|", "／")
        groups[chapter_group[chapter]].append(f"| {intents} | [{cfg.prefix}{slug}.md](references/{cfg.prefix}{slug}.md) | {neighbour} |")
    if unmapped:
        raise ValueError(f"unmapped entry chapters: {sorted(unmapped)}")
    notes = _notes(cfg, workdir, unit_card)
    generated[destination(f"{cfg.prefix}notes.md")] = notes
    table = [cfg.skill_md.table_heading, "",
             f"{len(slugs)} 张能力卡，一张卡管一类任务，每个分支写清输入、步骤、输出、原书页码和边界。按下表「用户在问」找对口的卡；两张都像时看「和近邻怎么分」，两条路线都能完成任务就都可以用。",
             "**怎么用卡**：回答围绕用户的处境，先给你自己的专业判断和具体做法，书外的实操（算一个例子、查数据、估成本、排期）照常给；卡用来补方法、校正判断、提供依据，不是回答的模板。不要按卡的分段复述这本书，卡里没写的不等于不能答。书名、作者和页码只在用户问出处或需要核对时给。",
             f"术语和只作参考的作者观点（原书讲了、但没给出可照做步骤的）在 [{cfg.prefix}notes.md](references/{cfg.prefix}notes.md)。卡里标「原书未说明」的地方可以给你自己的建议，但要说明不出自本书。", ""]
    for group, entries in groups.items():
        if entries:
            table.extend([f"**{group}**", "", "| 用户在问 | 读这张卡 | 和近邻怎么分 |", "|---|---|---|", *entries, ""])
    skill_path = gdt / "SKILL.md"
    if not skill_path.resolve().is_relative_to(cfg.target_root):
        raise ValueError("SKILL.md 逃出交付源码")
    text = skill_path.read_text(encoding="utf-8")
    quick = (workdir / cfg.skill_md.quick_ref_file).read_text(encoding="utf-8")
    text = _between(text, cfg.skill_md.quick_ref_start, cfg.skill_md.quick_ref_end, quick)
    start = cfg.skill_md.table_start if cfg.skill_md.table_start in text else cfg.skill_md.table_heading
    text = _between(text, start, cfg.skill_md.table_end, "\n".join(table).rstrip() + "\n\n")
    anchor = cfg.skill_md.when_to_use_anchor.rstrip("\n") + "\n"
    extra = cfg.skill_md.when_to_use_line.rstrip("\n") + "\n"
    if anchor not in text:
        raise ValueError("when_to_use_anchor 未找到")
    if extra not in text:
        text = text.replace(anchor, anchor + extra, 1)
    if cfg.skill_md.description_file:
        description = " ".join((workdir / cfg.skill_md.description_file).read_text(encoding="utf-8").split())
        if len(description) > 1024:
            raise ValueError(f"description {len(description)} chars > 1024")
        first, frontmatter, body = text.split("---", 2)
        frontmatter, count = re.subn(r"description:[^\n]*\n(?:[ \t]+[^\n]*\n)*", "description: >\n  " + description + "\n", frontmatter, count=1)
        if count != 1:
            raise ValueError("description key not found")
        text = first + "---" + frontmatter + "---" + body
    generated[skill_path] = text
    old_paths = [destination(name) for name in cfg.old_files]
    if set(old_paths) & set(generated):
        raise ValueError("old_files 包含本次生成的文件")
    notes_path = resolve(cfg, workdir, "notes_out")
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    notes_path.write_text(notes, encoding="utf-8", newline="\n")
    refs.mkdir(parents=True, exist_ok=True)
    for path, content in generated.items():
        path.write_text(content, encoding="utf-8", newline="\n")
    deleted = []
    for path in old_paths:
        if path.exists():
            path.unlink()
            deleted.append(path)
    residue = [(path, line, content) for path in generated
               for line, content in publicize.scan(path.read_text(encoding="utf-8"), cfg.residue_allow)]
    return IntegrateReport(list(generated), deleted, residue)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workdir", type=Path)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run(args.workdir)
        print(f"written: {len(result.written)}; deleted: {len(result.deleted)}; residue: {len(result.residue)}")
        for path, line, text in result.residue:
            print(f"{path.as_posix()}:{line}: {text}")
        return 1 if result.residue else 0
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
