"""Structure-only contracts, including the reviewed real project snapshot.

Tests never read the source game projects, execute an engine or contact a service.
"""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import pytest
import yaml

SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL.parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import check_content_model as cm  # noqa: E402


def field(fid, value="value", kind="value", interpretive=False):
    result = {
        "id": fid, "classification": "interpretive" if interpretive else "declarative",
        "kind": kind, "value": value, "sources": ["source.accepted"],
        "effective": "Accepted snapshot load; test fixture only.",
    }
    if interpretive:
        result["owner"] = "Framework"
    return result


@pytest.fixture
def model():
    data = cm.load_model(SKILL / "examples" / "content-model" / "minimal.content.yaml")
    instance = data["instances"][0]
    data["catalogs"] = [{"id": "catalog.related", "fields": [field("catalog.query", "external-selector")]}]
    data["mechanisms"] = [{"id": "mechanism.rule", "status": "gap",
                           "fields": [field("mechanism.home", "Missing accepted contract", interpretive=True)]}]
    instance["adopted"]["branches"] = [{"id": "branch.variant", "fields": [field("branch.name")]}]
    instance["adopted"]["fields"] = [
        field("item.related", ["catalog.related"], "relation"),
        field("item.rule", ["mechanism.rule"], "mechanism_refs"),
        field("item.variants", ["branch.variant"], "branch_refs"),
        field("item.condition", "existing-contract-condition-id"),
        field("item.amount", 2.5),
    ]
    instance["release"] = [field("item.available", True)]
    extra = ["branch.name", "item.related", "item.rule", "item.variants", "item.condition", "item.amount", "item.available"]
    data["publication_ir"][0]["fields"].extend({"id": "out." + fid, "from": [fid]} for fid in extra)
    return data


def at(data, path):
    for part in path:
        data = data[part]
    return data


def invalid(model, expected):
    errors = cm.validate(model)
    assert errors, "expected rejection"
    assert any(expected in e for e in errors), errors


def test_complete_graph_and_renamed_ir_pass(model):
    assert cm.validate(model) == []


@pytest.mark.parametrize("path", [
    ("sources", 0), ("catalogs", 0), ("mechanisms", 0),
    ("instances", 0), ("instances", 0, "identity", 0),
    ("instances", 0, "adopted", "branches", 0),
    ("instances", 0, "discussion", 0), ("publication_ir", 0),
    ("publication_ir", 0, "fields", 0),
])
def test_ids_are_global_and_unique(model, path):
    at(model, path)["id"] = "source.notes"
    invalid(model, "duplicate id")


@pytest.mark.parametrize("path", [
    ("instances", 0, "identity", 0),
    ("instances", 0, "adopted", "fields", 0),
    ("instances", 0, "adopted", "branches", 0, "fields", 0),
    ("instances", 0, "release", 0),
    ("instances", 0, "discussion", 0, "fields", 0),
    ("catalogs", 0, "fields", 0), ("mechanisms", 0, "fields", 0),
])
def test_every_domain_field_requires_classification(model, path):
    del at(model, path)["classification"]
    invalid(model, "classification")


@pytest.mark.parametrize("owner", ["Framework", "Interface", "C"])
def test_interpretive_owner_variants_pass(model, owner):
    model["instances"][0]["discussion"][0]["fields"][0]["owner"] = owner
    assert cm.validate(model) == []


@pytest.mark.parametrize("change", [
    {"classification": "maybe"}, {"classification": None}, {"classification": []},
    {"classification": "interpretive"}, {"classification": "interpretive", "owner": "Content"},
    {"classification": "interpretive", "owner": ""}, {"classification": "declarative", "owner": "C"},
])
def test_classification_or_owner_errors(model, change):
    model["instances"][0]["identity"][0].update(change)
    invalid(model, "classification" if change["classification"] not in ("interpretive", "declarative") else "owner")


@pytest.mark.parametrize("field_index,kind", [(0, "relation"), (1, "mechanism_refs"), (2, "branch_refs")])
@pytest.mark.parametrize("target,diagnostic", [("not-registered", "unresolved reference"),
                                           ("source.accepted", "has kind source")])
def test_reference_resolution_and_target_kind(model, field_index, kind, target, diagnostic):
    entry = model["instances"][0]["adopted"]["fields"][field_index]
    assert entry["kind"] == kind
    entry["value"] = [target]
    invalid(model, diagnostic)


@pytest.mark.parametrize("index", [0, 1, 2])
def test_reference_fields_reject_empty_scalar_duplicate_and_object(model, index):
    entry = model["instances"][0]["adopted"]["fields"][index]
    original = entry["value"][0]
    for bad in ([], original, [original, original], [{"id": original}]):
        entry["value"] = bad
        assert cm.validate(model)


def test_relation_can_reference_an_instance(model):
    model["instances"][0]["adopted"]["fields"][0]["value"] = ["example.item"]
    assert cm.validate(model) == []


@pytest.mark.parametrize("section", ["identity", "release"])
@pytest.mark.parametrize("sources", [None, [], [""], ["missing-source"], ["branch.variant"]])
def test_declarative_values_need_resolvable_sources(model, section, sources):
    model["instances"][0][section][0]["sources"] = sources
    invalid(model, "sources")


