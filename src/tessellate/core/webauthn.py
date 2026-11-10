"""The small part of WebAuthn that Windows Hello unlock needs (INBOX 1727).

Two checks, done here with `cryptography` rather than a WebAuthn library
(none is a dependency, and the subset is small enough to read whole):

- `verify_registration`: a new platform credential. The client data says
  `webauthn.create`, carries our challenge and our origin; the authenticator
  data is for our RP id, the person was present and verified, and the
  attested credential is the one the browser named. The attestation
  statement is not checked: the page asks for `attestation: "none"`, and the
  person enrolling has just typed the password on this computer, so there is
  no vendor whose word would add anything.
- `verify_assertion`: an unlock. The same client data and flag checks for
  `webauthn.get`, then the signature over `authData || SHA-256(clientData)`
  with the key stored at registration, and a sign count that only grows
  (where the authenticator keeps one; Windows Hello often sends 0).

Only ES256 (COSE -7, P-256) and RS256 (COSE -257) are accepted: the two that
Windows Hello and every platform authenticator offer. The CBOR reader takes
the definite-length subset CTAP2's canonical encoding uses and nothing more.
Every failure is a `WebAuthnError` with a reason for the log, never the
caller's own words back.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import struct
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa

ES256 = -7
RS256 = -257
ALGORITHMS = (ES256, RS256)

_UP = 0x01  # user present
_UV = 0x04  # user verified (Windows Hello's face, finger or PIN)
_AT = 0x40  # attested credential data follows
_MAX_DEPTH = 8


class WebAuthnError(ValueError):
    """The response does not prove what it claims."""


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64url(text: str) -> bytes:
    if not isinstance(text, str) or len(text) > 65536:
        raise WebAuthnError("not base64url text")
    try:
        return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
    except (ValueError, TypeError) as exc:
        raise WebAuthnError("not base64url") from exc


# --- CBOR, the definite-length subset ------------------------------------------


def _head(data: bytes, at: int) -> tuple[int, int, int, int]:
    """(major type, additional info, argument, offset after the head)."""
    if at >= len(data):
        raise WebAuthnError("CBOR cut short")
    major, info = data[at] >> 5, data[at] & 0x1F
    at += 1
    if info < 24:
        return major, info, info, at
    if info not in (24, 25, 26, 27):
        raise WebAuthnError("CBOR indefinite length")
    size = 1 << (info - 24)
    if at + size > len(data):
        raise WebAuthnError("CBOR cut short")
    return major, info, int.from_bytes(data[at : at + size], "big"), at + size


def _string(data: bytes, at: int, size: int, text: bool):  # noqa: ANN202  # bytes | str
    if at + size > len(data):
        raise WebAuthnError("CBOR cut short")
    raw = data[at : at + size]
    try:
        return (raw.decode("utf-8") if text else bytes(raw)), at + size
    except UnicodeDecodeError as exc:
        raise WebAuthnError("CBOR text is not UTF-8") from exc


def _map(data: bytes, at: int, count: int, depth: int) -> tuple[dict, int]:
    out = {}
    for _ in range(count):
        key, at = _cbor(data, at, depth + 1)
        if isinstance(key, (list, dict)):
            raise WebAuthnError("CBOR map key is not a scalar")
        out[key], at = _cbor(data, at, depth + 1)
    return out, at


def _cbor(data: bytes, at: int, depth: int):  # noqa: ANN202  # any CBOR value
    if depth > _MAX_DEPTH:
        raise WebAuthnError("CBOR nested too deep")
    major, info, arg, at = _head(data, at)
    if major == 0:
        return arg, at
    if major == 1:
        return -1 - arg, at
    if major in (2, 3):
        return _string(data, at, arg, major == 3)
    if major == 4:
        items = []
        for _ in range(arg):
            item, at = _cbor(data, at, depth + 1)
            items.append(item)
        return items, at
    if major == 5:
        return _map(data, at, arg, depth)
    if major == 7 and info in (20, 21, 22):
        return {20: False, 21: True, 22: None}[info], at
    raise WebAuthnError("CBOR type not used by WebAuthn")


def cbor_decode(data: bytes, at: int = 0) -> tuple[object, int]:
    """One CBOR item from `data` at `at`: (value, offset after it)."""
    return _cbor(bytes(data), at, 0)


# --- keys ----------------------------------------------------------------------


def cose_to_spki(cose: dict) -> tuple[int, bytes]:
    """(algorithm, SubjectPublicKeyInfo DER) for an ES256 or RS256 COSE key."""
    alg = cose.get(3)
    if alg == ES256 and cose.get(1) == 2 and cose.get(-1) == 1:
        x, y = cose.get(-2), cose.get(-3)
        if not (isinstance(x, bytes) and isinstance(y, bytes) and len(x) == len(y) == 32):
            raise WebAuthnError("EC2 key is not P-256")
        try:
            key = ec.EllipticCurvePublicNumbers(
                int.from_bytes(x, "big"), int.from_bytes(y, "big"), ec.SECP256R1()
            ).public_key()
        except ValueError as exc:
            raise WebAuthnError("EC2 point is not on the curve") from exc
    elif alg == RS256 and cose.get(1) == 3:
        n, e = cose.get(-1), cose.get(-2)
        if not (isinstance(n, bytes) and isinstance(e, bytes) and len(n) >= 256):
            raise WebAuthnError("RSA key is under 2048 bits")
        key = rsa.RSAPublicNumbers(int.from_bytes(e, "big"), int.from_bytes(n, "big")).public_key()
    else:
        raise WebAuthnError("key algorithm is not ES256 or RS256")
    spki = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return alg, spki


def _verify_signature(alg: int, spki: bytes, signature: bytes, signed: bytes) -> None:
    try:
        key = serialization.load_der_public_key(spki)
        if alg == ES256 and isinstance(key, ec.EllipticCurvePublicKey):
            key.verify(signature, signed, ec.ECDSA(hashes.SHA256()))
        elif alg == RS256 and isinstance(key, rsa.RSAPublicKey):
            key.verify(signature, signed, padding.PKCS1v15(), hashes.SHA256())
        else:
            raise WebAuthnError("stored key does not match its algorithm")
    except InvalidSignature as exc:
        raise WebAuthnError("signature does not verify") from exc
    except (ValueError, TypeError) as exc:
        raise WebAuthnError("signature or key is malformed") from exc


# --- the two ceremonies --------------------------------------------------------


@dataclass(frozen=True)
class AuthData:
    rp_id_hash: bytes
    flags: int
    sign_count: int
    credential_id: bytes | None = None
    cose_key: dict | None = None


def parse_auth_data(raw: bytes) -> AuthData:
    if len(raw) < 37:
        raise WebAuthnError("authenticator data is too short")
    rp_id_hash, flags = raw[:32], raw[32]
    (count,) = struct.unpack(">I", raw[33:37])
    if not flags & _AT:
        return AuthData(rp_id_hash, flags, count)
    if len(raw) < 55:
        raise WebAuthnError("attested credential data is too short")
    (id_len,) = struct.unpack(">H", raw[53:55])
    if len(raw) < 55 + id_len:
        raise WebAuthnError("credential id is cut short")
    cred_id = raw[55 : 55 + id_len]
    cose, _ = cbor_decode(raw, 55 + id_len)
    if not isinstance(cose, dict):
        raise WebAuthnError("credential key is not a COSE map")
    return AuthData(rp_id_hash, flags, count, cred_id, cose)


def _check_client_data(raw: bytes, kind: str, challenge: bytes, origin: str) -> None:
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise WebAuthnError("client data is not JSON") from exc
    if not isinstance(data, dict) or data.get("type") != kind:
        raise WebAuthnError(f"client data is not {kind}")
    if not hmac.compare_digest(unb64url(str(data.get("challenge", ""))), challenge):
        raise WebAuthnError("challenge does not match")
    if data.get("origin") != origin:
        raise WebAuthnError("origin does not match")
    if data.get("crossOrigin"):
        raise WebAuthnError("asked from inside another site's frame")


def _check_flags(auth: AuthData, rp_id: str) -> None:
    if not hmac.compare_digest(auth.rp_id_hash, hashlib.sha256(rp_id.encode()).digest()):
        raise WebAuthnError("RP id does not match")
    if not auth.flags & _UP or not auth.flags & _UV:
        raise WebAuthnError("the person was not verified")


@dataclass(frozen=True)
class Registered:
    credential_id: bytes
    alg: int
    spki: bytes
    sign_count: int


def verify_registration(
    *, client_data_json: bytes, attestation_object: bytes, credential_id: bytes,
    challenge: bytes, origin: str, rp_id: str,
) -> Registered:
    _check_client_data(client_data_json, "webauthn.create", challenge, origin)
    attestation, _ = cbor_decode(attestation_object)
    if not isinstance(attestation, dict) or not isinstance(attestation.get("authData"), bytes):
        raise WebAuthnError("attestation object has no authenticator data")
    auth = parse_auth_data(attestation["authData"])
    _check_flags(auth, rp_id)
    if auth.credential_id is None or auth.cose_key is None:
        raise WebAuthnError("no attested credential")
    if not hmac.compare_digest(auth.credential_id, credential_id):
        raise WebAuthnError("credential id does not match the attested one")
    alg, spki = cose_to_spki(auth.cose_key)
    return Registered(auth.credential_id, alg, spki, auth.sign_count)


def verify_assertion(
    *, client_data_json: bytes, authenticator_data: bytes, signature: bytes,
    challenge: bytes, origin: str, rp_id: str, alg: int, spki: bytes, sign_count: int,
) -> int:
    """The new sign count after a valid assertion; WebAuthnError otherwise."""
    _check_client_data(client_data_json, "webauthn.get", challenge, origin)
    auth = parse_auth_data(authenticator_data)
    _check_flags(auth, rp_id)
    signed = bytes(authenticator_data) + hashlib.sha256(client_data_json).digest()
    _verify_signature(alg, spki, signature, signed)
    if (auth.sign_count or sign_count) and auth.sign_count <= sign_count:
        raise WebAuthnError("sign count went backwards: a cloned authenticator")
    return auth.sign_count
