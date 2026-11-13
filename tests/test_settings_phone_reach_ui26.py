"""Source text: L-ui-modernisation-26, "Check every Settings page (and other
pages) is reachable on a narrow phone view" (IDEAS.md, retired: "check at 360
wide"). Measured at 360 and 320 touch: #settings-jump lists all 21 sections
and each opens on screen; only Shortcuts overflowed, 8px and 48px, because
its rows could not wrap. The rule that lets them is read here."""
import re

from tests._css_paths import css_text


def test_shortcut_rows_wrap_their_keys():
    css = re.sub(r"/\*.*?\*/", "", css_text(), flags=re.S)
    row = re.search(r"\.shortcut-list li \{\s*display: flex;([^}]*)\}", css)
    assert row and "flex-wrap: wrap" in row.group(1)
    label = re.search(r"\.shortcut-list li>span \{([^}]*)\}", css)
    assert label and "flex: 1 1 10rem" in label.group(1)
