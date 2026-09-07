#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查/写入项目的 `game-toolkit.yaml` —— Game Toolkit 项目环境声明。

    python project_env.py check <项目根>
    python project_env.py write <项目根> --engine unreal --engine-version 5.8 ...

**为什么是独立 YAML 而不是 CLAUDE.md 里的一段**：这份声明既给 agent 读，也给程序
读写。用 Markdown 列表承载就得靠正则去啃，人改一下排版就解析不出来。

**这个脚本不与人交互**，也不该交互 —— 它在 agent 的 Bash 工具里跑，stdin 接的是
空设备，input() 只会拿到 EOF。分工是：

    脚本 check  →  报告缺什么 / 哪里坏了 + 探测出的候选值
    agent       →  用 AskUserQuestion 把候选值交给人确认
    脚本 write  →  把确认后的值写回

探测出来的一律是**候选**，不是结论 —— 引擎和版本要人确认过才算数。

## 写入安全（踩过的坑，别退回去）

`write` 是**读-改-写**：先读现有配置，合并新值，再重渲染整个文件。所以：

1. **文件损坏时必须拒绝写入。** 曾经解析失败就返回空 dict，`write` 把它当「没有
   配置」合并，结果只改一个字段就把其余字段清成占位符、自定义字段全丢。
   现在 `load_config` 区分「文件不存在」和「文件损坏」，后者直接拒写。
2. **值的序列化交给 yaml，不要手拼块标量。** 曾经手拼 `|-`，遇到首行带缩进的值
   会生成解析不回来的 YAML。
3. **null 也是值。** 过滤 `None` 会让 `custom: null` 这种字段在下次写入时消失。
4. **写完要重新解析验证，再原子替换。** 免得写出一个自己都读不回来的文件。
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 pyyaml：pip install pyyaml", file=sys.stderr)
    raise

CONFIG_NAME = "game-toolkit.yaml"

FIELDS = [
    ("engine", "引擎：godot / unreal / unity / 自研 / 无（纯文档项目）。人工填，不探测", True),
    ("engine_version", "引擎版本：写成字符串（5.10 不加引号会被 YAML 读成 5.1）。不知道就写「待核实」", True),
    ("project_root", "工程根：相对本文件的路径。仓库根 != 工程根时尤其要写", True),
    ("tech_stack", "技术栈：语言与框架", False),
    ("source_scope", "源码范围：目录与排除项；写目录和排除规则，别写会过期的文件计数", False),
    ("inspectability", "可检查程度：按「检查动作」分档，不要只按扩展名一刀切", False),
    ("verify_entry", "验证入口：构建/测试/导出检查怎么跑。同一引擎不同项目可以完全不同", False),
    ("asset_config", "资源配置：asset-config.yaml 的位置", False),
]
KEYS = [k for k, _, _ in FIELDS]
REQUIRED = [k for k, _, req in FIELDS if req]
PLACEHOLDERS = ("待核实", "未知", "TBD", "tbd", "?", "")

HEADER = """# Game Toolkit 项目环境声明
#
# 由人填写，不由工具探测 —— 探测认得出 .uproject，认不出「这个仓库里哪个才是
# 本次要动的工程」「哪个大版本」「Blueprint 能不能按文本扫」。
#
# 三种「没有」必须分开写，不要混成一句「不支持」：
#   未知   —— 还没查，可能有
#   不适用 —— 这个项目结构上就没这一项
#   查不了 —— 有，但当前手段验证不了（如 Blueprint 图逻辑），**不得当作「未实现」**
#
# 字段含义见 game-toolkit 的 layer-contracts skill。
"""


def config_path(root: Path) -> Path:
    return root / CONFIG_NAME


def _is_blank(v) -> bool:
    """None、空串、占位值都算「没填」。str(None) 是 'None'，不在占位表里 —— 踩过：
    三个必填项都写成 null，check 报 ok，write 再崩。"""
    return v is None or str(v).strip() in PLACEHOLDERS


