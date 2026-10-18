"""INBOX 1300 C42: a composer reply's text was lost after a restart.

A "yo <name>" call answers with text plus an "ask" offer, and the offer saved
its follow-up chips while the reply was still streaming, racing the turn's own
save: the chips write read the checkpoint row (empty answer) and wrote it back
over the finished turn. The offer now only draws the chips; `offerFollowups`
saves them after the turn is saved (the `c42` Playwright sweep (kept out of the repo, which is at its scratchpad file cap) measures it
in the app)."""

from __future__ import annotations

import re

from tests._app_js import app_js_text


def test_a_calls_asks_are_not_saved_mid_stream() -> None:
    js = app_js_text()
    offer = re.search(r"function digestOffer\(.*?\n\}\n", js, re.S)
    assert offer, "digestOffer moved"
    ask = offer.group(0).split('offer?.kind === "ask"', 1)[1].split("return;", 1)[0]
    assert "saveFollowups" not in ask, "chips saved mid-stream race the turn save"


def test_the_turn_end_saves_the_drawn_chips() -> None:
    js = app_js_text()
    body = re.search(r"async function offerFollowups\(.*?\n\}\n", js, re.S)
    assert body and "bubble.dataset.followups" in body.group(0)
