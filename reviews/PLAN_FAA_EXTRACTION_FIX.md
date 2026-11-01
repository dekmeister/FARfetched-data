# Plan: fix the FAA Part 23/25/27/29/36 extraction pipeline

## Context

Parts 25/27/29/36 went through `tools/regulations/faa/` (manifest → worklist →
extract → emit) on 2026-10-31. Nothing has been promoted. The investigation
found text corruption in rows marked `ok`, and that also affects Part 23 in
`data/`. It also found good rows rejected by the verifier and manifest rows
silently dropped. `build.py` passes, so none of this is caught. The goal is
correct, traceable text for every manifest pair, with every gap visible as
`TEXT MISSING` or `deleted`.

The `deleted: true` work (schema v2) is already in the working tree:
`build.py`, `schemas/provision.schema.json`, `README.md`, `plan.md`,
`tests/test_deletion.py` and its mirror `tools/tests/e2e/test_deletion.py`.
This plan builds on it and does not touch those files except to read them.

## Investigation results (all confirmed; corrections in **bold**)

Raw DRS documents were re-fetched into the scratchpad, plus a full Part 25 DRS
listing and FR API lookups.

- **Root cause of A2–A5 is one bug.** Each DRS field block is laid out as
  `<!-- value -->`, `<!-- connectorValue -->`, `<!-- header -->`,
  `<!-- status -->`, then `<b>FIELD:</b>`. The comments come *before* the
  rendered field. `SECTION RULE:(.*?)</body>` runs into the next block. It stops
  at the first `</body>` (inside the NPRM block's 501 error-page comment, which
  gives the 501 tail) or at the last one (which glues on the NPRM/FINAL RULE
  text). The `Link to eCFR -->` fragment (found in 76 `ok` rows) is a
  `FARSectionRuleLink` comment chopped by the tag stripper. The `connectorValue`
  fallback (header → next connectorValue) reads the *next* block's value. The
  trailing `-` on §25.1093@25-140 is the NPRM block's value. A prototype that
  ends the capture at the first `<!--`, decodes strict UTF-8 then cp1252, turns
  block tags into spaces, and calls `html.unescape` gave clean text on
  §25.965@25-0 (°, ½), §25.1457@25-2 and §25.1093@25-140 (§, °, table cells).
- Defect counts in `ok/warn/assembled` rows (extracted 23/25/27/29/36 +
  appendix parts): U+FFFD ≈ 320, entities ≈ 380, NPRM tail ≈ 560, 501 tail ≈ 36.
  In `data/` Part 23: U+FFFD 115, entities 115, NPRM tail 121, 501 tail 8.
- **date_mismatch (84):** DRS is right for 25-139 (manifest D/M read) and for
  **23-63, 25-144, 27-48 and 29-56: 82 FR 9677 (2017-02-08) delayed 81 FR 90126 to
  2017-03-21.** **36-55 is not a DRS typo:** FR 2025-13972 makes every Part 36
  instruction "Effective July 24, 2026". DRS is wrong (manifest right, FR
  confirmed where online) for 25-23/91/95/96/97 (DRS uses the publication
  date), 25-42 (1998 typo), 25-151, 27-35/29-42 (FR: 1998-09-11), 27-49 and
  29-58. These single-document DRS outliers need checking by hand: 23-0, 23-2,
  23-50, 25-46, 25-60, 29-3.
- **29-39/29-40 swap confirmed against the FR text.** 96-11494 (29-40, effective
  Jun 10) amended §§29.1, 49–87, 1323, 1517, 1587. 96-11493 (29-39, effective
  Aug 8) amended §§29.337–1351, 1587. DRS has them the other way round. The
  manifest also holds phantom pairs from mixing the sources (both §29.49@29-39
  and §29.49@29-40).
- **B3 confirmed:** the DRS listing finds the 404'd sections under `CFR_…` ids
  (25.773@25-144, 25.795@25-145, 25.954/981@25-146, 25.975@25-143,
  25.1707@25-123, 29.773@29-56 and @29-57; the manifest gave both 29.773
  rows the same GUID). The 404'd appendix *subsections* have no DRS subsection
  document at all.
- **C3: DRS has whole-appendix documents** (`Sec. A25`, `C25`@25-140,
  `F25`@25-142, `H25`@25-146/152, I/J/K/L/M/N/O…, ids `CFR_…_apXpt25…`). The
  assembler never looks for them.
- **B4 confirmed:** §29.307's CITA prints `Amdt. 27-26, 55 FR 8001, Mar. 6, 1990`.
  The manifest's 29-30 has the same publication date and FR volume. The cites
  differ by page within one FR document, so match on publication date and FR
  document, not on the exact cite.
- **B2/C1/C2/C5 confirmed:** §25.31, §27.31, §29.31 and §25.871 are absent from
  staging (genuine 97-char sections rejected as `short_text`). §23.615@23-45 has
  an empty body and DRS title `Removed.`. 18 Subpart H/§1801 `25-0` orphans are
  staged as TEXT MISSING. 76 extracted 23-43 rows carry 1993-05-10 while the
  manifest has 1996-01-04, taken from correction 61 FR 252.

