"""Cert-basis resolution rules (docs/DATA_FORMAT.md §Resolution).

Pure: this module never imports sqlite3. It reads a `DocIndex` (plain data
built by aircraft.py from the DB) and returns ids and error messages, so
every rule can be tested without staging a data tree (tests/test_resolve.py).
Errors are collected, never raised: the caller decides when to stop.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

DocKey = tuple[str, str]  # (issuer, document slug)


@dataclass
class DocIndex:
    """In-memory view of one document, for resolving cert-basis refs."""

    document_id: int
    slug: str = ""
    # printed number -> ids of every provision that has ever carried it
    carriers: dict[str, set[int]] = field(default_factory=dict)
    revisions: dict[str, tuple[int, int]] = field(
        default_factory=dict
    )  # designator -> (id, ordinal)
    # provision id -> [(ordinal, revision id, provision version id)]
    versions: dict[int, list[tuple[int, int, int]]] = field(default_factory=dict)
    numbers: dict[int, str] = field(default_factory=dict)  # provision id -> number
    deleted: set[int] = field(default_factory=set)  # deleted provision version ids
    printed: dict[int, str] = field(default_factory=dict)  # version id -> number

    @classmethod
    def from_rows(
        cls,
        document_id: int,
        slug: str,
        provisions: Iterable[tuple[int, str]],
        revisions: Iterable[tuple[int, str, int]],
        versions: Iterable[tuple[int, int, int, int, int, str]],
    ) -> DocIndex:
        """Build from (provision id, number), (revision id, designator,
        ordinal) and (provision id, ordinal, revision id, version id,
        deleted, printed number) rows."""
        idx = cls(document_id, slug)
        for pid, number in provisions:
            idx.numbers[pid] = number
        for rid, designator, ordinal in revisions:
            idx.revisions[designator] = (rid, ordinal)
        for pid, ordinal, rid, pv_id, deleted, number in versions:
            idx.versions.setdefault(pid, []).append((ordinal, rid, pv_id))
            idx.carriers.setdefault(number, set()).add(pid)
            idx.printed[pv_id] = number
            if deleted:
                idx.deleted.add(pv_id)
        return idx

    def provision_at(self, number: str, ordinal: int) -> tuple[int | None, str]:
        """The provision that carried printed `number` at the revision with
        this ordinal (the number of its latest version up to it, skips not
        applied). One in force wins over one the revision range deleted.
        Return (id, "") or (None, why)."""
        if number not in self.carriers:
            return None, f"unknown provision {self.slug}.{number}"
        live: list[int] = []
        gone: list[int] = []
        for pid in sorted(self.carriers[number]):
            at = [(o, pv) for o, _, pv in self.versions.get(pid, []) if o <= ordinal]
            if not at:
                continue
            pv = max(at)[1]
            if self.printed[pv] == number:
                (gone if pv in self.deleted else live).append(pid)
        found = live or gone
        if len(found) == 1:
            return found[0], ""
        if not found:
            return None, f"no provision {self.slug}.{number} at that revision"
        return None, f"{self.slug}.{number} names {len(found)} provisions there"

    def pick(self, provision_id: int, to_ordinal: int, skip: set[int]) -> int | None:
        """Version of a provision in force at `to`, ignoring skipped revisions."""
        best: tuple[int, int] | None = None
        for ordinal, rev_id, pv_id in self.versions.get(provision_id, []):
            if ordinal <= to_ordinal and rev_id not in skip:
                if best is None or ordinal > best[0]:
                    best = (ordinal, pv_id)
        return best[1] if best else None


@dataclass(frozen=True)
class Ref:
    """A cert-basis ref with designators and numbers resolved to ids."""

    effect: str
    doc: DocIndex
    to_revision_id: int | None
    to_ordinal: int | None
    skip: tuple[int, ...]  # revision ids, in the order the ref lists them
    provisions: tuple[int, ...]  # provision ids; empty = whole document
    paragraph: str | None
    ref_id: int = 0  # cert_basis_refs.id, set once the ref is inserted


@dataclass(frozen=True)
class Resolved:
    provision_version_id: int
    ref_id: int
    paragraph: str | None


def exclude_ordinals(
    refs: list[dict[str, Any]], doc_for: Callable[[DocKey], DocIndex | None]
) -> dict[DocKey, int]:
    """Per document, the highest `to` among an entry's include refs: the
    revision at which its exclude refs' numbers are read."""
    out: dict[DocKey, int] = {}
    for ref in refs:
        if ref.get("effect", "include") != "include" or "to" not in ref:
            continue
        key = (ref["issuer"], ref["document"])
        doc = doc_for(key)
        rev = doc.revisions.get(ref["to"]) if doc else None
        if rev is not None:
            out[key] = max(out.get(key, rev[1]), rev[1])
    return out


