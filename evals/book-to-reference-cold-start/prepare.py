"""准备外置材料、隔离源码副本和日志；拒绝继承用户目录的祖先配置。"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import sys

from cold_start_common import FIXTURE, REPO, configured_bytes, snapshot, write_json


@dataclass
class Prepared:
    workdir: Path
    plugin_copy: Path
    log_dir: Path


def ignored_paths(repo: Path, directory: str, names: list[str]) -> set[str]:
    relative = Path(directory).relative_to(repo)
    ignored = {name for name in names if name == ".git" or name.startswith(".env")}
    if len(relative.parts) == 2 and relative.parts[0] == "evals":
        ignored.add("results")
    return ignored


def prepare(parent: Path, repo: Path = REPO) -> Prepared:
    parent, repo = Path(parent).resolve(), Path(repo).resolve()
    if parent.is_relative_to(Path.home().resolve()):
        raise ValueError("父目录不能在用户主目录下面，祖先配置会污染实验")
    if parent.is_relative_to(repo):
        raise ValueError("评测父目录必须在被复制的源码仓库外")
    result = Prepared(parent / "book", parent / "plugin", parent / "logs")
    if any(path.exists() for path in (result.workdir, result.plugin_copy, result.log_dir)):
        raise ValueError("book、plugin、logs 必须都是新目录，不能覆盖旧证据")

    def ignore(directory, names):
        return ignored_paths(repo, directory, names)

    # 凭证文件不打开、不复制；符号链接保留，快照会拒绝而非读取仓库外的目标。
    shutil.copytree(repo, result.plugin_copy, ignore=ignore, symlinks=True)
    snapshot(result.plugin_copy)
    shutil.copytree(FIXTURE / "book", result.workdir)
    shutil.copytree(FIXTURE / "stops", result.workdir / "stops")
    for config in [result.workdir / "book.yaml", *sorted((result.workdir / "stops").glob("*/book.yaml"))]:
        config.write_bytes(configured_bytes(config.read_bytes(), result.plugin_copy))
    result.log_dir.mkdir(parents=True)
    commands = []
    for arguments in (("init",), ("add", "-A"), ("commit", "-m", "cold-start baseline")):
        command = ["git", "-c", "user.name=Cold Start Fixture", "-c", "user.email=fixture@example.invalid",
                   "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", "-C", str(result.plugin_copy), *arguments]
        process = subprocess.run(command, capture_output=True)
        output = f"prepare-{len(commands) + 1}.out"
        (result.log_dir / output).write_bytes(process.stdout + process.stderr)
        commands.append({"argv": command, "returncode": process.returncode, "output": output})
        write_json(result.log_dir / "prepare-commands.json", commands)
        if process.returncode:
            raise ValueError(f"准备 Git 基线失败，见 {output}")
    write_json(result.log_dir / "session.json", {
        "schema_version": 1, "workdir": result.workdir.as_posix(),
        "plugin_copy": result.plugin_copy.as_posix(), "log_dir": result.log_dir.as_posix(),
        "excluded": [".git (source)", "evals/*/results", ".env*"],
    })
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parent", type=Path)
    args = parser.parse_args(argv)
    try:
        result = prepare(args.parent)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1
    for name in ("workdir", "plugin_copy", "log_dir"):
        print(f"{name}: {getattr(result, name).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
