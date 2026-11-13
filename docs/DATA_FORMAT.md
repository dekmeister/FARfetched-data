# Data format (JSON contract)

The field-level contract for the JSON files in `data/`. They are written only
by [tools/](../tools/) (emit → promote) and read only by
the build ([build.py](../build.py), code in [certbuild/](../certbuild/)),
which enforces everything here. The SQLite side of
the contract is in [SQLITE.md](SQLITE.md), and the history of the format is
in [SCHEMA_HISTORY.md](SCHEMA_HISTORY.md).

Contents: [File paths](#file-paths) · [Document file](#document-file-datadocumentsfaa23_documentjson) ·
[Provision file](#provision-file-datadocumentsfaa231309json) ·
[Grouping labels](#grouping-labels) · [Text format](#text-format) ·
[Aircraft model file](#aircraft-model-file-dataaircraftmanufacturer-slugmodel-slugjson) ·
[Resolution rules](#resolution-rules) · [Citations](#citations) ·
[Deviation file](#deviation-file-datadeviationseasa120960json)

## File paths

```
data/documents/{issuer}/{document}/_document.json
data/documents/{issuer}/{document}/{key}.json
data/aircraft/{manufacturer-slug}/{model-slug}.json
data/deviations/{issuer}/{key}.json
```

Document file paths are flat by design: issuer + document + provision key
are the only parts of a citation that are truly stable. Grouping (subpart)
and the CFR title live inside the files, so a provision can be re-subparted
without a rename. `{issuer}` is the issuer code in lower case,
`{document}` is the document's `slug` and `{key}` the provision's `key`
(see [Provision file](#provision-file-datadocumentsfaa231309json): for FAA,
CAR and EASA it is the section or paragraph number). The build fails if a
file's path disagrees with the identity fields inside it.

## Common rules

All schemas use `additionalProperties: false`. Dates are ISO `YYYY-MM-DD`.
URLs must be `http(s)://`. `provenance` is always
`{"source": "scraped" | "ocr", "notes"?: string}` and absent means
`"scraped"`. There is no `"manual"`: every file in `data/` is built from
source by [tools/](../tools/), and a correction is an override row there.

## Document file (`data/documents/faa/23/_document.json`)

One file per document. Holds the master revision list — the attributes that
belong to the revision as a whole.

```json
{
  "issuer": "FAA",
  "doc_kind": "regulation",
  "code": "14 CFR 23",
  "slug": "23",
  "title": "Airworthiness Standards: Normal, Utility, Acrobatic, and Commuter Category Airplanes",
  "revisions": [
    { "designator": "23-62", "ordinal": 62, "effective_date": "2012-01-31" }
  ]
}
```

**Top-level fields**

| Field       | Type   | Nullable | Purpose |
|-------------|--------|----------|---------|
| `issuer`    | enum   | no       | `FAA`, `CAA`, `CAB`, `EASA`, `DOD`, `NATO`. CAA and CAB are historical US issuers whose successor is the FAA (recorded in the `issuers` table, not the code). `DOD` is the U.S. Department of Defense (MIL-HDBK-516). `NATO` is the North Atlantic Treaty Organization, which has no country and is of kind `military` (STANAG 4671 / AEP-4671). |
| `doc_kind`  | enum   | no       | `regulation`, `certification_spec`, `amc_gm`, `advisory_circular`, `handbook`, `standard`. Special conditions, ELOS and exemptions are [deviation files](#deviation-file-datadeviationseasa120960json), not documents. |
| `code`      | string | no       | Human citation: `"14 CFR 23"`, `"CAR 3"`, `"CS-23"`. |
| `slug`      | string | no       | Path segment, lower case: `"23"`, `"car-3"`, `"cs-23"`. Unique per issuer. |
| `title`     | string | yes      | Document title. |
| `revisions` | array  | no       | One entry per revision that has ever touched the document. Non-empty. |

**Per-revision fields**

| Field            | Type    | Purpose |
|------------------|---------|---------|
| `designator`     | string  | As printed: `"23-62"`, `"CS23-5"`. Unique per document. For `doc_kind: regulation` it must match `^[A-Za-z0-9]+-[0-9]+$`; other kinds only forbid surrounding whitespace. |
| `ordinal`        | integer | Sort key, unique per document. `0` is the original issue. |
| `effective_date` | date    | Same for every provision the revision changed. Must not be in the future. |
| `provenance`     | object  | Optional. |

## Provision file (`data/documents/faa/23/1309.json`)

One file per provision. Ordinal and effective date come from the document file.

A provision is one requirement followed through the document's revisions.
Its `key` is its identity; its `number` is a printed label. In the CFR, CAR
and the EASA CS the two are the same and a number is never reused. A
document such as MIL-HDBK-516 reuses a number for an unrelated requirement
in a later edition, and renumbers a requirement that carries on (516B 5.2.3
is 5.2.2 in 516B Change 1), so there the label is recorded per version.

```json
{
  "issuer": "FAA",
  "document": "23",
  "key": "1309",
  "number": "1309",
  "current_grouping": "Subpart F — Equipment",
  "canonical_title": "Equipment, systems, and installations.",
  "subject_group": "General",
  "versions": [
    {
      "designator": "23-62",
      "grouping_at_time": "Subpart F — Equipment",
      "title_at_revision": "Equipment, systems, and installations.",
      "text": "...full text at this revision...",
      "publication_cite": "76 FR 75736",
      "source_url": "https://drs.faa.gov/browse/excelExternalWindow/{GUID}.0001",
      "actions": [
        { "type": "nprm", "reference": "09-12", "issued_on": "2009-07-23",
          "source_url": null, "notes": null }
      ],
      "provenance": { "source": "scraped" }
    }
  ]
}
```

**Top-level fields**

| Field              | Type   | Nullable | Purpose |
|--------------------|--------|----------|---------|
| `issuer`           | enum   | no       | Must match the directory and the document file. |
| `document`         | string | no       | The document's `slug`. Must match the directory. |
| `key`              | string | no       | Stable, opaque identity within the document; must match the file name. Same pattern as `number`. Equal to `number` unless the document reuses or renumbers numbers; then it is the number at first appearance, with a suffix when that was already used as a key (`"4.1.3-516a"`). Never shown as a citation. |
| `number`           | string | no       | Number as printed at the latest version, e.g. `"1309"`, `"1309a"`, `"A23"` (appendix), `"4.1.3"`. The latest version must not carry a different per-version `number`. |
| `current_grouping` | string | yes      | Present-day subpart (or equivalent), in the [grouping style](#grouping-labels): `Subpart F — Equipment`. Display only. |
| `canonical_title`  | string | no       | Present-day heading. |
| `subject_group`    | string | yes      | The finer heading inside the grouping: the FAA DRS Subject Group, the CAR sub-heading (regs.csv `Subsubpart`, `"Controllability"`), and for MIL-HDBK-516 the parent heading (`"4.1 Design criteria"`) under the section in `current_grouping`. Never a subpart. |
| `versions`         | array  | no       | One entry per revision that changed this provision. Non-empty. |

**Per-version fields**

| Field                | Type   | Nullable | Purpose |
|----------------------|--------|----------|---------|
| `designator`         | string | no       | Must be declared in the document file. One version per designator. |
| `number`             | string | yes      | The number as printed at this revision, when it differs from the top-level `number` (a renumbered provision). Absent = the top-level `number`. Two versions printed at one revision may not share a number (a deletion excepted), and at every revision a number names at most one provision in force. |
| `grouping_at_time`   | string | yes      | Subpart the provision sat under at this revision, in the [grouping style](#grouping-labels). EASA, NATO, CAR and MIL-HDBK-516 read it from the revision's own source. **FAA: the present-day label** (DRS repeats today's subpart on every historical version; ISSUES FAA-31). It is the heading over this version's text when it was printed: a subpart renamed later without a new version keeps the old name here. |
| `title_at_revision`  | string | no       | Heading as it read at this revision. |
| `text`               | string | one of   | Full text at this revision, in the label-line format (see [Text format](#text-format)). No tabs or carriage returns. The literal `"TEXT MISSING"` is the reserved marker for a known gap: the pair must exist (per a manifest) but the source is unreadable. The DB flags these rows with `text_missing = 1`. |
| `same_as_designator` | string | one of   | Instead of `text`: the text is unchanged from this earlier version of the same provision. The build copies the text and records the link. Must not point at a deleted version. |
| `deleted`            | `true` | one of   | Instead of `text`: this revision deleted (removed, repealed) the provision, e.g. every old-numbered CS-23 paragraph at CS23-5. Only valid while the provision is in force (not as its first version, not twice in a row). A later version may re-create it. Stored with `text` NULL and `deleted = 1`. |
| `publication_cite`   | string | yes      | Where the revision was published, e.g. `"35 FR 5665"`. Omit (or `""`) when unknown — including for original issues. The schema rejects the sentinel `"Initial Adoption"`. |
| `source_url`         | url    | yes      | Where the text was transcribed from. Prefer DRS `https://drs.faa.gov/browse/excelExternalWindow/{GUID}.0001`. |
| `actions`            | array  | yes      | Rulemaking actions behind this version, as the source records them for this provision (see below). Omit when none are known. |
| `provenance`         | object | yes      | How the text was obtained: `scraped` (default) or `ocr`. `notes` records any override applied to it. Carried into the DB so the app can mark OCR text. |

Actions stay on the version rather than the revision because the source (DRS)
records them per section, and the per-section lists for one amendment don't
always agree.

### Grouping labels

`current_grouping` and `grouping_at_time` use one style for every document,
so the app can show them alike and group a renamed subpart by its label:

| Case | Value |
|---|---|
| Subpart (FAA, EASA, NATO, CAR) | `Subpart B — Flight` |
| General | `Subpart A — General` (it is Subpart A in every source) |
| Reserved subpart | `Subpart C — Reserved` |
| SFAR inside a subpart (14 CFR 25.1801) | `Subpart I — Special Federal Aviation Regulations` |
| MIL-HDBK-516 section | `Section 7 — Propulsion` |
| Every appendix | `Appendices` (one group, no label; each appendix's letter is in its key) |

- `{Label} — {Name}`: the label as the source prints it (`Subpart` plus one
  or two capital letters, or `Section` plus a number), then an em dash with
  exactly one space either side, then the name. No en dash or hyphen
  separator, and no second separator inside the name. A dash inside the
  name is the unspaced em dash the source prints there: `Subpart C — Aging
  Airplane Safety—Widespread Fatigue Damage` (14 CFR 26, as eCFR prints it).
- The name keeps the source's own mixed case. A name the source prints in
  capitals is put in heading case (small words such as *and*, *of*, *the* in
  lower case; acronyms and words with digits as printed), so
  `Design and Construction` reads the same in every document.
- A subpart renamed between revisions keeps its label: `Subpart C —
  Structure` and `Subpart C — Structures` are one subpart under two names.
  The label is the stable part; a MIL-HDBK-516 section number is not (an
  edition can reuse it for a different section).
- The finer heading inside a group is `subject_group`, never the grouping.
- Null is allowed (no grouping known).

The build fails on any other value (`certbuild/sources.py`
`check_groupings`, also run by `--check`). A new kind of label or letterless
group (for example `Special Federal Aviation Regulations` for SFARs outside
any subpart) is added there and here together.

### Text format

`text` is **label-line text**: a plain string whose line breaks and
indentation carry the paragraph structure (`(a)` / `(1)` / `(i)` / `(A)`), so
the app can show nested, linkable paragraphs and a cert-basis `paragraph`
qualifier can point at real text.

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
(c)(1) Text where (c) has no words of its own                 ← compound: rows (c) and (c)(1)
  (2) ...
```

**A text with one line is flat**: it becomes a single unlabelled paragraph,
whatever it starts with. Labels are only read in texts with several lines.

Rules for a structured (multi-line) text, enforced by `build.py`:

1. **Lines.** One block per non-empty line. Blank lines are ignored. Tabs and
   trailing whitespace are errors; indentation is spaces. A block never
   contains a line break.
2. **Labels.** An optional leading `[` (or `[ `), then one or more `(x)`
   tokens (`x` is 1–5 letters or digits), then a space or the end of the
   line. Compound `(c)(1)` gives a label-only `(c)` row and a `(1)` row. Labels
   are stored verbatim (`[(4)`); paths use the bare tokens (`(a)(4)`). A token
   that reads in no style, such as `(OEI)`, is not a label: its line is
   unlabelled.
3. **Depth from labels (style stack).** Styles: lower alpha (`a`…`z`, then
   `aa`, `bb`…), number, lower roman (`i`…`xxxix`), upper alpha, upper roman.
   `l`, `c`, `d`, `m` are always letters. A label either continues an open
   level (a later value of its style) or opens a new level under the innermost
   open item (value 1 of a style). This covers FAA's level-5 `(1)` and the
   ambiguous `(i)`.
4. **Indentation picks the reading.** Of the readings rule 3 allows,
   indentation picks one: continuing a level means the same indentation as
   that level's line; opening a level means more than the parent's line. It
   is only ever compared with other lines, never counted against a fixed
   width. If no reading fits, the build fails (this is the layout check).
   (The levels opened by a compound label have no line of their own: a later
   sibling only has to be indented more than the compound line, and if that
   leaves two exact readings the build fails as ambiguous.)
5. **Unlabelled lines** belong to the innermost open item whose label line is
   indented less than they are. With no such item they are top-level text.
6. **Label gaps** (`(a)` then `(c)`, or a text starting at `(b)`) are allowed,
   because real regulations drop paragraphs, and counted in the build report.
7. **Section headings.** A line starting `Sec. ` and an appendix section
   number (`Sec. F23.2 Part II--Test Method …`: a capital letter, digits, a
   dot, digits) is a section heading. It closes every open level, so labels
   restart under it, and every path after it starts with its number
   (`F23.2(b)(1)`). Lines before the first heading have no section. A heading
   must not be indented, and a section number may not repeat in one text.
   This is how FAA appendices assembled from their DRS sections keep each
   section's own `(a)…` run.

   **Roman headings.** A text that opens with `I. ` (roman numeral, a dot,
   a space, a capital) is divided by roman numerals: an unindented line
   `II. Definitions`, `III. Trim.` … is a heading whose section number is the
   numeral, so paths read `IV(b)(1)`. A numeral counts only as the next one
   in the run (`I`, `II`, `III`, …, up to `XXXIX`); any other `V. ` line is
   ordinary text. Used by the helicopter IFR appendices (CS-27/29 and FAA
   27/29 Appendix B). A `paragraph` qualifier is a run of bare labels,
   so it matches no path inside a sectioned text.

   ```
   Sec. F23.1 Part I--Acceptable Test Procedure …
   (a) Conditioning. …
   (b) Specimen configuration. …
     (1) Thick foam parts …                  ← path F23.1(b)(1)
   Sec. F23.2 Part II--Test Method …
   Use this test method to evaluate …        ← top level, section F23.2
   (a) Definitions. …                        ← path F23.2(a)
   ```

8. **Tables.** A table is a block of lines, all indented alike: an open
   line `{|` (optionally followed by a space and the caption), one line per
   row, and a close line `|}`. The whole block is unlabelled and belongs to
   an item by rule 5, like any unlabelled line; notes printed after a table
   are ordinary unlabelled lines. See [Tables](#tables) for the row syntax.
9. **Formula lines.** A line whose whole content (after the indentation) is
   `$$ <formula> $$` is a display formula. It is always unlabelled and
   belongs to an item by rule 5. Sub- and superscripts may appear in any
   line. See [Inline markup](#inline-markup).

#### Tables

```
(a) HIRF environment I is specified in the following table:
  {| Table I. - HIRF Environment I                       ← open line, caption
  ! Frequency {r2} ! Field strength (volts/meter) {c2}   ← header cells, spans
  ! Peak ! Average
  | 10 kHz-2 MHz | 50 | 50                               ← data cells
  | 2 MHz-30 MHz | 100 | 100
  |}                                                     ← close line
  In this table, the higher field strength applies at the frequency band edges.
(b) …
```

- **Rows.** A row line is a run of cells. Each cell opens with a delimiter:
  `!` for a header cell, `|` for a data cell. A delimiter is a token of its
  own: at the start of the line, or with a space on both sides. So
  `|H(ω)|` inside a cell is text, not a delimiter. An empty cell is a
  delimiter followed directly by the next one (`| | x`).
- **Spans.** A cell may end with `{rN}` (row span), `{cN}` (column span) or
  `{rN cM}`, each 2 or more. Once spans are applied every row must have the
  same width and no span may overlap another or run past the last row.
- **Never labels.** A table line is never read for labels or section
  headings: `| (a) Aileron | 0.75` is a row whose first cell is "(a) Aileron".
- **Reserved.** `{|`, `|}` and `|-` are table markup and occur nowhere else;
  a line that starts with `!` or `|` followed by a space is a row and must be
  inside a block. A cell or caption may not contain table markup. Tables
  don't nest, a table has at least one row, and a single-line (flat) text
  can't hold one.
- **Flat form.** Flattening (below) joins a table's lines with ` |- `
  between rows, so a table is one line again:
  `{| Table I. … |- ! Frequency {r2} ! … |- | 10 kHz-2 MHz | 50 | 50 |}`.
  The tools carry tables in this form until layout, and override rows write
  it.
- **Plain form.** The words with all table markup removed (`{|`, `|}`,
  `|-`, delimiters, spans): `build.plain_text`. Used to compare wording
  across layouts (and by the tools to compare versions), never for display.
- Table markup is written by an extractor reading a real table in the
  source, or by an evidence-backed override row. Layout never invents it.
- A cell may hold `_{…}`/`^{…}`, but not a formula line (`$$`).

#### Inline markup

Text encodes the *meaning* of typeset notation in a small linear markup; how
to show it is the app's job. No TeX, no MathML.

```
(a) … a sinusoidal input of speed V_{A}, with a frequency not less than:  ← subscript
  $$ ω = πV/(2V_{A}) $$                                                    ← formula line
  where t_{max} is …
(b) … not more than 10^{-7} per flight hour.                              ← superscript
```

- **Sub/superscript.** `_{x}` is a subscript, `^{x}` a superscript. The
  content is non-empty and contains no `{`, `}`, `$` or line break, so
  markup never nests. `_{` or `^{` that doesn't open such a span is an
  error (unclosed, empty, nested). A bare `_`, `^`, `{` or `}` is literal
  (OCR junk has them).
- **Formula line.** A line that is wholly `$$ <formula> $$` (one space
  inside each mark, after the indentation) is a display formula: rule 9.
  It may hold sub/superscripts. Fractions and roots are written linearly:
  `πV/(2V_{A})`, `√(x)`. `$$` anywhere else is an error: mid-line, in a
  labelled line, in a heading, in a table, or in a single-line (flat) text.
  A text with a formula therefore always has several lines.
- **Plain form.** The words with the markup removed (`V_{A}` → `VA`,
  `$$ x $$` → `x`), together with the table markup: `build.plain_text`.
  Used for similarity and for comparing words across versions, never for
  display.
- **Who writes it.** Extractors writing a sub/superscript that the source
  marks (an HTML `<sub>`, a glyph set lower on the PDF line), or an
  evidence-backed override row. Layout never writes markup; it may only
  move a `$$ … $$` span onto its own line.

**Layout only.** Structuring may only add line breaks and indentation
(and so may put a `$$ … $$` span, or a table, on lines of its own; it never
writes markup).
Flattening a text (strip every line, drop blank ones, join with single spaces;
table rows with ` |- `) gives its words; the tools assert that layout never
changes them. A ` |- ` row separator is the one place layout may turn
something other than a space into a line break. The tools
write two spaces per level, but the build accepts any consistent indentation.
`tools/s00_common/structure.py` produces the format from flat text; see
[tools/README.md](../tools/README.md) and [tools/s00_docs/STRUCTURE.md](../tools/s00_docs/STRUCTURE.md).

**Action fields**

| Field        | Type   | Nullable | Purpose |
|--------------|--------|----------|---------|
| `type`       | enum   | no       | `nprm`, `final_rule`, `direct_final_rule`, `interim_final_rule`, `easa_npa`, `easa_opinion`, `easa_decision`, `jar_npa`, `jar_change`, `other`. |
| `reference`  | string | yes      | Notice, docket or NPA number, verbatim. |
| `issued_on`  | date   | yes      | Must not be in the future (a future date is a two-digit-year parse error). |
| `source_url` | url    | yes      | Link to the action document. Usually `null` for FAA. |
| `notes`      | string | yes      | Verbatim raw text when `type` is `other`, or other context. |

## Aircraft model file (`data/aircraft/{manufacturer-slug}/{model-slug}.json`)

One file per type-certificated model variant. `tcb` holds one entry per
TCDS that covers the model: the State-of-Design TCDS first, then any
validation by another regulator (e.g. FAA and EASA). The model's identity
(`manufacturer`, `model_designation`, file path) comes from the State-of-Design
TCDS. A second TCDS joins a model only through a reviewed link row in
`tools/overrides/aircraft_links.tsv`, never by matching names: the same
designation can be a different type design under another TC. When no TCDS of
the State of Design is in the dataset, the TCDS whose type certificate came
first gives the identity.

`manufacturer` and `model_designation` use one character per hyphen (a soft
hyphen or U+2010/U+2011 on the PDF is `-`) and NFKC forms (a full-width
comma is `,`); letters and accents are kept as printed. A company has one
name in the dataset, set by reviewed rows in `tools/overrides/manufacturers.tsv`:
a company that TCDS spell several ways ("Textron Aviation Inc." / "Textron
Aviation, Inc.") or that a TCDS still prints under a former name takes one
name, and lookalike names of different companies (Gulfstream Aerospace
Corporation and Gulfstream Aerospace LP (GALP)) stay apart.

A model carries three names, each from its own source:

- `tcb[].tcds.holder`: the holder exactly as that TCDS prints it (cleaned the
  same way: hyphens, NFKC). Every TCB keeps its own, so a validation that
  prints the company differently ("Gulfstream Aerospace LP" on FAA A16NM)
  isn't lost.
- `manufacturer`: the legal TC holder, one name per company (above).
- `manufacturer_group`: the name a consumer shows and groups by. Companies a
  user thinks of as one manufacturer share one, legally separate ones
  included (both Gulfstream companies are "Gulfstream"). Set by reviewed rows
  in `tools/overrides/manufacturer_groups.tsv`. Without a row it equals
  `manufacturer`. It is a display choice, never a statement about the legal
  holder, and it changes neither `manufacturer` nor the path. Every file
  with the same `manufacturer` has the same group, or the build fails.
The slugs in the path are transliterated (`Zakłady` → `zaklady`).

A model is a designation the TCDS heads a model section with ("Model
737-300"), not a series suffix ("737-300 Series") and not a customer-coded
variant (737-317) that appears only in serial tables. A configuration the TCDS
gives "additional certification basis items" for (737-800BCF) is
`applicability` on its model, not a model.

When one TCDS block applies to several models, each model's `tcb` gets its own
copy of every line that applies to it, with the same verbatim
`raw_reference`. A line scoped to some of the block's models is copied to
those models only, and the scope stays verbatim in `applicability`. There is no
shared-basis object: an entry belongs to exactly one TCB.

```json
{
  "manufacturer": "Cessna Aircraft Company",
  "manufacturer_group": "Cessna",
  "model_designation": "525",
  "common_name": "CitationJet",
  "notes": null,
  "tcb": [
    {
      "tcds": {
        "issuer": "FAA",
        "tcds_number": "A1WI",
        "holder": "Cessna Aircraft Company",
        "revision": "34",
        "revision_date": null,
        "source_url": null
      },
      "categories": ["normal"],
      "notes": null,
      "certification_basis": [
        {
          "display_order": 1,
          "entry_type": "regulation",
          "raw_reference": "525-0600 thru 525-0684 ... 14 CFR Part 23 ... as amended by Amendments 23-1 thru 23-38, 23-40; except ... 23.611, 23.777 ... as amended through ... 23-54. 14 CFR 23.1309(a) as amended through Amendments 23-62, for PED tolerance only.",
          "applicability": "525-0600 thru 525-0684",
          "applicability_notes": null,
          "references": [
            { "issuer": "FAA", "document": "23", "to": "23-40", "skip": ["23-39"] },
            { "issuer": "FAA", "document": "23", "to": "23-54", "skip": ["23-39"],
              "provisions": ["611", "777"] },
            { "issuer": "FAA", "document": "23", "to": "23-62",
              "provisions": ["1309"], "paragraph": "(a)" }
          ]
        }
      ]
    }
  ]
}
```

**Top-level, TCB and TCDS fields**

| Field                         | Type         | Nullable | Purpose |
|-------------------------------|--------------|----------|---------|
| `manufacturer`                | string       | no       | Current TC holder as on the primary TCDS, one name per company (`tools/overrides/manufacturers.tsv`). |
| `manufacturer_group`          | string       | no       | Display name to show and group by; several companies may share one (`tools/overrides/manufacturer_groups.tsv`). Equals `manufacturer` when no row groups it. One per `manufacturer`. |
| `model_designation`           | string       | no       | Formal model identifier. |
| `common_name`                 | string       | yes      | Popular name, if different. |
| `notes`                       | string       | yes      | Editor notes, displayed to users. |
| `tcb[].tcds`                  | object       | no       | `issuer`, `tcds_number`, `holder` (as this TCDS prints it), and optional `revision`, `revision_date`, `source_url`. Several model files may share a TCDS, but its metadata must then be identical, or the build fails. |
| `tcb[].categories`            | enum array   | no       | Categories as stated on this TCDS. When the parser reads none (the TCDS prints none, as FAA A2NM, or prints it where the parser doesn't look), a reviewed row in `tools/overrides/tcds_categories.tsv` gives them, with evidence; they are never inferred. Closed set: `transport`, `normal`, `utility`, `acrobatic`, `commuter`, `restricted`, `limited`, `provisional`, `primary`, `special`. Non-empty. |
| `tcb[].notes`                 | string       | yes      | TCB-level notes. |
| `tcb[].certification_basis`   | array        | no       | One entry per TCDS line that applies to this model, in TCDS order. A line shared by several models is copied to each. |

**Per-entry fields** — one entry is one line of the TCDS, verbatim

| Field                 | Type    | Nullable | Purpose |
|-----------------------|---------|----------|---------|
| `display_order`       | integer | no       | Position in this TCB's basis, 1..N in TCDS order. Unique per TCB. A shared line may have a different number on each model. |
| `entry_type`          | enum    | no       | `regulation`, `special_condition`, `elos`, `exemption`, `other`. |
| `raw_reference`       | string  | no       | Verbatim TCDS text. Never rewritten. |
| `applicability`       | string  | yes      | Verbatim serial/config scope, e.g. `"525-0600 thru 525-0684"`. |
| `applicability_notes` | string  | yes      | Other scope or caveats. |
| `references`          | array   | no       | What the line *means*, machine-readably. Empty when not (yet) interpreted. |
| `citations`           | array   | yes      | `elos`, `special_condition` and `exemption` only: the sections the line explicitly cites. See [Citations](#citations). Absent when none. |
| `citation_gaps`       | array   | yes      | Same entry types: section-like citations on the line that are not linked, and why. Absent when none. |

**Per-reference fields**

| Field        | Type          | Purpose |
|--------------|---------------|---------|
| `issuer`     | enum          | Issuer of the referenced document. |
| `document`   | string        | The document's `slug`. |
| `to`         | designator    | Include refs only: the highest revision in force. **The base revision is always included**, so "as amended by 23-1 thru 23-13" is `to: "23-13"`. |
| `skip`       | designators   | Revisions left out of a non-contiguous set ("23-1 thru 23-38, 23-40" → `to: "23-40", skip: ["23-39"]`). Each must be earlier than `to`. |
| `provisions` | numbers       | Scope the ref to these provisions, by **printed number**, as the TCDS writes them (see rule 6). Absent = the whole document. |
| `paragraph`  | string        | Verbatim qualifier, e.g. `"(a)"` or `"(a)(1)(2)(b)"`. Needs exactly one `provisions` entry. Checked against the resolved version's paragraphs (below), never rewritten. |
| `effect`     | enum          | `include` (default) or `exclude`. An exclude ref needs `provisions` and takes no `to`, `skip` or `paragraph`. |

### Resolution rules

The build resolves each entry's references **within that entry only** —
overrides never cross TCDS lines, so two lines (e.g. two serial ranges) may
legitimately hold one provision at different levels.

1. For an include ref, the revision set is every revision with ordinal ≤
   `to`, minus `skip`. For each provision in scope, the version at the
   highest revision in that set applies. A provision with no such version
   didn't exist yet and is not part of the basis through this ref. Nor is a
   provision whose applicable version is a deletion.
2. Scoped results (refs with `provisions`) replace document-wide results for
   the same provision.
3. A paragraph ref adds a row alongside the whole-provision row. If it lands
   on the same version, it is dropped.
4. An exclude ref removes provisions from the document-wide results.
5. A paragraph qualifier is checked against the paragraphs of the version it
   resolves to. It is read as TCDSs write it: each `(x)` token descends into
   the current paragraph or names a sibling of it or of an ancestor, so
   `(a)(1)(2)(b)` is (a)(1), (a)(2) and (b). `(c3)` is read as `(c)(3)`. If
   the version is flat (one line, including `TEXT MISSING`) the qualifier
   can't be checked and is counted as `paragraph_refs_unverifiable`.
6. A number in `provisions` names the provision that carried it at the ref's
   `to` revision: the one whose latest version up to `to` (skips not
   applied) prints that number. A provision in force wins over one the
   range deleted. An exclude ref has no `to`; its numbers are read at the
   highest `to` of the entry's include refs to the same document. Where
   `key == number` and numbers are never reused (FAA, CAR, EASA) this is
   simply the provision with that number.

The build fails, rather than guessing, when:
- a `to` or `skip` designator, provision, or document doesn't exist;
- a number in `provisions` names no provision, or more than one, at the
  revision it is read at, or an exclude ref has no include ref to the same
  document to read it at;
- a `skip` is not earlier than `to`;
- two document-wide refs, or two scoped refs, resolve one provision to
  different versions;
- a provision is both excluded and included by a scoped ref;
- an exclude removes nothing;
- an include ref resolves to no provisions;
- a scoped or paragraph ref resolves a provision to a version that deleted it;
- a paragraph qualifier is not a run of `(x)` tokens, or names a paragraph
  that the (structured) resolved version doesn't have.

### Citations

`citations` records which provisions an ELOS, special condition or exemption
line **explicitly names**. A citation is not part of the certification basis:
it never reaches `cert_basis_resolved` and changes no expansion. It is read from
`raw_reference` by a parser (`tools/s00_common/tcds_citations.py`). It is not a
reviewed statement that the deviation applies to that section, so consumers show
the verbatim line beside it and mark it as computed.

```json
{
  "entry_type": "elos",
  "raw_reference": "ACE-00-09 for 14 CFR § 23.1143(g) and § 23.1147(b), JAR 25.607",
  "references": [],
  "citations": [
    { "issuer": "FAA", "document": "23", "number": "1143", "paragraph": "(g)" },
    { "issuer": "FAA", "document": "23", "number": "1147", "paragraph": "(b)", "at": "23-49" }
  ],
  "citation_gaps": [
    { "cited": "JAR 25.607", "reason": "doc_not_in_dataset" }
  ]
}
```

| Field       | Purpose |
|-------------|---------|
| `issuer`, `document` | The cited document. |
| `number`    | Printed number, read at `at`, or at the latest revision when there is no `at`. |
| `paragraph` | Run of `(x)` tokens, the grammar of a reference's `paragraph`: `(d), (e)` on the line is `(d)(e)`. |
| `at`        | The amendment the line states for this section, if the section is in force at it. |

Gap fields: `cited`, an exact substring of `raw_reference`, and `reason`:

| Reason | Meaning |
|---|---|
| `doc_not_in_dataset` | The line cites a document we don't hold: JAR, AMC, GM, or an absent part. |
| `section_not_in_document` | The document is held but never printed that number. |
| `document_undetermined` | Nothing decides which document a bare number belongs to. |
| `range_not_expanded` | A range (`23.1381 to 23.1401`). Its members are not listed. |
| `withheld_basis_list` | The line reads like a basis list typed as a deviation, so nothing on it is linked. |

**Which document** (tools, first match wins): the line names it (`CS 25.x`,
`FAR`/`14 CFR`, or a document named earlier on the line for that part); `JAR`,
`AMC`, `GM` are gaps; `CAR 3.x` is the one CAR 3 document in the aircraft's
basis; a bare number on an FAA TCDS is that FAA part; on an EASA TCDS it is the
one basis document with that part number, or the one family (FAR, CS or JAR)
the aircraft's regulation lines name. Otherwise it is a gap.

**The guard** (tools): a line is withheld when it has three or more section
ranges, or six or more distinct sections at three or more amendment levels. A
row in `tools/overrides/tcds_citations.tsv` can force `withhold` or `allow`.

**Which version a citation links to** (build), recorded as `version_basis`:

1. `stated`: the version in force at `at`.
2. `basis`: the aircraft's resolved basis holds the section at one version.
3. `basis_several`: it holds several (different serial ranges); no version is
   chosen, because the line doesn't say which.
4. `latest`: neither applies. The latest version that isn't a deletion,
   preferring one with real text. This says nothing about what the aircraft was
   certified to.

The build fails on an unknown document, revision or number, a section not in
force at `at`, a malformed `paragraph`, or a `cited` string that isn't in the
line. A well-formed `paragraph` the linked version lacks is counted in the
report, not fatal: a TCDS line can be wrong, and `latest` can be the wrong text
to check it against.

## Deviation file (`data/deviations/easa/120960.json`)

One file per special condition, ELOS/ESF, exemption or deviation, as its
regulator lists it. A record is a **link**: it holds what the listing says and
the regulator's page, never the text. Most of these documents are letters or
scans that can't meet the provision rule that every version has text, so they
are not provisions (reviews/2026-11-13 deviations proposal, D1). Emitted:
EASA's consulted publications, and FAA's ELOS memos, special conditions (final
and proposed) and certification-relevant exemptions from DRS.

```json
{
  "issuer": "EASA",
  "key": "120960",
  "kind": "special_condition",
  "number": "SC-E25.904-01",
  "title": "Special Condition SC-E25.904-01 – Use of Automatic Power Reserve for Go-Around Performance Credit - Issue 01",
  "stage": "final",
  "published_on": "2021-01-19",
  "source_url": "https://www.easa.europa.eu/en/document-library/product-certification-consultations/special-condition-sc-e25904-01-use-automatic",
  "citations": [{ "issuer": "EASA", "document": "cs-25", "number": "904" }]
}
```

| Field | Nullable | Purpose |
|---|---|---|
| `issuer` | no | Must match the directory. |
| `key` | no | Identity within the issuer; the file name. EASA: the publication page's node id. FAA: the DRS document id (`40667CC5D05D267C8625761E005A49E6.0001`), because DRS numbers repeat. Never shown as a citation. |
| `kind` | no | `special_condition`, `elos` (EASA's Equivalent Safety Finding), `exemption`, `deviation`, `means_of_compliance` (EASA's interpretative material or MoC to an SC or ESF). |
| `number` | yes | The identifier as printed (`SC-E25.904-01`, older `ESF F-69`), or null when the listing prints none. EASA: from the title, the listing's Reference line or a file label; a list in the Reference stays whole, and a newer page may have only a document number (`M-TS-0000358`). Not unique: a project label like `SC D-01` recurs. |
| `title` | yes | As listed, verbatim. Null when the listing prints none: DRS lists no subject for exemptions. |
| `stage` | no | `final` when a final version is published, else `proposed`. EASA publishes the proposal, comment response and final on one page, so one record covers all three; a comment-response document counts as final (it adopts the text), and `proposed` can also mean the page doesn't say (tools/s00_docs/EASA_DEVIATIONS.md). |
| `published_on` | yes | Date the listing gives. Not in the future. |
| `source_url` | no | The regulator's page. The app links here; local copies are never served (D5). |
| `applicant` | — | Optional. Applicant or petitioner as listed, verbatim. |
| `make`, `model` | — | Optional. As listed, verbatim; several models are joined with ` \| `. |
| `regulation_ref` | — | Optional. The listing's regulation field, verbatim, like `raw_reference`: FAA DRS's CFR Section Reference (ELOS, SC) or Regulation/Title 14 CFR Reference (exemptions), values joined with ` \| ` (`Sec. 21.21 \| Sec. 25.1191`). |
| `disposition` | — | Optional. Exemptions: `Granted`, `Denied`, … as listed. A denied exemption is still a record. |
| `final` | — | Optional, only on a `proposed` record: the `key` of the final record it became, same issuer and kind. FAA: computed from the shared docket number and agreeing titles. |
| `citations` | — | Optional. Sections the title, identifier or `regulation_ref` names, same fields as a [TCDS citation](#citations) without `at`: the number is read at the latest revision. The identifier counts as naming a section (`SC-E25.904-01` → CS 25.904). Never a statement that the deviation applies to that section. |
| `citation_gaps` | — | Optional. As on a TCDS line; `cited` must be a slice of the title, the number or `regulation_ref`. |

A deviation's citations never reach the certification basis. The build fails
on an unknown document or number, a malformed `paragraph`, a gap that isn't
printed, or a `final` that isn't a final record of the same kind. Linking a TCDS line to the record it names is not built yet
(ISSUES ROADMAP-2).
