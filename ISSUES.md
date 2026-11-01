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

## TCDS parser trial: 20 Part 23 TCDS (2026-10-31)

Source: `tools/aircraft/faa_tcds.py` run unchanged over 20 current Part 23 TCDS.
Full evidence, per-TCDS table and suggested order: `reviews/TCDS_TRIAL_20.md`.
4 of 20 gave usable output (all with defects), 2 lost the real basis, 14 gave
nothing usable. Nothing was staged into `tools/out/` or `data/`.

16. **`resolve_regulation` mis-reads undashed amendment numbers.** `\d*-?(\d+)`
    lets `\d*` eat digits: "Amendments 1 through 62" gives `to: 23-2`,
    "10 through 20" gives `23-0`, "23-38, 40" drops the 40. Valid revision, so
    the build cannot catch it. Fix before accepting `thru Amendment N`.
17. **Zero-entry models are staged as a placeholder row** ("parser produced no
    entries; review PDF by hand"). It passes schema and `build.py` (11 files
    here, 10 rows in a test DB) and `promote --aircraft` would copy them into
    `data/`. Should fail loud and not stage.
18. **`classify()` checks Special Condition / Exemption / ELOS substrings before a
    Part 23 citation,** so a base line such as Cessna 525B/525C "14 CFR Part 23
    … 23-54 … Exemption No. 7981" becomes `exemption` / `special_condition` and
    its references are never resolved.
19. **Outline mode drops text before the first number.** 172R/172S/T206H have the
    real basis as a paragraph and only the ELOS list numbered, so the staged file
    holds the ELOS rows and no Part 23 or Part 36 line, without a warning.
20. **Shared "Data Pertinent to …" bases go to the last model only** (172, 206, 208,
    Cirrus, Kodiak, Air Tractor). Models sharing a heading block are never
    emitted (172B, 172E–H, 172K, P206D/E…), and nothing reconciles the cover
    model list with what was emitted.
21. **Model heading regex only matches `I.  Model`.** Dash, en dash, `I. -`, `IA. -`,
    capitals, no numeral and no "Model" word all fail: 105 of 201 current Part 23
    small-airplane TCDS match, a dash-tolerant pattern matches 181. Aviat A8SO
    silently emitted 1 of 7 models.
22. **Tokenisers cover only `- ` bullets and `1.`/`a.` at indent ≤ 8.** `1)` numbering
    (PC-24, PC-12), unmarked prose (KC-100, P2006T, Kodiak) and deeply indented
    numbering (Bristell, C208) give 0 entries.
23. **Variant scope is lost on TBM 700 (A60EU):** 24 flat entries, no
    `applicability`, Part 36 levels 36-17/-22/-28 side by side; a page break
    truncates a bullet; override sections ("… of Amendment 44") are dropped while
    the line still resolves to `to 23-34`.
24. **Header parsing gaps:** manufacturer `Unknown` when there is no
    `Holder␣␣Name` line (30 of 201), dates not in `Month D, YYYY` or beyond
    2000 chars (12 of 201), `Revison`/`Rev. No.` (9 of 201); categories like
    `6/7/8PCLM` or `Malibu Matrix` and seat codes in designations (`AT-504 2 PCLM`).
25. **Other:** `14 CFR part 21.29, … 14 CFR Part 23` resolves the part as 21; `14 CFR 23`,
    `FAR Part 23` and `Amendments 23-59` (no range) are not recognised; duplicate
    designations (A37CE `208B` twice) share a filename; restricted-category TCDS
    (Air Tractor A17SW) have no certification basis field, which the schema
    cannot represent (7 of 201); re-parsing 3A12 at rev 89 conflicts with the
    existing 172 at rev 42 in `build.py`, and the manufacturer would change
    from "Cessna Aircraft Company" to "Textron Aviation Inc.".

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

## FAA extraction fix (reviews/PLAN_FAA_EXTRACTION_FIX.md) — state at commit (2026-11-01)

