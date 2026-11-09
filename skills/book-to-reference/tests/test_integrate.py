"""发布生成要可重跑，分组、截断和路径错误都不能静默改变交付。"""
import os
import re
import subprocess
import sys

import pytest
import yaml

import integrate


def test_tie_prefers_real_chapter():
    units = ["u00-01", "u00-02", "u11-01", "u11-05"]
    assert integrate.main_chapter(units) == "11"
    for seed in range(5):
        result = subprocess.run([sys.executable, "-c", "import integrate; print(integrate.main_chapter(" + repr(units) + "))"],
                                cwd=integrate.Path(__file__).parent.parent / "scripts",
                                env={**os.environ, "PYTHONHASHSEED": str(seed)}, capture_output=True, text=True)
        assert result.returncode == 0 and result.stdout.strip() == "11"
    assert integrate.main_chapter(["u02-01", "u01-01"]) == "01"


def test_safe_cut_keeps_backtick_name():
    text = "参考 `micro-a-long-name.md` 后再决定。"
    assert "`micro-a-long-name.md`" in integrate.safe_cut(text, 12)


def prepare(workdir):
    path = workdir / "stage2/quick-ref.md"
    path.write_text("简短速查。\n\n", encoding="utf-8", newline="\n")
    for path in (workdir / "meta").glob("*.yaml"):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data.setdefault("intents", [data["title"]])
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8", newline="\n")


def test_unmapped_entry_chapter_rejected(microbook, plugin_copy):
    prepare(microbook)
    path = microbook / "book.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["entry_groups"] = {"起步": ["01", "03"]}
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8", newline="\n")
    before = {p.relative_to(plugin_copy): p.read_bytes() for p in plugin_copy.rglob("*") if p.is_file()}
    with pytest.raises(ValueError, match="02"):
        integrate.run(microbook)
    assert before == {p.relative_to(plugin_copy): p.read_bytes() for p in plugin_copy.rglob("*") if p.is_file()}


def test_integrate_microbook_end_to_end(microbook, plugin_copy):
    prepare(microbook)
    retained = plugin_copy / "skills/game-design-theory/references/retained.md"
    retained.write_bytes(b"# Retained\r\n\r\nExisting text.\r\n")
    result = integrate.run(microbook)
    assert not result.residue
    refs = plugin_copy / "skills/game-design-theory/references"
    assert (refs / "micro-steady-shadow.md").is_file()
    assert retained.read_bytes() == b"# Retained\r\n\r\nExisting text.\r\n"
    assert not (refs / "old.md").exists()
    skill = (refs.parent / "SKILL.md").read_text(encoding="utf-8")
    table = skill.split("<!-- TABLE START -->")[1].split("<!-- TABLE END -->")[0]
    assert "micro-steady-shadow.md" in table
    before = {p.relative_to(plugin_copy): p.read_bytes() for p in plugin_copy.rglob("*") if p.is_file()}
    assert not integrate.run(microbook).residue
    assert before == {p.relative_to(plugin_copy): p.read_bytes() for p in plugin_copy.rglob("*") if p.is_file()}
    assert all(b"\r" not in p.read_bytes() for p in result.written)


def test_description_limit_precedes_writes(microbook, plugin_copy):
    prepare(microbook)
    (microbook / "description.txt").write_text("x" * 1025, encoding="utf-8", newline="\n")
    path = microbook / "book.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["skill_md"]["description_file"] = "description.txt"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="1024"):
        integrate.run(microbook)


def test_integrate_leaves_unrelated_files(microbook, plugin_copy):
    prepare(microbook)
    unrelated = plugin_copy / "skills/game-design-theory/references/unrelated.md"
    # 其他书的合法用语不能被本书的残留清单误报；连换行也不归本次接入管。
    content = "# Other book\r\n\r\n分析单元与参考单元。\r\n".encode("utf-8")
    unrelated.write_bytes(content)
    result = integrate.run(microbook)
    assert unrelated.read_bytes() == content
    assert unrelated not in result.written
    assert not any(path == unrelated for path, _, _ in result.residue)


def test_notes_title_uses_display_names(microbook, plugin_copy):
    prepare(microbook)
    path = microbook / "book.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data.update(display_author="Mira", display_title="Lantern Trials")
    data["mask_names"] = {"authors": ["Different Author", "Mira"],
                          "titles": ["Other Book", "Lantern Trials"]}
    path.write_text(yaml.safe_dump(data), encoding="utf-8", newline="\n")
    integrate.run(microbook)
    notes = microbook / "landing/notes.md"
    first = notes.read_bytes()
    assert first.decode("utf-8").startswith("# Mira《Lantern Trials》")
    data["mask_names"] = {"authors": [], "titles": []}
    path.write_text(yaml.safe_dump(data), encoding="utf-8", newline="\n")
    integrate.run(microbook)
    assert notes.read_bytes() == first


def test_scope_reference_enters_notes_without_unit(microbook):
    prepare(microbook)
    before = {path.name: path.read_bytes() for path in (microbook / "verify/out").glob("*.yaml")}
    integrate.run(microbook)
    notes = (microbook / "landing/notes.md").read_text(encoding="utf-8")
    section = notes.split("## 只作参考的作者观点", 1)[1]
    assert "讨论灯笼的象征" in section and "只作参考" in section
    assert "没有可执行步骤" in section and "p.4" in section
    assert not re.search(r"u\d\d-\d\d", section)
    assert before == {path.name: path.read_bytes() for path in (microbook / "verify/out").glob("*.yaml")}


