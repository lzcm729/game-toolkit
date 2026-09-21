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

    @property
    def categories(self) -> dict:
        return self.config.get("categories") or {}


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


def resolve_project_root(
    config_path: Path,
    config: dict,
    adapter,
    explicit: "Path | None" = None,
) -> "tuple[Path, str]":
    """定工程根，返回 (根, 来源说明)。

    四级，先到先得：
      1. 显式参数（`--project-root`）—— 只覆盖本次运行
      2. config 里的 `project_root`，相对 config 所在目录解析
      3. 适配器探测（Godot 找 project.godot，Unreal 找 *.uproject）
      4. 按 yaml 位置推断 —— 兜底。把 config 挪个子目录，根就变了

    第 4 条带一条约定：yaml 放在 `assets/` 下时，根是再上一级。这是
    `assets/asset-config.yaml` 这个默认位置的直接推论。
    """
    if explicit is not None:
        return Path(explicit).resolve(), "显式参数 --project-root"

    declared = config.get("project_root")
    if declared:
        return (
            (config_path.parent / str(declared)).resolve(),
            f"config 的 project_root: {declared!r}",
        )

    found = adapter.detect_root(config_path.parent)
    if found is not None:
        return Path(found), f"adapter={getattr(adapter, 'name', '?')} 探测"

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

    try:
        adapter = engine_adapter.select(config, config_path.parent)
    except ValueError as e:
        raise ContextError(str(e)) from e

    project_root, source = resolve_project_root(
        config_path, config, adapter, explicit_project_root
    )
    output_root = resolve_output_root(config, project_root, adapter)

    try:
        backend = image_backend.select(config, project_root)
    except ValueError as e:
        raise ContextError(str(e)) from e

    return AssetContext(
        config_path=config_path,
        config=config,
        adapter=adapter,
        project_root=project_root,
        project_root_source=source,
        output_root=output_root,
        backend=backend,
    )
