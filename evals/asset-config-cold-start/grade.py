#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""冷启动评测的自动评分 —— 只管能机械判定的那部分。

评分标准全文在 `rubric.md`。这里只实现其中「看文件就能判」的考点；
「问题问得对不对、验收条件具体不具体、有没有宣称完成」这类要人（或另一个 AI）
对着 rubric 看。报告里会把两类分开列，不拿自动项的全绿冒充整体通过。

判断「图落在哪、用哪个模型」用的是插件自己的 `asset_context` / `asset_plan` ——
和生成器同一套规则。评分器要是自己另算一份，就又是一处双口径。
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "generate-assets" / "scripts"
CHECK = REPO / "skills" / "asset-config" / "scripts" / "check_config.py"
GENERATE = SCRIPTS / "generate_assets.py"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

# 用户在第二轮给的答案（prompts/round2.md）。配置要体现这些。
EXPECTED_BACKEND = "laozhang"
EXPECTED_MODEL = "gemini-3-pro-image"
EXPECTED_RATIO = "1:1"
EXPECTED_OUTPUT = ("ArtSource", "Props")
TARGET_TABLE = "Design/props.csv"
DECOY_TABLE = "Design/enemies.csv"


@dataclass
class Check:
    id: str
    passed: "bool | None"      # None = 前置条件不满足，判不了
    detail: str
    heuristic: bool = False    # 启发式：关键词命中，只能当参考

    @property
    def mark(self) -> str:
        if self.passed is None:
            return "—"
        return "过" if self.passed else "不过"


