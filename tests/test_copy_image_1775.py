"""Copy image from every picture (INBOX 1775).

The owner: "I want to be able to right click and copy images from both the
library, the chat, staged files, the lightbox and ect". One helper
(`copyImage`, attachment-actions.js) puts the picture on the clipboard as a
PNG; a right-click (or a hold on a phone, or the menu key) on any picture
offers it; the Library tile's menu, the attachment card's menu and the
viewer's bar, menu and Ctrl+C reach the same helper. The helper runs here in a
`vm` with a fake clipboard (real clipboard permission is the owner's to check).

The same screenshot showed the viewer's filmstrip over the details card's last
line and the zoom bar on the status bar: both are a fixed foot that did not
know the scroll area or the status bar.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
CSS = ROOT / "frontend" / "css"
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const [file, scenario] = process.argv.slice(1);
const log = [];
const listeners = {};
const toasts = [];
class FakeElement {
  constructor(tag, props = {}) { this.tag = tag; Object.assign(this, props); }
  closest(sel) { return this.matches ? this.matches(sel) : null; }
  getBoundingClientRect() { return { left: 10, top: 20, right: 210, bottom: 120, width: 200, height: 100 }; }
}
const ctx = {
  console, Math, Number, Object, Set, Map, JSON, Date, Array, String, RegExp, Promise, Boolean, URL, Error, Blob,
  location: { href: "http://x.test/app", origin: "http://x.test" },
  toasts,
  toast: (message, kind) => toasts.push([message, kind]),
  mediaSrc: (url) => url,
  api: async (path) => { log.push(["api", path]); return { blob: async () => ({ type: scenario.includes("jpeg") ? "image/jpeg" : "image/png", size: 3 }) }; },
  saveFile: async () => {},
  copyToClipboard: async (text) => { log.push(["copyToClipboard", text]); return !scenario.includes("linkfails"); },
  openMenuAtPoint: (items, label, x, y) => log.push(["menu", items.map((i) => i.label), label, x, y]),
  wireLongPress: (target, fn, opts) => log.push(["longpress", opts.selector]),
  document: {
    addEventListener: (type, fn) => { (listeners[type] = listeners[type] || []).push(fn); },
    createElement: () => ({ width: 0, height: 0, getContext: () => ({ drawImage: () => log.push("draw") }), toBlob: (cb) => cb({ type: "image/png", size: 9 }) }),
  },
  Image: class { set src(v) { this._src = v; } async decode() { log.push(["decode", this._src]); } get naturalWidth() { return 40; } get naturalHeight() { return 30; } },
  Element: FakeElement,
  fetch: async () => { log.push("fetch"); throw new Error("blocked by CSP"); },
  window: null,
};
ctx.window = ctx;
ctx.URL = Object.assign(URL, { createObjectURL: () => "blob:made", revokeObjectURL: () => {} });
if (!scenario.includes("noclipboard")) {
  ctx.ClipboardItem = class { constructor(parts) { this.parts = parts; } };
  ctx.navigator = { clipboard: { write: async (items) => { const parts = items[0].parts; log.push(["write", Object.keys(parts), (await parts["image/png"]).type]); } } };
} else {
  ctx.navigator = {};
}
ctx.getSelection = () => ({ toString: () => (scenario.includes("selection") ? "some words" : "") });
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(file, "utf8"), ctx);
(async () => {
  if (scenario.startsWith("copy")) {
    const spec = scenario.includes("blobsrc") ? { src: "blob:http://x.test/abc", name: "s.png" } : { url: "/media/a.jpg", name: "a.jpg" };
    await ctx.attachmentAction("copy-image", spec);
  } else if (scenario.startsWith("menu")) {
    const img = new FakeElement("img", { currentSrc: "http://x.test/media/a.png", src: "http://x.test/media/a.png", alt: "a", naturalWidth: 40 });
    img.matches = (sel) => (sel.startsWith("input") ? null : sel.includes("img") && !sel.includes("figure") ? img : null);
    img.closest = (sel) => (/^input/.test(sel) || sel.includes("button, [tabindex]") ? null : /^img/.test(sel) || sel === "img" ? img : null);
    let prevented = false;
    const event = { target: img, clientX: 50, clientY: 60, defaultPrevented: scenario.includes("claimed"), preventDefault: () => { prevented = true; } };
    for (const fn of listeners.contextmenu || []) fn(event);
    log.push(["prevented", prevented]);
  }
  console.log(JSON.stringify({ log, toasts }));
})();
"""