Done (tools/ commit "Fix FAA DRS text extraction …"): Steps 1–6 of the plan in
code, with tests — cp1252/UTF-8 decoding, `SECTION RULE` capture ending at the
next field block, shared `_html_to_text`, connectorValue fix, content-based
verifier (U+FFFD / entity / 501 / action-tail fatal, `short_text` a warning),
`Removed.` → `deleted: true`; `tools/regulations/faa/overrides.tsv` (18 rows)
used by manifest and extract; manifest month-first CSV dates (25-139),
correction-not-dated rule (23-43, 25-148), `effective_date` overrides (2017
rule → 2017-03-21, 36-55 → 2026-07-24), 29-39/29-40 relabel, B4
`cita_sibling_designator`; extract part listing + `guid_404_listing_hit` +
appendix strategy (whole-appendix doc → eCFR → subsections → TEXT MISSING);
`worklist --refetch-data`, `covered_by_whole`, fetch-anyway for
`cita_omits_designator`; `emit --plan` (TEXT MISSING for failed/unfetched
rows, orphans reported, deletion rules checked, `kept_existing`). Docs:
tools/README.md, tools/docs/FAA_DRS.md §3.3/§3.7/§4.5. ruff, mypy and 622 tests
pass. **No pipeline has been re-run yet: tools/out/ and data/ are unchanged.**

