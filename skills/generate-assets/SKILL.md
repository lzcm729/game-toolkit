---
name: generate-assets
description: |
  schema-driven 批量资源生成。读项目 asset-config.yaml → 加载数据源 → 渲染 prompt
  → 调生图后端批量生成 → 写到项目的资源目录。
  核心流程引擎无关；引擎相关的部分（虚拟路径前缀、导入检查）在适配层，
  当前提供 Godot 适配，其他引擎走 generic（普通相对路径、不做导入检查）。

  **触发条件**：
  - 项目根存在 `asset-config.yaml`（或 `assets/asset-config.yaml`）
  - 用户要求"批量生成 asset"、"生成 art"、"按 yaml 跑 batch"

  **不适用**：
  - 即兴单张生图 → 用 image-gen
  - 项目里还没有 asset-config.yaml → 用 asset-config skill 把它建起来
  - 配置写坏了 / 改完想确认 → 用 asset-config 的 check

  **依赖**：一个生图后端（subprocess 调用）。缺省 image-gen（需单独安装），
  插件自带 laozhang 极简后端可直接用，也可接自定义脚本，协议见 BACKEND-PROTOCOL.md
---

# generate-assets — schema-driven 批量资源生成

把项目 asset 列表 / 数据源 / prompt 模板放在一份 `asset-config.yaml` 里，
本框架翻译成 v2 batch JSON 后 subprocess 调用生图后端批量生成。

**核心定位**：yaml → batch JSON 翻译器 + 后端调度器 + 引擎适配层。
所有项目特化（风格、prompt 模板、数据源映射、category 列表）都在 yaml 里，
本 skill 的 Python 代码不含任何项目硬编码。

## 何时用

| 场景 | 用什么 |
|---|---|
| 单张即兴生图 | 直接 `image-gen` |
| 批量生成（5+ asset） | **本 skill** |
| 项目根存在 `asset-config.yaml` | **本 skill** |
| 三状态 schema（item/character/background，旧版特化） | 已由具体项目 fork 为项目内 skill 维护，本通用 framework 不再支持 |

## 生图后端

本 skill 不自己生图，它把 asset 列表翻译成 batch JSON 后调用一个**后端脚本**。
后端是普通 CLI 脚本，不是 skill —— 注册表存的是脚本路径，不关心背后是不是 skill。

| backend | 来源 | 何时用 |
|---|---|---|
| `image-gen`（缺省） | 用户级 skill，需单独安装 | 要 chain fallback / preset / manifest |
| `laozhang` | 随插件安装 | 装了插件就想直接跑；需 `LAOZHANG_API_KEY` |
| 脚本路径 | 自己写 | 接本地 ComfyUI、公司内部 API 等 |

在 asset-config.yaml 里与 `adapter:` 平行声明：

```yaml
backend: laozhang
model: gemini-3-pro-image      # 可选，category 可覆盖
```

`model` 是后端配置不是风格，所以放顶层而非 `style:` 段 —— 放 style 里会被
`skip_global_style` 连带关掉。image-gen 用 `chain:` 表达模型选择，配了 `model:`
会**报错**并指向 `chain:`（3.20.0 起；丢掉指定的模型仍然出得来图，但那不是
你要的那件事）。

## 两种输入模式

| 模式 | yaml 字段 | 含义 |
|---|---|---|
| 风格参考 | `style.reference_paths` / category 的 `reference_paths` | 参考这些图的风格，重新画一张 |
| 编辑底图 | category 或 item 的 `image` | 编辑这张图，保住构图 |

两者**互斥**，同时给会 fail fast。要「同一底图批量出变体」（四季版、角色的
不同状态）用 `image`；要「一套风格贯穿全部资源」用 `reference_paths`。

后端不支持的字段（如 laozhang 不认 `chain` / `preset`）默认**阻止执行**并点名
是哪个 category、哪个条目、丢掉的是什么值。要临时跑一次加 `--allow-degrade`，
它把这类错降回告警。`seed` 例外 —— 它只影响可复现性，不影响画的是什么，
丢了照旧只告警。`check_config.py` 有同名开关，两边判断一致。

自定义后端（脚本路径 / `IMAGE_GEN_SCRIPT`）的能力**未知**：既不报降级也不假装
查过，只在开头说一句。写一个后端只需满足几条约定，见 BACKEND-PROTOCOL.md。

## 调用前：把工程根接上

