#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 裁决单.json 校验后注入模板，生成单文件 裁决单.html。

    python build_page.py <裁决单.json> [--out <裁决单.html>] [--template <template.html>] [--root <仓库根>]

校验不过就不出页（退出码 1），错误逐条打到 stderr；只是提醒的（标题、ctx 里疑似代码名、
引文对不上原文）照出页、退出码 0。默认输出与输入同目录同名 .html。生成的页面不依赖网络，浏览器直接打开。

引文核对：quotes 的出处里认得出仓库文件（`物品规则.md:42`、`README.md 第 94 行`）就去那个文件里
逐字找原文，比对时忽略空白、全角半角和 Markdown 标记，原文里的「……」按分段找。找不到、行号对不上、
同名文件不止一个，都只提醒；认不出文件的出处（飞书账本、评审意见）不核，只计数。
仓库根默认取裁决单所在的 git 仓库，--root 可以改。

裁决单.json 的形状见 ../examples/裁决单.example.json；字段含义见 SKILL.md「写题」。
"""
from __future__ import annotations

import argparse
import bisect
import csv
import difflib
import hashlib
import html
import io
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_TEMPLATE = HERE.parent / "template.html"
DATA_BEGIN = "/* DATA-BEGIN */"
DATA_END = "/* DATA-END */"

DATE = re.compile(r"^\d{4}-\d{2}-\d{2}[a-z]?$")
OPT_KEY = re.compile(r"^[A-Z][A-Z0-9]*$")
# ruling＝裁决题，恰好一个倾向；confirmation＝确认题，问属主才知道的事实，不设倾向、不入账
KINDS = ("ruling", "confirmation")
# 代码名只该进 refs：类名::方法、带扩展名的文件、CamelCase、snake_case
CODE_NAME = re.compile(r"::|\b\w+\.(?:cpp|hpp|h|cs|gd|py|ts|js|json|yaml|ini)\b"
                       r"|\b[A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+\b|\b[a-z]+_[a-z0-9_]+\b")


def storage_key(page: dict) -> str:
    """本浏览器兜底存储的键。file:// 下所有本地页共用一个 origin，所以要按页区分。"""
    digest = hashlib.sha1(("%s\n%s" % (page.get("title", ""), page.get("eyebrow", ""))).encode("utf-8")).hexdigest()
    return "rulings-%s-%s" % (page.get("date", ""), digest[:8])


