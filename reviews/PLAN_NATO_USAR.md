# PLAN_NATO_USAR: STANAG 4671 / AEP-4671 ingestion (blocked on schema v7)

## Context

The NATO USAR ingestion was started on 2026-11-04 and stopped at the identity
check. Paragraph numbers are not stable identities between STANAG 4671 Ed. 1
and AEP-4671 Ed. B, so the pipeline needs schema v7 (provision `key` vs
printed `number`, reviews/PLAN_516.md Part A). v7 isn't built yet
(`SCHEMA_VERSION = 6`, no `key` field). The developer will do MIL-HDBK-516
(which brings v7) first. Nothing in the repo was changed.

Below is the original prompt, cleaned up. Some lines of the pasted original
were cut off. Where I filled a gap from context, the text is marked
**[reconstructed]**: check those before reuse. The identity findings from
this session are included, so the next run doesn't redo the check.

---

## Prompt

Implement an ingestion pipeline for STANAG 4671 / AEP-4671 (NATO UAS
airworthiness requirements, "USAR") in this repo, following the same approach
as the existing regulation pipelines. This is implementation work, not a
planning exercise.

**Prerequisite:** schema v7 (provision `key` vs per-version printed `number`,
PLAN_516 Part A) is implemented and committed, and the MIL-HDBK-516 pipeline
exists as the reference for key assignment and the continuity-decisions
file. If v7 isn't in place, stop and say so.

### Source files (already downloaded, text-layer PDFs)

In `input/Regs/NATO/` (gitignored):
- `STANAG-4671 Ed1 (2009-09-03).pdf`: 214 pp. The STANAG with the full USAR
  requirements inside it. Source: Wayback snapshot of the French MoD archive
  copy.
- `AEP-4671 EdB V1 (2019-04-02).pdf`: 262 pp. Official NSO download. From
  Ed. 2 onward the requirements live in the AEP.
- `STANAG-4671 Ed3 (2019-04-02).pdf`: 6 pp. Official NSO download. A
  covering agreement only: no requirements, just a pointer to AEP-4671 Ed. B.

Not every file is regulation text:
- The Ed. 3 STANAG is a cover document. Don't extract provisions from it.
  Use it only as metadata (edition, promulgation date, which AEP edition it
  references), if and where the schema has a place for that. Its letter of
  promulgation says it supersedes "STANAG 4671, Edition 2, dated 9 February
  2017" and implements "AEP-4671, Edition B". Dated 2 April 2019,
  NSO/0427(2019)JCGUAS/4671.
- Inside the two big PDFs, skip front matter and back matter that isn't a
  requirement: covers, letters of promulgation, records of
  amendments/reservations, explanatory notes, tables of contents, and any
  non-normative annexes. Decide the boundary from the actual PDFs and
  document it in the pipeline doc.

Known gap: STANAG 4671 Ed. 2 and AEP-4671 Ed. A (both Feb 2017) aren't freely
available. The edition history is therefore Ed. 1 → Ed. B. Don't invent a
revision and don't use TEXT MISSING for it (that marker is only for
known-extant but unreadable text). Check how docs/DATA_FORMAT.md handles a
revision list with a gap, and note the gap in `ISSUES.md`. (Session note:
`ordinal` is only a unique sort key, so a gap in ordinals is allowed. Missing
revisions themselves have no representation.)

Licensing is settled. Don't raise it.

### Read first

