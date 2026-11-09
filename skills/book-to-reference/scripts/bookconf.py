"""书的差异留在配置里；所有 CLI 在写文件前共用同一道路径检查。"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, fields
from pathlib import Path
import sys
from typing import Literal

import yaml


@dataclass
class MaskNames:
    authors: list[str]
    titles: list[str]


@dataclass
class Paths:
    source: str = ""
    overview: str = "BOOK_OVERVIEW.md"
    candidates: str = "candidates"
    scope: str = "candidates/_scope.yaml"
    verify_in: str = "verify/input"
    verify_out: str = "verify/out"
    recheck_in: str = "verify/recheck/input"
    recheck_out: str = "verify/recheck/out"
    card_plan: str = "stage2/CARD-PLAN.md"
    cards: str = "cards"
    meta: str = "meta"
    glossary: str = "candidates/glossary.md"
    notes_out: str = "landing/notes.md"


@dataclass
class SkillMdConfig:
    quick_ref_start: str
    quick_ref_end: str
    quick_ref_file: str
    table_start: str
    table_end: str
    table_heading: str
    when_to_use_anchor: str
    when_to_use_line: str
    description_file: str | None = None


@dataclass
class Ruling:
    find: str
    replace: str
    why: str
    scope: Literal["cards", "notes", "all"]


@dataclass
class BookConfig:
    book_id: str
    prefix: str
    display_author: str
    display_title: str
    target_root: Path
    mask_names: MaskNames
    verify_groups: dict[str, list[str]]
    entry_groups: dict[str, list[str]]
    old_files: list[str]
    paths: Paths
    skill_md: SkillMdConfig
    rulings: list[Ruling]
    residue_allow: list[str]
    convert: dict
    answer_compare: dict


def _mapping(value, name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{name} 必须是 mapping")
    return value


def _string(value, name: str, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError(f"{name} 必须是{'非空' if not empty else ''}字符串")
    return value


def _strings(value, name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{name} 必须是字符串列表")
    return [_string(item, name) for item in value]


def _record(cls, value, name: str):
    data = _mapping(value, name)
    try:
        result = cls(**data)
    except TypeError as exc:
        raise ValueError(f"{name}: {exc}") from exc
    for field in fields(result):
        item = getattr(result, field.name)
        if field.name == "description_file" and item is None:
            continue
        _string(item, f"{name}.{field.name}", empty=field.name == "replace")
    return result


def _groups(value, name: str) -> dict[str, list[str]]:
    groups = _mapping(value, name)
    seen = set()
    for group, members in groups.items():
        _string(group, name)
        for member in _strings(members, f"{name}.{group}"):
            if member in seen:
                raise ValueError(f"{name} 章标签重复: {member}")
            seen.add(member)
    return groups


def _path(base: Path, value: str) -> Path:
    # 配置可在 Windows 编辑、在 POSIX 使用，相对路径中的反斜杠不是文件名。
    path = Path(value.replace("\\", "/")).expanduser()
    return (base / path).resolve()


def load_config(workdir: Path) -> BookConfig:
    workdir = Path(workdir).resolve()
    try:
        data = _mapping(yaml.safe_load((workdir / "book.yaml").read_text(encoding="utf-8")), "book.yaml")
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"book.yaml: {exc}") from exc
    unknown = set(data) - {field.name for field in fields(BookConfig)}
    if unknown:
        raise ValueError(f"book.yaml 未知字段: {', '.join(sorted(unknown))}")
    for name in ("book_id", "prefix", "display_author", "display_title", "target_root", "mask_names", "verify_groups", "entry_groups", "skill_md"):
        if name not in data:
            raise ValueError(f"book.yaml 缺 {name}")
    book_id = _string(data["book_id"], "book_id")
    if "/" in book_id or "\\" in book_id or book_id in (".", ".."):
        raise ValueError("book_id 必须是文件名，不是路径")
    masks = _mapping(data["mask_names"], "mask_names")
    if set(masks) != {"authors", "titles"}:
        raise ValueError("mask_names 需要 authors 和 titles")
    paths_data = {"source": f"source/{book_id}.md", **_mapping(data.get("paths", {}), "paths")}
    rules = data.get("rulings", [])
    if not isinstance(rules, list):
        raise ValueError("rulings 必须是列表")
    rulings = [_record(Ruling, rule, "rulings") for rule in rules]
    for rule in rulings:
        if rule.scope not in ("cards", "notes", "all"):
            raise ValueError(f"rulings.scope 无效: {rule.scope}")
    return BookConfig(
        book_id=book_id, prefix=_string(data["prefix"], "prefix"),
        display_author=_string(data["display_author"], "display_author"),
        display_title=_string(data["display_title"], "display_title"),
        target_root=_path(workdir, _string(data["target_root"], "target_root")),
        mask_names=MaskNames(_strings(masks["authors"], "mask_names.authors"),
                             _strings(masks["titles"], "mask_names.titles")),
        verify_groups=_groups(data["verify_groups"], "verify_groups"),
        entry_groups=_groups(data["entry_groups"], "entry_groups"),
        old_files=_strings(data.get("old_files", []), "old_files"),
        paths=_record(Paths, paths_data, "paths"),
        skill_md=_record(SkillMdConfig, data["skill_md"], "skill_md"),
        rulings=rulings, residue_allow=_strings(data.get("residue_allow", []), "residue_allow"),
        convert=_mapping(data.get("convert", {}), "convert"),
        answer_compare=_mapping(data.get("answer_compare", {}), "answer_compare"),
    )


def resolve(cfg: BookConfig, workdir: Path, name: str) -> Path:
    if name not in {field.name for field in fields(Paths)}:
        raise ValueError(f"未知 Paths 字段: {name}")
    return _path(Path(workdir).resolve(), getattr(cfg.paths, name))


def check_target(target_root: Path) -> None:
    target = Path(target_root)
    for path in (target.absolute(), target.resolve()):
        parts = [part.casefold() for part in path.as_posix().replace("\\", "/").split("/")]
        if any(a == "plugins" and b in ("cache", "marketplaces") for a, b in zip(parts, parts[1:])):
            raise ValueError(f"交付目标不能是安装缓存或 marketplace: {target}")
    if not (target / ".git").exists():
        raise ValueError(f"交付目标缺 .git（目录或 worktree 文件）: {target}")
    if not (target / ".claude-plugin/plugin.json").is_file():
        raise ValueError(f"交付目标缺 .claude-plugin/plugin.json: {target}")
    if not (target / "skills/game-design-theory").is_dir():
        raise ValueError(f"交付目标缺 skills/game-design-theory/: {target}")


def find_repo_root(start: Path) -> Path | None:
    start = Path(start).resolve()
    for parent in (start, *start.parents):
        if (parent / ".claude-plugin/plugin.json").is_file():
            return parent
    return None


def open_workdir(workdir: Path) -> BookConfig:
    cfg = load_config(workdir)
    check_target(cfg.target_root)
    roots = [cfg.target_root, find_repo_root(Path(__file__))]
    paths = {"工作目录": Path(workdir).resolve()}
    paths.update({field.name: resolve(cfg, workdir, field.name) for field in fields(Paths)})
    for name, path in paths.items():
        for root in roots:
            if root is not None and path.is_relative_to(root):
                raise ValueError(f"{name} 不能落在源码仓库里: {path}")
    return cfg


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["check"])
    parser.add_argument("workdir", type=Path)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = open_workdir(args.workdir)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"book_id={cfg.book_id}; prefix={cfg.prefix}; target_root={cfg.target_root.as_posix()}")
    print(f"verify_groups={list(cfg.verify_groups)}; entry_groups={list(cfg.entry_groups)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
