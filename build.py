"""Compile FARfetched-data JSON sources into cert_basis.sqlite.

Currently implements validation only. SQLite emission comes next.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).parent
SCHEMAS_DIR = REPO_ROOT / "schemas"

SCHEMA_SQL = """
CREATE TABLE regulations (
    id              INTEGER PRIMARY KEY,
    authority       TEXT NOT NULL,
    title_number    INTEGER NOT NULL,
    part            TEXT NOT NULL,
    subpart         TEXT,
    section         TEXT NOT NULL,
    section_title   TEXT,
    UNIQUE (authority, title_number, part, subpart, section)
);

CREATE TABLE regulation_amendments (
    id                      INTEGER PRIMARY KEY,
    regulation_id           INTEGER NOT NULL REFERENCES regulations(id),
    amendment_designator    TEXT NOT NULL,
    amendment_ordinal       INTEGER NOT NULL,
    effective_date          DATE NOT NULL,
    text                    TEXT NOT NULL,
    title_at_amendment      TEXT,
    source_url              TEXT,
    federal_register_cite   TEXT,
    UNIQUE (regulation_id, amendment_designator)
);

CREATE INDEX idx_amendments_reg_date
    ON regulation_amendments (regulation_id, effective_date);
CREATE INDEX idx_amendments_reg_ordinal
    ON regulation_amendments (regulation_id, amendment_ordinal);

CREATE TABLE aircraft (
    id                  INTEGER PRIMARY KEY,
    tcds_number         TEXT NOT NULL UNIQUE,
    manufacturer        TEXT NOT NULL,
    model_designation   TEXT NOT NULL,
    common_name         TEXT,
    category            TEXT,
    tcds_revision       TEXT,
    tcds_revision_date  DATE,
    tcds_source_url     TEXT,
    notes               TEXT
);

CREATE TABLE certification_basis_entries (
    id                          INTEGER PRIMARY KEY,
    aircraft_id                 INTEGER NOT NULL REFERENCES aircraft(id),
    regulation_amendment_id     INTEGER REFERENCES regulation_amendments(id),
    entry_type                  TEXT NOT NULL,
    raw_reference               TEXT NOT NULL,
    applicability_notes         TEXT,
    display_order               INTEGER NOT NULL,
    UNIQUE (aircraft_id, regulation_amendment_id, entry_type, raw_reference)
);

CREATE INDEX idx_cbe_aircraft
    ON certification_basis_entries (aircraft_id, display_order);

CREATE VIEW latest_amendments AS
SELECT ra.*
FROM regulation_amendments ra
WHERE ra.amendment_ordinal = (
    SELECT MAX(amendment_ordinal)
    FROM regulation_amendments
    WHERE regulation_id = ra.regulation_id
);
"""


class BuildError(Exception):
    """Raised when the build cannot complete (validation or resolution failure)."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


@dataclass(frozen=True)
class ValidationError:
    path: Path
    message: str
    location: str

    def __str__(self) -> str:
        where = f" at {self.location}" if self.location else ""
        return f"{self.path}:{where} {self.message}"


@cache
def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS_DIR / f"{name}.schema.json").read_text())
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate(path: Path, schema_name: str) -> list[ValidationError]:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [ValidationError(path, f"invalid JSON: {exc}", "")]
    validator = _validator(schema_name)
    errors: list[ValidationError] = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        location = "/".join(str(p) for p in err.absolute_path)
        errors.append(ValidationError(path, err.message, location))
    return errors


def validate_regulation_file(path: Path) -> list[ValidationError]:
    return _validate(path, "regulation")


def validate_aircraft_file(path: Path) -> list[ValidationError]:
    return _validate(path, "aircraft")


def validate_data_dir(data_dir: Path) -> list[ValidationError]:
    errors: list[ValidationError] = []
    regs_dir = data_dir / "regulations"
    if regs_dir.is_dir():
        for p in sorted(regs_dir.rglob("*.json")):
            errors.extend(validate_regulation_file(p))
    aircraft_dir = data_dir / "aircraft"
    if aircraft_dir.is_dir():
        for p in sorted(aircraft_dir.glob("*.json")):
            errors.extend(validate_aircraft_file(p))
    return errors


def _load_regulations(data_dir: Path) -> list[dict]:
    regs_dir = data_dir / "regulations"
    if not regs_dir.is_dir():
        return []
    return [
        json.loads(p.read_text()) for p in sorted(regs_dir.rglob("*.json"))
    ]


