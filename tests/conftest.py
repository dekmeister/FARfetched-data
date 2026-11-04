from pathlib import Path

import pytest

from build import build

REPO_ROOT = Path(__file__).parent.parent


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def fixtures_dir() -> Path:
    return REPO_ROOT / "tests" / "fixtures"


@pytest.fixture(scope="session")
def real_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The real data/, built once per test session (the report sits beside it)."""
    data = REPO_ROOT / "data"
    if not (data / "documents").is_dir():
        pytest.skip("no checked-in data")
    out = tmp_path_factory.mktemp("real") / "cert_basis.sqlite"
    build(data, out)
    return out