def _has_cycle(obj, _stack=None) -> bool:
    """`x: &c [*c]` 是合法 YAML，读进来是自引用结构；json 化和写后比对都会递归爆栈。"""
    if not isinstance(obj, (dict, list)):
        return False
    stack = _stack or set()
    if id(obj) in stack:
        return True
    stack.add(id(obj))
    items = obj.values() if isinstance(obj, dict) else obj
    hit = any(_has_cycle(x, stack) for x in items)
    stack.discard(id(obj))
    return hit


def load_config(root: Path):
    """读配置。返回 (data, error)。

    三种结果必须分开，混在一起会导致 write 把损坏的文件当空配置覆盖掉：
      (None, None)   文件不存在
      (None, "...")  文件存在但读不了（语法错 / 顶层不是映射）
      (dict, None)   正常
    """
    p = config_path(root)
    if not p.exists():
        return None, None
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8", errors="replace"))
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = " 第 %d 行第 %d 列" % (mark.line + 1, mark.column + 1) if mark else ""
        return None, "YAML 解析失败%s：%s" % (where, getattr(exc, "problem", exc))
    if data is None:
        return {}, None
    if not isinstance(data, dict):
        return None, "顶层不是键值映射（读到 %s），无法作为配置使用" % type(data).__name__
    if _has_cycle(data):
        return None, "YAML 里有循环引用（anchor 引用了自己），无法作为配置使用"
    return data, None


def validate(data: dict) -> list:
    """字段类型校验。返回问题列表；空表示通过。

    `check` 报 ok 却让 `engine: []` 或 `engine_version: false` 过关，等于什么也没保证。
    """
    issues = []
    for key in KEYS:
        if key not in data:
            continue
        v = data[key]
        if v is None:
            continue
        if key == "engine_version" and isinstance(v, (int, float)) and not isinstance(v, bool):
            issues.append("engine_version 是数字 %r —— YAML 会把 5.10 读成 5.1，"
                          "请加引号写成字符串" % v)
        elif not isinstance(v, str):
            issues.append("%s 应为字符串，实际是 %s（%r）" % (key, type(v).__name__, v))
        elif key in REQUIRED and not v.strip():
            issues.append("%s 是空字符串" % key)
    return issues