1. `CLAUDE.md` (repo), `tools/CLAUDE.md`, `tools/README.md`,
   `tools/s00_docs/PIPELINE.md` (stage vocabulary and the "Adding a new
   pipeline" steps).
2. The closest existing pipelines: the MIL-HDBK-516 pipeline (multi-edition
   PDFs, key assignment by text continuity, decisions overrides file) and
   EASA CS (`tools/s00_docs/EASA_CS.md`, `tools/s01_extract/easa/cs/`,
   `tools/s02_emit/easa/cs/`) for the PDF → text → provision pattern.
3. `docs/DATA_FORMAT.md`, `docs/SQLITE.md`, `docs/SCHEMA_HISTORY.md`,
   `schemas/` (issuer enum).

### Build

- **Layout:** new `s01_extract/` and `s02_emit/` folders per tools/CLAUDE.md.
  Inputs are local PDFs, so "discover/manifest" is a manifest of the files
  plus checksums, not a download. Use the shared helpers in
  `tools/s00_common/`, and `paths.py` for locations.
- **Emit:** write to `tools/out/staged/documents/` only, with provision text
  laid out through `structure_version`. Never write to `data/`.
- **Identity:** USAR paragraphs look like `USAR.23`, `USAR.1389` and
  `USAR.U1821`. Key == number does **not** hold across editions (findings
  below). Assign keys by text continuity under v7, the same way as 516.
  Record the reviewed decisions in an overrides file with evidence.
- **Document model:** decide whether this is one document with revisions
  Ed. 1 → Ed. B, or two (STANAG vs AEP) **[reconstructed]**. Decide from
  DATA_FORMAT.md and the resolution rules. Record the reasoning in the
  pipeline doc.
- **Issuer:** add a new issuer code (e.g. `NATO`). The schema, docs,
  `build.py` and a test change together, per the repo CLAUDE.md Do/Don't
  **[reconstructed]**.
- **Metadata:** `source_url` and `publication_cite` on every version. NSO
  pages: https://nso.nato.int/nso/nsdd/main/standards/ap-details/2783/EN and
  https://nso.nato.int/nso/nsdd/main/standards/stanag-details/9175/EN
  **[reconstructed: the first URL's path was cut off]**. The Ed. 1
  provenance is the French MoD archive copy via the Wayback Machine
  **[reconstructed]**.
- **Tests and docs:** fixtures under `tools/s99_tests/fixtures/` and
  happy-path tests, `tools/s00_docs/NATO_USAR.md` (CLI examples, reports,
  source quirks) **[reconstructed name]**, and a row in the tools README
  table.
- **Problems:** put anything the parser can't handle cleanly (tables,
  figures, ambiguous paragraph boundaries) into `ISSUES.md`
  **[reconstructed]**.

### Verify

- Run the new extract and emit stages, then `uv run python build.py --check`,
  `uv run ruff check .`, `uv run mypy .` and `uv run pytest`
  **[reconstructed]**. Per tools/README.md, also name `tools/s0*
  tools/s99_tests` for ruff/mypy (the root `.gitignore` hides `tools/`).
- Run `uv run python -m tools.s03_promote.promote --dry-run` and show me the
  diff. Stop there. Real promotion is my step, after review.

### Constraints

- Work on `main`. No branches. No `git add`, `commit` or `push`.
- No hand edits to `data/`; corrections are override rows.
- Non-destructive: don't move or delete files; write any file operations to
  a review script **[reconstructed]**.
- Ask before large schema changes.
- No docker or sudo is needed.
- Scripts are run as `python -m tools.…`; stdout is data while stderr is
  progress **[reconstructed]**.

---

## Findings from the 2026-11-04 session (evidence for the next run)

Method: `pdftotext` (raw), headings `USAR.<n> <Capitalised title>` inside
`BOOK 1 – AIRWORTHINESS CODE` up to `BOOK 2 - ACCEPTABLE MEANS OF
COMPLIANCE`. Each common number's body was compared by word-sequence ratio.
Script: the appendix below

Counts: Ed. 1 has 376 headings, Ed. B 439. 375 numbers are common, and 12 of
them have low text or title similarity. 1 number is only in Ed. 1 (U1719,
only because Ed. 1 prints a duplicate, see below). 63 are only in Ed. B
(new: 321, 341, 349, 395, 751–859 block, 1109–1201, 1305–1335, 1441–1457,
1555, U240, U304, U590, U1304, U1330, U1494, U1712–U1718).

Identity breaks:
- **Number reuse:** Ed. 1 U1717 "UCS electrical systems", U1719 "UCS power
  supply" and U1720 "Automated Mission Planning" are Ed. B **U1712, U1713,
  U1714**. Ed. B U1717 "UCS Smoke or Fire Detector System", U1719 "Exits"
  and U1720 "UCS Emergency Lighting" are new requirements.
- **Ed. 1 printing error:** USAR.1367 is printed twice in Ed. 1. The first,
  "Electric cables and equipment", is CS-23/Ed. B **1365**. The second,
  "Switches", is 1367. Needs an override with evidence.
- **Moved text:** Ed. 1 1329 "Flight control system" text is Ed. B **U1330**
  "Flight control performance". Ed. B 1329 reads "Not Applicable. See
  USAR.U1330".
- **Same requirement, title changed:** U1490 (Ed. 1 "General" → Ed. B
  "Automatic take-off system, automatic landing system", text ratio 0.96),
  347 (Unsymmetrical → Asymmetrical), 1141, U1887 (UAV → UA wording).
- **Partial splits into new paragraphs:** 307 → part to new 321, 347 → 349,
  393 → 395. 1041, U850 and U1727 are heavily reworded. These continue
  under the same key, but review each one.

Source quirks seen:
- A margin index column of paragraph numbers (`21`, `U2`, `U1887`) is
  interleaved into the raw text, sometimes on the heading line itself
  (`U1717 USAR.U1717 …`). It has to be stripped.
- Running furniture: `STANAG 4671` / `(Edition 1)`; `AEP-4671` /
  `Edition B Version 1`; page ids `1-A-1`, `1-App C-1`.
- `See AMC.xx` lines under headings: cross-references into Book 2.
- Ed. B prints CS-23 numbers it doesn't adopt as "Not Applicable" stubs,
  some without the `USAR.` prefix (`3 Aeroplane categories` / `Not
  Applicable.`).
- In-text cross-references wrap onto line starts (`USAR.445.`, `and
  USAR.203`). A heading needs a capitalised title and no trailing period.
  Ed. B `USAR.U1719 Exits.` breaks the "no trailing period" rule.
- Ed. B U1714 has a page break straight after its heading. Check that it has
  a body.
- Boundaries: Book 1 runs from `BOOK 1 – AIRWORTHINESS CODE` to `BOOK 2 -
  ACCEPTABLE MEANS OF COMPLIANCE (AMC)`. Book 1 includes Appendices C, D, F
  and G (Ed. B adds K and L). Front matter before Book 1 is the
  introduction plus Annexes A (Glossary), B (Abbreviations) and C
  (cross-reference table with EASA CS-23). Book 2 (AMC) is non-normative,
  like EASA AMC. Decide during implementation whether Annex A/C are in
  scope (the C table is good evidence for ROADMAP-4 relations).

## Open questions for the developer (to settle at the start of the next session)

1. **Document model.** Under v7 one document with revisions Ed. 1 → Ed. B
   looks right: it is one requirement set that changed carrier (STANAG →
   AEP). What should `code` and `slug` be? Candidates: `code "AEP-4671"` /
   `slug "aep-4671"`, or `code "STANAG 4671"` / `slug "stanag-4671"`, or
   `"USAR"`. A cert basis would cite the edition as the `to` designator.
2. **Designators and ordinals.** As printed, they are "Edition 1" and
   "Edition B Version 1". Proposal: designators `Ed1` and `EdB-V1`, ordinals
   `1` and `3`, which leaves `2` free for the missing Ed. 2 / Ed. A. Or are
   plain `0` and `1` better? `doc_kind` is `standard`, a value the enum
   already has.
3. **Effective dates.** Neither big PDF prints a promulgation date in its
   text layer (Ed. 1's explanatory notes have none; Ed. B's letter of
   promulgation page is "RESERVED FOR NATIONAL LETTER OF PROMULGATION").
   2009-09-03 comes from the file name / Wayback snapshot, and 2019-04-02
   is the STANAG Ed. 3 letter date. Can the NSDD pages confirm the
   promulgation dates? Otherwise should the dates come from Ed. 3 and a
   catalogue TSV?
4. **`publication_cite`.** For Ed. B, `NSO/0427(2019)JCGUAS/4671` (Ed. 3
   letter)? Ed. 1 has no promulgation reference in the PDF. Omit it or
   look it up?
5. **Issuer row.** `_ISSUERS["NATO"]` = ("North Atlantic Treaty
   Organization", kind?, country None, successor None). What is the
   `kind`: `military`, as DOD in PLAN_516, or something else?
6. **"Not Applicable" stubs.** Ed. B prints CS-23 numbers it doesn't adopt
   as stubs (`USAR.1329 … Not Applicable. See USAR.U1330`, and some without
   the `USAR.` prefix, e.g. `3 Aeroplane categories`). Should they be
   versions with that text, or skipped? Ingesting them keeps the CS-23
   number alignment visible but adds noise.
7. **Ed. 1 duplicate 1367.** This is a source printing error, not a
   continuity decision. What kind of override fixes it: an
   extract-stage renumber row (`designator number occurrence → number`) or
   a v7 continuity row? Pick whatever 516 settles on for source errors.
8. **Scope of annexes and appendices.** Book 1 appendices (C, D, F, G; Ed. B
   adds K, L) are normative. They need provision numbers (EASA uses `A23`
   style). Introduction Annex A (glossary) and C (CS-23 cross-reference):
   are they in or out? Annex C may become evidence for ROADMAP-4
   relations.
9. **Ed. B "Version 1".** If NSO issues Ed. B V2, would it be a new
   revision? That affects the designator choice in Q2.
10. **The [reconstructed] lines** in the prompt above: confirm or correct
    them, mainly the first NSO URL and the pipeline doc name.

## Appendix: sample-match script (scratch, for replaying the identity check)

Run against `pdftotext` (raw mode) output of the two PDFs:
`python3 -I sample_match.py Ed1.txt EdB.txt`.

```python
"""Crude cross-edition identity check for USAR paragraphs (scratch, not pipeline)."""

import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

HEAD = re.compile(r"^(?:U?\d+[a-z]?\s+)?USAR\.(U?\d+[A-Za-z]?)\s+([A-Z][^.]*)$")
NOISE = re.compile(
    r"^(U?\d+[a-z]?|1-[A-I]-\d+|1-App [A-Z]-\d+|STANAG 4671|\(Edition 1\)|AEP-4671|"
    r"Edition B Version 1|)$"
)


def paras(path: Path) -> dict[str, tuple[str, str]]:
    lines = path.read_text().splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("BOOK 1 – AIRWORTHINESS"))
    end = next(i for i, ln in enumerate(lines) if ln.startswith("BOOK 2 - ACCEPTABLE"))
    out: dict[str, tuple[str, str]] = {}
    cur: str | None = None
    title = ""
    body: list[str] = []
    for ln in lines[start:end]:
        s = ln.strip()
        m = HEAD.match(s)
        if m:
            if cur:
                out.setdefault(cur, (title, " ".join(body)))
            cur, title, body = m.group(1), m.group(2), []
            continue
        if NOISE.match(s):
            continue
        body.append(s)
    if cur:
        out.setdefault(cur, (title, " ".join(body)))
    return out


def words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def main() -> None:
    a, b = paras(Path(sys.argv[1])), paras(Path(sys.argv[2]))
    print(f"ed1 {len(a)}  edB {len(b)}", file=sys.stderr)
    only_a = sorted(set(a) - set(b))
    only_b = sorted(set(b) - set(a))
    print("only in Ed1:", only_a)
    print("only in EdB:", only_b)
    low = []
    for n in sorted(set(a) & set(b), key=lambda x: (x.lstrip("U").zfill(6), x)):
        ta, xa = a[n]
        tb, xb = b[n]
        r = SequenceMatcher(None, words(xa), words(xb), autojunk=False).ratio()
        tr = SequenceMatcher(None, words(ta), words(tb)).ratio()
        if r < 0.6 or tr < 0.5:
            low.append((n, round(r, 2), round(tr, 2), ta, tb))
    print(f"common {len(set(a) & set(b))}, low-similarity {len(low)}")
    for row in low:
        print(*row, sep="\t")
    # best cross-match for low ones: does Ed1 text match a different EdB number?
    for n, *_ in low:
        xa = words(a[n][1])
        best = max(
            ((m, SequenceMatcher(None, xa, words(b[m][1]), autojunk=False).quick_ratio())
             for m in b),
            key=lambda t: t[1],
        )
        print("cross", n, "->", best[0], round(best[1], 2))


if __name__ == "__main__":
    main()
```
