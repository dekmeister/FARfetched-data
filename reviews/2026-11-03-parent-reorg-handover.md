# Handover: parent-repo reorganisation (2026-11-03)

This brings the parent repo's docs into line with the `tools/` reorganisation
([tools/s00_docs/reviews/2026-11-02-tools-reorg-handover.md](../tools/s00_docs/reviews/2026-11-02-tools-reorg-handover.md)).
Scope was the parent repo only. In tools/, only links and a few dated
records changed. Nothing was promoted into `data/`. The FAA Part 23 re-fetch
(its own handover) is untouched apart from one pointer.

## Goal

1. Make the layout and docs match real use:
   - tools/ produces `data/`
   - `build.py` checks and compiles it
   - `cert_basis.sqlite` is the contract with the app
2. Split README.md: keep the contract easy to find and move the history out.
3. Sort ISSUES.md (still one file), plan.md and reviews/.
4. Review build.py and tests/ against CLAUDE.md, and propose before changing
   code.
5. Flag anything that belongs on the other side of the parent/tools line.

## Decisions (user, 2026-11-03)

- The other session's schema-v5 work was finished. It was committed during
  this session as `77bfeba` (build.py, plan.md, tests). Its README v5 text
  was never committed; it lives on, word for word, in `docs/SQLITE.md`.
- README is a light front page for people, with detail in `docs/` sub-docs.
- plan.md is deleted. Its data-repo items went to ISSUES.md `ROADMAP-`, and
  the app owns the rest in its own `plan.md`.
- ISSUES.md is organised by area with stable prefixed IDs. Narratives moved
  to `tools/s00_docs/reviews/`.

## What changed

**Parent repo (uncommitted):**

| File | Change |
|---|---|
| `README.md` | Rewritten as a ~110-line front page: the tools → data → build → SQLite → app picture, the model, a docs index, layout, commands, and how to add data via the pipeline. The old "create `data/documents/…json` by hand" text is gone; it contradicted build-from-source. |
| `docs/DATA_FORMAT.md` | New. Old README §JSON formats, §Text format and §Resolution rules, moved word for word. History remarks ("replaces the old `title_number`") went to SCHEMA_HISTORY. |
| `docs/SQLITE.md` | New. Old README §Consuming (now first), §SQLite schema, §Similarity, §latest_versions and §Build pipeline. **Corrected:** the build steps listed similarity after aircraft, but `build()` runs `_insert_similarity` before `_insert_aircraft`. |
| `docs/SCHEMA_HISTORY.md` | New. v1–v5 table with commits, the v1 renames, and standing design decisions (no status column, per-version actions, flat paths, per-line resolution, DELETE journal mode, build from source, computed similarity). |
| `ISSUES.md` | Restructured; see the ID map below. |
| `CLAUDE.md` | The three roles, a "where things are documented" list, the new layout block, `--check` documented as implemented, and README/plan.md references pointed at `docs/`. |
| `build.py` | **Comments only:** three `README §Text format` → `docs/DATA_FORMAT.md §Text format`. The §Similarity ones were already changed in `77bfeba`. |
| `.gitignore` | 174-line template trimmed to the 35 lines that apply, with comments. **It no longer ignores `uv.lock`**, which now shows as untracked: commit it for reproducible builds, or put the line back. The old file is at `/tmp/claude-1000/-mnt-server-Projects-2026-FARfetched-data/b0ef0e77-535c-4220-9d4a-2bd3d620bf94/scratchpad/gitignore.before`. |
| `reviews/2026-10-31-db-schema/README.md` | "Contract as built" link → `docs/`. The findings files still cite plan.md/README as evidence at `20d6289`; left as written. |

**tools/ (uncommitted, separate repo):**

- New dated records in `s00_docs/reviews/`. Each is the old ISSUES.md text,
  word for word, under a provenance note:
  - `2026-11-01-tcds-corpus-run.md`
  - `2026-11-01-easa-cs-closeout.md`
  - `2026-11-01-paragraph-structure-migration.md`
- Link fixes:
  - `s00_docs/STRUCTURE.md`: README §Text format → docs/DATA_FORMAT.md, and
    ISSUES pointers → TEXT-
  - `s00_docs/EASA_CS.md`
  - `s00_common/structure.py` (docstring)
  - `s99_tests/emit/faa/tcds/test_stages.py` (docstring)
  - `s00_docs/reviews/2026-11-03-faa23-refetch-handover.md`: one pointer to
    the ISSUES section that no longer exists → item IDs

**To delete:** run
`/tmp/claude-1000/-mnt-server-Projects-2026-FARfetched-data/b0ef0e77-535c-4220-9d4a-2bd3d620bf94/scratchpad/cleanup_parent.sh`.
It is a dry run by default; `--run` removes. It removes:

- `plan.md`
- `TODO.md` (gitignored, so this is the only copy; every item is in ISSUES.md)
- two zero-byte `.xdp-cert_basis.sqlite-*` files

## ISSUES.md ID map (old → new)

- **Authority-only "Data" items:**
  - #1 → FAA-1
  - #2 → FAA-2 (23-43 closed)
  - #3 → FAA-4
  - #4 → FAA-5
  - #5 → FAA-6
  - #6 → FAA-7
- **"Risks" items:**
  - #7 → PROC-1
  - #8 → PROC-2
  - #9 → PROC-3
  - #10 → PROC-4
  - #11 → Closed
  - #12 → PROC-5
  - #13 → FAA-11
  - #14 → PROC-6
  - #15 → Closed
