"""Every mention of a game-design-theory reference file by name resolves to an existing file.

Agents, design-discuss and the cards themselves point at files under
skills/game-design-theory/references/ by file name (agents/framework.md, for one, names the cards
to read when designing decisions). When reference files are replaced or renamed -- Sylvester's
seven summaries became capability cards -- a stale name leaves that consumer pointing at nothing.
test_skill_files.py only checks the links inside SKILL.md files, so the agents, the other skills'
references/ and the template were not covered.

Two failure shapes are checked: a full name that does not exist, and a reference that was cut
before ".md" (a generator once cut `sylvester-decision-rh…` mid-name in the selection table, which a
full-name check passes silently). Cut names are looked for only where a file is being referenced --
inside backticks or a link target -- so prose such as "the sylvester-skill cards" is not flagged.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
REFS = ROOT / "skills" / "game-design-theory" / "references"
NAMES = {p.name for p in REFS.glob("*.md")}
ALL_MD = {p.name for p in ROOT.rglob("*.md") if ".git" not in p.parts}
# the prefixed book families; Rouse's files have no prefix
PREFIX = r"(?:sylvester|schell|meadows)-"
FULL = re.compile(rf"(?<![\w-])({PREFIX}[a-z0-9-]+\.md)")
# a reference context: a backtick span, a markdown link target, or an opening backtick that never closes
# on its line (the generator's cut names lost their closing backtick along with ".md")
CONTEXT = re.compile(r"`([^`\n]+)`|\]\(([^)\s]+)\)|`([^`\n]+)$", re.M)
# inside a context, anything that starts like a family file name, up to whitespace or punctuation
TOKEN = re.compile(rf"(?<![\w-])({PREFIX}[^\s`'\"()\[\]<>{{}}*，。、；：]*)")
SOURCES = sorted({*ROOT.glob("agents/*.md"), *ROOT.glob("skills/*/SKILL.md"), *ROOT.glob("skills/*/references/*.md")})


def ids(p):
    return p.relative_to(ROOT).as_posix()


def problems(text):
    missing = {n for n in FULL.findall(text) if n not in NAMES}
    cut = set()
    for m in CONTEXT.finditer(text):
        span = m.group(1) or m.group(2) or m.group(3)
        if re.search(r"[<>{}*]", span):  # a pattern such as `sylvester-<slug>.md`, not a reference
            continue
        for tok in TOKEN.findall(span):
            tok = tok.rstrip(".,;:")
            if tok.endswith(".md"):
                if tok not in NAMES:
                    missing.add(tok)
            else:
                cut.add(tok)  # starts like a reference file name, never reaches ".md"
    return missing, cut


@pytest.mark.parametrize("src", SOURCES, ids=ids)
def test_reference_mentions_resolve(src):
    missing, cut = problems(src.read_text(encoding="utf-8"))
    assert not missing, f"{ids(src)} 指向不存在的参考文件：{sorted(missing)}"
    assert not cut, f"{ids(src)} 有被截断或缺 .md 的参考文件名：{sorted(cut)}"


@pytest.mark.parametrize("text, missing, cut", [
    ("见 `sylvester-balance-target.md`", set(), set()),
    ("[卡](references/sylvester-balance-target.md)", set(), set()),
    ("sylvester-skill 系列卡", set(), set()),  # prose, not a reference
    ("`sylvester-<slug>.md` 是命名规则", set(), set()),
    ("→ `sylvester-decision-rh…`", set(), {"sylvester-decision-rh…"}),
    ("→ `sylvester-…`", set(), {"sylvester-…"}),
    ("→ `sylvester-`", set(), {"sylvester-"}),
    ("| → `sylvester-overplanni… |", set(), {"sylvester-overplanni…"}),  # cut with its closing backtick
    ("见 sylvester-no-such-card.md", {"sylvester-no-such-card.md"}, set()),
    ("[卡](references/sylvester-no-such-card.md)", {"sylvester-no-such-card.md"}, set()),
])
def test_problem_shapes(text, missing, cut):
    assert problems(text) == (missing, cut)


# file names as agents write them: hyphens, underscores, capitals, with or without a path in front
AGENT_FILE = re.compile(r"(?<![A-Za-z0-9_.-])([A-Za-z0-9_][A-Za-z0-9_.-]*\.md)\b")


@pytest.mark.parametrize("src", sorted(ROOT.glob("agents/*.md")), ids=ids)
def test_agent_file_mentions_exist(src):
    """Agents also name Rouse's unprefixed files (player-psychology.md ...) and other skills' files."""
    names = set(AGENT_FILE.findall(src.read_text(encoding="utf-8")))
    missing = sorted(n for n in names if n not in ALL_MD)
    assert not missing, f"{ids(src)} 提到的文件在仓库里找不到：{missing}"


@pytest.mark.parametrize("text, found", [
    ("→ `sharp_edges.md`", {"sharp_edges.md"}),
    ("`references/player-psychology.md`", {"player-psychology.md"}),
    ("Read CLAUDE.md first", {"CLAUDE.md"}),
])
def test_agent_file_shapes(text, found):
    assert set(AGENT_FILE.findall(text)) == found


def test_sources_found():
    assert len(SOURCES) > 20 and len(NAMES) > 20
