# -*- coding: utf-8 -*-
"""build_page.py：裁决单.json 校验与注入。

规则来自 SKILL.md「写题」一节：每题恰好一个倾向、选项 2～3 个、id 全局唯一、
不在单上的组不空也不重名；这些靠脚本拦，比靠 agent 自觉稳。引文核对见后半部分。
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import time
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
    (lambda d: d["outside"].append(["直接进 issue，不用你拍", ["x"]]), None),  # 项目自己的去向：合法
    (lambda d: d["outside"].append(["我会顺手改的", ["y"]]), "组名「我会顺手改的」重复"),
    (lambda d: d["outside"].append(["  ", ["y"]]), "组名不能空"),
    (lambda d: d["outside"].append(["只有空白", [" ", ""]]), "没有内容"),
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


def _quote_sheet(*quotes):
    """一题一组的最小裁决单，quotes 是 [出处, 原文] 列表。"""
    data = _load()
    item = data["groups"][0]["items"][0]
    item["quotes"] = [list(q) for q in quotes]
    data["groups"] = [{"id": "g", "title": "组", "items": [item]}]
    return data


def _repo(tmp_path, files):
    root = tmp_path / "repo"
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


def test_quote_found_verbatim_with_right_line(tmp_path):
    root = _repo(tmp_path, {"docs/战斗规则.md": "# 标题\n\n血量归零即出局，本局不再回到场上。\n"})
    warnings, c = bp.check_quotes(_quote_sheet(["战斗规则.md:3", "血量归零即出局，本局不再回到场上。"]), root)
    assert warnings == [] and c["ok"] == 1 and c["bad"] == 0


def test_quote_ignores_whitespace_width_and_markdown(tmp_path):
    root = _repo(tmp_path, {"a.md": "**快捷栏** 占背包前四格（[物品规则](https://x)，2026-09-15）\n"})
    warnings, c = bp.check_quotes(_quote_sheet(["a.md 第 1 行", "快捷栏占背包前四格(物品规则, 2026-09-15)"]), root)
    assert warnings == [] and c["ok"] == 1


def test_quote_line_mismatch_reports_actual_line(tmp_path):
    root = _repo(tmp_path, {"a.md": "\n".join(["x"] * 9 + ["倒地后队友可以拉起"])})
    warnings, c = bp.check_quotes(_quote_sheet(["a.md:3", "倒地后队友可以拉起"]), root)
    assert c["bad"] == 1 and "第 10 行" in warnings[0] and "第 3 行" in warnings[0]


def test_section_number_is_not_a_line_number(tmp_path):
    root = _repo(tmp_path, {"a.md": "\n".join(["x"] * 9 + ["这句在第 10 行"])})
    warnings, c = bp.check_quotes(_quote_sheet(["a.md 第 3 节", "这句在第 10 行"],
                                               ["a.md（附篇）第 10 行", "这句在第 10 行"]), root)
    assert warnings == [] and c["ok"] == 2


def test_quote_not_found_suggests_closest_line(tmp_path):
    root = _repo(tmp_path, {"a.md": "第一行\n多人模式下队友可以拉起、救援。\n"})
    warnings, c = bp.check_quotes(_quote_sheet(["a.md:2", "多人模式下队友可以复活、救援。"]), root)
    assert c["bad"] == 1 and "找不到" in warnings[0] and "第 2 行" in warnings[0]


def test_quote_ellipsis_fragments_must_appear_in_order(tmp_path):
    root = _repo(tmp_path, {"a.md": "每个房间最多放三个宝箱，离开再回来也不会多刷。\n"})
    ok, c1 = bp.check_quotes(_quote_sheet(["a.md", "每个房间最多放三个宝箱……不会多刷。"]), root)
    bad, c2 = bp.check_quotes(_quote_sheet(["a.md", "不会多刷……每个房间最多放三个宝箱"]), root)
    assert ok == [] and c1["ok"] == 1 and c2["bad"] == 1


def test_quote_without_repo_file_is_skipped_and_missing_file_is_reported(tmp_path):
    root = _repo(tmp_path, {"a.md": "x\n"})
    warnings, c = bp.check_quotes(_quote_sheet(["设计账本 2026-09-22 第 33 条", "数值只在参数表里改"],
                                               ["不存在.md:4", "随便一句"]), root)
    assert c["skipped"] == 1 and c["bad"] == 1 and "不存在.md" in warnings[0]


def test_same_name_file_prefers_the_sheets_own_directory(tmp_path):
    root = _repo(tmp_path, {"docs/design/商店.md": "商店每天刷新一次货架。\n",
                            "docs/design/物品.md": "背包前四格为快捷栏。\n",
                            "docs/old/商店.md": "旧稿：商店每周刷新。\n"})
    warnings, c = bp.check_quotes(_quote_sheet(["docs/design/物品.md", "背包前四格为快捷栏。"],
                                               ["商店.md", "商店每天刷新一次货架。"]), root)
    assert warnings == [] and c["ok"] == 2


def test_same_name_file_without_any_hint_asks_for_full_path(tmp_path):
    root = _repo(tmp_path, {"x/商店.md": "同一句。\n", "y/商店.md": "同一句。\n"})
    warnings, c = bp.check_quotes(_quote_sheet(["商店.md", "同一句。"]), root)
    assert c["bad"] == 1 and "写全路径" in warnings[0]


def test_file_name_with_space_and_csv_rows(tmp_path):
    csv_text = 'id,特点\nEnemy_A,"会隐身。\n只在夜晚出现。"\nEnemy_B,普通\n'
    root = _repo(tmp_path, {"系统 总览/系统 总览.md": "a\n出处只有两种。\n", "敌人表/第一版.csv": csv_text})
    warnings, c = bp.check_quotes(_quote_sheet(["总览页「统一口径」，系统 总览.md:2", "出处只有两种。"],
                                               ["敌人表/第一版.csv 第 2 行［特点］", "只在夜晚出现。"]), root)
    assert warnings == [] and c["ok"] == 2


def test_main_warns_on_bad_quote_but_still_builds(tmp_path, capsys):
    root = _repo(tmp_path, {"a.md": "现行说法。\n"})
    src = _write(tmp_path, _quote_sheet(["a.md:1", "旧说法。"]))
    assert bp.main([str(src), "--root", str(root)]) == 0
    assert (tmp_path / "裁决单.html").exists()
    captured = capsys.readouterr()
    assert "找不到" in captured.err and "1 条有问题" in captured.out


# ---- 以下是 4.12.0 独立评审复现过的边界 ----

def test_file_deleted_from_worktree_warns_instead_of_crashing(tmp_path):
    root = _repo(tmp_path, {"a.md": "原文\n"})
    for cmd in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"],
                ["add", "."], ["commit", "-qm", "x"]):
        subprocess.run(["git", "-C", str(root), *cmd], check=True, capture_output=True)
    (root / "a.md").unlink()
    warnings, c = bp.check_quotes(_quote_sheet(["a.md:1", "原文"]), root)
    assert c["bad"] == 1 and "没核" in warnings[0]


def test_written_directory_must_match(tmp_path):
    root = _repo(tmp_path, {"current/a.md": "新句\n", "old/a.md": "旧句\n"})
    warnings, c = bp.check_quotes(_quote_sheet(["typo/a.md:1", "旧句"]), root)
    assert c["bad"] == 1 and "typo/a.md" in warnings[0] and "current/a.md" in warnings[0]


def test_only_the_first_file_in_a_source_is_checked(tmp_path):
    root = _repo(tmp_path, {"a.md": "别的话\n", "docs/b.md": "这句只在 b 里\n"})
    warnings, c = bp.check_quotes(_quote_sheet(["a.md:1（参考 docs/b.md）", "这句只在 b 里"]), root)
    assert c["bad"] == 1 and "a.md" in warnings[0]


def test_same_name_copy_found_only_by_content_is_not_verified(tmp_path):
    root = _repo(tmp_path, {"current/a.md": "新句\n", "old/a.md": "旧句\n"})
    warnings, c = bp.check_quotes(_quote_sheet(["a.md", "旧句"]), root)
    assert c["bad"] == 1 and "old/a.md" in warnings[0] and "写全路径" in warnings[0]


def test_one_shared_top_directory_is_not_enough_to_pick_a_copy(tmp_path):
    root = _repo(tmp_path, {"docs/design/other.md": "锚点\n", "docs/archive/a.md": "旧句\n", "official/a.md": "新句\n"})
    warnings, c = bp.check_quotes(_quote_sheet(["docs/design/other.md", "锚点"], ["a.md", "旧句"]), root)
    assert c["ok"] == 1 and c["bad"] == 1 and "写全路径" in warnings[0]


def test_single_char_fragment_and_literal_star_are_kept(tmp_path):
    root = _repo(tmp_path, {"a.md": "甲乙\n扣除 2*3 个道具。\n"})
    _, c1 = bp.check_quotes(_quote_sheet(["a.md", "甲乙……错"]), root)
    _, c2 = bp.check_quotes(_quote_sheet(["a.md", "扣除23个道具。"]), root)
    _, c3 = bp.check_quotes(_quote_sheet(["a.md:2", "扣除 2*3 个道具。"]), root)
    assert c1["bad"] == 1 and c2["bad"] == 1 and c3["ok"] == 1


def test_csv_cells_are_compared_unescaped_even_when_huge(tmp_path):
    big = "x" * 200000
    csv_text = 'id,text\n1,"他说""可以"""\n2,"%s\n\n目标内容"\n' % big
    root = _repo(tmp_path, {"t.csv": csv_text})
    warnings, c = bp.check_quotes(_quote_sheet(["t.csv 第 2 行", '他说"可以"'], ["t.csv 第 3 行", "目标内容"]), root)
    assert warnings == [] and c["ok"] == 2


