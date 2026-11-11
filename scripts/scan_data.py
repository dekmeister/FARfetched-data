"""Scan the JSON that goes into the database for damage we have seen before.

Malformed equations, figure captions and chart labels in the text, OCR
symbols, page headers and footers, tables of contents, headings run into a
section, words broken in two, amendatory instructions read as regulation
text. The checks, and the GitHub issue or ISSUES.md item each came from,
are in scripts/scan_checks.py (`--list` prints them).

A hit is a lead to read against the source, never a verdict: some are
faithful to the source. The baseline (scripts/scan_data_baseline.tsv) holds
the hits already known, so a run reports only what is new:

    uv run python -m scripts.scan_data                  # new hits vs baseline
    uv run python -m scripts.scan_data --all > hits.tsv # every hit
    uv run python -m scripts.scan_data --check toc-run --all
    uv run python -m scripts.scan_data --root tools/out/staged   # before promote
    uv run python -m scripts.scan_data --write-baseline # accept the current hits

Reads only; writes the baseline only with --write-baseline. TSV on stdout
(check, issuer, document, key, designator, field, match, context), a count
per check on stderr. Exit status: 0 no new hits, 1 new hits.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from certbuild.text import plain_text
from scripts.scan_checks import CHECKS, Check, Context, Field, kind

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE = REPO_ROOT / "scripts" / "scan_data_baseline.tsv"
COLUMNS = (
    "check",
    "issuer",
    "document",
    "key",
    "designator",
    "field",
    "match",
    "context",
)
# The columns that identify a hit across runs (context may shift).
IDENTITY = COLUMNS[:-1]
TEXT_MISSING = "TEXT MISSING"


@dataclass(frozen=True)
class Finding:
    check: str
    issuer: str
    document: str
    key: str
    designator: str
    field: str
    match: str
    context: str

    def row(self) -> tuple[str, ...]:
        return tuple(getattr(self, c) for c in COLUMNS)

    def identity(self) -> tuple[str, ...]:
        return tuple(getattr(self, c) for c in IDENTITY)


def provision_fields(root: Path) -> Iterator[Field]:
    for path in sorted(root.glob("documents/*/*/*.json")):
        if path.name == "_document.json":
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        for v in d["versions"]:
            where = (d["issuer"], d["document"], d["key"], v["designator"])
            yield Field(*where, "title", v["title_at_revision"])
            if "text" in v:
                yield Field(*where, "text", v["text"])


def aircraft_fields(root: Path) -> Iterator[Field]:
    aircraft = root / "aircraft"
    for path in sorted(aircraft.glob("**/*.json")):
        d = json.loads(path.read_text(encoding="utf-8"))
        model = path.relative_to(aircraft).with_suffix("").as_posix()
        for tcb in d["tcb"]:
            tcds = tcb["tcds"]
            for entry in tcb["certification_basis"]:
                yield Field(
                    tcds["issuer"],
                    tcds["tcds_number"],
                    model,
                    tcds.get("revision") or "",
                    f"basis[{entry['display_order']}]",
                    entry["raw_reference"],
                )


def build_context(fields: Sequence[Field]) -> Context:
    vocab: Counter[str] = Counter()
    for f in fields:
        if f.field == "text":
            vocab.update(re.findall(r"[a-z]+", plain_text(f.value).lower()))
    return Context(vocabulary=vocab)


def scan(fields: Sequence[Field], checks: Sequence[Check]) -> list[Finding]:
    ctx = build_context(fields)
    found: list[Finding] = []
    for f in fields:
        if f.value == TEXT_MISSING:
            continue
        for check in checks:
            if kind(f) not in check.fields:
                continue
            for h in check.run(f, ctx):
                found.append(
                    Finding(
                        check.name,
                        f.issuer,
                        f.document,
                        f.key,
                        f.designator,
                        f.field,
                        h.match,
                        h.context,
                    )
                )
    return found


def read_baseline(path: Path) -> Counter[tuple[str, ...]]:
    """Identities in the baseline, counted (one text can repeat a hit)."""
    if not path.exists():
        return Counter()
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split("\t") if lines else []
    if tuple(header) != COLUMNS:
        raise SystemExit(f"{path}: header is not {chr(9).join(COLUMNS)}")
    return Counter(tuple(line.split("\t")[: len(IDENTITY)]) for line in lines[1:])


def new_findings(
    found: Iterable[Finding], baseline: Counter[tuple[str, ...]]
) -> list[Finding]:
    left = Counter(baseline)
    new: list[Finding] = []
    for f in found:
        if left[f.identity()] > 0:
            left[f.identity()] -= 1
        else:
            new.append(f)
    return new


def clean(cell: str) -> str:
    return cell.replace("\t", " ").replace("\n", " ⏎ ").replace("\r", " ")


def write_tsv(findings: Iterable[Finding], out: TextIO) -> None:
    """Plain TSV, no quoting: cells never hold a tab or line break."""
    out.write("\t".join(COLUMNS) + "\n")
    for f in findings:
        out.write("\t".join(clean(c) for c in f.row()) + "\n")


def summary(found: Sequence[Finding], shown: Sequence[Finding]) -> str:
    total = Counter(f.check for f in found)
    new = Counter(f.check for f in shown)
    lines = [f"{'check':<22}{'hits':>7}{'reported':>10}  versions"]
    for check in CHECKS:
        versions = {
            (f.issuer, f.document, f.key, f.designator)
            for f in found
            if f.check == check.name
        }
        if total[check.name] or new[check.name]:
            lines.append(
                f"{check.name:<22}{total[check.name]:>7}{new[check.name]:>10}"
                f"  {len(versions)}"
            )
    lines.append(f"{'total':<22}{len(found):>7}{len(shown):>10}")
    return "\n".join(lines)


def list_checks() -> str:
    return "\n".join(f"{c.name:<22}{c.seen_in:<26}{c.about}" for c in CHECKS)


def select_checks(names: Sequence[str] | None) -> list[Check]:
    if not names:
        return list(CHECKS)
    known = {c.name: c for c in CHECKS}
    unknown = [n for n in names if n not in known]
    if unknown:
        raise SystemExit(f"unknown check(s): {', '.join(unknown)} (see --list)")
    return [known[n] for n in names]


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--root",
        type=Path,
        default=REPO_ROOT / "data",
        help="tree holding documents/ and aircraft/ (default: data/)",
    )
    p.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    p.add_argument(
        "--all",
        action="store_true",
        help="report every hit, not only those missing from the baseline",
    )
    p.add_argument(
        "--check",
        action="append",
        metavar="NAME",
        help="run only this check (repeatable)",
    )
    p.add_argument(
        "--write-baseline",
        action="store_true",
        help="write every hit to the baseline and exit 0",
    )
    p.add_argument("--list", action="store_true", help="list the checks")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list:
        print(list_checks())
        return 0
    checks = select_checks(args.check)
    fields = [*provision_fields(args.root), *aircraft_fields(args.root)]
    if args.write_baseline and args.check:
        raise SystemExit("--write-baseline records every check; drop --check")
    found = scan(fields, checks)
    if args.write_baseline:
        with args.baseline.open("w", encoding="utf-8", newline="") as fh:
            write_tsv(found, fh)
        print(f"wrote {len(found)} hits to {args.baseline}", file=sys.stderr)
        return 0
    shown = found if args.all else new_findings(found, read_baseline(args.baseline))
    write_tsv(shown, sys.stdout)
    print(summary(found, shown), file=sys.stderr)
    return 1 if shown and not args.all else 0


if __name__ == "__main__":
    sys.exit(main())
