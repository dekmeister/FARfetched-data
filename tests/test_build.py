"""Tests for SQLite emission in build.py."""

from __future__ import annotations

import json
import sqlite3
import subprocess
from pathlib import Path

import pytest

from build import (
    REPO_ROOT,
    SCHEMA_VERSION,
    BuildError,
    build,
    check,
    main,
    sort_key,
)

# ---------------------------------------------------------------------------
# helpers


def _document(slug: str, ordinals: list[int], issuer: str = "FAA") -> dict:
    return {
        "issuer": issuer,
        "doc_kind": "regulation",
        "code": f"14 CFR {slug}",
        "slug": slug,
        "title": None,
        "revisions": [
            {
                "designator": f"{slug}-{n}",
                "ordinal": n,
                "effective_date": f"{1965 + n // 2:04d}-01-01",
            }
            for n in ordinals
        ],
    }


def _version(designator: str, **extra: object) -> dict:
    return {
        "designator": designator,
        "title_at_revision": "Dummy title",
        "text": f"text at {designator}",
        "publication_cite": "1 FR 1",
        "source_url": "https://example.com",
        **extra,
    }


def _provision(slug: str, number: str, ordinals: list[int]) -> dict:
    return {
        "issuer": "FAA",
        "document": slug,
        "key": number,
        "number": number,
        "current_grouping": "A",
        "canonical_title": f"Dummy §{slug}.{number}",
        "versions": [_version(f"{slug}-{n}") for n in ordinals],
    }


def _entry(refs: list[dict], display_order: int = 1, **extra: object) -> dict:
    return {
        "display_order": display_order,
        "entry_type": "regulation",
        "raw_reference": "verbatim TCDS text",
        "applicability": None,
        "applicability_notes": None,
        "references": refs,
        **extra,
    }


def _ref(to: str, document: str = "23", **extra: object) -> dict:
    return {"issuer": "FAA", "document": document, "to": to, **extra}


def _aircraft(
    entries: list[dict], model: str = "DummyModel", tcds: dict | None = None
) -> dict:
    return {
        "manufacturer": "Dummy Mfg",
        "model_designation": model,
        "common_name": None,
        "notes": None,
        "tcb": [
            {
                "tcds": tcds or {"issuer": "FAA", "tcds_number": "DUMMY1"},
                "categories": ["normal"],
                "notes": None,
                "certification_basis": entries,
            }
        ],
    }


def _stage(
    tmp_path: Path,
    documents: list[dict],
    provisions: list[dict],
    aircraft: list[dict],
) -> Path:
    data = tmp_path / "data"
    for d in documents:
        doc_dir = data / "documents" / d["issuer"].lower() / d["slug"]
        doc_dir.mkdir(parents=True, exist_ok=True)
        (doc_dir / "_document.json").write_text(json.dumps(d))
    for p in provisions:
        doc_dir = data / "documents" / p["issuer"].lower() / p["document"]
        doc_dir.mkdir(parents=True, exist_ok=True)
        (doc_dir / f"{p['key']}.json").write_text(json.dumps(p))
    (data / "aircraft").mkdir(parents=True, exist_ok=True)
    for a in aircraft:
        slug = a["model_designation"].replace(" ", "-").lower()
        (data / "aircraft" / f"{slug}.json").write_text(json.dumps(a))
    return data


def _resolved(
    out: Path, tcds_number: str | None = None, model: str | None = None
) -> set[tuple[int, str, str, str | None]]:
    """(display_order, provision number, designator, paragraph) per resolved row,
    optionally only for one TCDS and/or one model designation (a TCDS covers
    many models, each with its own TCB)."""
    with sqlite3.connect(out) as conn:
        rows = conn.execute(
            """
            SELECT e.display_order, p.number, dr.designator, r.paragraph
            FROM cert_basis_resolved r
            JOIN cert_basis_entries e ON e.id = r.entry_id
            JOIN tcb ON tcb.id = e.tcb_id
            JOIN tcds ON tcds.id = tcb.tcds_id
            JOIN aircraft_models m ON m.id = tcb.model_id
            JOIN provision_versions pv ON pv.id = r.provision_version_id
            JOIN provisions p ON p.id = pv.provision_id
            JOIN document_revisions dr ON dr.id = pv.revision_id
            WHERE (?1 IS NULL OR tcds.tcds_number = ?1)
              AND (?2 IS NULL OR m.model_designation = ?2)
            """,
            (tcds_number, model),
        ).fetchall()
    return set(rows)