本脚本是独立 CLI，**不读 `game-toolkit.yaml`** —— 那是 agent 侧的事实源。
所以 agent 调它之前要先桥接：

1. 读项目声明拿到 `project_root`（`../layer-contracts/scripts/project_env.py check`，相对**本 skill 目录** —— 它是兄弟 skill，不在本目录下）
2. 解析成绝对路径，用 `--project-root` 传给本脚本
   （声明还没有、但本次任务已经明确给了工程根 → 直接用任务给的，回报里标明来源；**不要替项目写声明** —— 那是主流程 check → 问人 → write 的事）

不做这一步、又把 `asset-config.yaml` 放在子目录（如 `tools/`）时，脚本只能按
config 位置推断工程根 —— 推出来的会是 `tools/`，相对路径全部错基准。
让用户在两处重复声明不是解法，桥接一步就够。

## 快速使用

```bash
# 脚本随插件安装。用 Skill 工具调用本 skill 后，按告知的 base directory 定位；
# 或在插件目录下取 skills/generate-assets/scripts/generate_assets.py
SKILL="<本 skill 目录>/scripts/generate_assets.py"

# 列出 config 里所有 category
python "$SKILL" list

# 跑单个 category（dry-run：打印渲染后的 prompt，不调 API）
python "$SKILL" customers --dry-run

# 跑全部 + 强制覆盖
python "$SKILL" all --force

# 只生成指定 id
python "$SKILL" customers --names student,bigEater
```

默认搜索 config 路径：`./asset-config.yaml` → `./assets/asset-config.yaml`，可
`--config <path>` 覆盖。

## 文件结构

```
generate-assets/
├── SKILL.md                            # 本文件
├── scripts/
│   ├── generate_assets.py              # 主入口：拿到计划之后落盘、调后端、汇总
│   ├── asset_context.py                # 上下文解析：定位配置 / 工程根 / 输出根 / 适配器 / 后端
│   ├── asset_plan.py                   # 生成计划：数据源 → prompt → 文件名 → 落盘位置
│   ├── data_source.py                  # 数据源加载（json_dict / json_list / inline / csv）+ filter
│   ├── prompt_render.py                # 模板 format + derived_fields mini DSL
│   ├── engine_adapter.py               # 工程探测 / 路径前缀解析 / 导入提示（三者独立）
│   ├── image_backend.py                # 后端注册表与能力声明
│   ├── backends/laozhang_backend.py    # 随插件自带的极简后端
│   └── godot_utils.py                  # Godot 适配的实现（res:// / project.godot / .import）
├── examples/
│   ├── README.md                       # asset-config.yaml schema 文档
│   └── milk-tea-defense.yaml           # 完整示例（5 category）
├── BACKEND-PROTOCOL.md                 # 生图后端协议
└── tests/                              # unit tests

前两个模块（`asset_context` / `asset_plan`）和 `asset-config` skill 的校验器
**共用** —— 校验和执行看到的是同一个计划。
```

## asset-config.yaml schema

完整字段表 / 数据源 type / derived DSL 见 `examples/README.md`。最小骨架：

```yaml
$schema_version: 1
style:
  prompt_prefix: "Cute chibi sticker style, transparent background."
  prompt_suffix: "Warm caramel palette."
output_root: "art"          # Godot 项目可写 res://art；其他引擎用普通相对路径
categories:
  ingredients:
    aspect_ratio: "1:1"
    data_source:
      type: inline
      items:
        pearl: { visual: "black tapioca pearls", main: "#1e1b4b" }
        taro:  { visual: "lavender taro chunks", main: "#4a1942" }
    prompt_template: "Icon '{id}': {visual}. Main {main}."
```

## 数据源 type（v1）

| type | 形态 | 例 |
|---|---|---|
| `json_dict` | JSON 顶层 dict，**key 当 id** | `enemy-stats.json` |
| `json_list` | JSON 顶层 list，每个 element 必含 `id` | `recipe-defs.json` |
| `inline` | yaml 内 `items` 字段，与 json_dict 同语义 | 适合 5-10 个静态条目 |

`filter` 支持 `field_len: N`（数组长度）+ `field: value`（值相等），v1 只这俩。

## derived_fields mini DSL

**只有 hardcoded helper，禁止 eval/exec**：

| DSL | 语义 |
|---|---|
| `join(field, ", ")` | `", ".join(item["field"])` |
| `upper(field)` | `str(...).upper()` |
| `lower(field)` | `str(...).lower()` |
| `title(field)` | `str(...).title()` |

