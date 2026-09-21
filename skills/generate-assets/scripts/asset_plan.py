#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成计划 —— 校验器和生成器共用这一份。

一个 category 从配置走到「要生成哪些图、每张的 prompt 和落盘位置是什么」，
中间有十来步：加载数据源、过滤、注入 extra_fields、算 derived_fields、
渲染模板、拼全局风格、解析参考图、定文件名、定输出目录。3.16.0 之前
这条链在生成器里走一遍、在校验器里走一遍（而且校验器只渲染**第一个条目**），
两份实现迟早给出不同结论。

现在只有一条链，三种用法各取所需：
  - 校验器**验证**这个计划（外加它自己的关注点：输入图存不存在、TODO 标记）
  - dry-run **展示**这个计划
  - 执行器**消费**这个计划

和生成器旧行为的一个差别：遇到问题**收集**而不是抛。第一条错误之后还有
什么问题，人本来就该一次看完，而不是修一条跑一次。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import engine_adapter  # noqa: E402
from data_source import load_data_source  # noqa: E402
from prompt_render import compose_prompt, evaluate_derived, render_template  # noqa: E402

# 逐条渲染失败时，同类错误报到这个数就打住。数据源有一千条、模板引用了一个
# 不存在的字段，那就是一千条一模一样的错 —— 刷屏会把别的问题顶没。
MAX_ITEM_ERRORS = 5

# 后端不认某个字段时，「为什么不支持、改用什么」每个字段都不一样。
# 统一一句「切回 image-gen」对 model 恰好是反的 —— image-gen 才是不认 model 的那个。
UNSUPPORTED_HINTS = {
    "chain": "风格链是 image-gen 特有能力，切回 backend: image-gen 才生效。",
    "preset": "预设是 image-gen 特有能力，切回 backend: image-gen 才生效。",
    "model": "image-gen 用 chain 表达模型选择，把 model: 改写成 chain: 才生效。",
}

# 这几个键是 batch 协议的必备字段，不参与「后端认不认」的判断。
_PROTOCOL_KEYS = ("name", "filename", "prompt")

# 丢掉也**不改变任务含义**的字段。seed 只影响可复现性，不影响画的是什么。
# 其余（model / chain / preset / reference_paths / image / aspect_ratio）
# 一旦被丢掉，产出的就不是用户要的那件事了 —— 那种情况默认阻止，不是告警。
DEGRADE_TOLERANT = frozenset({"seed"})

# 可以按条目覆盖的生成参数。数据里出现同名字段就会顶掉 category 级的设置 ——
# 对专门做的生成清单这很方便，对复用的策划表就是**隐式控制通道**：
# 表里加一列 `model` 表示游戏里的模型类型，不该顺手改掉生图模型。
# 所以 category 可以用 `item_overrides` 显式声明哪一列覆盖哪个参数。
ITEM_CONTROL_PARAMS = ("model", "aspect_ratio", "seed", "image")


@dataclass(frozen=True)
class PlannedAsset:
    """计划里的一张图。"""

    item_id: str
    filename: str
    prompt: str
    output_path: Path
    payload: dict           # 送给后端的 asset dict


@dataclass
class CategoryPlan:
    """一个 category 的完整计划。

    `errors` 非空就不该执行 —— 生成器据此跳过该 category，校验器据此报错。
    `warnings` 是会改变结果但不致命的事（字段被后端丢掉之类）。
    """

    name: str
    output_dir: "Path | None" = None
    defaults: dict = field(default_factory=dict)
    assets: list = field(default_factory=list)          # list[PlannedAsset]
    errors: list = field(default_factory=list)          # list[str]
    warnings: list = field(default_factory=list)        # list[str]
    notes: list = field(default_factory=list)           # list[str]
    # 能跑，但配置的意图没被声明过。校验器按治理问题报（退码 3），
    # 生成器按告警打 —— 它不该拦住人，但也不该悄无声息。
    governance: list = field(default_factory=list)      # list[str]
    # (标签, 绝对路径)，供校验器查存在性。生成器不查 —— 后端会报。
    input_paths: list = field(default_factory=list)     # list[tuple[str, Path]]
    total_items: int = 0                                # 过滤/截断之前的条目数

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_batch(self) -> dict:
        """序列化成 BACKEND-PROTOCOL.md 的 batch JSON。"""
        return {
            "$schema_version": 2,
            "defaults": dict(self.defaults),
            "assets": [dict(a.payload) for a in self.assets],
        }


