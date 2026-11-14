"""cites.py: publication_cite values from a reviewed cite override, checked
against a synthetic FR issue. Not in the repo's testpaths; run:

    PYTHONPATH=.:.claude/skills/audit-data/scripts uv run pytest \
        .claude/skills/promote-staged/scripts/
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import cites  # noqa: E402
import fields  # noqa: E402

PAGES = [
    "FEDERAL REGISTER 100\nOther agency rules.\n",
    "101 FEDERAL REGISTER\n[Civil Air Regs., Amdt. 3-7]\n"
    "PART 3—AIRPLANE AIRWORTHINESS; NORMAL\n"
    "[F. R. Doc. 52-1; Filed, Feb. 4, 1952]\n"  # another document's, interleaved
    "MISCELLANEOUS AMENDMENTS\n1. By amending § 3.85 to read:\n",
    "FEDERAL REGISTER 102\n§ 3.85 Climb. (a) Normal climb.\n"
    "2. By adding § 3.86a.\n[F. R. Doc. 52-1420; Filed, Feb. 4, 1952]\n"
    "§ 3.99 Some later rule.\n",
    "FEDERAL REGISTER 103\nNotices.\n",
]


def _setup(tmp_path: Path, cite: str, evidence_page: str = "2, printed p.101") -> None:
    fr = tmp_path / "FR-1952-02-05.pdf"
    fr.with_suffix(".txt").write_text("\f".join(PAGES), encoding="utf-8")
    tsv = tmp_path / "cites.tsv"
    tsv.write_text(
        "designator\tpublication_cite\tevidence\tnote\n"
        f"CAR3-7\t{cite}\t{fr} pdf p.{evidence_page}: quoted\tchecked\n",
        encoding="utf-8",
    )
    cites.OVERRIDES[:] = [tsv]
    cites.rows.cache_clear()
    cites.fr_document.cache_clear()


@pytest.fixture(autouse=True)
def _restore() -> Iterator[None]:
    saved = list(cites.OVERRIDES)
    yield
    cites.OVERRIDES[:] = saved
    cites.rows.cache_clear()
    cites.fr_document.cache_clear()


def test_ok_when_row_page_and_section_agree(tmp_path: Path) -> None:
    _setup(tmp_path, "17 FR 101")
    status, note, ex = cites.check("CAR3-7", "85", "17 FR 101")
    assert status == "ok", note
    assert "amendment 3-7 matches" in note and ex and "3.85" in ex["text"]
    # the document runs past another document's interleaved F.R. Doc. line
    assert cites.check("CAR3-7", "86a", "17 FR 101")[0] == "ok"


def test_flags_a_section_not_in_the_document(tmp_path: Path) -> None:
    _setup(tmp_path, "17 FR 101")
    for key in ("99", "86", "8"):  # after the doc's end; 3.86a ≠ 3.86; 3.85 ≠ 3.8
        status, note, _ = cites.check("CAR3-7", key, "17 FR 101")
        assert status == "flag" and "section" in note, key


def test_flags_a_value_other_than_the_row(tmp_path: Path) -> None:
    _setup(tmp_path, "17 FR 101")
    status, note, _ = cites.check("CAR3-7", "85", "17 FR 102")
    assert status == "flag" and "17 FR 101" in note


@pytest.mark.parametrize(
    ("cite", "evidence", "want"),
    [
        ("17 FR 102", "2, printed p.101", "printed p.101"),  # row vs its evidence
        ("16 FR 101", "2, printed p.101", "volume"),  # 1952 is volume 17
        ("17 FR 102", "3, printed p.102", "heading"),  # page without the heading
        ("17 FR 105", "2, printed p.105", "reads as printed p.101"),
    ],
)
def test_flags_a_row_that_disagrees(
    tmp_path: Path, cite: str, evidence: str, want: str
) -> None:
    _setup(tmp_path, cite, evidence)
    status, note, _ = cites.check("CAR3-7", "85", cite)
    assert status == "flag" and want in note, note


def test_revision_without_a_row(tmp_path: Path) -> None:
    _setup(tmp_path, "17 FR 101")
    assert cites.check("CAR3-0", "85", None)[0] == "ok"
    assert cites.check("CAR3-0", "85", "13 FR 1")[0] == "flag"


def test_missing_fr_copy_is_unverifiable(tmp_path: Path) -> None:
    _setup(tmp_path, "17 FR 101")
    (tmp_path / "FR-1952-02-05.txt").unlink()
    assert cites.check("CAR3-7", "85", "17 FR 101")[0] == "unverifiable"


def test_amendment_and_coverage(tmp_path: Path) -> None:
    assert cites.amendment("CAR3-7") == "3-7"
    assert cites.amendment("CAR3R-2") == "3-2"
    assert cites.amendment("CAR3R-0") == ""
    _setup(tmp_path, "17 FR 101")
    assert cites.covers("CAR3R-5") and not cites.covers("25-140")


def test_fields_uses_cited_for_covered_versions(tmp_path: Path) -> None:
    _setup(tmp_path, "17 FR 101")
    rel = "documents/caa/car-3/85.json"
    rec = {"versions": [{"designator": "CAR3-7", "text": "x"}]}
    (tmp_path / rel).parent.mkdir(parents=True)
    (tmp_path / rel).write_text(fields.json.dumps(rec), encoding="utf-8")
    row = {
        "relpath": rel,
        "kind": "document",
        "fields": [
            {
                "where": "version CAR3-7",
                "field": "publication_cite",
                "old": None,
                "new": "17 FR 101",
            }
        ],
    }
    (out,) = fields.check_row(row, tmp_path, {})
    assert out["kind"] == "cited" and out["status"] == "ok", out["note"]
    assert out["source"].endswith("FR-1952-02-05.txt p.2")
