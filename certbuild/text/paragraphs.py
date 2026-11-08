"""The label-line text parser (docs/DATA_FORMAT.md §Text format).

Pure: no I/O, no sqlite3. It never guesses a layout: a text that breaks the
format raises TextFormatError with the line and the reason. tools/ lays out
text with this same parser, so error messages are part of what it relies on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from certbuild.text.labels import (
    SECTION_HEADING_RE,
    LABEL_GROUP_RE,
    LABEL_TOKEN_RE,
    heading_section,
    label_values,
)
from certbuild.text.markup import FORMULA_MARK, formula_body, inline_error
from certbuild.text.tables import (
    TABLE_CLOSE,
    TableCell,
    TABLE_OPEN_RE,
    TABLE_TOKEN_RE,
    is_table_row,
    parse_table_row,
    table_width,
)


class TextFormatError(ValueError):
    """A provision text breaks the label-line format."""

    def __init__(self, line: int, message: str) -> None:
        self.line = line
        self.message = message
        super().__init__(f"line {line}: {message}")


@dataclass(frozen=True)
class Paragraph:
    """One block of a provision text, in document order."""

    seq: int
    depth: int  # 0 = top level; otherwise the number of labels in `path`
    label: str | None  # verbatim, e.g. '(ii)' or '[(4)'; None when unlabelled
    path: str | None  # '(a)(1)(ii)'; the enclosing item's path when unlabelled
    text: str  # '' for a label-only block
    section: str | None = None  # 'F23.2' under a section heading, else None
    heading: bool = False  # the block is the section heading itself
    kind: str = "text"  # 'table' for a line of a table block; 'formula'


@dataclass(frozen=True)
class ParsedText:
    paragraphs: tuple[Paragraph, ...]
    structured: bool  # more than one line
    gaps: int  # labels that skip values, e.g. (a) then (c)


@dataclass
class _Level:
    """One open item on the style stack."""

    style: str
    value: int
    token: str
    indent: int
    inline: bool  # opened by a later token of a compound label like (c)(1)


@dataclass(frozen=True)
class _Reading:
    kind: str  # 'cont' (continue stack[level]) or 'open' (child of stack[-1])
    level: int
    style: str
    value: int
    gap: int


def _first_style(values: dict[str, int]) -> tuple[str, int]:
    """Style for a label that opens a level with no sequence to go by."""
    return min(values.items(), key=lambda kv: (kv[1], kv[0]))


def _choose(stack: list[_Level], token: str, indent: int, line: int) -> _Reading:
    values = label_values(token)
    if not stack:
        style, value = _first_style(values)
        return _Reading("open", 0, style, value, value - 1)
    readings: list[_Reading] = []
    for k, lvl in enumerate(stack):
        v = values.get(lvl.style)
        if v is not None and v > lvl.value:
            readings.append(_Reading("cont", k, lvl.style, v, v - lvl.value - 1))
    readings.extend(
        _Reading("open", len(stack), s, v, 0) for s, v in values.items() if v == 1
    )
    if not readings:
        raise TextFormatError(line, f"label ({token}) continues no open level")

    def fits(r: _Reading) -> bool:
        if r.kind == "open":
            return indent > stack[-1].indent
        lvl = stack[r.level]
        return indent > lvl.indent if lvl.inline else indent == lvl.indent

    fitting = [r for r in readings if fits(r)]
    if len(fitting) > 1:
        # Only possible next to a compound label, whose inline levels have no
        # indentation of their own. One exact value beats gaps; else fail.
        exact = [r for r in fitting if r.gap == 0]
        if len(exact) != 1:
            raise TextFormatError(line, f"label ({token}) is ambiguous")
        fitting = exact
    if not fitting:
        raise TextFormatError(
            line,
            f"indentation of label ({token}) fits none of its readings "
            f"(re-run the tools segmenter to fix the layout)",
        )
    return fitting[0]


def _path(stack: list[_Level], section: str | None = None) -> str:
    labels = "".join(f"({lvl.token})" for lvl in stack)
    return f"{section or ''}{labels}" if labels else ""


def parse_paragraphs(text: str) -> ParsedText:
    """Split a provision text into paragraphs. Raise TextFormatError if the
    text breaks the format (docs/DATA_FORMAT.md §Text format)."""
    lines = _lines(text)
    if len(lines) == 1:
        return _flat(*lines[0])
    parser = _Parser()
    for n, raw in lines:
        parser.line(n, raw)
    return parser.finish()


def _lines(text: str) -> list[tuple[int, str]]:
    """The non-empty lines with their line numbers, checked for whitespace
    faults that no layout allows."""
    lines: list[tuple[int, str]] = []
    for n, raw in enumerate(text.split("\n"), 1):
        if raw == "":
            continue
        if "\t" in raw:
            raise TextFormatError(n, "tab character")
        if raw != raw.rstrip():
            raise TextFormatError(n, "trailing whitespace")
        lines.append((n, raw))
    if not lines:
        raise TextFormatError(1, "no text")
    return lines


def _flat(n: int, raw: str) -> ParsedText:
    """A single-line text: one unlabelled paragraph, no layout markup."""
    if raw[0].isspace():
        raise TextFormatError(n, "a single-line text must not be indented")
    if TABLE_TOKEN_RE.search(raw) or is_table_row(raw):
        raise TextFormatError(n, "table markup in a single-line text")
    if FORMULA_MARK in raw:
        raise TextFormatError(n, "`$$` in a single-line text")
    if err := inline_error(raw):
        raise TextFormatError(n, err)
    return ParsedText((Paragraph(0, 0, None, None, raw),), False, 0)


@dataclass
class _Table:
    """An open table block."""

    line: int  # the `{|` line
    indent: int
    rows: list[list[TableCell]] = field(default_factory=list)


class _Parser:
    """A structured (multi-line) text, read one line at a time.

    Each kind of line has its own method: a line of a table block, a section
    heading, a labelled line, and an unlabelled one (text or a formula).
    `line` runs the checks every line shares and picks the method; a new
    kind of line is a new branch there plus its own method.
    """

    def __init__(self) -> None:
        self.stack: list[_Level] = []  # open items, outermost first
        self.out: list[Paragraph] = []
        self.gaps = 0
        self.section: str | None = None
        self.sections: set[str] = set()
        self.roman = 0  # the last roman section heading read (I = 1)
        self.table: _Table | None = None

    def line(self, n: int, raw: str) -> None:
        content = raw.lstrip(" ")
        indent = len(raw) - len(content)
        if content[0].isspace():
            raise TextFormatError(n, "indentation must be spaces")
        if err := inline_error(content):
            raise TextFormatError(n, err)
        formula = formula_body(content) is not None
        if FORMULA_MARK in content and (self.table is not None or not formula):
            raise TextFormatError(
                n, "`$$` outside a formula line (a whole line `$$ … $$`)"
            )
        opening = TABLE_OPEN_RE.match(content)
        if self.table is not None or opening:
            self._table_line(n, content, indent, opening)
        elif TABLE_TOKEN_RE.search(content) or is_table_row(content):
            raise TextFormatError(n, "table markup outside a table block")
        elif not self._heading(n, content, indent):
            self._item(n, content, indent, formula)

    def finish(self) -> ParsedText:
        if self.table is not None:
            raise TextFormatError(
                self.table.line, "a table that is never closed (`|}`)"
            )
        return ParsedText(tuple(self.out), True, self.gaps)

    def _owner(self, indent: int) -> list[_Level]:
        """Rule 5: the open items up to the innermost one whose label line is
        indented less than `indent`."""
        k = next(
            (
                i
                for i in range(len(self.stack) - 1, -1, -1)
                if self.stack[i].indent < indent
            ),
            -1,
        )
        return self.stack[: k + 1]

    def _unlabelled(self, content: str, indent: int, kind: str) -> None:
        owner = self._owner(indent)
        self.out.append(
            Paragraph(
                len(self.out),
                len(owner),
                None,
                _path(owner, self.section) or None,
                content,
                self.section,
                kind=kind,
            )
        )

    def _table_line(
        self, n: int, content: str, indent: int, opening: re.Match[str] | None
    ) -> None:
        """Every line of a table block is indented like its `{|` line and
        belongs, as an unlabelled block, to that line's owner."""
        if self.table is None:
            self.table = _Table(n, indent)
        elif opening:
            raise TextFormatError(n, "a table inside a table")
        elif indent != self.table.indent:
            raise TextFormatError(n, "a table line indented unlike its `{|`")
        elif content == TABLE_CLOSE:
            self._close_table(n)
        else:
            try:
                self.table.rows.append(parse_table_row(content))
            except ValueError as exc:
                raise TextFormatError(n, f"table row: {exc}") from None
        if opening and TABLE_TOKEN_RE.search(opening.group(1) or ""):
            raise TextFormatError(n, "table markup inside a caption")
        self._unlabelled(content, indent, "table")

    def _close_table(self, n: int) -> None:
        assert self.table is not None
        if not self.table.rows:
            raise TextFormatError(n, "a table with no rows")
        try:
            table_width(self.table.rows)
        except ValueError as exc:
            raise TextFormatError(self.table.line, f"table: {exc}") from None
        self.table = None

    def _heading(self, n: int, content: str, indent: int) -> bool:
        """Rule 7: a section heading closes every open level. Return whether
        the line is one."""
        h = SECTION_HEADING_RE.match(content)
        found = heading_section(h, self.roman + 1) if h else None
        if h is None or found is None:
            return False
        if indent:
            raise TextFormatError(n, "a section heading must not be indented")
        self.section = found
        if h.group("rom"):
            self.roman += 1
        if found in self.sections:
            raise TextFormatError(n, f"section {found} repeats")
        self.sections.add(found)
        self.stack = []
        self.out.append(Paragraph(len(self.out), 0, None, None, content, found, True))
        return True

    def _item(self, n: int, content: str, indent: int, formula: bool) -> None:
        m = LABEL_GROUP_RE.match(content)
        tokens = LABEL_TOKEN_RE.findall(m.group(2)) if m else []
        if m is None or not all(label_values(t) for t in tokens):
            self._unlabelled(content, indent, "formula" if formula else "text")
        else:
            self._labelled(n, m, tokens, content, indent)

    def _labelled(
        self, n: int, m: re.Match[str], tokens: list[str], content: str, indent: int
    ) -> None:
        body = content[m.end() :]
        body = body[1:] if body.startswith(" ") else body
        r = _choose(self.stack, tokens[0], indent, n)
        del self.stack[r.level :]
        self.stack.append(_Level(r.style, r.value, tokens[0], indent, False))
        self.gaps += 1 if r.gap else 0
        for tok in tokens[1:]:
            # A later token of a compound label is a child of the one before.
            style, value = _first_style(label_values(tok))
            self.stack.append(_Level(style, value, tok, indent, True))
            self.gaps += 1 if value != 1 else 0
        for i, tok in enumerate(tokens):
            depth = len(self.stack) - len(tokens) + i + 1
            self.out.append(
                Paragraph(
                    len(self.out),
                    depth,
                    ((m.group(1) or "") if i == 0 else "") + f"({tok})",
                    _path(self.stack[:depth], self.section),
                    body if i == len(tokens) - 1 else "",
                    self.section,
                )
            )


