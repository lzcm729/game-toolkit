"""端到端测试：mock subprocess，验证 batch JSON 构造 + image-gen 调用 + 退码。"""
from __future__ import annotations

import dataclasses
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

def test_non_godot_falls_back_to_generic_engine(tmp_path, capsys, mock_subprocess_run, monkeypatch):
    """没有已支持的引擎工程文件时退到 generic，并说明这意味着什么。"""
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_path / "asset-config.yaml"          # tmp_path 没 project.godot
    _write_yaml(cfg, _minimal_config())
    monkeypatch.chdir(tmp_path)
    ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    err = capsys.readouterr().err
    assert "adapter=generic" in err


def test_explicit_engine_generic_skips_detection(tmp_project, capsys, mock_subprocess_run):
    """显式声明 engine 后不再探测 —— 即使目录里有 project.godot。"""
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    config = _minimal_config()
    config["engine"] = "generic"
    config["output_root"] = "res://art"      # generic 不认 res://：被拒 = 声明生效
    _write_yaml(cfg, config)
    assert ga.main(["ingredients", "--config", str(cfg), "--dry-run"]) == 1
    assert "res://" in capsys.readouterr().err
    assert calls == []


def test_generic_engine_rejects_res_prefix(tmp_path, mock_subprocess_run, monkeypatch, capsys):
    """generic 模式撞见 res:// 要报错，不能硬拼成 <root>/res:/art。"""
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_path / "asset-config.yaml"
    config = _minimal_config()
    config["engine"] = "generic"
    config["output_root"] = "res://art"
    _write_yaml(cfg, config)
    monkeypatch.chdir(tmp_path)
    assert ga.main(["ingredients", "--config", str(cfg), "--dry-run"]) == 1
    assert "res://" in capsys.readouterr().err


def test_unknown_adapter_rejected(tmp_path, mock_subprocess_run, monkeypatch, capsys):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_path / "asset-config.yaml"
    config = _minimal_config()
    config["adapter"] = "unity"
    _write_yaml(cfg, config)
    monkeypatch.chdir(tmp_path)
    assert ga.main(["ingredients", "--config", str(cfg), "--dry-run"]) == 1
    assert "未知的 adapter" in capsys.readouterr().err


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

# -------------------- reference_paths 的 res:// 解析 --------------------

def _batch_of(calls):
    return json.loads(Path(calls[0]["cmd"][2]).read_text(encoding="utf-8"))


def test_global_reference_res_path_resolves_from_project_root(tmp_project, mock_subprocess_run):
    """res:// 等价于项目根，不是 output_root —— 否则会拼出 art/art/。"""
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    config = _minimal_config()
    config["style"]["reference_paths"] = ["res://art/_style/anchor.png"]
    _write_yaml(cfg, config)
    ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    resolved = Path(_batch_of(calls)["defaults"]["reference_paths"][0])
    assert resolved == (tmp_project / "art" / "_style" / "anchor.png").resolve()


