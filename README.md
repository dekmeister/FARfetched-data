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
│   ├── regulation.schema.json
│   └── aircraft.schema.json
├── data/
│   ├── regulations/{authority}/{part}/{section}.json
│   └── aircraft/{tcds}.json
├── build.py                    JSON → SQLite compiler
└── tests/
```

Regulation file paths are flat by design: `authority` + `part` + `section`
are the only parts of a citation that are truly stable. Subpart and title
number are stored inside the file, so a section can be re-subparted without
a rename.

## JSON formats

### Regulation file (`data/regulations/faa/25/1309.json`)

One file per regulation section, containing every known amendment of that
section. Example:

```json
{
  "authority": "FAA",
  "title_number": 14,
  "part": "25",
  "subpart": "F",
  "section": "1309",
  "canonical_title": "Equipment, systems, and installations",
  "subject_group": "Equipment",
  "amendments": [
    {
      "designator": "25-23",
      "ordinal": 23,
      "effective_date": "1970-05-08",
      "title_at_amendment": "Equipment, systems, and installations",
      "text": "...full regulation text at this amendment...",
      "source_url": "https://drs.faa.gov/browse/excelExternalWindow/{GUID}.0001",
      "federal_register_cite": "35 FR 5665"
    }
  ]
}
```

**Top-level fields**

| Field             | Type      | Nullable | Purpose |
|-------------------|-----------|----------|---------|
| `authority`       | string    | no       | Issuing authority. Currently only `"FAA"`. Reserved so EASA etc. can coexist without schema change. |
| `title_number`    | integer   | no       | CFR title. For FAA regulations always `14`. Stored as a field (not in the path) so an atypical citation doesn't force a move. |
| `part`            | string    | no       | CFR part, e.g. `"25"` (transport) or `"23"` (normal/utility). String, not int, because some parts are non-numeric (`"SFAR"`). |
| `subpart`         | string    | yes      | Current subpart letter, e.g. `"F"`. For appendix entries use the form `"Appendix C"`. `null` when the section is not under any subpart. Subparts get reorganised occasionally; treated as metadata, not identity. |
| `section`         | string    | no       | Section number within the part, e.g. `"1309"`. String to allow suffixes like `"1309a"`. |
| `canonical_title` | string    | no       | Present-day title. What the app shows as the section heading when no specific amendment is in view. |
| `subject_group`   | string    | yes      | FAA's intra-subpart grouping label, e.g. `"Equipment"`, `"Emergency Provisions"`. Sourced from DRS `metadatas["Subject Group"]`. Optional — `null` when DRS has no value. Useful for sidebar/search facets in the app. |
| `amendments`      | array     | no       | All amendments that have ever changed this section. Must be non-empty. |

**Per-amendment fields** (all required, all non-null)

| Field                   | Type    | Purpose |
|-------------------------|---------|---------|
| `designator`            | string  | Human-readable amendment ID, e.g. `"25-23"`. This is what TCDS documents cite. Unique per regulation. For original FAR adoption entries (where DRS reports `"Initial"` and ordinal is `0`), synthesise `"{part}-0"` (e.g. `"25-0"`) so the designator pattern stays uniform. |
| `ordinal`               | integer | Numeric ordering key extracted from the designator. `"25-23"` → `23`. Used to (a) sort amendments and (b) expand ranges like "25-1 through 25-62" into specific rows. `0` marks the original adoption (the section as it appeared at FAR enactment, before any amendment). |
| `effective_date`        | date    | ISO `YYYY-MM-DD`. Secondary sort key and shown to users. Display formatting happens in the app, not here. |
| `title_at_amendment`    | string  | Section heading as it read at this amendment. Kept separate from `canonical_title` because titles have been edited across amendments, and correctness matters when you're showing a historical view. |
| `text`                  | string  | Full regulation text at this amendment. This is the whole reason the dataset exists. Rendered inside `<pre>` / whitespace-preserving CSS; never unsafe-rendered. |
| `source_url`            | url     | Where the text was transcribed from. For FAA amendments, prefer the DRS canonical URL `https://drs.faa.gov/browse/excelExternalWindow/{GUID}.0001` because it is amendment-specific. eCFR or scanned-FR URLs are acceptable fallbacks when no DRS document exists. |
| `federal_register_cite` | string  | FR citation that promulgated the amendment, e.g. `"35 FR 5665"`. Historical reference. |

