---
name: sync-docs-ahead
description: >
  Full design-document vs code gap analysis. Compares all design docs against
  actual code to identify implemented, partial, missing, and divergent features.
  Design document location is read from CLAUDE.md.
  Outputs a structured report to docs/gap-analysis/{date}/.
  Use when user says "gap analysis", "差距分析", "设计vs代码对比",
  "哪些功能还没实现", "实现了多少", "代码覆盖了哪些设计".
---

# Gap Analysis

Auto-discover design docs, spawn one `general-purpose` subagent per doc (needs Write tool), each writes report to disk. Main agent extracts summaries from files into a consolidated report.

## Workflow

### Phase 1: Auto-Discover

1. Read CLAUDE.md to find the design documents directory (look for "Design Documents" section or similar).
   **If CLAUDE.md names no local directory** (the project keeps its design docs in Feishu, Notion,
   a wiki…): stop and ask the user for a local export directory or the remote location. Do not
   treat "no local docs" as "no design" — nothing downstream can be judged missing from an empty
   input. Exporting from Feishu is the user's `lark-doc` / `feishu-doc-sync` skills' job, not this
   skill's; once the export exists, have it declared in CLAUDE.md and continue from step 2.
2. Glob `**/*.md` under that directory to discover all design documents.
3. Derive system name from each filename:
   - If filename contains English in parentheses: extract it (e.g., `鉴定系统 (Appraisal System).md` → `Appraisal`)
   - If filename has a numeric prefix: strip it and use remainder (e.g., `00_核心愿景.md` → `CoreVision`)
   - Otherwise: use the filename without extension

Pick the output directory **once** and reuse it in every phase below as `{OUTPUT_DIR}`: `docs/gap-analysis/{YYYY-MM-DD}/`, or — if that already exists (same-day re-run) — `docs/gap-analysis/{YYYY-MM-DD}-{HHMM}/`; if *that* exists as well (a third run inside the same minute), append `-2`, `-3`… until the name is free. `mkdir` it. The invariant is **never write into a directory that already exists** — a same-minute re-run overwrote a report with manual edits in testing. **Never clear a previous run**: if the new analysis fails halfway, the old report is the only evidence left, and it may carry manual corrections. Every output path mentioned later in this skill means `{OUTPUT_DIR}` — choosing a fresh directory here while Phase 2 agents still write to the dated one silently overwrites the old reports (caught in testing).

### Phase 2: Parallel Analysis

Launch ALL subagents in a single message (`subagent_type: "general-purpose"`, `run_in_background: true`).

Subagent prompt template:

```
Analyze the gap between a design document and its code implementation.

**Design document:** {docPath}
**System name:** {systemName}
**Output file:** {OUTPUT_DIR}/{systemName}.md

Steps:
1. Read the entire design document
2. Extract every distinct feature/requirement/mechanic described
3. Search the project's source code using Glob and Grep. Read the scope from the project's
   **`game-toolkit.yaml`** at the project root (format and rules: invoke `game-toolkit:layer-contracts`) —
   engine, 工程根, 技术栈, 源码范围, 可检查程度. Do not detect the engine yourself; if the
   declaration is missing or the needed field is 未知, ask the user rather than guessing.

   **Honour 可检查程度 — this is the part that silently corrupts a gap report.** Some sources
   can be Glob'd but not read: Blueprint graphs, prefab wiring, visual-script assets. Finding
   `.uasset` files does not mean their logic was inspected.
   - source is text and in scope → rate it normally
   - source exists but **查不了** (needs the engine / an export to inspect) → rate it
     `无法检查`, never `missing`. A feature reported missing because its logic lives in a
     binary asset triggers a duplicate implementation.
   - source language was **not in scope** at all → say so; a "missing" verdict is only
     meaningful when the language was actually searched.

   State in the report which directories, file types, and check methods were used.
4. Rate each feature's implementation status
5. Write report to the output file using the Write tool

Report format (strict):

## {systemName}

### Features

| # | Design Requirement | Status | Code Reference | Notes |
|---|-------------------|--------|---------------|-------|
| 1 | [requirement summary] | [status] | [file:line or "—"] | [note] |

Status values: ✅ Implemented, ⚠️ Partial, ❌ Missing, 🔄 Divergent, ❓ Unverifiable

`❓ Unverifiable` = the feature's source exists but **cannot be inspected by the means
available** (Blueprint graphs, prefab wiring, binary assets — see 可检查程度 in the
project declaration). It is **not** a synonym for Missing: reporting it as Missing
triggers a duplicate implementation. Never fold it into the other four.

### Summary
- Total features: N
- ✅ Implemented: N
- ⚠️ Partial: N
- ❌ Missing: N
- 🔄 Divergent: N
- ❓ Unverifiable: N
- Inspectable: (Total - Unverifiable) / Total * 100%   ← 这次**能**下结论的比例
- Coverage of inspected: (Implemented + 0.5 * Partial) / (Total - Unverifiable) * 100%

两个百分比都要给，不要只报一个。Unverifiable 既不算实现、也不算缺失 ——
把它塞进分母会让 Blueprint 重的系统凭空显得完成度很低；把它排除后又宣称
「全项目已完成」同样是错的。
```

### Phase 3: Collect Results

Wait for all subagents using `TaskOutput` with `block: true` on each. Then extract Summary sections from persisted files:

```
Grep pattern="^### Summary$" with -A 8 on each file in {OUTPUT_DIR}/ (the block is eight lines — five status counts, `Inspectable`, `Coverage of inspected`; `-A 7` silently dropped the last one)
```

Parse summaries to build the overview table. Note any missing files as "TIMEOUT".

### Phase 4: Write SUMMARY.md

Write overview table to `{OUTPUT_DIR}/SUMMARY.md`. Per-system reports are already in the same folder.

### Phase 5: User Summary

Print overview table to user. Highlight top 5 systems with lowest coverage.

## Notes

- Read-only — never modifies source code or design docs (only writes to `docs/`)
- For cross-cutting docs (CoreVision), check overall architecture patterns rather than specific features
