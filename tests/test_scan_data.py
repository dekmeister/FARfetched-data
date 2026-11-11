"""scripts/scan_data.py: each check catches the damage it was written for
(examples from the issues it names) and leaves clean text alone; the
baseline reports only new hits."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from scripts import scan_data
from scripts.scan_checks import CHECKS, Check, Context, Field, kind
from factories import aircraft, entry, provision, stage, version

BY_NAME = {c.name: c for c in CHECKS}
VOCAB = Counter({"might": 50, "the": 500, "airplane": 40, "exceptional": 9, "air": 30})
CTX = Context(vocabulary=VOCAB)

# (check, field kind, issuer, value that must hit, value that must not)
CASES = [
    ("encoding", "text", "CAA", "the manufacturer\x92s control", "the pilot’s control"),
    ("encoding", "text", "EASA", "Change \x1a dated", "Change 1 dated"),
    ("private-use", "text", "NATO", "0.75 \uf0b1 0.50", "0.75 ± 0.50"),
    (
        "formula-glyphs",
        "text",
        "EASA",
        "coefficient ⎛ n W ⎞ ⎜⎜ ⎟⎟",
        "coefficient (nW/qS)",
    ),
    ("formula-glyphs", "text", "DOD", "equation: 𝑋𝑋 = 30", "Line\n  $$ X = 30 − A $$"),
    (
        "scrambled-equation",
        "text",
        "EASA",
        "frequency πV ω = 2V A not",
        "where n = 2.5",
    ),
    (
        "dropped-symbol",
        "text",
        "FAA",
        "must not be less than ; and",
        "less than V_{1}; and",
    ),
    (
        "dropped-symbol",
        "text",
        "FAA",
        "A power-off glide at 1.4 ;",
        "a glide at 1.4 V_{S1};",
    ),
    (
        "dropped-symbol",
        "text",
        "FAA",
        "computed as follows--] where-- K = 0.88",
        "computed as follows: $$ K = 0.88 $$",
    ),
    (
        "dropped-symbol",
        "text",
        "FAA",
        "(f.p.s.); = Density of air",
        "; ρ = Density of air",
    ),
    ("stray-symbols", "text", "CAA", "My =| SO ¥e min", "|Δs(i,k)| = 5"),
    ("stray-braces", "text", "CAB", "(b) Load o {e) The", "Line\n  {| T |- | a | b |}"),
    ("stray-braces", "text", "FAA", "speed V {d} here", "speed V_{d} and 10^{-7}"),
    (
        "literal-escape",
        "text",
        "FAA",
        "for showing \\ncompliance",
        "for showing compliance",
    ),
    ("literal-escape", "text", "FAA", "greater than \\1/2\\ psi", "greater than ½ psi"),
    (
        "toc-run",
        "text",
        "CAA",
        "end. 3.302 Special factors. 3.303 Variability factor. 3.304 Castings. "
        "3.305 Bearing factors. 3.306 Fitting factor.",
        "See § 3.302 Special factors and § 3.303 and 3.304 Castings.",
    ),
    (
        "dot-leaders",
        "text",
        "CAA",
        "Gasoline....... 6 pounds",
        "in the ______ category",
    ),
    (
        "figure-caption",
        "text",
        "CAB",
        "conditions. FIG. 3-2—LIMIT MANEUVERING LOAD FACTORS",
        "the factors (see Fig. 3-2) apply",
    ),
    (
        "figure-caption",
        "text",
        "CAB",
        "E(u,a) FIG. 3-1-—(V-n) DIAGRAM (FLIGHT ENVELOPE) tions",
        "the V-n diagram of Fig. 3-1.",
    ),
    (
        "caps-run",
        "text",
        "CAA",
        "values. LIMIT AVERAGE MANEUVERING CONTROL SURFACE LOADINGS apply",
        "References: MIL-STD-882 SAE ARP4754 SAE ARP4761 RTCA DO-178",
    ),
    (
        "trailing-heading",
        "text",
        "CAB",
        "are installed. CONTROL SURFACES (FIXED AND MOVABLE)",
        "are installed in CONTROL SURFACES.",
    ),
    (
        "trailing-heading",
        "text",
        "EASA",
        "from any direction. Emergency Landing Conditions",
        "from any direction.",
    ),
    (
        "amendment-text",
        "text",
        "CAB",
        "engines. 12. By amending § 3.551(b) to read as follows:",
        "engines amending the limits as follows:",
    ),
    (
        "lowercase-start",
        "text",
        "NATO",
        "structure See AMC.865 The flight controls",
        "(a) the flight controls",
    ),
    (
        "truncated-end",
        "text",
        "CAA",
        "shall comply with §",
        "shall comply with § 3.422.",
    ),
    ("split-word", "text", "EASA", "the pilot m ight not", "the pilot might not"),
    (
        "split-word",
        "text",
        "CAB",
        "without ex~ ceptional skill",
        "without exceptional skill",
    ),
    ("ocr-label", "text", "CAB", "(a) One\n{b) Two", "(a) One\n(b) Two\n  (iv) Four"),
    ("ocr-label", "text", "CAB", "(a) One\n(bo) Two", "(aa) One\n(bb) Two"),
    (
        "vspeed-ocr",
        "text",
        "CAA",
        "a speed between Vx and 1.4 Vs], then",
        "1.4 V_{s1}, then",
    ),
    (
        "unbalanced-brackets",
        "text",
        "CAB",
        "The minimum weight shal] not",
        "[Amdt. 3-1]",
    ),
    (
        "gibberish",
        "text",
        "CAA",
        "FACTORS SHA1t BE OrRECTION BY LiMIT VALUES",
        "SCFs and APUs and gMAX and McDonnell",
    ),
    (
        "numeric-run",
        "text",
        "EASA",
        "PEAK AVERAGE 20 20 30 30 100 100 10 10 30 10 10 10 700",
        "Line\n  {| T |- | 20 | 20 | 30 | 30 | 100 | 100 | 10 | 10 | 30 | 10 |}",
    ),
    (
        "basis-footer",
        "basis",
        "EASA",
        "Issue: 70 [A330-743L] Date: 30/10/2026",
        "CS-25 Amendment 3",
    ),
    (
        "basis-heading",
        "basis",
        "EASA",
        "3 Special Conditions: None",
        "SC F-01 Lightning",
    ),
    (
        "basis-list-header",
        "basis",
        "EASA",
        "Plus the following CS 25 paragraphs applicable at Amdt 13",
        "CS 25.301 at Amdt 13",
    ),
]


def _field(kind_: str, issuer: str, value: str) -> Field:
    name = "basis[1]" if kind_ == "basis" else kind_
    document = {"CAA": "car-3", "CAB": "car-3-reissue"}.get(issuer, "x")
    return Field(issuer, document, "301", "R1", name, value)


def _hits(check: Check, kind_: str, issuer: str, value: str) -> list[str]:
    return [h.match for h in check.run(_field(kind_, issuer, value), CTX)]


@pytest.mark.parametrize(("name", "kind_", "issuer", "bad", "good"), CASES)
def test_check_hits_damage_and_spares_clean_text(
    name: str, kind_: str, issuer: str, bad: str, good: str
) -> None:
    check = BY_NAME[name]
    assert kind_ in check.fields
    assert _hits(check, kind_, issuer, bad), f"{name} missed: {bad!r}"
    assert not _hits(check, kind_, issuer, good), f"{name} flagged: {good!r}"


def test_every_check_has_a_case() -> None:
    assert {c[0] for c in CASES} == set(BY_NAME)


def test_faa_change_brackets_are_not_ocr() -> None:
    value = "speeds between [1.13 VSR] and the [VMCG] speed"
    assert not _hits(BY_NAME["vspeed-ocr"], "text", "FAA", value)
    assert not _hits(BY_NAME["unbalanced-brackets"], "text", "FAA", "text]")


def test_appendix_subsections_are_not_a_toc() -> None:
    value = "25.1 Applicability x. 25.2 Definitions x. 25.3 General x. 25.4 Test x. "
    value += "25.5 Other x. 25.6 More x."
    f = Field("EASA", "cs-25", "Q25", "CS25-13", "text", value)
    assert not list(BY_NAME["toc-run"].run(f, CTX))


def test_cited_sections_are_not_a_toc() -> None:
    value = "(2) CS 25.854 Lavatory fire protection (3) CS 25.858 Cargo x (4) CS "
    value += "25.981 Fuel tank x (5) CS 25.1165 Engine x (6) CS 25.1310 Power x"
    f = Field("EASA", "cs-25", "1705", "CS25-5", "text", value)
    assert not list(BY_NAME["toc-run"].run(f, CTX))


def test_list_header_with_its_list_is_fine() -> None:
    value = "the following paragraphs applicable for FADECs: 23.611, 23.777"
    assert not _hits(BY_NAME["basis-list-header"], "basis", "FAA", value)


def test_kind_of_field() -> None:
    assert kind(_field("basis", "EASA", "x")) == "basis"
    assert kind(_field("title", "EASA", "x")) == "title"


def _finding(match: str) -> scan_data.Finding:
    return scan_data.Finding("c", "CAA", "car-3", "1", "R1", "text", match, "ctx")


def test_baseline_reports_only_new_and_extra_hits() -> None:
    known = Counter({_finding("a").identity(): 1})
    found = [_finding("a"), _finding("a"), _finding("b")]
    assert [f.match for f in scan_data.new_findings(found, known)] == ["a", "b"]


def _tree(tmp_path: Path, text: str) -> Path:
    p = provision("CAA", "car-3", "1", [version("CAR3-0", text=text)])
    model = aircraft([entry([], raw_reference="Issue: 70 [X] Date: 30/10/2026")])
    return stage(tmp_path, [], [p], [model])


def test_main_baseline_round_trip(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _tree(tmp_path, "The weight shal] not exceed")
    baseline = tmp_path / "baseline.tsv"
    args = ["--root", str(root), "--baseline", str(baseline)]
    assert scan_data.main([*args, "--write-baseline"]) == 0
    assert scan_data.main(args) == 0
    out = capsys.readouterr().out
    assert out.splitlines() == ["\t".join(scan_data.COLUMNS)]

    _tree(tmp_path, "The weight shal] not exceed (bo) the contro] limit")
    assert scan_data.main(args) == 1
    rows = capsys.readouterr().out.splitlines()[1:]
    assert [r.split("\t")[0] for r in rows] == ["unbalanced-brackets"]
    assert "basis-footer" in baseline.read_text()


def test_text_missing_is_not_scanned(tmp_path: Path) -> None:
    root = _tree(tmp_path, "TEXT MISSING")
    fields = list(scan_data.provision_fields(root))
    found = scan_data.scan(fields, CHECKS)
    assert not [f for f in found if f.field == "text"]


def test_write_baseline_refuses_a_subset(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        scan_data.main(
            ["--root", str(tmp_path), "--write-baseline", "--check", "toc-run"]
        )
