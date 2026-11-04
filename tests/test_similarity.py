"""Tests for the provision similarity step of build.py (docs/SQLITE.md §Similarity)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from build import (
    SIMILARITY_MIN_DOC_SIZE,
    SIMILARITY_TOP_PER_DOCUMENT,
    SimilaritySource,
    build,
    compute_similarity,
    similarity_terms,
    stem,
)

# ---------------------------------------------------------------------------
# terms


@pytest.mark.parametrize(
    "words",
    [
        ("install", "installed", "installing", "installation", "installations"),
        ("system", "systems"),
        ("battery", "batteries"),
        ("require", "required", "requirement", "requirements"),
        ("device", "devices"),
    ],
)
def test_stem_collapses_word_forms(words: tuple[str, ...]) -> None:
    assert len({stem(w) for w in words}) == 1


def test_stem_keeps_short_words_and_double_s() -> None:
    assert stem("gas") == "gas"
    assert stem("pass") == "pass"
    assert stem("class") == "class"


def test_terms_drop_labels_numbers_and_stopwords() -> None:
    text = "(a) The fuel tank must (iii) withstand 3.5 g, under §23.963."
    assert similarity_terms(text) == ["fuel", "tank", "withstand"]


# ---------------------------------------------------------------------------
# compute_similarity on hand-made sources


def _src(pid: int, doc: int, text: str, title: str = "Title") -> SimilaritySource:
    return SimilaritySource(
        provision_id=pid,
        document_id=doc,
        order=(f"DOC{doc}", f"{pid:05d}"),
        titles=(title,),
        grouping=None,
        text=text,
    )


# Filler provisions so that no topic word is in half of all provisions.
_FILLER = [
    _src(100 + i, 9, f"{w} {w} {w}", title=w)
    for i, w in enumerate(
        "galley lavatory seat belt harness cargo door window mirror placard".split()
    )
]


def _rows(sources: list[SimilaritySource]) -> dict[int, list[tuple[int, int, int]]]:
    out: dict[int, list[tuple[int, int, int]]] = {}
    for pid, other, rank, score in compute_similarity(sources):
        out.setdefault(pid, []).append((other, rank, score))
    return out


def test_equivalents_across_documents_match() -> None:
    sources = [
        _src(1, 1, "fuel tank vent outlet drain", "Fuel tanks: general"),
        _src(2, 2, "fuel tank vent outlet sump", "Fuel tanks: general"),
        _src(3, 2, "landing gear retraction warning", "Retracting mechanism"),
        *_FILLER,
    ]
    rows = _rows(sources)
    assert (2, 1) == rows[1][0][:2]
    assert all(other != 3 for other, _, _ in rows[1])


def test_scores_are_integer_per_mille_and_identical_text_scores_1000() -> None:
    sources = [
        _src(1, 1, "fuel tank vent", "Fuel tanks"),
        _src(2, 2, "fuel tank vent", "Fuel tanks"),
        *_FILLER,
    ]
    assert _rows(sources)[1] == [(2, 1, 1000)]


def test_top_n_per_document_and_ranked_by_score() -> None:
    target = _src(1, 1, "fuel tank vent outlet drain sump", "Fuel tanks")
    others = [
        _src(10 + i, 2, " ".join("fuel tank vent outlet drain sump".split()[: 6 - i]))
        for i in range(5)
    ]
    rows = _rows([target, *others, *_FILLER])[1]
    in_doc2 = [r for r in rows if r[0] >= 10]
    assert [r[1] for r in in_doc2] == list(range(1, SIMILARITY_TOP_PER_DOCUMENT + 1))
    assert [r[0] for r in in_doc2] == [10, 11, 12]
    scores = [r[2] for r in in_doc2]
    assert scores == sorted(scores, reverse=True)


def test_ties_break_on_document_order_not_input_order() -> None:
    target = _src(1, 1, "fuel tank vent", "Fuel tanks")
    a = _src(20, 2, "fuel tank vent", "Fuel tanks")
    b = _src(30, 2, "fuel tank vent", "Fuel tanks")
    forward = compute_similarity([target, a, b, *_FILLER])
    backward = compute_similarity([b, a, target, *reversed(_FILLER)])
    assert sorted(forward) == sorted(backward)
    assert [r for r in forward if r[0] == 1][:2] == [(1, 20, 1, 1000), (1, 30, 2, 1000)]


def test_unrelated_pairs_fall_below_the_floor() -> None:
    sources = [
        _src(1, 1, "fuel tank vent outlet", "Fuel tanks"),
        _src(2, 2, "landing gear retraction warning horn", "Retracting mechanism"),
        *_FILLER,
    ]
    assert 1 not in _rows(sources)


def test_empty_vectors_get_no_rows() -> None:
    sources = [_src(1, 1, "", "The"), _src(2, 2, "fuel tank", "Fuel"), *_FILLER]
    assert all(
        1 not in (pid, other) for pid, other, _, _ in compute_similarity(sources)
    )


def test_per_document_boilerplate_is_ignored() -> None:
    # Every provision of document 1 says "airplane"; it must not make them all
    # look alike, nor pull document 1 toward a document 2 provision about
    # airplanes.
    doc1 = [
        _src(i, 1, f"airplane airplane airplane {w} {w}", title=w)
        for i, w in enumerate(
            "galley lavatory seat belt harness cargo door window mirror placard"
            " antenna".split(),
            start=1,
        )
    ]
    assert len(doc1) >= SIMILARITY_MIN_DOC_SIZE
    other = _src(50, 2, "airplane airplane airplane", "Airplane")
    ids = {s.provision_id for s in doc1}
    rows = compute_similarity([*doc1, other, *_FILLER])
    assert not [r for r in rows if r[0] in ids and r[1] in ids | {50}]


# ---------------------------------------------------------------------------
# build integration


def _version(designator: str, text: str | None, title: str) -> dict:
    v: dict[str, object] = {"designator": designator, "title_at_revision": title}
    if text is None:
        v["deleted"] = True
    else:
        v["text"] = text
    return v


def _stage(tmp_path: Path, provisions: dict[str, list[dict]]) -> Path:
    data = tmp_path / "data"
    doc_dir = data / "documents" / "easa" / "cs-23"
    doc_dir.mkdir(parents=True)
    (doc_dir / "_document.json").write_text(
        json.dumps(
            {
                "issuer": "EASA",
                "doc_kind": "certification_spec",
                "code": "CS-23",
                "slug": "cs-23",
                "title": None,
                "revisions": [
                    {
                        "designator": "CS23-0",
                        "ordinal": 0,
                        "effective_date": "2003-01-01",
                    },
                    {
                        "designator": "CS23-1",
                        "ordinal": 1,
                        "effective_date": "2004-01-01",
                    },
                ],
            }
        )
    )
    for number, versions in provisions.items():
        (doc_dir / f"{number}.json").write_text(
            json.dumps(
                {
                    "issuer": "EASA",
                    "document": "cs-23",
                    "number": number,
                    "current_grouping": None,
                    "canonical_title": versions[-1]["title_at_revision"],
                    "versions": versions,
                }
            )
        )
    (data / "aircraft").mkdir()
    out = tmp_path / "cert_basis.sqlite"
    build(data, out)
    return out


def _pairs(db: Path) -> set[tuple[str, str]]:
    with sqlite3.connect(db) as conn:
        return set(
            conn.execute(
                "SELECT a.number, b.number FROM provision_similarity s "
                "JOIN provisions a ON a.id = s.provision_id "
                "JOIN provisions b ON b.id = s.similar_provision_id"
            ).fetchall()
        )


def test_build_uses_latest_text_and_skips_deleted_and_missing(
    tmp_path: Path,
) -> None:
    filler = {
        str(900 + i): [_version("CS23-0", f"{w} {w}", w.title())]
        for i, w in enumerate("galley lavatory seat belt harness cargo".split())
    }
    db = _stage(
        tmp_path,
        {
            # Text changed at CS23-1: only the new text counts. (Every title a
            # provision has carried counts, so the old one is kept the same.)
            "1": [
                _version("CS23-0", "landing gear retraction", "Fuel tanks"),
                _version("CS23-1", "fuel tank vent outlet", "Fuel tanks"),
            ],
            "2": [_version("CS23-0", "fuel tank vent outlet", "Fuel tanks")],
            "3": [_version("CS23-0", "landing gear retraction", "Gear")],
            # Deleted at CS23-1: its last text still describes it.
            "4": [
                _version("CS23-0", "landing gear retraction", "Gear"),
                _version("CS23-1", None, "Gear"),
            ],
            "5": [_version("CS23-0", "TEXT MISSING", "Fuel tanks")],
            **filler,
        },
    )
    pairs = _pairs(db)
    assert ("1", "2") in pairs and ("2", "1") in pairs
    assert ("1", "3") not in pairs
    assert ("3", "4") in pairs
    assert not any("5" in p for p in pairs)
    with sqlite3.connect(db) as conn:
        report = json.loads((tmp_path / "cert_basis_report.json").read_text())
        assert (
            report["similarity"]["provisions_with_matches"]
            == conn.execute(
                "SELECT count(DISTINCT provision_id) FROM provision_similarity"
            ).fetchone()[0]
        )


# ---------------------------------------------------------------------------
# golden set on the real checked-in data
#
# Known equivalents must be the best match in their document. Tune the
# SIMILARITY_* constants against this list, and extend it when a document
# (e.g. MIL-HDBK-516) is added.

GOLDEN = [
    # (document, number) -> best match in another document
    (("14 CFR 23", "1309"), ("CS-23", "2510")),
    (("14 CFR 23", "1309"), ("CS-25", "1309")),
    (("14 CFR 23", "1309"), ("CS-27", "1309")),
    (("14 CFR 23", "1301"), ("CS-23", "1301")),
    (("14 CFR 23", "65"), ("CS-23", "65")),
    (("14 CFR 23", "65"), ("CAR 3", "85")),
    (("14 CFR 23", "963"), ("CAR 3", "440")),
    (("CAR 3", "440"), ("CAR 3 (Reissue)", "440")),
]

# Pairs that must never be kept.
CONTROLS = [
    (("14 CFR 23", "1309"), ("CAR 3", "25")),  # "Major changes"
]


@pytest.fixture(scope="module")
def real_conn(real_db: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(real_db)
    yield conn
    conn.close()


def _match(
    conn: sqlite3.Connection, src: tuple[str, str], dst: tuple[str, str]
) -> tuple[int, int] | None:
    return conn.execute(
        """
        SELECT s.rank, s.score FROM provision_similarity s
        JOIN provisions a ON a.id = s.provision_id
        JOIN documents da ON da.id = a.document_id
        JOIN provisions b ON b.id = s.similar_provision_id
        JOIN documents db ON db.id = b.document_id
        WHERE da.code = ? AND a.number = ? AND db.code = ? AND b.number = ?
        """,
        (*src, *dst),
    ).fetchone()


@pytest.mark.parametrize(("src", "dst"), GOLDEN)
def test_golden_pairs_rank_first(
    real_conn: sqlite3.Connection, src: tuple[str, str], dst: tuple[str, str]
) -> None:
    found = _match(real_conn, src, dst)
    assert found is not None, f"{src} -> {dst} not kept"
    assert found[0] == 1, f"{src} -> {dst} ranked {found[0]} (score {found[1]})"


@pytest.mark.parametrize(("src", "dst"), CONTROLS)
def test_control_pairs_not_kept(
    real_conn: sqlite3.Connection, src: tuple[str, str], dst: tuple[str, str]
) -> None:
    assert _match(real_conn, src, dst) is None
