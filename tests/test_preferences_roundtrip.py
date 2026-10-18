"""Every preference the frontend sends is one the backend keeps (INBOX 509).

`PreferencesBody` is a pydantic model with the default `extra="ignore"`, so a
key it does not name is dropped without an error: Settings' Ask Atlas where
each note belongs, File notes in the background, Describe images and Read
text in images were all shown and never saved, each checkbox snapping back
on the next load. This compares the frontend's keys with the body, and
checks a round trip for each of the switches that were lost.
"""
import re
from pathlib import Path

import pytest

from tessellate.api.routes_settings import PreferencesBody
from tests._app_js import app_js_text

JS_DIR = Path(__file__).resolve().parents[1] / "frontend" / "js"


def _sent_keys() -> set[str]:
    js = app_js_text()
    keys = set(re.findall(r'setPreference\(\s*"([a-z_]+)"', js))
    for m in re.finditer(r'"/preferences",\s*\{[^}]*?body:\s*JSON\.stringify\(\{([^)]*?)\}\)', js, re.S):
        keys |= set(re.findall(r"([a-z_]+)\s*:", m.group(1)))
    return keys


def test_every_key_the_frontend_sends_is_in_the_body():
    missing = sorted(_sent_keys() - set(PreferencesBody.model_fields))
    assert not missing, f"sent to /preferences and silently dropped: {missing}"


def test_every_key_the_frontend_reads_comes_back(app_state):
    reads = set(re.findall(r"prefsCache\??\.([a-z_]+)", app_js_text()))
    from tessellate.api.routes_settings import get_preferences

    returned = set(get_preferences())
    assert not sorted(reads - returned), sorted(reads - returned)


@pytest.mark.parametrize(
    "key",
    ["ai_first_filing", "background_filing", "auto_caption_images",
     "auto_read_image_text", "warm_search_model_at_launch"],
)
def test_a_switch_turned_off_stays_off(client, key):
    assert client.get("/preferences").json()[key] is True
    assert client.put("/preferences", json={key: False}).status_code == 200
    assert client.get("/preferences").json()[key] is False


@pytest.mark.parametrize("on", [True, False])
def test_the_launch_switch_decides_whether_startup_warms_the_model(app_state, monkeypatch, on):
    """INBOX 509: off leaves the model to its first use."""
    from tessellate.ai import embeddings
    from tessellate.api.app import create_app

    calls = []
    monkeypatch.setattr(embeddings, "start_warmup", lambda *a, **k: calls.append(1))
    app_state.set_preference("warm_search_model_at_launch", on)
    create_app()
    assert len(calls) == (1 if on else 0)
