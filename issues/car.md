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
  no amendment brackets). It is a pattern: OCR reads a final `l` as `]`
  ("shal]", "contro]", "critica]") in 37 CAB and 6 CAA versions
  (`scripts/scan_data.py --check unbalanced-brackets --all`, 2026-11-12).
- Figure lettering spliced into a sentence (GitHub #20): CAB 173@CAR3R-0 has
  the V-n diagram's labels and caption inside "actual condi… tions". The
  `caps-run`, `gibberish` and `figure-caption` scan checks list the rest.

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

### CAR-5. OCR'd V-speed subscripts read as letters

CAR text is OCR with no geometry, so a subscript can't be told from the
letters around it: `Vu` and `Vd` for V_d, `Vy,` for V_p, `Ve min` for
V_c min, `V_.` (CAB §3.184 and many more), `Vs]` for V_s1 (CAA §3.111@CAR3-0,
GitHub #23). Only §3.159 (CAA and CAB) is fixed so far (GitHub #4).

**To close:** `replace_text` rows writing `V_{d}` etc., checked against the
scans (`input/Regs/CAR/3/CAR3R-*.pdf`, the CAA retype `CAR3-*_full.pdf`).

### CAR-6. 73 `TEXT MISSING` versions are untracked

CAR holds 73 of the dataset's 104 `TEXT MISSING` versions (CAB reissue 63, CAA
10, 2026-11-07), none with a `provenance_notes` reason, and no issue lists
them. 57 are reached by a certification basis: 51 CAB versions on 27 models
and 6 CAA versions on 16 models. The CAR parser emits the marker for a section
it can't find, so some may be parser misses rather than absent text.

**To close:** record why each is missing, then recover the text from the scans
with a parser fix or `replace_text` rows.

8 of them were whole-section deletions (CSV title "[Deleted.]"), now
`deleted: true` versions through `tools/overrides/car.tsv` (2026-11-11). One
"[Deleted.]" row is not a deletion: CAR3R-7 deleted only §3.681(b)
(`CAR3R-7.raw.txt`:863-864), so §3.681 at CAR3R-7 needs its amended text, and
`input/regs.csv` titles it wrongly. The emitter warns about it on every run.

### CAR-7. Section boundaries are wrong in sampled CAR texts

Found by the 2026-11-08 accuracy pilot (PROC-17), which read 20 CAR versions
against page images. 5 have a boundary or omission error:

- CAR3-0 §3.422: stops at "compliance with §". The rest of (b) and all of (c)
  are missing, about 70 words. A section reference at a line end looks like the
  cause.
- CAR3-0 §3.791: its body is the §3.792 heading and the AUTHORITY note.
- CAR3R-0 §3.735: holds §3.737 and its heading.
- CAR3R-2 §3.75 and §3.383: hold the amendment instructions that follow them.

Word-level OCR errors are also common in the CAR3R scans (8 of 10 versions).

**To close:** check how many versions share each cause, fix the splitter, and
use `replace_text` rows for the rest.

### CAR-8. cp1252 bytes in the CAA retype

48 CAA versions (42 at CAR3-0) hold C1 control characters where the source has
punctuation: `\x97` for an em dash (57 places, "Subpart B\x97Flight
Requirements"), `\x92` for an apostrophe ("pilot\x92s", 17), `\x93`/`\x94` for
quotes. The retype was decoded as Latin-1 instead of cp1252. Found by the
`encoding` scan check (2026-11-12).

**To close:** decode the CAA retype as cp1252 in the extractor, re-emit, and
rewrite the scan baseline.

### CAR-9. Tables of contents read into section texts

Reported from the site for CAA §3.652 (GitHub #21, "picking up the index").
The `toc-run` scan check finds a run of five or more rising section numbers
with titles in 18 CAA and 5 CAB versions (2026-11-12). The worst carry whole
subpart contents: CAA 270@CAR3-0 (262 entries, 3.271 to 3.780), 17@CAR3-3,
19@CAR3-12, 669@CAR3-7, 702@CAR3-14; CAB 301@CAR3R-0 (91 entries), 583@CAR3R-0.
The section splitter takes the contents listing that opens each subpart in the
scans as the end of the preceding section.

**To close:** make the splitter drop subpart contents listings, re-emit, check
the affected sections against the scans, and answer GitHub #21.

### CAR-10. NPRM cites are not recorded as actions

Several narrative amendments name the proposal they followed ("participate in
the making of this amendment (21 F.R. 3388)"): CAR3-13 (20 F.R. 369), CAR3-14
(20 F.R. 8350), CAR3R-1 (21 F.R. 3388), CAR3R-3 (22 F.R. 9116), CAR3R-5
(24 F.R. 128), CAR3R-7 (26 F.R. 5130). CAR versions carry no `actions`, so
these are dropped. Found 2026-11-13 while fixing the CAR publication cites
(the FR page of each final rule is now in `tools/overrides/car_cites.tsv`).

**To close:** emit them as `actions` of type `nprm` (reference the FR cite)
on every version of the revision, with the narrative line as evidence; check
the other narratives for the same sentence.

### CAR-11. CAA revision dates are adoption dates, not effective dates

`caa/car-3/_document.json` `effective_date` comes from the `Effectivity Date`
column of `input/regs.csv`. For 8 of 13 amendments that column is the
adoption date printed on the narrative PDF
(`input/Regs/CAR/3/CAR3-N.raw.txt`, "Adopted:" / "Effective:" header):
CAR3-1 (data 1949-11-02, effective 1949-12-07), CAR3-3, -8, -10, -11, -12,
-13, -14 (CAR3-14: data 1956-02-07, effective 1956-03-13). CAR3-5, -6, -7, -9
are one day early (CAR3-7: data 1952-03-04, "Effective: March 5, 1952"), and
CAR3-2 is a month early (1950-01-06 vs 1950-02-06). The CAB reissue mostly
matches (CAR3R-1, -3, -6 effective; CAR3R-4 is the adoption date; the rest have
no header to compare). Found 2026-11-13 while looking up FR cites
(F-20261112-05). The dates order revisions and decide which one a TCDS date
resolves to, so a basis dated between adoption and effectiveness picks the
wrong revision.

**To close:** take each revision's date from the narrative header (an override
column, or a CAR revisions table with evidence), check the reissue dates
against the FR text in `input/Regs/CAR/FR/`, re-emit, and check that TCDS
resolution doesn't change unexpectedly.