class _ErrorSink:
    """带上限的错误收集器。超出后只留一条汇总，不刷屏。"""

    def __init__(self, target: list, limit: int = MAX_ITEM_ERRORS):
        self._target = target
        self._limit = limit
        self._count = 0

    def add(self, msg: str) -> None:
        self._count += 1
        if self._count <= self._limit:
            self._target.append(msg)

    def finish(self, tail: str) -> None:
        if self._count > self._limit:
            self._target.append(
                f"{tail}：另有 {self._count - self._limit} 条同类错误未列出"
            )


def resolve_reference(ref: str, *, project_root: Path, output_root: Path, adapter) -> Path:
    """解析 reference_paths / image 里的一项，返回绝对路径。

    三种写法的基准不同，不能共用一个 root：
      - 绝对路径   → 原样
      - `res://X`  → project_root / X （引擎虚拟前缀按定义等价于项目根）
      - 裸相对路径 → output_root / X  （examples/README.md 的约定）
    """
    p = Path(ref)
    if p.is_absolute():
        return p
    is_engine_path = any(ref.startswith(px) for px in engine_adapter.KNOWN_ENGINE_PREFIXES)
    root = project_root if is_engine_path else output_root
    return Path(adapter.resolve_path(ref, root))


def resolve_item_overrides(cat_name: str, cat_spec: dict, plan: "CategoryPlan"):
    """读 `item_overrides`。返回 {生成参数: 数据字段名}，未声明时返回 None。

    显式声明的语义是**封闭的**：只有写出来的映射生效，数据里别的同名字段
    一律当普通数据。`item_overrides: {}` 就是「本 category 不接受逐项覆盖」。
    """
    if "item_overrides" not in cat_spec:
        return None

    raw = cat_spec.get("item_overrides")
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        plan.errors.append(
            f"category {cat_name}: item_overrides 应为映射（生成参数 → 数据字段名），"
            f"实际是 {type(raw).__name__}"
        )
        return {}

    out: dict = {}
    for param, source in raw.items():
        if param not in ITEM_CONTROL_PARAMS:
            plan.errors.append(
                f"category {cat_name}: item_overrides 里的 {param!r} 不是可逐项覆盖的"
                f"生成参数（可选：{' / '.join(ITEM_CONTROL_PARAMS)}）"
            )
            continue
        if not isinstance(source, str) or not source.strip():
            plan.errors.append(
                f"category {cat_name}: item_overrides[{param!r}] 应为数据字段名"
                f"（非空字符串），实际是 {source!r}"
            )
            continue
        out[param] = source.strip()
    return out


def implicit_override_governance(cat_name: str, items: list) -> list:
    """未声明 `item_overrides` 时，数据里撞名的字段正在当控制通道用。

    不改变行为（那会让现有配置静默失效），但要说出来 —— 它是「能跑，
    但这份配置的行为依赖一个列名巧合，没有被任何人声明过」。
    """
    hit = sorted({k for item in items for k in ITEM_CONTROL_PARAMS if k in item})
    if not hit:
        return []
    names = " / ".join(repr(k) for k in hit)
    return [
        f"category {cat_name}: 数据里的 {names} 正在当生图参数用（条目级优先级最高，"
        "压得过 category 和顶层的同名设置），但配置没声明过这件事。"
        f"有意的话写 item_overrides: {{{hit[0]}: {hit[0]}}}；"
        "是业务数据的话用 data_source.columns 改个名，"
        "或写 item_overrides: {} 关掉逐项覆盖。"
    ]


def apply_extra_fields(item: dict, extra_fields: dict) -> dict:
    """extra_fields 是 {字段名: {条目 id: 值}}。item 自身的同名字段优先。"""
    out = dict(item)
    item_id = item.get("id")
    for field_name, mapping in extra_fields.items():
        if not isinstance(mapping, dict):
            raise ValueError(
                f"extra_fields[{field_name!r}] 必须是 dict，实际 {type(mapping).__name__}"
            )
        if field_name in out:
            continue
        if item_id in mapping:
            out[field_name] = mapping[item_id]
    return out


