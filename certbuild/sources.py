"""Reading data/: schema validation, parsing, path checks, grouping style
(docs/DATA_FORMAT.md).

Reads files only; never touches the DB except to turn an integrity error
into a BuildError naming the file (`integrity_context`).
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from certbuild.errors import BuildError, ValidationError


REPO_ROOT = Path(__file__).parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"


DOCUMENT_FILE = "_document.json"


# A parsed JSON object. Schema validation guarantees its shape (BUILD-10:
# typed records would let mypy check it too).
JsonObject = dict[str, Any]


@dataclass(frozen=True)
class Source:
    """One loaded JSON file and where it came from."""

    path: Path
    doc: JsonObject


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


def _read(path: Path, schema_name: str) -> tuple[Any, list[ValidationError]]:
    """Parse one JSON file and validate it against a schema."""
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return None, [ValidationError(path, f"invalid JSON: {exc}", "")]
    validator = _validator(schema_name)
    errors: list[ValidationError] = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        location = "/".join(str(p) for p in err.absolute_path)
        errors.append(ValidationError(path, err.message, location))
    return data, errors


def _validate(path: Path, schema_name: str) -> list[ValidationError]:
    return _read(path, schema_name)[1]


def validate_document_file(path: Path) -> list[ValidationError]:
    return _validate(path, "document")


def validate_provision_file(path: Path) -> list[ValidationError]:
    return _validate(path, "provision")


def validate_aircraft_file(path: Path) -> list[ValidationError]:
    return _validate(path, "aircraft_model")


@dataclass(frozen=True)
class DataFiles:
    """Every JSON file under data/, parsed, in sorted path order."""

    documents: list[Source]
    provisions: list[Source]
    aircraft: list[Source]


def read_data_dir(data_dir: Path) -> tuple[DataFiles, list[ValidationError]]:
    """Read, parse and validate every file once. The files are only usable
    when the error list is empty."""
    files = DataFiles([], [], [])
    errors: list[ValidationError] = []
    docs_dir = data_dir / "documents"
    if docs_dir.is_dir():
        for p in sorted(docs_dir.rglob("*.json")):
            if p.name == DOCUMENT_FILE:
                data, errs = _read(p, "document")
                files.documents.append(Source(p, data))
            else:
                data, errs = _read(p, "provision")
                files.provisions.append(Source(p, data))
            errors.extend(errs)
    aircraft_dir = data_dir / "aircraft"
    if aircraft_dir.is_dir():
        for p in sorted(aircraft_dir.rglob("*.json")):
            data, errs = _read(p, "aircraft_model")
            files.aircraft.append(Source(p, data))
            errors.extend(errs)
    return files, errors


def validate_data_dir(data_dir: Path) -> list[ValidationError]:
    return read_data_dir(data_dir)[1]


# ---------------------------------------------------------------------------
# Loaders


def _load(paths: Iterator[Path]) -> list[Source]:
    return [Source(p, json.loads(p.read_text())) for p in sorted(paths)]


def load_provisions(data_dir: Path) -> list[Source]:
    docs_dir = data_dir / "documents"
    if not docs_dir.is_dir():
        return []
    return _load(p for p in docs_dir.rglob("*.json") if p.name != DOCUMENT_FILE)


def check_paths(documents: list[Source], provisions: list[Source]) -> list[str]:
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
        want = f"{s.doc['issuer'].lower()}/{s.doc['document']}/{s.doc['key']}"
        got = f"{s.path.parent.parent.name}/{s.path.parent.name}/{s.path.stem}"
        if got != want:
            errors.append(f"{s.path}: expected at documents/{want}.json")
    return errors


# docs/DATA_FORMAT.md §Grouping labels: `{Label} — {Name}`, or a letterless
# group. A new kind of label or letterless group is added here and in the doc.
_GROUPING = re.compile(r"(Subpart [A-Z]{1,2}|Section [0-9]+) — (\S(?:.*\S)?)")
LETTERLESS_GROUPINGS = frozenset({"Appendices"})
_OTHER_SEPARATOR = re.compile(r" [\u2014\u2013-] ")


def grouping_fault(value: str | None) -> str | None:
    """Why a `current_grouping` / `grouping_at_time` value breaks the one
    grouping style, or None."""
    if value is None or value in LETTERLESS_GROUPINGS:
        return None
    m = _GROUPING.fullmatch(value)
    if m is None:
        return (
            "not `Subpart X — Name`, `Section N — Name` or one of "
            f"{sorted(LETTERLESS_GROUPINGS)} (em dash, one space either side)"
        )
    name = m.group(2)
    if "  " in value:
        return "double space"
    if _OTHER_SEPARATOR.search(name):
        return "a second separator in the name"
    if not any(c.islower() for c in name):
        return "name in capitals (use heading case)"
    return None


def check_groupings(provisions: list[Source]) -> list[str]:
    """Every grouping value in the one style (docs/DATA_FORMAT.md §Grouping
    labels). Lists each fault once per file and value."""
    errors: list[str] = []
    for s in provisions:
        values = [("current_grouping", s.doc.get("current_grouping"))]
        values += [
            (f"{v['designator']} grouping_at_time", v.get("grouping_at_time"))
            for v in s.doc["versions"]
        ]
        seen: set[str | None] = set()
        for where, value in values:
            fault = grouping_fault(value)
            if fault and value not in seen:
                seen.add(value)
                errors.append(f"{s.path}: {where} {value!r}: {fault}")
    return errors


@contextmanager
def integrity_context(path: Path) -> Iterator[None]:
    """Turn a constraint violation into a BuildError naming the source file."""
    try:
        yield
    except sqlite3.IntegrityError as exc:
        raise BuildError([f"{path}: integrity error: {exc}"]) from exc


def provenance(obj: JsonObject) -> tuple[str, str | None]:
    prov = obj.get("provenance") or {}
    return prov.get("source", "scraped"), prov.get("notes")
