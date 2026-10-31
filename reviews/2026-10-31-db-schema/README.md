# Review: SQLite schema and JSON data contract (2026-10-31)

**Status:** Proposed. Not yet implemented. Nothing in `build.py`, `schemas/`,
`data/` or `tools/` has been changed as part of this review.

**Scope:** the SQLite schema emitted by `build.py`, the three JSON Schemas in
`schemas/`, and the documentation of both in `README.md` and `plan.md`.
Reviewed for (a) anti-patterns and correctness, and (b) extensibility to
other document types (advisory circulars, EASA CS/AMC/GM, special
conditions, ELOS, exemptions) and other sources (e.g. MIL-HDBK-516).

**State reviewed:** commit `20d6289` (main). Built DB at the time: 2 parts,
88 sections, 89 section_amendments, 1 aircraft, 22 cert_basis_entries.

## Files

| File | Contents |
|---|---|
| [01-findings.md](01-findings.md) | Every issue found, with evidence and a reproducing query or code reference. Numbered `F-nn` for cross-reference. |
| [02-proposal.md](02-proposal.md) | Proposed target schema: SQLite DDL, JSON format changes, cert-basis resolution rules. Numbered `P-nn`. |
| [03-migration-plan.md](03-migration-plan.md) | Phased implementation order, with per-phase tests and downstream impact (tools/, FARFETCHed app). |
| [04-open-questions.md](04-open-questions.md) | Decisions that need the maintainer before or during implementation. |
| [checks.sql](checks.sql) | Evidence queries for the findings, run against the *current* schema. |
| [proposed_schema.sql](proposed_schema.sql) | The target DDL from 02-proposal.md as a standalone file. Checked to load in SQLite 3.46.1 with `PRAGMA foreign_keys = ON`. |

## How to use this review

1. Read `01-findings.md` and check each finding against the code. Every
   finding cites a file/line or a query you can run against a fresh
   `cert_basis.sqlite`.
2. Resolve `04-open-questions.md`. Several proposal details depend on those
   answers.
3. Implement in the phase order in `03-migration-plan.md`. Phase 0 is safe
   to land alone and does not change the data contract.

## Conflicts with existing repo rules

This proposal touches rules stated in the root `CLAUDE.md`. They need an
explicit decision, not silent override:

- **Regulation file paths** (`data/regulations/{authority}/{part}/{section}.json`
  "Don't introduce additional path segments"). P-02 proposes renaming the
  tree to `data/documents/{issuer}/{document}/…` but keeps the same depth.
- **`PRAGMA journal_mode = WAL`** on the built DB. F-21 recommends
  `DELETE` for a read-only distributed artifact.
- **`TEXT MISSING` / no status column.** Kept as is. F-07 only adds a
  derived flag and doesn't change the rule.

## Verification commands

```bash
uv run python build.py
sqlite3 cert_basis.sqlite < reviews/2026-10-31-db-schema/checks.sql
# Load the proposed DDL into a throwaway DB:
sqlite3 :memory: "PRAGMA foreign_keys=ON;" ".read reviews/2026-10-31-db-schema/proposed_schema.sql" ".tables"
```
