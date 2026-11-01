# TCDS parser trial: 20 Part 23 TCDS (2026-10-31)

Ran the existing `tools/aircraft/faa_tcds.py` (unchanged) over 20 current
Part 23 TCDS from `input/TCDS/FAA/`. Expected to find problems; this lists
them with evidence. Nothing in `data/`, `tools/out/staged/` or the repo was
changed. All output went to the session scratchpad
(`.../scratchpad/{staged,reports,logs}`), via `--out-dir` / `--report-dir`.

This is input for `reviews/PROMPT_TCDS_PARSER.md` (the three-stage refactor).
Items marked **(known)** are already listed there; the rest are new.

## Result in one paragraph

Of 20 TCDS, **4 produced usable output** (A57CE, A1WI, A00012NY, A60EU), and
all four have defects. **2 more** (3A12, A4CE) staged only the equivalent-safety
list and lost the real basis. **14 produced nothing usable**: 9 found no model
headings, 5 found models but tokenised zero entries. Worse than the loud
failures: the parser **stages "empty" files that pass the schema and the build**
(11 of them here), and several defects produce plausible-looking output that is
wrong or incomplete with no warning.

## Method

```bash
# per TCDS; --out-dir/--report-dir pointed at the scratchpad
uv run python -m tools.aircraft.faa_tcds input/TCDS/FAA/<T>_Rev<N>.pdf \
    --out-dir $S/staged --report-dir $S/reports
```

Selection: current Part 23 "Small Airplane" TCDS, chosen to span holders,
eras, layouts (bullet, outline, label-prose, pertinent-to-all, per-model
headings) and the families the prompt calls out (Cirrus, DA 42, Cessna 525/172).

Extra probes, all scratch-only (no repo edits):
- ran the staged output through `build.py --data-dir <copy of data/ + staged>`;
- re-ran the 7 dash-heading TCDS with a widened heading regex (monkeypatched
  in a runner script) to see what fails *behind* the heading failure;
- called `classify()` / `resolve_regulation()` directly on real strings;
- a parser-free heuristic count over the 201 current Part 23 small-airplane
  TCDS on disk, to weight each issue (numbers marked "corpus" below are
  `pdftotext` pattern counts, not parser output).

## Per-TCDS outcome

