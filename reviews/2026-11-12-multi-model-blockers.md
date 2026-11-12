# Multi-model TCDS: the step 3 blockers (Q1–Q7)

Exploration for [the multi-model proposal](2026-11-10-multi-model-tcds-proposal.md),
step 3, from [PROMPT_multi_model_blockers.md](PROMPT_multi_model_blockers.md).
Status: **decided and implemented 2026-11-12, awaiting your review** (not
committed, nothing promoted). The recommendations below were written first; the
decisions and what was built follow.

## Decisions (2026-11-12) and what was built

| Q | Decision | Built |
|---|---|---|
| 1 | **Reviewed rows**, not the rule, for both parsers | `tools/s00_common/tcds_categories.py`, `overrides/tcds_categories.tsv` (A2NM + 25 EASA TCDS), EASA inference removed |
| 2 | Defer | TCDS-15 |
| 3 | One item, no change | pinned by the A2NM golden |
| 4 | Split on the two-levels footnote only | `amdt_table.py`, `Line.notes` → `applicability_notes` |
| 5 | Accept | TCDS-16 |
| 6 | Build the guard | `tools/s00_common/tcds_guard.py`, in both parsers |
| 7 | Fix now | `sections.complete_designation`, slash lists in `scope_models`; unread scope refuses the model (`ModelBasis.refused`) |

The 26 category rows were **drafted by the assistant from `pdftotext` text
search**, quoting the TCDS. Only A2NM's was read on rendered pages. They are
yours to review before promotion. Eight of the EASA TCDS do print a category,
where the EASA parser doesn't look (ETCDS-17).

Effect (compare_stages, committed code vs working tree):

- **FAA: no staged file changes.** A2NM isn't in the selection list.
- **EASA:** 8 models leave the staged tree, refused by the guard:
  A330-743L, A330-841, 680A, G280, GVII-G500, GVII-G600, C-212-EE (see
  ETCDS-16). MD-90-30 (IM.A.211) newly stages: its printed category "MD-90:
  JAR 25 Large Aeroplane … FAR 25 Transport Category" wasn't mapped before
  and the row now gives it. No other staged file changes.
- Published `data/` still holds the 7 refused models until the next
  promotion, which would list them as orphans.

Correction to Q6 below: the GVII-G500 and G600 don't pass. "CS 25 Appendix S,
Amendment 19" and "CS 25 Appendix Q Amendment 13" are read as all of CS-25,
and the guard refuses them. I had compared only Part 25 against CS-25.

