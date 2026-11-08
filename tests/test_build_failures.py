"""Fail-loud build checks, the CLI, atomic output and git state."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import factories as fx
import pytest

from build import main
from certbuild.errors import BuildError
from certbuild.pipeline import build, check


# ---------------------------------------------------------------------------
# fail-loud build checks


class TestBuildFailures:
    def test_undeclared_revision_fails(self, tmp_path: Path) -> None:
        data = fx.stage(
            tmp_path,
            [fx.faa_part("25", [23])],
            [fx.cfr_provision("25", "1309", [99])],
            [],
        )
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "cert_basis.sqlite")
        assert "25-99" in str(ei.value)

    def test_duplicate_version_names_the_file(self, tmp_path: Path) -> None:
        # The CAR 3 §3.735 case: one revision listed twice in one provision.
        prov = fx.cfr_provision("23", "735", [0, 0])
        data = fx.stage(tmp_path, [fx.faa_part("23", [0])], [prov], [])
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "cert_basis.sqlite")
        assert "735.json" in str(ei.value)
        assert "UNIQUE constraint failed" in str(ei.value)

    def test_duplicate_display_order_fails(self, tmp_path: Path) -> None:
        entries = [fx.entry([], display_order=1), fx.entry([], display_order=1)]
        assert "UNIQUE constraint failed" in fx.part23_fails(
            tmp_path, [fx.cfr_provision("23", "1", [0])], entries
        )

    def test_future_action_date_fails(self, tmp_path: Path) -> None:
        # A two-digit year read with strptime's %y pivot: 3/25/64 -> 2064.
        prov = fx.cfr_provision("23", "1", [])
        prov["versions"] = [
            fx.cfr_version(
                "23-0", actions=[{"type": "nprm", "issued_on": "2064-03-25"}]
            )
        ]
        message = fx.part23_fails(tmp_path, [prov], [])
        assert "version_actions.issued_on" in message and "2064-03-25" in message

    def test_conflicting_tcds_metadata_fails(self, tmp_path: Path) -> None:
        tcds = {"issuer": "FAA", "tcds_number": "3A12", "revision": "42"}
        data = fx.stage(
            tmp_path,
            [fx.faa_part("23", [0])],
            [fx.cfr_provision("23", "1", [0])],
            [
                fx.cfr_aircraft([fx.entry([])], model="172", tcds=tcds),
                fx.cfr_aircraft(
                    [fx.entry([])], model="172A", tcds={**tcds, "revision": "43"}
                ),
            ],
        )
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "cert_basis.sqlite")
        assert "TCDS 3A12 metadata" in str(ei.value)

    def test_shared_tcds_with_same_metadata_is_fine(self, tmp_path: Path) -> None:
        tcds = {"issuer": "FAA", "tcds_number": "3A12", "revision": "42"}
        data = fx.stage(
            tmp_path,
            [fx.faa_part("23", [0])],
            [fx.cfr_provision("23", "1", [0])],
            [
                fx.cfr_aircraft([fx.entry([])], model="172", tcds=tcds),
                fx.cfr_aircraft([fx.entry([])], model="172A", tcds=tcds),
            ],
        )
        report = build(data, tmp_path / "cert_basis.sqlite")
        assert report["tables"]["tcds"] == 1
        assert report["tables"]["tcb"] == 2

    def test_path_must_match_content(self, tmp_path: Path) -> None:
        data = fx.stage(
            tmp_path, [fx.faa_part("23", [0])], [fx.cfr_provision("23", "1", [0])], []
        )
        wrong = data / "documents" / "faa" / "23" / "2.json"
        (data / "documents" / "faa" / "23" / "1.json").rename(wrong)
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "cert_basis.sqlite")
        assert "expected at documents/faa/23/1.json" in str(ei.value)

    def test_check_catches_path_mismatch(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        data = fx.stage(
            tmp_path, [fx.faa_part("23", [0])], [fx.cfr_provision("23", "1", [0])], []
        )
        assert check(data) == []
        (data / "documents" / "faa" / "23" / "1.json").rename(
            data / "documents" / "faa" / "23" / "2.json"
        )
        assert main(["--check", "--data-dir", str(data)]) == 1
        assert "expected at documents/faa/23/1.json" in capsys.readouterr().err

    def test_validation_failure_fails_build_before_sqlite(self, tmp_path: Path) -> None:
        prov = fx.cfr_provision("25", "1309", [23])
        del prov["canonical_title"]
        data = fx.stage(tmp_path, [fx.faa_part("25", [23])], [prov], [])
        with pytest.raises(BuildError):
            build(data, tmp_path / "cert_basis.sqlite")
        assert not (tmp_path / "cert_basis.sqlite").exists()
        assert not (tmp_path / "cert_basis.sqlite.new").exists()


class TestAtomicWrite:
    def test_rebuild_overwrites_and_clears_stale_wal(self, tmp_path: Path) -> None:
        data = fx.stage(
            tmp_path, [fx.faa_part("23", [0])], [fx.cfr_provision("23", "1", [0])], []
        )
        out = tmp_path / "cert_basis.sqlite"
        build(data, out)
        # Sidecars left by an old WAL-mode build must not survive next to the
        # new file, or SQLite could replay a stale WAL into it.
        stale = [out.with_name(out.name + s) for s in ("-wal", "-shm")]
        for p in stale:
            p.write_bytes(b"stale")
        build(data, out)
        assert out.exists()
        assert not out.with_suffix(out.suffix + ".new").exists()
        assert not any(p.exists() for p in stale)

    def test_failed_report_write_keeps_the_old_pair(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        data = fx.stage(
            tmp_path, [fx.faa_part("23", [0])], [fx.cfr_provision("23", "1", [0])], []
        )
        out = tmp_path / "cert_basis.sqlite"
        report = tmp_path / "cert_basis_report.json"
        build(data, out)
        before = (out.read_bytes(), report.read_bytes())

        def fail(*args: object, **kwargs: object) -> str:
            raise OSError("disk full")

        monkeypatch.setattr(json, "dumps", fail)
        with pytest.raises(OSError, match="disk full"):
            build(data, out)
        assert (out.read_bytes(), report.read_bytes()) == before
        assert not out.with_name(out.name + ".new").exists()
        assert not report.with_name(report.name + ".new").exists()


class TestGitDirty:
    """The report says whether data/ had uncommitted changes (BUILD-5)."""

    @staticmethod
    def _git(repo: Path, *args: str) -> None:
        subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
            + list(args),
            check=True,
            capture_output=True,
        )

    def _report(self, data: Path, out: Path) -> dict:
        build(data, out)
        return json.loads(out.with_name("cert_basis_report.json").read_text())

    def test_clean_modified_and_untracked(self, tmp_path: Path) -> None:
        data = fx.stage(
            tmp_path, [fx.faa_part("23", [0])], [fx.cfr_provision("23", "1", [0])], []
        )
        (tmp_path / "other.txt").write_text("outside data/: not reported")
        self._git(tmp_path, "init", "-q")
        self._git(tmp_path, "add", "data")
        self._git(tmp_path, "commit", "-q", "-m", "init")
        out = tmp_path / "out" / "cert_basis.sqlite"
        out.parent.mkdir()

        report = self._report(data, out)
        assert (report["git_dirty"], report["git_dirty_paths"]) == (False, [])

        prov = fx.cfr_provision("23", "1", [0])
        prov["canonical_title"] = "Changed"
        (data / "documents" / "faa" / "23" / "1.json").write_text(json.dumps(prov))
        (data / "documents" / "faa" / "23" / "2.json").write_text(
            json.dumps(fx.cfr_provision("23", "2", [0]))
        )
        report = self._report(data, out)
        assert report["git_dirty"] is True
        assert report["git_dirty_paths"] == [
            "data/documents/faa/23/1.json",
            "data/documents/faa/23/2.json",
        ]

    def test_outside_git_is_unknown(self, tmp_path: Path) -> None:
        data = fx.stage(tmp_path, [fx.faa_part("23", [0])], [], [])
        report = self._report(data, tmp_path / "cert_basis.sqlite")
        assert (report["git_dirty"], report["git_dirty_paths"]) == (None, [])


# ---------------------------------------------------------------------------
# one run lists every fault of the failing stage (certbuild/errors.py)


class TestCollectsAll:
    def test_faults_in_two_provision_files(self, tmp_path: Path) -> None:
        bad_alias = fx.cfr_provision("23", "1301", [0])
        bad_alias["versions"].append(
            fx.cfr_version("23-1", same_as_designator="23-9") | {"text": None}
        )
        del bad_alias["versions"][1]["text"]
        bad_number = fx.cfr_provision("23", "1309", [0])
        bad_number["number"] = "1310"
        bad_number["versions"][0]["number"] = "1309"
        msg = fx.build_fails(
            tmp_path, [fx.faa_part("23", [0, 1])], [bad_alias, bad_number]
        )
        assert "aliases unknown designator '23-9'" in msg
        assert "is not the number printed at the latest version" in msg

    def test_path_and_text_faults_together(self, tmp_path: Path) -> None:
        misplaced = fx.cfr_provision("23", "1301", [0])
        misplaced["key"] = "1301"
        bad_text = fx.cfr_provision("23", "1309", [0])
        bad_text["versions"][0]["text"] = "(a) x\n  y $$ z"
        data = fx.stage(tmp_path, [fx.faa_part("23", [0])], [bad_text])
        doc_dir = data / "documents" / "faa" / "23"
        (doc_dir / "wrong-name.json").write_text(json.dumps(misplaced))
        with pytest.raises(BuildError) as ei:
            build(data, tmp_path / "out.sqlite")
        assert any("wrong-name.json: expected at" in e for e in ei.value.errors), (
            ei.value.errors
        )
        assert any("outside a formula line" in e for e in ei.value.errors)
        assert check(data) == ei.value.errors

    def test_tcds_conflict_and_unresolved_ref_together(self, tmp_path: Path) -> None:
        tcds = {"issuer": "FAA", "tcds_number": "A1", "revision": "1"}
        first = fx.cfr_aircraft([fx.entry([fx.cfr_ref("23-0")])], "M1", tcds)
        second = fx.cfr_aircraft(
            [fx.entry([fx.cfr_ref("23-7")])], "M2", tcds | {"revision": "2"}
        )
        msg = fx.build_fails(
            tmp_path,
            [fx.faa_part("23", [0])],
            [fx.cfr_provision("23", "1301", [0])],
            [first, second],
        )
        assert "TCDS A1 metadata" in msg
        assert "unknown revision '23-7'" in msg


def test_coverage_counts_entries_tcbs_and_models(tmp_path: Path) -> None:
    data = fx.stage(
        tmp_path,
        [fx.faa_part("23", [0])],
        [fx.cfr_provision("23", "1", [0])],
        [
            fx.cfr_aircraft(
                [fx.entry([fx.cfr_ref("23-0")]), fx.entry([], 2)], model="A"
            ),
            fx.cfr_aircraft([fx.entry([])], model="B"),
        ],
    )
    coverage = build(data, tmp_path / "cert_basis.sqlite")["coverage"]
    assert coverage["entries"]["FAA"]["regulation"] == {
        "entries": 3,
        "with_references": 1,
        "without_references": 2,
    }
    assert coverage["tcbs"]["FAA"] == {"total": 2, "resolve_to_nothing": 1}
    assert coverage["models"] == {"total": 2, "resolve_to_nothing": 1}
    [only] = coverage["models_resolving_to_nothing"]
    assert only.endswith(" / B")


def test_report_carries_promotion_and_source_checks(tmp_path: Path) -> None:
    data = fx.stage(
        tmp_path, [fx.faa_part("23", [0])], [fx.cfr_provision("23", "1", [0])], []
    )
    assert build(data, tmp_path / "a.sqlite")["source_checks"] == {"FAA/23": None}
    (data / "promotion.json").write_text('{"documents": {"tools_commit": "abc"}}')
    (data / "source_checks.json").write_text('{"FAA/23": {"checked_on": "2026-11-08"}}')
    report = build(data, tmp_path / "b.sqlite")
    assert report["promotion"]["documents"]["tools_commit"] == "abc"
    assert report["source_checks"]["FAA/23"]["checked_on"] == "2026-11-08"
