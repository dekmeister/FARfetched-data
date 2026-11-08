"""Aircraft, TCDS and cert-basis inserts."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from certbuild.errors import BuildError
from certbuild.lookups import category_id_for, issuer_id_for, upsert_manufacturer
from certbuild.provisions import document_id_for
from certbuild.resolve import DocIndex, Ref, Resolved, resolve_entry
from certbuild.sources import Source, integrity_context
from certbuild.text.paragraphs import paragraph_ref_paths


def _doc_index(conn: sqlite3.Connection, document_id: int, slug: str) -> DocIndex:
    idx = DocIndex(document_id, slug)
    for pid, number in conn.execute(
        "SELECT id, number FROM provisions WHERE document_id = ?", (document_id,)
    ):
        idx.numbers[pid] = number
    for rid, designator, ordinal in conn.execute(
        "SELECT id, designator, ordinal FROM document_revisions WHERE document_id = ?",
        (document_id,),
    ):
        idx.revisions[designator] = (rid, ordinal)
    for pid, ordinal, rid, pv_id, deleted, number in conn.execute(
        "SELECT pv.provision_id, dr.ordinal, dr.id, pv.id, pv.deleted, pv.number "
        "FROM provision_versions pv "
        "JOIN document_revisions dr ON dr.id = pv.revision_id "
        "WHERE pv.document_id = ?",
        (document_id,),
    ):
        idx.versions.setdefault(pid, []).append((ordinal, rid, pv_id))
        idx.carriers.setdefault(number, set()).add(pid)
        idx.printed[pv_id] = number
        if deleted:
            idx.deleted.add(pv_id)
    return idx


def _doc_index_for(
    conn: sqlite3.Connection,
    key: tuple[str, str],
    doc_indexes: dict[tuple[str, str], DocIndex],
) -> DocIndex | None:
    if key not in doc_indexes:
        doc_id = document_id_for(conn, *key)
        if doc_id is None:
            return None
        doc_indexes[key] = _doc_index(conn, doc_id, key[1])
    return doc_indexes[key]


def _exclude_ordinals(
    conn: sqlite3.Connection,
    refs: list[dict],
    doc_indexes: dict[tuple[str, str], DocIndex],
) -> dict[tuple[str, str], int]:
    """Per document, the highest `to` among an entry's include refs: the
    revision at which its exclude refs' numbers are read."""
    out: dict[tuple[str, str], int] = {}
    for ref in refs:
        if ref.get("effect", "include") != "include" or "to" not in ref:
            continue
        key = (ref["issuer"], ref["document"])
        doc = _doc_index_for(conn, key, doc_indexes)
        rev = doc.revisions.get(ref["to"]) if doc else None
        if rev is not None:
            out[key] = max(out.get(key, rev[1]), rev[1])
    return out


def _insert_ref(
    conn: sqlite3.Connection,
    entry_id: int,
    seq: int,
    ref: dict,
    doc_indexes: dict[tuple[str, str], DocIndex],
    label: str,
    exclude_at: dict[tuple[str, str], int],
) -> tuple[Ref | None, list[str]]:
    """Insert one ref and its children. Return it resolved, or the errors.

    `provisions` are printed numbers, read at the ref's `to` (an exclude ref:
    at `exclude_at`, the entry's highest include `to` in the document)."""
    where = f"{label} ref {seq}"
    key = (ref["issuer"], ref["document"])
    doc = _doc_index_for(conn, key, doc_indexes)
    if doc is None:
        return None, [f"{where}: unknown document {key[0]}/{key[1]}"]

    errors: list[str] = []
    to_rev: tuple[int, int] | None = None
    if "to" in ref:
        to_rev = doc.revisions.get(ref["to"])
        if to_rev is None:
            errors.append(f"{where}: unknown revision {ref['to']!r} in {key[1]}")
    skip: list[int] = []
    for d in ref.get("skip", []):
        rev = doc.revisions.get(d)
        if rev is None:
            errors.append(f"{where}: unknown skip revision {d!r} in {key[1]}")
        elif to_rev is not None and rev[1] >= to_rev[1]:
            errors.append(f"{where}: skip {d!r} is not earlier than to {ref['to']!r}")
        else:
            skip.append(rev[0])
    provisions: list[int] = []
    at = to_rev[1] if to_rev else exclude_at.get(key)
    for number in ref.get("provisions", []):
        if at is None:
            if "to" not in ref:
                errors.append(
                    f"{where}: exclude of {key[1]}.{number} has no include ref "
                    f"in {key[1]} to read its number at"
                )
            continue
        pid, why = doc.provision_at(number, at)
        if pid is None:
            errors.append(f"{where}: {why}")
        else:
            provisions.append(pid)
    if errors:
        return None, errors

    effect = ref.get("effect", "include")
    cur = conn.execute(
        "INSERT INTO cert_basis_refs "
        "(entry_id, seq, effect, document_id, to_revision_id, paragraph) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            entry_id,
            seq,
            effect,
            doc.document_id,
            to_rev[0] if to_rev else None,
            ref.get("paragraph"),
        ),
    )
    ref_id = cur.lastrowid
    assert ref_id is not None
    conn.executemany(
        "INSERT INTO cert_basis_ref_provisions (ref_id, document_id, provision_id) "
        "VALUES (?, ?, ?)",
        [(ref_id, doc.document_id, pid) for pid in provisions],
    )
    conn.executemany(
        "INSERT INTO cert_basis_ref_skips (ref_id, document_id, revision_id) "
        "VALUES (?, ?, ?)",
        [(ref_id, doc.document_id, rid) for rid in skip],
    )
    return (
        Ref(
            ref_id=ref_id,
            effect=effect,
            doc=doc,
            to_ordinal=to_rev[1] if to_rev else None,
            skip=frozenset(skip),
            provisions=tuple(provisions),
            paragraph=ref.get("paragraph"),
        ),
        [],
    )


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


