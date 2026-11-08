"""Cert-basis resolution rules (docs/DATA_FORMAT.md)."""

from __future__ import annotations

from dataclasses import dataclass, field


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

    ref_id: int
    effect: str
    doc: DocIndex
    to_ordinal: int | None
    skip: frozenset[int]  # revision ids
    provisions: tuple[int, ...]  # provision ids; empty = whole document
    paragraph: str | None


@dataclass(frozen=True)
class Resolved:
    provision_version_id: int
    ref_id: int
    paragraph: str | None


def resolve_entry(refs: list[Ref], label: str) -> tuple[list[Resolved], list[str]]:
    """Apply the resolution rules to the refs of one cert-basis entry.

    1. An include ref selects, for each provision in scope (its `provisions`,
       or the whole document), the version at the highest revision <= `to`
       that is not skipped. Provisions with no such version are out, and so
       are provisions whose selected version deleted them (document-wide refs
       only: a scoped or paragraph ref to a deleted provision is an error).
    2. Scoped results (refs with `provisions`) override wide ones.
    3. Paragraph refs add a row, unless they land on the whole-provision version.
    4. Exclude refs remove provisions from the wide results.
    Anything ambiguous is an error, not a guess.
    """
    errors: list[str] = []
    wide: dict[int, Resolved] = {}
    scoped: dict[int, Resolved] = {}
    paragraphs: list[tuple[int, Resolved]] = []
    excluded: set[int] = set()

    def name(ref: Ref, pid: int) -> str:
        return f"{ref.doc.numbers[pid]}"

    for ref in refs:
        if ref.effect != "include":
            continue
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
            errors.extend(
                f"{label}: ref {ref.ref_id} resolves {name(ref, pid)} to a "
                f"revision that deleted it"
                for pid in gone
            )
            continue
        if not picked:
            errors.append(f"{label}: ref {ref.ref_id} resolves to no provisions")
            continue
        for pid, pv in picked.items():
            row = Resolved(pv, ref.ref_id, ref.paragraph)
            if ref.paragraph is not None:
                paragraphs.append((pid, row))
                continue
            target = scoped if ref.provisions else wide
            prior = target.get(pid)
            if prior is not None and prior.provision_version_id != pv:
                kind = "scoped" if ref.provisions else "document-wide"
                errors.append(
                    f"{label}: two {kind} refs resolve {name(ref, pid)} "
                    f"to different versions"
                )
            target.setdefault(pid, row)

    for ref in refs:
        if ref.effect != "exclude":
            continue
        for pid in ref.provisions:
            if pid in scoped or any(p == pid for p, _ in paragraphs):
                errors.append(
                    f"{label}: {name(ref, pid)} is both excluded and included"
                )
            elif pid not in wide:
                errors.append(f"{label}: exclude of {name(ref, pid)} removes nothing")
            excluded.add(pid)

    whole = {pid: r for pid, r in wide.items() if pid not in excluded}
    whole.update(scoped)
    out: dict[int, Resolved] = {r.provision_version_id: r for r in whole.values()}
    for pid, row in paragraphs:
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
