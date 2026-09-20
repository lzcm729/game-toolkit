# csv 数据源 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 generate-assets 的数据源加一种 `csv`，让策划表（CSV）能直接当批量生成的数据源，不必先转 JSON。

**Architecture:** 在 `scripts/data_source.py` 里加一个 loader 分支，复用既有的 `_resolve_path` 与 `_apply_filter`。核心是列名匹配：策划表的表头常带括注（`力量系数K（KG*K=力量）`），配置里只写短名，按「精确优先 → 唯一前缀兜底 → 歧义不猜」匹配。

**Tech Stack:** Python 3.10+、标准库 `csv`、pytest

**Spec:** 无独立 spec。本计划的设计依据写在下面的「设计依据」一节。

## Global Constraints

- 工作目录 `skills/generate-assets/`，测试用 `python -m pytest` 在该目录下跑
- Python 3.10+ 语法；沿用文件现有风格：中文 docstring、错误消息说清「哪里错了、怎么办」
- **只改 `scripts/data_source.py`、`tests/test_data_source.py`、`examples/README.md` 三个文件**，不要动其他文件
- **不要执行 `git add` / `git commit` / 切分支**，改动留在工作区
- 不要引入任何第三方依赖（`csv` 是标准库）
- 所有单元格值**保持字符串**，不做类型推断（理由见「设计依据」第 3 条）
- 现有 187 条以上测试必须继续全绿：`python -m pytest tests/ -q`

## 设计依据

实现前先读懂这三条，它们决定了为什么这么写：

**1. 列名匹配规则不是新发明的，是对齐既有约定。**

真实策划表的表头长这样（来自一个使用本插件的 UE 项目的鱼表格）：

```
fish_id（资产文件名，如 Fish_RiverPattern；2026-09-09 加，程序按此列对鱼、不按名字。...）
名字
力量系数K（KG*K=力量）
重量/KG
```

而该项目的列声明文件里写的是短名 `fish_id`、`名字`、`力量系数K`、`重量/KG`。它自己的校验脚本
`Scripts/check_fish_table_vs_definition.py` 用这个规则匹配：

```python
def match_col(name: str, head: list[str]) -> str | None:
    """sidecar 的 name 按表头前缀匹配（表头常带括注）。"""
    exact = [h for h in head if h == name]
    if exact:
        return exact[0]
    pref = [h for h in head if h.startswith(name)]
    return pref[0] if len(pref) == 1 else None
```

**本插件必须用同一套规则** —— 同一份 CSV 在两个工具里解析出不同结果，是那个项目明令禁止的
「双口径」。唯一的差别：本插件匹配失败时**抛 ValueError 而不是返回 None**，因为配置错误该在
开跑前就报，不该拖到渲染阶段变成一个费解的 KeyError。

注意「精确优先」不是多余的：若表里同时有 `名字` 和 `名字（旧）`，找 `名字` 必须命中前者，
而不是报「前缀歧义」。

**2. BOM 必须处理。** 实测该项目的 CSV 由在线表格导出，带 UTF-8 BOM。用 `utf-8` 读会让第一个
列名变成 `﻿fish_id（...`，前缀匹配随之失效且报错信息完全看不出原因。所以默认编码用
`utf-8-sig`（它同时能正确读不带 BOM 的文件）。

**3. 不做类型推断。** CSV 没有类型信息，而真实数据里 `重量/KG` 一列的值是 `0.4~3` 这种范围
写法，`持续时间` 是 `60秒`。任何「看起来像数字就转成数字」的规则都会在这类值上猜错，且错得
安静。需要数值转换的场景已经有 `derived_fields` 的 DSL 兜底。

**4. 跳过空行，但空 id 要报错。** 导出的 CSV 常带尾部空行。整行全空跳过；但一行有内容、
id 列却是空的，属于数据错误 —— id 决定输出文件名，必须报出来并指明行号。

---

### Task 1: 列名匹配

**Files:**
- Modify: `scripts/data_source.py`（新增 `_match_column`，放在 `_resolve_path` 之后）
- Test: `tests/test_data_source.py`（追加到文件末尾）

