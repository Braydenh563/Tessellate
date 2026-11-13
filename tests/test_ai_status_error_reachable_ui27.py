"""Source text: L-ui-modernisation-27, "Check the status dot's error state can
be reached, or remove it" (IDEAS.md, retired: "The status dot's "X" state in
the top bar: it was never seen"). Measured in the app at 1440 dark with
/models/status refused after a first answer: the pill went from "off" to
data-level "error", glyph ✕, "Can't reach Tessellate", on a red tint. The
path that gets there is read here."""
from tests._app_js import app_js_text


def _fn(src, name):
    start = src.index(name)
    return src[start : src.index("\n}\n", start)]


def test_a_failed_poll_drops_the_status():
    poll = _fn(app_js_text(), "async function refreshModelStatus(")
    catch = poll[poll.index("} catch (err) {") :]
    assert 'err?.name === "TimeoutError"' in catch
    assert "modelStatus = null;" in catch.split("else {", 1)[1]


def test_no_status_after_an_answer_is_the_error_level():
    state = _fn(app_js_text(), "function aiStatusState(")
    head = state[: state.index('level: "error"')]
    assert "if (!modelStatus) {" in head and "if (!statusEverAnswered) {" in head
    assert 'error: "✕"' in app_js_text()
