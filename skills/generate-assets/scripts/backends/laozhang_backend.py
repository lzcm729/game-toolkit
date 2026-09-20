#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""laozhang.ai 极简生图后端 —— generate-assets 的参考实现。

它不是 skill，是一个满足 BACKEND-PROTOCOL.md 的普通 CLI 脚本：
读 batch JSON、逐张生图、把 summary 打到 stdout 末行、按三值退码退出。

刻意不做 image-gen 那套 chain / fallback / preset / manifest —— 那是上游
SDK 的职责。本脚本只求「装了插件就能跑通全流程」。

env:
  LAOZHANG_API_KEY    必需
  LAOZHANG_BASE_URL   可选，缺省 https://api.laozhang.ai
  LAOZHANG_MODEL      可选，缺省 gemini-3.1-flash-image-preview
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SUPPORTED_SCHEMA = 2
DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_BASE_URL = "https://api.laozhang.ai"
DEFAULT_TIMEOUT_S = 180.0
# Gemini native 路径的参考图上限
MAX_REFERENCES = 14


def _generate_one(
    prompt: str,
    *,
    model: str,
    api_key: str,
    base_url: str,
    aspect_ratio: str,
    seed: "int | None",
    reference_paths: list,
    timeout_s: float,
) -> bytes:
    """生成一张图，返回图像字节。Task 5 实现。"""
    raise NotImplementedError


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description="laozhang 极简生图后端")
    ap.add_argument("batch", help="batch JSON 路径")
    ap.add_argument("--output-dir", required=True, help="图片输出目录")
    ap.add_argument("--dry-run", action="store_true", help="只打计划，不请求不写文件")
    ap.add_argument("--force", action="store_true", help="目标文件已存在时仍重新生成")
    args = ap.parse_args(argv)

    try:
        batch = json.loads(Path(args.batch).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[fatal] batch JSON 读不了：{e}", file=sys.stderr)
        return 1

    schema = batch.get("$schema_version")
    if schema != SUPPORTED_SCHEMA:
        print(
            f"[fatal] 不认识的 batch schema_version: {schema!r}"
            f"（本后端支持 {SUPPORTED_SCHEMA}）。上游 generate-assets 可能比本后端新，"
            "升级插件或换 backend: image-gen。",
            file=sys.stderr,
        )
        return 1

    api_key = os.environ.get("LAOZHANG_API_KEY", "").strip()
    if not api_key:
        print(
            "[fatal] 缺 LAOZHANG_API_KEY。到 https://api.laozhang.ai 注册取 key 后设环境变量；"
            "或在 asset-config.yaml 里改用别的 backend。",
            file=sys.stderr,
        )
        return 1

    base_url = os.environ.get("LAOZHANG_BASE_URL") or DEFAULT_BASE_URL
    model = os.environ.get("LAOZHANG_MODEL") or DEFAULT_MODEL

    defaults = batch.get("defaults") or {}
    assets = batch.get("assets") or []
    out_dir = Path(args.output_dir)

    refs = list(defaults.get("reference_paths") or [])
    if len(refs) > MAX_REFERENCES:
        print(
            f"[fatal] reference_paths {len(refs)} 张，超过上限 {MAX_REFERENCES}。",
            file=sys.stderr,
        )
        return 1

    success = failed = skipped = 0
    failed_assets: list = []

    for asset in assets:
        name = asset.get("name") or asset.get("filename") or "?"
        filename = asset.get("filename")
        prompt = asset.get("prompt") or ""
        if not filename:
            print(f"[error] asset {name!r} 缺 filename，跳过", file=sys.stderr)
            failed += 1
            failed_assets.append({"name": name, "error": "缺 filename"})
            continue

        target = out_dir / filename

        if args.dry_run:
            print(f"  [plan] {name} -> {target}")
            continue

        if target.exists() and not args.force:
            print(f"  [skip] {name}（已存在，--force 可覆盖）")
            skipped += 1
            continue

        try:
            data = _generate_one(
                prompt,
                model=model,
                api_key=api_key,
                base_url=base_url,
                aspect_ratio=asset.get("aspect_ratio") or defaults.get("aspect_ratio") or "1:1",
                seed=asset.get("seed", defaults.get("seed")),
                reference_paths=refs,
                timeout_s=DEFAULT_TIMEOUT_S,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            print(f"  [ok] {name} -> {target}")
            success += 1
        except Exception as e:      # 单张失败不中断整批：一张 429 不该毁掉 50 张
            print(f"  [error] {name}: {e}", file=sys.stderr)
            failed += 1
            failed_assets.append({"name": name, "error": str(e)})

    summary = {
        "total": len(assets),
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "failed_assets": failed_assets,
    }
    print(json.dumps(summary, ensure_ascii=False), flush=True)

    if failed == 0:
        return 0
    if success == 0 and skipped == 0:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
