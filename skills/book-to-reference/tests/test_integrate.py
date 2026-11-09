"""发布生成要可重跑，分组、截断和路径错误都不能静默改变交付。"""
import os
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
        data["intents"] = [data["title"]]
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
