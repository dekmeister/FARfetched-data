"""Document, provision, version and paragraph inserts."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from certbuild.errors import BuildError
from certbuild.keys import sort_key
from certbuild.lookups import issuer_id_for
from certbuild.sources import (
    JsonObject,
    DOCUMENT_FILE,
    Source,
    integrity_context,
    load_provisions,
    provenance,
)
from certbuild.text.paragraphs import ParsedText, TextFormatError, parse_paragraphs


def insert_documents(conn: sqlite3.Connection, documents: list[Source]) -> None:
    for s in documents:
        d = s.doc
        with integrity_context(s.path):
            cur = conn.execute(
                "INSERT INTO documents "
                "(issuer_id, doc_kind, code, slug, title) VALUES (?, ?, ?, ?, ?)",
                (
                    issuer_id_for(conn, d["issuer"]),
                    d["doc_kind"],
                    d["code"],
                    d["slug"],
                    d.get("title"),
                ),
            )
            doc_id = cur.lastrowid
            for r in d["revisions"]:
                source, notes = provenance(r)
                conn.execute(
                    "INSERT INTO document_revisions "
                    "(document_id, designator, ordinal, effective_date, "
                    " provenance, provenance_notes) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        doc_id,
                        r["designator"],
                        r["ordinal"],
                        r["effective_date"],
                        source,
                        notes,
                    ),
                )


def document_id_for(conn: sqlite3.Connection, issuer: str, slug: str) -> int | None:
    row = conn.execute(
        "SELECT d.id FROM documents d JOIN issuers i ON i.id = d.issuer_id "
        "WHERE i.code = ? AND d.slug = ?",
        (issuer, slug),
    ).fetchone()
    return row[0] if row else None


def _resolve_alias_versions(
    label: str,
    versions: list[JsonObject],
    ordinal_of: dict[str, int],
) -> list[JsonObject]:
    """Return versions in revision order with `same_as_designator` resolved.

    Each returned dict carries the resolved `text` (None for a deleted version)
    plus the original `same_as_designator` so the DB can record both. A
    deletion must follow a live version, and an alias must not target a
    deleted one.
    """
    items: list[tuple[int, JsonObject]] = []
    for v in versions:
        if v["designator"] not in ordinal_of:
            raise BuildError(
                [
                    f"Provision {label}: revision '{v['designator']}' "
                    f"not declared in {DOCUMENT_FILE}"
                ]
            )
        items.append((ordinal_of[v["designator"]], v))
    items.sort(key=lambda x: x[0])

    resolved_text: dict[str, str] = {}
    deleted_designators: set[str] = set()
    out: list[JsonObject] = []
    live = False  # is the provision in force after the previous version?
    for ordinal, v in items:
        if v.get("deleted"):
            if not live:
                raise BuildError(
                    [
                        f"Provision {label}: version '{v['designator']}' deletes "
                        f"a provision that is not in force"
                    ]
                )
            live = False
            deleted_designators.add(v["designator"])
            out.append({**v, "text": None, "same_as_designator": None})
            continue
        live = True
        if "text" in v:
            text = v["text"]
            same_as = None
        else:
            target = v["same_as_designator"]
            if target in deleted_designators:
                raise BuildError(
                    [
                        f"Provision {label}: version '{v['designator']}' "
                        f"aliases deleted version '{target}'"
                    ]
                )
            if target not in resolved_text:
                raise BuildError(
                    [
                        f"Provision {label}: version '{v['designator']}' "
                        f"aliases unknown designator '{target}' (must point at "
                        f"an earlier version of the same provision)"
                    ]
                )
            if ordinal_of[target] >= ordinal:
                raise BuildError(
                    [
                        f"Provision {label}: version '{v['designator']}' "
                        f"aliases '{target}' which is not strictly earlier"
                    ]
                )
            text = resolved_text[target]
            same_as = target
        resolved_text[v["designator"]] = text
        out.append({**v, "text": text, "same_as_designator": same_as})
    return out


@dataclass
class TextStats:
    """Paragraph-structure counts for the build report."""

    structured: int = 0
    flat: int = 0
    label_gaps: int = 0


def parse_texts(provisions: list[Source]) -> tuple[dict[str, ParsedText], list[str]]:
    """Parse every version text once (docs/DATA_FORMAT.md §Text format).
    Return the parses by text, and the format errors of every file."""
    parsed: dict[str, ParsedText] = {}
    errors: list[str] = []
    for s in provisions:
        p = s.doc
        label = f"{p['issuer']}/{p['document']}/{p['key']}"
        for v in p.get("versions", []):
            text = v.get("text")
            if not isinstance(text, str) or text in parsed:
                continue
            try:
                parsed[text] = parse_paragraphs(text)
            except TextFormatError as exc:
                designator = v.get("designator", "?")
                errors.append(
                    f"{s.path}: Provision {label} version '{designator}': text {exc}"
                )
    return parsed, errors


def check_text_format(data_dir: Path) -> list[str]:
    """Format errors in every provision text under data_dir."""
    return parse_texts(load_provisions(data_dir))[1]


def _insert_paragraphs(
    conn: sqlite3.Connection, pv_id: int, parsed: ParsedText
) -> None:
    conn.executemany(
        "INSERT INTO provision_paragraphs "
        "(provision_version_id, seq, depth, label, path, section, heading, kind, "
        "text) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                pv_id,
                p.seq,
                p.depth,
                p.label,
                p.path,
                p.section,
                int(p.heading),
                p.kind,
                p.text,
            )
            for p in parsed.paragraphs
        ],
    )


def insert_provisions(
    conn: sqlite3.Connection, provisions: list[Source], texts: dict[str, ParsedText]
) -> tuple[TextStats, list[str]]:
    """Insert provisions, versions, actions and paragraphs (`texts`: every
    version text, parsed by `parse_texts`). A file whose revisions, aliases
    or number are wrong is skipped and its fault listed, so one run reports
    every such file; the caller raises."""
    stats = TextStats()
    errors: list[str] = []
    for s in provisions:
        try:
            doc_id, revisions, resolved = _checked_versions(conn, s)
        except BuildError as exc:
            errors.extend(exc.errors)
            continue
        _insert_provision(conn, s, doc_id, revisions, resolved, texts, stats)
    return stats, errors


def _checked_versions(
    conn: sqlite3.Connection, s: Source
) -> tuple[int, dict[str, tuple[int, int]], list[JsonObject]]:
    """A provision file's document id, the document's revisions (designator
    -> (id, ordinal)) and its versions with aliases resolved. Raise
    BuildError on the file's first fault: later checks would only cascade."""
    p = s.doc
    label = f"{p['issuer']}/{p['document']}/{p['key']}"
    doc_id = document_id_for(conn, p["issuer"], p["document"])
    if doc_id is None:
        raise BuildError(
            [f"{s.path}: no {DOCUMENT_FILE} for ({p['issuer']}, {p['document']})"]
        )
    revisions = {
        d: (rid, o)
        for rid, d, o in conn.execute(
            "SELECT id, designator, ordinal FROM document_revisions "
            "WHERE document_id = ?",
            (doc_id,),
        )
    }
    ordinal_of = {d: o for d, (_, o) in revisions.items()}
    resolved = _resolve_alias_versions(label, p["versions"], ordinal_of)
    latest_number = resolved[-1].get("number", p["number"])
    if latest_number != p["number"]:
        raise BuildError(
            [
                f"{s.path}: number {p['number']!r} is not the number printed "
                f"at the latest version ({latest_number!r} at "
                f"{resolved[-1]['designator']!r})"
            ]
        )
    return doc_id, revisions, resolved


