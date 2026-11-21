"""Silero VAD as an optional extra (Brief 87, L691): the segmenting of a probability
track, the engine with fakes, absence, the pinned extra, and one real-model check
when the file is named by `TESSELLATE_SILERO_VAD` (the real model is unverified in CI)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np
import pytest

from tessellate.ai import vad
from tessellate.core import extra_downloads, extras

STEP = vad.WINDOW * 1000 / vad.RATE  # 32 ms a window


@pytest.fixture(autouse=True)
def _no_runner():
    vad.set_runner(None)
    yield
    vad.set_runner(None)


def _track(*runs: tuple[int, int]) -> list[float]:
    """Windows 0..n: 0.9 inside each (first, last) window run, 0.0 elsewhere."""
    length = max(stop for _start, stop in runs) + 10
    probs = [0.0] * length
    for start, stop in runs:
        for index in range(start, stop):
            probs[index] = 0.9
    return probs


def test_bursts_against_silence_give_the_right_segments() -> None:
    # Windows 20..60 and 120..170 are speech: 640 to 1920 ms and 3840 to 5440 ms.
    found = vad.segments_from(_track((20, 60), (120, 170)))
    assert len(found) == 2
    (a0, a1), (b0, b1) = found
    assert abs(a0 - (20 * STEP - vad.PAD_MS)) <= 1 and abs(a1 - (60 * STEP + vad.PAD_MS)) <= 1
    assert abs(b0 - (120 * STEP - vad.PAD_MS)) <= 1 and abs(b1 - (170 * STEP + vad.PAD_MS)) <= 1


def test_silence_gives_nothing_and_a_click_is_not_speech() -> None:
    assert vad.segments_from([0.0] * 100) == []
    assert vad.segments_from(_track((10, 13))) == []  # 96 ms, under MIN_SPEECH_MS


def test_a_breath_inside_a_phrase_does_not_split_it() -> None:
    probs = _track((10, 40), (42, 80))  # a two-window (64 ms) gap
    assert len(vad.segments_from(probs)) == 1
    assert len(vad.segments_from(_track((10, 40), (50, 80)))) == 2  # 320 ms apart


def test_one_quiet_window_inside_speech_is_held_by_the_hysteresis() -> None:
    probs = _track((10, 50))
    probs[30] = 0.4  # under THRESHOLD, over THRESHOLD - HYSTERESIS
    assert len(vad.segments_from(probs)) == 1
    probs[30] = 0.1
    probs[31] = 0.1
    probs[32] = 0.1
    probs[33] = 0.1  # 128 ms of silence splits it
    assert len(vad.segments_from(probs)) == 2


def test_segments_stay_inside_the_clip() -> None:
    found = vad.segments_from(_track((0, 40)), total_ms=1000)
    assert found == [(0, 1000)]


def test_speech_share() -> None:
    assert vad.speech_share([(0, 500), (1000, 1500)], 2000) == 0.5
    assert vad.speech_share([], 0) == 0.0


def test_the_runner_stands_in_for_the_engine_end_to_end() -> None:
    seen = {}

    def runner(samples):
        seen["n"] = len(samples)
        return _track((10, 40))

    vad.set_runner(runner)
    assert vad.available()
    samples = np.zeros(vad.RATE * 3, dtype=np.float32)  # three seconds
    found = vad.speech_segments(samples)
    assert seen["n"] == 48_000 and len(found) == 1


def test_absent_engine_or_model_is_available_false_and_says_what_to_install(app_state, monkeypatch) -> None:
    assert not vad.available()
    with pytest.raises(RuntimeError, match="Speech detection"):
        vad.probabilities(np.zeros(1024, dtype=np.float32))
    monkeypatch.setattr(vad, "engine_installed", lambda: False)
    assert not vad.available()


def test_the_model_is_read_from_the_data_dir_once_installed(app_state, monkeypatch) -> None:
    model = extras.EXTRAS_BY_ID[vad.MODEL_EXTRA]
    assert vad.model_path() is None
    target = extra_downloads.folder(model)
    target.mkdir(parents=True)
    (target / vad.MODEL_FILE).write_bytes(b"x")
    (target / extra_downloads.MARKER).write_text(json.dumps({"version": model.version, "files": [vad.MODEL_FILE]}))
    assert vad.model_path() == target / vad.MODEL_FILE
    monkeypatch.setattr(vad, "engine_installed", lambda: True)
    assert vad.available()


def test_the_extra_is_an_engine_and_a_pinned_model_in_one_bundle() -> None:
    engine = extras.EXTRAS_BY_ID[vad.ENGINE_EXTRA]
    model = extras.EXTRAS_BY_ID[vad.MODEL_EXTRA]
    assert engine.kind == "pip" and engine.module == "onnxruntime" and engine.packages == ("onnxruntime",)
    assert model.kind == "download" and model.version
    assert extras.BUNDLES_BY_ID["vad"].extras == ("vad", "vad-model")
    (download,) = model.downloads
    assert download.members == (("", vad.MODEL_FILE),)
    assert re.fullmatch(r"[0-9a-f]{64}", download.sha256) and 0 < download.size < 10_000_000
    assert download.url.startswith("https://") and extra_downloads.url_allowed(download.url)
    assert re.search(r"/[0-9a-f]{40}/", download.url), "pinned to a commit, never a branch"


def _burst(seconds: float, freq: float, rng) -> np.ndarray:
    """Speech-like: a voiced carrier with a syllable-rate envelope plus a little noise."""
    t = np.arange(int(seconds * vad.RATE)) / vad.RATE
    envelope = 0.5 * (1 + np.sin(2 * np.pi * 4 * t))
    voiced = sum(np.sin(2 * np.pi * freq * k * t) / k for k in range(1, 6))
    return (0.3 * envelope * voiced + 0.01 * rng.standard_normal(len(t))).astype(np.float32)


@pytest.mark.skipif(not os.environ.get("TESSELLATE_SILERO_VAD"), reason="names the real model file; unverified in CI")
def test_the_real_model_finds_the_bursts_in_a_synthetic_clip(app_state, monkeypatch) -> None:
    rng = np.random.default_rng(7)
    quiet = lambda s: (0.002 * rng.standard_normal(int(s * vad.RATE))).astype(np.float32)  # noqa: E731
    clip = np.concatenate([quiet(1.0), _burst(2.0, 140, rng), quiet(1.5), _burst(2.0, 190, rng), quiet(1.0)])
    monkeypatch.setattr(vad, "model_path", lambda: Path(os.environ["TESSELLATE_SILERO_VAD"]))
    monkeypatch.setattr(vad, "engine_installed", lambda: True)
    found = vad.speech_segments(clip)
    print("real model segments (ms):", found, "share:", vad.speech_share(found, round(len(clip) * 1000 / vad.RATE)))
    # Bursts at 1.0 to 3.0 s and 4.5 to 6.5 s: two segments, each edge within a quarter second.
    assert len(found) == 2
    for (start, stop), (want_start, want_stop) in zip(found, [(1000, 3000), (4500, 6500)], strict=True):
        assert abs(start - want_start) < 250 and abs(stop - want_stop) < 250
