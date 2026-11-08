"""Compile FARfetched-data JSON sources into cert_basis.sqlite."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from certbuild.ddl import SCHEMA_VERSION
from certbuild.errors import BuildError
from certbuild.keys import sort_key
from certbuild.lookups import _CATEGORY_NAMES, _ISSUERS
from certbuild.pipeline import build, check
from certbuild.provisions import check_text_format
from certbuild.similarity import (
    SIMILARITY_MIN_DOC_SIZE,
    SIMILARITY_TOP_PER_DOCUMENT,
    SimilaritySource,
    compute_similarity,
    similarity_terms,
    stem,
)
from certbuild.sources import (
    REPO_ROOT,
    SCHEMAS_DIR,
    validate_aircraft_file,
    validate_data_dir,
    validate_document_file,
    validate_provision_file,
)
from certbuild.text.flat import flatten_text, plain_text
from certbuild.text.labels import SECTION_HEADING_RE, heading_section, label_values
from certbuild.text.markup import FORMULA_MARK, inline_error, strip_inline
from certbuild.text.paragraphs import (
    TextFormatError,
    paragraph_ref_paths,
    parse_paragraphs,
)
from certbuild.text.tables import (
    TABLE_CLOSE,
    TABLE_OPEN,
    TABLE_ROW_SEP,
    TableCell,
    parse_table_row,
    table_width,
)

# Temporary re-exports while tests/ and tools/ move to certbuild.
__all__ = [
    "BuildError",
    "FORMULA_MARK",
    "REPO_ROOT",
    "SCHEMAS_DIR",
    "SCHEMA_VERSION",
    "SECTION_HEADING_RE",
    "SIMILARITY_MIN_DOC_SIZE",
    "SIMILARITY_TOP_PER_DOCUMENT",
    "SimilaritySource",
    "TABLE_CLOSE",
    "TABLE_OPEN",
    "TABLE_ROW_SEP",
    "TableCell",
    "TextFormatError",
    "_CATEGORY_NAMES",
    "_ISSUERS",
    "build",
    "check",
    "check_text_format",
    "compute_similarity",
    "flatten_text",
    "heading_section",
    "inline_error",
    "label_values",
    "paragraph_ref_paths",
    "parse_paragraphs",
    "parse_table_row",
    "plain_text",
    "similarity_terms",
    "sort_key",
    "stem",
    "strip_inline",
    "table_width",
    "validate_aircraft_file",
    "validate_data_dir",
    "validate_document_file",
    "validate_provision_file",
    "main",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=REPO_ROOT / "data",
        help="Path to the data directory (default: ./data)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "cert_basis.sqlite",
        help="Output SQLite path (default: ./cert_basis.sqlite)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate schemas, file paths and text layout; do not build SQLite.",
    )
    args = parser.parse_args(argv)

    if args.check:
        errors = check(args.data_dir)
        if errors:
            for e in errors:
                print(e, file=sys.stderr)
            print(f"\n{len(errors)} validation error(s).", file=sys.stderr)
            return 1
        print(f"OK: {args.data_dir} validates clean.", file=sys.stderr)
        return 0

    try:
        report = build(args.data_dir, args.out)
    except BuildError as exc:
        for line in exc.errors:
            print(line, file=sys.stderr)
        print(f"\nBuild failed ({len(exc.errors)} error(s)).", file=sys.stderr)
        return 1

    t = report["tables"]
    print(
        f"OK: wrote {args.out} (schema v{SCHEMA_VERSION}, "
        f"documents={t['documents']}, revisions={t['document_revisions']}, "
        f"provision_versions={t['provision_versions']}, "
        f"text_missing={report['text_missing']}, "
        f"structured={report['structured_versions']}, "
        f"paragraphs={t['provision_paragraphs']}, "
        f"deleted={report['deleted']}, "
        f"similar={t['provision_similarity']}, "
        f"models={t['aircraft_models']}, entries={t['cert_basis_entries']}, "
        f"resolved={t['cert_basis_resolved']})",
        file=sys.stderr,
    )
    if report["git_dirty"]:
        n = len(report["git_dirty_paths"])
        print(
            f"WARNING: built from {n} uncommitted path(s) under {args.data_dir}; "
            "build_info.git_sha names HEAD, which doesn't hold them. "
            "See git_dirty_paths in the report.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
