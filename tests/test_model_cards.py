"""The model cards (INBOX 444): what a card says about a model, and the check
behind "Download another model".

The Suggested downloads list was 31 rows of ``name ~size purpose`` with 29
identical Download buttons and nothing about memory. These pin the numbers the
cards show, so the page is not guessing: the memory a model asks for, whether
it fits this computer, what it is good at, the one starting pick per purpose,
and what a typed name is before it is downloaded.
"""

from __future__ import annotations

import pytest

from tessellate.ai import model_cards
from tessellate.ai.model_manager import SUGGESTED_MODELS
from tessellate.core import hardware


# --- the numbers ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [("~2.7 GB", 2.7), ("274 MB", 0.274), ("~19 GB", 19.0), ("1.2 GB", 1.2), ("", None), (None, None), ("big", None)],
)
def test_size_is_read_in_gigabytes(text, expected):
    assert model_cards.size_gb(text) == pytest.approx(expected) if expected is not None else model_cards.size_gb(text) is None


def test_memory_is_the_weights_plus_working_room_rounded_up_to_half_a_gigabyte():
    # 2.0 GB of weights: 2.0 * 1.15 + 0.7 = 3.0
    assert model_cards.ram_needed_gb({"size": "~2.0 GB"}) == 3.0
    # 6.6 GB: 8.29, up to 8.5
    assert model_cards.ram_needed_gb({"size": "~6.6 GB"}) == 8.5
    # A tiny embedding model still asks for a gigabyte and a half, not 0.3.
    assert model_cards.ram_needed_gb({"size": "~274 MB"}) == 1.5


def test_a_stated_figure_beats_the_estimate():
    """The catalogue says "Needs ~16 GB" on the big mixture-of-experts entries;
    the estimate from a 19 GB download would say 22.5, and the page would
    contradict the line printed under it."""
    entry = next(m for m in SUGGESTED_MODELS["moe"] if m["name"] == "gemma4:26b")
    assert entry["ram_gb"] == 16
    assert model_cards.ram_needed_gb(entry) == 16.0


def test_every_shipped_model_has_a_memory_figure():
    for kind, models in SUGGESTED_MODELS.items():
        for model in models:
            assert model_cards.ram_needed_gb(model), f"{kind}/{model['name']} has no readable size"


@pytest.mark.parametrize(
    ("need", "total", "verdict"),
    [
        (3.0, 16, "fits"),
        (9.6, 16, "fits"),  # exactly the 60% line
        (9.7, 16, "tight"),
        (13.6, 16, "tight"),  # exactly the 85% line
        (13.7, 16, "too_big"),
        (16.0, 16, "too_big"),
        (5.0, 8, "tight"),
        (3.0, None, "unknown"),
        (None, 16, "unknown"),
        (3.0, 0, "unknown"),
    ],
)
def test_fit_is_a_share_of_this_computers_memory(need, total, verdict):
    assert model_cards.fit_for(need, total) == verdict


def test_what_a_model_is_good_at_comes_from_its_group_and_its_purpose_line():
    text = {m["name"]: m for m in SUGGESTED_MODELS["text"]}
    assert model_cards.good_for("text", text["llama3.2"]) == ["chat", "filing"]
    assert "agent" in model_cards.good_for("text", text["qwen3.5:4b"])
    assert "long documents" in model_cards.good_for("text", text["mistral-nemo"])
    assert "writing" in model_cards.good_for("text", text["gemma4:12b"])
    assert model_cards.good_for("embedding", SUGGESTED_MODELS["embedding"][0]) == ["embeddings"]
    assert model_cards.good_for("ocr", SUGGESTED_MODELS["ocr"][0]) == ["ocr"]
    vision = {m["name"]: m for m in SUGGESTED_MODELS["vision"]}
    assert model_cards.good_for("vision", vision["moondream"]) == ["vision"]
    assert model_cards.good_for("vision", vision["minicpm-v"]) == ["vision", "ocr"]


def test_each_group_has_exactly_one_starting_pick_and_it_is_in_the_catalogue():
    for kind, models in SUGGESTED_MODELS.items():
        picks = [m["name"] for m in models if model_cards.decorate(kind, m, 16)["recommended"]]
        assert len(picks) == 1, f"{kind}: {picks}"
        assert picks[0] == model_cards.RECOMMENDED[kind]


def test_a_starting_pick_fits_a_modest_computer():
    """A recommendation that does not run on an 8 GB laptop is not a starting
    point. (The mixture-of-experts group's entry point is the one exception it
    states for itself: its pick is its smallest, 7.2 GB.)"""
    for kind, models in SUGGESTED_MODELS.items():
        pick = next(m for m in models if m["name"] == model_cards.RECOMMENDED[kind])
        need = model_cards.ram_needed_gb(pick)
        limit = 12 if kind == "moe" else 4.5
        assert need <= limit, f"{kind}: {pick['name']} wants {need} GB"


