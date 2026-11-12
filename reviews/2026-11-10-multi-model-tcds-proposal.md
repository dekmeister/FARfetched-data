# Multi-model TCDS: design proposal (towards Boeing 737, A16WE Rev 82)

Status (2026-11-12): **steps 1–2 done; step 3 done, awaiting review.** The
blockers Q1–Q7 are decided and built
([2026-11-12-multi-model-blockers.md](2026-11-12-multi-model-blockers.md)), A2NM's
four goldens are read against [the A2NM reading](2026-11-11-a2nm-reading.md).
Nothing of 2026-11-12 is committed or promoted. Steps 4–10 not started. A16WE
and A2NM are not in `tools/overrides/faa_tcds_selection.tsv`.

## Handover

### Decisions taken (2026-11-11)

- **D1: (a), copy per model, but with §2 rule 4 dropped.** `display_order`
  stays 1..N per TCB; a shared line may have a different number on each model.
  Numbering by position in the whole TCDS would renumber published
  multi-model TCDS (3A12) and break app anchors, and nothing reads the number
  across models. Rule 4 and the "gaps are allowed" doc change are withdrawn.
- **D2: yes.** The 17 heading designations are the models; BCF/IGW are
  `applicability` on -800/-700.
- **D3: yes.** The -200C takes the "737-100 & 737-200 Series" basis through a
  reviewed `tcds_model_groups.tsv` row (written at step 8, with the evidence).
- D4–D7: ask at the steps they affect (D7 at step 4, D4/D5 at step 7, D6 at 10).

### Step 1, done: the decision recorded

`docs/DATA_FORMAT.md` (aircraft section: what a model is, a shared line is
copied per model, `display_order` 1..N per TCB) and `docs/SCHEMA_HISTORY.md`
(standing decision "A shared basis is copied per model", no version row).

### Step 2, done: heading shapes, footers, sequence guard

In `tools/s02_emit/faa/tcds/`:

- `sections.py`: `HEADING_RE` takes no separator before "Model" (A16WE
  `VIII Model 737-700C`), `I-Model` (A4SW), indent ≤16 before "Model" (≤8
  otherwise), numerals up to 8 letters (`XXXVIII`); `_joined_heading` joins a
  heading wrapped inside a parenthesis or after a comma (not over a `Model X`
  line); `_dated_list` reads "737-600 (Approved …), 737-700 (Approved …)";
  `_repeats` drops page-top repeats (same numeral, no new designation);
  `numeral_gaps`.
- `header.py`: one-sided footers (`A16WE   62`, `47   A16WE`).
- `parse.py`: cover " Series" matches a heading; the sequence guard
  (now `attach.sequence_guard`) refuses the section before a numeral gap.
- Tests: `s99_tests/emit/faa/tcds/test_stages.py` (heading shapes, gap guard,
  footers). Docs: `s00_docs/FAA_TCDS.md` (Rules, Page furniture).
- Evidence: a scan of all 1,506 FAA TCDS before and after (every heading
  change read); no selected TCDS changed; compare_stages showed only
  A00007SE's stripped text losing 6 footer lines. A16WE: 17 of 17 headings,
  the -600/-700/-800 each hold one headline, no footer entries (scratch only,
  not read against the PDF). 22 TCDS still have gaps: TCDS-14
  (`issues/faa-tcds.md`, new); TCDS-5 marked narrowed.

### Step 3, built, blocked: shared blocks with per-line model sets

In `tools/s02_emit/faa/tcds/`:

