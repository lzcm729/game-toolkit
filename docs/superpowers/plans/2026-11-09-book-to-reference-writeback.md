# book-to-reference 写回 实施计划（4.19.0）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把导入 Sylvester 时走通的流程写回 `skills/book-to-reference`：维护者 skill、随包的任务书和格式说明、主流程必需的确定性脚本（带测试），以及一个执行型冷启动评测，发 4.19.0。

**Architecture:** 脚本平铺在 `skills/book-to-reference/scripts/`，每个文件管一个阶段的一类事，共用 `bookconf.py` 读每本书的配置、工作目录布局和交付目标。书的全文、中间产物和每本书的配置都在仓库外的工作目录里。测试用编造的微型书做夹具。移植正确与否靠「对照检查」：在作者本地的 Sylvester 工作目录副本上重跑，和旧产物或 tag `v4.18.0` 的发布文件比。

**Tech Stack:** Python 3.11（PyYAML；PyMuPDF 只给 PDF 转换用，模块里延迟导入）、pytest、Claude Code CLI（只在运行器、触发冒烟和冷启动里用）。

**Spec:** `docs/superpowers/specs/2026-11-09-book-to-reference-writeback-design.md`（写回稿 v0.3，D7–D11 全选 A）；它的前置 `docs/superpowers/specs/2026-11-08-book-import-pipeline-design.md`（导入稿）。两份都要读。

**移植源：** 作者本地的流水线脚本和任务书不在仓库里，路径由交办任务书给出。下文用「旧 `xxx.py`」「旧 `XXX-BRIEF.md`」指代它们。

## Global Constraints

