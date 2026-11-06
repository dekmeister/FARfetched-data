"""Issuer `NATO` (STANAG 4671 / AEP-4671): seeded, and a document under it builds.

The shape is the real one: a `standard` of two editions whose ordinals leave a
gap (the missing Edition 2 / Edition A have no representation), a paragraph
number reused for another requirement (Ed. 1 U1719 vs Ed. B U1719), and a
requirement that carries on under a new number.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from build import build

URL = "https://nso.nato.int/nso/nsdd/main/standards/stanag-details/9175/EN"


def _version(designator: str, number: str | None, text: str | None = None) -> dict:
    v: dict = {
        "designator": designator,
        "title_at_revision": "Title",
        "source_url": URL,
    }
    if text is None:
        v["deleted"] = True
    else:
        v["text"] = text
    if number is not None:
        v["number"] = number
    return v


def _provision(key: str, number: str, versions: list[dict]) -> dict:
    return {
        "issuer": "NATO",
        "document": "stanag-4671",
        "key": key,
        "number": number,
        "current_grouping": "Subpart I – UA Control Station",
        "canonical_title": "Title",
        "versions": versions,
    }


def test_nato_document_builds_with_a_gap_in_ordinals(tmp_path: Path) -> None:
    data = tmp_path / "data"
    doc = data / "documents" / "nato" / "stanag-4671"
    doc.mkdir(parents=True)
    (data / "aircraft").mkdir()
    (doc / "_document.json").write_text(
        json.dumps(
            {
                "issuer": "NATO",
                "doc_kind": "standard",
                "code": "STANAG 4671",
                "slug": "stanag-4671",
                "title": "Unmanned Aircraft Systems Airworthiness Requirements (USAR)",
                "revisions": [
                    {"designator": "Ed1", "ordinal": 0, "effective_date": "2009-09-03"},
                    {
                        "designator": "EdB-V1",
                        "ordinal": 2,
                        "effective_date": "2019-04-02",
                    },
                ],
            }
        )
    )
    provisions = [
        # Ed. 1 U1719 "UCS power supply" carries on as Ed. B U1713 ...
        _provision(
            "U1719",
            "U1713",
            [
                _version("Ed1", "U1719", "power"),
                _version("EdB-V1", None, "power supply"),
            ],
        ),
        # ... and Ed. B prints U1719 for a new requirement.
        _provision("U1719-edb-v1", "U1719", [_version("EdB-V1", None, "Exits")]),
    ]
    for p in provisions:
        (doc / f"{p['key']}.json").write_text(json.dumps(p))
    out = tmp_path / "cert_basis.sqlite"
    build(data, out)
    with sqlite3.connect(out) as conn:
        assert conn.execute(
            "SELECT name, kind, country, successor_id FROM issuers WHERE code = 'NATO'"
        ).fetchone() == ("North Atlantic Treaty Organization", "military", None, None)
        assert conn.execute(
            "SELECT dr.designator, dr.ordinal FROM document_revisions dr "
            "JOIN documents d ON d.id = dr.document_id WHERE d.slug = 'stanag-4671' "
            "ORDER BY dr.ordinal"
        ).fetchall() == [("Ed1", 0), ("EdB-V1", 2)]
