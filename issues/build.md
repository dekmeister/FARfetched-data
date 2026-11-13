# Build and contract (BUILD-)

The build (`build.py`, `certbuild/`) and the SQLite contract
([docs/SQLITE.md](../docs/SQLITE.md)).
[Index](../ISSUES.md)

### BUILD-3. DB and report are replaced in two steps

The build writes both `.new` files in full before replacing either, but the
two `os.replace()` calls are separate, so a crash between them can pair a new
DB with an old report.

**To close:** accept it (low risk), or check the pairing at read time (e.g.
the report records the DB's `build_info`).

### BUILD-8. Aircraft model identity is `(manufacturer, model_designation)`

A name used as a key, the smell schema v7 fixed for provisions. A
manufacturer rename or a re-designated model splits one model's history, and
the build matches on the strings.

The app slugifies `model_designation` and scans a TCDS's models for a match,
while `tools/` names the file with its own slug. They agree for all 325 files
(2026-11-11), so this is the same risk seen from the app side.

**To close:** decide on a stable model key, like `provisions.key`.

### BUILD-10. Parsed JSON is untyped `dict` in the build

`Source.doc` is `JsonObject` (`dict[str, Any]`), and versions flow through
`provisions._resolve_alias_versions` as merged dicts. Schema validation
guarantees the shape, so this isn't a bug, but a mistyped key is a runtime
`KeyError` mypy can't catch, against CLAUDE.md's "dataclasses, not dicts".
Deferred from the 2026-11 refactor as the largest change with the least
payoff.

**To close:** after validation, convert each file once into frozen
dataclasses (at least `VersionRec` and `RefRec`, where the dict merging
lives), with a test that each dataclass's fields equal its schema's
`properties`.

### BUILD-11. Build time

The real build takes ~44 s, ~34 s of it similarity scoring in pure Python,
and `uv run pytest` builds the real data twice: the `real_db` fixture, and
`tools/s99_tests/extract/faa/regs/test_extract.py`'s eCFR-marker test (both
`slow`). Lossless options not done: score each pair once and mirror it
(changes float summation order, so check with `scripts/compare_builds.py`
first); cache the similarity rows keyed by a hash of the sources, constants
and `certbuild/similarity.py`. Lowering `SIMILARITY_MAX_DF` is faster but
changes shipped rows (a data decision).

**To close:** decide if the time hurts enough to take one of these.

### BUILD-12. "Zero unresolved references" does not measure basis coverage

The report now has a `coverage` section (docs/SQLITE.md). It counts whether
references exist, not whether they are right. Current figures are in each build's
`cert_basis_report.json`.

**To close:** the maintainer decides a coverage target for Phase 2. A target should
come with a way to sample reference accuracy, or it rewards references that exist
but are wrong.

### BUILD-13. `canonical_title` and `current_grouping` are unchecked copies

`provisions.number` must equal the latest version's number (the build fails
otherwise). The title and grouping have no such check. On the 2026-11-11 build
(schema v12) they differed from the latest live version in 768 provisions for
`canonical_title` (CAR 3: 397, CAR 3 reissue: 371, `Definitions` vs
`Definitions.`) and 129 for `current_grouping` (STANAG 4671: 113, CS-25: 16,
`…Interconnection Systems` vs `…System`). The app shows `canonical_title` in
lists and `title_at_revision` on the page, so readers see both. Re-measure on
the current build first: the grouping style was reworked after that count
(2026-11-12).

**To close:** read CAR 3, STANAG 4671 and CS-25 Subpart H against `input/` to
decide which spelling is right and fix it in the extractor or an override. Then
either make the check fatal, or drop both fields from the provision JSON and
have the build derive them from the latest live version (one fewer way to be
wrong; a JSON schema change). See also EASA-6 (titles).

### BUILD-14. Nothing forces a `SCHEMA_VERSION` bump when the DDL changes

