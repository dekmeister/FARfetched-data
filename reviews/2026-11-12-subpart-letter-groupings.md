# Subpart letters in grouping headings (all documents)

Date: 2026-11-12. Status: **implemented, promoted and committed**
(tools `56b8ddc`, then the data repo and the app). Open: the app release and
the answer to GitHub #19 (§6, "Left"). The open items are in ISSUES.md.

Trigger: GitHub #19 (14 CFR 36, open). The live issue text is a reader's
comment from the site's report button: *"Mix of section headings, letters and
subpart names makes it difficult to read properly."* Data build `ad4ef73`,
schema 11. That build came before `28424af` (reserved subparts promoted as
"Reserved"), so the reader saw names mixed with raw `Subpart C [Reserved]`
labels. This also closes **EASA-16** ("Subpart labels differ in style from
FAA").

Goal (developer): **one grouping style across every document.** The app
already merges a subpart's names across revisions, so renames don't need a
data-side solution.

Read first: CLAUDE.md, tools/CLAUDE.md, docs/DATA_FORMAT.md, docs/SQLITE.md,
docs/SCHEMA_HISTORY.md. The app code is read-only at `../FARfetched` (HEAD
`76dffee`).

**What "checked" means here.** "Read against source" means I opened the local
source copy (DRS JSON in `input/cache/drs/`, eCFR structure JSON in
`input/cache/ecfr/`, `input/regs.csv`, PDFs in `input/Regs/` via
`pdftotext` or a byte grep). Anything marked *unverified* comes from memory
or inference. Nothing was re-downloaded and nothing in `data/` or git was
touched.

---

## Decisions (developer, 2026-11-12)

| # | Decision |
|---|---|
| D1 | **One string, one style, every document:** `{Label} — {Name}` in the existing `current_grouping` / `grouping_at_time` fields (design (a), §5). No new fields, no document-level grouping list. |
| D2 | A reserved subpart is `Subpart C — Reserved`, not eCFR's `Subpart C [Reserved]`, so there is one separator. |
| D3 | **No contract version bump.** No table or type changes. The format rule goes into DATA_FORMAT as contract, with a SCHEMA_HISTORY note, as for the NATO issuer. The app's code works unchanged, so a bump would only force a release. |
| D4 | All appendices are one group, `Appendices` (FAA and EASA change from `Appendix`). |
| D5 | FAA history: `grouping_at_time` stays the present-day label, and DATA_FORMAT says so (FAA-31). No override rows for history. |
| D6 | Part 36 reserved placeholders (36.400, .900, .1000–.1400) stay as they are. Each falls into its own `Subpart X — Reserved` group. §36.1100 is tracked separately (FAA-32). |
| D7 | CAR and MIL-HDBK-516 join the style: CAR `Subpart B — Flight Requirements`, MIL-HDBK `Section 7 — Propulsion`. |
| D8 | Old app group links (`?open=<name>#g-<slug>`) are allowed to break. Low traffic; the app may map old names later if anyone notices. |

D6 and D8 record the defaults offered in the conversation (no change, accept
the break); the developer approved them with the rest.

---

## The style

| Case | Value |
|---|---|
| Subpart (FAA, EASA, NATO, CAR) | `Subpart B — Flight` |
| General | `Subpart A — General` (it is Subpart A in every source) |
| Reserved subpart | `Subpart C — Reserved` |
| SFAR inside a subpart (25.1801) | `Subpart I — Special Federal Aviation Regulations` (it is eCFR Subpart I) |
| MIL-HDBK-516 section | `Section 7 — Propulsion` |
| All appendices | `Appendices` (no label: the group isn't lettered; each appendix's letter is in its key, `A25`) |
| Finer headings (FAA DRS Subject Group, CAR sub-headings, MIL-HDBK parent heading, CS-25 J Part A/B) | `subject_group`, never `current_grouping` |

- **Separator:** an em dash with exactly one space either side. No en dash, no
  hyphen.
- **Label:** as the source prints it: `Subpart` plus letter(s), or `Section`
  plus number.
- **Name casing:** the source's own mixed case where it prints one (FAA DRS
  and eCFR, NATO, newer EASA running headers). Otherwise one shared title-case
  function: small words (a, an, and, as, at, by, for, in, of, on, or, the,
  to) in lower case except first, acronyms and tokens with digits kept (EWIS,
  E3, UA, APU). So `Design and Construction` everywhere.
