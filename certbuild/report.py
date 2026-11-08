"""The build report and git state."""

from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path
from typing import TypedDict

from certbuild.aircraft import ParagraphRefStats
from certbuild.ddl import SCHEMA_VERSION
from certbuild.provisions import TextStats
from certbuild.similarity import similarity_report


def git_sha(data_dir: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(data_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip() or None


def git_dirty_paths(data_dir: Path) -> list[str] | None:
    """Uncommitted changes under data_dir (repo-relative), or None outside git.

    Reported, not stored in the DB: build_info.git_sha names HEAD, and this
    says whether the build also included files HEAD doesn't have.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(data_dir), "status", "--porcelain=v1", "-z"]
            + ["--untracked-files=all", "--", "."],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    paths: list[str] = []
    fields = iter(out.stdout.split("\0"))
    for entry in fields:
        if not entry:
            continue
        paths.append(entry[3:])
        if "R" in entry[:2] or "C" in entry[:2]:
            next(fields, None)  # the rename/copy source follows
    return sorted(paths)


# TypedDict rather than dataclass: keeps the return dict-serialisable for the report.
class BuildReport(TypedDict):
    schema_version: int
    tables: dict[str, int]
    documents: dict[str, dict[str, int]]
    text_missing: int
    deleted: int
    provenance: dict[str, int]
    structured_versions: int
    flat_versions: int
    label_gaps: int
    paragraph_refs_verified: int
    paragraph_refs_unverifiable: int
    similarity: dict[str, int]
    git_dirty: bool | None
    git_dirty_paths: list[str]
    unresolved_references: list[str]


def build_report(
    conn: sqlite3.Connection,
    unresolved: list[str],
    text_stats: TextStats,
    para_stats: ParagraphRefStats,
    dirty_paths: list[str] | None,
) -> BuildReport:
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    # Table names come from sqlite_master, not from data.
    counts = {
        t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "tables": counts,
        "documents": {
            f"{issuer}/{slug}": {
                "revisions": revs,
                "provisions": provs,
                "versions": vers,
                "renumbered": renum,
            }
            for issuer, slug, revs, provs, vers, renum in conn.execute(
                """
                SELECT i.code, d.slug,
                  (SELECT count(*) FROM document_revisions r
                   WHERE r.document_id = d.id),
                  (SELECT count(*) FROM provisions p WHERE p.document_id = d.id),
                  (SELECT count(*) FROM provision_versions v
                   WHERE v.document_id = d.id),
                  (SELECT count(DISTINCT v.provision_id) FROM provision_versions v
                   JOIN provisions p ON p.id = v.provision_id
                   WHERE v.document_id = d.id AND v.number <> p.number)
                FROM documents d JOIN issuers i ON i.id = d.issuer_id
                ORDER BY i.code, d.slug
                """
            )
        },
        "text_missing": conn.execute(
            "SELECT count(*) FROM provision_versions WHERE text_missing"
        ).fetchone()[0],
        "deleted": conn.execute(
            "SELECT count(*) FROM provision_versions WHERE deleted"
        ).fetchone()[0],
        "provenance": dict(
            conn.execute(
                "SELECT provenance, count(*) FROM provision_versions "
                "GROUP BY provenance ORDER BY provenance"
            ).fetchall()
        ),
        "structured_versions": text_stats.structured,
        "flat_versions": text_stats.flat,
        "label_gaps": text_stats.label_gaps,
        "paragraph_refs_verified": para_stats.verified,
        "paragraph_refs_unverifiable": para_stats.unverifiable,
        "similarity": similarity_report(conn),
        "git_dirty": None if dirty_paths is None else bool(dirty_paths),
        "git_dirty_paths": dirty_paths or [],
        "unresolved_references": unresolved,
    }
