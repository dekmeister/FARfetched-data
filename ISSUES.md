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

**Pending work:** FAA Parts 23, 25, 27 and 29 are re-fetched with the current
decoder and **promoted into `data/documents/faa/`** (23 on 2026-11-03; 27, 29
and 25 on 2026-11-03/04). Each staged tree is identical to `data/`, and a trial
build of `data/documents/` alone passes. **Not done:** the aircraft side
(BUILD-1: `data/aircraft/` is still the v5 shape, so the real `data/` does not
build and the real-data tests fail), and Part 36 (FAA-17). Close FAA-2, FAA-8,
FAA-13..16, TEXT-9 and BUILD-1 once aircraft is re-staged, promoted and
`build.py` and `uv run pytest` are green. Part 27 is committed (parent `69afe1b`, tools `559f141`);
Parts 23, 25 and 29 and the tools changes for 29/25 are not yet.

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
  - Re-fetch done 2026-11-03; staged tree rebuilt offline and reproducible.
    `_document.json` dates now differ from data/ as intended:
    - 23-51: 1996-03-12 → 1996-03-11
    - 23-58: 2009-07-09 → 2008-04-07 (maintainer decision 2026-11-03; DRS
      dates §23.1457/§23.1459 with the correction E9-16056, 74 FR 32799)
    - 23-63 → 2017-03-21 (override)
  - Five `drs_date` override rows were added with FR evidence (23-0, 23-48,
    23-50, 23-51, 23-58); all six affected DRS documents are
    `override_applied`, none `override_stale`.
  - The "… Notice No." action tails are gone from the diff.
  - **Not promoted yet.** FAA-13 and FAA-14 (data/ text the staged tree
    lacked) are fixed in the tools (2026-11-03); the promotion itself is the
    maintainer's call. Details are in the refetch handover.
- **FAA-3. DRS date outliers** (FAA-fix), each one document:
  - 23-2, Appendix E (DRS 07/08/1965; regs.csv also gives 8 Jul 1965 for
    this row, while §23.25 of the same amendment says 1965-08-01). **Open.**
    FR 1965-07-08, -06-29, -06-30 and -07-01 (govinfo scans, OCR) hold no
    Part 23 rule other than Amdt 23-1 (30 FR 8261, 06-29), and the manifest
    has no FR cite for 23-2 (Docket 2029, issued 1965-06-24). Not yet
    searched: 1965-06-25/26 and 07-02..07. Until an override with evidence
    exists, E23@23-2 is `TEXT MISSING` (a new file, so no regression).
    Leads (2026-11-03): a web search snippet of the FAA Part 23 certification-
    basis summary table (faa.gov, `.../small_airplanes/certification_basis/
    part23_summary/`; returned 403 to a direct fetch, so unverified) lists
    23-2 as effective 8/1/1965, "Limited Weight Credit for Airplanes Equipped
    with Standby Power" (which fits Appendix E), between 23-1 (7/29/1965)
    and 23-3 (11/11/1965). That matches §23.25's 1965-08-01 and the manifest.
    The archives.federalregister.gov `issue_slice/1965/7/3/8516-8519.pdf` is a
    Part 25 rule, not 23-2. archives.federalregister.gov slices have a text
    layer (no OCR), but need exact page ranges.
  - 25-46 (12/02/1978 vs 1978-12-01), 25-60 (06/18/1986 vs 1986-06-16) and
    29-3 (09/17/1968 vs 1968-02-25): **overrides added 2026-11-04**. Each is a
    single DRS document (§25.629, §25.855, §29.1505) disagreeing with the
    amendment's other DRS documents (33 of 34, 2 of 3, 57 of 58). Why that one
    differs is not established (pre-1994, no FR API); a later correction is
    possible and would already be in its text. Reviewed on majority evidence
    only, so confirm if it matters.

  Only 23-2 is still open. (23-0, 23-50 closed 2026-11-03 with 23-48, 23-51,
  23-58.)