## Decisions (from you)

- 29-39/29-40: **FR wins.** DRS docs are relabelled through a reviewed override.
- 2017 rule: **2017-03-21** for 23-63, 25-144, 27-48 and 29-56, including 23-63 in `data/`.
- Part 23: **re-extract and promote**, after you approve the `promote --dry-run`.
- 25-118, 27-41, 29-48, 23-56 and 23-60: **leave undeclared.** ISSUES entries stay open.
- My defaults (say if you disagree): 36-55 for Part 36 → 2026-07-24. Body-less
  `Removed.` → `deleted: true`. `[Reserved]` stays verbatim text, per plan.md.

## Implementation

### Step 1: text extraction (A1–A5), `tools/regulations/faa/extract.py`
- New `decode_doc_content(b64) -> str`: strict UTF-8, else cp1252. Use it in
  `extract_row` and `run_legacy`. `_fetch_fr_html` keeps UTF-8.
- `extract_text_from_html`: end the `SECTION RULE` capture at the first `<!--`
  / `</body>` / end of text. Turn block tags (`td th tr table p br li div h*`)
  into spaces, strip the rest, `html.unescape`, map NBSP to a space, collapse
  whitespace. Share one `_html_to_text` with `_extract_ecfr_rendering`. The
  `connectorValue` fallback reads the comment *preceding*
  `<!-- header: SECTION RULE -->`.
- `strip_action_appendix` stays as a safety net. It also handles a bare
  `Link to eCFR -->`.
- Verifier (`text_issues`): make fatal checks content-based. Fail on U+FFFD,
  a leftover entity, `Error 50x`/501 text, `Issued on M/D/Y`, `NPRM ACTIONS`
  or `Link to eCFR`. `short_text` becomes a non-fatal warning (B2: genuine
  short sections pass).
- Empty body + DRS Title `Removed.` → extracted doc with `deleted: true`
  (verification `deleted`). Empty body otherwise → `empty_text` (fatal).
- Tests (`tools/tests/regulations/test_faa_extract.py`, new fixtures in
  `tools/tests/fixtures/drs/`, trimmed copies of the real raw docs): a cp1252
  doc (°, ½, §), entities, a trailing NPRM/FINAL RULE block, a trailing 501
  block, table cells, the connectorValue fallback, and a `Removed.` doc.

### Step 2: verifier overrides and manifest fixes (B1, B4, C5)
- New reviewed file `tools/regulations/faa/overrides.tsv`. Columns: `kind`
  (`drs_date` | `drs_designator` | `effective_date`), part, designator, DRS
  value, correct value, evidence (FR cite or doc number), note. Loaded by
  manifest and extract. `verify_extracted`: a mismatch listed there becomes a
  non-fatal `override_applied` issue. The original DRS value stays in
  `drs_metadata`, and the override is recorded in `verification`.
  `drs_designator` relabels the 29-39/29-40 documents by (DRS amendment, DRS
  date). Nothing is loosened globally.
- `manifest.py`:
  - CSV date. When D/M gives a date before the amendment's FR publication date
    and M/D doesn't, take M/D and report it (25-139).
  - `_rule_for`. A correction may *identify* the designator, but must not
    supply the effective date when it was published after the CITA entry. Use
    the covering rule's date, else the CSV date. Regression tests for 23-43
    and 25-148.
  - Apply `effective_date` overrides (the 2017 rule → 2017-03-21 with
    82 FR 9677; 36-55 → 2026-07-24).
  - 29-39/29-40: drop the phantom pairs, so each section keeps only the
    designator(s) the FR text gives.
  - B4 sibling rule. A CITA entry for another part's designator with the same
    publication date and the same FR document (same volume; page inside the FR
    rule when the FR API knows it) confirms the row. Report kind
    `cita_sibling_designator`, `needs_human=0`. Remaining
    `cita_omits_designator` CSV rows that have a GUID are fetched anyway (tag
    kept). The extractor's Amendment and Effective Date checks guard them.
- Fix FAA_DRS.md §3.7 (the 2017-03-13 claim) and §3.3 (block layout,
  encoding).

### Step 3: DRS listing fallback (B3), `extract.py`
- Load a whole-part listing once per run with `drs_csv.load_listing` (cached
  `tools/out/cache/drs/far/listing_{part}.json`). Use it for `ecfr_only`
  lookups, for the 404 fallback (`fetch` row GUID 404 → `pick_listing` by
  section and designator → fetch that id), and for appendix work (Step 5).
  Report kind `guid_404_listing_hit`.
- `drs-error` rows still unresolved go through Step 4, so they land in
  `incomplete.tsv` as TEXT MISSING.

