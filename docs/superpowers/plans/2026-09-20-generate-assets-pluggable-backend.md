# generate-assets 可插拔生图后端 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 generate-assets 与 image-gen 之间的隐式协议显式化为后端契约，并让插件自带一个可直接跑的 laozhang 极简后端。

**Architecture:** 新增 `image_backend.py`（结构逐条对称既有的 `engine_adapter.py`：frozen dataclass + 注册表 + `select()`），主流程改为经它选后端；后端是「一个可执行 Python 脚本 + 一套 CLI 约定」，不是 skill。插件内置 `backends/laozhang_backend.py` 作为参考实现。

**Tech Stack:** Python 3.10+、pytest、requests（仅 laozhang 后端用）、PyYAML（既有）

**Spec:** `docs/superpowers/specs/2026-09-20-generate-assets-pluggable-backend-design.md`

## Global Constraints

- 工作目录为 `skills/generate-assets/`，测试用 `python -m pytest` 在该目录下跑
- Python 3.10+ 语法（既有代码已用 `dict | None`、`from __future__ import annotations`）
- laozhang 后端**只能**依赖 `requests` + 标准库，不得引入 google-genai 等重 SDK
- 缺省后端必须是 `image-gen`，作者本机行为一字不变
- `IMAGE_GEN_SCRIPT` 环境变量保持**最高优先级** —— `tests/conftest.py` 的 `mock_subprocess_run` fixture 靠它指向假脚本，破坏它会连带废掉整个测试套件
- 协议必需字段：`total` / `success` / `failed` / `skipped`；退码 `0` 全成功 / `1` 全失败 / `2` 部分失败
- batch JSON 顶层 `$schema_version: 2`；asset 字段是 `name` / `filename` / `prompt`（**不是** `id`），可选 `aspect_ratio` / `seed`
- 区分两个 schema_version：asset-config.yaml 顶层是 `1`，batch JSON 顶层是 `2`
- 测试一律 mock，禁止打真 API
- 注释与报错文案用中文，跟随既有风格：报错要说清「怎么办」，列出可选项

---

### Task 1: `image_backend.py` —— 后端结构与选择

**Files:**
- Create: `scripts/image_backend.py`
- Test: `tests/test_image_backend.py`

**Interfaces:**
- Consumes: 无（纯新增，不碰主流程）
- Produces:
  - `ImageBackend` frozen dataclass，字段 `name: str`、`resolve_script: Callable[[], Path | None]`、`supports: frozenset`、`install_hint: str`
  - `BACKENDS: dict[str, ImageBackend]`，键为 `"image-gen"` / `"laozhang"`
  - `select(config: dict, project_root: Path) -> ImageBackend`
  - `ALL_FIELDS: frozenset` —— defaults 全集，自定义后端用它以免误告警
  - `SCRIPT_ENV = "IMAGE_GEN_SCRIPT"`

- [ ] **Step 1: 写选择优先级的失败测试**

创建 `tests/test_image_backend.py`：

```python
"""后端注册表与选择。"""
from __future__ import annotations

from pathlib import Path

import pytest

import image_backend


def test_default_is_image_gen(tmp_path, monkeypatch):
    """config 没写 backend 且没有环境变量 → image-gen（保持既有行为）。"""
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    be = image_backend.select({}, tmp_path)
    assert be.name == "image-gen"


def test_env_var_wins_over_config(tmp_path, monkeypatch):
    """IMAGE_GEN_SCRIPT 优先级最高——conftest 的 mock fixture 依赖这条。"""
    script = tmp_path / "fake.py"
    script.write_text("# stub\n", encoding="utf-8")
    monkeypatch.setenv("IMAGE_GEN_SCRIPT", str(script))
    be = image_backend.select({"backend": "laozhang"}, tmp_path)
    assert be.resolve_script() == script
    # 环境变量指过来的脚本能力未知，按全集处理，不误报降级
    assert be.supports == image_backend.ALL_FIELDS


def test_config_backend_name(tmp_path, monkeypatch):
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    be = image_backend.select({"backend": "laozhang"}, tmp_path)
    assert be.name == "laozhang"
    assert "chain" not in be.supports
    assert "reference_paths" in be.supports
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_image_backend.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'image_backend'`

- [ ] **Step 3: 实现 `image_backend.py`**

