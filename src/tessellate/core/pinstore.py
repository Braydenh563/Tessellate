"""The PIN quick unlock: a second wrap of the vault key, kept by the OS.

The owner, 2026-10-12: the password stays eight characters or more, and a
PIN of 4 to 12 digits may unlock *this computer only*, like Windows Hello.
The bar is "maximum trust": nothing may make a stolen notebook file or
backup easier to crack. So, three rules this module is built around:

- **No PIN material in the notebook.** Not the database, not the data dir,
  not a backup. The record lives in the operating system's protected store
  for the signed-in user: Windows DPAPI, the macOS Keychain, the Secret
  Service through `secret-tool` on Linux. Where none is available a PIN
  cannot be set up, and there is no file fallback: a file next to the
  notebook is exactly what a thief copies.
- **The record is useless without both the OS user and the PIN.** It holds
  the vault's data key under AES-GCM with a key scrypt derives from the PIN
  and a random salt, and its associated data binds it to the vault row and
  password hash it was made against (`binding`), so a restored backup, a
  re-key or a password change leaves it unable to open anything.
- **Five wrong PINs and it is gone.** The count lives in the record itself,
  in the OS store, so restarting the app does not refill it.

A ten-thousand-guess PIN is only as strong as the OS store around it; the
scrypt makes each guess cost, it cannot make four digits a password. That is
why routes_auth takes a PIN only from this computer's own keyboard.

`Store` is the one small interface the OS backends share, so tests swap in
a fake (`set_store`) and never touch a real keyring.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from tessellate.core import crypto
from tessellate.core.subproc import NO_WINDOW

log = logging.getLogger("tessellate.pin")

PIN_PATTERN = re.compile(r"[0-9]{4,12}")
MAX_STRIKES = 5
_SERVICE = "Tessellate PIN"
_AAD_PREFIX = b"tessellate-pin-v1|"
_TIMEOUT = 10  # seconds for one call to the OS store's command line tool


class StoreError(RuntimeError):
    """The OS store refused or failed; the PIN is treated as not there."""


class Store:
    """One record per name in the OS user's protected store."""

    name = "none"

    def available(self) -> bool:
        return False

    def put(self, account: str, secret: str) -> None:
        raise StoreError("no protected store on this computer")

    def get(self, account: str) -> str | None:
        return None

    def delete(self, account: str) -> None:
        return None


