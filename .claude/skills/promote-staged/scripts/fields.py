"""Verify the scalar field changes in a promotion delta with scripts.

delta.py lists every changed field ({"where", "field", "old", "new"}). Most
are mechanical: a value copied from the source (a holder, a title, a cite), a
date, or a value derived by a rule (a display group). A script answers those
more cheaply than a reader does, so each field name has a verifier kind here
(FIELDS), and only what the script can't confirm goes to a reader.

Kinds:
  verbatim  the new value appears word for word in the local source text
            (after `label`, if given), is not cut short (the source line goes
            on after it) and is not missing a wrapped continuation (the next
            line starts with a company suffix, "trading as", "(" or lower
            case). A case-only difference passes, with a note.
  date      the new ISO date appears in the source text in a common format.
  derived   the value follows its rule (manufacturer_group from
            tools/overrides/manufacturer_groups.tsv; deleted ⇒ no text;
            deviation.* rules in listing.py).
  listed    a deviation field is what the regulator's listing prints, and an
            absent one is absent there too (listing.py).
  cited     a publication_cite from a reviewed cite override (CAR FR cites):
            the override row, its evidence, the FR page, and the provision's
            section in the FR document at that cite (cites.py). Used instead
            of verbatim for any version the override covers.
A field with no entry is `unverifiable`: a reader checks it. Adding a field to
the schema means adding a line here, or accepting that it is read.

    PYTHONPATH=.:.claude/skills/audit-data/scripts uv run python \\
        .claude/skills/promote-staged/scripts/fields.py \\
        --delta delta.jsonl > fields.jsonl 2> fields_summary.txt

Each line is one distinct check: {"field", "kind", "where", "old", "new",
"relpaths", "source", "status": ok|flag|unverifiable, "note", "excerpt"}.
The same value checked against the same source in several files is one line.
The text sources are pipeline copies: `ok` means "matches our copy of the
source", which is not proof that the source says it (see context.py).
Read-only.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from context import excerpt, find, load_text, tcds_paths  # noqa: E402
from sample import source_copies  # noqa: E402

import cites  # noqa: E402
import listing  # noqa: E402

GROUPS = Path("tools/overrides/manufacturer_groups.tsv")
CONTINUATION = re.compile(
    r"^(S\.?\s?p\.?\s?A\.?|S\.?A\.?S?\.?|Ltd\.?|Limited|GmbH|Inc\.?|LLC|L\.L\.C\.|"
    r"s\.\s?r\.\s?o\.|a\.\s?s\.|Corp(oration)?\.?|AG|plc|B\.V\.|N\.V\.|Co\.|"
    r"trading as\b|t/a\b|d/b/a\b|dba\b|\(|[a-z])"
)


@dataclass(frozen=True)
class Check:
    kind: str  # verbatim | date | derived | listed | cited
    label: str | None = None  # regex: search after the first line matching it


FIELDS: dict[str, Check] = {
    "tcds.holder": Check("verbatim", r"holder"),
    "title_at_revision": Check("verbatim"),
    "canonical_title": Check("verbatim"),
    "publication_cite": Check("verbatim"),
    "tcds.revision_date": Check("date"),
    "manufacturer_group": Check("derived"),
    "deleted": Check("derived"),
    **{
        f"deviation.{k}": Check("listed")
        for k in (
            "number",
            "title",
            "applicant",
            "make",
            "model",
            "regulation_ref",
            "disposition",
            "published_on",
        )
    },
    **{
        f"deviation.{k}": Check("derived")
        for k in ("kind", "stage", "source_url", "final", "citations", "citation_gaps")
    },
}


@dataclass
class Ctx:
    """What a verifier may look at for one field change."""

    record: dict[str, Any]  # the staged file
    version: dict[str, Any] | None = None
    source: Path | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Result:
    status: str
    note: str = ""
    excerpt: dict[str, Any] | None = None


# --- verifiers --------------------------------------------------------------


def _label_line(text: str, label: str | None) -> int:
    if not label:
        return 0
    rx = re.compile(label, re.I)
    return next((n for n, ln in enumerate(text.split("\n")[:300]) if rx.search(ln)), 0)


def _cut_short(text: str, value: str, first_line: int) -> str:
    """The words that follow value on its own line, when only a single space
    separates them (a column gap is two or more)."""
    line = text.split("\n")[first_line]
    i = line.casefold().find(value.casefold())
    if i < 0:
        return ""
    rest = line[i + len(value) :]
    return rest.strip() if rest[:1] == " " and rest[1:2] not in (" ", "") else ""


def _wrapped(text: str, last_line: int) -> str:
    lines = text.split("\n")
    nxt = next(
        (ln.strip() for ln in lines[last_line + 1 : last_line + 3] if ln.strip()), ""
    )
    return nxt if CONTINUATION.match(nxt) else ""


def verbatim(value: Any, ctx: Ctx, check: Check) -> Result:
    if not value:
        return Result("flag", "empty")
    if ctx.source is None or not (text := load_text(ctx.source)):
        return Result("unverifiable", "no source text")
    value = str(value)
    start = _label_line(text, check.label)
    m = find(text, value, start) or find(text, value)
    if m is None:
        return Result("flag", "not found in the source text")
    ex = excerpt(text, m, 3)
    if cont := _cut_short(text, value, m.first_line):
        return Result("flag", f"source line goes on: {cont[:60]!r}", ex)
    if (wrap := _wrapped(text, m.last_line)) and check.label:
        return Result("flag", f"next line may continue it: {wrap[:60]!r}", ex)
    exact = " ".join(value.split()) in " ".join(text.split())
    return Result("ok", "" if exact else "case or punctuation differs", ex)


MONTHS = "January February March April May June July August September October November December".split()


def _date_forms(d: dt.date) -> list[str]:
    m = MONTHS[d.month - 1]
    return [
        f"{d.day} {m} {d.year}",
        f"{d.day:02} {m} {d.year}",
        f"{m} {d.day}, {d.year}",
        f"{m} {d.day:02}, {d.year}",
        f"{d.day:02}-{m[:3]}-{d.year}",
        f"{d.day}-{m[:3]}-{d.year}",
        f"{d.day:02} {m[:3]} {d.year}",
        f"{d.day:02}.{d.month:02}.{d.year}",
        f"{d.day:02}/{d.month:02}/{d.year}",
        f"{d.month:02}/{d.day:02}/{d.year}",
        f"{d.month}/{d.day}/{d.year}",
        d.isoformat(),
    ]


def date(value: Any, ctx: Ctx, check: Check) -> Result:
    if not value:
        return Result("flag", "empty")
    if ctx.source is None or not (text := load_text(ctx.source)):
        return Result("unverifiable", "no source text")
    try:
        d = dt.date.fromisoformat(str(value))
    except ValueError:
        return Result("flag", "not an ISO date")
    flat = " ".join(text.split()).casefold()
    for form in _date_forms(d):
        if form.casefold() in flat:
            m = find(text, form)
            return Result("ok", "", excerpt(text, m, 1) if m else None)
    return Result("flag", "date not found in the source text")


def _groups() -> dict[str, str]:
    if not GROUPS.exists():
        return {}
    with GROUPS.open(encoding="utf-8") as fh:
        return {
            r["manufacturer"]: r["group"] for r in csv.DictReader(fh, delimiter="\t")
        }


def derived(value: Any, ctx: Ctx, check: Check) -> Result:
    name = ctx.extra["field"]
    if name.startswith("deviation."):
        status, note = listing.derived(
            name.removeprefix("deviation."), ctx.record, value, ctx.extra["roots"]
        )
        return Result(status, note)
    if name == "manufacturer_group":
        maker = ctx.record.get("manufacturer")
        want = ctx.extra["groups"].get(maker, maker)
        return Result("ok") if value == want else Result("flag", f"rule gives {want!r}")
    if name == "deleted":
        text = (ctx.version or {}).get("text")
        return (
            Result("flag", "deleted but has text") if value and text else Result("ok")
        )
    return Result("unverifiable", f"no rule for {name}")


def listed(value: Any, ctx: Ctx, check: Check) -> Result:
    rec = ctx.record
    name = ctx.extra["field"].removeprefix("deviation.")
    status, note, ex = listing.listed(rec["issuer"], rec["key"], name, value)
    return Result(status, note, ex)


def cited(value: Any, ctx: Ctx, check: Check) -> Result:
    status, note, ex = cites.check(ctx.extra["designator"], ctx.extra["key"], value)
    return Result(status, note, ex)


VERIFIERS: dict[str, Callable[[Any, Ctx, Check], Result]] = {
    "verbatim": verbatim,
    "date": date,
    "derived": derived,
    "listed": listed,
    "cited": cited,
}

# --- context per field change ------------------------------------------------


def _load(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _ctx(row: dict[str, Any], fch: dict[str, Any], staged: Path, groups: dict) -> Ctx:
    rel = row["relpath"]
    record = _load(staged / rel) or {}
    roots = [staged, Path("data")]
    ctx = Ctx(record, extra={"field": fch["field"], "groups": groups, "roots": roots})
    kind, _, ident = fch["where"].partition(" ")
    if row["kind"] == "deviation":
        label, _ = listing.source(record.get("issuer", ""), record.get("key", ""))
        ctx.extra["source_label"] = label
    elif kind == "tcb":
        for tcb in record.get("tcb", []):
            t = tcb["tcds"]
            if f"{t['issuer']} {t['tcds_number']}" == ident:
                ctx.source = tcds_paths(t)[1]
    elif kind == "version":
        issuer, doc, key = rel.split("/")[1:4]
        ctx.extra["designator"], ctx.extra["key"] = ident, key.removesuffix(".json")
        ctx.version = next(
            (v for v in record.get("versions", []) if v.get("designator") == ident),
            None,
        )
        if ctx.version is not None:
            copies = source_copies(issuer, doc, key.removesuffix(".json"), ctx.version)
            texts = [
                p
                for p in copies["extracted"] + copies["source"]
                if p.endswith((".txt", ".json"))
            ]
            ctx.source = Path(texts[0]) if texts else None
    return ctx


def check_row(row: dict[str, Any], staged: Path, groups: dict) -> list[dict[str, Any]]:
    out = []
    for fch in row.get("fields", []):
        check = FIELDS.get(fch["field"])
        ctx = _ctx(row, fch, staged, groups)
        des = ctx.extra.get("designator", "")
        if fch["field"] == "publication_cite" and cites.covers(des):
            check = Check("cited")
            ctx.extra["source_label"] = cites.source(des)
        if check is None:
            res = Result("unverifiable", f"no verifier for {fch['field']}")
        else:
            res = VERIFIERS[check.kind](fch["new"], ctx, check)
        out.append(
            {
                **fch,
                "kind": check.kind if check else None,
                "relpaths": [row["relpath"]],
                "source": ctx.extra.get("source_label")
                or (ctx.source.as_posix() if ctx.source else None),
                "status": res.status,
                "note": res.note,
                "excerpt": res.excerpt,
            }
        )
    return out


def merge(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One line per (field, value, source, outcome); relpaths gathered."""
    merged: dict[str, dict[str, Any]] = {}
    for r in results:
        same_file = r["source"] is None  # derived: one check per file
        key = json.dumps(
            [
                r["field"],
                r["new"],
                r["old"],
                r["source"],
                r["status"],
                r["note"],
                r["relpaths"][0] if same_file else "",
            ],
            ensure_ascii=False,
        )
        if key in merged:
            merged[key]["relpaths"] += r["relpaths"]
        else:
            merged[key] = r
    return list(merged.values())


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--delta", type=Path, required=True)
    p.add_argument("--staged", type=Path, default=Path("tools/out/staged"))
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    groups = _groups()
    results: list[dict[str, Any]] = []
    for line in args.delta.read_text(encoding="utf-8").splitlines():
        results += check_row(json.loads(line), args.staged, groups)
    merged = merge(results)
    counts: Counter[tuple[str, str]] = Counter()
    for r in merged:
        print(json.dumps(r, ensure_ascii=False))
        counts[(r["field"], r["status"])] += 1
    for (name, status), n in sorted(counts.items()):
        print(f"{n:7}  {name}: {status}", file=sys.stderr)
    print(
        f"{len(results):7}  field changes, {len(merged)} distinct checks",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