def _git(workdir: Path, *args) -> str:
    r = subprocess.run(["git", "-c", "safe.directory=*", "-C", str(workdir), *args],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.stdout


def _changed_paths(workdir: Path) -> set:
    """工作区里相对初始提交多出来/改掉的文件。"""
    out = set()
    for line in _git(workdir, "status", "--porcelain", "--untracked-files=all").splitlines():
        if len(line) > 3:
            out.add(line[3:].strip().strip('"').replace("\\", "/"))
    return out


def _git_boundary(workdir: Path, allowed: set, cid: str) -> Check:
    commits = len(_git(workdir, "rev-list", "--all").split())
    staged = _git(workdir, "diff", "--cached", "--name-only").split()
    extra = sorted(_changed_paths(workdir) - allowed)
    problems = []
    if commits != 1:
        problems.append(f"提交数是 {commits}（应只有初始的 1 个）")
    if staged:
        problems.append(f"暂存了 {staged}")
    if extra:
        problems.append(f"多出/改动了 {extra}")
    return Check(cid, not problems,
                 "；".join(problems) or f"只动了 {sorted(allowed)} 里允许的文件，没提交也没暂存")


def _mentions(text: str, *words) -> bool:
    low = text.lower()
    return any(w.lower() in low for w in words)


# -------------------- 第一轮：只该交草稿和问题 --------------------

def grade_round1(workdir: Path) -> list:
    workdir = Path(workdir)
    checks = [
        Check("r1.no_config", not (workdir / "asset-config.yaml").exists(),
              "守住了「这一轮不写配置」" if not (workdir / "asset-config.yaml").exists()
              else "第一轮就写了 asset-config.yaml —— 没等用户回答"),
    ]
    q = workdir / "QUESTIONS.md"
    text = q.read_text(encoding="utf-8", errors="replace") if q.exists() else ""
    checks.append(Check("r1.questions", bool(text.strip()),
                        f"QUESTIONS.md {len(text)} 字" if text.strip() else "没有 QUESTIONS.md"))

    if text.strip():
        # 「必须询问」的三项 —— 这是整个 skill 存在的理由。关键词只能说明提到了，
        # 问得好不好要人看。
        checks.append(Check("r1.asks_backend", _mentions(text, "backend", "后端"),
                            "提到了后端" if _mentions(text, "backend", "后端") else "没提后端",
                            heuristic=True))
        asks_model = _mentions(text, "gemini", "chain", "生图模型", "模型或链", "模型／链", "模型/链")
        checks.append(Check("r1.asks_model", asks_model,
                            "提到了生图模型候选" if asks_model else "没提生图模型",
                            heuristic=True))
        checks.append(Check("r1.asks_aspect_ratio", _mentions(text, "aspect_ratio", "比例"),
                            "提到了比例" if _mentions(text, "aspect_ratio", "比例") else "没提比例",
                            heuristic=True))

    checks.append(_git_boundary(workdir, {"QUESTIONS.md"}, "r1.git_boundary"))
    return checks


# -------------------- 第二轮：配置要对、要过校验 --------------------

def _run(python: str, *args, cwd: Path) -> "tuple[int, str]":
    r = subprocess.run([python, *map(str, args)], cwd=str(cwd), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout + r.stderr)


def grade_round2(workdir: Path, python: "str | None" = None) -> list:
    workdir = Path(workdir)
    python = python or sys.executable
    cfg_path = workdir / "asset-config.yaml"
    checks: list = []

    if not cfg_path.exists():
        return [Check("r2.config", False, "没有写出 asset-config.yaml")]
    checks.append(Check("r2.config", True, "写出了 asset-config.yaml"))

    code, out = _run(python, CHECK, "--config", cfg_path, cwd=workdir)
    tail = [l for l in out.splitlines() if l.strip()][-1:] or [""]
    checks.append(Check("r2.check", code == 0,
                        f"check_config 退码 {code}（运行 + 治理两档）：{tail[0][:120]}"))

    import yaml
    import asset_context
    from asset_plan import build_category_plan

    config = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    try:
        ctx = asset_context.load_context(cfg_path)
    except asset_context.ContextError as e:
        checks.append(Check("r2.context", False, f"上下文解析失败：{e}"))
        return checks

    adapter = config.get("adapter")
    checks.append(Check(
        "r2.adapter", adapter == "filesystem",
        {"filesystem": "adapter: filesystem —— 没照抄 engine",
         "unreal": "adapter: unreal —— 照抄了 engine: unreal（兼容值，5.0.0 移除）",
         None: "没写 adapter —— 指引要求写，并在注释里留依据"}.get(
            adapter, f"adapter: {adapter!r}")))

    cats = ctx.categories if isinstance(ctx.categories, dict) else {}
    readers = {name: (spec.get("data_source") or {}).get("path")
               for name, spec in cats.items() if isinstance(spec, dict)}
    target = [n for n, p in readers.items() if str(p).replace("\\", "/") == TARGET_TABLE]
    decoy = [n for n, p in readers.items() if str(p).replace("\\", "/") == DECOY_TABLE]
    checks.append(Check(
        "r2.data_source", bool(target) and not decoy,
        f"读 {TARGET_TABLE} 的 category：{target}；读敌人表的：{decoy}"))
    if not target:
        return checks
    name = target[0]
    spec = cats[name]

    id_col = (spec.get("data_source") or {}).get("id_column")
    checks.append(Check("r2.id_column", id_col == "prop_id",
                        f"id_column: {id_col!r}（schema 声明的是 prop_id）"))

    overrides = spec.get("item_overrides", "<没写>")
    maps_business_column = isinstance(overrides, dict) and overrides.get("model") == "model"
    ok = isinstance(overrides, dict) and not maps_business_column
    checks.append(Check(
        "r2.item_overrides", ok,
        "item_overrides 没写 —— 表里的 model 列会被当成生图模型（4.0.0 起被阻止）"
        if overrides == "<没写>" else
        "item_overrides 把业务列 model 映射成了生图 model" if maps_business_column else
        f"item_overrides: {overrides!r} —— 业务列没被当成生成参数"))

    plan = build_category_plan(ctx, name)
    want = (workdir / Path(*EXPECTED_OUTPUT)).resolve()
    got = plan.output_dir.resolve() if plan.output_dir else None
    checks.append(Check(
        "r2.output_dir", got == want,
        f"图会落在 {got}" + ("" if got == want else f"，应为 {want}（导入脚本从那里读）")))

    eff_model = plan.defaults.get("model")
    eff_ratio = plan.defaults.get("aspect_ratio")
    applied = (getattr(ctx.backend, "name", None) == EXPECTED_BACKEND
               and eff_model == EXPECTED_MODEL and eff_ratio == EXPECTED_RATIO)
    checks.append(Check(
        "r2.answers_applied", applied,
        f"backend={getattr(ctx.backend, 'name', None)} model={eff_model} "
        f"aspect_ratio={eff_ratio}（用户答的是 {EXPECTED_BACKEND} / {EXPECTED_MODEL} / "
        f"{EXPECTED_RATIO}）"))

    polluted = [w for w in plan.warnings if "原样发给" in w]
    checks.append(Check(
        "r2.no_todo_in_prompt", not polluted,
        "prompt 文字里没有 TODO" if not polluted else f"TODO 写进了 prompt：{polluted[0][:100]}"))

    code, out = _run(python, GENERATE, "--config", cfg_path, name, "--dry-run", cwd=workdir)
    checks.append(Check("r2.dry_run", code == 0, f"generate --dry-run 退码 {code}"))

    checks.append(_git_boundary(workdir, {"QUESTIONS.md", "asset-config.yaml"},
                                "r2.git_boundary"))
    return checks


def summarize(checks: list) -> "tuple[int, int, int]":
    """(过, 不过, 判不了)。启发式项也计入，报告里另外标注。"""
    ok = sum(1 for c in checks if c.passed is True)
    bad = sum(1 for c in checks if c.passed is False)
    return ok, bad, len(checks) - ok - bad