def _run(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(  # noqa: S603  # fixed argv, no shell
            args, input=stdin, capture_output=True, text=True, timeout=_TIMEOUT, check=False,
            creationflags=NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise StoreError(str(exc)) from exc


class SecretServiceStore(Store):
    """Linux: the Secret Service (GNOME Keyring, KWallet) via `secret-tool`.
    The secret goes in on stdin, never on the command line."""

    name = "secret-service"

    def __init__(self) -> None:
        self._tool = shutil.which("secret-tool")
        self._ok: bool | None = None

    def available(self) -> bool:
        if self._ok is None:
            ok = False
            if self._tool:
                try:
                    # Exit 1 with nothing on stderr is "no such item": a
                    # working service. No daemon or no bus prints an error.
                    probe = _run([self._tool, "lookup", "service", _SERVICE, "account", "probe"])
                    ok = probe.returncode in (0, 1) and not probe.stderr.strip()
                except StoreError:
                    ok = False
            self._ok = ok
        return self._ok

    def put(self, account: str, secret: str) -> None:
        done = _run(
            [self._tool or "secret-tool", "store", "--label", _SERVICE, "service", _SERVICE, "account", account],
            stdin=secret,
        )
        if done.returncode != 0:
            raise StoreError(done.stderr.strip() or "secret-tool store failed")

    def get(self, account: str) -> str | None:
        done = _run([self._tool or "secret-tool", "lookup", "service", _SERVICE, "account", account])
        if done.returncode != 0:
            return None
        return done.stdout.strip() or None

    def delete(self, account: str) -> None:
        _run([self._tool or "secret-tool", "clear", "service", _SERVICE, "account", account])


class KeychainStore(Store):
    """macOS: the login Keychain via `security`. Written through `security -i`
    so the secret is read from stdin rather than appearing in `ps`."""

    name = "keychain"

    def available(self) -> bool:
        return sys.platform == "darwin" and shutil.which("security") is not None

    def put(self, account: str, secret: str) -> None:
        # Both are base64 or hex text the module made: no quote or newline.
        command = f'add-generic-password -U -s "{_SERVICE}" -a "{account}" -w "{secret}"\n'
        done = _run(["security", "-i"], stdin=command)
        if done.returncode != 0 or self.get(account) != secret:
            raise StoreError(done.stderr.strip() or "security add-generic-password failed")

    def get(self, account: str) -> str | None:
        done = _run(["security", "find-generic-password", "-s", _SERVICE, "-a", account, "-w"])
        return (done.stdout.strip() or None) if done.returncode == 0 else None

    def delete(self, account: str) -> None:
        _run(["security", "delete-generic-password", "-s", _SERVICE, "-a", account])


#: Letters, digits, `_`, `-` and `.`: legal in a file name on every system this runs on.
_SAFE_FILE_NAME = re.compile(r"[A-Za-z0-9_.-]{1,64}")


class DpapiStore(Store):
    """Windows: CryptProtectData, user scope, through ctypes. DPAPI encrypts
    to the signed-in Windows user; the protected bytes are kept under
    %LOCALAPPDATA% (never roamed, never in the notebook's data dir, which is
    under %APPDATA%), and are worthless to any other user or machine."""

    name = "dpapi"

    def __init__(self, notebook_dir: Path | None = None) -> None:
        self._notebook_dir = notebook_dir

    def _dir(self) -> Path | None:
        base = os.getenv("LOCALAPPDATA")
        if not base:
            return None
        folder = Path(base) / "Tessellate" / "pin"
        if self._notebook_dir is not None:
            try:
                folder.resolve().relative_to(Path(self._notebook_dir).resolve())
                return None  # inside the notebook: a backup would carry it
            except ValueError:
                pass
        return folder

    def available(self) -> bool:
        return sys.platform == "win32" and self._dir() is not None

    @staticmethod
    def _crypt(data: bytes, protect: bool) -> bytes:
        import ctypes
        import ctypes.wintypes

        wintypes = ctypes.wintypes

        class Blob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

        crypt32 = ctypes.windll.crypt32  # type: ignore[attr-defined]
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        buffer = ctypes.create_string_buffer(data, len(data))
        source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char)))
        out = Blob()
        ui_forbidden = 0x1  # CRYPTPROTECT_UI_FORBIDDEN
        call = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
        if not call(ctypes.byref(source), None, None, None, None, ui_forbidden, ctypes.byref(out)):
            raise StoreError("DPAPI refused")
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            kernel32.LocalFree(out.pbData)

    @staticmethod
    def _file_name(account: str) -> str:
        """A name Windows accepts. A PIN account is a 32-hex digest and keeps its name, so records
        already on disk still read; any other account (a secret setting's "setting|mcp_token|<id>"
        holds `|`, which Windows refuses: the owner's log, 2026-11-22) is named by its digest.
        Those never reached the disk under their raw name, because the write itself failed."""
        if _SAFE_FILE_NAME.fullmatch(account):
            return f"{account}.bin"
        return "a-" + hashlib.sha256(account.encode()).hexdigest()[:40] + ".bin"

    def put(self, account: str, secret: str) -> None:
        folder = self._dir()
        if folder is None:
            raise StoreError("no place for DPAPI data")
        path = folder / self._file_name(account)
        tmp = path.with_suffix(".tmp")
        try:
            folder.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(self._crypt(secret.encode(), True))
            os.replace(tmp, path)
        except OSError as exc:
            raise StoreError(f"DPAPI data could not be written: {exc}") from exc

    def get(self, account: str) -> str | None:
        folder = self._dir()
        path = folder / self._file_name(account) if folder else None
        if path is None or not path.is_file():
            return None
        try:
            return self._crypt(path.read_bytes(), False).decode()
        except (StoreError, UnicodeDecodeError, OSError):
            return None

    def delete(self, account: str) -> None:
        folder = self._dir()
        if folder is not None:
            (folder / self._file_name(account)).unlink(missing_ok=True)


_store: Store | None = None
_lock = threading.Lock()


def _detect(notebook_dir: Path | None) -> Store:
    if sys.platform == "win32":
        return DpapiStore(notebook_dir)
    if sys.platform == "darwin":
        return KeychainStore()
    return SecretServiceStore()


def store(notebook_dir: Path | None = None) -> Store:
    global _store
    if _store is None:
        _store = _detect(notebook_dir)
    return _store


def set_store(replacement: Store | None) -> None:
    """Tests: a fake store; None goes back to detecting the OS's own."""
    global _store
    _store = replacement


def account_for(data_dir: Path) -> str:
    """One record per notebook on this computer, named by its folder."""
    return hashlib.sha256(str(Path(data_dir).resolve()).encode()).hexdigest()[:32]


