# ISSUES.md

Open issues and review notes. Items are things a later review should check or
decide. Nothing here is a known build failure. Dates are 2026-10-31 unless noted.

Source: the "authority-only amendments" work (data commit `66a087b`, tools
commit `07c543c`). See `tools/docs/FAA_DRS.md` §3.8 and
`tools/regulations/faa/authority_only.py`.

## Data questions (need a human or a source)

1. **23-56 and 23-60 are undeclared and unexplained.** DRS has no document for
   either. A Federal Register full-text search found no rule naming them (the
   hits were airspace rules, ADs and part numbers), and eCFR and `regs.csv`
   don't list them. This is absence of evidence, not proof they were never
   issued. Not checked: a general web search, FAA's own amendment-history
   tables, FR rules published between 2002-03 and 2007-08 (23-56) and
   2008-12 and 2011-08 (23-60) read by hand. If a TCDS ever cites one as a
   range endpoint, the build will reject it ("unknown revision"); that is the
   intended behaviour until a source turns up.
2. **Existing `_document.json` dates disagree with the manifest** (reported in
   `tools/out/reports/incomplete_authority_only.tsv`, nothing was changed):
   - 23-43: data 1993-05-10, manifest 1996-01-04 (61 FR 252, doc 96-135). The
     manifest value comes from the `_rule_for` correction logic (report kind
     `fr_correction_names_designator`) and looks wrong to me: the 23-43 CITA
     cite is 58 FR 18970 (1993-04-09).
   - 23-51: data 1996-03-12, manifest 1996-03-11.
   - 23-58: data 2009-07-09, manifest 2008-04-07 (73 FR 12542, FR API).
   Decide which source is right per amendment, fix the manifest logic or the
   data, and promote any change with `emit --replace`.
3. **25-118** is a DRS `Sec. 0.0` document saying the number "was inadvertently
   skipped and will not be used". It is deliberately not declared. A TCDS that
   cites "through 25-118" would need a human decision (probably use 25-117).
4. **27-41 and 29-48** have no DRS document and are undeclared. Same open
   question as item 1.
5. **Part 36 gap list is mostly noise.** The manifest assumes contiguous
   numbering. Part 36 isn't: 36-32 is 2022, 36-54 is 2002 (report kind
   `ordinal_out_of_date_order`). 36-33 to 36-53 (21 designators) have no DRS
   document and probably never existed; unconfirmed. Separately, 36-1, 36-2,
   36-3, 36-5, 36-11 and 36-32 have real sections in DRS that the eCFR-derived
   manifest never listed (CITAs restart). They need the section pipeline, not
   this one.
6. **Authority-only declarations for Parts 25, 27, 29 and 36 are not promoted.**
   `data/` only holds Part 23. 25-85, 27-31, 27-39, 29-37, 29-46, 36-21 and
   36-23 are in the regenerated `tools/out/work/manifest_faa_{p}_part_amendments.json`
   and will flow in with those parts' bulk emits. Check they are there when
   each part is first promoted.

## Code and process risks

7. **DRS lookup cache never expires.** `tools/out/cache/drs/far_amendment/`
   caches hits and misses for good (`--force` refreshes). A designator that is
   a gap today and gets a DRS document later stays "none" until forced. Gaps
   are by definition below an existing ordinal, so this is unlikely, but a
   time limit like the TCDS listing's 24 h would be cheap.
8. **The verdict trusts DRS listing fields, not the document text.** `judge()`
   uses `Section == "Sec. 0.0"` plus the title. I read the text of all ten
   documents by hand once (each only revises or "continues to read" the
   authority citation, 23-55 also removes SFAR 41) but the code does not. A
   `Sec. 0.0` document with an unexpected title is `unrecognised`, not declared.
9. **FR cite lookup is a window heuristic.** It scans weekdays from 30 days
   before to 7 days after the DRS effective date for a rule whose docket line
   names the designator. Zero or several matches means no cite and an
   `authority_only_no_fr_cite` report row (the revision is still declared).
   27-39 and 29-46 have an empty FR `effective_on`, so the date cross-check
   does not apply to them. DRS prints their docket as `FAA-19998-4390`; the FR
   has `FAA-98-4390`.