def unsupported_field_findings(
    cat_name: str, backend, defaults: dict, assets: list, *, allow_degrade: bool = False
) -> "tuple[list, list]":
    """后端不认的字段，返回 (errors, warnings)。defaults 和每个 asset 都要查。

    只扫 defaults 的话，「只在某个 item 上配了 model」会静默失效 —— 字段
    确实送到了后端，但后端不认，而上层以为自己已经告警过了。

    **丢掉会改变任务含义的字段默认阻止执行。** 指定的模型、底图、风格参考被
    丢掉，仍然能产出图片，但那已经不是用户要求的那件事 —— 批量跑一次是按张
    烧钱的，「方便切后端试一下」不足以作为默认改变任务含义的理由。要试就用
    `--allow-degrade` 明确接受这次降级。`seed` 那类只影响可复现性的照旧告警。

    自定义后端的能力**未知**，两样都不报 —— 既不能说它不支持，也不该假装查过。
    """
    errors: list = []
    warnings: list = []
    supports = getattr(backend, "supports", None)
    if supports is None or not getattr(backend, "capability_known", True):
        return errors, warnings
    name = getattr(backend, "name", "?")

    def _record(where: str, key: str, value) -> None:
        hint = UNSUPPORTED_HINTS.get(key, "该后端不认这个字段。")
        if key in DEGRADE_TOLERANT or allow_degrade:
            tail = "已忽略。" if key in DEGRADE_TOLERANT else "已按 --allow-degrade 放行并忽略。"
            warnings.append(f"{where}: backend={name} 不支持 {key}（值 {value!r}），{tail}{hint}")
            return
        errors.append(
            f"{where}: backend={name} 不支持 {key}（值 {value!r}），"
            f"丢掉它产出的就不是你要的那件事了。{hint}"
            " 改配置，或加 --allow-degrade 明确接受这次降级。"
        )

    for key in sorted(k for k in defaults if k not in supports):
        _record(f"category={cat_name}", key, defaults[key])

    for asset in assets:
        payload = asset.payload if isinstance(asset, PlannedAsset) else asset
        unknown = [k for k in payload if k not in _PROTOCOL_KEYS and k not in supports]
        for key in sorted(unknown):
            _record(f"category={cat_name} item={payload.get('name')}", key, payload[key])

    return errors, warnings


def capability_errors(cat_name: str, backend, defaults: dict, assets: list) -> list:
    """按模型判定的能力冲突 —— `supports` 那种字段集合表达不了的。

    问的是后端自己（`backend.incompatibilities`），不是在这里重写一份
    「哪些模型走哪条 API」。规则重复两份，后端哪天改了判断标准，
    这里就开始说谎。新增后端不必改动本函数。
    """
    hook = getattr(backend, "incompatibilities", None)
    if hook is None:
        return []
    out: list = []
    for asset in assets:
        payload = asset.payload if isinstance(asset, PlannedAsset) else asset
        for msg in hook(defaults, payload):
            out.append(f"category {cat_name} item={payload.get('name')}: {msg}")
    return out


def _item_override(item: dict, overrides: "dict | None", param: str):
    """取这一条目对 `param` 的覆盖值。没有就返回 None。

    `overrides` 是 None 表示 category 没声明 `item_overrides` —— 退回旧的
    「同名即覆盖」。声明过就**只认声明的映射**，别的同名字段是普通数据。
    """
    source = param if overrides is None else overrides.get(param)
    if source is None:
        return None
    value = item.get(source)
    # 空值不算覆盖。CSV 的短行会把缺的字段补成空字符串 —— 一列 model 里
    # 有几行没填，不该给后端送个空模型名过去。
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return value


def _build_defaults(
    *, cat_spec: dict, global_style: dict, top_model: "str | None",
    project_root: Path, output_root: Path, adapter, plan: CategoryPlan,
) -> dict:
    skip_global = bool(cat_spec.get("skip_global_style", False))
    defaults: dict[str, Any] = {}

    if not skip_global:
        for key in ("chain", "preset"):
            if global_style.get(key) is not None:
                defaults[key] = global_style[key]

    # model 不走 skip_global_style：那个开关关的是风格，模型是后端配置。
    # 也因此 model 声明在 config 顶层而非 style 段里。
    model = cat_spec.get("model") or top_model
    if model:
        defaults["model"] = model

    for key in ("aspect_ratio", "seed", "chain", "preset"):
        if key in cat_spec:
            defaults[key] = cat_spec[key]

    # 参考图：category 自带的覆盖全局的内容层
    raw_refs = None
    label = None
    if "reference_paths" in cat_spec:
        raw_refs = cat_spec.get("reference_paths") or []
        label = f"category {plan.name} 的 reference_paths"
    elif not skip_global and (global_style.get("reference_paths") or []):
        raw_refs = global_style.get("reference_paths") or []
        label = "style.reference_paths"

    if raw_refs:
        resolved: list[str] = []
        for raw in raw_refs:
            try:
                full = resolve_reference(
                    str(raw), project_root=project_root,
                    output_root=output_root, adapter=adapter,
                )
            except ValueError as e:
                plan.errors.append(f"{label} 的路径解析失败（{raw}）：{e}")
                continue
            resolved.append(str(full))
            plan.input_paths.append((label, full))
        if resolved:
            defaults["reference_paths"] = resolved

    return defaults


