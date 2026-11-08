# NATO USAR (NATO-)

STANAG 4671 Ed. 1 and AEP-4671 Ed. B. Pipeline `nato/usar`:
[tools/s00_docs/NATO_USAR.md](../tools/s00_docs/NATO_USAR.md). Reports:
`tools/out/reports/nato_usar_extract_report.tsv` and
`emit_nato_usar_report.tsv`. Continuity decisions:
`tools/overrides/nato_usar.tsv`. [Index](../ISSUES.md)

### NATO-1. Edition gap: STANAG 4671 Ed. 2 and AEP-4671 Ed. A

Both are dated 9 February 2017 and aren't freely available. The history is
Ed. 1 → Ed. B (`Ed1` ordinal 0, `EdB-V1` ordinal 2; `1` is free), so a
paragraph that changed at Ed. 2/A shows its change at Ed. B. Nothing in the
format represents a missing revision (`TEXT MISSING` is for text known to
exist but unreadable).

**To close:** if the documents turn up, add them as input and re-run the
continuity review (decisions are keyed by designator and number).

### NATO-2. `source_url` is unverified

`s01_extract/nato/usar/manifest.py` uses the NSDD pages `stanag-details/9175`
(Ed. 1) and `ap-details/2783` (Ed. B). Both answered HTTP 404 from the build
host on 2026-11-06 (bot blocking or wrong paths). Ed. 1's actual provenance,
the French MoD archive copy via the Wayback Machine, has no URL in the repo.
The 2009-09-03 date of Ed. 1 comes from the file name.

**To close:** replace both with checked URLs (the Wayback snapshot for
Ed. 1) and confirm the Ed. 1 date against the NSDD record.

### NATO-3. Annexes and Book 2 are not ingested

Out of scope today: the introduction, Annex A (glossary), Annex B
(abbreviations), Annex C (the cross-reference table with EASA CS-23) and
Book 2 (the AMC; the `See AMC.17` pointer lines stay in each paragraph).

**To close:** ingest Annex C if ROADMAP-4 cross-document links go ahead; the
rest only if wanted.

### NATO-4. Tables and figures in the text layer

Book 1's tables and figures are absent from the text layer or run into the
text (Appendix C, the flight envelope under `333`, Appendix L's HIRF tables,
Appendix K: 27,000 characters of mostly flat text). One version is
`flat-failed` (Ed. 1 Appendix G, a scrambled table). The tables of 415 and 423
have labelled rows, so they are `line-fallback` and stay inline in (b).

**To close:** handle the tables with NATO-6; sample-review the 250
`line-split` versions (a spot check of 40 read right).

### NATO-5. Limits of the continuity review

505 provisions, 848 versions; eight decision rows cover the identity breaks.

- Not decided row by row: 8 same-number pairs that continue on an identical
  title with rewritten text (57, U2, 341, U850, 1195, 1197, 1199, 1201).
- Partial splits and merges aren't recorded (ROADMAP-4).
- Stubs are ingested as printed provisions (policy in NATO_USAR.md).

**To close:** confirm the 8 pairs; the maintainer to say if stubs should be
skipped.

### NATO-6. Tables in STANAG 4671 are flattened

The extractor uses `pdftotext -raw`, so there is no geometry: 1391, 1393,
1395, 1401 (readable row order), AppL (HIRF), AppK Table 1, AppC (EdB:
column-major; Ed1: the table is a raster image, only the notes are text).
About 7 provisions / 10 versions.

**To close:** EdB draws full vector grids (AppC p.187, AppL p.205), so the
geometry route of EASA-17 would work there; Ed. 1 AppC needs transcription.

### NATO-7. USAR.865 at EdB-V1 has a wrapped title read into its text

Reported from the site (GitHub #18). The title stops at "…and other flight",
and the text opens "structure See AMC.865 …". It is the only STANAG version
whose text opens with a stray lower-case word (2026-11-08).

**To close:** an extractor fix or override rows, then answer GitHub #18.
