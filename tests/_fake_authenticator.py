"""A platform authenticator in Python for the Windows Hello tests (INBOX 1727).

It makes real ES256 or RS256 credentials, real CBOR attestation objects and
real signatures, and answers the PRF extension the way CTAP2's hmac-secret
does (an HMAC of the salt under a per-credential secret), so the server's
checks in core/webauthn.py run against the bytes a browser would send.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64url(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def cbor(value) -> bytes:  # noqa: ANN001
    def head(major: int, arg: int) -> bytes:
        if arg < 24:
            return bytes([major << 5 | arg])
        for info, size in ((24, 1), (25, 2), (26, 4), (27, 8)):
            if arg < 1 << (8 * size):
                return bytes([major << 5 | info]) + arg.to_bytes(size, "big")
        raise ValueError(arg)

    if value is None:
        return bytes([0xF6])
    if isinstance(value, bool):
        return bytes([0xF5 if value else 0xF4])
    if isinstance(value, int):
        return head(0, value) if value >= 0 else head(1, -1 - value)
    if isinstance(value, bytes):
        return head(2, len(value)) + value
    if isinstance(value, str):
        raw = value.encode()
        return head(3, len(raw)) + raw
    if isinstance(value, list):
        return head(4, len(value)) + b"".join(cbor(v) for v in value)
    if isinstance(value, dict):
        return head(5, len(value)) + b"".join(cbor(k) + cbor(v) for k, v in value.items())
    raise TypeError(type(value))


class FakeAuthenticator:
    def __init__(self, alg: int = -7, counts: bool = True) -> None:
        self.alg = alg
        self.counts = counts
        self.count = 0
        self.cred_id = os.urandom(16)
        self.prf_secret = os.urandom(32)
        if alg == -7:
            self.key = ec.generate_private_key(ec.SECP256R1())
        else:
            self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def cose(self) -> dict:
        pub = self.key.public_key().public_numbers()
        if self.alg == -7:
            return {1: 2, 3: -7, -1: 1, -2: pub.x.to_bytes(32, "big"), -3: pub.y.to_bytes(32, "big")}
        return {1: 3, 3: -257, -1: pub.n.to_bytes(256, "big"), -2: pub.e.to_bytes(3, "big")}

    def prf(self, salt: bytes) -> bytes:
        return hmac.new(self.prf_secret, salt, hashlib.sha256).digest()

    def _flags_count(self, flags: int) -> bytes:
        if self.counts:
            self.count += 1
        return bytes([flags]) + struct.pack(">I", self.count if self.counts else 0)

    @staticmethod
    def client_data(kind: str, challenge: str, origin: str, **extra) -> bytes:  # noqa: ANN003
        return json.dumps({"type": kind, "challenge": challenge, "origin": origin, "crossOrigin": False, **extra}).encode()

    def create(self, begin: dict, origin: str, *, rp_id: str | None = None, flags: int = 0x45) -> dict:
        rp = rp_id or begin["rp_id"]
        auth = (
            hashlib.sha256(rp.encode()).digest()
            + self._flags_count(flags)
            + bytes(16)
            + struct.pack(">H", len(self.cred_id))
            + self.cred_id
            + cbor(self.cose())
        )
        attestation = cbor({"fmt": "none", "attStmt": {}, "authData": auth})
        return {
            "credential_id": b64url(self.cred_id),
            "client_data_json": b64url(self.client_data("webauthn.create", begin["create_challenge"], origin)),
            "attestation_object": b64url(attestation),
        }

    def sign(self, data: bytes) -> bytes:
        if self.alg == -7:
            return self.key.sign(data, ec.ECDSA(hashes.SHA256()))
        return self.key.sign(data, padding.PKCS1v15(), hashes.SHA256())

    def get(self, challenge: str, rp_id: str, origin: str, *, flags: int = 0x05, kind: str = "webauthn.get") -> dict:
        auth = hashlib.sha256(rp_id.encode()).digest() + self._flags_count(flags)
        client = self.client_data(kind, challenge, origin)
        return {
            "credential_id": b64url(self.cred_id),
            "client_data_json": b64url(client),
            "authenticator_data": b64url(auth),
            "signature": b64url(self.sign(auth + hashlib.sha256(client).digest())),
        }
