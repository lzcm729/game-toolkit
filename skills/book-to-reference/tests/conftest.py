"""隔离工作目录和交付目标，避免测试把生成物写进源码。"""
import shutil
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def plugin_copy(tmp_path):
    target = tmp_path / "plugin"
    shutil.copytree(FIXTURES / "plugin", target)
    (target / ".git").mkdir()
    return target


@pytest.fixture
def microbook(tmp_path, plugin_copy):
    workdir = tmp_path / "book"
    shutil.copytree(FIXTURES / "microbook", workdir)
    config = yaml.safe_load((workdir / "book.yaml").read_text(encoding="utf-8"))
    config["target_root"] = plugin_copy.as_posix()
    (workdir / "book.yaml").write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8", newline="\n",
    )
    return workdir
