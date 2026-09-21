#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""引擎相关的知识：工程怎么认、路径前缀怎么解析、生成完要不要提示导入。

这三件事**互相独立**，3.17.0 之前被捆在一个 `EngineAdapter` 里，代价是
「切换路径处理能力」会顺带换掉工程根 —— 于是「UE 项目用普通文件路径完全合理」
这句话，在 config 放子目录时变成行为不等价。现在分开：

  1. `detect_project()` / `project_kind()` —— 工程是什么、根在哪。
     **与选哪个适配器无关**，工程根在选路径处理方式之前就该定下来。
  2. `EngineAdapter` —— 只管路径：认哪个虚拟前缀、怎么解析成绝对路径。
  3. `import_hint()` —— 生成后的导入说明，按**探测到的工程**给，
     不按用户选的适配器给。UE 项目用 filesystem 照样拿得到那句提示。

注册的适配器只有两个，**名字说的是路径系统**：`godot`（Godot 的 `res://` 路径）
和 `filesystem`（普通文件系统路径，不认任何虚拟前缀）。

`unreal` 和 `generic` 是兼容值，都等价于 filesystem，详见 `LEGACY_ADAPTERS`。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from godot_utils import is_godot_project, resolve_res_path, scan_imports


@dataclass(frozen=True)
class EngineAdapter:
    """一套路径解析规则。只管路径 —— 工程根和导入提示都不在这里。"""

    name: str
    # 解析 output_root / reference 里的路径（含引擎虚拟前缀）
    resolve_path: Callable[[str, Path], Path]
    # 这个适配器认的虚拟路径前缀；None = 不认任何前缀
    virtual_prefix: "str | None" = None


# -------------------- 工程探测 --------------------

def project_kind(root: Path) -> "str | None":
    """这个目录本身是哪种引擎工程。不向上找。

    探测结果只说明「这里有什么」，不能自动升格成项目的人工声明。
    """
    root = Path(root)
    if is_godot_project(root):
        return "godot"
    try:
        if any(root.glob("*.uproject")):
            return "unreal"
    except OSError:  # pragma: no cover - 路径不可读时当作没探到
        return None
    return None


def detect_project(start: Path) -> "tuple[str | None, Path | None]":
    """从 start 向上找工程标志，返回 (引擎名, 工程根)。

    一次走完，每层把所有标志都看一遍 —— 不是每种引擎各走一趟。分开走的话，
    嵌在 UE 仓库里的 Godot 子工程会被两次搜索给出不同答案。

    start 可以是文件或目录。都找不到返回 (None, None)，由调用方兜底。
    """
    cur = Path(start).resolve()
    if cur.is_file():
        cur = cur.parent
    while True:
        kind = project_kind(cur)
        if kind is not None:
            return kind, cur
        if cur.parent == cur:
            return None, None
        cur = cur.parent


def import_hint(kind: "str | None", output_dir: Path) -> "str | None":
    """生成结束后的导入说明。按探测到的工程给，不按适配器给。

    说的是**生成与导入的边界**，不是检查结果 —— Godot 那条会去数 `.import`
    文件，UE 这条不能：`.uasset` 是二进制，源图片到资产的对应关系写在项目
    各自的导入脚本里（`destination_path` 各处硬编码），没法反查。
    """
    if kind == "godot":
        return scan_imports(output_dir).render_hint()
    if kind == "unreal":
        return (
            "[unreal] 图片已生成在 {} —— 它们是源文件，要在引擎里用还得走一次 "
            "UE 导入（在 Content/ 下生成 .uasset）。本工具不检查导入状态，"
            "按项目现有的导入流程处理。".format(output_dir)
        )
    return None


# -------------------- 路径解析 --------------------

# 各引擎的虚拟根前缀。filesystem 模式下撞见任何一个都要报错，
# 否则 "res://art" 会被硬拼成 "<root>/res:/art" 这种没人想要的路径。
KNOWN_ENGINE_PREFIXES = {"res://": "godot", "/Game/": "unreal"}

# 有些前缀不是「换个适配器就能用」，而是**根本不该出现在源文件配置里**。
# 这类得单独说清楚，否则人会照着「没有 X 适配」的提示去找一个并不存在的开关。
_PREFIX_REJECTIONS = {
    "/Game/": (
        "/Game/ 是**导入后**的资产路径（对应 Content/ 下的 .uasset），"
        "而这里配的是导入前的源图片 —— 没有任何适配器认它，将来也不会有。"
        "改用普通相对路径（相对工程根，如 ArtSource/xxx），引擎侧的导入另行处理。"
    ),
}


def _filesystem_resolve(raw: str, root: Path) -> Path:
    """不认任何引擎前缀。绝对路径原样，相对路径接在 root 下。"""
    for prefix, engine in KNOWN_ENGINE_PREFIXES.items():
        if not raw.startswith(prefix):
            continue
        fix = _PREFIX_REJECTIONS.get(prefix)
        if fix is None:
            target = ADAPTERS.get(engine)
            if target is not None and target.virtual_prefix == prefix:
                # 必须说 adapter 而不是 engine：config 里已有 adapter 时再加个
                # engine 会触发「两者不一致」的冲突报错 —— 照着提示做反而更错。
                fix = ("把 config 的 adapter 改成 {}（若还留着旧的 engine 字段，"
                       "一并删掉，否则两者会冲突），或改用普通相对路径。").format(engine)
            else:
                fix = (
                    "本 skill 目前没有 {} 的路径适配（已注册：{}）。"
                    "改用普通相对路径输出，引擎侧的资产导入另行处理。"
                ).format(engine, " / ".join(sorted(ADAPTERS)))
        raise ValueError(
            "adapter={} 不认识路径前缀 {!r}（那是 {} 的写法）：{}。{}"
            .format("filesystem", prefix, engine, raw, fix)
        )
    p = Path(raw)
    return p if p.is_absolute() else (Path(root) / p).resolve()


