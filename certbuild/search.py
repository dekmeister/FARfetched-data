"""The full-text search tables (docs/SQLITE.md §Search).

Fills `search_text`, `search_current` and `search_aircraft` from rows already
inserted. Must run after the provisions and aircraft stages. Never reads
`data/` and never changes another table.
"""

from __future__ import annotations

import re
import sqlite3

from certbuild.text.flat import plain_text

# The app marks snippet hits with \x02 and \x03. Garbled PDF extraction has put
# C0 controls into at least one text (issues/easa-cs.md), and an index needs
# none of them.
_CONTROL_RE = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]+")


def _clean(text: str) -> str:
    """`text` without control characters (newlines stay)."""
    return _CONTROL_RE.sub(" ", text)


def _body(text: str) -> str:
    return " ".join(_clean(plain_text(text)).split())


def _insert_text(conn: sqlite3.Connection) -> None:
    """One row per version with text of its own, plus title-only rows for
    known gaps. Aliases share their target's row and deletions have no text.
    `body` is plain text, so markup can neither be matched nor reach a snippet.
    """
    rows = conn.execute(
        "SELECT id, title_at_revision, text, text_missing FROM provision_versions "
        "WHERE deleted = 0 AND same_as_version_id IS NULL ORDER BY id"
    ).fetchall()
    conn.executemany(
        "INSERT INTO search_text (rowid, title, body) VALUES (?, ?, ?)",
        (
            (vid, title, "" if missing else _body(text))
            for vid, title, text, missing in rows
        ),
    )


def _insert_current(conn: sqlite3.Connection) -> None:
    """The version holding the text of each provision's latest version, unless
    that version deleted the provision."""
    conn.execute(
        """
        WITH RECURSIVE text_of(id, same_as) AS (
            SELECT id, same_as_version_id FROM latest_versions WHERE deleted = 0
            UNION
            SELECT pv.id, pv.same_as_version_id
            FROM text_of JOIN provision_versions pv ON pv.id = text_of.same_as
        )
        INSERT INTO search_current (version_id)
        SELECT id FROM text_of WHERE same_as IS NULL ORDER BY id
        """
    )


def _names(names: list[str]) -> str:
    """Group, manufacturer and printed holder, each once, by newlines."""
    return "\n".join(dict.fromkeys(names))


def _insert_aircraft(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT tcb.id, m.model_designation, m.common_name,
               mf.group_name, mf.name, t.holder, t.tcds_number,
               (SELECT group_concat(raw_reference, char(10)) FROM (
                    SELECT e.raw_reference FROM cert_basis_entries e
                    WHERE e.tcb_id = tcb.id ORDER BY e.display_order))
        FROM tcb
        JOIN aircraft_models m ON m.id = tcb.model_id
        JOIN manufacturers mf ON mf.id = m.manufacturer_id
        JOIN tcds t ON t.id = tcb.tcds_id
        ORDER BY tcb.id
        """
    ).fetchall()
    conn.executemany(
        "INSERT INTO search_aircraft "
        "(rowid, designation, common_name, manufacturer, tcds_number, basis) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            (tcb, designation, common, _names(names), tcds, _clean(basis or ""))
            for tcb, designation, common, *names, tcds, basis in rows
        ),
    )


def insert_search(conn: sqlite3.Connection) -> None:
    """Fill the search tables and merge each index into one segment."""
    _insert_text(conn)
    _insert_current(conn)
    _insert_aircraft(conn)
    for table in ("search_text", "search_aircraft"):  # constants, not data
        conn.execute(f"INSERT INTO {table} ({table}) VALUES ('optimize')")


def search_report(conn: sqlite3.Connection) -> dict[str, int]:
    """Counts for the build report."""
    text, title_only = conn.execute(
        "SELECT count(*), coalesce(sum(body = ''), 0) FROM search_text"
    ).fetchone()
    return {
        "text_rows": text,
        "title_only_rows": title_only,
        "current_rows": conn.execute("SELECT count(*) FROM search_current").fetchone()[
            0
        ],
        "aircraft_rows": conn.execute(
            "SELECT count(*) FROM search_aircraft"
        ).fetchone()[0],
    }
