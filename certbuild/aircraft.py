"""Aircraft, TCDS and cert-basis inserts (docs/SQLITE.md).

The SQL half of cert-basis resolution: it builds each document's `DocIndex`
from the DB, hands refs to the pure rules in resolve.py and inserts what they
return. Resolution decisions belong in resolve.py, not here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from certbuild.citations import CitationStats, insert_citations
from certbuild.lookups import category_id_for, issuer_id_for, upsert_manufacturer
from certbuild.provisions import document_id_for
from certbuild.resolve import (
    DocIndex,
    DocKey,
    Ref,
    Resolved,
    exclude_ordinals,
    resolve_entry,
    resolve_ref,
)
from certbuild.sources import JsonObject, Source, integrity_context
from certbuild.text.paragraphs import paragraph_ref_paths


def doc_index(conn: sqlite3.Connection, document_id: int, slug: str) -> DocIndex:
    return DocIndex.from_rows(
        document_id,
        slug,
        conn.execute(
            "SELECT id, number FROM provisions WHERE document_id = ?", (document_id,)
        ),
        conn.execute(
            "SELECT id, designator, ordinal FROM document_revisions "
            "WHERE document_id = ?",
            (document_id,),
        ),
        conn.execute(
            "SELECT pv.provision_id, dr.ordinal, dr.id, pv.id, pv.deleted, pv.number "
            "FROM provision_versions pv "
            "JOIN document_revisions dr ON dr.id = pv.revision_id "
            "WHERE pv.document_id = ?",
            (document_id,),
        ),
    )


class _DocIndexes:
    """A DocIndex per document, built on first use."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.cache: dict[DocKey, DocIndex] = {}

    def get(self, key: DocKey) -> DocIndex | None:
        if key not in self.cache:
            doc_id = document_id_for(self.conn, *key)
            if doc_id is None:
                return None
            self.cache[key] = doc_index(self.conn, doc_id, key[1])
        return self.cache[key]


def insert_ref(conn: sqlite3.Connection, entry_id: int, seq: int, r: Ref) -> int:
    """Insert one resolved ref and its provisions and skips; return its id."""
    cur = conn.execute(
        "INSERT INTO cert_basis_refs "
        "(entry_id, seq, effect, document_id, to_revision_id, paragraph) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (entry_id, seq, r.effect, r.doc.document_id, r.to_revision_id, r.paragraph),
    )
    ref_id = cur.lastrowid
    assert ref_id is not None
    conn.executemany(
        "INSERT INTO cert_basis_ref_provisions (ref_id, document_id, provision_id) "
        "VALUES (?, ?, ?)",
        [(ref_id, r.doc.document_id, pid) for pid in r.provisions],
    )
    conn.executemany(
        "INSERT INTO cert_basis_ref_skips (ref_id, document_id, revision_id) "
        "VALUES (?, ?, ?)",
        [(ref_id, r.doc.document_id, rid) for rid in r.skip],
    )
    return ref_id


@dataclass
class ParagraphRefStats:
    verified: int = 0
    unverifiable: int = 0  # the resolved version's text is flat


def _check_paragraph_refs(
    conn: sqlite3.Connection,
    rows: list[Resolved],
    label: str,
    stats: ParagraphRefStats,
) -> list[str]:
    """Check each paragraph-qualified row against its version's paragraphs."""
    errors: list[str] = []
    for r in rows:
        if r.paragraph is None:
            continue
        paths = {
            p
            for (p,) in conn.execute(
                "SELECT path FROM provision_paragraphs "
                "WHERE provision_version_id = ? AND path IS NOT NULL",
                (r.provision_version_id,),
            )
        }
        if not paths:
            stats.unverifiable += 1
            continue
        missing = paragraph_ref_paths(r.paragraph, paths)
        if missing is None:
            errors.append(
                f"{label}: paragraph {r.paragraph!r} is not a run of (x) labels"
            )
        elif missing:
            number, designator = conn.execute(
                "SELECT pv.number, dr.designator FROM provision_versions pv "
                "JOIN document_revisions dr ON dr.id = pv.revision_id "
                "WHERE pv.id = ?",
                (r.provision_version_id,),
            ).fetchone()
            errors.append(
                f"{label}: paragraph {r.paragraph!r}: {''.join(missing)} not in "
                f"{number} at {designator}"
            )
        else:
            stats.verified += 1
    return errors


