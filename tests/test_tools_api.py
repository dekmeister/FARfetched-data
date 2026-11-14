"""The names tools/ imports from certbuild (PROC-11).

tools/ is a separate git repo, so a rename here passes this repo's own tests
and breaks the tools quietly. This test fails here instead. When tools/
starts using another name, add it below (and to certbuild.text.__all__ if it
is part of the text format).
"""

import ast
from pathlib import Path

import pytest

import certbuild.text

REPO_ROOT = Path(__file__).parent.parent

TEXT_API = {
    "FORMULA_MARK",
    "SECTION_HEADING_RE",
    "TABLE_CLOSE",
    "TABLE_OPEN",
    "TABLE_ROW_SEP",
    "Paragraph",
    "TableCell",
    "TextFormatError",
    "flatten_text",
    "heading_section",
    "inline_error",
    "label_values",
    "parse_paragraphs",
    "parse_table_row",
    "plain_text",
    "strip_inline",
    "table_width",
}
OTHER_API = {
    "certbuild.keys": {"sort_key"},
    "certbuild.pipeline": {"build"},
}


def test_text_api_is_declared() -> None:
    assert TEXT_API <= set(certbuild.text.__all__)
    for name in certbuild.text.__all__:
        assert hasattr(certbuild.text, name), name


@pytest.mark.parametrize("module,names", sorted(OTHER_API.items()))
def test_other_api_exists(module: str, names: set[str]) -> None:
    mod = __import__(module, fromlist=sorted(names))
    for name in names:
        assert hasattr(mod, name), f"{module}.{name}"


def test_tools_import_only_declared_names() -> None:
    """When tools/ is checked out, every certbuild name it imports is one of
    the above, so this list stays the real contract."""
    tools = REPO_ROOT / "tools"
    if not tools.is_dir():
        pytest.skip("tools/ not checked out")
    allowed = {"certbuild.text": TEXT_API} | OTHER_API
    undeclared: list[str] = []
    for path in sorted(tools.rglob("*.py")):
        if "out" in path.relative_to(tools).parts[:1]:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                ("certbuild", "build")
            ):
                for a in node.names:
                    if a.name not in allowed.get(node.module or "", set()):
                        rel = path.relative_to(REPO_ROOT)
                        undeclared.append(f"{rel}: {node.module}.{a.name}")
    assert undeclared == []