def build_category_plan(
    ctx,
    cat_name: str,
    cat_spec: "dict | None" = None,
    *,
    name_filter: "set[str] | None" = None,
    limit: "int | None" = None,
    allow_degrade: bool = False,
) -> CategoryPlan:
    """把一个 category 算成完整计划。不抛异常 —— 问题都进 plan.errors。

    `ctx` 是 `asset_context.AssetContext`。`cat_spec` 不给就从 ctx 里取。
    """
    plan = CategoryPlan(name=cat_name)

    if cat_spec is None:
        cat_spec = (ctx.categories or {}).get(cat_name)
    if not isinstance(cat_spec, dict):
        plan.errors.append(
            f"category {cat_name!r} 的配置应为映射，实际是 {type(cat_spec).__name__}"
        )
        return plan

    project_root = ctx.project_root
    output_root = ctx.output_root
    adapter = ctx.adapter
    global_style = ctx.config.get("style") or {}
    if not isinstance(global_style, dict):
        plan.errors.append(f"style 应为映射，实际是 {type(global_style).__name__}")
        return plan

    # --- 输出目录。要在数据源之前算：目录越界是配置错，和有没有条目无关 ---
    out_subdir = cat_spec.get("output_subdir") or cat_name
    output_dir = (Path(output_root) / str(out_subdir)).resolve()
    try:
        # output_subdir 是「子目录名」，不是任意路径。`../../x` 会把图写到工程外面。
        output_dir.relative_to(Path(output_root).resolve())
    except ValueError:
        plan.errors.append(
            f"category {cat_name}: output_subdir={out_subdir!r} 解析到了 output_root "
            f"之外：{output_dir}。子目录只能往下，不能用 .. 往上或写绝对路径；"
            "要换根目录改 output_root。"
        )
        return plan
    plan.output_dir = output_dir

    # --- 数据源 ---
    try:
        items = load_data_source(cat_spec.get("data_source") or {}, project_root)
    except Exception as e:
        plan.errors.append(f"category {cat_name}: 数据源加载失败 —— {e}")
        return plan
    plan.total_items = len(items)

    if not items:
        plan.notes.append(
            f"category {cat_name}: 数据源没有条目，这个 category 不会产出任何图"
        )

    if name_filter is not None:
        items = [it for it in items if it.get("id") in name_filter]
        if not items:
            plan.notes.append(f"category {cat_name}: --names 过滤后无条目")

    if limit is not None and len(items) > limit:
        # 顺序要紧：先按 id 挑，再取前 N。反过来的话 --names 指定的条目
        # 可能根本不在前 N 里，两个参数一起用就等于 --names 失效了。
        plan.notes.append(
            f"category {cat_name}: 取前 {limit} 条（共 {len(items)} 条）"
        )
        items = items[:limit]

    # --- extra_fields ---
    extra_fields = cat_spec.get("extra_fields") or {}
    if extra_fields:
        try:
            items = [apply_extra_fields(it, extra_fields) for it in items]
        except ValueError as e:
            plan.errors.append(f"category {cat_name}: extra_fields 注入失败 —— {e}")
            return plan

    # --- defaults ---
    plan.defaults = _build_defaults(
        cat_spec=cat_spec, global_style=global_style,
        top_model=ctx.config.get("model"),
        project_root=project_root, output_root=output_root,
        adapter=adapter, plan=plan,
    )

    # --- 逐项覆盖：哪一列能当生成参数 ---
    overrides = resolve_item_overrides(cat_name, cat_spec, plan)
    if overrides is None:
        plan.governance.extend(implicit_override_governance(cat_name, items))
    else:
        for param, source in overrides.items():
            if items and not any(source in it for it in items):
                plan.notes.append(
                    f"category {cat_name}: item_overrides 声明了 {param} ← {source!r}，"
                    "但没有一个条目带这个字段 —— 检查是不是写错了列名"
                )

    # --- 模板 ---
    template = cat_spec.get("prompt_template")
    if not template:
        plan.errors.append(f"category {cat_name}: 缺 prompt_template")
        return plan

    skip_global = bool(cat_spec.get("skip_global_style", False))
    global_prefix = (global_style.get("prompt_prefix") or "") if not skip_global else ""
    global_suffix = (global_style.get("prompt_suffix") or "") if not skip_global else ""
    derived = cat_spec.get("derived_fields")
    ext = cat_spec.get("output_ext", "png")

    render_errors = _ErrorSink(plan.errors)
    seen_filenames: dict[str, str] = {}

    for item in items:
        item_id = item.get("id")
        if not item_id:
            render_errors.add(f"category {cat_name}: 有条目缺 id —— {item!r}")
            continue

        try:
            enriched = evaluate_derived(item, derived)
        except Exception as e:
            render_errors.add(
                f"category {cat_name} item={item_id!r}: derived_fields 算不出来 —— {e}"
            )
            continue

        try:
            rendered = render_template(template, enriched)
        except Exception as e:
            render_errors.add(
                f"category {cat_name} item={item_id!r}: prompt_template 渲染失败 —— {e}。"
                f"该条目可用的字段：{sorted(enriched)}"
            )
            continue

        try:
            full_prompt = compose_prompt(
                rendered,
                global_prefix=global_prefix,
                global_suffix=global_suffix,
                skip_global=skip_global,
            )
        except Exception as e:
            render_errors.add(
                f"category {cat_name} item={item_id!r}: 拼全局风格时失败 —— {e}"
            )
            continue

        filename = f"{item_id}.{ext}"
        prev = seen_filenames.get(filename)
        if prev is not None:
            render_errors.add(
                f"category {cat_name}: 两个条目输出同一个文件 {filename}"
                f"（{prev!r} 和 {item_id!r}）—— 后写的会覆盖先写的，"
                "检查数据源里的 id 是否重复"
            )
        seen_filenames[filename] = str(item_id)

        payload: dict[str, Any] = {
            "name": str(item_id),
            "filename": filename,
            "prompt": full_prompt,
        }

        # 编辑底图：item 级覆盖 category 级。只放 asset 不放 defaults ——
        # 上游 image-gen 的 Defaults 不解析 image，放 defaults 会被静默丢掉。
        item_image = _item_override(item, overrides, "image")
        raw_image = item_image or cat_spec.get("image")
        if raw_image:
            label = (f"category {cat_name} item={item_id!r} 的 image"
                     if item_image else f"category {cat_name} 的 image")
            try:
                full = resolve_reference(
                    str(raw_image), project_root=project_root,
                    output_root=output_root, adapter=adapter,
                )
            except ValueError as e:
                render_errors.add(f"{label} 的路径解析失败（{raw_image}）：{e}")
                continue
            payload["image"] = str(full)
            plan.input_paths.append((label, full))

        # item 级覆盖（优先级最高）。声明过 item_overrides 就只认声明的那几列，
        # 没声明才退回「同名即覆盖」—— 后者已经在上面记了治理问题。
        for key in ("model", "aspect_ratio", "seed"):
            value = _item_override(item, overrides, key)
            if value is not None:
                payload[key] = value

        plan.assets.append(
            PlannedAsset(
                item_id=str(item_id),
                filename=filename,
                prompt=full_prompt,
                output_path=output_dir / filename,
                payload=payload,
            )
        )

    render_errors.finish(f"category {cat_name}")

    # --- image 与 reference_paths 互斥 ---
    # 语义不同，上游 provider 本就互斥。早点报比发到后端才炸好 ——
    # 后者要等一轮网络往返，而且是按张烧钱的那种。
    if plan.defaults.get("reference_paths"):
        with_image = [a.item_id for a in plan.assets if a.payload.get("image")]
        if with_image:
            shown = ", ".join(with_image[:MAX_ITEM_ERRORS])
            more = (f"（另有 {len(with_image) - MAX_ITEM_ERRORS} 条）"
                    if len(with_image) > MAX_ITEM_ERRORS else "")
            plan.errors.append(
                f"category {cat_name}: 同时给了 image 和 reference_paths，两者互斥 —— "
                "image 是「编辑这张底图」，reference_paths 是「参考这些图的风格」。"
                f"涉及条目：{shown}{more}"
            )

    # --- 后端能力 ---
    unsupported_errors, unsupported_warnings = unsupported_field_findings(
        cat_name, ctx.backend, plan.defaults, plan.assets, allow_degrade=allow_degrade,
    )
    plan.errors.extend(unsupported_errors)
    plan.warnings.extend(unsupported_warnings)
    plan.errors.extend(
        capability_errors(cat_name, ctx.backend, plan.defaults, plan.assets)
    )

    return plan
