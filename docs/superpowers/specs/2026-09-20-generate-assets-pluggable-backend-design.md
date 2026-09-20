# generate-assets 可插拔生图后端

日期：2026-09-20
状态：已评审，待实现
目标版本：3.9.0

## 背景

`generate-assets` 通过 subprocess 调用 `~/.claude/skills/image-gen/scripts/generate_image.py`
完成实际生图。代码层面这个依赖处理得不差 —— `_resolve_image_gen()` 会 fail-fast 并打印
怎么装、怎么用 `IMAGE_GEN_SCRIPT` 指路，还有两条测试覆盖，README 也声明了「需单独安装」。

真正的问题是**装不了**：`image-gen` 是作者的用户级 skill（`~/.claude/skills/image-gen/`，
873K），不在任何 git 仓库里，没有发布形态。对插件使用者而言，`generate-assets` 是一个
永远无法满足的依赖 —— 报错信息再清楚，也指向一个他们拿不到的东西。

依赖面本身很薄：一次 subprocess 调用 + batch JSON 输入 + 末行 JSON summary + 三值退码。
这已经是一个事实上的协议，只是从未被写成文档，也从未允许第二个实现。

## 目标

1. 把隐式协议显式化为文档契约，任何满足契约的可执行脚本都能作为后端
2. 插件自带一个可直接跑的参考后端，装了插件就能完成全流程
3. 作者本机现有行为一字不变（默认仍是 image-gen）

## 非目标

- 不把 image-gen 整体 vendored 进插件（873K，且它有独立于本插件的用途）
- 不在参考后端里复刻 image-gen 的 chain / fallback / preset / manifest
- 不支持非 Python 后端（见「已决取舍」第 3 条）
- 不做后端自动探测（见「已决取舍」第 1 条）

## 插拔的单位是什么

**不是 skill，是「一个可执行脚本 + 一套 CLI 约定」。**

`generate_assets.py` 从未「调用 image-gen 这个 skill」，它调的是一个文件路径，
经由 `subprocess.run([sys.executable, <script>, <batch.json>, "--output-dir", ...])`。
整个过程发生在 Claude 之外；Python 不知道什么是 skill。

image-gen 之所以是 skill，是因为它有双重身份，而本框架只用其中一半：

| 身份 | 消费者 | 入口 |
|---|---|---|
| 一个 skill | Claude（即兴单张生图时） | `skill.md` |
| 一个 CLI 程序 | generate-assets 的 Python 代码 | `scripts/generate_image.py` |

因此后端注册表里存的是脚本路径，它不关心那个路径背后是不是 skill。
内置的 `laozhang` 后端就是插件 `scripts/backends/` 下一个普通 Python 文件，
与 `data_source.py`、`prompt_render.py` 同级，没有 SKILL.md，Claude 不会单独触发它。

## 后端协议

### 调用约定

```
python <backend.py> <batch.json> --output-dir <dir> [--dry-run] [--force]
```

- `--dry-run`：只打印计划，不发起任何 API 请求，不写文件
- `--force`：目标文件已存在时仍重新生成（缺省则计入 skipped）

### 输入：batch JSON

```json
{
  "$schema_version": 2,
  "defaults": {
    "chain": "default",
    "preset": "...",
    "aspect_ratio": "1:1",
    "seed": 12345,
    "reference_paths": ["/abs/path/anchor.png"]
  },
  "assets": [
    {
      "name": "red_bean",
      "filename": "red_bean.png",
      "prompt": "...",
      "aspect_ratio": "4:5",
      "seed": 999
    }
  ]
}
```

- `defaults` 全部字段可选；后端应忽略不认识的字段并继续；按 category 的告警由上层基于 `supports` 声明发出（见「降级告警」），后端自身不得因此中断
- `assets[].name` / `filename` / `prompt` 必有；`aspect_ratio` / `seed` 为 item 级覆盖，优先于 defaults
- `reference_paths` 已由上层解析为绝对路径，后端不必再处理 `res://` 等引擎前缀
- 后端应校验 `$schema_version`：不认识的版本直接报错退出，不要猜

