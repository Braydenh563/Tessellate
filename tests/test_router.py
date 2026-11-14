"""The hash router (WORLD_CLASS_PLAN 22.1 item 1, frontend/js/router.js).

Every view has an address: `#/notes/12`, `#/chat/45`, `#/docs/7`,
`#/library/images`, `#/settings/appearance`. The two pure halves, a history
entry to its hash and a hash back to the entry, are run in node here and must
be inverses; the wiring (navigation.js's stack mirrored into the browser's,
popstate driving Back and Forward, the boot restoring the address, the title
naming the view) is checked by reading the source, and measured by
`scratchpad/ui-sweeps/router.js` in a browser.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._app_js import app_js_text

ROOT = Path(__file__).resolve().parent.parent
ROUTER = ROOT / "frontend" / "js" / "router.js"


def _functions(*names: str) -> str:
    source = ROUTER.read_text(encoding="utf-8")
    parts = []
    for name in names:
        match = re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M)
        assert match, f"{name} is gone from router.js"
        parts.append(match.group(0))
    consts = re.findall(r"^const ROUTE_\w+ = .*?;$", source, re.S | re.M)
    return "\n".join(consts + parts)


def _run(expr: str):
    script = _functions("routeHash", "routeEntry") + f"\nprocess.stdout.write(JSON.stringify({expr}));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


CASES = [
    ({"tab": "dashboard", "section": None}, "#/dashboard"),
    ({"tab": "notes", "section": None}, "#/notes"),
    ({"tab": "notes", "section": "browse"}, "#/notes"),
    ({"tab": "notes", "section": "capture"}, "#/notes/capture"),
    ({"tab": "notes", "section": "writing-room"}, "#/notes/writing-room"),
    ({"tab": "notes", "section": "note:12"}, "#/notes/12"),
    ({"tab": "chat", "section": None}, "#/chat"),
    ({"tab": "chat", "section": "conv:45"}, "#/chat/45"),
    ({"tab": "documents", "section": "doc:7"}, "#/docs/7"),
    ({"tab": "library", "section": "library-view-media:images"}, "#/library/images"),
    ({"tab": "library", "section": "library-view-media:files"}, "#/library/files"),
    ({"tab": "library", "section": "library-view-docs"}, "#/library/documents"),
    ({"tab": "library", "section": "library-view-documents"}, "#/library/all"),
    ({"tab": "library", "section": "board:3"}, "#/library/board/3"),
    ({"tab": "graph", "section": None}, "#/graph"),
    ({"tab": "graph", "section": "focus:9"}, "#/graph/focus/9"),
    ({"tab": "timeline", "section": None}, "#/timeline"),
    ({"tab": "reminders", "section": None}, "#/reminders"),
    ({"tab": "settings", "section": "appearance"}, "#/settings/appearance"),
]


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize(("entry", "hash_"), CASES)
def test_an_entry_has_an_address_and_the_address_is_the_entry(entry, hash_):
    assert _run(f"routeHash({json.dumps(entry)})") == hash_
    back = _run(f"routeEntry({json.dumps(hash_)})")
    expected = dict(entry)
    if expected["tab"] == "notes" and expected["section"] == "browse":
        expected["section"] = None
    assert back == expected


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize("hash_", ["", "#", "#heading-2", "#/nowhere", "#/notes/abc", "#/chat/1x", "#/docs"])
def test_an_address_that_is_not_a_view_is_ignored_or_lands_on_its_tab(hash_):
    got = _run(f"routeEntry({json.dumps(hash_)})")
    if hash_ == "#/docs":
        assert got == {"tab": "documents", "section": None}
    else:
        # An in-page anchor (a document's heading link) is not a route: the
        # router must leave it alone rather than navigate somewhere.
        assert got is None


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_an_overlay_with_an_entry_shows_its_own_address():
    # B43: the manual and Statistics wrote `#/dashboard` while open (Playwright,
    # 2026-11-10). They were routes added by the lazy router-overlays.js, which
    # is not in yet when a pasted `#/Manual` is read at load (Sh1 P17), so the
    # routes are in router.js now: the intent (the address names the overlay)
    # is the same, it holds in the first seconds too.
    lazy = (ROOT / "frontend" / "js" / "router-overlays.js").read_text(encoding="utf-8")
    assert "Object.assign(ROUTE_TABS" not in lazy
    for tab in ("Manual", "Statistics"):
        assert _run(f'routeHash({{tab: "{tab}", section: null}})') == f"#/{tab}"


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_pasted_manual_or_statistics_address_is_an_entry_in_either_case():
    for hash_, tab in (("#/Manual", "Manual"), ("#/manual", "Manual"), ("#/Statistics", "Statistics"), ("#/statistics", "Statistics")):
        assert _run(f'routeEntry("{hash_}")') == {"tab": tab, "section": None}
    assert _run('routeEntry("#/manual/x")') is None
    source = ROUTER.read_text(encoding="utf-8")
    restore = source[source.index("async function routerRestore(") :]
    assert 'ensureModule("quickNote").then(() => openHistoryEntry(entry))' in restore[: restore.index("\n}\n")]


def test_the_stack_is_mirrored_into_the_browsers_history():
    app = app_js_text()
    record = app[app.index("function recordTabVisit(") :]
    record = record[: record.index("\n}\n")]
    assert "routerOnVisit(" in record, "a visit no longer reaches the address bar"
    step = app[app.index("function stepTabHistory(") :]
    step = step[: step.index("\n}\n")]
    assert "routerGo(" in step, "the in-app Back and Forward no longer go through the browser's history"
    router = ROUTER.read_text(encoding="utf-8")
    assert 'addEventListener("popstate"' in router
    assert "pushState" in router and "replaceState" in router


def test_reload_restores_the_view_and_the_title_names_it():
    app = app_js_text()
    assert "routerRestore()" in app, "the boot no longer opens the view in the address"
    router = ROUTER.read_text(encoding="utf-8")
    assert "setTitleView(" in router
    status = (ROOT / "frontend" / "js" / "status.js").read_text(encoding="utf-8")
    assert "function setTitleView(" in status


def test_opening_a_note_gives_it_an_address():
    body = app_js_text()
    flash = body[body.index("function flashEntry(") :]
    flash = flash[: flash.index("\n}\n")]
    assert 'recordTabVisit("notes", `note:${id}`' in flash


# "Copy app link" (INBOX 483): one address table for entry-to-hash and
# kind-and-id-to-hash, one helper that copies the full address.
OBJECT_CASES = [
    ("note", 12, "#/notes/12"),
    ("chat", 45, "#/chat/45"),
    ("document", 7, "#/docs/7"),
    # A diagram is a document file (L-documents-10): its tray row and Copy app link open the Documents page.
    ("diagram", 7, "#/docs/7"),
    ("board", 3, "#/library/board/3"),
    ("map", 3, "#/library/board/3"),
    ("graph", 9, "#/graph/focus/9"),
]


def _run_for(expr: str):
    script = _functions("routeHash", "routeEntry", "routeHashFor") + f"\nprocess.stdout.write(JSON.stringify({expr}));"
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize(("kind", "ident", "hash_"), OBJECT_CASES)
def test_an_object_has_an_address_the_router_opens(kind, ident, hash_):
    assert _run_for(f"routeHashFor({json.dumps(kind)}, {ident})") == hash_
    # The address a menu copies must be one a pasted link opens.
    assert _run_for(f"routeEntry(routeHashFor({json.dumps(kind)}, {ident}))") is not None


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize(("kind", "ident"), [("nowhere", 1), ("note", "abc"), ("note", ""), ("chat", "1/2"), ("note", None)])
def test_a_kind_or_id_with_no_address_gives_none(kind, ident):
    assert _run_for(f"routeHashFor({json.dumps(kind)}, {json.dumps(ident)})") == ""


def test_the_copy_helper_writes_the_full_address_through_the_shared_clipboard_helper():
    router = ROUTER.read_text(encoding="utf-8")
    helper = router[router.index("async function copyObjectAddress(") :]
    helper = helper[: helper.index("\n}\n")]
    assert "location.origin + location.pathname + hash" in helper
    assert "copyToClipboard(" in helper and "toast(" in helper



#: Where "Copy app link" must be offered: the file, and what it calls (a built
#: menu calls `appLinkMenuItem(kind, id)`, a markup menu's button its own handler).
COPY_LINK_SITES = [
    ("entry-menu.js", 'appLinkMenuItem("note", entry.id)'),
    ("library.js", "appLinkMenuItem(kind, id)"),
    ("boards-gallery.js", 'appLinkMenuItem(board.type === "map" ? "map" : "board", board.id)'),
    ("documents.js", 'appLinkMenuItem("document", doc.id)'),
    ("documents.js", 'copyObjectAddress("document", currentDoc.id)'),
    ("sheets-selects.js", 'appLinkMenuItem("chat", conversation.id)'),
    ("chat.js", 'appLinkMenuItem("chat", () => chatConv.id)'),
    ("whiteboard.js", 'copyObjectAddress(wbIsMap() ? "map" : "board", id)'),
]


@pytest.mark.parametrize(("name", "needle"), COPY_LINK_SITES)
def test_every_object_menu_offers_copy_app_link(name, needle):
    source = (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")
    assert needle in source, f"{name} lost its Copy app link row"


def test_the_document_and_board_menus_have_the_row_in_markup():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for ident in ("doc-copy-link", "wb-copy-link"):
        assert f'id="{ident}"' in html, f"{ident} is gone from index.html"
        assert "Copy app link" in html


def test_the_app_link_row_is_one_recipe_and_the_wiki_row_is_named_apart():
    router = ROUTER.read_text(encoding="utf-8")
    assert '"ph:link Copy app link"' in router
    # Where a wiki link is copied the two rows must be told apart (INBOX 483).
    for name in ("entry-menu.js", "library.js"):
        source = (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")
        assert "Copy wiki link" in source and "Copy [[link]]" not in source


# An app address pasted into a note or document opens in this window
# (INBOX 483): only this origin and page, only a route the router opens.
def _run_address(expr: str):
    script = (
        'globalThis.location = {origin: "http://127.0.0.1:8877", pathname: "/", href: "http://127.0.0.1:8877/"};\n'
        + _functions("routeHash", "routeEntry", "appAddressHash")
        + f"\nprocess.stdout.write(JSON.stringify({expr}));"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://127.0.0.1:8877/#/notes/12", "#/notes/12"),
        ("http://127.0.0.1:8877/#/library/board/3", "#/library/board/3"),
        ("http://127.0.0.1:8877/#/docs/7", "#/docs/7"),
        ("http://127.0.0.1:8877/#/chat/45", "#/chat/45"),
        ("http://127.0.0.1:8877/#/settings/appearance", "#/settings/appearance"),
        ("#/notes/12", "#/notes/12"),
        ("http://example.com/#/notes/12", ""),
        ("http://127.0.0.1:8878/#/notes/12", ""),
        ("https://127.0.0.1:8877/#/notes/12", ""),
        ("http://127.0.0.1:8877/other/#/notes/12", ""),
        ("http://127.0.0.1:8877/#/nowhere", ""),
        ("http://127.0.0.1:8877/#/notes/abc", ""),
        ("http://127.0.0.1:8877/", ""),
        ("#intro", ""),
        ("javascript:alert(1)", ""),
        ("data:text/html,<b>x</b>", ""),
        ("/media/x.pdf", ""),
        ("", ""),
    ],
)
def test_only_this_apps_own_routes_are_app_addresses(url, expected):
    assert _run_address(f"appAddressHash({json.dumps(url)})") == expected


def test_a_pasted_app_address_opens_in_this_window_and_other_links_keep_their_behaviour():
    notes = (ROOT / "frontend" / "js" / "notes-list.js").read_text(encoding="utf-8")
    body = notes[notes.index("function appendInlineRun(") :]
    body = body[: body.index("\nfunction ", 1)]
    # Still through the scheme allow-list, whatever address it is.
    assert "a.href = safeHref(linkTarget)" in body
    assert "const linkTarget = appAddressHash(linkUrl) || linkUrl;" in body
    # A new tab only for a web link that is not this app's own address.
    assert "if (linkTarget === linkUrl && /^https?:\\/\\//i.test(linkUrl))" in body
    #: documents-embeds.js is one closure (doc23-1102): the function ends at an indented brace.
    docs = (ROOT / "frontend" / "js" / "documents-embeds.js").read_text(encoding="utf-8")
    opener = docs[docs.index("function docOpenLink(") :]
    opener = opener[: opener.index("\n  }\n")]
    assert "appAddressHash(clean)" in opener and "window.open(clean" in opener
