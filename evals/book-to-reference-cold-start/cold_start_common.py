"""夹具原件与运行副本分开；路径替换只发生在准备出的副本中。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import yaml


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FIXTURE = HERE / "fixture"
STOP_NAMES = ("01-quotes", "02-propagation", "03-entry")


def check_output(path: Path) -> Path:
    scripts = REPO / "skills/book-to-reference/scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from bookconf import check_work_output
    return check_work_output(path)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def configured_bytes(data: bytes, plugin_copy: Path) -> bytes:
    config = yaml.safe_load(data.decode("utf-8"))
    config["target_root"] = plugin_copy.resolve().as_posix()
    return yaml.safe_dump(config, allow_unicode=True, sort_keys=False, width=200).encode("utf-8")


def snapshot(directory: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(Path(directory).rglob("*")):
        if path.is_symlink():
            raise ValueError(f"快照不跟随符号链接: {path}")
        if path.is_file() and not path.name.startswith(".env"):
            hashes[path.relative_to(directory).as_posix()] = sha256(path.read_bytes())
    return hashes


def read_session(log_dir: Path) -> dict:
    session = json.loads((Path(log_dir) / "session.json").read_text(encoding="utf-8"))
    for name in ("workdir", "plugin_copy", "log_dir"):
        session[name] = Path(session[name]).resolve()
    if session["log_dir"] != Path(log_dir).resolve():
        raise ValueError("日志目录与 session 不一致")
    return session
