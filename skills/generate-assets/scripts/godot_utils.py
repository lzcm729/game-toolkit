"""Godot 项目特化工具：res:// 路径解析 / project.godot 检测 / .import 扫描。

设计原则：
- 不依赖 godot 二进制，只读文件
- res:// 等价于 project.godot 所在目录（如果找得到），否则等价于 yaml 文件所在目录
- 不主动写 .import 文件（让 Godot 编辑器自己生成）
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# -------------------- 项目根定位 --------------------

def find_project_root(start: Path) -> Path | None:
    """从 start 向上找 project.godot；找到返回所在目录，否则 None。

    start 可以是文件或目录。
    """
    start = Path(start).resolve()
    if start.is_file():
        start = start.parent
    cur: Path | None = start
    while cur is not None:
        if (cur / "project.godot").exists():
            return cur
        parent = cur.parent
        if parent == cur:
            return None
        cur = parent
    return None


def is_godot_project(path: Path) -> bool:
    """目录里有 project.godot 即认为是 Godot 项目。"""
    return (Path(path) / "project.godot").exists()


# -------------------- res:// 路径解析 --------------------

def resolve_res_path(rel_or_res: str, project_root: Path) -> Path:
    """把 'res://art/foo.png' 或 'art/foo.png' 解析成绝对路径。

    规则：
      - 'res://X' → project_root / X
      - 绝对路径 → 直接返回
      - 其他相对路径 → project_root / X
    """
    if rel_or_res.startswith("res://"):
        rel = rel_or_res[len("res://"):]
        return (Path(project_root) / rel).resolve()
    p = Path(rel_or_res)
    if p.is_absolute():
        return p
    return (Path(project_root) / p).resolve()


def strip_res_prefix(path_str: str) -> str:
    """剥 res:// 前缀，仅用于调试 / 日志。"""
    if path_str.startswith("res://"):
        return path_str[len("res://"):]
    return path_str


# -------------------- .import 扫描 --------------------

@dataclass
class ImportScanResult:
    output_dir: Path
    image_files: list[Path]
    with_import: list[Path]
    without_import: list[Path]

    @property
    def total(self) -> int:
        return len(self.image_files)

    def render_hint(self) -> str:
        """供 stdout 提示用户的简短文本。"""
        if self.total == 0:
            return f"[godot] 输出目录暂无图片：{self.output_dir}"
        missing = len(self.without_import)
        if missing == 0:
            return (
                f"[godot] {self.total} 张图片均已 import "
                f"（{self.output_dir}）"
            )
        return (
            f"[godot] {self.total} 张图片中 {missing} 张缺 .import — "
            f"请用 Godot 编辑器打开项目让它自动 import"
        )


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def scan_imports(output_dir: Path) -> ImportScanResult:
    """扫描 output_dir 递归查所有图片，统计哪些已配 .import 文件。"""
    output_dir = Path(output_dir)
    image_files: list[Path] = []
    with_import: list[Path] = []
    without_import: list[Path] = []

    if not output_dir.exists():
        return ImportScanResult(
            output_dir=output_dir,
            image_files=[],
            with_import=[],
            without_import=[],
        )

    for p in sorted(output_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in _IMAGE_EXTS:
            image_files.append(p)
            sidecar = p.with_suffix(p.suffix + ".import")
            if sidecar.exists():
                with_import.append(p)
            else:
                without_import.append(p)
    return ImportScanResult(
        output_dir=output_dir,
        image_files=image_files,
        with_import=with_import,
        without_import=without_import,
    )


# -------------------- 子目录预建 --------------------

def ensure_parent_dirs(filepaths: list[Path]) -> list[Path]:
    """为每个 filepath 的父目录 mkdir -p，返回实际创建的目录列表。"""
    created: list[Path] = []
    seen: set[Path] = set()
    for fp in filepaths:
        parent = Path(fp).parent
        if parent in seen:
            continue
        seen.add(parent)
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
            created.append(parent)
    return created
