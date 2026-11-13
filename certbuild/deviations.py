"""Deviation records: special conditions, ELOS/ESF, exemptions, deviations
(docs/DATA_FORMAT.md §Deviations, docs/SQLITE.md §Deviations).

A record is a link to the regulator's page plus what its listing says. A
proposed record may name the final it became. Its citations are resolved against the documents and fail loud like a TCDS line's.
This module must not touch the certification basis: a deviation's citations
say what it names, never what any aircraft complies with.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from certbuild.aircraft import doc_index
from certbuild.citations import resolve_citation
from certbuild.lookups import issuer_id_for
from certbuild.provisions import document_id_for
from certbuild.resolve import DocIndex, DocKey
from certbuild.sources import Source, integrity_context
from certbuild.text.paragraphs import paragraph_ref_paths


def check_deviation_paths(deviations: list[Source]) -> list[str]:
    """A record lives at deviations/{issuer}/{key}.json."""
    errors: list[str] = []
    for s in deviations:
        want = f"{s.doc['issuer'].lower()}/{s.doc['key']}"
        got = f"{s.path.parent.name}/{s.path.stem}"
        if got != want:
            errors.append(f"{s.path}: expected at deviations/{want}.json")
    return errors


class _Indexes:
    """A DocIndex per cited document, built on first use."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.cache: dict[DocKey, DocIndex | None] = {}

    def get(self, key: DocKey) -> DocIndex | None:
        if key not in self.cache:
            doc_id = document_id_for(self.conn, *key)
            self.cache[key] = (
                None if doc_id is None else doc_index(self.conn, doc_id, key[1])
            )
        return self.cache[key]


def _insert_citations(
    conn: sqlite3.Connection,
    deviation_id: int,
    doc: dict[str, Any],
    label: str,
    indexes: _Indexes,
) -> list[str]:
    failures: list[str] = []
    for seq, citation in enumerate(doc.get("citations", [])):
        where = f"{label} citation {seq}"
        target, errs = resolve_citation(
            citation, indexes.get((citation["issuer"], citation["document"])), where
        )
        failures.extend(errs)
        paragraph = citation.get("paragraph")
        if paragraph is not None and paragraph_ref_paths(paragraph, set()) is None:
            failures.append(f"{where}: paragraph {paragraph!r} is not a run of (x)")
            continue
        if target is None:
            continue
        conn.execute(
            "INSERT INTO deviation_citations "
            "(deviation_id, seq, document_id, provision_id, paragraph) "
            "VALUES (?, ?, ?, ?, ?)",
            (deviation_id, seq, target.document_id, target.provision_id, paragraph),
        )
    return failures


def _insert_gaps(
    conn: sqlite3.Connection, deviation_id: int, doc: dict[str, Any], label: str
) -> list[str]:
    """A gap's `cited` must be a slice of the title, number or regulation field."""
    failures: list[str] = []
    printed = [doc.get(f) or "" for f in ("title", "number", "regulation_ref")]
    for seq, gap in enumerate(doc.get("citation_gaps", [])):
        if not any(gap["cited"] in text for text in printed):
            failures.append(
                f"{label} gap {seq}: {gap['cited']!r} is not in the title, "
                "number or regulation_ref"
            )
            continue
        conn.execute(
            "INSERT INTO deviation_citation_gaps (deviation_id, seq, cited, reason) "
            "VALUES (?, ?, ?, ?)",
            (deviation_id, seq, gap["cited"], gap["reason"]),
        )
    return failures


_COLUMNS = (
    "key",
    "kind",
    "number",
    "title",
    "stage",
    "published_on",
    "source_url",
    "applicant",
    "make",
    "model",
    "regulation_ref",
    "disposition",
)
_INSERT = (
    f"INSERT INTO deviations (issuer_id, {', '.join(_COLUMNS)}) "
    f"VALUES ({', '.join('?' * (len(_COLUMNS) + 1))})"
)


def _link_finals(
    conn: sqlite3.Connection, ids: dict[tuple[str, str], int], deviations: list[Source]
) -> list[str]:
    """A proposed record's `final` names a final record of its issuer and kind."""
    failures: list[str] = []
    by_key = {(s.doc["issuer"], s.doc["key"]): s.doc for s in deviations}
    for s in deviations:
        doc = s.doc
        if "final" not in doc:
            continue
        label = f"deviation {doc['issuer']}/{doc['key']}"
        target = by_key.get((doc["issuer"], doc["final"]))
        if target is None:
            failures.append(f"{label}: final {doc['final']!r} is not a record")
        elif target["stage"] != "final" or target["kind"] != doc["kind"]:
            failures.append(
                f"{label}: final {doc['final']!r} is not a final {doc['kind']}"
            )
        else:
            conn.execute(
                "UPDATE deviations SET final_id = ? WHERE id = ?",
                (ids[(doc["issuer"], doc["final"])], ids[(doc["issuer"], doc["key"])]),
            )
    return failures


def insert_deviations(conn: sqlite3.Connection, deviations: list[Source]) -> list[str]:
    """Insert every record with its citations and gaps; return every failure."""
    failures: list[str] = []
    indexes = _Indexes(conn)
    ids: dict[tuple[str, str], int] = {}
    for s in deviations:
        doc = s.doc
        label = f"deviation {doc['issuer']}/{doc['key']}"
        with integrity_context(s.path):
            cur = conn.execute(
                _INSERT,
                (issuer_id_for(conn, doc["issuer"]), *(doc.get(c) for c in _COLUMNS)),
            )
            deviation_id = cur.lastrowid
            assert deviation_id is not None
            ids[(doc["issuer"], doc["key"])] = deviation_id
            failures.extend(_insert_citations(conn, deviation_id, doc, label, indexes))
            failures.extend(_insert_gaps(conn, deviation_id, doc, label))
    failures.extend(_link_finals(conn, ids, deviations))
    return failures
