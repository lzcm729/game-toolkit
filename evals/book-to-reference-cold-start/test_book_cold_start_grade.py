"""反例测试评分边界；这些合成产物不算新上下文的冷启动。"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRIPTS = REPO / "skills/book-to-reference/scripts"
for directory in (HERE, SCRIPTS):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


grade = module("book_cold_start_grade", "grade.py")
prepare = module("book_cold_start_prepare", "prepare.py")
logged = module("book_cold_start_logged", "run_logged.py")
from cold_start_common import FIXTURE, STOP_NAMES, configured_bytes, sha256, snapshot, write_json
import bookconf
import check_cards
import integrate
import stage1
import verify_units


def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def make_prepared(tmp_path, monkeypatch, real_git=False):
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "simulated-home")
    repo = tmp_path / "source"
    shutil.copytree(SCRIPTS.parent, repo / "skills/book-to-reference")
    put(repo / ".claude-plugin/plugin.json", '{"name":"game-toolkit"}\n')
    put(repo / "skills/game-design-theory/SKILL.md", """---
name: game-design-theory
description: Synthetic source
---
# Synthetic source
## When to Use This Skill
- Evaluating game concepts for player appeal
<!-- RIBBON QUICK START -->
<!-- RIBBON QUICK END -->
<!-- RIBBON TABLE START -->
<!-- RIBBON TABLE END -->
""")
    put(repo / "evals/example/results/private.txt", "must not copy\n")
    put(repo / ".git/private.txt", "must not copy\n")
    if real_git:
        return prepare.prepare(tmp_path / "session", repo)

    def git(command, **kwargs):
        assert command[0] == "git"
        if command[-1] == "init":
            (tmp_path / "session/plugin/.git").mkdir()
        return subprocess.CompletedProcess(command, 0, b"synthetic git setup\n", b"")

    # 评分反例只需要源码标记；真正 init/commit 另有一条集成测试，避免每个反例都建 Git。
    with monkeypatch.context() as patch:
        patch.setattr(prepare.subprocess, "run", git)
        return prepare.prepare(tmp_path / "session", repo)


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    return make_prepared(tmp_path, monkeypatch)


def repair_stop(workdir, name):
    if name == "01-quotes":
        card = workdir / "cards/gate-token.md"
        put(card, card.read_text(encoding="utf-8").replace("Notebook, p.3", "Notebook, p.2"))
    elif name == "02-propagation":
        card = workdir / "cards/single-vane.md"
        put(card, card.read_text(encoding="utf-8").replace(
            "对齐后即可开放整个港口（p.10）。", "只用于单个泊位，不构成全港放行许可（p.10）。"))
    else:
        config = yaml.safe_load((workdir / "book.yaml").read_text(encoding="utf-8"))
        config["entry_groups"]["保留记录"] = ["03"]
        put(workdir / "book.yaml", yaml.safe_dump(config, allow_unicode=True, sort_keys=False, width=200))


def test_prepare_creates_isolated_source(tmp_path, monkeypatch):
    prepared = make_prepared(tmp_path, monkeypatch, real_git=True)
    bookconf.open_workdir(prepared.workdir)
    assert len(list((prepared.workdir / "stops").glob("*/book.yaml"))) == 3
    assert not (prepared.plugin_copy / ".git/private.txt").exists()
    assert not (prepared.plugin_copy / "evals/example/results").exists()
    assert prepare.ignored_paths(tmp_path, str(tmp_path), [".env.example"]) == {".env.example"}
    result = subprocess.run(["git", "-C", str(prepared.plugin_copy), "rev-list", "--count", "HEAD"], capture_output=True)
    assert result.stdout.strip() == b"1"


def test_fixture_description_preserves_books_and_adds_task_signals():
    config = yaml.safe_load((FIXTURE / "book/book.yaml").read_text(encoding="utf-8"))
    path = config["skill_md"]["description_file"]
    assert path
    description = " ".join((FIXTURE / "book" / path).read_text(encoding="utf-8").split())
    assert len(description) <= 1024
    for marker in ("Rouse", "Sylvester", "Schell", "Meadows", "stocks, flows and feedback",
                   "Ribbon Harbor", "gate identity", "single-berth", "closing records", "闸口辨认"):
        assert marker in description


def test_fixture_uses_vane_signal_and_peer_heading_level():
    for path in FIXTURE.rglob("book.yaml"):
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert "风向试验" not in config["skill_md"]["when_to_use_line"]
        assert "风牌试验" in config["skill_md"]["when_to_use_line"]
        assert config["skill_md"]["table_heading"].startswith("### ")


@pytest.mark.parametrize("name", STOP_NAMES)
def test_fixture_quotes_have_actual_translations(name):
    expected = {
        "gate-token": ("Place the blue token beside the gate before moving a ribbon.", "移动纸带之前，先把蓝色标记放在闸口旁。"),
        "single-vane": ("Turn one amber vane and copy its previous direction into the ledger.", "转动一个琥珀色风牌，并把它原先的方向抄入记录簿。"),
        "visible-close": ("Keep the final ribbon visible until both harbor keepers sign the ledger.", "在两位港口看守都签署记录簿之前，让最后一条纸带保持可见。"),
    }
    for slug, (quote, translation) in expected.items():
        text = (FIXTURE / "stops" / name / "cards" / f"{slug}.md").read_text(encoding="utf-8")
        reading = text.split("## R", 1)[1].split("## I", 1)[0]
        assert f"> {quote}\n" in reading
        assert f"> 译：{translation}\n" in reading


@pytest.mark.parametrize("name", STOP_NAMES)
def test_fixture_normal_scope_and_terms(name):
    work = FIXTURE / "stops" / name
    text = (work / "cards/single-vane.md").read_text(encoding="utf-8")
    assert "全港放行由设计者判断" not in text
    assert ("对齐后即可开放整个港口" in text) == (name == "02-propagation")
    glossary = (work / "candidates/glossary.md").read_text(encoding="utf-8")
    terms = yaml.safe_load(glossary.split("```yaml\n", 1)[1].split("```", 1)[0])
    ids = {term["id"] for term in terms}
    assert all(term.get("key_distinction") for term in terms)
    for path in sorted((work / "verify/out").glob("*.yaml")):
        units = yaml.safe_load(path.read_text(encoding="utf-8"))["units"]
        assert all(unit.get("supports", {}).get("terms") for unit in units)
        assert all(set(unit["supports"]["terms"]) <= ids for unit in units)
    for path in sorted((work / "meta").glob("*.yaml")):
        meta = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert len(meta["intents"]) >= 2 and all(question != meta["title"] for question in meta["intents"])


def test_prepare_rejects_home_before_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    with pytest.raises(ValueError, match="主目录"):
        prepare.prepare(tmp_path / "nested")
    assert not (tmp_path / "nested").exists()


def test_prepare_refuses_reuse(prepared):
    with pytest.raises(ValueError, match="新目录"):
        prepare.prepare(prepared.workdir.parent)


def test_run_logged_records_failure_and_hash_changes(prepared):
    watched = prepared.workdir / "scratch.txt"
    put(watched, "before")
    command = [sys.executable, "-c", "from pathlib import Path; import sys; Path(sys.argv[1]).write_text('after'); print('captured'); sys.exit(7)", str(watched)]
    assert logged.run_logged(prepared.log_dir, command, prepared.plugin_copy) == 7
    record = json.loads((prepared.log_dir / "commands.jsonl").read_text(encoding="utf-8"))
    assert record["argv"] == command and record["returncode"] == 7
    assert record["started_at"] <= record["ended_at"]
    assert record["before"]["workdir"]["scratch.txt"] == sha256(b"before")
    assert record["after"]["workdir"]["scratch.txt"] == sha256(b"after")
    assert record["before"]["plugin_copy"] == record["after"]["plugin_copy"]
    assert b"captured" in (prepared.log_dir / record["output"]).read_bytes()


def test_run_logged_records_launch_failure(prepared):
    assert logged.run_logged(prepared.log_dir, [str(prepared.workdir / "missing")]) == 127
    record = json.loads((prepared.log_dir / "commands.jsonl").read_text(encoding="utf-8"))
    assert record["error"]["type"] == "FileNotFoundError"


def test_run_logged_cli_separator(prepared):
    command = [sys.executable, "-c", "print('wrapped')"]
    assert logged.main([str(prepared.log_dir), "--", *command]) == 0
    row = json.loads((prepared.log_dir / "commands.jsonl").read_text(encoding="utf-8"))
    assert row["argv"] == command


@pytest.mark.parametrize("name", STOP_NAMES)
def test_adopted_stop_fails_then_passes(prepared, name):
    workdir = prepared.workdir / "stops" / name
    if name == "01-quotes":
        command = [sys.executable, str(SCRIPTS / "check_cards.py"), str(workdir)]
    elif name == "02-propagation":
        command = [sys.executable, str(HERE / "grade.py"), "check-propagation", str(workdir)]
    else:
        command = [sys.executable, str(SCRIPTS / "integrate.py"), str(workdir)]
    assert subprocess.run(command, capture_output=True).returncode == 1
    repair_stop(workdir, name)
    assert subprocess.run(command, capture_output=True).returncode == 0


@pytest.mark.parametrize("name", STOP_NAMES)
def test_adopted_stop_supports_evidence_and_prior_audits(prepared, name):
    work = prepared.workdir / "stops" / name
    cfg = bookconf.open_workdir(work)
    text = verify_units.show(cfg, work, ["u02-01"])
    assert "raw recheck R1" in text and "只用于单个泊位" in text
    assert stage1.coverage(cfg, work).problems == []
    assert verify_units.aggregate(cfg, work).problems == []


def test_propagation_accepts_paraphrase(prepared):
    work = prepared.workdir / "stops/02-propagation"
    card = work / "cards/single-vane.md"
    put(card, card.read_text(encoding="utf-8").replace("对齐后即可开放整个港口（p.10）。", "试验只适用于单一泊位，不批准其他区域（p.10）。"))
    assert grade.check_propagation(work) == []


def test_propagation_does_not_accept_boundary_only(prepared):
    work = prepared.workdir / "stops/02-propagation"
    card = work / "cards/single-vane.md"
    put(card, card.read_text(encoding="utf-8") + "\n只用于单个泊位。\n")
    assert grade.check_propagation(work)


@pytest.fixture
def good(prepared, monkeypatch):
    # 执行真实确定性检查，只有进程启动与无界面运行的事件由本地回放代替。
    work, plugin, logs = prepared.workdir, prepared.plugin_copy, prepared.log_dir
    adopted = work / "stops/01-quotes"
    for child in adopted.iterdir():
        destination = work / child.name
        if child.is_dir():
            shutil.copytree(child, destination, dirs_exist_ok=True)
        else:
            shutil.copyfile(child, destination)
    repair_stop(work, "01-quotes")
    for name in grade.FLOW_FILES:
        path = work / name
        if not path.exists():
            put(path, "# 合成测试产物，未独立验证\n")
    for pattern in grade.FLOW_GLOBS:
        if not list(work.glob(pattern)):
            put(work / pattern.replace("*", "synthetic"), "# 合成测试产物，未独立验证\n")
    for stem in ("frameworks", "principles", "cases", "counter-examples"):
        put(work / f"candidates/{stem}.md", "# 已读，测试在此仅检查产物存在\n")

    def process(command, **kwargs):
        filename = Path(command[1]).name
        if filename == "check_cards.py":
            code = check_cards.main(command[2:])
        elif filename == "integrate.py":
            code = integrate.main(command[2:])
        elif filename == "grade.py":
            code = grade.main(command[2:])
        elif filename == "runner.py":
            out = logs / "runs/new/q1-r1.jsonl"
            card = plugin / "skills/game-design-theory/references/ribbon-gate-token.md"
            events = [
                {"type":"assistant", "message":{"content":[{"type":"tool_use", "name":"Skill", "id":"s1", "input":{"skill":"game-toolkit:design-discuss"}}, {"type":"tool_use", "name":"Read", "id":"r1", "input":{"file_path":card.as_posix()}}]}},
                {"type":"user", "message":{"content":[{"type":"tool_result", "tool_use_id":"r1", "content":"Synthetic card"}, {"type":"tool_result", "tool_use_id":"s1", "content":"Launching skill"}]}},
                {"type":"result", "subtype":"success", "result":"Synthetic answer"},
            ]
            put(out, "".join(json.dumps(row) + "\n" for row in events))
            write_json(Path(str(out) + ".meta.json"), {"batch_id":"synthetic", "plugin_dir":plugin.as_posix(),
                       "plugin_sha256": grade.runner.plugin_digest(plugin), "returncode":0})
            code = 0
        else:
            raise AssertionError(command)
        return subprocess.CompletedProcess(command, code, b"synthetic local replay\n", b"")

    monkeypatch.setattr(logged.subprocess, "run", process)
    scripts = plugin / "skills/book-to-reference/scripts"
    for filename in ("check_cards.py", "integrate.py"):
        assert logged.run_logged(logs, [sys.executable, (scripts / filename).as_posix(), work.as_posix()]) == 0
    put(logs / "prompts.tsv", "q1\tt01-01\tSynthetic request\n")
    assert logged.run_logged(logs, [sys.executable, (scripts / "runner.py").as_posix(),
                                  (logs / "prompts.tsv").as_posix(), (logs / "runs").as_posix(),
                                  "--variant", f"new={plugin.as_posix()}", "--reps", "1", "--lanes", "1",
                                  "--budget", ".1", "--runs-root", (logs / "host").as_posix(), "--batch-id", "synthetic"]) == 0
    for name in STOP_NAMES:
        stop = work / "stops" / name
        if name == "01-quotes":
            command = [sys.executable, (scripts / "check_cards.py").as_posix(), stop.as_posix()]
        elif name == "02-propagation":
            command = [sys.executable, (HERE / "grade.py").as_posix(), "check-propagation", stop.as_posix()]
        else:
            command = [sys.executable, (scripts / "integrate.py").as_posix(), stop.as_posix()]
        assert logged.run_logged(logs, command) == 1
        repair_stop(stop, name)
        assert logged.run_logged(logs, command) == 0
    return prepared


def by_name(case):
    return {item.name: item for item in grade.grade(case.workdir, case.plugin_copy, case.log_dir)}


def edit_records(case, change):
    path = case.log_dir / "commands.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    change(rows)
    for index, row in enumerate(rows, 1):
        row["seq"] = index
    put(path, "".join(json.dumps(row) + "\n" for row in rows))


def test_grade_all_automatic_checks_pass(good):
    checks = by_name(good)
    assert len(checks) == 10
    assert all(item.ok for item in checks.values()), checks


def test_grade_missing_artifact(good):
    (good.workdir / "BOOK_OVERVIEW.md").unlink()
    assert not by_name(good)["flow.artifacts"].ok


@pytest.mark.parametrize("script, check", [("check_cards.py", "flow.cards_check"), ("integrate.py", "flow.integrate")])
def test_grade_requires_last_successful_check(good, script, check):
    def change(rows):
        record = next(row for row in rows if Path(row["argv"][1]).name == script)
        record["returncode"] = 1
    edit_records(good, change)
    assert not by_name(good)[check].ok


def test_grade_missing_integrated_card(good):
    (good.plugin_copy / "skills/game-design-theory/references/ribbon-gate-token.md").unlink()
    assert not by_name(good)["flow.integrated"].ok


def test_grade_residue(good):
    path = good.plugin_copy / "skills/game-design-theory/references/ribbon-gate-token.md"
    put(path, path.read_text(encoding="utf-8") + "\n参考单元\n")
    assert not by_name(good)["flow.integrated"].ok


def test_grade_requires_scope(good):
    (good.workdir / "candidates/_scope.yaml").unlink()
    assert not by_name(good)["flow.scope"].ok


def test_grade_requires_selection_table(good):
    path = good.plugin_copy / "skills/game-design-theory/SKILL.md"
    put(path, "# 没有本书选卡表\n")
    assert not by_name(good)["flow.integrated"].ok


@pytest.mark.parametrize("variant", ["no-card", "failed", "denied", "no-skill"])
def test_grade_requires_successful_consumption(good, variant):
    path = good.log_dir / "runs/new/q1-r1.jsonl"
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if variant == "no-card":
        events[0]["message"]["content"][1]["input"]["file_path"] = "unrelated.md"
    elif variant == "failed":
        events[-1]["subtype"] = "error"
    elif variant == "denied":
        events[1]["message"]["content"][0]["is_error"] = True
    else:
        events[0]["message"]["content"] = events[0]["message"]["content"][1:]
    put(path, "".join(json.dumps(row) + "\n" for row in events))
    edit_records(good, lambda rows: rows[2].update(runs=snapshot(good.log_dir / "runs")))
    assert not by_name(good)["consumption"].ok


@pytest.mark.parametrize("fault", ["batch", "error", "nonzero", "changed-after-run"])
def test_grade_rejects_untrusted_run(good, fault):
    meta_path = good.log_dir / "runs/new/q1-r1.jsonl.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if fault == "batch":
        meta["batch_id"] = "other-batch"
    elif fault == "error":
        meta["error"] = {"type":"RuntimeError", "message":"synthetic failure"}
    elif fault == "nonzero":
        meta["returncode"] = 1
    else:
        meta["note"] = "changed after runner finished"
    write_json(meta_path, meta)
    if fault != "changed-after-run":
        edit_records(good, lambda rows: rows[2].update(runs=snapshot(good.log_dir / "runs")))
    assert not by_name(good)["consumption"].ok


@pytest.mark.parametrize("name", STOP_NAMES)
@pytest.mark.parametrize("fault", ["before-check", "no-rerun", "unchanged", "order"])
def test_grade_stop_negative_cases(good, name, fault):
    def change(rows):
        indices = [i for i, row in enumerate(rows) if name in " ".join(row["argv"])]
        first, last = indices[0], indices[-1]
        if fault == "before-check":
            rows[first]["before"] = copy.deepcopy(rows[last]["before"])
        elif fault == "no-rerun":
            del rows[last]
        elif fault == "unchanged":
            rows[last]["before"] = copy.deepcopy(rows[first]["before"])
            rows[last]["after"] = copy.deepcopy(rows[first]["after"])
        else:
            rows[first]["returncode"], rows[last]["returncode"] = 0, 1
    edit_records(good, change)
    assert not by_name(good)[f"stop.{name}"].ok


def test_grade_rejects_bad_log(good):
    edit_records(good, lambda rows: rows[0].update(output_sha256="0" * 64))
    assert not by_name(good)["logs.valid"].ok


def test_grade_requires_same_check(good):
    def change(rows):
        row = next(row for row in reversed(rows) if "01-quotes" in " ".join(row["argv"]))
        row["argv"] += ["--only", "quotes"]
    edit_records(good, change)
    assert not by_name(good)["stop.01-quotes"].ok


def test_grade_requires_stop_order(good):
    def change(rows):
        times = sorted((row["started_at"], row["ended_at"]) for row in rows[3:7])
        rows[3:7] = rows[5:7] + rows[3:5]
        for row, (start, end) in zip(rows[3:7], times):
            row["started_at"], row["ended_at"] = start, end
    edit_records(good, change)
    checks = by_name(good)
    assert checks["logs.valid"].ok
    assert not checks["stop.02-propagation"].ok


@pytest.mark.parametrize("phase", ["cards-integrate", "during-integrate", "integrate-runner", "during-runner", "stop-after-check"])
def test_grade_hash_bindings_reject_changed_inputs(good, phase):
    def change(rows):
        if phase == "cards-integrate":
            rows[1]["before"]["workdir"]["cards/gate-token.md"] = "0" * 64
        elif phase == "during-integrate":
            rows[1]["after"]["workdir"]["cards/gate-token.md"] = "0" * 64
        elif phase == "integrate-runner":
            rows[2]["before"]["plugin_copy"]["skills/game-design-theory/references/ribbon-gate-token.md"] = "0" * 64
        elif phase == "during-runner":
            rows[2]["after"]["plugin_copy"]["skills/game-design-theory/references/ribbon-gate-token.md"] = "0" * 64
    edit_records(good, change)
    if phase == "stop-after-check":
        path = good.workdir / "stops/01-quotes/cards/gate-token.md"
        put(path, path.read_text(encoding="utf-8") + "\n改变受检内容\n")
    checks = by_name(good)
    expected = "flow.integrate" if phase in ("cards-integrate", "during-integrate") else "stop.01-quotes" if phase == "stop-after-check" else "consumption"
    assert not checks[expected].ok


def test_restore_main_after_stops_does_not_change_start(good):
    # 真实第二次日志的顺序是 42→43、45→47、48→51/52，54 再接入主流程。
    shape = json.loads((HERE / "fixtures/restore-after-stops.json").read_text(encoding="utf-8"))
    assert [(r["seq"], r["returncode"]) for r in shape if r["seq"] in (42, 43, 45, 47, 48, 51, 52, 54)] == [
        (42, 1), (43, 0), (45, 1), (47, 0), (48, 1), (51, 0), (52, 0), (54, 0)]
    scripts = good.plugin_copy / "skills/book-to-reference/scripts"
    assert logged.run_logged(good.log_dir, [sys.executable, str(scripts / "integrate.py"), str(good.workdir)]) == 0
    checks = by_name(good)
    assert checks["flow.integrate"].ok
    assert all(checks[f"stop.{name}"].ok for name in STOP_NAMES)
    assert checks["consumption"].ok


def test_real_shape_without_paths_cannot_be_bound():
    shape = json.loads((HERE / "fixtures/restore-after-stops.json").read_text(encoding="utf-8"))
    rows = {r["seq"]: r for r in shape}
    work, plugin = Path("/fictional/session/book").resolve(), Path("/fictional/session/plugin").resolve()
    assert "旧日志缺新证据" in grade._integration_binding(shape, rows[35], work, plugin, work)
    assert "旧日志缺新证据" in grade._integration_binding(shape, rows[54], work, plugin, work)


def test_logged_paths_record_actual_config_and_allow_unrelated_change(good):
    rows, _ = grade.read_records(good.log_dir)
    assert rows[0]["inputs"]["before"]["paths"]["cards"] == (good.workdir / "cards").as_posix()
    assert set(rows[0]["inputs"]["before"]["paths"]) == set(bookconf.Paths.__dataclass_fields__)
    # notes 裁定变化不改受检材料；绑定不得依赖整份配置字节相等。
    rows[1]["before"]["workdir"]["book.yaml"] = "a" * 64
    assert not grade._integration_binding(rows, rows[1], good.workdir, good.plugin_copy, good.workdir)
    path = good.workdir / "book.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config.setdefault("paths", {})["cards"] = "cards-B"
    put(path, yaml.safe_dump(config, allow_unicode=True))
    command = rows[0]["argv"]
    evidence = logged.input_paths(command, Path(rows[0]["cwd"]), {"plugin_copy": good.plugin_copy})
    assert evidence["paths"]["cards"] == (good.workdir / "cards-B").as_posix()
    assert rows[0]["inputs"]["before"]["paths"]["cards"] != evidence["paths"]["cards"]


def test_logged_paths_reject_switch_to_existing_unchecked_cards(good):
    rows, _ = grade.read_records(good.log_dir)
    for row in rows[:2]:
        for phase in ("before", "after"):
            row[phase]["workdir"]["cards-B/gate-token.md"] = "b" * 64
    for phase in ("before", "after"):
        rows[1]["inputs"][phase]["paths"]["cards"] = (good.workdir / "cards-B").as_posix()
    problem = grade._integration_binding(rows, rows[1], good.workdir, good.plugin_copy, good.workdir)
    assert "实际输入路径不一致" in problem


@pytest.mark.parametrize("option", [["--only", "quotes"], ["--only=quotes"]])
def test_partial_quotes_not_full_check(good, option):
    edit_records(good, lambda rows: rows[0]["argv"].extend(option))
    checks = by_name(good)
    assert not checks["flow.cards_check"].ok
    assert not checks["flow.integrate"].ok
    assert not checks["consumption"].ok


@pytest.mark.parametrize("digest", [None, "old-version"])
def test_consumption_rejects_old_cache_under_new_plugin_snapshot(good, digest):
    # A 的成功事件和 Read 保留，B 的命令前后快照和文件结束哈希也都真实有效。
    path = good.log_dir / "runs/new/q1-r1.jsonl.meta.json"
    meta = json.loads(path.read_text(encoding="utf-8"))
    if digest is None:
        meta.pop("plugin_sha256")
    else:
        rows, _ = grade.read_records(good.log_dir)
        old_state = dict(rows[1]["after"]["plugin_copy"])
        old_state["skills/game-design-theory/references/ribbon-gate-token.md"] = sha256(b"version A card")
        meta["plugin_sha256"] = grade.runner.plugin_digest_from_snapshot(old_state)
        assert meta["plugin_sha256"] != grade.runner.plugin_digest(good.plugin_copy)
        run_path = good.log_dir / "runs/new/q1-r1.jsonl"
        events = [json.loads(line) for line in run_path.read_text(encoding="utf-8").splitlines()]
        events[1]["message"]["content"][0]["content"] = "version A card"
        events[-1]["result"] = "Answer from version A"
        put(run_path, "".join(json.dumps(event) + "\n" for event in events))
    write_json(path, meta)
    edit_records(good, lambda rows: rows[2].update(runs=snapshot(good.log_dir / "runs")))
    check = by_name(good)["consumption"]
    assert not check.ok
    assert ("旧运行缺新证据" if digest is None else "旧缓存") in check.detail


def test_missing_paths_never_projects_current_config(good):
    edit_records(good, lambda rows: [row.pop("inputs", None) for row in rows])
    checks = by_name(good)
    for name in ("flow.cards_check", "flow.integrate", "consumption", *(f"stop.{name}" for name in STOP_NAMES)):
        assert not checks[name].ok
        assert "旧日志缺新证据" in checks[name].detail


def test_eval_output_paths_reject_plugin(prepared):
    with pytest.raises(ValueError, match="输出"):
        logged.run_logged(prepared.plugin_copy / "logs", ["fake"])
    assert not (prepared.plugin_copy / "logs").exists()


def test_integrated_card_must_be_the_generated_version(good):
    path = good.plugin_copy / "skills/game-design-theory/references/ribbon-gate-token.md"
    put(path, path.read_text(encoding="utf-8") + "\n合法文字但未经接入。\n")
    assert not by_name(good)["flow.integrated"].ok
