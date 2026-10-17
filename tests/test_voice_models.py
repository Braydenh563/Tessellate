"""Which dictation sizes are on this computer, and removing one (B61).

The owner (INBOX 904 B61): "there is no indication for which ones are
installed ... if I click a different dictation model size, does it download
immediately? ... can I delete or uninstall models". Nothing said; choosing a
size only saved a preference and the download happened at the first
dictation. The cache is Hugging Face's:
`models--Systran--faster-whisper-<size>`.
"""

from __future__ import annotations


def _fake_whisper_cache(root, size, *, weights=True):
    snap = root / f"models--Systran--faster-whisper-{size}" / "snapshots" / "abc123"
    snap.mkdir(parents=True)
    (snap / "config.json").write_text("{}")
    if weights:
        (snap / "model.bin").write_bytes(b"x" * 2048)
    return snap.parent.parent


def test_status_says_which_sizes_are_downloaded(client, monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    _fake_whisper_cache(tmp_path, "small")
    _fake_whisper_cache(tmp_path, "tiny", weights=False)  # an interrupted download is not installed
    models = client.get("/voice/status").json()["models"]
    assert set(models) == {"tiny", "base", "small", "medium"}
    assert models["small"]["installed"] is True and models["small"]["bytes"] >= 2048
    assert models["tiny"]["installed"] is False and models["base"]["installed"] is False
    assert models["medium"]["approx"].endswith("GB") and models["tiny"]["approx"].endswith("MB")


def test_a_downloaded_size_can_be_removed_and_nothing_else(client, monkeypatch, tmp_path):
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path))
    folder = _fake_whisper_cache(tmp_path, "small")
    bystander = tmp_path / "models--someone--else"
    bystander.mkdir()
    done = client.delete("/voice/models/small")
    assert done.status_code == 200 and done.json()["removed"] is True
    assert not folder.exists()
    assert bystander.exists()
    gone = client.delete("/voice/models/small")  # already gone
    assert gone.status_code == 404
    huge = client.delete("/voice/models/huge")  # not a size we offer
    assert huge.status_code == 404
