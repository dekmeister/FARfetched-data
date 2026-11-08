"""Schema v7: a provision's `key` is its identity, its printed `number` a label
that a document may reuse for another provision or change (renumber).

The handbook here is MIL-HDBK-516-shaped: four editions A..D, where
- 516's 4.1.3 is deleted at B and B prints an unrelated 4.1.3 (number reuse);
- B's 5.2.3 is renumbered 5.2.2 at C (one key, two numbers).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from certbuild.errors import BuildError
from certbuild.pipeline import build

EDITIONS = ["A", "B", "C", "D"]


def _document() -> dict:
    return {
        "issuer": "DOD",
        "doc_kind": "handbook",
        "code": "MIL-HDBK-516",
        "slug": "mil-hdbk-516",
        "title": "Airworthiness Certification Criteria",
        "revisions": [
            {"designator": d, "ordinal": n, "effective_date": f"{2002 + n}-01-01"}
            for n, d in enumerate(EDITIONS)
        ],
    }


def _text(designator: str, number: str | None = None) -> dict:
    v: dict = {
        "designator": designator,
        "title_at_revision": "Criterion",
        "text": f"criterion text at {designator}",
        "source_url": "https://assist.dla.mil",
    }
    if number is not None:
        v["number"] = number
    return v


def _gone(designator: str) -> dict:
    return {"designator": designator, "title_at_revision": "Criterion", "deleted": True}


def _provision(key: str, number: str, versions: list[dict]) -> dict:
    return {
        "issuer": "DOD",
        "document": "mil-hdbk-516",
        "key": key,
        "number": number,
        "current_grouping": "Systems engineering",
        "canonical_title": f"Criterion {key}",
        "versions": versions,
    }


# The scenario from the module docstring.
HANDBOOK = [
    _provision("4.1.3", "4.1.3", [_text("A"), _gone("B")]),
    _provision("4.1.3-516b", "4.1.3", [_text("B"), _text("D")]),
    _provision("5.2.3", "5.2.2", [_text("B", number="5.2.3"), _text("C")]),
]


def _ref(to: str, **extra: object) -> dict:
    return {"issuer": "DOD", "document": "mil-hdbk-516", "to": to, **extra}


def _exclude(*numbers: str) -> dict:
    return {
        "issuer": "DOD",
        "document": "mil-hdbk-516",
        "effect": "exclude",
        "provisions": list(numbers),
    }


def _aircraft(refs: list[dict]) -> dict:
    return {
        "manufacturer": "Dummy Mfg",
        "model_designation": "X-1",
        "common_name": None,
        "notes": None,
        "tcb": [
            {
                "tcds": {"issuer": "FAA", "tcds_number": "DUMMY1"},
                "categories": ["special"],
                "notes": None,
                "certification_basis": [
                    {
                        "display_order": 1,
                        "entry_type": "other",
                        "raw_reference": "verbatim",
                        "applicability": None,
                        "applicability_notes": None,
                        "references": refs,
                    }
                ],
            }
        ],
    }


def _stage(tmp_path: Path, provisions: list[dict], refs: list[dict] | None) -> Path:
    data = tmp_path / "data"
    doc_dir = data / "documents" / "dod" / "mil-hdbk-516"
    doc_dir.mkdir(parents=True)
    (doc_dir / "_document.json").write_text(json.dumps(_document()))
    for p in provisions:
        (doc_dir / f"{p['key']}.json").write_text(json.dumps(p))
    (data / "aircraft").mkdir()
    if refs is not None:
        (data / "aircraft" / "x-1.json").write_text(json.dumps(_aircraft(refs)))
    return data


def _build(tmp_path: Path, provisions: list[dict], refs: list[dict] | None) -> Path:
    out = tmp_path / "cert_basis.sqlite"
    build(_stage(tmp_path, provisions, refs), out)
    return out


def _fails(tmp_path: Path, provisions: list[dict], refs: list[dict] | None) -> str:
    with pytest.raises(BuildError) as ei:
        _build(tmp_path, provisions, refs)
    return str(ei.value)


def _resolved(db: Path) -> set[tuple[str, str]]:
    """(provision key, designator) of every resolved row."""
    with sqlite3.connect(db) as conn:
        return set(
            conn.execute(
                "SELECT p.key, dr.designator FROM cert_basis_resolved r "
                "JOIN provision_versions pv ON pv.id = r.provision_version_id "
                "JOIN provisions p ON p.id = pv.provision_id "
                "JOIN document_revisions dr ON dr.id = pv.revision_id"
            ).fetchall()
        )


class TestIdentity:
    def test_renumbered_provision_keeps_one_key(self, tmp_path: Path) -> None:
        db = _build(tmp_path, HANDBOOK, None)
        with sqlite3.connect(db) as conn:
            assert conn.execute(
                "SELECT p.number, dr.designator, pv.number "
                "FROM provision_versions pv "
                "JOIN provisions p ON p.id = pv.provision_id "
                "JOIN document_revisions dr ON dr.id = pv.revision_id "
                "WHERE p.key = '5.2.3' ORDER BY dr.ordinal"
            ).fetchall() == [("5.2.2", "B", "5.2.3"), ("5.2.2", "C", "5.2.2")]

    def test_number_reused_by_another_key(self, tmp_path: Path) -> None:
        db = _build(tmp_path, HANDBOOK, None)
        with sqlite3.connect(db) as conn:
            rows = conn.execute(
                "SELECT p.key, dr.designator, pv.deleted FROM provision_versions pv "
                "JOIN provisions p ON p.id = pv.provision_id "
                "JOIN document_revisions dr ON dr.id = pv.revision_id "
                "WHERE pv.number = '4.1.3' ORDER BY dr.ordinal, p.key"
            ).fetchall()
        # B both deletes the old 4.1.3 and prints a new one.
        assert rows == [
            ("4.1.3", "A", 0),
            ("4.1.3", "B", 1),
            ("4.1.3-516b", "B", 0),
            ("4.1.3-516b", "D", 0),
        ]

    def test_report_counts_the_document(self, tmp_path: Path) -> None:
        out = tmp_path / "cert_basis.sqlite"
        report = build(_stage(tmp_path, HANDBOOK, None), out)
        assert report["documents"]["DOD/mil-hdbk-516"] == {
            "revisions": 4,
            "provisions": 3,
            "versions": 6,
            "renumbered": 1,
        }

    def test_two_in_force_provisions_with_one_number_fail(self, tmp_path: Path) -> None:
        provs = [
            _provision("4.1.1", "4.1.1", [_text("A")]),
            _provision("4.1.1-x", "4.1.1", [_text("A")]),
        ]
        # Both are printed at A, so the DDL catches it before the sweep does.
        message = _fails(tmp_path, provs, None)
        assert "UNIQUE constraint failed: provision_versions.document_id" in message

    def test_clash_through_a_sparse_version_fails(self, tmp_path: Path) -> None:
        # 4.1.1 has no version at C but is still in force there when 4.1.2
        # is renumbered onto it.
        provs = [
            _provision("4.1.1", "4.1.1", [_text("A")]),
            _provision("4.1.2", "4.1.1", [_text("A", number="4.1.2"), _text("C")]),
        ]
        message = _fails(tmp_path, provs, None)
        assert "mil-hdbk-516 at C: number '4.1.1'" in message
        assert "4.1.1, 4.1.2" in message

    def test_reuse_after_the_old_one_is_deleted_is_fine(self, tmp_path: Path) -> None:
        provs = [
            _provision("4.1.1", "4.1.1", [_text("A"), _gone("C")]),
            _provision("4.1.2", "4.1.1", [_text("A", number="4.1.2"), _text("C")]),
        ]
        _build(tmp_path, provs, None)

    def test_top_level_number_must_be_the_latest(self, tmp_path: Path) -> None:
        provs = [_provision("5.2.3", "5.2.3", [_text("B"), _text("C", number="5.2.2")])]
        message = _fails(tmp_path, provs, None)
        assert "not the number printed at the latest version ('5.2.2'" in message

    def test_path_must_match_key(self, tmp_path: Path) -> None:
        data = _stage(tmp_path, HANDBOOK, None)
        doc_dir = data / "documents" / "dod" / "mil-hdbk-516"
        (doc_dir / "5.2.3.json").rename(doc_dir / "5.2.2.json")
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "cert_basis.sqlite")
        assert "expected at documents/dod/mil-hdbk-516/5.2.3.json" in str(ei.value)


class TestRefsByNumber:
    @pytest.mark.parametrize(
        ("refs", "expected"),
        [
            # The number is read at `to`, across the renumber.
            ([_ref("B", provisions=["5.2.3"])], {("5.2.3", "B")}),
            ([_ref("C", provisions=["5.2.2"])], {("5.2.3", "C")}),
            ([_ref("D", provisions=["5.2.2"])], {("5.2.3", "C")}),
            # A reused number names whichever provision carried it at `to`.
            ([_ref("A", provisions=["4.1.3"])], {("4.1.3", "A")}),
            ([_ref("B", provisions=["4.1.3"])], {("4.1.3-516b", "B")}),
            ([_ref("D", provisions=["4.1.3"])], {("4.1.3-516b", "D")}),
        ],
    )
    def test_scoped_ref(
        self, tmp_path: Path, refs: list[dict], expected: set[tuple[str, str]]
    ) -> None:
        assert _resolved(_build(tmp_path, HANDBOOK, refs)) == expected

    @pytest.mark.parametrize(
        ("refs", "expected"),
        [
            ([_ref("C"), _exclude("5.2.2")], {("4.1.3-516b", "B")}),
            ([_ref("B"), _exclude("5.2.3")], {("4.1.3-516b", "B")}),
            # Excludes read numbers at the entry's highest include `to`.
            ([_ref("B"), _ref("C", provisions=["5.2.2"]), _exclude("4.1.3")], set()),
        ],
    )
    def test_exclude_ref(
        self, tmp_path: Path, refs: list[dict], expected: set[tuple[str, str]]
    ) -> None:
        got = _resolved(_build(tmp_path, HANDBOOK, refs))
        assert got - {("5.2.3", "C")} == expected

    @pytest.mark.parametrize(
        ("refs", "message"),
        [
            ([_ref("D", provisions=["5.2.3"])], "no provision mil-hdbk-516.5.2.3 at"),
            ([_ref("A", provisions=["5.2.2"])], "no provision mil-hdbk-516.5.2.2 at"),
            ([_ref("D", provisions=["9.9"])], "unknown provision mil-hdbk-516.9.9"),
            ([_ref("B"), _exclude("5.2.2")], "no provision mil-hdbk-516.5.2.2 at"),
        ],
    )
    def test_fails_loud(self, tmp_path: Path, refs: list[dict], message: str) -> None:
        assert message in _fails(tmp_path, HANDBOOK, refs)

    def test_deleted_number_resolves_to_the_deletion(self, tmp_path: Path) -> None:
        # Nothing else carries 4.1.1 at C, so the ref finds the deleted
        # provision and fails as a ref to a deletion, as before v7.
        provs = [_provision("4.1.1", "4.1.1", [_text("A"), _gone("C")])]
        message = _fails(tmp_path, provs, [_ref("C", provisions=["4.1.1"])])
        assert "to a revision that deleted it" in message
