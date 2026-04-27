# FARfetched-data

Canonical source of truth for [FARFETCHed](https://github.com/DEK-DEBIAN/FARFETCHed):
a dataset of FAA type-certificated aircraft and the regulations that form
their certification basis.

This repository contains JSON files only. A build script compiles them into a
single `cert_basis.sqlite` database which the Flask app consumes. The SQLite
file is not checked in — it is produced by `build.py` and (later) published
as a GitHub release artifact.

See [plan.md](plan.md) for full architecture and roadmap.

## Layout

```
FARfetched-data/
├── plan.md                     Project plan (authoritative)
├── README.md                   This file
├── schemas/                    JSON Schema files (validation)
│   ├── regulation_part.schema.json
│   ├── regulation.schema.json
│   └── aircraft_model.schema.json
├── data/
│   ├── regulations/{authority}/{part}/_part.json
│   ├── regulations/{authority}/{part}/{section}.json
│   └── aircraft/{manufacturer-slug}/{model-slug}.json
├── build.py                    JSON → SQLite compiler
└── tests/
```

Regulation file paths are flat by design: `authority` + `part` + `section`
are the only parts of a citation that are truly stable. Subpart and title
number are stored inside the file, so a section can be re-subparted without
a rename.

## JSON formats

### Part file (`data/regulations/faa/25/_part.json`)

One file per CFR part. Holds the master amendment list — the attributes that
belong to the amendment-as-a-whole (effective date, ordinal), not to any
individual section.

```json
{
  "authority": "FAA",
  "title_number": 14,
  "part": "25",
  "description": "Airworthiness Standards: Transport Category Airplanes",
  "amendments": [
    {
      "designator": "25-23",
      "ordinal": 23,
      "effective_date": "1970-05-08"
    }
  ]
}
```

**Top-level fields**

| Field          | Type    | Nullable | Purpose |
|----------------|---------|----------|---------|
| `authority`    | string  | no       | Issuing authority. Currently only `"FAA"`. |
| `title_number` | integer | no       | CFR title. For FAA regulations always `14`. |
| `part`         | string  | no       | CFR part, e.g. `"25"` or `"23"`. String — some parts are non-numeric. |
| `description`  | string  | yes      | Human-readable part title, e.g. "Transport Category Airworthiness Standards". |
| `amendments`   | array   | no       | One entry per amendment that has ever touched this part. Must be non-empty. |

**Per-amendment fields**

| Field            | Type    | Purpose |
|------------------|---------|---------|
| `designator`     | string  | Human-readable amendment ID, e.g. `"25-23"`. Unique per part. |
| `ordinal`        | integer | Numeric ordering key. `0` marks the original adoption. |
| `effective_date` | date    | ISO `YYYY-MM-DD`. The date the amendment became effective. Same for all sections changed by this amendment. |

Note: `federal_register_cite` is intentionally absent here. Different sections
changed by the same amendment appear on different FR pages, so that field
belongs on the per-section amendment record.

### Regulation section file (`data/regulations/faa/25/1309.json`)

One file per CFR section. Contains only the per-section payload for each
amendment. Ordinal and effective date are looked up from the part file.

```json
{
  "authority": "FAA",
  "part": "25",
  "section": "1309",
  "current_subpart": "F",
  "canonical_title": "Equipment, systems, and installations",
  "subject_group": "Equipment",
  "amendments": [
    {
      "designator": "25-23",
      "subpart_at_time": "F",
      "title_at_amendment": "Equipment, systems, and installations",
      "text": "...full regulation text at this amendment...",
      "federal_register_cite": "35 FR 5665",
      "source_url": "https://drs.faa.gov/browse/excelExternalWindow/{GUID}.0001"
    }
  ]
}
```

**Top-level fields**

| Field             | Type   | Nullable | Purpose |
|-------------------|--------|----------|---------|
| `authority`       | string | no       | Issuing authority. Must match the part file in the same directory. |
| `part`            | string | no       | CFR part. Must match the directory name and part file. |
| `section`         | string | no       | Section number, e.g. `"1309"`. String to allow suffixes like `"1309a"`. |
| `current_subpart` | string | yes      | Present-day subpart label. Display only — subparts get reorganised. |
| `canonical_title` | string | no       | Present-day section heading. |
| `subject_group`   | string | yes      | FAA intra-subpart grouping label from DRS. Optional. |
| `amendments`      | array  | no       | One entry per amendment that changed this section. Must be non-empty. |

**Per-amendment fields**

| Field                   | Type   | Nullable | Purpose |
|-------------------------|--------|----------|---------|
| `designator`            | string | no       | Amendment designator. Must match an entry in the part file. |
| `subpart_at_time`       | string | yes      | Subpart this section sat under at the time of this amendment. Captures historical subpart reorganisations. |
| `title_at_amendment`    | string | no       | Section heading as it read at this amendment. |
| `text`                  | string | no       | Full regulation text at this amendment. |
| `federal_register_cite` | string | yes      | FR cite for this section's page in the FR issue, e.g. `"35 FR 5665"`. Per-section because different sections in the same amendment appear on different pages. Use the literal `"Initial Adoption"` for `-0` designators (the original adoption predates the modern FR cite scheme used elsewhere). Use `""` (or omit the key) when the cite is genuinely unknown — these can be backfilled later without invalidating the row. |
| `source_url`            | url    | yes      | Where the text was transcribed from. Prefer the DRS canonical URL `https://drs.faa.gov/browse/excelExternalWindow/{GUID}.0001`. |
| `actions`               | array  | yes      | Ordered list of rulemaking actions that produced this amendment (NPRM, Final Rule, EASA NPA, etc.). See action object fields below. Omit the key entirely when no actions are known. |
| `provenance`            | object | yes      | Where the amendment came from. Object with required `source` (`"scraped"` \| `"ocr"` \| `"manual"`) and optional `notes`. Absent ≡ `"scraped"`. Set `"manual"` on any amendment you have hand-corrected — `tools/promote.py` and the `tests/test_manual_provenance.py` tripwire then refuse to let it be silently overwritten. See [tools/README_TOOLS.md §Manual edit protection](tools/README_TOOLS.md#manual-edit-protection). |

**Action object fields** (each element of `actions`)

| Field        | Type   | Nullable | Purpose |
|--------------|--------|----------|---------|
| `type`       | string | no       | Action kind. Enum: `nprm`, `final_rule`, `direct_final_rule`, `interim_final_rule`, `easa_npa`, `easa_opinion`, `easa_decision`, `jar_npa`, `jar_change`, `other`. |
| `reference`  | string | yes      | Notice number (NPRM), docket number (Final Rule), NPA number (EASA), etc. Authority-specific; stored verbatim. |
| `issued_on`  | date   | yes      | ISO `YYYY-MM-DD` date the action was issued. |
| `source_url` | url    | yes      | Direct link to the action document (EASA or other). Usually `null` for FAA (DRS does not expose stable per-action URLs). |
| `notes`      | string | yes      | Verbatim raw text when `type` is `other`, or any additional context. |

### Aircraft model file (`data/aircraft/{manufacturer-slug}/{model-slug}.json`)

One file per type-certificated model variant. The `tcb` array holds one entry
per regulator that has issued a type certificate for this model — each with
its own TCDS reference and certification basis.

```json
{
  "manufacturer": "The Boeing Company",
  "model_designation": "737-800",
  "common_name": "737-800",
  "categories": ["transport"],
  "notes": null,
  "tcb": [
    {
      "tcds": {
        "authority": "FAA",
        "tcds_number": "A16WE",
        "revision": "57",
        "revision_date": "2024-03-15",
        "source_url": "https://..."
      },
      "notes": null,
      "certification_basis": [
        {
          "display_order": 1,
          "entry_type": "regulation",
          "raw_reference": "14 CFR Part 25 as amended by Amendments 25-1 through 25-62",
          "applicability_notes": null,
          "resolved_references": [
            {
              "reference_kind": "range",
              "authority": "FAA",
              "title_number": 14,
              "part": "25",
              "from_amendment_ordinal": 1,
              "to_amendment_ordinal": 62
            }
          ]
        }
      ]
    }
  ]
}
```

**Top-level fields**

| Field               | Type          | Nullable | Purpose |
|---------------------|---------------|----------|---------|
| `manufacturer`      | string        | no       | Current TC holder name as it appears on the TCDS. |
| `model_designation` | string        | no       | Formal model identifier, e.g. `"737-800"`. |
| `common_name`       | string        | yes      | Popular name if it differs from `model_designation`. |
| `categories`        | string array  | no       | Airworthiness categories, e.g. `["transport"]`. Array because some models are certified in multiple categories simultaneously. Must be non-empty. |
| `notes`             | string        | yes      | Free-form editor notes. Displayed to users. |
| `tcb`               | array         | no       | One entry per certifying authority (FAA, EASA, …). Must be non-empty. |

**Per-TCB fields** (`tcb[]`)

| Field                 | Type   | Nullable | Purpose |
|-----------------------|--------|----------|---------|
| `tcds`                | object | no       | TCDS reference (see below). |
| `notes`               | string | yes      | TCB-level notes (e.g. scope of applicability for this authority). |
| `certification_basis` | array  | no       | Ordered certification basis entries for this authority's TCDS. |

**TCDS fields** (`tcb[].tcds`)

| Field           | Type   | Nullable | Purpose |
|-----------------|--------|----------|---------|
| `authority`     | string | no       | Issuing authority. |
| `tcds_number`   | string | no       | TCDS identifier, e.g. `"A16WE"`. |
| `revision`      | string | yes      | Revision identifier of the TCDS this data was taken from. |
| `revision_date` | date   | yes      | ISO date of that revision. |
| `source_url`    | url    | yes      | Link to the source TCDS document. |

**Per-entry fields** (`tcb[].certification_basis[]`)

| Field                  | Type    | Nullable | Purpose |
|------------------------|---------|----------|---------|
| `display_order`        | integer | no       | Render order matching the TCDS. |
| `entry_type`           | enum    | no       | One of `regulation`, `special_condition`, `elos`, `exemption`, `other`. |
| `raw_reference`        | string  | no       | Verbatim TCDS text. Never rewritten. |
| `applicability_notes`  | string  | yes      | Scope or caveats from the TCDS. |
| `resolved_references`  | array   | no       | Machine-readable interpretation. Empty for unresolvable types. |

**Per resolved reference** — two shapes:

*Range* — compact, expanded at build time:
```json
{ "reference_kind": "range",
  "authority": "FAA", "title_number": 14, "part": "25",
  "from_amendment_ordinal": 1, "to_amendment_ordinal": 62 }
```

*Single* — explicit, one row:
```json
{ "reference_kind": "single",
  "authority": "FAA", "title_number": 14, "part": "25", "section": "1309",
  "amendment_designator": "25-58" }
```

## SQLite schema

`build.py` compiles the JSON into twelve tables plus one view.

### Lookup tables

`naa_authorities` — FAA, EASA, etc. (`code`, `name`, `country`).

`manufacturers` — TC holders by name.

`categories` — Airworthiness category codes (`transport`, `normal`, etc.).

### Regulation tables

`regulation_parts` — one row per CFR part. Holds `(authority_id, title_number, part, description)`.

`regulations` — one row per CFR section. `current_subpart` is present-day display only.

`amendments` — one row per amendment-as-a-whole. `(part_id, designator, ordinal, effective_date)`. `effective_date` is stored here because it is the same for all sections changed by one amendment.

`section_amendments` — one row per (section × amendment). The per-section payload: `text`, `title_at_amendment`, `federal_register_cite`, `subpart_at_time`, `source_url`.

`amendment_actions` — child rows of `section_amendments`. Each row is one rulemaking action (NPRM, Final Rule, EASA NPA, etc.) associated with a section amendment. Fields: `section_amendment_id`, `seq` (ordering), `type`, `reference`, `issued_on`, `source_url`, `notes`.

### Aircraft / TCB tables

`aircraft_models` — one row per model variant.

`model_categories` — M:N join between models and categories (a model can have multiple categories).

`tcds` — one row per type certificate document `(authority_id, tcds_number, revision, revision_date, source_url)`.

`tcb` — the certification basis container. One row per `(model, tcds)` pair. This is the entity that owns `cert_basis_entries`.

`cert_basis_entries` — one row per resolved cert-basis item. FK to `tcb_id` (not aircraft directly). `section_amendment_id` is nullable for unresolvable entry types.

### `latest_amendments` view

Convenience view: for each regulation section, the `section_amendments` row
joined with the highest-ordinal amendment. Used by part-vs-part comparison
without requiring a MAX-subquery each time.

## Build pipeline

```bash
python build.py                     # reads data/, writes cert_basis.sqlite
python build.py --data-dir X --out Y.sqlite
```

`build.py`:
1. Validates every JSON file against its schema. Fails on any mismatch.
2. Inserts lookup rows (`naa_authorities`, `manufacturers`, `categories`).
3. Inserts `regulation_parts` and `amendments` from `_part.json` files.
4. Inserts `regulations` and `section_amendments` from section files. Fails if
   a section references an amendment designator not present in its part file.
5. Inserts `aircraft_models`, `model_categories`, `tcds`, and `tcb`.
6. For each cert-basis entry, expands `resolved_references` and inserts
   one row per resolved `section_amendment`. Fails if a range references
   an amendment not present in the data.
7. Writes `cert_basis_report.json` alongside the SQLite file: row counts,
   unresolvable references (must always be zero on a successful build).

Output is atomic: build writes `cert_basis.sqlite.new` then `os.replace()`s
it into place.

## Consuming the SQLite artifact

`cert_basis.sqlite` ships in WAL mode. Consumers should treat the file as
read-only and configure each connection like this:

```python
import sqlite3

conn = sqlite3.connect("cert_basis.sqlite")
conn.execute("PRAGMA query_only = ON")
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("PRAGMA synchronous = NORMAL")
conn.execute("PRAGMA busy_timeout = 5000")
```

## Adding data

**New aircraft:** create
`data/aircraft/{manufacturer-slug}/{model-slug}.json` and run `build.py`.
If build fails with missing-amendment errors, add the amendments to the
relevant regulation and part files first.

**New regulation section:** create
`data/regulations/{authority}/{part}/{section}.json` with at least one
amendment. Ensure that part `_part.json` declares all amendment designators
referenced by the section.

**New amendment to existing part:** append to `amendments` in `_part.json`,
then add the corresponding amendment block to each section file that was
changed by that amendment. Ordinals must be unique within the part.
