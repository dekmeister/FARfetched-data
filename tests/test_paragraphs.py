"""Tests for the label-line text format: build.parse_paragraphs, the
provision_paragraphs table, and paragraph-qualified cert-basis refs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import factories as fx

from certbuild.ddl import SCHEMA_VERSION
from certbuild.pipeline import build
from certbuild.provisions import check_text_format
from certbuild.text import (
    TextFormatError,
    flatten_text,
    inline_error,
    label_values,
    paragraph_ref_paths,
    parse_paragraphs,
    parse_table_row,
    plain_text,
    strip_inline,
    table_width,
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
# Rule 7: section headings (appendices assembled from their sections)

APPENDIX_F23 = """\
Sec. F23.1 Part I--Test Procedure
(a) Conditioning.
(b) Specimen configuration:
  (1) Thick foam parts.
Sec. F23.2 Part II--Test Method
Use this test method to evaluate insulation.
(a) Definitions.
(b) Test apparatus.
  (1) Radiant panel test chamber.
    More of (b)(1)."""


class TestSectionHeadings:
    def test_labels_restart_under_each_section(self) -> None:
        got = [
            (p.depth, p.path, p.section, p.heading)
            for p in parse_paragraphs(APPENDIX_F23).paragraphs
        ]
        assert got == [
            (0, None, "F23.1", True),
            (1, "F23.1(a)", "F23.1", False),
            (1, "F23.1(b)", "F23.1", False),
            (2, "F23.1(b)(1)", "F23.1", False),
            (0, None, "F23.2", True),
            (0, None, "F23.2", False),
            (1, "F23.2(a)", "F23.2", False),
            (1, "F23.2(b)", "F23.2", False),
            (2, "F23.2(b)(1)", "F23.2", False),
            (2, "F23.2(b)(1)", "F23.2", False),
        ]

    def test_text_before_the_first_heading_has_no_section(self) -> None:
        got = parse_paragraphs("Intro.\nSec. A23.1 General.\n(a) A.").paragraphs
        assert [(p.section, p.path) for p in got] == [
            (None, None),
            ("A23.1", None),
            ("A23.1", "A23.1(a)"),
        ]

    def test_roman_headings_are_sections(self) -> None:
        text = "I. General.\nIntro.\nII. Defs\n(a) A.\nIII. Trim.\n(a) B.\n  (1) C."
        got = parse_paragraphs(text).paragraphs
        assert [(p.section, p.path) for p in got if p.path] == [
            ("II", "II(a)"),
            ("III", "III(a)"),
            ("III", "III(a)(1)"),
        ]
        assert [p.section for p in got if p.heading] == ["I", "II", "III"]

    def test_roman_heading_out_of_order_is_text(self) -> None:
        got = parse_paragraphs("(a) A.\nIII. Foo.").paragraphs
        assert [p.section for p in got] == [None, None]

    def test_indented_roman_heading_fails(self) -> None:
        assert "must not be indented" in error("I. One.\n(a) A.\n  II. Two.")

    def test_indented_heading_fails(self) -> None:
        assert "must not be indented" in error("(a) A.\n  Sec. A23.1 General.")

    def test_repeated_section_fails(self) -> None:
        assert "repeats" in error("Sec. A23.1 One.\n(a) A.\nSec. A23.1 Again.")

    def test_cross_reference_is_not_a_heading(self) -> None:
        # Only an appendix section number (letter first) opens a section.
        got = parse_paragraphs("(a) A.\nSec. 23.853 applies.").paragraphs
        assert [p.section for p in got] == [None, None]

    def test_single_line_stays_flat(self) -> None:
        assert rows("Sec. A23.1 General. (a) A.") == [
            (0, None, None, "Sec. A23.1 General. (a) A.")
        ]

    def test_bare_qualifier_matches_no_sectioned_path(self) -> None:
        paths = {p.path for p in parse_paragraphs(APPENDIX_F23).paragraphs if p.path}
        assert paragraph_ref_paths("(a)", paths) == ["(a)"]


# ---------------------------------------------------------------------------
# Tables


HIRF = """\
(a) HIRF environment I is specified in the following table:
  {| Table I. - HIRF Environment I
  ! Frequency {r2} ! Field strength (volts/meter) {c2}
  ! Peak ! Average
  | 10 kHz-2 MHz | 50 | 50
  | 2 MHz-30 MHz | 100 | 100
  |}
  In this table, the higher field strength applies at the frequency band edges.
