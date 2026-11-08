"""The one copy of the JSON record shapes the build tests stage.

Each builder returns a record that passes the schema with the fewest fields;
keywords fill in the rest. When a schema gains a required field, add it here
and every test picks it up. Test files bind their own defaults with
`functools.partial` (an issuer, a document) instead of copying a shape.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from certbuild.errors import BuildError
from certbuild.pipeline import build

Record = dict[str, Any]


# ---------------------------------------------------------------------------
# documents/{issuer}/{slug}/_document.json


def document(
    issuer: str,
    slug: str,
    revisions: list[tuple[str, int, str]],
    *,
    doc_kind: str = "regulation",
    code: str | None = None,
    title: str | None = None,
) -> Record:
    """`revisions` are (designator, ordinal, effective date)."""
    return {
        "issuer": issuer,
        "doc_kind": doc_kind,
        "code": code if code is not None else slug.upper(),
        "slug": slug,
        "title": title,
        "revisions": [
            {"designator": d, "ordinal": o, "effective_date": e}
            for d, o, e in revisions
        ],
    }


def faa_part(slug: str, ordinals: list[int], issuer: str = "FAA") -> Record:
    """A 14 CFR part whose revision n is `{slug}-{n}`."""
    return document(
        issuer,
        slug,
        [(f"{slug}-{n}", n, f"{1965 + n // 2:04d}-01-01") for n in ordinals],
        code=f"14 CFR {slug}",
    )


# ---------------------------------------------------------------------------
# documents/{issuer}/{document}/{key}.json


def version(
    designator: str, *, title: str = "Title", text: str | None = None, **extra: Any
) -> Record:
    """A live version; its text defaults to `text at {designator}`."""
    return {
        "designator": designator,
        "title_at_revision": title,
        "text": f"text at {designator}" if text is None else text,
        **extra,
    }


def deleted(designator: str, *, title: str = "Title", **extra: Any) -> Record:
    return {
        "designator": designator,
        "title_at_revision": title,
        "deleted": True,
        **extra,
    }


def provision(
    issuer: str,
    document: str,
    number: str,
    versions: list[Record],
    *,
    key: str | None = None,
    grouping: str | None = None,
    title: str = "Title",
) -> Record:
    return {
        "issuer": issuer,
        "document": document,
        "key": number if key is None else key,
        "number": number,
        "current_grouping": grouping,
        "canonical_title": title,
        "versions": versions,
    }


# ---------------------------------------------------------------------------
# aircraft/{model}.json


def ref(issuer: str, document: str, to: str, **extra: Any) -> Record:
    return {"issuer": issuer, "document": document, "to": to, **extra}


def exclude(issuer: str, document: str, *numbers: str) -> Record:
    return {
        "issuer": issuer,
        "document": document,
        "effect": "exclude",
        "provisions": list(numbers),
    }


def entry(
    refs: list[Record],
    display_order: int = 1,
    *,
    entry_type: str = "regulation",
    raw_reference: str = "verbatim TCDS text",
    **extra: Any,
) -> Record:
    return {
        "display_order": display_order,
        "entry_type": entry_type,
        "raw_reference": raw_reference,
        "applicability": None,
        "applicability_notes": None,
        "references": refs,
        **extra,
    }


def aircraft(
    entries: list[Record],
    *,
    model: str = "Dummy",
    tcds: Record | None = None,
    categories: tuple[str, ...] = ("normal",),
) -> Record:
    return {
        "manufacturer": "Dummy Mfg",
        "model_designation": model,
        "common_name": None,
        "notes": None,
        "tcb": [
            {
                "tcds": tcds or {"issuer": "FAA", "tcds_number": "DUMMY1"},
                "categories": list(categories),
                "notes": None,
                "certification_basis": entries,
            }
        ],
    }


# ---------------------------------------------------------------------------
# Staging and building


def stage(
    tmp_path: Path,
    documents: list[Record],
    provisions: list[Record],
    models: list[Record] | None = None,
) -> Path:
    """Write a data/ tree under tmp_path at the paths the build checks."""
    data = tmp_path / "data"
    for d in documents:
        doc_dir = data / "documents" / d["issuer"].lower() / d["slug"]
        doc_dir.mkdir(parents=True, exist_ok=True)
        (doc_dir / "_document.json").write_text(json.dumps(d))
    for p in provisions:
        doc_dir = data / "documents" / p["issuer"].lower() / p["document"]
        doc_dir.mkdir(parents=True, exist_ok=True)
        (doc_dir / f"{p['key']}.json").write_text(json.dumps(p))
    (data / "aircraft").mkdir(parents=True, exist_ok=True)
    for a in models or []:
        slug = a["model_designation"].replace(" ", "-").lower()
        (data / "aircraft" / f"{slug}.json").write_text(json.dumps(a))
    return data


def build_tree(
    tmp_path: Path,
    documents: list[Record],
    provisions: list[Record],
    models: list[Record] | None = None,
) -> Path:
    """Stage and build; return the DB path."""
    out = tmp_path / "cert_basis.sqlite"
    build(stage(tmp_path, documents, provisions, models), out)
    return out


def build_fails(
    tmp_path: Path,
    documents: list[Record],
    provisions: list[Record],
    models: list[Record] | None = None,
) -> str:
    """Stage and build, expecting a BuildError and no output; return its text."""
    with pytest.raises(BuildError) as ei:
        build_tree(tmp_path, documents, provisions, models)
    assert not (tmp_path / "cert_basis.sqlite").exists()
    return str(ei.value)


# ---------------------------------------------------------------------------
# A 14 CFR world: Part 23 with revisions 23-0 .. 23-62 (the resolution tests)


def cfr_version(designator: str, **extra: Any) -> Record:
    return version(
        designator,
        title="Dummy title",
        publication_cite="1 FR 1",
        source_url="https://example.com",
        **extra,
    )


def cfr_provision(slug: str, number: str, ordinals: list[int]) -> Record:
    """A provision with a version at each of `ordinals` (`{slug}-{n}`)."""
    return provision(
        "FAA",
        slug,
        number,
        [cfr_version(f"{slug}-{n}") for n in ordinals],
        grouping="A",
        title=f"Dummy §{slug}.{number}",
    )


def cfr_ref(to: str, document: str = "23", **extra: Any) -> Record:
    return ref("FAA", document, to, **extra)


def cfr_aircraft(
    entries: list[Record], model: str = "DummyModel", tcds: Record | None = None
) -> Record:
    return aircraft(entries, model=model, tcds=tcds)


def build_part23(
    tmp_path: Path, provisions: list[Record], entries: list[Record]
) -> Path:
    """Build Part 23 with revisions 0..62, plus one aircraft if `entries`."""
    return build_tree(
        tmp_path,
        [faa_part("23", list(range(63)))],
        provisions,
        [cfr_aircraft(entries)] if entries else [],
    )


def part23_fails(
    tmp_path: Path, provisions: list[Record], entries: list[Record]
) -> str:
    with pytest.raises(BuildError) as ei:
        build_part23(tmp_path, provisions, entries)
    assert not (tmp_path / "cert_basis.sqlite").exists()
    return str(ei.value)


# ---------------------------------------------------------------------------
# Reading results


def resolved_versions(db: Path, by: str = "number") -> set[tuple[str, str]]:
    """(provision number or key, designator) of every resolved row."""
    column = {"number": "p.number", "key": "p.key"}[by]
    with sqlite3.connect(db) as conn:
        return set(
            conn.execute(
                # `column` is one of two constants above, never data.
                f"SELECT {column}, dr.designator FROM cert_basis_resolved r "
                "JOIN provision_versions pv ON pv.id = r.provision_version_id "
                "JOIN provisions p ON p.id = pv.provision_id "
                "JOIN document_revisions dr ON dr.id = pv.revision_id"
            ).fetchall()
        )


def resolved(
    db: Path, tcds_number: str | None = None, model: str | None = None
) -> set[tuple[int, str, str, str | None]]:
    """(display_order, provision number, designator, paragraph) per resolved
    row, optionally only for one TCDS and/or one model designation (a TCDS
    covers many models, each with its own TCB)."""
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            """
            SELECT e.display_order, p.number, dr.designator, r.paragraph
            FROM cert_basis_resolved r
            JOIN cert_basis_entries e ON e.id = r.entry_id
            JOIN tcb ON tcb.id = e.tcb_id
            JOIN tcds ON tcds.id = tcb.tcds_id
            JOIN aircraft_models m ON m.id = tcb.model_id
            JOIN provision_versions pv ON pv.id = r.provision_version_id
            JOIN provisions p ON p.id = pv.provision_id
            JOIN document_revisions dr ON dr.id = pv.revision_id
            WHERE (?1 IS NULL OR tcds.tcds_number = ?1)
              AND (?2 IS NULL OR m.model_designation = ?2)
            """,
            (tcds_number, model),
        ).fetchall()
    return set(rows)
