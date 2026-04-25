"""Tests for SQLite emission in build.py.

Minimal coverage: happy path on the real checked-in data, plus a handful of
synthetic cases staged into tmp_path for the trickier expansion and failure
modes.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from build import BuildError, build


# ---------------------------------------------------------------------------
# helpers


def _aircraft_doc(
    tcds: str, entries: list[dict], **overrides: object
) -> dict:
    doc = {
        "tcds_number": tcds,
        "manufacturer": "Dummy Mfg",
        "model_designation": tcds,
        "common_name": None,
        "category": None,
        "tcds_revision": None,
        "tcds_revision_date": None,
        "tcds_source_url": None,
        "notes": None,
        "certification_basis": entries,
    }
    doc.update(overrides)
    return doc


def _regulation_doc(part: str, section: str, amendments: list[dict]) -> dict:
    return {
        "authority": "FAA",
        "title_number": 14,
        "part": part,
        "subpart": "A",
        "section": section,
        "canonical_title": f"Dummy §{part}.{section}",
        "amendments": amendments,
    }


def _amendment(designator: str, ordinal: int, text: str = "dummy") -> dict:
    return {
        "designator": designator,
        "ordinal": ordinal,
        "effective_date": "1970-01-01",
        "title_at_amendment": "Dummy title",
        "text": text,
        "source_url": "https://example.com",
        "federal_register_cite": "1 FR 1",
    }


def _stage_data(tmp_path: Path, regulations: list[dict], aircraft: list[dict]) -> Path:
    data = tmp_path / "data"
    (data / "regulations" / "faa" / "25").mkdir(parents=True)
    (data / "aircraft").mkdir(parents=True)
    for r in regulations:
        p = data / "regulations" / "faa" / r["part"] / f"{r['section']}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r))
    for a in aircraft:
        (data / "aircraft" / f"{a['tcds_number']}.json").write_text(json.dumps(a))
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

        assert report["regulations"] == 1
        assert report["regulation_amendments"] == 1
        assert report["aircraft"] == 1
        # 1 row from range expansion into §25.1309, 1 row from the
        # special_condition entry with NULL FK.
        assert report["certification_basis_entries"] == 2
        assert report["unresolved_references"] == []

    def test_built_schema_matches_plan(
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
        assert tables == {
            "regulations",
            "regulation_amendments",
            "aircraft",
            "certification_basis_entries",
        }
        assert views == {"latest_amendments"}

    def test_range_expansion_points_at_right_amendment(
        self, repo_root: Path, tmp_path: Path
    ) -> None:
        out = tmp_path / "cert_basis.sqlite"
        build(repo_root / "data", out)
        with sqlite3.connect(out) as conn:
            row = conn.execute(
                """
                SELECT ra.amendment_designator, r.part, r.section
                FROM certification_basis_entries cbe
                JOIN regulation_amendments ra
                  ON ra.id = cbe.regulation_amendment_id
                JOIN regulations r ON r.id = ra.regulation_id
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
                "SELECT entry_type, raw_reference, regulation_amendment_id "
                "FROM certification_basis_entries "
                "WHERE regulation_amendment_id IS NULL"
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
                "SELECT amendment_designator FROM latest_amendments"
            ).fetchall()
        assert rows == [("25-23",)]


# ---------------------------------------------------------------------------
# synthetic cases


class TestSingleReference:
    def test_single_ref_resolves_to_specific_amendment(
        self, tmp_path: Path
    ) -> None:
        regs = [
            _regulation_doc(
                "25",
                "1309",
                [
                    _amendment("25-23", 23, "text at 25-23"),
                    _amendment("25-41", 41, "text at 25-41"),
                ],
            )
        ]
        ac = _aircraft_doc(
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
        data = _stage_data(tmp_path, regs, [ac])
        out = tmp_path / "cert_basis.sqlite"
        build(data, out)
        with sqlite3.connect(out) as conn:
            row = conn.execute(
                """
                SELECT ra.amendment_designator
                FROM certification_basis_entries cbe
                JOIN regulation_amendments ra
                  ON ra.id = cbe.regulation_amendment_id
                """
            ).fetchone()
        assert row == ("25-41",)


class TestRangeExpansionPostdating:
    def test_section_post_dating_range_is_skipped(self, tmp_path: Path) -> None:
        # §25.1309 has amendment 23 (within range); §25.9999 was added at
        # amendment 70 (post-dates the range). The range 1–62 should only
        # produce a row for §25.1309.
        regs = [
            _regulation_doc("25", "1309", [_amendment("25-23", 23)]),
            _regulation_doc("25", "9999", [_amendment("25-70", 70)]),
        ]
        ac = _aircraft_doc(
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
        data = _stage_data(tmp_path, regs, [ac])
        out = tmp_path / "cert_basis.sqlite"
        report = build(data, out)
        assert report["certification_basis_entries"] == 1
        assert report["unresolved_references"] == []


class TestBuildFailures:
    def test_unresolvable_single_ref_fails(self, tmp_path: Path) -> None:
        regs = [_regulation_doc("25", "1309", [_amendment("25-23", 23)])]
        ac = _aircraft_doc(
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
        data = _stage_data(tmp_path, regs, [ac])
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "cert_basis.sqlite")
        assert "25-99" in str(ei.value)
        assert not (tmp_path / "cert_basis.sqlite").exists()
        assert not (tmp_path / "cert_basis.sqlite.new").exists()

    def test_range_over_empty_part_fails(self, tmp_path: Path) -> None:
        # No Part 23 regulations in data, but the aircraft references it.
        regs = [_regulation_doc("25", "1309", [_amendment("25-23", 23)])]
        ac = _aircraft_doc(
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
        data = _stage_data(tmp_path, regs, [ac])
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "cert_basis.sqlite")
        assert "Part 23" in str(ei.value) or "part 23" in str(ei.value) or "'23'" in str(ei.value)

    def test_validation_failure_fails_build_before_sqlite(
        self, tmp_path: Path
    ) -> None:
        data = tmp_path / "data"
        (data / "regulations" / "faa" / "25").mkdir(parents=True)
        (data / "aircraft").mkdir(parents=True)
        # Invalid: missing canonical_title.
        (data / "regulations" / "faa" / "25" / "1309.json").write_text(
            json.dumps(
                {
                    "authority": "FAA",
                    "title_number": 14,
                    "part": "25",
                    "subpart": "F",
                    "section": "1309",
                    "amendments": [_amendment("25-23", 23)],
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