(b) HIRF environment II."""


class TestTables:
    def test_block_belongs_to_its_item(self) -> None:
        paras = parse_paragraphs(HIRF).paragraphs
        table = [p for p in paras if p.kind == "table"]
        assert [p.text for p in table][0] == "{| Table I. - HIRF Environment I"
        assert table[-1].text == "|}"
        assert len(table) == 6
        assert {(p.depth, p.label, p.path) for p in table} == {(1, None, "(a)")}
        note = paras[7]
        assert (note.kind, note.path) == ("text", "(a)")
        assert paras[8].label == "(b)"

    def test_cell_labels_are_not_labels(self) -> None:
        text = "(a) Factors:\n  {|\n  | (a) Aileron | 0.75\n  |}\n(b) Next."
        assert [p.label for p in parse_paragraphs(text).paragraphs] == [
            "(a)", None, None, None, "(b)",
        ]  # fmt: skip

    def test_table_in_unlabelled_text(self) -> None:
        text = "Intensities:\n{|\n! Angle ! Intensity\n| 0 | 1.00\n|}"
        paras = parse_paragraphs(text).paragraphs
        assert [(p.depth, p.kind) for p in paras] == [(0, "text")] + [(0, "table")] * 4

    def test_cells_and_spans(self) -> None:
        cells = parse_table_row(
            "! Frequency {r2} ! Field strength {r1 c2}".replace("{r1 c2}", "{c2}")
        )
        assert [(c.header, c.text, c.rowspan, c.colspan) for c in cells] == [
            (True, "Frequency", 2, 1),
            (True, "Field strength", 1, 2),
        ]
        both = parse_table_row("| x {r2 c3} | | y")
        assert [(c.text, c.rowspan, c.colspan) for c in both] == [
            ("x", 2, 3), ("", 1, 1), ("y", 1, 1),
        ]  # fmt: skip
        assert parse_table_row("| |H(w)| value")[0].text == "|H(w)| value"

    def test_width_counts_spans(self) -> None:
        rows = [
            parse_table_row(r) for r in ("! a {r2} ! b {c2}", "! c ! d", "| 1 | 2 | 3")
        ]
        assert table_width(rows) == 3

    def test_flatten_and_plain(self) -> None:
        flat = flatten_text(HIRF)
        assert (
            "table: {| Table I. - HIRF Environment I |- ! Frequency {r2} ! Field "
            "strength (volts/meter) {c2} |- ! Peak ! Average |- | 10 kHz-2 MHz | 50 "
            "| 50 |- | 2 MHz-30 MHz | 100 | 100 |} In this table" in flat
        )
        assert plain_text(flat) == plain_text(HIRF)
        assert (
            "Frequency Field strength (volts/meter) Peak Average 10 kHz-2 MHz 50 50"
            in (plain_text(HIRF))
        )

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            ("(a) x\n  {| c\n  | a | b\n  | c\n  |}", "rows differ in width"),
            ("(a) x\n  {| c\n  |}", "a table with no rows"),
            ("(a) x\n  {| c\n  | a", "never closed"),
            ("(a) x\n  |}\n(b) y", "outside a table block"),
            ("(a) x\n  | a | b\n(b) y", "outside a table block"),
            ("(a) x\n  {|\n  {|\n  | a\n  |}", "a table inside a table"),
            ("(a) x\n  {|\n   | a\n  |}", "indented unlike"),
            ("(a) x\n  {|\n  ! a {r2} ! b\n  |}", "runs past the last row"),
            ("(a) x\n  {|\n  ! a {r1} ! b\n  |}", "a span must be 2 or more"),
            ("(a) x\n  {|\n  ! a {r2 ! b\n  |}", "malformed span"),
            ("(a) x\n  {|\n  ! a {} ! b\n  |}", "empty span"),
            ("(a) x\n  {|\n  | a |- b\n  |}", "markup inside cell"),
            ("(a) x {| y |}\n(b) z", "outside a table block"),
            ("{| a |- | b |}", "single-line text"),
        ],
    )
    def test_fails_loud(self, text: str, message: str) -> None:
        assert message in error(text)


GUST = """\
(a) The airplane is subjected to a sinusoidal input of speed V_{A}:
  $$ ω = πV/(2V_{A}) $$
  where t_{max} is defined in (b).
  (1) For 0 ≤ t ≤ t_{max}:
    $$ δ(t) = δ_{1} sin(ωt) $$
