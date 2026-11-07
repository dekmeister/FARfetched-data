# MIL-HDBK-516 (DOD-)

Pipeline `dod/hdbk`: [tools/s00_docs/DOD_HDBK.md](../tools/s00_docs/DOD_HDBK.md).
Reports: `tools/out/reports/dod_hdbk_extract_report.tsv` and
`emit_dod_hdbk_report.tsv`. Continuity decisions:
`tools/overrides/dod_hdbk.tsv`. [Index](../ISSUES.md)

### DOD-2. The 516/516A appendix cross-reference table is not ingested

It maps each criterion to JSSG paragraphs and 14 CFR sections (after NOTES).

**To close:** ingest it as input for cross-document links (ROADMAP-4).

### DOD-3. Section and subsection intros are not provisions

The section text, the "TYPICAL CERTIFICATION SOURCE DATA" lists, and 516D's
subsection intros (`4.1 Operational usage.` + several paragraphs) sit under
headings with children. They are reported `grouping_text` (37–139 per
edition) and dropped. Tables IV and XVI of 516D are in this text (DOD-8).

**To close:** a grouping-level text field (contract change).

### DOD-4. 516D MoC items whose numbering restarts stay flat

Under each method (Examination, Analysis, Test) the `(1)` list restarts and
continues in the next phase: 18 versions are `flat-failed` (sequence break at
(2)/(3)); 933 of 993 516D versions are structured. Same format limit as
TEXT-13.

**To close:** follows TEXT-13.

### DOD-5. Titles of 516-516B are first sentences

Those editions print no paragraph titles; `title_at_revision` is the
criterion's first sentence. A provision that lives into 516C takes its 516C
title as `canonical_title`; one deleted earlier keeps the sentence.

**To close:** accept as the documented behaviour, or decide on a different
title source.

### DOD-6. Superscripts are lost

The text layer gives `10-7 per flight hour` for 10⁻⁷ (23 places in
516C/516D).

**To close:** `text.tsv` rows writing `10^{-7}` (inline markup exists since
schema v10, docs/DATA_FORMAT.md §Inline markup).

### DOD-7. Limits of the continuity review

816 decision rows.

- Candidates come from text similarity (cosine >= 0.6) or near-identical
  printed titles (516C/D). A move that was both reworded and retitled (common
  in 516D) is found only if a reviewer spotted it: 516D still starts more new
  keys than any other edition.
- Several splits gave the key by judgement (rule in DOD_HDBK.md): 516D
  11.1.1.1, 516D 8.4.4, 516C 14.1.1.4.1 and 11.3.3.1, 516B w/CHANGE 1 5.1.3.
- Merges are recorded only as one continuing key (ROADMAP-4).
- Deleted provisions keep the section title they were last printed under, so
  the document page has two groups for sections 10, 15 and 20. The app merges
  only titles that extend one another.

**To close:** a second review pass on 516D new keys; the merge and grouping
points follow ROADMAP-4.

### DOD-8. Handbook tables are flattened

15 provisions of 516D/516C hold tables (516D Tables I-III, V-XV, XVII; 516C
Table I) as running text in row order. Multi-page tables repeat their caption
and header ("TABLE I. … – Continued."), 4.3.3-516d and 4.3.4-516d are
`flat-failed`, and 9.3.4.2 Table VIII has a row-spanning cell read
column-wise.

**To close:** the flat table form through override rows, or extraction from
`-bbox-layout` geometry.