def _insert_provision(
    conn: sqlite3.Connection,
    s: Source,
    doc_id: int,
    revisions: dict[str, tuple[int, int]],
    resolved: list[JsonObject],
    texts: dict[str, ParsedText],
    stats: TextStats,
) -> None:
    p = s.doc
    with integrity_context(s.path):
        cur = conn.execute(
            "INSERT INTO provisions "
            "(document_id, key, number, sort_key, canonical_title, "
            " current_grouping, subject_group) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                doc_id,
                p["key"],
                p["number"],
                sort_key(p["number"]),
                p["canonical_title"],
                p.get("current_grouping"),
                p.get("subject_group"),
            ),
        )
        prov_id = cur.lastrowid
        version_id: dict[str, int] = {}
        for v in resolved:
            source, notes = provenance(v)
            same_as = v["same_as_designator"]
            pv_cur = conn.execute(
                "INSERT INTO provision_versions "
                "(document_id, provision_id, revision_id, number, "
                " grouping_at_time, title_at_revision, text, deleted, "
                " same_as_version_id, publication_cite, source_url, "
                " provenance, provenance_notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    doc_id,
                    prov_id,
                    revisions[v["designator"]][0],
                    v.get("number", p["number"]),
                    v.get("grouping_at_time"),
                    v["title_at_revision"],
                    v["text"],
                    1 if v.get("deleted") else 0,
                    version_id[same_as] if same_as else None,
                    v.get("publication_cite") or None,
                    v.get("source_url"),
                    source,
                    notes,
                ),
            )
            pv_id = pv_cur.lastrowid
            assert pv_id is not None
            version_id[v["designator"]] = pv_id
            for seq, action in enumerate(v.get("actions", [])):
                conn.execute(
                    "INSERT INTO version_actions "
                    "(provision_version_id, seq, action_type, reference, "
                    " issued_on, source_url, notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        pv_id,
                        seq,
                        action["type"],
                        action.get("reference"),
                        action.get("issued_on"),
                        action.get("source_url"),
                        action.get("notes"),
                    ),
                )
            if v["text"] is None:
                continue
            parsed = texts[v["text"]]
            _insert_paragraphs(conn, pv_id, parsed)
            if same_as is None:  # an alias is counted as its target
                stats.structured += parsed.structured
                stats.flat += not parsed.structured
                stats.label_gaps += parsed.gaps