| Module | What it does |
|---|---|
| `segments.py` | `BASIS_LABEL_RE` takes "Certification Basis for <models>:" (`find_scoped_blocks` → `BasisBlock.scope`; capitalised and with a digit, so A25SO's wrapped prose "certification basis for installation specific items only is:" isn't one). "NOTES APPLY …" ends a block. `For X:` sub-labels. Family headers as sentences (`_family_sentence`, capital first letter; "(for X)" scopes the segment). |
| `sections.py` | `expand_group`: `757-200/200CB/-200PF` → three models; leading "Model(s)", trailing "Series" dropped; every token must be a heading. |
| `attach.py` (new, from `parse.py`) | `model_lines`, `block_models` (label scope, or a `tcds_model_groups.tsv` row; bad, redundant or stale rows are fatal), `_keeps` (a line leaves the models it doesn't name, except a name after "same as" / "unchanged from" / "derivative product from"), `sequence_guard`. |
| `lists.py` (new) | Item lists under a family header: an item starts at a section number (ELOS/SC) or "Exemption No." / "Partial …" (exemptions), unless the line before runs on. Fewer than two starts: the old paragraph reading. |
| `amdt_table.py` (new) | "SECTION NO. / TITLE / AT AMDT. 25.-" rows: one entry each, `reading` "25.101 thru Amendment 25-92"; two-level cells give two entries; "not part of the TC basis" gives `[]`; the "exceptions listed below" headline gets an exclude per section-level row. Brought forward from step 7. |
| `tokens.py` | `Line.reading` (what to interpret instead of `raw`), `Line.exclude`, `Line.kind` (entry type fixed by position). |
| `payload.py` | `_references`: uses `reading`, merges `exclude` only into a single whole-document include, else `partial`. |
| `layout.py` | Runs `amdt_table` and `tokenize_items`. |

Also: `tools/s00_common/tcds.py` (`ModelGroup`, `load_model_groups`),
`tools/overrides/tcds_model_groups.tsv` (header only), docs in
`s00_docs/FAA_TCDS.md` (Rules) and `s00_docs/PIPELINE.md` (overrides table),
tests in `s99_tests/emit/faa/tcds/test_shared_blocks.py` (21 tests).

Evidence:

- A2NM read against all 13 pages (pp. 2–5 by text search): every line on the
  right models. Checklist and the questions: [2026-11-11-a2nm-reading.md](2026-11-11-a2nm-reading.md).
- compare_stages, selected TCDS: one change, a correction. A25SO PA-46R-350T
  gains its base line ("For those portions … unchanged from the Model
  PA-46-350P: FAR Part 23 … 23-25; FAR 25.783(e) …; FAR 25.831(c) and (d)
  …"), which the old rule dropped; read on the rendered p. 15. Published
  `data/` lacks it until the next promotion.
- A rule tried and backed out: keeping any line that names only models
  outside its segment put PA-44-180 lines on the PA-44-180T (A19SO).

**Unblocked 2026-11-12** (decisions and detail in
[2026-11-12-multi-model-blockers.md](2026-11-12-multi-model-blockers.md)):

| Change | Where |
|---|---|
| Category from a reviewed row, never inferred (FAA and EASA; EASA's Part 25 inference removed) | `s00_common/tcds_categories.py`, `overrides/tcds_categories.tsv` (26 rows, drafted from text, **to review**) |
| Headline guard: two whole-Part levels of one airworthiness Part, same `applicability`, refuse the model (FAA and EASA) | `s00_common/tcds_guard.py`, both `parse.py` |
| Slash lists in line scope ("For 737-100/-200/-200C/…:"); an unreadable list refuses the model instead of reaching all | `sections.complete_designation`, `scope_models`, `attach._keeps`, `ModelBasis.refused` |
| Two-level cells split only on the "two amendment levels are shown" footnote; the note goes to `applicability_notes` | `amdt_table.py`, `layout.py`, `tokens.Line.notes`, `payload.py` |
| A2NM golden: fixture text, catalogue row, Part 25 in the golden document set | `s99_tests/fixtures/tcds/A2NM_Rev32*`, `test_golden.py` |
| Tests | `s99_tests/common/test_tcds_categories.py`, `test_tcds_guard.py`; `emit/faa/tcds/test_shared_blocks.py`; `emit/easa/tcds/test_golden.py` |
| Docs | parent `docs/DATA_FORMAT.md` (`categories`); `s00_docs/FAA_TCDS.md`, `EASA_TCDS.md`, `PIPELINE.md` |
| Issues | ETCDS-12 closed; ETCDS-16 extended (6 more models refused); new ETCDS-17, TCDS-15, TCDS-16; TCDS-5 re-count |

compare_stages: no FAA staged change. EASA: 7 models refused by the guard
(A330-743L, A330-841, 680A, G280, GVII-G500, GVII-G600, C-212-EE), MD-90-30
newly staged. `uv run pytest` (fast and slow), `ruff check .` pass. `mypy .`
reports only leftover `tools/out/compare_stages_*` copies.

**Open from step 3:**

- Your review of the 26 category rows and the four A2NM goldens.
- Whether A2NM joins `faa_tcds_selection.tsv` (then promote with the EASA
  removals above).
- 25.813 "75, 88\*\*\*" needs a step 4 `tcds_entries.tsv` row: one entry,
  `{813, to 25-88}` plus `{813, paragraph "(c)", to 25-75}`, evidence footnote
  \*\*\*.
- The headline guard reads resolved references only. A headline left
  `partial` (A2NM 757-200 line 1, "Federal Aviation Regulations (FAR) Part 25
  with Amendments …") isn't counted. The interpreter would need to flag a
  whole-Part line even when partial.
- Step 10: line scope isn't applied inside a multi-model *model* section, only
  in "Data Pertinent" blocks. So the A16WE MAX models each take all three
  headline sentences ("The certification basis for the 737-8 and 737-9
  airplanes is …"), and the guard refuses all five.

### How to check this work

- Parse into scratch, never `tools/out/`:
  `uv run python -m tools.s02_emit.faa.tcds.parse input/TCDS/FAA/A2NM_Rev32.pdf --out-dir <scratch>/out --report-dir <scratch>/rep`
- See A2NM's entries despite Q1: call `parse.parse_tcds_text` after replacing
  `sections._designations_from_heading` with a wrapper that gives
  `["transport"]` when the categories are empty (scratch script only).
- Corpus heading scan: `pdftotext -layout` every `input/TCDS/FAA/*.pdf` into
  scratch, then run `segment_sections` / `numeral_gaps` /
  `find_scoped_blocks` per file.
- `uv run python -m tools.s99_tests.compare_stages` takes 2–5 minutes.
- Render pages to read: `pdftoppm -r 100 -png -f N -l N <pdf> <scratch>/p`.

### Gotchas

- **Other agents work in this tree.** On 2026-11-11 the EASA TCDS parser,
  `s02_emit/aircraft/assemble.py`, `s00_common/names.py` and
  `overrides/manufacturers.tsv` were changed by others, and `data/documents/caa/car-3/`
  and `issues/roadmap.md` too. Their changes show in compare_stages (EASA
  entries, manufacturer slugs such as `b-lkow-…` → `bolkow-…`); don't take
  them for this work, and don't revert them.
- `tools/` is its own git repo. Files of this work (committed in tools
  4958b93 and parent 650c122):
  parent `docs/DATA_FORMAT.md`, `docs/SCHEMA_HISTORY.md`,
  `issues/faa-tcds.md`, `reviews/2026-11-10-multi-model-tcds-proposal.md`,
  `reviews/2026-11-11-a2nm-reading.md`, `reviews/PROMPT_multi_model_blockers.md`;
  `tools/`: `s00_common/tcds.py`, `s00_docs/FAA_TCDS.md`, `s00_docs/PIPELINE.md`,
  `overrides/tcds_model_groups.tsv`, and in `s02_emit/faa/tcds/` `attach.py`,
  `amdt_table.py`, `lists.py`, `header.py`, `layout.py`, `parse.py`,
  `payload.py`, `sections.py`, `segments.py`, `tokens.py`, plus
  `s99_tests/emit/faa/tcds/test_stages.py`, `test_shared_blocks.py`.
- `test_da40_golden_is_the_promoted_file` failed for a while (data/ had
  `common_name` from an EASA link); it passed again by the end, presumably
  fixed by another agent. `mypy .` reports errors inside leftover
  `tools/out/compare_stages_*` copies; they are not source.
- Relative designations in line scope are read since 2026-11-12 (Q7).

### Changed from the plan below

- §2 rule 1 is narrower: a line leaves the models it doesn't name, except a
  name in reference wording (see `_keeps`).
- §2 rule 5's "more than one headline basis" guard is not built: counting
  basis blocks is no proxy (selected A00003SE and A78EU have two). It needs a
  definition of a headline line.
- Table parsing for "AT AMDT." tables came forward from step 7. Step 7 keeps
  `pdf_grid.py` for merged-cell grids (737 MAX Table A-1).
- The proposed footer issue is not needed (fixed). The missed-heading issue
  became TCDS-14. The `F25.3` appendix issue waits for step 7.

The proposal as reviewed follows. Nothing below this line was edited.

**What was read against the source, and what was not.** Read in the `pdftotext`
text of A16WE: the cover, Section I, the whole Original/Classic basis (pp. 17–21),
Section VII basis parts A–E (pp. 34–42), the start of Table A-1 and pp. 80–82. Seen
as rendered images: pp. 73 and 81 only. Sections VIII, IX, X and most of A-1 were
located and sampled, not read line by line. The EASA 737 (IM.A.120) was read for
structure only. Candidates in §5 were read at their basis blocks only. Nothing in
this file should be taken as a reviewed transcription.

## 1. A16WE: your observations, re-checked

| Observation | Result |
|---|---|
| 3 of 8 headings staged; -200, -200C, -300, -400, -500 "no certification basis" | Confirmed |
| Classic/Original basis sits in separate group blocks | Confirmed. pp. 17–21 under one "DATA PERTINENT" section, three blocks |
| -600/-700/-800 share a block | Confirmed: heading VII names all three, each with its own approval date |
| MAX: one Table A-1, a column per model | Confirmed; only the -8 came out |
| "Model" tables keyed by customer code | Confirmed for I–X. MAX is keyed by designation (737-8 …) |
| 16 cover designations unmatched | **Misleading.** 7 differ only by the cover's " Series" suffix (-200, -200C, -300, -400, -500, -600, -900ER). 9 are really missing |
| 95/108 regulation lines without references, 165/325 `other` | Numbers confirmed, but they measure the mis-parse (see below). Don't use them as a baseline |

**The staged 737-600 is wrong.** Its 144 entries contain three "A. 14 CFR Part 25 …"
headlines: 25-77 (Section VII), 25-91 (VIII, the -700C) and 25-91 (IX, the -900).
`VIII Model 737-700C` and `IX Model 737-900` have no `.`/`-` after the numeral, so
`HEADING_RE` misses them and their text runs into Section VII. The parser reported
no warning about this. Page footers also became entries (`A16WE 62`, `47 A16WE`).

The 9 missing designations have three causes:

- -100: heading indented 11 columns on page 1 (the regex allows 8).
- -700C, -900: no separator after the numeral.
- -700, -800, -9, -8200, -7, -10: a list where each model has its own
  `(Approved …)`.

Swallowed headings are not only a 737 problem. A scan of the current corpus found
29 TCDS with a numbered model heading the parser did not take (A17WE, A22WE XI,
A23NM, H1SW, H3WE and others). None is in the FAA selection list, so nothing
published is affected.

**Scope crosses the group blocks.** This drives the recommendation below. Inside
the "(737-400 and 737-500 Series Airplanes)" block (pp. 20–21):

- "For 737-100/-200/-200C/-300/-400/-500: 14 CFR §25.1415(d)"
- "For 737-200/-200C/-300/-400/-500: 14 CFR §25.901(c)"
- "Compliance with the following optional requirements has been established for
  all Models"

So the unit of sharing is the **line**, not the section.

## 2. Representation (Q1)

**Recommendation: (a), one `tcb` per model, with the shared lines copied to each
model the line applies to.** The parser holds a shared block once, with a model set
per line, and materialises it per model. Nothing in the SQLite contract changes.

| | (a) copy per model | (b) shared basis referenced by models | (c) one record per section |
|---|---|---|---|
| JSON schema | None | New shared object, plus a per-line model mask (needed anyway, §1) | `model_designation` becomes a list or a compound name |
| SQLite | None; **no `SCHEMA_VERSION` bump** | New tables, v12. `tcb → basis set` | Breaks `UNIQUE (manufacturer_id, model_designation)` semantics, v12 |
| Build | None. Row growth only | Resolution and v11 citations both assume an entry has one TCB (`version_basis` reads "the entry's TCB") | Unclear what a citation's basis means |
| App | None. `list_basis_entries` works by `tcb_id` | Query and export rewrite, and `SUPPORTED_SCHEMA` | Search for "737-800" misses; link rows by designation break |
| Fit to A-1 (per-model amendments) | Fits: each model has its own refs | Needs per-model overrides on shared lines | Cannot represent it |
| Traceability | Same verbatim `raw_reference` on each model | Good | Good for the section, none per model |

Rejected (b) because the sharing it saves is what the line-level scoping breaks, and
it costs a contract change and an app release for a saving of disk only. Rejected
(c) because it contradicts "one file per type-certificated model variant", and the
same section already holds different amendment levels per model.

(a) is also what the data already does: 1,301 of today's 4,410 entries are copies
of the same line on another model of the same TCDS (3A12's "Data Pertinent" blocks
and many EASA TCDS). The cost is size. An estimate for the 737 is 4,000–4,500
entries, about double today's total, and about 10% more `cert_basis_resolved` rows.
The DB is 52 MB and read-only, so this is acceptable.

**Materialisation rules** (tools only):

1. A line is copied to the models its own scope names. Existing rule: a line that
   names designations is dropped from models it doesn't name.
2. A group heading or wrapper is expanded only when every token matches a heading
   designation on that TCDS (`737-200/200C/300`, `757-200/200CB/-200PF`). Anything
   else is reported and the block stays unattached. A reviewed row can decide it
   (`overrides/tcds_model_groups.tsv`: `tcds`, verbatim label, models, evidence),
   the same pattern as `aircraft_links.tsv`.
3. `raw_reference` is the verbatim line, identical on every model. The group label
   goes in `applicability`, as multi-model sub-labels already do.
4. `display_order` is assigned once on the shared block and kept on every copy, so
   the same line has the same number on each model. Gaps are legal (DDL is `>= 1`,
   unique per TCB) and the app only sorts and anchors by it.
5. A guard fails loud when a model section holds more than one headline basis, or
   when roman numerals in the section sequence skip a value. This is what would
   have caught the -600.

Needs one docs change: DATA_FORMAT says "one entry per TCDS line, in TCDS order". It
should add that a shared line is copied per model and that gaps are allowed. Record
the decision under "Standing design decisions" in SCHEMA_HISTORY, with no version row.

## 3. What is a "model" on the 737 (Q2)

**The unit is the section-heading designation: 17 models**, 737-100 through 737-10,
the same as the cover once " Series" is stripped. Slugs don't collide (737-8 and
737-800 differ).

- The TCDS headings say "Model 737-300"; the basis blocks say "737-300 Series
  Airplanes"; the cover says "737-300 Series". NOTE 5 defines 737-105 as the "-100
  Series" plus a customer code.
- Customer-coded variants (737-317) appear only in the eligible-serial tables. A
  grep of every basis range finds **no customer code scoping any basis line**.
- EASA IM.A.120 agrees on the unit: "For Models: 737-100 … 737-900ER", 737-8 …, with
  customer codes only as first-validation examples.
- 737-800BCF and 737-700IGW are configurations, printed as "Additional cert basis
  items for" a model. They are `applicability` on -800 and -700, not models. EASA
  brackets the BCF on its cover too.

## 4. Table A-1 and scoped lines (Q3, Q4)

**A-1 is a table parse from PDF geometry, not from text.** `pdftotext` cannot tell a
merged cell across models from a single-column cell. The PDF draws real cell rules,
and `pdftocairo -svg` (poppler, already a dependency) exposes them.

A prototype on pp. 72–106 recovered 600 rows, 90 of which vary by model. It agreed
with every row checked by eye on pp. 73 and 81 (25.111, 25.809, 25.831(b),(c)).
Cell values: 2,081 amendments, 509 `N/A`, 60 `NA`, 10 `(See Note)`, 340 blank.

Proposed: a reusable `s00_common/pdf_grid.py` extractor, plus a cross-check by a
second method (cell tiling from word centres) that fails loud on disagreement.
Reviewed override rows handle the residue only. They never change `raw_reference`.

| Case | Treatment |
|---|---|
| Amendment in a model's cell | Entry for that model, scoped ref `to: 25-N`, section and paragraph from the row |
| Row headline ("25.125 Landing") with sub-rows | Sub-rows are the entries |
| `NA` ("No Amendment", with ADRC) | Entry, `references: []`, kept verbatim |
| `N/A` | Decision 4 |
| Blank cell | No entry for that model |
| System/Area and Notes columns | `applicability`, verbatim |
| Which cell this model read | `applicability_notes`: "Table A-1, column 737-8200" |
| Source typo `24.143(j)` | `raw_reference` kept; reference needs an override row |
| Appendix rows (`F25.3`) | Dataset has one provision `F25`, so `references: []` at first |

Whole-part headlines. The 737-8 line ("25-0 through 25-137, plus 25-141 with
exceptions") must not expand, or the resolved basis would hold each section at two
levels. A-1 lists **every** numeric Part 25 section in force at 25-141 and 25-146
(402 of 402, checked against `data/`), so the headline gets `references: []`. For
Section VII ("through 25-77 with the exceptions listed below") the exceptions are a
partial list. There the headline keeps the include ref plus an `exclude` for each
section-level exception, and each table row is its own entry. `exclude` takes no
paragraph, so paragraph-level rows (25.783(f)) stay as paragraph refs. A row with
two levels (`0, 77**`) becomes two entries, because one entry may not hold one
provision at two versions.

**Scoped lines.** Line-level scope comes in four kinds on the 737, and all fit
today's fields:

- all models in the block;
- a named series ("For 737-400 and 737-500 only"): used to filter, kept in `applicability`;
- a configuration (winglets, IGW, BCF, LCA): `applicability`;
- a line-number or service-bulletin condition (part B: "line #'s 2517, 2620 and on
  or as a modification per Service Bulletins"): `applicability`.

So this does **not** force ROADMAP-5. Most of the scope isn't serial ranges at all,
so structured serials would not express it.

## 5. Staging path (Q5)

| Candidate | Why | Today |
|---|---|---|
| **FAA A2NM** (757), 13 pp, 4 models. **Do first** | Same holder and shape as the Classics: "Certification Basis for 757-200/200CB/-200PF", "For 757-300", in one pertinent section. 757-300 has an exceptions table, `85*`, and "not part of the TC basis" | 0 of 4 staged, all "no basis" |
| FAA A16NM (Astra/G100/G150), 14 pp, 4 models | "Data Pertinent to all Models except G150", and a G150 block that reads "same as the Model G100". Has a single-model AMDT table for the grid extractor | 0 of 4 |
| EASA.IM.A.503 (C90A/GT/GTi), 23 pp, 3 models in one section | Smallest ETCDS-7 shape: a common basis plus "For C90A – Additional …" lines | "several models" |

Considered and set aside for later: EASA.A.010 TBM 700 and A43NM with EASA.A.015
(A340), which is a good test of FAA series against EASA variant linking. TBM is not
a shared-section case: see the correction under ETCDS-6.

Sequence: A2NM → A16NM → IM.A.503 → 737 Classic → NG → MAX (detail in §7).

## 6. Verification (Q6)

A clean parse, passing tests and `identical` show only that the pipeline ran.

**First TCDS (A2NM).** Render all 13 pages to images and read them. Fill a checklist
in `reviews/` with one row per TCDS basis line (line, models claimed, models per the
PDF, `references` meaning, verdict). Mechanical aids may narrow the work, never
replace it: every `raw_reference` must be a substring of the PDF text, and every
PDF basis line must appear on some model. Read the expansion for one provision per
reference on each model in the built DB. Only rows actually read may be marked
checked.

**737, in three gates**, each promoted separately:

- Classic: read pp. 17–21 and every line's model set against the blocks. Six models,
  about 200 lines, all read.
- NG: read every table row of VII–X, once per model, including parts C–E. The
  -600/-700/-800 split is where the current parser is wrong.
- MAX: both grid methods must agree. Read all 90 model-varying rows against rendered
  pages, plus a random 5% of uniform rows (about 25). Read all `NA`, `(See Note)` and
  appendix rows. The sample rate is Decision 6.

Failures found are fixed in the extractor or by an evidence override, then the
affected gate is re-read. After promotion, `build.py` and `compare_stages` show
reproducibility only.

## 7. Sequence

No step changes the SQLite contract. All steps run on `main`, and each is your
review before the next.

| # | Step | Tests | Docs |
|---|---|---|---|
| 1 | Record the decision | None (docs only) | DATA_FORMAT, SCHEMA_HISTORY |
| 2 | Heading fixes and the section guard (§2 rule 5); footer formats | Unit tests per heading shape; `compare_stages` shows no change for selected TCDS | FAA_TCDS |
| 3 | Shared block with per-line model sets; `tcds_model_groups.tsv`; proven on A2NM | Unit, `golden` for 4 models, scope-crossing line, unmatched group refused | FAA_TCDS, PIPELINE (override) |
| 4 | Aircraft entry corrections (TCDS-2): `tcds_entries.tsv`, keyed like `tcds_citations.tsv` (`line_sha`, action, evidence). Actions: drop furniture, set type, set references, scope models. Never `raw_reference` | Unit: stale row fails, `raw_reference` unchanged | FAA_TCDS, PIPELINE |
| 5 | A16NM: "except" scopes, a block that refers to another block | Golden | FAA_TCDS |
| 6 | EASA port of the shared block; IM.A.503, then IM.A.071 and IM.A.188 | EASA goldens | EASA_TCDS |
| 7 | `pdf_grid.py`, exclude-plus-rows headlines; proven on A16NM's table | Grid unit tests against a small fixture, second-method check | FAA_TCDS |
| 8 | 737 Classic, reviewed, added to the selection list | Golden for -300; §6 read | FAA_TCDS |
| 9 | 737 NG, reviewed | Goldens; §6 read | |
| 10 | 737 MAX, reviewed | Golden for -8 and -8200; §6 read | |

## 8. Issues

| ID | Effect |
|---|---|
| ETCDS-6 | **Closes** the inheritance rule at step 6. Correct its text: TBM 700's Section A holds category and holder only, the basis is in B.II keyed by variant, and the parser now reports "no category" |
| ETCDS-7 | **Narrows.** Same rule, but each TCDS still needs its model list read (A.004 and others) |
| TCDS-5 | **Narrows.** Fixes the heading shapes above; the " Series" suffix alone explains only 3 TCDS in the corpus |
| TCDS-3 | **Leaves.** A16WE has no duplicates. A3EU's 83 are a separate continuation-heading shape |
| TCDS-1 | **Closes** by decision if you accept option (a), verbatim scoped entries |
| ROADMAP-5 | **Leaves**; not forced (§4) |
| TCDS-2 | **Closes** at step 4; the parser is the only route today |
| TCDS-10 | **Leaves.** No 737 slug collisions. An EASA 737 link needs review later |
| TCDS-13 | **Context.** Parts 26 and 34 aren't in the dataset (Part 36 and Part 25 to 25-153 are), so the 737 adds lines that stay unresolved |
| TCDS-12, ETCDS-15 | **Leaves**, adds cases of the same kind ("36-20 or any subsequent amendment"; "14 CFR Part 36 of the Federal Aviation Regulations") |

Proposed new issues:

- `faa-tcds.md`: model headings the parser misses, whose text merges into the
  previous model (29 TCDS scanned).
- `faa-tcds.md`: page footers `A16WE N` and `N A16WE` reach entries.
- `faa-tcds.md`: appendix rows (`F25.3`) have no mapping to the single `F25`
  provision.
- `easa-tcds.md`: TBM 700 is a variant-keyed basis table (replaces the ETCDS-6 example).

## 9. Decisions needed from you

1. Do you accept (a), copying per model with `display_order` kept across copies and
   no contract change? (Recommended.)
2. Are the 17 heading designations the models, with BCF and IGW as `applicability`
   on -800 and -700? (Recommended.)
3. Does the -200C take the "737-100 & 737-200 Series" basis? The block heading
   doesn't name it, though the enclosing section heading and the special conditions
   do. I'd put it in by a reviewed group row with that evidence.
4. For an `N/A` cell in A-1, do you want an `other` entry with `references: []`
   (recommended: 509 statements stay visible) or no entry?
5. Should the A-1 headline stay at `references: []`, with the rows as the basis?
   (Recommended; the whole-part reference would double-claim sections.)
6. Is 90 varying rows plus a 5% sample enough reading for MAX, or do you want all
   600 rows read?
7. Should TCDS-2's corrections file be built up front (step 4), or only when the
   first reviewed error needs it? I'd build it at step 4, because A2NM's reading is
   likely to need it.
