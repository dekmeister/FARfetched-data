from pathlib import Path

import pytest

from build import (
    validate_aircraft_file,
    validate_data_dir,
    validate_regulation_file,
)


class TestRealData:
    def test_checked_in_regulation_validates(self, repo_root: Path) -> None:
        errors = validate_regulation_file(
            repo_root / "data" / "regulations" / "faa" / "25" / "1309.json"
        )
        assert errors == [], [str(e) for e in errors]

    def test_checked_in_aircraft_validates(self, repo_root: Path) -> None:
        errors = validate_aircraft_file(
            repo_root / "data" / "aircraft" / "A16WE.json"
        )
        assert errors == [], [str(e) for e in errors]

    def test_full_data_dir_validates(self, repo_root: Path) -> None:
        errors = validate_data_dir(repo_root / "data")
        assert errors == [], [str(e) for e in errors]


INVALID_REGULATIONS = [
    ("missing_required.json", "canonical_title"),
    ("additional_property.json", "nonsense_field"),
    ("empty_text.json", "text"),
    ("bad_date.json", "effective_date"),
    ("bad_designator.json", "designator"),
    ("empty_amendments.json", "amendments"),
]


@pytest.mark.parametrize("fixture,expected_hint", INVALID_REGULATIONS)
def test_invalid_regulation_rejected(
    fixtures_dir: Path, fixture: str, expected_hint: str
) -> None:
    path = fixtures_dir / "invalid_regulations" / fixture
    errors = validate_regulation_file(path)
    assert errors, f"{fixture} should have failed validation"
    combined = " ".join(f"{e.location} {e.message}" for e in errors)
    assert expected_hint in combined, (
        f"expected error mentioning {expected_hint!r}, got: {combined}"
    )


INVALID_AIRCRAFT = [
    ("missing_required.json", "certification_basis"),
    ("bad_entry_type.json", "mystery"),
    ("unknown_reference_kind.json", "reference_kind"),
    ("range_missing_bounds.json", "resolved_references/0"),
    ("extra_field.json", "secret_field"),
    ("empty_cert_basis.json", "certification_basis"),
]


@pytest.mark.parametrize("fixture,expected_hint", INVALID_AIRCRAFT)
def test_invalid_aircraft_rejected(
    fixtures_dir: Path, fixture: str, expected_hint: str
) -> None:
    path = fixtures_dir / "invalid_aircraft" / fixture
    errors = validate_aircraft_file(path)
    assert errors, f"{fixture} should have failed validation"
    combined = " ".join(f"{e.location} {e.message}" for e in errors)
    assert expected_hint in combined, (
        f"expected error mentioning {expected_hint!r}, got: {combined}"
    )


def test_malformed_json_reported_not_crashed(tmp_path: Path) -> None:
    bad = tmp_path / "broken.json"
    bad.write_text("{ not valid json")
    errors = validate_regulation_file(bad)
    assert errors
    assert "invalid JSON" in errors[0].message