| # | TCDS | Aircraft | Outcome | Main cause |
|---|---|---|---|---|
| 1 | A00009CH r25 | Cirrus SR20/22/22T | **0 staged** (no headings) | `I - MODEL SR20` (dash, capitals). Behind it: basis sits under "Data Pertinent to All Models"; SR22T has no `( )` so category `unknown` fails schema |
| 2 | A57CE r34 | Diamond DA 42 (+DA 62) | 4 staged | Known DA 42 defects reproduce (header line "Special Conditions:" is an entry; NG/M-NG JAR+NOTE merged, 0 refs) **(known)** |
| 3 | A1WI r34 | Cessna 525 family | 4 staged | 525B/525C base Part 23 line misclassified, unresolved (§A2) |
| 4 | A00072CE r12 | Pilatus PC-24 | 1 staged, **placeholder only** | Basis items numbered `1)`, `2)`; manufacturer `Unknown` |
| 5 | A00007SE r28 | Kodiak 100/200 | **0 staged** (no headings) | `I - Model` dash. Behind it: prose basis, no bullets → 0 entries; no `Type Certificate Holder` line |
| 6 | A00059SE r7 | Epic E1000 | **0 staged** (no headings) | Single model, no Roman numeral (`Model E1000 (Utility…)`); no holder line |
| 7 | A00018AT r11 | Honda HA-420 | **0 staged** (no headings) | `I – Model` en dash. Behind it: category `6/7/8PCLM, Normal Category` → `'6/7/8pclm'` fails schema |
| 8 | A00012NY r2 | Diamond DA 62 (Canada) | 1 staged, 9 entries | AWM "equivalent to 23-62" unresolved (matches DA 40 gap, **known**); policy memo classed `regulation` |
| 9 | A62CE r12 | Tecnam P2006T | **0 staged** (no headings) | `I - Model` dash. Behind it: label-prose basis, unmarked lines → 0 entries |
| 10 | A25SO r42 | Piper PA-46 | **0 staged** (no headings) | `I. - Model` (dot **and** dash). Behind it: no basis found for 2 of 4 models; `(Malibu Matrix)` taken as a category |
| 11 | A19SO r23 | Piper PA-44 | **0 staged** (no headings) | `IA. - Model`, `IB. - Model`. FAA typo "Revison 23" → revision `None` |
| 12 | 3A12 r89 | Cessna 172 | 3 staged: `172Q` placeholder, `172R`/`172S` ELOS list only | Group basis "Data Pertinent to Models 172 thru 172Q" (§A3, §A4); CAR 3 not interpreted |
| 13 | A4CE r52 | Cessna 206 | 3 staged: 2 placeholders, `T206H` ELOS list only | Same group-basis pattern; 10 of 13 blocks have no basis, 2 have zero entries |
| 14 | A37CE r25 | Cessna 208 | 1 staged, **placeholder** | "Data Pertinent to All Models" basis; designation `208B` appears twice |
| 15 | A78EU r39 | Pilatus PC-12 (5 models) | 4 **placeholders**, `PC-12` fails schema | `Certification Basis.` + `1)` numbering; heading has no `( )` → category `unknown`; holder `Type Certificate Holder.` → `Unknown` |
| 16 | A60EU r40 | Daher TBM 700 | 1 staged, 24 flat entries | Variants by MOD/serial flattened with no applicability (§A6) |
| 17 | A00079CE r0 | KC-100 | 1 staged, **placeholder** | Unmarked paragraphs, no bullets |
| 18 | A00121CE r0 | Bristell B23 | **0 staged** (no headings) | `I. Bristell B23` (no word "Model"). Behind it: `1.` list indented 29 cols, outside the outline detector's `{0,8}` |
| 19 | A17SW r15 | Air Tractor AT-4xx/5xx | **0 staged** (no headings) | Dash headings. Behind it: **no Certification Basis field at all** (restricted category) |
| 20 | A8SO r28 | Aviat Husky/S-1/S-2 | **1 of 7 models staged, placeholder** | Only `VII. Model S-2C` has a dot; six dash headings silently skipped |

## Findings

### A. Silent: wrong or incomplete output with no warning (fix first)

**A1. `resolve_regulation` mis-reads amendment numbers written without the part prefix.**
`PART_RANGE_RE` uses `\d*-?(\d+)`; with no `23-` prefix the greedy `\d*` takes
all but the last digit:

```
'14 CFR Part 23 including Amendments 1 through 62'  -> to: 23-2    (should be 23-62)
'14 CFR Part 23 ... amendments 10 through 20'       -> to: 23-0    (should be 23-20)
'14 CFR Part 23 Amendments 23-1 through 23-38, 40'  -> to: 23-38   (40 dropped, no skip)
```

Dashed forms are fine. The result is a valid, existing revision, so the build
cannot catch it. Latent in this run only because the tokeniser failed first on
PC-24 ("amendments 1 through amendment 62"), but PC-24, Aviat, Tecnam and most
pre-2000 TCDS use this style. The prompt's planned "accept `thru Amendment 51`
without the part prefix" would switch it on; fix the regex *before* that.

**A2. Misclassification discards the base line's references.**
`classify()` tests `Special Condition`, `Exemption`, `ELOS` with `re.search`
before checking for a Part 23 citation, and `build_aircraft_json` only resolves
`regulation` entries. Real cases (A1WI, the "golden" layout):
- 525B entry 1: `14 CFR Part 23 … 23-1 through 23-54. 23.562 … as required by Exemption No. 7981 …` → `exemption`, `references: []`.
- 525C entry 1: `14 CFR Part 23 … 23-1 through 23-57, with exceptions addressed in Special Conditions, ELOS's, and Exemptions` → `special_condition`, `references: []`.
`resolve_regulation` alone does resolve both (`to 23-54`, `to 23-57`). The
model's primary basis is therefore missing from cert-basis resolution.
Also DA 62 (A00012NY): "Project Specific Policy Memorandum … Unintended Errors
in 14 CFR Part 23" is classed `regulation`.

