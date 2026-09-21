# asset-config.yaml — Schema 文档

`generate-assets` 的项目级配置文件。一个 yaml 描述一个游戏项目的所有 asset（引擎无关；Godot 有专门适配，其他引擎走 generic）
category（顾客、配料、配方、建筑、背景……）。底层调用生图后端（缺省 image-gen），
本框架只负责"yaml → batch JSON → 后端 subprocess"翻译 + 调度。

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
adapter: godot       # 路径写法（可选，缺省按探测到的工程定；godot / generic）
backend: image-gen   # 生图后端（可选，缺省 image-gen）
model: gemini-3-pro-image   # 生图模型（可选，category 可覆盖）
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

## `adapter` 与 `project_root`

```yaml
adapter: godot        # 可选。godot / generic；不写就按探测到的工程定
project_root: ".."    # 可选。相对本文件；也可用 CLI 的 --project-root 覆盖
```

`adapter` 选的**只是路径写法**，不是项目用的引擎。可选值两个：

| `adapter` | 路径写法 |
|---|---|
| `godot` | 认 `res://`（等价于工程根） |
| `generic` | 普通文件路径，不认任何虚拟前缀 |

多对一是正常的：UE / Unity / 自研 / 没探到，全都用 `generic`。**`generic` 表达的是
「用普通文件路径」，不是「这个项目没有引擎」** —— UE 项目声明「引擎：unreal」而这里
写 `adapter: generic`，两者不矛盾。

`adapter: unreal` 是**兼容值**，等价于 `generic`（3.17.0 起）。它当年多做的工程根
探测已经归入通用的工程探测，对所有适配器一视同仁；导入提示也改成按探测到的工程给。
写着它的配置照样能跑，只会多一条提示。

旧字段 `engine:` 仍可用（按 `adapter:` 处理），但两者同时出现且不一致会报错。

`project_root` 不给时按「工程标志探测（`project.godot` / `*.uproject`）→ yaml 位置
推断」兜底。**探测不问适配器** —— 换 `adapter` 不会换掉工程根。最后那条兜底会随
config 移动而改变相对路径基准，config 不在工程根时建议显式写 `project_root`。

工程根按哪一条定下来的，`check` 和生成时都会打出来。

## `model`（生图模型）

顶层字段，category 可覆盖。`laozhang` 后端按前缀分流：`gemini-*` 走 Gemini native
（支持多图 reference 与单图 edit），`gpt-image-*` 走 OpenAI（只有单图 edit，
且 `aspect_ratio` 只原生支持 1:1 / 2:3 / 3:2）。

优先级：item 的 `model` > category 的 `model` > 顶层 `model` > `LAOZHANG_MODEL` > 后端内置默认。

`image-gen` 后端不认 `model`（它用 `chain`），配了会**报错**：丢掉指定的模型仍然
出得来图，但那不是你要的那件事，而批量是按张烧钱的。

同理 `laozhang` 不认 `chain` / `preset`。要临时跑一次（比如切后端试试）就加
`--allow-degrade`，它会把这类错降回告警并说明放行了什么。`seed` 是例外 ——
它只影响可复现性，不影响画的是什么，丢了照旧只告警。

`check` 有同名开关，两边判断一致 —— 否则校验和执行又会分家。

自定义后端（脚本路径 / `IMAGE_GEN_SCRIPT`）的能力**未知**：上层既不报降级，
也不假装查过，只在开头说一句。它若丢弃字段，得自己出声。

## Unreal 项目

**不需要写 `adapter`。** 向上找 `*.uproject` 是通用的工程探测在做，`/Game/` 由
通用路径校验拒绝，导入提示按探测到的工程给 —— 三件事都不依赖一个叫 `unreal`
的适配器。留空或写 `generic` 都行。

**`/Game/` 不能用**，这不是「暂未支持」而是它本来就不该用在这里：

```
ArtSource/Fish/F_River.png          ← 本流水线产出的（导入前的源图片）
        ↓  UE 的 AssetImportTask
Content/Fish/F_River.uasset         ← /Game/Fish/F_River 指的是这个
```

