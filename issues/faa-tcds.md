# FAA TCDS and aircraft (TCDS-)

FAA TCDS parsing into `data/aircraft/`. Pipeline:
[tools/s00_docs/FAA_TCDS.md](../tools/s00_docs/FAA_TCDS.md). Aircraft
overrides: `tools/overrides/aircraft_links.tsv`, `aircraft_holds.tsv`.
[Index](../ISSUES.md)

## Pending runs

### TCDS-12. Part 36 lines the re-parse left without references

The re-parse landed in b3ca90c: 69 models and 88 entries gained `references`.
On the 2026-11-08 `data/`, these FAA lines still cite Part 36 and have none
(16 entries, more than the 7 first listed):

- No amendment to pick: "FAR 36 as amended on the date of certification"
  (A00003SE, 4 models), and the PC-12 open range "Amendments 36-1 through
  amendment in effect at the time of U.S. Type Certification" (A78EU, 2).
- Composite lines that do name an amendment: A25SO PA-46-310P and -350P (2 on
  -350P), -500TP ("FAR 36, Appendix G, Amendment 36-22"), -600TP, -701TP,
  PA-46R-350T, and A00007SE Kodiak 100.
- A37CE 208: two Part 36 notes sit inside an entry typed `special_condition`.

**To close:** leave the first group at `references: []` unless a rule for
"as amended on the date of certification" is agreed. Fix the rest in the parser
or through TCDS-2.

## Parser gaps

### TCDS-14. Model heading numerals that skip a value

After the 2026-11-11 heading fixes, 22 aircraft TCDS still have numerals that
skip, run backwards or start after I (engine TCDS left out). The sequence
guard refuses the model before each gap, so a missed heading can't merge into
it, but each case needs reading: either a heading shape the parser still
misses, or a TCDS that really numbers that way.

- Start after I: 1A14 (III), A-655, A-675, A-787, H5NE, TC_1 (II), H9SW (IV).
- Skip: 1H15 I→III, 2A3 XIV→XVI, 3A23 XXXVIII→XXVIII, 4A21 IV→II, 4A26
  II→IV, 7A14 XII→XIV, A14SO XXII→XXV, A17WE I→IV, A1NM I→III→V→VII, A1PC
  III→VI→V, A21EA-1 V→VII, A2PC IV→I, A43NM II→IV, A16EU II→I, T00003NY II→VI.

None is in `faa_tcds_selection.tsv`. Scan: run `find_model_headings` /
`numeral_gaps` over `pdftotext -layout` text of `input/TCDS/FAA/`.

**To close:** read each against its PDF; fix the parser for real heading
shapes, and leave a true numbering to the guard's warning.

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

Narrowed 2026-11-11: headings with no separator, a deep indent, a dated
model list or a page-top repeat are now read, and a cover "737-300 Series"
matches heading "737-300" (A16WE: 16 unmatched to 0). The counts above
predate that.

Re-count of the category skips, 2026-11-12 (939 Current aircraft TCDS, by
regex, not read): 600 models in 236 TCDS had no category on the heading. 94
(about 45 TCDS) print one elsewhere that the parser misses, e.g. A28NM "I.
Type A318-100 Series Transport Category Airplanes", A21NM a wrapped "Transport
Category", 4A21 "(Transport Aircraft)". 383 (100 TCDS) print none but cite a
Part: 255 of them are balloons (Part 31, no category in the closed set), 10
21.17(b) special class. 123 (89 TCDS) show nothing detectable (gliders, pre-CAR
3 types). A category no TCDS prints now needs a reviewed row in
`tools/overrides/tcds_categories.tsv` (A2NM has one); it is never inferred.
Detail: `reviews/2026-11-12-multi-model-blockers.md` Q1, in git at acadefc.

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

### TCDS-15. Part 26 compliance outside the basis blocks is not attached

Eight TCDS print the §21.101(g) statement that "applicable provisions of 14 CFR
part 26 are included in the certification basis" outside their basis blocks
(A20EU, A21EA, A2NM, A56NM, A57NM, A58NM, T00011AT, T00063IB; 18 more print it
inside one). A2NM p. 7: "Compliance with 14 CFR §26:" in "Data Pertinent to All
Models", with compliance at 26-0 (26.11), 26-1 (26.43, .45, .47, .49) and 26-3
(26.33). Counted by a text scan; only A2NM read. Part 26 isn't in the dataset
(TCDS-13), so attached lines would have no references.

**To close:** read the eight, then treat a field label naming Part 26 in an
all-models section as a basis block for that section's models. Not a general
"included in the certification basis" trigger: A2NM Note 16 uses the same words
for an optional basis that must not be attached.

### TCDS-16. A paragraph excluded from the basis can't be expressed

An `exclude` reference takes no `paragraph` (docs/DATA_FORMAT.md). A2NM 757-300
"25.858(a) Cargo Compartment Fire Detection System — not part of the TC basis":
the row stays visible with `references: []`, and the headline "Part 25 …
through 25-85" still holds 25.858 (the 25-54 version) with (a) in it. Decided
2026-11-12: accept for now, since the resolved grain is the provision version
and (b)–(d) do apply.

Other paragraph-level "not part of the basis / not applicable / does not apply /
except (x)" lines found by text scan, not read: A21EA, A-817, A14EA, A1NM
(25.803(c)(8)), A20WE (25.1103(d)), A21EA-1, A28NM, T00001SE (25.812(g)),
A16WE ("25.807 (except (g)) 94"), A46EU, A77EU, H1NE. Some give the paragraph
another level rather than excluding it. None is resolved in `data/` today.

**To close:** when a case changes something a user filters on (or at the 737 NG,
A16WE), read these lines and decide on a contract change (exclude with a
paragraph: schema, `certbuild/resolve.py`, a `cert_basis_resolved`
representation, `SCHEMA_VERSION`, the app).

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
TCDS in `tools/overrides/faa_tcds_selection.tsv`).

**To close:** an `aircraft_links.tsv` row per pair if it is one type design,
else a holder/designation difference from the TCDS. List them with `uv run
python -m tools.s02_emit.aircraft.assemble`.

### TCDS-13. Most regulation lines on aircraft have no references

From the 2026-11-07 build, FAA and EASA together:

- 1,330 of 1,850 `regulation` entries have no `references` (FAA 315 of 560,
  EASA 1,015 of 1,290). Some are fragments, so this is an upper bound.
- 97 of 325 models resolve to no provision at all, including 24 of the 51
  Transport models. 114 of 358 TCBs have no reference (111 of them EASA).
- 14 CFR 27, 14 CFR 29, CS-27 and CS-29 are referenced by no aircraft
  (ROADMAP-9, ROADMAP-10).

Causes seen in a sample:

- Documents not in the dataset: JAR (34 of the 114 TCBs cite it; ROADMAP-3
  ranks it low), BCAR, 14 CFR 34.
- Cross-references to another field ("As per para. A.II.5").
- Date-and-amendment prose ("FAR Part 23, effective 1 February 1965, as amended
  by …").
- Basis lines split where they wrapped ("February 1965, Amendment 23-1 thru
  23-31").

**To close:** count each line by cause, fix the causes in order of models
gained, and report what is left (BUILD-12).
