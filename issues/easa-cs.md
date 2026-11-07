# EASA CS (EASA-)

CS-23, CS-25, CS-27 and CS-29 from the EASA PDFs. Pipeline:
[tools/s00_docs/EASA_CS.md](../tools/s00_docs/EASA_CS.md). Reports:
`tools/out/reports/emit_easa_cs{n}_report.tsv`. Overrides:
`tools/overrides/easa_cs.tsv`. [Index](../ISSUES.md)

## Source questions

### EASA-1. CS-29 Amdt 10 exists only as a corrigendum

ED Decision 2021/016/R. It is promoted with the corrigendum text and the
effective date 2021-12-18 borrowed from CS-27 Amdt 9.

**To close:** check against the original Amdt 10, if EASA still has it, and
confirm the date.

### EASA-2. CS-23 Amdt 2 ED Decision number conflicts

The website says 2010/007/R; the CS-23 Amdt 6 preamble says 2010/008/R.

**To close:** establish which is right.

### EASA-3. The CS-23 Amdt 1 PDF prints page 1–E–25 twice

Extract drops the repeat.

**To close:** check CS 23.1199–23.1203 at CS23-1 against the PDF.

### EASA-4. CS 23.851 at CS23-3 is said to change but doesn't

The preamble says it was amended, but the extracted text is identical
(probably only the AMC reference changed). No version is emitted.

**To close:** confirm against the PDF.

### EASA-7. CS-23 Amdt 5 and 6 texts come from republished files

They come from AMC/GM republications and have not been verified against the
original 2017/2023 files.

**To close:** compare with the originals.

### EASA-13. CS 25.807(k) appears only in the Amdt 27 PDF

It gives two versions (added at 27, removed at 28).

**To close:** ask EASA or check the ED Decisions.

## Missing or wrong text

### EASA-5. Appendix I to CS-23 has no text layer

Figures only, in every issue; its versions are `TEXT MISSING`.

**To close:** none from the PDFs; a transcription source would be needed.

### EASA-21. CS-29 Appendix B at Amdt 11 has no `IV.` heading

The CS29-11 PDF prints `III. Trim` and then `(a) General. The helicopter must
possess positive static longitudinal control force stability` with no
`IV. Static longitudinal stability` line (CS29-0/1 and the FAA text have it,
and the text itself cites "IV (b) to (f)"). Roman headings must run in order,
so this version stays one flat line (`flat-failed`). Found fixing GitHub #17.

**To close:** a `replace_text` override restoring the heading, with evidence
from CS29-1 and the cross-references (needs the developer's call: it adds
words the Amdt 11 PDF lacks).

### EASA-8. CS 25.773 at Amdt 16 is `TEXT MISSING`

The heading sits on a two-column page and the body isn't extracted, but the
text is in the PDF (CS25-17.pdf, `pdftotext -layout` line 7177).

**To close:** fix the column order in extract.

### EASA-9. `manifest_change_not_in_text` not reviewed

CS-25 has 20 (mostly Amdt 28, AMC-only or sub-word changes); CS-27 and CS-29
have 2 each.

**To close:** check each one.

### EASA-10. CS-25 Subpart J (APU) isn't split into provisions

Its 25J9xx text is part of CS 25.1591 (to Amdt 4) and 25.1731 (later).

**To close:** a heading rule for "CS 25J901" and a numbering decision.

### EASA-19. CS-25 1591 (Amdt 0-3) and 1731 swallow the CS-APU book

Their texts are ~40,000 characters: everything up to the next accepted
heading, including CS-APU (Book 1 Section B) with its own `CS 25B1011`-style
headings.

**To close:** stop the CS-25 run at the CS-APU part (as `_book2_start` does
for Book 2), then re-check the version counts of both.

### EASA-11. Letter-spaced text in old CS-29 PDFs

"m ight", "t he" are stored as printed. Display and search suffer.

**To close:** a careful de-spacing pass, or accept it.

### EASA-12. Group headings run into the preceding paragraph in CS25-0

E.g. "Emergency Landing Conditions" at the end of 25.519. Cosmetic.

**To close:** a heading rule for CS25-0, or accept it.

### EASA-18. Chart labels are read into the text

Bare numbers in the page body are kept (they are table cells and formula
parts), so chart axis numbers come through with their axis labels: CS 23.1443
(LPM chart), 23.441 (rudder force), A23 figures A1-A7.

**To close:** drop text inside figure areas (no ruling-line table, many short
numeric lines), or override rows.

### EASA-20. Collapsed spurious versions keep the older text

The 2026-11-07 cell fixes removed 12 versions that existed only because cells
were lost (CS-25 109, 1401, 562, 851 @CS25-27; 1731 @CS25-26; CS-27 397, 562,
1393, 1401 @CS27-10; CS-29 562, 1391, 1401 @CS29-11). The text in force is now
the earlier PDF's, which for re-typeset issues is often the worse reading
(CS 29.562@CS29-0 has "m etres").

**To close:** decide whether a cleaner re-typeset reading may replace the text
without a new version.

## Titles and grouping

### EASA-6. Titles have no canonical source

Appendix titles that wrap keep half a title unless the first line ends in a
dangling word. Capitalised headings (CS-25 Amdt 27+) keep the earlier
mixed-case title, some titles are table headers (L25 "Strength Value"), and
wrapped paragraph titles keep only their first line.

**To close:** spot-check `canonical_title` and fix the cases found.

### EASA-16. Subpart labels differ in style from FAA

- `.title()` gives "Design And Construction"; FAA has "Design and
  Construction".
- EASA values keep the "Subpart X — " prefix; FAA values don't ("Equipment").

Real renames across amendments stay distinct on purpose (CS-23 "Structure" →
"Structures", Amdt 5 rewrite); the app merges them for display.

**To close:** a contract/display decision on cross-issuer label style.

## Tables and extraction robustness

### EASA-17. Tables are flattened, often column by column

The extractor reads text only. A table whose columns sit either side of the
page centre comes out column-major ("Type A Type B Type C Type I 110 75 55 45
…", CS 25.807@CS25-28; the HIRF tables of CS-25 R25, CS-27 D27, CS-29 E29),
and wrapped cells split (E29@CS29-4). About 50 provisions / 120 versions:
143, 397, 405, 415, 509, 621, 807, 812, 815, 851, 1093, 1324, 1391-1401,
1435, 1453, A23, C23, K23, F25, L25, N25, P25, R25, D27, E29. Spurious
versions from table reading remain: E29@CS29-11/12 (a repeated "FIELD
STRENGTH (V/m) PEAK AVERAGE" header) and other `unexplained_change` rows on
table paragraphs.

**To close:** rebuild tables from geometry: word boxes from `pdftotext
-bbox-layout` plus ruling lines from `mutool trace` (old PDFs draw full grids;
Word 365 PDFs draw grey row rules with ~2 pt gaps at column edges). Cells must
come out identical in every PDF a provision appears in, or each difference
needs a `suppress` row. 60 PDFs, at least 8 producers; skip AMC tables on
interleaved pages.

### EASA-14. Extraction heuristics are layout-specific

- Column order still fails where a figure splits a two-column page (CS25-8..10
  p. 1-C-4); fixed by an override, not in code.
- `_header_lines`, the `listed` heuristic and the AMC heading pattern are
  pattern-based.

**To close:** ongoing watch: look for paragraphs whose length jumps without a
manifest entry when new PDFs are added.

### EASA-15. Small extract/emit improvements

- discover should record the corrigendum Decision (2022/010/R) in the
  catalogue notes.
- `amdt_markers` are unused by emit, but could cross-check versions.

**To close:** implement both.
