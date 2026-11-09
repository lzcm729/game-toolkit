"""把执行与前后文件快照放进同一条记录，避免凭最终文件推断修复顺序。"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from cold_start_common import read_session, sha256, snapshot


def run_logged(log_dir: Path, command: list[str], cwd: Path | None = None) -> int:
    if not command:
        raise ValueError("缺少 -- 后的命令")
    log_dir = Path(log_dir).resolve()
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
    error = None
    try:
        process = subprocess.run(command, cwd=cwd, capture_output=True)
        code, data = process.returncode, process.stdout + process.stderr
    except OSError as exc:
        code, data = 127, str(exc).encode("utf-8")
        error = {"type": type(exc).__name__, "message": str(exc)}
    end = datetime.now(timezone.utc).isoformat()
    after = state()
    (log_dir / output).write_bytes(data)
    record = {"seq": sequence, "argv": command, "cwd": cwd.as_posix(), "started_at": start,
              "ended_at": end, "returncode": code, "output": output, "output_sha256": sha256(data),
              "before": before, "after": after, "runs": snapshot(log_dir / "runs")}
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
