"""A button says its keyboard shortcut, from the one table (INBOX 701).

The owner, 2026-10-06: "if something has a keyboard shortcut, should they be
added to the tooltips??" Yes: `DEFAULT_SHORTCUTS` (settings-wiring.js) is the
only place a chord is written. A button whose action has a binding carries
`data-shortcut="<action>"` (stamped by `stampShortcutTitles`) or is painted
with `shortcutTitle(...)` / `shortcut: "<action>"` (the status bar), so a
rebound key changes its tooltip; on a Mac it is written with the Command
symbol. These tests are the rule: an action with a button that carries
neither fails, and so does a chord typed next to a `data-shortcut`.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
ENTRY = re.compile(r'^\s*(\w+):\s*\{\s*keys:\s*"([^"]+)"', re.MULTILINE)

#: Actions that have no button of their own, each with why. A new action must
#: either get a button that carries its chord or a line here; a line here for
#: an action that has since grown a button fails (it would be stale).
NO_BUTTON = {
    "search": "the search field itself is the control; the key only focuses it",
    "help": "opened from Settings and the palette row, which prints its chord from the table",
    "quickNote": "a palette and Settings row that prints its chord (`chord:` in settings-panes.js)",
    "pasteNote": "a palette and Settings row that prints its chord (`chord:` in settings-panes.js)",
    "todaysNote": "a palette and Settings row that prints its chord (`chord:` in settings-panes.js)",
    "recordMeeting": "a palette and Settings row that prints its chord (`chord:` in settings-panes.js)",
    "toggleCompanion": "a palette and Settings row that prints its chord (`chord:` in settings-panes.js)",
    "whiteboard": "boards are a view inside the Library; no button opens the tab by itself",
    "renameRow": "acts on the list item that has focus (its Rename item); a row's menu already shows Rename",
    "selectionActions": "the selection's own menu opens on the same key; it has no fixed button",
    "editorMenu": "typing / opens the same menu; the placeholder on every editor says so",
    "inlineAi": "a row of the editor's / menu, which prints its own key",
}


def _table() -> dict[str, str]:
    source = app_js_text()
    start = source.index("const DEFAULT_SHORTCUTS")
    end = source.index("\n};", start)
    return {name: keys for name, keys in ENTRY.findall(source[start:end])}


def _js_files() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend" / "js").glob("*.js"))}


def _html_actions() -> set[str]:
    return set(re.findall(r'data-shortcut="(\w+)"', HTML))


def _painted_actions() -> set[str]:
    found: set[str] = set()
    for name, text in _js_files().items():
        if name == "prefs.js":
            continue
        found |= set(re.findall(r'\bshortcut: [^\n]*?"(\w+)"', text))
        found |= set(re.findall(r'shortcutTitle\([^\n]*?,\s*"(\w+)"\)', text))
        #: The status bar's Undo and Redo, painted with their chords by
        #: `paintUndoDoor(button, "undo" | "redo", ...)` (Brief 76).
        found |= set(re.findall(r'paintUndoDoor\(\w+, "(\w+)"', text))
    return found


def test_the_table_was_found():
    assert len(_table()) > 20
    assert _html_actions(), "no data-shortcut in index.html: the stamp has nothing to do"


def test_every_data_shortcut_names_a_bound_action():
    unknown = sorted(_html_actions() - set(_table()))
    assert not unknown, f"data-shortcut names an action the table does not have: {unknown}"
    painted = sorted(_painted_actions() - set(_table()))
    assert not painted, f"a painted tooltip names an action the table does not have: {painted}"


def test_every_bound_action_with_a_button_carries_its_chord():
    covered = _html_actions() | _painted_actions()
    missing = sorted(set(_table()) - covered - set(NO_BUTTON))
    assert not missing, (
        "These actions are bound but no button shows the chord. Put "
        'data-shortcut="<action>" on the button (or paint it with shortcutTitle), '
        "or add the action to NO_BUTTON with the reason it has none:\n  " + "\n  ".join(missing)
    )


def test_no_button_list_has_no_stale_entries():
    covered = _html_actions() | _painted_actions()
    stale = sorted(set(NO_BUTTON) & covered)
    assert not stale, f"NO_BUTTON lists an action that now has a button: {stale}"
    gone = sorted(set(NO_BUTTON) - set(_table()))
    assert not gone, f"NO_BUTTON lists an action the table no longer has: {gone}"


def test_a_data_shortcut_element_does_not_also_write_a_chord():
    """The stamp appends the chord; one typed in the markup would say it twice,
    or say the old key after a rebind."""
    offenders = []
    for tag in re.findall(r'<[^>]*data-shortcut="[^"]+"[^>]*>', HTML):
        for attr in re.findall(r'(?:title|aria-label)="([^"]*)"', tag):
            if re.search(r"\b(?:Ctrl|Alt|Shift|Cmd)\+", attr):
                offenders.append(attr)
    assert not offenders, f"chords written beside data-shortcut: {offenders}"


def test_no_tooltip_builds_a_chord_from_the_table_by_hand():
    """`(${shortcuts.undo.keys})` shows the key unformatted, and on a Mac says
    Ctrl. The one way to put a chord in a title is `shortcutTitle`."""
    offenders = []
    for name, text in _js_files().items():
        for match in re.finditer(r"\(\$\{[^}]*\bshortcuts\b[^}]*\}\)", text):
            offenders.append(f"{name}: {match.group(0)}")
    assert not offenders, "\n".join(offenders)


def test_the_status_bar_titles_come_from_the_table():
    status = _js_files()["status.js"]
    assert "STATUS_META_KEY.startsWith" not in status, "a hand-built modifier in a tooltip"
    for action in ("palette", "askAgent", "findAnything", "askAtlas", "undo", "redo"):
        assert f'"{action}"' in status, action
    assert '"navigateBack"' in _js_files()["navigation.js"]
    assert '"navigateForward"' in _js_files()["navigation.js"]


def test_stamping_runs_again_when_a_binding_changes():
    wiring = _js_files()["settings-wiring.js"]
    for fn in ("saveShortcutOverrides", "resetShortcuts"):
        body = wiring[wiring.index(f"function {fn}(") :][:700]
        assert "restampShortcutHints()" in body, fn


# --- the platform's spelling (run through node when it is there) -------------------


def _run_hints(platform: str, calls: str) -> list:
    source = (ROOT / "frontend" / "js" / "prefs.js").read_text(encoding="utf-8")
    block = source[source.index("const SHORTCUT_MAC") :]
    script = (
        f"Object.defineProperty(globalThis, 'navigator', {{ value: {{ platform: {json.dumps(platform)} }}, configurable: true }});\n"
        + block
        + "\nSHORTCUT_SOURCE.table = () => ({ newNote: { keys: 'Ctrl+Shift+N' }, rel: { keys: 'Ctrl+Alt+R' },"
        " back: { keys: 'Alt+ArrowLeft' }, settings: { keys: 'Ctrl+,' }, search: { keys: '/' } });\n"
        + f"console.log(JSON.stringify({calls}));"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_chords_read_the_platform_way():
    calls = (
        "[chordLabel('Ctrl+B'), chordLabel('Ctrl+Shift+N'), chordLabel('Ctrl+Alt+R'),"
        " chordLabel('Alt+ArrowLeft'), chordLabel('Ctrl+,'), chordLabel('/'),"
        " shortcutTitle('New note', 'newNote'), shortcutTitle('Reload', 'rel'),"
        " shortcutTitle('Nothing bound', 'nope'), shortcutHint('settings')]"
    )
    assert _run_hints("Win32", calls) == [
        "Ctrl+B", "Ctrl+Shift+N", "Ctrl+Alt+R", "Alt+ArrowLeft", "Ctrl+,", "/",
        "New note (Ctrl+Shift+N)", "Reload (Ctrl+Alt+R)", "Nothing bound", "Ctrl+,",
    ]
    assert _run_hints("MacIntel", calls) == [
        "⌘B", "⇧⌘N", "⌥⌘R", "⌥Left", "⌘,", "/",
        "New note (⇧⌘N)", "Reload (⌥⌘R)", "Nothing bound", "⌘,",
    ]
