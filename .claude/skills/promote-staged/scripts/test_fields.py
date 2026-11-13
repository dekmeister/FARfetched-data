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
