---
name: gap-analysis
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
2. Glob `**/*.md` under that directory to discover all design documents.
3. Derive system name from each filename:
   - If filename contains English in parentheses: extract it (e.g., `鉴定系统 (Appraisal System).md` → `Appraisal`)
   - If filename has a numeric prefix: strip it and use remainder (e.g., `00_核心愿景.md` → `CoreVision`)
   - Otherwise: use the filename without extension

Create output directory: `mkdir -p docs/gap-analysis/{YYYY-MM-DD}`. If it already exists (same-day re-run), clear it first.

### Phase 2: Parallel Analysis

Launch ALL subagents in a single message (`subagent_type: "general-purpose"`, `run_in_background: true`).

Subagent prompt template:

```
Analyze the gap between a design document and its code implementation.

**Design document:** {docPath}
**System name:** {systemName}
**Output file:** docs/gap-analysis/{YYYY-MM-DD}/{systemName}.md

Steps:
1. Read the entire design document
2. Extract every distinct feature/requirement/mechanic described
3. Search the project's source code directories (read from CLAUDE.md Architecture section; if unspecified, search all .ts/.tsx/.py/.js files under project root) using Glob and Grep
4. Rate each feature's implementation status
5. Write report to the output file using the Write tool

Report format (strict):

## {systemName}

### Features

| # | Design Requirement | Status | Code Reference | Notes |
|---|-------------------|--------|---------------|-------|
| 1 | [requirement summary] | [status] | [file:line or "—"] | [note] |

Status values: ✅ Implemented, ⚠️ Partial, ❌ Missing, 🔄 Divergent

### Summary
- Total features: N
- ✅ Implemented: N
- ⚠️ Partial: N
- ❌ Missing: N
- 🔄 Divergent: N
- Coverage: X%  (formula: (Implemented + 0.5 * Partial) / Total * 100)
```

### Phase 3: Collect Results

Wait for all subagents using `TaskOutput` with `block: true` on each. Then extract Summary sections from persisted files:

```
Grep pattern="^### Summary$" with -A 7 on each file in docs/gap-analysis/{YYYY-MM-DD}/
```

Parse summaries to build the overview table. Note any missing files as "TIMEOUT".

### Phase 4: Write SUMMARY.md

Write overview table to `docs/gap-analysis/{YYYY-MM-DD}/SUMMARY.md`. Per-system reports are already in the same folder.

### Phase 5: User Summary

Print overview table to user. Highlight top 5 systems with lowest coverage.

## Notes

- Read-only — never modifies source code or design docs (only writes to `docs/`)
- For cross-cutting docs (CoreVision), check overall architecture patterns rather than specific features
