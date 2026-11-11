"""The checks behind `scripts/scan_data.py`: patterns of damage seen before.

Each check is a pure function from one field (a provision version's text or
title, or an aircraft basis line's `raw_reference`) to the suspicious
spans in it. It names where the pattern was first seen: a GitHub issue
(`#20`) or an ISSUES.md item (`CAR-3`). A hit is a lead to read against the
source, not a verdict (CLAUDE.md, "Reproducible is not correct"): some hits
are faithful to the source, and the baseline file records the ones already
known.

To add a check: write a function `(Field, Context) -> Iterable[Hit]`, add
a `Check` row to `CHECKS`, and add a hit and a miss to
tests/test_scan_data.py.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass

from certbuild.text import (
    TABLE_CLOSE,
    formula_body,
    is_table_row,
    strip_inline,
)
from certbuild.text.tables import TABLE_OPEN_RE

CONTEXT_CHARS = 40
MAX_MATCH = 100
MAX_CONTEXT = 240


@dataclass(frozen=True)
class Field:
    """One string that goes into the database, and where it came from."""

    issuer: str
    document: str
    key: str
    designator: str
    field: str  # "text", "title" or "basis[N]"
    value: str


@dataclass(frozen=True)
class Hit:
    """A suspicious span. `match` identifies it in the baseline; `context`
    is for the reader."""

    match: str
    context: str


@dataclass(frozen=True)
class Context:
    """Corpus-wide facts some checks need (built once per scan)."""

    vocabulary: Counter[str]


@dataclass(frozen=True)
class Check:
    name: str
    fields: frozenset[str]  # which field kinds it reads: text, title, basis
    seen_in: str
    about: str
    run: Callable[[Field, Context], Iterable[Hit]]


def kind(field: Field) -> str:
    return "basis" if field.field.startswith("basis") else field.field


def hit(value: str, m: re.Match[str], group: int = 0) -> Hit:
    """A hit for match `m`, with some text either side. Long matches are cut
    so the baseline stays readable."""
    a = max(0, m.start() - CONTEXT_CHARS)
    b = min(len(value), m.end() + CONTEXT_CHARS, a + MAX_CONTEXT)
    context = value[a:b].replace("\n", " ⏎ ")
    return Hit(match=m.group(group)[:MAX_MATCH].replace("\n", " ⏎ "), context=context)


def finditer(rx: re.Pattern[str], value: str, group: int = 0) -> Iterator[Hit]:
    for m in rx.finditer(value):
        yield hit(value, m, group)


def prose_lines(text: str) -> Iterator[str]:
    """The lines of a text that are running prose: not table lines, not
    display formula lines. Indentation stripped."""
    in_table = False
    for line in text.split("\n"):
        s = line.strip()
        if TABLE_OPEN_RE.match(s):
            in_table = True
        if in_table:
            in_table = s != TABLE_CLOSE
            continue
        if s and not is_table_row(s) and formula_body(s) is None:
            yield s


def prose(text: str) -> str:
    """Prose lines joined by line breaks, sub/superscript markup removed."""
    return strip_inline("\n".join(prose_lines(text)))


# --- characters -----------------------------------------------------------

_ENCODING_RE = re.compile(
    r"[\x00-\x08\x0b-\x1f\x7f-\x9f\ufffd\ufb00-\ufb06]|â€|Ã[\x80-\xbf]|Â(?=\s)"
)


def encoding(f: Field, _: Context) -> Iterable[Hit]:
    for h in finditer(_ENCODING_RE, f.value):
        yield Hit(match=ascii(h.match), context=ascii(h.context))


_PRIVATE_USE_RE = re.compile(r"[\ue000-\uf8ff]+")


def private_use(f: Field, _: Context) -> Iterable[Hit]:
    for h in finditer(_PRIVATE_USE_RE, f.value):
        yield Hit(match=ascii(h.match), context=h.context)


# Stacked-bracket pieces (⎛⎜⎝ …), math alphanumerics (𝑋, 𝛼) and integrals:
# what a PDF text layer gives for a typeset display formula.
_FORMULA_GLYPH_RE = re.compile(r"[\u239b-\u23b3\u23b7\U0001d400-\U0001d7ff∫∑∏]+")


def formula_glyphs(f: Field, _: Context) -> Iterable[Hit]:
    return finditer(_FORMULA_GLYPH_RE, prose(f.value))


# A line with `=` whose neighbourhood is mostly one-character tokens:
# a stacked fraction or sub/superscripts read in row order ("πV ω = 2V A").
_ONE_CHAR_RE = re.compile(r"^[^\W\d_]$|^[α-ωΑ-Ω]\w?$|^\d$")
EQUATION_WINDOW = 4


def scrambled_equation(f: Field, _: Context) -> Iterable[Hit]:
    """An `=` whose neighbours are mostly one-character tokens: a stacked
    fraction or sub/superscripts read in row order (`πV ω = 2V A`)."""
    for line in prose(f.value).split("\n"):
        if "=" not in line:
            continue
        tokens = line.split()
        for i, token in enumerate(tokens):
            if "=" not in token:
                continue
            window = tokens[max(0, i - EQUATION_WINDOW) : i + EQUATION_WINDOW + 1]
            singles = sum(1 for t in window if _ONE_CHAR_RE.match(t))
            if singles >= 3 and singles * 2 >= len(window) - 1:
                excerpt = " ".join(window)
                yield Hit(match=excerpt, context=excerpt)


# Symbols that regulation text doesn't print but OCR and PDF extraction
# produce. `|` and `{}` outside table/inline markup count too.
_SYMBOL_RE = re.compile(r"[¢¥©®€«»~@`´¦¬■□▪►◄\\]|(?<!\S)\|(?!\S)|(?<=\w)[!?](?=\w)")


def stray_symbols(f: Field, _: Context) -> Iterable[Hit]:
    return finditer(_SYMBOL_RE, prose(f.value))


_BRACE_RE = re.compile(r"[{}]")
_INLINE_SPAN_RE = re.compile(r"[_^]\{[^{}$\n]+\}")


def stray_braces(f: Field, _: Context) -> Iterable[Hit]:
    """`{e)`, `(b}`: OCR'd parentheses (CAR-4). Inline markup is removed
    first, and table lines are skipped."""
    text = "\n".join(prose_lines(f.value))
    masked = _INLINE_SPAN_RE.sub(lambda m: " " * len(m.group()), text)
    for m in _BRACE_RE.finditer(masked):
        a, b = max(0, m.start() - 12), m.end() + 12
        yield Hit(match=text[max(0, m.start() - 3) : m.end() + 3], context=text[a:b])


def literal_escape(f: Field, _: Context) -> Iterable[Hit]:
    """A literal backslash-n, or DRS fraction markup `\\1/2\\` (FAA-24)."""
    return finditer(re.compile(r"\\n|\\\d+(?:/\d+)?\\?|\(\\\d"), f.value)


# --- structure leaking in ---------------------------------------------------

_TOC_ENTRY_RE = re.compile(
    r"(?<![§\w.])(?:USAR\.)?(\d{1,2})\.(\d{1,4})([a-z]?)\s+(?:\[?[A-Z][a-z]|[A-Z]{2})"
)
TOC_MIN_RUN = 5
# A number written as a citation (`Sec. 25.858`, `CS 25.858`) is not an entry.
_CITED_RE = re.compile(r"(?:Secs?\.|CS|§)\s*$")


def toc_run(f: Field, _: Context) -> Iterable[Hit]:
    """A run of rising section numbers each followed by a title: a table of
    contents or index read as text (#21)."""
    major = re.sub(r"\D", "", f.document)
    # DOD has no section prefix; appendices number their own sub-sections.
    if not major or f.issuer == "DOD" or not f.key[:1].isdigit():
        return
    run: list[re.Match[str]] = []
    for m in _TOC_ENTRY_RE.finditer(f.value):
        before = f.value[max(0, m.start() - 6) : m.start()]
        if m.group(1) != major or _CITED_RE.search(before):
            continue
        if run and int(m.group(2)) <= int(run[-1].group(2)):
            yield from _toc_flush(f.value, run)
            run = []
        run.append(m)
    yield from _toc_flush(f.value, run)


def _toc_flush(value: str, run: list[re.Match[str]]) -> Iterable[Hit]:
    if len(run) >= TOC_MIN_RUN:
        first, last = run[0], run[-1]
        span = value[first.start() : last.end() + CONTEXT_CHARS]
        numbers = f"{first.group(1)}.{first.group(2)}..{last.group(1)}.{last.group(2)}"
        yield Hit(match=f"{len(run)} entries {numbers}", context=span[:160])


def dot_leaders(f: Field, _: Context) -> Iterable[Hit]:
    """`Gasoline.......` (#21: an index; or a flattened table). A run of
    underscores alone is a placard's fill-in blank, and is fine."""
    rx = re.compile(r"\.{5,}|(?:\. ){4,}|…{2,}|_+\.[._]*|\.+_[._]*")
    return finditer(rx, prose(f.value))


_CAPTION_RE = re.compile(
    r"(?:^|(?<=[.;:)] )|(?<=\d )|(?<=⏎ ))"
    r"((?:FIGURE|Figure|FIG\.|Fig\.|TABLE|Table)\s*[A-Z]?\d+(?:[-–.]\d+)?"
    r"(?:\s*\(\w\)|\{\w\})?(?:\s*[-—–.:]+\s*|\s+)\(?[A-Z][A-Za-z-]+)",
    re.MULTILINE,
)


def figure_caption(f: Field, _: Context) -> Iterable[Hit]:
    """A figure or table caption in running text (#20, EASA-18). Captions
    the source prints under a reproduced table belong on the `{|` line."""
    return finditer(_CAPTION_RE, prose(f.value), 1)


_CAPS_WORD = r"[A-Z][A-Z'’&]+[,;:]?"
_CAPS_RUN_RE = re.compile(rf"\b{_CAPS_WORD}(?:[ \-]+{_CAPS_WORD}){{3,}}\b")
_LONG_CAPS_RE = re.compile(r"[A-Z]{5,}")
_TRAILING_HEADING_RE = re.compile(
    rf"(?:{_CAPS_WORD}[ \-]+){{1,}}{_CAPS_WORD}\)?\s*$"
    r"|(?<=[.;:] )(?:[A-Z][a-z]+ (?:and |of |or |the |for |to )*){1,}[A-Z][a-z]+\s*$"
)


def caps_run(f: Field, _: Context) -> Iterable[Hit]:
    """Four or more words in capitals: a centre heading or figure lettering
    in the text (#2, CAR-3)."""
    for h in finditer(_CAPS_RUN_RE, prose(f.value)):
        if len(_LONG_CAPS_RE.findall(h.match)) >= 2:  # not a run of acronyms
            yield h


def trailing_heading(f: Field, _: Context) -> Iterable[Hit]:
    """The text ends in a heading with no full stop: the next group's
    centre heading run in (#2, EASA-12)."""
    lines = list(prose_lines(f.value))
    if lines:
        yield from finditer(_TRAILING_HEADING_RE, lines[-1])


_AMENDMENT_RE = re.compile(
    r"(?i)to read as follows|\bby (?:amending|adding|deleting|redesignating) "
    r"(?:§|a new|the|paragraph|subparagraph)|\[(?:amendment|deletion)\]"
    r"|\(as published in the federal register|\bfiled,? [a-z]+\.? \d"
    r"|\bF\.\s?R\. Doc\.|\d:\d\d [ap]\.?\s?m\.?\)"
)


def amendment_text(f: Field, _: Context) -> Iterable[Hit]:
    """Amendatory instructions or a Federal Register filing line read as
    regulation text (CAR-3, CAR-4, CAR-7)."""
    return finditer(_AMENDMENT_RE, f.value)


_LABEL_PREFIX_RE = re.compile(r"^\[?(?:\(\w{1,5}\))+\s*")


def lowercase_start(f: Field, _: Context) -> Iterable[Hit]:
    """The text opens mid-sentence: a wrapped title or the tail of the
    previous section (#18, NATO-7)."""
    first = f.value.lstrip()
    if re.match(r"[a-z]{2,}\b(?![.)])", first) and not re.match(
        r"(?:e\.g|i\.e)", first
    ):
        yield Hit(match=first.split()[0], context=first[:80])


_TRUNCATED_RE = re.compile(
    r"(?:§|,|\band|\bor|\bthe|\bof|\bto|\bwith|\bby|\bfor|\bin|\ba|\ban)\s*$"
)


def truncated_end(f: Field, _: Context) -> Iterable[Hit]:
    """The text stops on a `§`, a comma or a function word: words lost at
    a section boundary (CAR-7)."""
    lines = list(prose_lines(f.value))
    if lines:
        yield from finditer(_TRUNCATED_RE, lines[-1][-60:])


_DROPPED_RE = re.compile(
    r"\b(?:as|is|of|to|than|and|or|between|equal|exceeds?|at|the|by|from|below"
    r"|above|within) [,;:.)](?!\w)"
    r"|\b(?:at|than|of|to|and) \d+(?:\.\d+)? [,;.)](?!\w)"
    r"|(?:^|[;:(]|\bwhere-*)\s*=\s"  # a definition with no symbol: `; = Density`
    r"|\bas follows\W{0,4}\s+where\b",  # the formula itself is missing
    re.MULTILINE,
)


def dropped_symbol(f: Field, _: Context) -> Iterable[Hit]:
    """A symbol or formula the source had only as an image is missing:
    `greater than .`, `at 1.4 ;`, `the highest value of and ;`, `; = Density
    of air`, `computed as follows--] where--` (#4, #24, FAA-25)."""
    return finditer(_DROPPED_RE, prose(f.value))


# --- words ------------------------------------------------------------------

# The second word is a lookahead, so pairs overlap: `without ex~ ceptional`.
_PAIR_RE = re.compile(r"\b([A-Za-z]{1,12})(-|~)? (?=([a-z]{1,12})\b)")
_COMMON = 5


def split_word(f: Field, ctx: Context) -> Iterable[Hit]:
    """A word broken in two: letter-spacing (`m ight`, EASA-11) or a line-end
    hyphen kept (`air- plane`, `ex~ ceptional`). Flagged when the joined
    word is common in the corpus and a part is not."""
    vocab = ctx.vocabulary
    text = prose(f.value)
    for m in _PAIR_RE.finditer(text):
        a, mark, b = m.group(1), m.group(2), m.group(3)
        joined = (a + b).lower()
        if vocab[joined] < _COMMON:
            continue
        if mark or (vocab[a.lower()] <= 1 or vocab[b] <= 1):
            h = hit(text, m)
            yield Hit(match=f"{h.match}{b}", context=h.context)


_OCR_LABEL_RE = re.compile(
    r"(?m)^\s*\[?(\{[a-z0-9]{1,3}\)|\([a-z0-9]{1,3}\}|\((?![ivxl]+\))"
    r"(?:([a-z])(?!\2)[a-z]|[a-z]0|0[a-z]?|[0-9][a-z]|[a-z][0-9])\))"
)


def ocr_label(f: Field, _: Context) -> Iterable[Hit]:
    """A paragraph label OCR misread: `(bo)`, `(ce)`, `{e)`, `(0)` (CAR-1)."""
    return finditer(_OCR_LABEL_RE, f.value, 1)


_VSPEED_RE = re.compile(r"\bV[A-Za-z]{0,3}[\]}|](?!\w)|\bV_\.|\bV [a-z]{1,2}\b(?= \()")


def vspeed_ocr(f: Field, _: Context) -> Iterable[Hit]:
    """A V-speed with OCR junk for its subscript: `Vs]`, `V_.` (#23,
    CAR-5). Not FAA, where `[1.13 VSR]` is a change bracket."""
    if f.issuer != "FAA":
        yield from finditer(_VSPEED_RE, prose(f.value))


def unbalanced_brackets(f: Field, _: Context) -> Iterable[Hit]:
    """`shall]`: a `]` with no `[` (CAR-3). Not FAA, whose change brackets
    span paragraphs (TEXT-7)."""
    if f.issuer == "FAA":
        return
    depth = 0
    for m in re.finditer(r"[\[\]]", f.value):
        depth += 1 if m.group() == "[" else -1
        if depth < 0:
            yield hit(f.value, m)
            depth = 0


# Case flipping inside a word (`OrRECTION`, `LiMIT`, `aaD`), a digit
# between letters (`SHA1t`), or a run of lone characters (`q u a o i a`).
_MIXED_RE = re.compile(
    r"\b[A-Z][a-z]{1,2}[A-Z]{2,}[a-z]*\b|\b[a-z]+[A-Z][a-z]+[A-Z]\w*\b"
    r"|\b[A-Za-z]*[A-Za-z][0-9][a-z][A-Za-z]*\b|(?:(?<!\S)\S \b){8,}"
)
_MIXED_OK = frozenset({"McDonnell", "LiDAR", "iPad"})
GIBBERISH_MIN = 3


def gibberish(f: Field, _: Context) -> Iterable[Hit]:
    """OCR word salad from figure lettering: `OrRECTION`, `SHA1t`,
    `RULTIPLYWG` (#20, CAR-3). Flagged when a text has several."""
    text = prose(f.value)
    found = [m for m in _MIXED_RE.finditer(text) if m.group() not in _MIXED_OK]
    if len(found) >= GIBBERISH_MIN:
        words = " ".join(m.group() for m in found[:6])
        yield Hit(match=f"{len(found)} words", context=words)


_NUMBER = r"[-+−]?\d+(?:[.,·]\d+)?%?"
_NUMERIC_RUN_RE = re.compile(rf"(?:{_NUMBER}\s+){{9,}}{_NUMBER}")


def numeric_run(f: Field, _: Context) -> Iterable[Hit]:
    """Ten or more bare numbers in a row outside a table: chart axis labels
    or a flattened table (EASA-17, EASA-18, NATO-6, DOD-8)."""
    return finditer(_NUMERIC_RUN_RE, prose(f.value))


# --- aircraft basis lines ------------------------------------------------

_FOOTER_RE = re.compile(r"(?i)\bissue:?\s*\d+\b.*\bdate:?\s*\d|\bpage \d+ of \d+\b")


def basis_footer(f: Field, _: Context) -> Iterable[Hit]:
    """A TCDS page footer or header read as a basis line (ETCDS-16)."""
    return finditer(_FOOTER_RE, f.value)


_HEADING_LINE_RE = re.compile(
    r"^(?:\d+(?:\.\d+)*\.?|[IVX]+\.)\s+(?:Special Conditions?|Exemptions?|"
    r"Equivalent (?:Level of )?Safety|Certification Basis|Environmental|"
    r"Operational Suitability|Elect(?:ed|s) to comply)\b.*$",
    re.IGNORECASE,
)


def basis_heading(f: Field, _: Context) -> Iterable[Hit]:
    """A TCDS section heading, with its number, read as a basis line."""
    return finditer(_HEADING_LINE_RE, f.value)


_LIST_HEADER_RE = re.compile(
    r"(?i)\bthe following\b.{0,40}\b(?:paragraphs|sections)\b.*$"
)
_SECTION_NUMBER_RE = re.compile(r"\b\d{2}\.\s?\d{2,4}\b")


def basis_list_header(f: Field, _: Context) -> Iterable[Hit]:
    """`Plus the following CS 25 paragraphs …`: the header of a list on the
    next line, read as a reference to the whole document (ETCDS-16). A line
    that carries its own list (`… : 23.611, 23.777`) is fine."""
    for h in finditer(_LIST_HEADER_RE, f.value):
        if not _SECTION_NUMBER_RE.search(h.match):
            yield h


TEXT = frozenset({"text"})
TEXT_TITLE = frozenset({"text", "title"})
ALL = frozenset({"text", "title", "basis"})
BASIS = frozenset({"basis"})

CHECKS: tuple[Check, ...] = (
    Check(
        "encoding",
        ALL,
        "EASA-24",
        "control characters, cp1252 bytes, mojibake",
        encoding,
    ),
    Check(
        "private-use", ALL, "NATO-4", "private-use glyphs (Symbol font)", private_use
    ),
    Check(
        "formula-glyphs",
        TEXT,
        "#4, #24, TEXT-11",
        "stacked brackets, math italics, integrals in prose",
        formula_glyphs,
    ),
    Check(
        "scrambled-equation",
        TEXT,
        "#4, #24, TEXT-11",
        "an equation read in row order",
        scrambled_equation,
    ),
    Check(
        "dropped-symbol",
        TEXT,
        "#4, #24, FAA-25",
        "a word or number then bare punctuation",
        dropped_symbol,
    ),
    Check(
        "stray-symbols",
        TEXT_TITLE,
        "#23, CAR-3",
        "OCR symbols outside markup",
        stray_symbols,
    ),
    Check(
        "stray-braces",
        TEXT,
        "CAR-4",
        "braces outside table/inline markup",
        stray_braces,
    ),
    Check(
        "literal-escape",
        TEXT_TITLE,
        "FAA-24",
        "literal \\n or DRS \\1/2\\",
        literal_escape,
    ),
    Check("toc-run", TEXT, "#21", "a table of contents read as text", toc_run),
    Check("dot-leaders", TEXT, "#21", "index dot leaders", dot_leaders),
    Check(
        "figure-caption",
        TEXT,
        "#20, EASA-18",
        "a caption in running text",
        figure_caption,
    ),
    Check("caps-run", TEXT, "#2, CAR-3", "four or more words in capitals", caps_run),
    Check(
        "trailing-heading",
        TEXT,
        "#2, EASA-12",
        "a heading run in at the end",
        trailing_heading,
    ),
    Check(
        "amendment-text",
        TEXT,
        "CAR-3, CAR-4, CAR-7",
        "amendatory instructions or FR filing lines",
        amendment_text,
    ),
    Check(
        "lowercase-start",
        TEXT,
        "#18, NATO-7",
        "the text opens mid-sentence",
        lowercase_start,
    ),
    Check("truncated-end", TEXT, "CAR-7", "the text stops mid-sentence", truncated_end),
    Check("split-word", TEXT_TITLE, "EASA-11", "a word broken in two", split_word),
    Check("ocr-label", TEXT, "CAR-1", "a misread paragraph label", ocr_label),
    Check(
        "vspeed-ocr", TEXT, "#23, CAR-5", "a V-speed with a junk subscript", vspeed_ocr
    ),
    Check("unbalanced-brackets", TEXT, "CAR-3", "a ] with no [", unbalanced_brackets),
    Check("gibberish", TEXT, "#20, CAR-3", "OCR word salad", gibberish),
    Check(
        "numeric-run",
        TEXT,
        "EASA-17, EASA-18, NATO-6",
        "ten bare numbers in a row",
        numeric_run,
    ),
    Check("basis-footer", BASIS, "ETCDS-16", "a TCDS page footer", basis_footer),
    Check("basis-heading", BASIS, "ETCDS-16", "a TCDS section heading", basis_heading),
    Check(
        "basis-list-header",
        BASIS,
        "ETCDS-16",
        "a 'the following paragraphs' header",
        basis_list_header,
    ),
)
