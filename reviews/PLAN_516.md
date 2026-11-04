# PLAN_516 — MIL-HDBK-516 ingestion + provision identity (schema v7)

## Context

The user wants MIL-HDBK-516 (DoD airworthiness certification criteria) in the
regulations pipeline. Six editions are already downloaded as text-layer PDFs
in `input/Regs/US DoD/`: 516 (2002-10-01), 516A (2004-02-05), 516B
(2005-09-26), 516B w/Change 1 (2008-02-29), 516C (2014-12-12) and 516D
(2026-05-29). No OCR is needed.

A sample check (12 paragraphs from 516C, matched by text across all
editions) showed that **paragraph numbers are not stable identities**:

- A number gets reused for a different requirement. 516's 4.1.3 is not
  516A's 4.1.3 (commercial derivative aircraft).
- A requirement gets renumbered. The 516B 5.2.3 mass-balance criterion is
  5.2.2 in Chg 1.
- Between 516C and 516D, criteria were consolidated across sections. The 516D
  foreword says section 14 went into 4, 10 into 11, 18 into 9, and 8.7 into a
  new section 10.
- Many requirements still carry through under the same number with the same
  text (516 → 516C is mostly stable).

Today `provisions UNIQUE(document_id, number)` makes the printed number the
identity of a provision. That mixes reused numbers into one history and
breaks renumbered requirements into unrelated provisions. Decision (user,
this session):

- **Separate identity from label:** a stable `key` per provision, plus the
  printed `number` per version. This is schema v7.
- Text is the whole printed block under each paragraph.
- The issuer code is `DOD`.
- Relations between provisions (merges, splits, cross-document links, as in
  ROADMAP-4) are deferred.

Schema v6 (EASA TCDS, categories per TCB) is committed (`e7ee945`), and v7
is built on top of it.

