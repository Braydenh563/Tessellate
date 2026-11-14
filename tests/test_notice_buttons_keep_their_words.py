"""Source text: ui-modernisation 60. A button in a `.notice` row shrank below
its own label: the optional-package notice on Notes, Capture at 390 (the
Install button, `min-width: 44px` set so the flex minimum is not the label's)
was 59.2px wide with 25.6px of padding for a 34.0px word, and fontmatrix.js
(errors.js text fit) reported the word 1 to 2px past its padding. The notice
recipe holds its buttons at their own width and lets the words wrap."""

import re

from tests._css_paths import css_text


def test_a_notice_keeps_its_buttons_at_their_label_width():
    css = css_text()
    rule = re.search(r"\n\.notice > button \{(.*?)\n\}", css, re.S)
    assert rule, ".notice > button has no rule"
    assert "flex: none;" in rule.group(1)
