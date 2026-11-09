"""口径 B 分组判定，归因列不能改变质量计数或放行未完成评分。"""
import json
from pathlib import Path
import shutil

import pytest

from bookconf import MaskNames
import grading

NAMES = MaskNames(["Mira Example", "Second Writer"], ["The Lantern Workshop", "Another Book"])
RUNS = Path(__file__).parent / "fixtures/runs"


def test_mask_hides_markers():
    text = "Mira Example Second Writer The Lantern Workshop Another Book p.12 pp.13–15 micro-a.md docs/IDEAS.md"
    masked = grading.mask(text, NAMES)
    assert all(name not in masked for name in NAMES.authors + NAMES.titles)
    assert "p.12" not in masked and "micro-a.md" not in masked
    assert "docs/IDEAS.md" in masked
    assert grading.leaks(masked, NAMES) == 0


def packet_inputs(tmp_path):
    arms = {name: tmp_path / name for name in ("baseline", "candidate")}
    for directory in arms.values():
        directory.mkdir()
        for rep in (1, 2):
            shutil.copyfile(RUNS / "success.jsonl", directory / f"a001-r{rep}.jsonl")
    return ({"a001": "t01-01"}, {"t01-01": {"correct": "能比较影子"}}, {"t01-01": "怎样比较影子？"}, arms)


def test_packets_key_separate(tmp_path):
    idmap, rubric, prompts, arms = packet_inputs(tmp_path)
    packets, key = grading.build_packets(idmap, rubric, prompts, arms, 2, 1, 1110, NAMES)
    assert all(word not in packets[0] for word in ("baseline", "candidate", '"arm"'))
    assert set(key["a001|甲"]) == {"arm", "rep", "forced"}
    assert key["a001|cmp1"]["X"] != key["a001|cmp1"]["Y"]


def test_packets_deterministic(tmp_path):
    inputs = packet_inputs(tmp_path)
    assert grading.build_packets(*inputs, 2, 2, 1110, NAMES) == grading.build_packets(*inputs, 2, 2, 1110, NAMES)


def grades_for(rows):
    grades = []
    key = {}
    idmap = {}
    meta = {}
    for index, (group, verdict, required, regression) in enumerate(rows, 1):
        qid, item = f"a{index:03d}", f"t{index:02d}-01"
        idmap[qid] = item
        meta[item] = {"group": group, "required": required, "source": group}
        key[qid + "|cmp1"] = {"X": "candidate", "Y": "baseline"}
        grades.append({"q": qid, "cmp1": {"verdict": {"better": "X_better", "worse": "Y_better", "same": "same", "undecided": "unclear"}[verdict],
                                               "regression": regression, "difference": "编造的评分差异"}})
    return grades, key, idmap, meta


def aggregate(grades, key, idmap, meta, protocol, chain=None):
    frozen = {group: [item for item, info in meta.items() if info["required"] and
                     ("O" if info["group"].startswith("O") else info["group"]) == group] for group in ("O", "N")}
    # 合成测试有时只考一个组；缺省组明确声明为空，有可选题的组仍须接受完整性检查。
    present = {"O" if info["group"].startswith("O") else info["group"] for info in meta.values()}
    requirements = {"required_items": frozen, "empty_groups": {group: "本合成测试明确不设此组" for group in ("O", "N") if group not in present}}
    return grading.aggregate(grades, key, idmap, meta, protocol, chain, requirements=requirements)


def test_b_protocol_groups_separate():
    inputs = grades_for([("O", "better", True, "none")] * 3 + [("N", "worse", True, "none")])
    assert aggregate(*inputs, "B").status == "fail"
    assert aggregate(*inputs, "pooled-required").status == "pass"


def test_attribution_invariant():
    inputs = grades_for([("N", "worse", True, "漏了必要步骤")])
    results = [aggregate(*inputs, "B", info) for info in
               (None, {"a001": {"baseline": [True], "candidate": [True]}},
                {"a001": {"baseline": [False], "candidate": [False]}})]
    assert all((r.counts, r.substantive, r.status) == (results[0].counts, results[0].substantive, results[0].status) for r in results)


def test_substantive_fails_b():
    result = aggregate(*grades_for([("O-other", "worse", True, "漏了必要步骤"), ("O", "better", True, "none")]), "B")
    assert result.status == "fail" and result.substantive == ["a001"]


@pytest.mark.parametrize("duplicate", [False, True])
def test_missing_or_duplicate_grade_incomplete(duplicate):
    grades, key, idmap, meta = grades_for([("O", "same", True, "none")])
    grades = grades * 2 if duplicate else []
    assert aggregate(grades, key, idmap, meta, "B").status == "incomplete"


def test_undecided_incomplete():
    assert aggregate(*grades_for([("N", "undecided", True, "none")]), "B").status == "incomplete"


def test_optional_not_counted():
    result = aggregate(*grades_for([("O", "same", True, "none"), ("N", "worse", False, "漏了必要步骤")]), "B")
    assert result.status == "incomplete" and not result.substantive
    assert result.counts.get(("N", "worse"), 0) == 0


def test_failed_answer_cannot_enter_packets(tmp_path):
    idmap, rubric, prompts, arms = packet_inputs(tmp_path)
    shutil.copyfile(RUNS / "error.jsonl", arms["baseline"] / "a001-r1.jsonl")
    with pytest.raises(ValueError, match="failed"):
        grading.build_packets(idmap, rubric, prompts, arms, 2, 1, 1, NAMES)


