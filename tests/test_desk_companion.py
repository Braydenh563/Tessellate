"""The desktop companion (BACKLOG 16, INBOX 1464): `core/desk_companion.py`, its
page `frontend/desktop-companion.html`, and the launcher's hooks.

pywebview and pystray are faked: this sandbox has no desktop. What these tests
hold is the logic (when the window is made, shown and hidden, where it sits,
what the page may ask of it) and the security shape (the page is static, every
note route still needs the sign-in, a locked page draws no note). What they
cannot show, and nothing here does, is the real Windows window: transparency,
staying above the taskbar, and the position on a scaled screen.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from tessellate.core import desk_companion as dc

ROOT = Path(__file__).resolve().parent.parent
MAIN = (ROOT / "src" / "tessellate" / "__main__.py").read_text(encoding="utf-8")


class FakeWindow:
    def __init__(self, **options):
        self.options = options
        self.calls: list[tuple] = []

    def show(self):
        self.calls.append(("show",))

    def hide(self):
        self.calls.append(("hide",))

    def resize(self, w, h):
        self.calls.append(("resize", w, h))

    def move(self, x, y):
        self.calls.append(("move", x, y))

    def destroy(self):
        self.calls.append(("destroy",))

    def evaluate_js(self, script):
        self.calls.append(("js", script))


class FakeWebview:
    screens = [SimpleNamespace(width=1920, height=1080)]

    def __init__(self):
        self.made: list[FakeWindow] = []

    def create_window(self, title, **options):
        window = FakeWindow(title=title, **options)
        self.made.append(window)
        return window


@pytest.fixture()
def prefs(monkeypatch):
    """The notebook's preferences, as a dict the module reads and writes."""
    store: dict = {}
    config = SimpleNamespace(
        get_preference=lambda key, default=None: store.get(key, default),
        set_preference=lambda key, value: store.__setitem__(key, value),
    )
    monkeypatch.setattr(dc, "_config", lambda: config)
    monkeypatch.setattr(dc, "work_area", lambda: None)
    return store


@pytest.fixture()
def made(prefs):
    """A companion over a fake main window, `sync` run in line."""
    webview = FakeWebview()
    main = FakeWindow()
    opened: list[str] = []
    companion = dc.attach(
        webview, main, lambda script="": opened.append(script), lambda: "http://127.0.0.1:8000/desktop-companion.html",
        transparent=False,
    )
    companion._dispatch = lambda name, fn: fn()  # noqa: SLF001
    companion.opened = opened
    companion.webview = webview
    companion.main_window = main
    return companion


# --- the small pure parts -----------------------------------------------------


def test_a_size_the_page_asks_for_is_held_to_the_bounds():
    assert dc.clean_size(10, 10) == dc.MIN_SIZE
    assert dc.clean_size(5000, 5000) == dc.MAX_SIZE
    assert dc.clean_size(320, 376) == (320, 376)
    assert dc.clean_size("x", None) == dc.REST_SIZE


def test_a_saved_corner_off_the_screen_is_pulled_back_in():
    area = (0, 0, 1920, 1040)
    assert dc.clamp_corner((99999, 99999), (160, 160), area) == (1920, 1040)
    assert dc.clamp_corner((-50, -50), (160, 160), area) == (160, 160)
    assert dc.clamp_corner((900, 700), (160, 160), area) == (900, 700)


@pytest.mark.parametrize(
    "kind, ident",
    [("note", "7"), ("note", -1), ("note", True), ("nope", 3), ("note;alert(1)", 3), (None, 3), ("note", 1.5)],
)
def test_a_search_hit_the_page_names_is_checked_before_it_becomes_script(kind, ident):
    assert dc.hit_script(kind, ident) == ""


def test_a_real_hit_becomes_one_route_line():
    script = dc.hit_script("note", 12)
    assert 'routeHashFor("note", 12)' in script and "location.hash" in script


# --- when the window is made, shown and hidden ----------------------------------------


def test_nothing_is_made_while_the_preference_is_off(made, prefs):
    made.main_window.hide()
    assert made.webview.made == []


def test_it_is_made_once_and_follows_the_main_window_in_and_out_of_the_tray(made, prefs):
    prefs[dc.PREF] = True
    made.main_window.hide()  # the tray: the wrapped hide
    assert len(made.webview.made) == 1
    window = made.webview.made[0]
    assert window.calls == [("show",)]
    made.main_window.show()  # the app comes back
    assert window.calls[-1] == ("hide",)
    made.main_window.hide()
    assert len(made.webview.made) == 1 and window.calls[-1] == ("show",)


