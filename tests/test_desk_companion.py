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
    assert public == {"open_app", "open_hit", "set_size", "drag_start", "drag_to", "drag_end", "hide_companion"}


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

    monkeypatch.setattr(launcher, "_focus_window", lambda window: window.calls.append(("focus",)))
    main = FakeWindow()
    companion = launcher._attach_desk_companion(FakeWebview(), main, object())
    companion._dispatch = lambda name, fn: fn()  # noqa: SLF001
    assert companion.open_main("x = 1")
    assert main.calls == [("show",), ("focus",), ("js", "x = 1")]


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
    assert menu.index("else if (locked)") < menu.index('"Quick note"'), "locked is answered before the note and search rows"
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
