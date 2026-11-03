# Review: SQLite schema and JSON data contract (2026-10-31)

**Status:** Implemented 2026-10-31, trimmed (schema version 1). The files
below are the review as written; the implementation differs where noted
here. The contract as built is [../../docs/DATA_FORMAT.md](../../docs/DATA_FORMAT.md)
and [../../docs/SQLITE.md](../../docs/SQLITE.md) (README.md until 2026-11-03;
`plan.md`, cited below as evidence, was deleted on 2026-11-03 and is in git
history).

## Implementation record

Findings were re-checked against the data at `ec5fe36` (about 1,150 files,
not the 88 sections reviewed) before implementing.

**Implemented:** F-01, F-02, F-03 (three-layer cert basis and resolution
rules), F-04, F-16, F-18 (generic issuer → document → revision → provision
model; `CAA (FAA)` → `CAA` with successor FAA), F-07 (`Initial Adoption`
removed; `text_missing` generated column), F-08, F-09 (composite FKs;
`title_number` folded into `documents.code`), F-10 to F-13 (fail-loud
fixes; closed issuer and category sets), F-14 (STRICT tables, date
CHECKs, build-time future-date check; the `%y` pivot bug fixed in
`tools/regulations/faa/extract.py` and `tools/common/drs.py`, and 662
2060s dates corrected by the migration), F-15 (designators, not ordinals),
F-17 partly (`sort_key` only), F-19, F-20, F-21 (DELETE journal mode),
F-23, F-25.

**Changed from the proposal:**
- No `ref_kind` and no `from` on references. "As amended by 23-1 thru
  23-38" always includes the base revision. With an explicit `from:
  "23-1"`, rule 3 would have silently dropped every provision unchanged
  since 23-0. Every ref is `{issuer, document, to, skip?, provisions?,
  paragraph?, effect?}`.
- Overrides resolve within one cert-basis entry (one TCDS line), not within
  a TCB + applicability conflict group (Q-02b).
- `cert_basis_ref_provisions` and `cert_basis_ref_skips` carry
  `document_id` so their FKs are same-document too, and
  `cert_basis_resolved.via_ref_id` is constrained to the same entry.
- Two document-wide refs that disagree, and an exclude that removes
  nothing, are also build failures.

**Rejected:** F-06 / P-05. Actions stay per provision version
(`version_actions`). DRS records them per section, and 16 of 77 amendments
had differing per-section lists, some legitimately (e.g. 23-59 on §23.905
vs §23.907).

**Deferred:** F-22 / Q-03 repeal and `[Reserved]` (needed before 23-64),
F-17 `parent_id` (until a hierarchical document arrives), P-07 / Q-07
`provision_relations`, F-24 / Q-06 per-TCDS files (decide before a second
model on an existing TCDS), Q-04 structured serial applicability,
`document_revisions.cancelled_on`.

**Found during implementation:** `input/regs.csv` lists CAR 3 §3.735 twice
per series (under "General" and "Limitations"), so `car-3/735.json` and
`car-3-reissue/735.json` held duplicate base versions. The "Limitations"
copy was removed (text unchanged, provenance stays `ocr`), and
`tools/regulations/car/emit.py` now drops identical duplicates with a
warning and fails on differing ones. Also, jsonschema's `format: uri` is not
enforced without the optional `rfc3987` package, so URLs are now checked by
an `^https?://` pattern.

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
