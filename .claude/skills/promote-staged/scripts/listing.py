"""Deviation records against their regulator listings: sources and verifiers.

A deviation record (data/deviations/{issuer}/{key}.json) is link-only: every
field is something the regulator's listing prints, or a rule applied to it.
So the whole record can be checked field by field against our cached copy of
the listing, without reading the PDF behind it:

  FAA   the DRS listing entry for the record's docUniqueId, in the cached
        listing pages input/cache/drs/deviations/{ELOS,SCFINAL,SCPROPOSED,
        EXEMPTION}/pNNNN.json. Each entry is a set of labelled metadata
        (Subject, Applicant, CFR Section Reference, ...). The same page
        source as the catalogue, read independently of it.
  EASA  the publication's detail page, input/cache/easa_deviations/detail/
        {node_id}.html.

Verifier kinds (registered in fields.py):

  listed   the value is what the listing prints. FAA: equal (whitespace
           collapsed) to the value of one of the field's DRS labels (LABELS);
           a date equal to the date there. A field the record leaves out
           (None) passes only when the listing prints nothing under those
           labels: that catches dropped values. EASA: the title is a whole
           line of the page, the number a phrase on it, the date in it.
  derived  (deviation.* only, via `derived`) kind and stage from the listing
           type (EASA stage only when the page says "with final
           publication": its file labels can't decide it, so it is sampled); final points at a final record of the same kind and, for
           FAA, the same docket; source_url is the DRS view URL or the page's
           canonical link; each citation's number and each gap's `cited`
           occurs in the title, number or regulation_ref.

These are restated from docs/DATA_FORMAT.md §Deviation file and the DRS
field names, not imported from the emitters, so a shared bug shows up. `ok`
means "matches our cached listing". Read-only.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

DRS = Path("input/cache/drs/deviations")
EASA_DETAIL = Path("input/cache/easa_deviations/detail")
DRS_URL = "https://drs.faa.gov/browse/excelExternalWindow/{key}"
DRS_TYPES = ("ELOS", "SCFINAL", "SCPROPOSED", "EXEMPTION")

# record field → DRS metadata labels it may come from (any one)
LABELS: dict[str, tuple[str, ...]] = {
    "title": ("Subject",),
    "number": ("Finding Number", "SC Number", "Notice Number", "Exemption Number"),
    "applicant": ("Applicant", "Petitioner Name", "Company Name"),
    "make": ("Make",),
    "model": ("Model", "Model/Series", "Equipment"),
    "regulation_ref": ("CFR Section Reference", "Regulation/Title 14 CFR Reference"),
    "disposition": ("Disposition",),
    "published_on": ("Document Issue Date", "Effective Date", "Issue Date"),
}
# fields each issuer's records are checked for even when absent (dropped values)
CHECK_ABSENT = {
    "FAA": (
        "number",
        "title",
        "applicant",
        "make",
        "model",
        "regulation_ref",
        "disposition",
        "published_on",
    ),
    "EASA": ("title", "published_on"),
}
FAA_KIND = {
    "ELOS": ("elos", "final"),
    "SCFINAL": ("special_condition", "final"),
    "SCPROPOSED": ("special_condition", "proposed"),
    "EXEMPTION": ("exemption", "final"),
}
EASA_KIND = {
    "special_condition": "Special Condition (SC)",
    "elos": "Equivalent Safety Finding (ESF)",
    "deviation": "Deviation (DEV)",
    "means_of_compliance": "Interpretative Material/Means of Compliance to SC and ESF",
}
DROP_RE = re.compile(r"<(script|style)\b.*?</\1>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")
CANONICAL_RE = re.compile(r'<link rel="canonical" href="([^"]+)"')


@dataclass(frozen=True)
class Entry:
    """One DRS listing entry."""

    doc_type: str
    path: Path
    meta: dict[str, str]

    def text(self) -> str:
        return "\n".join(f"{k}: {v}" for k, v in self.meta.items())


@lru_cache(maxsize=1)
def drs_index() -> dict[str, Entry]:
    """docUniqueId → listing entry, over every cached listing page."""
    out: dict[str, Entry] = {}
    for doc_type in DRS_TYPES:
        for page in sorted((DRS / doc_type).glob("p*.json")):
            for e in json.loads(page.read_text(encoding="utf-8"))["documentList"]:
                meta = {
                    e["headerLink"]["metadataName"]: e["headerLink"]["metadataValue"]
                }
                more = (
                    e.get("description", []) + e.get("subText", []) + e.get("tags", [])
                )
                for m in more:
                    meta[m["metadataName"]] = m["metadataValue"] or ""
                out.setdefault(e["docUniqueId"], Entry(doc_type, page, meta))
    return out


@lru_cache(maxsize=1024)
def page_text(path: Path) -> str:
    """An EASA detail page as text: scripts dropped, one line per element."""
    if not path.exists():
        return ""
    raw = DROP_RE.sub("", path.read_text(encoding="utf-8", errors="replace"))
    lines = (ln.strip() for ln in html.unescape(TAG_RE.sub("\n", raw)).split("\n"))
    return "\n".join(ln for ln in lines if ln)


def source(issuer: str, key: str) -> tuple[str | None, str]:
    """(source label, its text) for one record. FAA labels are
    `<listing page>#<key>`; the text is the entry's `Label: value` lines."""
    if issuer == "FAA":
        e = drs_index().get(key)
        return (f"{e.path.as_posix()}#{key}", e.text()) if e else (None, "")
    p = EASA_DETAIL / f"{key}.html"
    return (p.as_posix(), page_text(p)) if p.exists() else (None, "")


