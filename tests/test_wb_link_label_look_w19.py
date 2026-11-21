"""W19 C15: a connector's label has its own size, colour, bold and chip (audit t20#12)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
FMT = (JS / "whiteboard-format.js").read_text(encoding="utf-8")
WB = (JS / "whiteboard.js").read_text(encoding="utf-8")
HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "07-whiteboard-misc.css").read_text(encoding="utf-8") + (
    ROOT / "frontend" / "css" / "library-lazy.css"
).read_text(encoding="utf-8")  # L-ui-modernisation-31: Library-only rules live in library-lazy.css


def test_link_takes_the_label_look_rows():
    link = FMT[FMT.index("  link: [") :].split("\n", 1)[0]
    assert '"linklook"' in link
    for ident in ("wb-fmt-lsize", "wb-fmt-lcolor", "wb-fmt-lbold", "wb-fmt-lchip"):
        assert f'id="{ident}"' in HTML
        assert ident in FMT
    assert HTML.count('data-fmt="linklook"') == 3


def test_look_is_saved_as_label_props_and_painted_on_the_label():
    for key in ("label_size", "label_color", "label_bold", "label_chip"):
        assert key in FMT
    paint = WB[WB.index("function wbPaintLinkLabel(") :]
    paint = paint[: paint.index("\n}\n")]
    for token in ("parsed.label_size", "parsed.label_bold", "parsed.label_color", "wb-link-label-chip"):
        assert token in paint
    assert ".wb-link-label.wb-link-label-chip" in CSS