**A3. Outline mode drops everything before the first number.**
`detect_mode` switches to outline if *any* line matches `^\s{0,8}\d+\.\s`. In
the 172R/172S/T206H basis, the only numbered thing is the "Equivalent Safety
Items" list, which sits *after* the real basis paragraph. `tokenize_outline`
ignores text before the first numbered item, so staged `172r.json` contains five
ELOS rows and **no Part 23 or Part 36 line**, with no warning. (Entry 5 also
swallows trailing "Date of Application…" prose and is typed `special_condition`.)

**A4. A shared basis is attached to one model or none.**
Cessna 172, 206 and 208, Cirrus, Air Tractor and Kodiak keep the basis in a
"Data Pertinent to Models X thru Y" / "…to All Models" block after the
last model of the group. `split_models` gives that text to the last model block
only. Effects:
- 172: `172`…`172P` → "no Certification Basis section found" (warned);
  `172Q` gets the group basis (CAR 3) but 0 entries (the "Models 172 thru 172P"
  sub-label etc. are not understood).
- 206: models I–XI warned; `U206G/TU206G` and `206H` 0 entries.
- 208: models I and II warned, III gets 0 entries.
Cessna's CAR 3 / Part 23 split by model range ("Models 172 thru 172P: CAR 3 …",
"Models 172P thru 172Q: FAR 36…") is a within-basis scoping layer the
architecture has no field for yet.

**A5. Models that share a heading block are never emitted; no cover-page reconciliation.**
One file per primary heading. 3A12 lists 18 designations on its cover; 11 model
blocks exist; `172B`, `172E`–`172H` (block IV is "Models 172D, 172E, …"), `172K`
(block V) and others are never emitted. A4CE does the same with
`P206C/TP206C, P206D/TP206D, …`. A8SO is the worst case: six of seven models
skipped because of dash headings (§B1), and the run reports one model with
nothing about the other six. Nothing compares the cover list to the models
emitted.