def test_make_prompts_preserves_identity(tmp_path):
    items = {"p-lamp": {"task": "比较影子", "group": "O-other", "required": True, "source": "Other"}}
    prompts, idmap, meta = grading.make_prompts(items, {"p-lamp": "怎么比较影子？"}, tmp_path)
    assert json.loads(idmap.read_text(encoding="utf-8")) == {"a001": "p-lamp"}
    assert json.loads(meta.read_text(encoding="utf-8"))["p-lamp"]["group"] == "O-other"
    assert prompts.read_text(encoding="utf-8").startswith("a001\tO-other\t")


def test_forced_comparison_stays_separate(tmp_path):
    idmap, rubric, prompts, arms = packet_inputs(tmp_path)
    packets, key = grading.build_packets(idmap, rubric, prompts, arms, 2, 1, 1111, NAMES, arms)
    assert "a001|cmp2" in key and "比较 2" in packets[0]
    answers = [row for identity, row in key.items() if "cmp" not in identity]
    assert sum(row["forced"] for row in answers) == 2
    assert len(answers) == 6


def test_historical_key_export_is_explicit(tmp_path):
    inputs = packet_inputs(tmp_path)
    _, key = grading.build_packets(*inputs, 2, 1, 1110, NAMES)
    frozen = json.dumps(key, ensure_ascii=False)
    old = grading.legacy_key(key, "accepted", "release")
    assert set(old["a001|甲"]) == {"variant", "rep"}
    assert set(key["a001|甲"]) == {"arm", "rep", "forced"}
    assert json.dumps(key, ensure_ascii=False) == frozen


def test_pick_items_respects_quotas_and_book_minima():
    groups = {"tasks": [
        {"task_id": "t01-01", "group": "O", "capabilities": ["main"]},
        {"task_id": "t02-01", "group": "O-partial", "capabilities": ["main"]},
        {"task_id": "t03-01", "group": "N"}, {"task_id": "t04-01", "group": "N"},
    ]}
    caps = {"capabilities": [
        {"id": "main", "source": "Lantern", "depth": "method", "supports": "主书任务"},
        {"id": "other-a", "source": "Other A", "depth": "method", "supports": "旧能力 A"},
        {"id": "other-b", "source": "Other B", "depth": "method", "supports": "旧能力 B"},
    ], "entry_sensitive": [{"ids": ["other-a"]}]}
    tasks = {row["task_id"]: "编造的任务" for row in groups["tasks"]}
    config = {"target_source": "Lantern", "quotas": {"O-book": [1, 1], "O-other": [2, 0], "N": [1, 1]},
              "exclude_items": [], "other_books": {"Other A": 1, "Other B": 1}}
    selected = grading.pick_items(groups, caps, tasks, set(), config, 42)
    assert len(selected) == 6 and sum(row["required"] for row in selected.values()) == 4
    assert selected["p-other-b"]["source"] == "Other B"
    assert selected == grading.pick_items(groups, caps, tasks, set(), config, 42)


def test_old_tasks_supported_only_by_other_book_are_eligible():
    groups = {"tasks": [{"task_id": "t01-01", "group": "O", "capabilities": ["other"]}]}
    caps = {"capabilities": [{"id": "other", "source": "Other", "supports": "原来已能做"}]}
    cfg = {"target_source": "New", "quotas": {"O": [1, 0], "N": [0, 0], "O-other": [0, 0]}}
    assert "t01-01" in grading.pick_items(groups, caps, {"t01-01": "任务"}, set(), cfg, 1)
    with pytest.raises(ValueError, match="eligible pool"):
        grading.pick_items(groups, caps, {"t01-01": "任务"}, set(), cfg, 1, old_pool="migration")


@pytest.mark.parametrize("field", ["difference", "regression"])
def test_missing_judgment_details_incomplete(field):
    inputs = grades_for([("O", "same", True, "none"), ("N", "same", True, "none")])
    del inputs[0][0]["cmp1"][field]
    assert aggregate(*inputs, "B").status == "incomplete"


def test_frozen_required_manifest_detects_missing_item():
    grades, key, idmap, meta = grades_for([("O", "same", True, "none"), ("N", "same", True, "none")])
    frozen = {"required_items": {"O": ["t01-01", "t09-01"], "N": ["t02-01"]}}
    assert grading.aggregate(grades, key, idmap, meta, "B", requirements=frozen).status == "incomplete"


def test_b_requires_frozen_scope_and_explicit_empty_reason():
    inputs = grades_for([("O", "same", True, "none")])
    assert grading.aggregate(*inputs, "B").status == "incomplete"
    frozen = {"quotas": {"O": [1, 0], "N": [0, 0]}}
    assert grading.aggregate(*inputs, "B", requirements=frozen).status == "incomplete"
    frozen["empty_groups"] = {"N": "本书冻结范围没有新增任务"}
    assert grading.aggregate(*inputs, "B", requirements=frozen).status == "pass"


def test_b_checks_each_frozen_old_subgroup_not_only_total():
    inputs = grades_for([("O-book", "same", True, "none"), ("O-book", "same", True, "none"), ("N", "same", True, "none")])
    frozen = {"quotas": {"O-book": [1, 0], "O-other": [1, 0], "N": [1, 0]}}
    result = grading.aggregate(*inputs, "B", requirements=frozen)
    assert result.status == "incomplete" and any("O-other" in p for p in result.problems)


def test_b_rejects_malformed_frozen_manifest():
    inputs = grades_for([("O", "same", True, "none"), ("N", "same", True, "none")])
    assert grading.aggregate(*inputs, "B", requirements={"required_items": []}).status == "incomplete"