### Step 4: no dropped rows (C1) and no orphans (C2), `emit.py`
- New `--plan tools/out/work/fetch_plan_faa_{p}.tsv`. With it, emit:
  - takes only extracted files whose (section, designator) is in the plan.
    Others go to `incomplete.tsv` as `orphan` and are never deleted;
  - emits every plan row not `in_data`/`manual` as a version: verified text,
    `deleted: true`, or `TEXT MISSING` (manifest title, subpart, FR cite;
    reason in `incomplete.tsv`). Exception: `suspect_designator` rows stay
    out and are reported;
  - supports `deleted` in `slim_section_amendment`/`is_section_complete`. It
    checks the build's rules up front (not first, not after a deletion) and
    reports violations instead of writing them.
- Tests in `tools/tests/regulations/test_faa_emit.py`: failed row → TEXT
  MISSING, orphan ignored, deleted version emitted, and the e2e build passes.

### Step 5: appendices (C3)
For each `assemble` row, in order:
1. A DRS whole-appendix document (`Sec. {X}{part}`) for this designator, from
   the part listing. Check the newest designator in its `<p class="citation">`
   with `ecfr_version_verdict`.
2. eCFR point-in-time (`ecfr_doc_for_row`) when effective ≥ 2017.
3. Subsection assembly. The DRS label comes from the listing, not from an
   extracted subsection. `check_appendix_listing` compares only the
   subsections in force at the row's ordinal.
4. Otherwise TEXT MISSING with the reason. §G25.1@25-141 (figure only) is
   expected here; log it.

`fetch_part` rows whose appendix resolves through step 1 or 2 are not needed.
The worklist marks them `covered_by_whole`.

### Step 6: Part 23 re-extraction support
- `worklist.py --refetch-data`: non-manual `in_data` rows get action `fetch`,
  so Part 23 can be re-extracted. Manual rows are never touched.

### Step 7: run, in this order (all outputs under `tools/out/`)
1. `ruff`, `mypy`, `pytest` (root and `tools/`).
2. For each part, 23 (`--as-of 2017-08-29`), 25, 27, 29: manifest (keep copies
   of the old work files in the scratchpad first; ISSUES #15), worklist
   (`--refetch-data` for 23), `extract --force`, `worklist --summary`.
   Move the old extracted files aside to a dated directory under `tools/out/`
   rather than deleting them.
3. Part 36 (C4): manifest, worklist, extract with the fixed code, emit. Not
   promoted.
4. Emit each part into its own staging root (`--data-root …/staged_v2/faa`,
   `--seed-root data/documents/faa --replace --plan …`), to avoid the shared
   staging problem (ISSUES #11). Scratch-build the staged tree with `build.py`.
5. Re-scan for every defect pattern (target: zero in emitted text). Report
   counts per part: verified / TEXT MISSING / deleted / overrides applied.
6. `promote --staged … --dry-run` for every part. Show it to you.
7. **Part 23 only:** after your approval, run `promote` (not `--dry-run`). Then
   `build.py` against `data/`, and `pytest` including the manual-provenance
   tripwire. 25/27/29/36 stay staged.

### ISSUES.md
New entries: the remaining DRS date outliers needing hand checks (23-0, 23-2,
23-50, 25-46, 25-60, 29-3); 29-39/29-40 (resolved, with evidence); 36-55 split
effectivity; G25.1 figure-only; Part 36 Appendix C@36-24 (no DRS text); the
FR docket for 29-58 also naming 25-146 (25-146 is 2018 in DRS); orphan files
left on disk; Part 36 `cita_has_unresolved_entry` rows (11). Update #2 (23-43
fixed) and #6.

## Critical files
- `tools/regulations/faa/extract.py`, `emit.py`, `worklist.py`, `manifest.py`
- new `tools/regulations/faa/overrides.tsv`
- reuse: `tools/regulations/faa/drs_csv.py:load_listing`,
  `tools/common/drs.py` (`list_documents`, `DrsListing`),
  `extract.py:pick_listing`, `ecfr_doc_for_row`, `ecfr_version_verdict`
- `tools/tests/regulations/test_faa_{extract,emit,manifest,worklist}.py`,
  `tools/tests/fixtures/drs/`
- docs: `tools/docs/FAA_DRS.md`, `tools/README.md` (new flags), `ISSUES.md`
- read-only: `build.py`, `schemas/provision.schema.json`, `tests/test_deletion.py`

## Verification
- Unit tests per defect plus e2e `tools/tests/e2e/test_build.py`.
- Pattern scan (`scan.py` in the scratchpad, or a check folded into `--summary`)
  shows zero U+FFFD, entity, NPRM, 501 or `Link to eCFR` hits in emitted text.
- Spot checks against DRS/FR: §25.965@25-0 (°, ½), §25.1457@25-2,
  §25.1093@25-140, §29.53@29-40, §25.773@25-144, §23.615@23-45 (deleted),
  §25.31@25-0 present, the C25 and H25 appendices.
- `build.py` passes against each staged tree and, after the Part 23 promotion,
  against `data/`. The report shows `deleted` and `text_missing` counts and
  no unresolved references.
- No `git add`/`commit`/`push` and no `sudo`. Nothing written to `data/` except
  by `promote`.
