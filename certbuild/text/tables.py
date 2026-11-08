"""Table blocks (docs/DATA_FORMAT.md §Tables)."""

from __future__ import annotations

import re
from dataclasses import dataclass


# Tables (docs/DATA_FORMAT.md §Tables). A block of lines: `{|` with an optional
# caption, one row per line (cells opened by `!` header / `|` data, each a
# token of its own, with an optional `{rN cM}` span), then `|}`. The flat form
# (`flatten_text`) joins rows with ` |- `.
TABLE_OPEN = "{|"
TABLE_CLOSE = "|}"
TABLE_ROW_SEP = "|-"
_TABLE_OPEN_RE = re.compile(r"\{\|(?: (.*))?$")
_TABLE_ROW_RE = re.compile(r"[!|](?: |$)")
_TABLE_DELIM_RE = re.compile(r"(?:^| )([!|])(?= |$)")
_TABLE_SPAN_RE = re.compile(r"(?:^| )\{(?:r(\d+))?(?:(?<=\d) )?(?:c(\d+))?\}$")
_TABLE_TOKEN_RE = re.compile(r"\{\||\|\}|\|-")


@dataclass(frozen=True)
class TableCell:
    header: bool  # `!` cell
    text: str  # '' for an empty cell
    rowspan: int = 1
    colspan: int = 1


def is_table_row(content: str) -> bool:
    """A line (without its indentation) that is a table row."""
    return content != TABLE_CLOSE and bool(_TABLE_ROW_RE.match(content))


def parse_table_row(content: str) -> list[TableCell]:
    """Split a table row line (without its indentation) into its cells.
    Raise ValueError when the line isn't a valid row."""
    if not is_table_row(content):
        raise ValueError("a table row must start with `!` or `|`")
    delims = list(_TABLE_DELIM_RE.finditer(content))
    cells: list[TableCell] = []
    for i, d in enumerate(delims):
        end = delims[i + 1].start() if i + 1 < len(delims) else len(content)
        body = content[d.end() : end].strip()
        rowspan = colspan = 1
        span = _TABLE_SPAN_RE.search(body)
        if span:
            if not (span.group(1) or span.group(2)):
                raise ValueError("empty span `{}`")
            rowspan = int(span.group(1) or 1)
            colspan = int(span.group(2) or 1)
            if rowspan < 2 and colspan < 2 or "1" in (span.group(1), span.group(2)):
                raise ValueError("a span must be 2 or more")
            body = body[: span.start()].strip()
        if re.search(r"(?<!\S)\{[rc]\d|(?<!\S)\{\}|[rc]\d+\}(?!\S)", body):
            raise ValueError(f"malformed span in cell {body!r}")
        if _TABLE_TOKEN_RE.search(body):
            raise ValueError(f"table markup inside cell {body!r}")
        cells.append(TableCell(d.group(1) == "!", body, rowspan, colspan))
    return cells


def table_width(rows: list[list[TableCell]]) -> int:
    """Column count of a table. Raise ValueError when rows differ in width
    once spans are applied, spans overlap, or a row span runs past the last
    row."""
    taken: set[tuple[int, int]] = set()
    for r, cells in enumerate(rows):
        col = 0
        for cell in cells:
            while (r, col) in taken:
                col += 1
            for dr in range(cell.rowspan):
                for dc in range(cell.colspan):
                    if (r + dr, col + dc) in taken:
                        raise ValueError("overlapping spans")
                    taken.add((r + dr, col + dc))
            col += cell.colspan
    if any(r >= len(rows) for r, _ in taken):
        raise ValueError("a row span runs past the last row")
    widths = [1 + max(c for rr, c in taken if rr == r) for r in range(len(rows))]
    if (
        any((r, c) not in taken for r in range(len(rows)) for c in range(widths[r]))
        or len(set(widths)) > 1
    ):
        raise ValueError(f"rows differ in width: {widths}")
    return widths[0]