10. **`emit --part` assumes designator prefix = part** (`23-47` belongs to `23`).
    True for FAA; wrong for CAR or EASA designators. Fine while emit is
    FAA-only.
11. **Shared staging.** `tools/out/extracted/faa/` held 1,280 files from another
    session and `promote` scans all of `tools/out/staged/`. I scoped `emit`
    with a missing `--in-dir`. A plain `emit` then `promote` would sweep in
    everything. Consider a `--only` filter on `promote`.
12. **Any test that calls `manifest.main` must pass `--skip-drs` or patch
    `far_amendment_documents`**, or it will try the real DRS. I fixed
    `test_main_end_to_end`; nothing enforces it for new tests. A conftest guard
    that fails on a real DRS request would.
13. **Part 23 must be run with `--as-of 2017-08-29`.** The default is now the
    newest eCFR date, which is the post-rewrite Part 23. The README says so;
    nothing enforces it.
14. **Network-call counter.** A DRS lookup adds 1 to `http.network_calls`
    however many pages it took, so the stderr "network calls: N" undercounts.
15. **Regenerated work files.** `manifest_faa_{25,27,29,36}*` in
    `tools/out/work/` were overwritten with this run's output. The previous
    copies were only in a session scratchpad and are gone. Differences are the
    new declarations plus whatever the other session's manifest changes did.

## Not done

- No aircraft were added. SR20 (A00009CH Rev 25, through 23-47) and DA 42
  (A57CE Rev 34, through 23-55) can now be, but any TCDS citing 23-56 or
  23-60 cannot (item 1).
- `ruff`, `mypy`, `pytest` and `build.py` all passed after the change. The
  build report (`cert_basis_report.json`) was not reviewed beyond the summary
  line.

## EASA CS ingestion (2026-10-31)

Pipeline: `tools/regulations/easa/` (see `tools/docs/EASA_CS.md`). Reports
named below are under `tools/out/reports/`.

1. **CS-29 Amendment 10 exists only as a corrigendum.** The EASA listing has
   no "CS-29 Amendment 10" entry, only "Amendment 10 — Corrigendum" (ED
   Decision 2021/016/R), dated 17/12/2011 on the listing; the year must be
   2021. The pipeline uses the corrigendum file as the Amdt 10 text and
   borrows the effective date 2021-12-18 from CS-27 Amdt 9 (same Decision).
   `emit --cs 29` refuses to run until a human accepts this
   (`--accept-needs-human`). Check the corrigendum against the original
   Amdt 10 (if EASA still has it anywhere) and confirm the date.
2. **CS-23 Amdt 2 ED Decision number.** The website lists ED Decision
   2010/007/R; the CS-23 Amdt 6 preamble lists Amendment 2 under 2010/008/R
   (`manifest_easa_cs23_report.tsv`, `decision_mismatch`). The catalogue uses
   the website's number (whose Decision PDF gives the effective date
   2010-09-09). One of the two is wrong.
3. **CS-23 Amdt 1 PDF prints page 1–E–25 twice** (pages 105 and 106 of the
   file, CS 23.1199(b)–23.1203, different hyphen glyphs). `extract.py` drops
   the repeated page (`repeated_page_dropped`). Check CS 23.1199–23.1203 at
   CS23-1 against the PDF.
4. **Spurious CS-23 versions from formula glyphs** (`emit_easa_cs23_report.tsv`,
   `unexplained_change`): 23.425 and 23.443 at CS23-1 differ from CS23-0
   only by a superscript "2" that only the Amdt 1 PDF yields; J23 at CS23-1
   and CS23-4 differs by "(degrees)" placement and similar. These produce
   versions EASA never made. Options: hand-delete them after promotion
   (manual provenance), or add a per-paragraph override list to `emit.py`.
   Real editorial changes look the same to the comparison (23.572 at CS23-1
   fixes "pargarph"), so the comparison was not loosened further.
