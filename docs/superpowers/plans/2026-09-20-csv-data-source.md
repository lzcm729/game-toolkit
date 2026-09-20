# csv 数据源 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 generate-assets 的数据源加一种 `csv`，让策划表（CSV）能直接当批量生成的数据源，不必先转 JSON。

**Architecture:** 在 `scripts/data_source.py` 里加一个 loader 分支，复用既有的 `_resolve_path` 与 `_apply_filter`。核心是列名匹配：策划表的表头常带括注（`力量系数K（KG*K=力量）`），配置里只写短名，按「精确优先 → 唯一前缀兜底 → 歧义不猜」匹配。

**Tech Stack:** Python 3.10+、标准库 `csv`、pytest

**Spec:** 无独立 spec。设计依据见下面的「设计依据」一节。

> **本版是第二稿。** 第一稿经 codex 评审发现 6 处必须改，其中两处会让执行直接卡住
> （分派接入太晚导致 Task 2 的 14 条测试全红；现有 `test_unknown_type` 恰好用 `csv`
> 当未知类型，接入后必红）。修订点在每处用「**[评审]**」标出，便于追溯。

## Global Constraints

- 工作目录 `skills/generate-assets/`，测试用 `python -m pytest` 在该目录下跑
- Python 3.10+ 语法；沿用文件现有风格：中文 docstring、错误消息说清「哪里错了、怎么办」
- **只改这四个文件**，不要动其他任何文件：
  - `scripts/data_source.py`
  - `tests/test_data_source.py`
  - `tests/test_main_flow.py`（只加 Task 3 的那一条集成测试）
  - `examples/README.md`
- **不要执行 `git add` / `git commit` / 切分支**，改动留在工作区
- 不要引入任何第三方依赖（`csv` 是标准库）
- 所有单元格值**保持字符串**，不做类型推断（理由见「设计依据」第 3 条）
- **现有 229 条测试必须继续全绿**：`python -m pytest tests/ -q`
- 错误消息里凡是提到行号，一律写成「第 N 行」的完整片段，不要只写数字
  —— **[评审]** 测试断言 `"3" in msg` 会被路径里的数字 3 满足，是假绿

## 设计依据

实现前先读懂这四条，它们决定了为什么这么写：

**1. 列名匹配策略对齐使用方项目，不是新发明的。**

真实策划表的表头长这样（来自一个使用本插件的 UE 项目的鱼表格）：

```
fish_id（资产文件名，如 Fish_RiverPattern；2026-09-09 加，程序按此列对鱼、不按名字。...）
名字
力量系数K（KG*K=力量）
重量/KG
```

而该项目的列声明文件里写的是短名 `fish_id`、`名字`、`力量系数K`、`重量/KG`。它自己的校验脚本
`Scripts/check_fish_table_vs_definition.py`（2026-09-17 的版本）用这个规则匹配：

```python
def match_col(name: str, head: list[str]) -> str | None:
    """sidecar 的 name 按表头前缀匹配（表头常带括注）。"""
    exact = [h for h in head if h == name]
    if exact:
        return exact[0]
    pref = [h for h in head if h.startswith(name)]
    return pref[0] if len(pref) == 1 else None
```

**本插件采用同一套列名匹配策略** —— 同一份 CSV 在两个工具里对不上列，是那个项目明令禁止的
「双口径」。

**[评审]** 承诺限定在「列名匹配策略一致」这一点上，不要声称整体解析一致：本计划还额外做了
表头去空白、重复列名拒绝、id 去空白等该脚本没有的事。上面那段代码取自 2026-09-17 的文件，
执行者无需也无法独立核验它是否仍是最新版。

注意「精确优先」不是多余的：若表里同时有 `名字` 和 `名字（旧）`，找 `名字` 必须命中前者，
而不是报「前缀歧义」。

**2. BOM 必须处理。** 实测该项目的 CSV 由在线表格导出，带 UTF-8 BOM。用 `utf-8` 读会让第一个
列名多出 `﻿`，前缀匹配随之失效且报错信息完全看不出原因。所以默认编码用 `utf-8-sig`
（它同时能正确读不带 BOM 的文件）。

**3. 不做类型推断。**

**[评审]** 第一稿的理由写错了两处，这里是修正版：

