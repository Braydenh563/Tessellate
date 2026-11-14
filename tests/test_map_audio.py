"""An audio note on a map topic (MINDMAP_PLAN gap 4), decided 2026-11-10: a
recording is its own object (WORLD_CLASS_PLAN "Audio in the notebook",
decision 2), so a topic holds a link to an existing recording, picked from the
Library's recordings, and never raw audio. No upload route, no new media type."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_mindmap import _map, _node, _set_data, _styles_by_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
MAP = (JS / "whiteboard-map.js").read_text(encoding="utf-8")
AUDIO = (JS / "whiteboard-map-more.js").read_text(encoding="utf-8")


def test_a_topic_holds_a_recording_id_checked_and_kept_by_a_look_reset(client):
    board = _map(client, name="Audio")
    root = _node(client, board["id"], text="Plan")
    node = _node(client, board["id"], parent_id=root["id"], text="Interview")
    for bad in (0, -3, "7", 1.5, "a recording"):
        response = _set_data(client, board, node, {"recording": bad})
        assert response.status_code == 422, bad
    response = _set_data(client, board, node, {"recording": 7})
    assert response.status_code == 200
    assert _styles_by_text(client, board["id"])["Interview"]["recording"] == 7
    client.post(f"/whiteboard/boards/{board['id']}/nodes/clear-style")
    assert _styles_by_text(client, board["id"])["Interview"]["recording"] == 7
    response = _set_data(client, board, node, {"recording": None})
    assert response.status_code == 200


def test_no_upload_route_takes_audio_for_a_topic():
    from tessellate.api.routes_files import MEDIA_SUFFIXES, VIDEO_TYPES

    # .webm is also the video container a document embeds since L-documents-68,
    # and it is served as video/webm, never as an audio type; the audio-only
    # suffixes stay out, and the map topic still uploads nothing.
    assert not {".wav", ".mp3", ".m4a", ".ogg", ".oga", ".opus", ".flac", ".aac"} & set(MEDIA_SUFFIXES)
    assert VIDEO_TYPES[".webm"] == "video/webm"
    assert "/media/upload" not in AUDIO and "FormData" not in AUDIO


def _run(body: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    start = AUDIO.index("function wbAudioLength(")
    end = AUDIO.index("function wbAudioRows(")
    end = AUDIO.index("\n  }\n", end) + 5
    script = AUDIO[start:end].replace("\n  ", "\n") + body
    return json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)


def test_the_picker_rows_name_a_recording_by_its_title_and_length():
    out = _run(
        "const rows=wbAudioRows([{id:4,title:'Kiln call',duration_ms:72000,created_at:'2026-11-03T10:00:00'},"
        "{id:5,title:'',duration_ms:null,created_at:null},"
        "{id:6,title:'Budget',duration_ms:3725000,created_at:'2026-10-01T09:00:00'}],'bud');"
        "const all=wbAudioRows([{id:4,title:'Kiln call',duration_ms:72000,created_at:'2026-11-03T10:00:00'},"
        "{id:5,title:'',duration_ms:null,created_at:null}],'');"
        "console.log(JSON.stringify({rows:rows.map(r=>[r.value,r.label,r.about]),"
        "all:all.map(r=>[r.value,r.label,r.about]),len:[wbAudioLength(0),wbAudioLength(59999),wbAudioLength(72000),wbAudioLength(3725000)]}));"
    )
    assert out["rows"] == [[6, "Budget", "1:02:05"]]
    assert out["all"] == [[4, "Kiln call", "1:12"], [5, "Untitled recording", ""]]
    assert out["len"] == ["0:00", "0:59", "1:12", "1:02:05"]


def test_the_link_is_set_cleared_and_undone_through_the_one_style_writer():
    assert "wbMapSetNodeStyle(live, { recording: id })" in AUDIO
    assert "wbMapSetNodeStyle(live, { recording: null })" in AUDIO
    assert "preload = \"none\"" in AUDIO and "/media/recordings/" in AUDIO
    keys = MAP[MAP.index("const WB_MAP_CONTENT_KEYS = [") :].split("];", 1)[0]
    assert '"recording"' in keys
    assert "wbMapLazy.paintAudio(" in MAP
    for words in ("Audio note: pick a recording", "Play the audio note", "Remove the audio note"):
        assert words in MAP, words
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert "whiteboard-map-audio.js" not in app  # one lazy file for both, one path in the boot script's list