**Interfaces:**
- Consumes: 无
- Produces: `_match_column(name: str, header: list[str], *, where: str) -> str`
  —— 返回表头里实际的列名；匹配不到或歧义时抛 `ValueError`。`where` 用于错误消息里指明
  是哪个配置项引用了这个列名（如 `"id_column"` 或 `"columns 的键"`）。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_data_source.py`：

```python
# -------------------- csv 列名匹配 --------------------
# 注意：把 _match_column 加进文件顶部那行 import，别在文件中间另写一句 import
#   from data_source import load_data_source, _match_column


def test_match_column_exact():
    head = ["fish_id", "名字", "重量/KG"]
    assert _match_column("名字", head, where="id_column") == "名字"


def test_match_column_prefix():
    """策划表的表头常带括注，配置里只写短名。"""
    head = ["fish_id（资产文件名，如 Fish_RiverPattern）", "力量系数K（KG*K=力量）"]
    assert _match_column("fish_id", head, where="id_column") == head[0]
    assert _match_column("力量系数K", head, where="id_column") == head[1]


def test_match_column_exact_beats_prefix():
    """同时有「名字」和「名字（旧）」时，找「名字」必须命中精确的那个。"""
    head = ["名字（旧）", "名字"]
    assert _match_column("名字", head, where="id_column") == "名字"


def test_match_column_ambiguous_prefix_raises():
    head = ["重量（kg）", "重量（lb）"]
    with pytest.raises(ValueError) as ei:
        _match_column("重量", head, where="columns 的键")
    msg = str(ei.value)
    assert "重量" in msg
    assert "重量（kg）" in msg and "重量（lb）" in msg   # 列出歧义候选
    assert "columns 的键" in msg


