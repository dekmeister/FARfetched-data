"""The full-text search tables (docs/SQLITE.md §Search)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import factories as fx


def _prov(number: str, versions: list[dict[str, Any]]) -> dict[str, Any]:
    return fx.provision("FAA", "23", number, versions)


def _v(designator: str, text: str = "Each fuel tank is vented.", **extra: Any) -> Any:
    return fx.version(designator, text=text, **extra)


def _alias(designator: str, target: str) -> dict[str, Any]:
    return {
        "designator": designator,
        "title_at_revision": "Title",
        "same_as_designator": target,
    }


def _build(tmp_path: Path, provisions: list[dict[str, Any]], *aircraft: Any) -> Path:
    return fx.build_tree(
        tmp_path, [fx.faa_part("23", [0, 1, 2])], provisions, list(aircraft)
    )


def _version_ids(db: Path, table_sql: str) -> set[str]:
    """Designators of the versions a query's ids point at."""
    with sqlite3.connect(db) as conn:
        return {
            r[0]
            for r in conn.execute(
                "SELECT dr.designator FROM provision_versions pv "
                "JOIN document_revisions dr ON dr.id = pv.revision_id "
                f"WHERE pv.id IN ({table_sql})"
            )
        }


class TestSearchText:
    def test_one_row_per_version_with_its_own_text(self, tmp_path: Path) -> None:
        db = _build(
            tmp_path,
            [
                _prov(
                    "1",
                    [
                        _v("23-0"),
                        _alias("23-1", "23-0"),
                        _v("23-2", "Reworded."),
                    ],
                )
            ],
        )
        assert _version_ids(db, "SELECT rowid FROM search_text") == {"23-0", "23-2"}

    def test_deletions_are_not_indexed(self, tmp_path: Path) -> None:
        db = _build(tmp_path, [_prov("1", [_v("23-0"), fx.deleted("23-1")])])
        assert _version_ids(db, "SELECT rowid FROM search_text") == {"23-0"}

    def test_text_missing_keeps_the_title_only(self, tmp_path: Path) -> None:
        db = _build(
            tmp_path, [_prov("1", [_v("23-0", "TEXT MISSING", title="Fuel vents")])]
        )
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT title, body FROM search_text").fetchall() == [
                ("Fuel vents", "")
            ]

    def test_body_has_no_markup(self, tmp_path: Path) -> None:
        text = "(a) V_{MO} and x^{2}.\n$$ a = b $$\n{| Caption\n! Head\n| cell\n|}"
        db = _build(tmp_path, [_prov("1", [_v("23-0", text)])])
        with sqlite3.connect(db) as conn:
            body = conn.execute("SELECT body FROM search_text").fetchone()[0]
            found = conn.execute(
                "SELECT count(*) FROM search_text WHERE search_text MATCH 'VMO'"
            ).fetchone()[0]
        for mark in ("_{", "^{", "$$", "{|", "|}", "!"):
            assert mark not in body
        assert "VMO" in body and found == 1

    def test_control_characters_are_removed(self, tmp_path: Path) -> None:
        db = _build(tmp_path, [_prov("1", [_v("23-0", "fuel\x02 tank\x03 vent")])])
        with sqlite3.connect(db) as conn:
            body = conn.execute("SELECT body FROM search_text").fetchone()[0]
        assert body == "fuel tank vent"

    def test_stemming(self, tmp_path: Path) -> None:
        db = _build(tmp_path, [_prov("1", [_v("23-0", "Each fuel tank.")])])
        with sqlite3.connect(db) as conn:
            assert conn.execute(
                "SELECT count(*) FROM search_text WHERE search_text MATCH 'tanks'"
            ).fetchone() == (1,)


class TestSearchCurrent:
    def test_latest_text(self, tmp_path: Path) -> None:
        db = _build(tmp_path, [_prov("1", [_v("23-0"), _v("23-1", "New.")])])
        assert _version_ids(db, "SELECT version_id FROM search_current") == {"23-1"}

    def test_follows_an_alias_chain_to_the_text(self, tmp_path: Path) -> None:
        db = _build(
            tmp_path,
            [
                _prov(
                    "1",
                    [
                        _v("23-0"),
                        _alias("23-1", "23-0"),
                        _alias("23-2", "23-1"),
                    ],
                )
            ],
        )
        assert _version_ids(db, "SELECT version_id FROM search_current") == {"23-0"}

    def test_deleted_provision_has_no_current_text(self, tmp_path: Path) -> None:
        db = _build(tmp_path, [_prov("1", [_v("23-0"), fx.deleted("23-1")])])
        with sqlite3.connect(db) as conn:
            assert conn.execute("SELECT count(*) FROM search_current").fetchone() == (
                0,
            )


class TestSearchAircraft:
    def test_row_per_tcb_with_basis_lines(self, tmp_path: Path) -> None:
        db = _build(
            tmp_path,
            [_prov("1", [_v("23-0")])],
            fx.cfr_aircraft(
                [fx.entry([], 1, raw_reference="Part 23 through 23-ACE-52")],
                model="SR22",
            ),
        )
        with sqlite3.connect(db) as conn:
            row = conn.execute(
                "SELECT designation, tcds_number, basis FROM search_aircraft "
                "WHERE search_aircraft MATCH '\"23-ACE-52\"'"
            ).fetchall()
        assert row == [("SR22", "DUMMY1", "Part 23 through 23-ACE-52")]


def test_report_counts_search_and_leaves_out_shadow_tables(tmp_path: Path) -> None:
    db = _build(tmp_path, [_prov("1", [_v("23-0", "TEXT MISSING")])])
    report = json.loads((tmp_path / "cert_basis_report.json").read_text())
    assert db.exists()
    assert report["search"] == {
        "text_rows": 1,
        "title_only_rows": 1,
        "current_rows": 1,
        "aircraft_rows": 0,
    }
    assert "search_text" in report["tables"]
    assert "search_text_data" not in report["tables"]
