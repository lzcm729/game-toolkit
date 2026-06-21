# split-doc-layers.config.yaml — Schema 文档

`split-doc-layers` 的项目级配置文件。一份 yaml 描述一个项目的三层拆分上下文，
让 skill 的所有项目特化都收在配置里，skill 正文零硬编码。

## 文件位置

默认在项目根：

```
split-doc-layers.config.yaml
```

## 顶层结构

```yaml
$schema_version: 1
data_ssot: "..."         # 精确数值真值锚（路径模式）
framework_docs: "..."    # Framework 文档路径模式
content_dir: "..."       # 内容目录位置 + 形态说明
semantic_field: "..."    # 现成语义字段名（逐字搬源）
reader: "..."            # 内容目录目标读者
pointer_loc: "..."       # 双向指针两端位置描述
forbid_pattern: "..."    # 防回退精确数值正则（标注用）
```

## 7 项配置说明

### `data_ssot`

精确数值的真值锚（数据层 SSOT）。内容目录里不手写精确数值，要查去这里查。它表示"精确数值不进内容目录时，读者应去哪查"——任何格式的路径模式均可填写。

- Godot 项目：`data/**/*.tres`
- JSON 数据：`data/**/*.json`
- 数据库：`db/schema.sql`（或说明"PostgreSQL production DB"）
- CSV 数据驱动项目：`content/**/*.csv`

```yaml
data_ssot: "data/**/*.tres"
```

**数据分层处理**：若项目实体数据与数值/校准数据分属不同源（如"动物种类/名称在 CSV"，"成长速率/稀有度概率在 sim JSON"），`data_ssot` 可写多条（YAML 列表），或填主实体层并在注释中说明数值层位置：

```yaml
# 方式 A：列表（两层都作为 SSOT）
data_ssot:
  - "content/animal/*.csv"       # 实体层（种类/名称/场景路径）
  - "docs/design/sim/saved_params.json"  # 数值层（成长参数/概率校准）

# 方式 B：单值填主实体层 + 注释标数值层
data_ssot: "content/animal/*.csv"
# ⚠ 数值层（精确校准参数）→ docs/design/sim/saved_params.json
```

内容目录里指向数值的指针，应指向数值层路径（而非实体层）。

### `framework_docs`

Framework 文档路径模式。Phase 5 Framework 瘦身时，只对这里的文件加指针。

```yaml
framework_docs: "docs/GDD/*.md"
```

### `content_dir`

内容目录的目标位置 + 形态说明。可以是已存在的目录/文件模式，也可以是待创建的位置。

```yaml
content_dir: "docs/design/*-menu.html"  # HTML 图鉴，已有
content_dir: "docs/content/*.md"        # Markdown 表，待建
```

### `semantic_field`

数据 schema 里现成的语义字段名。身份摘要优先从这里逐字搬，不提炼不改写。

可以填多个字段名（按优先级顺序）：

```yaml
semantic_field: "behavior_description"               # 单字段
semantic_field: "behavior_description, description"  # 多字段，按顺序 fallback
```

没有现成语义字段时填 `none`，Phase 3 会走手动提炼路径（从 `framework_docs` 设计意图段提炼 + 标漂移风险注释）。

**填 `none` 的场景**：数据 schema 里没有面向读者的自然语言描述字段。例如 CSV 字段全是 `type, name, stage, base_value, scene_path` 这类技术/工程字段——它们不是语义字段。

**不要用离题字段充数**：`name`（中文名"小鸡"）、`id`、`scene_path`、`egg_scene_path` 等字段**不是**语义描述字段，不能逐字搬做身份摘要。填了也无法在 Phase 3 直接使用，反而造成配置和实际操作的歧义。这种情况应填 `semantic_field: none`，走提炼路径。

### `reader`

内容目录的目标读者。决定 Phase 3 的内容边界。

| 值 | 含义 |
|---|---|
| `designer` | 设计师/开发者——可含实施细节和功能组合推荐，不含精确数值 |
| `player` | 玩家——只含身份摘要/文案/视觉标识，不含实施细节和精确数值 |
| 自定义描述 | 如 `"设计阶段内部评审用，面向策划和程序"` |

```yaml
reader: designer
```

### `pointer_loc`

双向指针两端的位置描述，格式：`内容目录端描述 ↔ Framework端描述`。

Phase 4 按此配置在两端各加一件指针，构成导航闭环即够——不要第三件。

```yaml
pointer_loc: "图鉴 footer「📐层次」段 ↔ GDD「实施细节速查」段"
pointer_loc: "content/*.md footer ↔ GDD §0「相关文档」段"
```

### `forbid_pattern`

防止精确数值回退到内容目录的正则（标注用，CI 可接入 lint）。

本项目暂不接 lint 时，填值作为"提醒拦截门"——执行 Phase 3 时手动过滤。

```yaml
forbid_pattern: "[0-9]+\\.[0-9]+"     # 小数点数值（如 1.5 / 0.25）
forbid_pattern: "×[0-9]|[0-9]+%"     # 乘数或百分比
```

---

## 最小骨架 yaml

```yaml
$schema_version: 1
data_ssot: "data/**/*.json"
framework_docs: "docs/design/*.md"
content_dir: "docs/content/*.md"
semantic_field: "description"
reader: designer
pointer_loc: "内容文档 footer ↔ 框架文档「速查」段"
forbid_pattern: "[0-9]+\\.[0-9]+"
```

---

## 完整示例

- `milk-tea-defense.yaml` — Godot 奶茶塔防项目（`.tres` 数据驱动 + `behavior_description` 语义字段）
- `project-egg.yaml` — 养鸡养成游戏（CSV + 双层 SSOT + 无语义字段，`semantic_field: none` 场景）