**A6. Variant scopes are flattened (TBM 700), page breaks split bullets.**
A60EU states four to six mutually exclusive bases by MOD/serial ("Airplanes
(s/n 434-999 …) equipped with …", "Airplanes not equipped with MOD 70-139-00"),
then dash bullets at three different indents. The parser's wrapper trigger only
fires on "…the following is the certification basis:", so **all 24 entries have
`applicability: None`** and carry Part 36 levels 36-17, 36-22 and 36-28 together.
A page break splits one bullet: entry 12 ends at `…36-1`, the continuation
`through Amendment 36-28.` is treated as wrapper text and dropped. Entries 1, 4, 7, 13 and 16
resolve to `to 23-34` while the raw line also lists overriding sections
("Sections 23.49, 23.561, 23.562 and 23.785 of Amendment 44 …"); the override is
silently not represented, so a partly understood line looks fully resolved.
Entry 19 ("at Amendment 23-64 sections 23.2005 …") is left unresolved, which is
correct. A later sub-list is split into an `other` row that starts with a stray
`-` (entry 21, `-Sections 23.201, 23.203, …`).

**A7. Placeholder rows are staged, schema-valid, build-valid and promotable.**
When tokenising yields nothing, `build_aircraft_json` writes one entry
`"(parser produced no entries; review PDF by hand)"`. It passes the schema, so
the file is staged and counted in `models_emitted`. 11 of these were staged here
(`s-2c`, `kc-100`, `172q`, `206h`, `208b`, `u206g-tu206g`, `pc-12-45`, `-47`,
`-47e`, `-47g`, `pc-24`). With 3A12 removed, `build.py` on `data/` + staged
output **succeeded** (23 models, 10 placeholder entries in `cert_basis_entries`,
manufacturer `Unknown` in `manufacturers`). `promote --aircraft` would copy
these into `data/`. Per-TCDS stderr reads `models: 1  entries: 0`, which hides that
a file was written. The zero-entry case should not stage; it should fail loud
in the report (CLAUDE.md "fail loud").

**A8. `Part 21` can be captured as the cited part.**
PC-24 reads `14 CFR part 21.29, part 21.183(c) and 14 CFR Part 23 …`. The regex
anchors on the first `Part N`, giving `document: 21`, so the report would say
"document 21 not in dataset" for a Part 23 line (verified: groups
`('21','1','2')`). If a Part 21 document is ever added, this becomes a wrong
reference. Related: forms the regex rejects outright and so reports as
unresolved: `14 CFR 23, Normal Category …` (PC-12, no word "Part"),
`FAR Part 23 as amended by Amendments 23-1 through 23-28` (Cessna 208, no
`14`), `Part 23 Amendments 23-59` (KC-100, no range).

**A9. Duplicate designations collide on the filename.**
A37CE has blocks II and III both headed `Model 208B`; both slug to `208b.json`,
so one overwrites the other. (Here both were placeholders.) Same risk for any
TCDS that splits a model by serial range into several headings.

### B. Loud failures: stage 1 (segmentation)

**B1. Model heading regex is too narrow.** `ROMAN_RE =
^\s*([IVX]+)\.\s+Model\s+` is case-sensitive and dot-only. Variants seen in
these 20: `I - MODEL SR20` (Cirrus), `I - Model` (Kodiak, P2006T, Air Tractor, 6
of 7 Aviat headings), `I – Model` en dash (HA-420), `I. - Model` (PA-46),
`IA. - Model` (PA-44), `I. Bristell B23` (no "Model"), and no numeral at all
(E1000). Corpus: the strict regex finds headings in **105 of 201**;
a dash-tolerant one finds **181**; **20 match neither** (single-model TCDS
without numerals, and others). Biggest single unlock found.

**B2. Heading parsing assumes `Model X (Category)`.**
Designation and category come from `re.split(r"[(,]|\bapproved\b")` and the
first `( )`. Seen: `Model PC-12, Normal Category, approved …` (no parens →
category `unknown` → schema error); `(6/7/8PCLM, Normal Category)` →
`'6/7/8pclm'`; `(Malibu Matrix)` → category `'malibu matrix'`; Air Tractor
`AT-504 2 PCLM (Restricted Category)` → designation `AT-504 2 PCLM` (seat code
inside the designation); `X . Models …` and `X. Model …` spacing variants in
"(cont'd)" lines. Schema validation does catch the bad categories (4 across both runs), which
is the safety net working, but the model is lost rather than corrected.

**B3. Certification Basis label variants.** Seen: `Certification Basis`,
`Certification Basis:`, `Certification Basis.` (PC-12), a doubled
`Certification Basis:  Certification Basis: …` (Kodiak), `Certification Basis
(NOTE 16)` (PC-12 47E, a second basis mid-block). Corpus: 7 TCDS have no label at
all.

**B4. Some TCDS have no certification basis.** Air Tractor A17SW (Restricted
category) has only "Production Basis". `certification_basis` requires ≥1 entry,
so these cannot be represented without a placeholder (which is what A7 does).
A schema/product decision, not a parser bug; needs an explicit answer.

**B5. Cert-basis end markers cut short or run long.** Only the first label
match in a block is used; a second basis in the same block (PC-12 47E; 3A12's
"Data Pertinent to Model 172R" repeated with "(cont'd)") is ignored. A8SO's
basis appears after the *last* model and is common to all, so only S-2C would
have received it (§A4).

### C. Loud failures: stage 2 (tokenisation)

**C1. Only two tokenisers, and the detector is a one-regex heuristic.** Layouts
that produced **0 entries** in "bullet" mode, because there is no `- ` bullet:
- `1)` / `2)` numbering (PC-24, PC-12, ×5 models), with `(a)` sub-items;
- unmarked paragraphs in the label column (KC-100, P2006T, Kodiak 100/200);
- `1.` lists indented past column 8 (Bristell: 29; Cessna 208: 27) — `detect_mode`
  requires `^\s{0,8}\d+\.`;
- "pertinent-to-all" with sub-labels (Cirrus `Model SR20:` etc.; known).
Unlike A7, the tokenisers do warn, but only after the model has already been
reduced to a placeholder.

**C2. Table-style additions** (PC-12 `14 CFR 23, (23-43) 23.1305(c3)`; 525B
"Additions (525B0057 …) Amendment Regulation No. Title Level 23.1306 …" folded
into one entry with the column headings inline) are not tokenised as rows.

### D. Header and metadata

| Issue | Seen in | Effect |
|---|---|---|
| Holder regex needs `Type Certificate Holder␣␣Name` | PC-24 (`…Holder Record:`), PC-12 (`Holder.`), Kodiak, E1000 (no line) | manufacturer `Unknown` → `unknown/` dir and an `Unknown` manufacturer row in the DB. Corpus: 30 of 201 |
| Date parser needs `Month D, YYYY` in the first 2000 chars | A8SO `18 FEB 2026`, A4SW `Aug 06, 2024`, A00076CE `Septermber 09, 2025`, Cessna 3A10/3A13/3A20/3A21 (long model list pushes the date past 2000 chars) | `revision_date: null`, no warning (the catalogue-mismatch warning needs both dates). Corpus: 12 of 201 |
| Revision regex needs the word `Revision` | A19SO `Revison 23` (FAA typo), A4SW `Rev. No. 44` | `revision: null`; only a "not in catalogue" warning. Corpus: 9 of 201 |
| `source_url` | any with null revision | left null |

### E. Process and contract

- **Exit code and report vs. staging.** Any warning gives exit 1, including
  harmless ones; a placeholder write gives `models: 1 entries: 0 warnings: 2`
  and exit 1, but the file is staged anyway. There is no "nothing staged"
  signal.
- **Rev mismatch with existing data.** `data/aircraft/cessna-aircraft-company/172.json`
  carries 3A12 **rev 42**; staging rev 89 fails `build.py` ("TCDS 3A12 metadata
  … conflicts with an earlier file's"). Correct by design, but it means
  re-parsing a current TCDS cannot be promoted next to older models of the same
  TCDS. It needs a rule (replace-all per TCDS number) before any pre-existing TCDS
  is re-done. Also manufacturer naming: the existing file is "Cessna Aircraft
  Company"; the current TCDS says "Textron Aviation Inc.", so a re-parse would
  create a second `172` under a different manufacturer directory.
- **Same slug, two TCDS.** `da-62` is staged twice, under
  `diamond-aircraft-industries-gmbh/` (from A57CE) and `-inc/` (from A00012NY).
  Legitimate (different holders), but a reviewer promoting by model name could
  miss it.
- **Known and unchanged by this run:** aircraft files still have no
  `provenance`; serial applicability is still verbatim text; JAR and
  "equivalent to" bases are still unresolved (DA 40/42/62). Cirrus-style
  "additions" cannot be layered on a base line.

## What worked

- A57CE, A1WI, A00012NY and A60EU parse without warnings (but see A2, A6 and the
  DA 42 items). The DA 40 path was not touched.
- Schema validation caught four bad categories (one in the unmodified run, three
  once headings were widened); `build.py` caught the 3A12 revision conflict. These two are doing their jobs.
- `raw_reference` was kept verbatim in every staged entry I read.
- PDF → text and page-furniture stripping were not the problem on any of the 20.

## Suggested order for the refactor (value vs. risk)

1. A1 (regex digit-stealing) and A7 (never stage a placeholder): small, and
   stop silent wrong data. Write both as failing tests first.
2. A2 (classify order: check for Part citation before SC/Exemption/ELOS substrings).
3. B1/B2 (heading regex and category parsing): the largest unlock (105 → ~181 TCDS
   reach stage 2), but it exposes A4/A5 and C2 on all of them, so do it together with
   the coverage report so the new failures are counted, not discovered.
4. C2 tokenisers (`1)`, unmarked prose, wide-indent numbering) and A4 (group basis).
5. A5 (cover-list reconciliation) as a report column, since it is cheap and catches
   whole classes of silent loss.
6. A6 (variant scope) needs the Q-04 design decision on serial applicability first.

## Not done

- Did not verify any staged entry against the PDF beyond the ones quoted here.
  The four "clean" TCDS were spot-checked (TBM, DA 62, DA 42/NG, 525B/C), not
  audited line by line.
- Corpus counts in §B/D are heuristics over `pdftotext -layout` text, not parser
  runs; they weight issues, they are not coverage.
- No fixes, tests or doc changes were made, per the request.
- Scratch scripts (`dbg.py`, `patched_run.py`, `probe.py`, `corpus.py`) are in the
  session scratchpad, not the repo.
