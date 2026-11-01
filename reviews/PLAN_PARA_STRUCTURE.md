# Plan: structured paragraph text for provisions (all sources)

## Context

Every regulation pipeline (FAA DRS, eCFR, Federal Register, CAR 3 OCR, EASA CS
PDFs) flattens a provision into one line, and FARfetched shows it in a single
`<div class="prose">` (`FARfetched/src/farfetched/templates/regulations/provision.html`).
A provision like §23.1309 is one paragraph about 3,000 characters long. We want
`(a)` / `(1)` / `(i)` / `(A)` levels kept as data, so the app can show nested,
linkable, selectable paragraphs. The cert-basis `paragraph: "(a)"` qualifier
can then point at real text.

The decided format is **"label-line text"**, which stays a string in `text`.
Its robustness rules come from the user's concerns:

- **Depth comes from the labels, not from whitespace.** Indentation is
  cosmetic: a formatter writes it, the build checks it, and the build only
  reads it to break a genuine tie (see the rules below). It is always compared
  relative to the lines around it, never counted against a fixed width.
- **A line is a block, not "the" paragraph of an item.** An item can have
  several blocks: its labelled line plus any unlabelled lines that follow it.
- **Layout only.** Structuring may only add line breaks and indentation. A
  structured text, flattened, must equal the original flat text character for
  character. Emit asserts this, so the segmenter can never change wording.

### Evidence it holds up

A crude prototype (one regex plus depth-from-labels, run read-only over the
current `data/`) gave these results:

| Source | Text versions | Clean structure | No labels (stays flat) | Failed |
|---|---|---|---|---|
| FAA Part 23 | 1,110 | 930 | 111 | 69 |
| CAA CAR 3 | 467 | 119 | 307 | 41 |
| CAB CAR 3 reissue | 396 | 74 | 260 | 62 |

The failures were mostly real data defects, not limits of the format:

- OCR damage: `(bo)` for `(b)` and `Gi)` for `(ii)` in `cab/car-3-reissue/109`.
- Column bleed: stray text before `(a)` in `caa/car-3/381` CAR3-0.
- `(a)` labels the prototype missed.

The rest were inline lists inside a sentence ("designed for (1) … and (2) …",
`caa/car-3/191`), which correctly stay inline. So the segmenter doubles as a
data-quality detector.

## The format (README contract)

```
The requirements of this section ... are applicable ...      ← top level, unlabelled
(a) Each item of equipment, each system, and each installation:
  (1) When performing its intended function, may not ... any--
    (i) Equipment essential to safe operation; or
    (ii) Other equipment unless ...
  [(4) In a commuter category airplane, ...]                  ← FAA change brackets kept
(b) The design of each item ... must comply with the following:
  (1) It must perform its intended function ...
  (2) ...
  Each item of equipment ... must also ...                    ← second block of (b)
(c)
  (1) Text where (c) has no own words ("(c)(1)" in source)    ← label-only line
```

Rules (parser in `build.py`, the contract owner):

1. **Lines.** One block per non-empty line. Blank lines are ignored. Tabs and
   trailing whitespace are errors. A block never contains a hard line break.
   Formulas go on their own unlabelled line.
2. **Labels.** An optional leading `[`, then one or more `(x)` tokens, then a
   space or the end of the line. `x` is 1–5 alphanumerics. Compound `(a)(1)`
   splits into a label-only `(a)` and `(1)`. The label text is kept verbatim.
   Lines starting `1.` or `A.` are unlabelled in v1 (a possible later
   extension).
3. **Depth from labels (style stack).** Each label has candidate styles:
   lower-alpha (`a`…`z`, `aa`), number, lower roman, upper alpha, upper roman.
   A label either continues an open level (its next expected value, innermost
   level first) or opens a new level (value 1 of a style). That covers FAA's
   level-5 italic `(1)` and ambiguous `(i)`: after `(h)` it continues the
   letter level, otherwise it opens a roman level.
4. **Ties.** If more than one reading is valid (for example `(i)` after `(h)`
   while a numbered level is open), the line's indentation decides, relative
   to the open items' lines. If indentation doesn't settle it, the build fails
   loudly.
