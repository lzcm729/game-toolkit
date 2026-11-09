"""随包说明要能独立执行；命令按真实 argparse 验证，防止文档漂移。"""
import argparse
import importlib
from pathlib import Path
import re
import shlex

import pytest


SKILL = Path(__file__).resolve().parents[1]
BRIEFS = ("stage0-notes", "stage1-extract", "stage15-verify", "recheck",
          "card-writing", "propagation", "grouping", "consumers",
          "question-writer", "rubric-writer", "grader", "content-review")
FORMATS = ("card-format", "candidate-schema", "method")


def check_commands(text):
    found = []
    for match in re.finditer(r"\bpython\s+((?:scripts/)?[a-z0-9_]+\.py)([^\n`]*)", text):
        filename, arguments = match.groups()
        path = SKILL / "scripts" / Path(filename).name
        assert path.is_file(), filename
        parser = importlib.import_module(path.stem).build_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        try:
            parser.parse_args(shlex.split(arguments))
        except SystemExit as exc:
            pytest.fail(f"文档命令不被 argparse 接受: {match.group(0)} (exit {exc.code})")
        found.append(match.group(0))
    return found


def test_briefs_self_contained():
    for name in BRIEFS:
        assert (SKILL / "references/briefs" / (name + ".md")).is_file(), name
    for name in FORMATS:
        assert (SKILL / "references" / (name + ".md")).is_file(), name
    for path in sorted((SKILL / "references").rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for external in ("extractors/", "methodology/", "build_index.py", "cangjie.py"):
            assert external not in text, (path, external)


def test_brief_commands_exist():
    # 没有在任务书中举例的工具也必须暴露解析器，后续入口检查会复用它。
    for script in sorted((SKILL / "scripts").glob("*.py")):
        # 页标契约是两个 CLI 共用的库，不虚构一个不能执行任务的命令入口。
        if script.stem == "page_labels":
            continue
        assert isinstance(importlib.import_module(script.stem).build_parser(), argparse.ArgumentParser)
    found = []
    for path in sorted((SKILL / "references").rglob("*.md")):
        found.extend(check_commands(path.read_text(encoding="utf-8")))
    assert found


def test_mit_notice_present():
    for name in ("candidate-schema", "method"):
        text = (SKILL / "references" / (name + ".md")).read_text(encoding="utf-8")
        assert "cangjie-skill" in text
        assert "MIT License" in text and "Copyright (c) 2026" in text
        assert "Permission is hereby granted, free of charge" in text
        assert 'THE SOFTWARE IS PROVIDED "AS IS"' in text


@pytest.mark.parametrize("command", ["python stage1.py wrong work", "python reach.py pick work --unknown yes"])
def test_command_check_rejects_invalid_invocation(command):
    with pytest.raises(pytest.fail.Exception):
        check_commands(command)
