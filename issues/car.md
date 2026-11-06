# CAR 3 (CAR-)

CAR 3 (CAA editions) and the CAB CAR 3 reissue, OCR'd from scans. Fixes are
`replace_text` overrides checked against the scans, or extractor rules.
[Index](../ISSUES.md)

### CAR-1. OCR-damaged and out-of-sequence labels leave texts flat

- CAB CAR 3 reissue (24 sections): `(bo)`/`(ob)` for `(b)`, `(ce)`/`(ec)` for
  `(c)`, `(ad)`, `(0)`. Sections 109, 115, 123@R7, 124 (R0, R7), 171, 185,
  197@R2, 222, 225, 233, 550@R2, 625, 667, 700, 745, 75, 767, 771, 778, 780
  (R0, R7), 82, 84.
- Sequence breaks (16): e.g. 3.655 at CAR3-0/2/10 and CAR3R-0, 3.6, 3.437,
  3.667.

**To close:** `replace_text` overrides for each label, checked against the
scan.

### CAR-2. "NOTE: The following interpretation …" paragraphs are editorial

They are not regulation text, but read as part of the paragraph before them
(see TEXT-8).

**To close:** decide whether to mark them (a note boundary) or leave them.

### CAR-3. OCR junk at the end of CAR 3 texts

Left behind after the next group's centre heading was stripped:

- Narrative amendment instructions read as text: CAB 211@R2, 686@R3 ("By
  adding a new heading and … to read as follows:"), 587@R7 ("By amending
  § 3.682 and the center heading …").
- Column-bleed fragments: CAB 681@R0 "e in excess", 256@R0 "Limit force"; CAA
  596@CAR3-0 "ith at least two separate air intake", 747@CAR3-0 "‘termined by
  the availability and".
- CAA 188@CAR3-0 has OCR garbage from Fig. 3-2 in front of its caption
  (figure captions are kept on purpose).
- CAB 318@R0 "shall]": a stray bracket, probably OCR (the 1956 reissue prints
  no amendment brackets).

**To close:** `replace_text` overrides or an extractor rule, checked against
the scans.

### CAR-4. CAB 3.304@CAR3R-7 castings table is OCR-damaged

The table in (b) is flattened with OCR errors ("vusuai"), `{e)` should be
`(c)` (so (c) is lost and (d) shows as a gap), and amendatory text of the next
sections ("§3.304-1 [Deletion] 21. By deleting…") is appended to (d).
Sources: `CAR3R-7.raw.txt`:636-720, column layout in `CAR3R-7.txt` around
line 340.

**To close:** `replace_text` rows (label, trailing text) and the table in its
flat form.
