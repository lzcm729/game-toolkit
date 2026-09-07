#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引擎适配层：把「引擎特有的路径与导入规则」从通用流水线里分出来。

通用的部分（数据源加载、prompt 渲染、批量调度、reference_paths 的两种基准）
不属于任何引擎，留在 generate_assets.py。这里只放**换引擎就得改**的三件事：

  1. 项目根怎么找        —— Godot 看 project.godot；其他引擎有自己的工程文件
  2. 路径前缀怎么解析    —— Godot 的 `res://`；其他引擎有自己的虚拟根
  3. 生成完要不要提示    —— Godot 需要编辑器导入生成 .import；其他引擎未必

新增一个引擎 = 加一个 EngineAdapter 实例并注册，不用改主流程。
`generic` 是保底实现：不认任何前缀、不做导入检查，任何引擎的项目都能跑通基本流程。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from godot_utils import find_project_root, is_godot_project, resolve_res_path, scan_imports


@dataclass(frozen=True)
class EngineAdapter:
    name: str
    # 从 config 所在目录往上找工程根；找不到返回 None，由调用方 fallback
    detect_root: Callable[[Path], "Path | None"]
    # 解析 output_root / reference 里的路径（含引擎虚拟前缀）
    resolve_path: Callable[[str, Path], Path]
    # 生成结束后的提示；返回 None 表示这个引擎不需要
    post_generate_hint: Callable[[Path], "str | None"]


def _godot_hint(output_dir: Path) -> str | None:
    return scan_imports(output_dir).render_hint()


def _generic_detect(start: Path) -> Path | None:
    return None


# 各引擎的虚拟根前缀。generic 模式下撞见任何一个都要报错，
# 否则 "res://art" 会被硬拼成 "<root>/res:/art" 这种没人想要的路径。
KNOWN_ENGINE_PREFIXES = {"res://": "godot", "/Game/": "unreal"}


def _generic_resolve(raw: str, root: Path) -> Path:
    """不认任何引擎前缀。绝对路径原样，相对路径接在 root 下。"""
    for prefix, engine in KNOWN_ENGINE_PREFIXES.items():
        if raw.startswith(prefix):
            # 认出前缀属于哪个引擎 ≠ 本 skill 支持那个引擎的操作。
            # 只有注册了适配才建议改 engine，否则会把人指进「未知的 engine」。
            if engine in ADAPTERS:
                fix = "把 config 的 engine 设成 {}，或改用普通相对路径。".format(engine)
            else:
                fix = (
                    "本 skill 目前没有 {} 适配（已注册：{}）。"
                    "改用普通相对路径输出，引擎侧的资产导入另行处理。"
                ).format(engine, " / ".join(sorted(ADAPTERS)))
            raise ValueError(
                "engine=generic 不认识路径前缀 {!r}（那是 {} 的写法）：{}。{}"
                .format(prefix, engine, raw, fix)
            )
    p = Path(raw)
    return p if p.is_absolute() else (Path(root) / p).resolve()


GODOT = EngineAdapter(
    name="godot",
    detect_root=find_project_root,
    resolve_path=resolve_res_path,
    post_generate_hint=_godot_hint,
)

GENERIC = EngineAdapter(
    name="generic",
    detect_root=_generic_detect,
    resolve_path=_generic_resolve,
    post_generate_hint=lambda _out: None,
)

ADAPTERS = {"godot": GODOT, "generic": GENERIC}


def select(config: dict, config_dir: Path) -> EngineAdapter:
    """选适配器。`adapter` 优先，`engine` 是兼容期的旧名。

    这两个词指的不是一回事，混用过一次值得写下来：
      - **引擎身份**（项目用的是 UE 还是 Godot）属于项目环境声明，人工填，见
        `game-toolkit:layer-contracts` 的「项目环境声明」。
      - **适配器**（本生成器能提供哪套路径与导入规则）是这里选的东西。
        `generic` 是一个适配器，不是一种引擎 —— UE 项目用 generic 完全正常。

    旧配置里的 `engine:` 按 `adapter:` 处理；两者同时存在且不同则报错，
    不替用户猜哪个是他真正想要的。
    """
    adapter_name = (config.get("adapter") or "").strip().lower()
    legacy_name = (config.get("engine") or "").strip().lower()

    if adapter_name and legacy_name and adapter_name != legacy_name:
        raise ValueError(
            "config 同时有 adapter={!r} 和 engine={!r} 且不一致。"
            "engine 是 adapter 的旧名，请只保留 adapter。".format(adapter_name, legacy_name)
        )
    declared = adapter_name or legacy_name
    if declared:
        if declared not in ADAPTERS:
            raise ValueError(
                "未知的 adapter: {!r}（可选：{}）。"
                "注意这里选的是本生成器的适配能力，不是项目用的引擎 —— "
                "没有对应适配时用 generic。".format(declared, " / ".join(sorted(ADAPTERS)))
            )
        return ADAPTERS[declared]

    found = find_project_root(config_dir)
    return GODOT if (found is not None and is_godot_project(found)) else GENERIC