def binding(password_hash: str, kdf_salt: bytes, wrapped_dek: bytes) -> bytes:
    """What the record is tied to: the vault row and the password as they are
    now. Any change to either and the record opens nothing."""
    return hashlib.sha256(password_hash.encode() + b"|" + kdf_salt + b"|" + wrapped_dek).digest()


def valid_pin(pin: str) -> bool:
    return bool(PIN_PATTERN.fullmatch(pin or ""))


def _read(account: str, notebook_dir: Path | None) -> dict | None:
    raw = store(notebook_dir).get(account)
    if not raw:
        return None
    try:
        record = json.loads(base64.b64decode(raw, validate=True))
        if record.get("v") != 1:
            return None
        return record
    except (ValueError, TypeError):
        return None


def _write(account: str, record: dict, notebook_dir: Path | None) -> None:
    store(notebook_dir).put(account, base64.b64encode(json.dumps(record).encode()).decode())


def available(notebook_dir: Path | None = None) -> bool:
    try:
        return store(notebook_dir).available()
    except Exception:  # noqa: BLE001  # a broken keyring is "no PIN here", never a 500
        log.warning("the OS protected store could not be reached", exc_info=True)
        return False


def is_set(data_dir: Path) -> bool:
    if not available(data_dir):
        return False
    try:
        return _read(account_for(data_dir), data_dir) is not None
    except StoreError:
        return False


def save(data_dir: Path, pin: str, dek: bytes, bound_to: bytes) -> None:
    """Wrap `dek` under the PIN into the OS store. Raises StoreError."""
    if not valid_pin(pin):
        raise ValueError("a PIN is 4 to 12 digits")
    if not available(data_dir):
        raise StoreError("no protected store on this computer")
    salt = crypto.new_salt()
    nonce = os.urandom(crypto.NONCE_BYTES)
    sealed = AESGCM(crypto.derive_kek(pin, salt)).encrypt(nonce, dek, _AAD_PREFIX + bound_to)
    record = {
        "v": 1,
        "salt": base64.b64encode(salt).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "ct": base64.b64encode(sealed).decode(),
        "fails": 0,
    }
    with _lock:
        account = account_for(data_dir)
        _write(account, record, data_dir)
        if _read(account, data_dir) != record:
            forget(data_dir)
            raise StoreError("the protected store did not keep the PIN")


def forget(data_dir: Path) -> bool:
    """Remove this notebook's PIN record. True when one was there."""
    try:
        if not available(data_dir):
            return False
        account = account_for(data_dir)
        had = _read(account, data_dir) is not None
        store(data_dir).delete(account)
        return had
    except StoreError:
        log.warning("could not remove the PIN from the protected store", exc_info=True)
        return False


def unlock(data_dir: Path, pin: str, bound_to: bytes) -> tuple[str, bytes | None]:
    """("ok", dek), ("wrong", None), ("wiped", None) or ("none", None).

    Every wrong PIN is counted in the record; the fifth deletes it. A record
    that will not decrypt because the vault or password moved on is the same
    as a wrong PIN to whoever is typing, and is spent the same way.
    """
    if not valid_pin(pin) or not available(data_dir):
        return "none", None
    with _lock:
        account = account_for(data_dir)
        try:
            record = _read(account, data_dir)
        except StoreError:
            return "none", None
        if record is None:
            return "none", None
        try:
            salt = base64.b64decode(record["salt"])
            nonce = base64.b64decode(record["nonce"])
            sealed = base64.b64decode(record["ct"])
            dek = AESGCM(crypto.derive_kek(pin, salt)).decrypt(nonce, sealed, _AAD_PREFIX + bound_to)
        except (InvalidTag, KeyError, ValueError, TypeError):
            dek = None
        if dek is not None:
            if record.get("fails"):
                record["fails"] = 0
                try:
                    _write(account, record, data_dir)
                except StoreError:
                    pass  # the count stays high, which only errs towards caution
            return "ok", dek
        try:
            record["fails"] = int(record.get("fails", 0)) + 1
            if record["fails"] >= MAX_STRIKES:
                store(data_dir).delete(account)
                return "wiped", None
            _write(account, record, data_dir)
        except StoreError:
            # A count that cannot be kept is a count that could be reset:
            # refuse the PIN rather than allow unlimited guesses.
            try:
                store(data_dir).delete(account)
            except StoreError:
                pass  # refused below either way; nothing left to undo
            return "wiped", None
        return "wrong", None
