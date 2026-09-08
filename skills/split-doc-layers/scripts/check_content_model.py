#!/usr/bin/env python3
"""Validate author-model/1 structure only. No engine IO, semantics or roundtrip.

Exit codes: 0 structurally valid, 1 invalid structure, 2 unreadable YAML/input.
Only PyYAML and the standard library are required.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import yaml


class ModelLoader(yaml.SafeLoader):
    """Reject duplicate mapping keys instead of silently losing author data."""


def _mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise ValueError("mapping keys must be strings")
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


ModelLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def _plain_tree(value, ancestors=None):
    """Fail cleanly on cyclic aliases, non-JSON YAML types and excessive depth."""
    ancestors = set() if ancestors is None else ancestors
    if isinstance(value, (dict, list)):
        if id(value) in ancestors:
            raise ValueError("cyclic YAML alias")
        ancestors.add(id(value))
        if isinstance(value, dict) and any(not isinstance(k, str) for k in value):
            raise ValueError("mapping keys must be strings")
        for child in (value.values() if isinstance(value, dict) else value):
            _plain_tree(child, ancestors)
        ancestors.remove(id(value))
    elif type(value) not in (str, int, float, bool, type(None)):
        raise ValueError("only JSON-compatible YAML values are supported; quote dates")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite numbers are not supported")


def load_model(path: Path):
    data = yaml.load(path.read_text(encoding="utf-8-sig"), Loader=ModelLoader)
    _plain_tree(data)
    return data


def validate(model) -> list[str]:
    """Return path-qualified structural errors without opening referenced sources."""
    errors = []
    ids = {}
    references = []
    instance_fields = {}
    eligible = set()
    branch_owners = {}

    def error(path, message):
        errors.append(f"{path}: {message}")

    def shape(obj, path, required, optional=()):
        if not isinstance(obj, dict):
            error(path, "expected mapping")
            return False
        for key in sorted(set(required) - obj.keys()):
            error(path, f"missing {key}")
        for key in sorted(obj.keys() - set(required) - set(optional)):
            error(path, f"unknown key {key}; domain data must use classified fields")
        return True

    def string(value, path):
        if not isinstance(value, str) or not value.strip():
            error(path, "expected non-empty string")
            return False
        return True

    def sequence(value, path):
        if not isinstance(value, list):
            error(path, "expected list")
            return []
        return value

    def identifier(obj, kind, path):
        value = obj.get("id")
        if not string(value, path + ".id"):
            return None
        if value in ids:
            error(path + ".id", f"duplicate id {value}")
        else:
            ids[value] = kind
        return value

    def ref(value, kinds, path):
        if string(value, path):
            references.append((value, kinds, path))

    def unique_strings(value, path):
        values = sequence(value, path)
        found = set()
        for i, item in enumerate(values):
            if string(item, f"{path}[{i}]"):
                if item in found:
                    error(path, f"duplicate entry {item}")
                found.add(item)
        return found

    def field_list(value, path, instance=None, publishable=False):
        for i, field in enumerate(sequence(value, path)):
            fp = f"{path}[{i}]"
            if not shape(field, fp, ("id", "classification", "kind", "value", "sources", "effective"), ("owner",)):
                continue
            fid = identifier(field, "field", fp)
            classification = field.get("classification")
            if classification not in ("declarative", "interpretive"):
                error(fp + ".classification", "expected declarative or interpretive")
            if classification == "interpretive":
                if field.get("owner") not in ("Framework", "Interface", "C"):
                    error(fp + ".owner", "interpretive field needs Framework, Interface or C owner")
            elif "owner" in field:
                error(fp + ".owner", "owner is reserved for interpretive fields")
            source_ids = unique_strings(field.get("sources"), fp + ".sources")
            if not source_ids:
                error(fp + ".sources", "every field value needs a source")
            for sid in sorted(source_ids):
                ref(sid, {"source"}, fp + ".sources")
            string(field.get("effective"), fp + ".effective")
            kind = field.get("kind")
            kinds = {"relation": {"instance", "catalog"}, "mechanism_refs": {"mechanism"}, "branch_refs": {"branch"}}
            if kind == "value":
                v = field.get("value")
                scalars = v if isinstance(v, list) else [v]
                if any(type(s) not in (str, int, float, bool) for s in scalars):
                    error(fp + ".value", "expected scalar or flat scalar list; split structured domain fields")
            elif isinstance(kind, str) and kind in kinds:
                targets = unique_strings(field.get("value"), fp + ".value")
                if not targets:
                    error(fp + ".value", "reference field must not be empty")
                for target in sorted(targets):
                    ref(target, kinds[kind], fp + ".value")
            else:
                error(fp + ".kind", "expected value, relation, mechanism_refs or branch_refs")
            if fid:
                if instance:
                    instance_fields.setdefault(instance, set()).add(fid)
                if publishable and classification == "declarative":
                    eligible.add(fid)

    try:
        _plain_tree(model)
    except (ValueError, RecursionError) as exc:
        return [f"$: invalid YAML tree: {exc}"]
    if not shape(model, "$", ("schema_version", "sources", "catalogs", "mechanisms", "instances", "publication_ir")):
        return errors
    if model.get("schema_version") != "author-model/1":
        error("$.schema_version", "expected author-model/1")

    for i, source in enumerate(sequence(model.get("sources"), "$.sources")):
        p = f"$.sources[{i}]"
        if shape(source, p, ("id", "locator", "version")):
            identifier(source, "source", p)
            string(source.get("locator"), p + ".locator")
            string(source.get("version"), p + ".version")

    for group, kind in (("catalogs", "catalog"), ("mechanisms", "mechanism")):
        for i, item in enumerate(sequence(model.get(group), "$." + group)):
            p = f"$.{group}[{i}]"
            required = ("id", "fields", "status") if kind == "mechanism" else ("id", "fields")
            if shape(item, p, required):
                identifier(item, kind, p)
                if kind == "mechanism" and item.get("status") not in ("indexed", "gap"):
                    error(p + ".status", "expected indexed or gap (neither proves contract completeness)")
                field_list(item.get("fields"), p + ".fields")

    instances = sequence(model.get("instances"), "$.instances")
    if not instances:
        error("$.instances", "at least one instance is required")
    discussions = []
    for i, instance in enumerate(instances):
        p = f"$.instances[{i}]"
        if not shape(instance, p, ("id", "version", "identity", "adopted", "release", "discussion")):
            continue
        iid = identifier(instance, "instance", p)
        string(instance.get("version"), p + ".version")
        if iid:
            instance_fields.setdefault(iid, set())
        for group in ("identity", "release"):
            field_list(instance.get(group), p + "." + group, iid, True)
        adopted = instance.get("adopted")
        if shape(adopted, p + ".adopted", ("fields", "branches")):
            field_list(adopted.get("fields"), p + ".adopted.fields", iid, True)
            for j, branch in enumerate(sequence(adopted.get("branches"), p + ".adopted.branches")):
                bp = f"{p}.adopted.branches[{j}]"
                if shape(branch, bp, ("id", "fields")):
                    bid = identifier(branch, "branch", bp)
                    if bid:
                        branch_owners[bid] = iid
                    field_list(branch.get("fields"), bp + ".fields", iid, True)
        for j, discussion in enumerate(sequence(instance.get("discussion"), p + ".discussion")):
            dp = f"{p}.discussion[{j}]"
            if shape(discussion, dp, ("id", "target", "target_version", "fields")):
                identifier(discussion, "discussion", dp)
                ref(discussion.get("target"), {"instance", "branch"}, dp + ".target")
                string(discussion.get("target_version"), dp + ".target_version")
                discussions.append((discussion.get("target"), iid, dp))
                field_list(discussion.get("fields"), dp + ".fields", iid)

    projected_instances = set()
    for i, projection in enumerate(sequence(model.get("publication_ir"), "$.publication_ir")):
        p = f"$.publication_ir[{i}]"
        if not shape(projection, p, ("id", "instance_id", "fields", "excluded")):
            continue
        identifier(projection, "projection", p)
        iid = projection.get("instance_id")
        ref(iid, {"instance"}, p + ".instance_id")
        if not isinstance(iid, str):
            continue
        projected_instances.add(iid)
        author_fields = instance_fields.get(iid, set())
        included = set()
        for j, target in enumerate(sequence(projection.get("fields"), p + ".fields")):
            tp = f"{p}.fields[{j}]"
            if shape(target, tp, ("id", "from")):
                identifier(target, "ir_field", tp)
                origin = unique_strings(target.get("from"), tp + ".from")
                if not origin:
                    error(tp + ".from", "IR field needs author field origins")
                for fid in sorted(origin):
                    if fid not in author_fields:
                        error(tp + ".from", f"unknown author field for this instance: {fid}")
                    elif fid not in eligible:
                        error(tp + ".from", f"non-publishable interpretation/discussion: {fid}")
                included.update(origin)
        excluded = unique_strings(projection.get("excluded"), p + ".excluded")
        if included & excluded:
            error(p, "IR included and excluded fields overlap")
        if included | excluded != author_fields:
            error(p, "IR included/excluded must partition all author fields of this instance")

    for iid in instance_fields:
        if iid not in projected_instances:
            error("$.publication_ir", f"missing field-set declaration for instance {iid}")
    for target, iid, path in discussions:
        if isinstance(target, str) and target in ids and target != iid and branch_owners.get(target) != iid:
            error(path + ".target", "discussion target must belong to containing instance")
    for target, kinds, path in references:
        if target not in ids:
            error(path, f"unresolved reference {target}")
        elif ids[target] not in kinds:
            error(path, f"reference {target} has kind {ids[target]}, expected {'/'.join(sorted(kinds))}")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path)
    args = parser.parse_args(argv)
    try:
        model = load_model(args.model)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError, RecursionError) as exc:
        print(json.dumps({"status": "unreadable", "scope": "structure-only", "errors": [str(exc)]}, ensure_ascii=False))
        return 2
    errors = validate(model)
    print(json.dumps({"status": "invalid" if errors else "ok", "scope": "structure-only", "errors": errors}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