def _load_aircraft(data_dir: Path) -> list[dict]:
    ac_dir = data_dir / "aircraft"
    if not ac_dir.is_dir():
        return []
    return [json.loads(p.read_text()) for p in sorted(ac_dir.glob("*.json"))]


def _insert_regulations(conn: sqlite3.Connection, regs: list[dict]) -> None:
    for r in regs:
        cur = conn.execute(
            "INSERT INTO regulations "
            "(authority, title_number, part, subpart, section, section_title) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                r["authority"],
                r["title_number"],
                r["part"],
                r["subpart"],
                r["section"],
                r["canonical_title"],
            ),
        )
        reg_id = cur.lastrowid
        for a in r["amendments"]:
            conn.execute(
                "INSERT INTO regulation_amendments "
                "(regulation_id, amendment_designator, amendment_ordinal, "
                " effective_date, text, title_at_amendment, source_url, "
                " federal_register_cite) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    reg_id,
                    a["designator"],
                    a["ordinal"],
                    a["effective_date"],
                    a["text"],
                    a["title_at_amendment"],
                    a["source_url"],
                    a["federal_register_cite"],
                ),
            )


def _sections_in_part(
    conn: sqlite3.Connection, authority: str, title_number: int, part: str
) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT section FROM regulations "
            "WHERE authority = ? AND title_number = ? AND part = ?",
            (authority, title_number, part),
        )
    ]


def _amendment_for_section_at_ordinal(
    conn: sqlite3.Connection,
    authority: str,
    title_number: int,
    part: str,
    section: str,
    ordinal_max: int,
) -> int | None:
    row = conn.execute(
        "SELECT ra.id FROM regulation_amendments ra "
        "JOIN regulations r ON r.id = ra.regulation_id "
        "WHERE r.authority = ? AND r.title_number = ? AND r.part = ? "
        "  AND r.section = ? AND ra.amendment_ordinal <= ? "
        "ORDER BY ra.amendment_ordinal DESC LIMIT 1",
        (authority, title_number, part, section, ordinal_max),
    ).fetchone()
    return row[0] if row else None


def _amendment_by_designator(
    conn: sqlite3.Connection,
    authority: str,
    title_number: int,
    part: str,
    section: str,
    designator: str,
) -> int | None:
    row = conn.execute(
        "SELECT ra.id FROM regulation_amendments ra "
        "JOIN regulations r ON r.id = ra.regulation_id "
        "WHERE r.authority = ? AND r.title_number = ? AND r.part = ? "
        "  AND r.section = ? AND ra.amendment_designator = ?",
        (authority, title_number, part, section, designator),
    ).fetchone()
    return row[0] if row else None


def _insert_cb_row(
    conn: sqlite3.Connection,
    aircraft_id: int,
    amendment_id: int | None,
    entry: dict,
) -> None:
    try:
        conn.execute(
            "INSERT INTO certification_basis_entries "
            "(aircraft_id, regulation_amendment_id, entry_type, raw_reference, "
            " applicability_notes, display_order) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                aircraft_id,
                amendment_id,
                entry["entry_type"],
                entry["raw_reference"],
                entry["applicability_notes"],
                entry["display_order"],
            ),
        )
    except sqlite3.IntegrityError:
        # Two resolved_references in the same entry expanded to the same
        # amendment. Rare but harmless; the UNIQUE constraint dedupes.
        pass


def _insert_aircraft(
    conn: sqlite3.Connection, aircraft_docs: list[dict]
) -> list[str]:
    failures: list[str] = []
    for a in aircraft_docs:
        cur = conn.execute(
            "INSERT INTO aircraft "
            "(tcds_number, manufacturer, model_designation, common_name, "
            " category, tcds_revision, tcds_revision_date, tcds_source_url, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                a["tcds_number"],
                a["manufacturer"],
                a["model_designation"],
                a["common_name"],
                a["category"],
                a["tcds_revision"],
                a["tcds_revision_date"],
                a["tcds_source_url"],
                a["notes"],
            ),
        )
        aid = cur.lastrowid
        assert aid is not None
        for entry in a["certification_basis"]:
            failures.extend(_expand_and_insert_entry(conn, aid, entry, a["tcds_number"]))
    return failures


