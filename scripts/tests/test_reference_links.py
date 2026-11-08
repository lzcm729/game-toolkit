"""Every mention of a game-design-theory reference file by name resolves to an existing file.

Agents, design-discuss and the cards themselves point at files under
skills/game-design-theory/references/ by file name (agents/framework.md, for one, names the cards
to read when designing decisions). When reference files are replaced or renamed -- Sylvester's
seven summaries became capability cards -- a stale name leaves that consumer pointing at nothing.
test_skill_files.py only checks the links inside SKILL.md files, so the agents, the other skills'
references/ and the template were not covered.

Two failure shapes are checked: a full name that does not exist, and a name that starts like a
reference file but never ends in ".md" (a generator once cut `sylvester-decision-rh…` mid-name in the
selection table, which a full-name check passes silently).
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REFS = ROOT / "skills" / "game-design-theory" / "references"
NAMES = {p.name for p in REFS.glob("*.md")}
ALL_MD = {p.name for p in ROOT.rglob("*.md") if ".git" not in p.parts}
# the prefixed book families; Rouse's files have no prefix
FAMILY = re.compile(r"(?<![\w-])((?:sylvester|schell|meadows)-[a-z0-9-]+)(\.md)?")
SOURCES = sorted({*ROOT.glob("agents/*.md"), *ROOT.glob("skills/*/SKILL.md"), *ROOT.glob("skills/*/references/*.md")})


def ids(p):
    return p.relative_to(ROOT).as_posix()


@pytest.mark.parametrize("src", SOURCES, ids=ids)
def test_reference_mentions_resolve(src):
    text = src.read_text(encoding="utf-8")
    missing, cut = set(), set()
    for stem, ext in FAMILY.findall(text):
        if ext:
            if stem + ext not in NAMES:
                missing.add(stem + ext)
        elif any(n.startswith(stem) and n != stem + ".md" for n in NAMES) or stem + ".md" in NAMES:
            cut.add(stem)  # looks like the start of a reference file name but has no ".md"
    assert not missing, f"{ids(src)} 指向不存在的参考文件：{sorted(missing)}"
    assert not cut, f"{ids(src)} 有被截断或缺 .md 的参考文件名：{sorted(cut)}"


@pytest.mark.parametrize("src", sorted(ROOT.glob("agents/*.md")), ids=ids)
def test_agent_file_mentions_exist(src):
    """Agents also name Rouse's unprefixed files (player-psychology.md ...) and other skills' files."""
    names = set(re.findall(r"(?<![\w/.-])([a-z0-9][a-z0-9-]*\.md)\b", src.read_text(encoding="utf-8")))
    missing = sorted(n for n in names if n not in ALL_MD)
    assert not missing, f"{ids(src)} 提到的文件在仓库里找不到：{missing}"


def test_sources_found():
    assert len(SOURCES) > 20 and len(NAMES) > 20