def _run(scenario: str) -> dict:
    out = subprocess.run(
        ["node", "-e", HARNESS, str(JS / "attachment-actions.js"), scenario],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return json.loads(out.stdout)


@needs_node
def test_copy_writes_a_png_clipboard_item_from_the_apps_own_route():
    got = _run("copy")
    assert ["api", "/media/a.jpg"] in got["log"]
    assert ["write", ["image/png"], "image/png"] in got["log"]
    assert got["toasts"] == [["Image copied.", None]] or got["toasts"][0][0] == "Image copied."


@needs_node
def test_copy_draws_a_non_png_onto_a_canvas_first():
    got = _run("copy-jpeg")
    assert "draw" in got["log"]
    assert ["write", ["image/png"], "image/png"] in got["log"]


@needs_node
def test_a_staged_blob_is_drawn_not_fetched_because_the_csp_refuses_a_blob_fetch():
    got = _run("copy-blobsrc")
    assert "fetch" not in got["log"]
    assert ["decode", "blob:http://x.test/abc"] in got["log"]
    assert ["write", ["image/png"], "image/png"] in got["log"]


@needs_node
def test_without_clipboard_image_support_the_link_is_copied_and_the_toast_says_so():
    got = _run("copy-noclipboard")
    assert ["copyToClipboard", "http://x.test/media/a.jpg"] in got["log"]
    assert "link" in got["toasts"][-1][0]
    assert got["toasts"][-1][1] is None


@needs_node
def test_when_nothing_can_be_copied_the_toast_is_an_info_not_a_fault():
    got = _run("copy-noclipboard-linkfails")
    assert got["toasts"][-1] == ["This picture cannot be copied.", "info"]


@needs_node
def test_a_staged_picture_without_clipboard_support_does_not_copy_a_blob_link():
    got = _run("copy-blobsrc-noclipboard")
    assert not any(row[0] == "copyToClipboard" for row in got["log"] if isinstance(row, list))
    assert got["toasts"][-1][0] == "This picture cannot be copied."


@needs_node
def test_right_click_on_a_picture_offers_copy_image_and_save_image():
    got = _run("menu")
    menu = next(row for row in got["log"] if row[0] == "menu")
    assert [label.split(" ", 1)[1] for label in menu[1]] == ["Copy image", "Save image"]
    assert menu[2] == "Picture actions"
    assert ["prevented", True] in got["log"]


@needs_node
def test_a_menu_a_row_has_already_claimed_is_left_alone():
    got = _run("menu-claimed")
    assert not any(row[0] == "menu" for row in got["log"])
    assert ["prevented", False] in got["log"]


@needs_node
def test_a_text_selection_keeps_the_browsers_menu():
    got = _run("menu-selection")
    assert not any(row[0] == "menu" for row in got["log"])


@needs_node
def test_a_hold_on_a_phone_is_wired_to_the_same_picture_menu():
    got = _run("menu")
    hold = next(row for row in got["log"] if row[0] == "longpress")
    assert "img" in hold[1] and ".lightbox-stage" in hold[1] and ".msg-attachment-image" in hold[1]


def test_every_surface_reaches_the_one_helper():
    actions = (JS / "attachment-actions.js").read_text(encoding="utf-8")
    assert '"copy-image": (spec) => copyImage(imageSource(spec))' in actions
    cards = (JS / "notes-list.js").read_text(encoding="utf-8")
    assert 'add("copy-image", "ph:image Copy image"' in cards
    library = (JS / "library.js").read_text(encoding="utf-8")
    assert 'attachmentAction("copy-image"' in library
    lightbox = (JS / "lightbox-view.js").read_text(encoding="utf-8")
    assert lightbox.count('attachmentAction("copy-image"') == 1
    assert 'label: "ph:image Copy image"' in lightbox
    assert "copyPictureNow();" in lightbox
    #: The viewer's Ctrl+C is the picture's only while nothing is selected or typed in.
    assert re.search(r'e\.key !== "c".*typing\(e\.target\).*getSelection', lightbox)
    assert "Ctrl+C copies the picture" in lightbox


def test_the_helper_lives_in_the_lazy_file_and_boot_only_warms_it():
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert "copyImage" not in app and "contextmenu" not in app
    #: The right-click is live only once attachment-actions.js has loaded, so boot fetches it soon after start.
    assert re.search(r'setTimeout\(\(\) => \[[^\]]*"attachments"[^\]]*\]\.forEach\(ensureModule\)', app)


def test_the_guide_names_the_right_click_and_ctrl_c():
    from tessellate.ai import help_chat

    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "image-viewer")
    assert "Copy image" in body and "Ctrl+C" in body
    assert "in a note" in body


