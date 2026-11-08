"""The release gate refuses a build that fails an integrity check."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from certbuild.ddl import SCHEMA_VERSION
from scripts.check_release import problems

GOOD = {
    "schema_version": SCHEMA_VERSION,
    "git_dirty": False,
    "unresolved_references": [],
}


def _build(
    tmp_path: Path, *, version: int = SCHEMA_VERSION, sha: str = "abc", **report: object
) -> tuple[Path, Path]:
    db = tmp_path / "b.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE build_info (git_sha TEXT)")
        conn.execute("INSERT INTO build_info VALUES (?)", (sha,))
        conn.execute(f"PRAGMA user_version = {int(version)}")
    path = tmp_path / "r.json"
    path.write_text(json.dumps({"git_dirty_paths": [], **GOOD, **report}))
    return db, path


def test_a_good_build_passes(tmp_path: Path) -> None:
    assert problems(*_build(tmp_path), "abc") == []


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"version": 1}, "user_version"),
        ({"sha": "other"}, "built from other"),
        ({"git_dirty": True}, "not clean"),
        ({"git_dirty": None}, "not clean"),
        ({"unresolved_references": ["x"]}, "1 unresolved"),
    ],
)
def test_a_bad_build_is_refused(
    change: dict[str, object], message: str, tmp_path: Path
) -> None:
    found = problems(*_build(tmp_path, **change), "abc")  # type: ignore[arg-type]
    assert any(message in p for p in found)