### Aircraft file (`data/aircraft/A16WE.json`)

One file per aircraft, keyed by TCDS number. Example:

```json
{
  "tcds_number": "A16WE",
  "manufacturer": "The Boeing Company",
  "model_designation": "737-800",
  "common_name": "737-800",
  "category": "transport",
  "tcds_revision": "57",
  "tcds_revision_date": "2024-03-15",
  "tcds_source_url": "https://...",
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
```

**Top-level fields**

| Field                | Type    | Nullable | Purpose |
|----------------------|---------|----------|---------|
| `tcds_number`        | string  | no       | FAA Type Certificate Data Sheet number. Primary key. |
| `manufacturer`       | string  | no       | Current TC holder name (as it appears on the TCDS). |
| `model_designation`  | string  | no       | Formal model identifier from the TCDS, e.g. `"737-800"`. |
| `common_name`        | string  | yes      | Popular name if it differs from `model_designation`. Optional, used for search. |
| `category`           | string  | yes      | FAA airworthiness category (`transport`, `normal`, `utility`, `acrobatic`, `commuter`, `restricted`, …). Drives filtering and display. |
| `tcds_revision`      | string  | yes      | Revision identifier of the TCDS the data was taken from. String because revisions are sometimes alphanumeric. |
| `tcds_revision_date` | date    | yes      | ISO date of that revision. Lets users spot stale data. |
| `tcds_source_url`    | url     | yes      | Link to the source TCDS document. |
| `notes`              | string  | yes      | Free-form editor notes. Displayed to users. |
| `certification_basis`| array   | no       | Ordered list of cert-basis entries. Must be non-empty. |

**Per-entry fields** (`certification_basis[]`)

| Field                  | Type    | Nullable | Purpose |
|------------------------|---------|----------|---------|
| `display_order`        | integer | no       | Render order on the aircraft page. Matches the order the TCDS lists items. |
| `entry_type`           | enum    | no       | One of `regulation`, `special_condition`, `elos`, `exemption`, `other`. Determines how the entry is rendered and whether it resolves to regulation text. |
| `raw_reference`        | string  | no       | The TCDS text, verbatim. Always preserved so users can check our interpretation against the original. |
| `applicability_notes`  | string  | yes      | Scope/caveats from the TCDS ("applies to serial numbers 1–500", "except §25.1309"). Shown beneath the entry. |
| `resolved_references`  | array   | no       | Machine-readable interpretation of `raw_reference`. Empty for entry types we don't resolve to regulations yet (special conditions, ELOS, exemptions). |

**Per resolved reference** — two shapes:

*Range* — compact, expanded at build time:
```json
{ "reference_kind": "range",
  "authority": "FAA", "title_number": 14, "part": "25",
  "from_amendment_ordinal": 1, "to_amendment_ordinal": 62 }
```
Expands to one `certification_basis_entries` row per section in the part,
each pointing at the highest amendment ≤ `to_amendment_ordinal` for that
section.

