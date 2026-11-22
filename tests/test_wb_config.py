"""The board configuration file (L-whiteboard-44): schema checks, the route, and the JS half as source."""

from __future__ import annotations

import json

import pytest
from fastapi import HTTPException

from tessellate.api import wb_config
from tests._app_js import frontend_text

GOOD = {
    "format": "tessellate-board-config",
    "version": 1,
    "board": {"grid_size": 24, "guides": True, "paper": "a4", "defaults": {"shape": {"fill": "#336699"}}},
    "palettes": [{"name": "Brand", "colours": ["#336699", "#FFAA00", "#336699"]}],
    "shape_libraries_off": ["drawio-bpmn", "drawio-bpmn"],
}


def _check(obj):
    return wb_config.check_config(json.dumps(obj))


def test_a_valid_configuration_is_cleaned():
    out = _check(GOOD)
    assert out["board"]["grid_size"] == 24 and out["board"]["paper"] == "a4"
    assert out["palettes"][0]["colours"] == ["#336699", "#ffaa00"], "lower-cased and de-duplicated"
    assert out["shape_libraries_off"] == ["drawio-bpmn"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda c: c.update(format="other"),
        lambda c: c.update(version=2),
        lambda c: c.update(script="alert(1)"),
        lambda c: c["board"].update(image="/media/x.png"),
        lambda c: c["board"].update(color="#000000"),
        lambda c: c["board"].update(grid_size=-3),
        lambda c: c["palettes"][0]["colours"].append("red"),
        lambda c: c.update(palettes=[{"name": "p", "colours": ["#000000"]}] * 9),
        lambda c: c.update(shape_libraries_off=["../../etc"]),
    ],
)
def test_a_bad_configuration_is_refused_with_a_sentence(mutate):
    cfg = json.loads(json.dumps(GOOD))
    mutate(cfg)
    with pytest.raises(HTTPException) as err:
        _check(cfg)
    assert err.value.status_code == 422 and err.value.detail


def test_the_sentence_is_ours_and_never_echoes_the_file():
    """Our validators' sentences reach the toast; the file's own values and the library's words do not."""
    for mutate, said in [
        (lambda c: c.update(version=99), "another version of the app"),
        (lambda c: c["board"].update(zzz_secret_key=1), "does not read."),
        (lambda c: c.update(palettes="not a list"), wb_config.WRONG_KIND),
    ]:
        cfg = json.loads(json.dumps(GOOD))
        mutate(cfg)
        with pytest.raises(HTTPException) as err:
            _check(cfg)
        assert said in err.value.detail and "99" not in err.value.detail and "zzz" not in err.value.detail


def test_not_json_and_oversized_are_refused():
    with pytest.raises(HTTPException) as err:
        wb_config.check_config("{nope")
    assert err.value.status_code == 422
    with pytest.raises(HTTPException) as err:
        wb_config.check_config(" " * (wb_config.MAX_CONFIG_CHARS + 1))
    assert err.value.status_code == 413


def test_the_route_checks_and_stores_nothing(ai_client):
    r = ai_client.post("/whiteboard/config/check", json={"content": json.dumps(GOOD)})
    assert r.status_code == 200 and r.json()["palettes"][0]["name"] == "Brand"
    bad = ai_client.post("/whiteboard/config/check", json={"content": "[]"})
    assert bad.status_code == 422


def test_the_browser_half_exports_and_imports_through_the_checked_route():
    js = frontend_text("whiteboard-config.js")
    assert '"/whiteboard/config/check"' in js and "wbSetBackground(" in js and "wbBoardBackground()" in js
    assert '"wb-lib-sets-off"' in js and "wbLibCreate(" in js and "saveFile(" in js
    assert "eval(" not in js and "new Function" not in js, "a configuration is data, never code"
