"""两个冻结版本同批交错运行；只有本批完整回答可跳过或进入评分。"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile

from chain import parse_run


@dataclass
class Job:
    prompt_id: str
    prompt: str
    variant: str
    plugin_dir: Path
    rep: int


def plan_jobs(prompts: list[tuple[str, str]], variants: dict[str, Path], reps: int) -> list[Job]:
    if reps < 1:
        raise ValueError("reps 必须大于 0")
    return [Job(qid, prompt, variant, Path(directory), rep)
            for qid, prompt in prompts for rep in range(1, reps + 1)
            for variant, directory in variants.items()]


def is_success(out: Path, batch_id: str) -> bool:
    try:
        meta = json.loads(Path(str(out) + ".meta.json").read_text(encoding="utf-8"))
        return meta.get("batch_id") == batch_id and parse_run(out).ok
    except (OSError, ValueError, AttributeError):
        return False


def check_runs_root(runs_root: Path) -> None:
    if Path(runs_root).resolve().is_relative_to(Path.home().resolve()):
        raise ValueError("runs_root 不能在用户主目录下面，祖先配置会污染实验")


def _write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def run_batch(jobs, out_dir: Path, runs_root: Path, batch_id: str, lanes: int,
              budget_usd: float, model: str, claude_cmd: list[str]) -> list[Path]:
    check_runs_root(runs_root)
    if lanes < 1 or budget_usd <= 0 or not batch_id or not claude_cmd:
        raise ValueError("lanes、budget、batch_id 和 claude_cmd 无效")
    jobs = list(jobs)
    destinations = []
    seen = set()
    for job in jobs:
        if not all(re.fullmatch(r"[A-Za-z0-9_-]+", name) for name in (job.prompt_id, job.variant)) or job.rep < 1:
            raise ValueError("提示词号、版本名或重复号无效")
        path = Path(out_dir).resolve() / job.variant / f"{job.prompt_id}-r{job.rep}.jsonl"
        if path in seen:
            raise ValueError(f"duplicate job: {path.name}")
        seen.add(path)
        destinations.append(path)
    runs_root = Path(runs_root).resolve()
    runs_root.mkdir(parents=True, exist_ok=True)
    config = Path(tempfile.mkdtemp(prefix="config-", dir=runs_root))

    def run_one(pair):
        job, path = pair
        plugin = job.plugin_dir.resolve().as_posix()
        prompt_sha = hashlib.sha256(job.prompt.encode("utf-8")).hexdigest()
        meta_path = Path(str(path) + ".meta.json")
        if is_success(path, batch_id):
            old = json.loads(meta_path.read_text(encoding="utf-8"))
            if (old.get("prompt_sha256"), old.get("requested_model"), old.get("plugin_dir")) == (prompt_sha, model, plugin):
                return path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() or meta_path.exists():
            number = 1
            while Path(str(path) + f".stale-{number}").exists() or Path(str(meta_path) + f".stale-{number}").exists():
                number += 1
            for existing in (path, meta_path):
                if existing.exists():
                    existing.rename(Path(str(existing) + f".stale-{number}"))
        cwd = Path(tempfile.mkdtemp(prefix="cwd-", dir=runs_root))
        meta = {"batch_id": batch_id, "variant": job.variant, "prompt_id": job.prompt_id, "rep": job.rep,
                "prompt_sha256": prompt_sha, "requested_model": model, "model": model,
                "cc_version": "", "plugin_dir": plugin, "cwd": cwd.as_posix(),
                "config_dir": config.as_posix()}
        _write_json(meta_path, meta)
        command = [*claude_cmd, "-p", "--plugin-dir", plugin, "--add-dir", plugin,
                   "--model", model, "--tools", "Read,Glob,Grep,Skill", "--output-format", "stream-json",
                   "--verbose", "--no-session-persistence", "--max-budget-usd", str(budget_usd), job.prompt]
        env = {**os.environ, "CLAUDE_CONFIG_DIR": config.as_posix()}
        try:
            process = subprocess.run(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                     capture_output=True, text=True, encoding="utf-8", errors="replace")
            path.write_text(process.stdout, encoding="utf-8", newline="\n")
            Path(str(path) + ".err").write_text(process.stderr, encoding="utf-8", newline="\n")
            run = parse_run(path)
            meta.update(model=run.model or model, cc_version=run.cc_version, returncode=process.returncode)
        except OSError as exc:
            path.write_text("", encoding="utf-8", newline="\n")
            Path(str(path) + ".err").write_text(str(exc), encoding="utf-8", newline="\n")
            meta.update(returncode=1, process_error=str(exc))
        _write_json(meta_path, meta)
        return path

    # submit 的顺序保持 plan_jobs 的题→重复→版本；并发只改变完成时间。
    with ThreadPoolExecutor(max_workers=lanes) as pool:
        return list(pool.map(run_one, zip(jobs, destinations)))


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompts", type=Path)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--variant", action="append", required=True)
    parser.add_argument("--reps", type=int, required=True)
    parser.add_argument("--lanes", type=int, required=True)
    parser.add_argument("--budget", type=float, required=True)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--claude", default="claude", help="命令及固定参数；路径用正斜杠")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        prompts = []
        for line in args.prompts.read_text(encoding="utf-8").splitlines():
            if line.strip():
                qid, _, prompt = line.split("\t", 2)
                prompts.append((qid, prompt))
        variants = dict(item.split("=", 1) for item in args.variant)
        jobs = plan_jobs(prompts, {name: Path(path) for name, path in variants.items()}, args.reps)
        paths = run_batch(jobs, args.out_dir, args.runs_root, args.batch_id, args.lanes, args.budget,
                          args.model, shlex.split(args.claude.replace("\\", "/")))
        failed = [path.as_posix() for path in paths if not is_success(path, args.batch_id)]
        print(f"runs: {len(paths)}; failed: {len(failed)}")
        for path in failed:
            print(path)
        return 1 if failed else 0
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