- 仓库是公开的：正文、示例、测试、夹具里不写作者本机路径、项目名、平台 token。书的全文、分块和中间产物不进仓库；发布卡的 R 段摘句按导入稿 D6 保留。夹具一律编造。
- 每本书的配置 `book.yaml` 和工作目录都在仓库外。`book.yaml` 写明交付目标 `target_root`（本插件的源码副本）；工作目录本身，以及 `Paths` 解析出来的每个路径，都不能落在 `target_root` 里，也不能落在脚本所在的仓库里。
- 交付目标必须是源码副本：有 `.git`、`.claude-plugin/plugin.json`、`skills/game-design-theory/`，路径里不含 `plugins/cache` 或 `plugins/marketplaces`。
- 确定性：遍历一律排序；平票规则写明；新写的文件一律 `encoding="utf-8", newline="\n"`；同样的输入逐字节相同的输出（写回稿原则 10）。
- **对照检查的比较规则**：作者本地的旧产物是 CRLF，比较前两边都规范成 UTF-8 加 LF，记下原始和规范化后的 sha256；和 tag `v4.18.0` 的发布文件比，比较提交后的形式：暂存 `skills/game-design-theory`，确认 `git diff --cached --quiet v4.18.0 -- skills/game-design-theory` 退出 0，暂存后的文件集合与 tag 一致，比完撤销暂存并重置该目录。本次生成的文件另外用 `git show v4.18.0:<路径>` 的原始字节严格比。期望和快照先锁住，不一致就修脚本，不改期望。**审核方 2026-11-09 改，用户未拍板。**
- 脚本只从参数和 `book.yaml` 取路径，不写死任何路径；Windows 和 POSIX 都要能跑；工具调用里的路径先把 `\` 换成 `/`。
- 每个脚本都有 CLI，任务书和 SKILL.md 里写的命令只能用本计划定义的 CLI。审计类脚本发现问题就退出 1，不只打印。
- pytest 里不联网、不调模型、不花钱；要调模型的只在 `runner.py` 和 `evals/book-to-reference-cold-start/` 里，不进普通测试。
- `book-to-reference` 的 description 不超过 1024 字符（`scripts/tests/test_skill_files.py` 已查）。
- 盲评的对照表（key）和评分包分开写；评分包里不能出现能认出版本的标记：页码、参考文件名，以及 `book.yaml` 的 `mask_names` 里列的全部作者和书名（含另外三本书）。
- 口径 B 的判法不改（导入稿第 2 节第 4 条：旧覆盖组、新增组**各自**不差，没有确认过的实质退步，未决不放行），只按写回稿原则 12、13 补。
- 复制 cangjie-skill 的实质文字时保留其 MIT 许可声明（导入稿 D5）。
- 新的测试文件名在全仓库唯一（pytest 用默认的 prepend 导入，同名测试模块会冲突）。

## Review Focus

1. **工作目录或产物路径落进了实际交付的源码仓库**（比如 `Paths.source` 被覆盖成仓库里的路径，或者从安装缓存加载这个 skill、往另一个源码副本写）：脚本应在写任何文件之前报错退出。测试在 Task 1。
2. **交付目标是安装缓存**：应报错，不能改缓存里的 skill。测试在 Task 1。
3. **运行中断、失败或读文件被拒**：没有成功的最终回答的运行不能算完成、不能被跳过、不能进评分；被拒绝的 Read 不能算读到卡。测试在 Task 6。
4. **口径 B 的判定被合计数或归因列改写**：旧覆盖组的改善不能抵新增组的退步；归因信息变了，计数、实质退步标记和判定都不能变；有缺评分、重复评分或未决时不能自动判通过。测试在 Task 7。
5. **公开化抹掉了来源性质和限制**：把「依据不足」「原图缺失」「合成演练」这类说明当残留删掉，或者替换后丢了分支边界。测试在 Task 5。

---

### Task 1: 配置、工作目录与交付目标（`bookconf.py`）

**Files:**
- Create: `skills/book-to-reference/scripts/bookconf.py`
- Create: `skills/book-to-reference/references/workdir.md`
- Test: `skills/book-to-reference/tests/test_bookconf.py`
- Create: `skills/book-to-reference/tests/fixtures/microbook/`（编造的三章小书：`source/microbook.md` 带 `[p.N]`、`BOOK_OVERVIEW.md` 带任务表、`book.yaml`；后续任务往里加文件）
- Create: `skills/book-to-reference/tests/fixtures/plugin/`（最小插件树：`.claude-plugin/plugin.json`、`skills/game-design-theory/SKILL.md` 带锚点、`references/`；**不放 `.git`**）
- Create: `skills/book-to-reference/tests/conftest.py`：把 `scripts/` 加进 `sys.path`；夹具 `microbook`（复制到 `tmp_path`）、`plugin_copy`（复制到 `tmp_path` 并现场建一个 `.git/` 目录）；把 `microbook/book.yaml` 的 `target_root` 改写成 `plugin_copy`

**Interfaces:**
- Produces:
  - `@dataclass BookConfig`: `book_id: str`, `prefix: str`（如 `"sylvester-"`）, `target_root: Path`, `mask_names: MaskNames`, `verify_groups: dict[str, list[str]]`, `entry_groups: dict[str, list[str]]`（两者都保持文件里的顺序）, `old_files: list[str]`, `paths: Paths`, `skill_md: SkillMdConfig`, `rulings: list[Ruling]`, `residue_allow: list[str]`, `convert: dict`, `answer_compare: dict`
  - 两套分组的键空间不同，`workdir.md` 写明：`verify_groups` 的值是候选 `source_chapter` 解析出的章标签（数字章 `"1"`…，以及非数字部分的规范键 `"pre"`、`"p1"`…`"p3"`、`"quiz"`、`"end"`、`"books"`、`"sources"`，按书增减）；`entry_groups` 的值是单元号里的两位章号（`"00"`…）
  - `@dataclass MaskNames`: `authors: list[str]`, `titles: list[str]`
  - `@dataclass Paths`（相对工作目录，有默认值）: `source="source/<book_id>.md"`, `overview="BOOK_OVERVIEW.md"`, `candidates="candidates"`, `verify_in="verify/input"`, `verify_out="verify/out"`, `recheck_in="verify/recheck/input"`, `recheck_out="verify/recheck/out"`, `card_plan="stage2/CARD-PLAN.md"`, `cards="cards"`, `meta="meta"`, `glossary="candidates/glossary.md"`, `notes_out="landing/notes.md"`
  - `@dataclass SkillMdConfig`: `quick_ref_start: str`, `quick_ref_end: str`, `quick_ref_file: str`, `table_start: str`, `table_end: str`, `table_heading: str`, `when_to_use_anchor: str`, `when_to_use_line: str`, `description_file: str | None`
  - `@dataclass Ruling`: `find: str`, `replace: str`, `why: str`, `scope: Literal["cards", "notes", "all"]`
  - `load_config(workdir: Path) -> BookConfig`
  - `resolve(cfg: BookConfig, workdir: Path, name: str) -> Path`
  - `check_target(target_root: Path) -> None`：不满足 Global Constraints 里的源码副本条件就 `raise ValueError`
  - `open_workdir(workdir: Path) -> BookConfig`：`load_config`，再 `check_target(cfg.target_root)`，再确认工作目录和 `Paths` 的每个解析结果都不在 `cfg.target_root` 里、也不在 `find_repo_root(Path(__file__))` 里。**后续每个脚本的 CLI 都经它打开工作目录**
  - `find_repo_root(start: Path) -> Path | None`：往上找含 `.claude-plugin/plugin.json` 的目录
  - CLI：`python bookconf.py check <workdir>`，打印配置摘要，出错退出 1

- [ ] **Step 1: 写测试**
  - `test_load_microbook_config`：`prefix == "micro-"`，两套分组的键顺序和文件一致，`paths.cards == "cards"`
  - `test_paths_override`：`paths: {cards: ".cangjie/capabilities/cards"}` 生效
  - `test_missing_required_field`：删掉 `prefix` 抛 `ValueError`，消息含 `prefix`
  - `test_ruling_requires_why`：ruling 缺 `why` 抛 `ValueError`（写回稿原则 11）
  - `test_workdir_inside_target_rejected`：工作目录放进 `plugin_copy` 里，`open_workdir` 抛错
  - `test_resolved_path_inside_target_rejected`：工作目录在外，但 `paths.source` 覆盖成 `plugin_copy` 里的绝对路径，`open_workdir` 抛错
  - `test_cache_target_rejected`：`target_root` 的路径里含 `plugins/cache`，`check_target` 抛错
  - `test_target_without_git_rejected`：没有 `.git` 的插件树被拒
  - `test_cli_rejects_bad_workdir`：`python bookconf.py check <仓库里的临时目录>` 退出 1，且没有写出任何文件
- [ ] **Step 2: 跑测试，确认失败**：`pytest skills/book-to-reference/tests/test_bookconf.py -v`，预期 `ModuleNotFoundError: bookconf`
- [ ] **Step 3: 实现 `bookconf.py`**；`references/workdir.md` 写工作目录布局和 `book.yaml` 每个字段，分「机械参数」和「内容裁决」两节，附微型书的完整例子
- [ ] **Step 4: 跑测试，确认通过**
- [ ] **Step 5: 提交**：`feat(book-to-reference): 每本书的配置、工作目录与交付目标`

### Task 2: PDF 转带页码的文本（`pdf_convert.py`）

**Files:**
- Create: `skills/book-to-reference/scripts/pdf_convert.py`（合并旧 `probe_pdf.py`、`font_survey.py`、`font_pages.py`、`pdf_to_md.py`、`verify_pages.py`）
- Test: `skills/book-to-reference/tests/test_pdf_convert.py`

**Interfaces:**
- Consumes: `open_workdir`、`BookConfig.convert`（Task 1）
- Produces:
  - `survey_fonts(pdf: Path) -> list[FontRow]`；`FontRow(font: str, size: float, count: int, sample: str, pages: list[int])`，按次数降序再按字体名排序（合并旧 `font_survey` 和 `font_pages`）
  - `convert(pdf: Path, conv: dict) -> str`。`conv` 的键，默认值取旧 `pdf_to_md.py` 的行为：
    - `page_offset: int`（印刷页码 = PDF 页 − offset；PDF 页 ≤ offset 时标 `fm-<PDF 页>`）
    - `start_page: int`、`stop_page: int | None`（PDF 页，前闭后开；旧值 7、395）
    - `title_min_size: float`（≥ 它的行丢弃；旧值 18）
    - `classes: list[{kind, font_contains, size | null, tol}]`，按顺序第一个命中的生效，`kind ∈ {h3, h4, callout, vignette, skip}`；没命中的是 body
    - `page_number: {font_contains, pattern}`（旧值 `ScalaLF`、阿拉伯和罗马数字）
    - `header_max_y: float`（纵坐标小于它的 body 和 skip 行丢弃；旧值 45）
    - `para_indent_x: float`（body 行横坐标 ≥ 它就另起一段；旧值 84）
    - `outline: {part_pattern, chapter_pattern}`（目录大纲一级的 Part 写成 `# Part X: 标题`，`N 标题` 写成 `## Chapter N: 标题`，其余 `# 标题`）
    - `header: str`（输出文件开头的说明文字）
  - `find_page(source_md: str, phrase: str) -> int | None`：短语第一次出现所在的印刷页码（写回稿第 5 节「页码抽查」）
  - CLI：`python pdf_convert.py survey <pdf>` / `convert <workdir> <pdf>`（写到 `Paths.source`）/ `page <workdir> "<短语>"`
  - `fitz` 只在 `survey_fonts` 和 `convert` 里导入；没装 PyMuPDF 时 `find_page` 照常可用