def _is_str(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def validate(data: dict) -> "tuple[list, list]":
    """返回 (errors, warnings)。errors 非空就不该出页。"""
    errors, warnings = [], []
    page = data.get("page")
    if not isinstance(page, dict):
        return ["缺 page 块"], warnings
    if not _is_str(page.get("title")):
        errors.append("page.title 要有")
    if not _is_str(page.get("date")) or not DATE.match(page["date"]):
        errors.append("page.date 要是 YYYY-MM-DD（同一天第二张单加字母后缀，如 2026-09-22b）")
    if not isinstance(page.get("intro", []), list) or not all(isinstance(x, str) for x in page.get("intro", [])):
        errors.append("page.intro 要是字符串列表")
    if not isinstance(page.get("status", ""), str):
        errors.append("page.status 要是字符串：落地后写提交号与账本条目号，没落地留空")

    groups = data.get("groups")
    if not isinstance(groups, list) or not groups:
        errors.append("groups 至少一组")
        groups = []
    seen = {}
    for gi, g in enumerate(groups):
        where = "groups[%d]" % gi
        if not isinstance(g, dict):
            errors.append("%s 要是 mapping" % where)
            continue
        if not _is_str(g.get("id")) or not _is_str(g.get("title")):
            errors.append("%s 要有 id 和 title" % where)
        items = g.get("items")
        if not isinstance(items, list) or not items:
            errors.append("%s 至少一题" % where)
            continue
        for ii, d in enumerate(items):
            w = "%s.items[%d]" % (where, ii)
            if not isinstance(d, dict):
                errors.append("%s 要是 mapping" % w)
                continue
            did = d.get("id")
            if not _is_str(did):
                errors.append("%s 缺 id" % w)
            elif did in seen:
                errors.append("题 id 重复：%s（%s 和 %s）" % (did, seen[did], w))
            else:
                seen[did] = w
            label = did if _is_str(did) else w
            if not _is_str(d.get("title")):
                errors.append("%s 缺 title" % label)
            if not _is_str(d.get("ctx")):
                errors.append("%s 缺 ctx：读者没看过代码，要写现在是什么样、为什么要拍" % label)
            for field in ("refs", "facts"):
                v = d.get(field, [])
                if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                    errors.append("%s.%s 要是字符串列表" % (label, field))
            quotes = d.get("quotes", [])
            if not isinstance(quotes, list) or not all(
                    isinstance(q, list) and len(q) == 2 and all(isinstance(x, str) for x in q) for q in quotes):
                errors.append("%s.quotes 要是 [[出处, 原文], …]" % label)
            kind = d.get("kind", "ruling")
            if kind not in KINDS:
                errors.append("%s.kind 只能是 %s" % (label, " 或 ".join(KINDS)))
                kind = "ruling"
            opts = d.get("opts")
            if not isinstance(opts, list) or not (2 <= len(opts) <= 3):
                errors.append("%s 的选项要 2～3 个" % label)
                opts = []
            keys, recs = [], 0
            for oi, o in enumerate(opts):
                if not isinstance(o, list) or not (3 <= len(o) <= 4) or not all(isinstance(x, str) for x in o[:3]):
                    errors.append("%s.opts[%d] 要是 [键, 短标签, 选了会发生什么, 倾向标记?]" % (label, oi))
                    continue
                if not OPT_KEY.match(o[0]):
                    errors.append("%s.opts[%d] 键要是大写字母（A/B/C）" % (label, oi))
                keys.append(o[0])
                if not _is_str(o[1]):
                    errors.append("%s.opts[%d] 短标签不能空" % (label, oi))
                if len(o) == 4 and o[3]:
                    recs += 1
            if len(keys) != len(set(keys)):
                errors.append("%s 的选项键重复" % label)
            if opts and kind == "confirmation" and recs:
                errors.append("%s 确认题不设倾向（现在 %d 个）：问的是事实，填了倾向就替属主答了" % (label, recs))
            elif opts and kind == "ruling" and recs != 1:
                errors.append("%s 要恰好一个倾向（现在 %d 个）：只给选项不给倾向，用户没法比" % (label, recs))
            need = d.get("note_required", [])
            if not isinstance(need, list) or not all(isinstance(x, str) for x in need):
                errors.append("%s.note_required 要是选项键列表" % label)
            else:
                for k in need:
                    if k not in keys:
                        errors.append("%s.note_required 里的 %s 不是这题的选项键" % (label, k))
            for field in ("title", "ctx"):
                v = d.get(field)
                if isinstance(v, str):
                    m = CODE_NAME.search(v)
                    if m:
                        warnings.append("%s.%s 里疑似代码名「%s」：代码名进 refs，正文写玩家看得到的行为"
                                        % (label, field, m.group(0)))

    outside = data.get("outside", [])
    if not isinstance(outside, list):
        errors.append("outside 要是 [[组名, [行, …]], …]")
    else:
        # 组名按去向起：默认六个见 SKILL.md「写题」，项目的去向不同就用项目的说法，这里不限定。
        names = set()
        for oi, entry in enumerate(outside):
            if not (isinstance(entry, list) and len(entry) == 2 and isinstance(entry[0], str)
                    and isinstance(entry[1], list) and all(isinstance(x, str) for x in entry[1])):
                errors.append("outside[%d] 要是 [组名, [行, …]]" % oi)
                continue
            name = entry[0].strip()
            if not name:
                errors.append("outside[%d] 组名不能空" % oi)
            elif name in names:
                errors.append("outside[%d] 组名「%s」重复：同一个去向并成一组" % (oi, name))
            names.add(name)
            if not any(x.strip() for x in entry[1]):
                errors.append("outside[%d]「%s」没有内容就删掉这一组" % (oi, entry[0]))
    return errors, warnings


# ---- 引文核对：出处认得出仓库文件，就去文件里逐字找原文 ----
QUOTE_EXT = "md|csv|txt|json|yaml|yml|ini|toml|py|h|hpp|cpp|cs|gd|ts|js"
# 扩展名后面不能再跟文件名字符，也不能是「.backup.md」这种多重扩展名的中段
_EXT_END = re.compile(r"\.(?:%s)(?![A-Za-z0-9]|\.[A-Za-z0-9])" % QUOTE_EXT, re.I)
_EXT_TAIL = re.compile(r"\.(?:%s)$" % QUOTE_EXT, re.I)
# 紧跟路径的行号「:86」「:25-26」，路径和冒号之间可以夹收尾的引号或一个括注（「`a.md`:4」「CLAUDE.md（工程根）:25」）
_LINE_COLON = re.compile(r"[`'\"’”」』]?\s*(?:（[^）]*）|\([^)]*\))?\s*[:：]\s*(\d+)(?:\s*[-–~～至]\s*(\d+))?")
# 路径之后任意位置的「第 94 行」「第 25～26 行」；「第 3 节」不是行号
_LINE_WORD = re.compile(r"第\s*(\d+)(?:\s*[-–~～至]\s*(\d+))?\s*行")
_ELLIPSIS = re.compile(r"\.{3,}")  # 统一宽度之后「……」「．．．」都成了三个以上的点
_MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
# 文件侧的粗体记号：两边不同时挨着英文字母或数字的 **。按行判断，跨行的粗体也去得掉；「2**3」里的不动
_MD_BOLD = re.compile(r"(?<![A-Za-z0-9])\*\*|\*\*(?![A-Za-z0-9])")
_STAR_MARK = ""  # 转义的 \* 先换成它，躲过粗体处理，最后还原成字面的 *
_MD_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!~|>])")
_BLOCK_PREFIX = re.compile(r"^\s*(?:>\s*)*(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s+)?")
_VERSION_ROW = re.compile(r"^\s*\|\s*v\d")
_VERSION_HEADING = re.compile(r"^#+\s*版本(?:历史|记录)\s*$")
# 文件名前面允许出现的字符：开头、空白、常见标点、路径分隔符、反引号
_BOUNDARY = set(" \t，,。；;：:、「」『』（）()[]【】《》<>\"'“”‘’/`")
csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))


