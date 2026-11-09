"""核对修复后的交接契约，避免说明继续引导出同一类错误。"""
from pathlib import Path

import integrate


def test_usage_and_host_contracts_have_one_definition():
    skill = Path(__file__).parent.parent
    docs = skill / "references"
    assert integrate.USAGE == (docs / "card-usage.md").read_text(encoding="utf-8").strip()
    assert "card-usage.md" in (docs / "card-format.md").read_text(encoding="utf-8")
    assert "qid<TAB>group<TAB>prompt" in (docs / "host.md").read_text(encoding="utf-8")


def test_host_precheck_does_not_group_before_task_table():
    root = Path(__file__).resolve().parents[3]
    skill = (root / "skills/book-to-reference/SKILL.md").read_text(encoding="utf-8")
    smoke = next(line for line in skill.splitlines() if line.startswith("| 前置宿主冒烟 |"))
    assert "不做 O/N 分组" in smoke
    assert skill.index("| 0 整书理解 |") < skill.index("| 0 后冻结分组 |") < skill.index("| 1 提取 |")
    assert "维护者向本插件源码的 game-design-theory" in (root / "README.md").read_text(encoding="utf-8")
