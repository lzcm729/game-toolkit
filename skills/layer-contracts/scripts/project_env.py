#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查/写入项目的「Game Toolkit 项目环境」声明。

    python project_env.py check <项目根>
    python project_env.py write <项目根> --engine unreal --engine-version 5.8 ...

**这个脚本不与人交互**，也不该交互 —— 它在 agent 的 Bash 工具里跑，stdin 接的是
空设备，input() 只会拿到 EOF。分工是：

    脚本 check  →  报告缺什么 + 探测出的候选值
    agent       →  用 AskUserQuestion 把候选值交给人确认
    脚本 write  →  把确认后的值写回 CLAUDE.md

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

SECTION = "## Game Toolkit 项目环境"

FIELDS = [
    ("engine", "引擎", True),
    ("engine_version", "引擎版本", True),
    ("project_root", "工程根", True),
    ("tech_stack", "技术栈", False),
    ("source_scope", "源码范围", False),
    ("inspectability", "可检查程度", False),
    ("verify_entry", "验证入口", False),
    ("asset_config", "资源配置", False),
]
LABEL = {k: label for k, label, _ in FIELDS}
REQUIRED = [k for k, _, req in FIELDS if req]
PLACEHOLDERS = ("待核实", "未知", "TBD", "tbd", "?")


def _claude_md(root: Path) -> Path:
    return root / "CLAUDE.md"


def parse_declaration(root: Path) -> dict:
    """从 CLAUDE.md 读已有声明；没有该段落则返回空 dict。"""
    p = _claude_md(root)
    if not p.exists():
        return {}
    text = p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    m = re.search(r"^%s\s*$(.*?)(?=^## |\Z)" % re.escape(SECTION), text, re.S | re.M)
    if not m:
        return {}
    out = {}
    for line in m.group(1).split("\n"):
        hit = re.match(r"\s*[-*]\s*([^：:]+)\s*[：:]\s*(.+?)\s*$", line)
        if not hit:
            continue
        label, value = hit.group(1).strip(), hit.group(2).strip()
        for key, lab, _ in FIELDS:
            if label == lab:
                out[key] = value
    return out


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


def render_section(values: dict) -> str:
    lines = [SECTION, ""]
    for key, label, required in FIELDS:
        v = values.get(key)
        if v:
            lines.append("- %s：%s" % (label, v))
        elif required:
            lines.append("- %s：待核实" % label)
    lines.append("")
    return "\n".join(lines)


def write_declaration(root: Path, values: dict) -> str:
    p = _claude_md(root)
    section = render_section(values)
    if p.exists():
        text = p.read_text(encoding="utf-8", errors="replace")
        crlf = "\r\n" in text
        t = text.replace("\r\n", "\n")
        pat = re.compile(r"^%s\s*$.*?(?=^## |\Z)" % re.escape(SECTION), re.S | re.M)
        t, n = pat.subn(section, t, count=1)
        if n == 0:
            t = t.rstrip("\n") + "\n\n" + section
        p.write_text(t.replace("\n", "\r\n") if crlf else t, encoding="utf-8")
        return "%s %s" % ("更新" if n else "追加", p)
    p.write_text("# %s\n\n%s" % (root.name, section), encoding="utf-8")
    return "新建 CLAUDE.md 并写入 %s" % p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="检查/写入 Game Toolkit 项目环境声明")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="只读检查，输出 JSON")
    c.add_argument("root")

    w = sub.add_parser("write", help="写入声明（值由调用方确认后给出）")
    w.add_argument("root")
    for key, label, _ in FIELDS:
        w.add_argument("--" + key.replace("_", "-"), default=None, help=label)

    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(json.dumps({"error": "目录不存在: %s" % root}, ensure_ascii=False))
        return 2

    if args.cmd == "check":
        declared = parse_declaration(root)
        detected = detect(root)
        missing = [k for k in REQUIRED
                   if not declared.get(k) or declared.get(k) in PLACEHOLDERS]
        status = "ok" if not missing else ("incomplete" if declared else "missing")
        print(json.dumps({
            "status": status,
            "claude_md": str(_claude_md(root)),
            "claude_md_exists": _claude_md(root).exists(),
            "declared": declared,
            "detected": detected,
            "missing_required": missing,
            "missing_labels": [LABEL[k] for k in missing],
            "next": ("声明齐全，直接用" if status == "ok" else
                     "把 detected 当候选值交给用户确认（AskUserQuestion），再用 write 写回。"
                     "不要替用户拍板引擎与版本。"),
        }, ensure_ascii=False, indent=2))
        return 0

    values = {k: getattr(args, k) for k, _, _ in FIELDS}
    if not any(values.values()):
        print("write 至少要给一个字段", file=sys.stderr)
        return 2
    merged = parse_declaration(root)
    merged.update({k: v for k, v in values.items() if v})
    print(write_declaration(root, merged))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
