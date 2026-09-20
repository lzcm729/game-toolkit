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
    import engine_adapter
    import image_backend
    from data_source import load_data_source
    from prompt_render import compose_prompt, evaluate_derived, render_template
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


def _openai_style_checker():
    """拿 laozhang 后端自己的「这个模型走哪条 API 路径」判断。

    不在这里重写 model.startswith("gpt-image") —— 规则重复两份，
    后端哪天改了判断标准，check 就开始说谎。拿不到就返回 None，
    这条检查跳过而不是瞎猜。
    """
    backends_dir = _GA_SCRIPTS / "backends"
    if str(backends_dir) not in sys.path:
        sys.path.insert(0, str(backends_dir))
    try:
        from laozhang_backend import _is_openai_style
    except ImportError:
        return None
    return _is_openai_style


# 未完成标记。只用于**创作性**未定稿 —— 功能性缺失（比如模板引用了不存在的
# 字段）由检查本身发现，不需要人手标。
TODO_MARKER = "TODO"

DEFAULT_CONFIG_NAMES = ("asset-config.yaml", "assets/asset-config.yaml")

# 「必须询问」档的字段 —— 与 SKILL.md 的决策权限表一致。
# 它们的值必须在注释里写明从哪来，见 _check_decision_sources。
_MUST_ASK_FIELDS = frozenset({"backend", "model", "chain", "aspect_ratio", "id_column"})

# 来源标记。要求固定前缀而不是自由发挥，是为了能机械地查；
# 前缀之后写什么随意，那部分是给人读的。
_SOURCE_MARKER = "来源："


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def note(self, msg: str) -> None:
        self.notes.append(msg)


def check_config(config_path: Path, project_root: Path) -> Report:
    """校验一份 asset-config.yaml，返回 Report。不抛异常。"""
    r = Report()
    config_path = Path(config_path)
    project_root = Path(project_root)

    if not config_path.exists():
        r.error(f"配置文件不存在：{config_path}")
        return r

    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        r.error(f"{config_path} 不是合法 YAML：{e}")
        return r
    if not isinstance(config, dict):
        r.error(f"{config_path} 的顶层应该是映射，实际是 {type(config).__name__}")
        return r

    _check_decision_sources(config_path, r)

    adapter = _check_adapter(config, config_path, r)
    if adapter is None:
        return r

    output_root = _check_output_root(config, project_root, adapter, r)
    backend = _check_backend(config, project_root, r)
    _check_style(config, project_root, output_root, adapter, r)

    categories = config.get("categories") or {}
    if not isinstance(categories, dict) or not categories:
        r.error(
            "config 里没有 categories（或它不是映射）—— 至少要有一个 category "
            "才知道生成什么"
        )
        return r

    for name, spec in categories.items():
        if not isinstance(spec, dict):
            r.error(f"category {name!r} 的配置应为映射，实际是 {type(spec).__name__}")
            continue
        _check_category(
            name, spec, config, project_root, output_root, adapter, backend, r
        )

    return r


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
            r.error(
                "第 {} 行的 {!r} 是「必须询问」档的字段，但上面没写它从哪来。"
                "在紧邻的注释里加一行「{}…」，例如"
                "「# {}用户选定（候选 A / B）」或"
                "「# {}沿用 xxx.yaml 的声明」。".format(
                    i + 1, m.group(2), _SOURCE_MARKER, _SOURCE_MARKER, _SOURCE_MARKER
                )
            )


def _check_adapter(config: dict, config_path: Path, r: Report):
    try:
        return engine_adapter.select(config, config_path.parent)
    except ValueError as e:
        r.error(str(e))
        return None


def _check_output_root(config: dict, project_root: Path, adapter, r: Report):
    """解析 output_root。

    目录不存在**不算错** —— 生成时会自己 mkdir，要求人先建出来纯属添乱。
    这里只验路径能不能解析（比如 /Game/ 配 generic adapter 就解析不了）。
    """
    raw = config.get("output_root", "assets/art")
    if not isinstance(raw, str):
        r.error(f"output_root 应为字符串，实际是 {type(raw).__name__}")
        return None
    try:
        return adapter.resolve_path(raw, project_root)
    except ValueError as e:
        r.error(f"output_root 解析失败：{e}")
        return None