- **FAA-13. Part 23 versions wrongly dropped as `suspect_designator`.**
  **Fixed 2026-11-03** (FAA-fix). All three are real; checked against the FR
  scans. New override kinds in `tools/overrides/faa_regs.tsv`, with tests and
  FAA_REGS.md:
  - `retroactive` for §23.1545@23-3 (30 FR 14240): FR 1965-11-13 says Part 23
    "is amended effective November 11, 1965" (good cause), so publication
    after the effective date is deliberate.
  - `fr_cite` for §23.853 and §23.929 @23-14: the eCFR CITA prints
    `23 FR 31822` and `33 FR 31822`; the rule is 38 FR 31822 (Docket 11011,
    FR 1973-11-19, effective 1973-12-20). data/ carried the bad cites; the
    staged files now have 38 FR 31822.
  - Still `suspect_designator` and not emitted (not in data/, unchanged):
    §335/§443/§561@23-24, §1549@23-12, §1557@23-21.
- **FAA-14. Appendix A to Part 23 for 23-0, 23-7, 23-16, 23-28 and 23-48.**
  **Fixed 2026-11-03** (FAA-fix). DRS holds all 16 Appendix A subsection
  documents ("Initial" is 23-0). `appendix_label` took its label from the
  23-64 whole-appendix document ("Appendix A to Part 23") first, so the
  listing check saw no subsections and refused to assemble. It now prefers a
  subsection's label. The five versions assemble; against data/ the text
  differs only by `&quot;` decoded, U+FFFD → `±`, and table cells spaced.
- **FAA-15. "Deleted."/"Removed and Reserved." DRS stubs.** **Fixed
  2026-11-03.** An empty body with DRS title "Deleted." or "Removed and
  Reserved." is now a `deleted: true` version, like "Removed." (§617, §643,
  §721 @23-7; E23@23-50). B23.1/B23.11@23-42 are still not emitted. Still
  TEXT MISSING and not in data/: §1567@23-13 (DRS has no 23-13 document) and
  §903@23-54 (`skip_human`).
- **FAA-16. `faa_rules_published()` missed FR doc 96-2082** (61 FR 5171, Amdt
  23-50, 1996-02-09): the daily FAA listing returned four documents and not
  that one, although the FR API serves it by docket. Check the agency filter
  when relying on this lookup (see PROC-3). Also §23.573@23-48 text reflects
  the 2008 technical amendment (73 FR 19746), not the 1996 original wording.
