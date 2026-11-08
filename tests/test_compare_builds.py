"""Tests for scripts/compare_builds.py's DB diff (the refactor gate)."""

import sqlite3
from pathlib import Path

from scripts.compare_builds import diff_dbs


def _db(path: Path, rows: list[tuple[int, str]], built_at: str = "t0") -> Path:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE t (id INTEGER, v TEXT)")
        conn.execute("CREATE TABLE build_info (built_at TEXT)")
        conn.executemany("INSERT INTO t VALUES (?, ?)", rows)
        conn.execute("INSERT INTO build_info VALUES (?)", (built_at,))
    return path


def test_identical_ignores_build_info_and_row_order(tmp_path: Path) -> None:
    old = _db(tmp_path / "a.sqlite", [(1, "x"), (2, "y")], "t0")
    new = _db(tmp_path / "b.sqlite", [(2, "y"), (1, "x")], "t1")
    assert diff_dbs(old, new) == []


def test_reports_added_and_removed_rows(tmp_path: Path) -> None:
    old = _db(tmp_path / "a.sqlite", [(1, "x"), (2, "y")])
    new = _db(tmp_path / "b.sqlite", [(1, "x"), (2, "z")])
    assert diff_dbs(old, new) == [
        "t: 1 row(s) removed, 1 added",
        "  - (2, 'y')",
        "  + (2, 'z')",
    ]


def test_duplicate_rows_count(tmp_path: Path) -> None:
    old = _db(tmp_path / "a.sqlite", [(1, "x")])
    new = _db(tmp_path / "b.sqlite", [(1, "x"), (1, "x")])
    assert diff_dbs(old, new)[0] == "t: 0 row(s) removed, 1 added"


def test_schema_change_reported(tmp_path: Path) -> None:
    old = _db(tmp_path / "a.sqlite", [])
    new = _db(tmp_path / "b.sqlite", [])
    with sqlite3.connect(new) as conn:
        conn.execute("CREATE TABLE extra (x INTEGER)")
    assert diff_dbs(old, new) == ["schema (DDL) differs", "extra: only in new build"]
