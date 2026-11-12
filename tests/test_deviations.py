"""Deviation records (docs/DATA_FORMAT.md §Deviations, docs/SQLITE.md
§Deviations): link-only rows whose citations resolve like a TCDS line's."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import factories as fx
import pytest

from certbuild.errors import BuildError
from certbuild.pipeline import build, check

CS25 = fx.document(
    "EASA",
    "cs-25",
    [("CS25-1", 1, "2003-10-17"), ("CS25-2", 2, "2006-10-02")],
    doc_kind="certification_spec",
    code="CS-25",
)
PROVISIONS = [
    fx.provision("EASA", "cs-25", "1309", [fx.version("CS25-1")]),
    fx.provision("EASA", "cs-25", "904", [fx.version("CS25-2")]),
]


def _stage(tmp_path: Path, *records: dict[str, Any]) -> Path:
    data = fx.stage(tmp_path, [CS25], PROVISIONS)
    fx.stage_deviations(data, list(records))
    return data


def _build(tmp_path: Path, *records: dict[str, Any]) -> Path:
    out = tmp_path / "cert_basis.sqlite"
    build(_stage(tmp_path, *records), out)
    return out


def _fails(tmp_path: Path, *records: dict[str, Any]) -> str:
    with pytest.raises(BuildError) as ei:
        _build(tmp_path, *records)
    assert not (tmp_path / "cert_basis.sqlite").exists()
    return str(ei.value)


def _cite(number: str = "1309", **extra: Any) -> dict[str, Any]:
    return {"issuer": "EASA", "document": "cs-25", "number": number, **extra}


def test_record_and_citations_are_inserted(tmp_path: Path) -> None:
    gap = {"cited": "JAR 25.1", "reason": "doc_not_in_dataset"}
    db = _build(
        tmp_path,
        fx.deviation(
            title="SC-E25.904-01 on CS 25.1309(a) and JAR 25.1",
            citations=[_cite(paragraph="(a)"), _cite("904")],
            citation_gaps=[gap],
        ),
        fx.deviation("17584", number=None, kind="elos", stage="proposed"),
    )
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT key, kind, number, stage FROM deviations ORDER BY key"
        ).fetchall()
        cited = conn.execute(
            "SELECT p.number, c.paragraph FROM deviation_citations c "
            "JOIN provisions p ON p.id = c.provision_id ORDER BY c.seq"
        ).fetchall()
        gaps = conn.execute(
            "SELECT cited, reason FROM deviation_citation_gaps"
        ).fetchall()
    assert rows == [
        ("120960", "special_condition", "SC-E25.904-01", "final"),
        ("17584", "elos", None, "proposed"),
    ]
    assert cited == [("1309", "(a)"), ("904", None)]
    assert gaps == [("JAR 25.1", "doc_not_in_dataset")]


def test_citations_never_touch_the_basis(tmp_path: Path) -> None:
    db = _build(tmp_path, fx.deviation(citations=[_cite()]))
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT count(*) FROM cert_basis_resolved").fetchone() == (
            0,
        )


@pytest.mark.parametrize(
    ("citation", "message"),
    [
        (_cite("1310"), "1310"),
        ({**_cite(), "document": "cs-23"}, "unknown document EASA/cs-23"),
        (_cite(paragraph="a"), "is not a run of (x)"),
    ],
)
def test_unresolvable_citation_fails(
    tmp_path: Path, citation: dict[str, Any], message: str
) -> None:
    assert message in _fails(tmp_path, fx.deviation(citations=[citation]))


def test_gap_must_be_printed(tmp_path: Path) -> None:
    gap = {"cited": "CS 25.999", "reason": "section_not_in_document"}
    err = _fails(tmp_path, fx.deviation(citation_gaps=[gap]))
    assert "is not in the title or number" in err


def test_path_must_match_key(tmp_path: Path) -> None:
    data = _stage(tmp_path)
    path = data / "deviations" / "easa" / "wrong.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fx.deviation()))
    assert any("expected at deviations/easa/120960.json" in e for e in check(data))


def test_issuer_directory_is_lower_case(tmp_path: Path) -> None:
    data = _stage(tmp_path)
    path = data / "deviations" / "EASA" / "120960.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(fx.deviation()))
    assert any("expected at deviations/easa/120960.json" in e for e in check(data))


@pytest.mark.parametrize(
    "change",
    [
        {"source_url": None},
        {"stage": "draft"},
        {"kind": "certification_memorandum"},
        {"published_on": "19 Jan 2021"},
        {"text": "a body"},
    ],
)
def test_schema_rejects(tmp_path: Path, change: dict[str, Any]) -> None:
    data = _stage(tmp_path, fx.deviation(**change))
    assert any("deviations/easa/120960.json" in e for e in check(data))


def test_future_publication_date_fails(tmp_path: Path) -> None:
    assert "deviations.published_on" in _fails(
        tmp_path, fx.deviation(published_on="2999-01-01")
    )


def test_deviation_doc_kinds_are_gone(tmp_path: Path) -> None:
    doc = {**CS25, "doc_kind": "elos"}
    data = fx.stage(tmp_path, [doc], PROVISIONS)
    assert any("doc_kind" in e or "'elos'" in e for e in check(data))