创建 `scripts/image_backend.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生图后端层：把「实际生图用哪个程序」从流水线里分出来。

插拔的单位是**一个可执行脚本 + 一套 CLI 约定**，不是 skill。本模块只负责
挑出那个脚本；怎么调、怎么读结果在 generate_assets.py，协议写在
BACKEND-PROTOCOL.md。

注册表里的条目是同构的，都只是「一个脚本路径」：
  - image-gen 指向外部用户级 skill 里的脚本（可能不存在）
  - laozhang  指向本插件自带的脚本（随插件走，必定存在）
注册表不关心那个路径背后是不是 skill。

新增一个内置后端 = 加一个 ImageBackend 实例并注册，不用改主流程。
"""
from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# batch JSON defaults 里可能出现的全部字段。自定义后端能力未知，按全集处理 ——
# 宁可不告警，也不要对着一个我们没见过的后端误报「不支持 chain」。
ALL_FIELDS = frozenset({"chain", "preset", "reference_paths", "aspect_ratio", "seed"})

SCRIPT_ENV = "IMAGE_GEN_SCRIPT"


@dataclass(frozen=True)
class ImageBackend:
    name: str
    # 解析入口脚本；找不到返回 None，由调用方打 install_hint
    resolve_script: Callable[[], "Path | None"]
    # 认得的 defaults 字段，用于降级告警
    supports: frozenset
    # 找不到脚本时告诉人怎么装
    install_hint: str


def _existing(p: Path) -> "Path | None":
    return p if p.exists() else None


def _image_gen_script() -> "Path | None":
    return _existing(
        Path.home() / ".claude" / "skills" / "image-gen" / "scripts" / "generate_image.py"
    )


def _laozhang_script() -> "Path | None":
    return _existing(Path(__file__).resolve().parent / "backends" / "laozhang_backend.py")


IMAGE_GEN = ImageBackend(
    name="image-gen",
    resolve_script=_image_gen_script,
    supports=ALL_FIELDS,
    install_hint=(
        "image-gen 是独立的用户级 skill（~/.claude/skills/image-gen），不随本插件安装。"
        "装好它，或用 backend: laozhang 换成插件自带的极简后端，"
        f"或用 {SCRIPT_ENV}=<脚本路径> 指向别的实现。"
    ),
)

LAOZHANG = ImageBackend(
    name="laozhang",
    resolve_script=_laozhang_script,
    # chain / preset 是 image-gen 特有的风格链与预设，本后端没有对应概念
    supports=frozenset({"reference_paths", "aspect_ratio", "seed"}),
    install_hint=(
        "laozhang 后端随插件安装，脚本却不见了 —— 插件目录可能不完整，"
        "重装插件或 /plugin update game-toolkit。"
    ),
)

BACKENDS = {"image-gen": IMAGE_GEN, "laozhang": LAOZHANG}


def _custom(path: Path, origin: str) -> ImageBackend:
    """外部脚本后端。能力未知 → supports 用全集，不误报降级。"""
    return dataclasses.replace(
        IMAGE_GEN,
        name=f"custom:{path.name}",
        resolve_script=lambda: _existing(path),
        supports=ALL_FIELDS,
        install_hint=f"{origin} 指向的后端脚本不存在：{path}。检查路径是否写对。",
    )


def _looks_like_path(value: str) -> bool:
    return "/" in value or "\\" in value or value.endswith(".py")


def select(config: dict, project_root: Path) -> ImageBackend:
    """选后端。优先级：环境变量 > config 的 backend > 缺省 image-gen。

    环境变量放在最高位是为了向后兼容：它原本就是 image-gen 的覆盖点，
    测试套件的 mock fixture 也靠它把脚本指到临时文件。
    """
    env_path = os.environ.get(SCRIPT_ENV)
    if env_path:
        return _custom(Path(env_path), f"环境变量 {SCRIPT_ENV}")

    declared = str(config.get("backend") or "").strip()
    if not declared:
        return IMAGE_GEN

    if _looks_like_path(declared):
        p = Path(declared)
        if not p.is_absolute():
            # 与 output_root 同基准。相对 config 目录或 cwd 都说得通，
            # 但一份 yaml 只该有一个「相对谁」的答案。
            p = (Path(project_root) / p).resolve()
        return _custom(p, "config 的 backend")

    if declared not in BACKENDS:
        raise ValueError(
            "未知的 backend: {!r}（可选：{}）。"
            "也可以直接写一个脚本路径，满足 BACKEND-PROTOCOL.md 的约定即可。"
            .format(declared, " / ".join(sorted(BACKENDS)))
        )
    return BACKENDS[declared]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_image_backend.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 补未知名字与路径式后端的测试**

追加到 `tests/test_image_backend.py`：

```python
def test_unknown_backend_lists_options(tmp_path, monkeypatch):
    """报错必须列出可选项——只说'不认识'的话人还得去翻源码。"""
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    with pytest.raises(ValueError) as ei:
        image_backend.select({"backend": "midjourney"}, tmp_path)
    msg = str(ei.value)
    assert "midjourney" in msg
    assert "image-gen" in msg and "laozhang" in msg


def test_path_backend_relative_to_project_root(tmp_path, monkeypatch):
    """相对路径以 project_root 为基准，不是 cwd、不是 config 目录。"""
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    script = tmp_path / "tools" / "my_backend.py"
    script.parent.mkdir(parents=True)
    script.write_text("# stub\n", encoding="utf-8")
    be = image_backend.select({"backend": "tools/my_backend.py"}, tmp_path)
    assert be.resolve_script() == script.resolve()
    assert be.supports == image_backend.ALL_FIELDS


def test_path_backend_missing_reports_path(tmp_path, monkeypatch):
    monkeypatch.delenv("IMAGE_GEN_SCRIPT", raising=False)
    be = image_backend.select({"backend": "tools/absent.py"}, tmp_path)
    assert be.resolve_script() is None
    assert "absent.py" in be.install_hint
```

- [ ] **Step 6: 跑测试**

Run: `python -m pytest tests/test_image_backend.py -v`
Expected: PASS（6 passed）—— Step 3 的实现已覆盖这些分支；若有红，修实现而非改测试

- [ ] **Step 7: Commit**

```bash
git add scripts/image_backend.py tests/test_image_backend.py
git commit -m "feat: 新增 image_backend 后端注册表与选择"
```

---

### Task 2: 主流程改用注册表

**Files:**
- Modify: `scripts/generate_assets.py`（删 `_resolve_image_gen` 与 `DEFAULT_IMAGE_GEN_SCRIPT`/`IMAGE_GEN_SCRIPT_ENV` 常量；`main()` 约 152 行的调用点；`_run_category` 参数名；`_invoke_image_gen` 改名）
- Modify: `tests/test_main_flow.py`（两条 `test_missing_image_gen_*`）

**Interfaces:**
- Consumes: Task 1 的 `image_backend.select(config, project_root) -> ImageBackend`、`ImageBackend.resolve_script()`、`.install_hint`、`.name`
- Produces: `_invoke_backend(cmd) -> tuple[dict | None, int, str | None]`（原 `_invoke_image_gen` 改名，行为不变）；`_run_category(..., backend_script: Path, ...)`（原参数名 `image_gen_script`）

- [ ] **Step 1: 改现有两条测试为后端无关的语义**

在 `tests/test_main_flow.py` 顶部确保有 `import dataclasses`。把 `test_missing_image_gen_fails_fast_with_directions` 与 `test_missing_image_gen_at_default_location_is_also_reported` 整体替换为：

```python
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
```

注：`ImageBackend` 是 frozen dataclass，不能直接给实例字段赋值，所以用 `dataclasses.replace` 换掉整个模块级常量。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_main_flow.py -k backend -v`
Expected: FAIL — `AttributeError: module 'generate_assets' has no attribute 'image_backend'`

