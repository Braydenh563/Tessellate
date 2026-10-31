"""INBOX 1467 part 1: one reference to any object, one function to build it
from a card element and one to render it at a destination (obj-ref.js)."""

from __future__ import annotations

from tests._objmove_node import needs_node, run

FILES = ["obj-ref.js"]

CARD = """
const mk = (sel, data, text = "") => {
  const card = { dataset: data, getAttribute: () => null, matches: (s) => s === sel,
    querySelector: () => (text ? { textContent: text } : null) };
  card.closest = (s) => (s.split(",").includes(sel) ? card : null);
  return card;
};
"""


@needs_node
def test_a_reference_has_kind_id_title_and_is_refused_for_other_things() -> None:
    out = run(FILES, """__out([
      objRef("note", "12", "  A   spaced\\n title "), objRef("chat", 4, "x"), objRef("board", null, "x"),
      objRef("map", 3, ""), objRef("image", 9, "p.png", "/media/p.png"), objKey(objRef("document", 7, "d")),
      objRef("note", 1, "x".repeat(300)).title.length,
    ])""")
    assert out[0] == {"kind": "note", "id": 12, "title": "A spaced title", "url": ""}
    assert out[1] is None and out[2] is None
    assert out[3]["title"] == "Mind map 3"
    assert out[4]["url"] == "/media/p.png"
    assert out[5] == "document:7"
    assert out[6] == 120


@needs_node
def test_every_card_shape_builds_the_same_reference() -> None:
    out = run(FILES, CARD + """__out([
      objRefFromCard(mk("[data-obj]", { obj: "document:4", objTitle: "Plan" })),
      objRefFromCard(mk("[data-obj]", { obj: "image:2", objTitle: "p.png", objUrl: "/media/p.png" })),
      objRefFromCard(mk("[data-stop-key]", { stopKey: "map:8" }, "Atlas")),
      objRefFromCard(mk(".timeline-row[data-key]", { key: "board:10" }, "Launch")),
      objRefFromCard(mk("#entry-list > li[data-id]", { id: "5" })),
      objRefFromCard(mk("[data-stop-key]", { stopKey: "tag:0" }, "work")),
      objRefFromCard({ closest: () => null }),
    ])""")
    assert [r and (r["kind"], r["id"], r["title"]) for r in out[:5]] == [
        ("document", 4, "Plan"),
        ("image", 2, "p.png"),
        ("map", 8, "Atlas"),
        ("board", 10, "Launch"),
        ("note", 5, "Five"),
    ]
    assert out[1]["url"] == "/media/p.png"
    assert out[5] is None and out[6] is None


@needs_node
def test_the_link_text_is_the_apps_own_link_form() -> None:
    out = run(FILES, """__out([
      objLinkText(objRef("note", 1, "Trip [plan]|x")), objLinkText(objRef("document", 2, "Notes")),
      objLinkText(objRef("map", 3, "House jobs")), objLinkText(objRef("board", 4, "Q3")),
      objLinkText(objRef("image", 5, "cat", "/media/cat.png")), objLinkText(objRef("file", 6, "a.pdf", "/files/6")),
      objLinkText(objRef("image", 7, "bare")),
    ])""")
    assert out == [
        "[[Trip plan x]]",
        "[[Notes]]",
        "![[map:3|House jobs]]",
        "![[board:4|Q3]]",
        "![cat](/media/cat.png)",
        "[a.pdf](/files/6)",
        "bare",
    ]


@needs_node
def test_rendering_in_the_chat_uses_the_composers_own_staging() -> None:
    out = run(FILES, """
      const dest = { type: "chat", el: {} };
      const r = [
        objRender(objRef("note", 5, "Five"), dest), objRender(objRef("note", 5, "Five"), dest),
        objRender(objRef("document", 2, "Doc"), dest), objRender(objRef("map", 3, "M"), dest),
        objRender(objRef("file", 4, "f.pdf"), dest),
        objRender(objRef("image", 6, "p.png", "/media/p.png"), dest), objRender(objRef("image", 6, "p.png"), dest),
      ];
      __out({ r, notes: attachedNoteIds, images: attachedImages.length, log });
    """)
    assert out["r"] == [True] * 7
    assert out["notes"] == [5], "the same note twice stages once"
    assert out["images"] == 1
    assert ["doc", 2, "Doc"] in out["log"] and ["board", 3, "M"] in out["log"] and ["file", 4, "f.pdf"] in out["log"]


@needs_node
def test_a_full_composer_refuses_the_fifth_picture() -> None:
    out = run(FILES, """
      const dest = { type: "chat", el: {} };
      const r = [1, 2, 3, 4, 5].map((n) => objRender(objRef("image", n, "p", "/m/p"), dest));
      __out(r)
    """)
    assert out == [True, True, True, True, False]


@needs_node
def test_text_destinations_insert_the_link_and_unknown_ones_do_nothing() -> None:
    out = run(FILES, """
      const typed = [];
      document.execCommand = (name, _ui, text) => { typed.push(text); return true; };
      const field = { matches: (s) => s.includes("textarea"), focus() { log.push("focus"); } };
      const a = objRender(objRef("document", 2, "Plan"), { type: "text", el: field });
      const b = objRender(objRef("document", 2, "Plan"), { type: "nowhere", el: field });
      const c = objRender(null, { type: "text", el: field });
      __out({ a, b, c, typed });
    """)
    assert out == {"a": True, "b": False, "c": False, "typed": ["[[Plan]]"]}
