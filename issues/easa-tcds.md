# EASA TCDS (ETCDS-)

623 TCDS downloaded 2026-11-02 (650 files in `input/TCDS/EASA/`). The parser
(`s02_emit/easa/tcds/parse.py`) covers CS-23/25 aeroplanes only. Pipeline:
[tools/s00_docs/EASA_TCDS.md](../tools/s00_docs/EASA_TCDS.md). Handover:
[2026-11-03-easa-tcds-handover.md](../tools/s00_docs/reviews/2026-11-03-easa-tcds-handover.md).
Coverage: `uv run python -m tools.s02_emit.easa.tcds.coverage > /dev/null`.
Widening the scope (rotorcraft, noise TCDS) is ROADMAP-9. [Index](../ISSUES.md)

## Pending runs

### ETCDS-15. EASA TCDS citing FAR Part 36 don't resolve it

11 EASA TCDS cite FAR Part 36. Only IM.A.013 (2 models) resolves to it in
`data/aircraft/` (2026-11-07); EASA.A.026, .056, .057, .059, .089, .187, .586
and EASA.IM.A.162, .196, .352 (35 models) don't. A.089 (PC-12) also has the
open range of TCDS-12.

**To close:** re-run the EASA parser on these, check why the Part 36 lines
stay unresolved, assemble, review, `promote --aircraft`.

## Sources

### ETCDS-1. Only the current issue exists, locally and upstream

EASA replaces files in place, so `input/TCDS/EASA/` is irreplaceable.

**To close:** back it up (see PROC-10) and re-run the downloader
periodically to build up history.

### ETCDS-2. 29 TCDS have no downloadable file

Mostly withdrawn or transferred (catalogue `role=none`):

- Scheibe gliders (A.100–A.107, A.577, A.578)
- CEAPR DR series (A.510, A.551, A.552)
- BAC 1-11 and Slingsby T67
- SZD/IS gliders (A.441, A.446, A.452, A.454)
- Gulfstream IM.A.002/IM.A.016
- Hughes 369HS, EH 101-300, Viper, FLAIR-2, Schroeder, Lindstrand HS-110
- A.022/A.629 ("Transferred to outside EU")

**To close:** only if one is needed, from another source.

### ETCDS-3. 4 scanned PDFs were OCR'd

A.200, IM.A.343, IM.E.077, P.016. Header and ID text is unreliable
(`[M.E.077`, `O1`, `Lid.`), and IM.A.343 says "Page 1 of 7" but has 8 pages.

**To close:** a parser of these must check OCR'd codes and numbers against the
PDF.

### ETCDS-4. `EASA.BA.025_Issue3.pdf` is not a TCDS

It is a revocation notice that the catalogue labels `main`.

**To close:** skip it in the parser (or relabel it in the catalogue).

## Parser gaps

### ETCDS-6. Shared basis sections are not attached to models

A section titled "General (All Models)" / "Data pertinent …" that holds a
certification basis (IM.A.071, IM.A.080, IM.A.188; reported as a warning) is
skipped, so its models get only their own section's entries, or none.
EASA.A.010 (TBM 700): Section A "GENERAL (ALL TBM700)" holds the basis and
Section B lists TBM700 A … N in one section, so nothing is staged and FAA
A60EU stays FAA-only.

**To close:** a rule for inheriting a shared basis and for which models it
covers.

### ETCDS-7. Series sections are not split into models

42 TCDS, e.g. A.004 A330, A.015, A.064, IM.A.196 747-400, IM.A.229 EMB-110
"(ALL VARIANTS)". Reported "several models in one section"; nothing staged.

**To close:** read the model list (1.2 Models/Variants, the cover's "For
Models") and a rule for per-model scoped lines.

### ETCDS-8. 12 in-scope models refused as implausible designations

A.004 `Passenger Models:`; A.182 `BAe 146 Model` / `AVRO 146-RJ Model`;
IM.A.001 `EMBRAER ERJ 170-100 VARIANT` / `-200 VARIANT`; IM.A.003 `(-200
VARIANT)`, `(- 300ER VARIANT)`, `(- 200LR VARIANT)`, `(F Freighter VARIANT)`;
IM.A.035 `767-300BCF (Major Design Change)`; IM.A.171 `EA500 DESIGNATION`;
IM.A.643 `CL-215-6B11 (CL-215T Variant) (Restricted Category)`. Each is a
layout the designation reader doesn't know (variant tables, "MODEL X
DESIGNATION" titles).

**To close:** fix per layout; the guard stays.

### ETCDS-9. Table-shaped basis fields split badly

3-column SC / ESF tables (Dornier A.096) come out as one entry per wrapped
row, and cross-field tables ("as per D.II.2 as amended by:") become separate
entries, like the FAA "additions" in TCDS-1.

**To close:** parse these tables as tables.

### ETCDS-10. PC-12 paragraph letters are unread

EASA.A.089 rows such as `23.305 a (23-45)` (a letter without parentheses)
resolve without the paragraph or come out `partial`.

**To close:** accept the bare-letter form in the interpreter.

### ETCDS-11. Environmental sub-labels fold into the field label

"Environmental Protection … Noise: …": the `other` entry starts with the
sub-label. Cosmetic, but `raw_reference` should start at the value.

**To close:** split the sub-label off.

### ETCDS-13. "basis cites no CS/JAR/FAR 23 or 25" misses indirect bases

76 TCDS, many correctly (sailplanes, CS-22). Some are aeroplanes whose basis
points elsewhere ("same as …", A330-941 in A.004, L-410).

**To close:** distinguish the two before trusting the out-of-scope count.

## Decisions needed

### ETCDS-12. Transport is inferred when no category is printed

49 staged models (e.g. SAAB 340/2000 A.068/A.069, Dornier 328 A.096, CN-235 /
C-295 A.186, C-212 A.187): a Part 25 basis gives `transport`, with a report
note.

**To close:** confirm this is acceptable, or require a printed category.

### ETCDS-14. Link decisions to review

`tools/overrides/aircraft_links.tsv` (33 rows, 2026-11-03):

- DA 40 (A47CE / IM.A.022) and DA 62 Inc (A00012NY / IM.A.629): the State of
  Design is TCCA, which has no TCDS here; FAA was taken as primary (same path
  either way).
- DA 62 on A57CE (GmbH, the EASA.A.005 derivative) is not linked to IM.A.629:
  a different TC (A00012NY Note 9).
- DA 42 (EASA.A.005 primary): `manufacturer` becomes the EASA cover's
  `DIAMOND AIRCRAFT INDUSTRIES GMBH` (was FAA's mixed case).
- LC42-550FG: EASA.IM.A.516 gives the FAA TC date as 30 March 2003; FAA
  A00003SE says May 30, 2003.

**To close:** the maintainer confirms or changes each row.
