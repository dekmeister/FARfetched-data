# Multi-model TCDS (Boeing 737, A16WE Rev 82): handover

Consolidated 2026-11-14 from the 2026-11-10 proposal (693 lines), the A2NM
reading (2026-11-11) and the step logs. The full text is in git history
(`git log -- reviews/2026-11-10-multi-model-tcds-proposal.md`). Delete this
file when the 737 is promoted and the leftovers below are in `issues/`.

**Status: in progress.** Steps 1–5 are done and promoted. Steps 8 (737
Classic) and 9 (NG, Section VII parts A–D) are built and committed (tools
`858927e`) but **not read, not selected, not promoted**. Steps 6, 7 and 10 are
not started. A16WE is not in `overrides/faa_tcds_selection.tsv`, so a rebuild
stages none of it. Don't add it until the part E decision (below) is answered.

## Goal

Stage Boeing 737 (FAA A16WE, 17 models, one Table A-1 with a column per MAX
model) and the shapes it needs, without a contract change: parsers handle a
TCDS section that holds several models, and each shared basis line is copied to
the models its own scope names.

## Decisions taken (all answered; nothing waiting on you except part E)

- **D1 copy per model.** One `tcb` per model, shared lines copied to every model
  the line's scope names. No schema or SQLite change. `display_order` is
  1..N per TCB, so a shared line may have a different number on each model.
- **D2 the 17 heading designations are the models.** BCF and IGW are
  `applicability` on -800 and -700, not models.
- **D3** the -200C takes the "737-100 & 737-200 Series" basis through a reviewed
  `overrides/tcds_model_groups.tsv` row (written at step 8, with evidence).
- **D7** the entry-corrections file (`overrides/tcds_entries.tsv`, TCDS-2) was
  built at step 4. Actions: `drop`, `type`, `references`, `notes`,
  `applicability`, `scope`, `copy`. Never `raw_reference`.
- **Verification** is scripted (raw text in the PDF, line coverage, row checks,
  scratch build, corpus line diff), then Sonnet subagents read the changes. No
  manual reading by the assistant. A2NM and A16NM were read this way on
  2026-11-13: no new major finding.
- Category comes only from a reviewed `tcds_categories.tsv` row, never inferred.

## Done and where

| Step | What | State |
|---|---|---|
| 1 | Decision recorded in `docs/DATA_FORMAT.md` and `docs/SCHEMA_HISTORY.md` | done |
| 2 | Heading shapes, page footers, numeral-gap guard (TCDS-14) | done |
| 3 | Shared blocks with per-line model sets (`attach.py`, `lists.py`, `amdt_table.py`); A2NM (757) goldens | done, promoted |
| 4 | `tcds_entries.tsv` corrections; A2NM selected | done, promoted |
| 5 | A16NM (Astra, SPX, G100, G150): zone tables, bullets, `scope`/`copy` actions; manufacturer registry (`manufacturers.tsv`, tools 1578760) | done, promoted |
| 8 | 737 Classic (-100 … -500): six models stage; scratch build passes | built, committed, **not read or promoted** |
| 9 | 737 NG Section VII parts A–D (-600/-700/-800) | built, committed, **not read or promoted** |

Modules are in `tools/s02_emit/faa/tcds/` (rules in `tools/s00_docs/FAA_TCDS.md`
and `PIPELINE.md`). The corpus line diff of all 1,506 FAA TCDS is in
`tools/s00_docs/reviews/2026-11-13-tcds-corpus-diff.md`; rerun it after every
parser change.

## Open, in order

1. **Part E (737-800BCF) is wrong and must not be promoted as is.** Its three
   grid tables (Section/Amdt/Applies To, the 25-0 thru 25-138 exceptions table,
   SC/exemption/ELOS tables) are vertically centred cells. Text parsing glues
   20+ rows per entry, duplicates one, and drops rows 25.1301–36.103 and the
   "25-0 through 25-138 with exceptions" headline.
   **Decision needed (asked 2026-11-13):** build grid parsing now (step 7,
   `pdf_grid.py`), or hold the -800 back until it exists.