def test_line_number_is_exact_and_a_range_must_cover_the_whole_quote(tmp_path):
    root = _repo(tmp_path, {"a.md": "甲乙\nx\nx\nx\nx\n丙丁\n"})
    w1, _ = bp.check_quotes(_quote_sheet(["a.md:2", "甲乙"]), root)
    w2, _ = bp.check_quotes(_quote_sheet(["a.md:1-2", "甲乙……丙丁"]), root)
    w3, c3 = bp.check_quotes(_quote_sheet(["a.md:1-6", "甲乙……丙丁"]), root)
    assert "第 1 行" in w1[0] and "1～6" in w2[0] and w3 == [] and c3["ok"] == 1


def test_blockquote_prefix_and_fullwidth_ellipsis_are_normalized(tmp_path):
    root = _repo(tmp_path, {"a.md": "> 甲乙\n> 丙丁，中间的话，戊己\n"})
    warnings, c = bp.check_quotes(_quote_sheet(["a.md:1", "甲乙丙丁"], ["a.md", "甲乙．．．戊己"]), root)
    assert warnings == [] and c["ok"] == 2


def test_source_path_and_line_number_variants(tmp_path):
    root = _repo(tmp_path, {"docs/a.md": "第一句\n第二句\n"})
    warnings, c = bp.check_quotes(_quote_sheet(["docs\\a.md:1", "第一句"], ["`a.md`：2", "第二句"],
                                               ["a.md 第 3 节，第 2 行", "第二句"]), root)
    assert warnings == [] and c["ok"] == 3


