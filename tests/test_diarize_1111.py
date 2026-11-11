"""Speaker labels by voice, all local (BACKLOG 102 item 8, gap 12; the owner,
2026-11-11).

The engine is sherpa-onnx (onnxruntime, no torch) with two pinned model files
in the data dir; both are an optional extra. Nothing here downloads or runs
a model: `diarize.set_runner` is the seam a fake fills (CLAUDE.md section 4:
real inference is unverified in tests), and the download is checked as a
table of pins, not fetched.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tessellate.ai import diarize, speakers, voice
from tessellate.core import extra_downloads, extras, recordings, transcript

HERE = Path(__file__).parent / "fixtures" / "meetings"
SEGMENTS = transcript.clean(json.loads((HERE / "launch_sync.segments.json").read_text()))
WEBM_HEAD = b"\x1a\x45\xdf\xa3" + b"\x00" * 60
#: The sample's five lines: two voices, found as clusters 7 and 3 by the fake,
#: so numbering by first appearance is exercised.
SPANS = [(0, 6150, 7), (8200, 64005, 3), (3661000, 3663000, 7)]


def _seg(start: int, end: int, text: str = "x") -> dict:
    return {"start": start, "end": end, "text": text, "speaker": None}


# --- assigning speakers to lines ---------------------------------------------


def test_lines_get_numbered_speakers_in_the_order_they_first_speak() -> None:
    segs = [_seg(0, 1000), _seg(1200, 2000), _seg(2200, 3000)]
    out = diarize.assign(segs, [(0, 1100, 9), (1100, 2100, 4), (2100, 3000, 9)])
    assert [s["speaker"] for s in out] == ["Speaker 1", "Speaker 2", "Speaker 1"]
    assert all(s["speaker"] is None for s in segs)  # the input is never changed


def test_a_line_takes_the_voice_that_covers_most_of_it() -> None:
    out = diarize.assign([_seg(0, 900), _seg(500, 4500)], [(0, 1000, 1), (1000, 4000, 2), (9000, 9500, 1)])
    assert [s["speaker"] for s in out] == ["Speaker 1", "Speaker 2"]


def test_a_line_in_a_gap_takes_a_near_voice_or_none() -> None:
    near = diarize.assign([_seg(2000, 2500), _seg(9000, 9500)], [(0, 1800, 1), (9400, 9900, 2)])
    assert [s["speaker"] for s in near] == ["Speaker 1", "Speaker 2"]
    far = diarize.assign([_seg(20000, 20500)], [(0, 1000, 1), (1000, 2000, 2)])
    assert far[0]["speaker"] is None


def test_one_voice_labels_nothing() -> None:
    """A monologue has nobody to tell apart; a label there is noise."""
    out = diarize.assign([_seg(0, 1000), _seg(1500, 2500)], [(0, 3000, 5)])
    assert all(s["speaker"] is None for s in out)


def test_assign_keeps_the_paragraph_flag_and_text() -> None:
    segs = [{**_seg(0, 1000, "Hello"), "paragraph": True}, _seg(1000, 2000, "Hi")]
    out = diarize.assign(segs, [(0, 1000, 0), (1000, 2000, 1)])
    assert out[0]["paragraph"] is True and out[0]["text"] == "Hello" and out[1]["text"] == "Hi"


# --- availability (the extra absent leaves everything as it was) --------------


@pytest.fixture(autouse=True)
def _no_runner():
    diarize.set_runner(None)
    yield
    diarize.set_runner(None)


def test_unavailable_without_the_engine_or_the_models(monkeypatch) -> None:
    monkeypatch.setattr(diarize, "engine_installed", lambda: False)
    monkeypatch.setattr(diarize, "model_folder", lambda: None)
    assert diarize.available() is False
    monkeypatch.setattr(diarize, "engine_installed", lambda: True)
    assert diarize.available() is False  # models missing
    monkeypatch.setattr(diarize, "engine_installed", lambda: False)
    monkeypatch.setattr(diarize, "model_folder", lambda: Path("/x"))
    assert diarize.available() is False  # engine missing


def test_a_runner_set_for_a_test_counts_as_available() -> None:
    diarize.set_runner(lambda path: SPANS)
    assert diarize.available() is True


def test_label_audio_returns_the_lines_untouched_when_the_runner_fails(tmp_path) -> None:
    def broken(path):
        raise RuntimeError("model would not load")

    diarize.set_runner(broken)
    out = diarize.label_audio(SEGMENTS, tmp_path / "a.webm")
    assert out == SEGMENTS


# --- the engine call (a fake sherpa-onnx module) -------------------------------


class _FakeSpan:
    def __init__(self, start: float, end: float, speaker: int) -> None:
        self.start, self.end, self.speaker = start, end, speaker


def test_spans_come_from_the_engine_in_milliseconds(monkeypatch, tmp_path) -> None:
    import sys
    import types

    seen: dict = {}

    class _Result:
        def sort_by_start_time(self):
            return [_FakeSpan(0.0, 1.5, 1), _FakeSpan(1.5, 2.25, 0)]

    class _Engine:
        sample_rate = 16000

        def __init__(self, config) -> None:
            seen["config"] = config

        def process(self, samples, callback=None):
            seen["samples"] = len(samples)
            return _Result()

    ns = types.SimpleNamespace
    fake = types.ModuleType("sherpa_onnx")
    fake.OfflineSpeakerDiarizationConfig = lambda **kw: ns(**kw)
    fake.OfflineSpeakerSegmentationModelConfig = lambda **kw: ns(**kw)
    fake.OfflineSpeakerSegmentationPyannoteModelConfig = lambda **kw: ns(**kw)
    fake.SpeakerEmbeddingExtractorConfig = lambda **kw: ns(**kw)
    fake.FastClusteringConfig = lambda **kw: ns(**kw)
    fake.OfflineSpeakerDiarization = _Engine
    monkeypatch.setitem(sys.modules, "sherpa_onnx", fake)
    monkeypatch.setattr(diarize, "model_folder", lambda: tmp_path)
    monkeypatch.setattr(diarize, "engine_installed", lambda: True)
    monkeypatch.setattr(voice, "_decode_samples", lambda path, rate=16000: [0.0] * 32000)
    assert diarize.spans(tmp_path / "a.webm") == [(0, 1500, 1), (1500, 2250, 0)]
    config = seen["config"]
    assert config.segmentation.pyannote.model == str(tmp_path / diarize.SEGMENTATION)
    assert config.embedding.model == str(tmp_path / diarize.EMBEDDING)
    assert seen["samples"] == 32000


# --- the extra ----------------------------------------------------------------


def test_the_extra_is_an_engine_and_pinned_models_in_one_bundle() -> None:
    engine = extras.EXTRAS_BY_ID["speakers"]
    models = extras.EXTRAS_BY_ID["speakermodels"]
    assert engine.kind == "pip" and engine.module == "sherpa_onnx" and engine.packages == ("sherpa-onnx",)
    assert models.kind == "download" and models.version
    assert extras.BUNDLES_BY_ID["speakers"].extras == ("speakers", "speakermodels")
    names = {name for download in models.downloads for _member, name in download.members}
    assert {diarize.SEGMENTATION, diarize.EMBEDDING} <= names
    for download in models.downloads:
        assert download.url.startswith("https://") and re.fullmatch(r"[0-9a-f]{64}", download.sha256)
        assert 0 < download.size < 100_000_000
        assert extra_downloads.url_allowed(download.url)


def test_the_models_are_read_from_the_data_dir_once_installed(app_state) -> None:
    models = extras.EXTRAS_BY_ID["speakermodels"]
    assert diarize.model_folder() is None
    target = extra_downloads.folder(models)
    target.mkdir(parents=True)
    names = [name for download in models.downloads for _member, name in download.members]
    for name in names:
        (target / name).write_bytes(b"x")
    (target / extra_downloads.MARKER).write_text(json.dumps({"version": models.version, "files": names}))
    assert diarize.model_folder() == target


# --- in the recordings routes -------------------------------------------------


@pytest.fixture
def client(app_state, monkeypatch):
    from tessellate.api.app import create_app

    monkeypatch.setattr(voice, "whisper_available", lambda: True)
    monkeypatch.setattr(voice, "transcribe_segments", lambda path, model_size="base": SEGMENTS)
    monkeypatch.setattr(voice, "iter_segments", lambda path, model_size="base": iter(SEGMENTS))
    return TestClient(create_app())


def _recording(client) -> int:
    rid = client.post("/recordings", json={"title": "Launch sync", "mime": "audio/webm"}).json()["id"]
    client.post(f"/recordings/{rid}/chunk", files={"file": ("c.webm", WEBM_HEAD, "audio/webm")}, data={"duration_ms": "4000"})
    client.post(f"/recordings/{rid}/finish", json={"duration_ms": 3_663_000})
    return rid


def test_with_the_extra_absent_the_transcript_is_as_it_was(client) -> None:
    rid = _recording(client)
    body = client.post(f"/recordings/{rid}/transcribe").json()
    assert all(seg["speaker"] is None for seg in body["segments"])
    assert client.get("/voice/status").json()["speakers_by_voice"] is False
    refused = client.post(f"/recordings/{rid}/speakers/voice")
    assert refused.status_code == 503 and "Settings, Packages" in refused.json()["detail"]


def test_a_transcript_made_with_the_extra_carries_speaker_labels(client) -> None:
    diarize.set_runner(lambda path: SPANS)
    rid = _recording(client)
    body = client.post(f"/recordings/{rid}/transcribe").json()
    assert [s["speaker"] for s in body["segments"]] == ["Speaker 1", "Speaker 1", "Speaker 2", "Speaker 2", "Speaker 1"]
    assert client.get(f"/recordings/{rid}/transcript").json()["speakers"] is True
    assert client.get("/voice/status").json()["speakers_by_voice"] is True


def test_the_voice_labels_win_over_the_models_reading_of_the_words(client, fake_ollama) -> None:
    diarize.set_runner(lambda path: SPANS)
    fake_ollama.librarian_reply = "1 | Sam\n2 | Priya\n3 | Sam"
    rid = _recording(client)
    body = client.post(f"/recordings/{rid}/transcribe").json()
    assert {s["speaker"] for s in body["segments"]} == {"Speaker 1", "Speaker 2"}


def test_a_failed_diarizer_leaves_the_transcript_whole(client) -> None:
    def broken(path):
        raise RuntimeError("no")

    diarize.set_runner(broken)
    rid = _recording(client)
    body = client.post(f"/recordings/{rid}/transcribe").json()
    assert len(body["segments"]) == len(SEGMENTS) and all(s["speaker"] is None for s in body["segments"])


def test_the_background_run_labels_speakers_too(client) -> None:
    diarize.set_runner(lambda path: SPANS)
    rid = _recording(client)
    assert client.post(f"/recordings/{rid}/transcribe/start").status_code == 202
    assert recordings.wait_transcription(rid, 10)
    segs = client.get(f"/recordings/{rid}/transcript").json()["segments"]
    assert [s["speaker"] for s in segs] == ["Speaker 1", "Speaker 1", "Speaker 2", "Speaker 2", "Speaker 1"]


def test_an_existing_transcript_can_be_labelled_by_voice_in_the_background(client) -> None:
    rid = _recording(client)
    client.post(f"/recordings/{rid}/transcribe")  # no extra yet: unlabelled
    diarize.set_runner(lambda path: SPANS)
    started = client.post(f"/recordings/{rid}/speakers/voice")
    assert started.status_code == 202 and started.json()["transcription"]["task"] == "voices"
    assert recordings.wait_transcription(rid, 10)
    run = client.get(f"/recordings/{rid}").json()["transcription"]
    assert run["state"] == "done" and run["task"] == "voices" and run["speakers"] == 2
    segs = client.get(f"/recordings/{rid}/transcript").json()["segments"]
    assert [s["speaker"] for s in segs] == ["Speaker 1", "Speaker 1", "Speaker 2", "Speaker 2", "Speaker 1"]


def test_a_run_that_cannot_tell_voices_apart_says_so(client) -> None:
    rid = _recording(client)
    client.post(f"/recordings/{rid}/transcribe")
    diarize.set_runner(lambda path: [(0, 12000, 0)])
    client.post(f"/recordings/{rid}/speakers/voice")
    assert recordings.wait_transcription(rid, 10)
    run = client.get(f"/recordings/{rid}").json()["transcription"]
    assert run["state"] == "done" and run["speakers"] == 0
    assert client.get(f"/recordings/{rid}/transcript").json()["speakers"] is False


def test_a_label_renamed_once_sticks_for_that_recording(client) -> None:
    diarize.set_runner(lambda path: SPANS)
    rid = _recording(client)
    other = _recording(client)
    client.post(f"/recordings/{rid}/transcribe")
    client.post(f"/recordings/{other}/transcribe")
    renamed = client.put(f"/recordings/{rid}/speakers", json={"from_name": "Speaker 2", "to_name": "Priya"})
    assert renamed.status_code == 200
    for _ in range(2):  # read back twice: it is stored, not remembered by the page
        segs = client.get(f"/recordings/{rid}/transcript").json()["segments"]
        assert [s["speaker"] for s in segs] == ["Speaker 1", "Speaker 1", "Priya", "Priya", "Speaker 1"]
    #: The other recording keeps its own labels.
    assert "Priya" not in {s["speaker"] for s in client.get(f"/recordings/{other}/transcript").json()["segments"]}
    #: The names reach the subtitle files.
    assert "<v Priya>" in client.get(f"/recordings/{rid}/transcript.vtt").text


def test_the_text_naming_pass_is_still_there_without_the_extra(client, fake_ollama) -> None:
    fake_ollama.librarian_reply = "1 | Sam\n2 | Priya\n3 | Sam"
    rid = _recording(client)
    body = client.post(f"/recordings/{rid}/transcribe").json()
    assert [s["speaker"] for s in body["segments"]] == ["Sam", "Sam", "Priya", "Priya", "Sam"]
    assert speakers.MAX_PROMPT_CHARS  # the module this one sits beside is unchanged


# --- the page ------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]


def test_the_recordings_view_mounts_the_notice_and_offers_the_action() -> None:
    from tests._app_js import app_js_text

    js = app_js_text()
    assert 'extraNoticeMount($("xn-speakers"), "speakers"' in js
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert html.count('id="xn-speakers"') == 1
    notice = (ROOT / "frontend" / "js" / "extra-notice.js").read_text(encoding="utf-8")
    assert "speakers:" in notice.split("EXTRA_NOTICE_WHAT")[1].split("};")[0]
    assert "Label speakers by voice" in js and "/speakers/voice" in js
