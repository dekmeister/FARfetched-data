"""items.py and batches.py on the delta.py row shapes. Not in the repo's
testpaths; run:

    PYTHONPATH=.:.claude/skills/audit-data/scripts uv run pytest \
        .claude/skills/promote-staged/scripts/
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import batches  # noqa: E402
import items  # noqa: E402


def _tcb(issuer: str, number: str, raw: str = "14 CFR Part 23") -> dict[str, object]:
    return {
        "tcds": {"issuer": issuer, "tcds_number": number, "revision": "1"},
        "certification_basis": [{"raw_reference": raw}],
    }


@pytest.fixture
def staged(tmp_path: Path) -> Path:
    for rel, tcbs in {
        "aircraft/m/new.json": [_tcb("FAA", "A00071CE")],
        "aircraft/m/old.json": [
            _tcb("FAA", "A1", "Part 23 amdt 2"),
            _tcb("EASA", "E1"),
            _tcb("FAA", "SAME"),
        ],
    }.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(json.dumps({"tcb": tcbs}), encoding="utf-8")
    return tmp_path


def test_new_file_row(staged: Path) -> None:
    row = {
        "relpath": "aircraft/m/new.json",
        "status": "new",
        "changes": [{"tcb": ["FAA A00071CE"]}],
    }
    out, notes = items.aircraft_items(row, staged, set())
    assert [(i["mode"], i["reason"], i["tcds"]["tcds_number"]) for i in out] == [
        ("full", "new-file", "A00071CE")
    ]
    assert notes == []


def test_new_tcb_identical_to_data_is_skipped(staged: Path) -> None:
    row = {
        "relpath": "aircraft/m/new.json",
        "status": "new",
        "changes": [{"tcb": ["FAA A00071CE"]}],
    }
    known = {items._tcb_sig(_tcb("FAA", "A00071CE"))}
    out, notes = items.aircraft_items(row, staged, known)
    assert out == [] and "identical" in notes[0]


def test_changed_file_row(staged: Path) -> None:
    line_change = {
        "tcb": "FAA A1",
        "lines_added": [{"raw_reference": "Part 23 amdt 2"}],
        "lines_removed": [{"raw_reference": "Part 23"}],
    }
    holder_only = {"tcb": "FAA SAME", "tcds": [{}, {"holder": "X"}]}
    row = {
        "relpath": "aircraft/m/old.json",
        "status": "changed",
        "changes": [
            {"top_fields": {"model": ["a", "b"]}},
            line_change,
            holder_only,
            {"tcb_added": "EASA E1"},
            {"tcb_removed": "FAA GONE"},
        ],
    }
    out, _ = items.aircraft_items(row, staged, set())
    got = [(i["mode"], i["reason"], i["tcds"]["tcds_number"]) for i in out]
    assert got == [("full", "tcb-added", "E1"), ("diff", "basis-lines", "A1")]
    diff = out[1]
    assert diff["changed"]["lines_added"][0]["raw_reference"] == "Part 23 amdt 2"
    assert diff["unchanged_lines"] == 0


def test_dedup_merges_shared_tcds() -> None:
    a = {
        "relpath": "aircraft/m/a.json",
        "relpaths": ["aircraft/m/a.json"],
        "group": "m",
        "mode": "diff",
        "x": 1,
    }
    b = {
        **a,
        "relpath": "aircraft/n/b.json",
        "relpaths": ["aircraft/n/b.json"],
        "group": "n",
    }
    merged = items.dedup([a, b])
    assert len(merged) == 1 and merged[0]["relpaths"] == [
        "aircraft/m/a.json",
        "aircraft/n/b.json",
    ]


def test_word_hunks_have_context() -> None:
    h = items.word_hunks("one two three four", "one two 3 four")
    assert h == [{"before": "one two", "data": "three", "staged": "3", "after": "four"}]


def test_hits_match_by_designator(tmp_path: Path) -> None:
    checks = tmp_path / "c.tsv"
    checks.write_text(
        "length-jump\tdocuments/faa/25/F25.json\t25-142\tx\n", encoding="utf-8"
    )
    scan = tmp_path / "s.tsv"
    scan.write_text(
        "check\tissuer\tdocument\tkey\tdesignator\tfield\tmatch\tcontext\n"
        "stray-symbols\tFAA\t26\t1\t26-0\ttext\t`\tctx\n",
        encoding="utf-8",
    )
    hits = batches.load_hits([checks, scan])
    assert set(hits) == {
        ("documents/faa/25/F25.json", "25-142"),
        ("documents/faa/26/1.json", "26-0"),
    }


def _item(mode: str, reason: str, n: int, size: int = 100) -> dict[str, object]:
    rel = f"documents/faa/23/{n}.json"
    return {
        "mode": mode,
        "reason": reason,
        "relpath": rel,
        "relpaths": [rel],
        "group": "faa/23",
        "source_key": rel,
        "pad": "x" * size,
    }


def test_pack_respects_token_target_and_modes() -> None:
    its = [_item("diff", "words", n, 40_000) for n in range(3)] + [
        _item("field", "field-flag", 9)
    ]
    packed = batches.pack(its, 40_000)
    assert [len(b) for b in packed] == [1, 1, 1, 1]
    assert packed[0][0]["mode"] == "field"


def test_downscale_shrinks_samples_first() -> None:
    pools = {
        "must": [_item("diff", "words", 0)],
        "fields": {},
        "optional": {
            "layout-only": [
                _item("diff", "layout-only", n, 8_000) for n in range(1, 9)
            ],
            "markup-only": [],
            "new-file": [],
        },
    }
    args = batches.parse_args(["--delta", "d", "--out-dir", "o", "--budget", "40000"])
    out, settings, steps = batches.plan_batches(args, pools)
    assert steps and steps[0] == "class_sample=4"
    assert any(i["reason"] == "words" for b in out for i in b)
    assert batches.total(out) <= 40_000 or settings["class_sample"] == 0