def _norm(text: str, markup: bool = False) -> str:
    """比对用的规范形：全角转半角，链接只留文字，去掉反引号、转义用的反斜杠和所有空白。
    markup=True 是 Markdown 文件那一侧，另外去掉粗体记号；引文是渲染后的文字，里面的 ** 按字面比。
    单个星号、下划线是字面字符，留着（「2*3」「P_base」）。"""
    t = _MD_LINK.sub(r"\1", unicodedata.normalize("NFKC", text))
    if markup:
        t = _MD_BOLD.sub("", t.replace("\\*", _STAR_MARK)).replace(_STAR_MARK, "\\*")
    return re.sub(r"\s", "", _MD_ESCAPE.sub(r"\1", t.replace("`", "")))


def _fragments(text: str) -> "list[str]":
    """原文按省略号分段：每行先去掉行首的引用、列表、标题记号（和文件侧一样），再统一宽度，
    「……」「．．．」都算省略号；每段规范化，单字段也留着。"""
    text = "\n".join(_BLOCK_PREFIX.sub("", ln) for ln in text.splitlines())
    return [f for f in map(_norm, _ELLIPSIS.split(unicodedata.normalize("NFKC", text))) if f]


def repo_root(start: Path) -> "Path | None":
    try:
        out = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, encoding="utf-8", timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    top = out.stdout.strip()
    return Path(top) if out.returncode == 0 and top else None