- CSV 没有类型信息。做推断就得决定 `"001"` 变不变成 `1`、`"6"` 变不变成 `int` ——
  **一旦转换，原始表示就丢了**，而策划表里的编号、版本号、带前导零的 id 都依赖原始表示。
- 保持字符串还让同一列的取值类型稳定：不会出现「这行是 int、那行因为写了 `0.4~3` 而是 str」。
- ~~"需要数值转换用 derived_fields 兜底"~~ —— **这句是错的，已删**。现有 DSL
  （`scripts/prompt_render.py`）只有 `join / upper / lower / title` 四个 helper，**没有任何
  数值转换**；而且 DSL 的字段参数只接受 ASCII 标识符，中文列名（哪怕加引号）都解析不了。
  本计划不扩展 DSL，文档里要如实说明这个限制。

**4. 跳过空行，但空 id 要报错。** 导出的 CSV 常带尾部空行。整行全空跳过；但一行有内容、
id 列却是空的，属于数据错误 —— id 决定输出文件名，必须报出来并指明行号。

**5. 宁可报错，不要静默丢数据。** **[评审]** 新增。以下情况一律报错而不是默默处理：
表头有重复列名、某行单元格数超过表头列数、别名与原列名撞车、两个源列映射到同一目标、
映射目标是保留字 `id`。理由：这些都是配置或数据的真实错误，静默处理会让 prompt 里的
`{字段}` 和输出文件名对不上，而那种 bug 极难查。

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

先把测试文件顶部的 import 改成：

```python
from data_source import load_data_source, _match_column
```

再追加到 `tests/test_data_source.py` 末尾：

```python
# -------------------- csv 列名匹配 --------------------

def test_match_column_exact():
    head = ["fish_id", "名字", "重量/KG"]
    assert _match_column("名字", head, where="id_column") == "名字"


def test_match_column_prefix():
    """策划表的表头常带括注，配置里只写短名。"""
    head = ["fish_id（资产文件名，如 Fish_RiverPattern）", "力量系数K（KG*K=力量）"]
    assert _match_column("fish_id", head, where="id_column") == head[0]
    assert _match_column("力量系数K", head, where="id_column") == head[1]


def test_match_column_exact_beats_prefix():
    """同时有「名字」和「名字（旧）」时，找「名字」必须命中精确的那个。

    注意精确的那个故意放在后面：如果实现只做前缀匹配取第一个，这条会红。
    """
    head = ["名字（旧）", "名字"]
    assert _match_column("名字", head, where="id_column") == "名字"


def test_match_column_ambiguous_prefix_raises():
    head = ["重量（kg）", "重量（lb）"]
    with pytest.raises(ValueError) as ei:
        _match_column("重量", head, where="columns 的键")
    msg = str(ei.value)
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

    与使用方项目 check_fish_table_vs_definition.py 的 match_col 同策略：
    同一份 CSV 在两个工具里对不上列，是那个项目明令禁止的双口径。
    差别只在匹配失败时本函数抛错而不是返回 None —— 配置错误该在开跑前报，
    不该拖到渲染阶段变成一个看不懂的 KeyError。

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
        "{} 里的列名 {!r} 在表头里找不到。可用列名：{}".format(where, name, header)
    )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_data_source.py -k match_column -q`
Expected: 5 passed

---

### Task 2: csv loader + 接进分派

**[评审]** 第一稿把分派留到 Task 3，导致本任务的测试全部调不通 `load_data_source()`
（codex 内存验证：0 通过、14 失败）。分派必须和 loader 一起落地。

**Files:**
- Modify: `scripts/data_source.py`（顶部加 `import csv`；新增 `_load_csv`；`load_data_source` 加分派并更新 docstring；模块 docstring 首行）
- Test: `tests/test_data_source.py`（**含修改现有的 `test_unknown_type`**）

**Interfaces:**
- Consumes: Task 1 的 `_match_column(name, header, *, where) -> str`；文件已有的
  `_resolve_path(rel, project_root) -> Path`、`_apply_filter(items, flt) -> list[dict]`
- Produces: `_load_csv(spec: dict, project_root: Path) -> list[dict]`

- [ ] **Step 1: 先修现有测试**

**[评审]** 现有 `tests/test_data_source.py:193` 的 `test_unknown_type` 恰好拿 `csv` 当
未知类型，CSV 接入后它会收到「必须设 'path'」而不是「未知 data_source type」，必红。
把它的输入换成一个确实不支持的类型，**断言保持不变**：

