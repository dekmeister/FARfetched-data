"""Sort keys. `sort_key` is part of the API tools/ uses (tests/test_tools_api.py)."""

from __future__ import annotations

import re


def sort_key(number: str) -> str:
    """Natural sort key: zero-pad every digit run, so 175 sorts before 1309."""
    return re.sub(r"\d+", lambda m: m.group().zfill(6), number)
