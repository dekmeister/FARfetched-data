# Data findings log

Inbox of data problems found by the `promote-staged` and `audit-data` skills,
waiting for triage. Triage moves each entry into `issues/<area>.md` (or a
GitHub issue), fixes it, or dismisses it, then deletes the entry here. Each
finding is a lead read by a subagent against the local source copy; confirm it
against the source before acting. Delete this file when it is empty.

## 2026-11-12 audit-data (seed 949374)

- **Scope:** 80 provision versions from 13 documents (faa/23 6, faa/25 6,
  faa/27 6, faa/29 7, faa/36 6, easa/cs-23 7, cs-25 6, cs-27 6, cs-29 6,
  caa/car-3 6, cab/car-3-reissue 6, nato/stanag-4671 6, dod/mil-hdbk-516 6),
  20 TCDS (10 FAA, 10 EASA). Focus: none. 0 versions without a local source.
- **Reading:** 102 items read by 17 Sonnet subagents (readers added 2 items
  outside the sample: faa/36 36-8 and the pc-12 FAA A78EU block; both are
  counted). Nobody could not-check an item. One medium-confidence blocker
  (F-20261112-02 CAR3-0 §576) went to a second reader, who confirmed it, but
  both readers had compared it with the wrong document (dismissed 2026-11-13:
  `sample.py` gave CAR3-0 items the 1945 Part 03 scans). Nothing
  below is "verified" beyond what a reader checked against the source; the
  readers mostly used pdftotext / cached DRS HTML, not page images.
- **Result:** 13 blocker, 61 major, 46 minor findings in 43 of 102 items
  (59 ok; "ok" includes items whose only finding is source-faithful). Per
  document (items ok / with issues):

  | Document | ok | issues |
  |---|---|---|
  | caa/car-3 | 1 | 5 |
  | cab/car-3-reissue | 2 | 4 |
  | easa/cs-29 | 2 | 4 |
  | easa/cs-25 | 3 | 3 |
  | easa/cs-23 | 5 | 2 |
  | faa/36 | 6 | 2 |
  | faa/23, faa/25, faa/27 | 5 each | 1 each |
  | dod/mil-hdbk-516 | 5 | 1 |
  | easa/cs-27, faa/29, nato/stanag-4671 | all ok | 0 |
  | **TCDS (20)** | 1 | 19 |

  Provisions: about 29% of items have a defect. The old CAR 3 texts (OCR,
  wrong revision, section boundaries, publication_cite) are worst, then EASA
  CS-29 and formulas anywhere. TCDS: 19 of 20 have a defect, but nearly all
  are `references: []` and line-split/typing problems, not wrong text
  (`raw_reference` matched the source in every line a reader compared).
- **Automated (whole tree):** `build.py --check` clean. First audit run, so no
  earlier counts to compare with. `scan_data --all` 2425: regulation-no-refs
  1174, cite-suspect 184, length-jump 178, duplicate-paragraph 153,
  label-gap 128, short-text 107, duplicate-line 106, text-missing 96,
  length-drop 75, no-source-url 73, heading-in-text 48, title-suspect 36,
  same-as-previous 29, split-amendment 21, runaway-line 14,
  amendment-unreferenced 3. `checks.py` 3166: split-word 738,
  dropped-symbol 408, formula-glyphs 405, stray-symbols 223, stray-braces 207,
  amendment-text 219, figure-caption 201, caps-run 141, private-use 98,
  encoding 92, dot-leaders 64, scrambled-equation 63, lowercase-start 58,
  truncated-end 54, unbalanced-brackets 47, numeric-run 33, toc-run 30,
  basis-list-header 20, basis-footer 18, basis-heading 18, trailing-heading 17,
  literal-escape 6, gibberish 3, vspeed-ocr 2, ocr-label 1. Sample hits:
  146 leads. Real-defect leads: cite-suspect (CAR publication_cite, 3 of 4
  confirmed), label-gap (25.795 run-together labels, CAR3R-0 `(bo)`),
  length-drop on CAR3R-5. False positives: length-drop on 23.959 and 29-17,
  length-jump on MIL-HDBK-516, title-suspect on 36-16, duplicate-paragraph on
  29.1521 and 25.903(c) (source repeats).
- **Reader plumbing note:** the batch `extracted` paths for CS-27/CS-29
  items pointed at cs-23/cs-25 files; `sample.py` has a lookup bug (data is
  fine).

### F-20261112-01 · blocker · formula · scrambled or missing display formulas

