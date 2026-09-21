#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生图后端层：把「实际生图用哪个程序」从流水线里分出来。

插拔的单位是**一个可执行脚本 + 一套 CLI 约定**，不是 skill。本模块只负责
挑出那个脚本；怎么调、怎么读结果在 generate_assets.py，协议写在
BACKEND-PROTOCOL.md。

注册表里的条目是同构的，都只是「一个脚本路径」：
  - image-gen 指向外部用户级 skill 里的脚本（可能不存在）
  - laozhang  指向本插件自带的脚本（随插件走，必定存在）
注册表不关心那个路径背后是不是 skill。

新增一个内置后端 = 加一个 ImageBackend 实例并注册，不用改主流程。
"""
from __future__ import annotations

import dataclasses
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# 后端可能收到的全部可选字段（`image` 只出现在 asset 上，别的可出现在 defaults）。
# 内置后端逐个声明认哪些；自定义后端的能力**未知**，走 capability_known=False。
ALL_FIELDS = frozenset({
    "chain", "preset", "model", "reference_paths", "aspect_ratio", "seed", "image",
})

SCRIPT_ENV = "IMAGE_GEN_SCRIPT"


def _no_incompatibilities(defaults: dict, asset: dict) -> list:
    return []


@dataclass(frozen=True)
class ImageBackend:
    name: str
    # 解析入口脚本；找不到返回 None，由调用方打 install_hint
    resolve_script: Callable[[], "Path | None"]
    # 认得的 defaults 字段，用于降级告警
    supports: frozenset
    # 找不到脚本时告诉人怎么装
    install_hint: str
    # 这个后端的能力是不是已知的。自定义后端（脚本路径 / 环境变量指定）填 False：
    # 我们没见过它，既不能说「不支持 chain」，也不该假装「全部支持」。
    # 「没发现」和「没看」得分得开。
    capability_known: bool = True
    # 按模型判定的能力冲突 —— `supports` 那种字段集合表达不了的那类。
    # 收 (defaults, asset)，返回人话消息列表；空列表 = 没发现冲突。
    #
    # 这是后端对外的能力声明入口。有了它，上层校验不必再按后端名特判、
    # 也不必伸手去拿后端的私有函数 —— 新增后端只要填这一格。
    incompatibilities: Callable[[dict, dict], list] = _no_incompatibilities


def _existing(p: Path) -> "Path | None":
    return p if p.exists() else None


def _effective(defaults: dict, asset: dict, key: str):
    """asset 级覆盖 defaults —— 和 BACKEND-PROTOCOL.md 的优先级一致。"""
    value = asset.get(key)
    return value if value is not None else defaults.get(key)


def _laozhang_rules():
    """拿后端自己的判断规则。拿不到返回 None。

    「哪个模型走哪条 API」「哪些比例是原生的」都问后端要，不在这里重写一份 ——
    规则重复两份，后端哪天改了标准，校验就开始说谎。
    """
    backends_dir = Path(__file__).resolve().parent / "backends"
    if str(backends_dir) not in sys.path:
        sys.path.insert(0, str(backends_dir))
    try:
        from laozhang_backend import (  # type: ignore
            _OPENAI_EXACT_RATIOS, _is_openai_style,
        )
    except ImportError:
        return None
    return _is_openai_style, _OPENAI_EXACT_RATIOS


def _laozhang_incompatibilities(defaults: dict, asset: dict) -> list:
    """laozhang 自己知道、但字段集合表达不了的那些降级。

    三条，都是「配了但不会按你要的生效」：
      - gpt-image-* 走 OpenAI 路径，没有多图 reference
      - gpt-image-* 只原生支持 1:1 / 2:3 / 3:2，别的比例会被就近裁切
      - edit 模式（给了 image）输出尺寸跟随底图，aspect_ratio 不生效

    后两条后端运行时会 `[warn]`，但那是**图已经在生成**的时候了 ——
    批量按张烧钱，该在发请求之前说。
    """
    refs = _effective(defaults, asset, "reference_paths")
    model = _effective(defaults, asset, "model")
    image = asset.get("image")
    ratio = _effective(defaults, asset, "aspect_ratio")

    if not (refs or ratio):
        return []

    rules = _laozhang_rules()
    if rules is None:
        # 不能静默跳过 —— 「没发现」和「没看」得分开，这是本模块自己立的规矩
        return [
            "读不到 laozhang 后端的判断规则（backends/laozhang_backend.py 导入失败，"
            "多半是缺 requests），所以模型与比例的兼容性**没检查**。"
            "装上依赖再跑，或换个后端。"
        ]
    is_openai, exact_ratios = rules
    openai = bool(model) and is_openai(str(model))

    out: list = []
    if openai and refs:
        out.append(
            f"model={model!r} 走 OpenAI 路径、不支持多图 reference_paths，"
            f"但这里配了 {len(refs)} 张风格参考图。"
            "改用 gemini-* 模型，或把风格参考换成 image（单张编辑底图）。"
        )
    if openai and ratio and str(ratio) not in exact_ratios:
        out.append(
            f"model={model!r} 只原生支持 {' / '.join(sorted(exact_ratios))}，"
            f"aspect_ratio={ratio!r} 会被就近裁切，画面边缘丢掉一圈。"
            "改成原生比例，或换 gemini-* 模型。"
        )
    if image and ratio:
        out.append(
            f"给了 image（编辑底图）时输出尺寸跟随底图，aspect_ratio={ratio!r} 不生效。"
            "要指定比例就别给 image，改用 reference_paths。"
        )
    return out


def _image_gen_script() -> "Path | None":
    return _existing(
        Path.home() / ".claude" / "skills" / "image-gen" / "scripts" / "generate_image.py"
    )


def _laozhang_script() -> "Path | None":
    return _existing(Path(__file__).resolve().parent / "backends" / "laozhang_backend.py")


# image-gen 用 chain（一串 provider/model 的 fallback 序列）表达模型选择，
# 它的 batch 协议里没有 model 字段。配了 model 该被告警指向 chain，而不是默默丢掉。
IMAGE_GEN = ImageBackend(
    name="image-gen",
    resolve_script=_image_gen_script,
    supports=ALL_FIELDS - {"model"},
    install_hint=(
        "image-gen 是独立的用户级 skill（~/.claude/skills/image-gen），不随本插件安装。"
        "装好它，或用 backend: laozhang 换成插件自带的极简后端，"
        f"或用 {SCRIPT_ENV}=<脚本路径> 指向别的实现。"
    ),
)

LAOZHANG = ImageBackend(
    name="laozhang",
    resolve_script=_laozhang_script,
    # chain / preset 是 image-gen 特有的风格链与预设，本后端没有对应概念
    supports=frozenset({"model", "reference_paths", "aspect_ratio", "seed", "image"}),
    install_hint=(
        "laozhang 后端随插件安装，脚本却不见了 —— 插件目录可能不完整，"
        "重装插件或 /plugin update game-toolkit。"
    ),
    incompatibilities=_laozhang_incompatibilities,
)

BACKENDS = {"image-gen": IMAGE_GEN, "laozhang": LAOZHANG}


def _custom(path: Path, origin: str) -> ImageBackend:
    """外部脚本后端。**能力未知** —— 不是「全部支持」。

    上层据此既不报降级、也不声称查过；由后端自己在丢弃字段时出声
    （BACKEND-PROTOCOL.md 写着这条义务）。
    """
    return dataclasses.replace(
        IMAGE_GEN,
        name=f"custom:{path.name}",
        resolve_script=lambda: _existing(path),
        supports=ALL_FIELDS,
        capability_known=False,
        incompatibilities=_no_incompatibilities,
        install_hint=f"{origin} 指向的后端脚本不存在：{path}。检查路径是否写对。",
    )


def _looks_like_path(value: str) -> bool:
    return "/" in value or "\\" in value or value.endswith(".py")


def select(config: dict, project_root: Path) -> ImageBackend:
    """选后端。优先级：环境变量 > config 的 backend > 缺省 image-gen。

    环境变量放在最高位是为了向后兼容：它原本就是 image-gen 的覆盖点，
    测试套件的 mock fixture 也靠它把脚本指到临时文件。
    """
    env_path = os.environ.get(SCRIPT_ENV)
    if env_path:
        p = Path(env_path)
        if not p.is_absolute():
            # 必须在这里定死：后端子进程在 project_root 下跑，留作相对的话
            # 存在性检查（按当前 CWD）和子进程执行（按 project_root）两个基准
            # 会打架 —— 检查通过了，跑起来却找不到，或者跑到同名的另一个脚本。
            # 环境变量是调用者设的，所以按调用者 CWD 解析。
            p = (Path.cwd() / p).resolve()
        return _custom(p, f"环境变量 {SCRIPT_ENV}")

    declared = str(config.get("backend") or "").strip()
    if not declared:
        return IMAGE_GEN

    if _looks_like_path(declared):
        p = Path(declared)
        if not p.is_absolute():
            # 与 output_root 同基准。相对 config 目录或 cwd 都说得通，
            # 但一份 yaml 只该有一个「相对谁」的答案。
            p = (Path(project_root) / p).resolve()
        return _custom(p, "config 的 backend")

    if declared not in BACKENDS:
        raise ValueError(
            "未知的 backend: {!r}（可选：{}）。"
            "也可以直接写一个脚本路径，满足 BACKEND-PROTOCOL.md 的约定即可。"
            .format(declared, " / ".join(sorted(BACKENDS)))
        )
    return BACKENDS[declared]