def test_the_window_is_frameless_on_top_hidden_and_given_the_page_only(made, prefs):
    prefs[dc.PREF] = True
    made.main_window.hide()
    options = made.webview.made[0].options
    assert options["frameless"] and options["on_top"] and options["hidden"]
    assert options["url"] == "http://127.0.0.1:8000/desktop-companion.html?card=1"
    assert isinstance(options["js_api"], dc.DeskApi)
    assert (options["width"], options["height"]) == dc.REST_SIZE


def test_a_see_through_window_gets_no_card_flag(prefs):
    webview, main = FakeWebview(), FakeWindow()
    companion = dc.attach(webview, main, lambda s="": None, lambda: "http://h/p.html", transparent=True)
    companion._dispatch = lambda name, fn: fn()  # noqa: SLF001
    prefs[dc.PREF] = True
    main.hide()
    assert webview.made[0].options["url"] == "http://h/p.html"
    assert webview.made[0].options["transparent"] is True


def test_turning_the_preference_off_hides_it_at_the_next_sync(made, prefs):
    prefs[dc.PREF] = True
    made.main_window.hide()
    prefs[dc.PREF] = False
    made.sync()
    assert made.webview.made[0].calls[-1] == ("hide",)


def test_a_failing_second_window_never_takes_the_app_down(made, prefs):
    prefs[dc.PREF] = True

    def boom(*a, **k):
        raise RuntimeError("no web view")

    made.webview.create_window = boom
    made.main_window.hide()  # must not raise
    assert made.window is None


def test_an_older_pywebview_without_the_newer_options_still_gets_a_window(made, prefs):
    prefs[dc.PREF] = True
    seen = []

    def old(title, **options):
        seen.append(set(options))
        if "hidden" in options:
            raise TypeError("unexpected keyword 'hidden'")
        return FakeWindow(**options)

    made.webview.create_window = old
    made.main_window.hide()
    assert made.window is not None and "hidden" in seen[0] and "hidden" not in seen[1]


def test_quitting_destroys_it_and_it_is_never_made_again(made, prefs):
    prefs[dc.PREF] = True
    made.main_window.hide()
    window = made.webview.made[0]
    dc.shutdown()
    assert window.calls[-1] == ("destroy",)
    made.main_window.hide()
    assert len(made.webview.made) == 1


def test_the_stop_before_exit_closes_it(made, prefs):
    assert "desk_companion.shutdown()" in MAIN.split("def _stop_background_work")[1].split("\ndef ")[0]


# --- where it sits ---------------------------------------------------------------------


def test_it_starts_bottom_right_above_the_taskbar(made, prefs, monkeypatch):
    monkeypatch.setattr(dc, "work_area", lambda: (0, 0, 1920, 1040))  # the taskbar is the last 40
    prefs[dc.PREF] = True
    made.main_window.hide()
    options = made.webview.made[0].options
    assert (options["x"] + options["width"], options["y"] + options["height"]) == (1920 - dc.MARGIN, 1040 - dc.MARGIN)


def test_a_dragged_place_is_remembered_and_used_next_time(made, prefs):
    prefs[dc.PREF] = True
    made.main_window.hide()
    api = made.webview.made[0].options["js_api"]
    start = api.drag_start()
    assert api.drag_to(start[0] - 300, start[1] - 200)
    assert api.drag_end()
    saved = prefs[dc.POS_PREF]
    assert saved == [1920 - dc.MARGIN - 300, 1080 - dc.MARGIN - 200]
    again = dc.attach(made.webview, FakeWindow(), lambda s="": None, lambda: "http://h/p.html", transparent=True)
    assert again.top_left() == (saved[0] - dc.REST_SIZE[0], saved[1] - dc.REST_SIZE[1])


def test_a_panel_grows_up_and_left_about_the_corner(made, prefs):
    prefs[dc.PREF] = True
    made.main_window.hide()
    window = made.webview.made[0]
    api = window.options["js_api"]
    corner = (made.corner[0], made.corner[1])
    assert api.set_size(320, 376) == [320, 376]
    assert window.calls[-2:] == [("resize", 320, 376), ("move", corner[0] - 320, corner[1] - 376)]
    api.set_size(*dc.REST_SIZE)
    assert window.calls[-1] == ("move", corner[0] - dc.REST_SIZE[0], corner[1] - dc.REST_SIZE[1])
    assert api.drag_end() and prefs[dc.POS_PREF] == list(corner)


