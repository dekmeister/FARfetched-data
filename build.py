"""Compile FARfetched-data JSON sources into cert_basis.sqlite."""

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
CREATE TABLE naa_authorities (
    id      INTEGER PRIMARY KEY,
    code    TEXT NOT NULL UNIQUE,
    name    TEXT NOT NULL,
    country TEXT
);

CREATE TABLE manufacturers (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE categories (
    id   INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
);

CREATE TABLE regulation_parts (
    id           INTEGER PRIMARY KEY,
    authority_id INTEGER NOT NULL REFERENCES naa_authorities(id),
    title_number INTEGER NOT NULL,
    part         TEXT NOT NULL,
    description  TEXT,
    UNIQUE (authority_id, title_number, part)
);

CREATE TABLE regulations (
    id              INTEGER PRIMARY KEY,
    part_id         INTEGER NOT NULL REFERENCES regulation_parts(id),
    section         TEXT NOT NULL,
    current_subpart TEXT,
    canonical_title TEXT NOT NULL,
    subject_group   TEXT,
    UNIQUE (part_id, section)
);

CREATE TABLE amendments (
    id             INTEGER PRIMARY KEY,
    part_id        INTEGER NOT NULL REFERENCES regulation_parts(id),
    designator     TEXT NOT NULL,
    ordinal        INTEGER NOT NULL,
    effective_date DATE NOT NULL,
    UNIQUE (part_id, designator),
    UNIQUE (part_id, ordinal)
);

CREATE TABLE section_amendments (
    id                    INTEGER PRIMARY KEY,
    regulation_id         INTEGER NOT NULL REFERENCES regulations(id),
    amendment_id          INTEGER NOT NULL REFERENCES amendments(id),
    subpart_at_time       TEXT,
    title_at_amendment    TEXT NOT NULL,
    text                  TEXT NOT NULL,
    federal_register_cite TEXT NOT NULL,
    source_url            TEXT,
    UNIQUE (regulation_id, amendment_id)
);

CREATE INDEX idx_sa_reg ON section_amendments (regulation_id);
CREATE INDEX idx_amendments_part_ordinal ON amendments (part_id, ordinal);

CREATE TABLE aircraft_models (
    id                INTEGER PRIMARY KEY,
    manufacturer_id   INTEGER NOT NULL REFERENCES manufacturers(id),
    model_designation TEXT NOT NULL,
    common_name       TEXT,
    notes             TEXT,
    UNIQUE (manufacturer_id, model_designation)
);

CREATE TABLE model_categories (
    model_id    INTEGER NOT NULL REFERENCES aircraft_models(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    PRIMARY KEY (model_id, category_id)
);

CREATE TABLE tcds (
    id            INTEGER PRIMARY KEY,
    authority_id  INTEGER NOT NULL REFERENCES naa_authorities(id),
    tcds_number   TEXT NOT NULL,
    revision      TEXT,
    revision_date DATE,
    source_url    TEXT,
    UNIQUE (authority_id, tcds_number)
);

CREATE TABLE tcb (
    id       INTEGER PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES aircraft_models(id),
    tcds_id  INTEGER NOT NULL REFERENCES tcds(id),
    notes    TEXT,
    UNIQUE (model_id, tcds_id)
);

CREATE TABLE cert_basis_entries (
    id                    INTEGER PRIMARY KEY,
    tcb_id                INTEGER NOT NULL REFERENCES tcb(id),
    section_amendment_id  INTEGER REFERENCES section_amendments(id),
    entry_type            TEXT NOT NULL
                          CHECK (entry_type IN
                              ('regulation','special_condition','elos',
                               'exemption','other')),
    raw_reference         TEXT NOT NULL,
    applicability_notes   TEXT,
    display_order         INTEGER NOT NULL
);

CREATE INDEX idx_cbe_tcb ON cert_basis_entries (tcb_id, display_order);

CREATE VIEW latest_amendments AS
SELECT sa.*, a.designator, a.ordinal, a.effective_date
FROM section_amendments sa
JOIN amendments a ON a.id = sa.amendment_id
WHERE a.ordinal = (
    SELECT MAX(a2.ordinal)
    FROM section_amendments sa2
    JOIN amendments a2 ON a2.id = sa2.amendment_id
    WHERE sa2.regulation_id = sa.regulation_id
);
"""

# Canonical names and countries for authorities encountered in data.
_AUTHORITY_META: dict[str, tuple[str, str | None]] = {
    "FAA": ("Federal Aviation Administration", "US"),
    "EASA": ("European Union Aviation Safety Agency", "EU"),
}

# Canonical display names for category codes.
_CATEGORY_NAMES: dict[str, str] = {
    "transport": "Transport",
    "normal": "Normal",
    "utility": "Utility",
    "acrobatic": "Acrobatic",
    "commuter": "Commuter",
    "restricted": "Restricted",
    "limited": "Limited",
    "provisional": "Provisional",
    "primary": "Primary",
    "special": "Special",
}


class BuildError(Exception):
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


def validate_regulation_part_file(path: Path) -> list[ValidationError]:
    return _validate(path, "regulation_part")


def validate_regulation_file(path: Path) -> list[ValidationError]:
    return _validate(path, "regulation")


def validate_aircraft_file(path: Path) -> list[ValidationError]:
    return _validate(path, "aircraft_model")


def validate_data_dir(data_dir: Path) -> list[ValidationError]:
    errors: list[ValidationError] = []
    regs_dir = data_dir / "regulations"
    if regs_dir.is_dir():
        for p in sorted(regs_dir.rglob("*.json")):
            if p.name == "_part.json":
                errors.extend(validate_regulation_part_file(p))
            else:
                errors.extend(validate_regulation_file(p))
    aircraft_dir = data_dir / "aircraft"
    if aircraft_dir.is_dir():
        for p in sorted(aircraft_dir.rglob("*.json")):
            errors.extend(validate_aircraft_file(p))
    return errors


# ---------------------------------------------------------------------------
# Loaders


def _load_regulation_parts(data_dir: Path) -> list[dict]:
    regs_dir = data_dir / "regulations"
    if not regs_dir.is_dir():
        return []
    return [
        json.loads(p.read_text())
        for p in sorted(regs_dir.rglob("_part.json"))
    ]


def _load_regulations(data_dir: Path) -> list[dict]:
    regs_dir = data_dir / "regulations"
    if not regs_dir.is_dir():
        return []
    return [
        json.loads(p.read_text())
        for p in sorted(regs_dir.rglob("*.json"))
        if p.name != "_part.json"
    ]


def _load_aircraft(data_dir: Path) -> list[dict]:
    ac_dir = data_dir / "aircraft"
    if not ac_dir.is_dir():
        return []
    return [json.loads(p.read_text()) for p in sorted(ac_dir.rglob("*.json"))]


# ---------------------------------------------------------------------------
# Lookup-table upserts


def _upsert_authority(conn: sqlite3.Connection, code: str) -> int:
    name, country = _AUTHORITY_META.get(code, (code, None))
    conn.execute(
        "INSERT OR IGNORE INTO naa_authorities (code, name, country) VALUES (?, ?, ?)",
        (code, name, country),
    )
    row = conn.execute(
        "SELECT id FROM naa_authorities WHERE code = ?", (code,)
    ).fetchone()
    assert row is not None
    return row[0]


def _upsert_manufacturer(conn: sqlite3.Connection, name: str) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO manufacturers (name) VALUES (?)", (name,)
    )
    row = conn.execute(
        "SELECT id FROM manufacturers WHERE name = ?", (name,)
    ).fetchone()
    assert row is not None
    return row[0]


def _upsert_category(conn: sqlite3.Connection, code: str) -> int:
    display = _CATEGORY_NAMES.get(code, code.title())
    conn.execute(
        "INSERT OR IGNORE INTO categories (code, name) VALUES (?, ?)",
        (code, display),
    )
    row = conn.execute(
        "SELECT id FROM categories WHERE code = ?", (code,)
    ).fetchone()
    assert row is not None
    return row[0]


# ---------------------------------------------------------------------------
# Regulation inserts


def _insert_regulation_parts(conn: sqlite3.Connection, parts: list[dict]) -> None:
    for p in parts:
        auth_id = _upsert_authority(conn, p["authority"])
        cur = conn.execute(
            "INSERT INTO regulation_parts "
            "(authority_id, title_number, part, description) VALUES (?, ?, ?, ?)",
            (auth_id, p["title_number"], p["part"], p.get("description")),
        )
        part_id = cur.lastrowid
        assert part_id is not None
        for a in p["amendments"]:
            conn.execute(
                "INSERT INTO amendments "
                "(part_id, designator, ordinal, effective_date) "
                "VALUES (?, ?, ?, ?)",
                (
                    part_id,
                    a["designator"],
                    a["ordinal"],
                    a["effective_date"],
                ),
            )


def _part_id(
    conn: sqlite3.Connection, authority: str, part: str
) -> int | None:
    row = conn.execute(
        "SELECT rp.id FROM regulation_parts rp "
        "JOIN naa_authorities na ON na.id = rp.authority_id "
        "WHERE na.code = ? AND rp.part = ?",
        (authority, part),
    ).fetchone()
    return row[0] if row else None


def _amendment_id_by_designator(
    conn: sqlite3.Connection, part_id: int, designator: str
) -> int | None:
    row = conn.execute(
        "SELECT id FROM amendments WHERE part_id = ? AND designator = ?",
        (part_id, designator),
    ).fetchone()
    return row[0] if row else None


def _insert_regulations(conn: sqlite3.Connection, sections: list[dict]) -> None:
    for s in sections:
        pid = _part_id(conn, s["authority"], s["part"])
        if pid is None:
            raise BuildError(
                [
                    f"Section {s['authority']}/{s['part']}/{s['section']}: "
                    f"no _part.json found for ({s['authority']}, {s['part']})"
                ]
            )
        cur = conn.execute(
            "INSERT INTO regulations "
            "(part_id, section, current_subpart, canonical_title, subject_group) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                pid,
                s["section"],
                s.get("current_subpart"),
                s["canonical_title"],
                s.get("subject_group"),
            ),
        )
        reg_id = cur.lastrowid
        assert reg_id is not None
        for a in s["amendments"]:
            amend_id = _amendment_id_by_designator(conn, pid, a["designator"])
            if amend_id is None:
                raise BuildError(
                    [
                        f"Section {s['authority']}/{s['part']}/{s['section']}: "
                        f"amendment '{a['designator']}' not declared in _part.json"
                    ]
                )
            conn.execute(
                "INSERT INTO section_amendments "
                "(regulation_id, amendment_id, subpart_at_time, "
                " title_at_amendment, text, federal_register_cite, source_url) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    reg_id,
                    amend_id,
                    a.get("subpart_at_time"),
                    a["title_at_amendment"],
                    a["text"],
                    a["federal_register_cite"],
                    a.get("source_url"),
                ),
            )


# ---------------------------------------------------------------------------
# Aircraft inserts


def _section_amendment_id_for_ordinal(
    conn: sqlite3.Connection,
    authority: str,
    part: str,
    section: str,
    ordinal_max: int,
) -> int | None:
    row = conn.execute(
        "SELECT sa.id "
        "FROM section_amendments sa "
        "JOIN regulations r ON r.id = sa.regulation_id "
        "JOIN amendments a ON a.id = sa.amendment_id "
        "JOIN regulation_parts rp ON rp.id = r.part_id "
        "JOIN naa_authorities na ON na.id = rp.authority_id "
        "WHERE na.code = ? AND rp.part = ? AND r.section = ? "
        "  AND a.ordinal <= ? "
        "ORDER BY a.ordinal DESC LIMIT 1",
        (authority, part, section, ordinal_max),
    ).fetchone()
    return row[0] if row else None


def _section_amendment_id_by_designator(
    conn: sqlite3.Connection,
    authority: str,
    part: str,
    section: str,
    designator: str,
) -> int | None:
    row = conn.execute(
        "SELECT sa.id "
        "FROM section_amendments sa "
        "JOIN regulations r ON r.id = sa.regulation_id "
        "JOIN amendments a ON a.id = sa.amendment_id "
        "JOIN regulation_parts rp ON rp.id = r.part_id "
        "JOIN naa_authorities na ON na.id = rp.authority_id "
        "WHERE na.code = ? AND rp.part = ? AND r.section = ? "
        "  AND a.designator = ?",
        (authority, part, section, designator),
    ).fetchone()
    return row[0] if row else None


def _sections_in_part(
    conn: sqlite3.Connection, authority: str, part: str
) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT r.section FROM regulations r "
            "JOIN regulation_parts rp ON rp.id = r.part_id "
            "JOIN naa_authorities na ON na.id = rp.authority_id "
            "WHERE na.code = ? AND rp.part = ?",
            (authority, part),
        )
    ]


def _insert_cb_row(
    conn: sqlite3.Connection,
    tcb_id: int,
    section_amendment_id: int | None,
    entry: dict,
) -> None:
    try:
        conn.execute(
            "INSERT INTO cert_basis_entries "
            "(tcb_id, section_amendment_id, entry_type, raw_reference, "
            " applicability_notes, display_order) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                tcb_id,
                section_amendment_id,
                entry["entry_type"],
                entry["raw_reference"],
                entry["applicability_notes"],
                entry["display_order"],
            ),
        )
    except sqlite3.IntegrityError:
        pass


def _expand_and_insert_entry(
    conn: sqlite3.Connection,
    tcb_id: int,
    entry: dict,
    tcds_number: str,
) -> list[str]:
    failures: list[str] = []
    if entry["entry_type"] != "regulation" or not entry["resolved_references"]:
        _insert_cb_row(conn, tcb_id, None, entry)
        return failures

    for ref in entry["resolved_references"]:
        kind = ref["reference_kind"]
        if kind == "single":
            sa_id = _section_amendment_id_by_designator(
                conn,
                ref["authority"],
                ref["part"],
                ref["section"],
                ref["amendment_designator"],
            )
            if sa_id is None:
                failures.append(
                    f"{tcds_number}: single ref to "
                    f"§{ref['part']}.{ref['section']} "
                    f"amendment {ref['amendment_designator']} — "
                    f"no matching section_amendment in data"
                )
                continue
            _insert_cb_row(conn, tcb_id, sa_id, entry)
        elif kind == "range":
            sections = _sections_in_part(conn, ref["authority"], ref["part"])
            if not sections:
                failures.append(
                    f"{tcds_number}: range ref over "
                    f"{ref['authority']} part '{ref['part']}' — "
                    f"no sections of that part in data"
                )
                continue
            for sec in sections:
                sa_id = _section_amendment_id_for_ordinal(
                    conn,
                    ref["authority"],
                    ref["part"],
                    sec,
                    ref["to_amendment_ordinal"],
                )
                if sa_id is None:
                    continue
                _insert_cb_row(conn, tcb_id, sa_id, entry)
    return failures


def _insert_aircraft(
    conn: sqlite3.Connection, aircraft_docs: list[dict]
) -> list[str]:
    failures: list[str] = []
    for doc in aircraft_docs:
        mfr_id = _upsert_manufacturer(conn, doc["manufacturer"])
        cur = conn.execute(
            "INSERT INTO aircraft_models "
            "(manufacturer_id, model_designation, common_name, notes) "
            "VALUES (?, ?, ?, ?)",
            (
                mfr_id,
                doc["model_designation"],
                doc.get("common_name"),
                doc.get("notes"),
            ),
        )
        model_id = cur.lastrowid
        assert model_id is not None

        for cat_code in doc.get("categories", []):
            cat_id = _upsert_category(conn, cat_code)
            conn.execute(
                "INSERT OR IGNORE INTO model_categories (model_id, category_id) "
                "VALUES (?, ?)",
                (model_id, cat_id),
            )

        for tcb_entry in doc["tcb"]:
            tcds_doc = tcb_entry["tcds"]
            auth_id = _upsert_authority(conn, tcds_doc["authority"])
            conn.execute(
                "INSERT OR IGNORE INTO tcds "
                "(authority_id, tcds_number, revision, revision_date, source_url) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    auth_id,
                    tcds_doc["tcds_number"],
                    tcds_doc.get("revision"),
                    tcds_doc.get("revision_date"),
                    tcds_doc.get("source_url"),
                ),
            )
            tcds_row = conn.execute(
                "SELECT id FROM tcds WHERE authority_id = ? AND tcds_number = ?",
                (auth_id, tcds_doc["tcds_number"]),
            ).fetchone()
            assert tcds_row is not None
            tcds_id = tcds_row[0]

            cur2 = conn.execute(
                "INSERT INTO tcb (model_id, tcds_id, notes) VALUES (?, ?, ?)",
                (model_id, tcds_id, tcb_entry.get("notes")),
            )
            tcb_id = cur2.lastrowid
            assert tcb_id is not None

            for entry in tcb_entry["certification_basis"]:
                failures.extend(
                    _expand_and_insert_entry(
                        conn, tcb_id, entry, tcds_doc["tcds_number"]
                    )
                )
    return failures


# ---------------------------------------------------------------------------
# Build report & helpers


def _build_report(
    conn: sqlite3.Connection, unresolved: list[str]
) -> dict[str, object]:
    def count(table: str) -> int:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    return {
        "naa_authorities": count("naa_authorities"),
        "manufacturers": count("manufacturers"),
        "categories": count("categories"),
        "regulation_parts": count("regulation_parts"),
        "regulations": count("regulations"),
        "amendments": count("amendments"),
        "section_amendments": count("section_amendments"),
        "aircraft_models": count("aircraft_models"),
        "tcds": count("tcds"),
        "tcb": count("tcb"),
        "cert_basis_entries": count("cert_basis_entries"),
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
        _insert_regulation_parts(conn, _load_regulation_parts(data_dir))
        _insert_regulations(conn, _load_regulations(data_dir))
        unresolved = _insert_aircraft(conn, _load_aircraft(data_dir))
        report = _build_report(conn, unresolved)
        conn.commit()
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except BuildError:
        conn.close()
        _remove_sqlite_file(tmp)
        raise
    except Exception:
        conn.close()
        _remove_sqlite_file(tmp)
        raise
    finally:
        conn.close()

    if unresolved:
        _remove_sqlite_file(tmp)
        raise BuildError(unresolved)

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
        f"(parts={report['regulation_parts']}, "
        f"amendments={report['amendments']}, "
        f"section_amendments={report['section_amendments']}, "
        f"models={report['aircraft_models']}, "
        f"tcb={report['tcb']}, "
        f"entries={report['cert_basis_entries']})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
