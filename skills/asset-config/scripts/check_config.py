#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""asset-config.yaml 校验。

在四个时刻都用得上：首次初始化完、人手改过、AI 改过、以及后续维护。
所以它是这个 skill 的工具侧重心 —— 初始化引导是一次性的，校验是长期的。

**复用 generate-assets 的加载与渲染逻辑，不另写一套。** 两边各自解析同一份
yaml，迟早得出不同结论 —— 那正是「双口径」。代价是本脚本依赖隔壁 skill 的
scripts 目录，找不到时会明确报出来，而不是退化成一套简化实现。

错误与提示是两回事：
  - **错误**（退码 1）：会让生成失败，或者产出错的东西
  - **提示**（退码 0）：创作性的未定稿，比如 prompt 还没调满意 ——
    它不该拦住人，因为「调到满意」本来就得靠出小样反复看

用法：
    python check_config.py [--config PATH] [--project-root PATH]
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# 隔壁 skill 的 scripts —— check 必须和真正跑生成的那套用同一份解析逻辑
_GA_SCRIPTS = Path(__file__).resolve().parents[2] / "generate-assets" / "scripts"
if _GA_SCRIPTS.is_dir() and str(_GA_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_GA_SCRIPTS))

try:
    import asset_context
    from asset_plan import build_category_plan, resolve_reference
except ImportError as e:  # pragma: no cover - 环境缺失时的兜底
    print(
        f"[fatal] 找不到 generate-assets 的脚本（{e}）。"
        f"本校验复用它的加载与渲染逻辑，期望位置：{_GA_SCRIPTS}",
        file=sys.stderr,
    )
    raise SystemExit(2)

try:
    import yaml
except ImportError:  # pragma: no cover
    print("[fatal] 需要 PyYAML：pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)


# 未完成标记。只用于**创作性**未定稿 —— 功能性缺失（比如模板引用了不存在的
# 字段）由检查本身发现，不需要人手标。
TODO_MARKER = "TODO"

DEFAULT_CONFIG_NAMES = tuple(str(p) for p in asset_context.DEFAULT_CONFIG_PATHS)

# 「必须询问」档的字段 —— 与 SKILL.md 的决策权限表一致。
# 它们的值必须在注释里写明从哪来，见 _check_decision_sources。
_MUST_ASK_FIELDS = frozenset({"backend", "model", "chain", "aspect_ratio", "id_column"})

# 来源标记。要求固定前缀而不是自由发挥，是为了能机械地查；
# 前缀之后写什么随意，那部分是给人读的。
_SOURCE_MARKER = "来源："


# 检查分组。两种问题的性质不同，退码也不同 —— 见 Report。
CHECK_RUNTIME = "runtime"
CHECK_GOVERNANCE = "governance"
CHECK_ALL = "all"
CHECK_CHOICES = (CHECK_ALL, CHECK_RUNTIME, CHECK_GOVERNANCE)


@dataclass
class Report:
    """三类结果，性质不同，不该共用一个退码。

    - `errors`（**运行合法性**）：会让生成失败或产出错的东西。退码 1。
    - `governance`（**配置治理**）：「必须询问」档的字段没写来源。
      配置照样能正确生成图片 —— 格式化工具重排 YAML、删掉注释就会触发它，
      而运行语义完全没变。冒充运行合法性的话，每个未来的消费者都要被迫
      继承某个 agent 写配置时的交互规矩。退码 3。
    - `notes`：提示，不影响退码。
    """

    errors: list[str] = field(default_factory=list)
    governance: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """运行合法性。**不含治理** —— 「能不能跑」和「有没有留决策记录」是两回事。"""
        return not self.errors

    @property
    def governance_ok(self) -> bool:
        return not self.governance

    @property
    def clean(self) -> bool:
        """两样都过。初始化交付要求的是这个。"""
        return self.ok and self.governance_ok

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def governance_issue(self, msg: str) -> None:
        self.governance.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)


