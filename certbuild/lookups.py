"""Closed sets (issuers, categories) seeded up front, and id lookups."""

from __future__ import annotations

import sqlite3

from certbuild.errors import BuildError


# Closed set of issuers: (name, kind, country, successor code). Must match the
# `issuer` enum in schemas/common.schema.json. Successors must come first.
_ISSUERS: dict[str, tuple[str, str, str | None, str | None]] = {
    "FAA": ("Federal Aviation Administration", "naa", "US", None),
    "CAA": ("Civil Aeronautics Administration", "naa", "US", "FAA"),
    "CAB": ("Civil Aeronautics Board", "naa", "US", "FAA"),
    "EASA": ("European Union Aviation Safety Agency", "naa", "EU", None),
    "DOD": ("U.S. Department of Defense", "military", "US", None),
    "NATO": ("North Atlantic Treaty Organization", "military", None, None),
}

# Closed set of airworthiness categories. Must match the `categories` enum in
# schemas/aircraft_model.schema.json.
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


def _seed_lookups(conn: sqlite3.Connection) -> None:
    for code, (name, kind, country, successor) in _ISSUERS.items():
        successor_id = _issuer_id(conn, successor) if successor else None
        conn.execute(
            "INSERT INTO issuers (code, name, kind, country, successor_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (code, name, kind, country, successor_id),
        )
    conn.executemany(
        "INSERT INTO categories (code, name) VALUES (?, ?)",
        _CATEGORY_NAMES.items(),
    )


def _issuer_id(conn: sqlite3.Connection, code: str) -> int:
    row = conn.execute("SELECT id FROM issuers WHERE code = ?", (code,)).fetchone()
    if row is None:
        raise BuildError([f"unknown issuer {code!r}"])
    return row[0]


def _category_id(conn: sqlite3.Connection, code: str) -> int:
    row = conn.execute("SELECT id FROM categories WHERE code = ?", (code,)).fetchone()
    if row is None:
        raise BuildError([f"unknown category {code!r}"])
    return row[0]


def _upsert_manufacturer(conn: sqlite3.Connection, name: str) -> int:
    conn.execute("INSERT OR IGNORE INTO manufacturers (name) VALUES (?)", (name,))
    row = conn.execute(
        "SELECT id FROM manufacturers WHERE name = ?", (name,)
    ).fetchone()
    assert row is not None
    return row[0]