- [ ] **Step 3: 改 `generate_assets.py` 的导入与常量**

在与 `engine_adapter` 并列的导入区加入：

```python
import image_backend
```

删除这两个常量，连同 `_resolve_image_gen` 整个函数（约 291–310 行）：

```python
IMAGE_GEN_SCRIPT_ENV = "IMAGE_GEN_SCRIPT"
DEFAULT_IMAGE_GEN_SCRIPT = Path.home() / ".claude" / "skills" / "image-gen" / "scripts" / "generate_image.py"
```

- [ ] **Step 4: 改 `main()` 的调用点**

把约 152 行的：

```python
    image_gen_script = _resolve_image_gen()
    if image_gen_script is None:
        return 1
```

替换为：

```python
    try:
        backend = image_backend.select(config, project_root)
    except ValueError as e:
        print(f"[fatal] {e}", file=sys.stderr)
        return 1
    backend_script = backend.resolve_script()
    if backend_script is None:
        print(
            f"[fatal] backend={backend.name} 的脚本不存在。{backend.install_hint}",
            file=sys.stderr,
        )
        return 1
```

并把下方 `_run_category(...)` 调用里的 `image_gen_script=image_gen_script,` 改为 `backend_script=backend_script,`。

- [ ] **Step 5: 改 `_run_category` 与 `_invoke_image_gen`**

`_run_category` 签名里 `image_gen_script: Path,` → `backend_script: Path,`；函数体内构造 cmd 处：

```python
    cmd = [
        sys.executable,
        str(backend_script),
        str(batch_path),
        "--output-dir",
        str(output_dir),
    ]
```

把 `summary, exit_code, err = _invoke_image_gen(cmd)` 改为 `_invoke_backend(cmd)`。
`_invoke_image_gen` 改名为 `_invoke_backend`，docstring 改为「跑后端，返回 (summary_json, exit_code, error_msg)。后端会把末尾一行 JSON summary 打到 stdout。」。
该函数内 `return None, 1, f"image-gen 脚本不存在: {e}"` 改为 `f"后端脚本不存在: {e}"`。
无 summary 那条 `err = f"image-gen 没有返回 summary，..."` 改为 `err = f"后端没有返回 summary，无法确认生成结果（它的退出码 {exit_code}）"`。

- [ ] **Step 6: 跑全套测试**

Run: `python -m pytest tests/ -v`
Expected: PASS（全绿）

- [ ] **Step 7: Commit**

```bash
git add scripts/generate_assets.py tests/test_main_flow.py
git commit -m "feat: 主流程改用 image_backend 选后端"
```

---

### Task 3: 降级告警

**Files:**
- Modify: `scripts/generate_assets.py`（新增 `_warn_unsupported`；`_run_category` 新增 `backend` 参数并调用它）
- Test: `tests/test_main_flow.py`

**Interfaces:**
- Consumes: Task 1 的 `ImageBackend.supports` / `.name`、Task 2 的 `backend` 对象
- Produces: `_warn_unsupported(cat_name: str, defaults: dict, backend) -> None`；`_run_category(..., backend, ...)`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_main_flow.py`：

```python
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
    # 不会改字典里那个。走 backend: 具名分支时 select() 从字典取，所以两处都要换。
    # （Task 2 那条测试不需要 setitem —— 它走的是 `return IMAGE_GEN`，模块全局查找。）
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
    """image-gen 认 chain，不该有告警噪音。"""
    _, _ = mock_subprocess_run   # fixture 已把 IMAGE_GEN_SCRIPT 指向假脚本
    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    conf["style"]["chain"] = "default"
    _write_yaml(cfg, conf)

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    assert "不支持 chain" not in capsys.readouterr().err
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_main_flow.py -k unsupported -v`
Expected: FAIL — 断言 `"chain" in err` 不成立（当前无任何告警）

- [ ] **Step 3: 实现 `_warn_unsupported`**

在 `generate_assets.py` 中 `_build_batch_json` 附近加入：

```python
def _warn_unsupported(cat_name: str, defaults: dict, backend) -> None:
    """defaults 里有后端不认的字段就说出来。

    静默忽略会让人以为风格链生效了实则没有；报错又会让「切个后端试一下」
    变得很麻烦。所以告警后继续，并且必须带上被丢弃的值 —— 只说「不支持
    chain」，人还得回头翻 yaml 才知道丢了什么。
    """
    unknown = [k for k in defaults if k not in backend.supports]
    for key in sorted(unknown):
        print(
            f"[warn] category={cat_name}: backend={backend.name} 不支持 {key}"
            f"（值 {defaults[key]!r}），已忽略。"
            f"风格链/预设是 image-gen 特有能力，切回 backend: image-gen 才生效。",
            file=sys.stderr,
        )
```

- [ ] **Step 4: 接进 `_run_category`**

`_run_category` 签名新增 `backend,`（放在 `backend_script: Path,` 之后）。在 `batch = _build_batch_json(...)` 的 try 块之后、`if not batch["assets"]:` 之前插入：

```python
    _warn_unsupported(cat_name, batch.get("defaults") or {}, backend)
