# FARFETCHed — Plan

## Purpose

A public web app that displays the certification basis of type-certificated
aircraft, sourced from FAA Type Certificate Data Sheets (TCDS). Users can:

- View an aircraft's cert basis with full regulation text at the referenced
  amendment levels.
- Compare two amendments of the same regulation section.
- Compare the same section across parts (e.g. §23.1309 vs §25.1309) at their
  latest amendment.
- Download the cert basis as CSV or JSON.
- Submit a structured cert basis file and receive a resolved version with full
  regulation text included.
- Flag data issues for review.

Initial scope: 14 CFR (FAA) only. Design leaves room for EASA, special
conditions, equivalent level of safety findings, and exemptions without schema
breakage.

## Architecture

Two repositories:

### `FARfetched-data`
Canonical source of truth. Located at `../FARfetched-data`. Contains:
- JSON files for regulations and aircraft, validated against strict schemas.
- `build.py` — compiles JSON into `cert_basis.sqlite`.
- GitHub Actions workflow that validates, builds, and publishes the SQLite
  file as a release artifact.

### `FARFETCHed`
Flask web application. On deploy, fetches the latest `cert_basis.sqlite` from
the data repo's GitHub releases. Contains no data itself.

## Tech Stack

- **Language:** Python 3.12+
- **Framework:** Flask 3.x with Jinja2 templates
- **Validation:** Pydantic v2
- **Database:** SQLite (stdlib `sqlite3`, WAL mode, foreign keys on)
- **Frontend interactivity:** HTMX + vanilla JS
- **Tooling:** `uv` for deps, `ruff` for lint+format, `mypy` for types,
  `pytest` for tests
- **Hosting:** NearlyFreeSpeech.net (Python daemon realm)

## Database Schema

```sql
CREATE TABLE regulations (
    id              INTEGER PRIMARY KEY,
    authority       TEXT NOT NULL,            -- 'FAA'
    title_number    INTEGER NOT NULL,         -- 14
    part            TEXT NOT NULL,            -- '23', '25'
    subpart         TEXT,
    section         TEXT NOT NULL,            -- '1309'
    section_title   TEXT,
    UNIQUE (authority, title_number, part, subpart, section)
);

CREATE TABLE regulation_amendments (
    id                      INTEGER PRIMARY KEY,
    regulation_id           INTEGER NOT NULL REFERENCES regulations(id),
    amendment_designator    TEXT NOT NULL,      -- '25-62'
    amendment_ordinal       INTEGER,            -- 62
    effective_date          DATE,
    text                    TEXT,               -- null when status='pending'
    title_at_amendment      TEXT,
    source_url              TEXT,
    federal_register_cite   TEXT,
    status                  TEXT NOT NULL
                            CHECK (status IN ('ingested','pending','flagged')),
    UNIQUE (regulation_id, amendment_designator)
);

CREATE INDEX idx_amendments_reg_date
    ON regulation_amendments (regulation_id, effective_date);
CREATE INDEX idx_amendments_reg_ordinal
    ON regulation_amendments (regulation_id, amendment_ordinal);

CREATE TABLE aircraft (
    id                  INTEGER PRIMARY KEY,
    tcds_number         TEXT NOT NULL UNIQUE,
    manufacturer        TEXT NOT NULL,
    model_designation   TEXT NOT NULL,
    common_name         TEXT,
    category            TEXT,
    tcds_revision       TEXT,
    tcds_revision_date  DATE,
    tcds_source_url     TEXT,
    notes               TEXT
);

CREATE TABLE certification_basis_entries (
    id                          INTEGER PRIMARY KEY,
    aircraft_id                 INTEGER NOT NULL REFERENCES aircraft(id),
    regulation_amendment_id     INTEGER REFERENCES regulation_amendments(id),
    entry_type                  TEXT NOT NULL,
                                -- 'regulation' | 'special_condition'
                                -- | 'elos' | 'exemption' | 'other'
    raw_reference               TEXT NOT NULL,
    applicability_notes         TEXT,
    display_order               INTEGER NOT NULL,
    UNIQUE (aircraft_id, regulation_amendment_id, entry_type, raw_reference)
);

CREATE INDEX idx_cbe_aircraft
    ON certification_basis_entries (aircraft_id, display_order);

CREATE VIEW latest_amendments AS
SELECT ra.*
FROM regulation_amendments ra
WHERE ra.status = 'ingested'
  AND ra.amendment_ordinal = (
      SELECT MAX(amendment_ordinal)
      FROM regulation_amendments
      WHERE regulation_id = ra.regulation_id AND status = 'ingested'
  );
```

### Notes on design

- `status='pending'` on `regulation_amendments` allows the build script to
  stub out amendments referenced by aircraft but not yet ingested. `text` is
  nullable for this reason.
- `certification_basis_entries.regulation_amendment_id` is nullable for
  entries where the raw TCDS reference cannot be parsed.
- `raw_reference` is always preserved for traceability.
- Entry `status` is always derivable from joined state; it is not duplicated
  on the entry row.
- Polymorphic handling of special conditions, ELOS, exemptions is deferred.
  For MVP only `entry_type='regulation'` produces an FK link; other types
  keep `regulation_amendment_id` null and rely on `raw_reference`.

