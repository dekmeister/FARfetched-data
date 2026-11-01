Restructure tools/aircraft/faa_tcds.py into a three-stage TCDS parser
(segmentation → classification → interpretation), with golden regression
tests and a corpus-wide coverage report. Then extend it to the layouts
listed below.

## Why
The parser handles one TCDS end to end today: A47CE Rev 17 / DA 40, now in
data/aircraft/diamond-aircraft-industries-inc/da-40.json. A trial on three
other contemporary Part 23 TCDS failed at different stages (details below).
Edge-case fixes piled into one code path will regress TCDS that already
work. The goal is one module whose stages fail and get fixed independently,
guarded by golden tests and measured across the corpus.

## Read first
CLAUDE.md, README.md (aircraft format and resolution rules), tools/CLAUDE.md,
tools/README.md, and tools/docs/FAA_TCDS.md (layout notes and schema gaps).
Then read the whole of tools/aircraft/faa_tcds.py and the tests in
tools/tests/aircraft/.

Hard rules that apply here:
- Only tools/regulations/promote.py writes to data/. The parser stages to
  tools/out/staged/aircraft/.
- `raw_reference` is verbatim TCDS text. Never normalise it.
- Stdout = data, stderr = progress. Take paths from tools/common/paths.py and
  use common/io.py.
- When a reference isn't confidently understood, leave `references: []` and
  say so in the report. Never guess.

## Target architecture (keep it in one module unless it clearly earns a split)
1. **Segmentation (layout-specific).** Find the model blocks and the
   cert-basis block, then cut it into TCDS lines with their verbatim scope
   (`applicability`). Each layout is a small tokenizer. A detector picks one
   and records the choice in the report; the existing `detect_mode()` is the
   seed of this. Layouts are known so far:
   - **bullet**: A47CE. Dash bullets under "… the following is the
     certification basis:" wrappers. A bullet back at the wrapper's indent
     after a blank line closes the scope.
   - **outline**: A1WI. `1. a.` numbering, serial-range sub-items.
   - **label-prose**: A00003SE (Textron LC40/LC42/LC41/T240).
     `Certification Basis:` in a two-column label layout, then one prose
     paragraph; ELOS under its own label follows.
   - **pertinent-to-all**: A00009CH (Cirrus SR20/SR22/SR22T). Model headings
     are `I - MODEL SR20, (NORMAL CATEGORY), …` (dash, capitals). The basis
     sits under "DATA PERTINENT TO ALL MODELS" in `Model SR20:` /
     `Model SR22:` sub-blocks. Each sub-block has a base line, a list of
     per-section raised levels ("except as follows: 14 CFR 23.573, … thru
     Amendment 23-48;"), then serial- and equipment-scoped additions ("In
     addition …, for SR20 S/N 1423 thru 1877 …").
2. **Classification (shared).** Decide the `entry_type` of each line,
   regardless of layout.
3. **Interpretation (shared, conservative).** Turn a line into `references`
   per the README resolution rules (`to`, `skip`, `provisions`, `paragraph`,
   `effect`). Resolve only documents that exist in data/documents/ (current
   behaviour). Report anything left uninterpreted.

## Golden regression tests (do this first, before refactoring)
- Turn today's behaviour into goldens: for A47CE Rev 17 / DA 40, the parsed
  output must equal data/aircraft/diamond-aircraft-industries-inc/da-40.json
  exactly. Add the A1WI outline case too. Store the fixture text (cert-basis
  block, or whole stripped text where model splitting is under test) under
  tools/tests/fixtures/tcds/ and the expected JSON beside it. The existing
  A47CE fixture is tools/tests/fixtures/tcds/A47CE_Rev17_da40_cert_basis.txt.
- Every layout or TCDS you add gets a golden. A fix that changes any
  existing golden must be a deliberate, explained change.
- Keep unit tests for each stage too (tokenizer, classifier, interpreter).

## Corpus coverage report
Write a batch mode or a sibling script (e.g. tools/aircraft/faa_tcds_coverage.py)
that runs over input/TCDS/FAA/ (about 1,500 PDFs; current revisions are in
tools/out/work/tcds_catalogue.tsv). It writes a TSV to stdout and to
tools/out/reports/tcds_coverage.tsv, one row per (TCDS, model), with these
columns:
- layout detected
- entries
- regulation lines
- lines resolved
- unresolved reasons, counted (no pattern / document not in dataset /
  unknown revision)
- schema-valid

Cache pdftotext output so re-runs are cheap. Print totals to stderr. Use it
to rank which layout or phrase to fix next by how many TCDS it unlocks.
Record the before/after numbers in your summary. Staging the whole corpus
is not the goal; the report is.

## Known defects to fix (found 2026-10-31, each needs a test)
- CERT_BASIS_RE anchors on any line starting with whitespace +
  "Certification Basis", including prose like "(see Certification Basis)
  must be installed" (A00003SE line 128). Anchor on the label position.
- The interpreter requires "14 CFR Part N". Also accept "Part 23 of the
  Federal Aviation Regulations (FAR)", "FAR 23", "14 Part 23" (already
  handled), and "thru Amendment 51" without the part prefix (seen in Cirrus).
