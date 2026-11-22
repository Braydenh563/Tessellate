"""L-world-class-354: board miniatures waiting on map-preview.js drew in the one task its load ended
(92 to 119ms at 4x CPU at dashboard boot, 5,000 notes). They now draw from a queue that yields every 12ms."""

from tests._app_js import app_js_text


def _body():
    js = app_js_text()
    start = js.index("function mapPreview(board")
    return js[start : js.index("function mapCountLabel", start)]


def test_previews_queue_instead_of_drawing_in_the_load_callback():
    body = _body()
    assert "mapPreview.queue.push([svg, board, size])" in body
    assert ".then((ok) => ok && mapPreviewDraw" not in body


def test_the_drain_yields_between_slices_and_survives_a_throw():
    body = _body()
    drain = body[body.index("mapPreview.drain = async") :]
    assert "performance.now() + 12" in drain
    assert "scheduler.yield()" in drain and "setTimeout(resolve, 0)" in drain
    assert "catch (error)" in drain
