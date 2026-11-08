"""Provision similarity (docs/SQLITE.md §Similarity)."""

from __future__ import annotations

import math
import re
import sqlite3
from dataclasses import dataclass

from certbuild.text.flat import plain_text


# ---------------------------------------------------------------------------
# Provision similarity (docs/SQLITE.md §Similarity)
#
# TF-IDF cosine over each provision's title(s), grouping and latest text. The
# unit is the provision, not the version: a relation is between two sections,
# not two amendments. Pure stdlib; the inverted index keeps it to seconds.

# Lowest cosine kept. Unrelated pairs score about 0.1-0.2, equivalents 0.4+.
SIMILARITY_MIN_SCORE = 0.25
# Matches kept per (provision, document of the match), the provision's own
# document included.
SIMILARITY_TOP_PER_DOCUMENT = 3
# Title words count this many times over a text word; grouping words once.
SIMILARITY_TITLE_WEIGHT = 5
SIMILARITY_GROUPING_WEIGHT = 1
# A term in more than this share of all provisions carries no signal. The same
# share within one document is that document's boilerplate ("airplane",
# "rotorcraft", a handbook's fixed block labels) and is dropped for it alone,
# once the document has SIMILARITY_MIN_DOC_SIZE provisions.
SIMILARITY_MAX_DF = 0.5
SIMILARITY_MIN_DOC_SIZE = 10

_SIM_WORD = re.compile(r"[a-z]{3,}")
_SIM_ROMAN = re.compile(r"[ivxlc]+")
_SIM_STOPWORDS = frozenset(
    """
    about above after again all also and any are because been before being
    below between both but can could does doing down during each either for
    from further had has have having here how into its itself may more most
    must not now off once only other otherwise our out over own per same shall
    should such than that the their them then there these they this those
    through under until upon very was were what when where whether which while
    who whom why will with within without would
    """.split()
)
# Longest first: the first suffix that leaves a stem of 4+ letters is removed.
_SIM_SUFFIXES = (
    "ations", "ation", "ments", "ment", "ings", "ing", "ies", "ed", "es", "s",
)  # fmt: skip


def stem(word: str) -> str:
    """Crude suffix stripping so that install, installed, installing and
    installations meet. Not linguistics: only consistency matters."""
    for suffix in _SIM_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            if suffix == "s" and word.endswith("ss"):
                break
            word = word[: -len(suffix)] + ("y" if suffix == "ies" else "")
            break
    if word.endswith("e") and len(word) > 4:
        word = word[:-1]
    return word


def similarity_terms(text: str) -> list[str]:
    """Stemmed content words of `text`: no stopwords, numbers, paragraph
    labels or roman numerals."""
    return [
        stem(w)
        for w in _SIM_WORD.findall(text.lower())
        if w not in _SIM_STOPWORDS and not _SIM_ROMAN.fullmatch(w)
    ]


@dataclass(frozen=True)
class SimilaritySource:
    """What similarity sees of one provision. `order` breaks score ties so the
    output is the same on every build."""

    provision_id: int
    document_id: int
    order: tuple[str, str]  # (document code, sort_key)
    titles: tuple[str, ...]
    grouping: str | None
    text: str


def _similarity_counts(src: SimilaritySource) -> dict[str, float]:
    counts: dict[str, float] = {}
    for term in similarity_terms(src.text):
        counts[term] = counts.get(term, 0.0) + 1.0
    for term in {t for title in src.titles for t in similarity_terms(title)}:
        counts[term] = counts.get(term, 0.0) + SIMILARITY_TITLE_WEIGHT
    for term in set(similarity_terms(src.grouping or "")):
        counts[term] = counts.get(term, 0.0) + SIMILARITY_GROUPING_WEIGHT
    return counts


def _similarity_vectors(
    sources: list[SimilaritySource],
) -> dict[int, dict[str, float]]:
    """L2-normalised TF-IDF vector per provision. Empty vectors are left out."""
    counts = {s.provision_id: _similarity_counts(s) for s in sources}
    n = len(sources)
    df: dict[str, int] = {}
    doc_df: dict[int, dict[str, int]] = {}
    doc_size: dict[int, int] = {}
    for s in sources:
        doc_size[s.document_id] = doc_size.get(s.document_id, 0) + 1
        per_doc = doc_df.setdefault(s.document_id, {})
        for term in counts[s.provision_id]:
            df[term] = df.get(term, 0) + 1
            per_doc[term] = per_doc.get(term, 0) + 1

    vectors: dict[int, dict[str, float]] = {}
    for s in sources:
        size = doc_size[s.document_id]
        per_doc = doc_df[s.document_id]
        vec: dict[str, float] = {}
        for term, tf in counts[s.provision_id].items():
            if df[term] > n * SIMILARITY_MAX_DF:
                continue
            if size >= SIMILARITY_MIN_DOC_SIZE and per_doc[term] > (
                size * SIMILARITY_MAX_DF
            ):
                continue
            vec[term] = (1.0 + math.log(tf)) * math.log(n / df[term])
        norm = math.sqrt(sum(x * x for x in vec.values()))
        if norm > 0:
            vectors[s.provision_id] = {t: x / norm for t, x in vec.items()}
    return vectors


