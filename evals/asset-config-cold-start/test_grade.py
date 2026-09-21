"""评分器自己的测试。

评分器是个检查器，而这个仓库反复证明过：没人测的检查器会假绿。所以每条考点都
配一个「故意做错」的输入，确认它真的会判不过。

打底的「好配置」是 codex 冷启动时真写出来、校验退 0 的那份（去掉了注释以外的
个人化措辞）—— 不是照着评分器反推出来的。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import grade  # noqa: E402
import run_eval  # noqa: E402

GOOD = """$schema_version: 1

# 依据：项目声明 engine: unreal，且存在 Toolbox.uproject；UE 使用普通文件系统路径。
adapter: filesystem

# 来源：用户选 A；沿用 Tools/import_props.py 的源图目录约定。
output_root: ArtSource

# 来源：用户选 laozhang。
backend: laozhang
# 来源：用户选 gemini-3-pro-image，优先考虑质量。
model: gemini-3-pro-image

style:
  # TODO（创作性）：尚未出小样
  prompt_prefix: >-
    游戏道具图标，用于背包格，缩小到 64×64 像素显示时仍清晰可辨。

categories:
  props:
    desc: 道具图标
    output_subdir: Props
    # 来源：用户选 1:1。
    aspect_ratio: "1:1"
    data_source:
      type: csv
      path: Design/props.csv
      # 来源：沿用 Design/Schema/props.schema.yaml 的 identity_column: prop_id 声明。
      id_column: prop_id
    # schema 声明 model 表示游戏内 mesh 精度，是业务数据
    item_overrides: {}
    # TODO（创作性）：构图待小样验证
    prompt_template: >-
      绘制单个「{名称}」。外观特征：{外观描述}。主体完整居中。
"""


@pytest.fixture
def workdir(tmp_path):
    return run_eval.prepare(tmp_path)


def _by_id(checks) -> dict:
    return {c.id: c for c in checks}


def _write(workdir, text):
    (workdir / "asset-config.yaml").write_text(text, encoding="utf-8")


# -------------------- 夹具本身 --------------------

def test_fixture_is_laid_out_as_a_clean_repo(workdir):
    assert (workdir / ".gitignore").exists()             # gitignore.txt 改回了原名
    assert not (workdir / "gitignore.txt").exists()
    assert (workdir / "Content").is_dir()                # 空目录也铺出来了
    assert grade._changed_paths(workdir) == set()        # 干净，只有初始提交
    # 被忽略的那个美术目录，在铺出来的工程里确实被忽略
    assert "SourceArt" in grade._git(workdir, "status", "--ignored", "--porcelain")


def test_prompts_render_with_real_paths():
    text = run_eval.render("round1.md", sys.executable)
    assert "{skill}" not in text and "SKILL.md" in text
    assert Path(text.split("SKILL.md")[0].split()[-1] + "SKILL.md").exists()


# -------------------- 第二轮：好配置全过 --------------------

def test_good_config_passes_every_automated_check(workdir):
    _write(workdir, GOOD)
    checks = grade.grade_round2(workdir)
    failed = [(c.id, c.detail) for c in checks if c.passed is not True]
    assert not failed, failed


# -------------------- 第二轮：每条考点都抓得到对应的错 --------------------

@pytest.mark.parametrize("check_id, old, new", [
    ("r2.adapter", "adapter: filesystem", "adapter: unreal"),              # 照抄 engine
    ("r2.item_overrides", "    item_overrides: {}\n", ""),                 # 没声明业务列
    ("r2.item_overrides", "item_overrides: {}", "item_overrides: {model: model}"),
    ("r2.output_dir", "output_root: ArtSource", "output_root: SourceArt"),  # 被忽略的目录
    ("r2.id_column", "id_column: prop_id", "id_column: 名称"),
    ("r2.data_source", "path: Design/props.csv", "path: Design/enemies.csv"),
    ("r2.answers_applied", "model: gemini-3-pro-image", "model: gemini-3.1-flash-image"),
    ("r2.answers_applied", 'aspect_ratio: "1:1"', 'aspect_ratio: "4:3"'),
    ("r2.no_todo_in_prompt", "主体完整居中。", "主体完整居中。TODO 构图"),
])
def test_each_check_catches_its_mistake(workdir, check_id, old, new):
    assert old in GOOD
    _write(workdir, GOOD.replace(old, new, 1))
    got = _by_id(grade.grade_round2(workdir))
    assert got[check_id].passed is False, got[check_id].detail


def test_missing_adapter_is_not_a_pass(workdir):
    _write(workdir, GOOD.replace("adapter: filesystem\n", ""))
    assert _by_id(grade.grade_round2(workdir))["r2.adapter"].passed is False


def test_missing_source_comment_fails_check(workdir):
    """治理一档也算在 check 退码里 —— 来源注释漏了就不是退 0。"""
    _write(workdir, GOOD.replace("# 来源：用户选 laozhang。\n", ""))
    assert _by_id(grade.grade_round2(workdir))["r2.check"].passed is False


def test_committing_violates_the_boundary(workdir):
    _write(workdir, GOOD)
    grade._git(workdir, "add", "-A")
    grade._git(workdir, "commit", "-q", "-m", "agent committed")
    assert _by_id(grade.grade_round2(workdir))["r2.git_boundary"].passed is False


def test_touching_other_files_violates_the_boundary(workdir):
    _write(workdir, GOOD)
    (workdir / "Design" / "props.csv").write_text("tampered", encoding="utf-8")
    assert _by_id(grade.grade_round2(workdir))["r2.git_boundary"].passed is False


def test_no_config_at_all(workdir):
    got = grade.grade_round2(workdir)
    assert len(got) == 1 and got[0].id == "r2.config" and got[0].passed is False


# -------------------- 第一轮 --------------------

_QUESTIONS = """草稿：adapter 写 filesystem。

