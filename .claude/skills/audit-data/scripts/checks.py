"""Structural and cross-version checks over a data tree (data/ or the staged tree).

Complements scripts/scan_data.py. scan_data looks for text-damage patterns
inside one string. These checks look at shape: a version against the one
before it, labels against their sequence, a TCDS basis line against the
references parsed from it. Each hit is a lead to read against the source,
not a verdict.

Run from the repo root (it imports certbuild.text):

    PYTHONPATH=. uv run python .claude/skills/audit-data/scripts/checks.py \
        --root data > hits.tsv
    # only hits that the staged tree adds over data/:
    PYTHONPATH=. uv run python .claude/skills/audit-data/scripts/checks.py \
        --root tools/out/staged --baseline-root data
    # restrict to some files (paths relative to --root, one per line):
    ... --paths sample_paths.txt

ROOT holds documents/ and/or aircraft/. stdout is TSV
(check, relpath, locator, detail); stderr is a count per check. Read-only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from certbuild.text import TextFormatError, parse_paragraphs, plain_text

CHECKS = {
    "text-missing": "version text is the TEXT MISSING marker",
    "format-error": "text breaks the label-line format",
    "label-gap": "paragraph labels skip a value, e.g. (a) then (c)",
    "length-drop": "text under half the previous version's (truncation?)",
    "length-jump": "text over 2.5x the previous version's (run-on?)",
    "same-as-previous": "text and title identical to the previous version",
    "short-text": "under 40 characters and not Reserved",
    "duplicate-paragraph": "the same long paragraph twice in one version",
    "no-source-url": "version without source_url (CAR scans have none)",
    "cite-suspect": "publication_cite over 80 characters or with FR filing text",
    "title-suspect": "title empty, long (not DoD), lowercase start, § or hyphen end",
    "heading-in-text": "text opens with a § / Sec. heading",
    "regulation-no-refs": "TCDS regulation line naming a data/ document, no references",
    "split-amendment": "amendment number broken by a line wrap ('23- 25')",
    "amendment-unreferenced": "an amendment named on the line is in no reference",
    "section-unreferenced": "a section cited on the line is in no reference",
    "runaway-line": "basis line over 1500 characters",
    "duplicate-line": "the same basis line twice in one TCDS",
    "no-categories": "TCDS with no categories",
}

RESERVED_RE = re.compile(r"reserved|removed|deleted", re.I)
AMDT_RE = re.compile(
    r"(?:Amendments?|Amdts?\.?|Amend\.?)\s*(?:No\.?\s*)?(\d{1,2})\s*-\s*(\d{1,3})\b"
)
SPLIT_AMDT_RE = re.compile(r"\b(?:2[3579]|36)(?:-\s+|\s+-\s*)\d{1,3}\b")
# A basis line that names a document data/ holds: 14 CFR 23/25/26/27/29/36,
# CS-23/25/27/29, CAR 3. A line naming only JAR, BCAR, Part 34, SFAR and the
# like can't have references, so `regulation-no-refs` skips it.
FOREIGN_RE = re.compile(r"\b(?:JAR|BCAR|SFAR)[-\s]?\d+(?:\.\d+)?", re.I)
DATASET_DOC_RE = re.compile(
    r"\b(?:14\s*CFR|FAR|CFR|Part)\s*(?:Pt\.?\s*|Part\s*)?(?:2[35679]|36)\b(?!\.\d)"
    r"|\bCS[-\s]?2[3579]\b"
    r"|(?<![\d.])(?:2[35679]|36)\.\d"
    r"|\bCAR\s*(?:Part\s*)?3\b",
    re.I,
)
SECTION_RE = re.compile(r"(?<![\d.])(2[3579]|36)\.(\d{1,4})(?![\d.]*\d)")


@dataclass(frozen=True)
class Hit:
    check: str
    relpath: str
    locator: str
    detail: str

    def row(self) -> str:
        cells = (self.check, self.relpath, self.locator, self.detail)
        return "\t".join(c.replace("\t", " ").replace("\n", " ⏎ ") for c in cells)


def _plain(text: str) -> str:
    try:
        return plain_text(text)
    except (TextFormatError, ValueError):
        return text


def _norm(text: str) -> str:
    return " ".join(text.split())


def _version_text_hits(rel: str, loc: str, text: str) -> Iterator[Hit]:
    if text == "TEXT MISSING":
        yield Hit("text-missing", rel, loc, "")
        return
    try:
        parsed = parse_paragraphs(text)
    except TextFormatError as exc:
        yield Hit("format-error", rel, loc, str(exc)[:200])
        return
    if parsed.gaps:
        yield Hit("label-gap", rel, loc, f"{parsed.gaps} gap(s)")
    plain = _plain(text)
    if len(plain) < 40 and not RESERVED_RE.search(plain):
        yield Hit("short-text", rel, loc, plain)
    if re.match(r"\s*\[?\s*(§|Sec\.)\s*[A-Z]?\d", text):
        yield Hit("heading-in-text", rel, loc, text[:80])
    seen: set[str] = set()
    for para in parsed.paragraphs:
        body = _norm(para.text)
        if len(body) >= 80 and para.kind == "text":
            if body in seen:
                yield Hit("duplicate-paragraph", rel, loc, body[:120])
            seen.add(body)


def _title_hits(rel: str, loc: str, title: str | None) -> Iterator[Hit]:
    t = (title or "").strip()
    too_long = len(t) > 150 and not rel.startswith("documents/dod/")
    if not t or too_long or t[0].islower() or "§" in t or t.endswith("-"):
        yield Hit("title-suspect", rel, loc, t[:160])


def _meta_hits(rel: str, loc: str, v: dict[str, Any]) -> Iterator[Hit]:
    scan = not rel.startswith(("documents/caa/", "documents/cab/"))
    if scan and not v.get("source_url"):
        yield Hit("no-source-url", rel, loc, "")
    cite = v.get("publication_cite") or ""
    if len(cite) > 80 or re.search(r"F\.\s?R\. Doc|\[SEAL\]|Secretary|Stat\.", cite):
        yield Hit("cite-suspect", rel, loc, cite[:160])


def provision_hits(rel: str, doc: dict[str, Any]) -> Iterator[Hit]:
    prev: dict[str, Any] | None = None
    for v in doc.get("versions", []):
        loc = str(v.get("designator"))
        yield from _title_hits(rel, loc, v.get("title_at_revision"))
        yield from _meta_hits(rel, loc, v)
        if v.get("deleted"):
            continue  # a deletion has no text; compare the next one to the last text
        text = v.get("text") or ""
        yield from _version_text_hits(rel, loc, text)
        if prev is not None and text != "TEXT MISSING":
            yield from _against_previous(rel, loc, prev, v)
        prev = v


def _against_previous(
    rel: str, loc: str, prev: dict[str, Any], cur: dict[str, Any]
) -> Iterator[Hit]:
    p_text, c_text = prev.get("text") or "", cur.get("text") or ""
    if p_text == "TEXT MISSING":
        return
    p_len, c_len = len(_plain(p_text)), len(_plain(c_text))
    detail = f"{prev.get('designator')} {p_len} → {c_len} chars"
    if p_len >= 400 and c_len < p_len / 2 and not RESERVED_RE.search(c_text[:200]):
        yield Hit("length-drop", rel, loc, detail)
    if p_len and c_len > 2.5 * p_len and c_len - p_len > 1500:
        yield Hit("length-jump", rel, loc, detail)
    same_title = prev.get("title_at_revision") == cur.get("title_at_revision")
    if same_title and _norm(p_text) == _norm(c_text):
        yield Hit("same-as-previous", rel, loc, f"same as {prev.get('designator')}")


def _ref_strings(refs: list[dict[str, Any]]) -> tuple[set[str], set[str]]:
    """(revision designators, provision numbers) named by the references."""
    revs: set[str] = set()
    provs: set[str] = set()
    for ref in refs:
        for k, val in ref.items():
            if k == "provisions" and isinstance(val, list):
                for p in val:
                    provs.add(re.split(r"[(\s]", str(p), maxsplit=1)[0])
            elif isinstance(val, str):
                revs.add(val)
    return revs, provs


def _line_hits(rel: str, loc: str, line: dict[str, Any]) -> Iterator[Hit]:
    raw = line.get("raw_reference") or ""
    refs = line.get("references") or []
    if len(raw) > 1500:
        yield Hit("runaway-line", rel, loc, f"{len(raw)} chars")
    if SPLIT_AMDT_RE.search(raw):
        yield Hit("split-amendment", rel, loc, raw[:160])
    if line.get("entry_type") != "regulation":
        return
    if not refs:
        if DATASET_DOC_RE.search(FOREIGN_RE.sub(" ", raw)):
            yield Hit("regulation-no-refs", rel, loc, raw[:200])
        return
    yield from _unreferenced_hits(rel, loc, raw, refs)


def _unreferenced_hits(
    rel: str, loc: str, raw: str, refs: list[dict[str, Any]]
) -> Iterator[Hit]:
    """Amendments and sections named on a line that no reference carries."""
    revs, provs = _ref_strings(refs)
    rev_text = " ".join(revs)
    for m in AMDT_RE.finditer(raw):
        a, b = m.groups()
        if re.match(r"\s*(through|thru|to)\b", raw[m.end() :]):
            continue  # the start of a range: the reference names its end
        if f"{a}-{b}" not in rev_text:
            yield Hit("amendment-unreferenced", rel, loc, f"{a}-{b}: {raw[:160]}")
    for _part, num in SECTION_RE.findall(raw):
        if provs and num not in provs:
            yield Hit("section-unreferenced", rel, loc, f"{_part}.{num}: {raw[:160]}")


def aircraft_hits(rel: str, doc: dict[str, Any]) -> Iterator[Hit]:
    for tcb in doc.get("tcb", []):
        t = tcb.get("tcds", {})
        tloc = f"{t.get('issuer')} {t.get('tcds_number')} rev {t.get('revision')}"
        if not tcb.get("categories"):
            yield Hit("no-categories", rel, tloc, "")
        seen: set[str] = set()
        for line in tcb.get("certification_basis", []):
            loc = f"{tloc} #{line.get('display_order')}"
            raw = line.get("raw_reference") or ""
            if raw in seen:
                yield Hit("duplicate-line", rel, loc, raw[:160])
            seen.add(raw)
            yield from _line_hits(rel, loc, line)


def scan(root: Path, only: set[str] | None) -> list[Hit]:
    hits: list[Hit] = []
    for sub, fn in (("documents", provision_hits), ("aircraft", aircraft_hits)):
        base = root / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.json")):
            rel = path.relative_to(root).as_posix()
            if path.name.startswith("_") or (only is not None and rel not in only):
                continue
            hits.extend(fn(rel, json.loads(path.read_text(encoding="utf-8"))))
    return hits


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--root", type=Path, default=Path("data"))
    p.add_argument(
        "--baseline-root",
        type=Path,
        help="drop hits that this tree has too (same check, file, locator, detail)",
    )
    p.add_argument("--paths", type=Path, help="file of relpaths to restrict to")
    p.add_argument("--list", action="store_true", help="list the checks")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list:
        for name, desc in CHECKS.items():
            print(f"{name:24}{desc}")
        return 0
    only = None
    if args.paths:
        only = {s.strip() for s in args.paths.read_text().splitlines() if s.strip()}
    hits = scan(args.root, only)
    if args.baseline_root:
        known = set(scan(args.baseline_root, only))
        hits = [h for h in hits if h not in known]
    for h in hits:
        print(h.row())
    counts = Counter(h.check for h in hits)
    for name in CHECKS:
        if counts[name]:
            print(f"{counts[name]:7}  {name}", file=sys.stderr)
    print(f"{len(hits):7}  total", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
