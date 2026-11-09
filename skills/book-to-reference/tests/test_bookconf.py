"""路径隔离应在 CLI 有机会写文件之前生效。"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

import bookconf as bc


def update(workdir, **changes):
    path = workdir / "book.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data.update(changes)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                    encoding="utf-8", newline="\n")


def test_load_microbook_config(microbook):
    cfg = bc.open_workdir(microbook)
    assert cfg.prefix == "micro-"
    assert list(cfg.verify_groups) == ["G2", "G1"]
    assert list(cfg.entry_groups) == ["灯光试验", "起步"]
    assert cfg.paths.cards == "cards"
    assert bc.resolve(cfg, microbook, "source") == microbook / "source/microbook.md"


def test_paths_override(microbook):
    update(microbook, paths={"cards": ".cangjie/capabilities/cards"})
    assert bc.open_workdir(microbook).paths.cards == ".cangjie/capabilities/cards"


def test_missing_required_field(microbook):
    data = yaml.safe_load((microbook / "book.yaml").read_text(encoding="utf-8"))
    del data["prefix"]
    (microbook / "book.yaml").write_text(yaml.safe_dump(data), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="prefix"):
        bc.load_config(microbook)


def test_ruling_requires_why(microbook):
    update(microbook, rulings=[{"find": "旧说法", "replace": "新说法", "scope": "cards"}])
    with pytest.raises(ValueError, match="why"):
        bc.load_config(microbook)


def test_workdir_inside_target_rejected(microbook, plugin_copy):
    inside = plugin_copy / "work"
    shutil.copytree(microbook, inside)
    with pytest.raises(ValueError, match="工作目录"):
        bc.open_workdir(inside)


def test_resolved_path_inside_target_rejected(microbook, plugin_copy):
    update(microbook, paths={"source": (plugin_copy / "source.md").as_posix()})
    with pytest.raises(ValueError, match="source"):
        bc.open_workdir(microbook)


@pytest.mark.parametrize("location", ["cache", "marketplaces"])
def test_cache_target_rejected(tmp_path, plugin_copy, location):
    target = tmp_path / "plugins" / location / "sample"
    shutil.copytree(plugin_copy, target)
    with pytest.raises(ValueError, match="安装"):
        bc.check_target(target)


def test_target_without_git_rejected(plugin_copy):
    (plugin_copy / ".git").rmdir()
    with pytest.raises(ValueError, match=".git"):
        bc.check_target(plugin_copy)


def test_worktree_git_file_accepted(plugin_copy):
    (plugin_copy / ".git").rmdir()
    (plugin_copy / ".git").write_text("gitdir: ../git/worktrees/sample\n", encoding="utf-8", newline="\n")
    bc.check_target(plugin_copy)


def test_path_inside_script_repo_rejected(microbook):
    repo = bc.find_repo_root(Path(bc.__file__))
    update(microbook, paths={"cards": (repo / "skills/book-to-reference/cards").as_posix()})
    with pytest.raises(ValueError, match="cards"):
        bc.open_workdir(microbook)


def test_cli_rejects_bad_workdir(microbook):
    with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as temp:
        inside = Path(temp) / "book"
        shutil.copytree(microbook, inside)
        before = {p.relative_to(inside): p.read_bytes() for p in inside.rglob("*") if p.is_file()}
        result = subprocess.run([sys.executable, bc.__file__, "check", str(inside)], capture_output=True)
        assert result.returncode == 1
        assert before == {p.relative_to(inside): p.read_bytes() for p in inside.rglob("*") if p.is_file()}


def test_malformed_config_is_value_error(microbook):
    (microbook / "book.yaml").write_text("prefix: [\n", encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="book.yaml"):
        bc.load_config(microbook)
