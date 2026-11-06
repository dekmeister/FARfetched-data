# PLAN — Inline markup for formulas and sub/superscripts (GitHub #4)

**Status (2026-11-05): not started.** Planned only; no code or data changed yet.
Spans the data repo (schema **v10**, tools) and the FARfetched app.

**Updated 2026-11-07.** Schema v8 (section headings) and v9 (tables, GitHub
#9) have landed since this was written, so read every "v8" below as **v10**,
and the line numbers as stale. Already in place from v9, to reuse:
`provision_paragraphs.kind` (add `'formula'` to its CHECK rather than adding
the column), `build.plain_text` (the plain form: extend it to strip `_{}`,
`^{}` and `$$`), `tools/s00_common/tables.py` beside the planned `markup.py`,
the app's `services/markup.py` (`blocks()`; extend it with sub/sup segments
and formula lines rather than adding a module), block-by-block rendering in
`provision.html`, the quiet compare display (`markup.display_line`), and the
promote version-count guard (Part B5 is done: `VERSIONS n → m`). Table cells
must not contain `$$` lines; `_{}`/`^{}` inside a cell are fine.

## Context

GitHub issue dekmeister/FARfetched-data#4 (filed from the site's report button) says the following about CS-25 §25.331 (compared against FAA 25.331):
- inline equations are hard to read and should be on their own line;
- subscripts such as t_max don't come through.

A comment adds that §3.159 (Flutter and vibration) has similar problems.

Exploration shows this is mainly a **data** problem, not a view problem:
- The label-line text format has no way to express a subscript, a superscript or a display formula (docs/DATA_FORMAT.md §Text format). Every extractor flattens to plain words.
- EASA (`pdftotext -bbox-layout`, `_merge_rows`):
  - subscripts get merged into the word: `tmax`, `VA`;
  - a stacked fraction comes out in row order, so ω = πV/(2V_A) is stored as `πV ω = 2V A`.
- FAA DRS HTML:
  - has `<sub>` tags (54 of them in 25.331@25-141), but `_html_to_text` drops them;
  - the ω formula is a GIF and is missing from the text entirely.
- CAR 3 §3.159 is OCR, so no geometry survives:
  - CAA `car-3/159` has `Vd` and "valve" (should be "value");
  - CAB `car-3-reissue/159` has `Vu`, "ts" (should be "is"), and figure OCR junk spliced into the sentence.
- App: text is escaped plain text in a `pre-wrap` block, and the compare view word-diffs it. CSP (`style-src 'self'`) rules out client-side KaTeX. Server-rendered `<sub>`/`<sup>` works.
- Scale:
  - ~150 provision files contain formulas;
  - ~230 have subscripted V-speeds;
  - ISSUES TEXT-11 (formulas flattened) and DOD-6 (superscripts lost) already note this.

