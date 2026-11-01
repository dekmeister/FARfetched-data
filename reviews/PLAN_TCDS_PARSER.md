# Plan: three-stage TCDS parser, goldens, coverage report, trial fixes

## Context
`tools/aircraft/faa_tcds.py` handles one TCDS end to end (A47CE / DA 40). A trial over 20
current Part 23 TCDS (`reviews/TCDS_TRIAL_20.md`, ISSUES.md 16–25) found it produces
nothing for 14 of them, and gives silently wrong output on several more: digit-stealing
amendment regex, placeholder rows that are staged, misclassified base lines, lost shared
bases. Two prompts ask for (a) a refactor into segmentation → classification →
interpretation stages, guarded by golden tests and measured by a corpus coverage report,
and (b) fixes for 17 defects. Both prompts are deleted when the work is done.

**Overlap between the prompts:** TRIAL_FIXES items 9–12 (headings, labels, tokenisers),
item 14 (citation forms) and the A1/A8 regex items fall inside PARSER's
"segmentation / interpretation" work and "known defects" (CERT_BASIS_RE, "FAR 23" /
"thru Amendment 51"). Each is done once, and the summary says which prompt item it
closes. Items 1–8, 13 and 17 are new relative to PARSER.

**Decisions taken (from the user):**
- Restricted-category TCDS with no basis (A17SW): don't stage. Report "no certification
  basis on TCDS" in the per-TCDS report and the coverage TSV. No schema change.
- `data/aircraft/cessna-aircraft-company/172.json` (3A12 Rev 42 placeholder that claims
  Part 23) may be replaced by the Rev 89 parse.
