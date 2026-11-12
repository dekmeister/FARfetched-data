"""The SQLite contract with consumers (docs/SQLITE.md)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import factories as fx
import pytest

from certbuild.ddl import SCHEMA_VERSION
from certbuild.keys import sort_key
from certbuild.pipeline import build


# ---------------------------------------------------------------------------
# the contract with consumers


class TestContract:
    @pytest.fixture
    def db(self, tmp_path: Path) -> Path:
        return fx.build_part23(tmp_path, [fx.cfr_provision("23", "1", [0])], [])

    def test_user_version_and_build_info(self, db: Path) -> None:
        with sqlite3.connect(db) as conn:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            rows = conn.execute(
                "SELECT schema_version, built_at FROM build_info"
            ).fetchall()
        assert len(rows) == 1 and rows[0][0] == SCHEMA_VERSION

    def test_single_file_delete_journal(self, db: Path) -> None:
        with sqlite3.connect(db) as conn:
            assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert sorted(p.name for p in db.parent.iterdir() if "sqlite" in p.name) == [
            "cert_basis.sqlite"
        ]

    def test_every_table_is_strict(self, db: Path) -> None:
        with sqlite3.connect(db) as conn:
            tables = conn.execute(
                "SELECT name, strict FROM pragma_table_list "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        assert tables and all(strict for _, strict in tables), tables

    def test_db_rejects_cross_document_version(self, tmp_path: Path) -> None:
        data = fx.stage(
            tmp_path,
            [fx.faa_part("23", [0]), fx.faa_part("25", [0])],
            [fx.cfr_provision("23", "1", [0])],
            [],
        )
        out = tmp_path / "cert_basis.sqlite"
        build(data, out)
        with sqlite3.connect(out) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            (doc23, prov), rev25 = (
                conn.execute("SELECT document_id, id FROM provisions").fetchone(),
                conn.execute(
                    "SELECT dr.id FROM document_revisions dr "
                    "JOIN documents d ON d.id = dr.document_id WHERE d.slug = '25'"
                ).fetchone()[0],
            )
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO provision_versions (document_id, provision_id, "
                    "revision_id, title_at_revision, text, provenance) "
                    "VALUES (?, ?, ?, 't', 'x', 'scraped')",
                    (doc23, prov, rev25),
                )

    def test_db_rejects_malformed_date(self, db: Path) -> None:
        with sqlite3.connect(db) as conn:
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "UPDATE document_revisions SET effective_date = '1970-13-01'"
                )

    def test_categories_are_per_tcb(self, tmp_path: Path) -> None:
        # One model, validated by a second regulator that states another
        # category: each TCB keeps what its own TCDS says.
        entry = {
            "display_order": 1,
            "entry_type": "other",
            "raw_reference": "x",
            "applicability": None,
            "applicability_notes": None,
            "references": [],
        }
        aircraft = fx.cfr_aircraft([entry])
        easa_tcb = {
            "tcds": {"issuer": "EASA", "tcds_number": "EASA.A.000", "holder": "Dummy"},
            "categories": ["commuter"],
            "notes": None,
            "certification_basis": [entry],
        }
        aircraft["tcb"].append(easa_tcb)
        data = fx.stage(tmp_path, [fx.faa_part("23", [0])], [], [aircraft])
        out = tmp_path / "cert_basis.sqlite"
        build(data, out)
        with sqlite3.connect(out) as conn:
            rows = conn.execute(
                "SELECT tcds.tcds_number, c.code FROM tcb_categories tc "
                "JOIN tcb ON tcb.id = tc.tcb_id JOIN tcds ON tcds.id = tcb.tcds_id "
                "JOIN categories c ON c.id = tc.category_id ORDER BY 1"
            ).fetchall()
        assert rows == [("DUMMY1", "normal"), ("EASA.A.000", "commuter")]

    def test_group_legal_name_and_printed_holder_are_kept(self, tmp_path: Path) -> None:
        # Two legally separate companies shown as one group; each TCDS keeps
        # the holder it prints.
        a = fx.cfr_aircraft([fx.entry([])], model="G150")
        a["manufacturer"] = "Gulfstream Aerospace LP (GALP)"
        a["manufacturer_group"] = "Gulfstream"
        a["tcb"][0]["tcds"]["holder"] = "Gulfstream Aerospace LP"
        b = fx.cfr_aircraft(
            [fx.entry([])], model="G500", tcds={"issuer": "FAA", "tcds_number": "X2"}
        )
        b["manufacturer"] = "Gulfstream Aerospace Corporation"
        b["manufacturer_group"] = "Gulfstream"
        b["tcb"][0]["tcds"]["holder"] = "Gulfstream Aerospace Corporation"
        data = fx.stage(tmp_path, [fx.faa_part("23", [0])], [], [a, b])
        out = tmp_path / "cert_basis.sqlite"
        build(data, out)
        with sqlite3.connect(out) as conn:
            rows = conn.execute(
                "SELECT mf.group_name, mf.name, t.holder FROM tcb "
                "JOIN aircraft_models m ON m.id = tcb.model_id "
                "JOIN manufacturers mf ON mf.id = m.manufacturer_id "
                "JOIN tcds t ON t.id = tcb.tcds_id ORDER BY mf.name"
            ).fetchall()
        assert rows == [
            (
                "Gulfstream",
                "Gulfstream Aerospace Corporation",
                "Gulfstream Aerospace Corporation",
            ),
            ("Gulfstream", "Gulfstream Aerospace LP (GALP)", "Gulfstream Aerospace LP"),
        ]

    def test_provenance_carried_into_db(self, tmp_path: Path) -> None:
        prov = fx.cfr_provision("23", "1", [])
        prov["versions"] = [fx.cfr_version("23-0", provenance={"source": "ocr"})]
        out = fx.build_part23(tmp_path, [prov], [])
        with sqlite3.connect(out) as conn:
            assert conn.execute(
                "SELECT provenance FROM provision_versions"
            ).fetchall() == [("ocr",)]


@pytest.mark.parametrize(
    ("number", "key"),
    [
        ("175", "000175"),
        ("1309", "001309"),
        ("A23", "A000023"),
        ("4.10", "000004.000010"),
    ],
)
def test_sort_key(number: str, key: str) -> None:
    assert sort_key(number) == key
