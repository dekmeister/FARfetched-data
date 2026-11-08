"""Schema validation and loading of data/ JSON (docs/DATA_FORMAT.md)."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

from certbuild.errors import BuildError, ValidationError


REPO_ROOT = Path(__file__).parent.parent
SCHEMAS_DIR = REPO_ROOT / "schemas"


DOCUMENT_FILE = "_document.json"


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
        want = f"{s.doc['issuer'].lower()}/{s.doc['document']}/{s.doc['key']}"
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
