"""godot_utils.py — res:// 路径 + project.godot 检测 + .import 扫描测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from godot_utils import (
    ensure_parent_dirs,
    find_project_root,
    is_godot_project,
    resolve_res_path,
    scan_imports,
    strip_res_prefix,
)


# -------------------- find_project_root --------------------

def test_find_project_root_at_self(tmp_project):
    found = find_project_root(tmp_project)
    assert found == tmp_project.resolve()


def test_find_project_root_walks_up(tmp_project):
    sub = tmp_project / "scripts" / "view"
    sub.mkdir(parents=True)
    found = find_project_root(sub)
    assert found == tmp_project.resolve()


def test_find_project_root_from_file(tmp_project):
    f = tmp_project / "scripts" / "main.gd"
    f.parent.mkdir(parents=True)
    f.write_text("extends Node", encoding="utf-8")
    found = find_project_root(f)
    assert found == tmp_project.resolve()


def test_find_project_root_none(tmp_path):
    found = find_project_root(tmp_path)
    assert found is None


def test_is_godot_project_true(tmp_project):
    assert is_godot_project(tmp_project) is True


def test_is_godot_project_false(tmp_path):
    assert is_godot_project(tmp_path) is False


# -------------------- resolve_res_path --------------------

def test_resolve_res_prefix(tmp_project):
    p = resolve_res_path("res://art/foo.png", tmp_project)
    assert p == (tmp_project / "art" / "foo.png").resolve()


def test_resolve_relative(tmp_project):
    p = resolve_res_path("art/foo.png", tmp_project)
    assert p == (tmp_project / "art" / "foo.png").resolve()


def test_resolve_absolute(tmp_path):
    abs_target = (tmp_path / "elsewhere" / "x.png").resolve()
    p = resolve_res_path(str(abs_target), tmp_path)
    assert p == abs_target


def test_strip_res_prefix():
    assert strip_res_prefix("res://art/x.png") == "art/x.png"
    assert strip_res_prefix("art/x.png") == "art/x.png"
    assert strip_res_prefix("") == ""


# -------------------- ensure_parent_dirs --------------------

def test_ensure_parent_dirs_creates(tmp_path):
    files = [
        tmp_path / "a" / "b" / "x.png",
        tmp_path / "a" / "b" / "y.png",
        tmp_path / "c" / "z.png",
    ]
    created = ensure_parent_dirs(files)
    assert (tmp_path / "a" / "b").is_dir()
    assert (tmp_path / "c").is_dir()
    # 去重：a/b 只创建一次
    assert len(created) == 2


def test_ensure_parent_dirs_idempotent(tmp_path):
    (tmp_path / "preexisting").mkdir()
    files = [tmp_path / "preexisting" / "x.png"]
    created = ensure_parent_dirs(files)
    assert created == []


def test_ensure_parent_dirs_empty_input():
    assert ensure_parent_dirs([]) == []


# -------------------- scan_imports --------------------

def test_scan_imports_empty_dir(tmp_path):
    out = tmp_path / "art"
    out.mkdir()
    res = scan_imports(out)
    assert res.total == 0
    assert "暂无图片" in res.render_hint()


def test_scan_imports_dir_missing(tmp_path):
    res = scan_imports(tmp_path / "nope")
    assert res.total == 0


def test_scan_imports_some_with_import(tmp_path):
    out = tmp_path / "art"
    out.mkdir()
    (out / "a.png").write_bytes(b"\x89PNG")
    (out / "a.png.import").write_text("[remap]", encoding="utf-8")
    (out / "b.png").write_bytes(b"\x89PNG")
    res = scan_imports(out)
    assert res.total == 2
    assert len(res.with_import) == 1
    assert len(res.without_import) == 1
    assert "1 张缺 .import" in res.render_hint()


def test_scan_imports_all_imported(tmp_path):
    out = tmp_path / "art"
    out.mkdir()
    for n in ["a.png", "b.png"]:
        (out / n).write_bytes(b"\x89PNG")
        (out / (n + ".import")).write_text("[remap]", encoding="utf-8")
    res = scan_imports(out)
    assert "均已 import" in res.render_hint()


def test_scan_imports_recursive(tmp_path):
    out = tmp_path / "art"
    sub = out / "customers"
    sub.mkdir(parents=True)
    (sub / "x.png").write_bytes(b"\x89PNG")
    res = scan_imports(out)
    assert res.total == 1
    assert res.image_files[0].name == "x.png"


def test_scan_imports_ignores_non_images(tmp_path):
    out = tmp_path / "art"
    out.mkdir()
    (out / "x.png").write_bytes(b"\x89PNG")
    (out / "notes.txt").write_text("hi", encoding="utf-8")
    (out / "manifest.jsonl").write_text("{}", encoding="utf-8")
    res = scan_imports(out)
    assert res.total == 1


def test_scan_imports_jpg_webp(tmp_path):
    out = tmp_path / "art"
    out.mkdir()
    (out / "a.jpg").write_bytes(b"x")
    (out / "b.webp").write_bytes(b"x")
    (out / "c.JPEG").write_bytes(b"x")
    res = scan_imports(out)
    assert res.total == 3
