"""Build errors, and the one rule for reporting them.

Collect within a stage, raise between stages. A stage (schema validation,
paths and text layout, provision inserts, number clashes, aircraft and
references, dates, foreign keys) returns its faults as `list[str]`, or a
result plus that list. certbuild/pipeline.py raises one `BuildError` with
all of them before the next stage starts, so a run lists every fault of the
first failing stage instead of stopping at the first.

Raise at once only where carrying on would add nonsense: inside one file
(its later checks depend on the earlier ones), and on a sqlite integrity
error (the DB state is then unknown).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class BuildError(Exception):
    """The build failed; `errors` lists every fault found, one per line."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("\n".join(self.errors))


@dataclass(frozen=True)
class ValidationError:
    path: Path
    message: str
    location: str

    def __str__(self) -> str:
        where = f" at {self.location}" if self.location else ""
        return f"{self.path}:{where} {self.message}"