def detect(root: Path, scope: Path | None = None) -> dict:
    """探测候选值。每项都带依据，方便人判断该不该采信。

    scope 给出时在该目录下探测（对应声明里的 project_root）——
    配置文件所在目录不一定就是工程根。
    """
    base = scope or root
    found: dict = {"evidence": [], "scanned": str(base)}
    if not base.is_dir():
        found["evidence"].append("探测目录不存在：%s" % base)
        return found

    engines = []

    uprojects = sorted(base.glob("*.uproject"))
    for up in uprojects:
        item = {"engine": "unreal", "file": up.name}
        try:
            data = json.loads(up.read_text(encoding="utf-8", errors="replace"))
            assoc = str(data.get("EngineAssociation", "")).strip()
            if re.fullmatch(r"\d+\.\d+(\.\d+)?", assoc):
                item["engine_version"] = assoc
            elif assoc:
                item["note"] = ("EngineAssociation = %s 不是版本号，"
                                "可能是源码版引擎标识，需人工确认" % assoc)
            mods = [m.get("Name") for m in data.get("Modules", []) if m.get("Name")]
            if mods:
                item["modules"] = mods
        except Exception as exc:
            item["note"] = "读取失败：%s" % exc
        engines.append(item)

    godot = base / "project.godot"
    if godot.exists():
        item = {"engine": "godot", "file": "project.godot"}
        m = re.search(r'config/features\s*=\s*PackedStringArray\("([\d.]+)"',
                      godot.read_text(encoding="utf-8", errors="replace"))
        if m:
            item["engine_version"] = m.group(1)
        engines.append(item)

    unity_pv = base / "ProjectSettings" / "ProjectVersion.txt"
    if (base / "Assets").is_dir() and unity_pv.exists():
        item = {"engine": "unity", "file": "ProjectSettings/ProjectVersion.txt"}
        m = re.search(r"m_EditorVersion:\s*(\S+)",
                      unity_pv.read_text(encoding="utf-8", errors="replace"))
        if m:
            item["engine_version"] = m.group(1)
        engines.append(item)

    if engines:
        found["candidates"] = engines
        kinds = sorted({e["engine"] for e in engines})
        if len(engines) == 1:
            found["engine"] = engines[0]["engine"]
            if "engine_version" in engines[0]:
                found["engine_version"] = engines[0]["engine_version"]
        else:
            found["evidence"].append(
                "找到 %d 个工程标志（%s）—— 哪个是本次要动的、用哪个版本，需人工指定；"
                "不给出单一候选" % (len(engines), " / ".join(kinds)))
        for e in engines:
            bits = [e["file"], e["engine"]]
            if e.get("engine_version"):
                bits.append("v" + e["engine_version"])
            if e.get("modules"):
                bits.append("模块 " + ", ".join(e["modules"]))
            if e.get("note"):
                bits.append(e["note"])
            found["evidence"].append(" | ".join(bits))

    slns = sorted(base.glob("*.sln"))
    if slns and any(e["engine"] == "unreal" for e in engines):
        found["evidence"].append(
            "存在 %s —— UE 会自动生成 .sln，不能据此推断 dotnet build"
            % ", ".join(p.name for p in slns))

    # 文件计数只作现场参考，不建议写进声明（会过期，且含生成物与第三方代码）
    counts, generated = {}, {}
    noise = ("Intermediate", "Saved", "Binaries", "DerivedDataCache", "Build", ".git")
    for ext in (".cpp", ".h", ".cs", ".gd", ".tscn", ".uasset", ".umap", ".prefab", ".unity"):
        for f in base.rglob("*" + ext):
            rel = f.relative_to(base).parts
            bucket = generated if (rel and rel[0] in noise) else counts
            bucket[ext] = bucket.get(ext, 0) + 1
    if counts:
        found["source_counts"] = counts
        # 分两档，别一刀切成「都读不懂」：.tscn / .prefab / .unity 是文本序列化，
        # 能读出节点、属性和引用；.uasset / .umap 才是真的打不开。
        # 两者都不能证明运行行为 —— 但「读不出结构」和「读得出结构但证明不了行为」
        # 是不同的检查边界，混成一句会白白挡掉本可以做的检查。
        binary = {e: n for e, n in counts.items() if e in (".uasset", ".umap")}
        textual = {e: n for e, n in counts.items() if e in (".tscn", ".prefab", ".unity")}
        hints = []
        if binary:
            hints.append("二进制资产 %s —— 能 Glob 到但内容读不懂，属「查不了」，"
                         "不得据文本扫描结果判定功能缺失"
                         % ", ".join("%s x%d" % kv for kv in sorted(binary.items())))
        if textual:
            hints.append("文本序列化资产 %s —— 可读节点/属性/引用，但读得出结构"
                         "不等于能证明运行行为；按检查动作分档，别整体归为「查不了」"
                         % ", ".join("%s x%d" % kv for kv in sorted(textual.items())))
        if hints:
            found["inspectability_hint"] = "；".join(hints)
        if generated:
            found["generated_or_ignored"] = generated
            found["evidence"].append(
                "另有 %s 位于 %s 等生成/备份目录，已单列 —— 别把它们算进正式范围"
                % (", ".join("%s x%d" % kv for kv in sorted(generated.items())),
                   "/".join(noise[:3])))
        found["evidence"].append(
            "文件计数会随构建变化，写进声明会过期 —— 声明里请写目录与排除规则")

    for name in ("asset-config.yaml", "assets/asset-config.yaml"):
        if (base / name).exists():
            found["asset_config"] = name
            break
    return found


def _json_safe(value):
    """YAML 会把 2026-09-07 读成 date 对象，直接 json.dumps 会崩。"""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (datetime.date, datetime.datetime, datetime.time)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return str(value)