# --- this computer's memory ---------------------------------------------------------


def test_the_memory_can_be_overridden_for_a_container(monkeypatch):
    monkeypatch.setenv("TESSELLATE_RAM_GB", "12")
    assert hardware.total_memory_gb() == 12.0
    monkeypatch.setenv("TESSELLATE_RAM_GB", "not a number")
    assert hardware.total_memory_bytes() is None or hardware.total_memory_bytes() > 0


def test_the_real_memory_is_a_positive_number_where_the_platform_can_say(monkeypatch):
    monkeypatch.delenv("TESSELLATE_RAM_GB", raising=False)
    total = hardware.total_memory_bytes()
    assert total is None or total > 256 * 1024**2


# --- the routes -----------------------------------------------------------------------


def test_the_catalogue_route_carries_what_the_card_shows(ai_client, monkeypatch):
    monkeypatch.setenv("TESSELLATE_RAM_GB", "16")
    body = ai_client.get("/models/suggested").json()
    flat = {m["name"]: m for models in body.values() for m in models}
    llama = flat["llama3.2"]
    assert llama["ram_gb"] == 3.0
    assert llama["fit"] == "fits"
    assert llama["recommended"] is True
    assert llama["good_for"] == ["chat", "filing"]
    assert llama["kind"] == "text" and llama["purpose_key"] == "chat"
    assert flat["gemma4:26b"]["fit"] == "too_big"
    assert flat["qwen3.5:9b"]["recommended"] is False


def test_the_catalogue_says_unknown_when_the_memory_is_not_known(ai_client, monkeypatch):
    monkeypatch.setattr(hardware, "total_memory_bytes", lambda: None)
    body = ai_client.get("/models/suggested").json()
    assert {m["fit"] for models in body.values() for m in models} == {"unknown"}


def test_the_hardware_route_reports_the_memory(client, monkeypatch):
    monkeypatch.setenv("TESSELLATE_RAM_GB", "8")
    assert client.get("/models/hardware").json()["ram_gb"] == 8.0
    monkeypatch.setattr(hardware, "total_memory_bytes", lambda: None)
    assert client.get("/models/hardware").json()["ram_gb"] is None


# --- "Download another model": say what it is before it downloads -----------------------


@pytest.mark.parametrize(
    ("typed", "name", "source"),
    [
        ("qwen2.5:3b", "qwen2.5:3b", "ollama"),
        ("llama3.2", "llama3.2", "ollama"),
        ("  Llama3.2:1B ", "llama3.2:1b", "ollama"),
        ("someone/their-model:q4", "someone/their-model:q4", "ollama"),
        ("hf.co/ggml-org/GLM-OCR-GGUF:Q8_0", "hf.co/ggml-org/GLM-OCR-GGUF:Q8_0", "huggingface"),
        ("huggingface.co/unsloth/gemma-3-4b-it-GGUF", "hf.co/unsloth/gemma-3-4b-it-GGUF", "huggingface"),
        ("https://huggingface.co/unsloth/gemma-3-4b-it-GGUF", "hf.co/unsloth/gemma-3-4b-it-GGUF", "huggingface"),
        ("https://huggingface.co/unsloth/gemma-3-4b-it-GGUF/tree/main", "hf.co/unsloth/gemma-3-4b-it-GGUF", "huggingface"),
        (
            "https://huggingface.co/unsloth/gemma-3-4b-it-GGUF/blob/main/gemma-3-4b-it-Q4_K_M.gguf",
            "hf.co/unsloth/gemma-3-4b-it-GGUF:Q4_K_M",
            "huggingface",
        ),
        (
            "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-IQ3_M.gguf?download=true",
            "hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:IQ3_M",
            "huggingface",
        ),
        ("bartowski/Llama-3.2-3B-Instruct-GGUF", "hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF", "huggingface"),
    ],
)
def test_a_good_name_is_read_and_normalised(typed, name, source):
    info = model_cards.inspect_model_name(typed)
    assert info["valid"] is True, info
    assert info["name"] == name
    assert info["source"] == source
    assert info["title"] and info["detail"]
    assert "size is not known" in info["detail"], "the size is never claimed for a name we cannot look up"


@pytest.mark.parametrize(
    "typed",
    [
        "",
        "   ",
        "two words",
        "x" * 201,
        "../../etc/passwd",
        "/usr/models/llama.gguf",
        "C:\\models\\llama.gguf",
        "model.gguf",
        "registry.example.com/team/model:1b",
        "localhost:5000/model",
        "qwen2.5:3b:extra",
        "-leading-dash",
        "name!",
        "https://huggingface.co/unsloth/gemma-3-4b-it-GGUF/blob/main/README.md",
        "https://example.com/model",
    ],
)
def test_a_bad_name_is_refused_with_a_reason(typed):
    info = model_cards.inspect_model_name(typed)
    assert info["valid"] is False
    assert info["error"].endswith(".")
    assert "!" not in info["error"] and "\u2014" not in info["error"]


