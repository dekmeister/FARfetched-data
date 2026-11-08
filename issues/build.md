# Build and contract (BUILD-)

`build.py` and the SQLite contract ([docs/SQLITE.md](../docs/SQLITE.md)).
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

### BUILD-9. `build.py` has outgrown a single file

2,433 lines, six concerns, `parse_paragraphs` at CC 59, and a de facto public
API used by tools (PROC-11). The real build takes ~52 s, 80% similarity.

**To close:** decide on and carry out (or reject) the plan in
[docs/BUILD_REFACTOR_REVIEW.md](../docs/BUILD_REFACTOR_REVIEW.md); then
delete that file and update CLAUDE.md's "Keep `build.py` a single file" rule.