### 输出：stdout 末行 JSON summary

```json
{"total": 12, "success": 10, "failed": 1, "skipped": 1}
```

- **必需字段**：`total` / `success` / `failed` / `skipped`（上层目前只消费这四个）
- 可选字段：`failed_assets`（失败项清单，对人排查有用）、`manifest`（清单文件路径）
- summary 必须是 stdout 的最后一行；其余输出可自由打印

### 退出码

| 码 | 含义 |
|---|---|
| 0 | 全成功（含全部 skipped） |
| 1 | 全失败 |
| 2 | 部分失败 |

上层的既有约束：非 dry-run 时若拿不到 summary，即便退码为 0 也判定为失败
（「没有 summary 就无法确认产物」）。

## 组件设计

### 新增

| 文件 | 职责 |
|---|---|
| `scripts/image_backend.py` | 后端注册表与选择，结构逐条对称 `engine_adapter.py` |
| `scripts/backends/laozhang_backend.py` | 极简参考后端，独立 CLI，可脱离 generate-assets 单跑 |
| `BACKEND-PROTOCOL.md` | 上节协议的面向实现者版本，含一个最小骨架示例 |

### 修改

| 文件 | 改动 |
|---|---|
| `scripts/generate_assets.py` | `_resolve_image_gen()` → `image_backend.select()`；`_invoke_image_gen()` → `_invoke_backend()`；新增降级告警 |
| `SKILL.md` | 依赖段：从「依赖 image-gen」改为「需要一个生图后端，默认 image-gen，插件自带 laozhang」 |
| `README.md`（约 105 行） | 同上 |
| `examples/README.md` | 补 `backend` 字段说明 |

### `ImageBackend` 结构

照 `EngineAdapter` 的形状（frozen dataclass + Callable 字段 + 注册表）：

```python
@dataclass(frozen=True)
class ImageBackend:
    name: str
    resolve_script: Callable[[], Path | None]   # 找不到返回 None
    supports: frozenset[str]                    # 认得的 defaults 字段
    install_hint: str                           # 找不到时怎么装

BACKENDS = {"image-gen": IMAGE_GEN, "laozhang": LAOZHANG}
```

- `IMAGE_GEN.supports` = `{chain, preset, reference_paths, aspect_ratio, seed}`
- `LAOZHANG.supports` = `{reference_paths, aspect_ratio, seed}`

两个条目是同构的，都只是「一个脚本路径」：前者指向外部用户级 skill 内的脚本（可能不存在），
后者指向插件自身目录内的脚本（随插件走，必定存在）。

### 选择优先级

```
1. IMAGE_GEN_SCRIPT 环境变量   → 匿名自定义后端（向后兼容，保持最高优先级）
2. config 的 backend: 字段     → 注册名，或含 "/" 或以 ".py" 结尾的脚本路径
3. 缺省                        → image-gen
```

路径形式的 `backend`：绝对路径原样使用；相对路径以 **project_root** 为基准解析 —— 与 `output_root` 的基准一致，而非相对 config 所在目录或当前工作目录。

yaml 中与既有 `adapter:` 平行：

```yaml
adapter: godot          # 已有：引擎适配
backend: image-gen      # 新增：生图后端
```

未知名字的报错须列出已注册后端，照 `engine_adapter._generic_resolve` 的文案风格 ——
只说「不认识」而不给可选项，人还得去翻源码。

### 降级告警

在 `_build_batch_json` 产出 defaults 之后、调用后端之前，逐条比对 `supports`：

```
[warn] category=customers: backend=laozhang 不支持 chain（值 "default"），已忽略。
       风格链/预设是 image-gen 特有能力，切回 backend: image-gen 才生效。
```

按 category 报告，且必须带上被丢弃的值 —— 只说「不支持 chain」，人还得回头翻 yaml
才知道丢了什么。

## 极简后端规格

`scripts/backends/laozhang_backend.py`，约 130 行，仅依赖 `requests`。

