"""The filing model is warmed only when it is installed (the owner,
2026-10-07: the janitor warmed a default "llama3.2" nobody had pulled, and the
log said "Chat with 'llama3.2' failed")."""

from __future__ import annotations

import pytest

from tessellate.ai import janitor

# The warm-up reads the config (`choose_chat_model_if_missing`), which without
# an app state builds one in the repo's own `data/` folder.
pytestmark = pytest.mark.usefixtures("app_state")


class _Models:
    def __init__(self, model):
        self.model = model

    def utility_model(self):
        return self.model


class _Ollama:
    def __init__(self, names):
        self.names = names
        self.chats = []

    def is_running(self):
        return True

    def list_models(self):
        return [{"name": name} for name in self.names]

    def chat(self, model, messages, **kwargs):
        self.chats.append(model)
        return {"message": {"content": "OK"}}


def test_a_model_that_is_not_installed_is_not_warmed(caplog):
    ollama = _Ollama(["qwen3:4b"])
    with caplog.at_level("INFO", logger="memorymap.janitor"):
        janitor.warm_filing_model(_Models("llama3.2"), ollama)
    assert ollama.chats == []
    assert not [r for r in caplog.records if r.levelname == "WARNING"]


def test_an_installed_model_is_warmed_by_its_bare_name():
    ollama = _Ollama(["llama3.2:latest"])
    janitor.warm_filing_model(_Models("llama3.2"), ollama)
    assert ollama.chats == ["llama3.2"]
