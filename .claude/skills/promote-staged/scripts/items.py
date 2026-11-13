"""Reading items for one delta row: what a reader sees, and only that.

Three modes, each with its own section in READER.md:

  diff   a changed version or TCB. The item carries only what changed
         (`changed`: word hunks, line hunks or basis lines added, removed
         or re-parsed) with the data/ side and a slice of the source around
         each change (context.py). Unchanged text is out of scope.
  full   new content with no data/ side: a new or added version, a TCB
         not in data/ anywhere. The whole text against the source.
  field  a field value fields.py could not confirm, or a sampled pass
         (built in batches.py from fields.jsonl).

Each item has `reason` (why it is here), `group` (for stratified sampling:
the document or manufacturer directory) and `source_key` (items with the same
source are packed into one batch, so one PDF serves them all). Identical
changes in several files (one TCDS shared by many model files) are one item
with all their `relpaths`. A TCB that is byte-identical to one already in
data/ (same TCDS revision and basis) is not new content: it's skipped.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

from context import load_text, locate, excerpt, slice_for, tcds_paths
from sample import source_copies

MAX_HUNKS = 12
MAX_SLICES = 6
CTX_WORDS = 12


def _load(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _version(doc: dict[str, Any] | None, des: str) -> dict[str, Any] | None:
    return next(
        (v for v in (doc or {}).get("versions", []) if v.get("designator") == des), None
    )


def word_hunks(old: str, new: str) -> list[dict[str, str]]:
    """Word-level changes with CTX_WORDS of context on each side."""
    a, b = old.split(), new.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, a, b, autojunk=False
    ).get_opcodes():
        if op == "equal":
            continue
        out.append(
            {
                "before": " ".join(b[max(0, j1 - CTX_WORDS) : j1]),
                "data": " ".join(a[i1:i2])[:400],
                "staged": " ".join(b[j1:j2])[:400],
                "after": " ".join(b[j2 : j2 + CTX_WORDS]),
            }
        )
    return out


def line_hunks(old: str, new: str) -> list[dict[str, list[str]]]:
    """Line-level changes (for layout and markup), with one line of context."""
    a, b = old.splitlines(), new.splitlines()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, a, b, autojunk=False
    ).get_opcodes():
        if op == "equal":
            continue
        out.append(
            {
                "before": [ln[:200] for ln in b[max(0, j1 - 1) : j1]],
                "data": [ln[:400] for ln in a[i1:i2]],
                "staged": [ln[:400] for ln in b[j1:j2]],
            }
        )
    return out


def _source_slices(paths: list[str], needles: list[str]) -> list[dict[str, Any]]:
    texts = [Path(p) for p in paths if p.endswith((".txt", ".json"))]
    out: list[dict[str, Any]] = []
    for needle in needles[:MAX_SLICES]:
        for p in texts:
            if s := slice_for(p, needle, radius=2):
                if s not in out:
                    out.append(s)
                break
    return out


def _diff_needles(hunks: list[dict[str, Any]]) -> list[str]:
    needles = []
    for h in hunks:
        staged = h["staged"] if isinstance(h["staged"], str) else " ".join(h["staged"])
        before = h.get("before") if isinstance(h.get("before"), str) else ""
        needles.append(" ".join(f"{before} {staged}".split()[-14:]) or staged)
    return needles


def _version_item(rel: str, des: str, reason: str, new: dict, old: dict | None) -> dict:
    issuer, doc_name, key = rel.split("/")[1:4]
    src = source_copies(issuer, doc_name, key.removesuffix(".json"), new)
    item: dict[str, Any] = {
        "relpath": rel,
        "relpaths": [rel],
        "designator": des,
        "reason": reason,
        "title": new.get("title_at_revision"),
        "group": f"{issuer}/{doc_name}",
        "source_key": (src["source"] or src["extracted"] or [rel])[0],
        **src,
    }
    if old is None:  # full: new content
        item |= {
            "mode": "full",
            "staged_text": new.get("text") or "",
            "grouping": new.get("grouping_at_time"),
            "publication_cite": new.get("publication_cite"),
        }
        return item
    o, n = old.get("text") or "", new.get("text") or ""
    hunks: list[Any] = word_hunks(o, n) if reason == "words" else line_hunks(o, n)
    item |= {
        "mode": "diff",
        "changed": hunks[:MAX_HUNKS],
        "hunks_total": len(hunks),
        "chars": [len(o), len(n)],
        "source_context": _source_slices(
            src["extracted"] + src["source"], _diff_needles(hunks)
        ),
    }
    return item


def document_items(
    row: dict[str, Any], staged: Path, data: Path
) -> list[dict[str, Any]]:
    """One item per new, added or text-changed version of a provision file."""
    rel = row["relpath"]
    if rel.rsplit("/", 1)[-1].startswith("_"):
        return []
    new_doc, old_doc = _load(staged / rel), _load(data / rel)
    targets: list[tuple[str, str]] = []
    if row["status"] == "new":
        targets = [("new-file", d) for d in row["changes"][0]["versions"]]
    for ch in row["changes"]:
        targets += [("versions-added", d) for d in ch.get("versions_added", [])]
        if "designator" in ch and (
            "words" in ch or "markup-only" in ch or "layout_only" in ch
        ):
            reason = next(
                (t for t in ("words", "markup-only") if t in ch), "layout-only"
            )
            targets.append((reason, ch["designator"]))
    out = []
    for reason, des in targets:
        new = _version(new_doc, des)
        old = (
            None if reason in ("new-file", "versions-added") else _version(old_doc, des)
        )
        if new is None or not (new.get("text") or (old or {}).get("text")):
            continue  # nothing to read; a text that was removed is read as a diff
        out.append(_version_item(rel, des, reason, new, old))
    return out


# --- aircraft -----------------------------------------------------------------


def tcb_index(data: Path) -> set[str]:
    """Every TCB already in data/aircraft, as a canonical string."""
    seen = set()
    for p in sorted((data / "aircraft").glob("*/*.json")):
        for tcb in json.loads(p.read_text(encoding="utf-8")).get("tcb", []):
            seen.add(_tcb_sig(tcb))
    return seen


def _tcb_sig(tcb: dict[str, Any]) -> str:
    t = tcb["tcds"]
    return json.dumps(
        [t["issuer"], t["tcds_number"], t["revision"], tcb.get("certification_basis")],
        sort_keys=True,
        ensure_ascii=False,
    )


def _with_context(line: dict[str, Any], text_path: Path) -> dict[str, Any]:
    raw = str(line.get("raw_reference", ""))
    return {**line, "source_context": slice_for(text_path, raw, radius=2)}


def _tcb_diff_item(rel: str, tcb: dict[str, Any], ch: dict[str, Any]) -> dict[str, Any]:
    t = tcb["tcds"]
    pdf, text = tcds_paths(t)
    added, removed = ch.get("lines_added", []), ch.get("lines_removed", [])
    changed = ch.get("lines_changed", [])
    n_lines = len(tcb["certification_basis"])
    return {
        "mode": "diff",
        "reason": "references" if changed and not (added or removed) else "basis-lines",
        "relpath": rel,
        "relpaths": [rel],
        "tcds": t,
        "changed": {
            "lines_added": [_with_context(ln, text) for ln in added],
            "lines_removed": [_with_context(ln, text) for ln in removed],
            "lines_changed": [
                {
                    "old": c["old"],
                    "new": c["new"],
                    "source_context": slice_for(
                        text, str(c["new"].get("raw_reference", "")), 2
                    ),
                }
                for c in changed
            ],
        },
        "unchanged_lines": n_lines - len(added) - len(changed),
        "group": rel.split("/")[1],
        "source_key": pdf.as_posix(),
        "source": [pdf.as_posix()] if pdf.exists() else [],
        "source_text": [text.as_posix()] if text.exists() else [],
    }


def _tcb_full_item(rel: str, tcb: dict[str, Any], reason: str) -> dict[str, Any]:
    t = tcb["tcds"]
    pdf, text = tcds_paths(t)
    return {
        "mode": "full",
        "reason": reason,
        "relpath": rel,
        "relpaths": [rel],
        "tcds": t,
        "categories": tcb.get("categories"),
        "certification_basis": tcb["certification_basis"],
        "group": rel.split("/")[1],
        "source_key": pdf.as_posix(),
        "source": [pdf.as_posix()] if pdf.exists() else [],
        "source_text": [text.as_posix()] if text.exists() else [],
    }


def aircraft_items(
    row: dict[str, Any], staged: Path, known_tcbs: set[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """(items, notes). Notes name TCBs skipped as copies of data/."""
    rel = row["relpath"]
    record = _load(staged / rel) or {}
    tcbs = {
        f"{t['tcds']['issuer']} {t['tcds']['tcds_number']}": t
        for t in record.get("tcb", [])
    }
    # delta.py: a new file's single change is {"tcb": [keys]}; a changed file's
    # are {"tcb": key, ...} (_tcb_change), {"tcb_added": key}, {"tcb_removed":
    # key} or {"top_fields": ...}. Removed TCBs aren't in staged.
    full_keys: list[str] = []
    diffs: list[dict[str, Any]] = []
    if row["status"] == "new":
        full_keys = list(row["changes"][0]["tcb"])
    else:
        full_keys = [c["tcb_added"] for c in row["changes"] if "tcb_added" in c]
        diffs = [
            c
            for c in row["changes"]
            if isinstance(c.get("tcb"), str) and any(k.startswith("lines_") for k in c)
        ]
    items, notes = [], []
    for key in full_keys:
        if (tcb := tcbs.get(key)) is None:
            continue
        if _tcb_sig(tcb) in known_tcbs:
            notes.append(f"{key}: identical TCB already in data/")
            continue
        items.append(
            _tcb_full_item(
                rel, tcb, "new-file" if row["status"] == "new" else "tcb-added"
            )
        )
    for ch in diffs:
        if (tcb := tcbs.get(ch["tcb"])) is not None:
            items.append(_tcb_diff_item(rel, tcb, ch))
    return items, notes


def dedup(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge items whose content is identical apart from relpath."""
    merged: dict[str, dict[str, Any]] = {}
    for it in items:
        key = json.dumps(
            {k: v for k, v in it.items() if k not in ("relpath", "relpaths", "group")},
            sort_keys=True,
            ensure_ascii=False,
        )
        if key in merged:
            merged[key]["relpaths"] += it["relpaths"]
        else:
            merged[key] = it
    return list(merged.values())


def field_excerpt(source: str | None, needle: str) -> dict[str, Any] | None:
    """A fuller source excerpt for a field flag: 10 lines around the value,
    or the first 40 lines (the cover) when the value isn't found."""
    if not source or not (text := load_text(Path(source))):
        return None
    if m := locate(text, needle):
        return excerpt(text, m, 10)
    head = "\n".join(ln.replace("\f", "").rstrip() for ln in text.split("\n")[:40])
    return {"lines": "1-40", "page": 1, "text": head[:2500]}