def list_text_files(root: Path) -> "list[str]":
    """root 下的文本文件，相对路径、/ 分隔。git 仓库用 ls-files（含未跟踪、不含忽略的），否则遍历目录。"""
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],
                             capture_output=True, timeout=120)
        if out.returncode == 0:
            return [n for n in out.stdout.decode("utf-8", "replace").split("\0") if n and _EXT_TAIL.search(n)]
    except (OSError, subprocess.SubprocessError):
        pass
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "node_modules"]
        files += [Path(dirpath, f).relative_to(root).as_posix() for f in filenames if _EXT_TAIL.search(f)]
    return files


def _suffix(head: str, rel: str) -> "tuple[int, bool]":
    """head 以 rel 的哪一段后缀结尾（按 / 切，取最长的），返回 (长度, 是否整条路径)。对不上返回 (0, False)。"""
    parts = rel.split("/")
    for i in range(len(parts)):
        suf = "/".join(parts[i:])
        j = len(head) - len(suf)
        if head.endswith(suf) and (j == 0 or head[j - 1] in _BOUNDARY):
            return len(suf), i == 0
    return 0, False


def _line_range(src: str, pos: int) -> "tuple | None":
    """pos 处那个文件的行号。「第 N 行」只在下一个文件名之前找，不借后面「参考 b.md 第 99 行」的行号。"""
    nxt = _EXT_END.search(src, pos)
    stop = len(src)
    if nxt:
        stop = nxt.start()
        while stop > pos and src[stop - 1] not in _BOUNDARY:
            stop -= 1
    m = _LINE_COLON.match(src, pos) or _LINE_WORD.search(src, pos, stop)
    return (int(m.group(1)), int(m.group(2) or m.group(1))) if m else None


def resolve_source(src: str, by_name: dict) -> "tuple[str | None, object, tuple | None]":
    """出处 → (状态, 结果, 行号范围)。只认出处里第一个写到的文件，后面「参考 X」之类的不算。
    'file'：结果是相对路径。'multi'：同名文件不止一个，出处写的部分分不开，结果是候选列表。
    'missing'：结果是出处里写的那段路径。None：出处里没有文件（飞书、评审意见之类），不核。"""
    src = src.replace("\\", "/")
    m = _EXT_END.search(src)
    if not m:
        return None, None, None
    head, lines = src[:m.end()], _line_range(src, m.end())
    name_at = m.start()
    while name_at > 0 and src[name_at - 1] not in _BOUNDARY:
        name_at -= 1
    start = name_at
    while start > 0 and (src[start - 1] == "/" or src[start - 1] not in _BOUNDARY):
        start -= 1
    written = src[start:m.end()]
    best, cands = 0, []
    for name, rels in by_name.items():
        if head.endswith(name):
            for rel in rels:
                n, full = _suffix(head, rel)
                if n > best:
                    best, cands = n, [(rel, full)]
                elif n and n == best:
                    cands.append((rel, full))
    # 对上的那段前面紧挨着「/」，说明写下的路径还有更上层的目录没对上：写的目录不对，不能拿同名文件顶替
    if not cands or (len(head) > best and head[len(head) - best - 1] == "/"):
        return "missing", written, lines
    exact = [rel for rel, full in cands if full]
    if len(cands) == 1 or len(exact) == 1:
        return "file", (exact[0] if len(exact) == 1 else cands[0][0]), lines
    return "multi", sorted(rel for rel, _ in cands), lines