def test_a_resize_beyond_the_bounds_is_held(made, prefs):
    prefs[dc.PREF] = True
    made.main_window.hide()
    assert made.webview.made[0].options["js_api"].set_size(9999, 1) == [dc.MAX_SIZE[0], dc.MIN_SIZE[1]]


# --- what the page may ask --------------------------------------------------------------


def test_open_tessellate_and_settings_and_a_hit_go_through_the_launcher(made, prefs):
    prefs[dc.PREF] = True
    made.main_window.hide()
    api = made.webview.made[0].options["js_api"]
    assert api.open_app() and api.open_app("settings") and api.open_hit("note", 4)
    assert made.opened[0] == ""
    assert "lock-overlay" in made.opened[1] and "openSettingsModal" in made.opened[1]
    assert 'routeHashFor("note", 4)' in made.opened[2]


def test_a_bad_hit_opens_the_app_with_no_script(made, prefs):
    prefs[dc.PREF] = True
    made.main_window.hide()
    api = made.webview.made[0].options["js_api"]
    assert api.open_hit("note", "1; evil()") and made.opened == [""]


def test_the_page_can_ask_for_nothing_else():
    public = {name for name in dir(dc.DeskApi) if not name.startswith("_")}
    assert public == {"open_app", "open_hit", "set_size", "drag_start", "drag_to", "drag_end", "hide_companion", "hide_panel", "panel_blur", "panel_kind", "panel_motion", "let_it_walk", "set_roam", "figure_do", "set_stay", "snooze", "companion_choices", "choose_companion"}


def test_hide_turns_the_preference_off_and_hides_the_window(made, prefs):
    prefs[dc.PREF] = True
    made.main_window.hide()
    assert made.webview.made[0].options["js_api"].hide_companion()
    assert prefs[dc.PREF] is False and made.webview.made[0].calls[-1] == ("hide",)


# --- the tray item -----------------------------------------------------------------------


def test_the_tray_item_is_a_tick_that_is_the_preference(made, prefs):
    class Item:
        def __init__(self, text, action, checked=None):
            self.text, self.action, self.checked = text, action, checked

    notes = []
    icon = SimpleNamespace(notify=lambda *a: notes.append(a))
    item = dc.tray_menu_item(SimpleNamespace(MenuItem=Item))
    assert item.text == "Show desktop companion" and item.checked(item) is False
    item.action(icon, item)
    assert prefs[dc.PREF] is True and item.checked(item) is True and notes
    made.main_window.hide()
    assert len(made.webview.made) == 1
    item.action(icon, item)  # off while the window is in the tray: it goes
    assert prefs[dc.PREF] is False and made.webview.made[0].calls[-1] == ("hide",)


# --- the launcher's hooks ----------------------------------------------------------------


def test_the_launcher_attaches_it_only_where_there_is_a_tray(monkeypatch, prefs):
    import tessellate.__main__ as launcher

    assert launcher._attach_desk_companion(FakeWebview(), FakeWindow(), None) is None
    main = FakeWindow()
    companion = launcher._attach_desk_companion(FakeWebview(), main, object())
    assert companion is not None and main.show.__name__ == "shown" and main.hide.__name__ == "hidden"


def test_open_tessellate_brings_the_window_forward_and_runs_the_checked_script(monkeypatch, prefs):
    import tessellate.__main__ as launcher

    def focus(window):
        launcher._reassert_window_state(window)  # restores only a minimised window (INBOX 1688)
        window.calls.append(("show",))
        window.calls.append(("focus",))

    monkeypatch.setattr(launcher, "_focus_window", focus)
    main = FakeWindow()
    main.restore = lambda: main.calls.append(("restore",))
    launcher._WINDOW_MEMORY[id(main)] = {"maximised": False, "minimised": True}
    companion = launcher._attach_desk_companion(FakeWebview(), main, object())
    companion._dispatch = lambda name, fn: fn()  # noqa: SLF001
    assert companion.open_main("x = 1")
    _wait(lambda: ("js", "x = 1") in main.calls)
    # Owner report 2026-11-04 (d): restored (it may be minimised), shown and focused
    # before the script; the script now runs on a worker, so it is last.
    assert main.calls == [("restore",), ("show",), ("focus",), ("js", "x = 1")]


