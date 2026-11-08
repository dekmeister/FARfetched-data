"""The label-line text parser (docs/DATA_FORMAT.md §Text format)."""

from __future__ import annotations

import re
from dataclasses import dataclass

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
    if len(lines) == 1:
        n, raw = lines[0]
        if raw[0].isspace():
            raise TextFormatError(n, "a single-line text must not be indented")
        if TABLE_TOKEN_RE.search(raw) or is_table_row(raw):
            raise TextFormatError(n, "table markup in a single-line text")
        if FORMULA_MARK in raw:
            raise TextFormatError(n, "`$$` in a single-line text")
        if err := inline_error(raw):
            raise TextFormatError(n, err)
        return ParsedText((Paragraph(0, 0, None, None, raw),), False, 0)

    stack: list[_Level] = []
    out: list[Paragraph] = []
    gaps = 0
    section: str | None = None
    sections: set[str] = set()
    roman = 0  # the last roman section heading read (I = 1)
    # An open table block: (line it opened on, its indentation, rows so far).
    table: tuple[int, int, list[list[TableCell]]] | None = None
    for n, raw in lines:
        content = raw.lstrip(" ")
        indent = len(raw) - len(content)
        if content[0].isspace():
            raise TextFormatError(n, "indentation must be spaces")
        if err := inline_error(content):
            raise TextFormatError(n, err)
        formula = formula_body(content) is not None
        if FORMULA_MARK in content and (table is not None or not formula):
            raise TextFormatError(
                n, "`$$` outside a formula line (a whole line `$$ … $$`)"
            )
        opening = TABLE_OPEN_RE.match(content)
        if table is not None or opening:
            # Tables: every line of the block is indented like its `{|` line
            # and belongs, as an unlabelled block, to that line's owner.
            if table is None:
                table = (n, indent, [])
            elif opening:
                raise TextFormatError(n, "a table inside a table")
            elif indent != table[1]:
                raise TextFormatError(n, "a table line indented unlike its `{|`")
            elif content == TABLE_CLOSE:
                if not table[2]:
                    raise TextFormatError(n, "a table with no rows")
                try:
                    table_width(table[2])
                except ValueError as exc:
                    raise TextFormatError(table[0], f"table: {exc}") from None
                table = None
            else:
                try:
                    table[2].append(parse_table_row(content))
                except ValueError as exc:
                    raise TextFormatError(n, f"table row: {exc}") from None
            if opening and TABLE_TOKEN_RE.search(opening.group(1) or ""):
                raise TextFormatError(n, "table markup inside a caption")
            k = next(
                (i for i in range(len(stack) - 1, -1, -1) if stack[i].indent < indent),
                -1,
            )
            owner = stack[: k + 1]
            out.append(
                Paragraph(
                    len(out),
                    len(owner),
                    None,
                    _path(owner, section) or None,
                    content,
                    section,
                    kind="table",
                )
            )
            continue
        if TABLE_TOKEN_RE.search(content) or is_table_row(content):
            raise TextFormatError(n, "table markup outside a table block")
        h = SECTION_HEADING_RE.match(content)
        found = heading_section(h, roman + 1) if h else None
        if h and found:
            # Rule 7: a section heading closes every open level.
            if indent:
                raise TextFormatError(n, "a section heading must not be indented")
            section = found
            roman = roman + 1 if h.group("rom") else roman
            if section in sections:
                raise TextFormatError(n, f"section {section} repeats")
            sections.add(section)
            stack = []
            out.append(Paragraph(len(out), 0, None, None, content, section, True))
            continue
        m = LABEL_GROUP_RE.match(content)
        tokens = LABEL_TOKEN_RE.findall(m.group(2)) if m else []
        if not (m and all(label_values(t) for t in tokens)):
            # Rule 5: the innermost open item whose label line is indented less.
            k = next(
                (i for i in range(len(stack) - 1, -1, -1) if stack[i].indent < indent),
                -1,
            )
            owner = stack[: k + 1]
            out.append(
                Paragraph(
                    len(out),
                    len(owner),
                    None,
                    _path(owner, section) or None,
                    content,
                    section,
                    kind="formula" if formula else "text",
                )
            )
            continue
        assert m is not None
        body = content[m.end() :]
        body = body[1:] if body.startswith(" ") else body
        r = _choose(stack, tokens[0], indent, n)
        del stack[r.level :]
        stack.append(_Level(r.style, r.value, tokens[0], indent, False))
        gaps += 1 if r.gap else 0
        for tok in tokens[1:]:
            # A later token of a compound label is a child of the one before.
            style, value = _first_style(label_values(tok))
            stack.append(_Level(style, value, tok, indent, True))
            gaps += 1 if value != 1 else 0
        for i, tok in enumerate(tokens):
            depth = len(stack) - len(tokens) + i + 1
            out.append(
                Paragraph(
                    len(out),
                    depth,
                    ((m.group(1) or "") if i == 0 else "") + f"({tok})",
                    _path(stack[:depth], section),
                    body if i == len(tokens) - 1 else "",
                    section,
                )
            )
    if table is not None:
        raise TextFormatError(table[0], "a table that is never closed (`|}`)")
    return ParsedText(tuple(out), True, gaps)


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