问题：
1. 用哪个后端（backend）？laozhang / image-gen
2. 用哪个生图模型？gemini-3-pro-image / gemini-3.1-flash
3. 比例（aspect_ratio）？1:1 / 4:3
"""


def test_round1_good(workdir):
    (workdir / "QUESTIONS.md").write_text(_QUESTIONS, encoding="utf-8")
    failed = [(c.id, c.detail) for c in grade.grade_round1(workdir) if c.passed is not True]
    assert not failed, failed


def test_round1_writing_the_config_early_fails(workdir):
    (workdir / "QUESTIONS.md").write_text(_QUESTIONS, encoding="utf-8")
    _write(workdir, GOOD)
    got = _by_id(grade.grade_round1(workdir))
    assert got["r1.no_config"].passed is False
    assert got["r1.git_boundary"].passed is False      # 多出的文件


def test_round1_without_questions_fails(workdir):
    assert _by_id(grade.grade_round1(workdir))["r1.questions"].passed is False


@pytest.mark.parametrize("check_id, drop", [
    ("r1.asks_backend", ("backend", "后端")),
    ("r1.asks_model", ("生图模型", "gemini")),
    ("r1.asks_aspect_ratio", ("aspect_ratio", "比例")),
])
def test_round1_heuristics_notice_a_missing_topic(workdir, check_id, drop):
    text = _QUESTIONS
    for w in drop:
        text = text.replace(w, "某项")
    (workdir / "QUESTIONS.md").write_text(text, encoding="utf-8")
    got = _by_id(grade.grade_round1(workdir))
    assert got[check_id].passed is False and got[check_id].heuristic


def test_business_model_column_alone_does_not_count_as_asking_about_the_model(workdir):
    """表里本来就有一列叫 model。提到它不等于问了生图模型。"""
    (workdir / "QUESTIONS.md").write_text(
        "表里的 model 列是低模/高模。后端（backend）用哪个？比例呢？", encoding="utf-8")
    assert _by_id(grade.grade_round1(workdir))["r1.asks_model"].passed is False


# -------------------- 变异验证补的两条 --------------------
# 上面那组第一版有两处假绿：删掉对应的判断，测试照样全过。

def test_adding_an_enemy_category_is_out_of_scope(workdir):
    """用户说只要道具。第一版的测试是把道具表「换成」敌人表 —— 那样「没读道具表」
    先判了不过，「不该读敌人表」这一半从来没被单独测到。真实的错法是「多加」一个。
    """
    extra = GOOD + """
  enemies:
    data_source:
      type: csv
      path: Design/enemies.csv
      # 来源：测试
      id_column: enemy_id
    item_overrides: {}
    prompt_template: "{名称}"
"""
    _write(workdir, extra)
    got = _by_id(grade.grade_round2(workdir))
    assert got["r2.check"].passed is True          # 配置本身没毛病
    assert got["r2.data_source"].passed is False   # 但超出了用户要的范围


def test_dry_run_failure_is_caught_even_when_check_passes(workdir, monkeypatch):
    """后端脚本不在位：check 只提示、退 0（校验配置不该要求生图环境就绪），
    dry-run 却直接 fatal。两边结论不同，评分器得分别看。
    """
    monkeypatch.setenv("IMAGE_GEN_SCRIPT", str(workdir / "no_such_backend.py"))
    _write(workdir, GOOD)
    got = _by_id(grade.grade_round2(workdir))
    assert got["r2.check"].passed is True
    assert got["r2.dry_run"].passed is False