```

`main()` 里 `_run_category(...)` 调用处补上 `backend=backend,`。

- [ ] **Step 5: 跑全套测试**

Run: `python -m pytest tests/ -v`
Expected: PASS（全绿）

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_assets.py tests/test_main_flow.py
git commit -m "feat: 后端不支持的 defaults 字段按 category 告警"
```

---

### Task 4: laozhang 后端 —— 协议层

**Files:**
- Create: `scripts/backends/laozhang_backend.py`
- Test: `tests/test_laozhang_backend.py`

**Interfaces:**
- Consumes: 无（独立 CLI，只按协议收发）
- Produces:
  - `main(argv: list[str] | None = None) -> int`
  - `_generate_one(prompt: str, *, model: str, api_key: str, base_url: str, aspect_ratio: str, seed: int | None, reference_paths: list, timeout_s: float) -> bytes` —— 本任务先抛 `NotImplementedError`，Task 5 填实现；测试用 monkeypatch 替换它
  - 常量 `SUPPORTED_SCHEMA = 2`、`DEFAULT_MODEL = "gemini-3.1-flash-image-preview"`、`DEFAULT_BASE_URL`、`DEFAULT_TIMEOUT_S`、`MAX_REFERENCES = 14`

- [ ] **Step 1: 写协议层的失败测试**

创建 `tests/test_laozhang_backend.py`：

```python
"""laozhang 极简后端的协议层：不打真 API。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKENDS_DIR = Path(__file__).resolve().parent.parent / "scripts" / "backends"
if str(BACKENDS_DIR) not in sys.path:
    sys.path.insert(0, str(BACKENDS_DIR))

import laozhang_backend as lb


def _batch(tmp_path: Path, assets: list, defaults: dict | None = None) -> Path:
    p = tmp_path / "batch.json"
    p.write_text(json.dumps({
        "$schema_version": 2,
        "defaults": defaults or {},
        "assets": assets,
    }, ensure_ascii=False), encoding="utf-8")
    return p


def _read_summary(capsys) -> dict:
    """summary 必须是 stdout 的最后一行。"""
    out = capsys.readouterr().out.strip().splitlines()
    return json.loads(out[-1])


def test_dry_run_makes_no_request_and_writes_nothing(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    called = []
    monkeypatch.setattr(lb, "_generate_one", lambda *a, **k: called.append(1) or b"x")
    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}])
    out = tmp_path / "out"
    out.mkdir()

    rc = lb.main([str(batch), "--output-dir", str(out), "--dry-run"])

    assert rc == 0
    assert called == []
    assert list(out.iterdir()) == []
    assert _read_summary(capsys)["total"] == 1


def test_rejects_unknown_schema_version(tmp_path, capsys, monkeypatch):
    """不认识的 schema 直接报错，不要猜。"""
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    p = tmp_path / "batch.json"
    p.write_text(json.dumps({"$schema_version": 99, "defaults": {}, "assets": []}), encoding="utf-8")
    rc = lb.main([str(p), "--output-dir", str(tmp_path)])
    assert rc == 1
    assert "99" in capsys.readouterr().err


def test_missing_api_key_explains_how_to_set_it(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("LAOZHANG_API_KEY", raising=False)
    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}])
    rc = lb.main([str(batch), "--output-dir", str(tmp_path)])
    assert rc == 1
    assert "LAOZHANG_API_KEY" in capsys.readouterr().err


def test_existing_file_is_skipped_without_force(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    calls = []
    monkeypatch.setattr(lb, "_generate_one", lambda *a, **k: calls.append(1) or b"png")
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.png").write_bytes(b"old")
    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}])

    rc = lb.main([str(batch), "--output-dir", str(out)])

    assert rc == 0
    assert calls == []
    assert (out / "a.png").read_bytes() == b"old"
    s = _read_summary(capsys)
    assert (s["skipped"], s["success"], s["total"]) == (1, 0, 1)


def test_force_overwrites(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    monkeypatch.setattr(lb, "_generate_one", lambda *a, **k: b"new")
    out = tmp_path / "out"
    out.mkdir()
    (out / "a.png").write_bytes(b"old")
    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}])

    rc = lb.main([str(batch), "--output-dir", str(out), "--force"])

    assert rc == 0
    assert (out / "a.png").read_bytes() == b"new"
    assert _read_summary(capsys)["success"] == 1


def test_one_failure_does_not_abort_batch(tmp_path, capsys, monkeypatch):
    """一张 429 不该毁掉 50 张的批次；部分失败退 2。"""
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")

    def flaky(prompt, **kwargs):
        if "boom" in prompt:
            raise RuntimeError("HTTP 429")
        return b"png"

    monkeypatch.setattr(lb, "_generate_one", flaky)
    out = tmp_path / "out"
    out.mkdir()
    batch = _batch(tmp_path, [
        {"name": "a", "filename": "a.png", "prompt": "ok"},
        {"name": "b", "filename": "b.png", "prompt": "boom"},
        {"name": "c", "filename": "c.png", "prompt": "ok"},
    ])

    rc = lb.main([str(batch), "--output-dir", str(out)])

    assert rc == 2
    s = _read_summary(capsys)
    assert (s["total"], s["success"], s["failed"]) == (3, 2, 1)
    assert "b" in json.dumps(s["failed_assets"])
    assert (out / "c.png").exists()      # 失败之后仍继续跑完


def test_all_failed_exits_1(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")

    def always_fail(prompt, **kwargs):
        raise RuntimeError("nope")

    monkeypatch.setattr(lb, "_generate_one", always_fail)
    out = tmp_path / "out"
    out.mkdir()
    batch = _batch(tmp_path, [{"name": "a", "filename": "a.png", "prompt": "p"}])
    assert lb.main([str(batch), "--output-dir", str(out)]) == 1


def test_item_level_overrides_beat_defaults(tmp_path, monkeypatch):
    """asset 上的 aspect_ratio / seed 优先于 defaults。"""
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    seen = {}

    def capture(prompt, **kwargs):
        seen.update(kwargs)
        return b"png"

    monkeypatch.setattr(lb, "_generate_one", capture)
    out = tmp_path / "out"
    out.mkdir()
    batch = _batch(
        tmp_path,
        [{"name": "a", "filename": "a.png", "prompt": "p", "aspect_ratio": "4:5", "seed": 7}],
        defaults={"aspect_ratio": "1:1", "seed": 1},
    )
    lb.main([str(batch), "--output-dir", str(out)])
    assert seen["aspect_ratio"] == "4:5"
    assert seen["seed"] == 7


def test_too_many_references_is_fatal(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("LAOZHANG_API_KEY", "sk-test")
    refs = [str(tmp_path / f"r{i}.png") for i in range(lb.MAX_REFERENCES + 1)]
    batch = _batch(
        tmp_path,
        [{"name": "a", "filename": "a.png", "prompt": "p"}],
        defaults={"reference_paths": refs},
    )
    assert lb.main([str(batch), "--output-dir", str(tmp_path)]) == 1
    assert str(lb.MAX_REFERENCES) in capsys.readouterr().err
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_laozhang_backend.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'laozhang_backend'`