**Decided approach** (confirmed with the user): the data repo encodes *meaning* with a tiny inline markup in `text`, and the app decides *presentation*.
- Linear notation: `_{…}` for subscript, `^{…}` for superscript, and a `$$ … $$` line for a display formula.
- No TeX and no MathML.
- FAA and EASA extractors recover sub/superscripts automatically.
- Display formulas and CAR OCR fixes come from evidence-backed override rows.
- `_{`, `^{` and `$$` occur nowhere in the current data, so they are safe to reserve. A bare `{ } _ \` does occur in CAR OCR junk and stays literal.

## Part A — Contract, schema v8 (data repo)

1. **docs/DATA_FORMAT.md**: add a new §Inline markup under §Text format.
   - `_{x}` is a subscript and `^{x}` a superscript. The content must be non-empty, must not contain `{ } $` or a line break, and nesting is not allowed. A bare `_ ^ { }` is literal.
   - **Formula block**: a line whose whole content (after the indentation) is `$$ <formula> $$`.
     - It is always unlabelled and obeys Rule 5 (it belongs to the innermost open item).
     - It may contain `_{}`/`^{}`.
     - Fractions and roots are written linearly: `a/(b)`, `√(x)`.
     - `$$` anywhere else is an error.
   - Define the **plain form**, with markup removed (`V_{A}`→`VA`, `$$ x $$`→`x`). The plain form is used for similarity and for comparing words.
   - Amend "layout may only add line breaks and indentation": markup is written by extractors or overrides, never by layout. Layout may move a `$$…$$` span onto its own line.
2. **build.py**:
   - Add `parse_inline`/markup checks, called from `parse_paragraphs` (645) and `_text_format_errors` (934). They fail loud on unclosed, empty or nested markup, a stray `$$`, or a labelled formula line.
   - Add a `kind TEXT NOT NULL CHECK (kind IN ('text','formula'))` column to `provision_paragraphs` (DDL ~149).
   - `similarity_terms` (1726) works on the plain form.
   - `SCHEMA_VERSION = 8` (line 27).
3. **docs/SQLITE.md**: document `kind`, the markup in `text`, and user_version 8. **docs/SCHEMA_HISTORY.md**: add a v8 row with the rationale (linear markup instead of TeX: raw text stays readable, both sides need only a small parser, no dependencies).
4. **Schema JSON**: no field changes. Text stays a string. Confirm no pattern constraint rejects the new markup.
5. **tests/**: synthetic trees for:
   - valid sub/sup and formula lines;
   - each fail-loud case (unclosed `_{`, empty `_{}`, nested, `$$` mid-line, labelled `$$` line, formula as a single-line flat text);
   - `kind` rows;
   - similarity ignoring markup.

## Part B — Tools (read tools/CLAUDE.md and tools/README.md first, follow them)

1. **Shared helpers** in a new `tools/s00_common/markup.py`: `sub()`, `sup()`, `formula()`, `strip_markup()`. Reuse them in the extractors and in structure.py.
2. **tools/s00_common/structure.py** (`segment` 200, `_lay_out` 368, `structure_version` 456):
   - lay out a `$$…$$` span as its own unlabelled line, one level deeper than its item;
   - keep the existing self-check against `build.parse_paragraphs`, which picks up the v8 rules for free.
3. **FAA** `tools/s01_extract/faa/regs/extract.py` `_html_to_text` (168–182):
   - map `<sub>` to `_{}` and `<sup>` to `^{}`;
   - check that footnote/change-bracket `<sup>` use doesn't produce noise; skip those cases if it does.
   - The eCFR fallback (`tools/s00_common/faa/ecfr.py` 231–263) should do the same for `E T="52"`/`SU` instead of flattening with `itertext`. Confirm the T codes during implementation.
4. **EASA** `tools/s01_extract/easa/cs/extract.py` `_merge_rows` (787–813): a piece that is shorter and sits lower than the row's main baseline becomes `_{}`; shorter and higher becomes `^{}`. Stacked fractions are **not** rebuilt automatically; they go to override rows.
5. **Version-drift guard** (ISSUES lists formula drift as a past cause of spurious EASA versions):
   - before promotion, diff the version count per provision against current `data/`;
   - any count that changes means fixing the heuristic or adding a `suppress` row, never accepting silently.
6. **Override rows** (`replace_text`, evidence required; check each against the source PDF/HTML):
   - **CS-25 25.331**, every revision showing the garbled forms (CS25-0, 13, 18, 21, 27):
     - `πV ω = 2V A` (and the CS25-27 variant) becomes `$$ ω = πV/(2V_{A}) $$`;
     - `δ(t) = δ_{1} sin(ωt) for 0 ≤ t ≤ t_{max}` and `t_{max} = 3π/2ω` become formula lines.
   - **FAA 25.331**: insert the missing ω formula after "not less than:" in every version where the GIF dropped it, and make the δ(t) and t_max formulas formula lines.
   - **CAR 3 §3.159**:
     - CAA: `Vd` becomes `V_{D}` (follow the printed form) and "valve" becomes "value";
     - CAB: remove the spliced figure junk span, fix `Vu` to the subscripted form and "ts" to "is".
7. Re-run the pipelines, review the staged diff (expect broad FAA/EASA subscript changes across ~230 files), and promote with the tools' promotion step. Run `uv run python build.py`, ruff, mypy and pytest.

## Part C — App (/mnt/server/Projects/2026/FARfetched)

1. Add `src/farfetched/services/markup.py`. It tokenises a line into segments of kind `text`/`sub`/`sup` and recognises formula lines. It is strict: invalid markup is a contract violation.
2. **Reader** (`services/reader.py` `link_citations` 114–167; `services/citations.py` `segment`):
   - render line by line;
   - give `Segment` a `kind`;
   - run citation linking only inside `text` runs;
   - the segments together must still give back the exact input (CLAUDE.md rule).
   - Template `templates/regulations/provision.html` 115–125: write `<sub>{{ s.text }}</sub>`/`<sup>` with autoescape still on and **no `|safe`**. A formula line becomes `<div class="formula">`.
3. **Compare** (`services/compare.py`):
   - add `_{…}`/`^{…}` as atomic alternatives at the front of `_TOKEN` (43), so a subscript diffs as one token;
   - `_compare.html` writes sub/sup inside `del`/`ins`;
   - `$$` lines are styled as formulas.
   - The unified diff keeps the raw markup.
4. **CSS** `static/css/app.css`: `.formula` gets its own centred line in the serif face, `sub, sup` get `line-height: 0` so line spacing stays steady. No inline styles, because of the CSP.
5. **Contract**:
   - `db.py:22` `SUPPORTED_SCHEMA = 8`;
   - regenerate `tests/fixtures/schema.sql`;
   - `tests/test_schema_drift.py` must pass;
   - `tests/dbbuilder.py` adds `kind`.
   - The app checks the version exactly, so the new DB and the app must deploy together.
6. **Tests**: new `tests/test_markup.py`, plus cases in `test_citations.py`, `test_compare.py` and `test_pages.py` (sub/sup and formula HTML, escaping of `<` inside a subscript, citations next to markup).
7. **App CLAUDE.md**: one rule saying markup becomes `<sub>`/`<sup>`/`.formula` through segments, never `|safe`.

## Part D — Bookkeeping

- **ISSUES.md**:
  - narrow TEXT-11 to the remaining backlog: display formulas in ~150 files still need override rows, and tables are still flattened;
  - note on DOD-6 that `^{}` is now available for the `10-7` cases;
  - add a CAR issue: OCR V-speed subscripts (`Vd`, `Vu`…) need override rows because there is no geometry.
- **GitHub #4**: after the data and app are deployed, draft a closing comment for the user to post (outward-facing, so the user posts it). No git add/commit/push.

## Verification

- Data repo:
  - `uv run python build.py` gives zero unresolved references;
  - `sqlite3 cert_basis.sqlite 'PRAGMA user_version'` gives 8;
  - `SELECT text FROM provision_paragraphs WHERE kind='formula'` includes the 25.331 ω line for EASA and FAA;
  - the version count per provision is unchanged apart from reviewed cases;
  - `uv run pytest`, ruff and mypy are clean.
- App:
  - `uv run pytest`;
  - point the app at the new DB and run it (the `run` skill), then open `/regulations/easa/cs-25/331?vs=faa%2F25%2F331` and `/regulations/caa/car-3/159`;
  - confirm V<sub>A</sub>, t<sub>max</sub>, centred formula lines, a clean CAB §3.159, no CSP console errors, and readable compare view word diffs.
