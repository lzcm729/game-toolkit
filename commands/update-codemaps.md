---
description: Scan imports and exports to regenerate the architecture/backend/frontend/data codemaps, stamping freshness and asking for approval when the diff exceeds 30%.
---

# Update Codemaps

Analyze the codebase structure and update architecture documentation:

1. Scan all source files for imports, exports, and dependencies

2. Generate token-lean codemaps under **`docs/CODEMAPS/`** — the same location the
   `doc-updater` agent writes to, and the one READMEs link at. Do not write to a
   second `codemaps/` tree: two producers with two output paths means whichever
   ran last is current and the other silently goes stale.
   - docs/CODEMAPS/INDEX.md - Overall architecture, links to the rest
   - docs/CODEMAPS/frontend.md - Frontend structure
   - docs/CODEMAPS/backend.md - Backend structure
   - docs/CODEMAPS/integrations.md - External integrations and data contracts

3. Calculate diff percentage from previous version
4. If changes > 30%, request user approval before updating
5. Add freshness timestamp to each codemap
6. Save reports to .reports/codemap-diff.txt

Determine the source language and directories from the project (CLAUDE.md's Architecture section, else detect from the project root). Focus on high-level structure, not implementation details.