def _tcds_id(conn: sqlite3.Connection, tcds_doc: dict, path: Path) -> int:
    """Insert a TCDS once; a repeat must carry identical metadata."""
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
            raise BuildError(
                [
                    f"{path}: TCDS {tcds_doc['tcds_number']} metadata "
                    f"{meta} conflicts with an earlier file's {tuple(row[1:])}"
                ]
            )
        return row[0]
    cur = conn.execute(
        "INSERT INTO tcds "
        "(issuer_id, tcds_number, revision, revision_date, source_url) "
        "VALUES (?, ?, ?, ?, ?)",
        (issuer_id, tcds_doc["tcds_number"], *meta),
    )
    assert cur.lastrowid is not None
    return cur.lastrowid


def insert_aircraft(
    conn: sqlite3.Connection, aircraft: list[Source], para_stats: ParagraphRefStats
) -> list[str]:
    failures: list[str] = []
    doc_indexes: dict[tuple[str, str], DocIndex] = {}
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

            for tcb_entry in doc["tcb"]:
                tcds_doc = tcb_entry["tcds"]
                tcb_cur = conn.execute(
                    "INSERT INTO tcb (model_id, tcds_id, notes) VALUES (?, ?, ?)",
                    (
                        model_id,
                        _tcds_id(conn, tcds_doc, s.path),
                        tcb_entry.get("notes"),
                    ),
                )
                tcb_id = tcb_cur.lastrowid
                for cat_code in tcb_entry["categories"]:
                    conn.execute(
                        "INSERT INTO tcb_categories (tcb_id, category_id) "
                        "VALUES (?, ?)",
                        (tcb_id, category_id_for(conn, cat_code)),
                    )
                for entry in tcb_entry["certification_basis"]:
                    label = (
                        f"{s.path.name} {tcds_doc['tcds_number']} "
                        f"line {entry['display_order']}"
                    )
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
                    refs: list[Ref] = []
                    exclude_at = _exclude_ordinals(
                        conn, entry["references"], doc_indexes
                    )
                    for seq, ref in enumerate(entry["references"]):
                        r, errs = _insert_ref(
                            conn, entry_id, seq, ref, doc_indexes, label, exclude_at
                        )
                        failures.extend(errs)
                        if r is not None:
                            refs.append(r)
                    rows, errs = resolve_entry(refs, label)
                    failures.extend(errs)
                    failures.extend(
                        _check_paragraph_refs(conn, rows, label, para_stats)
                    )
                    conn.executemany(
                        "INSERT INTO cert_basis_resolved "
                        "(entry_id, provision_version_id, via_ref_id, paragraph) "
                        "VALUES (?, ?, ?, ?)",
                        [
                            (entry_id, r.provision_version_id, r.ref_id, r.paragraph)
                            for r in rows
                        ],
                    )
    return failures
