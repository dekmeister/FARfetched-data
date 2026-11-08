# FARfetched-data

The dataset behind [FARFETCHed](https://github.com/DEK-DEBIAN/FARFETCHed): it
records which regulations, at which amendment level, make up the
certification basis of each type-certificated aircraft, along with the text
of those regulations.

## How it fits together

```
upstream sources ──► tools/ ──► data/ ──► build.py ──► cert_basis.sqlite ──► FARFETCHed app
(FAA DRS, eCFR,      extract,   JSON,     validate,    one read-only file,
 EASA PDFs, CAR      emit,      built     resolve,     the contract with
 scans, TCDS PDFs)   promote    from      compile      the app
                                source
```

- **[tools/](tools/)** is an internal sub-repo with its own docs. It is the
  only thing that writes `data/`, and it does so through a reviewed promote
  step, from local source copies plus override files. Nobody edits `data/`
  by hand.
- **`data/`** is JSON: one file per document, per provision, and per
  aircraft model.
- **[build.py](build.py)** is the last line of defence. It validates every
  file, resolves every cert-basis reference, fails loudly on anything
  inconsistent, and writes `cert_basis.sqlite` plus `cert_basis_report.json`.
- **`cert_basis.sqlite`** is what the app reads. It isn't checked in.

## The model

Everything citable is a **document** with its own revision history:

| Concept   | 14 CFR      | CAR 3         | EASA CS     |
|-----------|-------------|---------------|-------------|
| Issuer    | FAA         | CAA (now FAA) | EASA        |
| Document  | 14 CFR 23   | CAR 3         | CS-23       |
| Revision  | Amdt 23-62  | CAR3-0        | CS23-5      |
| Provision | §23.1309    | §3.735        | CS 23.2000  |

Advisory circulars, special conditions, ELOS findings, exemptions and
handbooks use the same four layers, so a cert-basis reference always points
at a provision version. An aircraft's cert basis is kept per TCDS (one model can carry the State
of Design's TCDS and a validation of it, each with its own categories), line by
line: the verbatim line, what it means (references), and the provision
versions it resolves to.

## Docs

| Doc | For | Contents |
|---|---|---|
| [docs/DATA_FORMAT.md](docs/DATA_FORMAT.md) | tools and data authors | The JSON contract: every field, the label-line text format, cert-basis resolution rules |
| [docs/SQLITE.md](docs/SQLITE.md) | the app | Tables, contract version, similarity, what `build.py` checks and reports |
| [docs/SCHEMA_HISTORY.md](docs/SCHEMA_HISTORY.md) | anyone changing the contract | Schema versions v1–v6 and the reasons behind them |
| [ISSUES.md](ISSUES.md) | maintainers | Index of outstanding data and pipeline issues and the roadmap; items in [issues/](issues/), one file per area |
| [reviews/](reviews/) | maintainers | Design reviews and session handovers |
| [tools/README.md](tools/README.md) | pipeline work | How sources become `data/` |
| [CLAUDE.md](CLAUDE.md) | AI assistants | Repo rules |

## Layout

```
FARfetched-data/
├── README.md            this page
├── ISSUES.md            index of outstanding issues and roadmap
├── issues/              one file of issues per area
├── docs/                the contract (data format, SQLite, history)
├── reviews/             design reviews and handovers
├── schemas/             JSON Schemas (Draft 2020-12)
├── data/
│   ├── documents/{issuer}/{document}/_document.json   revision list
│   ├── documents/{issuer}/{document}/{provision}.json
│   └── aircraft/{manufacturer-slug}/{model-slug}.json
├── build.py             JSON → SQLite compiler and checker (the CLI)
├── certbuild/           the build itself, one module per concern
├── scripts/             compare_builds.py: old vs new build code on data/
├── tests/               build tests (pytest)
├── tools/               ingestion sub-repo (own git repo; gitignored here)
└── input/               local source copies, owned by tools (gitignored)
```

## Common commands

```bash
uv sync                                   # install
uv run python build.py --check            # validate data/ (schema, paths, text layout)
uv run python build.py                    # build cert_basis.sqlite + report
uv run pytest                             # tests/ and tools/s99_tests/
uv run pytest -m "not slow"               # the same without the real data/ (seconds)
uv run ruff check . && uv run mypy .      # lint and types
```

## Adding data

Data comes in only through the tools pipeline. See
[tools/README.md](tools/README.md) and the per-source guides in
`tools/s00_docs/`.

1. Refresh the local source copies (only when needed: downloading isn't
   building).
2. Run the pipeline's extract and emit steps. Emit writes a staged tree under
   `tools/out/staged/`. Aircraft: the TCDS parsers write per-TCDS fragments
   and `tools.s02_emit.aircraft.assemble` stages them, joining an FAA and an
   EASA TCDS of the same type design only through a reviewed link row.
3. Review the diff with `python -m tools.s03_promote.promote --dry-run`, then
   promote.
4. Run `uv run python build.py`. It must finish with zero unresolved
   references.

A wrong value is fixed with an override row (with evidence) in
`tools/overrides/` or with an extractor fix, never by editing `data/`. If a
TCDS cites a revision or provision that isn't in `data/` yet, ingest that
document first. Problems that need a human go in [ISSUES.md](ISSUES.md).

## License

See [LICENSE](LICENSE).
