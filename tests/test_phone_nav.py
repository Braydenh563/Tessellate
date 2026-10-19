"""The phone's bottom bar: where each column goes and in what order (INBOX 1314).

The owner, 2026-10-19: "the bottom nav bar just doesnt make sense with how it
works and is layed out". Measured at 390x844 before the rework
(`scratchpad/ui-sweeps/phonemore.js` plus a probe): More drew as the *first*
column (x=0) because a pre-dock rule still gave `#tab-bar` `order: 3` below
600; Dashboard, the app's home and one of Simple mode's four, sat behind More
while Graph held a column; More's sheet mixed three pages with five tools in
one undivided list; and the header's own menu was also called "More".

These pin the shape the rework settled on, so none of it drifts back.
"""

from __future__ import annotations

import re

from tests._app_js import JS_DIR, app_js_files, app_js_text, frontend_text
from tests._css_paths import CSS_DIR

PHONE_BAND = "max-width: 599.98px"


def _phone_blocks(css: str) -> list[str]:
    """The bodies of every `@media (max-width: 599.98px)` block in one file."""
    out = []
    for match in re.finditer(r"@media[^{]*" + re.escape(PHONE_BAND) + r"[^{]*\{", css):
        depth, i = 1, match.end()
        while depth and i < len(css):
            depth += {"{": 1, "}": -1}.get(css[i], 0)
            i += 1
        out.append(css[match.end() : i])
    return out


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def test_the_bar_holds_dashboard_notes_chat_library_and_more():
    """Simple mode's four (Settings, General) are the four columns; the rest
    are rows of More."""
    hidden = set()
    for path in CSS_DIR.glob("*.css"):
        for block in _phone_blocks(_strip_comments(path.read_text(encoding="utf-8"))):
            for rule in re.finditer(r"([^{}]+)\{([^{}]*)\}", block):
                if re.search(r"display:\s*none", rule.group(2)):
                    hidden |= set(re.findall(r"#tab-bar #tab-btn-(\w+)", rule.group(1)))
    assert hidden == {"graph", "timeline", "reminders"}, hidden
    app = app_js_text()
    tabs = re.search(r"const PHONE_MORE_TABS = \[([^\]]*)\]", app).group(1)
    assert re.findall(r'"(\w+)"', tabs) == ["graph", "timeline", "reminders"]


def test_more_is_the_last_column_not_the_first():
    """No phone-band rule may reorder the strip inside the dock: the strip's
    `order: 3` from the days it lived in the header put More at x=0."""
    for path in CSS_DIR.glob("*.css"):
        for block in _phone_blocks(_strip_comments(path.read_text(encoding="utf-8"))):
            for rule in re.finditer(r"([^{}]+)\{([^{}]*)\}", block):
                selectors = [s.strip() for s in rule.group(1).split(",")]
                if any(s in ("#tab-bar", "#phone-tab-dock > #tab-bar") for s in selectors):
                    assert not re.search(r"(^|;|\s)order\s*:", rule.group(2)), (
                        f"{path.name}: {rule.group(1).strip()} reorders the phone strip"
                    )


def test_more_sheet_is_lazy_and_grouped():
    """The sheet's builder is a lazy file (the boot JS cap), pages come first,
    and a hairline separates them from the tools."""
    lazy = frontend_text("phone-more.js")
    assert "function openPhoneMoreSheet" in lazy
    boot = "\n".join(path.read_text(encoding="utf-8") for path in app_js_files())
    assert "function openPhoneMoreSheet" not in boot
    loader = (JS_DIR / "lazy-entries.js").read_text(encoding="utf-8")
    assert re.search(r'phoneMore: \["/js/phone-more\.js"\]', loader)
    assert re.search(r'phoneMore: \["openPhoneMoreSheet"\]', loader)
    body = lazy.split("function openPhoneMoreSheet", 1)[1]
    assert body.index("PHONE_MORE_TABS") < body.index('"Ask the agent"')
    assert '"menu-sep"' in body and 'role", "separator"' in body


def test_the_header_menu_is_not_a_second_more():
    """Two buttons named More on one phone screen are two answers to one
    question; the header's is the app menu."""
    app = app_js_text()
    head = app.split("function initPhoneHeaderMore", 1)[1].split("\nfunction ", 1)[0]
    label = re.search(r'\],\s*(?://[^\n]*\n\s*)*"([^"]+)"\s*\);\s*menu\.id = "header-more"', head)
    assert label and label.group(1) != "More", label and label.group(1)


def test_pressing_the_tab_you_are_on_goes_to_the_top():
    """A phone's convention: the active tab pressed again scrolls its page to
    the top."""
    shell = (JS_DIR / "phone-shell.js").read_text(encoding="utf-8")
    assert "function tabPageScroller" in shell
    click = shell.split('for (const button of document.querySelectorAll("#tab-bar button"))', 1)[1][:1500]
    assert "tabPageScroller" in click and "scrollTo" in click
