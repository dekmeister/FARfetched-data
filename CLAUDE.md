# CLAUDE.md — FARfetched-data (data repo)

Guidance for AI coding assistants working in this repository.

This is the **data repo**. It contains no application code. Three roles:

- **`tools/` produces `data/`.** JSON for documents, provisions and aircraft
  is built from local source copies plus override rows, and promoted after
  review. Nothing else writes `data/`. The one exception is `data/NOTICE`, the
  hand-written rights statement (docs/RIGHTS.md).
- **`build.py` checks and compiles.** It validates `data/`, resolves every
  cert-basis reference, fails loud, and writes `cert_basis.sqlite`.
- **`cert_basis.sqlite` is the contract with the app.** The FARFETCHed Flask
  app lives in a separate repo and only reads this file.

Where things are documented:

- Overview, layout, commands: [README.md](README.md)
- JSON field-level contract, text format, resolution rules:
  [docs/DATA_FORMAT.md](docs/DATA_FORMAT.md)
- SQLite tables, contract version, build steps and report:
  [docs/SQLITE.md](docs/SQLITE.md)
- Schema versions and design rationale:
  [docs/SCHEMA_HISTORY.md](docs/SCHEMA_HISTORY.md)
- Open issues and the data-repo roadmap: [ISSUES.md](ISSUES.md) (index;
  items in `issues/`, one file per area). The app's
  roadmap is in the FARFETCHed repo.
