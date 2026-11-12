"""Closed sets (issuers, categories), seeded up front, and id lookups.

Each set must equal its schema enum (schemas/common.schema.json `issuer`,
schemas/aircraft_model.schema.json `categories`); tests/test_validation.py
checks that they agree.
"""

from __future__ import annotations

import sqlite3

from certbuild.errors import BuildError


# Closed set of issuers: (name, kind, country, successor code). Must match the
# `issuer` enum in schemas/common.schema.json. Successors must come first.
ISSUERS: dict[str, tuple[str, str, str | None, str | None]] = {
    "FAA": ("Federal Aviation Administration", "naa", "US", None),
    "CAA": ("Civil Aeronautics Administration", "naa", "US", "FAA"),
    "CAB": ("Civil Aeronautics Board", "naa", "US", "FAA"),
    "EASA": ("European Union Aviation Safety Agency", "naa", "EU", None),
    "DOD": ("U.S. Department of Defense", "military", "US", None),
    "NATO": ("North Atlantic Treaty Organization", "military", None, None),
}

# Closed set of airworthiness categories. Must match the `categories` enum in
# schemas/aircraft_model.schema.json.
CATEGORY_NAMES: dict[str, str] = {
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


def seed_lookups(conn: sqlite3.Connection) -> None:
    for code, (name, kind, country, successor) in ISSUERS.items():
        successor_id = issuer_id_for(conn, successor) if successor else None
        conn.execute(
            "INSERT INTO issuers (code, name, kind, country, successor_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (code, name, kind, country, successor_id),
        )
    conn.executemany(
        "INSERT INTO categories (code, name) VALUES (?, ?)",
        CATEGORY_NAMES.items(),
    )


def issuer_id_for(conn: sqlite3.Connection, code: str) -> int:
    row = conn.execute("SELECT id FROM issuers WHERE code = ?", (code,)).fetchone()
    if row is None:
        raise BuildError([f"unknown issuer {code!r}"])
    return int(row[0])


def category_id_for(conn: sqlite3.Connection, code: str) -> int:
    row = conn.execute("SELECT id FROM categories WHERE code = ?", (code,)).fetchone()
    if row is None:
        raise BuildError([f"unknown category {code!r}"])
    return int(row[0])


def upsert_manufacturer(
    conn: sqlite3.Connection, name: str, group: str
) -> tuple[int, str]:
    """The manufacturer's id, and the group its first file gave it (a
    caller compares that with its own)."""
    conn.execute(
        "INSERT OR IGNORE INTO manufacturers (name, group_name) VALUES (?, ?)",
        (name, group),
    )
    row = conn.execute(
        "SELECT id, group_name FROM manufacturers WHERE name = ?", (name,)
    ).fetchone()
    assert row is not None
    return int(row[0]), str(row[1])
