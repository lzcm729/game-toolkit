# -*- coding: utf-8 -*-
"""build_page.py：裁决单.json 校验与注入。

规则来自 SKILL.md「写题」一节：每题恰好一个倾向、选项 2～3 个、id 全局唯一、
OUTSIDE 组名限定；这些靠脚本拦，比靠 agent 自觉稳。
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_page as bp  # noqa: E402

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "裁决单.example.json"


def _load():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _write(tmp_path, data, name="裁决单.json"):
    p = tmp_path / name
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_example_validates_and_builds(tmp_path, capsys):
    src = _write(tmp_path, _load())
    assert bp.main([str(src)]) == 0
    out = tmp_path / "裁决单.html"
    html = out.read_text(encoding="utf-8")
    assert "fonts.googleapis" not in html, "本地页面不能依赖网络"
    assert "const GROUPS" in html and "const OUTSIDE" in html
    assert "<title>" + _load()["page"]["title"] + "</title>" in html
    assert "DATA-BEGIN" not in html
    msg = capsys.readouterr().out
    assert "裁决单.html" in msg


def test_storage_key_is_deterministic_and_per_page():
    a = bp.storage_key({"title": "甲", "eyebrow": "x", "date": "2026-09-22"})
    b = bp.storage_key({"title": "甲", "eyebrow": "x", "date": "2026-09-22"})
    c = bp.storage_key({"title": "乙", "eyebrow": "x", "date": "2026-09-22"})
    assert a == b and a != c and a.startswith("rulings-2026-09-22-")


@pytest.mark.parametrize("mutate, needle", [
    (lambda d: d["groups"][0]["items"].append(copy.deepcopy(d["groups"][0]["items"][0])), "id 重复"),
    (lambda d: d["groups"][0]["items"][0]["opts"].__setitem__(1, ["B", "另一个倾向", "", 1]), "恰好一个倾向"),
    (lambda d: d["groups"][0]["items"][0]["opts"][0].__setitem__(3, 0), "恰好一个倾向"),
    (lambda d: d["groups"][0]["items"][0]["opts"].pop(), "2～3 个"),
    (lambda d: d["groups"][0]["items"][0]["opts"].extend([["C", "c", ""], ["D", "d", ""]]), "2～3 个"),
    (lambda d: d["groups"][0]["items"][0].__setitem__("ctx", ""), "ctx"),
    (lambda d: d["outside"].append(["随便起的组名", ["x"]]), "组名"),
    (lambda d: d["page"].__setitem__("date", "9/22"), "date"),
    (lambda d: d["groups"][0]["items"][0]["opts"][0].__setitem__(0, "A"), None),  # 合法：不报
])
def test_validation_errors(mutate, needle):
    data = _load()
    mutate(data)
    errors, _warnings = bp.validate(data)
    if needle is None:
        assert errors == []
    else:
        assert any(needle in e for e in errors), errors


def test_invalid_input_writes_nothing(tmp_path, capsys):
    data = _load()
    data["groups"][0]["items"][0]["opts"][0][3] = 0  # 没有倾向了
    src = _write(tmp_path, data)
    assert bp.main([str(src)]) == 1
    assert not (tmp_path / "裁决单.html").exists()
    assert "恰好一个倾向" in capsys.readouterr().err


def test_code_names_in_title_or_ctx_only_warn(tmp_path, capsys):
    data = _load()
    data["groups"][0]["items"][0]["title"] = "InventoryComponent::AddItem 要不要改"
    data["groups"][0]["items"][0]["ctx"] = "现在 max_slots 是 24。"
    errors, warnings = bp.validate(data)
    assert errors == []
    assert len(warnings) >= 2
    src = _write(tmp_path, data)
    assert bp.main([str(src)]) == 0
    assert "提醒" in capsys.readouterr().err


def test_status_banner_rendered_only_when_filled(tmp_path):
    """落地后把提交号、账本条目号写进 page.status 重建，页面顶上要能看见；没填就不渲染。"""
    data = _load()
    data["page"]["status"] = "已落地：提交 abc1234，账本 #0042"
    src = _write(tmp_path, data)
    assert bp.main([str(src)]) == 0
    html = (tmp_path / "裁决单.html").read_text(encoding="utf-8")
    assert "已落地：提交 abc1234，账本 #0042" in html
    assert 'id="status"' in html
    data["page"]["status"] = ""
    _write(tmp_path, data)
    assert bp.main([str(src)]) == 0
    data["page"].pop("status")
    _write(tmp_path, data)
    assert bp.main([str(src)]) == 0


def test_status_must_be_string():
    data = _load()
    data["page"]["status"] = ["不是字符串"]
    errors, _ = bp.validate(data)
    assert any("status" in e for e in errors), errors


def test_script_tag_in_text_cannot_break_page(tmp_path):
    data = _load()
    data["groups"][0]["items"][0]["ctx"] = "有人在文档里写了 </script><b>x</b>"
    src = _write(tmp_path, data)
    assert bp.main([str(src)]) == 0
    html = (tmp_path / "裁决单.html").read_text(encoding="utf-8")
    assert html.count("</script>") == 1