*Single* — explicit, one row:
```json
{ "reference_kind": "single",
  "authority": "FAA", "title_number": 14, "part": "25", "section": "1309",
  "amendment_designator": "25-58" }
```
Used for per-section exceptions ("Part 25 through 25-62 *except* §25.1309
at 25-58") and for pinpoint citations.

## SQLite schema

`build.py` compiles the JSON into four tables plus one view.

### `regulations` — one row per CFR section

Identity columns (`authority`, `title_number`, `part`, `section`) plus the
`subpart` and `canonical_title` metadata. This table exists so that
amendments have something stable to hang off: the section identity is
stable, individual amendments come and go.

### `regulation_amendments` — one row per (section, amendment)

The actual regulation text lives here. One row per amendment of each
section. `ordinal` is indexed because range expansion does
`WHERE regulation_id = ? AND ordinal <= ?` constantly.

Every row has non-null `text` — an aircraft cannot reference an amendment
that doesn't have text yet. If you need to ingest an aircraft whose
referenced amendments aren't transcribed, add the amendments first (even
with placeholder text) or build will fail.

### `aircraft` — one row per TCDS

Straightforward mirror of the top-level fields in the aircraft JSON.

### `certification_basis_entries` — one row per resolved cert-basis item

The denormalised result of expanding each aircraft's `resolved_references`.

- An aircraft entry of type `regulation` with a `range` covering 62
  amendments of a part with 400 sections produces ~400 rows here (one per
  section, each pinned to the highest ordinal ≤ the range's upper bound).
- An entry of type `special_condition` / `elos` / `exemption` / `other`
  produces one row with `regulation_amendment_id = NULL` — we keep the
  `raw_reference` for display but have no regulation text to link to yet.

`display_order` lets the app re-assemble the TCDS's original ordering
instead of showing the denormalised flood in section order.

### `latest_amendments` view

Convenience view: for each regulation, the row from `regulation_amendments`
with the highest `ordinal`. Used by part-vs-part comparison ("show §23.1309
at its latest amendment next to §25.1309 at its latest amendment") without
making the query author figure out the MAX-subquery every time.

## Build pipeline

```bash
python build.py                     # reads data/, writes cert_basis.sqlite
python build.py --data-dir X --out Y.sqlite
```

`build.py`:
1. Validates every JSON file against its schema. Fails on any mismatch.
2. Inserts regulations and amendments.
3. Inserts aircraft.
4. For each cert-basis entry, expands `resolved_references` and inserts
   one row per resolved citation. Fails if a range references an amendment
   not present in the regulation data.
5. Writes `build_report.json` alongside the SQLite file: row counts,
   unresolvable references (should always be zero on a successful build).

Output is atomic: build writes `cert_basis.sqlite.new` then `os.replace()`s
it into place, so a consumer never sees a half-written DB.

## Consuming the SQLite artifact

`cert_basis.sqlite` ships in WAL mode — `build.py` sets
`PRAGMA journal_mode = WAL` and the journal mode is persisted in the file
header, so every consumer sees a WAL database. Consumers should treat the
file as read-only and configure each connection like this:

```python
import sqlite3

conn = sqlite3.connect("cert_basis.sqlite")
conn.execute("PRAGMA query_only = ON")        # read-only guard
conn.execute("PRAGMA foreign_keys = ON")      # not persisted; per-connection
conn.execute("PRAGMA synchronous = NORMAL")   # safe under WAL
conn.execute("PRAGMA busy_timeout = 5000")    # ms; wait out checkpoints
```

- `journal_mode = WAL` is already on the file. Consumers don't re-set it
  (and can't, on a read-only connection).
- `synchronous`, `busy_timeout`, `foreign_keys`, and `query_only` are
  per-connection and must be issued every time a new connection is opened.
- Under WAL, readers and a writer can operate concurrently. This repo only
  ever produces a single writer (the build), so the consuming app should
  open read-only connections.

## Adding data

**New aircraft:** create `data/aircraft/{TCDS}.json`, run `build.py`. If
build fails with missing-amendment errors, add the amendments to the
relevant regulation files first.

**New regulation:** create `data/regulations/{authority}/{part}/{section}.json`
with at least one amendment. Partial amendment coverage is fine as long as
no aircraft references the gaps.

**New amendment to existing regulation:** append to the `amendments` array
in the existing file. Ordinals must be unique within the file.
