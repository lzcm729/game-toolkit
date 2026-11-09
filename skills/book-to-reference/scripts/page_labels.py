"""转换与摘句共用印刷页标签；前置页不能误当正文整数页。"""
import re

LABEL = r"(?:fm-\d+|\d+)"
MARKER = re.compile(r"\[p\.(" + LABEL + r")\]")


def page_value(label):
    return int(label) if label.isdigit() else label


def printed_label(pdf_page, offset):
    return str(pdf_page - offset) if pdf_page > offset else f"fm-{pdf_page}"


def cited_pages(text):
    pages = set()
    for match in re.finditer(r"pp?\.\s*(" + LABEL + r")(?:\s*[–-]\s*(" + LABEL + r"))?((?:\s*,\s*" + LABEL + r"(?:\s*[–-]\s*" + LABEL + r")?)*)", text):
        spans = [(match[1], match[2])]
        spans += re.findall(r"(" + LABEL + r")(?:\s*[–-]\s*(" + LABEL + r"))?", match[3])
        for first, last in spans:
            last = last or first
            front = first.startswith("fm-")
            if front != last.startswith("fm-"):
                raise ValueError("页码范围不能混合正文页和 fm 前置页")
            begin, end = int(first.removeprefix("fm-")), int(last.removeprefix("fm-"))
            if end < begin:
                raise ValueError("页码范围逆序")
            pages.update(f"fm-{number}" if front else number for number in range(begin, end + 1))
    return frozenset(pages)
