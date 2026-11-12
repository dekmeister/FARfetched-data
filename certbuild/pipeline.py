"""build() and check(): the build steps, in order (docs/SQLITE.md §Build).

The stage list is `load_checked` (no DB) then `_fill`. A new check is a
function returning list[str] plus one `_raise_if(...)` line in the right
place.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from certbuild.aircraft import ParagraphRefStats, insert_aircraft
from certbuild.citations import CitationStats
from certbuild.ddl import SCHEMA_SQL, SCHEMA_VERSION
from certbuild.deviations import check_deviation_paths, insert_deviations
from certbuild.errors import BuildError
from certbuild.lookups import seed_lookups
from certbuild.provisions import (
    insert_documents,
    insert_provisions,
    number_clashes,
    parse_texts,
)
from certbuild.report import (
    BuildReport,
    build_report,
    git_dirty_paths,
    git_sha,
    read_state,
)
from certbuild.search import insert_search
from certbuild.similarity import insert_similarity
from certbuild.text.paragraphs import ParsedText
from certbuild.sources import (
    Source,
    check_groupings,
    check_paths,
    read_data_dir,
)


# (table, column) pairs holding dates. A date after the build day is a parse
# error upstream (e.g. a two-digit year read as 2064), never real data.
_DATE_COLUMNS = (
    ("document_revisions", "effective_date"),
    ("version_actions", "issued_on"),
    ("tcds", "revision_date"),
    ("deviations", "published_on"),
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


@dataclass(frozen=True)
class Sources:
    """data/ loaded and checked: everything the inserts need."""

    documents: list[Source]
    provisions: list[Source]
    aircraft: list[Source]
    texts: dict[str, ParsedText]  # every version text, parsed
    deviations: list[Source]


def load_checked(data_dir: Path) -> Sources:
    """Every check that needs no DB: the schemas, then file paths, text
    layout and grouping style. Raise BuildError listing every fault of the first stage that
    fails.

    `check()` (--check) and `build()` both run exactly this, so --check
    can't drift from the build: a new pre-insert check goes here."""
    files, validation_errors = read_data_dir(data_dir)
    _raise_if([str(e) for e in validation_errors])
    texts, text_errors = parse_texts(files.provisions)
    _raise_if(
        check_paths(files.documents, files.provisions)
        + check_deviation_paths(files.deviations)
        + text_errors
        + check_groupings(files.provisions)
    )
    return Sources(
        files.documents, files.provisions, files.aircraft, texts, files.deviations
    )


def _raise_if(errors: list[str]) -> None:
    if errors:
        raise BuildError(errors)


def _fill(conn: sqlite3.Connection, src: Sources, data_dir: Path) -> BuildReport:
    """Create the schema and insert everything, stage by stage. Each stage
    collects its faults; they are raised before the next stage starts
    (certbuild/errors.py)."""
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
    insert_documents(conn, src.documents)
    text_stats, errors = insert_provisions(conn, src.provisions, src.texts)
    _raise_if(errors)
    _raise_if(number_clashes(conn))
    insert_similarity(conn)
    para_stats = ParagraphRefStats()
    citation_stats = CitationStats()
    _raise_if(insert_aircraft(conn, src.aircraft, para_stats, citation_stats))
    _raise_if(insert_deviations(conn, src.deviations))
    insert_search(conn)
    _raise_if(_future_dates(conn, date.today().isoformat()))
    _raise_if(
        [
            f"foreign key violation: {r}"
            for r in conn.execute("PRAGMA foreign_key_check").fetchall()
        ]
    )
    # Every reference resolved, or insert_aircraft's stage would have raised.
    return build_report(
        conn,
        [],
        text_stats,
        para_stats,
        citation_stats,
        git_dirty_paths(data_dir),
        read_state(data_dir / "promotion.json"),
        read_state(data_dir / "source_checks.json"),
    )


def build(data_dir: Path, out_path: Path) -> BuildReport:
    """Validate, build SQLite, atomically write. Raise BuildError on failure."""
    src = load_checked(data_dir)
    tmp = out_path.with_suffix(out_path.suffix + ".new")
    _remove_sqlite_file(tmp)
    conn = sqlite3.connect(tmp)
    try:
        report = _fill(conn, src, data_dir)
        conn.commit()
    except Exception:
        conn.close()
        _remove_sqlite_file(tmp)
        raise
    conn.close()

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
    """Everything `build` checks before inserting (`load_checked`): schemas,
    paths, text layout. Cross-file checks (revisions, aliases, references,
    dates) need the build."""
    try:
        load_checked(data_dir)
    except BuildError as exc:
        return exc.errors
    return []
