"""Tests for tools.easa_extract section/AMC parsing.

Operates on synthetic raw-text inputs (not real PDFs) so we can pin
the regex behaviour without needing pdftotext + sample documents.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import easa_extract  # noqa: E402


SAMPLE = """\
SUBPART A — GENERAL

CS 23.1 Applicability
   This Subpart applies to all normal-category aeroplanes.

   Page 12 of 320

AMC 23.1 Applicability
   This is guidance material that should be skipped.

CS 23.3 Aeroplane categories
   Aeroplanes are classified into normal, utility, acrobatic and commuter
   categories.

GM 23.3 Aeroplane categories
   Skip me too.

SUBPART B — FLIGHT

CS 23.21 Proof of compliance
   Each requirement of this Subpart must be met.
"""


def test_extract_finds_three_sections() -> None:
    secs = easa_extract.extract_sections(SAMPLE)
    assert set(secs.keys()) == {"1", "3", "21"}


def test_extract_skips_amc_gm_blocks() -> None:
    secs = easa_extract.extract_sections(SAMPLE)
    assert "guidance material" not in secs["1"]["body"]
    assert "Skip me too" not in secs["3"]["body"]


def test_extract_strips_page_noise() -> None:
    secs = easa_extract.extract_sections(SAMPLE)
    assert "Page 12 of 320" not in secs["1"]["body"]


def test_extract_tracks_subpart() -> None:
    secs = easa_extract.extract_sections(SAMPLE)
    assert secs["1"]["subpart"] == "Subpart A — GENERAL"
    assert secs["21"]["subpart"] == "Subpart B — FLIGHT"


def test_extract_captures_inline_title() -> None:
    secs = easa_extract.extract_sections(SAMPLE)
    assert secs["3"]["title"] == "Aeroplane categories"
