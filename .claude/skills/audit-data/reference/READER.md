# Reader guide: checking FARfetched data against its source

You are a reader subagent. You get a batch file (JSON lines). Check each item
against its **local source copy**, then write your findings. Don't edit any
file in the repo or under `input/`. Don't download anything. Only write the
output file you were given.

**Read only the sections for your mode.** Every reader reads *Core* and
*Output*. Then:

| Batch | Mode | Also read |
|---|---|---|
| `batch_NN_field.jsonl` | field | *Mode: field* (skip the error catalogue) |
| `batch_NN_diff.jsonl` | diff | *Mode: diff*, *Error catalogue* |
| `batch_NN_full.jsonl`, and every audit-data batch | full | *Mode: full*, *Error catalogue* |

Each item says its `mode` too.

## Core

- The text comes out of PDFs through `pdftotext` (EASA CS, TCDS, NATO, DoD),
  OCR of 1950s scans (CAR 3), or HTML from the FAA DRS and eCFR. Regexes then
  cut it into provisions, paragraphs, basis lines and references. Expect the
  errors that layout extraction and pattern matching make.
- **The data is evidence, not truth, and so are the excerpts in your item.**
  `source_context` and `excerpt` slices come from the pipeline's own text copy
  (`tools/out/derived/tcds_text`, `tools/out/extracted`, the DRS JSON). They
  can share the data's bug. Each slice names its `file`, `lines` and `page`.
  When a slice looks wrong, garbled or doesn't settle the question, open the
  real source: for a PDF, read that page with the Read tool (`pages: "N"`)
  and look at the page image. pdftotext drops formulas, tables and
  subscripts, and mangles columns.
- To find something with no slice: `pdftotext -layout <pdf> - | grep -n
  '<distinctive phrase>'`, then read that page.
- If you can't find or open the source, say `could-not-check`. Don't guess.
  Report only what you saw in the source.

Severity:

