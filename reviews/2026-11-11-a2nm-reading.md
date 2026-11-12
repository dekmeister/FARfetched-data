# A2NM (Boeing 757, Rev 32): basis read against the PDF

Step 3 of [the multi-model proposal](2026-11-10-multi-model-tcds-proposal.md).
Status: **read once by the assistant, 2026-11-11; goldens read against it
2026-11-12; awaiting your check.** A2NM is not in `faa_tcds_selection.tsv`.
Q1–Q5 are decided (the blockers note (in git at acadefc, `reviews/2026-11-12-multi-model-blockers.md`)):
a `tcds_categories.tsv` row gives the category, and the four models stage in
the golden test (`tools/s99_tests/fixtures/tcds/A2NM_Rev32_*.expected.json`:
757-200 33 entries, -200CB 33, -200PF 39, -300 86).

2026-11-12 corrections, read on rendered pp. 9–11:

- The 757-300 has **50** equivalent safety findings (p. 10: 36, p. 11: 14),
  not 48. The parser had 50 all along; the count below was wrong.
- 25.813 "75, 88\*\*\*" is now **one** entry with no references. Footnote
  \*\*\* is a paragraph split (25-88 except 25.813(c) at 25-75), which a
  reviewed row must state (step 4). 25.783 "23, 85\*\*" stays two entries,
  with `applicability_notes` instead of the level as `applicability`.

## Method

- Pages 1 and 6–13 rendered at 100 dpi (`pdftoppm`) and read as images.
  Pages 2–5 (model sections: engines, weights, serials) checked by text
  search only: no FAR/CFR citation, "Basis", exemption, special condition
  or finding on them.
- Parser output read with the category forced to transport in a scratch
  script (the only difference from a real run: models stage). 123 distinct
  lines, 192 entries (757-200 33, -200CB 33, -200PF 39, -300 87).
- Columns: **Models** the parser gives (200 = 757-200, PF, CB, 300), **PDF**
  the models the page gives, **References** what the entry means.
  Only rows actually read are marked; every row here was read.

## Blocks and scope

| Block (page) | PDF scope | Parser | Verdict |
|---|---|---|---|
| "Certification Basis for 757-200/200CB/-200PF:" (7–9) | 200, CB, PF | 200, CB, PF | ✓ |
| "For 757-200PF: Same as 757-200 airplane plus …" (8) | PF | PF | ✓ |
| "Equivalent Safety Findings … (for 757-200PF):" (8) | PF | PF | ✓ |
| "Exemption from FAR Part 25 (for 757-200PF):" incl. 4808B after the page break (8–9) | PF | PF | ✓ |
| "For 757-200CB: Same as 757-200 airplane plus …" (9) | CB | CB | ✓ |
| "Certification Basis For 757-300:" (9–11) | 300 | 300 | ✓ |
| Block end at "NOTES APPLY TO ALL MODELS …" (11) | — | ends | ✓ |

## Lines

