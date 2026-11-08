"""Flat and plain forms of a provision text."""

from __future__ import annotations

import re

from certbuild.text.markup import FORMULA_MARK, strip_inline
from certbuild.text.tables import (
    TABLE_CLOSE,
    TABLE_OPEN,
    TABLE_ROW_SEP,
    TABLE_OPEN_RE,
    is_table_row,
)


def flatten_text(text: str) -> str:
    """A text's words without its layout: lines stripped and joined by single
    spaces. Structuring may change a text only where this stays equal.

    Table rows are joined by ` |- ` instead, so the flat form of a table is
    one line (`{| Caption |- ! A ! B |- | 1 | 2 |}`) that still says where
    each row starts."""
    out: list[str] = []
    in_table = False
    for line in text.split("\n"):
        if not (s := line.strip()):
            continue
        if in_table and is_table_row(s) and out:
            out.append(TABLE_ROW_SEP)
        if TABLE_OPEN_RE.match(s):
            in_table = True
        elif s == TABLE_CLOSE:
            in_table = False
        out.append(s)
    return " ".join(out)


_PLAIN_SPAN_RE = re.compile(r"(?<!\S)\{(?:r\d+)?(?: ?c\d+)?\}(?!\S)")
_PLAIN_MARKUP = frozenset(
    {TABLE_OPEN, TABLE_CLOSE, TABLE_ROW_SEP, "!", "|", FORMULA_MARK}
)


def plain_text(text: str) -> str:
    """The words of `text` (laid out or flat) with markup removed: table
    markup (`{|`, `|}`, `|-`, cell delimiters and spans), sub/superscripts
    (`V_{A}` → `VA`) and formula marks (`$$ x $$` → `x`). For comparing
    wording across layouts, never for display. (A lone `!` or `|` outside a
    table, which only OCR junk has, goes too.)"""
    flat = _PLAIN_SPAN_RE.sub(" ", strip_inline(flatten_text(text)))
    return " ".join(w for w in flat.split() if w not in _PLAIN_MARKUP)