def check_config(
    config_path: Path,
    project_root: "Path | None" = None,
    *,
    checks: str = CHECK_ALL,
) -> Report:
    """校验一份 asset-config.yaml，返回 Report。不抛异常。

    `project_root` 只是**覆盖**本次校验的工程根（对应 `--project-root`）。
    不给就由 asset_context 按四级规则定 —— 和真正跑生成时同一套规则，
    否则会出现「检查了一个位置、跑的是另一个位置」。

    `checks` 选跑哪一组：`all`（缺省）/ `runtime` / `governance`。
    治理检查纯看原文注释，不需要工程、数据源、后端就位，所以
    `governance` 这一档不加载上下文。
    """
    if checks not in CHECK_CHOICES:
        raise ValueError(f"checks 只能是 {' / '.join(CHECK_CHOICES)}，收到 {checks!r}")

    r = Report()
    config_path = Path(config_path)

    if not config_path.exists():
        # 任何档位都要报。否则 governance 档会对着一个不存在的文件返回「干净」。
        r.error(f"配置文件不存在：{config_path}")
        return r

    if checks in (CHECK_ALL, CHECK_GOVERNANCE):
        _check_decision_sources(config_path, r)
    if checks == CHECK_GOVERNANCE:
        return r

    try:
        config = asset_context.load_config(config_path)
    except asset_context.ContextError as e:
        r.error(str(e))
        return r

    try:
        ctx = asset_context.load_context(
            config_path,
            explicit_project_root=Path(project_root) if project_root is not None else None,
            config=config,
        )
    except asset_context.ContextError as e:
        r.error(str(e))
        return r

    # 工程根是所有相对路径的基准，四种定法结果可能差很远 —— 报出来，
    # 让人能一眼看出这次校验是按哪个位置算的。
    r.note(f"project_root={ctx.project_root}（{ctx.project_root_source}）")
    for note in ctx.notes:
        r.note(note)

    # 后端脚本不存在只提示不报错：校验配置不该要求生图环境就绪
    if ctx.backend.resolve_script() is None:
        r.note(f"backend={ctx.backend.name} 的脚本还不在位。{ctx.backend.install_hint}")

    declared_model = config.get("model")
    if declared_model and "model" not in getattr(ctx.backend, "supports", frozenset()):
        r.error(
            f"backend={ctx.backend.name} 不支持 model（配的是 {declared_model!r}）。"
            "image-gen 用 chain 表达模型选择，把 model: 改写成 chain: 才生效。"
        )

    style = config.get("style") or {}
    if not isinstance(style, dict):
        r.error(f"style 应为映射，实际是 {type(style).__name__}")
        return r
    _check_style_markers(style, r)

    categories = ctx.categories
    if not isinstance(categories, dict) or not categories:
        r.error(
            "config 里没有 categories（或它不是映射）—— 至少要有一个 category "
            "才知道生成什么"
        )
        return r

    # 输入图的存在性攒到最后一起查。全局 reference_paths 会进每个 category
    # 的计划，逐个 category 查的话，有几个 category 就把同一条「文件不存在」
    # 报几遍。
    inputs: dict = {}

    for name, spec in categories.items():
        if not isinstance(spec, dict):
            r.error(f"category {name!r} 的配置应为映射，实际是 {type(spec).__name__}")
            continue
        _check_category(ctx, name, spec, inputs, r)

    _check_global_references(ctx, style, inputs)
    for full, label in inputs.items():
        if not Path(full).exists():
            r.error(f"{label} 指向的文件不存在：{full}")

    return r


def _check_category(ctx, name: str, spec: dict, inputs: dict, r: Report) -> None:
    """把这个 category 算成生成计划，再验证那个计划。

    **算计划用的是生成器那一份函数**（asset_plan.build_category_plan），
    不是这里另写的简化版。以前这里只渲染第一个条目，第 2 条起的模板问题
    要等真跑才暴露 —— 那时候已经在按张烧钱了。
    """
    plan = build_category_plan(ctx, name, spec)

    for err in plan.errors:
        r.error(err)
    for note in plan.notes:
        r.note(note)
    # 字段被后端丢掉：生成时是告警，这里也只提示 —— 它不会让生成失败，
    # 只是结果和配置写的不一样。
    for warning in plan.warnings:
        r.note(warning)
    for issue in plan.governance:
        r.governance_issue(issue)

    template = spec.get("prompt_template")
    if isinstance(template, str) and TODO_MARKER in template:
        r.note(
            f"category {name}: prompt_template 还带着 {TODO_MARKER} 标记，"
            "是创作性未定稿 —— 能出图，但风格多半还没调到位"
        )

    for label, full in plan.input_paths:
        inputs.setdefault(full, label)


def _check_global_references(ctx, style: dict, inputs: dict) -> None:
    """全局 reference_paths 单独收一次。

    所有 category 都 skip_global_style 时，它不会进任何一份计划 ——
    但路径写错了仍然值得说，那多半是笔误而不是有意停用。
    """
    for raw in (style.get("reference_paths") or []):
        try:
            full = resolve_reference(
                str(raw), project_root=ctx.project_root,
                output_root=ctx.output_root, adapter=ctx.adapter,
            )
        except ValueError:
            continue    # 解析失败已由计划那边报过
        inputs.setdefault(full, "style.reference_paths")