def _norm(s: str) -> str:
    return " ".join(s.split())


def _drs_date(s: str) -> str | None:
    try:
        return dt.datetime.strptime(s.strip(), "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _excerpt(text: str, needle: str) -> dict[str, Any] | None:
    lines = text.split("\n")
    n = next((i for i, ln in enumerate(lines) if needle and needle in ln), None)
    if n is None:
        return None
    a, b = max(0, n - 2), min(len(lines), n + 3)
    return {"lines": f"{a + 1}-{b}", "page": None, "text": "\n".join(lines[a:b])[:1500]}


def listed_faa(name: str, value: Any, entry: Entry) -> tuple[str, str, str]:
    """(status, note, label) for one field against a DRS entry."""
    labels = LABELS.get(name, ())
    printed = {lb: entry.meta[lb] for lb in labels if entry.meta.get(lb, "").strip()}
    if value is None:
        if printed:
            lb, v = next(iter(printed.items()))
            return "flag", f"record has none; listing has {lb}: {_norm(v)[:80]!r}", lb
        return "ok", "", ""
    for lb, v in printed.items():
        got = _drs_date(v) if name == "published_on" else _norm(v)
        if got == _norm(str(value)):
            return "ok", "", lb
        if got and got.casefold() == _norm(str(value)).casefold():
            return "ok", "case differs", lb
    if not printed:
        return "flag", f"listing prints nothing under {' / '.join(labels)}", ""
    lb, v = next(iter(printed.items()))
    return "flag", f"listing has {lb}: {_norm(v)[:80]!r}", lb


def listed_easa(name: str, value: Any, text: str) -> tuple[str, str]:
    if value is None:
        return ("flag", "record has none") if name == "title" else ("ok", "")
    v = _norm(str(value))
    lines = [_norm(ln) for ln in text.split("\n")]
    if name == "title":
        return (
            ("ok", "") if v in lines else ("flag", "no line of the page is the title")
        )
    if name == "published_on":
        d = dt.date.fromisoformat(v)
        forms = {
            f"{d.day:02} {d:%b} {d.year}",
            f"{d.day} {d:%b} {d.year}",
            f"{d.day:02}/{d.month:02}/{d.year}",
            v,
        }
        hit = any(f in ln for f in forms for ln in lines)
        return ("ok", "") if hit else ("flag", "date not on the page")
    flat = " ".join(lines).casefold()
    return ("ok", "") if v.casefold() in flat else ("flag", "not found on the page")


def listed(
    issuer: str, key: str, name: str, value: Any
) -> tuple[str, str, dict | None]:
    """(status, note, excerpt) for a `listed` field of one record."""
    label, text = source(issuer, key)
    if label is None:
        return "unverifiable", "no cached listing for this record", None
    if issuer == "FAA":
        status, note, lb = listed_faa(name, value, drs_index()[key])
        return status, note, _excerpt(text, f"{lb}:" if lb else "")
    status, note = listed_easa(name, value, text)
    return status, note, _excerpt(text, _norm(str(value or ""))[:60])


def easa_stage(value: Any, text: str) -> tuple[str, str]:
    """EASA labels its files inconsistently (a final SC is often labelled like
    the proposal), so only "with final publication" on the page is firm. The
    rest passes with a note and is left to the reader sample."""
    if "with final publication" in text:
        return (
            ("ok", "") if value == "final" else ("flag", "page says final publication")
        )
    return "ok", "EASA stage not decidable by script: sampled"


def _record(root: Path, issuer: str, key: str) -> dict[str, Any] | None:
    p = root / "deviations" / issuer.lower() / f"{key}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def _docket(key: str) -> str:
    e = drs_index().get(key)
    return re.sub(
        r"[^0-9A-Za-z]", "", (e.meta.get("Docket Number", "") if e else "")
    ).upper()


def _final(record: dict[str, Any], value: Any, roots: list[Path]) -> tuple[str, str]:
    if value is None:
        return "ok", ""
    issuer = record["issuer"]
    target = next((r for root in roots if (r := _record(root, issuer, value))), None)
    if target is None:
        return "flag", f"no record {value}"
    if target.get("stage") != "final" or target.get("kind") != record.get("kind"):
        return "flag", f"{value} is {target.get('stage')} {target.get('kind')}"
    if issuer == "FAA" and _docket(record["key"]) != _docket(value):
        return (
            "flag",
            f"dockets differ: {_docket(record['key'])!r} vs {_docket(value)!r}",
        )
    return "ok", "same docket; title agreement not checked" if issuer == "FAA" else ""


def _named(record: dict[str, Any]) -> str:
    return " ".join(
        str(record.get(k) or "") for k in ("title", "number", "regulation_ref")
    )


def _citations(record: dict[str, Any], value: Any, gaps: bool) -> tuple[str, str]:
    text = _named(record)
    bad = []
    for c in value or []:
        if gaps:
            if str(c.get("cited", "")) not in text:
                bad.append(c.get("cited"))
        elif not re.search(
            rf"(?<![0-9])0*{re.escape(str(c['number']))}(?![0-9])", text
        ):
            bad.append(f"{c['document']} {c['number']}")
    return (
        ("flag", f"not named in title/number/regulation_ref: {bad[:5]}")
        if bad
        else ("ok", "")
    )


def derived(
    name: str, record: dict[str, Any], value: Any, roots: list[Path]
) -> tuple[str, str]:
    """(status, note) for a derived deviation field."""
    issuer, key = record["issuer"], record["key"]
    entry = drs_index().get(key) if issuer == "FAA" else None
    text = page_text(EASA_DETAIL / f"{key}.html") if issuer == "EASA" else ""
    if issuer == "FAA" and entry is None or issuer == "EASA" and not text:
        if name not in ("final", "citations", "citation_gaps"):
            return "unverifiable", "no cached listing for this record"
    if name in ("kind", "stage"):
        if issuer == "FAA":
            want = FAA_KIND[entry.doc_type][0 if name == "kind" else 1]  # type: ignore[union-attr]
        elif name == "kind":
            want = next((k for k, lb in EASA_KIND.items() if lb in text), "?")
        else:
            return easa_stage(value, text)
        return ("ok", "") if value == want else ("flag", f"listing gives {want!r}")
    if name == "source_url":
        if issuer == "FAA":
            want = DRS_URL.format(key=key)
        else:
            raw = (EASA_DETAIL / f"{key}.html").read_text(
                encoding="utf-8", errors="replace"
            )
            m = CANONICAL_RE.search(raw)
            want = m.group(1) if m else "?"
        return ("ok", "") if value == want else ("flag", f"listing gives {want!r}")
    if name == "final":
        return _final(record, value, roots)
    if name in ("citations", "citation_gaps"):
        return _citations(record, value, name == "citation_gaps")
    return "unverifiable", f"no rule for deviation.{name}"
