"""L-documents-51: Emmet in `.scss`, `.sass` and `.less`.

A stylesheet dialect opens as the CSS type (`filetypes.ALIASES`), whose syntax
is the one Emmet is mounted on, so the shorthands expand there with no table of
their own. SCSS nests, so the abbreviation is read inside a rule within a rule.
Stylus has no type here; Emmet's `sass` and `stylus` forms (no braces) would
need one each, which is why `.sass` still gets CSS punctuation.
"""

from __future__ import annotations

import pytest

from tessellate.core import filetypes
from tests.test_code_completion import node, one


@pytest.mark.parametrize("name", ["theme.scss", "theme.sass", "theme.less", ".LESS", "less"])
def test_a_stylesheet_dialect_opens_as_css(name):
    assert filetypes.normalise(name) == "css"
    assert filetypes.require(name) == "css"


def test_stylus_is_not_aliased_to_a_type_it_would_be_wrong_in():
    assert filetypes.normalise("a.styl") == filetypes.DEFAULT_FILE_TYPE


@node
@pytest.mark.parametrize("line", ["  df", "    &:hover { m10", "  .a { .b { bgc"])
def test_a_nested_rule_expands_emmet_shorthands(line):
    found = one("at", line, len(line), "css", False)
    assert found and found[0] in {"df", "m10", "bgc"}
    preview = one("expand", found[0], "css")[0]
    assert preview.endswith(";")
