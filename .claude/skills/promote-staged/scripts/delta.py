"""What promoting the staged tree would change, one JSON line per changed file.

Compares tools/out/staged/{documents,aircraft,deviations} with the same trees
in data/
at the level a reviewer needs: which versions or TCDS basis lines were added,
removed or changed, and for changed text whether any *words* changed or only
the layout (line breaks, indentation) or only the inline markup. Layout may add line breaks and
indentation but never change words (CLAUDE.md), so a words change is the
thing to read against the source.

    PYTHONPATH=. uv run python .claude/skills/promote-staged/scripts/delta.py \
        > delta.jsonl 2> delta_summary.txt

Each line: {"relpath", "kind": document|aircraft|deviation, "status": new|changed,
"class": [...], "changes": [...], "fields": [...], "residual": bool}.

Class tags: new-file, versions-added, versions-removed, words, markup-lost
(fewer sub/superscripts, formula lines or tables than data/ has),
markup-only (same plain words: markup gained or lost), layout-only,
metadata (some scalar field changed), basis-lines, references,
tcds-revision (a TCB's revision, revision_date or source_url changed) and
fields-only.

`fields` lists every scalar field change as {"where", "field", "old",
"new"}: where is "file", "version <designator>", "revision <designator>"
(_document.json) or "tcb <issuer> <number>"; field is the key, with TCDS
keys as "tcds.<key>". `residual` is true when anything other than those
fields changed: text, versions, revisions, basis lines, TCBs. A changed file
with no residual is tagged fields-only: it is "identical to data/ apart from
these fields", machine-checked, and fields.py can verify it without a reader.
Deviation records are listing metadata only, so every change to one is a
field change: `fields` holds each changed key as "deviation.<key>" (lists
too: citations, citation_gaps), where "file". A new record lists every key
it has plus, as new None, each key listing.CHECK_ABSENT expects the listing
may print, so fields.py can catch a dropped value. Changed records are
fields-only; new ones are new-file.
stderr: counts by class. Read-only.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from listing import CHECK_ABSENT  # noqa: E402

from certbuild.text import FORMULA_MARK, TABLE_OPEN, TextFormatError, plain_text

MAX_HUNKS = 6
REVISION_KEYS = {"revision", "revision_date", "source_url"}
INLINE_RE = re.compile(r"[_^]\{[^{}$\n]+\}")


def markup_count(text: str) -> int:
    """Sub/superscripts, formula lines and tables in one text."""
    return (
        len(INLINE_RE.findall(text))
        + text.count(FORMULA_MARK) // 2
        + text.count(TABLE_OPEN)
    )


def words_diff(old: str, new: str) -> list[dict[str, str]]:
    """Word-level hunks between two texts, ignoring all whitespace."""
    a, b = old.split(), new.split()
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    hunks = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        ctx = " ".join(a[max(0, i1 - 4) : i1])
        hunks.append(
            {
                "op": op,
                "context": ctx,
                "old": " ".join(a[i1:i2])[:300],
                "new": " ".join(b[j1:j2])[:300],
            }
        )
    return hunks


def _fields_changed(
    old: dict[str, Any], new: dict[str, Any], skip: set[str]
) -> list[str]:
    keys = (set(old) | set(new)) - skip
    return sorted(k for k in keys if old.get(k) != new.get(k))


def _field_rows(
    old: dict[str, Any],
    new: dict[str, Any],
    skip: set[str],
    where: str,
    prefix: str = "",
) -> list[dict[str, Any]]:
    """One {"where", "field", "old", "new"} per changed key."""
    return [
        {"where": where, "field": prefix + k, "old": old.get(k), "new": new.get(k)}
        for k in _fields_changed(old, new, skip)
    ]


def _finish(row: dict[str, Any], fields: list[dict[str, Any]], residual: bool) -> dict:
    if fields:
        row["class"] = sorted({*row["class"], "metadata"})
    if not residual and fields:
        row["class"] = sorted({*row["class"], "fields-only"})
    return {**row, "fields": fields, "residual": residual}


def document_delta(old: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    if old is None:
        designators = [v.get("designator") for v in new.get("versions", [])]
        return {
            "status": "new",
            "class": ["new-file"],
            "changes": [{"versions": designators}],
            "fields": [],
            "residual": True,
        }
    classes: set[str] = set()
    changes: list[dict[str, Any]] = []
    fields = _field_rows(old, new, {"versions"}, "file")
    top = _fields_changed(old, new, {"versions"})
    if top:
        changes.append({"top_fields": {k: [old.get(k), new.get(k)] for k in top}})
    ov = {v.get("designator"): v for v in old.get("versions", [])}
    nv = {v.get("designator"): v for v in new.get("versions", [])}
    if added := [d for d in nv if d not in ov]:
        classes.add("versions-added")
        changes.append({"versions_added": added})
    if removed := [d for d in ov if d not in nv]:
        classes.add("versions-removed")
        changes.append({"versions_removed": removed})
    for d in nv:
        if d in ov and ov[d] != nv[d]:
            changes.append(_version_change(d, ov[d], nv[d], classes))
            fields += _field_rows(ov[d], nv[d], {"text"}, f"version {d}")
    residual = bool(classes)  # versions or text changed, beyond the fields
    row = {"status": "changed", "class": sorted(classes), "changes": changes}
    return _finish(row, fields, residual)


def index_delta(old: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    """_document.json: top fields, and the revision list by designator."""
    if old is None:
        return {
            "status": "new",
            "class": ["new-file"],
            "changes": [],
            "fields": [],
            "residual": True,
        }
    classes: set[str] = set()
    changes: list[dict[str, Any]] = []
    fields = _field_rows(old, new, {"revisions"}, "file")
    orv = {r.get("designator"): r for r in old.get("revisions", [])}
    nrv = {r.get("designator"): r for r in new.get("revisions", [])}
    if added := [d for d in nrv if d not in orv]:
        classes.add("versions-added")
        changes.append({"revisions_added": added})
    if removed := [d for d in orv if d not in nrv]:
        classes.add("versions-removed")
        changes.append({"revisions_removed": removed})
    for d in nrv:
        if d in orv:
            fields += _field_rows(orv[d], nrv[d], set(), f"revision {d}")
    if fields:
        changes.append({"fields": len(fields)})
    row = {"status": "changed", "class": sorted(classes), "changes": changes}
    return _finish(row, fields, bool(classes))


def _version_change(
    designator: str, old: dict[str, Any], new: dict[str, Any], classes: set[str]
) -> dict[str, Any]:
    entry: dict[str, Any] = {"designator": designator}
    fields = _fields_changed(old, new, {"text"})
    if fields:
        entry["fields"] = {k: [old.get(k), new.get(k)] for k in fields}
    o_text, n_text = old.get("text") or "", new.get("text") or ""
    if o_text != n_text:
        hunks = words_diff(o_text, n_text)
        if hunks:
            tag = "markup-only" if _same_plain(o_text, n_text) else "words"
            classes.add(tag)
            entry[tag] = hunks[:MAX_HUNKS]
            entry["word_hunks"] = len(hunks)
        else:
            classes.add("layout-only")
            entry["layout_only"] = True
        entry["chars"] = [len(o_text), len(n_text)]
        o_mk, n_mk = markup_count(o_text), markup_count(n_text)
        if n_mk < o_mk:
            classes.add("markup-lost")
            entry["markup"] = [o_mk, n_mk]
    return entry


def _same_plain(old: str, new: str) -> bool:
    """True when the texts differ only in inline/table markup."""
    try:
        return plain_text(old).split() == plain_text(new).split()
    except (TextFormatError, ValueError):
        return False


def _tcb_key(tcb: dict[str, Any]) -> str:
    t = tcb.get("tcds", {})
    return f"{t.get('issuer')} {t.get('tcds_number')}"


def aircraft_delta(old: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    if old is None:
        return {
            "status": "new",
            "class": ["new-file"],
            "changes": [{"tcb": [_tcb_key(t) for t in new.get("tcb", [])]}],
            "fields": [],
            "residual": True,
        }
    classes: set[str] = set()
    changes: list[dict[str, Any]] = []
    fields = _field_rows(old, new, {"tcb"}, "file")
    residual = False
    top = _fields_changed(old, new, {"tcb"})
    if top:
        changes.append({"top_fields": {k: [old.get(k), new.get(k)] for k in top}})
    ot = {_tcb_key(t): t for t in old.get("tcb", [])}
    for key, nt in ((_tcb_key(t), t) for t in new.get("tcb", [])):
        if (otcb := ot.pop(key, None)) is None:
            classes.add("basis-lines")
            changes.append({"tcb_added": key})
            residual = True
        elif otcb != nt:
            entry = _tcb_change(key, otcb, nt, classes)
            changes.append(entry)
            fields += _tcb_fields(key, otcb, nt)
            residual |= any(k.startswith("lines_") for k in entry)
    for key in ot:
        classes.add("basis-lines")
        changes.append({"tcb_removed": key})
        residual = True
    row = {"status": "changed", "class": sorted(classes), "changes": changes}
    return _finish(row, fields, residual)


def _tcb_fields(key: str, old: dict[str, Any], new: dict[str, Any]) -> list[dict]:
    where = f"tcb {key}"
    rows = _field_rows(old, new, {"tcds", "certification_basis"}, where)
    return rows + _field_rows(
        old.get("tcds", {}), new.get("tcds", {}), set(), where, "tcds."
    )


def _tcb_change(
    key: str, old: dict[str, Any], new: dict[str, Any], classes: set[str]
) -> dict[str, Any]:
    entry: dict[str, Any] = {"tcb": key}
    o_tcds, n_tcds = old.get("tcds", {}), new.get("tcds", {})
    if o_tcds != n_tcds:
        if any(o_tcds.get(k) != n_tcds.get(k) for k in REVISION_KEYS):
            classes.add("tcds-revision")
        entry["tcds"] = [o_tcds, n_tcds]
    for k in _fields_changed(old, new, {"tcds", "certification_basis"}):
        entry.setdefault("fields", {})[k] = [old.get(k), new.get(k)]
    ol = {ln.get("raw_reference"): ln for ln in old.get("certification_basis", [])}
    nl = {ln.get("raw_reference"): ln for ln in new.get("certification_basis", [])}
    if added := [r for r in nl if r not in ol]:
        classes.add("basis-lines")
        entry["lines_added"] = [_line(nl[r]) for r in added]
    if removed := [r for r in ol if r not in nl]:
        classes.add("basis-lines")
        entry["lines_removed"] = [_line(ol[r]) for r in removed]
    changed = []
    for raw in nl:
        if raw in ol and _strip_order(ol[raw]) != _strip_order(nl[raw]):
            changed.append({"old": _line(ol[raw]), "new": _line(nl[raw])})
    if changed:
        classes.add("references")
        entry["lines_changed"] = changed
    return entry


def _strip_order(line: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in line.items() if k != "display_order"}


def _line(line: dict[str, Any]) -> dict[str, Any]:
    out = _strip_order(line)
    out["raw_reference"] = str(out.get("raw_reference", ""))[:600]
    return out


DEVIATION_IDENTITY = {"issuer", "key"}


def deviation_delta(old: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    """Every change to a deviation record is a field change."""
    if old is None:
        absent = CHECK_ABSENT.get(new.get("issuer", ""), ())
        keys = sorted((set(new) | set(absent)) - DEVIATION_IDENTITY)
        fields = [
            {"where": "file", "field": f"deviation.{k}", "old": None, "new": new.get(k)}
            for k in keys
        ]
        return {
            "status": "new",
            "class": ["new-file"],
            "changes": [],
            "fields": fields,
            "residual": True,
        }
    fields = _field_rows(old, new, DEVIATION_IDENTITY, "file", "deviation.")
    row = {"status": "changed", "class": [], "changes": [{"fields": len(fields)}]}
    return _finish(row, fields, residual=False)


WALKERS = {"document": document_delta, "aircraft": aircraft_delta}


def walk(staged: Path, data: Path, kind: str) -> list[dict[str, Any]]:
    fn = WALKERS.get(kind, deviation_delta)
    rows = []
    for path in sorted(staged.rglob("*.json")):
        rel = path.relative_to(staged)
        new = json.loads(path.read_text(encoding="utf-8"))
        target = data / rel
        old = (
            json.loads(target.read_text(encoding="utf-8")) if target.exists() else None
        )
        if old == new:
            continue
        if path.name.startswith("_"):
            row = index_delta(old, new)
        else:
            row = fn(old, new)
        rows.append({"relpath": f"{data.name}/{rel.as_posix()}", "kind": kind, **row})
    return rows


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--staged", type=Path, default=Path("tools/out/staged"))
    p.add_argument("--data", type=Path, default=Path("data"))
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows = walk(args.staged / "documents", args.data / "documents", "document")
    rows += walk(args.staged / "aircraft", args.data / "aircraft", "aircraft")
    rows += walk(args.staged / "deviations", args.data / "deviations", "deviation")
    counts: Counter[str] = Counter()
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
        counts.update(f"{row['kind']}:{c}" for c in row["class"])
    for name, n in sorted(counts.items()):
        print(f"{n:7}  {name}", file=sys.stderr)
    print(f"{len(rows):7}  files that would change", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
