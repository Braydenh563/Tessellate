"""The installer is verified before it runs (audit 1031 BK6; 1028 K5).

The update path downloaded an executable and ran it, checked only for a
truncated length and an allowed host. Now the download must match the SHA-256
the release lists for it, and when the app carries a pinned Ed25519 key the
release must also carry a detached signature over that digest. Anything else
is refused before the installer is started, and says so in words."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from tessellate.api import routes_update
from tessellate.core import update_verify

BYTES = b"MZ-the-real-installer"
DIGEST = "sha256:" + hashlib.sha256(BYTES).hexdigest()


def _pair():
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    return private, public


def _sign(private, data: bytes = BYTES) -> bytes:
    return private.sign(hashlib.sha256(data).digest())


@pytest.fixture()
def installer(tmp_path):
    path = tmp_path / "Tessellate-Setup-9.9.9.exe"
    path.write_bytes(BYTES)
    return path


def test_a_matching_digest_passes_without_a_key(installer):
    assert update_verify.refusal(installer, digest=DIGEST, signature=None, keys=()) is None


def test_a_different_file_is_refused(installer):
    installer.write_bytes(BYTES + b"tampered")
    reason = update_verify.refusal(installer, digest=DIGEST, signature=None, keys=())
    assert reason and "does not match" in reason


@pytest.mark.parametrize("digest", [None, "", "md5:abcd", "sha256:", "sha256:zz", 7])
def test_no_usable_digest_and_no_key_is_refused(installer, digest):
    reason = update_verify.refusal(installer, digest=digest, signature=None, keys=())
    assert reason and "could not be checked" in reason


def test_a_pinned_key_requires_a_valid_signature(installer):
    private, public = _pair()
    assert update_verify.refusal(installer, digest=DIGEST, signature=_sign(private), keys=(public,)) is None
    missing = update_verify.refusal(installer, digest=DIGEST, signature=None, keys=(public,))
    assert missing and "signature" in missing
    other, _ = _pair()
    wrong = update_verify.refusal(installer, digest=DIGEST, signature=_sign(other), keys=(public,))
    assert wrong and "signature" in wrong


def test_a_signature_over_another_file_is_refused(installer):
    private, public = _pair()
    reason = update_verify.refusal(installer, digest=None, signature=_sign(private, b"another file"), keys=(public,))
    assert reason and "signature" in reason


def test_any_pinned_key_may_sign_so_a_key_can_be_rotated(installer):
    old, old_public = _pair()
    _, new_public = _pair()
    assert update_verify.refusal(installer, digest=None, signature=_sign(old), keys=(new_public, old_public)) is None


def test_a_malformed_key_or_signature_is_a_refusal_not_a_crash(installer):
    assert update_verify.refusal(installer, digest=None, signature=b"short", keys=("nothex",))
    assert update_verify.refusal(installer, digest=None, signature=b"\0" * 64, keys=("00" * 32,))


def test_the_release_asset_carries_its_digest_and_signature_link():
    release = {
        "assets": [
            {"name": "Tessellate-Setup-9.9.9.exe", "browser_download_url": "https://github.com/x/Tessellate-Setup-9.9.9.exe", "size": 3, "digest": DIGEST},
            {"name": "Tessellate-Setup-9.9.9.exe.sig", "browser_download_url": "https://github.com/x/Tessellate-Setup-9.9.9.exe.sig"},
        ]
    }
    asset = routes_update._windows_asset(release)
    assert asset["digest"] == DIGEST
    assert asset["signature_url"] == "https://github.com/x/Tessellate-Setup-9.9.9.exe.sig"


# --- through the route: nothing is started that did not verify -------------


class _Response:
    def __init__(self, json_body=None, content=b""):
        self._json, self._content = json_body, content
        self.status_code, self.headers, self.is_redirect, self.is_permanent_redirect = 200, {"Content-Length": str(len(content))}, False, False

    def raise_for_status(self):
        pass

    def json(self):
        return self._json

    def iter_content(self, chunk_size=None):
        yield self._content

    def close(self):
        pass


def _apply(client, app_state, monkeypatch, tmp_path, *, digest, served=BYTES, sig_asset=None, keys=()):
    routes_update.reset_for_tests()
    app_state.set_preference("update_check_enabled", True)
    monkeypatch.setattr(routes_update.sys, "platform", "win32")
    monkeypatch.setattr(routes_update.sys, "frozen", True, raising=False)
    monkeypatch.setattr(routes_update.update_verify, "PUBLIC_KEYS", keys)
    assets = [{"name": "Tessellate-Setup-9.9.9.exe", "browser_download_url": "https://github.com/Braydenh563/Tessellate/releases/download/v9.9.9/Tessellate-Setup-9.9.9.exe", "size": len(served), "digest": digest}]
    if sig_asset is not None:
        assets.append({"name": "Tessellate-Setup-9.9.9.exe.sig", "browser_download_url": "https://github.com/Braydenh563/Tessellate/releases/download/v9.9.9/Tessellate-Setup-9.9.9.exe.sig"})
    release = {"tag_name": "v9.9.9", "assets": assets}

    def fake_get(url, **kwargs):
        if "releases/latest" in url:
            return _Response(release)
        return _Response(content=sig_asset if url.endswith(".sig") else served)

    monkeypatch.setattr(routes_update.requests, "get", fake_get)
    launched = []
    monkeypatch.setattr(routes_update.subprocess, "Popen", lambda *a, **k: launched.append(a))
    monkeypatch.setattr(routes_update.tempfile, "mkdtemp", lambda prefix="": str(tmp_path))
    monkeypatch.setattr(routes_update, "EXIT_DELAY_SECONDS", 0)
    exits = []
    monkeypatch.setattr(routes_update.os, "_exit", lambda code: exits.append(code))
    started = client.post("/update/apply")
    assert started.status_code == 200
    deadline = time.time() + 5
    while routes_update.current()["running"] and time.time() < deadline:
        time.sleep(0.02)
    while routes_update.current()["outcome"] == "launched" and not exits and time.time() < deadline:
        time.sleep(0.02)
    return launched, routes_update.current()


def test_a_download_that_does_not_match_its_digest_is_never_started(client, app_state, monkeypatch, tmp_path):
    launched, state = _apply(client, app_state, monkeypatch, tmp_path, digest=DIGEST, served=b"MZ-swapped-in-transit")
    assert launched == []
    assert state["outcome"] == "failed"
    assert "installer" in state["step"].lower()
    assert not (tmp_path / "Tessellate-Setup-9.9.9.exe").exists()


def test_a_release_with_no_digest_is_never_started(client, app_state, monkeypatch, tmp_path):
    launched, state = _apply(client, app_state, monkeypatch, tmp_path, digest=None)
    assert launched == [] and state["outcome"] == "failed"


def test_a_verified_installer_is_started(client, app_state, monkeypatch, tmp_path):
    launched, state = _apply(client, app_state, monkeypatch, tmp_path, digest=DIGEST)
    assert len(launched) == 1 and state["outcome"] == "launched"


def test_with_a_pinned_key_the_signature_file_decides(client, app_state, monkeypatch, tmp_path):
    private, public = _pair()
    launched, state = _apply(client, app_state, monkeypatch, tmp_path, digest=DIGEST, sig_asset=_sign(private), keys=(public,))
    assert len(launched) == 1 and state["outcome"] == "launched"
    other, _ = _pair()
    launched, state = _apply(client, app_state, monkeypatch, tmp_path, digest=DIGEST, sig_asset=_sign(other), keys=(public,))
    assert launched == [] and state["outcome"] == "failed"
    launched, state = _apply(client, app_state, monkeypatch, tmp_path, digest=DIGEST, sig_asset=None, keys=(public,))
    assert launched == [] and state["outcome"] == "failed"


def test_the_release_signature_is_what_the_app_verifies(tmp_path, monkeypatch):
    # packaging/sign_release.py is the release signer (INBOX 1500): what it
    # writes must pass `refusal` under the matching public key, and a release
    # with no key, or a malformed one, must stop rather than ship unsigned.
    import importlib.util

    spec = importlib.util.spec_from_file_location("sign_release", Path(__file__).resolve().parents[1] / "packaging" / "sign_release.py")
    signer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(signer)
    private = Ed25519PrivateKey.generate()
    seed = private.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()).hex()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
    installer = tmp_path / "Tessellate-Setup-9.9.9.exe"
    installer.write_bytes(b"an installer" * 1000)
    monkeypatch.setenv("UPDATE_SIGNING_KEY", seed)
    assert signer.main([str(installer)]) == 0
    signature = (tmp_path / "Tessellate-Setup-9.9.9.exe.sig").read_bytes()
    assert update_verify.refusal(installer, digest=None, signature=signature, keys=(public,)) is None
    monkeypatch.setenv("UPDATE_SIGNING_KEY", "")
    assert signer.main([str(installer)]) == 1
    monkeypatch.setenv("UPDATE_SIGNING_KEY", "not hex")
    assert signer.main([str(installer)]) == 1


def test_the_owners_key_is_pinned_and_the_release_signs_and_uploads_the_signature():
    # Pinned and signing land together: a pinned key with an unsigned release
    # would make every install refuse the next update.
    root = Path(__file__).resolve().parents[1]
    assert update_verify.PUBLIC_KEYS and all(len(bytes.fromhex(k)) == 32 for k in update_verify.PUBLIC_KEYS)
    release = (root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "UPDATE_SIGNING_KEY: ${{ secrets.UPDATE_SIGNING_KEY }}" in release
    assert "python packaging/sign_release.py dist/installer/Tessellate-Setup-*.exe" in release
    assert "dist/installer/Tessellate-Setup-*.exe.sig" in release
    assert release.index("sign_release.py") < release.index("Upload installers to the release")
