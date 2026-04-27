"""Tripwire: every file marked provenance.source=manual on disk must
appear in tests/manual_provenance_manifest.txt, and vice versa.

If a re-run of an emitter or a stray edit silently strips a manual
amendment, this test fails. If a new manual amendment is added, the
manifest must be updated in the same commit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_REGS = REPO_ROOT / "data" / "regulations"
MANIFEST = Path(__file__).parent / "manual_provenance_manifest.txt"


def _doc_has_manual(doc: object) -> bool:
    if not isinstance(doc, dict):
        return False
    prov = doc.get("provenance")
    if isinstance(prov, dict) and prov.get("source") == "manual":
        return True
    amends = doc.get("amendments")
    if isinstance(amends, list):
        for a in amends:
            if not isinstance(a, dict):
                continue
            ap = a.get("provenance")
            if isinstance(ap, dict) and ap.get("source") == "manual":
                return True
    return False


def _load_manifest() -> set[str]:
    if not MANIFEST.exists():
        return set()
    out: set[str] = set()
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.add(line)
    return out


def _scan_disk() -> set[str]:
    if not DATA_REGS.exists():
        return set()
    found: set[str] = set()
    for path in DATA_REGS.rglob("*.json"):
        try:
            with path.open(encoding="utf-8") as f:
                doc = json.load(f)
        except json.JSONDecodeError:
            continue
        if _doc_has_manual(doc):
            found.add(str(path.relative_to(DATA_REGS)))
    return found


def test_manual_provenance_manifest_matches_disk() -> None:
    on_disk = _scan_disk()
    manifest = _load_manifest()

    missing_from_manifest = on_disk - manifest
    missing_from_disk = manifest - on_disk

    msgs = []
    if missing_from_manifest:
        msgs.append(
            "Files contain manual provenance but are NOT listed in "
            f"tests/manual_provenance_manifest.txt: "
            f"{sorted(missing_from_manifest)}"
        )
    if missing_from_disk:
        msgs.append(
            "Manifest lists files that no longer carry manual provenance "
            "(possible silent loss of hand-edits): "
            f"{sorted(missing_from_disk)}"
        )
    if msgs:
        pytest.fail("\n".join(msgs))
