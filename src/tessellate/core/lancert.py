"""The certificate LAN mode serves HTTPS with (the owner, 2026-10-05).

WORLD_CLASS_PLAN 12, "Decisions made", 2: "Yes, self-signed HTTPS". SEC-08 of
the 2026-10-05 audit: LAN mode was plain http, so on shared Wi-Fi a passive
listener read the password at unlock and the seven-day session token after.

- Made on this computer with `cryptography` (already a dependency), never
  fetched: no certificate authority is asked and nothing leaves the machine.
- Made once, at the first LAN start (or when the switch is turned on), and
  reused after that, so a phone that trusted it once is not asked again on
  every launch. It is made again only when asked (Settings, "Regenerate
  certificate"), when an address is not on it (DHCP gave a new one), when it is close to expiring, or when the file cannot be read.
- Kept in the data folder, `lan-tls/`, the folder 0700 and both files 0600:
  the key is the one thing that lets another machine pretend to be this one.
- Its names (the SAN) are this computer's host name, its `.local` name,
  `localhost`, and every address LAN mode lists, so the warning a phone shows
  is "not trusted" and never "the wrong name" as well.
- Its SHA-256 fingerprint is shown in Settings, Other devices: the person
  compares it with what the phone's warning shows before trusting it once.

EC P-256 keeps generation instant and every phone browser speaks it. 825
days is the longest validity Apple's platforms accept for a TLS server
certificate, trusted by hand or not.

**An authority and a server certificate, not one self-signed certificate**
(INBOX 866, "the connection and security issues ... on phone over lan"). A
phone can only be told to trust a certificate authority: iOS lists only
those under Certificate Trust Settings, Android installs only those as a CA
certificate, and Firefox refuses an authority used as a server certificate.
So `ca.pem` is a small authority made here, and `cert.pem` the server
certificate it signs (with the authority after it, the chain a phone checks).
The authority is name constrained to private and link-local addresses, the
`.local` names and this computer's own names, so even a stolen `ca-key.pem`
cannot vouch for a bank's site on a phone that trusts it. A new address
inside those ranges only needs a new server certificate: the phone that
trusted the authority does not have to again.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import ipaddress
import logging
import os
import socket
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

FOLDER = "lan-tls"
CERT_FILE = "cert.pem"
KEY_FILE = "key.pem"
CA_FILE = "ca.pem"
CA_KEY_FILE = "ca-key.pem"
VALID_DAYS = 825
#: The authority outlives many server certificates, so trusting it is rare.
CA_VALID_DAYS = 3650
#: Where the authority may vouch (its name constraints): every private,
#: shared (carrier and Tailscale) and link-local range, and loopback.
PRIVATE_NETS = (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10",
    "169.254.0.0/16", "127.0.0.0/8", "fc00::/7", "fe80::/10", "::1/128",
)
#: Made again this close to the end, so a phone is never met by an expired one.
RENEW_BEFORE = dt.timedelta(days=30)


@dataclass(frozen=True)
class CertInfo:
    cert_path: Path
    key_path: Path
    fingerprint: str
    not_after: dt.datetime
    names: tuple[str, ...]
    #: The authority's fingerprint: what a phone shows when it installs it.
    authority_fingerprint: str = ""

    def public(self) -> dict:
        """What Settings shows: never a path, never the key."""
        return {
            "fingerprint": self.fingerprint,
            "authority_fingerprint": self.authority_fingerprint,
            "expires": self.not_after.date().isoformat(),
            "names": list(self.names),
        }


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def paths(data_dir: Path) -> tuple[Path, Path]:
    folder = Path(data_dir) / FOLDER
    return folder / CERT_FILE, folder / KEY_FILE


def authority_paths(data_dir: Path) -> tuple[Path, Path]:
    folder = Path(data_dir) / FOLDER
    return folder / CA_FILE, folder / CA_KEY_FILE


def default_names(addresses: list[str] | None = None) -> list[str]:
    """This computer's names and the addresses another device would type."""
    names: list[str] = ["localhost", "127.0.0.1", "::1"]
    with contextlib.suppress(OSError):
        host = socket.gethostname().strip().lower()
        if host:
            short = host.split(".", 1)[0]
            names += [host, short, f"{short}.local"]
    if addresses is None:
        from tessellate.core import netbind

        addresses = netbind.lan_addresses(include_v6=True)
    names += list(addresses)
    seen: list[str] = []
    for name in names:
        if name and name not in seen:
            seen.append(name)
    return seen


def _fingerprint(cert) -> str:  # noqa: ANN001  # an x509.Certificate
    from cryptography.hazmat.primitives import hashes

    digest = cert.fingerprint(hashes.SHA256()).hex().upper()
    return ":".join(digest[i : i + 2] for i in range(0, len(digest), 2))


