import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

from build import (
    _CATEGORY_NAMES,
    _ISSUERS,
    SCHEMAS_DIR,
    validate_aircraft_file,
    validate_data_dir,
    validate_document_file,
    validate_provision_file,
)


class TestRealData:
    def test_checked_in_provision_validates(self, repo_root: Path) -> None:
        errors = validate_provision_file(
            repo_root / "data" / "documents" / "faa" / "23" / "1585.json"
        )
        assert errors == [], [str(e) for e in errors]

    def test_checked_in_document_validates(self, repo_root: Path) -> None:
        errors = validate_document_file(
            repo_root / "data" / "documents" / "faa" / "23" / "_document.json"
        )
        assert errors == [], [str(e) for e in errors]

    def test_checked_in_aircraft_validates(self, repo_root: Path) -> None:
        errors = validate_aircraft_file(
            repo_root / "data" / "aircraft" / "textron-aviation-inc" / "172.json"
        )
        assert errors == [], [str(e) for e in errors]

    def test_full_data_dir_validates(self, repo_root: Path) -> None:
        errors = validate_data_dir(repo_root / "data")
        assert errors == [], [str(e) for e in errors]


class TestClosedSetsAgree:
    """Each closed set lives in a schema enum and a build.py seed table."""

    def test_issuers(self) -> None:
        common = json.loads((SCHEMAS_DIR / "common.schema.json").read_text())
        assert common["$defs"]["issuer"]["enum"] == list(_ISSUERS)

    def test_categories(self) -> None:
        aircraft = json.loads((SCHEMAS_DIR / "aircraft_model.schema.json").read_text())
        enum = aircraft["$defs"]["categories"]["items"]["enum"]
        assert enum == list(_CATEGORY_NAMES)

    def test_successors_are_seeded_first(self) -> None:
        codes = list(_ISSUERS)
        for i, (_, _, _, successor) in enumerate(_ISSUERS.values()):
            assert successor is None or codes.index(successor) < i


INVALID_PROVISIONS = [
    ("missing_required.json", "canonical_title"),
    ("additional_property.json", "nonsense_field"),
    ("empty_text.json", "text"),
    ("tab_in_text.json", "text"),
    ("bad_source_url.json", "source_url"),
    ("empty_versions.json", "versions"),
    ("initial_adoption_cite.json", "publication_cite"),
    ("bad_action_date.json", "issued_on"),
    ("legacy_field_names.json", "federal_register_cite"),
    # No hand edits in data/: corrections are override rows in tools/.
    ("manual_provenance.json", "manual"),
]

INVALID_DOCUMENTS = [
    ("bad_regulation_designator.json", "designator"),
    ("bad_effective_date.json", "effective_date"),
    ("unknown_doc_kind.json", "doc_kind"),
    ("bad_slug.json", "slug"),
]

INVALID_AIRCRAFT = [
    ("missing_required.json", "tcb"),
    ("bad_entry_type.json", "mystery"),
    ("extra_field.json", "secret_field"),
    ("empty_cert_basis.json", "certification_basis"),
    ("unknown_category.json", "nromal"),
    ("model_level_categories.json", "categories"),
    ("legacy_issuer_code.json", "CAA (FAA)"),
    ("legacy_resolved_references.json", "resolved_references"),
    ("include_without_to.json", "'to' is a required property"),
    ("exclude_with_to.json", "should not be valid"),
    ("paragraph_without_provision.json", "'provisions' is a required property"),
    ("paragraph_with_two_provisions.json", "is too long"),
]


def _assert_rejected(errors: list, fixture: str, expected_hint: str) -> None:
    assert errors, f"{fixture} should have failed validation"
    combined = " ".join(f"{e.location} {e.message}" for e in errors)
    assert expected_hint in combined, (
        f"expected error mentioning {expected_hint!r}, got: {combined}"
    )


@pytest.mark.parametrize("fixture,expected_hint", INVALID_PROVISIONS)
def test_invalid_provision_rejected(
    fixtures_dir: Path, fixture: str, expected_hint: str
) -> None:
    errors = validate_provision_file(fixtures_dir / "invalid_provisions" / fixture)
    _assert_rejected(errors, fixture, expected_hint)


@pytest.mark.parametrize("fixture,expected_hint", INVALID_DOCUMENTS)
def test_invalid_document_rejected(
    fixtures_dir: Path, fixture: str, expected_hint: str
) -> None:
    errors = validate_document_file(fixtures_dir / "invalid_documents" / fixture)
    _assert_rejected(errors, fixture, expected_hint)


@pytest.mark.parametrize("fixture,expected_hint", INVALID_AIRCRAFT)
def test_invalid_aircraft_rejected(
    fixtures_dir: Path, fixture: str, expected_hint: str
) -> None:
    errors = validate_aircraft_file(fixtures_dir / "invalid_aircraft" / fixture)
    _assert_rejected(errors, fixture, expected_hint)


def _write(tmp_path: Path, doc: dict) -> Path:
    path = tmp_path / "doc.json"
    path.write_text(json.dumps(doc))
    return path


class TestPublicationCiteOptional:
    BASE: ClassVar[dict[str, Any]] = {
        "issuer": "FAA",
        "document": "25",
        "number": "1309",
        "current_grouping": "F",
        "canonical_title": "Equipment, systems, and installations",
        "versions": [
            {
                "designator": "25-23",
                "title_at_revision": "Equipment, systems, and installations",
                "text": "placeholder",
                "source_url": "https://example.com/doc",
            }
        ],
    }

    def test_omitted_validates(self, tmp_path: Path) -> None:
        assert validate_provision_file(_write(tmp_path, self.BASE)) == []

    def test_blank_string_validates(self, tmp_path: Path) -> None:
        doc = {
            **self.BASE,
            "versions": [{**self.BASE["versions"][0], "publication_cite": ""}],
        }
        assert validate_provision_file(_write(tmp_path, doc)) == []


def test_non_regulation_designators_are_free_form(tmp_path: Path) -> None:
    doc = {
        "issuer": "EASA",
        "doc_kind": "certification_spec",
        "code": "CS-25",
        "slug": "cs-25",
        "title": None,
        "revisions": [
            {"designator": "Amdt 27", "ordinal": 27, "effective_date": "2023-01-24"}
        ],
    }
    assert validate_document_file(_write(tmp_path, doc)) == []


def test_malformed_json_reported_not_crashed(tmp_path: Path) -> None:
    bad = tmp_path / "broken.json"
    bad.write_text("{ not valid json")
    errors = validate_provision_file(bad)
    assert errors
    assert "invalid JSON" in errors[0].message
