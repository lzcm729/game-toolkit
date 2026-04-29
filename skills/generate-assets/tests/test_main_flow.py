"""端到端测试：mock subprocess，验证 batch JSON 构造 + image-gen 调用 + 退码。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import generate_assets as ga


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _minimal_config(extra_categories: dict | None = None) -> dict:
    cats = {
        "ingredients": {
            "aspect_ratio": "1:1",
            "data_source": {
                "type": "inline",
                "items": {
                    "pearl": {"visual": "black pearls", "main": "#1e1b4b"},
                    "taro": {"visual": "taro chunks", "main": "#4a1942"},
                },
            },
            "prompt_template": "Icon '{id}': {visual}. Main {main}.",
        },
    }
    if extra_categories:
        cats.update(extra_categories)
    return {
        "$schema_version": 1,
        "style": {
            "prompt_prefix": "Cute chibi, transparent bg.",
            "prompt_suffix": "Warm caramel palette.",
        },
        "output_root": "art",
        "categories": cats,
    }


# -------------------- list 命令 --------------------

def test_list_command(tmp_project, capsys):
    cfg_path = tmp_project / "asset-config.yaml"
    _write_yaml(cfg_path, _minimal_config())
    rc = ga.main(["list", "--config", str(cfg_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "1 categories" in out
    assert "ingredients" in out


def test_list_default_when_no_command(tmp_project, capsys, monkeypatch):
    cfg_path = tmp_project / "asset-config.yaml"
    _write_yaml(cfg_path, _minimal_config())
    monkeypatch.chdir(tmp_project)
    rc = ga.main([])
    assert rc == 0
    assert "categories" in capsys.readouterr().out


# -------------------- 单 category dry-run --------------------

def test_single_category_dry_run(tmp_project, mock_subprocess_run, capsys):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg_path = tmp_project / "asset-config.yaml"
    _write_yaml(cfg_path, _minimal_config())

    rc = ga.main(["ingredients", "--config", str(cfg_path), "--dry-run"])
    assert rc == 0
    assert len(calls) == 1
    cmd = calls[0]["cmd"]
    assert "--dry-run" in cmd
    assert "--output-dir" in cmd

    # 检查传给 image-gen 的 batch JSON
    batch_path = Path(cmd[2])  # cmd: [py, gen_image_script, batch_json, ...]
    assert batch_path.exists()
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    assert batch["$schema_version"] == 2
    assert batch["defaults"]["aspect_ratio"] == "1:1"
    assert len(batch["assets"]) == 2
    assert {a["name"] for a in batch["assets"]} == {"pearl", "taro"}

    # 检查 prompt 拼接
    pearl_asset = next(a for a in batch["assets"] if a["name"] == "pearl")
    assert "Cute chibi" in pearl_asset["prompt"]
    assert "black pearls" in pearl_asset["prompt"]
    assert "Warm caramel" in pearl_asset["prompt"]


def test_force_flag_passed(tmp_project, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    ga.main(["ingredients", "--config", str(cfg), "--force"])
    assert "--force" in calls[0]["cmd"]


# -------------------- all 命令 --------------------

def test_all_runs_each_category(tmp_project, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config({
        "buildings": {
            "aspect_ratio": "1:1",
            "data_source": {"type": "inline", "items": {"shop": {"visual": "shop"}}},
            "prompt_template": "Building {id}: {visual}",
        },
    }))
    rc = ga.main(["all", "--config", str(cfg), "--dry-run"])
    assert rc == 0
    assert len(calls) == 2


# -------------------- name filter --------------------

def test_name_filter(tmp_project, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    ga.main(["ingredients", "--config", str(cfg), "--names", "pearl", "--dry-run"])
    batch_path = Path(calls[0]["cmd"][2])
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    assert [a["name"] for a in batch["assets"]] == ["pearl"]


def test_name_filter_no_match_skips(tmp_project, mock_subprocess_run, capsys):
    calls, set_result = mock_subprocess_run
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    rc = ga.main(["ingredients", "--config", str(cfg), "--names", "nonexistent"])
    assert rc == 0
    assert len(calls) == 0  # 没东西可生成 → 不调 image-gen


# -------------------- skip_global_style --------------------

def test_skip_global_style(tmp_project, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config({
        "backgrounds": {
            "aspect_ratio": "9:16",
            "skip_global_style": True,
            "data_source": {
                "type": "inline",
                "items": {"bg1": {"prompt_full": "FULL_INDEPENDENT_PROMPT"}},
            },
            "prompt_template": "{prompt_full}",
        },
    }))
    ga.main(["backgrounds", "--config", str(cfg), "--dry-run"])
    batch_path = Path(calls[0]["cmd"][2])
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    prompt = batch["assets"][0]["prompt"]
    assert prompt == "FULL_INDEPENDENT_PROMPT"
    assert "Cute chibi" not in prompt


# -------------------- derived_fields 端到端 --------------------

def test_derived_fields_in_prompt(tmp_project, write_json, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    write_json("recipes.json", [
        {"id": "cup1", "label": "Pearl Cup", "color": "#a0522d", "toppings": ["pearl"]},
        {"id": "cup2", "label": "Taro Cup", "color": "#9333ea", "toppings": ["taro"]},
    ])
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config({
        "recipes": {
            "aspect_ratio": "4:5",
            "data_source": {
                "type": "json_list",
                "path": "recipes.json",
                "filter": {"toppings_len": 1},
            },
            "derived_fields": {"toppings_str": 'join(toppings, ", ")'},
            "prompt_template": "Cup '{label}' contains {toppings_str}",
        },
    }))
    ga.main(["recipes", "--config", str(cfg), "--dry-run"])
    batch_path = Path(calls[0]["cmd"][2])
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    cup1 = next(a for a in batch["assets"] if a["name"] == "cup1")
    assert "contains pearl" in cup1["prompt"]


# -------------------- extra_fields 注入 --------------------

def test_extra_fields_injected(tmp_project, write_json, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    write_json("enemies.json", {
        "student": {"label": "学生", "color": "#fff"},
    })
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config({
        "customers": {
            "aspect_ratio": "2:3",
            "data_source": {"type": "json_dict", "path": "enemies.json"},
            "extra_fields": {
                "visual": {"student": "young student with backpack"},
            },
            "prompt_template": "Customer {label}: {visual}",
        },
    }))
    ga.main(["customers", "--config", str(cfg), "--dry-run"])
    batch_path = Path(calls[0]["cmd"][2])
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    asset = batch["assets"][0]
    assert "young student with backpack" in asset["prompt"]


# -------------------- 退码透传 --------------------

def test_exit_code_propagation(tmp_project, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=2)
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    rc = ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    assert rc == 2


def test_exit_code_max_across_categories(tmp_project, monkeypatch, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config({
        "second": {
            "aspect_ratio": "1:1",
            "data_source": {"type": "inline", "items": {"x": {"v": "x"}}},
            "prompt_template": "{id}: {v}",
        },
    }))

    # 给两次 subprocess.run 不同退码：第 1 次 0，第 2 次 1 → 总和 1
    return_codes = iter([0, 1])

    class FakeProc:
        def __init__(self, args, returncode):
            self.args = args
            self.returncode = returncode
            self.stdout = '{"total": 1, "success": 0, "failed": 1, "skipped": 0}\n'
            self.stderr = ""

    def fake_run(cmd, *a, **kw):
        calls.append({"cmd": list(cmd), "args": a, "kwargs": kw})
        return FakeProc(cmd, next(return_codes))

    monkeypatch.setattr(ga.subprocess, "run", fake_run)

    rc = ga.main(["all", "--config", str(cfg), "--dry-run"])
    assert rc == 1
    assert len(calls) == 2


# -------------------- 错误 case --------------------

def test_unknown_category(tmp_project, capsys):
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    rc = ga.main(["nonexistent", "--config", str(cfg)])
    assert rc == 1
    assert "未知 category" in capsys.readouterr().err


def test_config_missing(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = ga.main(["list"])
    assert rc == 1
    assert "找不到 asset-config.yaml" in capsys.readouterr().err


def test_data_source_load_error_exit_1(tmp_project, capsys, mock_subprocess_run):
    calls, _ = mock_subprocess_run
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config({
        "broken": {
            "aspect_ratio": "1:1",
            "data_source": {"type": "json_dict", "path": "nope.json"},
            "prompt_template": "{id}",
        },
    }))
    rc = ga.main(["broken", "--config", str(cfg)])
    assert rc == 1
    assert len(calls) == 0  # 没调 image-gen


def test_prompt_template_missing_field(tmp_project, capsys, mock_subprocess_run):
    calls, _ = mock_subprocess_run
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config({
        "broken": {
            "aspect_ratio": "1:1",
            "data_source": {"type": "inline", "items": {"x": {}}},
            "prompt_template": "{nonexistent_field}",
        },
    }))
    rc = ga.main(["broken", "--config", str(cfg)])
    assert rc == 1
    assert len(calls) == 0


# -------------------- output_root res:// 解析 --------------------

def test_output_root_res_prefix(tmp_project, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    config = _minimal_config()
    config["output_root"] = "res://generated"
    _write_yaml(cfg, config)
    ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    out_dir = calls[0]["cmd"][calls[0]["cmd"].index("--output-dir") + 1]
    assert "generated" in out_dir
    # 不应保留 res:// 前缀
    assert "res://" not in out_dir


def test_output_subdir_default_to_category_name(tmp_project, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    out_dir = calls[0]["cmd"][calls[0]["cmd"].index("--output-dir") + 1]
    # 默认 subdir = "ingredients"
    assert out_dir.endswith("ingredients") or "ingredients" in Path(out_dir).name


def test_output_subdir_custom(tmp_project, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    config = _minimal_config()
    config["categories"]["ingredients"]["output_subdir"] = "custom_dir"
    _write_yaml(cfg, config)
    ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    out_dir = calls[0]["cmd"][calls[0]["cmd"].index("--output-dir") + 1]
    assert "custom_dir" in out_dir


# -------------------- defaults 透传 --------------------

def test_seed_passed_to_defaults(tmp_project, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    config = _minimal_config()
    config["categories"]["ingredients"]["seed"] = 42
    _write_yaml(cfg, config)
    ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    batch_path = Path(calls[0]["cmd"][2])
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    assert batch["defaults"]["seed"] == 42


def test_chain_passed_to_defaults(tmp_project, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    config = _minimal_config()
    config["categories"]["ingredients"]["chain"] = "laozhang_only"
    _write_yaml(cfg, config)
    ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    batch_path = Path(calls[0]["cmd"][2])
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    assert batch["defaults"]["chain"] == "laozhang_only"


# -------------------- summary 解析 --------------------

def test_extract_summary_from_stdout():
    stdout = "doing stuff\nmore stuff\n" + json.dumps({
        "total": 5, "success": 5, "failed": 0, "skipped": 0
    }) + "\n"
    summary = ga._extract_summary(stdout)
    assert summary == {"total": 5, "success": 5, "failed": 0, "skipped": 0}


def test_extract_summary_no_json():
    assert ga._extract_summary("just text\nno json here") is None


def test_extract_summary_handles_multiple_json_lines():
    """使用末尾那条。"""
    stdout = '{"early": "ignored"}\n{"final": true}\n'
    summary = ga._extract_summary(stdout)
    assert summary == {"final": True}


# -------------------- non-Godot warn --------------------

def test_non_godot_warn(tmp_path, capsys, mock_subprocess_run, monkeypatch):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    # tmp_path 没 project.godot
    cfg = tmp_path / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    monkeypatch.chdir(tmp_path)
    ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    err = capsys.readouterr().err
    assert "非 Godot 项目" in err or "没有 project.godot" in err


# -------------------- preset / extra_fields error --------------------

def test_extra_fields_must_be_dict(tmp_project, mock_subprocess_run, capsys):
    calls, _ = mock_subprocess_run
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config({
        "broken": {
            "aspect_ratio": "1:1",
            "data_source": {"type": "inline", "items": {"x": {}}},
            "extra_fields": {"visual": "not-a-dict"},
            "prompt_template": "{id}: {visual}",
        },
    }))
    rc = ga.main(["broken", "--config", str(cfg)])
    assert rc == 1