- **FAA-17. Parts 25, 27 and 29 re-fetched; Part 36 is not.** Done
  2026-11-03/04 by the Part 23 procedure (fresh DRS download, `extract --redo`,
  emit, review, promote). Part 36 still has no raw DRS copies and the old
  decoder's output. Do the same before promoting it. A
  `tools/out/staged/documents/faa/36/` tree exists (41 files, made 2026-11-03
  23:11 by something other than the Part 25/27/29 runs) and is **unreviewed**:
  a plain `promote` would copy it into `data/`. Promote with `--staged` on a
  scratch root, or regenerate Part 36 first.
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
  data/:** 25-85, 27-31, 27-39, 29-37, 29-46, 36-21, 36-23. **Done for Parts
  25, 27 and 29** (declared in each promoted `_document.json`); Part 36 will
  follow its promotion. (was: Data #6)
- **FAA-8. §23.303, §23.871 and §23.1524 are missing from
  `data/documents/faa/23/`** (confirmed 2026-11-03). (was: TCDS #28)
  - They leave 3A12 172R/172S lines unresolved (`doc_not_in_dataset`).
  - They're in the Part 23 manifest and expected with the re-fetch promotion.
  - Re-parse 3A12 afterwards.
- **FAA-9. 29-58's FR docket (2022-23327) also names 25-146,** while DRS
  dates 25-146 in 2018. **Resolved 2026-11-04.** 87 FR 75704 (effective
  2022-12-09) misprints 25-148 as "25-146"; the correction 2023-00139
  (88 FR 2813) names 25-148. DRS dates all six 25-148 documents with the
  correction date (as it does 29-58), so a `drs_date` override was added.
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

- **FAA-18. `TEXT MISSING` left in Parts 25, 27 and 29 (2026-11-04, 15
  versions).** DRS has no document and the date predates eCFR point-in-time
  data, so none is recoverable now:
  - Part 25: §733@25-48, §1181@25-11, Appendix M25@25-125.
  - Part 27: §87@27-0, 27-14, 27-21 (Height-velocity envelope).
  - Part 29: §967@29-26, §1019@29-10, §1093@29-3, §1303@29-12, §1521@29-3.
  - Part 29 Appendix B29@29-39: the subsection set differs from DRS's listing
    (B29.8 exists only at 29-31).
  - Part 27 §401, §403 and §413 @27-27 (`Removed`): two DRS documents each,
    `csv_duplicate`, so the worklist skips them. Both candidates are
    equivalent "Removed" stubs, so they would be `deleted` versions. An
    override kind that accepts a duplicate, or a worklist rule for
    all-stub duplicates, would clear them. Until then §27.401/403/413 look
    live after 27-27.
- **FAA-19. `suspect_designator` rows withheld from emit** (2026-11-04):
  - §351, §391, §395 @29-26 print "Amdt. 29-26, 55 FR 8002, Mar. 6, 1990".
    The real versions are 29-30 (from regs.csv) and are in `data/`. The 29-26
    rows are an eCFR typo. Same for §573@29-59 (typo for 29-54) and
    §1415@25-50 (the real version is 25-52).
  - §343 and §345 @25-72 are **not explained**: the CITA prints "Amdt. 25-72,
    55 FR 37607, Sept. 12, 1990", after 25-72's effective date (1990-08-20),
    but DRS holds both as 25-72 and the extract passes. The Sept. 12 cite may
    be a later correction. Needs the FR page (pre-1994, no FR API). Until
    then, §343 and §345 have no 25-72 version, so a 25-72 basis resolves to
    the previous amendment's text.
  - Part 23 has the same class (FAA-13).
- **FAA-20. Amendment-level FR cites for 25-148 and 25-151 are the
  corrections', not the rules'** (88 FR 2813 and 88 FR 44032). The rules are
  87 FR 75704 and 88 FR 39152. The section-level cites in the CITA are right.
  Related to FAA-12. Check the `source_url`/`publication_cite` this gives
  those versions.
- **FAA-21. The 25-151 override was backwards and was replaced
  (2026-11-04).** The old row said DRS 2023-07-17 → 2023-07-11. The rule
  2023-12454 (88 FR 39152) is effective 2023-07-17 and 2023-07-11 is the
  correction's date. Now: `effective_date` 2023-07-17 (regs.csv held one
  document of each date) plus `drs_date` 2023-07-11 → 2023-07-17 for §25.841.
  The FR docket line of the rule misprints "Amdt. No. 25-148".
- **FAA-22. Extractor and manifest changes made for Parts 27, 25 and 29**
  (documented in FAA_REGS.md and the `overrides.py` docstring, with tests):
  - Stub versions: a DRS title of "Re-designated", "Reserved." or "Revoked."
    with no body, and a "Removed" stub whose body is only the action preamble
    ("89-10; Issued on 04/19/89."), are `deleted: true` versions.
  - New override kind `fr_designator`: pins a bare FR cite to the amendment it
    corrects (61 FR 43952 is a correction of 29-39, but its docket line prints
    29-40, which made a phantom §29.1305@29-40).
  - `cita_has_unresolved_entry` joins `FETCH_ANYWAY`, so a csv row with a GUID
    and only that report item is fetched and checked by the extractor. This
    recovered §2@27-28, §2@29-32, §519@25-81, §1302@25-137, §1583@25-0.

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
  - 2026-11-03: assemble now reads two aircraft override files,
    `aircraft_links.tsv` (which TCBs are one model) and `aircraft_holds.tsv`
    (keep a model out of the staged tree). Neither corrects an entry; a
    wrong entry is still parser-only.
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
  - 2026-11-03: the shared interpreter reads CS forms now, but the A57CE
    DA 62 form `CS 23.573 Damage tolerance … (CS 23, amendment 2)` (title
    then a trailing amendment) comes out `partial` (12 lines). Teach
    `tcds_refs` the trailing `(CS 23, amendment N)` form.
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
- **TCDS-10. `aircraft.assemble` stages 1,446 of 1,470 fragments; 24 collide
  on path.** The same designation appears under two FAA TCDS, for example
  PA-36-285/-300/-375 (A9SO vs A10SO) and OH-13H (H5SW/H7SW). `assemble` fails
  loud and leaves those models unstaged (so they are missing from the
  `promote --aircraft` dry-run too). Each pair needs an
  `overrides/aircraft_links.tsv` row if it is one type design, else a
  holder/designation difference taken from the TCDS. Run
  `uv run python -m tools.s02_emit.aircraft.assemble` to list them.
  - 2026-11-03: this was a whole-corpus FAA run. The staged tree is now
    built from the 21 TCDS behind `data/aircraft/` only (TCDS-11), so these
    collisions reappear only when the FAA parser runs wider.
- **TCDS-11. Which FAA TCDS are staged is chosen by hand.** `assemble` stages
  every fragment under `tools/out/derived/tcb/`, so the aircraft set is
  whatever PDFs the FAA parser was last run on: today the 21 TCDS behind
  `data/aircraft/`, passed one by one. A full `input/TCDS/FAA/` run would
  stage ~1,450 files. This breaks the "one offline command rebuilds it"
  rule. Close by recording the selection as data (e.g. a TCDS list in
  `tools/overrides/` or the catalogue) that the parser or assemble reads.

### EASA TCDS (ETCDS-)

State of the 2026-11-02 download: 623 TCDS, 650 files in `input/TCDS/EASA/`
([tools/s00_docs/EASA_TCDS.md](tools/s00_docs/EASA_TCDS.md)). Parsed since
2026-11-03 (`s02_emit/easa/tcds/parse.py`; CS-23/25 aeroplanes only): 284
aircraft TCDS read, 263 models staged from 104 TCDS, 33 of them linked to
the FAA TCDS of the same design. Handover:
[2026-11-03-easa-tcds-handover.md](tools/s00_docs/reviews/2026-11-03-easa-tcds-handover.md).
Coverage: `uv run python -m tools.s02_emit.easa.tcds.coverage > /dev/null`.

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
- **ETCDS-5. CS 25.851 is only partly laid out, so 3 models are held.**
  At CS25-0 … CS25-18 the children of 25.851(a) (and (b), (c)) stay on one
  line (`structure_report_easa_cs25.tsv`: `inline-skip (4)…(8), (b)`; the
  inline extinguisher table "Passenger capacity Number of extinguishers"
  sits in (a)(1)). The build then can't find cited paragraphs:
  A330-841 (EASA.A.004 line 24, `CS 25.851(a)(c) Amdt 17` → (c) at CS25-12)
  and EMB-545 / EMB-550 (EASA.IM.A.526 line 4, `CS 25.851(a)(6) at Amdt. 18`
  → (a)(6) at CS25-18). They are in `tools/overrides/aircraft_holds.tsv`.
  Close by fixing the 851 layout (structure rule or a `text.tsv` override
  with evidence), then delete the three hold rows. Check other CS-25
  provisions with `inline-skip` notes for the same risk.
- **ETCDS-6. Shared basis sections are not attached to models.** A section
  titled "General (All Models)" / "Data pertinent …" that holds a
  certification basis (IM.A.071, IM.A.080, IM.A.188; reported as a warning)
  is skipped, and its models get only their own section's entries, or none.
  EASA.A.010 (TBM 700): Section A "GENERAL (ALL TBM700)" holds the basis and
  Section B lists TBM700 A … N in one section, so nothing is staged and
  the FAA A60EU TBM stays FAA-only. Needs a rule for inheriting a shared
  basis (and for which models it covers).
- **ETCDS-7. Series sections are not split into models** (42 TCDS, e.g.
  A.004 A330, A.015, A.064, IM.A.196 747-400, IM.A.229 EMB-110 "(ALL
  VARIANTS)"). Reported "several models in one section"; nothing staged.
  Needs the model list (1.2 Models/Variants, the cover's "For Models") and a
  rule for per-model scoped lines.
- **ETCDS-8. 12 in-scope models refused as implausible designations**
  (2026-11-03 guard): A.004 `Passenger Models:`, A.182 `BAe 146 Model` /
  `AVRO 146-RJ Model`, IM.A.001 `EMBRAER ERJ 170-100 VARIANT` / `-200
  VARIANT`, IM.A.003 `(-200 VARIANT)`, `(- 300ER VARIANT)`, `(- 200LR
  VARIANT)`, `(F Freighter VARIANT)`, IM.A.035 `767-300BCF (Major Design
  Change)`, IM.A.171 `EA500 DESIGNATION`, IM.A.643 `CL-215-6B11 (CL-215T
  Variant) (Restricted Category)`. Each is a layout the designation reader
  doesn't know (variant tables, "MODEL X DESIGNATION" titles). Fix per
  layout; the guard stays.
- **ETCDS-9. Table-shaped basis fields split badly.** 3-column SC / ESF
  tables (Dornier A.096) come out as one entry per wrapped row, and
  cross-field tables ("as per D.II.2 as amended by:") become separate
  entries, like the FAA "additions" in TCDS-1.
- **ETCDS-10. PC-12 paragraph letters are unread.** EASA.A.089 rows such as
  `23.305 a (23-45)` (a letter without parentheses) resolve without the
  paragraph or come out `partial`.
- **ETCDS-11. Environmental sub-labels fold into the field label**
  ("Environmental Protection … Noise: …"), so the `other` entry starts with
  the sub-label. Cosmetic, but `raw_reference` should start at the value.
- **ETCDS-12. Transport is inferred when no category is printed** (49
  staged models, e.g. SAAB 340/2000 A.068/A.069, Dornier 328 A.096, CN-235
  / C-295 A.186, C-212 A.187): a Part 25 basis → `transport`, with a report
  note. Confirm this is acceptable, or require a printed category.
- **ETCDS-13. "basis cites no CS/JAR/FAR 23 or 25" misses indirect bases**
  (76 TCDS, many correct: sailplanes, CS-22). Some are aeroplanes whose basis
  points elsewhere ("same as …", A330-941 in A.004, L-410). Distinguish the
  two before trusting the out-of-scope count.
- **ETCDS-14. Link decisions to review** (`tools/overrides/aircraft_links.tsv`,
  33 rows, 2026-11-03):
  - DA 40 (A47CE / IM.A.022) and DA 62 Inc (A00012NY / IM.A.629): the State
    of Design is TCCA, which has no TCDS here; FAA was taken as primary
    (same path either way).
  - DA 62 on A57CE (GmbH, the EASA.A.005 derivative) is not linked to
    IM.A.629: a different TC (A00012NY Note 9).
  - DA 42 (EASA.A.005 primary): `manufacturer` becomes the EASA cover's
    `DIAMOND AIRCRAFT INDUSTRIES GMBH` (was FAA's mixed case).
  - LC42-550FG: EASA.IM.A.516 gives the FAA TC date as 30 March 2003; FAA
    A00003SE says May 30, 2003.

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
  - Cause found 2026-11-03: they are in the pre-v6 shape (top-level
    `categories`; schema v6 puts it in each `tcb`), so building the real
    `data/` fails (`u206g.json: at tcb/0 'categories' is a required
    property`). That also fails `test_da40_golden_is_the_promoted_file` and
    `test_real_data_has_no_ecfr_marker_in_text`, and errors the root
    `tests/test_similarity.py`. Re-staging and promoting aircraft
    (`parse`, `aircraft.assemble`, `promote --aircraft`) replaces them: of
    the 95 existing models, 88 are identical in the new shape and 7 differ
    only by newly resolved Part 23 references.
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
- **BUILD-7. The app must read `tcb_categories` (contract v6).** Schema v6
  moved categories from the model to the TCB: `model_categories` is gone
  and `tcb_categories (tcb_id, category_id)` replaces it. FARFETCHed still
  queries `model_categories`, so it breaks on the first v6
  `cert_basis.sqlite`. Change the app before shipping a v6 build; a model's
  categories are now the union over its TCBs, or per regulator.

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
  Also: the dry-run still asks `overwrite …? [y/N]` per conflict. It
  auto-skips only when stdin is closed; with an open non-tty stdin (a
  background job) it blocks forever. Run it with `< /dev/null`.
- **PROC-8. FAA extract is serial.** A `ThreadPoolExecutor` with about 10
  workers would give roughly 5–10× on 1,000+ row batches. The DRS JWT cookie
  needs a lock around refresh, or per-worker sessions. (was: TODO.md)
- **PROC-9. Stale inputs in the parent's `input/`:** `input/parsed/` (old TCDS
  output, 2026-10-31) and `input/regs.csv.work` (identical to `regs.csv`).
  Both are untracked; the user to decide whether to remove them. (tools
  handover 2026-11-02)
- **PROC-10. `input/` is not in git and has no backup.** It now holds the DRS
  raw copies (`input/cache/drs/far_doc/`, 569 downloads for Part 23 alone),
  the govinfo FR scans used as override evidence (`input/cache/fr/`) and OCR
  sidecars. `rm -rf tools/out` is safe; losing `input/` is not (DRS pages can
  change or go). Related: ETCDS-1.

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
  citing "CS-25 Amendment N". 2026-11-03: parser, coverage and the
  cross-regulator assemble step exist (CS-23/25 aeroplanes; ETCDS-5…14);
  next are rotorcraft (CS-27/29) and the scope widening. Also download the Noise TCDS (TCDSN), which is
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
