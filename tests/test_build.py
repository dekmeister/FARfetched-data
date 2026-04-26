"""Tests for SQLite emission in build.py."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from build import BuildError, build


# ---------------------------------------------------------------------------
# helpers


def _part_doc(authority: str, part: str, amendments: list[dict]) -> dict:
    return {
        "authority": authority,
        "title_number": 14,
        "part": part,
        "description": None,
        "amendments": amendments,
    }


def _part_amendment(designator: str, ordinal: int) -> dict:
    return {
        "designator": designator,
        "ordinal": ordinal,
        "effective_date": "1970-01-01",
    }


def _regulation_doc(part: str, section: str, amendments: list[dict]) -> dict:
    return {
        "authority": "FAA",
        "part": part,
        "section": section,
        "current_subpart": "A",
        "canonical_title": f"Dummy §{part}.{section}",
        "amendments": amendments,
    }


def _section_amendment(designator: str, text: str = "dummy") -> dict:
    return {
        "designator": designator,
        "title_at_amendment": "Dummy title",
        "text": text,
        "federal_register_cite": "1 FR 1",
        "source_url": "https://example.com",
    }


def _aircraft_doc(
    manufacturer: str,
    model: str,
    tcds_number: str,
    cert_entries: list[dict],
) -> dict:
    return {
        "manufacturer": manufacturer,
        "model_designation": model,
        "common_name": None,
        "categories": ["transport"],
        "notes": None,
        "tcb": [
            {
                "tcds": {"authority": "FAA", "tcds_number": tcds_number},
                "notes": None,
                "certification_basis": cert_entries,
            }
        ],
    }


def _stage_data(
    tmp_path: Path,
    parts: list[dict],
    regulations: list[dict],
    aircraft: list[dict],
) -> Path:
    data = tmp_path / "data"
    for p in parts:
        part_dir = data / "regulations" / p["authority"].lower() / p["part"]
        part_dir.mkdir(parents=True, exist_ok=True)
        (part_dir / "_part.json").write_text(json.dumps(p))
    for r in regulations:
        part_dir = data / "regulations" / r["authority"].lower() / r["part"]
        part_dir.mkdir(parents=True, exist_ok=True)
        (part_dir / f"{r['section']}.json").write_text(json.dumps(r))
    (data / "aircraft").mkdir(parents=True, exist_ok=True)
    for a in aircraft:
        slug = a["model_designation"].replace(" ", "-").lower()
        (data / "aircraft" / f"{slug}.json").write_text(json.dumps(a))
    return data


# ---------------------------------------------------------------------------
# real checked-in data


class TestRealDataBuild:
    def test_build_succeeds_and_report_counts(
        self, repo_root: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "cert_basis.sqlite"
        report = build(repo_root / "data", out)

        assert out.exists()
        assert not (tmp_path / "cert_basis.sqlite.new").exists()

        assert report["regulation_parts"] >= 1
        assert report["amendments"] >= 1
        assert report["section_amendments"] >= 1
        assert report["aircraft_models"] == 1
        assert report["tcb"] == 1
        # At least 1 row from range expansion + 1 special_condition NULL FK.
        assert report["cert_basis_entries"] >= 2
        assert report["unresolved_references"] == []

    def test_built_schema_tables(
        self, repo_root: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "cert_basis.sqlite"
        build(repo_root / "data", out)
        with sqlite3.connect(out) as conn:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            views = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='view'"
                )
            }
        expected_tables = {
            "naa_authorities",
            "manufacturers",
            "categories",
            "regulation_parts",
            "regulations",
            "amendments",
            "section_amendments",
            "amendment_actions",
            "aircraft_models",
            "model_categories",
            "tcds",
            "tcb",
            "cert_basis_entries",
        }
        assert tables == expected_tables
        assert views == {"latest_amendments"}

    def test_range_expansion_points_at_right_amendment(
        self, repo_root: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "cert_basis.sqlite"
        build(repo_root / "data", out)
        with sqlite3.connect(out) as conn:
            row = conn.execute(
                """
                SELECT a.designator, rp.part, r.section
                FROM cert_basis_entries cbe
                JOIN section_amendments sa
                  ON sa.id = cbe.section_amendment_id
                JOIN amendments a ON a.id = sa.amendment_id
                JOIN regulations r ON r.id = sa.regulation_id
                JOIN regulation_parts rp ON rp.id = r.part_id
                """
            ).fetchone()
        assert row == ("25-23", "25", "1309")

    def test_special_condition_has_null_fk(
        self, repo_root: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "cert_basis.sqlite"
        build(repo_root / "data", out)
        with sqlite3.connect(out) as conn:
            rows = conn.execute(
                "SELECT entry_type, raw_reference, section_amendment_id "
                "FROM cert_basis_entries "
                "WHERE section_amendment_id IS NULL"
            ).fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "special_condition"

    def test_latest_amendments_view(
        self, repo_root: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "cert_basis.sqlite"
        build(repo_root / "data", out)
        with sqlite3.connect(out) as conn:
            rows = conn.execute(
                "SELECT designator FROM latest_amendments"
            ).fetchall()
        assert ("25-23",) in rows

    def test_lookup_tables_populated(
        self, repo_root: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "cert_basis.sqlite"
        build(repo_root / "data", out)
        with sqlite3.connect(out) as conn:
            authorities = {
                r[0]
                for r in conn.execute("SELECT code FROM naa_authorities")
            }
            manufacturers = conn.execute(
                "SELECT COUNT(*) FROM manufacturers"
            ).fetchone()[0]
        assert "FAA" in authorities
        assert manufacturers >= 1


# ---------------------------------------------------------------------------
# synthetic cases


class TestSingleReference:
    def test_single_ref_resolves_to_specific_amendment(
        self, tmp_path: Path
    ) -> None:
        parts = [
            _part_doc(
                "FAA",
                "25",
                [_part_amendment("25-23", 23), _part_amendment("25-41", 41)],
            )
        ]
        regs = [
            _regulation_doc(
                "25",
                "1309",
                [
                    _section_amendment("25-23", "text at 25-23"),
                    _section_amendment("25-41", "text at 25-41"),
                ],
            )
        ]
        ac = _aircraft_doc(
            "Dummy Mfg",
            "DummyModel",
            "DUMMY1",
            [
                {
                    "display_order": 1,
                    "entry_type": "regulation",
                    "raw_reference": "§25.1309 at 25-41",
                    "applicability_notes": None,
                    "resolved_references": [
                        {
                            "reference_kind": "single",
                            "authority": "FAA",
                            "title_number": 14,
                            "part": "25",
                            "section": "1309",
                            "amendment_designator": "25-41",
                        }
                    ],
                }
            ],
        )
        data = _stage_data(tmp_path, parts, regs, [ac])
        out = tmp_path / "cert_basis.sqlite"
        build(data, out)
        with sqlite3.connect(out) as conn:
            row = conn.execute(
                """
                SELECT a.designator
                FROM cert_basis_entries cbe
                JOIN section_amendments sa
                  ON sa.id = cbe.section_amendment_id
                JOIN amendments a ON a.id = sa.amendment_id
                """
            ).fetchone()
        assert row == ("25-41",)


class TestRangeExpansionPostdating:
    def test_section_post_dating_range_is_skipped(self, tmp_path: Path) -> None:
        parts = [
            _part_doc(
                "FAA",
                "25",
                [_part_amendment("25-23", 23), _part_amendment("25-70", 70)],
            )
        ]
        regs = [
            _regulation_doc("25", "1309", [_section_amendment("25-23")]),
            _regulation_doc("25", "9999", [_section_amendment("25-70")]),
        ]
        ac = _aircraft_doc(
            "Dummy Mfg",
            "DummyModel",
            "DUMMY2",
            [
                {
                    "display_order": 1,
                    "entry_type": "regulation",
                    "raw_reference": "Part 25 through 25-62",
                    "applicability_notes": None,
                    "resolved_references": [
                        {
                            "reference_kind": "range",
                            "authority": "FAA",
                            "title_number": 14,
                            "part": "25",
                            "from_amendment_ordinal": 1,
                            "to_amendment_ordinal": 62,
                        }
                    ],
                }
            ],
        )
        data = _stage_data(tmp_path, parts, regs, [ac])
        out = tmp_path / "cert_basis.sqlite"
        report = build(data, out)
        assert report["cert_basis_entries"] == 1
        assert report["unresolved_references"] == []


class TestBuildFailures:
    def test_unresolvable_single_ref_fails(self, tmp_path: Path) -> None:
        parts = [_part_doc("FAA", "25", [_part_amendment("25-23", 23)])]
        regs = [_regulation_doc("25", "1309", [_section_amendment("25-23")])]
        ac = _aircraft_doc(
            "Dummy Mfg",
            "DummyModel",
            "BADREF",
            [
                {
                    "display_order": 1,
                    "entry_type": "regulation",
                    "raw_reference": "§25.1309 at 25-99",
                    "applicability_notes": None,
                    "resolved_references": [
                        {
                            "reference_kind": "single",
                            "authority": "FAA",
                            "title_number": 14,
                            "part": "25",
                            "section": "1309",
                            "amendment_designator": "25-99",
                        }
                    ],
                }
            ],
        )
        data = _stage_data(tmp_path, parts, regs, [ac])
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "cert_basis.sqlite")
        assert "25-99" in str(ei.value)
        assert not (tmp_path / "cert_basis.sqlite").exists()
        assert not (tmp_path / "cert_basis.sqlite.new").exists()

    def test_range_over_empty_part_fails(self, tmp_path: Path) -> None:
        parts = [_part_doc("FAA", "25", [_part_amendment("25-23", 23)])]
        regs = [_regulation_doc("25", "1309", [_section_amendment("25-23")])]
        ac = _aircraft_doc(
            "Dummy Mfg",
            "DummyModel",
            "BADRNG",
            [
                {
                    "display_order": 1,
                    "entry_type": "regulation",
                    "raw_reference": "Part 23 through 23-10",
                    "applicability_notes": None,
                    "resolved_references": [
                        {
                            "reference_kind": "range",
                            "authority": "FAA",
                            "title_number": 14,
                            "part": "23",
                            "from_amendment_ordinal": 1,
                            "to_amendment_ordinal": 10,
                        }
                    ],
                }
            ],
        )
        data = _stage_data(tmp_path, parts, regs, [ac])
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "cert_basis.sqlite")
        assert "23" in str(ei.value)

    def test_section_with_undeclared_amendment_fails(
        self, tmp_path: Path
    ) -> None:
        parts = [_part_doc("FAA", "25", [_part_amendment("25-23", 23)])]
        regs = [_regulation_doc("25", "1309", [_section_amendment("25-99")])]
        data = _stage_data(tmp_path, parts, regs, [])
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "cert_basis.sqlite")
        assert "25-99" in str(ei.value)

    def test_validation_failure_fails_build_before_sqlite(
        self, tmp_path: Path
    ) -> None:
        data = tmp_path / "data"
        part_dir = data / "regulations" / "faa" / "25"
        part_dir.mkdir(parents=True)
        (data / "aircraft").mkdir(parents=True)
        # Invalid section: missing canonical_title.
        (part_dir / "1309.json").write_text(
            json.dumps(
                {
                    "authority": "FAA",
                    "part": "25",
                    "section": "1309",
                    "current_subpart": "F",
                    "amendments": [_section_amendment("25-23")],
                }
            )
        )
        with pytest.raises(BuildError):
            build(data, tmp_path / "cert_basis.sqlite")
        assert not (tmp_path / "cert_basis.sqlite").exists()
        assert not (tmp_path / "cert_basis.sqlite.new").exists()


class TestAtomicWrite:
    def test_successful_build_leaves_no_new_file(
        self, repo_root: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "cert_basis.sqlite"
        build(repo_root / "data", out)
        assert out.exists()
        assert not out.with_suffix(out.suffix + ".new").exists()

    def test_rebuild_overwrites_atomically(
        self, repo_root: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "cert_basis.sqlite"
        build(repo_root / "data", out)
        first_mtime = out.stat().st_mtime_ns
        build(repo_root / "data", out)
        assert out.exists()
        assert out.stat().st_mtime_ns >= first_mtime