def _check_backend(config: dict, project_root: Path, r: Report):
    try:
        backend = image_backend.select(config, project_root)
    except ValueError as e:
        r.error(str(e))
        return None

    # 后端脚本不存在只提示不报错：校验配置不该要求生图环境就绪
    if backend.resolve_script() is None:
        r.note(f"backend={backend.name} 的脚本还不在位。{backend.install_hint}")

    declared_model = config.get("model")
    if declared_model and "model" not in backend.supports:
        r.error(
            f"backend={backend.name} 不支持 model（配的是 {declared_model!r}）。"
            "image-gen 用 chain 表达模型选择，把 model: 改写成 chain: 才生效。"
        )
    return backend


def _check_style(config: dict, project_root: Path, output_root, adapter,
                 r: Report) -> None:
    """style 段：未完成标记 + 全局参考图。

    全局 reference_paths 在这里检查一次就够 —— 放进 category 循环的话，
    有几个 category 就把同一条「文件不存在」报几遍。

    prompt_prefix 为空**不算错** —— 风格可以写在 category 里，也可以用
    skip_global_style 整个关掉，强制非空是把一种用法当成唯一用法。
    """
    style = config.get("style") or {}
    if not isinstance(style, dict):
        r.error(f"style 应为映射，实际是 {type(style).__name__}")
        return
    for key in ("prompt_prefix", "prompt_suffix"):
        value = style.get(key)
        if isinstance(value, str) and TODO_MARKER in value:
            r.note(f"style.{key} 还带着 {TODO_MARKER} 标记，是创作性未定稿：{value!r}")

    for raw in (style.get("reference_paths") or []):
        _check_input_path(
            str(raw), project_root, output_root, adapter, "style.reference_paths", r)


def _check_category(
    name: str,
    spec: dict,
    config: dict,
    project_root: Path,
    output_root,
    adapter,
    backend,
    r: Report,
) -> None:
    # --- 数据源 ---
    try:
        items = load_data_source(spec.get("data_source") or {}, project_root)
    except (ValueError, FileNotFoundError, OSError) as e:
        r.error(f"category {name}: 数据源加载失败 —— {e}")
        return

    if not items:
        r.note(f"category {name}: 数据源没有条目，这个 category 不会产出任何图")
        return

    # --- id 唯一性与输出文件名 ---
    ext = spec.get("output_ext", "png")
    seen: dict[str, str] = {}
    for item in items:
        item_id = item.get("id")
        if not item_id:
            r.error(f"category {name}: 有条目缺 id —— {item!r}")
            continue
        filename = f"{item_id}.{ext}"
        if filename in seen:
            r.error(
                f"category {name}: 两个条目产出同一个文件 {filename}"
                f"（id {seen[filename]!r} 和 {item_id!r}）—— 后写的会覆盖先写的"
            )
        seen[filename] = str(item_id)

    # --- image 与 reference_paths 互斥 ---
    global_refs = (config.get("style") or {}).get("reference_paths")
    cat_refs = spec.get("reference_paths")
    has_refs = bool(cat_refs) or (bool(global_refs) and not spec.get("skip_global_style"))
    has_image = bool(spec.get("image")) or any(it.get("image") for it in items)
    if has_refs and has_image:
        r.error(
            f"category {name}: 同时给了 image 和 reference_paths，两者互斥 —— "
            "image 是「编辑这张底图」，reference_paths 是「参考这些图的风格」"
        )

    # --- 模型能力与风格锚是否相容 ---
    # 配置层就能静态判定的事，不该拖到烧钱的运行时才发现：
    # gpt-image-* 走 OpenAI 路径，没有多图 reference，配了风格锚必然全军覆没
    if backend is not None and backend.name == "laozhang" and has_refs:
        is_openai = _openai_style_checker()
        if is_openai is not None:
            top_model = config.get("model")
            for label, model in (
                (f"category {name} 的 model", spec.get("model")),
                ("顶层 model", top_model if not spec.get("model") else None),
                *((f"category {name} 中 item {it.get('id')!r} 的 model", it.get("model"))
                  for it in items if it.get("model")),
            ):
                if model and is_openai(str(model)):
                    r.error(
                        f"{label} 是 {model!r}，它走 OpenAI 路径、不支持多图 "
                        f"reference_paths；而 category {name} 配了风格锚。"
                        "改用 gemini-* 模型，或把风格参考换成 image（单张编辑底图）。"
                    )

    # --- 模板能否在真实条目上渲染 ---
    template = spec.get("prompt_template")
    if not template:
        r.error(f"category {name}: 缺 prompt_template")
        return
    if TODO_MARKER in template:
        r.note(
            f"category {name}: prompt_template 还带着 {TODO_MARKER} 标记，"
            "是创作性未定稿 —— 能出图，但风格多半还没调到位"
        )

    sample = items[0]
    try:
        enriched = evaluate_derived(sample, spec.get("derived_fields"))
    except Exception as e:
        r.error(f"category {name}: derived_fields 在第一个条目上算不出来 —— {e}")
        return

    try:
        rendered = render_template(template, enriched)
    except Exception as e:
        r.error(
            f"category {name}: prompt_template 在第一个条目上渲染失败 —— {e}。"
            f"该条目可用的字段：{sorted(enriched)}"
        )
        return

    style = config.get("style") or {}
    skip_global = bool(spec.get("skip_global_style", False))
    try:
        compose_prompt(
            rendered,
            global_prefix=(style.get("prompt_prefix") or "") if not skip_global else "",
            global_suffix=(style.get("prompt_suffix") or "") if not skip_global else "",
            skip_global=skip_global,
        )
    except Exception as e:
        r.error(f"category {name}: 拼全局风格时失败 —— {e}")

    # --- 引用的图片路径 ---
    # 全局 refs 已在 _check_style 里查过，这里只管 category 自己声明的
    for raw in (cat_refs or []):
        _check_input_path(
            str(raw), project_root, output_root, adapter,
            f"category {name} 的 reference_paths", r)
    raw_image = spec.get("image")
    if raw_image:
        _check_input_path(
            str(raw_image), project_root, output_root, adapter,
            f"category {name} 的 image", r,
        )