5. **Unlabelled lines** belong to the innermost open item whose label line is
   indented less than they are. At the left margin they are top-level text.
6. **Check.** After depth is worked out, every labelled line's indentation
   must agree in relative terms (deeper, same, shallower). Otherwise
   `build.py --check` fails, and the tools formatter fixes it.
7. **Label gaps** (`(a)` then `(c)`): not an error, because real regulations
   drop paragraphs. They are counted in the build report.

## Backend: `build.py` and the SQLite contract (`SCHEMA_VERSION` 2 → 3)

- **`build.py`:**
  - Add `parse_paragraphs(text) -> list[Paragraph]` (dataclass: seq, depth,
    label, path, text) using rules 1–7.
  - Run it on every version with `text`, except `TEXT MISSING`, deleted and
    `same_as` versions.
  - Fail loud on rule violations.
- **New table:**
  ```sql
  CREATE TABLE provision_paragraphs (
    id INTEGER PRIMARY KEY,
    provision_version_id INTEGER NOT NULL REFERENCES provision_versions(id),
    seq INTEGER NOT NULL,          -- document order
    depth INTEGER NOT NULL CHECK (depth >= 0),
    label TEXT,                    -- '(ii)', NULL when unlabelled
    path TEXT,                     -- '(a)(1)(ii)'; enclosing item's path when unlabelled; NULL at top
    text TEXT NOT NULL,            -- may be '' for label-only
    UNIQUE (provision_version_id, seq)
  ) STRICT;
  ```
  - An index on `(provision_version_id, path)`.
  - Flat texts get one unlabelled row, so the app has a single rendering path.
  - `provision_versions.text` keeps the label-line string unchanged.
- **Paragraph refs:** a cert-basis `paragraph` is now checked against the
  resolved version's paths. If the version is structured and the path is
  absent, the build fails. If the version is flat, it is counted as
  `paragraph_refs_unverifiable` in the report.
- **`cert_basis_report.json`:** new counts:
  - `provision_paragraphs` rows
  - structured vs flat versions
  - label gaps
  - `paragraph_refs_unverifiable`
- **`schemas/provision.schema.json`:** `text` stays a string. Add a pattern
  that rejects tabs.
- **`README.md`:**
  - A "Text format" section with the rules above.
  - The new table in the SQLite schema section.
  - The paragraph-ref change.
- **`tests/` (and the identical `tools/tests/e2e/` copy):**
  - Parser unit tests covering each rule and each tie case.
  - Build tests for the table and for the paragraph-ref failure.
  - A smoke query on §23.1309 paths.

## Backend: `tools/` (source-agnostic structuring)

- **New `tools/common/structure.py`:**
  - `segment(flat: str) -> str | None` turns flat text into label-line text,
    or returns `None` (stays flat) when unsure.
  - It finds paragraph markers only after the start of the text, after
    `. : ; ] -- — –`, or after `; or` / `; and` / `, or` / `, and`.
  - It never treats these as markers: text after
    `paragraph(s)|section|§|Sec.|of|under|in|to|and|through`, or text
    followed by `of this`. That keeps cross-references like "§23.561(b)(2)"
    inline.
  - It reuses `build.parse_paragraphs` to validate and indent. Tools import
    from the contract one way, as the tools tests already do.
  - It returns `None` on any sequence break, unresolved tie, or
    `flatten(result) != flat`.
  - It also provides `flatten(text) -> str`.
- **Emit stages call it in one place each:**
  - `tools/regulations/faa/emit.py`
  - `tools/regulations/easa/emit.py`
  - `tools/regulations/car/emit.py`

  Extracted files stay as they are, so nothing is re-fetched or re-OCR'd.
- **eCFR improvement:**
  - `tools/common/ecfr.py:section_text` keeps a `\n` between `<P>` blocks
    instead of collapsing them. This recovers the trailing unlabelled
    paragraphs ("Each item … must also …") that flat sources merge into the
    last item.
  - eCFR `<I>1</I>` italic labels give certain level-5 depth.
  - The DRS eCFR-rendering path (`faa/extract.py:_extract_ecfr_rendering`)
    keeps `<p>` breaks the same way.
  - Every DRS-vs-eCFR comparison and `text_issues` compares `flatten()`
    output, so verification is unchanged.