def compute_similarity(
    sources: list[SimilaritySource],
) -> list[tuple[int, int, int, int]]:
    """(provision_id, similar_provision_id, rank, score ×1000) rows: for each
    provision, its best SIMILARITY_TOP_PER_DOCUMENT matches in every document
    that score at least SIMILARITY_MIN_SCORE."""
    by_id = {s.provision_id: s for s in sources}
    vectors = _similarity_vectors(sources)
    # Provisions are indexed 0..n-1 and each term's postings are parallel
    # lists, so scores accumulate in a flat list rather than a dict. Each
    # pair's sum still runs over the source's terms in the same order, so
    # the scores are the same floats as a dict accumulator gives.
    ids = sorted(vectors)
    index = {pid: i for i, pid in enumerate(ids)}
    postings: dict[str, tuple[list[int], list[float]]] = {}
    for pid, vec in vectors.items():
        for term, weight in vec.items():
            idxs, weights = postings.setdefault(term, ([], []))
            idxs.append(index[pid])
            weights.append(weight)

    floor = round(SIMILARITY_MIN_SCORE * 1000)
    # A cheap superset of the scores that can round up to the floor.
    prefilter = (floor - 1) / 1000
    rows: list[tuple[int, int, int, int]] = []
    for i, pid in enumerate(ids):
        acc = [0.0] * len(ids)
        for term, weight in vectors[pid].items():
            idxs, weights = postings[term]
            for j, other_weight in zip(idxs, weights, strict=True):
                acc[j] += weight * other_weight
        acc[i] = 0.0
        per_doc: dict[int, list[tuple[int, tuple[str, str], int]]] = {}
        for j in [j for j, x in enumerate(acc) if x > prefilter]:
            score_int = min(1000, round(acc[j] * 1000))
            if score_int < floor:
                continue
            src = by_id[ids[j]]
            per_doc.setdefault(src.document_id, []).append(
                (-score_int, src.order, ids[j])
            )
        for matches in per_doc.values():
            matches.sort()
            for rank, (neg, _, other) in enumerate(
                matches[:SIMILARITY_TOP_PER_DOCUMENT], start=1
            ):
                rows.append((pid, other, rank, -neg))
    return rows


def _similarity_sources(conn: sqlite3.Connection) -> list[SimilaritySource]:
    """One source per provision with text: its latest version that has text
    (aliases followed, deletions and TEXT MISSING skipped) and every title the
    provision has carried."""
    latest = conn.execute(
        """
        SELECT p.id, p.document_id, d.code, p.sort_key, p.current_grouping,
               p.canonical_title,
               (SELECT COALESCE(root.text, pv.text)
                FROM provision_versions pv
                JOIN document_revisions dr ON dr.id = pv.revision_id
                LEFT JOIN provision_versions root
                       ON root.id = pv.same_as_version_id
                WHERE pv.provision_id = p.id AND pv.deleted = 0
                  AND NOT pv.text_missing
                ORDER BY dr.ordinal DESC LIMIT 1) AS text
        FROM provisions p JOIN documents d ON d.id = p.document_id
        ORDER BY p.id
        """
    ).fetchall()
    titles: dict[int, set[str]] = {}
    for pid, title in conn.execute(
        "SELECT provision_id, title_at_revision FROM provision_versions"
    ):
        titles.setdefault(pid, set()).add(title)
    return [
        SimilaritySource(
            provision_id=pid,
            document_id=doc_id,
            order=(doc_code, key),
            titles=tuple(sorted(titles.get(pid, set()) | {canonical})),
            grouping=grouping,
            text=plain_text(text),
        )
        for pid, doc_id, doc_code, key, grouping, canonical, text in latest
        if text is not None
    ]


def insert_similarity(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO provision_similarity "
        "(provision_id, similar_provision_id, rank, score) VALUES (?, ?, ?, ?)",
        compute_similarity(_similarity_sources(conn)),
    )


def similarity_report(conn: sqlite3.Connection) -> dict[str, int]:
    bands = conn.execute(
        """
        SELECT count(DISTINCT provision_id),
               sum(score < 500), sum(score >= 500 AND score < 750), sum(score >= 750)
        FROM provision_similarity
        """
    ).fetchone()
    return {
        "provisions_with_matches": bands[0],
        "score_below_500": bands[1] or 0,
        "score_500_to_749": bands[2] or 0,
        "score_750_up": bands[3] or 0,
    }
