# EASA TCDS downloader — handover (2026-11-01)

Goal (user): a tool to download every TCDS from
https://www.easa.europa.eu/en/document-library/type-certificates into a folder
for later analysis, re-runnable to pick up updates. Modelled on
`tools/aircraft/faa_tcds_catalogue.py`.

## Done (committed in tools/)

- `tools/aircraft/easa_tcds_catalogue.py`: catalogue mode (listing +
  detail pages → `tools/out/work/easa_tcds_catalogue.tsv`, one row per
  TCDS file, incremental merge) and `--download` mode
  (`input/TCDS/EASA/{code}_Issue{N}.pdf`, annexes in `input/TCDS/EASA/other/`).
- `tools/common/easa.py`: HTML helpers lifted out of
  `tools/regulations/easa/discover.py`, which now imports them (its tests pass).
- Tests: `tools/tests/aircraft/test_easa_tcds_catalogue.py` + fixtures in
  `tools/tests/fixtures/easa_tcds/`. 37/37 pass, along with the EASA discover tests.
- Docs: `tools/docs/EASA_TCDS.md` (site quirks), and the `tools/README.md` section.

Site facts behind the design: 623 TCDS; only the current issue is
published (the history builds up locally over re-runs); the listing must be
sorted by title (the default sort drops and duplicates rows); 30 listing rows
have no file link, so detail pages are the source of the downloads.

## Closed out (2026-11-02)

1. Catalogue run: done, in one uninterrupted pass (~35 min including the
   623 detail refetches; the "skip refetch when cache is fresh" improvement was
   not made, as it only saves time on the first run). 623 TCDS, 679 rows,
   `tools/out/work/easa_tcds_catalogue.tsv`.
2. Catalogue report: 29 TCDS with no downloads, 15 no_issue_number (a subset of
   the 29), 0 guessed main documents. Download size 344 MB estimated, 330 MB
   actual.
3. `--download --dry-run` then `--download`: 650 files, ok 644, warn_no_text 4,
   warn_code_mismatch 2. Findings are in ISSUES.md §EASA TCDS download.
4. Full pytest: the 15 errors are gone; 4 real-data e2e failures remain
   (uncommitted `data/aircraft/` work, not this tool). ruff/mypy clean.
5. Branch note was stale: both repos are on `main`.

OCR of the 4 scanned PDFs: done 2026-11-02 (see ISSUES.md).

Still open (not blocking): Noise TCDS (TCDSN) download; an EASA TCDS parse/coverage stage; periodic re-runs to build issue
history. Re-run: `uv run python -m tools.aircraft.easa_tcds_catalogue` then
`... --download`.

Uncommitted: the `reviews/` note, ISSUES.md, and downloaded PDFs under
`input/` are for the developer to review and commit.