def number_clashes(conn: sqlite3.Connection) -> list[str]:
    """At every revision of a document, a printed number names at most one
    provision in force. Versions are sparse (a provision keeps its number
    until its next version), so this is a sweep in revision order, not a
    constraint the DDL can state."""
    errors: list[str] = []
    rows = conn.execute(
        "SELECT d.id, i.code, d.slug, dr.ordinal, dr.designator, p.id, p.key, "
        "       pv.number, pv.deleted "
        "FROM provision_versions pv "
        "JOIN provisions p ON p.id = pv.provision_id "
        "JOIN documents d ON d.id = pv.document_id "
        "JOIN issuers i ON i.id = d.issuer_id "
        "JOIN document_revisions dr ON dr.id = pv.revision_id "
        "ORDER BY d.id, dr.ordinal, p.id"
    ).fetchall()
    doc: int | None = None
    number_of: dict[int, str] = {}  # provision id -> number, while in force
    holders: dict[str, set[int]] = {}  # number -> provision ids in force
    keys: dict[int, str] = {}
    i = 0
    while i < len(rows):
        doc_id, issuer, slug, ordinal, designator = rows[i][:5]
        if doc_id != doc:
            doc, number_of, holders = doc_id, {}, {}
        touched: set[str] = set()
        while i < len(rows) and rows[i][0] == doc_id and rows[i][3] == ordinal:
            _, _, _, _, _, pid, key, number, deleted = rows[i]
            keys[pid] = key
            old = number_of.pop(pid, None)
            if old is not None:
                holders[old].discard(pid)
            if not deleted:
                number_of[pid] = number
                holders.setdefault(number, set()).add(pid)
                touched.add(number)
            i += 1
        for number in sorted(touched):
            if len(holders[number]) > 1:
                names = ", ".join(sorted(keys[pid] for pid in holders[number]))
                errors.append(
                    f"{issuer}/{slug} at {designator}: number {number!r} is "
                    f"printed by more than one provision in force ({names})"
                )
    return errors