def resolve_ref(
    ref: dict[str, Any],
    doc: DocIndex | None,
    where: str,
    exclude_at: dict[DocKey, int],
) -> tuple[Ref | None, list[str]]:
    """Resolve one JSON ref's designators and printed numbers in `doc` (None:
    the document is unknown). Return it resolved, or the errors.

    `provisions` are printed numbers, read at the ref's `to` (an exclude ref:
    at `exclude_at`, the entry's highest include `to` in the document)."""
    key = (ref["issuer"], ref["document"])
    if doc is None:
        return None, [f"{where}: unknown document {key[0]}/{key[1]}"]

    errors: list[str] = []
    to_rev: tuple[int, int] | None = None
    if "to" in ref:
        to_rev = doc.revisions.get(ref["to"])
        if to_rev is None:
            errors.append(f"{where}: unknown revision {ref['to']!r} in {key[1]}")
    skip = _skips(ref, doc, to_rev, where, errors)
    provisions: list[int] = []
    at = to_rev[1] if to_rev else exclude_at.get(key)
    for number in ref.get("provisions", []):
        if at is None:
            if "to" not in ref:
                errors.append(
                    f"{where}: exclude of {key[1]}.{number} has no include ref "
                    f"in {key[1]} to read its number at"
                )
            continue
        pid, why = doc.provision_at(number, at)
        if pid is None:
            errors.append(f"{where}: {why}")
        else:
            provisions.append(pid)
    if errors:
        return None, errors
    return (
        Ref(
            effect=ref.get("effect", "include"),
            doc=doc,
            to_revision_id=to_rev[0] if to_rev else None,
            to_ordinal=to_rev[1] if to_rev else None,
            skip=tuple(skip),
            provisions=tuple(provisions),
            paragraph=ref.get("paragraph"),
        ),
        [],
    )


def _skips(
    ref: dict[str, Any],
    doc: DocIndex,
    to_rev: tuple[int, int] | None,
    where: str,
    errors: list[str],
) -> list[int]:
    """Revision ids of the ref's `skip` designators; faults go to `errors`."""
    skip: list[int] = []
    for d in ref.get("skip", []):
        rev = doc.revisions.get(d)
        if rev is None:
            errors.append(f"{where}: unknown skip revision {d!r} in {ref['document']}")
        elif to_rev is not None and rev[1] >= to_rev[1]:
            errors.append(f"{where}: skip {d!r} is not earlier than to {ref['to']!r}")
        else:
            skip.append(rev[0])
    return skip


@dataclass
class _Selection:
    """What an entry's refs select, by provision id, before merging."""

    wide: dict[int, Resolved] = field(default_factory=dict)
    scoped: dict[int, Resolved] = field(default_factory=dict)
    paragraphs: list[tuple[int, Resolved]] = field(default_factory=list)
    excluded: set[int] = field(default_factory=set)


