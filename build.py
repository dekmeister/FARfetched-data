"""Compile FARfetched-data JSON sources into cert_basis.sqlite."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from functools import cache
from pathlib import Path
from typing import TypedDict

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

REPO_ROOT = Path(__file__).parent
SCHEMAS_DIR = REPO_ROOT / "schemas"

# Bump on every change to the SQLite contract. Consumers require an exact match.
SCHEMA_VERSION = 1

DOCUMENT_FILE = "_document.json"

SCHEMA_SQL = """
CREATE TABLE build_info (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    schema_version INTEGER NOT NULL,
    git_sha        TEXT,
    built_at       TEXT NOT NULL
) STRICT;

CREATE TABLE issuers (
    id           INTEGER PRIMARY KEY,
    code         TEXT NOT NULL UNIQUE
                 CHECK (code GLOB '[A-Z0-9]*' AND code NOT GLOB '*[^A-Z0-9_-]*'),
    name         TEXT NOT NULL,
    kind         TEXT NOT NULL
                 CHECK (kind IN ('naa', 'military', 'standards_body')),
    country      TEXT,
    successor_id INTEGER REFERENCES issuers(id),
    CHECK (successor_id IS NULL OR successor_id <> id)
) STRICT;

CREATE TABLE documents (
    id        INTEGER PRIMARY KEY,
    issuer_id INTEGER NOT NULL REFERENCES issuers(id),
    doc_kind  TEXT NOT NULL
              CHECK (doc_kind IN (
                  'regulation', 'certification_spec', 'amc_gm',
                  'advisory_circular', 'handbook', 'special_condition',
                  'elos', 'exemption', 'standard'
              )),
    code      TEXT NOT NULL,
    slug      TEXT NOT NULL,
    title     TEXT,
    UNIQUE (issuer_id, code),
    UNIQUE (issuer_id, slug)
) STRICT;

CREATE TABLE document_revisions (
    id               INTEGER PRIMARY KEY,
    document_id      INTEGER NOT NULL REFERENCES documents(id),
    designator       TEXT NOT NULL,
    ordinal          INTEGER NOT NULL CHECK (ordinal >= 0),
    effective_date   TEXT NOT NULL CHECK (date(effective_date) IS effective_date),
    provenance       TEXT NOT NULL CHECK (provenance IN ('scraped', 'ocr', 'manual')),
    provenance_notes TEXT,
    UNIQUE (document_id, designator),
    UNIQUE (document_id, ordinal),
    UNIQUE (document_id, id)
) STRICT;

CREATE TABLE provisions (
    id               INTEGER PRIMARY KEY,
    document_id      INTEGER NOT NULL REFERENCES documents(id),
    number           TEXT NOT NULL,
    sort_key         TEXT NOT NULL,
    canonical_title  TEXT NOT NULL,
    current_grouping TEXT,
    subject_group    TEXT,
    UNIQUE (document_id, number),
    UNIQUE (document_id, id)
) STRICT;

CREATE TABLE provision_versions (
    id                 INTEGER PRIMARY KEY,
    document_id        INTEGER NOT NULL,
    provision_id       INTEGER NOT NULL,
    revision_id        INTEGER NOT NULL,
    grouping_at_time   TEXT,
    title_at_revision  TEXT NOT NULL,
    text               TEXT NOT NULL,
    text_missing       INTEGER GENERATED ALWAYS AS (text = 'TEXT MISSING') VIRTUAL,
    same_as_version_id INTEGER,
    publication_cite   TEXT,
    source_url         TEXT,
    provenance         TEXT NOT NULL CHECK (provenance IN ('scraped', 'ocr', 'manual')),
    provenance_notes   TEXT,
    UNIQUE (provision_id, revision_id),
    UNIQUE (provision_id, id),
    FOREIGN KEY (document_id, provision_id)
        REFERENCES provisions (document_id, id),
    FOREIGN KEY (document_id, revision_id)
        REFERENCES document_revisions (document_id, id),
    FOREIGN KEY (provision_id, same_as_version_id)
        REFERENCES provision_versions (provision_id, id),
    CHECK (same_as_version_id IS NULL OR same_as_version_id <> id)
) STRICT;

