"""A Settings pane's main action sits in its bar (design-rows-1005, the
leftover of INBOX 599: "the Settings pane docks hold only title, index and
'?'; a pane's own primary action (New persona, Add your own) still lives in
its fold"). Personas, Skills and Templates each make new things, and the
form that makes one was the last group of a long pane, folded on Skills. Now
the pane's dock carries "+ New ..." (a ghost: the form's own Add stays the
page's one filled button), which opens the form, cancels an edit in progress
and puts the cursor in its name field. `scratchpad/ui-sweeps/paneacts.js`
presses each one at 1440 and 390, light and dark.
"""

import re
from pathlib import Path
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
#: The listener lives with the Settings window's others (settings-controls.js, lazy).
JS = unwrapped((ROOT / "frontend" / "js" / "settings-controls.js").read_text(encoding="utf-8"))

PANES = {
    "personas": ("persona-name", None, "New persona"),
    "skills": ("skill-name", "skill-cancel", "New skill"),
    "templates": ("template-name", "template-cancel", "New template"),
}


def _section(name: str) -> str:
    start = HTML.index(f'id="settings-{name}"')
    return HTML[start : HTML.index("</section>", start)]


def test_each_making_pane_has_its_new_action_in_its_dock():
    for pane, (field, cancel, word) in PANES.items():
        section = _section(pane)
        dock = section[section.index('class="dock settings-pane-title"') :]
        dock = dock[: dock.index('class="dock-actions"') + 600]
        button = re.search(r'<button[^>]*data-opens="' + field + r'"[^>]*>(.*?)</button>', dock, re.S)
        assert button, f"{pane}: no New action in the dock"
        tag = button.group(0)
        assert 'class="ghost small' in tag, f"{pane}: the dock action is a ghost; the form's Add is the filled one"
        assert word in button.group(1)
        if cancel:
            assert f'data-cancel="{cancel}"' in tag
        assert f'id="{field}"' in section


def test_one_listener_opens_the_form():
    assert 'closest("[data-opens]")' in JS
    body = JS[JS.index('closest("[data-opens]")') :][:1400]
    assert "fold.open = true" in body and "focus(" in body


def test_on_a_phone_new_is_its_plus_on_the_titles_row():
    css = (ROOT / "frontend" / "css" / "01-forms-settings.css").read_text(encoding="utf-8")
    block = css[css.index("**On a phone the pane's New sits on the title's row**") :]
    block = block[: block.index("\n}\n")]
    assert "@media (max-width: 599.98px)" in block
    # The jump links that took a row of their own under both (`order: 3`) are
    # the sidebar's second level now (INBOX 622), so the dock is one row.
    assert "order: 2;" in block and "settings-index" not in block
    hidden = block[block.index(".settings-pane-new > .pane-new-word {") :]
    assert "clip-path: inset(50%);" in hidden and "display: none" not in hidden