- [ ] **Step 3: 实现协议层**

创建 `scripts/backends/laozhang_backend.py`：

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""laozhang.ai 极简生图后端 —— generate-assets 的参考实现。

它不是 skill，是一个满足 BACKEND-PROTOCOL.md 的普通 CLI 脚本：
读 batch JSON、逐张生图、把 summary 打到 stdout 末行、按三值退码退出。

刻意不做 image-gen 那套 chain / fallback / preset / manifest —— 那是上游
SDK 的职责。本脚本只求「装了插件就能跑通全流程」。

env:
  LAOZHANG_API_KEY    必需
  LAOZHANG_BASE_URL   可选，缺省 https://api.laozhang.ai
  LAOZHANG_MODEL      可选，缺省 gemini-3.1-flash-image-preview
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

SUPPORTED_SCHEMA = 2
DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
DEFAULT_BASE_URL = "https://api.laozhang.ai"
DEFAULT_TIMEOUT_S = 180.0
# Gemini native 路径的参考图上限
MAX_REFERENCES = 14


def _generate_one(
    prompt: str,
    *,
    model: str,
    api_key: str,
    base_url: str,
    aspect_ratio: str,
    seed: "int | None",
    reference_paths: list,
    timeout_s: float,
) -> bytes:
    """生成一张图，返回图像字节。Task 5 实现。"""
    raise NotImplementedError


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(description="laozhang 极简生图后端")
    ap.add_argument("batch", help="batch JSON 路径")
    ap.add_argument("--output-dir", required=True, help="图片输出目录")
    ap.add_argument("--dry-run", action="store_true", help="只打计划，不请求不写文件")
    ap.add_argument("--force", action="store_true", help="目标文件已存在时仍重新生成")
    args = ap.parse_args(argv)

    try:
        batch = json.loads(Path(args.batch).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[fatal] batch JSON 读不了：{e}", file=sys.stderr)
        return 1

    schema = batch.get("$schema_version")
    if schema != SUPPORTED_SCHEMA:
        print(
            f"[fatal] 不认识的 batch schema_version: {schema!r}"
            f"（本后端支持 {SUPPORTED_SCHEMA}）。上游 generate-assets 可能比本后端新，"
            "升级插件或换 backend: image-gen。",
            file=sys.stderr,
        )
        return 1

    api_key = os.environ.get("LAOZHANG_API_KEY", "").strip()
    if not api_key:
        print(
            "[fatal] 缺 LAOZHANG_API_KEY。到 https://api.laozhang.ai 注册取 key 后设环境变量；"
            "或在 asset-config.yaml 里改用别的 backend。",
            file=sys.stderr,
        )
        return 1

    base_url = os.environ.get("LAOZHANG_BASE_URL") or DEFAULT_BASE_URL
    model = os.environ.get("LAOZHANG_MODEL") or DEFAULT_MODEL

    defaults = batch.get("defaults") or {}
    assets = batch.get("assets") or []
    out_dir = Path(args.output_dir)

    refs = list(defaults.get("reference_paths") or [])
    if len(refs) > MAX_REFERENCES:
        print(
            f"[fatal] reference_paths {len(refs)} 张，超过上限 {MAX_REFERENCES}。",
            file=sys.stderr,
        )
        return 1

    success = failed = skipped = 0
    failed_assets: list = []

    for asset in assets:
        name = asset.get("name") or asset.get("filename") or "?"
        filename = asset.get("filename")
        prompt = asset.get("prompt") or ""
        if not filename:
            print(f"[error] asset {name!r} 缺 filename，跳过", file=sys.stderr)
            failed += 1
            failed_assets.append({"name": name, "error": "缺 filename"})
            continue

        target = out_dir / filename

        if args.dry_run:
            print(f"  [plan] {name} → {target}")
            continue

        if target.exists() and not args.force:
            print(f"  [skip] {name}（已存在，--force 可覆盖）")
            skipped += 1
            continue

        try:
            data = _generate_one(
                prompt,
                model=model,
                api_key=api_key,
                base_url=base_url,
                aspect_ratio=asset.get("aspect_ratio") or defaults.get("aspect_ratio") or "1:1",
                seed=asset.get("seed", defaults.get("seed")),
                reference_paths=refs,
                timeout_s=DEFAULT_TIMEOUT_S,
            )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            print(f"  [ok] {name} → {target}")
            success += 1
        except Exception as e:      # 单张失败不中断整批：一张 429 不该毁掉 50 张
            print(f"  [error] {name}: {e}", file=sys.stderr)
            failed += 1
            failed_assets.append({"name": name, "error": str(e)})

    summary = {
        "total": len(assets),
        "success": success,
        "failed": failed,
        "skipped": skipped,
        "failed_assets": failed_assets,
    }
    print(json.dumps(summary, ensure_ascii=False), flush=True)

    if failed == 0:
        return 0
    if success == 0 and skipped == 0:
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_laozhang_backend.py -v`
Expected: PASS（9 passed）

- [ ] **Step 5: Commit**

```bash
git add scripts/backends/laozhang_backend.py tests/test_laozhang_backend.py
git commit -m "feat: laozhang 后端协议层（读 batch / skip / summary / 三值退码）"
```

---

### Task 5: laozhang 后端 —— Gemini native API 调用

**Files:**
- Modify: `scripts/backends/laozhang_backend.py`（导入区 + `_generate_one`）
- Test: `tests/test_laozhang_backend.py`（追加）

**Interfaces:**
- Consumes: Task 4 的 `_generate_one` 签名（保持一字不变，协议层已按它调用）
- Produces: 可真实生图的 `_generate_one`；模块级 `requests` 导入供测试 monkeypatch

- [ ] **Step 1: 写 API 层失败测试**

追加到 `tests/test_laozhang_backend.py`：

```python
class _FakeResp:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self.ok = 200 <= status < 300
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def _image_payload(b64: str = "aGk=") -> dict:
    return {"candidates": [{"content": {"parts": [{"inlineData": {"data": b64}}]}}]}


def test_generate_one_posts_gemini_native_shape(monkeypatch):
    """必须走 /v1beta/...:generateContent —— OpenAI 路径不支持多图 reference。"""
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        seen["url"] = url
        seen["headers"] = headers
        seen["body"] = json
        return _FakeResp(payload=_image_payload())

    monkeypatch.setattr(lb.requests, "post", fake_post)

    data = lb._generate_one(
        "a cat", model="gemini-3.1-flash-image-preview", api_key="sk-x",
        base_url="https://api.laozhang.ai", aspect_ratio="4:5", seed=None,
        reference_paths=[], timeout_s=30.0,
    )

    assert data == b"hi"
    assert seen["url"] == (
        "https://api.laozhang.ai/v1beta/models/gemini-3.1-flash-image-preview:generateContent"
    )
    assert seen["headers"]["Authorization"] == "Bearer sk-x"
    cfg = seen["body"]["generationConfig"]
    assert cfg["imageConfig"]["aspectRatio"] == "4:5"
    assert "seed" not in cfg          # seed 为 None 时不该出现在请求里
    parts = seen["body"]["contents"][0]["parts"]
    assert parts[-1]["text"] == "a cat"


def test_generate_one_inlines_references_before_prompt(tmp_path, monkeypatch):
    """参考图以 inline_data 排在 prompt 之前。"""
    ref = tmp_path / "anchor.png"
    ref.write_bytes(b"\x89PNG-fake")
    seen = {}

    def fake_post(url, headers=None, json=None, timeout=None, **kw):
        seen["body"] = json
        return _FakeResp(payload=_image_payload())

    monkeypatch.setattr(lb.requests, "post", fake_post)

    lb._generate_one(
        "a cat", model="m", api_key="k", base_url="https://x",
        aspect_ratio="1:1", seed=42, reference_paths=[str(ref)], timeout_s=30.0,
    )

    parts = seen["body"]["contents"][0]["parts"]
    assert "inline_data" in parts[0]
    assert parts[0]["inline_data"]["mime_type"] == "image/png"
    assert parts[-1]["text"] == "a cat"
    assert seen["body"]["generationConfig"]["seed"] == 42


def test_generate_one_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(
        lb.requests, "post",
        lambda *a, **k: _FakeResp(status=429, text="rate limited"),
    )
    with pytest.raises(RuntimeError) as ei:
        lb._generate_one(
            "p", model="m", api_key="k", base_url="https://x",
            aspect_ratio="1:1", seed=None, reference_paths=[], timeout_s=5.0,
        )
    assert "429" in str(ei.value)


def test_generate_one_raises_when_no_image_in_response(monkeypatch):
    """只回了文字没回图 —— 不能当成功。"""
    monkeypatch.setattr(
        lb.requests, "post",
        lambda *a, **k: _FakeResp(
            payload={"candidates": [{"content": {"parts": [{"text": "sorry"}]}}]}
        ),
    )
    with pytest.raises(RuntimeError) as ei:
        lb._generate_one(
            "p", model="m", api_key="k", base_url="https://x",
            aspect_ratio="1:1", seed=None, reference_paths=[], timeout_s=5.0,
        )
    assert "没有图像" in str(ei.value)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_laozhang_backend.py -k generate_one -v`
Expected: FAIL — `AttributeError: module 'laozhang_backend' has no attribute 'requests'`

- [ ] **Step 3: 实现 `_generate_one`**

在 `laozhang_backend.py` 顶部导入区加入（`import argparse` 之前放 `import base64`，第三方 `import requests` 单独一组）：

```python
import base64

import requests
```

把 Task 4 里抛 `NotImplementedError` 的 `_generate_one` 整体替换为：

```python
def _generate_one(
    prompt: str,
    *,
    model: str,
    api_key: str,
    base_url: str,
    aspect_ratio: str,
    seed: "int | None",
    reference_paths: list,
    timeout_s: float,
) -> bytes:
    """生成一张图，返回图像字节。

    走 Gemini native 路径而非 OpenAI style：后者不支持多图 reference，
    而 reference_paths（风格锚）是 generate-assets 的核心能力。
    """
    url = f"{base_url.rstrip('/')}/v1beta/models/{model}:generateContent"

    parts: list = []
    for p in reference_paths:
        ref = Path(p)
        mime = "image/png" if str(ref).lower().endswith(".png") else "image/jpeg"
        parts.append({"inline_data": {
            "mime_type": mime,
            "data": base64.b64encode(ref.read_bytes()).decode(),
        }})
    parts.append({"text": prompt})

    generation_config: dict = {
        "responseModalities": ["TEXT", "IMAGE"],
        "imageConfig": {"aspectRatio": aspect_ratio},
    }
    if seed is not None:
        generation_config["seed"] = seed

    try:
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"contents": [{"role": "user", "parts": parts}],
                  "generationConfig": generation_config},
            timeout=timeout_s,
        )
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"请求失败：{e}") from e

    if not resp.ok:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")

    try:
        data = resp.json()
    except ValueError as e:
        raise RuntimeError(f"响应不是合法 JSON：{e}") from e

    for cand in data.get("candidates") or []:
        for part in (cand.get("content") or {}).get("parts") or []:
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                return base64.b64decode(inline["data"])

    raise RuntimeError("响应里没有图像数据（可能被安全策略拦了，或模型只回了文字）")
