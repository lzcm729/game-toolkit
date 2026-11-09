"""公开包不能夹带维护者路径；只给路径规范化用的虚构夹具豁免盘符。"""
from pathlib import Path
import re

import pytest


REPO = Path(__file__).resolve().parents[3]
ROOTS = (REPO / "skills/book-to-reference", REPO / "evals/book-to-reference-cold-start")
WINDOWS_FIXTURE = "skills/book-to-reference/tests/fixtures/runs/windows-read.jsonl"
# 唯一豁免：虚构盘符用于证明 chain 能解析 Windows 的 Read 路径；其他私有标记仍查。
EXEMPTIONS = {WINDOWS_FIXTURE: "虚构的 Windows Read 路径，验证反斜杠规范化。"}
# 盘符前不能还有单词字符，否则 https 的末尾也会被当成盘符。
DRIVE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]")
PRIVATE_MARKERS = ("/" + "Users/", "/" + "home/", "One" + "Drive", "lz" + "cm729")


def private_hits(text, allow_drive=False):
    hits = [] if allow_drive else DRIVE.findall(text)
    hits.extend(marker for marker in PRIVATE_MARKERS if marker.casefold() in text.casefold())
    return hits


def test_no_private_paths():
    checked = 0
    for root in ROOTS:
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.name.startswith(".env") or "__pycache__" in path.parts:
                continue
            try:
                text = path.read_bytes().decode("utf-8-sig")
            except UnicodeDecodeError:
                continue
            relative = path.relative_to(REPO).as_posix()
            assert not private_hits(text, relative in EXEMPTIONS), relative
            checked += 1
    assert checked > 0
    assert all((REPO / path).is_file() and reason for path, reason in EXEMPTIONS.items())


@pytest.mark.parametrize("text", ["Q:" + "/work/book.md", "/" + "Users/example", "/" + "home/example",
                                  "One" + "Drive/project", "lz" + "cm729"])
def test_privacy_detects_private_markers(text):
    assert private_hits(text)


def test_windows_exemption_keeps_other_checks():
    assert not private_hits("Q:" + "/snap/book.md", allow_drive=True)
    assert private_hits("Q:" + "/" + "Users/example/book.md", allow_drive=True)


def test_privacy_allows_web_urls():
    assert not private_hits("https://example.org/method")