def test_category_reference_res_path_resolves_from_project_root(tmp_project, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    config = _minimal_config()
    config["categories"]["ingredients"]["reference_paths"] = ["res://art/_style/cat.png"]
    _write_yaml(cfg, config)
    ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    resolved = Path(_batch_of(calls)["defaults"]["reference_paths"][0])
    assert resolved == (tmp_project / "art" / "_style" / "cat.png").resolve()


# -------------------- 全局 style.chain --------------------

def test_global_style_chain_passed_to_defaults(tmp_project, mock_subprocess_run):
    """examples/README 承诺 style.chain 透传到 defaults.chain。"""
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    config = _minimal_config()
    config["style"]["chain"] = "default"
    _write_yaml(cfg, config)
    ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    assert _batch_of(calls)["defaults"]["chain"] == "default"


def test_category_chain_overrides_global_chain(tmp_project, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    config = _minimal_config()
    config["style"]["chain"] = "default"
    config["categories"]["ingredients"]["chain"] = "laozhang_only"
    _write_yaml(cfg, config)
    ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    assert _batch_of(calls)["defaults"]["chain"] == "laozhang_only"


def test_skip_global_style_also_skips_global_chain(tmp_project, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    config = _minimal_config()
    config["style"]["chain"] = "default"
    config["categories"]["ingredients"]["skip_global_style"] = True
    _write_yaml(cfg, config)
    ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    assert "chain" not in _batch_of(calls)["defaults"]

# -------------------- 裸相对路径 vs res:// 的基准不同 --------------------

def test_bare_relative_reference_resolves_from_output_root(tmp_project, mock_subprocess_run):
    """examples/README.md 约定：裸相对路径相对 output_root，只有 res:// 才相对项目根。

    回归防护：修 res:// 时若把两者共用一个 root，这条就会挂。
    """
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    config = _minimal_config()
    config["style"]["reference_paths"] = ["_style/anchor.png"]
    _write_yaml(cfg, config)
    ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    resolved = Path(_batch_of(calls)["defaults"]["reference_paths"][0])
    assert resolved == (tmp_project / "art" / "_style" / "anchor.png").resolve()


def test_absolute_reference_passes_through(tmp_project, mock_subprocess_run):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    config = _minimal_config()
    abs_ref = (tmp_project / "elsewhere" / "ref.png").resolve()
    config["style"]["reference_paths"] = [str(abs_ref)]
    _write_yaml(cfg, config)
    ga.main(["ingredients", "--config", str(cfg), "--dry-run"])
    assert Path(_batch_of(calls)["defaults"]["reference_paths"][0]) == abs_ref


# -------------------- .import 提示的触发条件 --------------------

def test_import_hint_shown_when_all_skipped(tmp_project, mock_subprocess_run, capsys):
    """全部 skipped 时 success=0，但已存在的 PNG 同样可能还没被 Godot 导入。"""
    calls, set_result = mock_subprocess_run
    set_result(returncode=0, summary={"total": 2, "success": 0, "failed": 0, "skipped": 2,
                                      "failed_assets": [], "manifest": "/tmp/m.jsonl"})
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    ga.main(["ingredients", "--config", str(cfg)])
    assert "godot" in capsys.readouterr().out.lower()


def test_no_import_hint_when_nothing_produced(tmp_project, mock_subprocess_run, capsys):
    calls, set_result = mock_subprocess_run
    set_result(returncode=1, summary={"total": 2, "success": 0, "failed": 2, "skipped": 0,
                                      "failed_assets": [], "manifest": "/tmp/m.jsonl"})
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    ga.main(["ingredients", "--config", str(cfg)])
    assert "godot" not in capsys.readouterr().out.lower()

def test_unregistered_engine_prefix_does_not_suggest_unknown_engine():
    """认出前缀属于哪个引擎 != 支持那个引擎。

    回归防护：曾经 /Game/ 的报错建议「把 engine 设成 unreal」，
    照做会撞进「未知的 engine: 'unreal'」—— 把人指进一个死循环。
    """
    import engine_adapter as ea
    with pytest.raises(ValueError) as ex:
        ea.GENERIC.resolve_path("/Game/Art/a.uasset", Path("C:/p"))
    msg = str(ex.value)
    assert "没有 unreal 适配" in msg
    assert "adapter 改成 unreal" not in msg


def test_registered_engine_prefix_does_suggest_switching():
    import engine_adapter as ea
    with pytest.raises(ValueError) as ex:
        ea.GENERIC.resolve_path("res://art/a.png", Path("C:/p"))
    assert "adapter 改成 godot" in str(ex.value)


# -------------------- adapter vs engine：两个词不是一回事 --------------------

def test_adapter_field_preferred_over_legacy_engine(tmp_project, mock_subprocess_run, capsys):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    config = _minimal_config()
    config["adapter"] = "generic"
    config["output_root"] = "res://art"      # 同上
    _write_yaml(cfg, config)
    assert ga.main(["ingredients", "--config", str(cfg), "--dry-run"]) == 1
    assert "res://" in capsys.readouterr().err
    assert calls == []


def test_adapter_and_engine_conflict_is_an_error(tmp_project, mock_subprocess_run, capsys):
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    cfg = tmp_project / "asset-config.yaml"
    config = _minimal_config()
    config["adapter"], config["engine"] = "generic", "godot"
    _write_yaml(cfg, config)
    assert ga.main(["ingredients", "--config", str(cfg), "--dry-run"]) == 1
    assert "engine 是 adapter 的旧名" in capsys.readouterr().err


def test_explicit_project_root_wins(tmp_project, tmp_path, mock_subprocess_run):
    """config 挪位置不该改变相对路径的基准 —— 显式给根就固定下来。"""
    calls, set_result = mock_subprocess_run
    set_result(returncode=0)
    sub = tmp_project / "tools"
    sub.mkdir()
    cfg = sub / "asset-config.yaml"
    config = _minimal_config()
    config["style"]["reference_paths"] = ["_style/anchor.png"]
    _write_yaml(cfg, config)
    ga.main(["ingredients", "--config", str(cfg), "--project-root", str(tmp_project), "--dry-run"])
    resolved = Path(_batch_of(calls)["defaults"]["reference_paths"][0])
    assert resolved == (tmp_project / "art" / "_style" / "anchor.png").resolve()


# -------------------- 新用户的三道坎（3.4.3） --------------------

def _generic_res_config(tmp_path: Path) -> Path:
    """没有 project.godot 的目录 + res:// 路径 —— 插件自带示例在陌生目录跑就是这个组合。"""
    cfg = _minimal_config()
    cfg["output_root"] = "res://art"
    cfg["adapter"] = "generic"
    cfg.pop("engine", None)
    p = tmp_path / "asset-config.yaml"
    _write_yaml(p, cfg)
    return p


def test_res_prefix_under_generic_is_a_clean_fatal(tmp_path, capsys):
    """曾经是一整屏 traceback，把「改 adapter 或换相对路径」那句话埋在栈帧下面。"""
    p = _generic_res_config(tmp_path)
    rc = ga.main(["--config", str(p), "ingredients", "--dry-run"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "[fatal]" in err and "res://" in err
    assert "Traceback" not in err


def test_list_only_needs_config(tmp_path, capsys):
    """list 不该被路径解析拦住 —— 看一眼有哪些 category 不需要工程根。"""
    p = _generic_res_config(tmp_path)
    assert ga.main(["--config", str(p), "list"]) == 0
    assert "ingredients" in capsys.readouterr().out


def test_missing_backend_fails_fast_with_directions(
    tmp_project, capsys, mock_subprocess_run, monkeypatch
):
    calls, _ = mock_subprocess_run
    monkeypatch.setenv("IMAGE_GEN_SCRIPT", str(tmp_project / "nope" / "generate_image.py"))
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    rc = ga.main(["--config", str(cfg), "ingredients", "--dry-run"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "IMAGE_GEN_SCRIPT" in err
    assert calls == []          # 一个 category 都没开始跑


def test_missing_backend_at_default_location_is_also_reported(
    tmp_project, capsys, mock_subprocess_run, monkeypatch
):
    """以前只有走环境变量才有提示，默认路径不存在时一声不吭。"""
    calls, _ = mock_subprocess_run
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    monkeypatch.setattr(
        ga.image_backend, "IMAGE_GEN",
        dataclasses.replace(ga.image_backend.IMAGE_GEN, resolve_script=lambda: None),
    )
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    assert ga.main(["--config", str(cfg), "ingredients", "--dry-run"]) == 1
    err = capsys.readouterr().err
    assert "image-gen" in err
    assert calls == []


def test_unknown_backend_name_is_fatal(
    tmp_project, capsys, mock_subprocess_run, monkeypatch
):
    """config 写了不存在的 backend → 退 1 并列出可选项。"""
    _, _ = mock_subprocess_run
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    conf["backend"] = "midjourney"
    _write_yaml(cfg, conf)
    assert ga.main(["--config", str(cfg), "ingredients", "--dry-run"]) == 1
    err = capsys.readouterr().err
    assert "midjourney" in err and "laozhang" in err


def test_list_does_not_need_image_gen(tmp_project, capsys, monkeypatch):
    monkeypatch.setenv("IMAGE_GEN_SCRIPT", str(tmp_project / "nope.py"))
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    assert ga.main(["--config", str(cfg), "list"]) == 0


# -------------------- codex 实跑找出的（3.4.3） --------------------

def test_broken_yaml_is_a_clean_fatal(tmp_path, capsys):
    p = tmp_path / "asset-config.yaml"
    p.write_text("categories: [\n", encoding="utf-8")
    assert ga.main(["--config", str(p), "list"]) == 1
    err = capsys.readouterr().err
    assert "[fatal]" in err and "解析失败" in err


def test_non_string_output_root_is_a_clean_fatal(tmp_project, capsys, mock_subprocess_run):
    cfg = _minimal_config()
    cfg["output_root"] = ["art"]
    p = tmp_project / "asset-config.yaml"
    _write_yaml(p, cfg)
    assert ga.main(["--config", str(p), "ingredients", "--dry-run"]) == 1
    assert "output_root" in capsys.readouterr().err


def test_output_dir_blocked_by_a_file_is_a_category_error(tmp_project, capsys, mock_subprocess_run):
    calls, _ = mock_subprocess_run
    p = tmp_project / "asset-config.yaml"
    _write_yaml(p, _minimal_config())
    (tmp_project / "art").mkdir()
    (tmp_project / "art" / "ingredients").write_text("in the way", encoding="utf-8")
    assert ga.main(["--config", str(p), "ingredients", "--dry-run"]) == 1
    assert "输出目录建不了" in capsys.readouterr().err
    assert calls == []


def test_no_summary_on_a_real_run_is_a_failure(tmp_project, capsys, mock_subprocess_run, monkeypatch):
    """只有注释的上游脚本退出 0、什么都不打 —— 曾被报成成功，图一张没有。"""
    monkeypatch.setattr(ga, "_invoke_backend", lambda cmd, **kw: (None, 0, None))
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    assert ga.main(["--config", str(cfg), "ingredients"]) == 1
    assert "没有返回 summary" in capsys.readouterr().err


def test_no_summary_on_dry_run_is_fine(tmp_project, capsys, mock_subprocess_run, monkeypatch):
    """上游 dry-run 本来就只打计划、不吐 summary，不能当失败。"""
    monkeypatch.setattr(ga, "_invoke_backend", lambda cmd, **kw: (None, 0, None))
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    assert ga.main(["--config", str(cfg), "ingredients", "--dry-run"]) == 0


def test_dry_run_prints_rendered_prompts(tmp_project, capsys, mock_subprocess_run):
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())
    assert ga.main(["--config", str(cfg), "ingredients", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "[prompt]" in out and "black pearls" in out


def test_generic_hint_is_silent_when_adapter_is_declared(tmp_path, capsys, mock_subprocess_run):
    cfg = _minimal_config()
    cfg["adapter"] = "generic"
    cfg.pop("engine", None)
    p = tmp_path / "asset-config.yaml"
    _write_yaml(p, cfg)
    assert ga.main(["--config", str(p), "ingredients", "--dry-run"]) == 0
    assert "[info] adapter=generic" not in capsys.readouterr().err


def test_generic_hint_shows_when_auto_detected(tmp_path, capsys, mock_subprocess_run):
    cfg = _minimal_config()
    cfg.pop("adapter", None)
    cfg.pop("engine", None)
    p = tmp_path / "asset-config.yaml"
    _write_yaml(p, cfg)
    assert ga.main(["--config", str(p), "ingredients", "--dry-run"]) == 0
    assert "[info] adapter=generic" in capsys.readouterr().err


# -------------------- codex 第二轮（3.4.4） --------------------

def test_categories_list_is_a_clean_fatal(tmp_path, capsys):
    p = tmp_path / "asset-config.yaml"
    p.write_text("output_root: art\nadapter: generic\ncategories:\n  - icons\n", encoding="utf-8")
    assert ga.main(["--config", str(p), "list"]) == 1
    assert "categories 应为映射" in capsys.readouterr().err
    assert ga.main(["--config", str(p), "icons", "--dry-run"]) == 1


def test_null_category_spec_is_a_clean_fatal(tmp_path, capsys, mock_subprocess_run):
    cfg = _minimal_config()
    cfg["adapter"] = "generic"
    cfg.pop("engine", None)
    cfg["categories"]["broken"] = None
    p = tmp_path / "asset-config.yaml"
    _write_yaml(p, cfg)
    assert ga.main(["--config", str(p), "list"]) == 1
    assert "broken" in capsys.readouterr().err


def test_empty_categories_still_lists_nothing_without_error(tmp_path, capsys):
    p = tmp_path / "asset-config.yaml"
    p.write_text("output_root: art\nadapter: generic\ncategories: {}\n", encoding="utf-8")
    assert ga.main(["--config", str(p), "list"]) == 0
    assert "empty config" in capsys.readouterr().out


def test_printed_command_quotes_paths_with_spaces(tmp_path, capsys, mock_subprocess_run):
    """路径带空格时打印的 $ 命令行要能直接复制执行。"""
    root = tmp_path / "with space"
    root.mkdir()
    cfg = _minimal_config()
    cfg["adapter"] = "generic"
    cfg.pop("engine", None)
    p = root / "asset-config.yaml"
    _write_yaml(p, cfg)
    assert ga.main(["--config", str(p), "ingredients", "--dry-run", "--project-root", str(root)]) == 0
    line = [l for l in capsys.readouterr().out.splitlines() if l.strip().startswith("$ ")][0]
    assert '"' in line or "'" in line


# -------------------- codex 第三轮（3.4.5） --------------------

def test_output_subdir_cannot_escape_output_root(tmp_project, capsys, mock_subprocess_run):
    """`../../escaped` 曾真的写到工程外；dry-run 都把 generate.log 写出去了。"""
    calls, _ = mock_subprocess_run
    cfg = _minimal_config()
    cfg["categories"]["ingredients"]["output_subdir"] = "../../escaped"
    p = tmp_project / "asset-config.yaml"
    _write_yaml(p, cfg)
    assert ga.main(["--config", str(p), "ingredients", "--dry-run"]) == 1
    assert "output_root 之外" in capsys.readouterr().err
    assert calls == []
    assert not (tmp_project.parent / "escaped").exists()


def test_absolute_output_subdir_is_rejected_too(tmp_project, capsys, mock_subprocess_run):
    cfg = _minimal_config()
    cfg["categories"]["ingredients"]["output_subdir"] = str(tmp_project.parent / "abs-escape")
    p = tmp_project / "asset-config.yaml"
    _write_yaml(p, cfg)
    assert ga.main(["--config", str(p), "ingredients", "--dry-run"]) == 1
    assert "output_root 之外" in capsys.readouterr().err


def test_nested_output_subdir_is_fine(tmp_project, mock_subprocess_run):
    cfg = _minimal_config()
    cfg["categories"]["ingredients"]["output_subdir"] = "icons/small"
    p = tmp_project / "asset-config.yaml"
    _write_yaml(p, cfg)
    assert ga.main(["--config", str(p), "ingredients", "--dry-run"]) == 0


def test_unsupported_field_warns_with_value(
    tmp_project, capsys, mock_subprocess_run, monkeypatch
):
    """laozhang 不认 chain：要告警、要点名 category、要带上被丢弃的值。"""
    _, _ = mock_subprocess_run
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    fake = tmp_project / "fake_backend.py"
    fake.write_text("# stub\n", encoding="utf-8")
    monkeypatch.setattr(
        ga.image_backend, "LAOZHANG",
        dataclasses.replace(ga.image_backend.LAOZHANG, resolve_script=lambda: fake),
    )
    # setitem 不是多余的：BACKENDS 在模块加载时就捕获了对象引用，换模块属性
    # 不会改字典里那个。走 backend: 具名分支时 select() 从字典取，两处都要换。
    monkeypatch.setitem(ga.image_backend.BACKENDS, "laozhang", ga.image_backend.LAOZHANG)

    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    conf["backend"] = "laozhang"
    conf["style"]["chain"] = "default"
    _write_yaml(cfg, conf)

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    err = capsys.readouterr().err
    assert "ingredients" in err          # 点名 category
    assert "chain" in err
    assert "default" in err              # 带上被丢弃的值
    assert "image-gen" in err            # 指出切回哪个后端才生效


def test_supported_field_does_not_warn(
    tmp_project, capsys, mock_subprocess_run, monkeypatch
):
    """image-gen 认 chain，不该有告警噪音。

    必须走真正的 IMAGE_GEN 条目：fixture 设的 IMAGE_GEN_SCRIPT 会让 select()
    返回 custom 后端，那条按全集处理、永远不告警 —— 测试就永远绿，连
    supports 里删掉 chain 都发现不了（变异验证过）。
    """
    _, _ = mock_subprocess_run
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    fake = tmp_project / "fake_ig.py"
    fake.write_text("# stub", encoding="utf-8")
    monkeypatch.setattr(
        ga.image_backend, "IMAGE_GEN",
        dataclasses.replace(ga.image_backend.IMAGE_GEN, resolve_script=lambda: fake),
    )
    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    conf["style"]["chain"] = "default"
    _write_yaml(cfg, conf)

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    assert "不支持 chain" not in capsys.readouterr().err


# -------------------- model 配置 --------------------
# 模型选择是 per-project / per-category 的决策，不该只能靠环境变量。
# 放顶层而不是 style 段：它是后端配置不是风格，放 style 里会被
# skip_global_style 连带关掉。


def test_top_level_model_lands_in_batch_defaults(
    tmp_project, mock_subprocess_run
):
    calls, _ = mock_subprocess_run
    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    conf["model"] = "gemini-3-pro-image"
    _write_yaml(cfg, conf)

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    batch = json.loads(Path(calls[0]["cmd"][2]).read_text(encoding="utf-8"))
    assert batch["defaults"]["model"] == "gemini-3-pro-image"


def test_category_model_overrides_top_level(tmp_project, mock_subprocess_run):
    calls, _ = mock_subprocess_run
    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    conf["model"] = "gemini-3.1-flash-image"
    conf["categories"]["ingredients"]["model"] = "gemini-3-pro-image"
    _write_yaml(cfg, conf)

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    batch = json.loads(Path(calls[0]["cmd"][2]).read_text(encoding="utf-8"))
    assert batch["defaults"]["model"] == "gemini-3-pro-image"


def test_no_model_declared_leaves_it_out(tmp_project, mock_subprocess_run):
    """没声明就不要往 defaults 里塞空值——后端自己有默认。"""
    calls, _ = mock_subprocess_run
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    batch = json.loads(Path(calls[0]["cmd"][2]).read_text(encoding="utf-8"))
    assert "model" not in batch["defaults"]


def test_model_not_killed_by_skip_global_style(tmp_project, mock_subprocess_run):
    """skip_global_style 关的是风格，不该连模型一起关掉。"""
    calls, _ = mock_subprocess_run
    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    conf["model"] = "gemini-3-pro-image"
    conf["categories"]["ingredients"]["skip_global_style"] = True
    _write_yaml(cfg, conf)

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    batch = json.loads(Path(calls[0]["cmd"][2]).read_text(encoding="utf-8"))
    assert batch["defaults"]["model"] == "gemini-3-pro-image"


def test_image_gen_backend_warns_on_model_and_points_at_chain(
    tmp_project, capsys, mock_subprocess_run, monkeypatch
):
    """image-gen 用 chain 表达模型选择，不认 model——告警得指对方向。"""
    _, _ = mock_subprocess_run
    # 必须走真正的 IMAGE_GEN 条目：fixture 设的 IMAGE_GEN_SCRIPT 会走
    # _custom()，那条按全集处理不告警（自定义后端能力未知，不该误报）。
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    fake = tmp_project / "fake_ig.py"
    fake.write_text("# stub", encoding="utf-8")
    monkeypatch.setattr(
        ga.image_backend, "IMAGE_GEN",
        dataclasses.replace(ga.image_backend.IMAGE_GEN, resolve_script=lambda: fake),
    )
    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    conf["model"] = "gemini-3-pro-image"
    _write_yaml(cfg, conf)

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    err = capsys.readouterr().err
    assert "不支持 model" in err
    assert "chain" in err                 # 指向正确的替代写法
    assert "切回 backend: image-gen" not in err   # 这句对 model 是反的


def test_laozhang_backend_does_not_warn_on_model(
    tmp_project, capsys, mock_subprocess_run, monkeypatch
):
    _, _ = mock_subprocess_run
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    fake = tmp_project / "fake_backend.py"
    fake.write_text("# stub\n", encoding="utf-8")
    monkeypatch.setattr(
        ga.image_backend, "LAOZHANG",
        dataclasses.replace(ga.image_backend.LAOZHANG, resolve_script=lambda: fake),
    )
    monkeypatch.setitem(ga.image_backend.BACKENDS, "laozhang", ga.image_backend.LAOZHANG)

    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    conf["backend"] = "laozhang"
    conf["model"] = "gpt-image-2.5-flare"
    _write_yaml(cfg, conf)

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    assert "不支持 model" not in capsys.readouterr().err


# -------------------- edit 模式（image 底图） --------------------
# 「基于一张底图批量生成变体」是真实需求：同一场景的四季版、同一角色的
# 不同状态。协议此前只有 reference_paths（风格参考），语义不同。
# image 只做 asset 级：image-gen 的 Defaults 不解析它，放 defaults 会被
# 静默丢掉，而 supports 告警只覆盖 defaults 字段——等于埋个无声的坑。


def test_category_image_expands_to_every_asset(tmp_project, mock_subprocess_run):
    calls, _ = mock_subprocess_run
    base = tmp_project / "art" / "base.png"
    base.parent.mkdir(parents=True, exist_ok=True)
    base.write_bytes(b"png")
    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    conf["categories"]["ingredients"]["image"] = "base.png"   # 相对 output_root
    _write_yaml(cfg, conf)

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    batch = json.loads(Path(calls[0]["cmd"][2]).read_text(encoding="utf-8"))
    assert "image" not in batch["defaults"]          # 不进 defaults
    assert len(batch["assets"]) == 2
    for a in batch["assets"]:
        assert Path(a["image"]) == base.resolve()


def test_item_image_overrides_category_image(tmp_project, mock_subprocess_run):
    calls, _ = mock_subprocess_run
    art = tmp_project / "art"
    art.mkdir(parents=True, exist_ok=True)
    (art / "base.png").write_bytes(b"png")
    (art / "pearl_base.png").write_bytes(b"png")
    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    cat = conf["categories"]["ingredients"]
    cat["image"] = "base.png"
    cat["data_source"]["items"]["pearl"]["image"] = "pearl_base.png"
    _write_yaml(cfg, conf)

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    batch = json.loads(Path(calls[0]["cmd"][2]).read_text(encoding="utf-8"))
    by_name = {a["name"]: a for a in batch["assets"]}
    assert Path(by_name["pearl"]["image"]).name == "pearl_base.png"
    assert Path(by_name["taro"]["image"]).name == "base.png"


def test_image_and_reference_paths_are_mutually_exclusive(
    tmp_project, capsys, mock_subprocess_run
):
    """两者语义不同且上游 provider 本就互斥，早点报比发到后端才炸好。"""
    calls, _ = mock_subprocess_run
    art = tmp_project / "art"
    art.mkdir(parents=True, exist_ok=True)
    (art / "base.png").write_bytes(b"png")
    (art / "anchor.png").write_bytes(b"png")
    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    conf["style"]["reference_paths"] = ["anchor.png"]
    conf["categories"]["ingredients"]["image"] = "base.png"
    _write_yaml(cfg, conf)

    assert ga.main(["--config", str(cfg), "ingredients"]) == 1
    err = capsys.readouterr().err
    assert "ingredients" in err
    assert "image" in err and "reference_paths" in err
    assert calls == []          # 没往后端发


def test_image_accepts_res_prefix(tmp_project, mock_subprocess_run):
    calls, _ = mock_subprocess_run
    base = tmp_project / "sprites" / "base.png"
    base.parent.mkdir(parents=True, exist_ok=True)
    base.write_bytes(b"png")
    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    conf["categories"]["ingredients"]["image"] = "res://sprites/base.png"
    _write_yaml(cfg, conf)

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    batch = json.loads(Path(calls[0]["cmd"][2]).read_text(encoding="utf-8"))
    assert Path(batch["assets"][0]["image"]) == base.resolve()


def test_no_image_declared_leaves_asset_clean(tmp_project, mock_subprocess_run):
    calls, _ = mock_subprocess_run
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    batch = json.loads(Path(calls[0]["cmd"][2]).read_text(encoding="utf-8"))
    assert all("image" not in a for a in batch["assets"])


# -------------------- codex 评审发现的缺陷 --------------------


def test_item_model_lands_on_asset(tmp_project, mock_subprocess_run):
    """文档承诺 item 级 model 优先级最高，构造层却漏了透传。"""
    calls, _ = mock_subprocess_run
    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    conf["model"] = "gemini-3.1-flash-image"
    conf["categories"]["ingredients"]["data_source"]["items"]["pearl"]["model"] = "gpt-image-2.5-flare"
    _write_yaml(cfg, conf)

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    batch = json.loads(Path(calls[0]["cmd"][2]).read_text(encoding="utf-8"))
    by_name = {a["name"]: a for a in batch["assets"]}
    assert by_name["pearl"]["model"] == "gpt-image-2.5-flare"   # item 覆盖
    assert "model" not in by_name["taro"]                        # 没声明就不塞
    assert batch["defaults"]["model"] == "gemini-3.1-flash-image"


def test_backend_runs_in_project_root(tmp_project, mock_subprocess_run):
    """后端靠 CWD 向上找 .env。不设 cwd 的话，找的是调用者的项目而非目标项目。"""
    calls, _ = mock_subprocess_run
    cfg = tmp_project / "asset-config.yaml"
    _write_yaml(cfg, _minimal_config())

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    assert Path(calls[0]["kwargs"]["cwd"]) == tmp_project.resolve()
