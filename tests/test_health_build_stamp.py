"""/health says which build is running and whether its folder can be written.

L-general-6: a person who reports "it does not save" or "I updated but nothing
changed" can be asked for the build line instead of a guess. The commit comes
from the environment or a stamp file when there is no git checkout (the
packaged app), and the data directory is named by its hash, never its path.
"""

from __future__ import annotations

import os

from tessellate.core import build_stamp


def test_the_commit_comes_from_the_environment_first(monkeypatch):
    monkeypatch.setenv("TESSELLATE_SOURCE_COMMIT", "abcdef1234567890")
    build_stamp.source_commit.cache_clear()
    assert build_stamp.source_commit() == "abcdef123456"


def test_a_stamp_file_stands_in_when_there_is_no_git(monkeypatch, tmp_path):
    monkeypatch.delenv("TESSELLATE_SOURCE_COMMIT", raising=False)
    stamp = tmp_path / "SOURCE_COMMIT"
    stamp.write_text("0123456789abcdef\n", encoding="utf-8")
    monkeypatch.setattr(build_stamp, "_STAMP_FILES", (stamp,))
    build_stamp.source_commit.cache_clear()
    assert build_stamp.source_commit() == "0123456789ab"


def test_no_source_at_all_is_an_empty_string_not_an_error(monkeypatch, tmp_path):
    monkeypatch.delenv("TESSELLATE_SOURCE_COMMIT", raising=False)
    monkeypatch.setattr(build_stamp, "_STAMP_FILES", (tmp_path / "missing",))
    monkeypatch.setattr(build_stamp, "_git_head", lambda: "")
    build_stamp.source_commit.cache_clear()
    assert build_stamp.source_commit() == ""


def test_writable_is_true_for_a_folder_and_false_for_a_missing_one(tmp_path):
    assert build_stamp.data_dir_writable(tmp_path) is True
    assert build_stamp.data_dir_writable(tmp_path / "gone") is False
    if os.name != "nt" and os.geteuid() != 0:
        tmp_path.chmod(0o500)
        try:
            assert build_stamp.data_dir_writable(tmp_path) is False
        finally:
            tmp_path.chmod(0o700)


def test_health_carries_the_stamp(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert isinstance(body["data_dir_writable"], bool)
    assert len(body["data_dir_id"]) >= 8 and "/" not in body["data_dir_id"]
    assert body["started_at"].endswith("Z")
    assert isinstance(body["source_commit"], str)


def test_about_shows_the_build_and_a_folder_that_cannot_be_written():
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
    fill = js[js.index('const aboutHealth = await apiJson("/health")') :][:1400]
    assert "source_commit" in fill and "data_dir_writable" in fill


_BUILD = {"source_commit", "started_at", "data_dir_id", "data_dir_writable"}


def test_another_device_gets_the_stamp_only_when_signed_in(client, monkeypatch):
    """Source text: review (/health): the open route told any device on the LAN
    which commit runs, since when, and which folder; they go only to this
    computer or a signed-in session, and the LAN gets the old body."""
    from tessellate.core import security

    monkeypatch.setattr(security, "_session_is_live", lambda token: token == "live")
    lan = {"X-Forwarded-For": "192.168.1.20"}
    assert not _BUILD & client.get("/health", headers=lan).json().keys()
    assert not _BUILD & client.get("/health", headers={**lan, "X-Auth-Token": "stale"}).json().keys()
    assert _BUILD <= client.get("/health", headers={**lan, "X-Auth-Token": "live"}).json().keys()
    assert client.get("/health", headers=lan).json()["status"] == "ok"
