#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查/写入项目的 `game-toolkit.yaml` —— Game Toolkit 项目环境声明。

    python project_env.py check <项目根>
    python project_env.py write <项目根> --engine unreal --engine-version 5.8 ...

**为什么是独立的 YAML 而不是 CLAUDE.md 里的一段**：这份声明既给 agent 读，也给
程序读（本脚本、以及将来任何需要知道工程根与技术栈的工具）。用 Markdown 列表
承载就得靠正则去啃，人改一下排版就解析不出来了。严格格式换来可靠解析；
agent 侧在 CLAUDE.md 留一行指针即可。

**这个脚本不与人交互**，也不该交互 —— 它在 agent 的 Bash 工具里跑，stdin 接的是
空设备，input() 只会拿到 EOF。分工是：

    脚本 check  →  报告缺什么 + 探测出的候选值
    agent       →  用 AskUserQuestion 把候选值交给人确认
    脚本 write  →  把确认后的值写回 game-toolkit.yaml

探测出来的一律是**候选**，不是结论。引擎和版本要人确认过才算数：
.uproject 的 EngineAssociation 可能是版本号，也可能是源码版引擎的 GUID；
一个仓库里可能有多个工程；哪个才是「本次要动的那个」，文件系统答不了。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("需要 pyyaml：pip install pyyaml", file=sys.stderr)
    raise

CONFIG_NAME = "game-toolkit.yaml"

# (key, 注释, 是否必填)
FIELDS = [
    ("engine", "引擎：godot / unreal / unity / 自研 / 无（纯文档项目）。人工填，不探测", True),
    ("engine_version", "引擎版本：具体版本号；确实不知道写「待核实」，不要留空", True),
    ("project_root", "工程根：相对本文件的路径。仓库根 != 工程根时尤其要写", True),
    ("tech_stack", "技术栈：语言与框架", False),
    ("source_scope", "源码范围：目录与排除项；可写「见 XXX 文档」", False),
    ("inspectability", "可检查程度：哪些能按文本扫、哪些要引擎才能验、哪些当前查不了", False),
    ("verify_entry", "验证入口：构建/测试/导出检查怎么跑。同一引擎不同项目可以完全不同", False),
    ("asset_config", "资源配置：asset-config.yaml 的位置", False),
]
KEYS = [k for k, _, _ in FIELDS]
REQUIRED = [k for k, _, req in FIELDS if req]
COMMENT = {k: c for k, c, _ in FIELDS}
PLACEHOLDERS = ("待核实", "未知", "TBD", "tbd", "?", "")

HEADER = """# Game Toolkit 项目环境声明
#
# 由人填写，不由工具探测 —— 探测认得出 .uproject，认不出「这个仓库里哪个才是
# 本次要动的工程」「哪个大版本」「Blueprint 能不能按文本扫」。
#
# 三种「没有」必须分开写，不要混成一句「不支持」：
#   未知   —— 还没查，可能有
#   不适用 —— 这个项目结构上就没这一项
#   查不了 —— 有，但当前手段验证不了（如 Blueprint 逻辑），**不得当作「未实现」**
#
# 字段含义见 game-toolkit 的 layer-contracts skill。
"""


def config_path(root: Path) -> Path:
    return root / CONFIG_NAME


def parse_declaration(root: Path) -> dict:
    """读已有声明。文件不存在或不是映射则返回 {}。"""
    p = config_path(root)
    if not p.exists():
        return {}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8", errors="replace"))
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if v is not None}


