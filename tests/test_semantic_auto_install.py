"""The owner: "the user should be able to cancel or refuse the auto install of
sentence transformers when first downloading the app".

Three seams, each tested here: the preference that refuses it, the `auto`
flag on the /tasks row that lets the app say "I started this", and the
Settings switch that is bound to the preference."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tessellate.api import routes_tasks
from tessellate.core import config as config_module
from tessellate.core import deps, extras

ROOT = Path(__file__).resolve().parents[1]


def _no_dispatch(*args, **kwargs):
    """Queues nothing on the pool: no pip in a test."""


def _missing_package(service, monkeypatch):
    monkeypatch.setattr(
        service,
        "_load_builtin_model",
        lambda: (_ for _ in ()).throw(ModuleNotFoundError("No module named 'fastembed'")),
    )


@pytest.fixture(autouse=True)
def _allow_auto_install(monkeypatch):
    # The suite may run with the guard on; these tests are about the
    # preference, so the env var must not be what stops the install.
    monkeypatch.delenv("TESSELLATE_NO_AUTO_INSTALL", raising=False)
    yield
    # A test here starts a fake install (`_no_dispatch`) that never finishes;
    # left running it showed up in every later /tasks test on the worker.
    extras.reset_for_tests()


def test_the_preference_defaults_to_off():
    # The owner, 2026-10-27: no download without a yes (test_semantic_consent_1027.py).
    assert config_module.DEFAULT_PREFERENCES["semantic_auto_install"] is False


def test_the_preference_round_trips_through_the_api(client):
    before = client.get("/preferences").json()["semantic_auto_install"]
    assert before is False
    saved = client.put("/preferences", json={"semantic_auto_install": True})
    assert saved.status_code == 200
    after = client.get("/preferences").json()["semantic_auto_install"]
    assert after is True


def test_refusing_the_install_never_starts_pip(app_state, monkeypatch):
    service = deps.get_embeddings()
    _missing_package(service, monkeypatch)
    started = []
    monkeypatch.setattr(extras, "start", lambda *a, **k: (started.append(a), (True, "x"))[1])
    deps.get_config().set_preference("semantic_auto_install", False)

    assert service.embed_text("a note") is None
    assert not started
    # Search keeps working by keyword and says why, in words a person can act on.
    assert "not installed" in (service.last_error or "")
    # Not spent: turning it back on lets the next failure install.
    assert service._auto_install_attempted is False


def test_turning_it_back_on_lets_the_next_failure_install(app_state, monkeypatch):
    service = deps.get_embeddings()
    _missing_package(service, monkeypatch)
    started = []
    monkeypatch.setattr(extras, "start", lambda *a, **k: (started.append(k), (False, "mocked"))[1])
    config = deps.get_config()
    config.set_preference("semantic_auto_install", False)
    service.embed_text("one")
    assert not started
    config.set_preference("semantic_auto_install", True)
    service._load_failed_at = None
    service.embed_text("two")
    assert started == [{"auto": True}]


def test_the_auto_install_says_it_is_automatic(app_state, monkeypatch):
    service = deps.get_embeddings()
    _missing_package(service, monkeypatch)
    seen = []

    def fake_start(extra_id, reinstall=False, auto=False):
        seen.append((extra_id, auto))
        return False, "mocked"

    monkeypatch.setattr(extras, "start", fake_start)
    deps.get_config().set_preference("semantic_auto_install", True)
    service.embed_text("a note")
    assert seen == [("semantic", True)]


def test_a_task_row_for_an_automatic_install_carries_auto(client, monkeypatch):
    monkeypatch.setattr(extras, "is_installed", lambda extra: False)
    monkeypatch.setattr(extras, "_dispatch", _no_dispatch)
    extras.reset_for_tests()
    assert extras.start("semantic", auto=True)[0] is True
    rows = [t for t in routes_tasks.collect() if t["kind"] == "extra"]
    assert rows and rows[0]["auto"] is True
    assert rows[0]["name"] == "semantic"


def test_a_manual_install_is_not_marked_auto(client, monkeypatch):
    monkeypatch.setattr(extras, "is_installed", lambda extra: False)
    monkeypatch.setattr(extras, "_dispatch", _no_dispatch)
    extras.reset_for_tests()
    assert extras.start("semantic")[0] is True
    rows = [t for t in routes_tasks.collect() if t["kind"] == "extra"]
    assert rows and rows[0]["auto"] is False


def test_the_auto_flag_does_not_outlive_its_install(client, monkeypatch):
    monkeypatch.setattr(extras, "is_installed", lambda extra: False)
    monkeypatch.setattr(extras, "_dispatch", _no_dispatch)
    extras.reset_for_tests()
    extras.start("semantic", auto=True)
    extras.reset_for_tests()
    extras.start("voice")
    rows = [t for t in routes_tasks.collect() if t["kind"] == "extra"]
    assert rows[0]["auto"] is False


def test_stopping_the_automatic_install_stops_the_job(client, monkeypatch):
    monkeypatch.setattr(extras, "is_installed", lambda extra: False)
    monkeypatch.setattr(extras, "_dispatch", _no_dispatch)
    extras.reset_for_tests()
    extras.start("semantic", auto=True)
    response = client.post("/tasks/cancel", json={"kind": "extra", "name": "semantic"})
    assert response.status_code == 200, response.text


# --- the switch in Settings, Search and index -------------------------------


def test_settings_has_the_switch_with_a_help_popover():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert 'id="pref-semantic-auto-install"' in html
    assert "Download search by meaning" in html
    assert 'data-help-for="semantic-auto-install-help"' in html
    assert 'id="semantic-auto-install-help"' in html


def test_the_switch_is_bound_to_the_preference():
    from tests._app_js import app_js_text

    js = app_js_text()
    assert 'setPreference("semantic_auto_install"' in js
    assert "prefsCache.semantic_auto_install" in js


def test_the_guide_tells_the_choice():
    from tessellate.ai import help_chat, help_topics_more

    text = (
        Path(help_chat.__file__).read_text(encoding="utf-8")
        + Path(help_topics_more.__file__).read_text(encoding="utf-8")
    )
    joined = re.sub(r'"\s*\n\s*"', "", text)
    assert "Download search by meaning" in joined


# --- the first-time notice (a lazy module) ----------------------------------


def test_the_notice_is_lazy_and_reached_from_the_status_poll():
    js = ROOT / "frontend" / "js"
    assert 'semanticNotice: ["/js/semantic-notice.js"]' in (js / "app.js").read_text(encoding="utf-8")
    status = (js / "status.js").read_text(encoding="utf-8")
    assert "status.semantic_offer" in status
    assert "semanticOffer(Boolean(status.semantic_offer), status.semantic_engine_moved)" in status
    assert '"semanticOffer", "semanticOnboardingOffer"' in (js / "app.js").read_text(encoding="utf-8")
    # Lazy means not a boot script.
    assert "semantic-notice.js" not in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")


def test_the_notice_says_the_size_and_source_and_can_say_no():
    text = (ROOT / "frontend" / "js" / "semantic-notice.js").read_text(encoding="utf-8")
    assert "about 130 MB" in text and "Keyword search" in text and "huggingface.co" in text
    assert "Download" in text and "No thanks" in text
    assert "semanticSetAutoInstall" in text and "semantic_auto_install: on" in text
    assert '"Undo"' in text
    assert "\u2014" not in text


def test_the_welcome_card_offers_the_same_choice():
    js = ROOT / "frontend" / "js"
    assert "semanticOnboardingOffer(box)" in (js / "onboarding.js").read_text(encoding="utf-8")
    assert "function semanticOnboardingOffer" in (js / "semantic-notice.js").read_text(encoding="utf-8")
