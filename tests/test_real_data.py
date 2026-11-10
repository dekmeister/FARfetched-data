"""The real checked-in data/ builds and known queries hold (all slow)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import factories as fx
import pytest

from certbuild.sources import REPO_ROOT


# ---------------------------------------------------------------------------
# real checked-in data


# (real_db: tests/conftest.py, built once per session.)


class TestRealDataBuild:
    def test_tables_and_views(self, real_db: Path) -> None:
        with sqlite3.connect(real_db) as conn:
            objects = {
                (t, n)
                for t, n in conn.execute(
                    "SELECT type, name FROM sqlite_master WHERE type IN "
                    "('table', 'view')"
                )
            }
        assert {n for t, n in objects if t == "view"} == {"latest_versions"}
        shadow = ("search_text_", "search_aircraft_")
        assert {n for t, n in objects if t == "table" and not n.startswith(shadow)} == {
            "build_info",
            "cert_basis_citations",
            "cert_basis_citation_gaps",
            "issuers",
            "documents",
            "document_revisions",
            "provisions",
            "provision_versions",
            "provision_paragraphs",
            "version_actions",
            "manufacturers",
            "categories",
            "aircraft_models",
            "tcds",
            "tcb",
            "tcb_categories",
            "cert_basis_entries",
            "cert_basis_refs",
            "cert_basis_ref_provisions",
            "cert_basis_ref_skips",
            "cert_basis_resolved",
            "provision_similarity",
            "search_text",
            "search_current",
            "search_aircraft",
        }

    def test_23_1309_paragraph_paths(self, real_db: Path) -> None:
        # §23.1309 at 23-62: intro text, then (a)(1)-(2), (b), (c)(1)-(3), (d).
        with sqlite3.connect(real_db) as conn:
            rows = conn.execute(
                "SELECT pp.depth, pp.path FROM provision_paragraphs pp "
                "JOIN latest_versions lv ON lv.id = pp.provision_version_id "
                "JOIN provisions p ON p.id = lv.provision_id "
                "JOIN documents d ON d.id = p.document_id "
                "WHERE d.slug = '23' AND p.number = '1309' ORDER BY pp.seq"
            ).fetchall()
        assert rows[:6] == [
            (0, None),
            (1, "(a)"),
            (2, "(a)(1)"),
            (2, "(a)(2)"),
            (1, "(b)"),
            (1, "(c)"),
        ]
        assert (2, "(c)(3)") in rows

    def test_every_live_version_has_paragraphs(self, real_db: Path) -> None:
        with sqlite3.connect(real_db) as conn:
            orphans = conn.execute(
                "SELECT count(*) FROM provision_versions pv WHERE NOT pv.deleted "
                "AND NOT EXISTS (SELECT 1 FROM provision_paragraphs pp "
                "WHERE pp.provision_version_id = pv.id)"
            ).fetchone()[0]
        assert orphans == 0

    def test_tcds_lines_are_numbered_from_one(self, real_db: Path) -> None:
        # One entry per TCDS line: every TCB's display_order runs 1..n.
        with sqlite3.connect(real_db) as conn:
            gaps = conn.execute(
                "SELECT tcb_id FROM cert_basis_entries GROUP BY tcb_id "
                "HAVING min(display_order) != 1 OR max(display_order) != count(*)"
            ).fetchall()
        assert gaps == []

    def test_no_unresolved_references(self, real_db: Path) -> None:
        report = json.loads((real_db.parent / "cert_basis_report.json").read_text())
        assert report["unresolved_references"] == []

    def test_172_basis_resolves_to_car_3_through_3_12(self, real_db: Path) -> None:
        resolved = fx.resolved(real_db, "3A12", "172")
        assert resolved
        assert {order for order, _, _, _ in resolved} == {1}
        assert all(d.startswith("CAR3-") for _, _, d, _ in resolved)
        assert (1, "0", "CAR3-12", None) in resolved
        cap = _ordinal(real_db, "CAR3-12")
        assert max(_ordinal(real_db, d) for _, _, d, _ in resolved) <= cap

    def test_issuers_carry_succession(self, real_db: Path) -> None:
        with sqlite3.connect(real_db) as conn:
            rows = dict(
                conn.execute(
                    "SELECT i.code, s.code FROM issuers i "
                    "LEFT JOIN issuers s ON s.id = i.successor_id"
                ).fetchall()
            )
        assert rows == {
            "FAA": None,
            "CAA": "FAA",
            "CAB": "FAA",
            "EASA": None,
            "DOD": None,
            "NATO": None,
        }

    def test_text_missing_flag_matches_sentinel(self, real_db: Path) -> None:
        with sqlite3.connect(real_db) as conn:
            flagged, sentinel = conn.execute(
                "SELECT sum(text_missing), sum(text = 'TEXT MISSING') "
                "FROM provision_versions"
            ).fetchone()
        assert flagged == sentinel


# ---------------------------------------------------------------------------
# first real trace: Diamond DA 40, TCDS A47CE Rev 17


DA40 = (
    REPO_ROOT / "data" / "aircraft" / "diamond-aircraft-industries-inc" / "da-40.json"
)


def _ordinal(db: Path, designator: str) -> int:
    with sqlite3.connect(db) as conn:
        return conn.execute(
            "SELECT ordinal FROM document_revisions WHERE designator = ?",
            (designator,),
        ).fetchone()[0]


@pytest.mark.skipif(not DA40.exists(), reason="DA 40 not promoted into data/ yet")
class TestDA40Trace:
    """Two serial-scoped TCDS lines (Austria: display 2; Canada: display 6),
    each holding 14 CFR 23 through 23-51."""

    def test_both_scopes_hold_the_same_set_through_23_51(self, real_db: Path) -> None:
        resolved = fx.resolved(real_db, "A47CE", "DA 40")
        by_line: dict[int, set[tuple[str, str]]] = {}
        for order, number, designator, _ in resolved:
            by_line.setdefault(order, set()).add((number, designator))
        assert set(by_line) == {2, 3, 6, 7}  # Part 23 and Part 36, each scope
        assert by_line[2] == by_line[6]
        assert by_line[3] == by_line[7]
        assert max(_ordinal(real_db, d) for _, _, d, _ in resolved) <= 51

    @pytest.mark.parametrize(
        ("number", "designator"),
        [("1305", "23-51"), ("1191", "23-51"), ("561", "23-48"), ("1585", "23-50")],
    )
    def test_spot_checks(self, real_db: Path, number: str, designator: str) -> None:
        assert (2, number, designator, None) in fx.resolved(real_db, "A47CE", "DA 40")

    def test_provisions_after_23_51_are_not_in_the_basis(self, real_db: Path) -> None:
        with sqlite3.connect(real_db) as conn:
            later = {
                n
                for (n,) in conn.execute(
                    "SELECT p.number FROM provisions p "
                    "JOIN documents d ON d.id = p.document_id WHERE d.slug = '23' "
                    "AND NOT EXISTS (SELECT 1 FROM provision_versions pv "
                    "JOIN document_revisions dr ON dr.id = pv.revision_id "
                    "WHERE pv.provision_id = p.id AND dr.ordinal <= 51)"
                )
            }
        assert later
        assert not later & {n for _, n, _, _ in fx.resolved(real_db, "A47CE", "DA 40")}

    def test_only_the_part_23_and_36_lines_carry_refs(self, real_db: Path) -> None:
        # JAR 23 (not in the dataset), special conditions and ELOS
        # lines are kept as entries but reference nothing.
        with sqlite3.connect(real_db) as conn:
            rows = conn.execute(
                "SELECT e.display_order, e.entry_type, count(r.id) "
                "FROM cert_basis_entries e "
                "JOIN tcb ON tcb.id = e.tcb_id JOIN tcds ON tcds.id = tcb.tcds_id "
                "JOIN aircraft_models m ON m.id = tcb.model_id "
                "LEFT JOIN cert_basis_refs r ON r.entry_id = e.id "
                "WHERE tcds.tcds_number = 'A47CE' AND m.model_designation = 'DA 40' "
                "GROUP BY e.id"
            ).fetchall()
        with_refs = {(order, kind, n) for order, kind, n in rows if n}
        assert with_refs == {
            (2, "regulation", 1),
            (3, "regulation", 1),
            (6, "regulation", 1),
            (7, "regulation", 1),
        }
        assert len(rows) > len(with_refs)