Formulas read in row order, or lost entirely because DRS has them as images.
Row order: `easa/cs-29/1401.json` CS29-0 (effective intensity, also a
flattened (f) table), `easa/cs-25/562.json` CS25-17 (HIC), `easa/cs-25/335.json`
CS25-0 and CS25-27 (V_B gust formula, K_g and μ fractions). Missing images:
`faa/36/F36.json` 36-16 ("following formula: Where: D_{50}…" with no
equation), `faa/23/443.json` 23-34 (gust load, K_gt, μ, c̄), `faa/27/B27.json`
27-44 (V_Y, V_NE, V_MIN IFR symbols gone: "utilized instead of for
compliance", "trimmed at ;"; 27-19 probably the same), `faa/25/795.json` 25-145
("sphere of diameter (where H_{0}…").
- Data: `faa/27/B27.json` 27-44: `means instrument climb speed, utilized instead of for compliance`
- Source: DRS `<img>` GIF symbols in the SectionRule HTML (cached DRS JSON)
- Suggested area: already ISSUES TEXT-11 (display formulas), FAA-30 (image-only symbols)
- Promotion: n/a

### F-20261112-06 · major · structure · texts that are one flat line

`easa/cs-25/335.json` CS25-27 (7068 chars, no newlines), `easa/cs-23/729.json`
CS23-0, `caa/car-3/655.json` CAR3-2 (equipment table), `caa/car-3/44.json` CAR3-0 (definitions, also a
"Reference sections" column header run into the text). Also run-together
paragraphs: `faa/25/795.json` 25-145 ((c), (e), (f) mid-line),
`faa/36/201.json` 36-8 ((a)/(b), (3)/(c); source has `<br>`), `faa/36/F36.json`
36-16 (section headings ` Sec. F36.103` run onto the previous paragraph, TOC
read as text), `easa/cs-29/1457.json` CS29-11 and `easa/cs-23/729.json` (heading
note `(See AMC 23.729 (g)` with unclosed paren).
- Suggested area: already ISSUES TEXT-6, TEXT-8, TEXT-12, CAR-9 (TOC in text)
- Promotion: n/a

### F-20261112-07 · major · ocr · EASA CS spaced-out words

`easa/cs-29/1401.json`, `1337.json`, `1363.json` (CS29-0): "cert ification",
"m ore", "p owerplant an d", "usi ng". The source PDF text layer has the same
gaps (the rendered page reads normally), so the data copies the source but
the text is wrong for a reader. Unmarked V-speed subscripts too: `VSI` for
`VS1` in `easa/cs-23/161.json` CS23-0 (source layer), and only 22 of 449
CS-23 files use `V_{`.
- Suggested area: already ISSUES EASA-11 (letter-spaced text)
- Promotion: n/a

### F-20261112-09 · blocker · tcds-lines · TCDS lines dropped or split

`aircraft/honda-aircraft-company-llc/ha-420.json` (FAA A00018AT rev 11): six
ELOS lines dropped (ACE-15-09, -10, -11, -15, AT15774AT-A-F-1,
AT16447AT-A-A-1; only ACE-15-08 kept); the drawing line split so only "later
FAA approved revision." survives; operational statements (VFR/IFR, ditching,
icing, RVSM, steep approach) dropped; ELOS/SC table columns interleaved.
Split mid-list at page breaks: pa-46-500tp #3/#4/#5, pa-44-180t line #5
starts mid-block, aviat a-1a #1/#2 split at "1. February 1965", pc-12 ICAO
Annex 16 line, textron 4000 #38 swallows the next elect-to-comply line.
- Suggested area: issues/faa-tcds.md (TCDS-)
- Promotion: n/a

### F-20261112-11 · major · tcds-entry-type · wrong entry types, categories and applicability

skycar: item 9 Equivalent Safety Findings and `CRI E-02 (ESF)` typed
special_condition; CS-36 / ICAO Annex 16 typed special_condition (should be
`other`). Categories lost: `z-43` (Normal and Utility, data normal),
`siat-223-a1` (Normal and Utility, data normal), `g-120tp-a` (Utility and
Aerobatic, data utility; schema has no aerobatic). S/N applicability dropped
(null) though the source has `S/N … and On`: tu206a (FAR 36, 23.1545),
ha-420 (Part 36 lines, SC 23-287). da-62 `DAI elected` sibling lines get
different `entry_type`.
- Suggested area: already ISSUES ETCDS-17 (category outside model section); otherwise issues/easa-tcds.md and issues/faa-tcds.md
- Promotion: n/a

### Check candidates

Each is a pattern a script could find across the whole tree.

For `scripts/scan_data.py` (provision text and metadata):
1. **Flat text:** a version with 3 or more `(a)`, `(b)`, `(c)` style labels and
   0 newlines. Catches CS25-27, CAR3R-85, CAR3R-109, CS23-729, CAR3-2 (655).
2. **Missing image formula:** `following formula:` or `computed as follows:`
   directly followed by `Where`/`where--` with no equation; `of for`, ` at ;`,
   a leading ` = ` with an empty symbol; a paragraph ending mid-clause such as
   `diameter (where`. Catches 36-16, 23-34, 27-44, 25-145.
