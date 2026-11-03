"""Compile FARfetched-data JSON sources into cert_basis.sqlite."""

from __future__ import annotations

import argparse
import json
import math
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
SCHEMA_VERSION = 5

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
    provenance       TEXT NOT NULL CHECK (provenance IN ('scraped', 'ocr')),
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
    text               TEXT,
    -- 1 = the revision deleted the provision; such a version has no text.
    deleted            INTEGER NOT NULL DEFAULT 0 CHECK (deleted IN (0, 1)),
    text_missing       INTEGER GENERATED ALWAYS AS
                           (IFNULL(text = 'TEXT MISSING', 0)) VIRTUAL,
    same_as_version_id INTEGER,
    publication_cite   TEXT,
    source_url         TEXT,
    provenance         TEXT NOT NULL CHECK (provenance IN ('scraped', 'ocr')),
    provenance_notes   TEXT,
    UNIQUE (provision_id, revision_id),
    UNIQUE (provision_id, id),
    FOREIGN KEY (document_id, provision_id)
        REFERENCES provisions (document_id, id),
    FOREIGN KEY (document_id, revision_id)
        REFERENCES document_revisions (document_id, id),
    FOREIGN KEY (provision_id, same_as_version_id)
        REFERENCES provision_versions (provision_id, id),
    CHECK (same_as_version_id IS NULL OR same_as_version_id <> id),
    CHECK ((deleted = 1) = (text IS NULL)),
    CHECK (deleted = 0 OR same_as_version_id IS NULL)
) STRICT;

CREATE INDEX idx_pv_revision ON provision_versions (revision_id);

-- A version's text split into blocks (docs/DATA_FORMAT.md §Text format). Every version
-- that has text has rows; a flat (single-line) text is one unlabelled row.
CREATE TABLE provision_paragraphs (
    id                   INTEGER PRIMARY KEY,
    provision_version_id INTEGER NOT NULL REFERENCES provision_versions(id),
    seq                  INTEGER NOT NULL CHECK (seq >= 0),
    depth                INTEGER NOT NULL CHECK (depth >= 0),
    label                TEXT,
    path                 TEXT,
    text                 TEXT NOT NULL,
    UNIQUE (provision_version_id, seq),
    CHECK ((depth = 0) = (path IS NULL)),
    CHECK (label IS NULL OR depth >= 1)
) STRICT;

CREATE INDEX idx_pp_path ON provision_paragraphs (provision_version_id, path);

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

-- Build-computed text similarity between provisions (docs/SQLITE.md §Similarity).
-- Directed: the best matches *for* provision_id, ranked within each document
-- of similar_provision_id. Computed, never hand-checked.
CREATE TABLE provision_similarity (
    provision_id         INTEGER NOT NULL REFERENCES provisions(id),
    similar_provision_id INTEGER NOT NULL REFERENCES provisions(id),
    rank                 INTEGER NOT NULL CHECK (rank >= 1),
    score                INTEGER NOT NULL CHECK (score BETWEEN 1 AND 1000),
    PRIMARY KEY (provision_id, similar_provision_id),
    CHECK (provision_id <> similar_provision_id)
) STRICT, WITHOUT ROWID;

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
# Provision text format: "label-line text" (docs/DATA_FORMAT.md §Text format)
#
# A text with one line is flat. A text with several lines is structured: one
# block per line; a line may open with a label group such as `(a)`, `[(4)` or
# `(c)(1)`. Depth comes from the labels (a style stack); indentation picks
# between the readings the labels allow and must agree with the chosen one.
# Indentation is always compared with other lines, never with a fixed width.

_LABEL_GROUP_RE = re.compile(r"(\[ ?)?((?:\([A-Za-z0-9]{1,5}\))+)(?= |$)")
_LABEL_TOKEN_RE = re.compile(r"\(([A-Za-z0-9]{1,5})\)")
_ROMAN_DIGITS = {"i": 1, "v": 5, "x": 10}
# Lower to upper bound of roman labels: i..xxxix. `l`, `c`, `d`, `m` are
# letters, never numerals.
_MAX_ROMAN = 39