def test_missing_source_key_and_interpretive_source_are_checked(model):
    del model["instances"][0]["identity"][0]["sources"]
    invalid(model, "missing sources")
    model["instances"][0]["discussion"][0]["fields"][0]["sources"] = []
    invalid(model, "every field value needs a source")


@pytest.mark.parametrize("key", ["locator", "version"])
@pytest.mark.parametrize("value", ["", None, 123])
def test_source_locator_and_version_required(model, key, value):
    model["sources"][0][key] = value
    invalid(model, key)


@pytest.mark.parametrize("value", [None, "", []])
def test_effective_mode_required(model, value):
    model["instances"][0]["adopted"]["fields"][4]["effective"] = value
    invalid(model, "effective")


@pytest.mark.parametrize("target", ["example.item", "branch.variant"])
def test_discussion_targets_and_historical_version_pass(model, target):
    model["instances"][0]["discussion"][0].update(target=target, target_version="earlier-revision")
    assert cm.validate(model) == []


@pytest.mark.parametrize("value", ["", None, 42])
def test_discussion_version_required(model, value):
    model["instances"][0]["discussion"][0]["target_version"] = value
    invalid(model, "target_version")


def test_missing_discussion_version(model):
    del model["instances"][0]["discussion"][0]["target_version"]
    invalid(model, "missing target_version")


@pytest.mark.parametrize("target", ["unknown", "item.amount", "mechanism.rule"])
def test_discussion_target_must_resolve_to_instance_or_branch(model, target):
    model["instances"][0]["discussion"][0]["target"] = target
    invalid(model, ".target")


def test_other_instance_cannot_own_this_discussion_or_supply_ir_fields(model):
    model["instances"].append({"id": "second", "version": "v1", "identity": [field("second.name")],
                              "adopted": {"fields": [], "branches": [{"id": "second.branch", "fields": []}]},
                              "release": [], "discussion": []})
    model["publication_ir"].append({"id": "second.projection", "instance_id": "second", "fields": [],
                                    "excluded": ["second.name"]})
    assert cm.validate(model) == []
    model["instances"][0]["discussion"][0]["target"] = "second.branch"
    invalid(model, "must belong")
    model["publication_ir"][0]["fields"][0]["from"] = ["second.name"]
    invalid(model, "unknown author field for this instance")


def test_ir_accepts_rename_split_combine_and_exclusion(model):
    projection = model["publication_ir"][0]
    projection["fields"][0] = {"id": "out.combined", "from": ["example.name", "item.amount"]}
    projection["fields"].append({"id": "out.split", "from": ["example.name"]})
    assert cm.validate(model) == []
    projection["fields"] = []  # A wholly author-only instance is also legal.
    projection["excluded"] = [
        "example.name", "example.note.text", "branch.name", "item.related", "item.rule", "item.variants",
        "item.condition", "item.amount", "item.available",
    ]
    assert cm.validate(model) == []


@pytest.mark.parametrize("mutation,diagnostic", [
    ("missing_map", "missing field-set declaration"),
    ("identity", "unresolved reference"), ("foreign_type", "has kind source"),
    ("unknown_from", "unknown author field"), ("empty_from", "needs author field origins"),
    ("lost_field", "partition"), ("unknown_excluded", "partition"), ("overlap", "overlap"),
    ("raw_target_value", "unknown key value"), ("duplicate_target", "duplicate id"),
    ("duplicate_excluded", "duplicate entry"), ("interpretation", "non-publishable"),
    ("discussion", "non-publishable"),
])
def test_ir_invalid_field_set_relationships(model, mutation, diagnostic):
    projection = model["publication_ir"][0]
    if mutation == "missing_map":
        model["publication_ir"] = []
    elif mutation in ("identity", "foreign_type"):
        projection["instance_id"] = "unknown" if mutation == "identity" else "source.accepted"
    elif mutation == "unknown_from":
        projection["fields"][0]["from"] = ["unknown"]
    elif mutation == "empty_from":
        projection["fields"][0]["from"] = []
    elif mutation == "lost_field":
        projection["excluded"] = []
    elif mutation == "unknown_excluded":
        projection["excluded"].append("unknown")
    elif mutation == "overlap":
        projection["excluded"].append("example.name")
    elif mutation == "raw_target_value":
        projection["fields"][0]["value"] = 123
    elif mutation == "duplicate_target":
        projection["fields"].append(deepcopy(projection["fields"][0]))
    elif mutation == "duplicate_excluded":
        projection["excluded"] *= 2
    elif mutation == "interpretation":
        model["instances"][0]["identity"][0].update(classification="interpretive", owner="Interface")
    elif mutation == "discussion":
        # Even a mechanically declared discussion field is not a publication input.
        note = model["instances"][0]["discussion"][0]["fields"][0]
        note["classification"] = "declarative"
        del note["owner"]
        projection["fields"].append({"id": "out.note", "from": ["example.note.text"]})
        projection["excluded"] = []
    invalid(model, diagnostic)