- [ ] **Step 1: 写测试**（需要 PDF 的测试各自 `pytest.importorskip("fitz")`，用 PyMuPDF 现场生成一份 4 页的 PDF：两种字号、一行页边要点字体、一行页眉、一个页码）
  - `test_survey_lists_fonts_with_pages`
  - `test_convert_page_markers`：`page_offset=1` 时依次出现 `[p.fm-1]`、`[p.1]`…`[p.3]`
  - `test_convert_classes_in_order`：配置的大字号行变 `###`，页边要点变 `> **[Callout]** …`，页眉和页码不出现
  - `test_convert_paragraph_indent`：缩进的一行另起一段，连字符断行被接上
  - `test_stop_page`：`stop_page=4` 时第 4 页的文字不出现
  - `test_find_page_without_fitz`（不 importorskip）：微型书里第 2 页才有的短语返回 `2`，不存在返回 `None`
- [ ] **Step 2: 跑测试，确认失败**
- [ ] **Step 3: 实现**，行为照旧 `pdf_to_md.py`，常量全部从 `conv` 读
- [ ] **Step 4: 跑测试，确认通过**
- [ ] **Step 5: 对照检查（本地）**：给 Sylvester 的 `book.yaml` 写 `convert` 段，在工作目录副本上重转，按 Global Constraints 的比较规则和现有 `source/designing-games.md` 一致
- [ ] **Step 6: 提交**：`feat(book-to-reference): PDF 转带页码的文本`

### Task 3: 卡片核对（`check_cards.py`）

**Files:**
- Create: `skills/book-to-reference/scripts/check_cards.py`（合并旧 `check_quote_pages.py`、`check_step_pages.py`、`check_card_plan.py`、`check_cards_vs_plan.py`）
- Test: `skills/book-to-reference/tests/test_check_cards.py`
- 夹具：`microbook/` 加 `stage2/CARD-PLAN.md`、`cards/*.md`、`meta/*.yaml`、`verify/out/G1.yaml`

**Interfaces:**
- Consumes: Task 1
- Produces:
  - `pages_of(attribution: str) -> frozenset[int]`：`p.156–157`、`pp.12-14`、`p.5, 7` 都解析成**离散页集合**，不压成最小到最大的区间
  - `quote_pages(source_md: str, card_md: str) -> list[QuoteResult]`；`QuoteResult(card_line: int, pages_claimed: frozenset[int], found_on: list[int], status: Literal["OK", "OFFPAGE", "MISS", "NOPAGE"])`；判 OK 要求摘句的命中页和 `pages_claimed` 有交集
  - `step_pages(card_md: str) -> list[StepResult]`；`StepResult(line: int, text: str, ok: bool)`；放行标记照旧 `MARK` 正则
  - `plan_problems(cfg, workdir) -> list[str]`：每个 verified 单元恰好分到一张卡；计划里的卡都有 card 和 meta；meta 的 `units`、卡头注释和计划一致；每个单元在卡里有分支标题
  - CLI：`python check_cards.py <workdir> [--only quotes|steps|plan]`；`OFFPAGE`、`MISS`、`NOPAGE`、失败步骤、计划问题都让退出码为 1；输出末尾一句「页码在场不等于那一页支持这一步」
- [ ] **Step 1: 写测试**
  - `test_quote_on_cited_page`
  - `test_quote_wrong_page_fails`：标注页改成别的页，`status == "OFFPAGE"`
  - `test_quote_discontinuous_pages`：标 `p.1, 3`、摘句只在第 2 页，`status == "OFFPAGE"`（旧脚本判成 OK）
  - `test_quote_without_page_fails_exit`：去掉标注页，`status == "NOPAGE"`，CLI 退出 1（旧脚本退出 0）
  - `test_quote_word_changed_fails`：`status == "MISS"`
  - `test_step_without_page_fails`、`test_step_with_convention_mark_passes`
  - `test_plan_unit_unassigned`
- [ ] **Step 2: 跑测试，确认失败**
- [ ] **Step 3: 实现**，其余判定照旧（`SLACK = 0`，英文行至少 5 个 ASCII 词等）
- [ ] **Step 4: 跑测试，确认通过**
- [ ] **Step 5: 对照检查（本地）**：Sylvester 工作目录副本上，摘句 142/142 OK，E 段 639/657 步通过（其余 18 步和旧脚本报的同一批），计划检查无问题
- [ ] **Step 6: 提交**：`feat(book-to-reference): 卡片核对（摘句页码、步骤页码、卡与计划）`

### Task 4: 任务、候选与验证单元（`stage1.py`、`verify_units.py`）

**Files:**
- Create: `skills/book-to-reference/scripts/stage1.py`（旧 `coverage_audit.py`、`split_candidates.py`，加任务编号唯一检查）
- Create: `skills/book-to-reference/scripts/verify_units.py`（旧 `aggregate_verify.py`、`make_recheck_input.py`、`apply_recheck.py`、`dump_units.py`、`show_support.py`、`show_units.py`）
- Test: `skills/book-to-reference/tests/test_stage1.py`、`skills/book-to-reference/tests/test_verify_units.py`
- 夹具：`microbook/candidates/*.md`（五类候选各几条，含一个 YAML 写坏的块）、`verify/input/`、`verify/out/`、`verify/recheck/out/R1.yaml`