def _tcds_id(
    conn: sqlite3.Connection, tcds_doc: JsonObject, path: Path, errors: list[str]
) -> int:
    """Insert a TCDS once; a repeat must carry identical metadata (a
    conflict goes to `errors`, and the first file's row is used)."""
    issuer_id = issuer_id_for(conn, tcds_doc["issuer"])
    meta = (
        tcds_doc.get("revision"),
        tcds_doc.get("revision_date"),
        tcds_doc.get("source_url"),
    )
    row = conn.execute(
        "SELECT id, revision, revision_date, source_url FROM tcds "
        "WHERE issuer_id = ? AND tcds_number = ?",
        (issuer_id, tcds_doc["tcds_number"]),
    ).fetchone()
    if row is not None:
        if tuple(row[1:]) != meta:
            errors.append(
                f"{path}: TCDS {tcds_doc['tcds_number']} metadata "
                f"{meta} conflicts with an earlier file's {tuple(row[1:])}"
            )
        return int(row[0])
    cur = conn.execute(
        "INSERT INTO tcds "
        "(issuer_id, tcds_number, revision, revision_date, source_url) "
        "VALUES (?, ?, ?, ?, ?)",
        (issuer_id, tcds_doc["tcds_number"], *meta),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def insert_aircraft(
    conn: sqlite3.Connection,
    aircraft: list[Source],
    para_stats: ParagraphRefStats,
    citation_stats: CitationStats,
) -> list[str]:
    """Insert every aircraft file; return every failure (unresolved
    references, TCDS metadata conflicts) for the caller to raise."""
    failures: list[str] = []
    indexes = _DocIndexes(conn)
    for s in aircraft:
        doc = s.doc
        with integrity_context(s.path):
            cur = conn.execute(
                "INSERT INTO aircraft_models "
                "(manufacturer_id, model_designation, common_name, notes) "
                "VALUES (?, ?, ?, ?)",
                (
                    upsert_manufacturer(conn, doc["manufacturer"]),
                    doc["model_designation"],
                    doc.get("common_name"),
                    doc.get("notes"),
                ),
            )
            model_id = cur.lastrowid
            assert model_id is not None
            for tcb_entry in doc["tcb"]:
                failures.extend(
                    _insert_tcb(
                        conn,
                        model_id,
                        tcb_entry,
                        s.path,
                        indexes,
                        para_stats,
                        citation_stats,
                    )
                )
    return failures


def _insert_tcb(
    conn: sqlite3.Connection,
    model_id: int,
    tcb_entry: dict[str, Any],
    path: Path,
    indexes: _DocIndexes,
    para_stats: ParagraphRefStats,
    citation_stats: CitationStats,
) -> list[str]:
    failures: list[str] = []
    tcds_doc = tcb_entry["tcds"]
    tcb_cur = conn.execute(
        "INSERT INTO tcb (model_id, tcds_id, notes) VALUES (?, ?, ?)",
        (model_id, _tcds_id(conn, tcds_doc, path, failures), tcb_entry.get("notes")),
    )
    tcb_id = tcb_cur.lastrowid
    assert tcb_id is not None
    for cat_code in tcb_entry["categories"]:
        conn.execute(
            "INSERT INTO tcb_categories (tcb_id, category_id) VALUES (?, ?)",
            (tcb_id, category_id_for(conn, cat_code)),
        )
    for entry in tcb_entry["certification_basis"]:
        label = f"{path.name} {tcds_doc['tcds_number']} line {entry['display_order']}"
        failures.extend(_insert_entry(conn, tcb_id, entry, label, indexes, para_stats))
    failures.extend(
        insert_citations(conn, tcb_id, tcb_entry, indexes.get, citation_stats)
    )
    return failures


def _insert_entry(
    conn: sqlite3.Connection,
    tcb_id: int,
    entry: dict[str, Any],
    label: str,
    indexes: _DocIndexes,
    para_stats: ParagraphRefStats,
) -> list[str]:
    """Insert one cert-basis entry, its refs and its resolved rows; return
    the failures."""
    entry_cur = conn.execute(
        "INSERT INTO cert_basis_entries "
        "(tcb_id, display_order, entry_type, raw_reference, "
        " applicability, applicability_notes) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            tcb_id,
            entry["display_order"],
            entry["entry_type"],
            entry["raw_reference"],
            entry.get("applicability"),
            entry.get("applicability_notes"),
        ),
    )
    entry_id = entry_cur.lastrowid
    assert entry_id is not None
    failures: list[str] = []
    refs: list[Ref] = []
    exclude_at = exclude_ordinals(entry["references"], indexes.get)
    for seq, ref in enumerate(entry["references"]):
        doc = indexes.get((ref["issuer"], ref["document"]))
        r, errs = resolve_ref(ref, doc, f"{label} ref {seq}", exclude_at)
        failures.extend(errs)
        if r is not None:
            refs.append(replace(r, ref_id=insert_ref(conn, entry_id, seq, r)))
    rows, errs = resolve_entry(refs, label)
    failures.extend(errs)
    failures.extend(_check_paragraph_refs(conn, rows, label, para_stats))
    conn.executemany(
        "INSERT INTO cert_basis_resolved "
        "(entry_id, provision_version_id, via_ref_id, paragraph) "
        "VALUES (?, ?, ?, ?)",
        [(entry_id, r.provision_version_id, r.ref_id, r.paragraph) for r in rows],
    )
    return failures
