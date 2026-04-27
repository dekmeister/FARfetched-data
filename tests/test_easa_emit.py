"""Test tools.easa_emit dedupes via same_as_designator."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

import easa_emit  # noqa: E402


def _write_section(
    extract_dir: Path, amdt: str, section: str, title: str, body: str
) -> None:
    d = extract_dir / amdt
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{section}.txt").write_text(
        f"{title}\nSubpart A — General\n\n{body}\n", encoding="utf-8"
    )


def test_emit_dedupes_unchanged_section(tmp_path: Path, monkeypatch) -> None:
    extract = tmp_path / "extract"
    out_root = tmp_path / "staged"
    dates_tsv = tmp_path / "dates.tsv"
    dates_tsv.write_text("CS23-0\t2003-11-14\nCS23-1\t2009-12-12\nCS23-2\t2012-07-20\n")

    # Section 1 unchanged across all three amendments (whitespace differs).
    _write_section(extract, "CS23-0", "1", "Applicability", "Original text.")
    _write_section(extract, "CS23-1", "1", "Applicability", "Original text.")
    _write_section(extract, "CS23-2", "1", "Applicability", "Original   text.")
    # Section 3 changes at CS23-2.
    _write_section(extract, "CS23-0", "3", "Categories", "First version.")
    _write_section(extract, "CS23-1", "3", "Categories", "First version.")
    _write_section(extract, "CS23-2", "3", "Categories", "Second version.")

    monkeypatch.setattr(easa_emit, "EXTRACT_DIR", extract)
    monkeypatch.setattr(easa_emit, "DATES_TSV", dates_tsv)

    argv = ["easa_emit.py", "--data-root", str(out_root)]
    with patch.object(sys, "argv", argv):
        easa_emit.emit()

    # Section 1: text on CS23-0, aliases on CS23-1 and CS23-2.
    sec1 = json.loads((out_root / "easa" / "cs-23" / "1.json").read_text())
    amdts = {a["designator"]: a for a in sec1["amendments"]}
    assert "text" in amdts["CS23-0"]
    assert amdts["CS23-1"].get("same_as_designator") == "CS23-0"
    assert "text" not in amdts["CS23-1"]
    # CS23-2 chains back to CS23-0 (alias-of-alias resolves to source).
    assert amdts["CS23-2"].get("same_as_designator") == "CS23-0"

    # Section 3: text on CS23-0 and CS23-2, alias on CS23-1.
    sec3 = json.loads((out_root / "easa" / "cs-23" / "3.json").read_text())
    amdts3 = {a["designator"]: a for a in sec3["amendments"]}
    assert "text" in amdts3["CS23-0"]
    assert amdts3["CS23-1"].get("same_as_designator") == "CS23-0"
    assert "text" in amdts3["CS23-2"]
    assert amdts3["CS23-2"]["text"] == "Second version."

    # _part.json has all three amendments with effective dates.
    part = json.loads((out_root / "easa" / "cs-23" / "_part.json").read_text())
    assert part["authority"] == "EASA"
    assert part["part"] == "CS-23"
    assert "title_number" not in part
    designators = [a["designator"] for a in part["amendments"]]
    assert designators == ["CS23-0", "CS23-1", "CS23-2"]
