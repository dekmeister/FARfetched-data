"""build() and check(): the build steps in order."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

from certbuild.aircraft import ParagraphRefStats, insert_aircraft
from certbuild.ddl import SCHEMA_SQL, SCHEMA_VERSION
from certbuild.errors import BuildError
from certbuild.lookups import seed_lookups
from certbuild.provisions import (
    insert_documents,
    insert_provisions,
    number_clashes,
    text_format_errors,
)
from certbuild.report import BuildReport, build_report, git_dirty_paths, git_sha
from certbuild.similarity import insert_similarity
from certbuild.sources import (
    check_paths,
    load_aircraft,
    load_documents,
    load_provisions,
    validate_data_dir,
)


# (table, column) pairs holding dates. A date after the build day is a parse
# error upstream (e.g. a two-digit year read as 2064), never real data.
_DATE_COLUMNS = (
    ("document_revisions", "effective_date"),
    ("version_actions", "issued_on"),
    ("tcds", "revision_date"),
)


def _future_dates(conn: sqlite3.Connection, today: str) -> list[str]:
    errors: list[str] = []
    for table, column in _DATE_COLUMNS:
        # Identifiers come from the constant above, never from data.
        n, sample = conn.execute(
            f"SELECT count(*), min({column}) FROM {table} WHERE {column} > ?",
            (today,),
        ).fetchone()
        if n:
            errors.append(
                f"{table}.{column}: {n} date(s) after {today} (e.g. {sample})"
            )
    return errors


def _remove_sqlite_file(path: Path) -> None:
    """Remove a DB and any sidecars, including stale WAL ones from old builds."""
    path.unlink(missing_ok=True)
    for suffix in ("-journal", "-wal", "-shm"):
        path.with_name(path.name + suffix).unlink(missing_ok=True)


def build(data_dir: Path, out_path: Path) -> BuildReport:
    """Validate, build SQLite, atomically write. Raise BuildError on failure."""
    validation_errors = validate_data_dir(data_dir)
    if validation_errors:
        raise BuildError([str(e) for e in validation_errors])

    documents = load_documents(data_dir)
    provisions = load_provisions(data_dir)
    aircraft = load_aircraft(data_dir)
    path_errors = check_paths(documents, provisions)
    if path_errors:
        raise BuildError(path_errors)

    tmp = out_path.with_suffix(out_path.suffix + ".new")
    _remove_sqlite_file(tmp)

    conn = sqlite3.connect(tmp)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION:d}")
        conn.execute(
            "INSERT INTO build_info (id, schema_version, git_sha, built_at) "
            "VALUES (1, ?, ?, ?)",
            (
                SCHEMA_VERSION,
                git_sha(data_dir),
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        seed_lookups(conn)
        insert_documents(conn, documents)
        text_stats = insert_provisions(conn, provisions)
        if text_stats.errors:
            raise BuildError(text_stats.errors)
        clashes = number_clashes(conn)
        if clashes:
            raise BuildError(clashes)
        insert_similarity(conn)
        para_stats = ParagraphRefStats()
        unresolved = insert_aircraft(conn, aircraft, para_stats)
        date_errors = _future_dates(conn, date.today().isoformat())
        if date_errors:
            raise BuildError(date_errors)
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            raise BuildError([f"foreign key violation: {r}" for r in fk_errors])
        report = build_report(
            conn, unresolved, text_stats, para_stats, git_dirty_paths(data_dir)
        )
        conn.commit()
    except Exception:
        conn.close()
        _remove_sqlite_file(tmp)
        raise
    conn.close()

    if unresolved:
        _remove_sqlite_file(tmp)
        raise BuildError(unresolved)

    # Write the report beside the DB before either is swapped in, so a failed
    # write can't leave a new DB next to a stale report.
    report_path = out_path.with_name(out_path.stem + "_report.json")
    report_tmp = report_path.with_name(report_path.name + ".new")
    try:
        report_tmp.write_text(json.dumps(report, indent=2) + "\n")
    except BaseException:
        report_tmp.unlink(missing_ok=True)
        _remove_sqlite_file(tmp)
        raise

    for suffix in ("-wal", "-shm"):
        out_path.with_name(out_path.name + suffix).unlink(missing_ok=True)
    tmp.replace(out_path)
    report_tmp.replace(report_path)
    return report


def check(data_dir: Path) -> list[str]:
    """Everything `build` checks before inserting: schemas, paths, text layout.

    Cross-file checks (revisions, aliases, references, dates) need the build.
    """
    validation_errors = validate_data_dir(data_dir)
    if validation_errors:
        return [str(e) for e in validation_errors]
    provisions = load_provisions(data_dir)
    errors = check_paths(load_documents(data_dir), provisions)
    errors.extend(text_format_errors(provisions))
    return errors
