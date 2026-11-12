"""core/webauthn.py on its own: the checks Windows Hello unlock rests on."""

from __future__ import annotations

import hashlib
import json

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from tests._fake_authenticator import FakeAuthenticator, b64url, cbor, unb64url
from tessellate.core import webauthn

ORIGIN = "http://localhost:8000"
RP = "localhost"
CHALLENGE = b"c" * 32


def _registered(device):
    begin = {"rp_id": RP, "create_challenge": b64url(CHALLENGE)}
    made = device.create(begin, ORIGIN)
    return webauthn.verify_registration(
        client_data_json=unb64url(made["client_data_json"]),
        attestation_object=unb64url(made["attestation_object"]),
        credential_id=device.cred_id, challenge=CHALLENGE, origin=ORIGIN, rp_id=RP,
    )


def _verify(device, reg, got, **change):
    args = dict(
        client_data_json=unb64url(got["client_data_json"]),
        authenticator_data=unb64url(got["authenticator_data"]),
        signature=unb64url(got["signature"]),
        challenge=CHALLENGE, origin=ORIGIN, rp_id=RP, alg=reg.alg, spki=reg.spki, sign_count=reg.sign_count,
    )
    args.update(change)
    return webauthn.verify_assertion(**args)


@pytest.mark.parametrize("alg", [webauthn.ES256, webauthn.RS256])
def test_a_registration_and_assertion_round_trip(alg):
    device = FakeAuthenticator(alg=alg)
    reg = _registered(device)
    assert reg.alg == alg and reg.credential_id == device.cred_id
    assert _verify(device, reg, device.get(b64url(CHALLENGE), RP, ORIGIN)) == 2


@pytest.mark.parametrize(
    "change",
    [
        {"challenge": b"d" * 32},
        {"origin": "http://localhost:8001"},
        {"rp_id": "evil.localhost"},
    ],
)
def test_the_wrong_challenge_origin_or_rp_is_refused(change):
    device = FakeAuthenticator()
    reg = _registered(device)
    with pytest.raises(webauthn.WebAuthnError):
        _verify(device, reg, device.get(b64url(CHALLENGE), RP, ORIGIN), **change)


def test_a_create_response_is_not_an_assertion():
    device = FakeAuthenticator()
    reg = _registered(device)
    with pytest.raises(webauthn.WebAuthnError, match="webauthn.get"):
        _verify(device, reg, device.get(b64url(CHALLENGE), RP, ORIGIN, kind="webauthn.create"))


def test_a_cross_origin_frame_is_refused():
    device = FakeAuthenticator()
    reg = _registered(device)
    got = device.get(b64url(CHALLENGE), RP, ORIGIN)
    client = json.loads(unb64url(got["client_data_json"]))
    client["crossOrigin"] = True
    raw = json.dumps(client).encode()
    auth = unb64url(got["authenticator_data"])
    got = {**got, "client_data_json": b64url(raw), "signature": b64url(device.sign(auth + hashlib.sha256(raw).digest()))}
    with pytest.raises(webauthn.WebAuthnError, match="frame"):
        _verify(device, reg, got)


def test_presence_without_verification_is_refused():
    device = FakeAuthenticator()
    reg = _registered(device)
    with pytest.raises(webauthn.WebAuthnError, match="verified"):
        _verify(device, reg, device.get(b64url(CHALLENGE), RP, ORIGIN, flags=0x01))


def test_a_signature_over_other_data_is_refused():
    device = FakeAuthenticator()
    reg = _registered(device)
    got = device.get(b64url(CHALLENGE), RP, ORIGIN)
    other = device.get(b64url(CHALLENGE), RP, ORIGIN)
    with pytest.raises(webauthn.WebAuthnError):
        _verify(device, reg, {**got, "signature": other["signature"]})


def test_an_rsa_key_under_2048_bits_is_refused():
    small = rsa.generate_private_key(public_exponent=65537, key_size=1024).public_key().public_numbers()
    with pytest.raises(webauthn.WebAuthnError, match="2048"):
        webauthn.cose_to_spki({1: 3, 3: -257, -1: small.n.to_bytes(128, "big"), -2: b"\x01\x00\x01"})


def test_an_unsupported_algorithm_is_refused():
    with pytest.raises(webauthn.WebAuthnError, match="ES256"):
        webauthn.cose_to_spki({1: 1, 3: -8, -1: 6, -2: b"x" * 32})


def test_the_cbor_reader_round_trips_and_refuses_what_webauthn_never_sends():
    value = {1: 2, -1: b"\x00" * 40, "fmt": "none", "list": [True, False, None, 300, -500]}
    assert webauthn.cbor_decode(cbor(value)) == (value, len(cbor(value)))
    for bad in (b"\x5f", b"\x9f", b"\x58\x10abc", b"\xf9\x00\x00", b""):
        with pytest.raises(webauthn.WebAuthnError):
            webauthn.cbor_decode(bad)
    deep = b"\x81" * 20 + b"\x00"
    with pytest.raises(webauthn.WebAuthnError, match="deep"):
        webauthn.cbor_decode(deep)


def test_a_registration_naming_another_credential_is_refused():
    device = FakeAuthenticator()
    made = device.create({"rp_id": RP, "create_challenge": b64url(CHALLENGE)}, ORIGIN)
    with pytest.raises(webauthn.WebAuthnError, match="credential id"):
        webauthn.verify_registration(
            client_data_json=unb64url(made["client_data_json"]),
            attestation_object=unb64url(made["attestation_object"]),
            credential_id=b"someone else", challenge=CHALLENGE, origin=ORIGIN, rp_id=RP,
        )