def _wait(cond, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end and not cond():
        time.sleep(0.005)


def test_a_slow_app_window_script_never_holds_the_click(monkeypatch, prefs):
    """Owner report 2026-11-04 (d): Settings took 5 to 10 seconds. `evaluate_js` on a
    window that is not drawn yet can wait; the click must not."""
    import threading

    import tessellate.__main__ as launcher

    monkeypatch.setattr(launcher, "_focus_window", lambda window: None)
    gate = threading.Event()
    main = FakeWindow()
    main.evaluate_js = lambda script: gate.wait(5) and main.calls.append(("js", script))
    companion = launcher._attach_desk_companion(FakeWebview(), main, object())
    started = time.monotonic()
    assert dc.DeskApi(companion).open_app("settings")
    assert time.monotonic() - started < 0.5
    gate.set()
    _wait(lambda: any(call[0] == "js" for call in main.calls))


def test_the_page_opens_the_app_before_it_hides_the_panel():
    js = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
    leave = js.split("async function leave(action)")[1].split("\n  }\n")[0]
    assert leave.index("await action()") < leave.index('ask("hide_panel")')


def test_the_launcher_wires_the_attach_and_the_tray_item():
    assert "_attach_desk_companion(webview, window, tray_icon)" in MAIN.split("def _run_desktop")[1].split("\ndef ")[0]
    tray = MAIN.split("def _start_tray")[1].split("\ndef ")[0]
    assert "desk_companion.tray_menu_item(pystray)" in tray


# --- the setting -------------------------------------------------------------------------


def test_the_preference_is_off_by_default_and_saves(client):
    token = client.post("/auth/setup", json={"password": "testpassword123"}).json()["token"]
    headers = {"X-Auth-Token": token}
    before = client.get("/preferences", headers=headers).json()
    saved = client.put("/preferences", json={"desktop_companion": True}, headers=headers)
    after = client.get("/preferences", headers=headers).json()
    assert before["desktop_companion"] is False and saved.status_code == 200 and after["desktop_companion"] is True


def test_settings_has_the_switch_with_its_help_and_the_tray_names_it():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="pref-desktop-companion"' in html
    assert 'data-help-for="desktop-companion-help"' in html and 'id="desktop-companion-help"' in html
    controls = (ROOT / "frontend" / "js" / "settings-controls.js").read_text(encoding="utf-8")
    assert 'setPreference("desktop_companion", checked)' in controls
    assert "Show desktop companion" in (ROOT / "src" / "tessellate" / "core" / "desk_companion.py").read_text(encoding="utf-8")


# --- the page: static, and what it still needs a sign-in for -------------------------------


def test_the_page_is_served_stamped_and_carries_no_note(client):
    token = client.post("/auth/setup", json={"password": "testpassword123"}).json()["token"]
    made = client.post("/entries", json={"content": "the zebra ledger is hidden"}, headers={"X-Auth-Token": token})
    assert made.status_code in (200, 201)
    page = client.get("/desktop-companion.html")  # no token: the page is the same for everyone
    assert page.status_code == 200
    assert "zebra" not in page.text
    assert re.search(r'/js/desk-companion\.js\?v=[\w.-]+-[0-9a-f]{10}', page.text), "stamped by its own bytes"


def test_every_note_route_the_page_calls_refuses_a_locked_request(client):
    token = client.post("/auth/setup", json={"password": "testpassword123"}).json()["token"]
    client.post("/entries", json={"content": "the zebra ledger is hidden"}, headers={"X-Auth-Token": token})
    for method, path in (("get", "/preferences"), ("get", "/search?q=zebra"), ("post", "/entries")):
        refused = getattr(client, method)(path, **({"json": {"content": "x"}} if method == "post" else {}))
        assert refused.status_code == 401, path
        assert "zebra" not in refused.text
    stale = client.get("/search?q=zebra", headers={"X-Auth-Token": "not-a-token"})
    assert stale.status_code == 401


def test_the_page_has_no_inline_script_and_loads_its_files_in_order():
    html = (ROOT / "frontend" / "desktop-companion.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)", html), "the CSP refuses inline script"
    assert not re.search(r'\sstyle="', html), "the CSP refuses inline style"
    order = [html.index(f"/js/{name}.js") for name in ("prefs", "desk-env", "avatars", "atlas", "atlas-motion", "atlas-life", "standalone-undo", "desk-companion")]
    assert order == sorted(order)
    assert "desk-companion-lazy.css" in html


def test_the_main_apps_boot_never_loads_the_companions_page_files():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "desk-env" not in index and "desk-companion.js" not in index and "desk-companion-lazy" not in index


def test_the_page_decides_locked_from_the_notebook_and_fails_closed():
    js = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
    probe = js.split("async function probe()")[1].split("\n  // ---")[0]
    assert 'call("/preferences")' in probe and "locked = !response.ok" in probe
    assert "catch {\n      locked = true;" in probe, "an unreachable server reads as locked"
    menu = js.split("async function openMenu(kind)")[1].split("\n  //: Run")[0]
    # The menu moved to grouped rows (INBOX 1670, row C): the lock is still read before the note and search rows.
    assert menu.index("const capture = locked") < menu.index('"Quick note"'), "locked is answered before the note and search rows"
    assert js.count('openMenu("menu")') >= 3, "a 401 mid-panel returns to the menu"


def test_the_sweep_and_the_page_agree_on_the_window_sizes():
    js = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
    sweep = (ROOT / "scratchpad" / "ui-sweeps" / "deskcompanion.js").read_text(encoding="utf-8")
    sizes = lambda text: re.findall(r"(\w+): \[(\d+), (\d+)\]", text.split("SIZES = {")[1].split("}")[0])  # noqa: E731
    assert sizes(js) == sizes(sweep)
    mx = re.search(r"MAX_SIZE = \((\d+), (\d+)\)", (ROOT / "src/tessellate/core/desk_companion.py").read_text())
    assert all(int(w) <= int(mx[1]) and int(h) <= int(mx[2]) for _, w, h in sizes(js))


def test_the_window_is_see_through_to_the_root_element_and_a_hit_is_two_lines():
    """UX review 1031 items 2, 11 and 17: the app's page background is on `html`,
    so clearing the body left a pale rectangle; a snippet is clamped to two
    lines; the menu's rows take the arrow keys."""
    css = (ROOT / "frontend" / "css" / "desk-companion-lazy.css").read_text(encoding="utf-8")
    assert re.search(r"html:has\(> \.desk-page\) \{\s*background: none;", css)
    snippet = css[css.rindex(".desk-hit-title,") :][:300]
    assert "-webkit-line-clamp: 2" in snippet
    script = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
    assert '$("desk-menu").addEventListener("keydown"' in script and "ArrowDown" in script
    assert "said.startsWith(title.textContent)" in script


def test_the_settings_switch_with_a_question_mark_gives_way_to_it():
    """UX review 1031 item 1: at 390 the label did not shrink and the row was
    524.7px wide in a 263.6px one; the "?" fell to its own line."""
    css = (ROOT / "frontend" / "css" / "settings-controls-lazy.css").read_text(encoding="utf-8")
    rule = css[css.index("#settings-modal .help-head > .check-row {") :][:120]
    assert "flex: 1 1 0" in rule and "min-width: 0" in rule


# --- INBOX 1620: shown, on a monitor that is there, a tool window ---------------------


def test_a_corner_saved_on_a_gone_monitor_comes_back_to_the_primary():
    primary, second = (0, 0, 1920, 1040), (1920, 0, 3840, 1040)
    assert dc.pick_area((3000, 500), [primary, second]) == second
    assert dc.pick_area((1920, 500), [primary, second]) == primary  # the shared edge is the left one's
    assert dc.pick_area((3000, 500), [primary]) == primary  # the second monitor was unplugged
    assert dc.pick_area((-4000, 9000), [primary, second]) == primary
    assert dc.pick_area((10, 10), []) is None
    corner = dc.clamp_corner((3000, 500), dc.REST_SIZE, dc.pick_area((3000, 500), [primary]))
    assert corner == (1920, 500)


def test_a_saved_place_is_clamped_to_the_monitor_that_is_there(made, prefs, monkeypatch):
    monkeypatch.setattr(dc, "monitor_areas", lambda: [(0, 0, 1920, 1040)])
    prefs[dc.POS_PREF] = [5000, 900]
    assert made._home() == (1920, 900)  # noqa: SLF001
    prefs[dc.POS_PREF] = [-900, -900]
    assert made._home() == dc.REST_SIZE  # noqa: SLF001


def test_a_window_dragged_to_the_second_monitor_stays_there(made, prefs, monkeypatch):
    monkeypatch.setattr(dc, "monitor_areas", lambda: [(0, 0, 1920, 1040), (1920, 0, 3840, 1040)])
    prefs[dc.PREF] = True
    made.main_window.hide()
    assert made.move_to(2500, 300)
    assert made.corner == (2500 + made.size[0], 300 + made.size[1])


def test_the_window_is_a_tool_window_that_never_takes_focus():
    style = dc.companion_ex_style(dc.WS_EX_APPWINDOW | 0x100)
    assert style & dc.WS_EX_TOOLWINDOW and style & dc.WS_EX_NOACTIVATE
    assert not style & dc.WS_EX_APPWINDOW  # an app window would bring the taskbar button back
    assert style & 0x100  # what was there is kept


def test_it_is_made_frameless_on_top_and_unfocused(made, prefs):
    prefs[dc.PREF] = True
    made.main_window.hide()
    options = made.webview.made[0].options
    assert options["frameless"] and options["on_top"] and options["focus"] is False


def test_each_show_reasserts_the_stacking_where_it_can(made, prefs, monkeypatch):
    raised = []
    monkeypatch.setattr(dc, "raise_on_desktop", lambda window, rect=None: raised.append(window))
    prefs[dc.PREF] = True
    made.main_window.hide()
    made.main_window.show()
    made.main_window.hide()
    assert len(raised) == 2  # once per show, never on a hide


def test_raise_on_desktop_does_nothing_off_windows():
    assert dc.raise_on_desktop(object()) is False


def test_the_installers_make_no_desktop_shortcut_unless_asked():
    """INBOX 1620: the owner wants the app reachable from the Start menu and the
    tray only. The Inno installer's desktop shortcut is an unticked task, and the
    MSI has none; a Desktop link only comes from `start --shortcut` or Settings."""
    iss = (ROOT / "packaging" / "windows" / "installer.iss").read_text(encoding="utf-8")
    task = next(line for line in iss.splitlines() if line.startswith('Name: "desktopicon"'))
    assert "unchecked" in task
    assert [line for line in iss.splitlines() if "{autodesktop}" in line and "Tasks: desktopicon" not in line] == []
    wxs = (ROOT / "packaging" / "windows" / "installer.wxs").read_text(encoding="utf-8")
    assert "DesktopFolder" not in wxs


def test_the_companions_menu_has_the_desktop_row_only_in_the_desktop_app():
    menu = (ROOT / "frontend" / "js" / "companion-menu.js").read_text(encoding="utf-8")
    assert "if (isDesktopShell === true)" in menu
    assert "Hide from desktop" in menu and "Show on desktop" in menu
    assert 'setPreference("desktop_companion", !onDesktop)' in menu


def test_raise_on_desktop_never_rebuilds_the_form_or_waits_on_its_thread():
    """The owner, 2026-11-04: the companion "not responding" on the taskbar and
    the tray icon frozen. `ShowInTaskbar` set from the worker re-made the form's
    handle on a thread with no message loop; every later show waited on it while
    holding the lock the tray's toggle needs."""
    import inspect

    body = inspect.getsource(dc.raise_on_desktop)
    code = "\n".join(line for line in body.split("\n") if not line.strip().startswith(("#", '"')))
    assert "ShowInTaskbar =" not in code
    assert "ShowWindowAsync" in code and "user32.ShowWindow(" not in code
    assert dc.SWP_FLAGS & 0x4000  # SWP_ASYNCWINDOWPOS


def test_a_stuck_show_never_holds_the_tray_or_the_way_out(made, prefs, monkeypatch):
    import threading

    monkeypatch.setattr(dc, "LOCK_WAIT", 0.05)
    prefs[dc.PREF] = True
    held, let_go = threading.Event(), threading.Event()

    def stuck():  # a show that never comes back, holding the lock
        with dc._lock:  # noqa: SLF001
            held.set()
            let_go.wait(5)

    holder = threading.Thread(target=stuck)
    holder.start()
    held.wait(5)
    try:
        made.main_window.hide()  # sync gives up rather than waiting for good
        assert made.webview.made == []
        made.close()  # and the way out does not hang either
        assert made.closing
    finally:
        let_go.set()
        holder.join(5)


def test_the_tray_toggle_runs_the_show_on_a_worker(made, prefs):
    ran = []
    made._dispatch = lambda name, fn: ran.append(name)  # noqa: SLF001

    class Item:
        def __init__(self, text, action, checked=None):
            self.text, self.action, self.checked = text, action, checked

    item = dc.tray_menu_item(SimpleNamespace(MenuItem=Item))
    item.action(SimpleNamespace(notify=lambda *a: None), item)
    assert ran == ["desk-companion"]


class _Event:
    """pywebview's window event, as far as the companion uses it."""

    def __init__(self):
        self.handlers = []

    def __iadd__(self, fn):
        self.handlers.append(fn)
        return self

    def fire(self, window):
        for fn in self.handlers:
            fn(window)


def test_a_minimised_window_brings_the_companion_and_a_restore_sends_it(prefs):
    """The owner, 2026-11-04: "can the desktop companion show even when I
    still have the application open but minimised?"."""
    webview, main = FakeWebview(), FakeWindow()
    main.events = SimpleNamespace(minimized=_Event(), restored=_Event(), maximized=_Event())
    companion = dc.attach(webview, main, lambda script="": None, lambda: "http://127.0.0.1:8000/desktop-companion.html", transparent=False)
    companion._dispatch = lambda name, fn: fn()  # noqa: SLF001
    prefs[dc.PREF] = True
    main.events.minimized.fire(main)
    assert companion.shown and len(webview.made) == 1
    main.events.restored.fire(main)
    assert not companion.shown
    main.events.minimized.fire(main)
    main.events.maximized.fire(main)
    assert not companion.shown
    dc.shutdown()


def test_a_window_without_those_events_still_follows_the_tray(made, prefs):
    prefs[dc.PREF] = True
    made.main_window.hide()
    assert made.shown


# --- INBOX 1633: the window was placed past the screen's edge -------------------
# The owner's log: "window made at (2436, 1340), size (112, 152)", "shown",
# "raised above the desktop: True", and nothing on screen. Win32 work areas are
# physical pixels; pywebview's create_window and move take logical pixels and
# multiply them by the display's scale, so at 150% the corner landed at 3654.


def test_a_work_area_is_turned_into_the_logical_pixels_pywebview_takes():
    assert dc.to_logical((0, 0, 2560, 1552), 144) == (0, 0, 1707, 1035)
    assert dc.to_logical((0, 0, 2560, 1552), 120) == (0, 0, 2048, 1242)
    assert dc.to_logical((0, 0, 1920, 1040), 96) == (0, 0, 1920, 1040)
    # A second monitor to the right keeps its place in the same units.
    assert dc.to_logical((2560, 0, 4480, 1040), 96) == (2560, 0, 4480, 1040)


def test_a_dpi_that_is_missing_or_not_sane_is_no_scaling():
    for dpi in (None, "x", 0, 10_000):
        assert dc.to_logical((0, 0, 1920, 1040), dpi) == (0, 0, 1920, 1040)


def test_at_150_percent_the_window_lands_on_the_screen_once_pywebview_scales_it(monkeypatch):
    scale = 1.5
    physical = (0, 0, 2560, 1552)
    monkeypatch.setattr(dc, "monitor_areas", lambda: [dc.to_logical(physical, 96 * scale)])
    monkeypatch.setattr(dc, "_pref", lambda key, default: default)
    companion = dc.DeskCompanion(object(), object(), lambda s="": None, lambda: "http://x")
    companion.corner = companion._home()
    x, y = companion.top_left()
    w, h = companion.size
    # What pywebview's WinForms backend does with them (Location = x * scale).
    right, bottom = (x + w) * scale, (y + h) * scale
    assert 0 <= x * scale and right <= physical[2] and bottom <= physical[3]


def test_the_place_after_a_show_is_set_in_physical_pixels():
    """The owner, 2026-11-04, 200%: a card twice its size running off the right
    edge, its left edge right. WinForms scales the form's size again on its first
    show; the companion's own SetWindowPos after every show sets size and place."""
    assert dc.physical_rect((1156, 588, 112, 152), 192) == (2312, 1176, 224, 304)
    assert dc.physical_rect((10, 20, 112, 152), 96) == (10, 20, 112, 152)
    assert dc.physical_rect((10, 20, 112, 152), None) == (10, 20, 112, 152)
    assert not dc.SWP_PLACE & 0x0003  # neither NOSIZE nor NOMOVE
    assert dc.SWP_PLACE & 0x4000 and dc.SWP_PLACE & 0x0010  # async, no activate


def test_every_show_hands_its_rect_to_the_raise(made, prefs, monkeypatch):
    seen = []
    monkeypatch.setattr(dc, "raise_on_desktop", lambda window, rect=None: seen.append(rect) or True)
    prefs[dc.PREF] = True
    made.main_window.hide()
    assert seen and seen[-1] == (*made.top_left(), *made.size)


def test_the_window_asks_for_a_minimum_no_wider_than_its_resting_size(made, prefs):
    # pywebview's default minimum is 200 by 100: a 112-wide window grew to a
    # card with the character in its right half (INBOX 1633, the owner at 200%).
    prefs[dc.PREF] = True
    made.main_window.hide()
    options = made.webview.made[0].options if hasattr(made.webview.made[0], "options") else vars(made.webview.made[0])
    low = options["min_size"]
    assert low[0] <= dc.REST_SIZE[0] and low[1] <= dc.REST_SIZE[1]


def test_the_place_read_back_never_raises_where_there_is_no_win32():
    # A log line only: off Windows (no ctypes.windll) it logs at debug and returns.
    assert dc._log_placed(1, (0, 0, 224, 304), 192) is None


def test_a_first_show_that_did_not_hold_is_placed_once_more(monkeypatch):
    # INBOX 1650: the first show landed as a 232 by 233 square for a 224 by
    # 304 ask, and only a drag set it right. The show's read-back places it
    # again, once; a drag's read-back (no `again`) only logs.
    import ctypes

    calls = []

    class User32:
        def GetWindowRect(self, handle, ref):
            box = ref._obj
            box.left, box.top, box.right, box.bottom = 880, 512, 880 + 232, 512 + 233

        def SetWindowPos(self, *args):
            calls.append(args)

    monkeypatch.setattr(ctypes, "windll", type("W", (), {"user32": User32()})(), raising=False)
    monkeypatch.setattr(dc, "_read_back", lambda *args, **kw: calls.append(("timer", args)))
    want = (880, 512, 224, 304)
    dc._log_placed(7, want, 192, True)
    places = [c for c in calls if c[0] != "timer"]
    assert places and places[0][:6] == (7, 0, *want)
    assert ("timer", (7, want, 192)) in calls
    calls.clear()
    dc._log_placed(7, want, 192)
    assert calls == []


def test_hiding_it_from_its_own_menu_refreshes_the_tray_tick(made, prefs):
    # INBOX 1642: pystray builds the Windows menu once, so the tick stayed on
    # after Hide until the tray was told to rebuild it.
    refreshed = []
    made.on_change = lambda: refreshed.append(dc.enabled())
    prefs[dc.PREF] = True
    made.main_window.hide()
    made.webview.made[0].options["js_api"].hide_companion()
    assert refreshed[-1] is False
    calls = len(refreshed)
    made.sync()
    assert len(refreshed) == calls  # no rebuild when nothing changed


def test_a_panel_resize_goes_to_the_window_in_physical_pixels_where_it_can(made, prefs, monkeypatch):
    # INBOX 1633: pywebview's resize scaled the size again on a 200% display.
    placed = []
    monkeypatch.setattr(dc, "place_on_screen", lambda window, rect: placed.append(rect) or True)
    prefs[dc.PREF] = True
    made.main_window.hide()
    window = made.webview.made[0]
    made.resize(208, 312)
    assert placed and placed[-1][2:] == (208, 312)
    assert dc.place_on_screen(window, (0, 0, 1, 1)) is True  # patched
    monkeypatch.undo()
    assert dc.place_on_screen(window, (0, 0, 1, 1)) is False  # off Windows


def test_the_overlay_page_reports_a_blur_and_asks_for_the_first_menu():
    """Both ends of the bridge: Python's `panel_blur` and `panel_kind` are only
    worth having if the page calls them."""
    js = (ROOT / "frontend" / "js" / "desk-companion.js").read_text(encoding="utf-8")
    assert 'ask("panel_kind")' in js and 'ask("panel_blur")' in js
    assert 'addEventListener("blur"' in js and "if (!focused) return;" in js
    assert "pywebviewready" in js


def test_the_panels_near_edge_sits_within_the_gap_of_the_figures_drawn_box_on_both_sides() -> None:
    """INBOX 1663: placed from the figure's drawn alpha box (runner.drawn_rect), in physical pixels."""
    from tessellate.core.desk_companion import PANEL_GAP, panel_placement
    from tessellate.core.overlay import sprites as sp

    spr = sp.SpriteSet("feminine")
    area = (0, 0, 3000, 1600)
    for dpi in (96, 144, 192):
        gap = round(PANEL_GAP * dpi / 96)
        for flip in (False, True):
            f = spr.frame("stand", dpi, flip)
            for wx in (1500, 20):  # roomy, then against the left monitor edge (panel flips right)
                pet = (wx + f.box[0], 900 + f.box[1], f.box[2] - f.box[0], f.box[3] - f.box[1])
                (px, _py, pw, _ph), _ = panel_placement(pet, (360, 420), [(area, dpi)], dpi)
                near = pet[0] - (px + pw) if px + pw <= pet[0] else px - (pet[0] + pet[2])
                assert near == gap, (dpi, flip, wx, near)
