"""Paragraph labels and section headings (docs/DATA_FORMAT.md §Text format)."""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# Provision text format: "label-line text" (docs/DATA_FORMAT.md §Text format)
#
# A text with one line is flat. A text with several lines is structured: one
# block per line; a line may open with a label group such as `(a)`, `[(4)` or
# `(c)(1)`. Depth comes from the labels (a style stack); indentation picks
# between the readings the labels allow and must agree with the chosen one.
# Indentation is always compared with other lines, never with a fixed width.

LABEL_GROUP_RE = re.compile(r"(\[ ?)?((?:\([A-Za-z0-9]{1,5}\))+)(?= |$)")
LABEL_TOKEN_RE = re.compile(r"\(([A-Za-z0-9]{1,5})\)")
# A section heading inside a provision text: an appendix assembled from its
# sections (`Sec. F23.2 Part II--Test Method ...`), or one divided by roman
# numerals (`IV. Static longitudinal stability`). Labels restart under it.
SECTION_HEADING_RE = re.compile(
    r"Sec\. (?P<sec>[A-Z]\d+\.\d+[a-z]?)(?= |$)|(?P<rom>[IVX]{1,6})\. (?=[A-Z])"
)
_ROMAN_DIGITS = {"i": 1, "v": 5, "x": 10}
# Lower to upper bound of roman labels: i..xxxix. `l`, `c`, `d`, `m` are
# letters, never numerals.
_MAX_ROMAN = 39


def _roman_value(token: str) -> int | None:
    s = token.lower()
    if not s or any(ch not in _ROMAN_DIGITS for ch in s):
        return None
    total = 0
    for i, ch in enumerate(s):
        v = _ROMAN_DIGITS[ch]
        nxt = _ROMAN_DIGITS[s[i + 1]] if i + 1 < len(s) else 0
        total += -v if v < nxt else v
    if not 1 <= total <= _MAX_ROMAN or _to_roman(total) != s:
        return None
    return total


def heading_section(m: re.Match[str], next_roman: int = 1) -> str | None:
    """The section number a `SECTION_HEADING_RE` match names, or None.

    A roman heading counts only as the next numeral of the run (I, II, III, ...),
    so `I. ` or `V. ` elsewhere in a text stays ordinary text."""
    if m.group("sec"):
        return m.group("sec")
    rom = m.group("rom")
    return rom if _roman_value(rom) == next_roman else None


def _to_roman(n: int) -> str:
    out = ""
    for value, digits in ((10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while n >= value:
            out += digits
            n -= value
    return out


def label_values(token: str) -> dict[str, int]:
    """Every style a label token can be read in, with its value in that style.

    Styles: `lower_alpha` (a..z, then aa, bb, ...), `number`, `lower_roman`
    (i..xxxix), `upper_alpha`, `upper_roman`. An empty result means the token
    is not a label (e.g. `(OEI)`), so its line is unlabelled.
    """
    out: dict[str, int] = {}
    if token.isdigit() and not token.startswith("0"):
        out["number"] = int(token)
    if re.fullmatch(r"([a-z])\1*", token):
        out["lower_alpha"] = 26 * (len(token) - 1) + ord(token[0]) - ord("a") + 1
    if re.fullmatch(r"([A-Z])\1*", token):
        out["upper_alpha"] = 26 * (len(token) - 1) + ord(token[0]) - ord("A") + 1
    roman = _roman_value(token)
    if roman is not None:
        out["lower_roman" if token.islower() else "upper_roman"] = roman
    return out
