"""Tests for faa_discover.py — discovery diff and section version walking."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from faa_discover import (  # noqa: E402
    _clean_title,
    _iso_to_dmy,
    _known_designators,
    _max_ordinal,
    discover_section,
)


# ---------------------------------------------------------------------------
# Helpers


def _part_doc(designators: list[tuple[str, int]]) -> dict:
    return {
        "authority": "FAA",
        "title_number": 14,
        "part": "25",
        "description": None,
        "amendments": [
            {"designator": d, "ordinal": o, "effective_date": "2020-01-01"}
            for d, o in designators
        ],
    }


# ---------------------------------------------------------------------------
# Unit: _known_designators / _max_ordinal


class TestPartDocHelpers:
    def test_known_designators(self) -> None:
        doc = _part_doc([("25-1", 1), ("25-50", 50), ("25-100", 100)])
        assert _known_designators(doc) == {"25-1", "25-50", "25-100"}

    def test_known_empty(self) -> None:
        assert _known_designators({}) == set()

    def test_max_ordinal(self) -> None:
        doc = _part_doc([("25-1", 1), ("25-100", 100), ("25-50", 50)])
        assert _max_ordinal(doc) == 100

    def test_max_ordinal_empty(self) -> None:
        assert _max_ordinal({}) == -1


# ---------------------------------------------------------------------------
# Unit: _iso_to_dmy / _clean_title


class TestFormatHelpers:
    def test_iso_to_dmy(self) -> None:
        assert _iso_to_dmy("2024-10-22") == "22/10/2024"

    def test_iso_to_dmy_empty(self) -> None:
        assert _iso_to_dmy("") == ""

    def test_iso_to_dmy_invalid(self) -> None:
        # Returns raw string unchanged when format is unexpected
        assert _iso_to_dmy("not-a-date") == "not-a-date"

    def test_clean_title(self) -> None:
        assert (
            _clean_title("§ 25.803   Emergency evacuation.", "25", "803")
            == "Emergency evacuation"
        )

    def test_clean_title_no_prefix(self) -> None:
        assert (
            _clean_title("Emergency evacuation.", "25", "803") == "Emergency evacuation"
        )


# ---------------------------------------------------------------------------
# Unit: discover_section diff logic (eCFR calls stubbed)


_XML_TMPL = """<SECTION>
<CITA TYPE="N">[Doc. No. 4080, 29 FR 17955, Dec. 18, 1964, as amended by
{amdt_entries}]
</CITA>
</SECTION>"""

_AMDT_ENTRY = "Amdt. 25-{n}, {vol} FR {page}, Jan. 1, 20{yy}"


def _make_xml(amdt_numbers: list[int]) -> str:
    entries = "; ".join(
        _AMDT_ENTRY.format(n=n, vol=60 + n, page=10000 + n * 100, yy=n)
        for n in amdt_numbers
    )
    return _XML_TMPL.format(amdt_entries=entries)


def _make_version(date: str, amendment_date: str | None = None) -> dict:
    return {
        "date": date,
        "amendment_date": amendment_date or date,
        "identifier": "25.803",
        "name": "§ 25.803   Emergency evacuation.",
        "part": "25",
        "substantive": True,
        "removed": False,
        "subpart": "D",
        "title": "14",
        "type": "section",
    }


class TestDiscoverSection:
    """Given stubbed eCFR responses, assert discover_section emits correct rows."""

    def _run(
        self,
        versions: list[dict],
        xml_by_date: dict[str, str],
        known: set[str],
        watermark: int,
    ) -> list[dict]:
        def fake_versions(part: str, section: str) -> list[dict]:
            return versions

        def fake_xml(part: str, section: str, date: str) -> str | None:
            return xml_by_date.get(date)

        with (
            patch("faa_discover.fetch_section_versions", side_effect=fake_versions),
            patch("faa_discover.fetch_ecfr_xml", side_effect=fake_xml),
        ):
            return discover_section("25", "803", known, watermark, sleep=0.0)

    def test_new_amendments_above_watermark(self) -> None:
        # Existing data has 25-1..25-100; eCFR shows through 25-150.
        versions = [_make_version(f"2020-{i:02d}-01") for i in range(1, 6)]
        # Simulate five versions with accumulating amendments
        xml_by_date = {
            "2020-01-01": _make_xml(list(range(1, 101))),  # 25-1..25-100
            "2020-02-01": _make_xml(list(range(1, 111))),  # adds 25-101..25-110
            "2020-03-01": _make_xml(list(range(1, 121))),  # adds 25-111..25-120
            "2020-04-01": _make_xml(list(range(1, 131))),  # adds 25-121..25-130
            "2020-05-01": _make_xml(list(range(1, 151))),  # adds 25-131..25-150
        }
        known = {f"25-{n}" for n in range(1, 101)}
        watermark = 100

        items = self._run(versions, xml_by_date, known, watermark)
        emitted = {i["designator"] for i in items}

        assert emitted == {f"25-{n}" for n in range(101, 151)}
        assert all(i["url"] == "" for i in items)
        assert all(i["part"] == "25" for i in items)
        assert all(i["section"] == "803" for i in items)

    def test_no_new_amendments_when_all_known(self) -> None:
        versions = [_make_version("2020-01-01")]
        xml_by_date = {"2020-01-01": _make_xml(list(range(1, 11)))}
        known = {f"25-{n}" for n in range(1, 11)}
        watermark = 10

        items = self._run(versions, xml_by_date, known, watermark)
        assert items == []

    def test_watermark_filters_below(self) -> None:
        # eCFR shows 25-1..25-20; watermark=15; known is empty
        versions = [_make_version("2020-01-01")]
        xml_by_date = {"2020-01-01": _make_xml(list(range(1, 21)))}
        known: set[str] = set()
        watermark = 15

        items = self._run(versions, xml_by_date, known, watermark)
        emitted_ordinals = {int(i["designator"].split("-")[1]) for i in items}
        assert all(o > 15 for o in emitted_ordinals)
        assert emitted_ordinals == set(range(16, 21))

    def test_fr_cite_extracted(self) -> None:
        # Single version with one new amendment; assert fr_cite is populated.
        versions = [_make_version("2024-10-22")]
        xml_by_date = {"2024-10-22": _make_xml([150])}
        known: set[str] = set()
        watermark = -1

        items = self._run(versions, xml_by_date, known, watermark)
        assert len(items) == 1
        assert items[0]["designator"] == "25-150"
        assert "FR" in items[0]["fr_cite"]

    def test_effective_date_dmy_format(self) -> None:
        versions = [_make_version("2024-10-22", amendment_date="2024-10-22")]
        xml_by_date = {"2024-10-22": _make_xml([200])}
        known: set[str] = set()
        watermark = -1

        items = self._run(versions, xml_by_date, known, watermark)
        assert len(items) == 1
        assert items[0]["effective_date_raw"] == "22/10/2024"

    def test_empty_when_no_versions(self) -> None:
        with (
            patch("faa_discover.fetch_section_versions", return_value=[]),
            patch("faa_discover.fetch_ecfr_xml", return_value=None),
        ):
            items = discover_section("25", "803", set(), -1, sleep=0.0)
        assert items == []

    def test_empty_when_no_cita(self) -> None:
        versions = [_make_version("2024-01-01")]
        xml_no_cita = "<SECTION><P>Some text.</P></SECTION>"
        with (
            patch("faa_discover.fetch_section_versions", return_value=versions),
            patch("faa_discover.fetch_ecfr_xml", return_value=xml_no_cita),
        ):
            items = discover_section("25", "803", set(), -1, sleep=0.0)
        assert items == []