def test_tip_shows_the_changed_words_and_flags_version_rows(tmp_path):
    root = _repo(tmp_path, {"a.md": "组队时队友倒地可以拉起、救援。\n\n# 版本历史\n\n| v1 | 旧说：宝箱归哪一类仍待属主定。 |\n"})
    w1, _ = bp.check_quotes(_quote_sheet(["a.md:1", "组队时队友倒地可以复活、救援。"]), root)
    w2, _ = bp.check_quotes(_quote_sheet(["a.md", "宝箱归哪一类仍待属主定，没有结论。"]), root)
    assert "复活" in w1[0] and "拉起" in w1[0]
    assert "版本记录" in w2[0]


def test_written_path_must_match_in_full(tmp_path):
    root = _repo(tmp_path, {"docs/design/a.md": "旧句\n", "docs/系统 总览.md": "旧句\n"})
    w, c = bp.check_quotes(_quote_sheet(["typo/design/a.md:1", "旧句"], ["typo/系统 总览.md:1", "旧句"],
                                        ["design/a.md:1", "旧句"], ["docs/系统 总览.md:1", "旧句"]), root)
    assert c["bad"] == 2 and c["ok"] == 2 and "typo/design/a.md" in w[0]


def test_double_extension_is_read_as_one_file_name(tmp_path):
    root = _repo(tmp_path, {"docs/a.md.backup.md": "现行句\n", "docs/a.md": "旧句\n"})
    w, c = bp.check_quotes(_quote_sheet(["docs/a.md.backup.md:1", "旧句"], ["docs/a.md.backup.md:1", "现行句"]), root)
    assert c["bad"] == 1 and c["ok"] == 1 and "a.md.backup.md" in w[0]


