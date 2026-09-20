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
    # 这个适配器认的虚拟路径前缀；None = 不认任何前缀。
    # 用来判断「撞见某前缀时该不该建议切到这个 adapter」——
    # unreal 注册了却依然不认 /Game/，不能因为它在册就把人指过去。
    virtual_prefix: "str | None" = None


def _godot_hint(output_dir: Path) -> str | None:
    return scan_imports(output_dir).render_hint()


def _generic_detect(start: Path) -> Path | None:
    return None


def _unreal_detect(start: Path) -> "Path | None":
    """从 start 向上找 *.uproject；找到返回所在目录，否则 None。

    不做这一步的话，工程根会退化成 config 所在目录 —— config 放在
    tools/ 这类子目录时，所有相对路径的基准全错。
    """
    cur = Path(start).resolve()
    if cur.is_file():
        cur = cur.parent
    while True:
        if any(cur.glob("*.uproject")):
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


# 各引擎的虚拟根前缀。generic 模式下撞见任何一个都要报错，
# 否则 "res://art" 会被硬拼成 "<root>/res:/art" 这种没人想要的路径。
KNOWN_ENGINE_PREFIXES = {"res://": "godot", "/Game/": "unreal"}


def _generic_resolve(raw: str, root: Path) -> Path:
    """不认任何引擎前缀。绝对路径原样，相对路径接在 root 下。"""
    for prefix, engine in KNOWN_ENGINE_PREFIXES.items():
        if raw.startswith(prefix):
            # 认出前缀属于哪个引擎 ≠ 那个引擎的适配器认这个前缀。
            # unreal 注册了，但它同样拒绝 /Game/（那是导入后的资产路径，
            # 不是源文件路径）—— 建议人切过去等于把他指进死胡同。
            target = ADAPTERS.get(engine)
            if target is not None and target.virtual_prefix == prefix:
                # 必须说 adapter 而不是 engine：config 里已有 adapter 时再加个
                # engine 会触发「两者不一致」的冲突报错 —— 照着提示做反而更错。
                fix = ("把 config 的 adapter 改成 {}（若还留着旧的 engine 字段，"
                       "一并删掉，否则两者会冲突），或改用普通相对路径。").format(engine)
            elif target is not None:
                fix = (
                    "{} 适配也不认这个前缀（它指向导入后的资产，不是源文件）。"
                    "改用普通相对路径输出，引擎侧的资产导入另行处理。"
                ).format(engine)
            else:
                fix = (
                    "本 skill 目前没有 {} 适配（已注册：{}）。"
                    "改用普通相对路径输出，引擎侧的资产导入另行处理。"
                ).format(engine, " / ".join(sorted(ADAPTERS)))
            raise ValueError(
                "adapter=generic 不认识路径前缀 {!r}（那是 {} 的写法）：{}。{}"
                .format(prefix, engine, raw, fix)
            )
    p = Path(raw)
    return p if p.is_absolute() else (Path(root) / p).resolve()


def _unreal_resolve(raw: str, root: Path) -> Path:
    """unreal 不认任何虚拟前缀 —— 包括它自己的 /Game/。

    /Game/ 指向 Content/ 下的 .uasset，那是**导入后**的产物；本流水线
    产出的是导入前的源图片，两者不是一回事。把源图片写进 Content/，
    引擎既不认识裸 PNG，也会把那个目录搞乱。
    """
    if raw.startswith("/Game/"):
        raise ValueError(
            "/Game/ 是导入后的资产路径（对应 Content/ 下的 .uasset），"
            "而这里输出的是导入前的源图片：{}。"
            "改用相对工程根的普通路径（如 ArtSource/xxx），"
            "引擎侧的导入另行处理。".format(raw)
        )
    return _generic_resolve(raw, root)


def _unreal_hint(output_dir: Path) -> "str | None":
    """固定提示，不做检查。

    .uasset 是二进制，而且源图片到资产的对应关系写在项目各自的导入脚本里
    （destination_path 各处硬编码），没法反查「这张图导没导过」。
    """
    return (
        "[unreal] 图片已生成在 {} —— 它们是源文件，"
        "要在引擎里用还得走一次 UE 导入（在 Content/ 下生成 .uasset）。"
        .format(output_dir)
    )


GODOT = EngineAdapter(
    name="godot",
    detect_root=find_project_root,
    resolve_path=resolve_res_path,
    post_generate_hint=_godot_hint,
    virtual_prefix="res://",
)

UNREAL = EngineAdapter(
    name="unreal",
    detect_root=_unreal_detect,
    resolve_path=_unreal_resolve,
    post_generate_hint=_unreal_hint,
    virtual_prefix=None,        # 它连自己的 /Game/ 都不认，理由见 _unreal_resolve
)

GENERIC = EngineAdapter(
    name="generic",
    detect_root=_generic_detect,
    resolve_path=_generic_resolve,
    post_generate_hint=lambda _out: None,
)

ADAPTERS = {"godot": GODOT, "unreal": UNREAL, "generic": GENERIC}


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
