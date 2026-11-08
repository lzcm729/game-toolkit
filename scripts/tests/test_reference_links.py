"""Every mention of a game-design-theory reference file by name resolves to an existing file.

Agents, design-discuss and the cards themselves point at files under
skills/game-design-theory/references/ by file name (agents/framework.md, for one, names the cards
to read when designing decisions). When reference files are replaced or renamed -- Sylvester's
seven summaries became capability cards -- a stale name leaves that consumer pointing at nothing.
test_skill_files.py only checks the links inside SKILL.md files, so the agents, the other skills'
references/ and the template were not covered.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REFS = ROOT / "skills" / "game-design-theory" / "references"
NAMES = {p.name for p in REFS.glob("*.md")}
# the prefixed book families; Rouse's files have no prefix and are matched by the SKILL.md check
FAMILY = re.compile(r"(?<![\w-])((?:sylvester|schell|meadows)-[a-z0-9-]+\.md)\b")
SOURCES = sorted({*ROOT.glob("agents/*.md"), *ROOT.glob("skills/*/SKILL.md"), *ROOT.glob("skills/*/references/*.md")})


@pytest.mark.parametrize("src", SOURCES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_reference_mentions_resolve(src):
    text = src.read_text(encoding="utf-8")
    missing = sorted({m for m in FAMILY.findall(text) if m not in NAMES})
    assert not missing, f"{src.relative_to(ROOT).as_posix()} 指向不存在的参考文件：{missing}"


def test_sources_found():
    assert len(SOURCES) > 20 and len(NAMES) > 20
