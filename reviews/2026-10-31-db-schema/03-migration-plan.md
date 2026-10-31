# 03 — Migration plan

Each phase leaves `build.py` green (`ruff`, `mypy`, `pytest`, and a
successful build) and can be reviewed and committed on its own. Per repo
rule, each phase that changes a format ships the schema, README and test
changes together.

Downstream consumers:
- **`tools/`**: emitters, `promote.py`, `faa_tcds.py`, the manual-provenance
  tripwire (`tools/tests/e2e/test_manual_provenance.py` +
  `tests/manual_provenance_manifest.txt`). Follow `tools/CLAUDE.md`.
- **FARFETCHed app**: every query. Phases 2 and 3 are breaking for it.

## Phase 0 — Fail-loud and type fixes (no contract change)

Safe to land first. JSON formats and table names are unchanged.

| Change | Findings |
|---|---|
| Remove the `IntegrityError` swallow in `_insert_cb_row` | F-10 |
| Validate range `from`/`to` ordinals exist and `from ≤ to` | F-11 |
| TCDS metadata conflict → `BuildError` | F-12 |
| Closed `categories` enum in `aircraft_model.schema.json`; drop `.title()` and the authority fallbacks | F-13 |
| `STRICT` tables, `TEXT` dates with `CHECK (date(x) IS x)`, build-time future-date check | F-14 |
| Drop the redundant indexes; add the FK indexes | F-19 |
| `PRAGMA user_version = 1` + `build_info` | F-20 |
| Carry `provenance` into the DB | F-23 |
| Fix doc drift (`plan.md` schema block → link to README; table count; report filename) | F-25 |

**Expected fallout.** The future-date check will fail the build on the 36
`issued_on` values in the 2060s (F-14, F-26). Fix the parser in
`tools/regulations/faa/`, re-stage and promote. Don't loosen the check.
Data fixes go through tools, not hand-edits (repo rule), unless they're
marked `provenance: manual`.

Tests to add:
- a fixture with a `to_amendment_ordinal` not in the part → build fails;
- two model files with the same TCDS and different revisions → fails;
- an unknown category → schema fails;
- `issued_on: "2064-03-25"` → fails;
- `PRAGMA user_version` equals the build's constant.

## Phase 1 — Grain fixes (contract change, current names kept)

| Change | Findings |
|---|---|
| Move `actions` from section amendments to `_part.json` amendments; `amendment_actions.amendment_id` | F-06 |
| Split `cert_basis_entries` into entries / refs / resolved; `UNIQUE (tcb_id, display_order)` | F-01 |
| References use designators (`from`/`to`) instead of ordinals | F-15 |
| Add `skip`, `provisions`, `paragraph`, `effect`, `applicability`; implement the P-06 resolution rules | F-02, F-03 |
| Composite FKs on `section_amendments`; `same_as_designator` → FK | F-08 |
| Drop the `"Initial Adoption"` sentinel → NULL; add the `text_missing` generated column | F-07 |
| `user_version = 2` | |

Order inside the phase:
1. **Actions.** Add a temporary build check that fails if the
   per-section copies of an amendment's actions disagree. Run it on
   current data and fix any disagreement in tools. Then move the field.
   That needs an emitter change in `tools/regulations/*` and a staged
   re-emit, plus a one-off conversion of the existing promoted files. Any
   `provenance: manual` file has to be converted by hand and the manifest
   kept in step.
2. **Cert-basis split** with the existing range/single semantics first,
   checked to give the same `cert_basis_resolved` as today's expansion on
   the 172. Then add the P-06 rules.
3. **`faa_tcds.py`** emits the new `references` shape. The TODO.md
   parsing improvements (sub-paragraph splitting, except clauses, serial
   applicability) can then target a format that can hold them.

Tests: fixtures for each P-06 rule, including every rule-7 failure; the
525 worked example as an end-to-end fixture; a skip-gap fixture where a
provision changed only in the skipped revision.

## Phase 2 — Generic rename (contract change)

| Change | Findings |
|---|---|
| Tables renamed per the 02-proposal name map | F-04 |
| `issuers` with `kind`, `successor_id`; `CAA (FAA)` → `CAA` | F-16 |
| `documents.doc_kind`, `code`, `slug`; `title_number` folded into `code` | F-04, F-09 |
| `data/regulations/` → `data/documents/`; `_part.json` → `_document.json`; field renames (P-02) | F-04 |
| Per-`doc_kind` designator patterns | F-18 |
| `provisions.parent_id`, `sort_key` | F-17 |
| `user_version = 3` | |

Do this **before** bulk ingestion (the PROMPT_PART23_BULK_FETCH work). The
cost of a rename grows with every promoted file. It's a mechanical
conversion, so write it as a one-off script producing a review diff
(non-destructive, per server convention), not by hand.

Impact on tools: `tools/common/paths.py` constants, emitter output paths
and keys, `promote.py`, the manifest paths in
`tests/manual_provenance_manifest.txt`.

## Phase 3 — New capabilities (additive)

- `provision_relations` + JSON home (Q-07) (P-07).
- The first non-regulation documents: an FAA special condition as
  `doc_kind = 'special_condition'`, so SC entries resolve (F-05).
- Repeal / reserved representation (Q-03) before ingesting 23-64 (F-22).
- Journal-mode change if Q-05 is accepted (F-21).

Additive phases don't break consumers, but still bump `user_version`
(minor: the app may accept `>=`; see Q-08).

## Verification checklist per phase

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
uv run python build.py
sqlite3 cert_basis.sqlite 'PRAGMA foreign_key_check;'   # must be empty
sqlite3 cert_basis.sqlite 'PRAGMA integrity_check;'     # ok
sqlite3 cert_basis.sqlite 'PRAGMA user_version;'
sqlite3 cert_basis.sqlite < reviews/2026-10-31-db-schema/checks.sql  # Phase 0 only; queries use old names
```
