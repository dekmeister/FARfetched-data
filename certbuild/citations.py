"""What ELOS, special condition and exemption lines cite (docs/DATA_FORMAT.md
§Citations, docs/SQLITE.md §Citations).

Tools read the citations from the line; this resolves them against the
documents, fails loud on any that can't be, and picks the version to link. It
must not write to `cert_basis_resolved` or read a citation as part of the
basis: a citation says what a line names, not what the aircraft complies with.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from certbuild.resolve import DocIndex, DocKey
from certbuild.text.paragraphs import paragraph_ref_paths


@dataclass
class CitationStats:
    paragraphs_verified: int = 0
    paragraphs_unverifiable: int = 0  # the linked version's text is flat
    paragraphs_unmatched: int = 0  # the linked version has no such paragraph
    paragraphs_unchecked: int = 0  # basis_several: no single version to check


@dataclass(frozen=True)
class _Target:
    """One citation with its designators and number resolved to ids."""

    document_id: int
    provision_id: int
    stated_revision_id: int | None
    stated_version_id: int | None


def resolve_citation(
    citation: dict[str, Any], doc: DocIndex | None, where: str
) -> tuple[_Target | None, list[str]]:
    """Resolve one citation in `doc` (None: the document is unknown). The
    number is read at the stated amendment, or else at the latest revision."""
    key = f"{citation['issuer']}/{citation['document']}"
    if doc is None:
        return None, [f"{where}: unknown document {key}"]
    number = citation["number"]
    at = citation.get("at")
    if at is None:
        pid, why = doc.provision_at(number, max(o for _, o in doc.revisions.values()))
        if pid is None:
            return None, [f"{where}: {why}"]
        return _Target(doc.document_id, pid, None, None), []
    rev = doc.revisions.get(at)
    if rev is None:
        return None, [f"{where}: unknown revision {at!r} in {key}"]
    pid, why = doc.provision_at(number, rev[1])
    if pid is None:
        return None, [f"{where}: {why}"]
    version = doc.pick(pid, rev[1], set())
    if version is None or version in doc.deleted:
        return None, [f"{where}: {key} {number} is not in force at {at}"]
    return _Target(doc.document_id, pid, rev[0], version), []


def _basis_versions(conn: sqlite3.Connection, tcb_id: int) -> dict[int, set[int]]:
    """Provision id -> the versions this TCB's resolved basis holds it at."""
    out: dict[int, set[int]] = {}
    for provision_id, version_id in conn.execute(
        "SELECT pv.provision_id, pv.id FROM cert_basis_resolved r "
        "JOIN cert_basis_entries e ON e.id = r.entry_id "
        "JOIN provision_versions pv ON pv.id = r.provision_version_id "
        "WHERE e.tcb_id = ?",
        (tcb_id,),
    ):
        out.setdefault(provision_id, set()).add(version_id)
    return out


def _latest_with_text(conn: sqlite3.Connection, provision_id: int) -> int:
    """The newest version that isn't a deletion, preferring one with real
    text. A deleted section's page would otherwise say only that it is gone."""
    row = conn.execute(
        "SELECT pv.id FROM provision_versions pv "
        "JOIN document_revisions dr ON dr.id = pv.revision_id "
        "WHERE pv.provision_id = ? AND pv.deleted = 0 "
        "ORDER BY pv.text_missing, dr.ordinal DESC LIMIT 1",
        (provision_id,),
    ).fetchone()
    assert row is not None  # a provision's first version is never a deletion
    return int(row[0])


def choose_version(
    target: _Target, basis: set[int], latest: Callable[[int], int]
) -> tuple[int | None, str]:
    """The version a citation links to, and why: the amendment the line
    states; the one version the aircraft's basis holds; none when the basis
    holds several (the line doesn't say which); or the latest text."""
    if target.stated_version_id is not None:
        return target.stated_version_id, "stated"
    if len(basis) == 1:
        return next(iter(basis)), "basis"
    if basis:
        return None, "basis_several"
    return latest(target.provision_id), "latest"


def _check_paragraph(
    conn: sqlite3.Connection,
    paragraph: str,
    version_id: int | None,
    where: str,
    stats: CitationStats,
) -> list[str]:
    """Count a paragraph against the linked version. Only a malformed one is
    an error: a TCDS line can name a paragraph the linked text doesn't have,
    and that says something about the line, not about the reference."""
    if version_id is None:
        if paragraph_ref_paths(paragraph, set()) is None:
            return [f"{where}: paragraph {paragraph!r} is not a run of (x) labels"]
        stats.paragraphs_unchecked += 1
        return []
    paths = {
        p
        for (p,) in conn.execute(
            "SELECT path FROM provision_paragraphs "
            "WHERE provision_version_id = ? AND path IS NOT NULL",
            (version_id,),
        )
    }
    missing = paragraph_ref_paths(paragraph, paths)
    if missing is None:
        return [f"{where}: paragraph {paragraph!r} is not a run of (x) labels"]
    if not paths:
        stats.paragraphs_unverifiable += 1
    elif missing:
        stats.paragraphs_unmatched += 1
    else:
        stats.paragraphs_verified += 1
    return []


