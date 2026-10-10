# -*- coding: utf-8 -*-
"""skills/*/SKILL.md 本身的检查：frontmatter 能解析、name 和目录同名、description 不超长、引用的文件都在。

description 上限取 Agent Skills 规范的 1024 字符：Claude Code 放宽到 1536，但插件同时发给 Codex，按严的算。
引用检查只认指向插件里文件的相对路径：反引号里以 references/、scripts/、examples/ 开头的路径（一段里有几个都查），
以及 Markdown 链接。写成「layer-contracts 的 `scripts/project_env.py`」或「layer-contracts 的 [说明](…)」的，
只在那个 skill 里找，那个 skill 不存在也算错（skill 名都带连字符，「本 skill 的」不算写了归属）；
没写归属的，先在本 skill 里找，再按插件根找（`scripts/export_codex_agents.py` 这类）。
不支持：反引号里带空格的路径（和命令参数分不开）、链接目标里的括号、引用式链接，插件里都没有人这样写。
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SKILL_DIRS = sorted(p.parent for p in (REPO / "skills").glob("*/SKILL.md"))
DESC_LIMIT = 1024
TICK = re.compile(r"`([^`\n]+)`")
# 链接目标：(<带空格的路径>)、(路径 "标题")、(路径 '标题')、(路径)
LINK = re.compile(r"\]\(\s*(?:<([^>\n]+)>|([^)\s]+))(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
BUNDLED = re.compile(r"^(?:\.\./[\w.-]+/)?(?:references|scripts|examples)/")
OWNER = re.compile(r"`?([a-z0-9]+(?:-[a-z0-9]+)+)`?\s*的\s*$")  # skill 名：带连字符的小写词
PLACEHOLDER = set("<>*{}$~")


def _split(path: Path) -> "tuple[dict, str]":
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    assert m, "%s 没有 frontmatter（文件要以 --- 开头）" % path.relative_to(REPO)
    return yaml.safe_load(m.group(1)) or {}, text[m.end():]


def _owner(body: str, at: int) -> "str | None":
    m = OWNER.search(body[max(0, at - 40):at])
    return m.group(1) if m else None


def _references(body: str):
    """(写在哪个 skill 名下或 None, 路径)。路径去掉 #锚点。"""
    for m in TICK.finditer(body):
        for t in m.group(1).split():
            tok = t.removeprefix("./").split("#")[0]
            if BUNDLED.match(tok) and not PLACEHOLDER & set(tok):
                yield _owner(body, m.start()), tok
    for m in LINK.finditer(body):
        tok = unquote((m.group(1) or m.group(2)).split("#")[0]).removeprefix("./")  # 先切掉锚点再解码，%23 是字面的 #
        if tok and not re.match(r"[a-z]+:", tok) and not PLACEHOLDER & set(tok):
            yield _owner(body, body.rfind("[", 0, m.start() + 1)), tok


def test_every_skill_found():
    assert len(SKILL_DIRS) >= 10, SKILL_DIRS


def test_reference_parsing_rules():
    body = ("layer-contracts 的 `scripts/project_env.py check`；见 `references/a.md#一节` 和 `examples/b.md`；"
            "generate-assets 的 [字段](<examples/c d.md> \"标题\")；[说明](references/e%20f.md)；"
            "[单引号标题](references/i.md '标题')；[编码的井号](references/j%23k.md#节)；本 skill 的 `scripts/l.py`；"
            "命令 `python scripts/g.py scripts/h.py`；占位 `<本 skill>/scripts/x.py` 不查；外链 [x](https://a.b) 不查")
    assert list(_references(body)) == [
        ("layer-contracts", "scripts/project_env.py"), (None, "references/a.md"), (None, "examples/b.md"),
        (None, "scripts/l.py"), (None, "scripts/g.py"), (None, "scripts/h.py"),
        ("generate-assets", "examples/c d.md"), (None, "references/e f.md"),
        (None, "references/i.md"), (None, "references/j#k.md"),
    ]


@pytest.mark.parametrize("skill", SKILL_DIRS, ids=lambda p: p.name)
def test_frontmatter_parses_and_name_matches_directory(skill):
    meta, _ = _split(skill / "SKILL.md")
    assert meta.get("name") == skill.name, "name 要和目录名一样"
    assert isinstance(meta.get("description"), str) and meta["description"].strip(), "缺 description"


@pytest.mark.parametrize("skill", SKILL_DIRS, ids=lambda p: p.name)
def test_description_within_limit(skill):
    meta, _ = _split(skill / "SKILL.md")
    n = len(meta.get("description") or "")
    assert n <= DESC_LIMIT, "description %d 字符，超过 %d：先删和正文重复、不带触发词的部分" % (n, DESC_LIMIT)


@pytest.mark.parametrize("skill", SKILL_DIRS, ids=lambda p: p.name)
def test_referenced_files_exist(skill):
    _, body = _split(skill / "SKILL.md")
    missing = []
    for owner, rel in _references(body):
        named = REPO / "skills" / owner if owner else None
        bases = [named] if named else [skill, REPO]
        if not any((base / rel).exists() for base in bases):
            missing.append(rel if bases != [named] else "%s 的 %s" % (owner, rel))
    assert not missing, "SKILL.md 引用的文件不存在：%s" % "、".join(missing)
