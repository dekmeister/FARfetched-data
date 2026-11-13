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

### NATO-4. Figures, formulas and layout leftovers

Book 1's tables are rebuilt (geometry or transcribed rows; NATO_USAR.md
§Tables). Left:

- Figures aren't in the text layer: the flight envelope under `333`,
  Appendix K Figure 1 (Appendix K is 27,000 characters of running text).
- One version is `flat-failed`: Ed. 1 Appendix G. It isn't a table: G.3
  prints doubled labels (`(a) (I) UAV Maintenance Manual or section`,
  `(b) (II) Ground segment …`), which break the label sequence.
- Formulas are flat words: 415(a)(2) (`2.01 W/S + 4.45`, Ed. B
  `14.6√ 𝑊 𝑆 + 14.6`), 1401(e) (the effective-intensity integral), and Ed. B
  423 still carries Symbol-font private-use characters (U+F02B, U+F02D,
  U+F0E6-F0E8, U+F0F6-F0F8: a formula's signs and bracket pieces).
- 423's two `line-fallback` versions keep the plain reading.

**To close:** formula rows (TEXT- format) for 415, 423 and 1401; a
`replace_text` row or a fix for Ed. 1 Appendix G's doubled labels;
sample-review the 250 `line-split` versions (a spot check of 40 read right).

### NATO-5. Limits of the continuity review

505 provisions, 848 versions; eight decision rows cover the identity breaks.

- Not decided row by row: 8 same-number pairs that continue on an identical
  title with rewritten text (57, U2, 341, U850, 1195, 1197, 1199, 1201).
- Partial splits and merges aren't recorded (ROADMAP-4).
- Stubs are ingested as printed provisions (policy in NATO_USAR.md).

**To close:** confirm the 8 pairs; the maintainer to say if stubs should be
skipped.

### NATO-7. An unlabelled lead-in between two labels joins the label before it

USAR.1323 (Ed1 and EdB-V1) prints "For all airspeed measuring devices:" as a
paragraph of its own between (b) and (c) (EdB-V1 pdftotext, blank lines
around it). The extractor keeps a source break only before a line that opens
with a label, so the lead-in ends (b)'s line. The format holds it (an
unlabelled depth-0 line between (b) and (c) parses), but `structure_version`
with `source_breaks` honours breaks only before labels, and `text.tsv` can't
add one. A whole-tree search (a label line ending in `. Xxx … :` followed by
the next sibling label) finds only this provision. Audit F-20261112-12.

**To close:** keep a break before a whole source line that ends in `:` after
a sentence end and before a sibling label (extractor and structure rule), or
accept it for one provision.
