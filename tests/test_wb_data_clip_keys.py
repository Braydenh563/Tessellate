"""Copy data and Paste data carry the item's tooltip and link as well as its custom properties
(WHITEBOARD_PLAN section 2, "Edit data, edit tooltip, note, link": draw.io's Alt+Shift+B and E copy the whole
attribute set). The block runs in node here against stubs for the board."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


def _block() -> str:
    start = FMT.index("wbFmtState.dataKeys = (() => {")
    return FMT[start : FMT.index("})();", start) + 5]


def _run(body: str) -> dict:
    script = f"""
const wbFmtState = {{ dataClip: null }};
const WB_FMT_FIELDS = {{ shape: ["props", "tip"], text: ["props"] }};
const said = [], toasts = [];
const wbAnnounce = (m) => said.push(m), toast = (m) => toasts.push(m);
const wbFmtSketch = (e) => e.item.parsed;
const wbItemLink = (kind, item) => (kind === "sketch" ? item.parsed.link || "" : item.data?.link || "");
const wbTakesLink = () => true;
let entries = [];
const wbFmtEntries = () => entries;
let applied = [];
const wbFmtApply = async (field, patch, text) => {{ for (const e of entries) applied.push(patch(e, e.k)); said.push(text); }};
{_block()}
(async () => {{ {body} }})();
"""
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=30, check=True).stdout)


def test_the_copy_holds_props_tooltip_and_link():
    out = _run("""
entries = [{ kind: "sketch", k: "shape", item: { parsed: { props: { a: "1" }, tip: "Hello", link: "https://example.com" } } }];
wbFmtState.dataKeys.copy();
console.log(JSON.stringify({ clip: wbFmtState.dataClip, said }));
""")
    assert out["clip"] == {"props": {"a": "1"}, "tip": "Hello", "link": "https://example.com"}
    assert out["said"] == ["Data copied: 1 property, the tooltip, the link."]


def test_an_item_with_a_link_only_can_be_copied():
    out = _run("""
entries = [{ kind: "sketch", k: "shape", item: { parsed: { link: "https://example.com" } } }];
wbFmtState.dataKeys.copy();
console.log(JSON.stringify({ clip: wbFmtState.dataClip, toasts }));
""")
    assert out["clip"] == {"link": "https://example.com"} and out["toasts"] == []


def test_paste_sets_each_part_the_copy_held_and_the_tooltip_only_where_the_item_has_the_field():
    out = _run("""
wbFmtState.dataClip = { props: { a: "1" }, tip: "Hello", link: "https://example.com" };
entries = [{ kind: "sketch", k: "shape", item: {} }, { kind: "sketch", k: "text", item: {} }];
await wbFmtState.dataKeys.paste();
wbFmtState.dataClip = { link: "https://example.org" };
applied = [];
await wbFmtState.dataKeys.paste();
console.log(JSON.stringify({ applied }));
""")
    # The second paste held only a link: it leaves props and tip alone.
    assert out["applied"] == [{"link": "https://example.org"}, {"link": "https://example.org"}]


def test_paste_reaches_both_kinds_in_the_first_run():
    out = _run("""
wbFmtState.dataClip = { props: { a: "1" }, tip: "Hello", link: "https://example.com" };
entries = [{ kind: "sketch", k: "shape", item: {} }, { kind: "sketch", k: "text", item: {} }];
await wbFmtState.dataKeys.paste();
console.log(JSON.stringify({ applied }));
""")
    assert out["applied"] == [
        {"props": {"a": "1"}, "tip": "Hello", "link": "https://example.com"},
        {"props": {"a": "1"}, "link": "https://example.com"},
    ]


def test_an_item_with_nothing_says_so():
    out = _run("""
entries = [{ kind: "sketch", k: "shape", item: { parsed: {} } }];
wbFmtState.dataKeys.copy();
console.log(JSON.stringify({ clip: wbFmtState.dataClip, toasts }));
""")
    assert out["clip"] is None and out["toasts"] == ["That item has no data to copy."]