**Interfaces:**
- Consumes: Task 1
- Produces:
  - `read_tasks(overview_md: str) -> dict[str, str]`：任务号重复就 `raise ValueError` 并列出重复项
  - `coverage(cfg, workdir) -> CoverageResult`；`CoverageResult(by_task: dict[str, dict[str, int]], problems: list[str])`：YAML 解析失败、任务没有任何可执行候选都进 `problems`
  - `split_candidates(cfg, workdir) -> dict[str, dict[str, list]]`：按 `cfg.verify_groups` 分组；有候选的章标签不在任何组里就 `raise ValueError`
  - `aggregate(cfg, workdir) -> AggregateResult`；`AggregateResult(problems: list[str], counts: dict[str, int])`：写 verified / references / needs-review / rejected / coverage-audit / `verify/_flags.md`；遗漏 disposition、单元号重复、缺 coverage 行进 `problems`；判宽信号照旧 `DOUBT` 正则
  - `recheck_input(cfg, workdir, batch: str, ids: list[str]) -> Path`：只留 `KEEP` 字段
  - `apply_recheck(cfg, workdir, batches: list[str] | None, dry: bool) -> list[str]`：幂等；改动前备份一次 `.pre-recheck.bak`
  - `show(cfg, workdir, ids: list[str]) -> str`：打印单元的完整 YAML、它的原始复核记录（含逐步来源等级），以及 `c-*`、`ce-*`、`g-*` 支持条目（写卡和传播核对要用）
  - CLI：`python stage1.py tasks|coverage|split <workdir>`；`python verify_units.py aggregate|recheck-input|apply-recheck|show <workdir> ...`；`problems` 非空退出 1
- [ ] **Step 1: 写测试**
  - `test_duplicate_task_id_rejected`、`test_coverage_counts`
  - `test_coverage_reports_bad_yaml`：写坏的块进 `problems`，CLI 退出 1（旧脚本吞掉了它）
  - `test_unmapped_chapter_rejected`：候选来自配置里没有的章标签
  - `test_non_numeric_chapter_key`：`source_chapter` 是 Part 引言的候选归到配置里 `"p1"` 那组
  - `test_recheck_input_strips_verdicts`：输出里没有 `decision`、`decision_reason`、`gaps`、`V1`
  - `test_apply_recheck_idempotent`：跑两次，第二次返回空列表、文件不变、备份只有一份
  - `test_aggregate_problems_block`：删掉一条 disposition，`problems` 非空，CLI 退出 1
  - `test_show_includes_raw_recheck`
- [ ] **Step 2: 跑测试，确认失败**
- [ ] **Step 3: 实现**
- [ ] **Step 4: 跑测试，确认通过**
- [ ] **Step 5: 对照检查（本地）**：Sylvester 工作目录**副本**上跑 `aggregate`，四份汇总按比较规则和现有文件一致；`apply_recheck` 对已应用的批次返回空列表
- [ ] **Step 6: 提交**：`feat(book-to-reference): 任务、候选与验证单元的审计脚本`

### Task 5: 公开化与接入（`publicize.py`、`integrate.py`）

**Files:**
- Create: `skills/book-to-reference/scripts/publicize.py`
- Create: `skills/book-to-reference/scripts/integrate.py`（旧 `integrate_cards.py`、`build_book_notes.py`、`splice_skill_md.py`、`set_description.py`）
- Test: `skills/book-to-reference/tests/test_publicize.py`、`skills/book-to-reference/tests/test_integrate.py`

**Interfaces:**
- Consumes: Task 1（`Ruling`、`SkillMdConfig`、`entry_groups`、`residue_allow`、`check_target`）、Task 4（`read_tasks`）
- Produces:
  - `publicize.PIPELINE_TERMS: list[tuple[str, str]]`：通用的流程用语替换（取旧 `integrate_cards.PUBLIC`、旧 `build_book_notes.PUBLIC` 里不针对某一条的那些）
  - `publicize.RESIDUE_PATTERNS: list[str]`：单元、复核、待核查、参考单元、提取器、任务表、overview、批判节；单元号 `u\d\d-\d\d`、候选号 `p\d-\d\d`、术语号 `g-\d+`、任务号 `t\d\d-\d\d`。**不含**「演练」：「合成演练」是来源说明，必须保留
  - `publicize.apply(text: str, rulings: list[Ruling], scope: str) -> str`：先套 `rulings`，再套 `PIPELINE_TERMS`；`>` 开头的行不动
  - `publicize.scan(text: str, allow: list[str]) -> list[tuple[int, str]]`：先把每个 `allow` 短语的出现位置挖掉，再在剩下的文字里找残留（只豁免命中的片段，不豁免整行）；卡头 HTML 注释行跳过
  - `integrate.main_chapter(units: list[str]) -> str`：按次数，平票先选非 `"00"`，再选章号小的
  - `integrate.safe_cut(s: str, limit: int) -> str`
  - `integrate.run(workdir: Path) -> IntegrateReport`：经 `open_workdir` 拿配置和目标；写卡（改名、卡间引用换文件名、开头插用法句、公开化）、写 notes、删 `old_files`、按 `entry_groups` 生成选卡表、拼进 SKILL.md、换 description（有 `description_file` 时，超 1024 拒绝）；最后对写出的每个文件跑 `scan(…, cfg.residue_allow)`，有残留就退出 1 并列出位置；单元的章号不在任何 `entry_groups` 里就报错并列出（旧代码默默归到最后一组）
  - `IntegrateReport(written: list[Path], deleted: list[Path], residue: list[tuple[Path, int, str]])`
  - CLI：`python integrate.py <workdir>`；`python publicize.py scan <workdir> <file>...`
- 用法句和选卡表前言照抄旧 `integrate_cards.py`；`QUICK` 块的内容不进脚本，改由 `skill_md.quick_ref_file` 提供；旧脚本里针对 Sylvester 某一条的替换、`OVERRIDE_WHY`、`OVERRIDE_RELATED` 改写成 Sylvester `book.yaml` 的 `rulings`，每条写 `why`

- [ ] **Step 1: 写测试**
  - `test_tie_prefers_real_chapter`：`main_chapter(["u00-01","u00-02","u11-01","u11-05"]) == "11"`；用不同 `PYTHONHASHSEED` 起 5 个子进程，结果都一样
  - `test_unmapped_entry_chapter_rejected`
  - `test_safe_cut_keeps_backtick_name`
  - `test_rulings_before_generic_terms`
  - `test_quote_lines_untouched`：`>` 开头、含「单元」的行不被替换
  - `test_scan_keeps_source_labels`（Review Focus 5）：「以下是合成演练」「依据不足」「原图缺失」不报残留，`apply` 之后也都还在
  - `test_scan_allow_is_fragment_only`：一行里既有豁免的「分析单元」又有「参考单元」，后者照报
  - `test_integrate_microbook_end_to_end`：在 `plugin_copy` 上 `run`，卡文件名带前缀、选卡表在锚点之间、旧文件被删、无残留；再跑一次，所有文件逐字节不变
