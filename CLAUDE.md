# CLAUDE.md — FARfetched-data (data repo)

Guidance for AI coding assistants working in this repository.

This is the **data repo**. It contains JSON source files for FAA aircraft
and regulations, plus a `build.py` that compiles them into a single
`cert_basis.sqlite`. It contains no application code. The Flask web app
lives in a separate repo and consumes the SQLite artifact.

- Project scope and roadmap: [plan.md](plan.md)
- Data formats, field-by-field reference, SQLite schema, build behaviour:
  [README.md](README.md)

**Read README.md before proposing schema or format changes.** It is the
field-level contract.

## Project Context

- Scale: one maintainer, low traffic, public read-only consumer.
- The data here is the point. Favour correctness and traceability over
  cleverness. Every transcribed amendment carries a `source_url` and
  `federal_register_cite` for a reason.
- Prefer stdlib and hand-written code over dependencies.
- Keep `build.py` a single file. No package layout until it earns it.

## Tech Stack

- Python 3.12+
- `jsonschema` for validation
- stdlib `sqlite3` (no ORM)
- `uv` (deps), `ruff` (lint+format), `mypy` (types), `pytest` (tests)

## Repo Layout

See [README.md §Layout](README.md). Summary:

```
FARfetched-data/
├── plan.md
├── README.md
├── schemas/                    JSON Schema files (Draft 2020-12)
├── data/
│   ├── regulations/{authority}/{part}/{section}.json
│   └── aircraft/{tcds}.json
├── build.py
└── tests/
```

## Common Commands

```bash
# Setup
uv sync

# Build the SQLite artifact
uv run python build.py

# Validate without building (if implemented)
uv run python build.py --check

# Quality
uv run ruff check .
uv run ruff format .
uv run mypy .
uv run pytest

# Inspect the built DB
sqlite3 cert_basis.sqlite '.schema'
sqlite3 cert_basis.sqlite 'SELECT COUNT(*) FROM aircraft;'
```

## Code Style

- Type hints on all function signatures. PEP 604 syntax (`str | None`).
- `pathlib.Path` over `os.path`.
- f-strings, never string-interpolation into SQL — use `?` parameters.
- Dataclasses or Pydantic for structured data. Not dicts.
- Context managers for DB connections and files.
- Line length 88. Don't fight the formatter.
- Prefer explicit over clever.

## `build.py` conventions

- Single file, stdlib + `jsonschema`.
- Fail loud on any schema mismatch, any unresolvable reference, any
  duplicate key. The build is the last line of defence — don't paper over
  bad data.
- Atomic output: write `cert_basis.sqlite.new`, then `os.replace()`.
- `PRAGMA foreign_keys = ON`, `PRAGMA journal_mode = WAL` on the built DB.
- Parameterised SQL. No string concatenation.
- Emit `build_report.json` with row counts for every table. Zero unresolved
  references is a success criterion, not a nice-to-have.

## Data conventions

The field-level contract is in [README.md](README.md). Rules that matter
at the repo level:

- **ISO `YYYY-MM-DD` dates everywhere.** Display formatting is the app's
  job, not this repo's.
- **No `status` column on amendments.** Every amendment must have `text`.
  An aircraft that references an untranscribed amendment can't be added
  until that amendment is transcribed. This is deliberate — see plan.md.
- **`raw_reference` is sacred.** Never rewrite or normalise it. It's the
  unmodified TCDS text, kept for traceability against the original PDF.
- **Regulation file paths are flat:**
  `data/regulations/{authority}/{part}/{section}.json`. `title_number` and
  `subpart` are fields inside the file, not directories. Don't introduce
  additional path segments.
- **`additionalProperties: false`** in every JSON Schema. If you need a new
  field, update the schema, the README, and the build.

## Testing

- `pytest`. Fixtures point at a small hand-written `tests/fixtures/` tree
  that exercises range expansion, single references, and each
  `entry_type`.
- Smoke test: run `build.py` against fixtures, open the resulting SQLite,
  assert known row counts and that specific known queries return the
  expected rows (e.g. `SELECT * FROM latest_amendments WHERE ...`).
- Don't chase 100% coverage. Test behaviour.

## Do / Don't

**Do:**
- Preserve `raw_reference` exactly as it appears on the TCDS.
- Include `source_url` and `federal_register_cite` on every amendment.
- Add a schema change, a README update, and a test in the same commit.
- Fail the build on any unresolved reference.

**Don't:**
- Don't introduce an ORM.
- Don't add application logic here. App code lives in FARFETCHed.
- Don't commit `cert_basis.sqlite` or `build_report.json` — they are build
  outputs.
- Don't mutate JSON files to work around a build failure. Fix the data or
  fix the schema.
- Don't invent fields. If something new is needed, update schema, README,
  and build together.

## When In Doubt

- The source PDF on faa.gov is the authority. If the JSON disagrees with
  the PDF, the JSON is wrong.
- If a TCDS reference can't be resolved cleanly, record it verbatim in
  `raw_reference` with `resolved_references: []` and surface it in the
  build report rather than guessing.
- Ask before large schema changes. Every field is a downstream commitment.