## JSON Data Format

All files validated against strict JSON Schemas with
`additionalProperties: false`.

### Regulation section (`data/regulations/{authority}/{title}/{part}/{section}.json`)

One file per section, containing all known amendments.

```json
{
  "authority": "FAA",
  "title_number": 14,
  "part": "25",
  "subpart": "F",
  "section": "1309",
  "canonical_title": "Equipment, systems, and installations",
  "amendments": [
    {
      "designator": "25-23",
      "ordinal": 23,
      "effective_date": "1970-05-08",
      "text": "...",
      "source_url": "https://www.ecfr.gov/...",
      "federal_register_cite": "35 FR 5665",
      "status": "ingested"
    },
    {
      "designator": "25-41",
      "ordinal": 41,
      "status": "pending"
    }
  ]
}
```

### Aircraft (`data/aircraft/{tcds}.json`)

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
          "authority": "FAA", "title_number": 14, "part": "25",
          "from_amendment_ordinal": 1,
          "to_amendment_ordinal": 62
        }
      ]
    },
    {
      "display_order": 2,
      "entry_type": "special_condition",
      "raw_reference": "Special Conditions 25-123-SC",
      "resolved_references": []
    }
  ]
}
```

`resolved_references` may use `reference_kind: "range"` (compact) or
`"single"` (explicit). Ranges are expanded by `build.py` against the current
regulations set. An explicit `single` form is available for per-section
exceptions (e.g. "through 25-62 except §25.1309 at 25-58").

## HTTP API

```
GET  /api/aircraft                              list, paginated
GET  /api/aircraft/{tcds}                       aircraft + full cert basis
GET  /api/aircraft/{tcds}.csv                   cert basis as flat CSV
GET  /api/aircraft/{tcds}.json                  same schema as data repo

GET  /api/regulations/{authority}/{part}/{section}
                                                section + amendment metadata
GET  /api/regulations/{authority}/{part}/{section}/{amendment}
                                                single amendment with text

GET  /api/compare/amendments?ids=<a>,<b>        two amendments
GET  /api/compare/parts?section=<s>
                      &parts=<p1>,<p2>
                      &amendment=latest|<designator>

POST /api/resolve                               upload cert basis, return resolved
POST /api/issues                                flag an issue
```

### CSV export schema (stable contract)

```
display_order, entry_type, raw_reference, authority, part, subpart,
section, section_title, amendment_designator, effective_date,
amendment_status, source_url, applicability_notes, text
```

## Build Pipeline

### Data repo layout

```
FARfetched-data/
├── schemas/
│   ├── regulation.schema.json
│   └── aircraft.schema.json
├── data/
│   ├── regulations/faa/14/{part}/{section}.json
│   └── aircraft/{tcds}.json
├── build.py
├── tests/
├── pyproject.toml
└── .github/workflows/build.yml
```

### `build.py` responsibilities

1. Validate every JSON file against its schema. Fail on mismatch.
2. Load regulations; insert `regulations` and `regulation_amendments` rows
   (respecting `status`).
3. Load aircraft; for each `resolved_reference`:
   - Expand ranges against loaded regulations.
   - Look up or create `pending` amendment rows for references not yet
     ingested.
   - Insert `certification_basis_entries` rows.
4. Emit `cert_basis.sqlite`.
5. Emit `build_report.json` with counts: regulations, amendments by status,
   aircraft, cert basis entries, unresolvable references.

### CI

On push to `main` and on tags: validate, build, test. On tags: upload
`cert_basis.sqlite` and `build_report.json` as release assets.

## App Deploy

The app repo's deploy pulls the latest SQLite from the data repo's GitHub
releases via HTTPS. No credentials needed (public releases). Startup
script: fetch → atomic replace → restart Flask daemon.

## Build Sequence

Each phase shippable/testable before starting the next.

1. **Schemas.** Write `regulation.schema.json` and `aircraft.schema.json`.
   Hand-craft 2–3 example files and validate.
2. **`build.py` skeleton.** Load → validate → emit SQLite. Implement range
   expansion.
3. **Seed data.** Convert existing data for 1–2 aircraft end-to-end.
4. **Flask app, read-only.** Aircraft list, aircraft detail, regulation
   detail. Proves query patterns and two-repo deploy flow.
5. **Compare views.** Amendment-vs-amendment and part-vs-part. Side-by-side
   text first; diff visualisation is pure UI work over the same data.
6. **Export.** CSV and JSON download on aircraft detail.
7. **Upload/resolve endpoint.** `POST /api/resolve`. Reuses aircraft schema
   as request format.
8. **Issue flagging.** GitHub Issues API or local `issues` table (TBD).

## Deferred

- Full-text search via SQLite FTS5
- Special conditions, ELOS, exemptions with their own tables
- Non-FAA authorities (EASA, TCCA)
- Cross-part equivalent-section mapping
- TCDS PDF scraping automation
- Diff visualisation UI polish

## Open Decisions

- **Issue flagging backend:** GitHub Issues API vs local `issues` table.
  Leaning GitHub — triage happens where the fix happens.
- **NFSN deploy mechanics:** dry-run app-fetches-release pattern with a
  placeholder 1 KB SQLite before building anything dependent on it.
