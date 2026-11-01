"""Tests for the label-line text format: build.parse_paragraphs, the
provision_paragraphs table, and paragraph-qualified cert-basis refs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from build import (
    BuildError,
    TextFormatError,
    build,
    check_text_format,
    flatten_text,
    label_values,
    paragraph_ref_paths,
    parse_paragraphs,
)


def rows(text: str) -> list[tuple[int, str | None, str | None, str]]:
    return [
        (p.depth, p.label, p.path, p.text) for p in parse_paragraphs(text).paragraphs
    ]


def error(text: str) -> str:
    with pytest.raises(TextFormatError) as ei:
        parse_paragraphs(text)
    return str(ei.value)


SECTION_1309 = """\
The requirements of this section apply.
(a) Each item of equipment:
  (1) When performing its intended function, may not--
    (i) Equipment essential to safe operation; or
    (ii) Other equipment.
  [(4) In a commuter category airplane, must be designed.]
(b) The design must comply with the following:
  (1) It must perform its intended function.
  (2) It must also.
  Each item of equipment must also comply.
(c)(1) Text where (c) has no words of its own.
  (2) Second item of (c).
(d) [Reserved]"""


# ---------------------------------------------------------------------------
# Rules 1-2: lines and labels


class TestLinesAndLabels:
    def test_single_line_is_flat_even_with_labels(self) -> None:
        parsed = parse_paragraphs("(a) One. (b) Two.")
        assert not parsed.structured
        assert rows("(a) One. (b) Two.") == [(0, None, None, "(a) One. (b) Two.")]

    def test_structured_text(self) -> None:
        parsed = parse_paragraphs(SECTION_1309)
        assert parsed.structured
        assert rows(SECTION_1309) == [
            (0, None, None, "The requirements of this section apply."),
            (1, "(a)", "(a)", "Each item of equipment:"),
            (2, "(1)", "(a)(1)", "When performing its intended function, may not--"),
            (3, "(i)", "(a)(1)(i)", "Equipment essential to safe operation; or"),
            (3, "(ii)", "(a)(1)(ii)", "Other equipment."),
            (
                2,
                "[(4)",
                "(a)(4)",
                "In a commuter category airplane, must be designed.]",
            ),
            (1, "(b)", "(b)", "The design must comply with the following:"),
            (2, "(1)", "(b)(1)", "It must perform its intended function."),
            (2, "(2)", "(b)(2)", "It must also."),
            (1, None, "(b)", "Each item of equipment must also comply."),
            (1, "(c)", "(c)", ""),
            (2, "(1)", "(c)(1)", "Text where (c) has no words of its own."),
            (2, "(2)", "(c)(2)", "Second item of (c)."),
            (1, "(d)", "(d)", "[Reserved]"),
        ]

    def test_seq_is_document_order(self) -> None:
        paras = parse_paragraphs(SECTION_1309).paragraphs
        assert [p.seq for p in paras] == list(range(len(paras)))

    def test_bracket_with_space_and_removed(self) -> None:
        assert rows("[ (a) First.\n[(b) [Removed.]]") == [
            (1, "[ (a)", "(a)", "First."),
            (1, "[(b)", "(b)", "[Removed.]]"),
        ]

    def test_label_only_line(self) -> None:
        assert rows("(a)\n  (1) Child.")[0] == (1, "(a)", "(a)", "")

    def test_blank_lines_are_ignored(self) -> None:
        assert rows("(a) One.\n\n(b) Two.") == rows("(a) One.\n(b) Two.")

    def test_parenthesised_word_is_not_a_label(self) -> None:
        assert rows("(a) One.\n(OEI) power is defined.")[1] == (
            0,
            None,
            None,
            "(OEI) power is defined.",
        )

    def test_label_needs_a_following_space(self) -> None:
        assert rows("(a) One.\n(b)Two.")[1][1] is None

    @pytest.mark.parametrize(
        ("text", "hint"),
        [
            ("(a) One.\n\t(1) Two.", "tab"),
            ("(a) One. \n(b) Two.", "trailing whitespace"),
            ("  (a) Indented single line.", "indented"),
            ("\n\n", "no text"),
        ],
    )
    def test_line_errors(self, text: str, hint: str) -> None:
        assert hint in error(text)


# ---------------------------------------------------------------------------
# Rules 3-4, 6-7: depth from labels, indentation for ties and as a check


class TestDepth:
    def test_label_styles(self) -> None:
        assert label_values("i") == {"lower_alpha": 9, "lower_roman": 1}
        assert label_values("aa") == {"lower_alpha": 27}
        assert label_values("xiv") == {"lower_roman": 14}
        assert label_values("C") == {"upper_alpha": 3}
        assert label_values("c") == {"lower_alpha": 3}  # never roman 100
        assert label_values("bo") == {}
        assert label_values("07") == {}

    def test_i_after_h_continues_the_letters(self) -> None:
        assert rows("(h) H.\n(i) I.")[1][2] == "(i)"

    def test_i_under_h_by_indentation(self) -> None:
        assert rows("(h) H.\n  (i) Roman one.")[1][2] == "(h)(i)"

    def test_tie_after_number_resolved_by_indentation(self) -> None:
        base = "(h) H.\n  (1) One.\n"
        assert rows(base + "(i) Letter.")[2][2] == "(i)"
        assert rows(base + "    (i) Roman.")[2][2] == "(h)(1)(i)"

    def test_level_5_number(self) -> None:
        text = "(a) A.\n  (1) B.\n    (i) C.\n      (A) D.\n        (1) E.\n" + (
            "        (2) F.\n      (B) G."
        )
        assert [r[2] for r in rows(text)] == [
            "(a)",
            "(a)(1)",
            "(a)(1)(i)",
            "(a)(1)(i)(A)",
            "(a)(1)(i)(A)(1)",
            "(a)(1)(i)(A)(2)",
            "(a)(1)(i)(B)",
        ]

    def test_indentation_width_is_relative(self) -> None:
        assert [r[2] for r in rows("(a) A.\n     (1) B.\n(b) C.")] == [
            "(a)",
            "(a)(1)",
            "(b)",
        ]

    def test_wrong_indentation_fails(self) -> None:
        assert "indentation" in error("(a) A.\n(1) B.")
        assert "indentation" in error("(a) A.\n  (b) B.")

    def test_out_of_sequence_fails(self) -> None:
        assert "continues no open level" in error("(a) A.\n  (2) B.")
        # (a) could only open a new level under (b), and isn't indented to.
        assert "label (a)" in error("(b) B.\n(a) A.")

    def test_gaps_are_counted_not_errors(self) -> None:
        assert parse_paragraphs("(a) A.\n(c) C.").gaps == 1
        assert parse_paragraphs("(b) Text starts at b.\n(c) C.").gaps == 1
        assert parse_paragraphs(SECTION_1309).gaps == 1  # (1) -> [(4)

    def test_unlabelled_lines_attach_by_indentation(self) -> None:
        text = "(a) A.\n  (1) B.\n    More of (1).\n  More of (a).\nTop level again."
        assert [(r[0], r[2]) for r in rows(text)][2:] == [
            (2, "(a)(1)"),
            (1, "(a)"),
            (0, None),
        ]


# ---------------------------------------------------------------------------
# flatten and paragraph-ref qualifiers


def test_flatten_drops_layout_only() -> None:
    assert flatten_text(SECTION_1309).startswith(
        "The requirements of this section apply. (a) Each item of equipment: (1) When"
    )
    assert flatten_text("a\n\n  b") == "a b"
    assert flatten_text("one  two") == "one  two"  # inner spacing is wording


class TestParagraphRefPaths:
    paths = {p.path for p in parse_paragraphs(SECTION_1309).paragraphs if p.path}

    @pytest.mark.parametrize(
        "qualifier",
        ["(a)", "(a)(1)(ii)", "(b)(1)(2)", "(a)(1)(i)(ii)(4)(b)(2)(c)(1)", "(c1) "],
    )
    def test_matches(self, qualifier: str) -> None:
        assert paragraph_ref_paths(qualifier, self.paths) == []

    def test_reports_missing_tokens(self) -> None:
        assert paragraph_ref_paths("(a)(e)", self.paths) == ["(e)"]
        assert paragraph_ref_paths("(c3)", self.paths) == ["(3)"]

    def test_not_a_qualifier(self) -> None:
        assert paragraph_ref_paths("(a) and (b)", self.paths) is None


# ---------------------------------------------------------------------------
# The build: table, report, failures


_DOC = {
    "issuer": "FAA",
    "doc_kind": "regulation",
    "code": "14 CFR 23",
    "slug": "23",
    "title": None,
    "revisions": [
        {"designator": "23-0", "ordinal": 0, "effective_date": "1965-02-01"},
        {"designator": "23-1", "ordinal": 1, "effective_date": "1966-01-01"},
    ],
}


def _provision(number: str, versions: list[dict]) -> dict:
    return {
        "issuer": "FAA",
        "document": "23",
        "number": number,
        "current_grouping": None,
        "canonical_title": "Title",
        "versions": [{"title_at_revision": "Title", **v} for v in versions],
    }


def _aircraft(refs: list[dict]) -> dict:
    return {
        "manufacturer": "Dummy Mfg",
        "model_designation": "Dummy",
        "common_name": None,
        "categories": ["normal"],
        "notes": None,
        "tcb": [
            {
                "tcds": {"issuer": "FAA", "tcds_number": "A00XX"},
                "notes": None,
                "certification_basis": [
                    {
                        "display_order": 1,
                        "entry_type": "regulation",
                        "raw_reference": "14 CFR 23.1309(b)",
                        "applicability": None,
                        "applicability_notes": None,
                        "references": refs,
                    }
                ],
            }
        ],
    }


def _write(tmp_path: Path, provisions: list[dict], refs: list[dict] | None) -> Path:
    data = tmp_path / "data"
    doc_dir = data / "documents" / "faa" / "23"
    doc_dir.mkdir(parents=True)
    (doc_dir / "_document.json").write_text(json.dumps(_DOC))
    for p in provisions:
        (doc_dir / f"{p['number']}.json").write_text(json.dumps(p))
    (data / "aircraft").mkdir()
    if refs is not None:
        (data / "aircraft" / "dummy.json").write_text(json.dumps(_aircraft(refs)))
    return data


def _build(tmp_path: Path, provisions: list[dict], refs: list[dict] | None) -> Path:
    out = tmp_path / "cert_basis.sqlite"
    build(_write(tmp_path, provisions, refs), out)
    return out


def _fails(tmp_path: Path, provisions: list[dict], refs: list[dict] | None) -> str:
    with pytest.raises(BuildError) as ei:
        _build(tmp_path, provisions, refs)
    assert not (tmp_path / "cert_basis.sqlite").exists()
    return str(ei.value)


def _ref(paragraph: str, number: str = "1309", to: str = "23-1") -> dict:
    return {
        "issuer": "FAA",
        "document": "23",
        "to": to,
        "provisions": [number],
        "paragraph": paragraph,
    }


_STRUCTURED = _provision(
    "1309",
    [
        {"designator": "23-0", "text": "(a) Flat at the original issue. (b) Two."},
        {"designator": "23-1", "text": SECTION_1309},
    ],
)


class TestBuild:
    def test_paragraph_rows(self, tmp_path: Path) -> None:
        db = _build(tmp_path, [_STRUCTURED], None)
        with sqlite3.connect(db) as conn:
            got = conn.execute(
                "SELECT dr.designator, pp.seq, pp.depth, pp.label, pp.path "
                "FROM provision_paragraphs pp "
                "JOIN provision_versions pv ON pv.id = pp.provision_version_id "
                "JOIN document_revisions dr ON dr.id = pv.revision_id "
                "ORDER BY dr.ordinal, pp.seq"
            ).fetchall()
            assert conn.execute("PRAGMA user_version").fetchone()[0] == 3
        assert got[0] == ("23-0", 0, 0, None, None)  # flat: one unlabelled row
        assert got[1:4] == [
            ("23-1", 0, 0, None, None),
            ("23-1", 1, 1, "(a)", "(a)"),
            ("23-1", 2, 2, "(1)", "(a)(1)"),
        ]
        report = json.loads((tmp_path / "cert_basis_report.json").read_text())
        assert report["structured_versions"] == 1
        assert report["flat_versions"] == 1
        assert report["label_gaps"] == 1
        assert report["tables"]["provision_paragraphs"] == 1 + 14

    def test_alias_and_text_missing_have_rows(self, tmp_path: Path) -> None:
        p = _provision(
            "1",
            [
                {"designator": "23-0", "text": "TEXT MISSING"},
                {"designator": "23-1", "same_as_designator": "23-0"},
            ],
        )
        db = _build(tmp_path, [p], None)
        with sqlite3.connect(db) as conn:
            n = conn.execute("SELECT count(*) FROM provision_paragraphs").fetchone()[0]
        assert n == 2
        report = json.loads((tmp_path / "cert_basis_report.json").read_text())
        assert report["flat_versions"] == 1  # the alias counts as its target

    def test_bad_layout_fails_the_build_naming_the_version(
        self, tmp_path: Path
    ) -> None:
        bad = _provision("1", [{"designator": "23-0", "text": "(a) A.\n(1) B."}])
        msg = _fails(tmp_path, [bad], None)
        assert "FAA/23/1 version '23-0'" in msg and "line 2" in msg

    def test_check_reports_layout_errors(self, tmp_path: Path) -> None:
        bad = _provision("1", [{"designator": "23-0", "text": "(a) A.\n  (2) B."}])
        errors = check_text_format(_write(tmp_path, [bad], None))
        assert len(errors) == 1 and "continues no open level" in errors[0]

    def test_paragraph_ref_verified(self, tmp_path: Path) -> None:
        _build(tmp_path, [_STRUCTURED], [_ref("(a)(1)(ii)(b)")])
        report = json.loads((tmp_path / "cert_basis_report.json").read_text())
        assert report["paragraph_refs_verified"] == 1
        assert report["paragraph_refs_unverifiable"] == 0

    def test_paragraph_ref_on_flat_version_is_unverifiable(
        self, tmp_path: Path
    ) -> None:
        _build(tmp_path, [_STRUCTURED], [_ref("(z)", to="23-0")])
        report = json.loads((tmp_path / "cert_basis_report.json").read_text())
        assert report["paragraph_refs_unverifiable"] == 1

    def test_paragraph_ref_missing_from_structured_version_fails(
        self, tmp_path: Path
    ) -> None:
        msg = _fails(tmp_path, [_STRUCTURED], [_ref("(a)(3)")])
        assert "'(a)(3)': (3) not in 1309 at 23-1" in msg

    def test_paragraph_ref_that_is_not_a_qualifier_fails(self, tmp_path: Path) -> None:
        msg = _fails(tmp_path, [_STRUCTURED], [_ref("(a) and (b)")])
        assert "not a run of (x) labels" in msg
