"""Verify `publication_cite` values taken from a reviewed cite override.

CAR versions get their Federal Register cite from tools/overrides/car_cites.tsv
(one row per revision: designator, cite, evidence), not from the extracted
text, so the verbatim check can't find them. Each row was checked against its
FR page image when it was written. A promotion asks a different question: is
the right cite on each version, and does it point at the document that
printed this provision? The `cited` kind answers that for every value:

  1. value  the version's cite is its revision's override row (or empty, for
            a revision without one: the emitter has nothing to give it).
  2. row    the cite agrees with its own evidence: the printed page, and the
            volume (FR issue year - 1935).
  3. page   in our FR copy (input/Regs/CAR/FR/*.txt), the evidence PDF page
            reads as that printed page and carries the Part heading. The
            amendment number is noted, not flagged (OCR misreads it).
  4. section  the provision's section number ("3.85", "3.86a") is in the FR
            document that starts there. This is the independent check: it
            ties the version's designator, the provision and the cite
            together, and fails when a version sits on the wrong revision or a
            provision isn't in that amendment at all. The document runs from
            the heading to the first "F.R. Doc." line after the heading's
            page (pdftotext interleaves columns, so another document's F.R.
            Doc. line can follow the heading on its page).

`ok` means "consistent with our FR copy", not read: readers get a sample.
Imports the FR finder's tolerant matchers (tools.s01_extract.car.fr_issues)
read-only. Never fetches.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

from tools.s01_extract.car.fr_issues import HEADING, amdt_matches, page_numbers

OVERRIDES = [Path("tools/overrides/car_cites.tsv")]
# designators the overrides cover: a revision of these with no row has no cite
COVERED = re.compile(r"^CAR(?P<part>\d+)(?P<reissue>R?)-(?P<n>\d+)$")
CITE = re.compile(r"^(?P<vol>\d+) FR (?P<page>\d+)$")
EVIDENCE = re.compile(
    r"^(?P<pdf>\S+\.pdf) pdf p\.(?P<pdf_page>\d+), printed p\.(?P<printed>\d+)"
)
FR_YEAR = re.compile(r"FR-(\d{4})-\d\d-\d\d\.pdf$")
DOC_END = re.compile(r"F\s*\.?\s*R\s*\.?\s*D\s*o\s*c\s*\.?\s*\d", re.I)
AMDT_LOOKBACK = 2500


@dataclass(frozen=True)
class Row:
    designator: str
    cite: str
    evidence: str


@cache
def rows() -> dict[str, Row]:
    out: dict[str, Row] = {}
    for path in OVERRIDES:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                d = r["designator"]
                out[d] = Row(d, r["publication_cite"], r["evidence"])
    return out


def covers(designator: str) -> bool:
    return bool(COVERED.match(designator)) and bool(rows())


def amendment(designator: str) -> str:
    """The amendment number as the FR prints it: CAR3-7 → 3-7, CAR3R-2 → 3-2;
    "" for a base or reissued Part (CAR3-0, CAR3R-0)."""
    m = COVERED.match(designator)
    if not m or m["n"] == "0":
        return ""
    return f"{m['part']}-{m['n']}"


def section(designator: str, key: str) -> re.Pattern[str]:
    """OCR-tolerant section number: provision key 86a in CAR 3 → 3.86a."""
    m = COVERED.match(designator)
    part = m["part"] if m else ""
    body = r"\s*".join(re.escape(c) for c in key)
    return re.compile(rf"(?<![\d.]){part}\s*\.\s*{body}(?![\da-z])", re.I)


@dataclass(frozen=True)
class FRDoc:
    txt: Path
    pdf_page: int
    printed: int | None  # what our text layer reads for that page
    heading: bool
    amdt: bool
    body: str  # heading to the document's end


@cache
def fr_document(pdf: str, pdf_page: int, amdt: str) -> FRDoc | None:
    txt = Path(pdf).with_suffix(".txt")
    if not txt.exists():
        return None
    text = txt.read_text(encoding="utf-8", errors="replace")
    pages = text.split("\f")
    if not 0 < pdf_page <= len(pages):
        return FRDoc(txt, pdf_page, None, False, False, "")
    start = sum(len(p) + 1 for p in pages[: pdf_page - 1])
    page = pages[pdf_page - 1]
    h = HEADING.search(page)
    h0 = start + (h.start() if h else 0)
    # the first F.R. Doc. line after the heading's page: one on that page may
    # belong to another document (pdftotext interleaves columns)
    end = DOC_END.search(text, start + len(page) + 1)
    return FRDoc(
        txt,
        pdf_page,
        page_numbers(pages)[pdf_page - 1],
        h is not None,
        h is not None
        and amdt_matches(amdt, page[max(0, h.start() - AMDT_LOOKBACK) : h.start()]),
        text[h0 : end.end() if end else len(text)],
    )


def source(designator: str) -> str | None:
    """The FR page a revision's cite rests on, as "<txt> p.N"."""
    row = rows().get(designator)
    m = EVIDENCE.match(row.evidence) if row else None
    if not m:
        return None
    return f"{Path(m['pdf']).with_suffix('.txt').as_posix()} p.{m['pdf_page']}"


def _excerpt(body: str, pat: re.Pattern[str] | None) -> dict[str, Any]:
    m = pat.search(body) if pat else None
    a = max(0, m.start() - 600) if m else 0
    return {"text": re.sub(r"[ \t]+", " ", body[a : a + 1500]).strip()}


def _row_problem(value: str, row: Row) -> tuple[str, re.Match[str] | None]:
    """Steps 1-2: what's wrong with the value or its row, or ""."""
    if value != row.cite:
        return f"override row says {row.cite!r}", None
    c, ev = CITE.match(value), EVIDENCE.match(row.evidence)
    if not c or not ev:
        return "cite or evidence not in the expected form", None
    if c["page"] != ev["printed"]:
        return f"evidence names printed p.{ev['printed']}", None
    year = FR_YEAR.search(ev["pdf"])
    if not year or int(c["vol"]) != int(year[1]) - 1935:
        return f"volume {c['vol']} doesn't match the FR issue {ev['pdf']}", None
    return "", ev


def check(designator: str, key: str, value: Any) -> tuple[str, str, dict | None]:
    """(status, note, excerpt) for one version's cite."""
    row = rows().get(designator)
    if row is None:
        if value:
            return "flag", "no reviewed cite for this revision", None
        return "ok", "no reviewed cite for this revision; none given", None
    problem, ev = _row_problem(str(value or ""), row)
    if problem or ev is None:
        return "flag", problem, None
    amdt = amendment(designator)
    doc = fr_document(ev["pdf"], int(ev["pdf_page"]), amdt)
    if doc is None:
        return "unverifiable", f"no FR copy {ev['pdf']}", None
    if doc.printed != int(ev["printed"]):
        return (
            "flag",
            f"FR pdf p.{doc.pdf_page} reads as printed p.{doc.printed}",
            _excerpt(doc.body, None),
        )
    if not doc.heading:
        return (
            "flag",
            f"no Part heading on FR pdf p.{doc.pdf_page}",
            _excerpt(doc.body, None),
        )
    pat = section(designator, key)
    if not pat.search(doc.body):
        return (
            "flag",
            "section number not in the FR document at this cite",
            _excerpt(doc.body, None),
        )
    amdt_note = (
        f", amendment {amdt} matches"
        if doc.amdt
        else (f", amendment {amdt} not read" if amdt else "")
    )
    note = f"override row; FR page and heading{amdt_note}; section in the FR document"
    return "ok", note, _excerpt(doc.body, pat)