def _view(path: Path) -> dict:
    """一个文件的核对视图。units：给人看的行（CSV 是表格行）；numbers：出处里该写的行号；
    starts：每行在规范形里的起点；flat：整篇规范形；version：是不是版本记录行；error：读不了的原因。"""
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except FileNotFoundError:
        return {"error": "文件在 git 索引里，工作区里已经没有了"}
    except UnicodeDecodeError:
        return {"error": "不是 UTF-8 编码"}
    except OSError as exc:
        return {"error": "读不了（%s）" % (exc.strerror or exc)}
    units, norms, version, note = [], [], [], ""
    if path.suffix.lower() == ".csv":
        try:
            for row in csv.reader(io.StringIO(text, newline="")):
                units.append(" | ".join(row))
                norms.append("".join(_norm(c) + "\x1f" for c in row))  # \x1f 隔开单元格，原文不跨格
                version.append(False)
        except csv.Error as exc:
            units, norms, version, note = [], [], [], "（这个 CSV 解析不了：%s，按文件行号）" % exc
    if not units:
        after = False
        for ln in text.splitlines():
            after = after or bool(_VERSION_HEADING.match(ln))
            units.append(ln)
            norms.append(_norm(_BLOCK_PREFIX.sub("", ln), markup=True))
            version.append(after or bool(_VERSION_ROW.match(ln)))
    starts, pos = [], 0
    for n in norms:
        starts.append(pos)
        pos += len(n)
    return {"units": units, "norms": norms, "numbers": list(range(1, len(units) + 1)), "starts": starts,
            "flat": "".join(norms), "version": version, "note": note}


def _hits(flat: str, frags: list) -> "list[tuple[int, int]]":
    """各段原文依次出现的位置：每个首段起点给一个 (起点, 末段终点)。先取各段的全部位置再二分，长文件里不退化成平方。"""
    occ = []
    for f in frags:
        found, i = [], flat.find(f)
        while i != -1:
            found.append(i)
            i = flat.find(f, i + 1)
        if not found:
            return []
        occ.append(found)
    out = []
    for s in occ[0]:
        end = s + len(frags[0])
        for f, positions in zip(frags[1:], occ[1:]):
            k = bisect.bisect_left(positions, end)
            if k == len(positions):
                break
            end = positions[k] + len(f)
        else:
            out.append((s, end))
    return out


def _at(view: dict, i: int) -> int:
    return view["numbers"][bisect.bisect_right(view["starts"], i) - 1]


def _closest(view: dict, quote: str, around: "tuple | None") -> "tuple[float, int]":
    """和原文最像的一行：原文有多少按顺序出现在这一行里。先找写的行号附近、再找全篇，版本记录行最后才考虑。"""
    def scan(rng):
        best = (0.0, -1)
        for k in rng:
            if 0 < len(view["norms"][k]) <= 20000:  # 再长就不是一「行」了，逐字比对会很慢
                sm = difflib.SequenceMatcher(None, quote, view["norms"][k], autojunk=False)
                score = sum(b.size for b in sm.get_matching_blocks()) / len(quote)
                if score > best[0]:
                    best = (score, k)
        return best
    every = range(len(view["units"]))
    current = [k for k in every if not view["version"][k]]
    if around:
        near = scan([k for k in current if around[0] - 30 <= view["numbers"][k] <= around[1] + 30])
        if near[0] >= 0.6:
            return near
    best = scan(current)
    return best if best[0] >= 0.6 else scan([k for k in every if view["version"][k]])


def _diff_tip(quote: str, line: str) -> str:
    """原文和最像的那行差在哪：第一处不一样、或者这行在原文中间多出来的地方，两边各带几个字。
    这行在原文前后多出来的字不算差别（原文本来就只是一行的一段）。"""
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, quote, line, autojunk=False).get_opcodes():
        if tag == "equal" or (tag == "insert" and i1 in (0, len(quote))):
            continue
        if tag == "insert":
            return "文件在「%s」后面多了「%s」" % (quote[max(0, i1 - 8):i1], _clip(line[j1:j2], 24))
        return "引文「%s」，文件「%s」" % (quote[max(0, i1 - 6):i2 + 6], line[max(0, j1 - 6):j2 + 6])
    return ""


