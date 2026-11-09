"""按字体还原带印刷页码的文本；字体规则必须用原书抽查后再定。"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys

from bookconf import open_workdir, resolve
from page_labels import MARKER, page_value, printed_label


@dataclass
class FontRow:
    font: str
    size: float
    count: int
    sample: str
    pages: list[int]


REQUIRED = ("page_offset", "start_page", "stop_page", "title_min_size", "classes", "page_number", "header_max_y", "para_indent_x", "outline")


def validate_convert(conv):
    missing = [name for name in REQUIRED if name not in conv]
    if missing:
        raise ValueError("book.yaml convert 缺字段: " + ", ".join(missing))
    for name in ("font_contains", "pattern"):
        if name not in conv["page_number"]:
            raise ValueError(f"convert.page_number 缺 {name}")
    for name in ("part_pattern", "chapter_pattern"):
        if name not in conv["outline"]:
            raise ValueError(f"convert.outline 缺 {name}")
    if not isinstance(conv["classes"], list):
        raise ValueError("convert.classes 必须是有序列表，可显式为空")
    if not isinstance(conv["start_page"], int) or conv["start_page"] < 1:
        raise ValueError("convert.start_page 必须是从 1 起的 PDF 页序")
    if conv["stop_page"] is not None and conv["stop_page"] <= conv["start_page"]:
        raise ValueError("convert.stop_page 必须大于 start_page，或为 null")
    for rule in conv["classes"]:
        if not {"kind", "font_contains", "size", "tol"} <= set(rule):
            raise ValueError("convert.classes 每项须写 kind/font_contains/size/tol")


def survey_fonts(pdf: Path) -> list[FontRow]:
    import fitz

    rows = {}
    with fitz.open(pdf) as doc:
        for number, page in enumerate(doc, 1):
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        if not span["text"].strip():
                            continue
                        key = (span["font"], round(span["size"], 1))
                        row = rows.setdefault(key, FontRow(*key, 0, span["text"].strip()[:60], []))
                        row.count += len(span["text"])
                        if not row.pages or row.pages[-1] != number:
                            row.pages.append(number)
    return sorted(rows.values(), key=lambda row: (-row.count, row.font, row.size))


def convert(pdf: Path, conv: dict) -> str:
    validate_convert(conv)
    import fitz

    offset = conv["page_offset"]
    start = conv["start_page"]
    stop = conv["stop_page"]
    classes = conv["classes"]
    for rule in classes:
        if rule["kind"] not in {"h3", "h4", "callout", "vignette", "skip"}:
            raise ValueError(f"未知字体分类: {rule['kind']}")
    numbers = conv["page_number"]
    outline = conv["outline"]
    part_pattern = outline["part_pattern"]
    chapter_pattern = outline["chapter_pattern"]
    out = []
    para = []
    para_kind = None

    def clean(text):
        text = text.replace("\u2002", " ").replace("\u2003", " ").replace("\u00a0", " ").replace("\u00ad", "")
        return re.sub(r"[ \t]+", " ", text)

    def flush():
        nonlocal para, para_kind
        if para:
            body = " ".join(para)
            if para_kind == "callout":
                out.append(f"> **[Callout]** {body}")
            elif para_kind == "vignette":
                out.append(f"> {body}")
            else:
                out.append(body)
            out.append("")
        para = []
        para_kind = None

    def append_line(text):
        text = clean(text).strip()
        if not text:
            return
        if para and re.search(r"[A-Za-z]-$", para[-1]) and re.match(r"^[a-z]", text):
            para[-1] = para[-1][:-1] + text
        else:
            para.append(text)

    def classify(font, size):
        if size >= conv["title_min_size"]:
            return "title"
        for rule in classes:
            if rule["font_contains"] in font and (
                rule.get("size") is None or abs(size - rule["size"]) < rule.get("tol", .2)
            ):
                return rule["kind"]
        return "body"

    with fitz.open(pdf) as doc:
        inserts = {}
        for level, title, page in doc.get_toc():
            title = re.sub(r"\s+", " ", title.replace("|", " ")).strip()
            part = re.match(part_pattern, title) if level == 1 else None
            chapter = re.match(chapter_pattern, title)
            if part:
                heading = f"# Part {part.group(1)}: {part.group(2)}"
            elif chapter:
                heading = f"## Chapter {chapter.group(1)}: {chapter.group(2)}"
            else:
                heading = f"# {title}"
            inserts.setdefault(page, []).append(heading)
        for number, page in enumerate(doc, 1):
            if number < start or (stop is not None and number >= stop):
                continue
            for heading in inserts.get(number, []):
                flush()
                out.extend([heading, ""])
            marker = f"[p.{printed_label(number, offset)}]"
            first_on_page = True
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    spans = [span for span in line["spans"] if span["text"].strip()]
                    if not spans:
                        continue
                    # 同行混排时按文字最多的 span 判字体，保持已采用文本的转换语义。
                    main = max(spans, key=lambda span: len(span["text"].strip()))
                    text = "".join(span["text"] for span in line["spans"])
                    x, y = line["bbox"][:2]
                    kind = classify(main["font"], main["size"])
                    if numbers["font_contains"] in main["font"] and re.fullmatch(numbers["pattern"], text):
                        continue
                    if y < conv["header_max_y"] and kind in ("body", "skip"):
                        continue
                    if kind in ("skip", "title"):
                        continue
                    if kind in ("h3", "h4"):
                        flush()
                        out.extend([("### " if kind == "h3" else "#### ") + clean(text).strip(), ""])
                        continue
                    if para_kind != kind or (kind == "body" and x >= conv["para_indent_x"]):
                        flush()
                        para_kind = kind
                    if first_on_page:
                        para.append(marker)
                        first_on_page = False
                    append_line(text)
            if first_on_page:
                flush()
                out.extend([marker, ""])
    flush()
    return conv.get("header", "") + re.sub(r"\n{3,}", "\n\n", "\n".join(out))


def find_page(source_md: str, phrase: str) -> int | str | None:
    position = source_md.find(phrase)
    if position < 0:
        return None
    markers = list(MARKER.finditer(source_md[:position]))
    if not markers:
        return None
    return page_value(markers[-1].group(1))


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    survey = commands.add_parser("survey")
    survey.add_argument("pdf", type=Path)
    conversion = commands.add_parser("convert")
    conversion.add_argument("workdir", type=Path)
    conversion.add_argument("pdf", type=Path)
    page = commands.add_parser("page")
    page.add_argument("workdir", type=Path)
    page.add_argument("phrase")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "survey":
            for row in survey_fonts(args.pdf):
                print(f"{row.font} {row.size:g}: {row.count}; pages={row.pages}; {row.sample}")
        else:
            cfg = open_workdir(args.workdir)
            source = resolve(cfg, args.workdir, "source")
            if args.command == "convert":
                text = convert(args.pdf, cfg.convert)
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(text, encoding="utf-8", newline="\n")
                print(f"{source.as_posix()}: {len(text)} chars")
            else:
                found = find_page(source.read_text(encoding="utf-8"), args.phrase)
                print(found if found is not None else "NOT FOUND")
                return 0 if found is not None else 1
    except (OSError, ValueError, ImportError) as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
