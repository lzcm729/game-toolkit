---
name: generate-assets
description: |
  schema-driven 批量资源生成。读项目 asset-config.yaml → 加载数据源 → 渲染 prompt
  → 调底层 image-gen SDK 批量生成 → 写到项目的资源目录。
  核心流程引擎无关；引擎相关的部分（虚拟路径前缀、导入检查）在适配层，
  当前提供 Godot 适配，其他引擎走 generic（普通相对路径、不做导入检查）。

  **触发条件**：
  - 项目根存在 `asset-config.yaml`（或 `assets/asset-config.yaml`）
  - 用户要求"批量生成 asset"、"生成 art"、"按 yaml 跑 batch"

  **不适用**：
  - 即兴单张生图 → 用 image-gen
  - 项目里没 asset-config.yaml → 用 image-gen 单张或先建 yaml
  - 单张即兴生图（用 image-gen）

  **依赖**：底层 SDK image-gen（subprocess 调用）
---

# generate-assets — schema-driven 批量资源生成

把项目 asset 列表 / 数据源 / prompt 模板放在一份 `asset-config.yaml` 里，
本框架翻译成 image-gen v2 batch JSON 后 subprocess 调用底层 SDK 批量生成。

**核心定位**：yaml → batch JSON 翻译器 + image-gen 调度器 + 引擎适配层。
所有项目特化（风格、prompt 模板、数据源映射、category 列表）都在 yaml 里，
本 skill 的 Python 代码不含任何项目硬编码。

## 何时用

| 场景 | 用什么 |
|---|---|
| 单张即兴生图 | 直接 `image-gen` |
| 批量生成（5+ asset） | **本 skill** |
| 项目根存在 `asset-config.yaml` | **本 skill** |
| 三状态 schema（item/character/background，旧版特化） | 已由具体项目 fork 为项目内 skill 维护，本通用 framework 不再支持 |

## 快速使用

```bash
# 脚本随插件安装。用 Skill 工具调用本 skill 后，按告知的 base directory 定位；
# 或在插件目录下取 skills/generate-assets/scripts/generate_assets.py
SKILL="<本 skill 目录>/scripts/generate_assets.py"

# 列出 config 里所有 category
python "$SKILL" list

# 跑单个 category（dry-run 看 prompt 不调 API）
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
│   ├── generate_assets.py              # 主入口（CLI + 主流程）
│   ├── data_source.py                  # 数据源加载（json_dict / json_list / inline）+ filter
│   ├── prompt_render.py                # 模板 format + derived_fields mini DSL
│   ├── engine_adapter.py              # 引擎适配：路径前缀 / 工程根探测 / 生成后检查
│   └── godot_utils.py                  # Godot 适配的实现（res:// / project.godot / .import）
├── examples/
│   ├── README.md                       # asset-config.yaml schema 文档
│   └── milk-tea-defense.yaml           # 完整示例（5 category）
└── tests/                              # unit tests
```

## asset-config.yaml schema

完整字段表 / 数据源 type / derived DSL 见 `examples/README.md`。最小骨架：

```yaml
$schema_version: 1
style:
  prompt_prefix: "Cute chibi sticker style, transparent background."
  prompt_suffix: "Warm caramel palette."
output_root: "res://art"
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

## 引擎适配

config 里的 `engine` 字段选适配，未声明则探测（找到 `project.godot` → `godot`，否则 `generic`）：

| engine | 路径前缀 | 工程根探测 | 生成后 |
|---|---|---|---|
| `godot` | 认 `res://`（＝工程根） | 找 `project.godot` | 扫 `.import`，提示未导入的图片 |
| `generic` | 不认任何引擎前缀，写了 `res://` / `/Game/` 会**报错** | 无，用 yaml 位置推断 | 不检查 |

UE / Unity 项目现在用 `generic` 就能跑通生成流程 —— 只是没有虚拟路径解析和导入检查。
要加这两样，在 `engine_adapter.py` 里加一个 `EngineAdapter` 实例并注册即可，主流程不用动。

### Godot 适配的细节

- **`res://` 路径**：`output_root: "res://art"` ↔ `<project_root>/art`
- **自动 mkdir -p** 子目录（image-gen 不建多层目录）
- **`.import` 扫描**：跑完后统计哪些图缺 `.import`，提示"用 Godot 编辑器自动 import"
- **`project.godot` 检测**：缺则 warn 但仍跑（按 yaml 父目录推根）

## 退码 + summary

沿用 image-gen 的 `0/1/2`：
- `0` — 全成功（含 skipped）
- `1` — 全失败
- `2` — 部分失败

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
