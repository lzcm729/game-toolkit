#!/usr/bin/env python3
"""generate-assets: Godot 项目通用 schema-driven asset orchestrator。

读项目 asset-config.yaml → 加载数据源 → 渲染 prompt → 调底层 image-gen SDK 批量生成
→ 输出到 res:// 路径。

CLI:
    python generate_assets.py <category>          # 生成单个 category
    python generate_assets.py all                 # 生成全部 category
    python generate_assets.py list                # 列出 + desc
    python generate_assets.py <cat> --names a,b   # 过滤 id（仅对 inline / json_dict 生效）
    python generate_assets.py --dry-run           # image-gen 走 --dry-run
    python generate_assets.py --force             # 覆盖已存在
    python generate_assets.py --config path.yaml  # 默认 ./assets/asset-config.yaml

退码：沿用 image-gen 的 0/1/2，多 category 取最大。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# 允许包外直接 `python generate_assets.py`：把脚本所在目录加进 sys.path
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from data_source import load_data_source  # noqa: E402
from godot_utils import (  # noqa: E402
    ensure_parent_dirs,
    find_project_root,
    is_godot_project,
    resolve_res_path,
    scan_imports,
    strip_res_prefix,
)
from prompt_render import compose_prompt, evaluate_derived, render_template  # noqa: E402

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - 启动期检测
    yaml = None  # type: ignore[assignment]


DEFAULT_CONFIG_PATHS = [
    Path("asset-config.yaml"),
    Path("assets/asset-config.yaml"),
]

# 上游 image-gen SDK 入口
IMAGE_GEN_SCRIPT_ENV = "IMAGE_GEN_SCRIPT"
DEFAULT_IMAGE_GEN_SCRIPT = Path.home() / ".claude" / "skills" / "image-gen" / "scripts" / "generate_image.py"


# -------------------- 数据结构 --------------------

@dataclass
class CategoryRunResult:
    name: str
    exit_code: int
    summary: dict | None  # image-gen 末行 JSON
    error: str | None = None


# -------------------- 主流程 --------------------

def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if yaml is None:
        print(
            "[fatal] 缺少 PyYAML。请装：pip install pyyaml",
            file=sys.stderr,
        )
        return 1

    config_path = _locate_config(args.config)
    if config_path is None:
        print(
            f"[fatal] 找不到 asset-config.yaml（默认搜索：{[str(p) for p in DEFAULT_CONFIG_PATHS]}）",
            file=sys.stderr,
        )
        return 1

    with config_path.open(encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not isinstance(config, dict):
        print(f"[fatal] config 顶层必须是 dict，实际 {type(config).__name__}", file=sys.stderr)
        return 1

    project_root = _resolve_project_root(config_path, config)
    output_root = _resolve_output_root(config, project_root)
    image_gen_script = _resolve_image_gen()

    # list 命令
    if args.command == "list":
        _cmd_list(config)
        return 0

    # 选择 category
    categories: dict[str, dict] = config.get("categories") or {}
    if not categories:
        print("[fatal] config 中无 categories", file=sys.stderr)
        return 1

    if args.command == "all":
        target_names = list(categories.keys())
    else:
        if args.command not in categories:
            print(
                f"[fatal] 未知 category: {args.command!r}（可用：{', '.join(categories.keys())}）",
                file=sys.stderr,
            )
            return 1
        target_names = [args.command]

    # pre-flight: Godot 项目检测
    if not is_godot_project(project_root):
        print(
            f"[warn] {project_root} 没有 project.godot — 非 Godot 项目，res:// 解析以 yaml 父目录为根",
            file=sys.stderr,
        )

    name_filter = _parse_names(args.names)

    # 跑每个 category
    results: list[CategoryRunResult] = []
    for cat_name in target_names:
        cat_spec = categories[cat_name]
        result = _run_category(
            cat_name=cat_name,
            cat_spec=cat_spec,
            global_style=config.get("style") or {},
            output_root=output_root,
            project_root=project_root,
            image_gen_script=image_gen_script,
            dry_run=args.dry_run,
            force=args.force,
            name_filter=name_filter,
        )
        results.append(result)

    # 汇总 + .import 提示
    overall_code = max((r.exit_code for r in results), default=0)
    _print_summary(results)

    if not args.dry_run and overall_code != 1:
        scan = scan_imports(output_root)
        print(scan.render_hint())

    return overall_code


# -------------------- CLI 解析 --------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_assets",
        description="Godot 通用 schema-driven asset orchestrator",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="list",
        help="category 名 / 'all' / 'list'（默认 'list'）",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="asset-config.yaml 路径（默认 ./asset-config.yaml 或 ./assets/asset-config.yaml）",
    )
    parser.add_argument(
        "--names",
        type=str,
        default=None,
        help="逗号分隔 id 列表，仅对 inline / json_dict 数据源有效",
    )
    parser.add_argument("--dry-run", action="store_true", help="image-gen 走 --dry-run")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的输出文件")
    return parser


def _parse_names(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    parts = [s.strip() for s in raw.split(",") if s.strip()]
    return set(parts) if parts else None


# -------------------- 路径解析 --------------------

def _locate_config(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit if explicit.exists() else None
    cwd = Path.cwd()
    for rel in DEFAULT_CONFIG_PATHS:
        cand = cwd / rel
        if cand.exists():
            return cand
    return None


def _resolve_project_root(config_path: Path, config: dict) -> Path:
    """优先 project.godot 目录；否则 yaml 父目录的父（即 yaml 在 ./assets/foo.yaml 时，根=cwd）。"""
    found = find_project_root(config_path.parent)
    if found is not None:
        return found
    # fallback：yaml 直接父目录
    parent = config_path.parent
    # 习惯上 yaml 放 ./assets/asset-config.yaml，那么 project_root 应是再上一级
    if parent.name == "assets":
        return parent.parent
    return parent


def _resolve_output_root(config: dict, project_root: Path) -> Path:
    raw = config.get("output_root", "assets/art")
    return resolve_res_path(raw, project_root)


def _resolve_image_gen() -> Path:
    env_path = os.environ.get(IMAGE_GEN_SCRIPT_ENV)
    if env_path:
        p = Path(env_path)
        if not p.exists():
            print(
                f"[warn] {IMAGE_GEN_SCRIPT_ENV}={env_path} 指向的脚本不存在，仍尝试调用",
                file=sys.stderr,
            )
        return p
    return DEFAULT_IMAGE_GEN_SCRIPT


# -------------------- list --------------------

def _cmd_list(config: dict) -> None:
    cats = config.get("categories") or {}
    if not cats:
        print("(empty config — 无 categories)")
        return
    print(f"# {len(cats)} categories")
    for name, spec in cats.items():
        desc = spec.get("desc") or "(no desc)"
        ar = spec.get("aspect_ratio") or "1:1"
        ds_type = ((spec.get("data_source") or {}).get("type")) or "?"
        print(f"  - {name:<14} [{ar}, {ds_type}] {desc}")


# -------------------- 跑一个 category --------------------

def _run_category(
    *,
    cat_name: str,
    cat_spec: dict,
    global_style: dict,
    output_root: Path,
    project_root: Path,
    image_gen_script: Path,
    dry_run: bool,
    force: bool,
    name_filter: set[str] | None,
) -> CategoryRunResult:
    print(f"\n=== category: {cat_name} ===")
    try:
        items = load_data_source(cat_spec.get("data_source") or {}, project_root)
    except Exception as e:
        msg = f"data_source 加载失败：{e}"
        print(f"[error] {msg}", file=sys.stderr)
        return CategoryRunResult(name=cat_name, exit_code=1, summary=None, error=msg)

    if name_filter is not None:
        items = [it for it in items if it.get("id") in name_filter]
        if not items:
            print(f"[warn] --names 过滤后无项目可生成")
            return CategoryRunResult(name=cat_name, exit_code=0, summary={"total": 0, "success": 0, "failed": 0, "skipped": 0})

    # 注入 extra_fields 兜底（item 已有的同名字段优先）
    extra_fields = cat_spec.get("extra_fields") or {}
    try:
        items = [_apply_extra_fields(it, extra_fields) for it in items]
    except Exception as e:
        msg = f"extra_fields 注入失败：{e}"
        print(f"[error] {msg}", file=sys.stderr)
        return CategoryRunResult(name=cat_name, exit_code=1, summary=None, error=msg)

    # 构造 batch JSON
    try:
        batch = _build_batch_json(
            cat_name=cat_name,
            cat_spec=cat_spec,
            items=items,
            global_style=global_style,
            output_root=output_root,
        )
    except Exception as e:
        msg = f"batch JSON 构造失败：{e}"
        print(f"[error] {msg}", file=sys.stderr)
        return CategoryRunResult(name=cat_name, exit_code=1, summary=None, error=msg)

    if not batch["assets"]:
        print(f"[info] {cat_name}: 无 asset 可生成（数据源为空？）")
        return CategoryRunResult(name=cat_name, exit_code=0, summary={"total": 0, "success": 0, "failed": 0, "skipped": 0})

    # 解析 output_dir + 预建子目录
    out_subdir = cat_spec.get("output_subdir") or cat_name
    output_dir = (output_root / out_subdir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    asset_paths = [output_dir / a["filename"] for a in batch["assets"]]
    ensure_parent_dirs(asset_paths)

    # 写临时 batch 文件
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=f"_{cat_name}.json",
        delete=False,
        encoding="utf-8",
    ) as tf:
        json.dump(batch, tf, ensure_ascii=False, indent=2)
        batch_path = Path(tf.name)

    print(f"  items: {len(batch['assets'])}, output: {output_dir}")
    print(f"  batch JSON: {batch_path}")

    # 调 image-gen
    cmd = [
        sys.executable,
        str(image_gen_script),
        str(batch_path),
        "--output-dir",
        str(output_dir),
    ]
    if dry_run:
        cmd.append("--dry-run")
    if force:
        cmd.append("--force")

    print(f"  $ {' '.join(cmd)}")
    summary, exit_code, err = _invoke_image_gen(cmd)
    return CategoryRunResult(name=cat_name, exit_code=exit_code, summary=summary, error=err)


def _apply_extra_fields(item: dict, extra_fields: dict) -> dict:
    """extra_fields 是 {field_name: {item_id: value}}，把对应 id 的 value 注入 item（item 已有同名字段优先）。"""
    out = dict(item)
    item_id = item.get("id")
    for field_name, mapping in extra_fields.items():
        if not isinstance(mapping, dict):
            raise ValueError(
                f"extra_fields[{field_name!r}] 必须是 dict，实际 {type(mapping).__name__}"
            )
        if field_name in out:
            continue  # item 自身字段优先
        if item_id in mapping:
            out[field_name] = mapping[item_id]
    return out


# -------------------- batch JSON 构造 --------------------

def _build_batch_json(
    *,
    cat_name: str,
    cat_spec: dict,
    items: list[dict],
    global_style: dict,
    output_root: Path,
) -> dict:
    template = cat_spec.get("prompt_template")
    if not template:
        raise ValueError(f"category {cat_name!r} 缺 prompt_template")

    derived = cat_spec.get("derived_fields")
    skip_global = bool(cat_spec.get("skip_global_style", False))
    global_prefix = (global_style.get("prompt_prefix") or "") if not skip_global else ""
    global_suffix = (global_style.get("prompt_suffix") or "") if not skip_global else ""

    # defaults：把 category-level 字段透传到 image-gen defaults
    defaults: dict[str, Any] = {}
    if "aspect_ratio" in cat_spec:
        defaults["aspect_ratio"] = cat_spec["aspect_ratio"]
    if "seed" in cat_spec:
        defaults["seed"] = cat_spec["seed"]
    if "chain" in cat_spec:
        defaults["chain"] = cat_spec["chain"]
    if "preset" in cat_spec:
        defaults["preset"] = cat_spec["preset"]

    # global style refs（如果设了 reference_paths 且不 skip_global）
    if not skip_global:
        refs = global_style.get("reference_paths") or []
        if refs:
            # ref 也接受 res:// → 解析为绝对路径
            resolved_refs = [
                str(resolve_res_path(r, output_root)) if not Path(r).is_absolute() else r
                for r in refs
            ]
            defaults["reference_paths"] = resolved_refs

    # 还允许 category 自带 reference_paths（覆盖 global 的内容层）
    if "reference_paths" in cat_spec:
        cat_refs = cat_spec["reference_paths"] or []
        defaults["reference_paths"] = [
            str(resolve_res_path(r, output_root)) if not Path(r).is_absolute() else r
            for r in cat_refs
        ]

    assets: list[dict] = []
    for item in items:
        try:
            enriched = evaluate_derived(item, derived)
            rendered = render_template(template, enriched)
            full_prompt = compose_prompt(
                rendered,
                global_prefix=global_prefix,
                global_suffix=global_suffix,
                skip_global=skip_global,
            )
        except Exception as e:
            raise ValueError(
                f"item id={item.get('id')!r} prompt 渲染失败：{e}"
            ) from e

        item_id = item.get("id")
        if not item_id:
            raise ValueError(f"item 缺 id 字段: {item!r}")

        ext = cat_spec.get("output_ext", "png")
        filename = f"{item_id}.{ext}"

        asset: dict[str, Any] = {
            "name": str(item_id),
            "filename": filename,
            "prompt": full_prompt,
        }
        # item-level overrides（优先级最高）
        if "aspect_ratio" in item and "aspect_ratio" not in asset:
            asset["aspect_ratio"] = item["aspect_ratio"]
        if "seed" in item:
            asset["seed"] = item["seed"]

        assets.append(asset)

    batch = {
        "$schema_version": 2,
        "defaults": defaults,
        "assets": assets,
    }
    return batch


# -------------------- image-gen subprocess --------------------

def _invoke_image_gen(cmd: list[str]) -> tuple[dict | None, int, str | None]:
    """跑 image-gen，返回 (summary_json, exit_code, error_msg)。

    image-gen 会把末尾一行 JSON summary 打到 stdout。
    """
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as e:
        return None, 1, f"image-gen 脚本不存在: {e}"
    except Exception as e:
        return None, 1, f"subprocess 异常：{e}"

    # echo image-gen stdout/stderr
    if proc.stdout:
        sys.stdout.write(proc.stdout)
        if not proc.stdout.endswith("\n"):
            sys.stdout.write("\n")
    if proc.stderr:
        sys.stderr.write(proc.stderr)
        if not proc.stderr.endswith("\n"):
            sys.stderr.write("\n")

    summary = _extract_summary(proc.stdout or "")
    return summary, proc.returncode, None


def _extract_summary(stdout: str) -> dict | None:
    """从 stdout 末尾找 JSON summary（image-gen 协议）。"""
    for line in reversed(stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def _print_summary(results: list[CategoryRunResult]) -> None:
    print("\n=== overall summary ===")
    for r in results:
        if r.summary:
            s = r.summary
            print(
                f"  {r.name:<14} exit={r.exit_code} "
                f"total={s.get('total', '?')} "
                f"success={s.get('success', '?')} "
                f"failed={s.get('failed', '?')} "
                f"skipped={s.get('skipped', '?')}"
            )
        elif r.error:
            print(f"  {r.name:<14} exit={r.exit_code} ERROR: {r.error}")
        else:
            print(f"  {r.name:<14} exit={r.exit_code} (no summary)")


if __name__ == "__main__":
    sys.exit(main())