def _clip(text: str, n: int = 50) -> str:
    text = text.strip()
    return text if len(text) <= n else text[:n] + "…"


def _lines_text(a: int, b: int) -> str:
    return str(a) if a == b else "%d～%d" % (a, b)


def check_quotes(data: dict, root: Path, files: "list[str] | None" = None) -> "tuple[list, dict]":
    """逐条核对 quotes。返回 (提醒, 计数)；计数的键：total、ok、skipped（出处不是仓库文件）、bad。

    出处只写了文件名、仓库里又有同名文件（历史快照、报告副本）时：和本单其他引文落在同一目录、
    或共享两层以上目录的那份算数；分不出来就只提醒写全路径，哪怕某一份里真有这句，因为它可能正是过时的副本。"""
    by_name = {}
    for rel in (list_text_files(root) if files is None else files):
        by_name.setdefault(rel.rsplit("/", 1)[-1], []).append(rel)
    views = {}

    def view(rel):
        if rel not in views:
            views[rel] = _view(root / rel)
        return views[rel]

    entries = []
    for g in data.get("groups", []):
        for d in g.get("items", []):
            for qi, (src, text) in enumerate(d.get("quotes", []), 1):
                entries.append(("%s 引文 %d（%s）" % (d.get("id"), qi, _clip(src, 40)), _fragments(text))
                               + resolve_source(src, by_name))
    anchors = [e[3].split("/")[:-1] for e in entries if e[2] == "file"]

    def pick(cands, frags):
        def near(rel):
            parts = rel.split("/")[:-1]
            return max((len(os.path.commonprefix([parts, a])) for a in anchors), default=0)
        top = max(map(near, cands))
        best = [c for c in cands if near(c) == top]
        if len(best) == 1 and (top >= 2 or best[0].split("/")[:-1] in anchors):
            return best[0], None
        has = [c for c in cands if "flat" in view(c) and _hits(view(c)["flat"], frags)]
        listed = "、".join(cands[:3]) + ("…" if len(cands) > 3 else "")
        if len(has) == 1:
            return None, "对得上 %d 个同名文件，只在 %s 里找到这句，可出处没写到能分开它们的目录：写全路径" % (len(cands), has[0])
        return None, "对得上 %d 个同名文件（%s），出处写全路径才核得了" % (len(cands), listed)

    warnings, count = [], {"total": len(entries), "ok": 0, "skipped": 0, "bad": 0}
    for label, frags, state, found, want in entries:
        if state is None:
            count["skipped"] += 1
            continue
        count["bad"] += 1  # 核对通过时再改回 ok
        if not frags:
            warnings.append("%s：出处是仓库文件，原文却是空的（只有省略号或空白）" % label)
            continue
        if state == "multi":
            found, msg = pick(found, frags)
            if msg:
                warnings.append("%s：%s" % (label, msg))
                continue
        if state == "missing":
            same = by_name.get(found.rsplit("/", 1)[-1], [])
            hint = "（同名文件：%s）" % "、".join(same[:3]) if same else ""
            warnings.append("%s：出处里的「%s」在仓库里找不到%s" % (label, found, hint))
            continue
        v = view(found)
        if "error" in v:
            warnings.append("%s：%s %s，没核" % (label, found, v["error"]))
            continue
        spans = [(_at(v, s), _at(v, e - 1)) for s, e in _hits(v["flat"], frags)]
        if not spans:
            quote = "".join(frags)
            score, k = _closest(v, quote, None if v["note"] else want)
            tip = ""
            if score >= 0.6:
                tip = "；最接近的是第 %d 行%s，差在：%s" % (
                    v["numbers"][k], "（版本记录，原文多半已经改了）" if v["version"][k] else "",
                    _diff_tip(quote, v["norms"][k]) or _clip(v["units"][k]))
            warnings.append("%s：原文在 %s 里找不到%s%s" % (label, found, tip, v["note"]))
            continue
        if want and v["note"]:
            warnings.append("%s：原文在 %s 里对上了，行号没核%s" % (label, found, v["note"]))
            continue
        if want:
            a, b = want
            fits = [s == a for s, _ in spans] if a == b else [a <= s and e <= b for s, e in spans]
            if not any(fits):
                actual = "、".join(_lines_text(s, e) for s, e in spans[:3])
                warnings.append("%s：原文在 %s 第 %s 行，出处写的是第 %s 行" % (label, found, actual, _lines_text(a, b)))
                continue
        count["bad"] -= 1
        count["ok"] += 1
    return warnings, count