def _field_line(key: str, value) -> str:
    """一个字段的 YAML 文本。交给 yaml 序列化 —— 手拼块标量会在首行带缩进时炸。"""
    return yaml.safe_dump({key: value}, allow_unicode=True,
                          default_flow_style=False, width=10 ** 6).rstrip("\n")


def render(values: dict) -> str:
    """整文件渲染。已知字段按固定顺序带注释输出，未知字段原样留在末尾。"""
    out = [HEADER]
    for key, comment, required in FIELDS:
        if key not in values:
            if not required:
                continue
            values = dict(values, **{key: "待核实"})
        v = values[key]
        if required and (v is None or (isinstance(v, str) and not v.strip())):
            v = "待核实"
        out.append("# %s" % comment)
        out.append(_field_line(key, v))
        out.append("")
    extra = {k: v for k, v in values.items() if k not in KEYS}
    if extra:
        out.append("# ---- 以下字段本工具不认识，原样保留 ----")
        out.append(yaml.safe_dump(extra, allow_unicode=True, default_flow_style=False,
                                  sort_keys=False, width=10 ** 6).rstrip("\n"))
        out.append("")
    return "\n".join(out)


def write_declaration(root: Path, values: dict) -> str:
    """渲染 → 自校验 → 原子替换。写出一个自己都读不回来的文件是不可接受的。"""
    p = config_path(root)
    text = render(values)
    back = yaml.safe_load(text)
    for k, v in values.items():
        if k in back and back[k] != v and not (v is None and back[k] is None):
            raise RuntimeError("渲染后 %r 的值变了（%r → %r），拒绝写入" % (k, v, back[k]))
    existed = p.exists()
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".game-toolkit-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.replace(tmp, str(p))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return "%s %s" % ("更新" if existed else "新建", p)


def _major_minor(v: str) -> str:
    """5.8.1 -> 5.8。声明写 5.8、.uproject 写 5.8.1 不该报成冲突。"""
    parts = str(v).strip().split(".")
    return ".".join(parts[:2])


