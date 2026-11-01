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

**Status (2026-11-01, `reviews/PLAN_TCDS_PARSER.md`, tools/ commit ff2b6fc
plus the follow-up below):** 16–24 resolved. 25 resolved except the schema
point: restricted-category TCDS without a basis are reported and not staged
(no schema change, by decision). The 3A12 swap is done:
`data/aircraft/cessna-aircraft-company/172.json` (Rev 42) is replaced by
`data/aircraft/textron-aviation-inc/172.json` (Rev 89, `caa/car-3` to
`CAR3-12`). Each fix has a stage test in
`tools/tests/aircraft/test_faa_tcds_stages.py` and goldens for 8 TCDS in
`tools/tests/fixtures/tcds/`.

## TCDS parser: corpus run and open items (2026-11-01)

Coverage over the 939 current Aircraft TCDS
(`uv run python -m tools.aircraft.faa_tcds_coverage`, report in
`tools/out/reports/tcds_coverage.tsv`):

| | Old parser | Three-stage (ff2b6fc) | + heading fixes |
|---|---|---|---|
| TCDS with ≥ 1 model staged | 40 | 601 | 601 |
| Models staged | 65 | 1,429 | 1,451 |
| Resolved regulation lines | 21 | 818 | 759 |
| TCDS with cover models not parsed | | 442 | 397 |
| Placeholder files written | 148 | 0 | 0 |

The drop in resolved lines is a correction, not a loss. Before the heading
fixes, 2A13 sub-labels such as `PA-28-181:` didn't match the models, which
were named "A.- Model PA-28-181". So PA-28-181's basis (60 resolved lines) was
attached to every 2A13 model. It now goes to PA-28-181 only, which is
skipped as a duplicate designation (item 29).

Of 7,037 regulation lines on staged models, 759 resolve. The rest are left
verbatim with `references: []`: `doc_not_in_dataset` 3,045 (cited document
or provision not in `data/`, e.g. Part 36, item 28), `no_pattern` 2,919,
`partial` 200, `unknown_revision` 114. 22 TCDS (the 20 trial ones plus A47CE
and A00003SE; 95 models) are staged in `tools/out/staged/aircraft/` for
review. Only the 3A12 172 is promoted.