5. **CS-23 Amdt 3, CS 23.851: preamble and change information say amended,
   the extracted CS text is identical** (`manifest_change_not_in_text`).
   Probably only the "(See AMC 23.851 (c))" reference or the AMC changed.
   No version is emitted; check.
6. **Appendix I to CS-23 (Seaplane Loads) has no text layer** (figures only)
   in every issue: emitted as `TEXT MISSING`.
7. **Appendix titles that wrap** are joined only after a dangling word
   ("of", "with", …). Others may keep half a title, e.g. A23 before the
   dangling-word rule. Spot-check `canonical_title` of appendices.
8. **Tables and formulas are flattened** into running text (as in the FAA
   data). Appendix tables (e.g. C23) are hard to read; consider a table
   representation later.
9. **CS-23 Amdt 5 and Amdt 6 texts come from republished files**
   (2020 "Amdt 5 + AMC & GM Issue 3", 2026 "Amdt 6 + AMC & GM Issue 5"),
   recorded in `provenance.notes`. EASA says only AMC/GM changed in those
   republications; not verified against the original 2017/2023 files.
10. **Concurrent FAA tool edits.** During this work, 9 FAA tool tests
    (`test_faa_extract_manifest.py`, `test_faa_manifest.py`,
    `test_faa_worklist.py`) failed after `tools/regulations/faa/{extract,
    manifest,overrides,worklist}.py` were modified at 22:28 by another
    session. Not caused by the EASA changes; check them separately.
11. **CS-27 Amdt 7 PDF has broken font encoding in places** (e.g. Appendix C
    date "4 February 2016" extracts as control characters plus
    ")HEUXDU"). Text in that font is unusable; affected paragraphs show up as
    `unexplained_change` at CS27-7 and CS27-8 in `emit_easa_cs27_report.tsv`.
    Candidates for OCR or manual correction.
12. **Formula blocks drift between neighbouring paragraphs** (CS 27.1401 /
    27.1411 / 27.1415 integral formula across Amdts 4–8). A display formula
    set between two paragraphs can be read into either; the "change" is
    reported as `unexplained_change`. Formulas are also flattened to text.
13. **CS-27 Amdt 10 is a re-typeset** (single-column, appendices printed next
    to the paragraphs citing them). Small textual differences ("(l)" →
    "(1)", "27.175 (a)" → "27.175(a)") make many paragraphs differ from Amdt 9
    without a preamble entry. The new text is emitted as a CS27-10 version
    (the PDF is the authority) and each is listed as `unexplained_change`.
    A human should decide whether to keep them as versions.

### EASA: further work (state at commit)

Done: schema v2 (`deleted` versions); `discover` / `manifest` / `extract` /
`emit` for CS-23/25/27/29; all PDFs, change information and ED Decisions
downloaded to `input/Regs/EASA/`; CS-23 staged and checked with a scratch
build (448 provisions, 845 versions, 380 deletions at CS23-5). Nothing is
promoted into `data/` yet.

Still to do:
- Re-run extract → manifest → emit for all four CSs after the last extractor
  changes (Symbol-font map, appendix placement, "Annex to IV" footer), then
  review each `emit_easa_cs{n}_report.tsv`. CS-25 (29 amendments) and CS-29
  have not been through emit at all.
- CS-29: decide on Amdt 10 (item 1) before `emit --cs 29 --accept-needs-human`.
- Resolve the spurious-version cases (items 4, 11, 12, 13): either a
  per-paragraph override list in `emit.py` or manual edits after promotion.
- Spot-check about 5 paragraphs per CS against the PDFs, then
  `promote --dry-run` and promote (by hand).
- Smoke queries after promotion: CS 25.1309 versions, CS 23.2510 from
  CS23-5, a whole-document CS23-6 ref excluding the old paragraphs.
- EASA TCDS parsing (cert bases citing "CS-25 Amendment N") — not started.
- `tools/out/staged/` also holds other sessions' output; promote with care
  (item 11 of "Code and process risks").
