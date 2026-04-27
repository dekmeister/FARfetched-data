"""Tests for the same_as_designator alias mechanism in build.py."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from build import BuildError, build


def _stage(tmp_path: Path, parts: list[dict], regulations: list[dict]) -> Path:
    data = tmp_path / "data"
    for p in parts:
        slug = p["part"].lower().replace(" ", "-")
        d = data / "regulations" / p["authority"].lower() / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "_part.json").write_text(json.dumps(p))
    for r in regulations:
        slug = r["part"].lower().replace(" ", "-")
        d = data / "regulations" / r["authority"].lower() / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{r['section']}.json").write_text(json.dumps(r))
    (data / "aircraft").mkdir(parents=True, exist_ok=True)
    return data


def _easa_part(amdts: list[tuple[str, int, str]]) -> dict:
    return {
        "authority": "EASA",
        "part": "CS-23",
        "amendments": [
            {"designator": d, "ordinal": o, "effective_date": e} for d, o, e in amdts
        ],
    }


def _section(section: str, amendments: list[dict]) -> dict:
    return {
        "authority": "EASA",
        "part": "CS-23",
        "section": section,
        "current_subpart": "A",
        "canonical_title": "Definitions",
        "amendments": amendments,
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
                    "title_at_amendment": "Definitions",
                    "text": "Original text.",
                },
                {
                    "designator": "CS23-1",
                    "title_at_amendment": "Definitions",
                    "same_as_designator": "CS23-0",
                },
                {
                    "designator": "CS23-2",
                    "title_at_amendment": "Definitions",
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
            "SELECT a.designator, sa.text, sa.same_as_designator "
            "FROM section_amendments sa "
            "JOIN amendments a ON a.id = sa.amendment_id "
            "ORDER BY a.ordinal"
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
                    "title_at_amendment": "Definitions",
                    "same_as_designator": "CS23-1",
                },
                {
                    "designator": "CS23-1",
                    "title_at_amendment": "Definitions",
                    "text": "text",
                },
            ],
        )
    ]
    data = _stage(tmp_path, parts, regs)
    with pytest.raises(BuildError) as exc:
        build(data, tmp_path / "cert_basis.sqlite")
    assert "earlier amendment" in str(exc.value)


def test_easa_part_without_title_number(tmp_path: Path) -> None:
    parts = [_easa_part([("CS23-0", 0, "2003-11-14")])]
    regs = [
        _section(
            "1",
            [
                {
                    "designator": "CS23-0",
                    "title_at_amendment": "Definitions",
                    "text": "text",
                }
            ],
        )
    ]
    data = _stage(tmp_path, parts, regs)
    out = tmp_path / "cert_basis.sqlite"
    build(data, out)
    with sqlite3.connect(out) as conn:
        row = conn.execute("SELECT title_number FROM regulation_parts").fetchone()
    assert row[0] is None