@pytest.mark.parametrize("path", [
    (), ("instances", 0), ("instances", 0, "adopted"), ("instances", 0, "adopted", "branches", 0),
    ("instances", 0, "discussion", 0), ("catalogs", 0), ("mechanisms", 0),
])
def test_unclassified_fields_cannot_hide_outside_field_lists(model, path):
    at(model, path)["new_domain_field"] = 99
    invalid(model, "unknown key new_domain_field")


@pytest.mark.parametrize("value", [None, {"secret": 1}, [{"nested": 1}], [[1]], float("inf")])
def test_nested_or_nonfinite_field_values_rejected(model, value):
    model["instances"][0]["adopted"]["fields"][4]["value"] = value
    assert cm.validate(model)


@pytest.mark.parametrize("value", [2.5, 0, False, "declared text", ["symbol", 2.5, True], []])
def test_plain_scalar_values_and_arrays_pass(model, value):
    model["instances"][0]["adopted"]["fields"][4]["value"] = value
    assert cm.validate(model) == []


@pytest.mark.parametrize("value", [None, [], "text", 1, {}])
def test_invalid_top_level_reports_without_crashing(value):
    assert cm.validate(value)


@pytest.mark.parametrize("section", ["sources", "catalogs", "mechanisms", "instances", "publication_ir"])
def test_wrong_container_types_report_without_crashing(model, section):
    for value in (None, "bad", {}, [None]):
        model[section] = value
        assert cm.validate(model)


def test_checker_does_not_claim_semantics_engine_comparison_or_roundtrip(model):
    model["sources"][0].update(locator="unreachable-source", version="not-a-real-revision")
    model["instances"][0]["adopted"]["fields"][4]["value"] = -99999
    model["instances"][0]["adopted"]["fields"][3]["value"] = "invented-condition"
    # These require downstream ownership/contract/engine verification, not structure checks.
    assert cm.validate(model) == []


@pytest.mark.parametrize("status", ["gap", "indexed"])
def test_mechanism_index_is_not_a_completeness_gate(model, status):
    model["mechanisms"][0]["status"] = status
    assert cm.validate(model) == []


def test_unknown_mechanism_status_is_rejected(model):
    model["mechanisms"][0]["status"] = "fully-proven"
    invalid(model, ".status")


@pytest.mark.parametrize("raw", [
    "id: one\nid: two\n", "a: &cycle [*cycle]\n", "created: 2026-09-08\n",
    "a: .nan\n", "1: numeric-key\n", "a: [unfinished", "a: !!python/object:unknown {}\n",
    "base: &base {id: one}\nmerged: {<<: *base}\n",
])
def test_yaml_loader_rejects_ambiguous_or_unsupported_documents(tmp_path, capsys, raw):
    path = tmp_path / "bad.yaml"
    path.write_text(raw, encoding="utf-8")
    assert cm.main([str(path)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["scope"] == "structure-only" and result["status"] == "unreadable"


def test_cli_exit_codes_and_read_only_input(model, tmp_path, capsys):
    path = tmp_path / "model.yaml"
    path.write_text(yaml.safe_dump(model, allow_unicode=True), encoding="utf-8")
    before = path.read_bytes()
    assert cm.main([str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "ok"
    assert path.read_bytes() == before
    path.write_text("schema_version: wrong\n", encoding="utf-8")
    assert cm.main([str(path)]) == 1
    assert json.loads(capsys.readouterr().out)["status"] == "invalid"
    assert cm.main([str(tmp_path / "missing.yaml")]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "unreadable"


def test_plain_yaml_aliases_are_allowed_but_cycles_are_not(tmp_path, model):
    path = tmp_path / "aliases.yaml"
    path.write_text("first: &a [one]\nsecond: *a\n", encoding="utf-8")
    assert cm.load_model(path) == {"first": ["one"], "second": ["one"]}
    model["cycle"] = model
    invalid(model, "cyclic")


def test_minimal_example_is_valid():
    assert cm.validate(cm.load_model(SKILL / "examples" / "content-model" / "minimal.content.yaml")) == []


def test_real_ice_sample_and_generated_workbench_are_current():
    folder = ROOT / "skills" / "split-doc-layers" / "examples" / "content-model" / "ice"
    model = cm.load_model(folder / "ice.content.yaml")
    assert cm.validate(model) == []
    # Verifies the human view actually derives from YAML, not gameplay truth or engine roundtrip.
    spec = importlib.util.spec_from_file_location("ice_workbench_renderer", folder / "render_workbench.py")
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    assert renderer.render(model) == (folder / "ice.workbench.md").read_text(encoding="utf-8")


def test_real_sample_cannot_publish_its_discussions():
    model = cm.load_model(ROOT / "skills" / "split-doc-layers" / "examples" / "content-model" / "ice" / "ice.content.yaml")
    note_id = model["instances"][0]["discussion"][0]["fields"][0]["id"]
    projection = model["publication_ir"][0]
    projection["excluded"].remove(note_id)
    projection["fields"].append({"id": "out.accidental-note", "from": [note_id]})
    invalid(model, "non-publishable")