- **走 Gemini native 路径**（`{base}/v1beta/models/{model}:generateContent`）。
  这是硬约束：laozhang 的 OpenAI style 路径不支持多图 reference，而 `reference_paths`
  （风格锚）是 generate-assets 的核心能力，examples 里就在用。
- 认证：`LAOZHANG_API_KEY`；`LAOZHANG_BASE_URL` 可选，缺省 `https://api.laozhang.ai`
- 模型：缺省 `gemini-3.1-flash-image-preview`，`LAOZHANG_MODEL` 可换
  `gemini-3-pro-image-preview`
- reference 上限 14 张，超出报错
- 请求体形如 `{"contents": [{"role": "user", "parts": [...]}], "generationConfig": {...}}`，
  参考图以 `inline_data`（base64）随 parts 提交，`generationConfig.imageConfig.aspectRatio`
  传宽高比，`seed` 非 None 时透传
- 响应从 `candidates[].content.parts[].inlineData.data` 取 base64 图像数据

行为：

- 目标文件已存在且未给 `--force` → 计入 skipped，不发请求
- 单张失败记入 `failed_assets` 后继续，**不中断整批**（一张 429 不该毁掉 50 张的批次）
- `--dry-run` 只打计划
- 缺 `LAOZHANG_API_KEY` 时退码 1，提示给出注册入口与环境变量名 ——
  这是新用户第一个会撞上的墙，与当前 image-gen 缺失的处理同等对待

## 错误处理

| 情形 | 行为 |
|---|---|
| 后端脚本不存在 | fail-fast，打印该后端的 `install_hint`（沿用现有机制，按后端定制文案） |
| `backend:` 是未知名字 | 报错并列出已注册后端 |
| defaults 含后端不支持的字段 | 告警后继续（见「降级告警」） |
| 后端缺 API key | 后端自身退码 1 并给出配置指引 |
| 单张生成失败 | 记入 `failed_assets`，继续本批 |
| 非 dry-run 且无 summary | 判失败（既有行为，保持） |

## 测试

| 文件 | 覆盖 |
|---|---|
| `tests/test_image_backend.py`（新） | 选择优先级三档、路径式 backend、未知名字报错文案含已注册列表、`supports` 告警触发与文案含被丢弃的值 |
| `tests/test_laozhang_backend.py`（新） | batch 解析、`$schema_version` 校验、skip/force、summary 字段完整、退码 0/1/2 三值、单张失败不中断。**mock `requests`，不打真 API** |
| `tests/test_main_flow.py`（改） | 既有两条 `test_missing_image_gen_*` 改为后端无关语义 |

## 已决取舍

1. **不做后端自动探测。** 「发现 image-gen 就用它，否则退到 laozhang」会让同一份 yaml
   在不同机器上产出不同风格的图且不报错。这种静默分叉比一条硬错误难查得多。
   代价是新用户要显式改一行 yaml，换来行为可预期。

2. **不支持后端能力的自动降级。** 遇到 `chain` / `preset` 只告警不改写 prompt ——
   试图用别的手段「模拟」风格链会产出看起来对、实则不同的结果。

3. **后端限定为 Python 脚本。** 现有实现用 `sys.executable` 拼命令行。subprocess 边界
   本可容纳 bash / Node / 二进制，但支持它们需要加可执行性探测。按 YAGNI 保持
   Python-only 并在协议文档中写明，等真有需求再放开。

4. **参考后端不写 manifest。** 上层只消费 summary 的 `total/success/failed/skipped`
   四个字段，manifest 与 failed_assets 均未被读取。

## 发布

按 CLAUDE.md 的开发回路走 3.9.0（新增能力，非破坏性）：

1. 改 `plugin.json` 一处 + `marketplace.json` 两处版本号
2. 补 CHANGELOG 条目
3. 内容生成与 git 操作分两条命令跑
4. `python scripts/verify_release.py --version 3.9.0` 校验 commit（退码非 0 不得继续）
5. tag + push `--follow-tags`
6. 把 marketplace 镜像 `fetch` + `reset --hard origin/main` 对齐
