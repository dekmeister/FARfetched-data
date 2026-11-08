"""The cert-basis resolution rules as pure functions (certbuild/resolve.py).

No DB and no staged tree: a hand-built DocIndex stands in for one document.
The end-to-end cases (refs in aircraft JSON, rows in SQLite) stay in
test_resolution.py, test_deletion.py and test_provision_key.py.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from certbuild.resolve import (
    DocIndex,
    Ref,
    Resolved,
    exclude_ordinals,
    resolve_entry,
    resolve_ref,
)

# Part 23, revisions 23-0 .. 23-3 (revision id 100 + ordinal).
#   1301 (provision 1): versions at 23-0 (pv 10) and 23-2 (pv 12)
#   1309 (provision 2): printed 1307 at 23-0 (pv 20), renumbered at 23-1 (pv 21)
#   1305 (provision 3): version at 23-0 (pv 30), deleted at 23-2 (pv 32)
#   1311 (provision 4): printed 1305 from 23-3 (pv 43), the number 1305 freed
DOC = DocIndex.from_rows(
    7,
    "23",
    [(1, "1301"), (2, "1309"), (3, "1305"), (4, "1311")],
    [(100 + n, f"23-{n}", n) for n in range(4)],
    [
        (1, 0, 100, 10, 0, "1301"),
        (1, 2, 102, 12, 0, "1301"),
        (2, 0, 100, 20, 0, "1307"),
        (2, 1, 101, 21, 0, "1309"),
        (3, 0, 100, 30, 0, "1305"),
        (3, 2, 102, 32, 1, "1305"),
        (4, 3, 103, 43, 0, "1305"),
    ],
)


def _json(to: str | None = "23-3", **extra: Any) -> dict[str, Any]:
    ref: dict[str, Any] = {"issuer": "FAA", "document": "23", **extra}
    if to is not None:
        ref["to"] = to
    return ref


def _ref(ref_id: int = 1, exclude_at: int | None = None, **json: Any) -> Ref:
    at = {} if exclude_at is None else {("FAA", "23"): exclude_at}
    r, errors = resolve_ref(_json(**json), DOC, "w", at)
    assert errors == [] and r is not None
    return replace(r, ref_id=ref_id)


def _errors(
    exclude_at: dict[tuple[str, str], int] | None = None, **json: Any
) -> list[str]:
    r, errors = resolve_ref(_json(**json), DOC, "w", exclude_at or {})
    assert r is None
    return errors


def _rows(*refs: Ref) -> tuple[set[tuple[int, int, str | None]], list[str]]:
    rows, errors = resolve_entry(list(refs), "L")
    return {(r.provision_version_id, r.ref_id, r.paragraph) for r in rows}, errors


class TestDocIndex:
    def test_from_rows(self) -> None:
        assert DOC.revisions["23-2"] == (102, 2)
        assert DOC.carriers["1305"] == {3, 4}
        assert DOC.printed[20] == "1307"
        assert DOC.deleted == {32}

    @pytest.mark.parametrize(
        "number,ordinal,expected",
        [
            ("1309", 1, (2, "")),
            ("1307", 0, (2, "")),  # the number printed at that revision
            ("1307", 1, (None, "no provision 23.1307 at that revision")),
            ("1305", 1, (3, "")),
            ("1305", 2, (3, "")),  # deleted there, but nothing else carries it
            ("1305", 3, (4, "")),  # one in force beats one deleted
            ("9999", 3, (None, "unknown provision 23.9999")),
        ],
    )
    def test_provision_at(
        self, number: str, ordinal: int, expected: tuple[int | None, str]
    ) -> None:
        assert DOC.provision_at(number, ordinal) == expected

    def test_pick_honours_to_and_skip(self) -> None:
        assert DOC.pick(1, 3, set()) == 12
        assert DOC.pick(1, 1, set()) == 10
        assert DOC.pick(1, 3, {102}) == 10
        assert DOC.pick(4, 2, set()) is None


class TestResolveRef:
    def test_resolves_ids(self) -> None:
        r = _ref(to="23-2", provisions=["1301"], skip=["23-1"], paragraph="(a)")
        assert (r.to_revision_id, r.to_ordinal, r.skip) == (102, 2, (101,))
        assert (r.provisions, r.paragraph, r.effect) == ((1,), "(a)", "include")

    def test_unknown_document(self) -> None:
        r, errors = resolve_ref(_json(), None, "w", {})
        assert r is None and errors == ["w: unknown document FAA/23"]

    def test_collects_every_fault(self) -> None:
        assert _errors(to="23-9", skip=["23-8"], provisions=["1309"]) == [
            "w: unknown revision '23-9' in 23",
            "w: unknown skip revision '23-8' in 23",
        ]

    def test_skip_must_be_earlier_than_to(self) -> None:
        assert _errors(to="23-1", skip=["23-1"]) == [
            "w: skip '23-1' is not earlier than to '23-1'"
        ]

    def test_numbers_are_read_at_to(self) -> None:
        assert _ref(to="23-0", provisions=["1307"]).provisions == (2,)
        assert _errors(to="23-3", provisions=["1307"]) == [
            "w: no provision 23.1307 at that revision"
        ]

    def test_exclude_reads_numbers_at_the_include_to(self) -> None:
        r = _ref(to=None, effect="exclude", provisions=["1305"], exclude_at=3)
        assert r.provisions == (4,)

    def test_exclude_needs_an_include_in_the_document(self) -> None:
        assert _errors(to=None, effect="exclude", provisions=["1301"]) == [
            "w: exclude of 23.1301 has no include ref in 23 to read its number at"
        ]


def test_exclude_ordinals_takes_the_highest_include_to() -> None:
    refs = [
        _json("23-1"),
        _json("23-2"),
        _json("23-3", effect="exclude"),
        _json(None, effect="exclude"),
        {"issuer": "FAA", "document": "25", "to": "25-1"},
    ]
    docs = {("FAA", "23"): DOC}
    assert exclude_ordinals(refs, docs.get) == {("FAA", "23"): 2}


class TestResolveEntry:
    def test_rule1_wide_takes_latest_and_drops_deleted(self) -> None:
        assert _rows(_ref(to="23-2")) == ({(12, 1, None), (21, 1, None)}, [])

    def test_rule1_skip(self) -> None:
        rows, _ = _rows(_ref(to="23-3", skip=["23-2"]))
        assert rows == {(10, 1, None), (21, 1, None), (30, 1, None), (43, 1, None)}

    def test_rule1_scoped_ref_to_deleted_provision_fails(self) -> None:
        assert _rows(_ref(to="23-2", provisions=["1305"]))[1] == [
            "L: ref 1 resolves 1305 to a revision that deleted it"
        ]

    def test_rule1_nothing_selected_fails(self) -> None:
        rows, errors = _rows(replace(_ref(to="23-0"), provisions=(4,)))
        assert (rows, errors) == (set(), ["L: ref 1 resolves to no provisions"])

    def test_two_wide_refs_disagree(self) -> None:
        _, errors = _rows(_ref(1, to="23-1"), _ref(2, to="23-2"))
        assert errors == [
            "L: two document-wide refs resolve 1301 to different versions"
        ]

    def test_rule2_scoped_overrides_wide(self) -> None:
        rows, errors = _rows(
            _ref(1, to="23-3"), _ref(2, to="23-0", provisions=["1301"])
        )
        assert errors == []
        assert (10, 2, None) in rows and (12, 1, None) not in rows

    def test_rule3_paragraph_on_the_whole_version_adds_nothing(self) -> None:
        rows, _ = _rows(
            _ref(1, to="23-3"), _ref(2, to="23-3", provisions=["1301"], paragraph="(a)")
        )
        assert (12, 1, None) in rows and not any(p for _, _, p in rows)

    def test_rule3_paragraph_on_another_version_adds_a_row(self) -> None:
        rows, _ = _rows(
            _ref(1, to="23-3"), _ref(2, to="23-0", provisions=["1301"], paragraph="(a)")
        )
        assert {(12, 1, None), (10, 2, "(a)")} <= rows

    def test_rule3_two_paragraph_refs_on_one_version_fail(self) -> None:
        _, errors = _rows(
            _ref(1, to="23-0", provisions=["1301"], paragraph="(a)"),
            _ref(2, to="23-1", provisions=["1301"], paragraph="(b)"),
        )
        assert errors == [
            "L: two paragraph refs resolve to the same version of provision id 1"
        ]

    def test_rule4_exclude_removes_from_wide(self) -> None:
        rows, errors = _rows(
            _ref(1, to="23-3"),
            _ref(2, to=None, effect="exclude", provisions=["1301"], exclude_at=3),
        )
        assert errors == [] and {pv for pv, _, _ in rows} == {21, 43}

    def test_rule4_exclude_of_something_not_included_fails(self) -> None:
        _, errors = _rows(
            _ref(1, to="23-3", provisions=["1309"]),
            _ref(2, to=None, effect="exclude", provisions=["1301"], exclude_at=3),
        )
        assert errors == ["L: exclude of 1301 removes nothing"]

    def test_rule4_excluded_and_included_fails(self) -> None:
        _, errors = _rows(
            _ref(1, to="23-3", provisions=["1301"]),
            _ref(2, to=None, effect="exclude", provisions=["1301"], exclude_at=3),
        )
        assert errors == ["L: 1301 is both excluded and included"]

    def test_resolved_row_type(self) -> None:
        rows, _ = resolve_entry([_ref(5, to="23-1", provisions=["1309"])], "L")
        assert rows == [Resolved(21, 5, None)]
