# FAA regulations (FAA-)

14 CFR Parts 23, 25, 26, 27, 29 and 36, from DRS and eCFR. Pipeline:
[tools/s00_docs/FAA_REGS.md](../tools/s00_docs/FAA_REGS.md). Overrides:
`tools/overrides/faa_regs.tsv`. [Index](../ISSUES.md)

## Undeclared or doubtful amendments

### FAA-1. 23-56 and 23-60 are undeclared and unexplained

DRS has no document for either. A Federal Register full-text search found no
rule naming them, and eCFR and the DRS CSV don't list them. That is absence
of evidence, not proof they were never issued. A TCDS citing either as a
range endpoint is rejected by the build ("unknown revision"), which is
intended until a source turns up.

Not yet checked: a general web search, FAA's amendment-history tables, and FR
rules from 2002-03..2007-08 (23-56) and 2008-12..2011-08 (23-60) read by hand.

**To close:** find a source that declares or rules out each number.

### FAA-4. 25-118 is a DRS `Sec. 0.0` "inadvertently skipped" number

It is deliberately not declared. A TCDS citing "through 25-118" needs a human
decision (probably 25-117).

**To close:** decide how a TCDS range ending at 25-118 resolves, when one
appears.

### FAA-5. 27-41 and 29-48 have no DRS document

Both are undeclared. Same question as FAA-1.

**To close:** as FAA-1.

### FAA-6. Part 36 numbering above 36-32 is unconfirmed

The manifest assumes contiguous numbering, so its Part 36 gap list runs
36-33..36-54 (36-32 is from 2022). None has a DRS document and they probably
never existed (the "36-54" of 2002 is a misprint of 36-24, see FAA-23).

**To close:** confirm from FAA's amendment history that 36-32 is the latest,
then stop listing the gap.

## Dates and citations

### FAA-3. Part 23 Appendix E at 23-2 has no confirmed date

DRS gives 07/08/1965 for Appendix E at 23-2 (regs.csv agrees), while §23.25 of
the same amendment says 1965-08-01. Until an override with evidence exists,
E23@23-2 is `TEXT MISSING`.

- Searched: FR 1965-06-29, -06-30, -07-01 and -07-08 (govinfo scans, OCR);
  they hold no Part 23 rule other than Amdt 23-1 (30 FR 8261). The manifest
  has no FR cite for 23-2 (Docket 2029, issued 1965-06-24).
- Not yet searched: FR 1965-06-25/26 and 07-02..07.
- Lead: a search snippet of FAA's Part 23 certification-basis summary table
  (faa.gov `.../small_airplanes/certification_basis/part23_summary/`, 403 on
  direct fetch, unverified) lists 23-2 as effective 8/1/1965, "Limited Weight
  Credit for Airplanes Equipped with Standby Power", which fits Appendix E and
  §23.25. archives.federalregister.gov issue slices have a text layer but
  need exact page ranges (`issue_slice/1965/7/3/8516-8519.pdf` is a Part 25
  rule, not 23-2).

