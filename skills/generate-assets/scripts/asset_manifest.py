#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成记录：每张图是用什么请求生成的。

后端的「已存在就跳过」只看文件在不在。而这个工具的核心循环恰恰是
「出一张 → 看 → 改模板 → 再出」—— 改完模板再跑，得到的是一排 `[skip]`，
一张新图都没有。`skipped` 分不清两件事：

  - 这张图就是按当前配置生成的（真的不用重出）
  - 这张图是旧 prompt / 旧模型 / 旧风格锚留下的（已经对不上配置了）

所以每个输出目录放一份 `.generate-assets.json`，记下每张图生成时的**请求**
（完整 prompt、生效的 model / 比例 / seed、参考图与底图的内容哈希、后端）。
下次跑之前逐项比对，变了就报「过期」并说出是哪一项变了。

几条刻意的选择：

- **过期不自动重出。**批量按张烧钱，旧图也可能是用户已经认可的。只报告，
  要重出就 `--force`（配 `--names` / `--limit` 只重出那几张）。
- **只在真生成了的时候更新记录。**被后端跳过的图，记录必须保持原样 ——
  否则一张过期图会被标成「最新」，比没有这个功能还糟。
- **没有记录 ≠ 过期。**本功能之前生成的、手动放进来的图，没有记录可比，
  报「未追踪」。「没发现」和「没看」得分开。
- **路径存相对工程根的，比对只看内容哈希。**这份记录可能随图一起入库，
  存绝对路径的话，别人 checkout 下来会发现全部「过期」。
- 文件名以 `.` 开头：Godot 的导入器会跳过隐藏文件，不会把它当资源导入。
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MANIFEST_NAME = ".generate-assets.json"
MANIFEST_VERSION = 1

# 参与比对的字段。顺序就是报告「哪一项变了」时的顺序。
SIGNATURE_KEYS = (
    "prompt", "model", "aspect_ratio", "seed", "chain", "preset",
    "reference_paths", "image", "backend",
)

# 报告里给人看的字段名
_LABELS = {
    "prompt": "prompt",
    "model": "model",
    "aspect_ratio": "aspect_ratio",
    "seed": "seed",
    "chain": "chain",
    "preset": "preset",
    "reference_paths": "风格参考图",
    "image": "编辑底图",
    "backend": "后端",
}

CURRENT = "current"      # 有记录且一致
STALE = "stale"          # 有记录但不一致
UNTRACKED = "untracked"  # 文件在，但没有记录
NEW = "new"              # 文件不在


@dataclass(frozen=True)
class Status:
    kind: str
    changed: tuple = ()    # STALE 时：哪些字段变了

    def describe(self) -> str:
        return "、".join(_LABELS.get(k, k) for k in self.changed)


class _Hasher:
    """同一批里参考图会被每个条目引用一次，只算一遍。"""

    def __init__(self):
        self._cache: dict = {}

    def file(self, path) -> "str | None":
        p = str(path)
        if p not in self._cache:
            try:
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                self._cache[p] = h.hexdigest()
            except OSError:
                self._cache[p] = None   # 文件不在：记成 None，下次在了就算变了
        return self._cache[p]


def _rel(path, project_root: Path) -> str:
    """相对工程根的路径，正斜杠。工程根之外的只留文件名 —— 那种路径对别人本来就没意义。"""
    p = Path(path)
    try:
        return p.resolve().relative_to(Path(project_root).resolve()).as_posix()
    except (ValueError, OSError):
        return p.name


def signature(asset, defaults: dict, backend_name: str, project_root: Path,
              hasher: "_Hasher | None" = None) -> dict:
    """一张图的请求签名。字段见 `SIGNATURE_KEYS`。

    参考图与底图记成 `{"path": 相对路径, "sha256": 内容哈希}`，比对时只看哈希 ——
    换了个文件名但内容一样不算变，同名文件内容被替换了才算。
    """
    hasher = hasher or _Hasher()
    payload = getattr(asset, "payload", asset)

    def effective(key):
        value = payload.get(key)
        return value if value is not None else defaults.get(key)

    refs = defaults.get("reference_paths") or []
    image = payload.get("image")
    return {
        "prompt": payload.get("prompt"),
        "model": effective("model"),
        "aspect_ratio": effective("aspect_ratio"),
        "seed": effective("seed"),
        "chain": effective("chain"),
        "preset": effective("preset"),
        "reference_paths": [
            {"path": _rel(r, project_root), "sha256": hasher.file(r)} for r in refs
        ],
        "image": ({"path": _rel(image, project_root), "sha256": hasher.file(image)}
                  if image else None),
        "backend": backend_name,
    }


def _comparable(sig: dict, key: str):
    """比对用的值。图只比哈希，路径是给人看的。"""
    value = sig.get(key)
    if key == "reference_paths":
        return [r.get("sha256") for r in (value or [])]
    if key == "image":
        return value.get("sha256") if value else None
    return value


def diff(old: dict, new: dict) -> tuple:
    return tuple(k for k in SIGNATURE_KEYS if _comparable(old, k) != _comparable(new, k))


def load(output_dir: Path) -> "tuple[dict, str | None]":
    """读记录。返回 (条目表, 问题说明)。读不了不抛 —— 当成没有记录，但要说出来。"""
    path = Path(output_dir) / MANIFEST_NAME
    if not path.exists():
        return {}, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {}, f"{path} 读不了（{e}），本次当作没有生成记录"
    if not isinstance(data, dict) or not isinstance(data.get("items"), dict):
        return {}, f"{path} 格式不对，本次当作没有生成记录"
    if data.get("version") != MANIFEST_VERSION:
        return {}, (f"{path} 的版本是 {data.get('version')!r}，本工具只认 "
                    f"{MANIFEST_VERSION}，本次当作没有生成记录")
    return data["items"], None


def classify(filename: str, output_dir: Path, sig: dict, items: dict) -> Status:
    if not (Path(output_dir) / filename).exists():
        return Status(NEW)
    entry = items.get(filename)
    if not isinstance(entry, dict) or not isinstance(entry.get("request"), dict):
        return Status(UNTRACKED)
    changed = diff(entry["request"], sig)
    return Status(STALE, changed) if changed else Status(CURRENT)


def record(output_dir: Path, items: dict, updates: dict) -> None:
    """把这次真生成了的图写进记录。`updates` 是 {文件名: 签名}。

    先写临时文件再改名 —— 写到一半被打断，也不会留下一份坏掉的记录
    让下次把所有图都判成「未追踪」。
    """
    if not updates:
        return
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    merged = dict(items)
    for filename, sig in updates.items():
        merged[filename] = {"request": sig, "generated_at": now}
    data = {
        "version": MANIFEST_VERSION,
        "note": "generate-assets 的生成记录：每张图是用什么请求生成的。"
                "用来在配置改动后分辨哪些图已经过期。可以随图一起入库。",
        "items": dict(sorted(merged.items())),
    }
    out = Path(output_dir)
    fd, tmp = tempfile.mkstemp(prefix=".generate-assets.", suffix=".tmp", dir=str(out))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, out / MANIFEST_NAME)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def new_hasher() -> _Hasher:
    return _Hasher()
