"""Wires the AI services into `core/deps.py`, which may not import `ai`.

Importing this module registers how the shared state builds the chat client,
the model manager and the embedding service, hands the model manager the
running app's getters and gives `voice` its config peek. Everything that
builds the app state (the app, the launcher, the MCP server, scripts, the
test conftest) imports it first; `deps` says so if it was not.
"""

from __future__ import annotations

import logging

from tessellate.ai import model_manager, provider, voice
from tessellate.ai.embeddings import EmbeddingService
from tessellate.ai.model_manager import ModelManager
from tessellate.ai.ollama_client import OllamaClient
from tessellate.ai.openai_client import OpenAICompatClient
from tessellate.ai.provider import Provider
from tessellate.core import deps
from tessellate.core.config import ConfigManager
from tessellate.search import engine as _engine  # noqa: F401  (registers itself in search.matrix_hooks)


def build_llm_client(config: ConfigManager) -> Provider:
    """The chat backend the user has chosen (§6).

    Two dialects, not four products: `openai` covers LM Studio, llama.cpp, Jan
    and vLLM alike, because the only thing that differs between them is the
    base URL. Everything downstream, the agent, the librarian, the janitor , 
    is written against `Provider` and never asks which one it got.

    An unrecognised provider name falls back to Ollama rather than raising. The
    preferences file is a JSON file the user is invited to edit by hand, and a
    typo in it should cost the setting, not the app.
    """
    provider = str(config.get_preference("llm_provider", "ollama") or "ollama").lower()
    base_url = str(config.get_preference("llm_base_url", "") or "").strip()

    # The lock is enforced here as well as at the endpoint, and that is not
    # belt-and-braces for its own sake: `preferences.json` is a plain file the
    # user is invited to edit by hand, and it is what a restored backup or a
    # copied config brings with it. Checking only on the way in would mean a
    # remote address that never passed through the endpoint is used anyway, 
    # silently, and on every turn.
    #
    # Falling back to the provider's local default rather than refusing to
    # start: the app must open so the setting can be fixed from inside it.
    if base_url and config.get_preference("local_only_ai", True):
        from tessellate.core import security

        allowed, reason, _ = security.check_backend_url(base_url, local_only=True)
        if not allowed:
            logging.getLogger("tessellate.config").warning(
                "refusing the saved AI backend %r and using the local default "
                "instead: %s",
                base_url,
                reason,
            )
            base_url = ""

    if provider == "openai":
        return OpenAICompatClient(
            base_url=base_url or deps.DEFAULT_BASE_URLS["openai"],
            api_key=str(config.get_preference("llm_api_key", "") or ""),
        )
    # `config.ollama_url` carries the OLLAMA_URL environment variable, which
    # predates this setting: so it stays the default for the Ollama path
    # rather than being overwritten by an empty preference.
    return OllamaClient(base_url=base_url or config.ollama_url)


def _sampling_overrides() -> dict:
    config = deps.peek_config()
    return config.get_preference("sampling_overrides", {}) if config else {}


def register() -> None:
    deps.register_ai_factories(
        llm_client=build_llm_client,
        model_manager=ModelManager,
        embeddings=EmbeddingService,
    )
    provider.set_sampling_overrides_getter(_sampling_overrides)
    # Handed to the model manager so its durable jobs find the running app's
    # own objects without importing `deps` (a cycle).
    model_manager.APP_GETTERS.update(
        db=deps.get_db, embeddings=deps.get_embeddings, ollama=deps.get_ollama
    )
    voice.CONFIG_PEEK = deps.peek_config


register()