**Progress (2026-11-04):** Part A is implemented and committed, except
re-emitting and promoting the data (Sequence step 2, see below). Part B has
not started. Start the next session at [Next session](#next-session).

## Part A — Schema v7: provision key vs printed number

Contract (JSON):

- `schemas/provision.schema.json`:
  - Add a top-level `key`, a stable opaque id with the current number
    pattern. It is the file name, and the build checks the path against it.
  - The top-level `number` becomes the *current* printed number (the number
    at the latest version).
  - Add an optional per-version `number` (number as printed at that
    revision). When it is absent it defaults to the top-level `number`.
- FAA, CAR and EASA files carry `key == number` and no per-version number.
  The only churn is the added `key` field, from re-running their emitters.
  There is no hand edit.
- Add `DOD` to the issuer enum in `schemas/common.schema.json`.

SQLite (`build.py`):

- **`provisions`:** add `key TEXT NOT NULL` with `UNIQUE (document_id, key)`.
  Keep `number` as the current number and `sort_key` from it. Drop
  `UNIQUE (document_id, number)`.
- **`provision_versions`:** add `number TEXT NOT NULL`, resolved by the build
  from the version or the top-level default. Add
  `UNIQUE (document_id, revision_id, number)` for collisions within one
  revision.
- **Python check (fail loud):** at every revision of a document, each printed
  number belongs to at most one *in-force* provision. Versions are sparse,
  so the DDL can't express this.
- **Cert-basis refs:** `provisions: [...]` stay printed numbers, as a TCDS
  writes them. They resolve to the provision that carried that number at the
  ref's `to` revision. An exclude ref uses the highest `to` of the entry's
  include refs. If nothing or more than one provision matches, the build
  fails. For FAA/EASA (key == number, never reused) the results don't change.
  Rework the index at build.py:1049–1074 (number → id) to (number, revision)
  → id.
- **Similarity and `canonical_title`:** stay per provision, which now means
  per requirement.
- **Issuers:** `_ISSUERS` gets
  `"DOD": ("U.S. Department of Defense", "military", "US", None)`.
- **Version:** `SCHEMA_VERSION = 7`.

Docs:

- `docs/DATA_FORMAT.md` (file paths, provision fields, resolution rules).
- `docs/SQLITE.md` (provisions/versions, contract version 7).
- `docs/SCHEMA_HISTORY.md` (a v7 row, plus a standing decision: "number is a
  label, key is identity").

App impact, to note for the FARFETCHed repo:
- `provisions.number` keeps its meaning (current number), so lookups keep
  working.
- Historical display should use `provision_versions.number`.

Tests (`tests/`):
- a renumbered provision (version numbers differ, one key);
- number reuse by two keys in different revisions (allowed);
- the same number on two in-force provisions (fails);
- a ref by number resolving at `to` across a renumber;
- an exclude ref resolved the same way;
- the path vs `key` check;
- an invalid-fixture `DOD` file, for validation.

Tools for existing sources:
- `s02_emit/{faa/regs,car,easa/cs}` and the TCDS parser's staged-document
  lookup emit or accept `key`.
- One shared helper, `s00_common/` (e.g. `provision_record()`), builds the
  top-level dict, so key == number is set in one place.

## Part B — MIL-HDBK-516 pipeline (`dod/hdbk`)

The layout mirrors the existing pipelines (tools/CLAUDE.md "Adding a new
pipeline"). There is no discover stage (manual download), and no upstream
manifest exists.

**`tools/s01_extract/dod/hdbk/extract.py`**

1. For each PDF in `input/Regs/US DoD/`, use `s00_common/pdf.py:text_cached`
   (raw mode, not `-layout`).
2. Read edition metadata from the cover page: the designator as printed
   (`MIL-HDBK-516`, …, `MIL-HDBK-516B w/CHANGE 1`), the date, and what it
   supersedes. The superseding chain gives the ordinal. Write it to
   `tools/out/work/dod_hdbk_catalogue.tsv`, so nothing is hand-typed.
3. Strip page furniture: the ASSIST footer, the running `MIL-HDBK-516x`
   header, page numbers and the TOC. In 516C/516D, also strip the
   service-applicability "X" matrix rows.
4. Split sections 4–20 into numbered paragraphs, using a layout parser per
   edition family:
   - 516/516A: criterion text only. Stop before the Appendix cross-reference
     table.
   - 516B and Chg 1: criterion + `DoD/MIL Doc:` + `FAA Doc:`.
   - 516C/516D: title + `Criterion:` / `Standard:` /
     `Method of Compliance:` / `References:`.
   - Section and subsection headings (`4.`, `4.1 Design criteria`) are
     groupings, not provisions. A numbered paragraph is a provision when it
     has body text.
5. Write `tools/out/extracted/dod/mil-hdbk-516/{designator}/{number}.json`
   with title, grouping (section/subsection title), flat text and status
   (`ok` / `empty` for figure- or table-only).
6. Cross-check paragraph numbers against each PDF's TOC. Report mismatches to
   `tools/out/reports/dod_hdbk_extract_report.tsv`.

**`tools/s02_emit/dod/hdbk/emit.py`** (modelled on `s02_emit/easa/cs/emit.py`)

- Load the catalogue and the extracted paragraphs. Reuse EASA's
  `strict_key` / `loose_key` / `bag` comparisons: import them, or lift them to
  `s00_common/text.py` if they need to be shared.
- **Continuity (key assignment).** Walk editions in ordinal order. A
  paragraph continues the in-force provision carrying the same number only
  when the text matches above a similarity threshold, or the title is the
  same.
  - Otherwise the old provision gets a `deleted` version and the paragraph
    starts a new key.
  - The key is the number at first appearance. If that number was already
    used as a key, add the designator, e.g. `4.1.3-516a`.
  - Borderline scores are reported `needs_human`, and the run stops unless
    each one is decided.
- **Decisions file: `tools/overrides/dod_hdbk.tsv`.** Columns:
  `designator number action target_key evidence note`, read with
  `s00_common/overrides.py:read_rows`.
  - `continue` makes the paragraph continue `target_key`. This is also how
    a renumbered requirement (5.2.3 → 5.2.2) keeps one key.
  - `new` forces a new key.
  - Uses are reported `override_applied`, rows that match nothing
    `override_stale`.
- **Versions:**
  - a `text` version on first appearance or when the text changed;
  - nothing when unchanged (as EASA does);
  - `deleted` when gone;
  - `TEXT MISSING` for `empty`.
  - The per-version `number` is set only when it differs from the current
    number.
- **Version fields:**
  - `source_url`: `https://assist.dla.mil` (the URL printed in the footer).
  - `publication_cite`: omitted.
  - `provenance`: `scraped`.
  - `actions`: none.
- **Layout:** `structure_version(...)` last, with `TEXT_OVERRIDES`. Block
  heads (`Criterion:` …) stay inline, and 516D's `(1)`, `(2)` MoC items are
  structured. Check the structure report on the trial, and if `flat-failed` /
  `possible-trailing` dominate, record it in ISSUES.md rather than change
  `structure.py` now.
- **Output:**
  - `tools/out/staged/documents/dod/mil-hdbk-516/_document.json` with
    `issuer DOD`, `doc_kind handbook`, `code MIL-HDBK-516`,
    `slug mil-hdbk-516`, title "Airworthiness Certification Criteria", and
    the revisions from the catalogue.
  - `{key}.json` per provision.
  - Reports to `tools/out/reports/emit_dod_hdbk_report.tsv` and
    `structure_report_dod_hdbk.tsv`.

**Tests (`tools/s99_tests/`)**
- `extract/dod/hdbk/`: small hand-written text fixtures, one per layout
  family, under `fixtures/dod_hdbk/`.
- `emit/dod/hdbk/`: continue / new key / renumber via override / deletion /
  needs_human stop.
- `e2e`: a staged 516 tree builds.

**Docs**
- `tools/s00_docs/DOD_HDBK.md`: CLI, layouts per edition, continuity rule,
  decisions file, source quirks.
- The pipelines table in `tools/README.md`.
- The overrides table in `tools/s00_docs/PIPELINE.md`.
- The "Full offline rebuild" block.

**`ISSUES.md`**
- ROADMAP-4 note: merges and splits (516C §14 → 516D §4.4, and so on), the
  516B A.3 published cross-reference table as evidence, and cross-document
  14 CFR refs.
- The 516/516A appendix cross-reference table, not ingested.
- The aircraft model identity smell: `(manufacturer, model_designation)` as
  a key.
- Trial findings: structure outcomes and needs_human counts.

## Sequence

1. ~~User commits v6.~~ Done (`e7ee945`).
2. ~~Part A (schema, build, tests, docs)~~ done. **Open:** re-emit
   FAA/CAR/EASA and promote. `promote --dry-run` shows the added `key` on
   every provision file, *plus* layout-only text changes to 114 files (see
   Part A record).
3. Extract all six editions. Review the extract report and the TOC
   cross-check.
4. Emit trial. Review needs_human rows and continuity decisions with the
   user, then fill in `dod_hdbk.tsv`.
5. Run `promote --dry-run`. The user promotes and commits.

## Verification

- `uv run pytest`, `uv run ruff check . tools/s0* tools/s99_tests`,
  `uv run mypy . tools/s0* tools/s99_tests`.
- `uv run python build.py`. Zero unresolved refs, and the report shows the
  `DOD` document, its provision and version counts, and the same FAA/EASA
  cert-basis resolution counts as before v7.
- Smoke queries on `cert_basis.sqlite`:
  - `PRAGMA user_version` = 7.
  - The 516A 4.1.3 key has versions through 516C, and 516's 4.1.3 is a
    different key.
  - The 516B 5.2.3 key shows number 5.2.2 at Chg 1. That one depends on the
    override row.
  - No two in-force provisions share a number at any revision.
- Check `provision_similarity` for DOD rows, and that the existing
  `tests/test_similarity.py` golden set still ranks first.

## Next session

1. ~~**Re-emit and promote, so `data/` carries `key`.**~~ Done 2026-11-05: 3,663
   files promoted (3,549 `key` only, 114 `key` + layout), build v7 OK with
   98,145 resolved rows, 0 unresolved, paragraph refs 397/4, full
   `pytest` green. Commit of `data/` left to the user. Original note: Until then
   `build.py` fails on the real `data/` ("'key' is a required property"),
   and so do the real-data tests (`TestRealDataBuild`, `TestDA40Trace`,
   the similarity golden set, `TestRealData`, and
   `test_real_data_has_no_ecfr_marker_in_text`):
   ```bash
   for p in 23 25 27 29 36; do uv run python -m tools.s02_emit.faa.regs.emit --part $p; done
   uv run python -m tools.s02_emit.car.emit
   for c in 23 25 27 29; do uv run python -m tools.s02_emit.easa.cs.emit --cs $c --accept-needs-human; done
   uv run python -m tools.s03_promote.promote --dry-run
   ```
   The user reviews the diff and promotes. Then `uv run pytest` should pass
   in full, and `uv run python build.py` should report 98,145 resolved rows
   (as of `4db1aee`'s data) and zero unresolved.
2. Part B, from the top: `tools/s01_extract/dod/hdbk/extract.py`.

## Part A record (2026-11-04)

What was built, beyond or different from the plan text above:

- **`provisions.key`** is required in the JSON schema (not optional), with
  the number pattern, and is the file name. `UNIQUE (document_id, number)` is
  gone; there is a plain index on `(document_id, number)`.
- **Within-revision collisions:** a *partial* unique index
  `idx_pv_printed_number (document_id, revision_id, number) WHERE deleted = 0`
  replaces the plan's `UNIQUE (document_id, revision_id, number)`. The plain
  UNIQUE would have rejected the emitter's own reuse case, where an edition
  deletes the old 4.1.3 and prints a new 4.1.3 at the same revision.
- **Top-level `number` = the latest version's number**, which the build
  checks. So the latest version never carries a different per-version
  `number`.
- **In-force check:** `_number_clashes` sweeps each document's versions in
  revision order and fails if one number names two provisions in force.
- **Ref resolution** (`DocIndex.provision_at`): a number names the provision
  whose latest version up to `to` (skips not applied) prints it. One in
  force wins over one deleted in the range, so a ref to a deletion still
  fails as before ("to a revision that deleted it"). Excludes are read at
  the entry's highest include `to` *in the same document*. An exclude with
  no include ref to its document now fails with "no include ref … to read
  its number at", where before it failed with "removes nothing".
- **Verified on real data:** with `key` injected into a copy of `data/`
  (the same output the emitters now give), the v7 build's resolved rows are
  byte-identical to v6's (98,145). Paragraph refs (396 verified,
  5 unverifiable), and every test in `tests/` and `tools/s99_tests`, pass.
- **Report:** `cert_basis_report.json` gains `documents`: per `ISSUER/slug`,
  revisions, provisions, versions and `renumbered`.
- **Tools:** `s00_common/provision.py:provision_record()` (key defaults to
  number) is used by `faa/regs`, `car` and `easa/cs`.
  `s00_common/tcds.py:KnownDocuments` records the number per version and
  reads numbers at `to`, as the build does.
- **Re-emit check:** re-emitting FAA (23, 25, 27, 29, 36), CAR and EASA
  (23–29) into a scratch root gave `key == number == file stem` for every
  provision. 114 files also differ in text layout (line breaks and
  indentation only; flattened words are identical). The cause is committed
  layout fixes (`3e61723` and earlier) that `data/` had not been re-promoted
  with, not v7. Review them as part of the step 1 promotion.
- **App impact (for the FARFETCHed repo):** check `user_version` 7.
  `provisions.number` keeps its meaning (the current number), so lookups
  keep working. Show `provision_versions.number` for a historical version.
  `provisions.number` is no longer unique per document, so use `key` (or
  `id`) as the identity. Docs: `docs/SQLITE.md`.

Part B notes for the implementer:
- Emit DOD files with `provision_record(..., key=...)`. Set the per-version
  `number` only when it differs from the top-level (current) number. A
  deleted version needs no `number` when the number it was last printed
  under is the current one, which is always the case.
- When one edition both deletes old key X (number N) and starts a new key
  with number N, that is allowed (the partial index exempts deletions).

## Status and session record (2026-11-03)

Planning only: nothing implemented. Decisions taken with the user this
session: key + number identity (schema v7), whole printed block as text,
issuer `DOD`, links/relations deferred.

Sample evidence behind the identity decision (12 paragraphs of 516C matched
by TF-IDF cosine against every numbered paragraph of each edition; crude,
indicative only — 516/516A scores understate because they lack the
Standard/MoC blocks):

| 516C paragraph | 516 | 516A | 516B | B Chg 1 | 516D |
|---|---|---|---|---|---|
| 4.1.1 Requirements allocation | 4.1.1 | 4.1.1 | 4.1.1 | 4.1.1 | 4.1.1 reworded ("Operational usage", 0.25) |
| 4.1.3 Commercial derivative aircraft | no match (516 4.1.3 is other text) | 4.1.3 | 4.1.3 | 4.1.3 | none (folded into 4.1.1 MoC (4)) |
| 5.1.1 Design flight and ground loads | weak | weak | weak | 5.1.1 | weak (5.1 restructured) |
| 5.2.3 Aeroelastic, control surfaces | — | 5.7.3 | 5.2.3 | **5.2.2** (renumbered) | weak |
| 6.1.2 Primary flying qualities | weak | weak | weak | weak | 6.1.4.x |
| 7.1.1 Safety-critical propulsion | weak | weak | 7.1.1 | 7.1.1 | weak |
| 8.3.1 Fuel integration | weak | weak | 8.3.1 | 8.3.1 | 8.3.1 (0.73) |
| 12.1.2 Generation system operation | 12.1.2 | 12.1.2 | 12.1.2 | 12.1.2 | 12.1.2 |
| 14.1.1 System safety process | 14.1.1 | 14.1.1 | 14.1.1 | 14.1.1 | moved to 4.4 (§14 blank in D) |
| 15.2.1 Functional coupling | 15.2.1 | 15.2.1 | 15.2.1 | 15.2.1 | 15.2.1 (0.70) |
| 16.1.1 Servicing instructions | 16.1.1 | 16.1.1 | 16.1.1 | 16.1.1 | 16.1.1 reworded |

Source-published change information:
- 516B Appendix A.3 "Cross-reference table of major section changes from
  MIL-HDBK-516A to MIL-HDBK-516B" (section-level, e.g. "5.2 Structural
  dynamics — previously 5.7"; "4.3.2–4.3.6 incorporated into 4.3.1").
  Evidence for `dod_hdbk.tsv` rows and later ROADMAP-4 relations.
- 516D Foreword ¶3: §10 → §11, §14 → §4, §18 → §9, 8.7 → new §10; criteria
  consolidated across sections.
- 516C and 516D §21.3: no marginal change notations "due to the extent of
  the changes".

Layout notes seen while sampling:
- 516/516A body gives the criterion only; the 3-column appendix table maps
  each criterion to support docs and 14 CFR sections.
- 516B: `DoD/MIL Doc:` / `FAA Doc: 14CFR references: ...` under each criterion.
- 516C: `Criterion:` (sometimes `Criterion (Army, Navy and Air Force):`),
  `Standard:`, `Method of Compliance:`, `References:`.
- 516D: no `Criterion:`; `Standard:` + `Method of Compliance:` with
  "Prior to entering flight test ..." phase lines, verification-method words
  (`Examination.`), and `(1)`, `(2)` items. Service-applicability `X` matrix
  appears in `-layout` output (use raw mode, strip it).
- Rough numbered-paragraph counts (crude parser, sections 4–20):
  516 781, 516A 867, 516B 905, B Chg 1 908, 516C 1078, 516D 1170.