```

- [ ] **Step 4: 跑全套测试**

Run: `python -m pytest tests/ -v`
Expected: PASS（全绿）

- [ ] **Step 5: Commit**

```bash
git add scripts/backends/laozhang_backend.py tests/test_laozhang_backend.py
git commit -m "feat: laozhang 后端接 Gemini native 生图接口"
```

---

### Task 6: 协议文档与既有文档更新

**Files:**
- Create: `BACKEND-PROTOCOL.md`（在 `skills/generate-assets/` 下）
- Modify: `SKILL.md`（frontmatter 依赖段 + 正文）
- Modify: `examples/README.md`
- Modify: 仓库根 `README.md`（约 105 行）

**Interfaces:**
- Consumes: Task 1–5 的全部产物（文档描述的就是它们的实际行为）
- Produces: 无代码接口

- [ ] **Step 1: 写 `BACKEND-PROTOCOL.md`**

创建 `skills/generate-assets/BACKEND-PROTOCOL.md`：

````markdown
# 生图后端协议

generate-assets 自己不生图。它把 asset 列表翻译成 batch JSON，然后 subprocess
调用一个**后端脚本**。任何满足本协议的可执行 Python 脚本都能当后端 —— 后端
不是 skill，不需要 SKILL.md，Claude 不会单独触发它。

## 调用约定

```
python <backend.py> <batch.json> --output-dir <dir> [--dry-run] [--force]
```

- `--dry-run`：只打印计划，不发请求、不写文件
- `--force`：目标文件已存在时仍重新生成（缺省则计入 skipped）

当前实现用 `sys.executable` 拼命令行，因此后端**必须是 Python 脚本**。

## 输入：batch JSON

```json
{
  "$schema_version": 2,
  "defaults": {"aspect_ratio": "1:1", "seed": 123, "reference_paths": ["/abs/anchor.png"]},
  "assets": [{"name": "red_bean", "filename": "red_bean.png", "prompt": "..."}]
}
```

- `assets[].name` / `filename` / `prompt` 必有；`aspect_ratio` / `seed` 为 item 级覆盖，优先于 `defaults`
- `reference_paths` 已是绝对路径，后端不必处理 `res://` 等引擎前缀
- 后端应校验 `$schema_version`，不认识的版本直接报错，不要猜
- 后端忽略不认识的 `defaults` 字段即可；告警由上层基于能力声明发出