def _insert_citations_of(
    conn: sqlite3.Connection,
    entry: dict[str, Any],
    entry_id: int,
    label: str,
    context: _Tcb,
) -> list[str]:
    failures: list[str] = []
    for seq, citation in enumerate(entry.get("citations", [])):
        where = f"{label} citation {seq}"
        doc = context.doc_for((citation["issuer"], citation["document"]))
        target, errs = resolve_citation(citation, doc, where)
        failures.extend(errs)
        if target is None:
            continue
        version, basis = choose_version(
            target,
            context.basis.get(target.provision_id, set()),
            lambda pid: _latest_with_text(conn, pid),
        )
        paragraph = citation.get("paragraph")
        if paragraph is not None:
            failures.extend(
                _check_paragraph(conn, paragraph, version, where, context.stats)
            )
        conn.execute(
            "INSERT INTO cert_basis_citations "
            "(entry_id, seq, document_id, provision_id, paragraph, "
            " stated_revision_id, provision_version_id, version_basis) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry_id,
                seq,
                target.document_id,
                target.provision_id,
                paragraph,
                target.stated_revision_id,
                version,
                basis,
            ),
        )
    return failures


def _insert_gaps_of(
    conn: sqlite3.Connection, entry: dict[str, Any], entry_id: int, label: str
) -> list[str]:
    failures: list[str] = []
    for seq, gap in enumerate(entry.get("citation_gaps", [])):
        if gap["cited"] not in entry["raw_reference"]:
            failures.append(f"{label} gap {seq}: {gap['cited']!r} is not in the line")
            continue
        conn.execute(
            "INSERT INTO cert_basis_citation_gaps (entry_id, seq, cited, reason) "
            "VALUES (?, ?, ?, ?)",
            (entry_id, seq, gap["cited"], gap["reason"]),
        )
    return failures


@dataclass(frozen=True)
class _Tcb:
    """What every citation of one TCB is resolved against."""

    doc_for: Callable[[DocKey], DocIndex | None]
    basis: dict[int, set[int]]
    stats: CitationStats


def insert_citations(
    conn: sqlite3.Connection,
    tcb_id: int,
    tcb_entry: dict[str, Any],
    doc_for: Callable[[DocKey], DocIndex | None],
    stats: CitationStats,
) -> list[str]:
    """Insert one TCB's citations and gaps, after its entries have resolved
    (the version to link can depend on the whole basis). Return the failures."""
    ids = dict(
        conn.execute(
            "SELECT display_order, id FROM cert_basis_entries WHERE tcb_id = ?",
            (tcb_id,),
        ).fetchall()
    )
    context = _Tcb(doc_for, _basis_versions(conn, tcb_id), stats)
    number = tcb_entry["tcds"]["tcds_number"]
    failures: list[str] = []
    for entry in tcb_entry["certification_basis"]:
        order = entry["display_order"]
        label = f"{number} line {order}"
        entry_id = ids[order]
        failures.extend(_insert_citations_of(conn, entry, entry_id, label, context))
        failures.extend(_insert_gaps_of(conn, entry, entry_id, label))
    return failures


def _by_issuer_and_type(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for issuer, entry_type, entries, cited, gapped, citations, gaps in conn.execute(
        """
        SELECT i.code, e.entry_type, count(*),
               sum(EXISTS (SELECT 1 FROM cert_basis_citations c
                           WHERE c.entry_id = e.id)),
               sum(EXISTS (SELECT 1 FROM cert_basis_citation_gaps g
                           WHERE g.entry_id = e.id)),
               sum((SELECT count(*) FROM cert_basis_citations c
                    WHERE c.entry_id = e.id)),
               sum((SELECT count(*) FROM cert_basis_citation_gaps g
                    WHERE g.entry_id = e.id))
        FROM cert_basis_entries e
        JOIN tcb t ON t.id = e.tcb_id
        JOIN tcds d ON d.id = t.tcds_id
        JOIN issuers i ON i.id = d.issuer_id
        WHERE e.entry_type IN ('elos', 'special_condition', 'exemption')
        GROUP BY i.code, e.entry_type
        ORDER BY i.code, e.entry_type
        """
    ):
        out.setdefault(issuer, {})[entry_type] = {
            "entries": entries,
            "entries_with_citations": cited,
            "entries_with_gaps": gapped,
            "citations": citations,
            "gaps": gaps,
        }
    return out


def citation_report(conn: sqlite3.Connection, stats: CitationStats) -> dict[str, Any]:
    """Counts for the build report. They say how much was read and resolved,
    never whether a citation is right: that takes reading the TCDS."""
    return {
        "by_issuer_and_type": _by_issuer_and_type(conn),
        "version_basis": dict(
            conn.execute(
                "SELECT version_basis, count(*) FROM cert_basis_citations "
                "GROUP BY version_basis ORDER BY version_basis"
            ).fetchall()
        ),
        "gaps_by_reason": dict(
            conn.execute(
                "SELECT reason, count(*) FROM cert_basis_citation_gaps "
                "GROUP BY reason ORDER BY reason"
            ).fetchall()
        ),
        "entries_withheld": conn.execute(
            "SELECT count(DISTINCT entry_id) FROM cert_basis_citation_gaps "
            "WHERE reason = 'withheld_basis_list'"
        ).fetchone()[0],
        "paragraphs": {
            "verified": stats.paragraphs_verified,
            "unverifiable": stats.paragraphs_unverifiable,
            "unmatched": stats.paragraphs_unmatched,
            "unchecked": stats.paragraphs_unchecked,
        },
    }
