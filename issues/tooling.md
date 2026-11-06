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