def _expand_and_insert_entry(
    conn: sqlite3.Connection, aircraft_id: int, entry: dict, tcds: str
) -> list[str]:
    failures: list[str] = []
    if entry["entry_type"] != "regulation" or not entry["resolved_references"]:
        _insert_cb_row(conn, aircraft_id, None, entry)
        return failures

    for ref in entry["resolved_references"]:
        kind = ref["reference_kind"]
        if kind == "single":
            amend_id = _amendment_by_designator(
                conn,
                ref["authority"],
                ref["title_number"],
                ref["part"],
                ref["section"],
                ref["amendment_designator"],
            )
            if amend_id is None:
                failures.append(
                    f"{tcds}: single ref to §{ref['part']}.{ref['section']} "
                    f"amendment {ref['amendment_designator']} — "
                    f"no matching amendment in regulations data"
                )
                continue
            _insert_cb_row(conn, aircraft_id, amend_id, entry)
        elif kind == "range":
            sections = _sections_in_part(
                conn, ref["authority"], ref["title_number"], ref["part"]
            )
            if not sections:
                failures.append(
                    f"{tcds}: range ref over "
                    f"{ref['authority']} title {ref['title_number']} "
                    f"part '{ref['part']}' — no sections of that part in "
                    f"regulations data"
                )
                continue
            for sec in sections:
                amend_id = _amendment_for_section_at_ordinal(
                    conn,
                    ref["authority"],
                    ref["title_number"],
                    ref["part"],
                    sec,
                    ref["to_amendment_ordinal"],
                )
                if amend_id is None:
                    # Section post-dates the range. Skip silently.
                    continue
                _insert_cb_row(conn, aircraft_id, amend_id, entry)
    return failures


def _build_report(
    conn: sqlite3.Connection, unresolved: list[str]
) -> dict[str, object]:
    def count(table: str) -> int:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    return {
        "regulations": count("regulations"),
        "regulation_amendments": count("regulation_amendments"),
        "aircraft": count("aircraft"),
        "certification_basis_entries": count("certification_basis_entries"),
        "unresolved_references": unresolved,
    }


def _sqlite_sidecars(path: Path) -> list[Path]:
    return [path.with_name(path.name + suffix) for suffix in ("-wal", "-shm")]


def _remove_sqlite_file(path: Path) -> None:
    path.unlink(missing_ok=True)
    for side in _sqlite_sidecars(path):
        side.unlink(missing_ok=True)


def build(data_dir: Path, out_path: Path) -> dict[str, object]:
    """Validate, build SQLite, atomically write. Raise BuildError on failure."""
    validation_errors = validate_data_dir(data_dir)
    if validation_errors:
        raise BuildError([str(e) for e in validation_errors])

    tmp = out_path.with_suffix(out_path.suffix + ".new")
    _remove_sqlite_file(tmp)

    conn = sqlite3.connect(tmp)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        _insert_regulations(conn, _load_regulations(data_dir))
        unresolved = _insert_aircraft(conn, _load_aircraft(data_dir))
        report = _build_report(conn, unresolved)
        conn.commit()
        # Persist WAL mode in the header, then checkpoint so the -wal file
        # is flushed into the main DB and truncated before close. Without
        # this, the atomic rename below would orphan the sidecar files.
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except Exception:
        conn.close()
        _remove_sqlite_file(tmp)
        raise
    finally:
        conn.close()

    if unresolved:
        _remove_sqlite_file(tmp)
        raise BuildError(unresolved)

    # Clear any stale sidecars at the destination, then atomic rename.
    for side in _sqlite_sidecars(out_path):
        side.unlink(missing_ok=True)
    for side in _sqlite_sidecars(tmp):
        side.unlink(missing_ok=True)
    tmp.replace(out_path)

    report_path = out_path.with_name(out_path.stem + "_report.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "data",
        help="Path to the data directory (default: ./data)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "cert_basis.sqlite",
        help="Output SQLite path (default: ./cert_basis.sqlite)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate only; do not build SQLite.",
    )
    args = parser.parse_args(argv)

    if args.check:
        errors = validate_data_dir(args.data_dir)
        if errors:
            for e in errors:
                print(e, file=sys.stderr)
            print(f"\n{len(errors)} validation error(s).", file=sys.stderr)
            return 1
        print(f"OK: {args.data_dir} validates clean.", file=sys.stderr)
        return 0

    try:
        report = build(args.data_dir, args.out)
    except BuildError as exc:
        for line in exc.errors:
            print(line, file=sys.stderr)
        print(f"\nBuild failed ({len(exc.errors)} error(s)).", file=sys.stderr)
        return 1

    print(
        f"OK: wrote {args.out} "
        f"(regulations={report['regulations']}, "
        f"amendments={report['regulation_amendments']}, "
        f"aircraft={report['aircraft']}, "
        f"entries={report['certification_basis_entries']})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
