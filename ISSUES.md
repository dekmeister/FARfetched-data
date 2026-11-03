# ISSUES.md

Open data, pipeline and build issues for FARfetched-data and its `tools/`
sub-repo, plus the roadmap. It is one file on purpose (decided 2026-11-03).
Nothing here is a known build failure unless the item says so.

**Adding an item:**

- Put it under its area with the next free ID. IDs are never reused or
  renumbered.
- Say what is wrong, the evidence (file, report, PDF page, FR cite), and what
  would close it.
- Date it if it's time-sensitive.
- When an item is closed, move it to [Closed](#closed) as one line saying
  how and where it was resolved.

**Areas:** [FAA regs](#faa-regs-faa-) · [CAR](#car-car-) ·
[EASA CS](#easa-cs-easa-) · [FAA TCDS / aircraft](#faa-tcds--aircraft-tcds-) ·
[EASA TCDS](#easa-tcds-etcds-) · [Text layout](#text-layout-text-) ·
[Build / contract](#build--contract-build-) ·
[Tooling and process](#tooling-and-process-proc-) ·
[Roadmap](#roadmap-roadmap-) · [Closed](#closed)

**History.** Until 2026-11-03 this file was a set of dated logs. The
narratives moved, word for word, to `tools/s00_docs/reviews/`:

- [2026-11-01-tcds-corpus-run.md](tools/s00_docs/reviews/2026-11-01-tcds-corpus-run.md)
- [2026-11-01-easa-cs-closeout.md](tools/s00_docs/reviews/2026-11-01-easa-cs-closeout.md)
- [2026-11-01-paragraph-structure-migration.md](tools/s00_docs/reviews/2026-11-01-paragraph-structure-migration.md)

The authority-only, FAA extraction-fix and tools-reorg logs are in git
history and in the handovers in that folder. "was:" notes give each item's
old number:

- Data #n / Risks #n: the authority-only sections
- TCDS #n
- EASA-ingest #n / EASA-open #n: ingestion and close-out "Still open"
- Para #n
- FAA-fix: extraction-fix open data items
- TODO.md

## Open

### FAA regs (FAA-)

**Pending work:** the FAA Part 23 re-fetch, emit and promote review is in
progress. See
[tools/s00_docs/reviews/2026-11-03-faa23-refetch-handover.md](tools/s00_docs/reviews/2026-11-03-faa23-refetch-handover.md).
Several items below are expected to close with that promotion.

- **FAA-1. 23-56 and 23-60 are undeclared and unexplained.** (was: Data #1)
  - DRS has no document for either. A Federal Register full-text search found
    no rule naming them, and eCFR and the DRS CSV don't list them.
  - This is absence of evidence, not proof they were never issued.
  - Not checked: a general web search, FAA's amendment-history tables, and FR
    rules from 2002-03..2007-08 (23-56) and 2008-12..2011-08 (23-60) read by
    hand.
  - A TCDS citing either as a range endpoint is rejected by the build
    ("unknown revision"). That is intended until a source turns up.
- **FAA-2. Part 23 revision dates and re-fetch regressions.** (was: Data #2,
  FAA-fix)
  - The re-fetch diff will change these dates:
    - 23-51: 1996-03-12 → 1996-03-11
    - 23-58: 2009-07-09 → 2008-04-07 (**user decision needed**: DRS also
      files a 2009-07-09 document)
    - 23-63 → 2017-03-21 (override)
  - The diff should also drop the four "… Notice No." action tails
    (1457/23-58, 853/23-25, 65/23-21, 733/23-17).
  - On that run, confirm that every `tools/overrides/faa_regs.tsv` row is
    `override_applied` and none is `override_stale`.
  - Details are in the refetch handover.
- **FAA-3. DRS date outliers** (FAA-fix), each one document:
  - 23-0 (DRS 02/02/1965 vs 1965-02-01)
  - 23-2 (07/08/1965 vs 1965-08-01)
  - 23-50 (03/12/1996 vs 1996-03-11)
  - 25-46 (12/02/1978 vs 1978-12-01)
  - 25-60 (06/18/1986 vs 1986-06-16)
  - 29-3 (09/17/1968 vs 1968-02-25)

  No `drs_date` override exists for these yet. Confirm each, then add an
  override with evidence. Without one, the row stays fatal and becomes TEXT
  MISSING at emit.
- **FAA-4. 25-118 is a DRS `Sec. 0.0` "inadvertently skipped" number.** It is
  deliberately not declared. A TCDS citing "through 25-118" needs a human
  decision (probably 25-117). (was: Data #3)
- **FAA-5. 27-41 and 29-48 have no DRS document** and are undeclared. Same
  question as FAA-1. (was: Data #4)
- **FAA-6. Part 36 numbering.** (was: Data #5)
  - The manifest assumes contiguous numbering, so the Part 36 gap list is
    mostly noise: 36-32 is from 2022 and 36-54 from 2002. 36-33..36-53 have
    no DRS document and probably never existed (unconfirmed).
  - 36-1, 36-2, 36-3, 36-5, 36-11 and 36-32 have real sections in DRS that
    the eCFR-derived manifest never listed. They need the section pipeline.
  - 11 `cita_has_unresolved_entry` rows need a human (FAA-fix).
- **FAA-7. Authority-only declarations for Parts 25/27/29/36 aren't in
  data/:** 25-85, 27-31, 27-39, 29-37, 29-46, 36-21, 36-23. They will flow in
  with each part's first promotion; check that they're there. (was: Data #6)
- **FAA-8. §23.303, §23.871 and §23.1524 are missing from
  `data/documents/faa/23/`** (confirmed 2026-11-03). (was: TCDS #28)
  - They leave 3A12 172R/172S lines unresolved (`doc_not_in_dataset`).
  - They're in the Part 23 manifest and expected with the re-fetch promotion.
  - Re-parse 3A12 afterwards.
- **FAA-9. 29-58's FR docket (2022-23327) also names 25-146,** while DRS
  dates 25-146 in 2018. Check before Part 25 promotion. (FAA-fix)
- **FAA-10. Expected `TEXT MISSING`, not recoverable from DRS:** §G25.1@25-141
  (figure only) and Part 36 Appendix C@36-24 (no DRS text). Recheck if
  another source turns up. (FAA-fix)
- **FAA-11. Part 23 must be manifested with `--as-of 2017-08-29`.** The
  default is the newest eCFR date, which is the post-rewrite Part 23. The
  docs say so, but nothing enforces it (`manifest.py` defaults to
  `latest_date()`). (was: Risks #13)
- **FAA-12. Amendment-level FR cites.** Where a section has no eCFR CITA
  cite, the cite comes from the amendment manifest
  (`fr_cite_source=manifest_amendment`). That is the rule's first page, not
  the section's own page. Refine per section if needed. (was: TODO.md)

### CAR (CAR-)

- **CAR-1. OCR-damaged and out-of-sequence labels in CAR 3 texts** leave the
  paragraph structure flat. Check them against the scans; fix with
  `replace_text` overrides (was: Para #6, CAR part).
  - CAB CAR 3 reissue (24): `(bo)`/`(ob)` for `(b)`, `(ce)`/`(ec)` for
    `(c)`, `(ad)`, `(0)`. Sections: 109, 115, 123@R7, 124 (R0, R7), 171,
    185, 197@R2, 222, 225, 233, 550@R2, 625, 667, 700, 745, 75, 767, 771,
    778, 780 (R0, R7), 82, 84.
  - Sequence breaks (16): e.g. 3.655 at CAR3-0/2/10 and CAR3R-0, 3.6,
    3.437, 3.667.
- **CAR-2. CAR "NOTE: The following interpretation …" paragraphs are
  editorial, not regulation text.** They now read as part of the paragraph
  before them (see TEXT-8). (was: Para #8)

### EASA CS (EASA-)

Background: [2026-11-01-easa-cs-closeout.md](tools/s00_docs/reviews/2026-11-01-easa-cs-closeout.md).
Reports are `tools/out/reports/emit_easa_cs{n}_report.tsv`.

- **EASA-1. CS-29 Amdt 10 exists only as a corrigendum** (ED Decision
  2021/016/R). It is promoted with the corrigendum text and the effective
  date 2021-12-18 borrowed from CS-27 Amdt 9. Check it against the original
  Amdt 10, if EASA still has it, and confirm the date. (was: EASA-ingest #1)
- **EASA-2. CS-23 Amdt 2 ED Decision number.** The website says 2010/007/R
  and the CS-23 Amdt 6 preamble says 2010/008/R. One of them is wrong.
  (was: EASA-ingest #2, EASA-open #5)
- **EASA-3. The CS-23 Amdt 1 PDF prints page 1–E–25 twice.** Extract drops
  the repeat. Check CS 23.1199–23.1203 at CS23-1 against the PDF.
  (was: EASA-ingest #3; not re-checked since)
- **EASA-4. CS 23.851 at CS23-3:** the preamble says it was amended, but the
  extracted text is identical. Probably only the AMC reference changed; no
  version is emitted. (was: EASA-ingest #5, EASA-open #5)
- **EASA-5. Appendix I to CS-23 has no text layer** (figures only) in every
  issue. Its versions are TEXT MISSING. (was: EASA-ingest #6)
- **EASA-6. Titles.** Appendix titles that wrap keep half a title unless the
  first line ends in a dangling word. There is no canonical title source:
  capitalised headings (CS-25 Amdt 27+) keep the earlier mixed-case title,
  some titles are table headers (L25 "Strength Value"), and wrapped
  paragraph titles keep only their first line. Spot-check `canonical_title`.
  (was: EASA-ingest #7, close-out improvements)
- **EASA-7. CS-23 Amdt 5 and 6 texts come from republished files** (AMC/GM
  republications). They have not been verified against the original
  2017/2023 files. (was: EASA-ingest #9)
- **EASA-8. CS 25.773 at Amdt 16 is `TEXT MISSING`** (confirmed 2026-11-03).
  - The heading sits on a two-column page and the body isn't extracted, but
    the text is in the PDF (CS25-17.pdf, `pdftotext -layout` line 7177).
  - Fix the column order in extract. Hand transcription is no longer
    possible (no `manual` provenance since v4). (was: EASA-open #1)
- **EASA-9. `manifest_change_not_in_text`:** CS-25 has 20 (mostly Amdt 28,
  AMC-only or sub-word changes) and CS-27/29 have 2 each. They haven't been
  checked one by one. (was: EASA-open #2)
- **EASA-10. CS-25 Subpart J (APU) isn't split into provisions.** Its 25J9xx
  text is part of CS 25.1591 (to Amdt 4) and 25.1731 (later). Needs a
  heading rule for "CS 25J901" and a numbering decision. (was: EASA-open #3)
- **EASA-11. Letter-spaced text in old CS-29 PDFs** ("m ight", "t he") is
  stored as is. Display and search suffer; a de-spacing pass would need
  care. (was: EASA-open #4)
- **EASA-12. In CS25-0, group headings are read into the end of the
  preceding paragraph** (e.g. "Emergency Landing Conditions" in 25.519).
  Cosmetic. (was: EASA-open #6)
- **EASA-13. CS 25.807(k) appears only in the Amdt 27 PDF.** It gives two
  versions (added at 27, removed at 28). Ask EASA or check the ED Decisions.
  (close-out "reviewed and kept")
- **EASA-14. Extraction heuristics are layout-specific.**
  - Column order still fails where a figure splits a two-column page
    (CS25-8..10 p. 1-C-4). That is fixed by an override, not in code.
  - `_header_lines`, the `listed` heuristic and the AMC heading pattern are
    pattern-based.
  - Watch for paragraphs whose length jumps without a manifest entry.
    (close-out improvements)
- **EASA-15. Small extract/emit improvements** (close-out improvements):
  - discover should record the corrigendum Decision (2022/010/R) in the
    catalogue notes
  - `amdt_markers` are unused by emit, but could cross-check versions

### FAA TCDS / aircraft (TCDS-)

Background: [2026-11-01-tcds-corpus-run.md](tools/s00_docs/reviews/2026-11-01-tcds-corpus-run.md)
and [TCDS_TRIAL_20.md](tools/s00_docs/reviews/TCDS_TRIAL_20.md).

- **TCDS-1. Cirrus-style "additions" layered on a base line** (A00009CH
  SR20/22/22T and others). (was: TCDS #26)
  - The scoped additions ("For aircraft equipped with Garmin G1000 …: 14 CFR
    23.1308 thru Amendment 23-57") are separate entries, with the
    equipment/serial scope as verbatim `applicability`.
  - Options: (a) keep that; (b) structured applicability (ROADMAP-5); (c) an
    entry-level "supersedes entry N for scope S" link.
  - Needs a decision before Cirrus is promoted.
- **TCDS-2. There is no correction path for aircraft files.** Documents get
  `replace_text` overrides; aircraft files have no provenance and no override
  mechanism. Under build-from-source, a hand-finished aircraft file is not
  allowed, so a wrong parse can only be fixed in the parser. Decide whether
  aircraft need an override TSV (probably no schema change) before running
  the parser wider. (was: TCDS #27, reframed by schema v4)
- **TCDS-3. A designation appears twice on one TCDS** (A19SO `PA-44-180`,
  A37CE `208B`; 49 TCDS in the corpus). Such models are not staged. Some are
  continuation pages repeating a multi-model heading (A3EU). Needs a merge
  rule (two `tcb` entries? one list with scoped `applicability`?) or a hand
  merge per TCDS. (was: TCDS #29)
- **TCDS-4. EASA CS-23 citations on FAA TCDS** (A57CE DA 62, 17 lines;
  "Significant Regulatory Differences … CS-23"). They are left unresolved.
  CS-23 is now in `data/`, so the interpreter could resolve them to
  `EASA`/`cs-23`. Keep the "equivalent to 14 CFR Part 23 … through 23-55"
  line as FAA. (was: TCDS #30)
- **TCDS-5. Cover models not matched to headings:** 397 TCDS and 1,151
  designations (as of 2026-11-01). (was: TCDS #31)
  - Examples: 1A2/1A4 PA-18/PA-20 variants, 1G1/1G10, 1H11.
  - Top skip reasons: no category on heading 227, no certification basis
    153 (+45), no model headings 65, zero entries 11.
- **TCDS-6. 3A12 "Equivalent Safety Items" header-row serials**
  (17261445, 17261578, 17265685) are applied to both items under the row. It
  isn't clear whether they scope both items or only the airspeed one. Check
  the PDF when the 172 is reviewed. (was: TCDS #32)
- **TCDS-7. Citation 525-family parse gaps.** (was: TODO.md)
  - Serial applicability isn't picked up when it is combined with an
    "except the following paragraphs applicable for Engines and FADECs"
    list, or with non-contiguous serial sets ("525-0600 thru 525-0684,
    525-0686 thru 525-0701").
  - Several ELOS in one line aren't split into separate entries. 525B
    display 21 still holds ACE-00-01A plus two others.
  - Sub-paragraphs (4a/4b, 6.a.1/6.a.2) should usually be separate entries.
  - The 525 "Additions" tables aren't parsed.
  - 525C special conditions are now split (fixed). Re-check the rest against
    the current `data/aircraft/textron-aviation-inc/525*.json`.
- **TCDS-8. `tcds.source_url` is not filled for FAA TCDS.** (was: TODO.md)
- **TCDS-9. Restricted-category TCDS without a certification-basis field**
  (Air Tractor A17SW; 7 of 201) are reported and not staged. The schema
  can't represent them, by decision. Revisit if they are wanted. (was: TCDS
  #25)

### EASA TCDS (ETCDS-)

State of the 2026-11-02 download: 623 TCDS, 650 files in `input/TCDS/EASA/`
([tools/s00_docs/EASA_TCDS.md](tools/s00_docs/EASA_TCDS.md)). Nothing is
parsed yet (ROADMAP-9).

- **ETCDS-1. Only the current issue exists, locally and upstream.** EASA
  replaces files in place, so `input/TCDS/EASA/` is irreplaceable and needs
  a backup. Re-run the downloader periodically to build up history.
- **ETCDS-2. 29 TCDS have no downloadable file.** They are mostly withdrawn
  or transferred (catalogue `role=none`; the 15 `no_issue_number` rows are a
  subset):
  - Scheibe gliders (A.100–A.107, A.577, A.578)
  - CEAPR DR series (A.510, A.551, A.552)
  - BAC 1-11 and Slingsby T67
  - SZD/IS gliders (A.441, A.446, A.452, A.454)
  - Gulfstream IM.A.002/IM.A.016
  - Hughes 369HS, EH 101-300, Viper, FLAIR-2, Schroeder, Lindstrand HS-110
  - A.022/A.629 ("Transferred to outside EU")

  If any are needed, they must come from another source.
- **ETCDS-3. 4 scanned PDFs were OCR'd** (A.200, IM.A.343, IM.E.077, P.016).
  - Header and ID text is unreliable (`[M.E.077`, `O1`, `Lid.`).
  - A parser must not trust OCR'd codes or numbers without checking them
    against the PDF.
  - IM.A.343 says "Page 1 of 7" but the PDF has 8 pages.
- **ETCDS-4. `EASA.BA.025_Issue3.pdf` is not a TCDS.** It is a revocation
  notice that the catalogue labels `main`. A parser must skip it.

### Text layout (TEXT-)

Paragraph structure (label-line text, schema v3). The words are intact by
assertion; these items affect which paragraph a sentence appears to belong
to. Counts are upper bounds from the migration report: see
[2026-11-01-paragraph-structure-migration.md](tools/s00_docs/reviews/2026-11-01-paragraph-structure-migration.md)
for the per-document tables and how to list each kind.

- **TEXT-1. Trailing unlabelled paragraphs are attached to the last item**
  (`possible-trailing`, up to 462 versions). (was: Para #1)
  - For example, §23.1309(b) "Each item … must also …" is stored as
    `(b)(2)`.
  - Main fix candidate: eCFR/DRS `<P>` breaks as hints. That was deferred
    because it causes version churn between sources; revisit it before the
    app relies on paragraph scope.
  - Otherwise, review the flagged rows.
- **TEXT-2. Real paragraphs may be kept inline** (`inline-skip`, 360). If the
  predecessor label was a stray cross-reference, a real paragraph is merged
  and its path goes missing. (was: Para #2)
- **TEXT-3. Splits after `, and` / `, or`** (`weak-split`, 116) can create
  false paragraphs mid-sentence. (was: Para #3)
- **TEXT-4. Ambiguous labels resolved by heuristic** (`tie`, 49). A wrong
  guess nests a paragraph under the wrong parent. (was: Para #4)
- **TEXT-5. Label gaps may hide misreads** (`gap`, 174 versions; build
  report `label_gaps`). Most are in CS-25. (was: Para #5)
- **TEXT-6. Flat-failed texts show as one block** (171). Paragraph refs to
  them are unverifiable. (was: Para #6; CAR part → CAR-1)
  - FAA (3): 23.45@23-21 (DRS dropped a `(`), 23.1147@23-43 (`(a)[(1)`),
    and H23@23-43 (per-section `(a)` runs).
  - EASA (128): lists without an introducer, flattened tables, and appendix
    sub-sections.
- **TEXT-7. FAA change brackets span paragraphs** (`bracket-spans`, 452).
  Rendered per paragraph, they look unbalanced. The app needs a rule.
  (was: Para #7)
- **TEXT-8. Source line breaks that marked real paragraphs were dropped**
  (`dropped-break`, 68). This is the same effect as TEXT-1, from the other
  direction. (was: Para #8)
- **TEXT-9. Rulemaking-action text inside FAA provision text**
  (`action-text`, 114 versions; e.g. 23.1353@23-17). The extractor now treats
  it as fatal, so it is expected to go with the Part 23 re-fetch (FAA-2).
  Re-count after promotion. (was: Para #9)
- **TEXT-10. Paragraph-ref verification checks existence only.** `(a)(1)(2)`
  descends first, and `(c3)` is read as `(c)(3)`, so a ref can "verify"
  under a reading the TCDS didn't intend. The app must use the same reading
  as `build.paragraph_ref_paths`, or show the qualifier verbatim.
  (was: Para #10)
- **TEXT-11. Tables and formulas are flattened into running text** (FAA and
  EASA; e.g. CS-23 Appendix C23). Consider a table representation later.
  (was: EASA-ingest #8, #12)

### Build / contract (BUILD-)

From the 2026-11-03 parent review
([reviews/2026-11-03-parent-reorg-handover.md](reviews/2026-11-03-parent-reorg-handover.md)).
The code items are proposals awaiting a decision.

- **BUILD-1. 4 real-data tests fail on the working tree:**
  `test_one_row_per_tcds_line`, `test_172_basis_resolves_to_car_3_through_3_12`,
  and two in `TestDA40Trace`.
  - `data/aircraft/` holds 70 untracked model files (14 manufacturers),
    although the TCDS notes say only the 3A12 172 was promoted.
  - Decide whether those files are meant to be in `data/`. Then either
    commit them and update the tests, or remove them (re-promote later).
- **BUILD-2. The real-data tests assert exact row lists** for the 172 and
  DA 40, so any parser re-run breaks them. Proposal: assert invariants
  instead (the 172's CAR 3 lines resolve through CAR3-12; both DA 40 scopes
  hold 23-51; no unresolved references).
- **BUILD-3. `cert_basis_report.json` is written non-atomically, after the DB
  swap** (`build.py`, end of `build()`). A failed write leaves a new DB next
  to a stale report. Proposal: write `.new` and replace, report first.
- **BUILD-4. `build.py --check` skips `_check_paths`.** Path/identity
  mismatches only appear in a full build. Proposal: run it in `--check`.
- **BUILD-5. `build_info.git_sha` doesn't reveal a dirty tree.** A build that
  includes uncommitted files records HEAD. Proposal: a `git_dirty` column.
  That is a contract change (v6): ask first.
- **BUILD-6. The tests build the real `data/` twice** (`real_db` in
  test_build, `real_conn` in test_similarity). Proposal: one session-scoped
  fixture in `tests/conftest.py`. Also replace its `sys.path` insert with
  pytest `pythonpath = ["."]` in pyproject.

### Tooling and process (PROC-)

- **PROC-1. The DRS amendment lookup cache never expires.**
  `input/cache/drs/far_amendment/` caches hits and misses for good. A gap
  that later gets a DRS document stays "none" until `--force`. A time limit
  would be cheap. (was: Risks #7)
- **PROC-2. The authority-only verdict trusts DRS listing fields, not the
  document text.** It uses `Section == "Sec. 0.0"` plus the title. A
  `Sec. 0.0` document with an unexpected title is `unrecognised`, not
  declared. (was: Risks #8)
- **PROC-3. The FR cite lookup for authority-only revisions is a window
  heuristic** (−30/+7 days around the DRS date, docket must name the
  designator). Zero or several matches give no cite and an
  `authority_only_no_fr_cite` row. 27-39 and 29-46 have no FR
  `effective_on`, and DRS misprints their docket (`FAA-19998-4390`).
  (was: Risks #9)
- **PROC-4. FAA emit assumes designator prefix = part**
  (`s02_emit/faa/regs/emit.py`, `startswith(f"{part}-")`). That is fine for
  FAA, but wrong if reused for CAR or EASA. (was: Risks #10)
- **PROC-5. Nothing stops a test from calling the real DRS.** Tests that call
  `manifest.main` must pass `--skip-drs` or patch
  `far_amendment_documents`. A guard in `tools/s99_tests/conftest.py` that
  fails on a real request would enforce it. (was: Risks #12)
- **PROC-6. The `network calls: N` counter undercounts DRS lookups** (one per
  lookup, however many pages it took). Not re-checked since 2026-10-31.
  (was: Risks #14)
- **PROC-7. `promote --dry-run` prints `WROTE`** for a conflict it would
  accept, although nothing is written (`s03_promote/promote.py`, conflict
  loop). Cosmetic, but misleading. (was: TCDS #33; confirmed 2026-11-03)
- **PROC-8. FAA extract is serial.** A `ThreadPoolExecutor` with about 10
  workers would give roughly 5–10× on 1,000+ row batches. The DRS JWT cookie
  needs a lock around refresh, or per-worker sessions. (was: TODO.md)
- **PROC-9. Stale inputs in the parent's `input/`:** `input/parsed/` (old TCDS
  output, 2026-10-31) and `input/regs.csv.work` (identical to `regs.csv`).
  Both are untracked; the user to decide whether to remove them. (tools
  handover 2026-11-02)

### Roadmap (ROADMAP-)

Data-repo roadmap, moved from the former `plan.md` (deleted 2026-11-03). The
app's roadmap is in the FARFETCHed repo's `plan.md`.

- **ROADMAP-1. Promote FAA Parts 25, 27, 29 and 36.** They are extracted but
  not in `data/`. Do it after the Part 23 re-fetch closes (FAA-2), with
  FAA-7 and FAA-9.
- **ROADMAP-2. Special conditions, ELOS and exemptions as documents.**
  `doc_kind` already allows them; they need ingestion and a provision model.
  FAA special conditions are on DRS. (was: plan.md Deferred, TODO.md)
- **ROADMAP-3. More regulation sources:** non-FAA issuers beyond EASA (TCCA,
  …), SFARs, and JAR (low priority). (was: plan.md, TODO.md)
- **ROADMAP-4. Related provisions.**
  - Hand-confirmed `provision_relations` and explicit cross-citations (e.g.
    MIL-HDBK-516 citing 14 CFR sections). The computed half is
    `provision_similarity` (v5).
  - "Related references" on TCDS entries, e.g. an exemption that applies to
    a regulation in the basis, without making it part of the basis.
  - Needs a schema decision. (was: plan.md, TODO.md)
- **ROADMAP-5. Structured serial applicability.** Today `applicability` is
  verbatim (schema review Q-04). It also bears on TCDS-1.
- **ROADMAP-6. Deferred schema items from the 2026-10-31 review:**
  `document_revisions.cancelled_on`; `provisions.parent_id` (until a
  hierarchical document arrives); per-TCDS files (F-24/Q-06, "decide before a
  second model on an existing TCDS", which has now happened: 3A12 models
  share a TCDS, kept consistent by the build's metadata check); `drs_guid`
  as a field (only in `_diag` today).
- **ROADMAP-7. Find the official DRS API Technical Documentation PDF.** The
  alfId is in `tools/s00_docs/FAA_DRS.md` §3.5. If found, it supersedes the
  reverse-engineered notes. (was: plan.md)
- **ROADMAP-8. CI and releases.** There is no `.github/workflows/` yet.
  - On push to `main`: validate, build, test.
  - On tags: upload `cert_basis.sqlite` and `cert_basis_report.json` as
    release assets for the app's deploy to fetch.
  - Do a dry run of the release-fetch with a placeholder DB first (NFSN).
    (was: plan.md)
- **ROADMAP-9. EASA TCDS:** a parse/coverage stage, then EASA cert bases
  citing "CS-25 Amendment N". Also download the Noise TCDS (TCDSN), which is
  only recorded in the catalogue's `noise_*` columns today.

## Closed

- **Data #2 (23-43 date):** `data/` holds 1993-05-10, which matches the CITA
  cite 58 FR 18970. The manifest logic was fixed in the FAA extraction fix.
  The other dates moved to FAA-2.
- **Risks #11 (shared staging):** each emitter regenerates only the staged
  directories it owns, and promote lists orphans (tools handover 2026-11-03).
- **Risks #15 (overwritten work files):** historical. The work files are
  regenerated from local copies now.
- **TCDS #16–#24:** fixed in tools `ff2b6fc` (`PLAN_TCDS_PARSER.md`), with a
  stage test each in `tools/s99_tests/emit/faa/tcds/test_stages.py`.
- **TCDS #25:** fixed, except restricted-category TCDS (now TCDS-9). The 3A12
  swap to Rev 89 (`textron-aviation-inc/172.json`) is done.
- **EASA-ingest #4, #11, #12 (spurious versions from glyphs, broken fonts,
  drifting formulas):** 149 reviewed `suppress` rows in
  `tools/overrides/easa_cs.tsv` (EASA close-out).
- **EASA-ingest #10 (concurrent FAA tool edits):** historical.
- **EASA-ingest #13 (CS-27 Amdt 10 and other re-typesets):** decided. They
  are kept as versions because the PDF is the authority.
- **EASA "further work" list:** CS-23/25/27/29 promoted 2026-11-01. The
  remaining points are EASA-1..15 and ROADMAP-9.
- **FAA-fix: 29-39/29-40 swap and 36-55 split effectivity:** resolved by
  overrides in `tools/overrides/faa_regs.tsv`.
- **FAA-fix steps 1–6:** done in code. Step 7 (re-run and promote) was
  superseded by the tools reorg and the Part 23 re-fetch (FAA-2).
- **Para: v3 migration:** promoted. `data/` builds at v3 and later.
- **Para #11 (compound labels in hand layouts):** moot since v4. There are no
  hand layouts; overrides change words, and the segmenter lays out text.
- **Para (CAR emit read `out/extracted/car/`, data was in `out/car/`):**
  fixed in the tools reorg.
- **Tools reorg: CAR OCR sidecars and re-OCR risk:** the sidecars are the
  source copy, and `ocr.py` never re-OCRs a PDF that has one.
- **Tools reorg: raw DRS responses not kept:** they are kept now, in
  `input/cache/drs/far_doc/`, and extract decodes offline (`--redo`).
- **TODO.md: broken FR lookup (`lookup_by_fr_cite`):** removed with the
  legacy FAA path.
- **TODO.md: "… Notice No." tails:** the extractor strips them. Waiting on
  the Part 23 promotion (FAA-2).
- **EASA TCDS: 2 `warn_code_mismatch` rows** (IM.BA.026, IM.E.049): false
  alarms, right documents.