CREATE INDEX idx_pv_revision ON provision_versions (revision_id);

-- Rulemaking actions stay per version: DRS records them per section, and the
-- per-section lists for one amendment do not always agree.
CREATE TABLE version_actions (
    id                   INTEGER PRIMARY KEY,
    provision_version_id INTEGER NOT NULL REFERENCES provision_versions(id),
    seq                  INTEGER NOT NULL,
    action_type          TEXT NOT NULL
                         CHECK (action_type IN (
                             'nprm', 'final_rule', 'direct_final_rule',
                             'interim_final_rule', 'easa_npa', 'easa_opinion',
                             'easa_decision', 'jar_npa', 'jar_change', 'other'
                         )),
    reference            TEXT,
    issued_on            TEXT CHECK (issued_on IS NULL OR date(issued_on) IS issued_on),
    source_url           TEXT,
    notes                TEXT,
    UNIQUE (provision_version_id, seq)
) STRICT;

CREATE INDEX idx_actions_reference ON version_actions (reference);

CREATE TABLE manufacturers (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
) STRICT;

CREATE TABLE categories (
    id   INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL
) STRICT;

CREATE TABLE aircraft_models (
    id                INTEGER PRIMARY KEY,
    manufacturer_id   INTEGER NOT NULL REFERENCES manufacturers(id),
    model_designation TEXT NOT NULL,
    common_name       TEXT,
    notes             TEXT,
    UNIQUE (manufacturer_id, model_designation)
) STRICT;

CREATE TABLE model_categories (
    model_id    INTEGER NOT NULL REFERENCES aircraft_models(id),
    category_id INTEGER NOT NULL REFERENCES categories(id),
    PRIMARY KEY (model_id, category_id)
) STRICT, WITHOUT ROWID;

CREATE TABLE tcds (
    id            INTEGER PRIMARY KEY,
    issuer_id     INTEGER NOT NULL REFERENCES issuers(id),
    tcds_number   TEXT NOT NULL,
    revision      TEXT,
    revision_date TEXT
                  CHECK (revision_date IS NULL OR date(revision_date) IS revision_date),
    source_url    TEXT,
    UNIQUE (issuer_id, tcds_number)
) STRICT;

CREATE TABLE tcb (
    id       INTEGER PRIMARY KEY,
    model_id INTEGER NOT NULL REFERENCES aircraft_models(id),
    tcds_id  INTEGER NOT NULL REFERENCES tcds(id),
    notes    TEXT,
    UNIQUE (model_id, tcds_id)
) STRICT;

-- One row per TCDS line, verbatim.
CREATE TABLE cert_basis_entries (
    id                  INTEGER PRIMARY KEY,
    tcb_id              INTEGER NOT NULL REFERENCES tcb(id),
    display_order       INTEGER NOT NULL CHECK (display_order >= 1),
    entry_type          TEXT NOT NULL
                        CHECK (entry_type IN
                            ('regulation', 'special_condition', 'elos',
                             'exemption', 'other')),
    raw_reference       TEXT NOT NULL,
    applicability       TEXT,
    applicability_notes TEXT,
    UNIQUE (tcb_id, display_order)
) STRICT;

-- One row per machine-readable interpretation clause of an entry.
CREATE TABLE cert_basis_refs (
    id             INTEGER PRIMARY KEY,
    entry_id       INTEGER NOT NULL REFERENCES cert_basis_entries(id),
    seq            INTEGER NOT NULL,
    effect         TEXT NOT NULL CHECK (effect IN ('include', 'exclude')),
    document_id    INTEGER NOT NULL REFERENCES documents(id),
    to_revision_id INTEGER,
    paragraph      TEXT,
    UNIQUE (entry_id, seq),
    UNIQUE (entry_id, id),
    UNIQUE (document_id, id),
    FOREIGN KEY (document_id, to_revision_id)
        REFERENCES document_revisions (document_id, id),
    CHECK (
        (effect = 'include' AND to_revision_id IS NOT NULL)
     OR (effect = 'exclude' AND to_revision_id IS NULL AND paragraph IS NULL)
    )
) STRICT;