2. **Sections VIII–X (-700C, -900, -900ER):** the same pass as part A. Known now:
   the scratch build fails on 25.853(d)(3) at 25-72 (-700C, -900; same as A2NM:
   `references: []` plus a note row) and on 25.831(a)(g) at 25-41 (-900ER); one
   3,595-char glued ESF entry on the -900; about 30 unreferenced regulation lines
   each on -700C and -900.
3. **A16WE golden** for all staged models; extend `test_a16we_classic.py` for the
   NG rules; document the NG rules in `FAA_TCDS.md`; then subagent reading of
   Classic and NG; then add to the selection list.
4. **Split `segments.py`** (about 620 lines; the limit is about 350) before it
   grows.
5. **Log two minor reading findings** to `DATA_FINDINGS.md` (not done): SPX/G100
   ESF entry 22 glues the 25.1203(a) ESF to the lead-in of 23-24; entry 25 glues
   the optional-requirements intro and its two rows.
6. **Before promoting anything from A16WE:** scratch build (copy `data/` to the
   scratchpad, add the staged A16WE models, `build.py --data-dir … --out …`) and
   read the levels in `cert_basis_resolved`. Goldens pin no provisions, so only
   the build catches a missing paragraph.

How to look at it again: `pdftotext -layout` A16WE_Rev82 and read pp. 34–42
(VII), then VIII–X. One TCDS with its override rows parses with
`parse_tcds_text(raw, "A16WE_Rev82", known)` (see the corpus-diff file).

## Later steps (not started; move to `issues/` if this file closes first)

- **Step 7, `pdf_grid.py` and 737 MAX (step 10).** Table A-1 is a grid with merged
  cells across models. `pdftotext` can't tell a merged cell from a single one;
  the PDF draws real cell rules that `pdftocairo -svg` exposes. A prototype on
  pp. 72–106 recovered 600 rows, 90 of them varying by model. Plan: a reusable
  extractor plus a second method (cell tiling from word centres) that fails
  loud on disagreement. Treatment per cell: an amendment gives an entry with a
  scoped ref `to: 25-N`; `NA` gives an entry with `references: []`; `N/A` is
  decision D4 (recommended: an `other` entry with `references: []`); a blank
  cell gives no entry; System/Area and Notes go to `applicability`; the source
  column goes to `applicability_notes`. The 737-8 whole-part headline gets
  `references: []` because A-1 lists every Part 25 section in force. Section VII
  keeps the include plus an `exclude` per section-level exception. Appendix
  rows (`F25.3`) map to the single `F25` provision, so `references: []` at
  first. Open decisions: D4 (N/A cells), D5 (headline stays `[]`, recommended),
  D6 (how much of the 600 rows subagents read; proposed: all 90 varying rows,
  a 5% sample of the rest, every `NA`, `(See Note)` and appendix row).
- **Step 6, EASA port** of the shared-block rules: IM.A.503 (C90A/GT/GTi), then
  IM.A.071 and IM.A.188. `scope`/`copy` are fatal in the EASA parse today.
- **Issues this work touches:** ETCDS-6 (closes at step 6; its TBM 700 example
  is wrong: that TCDS keys its basis by variant in B.II), ETCDS-7 (narrows),
  TCDS-5 (narrows), TCDS-13 (Parts 26 and 34 aren't in the dataset, so 737 lines
  stay unresolved), TCDS-12 and ETCDS-15 (more Part 36 wording cases).
  Proposed new issue: a TBM 700 variant-keyed basis table (`easa-tcds.md`).

## Open questions from the A2NM reading (answered unless noted)

Category (Q1) by a reviewed row; Part 26 compliance on p. 7 (Q2) is handled by
tools 75edc06 (TCDS-15); not checked whether A2NM's Part 26 references have
reached `data/` yet; Exemption 5613 as one
exemption (Q3); two-level cells as separate entries with `applicability_notes`
(Q4). **Still a known limit (Q5):** a paragraph can't be excluded from a
headline, so the resolved 757-300 basis holds §25.858 whole at 25-85 and §25.853
whole at 25-83 although the TCDS excludes (a) and uses the later (d)(3)
numbering. Same class as TCDS-16 (`issues/faa-tcds.md`).