def test_the_viewers_foot_clears_the_status_bar_and_the_details_card():
    css = (CSS / "lightbox-lazy.css").read_text(encoding="utf-8")
    foot = css[css.index(".lightbox-bottom {"):]
    foot = foot[: foot.index("}")]
    assert "bottom: calc(var(--space-4) + var(--status-bar-h))" in foot
    #: The scroll area keeps room for the foot above the status bar, and the picture leaves room for the card.
    for rule in (".lightbox.lightbox-framed {", ".lightbox.lightbox-framed.lightbox-has-film {"):
        block = css[css.index(rule):]
        assert "var(--status-bar-h)" in block[: block.index("}")]
    assert "8.5rem" in css and "6.5rem" not in css[css.index(".lightbox.lightbox-framed .lightbox-stage > img"):][:600]


ROW_HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const src = fs.readFileSync(process.argv[1], "utf8");
const start = src.indexOf("function rowMenuAtEvent");
const end = src.indexOf("//: At the pointer when the menu's items are known");
class FakeElement {}
const opener = {};
const host = { querySelectorAll: () => [opener] };
opener.closest = () => host;
//: A target `inside` some of: the row, an img, an att-card.
const make = (inside) => {
  const el = new FakeElement();
  el.closest = (sel) => {
    if (sel === "#entry-list img") return inside.includes("img") ? el : null;
    if (sel === ".att-card") return inside.includes("att-card") ? el : null;
    if (sel.startsWith("input")) return null;
    return inside.includes("row") ? host : null;
  };
  return el;
};
const ctx = { Element: FakeElement, window: { getSelection: () => "" }, ROW_MENU_HOSTS: ".row" };
vm.createContext(ctx);
vm.runInContext(src.slice(start, end) + "\nthis.rowMenuAtEvent = rowMenuAtEvent;", ctx);
const out = {};
for (const name of ["row", "row img", "row img att-card"]) out[name] = !!ctx.rowMenuAtEvent({ target: make(name) });
console.log(JSON.stringify(out));
"""


@needs_node
def test_a_picture_in_a_note_card_is_not_claimed_by_the_notes_row_menu():
    out = subprocess.run(
        ["node", "-e", ROW_HARNESS, str(JS / "navigation.js")], capture_output=True, text=True, timeout=30, check=True
    )
    claimed = json.loads(out.stdout)
    #: The row keeps its right-click; a bare picture inside it goes to the picture menu (Copy image); a file card keeps its own.
    assert claimed == {"row": True, "row img": False, "row img att-card": True}