-- Optional provision scope of a ref. No rows = the whole document.
CREATE TABLE cert_basis_ref_provisions (
    ref_id       INTEGER NOT NULL,
    document_id  INTEGER NOT NULL,
    provision_id INTEGER NOT NULL,
    PRIMARY KEY (ref_id, provision_id),
    FOREIGN KEY (document_id, ref_id) REFERENCES cert_basis_refs (document_id, id),
    FOREIGN KEY (document_id, provision_id) REFERENCES provisions (document_id, id)
) STRICT, WITHOUT ROWID;

-- Revisions skipped by a ref ("23-1 thru 23-38, 23-40" skips 23-39).
CREATE TABLE cert_basis_ref_skips (
    ref_id      INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    revision_id INTEGER NOT NULL,
    PRIMARY KEY (ref_id, revision_id),
    FOREIGN KEY (document_id, ref_id) REFERENCES cert_basis_refs (document_id, id),
    FOREIGN KEY (document_id, revision_id)
        REFERENCES document_revisions (document_id, id)
) STRICT, WITHOUT ROWID;

-- Build-computed expansion of an entry's refs.
CREATE TABLE cert_basis_resolved (
    entry_id             INTEGER NOT NULL,
    provision_version_id INTEGER NOT NULL REFERENCES provision_versions(id),
    via_ref_id           INTEGER NOT NULL,
    paragraph            TEXT,
    PRIMARY KEY (entry_id, provision_version_id),
    FOREIGN KEY (entry_id, via_ref_id) REFERENCES cert_basis_refs (entry_id, id)
) STRICT, WITHOUT ROWID;

CREATE INDEX idx_cbr_version ON cert_basis_resolved (provision_version_id);

