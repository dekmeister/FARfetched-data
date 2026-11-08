# Tooling and process (PROC-)

Pipeline machinery in `tools/` and the local `input/` copies.
[Index](../ISSUES.md)

### PROC-1. The DRS amendment lookup cache never expires

`input/cache/drs/far_amendment/` caches hits and misses for good. A gap that
later gets a DRS document stays "none" until `--force`.

**To close:** a time limit on cached misses.

### PROC-2. The authority-only verdict trusts DRS listing fields

It uses `Section == "Sec. 0.0"` plus the title, not the document text. A
`Sec. 0.0` document with an unexpected title is `unrecognised`, not
declared.

**To close:** check the document text, or accept and review `unrecognised`
rows by hand.

### PROC-3. The FR cite lookup for authority-only revisions is a window heuristic

−30/+7 days around the DRS date; the docket must name the designator. Zero or
several matches give no cite and an `authority_only_no_fr_cite` row. 27-39
and 29-46 have no FR `effective_on`, and DRS misprints their docket
(`FAA-19998-4390`). See also FAA-16.

**To close:** override rows for the misses, or a better lookup.

### PROC-4. FAA emit assumes designator prefix = part

`s02_emit/faa/regs/emit.py`, `startswith(f"{part}-")`. Fine for FAA, wrong if
reused for CAR or EASA.

**To close:** generalise it if the code is ever shared.

### PROC-5. Nothing stops a test from calling the real DRS

Tests that call `manifest.main` must pass `--skip-drs` or patch
`far_amendment_documents`.

**To close:** a guard in `tools/s99_tests/conftest.py` that fails on a real
request.

### PROC-6. The `network calls: N` counter undercounts DRS lookups

One per lookup, however many pages it took.

**To close:** count requests, not lookups.

### PROC-7. `promote --dry-run` misreports and can block

It prints `WROTE` for a conflict it would accept, although nothing is written
(`s03_promote/promote.py`, conflict loop). It also asks `overwrite …? [y/N]`
per conflict and auto-skips only when stdin is closed, so with an open non-tty
stdin (a background job) it blocks forever. Workaround: `< /dev/null`.

**To close:** a dry run should neither print `WROTE` nor prompt.

### PROC-8. FAA extract is serial

A `ThreadPoolExecutor` with about 10 workers would give roughly 5–10× on
1,000+ row batches. The DRS JWT cookie needs a lock around refresh, or
per-worker sessions.

**To close:** implement it if batch time matters.

### PROC-9. Stale inputs in `input/`

`input/parsed/` (old TCDS output, 2026-10-31) and `input/regs.csv.work`
(identical to `regs.csv`). Both untracked.

**To close:** the maintainer decides whether to remove them.

### PROC-10. `input/` is not in git and has no backup

It holds the DRS raw copies (`input/cache/drs/far_doc/`), the govinfo FR
scans used as override evidence (`input/cache/fr/`), OCR sidecars and the EASA
TCDS (ETCDS-1). `rm -rf tools/out` is safe; losing `input/` is not (DRS pages
can change or go).

**To close:** a backup of `input/`.

### PROC-12. Complex functions still in tools

The big files are split and the worst functions untangled (the build's
method: `compare_stages`, move-only commits, then differential tests of old
vs new on real inputs). These are still over the ratchet in `tools/ruff.toml`,
fixed when next touched:

- `s00_common/continuity.py`: walk
- `s00_common/http.py`: get
- `s01_extract/dod/hdbk/extract.py`: headings
- `s01_extract/easa/cs/discover.py`: catalogue_row, reconcile_dates
- `s01_extract/easa/cs/manifest.py`: build, parse_preamble
- `s01_extract/faa/regs/extract.py`: extract_row, run_manifest
- `s01_extract/faa/regs/manifest_ecfr.py`: flag_suspect_designators
- `s01_extract/faa/regs/overrides.py`: parse_rows
- `s01_extract/faa/regs/worklist.py`: attention_rows
- `s01_extract/nato/usar/extract.py`: parse
- `s02_emit/aircraft/assemble.py`: assemble
- `s02_emit/car/emit.py`: emit
- `s02_emit/easa/cs/emit.py`: walk, emit
- `s02_emit/easa/tcds/fields.py`: split_fields
- `s02_emit/easa/tcds/header.py`: parse_header
- `s02_emit/easa/tcds/items.py`: split_items
- `s02_emit/easa/tcds/parse.py`: parse_tcds_text, main
- `s02_emit/faa/tcds/coverage.py`: summarise
- `s02_emit/faa/tcds/classify.py`: classify
- `s02_emit/faa/tcds/header.py`: parse_header
- `s02_emit/faa/tcds/outline.py`: tokenize_paren
- `s02_emit/faa/tcds/parse.py`: model_lines, parse_tcds_text, main
- `s02_emit/faa/tcds/prose.py`: tokenize_prose
- `s02_emit/faa/tcds/sections.py`: segment_sections
- `s02_emit/faa/tcds/segments.py`: split_segments
- `s03_promote/promote.py`: main

**To close:** split each with the same method, and delete its `ruff.toml`
entry; the list only shrinks.

Left alone on purpose, not part of the above: `tools/s00_common/structure.py`
(903 lines, functions untangled, file kept whole), typing the ref and version
dicts (JSON payloads the schema already validates; a TypedDict migration touches
every emitter), lifting the duplicate TCDS catalogue helpers, merging the
DoD/NATO emitters (too small, or already diverged).

### PROC-13. Nothing shows that `data/` can be rebuilt from source

The rule is that `data/` is local sources plus overrides through the pipeline,
but no command or test proves it. On 2026-11-08 `promote --dry-run` reported
295 document files differing from `tools/out/staged/`: the staged tree is older
than `data/` (no inline markup in 761 texts, and 5 CS-25 files still have the
versions removed on 2026-11-07). Aircraft were identical. `build_info` records
the data repo's commit but not the tools commit that produced the data.

**To close:** one offline command that runs every pipeline, a check that the
staged tree equals `data/`, and the tools commit recorded at promotion. Depends
on TCDS-11.

### PROC-14. Nothing detects new upstream revisions

Refreshing is manual and there is no record of when each source was last
checked. The build has no "data current to" date, so a reader can't tell a
source with no newer amendment from one nobody has checked. TCDS reissues have
the same problem (ETCDS-1).

**To close:** a scheduled, report-only discover run listing new amendments and
TCDS issues, and a per-document checked-on date in the report.

### PROC-15. Rights to redistribute source text have not been assessed

The repo is public and the site is live. `LICENSE` is MIT with no carve-out for
`data/`, which holds EASA and NATO text. NATO-1 notes that some STANAG 4671
editions aren't freely available, and Ed. 1 came from an archive copy. Nothing
records the reuse terms for any issuer. This is a gap in what was checked, not
a finding of infringement.

**To close:** record each issuer's reuse terms, and give `data/` its own licence
and attribution, separate from the code. Get advice if the terms are unclear.

### PROC-16. Versions without a `source_url`

All 936 CAR versions have no `source_url` (`s02_emit/car/emit.py` sets `None`),
and 45 live FAA versions have none (2026-11-07), against CLAUDE.md's "include
`source_url` on every version". Part 36 has the most, at 13.

**To close:** a stable reference for each CAR scan, and a look at the 45 FAA
rows. Then decide whether the build should enforce it.

### PROC-17. No independent measure of text accuracy

Layout checks prove the words weren't changed by layout, not that they match
the source. No test or report samples text against the PDFs or DRS, so no
per-issuer error rate exists, least of all for the 936 OCR versions. Readers
are finding errors by hand (GitHub #3, #18).

**To close:** a repeatable stratified sample per issuer and provenance, reviewed
against the source, with the error rate recorded and re-measured after each
major extraction change.
