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

### EASA-25. Appendix A to CS-25 has no text layer

Figure 1 (basic landing gear dimension data) and the landing-attitude figures
are images in every issue (CS25-28 pp. 1265–1269), so its versions are `TEXT
MISSING`: CS25-0, plus CS25-4 and CS25-28, where the manifest says it was
amended (Amdt 4 change information; Amdt 28 "Editorial correction"). Reported
as GitHub #28. The FAA counterpart is FAA-28.

**To close:** none from the PDFs. A description of the figures would not be
the regulation's words; leave it unless EASA publishes a text version.

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

### EASA-22. CS-25 Subpart J is not linked across its renumbering

Subpart J was split on 2026-11-08 into provisions keyed as printed: `A…` and
`B…` at Amdt 0 show as deleted at Amdt 1, where `J…` appear, because nothing
records that 25A901 became 25J901. TCDS citations in that form (`25J903(d1)`,
`25A901(c)`) are not read by `tcds_refs` either, so they stay unresolved.

**To close:** decide whether to link A/B to J (one provision across the
renumber, or a note), and teach `tcds_refs` the `25J…` form.

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

### EASA-16. A subpart renamed without a new version keeps its old name

The grouping style is done (`Subpart D — Design and Construction`;
rule in docs/DATA_FORMAT.md §Grouping labels). Left: `grouping_at_time`
is the heading over a version's text when it was printed, so a later rename
with no new version doesn't reach it. CS-25 Subpart H was renamed "…System" →
"…Systems" at CS25-27 (PDF read), and its 16 provisions have only a CS25-5
version, so the app's view at CS25-27 shows "…System". `current_grouping`
is right, and the app merges the two names on the current page.

**To close:** accept it, or a document-level grouping list with names per
revision (a contract change; rejected for now in the review).

## Tables and extraction robustness

### EASA-17. Tables the geometry reader doesn't build

Extract now finds tables on every page from geometry (`cs_tables.py`,
tools/s00_docs/EASA_CS.md §Tables): ruled grids in the 2003-2012 PDFs and
shaded cells in Word 2016+ PDFs, written in flat form, joined over page
breaks with repeated headers dropped. That removed the spurious versions
(145@CS25-3, 397@CS25-27/28, 509@CS25-1/22/27, 511@CS25-1/22, R25@CS25-27,
E29@CS29-11/12) and 17 `suppress` plus 16 `replace_text` rows. Left:

- **Borderless tables** (no rules, no shading) still read as loose words, in
  column order where columns straddle the page centre: CS 25.851 (dot-leader
  rows, all versions), 807@CS25-12/18/19/26, 812@CS25-0/3/5/12,
  621@CS25-0/1, 1397@CS25-0, 1453@CS25-0, F25@CS25-0/2/4/27, and most
  CS-23/27/29 tables in the PDFs of 2003-2012. Emit compares versions on
  their plain words, so a version starting in such a PDF keeps its loose
  text until the next real amendment.
- **`table_unread`** (extraction report): grids with a figure or formula
  inside, kept as words: CS-23 A23, C23 (CS23-0..4), CS 29.815 (CS29-6..9),
  and a few figure frames (CS 25.331).
- **Sub-rows inside one cell**: a Word cell holding several lines
  (397(c) `Aileron: Stick / Wheel*`, 1435 item 2, 509's load numbers) is one
  cell; the lines aren't paired across columns.
- **Layout falls back to flat**: 143@CS25-13..27 and N25 (3 versions) hit a
  label sequence break, and flat text can't hold a table (structure report
  `table-flattened`). The 143 footnote marks `(1)`–`(3)` after the table are
  superscript in print. Written as `(N)`, layout reads them as labels, so
  they need `^{(N)}` or `no_break` rows.
- **Title-only change**: 1093's retitling at CS25-27 ("Powerplant Icing" to
  "Air intake system de-icing and anti-icing provisions") showed only
  because table noise made a version there. Emit doesn't version a title
  change on its own.
- Header rows of a ruled grid are marked only when a top-row cell spans
  rows; shaded tables mark them by fill.
- D27@CS27-10 is a version because the CS27-10 PDF leaves out Table I's
  `30–100 MHz | 50 | 50` row (CS27-9 and the CS-29 tables have it). It reads
  as printed. Whether that is a publishing omission (a `suppress` row) is
  the developer's call.

**To close:** a borderless reader (aligned word columns inside a body, or
dot-leader rows), or `replace_text` rows writing the table, for the
provisions above; then `^{(N)}` for the 143 footnotes.

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

### EASA-24. Control characters in CS-27 C27 at CS27-6

Garbled PDF extraction: the text reads `(See AC 29-2C Change \x1a dated
\x17\x03)HEUXDU\\\x03\x15\x13\x14\x19 and AMC material to CS–29)`. The search
index drops control characters, so this can't break a snippet, but the words are
wrong in `text` too. Found while building search (schema v12).

**To close:** correct the text with an override row, against the PDF.
