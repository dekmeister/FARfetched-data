"""context.py, delta.py field rows and fields.py verifiers. Not in the repo's
testpaths; run:

    PYTHONPATH=.:.claude/skills/audit-data/scripts uv run pytest \
        .claude/skills/promote-staged/scripts/
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import context  # noqa: E402
import delta  # noqa: E402
import fields  # noqa: E402

COVER = (
    "TCDS A.006        Tecnam P2002        Page 1 of 2\n"
    "              Type Certificate Holder\n"
    "        Costruzioni Aeronautiche TECNAM\n"
    "                    S.p.A.\n"
    "             Via S. D'Acquisto, 62\n"
    "\fTCDS A.006        Tecnam P2002        Page 2 of 2\n"
    "Issue 13, 24 November 2022\n"
    "2. Airworthiness Requirements     CS-VLA, Amendment 1\n"
    "                                  dated 5 March 2003\n"
)


def test_find_spans_wrapped_lines_and_counts_pages() -> None:
    m = context.find(COVER, "CS-VLA, Amendment 1 dated 5 March 2003")
    assert m is not None and (m.first_line, m.last_line) == (7, 8)
    assert context.page_of(COVER, m.first_line) == 2
    assert context.page_of(COVER, 2) == 1


def test_locate_falls_back_to_a_prefix() -> None:
    m = context.locate(COVER, "Via S. D'Acquisto, 62 something the source never says")
    assert m is not None and m.first_line == 4


def _write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "t.txt"
    p.write_text(text, encoding="utf-8")
    context.load_text.cache_clear()
    return p


def test_verbatim_flags_a_wrapped_holder(tmp_path: Path) -> None:
    ctx = fields.Ctx({}, source=_write(tmp_path, COVER))
    check = fields.FIELDS["tcds.holder"]
    res = fields.verbatim("Costruzioni Aeronautiche TECNAM", ctx, check)
    assert res.status == "flag" and "S.p.A." in res.note
    full = "Costruzioni Aeronautiche TECNAM S.p.A."
    assert fields.verbatim(full, ctx, check).status == "ok"


def test_verbatim_flags_a_value_cut_short(tmp_path: Path) -> None:
    ctx = fields.Ctx(
        {}, source=_write(tmp_path, "Holder\n  Acme Aircraft Ltd trading as Foo\n")
    )
    res = fields.verbatim("Acme Aircraft", ctx, fields.FIELDS["tcds.holder"])
    assert res.status == "flag" and "goes on" in res.note


def test_verbatim_empty_and_missing(tmp_path: Path) -> None:
    ctx = fields.Ctx({}, source=_write(tmp_path, COVER))
    check = fields.FIELDS["tcds.holder"]
    assert fields.verbatim("", ctx, check).note == "empty"
    assert fields.verbatim("Nobody GmbH", ctx, check).status == "flag"
    assert fields.verbatim("X", fields.Ctx({}), check).status == "unverifiable"


def test_date_formats(tmp_path: Path) -> None:
    ctx = fields.Ctx({}, source=_write(tmp_path, COVER))
    check = fields.FIELDS["tcds.revision_date"]
    assert fields.date("2022-11-24", ctx, check).status == "ok"
    assert fields.date("2022-11-25", ctx, check).status == "flag"


def test_derived_manufacturer_group() -> None:
    groups = {"Gulfstream Aerospace LP (GALP)": "Gulfstream"}
    rec = {"manufacturer": "Gulfstream Aerospace LP (GALP)"}
    extra = {"field": "manufacturer_group", "groups": groups}
    check = fields.FIELDS["manufacturer_group"]
    assert (
        fields.derived("Gulfstream", fields.Ctx(rec, extra=extra), check).status == "ok"
    )
    bad = fields.derived("GALP", fields.Ctx(rec, extra=extra), check)
    assert bad.status == "flag"
    solo = {"manufacturer": "Acme"}
    assert fields.derived("Acme", fields.Ctx(solo, extra=extra), check).status == "ok"


def _aircraft() -> dict:
    return {
        "manufacturer": "Acme",
        "tcb": [
            {
                "tcds": {"issuer": "FAA", "tcds_number": "A1", "revision": "3"},
                "certification_basis": [{"raw_reference": "Part 23", "references": []}],
            }
        ],
    }


def test_delta_holder_only_is_fields_only() -> None:
    old = _aircraft()
    new = copy.deepcopy(old)
    new["manufacturer_group"] = "Acme"
    new["tcb"][0]["tcds"]["holder"] = "Acme Inc."
    row = delta.aircraft_delta(old, new)
    assert "tcds-revision" not in row["class"]
    assert {"fields-only", "metadata"} <= set(row["class"])
    assert row["residual"] is False
    assert {f["field"] for f in row["fields"]} == {"manufacturer_group", "tcds.holder"}


def test_delta_revision_and_basis_change_are_residual() -> None:
    old = _aircraft()
    new = copy.deepcopy(old)
    new["tcb"][0]["tcds"]["revision"] = "4"
    new["tcb"][0]["certification_basis"][0]["raw_reference"] = "Part 23 amdt 1"
    row = delta.aircraft_delta(old, new)
    assert {"tcds-revision", "basis-lines"} <= set(row["class"])
    assert row["residual"] is True and "fields-only" not in row["class"]


def test_delta_document_title_only() -> None:
    v = {"designator": "23-1", "text": "x", "title_at_revision": "A\\nB"}
    old = {"versions": [v]}
    new = {"versions": [{**v, "title_at_revision": "A B"}]}
    row = delta.document_delta(old, new)
    assert row["residual"] is False and "fields-only" in row["class"]
    assert row["fields"][0]["where"] == "version 23-1"


def test_delta_index_revision_date() -> None:
    old = {"revisions": [{"designator": "25-125", "effective_date": "2008-09-19"}]}
    new = {"revisions": [{"designator": "25-125", "effective_date": "2008-12-26"}]}
    row = delta.index_delta(old, new)
    assert row["fields"] == [
        {
            "where": "revision 25-125",
            "field": "effective_date",
            "old": "2008-09-19",
            "new": "2008-12-26",
        }
    ]


# --- deviations ---------------------------------------------------------------

import listing  # noqa: E402

DRS_ENTRY = listing.Entry(
    "SCPROPOSED",
    Path("input/cache/drs/deviations/SCPROPOSED/p0000.json"),
    {
        "Notice Number": "25-02-08-SC",
        "Subject": "Special Conditions: Boeing Model 777-200; Overhead Crew Rest \n"
        "Compartments",
        "Issue Date": "10/14/2002",
        "Docket Number": "NM237",
        "Make": "Boeing",
        "Applicant": "Boeing",
        "Model": "",
        "CFR Section Reference": "Sec. 25.1309",
    },
)
FAA_REC = {
    "issuer": "FAA",
    "key": "K1",
    "kind": "special_condition",
    "number": "25-02-08-SC",
    "title": "Special Conditions: Boeing Model 777-200; Overhead Crew Rest Compartments",
    "stage": "proposed",
    "published_on": "2002-10-14",
    "source_url": "https://drs.faa.gov/browse/excelExternalWindow/K1",
    "applicant": "Boeing",
    "make": "Boeing",
    "regulation_ref": "Sec. 25.1309",
    "citations": [{"issuer": "FAA", "document": "25", "number": "1309"}],
}


def test_deviation_delta_new_lists_absent_fields_and_changed_is_fields_only() -> None:
    row = delta.deviation_delta(None, FAA_REC)
    names = {f["field"] for f in row["fields"]}
    assert row["class"] == ["new-file"]
    assert {"deviation.title", "deviation.model", "deviation.disposition"} <= names
    assert "deviation.key" not in names
    changed = {**FAA_REC, "title": "Other", "citations": []}
    row = delta.deviation_delta(FAA_REC, changed)
    assert "fields-only" in row["class"] and not row["residual"]
    assert {f["field"] for f in row["fields"]} == {
        "deviation.title",
        "deviation.citations",
    }


def test_listed_faa_matches_labels_dates_and_absences() -> None:
    def check(name: str, value: object) -> str:
        return listing.listed_faa(name, value, DRS_ENTRY)[0]

    assert check("title", FAA_REC["title"]) == "ok"  # wrap collapsed
    assert check("title", "Special Conditions: Boeing Model 777-200") == "flag"
    assert check("published_on", "2002-10-14") == "ok"
    assert check("published_on", "2002-10-15") == "flag"
    assert check("model", None) == "ok"  # listing prints nothing
    assert check("applicant", None) == "flag"  # dropped value
    assert check("disposition", "Granted") == "flag"  # listing has none


def test_derived_deviation_rules(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    final = {**FAA_REC, "key": "K2", "stage": "final"}
    (tmp_path / "deviations/faa").mkdir(parents=True)
    (tmp_path / "deviations/faa/K2.json").write_text(
        __import__("json").dumps(final), encoding="utf-8"
    )
    entries = {"K1": DRS_ENTRY, "K2": DRS_ENTRY}
    monkeypatch.setattr(listing, "drs_index", lambda: entries)
    roots = [tmp_path]
    assert listing.derived("stage", FAA_REC, "proposed", roots)[0] == "ok"
    assert listing.derived("stage", FAA_REC, "final", roots)[0] == "flag"
    assert listing.derived("kind", FAA_REC, "special_condition", roots)[0] == "ok"
    assert (
        listing.derived("source_url", FAA_REC, FAA_REC["source_url"], roots)[0] == "ok"
    )
    assert listing.derived("final", FAA_REC, "K2", roots)[0] == "ok"
    assert listing.derived("final", FAA_REC, "K9", roots)[0] == "flag"
    cites = FAA_REC["citations"]
    assert listing.derived("citations", FAA_REC, cites, roots)[0] == "ok"
    wrong = [{"issuer": "FAA", "document": "25", "number": "1305"}]
    assert listing.derived("citations", FAA_REC, wrong, roots)[0] == "flag"
    padded = {**FAA_REC, "number": "SC-E23.0901-01", "regulation_ref": None}
    c901 = [{"issuer": "EASA", "document": "cs-23", "number": "901"}]
    assert listing.derived("citations", padded, c901, roots)[0] == "ok"


def test_listed_easa_title_is_a_whole_line() -> None:
    page = "Special Condition X - CS-E | EASA\nSpecial Condition X\n19 Aug 2019\n"
    assert listing.listed_easa("title", "Special Condition X", page)[0] == "ok"
    assert listing.listed_easa("title", "Special Condition", page)[0] == "flag"
    assert listing.listed_easa("published_on", "2019-08-19", page)[0] == "ok"
    assert listing.easa_stage("proposed", "with final publication")[0] == "flag"
    assert listing.easa_stage("proposed", "Proposed X")[0] == "ok"


def test_listed_easa_null_number_needs_an_empty_reference() -> None:
    page = "Reference\nM-TS-0000358\nPast reference\nN/a\n"
    assert listing.listed_easa("number", None, page)[0] == "flag"
    assert listing.listed_easa("number", "M-TS-0000358", page)[0] == "ok"
    placeholder = "Reference\nSC D-xx\nPast reference\nSC D-xx\n"
    assert listing.listed_easa("number", None, placeholder)[0] == "ok"
    assert listing.listed_easa("number", None, "Reference\nPast reference\n")[0] == "ok"
    both = "Reference\nMOC-EHPS.240, MOC-EHPS.250\nPast reference\n"
    assert listing.listed_easa("number", "MOC-EHPS.240", both)[0] == "flag"
