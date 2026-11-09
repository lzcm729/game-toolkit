"""入口的链接、路由边界和停止条件是交接契约，不靠人工记住。"""
from pathlib import Path
import re
from urllib.parse import unquote

import yaml

from test_briefs import check_commands


SKILL = Path(__file__).resolve().parents[1]


def skill_text():
    return (SKILL / "SKILL.md").read_text(encoding="utf-8")


def test_links_resolve():
    files = [SKILL / "SKILL.md", *sorted((SKILL / "references").rglob("*.md"))]
    brief_links = set()
    for path in files:
        for target in re.findall(r"\]\(([^)\s]+)\)", path.read_text(encoding="utf-8")):
            if re.match(r"[a-z]+:", target):
                continue
            relative = unquote(target.split("#")[0])
            assert (path.parent / relative).exists(), (path, target)
            if path == SKILL / "SKILL.md" and "references/briefs/" in relative:
                brief_links.add(Path(relative).name)
    assert brief_links == {p.name for p in (SKILL / "references/briefs").glob("*.md")}
    assert not (SKILL / "references/template.md").exists()


def test_description_routes_narrowly():
    meta = yaml.safe_load(skill_text().split("---", 2)[1])
    description = meta["description"]
    assert meta["name"] == "book-to-reference"
    assert "本插件源码" in description and "game-design-theory" in description
    assert "不触发" in description
    for exclusion in ("普通读书摘要", "个人笔记", "其他 skill"):
        assert exclusion in description
    assert "导入这本书" not in description
    assert len(description) <= 1024


def test_every_stage_has_check_and_stop():
    rows = [line for line in skill_text().splitlines() if line.startswith("| ")]
    header = next((line for line in rows if "| 检查 |" in line and "| 不过就停 |" in line), None)
    assert header, "需要完整流程表"
    columns = [cell.strip() for cell in header.strip("|").split("|")]
    stages = rows[rows.index(header) + 1:]
    assert len(stages) >= 10
    for line in stages:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == len(columns), line
        for column in ("检查", "不过就停"):
            assert cells[columns.index(column)] not in ("", "—", "-"), line


def test_skill_commands_exist():
    assert check_commands(skill_text())