- **TCDS items:**
  - #16–24 → Closed
  - #25 → TCDS-9 (rest closed)
  - #26 → TCDS-1
  - #27 → TCDS-2 (reframed: no correction path for aircraft files under v4)
  - #28 → FAA-8
  - #29 → TCDS-3
  - #30 → TCDS-4
  - #31 → TCDS-5
  - #32 → TCDS-6
  - #33 → PROC-7
- **EASA ingestion items:**
  - #1 → EASA-1
  - #2 → EASA-2
  - #3 → EASA-3
  - #4, #10–13 → Closed
  - #5 → EASA-4
  - #6 → EASA-5
  - #7 → EASA-6
  - #8 → TEXT-11
  - #9 → EASA-7
- **EASA close-out "Still open" items:**
  - #1 → EASA-8 ("transcribe by hand" no longer possible: fix the column
    order)
  - #2 → EASA-9
  - #3 → EASA-10
  - #4 → EASA-11
  - #5 → EASA-2/4
  - #6 → EASA-12
  - "reviewed and kept" 25.807(k) → EASA-13
  - improvements → EASA-6, EASA-14, EASA-15
- **Paragraph items:**
  - #1–5 → TEXT-1–5
  - #6 → TEXT-6 + CAR-1
  - #7 → TEXT-7
  - #8 → TEXT-8 + CAR-2
  - #9 → TEXT-9
  - #10 → TEXT-10
  - #11 → Closed
- **FAA extraction-fix open data items** → FAA-3, FAA-6, FAA-9, FAA-10; the
  overrides check → FAA-2.
- **EASA TCDS state** → ETCDS-1..4 and ROADMAP-9.
- **plan.md and TODO.md** → ROADMAP-1..9, TCDS-7, TCDS-8, PROC-8, FAA-12.
- **New:**
  - BUILD-1..6: this review
  - PROC-9: stale `input/` files

Items re-checked against code/data today:

- FAA-8: files still missing
- EASA-8: still TEXT MISSING
- PROC-4: `emit.py` prefix check
- PROC-5: no DRS guard in conftest
- PROC-7: `WROTE` still printed in dry run
- FAA-3: no `drs_date` overrides for those designators
- TCDS-7: 525C special conditions now split; 525B's ELOS line not split

Items marked "not re-checked" are carried as they were.

## Checks at hand-over

- `uv run pytest`: **716 passed, 4 failed**. `tests/` alone is **162 passed,
  4 failed**, the same as before the reorg. The 4 failures are BUILD-1.
- ruff check/format (build.py, tests, tools) and mypy (build.py, tests) are
  clean.
- `build.py --check` is OK. A full build into the scratchpad is OK: schema
  v5, 95 models, 1,064 entries, 33,700 resolved, 27,490 similarity rows.
- All relative links and anchors in README, ISSUES, CLAUDE, docs/*, the
  schema review README and the edited tools docs resolve (scripted check).
  The only exception was this file, before it was written.

## Review findings: build.py and tests (proposals, not implemented)

These are recorded as BUILD-2..6 in ISSUES.md.

**build.py against the CLAUDE.md conventions.** These all hold:

- single file, stdlib + jsonschema
- fails loud
- STRICT tables, `CHECK (date(x) IS x)`, composite FKs
- `foreign_keys = ON` and DELETE journal mode (tested)
- `.new` + `os.replace`
- parameterised SQL (the only f-strings are `PRAGMA user_version`, which
  can't be parameterised, and table names from `sqlite_master`)
- `SCHEMA_VERSION` 5, consistent with the docs and the tests

Gaps:

1. The report is written non-atomically, after the DB swap (BUILD-3).
2. `--check` skips the path/identity check (BUILD-4).
3. `git_sha` doesn't reveal a dirty tree (BUILD-5). Fixing it changes the
   contract (v6), so **ask before doing it**.
4. Size: 1,908 lines in three cohesive parts:
   - the text-format parser, which tools imports (`parse_paragraphs`,
     `flatten_text`)
   - similarity
   - build

   I recommend keeping it single-file, as the convention says. Revisit only
   if what tools imports keeps growing; that would be the natural first
   split.

**tests/:** the synthetic `tmp_path` and fail-loud tests test behaviour well.
The real-data smoke tests assert exact row lists and break on every parser
re-run (BUILD-2). The real `data/` is built twice per run (BUILD-6).

## Parent ↔ tools placement

- Moved to tools: the three dated narratives above.
- `input/` stays at the parent root. tools owns it (`paths.py`), and keeping
  it out of `tools/out/` is what makes `rm -rf tools/out` safe. It's now
  documented in the README and CLAUDE.md layout as tools-owned.
- `.env` (GOVINFO_API_KEY) is used only by tools. Documented; not moved.
- tools imports `build` (`structure.py`, `overrides.py`). That direction is
  right (tools depends on the contract), so no change.
- Nothing in tools belongs in the parent.

## Left for the user

1. Run the cleanup script, then review and commit both repos. The parent has
   `docs/` (new), README, ISSUES, CLAUDE, build.py comments, .gitignore, the
   review README, and the plan.md deletion. tools has the three records and
   the link fixes.
2. Decide `uv.lock`: commit it, or restore the ignore.
3. **BUILD-1:** the 70 untracked aircraft files in `data/aircraft/`. Keep
   them (commit them and update the tests) or drop them.
4. Decide on proposals BUILD-2..6. BUILD-5 is a contract change.
5. PROC-9: `input/parsed/` and `input/regs.csv.work`.
6. tools/ shows `s00_docs/reviews/2026-11-01-easa-tcds-download.md` as
   deleted (`D`). This session did not delete it; check it was intended.