- Section lists at a level ("14 CFR 23.573, 23.575 … thru Amendment 23-48")
  → one ref with `provisions`. Within a base line's "except as follows" block
  they belong to the SAME entry as the base ref, so README rule 2 (scoped
  overrides document-wide) applies.
- The DA 42 (A57CE Rev 34) splits "Special Conditions:" into its own entry,
  and classes `23-167-SC …` items as `other`. A header line should scope its
  items, not be an entry.
- On the DA 42 NG / M-NG, the "NOTE: … equivalent to 14 CFR Part 23 …
  through 23-55" sentence merges into the JAR line, so the Part 23 line goes
  unresolved.
- Amendment 23-64 references (the 2017 Part 23 rewrite: §23.2270, §23.2610,
  §23.2325, …) aren't in the dataset. They must report as "document/revision
  not in dataset" and stay unresolved, never fail.
- CAR 3 lines: data/documents/caa/car-3 and cab/car-3-reissue exist. Add
  interpretation for CAR 3 citations (issuer and slug per README) with goldens.
  The piston fleet is largely CAR 3. Check the 3A12 (Cessna 172) basis as the
  first case. Its current data/aircraft entry is placeholder data that claims
  Part 23; don't overwrite it without asking.

## Open design question to surface, not decide
Cirrus-style additions ("for S/N 1423 and subsequent, 23.561 thru 23-48")
layer on top of the base line. The README rule that overrides never cross
TCDS lines means a G2 SR20 shows §23.561 from both lines, with no record of
which applies to which serial. That ties to Q-04 (structured serial
applicability) in reviews/2026-10-31-db-schema/04-open-questions.md. Emit
these as separate scoped lines with verbatim `applicability`, and write up
the options for the maintainer. Don't change the schema.

Also flag, but don't implement: aircraft files have no `provenance` field, so
a hand-finished aircraft file would be overwritten by a re-parse and
promote. That is the main blocker to running wider; it's schema work.

## Dependencies and coordination
- A separate session is declaring the authority-only amendments 23-47 and
  23-55 in faa/23/_document.json. Until that lands, refs `to: "23-47"` (Cirrus
  SR20) and `to: "23-55"` (DA 42) fail the build with "unknown revision".
  That's expected. The coverage report should count it as "unknown
  revision", not as a parser bug.
- Other sessions work in this repo. tools/ is its own git repo, ignored by
  the parent. Check `git status` in both before editing, don't revert others'
  uncommitted changes, and commit only your files, by explicit path, with
  messages ending in the Co-Authored-By line. Don't push.
- Stage only. Don't promote new aircraft into data/. List what you staged
  and let the maintainer review and promote.

## Done when
- Goldens for A47CE/DA 40 and A1WI pass unchanged across the refactor.
- The bullet, outline, label-prose and pertinent-to-all layouts each have a
  golden.
- The coverage report runs over the corpus, with before/after numbers.
- tools/README.md and tools/docs/FAA_TCDS.md are updated (layouts, stages,
  coverage report).
- uv run ruff check ., uv run mypy . and uv run pytest pass (pytest runs
  tools/tests by default; run tests/test_build.py too).