def test_scope_out_of_scope_not_in_notes(microbook):
    prepare(microbook)
    path = microbook / "candidates/_scope.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data[0]["decision"] = "out_of_scope"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8", newline="\n")
    integrate.run(microbook)
    assert "讨论灯笼的象征" not in (microbook / "landing/notes.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("intents", [None, [], ["", "  "], "比较影子", [7]])
def test_empty_or_invalid_intents_block_before_writes(microbook, plugin_copy, intents, capsys):
    prepare(microbook)
    path = microbook / "meta/shutter-test.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if intents is None:
        del data["intents"]
    else:
        data["intents"] = intents
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8", newline="\n")
    before = {p.relative_to(plugin_copy): p.read_bytes() for p in plugin_copy.rglob("*") if p.is_file()}
    assert integrate.main([str(microbook)]) == 1
    message = capsys.readouterr().err
    assert "shutter-test" in message and "intents" in message
    assert before == {p.relative_to(plugin_copy): p.read_bytes() for p in plugin_copy.rglob("*") if p.is_file()}
    assert not (microbook / "landing/notes.md").exists()


def test_single_card_group_allows_no_neighbour(microbook, plugin_copy):
    prepare(microbook)
    integrate.run(microbook)
    skill = (plugin_copy / "skills/game-design-theory/SKILL.md").read_text(encoding="utf-8")
    row = next(line for line in skill.splitlines() if "[micro-steady-shadow.md]" in line)
    assert row.endswith("| — |")


def test_multi_card_group_requires_neighbour(microbook):
    prepare(microbook)
    card = microbook / "cards/shutter-test.md"
    text = re.sub(r"\*\*与相邻卡的区分\*\*.*?(?=^## |\Z)", "", card.read_text(encoding="utf-8"), flags=re.M | re.S)
    card.write_text(text, encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="近邻.*shutter-test"):
        integrate.run(microbook)


def test_intents_skip_blank_entries(microbook, plugin_copy):
    prepare(microbook)
    path = microbook / "meta/shutter-test.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["intents"] = ["", " ", "", "  每次应该只动哪片挡板  "]
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8", newline="\n")
    integrate.run(microbook)
    skill = (plugin_copy / "skills/game-design-theory/SKILL.md").read_text(encoding="utf-8")
    assert "| 每次应该只动哪片挡板 |" in skill


def test_notes_slug_rejected_before_writes(microbook):
    prepare(microbook)
    path = microbook / "stage2/CARD-PLAN.md"
    path.write_text(path.read_text(encoding="utf-8").replace("steady-shadow", "notes"), encoding="utf-8")
    with pytest.raises(ValueError, match="保留的 notes"):
        integrate.run(microbook)
    assert not (microbook / "landing/notes.md").exists()


def test_scope_publication_related_and_title_ruling(microbook):
    prepare(microbook)
    path = microbook / "candidates/_scope.yaml"
    scope = yaml.safe_load(path.read_text(encoding="utf-8"))
    scope[0].update(reason="补读后仅供交付检查。限制不能省略。", related=["steady-shadow"])
    path.write_text(yaml.safe_dump(scope, allow_unicode=True), encoding="utf-8")
    config = microbook / "book.yaml"
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    data["rulings"] = [{"find": "补读后仅供交付检查。", "replace": "原书仅有象征性描述。", "why": "公开说明来源性质", "scope": "notes"},
                       {"find": "术语与只作参考的观点", "replace": "术语与观点", "why": "明确显示标题", "scope": "notes"}]
    config.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    result = integrate.run(microbook)
    text = (microbook / "landing/notes.md").read_text(encoding="utf-8")
    assert text.splitlines()[0].endswith("术语与观点")
    assert "原因：原书仅有象征性描述。限制不能省略。 相关：`micro-steady-shadow.md`" in text
    assert not result.residue


def test_notes_retains_full_summary_and_reason(microbook):
    prepare(microbook)
    path = microbook / "verify/out/G1.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["units"][0].update(decision="reference", one_liner="只是比较。第二句是适用限制。", decision_reason="只有观点。不得推为操作标准。")
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    integrate.run(microbook)
    text = (microbook / "landing/notes.md").read_text(encoding="utf-8")
    assert "第二句是适用限制。 原因：只有观点。不得推为操作标准。" in text


def test_when_to_use_replaced_and_existing_usage_not_duplicated(microbook, plugin_copy):
    prepare(microbook)
    card = microbook / "cards/steady-shadow.md"
    card.write_text(card.read_text(encoding="utf-8").replace("# 比较影子", "# 比较影子\n\n> **怎么用这张卡**：已有的用法句。"), encoding="utf-8")
    integrate.run(microbook)
    config = microbook / "book.yaml"
    data = yaml.safe_load(config.read_text(encoding="utf-8"))
    old = data["skill_md"]["when_to_use_line"]
    data["skill_md"]["when_to_use_line"] = "新的灯光试验触发句。"
    config.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    integrate.run(microbook)
    skill = (plugin_copy / "skills/game-design-theory/SKILL.md").read_text(encoding="utf-8")
    assert old not in skill and skill.count("新的灯光试验触发句。") == 1
    text = (plugin_copy / "skills/game-design-theory/references/micro-steady-shadow.md").read_text(encoding="utf-8")
    assert text.count("**怎么用这张卡**") == 1
    assert "已有的用法句。" in text
