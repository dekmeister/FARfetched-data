"""Cert-basis resolution rules, end to end (docs/DATA_FORMAT.md)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import factories as fx
import pytest

from certbuild.errors import BuildError
from certbuild.pipeline import build


# ---------------------------------------------------------------------------
# cert-basis resolution rules


class TestResolution:
    def test_range_takes_latest_version_up_to_to(self, tmp_path: Path) -> None:
        provs = [
            fx.cfr_provision("23", "1309", [0, 7, 14]),
            fx.cfr_provision("23", "9999", [20]),  # post-dates the range: not in basis
        ]
        out = fx.build_part23(tmp_path, provs, [fx.entry([fx.cfr_ref("23-13")])])
        assert fx.resolved(out) == {(1, "1309", "23-7", None)}

    def test_base_revision_is_always_included(self, tmp_path: Path) -> None:
        # "as amended by 23-1 thru 23-13" still includes text unchanged since 23-0.
        out = fx.build_part23(
            tmp_path,
            [fx.cfr_provision("23", "1", [0])],
            [fx.entry([fx.cfr_ref("23-13")])],
        )
        assert fx.resolved(out) == {(1, "1", "23-0", None)}

    def test_skipped_revision_falls_back_to_earlier_text(self, tmp_path: Path) -> None:
        # "23-1 thru 23-38, 23-40": a provision last changed at 23-39 keeps 23-0.
        provs = [
            fx.cfr_provision("23", "1", [0, 39]),
            fx.cfr_provision("23", "2", [0, 39, 40]),
        ]
        out = fx.build_part23(
            tmp_path, provs, [fx.entry([fx.cfr_ref("23-40", skip=["23-39"])])]
        )
        assert fx.resolved(out) == {(1, "1", "23-0", None), (1, "2", "23-40", None)}

    def test_scoped_ref_overrides_document_wide(self, tmp_path: Path) -> None:
        # "... except 23.611 as amended through 23-54"
        provs = [
            fx.cfr_provision("23", "611", [0, 50]),
            fx.cfr_provision("23", "143", [0, 50]),
        ]
        refs = [fx.cfr_ref("23-40"), fx.cfr_ref("23-54", provisions=["611"])]
        out = fx.build_part23(tmp_path, provs, [fx.entry(refs)])
        assert fx.resolved(out) == {
            (1, "611", "23-50", None),
            (1, "143", "23-0", None),
        }

    def test_paragraph_ref_adds_a_row(self, tmp_path: Path) -> None:
        # "23.1309(a) as amended through 23-62, for PED tolerance only"
        refs = [
            fx.cfr_ref("23-54"),
            fx.cfr_ref("23-62", provisions=["1309"], paragraph="(a)"),
        ]
        out = fx.build_part23(
            tmp_path, [fx.cfr_provision("23", "1309", [0, 49, 62])], [fx.entry(refs)]
        )
        assert fx.resolved(out) == {
            (1, "1309", "23-49", None),
            (1, "1309", "23-62", "(a)"),
        }

    def test_paragraph_ref_on_same_version_is_dropped(self, tmp_path: Path) -> None:
        refs = [
            fx.cfr_ref("23-54"),
            fx.cfr_ref("23-62", provisions=["1309"], paragraph="(a)"),
        ]
        out = fx.build_part23(
            tmp_path, [fx.cfr_provision("23", "1309", [0, 49])], [fx.entry(refs)]
        )
        assert fx.resolved(out) == {(1, "1309", "23-49", None)}

    def test_exclude_removes_from_document_wide(self, tmp_path: Path) -> None:
        provs = [fx.cfr_provision("23", "1", [0]), fx.cfr_provision("23", "1419", [0])]
        refs = [
            fx.cfr_ref("23-13"),
            {
                "issuer": "FAA",
                "document": "23",
                "effect": "exclude",
                "provisions": ["1419"],
            },
        ]
        out = fx.build_part23(tmp_path, provs, [fx.entry(refs)])
        assert fx.resolved(out) == {(1, "1", "23-0", None)}

    def test_entries_resolve_independently(self, tmp_path: Path) -> None:
        # Two TCDS lines (e.g. two S/N ranges) may hold one provision at
        # different levels; overrides never cross lines.
        entries = [
            fx.entry([fx.cfr_ref("23-13")], display_order=1, applicability="S/N 1-99"),
            fx.entry(
                [fx.cfr_ref("23-62")], display_order=2, applicability="S/N 100 and on"
            ),
        ]
        out = fx.build_part23(tmp_path, [fx.cfr_provision("23", "1", [0, 50])], entries)
        assert fx.resolved(out) == {(1, "1", "23-0", None), (2, "1", "23-50", None)}

    def test_refs_and_children_are_stored(self, tmp_path: Path) -> None:
        refs = [
            fx.cfr_ref("23-40", skip=["23-39"]),
            fx.cfr_ref("23-54", provisions=["1"]),
        ]
        out = fx.build_part23(
            tmp_path, [fx.cfr_provision("23", "1", [0])], [fx.entry(refs)]
        )
        with sqlite3.connect(out) as conn:
            counts = [
                conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                for t in (
                    "cert_basis_refs",
                    "cert_basis_ref_skips",
                    "cert_basis_ref_provisions",
                )
            ]
        assert counts == [2, 1, 1]

    def test_entry_without_references_is_kept(self, tmp_path: Path) -> None:
        entry = fx.entry([], entry_type="special_condition")
        out = fx.build_part23(tmp_path, [fx.cfr_provision("23", "1", [0])], [entry])
        with sqlite3.connect(out) as conn:
            assert conn.execute(
                "SELECT entry_type FROM cert_basis_entries"
            ).fetchall() == [("special_condition",)]
        assert fx.resolved(out) == set()


class TestAuthorityOnlyRevisions:
    """Amendments that changed no section (23-47: authority citation only) are
    declared in _document.json but have no provision versions. TCDS cite them
    as range endpoints ("23-1 thru 23-47"), so a ref must be able to name them
    and resolve exactly as it does for the revision before."""

    # 23-47 and 23-55 are declared but no provision has a version at them.
    ORDINALS = [n for n in range(63) if n not in (56, 60)]
    PROVS = [
        fx.cfr_provision("23", "1", [0, 46]),
        fx.cfr_provision("23", "2", [0, 30]),
        fx.cfr_provision("23", "3", [0, 51]),
    ]

    def _resolve(self, tmp_path: Path, refs: list[dict]) -> set:
        data = fx.stage(
            tmp_path,
            [fx.faa_part("23", self.ORDINALS)],
            self.PROVS,
            [fx.cfr_aircraft([fx.entry(refs)])],
        )
        out = tmp_path / "cert_basis.sqlite"
        build(data, out)
        return fx.resolved(out)

    def test_ref_to_section_less_revision_resolves_like_the_one_before(
        self, tmp_path: Path
    ) -> None:
        at_47 = self._resolve(tmp_path / "a", [fx.cfr_ref("23-47")])
        at_46 = self._resolve(tmp_path / "b", [fx.cfr_ref("23-46")])
        assert (
            at_47
            == at_46
            == {
                (1, "1", "23-46", None),
                (1, "2", "23-30", None),
                (1, "3", "23-0", None),
            }
        )

    def test_skip_naming_a_section_less_revision_is_accepted(
        self, tmp_path: Path
    ) -> None:
        refs = [fx.cfr_ref("23-51", skip=["23-47"])]
        assert self._resolve(tmp_path, refs) == {
            (1, "1", "23-46", None),
            (1, "2", "23-30", None),
            (1, "3", "23-51", None),
        }

    def test_undeclared_number_is_still_rejected(self, tmp_path: Path) -> None:
        # 23-56 was never declared: nothing may name it, as a `to` or a `skip`.
        for refs, message in [
            ([fx.cfr_ref("23-56")], "unknown revision '23-56'"),
            ([fx.cfr_ref("23-57", skip=["23-56"])], "unknown skip revision '23-56'"),
        ]:
            data = fx.stage(
                tmp_path / message[:12],
                [fx.faa_part("23", self.ORDINALS)],
                self.PROVS,
                [fx.cfr_aircraft([fx.entry(refs)])],
            )
            with pytest.raises(BuildError, match=message):
                build(data, tmp_path / "cert_basis.sqlite")


class TestResolutionFailures:
    PROVS = [fx.cfr_provision("23", "1", [0, 50]), fx.cfr_provision("23", "2", [0])]

    @pytest.mark.parametrize(
        ("refs", "message"),
        [
            ([fx.cfr_ref("23-99")], "unknown revision '23-99'"),
            ([fx.cfr_ref("23-40", skip=["23-99"])], "unknown skip revision '23-99'"),
            ([fx.cfr_ref("23-40", skip=["23-40"])], "not earlier than to"),
            ([fx.cfr_ref("23-40", provisions=["1234"])], "unknown provision 23.1234"),
            ([fx.cfr_ref("25-1", document="25")], "unknown document FAA/25"),
            ([fx.cfr_ref("23-62"), fx.cfr_ref("23-13")], "two document-wide refs"),
            (
                [
                    fx.cfr_ref("23-62", provisions=["1"]),
                    fx.cfr_ref("23-13", provisions=["1"]),
                ],
                "two scoped refs",
            ),
            (
                [
                    fx.cfr_ref("23-62", provisions=["1"]),
                    {
                        "issuer": "FAA",
                        "document": "23",
                        "effect": "exclude",
                        "provisions": ["1"],
                    },
                ],
                "both excluded and included",
            ),
            (
                [
                    fx.cfr_ref("23-62", provisions=["2"]),
                    {
                        "issuer": "FAA",
                        "document": "23",
                        "effect": "exclude",
                        "provisions": ["1"],
                    },
                ],
                "removes nothing",
            ),
            (
                [
                    {
                        "issuer": "FAA",
                        "document": "23",
                        "effect": "exclude",
                        "provisions": ["1"],
                    }
                ],
                "no include ref in 23 to read its number at",
            ),
        ],
    )
    def test_fails_loud(self, tmp_path: Path, refs: list[dict], message: str) -> None:
        assert message in fx.part23_fails(tmp_path, self.PROVS, [fx.entry(refs)])

    def test_include_resolving_to_nothing_fails(self, tmp_path: Path) -> None:
        provs = [fx.cfr_provision("23", "1", [50])]
        message = fx.part23_fails(tmp_path, provs, [fx.entry([fx.cfr_ref("23-13")])])
        assert "resolves to no provisions" in message