- **Not covered, for future sources:** SFARs outside any subpart (eCFR
  "Special Federal Aviation Regulation No. 109") would be a letterless group
  `Special Federal Aviation Regulations`. EASA AMC/GM, if ingested, is its
  own document with the same `Subpart X — …` groups. Both get added to the
  allowed list when they arrive.

---

## 1. What each source says

### FAA

| Source | What it holds | Letter? | Read against source |
|---|---|---|---|
| DRS `Subpart/Appendix` (per document, i.e. per section × amendment) | `Subpart E - Powerplant`, `Subpart C [Reserved]`, `Appendix C to Part 25`, `Appendix G--Continuous Gust Design Criteria`, empty for some | Yes, for every subpart label | Yes: all extracted files (`tools/out/extracted/faa/`), and `input/cache/drs/far_doc/F4567343824D03458525668E00557A3A.json` (§36.201@Initial) |
| eCFR structure (`input/cache/ecfr/`, structure JSON 2026-10-30 for 25/27/29, 2026-11-02 for 36, 2017-08-29 for 23) | `identifier: "D"`, `label: "Subpart D—Design and Construction"`, reserved flag, appendix and SFAR nodes | Yes, present-day only | Yes |
| FAA manifest (`tools/out/work/manifest_faa_{part}.tsv`, from eCFR at `--as-of`) | `subpart` = letter; empty for appendices and for sections absent from eCFR | Yes, present-day; blank for removed sections | Yes |
| `input/regs.csv` | `Subpart` = name only (`Flight`, `Appendix`, `Electrical Wiring Interconnection System (EWIS)`), `Subsubpart` = finer heading | **No** | Yes. Also: **no Part 36 rows at all** |

- **The letters agree.** DRS letter = eCFR letter in every case where both
  exist (3,604 documents, 0 mismatches). 125 documents have a DRS letter but
  no eCFR letter: removed sections and reserved placeholders.