```python
def test_unknown_type(tmp_path):
    with pytest.raises(ValueError, match="未知 data_source type"):
        load_data_source({"type": "xlsx"}, tmp_path)
```

- [ ] **Step 2: 写失败测试**

追加到 `tests/test_data_source.py` 末尾：

```python
# -------------------- csv --------------------

def _write_csv(tmp_path, rel: str, text: str, *, bom: bool = False,
               encoding: str = "utf-8") -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    data = text.encode(encoding)
    if bom:
        data = b"\xef\xbb\xbf" + data
    p.write_bytes(data)
    return p


def _csv_spec(**extra):
    spec = {"type": "csv", "path": "fish.csv", "id_column": "fish_id"}
    spec.update(extra)
    return spec


def test_csv_basic(tmp_path):
    _write_csv(tmp_path, "fish.csv",
               "fish_id,名字,重量\nF_A,河纹鱼,0.4~3\nF_B,小银鱼,0.05~0.4\n")
    items = load_data_source(_csv_spec(), tmp_path)
    assert [it["id"] for it in items] == ["F_A", "F_B"]
    assert items[0]["名字"] == "河纹鱼"


def test_csv_handles_bom(tmp_path):
    """在线表格导出的 CSV 常带 BOM，用 utf-8 读会让第一个列名多出 \\ufeff。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n", bom=True)
    items = load_data_source(_csv_spec(), tmp_path)
    assert items[0]["id"] == "F_A"


def test_csv_id_column_matched_by_prefix(tmp_path):
    _write_csv(tmp_path, "fish.csv",
               '"fish_id（资产文件名，如 Fish_RiverPattern）",名字\nF_A,河纹鱼\n')
    items = load_data_source(_csv_spec(), tmp_path)
    assert items[0]["id"] == "F_A"


def test_csv_columns_mapping(tmp_path):
    """长列名当占位符不好用（DSL 的字段参数还只认 ASCII），映射成短名。"""
    _write_csv(tmp_path, "fish.csv",
               '"fish_id（资产文件名）","图鉴描述（给玩家看的一句话）"\nF_A,一条会反光的鱼\n')
    items = load_data_source(
        _csv_spec(columns={"图鉴描述": "description"}), tmp_path)
    assert items[0]["description"] == "一条会反光的鱼"


def test_csv_mapped_column_keeps_original_name_too(tmp_path):
    """映射过的列，原始列名也保留 —— 两边都能在模板里引用。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n")
    items = load_data_source(_csv_spec(columns={"名字": "name"}), tmp_path)
    assert items[0]["name"] == "河纹鱼"
    assert items[0]["名字"] == "河纹鱼"


def test_csv_unmapped_columns_keep_original_name(tmp_path):
    """没映射的列也要保留，derived_fields 可能要用。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字,稀有度\nF_A,河纹鱼,普通\n")
    items = load_data_source(_csv_spec(columns={"名字": "name"}), tmp_path)
    assert items[0]["稀有度"] == "普通"


def test_csv_values_stay_strings(tmp_path):
    """不做类型推断：转了就丢原始表示（001、前导零、0.4~3 这种范围写法）。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,力量,编号,重量\nF_A,6,001,0.4~3\n")
    items = load_data_source(_csv_spec(), tmp_path)
    assert items[0]["力量"] == "6"          # 字符串，不是 int
    assert items[0]["编号"] == "001"        # 前导零还在
    assert items[0]["重量"] == "0.4~3"


def test_csv_skips_blank_rows(tmp_path):
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n\n,\nF_B,小银鱼\n")
    items = load_data_source(_csv_spec(), tmp_path)
    assert [it["id"] for it in items] == ["F_A", "F_B"]


def test_csv_empty_id_reports_physical_line(tmp_path):
    """行号必须是文件里的物理行，且断言完整片段 —— 只断言数字会被路径里的数字满足。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n,小银鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    msg = str(ei.value)
    assert "第 3 行" in msg
    assert "fish_id" in msg


def test_csv_line_number_survives_multiline_cell(tmp_path):
    """多行单元格会让「第几条记录」和「第几行」错开，必须按物理行报。"""
    _write_csv(tmp_path, "fish.csv",
               'fish_id,描述\nF_A,"第一行\n第二行"\n,缺少ID\n')
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    assert "第 4 行" in str(ei.value)


def test_csv_duplicate_header_raises(tmp_path):
    """重复列名会让 id 取自前列、字段值取自后列，prompt 和文件名对不上。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,fish_id,名字\nF_A,F_B,河纹鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    msg = str(ei.value)
    assert "fish_id" in msg
    assert "重复" in msg


def test_csv_duplicate_header_after_strip_raises(tmp_path):
    """去空白之后才重复的也要抓到。"""
    _write_csv(tmp_path, "fish.csv", "fish_id, fish_id ,名字\nF_A,F_B,河纹鱼\n")
    with pytest.raises(ValueError):
        load_data_source(_csv_spec(), tmp_path)


def test_csv_alias_colliding_with_existing_column_raises(tmp_path):
    """别名撞上已有列名：谁覆盖谁取决于列顺序，必须拒绝而不是碰运气。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字,name\nF_A,河纹鱼,RiverFish\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(columns={"名字": "name"}), tmp_path)
    assert "name" in str(ei.value)


def test_csv_two_sources_to_same_alias_raises(tmp_path):
    _write_csv(tmp_path, "fish.csv", "fish_id,名字,别名\nF_A,河纹鱼,小河鱼\n")
    with pytest.raises(ValueError):
        load_data_source(
            _csv_spec(columns={"名字": "label", "别名": "label"}), tmp_path)


def test_csv_alias_to_id_raises(tmp_path):
    """id 是保留字段，由 id_column 决定。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(columns={"名字": "id"}), tmp_path)
    assert "id" in str(ei.value)


def test_csv_row_wider_than_header_raises(tmp_path):
    """多出来的单元格静默丢掉的话，数据错了也没人知道。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼,多余的\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    assert "第 2 行" in str(ei.value)


def test_csv_short_row_fills_empty(tmp_path):
    """短行补空字符串，这是常见且无害的。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字,稀有度\nF_A,河纹鱼\n")
    items = load_data_source(_csv_spec(), tmp_path)
    assert items[0]["稀有度"] == ""


def test_csv_missing_id_column_raises(tmp_path):
    _write_csv(tmp_path, "fish.csv", "名字,重量\n河纹鱼,0.4\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    assert "fish_id" in str(ei.value)


def test_csv_requires_id_column_field(tmp_path):
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source({"type": "csv", "path": "fish.csv"}, tmp_path)
    assert "id_column" in str(ei.value)


def test_csv_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_data_source(_csv_spec(path="nope.csv"), tmp_path)


def test_csv_empty_file_raises(tmp_path):
    _write_csv(tmp_path, "fish.csv", "")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    assert "表头" in str(ei.value)


def test_csv_blank_header_raises(tmp_path):
    """开头的空行会被当成表头，这跟数据区的空行不一样，得报出来。"""
    _write_csv(tmp_path, "fish.csv", ",,\nfish_id,名字\nF_A,河纹鱼\n")
    with pytest.raises(ValueError) as ei:
        load_data_source(_csv_spec(), tmp_path)
    assert "表头" in str(ei.value)


def test_csv_columns_not_a_dict_raises(tmp_path):
    """`or {}` 会让 [] 和 "" 绕过类型检查，必须显式判断。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n")
    for bad in ([], "", ["名字"]):
        with pytest.raises(ValueError) as ei:
            load_data_source(_csv_spec(columns=bad), tmp_path)
        assert "columns" in str(ei.value)


def test_csv_custom_encoding(tmp_path):
    _write_csv(tmp_path, "fish.csv", "fish_id,名字\nF_A,河纹鱼\n", encoding="gbk")
    items = load_data_source(_csv_spec(encoding="gbk"), tmp_path)
    assert items[0]["名字"] == "河纹鱼"


def test_csv_filter_still_works(tmp_path):
    """filter 是所有数据源共用的，csv 不该例外。"""
    _write_csv(tmp_path, "fish.csv", "fish_id,稀有度\nF_A,普通\nF_B,稀有\n")
    items = load_data_source(_csv_spec(filter={"稀有度": "稀有"}), tmp_path)
    assert [it["id"] for it in items] == ["F_B"]


def test_csv_filter_is_string_comparison(tmp_path):
    """CSV 值是字符串，filter 用严格相等 —— 写 6 匹配不到 "6"。

    这是当前行为，文档里要写明，免得有人以为 filter 会帮忙转类型。
    """
    _write_csv(tmp_path, "fish.csv", "fish_id,力量\nF_A,6\n")
    assert load_data_source(_csv_spec(filter={"力量": 6}), tmp_path) == []
    assert len(load_data_source(_csv_spec(filter={"力量": "6"}), tmp_path)) == 1
```