def resolve_entry(refs: list[Ref], label: str) -> tuple[list[Resolved], list[str]]:
    """Apply the resolution rules to the refs of one cert-basis entry.

    1. An include ref selects, for each provision in scope (its `provisions`,
       or the whole document), the version at the highest revision <= `to`
       that is not skipped. Provisions with no such version are out, and so
       are provisions whose selected version deleted them (document-wide refs
       only: a scoped or paragraph ref to a deleted provision is an error).
       (`_include`)
    2. Scoped results (refs with `provisions`) override wide ones. (`_merge`)
    3. Paragraph refs add a row, unless they land on the whole-provision
       version. (`_merge`)
    4. Exclude refs remove provisions from the wide results. (`_exclude`)
    Anything ambiguous is an error, not a guess.
    """
    sel = _Selection()
    errors: list[str] = []
    for ref in refs:
        if ref.effect == "include":
            errors.extend(_include(ref, sel, label))
    for ref in refs:
        if ref.effect == "exclude":
            errors.extend(_exclude(ref, sel, label))
    rows, merge_errors = _merge(sel, label)
    return rows, errors + merge_errors


def _name(ref: Ref, pid: int) -> str:
    return f"{ref.doc.numbers[pid]}"


def _include(ref: Ref, sel: _Selection, label: str) -> list[str]:
    """Rule 1: add what one include ref selects to `sel`."""
    assert ref.to_ordinal is not None
    scope = ref.provisions or tuple(ref.doc.numbers)
    picked = {
        pid: pv
        for pid in scope
        if (pv := ref.doc.pick(pid, ref.to_ordinal, set(ref.skip))) is not None
    }
    gone = [pid for pid, pv in picked.items() if pv in ref.doc.deleted]
    for pid in gone:
        del picked[pid]
    if ref.provisions and gone:
        return [
            f"{label}: ref {ref.ref_id} resolves {_name(ref, pid)} to a "
            f"revision that deleted it"
            for pid in gone
        ]
    if not picked:
        return [f"{label}: ref {ref.ref_id} resolves to no provisions"]
    errors: list[str] = []
    for pid, pv in picked.items():
        row = Resolved(pv, ref.ref_id, ref.paragraph)
        if ref.paragraph is not None:
            sel.paragraphs.append((pid, row))
            continue
        target = sel.scoped if ref.provisions else sel.wide
        prior = target.get(pid)
        if prior is not None and prior.provision_version_id != pv:
            kind = "scoped" if ref.provisions else "document-wide"
            errors.append(
                f"{label}: two {kind} refs resolve {_name(ref, pid)} "
                f"to different versions"
            )
        target.setdefault(pid, row)
    return errors


def _exclude(ref: Ref, sel: _Selection, label: str) -> list[str]:
    """Rule 4: mark one exclude ref's provisions as removed."""
    errors: list[str] = []
    for pid in ref.provisions:
        if pid in sel.scoped or any(p == pid for p, _ in sel.paragraphs):
            errors.append(f"{label}: {_name(ref, pid)} is both excluded and included")
        elif pid not in sel.wide:
            errors.append(f"{label}: exclude of {_name(ref, pid)} removes nothing")
        sel.excluded.add(pid)
    return errors


def _merge(sel: _Selection, label: str) -> tuple[list[Resolved], list[str]]:
    """Rules 2 and 3: wide minus excluded, scoped over wide, then paragraph
    rows that add something."""
    errors: list[str] = []
    whole = {pid: r for pid, r in sel.wide.items() if pid not in sel.excluded}
    whole.update(sel.scoped)
    out: dict[int, Resolved] = {r.provision_version_id: r for r in whole.values()}
    for pid, row in sel.paragraphs:
        if pid in whole and whole[pid].provision_version_id == row.provision_version_id:
            continue
        if row.provision_version_id in out:
            errors.append(
                f"{label}: two paragraph refs resolve to the same version of "
                f"provision id {pid}"
            )
            continue
        out[row.provision_version_id] = row
    return list(out.values()), errors
