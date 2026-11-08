"""Tests for the same_as_designator alias mechanism in build.py."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import factories as fx

from certbuild.errors import BuildError
from certbuild.pipeline import build


def _stage(tmp_path: Path, documents: list[dict], provisions: list[dict]) -> Path:
    return fx.stage(tmp_path, documents, provisions)


def _easa_part(amdts: list[tuple[str, int, str]]) -> dict:
    return fx.document(
        "EASA", "cs-23", amdts, doc_kind="certification_spec", code="CS-23"
    )


def _section(section: str, versions: list[dict]) -> dict:
    return fx.provision(
        "EASA", "cs-23", section, versions, grouping="A", title="Definitions"
    )


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