- [ ] **Step 3: 跑测试确认失败**

Run: `python -m pytest tests/test_data_source.py -k csv -q`
Expected: FAIL — 绝大多数报 `未知 data_source type: 'csv'`

- [ ] **Step 4: 实现 loader**

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

    单元格值一律保持字符串：CSV 没有类型信息，一旦转换就丢了原始表示
    （"001" 的前导零、"0.4~3" 这种范围写法），而且同一列的取值类型会变得
    不稳定。注意现有 derived_fields 的 DSL 只有 join/upper/lower/title，
    没有数值转换，字段参数也只认 ASCII 标识符。

    宁可报错不要静默丢数据：重复列名、超宽行、别名撞车都直接抛，
    因为它们会让 prompt 里的 {字段} 和输出文件名对不上，那种 bug 极难查。
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
        reader = csv.reader(f)
        # 记录每条记录的**起始物理行**：单元格里可以有换行，
        # 「第几条记录」和「第几行」会错开，报错要按人看得到的行号说。
        records: list[tuple[int, list[str]]] = []
        prev_end = 0
        for row in reader:
            records.append((prev_end + 1, row))
            prev_end = reader.line_num

    if not records:
        raise ValueError(f"CSV 是空的，读不到表头: {full}")

    header = [h.strip() for h in records[0][1]]
    if not any(header):
        raise ValueError(
            f"{full} 的表头是空的（第 1 行没有任何列名）。"
            "开头如果有空行，删掉它 —— 表头必须是第一行。"
        )

    seen_cols: dict[str, int] = {}
    for idx, col in enumerate(header):
        if not col:
            continue
        if col in seen_cols:
            raise ValueError(
                "{} 的表头有重复列名 {!r}（第 {} 列和第 {} 列）。"
                "重复列会让 id 取自前一列、字段值取自后一列，"
                "prompt 里的占位符和输出文件名就对不上了。".format(
                    full, col, seen_cols[col] + 1, idx + 1
                )
            )
        seen_cols[col] = idx

    id_col = _match_column(id_column, header, where="id_column")
    id_idx = header.index(id_col)

    # columns: {表里的列名(短名): item 里的字段名}
    mapping_raw = spec.get("columns")
    if mapping_raw is None:
        mapping_raw = {}
    if not isinstance(mapping_raw, dict):
        raise ValueError(
            f"data_source.columns 必须是映射（列名 → 字段名），"
            f"实际是 {type(mapping_raw).__name__}"
        )

    renames: dict[str, str] = {}
    alias_from: dict[str, str] = {}
    for src_name, dst_name in mapping_raw.items():
        actual = _match_column(str(src_name), header, where="columns 的键")
        dst = str(dst_name)
        if dst == "id":
            raise ValueError(
                "columns 不能把 {!r} 映射成 'id' —— id 是保留字段，"
                "由 id_column 决定。".format(actual)
            )
        if dst in seen_cols:
            raise ValueError(
                "columns 把 {!r} 映射成 {!r}，但表里已经有一列叫 {!r}。"
                "谁覆盖谁取决于列顺序，所以这里直接拒绝：换个别名。".format(
                    actual, dst, dst
                )
            )
        if dst in alias_from:
            raise ValueError(
                "columns 把 {!r} 和 {!r} 都映射成了 {!r}，只能留一个。".format(
                    alias_from[dst], actual, dst
                )
            )
        alias_from[dst] = actual
        renames[actual] = dst

    items: list[dict] = []
    for line_no, row in records[1:]:
        if not any((cell or "").strip() for cell in row):
            continue        # 整行空：导出的 CSV 常带尾部空行

        if len(row) > len(header):
            raise ValueError(
                "{} 第 {} 行有 {} 个单元格，表头只有 {} 列。"
                "多出来的会被丢掉，所以这里直接报错 —— 检查这行是不是多了逗号。"
                .format(full, line_no, len(row), len(header))
            )

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
                "{} 第 {} 行的 {!r} 是空的。id 决定输出文件名，不能为空 —— "
                "删掉这行或补上 id。".format(full, line_no, id_col)
            )
        item["id"] = raw_id
        items.append(item)

    return items