- No git add / commit / push (global and project CLAUDE.md override the prompt's "commit
  your files" line). Leave others' uncommitted changes alone: parent `CLAUDE.md`,
  `README.md`, `build.py`, `plan.md`, `schemas/provision.schema.json`,
  `tests/test_deletion.py`, and in tools/ `regulations/easa/discover.py`,
  `tests/e2e/test_deletion.py`.

## Order of work
1. **Goldens first, on today's code.** Add a pure entry point
   `parse_tcds_text(raw_text, pdf_stem, known, catalogue) -> ParseResult` (payloads +
   report), split out of `process_pdf` with no other behaviour change. Fixtures go in
   `tools/tests/fixtures/tcds/`: whole stripped text `<TCDS>_Rev<N>.txt` and expected JSON
   `<TCDS>_Rev<N>_<model-slug>.expected.json`.
   - A47CE Rev 17 / DA 40: expected JSON = `data/aircraft/diamond-aircraft-industries-inc/da-40.json`
     byte-for-byte in content (test-local catalogue TSV supplies the source_url).
   - A1WI Rev 34: today's four models, as a regression baseline. A later deliberate change
     (525B/525C base line, item 3) gets an explained edit to this golden.
   - New `tools/tests/aircraft/test_faa_tcds_golden.py`, parametrised over fixture pairs.
2. **Coverage script + baseline.** `tools/aircraft/faa_tcds_coverage.py`:
   - Inputs: `input/TCDS/FAA/`, limited by default to Current revisions in
     `tools/out/work/tcds_catalogue.tsv` (`--all` for every PDF).
   - pdftotext cache: `tools/out/cache/tcds_text/<stem>.txt` (add `TCDS_TEXT_CACHE_DIR` to
     `tools/common/paths.py`), `--force` to refresh.
   - Output: one row per (TCDS, model), TSV to stdout and `tools/out/reports/tcds_coverage.tsv`
     via `common/io.py`. Columns: tcds, revision, model, layout, staged/skip reason,
     entries, regulation_lines, resolved, unresolved_no_pattern,
     unresolved_doc_not_in_dataset, unresolved_unknown_revision, unresolved_partial,
     schema_valid, cover_models_missing. Plus one row per TCDS with no models found.
     Totals go to stderr, along with a ranked "top failure reasons by TCDS count".
   - Never writes staged files. Run it once on the pre-refactor parser and keep the
     numbers for the summary.
3. **Refactor into three stages** inside `faa_tcds.py`, one module. The goldens must
   pass unchanged.
   - *Segmentation:* `parse_header`, `find_model_headings`, `find_basis_blocks`, a layout
     detector, and one tokenizer per layout returning `Line(raw, applicability)`. The
     detected layout is recorded per model in the report.
   - *Classification:* `classify(raw) -> entry_type`.
   - *Interpretation:* `interpret(raw, known) -> (references, reason)`, where reason is one of
     `ok | no_pattern | doc_not_in_dataset | unknown_revision | partial`.
   - `known` becomes a `KnownDocuments` dataclass: (issuer, slug) → set of designators,
     loaded from `data/documents/*/*/_document.json`.
4. **Fixes**, each with a failing test first (unit test per stage, plus a golden where a
   layout or TCDS is added). See below.
5. **Re-run coverage.** Record the before/after numbers. Stage the trial TCDS plus the
   golden TCDS to `tools/out/staged/aircraft/`.
6. **3A12:** replace the old 172 file (details below).
7. **Docs, ISSUES, cleanup.** Update `tools/README.md` and `tools/docs/FAA_TCDS.md`
   (stages, layouts, coverage script, exit codes). Add new ISSUES.md items. Delete both
   PROMPT files. Leave `TCDS_TRIAL_20.md` in place.

## Fixes by stage (prompt item → change)

### Interpretation (shared, conservative)
- **T1 / A1:** rewrite amendment-number parsing as a tokenizer, not `\d*-?(\d+)`. Accept
  `N-K` or a bare `K` only when the document is known from context. Handles "1 through
  62" → `23-62`, "10 through 20" → `23-20`, and "23-38, 40" → `to 23-40, skip [23-39]`.
- **T14 / A8:** pick the cited part from the *airworthiness* citation, not the first
  `Part N`. Ignore `part 21.29` / `21.183` (section-style). Accept `14 CFR 23`, `FAR Part 23`,
  `FAR 23`, `Part 23 of the Federal Aviation Regulations`, `14 Part 23`, `thru Amendment 51`
  (part from context), and a single `Amendments 23-59` (no range → `to 23-59`).
- **PARSER:** section lists at a level ("23.573, 23.575 … thru Amendment 23-48",
  "23.x as amended by Amendment 23-K. 23.y … 23-J. …", as in 3A12 172R) become one ref
  per level with `provisions`, in the same entry as the base ref, so README rule 2
  applies. `23.1309(a)` becomes `paragraph`.
- **Residual check (T7, partly understood lines):** after interpreting, if any citation
  token is left unconsumed (`23.xxx`, `Amendment NN`, `of Amendment 44`, …), return
  `references: []` with reason `partial`. Never return a partial interpretation that looks
  complete.
- Revisions not in the dataset (23-56, 23-60, 23-64 rewrite §23.2xxx) → `[]`, reason
  `unknown_revision` / `doc_not_in_dataset`. Never a failure.
- **CAR 3:** "CAR Part 3 effective November 1, 1949, as amended by 3-1 through 3-12" →
  `{issuer: CAA, document: car-3, to: CAR3-12}`. "effective May 15, 1956" / reissue →
  `cab/car-3-reissue`, `CAR3R-N`. An undated or ambiguous CAR 3 citation → `no_pattern`.
  Goldens: 3A12 172 and one more CAR 3 case found by the coverage run.
- "equivalent to 14 CFR Part 23 … through 23-55" NOTE lines interpret as today (DA 40
  precedent).

### Classification
- **T3 / A2:** a line that *starts* with, or leads with, a CFR/FAR/CAR airworthiness
  citation is `regulation`, even if it later mentions Exemption / Special Condition /
  ELOS. SC / exemption / ELOS keyword checks only win when the line leads with them.
- DA 62 "Project Specific Policy Memorandum … in 14 CFR Part 23" → `other`.
- Header lines ("Special Conditions:", "Equivalent Safety Items") are not entries. They
  give their items a type hint (PARSER DA 42 item: `23-167-SC` → `special_condition`).

### Segmentation
- **T9 / B1:** heading regex accepts `I.`, `I -`, `I –`, `I. -`, `IA. -`, any case, with or
  without the word "Model"/"Models", and a single unnumbered `Model X (…)` heading. Also
  `(cont'd)` spacing variants.
- **T10 / B2:** designation/category parsing. Categories come from known category words
  anywhere in the heading (with or without parentheses). Seat codes `\d+PCLM`, `6/7/8PCLM`
  and non-category parentheticals (`Malibu Matrix`) are dropped from categories. Strip a
  `\d+ PCLM` seat code out of the designation. No category word found → don't stage
  (report it); don't emit `unknown`.
- **T6 / A5:** a heading naming several models ("Models 172D, 172E, …", "P206C/TP206C")
  emits one file per designation with the same basis. Cover-page reconciliation uses the
  catalogue `models` column: report and count designations that weren't emitted.
- **T11 / B3, B5, PARSER CERT_BASIS_RE:** the basis label must sit at label position (col
  0–8, followed by `:`/`.`/2+ spaces/EOL). Prose like "(see Certification Basis)" no
  longer matches. Handle the doubled label, `(NOTE 16)`, and a second basis block in one
  model (both collected, in order).
- **T5 / A4 (pertinent-to-all):** "Data Pertinent to All Models" / "Data Pertinent to
  Models X thru Y" / "Data Pertinent to Model X" blocks are segmented separately and
  attached to every model they name, not to the last heading. Inside them, sub-labels
  ("Models 172 thru 172P", Cirrus `Model SR20:`) select which lines apply to which model.
  Where a line's model scope can't be matched confidently, it's kept with the verbatim
  sub-label as `applicability`, and the report says so.
- **Tokenizers / layouts** (detector chooses per basis block, recorded in report):
  `bullet` (A47CE); `outline` (A1WI); `paren-numbered` `1)`/`(a)` (PC-24, PC-12, T12);
  `label-prose` (A00003SE, KC-100, P2006T, Kodiak: one entry per sentence/paragraph,
  split on line starts that begin a citation); `pertinent-to-all` (Cirrus, 3A12).
  - **T4 / A3:** outline mode keeps the text before the first number as entries (prose
    tokenizer), so 172R/172S/T206H keep their Part 23/36 lines.
  - Outline/numbered detection is indent-relative (Bristell col 29, C208 col 27).
  - **T7 bullet:** any non-bullet sentence ending in `:` immediately followed by bullets is
    a scope wrapper (TBM "Airplanes … equipped with …:"). Nested scopes are joined with
    `; ` (doc'd convention). A page-break continuation (indented, lowercase or
    mid-sentence after a bullet) is appended to the bullet. A stray leading `-` is never
    an entry start.
  - Table-style additions rows (525B "Additions … Regulation No. Title Level", PC-12
    `14 CFR 23, (23-43) 23.1305(c3)`): one entry per row. The comments column goes to
    `applicability`. Column headings are dropped from `raw_reference`, and the row text
    is kept verbatim.

### Header (T13)
- Holder: also `Type Certificate Holder Record:`, `Holder.`, and a fallback to the
  catalogue `holder` column. Still nothing → don't stage, report it (no `Unknown`).
- Revision: `Revision`, `Revison`, `Rev. No.`, `Rev.` anywhere in the cover. Fall back to
  the filename `_Rev<N>`, and warn on disagreement.
- Date: `Month D, YYYY`, `Mon DD, YYYY`, `DD MON YYYY`, and fuzzy month typos
  (`Septermber`) matched against a fixed list, searched over the whole cover block (up to
  the first model heading, not the first 2000 chars). Fall back to the catalogue date
  with a warning. Null date → warning.

### Staging and process (T2, T8, T15, T17)
- **T2 / A7:** zero entries → **don't stage**. The placeholder row code is deleted. The
  report records `not staged: zero entries`.
- **T15:** no basis on TCDS → not staged, reason `no certification basis`.
- **T8 / A9:** duplicate designations within one TCDS → neither is staged (no guessed
  merge). Reported as `duplicate designation; merge by hand`.
- **T17:** the per-TCDS stderr line becomes `staged N  not staged M  entries E  warnings W`.
  Every not-staged model is listed with its reason. Exit 0 = all clean; 1 = warnings
  but everything staged; 2 = at least one model not staged.

## 3A12 / existing 172.json
After the fixes, parse 3A12 Rev 89. The 172 basis should become the CAR 3 line (`car-3`,
`to CAR3-12`) plus the Part 36 and §23.1559 lines, with their verbatim scope. Promote
`textron-aviation-inc/172.json` with `tools.regulations.promote --aircraft` for that one
relpath, then delete the old `data/aircraft/cessna-aircraft-company/172.json`. The
holder changes, so the slug directory changes. Check `uv run python build.py` is clean
afterwards. All other staged aircraft stay staged for review. Nothing else is promoted.

## Write-ups (no schema change)
- ISSUES.md: Cirrus-style serial/equipment "additions" layered on a base line. Options:
  (a) status quo, separate scoped lines; (b) structured serial applicability (Q-04);
  (c) an entry-level "supersedes entry N for scope S" link. Tie to
  `reviews/2026-10-31-db-schema/04-open-questions.md` Q-04.
- ISSUES.md: aircraft files have no `provenance` field, so a re-parse and promote would
  overwrite a hand-finished aircraft file. This is the main blocker to running wider.
- ISSUES.md: any new data or tooling issues found during the corpus run. Mark items 16–25
  resolved / partly resolved with a pointer to the change.

## Critical files
- `tools/aircraft/faa_tcds.py` (refactor and fixes, one module)
- `tools/aircraft/faa_tcds_coverage.py` (new)
- `tools/common/paths.py` (text cache dir constant)
- `tools/tests/aircraft/test_faa_tcds_{golden,segmentation,classify,interpret,header}.py`
  (new). Existing `test_faa_tcds_bullet.py` / `_references.py` are kept and adapted to the
  renamed API.
- `tools/tests/fixtures/tcds/*` (stripped texts + expected JSON for A47CE, A1WI,
  A00003SE, A00009CH, 3A12, A60EU, A78EU or A00072CE)
- `tools/README.md`, `tools/docs/FAA_TCDS.md`, `ISSUES.md`
- Reused: `common/io.py` (`atomic_write_json`, `read_tsv`, TSV writer),
  `common/paths.py`, the existing `schema_validator()`, `catalogue_source_url()`,
  `strip_page_furniture()`.

## Verification
- `uv run pytest` (tools/tests, including goldens and e2e), `uv run pytest tests/test_build.py`,
  `uv run ruff check .`, `uv run mypy .`.
- The DA 40 golden equals `data/aircraft/diamond-aircraft-industries-inc/da-40.json`.
- `uv run python -m tools.aircraft.faa_tcds_coverage > /dev/null` gives before/after totals
  (TCDS with ≥1 model staged, entries, regulation lines resolved, reasons).
- Stage the 20 trial TCDS to a scratch `--out-dir`, then run `build.py --data-dir` over a
  copy of `data/` + staged output. Expect no placeholder rows and no `Unknown`
  manufacturer. Any build failures are listed in the summary.
- After the 3A12 promote: `uv run python build.py` passes on the real `data/`, and
  `sqlite3 cert_basis.sqlite` shows the 172 basis resolving to CAR 3.