`output_root` 要写相对工程根的普通路径（如 `ArtSource/Fish`）。把源图片写进
`Content/`，引擎既不认识裸 PNG，那个目录也会被搞乱。

探测到 `*.uproject` 就会提示一句需要走 UE 导入 —— 它**陈述的是生成与导入的边界，
不是检查结果**。`.uasset` 是二进制，而且源图片到资产的对应关系写在项目各自的导入
脚本里，没法反查「这张图导没导过」。Godot 那边能扫 `.import` 文件，Unreal 这边扫不了。

## `backend`（生图后端）

`image-gen`（缺省） / `laozhang`（随插件安装） / 脚本路径（相对路径以 project_root
为基准）。`IMAGE_GEN_SCRIPT` 环境变量可临时覆盖，优先级最高。

后端不认的字段默认**阻止执行** —— 例如 `laozhang` 不支持 `chain` / `preset`。
`--allow-degrade` 降回告警，`seed` 本来就只告警。详见上面「`model`（生图模型）」
一节和 `../BACKEND-PROTOCOL.md`。

## `output_root`

输出根目录，相对项目根。`adapter: godot` 时**支持 `res://` 前缀**，等价于剥掉前缀（项目根 =
`project.godot` 所在目录）。`generic` 不认 `res://`，会直接报错 —— 不会退回 yaml 父目录猜。

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
| `seed` / `chain` / `preset` | misc | 透传到 image-gen `defaults`；`chain` / `preset` 未设时继承 `style` 段的同名字段（`skip_global_style: true` 则不继承） |
| `reference_paths` | list | 覆盖 global style 的内容层 ref（可选） |
| `model` | string | 覆盖顶层 `model`（可选） |
| `image` | string | **编辑底图**，与 `reference_paths` 互斥（可选） |
| `item_overrides` | dict | `{生成参数: 数据字段名}` —— 声明哪一列能逐项覆盖（可选，见下） |

### `item_overrides`（逐项覆盖哪个参数）

`model` / `aspect_ratio` / `seed` / `image` 可以按条目覆盖 —— 一个 category 共用一张
底图、个别 item 换自己的，就靠这个。但**哪一列算控制字段，得声明**：

```yaml
item_overrides:
  model: gen_model      # 数据里的 gen_model 列 → 生图 model
  image: base_art
```

声明是**封闭的**：只有写出来的映射生效，数据里别的同名字段一律当普通数据。
`item_overrides: {}` 表示本 category 不接受逐项覆盖。空单元格不算覆盖
（CSV 短行会把缺的字段补成空串，不该给后端送个空模型名）。

**没声明时，行为退回「同名即覆盖」** —— 数据里叫 `model` 的字段会成为生图模型。
这对专门做的生成清单很方便，对复用的策划表就是隐式控制通道：表里加一列 `model`
表示游戏里的模型类型，会顺手改掉生图模型。所以没声明时 `check` 报**治理问题**
（退码 3），生成时打告警。行为不变 —— 改了会让现有配置静默失效 —— 但不再悄无声息。

### `image` 与 `reference_paths` 的区别

| | 含义 | 构图 |
|---|---|---|
| `image` | 编辑这张图 | 保住原构图 |
| `reference_paths` | 参考这些图的风格，重新画 | 会漂 |

两者**互斥**，同时给会在构造 batch 时就报错，不等发到后端。路径解析规则相同：
`res://` 相对项目根，裸相对路径相对 `output_root`，绝对路径原样。

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

### `csv` — 策划表直接当数据源

```yaml
data_source:
  type: csv
  path: "Knowledge/Design/鱼表格/第一版.csv"   # 相对 project_root，接受 res://
  id_column: fish_id                          # 必填：哪一列当 id
  columns:                                    # 可选：列名 → 字段名
    图鉴描述: description
    名字: name
  encoding: utf-8-sig                         # 可选，缺省 utf-8-sig
```

**列名按「精确优先 → 唯一前缀」匹配**，所以配置里写短名即可 —— 策划表的表头常带括注：

| 表头里的实际列名 | 配置里写 |
|---|---|
| `fish_id（资产文件名，如 Fish_RiverPattern；…）` | `fish_id` |
| `力量系数K（KG*K=力量）` | `力量系数K` |
| `名字` | `名字` |