def _check_input_path(
    raw: str, project_root: Path, output_root, adapter, label: str, r: Report
) -> None:
    """输入图片必须存在 —— 和输出目录不同，它不会被自动创建。"""
    try:
        if Path(raw).is_absolute():
            full = Path(raw)
        elif any(raw.startswith(px) for px in engine_adapter.KNOWN_ENGINE_PREFIXES):
            full = Path(adapter.resolve_path(raw, project_root))
        else:
            base = output_root if output_root is not None else project_root
            full = Path(adapter.resolve_path(raw, base))
    except ValueError as e:
        r.error(f"{label} 的路径解析失败（{raw}）：{e}")
        return
    if not full.exists():
        r.error(f"{label} 指向的文件不存在：{full}")


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description="校验 asset-config.yaml")
    ap.add_argument("--config", help="配置文件路径；不给就按默认位置找")
    ap.add_argument("--project-root", help="工程根；不给就从配置位置推断")
    args = ap.parse_args(argv)

    if args.config:
        config_path = Path(args.config)
    else:
        found = [Path(n) for n in DEFAULT_CONFIG_NAMES if Path(n).exists()]
        if not found:
            print(
                "[fatal] 当前目录下找不到 asset-config.yaml，"
                f"试过：{' / '.join(DEFAULT_CONFIG_NAMES)}。用 --config 指定。",
                file=sys.stderr,
            )
            return 1
        config_path = found[0]

    project_root = Path(args.project_root) if args.project_root else config_path.resolve().parent

    report = check_config(config_path, project_root)

    for note in report.notes:
        print(f"  [note] {note}")
    for err in report.errors:
        print(f"[error] {err}", file=sys.stderr)

    if report.ok:
        tail = f"（{len(report.notes)} 条提示）" if report.notes else ""
        print(f"✓ {config_path} 校验通过{tail}")
        return 0
    print(f"\n✗ {len(report.errors)} 处错误", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
