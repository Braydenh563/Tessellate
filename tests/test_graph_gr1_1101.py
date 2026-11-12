"""Audit 1031 GR1 (ranked row 19): the 2,000-note map's cold settle. Each test names the cost it keeps out."""

from tests._app_js import frontend_text
from tests._js_scope import gc_frame


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    return text[i : text.index(end, i)]


def test_the_layout_worker_is_started_while_the_data_is_on_its_way():
    # A dedicated worker's script loads through tasks on the page's own thread:
    # started after the data, it waited behind the first frames, 20 to 22 s at
    # 4x CPU on 2,000 notes before the worker saw `init` (22 ms on an idle page).
    js = frontend_text("graph-canvas.js")
    render = _between(js, "async function renderGraphCanvas(s = gcTab) {", "\n}\n")
    assert render.index("gcSpawnWorker(s);") < render.index("await apiJson(endpoint)")
    start = _between(js, "function gcStartWorker(", "\n}\n")
    assert "gcSpawnWorker(s);" in start and "new Worker(" not in start
    spawn = _between(js, "function gcSpawnWorker(", "\n}\n")
    assert "new Worker(`/js/graph-worker.js${lazyAssetStamp(\"/js/graph-worker.js\")}`)" in spawn


def test_a_map_hidden_until_its_first_fit_is_not_drawn():
    # Hidden behind the first fade at the default camera (zoom 1, the starting
    # spiral overflowing the card), the 2,000-note map still drew: 15 frames,
    # each a 1 to 2 s raster at 4x CPU, back to back, which also kept the
    # worker's start and its first tick waiting (first tick at 25 s).
    js = frontend_text("graph-canvas.js")
    unframed = _between(js, "const gcUnframed = ", "\n")
    assert 'opacity === "0"' in unframed and "!s.fittedOnce" in unframed
    request = _between(js, "function gcRequestDraw(", "\n}\n")
    assert "gcUnframed(s)" in request.split("requestAnimationFrame")[0]
    reveal = _between(js, "function gcReveal(s) {", "\n}\n")
    assert reveal.index('s.canvas.style.opacity = "";') < reveal.index("gcRequestDraw(s);")


def test_a_moving_map_strokes_its_thin_links_as_hairlines_and_rests_on_true_strokes():
    # One 1.3 px stroke of 1,879 curved links was 21 ms of raster at 1x (the
    # stroker's outline of the whole path); a 1 px hairline with the alpha
    # scaled by the width is 0.9 ms and within 3% of the ink. A 2,000-note drag
    # at 4x spent 3.6 s of its 4.7 s of draws in that raster. Only while the
    # map moves (a layout running, a drag): the frame at rest strokes as before.
    js = frontend_text("graph-canvas.js")
    assert "const GC_HAIR_PX = 1.5;" in js
    hair = _between(js, "function gcSetStroke(", "\n}\n")
    assert "s.strokeMoving" in hair and "!dashed" in hair and "device <= GC_HAIR_PX" in hair
    assert "Math.min(1, alpha * device)" in hair
    draw = gc_frame(js)
    assert "s.strokeMoving = Boolean(s.layoutRunning || s.dragNode);" in draw
    bucket = _between(draw, "const strokeBucket = ", "};")
    assert "gcSetStroke(ctx, s, " in bucket and "ctx.lineWidth = (style.width" not in bucket.split("ctx.stroke(bucket.path)")[0]
    end = _between(js, '} else if (message.type === "end") {', 'if (s.size === "full") graphMinimapQueuePaint();')
    assert "if (s.hairDrawn) gcRequestDraw(s);" in end