def compare(declared: dict | None, detected: dict) -> list:
    """声明与探测对不上的地方。**声明为准** —— 那是人工填的，这里只报告，不改。

    探测不到不算冲突：纯文档项目、自研引擎、工程根在别处，都合法。
    只有「探测到了，且和声明对不上」才值得打断人。
    """
    if not declared:
        return []
    candidates = detected.get("candidates") or []
    if not candidates:
        return []

    out = []
    d_engine = str(declared.get("engine", "")).strip()
    if not _is_blank(declared.get("engine")):
        kinds = sorted({c["engine"] for c in candidates})
        if d_engine.lower() not in kinds:
            out.append(
                "声明 engine=%s，但 %s 里找到的是 %s（%s）。"
                "要么声明写错了，要么 project_root 指错了目录。"
                % (d_engine, detected.get("scanned", "工程根"), " / ".join(kinds),
                   ", ".join(c["file"] for c in candidates)))
            return out  # 引擎都对不上，再比版本没有意义

        matched = [c for c in candidates if c["engine"] == d_engine.lower()]
        d_ver = str(declared.get("engine_version", "")).strip()
        if len(matched) == 1 and not _is_blank(declared.get("engine_version")):
            found_ver = matched[0].get("engine_version")
            if found_ver and _major_minor(found_ver) != _major_minor(d_ver):
                out.append(
                    "声明 engine_version=%s，但 %s 里写的是 %s。"
                    "以声明为准，但值得确认一下是不是升过引擎忘了改声明。"
                    % (d_ver, matched[0]["file"], found_ver))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="检查/写入 Game Toolkit 项目环境声明")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="只读检查，输出 JSON")
    c.add_argument("root")

    w = sub.add_parser("write", help="写入声明（值由调用方确认后给出）")
    w.add_argument("root")
    w.add_argument("--force", action="store_true",
                   help="配置损坏时仍然覆盖（会丢掉原文件内容，默认拒绝）")
    for key, comment, _ in FIELDS:
        w.add_argument("--" + key.replace("_", "-"), default=None, help=comment)

    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"error": "目录不存在: %s" % root}, ensure_ascii=False))
        return 2

    declared, err = load_config(root)

    if args.cmd == "check":
        issues = validate(declared) if declared else []
        scope = None
        if declared and isinstance(declared.get("project_root"), str) \
                and not _is_blank(declared["project_root"]):
            cand = (root / declared["project_root"]).resolve()
            if cand.is_dir():
                scope = cand
            else:
                # 静默退回配置所在目录会让探测看错地方，再报一个错误的「直接用」
                issues.append("project_root 指向的目录不存在：%s" % cand)
        if err:
            status = "invalid"
        elif declared is None:
            status = "missing"
        elif issues:
            status = "invalid"
        else:
            missing = [k for k in REQUIRED if _is_blank(declared.get(k))]
            status = "ok" if not missing else "incomplete"
        # 没有声明 = 三个必填项都缺。返回空列表会让调用方以为没什么要问的。
        missing = (list(REQUIRED) if declared is None else
                   [k for k in REQUIRED if _is_blank(declared.get(k))])
        detected = detect(root, scope)
        conflicts = compare(declared, detected)
        nxt = {
            "missing": "没有声明。把 detected 当候选值交给用户确认（AskUserQuestion），再 write 写回。",
            "invalid": "配置损坏或字段类型不对，**先让用户修**。不要直接 write —— 那会覆盖掉原文件。",
            "incomplete": "缺必填项。把 detected 当候选值交给用户确认，再 write 写回。",
            "ok": "声明齐全，直接用。",
        }[status]
        if conflicts:
            nxt = ("声明与工程里探测到的对不上（见 conflicts）。**以声明为准** —— "
                   "那是人工填的。但先把冲突报给用户：是声明过期了，"
                   "还是 project_root 指到了别的目录？确认前别拿它当准确前提往下推。")
        print(json.dumps({
            "status": status,
            "config": str(config_path(root)),
            "config_exists": config_path(root).exists(),
            "error": err,
            "issues": issues,
            "declared": _json_safe(declared or {}),
            "detected": _json_safe(detected),
            "conflicts": conflicts,
            "missing_required": missing,
            "next": nxt,
        }, ensure_ascii=False, indent=2))
        return 0 if status in ("ok", "incomplete", "missing") else 1

    if err and not args.force:
        print("拒绝写入：%s\n"
              "现有文件读不回来，直接覆盖会丢掉里面的内容。请先修好，或加 --force 明确覆盖。"
              % err, file=sys.stderr)
        return 1

    given = {k: getattr(args, k) for k in KEYS}
    if not any(v is not None for v in given.values()):
        print("write 至少要给一个字段", file=sys.stderr)
        return 2
    merged = dict(declared or {})
    merged.update({k: v for k, v in given.items() if v is not None})
    # 必填项写了键没写值（null）：渲染层会填「待核实」，自检发现 None → '待核实'
    # 对不上就拒绝。先统一成占位值，下次 check 报 incomplete 去催填。
    for k in REQUIRED:
        if merged.get(k) is None:
            merged[k] = "待核实"
    # 只改一个字段也是整文件重渲染：没动的字段按 YAML 读到的值写回去。
    # engine_version: 5.10 没加引号，读进来是浮点 5.1，写回去就成了 5.1 ——
    # check 早就会报这条，但 write 曾经照写不误。凡 validate 不过的一律拒绝，
    # 除非本次 write 把那个字段一起改了（命令行来的值是字符串，自然就修好了）。
    issues = validate(merged)
    if issues and not args.force:
        print("拒绝写入，重渲染会把这些值改掉：\n  - %s\n"
              "把出问题的字段在本次 write 里一起给出（如 --engine-version 5.10），"
              "或先手工加引号，或加 --force 接受改动。" % "\n  - ".join(issues),
              file=sys.stderr)
        return 1
    print(write_declaration(root, merged))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