3. **Scrambled formula:** `⎡ ⎢ ⎣ ⎧ ⎪ ⎫ ⎬` glyphs in text, or `0 ⋅ 2`, `∫ I(t)dt`
   remnants outside a `$$…$$` block. Catches CS25-17, CS25-27, CS29-1401.
4. **Authority text in `publication_cite`:** the field contains `By the Civil
   Aeronautics Board`, `Secretary`, `(SEAL)`, `/s/`, `last printed`, starts
   with `(Secs.`, or contains `U.S.C.`. Catches CAR3-9, CAR3-13, CAR3-2, CAR3R-5.
   Not needed: checks.py `cite-suspect` already flags these (it found all 184).
   F-20261112-05 is fixed: CAR cites now come from FR issues
   (`tools/overrides/car_cites.tsv`).
5. **Text fragment from another amendment:** text opening with `* * *` or
   containing `By amending §` (CAR3R-5).
6. **CAR OCR junk tokens:** `\bV;`, `Vs,[’”]`, `V:z`, `\(ce\)`, `\(bo\)`, `\$§`,
   `shal\]`, `Janding`, `fiaps`, `Gi\)`.
7. **Merged sections:** a raw `§3.NN[a-z]? Title` heading inside a CAR text
   (CAR3R-85 swallowed 85a). A section file that is TEXT MISSING while its
   neighbour's text contains the missing section's heading.
8. **Run-together labels:** a paragraph label such as `(c) An airplane` or
   `(e) Exceptions.` mid-line after a sentence-ending period; ` Sec. F36.` or
   ` Sec. <letter><digits>.` inside a line (appendix headings run in).
9. **Spaced-out words (EASA):** three or more `\b[a-z]{1,2} [a-z]{2,}` splits
   from a known-word list (`m ust`, `t he`, `sam e`, `cert ification`) in one
   version. Catches CS29-1337, 1363, 1401. Related to the existing
   `split-word` (738).
10. **Unclosed leading note:** EASA text beginning `(See AMC ` with an unclosed
    parenthesis (CS23-729).
11. **Image placeholder in DRS HTML:** any `<img` inside a SectionRule is a lead
    for a dropped formula or symbol (check at the extractor, then per file).
12. **Table flattening:** a long line with `Reference sections` or other
    column headers run into the text (CAR3-0 44).

For `scripts/scan_data.py` or `checks.py` (TCDS aircraft files):
14. **Page furniture as a line:** a basis line matching `^EASA Form NR \d+ CS-\d+`,
    a bare model name (`^A-1A$`, `^Z 43$`), or `^See Note \d+$`.
15. **Item numbers or sections as basis lines:** a line starting
    `^\d+\.? (Special Conditions|Equivalent Safety Findings|Exemptions)`, or
    matching `^\d+ to \d+$` (an Eligible S/N range), or Environmental
    Standards (`CS-36`, `ICAO Annex 16`) typed special_condition.
16. **Split basis line:** a line starting with a bare `23\.\d+` provision list,
    in lowercase, or with no regulation prefix; a line ending in a comma, a
    `dated \d+\.` (day number), or an unclosed `(`; consecutive lines under one
    applicability heading with differing `entry_type`.
17. **ELOS/SC citations short of the text:** a line with more `§ NN.NNN`
    mentions than `citations` entries, allowing `23. 807(e)` (space after the
    dot). Citation groups run together with no separator: `\)\(` joined
    patterns like `(a)(2)(a)(3)`.
18. **Categories short of the source:** a multi-category EASA line
    (`Normal / Utility`) with fewer categories than category words.
19. **S/N applicability dropped:** `raw_reference` with `S/N … and On` but
    `applicability` null.
20. **Basis footnote digit or glyph:** a line ending in a footnote digit as in
    `(CS-25 Amdt 1)2 Hydraulic Systems`; a private-use glyph in
    `applicability_notes`.

## 2026-11-13 promote-staged (GA8 and GA10 TCDS)

