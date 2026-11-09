"""公开化不能抹掉限制；豁免只保护那段合法文字。"""
from bookconf import Ruling
import publicize


def test_rulings_before_generic_terms():
    rule = Ruling("本单元的特殊限制", "依据不足", "保留来源限制", "cards")
    assert publicize.apply("本单元的特殊限制", [rule], "cards") == "依据不足"
    assert publicize.apply("本单元的特殊限制", [rule], "notes") != "依据不足"


def test_quote_lines_untouched():
    text = "> 单元复核原句\n> — 原书单元\n普通行（参考单元）\n"
    result = publicize.apply(text, [Ruling("单元", "内容", "不能改引文", "all")], "cards")
    assert result.splitlines()[:2] == text.splitlines()[:2]


def test_scan_keeps_source_labels():
    text = "以下是合成演练；依据不足；原图缺失。"
    assert publicize.scan(text, []) == []
    assert publicize.apply(text, [], "cards") == text


def test_scan_allow_is_fragment_only():
    problems = publicize.scan("分析单元与参考单元", ["分析单元"])
    assert problems and problems[0][0] == 1
    assert "参考单元" in problems[0][1]


def test_header_comment_only_is_skipped():
    assert publicize.scan("<!-- units: u01-01 -->\n正文 u01-01", []) == [(2, "正文 u01-01")]


def test_scope_process_language_flagged_without_normal_delivery_false_positive():
    assert publicize.scan("补读后进入交付流程", [])
    assert publicize.scan("玩家需要把货物交付给港口，完成交付后获得奖励。", []) == []
