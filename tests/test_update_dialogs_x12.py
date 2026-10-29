"""Update dialogs (audit 1029 X12): the apply poll ends, Escape stores
nothing, and the copy names the app."""

from __future__ import annotations

from tests._app_js import app_js_text


def _body(name: str) -> str:
    js = app_js_text()
    start = js.index(f"function {name}(")
    return js[start : js.index("\n}\n", start)]


def test_the_apply_poll_has_a_failure_exit():
    body = _body("applyUpdateNow")
    assert "for (;;)" not in body
    assert "misses < 10" in body and "failed: true" in body.split("misses < 10")[1]


def test_escape_on_the_update_choice_stores_nothing():
    ask = _body("askUpdateChoiceOnce")
    assert ask.index("if (yes === undefined) return") < ask.index('"/update/choice"')
    confirm = _body("confirmDialog")
    #: Escape and the backdrop answer undefined, falsy like "no" for every
    #: caller, but a caller that stores the answer can tell leaving apart.
    assert confirm.count("close()") == 2 and confirm.count("close(false)") == 1


def test_the_copy_names_the_app():
    assert "Tessellate AI" not in app_js_text()
