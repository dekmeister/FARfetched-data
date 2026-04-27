"""Tests for rulemaking action extraction and round-trip through the build."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from build import build  # noqa: E402
from faa_fetch import (  # noqa: E402
    parse_action_string,
    parse_actions_from_meta,
    parse_actions_from_tail,
    strip_action_appendix,
)


# ---------------------------------------------------------------------------
# Unit tests for parser helpers


class TestParseActionString:
    def test_nprm(self) -> None:
        s = "Notice of Proposed Rulemaking. Notice No. 71-12; Issued on 04/26/71."
        a = parse_action_string(s)
        assert a["type"] == "nprm"
        assert a["reference"] == "71-12"
        assert a["issued_on"] == "1971-04-26"
        assert a["source_url"] is None
        assert a["notes"] is None

    def test_final_rule(self) -> None:
        s = "Final Rule. Docket No. 11010; Issued on 09/20/74."
        a = parse_action_string(s)
        assert a["type"] == "final_rule"
        assert a["reference"] == "11010"
        assert a["issued_on"] == "1974-09-20"

    def test_direct_final_rule(self) -> None:
        s = "Direct Final Rule. Docket No. 12345; Issued on 01/15/90."
        a = parse_action_string(s)
        assert a["type"] == "direct_final_rule"

    def test_interim_final_rule(self) -> None:
        s = "Interim Final Rule. Docket No. 99-99; Issued on 06/01/99."
        a = parse_action_string(s)
        assert a["type"] == "interim_final_rule"

    def test_other_falls_back(self) -> None:
        s = "Some unknown rule type. No. 99; Issued on 01/01/00."
        a = parse_action_string(s)
        assert a["type"] == "other"
        assert a["notes"] == s

    def test_missing_reference_is_none(self) -> None:
        # Use an unambiguous MM/DD/YY date (month > 12 rules out DD/MM/YY)
        s = "Final Rule. Issued on 09/20/74."
        a = parse_action_string(s)
        assert a["type"] == "final_rule"
        assert a["reference"] is None
        assert a["issued_on"] == "1974-09-20"

    def test_missing_date_is_none(self) -> None:
        # Semicolon after reference number is required by the DRS format
        s = "Final Rule. Docket No. 99999; effective immediately."
        a = parse_action_string(s)
        assert a["type"] == "final_rule"
        assert a["reference"] == "99999"
        assert a["issued_on"] is None


class TestStripActionAppendix:
    _MARKER = "--> Link to eCFR -->"

    def test_no_marker_returns_original(self) -> None:
        text = "This is clean regulation text."
        clean, tail = strip_action_appendix(text)
        assert clean == text
        assert tail == ""

    def test_strips_preamble_and_splits(self) -> None:
        text = (
            "The pressure may not be less than 5 p.s.i.] "
            "71-12; Issued on 04/26/71. "
            + self._MARKER
            + " NPRM ACTIONS: &nbsp; Notice of Proposed Rulemaking. "
            "Notice No. 71-12; Issued on 04/26/71."
        )
        clean, tail = strip_action_appendix(text)
        assert clean == "The pressure may not be less than 5 p.s.i.]"
        assert "NPRM ACTIONS" in tail
        assert self._MARKER not in clean

    def test_preserves_text_without_dangling_preamble(self) -> None:
        text = "Simple rule text." + self._MARKER + " NPRM ACTIONS: &nbsp; Notice."
        clean, tail = strip_action_appendix(text)
        assert clean == "Simple rule text."


class TestParseActionsFromMeta:
    def test_extracts_nprm_and_final_rule(self) -> None:
        meta = {
            "NPRM Actions": "Notice of Proposed Rulemaking. Notice No. 71-12; Issued on 04/26/71.",
            "Final Rule Actions": "Final Rule. Docket No. 11010; Issued on 09/20/74.",
        }
        actions = parse_actions_from_meta(meta)
        assert len(actions) == 2
        assert actions[0]["type"] == "nprm"
        assert actions[0]["reference"] == "71-12"
        assert actions[1]["type"] == "final_rule"
        assert actions[1]["reference"] == "11010"

    def test_empty_meta_returns_empty(self) -> None:
        assert parse_actions_from_meta({}) == []

    def test_missing_field_skipped(self) -> None:
        meta = {"Final Rule Actions": "Final Rule. Docket No. 999; Issued on 01/01/80."}
        actions = parse_actions_from_meta(meta)
        assert len(actions) == 1
        assert actions[0]["type"] == "final_rule"


class TestParseActionsFromTail:
    def test_two_actions(self) -> None:
        tail = (
            " NPRM ACTIONS: &nbsp; Notice of Proposed Rulemaking. "
            "Notice No. 71-12; Issued on 04/26/71. "
            "11010; Issued on 09/20/74. "
            "--> Link to eCFR --> "
            "FINAL RULE ACTIONS: &nbsp; Final Rule. Docket No. 11010; Issued on 09/20/74."
        )
        actions = parse_actions_from_tail(tail)
        assert len(actions) == 2
        assert actions[0]["type"] == "nprm"
        assert actions[0]["reference"] == "71-12"
        assert actions[1]["type"] == "final_rule"
        assert actions[1]["reference"] == "11010"

    def test_single_nprm_only(self) -> None:
        tail = (
            " NPRM ACTIONS: &nbsp; Notice of Proposed Rulemaking. "
            "Notice No. 83-17; Issued on 09/23/83."
        )
        actions = parse_actions_from_tail(tail)
        assert len(actions) == 1
        assert actions[0]["type"] == "nprm"
        assert actions[0]["reference"] == "83-17"

    def test_empty_tail_returns_empty(self) -> None:
        assert parse_actions_from_tail("") == []
        assert parse_actions_from_tail("  no headers here  ") == []


# ---------------------------------------------------------------------------
# Build round-trip: actions are stored and queryable


def _part_doc(part: str, amendments: list[dict]) -> dict:
    return {
        "authority": "FAA",
        "title_number": 14,
        "part": part,
        "description": None,
        "amendments": amendments,
    }


def _stage(tmp_path: Path, part_doc: dict, section_doc: dict) -> Path:
    data = tmp_path / "data"
    part_dir = data / "regulations" / "faa" / part_doc["part"]
    part_dir.mkdir(parents=True, exist_ok=True)
    (part_dir / "_part.json").write_text(json.dumps(part_doc))
    (part_dir / f"{section_doc['section']}.json").write_text(json.dumps(section_doc))
    (data / "aircraft").mkdir(parents=True, exist_ok=True)
    return data


class TestActionsBuildRoundTrip:
    def test_actions_stored_in_db(self, tmp_path: Path) -> None:
        part = _part_doc(
            "25",
            [{"designator": "25-5", "ordinal": 5, "effective_date": "1974-09-20"}],
        )
        section = {
            "authority": "FAA",
            "part": "25",
            "section": "1309",
            "current_subpart": "F",
            "canonical_title": "Equipment, systems, and installations.",
            "amendments": [
                {
                    "designator": "25-5",
                    "title_at_amendment": "Equipment.",
                    "text": "The equipment must be designed.",
                    "federal_register_cite": "39 FR 35460",
                    "source_url": "https://drs.faa.gov/browse/excelExternalWindow/ABC.0001",
                    "actions": [
                        {
                            "type": "nprm",
                            "reference": "71-12",
                            "issued_on": "1971-04-26",
                            "source_url": None,
                            "notes": None,
                        },
                        {
                            "type": "final_rule",
                            "reference": "11010",
                            "issued_on": "1974-09-20",
                            "source_url": None,
                            "notes": None,
                        },
                    ],
                }
            ],
        }
        data = _stage(tmp_path, part, section)
        out = tmp_path / "cert_basis.sqlite"
        report = build(data, out)

        assert report["amendment_actions"] == 2

        with sqlite3.connect(out) as conn:
            rows = conn.execute(
                "SELECT seq, type, reference, issued_on "
                "FROM amendment_actions ORDER BY seq"
            ).fetchall()

        assert rows == [
            (0, "nprm", "71-12", "1971-04-26"),
            (1, "final_rule", "11010", "1974-09-20"),
        ]

    def test_amendment_without_actions_builds_fine(self, tmp_path: Path) -> None:
        part = _part_doc(
            "25",
            [{"designator": "25-1", "ordinal": 1, "effective_date": "1965-01-01"}],
        )
        section = {
            "authority": "FAA",
            "part": "25",
            "section": "1309",
            "current_subpart": "F",
            "canonical_title": "Equipment.",
            "amendments": [
                {
                    "designator": "25-1",
                    "title_at_amendment": "Equipment.",
                    "text": "Must be designed.",
                    "federal_register_cite": "30 FR 1000",
                    "source_url": None,
                }
            ],
        }
        data = _stage(tmp_path, part, section)
        out = tmp_path / "cert_basis.sqlite"
        report = build(data, out)
        assert report["amendment_actions"] == 0

    def test_real_data_has_no_ecfr_marker_in_text(
        self, repo_root: Path, tmp_path: Path
    ) -> None:
        """After --fix-actions is applied, no committed text should contain
        the embedded metadata marker."""
        out = tmp_path / "cert_basis.sqlite"
        build(repo_root / "data", out)
        with sqlite3.connect(out) as conn:
            contaminated = conn.execute(
                "SELECT COUNT(*) FROM section_amendments "
                "WHERE text LIKE '%--> Link to eCFR -->%'"
            ).fetchone()[0]
        assert contaminated == 0, (
            f"{contaminated} section_amendments still contain the embedded "
            "DRS metadata marker — run: uv run python tools/migrate_v2.py "
            "--fix-actions --apply"
        )
