"""Compile FARfetched-data JSON sources into cert_basis.sqlite.

Currently implements validation only. SQLite emission comes next.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).parent
SCHEMAS_DIR = REPO_ROOT / "schemas"


@dataclass(frozen=True)
class ValidationError:
    path: Path
    message: str
    location: str

    def __str__(self) -> str:
        where = f" at {self.location}" if self.location else ""
        return f"{self.path}:{where} {self.message}"


@cache
def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS_DIR / f"{name}.schema.json").read_text())
    return Draft202012Validator(schema, format_checker=FormatChecker())


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


def validate_regulation_file(path: Path) -> list[ValidationError]:
    return _validate(path, "regulation")


def validate_aircraft_file(path: Path) -> list[ValidationError]:
    return _validate(path, "aircraft")


def validate_data_dir(data_dir: Path) -> list[ValidationError]:
    errors: list[ValidationError] = []
    regs_dir = data_dir / "regulations"
    if regs_dir.is_dir():
        for p in sorted(regs_dir.rglob("*.json")):
            errors.extend(validate_regulation_file(p))
    aircraft_dir = data_dir / "aircraft"
    if aircraft_dir.is_dir():
        for p in sorted(aircraft_dir.glob("*.json")):
            errors.extend(validate_aircraft_file(p))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "data",
        help="Path to the data directory (default: ./data)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate only; do not build SQLite (currently the only mode)",
    )
    args = parser.parse_args(argv)

    errors = validate_data_dir(args.data_dir)
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        print(f"\n{len(errors)} validation error(s).", file=sys.stderr)
        return 1

    print(f"OK: {args.data_dir} validates clean.", file=sys.stderr)
    if not args.check:
        print("(SQLite build not yet implemented.)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