The bump is by convention. The app's `test_schema_drift.py` compares the
vendored DDL and the version, but a DDL edit with no bump passes once the copy
is re-vendored, and the test is skipped when the data repo isn't checked out
beside the app (so in CI). NATO was added to a closed set with no bump, and no
rule says when a new enum value or seeded row is a contract change. Closed sets
are also kept in two places: issuers and categories are tested against their
schema enums, but `doc_kind`, `entry_type`, `action_type`, `provenance`,
`effect` and gap `reason` live in a JSON Schema and a DDL CHECK with no test
(a mismatch fails the build loudly, so the risk is low).

**To close:** in `tests/test_contract.py`, pin a SHA-256 of `SCHEMA_SQL` beside
`SCHEMA_VERSION` (the failure message says to bump and add a SCHEMA_HISTORY
row); add a test that each CHECK enum equals its JSON Schema enum; write the
rule for closed-set additions into SCHEMA_HISTORY.

### BUILD-15. No post-build invariant stage

Facts about the computed tables hold only because the Python is right: a
resolved row's version belongs to its ref's document and isn't a deletion,
search rowids are versions with text of their own, every text version has
paragraphs. 18 such invariants were probed by SQL on 2026-11-11 and all held.

**To close:** add `certbuild/invariants.py`, a tuple of (message, SQL returning
offending rows) run after `foreign_key_check`. BUILD-13's agreement checks go
in as report counts first. Run `scripts/compare_builds.py`: expect `identical`.

### BUILD-16. Contract surface the app doesn't use

Measured on the v12 build (2026-11-11); re-measure on v15 before acting.

- **Aliases.** No file has `same_as_designator` and no tool emits it, so
  `same_as_version_id` is NULL in all 13,210 rows. It costs a column, a
  self-referencing composite FK, a unique index, two CHECKs, a schema branch,
  about 70 lines of build code, and a recursive CTE on every app version list
  and basis page. Meanwhile 31 consecutive version pairs have identical text
  (24 in MIL-HDBK-516 where the number or title changed; 7 in FAA 23/25/27/29
  and CAR 3), and the app counts each as a text change in "changes since".
- **`provision_paragraphs`** (72k rows, about 21 MB with indexes, a quarter of
  the file) isn't read by the app. The app parses `provision_versions.text` and
  takes depth as `indent / 2`, which DATA_FORMAT says not to rely on. Two
  parsers of one format, and the authoritative one ships unused. Text is stored
  three times (versions 21 MB, paragraphs 19 MB, FTS 20 MB; the FTS copy was a
  deliberate v12 choice).

**To close:** decide (a) remove aliases from JSON, DDL and app, or (b) remove the
authored field and have the build set `same_as_version_id` when a version's text
equals the previous one's, pointing at the root so the app needs no recursion
(recommended: a computed value can't be forgotten); file the 7 identical FAA/CAR
pairs for a source check. For the paragraphs, decide in the app repo: read the
table (recommended, one parser) or drop it from the shipped DB. Either change is
a contract bump that rides with the app release.

### BUILD-17. Small contract and documentation fixes

Found by the 2026-11-11 database review (schema v12); each is cheap.

- docs/SQLITE.md says `SUPPORTED_SCHEMA = 7` in its consumer example and
  "currently **14**" in the text; the code is 15. Add a sentence that `ordinal`
  is the only revision order: ordinal and date order disagree for 40 revision
  pairs (FAA 25: 20, 29: 10, 27: 5, 23: 4, 36: 1), probably real, and resolution
  uses ordinal only.
- The file isn't compacted: 945 free pages (3.7 MB) after the FTS `optimize`.
  Add `VACUUM` as the last build statement.
- `idx_actions_reference` (228 KB) is used by neither the app nor the build;
  `idx_pp_path` (1.3 MB) goes with BUILD-16.
- `latest_versions` is `SELECT pv.*`: its shape changes with every column, it
  carries `text`, and it returns deleted provisions despite its name. Give it an
  explicit column list without `text`.
- Unused enum values: `doc_kind` has 9 values (4 in use), `issuers.kind`
  `standards_body`, 5 of 10 `action_type` values. Each is a promise the app may
  code against; leave until ROADMAP-11 is decided.

**To close:** do the first four with the next contract bump.