def test_a_repository_that_may_not_hold_gguf_files_is_warned_not_refused():
    info = model_cards.inspect_model_name("hf.co/meta-llama/Llama-3.2-3B")
    assert info["valid"] is True
    assert any("GGUF" in w for w in info["warnings"])


def test_a_hugging_face_file_without_a_quantisation_in_its_name_says_so():
    info = model_cards.inspect_model_name("https://huggingface.co/a/b-GGUF/blob/main/weights.gguf")
    assert info["valid"] is True
    assert info["name"] == "hf.co/a/b-GGUF"
    assert any("quantisation" in w for w in info["warnings"])


def test_the_inspect_route_also_says_whether_it_is_already_installed(ai_client, fake_ollama):
    fake_ollama.installed = [{"name": "qwen2.5:3b", "size": 1_900_000_000}]
    here = ai_client.post("/models/inspect", json={"name": "qwen2.5:3b"}).json()
    assert here["valid"] is True and here["installed"] is True
    other = ai_client.post("/models/inspect", json={"name": "qwen2.5:7b"}).json()
    assert other["valid"] is True and other["installed"] is False
    bad = ai_client.post("/models/inspect", json={"name": "two words"}).json()
    assert bad["valid"] is False and "installed" not in bad


def test_the_inspect_route_knows_a_suggested_model_and_its_size(ai_client, fake_ollama):
    fake_ollama.installed = []
    info = ai_client.post("/models/inspect", json={"name": "llama3.2"}).json()
    assert info["suggested"] == {"size": "~2.0 GB", "purpose": "Fast all-rounder: the default, and a good first choice"}
    assert ai_client.post("/models/inspect", json={"name": "qwen2.5:7b"}).json()["suggested"] is None


def test_pulling_a_bad_name_is_refused_before_ollama_hears_of_it(ai_client, fake_ollama):
    response = ai_client.post("/models/pull", json={"name": "two words"})
    assert response.status_code == 422
    assert "space" in response.json()["detail"]
    assert ai_client.get("/models/status").json()["pulls"] == {}


def test_pulling_a_pasted_link_downloads_the_normalised_name(ai_client, fake_ollama):
    link = "https://huggingface.co/unsloth/gemma-3-4b-it-GGUF/blob/main/gemma-3-4b-it-Q4_K_M.gguf"
    response = ai_client.post("/models/pull", json={"name": link})
    assert response.status_code == 200
    assert response.json()["name"] == "hf.co/unsloth/gemma-3-4b-it-GGUF:Q4_K_M"


# --- what an installed model may be used for (op4-1005's found-not-fixed) -----


@pytest.mark.parametrize(
    ("entry", "uses"),
    [
        # The catalogue knows these by name, with or without ":latest".
        ({"name": "nomic-embed-text:latest"}, ["embeddings"]),
        ({"name": "llama3.2:latest"}, ["chat"]),
        ({"name": "moondream"}, ["vision", "ocr", "chat"]),
        # Not in the catalogue: Ollama's own details say the kind.
        ({"name": "my/embedder:v2", "details": {"family": "bert", "families": ["bert"]}}, ["embeddings"]),
        ({"name": "someone/seer:7b", "details": {"family": "llama", "families": ["llama", "clip"]}}, ["vision", "ocr", "chat"]),
        ({"name": "someone/writer:7b", "details": {"family": "qwen2", "families": ["qwen2"]}}, ["chat"]),
        # No details (an OpenAI-dialect server): the name is all there is.
        ({"name": "text-embedding-3-small"}, ["embeddings"]),
        ({"name": "llava-phi3"}, ["vision", "ocr", "chat"]),
        ({"name": "some-ocr-model"}, ["ocr"]),
        ({"name": "mistral-small"}, ["chat"]),
    ],
)
def test_an_installed_model_is_offered_only_the_uses_its_kind_has(entry, uses):
    """An embedding model was offered "Use for chat" (and never "Use for
    search"): the installed card offered chat, images and reading text to
    every model whatever it was."""
    assert model_cards.installed_uses(entry) == uses


def test_the_status_poll_carries_each_installed_models_uses(ai_client, fake_ollama):
    ai_client.post("/models/pull", json={"name": "nomic-embed-text"})
    status = ai_client.get("/models/status").json()
    embedder = next(m for m in status["installed_models"] if m["name"].startswith("nomic-embed-text"))
    assert embedder["uses"] == ["embeddings"]


def test_the_installed_card_menu_offers_the_models_own_uses():
    """The menu reads `uses` from the poll, so no client-side list of every
    purpose is offered to a model that cannot serve it."""
    from pathlib import Path

    js = (Path(__file__).resolve().parent.parent / "frontend" / "js" / "settings-models.js").read_text()
    assert '["chat", "vision", "ocr"]' not in js
    assert "uses: m.uses" in js