- Design reviews, plans and session handovers: `reviews/`, created when one
  lands (git doesn't keep it once the last one is deleted)
- Scraping/parsing/staging machinery lives in [tools/](tools/). Treat it as a
  self-contained internal sub-repo with its own [tools/CLAUDE.md](tools/CLAUDE.md)
  and [tools/README.md](tools/README.md). When working on data ingestion,
  defer to those — don't restate their rules here. Pipeline handovers and
  dated records go in `tools/s00_docs/reviews/`.

**Plans, reviews and handovers are temporary.** Once one is completed, delete
it, in a dedicated commit (nothing else in that commit), so git history keeps
it. Before deleting, move anything still open into [ISSUES.md](ISSUES.md) and
fix links that point at the file. A file with steps or items still open stays.
Don't keep completed ones as records. Don't delete without the developer's
confirmation: list the candidates and write the `git rm` commands to a review
script, per the root CLAUDE.md.

**Read docs/DATA_FORMAT.md and docs/SQLITE.md before proposing schema or
format changes.** They are the field-level contract.

## Project Context

- Scale: one maintainer, low traffic, public read-only consumer.
- The data here is the point. Favour correctness and traceability over
  cleverness. Every transcribed version carries a `source_url` and, where
  known, a `publication_cite` for a reason.
- Prefer stdlib and hand-written code over dependencies.
- `build.py` is only the CLI. The build is the `certbuild/` package, one
  module per reason to change: see [Code map](#code-map).

## Tech Stack

- Python 3.12+
- `jsonschema` for validation
- stdlib `sqlite3` (no ORM)
- `uv` (deps), `ruff` (lint+format), `mypy` (types), `pytest` (tests)

## Repo Layout

See [README.md §Layout](README.md#layout). Summary:

```
FARfetched-data/
├── README.md                   Front page for people
├── ISSUES.md                   Index of open issues + roadmap
├── issues/                     One file per area (stable IDs); outstanding only
├── docs/                       The contract: DATA_FORMAT, SQLITE, SCHEMA_HISTORY
├── reviews/                    Temporary reviews/handovers (only while one is open)
├── schemas/                    JSON Schema files (Draft 2020-12)
├── data/                       Output of tools/ (never hand-edited)
│   ├── documents/{issuer}/{document}/{_document,provision}.json
│   └── aircraft/{manufacturer-slug}/{model-slug}.json
├── build.py                    The CLI (argparse + main)
├── certbuild/                  The build, one module per concern (Code map)
├── scripts/compare_builds.py   Old vs new build code on the same data/
├── tests/
├── tools/                      Internal sub-repo: ingestion scripts.
│                               See tools/CLAUDE.md and tools/README.md.
└── input/                      Local source copies, owned by tools (gitignored)
```

## Common Commands

```bash
# Setup
uv sync

# Build the SQLite artifact
uv run python build.py

# Validate without building (schema + text layout)
uv run python build.py --check

# Quality
uv run pytest -m "not slow"     # fast loop
uv run python scripts/compare_builds.py   # after any certbuild/ change
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

## Code map

To change something, edit the module, read the doc section, run the test
file. Each module's docstring says what it must not do.

| To change | Module (`certbuild/`) | Doc | Tests |
|---|---|---|---|
| SQLite tables, contract version | `ddl.py` | docs/SQLITE.md | `test_contract.py` |
| Issuers, categories (closed sets) | `lookups.py` + schema enum | docs/DATA_FORMAT.md | `test_validation.py` |
| Schema validation, loading, path checks | `sources.py` | docs/DATA_FORMAT.md | `test_validation.py`, `test_build_failures.py` |
| Label-line text, headings, labels | `text/paragraphs.py`, `text/labels.py` | DATA_FORMAT §Text format | `test_paragraphs.py` |
| Tables, inline markup, flat/plain text | `text/tables.py`, `text/markup.py`, `text/flat.py` | DATA_FORMAT §Tables, §Inline markup | `test_paragraphs.py` |
| Provision/version inserts, aliases, deletions, number clashes | `provisions.py` | DATA_FORMAT, SQLITE §Build | `test_easa_alias.py`, `test_deletion.py`, `test_provision_key.py` |
| Cert-basis resolution rules (pure, no sqlite3) | `resolve.py` | DATA_FORMAT §Resolution rules | `test_resolve.py`, then `test_resolution.py` |
| Aircraft, TCDS, ref inserts, paragraph-ref checks | `aircraft.py` | SQLITE | `test_resolution.py` |
| ELOS/SC/exemption citations: resolving, version to link, report counts | `citations.py` | DATA_FORMAT §Citations, SQLITE §Citations | `test_citations.py` |
| Similarity | `similarity.py` | SQLITE §Similarity | `test_similarity.py` |
| Report, git state | `report.py` | SQLITE §Build | `test_build_failures.py` |
| Build steps, `--check`, atomic output | `pipeline.py` | SQLITE §Build | `test_build_failures.py` |
| Error reporting | `errors.py` (states the rule) | | `test_build_failures.py` |

- **`certbuild.text` is a public API.** `tools/` imports the text format from
  it (its `__all__`), plus `certbuild.keys.sort_key` and
  `certbuild.pipeline.build`. `tests/test_tools_api.py` pins those names and
  fails if tools imports anything else. Rename one only together with
  tools/.
- **Errors: collect within a stage, raise between stages** (errors.py). A new
  check returns `list[str]` and gets one `_raise_if(...)` line in
  `pipeline.py`. A pre-insert check goes in `load_checked`, which `--check`
  runs too.
- **Any change to `certbuild/` runs `uv run python scripts/compare_builds.py`.**
  It builds the current `data/` with the committed code and the working tree
  and diffs the DBs. A refactor must print `identical`. A behaviour change
  must show only the rows it means to change. It checks code, not data, so
  data changes don't affect it.
- Keep modules under ~350 lines. ruff fails any function over complexity 10
  (`pyproject.toml`): split it, don't `noqa` it. mypy is strict for
  `certbuild/`.

## Reproducible is not correct

These are two separate claims. Never let evidence for one stand in for the other.

- **Reproducible** means the pipeline regenerates the same output offline.
- **Correct** means the output matches the source.

The source is the only truth, and working out what it says and intends can take
careful reading. Everything else is evidence that may be wrong: `data/`, the
staged tree, pipeline code, override rows, tests, docs, issue text and earlier
reviews. Published data is probably good, but it has bugs.

- A rebuild that matches `data/` can be the same bug twice. It proves nothing
  about accuracy, and neither do a clean build, passing tests or `identical` from
  `compare_stages` or `compare_builds`.
- When a rebuild and `data/` differ, read the source to decide which is right.
  Never change the pipeline just to match `data/`.
- If the source shows a test or baseline encodes an error, change it, with the
  evidence in the commit.
- Don't call anything verified or reviewed unless it was actually read against
  the source.

## Build conventions

- Stdlib + `jsonschema` (and its bundled `referencing`).
- Fail loud on any schema mismatch, any unresolvable reference, any
  duplicate key. The build is the last line of defence — don't paper over
  bad data.
- Atomic output: write `cert_basis.sqlite.new`, then `os.replace()`.
- `PRAGMA foreign_keys = ON` while building. The shipped DB stays in the
  default `journal_mode = DELETE`: a single file that read-only consumers can
  open without `-wal`/`-shm` sidecars. Don't switch it to WAL.
- `STRICT` tables, `TEXT` dates with `CHECK (date(x) IS x)` (not `=`: a NULL
  CHECK passes), and integrity enforced in the DDL (composite FKs), not only
  in Python.
- `PRAGMA user_version` is the contract version (`SCHEMA_VERSION`). Bump it on
  every change to the SQLite contract.
- Parameterised SQL. No string concatenation.
- Emit `cert_basis_report.json` with row counts for every table. Zero
  unresolved references is a success criterion, not a nice-to-have.

## Data conventions

The field-level contract is in [docs/DATA_FORMAT.md](docs/DATA_FORMAT.md).
Rules that matter at the repo level:

- **Provision `text` is label-line text** (docs/DATA_FORMAT.md §Text format): one
  paragraph per line, depth from the labels, indentation checked relatively.
  A single-line text is flat. `build.py` parses and checks it; it never
  guesses a layout. The tools produce it, and layout may only add line breaks
  and indentation, never change words.
- **ISO `YYYY-MM-DD` dates everywhere.** Display formatting is the app's
  job, not this repo's.
- **No `status` column on versions.** Every provision version must have
  `text`. An aircraft that references an untranscribed revision can't be
  added until it is transcribed. This is deliberate — see
  docs/SCHEMA_HISTORY.md.
- **`text: "TEXT MISSING"` flags a known gap.** When an extractor knows
  a (provision, revision) pair *should* exist (the CSV/manifest says so)
  but the source is corrupted, OCR'd badly, or otherwise unreadable, it
  emits the record with the best-known title (from TOC, CSV, or other
  manifest) and the literal body `TEXT MISSING`. This keeps the DB row
  set consistent with the manifest and surfaces the gap loudly to a
  human reviewer rather than silently dropping it. Search for
  `TEXT MISSING` (or `WHERE text_missing` in the DB) to find pending
  recovery work. Don't use this marker for anything else.
- **`raw_reference` is sacred.** Never rewrite or normalise it. It's the
  unmodified TCDS text, kept for traceability against the original PDF.
- **`data/` is built from source.** Only `tools/` writes to `data/`, and only
  via its promotion step. Every file comes out of a pipeline run from local
  source copies plus `tools/overrides/`. No hand edits, and no `manual`
  provenance (the schema rejects it). A correction is an override row with
  evidence, or an extractor fix. The mechanics live in
  [tools/CLAUDE.md](tools/CLAUDE.md).
- **Document file paths are flat:**
  `data/documents/{issuer}/{document}/{provision}.json`, with the revision
  list in `_document.json` alongside. Grouping (subpart) and the CFR title
  are fields inside the files, not directories. Don't introduce additional
  path segments. The build checks every path against the file's contents.
- **`additionalProperties: false`** in every JSON Schema. If you need a new
  field, update the schema, the docs (`docs/`), and the build.

## Testing

- `pytest`. Build tests stage small synthetic data trees in `tmp_path` and
  exercise each cert-basis resolution rule and each fail-loud check; invalid
  schema inputs live in `tests/fixtures/`. Records are built with
  `tests/factories.py`, the only copy of each JSON shape: a new required
  field goes there, not into each test file. They live only here;
  `tools/s99_tests/e2e/` just checks that a staged tree builds.
  `uv run pytest` runs `tests/` and `tools/s99_tests/`.
- Smoke test (`test_real_data.py`): run the build against the real `data/`,
  open the resulting SQLite, and assert specific known queries return the
  expected rows (e.g. `SELECT * FROM latest_versions WHERE ...`).
- Tests that read or build the real `data/` are marked `slow` (any test
  using the `real_db` fixture is, automatically).
  `uv run pytest -m "not slow"` is the seconds-long edit loop. Run the full
  suite before committing.
- Don't chase 100% coverage. Test behaviour.

## Do / Don't

**Do:**
- Preserve `raw_reference` exactly as it appears on the TCDS.
- Include `source_url` on every version, and `publication_cite` whenever it
  is known.
- Add a schema change, a `docs/` update (and a `docs/SCHEMA_HISTORY.md` row
  for a contract change), and a test in the same commit.
- Fail the build on any unresolved reference.

**Don't:**
- Don't git add, git commit or git push. That will be done manually separately
  by the developer.
- Don't create or work on a git branch unless the developer explicitly says
  to. Work on `main` in both this repo and `tools/`.
- Don't introduce an ORM.
- Don't add application logic here. App code lives in FARFETCHed.
- Don't commit `cert_basis.sqlite` or `cert_basis_report.json` — they are
  build outputs.
- Don't mutate JSON files to work around a build failure. Fix the data or
  fix the schema.
- Don't invent fields. If something new is needed, update schema, `docs/`,
  and build together.

## When In Doubt

- The source data (e.g. FAA, EASA)) is the authority. If the JSON disagrees with
  the source (pdf, websites, etc. depending on source), the JSON is wrong.
- If a TCDS reference can't be resolved cleanly, record it verbatim in
  `raw_reference` with `references: []` and surface it in the build report
  rather than guessing.
- Ask before large schema changes. Every field is a downstream commitment.
- If there is issues with data (poor quality, edge cases, items needing additional work to script properly) write it to the right area file under issues/ (see ISSUES.md) for future
  review. Delete an issue once it is done, and its file once empty