Related, lower priority: the `drs_date` overrides for 25-46 (§25.629), 25-60
(§25.855) and 29-3 (§29.1505) rest on majority evidence only (one DRS
document disagreeing with the amendment's others); why it differs is not
established.

**To close:** find the FR publication of 23-2 and add a `drs_date` override
with it as evidence; confirm the three majority-based overrides if they ever
matter.

### FAA-12. Amendment-level FR cites point at the rule's first page

Where a section has no eCFR CITA cite, the cite comes from the amendment
manifest (`fr_cite_source=manifest_amendment`): the rule's first page, not
the section's own page.

**To close:** refine per section if needed.

### FAA-16. `faa_rules_published()` can miss FR documents

The daily FAA listing missed FR doc 96-2082 (61 FR 5171, Amdt 23-50,
1996-02-09), although the FR API serves it by docket. Separately,
§23.573@23-48 text reflects the 2008 technical amendment (73 FR 19746), not
the 1996 wording.

**To close:** check the agency filter before relying on this lookup (see
PROC-3); decide whether §23.573@23-48 needs the original wording.

### FAA-20. Amendment-level cites for 25-148 and 25-151 are the corrections'

The manifest gives 88 FR 2813 and 88 FR 44032 (the corrections); the rules are
87 FR 75704 and 88 FR 39152. Section-level CITA cites are right. Related to
FAA-12.

**To close:** check the `source_url`/`publication_cite` those versions carry
and fix the amendment cite.

## Missing or withheld versions

### FAA-10. `TEXT MISSING` that DRS cannot supply

- §G25.1@25-141 (figure only).
- Part 36 Appendix C@36-24 (no DRS text; the version is dropped by the
  deletion rule).

**To close:** recheck if another source turns up.

### FAA-15. Part 23 versions not emitted or `TEXT MISSING`

- B23.1/B23.11@23-42 are not emitted.
- §1567@23-13 (DRS has no 23-13 document) and §903@23-54 (`skip_human`) are
  `TEXT MISSING`.

**To close:** a source for each, or a recorded decision that they stay.

### FAA-18. `TEXT MISSING` in Parts 25, 27 and 29

No DRS document and the date predates eCFR point-in-time data:

- Part 25: §733@25-48, §1181@25-11, Appendix M25@25-125.
- Part 27: §87@27-0, 27-14, 27-21 (height-velocity envelope).
- Part 29: §967@29-26, §1019@29-10, §1093@29-3, §1303@29-12, §1521@29-3.
- Part 29 Appendix B29@29-39: the subsection set differs from DRS's listing
  (B29.8 exists only at 29-31).

Part 27 §401, §403 and §413 @27-27 are also `TEXT MISSING`, but recoverable:
DRS has two equivalent "Removed" stubs for each (`csv_duplicate`), so they
should be `deleted` versions. Until then they look live after 27-27. The
worklist now fetches a kept `csv_duplicate` row.

**To close:** re-run Part 27 `worklist`/`extract`/`emit`, review and promote
the three stubs; the rest need another source.

### FAA-23. Part 36 gaps

Eight versions are `TEXT MISSING`, none recoverable from DRS:

- §1583@36-18: no DRS document, pre-2017. The text is the 36-11 text with one
  cross-reference changed ("§ 91.56" → "§ 91.815").
- Appendices A and B @36-24 and @36-26: DRS holds no text for the 2002
  rewrite.
- Appendix J @36-25 and @36-30: DRS holds J36 subsections only at 36-20.
- Appendix F @36-9: the CITA lists 36-9, DRS has no F36 text there. Not
  checked in the FR (43 FR 8754, 1978).

Not in the dataset: Appendix C before 2002. DRS subsections C36.1..C36.9
(36-0..36-15) are extracted but never planned, because eCFR has no Appendix
C, so the manifest has no C36 rows (24 of the 26 `orphan` files).

**To close:** FR text for each gap (an override with evidence), and a
decision on whether pre-2002 Appendix C should be planned.

## Extraction

### FAA-11. Part 23 must be manifested with `--as-of 2017-08-29`

The default is the newest eCFR date, which is the post-rewrite Part 23. The
docs say so, but `manifest.py` defaults to `latest_date()` regardless.

**To close:** enforce the date for Part 23 in code.

### FAA-25. Tables that DRS has only as images are missing

No image is cached under `input/`, so these tables have a caption or
introducer but no cells: J23@23-57 (both HIRF tables), A23.13 Table 2 (all
four versions), A36.3/A36.4 Tables A36-1 and A36-2 (still images at 36-31),
probably J36.109, and 14 CFR 26: §26.5 Table 1 at 26-0 to 26-3 (a table from
26-5), §26.35 Tables 1 and 2 at 26-2, 26-3 and 26-7. The FR prints these Part 26
tables as text (73 FR 42444, 74 FR 31618), and eCFR has §26.35's from 2017.

**To close:** fetch the images, transcribe each table as a `text.tsv`
`replace_text` row in the flat table form (docs/DATA_FORMAT.md §Tables), with
the image as evidence.

### FAA-26. Old DRS tables mark no header row

rgl-era DRS tables have no `<th>` (25.1393@25-0 "Angle above or below the
horizontal plane: | Intensity"), so their first row is a data row; the
eCFR-rendered versions of the same tables have a header. A DRS-to-eCFR
version pair then differs in markup as well as words.

**To close:** decide whether a first row of all-text cells over numeric rows
may be marked a header, or leave it.

### FAA-27. 25.725 and 25.727 re-extract as `deleted`

A `--redo --offline` re-extract (2026-11-07) stages both as `deleted: true`
(titles "Limit drop tests." / "Reserve energy absorption drop tests.") where
`data/` has a `Reserved.` text version. The change comes from the stub rules
(`is_removed_doc`), not from tables.

**To close:** review which is right and promote separately.

### FAA-28. Appendices A and B to Part 25 are image-only in DRS

DRS has A25@25-0 and B25@25-0 only as scanned images (`EC28SE91.050`-`.054`
for A25) with no text, so both are `TEXT MISSING`. Until 2026-11-08 the
extractor wrongly took the trailing eCFR `<script type="application/json">`
metadata as their text (and appended it to 25.1707@25-123); that is fixed
(`_html_to_text` drops `<script>`/`<style>`), so the gap now shows honestly.

**To close:** fetch the images (the `img.federalregister.gov` URLs are in the
cached DRS doc under `input/cache/drs/far_doc/`), transcribe them, and add a
`text.tsv` `replace_text` row per appendix with the images as evidence. Check
whether eCFR has a text rendering of either appendix before transcribing.

### FAA-29. Part 23 stops before the 2017 rewrite

The dataset's last Part 23 revision is 23-63 (2017-03-21). Amendment 23-64 and
later, the performance-based rewrite (§23.2005 onward), are excluded by the
`--as-of 2017-08-29` manifest (FAA-11), and no issue records this as a gap.
51 basis entries on 21 models (14 TCDS, e.g. A00121CE, A00009CH) cite 23-64 or
later (2026-11-08, pattern match). Each resolves to nothing or only partly.

**To close:** decide how to model it (later revisions of the same document, or
a separate one, since the section numbers all change), then ingest it.

### FAA-30. Symbols that DRS has only as images are missing from the text

Where DRS prints a symbol or formula as an image, the text keeps the words
around a gap: "must not be less than ; and" (23.51), "a power-off glide at
1.4 ;" (23.1001), "the highest value of and ;" (23.49), and definition lists
whose every symbol is gone, "; = density of air (slugs/cu.ft.); W/S = wing
loading" (25.341). The `dropped-symbol` scan check finds 383 places in 69 FAA
provisions (2026-11-12): mostly V-speeds in Parts 23 and 25 flight sections
(23.145, 23.161, 23.67, 25.145, 25.175) and the gust and seaplane load formulas
(23.341, 23.443, 25.341, 25.351, 25.531 to 25.535). GitHub #24 (23.341, "the
equation … bunched in paragraph (c)") is one of them. FAA-25 is the same loss
for tables; TEXT-11 is formulas that are present but flattened.

**To close:** `replace_text` rows writing the symbols (`1.4 V_{S1}`) and
formula lines, checked against the Federal Register or eCFR text, then answer
GitHub #24.

## Groupings

### FAA-31. FAA `grouping_at_time` is the present-day DRS label

DRS stamps today's `Subpart/Appendix` label on every historical version of a
section, so FAA `grouping_at_time` is present-day, not "the subpart at this
revision" (DATA_FORMAT says so). Evidence: DRS
`F4567343824D03458525668E00557A3A`, §36.201 at Initial (1969), status
Historical, is labelled `Subpart C [Reserved]`, yet its text is an active
noise-limits rule; every FAA section carries one label across all its
amendments (3,604 extracted documents checked, 2026-11-12). The app's view of
Part 36 at 36-0 therefore shows §36.201 under `Subpart C — Reserved`. eCFR
point-in-time starts in 2017, and no cached Federal Register text covers
Part 36.

**To close:** a source for FAA historical subpart names (FR rule texts),
then override rows per rename, if ever wanted.

### FAA-32. Part 36 reserved-subpart placeholders and §36.1100

36.400, .900, .1000, .1100, .1200, .1300 and .1400 are DRS "Subpart X is
reserved." documents (Initial, 1969) in force in `data/`; eCFR has no such
sections. Each is its own one-item `Subpart X — Reserved` group. §36.1100
(`Subpart K [Reserved]`, DRS status Current) contradicts Subpart K
Tiltrotors (36-29, §36.1101/§36.1103), so the app shows "Subpart K —
Tiltrotors / Reserved". DRS also labels §36.600@36-14 ("§ 36.699
[Reserved]", the 36.6xx Subpart G range) as Subpart C; emit would report it
`subpart_mismatch` if it were emitted (it fails `empty_text`). Related to
GitHub #19.

**To close:** read 36-29's FR text for what happened to §36.1100 (a
`deleted` version at 36-29 if it was replaced), and decide whether the
placeholders are provisions at all.