## 输出：stdout 末行 JSON

```json
{"total": 12, "success": 10, "failed": 1, "skipped": 1}
```

四个字段必需，必须是 stdout 最后一行。可选 `failed_assets` / `manifest`。

## 退出码

| 码 | 含义 |
|---|---|
| 0 | 全成功（含全部 skipped） |
| 1 | 全失败 |
| 2 | 部分失败 |

非 dry-run 时若拿不到 summary，上层即便见到退码 0 也判失败。

## 最小骨架

```python
#!/usr/bin/env python3
import argparse, json, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("batch")
ap.add_argument("--output-dir", required=True)
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--force", action="store_true")
args = ap.parse_args()

batch = json.loads(Path(args.batch).read_text(encoding="utf-8"))
if batch.get("$schema_version") != 2:
    print(f"[fatal] 不支持的 schema: {batch.get('$schema_version')}", file=sys.stderr)
    sys.exit(1)

out = Path(args.output_dir)
assets = batch.get("assets") or []
success = failed = skipped = 0
for a in assets:
    target = out / a["filename"]
    if args.dry_run:
        print(f"  [plan] {a['name']} -> {target}")
        continue
    if target.exists() and not args.force:
        skipped += 1
        continue
    try:
        target.write_bytes(your_image_api(a["prompt"]))   # 换成你的生图调用
        success += 1
    except Exception as e:
        print(f"  [error] {a['name']}: {e}", file=sys.stderr)
        failed += 1

print(json.dumps({"total": len(assets), "success": success,
                  "failed": failed, "skipped": skipped}))
sys.exit(0 if failed == 0 else (1 if success == 0 and skipped == 0 else 2))
```

## 接上自己的后端

```yaml
backend: tools/my_backend.py    # 相对路径以 project_root 为基准
```

