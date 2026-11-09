"""只评分可机械重算的执行证据；全绿不代表内容质量或独立验收通过。"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import sys

import yaml

from cold_start_common import FIXTURE, HERE, REPO, STOP_NAMES, configured_bytes, read_session, sha256

SCRIPTS = REPO / "skills/book-to-reference/scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
from bookconf import open_workdir, resolve
from chain import parse_run
from check_cards import PLAN_ROW
import publicize
import runner
from stage1 import read_tasks, scope_dispositions


FLOW_FILES = (
    "BOOK_OVERVIEW.md", "candidates/frameworks.md", "candidates/principles.md", "candidates/cases.md",
    "candidates/counter-examples.md", "candidates/glossary.md", "candidates/_coverage-stage1.md",
    "verified.md", "references.md", "needs-review.md", "coverage-audit.md", "stage2/CARD-PLAN.md",
    "stage2/quick-ref.md", "landing/notes.md", "grouping/capabilities.yaml", "grouping/groups.yaml", "review.md",
)
FLOW_GLOBS = (
    "stage0-notes/*.md", "verify/input/*.yaml", "verify/out/*.yaml", "verify/recheck/input/*.yaml",
    "verify/recheck/out/*.yaml", "cards/*.md", "meta/*.yaml",
    "propagation/findings-*.yaml", "propagation/fixes-*.yaml",
)
WATCH = {"01-quotes": "cards/gate-token.md", "02-propagation": "cards/single-vane.md", "03-entry": "book.yaml"}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str


def _path(value: str, cwd: str | Path) -> Path:
    return (Path(cwd) / value.replace("\\", "/")).resolve()


def read_records(log_dir: Path) -> tuple[list[dict], list[str]]:
    try:
        records = [json.loads(line) for line in (log_dir / "commands.jsonl").read_text(encoding="utf-8").splitlines()]
        previous_end = None
        for index, row in enumerate(records, 1):
            if row["seq"] != index or not isinstance(row["returncode"], int):
                raise ValueError("命令序号或退出码错误")
            if not isinstance(row["argv"], list) or not all(isinstance(arg, str) for arg in row["argv"]):
                raise ValueError("argv 必须是字符串列表")
            start, end = datetime.fromisoformat(row["started_at"]), datetime.fromisoformat(row["ended_at"])
            if start.tzinfo is None or end < start or (previous_end and start < previous_end):
                raise ValueError("命令时间重叠、倒序或缺时区")
            previous_end = end
            output = _path(row["output"], log_dir)
            if not output.is_relative_to(log_dir) or sha256(output.read_bytes()) != row["output_sha256"]:
                raise ValueError("输出缺失、越界或哈希不符")
            for state in (row["before"], row["after"]):
                for name in ("workdir", "plugin_copy"):
                    if not isinstance(state[name], dict):
                        raise ValueError("缺少文件快照")
                    if not all(isinstance(key, str) and isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                               for key, value in state[name].items()):
                        raise ValueError("快照哈希无效")
        if not records:
            raise ValueError("没有命令记录")
        return records, []
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [], [str(exc)]


def command_for(row: dict, script: Path, workdir: Path, subcommand: str | None = None) -> bool:
    argv = row.get("argv", [])
    if len(argv) < 3 or _path(argv[1], row["cwd"]) != script.resolve():
        return False
    arguments = argv[2:]
    if subcommand:
        if not arguments or arguments[0] != subcommand:
            return False
        arguments = arguments[1:]
    return bool(arguments) and _path(arguments[0], row["cwd"]) == workdir.resolve()


def _artifact_problems(workdir: Path) -> list[str]:
    def nonempty(path):
        return path.is_file() and bool(path.read_bytes().strip())
    missing = [name for name in FLOW_FILES if not nonempty(workdir / name)]
    missing.extend(pattern for pattern in FLOW_GLOBS if not any(nonempty(path) for path in workdir.glob(pattern)))
    return missing


def _integrated(workdir: Path, plugin_copy: Path) -> str:
    cfg = open_workdir(workdir)
    if cfg.target_root != plugin_copy:
        raise ValueError("配置目标不是传入的插件副本")
    plan = resolve(cfg, workdir, "card_plan").read_text(encoding="utf-8")
    slugs = [match.group(2) for line in plan.splitlines() if (match := PLAN_ROW.match(line))]
    if not slugs:
        raise ValueError("卡片计划没有卡")
    skill_path = plugin_copy / "skills/game-design-theory/SKILL.md"
    skill = skill_path.read_text(encoding="utf-8")
    refs = skill_path.parent / "references"
    names = [f"{cfg.prefix}{slug}.md" for slug in slugs] + [f"{cfg.prefix}notes.md"]
    for name in names:
        path = refs / name
        if not path.is_file() or not path.read_bytes().strip() or f"](references/{name})" not in skill:
            raise ValueError(f"未接入文件或直链: {name}")
    for path in [skill_path, *(refs / name for name in names)]:
        if publicize.scan(path.read_text(encoding="utf-8"), cfg.residue_allow):
            raise ValueError(f"发布文件有残留: {path.name}")
    return f"{len(slugs)} 张卡、notes 和直链在场；只扫描本书生成文件及入口"


def check_propagation(workdir: Path) -> list[str]:
    """固定夹具的语义探针，不是面向任意书籍的传播验证器。"""
    cfg = open_workdir(workdir)
    unit = next(unit for unit in yaml.safe_load((resolve(cfg, workdir, "verify_out") / "G2.yaml").read_text(encoding="utf-8"))["units"]
                if unit["unit_id"] == "u02-01")
    if unit.get("recheck", {}).get("narrowing") != "只用于单个泊位，不用于全港放行":
        return ["采用的复核限制被改动，不能靠改证据通过"]
    text = (resolve(cfg, workdir, "cards") / "single-vane.md").read_text(encoding="utf-8")
    section = re.search(r"^## E\b.*?(?=^## B\b|\Z)", text, re.M | re.S)
    if not section:
        return ["没有执行段"]
    execution = section.group(0)
    local = re.search(r"单个泊位|单一泊位|一个泊位|单泊位|one berth|single berth", execution, re.I)
    if "对齐后即可开放整个港口" in execution or not local:
        return ["执行段未落实局部试验的收窄，或仍承诺全港放行"]
    return []


def _stop_records(records, name, workdir, plugin_copy):
    stop = workdir / "stops" / name
    script = plugin_copy / "skills/book-to-reference/scripts" / ("integrate.py" if name == "03-entry" else "check_cards.py")
    if name == "02-propagation":
        return [row for row in records if any(command_for(row, path, stop, "check-propagation") for path in
                (HERE / "grade.py", plugin_copy / "evals/book-to-reference-cold-start/grade.py"))]
    return [row for row in records if command_for(row, script, stop)]


def _stop_problem(records, name, workdir, plugin_copy, after_seq):
    checks = _stop_records(records, name, workdir, plugin_copy)
    if len(checks) < 2:
        return "缺少首次失败或修改后的同一检查", after_seq
    first, last = checks[0], checks[-1]
    if first["returncode"] == 0 or last["returncode"] != 0 or first["seq"] <= after_seq:
        return "检查顺序不是本轮采用输入的失败→修复→通过，或未按三份输入的次序执行", after_seq
    signature = lambda row: tuple(arg.replace("\\", "/") for arg in row["argv"][1:])
    if signature(first) != signature(last):
        return "复查不是同一条检查命令", after_seq
    prefix = f"stops/{name}/"
    for source in sorted((FIXTURE / "stops" / name).rglob("*")):
        if not source.is_file():
            continue
        data = source.read_bytes()
        if source.name == "book.yaml":
            data = configured_bytes(data, plugin_copy)
        key = prefix + source.relative_to(FIXTURE / "stops" / name).as_posix()
        if first["before"]["workdir"].get(key) != sha256(data):
            return f"首次失败前已修改或缺少采用输入: {key}", after_seq
    watched = prefix + WATCH[name]
    initial = first["before"]["workdir"].get(watched)
    changed = last["before"]["workdir"].get(watched)
    if not changed or initial == changed or first["after"]["workdir"].get(watched) != initial:
        return "相关文件没有在失败后、复查前修改", after_seq
    return "采用输入未提前修；失败后相关文件变化，同一检查复查通过", last["seq"]


def _consumed(records, workdir, plugin_copy, log_dir, prefix):
    script = plugin_copy / "skills/book-to-reference/scripts/runner.py"
    for row in records:
        argv = row["argv"]
        if len(argv) < 4 or _path(argv[1], row["cwd"]) != script:
            continue
        try:
            args = runner.build_parser().parse_args(argv[2:])
        except SystemExit:
            continue
        directory = _path(str(args.out_dir), row["cwd"])
        runs = log_dir / "runs"
        if not directory.is_relative_to(runs):
            continue
        for path in sorted(directory.glob("*/*.jsonl")):
            meta_path = Path(str(path) + ".meta.json")
            files = (path, meta_path)
            if any(not file.is_file() or row.get("runs", {}).get(file.relative_to(runs).as_posix()) != sha256(file.read_bytes()) for file in files):
                continue
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if not isinstance(meta, dict) or meta.get("plugin_dir") != plugin_copy.as_posix() or not runner.is_success(path, args.batch_id):
                continue
            run = parse_run(path)
            refs = plugin_copy / "skills/game-design-theory/references"
            cards = [file for file in run.reads if _path(file, row["cwd"]).parent == refs
                     and Path(file).name.startswith(prefix) and Path(file).suffix == ".md" and Path(file).name != f"{prefix}notes.md"
                     and _path(file, row["cwd"]).is_file()]
            if run.ok and any(skill.startswith("game-toolkit:") for skill in run.skills) and cards:
                return True, row["seq"], f"{path.relative_to(log_dir)}: 成功调用本插件并读到 {Path(cards[0]).name}"
    return False, 0, "日志目录/runs 没有带本批 meta、成功插件调用和成功新卡 Read 的完整运行"


def grade(workdir: Path, plugin_copy: Path, log_dir: Path) -> list[Check]:
    workdir, plugin_copy, log_dir = (Path(path).resolve() for path in (workdir, plugin_copy, log_dir))
    records, problems = read_records(log_dir)
    try:
        session = read_session(log_dir)
        if (session["workdir"], session["plugin_copy"]) != (workdir, plugin_copy):
            problems.append("session 根路径与评分输入不一致")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        problems.append(str(exc))
    if problems:
        records = []
    checks = [Check("logs.valid", not problems, "; ".join(problems) or f"{len(records)} 条顺序日志及输出哈希有效")]
    missing = _artifact_problems(workdir)
    checks.append(Check("flow.artifacts", not missing, ", ".join(missing) or "约定的各阶段产物在场；不判断其内容质量或独立性"))
    scripts = plugin_copy / "skills/book-to-reference/scripts"
    main_checks = {}
    for filename, name in (("check_cards.py", "flow.cards_check"), ("integrate.py", "flow.integrate")):
        rows = [row for row in records if command_for(row, scripts / filename, workdir)]
        if filename == "check_cards.py":
            rows = [row for row in rows if "--only" not in row["argv"]]
        ok = bool(rows) and rows[-1]["returncode"] == 0
        main_checks[name] = rows[-1]["seq"] if ok else 0
        checks.append(Check(name, ok, f"完整流程最后一次 {filename}: " + (str(rows[-1]["returncode"]) if rows else "未运行")))
    try:
        # 三份续跑会再次接入同一书；最终副本按最近一次采用输入核文件和选卡直链。
        integrations = [row for row in records if len(row["argv"]) == 3 and _path(row["argv"][1], row["cwd"]) == scripts / "integrate.py" and row["returncode"] == 0]
        final_work = _path(integrations[-1]["argv"][2], integrations[-1]["cwd"]) if integrations else workdir
        if not final_work.is_relative_to(workdir):
            raise ValueError("接入输入逃出本次工作目录")
        detail = _integrated(final_work, plugin_copy)
        checks.append(Check("flow.integrated", True, detail))
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        checks.append(Check("flow.integrated", False, str(exc)))
    prefix = "ribbon-"
    try:
        cfg = open_workdir(workdir)
        prefix = cfg.prefix
        tasks = read_tasks(resolve(cfg, workdir, "overview").read_text(encoding="utf-8"))
        scope, scope_problems = scope_dispositions(resolve(cfg, workdir, "scope"), tasks)
        scope_ok = not scope_problems and any(item["decision"] == "reference_only" for item in scope.values())
        checks.append(Check("flow.scope", scope_ok, "; ".join(scope_problems) or ("纯参考任务单独处置；是否给用户看及参考去向的质量仍须人工核" if scope_ok else "缺少有效的 reference_only 处置")))
    except (OSError, ValueError, KeyError, TypeError, yaml.YAMLError) as exc:
        checks.append(Check("flow.scope", False, str(exc)))
    try:
        consumed, consumption_seq, detail = _consumed(records, workdir, plugin_copy, log_dir, prefix)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        consumed, consumption_seq, detail = False, 0, str(exc)
    checks.append(Check("consumption", consumed, detail))
    after_seq = max([consumption_seq, *main_checks.values()])
    for name in STOP_NAMES:
        problem, last = _stop_problem(records, name, workdir, plugin_copy, after_seq)
        ok = last > after_seq
        checks.append(Check(f"stop.{name}", ok, problem))
        after_seq = last
    return checks


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("grade")
    run.add_argument("workdir", type=Path)
    run.add_argument("plugin_copy", type=Path)
    run.add_argument("log_dir", type=Path)
    propagation = commands.add_parser("check-propagation")
    propagation.add_argument("workdir", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "check-propagation":
            problems = check_propagation(args.workdir)
            print("\n".join(problems) if problems else "本夹具的局部试验限制已落实；其余传播项仍须人工核")
            return 1 if problems else 0
        checks = grade(args.workdir, args.plugin_copy, args.log_dir)
        for check in checks:
            print(f"{'PASS' if check.ok else 'FAIL'} {check.name}: {check.detail}")
        print("仅为机械执行证据；不能据此宣布内容质量或独立验收通过。")
        return 0 if all(check.ok for check in checks) else 1
    except (OSError, ValueError, KeyError, TypeError, StopIteration, yaml.YAMLError) as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