Still to do (plan Step 7, in order):
1. Copy the old work files (`tools/out/work/*faa_{23,25,27,29,36}*`) to the
   scratchpad; move `tools/out/extracted/faa{,_appendix_parts}` aside to a
   dated directory under `tools/out/` (don't delete).
2. Per part 23 (`--as-of 2017-08-29`), 25, 27, 29: `manifest`, `drs_csv`
   (caches `listing_{part}.json`, needed by `covered_by_whole`), `worklist`
   (`--refetch-data` for 23), `extract --force`, `worklist --summary`.
   Expect manifest changes: the 29-39/29-40 rows collapse (phantom pairs gone),
   25-139 dates become 2014-12-01, 23-43 becomes 1993-05-10.
3. Part 36: manifest, worklist, extract, emit. Not promoted.
4. Emit each part into its own root (`--data-root tools/out/staged_v2/faa
   --seed-root data/documents/faa --replace --plan …
   --incomplete tools/out/reports/incomplete_faa_{p}.tsv`); scratch-build each.
5. Re-scan emitted text for U+FFFD / entity / NPRM / 501 / `Link to eCFR`
   (target zero; a scan script is in the earlier investigation scratchpad,
   `scan.py`). Report verified / TEXT MISSING / deleted / overrides per part.
6. `promote --dry-run` per part for review; **Part 23 only** promote after
   approval, then `build.py` on data/ and pytest (manual-provenance tripwire).
7. Spot checks: §25.965@25-0 (°, ½), §25.1457@25-2, §25.1093@25-140,
   §29.53@29-40, §25.773@25-144, §23.615@23-45 (deleted), §25.31@25-0
   present, C25 and H25 appendices.

Open data items (new):
- DRS date outliers to check by hand (stay fatal → TEXT MISSING, or
  `kept_existing` for Part 23 rows already in data/ with clean text): 23-0
  (02/02/1965 vs 1965-02-01), 23-2 (07/08/1965 vs 1965-08-01), 23-50
  (03/12/1996 vs 1996-03-11), 25-46 (12/02/1978 vs 1978-12-01), 25-60
  (06/18/1986 vs 1986-06-16), 29-3 (09/17/1968 vs 1968-02-25). Each is one
  document; add a `drs_date` override once confirmed.
- 29-39/29-40 swap — resolved by override, evidence FR 96-11494 (29-40,
  61 FR 21894-21901, eff. 1996-06-10) and 96-11493 (29-39, 61 FR
  21904-21908, eff. 1996-08-08). Both DRS and the eCFR CITAs carry the swap.
- 36-55 split effectivity: FR 2025-13972 gives every Part 36 instruction
  "Effective July 24, 2026"; the rule's general date is 2025-10-22. Override
  applies 2026-07-24 to Part 36 only.
- §G25.1@25-141 is a figure only: expected TEXT MISSING.
- Part 36 Appendix C@36-24: no DRS text.
- FR docket for 29-58 (2022-23327) also names 25-146; DRS dates 25-146 in
  2018. Check before Part 25 promotion.
- Orphan extracted files (not plan rows) stay on disk; emit lists them as
  `orphan` in incomplete_faa_{p}.tsv.
- Part 36 `cita_has_unresolved_entry` rows (11) still need a human.
- Overrides not yet exercised against live data: confirm on the re-run that
  every row of overrides.tsv is used (`override_applied` counts) and no
  `override_stale` appears.
- Updates: item #2 (23-43 date) is fixed in code, pending the re-run; #6 to be
  re-checked after the re-run.

## EASA CS close-out (2026-11-01) — state at commit

Done (tools commit "EASA: fix CS-25/27/29 extraction gaps, emit overrides"):
extractor fixes for CS-25 Amdt 1/15/18/27/28, CS-27 Amdt 1, CS-29 Amdt 11/12
(see tools/README.md §extract.py); `regulations/easa/overrides.tsv` (8
reviewed `suppress` rows: CS 25.333/25.335 at CS25-8..10, CS 27.1316/1317 at
CS27-5, which the CS27-5 PDF omits); emit keeps the title in force for
capitalised/case-only titles. CS-29 Amdt 10 checked: ED Decision 2021/016/R
(15 Dec 2021, in force the day after publication = 2021-12-18; listing
"17/12/2011" is a typo); the file is the full "Corrigendum to Amendment 10",
Annex to ED Decision 2022/010/R (2 May 2022). Emit with
`--accept-needs-human`. Every paragraph now appears/disappears between
amendments only where the manifest says so, or as a real creation the
manifest labels differently (CS25-1 L25, CS25-10 1535, CS27-3 573, CS27-4 D27,
CS29-4 E29). Staged into `tools/out/staged_easa/documents/` (CS-23 448
provisions/845 versions, CS-25 403/998, CS-27 265/361, CS-29 320/456); a
scratch `build.py` of data/ + staged EASA passes (schema v2, 0 errors).
**Not promoted into data/ yet.**

Still to do before promotion:
1. Review the remaining `unexplained_change` rows in
   `tools/out/reports/emit_easa_cs{n}_report.tsv` (about 5 CS-23, ~160 CS-25,
   ~40 CS-27, ~80 CS-29). Most at CS25-27, CS27-10 and CS29-11 are genuine
   editorial changes from re-typesets (AMC cross-references removed, "(l)" →
   "(1)") — keep (PDF is the authority). Suppress the extraction artefacts:
   table-cell order (CS 25.815, 25.1391, L25, R25, E29), formula pieces
   (25.341, 25.405, 29.562, 29.725), footnotes leaking in (25.1199/1203,
   29.853, 29.865), CS25-6 25.963 ρ→r font, CS27-7/8 broken font (old item 11),
   D25 lead-in sentence at CS25-19/27. Add each to overrides.tsv with evidence.
2. Review `manifest_change_not_in_text` (CS-25: 94) — many are amendments to
   AMC only or sub-word changes; spot-check a sample.
3. Spot checks against PDFs (plan step 5), then
   `promote --staged tools/out/staged_easa/documents --dry-run`, promote, build,
   smoke queries (CS 25.1309 versions, CS 23.2510 from CS23-5, whole-document
   CS23-6 ref excludes deleted paragraphs).

Improvements for later:
- Appendix titles: no canonical source; capitalised headings (CS-25 Amdt 27+)
  keep the earlier mixed-case title. Some old-layout titles are table headers
  (L25 "Strength Value").
- Column reading order (`order_page`) still fails where a figure splits a
  two-column page (CS25-8..10 p. 1-C-4); fixed by override, not code.
- `_header_lines` (running-header second lines found by repetition) and the
  `listed` heuristic are pattern-based; a new layout may need new rules.
- discover should record the corrigendum Decision (2022/010/R) in the
  catalogue notes rather than only in this file.
- Table representation (old item 8) and formula flattening remain.
- `amdt_markers` are not used by emit; could cross-check versions.
