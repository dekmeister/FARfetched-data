# Text layout (TEXT-)

Paragraph structure of label-line text (docs/DATA_FORMAT.md §Text format),
across all issuers. The words are intact by assertion; these items affect
which paragraph a sentence appears to belong to, plus the format's limits
for tables and formulas. Rules: [tools/s00_docs/STRUCTURE.md](../tools/s00_docs/STRUCTURE.md).

Counts are report rows in `tools/out/reports/structure_report_*.tsv`
(excluding `_migration`) on 2026-11-07, an upper bound on affected versions.
List a kind with e.g.
`awk -F'\t' '$3 ~ /KIND/ || $5 ~ /KIND/' tools/out/reports/structure_report_faa.tsv`.
[Index](../ISSUES.md)

## Heuristic layout to review

### TEXT-1. Trailing unlabelled paragraphs are attached to the last item

`possible-trailing`, 1,024 rows. E.g. §23.1309(b) "Each item … must also …"
is stored as `(b)(2)`. The main fix candidate, eCFR/DRS `<P>` breaks as
hints, was deferred because it causes version churn between sources. TEXT-8
is the same effect from the other direction.

**To close:** revisit the `<P>`-hint approach before the app relies on
paragraph scope; otherwise review the flagged rows.

### TEXT-2. Real paragraphs may be kept inline

`inline-skip`, 184 rows. If the predecessor label was a stray
cross-reference, a real paragraph is merged and its path goes missing.

**To close:** review the flagged rows.

### TEXT-3. Splits after `, and` / `, or` and fit-splits

`weak-split` (268) can create false paragraphs mid-sentence; `fit-split`
(316: a label with no boundary, taken as the next value or after a short
heading) has the same risk. A sample of 45 read right.

**To close:** review the rest.

### TEXT-4. Ambiguous labels resolved by heuristic

`tie`, 100 rows. A wrong guess nests a paragraph under the wrong parent.

**To close:** review the flagged rows.

### TEXT-5. Label gaps may hide misreads

`gap` rows; build report `label_gaps`. Most are in CS-25.

**To close:** review the gaps.

### TEXT-6. Flat-failed texts show as one block

`flat-failed`, 171 rows. Paragraph refs to them are unverifiable.

- FAA: e.g. 23.45@23-21 (DRS dropped a `(`), 23.1147@23-43 (`(a)[(1)`),
  H36@36-14/24/25/30.
- EASA: lists without an introducer, flattened tables, appendix sub-sections (helicopter IFR Appendix B now splits by
  roman headings; CS29-11 is EASA-21).
  25.773@CS25-27 is flat because the source labels two paragraphs `(ii)` in
  (b)(3).
- CAR: see CAR-1. DOD: see DOD-4.

**To close:** fix per cause (override rows or structure rules).

### TEXT-8. Source line breaks that marked real paragraphs were dropped

`dropped-break`, 35 rows. Same effect as TEXT-1, from the other direction.

**To close:** as TEXT-1.

## Format limits and app rules

### TEXT-7. FAA change brackets span paragraphs

`bracket-spans`, 1,232 rows. Rendered per paragraph they look unbalanced.

**To close:** the app needs a rendering rule.

### TEXT-10. Paragraph-ref verification checks existence only

`(a)(1)(2)` descends first, and `(c3)` is read as `(c)(3)`, so a ref can
"verify" under a reading the TCDS didn't intend.

**To close:** the app uses the same reading as `build.paragraph_ref_paths`,
or shows the qualifier verbatim.

### TEXT-11. Display formulas are still flattened into running text

Schema v10 has inline markup (docs/DATA_FORMAT.md §Inline markup): FAA (DRS
`<sub>`/`<sup>`, eCFR `<E T>`) and EASA (PDF geometry) extractors write
`_{…}`/`^{…}`, and a `$$ … $$` formula line comes from an override row. Only
CS-25/14 CFR 25.331 (c)(2)(i) has formula rows so far (GitHub #4). Left:

- Display formulas in about 150 provision files are still running text,
  often scrambled (a stacked fraction read in row order, `πV ω = 2V A`), e.g.
  the rest of 25.331 ((c)(2)(iii): δ(t), t_{1}, t_{2}), 25.341, 25.343,
  Part 23/25/36 appendices. Each needs `replace_text` rows checked against the
  source; they are not rebuilt automatically.
- Scripts the extractors can't see: one EASA PDF word that fuses a base and
  its script (`δ1` in CS-25 Amdt 27), and eCFR's single `E T="53"`
  (`1.4 Vs1`, 14 CFR 25), left flat rather than guessed.
- Flattened tables: EASA-17, DOD-8, CAR-4 and FAA-25.

**To close:** formula rows for the listed provisions; then this item goes.

### TEXT-12. Section opening words stay on the heading line

In assembled appendices, a section whose title has no end mark keeps its
opening words on the `Sec. X.N` heading line (`Sec. F23.2 Part II--…
Insulation Materials Use this test method …`). The segmenter (a pure function
of the words) can't see the title boundary.

**To close:** pass the title boundary to the segmenter, or accept it.

### TEXT-13. A list that restarts inside one paragraph nests under its predecessor

F23.1(b)@23-62 has `(1)…(3)`, a sentence, then a second `(1)…(4)`, laid out
as `(b)(3)(1)…(4)`. The format can't repeat a label under the same parent.
Also DOD-4.

**To close:** a format decision (contract change).

### TEXT-14. Figures have no representation

The format can hold text, tables and formulas but not a figure. A reader
reported this on CS 25.331 (GitHub #3, "Figure has not been incorporated").
192 of 11,868 distinct texts mention a figure by number (2026-11-08, pattern
match), and nothing tells a reader whether the figure itself is available.

**To close:** a format decision: an explicit "figure not reproduced" marker
linking to the source page, or stored images (contract change).
