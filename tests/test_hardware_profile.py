"""Settings, Models, Suggested downloads: the hardware the badges are judged on.

Owner, 2026-10-17 (INBOX 904 B67): "The top of the suggested models section
should show the detected hardware of the user and allow the user to adjust or
edit it if it is incorrect. Also I feel like the 'fits' or 'tight'
suggestions should take into account the user's current memory and what and
how many ai models they already have installed."

The profile is the detected memory, the free memory now and the graphics
cards, with the person's correction on top. The fit verdict reads the
corrected numbers, the video memory when there is some, and the memory that is
free right now unless the model is already loaded (its memory is taken).
"""

from __future__ import annotations

import pytest

from tessellate.ai import model_cards
from tessellate.core import hardware


# --- reading the machine ----------------------------------------------------------


def test_meminfo_gives_the_memory_available_now():
    text = "MemTotal:       16384000 kB\nMemFree:          200000 kB\nMemAvailable:    8192000 kB\n"
    assert hardware.parse_meminfo_available(text) == pytest.approx(8192000 * 1024)
    assert hardware.parse_meminfo_available("MemTotal: 1 kB\n") is None
    assert hardware.parse_meminfo_available("") is None


def test_nvidia_smi_output_is_a_card_with_its_video_memory():
    cards = hardware.parse_nvidia_smi("NVIDIA GeForce RTX 3060, 12288\nNVIDIA T400, 4096\n")
    assert cards == [
        {"name": "NVIDIA GeForce RTX 3060", "vram_gb": 12.0, "shared": False},
        {"name": "NVIDIA T400", "vram_gb": 4.0, "shared": False},
    ]
    assert hardware.parse_nvidia_smi("") == []
    assert hardware.parse_nvidia_smi("garbage, not a number") == []


def test_no_card_means_none_not_a_guess(monkeypatch):
    monkeypatch.setattr(hardware, "detect_gpus", lambda: [])
    profile = hardware.profile(None)
    assert profile["vram_gb"] is None and profile["gpus"] == []


# --- the correction ----------------------------------------------------------------


def test_a_correction_wins_over_what_was_detected(monkeypatch):
    monkeypatch.setenv("TESSELLATE_RAM_GB", "8")
    monkeypatch.setattr(hardware, "detect_gpus", lambda: [{"name": "X", "vram_gb": 4.0, "shared": False}])
    detected = hardware.profile(None)
    assert detected["ram_gb"] == 8.0 and detected["vram_gb"] == 4.0 and detected["override"] is None
    fixed = hardware.profile({"ram_gb": 32, "vram_gb": 0})
    assert fixed["ram_gb"] == 32 and fixed["detected_ram_gb"] == 8.0
    assert fixed["vram_gb"] is None  # 0 is "no graphics card"
    assert fixed["detected_vram_gb"] == 4.0
    assert fixed["override"] == {"ram_gb": 32, "vram_gb": 0}


# --- the verdict ---------------------------------------------------------------------


def test_low_free_memory_makes_a_fit_tight_with_a_reason():
    assert model_cards.fit_for(4, 16) == "fits"
    assert model_cards.fit_for(4, 16, free_gb=2) == "tight"
    assert model_cards.fit_reason(4, 16, free_gb=2) == "low_free"
    assert model_cards.fit_for(4, 16, free_gb=12) == "fits"
    assert model_cards.fit_reason(4, 16, free_gb=12) is None


def test_low_free_memory_never_calls_a_small_model_too_big():
    # Free memory only moves a verdict one step, the total decides "too big".
    assert model_cards.fit_for(8, 16, free_gb=1) == "tight"
    assert model_cards.fit_for(15, 16, free_gb=1) == "too_big"


def test_video_memory_that_holds_the_model_makes_it_fit():
    assert model_cards.fit_for(6, 8) == "tight"
    assert model_cards.fit_for(6, 8, vram_gb=12) == "fits"
    assert model_cards.fit_reason(6, 8, vram_gb=12) == "gpu"
    assert model_cards.fit_for(10, 8, vram_gb=12) == "tight"
    assert model_cards.fit_for(10, 8, vram_gb=6) == "too_big"


def test_a_loaded_model_is_not_judged_on_the_memory_it_already_holds():
    entry = {"name": "llama3.2", "size": "~2.0 GB"}
    cold = model_cards.decorate("text", entry, 16, free_gb=1.0)
    assert cold["fit"] == "tight" and cold["fit_reason"] == "low_free"
    warm = model_cards.decorate("text", entry, 16, free_gb=1.0, loaded=True)
    assert warm["fit"] == "fits" and warm["fit_reason"] is None


# --- the routes ------------------------------------------------------------------------


@pytest.fixture
def _fixed_machine(monkeypatch):
    monkeypatch.setenv("TESSELLATE_RAM_GB", "16")
    monkeypatch.setattr(hardware, "free_memory_gb", lambda: 9.0)
    monkeypatch.setattr(hardware, "detect_gpus", lambda: [{"name": "NVIDIA T400", "vram_gb": 4.0, "shared": False}])


def test_the_route_reports_what_it_detected(client, _fixed_machine):
    body = client.get("/models/hardware").json()
    assert body["ram_gb"] == 16.0 and body["detected_ram_gb"] == 16.0
    assert body["free_ram_gb"] == 9.0
    assert body["vram_gb"] == 4.0
    assert body["gpus"][0]["name"] == "NVIDIA T400"
    assert body["override"] is None


def test_a_saved_correction_changes_the_catalogue_and_can_be_cleared(ai_client, _fixed_machine):
    flat = lambda body: {m["name"]: m for models in body.values() for m in models}  # noqa: E731
    before = flat(ai_client.get("/models/suggested").json())
    assert before["gemma4:26b"]["fit"] == "too_big"
    reply = ai_client.put("/models/hardware", json={"ram_gb": 64, "vram_gb": 24})
    assert reply.status_code == 200
    assert reply.json()["ram_gb"] == 64 and reply.json()["vram_gb"] == 24
    after = flat(ai_client.get("/models/suggested").json())
    assert after["gemma4:26b"]["fit"] != "too_big"
    assert ai_client.get("/models/hardware").json()["override"] == {"ram_gb": 64, "vram_gb": 24}
    cleared = ai_client.put("/models/hardware", json={})
    assert cleared.json()["override"] is None and cleared.json()["ram_gb"] == 16.0
    assert flat(ai_client.get("/models/suggested").json())["gemma4:26b"]["fit"] == "too_big"


@pytest.mark.parametrize("body", [{"ram_gb": -1}, {"ram_gb": 0}, {"ram_gb": 99999}, {"vram_gb": -2}, {"ram_gb": "lots"}])
def test_a_nonsense_correction_is_refused(client, _fixed_machine, body):
    assert client.put("/models/hardware", json=body).status_code == 422


# --- the page ------------------------------------------------------------------------------


def test_the_models_page_shows_the_hardware_and_can_correct_it():
    from tests._app_js import JS_DIR, FRONTEND_DIR

    page = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    code = (JS_DIR / "settings-models.js").read_text(encoding="utf-8")
    for element in ("suggested-hardware-edit", "suggested-hardware-form", "hardware-ram", "hardware-vram", "hardware-reset"):
        assert f'id="{element}"' in page
    assert '"/models/hardware", { method: "PUT"' in code
    assert "fit_reason" in code
    # Free memory moves, so the verdicts are asked for again while the page is open.
    assert "MODEL_HARDWARE_REFRESH_MS" in code
