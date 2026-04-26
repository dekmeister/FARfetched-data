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
-- Lookups
CREATE TABLE naa_authorities (
    id      INTEGER PRIMARY KEY,
    code    TEXT NOT NULL UNIQUE,        -- 'FAA', 'EASA'
    name    TEXT NOT NULL,
    country TEXT
);

CREATE TABLE manufacturers (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE categories (
    id   INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,           -- 'transport', 'normal', ...
    name TEXT NOT NULL
);

-- Regulations
CREATE TABLE regulation_parts (
    id           INTEGER PRIMARY KEY,
    authority_id INTEGER NOT NULL REFERENCES naa_authorities(id),
    title_number INTEGER NOT NULL,
    part         TEXT NOT NULL,           -- '23', '25', 'SFAR'
    description  TEXT,
    UNIQUE (authority_id, title_number, part)
);

CREATE TABLE regulations (
    id              INTEGER PRIMARY KEY,
    part_id         INTEGER NOT NULL REFERENCES regulation_parts(id),
    section         TEXT NOT NULL,        -- '1309'
    current_subpart TEXT,                 -- present-day display only
    canonical_title TEXT NOT NULL,
    subject_group   TEXT,
    UNIQUE (part_id, section)
);

CREATE TABLE amendments (
    id             INTEGER PRIMARY KEY,
    part_id        INTEGER NOT NULL REFERENCES regulation_parts(id),
    designator     TEXT NOT NULL,    -- '25-62'
    ordinal        INTEGER NOT NULL,
    effective_date DATE NOT NULL,
    UNIQUE (part_id, designator),
    UNIQUE (part_id, ordinal)
);

CREATE TABLE section_amendments (
    id                    INTEGER PRIMARY KEY,
    regulation_id         INTEGER NOT NULL REFERENCES regulations(id),
    amendment_id          INTEGER NOT NULL REFERENCES amendments(id),
    subpart_at_time       TEXT,             -- historical subpart
    title_at_amendment    TEXT NOT NULL,
    text                  TEXT NOT NULL,
    federal_register_cite TEXT NOT NULL,    -- per-section (FR page varies by section)
    source_url            TEXT,
    UNIQUE (regulation_id, amendment_id)
);

CREATE INDEX idx_sa_reg ON section_amendments (regulation_id);
CREATE INDEX idx_amendments_part_ordinal ON amendments (part_id, ordinal);

-- Aircraft / TCDS
CREATE TABLE aircraft_models (
    id                INTEGER PRIMARY KEY,
    manufacturer_id   INTEGER NOT NULL REFERENCES manufacturers(id),
    model_designation TEXT NOT NULL,      -- '737-800'
    common_name       TEXT,
    notes             TEXT,
    UNIQUE (manufacturer_id, model_designation)
);

CREATE TABLE model_categories (
    model_id    INTEGER NOT NULL REFERENCES aircraft_models(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    PRIMARY KEY (model_id, category_id)
);

CREATE TABLE tcds (
    id            INTEGER PRIMARY KEY,
    authority_id  INTEGER NOT NULL REFERENCES naa_authorities(id),
    tcds_number   TEXT NOT NULL,          -- 'A16WE', 'EASA.IM.A.120'
    revision      TEXT,
    revision_date DATE,
    source_url    TEXT,
    UNIQUE (authority_id, tcds_number)
);

CREATE TABLE tcb (
    id       INTEGER PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES aircraft_models(id),
    tcds_id  INTEGER NOT NULL REFERENCES tcds(id),
    notes    TEXT,
    UNIQUE (model_id, tcds_id)
);

CREATE TABLE cert_basis_entries (
    id                    INTEGER PRIMARY KEY,
    tcb_id                INTEGER NOT NULL REFERENCES tcb(id),
    section_amendment_id  INTEGER REFERENCES section_amendments(id),
    entry_type            TEXT NOT NULL
                          CHECK (entry_type IN
                              ('regulation','special_condition','elos',
                               'exemption','other')),
    raw_reference         TEXT NOT NULL,
    applicability_notes   TEXT,
    display_order         INTEGER NOT NULL
);

CREATE INDEX idx_cbe_tcb ON cert_basis_entries (tcb_id, display_order);

CREATE VIEW latest_amendments AS
SELECT sa.*, a.designator, a.ordinal, a.effective_date
FROM section_amendments sa
JOIN amendments a ON a.id = sa.amendment_id
WHERE a.ordinal = (
    SELECT MAX(a2.ordinal)
    FROM section_amendments sa2
    JOIN amendments a2 ON a2.id = sa2.amendment_id
    WHERE sa2.regulation_id = sa.regulation_id
);
```

### Notes on design

- `cert_basis_entries` is owned by `tcb`, not by `aircraft_models` directly.
  The TCB is identified by the (aircraft_model, tcds) pair, so an aircraft
  with FAA and EASA type certificates gets two separate certification bases.
- `effective_date` lives on `amendments` (same for all sections in one
  amendment). `federal_register_cite` lives on `section_amendments` because
  different sections changed by the same amendment appear on different FR pages.
- `model_categories` is M:N because a single TCDS can certify a model in
  multiple categories simultaneously (e.g. "normal, utility, acrobatic").
- `section_amendments.subpart_at_time` captures the historical subpart for
  correctness when showing a regulation at an old amendment.
- `section_amendment_id` is nullable on `cert_basis_entries` for entry types
  that don't resolve to regulation text (special conditions, ELOS, exemptions).
- `raw_reference` is always preserved for traceability.
- `entry_type` is an inline CHECK constraint — five values is too small to
  warrant a lookup table.

## JSON Data Format

All files validated against strict JSON Schemas with
`additionalProperties: false`.

### Part file (`data/regulations/{authority}/{part}/_part.json`)

One file per CFR part. Master amendment list for the part.

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

### Regulation section (`data/regulations/{authority}/{part}/{section}.json`)

One file per section. Per-section amendment payload.

```json
{
  "authority": "FAA",
  "part": "25",
  "section": "1309",
  "current_subpart": "F",
  "canonical_title": "Equipment, systems, and installations",
  "amendments": [
    {
      "designator": "25-23",
      "subpart_at_time": "F",
      "title_at_amendment": "Equipment, systems, and installations",
      "text": "...",
      "federal_register_cite": "35 FR 5665",
      "source_url": "https://drs.faa.gov/..."
    }
  ]
}
```

Each amendment's `designator` must be declared in the part's `_part.json`.
Build fails loud if any section references an undeclared designator.

### Aircraft model (`data/aircraft/{manufacturer-slug}/{model-slug}.json`)

One file per model variant. The `tcb` array holds one entry per certifying
authority. The certification basis belongs to the (model, TCDS) pair, not to
the model alone.

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
          "applicability_notes": null,
          "resolved_references": []
        }
      ]
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
│   ├── regulation_part.schema.json
│   ├── regulation.schema.json
│   └── aircraft_model.schema.json
├── data/
│   ├── regulations/{authority}/{part}/_part.json
│   ├── regulations/{authority}/{part}/{section}.json
│   └── aircraft/{manufacturer-slug}/{model-slug}.json
├── build.py
├── tests/
├── pyproject.toml
└── .github/workflows/build.yml
```

### `build.py` responsibilities

1. Validate every JSON file against its schema. Fail on mismatch.
2. Build lookup tables: `naa_authorities`, `manufacturers`, `categories`.
3. Load `_part.json` files → `regulation_parts` and `amendments`.
4. Load section files → `regulations` and `section_amendments`. Fail loud
   if a section references an amendment designator not in its part file.
5. Load aircraft model files → `aircraft_models`, `model_categories`,
   `tcds`, `tcb`.
6. For each cert-basis entry, expand `resolved_references` to
   `section_amendment_id`. Fail on any unresolved reference.
7. Emit `cert_basis.sqlite`.
8. Emit `cert_basis_report.json` with row counts for all tables and a list
   of unresolvable references (must be empty on success).

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
- ~~Optional regulation amendment fields (`drs_guid`, `docket_number`,
  `nprm`)~~ — `docket_number` and `nprm` are now captured in the
  `amendment_actions` table (`type`, `reference`, `issued_on`). `drs_guid`
  remains deferred (stored only in `_diag` in fetched JSON; no build consumer
  yet).

- Relax `federal_register_cite` requirement for pre-1996 ordinal-0
  entries that have no programmatic FR cite source. Pair with a sibling
  `federal_register_cite_verified` boolean and surface unverified rows
  in `build_report.json`.
- Track down the DRS download path for the official "DRS API Technical
  Documentation.pdf" (alfId in `tools/FAA_DRS.md` §3.5). If found, it
  supersedes the reverse-engineered notes.

## Open Decisions

- **Issue flagging backend:** GitHub Issues API vs local `issues` table.
  Leaning GitHub — triage happens where the fix happens.
- **NFSN deploy mechanics:** dry-run app-fetches-release pattern with a
  placeholder 1 KB SQLite before building anything dependent on it.
