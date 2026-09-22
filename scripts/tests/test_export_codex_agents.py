# -*- coding: utf-8 -*-
"""export_codex_agents.py：把插件 agents/*.md 转成项目里的 .codex/agents/*.toml。

Codex 的自定义 agent 是 TOML（name / description / developer_instructions），
插件清单带不进去，只能落到项目仓库里；这个脚本就是那一步。
"""
from __future__ import annotations

import sys
import tomllib
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import export_codex_agents as ex  # noqa: E402

REPO = SCRIPTS.parent
AGENTS = REPO / "agents"


def _tomls(root: Path) -> dict:
    out = {}
    for p in sorted((root / ".codex" / "agents").glob("*.toml")):
        out[p.stem] = tomllib.loads(p.read_text(encoding="utf-8"))
    return out


def test_exports_all_four_agents_as_valid_toml(tmp_path, capsys):
    assert ex.main([str(tmp_path)]) == 0
    got = _tomls(tmp_path)
    assert set(got) == {"framework", "content", "interaction", "game-designer"}
    for name, doc in got.items():
        assert doc["name"] == name
        assert doc["description"].strip()
        assert "<example>" not in doc["description"], "Claude 风格的示例块不该进 Codex 的 description"
        assert doc["developer_instructions"].strip()
    # 正文要完整：game-designer.md 的开头那句得在
    assert "Game Designer" in got["game-designer"]["developer_instructions"]
    msg = capsys.readouterr().out
    assert "4" in msg and ".codex" in msg


def test_instructions_carry_harness_preamble_and_source_note(tmp_path):
    ex.main([str(tmp_path)])
    text = (tmp_path / ".codex" / "agents" / "framework.toml").read_text(encoding="utf-8")
    assert text.startswith("#"), "文件头要有生成说明，人打开就知道别手改"
    assert "agents/framework.md" in text
    doc = tomllib.loads(text)
    assert "Codex" in doc["developer_instructions"][:400], "开头要有一段告诉它 Claude Code 专属工具怎么对应"


def test_quotes_and_backslashes_survive_roundtrip(tmp_path):
    src = tmp_path / "agents"
    src.mkdir()
    body = '正文里有 """ 三引号、反斜杠 C:\\Users\\x 和 \\n 这种写法，\n还有 <example>不该被删的正文示例</example>。\n'
    (src / "tricky.md").write_text(
        '---\nname: tricky\ndescription: |\n  一句描述。\n  <example>\n  user: "x"\n  </example>\n  第二句。\n'
        'tools: ["Read"]\n---\n' + body, encoding="utf-8")
    root = tmp_path / "proj"
    root.mkdir()
    assert ex.main([str(root), "--agents-dir", str(src)]) == 0
    doc = tomllib.loads((root / ".codex" / "agents" / "tricky.toml").read_text(encoding="utf-8"))
    assert doc["developer_instructions"].endswith(body)
    assert doc["description"] == "一句描述。\n第二句。"


def test_dry_run_writes_nothing(tmp_path, capsys):
    assert ex.main([str(tmp_path), "--dry-run"]) == 0
    assert not (tmp_path / ".codex").exists()
    assert "framework" in capsys.readouterr().out


def test_missing_root_or_frontmatter_fails_loudly(tmp_path, capsys):
    assert ex.main([str(tmp_path / "不存在")]) == 1
    src = tmp_path / "agents"
    src.mkdir()
    (src / "broken.md").write_text("没有 frontmatter 的文件\n", encoding="utf-8")
    root = tmp_path / "proj"
    root.mkdir()
    assert ex.main([str(root), "--agents-dir", str(src)]) == 1
    assert "broken.md" in capsys.readouterr().err
