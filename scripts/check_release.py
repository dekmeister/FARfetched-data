"""Refuse to publish a build that fails the integrity checks.

Checks the SQLite file and report that `build.py` just wrote: contract version,
`quick_check`, the build's commit, a clean `data/` and no unresolved references.

These are integrity checks only. They do not show that the data matches its
sources (CLAUDE.md, "Reproducible is not correct").

    uv run python -m scripts.check_release --commit "$GITHUB_SHA"

Exit status: 0 fit to publish, 1 not.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from certbuild.ddl import SCHEMA_VERSION
from certbuild.sources import REPO_ROOT


def problems(db: Path, report_path: Path, commit: str) -> list[str]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    found: list[str] = []
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        check = conn.execute("PRAGMA quick_check").fetchone()[0]
        row = conn.execute("SELECT git_sha FROM build_info").fetchone()
    if version != SCHEMA_VERSION:
        found.append(f"user_version {version}, expected {SCHEMA_VERSION}")
    if check != "ok":
        found.append(f"quick_check: {check}")
    if row is None or row[0] != commit:
        found.append(f"built from {row[0] if row else None}, expected {commit}")
    if report["schema_version"] != SCHEMA_VERSION:
        found.append(f"report schema {report['schema_version']}")
    if report["git_dirty"] is not False:
        found.append(f"data/ not clean: {report['git_dirty_paths'][:5]}")
    if report["unresolved_references"]:
        found.append(f"{len(report['unresolved_references'])} unresolved references")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True, help="The commit being released")
    parser.add_argument("--db", type=Path, default=REPO_ROOT / "cert_basis.sqlite")
    parser.add_argument(
        "--report", type=Path, default=REPO_ROOT / "cert_basis_report.json"
    )
    args = parser.parse_args(argv)
    found = problems(args.db, args.report, args.commit)
    for problem in found:
        print(f"not fit to publish: {problem}", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