- **DRS isn't historical.** Every version of a section carries the same
  label. The only variation is case, in three Part 36 Appendix C rows.
  §36.201 is labelled `Subpart C [Reserved]` at Initial (1969), 36-7, 36-8,
  36-10, 36-12 and 36-15, all with status Historical, yet its 1969 text is an
  active rule ("Compliance with this section must be shown with noise levels
  measured and evaluated as prescribed in Subpart B…").
- **DRS is wrong at least once on the letter.** §36.600@36-14 ("§ 36.699
  [Reserved]", in the 36.6xx = Subpart G range) is labelled `Subpart C
  [Reserved]`. It isn't in `data/` (`empty_text`, deletion rule), but it shows
  that DRS letters for sections absent from eCFR need a cross-check.
- **DRS keeps stale placeholders.** §36.1100 "Reserved." (`Subpart K
  [Reserved]`, Initial) is still status **Current**, but Subpart K has been
  Tiltrotors since 36-29. `data/` has it in force. Under the new style the
  app's merge will show "Subpart K — Tiltrotors / Reserved", which exposes
  this (FAA-32).
- **Part 25 Subpart I is real** (eCFR, holds §25.1801). The eCFR SFAR nodes
  outside subparts (Part 25 No. 13 and No. 109, Part 23 No. 23) are not in
  `data/`.
- **No FAA names before 2017 are local.** eCFR point-in-time starts in 2017,
  and no cached Federal Register document mentions Part 36.
- **Latent bug:** `verify.default_subpart()` and `emit.text_missing_obj()` fall
  back to the manifest/fetch row's `subpart`, which is a **bare letter**
  (`"H"`). None in `data/` today.
- **Where the strip happens:** `tools/s01_extract/faa/regs/verify.py:181`
  `subpart_name()` (extract stage), which writes `current_subpart` /
  `subpart_at_time`. The raw label stays in `drs_metadata["Subpart/Appendix"]`,
  so emit can reformat without a re-extract.

### EASA CS

- The pipeline reads the subpart heading printed in **each consolidation
  PDF** (`cs_parse.py:_subpart_heading`, building
  `f"Subpart {letter} — {title.title()}"`). `grouping_at_time` is
  historical. `current_grouping` is the heading in the newest PDF that prints
  the paragraph (`s02_emit/easa/cs/emit.py:current_grouping`).
- Read against source (`pdftotext` of CS25-0, CS25-26/27/28, CS23-4, CS23-6,
  CS27-10):
  - Old issues print headings in capitals with an en dash; newer ones use
    mixed case in running headers. `.title()` gives `Design And
    Construction`.
  - CS25-0's contents say `…INSTALLATION`, but its body (line 10460) says
    `…INSTALLATIONS`. The pipeline uses the body. Part A/B under Subpart J
    are not captured.
  - CS25-26 prints `…INTERCONNECTION SYSTEM`, CS25-27 and CS25-28
    `…SYSTEMS`.
  - CS-23 Amdt 5+ renames C, E, F and G.
- **Books.** Only Book 1 / CS paragraphs and the CS appendices are in
  `data/`; AMC/GM is not ingested.
- **Appendices** are printed under `APPENDICES` (CS23-4) / `APPENDICES TO
  CS-25` (CS25-28). Each appendix's letter is in its key.

### NATO, MIL-HDBK-516, CAR

- **NATO STANAG 4671:** `Subpart B – UA Flight` (en dash, as printed) and
  `Appendices`.
- **MIL-HDBK-516:** `7. PROPULSION`. Numbers are reused for different
  sections between editions ("10. DIAGNOSTICS SYSTEMS" → "10. AERIAL
  REFUELING"), so the number is a label, not an identity.
- **CAR 3:** `current_grouping` holds the finer heading
  (`s02_emit/car/emit.py:198`, subsubpart before subpart), and the subpart
  name is in `subject_group`; the app swaps the two levels for `car-*`.
  - The CAR source PDFs **do** print letters (byte grep of `input/Regs/CAR/`:
    `Subpart B—Flight Requirements`, `Subpart C—Strength Requirements`, …
    `Subpart H—Identification Data`, A–H).
  - regs.csv has names only, and for `3 (1949)` it has both `General` and
    `Airworthiness Requirements` for one section, so the CAR name → letter
    mapping needs a reviewed lookup with PDF evidence, not a guess.

---

## 2. Letters and names across revisions

Counted over `data/` (every version's `grouping_at_time` plus
`current_grouping`):

| Document | Letter changes | Names per letter |
|---|---|---|
| CS-23 | 0 | C Structure/Structures, E Powerplant/Powerplant Installation, F Equipment/Systems and Equipment, G Operating Limitations and Information/Flight Crew Interface and Other Information |
| CS-25 | 0 | H …System/…Systems (CS25-27), J Gas Turbine Auxiliary Power Unit Installations/Auxiliary Power Unit Installations |
| CS-27, CS-29 | 0 | none |
| NATO 4671 | 0 | B, C, D, E, I "UAV …" → "UA …"; H "data link" → "Data Link" |
| FAA 23/25/27/29/36 | 0 in `data/` | Not knowable: DRS repeats today's label |

Letters are stable and names change, which is exactly what the app's
`merged_grouping_labels` handles: it keys on the label and joins the names.
Part 36's letters follow section number ranges (36.1xx = B … 36.15xx = O).
K went from reserved to Tiltrotors at 36-29 (*unverified:* H at 36-14, F at
36-4).

**Known gaps, accepted:**

- **FAA `grouping_at_time` is present-day** (D5, FAA-31). The app's view of
  Part 36 at 36-0 shows §36.201 under `Subpart C — Reserved`.
- **A rename without a new version isn't in `grouping_at_time`.** The CS-25
  Subpart H provisions have only a CS25-5 version, so the app's view at
  CS25-27 shows "…System" where the PDF prints "…Systems". The merge hides
  this on the current page; it shows only in historical views (EASA-16
  update).

---

## 3. Where the grouping string is used

**Data repo:**

- Schema `["string","null"]`, no pattern.
- Copied verbatim into `provisions.current_grouping` and
  `provision_versions.grouping_at_time` (`certbuild/provisions.py`,
  `ddl.py`). No check reads it; it isn't in sort keys, search or the report.
- Similarity counts `current_grouping` words once (`similarity.py:103`).
  Words need 3+ letters, and "subpart"/"section" exceed the per-document 50%
  boilerplate limit, so they are dropped. Expected identical; **wrong**:
  see §6, verification. Casing doesn't matter (terms are
  lower-cased).
- Tools test `s99_tests/extract/faa/regs/test_extract_manifest.py:161`
  (`test_subpart_name`) pins the stripped names. Parent tests use arbitrary
  strings.

**FARFETCHed app:**

- Groups by the string in `sort_key` order; `_is_appendix` moves
  `appendi…` groups last (`blueprints/regulations.py:24,71-81`).
- `merged_grouping_labels` (`models.py:39-104`): `^(Subpart [A-Z]) — (.+)$`
  merges unconditionally; `^(\d+)\. (.+)$` (MIL-HDBK) merges only related
  names.
- Group URLs `?open=<grouping>#g-<slug>`; the reader header; historical
  view from `grouping_at_time`; basis view; CSV export `grouping` column; the
  `car-*` level swap (`models.py:24`).

---

## 4. Designs considered

- **(a) Letter in the existing string. Chosen.** No new field. It works with
  the app's existing merge, and the build checks the format.
- **(b) Separate label field.** Rejected: a contract change and every file
  rewritten, for a group key the app's merge already derives.
- **(c) Document-level grouping list with names per revision.** Rejected for
  now: a large schema change. Its main benefit (renames) is covered by the
  app's merge; what's left is the historical-view gaps in §2.
- **(d) The build splits the string into label/name columns.** Rejected: a
  contract change with no consumer that needs it.
- **Letters derived in the app.** Rejected: data in the app, and it can't
  see FAA removed/reserved cases.

---

## 5. Contract and docs changes

- **docs/DATA_FORMAT.md:**
  - `current_grouping` / `grouping_at_time` rows point at a new subsection
    "Grouping labels" holding the style table and rules above.
  - `grouping_at_time` gets a note: for FAA it is the present-day label
    (DRS does not record history).
  - `subject_group` gets the finer-heading rule, including CAR.
- **docs/SQLITE.md:** one line under `provisions` pointing at the rule.
  Separately fix the stale "currently **11**" at line 44 (the code is 12).
- **docs/SCHEMA_HISTORY.md:** a note under the table, like the NATO one:
  grouping values follow one style from <date>; no version bump because no
  table or type changed; the app's merge regexes are the consumer that cares.
- **Build check** (`certbuild/sources.py`, run by `load_checked` so `--check`
  has it too; returns `list[str]`, one `_raise_if` line in `pipeline.py`).
  Every non-null `current_grouping` / `grouping_at_time` must be
  - `^(Subpart [A-Z]{1,2}|Section [0-9]+) — (\S.*\S|\S)$`, with a name that
    has a lower-case letter (not printed in capitals) and no ` – ` or ` - `
    separator, or
  - one of the letterless names `Appendices` (later also `Special Federal
    Aviation Regulations`).

  Tests go in `tests/test_validation.py` and `tests/test_build_failures.py`.
  `tests/factories.py`'s default `grouping="A"` and the other test values
  change to valid ones.
- **Schema:** unchanged. A JSON Schema `pattern` would duplicate the build
  check; keep one place.

---

## 6. Plan and what was done

| Step | Status | Where |
|---|---|---|
| 1. Shared formatter | done | `tools/s00_common/grouping.py` (`subpart`, `section`, `heading_case`, `APPENDICES`, `RESERVED`), tests `s99_tests/common/test_grouping.py`; tools/CLAUDE.md code map |
| 2. Build check and docs | done | `certbuild/sources.py` `check_groupings` / `grouping_fault`, run in `load_checked` with the path and text checks; tests in `test_validation.py`, `test_build_failures.py`; DATA_FORMAT §Grouping labels, SQLITE (and the stale "currently 11"), SCHEMA_HISTORY note, CLAUDE.md code map |
| 3. FAA | done | `s00_common/faa/drs_labels.py` (DRS label parser); emit `assign_groupings` (eCFR letter, else DRS; `subpart_mismatch` / `no_subpart` reports; bare-letter fallback gone); extract's `subpart_name` gives the new style (provisional); FAA_REGS.md |
| 4. EASA | done | `cs_parse.py`: `subpart()` (heading case), `Appendices`; EASA_CS.md |
| 5. NATO | done | `extract.py` `subpart_titles` → em dash; NATO_USAR.md |
| 6. CAR | done | `tools/overrides/car_subparts.tsv` (17 rows, evidence per row: CAA 3-1..3-6 print Subpart A "Airworthiness Requirements", 3-7 on and the reissue "General"); emit sets the lettered subpart and moves `Subsubpart` to `subject_group`; CAR.md |
| 7. MIL-HDBK-516 | done | `extract.py` `Section N — Name`; DOD_HDBK.md |
| 8. Promotion | done | 4,941 document files, grouping fields only; `data/promotion.json` documents → tools `56b8ddc` |
| 9. App | done (uncommitted) | `../FARfetched`: `models.py` (`grouping_levels` has no CAR swap; `merged_grouping_labels` merges `Subpart X — …` by letter for every document, CAR included, and `Section N — …` by related names); tests and seed data in the new style. `_is_appendix` left as is: `startswith("appendi")` already covers `Appendices` and an old DB |

Not done as planned:

- `_is_appendix` was not narrowed to `== "Appendices"` (see step 9).
- FAA-33 in the earlier draft (bare-letter fallback) was fixed, not filed.
- 25.343 and 25.345 first re-staged without their 25-72 version: the Part 25
  worklist in `tools/out/work` (2026-11-08) predated the `retroactive` rows
  45–46 in `tools/overrides/faa_regs.tsv` (55 FR 37607 is a correction of
  Amdt 25-72). Re-running the Part 25 manifest and worklist offline fixed
  it; no data problem.

**Verification (2026-11-12):**

- `compare_stages --full --only faa_regs --only easa_cs --only car --only
  dod --only nato`: 21,786 files differ, and every changed field is a
  grouping field (`current_grouping`, `grouping_at_time`, `subject_group`
  for CAR, and the extracted `subpart`/`grouping`/`current_subpart`/
  `subpart_at_time`). No stage's exit status changed. (The user's
  uncommitted TCDS work was kept out with `--only`.)
- Re-staged `tools/out/staged/documents` from the current inputs (EASA,
  NATO, DOD extract; EASA manifest; Part 25 manifest and worklist; every
  document emit). Against `data/`: only grouping fields differ.
- `build.py --check` on today's `data/` fails with 5,112 grouping faults, as
  it must until promotion. The staged documents plus `data/aircraft` pass
  `--check` and build.
- That DB against `data/` built with the committed code: every table is
  identical except the grouping columns (`provisions.current_grouping`
  4,941 rows, `subject_group` 764, `provision_versions.grouping_at_time`
  11,439), the `latest_versions` view (it carries `grouping_at_time`), and
  `provision_similarity`. **Similarity is not identical**, contrary to §3:
  grouping words feed the vectors, and CAR's grouping changed from a topic
  ("Fuel Tanks") to its subpart. 85,237 pairs kept, 2,284 dropped, 2,069
  added (87,521 → 87,306 rows). The slow real-data tests, the similarity
  golden set included, pass against the staged tree (25 passed).
- `pytest -m "not slow"` green in both repos; ruff, ruff format and mypy
  clean on the changed code (mypy's remaining errors are in old
  `tools/out/compare_stages_*` leftovers here and in four app test lines
  this work didn't touch).
- `promote --dry-run`: 4,941 files to accept, 0 new, 0 orphans, no
  version-count flags.

**Left:**

1. Release the app after the data. Old `?open=<name>` links stop matching
   (D8).
2. Answer GitHub #19.
3. Then delete this review in its own commit.

---

## Open items (moved to ISSUES.md)

- **FAA-31** FAA `grouping_at_time` is the present-day DRS label.
- **FAA-32** Part 36 reserved-subpart placeholders and §36.1100 (GitHub #19).
- **EASA-16** rewritten: a subpart renamed without a new version keeps its
  old name in `grouping_at_time`.
- NATO-8, CAR-10 and DOD-9 (proposed in the earlier draft) were not filed:
  the code is done and only the promotion is left, which this review tracks.

When the app release is done and #19 answered, this file can be deleted in
its own commit.
