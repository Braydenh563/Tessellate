"""Owner, 2026-11-10: changing the background art drew the dashboard's constellation a
second time into the same card, leaving two (the first one empty). A draw now
removes the card's earlier constellation parts first."""

from tests._app_js import frontend_text


def test_a_second_draw_replaces_the_first():
    art = frontend_text("dash-art.js")
    body = art[art.index("async function renderArtWidget(body) {") :]
    clear = body.index(":scope > .art-holder, :scope > .art-caption, :scope > .art-controls, :scope > .art-legend")
    assert clear < body.index('const holder = document.createElement("div");')
    assert clear < body.index("body.appendChild(holder);")
