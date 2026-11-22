"""Every Settings row's name is one element in one type (INBOX 854: "filing
style text style is different to the other mini headers?? I think??").

`Categories` and `Tags` were `<span>` in `.setting-label` (600 weight at
`--text-lg`, `.setting-label > span`); `Filing style` was a `<label>`, which
that rule does not reach, so it drew in the body face. Of 49 row heads in the
page, 48 were spans and that one was the exception. A row whose control needs a
name takes `aria-labelledby` to its span instead.
"""

from __future__ import annotations

import re
from tests._app_js import index_html_text

INDEX = index_html_text()


def test_every_setting_label_starts_with_a_span():
    heads = re.findall(r'<div class="setting-label[^"]*">\s*<(\w+)', INDEX)
    assert len(heads) > 40, "the pattern should find the settings rows"
    odd = [tag for tag in heads if tag != "span"]
    assert not odd, f"a settings row's name is a span, found {odd}"


def test_filing_style_is_named_for_its_select_by_reference():
    assert 'id="pref-filing-style-name"' in INDEX
    assert re.search(r'<select id="pref-filing-style"[^>]*aria-labelledby="pref-filing-style-name"', INDEX)