def _roman_value(token: str) -> int | None:
    s = token.lower()
    if not s or any(ch not in _ROMAN_DIGITS for ch in s):
        return None
    total = 0
    for i, ch in enumerate(s):
        v = _ROMAN_DIGITS[ch]
        nxt = _ROMAN_DIGITS[s[i + 1]] if i + 1 < len(s) else 0
        total += -v if v < nxt else v
    if not 1 <= total <= _MAX_ROMAN or _to_roman(total) != s:
        return None
    return total


def _to_roman(n: int) -> str:
    out = ""
    for value, digits in ((10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while n >= value:
            out += digits
            n -= value
    return out


def label_values(token: str) -> dict[str, int]:
    """Every style a label token can be read in, with its value in that style.

    Styles: `lower_alpha` (a..z, then aa, bb, ...), `number`, `lower_roman`
    (i..xxxix), `upper_alpha`, `upper_roman`. An empty result means the token
    is not a label (e.g. `(OEI)`), so its line is unlabelled.
    """
    out: dict[str, int] = {}
    if token.isdigit() and not token.startswith("0"):
        out["number"] = int(token)
    if re.fullmatch(r"([a-z])\1*", token):
        out["lower_alpha"] = 26 * (len(token) - 1) + ord(token[0]) - ord("a") + 1
    if re.fullmatch(r"([A-Z])\1*", token):
        out["upper_alpha"] = 26 * (len(token) - 1) + ord(token[0]) - ord("A") + 1
    roman = _roman_value(token)
    if roman is not None:
        out["lower_roman" if token.islower() else "upper_roman"] = roman
    return out


class TextFormatError(ValueError):
    """A provision text breaks the label-line format."""

    def __init__(self, line: int, message: str) -> None:
        self.line = line
        self.message = message
        super().__init__(f"line {line}: {message}")


@dataclass(frozen=True)
class Paragraph:
    """One block of a provision text, in document order."""

    seq: int
    depth: int  # 0 = top level; otherwise the number of labels in `path`
    label: str | None  # verbatim, e.g. '(ii)' or '[(4)'; None when unlabelled
    path: str | None  # '(a)(1)(ii)'; the enclosing item's path when unlabelled
    text: str  # '' for a label-only block


@dataclass(frozen=True)
class ParsedText:
    paragraphs: tuple[Paragraph, ...]
    structured: bool  # more than one line
    gaps: int  # labels that skip values, e.g. (a) then (c)


@dataclass
class _Level:
    """One open item on the style stack."""

    style: str
    value: int
    token: str
    indent: int
    inline: bool  # opened by a later token of a compound label like (c)(1)


@dataclass(frozen=True)
class _Reading:
    kind: str  # 'cont' (continue stack[level]) or 'open' (child of stack[-1])
    level: int
    style: str
    value: int
    gap: int


def _first_style(values: dict[str, int]) -> tuple[str, int]:
    """Style for a label that opens a level with no sequence to go by."""
    return min(values.items(), key=lambda kv: (kv[1], kv[0]))


def _choose(stack: list[_Level], token: str, indent: int, line: int) -> _Reading:
    values = label_values(token)
    if not stack:
        style, value = _first_style(values)
        return _Reading("open", 0, style, value, value - 1)
    readings: list[_Reading] = []
    for k, lvl in enumerate(stack):
        v = values.get(lvl.style)
        if v is not None and v > lvl.value:
            readings.append(_Reading("cont", k, lvl.style, v, v - lvl.value - 1))
    readings.extend(
        _Reading("open", len(stack), s, v, 0) for s, v in values.items() if v == 1
    )
    if not readings:
        raise TextFormatError(line, f"label ({token}) continues no open level")

    def fits(r: _Reading) -> bool:
        if r.kind == "open":
            return indent > stack[-1].indent
        lvl = stack[r.level]
        return indent > lvl.indent if lvl.inline else indent == lvl.indent

    fitting = [r for r in readings if fits(r)]
    if len(fitting) > 1:
        # Only possible next to a compound label, whose inline levels have no
        # indentation of their own. One exact value beats gaps; else fail.
        exact = [r for r in fitting if r.gap == 0]
        if len(exact) != 1:
            raise TextFormatError(line, f"label ({token}) is ambiguous")
        fitting = exact
    if not fitting:
        raise TextFormatError(
            line,
            f"indentation of label ({token}) fits none of its readings "
            f"(re-run the tools segmenter to fix the layout)",
        )
    return fitting[0]


def _path(stack: list[_Level]) -> str:
    return "".join(f"({lvl.token})" for lvl in stack)


def parse_paragraphs(text: str) -> ParsedText:
    """Split a provision text into paragraphs. Raise TextFormatError if the
    text breaks the format (docs/DATA_FORMAT.md §Text format)."""
    lines: list[tuple[int, str]] = []
    for n, raw in enumerate(text.split("\n"), 1):
        if raw == "":
            continue
        if "\t" in raw:
            raise TextFormatError(n, "tab character")
        if raw != raw.rstrip():
            raise TextFormatError(n, "trailing whitespace")
        lines.append((n, raw))
    if not lines:
        raise TextFormatError(1, "no text")
    if len(lines) == 1:
        n, raw = lines[0]
        if raw[0].isspace():
            raise TextFormatError(n, "a single-line text must not be indented")
        return ParsedText((Paragraph(0, 0, None, None, raw),), False, 0)

    stack: list[_Level] = []
    out: list[Paragraph] = []
    gaps = 0
    for n, raw in lines:
        content = raw.lstrip(" ")
        indent = len(raw) - len(content)
        if content[0].isspace():
            raise TextFormatError(n, "indentation must be spaces")
        m = _LABEL_GROUP_RE.match(content)
        tokens = _LABEL_TOKEN_RE.findall(m.group(2)) if m else []
        if not (m and all(label_values(t) for t in tokens)):
            # Rule 5: the innermost open item whose label line is indented less.
            k = next(
                (i for i in range(len(stack) - 1, -1, -1) if stack[i].indent < indent),
                -1,
            )
            owner = stack[: k + 1]
            out.append(
                Paragraph(len(out), len(owner), None, _path(owner) or None, content)
            )
            continue
        assert m is not None
        body = content[m.end() :]
        body = body[1:] if body.startswith(" ") else body
        r = _choose(stack, tokens[0], indent, n)
        del stack[r.level :]
        stack.append(_Level(r.style, r.value, tokens[0], indent, False))
        gaps += 1 if r.gap else 0
        for tok in tokens[1:]:
            # A later token of a compound label is a child of the one before.
            style, value = _first_style(label_values(tok))
            stack.append(_Level(style, value, tok, indent, True))
            gaps += 1 if value != 1 else 0
        for i, tok in enumerate(tokens):
            depth = len(stack) - len(tokens) + i + 1
            out.append(
                Paragraph(
                    len(out),
                    depth,
                    ((m.group(1) or "") if i == 0 else "") + f"({tok})",
                    _path(stack[:depth]),
                    body if i == len(tokens) - 1 else "",
                )
            )
    return ParsedText(tuple(out), True, gaps)


def flatten_text(text: str) -> str:
    """A text's words without its layout: lines stripped and joined by single
    spaces. Structuring may change a text only where this stays equal."""
    return " ".join(s for line in text.split("\n") if (s := line.strip()))


def paragraph_ref_paths(qualifier: str, paths: set[str]) -> list[str] | None:
    """Match a verbatim cert-basis `paragraph` qualifier against a version's
    paragraph paths. Return the tokens that match no path, or None when the
    qualifier isn't a run of `(x)` tokens at all.

    A qualifier lists paragraphs the way TCDSs write them: `(a)(1)(2)(b)` is
    (a)(1), (a)(2) and (b). Each token descends into the current paragraph or
    names a sibling of it or of one of its ancestors. `(c3)` is read as
    `(c)(3)`.
    """
    if re.sub(r"\([A-Za-z0-9]+\)|\s", "", qualifier):
        return None
    tokens: list[str] = []
    for tok in re.findall(r"\(([A-Za-z0-9]+)\)", qualifier):
        m = re.fullmatch(r"([a-z])(\d+)", tok)
        tokens.extend(m.groups() if m else [tok])
    cur: list[str] = []
    unmatched: list[str] = []
    for tok in tokens:
        for k in range(len(cur), -1, -1):
            cand = cur[:k] + [tok]
            if "".join(f"({t})" for t in cand) in paths:
                cur = cand
                break
        else:
            unmatched.append(f"({tok})")
    return unmatched


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

    Each returned dict carries the resolved `text` (None for a deleted version)
    plus the original `same_as_designator` so the DB can record both. A
    deletion must follow a live version, and an alias must not target a
    deleted one.
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
    deleted_designators: set[str] = set()
    out: list[dict] = []
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
    errors: list[str] = field(default_factory=list)


def check_text(label: str, designator: str, text: str) -> ParsedText | str:
    """Parse one version's text; return the parse or an error message."""
    try:
        return parse_paragraphs(text)
    except TextFormatError as exc:
        return f"Provision {label} version '{designator}': text {exc}"


def check_text_format(data_dir: Path) -> list[str]:
    """Format errors in every provision text under data_dir (for --check)."""
    errors: list[str] = []
    for s in _load_provisions(data_dir):
        p = s.doc
        label = f"{p['issuer']}/{p['document']}/{p['number']}"
        for v in p.get("versions", []):
            if isinstance(v.get("text"), str):
                res = check_text(label, v.get("designator", "?"), v["text"])
                if isinstance(res, str):
                    errors.append(f"{s.path}: {res}")
    return errors


def _insert_paragraphs(
    conn: sqlite3.Connection, pv_id: int, parsed: ParsedText
) -> None:
    conn.executemany(
        "INSERT INTO provision_paragraphs "
        "(provision_version_id, seq, depth, label, path, text) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [(pv_id, p.seq, p.depth, p.label, p.path, p.text) for p in parsed.paragraphs],
    )


def _insert_provisions(conn: sqlite3.Connection, provisions: list[Source]) -> TextStats:
    """Insert provisions and versions. Text-format errors are collected over
    every file and raised together, so one run lists all of them."""
    stats = TextStats()
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
            parsed_by_text: dict[str, ParsedText] = {}
            for v in resolved:
                source, notes = _provenance(v)
                same_as = v["same_as_designator"]
                pv_cur = conn.execute(
                    "INSERT INTO provision_versions "
                    "(document_id, provision_id, revision_id, grouping_at_time, "
                    " title_at_revision, text, deleted, same_as_version_id, "
                    " publication_cite, source_url, provenance, provenance_notes) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        doc_id,
                        prov_id,
                        revisions[v["designator"]][0],
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
                parsed = parsed_by_text.get(v["text"])
                if parsed is None:
                    res = check_text(label, v["designator"], v["text"])
                    if isinstance(res, str):
                        if same_as is None:
                            stats.errors.append(f"{s.path}: {res}")
                        continue
                    parsed = parsed_by_text[v["text"]] = res
                _insert_paragraphs(conn, pv_id, parsed)
                if same_as is None:  # an alias is counted as its target
                    stats.structured += parsed.structured
                    stats.flat += not parsed.structured
                    stats.label_gaps += parsed.gaps
    return stats


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
    deleted: set[int] = field(default_factory=set)  # deleted provision version ids

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
    for pid, ordinal, rid, pv_id, deleted in conn.execute(
        "SELECT pv.provision_id, dr.ordinal, dr.id, pv.id, pv.deleted "
        "FROM provision_versions pv "
        "JOIN document_revisions dr ON dr.id = pv.revision_id "
        "WHERE pv.document_id = ?",
        (document_id,),
    ):
        idx.versions.setdefault(pid, []).append((ordinal, rid, pv_id))
        if deleted:
            idx.deleted.add(pv_id)
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
       that is not skipped. Provisions with no such version are out, and so
       are provisions whose selected version deleted them (document-wide refs
       only: a scoped or paragraph ref to a deleted provision is an error).
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
        gone = [pid for pid, pv in picked.items() if pv in ref.doc.deleted]
        for pid in gone:
            del picked[pid]
        if ref.provisions and gone:
            errors.extend(
                f"{label}: ref {ref.ref_id} resolves {name(ref, pid)} to a "
                f"revision that deleted it"
                for pid in gone
            )
            continue
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
                "SELECT p.number, dr.designator FROM provision_versions pv "
                "JOIN provisions p ON p.id = pv.provision_id "
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


def _insert_aircraft(
    conn: sqlite3.Connection, aircraft: list[Source], para_stats: ParagraphRefStats
) -> list[str]:
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
    postings: dict[str, list[tuple[int, float]]] = {}
    for pid, vec in vectors.items():
        for term, weight in vec.items():
            postings.setdefault(term, []).append((pid, weight))

    floor = round(SIMILARITY_MIN_SCORE * 1000)
    rows: list[tuple[int, int, int, int]] = []
    for pid in sorted(vectors):
        scores: dict[int, float] = {}
        for term, weight in vectors[pid].items():
            for other, other_weight in postings[term]:
                scores[other] = scores.get(other, 0.0) + weight * other_weight
        scores.pop(pid, None)
        per_doc: dict[int, list[tuple[int, tuple[str, str], int]]] = {}
        for other, score in scores.items():
            score_int = min(1000, round(score * 1000))
            if score_int < floor:
                continue
            src = by_id[other]
            per_doc.setdefault(src.document_id, []).append(
                (-score_int, src.order, other)
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
            text=flatten_text(text),
        )
        for pid, doc_id, doc_code, key, grouping, canonical, text in latest
        if text is not None
    ]


def _insert_similarity(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO provision_similarity "
        "(provision_id, similar_provision_id, rank, score) VALUES (?, ?, ?, ?)",
        compute_similarity(_similarity_sources(conn)),
    )


def _similarity_report(conn: sqlite3.Connection) -> dict[str, int]:
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


# TypedDict rather than dataclass: keeps the return dict-serialisable for the report.
class BuildReport(TypedDict):
    schema_version: int
    tables: dict[str, int]
    text_missing: int
    deleted: int
    provenance: dict[str, int]
    structured_versions: int
    flat_versions: int
    label_gaps: int
    paragraph_refs_verified: int
    paragraph_refs_unverifiable: int
    similarity: dict[str, int]
    unresolved_references: list[str]


def _build_report(
    conn: sqlite3.Connection,
    unresolved: list[str],
    text_stats: TextStats,
    para_stats: ParagraphRefStats,
) -> BuildReport:
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
        "deleted": conn.execute(
            "SELECT count(*) FROM provision_versions WHERE deleted"
        ).fetchone()[0],
        "provenance": dict(
            conn.execute(
                "SELECT provenance, count(*) FROM provision_versions "
                "GROUP BY provenance ORDER BY provenance"
            ).fetchall()
        ),
        "structured_versions": text_stats.structured,
        "flat_versions": text_stats.flat,
        "label_gaps": text_stats.label_gaps,
        "paragraph_refs_verified": para_stats.verified,
        "paragraph_refs_unverifiable": para_stats.unverifiable,
        "similarity": _similarity_report(conn),
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
        text_stats = _insert_provisions(conn, provisions)
        if text_stats.errors:
            raise BuildError(text_stats.errors)
        _insert_similarity(conn)
        para_stats = ParagraphRefStats()
        unresolved = _insert_aircraft(conn, aircraft, para_stats)
        date_errors = _future_dates(conn, date.today().isoformat())
        if date_errors:
            raise BuildError(date_errors)
        fk_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            raise BuildError([f"foreign key violation: {r}" for r in fk_errors])
        report = _build_report(conn, unresolved, text_stats, para_stats)
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
        help="Validate schemas and text layout only; do not build SQLite.",
    )
    args = parser.parse_args(argv)

    if args.check:
        errors: list[object] = list(validate_data_dir(args.data_dir))
        if not errors:
            errors.extend(check_text_format(args.data_dir))
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
        f"structured={report['structured_versions']}, "
        f"paragraphs={t['provision_paragraphs']}, "
        f"deleted={report['deleted']}, "
        f"similar={t['provision_similarity']}, "
        f"models={t['aircraft_models']}, entries={t['cert_basis_entries']}, "
        f"resolved={t['cert_basis_resolved']})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
