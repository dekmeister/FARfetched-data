"""Tests for deleted provision versions (`"deleted": true`) in build.py."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from build import BuildError, build

# CS23-0 .. CS23-6, one revision per year.
_REVISIONS = [(f"CS23-{n}", n, f"{2003 + n}-01-01") for n in range(7)]


def _document() -> dict:
    return {
        "issuer": "EASA",
        "doc_kind": "certification_spec",
        "code": "CS-23",
        "slug": "cs-23",
        "title": None,
        "revisions": [
            {"designator": d, "ordinal": o, "effective_date": e}
            for d, o, e in _REVISIONS
        ],
    }


def _live(designator: str, **extra: object) -> dict:
    return {
        "designator": designator,
        "title_at_revision": "Title",
        "text": f"text at {designator}",
        **extra,
    }


def _gone(designator: str) -> dict:
    return {"designator": designator, "title_at_revision": "Title", "deleted": True}


def _provision(number: str, versions: list[dict]) -> dict:
    return {
        "issuer": "EASA",
        "document": "cs-23",
        "number": number,
        "current_grouping": None,
        "canonical_title": "Title",
        "versions": versions,
    }


def _ref(to: str, **extra: object) -> dict:
    return {"issuer": "EASA", "document": "cs-23", "to": to, **extra}


def _aircraft(refs: list[dict]) -> dict:
    return {
        "manufacturer": "Dummy Mfg",
        "model_designation": "Dummy",
        "common_name": None,
        "categories": ["normal"],
        "notes": None,
        "tcb": [
            {
                "tcds": {"issuer": "EASA", "tcds_number": "EASA.A.000"},
                "notes": None,
                "certification_basis": [
                    {
                        "display_order": 1,
                        "entry_type": "regulation",
                        "raw_reference": "CS-23 Amendment N",
                        "applicability": None,
                        "applicability_notes": None,
                        "references": refs,
                    }
                ],
            }
        ],
    }


def _build(tmp_path: Path, provisions: list[dict], refs: list[dict] | None) -> Path:
    data = tmp_path / "data"
    doc_dir = data / "documents" / "easa" / "cs-23"
    doc_dir.mkdir(parents=True)
    (doc_dir / "_document.json").write_text(json.dumps(_document()))
    for p in provisions:
        (doc_dir / f"{p['number']}.json").write_text(json.dumps(p))
    (data / "aircraft").mkdir()
    if refs is not None:
        (data / "aircraft" / "dummy.json").write_text(json.dumps(_aircraft(refs)))
    out = tmp_path / "cert_basis.sqlite"
    build(data, out)
    return out


def _fails(tmp_path: Path, provisions: list[dict], refs: list[dict] | None) -> str:
    with pytest.raises(BuildError) as ei:
        _build(tmp_path, provisions, refs)
    return str(ei.value)


def _resolved(db: Path) -> set[tuple[str, str]]:
    with sqlite3.connect(db) as conn:
        return set(
            conn.execute(
                "SELECT p.number, dr.designator FROM cert_basis_resolved r "
                "JOIN provision_versions pv ON pv.id = r.provision_version_id "
                "JOIN provisions p ON p.id = pv.provision_id "
                "JOIN document_revisions dr ON dr.id = pv.revision_id"
            ).fetchall()
        )


# Old-style 23.1309 deleted at CS23-5; new 23.2510 created at CS23-5.
_OLD = _provision("1309", [_live("CS23-0"), _live("CS23-3"), _gone("CS23-5")])
_NEW = _provision("2510", [_live("CS23-5")])


def test_deleted_version_stored_without_text(tmp_path: Path) -> None:
    db = _build(tmp_path, [_OLD, _NEW], None)
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            "SELECT dr.designator, pv.text IS NULL, pv.deleted, pv.text_missing "
            "FROM provision_versions pv "
            "JOIN document_revisions dr ON dr.id = pv.revision_id "
            "JOIN provisions p ON p.id = pv.provision_id WHERE p.number = '1309' "
            "ORDER BY dr.ordinal"
        ).fetchall()
    assert rows == [("CS23-0", 0, 0, 0), ("CS23-3", 0, 0, 0), ("CS23-5", 1, 1, 0)]
    report = json.loads((tmp_path / "cert_basis_report.json").read_text())
    assert report["deleted"] == 1


def test_document_wide_ref_drops_deleted_provision(tmp_path: Path) -> None:
    db = _build(tmp_path, [_OLD, _NEW], [_ref("CS23-6")])
    assert _resolved(db) == {("2510", "CS23-5")}


def test_document_wide_ref_before_deletion_keeps_provision(tmp_path: Path) -> None:
    db = _build(tmp_path, [_OLD, _NEW], [_ref("CS23-4")])
    assert _resolved(db) == {("1309", "CS23-3")}


def test_scoped_ref_to_deleted_provision_fails(tmp_path: Path) -> None:
    msg = _fails(tmp_path, [_OLD, _NEW], [_ref("CS23-6", provisions=["1309"])])
    assert "deleted" in msg


def test_alias_to_deleted_version_fails(tmp_path: Path) -> None:
    p = _provision(
        "1309",
        [
            _live("CS23-0"),
            _gone("CS23-1"),
            {
                "designator": "CS23-2",
                "title_at_revision": "Title",
                "same_as_designator": "CS23-1",
            },
        ],
    )
    assert "aliases deleted version" in _fails(tmp_path, [p], None)


def test_deleting_a_provision_not_in_force_fails(tmp_path: Path) -> None:
    first = _provision("1", [_gone("CS23-0")])
    assert "not in force" in _fails(tmp_path, [first], None)
    twice = _provision("2", [_live("CS23-0"), _gone("CS23-1"), _gone("CS23-2")])
    assert "not in force" in _fails(tmp_path / "b", [twice], None)


def test_recreated_after_deletion(tmp_path: Path) -> None:
    p = _provision("1309", [_live("CS23-0"), _gone("CS23-2"), _live("CS23-4")])
    other = _provision("1", [_live("CS23-0")])
    db = _build(tmp_path, [p, other], [_ref("CS23-3")])
    assert _resolved(db) == {("1", "CS23-0")}
    db = _build(tmp_path / "b", [p], [_ref("CS23-6", provisions=["1309"])])
    assert _resolved(db) == {("1309", "CS23-4")}


def test_deleted_with_text_rejected_by_schema(tmp_path: Path) -> None:
    p = _provision("1309", [_live("CS23-0"), {**_live("CS23-1"), "deleted": True}])
    _fails(tmp_path, [p], None)
