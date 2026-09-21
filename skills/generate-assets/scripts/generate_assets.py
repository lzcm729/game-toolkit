#!/usr/bin/env python3
"""generate-assets: schema-driven asset orchestrator。

职责只有一段：拿到生成计划之后把它落盘、交给后端、汇总结果。

  - 配置的定位与解析（工程根、输出根、适配器、后端）在 asset_context
  - 计划的构造（数据源 → prompt → 文件名 → 落盘位置）在 asset_plan
  - 引擎相关的路径与导入规则在 engine_adapter
  - 实际调哪个生图程序在 image_backend，协议见 BACKEND-PROTOCOL.md

前两个模块和 asset-config skill 的校验器是同一份 —— 校验和执行看到的是
同一个计划，这是刻意的：两套解析迟早给出不同结论。

CLI:
    python generate_assets.py <category>          # 生成单个 category
    python generate_assets.py all                 # 生成全部 category
    python generate_assets.py list                # 列出 + desc
    python generate_assets.py <cat> --names a,b   # 过滤 id（对所有数据源都有效）
    python generate_assets.py --dry-run           # image-gen 走 --dry-run
    python generate_assets.py --force             # 覆盖已存在
    python generate_assets.py --config path.yaml  # 默认 ./assets/asset-config.yaml

退码：沿用 image-gen 的 0/1/2，多 category 取最大。
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# 允许包外直接 `python generate_assets.py`：把脚本所在目录加进 sys.path
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import asset_context  # noqa: E402
import image_backend  # noqa: E402
from asset_plan import build_category_plan  # noqa: E402
from godot_utils import ensure_parent_dirs  # noqa: E402

# 配置的定位与解析在 asset_context，计划的构造在 asset_plan —— 校验器用的是
# 同两个模块。本文件只剩「拿到计划之后怎么落盘、怎么调后端、怎么汇总」。
DEFAULT_CONFIG_PATHS = asset_context.DEFAULT_CONFIG_PATHS


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

    config_path = asset_context.locate_config(args.config)
    if config_path is None:
        print(
            f"[fatal] 找不到 asset-config.yaml（默认搜索：{asset_context.default_config_hint()}）",
            file=sys.stderr,
        )
        return 1

    try:
        config = asset_context.load_config(config_path)
    except asset_context.ContextError as e:
        print(f"[fatal] {e}", file=sys.stderr)
        return 1

    # list 只看 config，不解析路径 —— 插件自带的示例用 res://，
    # 在没有 Godot 工程的目录下也应该能列出来看看。
    if args.command == "list":
        # 空配置照旧打 "(empty config)"，不算错
        problems = asset_context.category_problems(config.get("categories"), allow_empty=True)
        if problems:
            for problem in problems:
                print(f"[fatal] {problem}", file=sys.stderr)
            return 1
        _cmd_list(config)
        return 0

    # 上下文解析的报错都是写给人看的（改 adapter、换相对路径……），
    # 不接住就变成 traceback，把那句话埋在栈帧下面。
    try:
        ctx = asset_context.load_context(
            config_path,
            explicit_project_root=(
                Path(args.project_root) if getattr(args, "project_root", None) else None
            ),
            config=config,
        )
    except asset_context.ContextError as e:
        print(f"[fatal] {e}", file=sys.stderr)
        return 1

    # 选择 category
    categories = ctx.categories
    problems = asset_context.category_problems(categories)
    if problems:
        for problem in problems:
            print(f"[fatal] {problem}", file=sys.stderr)
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

    backend_script = ctx.backend.resolve_script()
    if backend_script is None:
        print(
            f"[fatal] backend={ctx.backend.name} 的脚本不存在。{ctx.backend.install_hint}",
            file=sys.stderr,
        )
        return 1

    # 工程根决定了所有相对路径的基准，写进哪、读哪张参考图全看它。
    # 它有四种定法，光看结果分不出是哪种 —— 所以把来源一起说出来。
    print(f"[info] project_root={ctx.project_root}（{ctx.project_root_source}）", file=sys.stderr)
    for note in ctx.notes:
        print(f"[info] {note}", file=sys.stderr)

    if args.limit is not None and args.limit < 1:
        print(f"[fatal] --limit 要 ≥ 1，收到 {args.limit}", file=sys.stderr)
        return 1

    name_filter = _parse_names(args.names)

    # 跑每个 category
    results: list[CategoryRunResult] = []
    for cat_name in target_names:
        result = _run_category(
            ctx=ctx,
            cat_name=cat_name,
            cat_spec=categories[cat_name],
            backend_script=backend_script,
            dry_run=args.dry_run,
            force=args.force,
            name_filter=name_filter,
            limit=args.limit,
            allow_degrade=args.allow_degrade,
            allow_implicit_overrides=args.allow_implicit_overrides,
        )
        results.append(result)

    # 汇总 + 引擎导入提示
    overall_code = max((r.exit_code for r in results), default=0)
    _print_summary(results)

    # 只要输出目录里可能有图片就给导入提示。两个坑：
    #   1) 总退码取最大，一个 category 全失败会把它抬到 1，但另一个 category
    #      成功生成的图片仍然需要导入
    #   2) 全部 skipped（图片已存在）时 success=0，但那些已存在的 PNG 同样
    #      可能还没被引擎导入过
    any_output = any(
        ((r.summary or {}).get("success", 0) + (r.summary or {}).get("skipped", 0)) > 0
        for r in results
    )
    if not args.dry_run and any_output:
        hint = ctx.import_hint(ctx.output_root)
        if hint:
            print(hint)

    return overall_code


# -------------------- CLI 解析 --------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_assets",
        description="schema-driven asset orchestrator（引擎无关，适配层见 engine_adapter.py）",
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
        help="逗号分隔 id 列表，只生成这几条（对所有数据源都有效）",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="工程根绝对/相对路径。不给则按 config 的 project_root、"
             "适配器探测、最后按 config 位置推断（后者会随 config 移动而变）",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="只取前 N 条。用来抽样验模板，省得先去数据源里查 id 叫什么",
    )
    parser.add_argument(
        "--allow-degrade",
        action="store_true",
        help="后端不支持配置里的模型/风格/底图时仍然跑。默认阻止 —— 丢掉这些，"
             "产出的就不是你要的那件事了",
    )
    parser.add_argument(
        "--allow-implicit-overrides",
        action="store_true",
        help="数据里撞名的列（model/seed/aspect_ratio/image）没在 item_overrides 里"
             "声明过时仍然跑。默认阻止 —— 配置的行为不该依赖没人声明过的巧合",
    )
    parser.add_argument("--dry-run", action="store_true", help="image-gen 走 --dry-run")
    parser.add_argument("--force", action="store_true", help="覆盖已存在的输出文件")
    return parser


def _parse_names(raw: str | None) -> set[str] | None:
    if not raw:
        return None
    parts = [s.strip() for s in raw.split(",") if s.strip()]
    return set(parts) if parts else None


# -------------------- list --------------------

def _shell_join(argv: list[str]) -> str:
    """打印给人复制的命令行。路径带空格就得加引号，否则复制过去 argparse 会拆错。"""
    return subprocess.list2cmdline(argv) if os.name == "nt" else shlex.join(argv)


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
    ctx,
    cat_name: str,
    cat_spec: dict,
    backend_script: Path,
    dry_run: bool,
    force: bool,
    name_filter: "set[str] | None",
    limit: "int | None" = None,
    allow_degrade: bool = False,
    allow_implicit_overrides: bool = False,
) -> CategoryRunResult:
    """算出计划 → 落盘 → 调后端。

    计划本身由 asset_plan 构造，校验器用的是同一个函数 —— 所以
    `check_config.py` 通过的那份配置，跑起来看到的是同一批 prompt、
    同一批落盘位置。
    """
    print(f"\n=== category: {cat_name} ===")
    plan = build_category_plan(
        ctx, cat_name, cat_spec, name_filter=name_filter, limit=limit,
        allow_degrade=allow_degrade,
        allow_implicit_overrides=allow_implicit_overrides,
    )

    for note in plan.notes:
        print(f"  [note] {note}")
    for warning in plan.warnings:
        print(f"[warn] {warning}", file=sys.stderr)
    for issue in plan.governance:
        print(f"[warn] {issue}", file=sys.stderr)

    if not plan.ok:
        for err in plan.errors:
            print(f"[error] {err}", file=sys.stderr)
        return CategoryRunResult(
            name=cat_name, exit_code=1, summary=None, error=plan.errors[0]
        )

    if not plan.assets:
        print(f"[info] {cat_name}: 无 asset 可生成（数据源为空，或被 --names/--limit 滤光）")
        return CategoryRunResult(
            name=cat_name,
            exit_code=0,
            summary={"total": 0, "success": 0, "failed": 0, "skipped": 0},
        )

    output_dir = plan.output_dir
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        ensure_parent_dirs([a.output_path for a in plan.assets])
    except (FileExistsError, NotADirectoryError, PermissionError) as e:
        msg = (f"输出目录建不了：{output_dir}（{getattr(e, 'strerror', None) or e}）"
               "—— 那个位置已经是个文件，或没有写权限")
        print(f"[error] {msg}", file=sys.stderr)
        return CategoryRunResult(name=cat_name, exit_code=1, summary=None, error=msg)

    batch = plan.to_batch()
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=f"_{cat_name}.json",
        delete=False,
        encoding="utf-8",
    ) as tf:
        json.dump(batch, tf, ensure_ascii=False, indent=2)
        batch_path = Path(tf.name)

    print(f"  items: {len(plan.assets)}, output: {output_dir}")
    print(f"  batch JSON: {batch_path}")
    if dry_run:
        # dry-run 的目的之一是看 prompt；后端的 dry-run 通常只打计划不打 prompt
        for asset in plan.assets:
            print(f"  [prompt] {asset.item_id}: {asset.prompt}")

    cmd = [
        sys.executable,
        str(backend_script),
        str(batch_path),
        "--output-dir",
        str(output_dir),
    ]
    if dry_run:
        cmd.append("--dry-run")
    if force:
        cmd.append("--force")

    print(f"  $ {_shell_join(cmd)}")
    summary, exit_code, err = _invoke_backend(cmd, cwd=ctx.project_root)
    if summary is None and err is None and not dry_run:
        # 没有 summary 就无法确认产物，退出码 0 也不算成功。
        # dry-run 例外：上游 dry-run 本来就只打计划、不吐 summary。
        err = f"后端没有返回 summary，无法确认生成结果（它的退出码 {exit_code}）"
        print(f"[error] {err}", file=sys.stderr)
        exit_code = 1
    return CategoryRunResult(name=cat_name, exit_code=exit_code, summary=summary, error=err)


# -------------------- image-gen subprocess --------------------

def _invoke_backend(cmd: list[str], *, cwd: "Path | None" = None) -> tuple[dict | None, int, str | None]:
    """跑后端，返回 (summary_json, exit_code, error_msg)。

    后端会把末尾一行 JSON summary 打到 stdout。

    cwd 必须是工程根：后端靠 CWD 向上找 .env 取凭证，不设的话找的是
    调用者所在项目 —— 资源写进 A 项目，凭证却读了 B 项目的。
    """
    try:
        # 流式读而不是 capture_output：批量跑十几张要几十分钟，攒到结束才吐
        # 等于整个过程没有反馈 —— 不知道到第几张、哪张失败了。
        # stderr 不捕获、直接继承终端，让 [retry] / [warn] 也实时可见。
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except FileNotFoundError as e:
        return None, 1, f"后端脚本不存在: {e}"
    except Exception as e:
        return None, 1, f"subprocess 异常：{e}"

    collected: list[str] = []
    try:
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()      # 不 flush 还是会卡在缓冲里
            collected.append(line)
    finally:
        proc.stdout.close()
        returncode = proc.wait()

    summary = _extract_summary("".join(collected))
    return summary, returncode, None


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
