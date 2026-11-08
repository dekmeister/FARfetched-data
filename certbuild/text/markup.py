"""Inline markup: sub/superscripts and formulas (docs/DATA_FORMAT.md §Inline markup).

Pure string code: no I/O, no sqlite3.
"""

from __future__ import annotations

import re


# Inline markup (docs/DATA_FORMAT.md §Inline markup). `_{x}` is a subscript,
# `^{x}` a superscript: non-empty, no `{ } $` inside, no nesting. A line that
# is wholly `$$ <formula> $$` (after its indentation) is a display formula.
# A bare `_ ^ { }` is literal; `$$` anywhere else is an error.
FORMULA_MARK = "$$"
_INLINE_OPEN_RE = re.compile(r"[_^]\{")
_INLINE_RE = re.compile(r"([_^])\{([^{}$\n]+)\}")
_FORMULA_RE = re.compile(r"\$\$ (\S(?:.*\S)?) \$\$")


def inline_error(content: str) -> str | None:
    """Why the sub/superscript markup in `content` breaks the format, or
    None when it is valid (or absent)."""
    for m in _INLINE_OPEN_RE.finditer(content):
        if not _INLINE_RE.match(content, m.start()):
            return (
                f"malformed `{m.group(0)}…}}` at column {m.start() + 1} "
                "(unclosed, empty, nested or containing `$`)"
            )
    return None


def formula_body(content: str) -> str | None:
    """The formula of a display formula line (without its indentation), or
    None when the line isn't one."""
    m = _FORMULA_RE.fullmatch(content)
    return m.group(1) if m and FORMULA_MARK not in m.group(1) else None


def strip_inline(text: str) -> str:
    """`text` with sub/superscript markup removed: `V_{A}` → `VA`."""
    return _INLINE_RE.sub(r"\2", text)