```

- [ ] **Step 5: 接进分派**

`load_data_source` 里，把：

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

同一函数的 docstring 里 spec 字段说明改成：

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

- [ ] **Step 6: 跑全套测试**

Run: `python -m pytest tests/ -q`
Expected: 全绿，总数 229 + 5(Task 1) + 26(本任务新增，test_unknown_type 是改不是加) = **260**

若数字对不上，先查是不是漏改了 `test_unknown_type`。

---

### Task 3: 端到端集成测试 + 文档

**[评审]** 新增本任务。前两个任务的测试止于 loader，证明不了 CSV 能穿过 filter、
derived_fields、prompt 渲染真正变成 batch —— 这个仓库刚因为「只测消费端不测生产端」
漏过一个字段透传 bug。

**Files:**
- Test: `tests/test_main_flow.py`（追加一条）
- Modify: `examples/README.md`

**Interfaces:**
- Consumes: Task 2 的 `type: csv` 数据源
- Produces: 无新接口

- [ ] **Step 1: 写端到端测试**

追加到 `tests/test_main_flow.py` 末尾：

```python
def test_csv_data_source_end_to_end(tmp_project, mock_subprocess_run):
    """CSV → filter → 别名 → prompt → batch，全程不手写中间产物。"""
    calls, _ = mock_subprocess_run
    csv_path = tmp_project / "fish.csv"
    csv_path.write_text(
        '"fish_id（资产文件名）",名字,稀有度\n'
        "F_River,河纹鱼,普通\n"
        "F_Silver,小银鱼,稀有\n",
        encoding="utf-8",
    )
    cfg = tmp_project / "asset-config.yaml"
    conf = _minimal_config()
    conf["categories"]["ingredients"] = {
        "aspect_ratio": "1:1",
        "data_source": {
            "type": "csv",
            "path": "fish.csv",
            "id_column": "fish_id",
            "columns": {"名字": "name"},
            "filter": {"稀有度": "稀有"},
        },
        "prompt_template": "A fish named {name}, rarity {稀有度}.",
    }
    _write_yaml(cfg, conf)

    assert ga.main(["--config", str(cfg), "ingredients"]) == 0
    batch = json.loads(Path(calls[0]["cmd"][2]).read_text(encoding="utf-8"))
    assert len(batch["assets"]) == 1                      # filter 生效
    asset = batch["assets"][0]
    assert asset["name"] == "F_Silver"                    # id 来自前缀匹配的列
    assert asset["filename"] == "F_Silver.png"
    assert "小银鱼" in asset["prompt"]                     # 别名进了模板
    assert "稀有" in asset["prompt"]                       # 原始列名也能用
```

- [ ] **Step 2: 跑测试确认通过**

Run: `python -m pytest tests/test_main_flow.py -k csv_data_source_end_to_end -q`
Expected: PASS（Task 2 做完后这条应当直接通过；若红说明 loader 与主流程没接上）

- [ ] **Step 3: 写文档**

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

CSV 的列会原样进入 item，所以如果表里恰好有 `seed` / `model` / `aspect_ratio` / `image`
这些列名，它们会被当成 item 级的生成参数 —— 而 CSV 里取出来的是**字符串**。需要这些控制
字段时，建议在 yaml 的 category 层显式写，别依赖表里的同名列。
````

- [ ] **Step 4: 跑全套测试**

Run: `python -m pytest tests/ -q`
Expected: 全绿，总数 **261**（260 + 本任务 1 条）

- [ ] **Step 5: 交付前自检**

逐条确认并在交付说明里写结果：

1. `git status --short` —— 只有计划允许的四个文件被修改，没有新增其他文件
2. `python -m pytest tests/ -q` 全绿，条数与上面对得上
3. 没有执行过 `git add` / `git commit` / 切分支
4. **报告「故意没做什么、为什么」** —— 实现中若发现计划某处写得不对或不够，
   不要默默改掉，写出来
