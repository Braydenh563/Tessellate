"""The search-by-meaning switch once the model is on disk (INBOX 1533).

The owner: "it's already been downloaded so why is it a toggle?". On disk, the
preference no longer downloads anything; it only lets a model with missing
files be fetched again (`embeddings._fetch_again`). The row says so. A model the
app cannot fetch itself (Gemma's terms, nomic not bundled) was chipped "Runs
in the app" though its row said to use it through Ollama.
`scratchpad/ui-sweeps/semswitch1533.js` measured both in Settings."""

from __future__ import annotations

from pathlib import Path

from tests._app_js import frontend_text

HTML = (Path(__file__).parents[1] / "frontend" / "index.html").read_text(encoding="utf-8")


def test_the_switch_names_what_it_does_once_the_model_is_here():
    js = frontend_text("settings-models.js")
    assert 'id="semantic-auto-install-label"' in HTML and 'id="semantic-auto-install-hint"' in HTML
    assert 'ready ? "Repair search by meaning by itself" : "Download search by meaning"' in js
    assert 'status.embedding_ready && status.embedding_backend !== "ollama"' in js


def test_a_model_the_app_cannot_fetch_is_through_ollama():
    js = frontend_text("embed-choices.js")
    assert 'choice.backend === "ollama" || !choice.one_press ? "Through Ollama" : "Runs in the app"' in js
