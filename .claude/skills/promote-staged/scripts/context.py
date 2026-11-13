"""Source context for promotion reading: find a phrase in a local source copy.

Readers judge a change against the source, so each item carries a short slice
of the source text around it: the lines, and the PDF page they sit on. This
module finds that slice cheaply, without the reader opening the whole PDF.

The text is the pipeline's own copy (TCDS: the pdftotext cache in
tools/out/derived/tcds_text, which keeps form feeds between pages; documents:
the extracted copy, or the DRS JSON). It is evidence, not truth: it can share a
pdftotext bug with the data, which is why every slice names its page, so the
reader can open the page image when the slice looks wrong.

Matching is by word sequence (case-folded, outer punctuation stripped), so it
survives line wraps and column gaps but not interleaved columns. When the
whole phrase isn't found, `locate` retries with its first 12, 6 and 3 words.
Read-only.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

TCDS_TEXT = Path("tools/out/derived/tcds_text")
INPUT = Path("input")
STRIP = ".,;:()[]{}\"'`«»“”‘’"
DASHES = str.maketrans({"–": "-", "—": "-", "‐": "-", "‑": "-"})
TAG_RE = re.compile(r"<[^>]+>")


def tcds_paths(tcds: dict[str, Any]) -> tuple[Path, Path]:
    """(PDF, pdftotext cache) for one TCDS revision. Either may not exist."""
    num, rev = tcds["tcds_number"], tcds["revision"]
    if tcds["issuer"] == "FAA":
        return (
            INPUT / "TCDS/FAA" / f"{num}_Rev{rev}.pdf",
            TCDS_TEXT / f"{num}_Rev{rev}.txt",
        )
    return (
        INPUT / "TCDS/EASA" / f"{num}_Issue{rev}.pdf",
        TCDS_TEXT / "EASA" / f"{num}_Issue{rev}.txt",
    )


def _strings(obj: Any) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _strings(v)]
    if isinstance(obj, list):
        return [s for v in obj for s in _strings(v)]
    return []


@lru_cache(maxsize=256)
def load_text(path: Path) -> str:
    """Plain text of a .txt copy, or every string in a .json copy with HTML
    tags turned into line breaks. Empty when the file is missing or a PDF."""
    if not path.exists() or path.suffix not in (".txt", ".json"):
        return ""
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix == ".txt":
        return raw
    try:
        parts = _strings(json.loads(raw))
    except json.JSONDecodeError:
        parts = [raw]
    return "\n".join(html.unescape(TAG_RE.sub("\n", s)) for s in parts)


def norm_token(token: str) -> str:
    return token.translate(DASHES).strip(STRIP).casefold()


@dataclass(frozen=True)
class Tokens:
    words: list[str]  # normalised
    lines: list[int]  # line index of each word


@lru_cache(maxsize=256)
def _tokens(text: str) -> Tokens:
    words: list[str] = []
    lines: list[int] = []
    for n, line in enumerate(text.split("\n")):
        for tok in line.split():
            if w := norm_token(tok):
                words.append(w)
                lines.append(n)
    return Tokens(words, lines)


@dataclass(frozen=True)
class Match:
    first_line: int
    last_line: int
    end: int  # index of the first word after the match
    words: int  # how many words of the needle matched


def find(text: str, needle: str, start_line: int = 0) -> Match | None:
    """First occurrence of the whole needle at or after start_line."""
    toks = _tokens(text)
    want = [w for t in needle.split() if (w := norm_token(t))]
    if not want:
        return None
    k = len(want)
    for i in range(len(toks.words) - k + 1):
        if toks.lines[i] < start_line or toks.words[i] != want[0]:
            continue
        if toks.words[i : i + k] == want:
            return Match(toks.lines[i], toks.lines[i + k - 1], i + k, k)
    return None


def locate(text: str, needle: str, start_line: int = 0) -> Match | None:
    """`find`, falling back to the needle's first 12, 6 and 3 words."""
    if m := find(text, needle, start_line):
        return m
    words = needle.split()
    for n in (12, 6, 3):
        if len(words) > n and (m := find(text, " ".join(words[:n]), start_line)):
            return m
    return None


def page_of(text: str, line: int) -> int:
    """1-based page of a line, counting form feeds (pdftotext page breaks)."""
    return "\n".join(text.split("\n")[: line + 1]).count("\f") + 1


def excerpt(text: str, match: Match, radius: int = 4) -> dict[str, Any]:
    lines = text.split("\n")
    a = max(0, match.first_line - radius)
    b = min(len(lines), match.last_line + radius + 1)
    body = "\n".join(ln.replace("\f", "").rstrip() for ln in lines[a:b])
    return {
        "lines": f"{a + 1}-{b}",
        "page": page_of(text, match.first_line) if "\f" in text else None,
        "text": body[:2500],
    }


def slice_for(path: Path, needle: str, radius: int = 4) -> dict[str, Any] | None:
    """The source lines around needle in one local copy, or None."""
    text = load_text(path)
    if not text or not needle.strip():
        return None
    m = locate(text, needle)
    return None if m is None else {"file": path.as_posix(), **excerpt(text, m, radius)}