def paragraph_ref_paths(qualifier: str, paths: set[str]) -> list[str] | None:
    """Match a verbatim cert-basis `paragraph` qualifier against a version's
    paragraph paths. Return the tokens that match no path, or None when the
    qualifier isn't a run of `(x)` tokens at all.

    A qualifier lists paragraphs the way TCDSs write them: `(a)(1)(2)(b)` is
    (a)(1), (a)(2) and (b). Each token descends into the current paragraph or
    names a sibling of it or of one of its ancestors. `(c3)` is read as
    `(c)(3)`. In a text with section headings every path starts with its
    section (`G23.3(a)`), so a bare qualifier matches nothing there: it
    doesn't say which section's `(a)` it means.
    """
    if re.sub(r"\([A-Za-z0-9]+\)|\s", "", qualifier):
        return None
    tokens: list[str] = []
    for tok in re.findall(r"\(([A-Za-z0-9]+)\)", qualifier):
        m = re.fullmatch(r"([a-z])(\d+)", tok)
        tokens.extend(m.groups() if m else [tok])
    cur: list[str] = []
    unmatched: list[str] = []
    for tok in tokens:
        for k in range(len(cur), -1, -1):
            cand = cur[:k] + [tok]
            if "".join(f"({t})" for t in cand) in paths:
                cur = cand
                break
        else:
            unmatched.append(f"({tok})")
    return unmatched
