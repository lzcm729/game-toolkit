"""生成记录 —— 端到端，用一个真按协议干活的桩后端跑真子进程。

现有的 mock 后端不写文件，走不到「生成后更新记录」那条路径 —— 用它测
这个功能，测到的只是「什么都没发生」。所以这里换一个会写文件的：
每张图的内容就是它的 prompt，这样能直接断言「这张图是用哪个 prompt 生成的」。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

import asset_manifest
import generate_assets as ga

_STUB = r'''
import argparse, json, os, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("batch")
ap.add_argument("--output-dir", required=True)
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--force", action="store_true")
a = ap.parse_args()

batch = json.loads(Path(a.batch).read_text(encoding="utf-8"))
out = Path(a.output_dir)
fail = set(filter(None, os.environ.get("STUB_FAIL", "").split(",")))
ok = failed = skipped = 0
failed_assets = []
for asset in batch["assets"]:
    target = out / asset["filename"]
    if a.dry_run:
        print(f"  [plan] {asset['name']} -> {target}")
        continue
    if target.exists() and not a.force:
        print(f"  [skip] {asset['name']}")
        skipped += 1
        continue
    if asset["name"] in fail:
        failed += 1
        failed_assets.append({"name": asset["name"], "error": "stub fail"})
        continue
    target.write_text(asset["prompt"], encoding="utf-8")
    ok += 1
print(json.dumps({"total": len(batch["assets"]), "success": ok, "failed": failed,
                  "skipped": skipped, "failed_assets": failed_assets}))
'''


@pytest.fixture
def project(tmp_path, monkeypatch):
    """一个最小工程 + 真桩后端。返回 (工程根, 写配置的函数, 跑的函数)。"""
    stub = tmp_path / "_stub_backend.py"
    stub.write_text(_STUB, encoding="utf-8")
    monkeypatch.setenv("IMAGE_GEN_SCRIPT", str(stub))
    monkeypatch.delenv("STUB_FAIL", raising=False)

    (tmp_path / "items.json").write_text(
        json.dumps({"pearl": {"visual": "black pearls"}, "taro": {"visual": "taro chunks"}}),
        encoding="utf-8")
    cfg = tmp_path / "asset-config.yaml"

    def write(template="Icon of {visual}.", **extra):
        conf = {
            "$schema_version": 1, "adapter": "filesystem", "output_root": "art",
            "categories": {"ing": {
                "data_source": {"type": "json_dict", "path": "items.json"},
                "prompt_template": template, **extra,
            }},
        }
        cfg.write_text(yaml.safe_dump(conf, sort_keys=False, allow_unicode=True),
                       encoding="utf-8")

    def run(*args):
        return ga.main(["ing", "--config", str(cfg), *args])

    write()
    return tmp_path, write, run


def _out(root: Path) -> Path:
    return root / "art" / "ing"


def _manifest(root: Path) -> dict:
    p = _out(root) / asset_manifest.MANIFEST_NAME
    return json.loads(p.read_text(encoding="utf-8"))["items"] if p.exists() else {}


def _warns(err: str) -> list:
    return [l for l in err.splitlines() if l.startswith("[warn]") or l.startswith("         -")]


# -------------------- 正常路径 --------------------

def test_first_run_records_every_generated_image(project):
    root, _, run = project
    assert run() == 0
    items = _manifest(root)
    assert set(items) == {"pearl.png", "taro.png"}
    assert items["pearl.png"]["request"]["prompt"] == "Icon of black pearls."
    assert (_out(root) / "pearl.png").read_text(encoding="utf-8") == "Icon of black pearls."


def test_rerun_with_same_config_is_quiet(project, capsys):
    root, _, run = project
    run()
    before = _manifest(root)
    capsys.readouterr()
    assert run() == 0
    assert not _warns(capsys.readouterr().err)
    assert _manifest(root) == before


# -------------------- 核心：改了模板之后 --------------------

def test_changed_template_is_reported_as_stale_not_skipped(project, capsys):
    """**这个功能存在的全部理由**：改完模板再跑，以前只得到一排 [skip]。"""
    root, write, run = project
    run()
    write(template="A shiny icon of {visual}.")
    capsys.readouterr()

    assert run() == 0
    captured = capsys.readouterr()
    warns = _warns(captured.err)
    assert any("2 张图已存在" in w and "不会" in w for w in warns), warns
    assert any("pearl.png" in w and "prompt" in w for w in warns), warns
    assert "stale=2" in captured.out


def test_stale_images_are_not_regenerated_without_force(project):
    """批量按张烧钱，旧图也可能是已经认可的 —— 只报告，不自动重出。"""
    root, write, run = project
    run()
    write(template="A shiny icon of {visual}.")
    run()
    assert (_out(root) / "pearl.png").read_text(encoding="utf-8") == "Icon of black pearls."


def test_skipped_image_keeps_its_old_record(project):
    """**最容易埋的 bug**：被后端跳过的图，记录必须保持原样。

    更新成新签名，就等于把一张过期图标成「最新」—— 下次跑它就不再报过期，
    而盘上那张图仍然是旧 prompt 画的。
    """
    root, write, run = project
    run()
    write(template="A shiny icon of {visual}.")
    run()
    assert _manifest(root)["pearl.png"]["request"]["prompt"] == "Icon of black pearls."
    # 所以第三次跑还得报过期
    write(template="A shiny icon of {visual}.")
    assert asset_manifest.load(_out(root))[0]["pearl.png"]["request"]["prompt"] \
        == "Icon of black pearls."


def test_force_regenerates_and_updates_the_record(project, capsys):
    root, write, run = project
    run()
    write(template="A shiny icon of {visual}.")
    assert run("--force") == 0
    assert (_out(root) / "pearl.png").read_text(encoding="utf-8") == "A shiny icon of black pearls."
    assert _manifest(root)["pearl.png"]["request"]["prompt"] == "A shiny icon of black pearls."
    capsys.readouterr()
    run()
    assert not _warns(capsys.readouterr().err)


def test_force_with_names_only_touches_the_named_record(project):
    """迭代时常用 --names 只重出一张。别的图的记录必须原样保留。"""
    root, write, run = project
    run()
    write(template="A shiny icon of {visual}.")
    run("--force", "--names", "pearl")
    items = _manifest(root)
    assert items["pearl.png"]["request"]["prompt"] == "A shiny icon of black pearls."
    assert items["taro.png"]["request"]["prompt"] == "Icon of taro chunks."


# -------------------- 不只是 prompt --------------------

def test_changed_model_is_named(project, capsys):
    root, write, run = project
    write(model="m-one")
    run()
    write(model="m-two")
    capsys.readouterr()
    run()
    assert any("model" in w and "pearl.png" in w for w in _warns(capsys.readouterr().err))


def test_replaced_reference_image_content_is_stale(project, capsys):
    """风格锚换了内容、路径没变 —— 这正是「风格没传过去，换张锚试试」的场景。"""
    root, write, run = project
    (root / "art").mkdir(exist_ok=True)
    anchor = root / "art" / "anchor.png"
    anchor.write_bytes(b"version-1")
    write(reference_paths=["anchor.png"])
    run()
    anchor.write_bytes(b"version-2")
    capsys.readouterr()
    run()
    assert any("风格参考图" in w for w in _warns(capsys.readouterr().err))


def test_renamed_reference_with_same_content_is_not_stale(project, capsys):
    """比的是内容，不是路径。"""
    root, write, run = project
    (root / "art").mkdir(exist_ok=True)
    (root / "art" / "a.png").write_bytes(b"same")
    (root / "art" / "b.png").write_bytes(b"same")
    write(reference_paths=["a.png"])
    run()
    write(reference_paths=["b.png"])
    capsys.readouterr()
    run()
    assert not _warns(capsys.readouterr().err)


# -------------------- 没发现 ≠ 没看 --------------------

def test_existing_file_without_record_is_untracked_not_stale(project, capsys):
    """本功能之前生成的、手动放进来的图，没有记录可比 —— 不能冒充「过期」。"""
    root, _, run = project
    _out(root).mkdir(parents=True)
    (_out(root) / "pearl.png").write_text("hand-made", encoding="utf-8")
    capsys.readouterr()
    assert run() == 0
    captured = capsys.readouterr()
    assert "没有生成记录" in captured.out
    assert not any("pearl.png" in w for w in _warns(captured.err))
    assert "pearl.png" not in _manifest(root)       # 它被跳过了，没有新记录
    assert "taro.png" in _manifest(root)            # 新生成的有


def test_corrupt_manifest_is_reported_and_treated_as_empty(project, capsys):
    root, _, run = project
    run()
    (_out(root) / asset_manifest.MANIFEST_NAME).write_text("{not json", encoding="utf-8")
    capsys.readouterr()
    assert run() == 0
    out = capsys.readouterr().out
    assert "读不了" in out and "没有生成记录" in out


# -------------------- 边界 --------------------

def test_failed_image_is_not_recorded(project, monkeypatch):
    root, _, run = project
    monkeypatch.setenv("STUB_FAIL", "pearl")
    run()
    assert set(_manifest(root)) == {"taro.png"}


def test_dry_run_writes_no_record(project):
    root, _, run = project
    run("--dry-run")
    assert not (_out(root) / asset_manifest.MANIFEST_NAME).exists()


def test_dry_run_shows_staleness_before_spending(project, capsys):
    """dry-run 的用处就是「跑之前看会发生什么」—— 过期要在这时候就说。"""
    root, write, run = project
    run()
    write(template="A shiny icon of {visual}.")
    capsys.readouterr()
    run("--dry-run")
    assert any("不会" in w for w in _warns(capsys.readouterr().err))


def test_record_has_no_absolute_paths(project):
    """这份记录可能随图入库。绝对路径对别人都是错的 —— 别人 checkout 下来会全部「过期」。"""
    root, write, run = project
    (root / "art").mkdir(exist_ok=True)
    (root / "art" / "anchor.png").write_bytes(b"x")
    write(reference_paths=["anchor.png"])
    run()
    text = (_out(root) / asset_manifest.MANIFEST_NAME).read_text(encoding="utf-8")
    assert str(root) not in text
    assert str(root).replace("\\", "/") not in text
    ref = _manifest(root)["pearl.png"]["request"]["reference_paths"][0]
    assert ref["path"] == "art/anchor.png"


def test_record_file_is_hidden(project):
    """Godot 的导入器跳过 . 开头的文件，不会把它当资源导入。"""
    assert asset_manifest.MANIFEST_NAME.startswith(".")


# -------------------- 单元：比对规则 --------------------

def test_diff_names_every_changed_field_in_order():
    old = {"prompt": "a", "model": "m1", "reference_paths": [], "image": None, "backend": "x"}
    new = {"prompt": "b", "model": "m2", "reference_paths": [], "image": None, "backend": "x"}
    assert asset_manifest.diff(old, new) == ("prompt", "model")


def test_diff_ignores_reference_path_when_content_is_the_same():
    old = {"reference_paths": [{"path": "a.png", "sha256": "h"}]}
    new = {"reference_paths": [{"path": "b.png", "sha256": "h"}]}
    assert asset_manifest.diff(old, new) == ()


def test_diff_catches_reference_order_change():
    """多图参考的顺序会影响后端怎么用它们。"""
    old = {"reference_paths": [{"sha256": "a"}, {"sha256": "b"}]}
    new = {"reference_paths": [{"sha256": "b"}, {"sha256": "a"}]}
    assert asset_manifest.diff(old, new) == ("reference_paths",)


# -------------------- 防线真正起作用的场景：文件已经在盘上 --------------------
#
# 上面「失败不记录」「dry-run 不写记录」两条，第一版走的都是「文件根本没生成」
# 这条路 —— 于是那两道防线就算被删掉，也会被后面的 exists() 检查挡住，测试照样绿。
# 变异验证抓出来的。它们真正起作用的时候，文件都已经在盘上了。

def test_failed_force_regeneration_keeps_the_old_record(project, monkeypatch):
    """--force 重出失败 → 盘上还是旧图。给它记新签名，就是把旧图标成「最新」。"""
    root, write, run = project
    run()
    write(template="A shiny icon of {visual}.")
    monkeypatch.setenv("STUB_FAIL", "pearl")
    run("--force")
    assert (_out(root) / "pearl.png").read_text(encoding="utf-8") == "Icon of black pearls."
    assert _manifest(root)["pearl.png"]["request"]["prompt"] == "Icon of black pearls."
    # 另一张成功重出了，它的记录要更新
    assert _manifest(root)["taro.png"]["request"]["prompt"] == "A shiny icon of taro chunks."


def test_dry_run_with_force_does_not_touch_existing_records(project):
    """dry-run 什么都没生成。可文件本来就在，加上 --force 就会被当成「刚生成的」。"""
    root, write, run = project
    run()
    before = _manifest(root)
    write(template="A shiny icon of {visual}.")
    run("--dry-run", "--force")
    assert _manifest(root) == before
