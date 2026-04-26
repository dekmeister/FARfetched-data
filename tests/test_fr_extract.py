"""Tests for faa_fr_lookup.extract_section_block.

Uses minimal hand-written HTML fixtures that represent the key FR HTML patterns.
Real FR HTML is more complex, but these cover the core extraction logic.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))

from faa_fr_lookup import extract_section_block  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures: representative FR HTML patterns

# Pattern 1: Modern FR HTML — section header as bold span inside paragraph
_HTML_MODERN = """
<html><body>
<div class="rule-body">
<p>§ 25.561 General.</p>
<p>(a) The occupant of each seat must be protected as follows...</p>
<p>(b) The structure must be designed to give each occupant every
reasonable chance of escaping serious injury in a minor crash landing.</p>
<p>§ 25.562 Emergency landing dynamic conditions.</p>
<p>(a) The seat and restraint system in each...</p>
</div>
</body></html>
"""

# Pattern 2: Older FR HTML — section header embedded in running text
_HTML_OLDER = """
<html><body>
<p>PART 25--[AMENDED]</p>
<p>1. The authority citation for part 25 continues to read as follows:</p>
<p>Authority: 49 U.S.C. 40113, 44701-44702, 44704.</p>
<p>2. Section 25.803 is amended by revising paragraph (a) to read:</p>
<p>§ 25.803 Emergency evacuation.</p>
<p>(a) Each crew and passenger area must have emergency means to allow
rapid evacuation in crash landings, with the landing gear extended as well as
with the landing gear retracted, considering the possibility of the
airplane being on fire.</p>
<p>§ 25.807 Emergency exits.</p>
<p>(a) Types. For the purpose of this part, the types of exits are...</p>
</body></html>
"""

# Pattern 3: Multi-section rule — multiple sections; target is not the first
_HTML_MULTI = """
<html><body>
<p>§ 25.1 Applicability.</p>
<p>This part prescribes airworthiness standards for the issue of type
certificates, and changes to those certificates, for transport category
airplanes.</p>
<p>§ 25.3 Special provisions for ETOPS type design approvals.</p>
<p>(a) Applicability. This section applies to ETOPS type design approvals
for two-engine turbine-powered airplanes.</p>
<p>§ 25.5 Incorporations by reference.</p>
<p>(a) The material listed in this section...</p>
</body></html>
"""

# Pattern 4: Section not present in the page
_HTML_ABSENT = """
<html><body>
<p>§ 25.1 Applicability.</p>
<p>Some content here.</p>
</body></html>
"""


class TestExtractSectionBlock:
    def test_modern_html_extracts_target_section(self) -> None:
        text = extract_section_block(_HTML_MODERN, "25", "561")
        assert "§ 25.561" in text or "General" in text
        assert "protected" in text
        # Should NOT bleed into the next section
        assert "562" not in text

    def test_older_html_extracts_target_section(self) -> None:
        text = extract_section_block(_HTML_OLDER, "25", "803")
        assert "evacuation" in text.lower()
        # Should not include content from § 25.807
        assert "807" not in text

    def test_multi_section_first(self) -> None:
        text = extract_section_block(_HTML_MULTI, "25", "1")
        assert "Applicability" in text or "prescribes" in text
        # Should stop before § 25.3
        assert "ETOPS" not in text

    def test_multi_section_middle(self) -> None:
        text = extract_section_block(_HTML_MULTI, "25", "3")
        assert "ETOPS" in text
        # Should stop before § 25.5
        assert "Incorporations" not in text

    def test_absent_section_returns_empty(self) -> None:
        text = extract_section_block(_HTML_ABSENT, "25", "999")
        assert text == ""

    def test_strips_html_tags(self) -> None:
        html = "<p>§ 25.1 <b>Title.</b></p><p>Body text here.</p>"
        text = extract_section_block(html, "25", "1")
        assert "<p>" not in text
        assert "<b>" not in text

    def test_collapses_whitespace(self) -> None:
        html = "<p>§ 25.1 Applicability.</p>\n\n<p>  Some   spaced  text.  </p>"
        text = extract_section_block(html, "25", "1")
        assert "  " not in text  # no doubled spaces


class TestExtractSectionBlockEdgeCases:
    def test_section_with_subsection_number(self) -> None:
        # § 25.1 should not match § 25.10 or § 25.100
        html = (
            "<p>§ 25.100 Some section.</p>"
            "<p>Content of 25.100.</p>"
            "<p>§ 25.101 Next.</p>"
        )
        text = extract_section_block(html, "25", "100")
        assert "Some section" in text
        assert "101" not in text

    def test_no_trailing_section_caps_at_5000_chars(self) -> None:
        # When there's no subsequent section header, output is capped at 5000 chars
        body = "word " * 2000  # well over 5000 chars
        html = f"<p>§ 25.1 Applicability.</p><p>{body}</p>"
        text = extract_section_block(html, "25", "1")
        # The raw block (before tag stripping) is capped at 5000; stripped text shorter
        assert len(text) < len(body)