def _js(obj) -> str:
    # </script> 出现在字符串里会提前结束脚本块；JSON 允许 \/ 这个转义
    return json.dumps(obj, ensure_ascii=False, indent=1).replace("</", "<\\/")


def render(data: dict, template: str) -> str:
    if DATA_BEGIN not in template or DATA_END not in template:
        raise ValueError("模板里找不到 %s … %s 标记" % (DATA_BEGIN, DATA_END))
    page = dict(data["page"])
    page["storageKey"] = storage_key(page)
    page.setdefault("intro", [])
    page.setdefault("eyebrow", "")
    page.setdefault("status", "")
    block = "const PAGE = %s;\nconst GROUPS = %s;\nconst OUTSIDE = %s;" % (
        _js(page), _js(data["groups"]), _js(data.get("outside", [])))
    head, rest = template.split(DATA_BEGIN, 1)
    _, tail = rest.split(DATA_END, 1)
    out = head + block + tail
    out = re.sub(r"<title>.*?</title>", "<title>%s</title>" % html.escape(page["title"]), out, count=1, flags=re.S)
    return out


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # Windows 控制台默认 GBK，中文路径和提醒会编码失败
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description="裁决单.json → 裁决单.html")
    ap.add_argument("source", help="裁决单.json")
    ap.add_argument("--out", default=None, help="输出 html；默认与输入同目录同名")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    ap.add_argument("--root", default=None, help="引文核对用的仓库根；默认取裁决单所在的 git 仓库")
    args = ap.parse_args(argv)

    src = Path(args.source)
    try:
        data = json.loads(src.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("读不了 %s：%s" % (src, exc), file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print("%s 顶层要是 mapping" % src, file=sys.stderr)
        return 1
    errors, warnings = validate(data)
    for w in warnings:
        print("提醒：" + w, file=sys.stderr)
    if errors:
        print("校验不过，没有出页：\n  - " + "\n  - ".join(errors), file=sys.stderr)
        return 1
    n_quotes = sum(len(d.get("quotes", [])) for g in data["groups"] for d in g["items"])
    root = Path(args.root) if args.root else repo_root(src.resolve().parent)
    if not n_quotes:
        quote_line = ""
    elif root is None:
        quote_line = "引文核对：裁决单不在 git 仓库里，跳过（--root 可以指定仓库根）。"
    else:
        quote_warnings, c = check_quotes(data, root)
        for w in quote_warnings:
            print("提醒：" + w, file=sys.stderr)
        if c["skipped"] == c["total"]:
            quote_line = "引文核对：%d 条出处都不是仓库文件，没核。" % c["total"]
        else:
            quote_line = "引文核对：%d 条，%d 条对上原文，%d 条出处不是仓库文件没核%s。" % (
                c["total"], c["ok"], c["skipped"], "，%d 条有问题（见上方提醒）" % c["bad"] if c["bad"] else "")
    template = Path(args.template).read_text(encoding="utf-8")
    out = Path(args.out) if args.out else src.with_suffix(".html")
    out.write_text(render(data, template), encoding="utf-8")
    n_items = sum(len(g["items"]) for g in data["groups"])
    print("已生成 %s：%d 组 %d 题；不在单上的 %d 组。浏览器直接打开。"
          % (out, len(data["groups"]), n_items, len(data.get("outside", []))))
    if quote_line:
        print(quote_line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