新增 helper 改 `prompt_render.py:_HELPERS` 即可。

## prompt 拼接

```
{global.style.prompt_prefix} {category prompt_template 渲染} {global.style.prompt_suffix}
```

`skip_global_style: true` 跳过全局 prefix/suffix（背景图独立 prompt 场景）。

## 引擎相关的三件事

它们**互相独立**，分开处理（3.17.0 起）：

| 做什么 | 由什么决定 | 说明 |
|---|---|---|
| 工程根在哪 | **探测到的工程标志** | 向上找 `project.godot` / `*.uproject`。不问适配器 |
| 路径怎么写 | `adapter`（可声明） | `godot` 认 `res://`；`generic` 只认普通文件路径 |
| 生成后提示什么 | **探测到的工程** | Godot 扫 `.import`；Unreal 提示走一次导入 |

**换 `adapter` 不会换掉工程根**，也不会让导入提示消失 —— 那两件事跟着工程事实走。
UE 项目写 `adapter: generic`（正常默认）照样拿得到那句导入提示。

> **`adapter` 不是「项目用什么引擎」。** 引擎身份属于项目环境声明（人工填，见
> `game-toolkit:layer-contracts` 的「项目环境声明」）；这里选的只是**路径写法**。
> `generic` 表达「用普通文件路径」，不表达「这个项目没有引擎」。
>
> 旧配置的 `engine:` 按 `adapter:` 处理；两者同时存在且不同会报错。

可选的 `adapter` 只有两个：

| `adapter` | 路径前缀 |
|---|---|
| `godot` | 认 `res://`（＝工程根） |
| `generic` | 不认任何虚拟前缀；写了 `res://` / `/Game/` 会**报错** |

未声明时按探测到的工程给默认：Godot 工程 → `godot`，其余一律 `generic`。
多对一是正常的 —— 只有 Godot 需要一套自己的路径写法。

`adapter: unreal` 是**兼容值**，等价于 `generic`。它当年的三个职责在上表里都各有
归属，而「认得一种不合法输入」（`/Game/`）不足以支撑一个用户可选的适配器。
写着它的配置照样跑，只多一条提示。

要给某个引擎加虚拟路径解析，在 `engine_adapter.py` 里加一个 `EngineAdapter`
实例并注册；要加工程探测或导入提示，改 `project_kind()` / `import_hint()`。
三件事分开加，主流程不用动。

### Godot 适配的细节

- **`res://` 路径**：`output_root: "res://art"` ↔ `<project_root>/art`
- **自动 mkdir -p** 子目录（image-gen 不建多层目录）
- **`.import` 扫描**：跑完后统计哪些图缺 `.import`，提示「用 Godot 编辑器自动 import」

## 退码 + summary

沿用 image-gen 的 `0/1/2`：
- `0` — 全成功（含 skipped）
- `1` — 全失败
- `2` — 部分失败

非 dry-run 时上游没返回 summary 一律按 `1` 处理 —— 没有 summary 就无法确认产物，
退出码 0 也不算成功。

每个 category 末尾打印一行 image-gen 输出的 JSON summary，本框架再打总表：

```
=== overall summary ===
  customers      exit=0 total=6 success=6 failed=0 skipped=0
  ingredients    exit=2 total=5 success=4 failed=1 skipped=0
[godot] 11 张图片中 11 张缺 .import — 请用 Godot 编辑器打开项目让它自动 import
```

多 category 总退码取最大。

## 环境

- 依赖：`pyyaml`（其他都是标准库）
- 上游 image-gen 路径：默认 `~/.claude/skills/image-gen/scripts/generate_image.py`，
  可用 env `IMAGE_GEN_SCRIPT` 覆盖

```bash
pip install pyyaml
```

## 不做的事

- ❌ 重新实现 image-gen 的能力（chain / fallback / manifest / skip-existing 都已就绪）
- ❌ 项目特化的旧版 schema 解析（CSV / 三状态 / emotions） → 由该项目自己的 legacy 脚本负责
- ❌ 任意 Python 表达式 / jinja2（str.format + hardcoded helper 够用）
- ❌ 自动写 .tres atlas / SpriteSheet（thick-layer，未来 TODO）
- ❌ 绑定特定 model / preset 名（让 yaml chain / preset 透传）
