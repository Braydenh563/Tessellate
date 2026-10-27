"""Search by meaning downloads only after a yes (the owner, 2026-10-27).

The embedding model used to download from huggingface.co on the first note
saved, unasked, with an environment variable as the only off-switch. Now: no
download without a yes. The app offers it once, with a one-line reason, in
the notice recipe; the answer is kept in settings (`semantic_auto_install`,
`semantic_choice_made`); a Settings row turns it on later; and search runs on
keywords meanwhile with no error. Tests run on a fixed clock-free fake of the
transport: nothing here reaches a network.
"""

from __future__ import annotations

import logging
import socket
from pathlib import Path

import pytest

from tessellate.ai import embeddings as embeddings_module
from tessellate.core import config as config_module
from tessellate.core import deps, embedmodels

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _guard_off(monkeypatch):
    """The environment switch must not be what keeps these offline."""
    monkeypatch.delenv("TESSELLATE_NO_AUTO_INSTALL", raising=False)


@pytest.fixture
def no_network(monkeypatch):
    """Any lookup of a name outside this computer fails the test."""
    seen: list[str] = []
    real = socket.getaddrinfo

    def getaddrinfo(host, *args, **kwargs):
        if str(host) not in ("localhost", "127.0.0.1", "testserver", "::1"):
            seen.append(str(host))
        return real(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    yield seen
    assert seen == [], f"reached beyond this computer: {seen}"


def _service_with_nothing_on_disk(app_state, monkeypatch):
    monkeypatch.setattr(embedmodels, "is_downloaded", lambda repo: False)
    monkeypatch.setattr(embeddings_module, "_package_present", lambda: True)
    return deps.get_embeddings()


# --- the preference and its defaults ----------------------------------------


def test_nothing_downloads_by_default():
    defaults = config_module.DEFAULT_PREFERENCES
    assert defaults["semantic_auto_install"] is False
    assert defaults["semantic_choice_made"] is False


def test_the_answer_round_trips_and_marks_the_question_answered(client):
    prefs = client.get("/preferences").json()
    assert prefs["semantic_auto_install"] is False
    assert prefs["semantic_choice_made"] is False
    reply = client.put("/preferences", json={"semantic_auto_install": True})
    assert reply.status_code == 200
    prefs = client.get("/preferences").json()
    assert prefs["semantic_auto_install"] is True
    assert prefs["semantic_choice_made"] is True


def test_a_no_is_an_answer_too(client):
    reply = client.put("/preferences", json={"semantic_auto_install": False})
    assert reply.status_code == 200
    prefs = client.get("/preferences").json()
    assert prefs["semantic_auto_install"] is False
    assert prefs["semantic_choice_made"] is True


# --- the service: no download without a yes ---------------------------------


def test_a_first_save_downloads_nothing_and_search_keeps_working(app_state, monkeypatch, no_network, caplog):
    service = _service_with_nothing_on_disk(app_state, monkeypatch)
    fetched = []
    monkeypatch.setattr(embeddings_module, "_fetch_model_as_a_task", lambda *a, **k: fetched.append(a))
    with caplog.at_level(logging.INFO):
        assert service.embed_text("a note about bread") is None
    assert fetched == []
    assert service.awaiting_consent is True
    # Said in words, as a state and not as a failure: keyword search, no traceback.
    assert "keyword" in (service.last_error or "")
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]
    # No cooldown either: the answer, when it comes, takes effect on the next save.
    assert service._load_failed_at is None


def test_a_yes_lets_the_next_save_start_the_download(app_state, monkeypatch):
    from tests import _fake_fastembed

    service = _service_with_nothing_on_disk(app_state, monkeypatch)
    _fake_fastembed.install(monkeypatch)
    monkeypatch.setattr(embedmodels, "cache_health", lambda repo: {"state": "absent", "missing": []})
    fetched = []

    def fetch(cls, repo, label):
        fetched.append((repo, label))
        raise OSError("stop here: the fetch itself is not under test")

    monkeypatch.setattr(embeddings_module, "_fetch_model_as_a_task", fetch)
    service.embed_text("one")
    assert fetched == []
    deps.get_config().set_preference("semantic_auto_install", True)
    service.embed_text("two")
    assert [label for _repo, label in fetched] == ["Downloading the search model"]


def test_a_model_already_on_disk_needs_no_yes(app_state, monkeypatch):
    monkeypatch.setattr(embedmodels, "is_downloaded", lambda repo: True)
    monkeypatch.setattr(embeddings_module, "_package_present", lambda: True)
    service = deps.get_embeddings()
    service.embed_text("a note")
    # The gate let it through to the cache; nothing asked for a yes.
    assert service.awaiting_consent is False


def test_an_explicit_switch_of_engine_is_not_held_back(app_state):
    """A service pinned by the person's own Install or model switch carries no preferences."""
    service = deps.get_embeddings().pinned("fastembed", "BAAI/bge-small-en-v1.5")
    assert service._download_allowed() is True


def test_the_status_offers_once_and_stops_when_answered(client, monkeypatch):
    reply = client.get("/models/status").json()["semantic_offer"]
    assert reply is False
    deps.get_embeddings().awaiting_consent = True
    reply = client.get("/models/status").json()["semantic_offer"]
    assert reply is True
    client.put("/preferences", json={"semantic_auto_install": False})
    reply = client.get("/models/status").json()["semantic_offer"]
    assert reply is False


def test_a_booted_app_saves_and_searches_without_the_switch(app_state, monkeypatch, no_network):
    """The keyword path with the real service, nothing mocked but the disk."""
    from fastapi.testclient import TestClient

    from tessellate.api.app import create_app

    monkeypatch.setattr(embedmodels, "is_downloaded", lambda repo: False)
    with TestClient(create_app()) as client:
        token = client.post("/auth/setup", json={"password": "a long password"}).json()["token"]
        headers = {"X-Auth-Token": token}
        reply = client.post("/entries", json={"content": "a note about bread"}, headers=headers)
        assert reply.status_code in (200, 201)
        found = client.get("/search?q=bread", headers=headers)
        assert found.status_code == 200


# --- the page: the offer, the row, the help ---------------------------------


def _text(*parts: str) -> str:
    return "".join((ROOT / p).read_text(encoding="utf-8") for p in parts)


def test_the_offer_says_size_and_source_in_one_line_and_asks_before_anything():
    js = _text("frontend/js/semantic-notice.js")
    assert "function semanticOffer" in js
    assert "about 130 MB" in js and "huggingface.co" in js
    assert "Download" in js and "No thanks" in js
    assert "semantic_auto_install" in js
    assert chr(0x2014) not in js
    assert '!"' not in js and "! " not in js and '!`' not in js  # no exclamation marks in copy


def test_the_status_poll_reaches_the_offer():
    assert "status.semantic_offer" in _text("frontend/js/status.js")


def test_settings_row_says_downloads_are_ask_first():
    html = _text("frontend/index.html")
    assert 'id="pref-semantic-auto-install"' in html
    assert "Download search by meaning" in html
    assert "Install search by meaning automatically" not in html


def test_the_guide_and_privacy_say_it_asks_first():
    from tessellate.ai import help_chat, help_topics_more

    guide = _text("src/tessellate/ai/help_chat.py", "src/tessellate/ai/help_topics_more.py")
    assert "Download search by meaning" in guide
    privacy = _text("docs/PRIVACY.md")
    assert "asks first" in privacy.lower() or "after a yes" in privacy.lower()
    assert help_chat and help_topics_more