(b) The load factor is 10^{-7} per flight hour."""


class TestInlineMarkup:
    def test_formula_lines_belong_to_their_item(self) -> None:
        paras = parse_paragraphs(GUST).paragraphs
        got = [(p.depth, p.label, p.path, p.kind) for p in paras]
        assert got == [
            (1, "(a)", "(a)", "text"),
            (1, None, "(a)", "formula"),
            (1, None, "(a)", "text"),
            (2, "(1)", "(a)(1)", "text"),
            (2, None, "(a)(1)", "formula"),
            (1, "(b)", "(b)", "text"),
        ]
        assert paras[1].text == "$$ ω = πV/(2V_{A}) $$"

    def test_formula_in_unlabelled_text(self) -> None:
        paras = parse_paragraphs("Where:\n$$ n = 1 + x $$\nand x is small.").paragraphs
        assert [(p.depth, p.kind) for p in paras] == [
            (0, "text"), (0, "formula"), (0, "text"),
        ]  # fmt: skip

    def test_sub_and_sup_in_flat_text_and_cells(self) -> None:
        assert rows("V_{A} and 10^{-7}") == [(0, None, None, "V_{A} and 10^{-7}")]
        text = "(a) x\n  {|\n  | V_{D} | 10^{6}\n  |}"
        assert parse_paragraphs(text).paragraphs[2].kind == "table"

    def test_bare_characters_stay_literal(self) -> None:
        for ok in ("a_b {x} c^d", "x_ {y}", "} _{ok} {", "(a) a\n(b) _ ^ { }"):
            assert inline_error(ok) is None
            parse_paragraphs(ok)

    def test_plain_form(self) -> None:
        assert strip_inline("V_{A} 10^{-7} t_{max}") == "VA 10-7 tmax"
        assert plain_text(GUST).startswith(
            "(a) The airplane is subjected to a sinusoidal input of speed VA: "
            "ω = πV/(2VA) where tmax"
        )
        assert plain_text(flatten_text(GUST)) == plain_text(GUST)

    @pytest.mark.parametrize(
        ("text", "message"),
        [
            ("V_{A is", "malformed `_{…}`"),
            ("V_{} is", "malformed `_{…}`"),
            ("V_{A^{2}}", "malformed `_{…}`"),
            ("10^{a$b}", "malformed `^{…}`"),
            ("(a) x V_{A\n(b) y", "malformed `_{…}`"),
            ("(a) x $$ y $$\n(b) z", "`$$` outside a formula line"),
            ("(a) $$ y $$\n(b) z", "`$$` outside a formula line"),
            ("(a) x\n  $$ y\n(b) z", "`$$` outside a formula line"),
            ("(a) x\n  $$y$$\n(b) z", "`$$` outside a formula line"),
            ("(a) x\n  $$ a $$ b $$\n(b) z", "`$$` outside a formula line"),
            ("(a) x\n  {|\n  | $$ a $$\n  |}", "`$$` outside a formula line"),
            ("$$ x $$", "`$$` in a single-line text"),
        ],
    )
    def test_fails_loud(self, text: str, message: str) -> None:
        assert message in error(text)


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
    return fx.provision(
        "FAA", "23", number, [{"title_at_revision": "Title", **v} for v in versions]
    )


def _aircraft(refs: list[dict]) -> dict:
    return fx.aircraft(
        [fx.entry(refs, raw_reference="14 CFR 23.1309(b)")],
        tcds={"issuer": "FAA", "tcds_number": "A00XX"},
    )


def _write(tmp_path: Path, provisions: list[dict], refs: list[dict] | None) -> Path:
    models = [_aircraft(refs)] if refs is not None else []
    return fx.stage(tmp_path, [_DOC], provisions, models)


def _build(tmp_path: Path, provisions: list[dict], refs: list[dict] | None) -> Path:
    out = tmp_path / "cert_basis.sqlite"
    build(_write(tmp_path, provisions, refs), out)
    return out


def _fails(tmp_path: Path, provisions: list[dict], refs: list[dict] | None) -> str:
    models = [_aircraft(refs)] if refs is not None else []
    return fx.build_fails(tmp_path, [_DOC], provisions, models)


def _ref(paragraph: str, number: str = "1309", to: str = "23-1") -> dict:
    return fx.ref("FAA", "23", to, provisions=[number], paragraph=paragraph)


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
            assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
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

    def test_table_rows_have_kind(self, tmp_path: Path) -> None:
        p = _provision("1309", [{"designator": "23-1", "text": HIRF}])
        db = _build(tmp_path, [p], None)
        with sqlite3.connect(db) as conn:
            kinds = conn.execute(
                "SELECT kind, count(*) FROM provision_paragraphs GROUP BY kind"
            ).fetchall()
        assert dict(kinds) == {"text": 3, "table": 6}

    def test_formula_rows_have_kind(self, tmp_path: Path) -> None:
        p = _provision("1309", [{"designator": "23-1", "text": GUST}])
        db = _build(tmp_path, [p], None)
        with sqlite3.connect(db) as conn:
            got = conn.execute(
                "SELECT text FROM provision_paragraphs WHERE kind = 'formula' "
                "ORDER BY seq"
            ).fetchall()
        assert got == [("$$ ω = πV/(2V_{A}) $$",), ("$$ δ(t) = δ_{1} sin(ωt) $$",)]

    def test_bad_markup_fails_build(self, tmp_path: Path) -> None:
        p = _provision("1309", [{"designator": "23-1", "text": "Speed V_{A."}])
        assert "malformed `_{…}`" in _fails(tmp_path, [p], None)

    def test_bad_table_fails_build(self, tmp_path: Path) -> None:
        bad = HIRF.replace("  |}\n", "")
        p = _provision("1309", [{"designator": "23-1", "text": bad}])
        assert "table row: a table row must start" in _fails(tmp_path, [p], None)

    def test_section_rows(self, tmp_path: Path) -> None:
        p = _provision("1", [{"designator": "23-1", "text": APPENDIX_F23}])
        db = _build(tmp_path, [p], None)
        with sqlite3.connect(db) as conn:
            got = conn.execute(
                "SELECT seq, path, section, heading FROM provision_paragraphs "
                "WHERE heading = 1 OR path = 'F23.2(b)(1)' ORDER BY seq"
            ).fetchall()
        assert got == [
            (0, None, "F23.1", 1),
            (4, None, "F23.2", 1),
            (8, "F23.2(b)(1)", "F23.2", 0),
            (9, "F23.2(b)(1)", "F23.2", 0),
        ]

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
