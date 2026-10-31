"""Tests for the same_as_designator alias mechanism in build.py."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from build import BuildError, build


def _stage(tmp_path: Path, documents: list[dict], provisions: list[dict]) -> Path:
    data = tmp_path / "data"
    for p in documents:
        d = data / "documents" / p["issuer"].lower() / p["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "_document.json").write_text(json.dumps(p))
    for r in provisions:
        d = data / "documents" / r["issuer"].lower() / r["document"]
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{r['number']}.json").write_text(json.dumps(r))
    (data / "aircraft").mkdir(parents=True, exist_ok=True)
    return data


def _easa_part(amdts: list[tuple[str, int, str]]) -> dict:
    return {
        "issuer": "EASA",
        "doc_kind": "certification_spec",
        "code": "CS-23",
        "slug": "cs-23",
        "title": None,
        "revisions": [
            {"designator": d, "ordinal": o, "effective_date": e} for d, o, e in amdts
        ],
    }


def _section(section: str, versions: list[dict]) -> dict:
    return {
        "issuer": "EASA",
        "document": "cs-23",
        "number": section,
        "current_grouping": "A",
        "canonical_title": "Definitions",
        "versions": versions,
    }


def test_alias_resolves_to_target_text(tmp_path: Path) -> None:
    parts = [
        _easa_part(
            [
                ("CS23-0", 0, "2003-11-14"),
                ("CS23-1", 1, "2009-12-12"),
                ("CS23-2", 2, "2012-07-20"),
            ]
        )
    ]
    regs = [
        _section(
            "1",
            [
                {
                    "designator": "CS23-0",
                    "title_at_revision": "Definitions",
                    "text": "Original text.",
                },
                {
                    "designator": "CS23-1",
                    "title_at_revision": "Definitions",
                    "same_as_designator": "CS23-0",
                },
                {
                    "designator": "CS23-2",
                    "title_at_revision": "Definitions",
                    "same_as_designator": "CS23-1",
                },
            ],
        )
    ]
    data = _stage(tmp_path, parts, regs)
    out = tmp_path / "cert_basis.sqlite"
    build(data, out)

    with sqlite3.connect(out) as conn:
        rows = conn.execute(
            "SELECT dr.designator, pv.text, tr.designator "
            "FROM provision_versions pv "
            "JOIN document_revisions dr ON dr.id = pv.revision_id "
            "LEFT JOIN provision_versions t ON t.id = pv.same_as_version_id "
            "LEFT JOIN document_revisions tr ON tr.id = t.revision_id "
            "ORDER BY dr.ordinal"
        ).fetchall()
    assert rows == [
        ("CS23-0", "Original text.", None),
        ("CS23-1", "Original text.", "CS23-0"),
        ("CS23-2", "Original text.", "CS23-1"),
    ]


def test_alias_target_must_be_earlier(tmp_path: Path) -> None:
    parts = [_easa_part([("CS23-0", 0, "2003-11-14"), ("CS23-1", 1, "2009-12-12")])]
    regs = [
        _section(
            "1",
            [
                {
                    "designator": "CS23-0",
                    "title_at_revision": "Definitions",
                    "same_as_designator": "CS23-1",
                },
                {
                    "designator": "CS23-1",
                    "title_at_revision": "Definitions",
                    "text": "text",
                },
            ],
        )
    ]
    data = _stage(tmp_path, parts, regs)
    with pytest.raises(BuildError) as exc:
        build(data, tmp_path / "cert_basis.sqlite")
    assert "earlier version" in str(exc.value)


def test_easa_document_code_has_no_cfr_title(tmp_path: Path) -> None:
    parts = [_easa_part([("CS23-0", 0, "2003-11-14")])]
    regs = [
        _section(
            "1",
            [
                {
                    "designator": "CS23-0",
                    "title_at_revision": "Definitions",
                    "text": "text",
                }
            ],
        )
    ]
    data = _stage(tmp_path, parts, regs)
    out = tmp_path / "cert_basis.sqlite"
    build(data, out)
    with sqlite3.connect(out) as conn:
        row = conn.execute(
            "SELECT i.code, d.doc_kind, d.code FROM documents d "
            "JOIN issuers i ON i.id = d.issuer_id"
        ).fetchone()
    assert row == ("EASA", "certification_spec", "CS-23")