def test_match_column_not_found_lists_available():
    head = ["fish_id", "名字"]
    with pytest.raises(ValueError) as ei:
        _match_column("体重", head, where="id_column")
    msg = str(ei.value)
    assert "体重" in msg
    assert "fish_id" in msg and "名字" in msg           # 列出可用列名
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_data_source.py -k match_column -q`
Expected: FAIL — `ImportError: cannot import name '_match_column'`

- [ ] **Step 3: 实现**

在 `scripts/data_source.py` 的 `_resolve_path` 函数之后插入：

```python
def _match_column(name: str, header: list[str], *, where: str) -> str:
    """把配置里写的列名匹配到表头里的实际列名。

    精确优先，其次唯一前缀 —— 策划表的表头常带括注
    （「力量系数K（KG*K=力量）」），配置里只写短名。

    与使用方项目的 check_fish_table_vs_definition.py 的 match_col 同规则：
    同一份 CSV 在两个工具里必须解析出相同结果。差别只在匹配失败时本函数
    抛错而不是返回 None —— 配置错误该在开跑前报，不该拖到渲染阶段变成
    一个看不懂的 KeyError。

    「精确优先」不是多余的：表里同时有「名字」和「名字（旧）」时，
    找「名字」必须命中前者，而不是报前缀歧义。
    """
    exact = [h for h in header if h == name]
    if exact:
        return exact[0]

    prefixed = [h for h in header if h.startswith(name)]
    if len(prefixed) == 1:
        return prefixed[0]
    if len(prefixed) > 1:
        raise ValueError(
            "{} 里的列名 {!r} 匹配到多列，无法判断用哪个：{}。"
            "把它写得更长一些以区分。".format(where, name, prefixed)
        )
    raise ValueError(
        "{} 里的列名 {!r} 在表头里找不到。可用列名：{}".format(
            where, name, header
        )
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_data_source.py -k match_column -q`
Expected: 5 passed

---

### Task 2: csv loader

**Files:**
- Modify: `scripts/data_source.py`（新增 `_load_csv`，放在 `_load_inline` 之后；顶部加 `import csv`）
- Test: `tests/test_data_source.py`

**Interfaces:**
- Consumes: Task 1 的 `_match_column(name, header, *, where) -> str`；文件已有的
  `_resolve_path(rel, project_root) -> Path`
- Produces: `_load_csv(spec: dict, project_root: Path) -> list[dict]`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_data_source.py`：

```python
# -------------------- csv --------------------

def _write_csv(tmp_path, rel: str, text: str, *, bom: bool = False) -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    if bom:
        data = b"\xef\xbb\xbf" + data
    p.write_bytes(data)
    return p


def test_csv_basic(tmp_path):
    _write_csv(tmp_path, "fish.csv", "fish_id,名字,重量\nF_A,河纹鱼,0.4~3\nF_B,小银鱼,0.05~0.4\n")
    items = load_data_source(
        {"type": "csv", "path": "fish.csv", "id_column": "fish_id"},
        tmp_path,
    )
    assert [it["id"] for it in items] == ["F_A", "F_B"]
    assert items[0]["名字"] == "河纹鱼"


def test_csv_handles_bom(tmp_path):
    """在线表格导出的 CSV 常带 BOM，用 utf-8 读会让第一个列名多出 \\ufeff。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n", bom=True)
    items = load_data_source(
        {"type": "csv", "path": "fish.csv", "id_column": "fish_id"},
        tmp_path,
    )
    assert items[0]["id"] == "F_A"


def test_csv_id_column_matched_by_prefix(tmp_path):
    _write_csv(
        tmp_path, "fish.csv",
        '"fish_id（资产文件名，如 Fish_RiverPattern）",名字\nF_A,河纹鱼\n',
    )
    items = load_data_source(
        {"type": "csv", "path": "fish.csv", "id_column": "fish_id"},
        tmp_path,
    )
    assert items[0]["id"] == "F_A"


def test_csv_columns_mapping(tmp_path):
    """长列名没法当 prompt 占位符，映射成短名。"""
    _write_csv(
        tmp_path, "fish.csv",
        '"fish_id（资产文件名）","图鉴描述（给玩家看的一句话）"\nF_A,一条会反光的鱼\n',
    )
    items = load_data_source(
        {
            "type": "csv", "path": "fish.csv", "id_column": "fish_id",
            "columns": {"图鉴描述": "description"},
        },
        tmp_path,
    )
    assert items[0]["description"] == "一条会反光的鱼"


def test_csv_unmapped_columns_keep_original_name(tmp_path):
    """没映射的列也要保留，derived_fields 可能要用。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字,稀有度\nF_A,河纹鱼,普通\n")
    items = load_data_source(
        {
            "type": "csv", "path": "fish.csv", "id_column": "fish_id",
            "columns": {"名字": "name"},
        },
        tmp_path,
    )
    assert items[0]["name"] == "河纹鱼"      # 映射过的
    assert items[0]["稀有度"] == "普通"      # 没映射的，用原列名


def test_csv_values_stay_strings(tmp_path):
    """不做类型推断：真实数据里有 0.4~3、60秒 这种，猜必错且错得安静。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,力量,重量\nF_A,6,0.4~3\n")
    items = load_data_source(
        {"type": "csv", "path": "fish.csv", "id_column": "fish_id"},
        tmp_path,
    )
    assert items[0]["力量"] == "6"          # 字符串，不是 int
    assert items[0]["重量"] == "0.4~3"


def test_csv_skips_blank_rows(tmp_path):
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n\n,\nF_B,小银鱼\n")
    items = load_data_source(
        {"type": "csv", "path": "fish.csv", "id_column": "fish_id"},
        tmp_path,
    )
    assert [it["id"] for it in items] == ["F_A", "F_B"]


def test_csv_empty_id_in_nonblank_row_raises(tmp_path):
    """id 决定输出文件名，空了必须报出来并指明行号。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n,小银鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(
            {"type": "csv", "path": "fish.csv", "id_column": "fish_id"},
            tmp_path,
        )
    msg = str(ei.value)
    assert "3" in msg                      # 行号（表头算第 1 行）
    assert "fish_id" in msg


def test_csv_missing_id_column_raises(tmp_path):
    _write_csv(tmp_path, "fish.csv", "名字,重量\n河纹鱼,0.4\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(
            {"type": "csv", "path": "fish.csv", "id_column": "fish_id"},
            tmp_path,
        )
    assert "fish_id" in str(ei.value)


def test_csv_requires_id_column_field(tmp_path):
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source({"type": "csv", "path": "fish.csv"}, tmp_path)
    assert "id_column" in str(ei.value)


def test_csv_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_data_source(
            {"type": "csv", "path": "nope.csv", "id_column": "fish_id"},
            tmp_path,
        )


def test_csv_empty_file_raises(tmp_path):
    _write_csv(tmp_path, "fish.csv", "")
    with pytest.raises(ValueError) as ei:
        load_data_source(
            {"type": "csv", "path": "fish.csv", "id_column": "fish_id"},
            tmp_path,
        )
    assert "表头" in str(ei.value)


def test_csv_custom_encoding(tmp_path):
    p = tmp_path / "fish.csv"
    p.write_bytes("fish_id,名字\nF_A,河纹鱼\n".encode("gbk"))
    items = load_data_source(
        {"type": "csv", "path": "fish.csv", "id_column": "fish_id", "encoding": "gbk"},
        tmp_path,
    )
    assert items[0]["名字"] == "河纹鱼"


def test_csv_filter_still_works(tmp_path):
    """filter 是所有数据源共用的，csv 不该例外。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,稀有度\nF_A,普通\nF_B,稀有\n")
    items = load_data_source(
        {
            "type": "csv", "path": "fish.csv", "id_column": "fish_id",
            "filter": {"稀有度": "稀有"},
        },
        tmp_path,
    )
    assert [it["id"] for it in items] == ["F_B"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_data_source.py -k csv -q`
Expected: FAIL — `未知 data_source type: 'csv'`

- [ ] **Step 3: 实现**

在 `scripts/data_source.py` 顶部导入区把 `import json` 改成：

```python
import csv
import json
```

在 `_load_inline` 函数之后插入：

```python
def _load_csv(spec: dict, project_root: Path) -> list[dict]:
    """读策划表。

    列名按 _match_column 的规则匹配（精确优先、其次唯一前缀），所以配置里
    写短名即可，不必抄表头里那一长串括注。

    单元格值一律保持字符串：CSV 没有类型信息，而真实数据里有「0.4~3」
    「60秒」这类写法，任何「像数字就转」的规则都会猜错且错得安静。
    需要数值转换用 derived_fields。
    """
    path = spec.get("path")
    if not path:
        raise ValueError("data_source.type=csv 必须设 'path'")
    id_column = spec.get("id_column")
    if not id_column:
        raise ValueError(
            "data_source.type=csv 必须设 'id_column' —— id 决定输出文件名，"
            "没法从表里猜"
        )

    full = _resolve_path(path, project_root)
    if not full.exists():
        raise FileNotFoundError(f"data_source 路径不存在: {full}")

    # utf-8-sig：在线表格导出的 CSV 常带 BOM，用 utf-8 读会让第一个列名
    # 多出 ﻿，前缀匹配随之失效且报错完全看不出原因。
    # 它也能正确读不带 BOM 的文件。
    encoding = spec.get("encoding") or "utf-8-sig"
    with full.open(encoding=encoding, newline="") as f:
        rows = list(csv.reader(f))

    if not rows:
        raise ValueError(f"CSV 是空的，读不到表头: {full}")

    header = [h.strip() for h in rows[0]]
    id_col = _match_column(id_column, header, where="id_column")
    id_idx = header.index(id_col)

    # columns: {表里的列名(短名): item 里的字段名}
    mapping_raw = spec.get("columns") or {}
    if not isinstance(mapping_raw, dict):
        raise ValueError(
            f"data_source.columns 必须是映射（列名 → 字段名），"
            f"实际是 {type(mapping_raw).__name__}"
        )
    renames: dict[str, str] = {}
    for src_name, dst_name in mapping_raw.items():
        actual = _match_column(str(src_name), header, where="columns 的键")
        renames[actual] = str(dst_name)

    items: list[dict] = []
    for line_no, row in enumerate(rows[1:], start=2):
        if not any((cell or "").strip() for cell in row):
            continue        # 整行空：导出的 CSV 常带尾部空行

        item: dict[str, Any] = {}
        for i, col in enumerate(header):
            if not col:
                continue
            value = row[i] if i < len(row) else ""
            item[col] = value
            if col in renames:
                item[renames[col]] = value

        raw_id = (row[id_idx] if id_idx < len(row) else "").strip()
        if not raw_id:
            raise ValueError(
                f"{full} 第 {line_no} 行的 {id_col!r} 是空的。"
                "id 决定输出文件名，不能为空 —— 删掉这行或补上 id。"
            )
        item["id"] = raw_id
        items.append(item)

    return items
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_data_source.py -k csv -q`
Expected: 14 passed（Task 1 的 5 条 match_column 也会被 `-k csv` 漏掉，属正常）

---

### Task 3: 接进分派 + 文档

**Files:**
- Modify: `scripts/data_source.py`（`load_data_source` 的分派与 docstring）
- Modify: `examples/README.md`（数据源那一节）
- Test: `tests/test_data_source.py`

**Interfaces:**
- Consumes: Task 2 的 `_load_csv(spec, project_root) -> list[dict]`
- Produces: 无新接口

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_data_source.py`：

```python
def test_unknown_type_message_lists_csv(tmp_path):
    """报错里的可选类型清单得把 csv 算上，否则用户以为不支持。"""
    with pytest.raises(ValueError) as ei:
        load_data_source({"type": "xlsx"}, tmp_path)
    assert "csv" in str(ei.value)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_data_source.py -k unknown_type_message -q`
Expected: FAIL — 报错文案里只有 `json_dict / json_list / inline`

- [ ] **Step 3: 改分派**

`scripts/data_source.py` 的 `load_data_source` 里，把：

```python
    elif src_type == "inline":
        items = _load_inline(spec)
    else:
        raise ValueError(
            f"未知 data_source type: {src_type!r}（v1 仅支持 json_dict / json_list / inline）"
        )
```

改成：

```python
    elif src_type == "inline":
        items = _load_inline(spec)
    elif src_type == "csv":
        items = _load_csv(spec, project_root)
    else:
        raise ValueError(
            f"未知 data_source type: {src_type!r}"
            "（支持：json_dict / json_list / inline / csv）"
        )
```

同时把该函数 docstring 里的 spec 字段说明改成：

```python
    spec 字段：
      - type: "json_dict" / "json_list" / "inline" / "csv"
      - path: (json_* / csv) 相对 project_root 的文件路径
      - items: (inline) yaml 内嵌 dict
      - id_column: (csv) 哪一列当 id，按精确/唯一前缀匹配表头
      - columns: (csv, 可选) {表里的列名: item 里的字段名}
      - encoding: (csv, 可选) 缺省 utf-8-sig
      - filter: (可选) 简单 dict，过滤条件（见 _apply_filter）
```

并把文件顶部的模块 docstring 第一行 `（v1：json_dict / json_list / inline）` 改成
`（json_dict / json_list / inline / csv）`。

- [ ] **Step 4: 跑全套测试**

Run: `python -m pytest tests/ -q`
Expected: 全绿，且总数比改动前多 20 条

- [ ] **Step 5: 写文档**

在 `examples/README.md` 的 `### inline — yaml 内嵌 items` 一节之后，插入：

````markdown
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

几条行为值得先知道：

- **单元格值一律是字符串**，不做类型推断。真实策划表里有 `0.4~3`（范围）、`60秒`（带单位）
  这类写法，任何「像数字就转」的规则都会猜错且错得安静。要数值用 `derived_fields`。
- **没映射的列也保留**，用表头里的原始列名当字段名 —— `derived_fields` 可能要用到。
- **整行全空的行跳过**（导出的 CSV 常带尾部空行）；但一行有内容而 id 列为空会报错并指明行号。
- BOM 默认处理好了（`utf-8-sig` 也能读不带 BOM 的文件）。
````

- [ ] **Step 6: 跑全套测试确认文档改动没破坏什么**

Run: `python -m pytest tests/ -q`
Expected: 全绿

- [ ] **Step 7: 交付前自检**

把这几件事逐条确认并在交付说明里写结果：

1. `git status --short` —— 只有 `scripts/data_source.py`、`tests/test_data_source.py`、
   `examples/README.md` 三个文件被修改，没有新增其他文件
2. `python -m pytest tests/ -q` 全绿
3. 没有执行过 `git add` / `git commit` / 切分支
4. **报告「故意没做什么、为什么」** —— 如果你在实现中发现计划里某处写得不对或不够，
   不要默默改掉，写出来
