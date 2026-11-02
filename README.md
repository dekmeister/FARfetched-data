# FARfetched-data

Canonical source of truth for [FARFETCHed](https://github.com/DEK-DEBIAN/FARFETCHed):
a dataset of type-certificated aircraft and the regulations (and, later,
other documents) that form their certification basis.

This repository contains JSON files only. A build script compiles them into a
single `cert_basis.sqlite` database which the Flask app consumes. The SQLite
file is not checked in — it is produced by `build.py` and (later) published
as a GitHub release artifact.

See [plan.md](plan.md) for architecture and roadmap. The 2026-10-31 schema
review that shaped the current format is in
[reviews/2026-10-31-db-schema/](reviews/2026-10-31-db-schema/).

## Model

Everything citable is a **document** with its own revision history:

| Concept   | 14 CFR           | CAR 3          | EASA CS        |
|-----------|------------------|----------------|----------------|
| Issuer    | FAA              | CAA (now FAA)  | EASA           |
| Document  | 14 CFR 23        | CAR 3          | CS-23          |
| Revision  | Amdt 23-62       | CAR3-0         | CS23-5         |
| Provision | §23.1309         | §3.735         | CS 23.2000     |

The same four layers will hold advisory circulars, special conditions,
ELOS findings, exemptions and handbooks (`doc_kind`), so a cert-basis
reference always points at a provision version, whatever the document kind.

## Layout

```
FARfetched-data/
├── plan.md                     Project plan
├── README.md                   This file — the field-level contract
├── schemas/                    JSON Schema files (Draft 2020-12)
│   ├── common.schema.json      Shared closed sets: issuer, provenance, dates, URLs
│   ├── document.schema.json
│   ├── provision.schema.json
│   └── aircraft_model.schema.json
├── data/
│   ├── documents/{issuer}/{document}/_document.json
│   ├── documents/{issuer}/{document}/{provision}.json
│   └── aircraft/{manufacturer-slug}/{model-slug}.json
├── build.py                    JSON → SQLite compiler
└── tests/
```

Document file paths are flat by design: issuer + document + provision number
are the only parts of a citation that are truly stable. Grouping (subpart)
and the CFR title live inside the files, so a provision can be re-subparted
without a rename. `{issuer}` is the issuer code in lower case and
`{document}` is the document's `slug`. The build fails if a file's path
disagrees with the identity fields inside it.

## JSON formats

All schemas use `additionalProperties: false`. Dates are ISO `YYYY-MM-DD`.
URLs must be `http(s)://`. `provenance` is always
`{"source": "scraped" | "ocr", "notes"?: string}` and absent means
`"scraped"`. There is no `"manual"`: every file in `data/` is built from
source by [tools/](tools/), and a correction is an override row there.

### Document file (`data/documents/faa/23/_document.json`)

One file per document. Holds the master revision list — the attributes that
belong to the revision as a whole.

```json
{
  "issuer": "FAA",
  "doc_kind": "regulation",
  "code": "14 CFR 23",
  "slug": "23",
  "title": "Airworthiness Standards: Normal Category Airplanes",
  "revisions": [
    { "designator": "23-62", "ordinal": 62, "effective_date": "2012-01-31" }
  ]
}
```

**Top-level fields**

| Field       | Type   | Nullable | Purpose |
|-------------|--------|----------|---------|
| `issuer`    | enum   | no       | `FAA`, `CAA`, `CAB`, `EASA`. CAA and CAB are historical US issuers whose successor is the FAA (recorded in the `issuers` table, not the code). |
| `doc_kind`  | enum   | no       | `regulation`, `certification_spec`, `amc_gm`, `advisory_circular`, `handbook`, `special_condition`, `elos`, `exemption`, `standard`. |
| `code`      | string | no       | Human citation: `"14 CFR 23"`, `"CAR 3"`, `"CS-23"`. Replaces the old `title_number` + `part`. |
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

### Provision file (`data/documents/faa/23/1309.json`)

One file per provision. Ordinal and effective date come from the document file.

```json
{
  "issuer": "FAA",
  "document": "23",
  "number": "1309",
  "current_grouping": "Equipment",
  "canonical_title": "Equipment, systems, and installations.",
  "subject_group": "General",
  "versions": [
    {
      "designator": "23-62",
      "grouping_at_time": "Equipment",
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
| `number`           | string | no       | Provision number, e.g. `"1309"`, `"1309a"`, `"A23"` (appendix). Must match the file name. |
| `current_grouping` | string | yes      | Present-day subpart (or equivalent). Display only. |
| `canonical_title`  | string | no       | Present-day heading. |
| `subject_group`    | string | yes      | Intra-subpart grouping label (FAA DRS). |
| `versions`         | array  | no       | One entry per revision that changed this provision. Non-empty. |

**Per-version fields**

| Field                | Type   | Nullable | Purpose |
|----------------------|--------|----------|---------|
| `designator`         | string | no       | Must be declared in the document file. One version per designator. |
| `grouping_at_time`   | string | yes      | Subpart the provision sat under at this revision. |
| `title_at_revision`  | string | no       | Heading as it read at this revision. |
| `text`               | string | one of   | Full text at this revision, in the label-line format (see [Text format](#text-format)). No tabs or carriage returns. The literal `"TEXT MISSING"` is the reserved marker for a known gap: the pair must exist (per a manifest) but the source is unreadable. The DB flags these rows with `text_missing = 1`. |
| `same_as_designator` | string | one of   | Instead of `text`: the text is unchanged from this earlier version of the same provision. The build copies the text and records the link. Must not point at a deleted version. |
| `deleted`            | `true` | one of   | Instead of `text`: this revision deleted (removed, repealed) the provision, e.g. every old-numbered CS-23 paragraph at CS23-5. Only valid while the provision is in force (not as its first version, not twice in a row). A later version may re-create it. Stored with `text` NULL and `deleted = 1`. |
| `publication_cite`   | string | yes      | Where the revision was published, e.g. `"35 FR 5665"`. Omit (or `""`) when unknown — including for original issues. The old `"Initial Adoption"` sentinel is rejected. |
| `source_url`         | url    | yes      | Where the text was transcribed from. Prefer DRS `https://drs.faa.gov/browse/excelExternalWindow/{GUID}.0001`. |
| `actions`            | array  | yes      | Rulemaking actions behind this version, as the source records them for this provision (see below). Omit when none are known. |
| `provenance`         | object | yes      | How the text was obtained: `scraped` (default) or `ocr`. `notes` records any override applied to it. Carried into the DB so the app can mark OCR text. |

Actions stay on the version rather than the revision because the source (DRS)
records them per section, and the per-section lists for one amendment don't
always agree.

#### Text format

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

**Layout only.** Structuring may only add line breaks and indentation.
Flattening a text (strip every line, drop blank ones, join with single spaces)
gives its words; the tools assert that layout never changes them. The tools
write two spaces per level, but the build accepts any consistent indentation.
`tools/s00_common/structure.py` produces the format from flat text; see
[tools/README.md](tools/README.md).

**Action fields**

| Field        | Type   | Nullable | Purpose |
|--------------|--------|----------|---------|
| `type`       | enum   | no       | `nprm`, `final_rule`, `direct_final_rule`, `interim_final_rule`, `easa_npa`, `easa_opinion`, `easa_decision`, `jar_npa`, `jar_change`, `other`. |
| `reference`  | string | yes      | Notice, docket or NPA number, verbatim. |
| `issued_on`  | date   | yes      | Must not be in the future (a future date is a two-digit-year parse error). |
| `source_url` | url    | yes      | Link to the action document. Usually `null` for FAA. |
| `notes`      | string | yes      | Verbatim raw text when `type` is `other`, or other context. |

### Aircraft model file (`data/aircraft/{manufacturer-slug}/{model-slug}.json`)

One file per type-certificated model variant. `tcb` holds one entry per
regulator that has issued a type certificate for the model.

```json
{
  "manufacturer": "Cessna Aircraft Company",
  "model_designation": "525",
  "common_name": "CitationJet",
  "categories": ["normal"],
  "notes": null,
  "tcb": [
    {
      "tcds": {
        "issuer": "FAA",
        "tcds_number": "A1WI",
        "revision": "34",
        "revision_date": null,
        "source_url": null
      },
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
| `manufacturer`                | string       | no       | Current TC holder as on the TCDS. |
| `model_designation`           | string       | no       | Formal model identifier. |
| `common_name`                 | string       | yes      | Popular name, if different. |
| `categories`                  | enum array   | no       | Closed set: `transport`, `normal`, `utility`, `acrobatic`, `commuter`, `restricted`, `limited`, `provisional`, `primary`, `special`. Non-empty. |
| `notes`                       | string       | yes      | Editor notes, displayed to users. |
| `tcb[].tcds`                  | object       | no       | `issuer`, `tcds_number`, and optional `revision`, `revision_date`, `source_url`. Several model files may share a TCDS, but its metadata must then be identical, or the build fails. |
| `tcb[].notes`                 | string       | yes      | TCB-level notes. |
| `tcb[].certification_basis`   | array        | no       | One entry per TCDS line, in TCDS order. |

**Per-entry fields** — one entry is one line of the TCDS, verbatim

| Field                 | Type    | Nullable | Purpose |
|-----------------------|---------|----------|---------|
| `display_order`       | integer | no       | Position on the TCDS. Unique per TCB. |
| `entry_type`          | enum    | no       | `regulation`, `special_condition`, `elos`, `exemption`, `other`. |
| `raw_reference`       | string  | no       | Verbatim TCDS text. Never rewritten. |
| `applicability`       | string  | yes      | Verbatim serial/config scope, e.g. `"525-0600 thru 525-0684"`. |
| `applicability_notes` | string  | yes      | Other scope or caveats. |
| `references`          | array   | no       | What the line *means*, machine-readably. Empty when not (yet) interpreted. |

**Per-reference fields**

| Field        | Type          | Purpose |
|--------------|---------------|---------|
| `issuer`     | enum          | Issuer of the referenced document. |
| `document`   | string        | The document's `slug`. |
| `to`         | designator    | Include refs only: the highest revision in force. **The base revision is always included**, so "as amended by 23-1 thru 23-13" is `to: "23-13"`. |
| `skip`       | designators   | Revisions left out of a non-contiguous set ("23-1 thru 23-38, 23-40" → `to: "23-40", skip: ["23-39"]`). Each must be earlier than `to`. |
| `provisions` | numbers       | Scope the ref to these provisions. Absent = the whole document. |
| `paragraph`  | string        | Verbatim qualifier, e.g. `"(a)"` or `"(a)(1)(2)(b)"`. Needs exactly one `provisions` entry. Checked against the resolved version's paragraphs (below), never rewritten. |
| `effect`     | enum          | `include` (default) or `exclude`. An exclude ref needs `provisions` and takes no `to`, `skip` or `paragraph`. |

#### Resolution rules

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

The build fails, rather than guessing, when:
- a `to` or `skip` designator, provision, or document doesn't exist;
- a `skip` is not earlier than `to`;
- two document-wide refs, or two scoped refs, resolve one provision to
  different versions;
- a provision is both excluded and included by a scoped ref;
- an exclude removes nothing;
- an include ref resolves to no provisions;
- a scoped or paragraph ref resolves a provision to a version that deleted it;
- a paragraph qualifier is not a run of `(x)` tokens, or names a paragraph
  that the (structured) resolved version doesn't have.

## SQLite schema

`build.py` compiles the JSON into 19 tables plus one view. Every table is
`STRICT`; every date column is `TEXT` with `CHECK (date(x) IS x)`; every
UNIQUE key is over NOT NULL columns. The authoritative DDL is `SCHEMA_SQL`
in [build.py](build.py).

### Contract metadata

`PRAGMA user_version` is the schema version (currently **4**; v2 added
`provision_versions.deleted`, v3 added `provision_paragraphs` and the
label-line text format, v4 dropped `manual` from the `provenance` CHECK). It is bumped
on every contract change, and consumers should refuse a DB whose version
they don't know. `build_info` is a single row: `schema_version`, `git_sha` of
the data repo at build time (NULL if unavailable), `built_at` (UTC).

### Documents

`issuers` — closed set seeded by the build: `code`, `name`, `kind`
(`naa` / `military` / `standards_body`), `country`, `successor_id`.

`documents` — `(issuer_id, doc_kind, code, slug, title)`.

`document_revisions` — `(document_id, designator, ordinal, effective_date,
provenance, provenance_notes)`.

`provisions` — `(document_id, number, sort_key, canonical_title,
current_grouping, subject_group)`. `sort_key` is computed (digit runs
zero-padded) so §23.175 sorts before §23.1309: `ORDER BY sort_key`.

`provision_versions` — one row per (provision × revision): `text`,
`title_at_revision`, `grouping_at_time`, `publication_cite`, `source_url`,
`provenance`, `provenance_notes`, `same_as_version_id`, `deleted` (1 = the
revision deleted the provision; `text` is NULL exactly when `deleted = 1`),
and the generated `text_missing` flag. Composite foreign keys through `document_id` make it
impossible to pair a provision with another document's revision, or alias a
version of another provision.

`provision_paragraphs` — a version's text split into blocks by the
[text format](#text-format): `provision_version_id`, `seq` (document order),
`depth` (0 = top level, otherwise the number of labels in `path`), `label`
(verbatim, e.g. `(ii)` or `[(4)`; NULL when unlabelled), `path` (e.g.
`(a)(1)(ii)`; for an unlabelled block, its enclosing item's path; NULL at top
level) and `text` (`''` for a label-only block such as `(c)` in `(c)(1)`).
Every version that has text has rows, aliases and `TEXT MISSING` included; a
flat text is one unlabelled row, so the app has a single rendering path.
`provision_versions.text` keeps the label-line string unchanged. Index on
`(provision_version_id, path)`. Labels must be shown as stored, never
generated: real regulations skip and repeat them.

`version_actions` — rulemaking actions per provision version, ordered by
`seq`.

### Aircraft / TCB tables

`manufacturers`, `categories` (closed set), `aircraft_models`,
`model_categories` (M:N), `tcds`, and `tcb` — one row per (model, TCDS)
pair, owning the cert basis.

### Certification basis (three layers)

| Table | Grain | Source |
|---|---|---|
| `cert_basis_entries` | one TCDS line | authored, verbatim |
| `cert_basis_refs` (+ `cert_basis_ref_provisions`, `cert_basis_ref_skips`) | one interpretation clause | authored |
| `cert_basis_resolved` | one (entry, provision version) | computed by the build |

`cert_basis_resolved.via_ref_id` names the ref that produced each row and
`paragraph` carries the qualifier (NULL = whole provision). Index on
`provision_version_id` serves "which aircraft use §23.1309 @ 23-62".

### `latest_versions` view

For each provision, the `provision_versions` row at its highest-ordinal
revision, joined with `designator`, `ordinal` and `effective_date`. For a
deleted provision that row has `deleted = 1`; filter on it to list only
provisions in force.

## Build pipeline

```bash
uv run python build.py                     # reads data/, writes cert_basis.sqlite
uv run python build.py --data-dir X --out Y.sqlite
uv run python build.py --check             # schema + text layout validation only
```

`build.py`:
1. Validates every JSON file against its schema. Fails on any mismatch.
2. Checks every document/provision path against the identity fields inside.
3. Seeds the closed lookup sets (`issuers`, `categories`).
4. Inserts documents and revisions, then provisions, versions, actions and
   paragraphs. Fails if a version names an undeclared revision or a duplicate
   one, or if an alias doesn't point at an earlier, non-deleted version of the
   same provision, or a deletion doesn't follow a version in force, or a text
   breaks the [text format](#text-format) (all such texts are listed at once).
5. Inserts aircraft, TCDS (once each, metadata must agree), TCBs and
   entries; inserts each entry's refs, resolves them by the rules above, and
   checks paragraph qualifiers.
6. Fails on any date after the build day, and on any foreign-key violation.
7. Writes `cert_basis_report.json` alongside the SQLite file: row counts for
   every table, `text_missing` and `deleted` counts, provenance counts,
   `structured_versions` / `flat_versions` / `label_gaps`,
   `paragraph_refs_verified` / `paragraph_refs_unverifiable`, and
   `unresolved_references` (always empty on a successful build).

Every constraint violation fails the build with the offending file named.
Output is atomic: the build writes `cert_basis.sqlite.new`, then
`os.replace()`s it into place, removing any stale `-wal`/`-shm` sidecars.

## Consuming the SQLite artifact

`cert_basis.sqlite` ships as a single file in `journal_mode = DELETE` — no
`-wal`/`-shm` sidecars, so it works from read-only storage. Open it
read-only and check the contract version:

```python
import sqlite3

SUPPORTED_SCHEMA = 3

conn = sqlite3.connect("file:cert_basis.sqlite?mode=ro", uri=True)
conn.execute("PRAGMA foreign_keys = ON")
if conn.execute("PRAGMA user_version").fetchone()[0] != SUPPORTED_SCHEMA:
    raise RuntimeError("cert_basis.sqlite schema version not supported")
```

## Adding data

**New aircraft:** parse the TCDS PDF with `tools.s02_emit.faa.tcds.parse`. It stages
`{manufacturer-slug}/{model-slug}.json` under `tools/out/staged/aircraft/`.
Review the file, promote it into `data/aircraft/` with
`tools.s03_promote.promote --aircraft`, then run `build.py` (see
[tools/README.md](tools/README.md)). If the build reports unknown revisions
or provisions, add them to the relevant document first. Aircraft files
don't yet have a `provenance` field, so a hand-corrected aircraft file isn't
protected from re-promotion.

**New provision:** create `data/documents/{issuer}/{document}/{number}.json`
with at least one version. Every version's designator must be declared in
that document's `_document.json`.

**New revision of an existing document:** append it to `revisions` in
`_document.json`, then add a version to each provision file it changed.
Ordinals must be unique within the document.

Don't hand-edit `data/`: it is the output of [tools/](tools/), rebuilt from
local source copies plus `tools/overrides/`. A hand edit would be overwritten
by the next promotion. Fix the extractor, or add an override row.