CREATE VIEW latest_versions AS
SELECT pv.*, dr.designator, dr.ordinal, dr.effective_date
FROM provision_versions pv
JOIN document_revisions dr ON dr.id = pv.revision_id
WHERE dr.ordinal = (
    SELECT MAX(dr2.ordinal)
    FROM provision_versions pv2
    JOIN document_revisions dr2 ON dr2.id = pv2.revision_id
    WHERE pv2.provision_id = pv.provision_id
);
"""

# Closed set of issuers: (name, kind, country, successor code). Must match the
# `issuer` enum in schemas/common.schema.json. Successors must come first.
_ISSUERS: dict[str, tuple[str, str, str | None, str | None]] = {
    "FAA": ("Federal Aviation Administration", "naa", "US", None),
    "CAA": ("Civil Aeronautics Administration", "naa", "US", "FAA"),
    "CAB": ("Civil Aeronautics Board", "naa", "US", "FAA"),
    "EASA": ("European Union Aviation Safety Agency", "naa", "EU", None),
}

# Closed set of airworthiness categories. Must match the `categories` enum in
# schemas/aircraft_model.schema.json.
_CATEGORY_NAMES: dict[str, str] = {
    "transport": "Transport",
    "normal": "Normal",
    "utility": "Utility",
    "acrobatic": "Acrobatic",
    "commuter": "Commuter",
    "restricted": "Restricted",
    "limited": "Limited",
    "provisional": "Provisional",
    "primary": "Primary",
    "special": "Special",
}


class BuildError(Exception):
    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


@dataclass(frozen=True)
class ValidationError:
    path: Path
    message: str
    location: str

    def __str__(self) -> str:
        where = f" at {self.location}" if self.location else ""
        return f"{self.path}:{where} {self.message}"


@dataclass(frozen=True)
class Source:
    """One loaded JSON file and where it came from."""

    path: Path
    doc: dict


@cache
def _registry() -> Registry:
    resources = []
    for p in sorted(SCHEMAS_DIR.glob("*.schema.json")):
        schema = json.loads(p.read_text())
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


@cache
def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS_DIR / f"{name}.schema.json").read_text())
    return Draft202012Validator(
        schema, registry=_registry(), format_checker=FormatChecker()
    )


def _validate(path: Path, schema_name: str) -> list[ValidationError]:
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [ValidationError(path, f"invalid JSON: {exc}", "")]
    validator = _validator(schema_name)
    errors: list[ValidationError] = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        location = "/".join(str(p) for p in err.absolute_path)
        errors.append(ValidationError(path, err.message, location))
    return errors


def validate_document_file(path: Path) -> list[ValidationError]:
    return _validate(path, "document")


def validate_provision_file(path: Path) -> list[ValidationError]:
    return _validate(path, "provision")


def validate_aircraft_file(path: Path) -> list[ValidationError]:
    return _validate(path, "aircraft_model")


def validate_data_dir(data_dir: Path) -> list[ValidationError]:
    errors: list[ValidationError] = []
    docs_dir = data_dir / "documents"
    if docs_dir.is_dir():
        for p in sorted(docs_dir.rglob("*.json")):
            if p.name == DOCUMENT_FILE:
                errors.extend(validate_document_file(p))
            else:
                errors.extend(validate_provision_file(p))
    aircraft_dir = data_dir / "aircraft"
    if aircraft_dir.is_dir():
        for p in sorted(aircraft_dir.rglob("*.json")):
            errors.extend(validate_aircraft_file(p))
    return errors


# ---------------------------------------------------------------------------
# Loaders


def _load(paths: Iterator[Path]) -> list[Source]:
    return [Source(p, json.loads(p.read_text())) for p in sorted(paths)]


def _load_documents(data_dir: Path) -> list[Source]:
    docs_dir = data_dir / "documents"
    if not docs_dir.is_dir():
        return []
    return _load(docs_dir.rglob(DOCUMENT_FILE))


def _load_provisions(data_dir: Path) -> list[Source]:
    docs_dir = data_dir / "documents"
    if not docs_dir.is_dir():
        return []
    return _load(p for p in docs_dir.rglob("*.json") if p.name != DOCUMENT_FILE)


def _load_aircraft(data_dir: Path) -> list[Source]:
    ac_dir = data_dir / "aircraft"
    if not ac_dir.is_dir():
        return []
    return _load(ac_dir.rglob("*.json"))


def _check_paths(documents: list[Source], provisions: list[Source]) -> list[str]:
    """File location must agree with the identity fields inside the file."""
    errors: list[str] = []
    for s in documents:
        expected = (s.doc["issuer"].lower(), s.doc["slug"])
        actual = (s.path.parent.parent.name, s.path.parent.name)
        if actual != expected:
            errors.append(
                f"{s.path}: expected under documents/{expected[0]}/{expected[1]}/"
            )
    for s in provisions:
        want = f"{s.doc['issuer'].lower()}/{s.doc['document']}/{s.doc['number']}"
        got = f"{s.path.parent.parent.name}/{s.path.parent.name}/{s.path.stem}"
        if got != want:
            errors.append(f"{s.path}: expected at documents/{want}.json")
    return errors


@contextmanager
def _integrity_context(path: Path) -> Iterator[None]:
    """Turn a constraint violation into a BuildError naming the source file."""
    try:
        yield
    except sqlite3.IntegrityError as exc:
        raise BuildError([f"{path}: integrity error: {exc}"]) from exc


def _provenance(obj: dict) -> tuple[str, str | None]:
    prov = obj.get("provenance") or {}
    return prov.get("source", "scraped"), prov.get("notes")


def sort_key(number: str) -> str:
    """Natural sort key: zero-pad every digit run, so 175 sorts before 1309."""
    return re.sub(r"\d+", lambda m: m.group().zfill(6), number)


# ---------------------------------------------------------------------------
# Lookup tables (closed sets, seeded up front)


def _seed_lookups(conn: sqlite3.Connection) -> None:
    for code, (name, kind, country, successor) in _ISSUERS.items():
        successor_id = _issuer_id(conn, successor) if successor else None
        conn.execute(
            "INSERT INTO issuers (code, name, kind, country, successor_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (code, name, kind, country, successor_id),
        )
    conn.executemany(
        "INSERT INTO categories (code, name) VALUES (?, ?)",
        _CATEGORY_NAMES.items(),
    )


def _issuer_id(conn: sqlite3.Connection, code: str) -> int:
    row = conn.execute("SELECT id FROM issuers WHERE code = ?", (code,)).fetchone()
    if row is None:
        raise BuildError([f"unknown issuer {code!r}"])
    return row[0]


def _category_id(conn: sqlite3.Connection, code: str) -> int:
    row = conn.execute("SELECT id FROM categories WHERE code = ?", (code,)).fetchone()
    if row is None:
        raise BuildError([f"unknown category {code!r}"])
    return row[0]


def _upsert_manufacturer(conn: sqlite3.Connection, name: str) -> int:
    conn.execute("INSERT OR IGNORE INTO manufacturers (name) VALUES (?)", (name,))
    row = conn.execute(
        "SELECT id FROM manufacturers WHERE name = ?", (name,)
    ).fetchone()
    assert row is not None
    return row[0]


# ---------------------------------------------------------------------------
# Document inserts


def _insert_documents(conn: sqlite3.Connection, documents: list[Source]) -> None:
    for s in documents:
        d = s.doc
        with _integrity_context(s.path):
            cur = conn.execute(
                "INSERT INTO documents "
                "(issuer_id, doc_kind, code, slug, title) VALUES (?, ?, ?, ?, ?)",
                (
                    _issuer_id(conn, d["issuer"]),
                    d["doc_kind"],
                    d["code"],
                    d["slug"],
                    d.get("title"),
                ),
            )
            doc_id = cur.lastrowid
            for r in d["revisions"]:
                source, notes = _provenance(r)
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


def _document_id(conn: sqlite3.Connection, issuer: str, slug: str) -> int | None:
    row = conn.execute(
        "SELECT d.id FROM documents d JOIN issuers i ON i.id = d.issuer_id "
        "WHERE i.code = ? AND d.slug = ?",
        (issuer, slug),
    ).fetchone()
    return row[0] if row else None


def _resolve_alias_versions(
    label: str,
    versions: list[dict],
    ordinal_of: dict[str, int],
) -> list[dict]:
    """Return versions in revision order with `same_as_designator` resolved.

    Each returned dict carries the resolved `text` plus the original
    `same_as_designator` so the DB can record both.
    """
    items: list[tuple[int, dict]] = []
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
    out: list[dict] = []
    for ordinal, v in items:
        if "text" in v:
            text = v["text"]
            same_as = None
        else:
            target = v["same_as_designator"]
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


def _insert_provisions(conn: sqlite3.Connection, provisions: list[Source]) -> None:
    for s in provisions:
        p = s.doc
        label = f"{p['issuer']}/{p['document']}/{p['number']}"
        doc_id = _document_id(conn, p["issuer"], p["document"])
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

        with _integrity_context(s.path):
            cur = conn.execute(
                "INSERT INTO provisions "
                "(document_id, number, sort_key, canonical_title, "
                " current_grouping, subject_group) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    doc_id,
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
                source, notes = _provenance(v)
                same_as = v["same_as_designator"]
                pv_cur = conn.execute(
                    "INSERT INTO provision_versions "
                    "(document_id, provision_id, revision_id, grouping_at_time, "
                    " title_at_revision, text, same_as_version_id, "
                    " publication_cite, source_url, provenance, provenance_notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        doc_id,
                        prov_id,
                        revisions[v["designator"]][0],
                        v.get("grouping_at_time"),
                        v["title_at_revision"],
                        v["text"],
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


# ---------------------------------------------------------------------------
# Cert-basis resolution


@dataclass
class DocIndex:
    """In-memory view of one document, for resolving cert-basis refs."""

    document_id: int
    provisions: dict[str, int] = field(default_factory=dict)  # number -> id
    revisions: dict[str, tuple[int, int]] = field(
        default_factory=dict
    )  # designator -> (id, ordinal)
    # provision id -> [(ordinal, revision id, provision version id)]
    versions: dict[int, list[tuple[int, int, int]]] = field(default_factory=dict)
    numbers: dict[int, str] = field(default_factory=dict)  # provision id -> number

    def pick(self, provision_id: int, to_ordinal: int, skip: set[int]) -> int | None:
        """Version of a provision in force at `to`, ignoring skipped revisions."""
        best: tuple[int, int] | None = None
        for ordinal, rev_id, pv_id in self.versions.get(provision_id, []):
            if ordinal <= to_ordinal and rev_id not in skip:
                if best is None or ordinal > best[0]:
                    best = (ordinal, pv_id)
        return best[1] if best else None


def _doc_index(conn: sqlite3.Connection, document_id: int) -> DocIndex:
    idx = DocIndex(document_id)
    for pid, number in conn.execute(
        "SELECT id, number FROM provisions WHERE document_id = ?", (document_id,)
    ):
        idx.provisions[number] = pid
        idx.numbers[pid] = number
    for rid, designator, ordinal in conn.execute(
        "SELECT id, designator, ordinal FROM document_revisions WHERE document_id = ?",
        (document_id,),
    ):
        idx.revisions[designator] = (rid, ordinal)
    for pid, ordinal, rid, pv_id in conn.execute(
        "SELECT pv.provision_id, dr.ordinal, dr.id, pv.id "
        "FROM provision_versions pv "
        "JOIN document_revisions dr ON dr.id = pv.revision_id "
        "WHERE pv.document_id = ?",
        (document_id,),
    ):
        idx.versions.setdefault(pid, []).append((ordinal, rid, pv_id))
    return idx


@dataclass(frozen=True)
class Ref:
    """A cert-basis ref with designators and numbers resolved to ids."""

    ref_id: int
    effect: str
    doc: DocIndex
    to_ordinal: int | None
    skip: frozenset[int]  # revision ids
    provisions: tuple[int, ...]  # provision ids; empty = whole document
    paragraph: str | None


def _insert_ref(
    conn: sqlite3.Connection,
    entry_id: int,
    seq: int,
    ref: dict,
    doc_indexes: dict[tuple[str, str], DocIndex],
    label: str,
) -> tuple[Ref | None, list[str]]:
    """Insert one ref and its children. Return it resolved, or the errors."""
    where = f"{label} ref {seq}"
    key = (ref["issuer"], ref["document"])
    if key not in doc_indexes:
        doc_id = _document_id(conn, *key)
        if doc_id is None:
            return None, [f"{where}: unknown document {key[0]}/{key[1]}"]
        doc_indexes[key] = _doc_index(conn, doc_id)
    doc = doc_indexes[key]

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
    for number in ref.get("provisions", []):
        pid = doc.provisions.get(number)
        if pid is None:
            errors.append(f"{where}: unknown provision {key[1]}.{number}")
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


@dataclass(frozen=True)
class Resolved:
    provision_version_id: int
    ref_id: int
    paragraph: str | None


def resolve_entry(refs: list[Ref], label: str) -> tuple[list[Resolved], list[str]]:
    """Apply the resolution rules to the refs of one cert-basis entry.

    1. An include ref selects, for each provision in scope (its `provisions`,
       or the whole document), the version at the highest revision <= `to`
       that is not skipped. Provisions with no such version are out.
    2. Scoped results (refs with `provisions`) override wide ones.
    3. Paragraph refs add a row, unless they land on the whole-provision version.
    4. Exclude refs remove provisions from the wide results.
    Anything ambiguous is an error, not a guess.
    """
    errors: list[str] = []
    wide: dict[int, Resolved] = {}
    scoped: dict[int, Resolved] = {}
    paragraphs: list[tuple[int, Resolved]] = []
    excluded: set[int] = set()

    def name(ref: Ref, pid: int) -> str:
        return f"{ref.doc.numbers[pid]}"

    for ref in refs:
        if ref.effect != "include":
            continue
        assert ref.to_ordinal is not None
        scope = ref.provisions or tuple(ref.doc.numbers)
        picked = {
            pid: pv
            for pid in scope
            if (pv := ref.doc.pick(pid, ref.to_ordinal, set(ref.skip))) is not None
        }
        if not picked:
            errors.append(f"{label}: ref {ref.ref_id} resolves to no provisions")
            continue
        for pid, pv in picked.items():
            row = Resolved(pv, ref.ref_id, ref.paragraph)
            if ref.paragraph is not None:
                paragraphs.append((pid, row))
                continue
            target = scoped if ref.provisions else wide
            prior = target.get(pid)
            if prior is not None and prior.provision_version_id != pv:
                kind = "scoped" if ref.provisions else "document-wide"
                errors.append(
                    f"{label}: two {kind} refs resolve {name(ref, pid)} "
                    f"to different versions"
                )
            target.setdefault(pid, row)

    for ref in refs:
        if ref.effect != "exclude":
            continue
        for pid in ref.provisions:
            if pid in scoped or any(p == pid for p, _ in paragraphs):
                errors.append(
                    f"{label}: {name(ref, pid)} is both excluded and included"
                )
            elif pid not in wide:
                errors.append(f"{label}: exclude of {name(ref, pid)} removes nothing")
            excluded.add(pid)

    whole = {pid: r for pid, r in wide.items() if pid not in excluded}
    whole.update(scoped)
    out: dict[int, Resolved] = {r.provision_version_id: r for r in whole.values()}
    for pid, row in paragraphs:
        if pid in whole and whole[pid].provision_version_id == row.provision_version_id:
            continue
        if row.provision_version_id in out:
            errors.append(
                f"{label}: two paragraph refs resolve to the same version of "
                f"provision id {pid}"
            )
            continue
        out[row.provision_version_id] = row
    return list(out.values()), errors


# ---------------------------------------------------------------------------
# Aircraft inserts


def _tcds_id(conn: sqlite3.Connection, tcds_doc: dict, path: Path) -> int:
    """Insert a TCDS once; a repeat must carry identical metadata."""
    issuer_id = _issuer_id(conn, tcds_doc["issuer"])
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


def _insert_aircraft(conn: sqlite3.Connection, aircraft: list[Source]) -> list[str]:
    failures: list[str] = []
    doc_indexes: dict[tuple[str, str], DocIndex] = {}
    for s in aircraft:
        doc = s.doc
        with _integrity_context(s.path):
            cur = conn.execute(
                "INSERT INTO aircraft_models "
                "(manufacturer_id, model_designation, common_name, notes) "
                "VALUES (?, ?, ?, ?)",
                (
                    _upsert_manufacturer(conn, doc["manufacturer"]),
                    doc["model_designation"],
                    doc.get("common_name"),
                    doc.get("notes"),
                ),
            )
            model_id = cur.lastrowid
            for cat_code in doc["categories"]:
                conn.execute(
                    "INSERT INTO model_categories (model_id, category_id) "
                    "VALUES (?, ?)",
                    (model_id, _category_id(conn, cat_code)),
                )

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
                    for seq, ref in enumerate(entry["references"]):
                        r, errs = _insert_ref(
                            conn, entry_id, seq, ref, doc_indexes, label
                        )
                        failures.extend(errs)
                        if r is not None:
                            refs.append(r)
                    rows, errs = resolve_entry(refs, label)
                    failures.extend(errs)
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


# ---------------------------------------------------------------------------
# Post-insert checks, build info & report


# (table, column) pairs holding dates. A date after the build day is a parse
# error upstream (e.g. a two-digit year read as 2064), never real data.
_DATE_COLUMNS = (
    ("document_revisions", "effective_date"),
    ("version_actions", "issued_on"),
    ("tcds", "revision_date"),
)


def _future_dates(conn: sqlite3.Connection, today: str) -> list[str]:
    errors: list[str] = []
    for table, column in _DATE_COLUMNS:
        # Identifiers come from the constant above, never from data.
        n, sample = conn.execute(
            f"SELECT count(*), min({column}) FROM {table} WHERE {column} > ?",
            (today,),
        ).fetchone()
        if n:
            errors.append(
                f"{table}.{column}: {n} date(s) after {today} (e.g. {sample})"
            )
    return errors


def _git_sha(data_dir: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(data_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


# TypedDict rather than dataclass: keeps the return dict-serialisable for the report.
class BuildReport(TypedDict):
    schema_version: int
    tables: dict[str, int]
    text_missing: int
    provenance: dict[str, int]
    unresolved_references: list[str]


def _build_report(conn: sqlite3.Connection, unresolved: list[str]) -> BuildReport:
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    # Table names come from sqlite_master, not from data.
    counts = {
        t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "tables": counts,
        "text_missing": conn.execute(
            "SELECT count(*) FROM provision_versions WHERE text_missing"
        ).fetchone()[0],
        "provenance": dict(
            conn.execute(
                "SELECT provenance, count(*) FROM provision_versions "
                "GROUP BY provenance ORDER BY provenance"
            ).fetchall()
        ),
        "unresolved_references": unresolved,
    }


def _remove_sqlite_file(path: Path) -> None:
    """Remove a DB and any sidecars, including stale WAL ones from old builds."""
    path.unlink(missing_ok=True)
    for suffix in ("-journal", "-wal", "-shm"):
        path.with_name(path.name + suffix).unlink(missing_ok=True)


def build(data_dir: Path, out_path: Path) -> BuildReport:
    """Validate, build SQLite, atomically write. Raise BuildError on failure."""
    validation_errors = validate_data_dir(data_dir)
    if validation_errors:
        raise BuildError([str(e) for e in validation_errors])

    documents = _load_documents(data_dir)
    provisions = _load_provisions(data_dir)
    aircraft = _load_aircraft(data_dir)
    path_errors = _check_paths(documents, provisions)
    if path_errors:
        raise BuildError(path_errors)

    tmp = out_path.with_suffix(out_path.suffix + ".new")
    _remove_sqlite_file(tmp)

    conn = sqlite3.connect(tmp)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION:d}")
        conn.execute(
            "INSERT INTO build_info (id, schema_version, git_sha, built_at) "
            "VALUES (1, ?, ?, ?)",
            (
                SCHEMA_VERSION,
                _git_sha(data_dir),
                datetime.now(UTC).isoformat(timespec="seconds"),
            ),
        )
        _seed_lookups(conn)
        _insert_documents(conn, documents)
        _insert_provisions(conn, provisions)
        unresolved = _insert_aircraft(conn, aircraft)
        date_errors = _future_dates(conn, date.today().isoformat())
        if date_errors:
            raise BuildError(date_errors)
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            raise BuildError([f"foreign key violation: {r}" for r in fk_errors])
        report = _build_report(conn, unresolved)
        conn.commit()
    except Exception:
        conn.close()
        _remove_sqlite_file(tmp)
        raise
    conn.close()

    if unresolved:
        _remove_sqlite_file(tmp)
        raise BuildError(unresolved)

    for suffix in ("-wal", "-shm"):
        out_path.with_name(out_path.name + suffix).unlink(missing_ok=True)
    tmp.replace(out_path)

    report_path = out_path.with_name(out_path.stem + "_report.json")
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "data",
        help="Path to the data directory (default: ./data)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "cert_basis.sqlite",
        help="Output SQLite path (default: ./cert_basis.sqlite)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate only; do not build SQLite.",
    )
    args = parser.parse_args(argv)

    if args.check:
        errors = validate_data_dir(args.data_dir)
        if errors:
            for e in errors:
                print(e, file=sys.stderr)
            print(f"\n{len(errors)} validation error(s).", file=sys.stderr)
            return 1
        print(f"OK: {args.data_dir} validates clean.", file=sys.stderr)
        return 0

    try:
        report = build(args.data_dir, args.out)
    except BuildError as exc:
        for line in exc.errors:
            print(line, file=sys.stderr)
        print(f"\nBuild failed ({len(exc.errors)} error(s)).", file=sys.stderr)
        return 1

    t = report["tables"]
    print(
        f"OK: wrote {args.out} (schema v{SCHEMA_VERSION}, "
        f"documents={t['documents']}, revisions={t['document_revisions']}, "
        f"provision_versions={t['provision_versions']}, "
        f"text_missing={report['text_missing']}, "
        f"models={t['aircraft_models']}, entries={t['cert_basis_entries']}, "
        f"resolved={t['cert_basis_resolved']})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