| # | Line (abridged) | Models | PDF | References | Verdict |
|---|---|---|---|---|---|
| 1 | FAR Part 25 with Amendments 25-1 through 25-45 … except Section 25.109 Amendment 25-42, … 25.1522 Amendment 25-46 | 200 CB PF | same | `[]` (partial) | ✓ scope. Unresolved: inline exceptions with two levels for 25.365(e) by compartment (TCDS-13) |
| 2 | FAR Part 36 with Amendments 36-1 through 36-12 | 200 CB PF | same | 36 to 36-12 | ✓ |
| 3 | Stage 3 or Stage 4 Noise Compliance … | 200 CB PF; 300 (own copy) | same, printed in both blocks | `[]`, other | ✓ |
| 4 | Special Federal Aviation Regulation 27. | 200 CB PF | same | `[]` (SFAR 27 not in dataset) | ✓ |
| 5–29 | 25 findings, 25.251 … 25.1555(d)(1), one entry each | 200 CB PF | same (list under the block's ELOS header) | elos, citations by v11 | ✓ each item matches a printed line, wraps joined (25.853(a), 25.981(a)(3), 25.981(b)(2), 25.1441(c), 25.1443(c)) |
| 30 | Exemption No. 5613 … March 5, 1993 Exemption from FAR 25.1415(c) for survival kit … (Subject to Operational Procedures) | 200 CB PF | same | exemption | ✓ as one item. **Judgement** (Q3): the PDF prints "Exemption No. 5613 was granted on March 5, 1993" on its own line, then "Exemption from FAR 25.1415(c) …"; 5613A on the 757-300 is the same §25.1415(c), so read as one exemption |
| 31 | Partial Exemption No. 9405 … See note 14 | 200 CB PF | same | exemption | ✓ |
| 32 | Partial Time-Limited Exemption … 25.853(a) … 9791C, February 4, 2011) | 200 CB PF; 300 | printed in both blocks (and on p. 7 outside them, Q2) | exemption | ✓ |
| 33 | Exemption No. 13180 … limited to in-service 757-200 (freighter only) and 757-200PF … | 200 PF | 200 (freighter) PF | exemption | ✓; "freighter only" kept in the text |
| 34 | (CB) Same as 757-200 airplane plus 25.783 Amendment 25-54, applicable only to the main deck cargo door and FAR 25.783(a), Amendment 25-46. | CB | CB | 25.783 to 25-54; 25.783(a) to 25-46 | ✓. The "applicable only to …" limit is in the text, not the reference |
| 35 | (PF) Same as 757-200 airplane plus FAR 25.783 … 25-54 … and FAR 25.723(a), Amendment 25-46. | PF | PF | 25.783 to 25-54; 25.723(a) to 25-46 | ✓ (same note) |
| 36–37 | FAR 25.855(e); FAR 25.1447(c)(1) and (3) | PF | PF | elos | ✓ |
| 38–40 | Exemptions 4808, 4808A, 4808B | PF | PF | exemption | ✓ |
| 41 | Part 25 as amended by Amendments 25-1 through 25-85 … with the exceptions listed below; | 300 | 300 | 25 to 25-85, exclude 101 105 109 113 115 365 519 562 571 735 783 807 810 813 1316 1533 | ✓ the 16 section-level rows |
| 42–62 | Table rows 25.101 … 25.1533 (21 entries for 19 rows) | 300 | 300 | one `to: 25-N` per level, paragraph from the row | ✓ every cell checked against p. 9. 25.783 (23, 85\*\*) and 25.813 (75, 88\*\*\*) are two entries each, level as `applicability` (Q4) |
| 48, 59 | 25.519, 25.858(a) "not part of the TC basis" | 300 | 300 | `[]` | ✓ 25.519 is excluded from line 41. **Gap**: 25.858(a) can't be (an exclude takes no paragraph), so line 41 still holds 25.858 at 25-85, (a) included (Q5) |
| 58, 61 | 25.853(d)(3) at 72; 25.1419(c) at 23 | 300 | 300 | paragraph refs | ✓; the section stays at 25-85 through line 41, the paragraph at its own level |
| 63–65 | Footnotes \*, \*\*, \*\*\* | 300 | 300 | `[]`, other | ✓ one entry each |
| 66 | Part 34, through Amendment 34-1 | 300 | 300 | `[]` (Part 34 not in dataset) | ✓ |
| 67 | Part 36, with Amendments 36-1 through 36-21 | 300 | 300 | 36 to 36-21 | ✓ |
| 68–69 | SC 1. HIRF; 2. Engine Torque Loads | 300 | 300 | special_condition | ✓ |
| 70–117 | 48 findings 25.21(b) … 25.1587(b)(2) (two-column list, pp. 10–11) | 300 | 300 | elos | ✓ each row, wraps joined, page break crossed |
| 118–123 | Exemptions 6600, 6577, 5613A, 6867/7790, 7798, 9405 (and 9791, line 32) | 300 | 300 | exemption | ✓ |

Header text that is not an entry (by the family-header rule): "Equivalent
safety findings exist with respect to the following regulations:", both
"Exemption from FAR Part 25 …:" lines, "Special Conditions for the following
subjects … 757-300.", and the 757-300 lead-ins "The equivalent Safety
findings were proposed in accordance with §21.21. The following …" and
"Exemptions were requested in accordance with Paragraph 11.25. The
following …". ✓ none of them states a requirement.

## Open questions

- **Q1. Category.** A2NM never states a category (no "Transport" anywhere;
  headings give only approval dates). The schema needs one. Options: a
  reviewed row (evidence: the basis is 14 CFR Part 25), or pick a proof TCDS
  that states it. Until then nothing stages.
- **Q2. Outside the blocks, p. 7.** "Compliance with 14 CFR §26" says Part 26
  provisions "are included in the certification basis" (26.11 at 26-0;
  26.43, .45, .47, .49 at 26-1; 26.33 at 26-3), and "Exemptions from 14 CFR
  part 25" repeats 9791. Both sit in the all-models data, before the basis
  labels, so they aren't attached. Part 26 isn't in the dataset either
  (TCDS-13). Attach to all four models, or leave?
- **Q3.** Line 30 as one exemption (above).
- **Q4.** Two-level cells: two entries with the same verbatim row and the
  level as `applicability`. Alternative: the footnote text as
  `applicability_notes`.
- **Q5.** 25.858(a) "not part of the TC basis" can't be excluded at paragraph
  level, so the resolved 757-300 basis shows 25.858 at 25-85. A contract
  change (paragraph excludes) or accept and leave the row visible?
- **Not attached, by design:** Note 16 (p. 13) "Certification Basis for §14
  CFR 25.981 at Amendment 25-125, and Equivalent Safety Finding P-2 … is
  applied if fuel tank inerting is installed" sits in the notes. "Compliance
  with the following optional requirements … for all Models" (Ditching
  25.801, Ice Protection 25.1419, p. 6) is optional, not basis.
