"""UX audit 2026-10-18, measured with scratchpad/ui-sweeps (contrast.js in true
dark at 390 and 1440, then a Playwright probe of the Settings jump list).

These read the source because the suite cannot see the DOM; the measurements
are in docs/roadmap/agent-remaining/uxfix1-1018.md.
"""

import re

from tests._app_js import app_js_text
from tests._css_paths import CSS_DIR, css_text


def test_phone_settings_drops_the_heading_the_jump_list_already_shows():
    js = app_js_text()
    assert "function echoSettingsPaneTitle" in js
    assert "jump-echo" in js
    css = css_text()
    block = re.search(r"#settings-modal h3\.jump-echo\s*\{([^}]*)\}", css)
    assert block and "display: none" in block.group(1)


def test_suggested_tag_take_has_a_target_min_hit_area():
    css = css_text()
    rule = re.search(r"\.suggested-tag-take::before\s*\{([^}]*)\}", css)
    assert rule and "var(--target-min)" in rule.group(1)


def test_offline_note_action_is_ink_on_the_phone():
    text = (CSS_DIR / "offline-split-lazy.css").read_text(encoding="utf-8")
    phone = text[text.index("@media (max-width: 599.98px)") :]
    action = re.search(r"\.ai-offline-split > \.split-button-main \{([^}]*)\}", phone)
    assert action and "color: var(--ink)" in action.group(1)