def test_bold_markers_are_dropped_from_the_file_only(tmp_path):
    """引文是渲染后的文字；文件里的粗体记号去掉，跨行的也去，「2**3」和转义的 \\*\\* 按字面留着。"""
    root = _repo(tmp_path, {"a.md": "结果为 2**3。\n规则标记为 \\*\\*。\n**加粗**的说法。\n"
                                     "按日期为准；**判口径以最新\n裁决为准**\n"})
    _, c1 = bp.check_quotes(_quote_sheet(["a.md:1", "结果为23。"]), root)
    w2, c2 = bp.check_quotes(_quote_sheet(["a.md:2", "规则标记为 **。"], ["a.md:3", "加粗的说法。"],
                                          ["a.md 第 4～5 行", "按日期为准；判口径以最新裁决为准"]), root)
    assert c1["bad"] == 1 and w2 == [] and c2["ok"] == 3


def test_quote_copied_with_its_line_prefix_still_matches(tmp_path):
    root = _repo(tmp_path, {"a.md": "> 甲乙\n## 规则\n- 扣除两个道具\n"})
    w, c = bp.check_quotes(_quote_sheet(["a.md:1", "> 甲乙"], ["a.md:2", "## 规则"], ["a.md:3", "- 扣除两个道具"]), root)
    assert w == [] and c["ok"] == 3


def test_line_number_of_a_later_file_is_not_borrowed(tmp_path):
    root = _repo(tmp_path, {"a.md": "正确原文\n", "b.md": "x\n"})
    w, c = bp.check_quotes(_quote_sheet(["a.md（参考 b.md 第 99 行）", "正确原文"]), root)
    assert w == [] and c["ok"] == 1


def test_empty_quote_from_a_repo_file_is_reported(tmp_path):
    root = _repo(tmp_path, {"a.md": "x\n"})
    w, c = bp.check_quotes(_quote_sheet(["a.md:1", "……"]), root)
    assert c["bad"] == 1 and "空的" in w[0]


def test_closest_line_search_stays_fast_on_a_huge_line(tmp_path):
    root = _repo(tmp_path, {"a.md": "甲乙" * 500000 + "终点内容\n短的一行，甲乙甲乙不存在\n"})
    t = time.time()
    w, c = bp.check_quotes(_quote_sheet(["a.md", "甲乙" * 60 + "不存在"]), root)
    assert c["bad"] == 1 and time.time() - t < 3


def test_non_utf8_file_is_reported_not_misread(tmp_path):
    root = _repo(tmp_path, {"a.md": "x\n"})
    (root / "a.md").write_bytes("现行规则\n".encode("gbk"))
    warnings, c = bp.check_quotes(_quote_sheet(["a.md:1", "现行规则"]), root)
    assert c["bad"] == 1 and "UTF-8" in warnings[0]


def test_long_repetitive_file_stays_fast(tmp_path):
    root = _repo(tmp_path, {"a.md": "甲乙" * 100000 + "终点内容\n"})
    t = time.time()
    _, c = bp.check_quotes(_quote_sheet(["a.md", "甲乙……终点内容"], ["a.md", "甲乙……不存在"]), root)
    assert c["ok"] == 1 and time.time() - t < 2


def test_script_tag_in_text_cannot_break_page(tmp_path):
    data = _load()
    data["groups"][0]["items"][0]["ctx"] = "有人在文档里写了 </script><b>x</b>"
    src = _write(tmp_path, data)
    assert bp.main([str(src)]) == 0
    html = (tmp_path / "裁决单.html").read_text(encoding="utf-8")
    assert html.count("</script>") == 1
