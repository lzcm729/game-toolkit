"""用现场生成的 PDF 检查排版规则，不把真实书籍文本放进夹具。"""
import builtins
import importlib.util
from pathlib import Path

import pytest

import pdf_convert as pc


def make_pdf(tmp_path):
    fitz = pytest.importorskip("fitz")
    path = tmp_path / "lantern.pdf"
    with fitz.open() as doc:
        for number in range(1, 5):
            page = doc.new_page()
            page.insert_text((60, 20), "running workshop header", fontsize=10)
            page.insert_text((60, 80), f"Section {number}", fontsize=14, fontname="hebo")
            page.insert_text((60, 110), "Compare the shadow carefully.", fontsize=9, fontname="cour")
            page.insert_text((60, 150), f"Page {number} ordinary para-", fontsize=10)
            page.insert_text((60, 165), "graph continues here.", fontsize=10)
            page.insert_text((90, 195), "Indented paragraph begins here.", fontsize=10)
            page.insert_text((60, 600), str(number), fontsize=10, fontname="tiro")
        doc.set_toc([[1, "Part I Light", 1], [2, "1 Observe", 1]])
        doc.save(path)
    return path


def config(**changes):
    return {
        "page_offset": 1, "start_page": 1, "stop_page": None,
        "title_min_size": 18,
        "header_max_y": 45, "para_indent_x": 84,
        "outline": {"part_pattern": r"Part (\w+)\s+(.*)", "chapter_pattern": r"^(\d+)\s+(.*)$"},
        "classes": [
            {"kind": "h3", "font_contains": "Helvetica-Bold", "size": 14, "tol": .2},
            {"kind": "skip", "font_contains": "Helvetica-Bold", "size": None, "tol": .2},
            {"kind": "callout", "font_contains": "Courier", "size": 9, "tol": .2},
        ],
        "page_number": {"font_contains": "Times-Roman", "pattern": r"\s*[\divxlc]+\s*"},
        **changes,
    }


def test_survey_lists_fonts_with_pages(tmp_path):
    rows = pc.survey_fonts(make_pdf(tmp_path))
    body = next(row for row in rows if row.font == "Helvetica" and row.size == 10)
    assert body.pages == [1, 2, 3, 4]
    assert body.count > 0 and body.sample
    assert rows == sorted(rows, key=lambda row: (-row.count, row.font, row.size))


def test_convert_page_markers(tmp_path):
    result = pc.convert(make_pdf(tmp_path), config())
    positions = [result.index(f"[p.{number}]") for number in ["fm-1", "1", "2", "3"]]
    assert positions == sorted(positions)
    assert "# Part I: Light" in result
    assert "## Chapter 1: Observe" in result


def test_convert_classes_in_order(tmp_path):
    result = pc.convert(make_pdf(tmp_path), config())
    assert "### Section 1" in result
    assert "> **[Callout]**" in result
    assert "running workshop header" not in result
    assert not any(line.strip() in {"1", "2", "3", "4"} for line in result.splitlines())


def test_convert_paragraph_indent(tmp_path):
    result = pc.convert(make_pdf(tmp_path), config())
    assert "ordinary paragraph continues here.\n\nIndented paragraph" in result


def test_stop_page(tmp_path):
    result = pc.convert(make_pdf(tmp_path), config(stop_page=4))
    assert "Page 3 ordinary" in result
    assert "Page 4 ordinary" not in result


def test_find_page_without_fitz(monkeypatch):
    original = builtins.__import__

    def reject_fitz(name, *args, **kwargs):
        if name == "fitz":
            raise ImportError("PyMuPDF intentionally unavailable")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_fitz)
    # dataclass 会查定义模块，复用已注册的模块名即可避免无关的加载差异。
    spec = importlib.util.spec_from_file_location(pc.__name__, pc.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = (Path(__file__).parent / "fixtures/microbook/source/microbook.md").read_text(encoding="utf-8")
    assert module.find_page(source, "Change one shutter") == 2
    assert module.find_page(source, "missing phrase") is None


def test_empty_page_still_has_marker(tmp_path):
    fitz = pytest.importorskip("fitz")
    path = tmp_path / "empty.pdf"
    with fitz.open() as doc:
        doc.new_page()
        doc.save(path)
    assert "[p.fm-1]" in pc.convert(path, config())


def test_missing_conversion_contract_fails_before_open(tmp_path):
    with pytest.raises(ValueError, match="page_offset.*start_page.*stop_page.*classes.*page_number"):
        pc.convert(tmp_path / "not-opened.pdf", {})


@pytest.mark.parametrize("field", pc.REQUIRED)
def test_conversion_requires_each_explicit_field(tmp_path, field):
    data = config()
    del data[field]
    with pytest.raises(ValueError, match=field):
        pc.convert(tmp_path / "not-opened.pdf", data)


def test_front_page_contract_shared():
    assert pc.find_page("[p.fm-2] Short preface. [p.1] Body.", "Short preface") == "fm-2"
