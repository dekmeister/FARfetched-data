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
