"""Where a secret setting lives: the OS keyring, else an owner-only file.

The owner, 2026-11-11 (Q22): API keys go in the operating system's protected
store when one is present, and in a 0600 file otherwise. `preferences.json`
sits in the notebook folder, so a synced folder, a backup tool or another
local account read `llm_api_key` from it in plain text (audit 1028 K11).

The keyring is `pinstore`'s own seam (Windows DPAPI, the macOS Keychain, the
Secret Service), so tests swap one fake in for both (`pinstore.set_store`).
The file lives in `<data>/secrets/`, a 0700 folder holding 0600 files; the
backup bundle names its members one by one and never walks the folder.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from tessellate.core import pinstore

log = logging.getLogger("tessellate.secrets")

#: Settings that are secrets: never written to `preferences.json`.
SECRET_SETTINGS = frozenset({"llm_api_key", "mcp_token"})
_SERVICE_PREFIX = "setting|"


def _account(data_dir: Path, name: str) -> str:
    return _SERVICE_PREFIX + name + "|" + pinstore.account_for(data_dir)


def _file(data_dir: Path, name: str) -> Path:
    return Path(data_dir) / "secrets" / name


def _keyring(data_dir: Path) -> pinstore.Store | None:
    return pinstore.store(data_dir) if pinstore.available(data_dir) else None


def read(data_dir: Path, name: str) -> str:
    """The stored value, or an empty string. Never raises."""
    ring = _keyring(data_dir)
    if ring is not None:
        try:
            value = ring.get(_account(data_dir, name))
            if value:
                return value
        except pinstore.StoreError:
            log.warning("the OS protected store could not be read for %s", name)
    try:
        return _file(data_dir, name).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _write_file(data_dir: Path, name: str, value: str) -> None:
    path = _file(data_dir, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        path.parent.chmod(0o700)
    temp = path.with_suffix(".tmp")
    # 0600 from the first byte, so the value is never world-readable between
    # the write and a later chmod.
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(value)
    os.replace(temp, path)


def write(data_dir: Path, name: str, value: str) -> bool:
    """Keep `value` (empty deletes). True when it is stored somewhere safe;
    False means nothing was written and the caller keeps its own copy."""
    ring = _keyring(data_dir)
    if not value:
        if ring is not None:
            try:
                ring.delete(_account(data_dir, name))
            except pinstore.StoreError:
                log.warning("the OS protected store could not delete %s", name)
        _file(data_dir, name).unlink(missing_ok=True)
        return True
    if ring is not None:
        try:
            ring.put(_account(data_dir, name), value)
            _file(data_dir, name).unlink(missing_ok=True)
            return True
        except pinstore.StoreError:
            log.warning("the OS protected store refused %s; using the owner-only file", name)
    try:
        _write_file(data_dir, name, value)
        return True
    except OSError:
        log.warning("could not store %s", name, exc_info=True)
        return False