- **Report:** emit writes `tools/out/reports/structure_report.tsv` (path,
  designator, outcome: structured / flat-no-labels / flat-failed, reason,
  context). Failures stay flat and get grouped into ISSUES.md as data-quality
  items (for example, CAR OCR label damage).
- **Known limitation (ISSUES.md):** for flat-only sources (old DRS, FR, OCR),
  a trailing unlabelled paragraph after a sub-list can't be told apart from
  the last item's text, so it stays attached to that item. The meaning is
  intact; only the layout is approximate.
- **Tests (`tools/tests/common/test_structure.py`):** fixtures built from the
  real edge cases found:
  - §23.1309 with brackets
  - `[(b) [Removed.]]`
  - compound `(c)(1)`
  - inline `(1) … and (2)`
  - `(h)`→`(i)`
  - level-5 `(1)`
  - OCR `(bo)` → flat-failed
  - a cross-reference that must not split
  - plus the layout-only invariant
- **Hand-edited data:** the manual-provenance manifest is currently empty, so
  nothing needs restructuring by hand. From now on, hand restructuring follows
  the normal `provenance.source = "manual"` route.

## Frontend: FARfetched (separate repo, after the data side lands)

- **`services/queries.py` + `services/reader.py`:**
  - Add `version_paragraphs(conn, version_id)`.
  - Build a tree in Python and pass it to the template instead of `page.text`.
- **Template:**
  - A recursive macro renders `<ol class="reg-list">` / `<li id="p-a-1-ii">`.
  - Each item shows its stored label in a `<span class="reg-label">`. Never
    CSS counters: labels skip and repeat in real regulations.
  - Unlabelled blocks are `<p>` inside their item.
- **CSS (`static/css/app.css`):**
  - Hanging indent per depth.
  - A `:target` highlight.
  - Print layout that stays indented.
  - Optional subtle styling for FAA `[ … ]` change brackets.
- **Interaction:**
  - Clicking a label copies its citation (`§23.1309(a)(1)(ii)`) and anchor
    link.
  - A basis entry with `paragraph` highlights that path and scrolls to it.
  - Collapsing other paragraphs is optional.
- **Compatibility:** bump the app's expected `user_version` to 3.
- **Out of scope:** tables and in-paragraph formatting. Tables are rare in
  regulation text (about 8 FAA versions mention one). They stay flat for now,
  and `|` lines are reserved for a later table extension.

## Order of work

1. Contract: `build.py` parser, table, report, README, schema, tests,
   `SCHEMA_VERSION` 3. With today's flat data this already works (all
   single-row).
2. `tools/common/structure.py` and its tests; wire it into the three emitters;
   the eCFR/DRS `<p>` boundary change.
3. Re-run the emitters, review `structure_report.tsv`, and log failures in
   ISSUES.md. Then the user runs `promote --dry-run` and the real promotion.
4. FARfetched rendering.

## Verification

- `uv run pytest`, `uv run ruff check .`, `uv run mypy .` in both `tests/` and
  `tools/tests/`.
- `uv run python build.py`, then
  `sqlite3 cert_basis.sqlite "SELECT depth,label,path,substr(text,1,60) FROM provision_paragraphs pp JOIN latest_versions lv ON lv.id=pp.provision_version_id ..."`
  for §23.1309. Expect `(a)`, `(a)(1)`, `(a)(1)(i)`, `(a)(1)(ii)`, …
  `(b)(1)`.
- Check the report: zero build failures, structured share at or above the
  prototype baseline (FAA ≥ 930/1,110), and DA 40 paragraph refs verified.
- Layout invariant: a test over the whole staged tree asserts
  `flatten(new text) == old text`.
- FARfetched: run the app, open §23.1309 and a DA 40 basis entry with a
  paragraph qualifier, and check nesting, anchors, highlight and print view.
