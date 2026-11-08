from pathlib import Path

import pytest

from certbuild.pipeline import build

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


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Every test that uses the real build is slow."""
    for item in items:
        if "real_db" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.slow)
