"""Q22 (owner 2026-11-11, audit 1028 K11): the API key is kept in the OS
keyring when there is one, in a 0600 file otherwise, and never in
preferences.json."""

import json
import os
import stat

import pytest

from tessellate.core import pinstore, secrets_store
from tessellate.core.config import ConfigManager


class FakeRing(pinstore.Store):
    name = "fake"

    def __init__(self):
        self.items = {}

    def available(self):
        return True

    def put(self, account, secret):
        self.items[account] = secret

    def get(self, account):
        return self.items.get(account)

    def delete(self, account):
        self.items.pop(account, None)


def _config(tmp_path, monkeypatch):
    monkeypatch.setenv("TESSELLATE_DATA_DIR", str(tmp_path))
    return ConfigManager()


def _saved(config):
    return json.loads(config.preferences_path.read_text(encoding="utf-8"))


def test_without_a_keyring_the_key_is_an_owner_only_file(tmp_path, monkeypatch):
    config = _config(tmp_path, monkeypatch)
    config.set_preference("llm_api_key", "sk-one")
    assert config.get_preference("llm_api_key") == "sk-one"
    assert _saved(config)["llm_api_key"] == ""
    kept = tmp_path / "secrets" / "llm_api_key"
    assert kept.read_text() == "sk-one"
    if os.name == "posix":
        assert stat.S_IMODE(kept.stat().st_mode) == 0o600
        assert stat.S_IMODE(kept.parent.stat().st_mode) == 0o700
    assert ConfigManager().get_preference("llm_api_key") == "sk-one"


def test_with_a_keyring_no_file_is_written(tmp_path, monkeypatch):
    ring = FakeRing()
    pinstore.set_store(ring)
    config = _config(tmp_path, monkeypatch)
    config.set_preference("llm_api_key", "sk-two")
    assert list(ring.items.values()) == ["sk-two"]
    assert not (tmp_path / "secrets" / "llm_api_key").exists()
    assert _saved(config)["llm_api_key"] == ""
    assert ConfigManager().get_preference("llm_api_key") == "sk-two"


def test_a_key_an_older_version_left_in_the_file_moves_out(tmp_path, monkeypatch):
    (tmp_path / "preferences.json").write_text(json.dumps({"llm_api_key": "sk-old", "theme": "dark"}))
    config = _config(tmp_path, monkeypatch)
    assert config.get_preference("llm_api_key") == "sk-old"
    assert _saved(config) == {**_saved(config), "llm_api_key": "", "theme": "dark"}
    assert (tmp_path / "secrets" / "llm_api_key").read_text() == "sk-old"


def test_clearing_the_key_removes_it_everywhere(tmp_path, monkeypatch):
    ring = FakeRing()
    pinstore.set_store(ring)
    config = _config(tmp_path, monkeypatch)
    config.set_preference("llm_api_key", "sk-three")
    config.set_preference("llm_api_key", "")
    assert ring.items == {}
    assert config.get_preference("llm_api_key", "") == ""
    assert ConfigManager().get_preference("llm_api_key", "") == ""


def test_a_keyring_that_refuses_falls_back_to_the_file(tmp_path, monkeypatch):
    class Refusing(FakeRing):
        def put(self, account, secret):
            raise pinstore.StoreError("locked")

    pinstore.set_store(Refusing())
    config = _config(tmp_path, monkeypatch)
    config.set_preference("llm_api_key", "sk-four")
    assert (tmp_path / "secrets" / "llm_api_key").read_text() == "sk-four"
    assert _saved(config)["llm_api_key"] == ""


def test_a_key_that_cannot_be_stored_is_not_lost(tmp_path, monkeypatch):
    monkeypatch.setattr(secrets_store, "_write_file", lambda *a: (_ for _ in ()).throw(OSError("read-only")))
    config = _config(tmp_path, monkeypatch)
    config.set_preference("llm_api_key", "sk-five")
    assert config.get_preference("llm_api_key") == "sk-five"
    assert _saved(config)["llm_api_key"] == "sk-five"