- **Delta:** 3 aircraft files: 2 `basis-lines` (ga8, ga8-tc-320; ga8-tc-320 also `references`), 1 `new-file` (ga10). No document changes.
- **Reading:** 5 TCDS items (all must-read) read by 1 Sonnet subagent; 0 blocker, 0 major, 5 minor.
- **Automated:** candidate built, 0 unresolved (base 330 models → 331, entries 4616 → 4638). New hits: 1 `regulation-no-refs` (ga10 Part 34, expected: Part 34 isn't a document in data/).
- **Promoted:** airvan10-pty-ltd/ga10.json, ga8-airvan-pty-ltd/ga8.json, ga8-airvan-pty-ltd/ga8-tc-320.json
- **Held back:** none
- **Orphans left for the user:** airbus-defence-and-space-s-a/c-212-ee.json, gulfstream-aerospace-corporation/gvii-g500.json, gvii-g600.json, gulfstream-aerospace-lp-galp/gulfstream-g280.json, textron-aviation-inc/680a.json
- **Tooling note:** `.claude/skills/promote-staged/scripts/batches.py` crashes on a `new-file` aircraft delta row (its `tcb` is a list: unhashable in `aircraft_items`). Worked around with a scratch copy.

## 2026-11-13 promote-staged (schema v13 holder/manufacturer_group on all aircraft; FAA Part 26)

- **Delta:** 348 files. Aircraft 327 (`metadata` + `tcds-revision` all; 4 also `basis-lines`: bolkow-bo-209-monsun, c-295, bn2t-4s, ha-420). Documents 21: 17 `new-file` (FAA Part 26, 16 provisions + `_document.json`), 4 changed (faa/23/179 `[Removed.]` provision now `deleted`; faa/23/F23 titles lose a literal `\n` plus a provenance note; faa/25/F25 stray `\n` removed from 25-32; faa/25/_document 25-125 effective date 2008-09-19 → 2008-12-26, backed by an override row citing FR E9-15311).
- **Reading:** 184 items (must-read 364, capped at 160, plus 24 sampled) read by 23 Sonnet subagents. Aircraft items were read for the added `holder`, not the whole basis; `manufacturer_group` was not checked against any source (it isn't printed on a TCDS). 3 of 23 batches were FAA documents (Part 26 + F23/F25), the other 20 aircraft; the 160 cap means about 160 of the 327 aircraft were read.
- **Result:** 184 items read. 8 blocker, 140 major, 143 minor findings (reader counts, before grouping), all but F-20261113-01..05 pre-existing in data/ (basis lines are byte-identical to data/ apart from `holder`/`manufacturer_group`). No staged file is worse than data/.
- **Automated:** candidate built with no new errors; data/ itself fails to build (694 errors) because every aircraft file now needs `manufacturer_group` and `holder`. After promotion the build fails with 4 errors, all from the 2 orphans below. New hits: 12 `duplicate-paragraph` in Part 26 (false positive: repeated (i)-(iii) date lists under different (c)(n)), `figure-caption`, `stray-symbols` (``quote'' from eCFR, faithful), `regulation-no-refs`/`runaway-line` on c-295 and bn2t-4s (both in data/ already).
- **Promoted:** all 348 files (327 aircraft, 21 documents).
- **Held back:** none.
- **Orphans left for the user (build blocked until resolved):** airbus-s-a-s/a330-743l.json, airbus-s-a-s/a330-841.json. The guard in `tools/s00_common/tcds_guard.py` no longer stages them (ETCDS-16); they lack `manufacturer_group`/`holder`, so `build.py` fails on them. Delete them or fix ETCDS-16 and restage.
- **Tooling note:** the 20-subagent concurrency limit meant three batches launched late; no effect on results.
- **Check candidates:** `Amendments N – M` en-dash range with `to` = lower number; basis line that is a bare model footer (`^AS202/\S+$`), `3 Special Conditions: None`, or a table header ("Topic"); line over 1500 chars; `\S Table \d+--` run onto a prose line; `[ (]-inch` / `nominal inch` (lost fraction glyph); several `(N) ` labels on one line; holder string that is a prefix of the next cover-page line.

### F-20261113-05 · major · missing-source · documents/faa/26/35.json, 26/5.json

Text refers to Tables 1 and 2 (26.35) and Table 1 (26.5, 26-2) that are absent; the DRS source has only the intro sentence. 26.5 also carries stray `]` bracket marks from DRS amendment marking.
- Suggested area: issues/faa-regs
- Promotion: promoted (new files)

### F-20261113-06 · blocker · formula-glyphs · documents/faa/23/F23.json 23-49, 23-34, faa/25/F25.json 25-32 (pre-existing)

Fraction images in the DRS HTML were lost: "no more than inch thickness", "nominal inch I.D.", "nearest -inch". Needs an eCFR check or an override.
- Suggested area: issues/text-layout.md (TEXT-)
- Promotion: promoted (pre-existing)

### F-20261113-08 · blocker · tcds-lines · pre-existing

Junk basis lines from page footers / headings: "A-1C-180", "3 Special Conditions: None", eligible S/N "3000+" as entries (a-1c-180, a-1b, a-1, as202-18a2/a3/a4). pzl-m28-05 line 1 is a runaway swallowing S/N lead-ins; 525 "Additions" table flattened with titles on wrong reg numbers (~17 reg numbers lost).
- Suggested area: issues/easa-tcds.md
- Promotion: promoted (pre-existing)

### F-20261113-10 · major · tcds-lines · pre-existing

Runaway or merged basis lines and wrong splits: c-295 (EASA.A.186, up to 12.5k chars, same in data/; staged fixes one 25.562 wrap), bn2t-4s BCAR lines (staged fixes one wrap, line 2 still runs), l-410-ng, pa-46r-350t, 525b, md-90-30, pzl-m18/m18a Normal+Restricted merged, c-212-cb/cd "Spain" typed regulation and environmental items merged, saab 340B/SF340A B-6/D-9 and CRI merges.
- Suggested area: issues/easa-tcds.md
- Promotion: promoted (pre-existing)

### F-20261113-11 · major · tcds-entry-type · pre-existing

ELOS/ESF/SC mis-typed or merged: 390 ELOS as `other`, pa-44-180t "ICAO Annex 16" as `elos`, ae-270 SC+ELOS merged, pc-12-47e SC/ESF headings as `regulation`, emb-550 Dev/ESF dropped, 700/c-295 SC and ESF codes (D-01, F-20) lost, 717-200 header rows as regulation, 510 CRI lines scrambled, z-726 six ESFs in one line, da-62 exemption in ELOS line, 172q ESF lines missing.
- Suggested area: issues/easa-tcds.md
- Promotion: promoted (pre-existing)

### F-20261113-12 · major · tcds-categories / applicability · pre-existing

Categories missing a source category (z-242-l, g-115ta, z-143-l, z-50-ls, g-120tp-a); option-specific basis attached to the wrong model (pa-44-180t Avidyne/G1000 NXi from PA-44-180, pc-12-47e PT6E-67XP lines with null applicability); pa-32-301ft/pa-32r-301t basis is prose with levels only in note 5.
- Suggested area: issues/easa-tcds.md
- Promotion: promoted (pre-existing)

## 2026-11-13 promote-staged (deviations + aircraft)

- **Delta:** 6,825 files: 6,799 new deviation records (6,370 FAA, 429 EASA), 26 aircraft changes (4 basis-lines, 22 references). Documents: nothing to promote.
- **Checked by script:** fields.py 77,893 field checks, all `ok` (EASA `stage` passes with "not decidable: sampled"). Candidate build clean: 0 new unresolved; deviations 0 -> 6,799, deviation_citations 6,233, citation_gaps 2,676. checks.py/scan_data.py: 9 aircraft hits, all pre-existing patterns (Part 26 lines without refs, one DA-62 CS 23.0049).
- **Read:** 115 items in 8 Sonnet batches (80 field-sample, 16 deviation-new, 16 references, 3 basis-lines). Estimated ~318k tokens; actual ~557k (about 75% over; raise READER_OVERHEAD/BASE in batches.py).
- **Promoted:** 6,370 FAA deviation records, 26 aircraft files. data/ and promotion.json are uncommitted.
- **Held back:** all 429 EASA deviation records (F-20261113-15, stage unreliable). Orphans: 0.
- **Check candidates:** EASA `stage=proposed` where the detail page lists a "Final ..." pdf, an unlabelled Issue pdf or a CRD next to the proposal; EASA title starting "Final " with stage `proposed`; `number` null while title has SC-/MOC identifier or listing has a "Reference" line; `number` prefix of a comma-separated Reference; control chars `[\x00-\x1f]` in deviation title/source_url; literal `\n` in title (156 FAA files); CS-ACNS/CS-VLA in raw_reference with no reference; basis line ending in `,` or `:` before a line starting with a bare provision number.

### F-20261113-17 · minor · deviation-title · control char / literal \n

EASA 19608 title and source_url carry U+0003 (`%03`); FAA EX18074 `model` has a GUID run into it (source has it).
- FAA literal `\n` titles: the DRS Subject stores line breaks as the two characters `\n` (checked in input/cache/drs/deviations/). Fixed in the FAA emitter 2026-11-13 (tools, `listing_title`): 156 files change title only. data/ keeps the old titles until the user restages (`tools.s02_emit.faa.deviations.emit`) and promotes.
- Promotion: FAA promoted; EASA held back

### F-20261113-18 · major · tcds-references · pre-existing

EASA basis lines naming CS-ACNS / CS-VLA provisions have no references (04.06, 04.08, 04.09); basis lines broken at a trailing comma (page break; Textron A00003SE before `FAR 23.1325`). Staged is no worse than data/ (range fixes and PA-46/DA-62/Part 26 references all correct).
- Suggested area: issues/easa-tcds.md
- Promotion: promoted (pre-existing)

## 2026-11-14 promote-staged (EASA deviation records only)

- **Delta:** 890 files in the staged tree. This run took only the 429 new EASA deviation records. The 461 document and aircraft changes were deferred: the must-read set was ~1.03M tokens, over the 800k hard stop, mostly 546 CAR-3 / CAR-3 Reissue `publication_cite` FR-cite flags. `fields.py` has no verifier for derived FR cites ("not found in the source text"). The split was the user's decision.
- **Checked by script:** fields.py, deviation fields: 2,740 checks, all `ok` (EASA `stage` passes with "not decidable: sampled"). Candidate build (data/ plus the 429 records): clean, counts unchanged, 0 unresolved.
- **Read:** 76 items in 5 Sonnet batches (60 field-sample, 16 deviation-new). Plus one second reader on the stage and number findings (9 records). Checked by readers, not verified.
- **Cost:** estimated ~179k tokens; actual ~348k for the five batches (56k+57k+61k+79k+93k), +63k for the second reader (about 95% over the estimate; the estimate looks low for deviation field batches, raise BASE/READER_OVERHEAD).
- **Promoted:** all 429 EASA deviation records (data/deviations/easa/). Post-promote build passes; deviation dry run shows 6,799 identical, 0 new. data/ and promotion.json are uncommitted.
- **Held back:** none of these. The 461 document and aircraft files remain staged (not read). Orphans: 0.
- **Check candidates:** EASA `number` null while the title or a download label carries an identifier: spaced titles (`SC E23-979`), `ref. CPTS-000364`, labels without an SC/ESF prefix (`Deviation D-9107`, `SC B-15`, `SC D-43`, `CRI F-01`); a label suffix dropped (`ESF F-37-9` → `ESF F-37`); a title naming a second provision without a part (`and CS1309 (c)`); a citation paragraph that is several adjacent letters (`(a)(c)(d)`) alongside a duplicate citation of the same section.

### F-20261114-01 · major · deviation-number · EASA number null though the listing prints an identifier

`number` is null on records where the title or a download label prints an identifier. Confirmed by the second reader on 43885 (`SC E23-979`, title), 5881 (`SC B-15`, label), 20196 (`SC D-43`, label), 5939 (`D-9107`, label), 139399 (`CPTS-000364`, title). Also read once: 108102 (`SC E-18`), 5821 (`CRI F-01`), and 140151 (`M-TS-0000417`, title). 6056 is undecidable (identifier only in the CRD label, `H-01`). Likely in the number extractor (`number_of`): it misses spaced titles, `ref. X` and labels without an SC/ESF prefix. Probably more records than the sample shows.
- Data: `number: null`
- Source: input/cache/easa_deviations/detail/{43885,5881,20196,5939,139399}.html
- Suggested area: issues/ deviations file (EASA number extraction)
- Promotion: promoted (null is absent, not misleading; a later promote fills it in)

### F-20261114-02 · major · deviation-citations · EASA citations: second provision missed, adjacent letters read as a path

5792 title "CS29.1305(a)(25) and CS1309 (c)": only 1305(a)(25) cited, 1309(c) missed. 43904: citation 1305 appears twice, the second with paragraph `(a)(c)(d)`, which is the list (a), (c), (d) in the source.
- Data: `cs-29 1305 (a)(25)` only (5792); `cs-23 1305` + `1305 (a)(c)(d)` (43904)
- Source: input/cache/easa_deviations/detail/{5792,43904}.html
- Suggested area: issues/ deviations file (citation parsing)
- Promotion: promoted

### F-20261114-03 · minor · deviation-number · label suffix dropped

46936 `number` is `ESF F-37`; the label prints `ESF F-37-9` (probably a 777-9 model suffix, not certain).
- Promotion: promoted

### F-20261114-04 · minor · deviation-stage · EASA stage rule is a judgement call (no defect found)

First readers rated `stage: final` wrong on 21839, 43885, 5881, 6056, 20196, 17411 (title "Proposed ...", no pdf labelled Final, only the proposal and a CRD). The second reader checked the rule that a CRD counts as final and found all staged stages right (also 5794, 139399; 5939 proposed is right). Logged so the rule and the many readers' disagreement are visible when the stage check candidates from the 2026-11-13 run are triaged (F-20261113-15).
- Promotion: promoted

## 2026-11-14 promote-staged (second run today; documents + aircraft, CAR 3 split off)

- **Delta:** 461 files: 420 fields-only, 15 markup-only, 1 layout-only, 24 words, 1 versions-removed, 1 aircraft. 434 of them are CAR 3 (`caa/car-3`, `cab/car-3-reissue`) and carry the F-20261112-05 `publication_cite` change. Deviations: 0 changes.
- **Split:** the full plan was ~1.03M tokens of must-read, over the 800k hard stop. 546 of the 570 field checks were `publication_cite` flags in CAR 3: `fields.py` checks them as verbatim text in the extracted source, but the new values (`17 FR 1083`) come from the Federal Register copies, so every one flags "not found in the source text" and no script can judge them. On the user's choice, this run promoted everything except those two documents.
- **Checked by script:** fields.py on the 27 non-CAR files: 8 checks, `tcds.holder 1 ok`, `canonical_title 1 unverifiable`, `provenance 6 unverifiable`. The candidate build (all staged overlaid on data/) passed: schema v15, 0 unresolved. new_checks.tsv 3 hits and new_scan.tsv 21 (the CAR 3 and Part 26 ones were not read; the others fell within the read files).
- **Reading:** 29 items, all read: 7 field flags, 1 field sample, 12 words, 8 of 16 markup-only (sampled), 1 layout-only. Not sampled: 7 markup-only (MIL-HDBK-516 4.3.4-516d, 9.1.1.2, 9.3.3.4, 9.3.4.3, 9.4.4.3, 9.4.4.4; STANAG 1401), promoted by script check only.
- **Cost:** estimated ~141k; actual ~251k (63k+106k+82k), 3 readers, 1 wave. About 78% over the estimate.
- **Result:** 0 blocker, 1 major, 1 minor.
- **Promoted:** 25 document files (nato/stanag-4671 ×11, dod/mil-hdbk-516 ×14) and 1 aircraft file (TECNAM P-Mentor holder). The `nato/stanag-4671/865.json` removal of EdB-V1 is a collapse: with the title spill (the title's last word was in the text) fixed, EdB-V1 has the same text as Ed1. Post-promote build passes; data/ and promotion.json are uncommitted.
- **Held back:** `documents/easa/cs-25/143.json` (F-20261114b-01). The 434 CAR 3 files (`caa/car-3`, `cab/car-3-reissue`): not read. The `publication_cite` values need reading against the FR copies as a sample (about 20 per document), plus the 14 CAR 3 words files and the length-drop hits on CAR 3 Reissue §3.109 and §3.778 and the duplicate-paragraph and unbalanced-bracket hits on §3.84a/85a. Next run: `promote-staged` limited to CAR 3.
- **Orphans left for the user:** documents 2210 (the dry run lists the whole tree, unchanged by this run), aircraft 326 (see tools/out/reports/promote_orphans*.tsv; the earlier dry run in this session reported 0 against the real tree).
- **Check candidates:** a footnote number inside a garbled table read as a paragraph label: a lone `(N)` followed by uppercase words (`(3) ASYMMETRIC WAT-LIMITED`). Subscripts flattened in table headers (S₁ → S1 in STANAG EdB-V1 AppK).
- **Verifier gap:** `publication_cite` for CAR 3 needs a `derived` kind (FR cite from the FR copy), not `verbatim`. This is a skill change for the user to decide.

### F-20261114b-01 · major · layout · documents/easa/cs-25/143.json CS25-7

The layout split turns climb-table footnote text (interleaved by pdftotext, also in data/) into fake paragraphs under 25.143(j)(2).
- Data: `(2) There is no pitch control force reversal during a pushover manoeuvre down to 0.5 ASYMMETRIC WAT-LIMITED (1) ALL ENGINES OPERATING CLIMB (3) ASYMMETRIC ...` (the staged split adds paragraphs "(3) ASYMMETRIC WAT-LIMITED" and nested "(1) SYMMETRIC FOR –3° FLIGHT PATH ANGLE g load factor.")
- Source: `(2) There is no pitch control force reversal during a pushover manoeuvre down to 0.5 g load factor.` (input/Regs/EASA/CS-25/CS25-7.pdf, CS 25.143(j))
- Suggested area: issues/text-layout.md (TEXT-)
- Promotion: held back (staged adds false structure over the data/ text)
- Fixed 2026-11-14 (staged, not promoted): the cause is wider than CS25-7. In CS25-3, -7, -13, -15, -16, -18, -21 and -26 the reader drops "ANGLE IN A" from the (h) table header and moves the table's THRUST/POWER SETTING column into (j) (the CS25-7 split is one symptom). 16 `replace_text` rows in tools/overrides/text.tsv (two per revision, evidence = page of each PDF, checked against page images of CS25-3, -7 and -26) put the column back into (h) in reading order and restore the dropped words. No table markup: that is EASA-17. Word check: each revision gains only ANGLE IN A, and nothing else is lost; CS25-0 and CS25-27 are unchanged. Candidate build passes.

### F-20261114b-02 · minor · figure-table · documents/dod/mil-hdbk-516/4.3.3-516d.json MIL-HDBK-516D

TABLE II, Fungus row: the source prints "Natural" and "Induced" on two stacked lines; staged has `Natural Induced` in one cell. Words match; the meaning is ambiguous. Low confidence.
- Source: input/Regs/US DoD/MIL-HDBK-516D.pdf p.51
- Suggested area: issues/text-layout.md (TEXT-)
- Promotion: promoted (words match the source)

## 2026-11-14 promote-staged (third run today; the 15 words files only, CAR 3 FR-cite files split off)

- **Delta:** 435 files: 420 fields-only+metadata (CAR 3 `publication_cite`, F-20261112-05), 15 words+metadata (`caa/car-3` ×1, `cab/car-3-reissue` ×13, `easa/cs-25/143` ×1). Aircraft and deviations: 0 changes.
- **Split:** the full plan was ~1.03M tokens of must-read, over the 800k hard stop, because 546 `publication_cite` flags (FR cites no verbatim verifier can match). On the user's choice, this run read only the 15 words files; the 420 FR-cite files stay in staged.
- **Checked by script:** fields.py on the 15 words files: 47 checks, `publication_cite 24 flag` (FR cites, see the verifier gap in the earlier run), `provenance 13 unverifiable`, `title_at_revision 10 ok`. Candidate build passed (schema v15, 0 unresolved; text_missing 98 → 95). new_checks 3 hits, new_scan 38 (only those on the 15 files were attached; the rest, e.g. Part 26 and the TCDS basis hits, are in unchanged files).
- **Reading:** 70 items, all read: 37 field flags, 10 field samples, 23 words diffs. Hits: length-drop on §3.109 and §3.778 read and clean (readers 03.02, 03.09); duplicate-paragraph on §3.85a and unbalanced-brackets on §3.84a are real (F-20261114c-01, -02); caps-run on CS 25.143 is the flat (h) table (already EASA-17).
- **Cost:** estimated ~232k; actual ~379k (76k+77k+80k+90k+57k), 5 readers, 1 wave. About 63% over the estimate (over a third: raise the constants).
- **Result:** 1 blocker, 2 major, 1 minor.
- **Promoted:** 10 files: `caa/car-3/655.json`, `cab/car-3-reissue/{109,118,124,222,307,388,411,778}.json`, `easa/cs-25/143.json` (the F-20261114b-01 fix; the 8 override rows now read right on all 8 revisions). Post-promote build passes; data/ and promotion.json are uncommitted.
- **Held back:** `cab/car-3-reissue/85a.json` (F-20261114c-01) and `84a.json` (F-20261114c-02). Held with them because they move text into 84a/85a and would drop words alone: `84.json`, `85.json`, `1.json` (its CAR3R-7 loses the §3.85a(b)(2) text that belongs to 85a). The 420 FR-cite files: not read.
- **Orphans left for the user:** 0 at the step-1 dry runs (documents, aircraft, deviations).
- **Pre-existing seen:** CS 25.143(h) table still flat prose and its footnotes read as paragraphs (already ISSUES EASA-17); dangling "to read as follows:" at the end of 1.json CAR3R-7 (minor).
- **Check candidates:** OCR leaves a stray letter before a paragraph label, e.g. `(ob)`, `(ce)`, `(ad)`, `Gi)`, `Gii)`: a label like `\((o|c|a)[a-z]\)` at paragraph start. A version whose text starts with a lowercase word while its title ends mid-phrase (title cut at a line wrap). A CAR amendment provision text containing `§ N.NN [Amendment]` followed by `By amending` (another section's instructions bled in). A section-range with its hyphen lost, `3.1833.189`.

### F-20261114c-01 · blocker · boundary · documents/cab/car-3-reissue/85a.json CAR3R-7

New content (replaces TEXT MISSING) is wrong in two ways. The text runs on into other sections' amendment instructions (`§ 3.86 [Amendment] 5. By amending §3.86(a)(1)... 6. By amending §3.123 to read as follows:`), while 86.json CAR3R-7 is still TEXT MISSING, so item 5 sits under the wrong provision. And `title_at_revision` is cut at the column wrap.
- Data: title `Climb requirements; airplanes.`, text opens `of 6,000 pounds or less. * * . * *` (data/ kept the full title, "airplanes of 6,000lbs or less" with a spacing slip). Minor OCR left in: `gine`, `G)`, `Gii)`, `in. the`.
- Source: `§3.85a Climb requirements; airplanes / of 6,000 pounds or less.` (input/Regs/CAR/3/CAR3R-7.txt lines 149-151; page 8 scan)
- Suggested area: issues/ CAR file (CAR-9 narrowed: bracketed sections)
- Promotion: held back (title regresses; boundary bleed is new). The field-sample script passed the title: `title_at_revision` verbatim passes a cut title.
- 85a CAR3R-0 (V_{s1}, V_{s0}, 0.02 V_{s0}^{2}) was read and is right; it is held only because it is in the same file.

### F-20261114c-02 · major · ocr · documents/cab/car-3-reissue/84a.json CAR3R-0

New text for §3.84a (TEXT MISSING in data/) carries OCR damage: `(ob)` for `(b)`, `contro]` for `control` (the unbalanced-brackets hit), V_s1 flattened to `Vs,` twice, `ibs.` for `lbs.`, and paragraphs (a)-(d) run together on one line.
- Source: CAR3R-0.pdf p.8 (checked against the page image)
- Suggested area: issues/ CAR file
- Promotion: held back (a confirmed new hit). With it: 84.json (removes the 84a text from §3.84; correct), 85.json (likewise for 85a), 1.json.

### F-20261114c-03 · major · ocr · documents/cab/car-3-reissue/222.json CAR3R-0

The restored `(a)` reads `3.1833.189` where the PDF has `3.183-3.189` (p.12-13). Already in data/.
- Also minor: 411.json restored `(a)` keeps `instgjlation` (OCR).
- Suggested area: issues/ CAR file
- Promotion: promoted (pre-existing; staged is no worse)
