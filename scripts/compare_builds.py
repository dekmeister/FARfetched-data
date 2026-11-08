"""Compare what the committed build code and the working-tree build code
make of the same data/.

This checks a code change, not a data change. Both builds read the current
data/ (new or edited data included), so they agree unless the build code
changed behaviour. A refactor must report "identical". A deliberate
behaviour change shows, per table, exactly which rows moved: check that only
the intended ones did.

    uv run python scripts/compare_builds.py            # HEAD vs working tree
    uv run python scripts/compare_builds.py --ref HEAD~3
    uv run python scripts/compare_builds.py --baseline old.sqlite

`build_info` (timestamp, git sha) is ignored. Exit status: 0 identical,
1 different, 2 a build failed.
"""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IGNORED_TABLES = frozenset({"build_info"})

Row = tuple[object, ...]


def table_rows(db: Path) -> dict[str, Counter[Row]]:
    """Every row of every table (but IGNORED_TABLES), as a multiset."""
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        tables = [
            name
            for (name,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
            )
            if name not in IGNORED_TABLES
        ]
        # Table names come from sqlite_master, not from data.
        return {t: Counter(conn.execute(f"SELECT * FROM {t}")) for t in tables}


def schema_sql(db: Path) -> list[str]:
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        return sorted(
            sql
            for (sql,) in conn.execute(
                "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL"
            )
        )


def diff_dbs(old: Path, new: Path, limit: int = 5) -> list[str]:
    """Human-readable differences between two builds; empty when identical."""
    out: list[str] = []
    if schema_sql(old) != schema_sql(new):
        out.append("schema (DDL) differs")
    a, b = table_rows(old), table_rows(new)
    for t in sorted(a.keys() | b.keys()):
        if t not in a or t not in b:
            out.append(f"{t}: only in {'new' if t in b else 'old'} build")
            continue
        if a[t] == b[t]:
            continue
        removed = a[t] - b[t]
        added = b[t] - a[t]
        out.append(
            f"{t}: {sum(removed.values())} row(s) removed, {sum(added.values())} added"
        )
        for sign, rows in (("-", removed), ("+", added)):
            for r in sorted(rows.elements(), key=repr)[:limit]:
                out.append(f"  {sign} {r!r}")
    return out


def _build(code_dir: Path, data_dir: Path, out: Path) -> bool:
    proc = subprocess.run(
        [sys.executable, str(code_dir / "build.py")]
        + ["--data-dir", str(data_dir), "--out", str(out)],
        cwd=code_dir,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"build in {code_dir} failed:\n{proc.stderr}", file=sys.stderr)
    return proc.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--ref", default="HEAD", help="git ref of the old code")
    parser.add_argument(
        "--baseline", type=Path, help="an already built old DB (skips --ref)"
    )
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data")
    parser.add_argument("--limit", type=int, default=5, help="rows shown per side")
    args = parser.parse_args(argv)
    data_dir = args.data_dir.resolve()

    with tempfile.TemporaryDirectory(prefix="compare_builds_") as tmp:
        work = Path(tmp)
        old = args.baseline
        if old is None:
            tree = work / "old"
            subprocess.run(
                ["git", "-C", str(REPO_ROOT), "worktree", "add", "--detach"]
                + ["--quiet", str(tree), args.ref],
                check=True,
            )
            try:
                old = work / "old.sqlite"
                if not _build(tree, data_dir, old):
                    return 2
            finally:
                subprocess.run(
                    ["git", "-C", str(REPO_ROOT), "worktree", "remove", "--force"]
                    + [str(tree)],
                    check=True,
                )
        new = work / "new.sqlite"
        if not _build(REPO_ROOT, data_dir, new):
            return 2
        differences = diff_dbs(old, new, args.limit)

    if differences:
        print("\n".join(differences))
        return 1
    print(f"identical: {args.baseline or args.ref} and working tree on {data_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