前缀匹配到多列会报错并列出候选，不会替你猜。表里同时有 `名字` 和 `名字（旧）` 时，
写 `名字` 命中精确的那个。

#### 值一律是字符串

不做类型推断。转了就丢原始表示 —— `001` 的前导零、`0.4~3` 这种范围写法、`60秒` 这种带
单位的值，都会在推断里出问题；而且同一列的取值类型会变得不稳定。

**注意 `derived_fields` 的 DSL 当前只有 `join` / `upper` / `lower` / `title`，没有数值转换**，
而且它的字段参数只接受 ASCII 标识符 —— 中文列名要先用 `columns` 映射成英文短名才能在 DSL
里引用。`str.format` 模板本身没有这个限制，`{名字}` 可以直接写。

`filter` 也是严格相等比较：CSV 里的 `6` 是字符串，写 `力量: 6` 匹配不到，要写 `力量: "6"`。

#### 会报错而不是静默处理的情况

| 情况 | 为什么不能放过 |
|---|---|
| 表头有重复列名 | id 会取自前一列、字段值取自后一列，prompt 和文件名对不上 |
| 某行单元格数超过表头列数 | 多出来的会被丢掉，通常意味着这行多了个逗号 |
| 别名撞上已有列名 | 谁覆盖谁取决于列顺序 |
| 两个源列映射到同一别名 | 必然丢掉一份数据 |
| 别名是 `id` | `id` 是保留字段，由 `id_column` 决定 |
| 某行有内容但 id 列为空 | id 决定输出文件名 |
| 开头是空行（被当成表头） | 与数据区的空行不同，表头必须是第一行 |

报错里的行号是**文件里的物理行**，单元格内有换行时也对得上。

整行全空的行会跳过（导出的 CSV 常带尾部空行）；短行缺的字段补成空字符串。

#### 和生成控制字段的关系

CSV 的列会原样进入 item。表里恰好有 `seed` / `model` / `aspect_ratio` / `image`
这些列名时，默认会被当成 **item 级**生成参数 —— 而 CSV 取出来的是**字符串**。
item 级优先于 category 级，所以在 yaml 里写同名字段**压不过**表里的列。

复用的策划表最容易撞上这个。三条出路，按推荐顺序：

1. `item_overrides: {}` —— 本 category 不接受逐项覆盖，那几列当普通数据
2. `item_overrides: {model: <真正想用的列>}` —— 确实要逐项覆盖时，显式指名
3. `data_source.columns` 把那几列改名

不处理也能跑，但 `check` 会报治理问题（退码 3），生成时也会告警。

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
python generate_assets.py all --dry-run       # 只打计划和 prompt，不调 API（不带 category 等于 list）
python generate_assets.py --force             # 覆盖已存在
python generate_assets.py --config path.yaml  # 自定义 config
```

退码：沿用 image-gen `0/1/2`（多 category 取最大）。

`--limit N` 只取前 N 条，用来抽样验模板 —— 省得为了试两张先去数据源里查 id 叫什么。
和 `--names` 一起用时**先按 id 挑、再取前 N**（反过来的话 `--names` 指定的条目可能
根本不在前 N 里，等于白写）。

## 完整示例

见 `milk-tea-defense.yaml`（5 category：customers / ingredients / recipes /
buildings / backgrounds）。

## Godot 特化

- `res://` 路径自动剥前缀，等价于相对项目根
- 跑完后扫输出目录，提示有多少 `.import` 文件缺失（用 Godot 编辑器打开自动 import）
- 输出子目录自动 `mkdir -p`（image-gen 不建多层目录）
- 检测 `project.godot`：缺则退到 generic 适配 —— generic **不认** `res://`，会直接报错让你改 `adapter` 或换相对路径，不会按 yaml 父目录猜

## 不做的事

- ❌ 不重新实现 image-gen 的能力（chain / fallback / manifest / skip-existing 都已就绪）
- ❌ 不写 .tres atlas / SpriteSheet（thick-layer TODO）
- ❌ 不绑定特定 model / preset 名（让 yaml chain / preset 透传）
- ❌ 不允许 eval / exec 任意表达式
