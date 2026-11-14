"""X14: a bulk act's card lists the first five notes and a Show all control
(L-chat-61). The server already sent `items` and the cap (50) and the
"Done: 13. Not done: note 4 (it is private)." line; the card never drew them."""

from pathlib import Path

from tessellate.ai import commands

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "frontend" / "js" / "ask-compose.js").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "css" / "ask-compose-lazy.css").read_text(encoding="utf-8")


def test_the_card_draws_the_first_five_and_a_show_all():
    body = SRC[SRC.index("function renderActCard(") :]
    body = body[: body.index("\n}\n")]
    assert "ACT_ITEMS_SHOWN = 5" in SRC
    assert "const itemList = actItemList(event.items)" in body
    assert "Show all ${" in SRC and 'className = "act-items"' in SRC
    assert ".act-items" in CSS


def test_the_partial_failure_line_names_what_was_left():
    line = commands.summarise_done(["Tagged note 1", "Tagged note 2"], [{"id": 4, "reason": "private"}])
    assert line == "Done: Tagged note 1; Tagged note 2. Not done: note 4 (it is private)."
    assert commands._MAX_NOTES == 50