def detect(root: Path) -> dict:
    """探测候选值。每项都带依据，方便人判断该不该采信。"""
    found: dict = {"evidence": []}

    uprojects = sorted(root.glob("*.uproject"))
    godot = root / "project.godot"
    unity_assets = root / "Assets"
    unity_pv = root / "ProjectSettings" / "ProjectVersion.txt"

    if uprojects:
        found["engine"] = "unreal"
        found["evidence"].append(
            "找到 %d 个 .uproject: %s" % (len(uprojects), ", ".join(p.name for p in uprojects)))
        if len(uprojects) > 1:
            found["evidence"].append("多个工程文件 —— 哪个是本次要动的，需人工指定")
        try:
            data = json.loads(uprojects[0].read_text(encoding="utf-8", errors="replace"))
            assoc = str(data.get("EngineAssociation", "")).strip()
            if re.fullmatch(r"\d+\.\d+(\.\d+)?", assoc):
                found["engine_version"] = assoc
                found["evidence"].append("EngineAssociation = %s" % assoc)
            elif assoc:
                found["evidence"].append(
                    "EngineAssociation = %s（不是版本号，可能是源码版引擎标识，需人工确认）" % assoc)
            mods = [m.get("Name") for m in data.get("Modules", []) if m.get("Name")]
            if mods:
                found["evidence"].append("模块: %s" % ", ".join(mods))
        except Exception as exc:
            found["evidence"].append("读 .uproject 失败: %s" % exc)
    elif godot.exists():
        found["engine"] = "godot"
        found["evidence"].append("找到 project.godot")
        m = re.search(r'config/features\s*=\s*PackedStringArray\("([\d.]+)"',
                      godot.read_text(encoding="utf-8", errors="replace"))
        if m:
            found["engine_version"] = m.group(1)
            found["evidence"].append("config/features = %s" % m.group(1))
    elif unity_assets.is_dir() and unity_pv.exists():
        found["engine"] = "unity"
        found["evidence"].append("找到 Assets/ 与 ProjectSettings/ProjectVersion.txt")
        m = re.search(r"m_EditorVersion:\s*(\S+)",
                      unity_pv.read_text(encoding="utf-8", errors="replace"))
        if m:
            found["engine_version"] = m.group(1)

    counts = {}
    for ext in (".cpp", ".h", ".cs", ".gd", ".tscn", ".uasset", ".umap", ".prefab", ".unity"):
        n = sum(1 for _ in root.rglob("*" + ext))
        if n:
            counts[ext] = n
    if counts:
        found["source_counts"] = counts
        opaque = {e: n for e, n in counts.items()
                  if e in (".uasset", ".umap", ".prefab", ".unity", ".tscn")}
        if opaque:
            found["inspectability_hint"] = (
                "二进制/序列化资产 %s —— 能 Glob 到但内容读不懂，属「查不了」，"
                "不得据文本扫描结果判定功能缺失"
                % ", ".join("%s x%d" % (e, n) for e, n in sorted(opaque.items())))

    slns = sorted(root.glob("*.sln"))
    if slns and found.get("engine") == "unreal":
        found["evidence"].append(
            "存在 %s —— UE 会自动生成 .sln，不能据此推断 dotnet build"
            % ", ".join(p.name for p in slns))

    for name in ("asset-config.yaml", "assets/asset-config.yaml"):
        if (root / name).exists():
            found["asset_config"] = name
            break
    return found


def _emit(value) -> str:
    """单值转 YAML 片段（保持多行文本可读）。

    不能直接 safe_dump 一个标量 —— pyyaml 会给纯标量文档补一行 `...`
    （文档结束标记），拼进配置文件就把结构破坏了。包成 dict 再取值部分：
    该加的引号照样加，又不会带上文档标记。
    """
    text = str(value)
    if "\n" in text:
        body = "\n".join("  " + line for line in text.rstrip("\n").split("\n"))
        return "|-\n" + body
    line = yaml.safe_dump({"_": text}, allow_unicode=True,
                          default_flow_style=False, width=10 ** 6).strip()
    return line[len("_:"):].strip()


def render(values: dict) -> str:
    """整文件渲染。已知字段按固定顺序带注释输出，未知字段原样留在末尾。"""
    out = [HEADER]
    for key, comment, required in FIELDS:
        v = values.get(key)
        if v in (None, ""):
            if not required:
                continue
            v = "待核实"
        out.append("# %s" % comment)
        out.append("%s: %s" % (key, _emit(v)))
        out.append("")
    extra = {k: v for k, v in values.items() if k not in KEYS}
    if extra:
        out.append("# ---- 以下字段本工具不认识，原样保留 ----")
        out.append(yaml.safe_dump(extra, allow_unicode=True,
                                  default_flow_style=False, sort_keys=False).rstrip("\n"))
        out.append("")
    return "\n".join(out)


def write_declaration(root: Path, values: dict) -> str:
    p = config_path(root)
    existed = p.exists()
    p.write_text(render(values), encoding="utf-8")
    return "%s %s" % ("更新" if existed else "新建", p)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="检查/写入 Game Toolkit 项目环境声明")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="只读检查，输出 JSON")
    c.add_argument("root")

    w = sub.add_parser("write", help="写入声明（值由调用方确认后给出）")
    w.add_argument("root")
    for key, comment, _ in FIELDS:
        w.add_argument("--" + key.replace("_", "-"), default=None, help=comment)

    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"error": "目录不存在: %s" % root}, ensure_ascii=False))
        return 2

    if args.cmd == "check":
        declared = parse_declaration(root)
        detected = detect(root)
        missing = [k for k in REQUIRED
                   if str(declared.get(k, "")).strip() in PLACEHOLDERS]
        status = "ok" if not missing else ("incomplete" if declared else "missing")
        print(json.dumps({
            "status": status,
            "config": str(config_path(root)),
            "config_exists": config_path(root).exists(),
            "declared": declared,
            "detected": detected,
            "missing_required": missing,
            "next": ("声明齐全，直接用" if status == "ok" else
                     "把 detected 当候选值交给用户确认（AskUserQuestion），再用 write 写回。"
                     "不要替用户拍板引擎与版本。"),
        }, ensure_ascii=False, indent=2))
        return 0

    given = {k: getattr(args, k) for k in KEYS}
    if not any(given.values()):
        print("write 至少要给一个字段", file=sys.stderr)
        return 2
    merged = parse_declaration(root)
    merged.update({k: v for k, v in given.items() if v})
    print(write_declaration(root, merged))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