- [ ] **Step 2: 跑测试，确认失败**
- [ ] **Step 3: 实现**
- [ ] **Step 4: 跑测试，确认通过**
- [ ] **Step 5: 对照检查（本地，写回稿 D9 的「复现」）**：Sylvester 工作目录快照先锁住（记 sha256）；`book.yaml` 的 `target_root` 指向一份 `git worktree add <临时目录> v4.17.1` 的隔离副本（接入之前的状态：`old_files` 还在，SKILL.md 还是旧的；description 用 `description_file` 换）；`run` 后，副本里 `skills/game-design-theory/` 下的文件集合、每个文件的字节，都和 `git show v4.18.0:<路径>` 一致（`git status --porcelain` 只允许出现与 tag 一致的改动，不能有多出的未跟踪文件）。Sylvester 4.18.0 的 14 行合法用语（2 处书内「单元」、12 处「合成演练」）靠 `residue_allow` 和 `RESIDUE_PATTERNS` 放行，不改发布文件
- [ ] **Step 6: 提交**：`feat(book-to-reference): 公开化与接入，生成可复现`

### Task 6: 运行器与消费链统计（`runner.py`、`chain.py`）

**Files:**
- Create: `skills/book-to-reference/scripts/runner.py`（替旧 `run_headless.sh`、`run_batch.sh`）
- Create: `skills/book-to-reference/scripts/chain.py`（旧 `summarize_run.py`、`chain_stats.py` 的口径；旧 `compare_variants.py`、`entry_table.py`、`show_run.py` 只保留主流程用到的逐题表）
- Create: `skills/book-to-reference/references/host.md`
- Test: `skills/book-to-reference/tests/test_runner.py`、`skills/book-to-reference/tests/test_chain.py`
- 夹具：`tests/fixtures/runs/`（手写的 stream-json：调用 skill 并成功读两张卡；没调用；没有 `result` 事件的半截文件；`result` 是错误（如预算耗尽）；一次 Read 被拒；Read 路径带反斜杠）；`tests/fixtures/fake_claude.py`（按提示词吐出预制的 stream-json，并把收到的参数写进日志）