- `blocker`: the content is wrong in a way that misleads a reader. Wrong
  words or numbers, the wrong provision or revision, a formula scrambled or
  missing, text lost, references that point at the wrong regulation or
  amendment. In a promotion item, also anything where staged is **worse than
  data/**.
- `major`: a real defect that leaves the meaning recoverable. Furniture in
  the text, a caption run in, a structure or label error, a lost subscript,
  a missed reference, a name cut short.
- `minor`: cosmetic. Spacing, case, an unlinked cross-reference.

## Mode: field

Each item is one field value that a script couldn't confirm (`reason:
field-flag`, with the script's `check` note) or a value it confirmed, sampled
to test the script (`reason: field-sample`). `field` names it
(`tcds.holder`, `title_at_revision`, `effective_date`, …), `where` says
where in the file, and `relpaths` lists every file holding the same value.

- Judge only that one value against the source: is `new` what the source
  prints, complete (not cut at a line wrap, no continuation dropped such as
  "S.p.A." or "trading as …") and in the right place? For a value the
  source doesn't print (a display group, a provenance note), say whether it
  is consistent with the evidence given, or `could-not-check`.
- The `excerpt` is usually enough. Open the PDF page only if it isn't.
- A `field-sample` that is wrong means the script missed it. Say so in the
  summary ("script passed it").
- **Deviation fields** (`deviation.<key>`, relpath under `deviations/`)
  come from the regulator's listing, not a PDF. `source` is either a DRS
  listing page with `#<docUniqueId>` (find the entry with that
  `docUniqueId` in the JSON's `documentList`; its labelled metadata is in
  `headerLink`, `description`, `subText` and `tags`) or an EASA detail page
  (`.html`). For `deviation.stage` (EASA): `final` when the page holds the
  final document, whatever its label says; `proposed` when only the
  proposal, CRD or comments are there. For `deviation.final`: the proposed
  and the final record must be the same special condition (same docket,
  same subject). For `deviation.citations`: each citation must be a section
  the title, number or regulation_ref names, at the right part.
- Nothing else in the file is in scope.

## Mode: diff

Each item is one change from data/ to staged: a changed version (`changed`
holds word hunks `{before, data, staged, after}` or line hunks `{before,
data, staged}`) or a changed TCB (`changed` holds `lines_added`,
`lines_removed` and `lines_changed` (`{old, new}`), each with its
`source_context`). `hunks_total` or `unchanged_lines` says how much was left
out.

- Judge **only what changed**. For each hunk or line: does the staged side
  match the source (a fix), or move away from it (a regression), or neither?
  Say which in the summary.
- **Unchanged text is out of scope.** Don't audit it and don't report its
  problems, even real ones. That is audit-data's job. The one exception: a
  change that makes an existing problem worse, which counts as new.
- `pre_existing`: true when the problem is on the data/ side too (the hunk's
  `data` text, or a removed line, already had it), false when the staged
  change brought it in.
- A removed TCDS line is fine when the source has no such line, or when its
  text now sits in an added line (a merge or split fixed). Lost text is a
  blocker.
- Read the wider file (`relpath`, or `tools/out/staged/<relpath>`) only to
  understand a hunk, not to review it.

## Mode: full

Each item is content with no data/ side to compare against: an audit-data
sample, a new provision or version (`staged_text`), or a new TCB
(`certification_basis`). Check all of it against the source. Items list
`extracted` (pipeline text, nearly raw) and `source` (a PDF, or for FAA a
cached DRS JSON holding HTML), and for a TCDS `source_text` (the pdftotext
output the parser used). For a TCDS, compare the certification basis section
line by line.

A `deviation` item is one new deviation record (docs/DATA_FORMAT.md
§Deviation file) with `listing_excerpt`, the regulator's listing for it
(`source` says where; see *Mode: field* for the formats). The record holds
only what the listing says, never the document's text. Check every field
against the listing: values verbatim; nothing the listing prints for the
field left out; `kind` and `stage` (as in *Mode: field*); `number` the
identifier as printed; each citation named by the title, number or
regulation_ref; `final` the same SC. Use category `deviation`. Skip the error
catalogue for these items. Any `hits` are automated check hits on the item: confirm or
dismiss each.

## Error catalogue

Look for these first. They are listed roughly by how often they've been
reported.

### Provision text

1. **Formulas.** Read in row order (`ω = πV/(2V_A)` became `πV ω = 2V A`);
   numerator and denominator interleaved; an image formula missing; Greek
   letters or `≤ ≥ √ ∑ ∫` lost; subscripts flattened (`VMO` for `V_{MO}`;
   superscripts are `^{x}`); an equation run into a paragraph instead of its
   own `$$…$$` line.
2. **Boundaries.** The next heading run onto the end; the text opening
   mid-sentence; a contents page read as the provision; truncation; two
   provisions merged.
3. **Page furniture.** Running headers or footers, page numbers, `Amdt.
   25/18` or `CS-25 BOOK 1` banners, dot leaders, change bars, FR amendatory
   or filing lines (`[F.R. Doc. 52-1420; Filed …]`).
4. **Figures and tables.** Captions or axis labels in the running text; a
   table flattened into numbers. Tables are `{| … |}` with `||` between
   cells: check cells against the source's rows and columns.
5. **OCR damage (CAR 3 above all).** `(l)`/`(1)`, `(c)`/`(e)`; junk on
   V-speeds; words broken in two; word salad; wrong digits (speeds, weights,
   load factors, percentages matter most).
   CAA `CAR3-0` is Part 3 as printed 1 November 1949 (`3.xx` numbering),
   read from the CAR3-1 compilation. The 1945 Part 03 (`CAR3-00c/00d`,
   `03.xxx` numbering) is another document: never compare against it.
6. **Structure.** Wrong depth; skipped labels; an appendix or roman-numeral
   list left as one block. One paragraph per line, depth from the labels
   (docs/DATA_FORMAT.md §Text format).
7. **Wrong revision.** Words that only appear in another amendment. FAA
   bracketed text (`[(a) …]`) marks words that amendment changed; a bracket
   not in the source is suspect.
8. **Metadata.** A title not matching the source heading; a
   `publication_cite` that isn't a citation; a `grouping` naming the wrong
   subpart.

### TCDS certification basis

1. **Line boundaries.** A runaway line swallowing the next section; page
   footers or headings inside or as a line; one requirement split over two
   lines; lines dropped.
2. **References.** `raw_reference` is the TCDS text verbatim: compare it
   character for character. `references` is its parse: check each
   regulation, amendment level (`to`/`from`) and provision list. Common
   misses: a wrap splitting an amendment (`23- 25`), `through` or en-dash
   ranges, `as amended by`, sections at a different amendment from the part,
   `except` lists read as included, JAR vs CS vs FAR, Part 23 vs 25.
3. **Entry type.** An ELOS, special condition or exemption typed as
   `regulation`, or the reverse. A regulation line with `references: []`
   where the regulation and amendment could be parsed.
4. **Model and category.** Categories not matching the TCDS; a basis on the
   wrong model; applicability lost (`for S/N 1001 and on`).

## Output

Write one JSON object per line to the output path you were given, one line
per item, even when it is clean:

```json
{"id": "02.03", "relpath": "documents/easa/cs-25/331.json", "locator": "CS25-18",
 "verdict": "issues", "findings": [
   {"severity": "blocker", "category": "formula",
    "summary": "ω formula read in row order (regression: data/ had it right)",
    "data_excerpt": "πV ω = 2V A",
    "source_excerpt": "ω = πV / (2 V_A)",
    "source_ref": "input/Regs/EASA/CS-25/CS25-18.pdf p.1-C-4",
    "pre_existing": false, "confidence": "high"}]}
```

- `id` is the item's `id` (promotion batches; omit for audit-data).
- `verdict`: `ok`, `issues` or `could-not-check`.
- `locator`: the designator; `"<issuer> <key> <field>"` for a deviation; `"<issuer> <tcds_number> #<display_order>"` for a
  basis line; `"<issuer> <tcds_number> <field>"` for a TCB field.
- `category`: formula, boundary, furniture, figure-table, ocr, structure,
  wrong-revision, metadata, tcds-lines, tcds-references, tcds-entry-type,
  tcds-model, tcds-holder, deviation, other.
- `pre_existing`: always true or false in promotion items (diff mode says
  how); omit in audit-data and full mode for new content.
- Excerpts under 200 characters. A finding needs a `source_excerpt` or a
  `source_ref`.

When the batch is done, reply with one line: items by verdict, findings by
severity. Then add any **pattern** you saw more than once that a regex could
catch (a candidate check for `scripts/scan_data.py`), unless the prompt lists
it as already known. Don't repeat the findings in the reply.
