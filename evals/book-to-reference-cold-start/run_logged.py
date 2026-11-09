"""把执行与前后文件快照放进同一条记录，避免凭最终文件推断修复顺序。"""
from __future__ import annotations

import argparse
from contextlib import redirect_stderr
from dataclasses import fields
from datetime import datetime, timezone
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys

from cold_start_common import REPO, check_output, read_session, sha256, snapshot


def input_paths(command, cwd, session):
    scripts = REPO / "skills/book-to-reference/scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    from bookconf import Paths, load_config, resolve
    if len(command) < 3:
        return None
    script = (cwd / command[1]).resolve()
    allowed = {scripts.resolve(), (session["plugin_copy"] / "skills/book-to-reference/scripts").resolve()}
    try:
        if script.parent in allowed and (scripts / script.name).is_file() and script.stem != "page_labels":
            parser = importlib.import_module(script.stem).build_parser()
            with redirect_stderr(io.StringIO()):
                args = parser.parse_args(command[2:])
            if not hasattr(args, "workdir"):
                return None
            workdir = (cwd / args.workdir).resolve()
        elif script.name == "grade.py" and command[2] == "check-propagation" and script.parent in {
                REPO / "evals/book-to-reference-cold-start", session["plugin_copy"] / "evals/book-to-reference-cold-start"}:
            workdir = (cwd / command[3]).resolve()
        else:
            return None
        cfg = load_config(workdir)
        return {"workdir": workdir.as_posix(),
                "paths": {field.name: resolve(cfg, workdir, field.name).as_posix() for field in fields(Paths)}}
    except (OSError, ValueError, TypeError, IndexError, SystemExit) as exc:
        # 配置失败也要留证，不能为了采集路径阻止实际命令留下失败输出。
        return {"error": f"{type(exc).__name__}: {exc}"}


def run_logged(log_dir: Path, command: list[str], cwd: Path | None = None) -> int:
    if not command:
        raise ValueError("缺少 -- 后的命令")
    log_dir = check_output(log_dir)
    session = read_session(log_dir)
    index = log_dir / "commands.jsonl"
    previous = index.read_text(encoding="utf-8").splitlines() if index.exists() else []
    sequence = len(previous) + 1
    output = f"command-{sequence:04d}.out"
    if (log_dir / output).exists():
        raise ValueError("输出文件已存在；不要覆盖历史日志")

    def state():
        return {name: snapshot(session[name]) for name in ("workdir", "plugin_copy")}

    before = state()
    start = datetime.now(timezone.utc).isoformat()
    cwd = Path(cwd or Path.cwd()).resolve()
    inputs_before = input_paths(command, cwd, session)
    error = None
    try:
        process = subprocess.run(command, cwd=cwd, capture_output=True)
        code, data = process.returncode, process.stdout + process.stderr
    except OSError as exc:
        code, data = 127, str(exc).encode("utf-8")
        error = {"type": type(exc).__name__, "message": str(exc)}
    end = datetime.now(timezone.utc).isoformat()
    after = state()
    inputs_after = input_paths(command, cwd, session)
    (log_dir / output).write_bytes(data)
    record = {"seq": sequence, "argv": command, "cwd": cwd.as_posix(), "started_at": start,
              "ended_at": end, "returncode": code, "output": output, "output_sha256": sha256(data),
              "before": before, "after": after, "runs": snapshot(log_dir / "runs"),
              "inputs": {"before": inputs_before, "after": inputs_after}}
    if error:
        record["error"] = error
    with index.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    sys.stdout.buffer.write(data)
    return code


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_dir", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    try:
        return run_logged(args.log_dir, command)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
