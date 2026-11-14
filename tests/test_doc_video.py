"""L-documents-68: a video in a document, played from this app's own origin.

`![name](/media/x.mp4)` is a `<video controls preload="metadata">` in Read and
Live; the upload takes MP4 and WebM only, by what the bytes open with, and the
server answers a Range request with 206 so a seek does not refetch the file.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + bytes(range(256)) * 8
WEBM = b"\x1a\x45\xdf\xa3" + bytes(range(256)) * 8


def _upload(client, name, data):
    return client.post("/media/upload", files={"file": (name, data, "application/octet-stream")})


def test_mp4_and_webm_upload_and_are_served_inline_with_their_own_type(ai_client):
    for name, data, mime in (("a.mp4", MP4, "video/mp4"), ("a.webm", WEBM, "video/webm")):
        made = _upload(ai_client, name, data)
        assert made.status_code == 200, made.text
        served = ai_client.get(made.json()["url"])
        assert served.status_code == 200 and served.content == data
        assert served.headers["content-type"].startswith(mime)
        assert served.headers["content-disposition"].startswith("inline")


def test_a_range_request_is_answered_with_206_and_only_those_bytes(ai_client):
    url = _upload(ai_client, "seek.mp4", MP4).json()["url"]
    part = ai_client.get(url, headers={"Range": "bytes=100-199"})
    assert part.status_code == 206
    assert part.content == MP4[100:200]
    assert part.headers["content-range"] == f"bytes 100-199/{len(MP4)}"
    assert ai_client.get(url).headers["accept-ranges"] == "bytes"


def test_text_named_like_a_video_is_refused(ai_client):
    for name in ("x.mp4", "x.webm"):
        refused = _upload(ai_client, name, b"<html>not a video</html>" + b"x" * 40)
        assert refused.status_code == 415
        assert "not a video" in refused.json()["detail"]


def test_other_video_types_stay_out(ai_client):
    assert _upload(ai_client, "x.mov", MP4).status_code == 415
    assert _upload(ai_client, "x.avi", MP4).status_code == 415


def test_the_page_policy_lets_video_play_from_this_origin_only():
    from tessellate.core import security

    policy = security.build_csp([])
    assert "media-src 'self' blob:" in policy
    assert "media-src 'self' http" not in policy


def test_the_picker_offers_video_and_both_views_draw_a_player():
    js = "\n".join(
        (ROOT / "frontend" / "js" / name).read_text(encoding="utf-8")
        for name in ("documents.js", "documents-cm.js", "image-layout.js", "notes-list.js")
    )
    assert 'input.accept = "image/*,video/mp4,video/webm,.mp4,.webm"' in js
    assert 'player.preload = "metadata"' in js and "player.controls = true" in js
    assert "imageLayout.isVideo(this.src)" in js, "Live draws it"
    assert "window.imageLayout?.isVideo(imageUrl)" in js, "Read draws it"
    assert '.querySelector(".doc-video-name")' in js, "an export keeps its name"
    print_css = (ROOT / "frontend" / "css" / "09-editor.css").read_text(encoding="utf-8")
    assert "#doc-preview .doc-video video {\n    display: none;" in print_css
