#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""发布前自检：确认某个 commit 真的可以打上某个版本的 tag。

    python scripts/verify_release.py --version 3.4.1
    python scripts/verify_release.py --version 3.4.1 --ref HEAD~1

退出码 0 = 可以发；非 0 = 别发。

## 为什么校验 commit 而不是工作区

3.3.0 发生过一次事故：生成 CHANGELOG 的脚本因转义报错退出，但同一条 shell 命令里
的 `git commit && git push` 照跑了，推出去一个版本号仍是上一版、CHANGELOG 缺当版段
的 commit，tag 却打成了新版本。**工作区当时是对的，commit 是错的。**

所以本脚本一律用 `git show <ref>:<path>` 读文件内容，不看工作区 ——
未提交的正确内容不能替一个错误的 commit 背书。
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFESTS = [
    ("`.claude-plugin/plugin.json`", ".claude-plugin/plugin.json", 1),
    ("`.claude-plugin/marketplace.json`", ".claude-plugin/marketplace.json", 2),
]


def git(*args, check=True) -> str:
    """跑 git 并检查退出码 —— 静默忽略失败正是事故的成因。"""
    r = subprocess.run(["git", "-C", str(REPO), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError("git %s 失败（%d）：%s" % (" ".join(args), r.returncode, r.stderr.strip()))
    return r.stdout


def show(ref: str, path: str) -> str:
    return git("show", "%s:%s" % (ref, path))


def versions_in(text: str) -> list:
    return re.findall(r'"version"\s*:\s*"([^"]+)"', text)


def check(ref: str, version: str) -> list:
    """返回问题列表；空表示可以发。"""
    problems = []

    # 1) 三处 manifest 版本 —— 数量也要对，少一处等于漏改
    for label, path, expect_count in MANIFESTS:
        try:
            found = versions_in(show(ref, path))
        except RuntimeError as exc:
            problems.append("%s 在 %s 里读不到：%s" % (label, ref, exc))
            continue
        if len(found) != expect_count:
            problems.append("%s 应有 %d 处 version，实际 %d 处"
                            % (label, expect_count, len(found)))
        bad = [v for v in found if v != version]
        if bad:
            problems.append("%s 的版本是 %s，期望 %s"
                            % (label, "/".join(sorted(set(bad))), version))

    # 2) CHANGELOG 最新正式版本段
    try:
        changelog = show(ref, "CHANGELOG.md")
    except RuntimeError as exc:
        problems.append("CHANGELOG.md 读不到：%s" % exc)
    else:
        heads = re.findall(r"^##\s+(\d+\.\d+\.\d+)\s", changelog, re.M)
        if not heads:
            problems.append("CHANGELOG.md 里找不到任何 `## x.y.z` 段落")
        elif heads[0] != version:
            problems.append("CHANGELOG.md 最新段是 %s，期望 %s（新版本要放在最前面）"
                            % (heads[0], version))

    # 3) tag 冲突 —— 已公开的 tag 默认不动
    tag = "v" + version
    if git("tag", "--list", tag).strip():
        at = git("rev-list", "-n", "1", tag).strip()[:12]
        target = git("rev-list", "-n", "1", ref).strip()[:12]
        if at != target:
            problems.append(
                "%s 已存在且指向 %s，而本次要发的是 %s。**不要移动已推送的 tag** —— "
                "别人本地的 tag、缓存和已安装版本不会跟着变。发一个修正版本。" % (tag, at, target))

    # 4) 工作区状态：不阻断，但要说清楚校验的是哪个快照
    dirty = [l for l in git("status", "--porcelain").splitlines() if l.strip()]
    return problems, dirty


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="发布前自检")
    ap.add_argument("--version", required=True, help="拟发布的版本号，如 3.4.1")
    ap.add_argument("--ref", default="HEAD", help="要校验的 commit，默认 HEAD")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        print("版本号格式应为 x.y.z", file=sys.stderr)
        return 2

    try:
        problems, dirty = check(args.ref, args.version)
    except RuntimeError as exc:
        print("自检无法进行：%s" % exc, file=sys.stderr)
        if "not a git repository" in str(exc):
            print("  本脚本要在插件**源码仓库**里跑 —— 安装缓存（~/.claude/plugins/cache/…）"
                  "不是 git 仓库，没有 commit 可校验。", file=sys.stderr)
        return 2

    sha = git("rev-list", "-n", "1", args.ref).strip()[:12]
    if args.json:
        print(json.dumps({"ref": args.ref, "commit": sha, "version": args.version,
                          "ok": not problems, "problems": problems,
                          "dirty_files": len(dirty)}, ensure_ascii=False, indent=2))
    else:
        print("校验 %s（%s）能否发 v%s" % (args.ref, sha, args.version))
        if dirty:
            print("  注意：工作区有 %d 个改动未提交 —— 本次校验的是 commit 的内容，不是工作区。"
                  % len(dirty))
        if problems:
            print("\n不能发：")
            for p in problems:
                print("  - %s" % p)
        else:
            print("  ✓ 三处 manifest 版本、CHANGELOG 最新段、tag 状态都对得上")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