26. **Cirrus-style "additions" layered on a base line.** A00009CH (SR20/22/22T)
    and similar TCDS give a base line ("14 CFR Part 23 … through 23-53 …")
    followed by many scoped additions ("For aircraft equipped with Garmin
    G1000 …: 14 CFR 23.1308 thru Amendment 23-57"). These are emitted today as
    separate entries whose `applicability` is the verbatim equipment/serial
    scope. A consumer cannot tell which aircraft get which level without
    reading the scope text. Options: (a) status quo: separate scoped entries;
    (b) structured serial applicability, see
    `reviews/2026-10-31-db-schema/04-open-questions.md` Q-04 (it doesn't help
    the equipment scopes); (c) an entry-level "supersedes entry N for scope S"
    link. Needs a decision before Cirrus is promoted.
27. **Aircraft files have no `provenance` field.** `promote --aircraft` has no
    manual-edit guard: a re-parse plus promote would overwrite a hand-finished
    aircraft file, protected only by the diff and the y/N prompt. This is the
    main blocker to running the parser wider than review-by-review. Needs a
    schema change (aircraft-level or entry-level `provenance`), the promote
    guard and a manifest entry, like the document files.
28. **§23.303, §23.871 and §23.1524 are missing from `data/documents/faa/23/`.**
    The 3A12 172R/172S base line ("FAR Part 23 … 23-1 through 23-6, except as
    follows: … 23.871, … 23.1524 as amended by Amendment 23-10 …") and the
    "14 CFR 23.303, 23.307, …" line stay unresolved (`doc_not_in_dataset`).
    All three are in the Part 23 manifest/worklist and extracted
    (`tools/out/extracted/faa/23_303_23-0.json`, `23_871_23-{0,7}.json`,
    `23_1524_23-10.json`) but not emitted. They should land with the Part 23
    re-emit and promote in the FAA extraction fix (Step 7 below). Re-parse 3A12
    after that.
29. **Designation appears twice on one TCDS:** A19SO `PA-44-180` and A37CE
    `208B` (two headings each, different bases). Neither is staged (`duplicate
    designation; merge by hand`). 49 TCDS in the corpus have this. Some are
    unmarked continuation pages that repeat a multi-model heading (A3EU `VII.
    Model DH.125 Series 3A/RA, Model HS.125 …` ×3, so every model counts as a
    duplicate; such a wrapped heading also yields a truncated `HS.125 Series`).
    Needs a
    merge rule (one file with two `tcb` entries? one entry list with each
    heading's scope as `applicability`?) or a hand merge per TCDS.
30. **EASA CS-23 citations on FAA TCDS** (A57CE DA 62: "CS 23.573 … (CS 23,
    amendment 2)", 17 lines; plus "Significant Regulatory Differences … CS-23,
    Original Issue"). They are left unresolved, and are never read as FAA
    Part 23. Once the EASA CS-23 documents are in `data/`, the interpreter
    could resolve them to `EASA`/`cs-23` (mind the "equivalent to 14 CFR
    Part 23 … through 23-55" line, which stays FAA, as with the DA 40).
31. **Cover models not matched to headings: 397 TCDS, 1,151 designations**
    (was 442 / 1,330). The coverage report compares the catalogue `models`
    column with what was emitted. Not triaged beyond a sample. Fixed: brand
    prefixes in designations (1A13 `Colonial Model C-1` → `C-1`), several
    `Model` clauses on one heading (1A13 III `Lake Model LA-4 …; Lake Model
    LA-4A …`), designation lists (1A16 `G-164B-15T and G-164B-34T`, H8SW
    `HSS-1/UH-34D, …, CH-34C`), `MODEL:` headings, a category on a wrapped
    heading line reaching all models, and wrapped sub-labels (2A13). The
    reconciliation now accepts catalogue names with a brand the heading
    lacks (`Lake LA-4` for `LA-4`). What remains looks like real
    segmentation misses, e.g. 1A2/1A4 Piper PA-18/PA-20 variants, 1G1/1G10
    `SGS 1-23F …`, 1H11 `S-58E …`; not yet triaged. Other top skip
    reasons (by TCDS count): no category on heading 227, no certification
    basis 153 (+45 with none on the whole TCDS), no model headings 65, zero
    entries 11.
32. **3A12 "Equivalent Safety Items" header-row serials.** The header row reads
    `Equivalent Safety Items  17261445, 17261578, 17265685`. The parser keeps
    that list as the `applicability` of both items under it (Airspeed
    Indicator CAR 3.757, Operating Limitations CAR 3.778(a)), after
    "Models 172 thru 172P". From the TCDS layout it isn't clear whether the
    list scopes both items or only the airspeed one (whose own text repeats
    it: "S/N 17261445, 17261578, 17265685 thru 17276259"). Check against the
    PDF when the 172 is reviewed.
33. **`promote --dry-run` prints `WROTE`** for a conflict it would accept
    (`tools/regulations/promote.py:239`), although nothing is written.
    Cosmetic, but it reads like a real write.

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

## EASA CS close-out (2026-11-01) — promoted

CS-23/25/27/29 are promoted into `data/documents/easa/` (1,440 files): CS-23
448 provisions / 841 versions, CS-25 403 / 844, CS-27 265 / 344, CS-29 320 /
425. `build.py` passes (schema v2). Smoke checks: CS 25.1309 has versions
at Amdts 0, 5, 6, 19, 20, 24 (exactly the manifest's amendments); CS 23.2510
starts at CS23-5 where CS 23.1309 is deleted; at CS23-6 the 68 provisions in
force are all new-style 2xxx paragraphs. 60 random version snippets (15 per
CS) were found in their source PDF.

What changed in this pass (tools commit "EASA: close-out review …"):
- **Extraction fixes that recovered lost CS text:** "(See AMC …)" notes
  whose second line starts "AMC 25.812(b)(2) and …" were read as AMC
  headings (re.I matched the lower-case "and"), cutting the rest of
  CS 25.811, 25.1353(d)/(e), 25.145(b)(3), 25.571, 25.103(d), 29.1305(a)(26)
  and Appendix N/H text at many amendments; "AMC to CS 25.1319" and "AMC
  25.113(a)(2), (b)(2) and (c)(2) …" were not recognised (AMC text read into
  the CS); from CS-25 Amdt 27, appendix sections after their AMC (H25.5,
  N25.2, S25.10.., SAL 25.6) were dropped; general AMC ("AMC 25-1") after
  Appendix S was read into S25; an AMC 25.1302 table row replaced the real
  CS 25.1302 heading at Amdt 27 (17,000 words of AMC in the CS text);
  wrapped appendix running headers at CS25-28 were read into the text.
- **Manifest fixes:** the CS-25 Amdt 27/28 preamble page header ("CS-25
  Amendment 27") was taken as a history section, crediting ~120 older
  changes to Amdt 27; "Related Certification Specifications" lists and
  tables inside AMCs in CS-25 Amdt 4/8, CS-27 Amdt 8 and CS-29 Amdt 9 change
  information were read as amended paragraphs (~60 rows); a wrapped cell
  "create additional hazards" was read as an instruction. CS-25
  `manifest_change_not_in_text` fell from 94 to 20.
- **Emit comparison:** Greek letters equal to their Symbol-font Latin twins
  (ρ/r, δ/d, μ/m, Ω/W); title + text compared too (wrapped title lines).
- **overrides.tsv:** 149 reviewed `suppress` rows (was 8), each with the
  evidence. Kinds: Symbol-font/Latin-1 formula glyphs; formula or table cells
  in another order; the CS 27/29.1401 effective-intensity formula read into
  neighbouring paragraphs; footnotes, page headers, `[Amdt No]` markers and
  figure captions read into the text; two-column interleaving; broken fonts
  (CS27-7/8 C27, CS25-16 785, CS25-8 809 "Het Verloren Symbool"); drop
  capitals. All apply; none stale, none against the manifest. This closes
  items 4, 11 and 12 of "EASA CS ingestion".

Reviewed and kept (the PDF is the authority; still listed as
`unexplained_change` in `emit_easa_cs{n}_report.tsv`, 178 rows):
- Re-typesets without preamble entries: CS-25 Amdt 27 (65: "(See AMC …)"
  removed, "lbf" → "pounds", "25.491" → "25.415", "thrust" → "trust" typo),
  CS-27 Amdt 10 (24) and CS-29 Amdt 11/12 (43: Amdt 12 also corrects Amdt
  11 typos such as "must be must be"). Old item 13 decided: keep.
- CS-25 Amdt 1 (10): real FAR-harmonisation rewrites (25.933, 25.1141, APU
  Part A → Subpart J) and group headings that CS25-0 had read into the text.
- Real one-word changes: CS 23.572 "pargarph" fix (CS23-1), 25.1182
  "21.1187" → "25.1187" (CS25-14), 25.253 25.147(e) → (f) (CS25-11),
  27.965 "cpm"/"rpm" (CS27-0 and CS27-10 print cpm, Amdts 1–9 rpm), 29.811
  "0.76 mm" → "0.76 m" (CS29-10), 29.1 "This Airworthiness Code is" ↔
  "These certification specifications are" flipping at Amdts 4/5/6.
- CS 25.807(k) ("Each passenger entry door … must qualify as a Type A, Type
  I, or Type II passenger emergency exit") appears only in the Amdt 27 PDF;
  not in Amdt 26 or 28, and no change information mentions it. Two versions
  result (added at 27, removed at 28). Ask EASA or check the ED Decisions.
- CS 25.20(b)(1) at Amdt 28 prints "andd" (PDF typo, kept).
- CS 25.397(d) side-stick ROLL rows: Amdt 27 prints them after a page break
  (read into 25.399, suppressed); 25.397 at Amdt 27 therefore lacks them and
  Amdt 28 restores them as a version.
- Tables split between CS 25.509 and 25.511 (tow-point table) in CS25-0..21
  give versions at CS25-1 and CS25-22; CS 25.331/333 at CS25-21 (figure text
  moved back to 25.331); Appendix C Part II at CS25-3, F25 (two-column
  reorders at Amdts 4, 11, 12), H25.6 at CS25-25, Q25 at CS25-19.

Still open:
1. **CS 25.773 at Amdt 16 is `TEXT MISSING`** (also unchanged at 17): the
   heading sits on a two-column page and the body is not extracted, but the
   text is in the PDF (CS25-17.pdf, `pdftotext -layout` line 7177). The
   manifest says amended at 16, so it can't be suppressed. Transcribe by
   hand (`provenance.source = "manual"`) or fix the column order.
2. CS-25 `manifest_change_not_in_text` (20) and CS-27/29 (2 each): mostly
   CS-25 Amdt 28 (AMC-only or sub-word changes). Not checked one by one.
3. Subpart J (APU) of CS-25 is not split into provisions: its 25J9xx text
   is part of CS 25.1591 (to Amdt 4) and 25.1731 (later). Needs a heading
   rule for "CS 25J901" and a numbering decision.
4. Letter-spaced text in old CS-29 PDFs ("m ight", "t he") is kept as is in
   the stored text (comparisons ignore spacing). Display or search will
   suffer; a de-spacing pass would need care.
5. CS 23.851 at CS23-3 (old item 5) and the CS-23 Amdt 2 ED Decision number
   (old item 2) remain.
6. Group headings read into the end of the preceding paragraph in CS25-0
   (e.g. "Emergency Landing Conditions" in 25.519) — cosmetic.

Improvements for later:
- Appendix titles: no canonical source; capitalised headings (CS-25 Amdt 27+)
  keep the earlier mixed-case title. Some old-layout titles are table headers
  (L25 "Strength Value"). Paragraph titles that wrap keep only the first
  line; the rest starts the text (consistently across amendments).
- Column reading order (`order_page`) still fails where a figure splits a
  two-column page (CS25-8..10 p. 1-C-4); fixed by override, not code.
- `_header_lines`, the `listed` heuristic and the AMC heading pattern are
  pattern-based; a new layout may need new rules. Watch for paragraphs whose
  length jumps between amendments without a manifest entry.
- discover should record the corrigendum Decision (2022/010/R) in the
  catalogue notes rather than only in this file.
- Table representation (old item 8) and formula flattening remain.
- `amdt_markers` are not used by emit; could cross-check versions.