GODOT = EngineAdapter(
    name="godot",
    resolve_path=resolve_res_path,
    virtual_prefix="res://",
)

FILESYSTEM = EngineAdapter(
    name="filesystem",
    resolve_path=_filesystem_resolve,
    virtual_prefix=None,
)

ADAPTERS = {"godot": GODOT, "filesystem": FILESYSTEM}

# 兼容值 —— 仍然接受，但不再是推荐写法。两个都 5.0.0 移除（见 PLANNED.md）。
# 在那之前每次都打一条提示说明等价关系 —— 提示本身是成本，不该永远背着。
#
# `unreal`（3.17.0 降级）：当年做三件事，现在各有归属 —— 找 *.uproject 归
# `detect_project`，拒绝 `/Game/` 归通用路径校验，提醒走 UE 导入归
# `import_hint`（按探测到的工程给）。剩下的路径解析和 filesystem 一模一样。
#
# `generic`（4.2.0 改名）：行为一点没变，改的是名字。它读起来像「通用的、
# 没认出引擎」，于是写着 `adapter: generic` 的 UE 项目看上去像配错了。而这个
# 字段选的从来是**路径系统**，不是引擎。
LEGACY_ADAPTERS = {"unreal": "filesystem", "generic": "filesystem"}

_LEGACY_WHY = {
    "unreal": (
        "它当年多做的工程根探测已经归入通用的工程探测（对所有适配器都生效），"
        "导入提示也改成按探测到的工程给"
    ),
    "generic": (
        "只是改了名 —— 这个字段选的是路径系统，不是引擎；generic 读起来像"
        "「没认出引擎」，UE 项目写着它看上去像配错了"
    ),
}


# -------------------- 选择 --------------------

def declared_adapter(config: dict) -> "str | None":
    """config 里声明的适配器名（归一化）。`engine` 是 `adapter` 的旧名。

    这两个词指的不是一回事，混用过一次值得写下来：
      - **引擎身份**（项目用的是 UE 还是 Godot）属于项目环境声明，人工填，见
        `game-toolkit:layer-contracts` 的「项目环境声明」。
      - **适配器**（本生成器提供哪套路径规则）是这里选的东西。
        `filesystem` 是一种路径系统，不是一种引擎 —— UE 项目用它完全正常。

    两者同时存在且不同则报错，不替用户猜哪个是他真正想要的。
    """
    adapter_name = (config.get("adapter") or "").strip().lower()
    legacy_name = (config.get("engine") or "").strip().lower()
    # 比较的是**归一化之后**的值。迁移期里 `adapter: filesystem` 配旧字段
    # `engine: generic` 意思完全一样，按字符串比就会误报「不一致」。
    if (adapter_name and legacy_name
            and _canonical(adapter_name) != _canonical(legacy_name)):
        raise ValueError(
            "config 同时有 adapter={!r} 和 engine={!r} 且不一致。"
            "engine 是 adapter 的旧名，请只保留 adapter。".format(adapter_name, legacy_name)
        )
    return adapter_name or legacy_name or None


def _canonical(name: str) -> str:
    return LEGACY_ADAPTERS.get(name, name)


def legacy_note(config: dict) -> "str | None":
    """声明的是兼容值时，说一句它现在等价于什么。不报错。"""
    declared = declared_adapter(config)
    if declared is None or declared not in LEGACY_ADAPTERS:
        return None
    target = LEGACY_ADAPTERS[declared]
    return (
        "adapter: {} 现在是兼容值，等价于 {} —— {}。改成 adapter: {}，行为不变；"
        "5.0.0 起旧值不再接受。".format(declared, target, _LEGACY_WHY[declared], target)
    )


def select(config: dict, detected_kind: "str | None" = None) -> EngineAdapter:
    """选适配器。声明优先；没声明就按探测到的工程给默认。

    多对一是正常的：只有 Godot 需要一套自己的路径规则（`res://`），
    UE / Unity / 自研 / 没探到 全都用普通文件系统路径。`filesystem`
    说的是路径系统，不是「这个项目没有引擎」。
    """
    declared = declared_adapter(config)
    if declared:
        if declared in LEGACY_ADAPTERS:
            return ADAPTERS[LEGACY_ADAPTERS[declared]]
        if declared not in ADAPTERS:
            raise ValueError(
                "未知的 adapter: {!r}（可选：{}；{} 是仍然接受的兼容值）。"
                "注意这里选的是本生成器的路径适配，不是项目用的引擎 —— "
                "没有对应的路径系统时用 filesystem。".format(
                    declared, " / ".join(sorted(ADAPTERS)),
                    " / ".join(sorted(LEGACY_ADAPTERS)),
                )
            )
        return ADAPTERS[declared]

    return GODOT if detected_kind == "godot" else FILESYSTEM
