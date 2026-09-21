#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目上下文解析 —— 校验器和生成器共用这一份。

3.16.0 之前两边各解析一次工程根：生成器走四级回退（显式参数 → config 的
`project_root` → 适配器探测 → 按 yaml 位置推断），校验器直接取 config 的
父目录。**同一份配置因此可能检查一个位置、跑另一个位置**，而所有相对路径
（output_root、reference_paths、数据源）都挂在这个根上。

所以入口只有一个：`load_context()`。想覆盖本次运行就传 `explicit_project_root`，
覆盖来源会记在 `project_root_source` 里，由调用方报出来 —— 悄悄换基准和
解析错基准一样难查。

不读 `game-toolkit.yaml`：那是项目环境声明，接入它是独立的一步。核心生成
逻辑和后端仍然不必知道它存在，真要接也只接在这一层。
"""
from __future__ import annotations

import difflib
import sys
from dataclasses import dataclass
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

import engine_adapter  # noqa: E402
import image_backend  # noqa: E402

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - 启动期检测
    yaml = None  # type: ignore[assignment]


# 默认搜索位置。顺序即优先级。
DEFAULT_CONFIG_PATHS = (
    Path("asset-config.yaml"),
    Path("assets/asset-config.yaml"),
)


class ContextError(ValueError):
    """上下文解析失败。消息是写给人看的，调用方直接打印即可。"""


@dataclass(frozen=True)
class AssetContext:
    """一次运行/校验所依据的全部环境事实。

    构造它就等于把 yaml 读完、根定好、适配器和后端选好。后续每一步都从
    这里取，不再各自推断。
    """

    config_path: Path
    config: dict
    adapter: object              # engine_adapter.EngineAdapter
    project_root: Path
    project_root_source: str     # 这个根是怎么定下来的，用于报告
    output_root: Path
    backend: object              # image_backend.ImageBackend
    # 工程根**本身**是哪种引擎工程（探测所得，不是用户声明）。
    # 导入提示按它给 —— UE 项目用 filesystem 适配器照样该拿到那句提示。
    project_kind: "str | None" = None
    # 解析过程中值得说一句、但不影响成败的事。调用方自己决定怎么打。
    notes: tuple = ()

    @property
    def categories(self) -> dict:
        return self.config.get("categories") or {}

    def import_hint(self, output_dir: Path) -> "str | None":
        return engine_adapter.import_hint(self.project_kind, output_dir)


def locate_config(explicit: "Path | None", *, cwd: "Path | None" = None) -> "Path | None":
    """找配置文件。显式给了就只认那一个（不存在返回 None，不去别处找）。"""
    if explicit is not None:
        p = Path(explicit)
        return p if p.exists() else None
    base = Path(cwd) if cwd is not None else Path.cwd()
    for rel in DEFAULT_CONFIG_PATHS:
        cand = base / rel
        if cand.exists():
            return cand
    return None


def default_config_hint() -> str:
    return " / ".join(str(p) for p in DEFAULT_CONFIG_PATHS)


def load_config(config_path: Path) -> dict:
    """读 yaml。语法错误带行列 —— 让人能直接跳到那一行，而不是重新通读全文。"""
    if yaml is None:  # pragma: no cover - 启动期检测
        raise ContextError("缺少 PyYAML。请装：pip install pyyaml")
    config_path = Path(config_path)
    if not config_path.exists():
        raise ContextError(f"配置文件不存在：{config_path}")
    try:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = f" 第 {mark.line + 1} 行第 {mark.column + 1} 列" if mark else ""
        raise ContextError(
            f"{config_path} 解析失败{where}：{getattr(e, 'problem', e)}"
        ) from e
    except OSError as e:
        raise ContextError(f"{config_path} 读不了：{e}") from e
    if config is None:
        config = {}
    if not isinstance(config, dict):
        raise ContextError(
            f"{config_path} 的顶层必须是映射，实际是 {type(config).__name__}"
        )
    return config


# -------------------- 配置形状 --------------------
#
# 三个入口（生成器的 list / 生成器主流程 / 校验器）以前各有一份，互相之间
# 结论一致 —— **因为盲区相同**：都只查 spec 是不是映射，从不查 category
# 名字的类型。而校验之后的代码默认名字是字符串（拼目录、`', '.join`、
# `f"{name:<14}"`）。YAML 1.1 把不加引号的 `on:` 解析成布尔、`1:` 成整数、
# `~:` 成空值，于是校验退 0、生成器要么崩要么把图写进 `art/True/`。
#
# 三份各补一次也行，但那正是「同一件事有三份实现」的代价。收成这一处。

def category_name_problem(name) -> "str | None":
    """category 名字能不能用。能用返回 None。"""
    if isinstance(name, str):
        if name.strip():
            return None
        return (
            "有个 category 的名字是空字符串 —— 没有 output_subdir 时它会直接"
            "写进 output_root 根目录，和别的 category 混在一起。给它起个名字。"
        )
    if isinstance(name, bool):
        why = "YAML 1.1 会把不加引号的 on / off / yes / no / true / false 解析成布尔值"
    elif name is None:
        why = "YAML 把不加引号的 ~ 或 null 解析成空值"
    elif isinstance(name, (int, float)):
        why = "YAML 把不加引号的纯数字解析成数字"
    else:
        why = f"YAML 把它解析成了 {type(name).__name__}（日期之类）"
    return (
        f"category 名 {name!r} 不是字符串 —— {why}。给名字加引号，"
        '例如 "on": 而不是 on:。不加的话，按名指定会直接崩，'
        f"走 all 会把图写进一个叫 {name} 的目录。"
    )


def category_problems(cats, *, allow_empty: bool = False) -> list:
    """categories 的形状问题，全部列出。空列表 = 没问题。

    `allow_empty` 给 `list` 命令用：空配置它打 "(empty config)"，不算错。
    """
    if not cats:
        if allow_empty:
            return []
        return ["config 里没有 categories —— 至少要有一个 category 才知道生成什么"]
    if not isinstance(cats, dict):
        return [f"categories 应为映射（名字 → 配置），实际是 {type(cats).__name__}"]
    out: list = []
    for name, spec in cats.items():
        problem = category_name_problem(name)
        if problem is not None:
            out.append(problem)
            continue
        if not isinstance(spec, dict):
            out.append(
                f"category {name!r} 的配置应为映射，实际是 {type(spec).__name__}（{spec!r}）"
            )
    return out


# -------------------- 不认识的字段 --------------------
#
# 计划层只取认得的字段，剩下的没人看。于是 `aspect_ration: "4:3"`（拼错）
# 校验照样退 0，生成时静默退回默认比例 —— 冷启动评测第一次正式运行就撞上了。
#
# 表是从代码里所有读配置的地方 grep 出来的，不是凭记忆写的。漏一个真字段，
# 就会把合法配置误判成拼错；所以新增字段时这里也要加。

KNOWN_FIELDS = {
    "top": frozenset({
        "$schema_version", "adapter", "engine", "project_root", "output_root",
        "backend", "model", "style", "categories",
    }),
    "style": frozenset({
        "prompt_prefix", "prompt_suffix", "reference_paths", "chain", "preset",
    }),
    "category": frozenset({
        "desc", "data_source", "prompt_template", "derived_fields", "extra_fields",
        "item_overrides", "skip_global_style", "output_subdir", "output_ext",
        "aspect_ratio", "seed", "chain", "preset", "model", "image", "reference_paths",
    }),
    "data_source": frozenset({
        "type", "path", "items", "id_column", "columns", "encoding", "filter",
    }),
}

_LEVEL_LABEL = {
    "top": "顶层", "style": "style 段", "category": "category 里", "data_source": "data_source 里",
}


def field_problems(mapping, level: str, where: str) -> "tuple[list, list]":
    """一层映射里不认识的字段，返回 (errors, notes)。三种情况分开：

    - **放错层**（是真字段，但这一层不认）→ 错。写在这里等于没写，比如顶层的
      `aspect_ratio` —— 它只在 category 里生效
    - **拼错**（和这一层某个字段很像）→ 错，并说出像哪个。拼错的字段不起任何作用
    - **完全陌生** → 只提示。配置文件不只属于一个消费者，别的工具可能在这里放
      自己的字段，一律报错就把它们挡死了
    """
    errors: list = []
    notes: list = []
    if not isinstance(mapping, dict):
        return errors, notes
    known = KNOWN_FIELDS[level]
    lowered = {k.lower(): k for k in known}
    for key in mapping:
        if not isinstance(key, str) or key in known:
            continue
        elsewhere = [lvl for lvl, ks in KNOWN_FIELDS.items() if lvl != level and key in ks]
        if elsewhere:
            places = "、".join(_LEVEL_LABEL[lvl] for lvl in elsewhere)
            errors.append(
                f"{where}: {key!r} 写在{_LEVEL_LABEL[level]}不生效 —— 它只在{places}起作用，"
                "写在这里等于没写"
            )
            continue
        close = difflib.get_close_matches(key.lower(), list(lowered), n=1, cutoff=0.75)
        if close:
            errors.append(
                f"{where}: 不认识的字段 {key!r}，像是 {lowered[close[0]]!r} 拼错了 —— "
                "拼错的字段不起任何作用，生成时会静默用默认值"
            )
        else:
            notes.append(
                f"{where}: 不认识的字段 {key!r}，本工具不会用它"
                "（是别的工具放的就可以不管这条）"
            )
    return errors, notes


def config_field_problems(config: dict) -> "tuple[list, list]":
    """顶层与 style 段。category 那一层由计划层逐个查 —— 只跑一个 category 时
    只该报它自己的问题。"""
    errors, notes = field_problems(config, "top", "顶层")
    e, n = field_problems(config.get("style"), "style", "style")
    return errors + e, notes + n


def style_problem(style) -> "str | None":
    """style 段的形状。缺省（null / 空）就是没有全局风格，不算错。"""
    if not style or isinstance(style, dict):
        return None
    return f"style 应为映射，实际是 {type(style).__name__}"


def resolve_project_root(
    config_path: Path,
    config: dict,
    detected: "tuple[str | None, Path | None]" = (None, None),
    explicit: "Path | None" = None,
) -> "tuple[Path, str]":
    """定工程根，返回 (根, 来源说明)。

    四级，先到先得：
      1. 显式参数（`--project-root`）—— 只覆盖本次运行
      2. config 里的 `project_root`，相对 config 所在目录解析
      3. 工程标志探测（`project.godot` / `*.uproject`）
      4. 按 yaml 位置推断 —— 兜底。把 config 挪个子目录，根就变了

    第 4 条带一条约定：yaml 放在 `assets/` 下时，根是再上一级。这是
    `assets/asset-config.yaml` 这个默认位置的直接推论。

    **第 3 条不问适配器。** 工程根在选路径处理方式之前就该定下来 ——
    否则「把 adapter 从 unreal 换成 filesystem」会顺带换掉工程根，
    而那两件事在概念上毫无关系。
    """
    if explicit is not None:
        return Path(explicit).resolve(), "显式参数 --project-root"

    declared = config.get("project_root")
    if declared:
        return (
            (config_path.parent / str(declared)).resolve(),
            f"config 的 project_root: {declared!r}",
        )

    kind, found = detected
    if found is not None:
        return Path(found), f"探测到 {kind} 工程"

    parent = config_path.parent.resolve()
    if parent.name == "assets":
        return parent.parent, "按 config 位置推断（assets/ 的上一级）"
    return parent, "按 config 位置推断（config 所在目录）"


def resolve_output_root(config: dict, project_root: Path, adapter) -> Path:
    raw = config.get("output_root", "assets/art")
    if not isinstance(raw, str):
        raise ContextError(
            f"output_root 应为字符串，实际是 {type(raw).__name__}（{raw!r}）"
        )
    try:
        return adapter.resolve_path(raw, project_root)
    except ValueError as e:
        raise ContextError(f"output_root 解析失败：{e}") from e


def load_context(
    config_path: Path,
    *,
    explicit_project_root: "Path | None" = None,
    config: "dict | None" = None,
) -> AssetContext:
    """把一份 asset-config.yaml 解析成完整上下文。

    失败一律抛 `ContextError`，消息可以直接打给人看。
    `config` 参数只给「已经读好 yaml、不想再读一遍」的调用方用。
    """
    config_path = Path(config_path)
    if config is None:
        config = load_config(config_path)

    # 单向流，没有环：根 → 工程类型 → 适配器 → 输出根。
    # 以前是「先选适配器、再用适配器找根」，于是换适配器会换掉根。
    detected = engine_adapter.detect_project(config_path.parent)
    project_root, source = resolve_project_root(
        config_path, config, detected, explicit_project_root
    )
    kind = engine_adapter.project_kind(project_root)

    notes: list = []
    try:
        adapter = engine_adapter.select(config, kind)
        note = engine_adapter.legacy_note(config)
    except ValueError as e:
        raise ContextError(str(e)) from e
    if note:
        notes.append(note)

    # 没声明适配器时，说清这次按什么解析路径 —— 默认值不该是个哑谜。
    # 声明了就不说：那是人自己选的，重复一遍没有信息量。
    if not engine_adapter.declared_adapter(config) and adapter.name != "godot":
        if kind is None:
            notes.append(
                f"adapter={adapter.name}（{project_root} 下没有识别到 Godot / Unreal 工程）："
                "路径按普通相对路径解析。在 config 里显式写 adapter: filesystem "
                "可以关掉这条探测（engine: 是旧名，别再用）。"
            )
        else:
            notes.append(
                f"探测到 {kind} 工程，adapter={adapter.name}：路径按普通相对路径解析。"
                "这是正常默认 —— 只有 Godot 需要一套自己的路径写法。"
            )

    output_root = resolve_output_root(config, project_root, adapter)

    try:
        backend = image_backend.select(config, project_root)
    except ValueError as e:
        raise ContextError(str(e)) from e

    if not getattr(backend, "capability_known", True):
        notes.append(
            f"backend={backend.name} 的能力未知（自定义脚本），本次不做降级检查。"
            "它若丢弃了配置里的字段，必须自己出声 —— 见 BACKEND-PROTOCOL.md。"
        )

    return AssetContext(
        config_path=config_path,
        config=config,
        adapter=adapter,
        project_root=project_root,
        project_root_source=source,
        output_root=output_root,
        backend=backend,
        project_kind=kind,
        notes=tuple(notes),
    )
