# EASA TCDS (ETCDS-)

623 TCDS downloaded 2026-11-02 (650 files in `input/TCDS/EASA/`). The parser
(`s02_emit/easa/tcds/parse.py`) covers CS-23/25 aeroplanes only. Pipeline:
[tools/s00_docs/EASA_TCDS.md](../tools/s00_docs/EASA_TCDS.md). Handover:
[2026-11-03-easa-tcds-handover.md](../tools/s00_docs/reviews/2026-11-03-easa-tcds-handover.md).
Coverage: `uv run python -m tools.s02_emit.easa.tcds.coverage > /dev/null`.
Widening the scope (rotorcraft, noise TCDS) is ROADMAP-9. [Index](../ISSUES.md)

## Pending runs

### ETCDS-15. EASA TCDS citing FAR Part 36 that still don't resolve

Part 36 lines in the Environmental Protection field are now read, as are soft
hyphens, dotted dates and `App. G`. On the 2026-11-08 `data/`, these remain:

- No amendment to pick: A.026, A.056 (`14 CFR Part 36`), A.057, A.586
  (`FAR 36 Appendix F`), IM.A.352.
- A line that also cites Part 34 or 26, not in the dataset, so the whole line
  stays unresolved: A.187, A.089, IM.A.196.
- A.059: Part 36 followed by a CS 23.1529 sentence with no amendment.
- IM.A.162: "Aviation Regulations, Part 36, para 3". IM.A.352: serial-scoped
  lines naming Stage 4 "as amended by Amendment 36-1 through …" with no anchor.

**To close:** split composite lines so each citation stands alone (ETCDS-9
shape), and leave lines with no amendment unresolved.

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

### ETCDS-19. `_tcds.json` State of Design often holds the wrong field

`state_of_design` in the EASA fragments' `_tcds.json` (2026-11-12 parse) is
set on 137 of 594 TCDS. On about 30 it holds a neighbouring label or value,
not an authority: "Certification Application Date" (16, e.g. EASA.IM.A.228,
whose A.I.3 is the CAA of Israel), "Certification Basis", "Type
Certification", "5", "9", "Type Certificate MS 880 B: 26-October-1961". The
rest name the authority in many forms ("FAA", "Federal Aviation
Administration (US)", "Transport Canada Civil Aviation (TCCA)"). Nothing
applies it: it's evidence for link candidates only, and `_suggest_primary`
reads `validation`, not this.

**To close:** read the value of the State-of-Design field (A.I.3 "Certifying
Authority" on IM TCDS), not the next label; normalise to a country, then
check the 137 again.

### ETCDS-17. A category printed outside the model section is not read

The parser reads a model's category from its own section. Eight TCDS print it
elsewhere, in a general section ("2. Airworthiness Category: Large Aeroplanes":
A.096, A.192, A.407, IM.A.009, IM.A.162, IM.A.196, IM.A.211, IM.A.595) or in
prose (A.187 "certificated in Airworthiness Category Large Airplane under FAR
25", A.580 "large aeroplane category"). Rows in
`tools/overrides/tcds_categories.tsv` cover them since 2026-11-12, quoting the
text.

**To close:** read the general section's category field. The rows for those
TCDS then become stale (fatal) and are deleted in the same change.

## Decisions needed

### ETCDS-18. "As defined in CRI A-01, latest Issue, and below" is a regulation entry

12 lines in 7 EASA TCDS (whole-corpus run, 2026-11-13, by regex), e.g.
EASA.IM.A.042 Issue 9 A.II.4 "Certification Basis: As defined in CRI A-01,
latest Issue, and below". They are typed `regulation` with no references, so
they count as unresolved, though they point at a certification review item
that isn't published and add nothing the lines below don't state.

**To decide:** type them `other` corpus-wide (a parser rule in
`items.entry_type_for`, not one row per TCDS), or keep them as unresolved
regulation lines.

### ETCDS-16. A330 lines cite all of CS-25

Found on 2026-11-08 by reading a sample of aircraft references against the TCDS
PDFs. EASA.A.004 Issue 70 (A330), 2 models:

- 15 entries reading "Plus the following CS 25 paragraphs applicable at Amdt N" are
  headers for the paragraph list on the next line. The parser reads each as a
  whole-document reference, so the model resolves to all of CS-25 at that amendment.
  The listed paragraphs sit in a following entry with `references: []`. The build
  and coverage report both count this as a success.
- (Fixed 2026-11-12: the page footer `Issue: 70 [A330-743L] Date: 30/10/2026`
  is page furniture, and the "- Certification Requirements" heading is a scope.)

In the same sample, 8 of 400 `raw_reference` values were not found verbatim in the
PDF with either text extraction. All 8 are EASA, and most join table cells or
columns (see ETCDS-9). Sampled FAA references matched their PDF lines.

Since 2026-11-12 the headline guard (`tools/s00_common/tcds_guard.py`) refuses
a model with whole-document references to one airworthiness document at two
levels, so these models are no longer staged (published `data/` still holds them
until the next promotion). The guard refuses the same shape on 6 more models,
judged from `raw_reference` only, not read against the PDFs:

- EASA.IM.A.033 680A: "a) CS-25 Amendment 2", "b) CS-25 Amendment 4", … each
  read as all of CS-25, each followed by a "CS 25 paragraphs Applicability"
  table.
- EASA.IM.A.348 G280: "For steep approach landing modification (G25-10059) CS 25
  Amendment 13, Appendix Q" as all of CS-25.
- EASA.IM.A.595 GVII-G500, GVII-G600: "CS 25 Appendix S, Amendment 19" and "CS 25
  Appendix Q Amendment 13 (for Aircraft with ASC 014 …)" as all of CS-25.
- EASA.A.187 C-212-EE: "For model C-212-EE: For FMS, IEDS and EFIS, FAR Part 25 …
  25-87" as all of Part 25 for the whole aeroplane.

Same cause, not caught (same level as the headline): EASA.A.637 P2012 "CS-23
Amdt.4 § 783(d)(e)" and its neighbours each carry a whole-CS-23 reference.

**To close:** attach a "the following paragraphs" header to its list, read a
section or appendix named on the line as the scope, re-check the TCDS above
against their PDFs, and stage them again.