Corpus scans below are mechanical (regex over `pdftotext -layout` text of the
939 Current aircraft TCDS, run through today's parser). A count from a scan
is **not read against a source** unless the row says it was.

## Summary

| Q | Recommendation | Changes | Published files |
|---|---|---|---|
| 1 | A narrow rule shared with EASA: a single-category airworthiness Part gives the category when none is stated, written to `tcb.notes`. Decide it together with ETCDS-12 | FAA + EASA parser, DATA_FORMAT, two tool docs, tests | FAA: none. EASA: about 20 TCBs gain a note |
| 2 | Don't block step 3. Attach the Part 26 statement later through a narrow label rule, after the 8 TCDS are read | Issue now; parser later | None |
| 3 | One item. No rule change; pin it in the golden | None | None |
| 4 | Split a cell only when its footnote is the "two amendment levels" footnote; the level goes out of `applicability`. 25.813\*\*\* becomes one entry with a paragraph ref, set by a reviewed row | `amdt_table.py`, step 4 row, docs, tests | None |
| 5 | Accept. Leave the row visible with `references: []`, and file an issue | Issue only | None |
| 6 | A headline is a whole-Part include for an airworthiness Part. Fail on two levels with the same `applicability` | `attach`/`payload` guard, tests | None (it flags EASA data) |
| 7 | One reader for designation lists, in `sections.py`, used by both block labels and line scope. Refuse anything it can't complete | `sections.py`, tests | None |

Found along the way, outside the questions (detail under Q6 and Q7):

- The current parser gives every A16WE MAX model all three MAX headline
  sentences (25-141, 25-141, 25-146).
- `scope_models` reads "For 737-100/-200/-200C/-300/-400/-500:" as 737-100
  only.
- Published EASA data holds whole-CS-25 refs at several levels in one TCB
  beyond the known ETCDS-16 (680A, G280, C-212-EE).

---

## Q1. Category when a TCDS states none

**Read.** A2NM text: no "categor" or "transport" anywhere. Pages 1, 7, 8 and 9
rendered (p. 1 by the earlier reading). Basis lines: p. 7 "Federal Aviation
Regulations (FAR) Part 25 with Amendments 25-1 through 25-45 …" and p. 9 "Part 25
as amended by Amendments 25-1 through 25-85 …". In `data/documents/faa/`:
§25.1(a), every version: "airworthiness standards for the issue of type
certificates … for transport category airplanes". Part 25 title: "Airworthiness
Standards: Transport Category Airplanes". §23.1(a): normal, utility, acrobatic
(and commuter, later). §27.1(a): normal category rotorcraft. §29.1(a): transport
category rotorcraft. The DRS catalogue row for A2NM Rev 32 has `Large Airplane`
and `Part 25`. EASA parser `s02_emit/easa/tcds/parse.py:308`, EASA_TCDS.md and
issue ETCDS-12.

**Counts** (scan, not read against the sources). 600 models in 236 TCDS are
skipped with "no category on heading" today. That is not comparable with
TCDS-5's 227: the step 2 heading fixes find more headings, and TCDS-5 doesn't
say what it counted. Kinds:

| Kind | Models | TCDS | Notes |
|---|---|---|---|
| A. Category stated, parser misses it | 94 | ~45 | In the model's own section (43) or elsewhere (51), e.g. A28NM "I. Type A318-100 Series Transport Category Airplanes", A21NM a wrapped "Transport Category", 4A21 "(Transport Aircraft)" on a heading line parsed oddly. A heading/field fix (TCDS-5), not a Q1 rule |
| B. No category word; the basis cites a Part | 383 | 100 | Balloons 255/27 (Part 31: no category in the closed set at all); 21.17(b) special class 10; ~118 airplanes and rotorcraft |
| C. Nothing detected | 123 | 89 | Gliders 65, small airplanes 51, often pre-CAR 3 (A-725 "Type Certificate No. 725 (CAR 4a)") |

Among the B airplanes and rotorcraft, the regex hits for a "single-category
Part" include false positives: CAR 4a TCDS matched "25-" in dates. Checked by
grep only: A2NM (4 models), A1NM 767-400ER and 767-2C (the next Boeing has the
same gap), 1A7 and A-816 (CAR 4b), and about 12 CAR 6 rotorcraft. **A16WE
itself states "Transport Aircraft" on every heading** (pp. 1–65 headings by
grep), so Q1 blocks A2NM as the proof TCDS, not the 737.

**Evidence, under "reproducible is not correct":**

- *The catalogue: no.* It is DRS metadata, not the TCDS. `product_subtype`
  "Large Airplane" is a weight class (over 12,500 lb), not a category: a large
  airplane can be restricted, or Part 23 commuter. `cfr_part_reference` is
  noisy. Of the Current aircraft rows, 606 small and 70 large airplanes have
  it blank, and values include "Part 91", "Part 1" and "Part 15". Use it as a
  lead at most.
- *The Part 25 basis: yes.* It is the TCDS itself plus the regulation it
  cites, both sources. Part 25 admits one category by its own §25.1(a). This
  isn't a correction (nothing on the TCDS is wrong), so the "override row with
  evidence" rule doesn't require a row. It is interpretation, like reading
  "Part 25 through 25-45" as a reference.
- *Why Part 23 doesn't map:* Part 23 (and CAR 3, CAR 4a, CS-23) certify
  normal, utility, acrobatic or commuter, often several on one model (DA 40
  FAA: normal + utility). Which one is the TCDS's choice per model. The Part
  doesn't decide it.

**Options.**

- **(a) Reviewed per-TCDS row** (new `overrides/tcds_categories.tsv`: `tcds`,
  `model` or `*`, categories, evidence). Every case is read by a person.
  Cost: a file, a loader, stale and unknown-row tests, PIPELINE and FAA_TCDS
  docs. It contradicts the EASA parser, which already infers (ETCDS-12), so
  that would need rows too: about 20 published EASA TCBs (A.068, A.069, A.096,
  A.186, A.187) and 49 staged.
- **(b) Parser rule.** Recommended, narrowed: only when the TCDS states no
  category for the model, and its headline line(s) (Q6) cite exactly one
  airworthiness Part that admits one category. Part 25, CAR 4b, CS-25 and
  JAR-25 give transport. Part 29 and CAR 7 give transport (rotorcraft); Part
  27 and CAR 6 give normal (read §27.1/§29.1; CAR 6/7 not read). The rule
  refuses when the TCDS cites 21.25 (restricted), 21.17(b) (special class) or
  21.24 (primary), or when two airworthiness Parts are headlines. Part
  23/CAR 3/CAR 4a/CS-23 and Part 31 are never mapped. It writes `tcb.notes`
  "Category not stated on this TCDS; transport from its 14 CFR Part 25 basis."
  `tcb.notes` is null on every published TCB today, and the app prints it
  under the heading (`templates/aircraft/basis.html`), so the inference is
  visible to users with no contract change.
- **(c) DRS catalogue.** Rejected (above).
- **(d) Another proof TCDS.** No candidate. A scan for "Certification Basis
  for <models>" found A2NM and A17SW. With a looser pattern it found
  A-817/7A1 (F27: no category / no basis), A20EU F28 (duplicate designation)
  and A3EU (same). None is a clean shared-block TCDS with a stated category.

**Recommendation: (b), as one decision with ETCDS-12.** Move the EASA rule
into `s00_common` so both parsers use it, and have both write the note. Costs:

- Docs: DATA_FORMAT `categories` row ("as stated on this TCDS, or, when it
  states none, from a single-category airworthiness Part of its basis,
  recorded in `tcb.notes`"), FAA_TCDS (Rules, Not staged), EASA_TCDS (the
  category map line). Close ETCDS-12.
- Tests: Part 25 headline gives transport; Part 23 is still refused; 21.25
  cited is refused; a stated category wins; two airworthiness Parts are
  refused; the A2NM golden.
- No `SCHEMA_VERSION` bump. FAA published files: none (all 21 selected TCDS
  state a category). EASA: the about 20 published TCBs gain the note at the
  next promotion.

If you'd rather every inferred category be read by a person, choose (a), and
switch EASA to rows in the same change.

## Q2. Basis statements outside the basis blocks (A2NM p. 7)

**Read.** A2NM p. 7 (text): "Compliance with 14 CFR §26:" in "Data Pertinent
to All Models (cont'd)", before the first "Certification Basis for …" label.
It says "Based on 14 CFR §21.101(g) for changes made to TCs applicable
provisions of 14 CFR part 26 are included in the certification basis", then
compliance at 26-0 (26.11), 26-1 (26.43, .45, .47, .49) and 26-3 (26.33). The
"Exemptions from 14 CFR part 25:" paragraph after it repeats 9791, which is
already printed inside both blocks, so it needs no attaching.

**Counts** (scan, unread). The §21.101(g) sentence "… part 26 … included in
the certification basis" is in 26 TCDS. In 18 it sits inside a basis block
(A16WE, A1NM among them). In 8 it is outside: A20EU, A21EA, A2NM, A56NM, A57NM,
A58NM, T00011AT, T00063IB. None is in the selection list. A plain "Part 26" /
"26.xx" scan is useless: it mostly matches decimals (CG stations, % MAC).

**Should it join every model's basis?** The TCDS says so in words, and it sits
in an all-models section, so yes. But Part 26 isn't in the dataset (TCDS-13),
so every line would be `references: []`. Today it would only add visibility.

**How to find it without catching prose:** a label rule, not a sentence
search. Treat a field label naming Part 26 ("Compliance with 14 CFR §26:")
in a pertinent-to-all section as a basis block scoped to that section's
models. Its "Compliance has been found for the following regulations at
Amendment 26-N: …" lines become `regulation` entries; the §21.101(g) sentence
becomes an `other` entry. Don't add a general "included in the certification
basis" trigger: Note 16 (p. 13) has the same words for an optional
fuel-inerting basis that must not be attached.

**Recommendation:** don't block step 3. Record it in the A2NM checklist as
not attached, and file an issue (with TCDS-13) listing the 8 TCDS. Build the
label rule once they are read, or when Part 26 enters the dataset. Changes
now: issue text only.

## Q3. Item boundaries in the 5613 exemption (A2NM p. 8)

**Read.** Rendered p. 8. "Exemption No. 5613 was granted on March 5, 1993" and
"Exemption from FAR 25.1415(c) for survival kit attachment requirements.
(Subject to Operational Procedures)" are at the same indent, with no blank
line between them. Compare 4808 on the same page: "Exemption No. 4808 was
granted on June 9, 1987 - Exemption from FAR's 25.783(g) …" on one line. So
5613 is the same "No. N granted <date> – Exemption from …" shape, wrapped
without the dash. Outside source: `input/catalogues/faa_deviations_catalogue.tsv`
row EX5613, granted 1993-03-05, Boeing Commercial Airplane Group, B-757-200,
sections 25.1415(c) and 121.339(c). EX5613A (1998-08-05, Amendment, 757-200
and 757-300, the same sections) matches the 757-300's "Ditching Equipment FAR
25.1415(c) Exemption No. 5613A". **The exemption PDF itself is not in
`input/`** (the catalogue's `local_path` names it, but there's no file), so the
exemption text was not read.

**Recommendation: one item**, as parsed. **No rule change:** `lists.py`
already starts an item only at "Exemption No." / "Partial …", so the
"Exemption from …" line continues 5613. The A2NM golden will pin it. A risk
to note, not fix: a list whose items all start "Exemption from … (No. N)"
with no blank lines would merge. None seen.

## Q4. One table row, two amendment levels

**Read.** Rendered p. 9.

- Footnote \*\*: "Where two amendment levels are shown for the same paragraph,
  the number without the asterisk applies to structures, systems and portions
  of the airplane, which are not new or significantly modified." That is a
  **split by part of the airplane**, like two serial ranges.
- Footnote \*\*\* is different: "Boeing has complied with §25.813 at
  Amendment 25-88 except for §25.813(c), which used Amendment 25-75 … placarding
  requirements of §25.813(c)(3) at Amendment 25-88." That is a **paragraph
  split**. The current two whole-section entries (25.813 to 25-75 and to
  25-88) misstate it.
- `data/documents/faa/25/813.json` versions: 25-72, 25-76, 25-88. So 25-75
  resolves to the 25-72 version and 25-88 to 25-88.
- Corpus: 24 two-level cells, 22 in A16WE NG tables. All are "N, M\*\*" with
  the same Boeing footnote wording (A16WE p. ~33, by text); A2NM has the
  other two.

**Contract.** DATA_FORMAT doesn't say "one entry may not hold one provision at
two versions"; that phrase is from the proposal. What fails is two *scoped*
(whole-section) refs to one provision at different versions
(`resolve._include`). A paragraph ref at another version is allowed: rule 3
adds a row. So 25.813 can be **one entry**: `{813, to 25-88}` plus
`{813, paragraph "(c)", to 25-75}`. (c)(3) at 25-88 is covered by the
whole-section row. Not built, so the paragraph check against the 25-72 text
hasn't run. 25.783 (\*\*) can't be one entry and needs two.

**What the app shows** (read from `FARfetched/src/farfetched/templates/aircraft/basis.html`,
not in a running app): each entry is its own list item. Both show the same
raw row, then "Applies to: 23" or "Applies to: 85\*\*", which reads like a
serial or a model. The citation views dedupe by (type, raw, paragraph), but
only for ELOS, SC and exemption lines, not regulation rows.

**Options.** (i) Now: two entries, level as `applicability`. Wrong for 25.813,
and misleading "Applies to". (ii) The footnote marker in `applicability_notes`.
(iii) One entry, `references: []`, for every two-level cell. Honest, but it
loses 22 resolvable A16WE rows.

**Recommendation.**

- Split a cell into two entries **only when its marker's footnote contains
  "two amendment levels are shown"** (A2NM \*\*, A16WE \*\*).
- Set `applicability` to the inherited scope (null here), not the level. Put
  the meaning in `applicability_notes`, mechanically: `One of two levels in
  this row (23, 85**); footnote ** says which parts of the airplane each
  covers.`
- Any other marker (\*\*\*) gives one entry, `references: []`, reason
  `partial`. A step 4 `tcds_entries.tsv` "set references" row then gives
  25.813 the paragraph reading above, with footnote \*\*\* as evidence.
- Changes: `amdt_table.py` (needs the footnote text, which it already emits
  as entries), the FAA_TCDS amendment-tables rule, tests (both markers, the
  unknown-marker refusal). No contract change; no published file.

## Q5. A paragraph "not part of the TC basis" (25.858(a))

**Read.** Rendered p. 9: "25.858(a) Cargo Compartment Fire Detection System —
not part of the TC basis". `data/documents/faa/25/858.json` versions: 25-54 and
25-93, so the headline "through 25-85" holds 25.858 at the 25-54 version.

**Counts** (scan, unread).

- Corpus: "not part of the … basis" in 6 TCDS. Only A2NM and A21EA (a list
  ending "869, (a) & (b)") are paragraph-level; A1NM's is section-level
  (25.519).
- Paragraph "not applicable / does not apply" in 7 TCDS (A-817, A14EA, A1NM
  25.803(c)(8), A20WE 25.1103(d), A21EA-1, A28NM, T00001SE 25.812(g)).
- "25.x (except (y))" in 5 (A16WE "25.807 (except (g)) 94", A28NM, A46EU,
  A77EU, H1NE). Some of these give a paragraph a different level rather than
  excluding it.
- In `data/`, no resolved entry needs a paragraph exclude. The EASA lines
  that would (A.004 "(except (a))" lists, A.186) are already
  `references: []`.

**Options.**

- Accept.
- A contract change: exclude takes `paragraph`. That touches the schema,
  `resolve.py`, and a new representation in `cert_basis_resolved` (today
  `paragraph` there qualifies an inclusion; a negative needs a new column or
  table), so `SCHEMA_VERSION` 12, a SCHEMA_HISTORY row, and an app release.
- A workaround inside today's contract: exclude 25.858 from the headline and
  give the row a `paragraph "(b)(c)(d)"` ref. Rejected: `paragraph` must be
  verbatim, and "(b)(c)(d)" isn't on the TCDS.

**Recommendation: accept.** The resolved table's grain is the provision
version. "757-300 uses §25.858 @ 25-54" is true, because (b)–(d) apply. Only
the implicit (a) is wrong, and the verbatim row saying so is visible right
under the headline. File an issue (faa-tcds.md) with the corpus list above.
Revisit when a paragraph exclude would change something a user filters on,
or at step 9 (A16WE 25.807 except (g)), after reading what those lines mean.

## Q6. Rule 5's headline guard

**Definition.** A *headline* is an include reference with no `provisions`
(whole document) to an **airworthiness** document: FAA 23/25/27/29/31, CAR 3,
4a, 4b, 6, 7, CS-22/23/25/27/29/VLA. Not 34 or 36: noise lines legitimately
repeat per serial range, as in A00018AT, A00072CE and A78EU. **Guard:** a TCB
with headlines to one document at more than one `to` and the same
`applicability` fails. Unresolved lines need the same test: the interpreter
should flag a line it reads as a whole-Part range even when it ends
`partial` (A2NM line 1, "Federal Aviation Regulations (FAR) Part 25 with
Amendments …"). A regex is too fragile: mine missed that wording.

**Tested** (scratch, current parser, not read against the PDFs):

- **A2NM**: 757-300 has one headline (25-85); the others have none resolved.
  Passes.
- **A16WE**: -600, -700, -800 (25-77), -700C, -900 (25-91) and -900ER
  (25-108) pass. **All five MAX models fail** with 25-141 and 25-146. The
  three sentences on p. 72 ("The certification basis for the 737-8 and 737-9
  airplanes is … 25-137, plus 25-141"; "for the 737-8200 … 25-141"; "for the
  737-7 and 737-10 … 25-146") are copied to every MAX model, because their
  in-line model scope isn't read. A true positive, for step 10.
- **Selected FAA TCDS** in `data/`: all pass. A00003SE and A78EU have one
  airworthiness headline per model; their second blocks are Part 36 or
  scoped.
- **Published EASA** `data/` would fail on EASA.A.004 (both A330s, ETCDS-16),
  IM.A.033 680A (CS-25 at 2, 4, 9, 11, 17, 25 and 28, each "a) CS-25
  Amendment N" followed by a "CS 25 paragraphs Applicability" table), IM.A.348
  G280 ("For steep approach … CS 25 Amendment 13, Appendix Q" as all of CS-25)
  and A.187 C-212-EE ("For FMS, IEDS and EFIS, FAR Part 25 … 25-87" as all of
  Part 25). Judged from `raw_reference` only, these look like overclaims of
  the ETCDS-16 kind. Only A.004 is already an issue. Also seen, not caught
  by the guard (same `to`): A.637 P2012 "CS-23 Amdt.4 § 783(d)(e)" carries a
  whole-CS-23 ref.

Run the guard in the shared `s00_common` TCB code so EASA gets it too. It
would refuse those EASA models at the next staging until fixed, so it should
land with or after the ETCDS-16 fix.

## Q7. Relative designations in line scope

**Read.** A16WE text, around the p. 20 lines: "Equivalent safety findings exist
with respect to the following regulations: For 737-100/-200/-
200C/-300/-400/-500:". It wraps inside the list. Code: `sections.scope_models`,
`sections.expand_group`, `attach._keeps`.

**Tested** (scratch, hand-made model list): `scope_models("For
737-100/-200/-200C/-300/-400/-500:")` returns `{737-100}`, so `_keeps`
keeps the line on 737-100 only and **silently drops it from the other five**.
`expand_group` reads the unwrapped list correctly, but returns None on the
wrapped "-200/- 200C".

**Where it belongs:** one designation-list reader in `sections.py`, used by
both `expand_group` (block labels) and `scope_models` (line scope), so the
two can't disagree. `scope_models` would first find each slash list whose
first token is a heading designation, expand it with the same rule, then do
the "X thru Y" ranges as now. Join a hyphen-space wrap ("/- 200C") before
reading.

**What it must refuse** (return None, which callers turn into a report note
and no staging, never "keep on all"):

- a short token that doesn't complete to a heading designation;
- a list whose first token is a designation and whose later tokens complete
  to nothing on this TCDS.

**What it must ignore** (not a model list at all):

- slash lists whose first token isn't a heading designation: engines
  "CFM56-7B26/3F", amendments, paragraphs.

Also: `_keeps` treats None as "keep on all models", which over-attaches
quietly. It should fail loud the same way.

Tests: the A16WE forms (wrapped and not), "737-8/-9/-8200/-7/-10", the
CFM56 lists ignored, an unknown short token refused. No contract change.
compare_stages should show no change for the selected TCDS (unverified).

---

## Not done in this session

- Nothing staged, nothing in `tools/out/` written, nothing downloaded.
- Not read against sources: every corpus count above. The EASA overclaims in
  Q6 (raw text only). CAR 6/7 applicability. The exemption 5613 PDF (not
  local).
- Issues to file once you agree: Q2 (Part 26 outside blocks, 8 TCDS), Q5
  (paragraph excludes), Q6 (EASA whole-document refs beyond ETCDS-16), Q7
  (silent line-scope drop). TCDS-5's counts can be replaced with the Q1
  table.
