"""Edit data (INBOX 797, canvasdepth2; WHITEBOARD_PLAN section 3 and
"canvasdepth, ranked" row 10, draw.io's custom properties). `data.props`, up
to 30 named values on an item, edited in the Format panel's Data tab. The
browser half is `scratchpad/ui-sweeps/wbdepth2.js wbeditdata`."""

from __future__ import annotations

from pathlib import Path
from tests._app_js import index_html_text

ROOT = Path(__file__).resolve().parents[1]
FMT = (ROOT / "frontend" / "js" / "whiteboard-format.js").read_text(encoding="utf-8")
CMD = (ROOT / "frontend" / "js" / "whiteboard-commands.js").read_text(encoding="utf-8")
HTML = index_html_text()


def _body(src: str, name: str) -> str:
    start = src.index(name)
    return src[start : src.index("\n}\n", start)]


def _text(client, props):
    return client.post("/whiteboard/objects", json={"kind": "text", "data": {"content": "x", "props": props}, "x": 0, "y": 0, "width": 100, "height": 40})


def test_props_are_named_bounded_and_kept(ai_client):
    made = _text(ai_client, {"owner": "Ann", "due date": "May"})
    assert made.status_code in (200, 201) and made.json()["data"]["props"] == {"owner": "Ann", "due date": "May"}
    for bad in ({"9 lives": "x"}, {"": "x"}, {"owner": "y" * 201}, {f"k{i}": "v" for i in range(31)}):
        refused = _text(ai_client, bad)
        assert refused.status_code == 422, bad


def test_the_data_tab_reads_and_writes_one_item():
    assert 'data-format-tab="data"' in HTML and 'data-format-panel="data"' in HTML and 'id="wb-fmt-prop-add"' in HTML
    assert '"data"' in FMT[FMT.index("const WB_FMT_TABS") :][:80]
    sync = _body(FMT, "function wbFmtSyncProps(")
    assert "entries.length === 1" in sync and "list.contains(document.activeElement)" in sync
    save = _body(FMT, "function wbFmtWriteProps(")
    assert "propsChain" in _body(FMT, "function wbFmtSaveProps(")
    assert "WB_PROP_NAME.test(name)" in save and 'wbFmtApply("props"' in save
    assert 'id: "edit-data"' in CMD and 'wbFormatOpen("data")' in CMD
