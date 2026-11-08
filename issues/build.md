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
