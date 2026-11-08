"""The label-line text format (docs/DATA_FORMAT.md §Text format).

This package is a public API: tools/ lays out and checks provision text
with these names, so the two can never disagree. tests/test_tools_api.py
pins them; don't rename or drop one without changing tools/ too.
"""

from certbuild.text.labels import SECTION_HEADING_RE, heading_section, label_values
from certbuild.text.markup import FORMULA_MARK, formula_body, inline_error, strip_inline
from certbuild.text.tables import (
    TABLE_CLOSE,
    TABLE_OPEN,
    TABLE_ROW_SEP,
    TableCell,
    is_table_row,
    parse_table_row,
    table_width,
)
from certbuild.text.paragraphs import (
    Paragraph,
    ParsedText,
    TextFormatError,
    paragraph_ref_paths,
    parse_paragraphs,
)
from certbuild.text.flat import flatten_text, plain_text

__all__ = [
    "FORMULA_MARK",
    "Paragraph",
    "ParsedText",
    "SECTION_HEADING_RE",
    "TABLE_CLOSE",
    "TABLE_OPEN",
    "TABLE_ROW_SEP",
    "TableCell",
    "TextFormatError",
    "flatten_text",
    "formula_body",
    "heading_section",
    "inline_error",
    "is_table_row",
    "label_values",
    "paragraph_ref_paths",
    "parse_paragraphs",
    "parse_table_row",
    "plain_text",
    "strip_inline",
    "table_width",
]
