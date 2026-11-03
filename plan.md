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
- **Database:** SQLite (stdlib `sqlite3`, STRICT tables, foreign keys on;
  shipped as a single read-only file in DELETE journal mode)
- **Frontend interactivity:** HTMX + vanilla JS
- **Tooling:** `uv` for deps, `ruff` for lint+format, `mypy` for types,
  `pytest` for tests
- **Hosting:** NearlyFreeSpeech.net (Python daemon realm)

## Database Schema and JSON Data Format

The field-level contract (JSON formats, SQLite schema, cert-basis resolution
rules, build behaviour) lives in [README.md](README.md); the DDL itself is
`SCHEMA_SQL` in [build.py](build.py). It is not repeated here, so the two
can't drift apart again.

In short: every citable source is a **document** (`issuers` → `documents` →
`document_revisions` → `provisions` → `provision_versions`), so EASA CS,
special conditions, ELOS, exemptions and advisory circulars fit without new
table families. A cert basis is stored in three layers: one row per TCDS
line (`cert_basis_entries`, verbatim), its machine-readable interpretation
(`cert_basis_refs`), and the build-computed expansion
(`cert_basis_resolved`). The certification basis belongs to the (model,
TCDS) pair (`tcb`), so a model with FAA and EASA certificates has two bases.
The design rationale is in
[reviews/2026-10-31-db-schema/](reviews/2026-10-31-db-schema/).

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
│   ├── common.schema.json
│   ├── document.schema.json
│   ├── provision.schema.json
│   └── aircraft_model.schema.json
├── data/
│   ├── documents/{issuer}/{document}/_document.json
│   ├── documents/{issuer}/{document}/{provision}.json
│   └── aircraft/{manufacturer-slug}/{model-slug}.json
├── build.py
├── tests/
├── pyproject.toml
└── .github/workflows/build.yml
```

### `build.py` responsibilities

See [README.md §Build pipeline](README.md#build-pipeline). In short:
validate every file, load documents → provisions → aircraft, resolve each
cert-basis entry's references, fail loud on anything unresolvable or
inconsistent, then atomically write `cert_basis.sqlite` and
`cert_basis_report.json`.

### CI

On push to `main` and on tags: validate, build, test. On tags: upload
`cert_basis.sqlite` and `cert_basis_report.json` as release assets.

## App Deploy

The app repo's deploy pulls the latest SQLite from the data repo's GitHub
releases via HTTPS. No credentials needed (public releases). Startup
script: fetch → atomic replace → restart Flask daemon.

## Build Sequence

Each phase shippable/testable before starting the next.

1. **Schemas.** Write `provision.schema.json` and `aircraft_model.schema.json`.
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
- Special conditions, ELOS, exemptions as documents (`doc_kind`; the schema
  already allows them — needs ingestion)
- Non-FAA issuers beyond EASA (TCCA, ...)
- Cross-part equivalent-section mapping (`provision_relations`, deferred
  from the 2026-10-31 review). The computed half is done: schema v5's
  `provision_similarity` (docs/SQLITE.md §Similarity). Hand-confirmed relations and
  explicit cross-citations (e.g. MIL-HDBK-516 citing 14 CFR sections) are
  still deferred.
- ~~Repeal / `[Reserved]` representation~~ — schema v2 adds `deleted: true`
  versions (added for EASA CS-23 Amdt 5). FAA 23-64 (the 2017 Part 23
  rewrite) can now be ingested; `[Reserved]` text is still stored verbatim.
- Structured serial-number applicability (`applicability` is verbatim)
- TCDS PDF scraping automation
- Diff visualisation UI polish
- ~~Optional regulation amendment fields (`drs_guid`, `docket_number`,
  `nprm`)~~ — `docket_number` and `nprm` are now captured in the
  `version_actions` table (`action_type`, `reference`, `issued_on`). `drs_guid`
  remains deferred (stored only in `_diag` in fetched JSON; no build consumer
  yet).

- ~~Relax the FR cite requirement for pre-1996 ordinal-0 entries~~ —
  `publication_cite` is optional; the `"Initial Adoption"` sentinel is gone.
- Track down the DRS download path for the official "DRS API Technical
  Documentation.pdf" (alfId in `tools/FAA_DRS.md` §3.5). If found, it
  supersedes the reverse-engineered notes.

## Open Decisions

- **Issue flagging backend:** GitHub Issues API vs local `issues` table.
  Leaning GitHub — triage happens where the fix happens.
- **NFSN deploy mechanics:** dry-run app-fetches-release pattern with a
  placeholder 1 KB SQLite before building anything dependent on it.