**Interfaces:**
- Produces:
  - `runner.Job(prompt_id: str, prompt: str, variant: str, plugin_dir: Path, rep: int)`
  - `runner.plan_jobs(prompts: list[tuple[str, str]], variants: dict[str, Path], reps: int) -> list[Job]`：顺序「每道题 → 每个重复 → 每个版本」（写回稿原则 12）
  - `runner.is_success(out: Path, batch_id: str) -> bool`：jsonl 的最终事件是 `type == "result"`、`subtype == "success"`、`is_error` 为假、`result` 非空，且 `<out>.meta.json` 的 `batch_id` 等于本批
  - `runner.run_batch(jobs, out_dir: Path, runs_root: Path, batch_id: str, lanes: int, budget_usd: float, model: str, claude_cmd: list[str]) -> list[Path]`：每次运行用 `runs_root` 下全新的空工作目录，本批共用一个全新的配置目录（`CLAUDE_CONFIG_DIR`）；参数照旧脚本：`-p`、`--plugin-dir`、`--add-dir <插件目录>`、`--model`、`--tools "Read,Glob,Grep,Skill"`、`--output-format stream-json --verbose`、`--no-session-persistence`、`--max-budget-usd`；`is_success` 的跳过，不成功的改名成 `.stale-<n>` 再跑；`meta.json` 记 `batch_id`、版本名、提示词 sha256、模型、Claude Code 版本（取 init 事件）
  - `runner.check_runs_root(runs_root: Path) -> None`：在用户主目录下面就 `raise ValueError`（往上找会读到用户自己的 CLAUDE.md）
  - CLI：`python runner.py <prompts.tsv> <out_dir> --variant NAME=DIR [--variant ...] --reps N --lanes N --budget USD --runs-root DIR --batch-id ID [--model M] [--claude CMD]`；API key 只从环境变量透传
  - `chain.Run(path, ok: bool, skills: list[str], reads: list[str], cost: float, answer: str | None, model: str, cc_version: str)`
  - `chain.parse_run(jsonl: Path) -> Run`：`ok` 的定义同 `is_success`（不看 meta）；`reads` 只收对应 `tool_result` 不是错误的 Read，路径 `\` 换成 `/`
  - `chain.counts(runs: list[Run], refs_marker: str, card_prefix: str) -> dict[str, int]`：键 `runs`、`failed`、`skill`、`skill_and_any_book_ref`、`skill_and_card`、`skill_but_no_book_ref`、`no_skill`；`failed` 的运行不进其余各键。「skill」指调用了本插件的任何 skill，不限 `game-design-theory`
  - `chain.per_question(dirs: dict[str, Path], card_prefix: str) -> str`
  - CLI：`python chain.py counts <runs_dir>... --card-prefix P` / `per-question NAME=DIR ... --card-prefix P`
- [ ] **Step 1: 写测试**
  - `test_plan_jobs_interleaves`：两题、两版本、两次重复，前四个 job 的版本依次 `a, b, a, b`
  - `test_partial_run_not_success`、`test_error_result_not_success`、`test_other_batch_not_success`（Review Focus 3）
  - `test_rerun_replaces_partial`：用 `fake_claude.py`；预置的半截文件被改名成 `.stale-1`，新文件成功
  - `test_runs_root_under_home_rejected`
  - `test_denied_read_not_counted`（Review Focus 3）：Read 被拒的那张卡不在 `reads` 里，`skill_and_card` 不加
  - `test_backslash_read_detected`：Windows 风格路径的成功 Read 计入 `skill_and_card`
  - `test_failed_runs_separate`：错误结果的运行计入 `failed`，不计入 `no_skill`
- [ ] **Step 2: 跑测试，确认失败**
- [ ] **Step 3: 实现**；`references/host.md` 写宿主要求：Claude Code 版本、为什么要全新配置目录（`--bare` 会去掉 Skill 工具）、工作目录为什么不能在用户主目录下、为什么要 `--add-dir`、API key 用环境变量、Codex 宿主没有独立上下文时这几步标「未独立验证」（导入稿原则 8）、`claude plugin eval` 以后可以接替哪一段（写回稿 D8）。不写本机路径
- [ ] **Step 4: 跑测试，确认通过**
- [ ] **Step 5: 对照检查（本地）**：第三次回归的运行目录上，激活数验收版 10、10，最终版 11、8；读卡数和旧口径（4、3；4、7）相比只允许因 Read 被拒而减少，减少的逐条列出。再用真 `claude` 跑 2 题 × 2 版本 × 1 次（约 0.6 美元），确认 `meta.json` 有模型和版本、两个版本交错
- [ ] **Step 6: 提交**：`feat(book-to-reference): 同批交错的无界面运行器和消费链统计`

### Task 7: 可达测试与盲评（`reach.py`、`grading.py`）

**Files:**
- Create: `skills/book-to-reference/scripts/reach.py`（旧 `build_reach_tasks.py`、`score_reach_live.py`）
- Create: `skills/book-to-reference/scripts/grading.py`（旧 `answer_text.py`、`pick_answer_tasks.py`、`build_grading_packets.py`、`build_regress2_packets.py`、`aggregate_answer_compare.py`、`aggregate_regress2.py`、`leak_check.py`）
- Create: `skills/book-to-reference/references/acceptance.md`
- Test: `skills/book-to-reference/tests/test_reach.py`、`skills/book-to-reference/tests/test_grading.py`

**Interfaces:**
- Consumes: `chain.parse_run`（Task 6）、`open_workdir`、`MaskNames`、`answer_compare`（Task 1）
- Produces:
  - 题目身份：`item_id`（任务号 `tNN-NN`、受保护能力 `p-*`、诱饵 `d*`/`x*`）和 `qid`（评测里的题号，`a001` 起）。`id_map.json` 是 `qid → item_id`，`items_meta.json` 是 `item_id → {group, required, source}`；两者由 `make_prompts` 一起写出，后面所有步骤都从这两个文件拿映射
  - `reach.expected_cards(cfg, workdir) -> dict[str, list[str]]`；`reach.pick(expected, per_card: int, seed: int, used: set[str]) -> list[str]`
  - `reach.score(runs_dir: Path, id_map: dict, expected: dict, card_prefix: str) -> dict[str, str]`：任务题 `STRICT / ANY / OTHER / NONE`，受保护题 `HIT / MISS`，诱饵 `REJECT / FIRED`；`ok` 为假的运行记 `FAILED`
  - `grading.mask(text: str, names: MaskNames) -> str`
  - `grading.pick_items(groups: dict, capabilities: dict, tasks: dict, used: set[str], cfg_answer: dict, seed: int) -> dict[str, dict]`：`cfg_answer` 含 `target_source`（如 `"sylvester"`，替旧脚本里写死的来源判断）、`quotas: {组: [必测, 可选]}`、`exclude_items`、`other_books: {书: 最少题数}`
  - `grading.make_prompts(items: dict, prompts_raw: dict, out_dir: Path, prefix: str = "a") -> tuple[Path, Path, Path]`：写 `prompts.tsv`（给 `runner.py`）、`id_map.json`、`items_meta.json`
  - `grading.build_packets(id_map: dict, rubric: dict, prompts_raw: dict, arms: dict[str, Path], reps: int, n_graders: int, seed: int, names: MaskNames, forced: dict[str, Path] | None = None) -> tuple[list[str], dict]`：`arms` 恰好两个键 `baseline`、`candidate`；每题 `2 × reps` 份回答随机标号，两组随机分 X、Y；`key` 记每个标号的 `{arm, rep, forced}` 和每题 `cmp1`（有 `forced` 时还有 `cmp2`）的 X、Y
  - `grading.aggregate(grades: list[dict], key: dict, id_map: dict, meta: dict, protocol: Literal["B", "pooled-required"], chain_by_q: dict[str, dict[str, list[bool]]] | None = None) -> AggregateResult`
    - `AggregateResult(per_question: list[Row], counts: dict[tuple[str, str], int], substantive: list[str], status: Literal["pass", "fail", "incomplete"], problems: list[str])`；`Row` 带 `qid, item_id, group, required, verdict（better/same/worse/undecided）, regression, difference, plugin_use`
    - `protocol="B"`（新书验收和今后的回归）：必测题按旧覆盖组（O、O-partial、O-other 合并）和新增组 N **分别**要求 worse ≤ better；任何写了退步类型的 worse 进 `substantive` 并使 `status="fail"`（是否可归因由人核，核完写进计划记录，脚本不替人放行）；有缺评分、重复评分、`undecided` 时 `status="incomplete"`
    - `protocol="pooled-required"`：只用来复现三次验收后回归按当时冻结规则得出的历史结论
    - `chain_by_q` 只填进 `plugin_use` 一列，**不参与**计数、`substantive` 和 `status`（写回稿原则 13）
  - `grading.leaks(packet_md: str, names: MaskNames) -> int`
  - CLI：`python grading.py pick|prompts|packets|aggregate|leaks <workdir> ...`；`python reach.py expected|pick|score <workdir> ...`
- [ ] **Step 1: 写测试**
  - `test_mask_hides_markers`：作者名、书名（含另外三本）、`p.12`、`micro-a.md` 都被替换；`docs/IDEAS.md` 保留
  - `test_packets_key_separate`、`test_packets_deterministic`
  - `test_b_protocol_groups_separate`（Review Focus 4）：O 组 3 好 0 差、N 组 0 好 1 差，`protocol="B"` 判 `fail`；同样的数据 `pooled-required` 判 `pass`
  - `test_attribution_invariant`（Review Focus 4）：同一份评分，`chain_by_q` 全 True、全 False、不给，三种情况的 `counts`、`substantive`、`status` 完全相同
  - `test_substantive_fails_b`：一题 worse 带「漏了必要步骤」，`status == "fail"`
  - `test_missing_or_duplicate_grade_incomplete`、`test_undecided_incomplete`
  - `test_optional_not_counted`
  - `test_reach_decoy_fired`、`test_reach_failed_run`
- [ ] **Step 2: 跑测试，确认失败**
- [ ] **Step 3: 实现**；`references/acceptance.md` 写口径 B（分组、冻结、判法，照导入稿第 2 节第 4 条）、两种协议的用途、原则 12 和 13 怎么执行、回答对比计划要写什么（题数、报价、种子、必测与可选、协议）、报告格式（逐题判定旁边列插件调用情况，这一列不改判定）、可达测试的判法
- [ ] **Step 4: 跑测试，确认通过**
- [ ] **Step 5: 对照检查（本地）**：
  - 第二次回归（regress-927abad）的评分包和 key 用新 `build_packets` 重建，按比较规则一致
  - `aggregate(protocol="pooled-required")` 在第二次、第三次回归上分别得出「必测 1 好 5 差，不过」「3 好 14 平 1 差，通过」
  - `aggregate(protocol="B")` 在第三次回归上得出 O 组 3 好 9 平 0 差、N 组 0 好 5 平 1 差，`status="fail"`（与历史结论不同，这是协议差别，不重判历史）
  - 第二轮回答对比（answer-compare-r2）上 `protocol="B"` 得出 O 组 4 好 8 平 0 差、N 组 1 好 5 平 0 差，`pass`
  - 新 `pick_items` 按第二轮的种子和已用题目重抽，得到同样 22 题
- [ ] **Step 6: 提交**：`feat(book-to-reference): 可达测试与盲评的确定性部分，口径 B 分组判定`

### Task 8: 任务书和格式说明

**Files:**
- Create: `skills/book-to-reference/references/card-format.md`（R/I/A1/A2/E/B 六段、用法句、页码与「约定 / 原书未说明 / 原图缺失 / 合成演练」的区分、篇幅；吸收旧 `template.md` 里还有用的命名规则和 Rouse 旧文件的例外）
- Create: `skills/book-to-reference/references/candidate-schema.md`（五类候选的字段和格式：方法、原则、案例、反例、术语；从 cangjie 提取器的输出格式改写，文末附 MIT 许可声明）
- Create: `skills/book-to-reference/references/method.md`（阶段 0、1、1.5、2 用到的方法要点：整书理解和读者任务、三重验证与严格口径、按意图合卡与分支边界的作用域；从 cangjie 方法论改写的部分注明出处，文末附 MIT 许可声明）
- Create: `skills/book-to-reference/references/briefs/` 下：`stage0-notes.md`、`stage1-extract.md`、`stage15-verify.md`、`recheck.md`、`card-writing.md`、`propagation.md`（复核结论到卡的核对和修卡）、`grouping.md`（旧覆盖组 / 新增组）、`consumers.md`（改消费方引用、改和新卡冲突的旧摘要、提醒 Codex 用户重新导出 agent）、`question-writer.md`、`rubric-writer.md`、`grader.md`、`content-review.md`（写回稿 D11）
- Test: `skills/book-to-reference/tests/test_briefs.py`

**Interfaces:**
- Consumes: 各脚本的 CLI（Task 1–7），任务书里写的命令只能用这些
- Produces: 上面的文件名（Task 9 的 SKILL.md 按这些名字链接）

- [ ] **Step 1: 写测试 `test_briefs.py`**
  - `test_briefs_self_contained`：`references/` 下所有 md 里不出现 `extractors/`、`methodology/`、`build_index.py`、`cangjie.py` 这类外部依赖路径；说明出处的「cangjie-skill」字样允许
  - `test_brief_commands_exist`：任务书里形如 `python <名>.py <子命令>` 的命令，脚本文件存在，子命令在该脚本的 argparse 里有定义（导入脚本、读 `build_parser()`；每个脚本都暴露这个函数）
  - `test_mit_notice_present`：`candidate-schema.md`、`method.md` 里有 MIT 许可声明
- [ ] **Step 2: 跑测试，确认失败**
- [ ] **Step 3: 写文件。** 每份任务书去掉 Sylvester 专用的内容（章节号、单元号、页码例子换成微型书的），路径写成「工作目录下的 `<Paths 字段>`」，命令改成本 skill 的脚本；保留旧任务书的判断口径（严格口径、看不到上一轮判定、覆盖优先于省 token、「原书未说明」和「原图缺失」分开）。旧 `stage0-notes/BRIEF.md`、`STAGE15-BRIEF.md`、`CARD-BRIEF.md` 要求读的外部方法论，改成读 `references/method.md`；阶段 1 的候选格式改成读 `references/candidate-schema.md`；阅读方式改成按带页码的文本分段完整阅读加 `Grep` 检索、回读相邻段（写回稿 D10）；写卡和传播核对用 `verify_units.py show` 查单元和原始复核记录
- [ ] **Step 4: 跑测试，确认通过**
- [ ] **Step 5: 提交**：`feat(book-to-reference): 随包的任务书、方法要点和格式说明`

### Task 9: SKILL.md、description 和隐私检查

**Files:**
- Modify: `skills/book-to-reference/SKILL.md`（整篇重写）
- Delete: `skills/book-to-reference/references/template.md`（和 SKILL.md 重写在同一个提交里，免得中间状态有断链）
- Test: `skills/book-to-reference/tests/test_book_skill_md.py`、`skills/book-to-reference/tests/test_book_privacy.py`

**Interfaces:**
- Consumes: Task 1–8 的脚本 CLI 和文件名

- [ ] **Step 1: 写测试**
  - `test_links_resolve`：SKILL.md 的相对链接都存在，含 `references/briefs/`
  - `test_description_routes_narrowly`：description 里有「本插件源码」和「game-design-theory」，有不触发的一句，没有不带限定的「导入这本书」
  - `test_every_stage_has_check_and_stop`：流程表每行的「检查」「不过就停」两列非空
  - `test_no_private_paths`：`skills/book-to-reference/` 和 `evals/book-to-reference-cold-start/` 下所有文本文件，不出现盘符路径 `[A-Za-z]:[\\/]`、`/Users/`、`/home/`、`OneDrive`、作者的 GitHub 用户名；Task 6 夹具里故意写的 Windows 风格路径那一个文件列在豁免表里，写明理由
- [ ] **Step 2: 跑测试，确认失败**（旧 SKILL.md 里有盘符示例，隐私检查会失败）
- [ ] **Step 3: 重写 SKILL.md，删 `template.md`**：
  - description（写回稿 D7）：只接「向本插件源码中的 `game-design-theory` 导入或迁移书籍资料」；不触发：普通读书摘要、整理个人笔记、导入到自己的其他 skill；不写成本数字
  - 正文：开工前的三件事（`book.yaml` 的 `target_root` 是源码副本、工作目录在仓库外、按实测报价等用户拍：Sylvester 全书提取到写卡约 1690 万子代理 token，接入与验收另计）；写回稿第 5 节的流程表（每行：输入、做什么、产出、检查脚本、不过就停、要不要问用户），顺序含前置淘汰和 D11 的内容评审前移；原则 10–13 各一句，链到 `references/acceptance.md`；「检查脚本通过只说明它查的那件事」一段；接入阶段链到 `briefs/consumers.md`；每一步链到对应任务书
- [ ] **Step 4: 跑测试，确认通过**；跑全套 `pytest`，`test_reference_links.py`、`test_skill_files.py` 也过
- [ ] **Step 5: 触发冒烟（花钱，约 2 美元）**：用 `runner.py` 对 tag `v4.18.0` 的副本和本分支各跑 8 条提示词 × 1 次，同批交错：4 条该触发（「把 Schell 第 3 版导入 game-design-theory」之类）、4 条不该触发（「帮我总结这本书」「把书摘整理成我自己的笔记」等）。本分支不该触发的 4 条都不调用 book-to-reference，该触发的至少 3 条调用。之后 description 再改，就重跑这一步
- [ ] **Step 6: 提交**：`feat(book-to-reference): 重写为维护者流程`

### Task 10: 执行型冷启动评测（写回稿 D9）

**Files:**
- Create: `evals/book-to-reference-cold-start/README.md`
- Create: `evals/book-to-reference-cold-start/fixture/`：
  - `book/`：编造的微型书，三章、约 20 页的带页码文本，有可提炼的方法也有只作参考的观点；`book.yaml`（`target_root` 由运行时填）
  - `stops/`：三份预置的中间状态，各自放在某个检查**之前**，交给代理时说明「这是本轮采用的输入，继续往下做」：
    1. 写卡完成、未跑 `check_cards.py` 的状态，其中一张卡的摘句页码标错
    2. 复核结论已写回、未做传播核对的状态，其中一条收窄了的步骤在卡上仍写成照着执行
    3. 卡已写好、未跑 `integrate.py` 的状态，`book.yaml` 的 `entry_groups` 漏了一章
- Create: `evals/book-to-reference-cold-start/BRIEF.md`（交给冷启动代理：只给新 SKILL.md 的位置、`fixture/book/`、一份隔离的插件副本、仓库外的工作目录；先走完整流程，再依次处理三份 `stops/`；不给本会话的任何背景，不提「这里有预埋的错误」）
- Create: `evals/book-to-reference-cold-start/grade.py`、`evals/book-to-reference-cold-start/test_book_cold_start_grade.py`

**Interfaces:**
- Consumes: Task 1–9 的全部产物
- Produces: `grade.grade(workdir: Path, plugin_copy: Path, log_dir: Path) -> list[Check]`；`Check(name: str, ok: bool, detail: str)`。检查项：
  - 完整流程：各阶段产出存在；`check_cards.py`、`integrate.py` 的最后一次运行退出 0；插件副本里卡和选卡表已接入、无残留
  - 消费：至少一次成功的无界面运行里调用了本插件的某个 skill，并成功读到一张新卡（不限 `game-design-theory` 直接调用）
  - 三份 `stops/`：日志里依次出现「检查失败 → 修改 → 同一检查再跑通过」，顺序不能颠倒；没有在检查之前就改掉错误
- [ ] **Step 1: 写测试**：每条检查配一个故意做错的输入（缺产出；检查没跑就改了错误；修改后没重跑检查；没有消费到新卡；只有失败的运行），`grade` 对应项 `ok is False`；一份全对的输入全部 `ok`
- [ ] **Step 2: 跑测试，确认失败；实现 `grade.py`；跑测试，确认通过**
- [ ] **Step 3: 跑一次冷启动**：派一个没有本会话上下文的子代理，只交 `BRIEF.md`；它自己不能派子代理时，按导入稿原则 8 把独立性相关的步骤标「未独立验证」，照常做完。约 50–100 万 token、几美元 API
- [ ] **Step 4: 用 `grade.py` 判。** 不过的项按「让 AI 和人都能用的软件」原则八分类（缺能力、缺说明、缺依赖……），改 SKILL.md、任务书或脚本，不为它加新机制
- [ ] **Step 5: 改过指引就再派一个新上下文的子代理完整跑一次**（不是只重跑失败的片段），`grade.py` 全部 `ok` 才算过；改了 description 还要重跑 Task 9 的触发冒烟。结果记进 README 的「上次运行」一节
- [ ] **Step 6: 提交**：`feat(evals): book-to-reference 执行型冷启动`

### Task 11: 发版 4.19.0

**Files:**
- Modify: `CHANGELOG.md`、`.claude-plugin/plugin.json`、`.claude-plugin/marketplace.json`（两处）、`.codex-plugin/plugin.json`、`CLAUDE.md`（版本行）、`README.md:82`（book-to-reference 的介绍改成维护者流程）、`docs/superpowers/specs/2026-11-08-book-import-pipeline-design.md`（状态行补「第 6 步见写回稿」和 4.18.0 的结论）

- [ ] **Step 1: 写 CHANGELOG 4.19.0**：book-to-reference 改成维护者流程（不再对普通读书摘要触发、不再默认写进 skill 自己的目录）；随包的任务书、方法要点、格式说明和脚本；验证做了什么（脚本测试、Sylvester 产物复现、执行型冷启动、触发冒烟）和没做什么（只在 Sylvester 一本真书上走通过，Schell 是第一次真实使用）；外部依赖（PyMuPDF，只在转 PDF 时要）；**4.18.0 验证口径的更正**（用户 2026-11-09 定：保留 4.18.0，照实写更正）：4.18.0 发版前的三次验收后回归用的是合并计数，不是口径 B 的分组判法；按 B 分组，第三次回归旧覆盖组 3 好 9 平 0 差、新增组 0 好 5 平 1 差，新增组不过；判差的那题两个版本四次运行都没调用任何 skill，模型看到的插件内容只有各 skill 的描述，两版逐字节相同；今后的验收按 B 分组判（`grading.py` 的 `protocol="B"`）。导入稿的状态行同步写这一条
- [ ] **Step 2: 内容提交和版本号提交分开**：先提交 CHANGELOG、README、导入稿状态行；再单独 `chore: bump version to 4.19.0`
- [ ] **Step 3: 校验**：`pytest` 全过；`python scripts/verify_release.py --version 4.19.0` 退出 0；整段 diff 搜本机路径和项目名为空
- [ ] **Step 4: 合并、打 tag、推送、对齐镜像**：照 `CLAUDE.md` 开发回路第 5–7 步

---

## 胃口

剩余约 440 万子代理 token（codex 另算）。低估风险最大的是 Task 5（渲染和裁决的顺序要复现 4.18.0）、Task 7（两种协议和历史格式拆清）、Task 8（外部方法和候选格式补齐）、Task 10（改指引后要再完整跑一次）。Task 6 只做主流程用到的报告，不复刻旧的查看脚本。超了先砍 Task 6 的报告和 Task 4 的 `show` 输出格式，不砍 Task 5、7、10 的对照检查。

## 不在本计划里

- `claude plugin eval` 迁移（写回稿 D8：以后按同一契约接替）。
- 专用分块检索索引（写回稿 D10：等 Schell 遇到效率问题）。
- 导入到 `game-design-theory` 以外的目标（写回稿 D7）。
- Schell 第 3 版的导入（另定胃口）。
