"""Source text: the bell's panel is fetched soon after start-up with the other
small modules, so its first press opens at once on a slow link (L409).

Measured at 390 with `notifications.js` held 3s by the network: before, the
first press drew nothing for 3s (the panel shut, the bell already
`aria-expanded`); after, the panel is open 100ms after the press.
"""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def test_notifications_is_in_the_post_boot_warm_list():
    warm = re.search(r"setTimeout\(\(\) => \[([^\]]*)\]\.forEach\(ensureModule\), 3000\)", app_js_text())
    assert warm and '"notifications"' in warm.group(1)
