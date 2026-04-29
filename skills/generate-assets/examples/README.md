# asset-config.yaml — Schema 文档

`generate-assets` 的项目级配置文件。一个 yaml 描述一个 Godot 项目的所有 asset
category（顾客、配料、配方、建筑、背景……）。底层调用 image-gen SDK，本框架只
负责"yaml → batch JSON → image-gen subprocess"翻译 + 调度。

## 文件位置

默认搜索路径（按顺序）：
1. `./asset-config.yaml`（项目根）
2. `./assets/asset-config.yaml`

可用 `--config <path>` 显式指定。

## 顶层结构

```yaml
$schema_version: 1   # 当前版本
style: { ... }       # 全局风格（被所有 category 继承，可单独跳过）
output_root: "..."   # 输出根目录（接受 res:// 前缀）
categories:
  <name>: { ... }    # 一个 category
  ...
```

## `style`（全局风格）

```yaml
style:
  prompt_prefix: |
    全局前缀，每个 asset 最终 prompt 都拼这个。
  prompt_suffix: |
    全局后缀。
  reference_paths:
    - "_style/anchor.png"   # 相对 output_root；接受 res:// / 绝对路径
  chain: default            # 可选 — 透传到 image-gen defaults.chain
```

每个 asset 最终 prompt：

```
{style.prompt_prefix} {category 渲染后的 prompt_template} {style.prompt_suffix}
```

如果 category 设了 `skip_global_style: true`，只用 category 模板，不拼全局
prefix/suffix（背景图等独立 prompt 场景适用）。

## `output_root`

输出根目录，相对项目根。**支持 `res://` 前缀**，等价于剥掉前缀（项目根 =
`project.godot` 所在目录；找不到则 yaml 父目录或其父）。

```yaml
output_root: "res://art"   # = <project_root>/art
output_root: "assets/art"  # = <project_root>/assets/art
```

## `categories.<name>` 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `desc` | string | 仅供 `list` 命令显示 |
| `aspect_ratio` | string | `"1:1"` / `"4:5"` / `"9:16"` / ... 透传 image-gen |
| `output_subdir` | string | 输出子目录名（默认 = category 名） |
| `output_ext` | string | 输出扩展名（默认 `png`） |
| `data_source` | dict | 见下方"数据源 type" |
| `extra_fields` | dict | `{field: {item_id: value}}` 给数据源没有的字段补值 |
| `derived_fields` | dict | `{new_field: dsl_expr}` 见下方"derived DSL" |
| `prompt_template` | string | `str.format` 模板，占位符引用 item 字段 |
| `skip_global_style` | bool | true → 不拼全局 prefix/suffix |
| `seed` / `chain` / `preset` | misc | 透传到 image-gen `defaults` |
| `reference_paths` | list | 覆盖 global style 的内容层 ref（可选） |

## 数据源 type（v1）

### `json_dict` — 顶层 dict、key 当 id

```yaml
data_source:
  type: json_dict
  path: "docs/migration/machine-extract/enemy-stats.json"
  filter:
    weakness: pearl   # 仅取 item.weakness == "pearl"
```

JSON 形如 `{"student": {"label":"学生","color":"#fff"}, "bigEater": {...}}`，
框架把 key 注入 `id` 字段。

### `json_list` — 顶层 list、每个 element 必含 `id`

```yaml
data_source:
  type: json_list
  path: "docs/migration/machine-extract/recipe-defs.json"
  filter:
    toppings_len: 1   # 仅取 toppings 数组长度为 1
```

### `inline` — yaml 内嵌 items

```yaml
data_source:
  type: inline
  items:
    pearl:
      visual: "black pearls"
      main: "#1e1b4b"
    taro:
      visual: "taro chunks"
      main: "#4a1942"
```

key 当 id，与 json_dict 同语义。

## `data_source.filter`（v1 简单条件）

每个 (key, expected) 必须满足：

| key 形式 | 语义 |
|---|---|
| `field_len: 1` | `len(item["field"] or []) == 1` |
| `field: "value"` | `item["field"] == "value"` |

无 OR / NOT / 比较运算符（v1）。

## `derived_fields` mini DSL

**只支持 hardcoded helper，不允许任意 Python 表达式**（无 eval / exec）。

| 表达式 | 语义 |
|---|---|
| `join(field, ", ")` | `", ".join(item["field"])` |
| `upper(field)` | `str(item["field"]).upper()` |
| `lower(field)` | `str(item["field"]).lower()` |
| `title(field)` | `str(item["field"]).title()` |

例：

```yaml
derived_fields:
  toppings_str: 'join(toppings, ", ")'
  name_upper: 'upper(label)'
prompt_template: |
  Cup {label} ({id}) — toppings: {toppings_str}
```

新增 helper 必须改 `scripts/prompt_render.py` 的 `_HELPERS` dict。

## `extra_fields`（数据源里没的字段）

当 JSON 数据源缺少 visual/描述等只用于 prompt 的字段时，inline 在 yaml 里：

```yaml
extra_fields:
  visual:
    student: "young student with backpack and headphones"
    bigEater: "round chubby gourmand customer"
```

注入逻辑：item 自身已有同名字段则不覆盖；否则按 id 取 mapping。

## CLI

```bash
python generate_assets.py list                # 列出 + desc
python generate_assets.py <category>          # 单个 category
python generate_assets.py all                 # 全部
python generate_assets.py <cat> --names a,b   # 过滤 id
python generate_assets.py --dry-run           # image-gen --dry-run
python generate_assets.py --force             # 覆盖已存在
python generate_assets.py --config path.yaml  # 自定义 config
```

退码：沿用 image-gen `0/1/2`（多 category 取最大）。

## 完整示例

见 `milk-tea-defense.yaml`（5 category：customers / ingredients / recipes /
buildings / backgrounds）。

## Godot 特化

- `res://` 路径自动剥前缀，等价于相对项目根
- 跑完后扫输出目录，提示有多少 `.import` 文件缺失（用 Godot 编辑器打开自动 import）
- 输出子目录自动 `mkdir -p`（image-gen 不建多层目录）
- 检测 `project.godot`：缺则 warn"非 Godot 项目，res:// 解析按 yaml 父目录"

## 不做的事

- ❌ 不重新实现 image-gen 的能力（chain / fallback / manifest / skip-existing 都已就绪）
- ❌ 不写 .tres atlas / SpriteSheet（thick-layer TODO）
- ❌ 不绑定特定 model / preset 名（让 yaml chain / preset 透传）
- ❌ 不允许 eval / exec 任意表达式