def _build_basis(tmp_path: Path, provisions: list[dict], entries: list[dict]) -> Path:
    """Build Part 23 with revisions 0..62, plus one aircraft if `entries`."""
    data = _stage(
        tmp_path,
        [_document("23", list(range(63)))],
        provisions,
        [_aircraft(entries)] if entries else [],
    )
    out = tmp_path / "cert_basis.sqlite"
    build(data, out)
    return out


def _basis_fails(tmp_path: Path, provisions: list[dict], entries: list[dict]) -> str:
    with pytest.raises(BuildError) as ei:
        _build_basis(tmp_path, provisions, entries)
    assert not (tmp_path / "cert_basis.sqlite").exists()
    return str(ei.value)


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
        assert {n for t, n in objects if t == "table"} == {
            "build_info",
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
        resolved = _resolved(real_db, "3A12", "172")
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
        resolved = _resolved(real_db, "A47CE", "DA 40")
        by_line: dict[int, set[tuple[str, str]]] = {}
        for order, number, designator, _ in resolved:
            by_line.setdefault(order, set()).add((number, designator))
        assert set(by_line) == {2, 6}
        assert by_line[2] == by_line[6]
        assert max(_ordinal(real_db, d) for _, _, d, _ in resolved) <= 51

    @pytest.mark.parametrize(
        ("number", "designator"),
        [("1305", "23-51"), ("1191", "23-51"), ("561", "23-48"), ("1585", "23-50")],
    )
    def test_spot_checks(self, real_db: Path, number: str, designator: str) -> None:
        assert (2, number, designator, None) in _resolved(real_db, "A47CE", "DA 40")

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
        assert not later & {n for _, n, _, _ in _resolved(real_db, "A47CE", "DA 40")}

    def test_only_the_part_23_lines_carry_refs(self, real_db: Path) -> None:
        # JAR 23, Part 36 (not in the dataset), special conditions and ELOS
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
        assert with_refs == {(2, "regulation", 1), (6, "regulation", 1)}
        assert len(rows) > len(with_refs)


# ---------------------------------------------------------------------------
# the contract with consumers


class TestContract:
    @pytest.fixture
    def db(self, tmp_path: Path) -> Path:
        return _build_basis(tmp_path, [_provision("23", "1", [0])], [])

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
        data = _stage(
            tmp_path,
            [_document("23", [0]), _document("25", [0])],
            [_provision("23", "1", [0])],
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
        aircraft = _aircraft([entry])
        easa_tcb = {
            "tcds": {"issuer": "EASA", "tcds_number": "EASA.A.000"},
            "categories": ["commuter"],
            "notes": None,
            "certification_basis": [entry],
        }
        aircraft["tcb"].append(easa_tcb)
        data = _stage(tmp_path, [_document("23", [0])], [], [aircraft])
        out = tmp_path / "cert_basis.sqlite"
        build(data, out)
        with sqlite3.connect(out) as conn:
            rows = conn.execute(
                "SELECT tcds.tcds_number, c.code FROM tcb_categories tc "
                "JOIN tcb ON tcb.id = tc.tcb_id JOIN tcds ON tcds.id = tcb.tcds_id "
                "JOIN categories c ON c.id = tc.category_id ORDER BY 1"
            ).fetchall()
        assert rows == [("DUMMY1", "normal"), ("EASA.A.000", "commuter")]

    def test_provenance_carried_into_db(self, tmp_path: Path) -> None:
        prov = _provision("23", "1", [])
        prov["versions"] = [_version("23-0", provenance={"source": "ocr"})]
        out = _build_basis(tmp_path, [prov], [])
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


# ---------------------------------------------------------------------------
# cert-basis resolution rules


class TestResolution:
    def test_range_takes_latest_version_up_to_to(self, tmp_path: Path) -> None:
        provs = [
            _provision("23", "1309", [0, 7, 14]),
            _provision("23", "9999", [20]),  # post-dates the range: not in basis
        ]
        out = _build_basis(tmp_path, provs, [_entry([_ref("23-13")])])
        assert _resolved(out) == {(1, "1309", "23-7", None)}

    def test_base_revision_is_always_included(self, tmp_path: Path) -> None:
        # "as amended by 23-1 thru 23-13" still includes text unchanged since 23-0.
        out = _build_basis(
            tmp_path, [_provision("23", "1", [0])], [_entry([_ref("23-13")])]
        )
        assert _resolved(out) == {(1, "1", "23-0", None)}

    def test_skipped_revision_falls_back_to_earlier_text(self, tmp_path: Path) -> None:
        # "23-1 thru 23-38, 23-40": a provision last changed at 23-39 keeps 23-0.
        provs = [_provision("23", "1", [0, 39]), _provision("23", "2", [0, 39, 40])]
        out = _build_basis(tmp_path, provs, [_entry([_ref("23-40", skip=["23-39"])])])
        assert _resolved(out) == {(1, "1", "23-0", None), (1, "2", "23-40", None)}

    def test_scoped_ref_overrides_document_wide(self, tmp_path: Path) -> None:
        # "... except 23.611 as amended through 23-54"
        provs = [_provision("23", "611", [0, 50]), _provision("23", "143", [0, 50])]
        refs = [_ref("23-40"), _ref("23-54", provisions=["611"])]
        out = _build_basis(tmp_path, provs, [_entry(refs)])
        assert _resolved(out) == {
            (1, "611", "23-50", None),
            (1, "143", "23-0", None),
        }

    def test_paragraph_ref_adds_a_row(self, tmp_path: Path) -> None:
        # "23.1309(a) as amended through 23-62, for PED tolerance only"
        refs = [_ref("23-54"), _ref("23-62", provisions=["1309"], paragraph="(a)")]
        out = _build_basis(
            tmp_path, [_provision("23", "1309", [0, 49, 62])], [_entry(refs)]
        )
        assert _resolved(out) == {
            (1, "1309", "23-49", None),
            (1, "1309", "23-62", "(a)"),
        }

    def test_paragraph_ref_on_same_version_is_dropped(self, tmp_path: Path) -> None:
        refs = [_ref("23-54"), _ref("23-62", provisions=["1309"], paragraph="(a)")]
        out = _build_basis(
            tmp_path, [_provision("23", "1309", [0, 49])], [_entry(refs)]
        )
        assert _resolved(out) == {(1, "1309", "23-49", None)}

    def test_exclude_removes_from_document_wide(self, tmp_path: Path) -> None:
        provs = [_provision("23", "1", [0]), _provision("23", "1419", [0])]
        refs = [
            _ref("23-13"),
            {
                "issuer": "FAA",
                "document": "23",
                "effect": "exclude",
                "provisions": ["1419"],
            },
        ]
        out = _build_basis(tmp_path, provs, [_entry(refs)])
        assert _resolved(out) == {(1, "1", "23-0", None)}

    def test_entries_resolve_independently(self, tmp_path: Path) -> None:
        # Two TCDS lines (e.g. two S/N ranges) may hold one provision at
        # different levels; overrides never cross lines.
        entries = [
            _entry([_ref("23-13")], display_order=1, applicability="S/N 1-99"),
            _entry([_ref("23-62")], display_order=2, applicability="S/N 100 and on"),
        ]
        out = _build_basis(tmp_path, [_provision("23", "1", [0, 50])], entries)
        assert _resolved(out) == {(1, "1", "23-0", None), (2, "1", "23-50", None)}

    def test_refs_and_children_are_stored(self, tmp_path: Path) -> None:
        refs = [_ref("23-40", skip=["23-39"]), _ref("23-54", provisions=["1"])]
        out = _build_basis(tmp_path, [_provision("23", "1", [0])], [_entry(refs)])
        with sqlite3.connect(out) as conn:
            counts = [
                conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                for t in (
                    "cert_basis_refs",
                    "cert_basis_ref_skips",
                    "cert_basis_ref_provisions",
                )
            ]
        assert counts == [2, 1, 1]

    def test_entry_without_references_is_kept(self, tmp_path: Path) -> None:
        entry = _entry([], entry_type="special_condition")
        out = _build_basis(tmp_path, [_provision("23", "1", [0])], [entry])
        with sqlite3.connect(out) as conn:
            assert conn.execute(
                "SELECT entry_type FROM cert_basis_entries"
            ).fetchall() == [("special_condition",)]
        assert _resolved(out) == set()


class TestAuthorityOnlyRevisions:
    """Amendments that changed no section (23-47: authority citation only) are
    declared in _document.json but have no provision versions. TCDS cite them
    as range endpoints ("23-1 thru 23-47"), so a ref must be able to name them
    and resolve exactly as it does for the revision before."""

    # 23-47 and 23-55 are declared but no provision has a version at them.
    ORDINALS = [n for n in range(63) if n not in (56, 60)]
    PROVS = [
        _provision("23", "1", [0, 46]),
        _provision("23", "2", [0, 30]),
        _provision("23", "3", [0, 51]),
    ]

    def _resolve(self, tmp_path: Path, refs: list[dict]) -> set:
        data = _stage(
            tmp_path,
            [_document("23", self.ORDINALS)],
            self.PROVS,
            [_aircraft([_entry(refs)])],
        )
        out = tmp_path / "cert_basis.sqlite"
        build(data, out)
        return _resolved(out)

    def test_ref_to_section_less_revision_resolves_like_the_one_before(
        self, tmp_path: Path
    ) -> None:
        at_47 = self._resolve(tmp_path / "a", [_ref("23-47")])
        at_46 = self._resolve(tmp_path / "b", [_ref("23-46")])
        assert (
            at_47
            == at_46
            == {
                (1, "1", "23-46", None),
                (1, "2", "23-30", None),
                (1, "3", "23-0", None),
            }
        )

    def test_skip_naming_a_section_less_revision_is_accepted(
        self, tmp_path: Path
    ) -> None:
        refs = [_ref("23-51", skip=["23-47"])]
        assert self._resolve(tmp_path, refs) == {
            (1, "1", "23-46", None),
            (1, "2", "23-30", None),
            (1, "3", "23-51", None),
        }

    def test_undeclared_number_is_still_rejected(self, tmp_path: Path) -> None:
        # 23-56 was never declared: nothing may name it, as a `to` or a `skip`.
        for refs, message in [
            ([_ref("23-56")], "unknown revision '23-56'"),
            ([_ref("23-57", skip=["23-56"])], "unknown skip revision '23-56'"),
        ]:
            data = _stage(
                tmp_path / message[:12],
                [_document("23", self.ORDINALS)],
                self.PROVS,
                [_aircraft([_entry(refs)])],
            )
            with pytest.raises(BuildError, match=message):
                build(data, tmp_path / "cert_basis.sqlite")


class TestResolutionFailures:
    PROVS = [_provision("23", "1", [0, 50]), _provision("23", "2", [0])]

    @pytest.mark.parametrize(
        ("refs", "message"),
        [
            ([_ref("23-99")], "unknown revision '23-99'"),
            ([_ref("23-40", skip=["23-99"])], "unknown skip revision '23-99'"),
            ([_ref("23-40", skip=["23-40"])], "not earlier than to"),
            ([_ref("23-40", provisions=["1234"])], "unknown provision 23.1234"),
            ([_ref("25-1", document="25")], "unknown document FAA/25"),
            ([_ref("23-62"), _ref("23-13")], "two document-wide refs"),
            (
                [_ref("23-62", provisions=["1"]), _ref("23-13", provisions=["1"])],
                "two scoped refs",
            ),
            (
                [
                    _ref("23-62", provisions=["1"]),
                    {
                        "issuer": "FAA",
                        "document": "23",
                        "effect": "exclude",
                        "provisions": ["1"],
                    },
                ],
                "both excluded and included",
            ),
            (
                [
                    _ref("23-62", provisions=["2"]),
                    {
                        "issuer": "FAA",
                        "document": "23",
                        "effect": "exclude",
                        "provisions": ["1"],
                    },
                ],
                "removes nothing",
            ),
            (
                [
                    {
                        "issuer": "FAA",
                        "document": "23",
                        "effect": "exclude",
                        "provisions": ["1"],
                    }
                ],
                "no include ref in 23 to read its number at",
            ),
        ],
    )
    def test_fails_loud(self, tmp_path: Path, refs: list[dict], message: str) -> None:
        assert message in _basis_fails(tmp_path, self.PROVS, [_entry(refs)])

    def test_include_resolving_to_nothing_fails(self, tmp_path: Path) -> None:
        provs = [_provision("23", "1", [50])]
        message = _basis_fails(tmp_path, provs, [_entry([_ref("23-13")])])
        assert "resolves to no provisions" in message


# ---------------------------------------------------------------------------
# fail-loud build checks


class TestBuildFailures:
    def test_undeclared_revision_fails(self, tmp_path: Path) -> None:
        data = _stage(
            tmp_path, [_document("25", [23])], [_provision("25", "1309", [99])], []
        )
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "cert_basis.sqlite")
        assert "25-99" in str(ei.value)

    def test_duplicate_version_names_the_file(self, tmp_path: Path) -> None:
        # The CAR 3 §3.735 case: one revision listed twice in one provision.
        prov = _provision("23", "735", [0, 0])
        data = _stage(tmp_path, [_document("23", [0])], [prov], [])
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "cert_basis.sqlite")
        assert "735.json" in str(ei.value)
        assert "UNIQUE constraint failed" in str(ei.value)

    def test_duplicate_display_order_fails(self, tmp_path: Path) -> None:
        entries = [_entry([], display_order=1), _entry([], display_order=1)]
        assert "UNIQUE constraint failed" in _basis_fails(
            tmp_path, [_provision("23", "1", [0])], entries
        )

    def test_future_action_date_fails(self, tmp_path: Path) -> None:
        # A two-digit year read with strptime's %y pivot: 3/25/64 -> 2064.
        prov = _provision("23", "1", [])
        prov["versions"] = [
            _version("23-0", actions=[{"type": "nprm", "issued_on": "2064-03-25"}])
        ]
        message = _basis_fails(tmp_path, [prov], [])
        assert "version_actions.issued_on" in message and "2064-03-25" in message

    def test_conflicting_tcds_metadata_fails(self, tmp_path: Path) -> None:
        tcds = {"issuer": "FAA", "tcds_number": "3A12", "revision": "42"}
        data = _stage(
            tmp_path,
            [_document("23", [0])],
            [_provision("23", "1", [0])],
            [
                _aircraft([_entry([])], model="172", tcds=tcds),
                _aircraft([_entry([])], model="172A", tcds={**tcds, "revision": "43"}),
            ],
        )
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "cert_basis.sqlite")
        assert "TCDS 3A12 metadata" in str(ei.value)

    def test_shared_tcds_with_same_metadata_is_fine(self, tmp_path: Path) -> None:
        tcds = {"issuer": "FAA", "tcds_number": "3A12", "revision": "42"}
        data = _stage(
            tmp_path,
            [_document("23", [0])],
            [_provision("23", "1", [0])],
            [
                _aircraft([_entry([])], model="172", tcds=tcds),
                _aircraft([_entry([])], model="172A", tcds=tcds),
            ],
        )
        report = build(data, tmp_path / "cert_basis.sqlite")
        assert report["tables"]["tcds"] == 1
        assert report["tables"]["tcb"] == 2

    def test_path_must_match_content(self, tmp_path: Path) -> None:
        data = _stage(
            tmp_path, [_document("23", [0])], [_provision("23", "1", [0])], []
        )
        wrong = data / "documents" / "faa" / "23" / "2.json"
        (data / "documents" / "faa" / "23" / "1.json").rename(wrong)
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "cert_basis.sqlite")
        assert "expected at documents/faa/23/1.json" in str(ei.value)

    def test_check_catches_path_mismatch(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        data = _stage(
            tmp_path, [_document("23", [0])], [_provision("23", "1", [0])], []
        )
        assert check(data) == []
        (data / "documents" / "faa" / "23" / "1.json").rename(
            data / "documents" / "faa" / "23" / "2.json"
        )
        assert main(["--check", "--data-dir", str(data)]) == 1
        assert "expected at documents/faa/23/1.json" in capsys.readouterr().err

    def test_validation_failure_fails_build_before_sqlite(self, tmp_path: Path) -> None:
        prov = _provision("25", "1309", [23])
        del prov["canonical_title"]
        data = _stage(tmp_path, [_document("25", [23])], [prov], [])
        with pytest.raises(BuildError):
            build(data, tmp_path / "cert_basis.sqlite")
        assert not (tmp_path / "cert_basis.sqlite").exists()
        assert not (tmp_path / "cert_basis.sqlite.new").exists()


class TestAtomicWrite:
    def test_rebuild_overwrites_and_clears_stale_wal(self, tmp_path: Path) -> None:
        data = _stage(
            tmp_path, [_document("23", [0])], [_provision("23", "1", [0])], []
        )
        out = tmp_path / "cert_basis.sqlite"
        build(data, out)
        # Sidecars left by an old WAL-mode build must not survive next to the
        # new file, or SQLite could replay a stale WAL into it.
        stale = [out.with_name(out.name + s) for s in ("-wal", "-shm")]
        for p in stale:
            p.write_bytes(b"stale")
        build(data, out)
        assert out.exists()
        assert not out.with_suffix(out.suffix + ".new").exists()
        assert not any(p.exists() for p in stale)

    def test_failed_report_write_keeps_the_old_pair(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        data = _stage(
            tmp_path, [_document("23", [0])], [_provision("23", "1", [0])], []
        )
        out = tmp_path / "cert_basis.sqlite"
        report = tmp_path / "cert_basis_report.json"
        build(data, out)
        before = (out.read_bytes(), report.read_bytes())

        def fail(*args: object, **kwargs: object) -> str:
            raise OSError("disk full")

        monkeypatch.setattr(json, "dumps", fail)
        with pytest.raises(OSError, match="disk full"):
            build(data, out)
        assert (out.read_bytes(), report.read_bytes()) == before
        assert not out.with_name(out.name + ".new").exists()
        assert not report.with_name(report.name + ".new").exists()


class TestGitDirty:
    """The report says whether data/ had uncommitted changes (BUILD-5)."""

    @staticmethod
    def _git(repo: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
            + list(args),
            check=True,
            capture_output=True,
        )

    def _report(self, data: Path, out: Path) -> dict:
        build(data, out)
        return json.loads(out.with_name("cert_basis_report.json").read_text())

    def test_clean_modified_and_untracked(self, tmp_path: Path) -> None:
        data = _stage(
            tmp_path, [_document("23", [0])], [_provision("23", "1", [0])], []
        )
        (tmp_path / "other.txt").write_text("outside data/: not reported")
        self._git(tmp_path, "init", "-q")
        self._git(tmp_path, "add", "data")
        self._git(tmp_path, "commit", "-q", "-m", "init")
        out = tmp_path / "out" / "cert_basis.sqlite"
        out.parent.mkdir()

        report = self._report(data, out)
        assert (report["git_dirty"], report["git_dirty_paths"]) == (False, [])

        prov = _provision("23", "1", [0])
        prov["canonical_title"] = "Changed"
        (data / "documents" / "faa" / "23" / "1.json").write_text(json.dumps(prov))
        (data / "documents" / "faa" / "23" / "2.json").write_text(
            json.dumps(_provision("23", "2", [0]))
        )
        report = self._report(data, out)
        assert report["git_dirty"] is True
        assert report["git_dirty_paths"] == [
            "data/documents/faa/23/1.json",
            "data/documents/faa/23/2.json",
        ]

    def test_outside_git_is_unknown(self, tmp_path: Path) -> None:
        data = _stage(tmp_path, [_document("23", [0])], [], [])
        report = self._report(data, tmp_path / "cert_basis.sqlite")
        assert (report["git_dirty"], report["git_dirty_paths"]) == (None, [])
