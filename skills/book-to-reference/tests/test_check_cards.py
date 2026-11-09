"""引用命中全书不代表命中标注页，离散页不能被扩成连续范围。"""
import subprocess
import sys

import pytest

import bookconf
import check_cards as cc


def source_card(microbook):
    return ((microbook / "source/microbook.md").read_text(encoding="utf-8"),
            (microbook / "cards/steady-shadow.md").read_text(encoding="utf-8"))


def test_quote_on_cited_page(microbook):
    source, card = source_card(microbook)
    result, = cc.quote_pages(source, card)
    assert result.status == "OK"
    assert result.pages_claimed == frozenset({1})
    assert result.found_on == [1]
    assert result.card_line == 7


def test_quote_wrong_page_fails(microbook):
    source, card = source_card(microbook)
    assert cc.quote_pages(source, card.replace("p.1", "p.3"))[0].status == "OFFPAGE"


def test_quote_discontinuous_pages(microbook):
    source = "[p.1] First page. [p.2] A steady lantern makes every shadow easier to compare. [p.3] Last page."
    _, card = source_card(microbook)
    assert cc.quote_pages(source, card.replace("p.1", "p.1, 3"))[0].status == "OFFPAGE"


def test_quote_without_page_fails_exit(microbook):
    source, card = source_card(microbook)
    card = card.replace("p.1", "")
    assert cc.quote_pages(source, card)[0].status == "NOPAGE"
    (microbook / "cards/steady-shadow.md").write_text(card, encoding="utf-8", newline="\n")
    result = subprocess.run([sys.executable, cc.__file__, str(microbook), "--only", "quotes"], capture_output=True)
    assert result.returncode == 1


def test_quote_word_changed_fails(microbook):
    source, card = source_card(microbook)
    assert cc.quote_pages(source, card.replace("steady", "flickering"))[0].status == "MISS"


def test_step_without_page_fails():
    result, = cc.step_pages("## E\n\n  1. 直接比较影子。\n\n## B\n")
    assert not result.ok
    assert result.line == 3


def test_step_with_convention_mark_passes():
    assert cc.step_pages("## E\n\n  1. 约定：记录观察时间。\n\n## B\n")[0].ok


def test_plan_unit_unassigned(microbook):
    path = microbook / "stage2/CARD-PLAN.md"
    path.write_text(path.read_text(encoding="utf-8").replace("u01-01", ""), encoding="utf-8", newline="\n")
    problems = cc.plan_problems(bookconf.open_workdir(microbook), microbook)
    assert any("u01-01" in problem and "unassigned" in problem for problem in problems)


def test_plan_matches_microbook(microbook):
    assert cc.plan_problems(bookconf.open_workdir(microbook), microbook) == []


@pytest.mark.parametrize("attribution, expected", [
    ("p.156–157", {156, 157}), ("pp.12-14", {12, 13, 14}), ("p.5, 7", {5, 7}),
])
def test_pages_of(attribution, expected):
    assert cc.pages_of(attribution) == frozenset(expected)


def test_cross_page_quote_checks_each_ellipsis_segment():
    source = "[p.1] one two three four [p.2] five six seven eight [p.3] nine ten eleven twelve"
    assert cc.quote_pages(source, "> one two three four five six seven eight\n> — p.2\n")[0].status == "OK"
    assert cc.quote_pages(source, "> one two three four … nine ten eleven twelve\n> — p.1\n")[0].status == "OFFPAGE"


def test_plan_missing_meta_and_branch_fail(microbook):
    (microbook / "meta/steady-shadow.yaml").unlink()
    card = microbook / "cards/shutter-test.md"
    card.write_text(card.read_text(encoding="utf-8").replace("### 分支", "普通文字"), encoding="utf-8", newline="\n")
    problems = cc.plan_problems(bookconf.open_workdir(microbook), microbook)
    assert any("missing card or meta" in problem for problem in problems)
    assert any("no branch heading" in problem for problem in problems)
