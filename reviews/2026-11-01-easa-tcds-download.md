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

## Not done yet: next session

1. **First real catalogue run did not finish.** It was killed at about 250 of
   623 detail pages. The detail cache is in `tools/out/cache/easa_tcds/`, so a
   re-run continues cheaply:
   `uv run python -m tools.aircraft.easa_tcds_catalogue`
   (Detail pages are refetched when there is no catalogue row yet. Because the
   first run never wrote the catalogue, the re-run refetches all 623, about
   16 min. Optional improvement: skip refetch when the cache is fresh and no
   catalogue exists.)
2. Check `tools/out/reports/easa_tcds_catalogue_report.tsv`
   (no_downloads, no_issue_number, main_document_guessed). Sum the `length`
   column to estimate the download size.
3. `--download --dry-run`, then the full `--download` in tmux. Check
   `warn_no_text` / `warn_code_mismatch` in
   `tools/out/reports/easa_tcds_download_report.tsv`. Add anything odd to
   ISSUES.md.
4. Not yet run against the full suite: ruff/mypy are clean on the new files.
   The full pytest run has 1 failure and 15 errors. These come from the
   existing uncommitted build.py / CAR-3 label-line work in data/, not from
   this tool.
5. Possible follow-ups: download the TCDS for Noise (TCDSN), which is only
   recorded in the `noise_*` columns for now; a coverage/parse stage for EASA
   TCDS.

Note: both repos were on branch `easa-cs` (not `main`) during this session.
I did not switch branches.