def _san_names(cert) -> tuple[str, ...]:  # noqa: ANN001
    from cryptography import x509

    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return ()
    found = [str(v) for v in san.get_values_for_type(x509.DNSName)]
    found += [str(v) for v in san.get_values_for_type(x509.IPAddress)]
    return tuple(found)


def _not_after(cert) -> dt.datetime:  # noqa: ANN001
    value = getattr(cert, "not_valid_after_utc", None)
    if value is None:  # cryptography before 42
        value = cert.not_valid_after.replace(tzinfo=dt.timezone.utc)
    return value


def _private(path: Path) -> None:
    with contextlib.suppress(OSError, NotImplementedError):
        os.chmod(path, 0o600)


def _write_private(path: Path, data: bytes) -> None:
    """Written 0600 from the first byte (no window where it is readable)."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    _private(path)


def read(data_dir: Path) -> CertInfo | None:
    """The certificate on disk, or None when there is none or it is unreadable."""
    from cryptography import x509

    cert_path, key_path = paths(data_dir)
    if not cert_path.is_file() or not key_path.is_file():
        return None
    try:
        cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    except (OSError, ValueError):
        return None
    authority = _read_authority(data_dir)
    issued = authority is not None and cert.issuer == authority[0].subject and cert.issuer != cert.subject
    return CertInfo(
        cert_path, key_path, _fingerprint(cert), _not_after(cert), _san_names(cert),
        _fingerprint(authority[0]) if issued else "",
    )


def _read_authority(data_dir: Path):  # noqa: ANN202  # (certificate, key) or None
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    ca_path, ca_key_path = authority_paths(data_dir)
    try:
        cert = x509.load_pem_x509_certificate(ca_path.read_bytes())
        key = serialization.load_pem_private_key(ca_key_path.read_bytes(), password=None)
    except (OSError, ValueError, TypeError):
        return None
    return cert, key


def _constraint_trees(names: list[str]):  # noqa: ANN202  # list[x509.GeneralName]
    """The authority's permitted names: the private ranges, `.local`, and
    each name and address this computer has now (a public IPv4 address as a
    single host, a global IPv6 one as its /64, so a computer on one still
    gets a working certificate)."""
    from cryptography import x509

    nets = [ipaddress.ip_network(n) for n in PRIVATE_NETS]
    dns = ["localhost", "local"]
    for name in names:
        try:
            ip = ipaddress.ip_address(name)
        except ValueError:
            if name.lower() not in dns:
                dns.append(name.lower())
            continue
        if not any(ip in net for net in nets):
            # A global IPv6 address rotates within its /64 (privacy
            # addresses), so the network is permitted, not the one address.
            prefix = 64 if ip.version == 6 else 32
            nets.append(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))
    return [x509.DNSName(d) for d in dns] + [x509.IPAddress(n) for n in nets]


def _covers(authority, names: list[str]) -> bool:  # noqa: ANN001  # an x509.Certificate
    """Can this authority vouch for every name? (its name constraints)."""
    from cryptography import x509

    try:
        trees = authority.extensions.get_extension_for_class(x509.NameConstraints).value.permitted_subtrees or []
    except x509.ExtensionNotFound:
        return False
    nets = [t.value for t in trees if isinstance(t, x509.IPAddress)]
    domains = [str(t.value).lower() for t in trees if isinstance(t, x509.DNSName)]
    for name in names:
        try:
            ip = ipaddress.ip_address(name)
        except ValueError:
            low = name.lower()
            if not any(low == d or low.endswith("." + d) for d in domains):
                return False
            continue
        if not any(ip.version == net.version and ip in net for net in nets):
            return False
    return True


def _new_authority(data_dir: Path, names: list[str]):  # noqa: ANN202  # (certificate, key)
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    key = ec.generate_private_key(ec.SECP256R1())
    host = next((n for n in names if n not in ("localhost", "127.0.0.1", "::1")), "this computer")
    # The authority's subject is what a phone that already
    # trusts it shows and what every leaf names as its issuer: it keeps
    # the old name through the rename to Tessellate, so no phone has to
    # install a new authority (rebrand-1011).
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, f"MemoryMap AI on {host}"[:64]),  # brand: keep
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MemoryMap AI on this computer"),  # brand: keep
    ])
    now = _now()
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=CA_VALID_DAYS))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False, content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True,
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.NameConstraints(permitted_subtrees=_constraint_trees(names), excluded_subtrees=None),
                       critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    ca_path, ca_key_path = authority_paths(data_dir)
    _write_private(
        ca_key_path,
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        ),
    )
    _write_private(ca_path, cert.public_bytes(serialization.Encoding.PEM))
    return cert, key


def generate(data_dir: Path, names: list[str] | None = None, *, authority=None) -> CertInfo:  # noqa: ANN001
    """A new server certificate, replacing any there was, signed by
    `authority` (a (certificate, key) pair) or by a new authority made now.
    Settings' "Regenerate certificate" makes both new."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    names = names if names is not None else default_names()
    cert_path, key_path = paths(data_dir)
    cert_path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError, NotImplementedError):
        os.chmod(cert_path.parent, 0o700)
    ca_cert, ca_key = authority if authority is not None else _new_authority(data_dir, names)

    key = ec.generate_private_key(ec.SECP256R1())
    alt: list[x509.GeneralName] = []
    for name in names:
        try:
            alt.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            alt.append(x509.DNSName(name))
    common = next((n for n in names if n not in ("localhost", "127.0.0.1", "::1")), "localhost")
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, common[:64]),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "MemoryMap AI on this computer"),  # brand: keep
    ])
    now = _now()
    not_after = min(now + dt.timedelta(days=VALID_DAYS), _not_after(ca_cert))
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(not_after)
        .add_extension(x509.SubjectAlternativeName(alt), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False, key_encipherment=False,
                data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False,
                encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )
    _write_private(
        key_path,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    #: The chain a phone checks: the server certificate, then its authority.
    _write_private(
        cert_path,
        cert.public_bytes(serialization.Encoding.PEM) + ca_cert.public_bytes(serialization.Encoding.PEM),
    )
    return CertInfo(
        cert_path, key_path, _fingerprint(cert), _not_after(cert), _san_names(cert), _fingerprint(ca_cert)
    )


def authority_pem(data_dir: Path) -> bytes | None:
    """The authority's public certificate, for a phone to install (never a key)."""
    from cryptography.hazmat.primitives import serialization

    authority = _read_authority(data_dir)
    return authority[0].public_bytes(serialization.Encoding.PEM) if authority else None


def _norm(name: str) -> str:
    """One spelling per name, so an IPv6 address compares equal however written."""
    try:
        return str(ipaddress.ip_address(name))
    except ValueError:
        return name.lower()


def missing_names(info: CertInfo, wanted: list[str]) -> list[str]:
    """Names a device could type that the certificate on disk does not carry."""
    have = {_norm(n) for n in info.names}
    return [n for n in wanted if _norm(n) not in have]


def ensure(data_dir: Path, names: list[str] | None = None) -> CertInfo:
    """The certificate to serve: the one on disk while it is good, else a new one.

    Good means unexpired, naming every current address and signed by the
    authority on disk. A DHCP change gives the computer a new address; a
    certificate that does not name it makes the phone report "wrong name"
    (Safari: "connection lost"), so a new one is made. The authority is kept
    while it can vouch for every name, so a phone that trusted it once is
    not asked again; a certificate from before the authority existed (one
    self-signed certificate) is replaced by the pair.
    """
    wanted = names if names is not None else default_names()
    info = read(data_dir)
    authority = _read_authority(data_dir)
    if authority is not None and (
        _not_after(authority[0]) - _now() <= RENEW_BEFORE or not _covers(authority[0], wanted)
    ):
        log.info("LAN certificate authority made again: it could not vouch for every name")
        authority = None
    if info is not None and info.authority_fingerprint and authority is not None \
            and info.authority_fingerprint == _fingerprint(authority[0]) \
            and info.not_after - _now() > RENEW_BEFORE:
        absent = missing_names(info, wanted)
        if not absent:
            #: Every start, not only at creation: a restore, a sync tool or an
            #: older build may have loosened them, and the authority key is
            #: the one that matters most (lansec-1025).
            with contextlib.suppress(OSError, NotImplementedError):
                os.chmod(info.cert_path.parent, 0o700)
            for path in (info.cert_path, info.key_path, *authority_paths(data_dir)):
                _private(path)
            return info
        log.info("LAN certificate made again: it did not name %s", ", ".join(absent))
    return generate(data_dir, wanted, authority=authority)


#: The live HTTPS server's TLS context, so a regenerated certificate takes
#: effect on the next connection without a restart (`reload`).
_live_context = None


def set_live_context(context) -> None:  # noqa: ANN001  # an ssl.SSLContext, or None
    global _live_context
    _live_context = context


def reload(info: CertInfo) -> bool:
    """Hand the running HTTPS server a new certificate; False when none runs."""
    if _live_context is None:
        return False
    _live_context.load_cert_chain(str(info.cert_path), str(info.key_path))
    return True
