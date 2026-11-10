"""What ELOS, special condition and exemption lines cite (docs/SQLITE.md
§Citations): resolved against the documents, never part of the basis."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import factories as fx
import pytest


def _cite(number: str = "1309", **extra: Any) -> dict[str, Any]:
    return {"issuer": "FAA", "document": "23", "number": number, **extra}


def _elos(*citations: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return fx.entry(
        [],
        9,
        entry_type="elos",
        raw_reference="ELOS for 23.1309 and its paragraphs",
        citations=list(citations),
        **extra,
    )


def _rows(db: Path) -> list[tuple[str, str | None, str, str | None]]:
    """(number, paragraph, version_basis, designator linked) per citation."""
    with sqlite3.connect(db) as conn:
        return conn.execute(
            "SELECT p.number, c.paragraph, c.version_basis, dr.designator "
            "FROM cert_basis_citations c "
            "JOIN provisions p ON p.id = c.provision_id "
            "LEFT JOIN provision_versions pv ON pv.id = c.provision_version_id "
            "LEFT JOIN document_revisions dr ON dr.id = pv.revision_id "
            "ORDER BY c.entry_id, c.seq"
        ).fetchall()


PROVISION = fx.cfr_provision("23", "1309", [0, 7, 14])


class TestVersionChoice:
    def test_stated_amendment_wins_over_the_basis(self, tmp_path: Path) -> None:
        out = fx.build_part23(
            tmp_path,
            [PROVISION],
            [fx.entry([fx.cfr_ref("23-14")]), _elos(_cite(at="23-7"))],
        )
        assert _rows(out) == [("1309", None, "stated", "23-7")]

    def test_stated_is_the_version_in_force_at_the_amendment(
        self, tmp_path: Path
    ) -> None:
        out = fx.build_part23(tmp_path, [PROVISION], [_elos(_cite(at="23-10"))])
        assert _rows(out) == [("1309", None, "stated", "23-7")]

    def test_basis_version(self, tmp_path: Path) -> None:
        out = fx.build_part23(
            tmp_path, [PROVISION], [fx.entry([fx.cfr_ref("23-10")]), _elos(_cite())]
        )
        assert _rows(out) == [("1309", None, "basis", "23-7")]

    def test_several_basis_versions_link_none(self, tmp_path: Path) -> None:
        out = fx.build_part23(
            tmp_path,
            [PROVISION],
            [
                fx.entry([fx.cfr_ref("23-5")], 1),
                fx.entry([fx.cfr_ref("23-20")], 2),
                _elos(_cite()),
            ],
        )
        assert _rows(out) == [("1309", None, "basis_several", None)]

    def test_neither_links_the_latest_text(self, tmp_path: Path) -> None:
        out = fx.build_part23(tmp_path, [PROVISION], [_elos(_cite())])
        assert _rows(out) == [("1309", None, "latest", "23-14")]

    def test_latest_skips_a_deletion(self, tmp_path: Path) -> None:
        gone = fx.provision(
            "FAA",
            "23",
            "1309",
            [fx.cfr_version("23-0"), fx.cfr_version("23-7"), fx.deleted("23-14")],
        )
        out = fx.build_part23(tmp_path, [gone], [_elos(_cite())])
        assert _rows(out) == [("1309", None, "latest", "23-7")]

    def test_latest_prefers_real_text(self, tmp_path: Path) -> None:
        unreadable = fx.provision(
            "FAA",
            "23",
            "1309",
            [fx.cfr_version("23-0"), fx.cfr_version("23-7", text="TEXT MISSING")],
        )
        out = fx.build_part23(tmp_path, [unreadable], [_elos(_cite())])
        assert _rows(out) == [("1309", None, "latest", "23-0")]


def test_citations_are_not_part_of_the_basis(tmp_path: Path) -> None:
    provs = [PROVISION, fx.cfr_provision("23", "143", [0])]
    regulation = fx.entry(
        [fx.cfr_ref("23-20", provisions=["143"])], raw_reference="23.143"
    )
    without = fx.build_part23(tmp_path / "a", provs, [regulation])
    cited = fx.build_part23(tmp_path / "b", provs, [regulation, _elos(_cite())])
    assert fx.resolved(cited) == fx.resolved(without)
    assert fx.resolved_versions(cited) == {("143", "23-0")}


class TestFailLoud:
    @pytest.mark.parametrize(
        ("citation", "message"),
        [
            ({"issuer": "FAA", "document": "99", "number": "1"}, "unknown document"),
            (_cite("4242"), "unknown provision"),
            (_cite(at="23-63"), "unknown revision"),
            (_cite(paragraph="not labels"), "not a run"),
        ],
    )
    def test_bad_citation(
        self, tmp_path: Path, citation: dict[str, Any], message: str
    ) -> None:
        err = fx.part23_fails(tmp_path, [PROVISION], [_elos(citation)])
        assert message in err

    def test_section_deleted_at_the_stated_amendment(self, tmp_path: Path) -> None:
        gone = fx.provision(
            "FAA", "23", "1309", [fx.cfr_version("23-0"), fx.deleted("23-14")]
        )
        err = fx.part23_fails(tmp_path, [gone], [_elos(_cite(at="23-20"))])
        assert "not in force" in err

    def test_section_not_yet_in_force(self, tmp_path: Path) -> None:
        err = fx.part23_fails(
            tmp_path,
            [fx.cfr_provision("23", "1309", [7])],
            [_elos(_cite(at="23-3"))],
        )
        assert "1309" in err

    def test_gap_must_quote_the_line(self, tmp_path: Path) -> None:
        entry = fx.entry(
            [],
            9,
            entry_type="elos",
            raw_reference="ELOS",
            citation_gaps=[{"cited": "JAR 25.1", "reason": "doc_not_in_dataset"}],
        )
        err = fx.part23_fails(tmp_path, [PROVISION], [entry])
        assert "is not in the line" in err

    def test_schema_rejects_citations_on_a_regulation_line(
        self, tmp_path: Path
    ) -> None:
        entry = fx.entry([fx.cfr_ref("23-7")], citations=[_cite()])
        fx.part23_fails(tmp_path, [PROVISION], [entry])


def test_a_paragraph_the_version_lacks_is_counted_not_fatal(tmp_path: Path) -> None:
    text = "(a) First.\n(b) Second."
    prov = fx.provision("FAA", "23", "1309", [fx.cfr_version("23-0", text=text)])
    out = fx.build_part23(
        tmp_path,
        [prov],
        [_elos(_cite(paragraph="(a)"), _cite(paragraph="(z)"))],
    )
    report = json.loads(out.with_name("cert_basis_report.json").read_text())
    assert report["citations"]["paragraphs"] == {
        "verified": 1,
        "unverifiable": 0,
        "unmatched": 1,
        "unchecked": 0,
    }
    assert _rows(out)[1][1] == "(z)"


def test_report_counts(tmp_path: Path) -> None:
    gap = {"cited": "23.1309", "reason": "withheld_basis_list"}
    out = fx.build_part23(
        tmp_path,
        [PROVISION],
        [_elos(_cite(), citation_gaps=[gap])],
    )
    citations = json.loads(out.with_name("cert_basis_report.json").read_text())[
        "citations"
    ]
    assert citations["by_issuer_and_type"]["FAA"]["elos"] == {
        "entries": 1,
        "entries_with_citations": 1,
        "entries_with_gaps": 1,
        "citations": 1,
        "gaps": 1,
    }
    assert citations["version_basis"] == {"latest": 1}
    assert citations["gaps_by_reason"] == {"withheld_basis_list": 1}
    assert citations["entries_withheld"] == 1
