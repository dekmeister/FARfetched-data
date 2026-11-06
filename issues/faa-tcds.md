# FAA TCDS and aircraft (TCDS-)

FAA TCDS parsing into `data/aircraft/`. Pipeline:
[tools/s00_docs/FAA_TCDS.md](../tools/s00_docs/FAA_TCDS.md). Aircraft
overrides: `tools/overrides/aircraft_links.tsv`, `aircraft_holds.tsv`.
[Index](../ISSUES.md)

## Pending runs

### TCDS-12. Re-parse the FAA TCDS that cite Part 36

Part 36 is in `data/`, but no FAA-sourced model references it yet (only 7
EASA-sourced models do). A trial on the 21 FAA TCDS behind `data/aircraft/`
showed 19 TCDS, 69 models and 88 certification-basis entries gaining
`references`, with no other change.

Lines that cite Part 36 and still need a human (7 entries):

- "FAR 36 as amended on the date of certification" (A00003SE, 4 models).
- The PC-12 open range "Amendments 36-1 through amendment in effect at the
  time of U.S. Type Certification" (A78EU, 2).
- "FAR 36, Appendix G, Amendment 36-22" inside a composite line (A25SO
  PA-46-500TP): scope it to Appendix G@36-22.

**To close:** run the FAA parser over the 21 PDFs, `aircraft.assemble`,
review, `promote --aircraft` (TCDS list: TCDS-11); then decide the 7 lines.

## Parser gaps

### TCDS-1. Cirrus-style "additions" layered on a base line

A00009CH SR20/22/22T and others. The scoped additions ("For aircraft
equipped with Garmin G1000 …: 14 CFR 23.1308 thru Amendment 23-57") are
separate entries, with the equipment/serial scope as verbatim
`applicability`. Options: (a) keep that; (b) structured applicability
(ROADMAP-5); (c) an entry-level "supersedes entry N for scope S" link.

**To close:** a decision, before Cirrus is promoted.

### TCDS-3. A designation appears twice on one TCDS

A19SO `PA-44-180`, A37CE `208B`; 49 TCDS in the corpus. Such models are not
staged. Some are continuation pages repeating a multi-model heading (A3EU).

**To close:** a merge rule (two `tcb` entries, or one list with scoped
`applicability`) or a merge per TCDS.

### TCDS-4. EASA CS-23 citations on FAA TCDS are unresolved

A57CE DA 62 (17 lines, "Significant Regulatory Differences … CS-23"). The
interpreter reads CS forms, but `CS 23.573 Damage tolerance … (CS 23,
amendment 2)` (title then a trailing amendment) comes out `partial` (12
lines). The "equivalent to 14 CFR Part 23 … through 23-55" line stays FAA.

**To close:** teach `tcds_refs` the trailing `(CS 23, amendment N)` form and
re-parse A57CE.

### TCDS-5. Cover models not matched to headings

397 TCDS and 1,151 designations (as of 2026-11-01), e.g. 1A2/1A4 PA-18/PA-20
variants, 1G1/1G10, 1H11. Top skip reasons: no category on heading 227, no
certification basis 153 (+45), no model headings 65, zero entries 11.

**To close:** work through the skip reasons before the parser runs wider.

### TCDS-6. 3A12 "Equivalent Safety Items" header-row serials

17261445, 17261578, 17265685 are applied to both items under the row. It
isn't clear whether they scope both items or only the airspeed one.

**To close:** check the PDF when the 172 is reviewed.

### TCDS-7. Citation 525-family parse gaps

- Serial applicability isn't picked up when combined with an "except the
  following paragraphs applicable for Engines and FADECs" list, or with
  non-contiguous serial sets ("525-0600 thru 525-0684, 525-0686 thru
  525-0701").
- Several ELOS in one line aren't split (525B display 21 holds ACE-00-01A plus
  two others).
- Sub-paragraphs (4a/4b, 6.a.1/6.a.2) should usually be separate entries.
- The 525 "Additions" tables aren't parsed.

**To close:** parser fixes, checked against
`data/aircraft/textron-aviation-inc/525*.json`.

### TCDS-8. `tcds.source_url` is not filled for FAA TCDS

**To close:** fill it in the FAA parser.

### TCDS-9. Restricted-category TCDS without a certification-basis field

Air Tractor A17SW; 7 of 201. Reported and not staged; the schema can't
represent them, by decision.

**To close:** revisit only if they are wanted.

## Process

### TCDS-2. There is no correction path for aircraft entries

Documents get `replace_text` overrides; aircraft entries have none. The two
aircraft override files (`aircraft_links.tsv`, `aircraft_holds.tsv`) link or
hold models but don't correct an entry, so a wrong parse can only be fixed in
the parser.

**To close:** decide whether aircraft need a correction override TSV
(probably no schema change) before running the parser wider.

### TCDS-10. Path collisions when the parser runs on the whole corpus

On a whole-corpus run, `aircraft.assemble` staged 1,446 of 1,470 fragments: 24
collide on path because the same designation appears under two TCDS
(PA-36-285/-300/-375 on A9SO and A10SO; OH-13H on H5SW/H7SW). `assemble`
fails loud and leaves them unstaged. Not visible today (the staged set is the
21 TCDS of TCDS-11).

**To close:** an `aircraft_links.tsv` row per pair if it is one type design,
else a holder/designation difference from the TCDS. List them with `uv run
python -m tools.s02_emit.aircraft.assemble`.

### TCDS-11. Which FAA TCDS are staged is chosen by hand

`assemble` stages every fragment under `tools/out/derived/tcb/`, so the
aircraft set is whatever PDFs the FAA parser was last run on: the 21 TCDS
behind `data/aircraft/`, passed one by one. A full `input/TCDS/FAA/` run would
stage ~1,450 files. This breaks the "one offline command rebuilds it" rule.

**To close:** record the selection as data (a TCDS list in
`tools/overrides/` or the catalogue) that the parser or assemble reads.