def _check_style_markers(style: dict, r: Report) -> None:
    """style 段的未完成标记。

    prompt_prefix 为空**不算错** —— 风格可以写在 category 里，也可以用
    skip_global_style 整个关掉，强制非空是把一种用法当成唯一用法。
    """
    for key in ("prompt_prefix", "prompt_suffix"):
        value = style.get(key)
        if isinstance(value, str) and TODO_MARKER in value:
            r.note(f"style.{key} 还带着 {TODO_MARKER} 标记，是创作性未定稿：{value!r}")


def _check_decision_sources(config_path: Path, r: Report) -> None:
    """「必须询问」档的字段，要在紧邻的注释块里写明值从哪来。

    挡不住一个决心撒谎的 AI —— 注释是它自己写的。但挡得住「顺手填了忘了问」，
    而后者才是实际会发生的那种。顺带让配置本身成为可审查的决策记录：
    半年后翻开这份 yaml，能看出 model 是问过人的还是谁随手定的。

    写「沿用某处的声明」也算来源 —— 要求的是说清**从哪来**，
    不是证明**问过谁**。后者任何静态检查都做不到。

    注意读的是原始文本：yaml.safe_load 会把注释全丢掉。
    """
    try:
        lines = config_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", line)
        if not m or m.group(2) not in _MUST_ASK_FIELDS:
            continue

        # 往上扫紧邻的注释块。空行中断 —— 隔了空行的注释是在说别的事。
        found = False
        j = i - 1
        while j >= 0 and lines[j].lstrip().startswith("#"):
            if _SOURCE_MARKER in lines[j]:
                found = True
                break
            j -= 1

        if not found:
            r.governance_issue(
                "第 {} 行的 {!r} 是「必须询问」档的字段，但上面没写它从哪来。"
                "在紧邻的注释里加一行「{}…」，例如"
                "「# {}用户选定（候选 A / B）」或"
                "「# {}沿用 xxx.yaml 的声明」。".format(
                    i + 1, m.group(2), _SOURCE_MARKER, _SOURCE_MARKER, _SOURCE_MARKER
                )
            )


def main(argv: "list[str] | None" = None) -> int:
    """退码：0 全过 / 1 运行合法性有错 / 3 只有治理问题。

    3 单独留给治理，是为了让消费者能机械地分辨「这份配置跑不了」和
    「这份配置没留下决策记录」—— 后者不该拦住任何一个下游。
    """
    ap = argparse.ArgumentParser(description="校验 asset-config.yaml")
    ap.add_argument("--config", help="配置文件路径；不给就按默认位置找")
    ap.add_argument("--project-root", help="工程根；不给就从配置位置推断")
    ap.add_argument(
        "--check", choices=CHECK_CHOICES, default=CHECK_ALL,
        help="跑哪一组：all（缺省）/ runtime（只看能不能跑）/ "
             "governance（只看「必须询问」档的字段有没有写来源）",
    )
    args = ap.parse_args(argv)

    config_path = asset_context.locate_config(
        Path(args.config) if args.config else None
    )
    if config_path is None:
        print(
            "[fatal] 找不到 asset-config.yaml，"
            f"试过：{asset_context.default_config_hint()}。用 --config 指定。",
            file=sys.stderr,
        )
        return 1

    # 不给 --project-root 就传 None，让 asset_context 按四级规则定 ——
    # 这里曾经硬填 config 的父目录，于是校验和生成可能算出两个不同的根。
    report = check_config(
        config_path,
        Path(args.project_root) if args.project_root else None,
        checks=args.check,
    )

    for note in report.notes:
        print(f"  [note] {note}")
    for err in report.errors:
        print(f"[error] {err}", file=sys.stderr)
    for issue in report.governance:
        print(f"[治理] {issue}", file=sys.stderr)

    if not report.ok:
        print(f"\n✗ {len(report.errors)} 处错误（运行合法性）", file=sys.stderr)
        if report.governance:
            print(f"  另有 {len(report.governance)} 处治理问题", file=sys.stderr)
        return 1

    if report.governance:
        print(
            f"\n✗ {len(report.governance)} 处治理问题 —— 配置本身能跑，"
            "但「必须询问」档的字段没留下决策记录。",
            file=sys.stderr,
        )
        return 3

    tail = f"（{len(report.notes)} 条提示）" if report.notes else ""
    scope = {CHECK_RUNTIME: "运行检查", CHECK_GOVERNANCE: "治理检查"}.get(
        args.check, "校验")
    print(f"✓ {config_path} {scope}通过{tail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
