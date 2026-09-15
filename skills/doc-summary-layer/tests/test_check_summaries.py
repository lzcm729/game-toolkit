"""doc-summary-layer 两个脚本的结构性用例：不碰平台、不读真实工程。"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import build_summary_pages as bp  # noqa: E402
import check_summaries as cs  # noqa: E402

GOOD = """# 一句话

篝火边的猫吃什么、吃多少，由今天钓到的鱼决定。

# 规则

## 投喂

- 每条鱼只能被吃一次，吃掉即从鱼缸移除。
- 一只猫每晚最多吃三条，第四条会被拒绝（快照）。

## 效果

- 吃鱼给一层限时增益，持续到下一次入夜。

# 未决

- 增益能不能叠加，详稿标待定。
"""

BAD = """# 规则

## 投喂

- **每条鱼**只能被吃一次。
- 这是一条很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长很长的规则。
  - 嵌套的一条
| 表 | 头 |

## 空的组

# 接口

- 饥饿值决定能吃几条。
"""


def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    io.open(p, "w", encoding="utf-8", newline="\n").write(text)


def test_check_text_passes_good_summary():
    r = cs.check_text(GOOD, 60, ["饥饿值"])
    assert r["problems"] == []
    assert r["rules"] == 4 and r["groups"] == 2


def test_check_text_flags_every_structural_problem():
    r = cs.check_text(BAD, 60, ["饥饿值"])
    p = "；".join(r["problems"])
    for token in ("缺 # 一句话", "有加粗", "有表格", "有嵌套列表", "超 60 字", "空分组:空的组", "死概念:饥饿值"):
        assert token in p, (token, p)


def test_check_dir_uses_manifest_and_reports_missing(tmp_path: Path):
    summaries = tmp_path / "summaries"
    write(summaries / "GDD" / "篝火.md", GOOD)
    manifest = tmp_path / "manifest.json"
    write(manifest, json.dumps({"docs": [{"file": "GDD/篝火.md", "node_token": "tok1"},
                                          {"file": "GDD/鱼缸.md", "node_token": "tok2"}]}, ensure_ascii=False))
    result = cs.check_dir(summaries, cs.manifest_files(manifest), 60, [], set())
    assert result["ok"] is False
    assert result["missing"] == ["GDD/鱼缸.md"]
    assert [r["file"] for r in result["report"]] == ["GDD/篝火.md"]
    assert cs.main(["--summaries", str(summaries), "--manifest", str(manifest)]) == 1
    write(summaries / "GDD" / "鱼缸.md", GOOD)
    assert cs.main(["--summaries", str(summaries), "--manifest", str(manifest)]) == 0


def test_exempt_skips_dead_words_for_that_file(tmp_path: Path):
    summaries = tmp_path / "s"
    write(summaries / "旧词对照.md", GOOD.replace("由今天钓到的鱼决定", "不说饥饿值"))
    words = tmp_path / "dead.txt"
    write(words, "# 注释\n饥饿值\n")
    assert cs.main(["--summaries", str(summaries), "--dead-words", str(words)]) == 1
    assert cs.main(["--summaries", str(summaries), "--dead-words", str(words), "--exempt", "旧词对照.md"]) == 0


def test_build_adds_banner_and_applies_profile(tmp_path: Path):
    summaries = tmp_path / "summaries"
    write(summaries / "GDD" / "篝火.md", "---\nssot: true\n---\n<title>篝火</title>\n" + GOOD.replace("一层限时增益", "**一层**限时增益"))
    out = tmp_path / "out"
    manifest = {"docs": [{"file": "GDD/篝火.md", "node_token": "tok1"}]}
    index = bp.build(summaries, out, rev="abc1234", ssot_root="Knowledge/Design/", profile="feishu",
                     date="2026-09-15", manifest=manifest, banner_template=bp.DEFAULT_BANNER)
    assert index[0]["node_token"] == "tok1"
    page = io.open(out / "GDD" / "篝火.md", encoding="utf-8").read()
    assert page.startswith("> <b>规则版摘要</b>（2026-09-15，据仓库 abc1234）")
    assert "`Knowledge/Design/GDD/篝火.md`" in page
    assert "ssot: true" not in page and "<title>" not in page
    assert "<b>一层</b>限时增益" in page and "**" not in page
    idx = json.loads(io.open(out / "index.json", encoding="utf-8").read())
    assert idx[0]["file"] == "GDD/篝火.md" and idx[0]["profile"] == "feishu"


def test_build_plain_profile_keeps_markdown(tmp_path: Path):
    summaries = tmp_path / "summaries"
    write(summaries / "a.md", GOOD.replace("一层限时增益", "**一层**限时增益"))
    index = bp.build(summaries, tmp_path / "out", rev="v1.2", ssot_root="docs", profile="plain",
                     date="2026-09-15", manifest=None, banner_template=bp.DEFAULT_BANNER)
    page = io.open(tmp_path / "out" / "a.md", encoding="utf-8").read()
    assert page.startswith("> **规则版摘要**（2026-09-15，据仓库 v1.2）")
    assert "**一层**限时增益" in page
    assert "node_token" not in index[0]