也可以用 `IMAGE_GEN_SCRIPT=<路径>` 环境变量临时覆盖（优先级最高）。

## 内置后端

| 名字 | 脚本 | 说明 |
|---|---|---|
| `image-gen` | `~/.claude/skills/image-gen/scripts/generate_image.py` | 缺省。多 provider、chain fallback、preset、manifest。需单独安装 |
| `laozhang` | 插件内 `scripts/backends/laozhang_backend.py` | 随插件走。单 provider、串行、无 chain/preset。需 `LAOZHANG_API_KEY` |
````

- [ ] **Step 2: 改 `SKILL.md`**

frontmatter 里把 `**依赖**：底层 SDK image-gen（subprocess 调用）` 改为：

```
  **依赖**：一个生图后端（subprocess 调用）。缺省 image-gen（需单独安装），
  插件自带 laozhang 极简后端可直接用，也可接自定义脚本，协议见 BACKEND-PROTOCOL.md
```

正文「核心定位」里 `subprocess 调用底层 SDK 批量生成` 改为 `subprocess 调用生图后端批量生成`，并在「何时用」表格后新增一节：

```markdown
## 生图后端

本 skill 不自己生图，它把 asset 列表翻译成 batch JSON 后调用一个**后端脚本**。

| backend | 来源 | 何时用 |
|---|---|---|
| `image-gen`（缺省） | 用户级 skill，需单独安装 | 要 chain fallback / preset / manifest |
| `laozhang` | 随插件安装 | 装了插件就想直接跑；需 `LAOZHANG_API_KEY` |
| 脚本路径 | 自己写 | 接本地 ComfyUI、公司内部 API 等 |

在 asset-config.yaml 里与 `adapter:` 平行声明：

    backend: laozhang

后端是普通 CLI 脚本，不是 skill。写一个只需满足三条约定，见 BACKEND-PROTOCOL.md。
```

- [ ] **Step 3: 改 `examples/README.md`**

顶层字段说明表里加入一行：

```markdown
| `backend` | string | 生图后端：`image-gen`（缺省） / `laozhang` / 脚本路径。见 BACKEND-PROTOCOL.md |
```

并把开头 `底层调用 image-gen SDK` 改为 `底层调用生图后端（缺省 image-gen）`。

- [ ] **Step 4: 改仓库根 `README.md`**

把 `- \`generate-assets\` 依赖 \`image-gen\` skill（底层生图 SDK，需单独安装）` 改为：

```markdown
- `generate-assets` 需要一个生图后端：缺省用 `image-gen` skill（需单独安装），
  插件自带 `laozhang` 极简后端可直接用（设 `LAOZHANG_API_KEY` 即可），
  也可以接自己的脚本 —— 协议见 `skills/generate-assets/BACKEND-PROTOCOL.md`
```

- [ ] **Step 5: 端到端手动验证（不花钱）**

```bash
python scripts/generate_assets.py --config examples/milk-tea-defense.yaml list
```
Expected: 列出 category，无 traceback

- [ ] **Step 6: 跑全套测试**

Run: `python -m pytest tests/ -v`
Expected: PASS（全绿）

- [ ] **Step 7: Commit**

```bash
git add BACKEND-PROTOCOL.md SKILL.md examples/README.md ../../README.md
git commit -m "docs: 生图后端协议文档与依赖说明更新"
```

---

### Task 7: 发布 3.9.0

**Files:**
- Modify: `.claude-plugin/plugin.json`（version 一处）
- Modify: `.claude-plugin/marketplace.json`（version 两处）
- Modify: `CHANGELOG.md`
- Modify: `PLANNED.md`（若其中记的是本次范围，清掉已完成条目）

**Interfaces:**
- Consumes: Task 1–6 的改动均已提交
- Produces: v3.9.0 tag

- [ ] **Step 1: 改三处版本号**

```bash
grep -n '"version"' .claude-plugin/plugin.json .claude-plugin/marketplace.json
```
把 `3.8.0` 改为 `3.9.0` —— plugin.json 一处、marketplace.json 两处，一个都不能漏。

- [ ] **Step 2: 补 CHANGELOG 条目**

在 `CHANGELOG.md` 顶部按既有格式加入 `## 3.9.0` 段落，写明：可插拔生图后端、插件自带 laozhang 极简后端、新增 BACKEND-PROTOCOL.md、缺省仍为 image-gen 因此升级无行为变化。

标题格式必须是 `## 3.9.0` —— `verify_release.py` 靠它定位最新段。

- [ ] **Step 3: Commit（与内容生成分两条命令跑，不要用 && 串）**

```bash
git add .claude-plugin/plugin.json .claude-plugin/marketplace.json CHANGELOG.md PLANNED.md
git commit -m "chore: bump version to 3.9.0"
```

- [ ] **Step 4: 发布自检（打 tag 之前）**

Run: `python scripts/verify_release.py --version 3.9.0`
Expected: 退码 0。非 0 就停下来修，别往下走 —— 它查的是 commit 里的内容，不是工作区

- [ ] **Step 5: 打 tag 并推送**

```bash
git tag -a v3.9.0 -m "可插拔生图后端"
git push origin main --follow-tags
```

- [ ] **Step 6: 对齐 marketplace 镜像**

```bash
M=~/.claude/plugins/marketplaces/game-toolkit
git -C "$M" fetch origin main
git -C "$M" reset --hard origin/main
```
不要用 `git pull` —— 那个镜像是 shallow clone，会报 refusing to merge unrelated histories。

- [ ] **Step 7: 验证新版本可加载**

重启 Claude Code 或跑 `/plugin update game-toolkit`，确认运行时缓存出现 `3.9.0` 目录。
