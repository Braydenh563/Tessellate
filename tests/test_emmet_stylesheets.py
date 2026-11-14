"""L-documents-51: Emmet in `.scss`, `.sass` and `.less`.

A stylesheet dialect opens as the CSS type (`filetypes.ALIASES`), whose syntax
is the one Emmet is mounted on, so the shorthands expand there with no table of
their own. SCSS nests, so the abbreviation is read inside a rule within a rule.
Indented Sass and Stylus are types of their own (L-documents-76), because
Emmet's `sass` and `stylus` forms have no braces or semicolons. No highlighter
for either is bundled, so they edit as plain text with Emmet.
"""

from __future__ import annotations

import pytest

from tessellate.core import filetypes
from tests.test_code_completion import node, one


@pytest.mark.parametrize("name", ["theme.scss", "theme.less", ".LESS", "less"])
def test_a_stylesheet_dialect_opens_as_css(name):
    assert filetypes.normalise(name) == "css"
    assert filetypes.require(name) == "css"


@pytest.mark.parametrize(("name", "ext"), [("a.sass", "sass"), ("a.styl", "styl"), ("stylus", "styl"), (".SASS", "sass")])
def test_sass_and_stylus_are_types_of_their_own(name, ext):
    assert filetypes.require(name) == ext
    assert filetypes.get(ext).line_comment == "//"


@node
@pytest.mark.parametrize(
    ("syntax", "expected"),
    [("sass", "display: flex"), ("stylus", "display flex")],
)
def test_emmet_writes_the_indented_forms_without_braces_or_semicolons(syntax, expected):
    line = "  df"
    found = one("at", line, len(line), syntax, False)
    assert found and found[0] == "df"
    assert one("expand", "df", syntax)[0] == expected
    assert one("expand", "m10", syntax)[0] == ("margin: 10px" if syntax == "sass" else "margin 10px")
    assert one("at", "  hello", 7, syntax, False) is None


@node
@pytest.mark.parametrize("line", ["  df", "    &:hover { m10", "  .a { .b { bgc"])
def test_a_nested_rule_expands_emmet_shorthands(line):
    found = one("at", line, len(line), "css", False)
    assert found and found[0] in {"df", "m10", "bgc"}
    preview = one("expand", found[0], "css")[0]
    assert preview.endswith(";")
