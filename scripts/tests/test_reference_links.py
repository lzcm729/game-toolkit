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


def infer_book_prefixes(entry_text):
    """两份不同的入口直链才成一家，避免把 Rouse 的单个无前缀文件当书姓。"""
    families = {}
    links = re.findall(r'\]\(\s*references/([a-z0-9]+-[a-z0-9-]+\.md)(?:#[^\s)]*)?(?:\s+"[^"]*")?\s*\)', entry_text)
    for name in links:
        prefix = name.split("-", 1)[0]
        families.setdefault(prefix, set()).add(name)
    return {prefix for prefix, names in families.items() if len(names) >= 2}


PREFIXES = infer_book_prefixes((REFS.parent / "SKILL.md").read_text(encoding="utf-8"))
# a reference context: a backtick span, a markdown link target, or an opening backtick that never closes
# on its line (the generator's cut names lost their closing backtick along with ".md")
CONTEXT = re.compile(r"`([^`\n]+)`|\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)|`([^`\n]+)$", re.M)  # a link may carry a title
SOURCES = sorted({*ROOT.glob("agents/*.md"), *ROOT.glob("skills/*/SKILL.md"), *ROOT.glob("skills/*/references/*.md")})


def ids(p):
    return p.relative_to(ROOT).as_posix()


def problems(text, names=None, prefixes=None):
    names = NAMES if names is None else names
    prefixes = PREFIXES if prefixes is None else prefixes
    prefix = "(?:" + "|".join(re.escape(name) for name in sorted(prefixes)) + ")-" if prefixes else r"(?!)"
    full = re.compile(rf"(?<![\w-])({prefix}[a-z0-9-]+\.md)")
    token = re.compile(rf"(?<![\w-])({prefix}[^\s`'\"()\[\]<>{{}}*，。、；：]*)")
    missing = {n for n in full.findall(text) if n not in names}
    cut = set()
    for m in CONTEXT.finditer(text):
        span = m.group(1) or m.group(2) or m.group(3)
        if re.search(r"[<>{}*]", span):  # a pattern such as `sylvester-<slug>.md`, not a reference
            continue
        for tok in token.findall(span):
            tok = tok.split("#")[0].rstrip(".,;:")  # a link may point at a heading: file.md#anchor
            if tok.endswith(".md"):
                if tok not in names:
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
    ("[卡](references/sylvester-balance-target.md#b-边界-boundary)", set(), set()),  # anchor on a valid file
    ('[卡](references/sylvester-… "标题")', set(), {"sylvester-…"}),  # cut target behind a link title
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


@pytest.mark.parametrize("text, missing, cut", [
    ("见 `aurora-missing.md`", {"aurora-missing.md"}, set()),
    ("→ `aurora-second…`", set(), {"aurora-second…"}),
    ("[读卡](references/aurora-third…)", set(), {"aurora-third…"}),
])
def test_new_book_prefix_is_checked(text, missing, cut):
    names = NAMES | {"aurora-first.md", "aurora-second.md", "aurora-third.md"}
    entry = "\n".join(f"[卡](references/aurora-{slug}.md)" for slug in ("first", "second", "third"))
    prefixes = infer_book_prefixes(entry)
    assert prefixes == {"aurora"}
    assert problems(text, names=names, prefixes=prefixes) == (missing, cut)


def test_prefix_inference_ignores_unprefixed_and_skill_links():
    entry = "\n".join([
        "[玩家](references/player-psychology.md)",
        "[重复](references/player-psychology.md)",
        "[设计](references/design-principles.md)",
        "[玩法](references/gameplay-elements.md)",
        "[技能](../design-discuss/SKILL.md)",
        "[另一个锚点](../design-discuss/SKILL.md#usage)",
    ])
    assert infer_book_prefixes(entry) == set()


def test_new_book_cut_entry_still_infers_prefix():
    entry = "\n".join([
        "[一](references/aurora-first.md)", "[二](references/aurora-second.md)",
        "[三](references/aurora-thir…)",
    ])
    prefixes = infer_book_prefixes(entry)
    assert prefixes == {"aurora"}
    assert problems(entry, names={"aurora-first.md", "aurora-second.md"}, prefixes=prefixes) == (set(), {"aurora-thir…"})
