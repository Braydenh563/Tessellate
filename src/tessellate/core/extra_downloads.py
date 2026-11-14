"""The second kind of optional extra: a pinned download (INBOX 404, 302).

The owner, 2026-09-24, on two decisions the repository read and the code
editor's Run button had left open: "Run Python files: yes, as an opt-in
extra" and, for needle, "Yes, as an extra". Neither one is a pip package.
Pyodide is a WebAssembly build of CPython that runs in the browser, shipped
as a release archive; needle is a native engine and a weights file on
Hugging Face. `core/extras.py` installed pip packages only, so this is the
other kind, behind the same routes, the same Settings row and the same
one-at-a-time state.

**What an entry is.** A `Download` is a URL, the file's sha256 and its size,
all written down in `extras.py` beside the entry, and an unpack step: the
file as it is, or named members out of a tar or zip archive, each written to
a name the entry chose. Nothing about it is looked up at run time, which is
the same property the pip allowlist has: the request picks an entry, never a
URL.

**The properties, each tested in `tests/test_extras_download.py`:**

- **Network only on the install click.** Nothing here runs at start-up or on
  a status read; `status` is a look at a folder on disk. Once installed the
  files are served from the data dir and nothing asks again.
- **The hash is the gate.** A file is streamed to a staging folder while it
  is hashed, and a file whose sha256 is not the pinned one is deleted and the
  install fails, with nothing of it kept. A file that grows past its pinned
  size is cut off rather than read to the end, so a wrong URL cannot fill a
  disk before the hash gets a say.
- **An archive cannot choose where its files go.** Only the members the entry
  names are read, each through `extractfile`/`open` into a name that is a
  plain file name (checked when the `Download` is built), so a `../` in an
  archive has nowhere to go; `extractall` is never called.
- **All or nothing.** Every download lands and is checked in the staging
  folder first; only then is the folder moved into place, with a marker file
  that records the version. A cancelled or failed install leaves the
  previous state as it was.
- **A native engine is read before it is kept** (INBOX 699). An entry that
  marks a download `inspect_imports` has the file's imported symbols read
  (`core/native_imports.py`: ELF, PE, Mach-O, pure Python, nothing loaded or
  run); one that imports a socket, name-lookup or HTTP call, or cannot be
  read at all, fails the install with nothing kept.
- **HTTPS only**, except for a loopback address, which is what the tests'
  fake file server and a local mirror use.
"""

from __future__ import annotations

import gzip
import hashlib
import ipaddress
import json
import os
import platform as _platform
import re
import shutil
import sys
import tarfile
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from tessellate.core import egress


#: The file that says an install finished, and which version it was.
MARKER = "installed.json"

#: A written name: a plain file name, nothing that could be a path.
_NAME_RE = re.compile(r"[A-Za-z0-9._-]+")
#: One path part inside a tree: Java inner classes carry a `$`.
_TREE_PART_RE = re.compile(r"[A-Za-z0-9._$@+=,-]+")

#: How much is read at a time, and how often the progress line changes.
_CHUNK = 256 * 1024


@dataclass(frozen=True)
class Download:
    """One pinned file, and what to take out of it."""

    url: str
    sha256: str
    #: The file's size in bytes. A download that grows past it is cut off.
    size: int
    #: "file" (written as it is), "tar" (any compression tarfile reads), "zip",
    #: or "gzip" (one gzipped file, written decompressed: the translator's
    #: model files are published that way).
    unpack: str
    #: (member in the archive, name to write it as). For "file" the member is
    #: "" and there is one pair.
    members: tuple[tuple[str, str], ...]
    #: A `platform_key()` this file is for, or "" for every platform.
    platform: str = ""
    #: A native library whose imported symbols are read before it is kept
    #: (INBOX 699): one that imports a network call is refused.
    inspect_imports: bool = False
    #: Zip only: (folder in the archive, folder to write it as). Every file
    #: under it is kept with its relative path, for a program that reads data
    #: from directories on its class path (LanguageTool's language modules are
    #: unpacked folders beside its jars, not jars; without them the server
    #: dies at start with "'es' is not a language code known").
    trees: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.unpack not in {"file", "tar", "zip", "gzip"}:
            raise ValueError(f"unknown unpack step {self.unpack!r}")
        if not self.members:
            raise ValueError("a download names at least one file to keep")
        for _member, name in self.members:
            if not _NAME_RE.fullmatch(name or "") or name in {".", ".."}:
                raise ValueError(f"{name!r} is not a plain file name")
        for prefix, dest in self.trees:
            if (
                self.unpack != "zip"
                or not prefix.endswith("/")
                or not _NAME_RE.fullmatch(dest or "")
            ):
                raise ValueError(f"{prefix!r} is not a tree of a zip")


def platform_key() -> str:
    """This computer, in the words the download table uses.

    `linux-x86_64`, `linux-x86_64-musl`, `linux-aarch64`, `macos-arm64`,
    `macos-x86_64`, `windows-x86_64`, `windows-arm64`; anything else comes
    back as `<sys.platform>-<machine>` so the "not built for" message can
    name it.
    """
    machine = (_platform.machine() or "").lower()
    arch = {"amd64": "x86_64", "x64": "x86_64", "arm64": "aarch64"}.get(machine, machine)
    if sys.platform == "darwin":
        return "macos-arm64" if arch == "aarch64" else f"macos-{arch}"
    if sys.platform == "win32":
        return "windows-arm64" if arch == "aarch64" else f"windows-{arch}"
    if sys.platform.startswith("linux"):
        return f"linux-{arch}-musl" if _is_musl() else f"linux-{arch}"
    return f"{sys.platform}-{arch}"


def _is_musl() -> bool:
    """A musl libc (Alpine), which needs its own build of a native library.
    Read from the loader's own mapping first, as needle's fetcher does,
    because `platform.libc_ver()` misreports on some musl builds."""
    try:
        with open("/proc/self/maps", "rb") as maps:
            blob = maps.read()
        if b"musl" in blob:
            return True
        if b"/libc.so.6" in blob or b"/ld-linux" in blob:
            return False
    except OSError:
        # No /proc (not Linux, or locked down): fall through to the libc probe.
        pass
    return not _platform.libc_ver()[0]


def downloads_for(extra) -> list[Download]:
    """The files this computer needs: every shared one, plus its platform's."""
    key = platform_key()
    return [d for d in extra.downloads if not d.platform or d.platform == key]


def platform_reason(extra) -> str:
    """Why this extra cannot be installed here, or "".

    An entry with platform-specific files and none for this computer is not
    offered: its Install button is greyed with this sentence beside it, and
    `extras.start` refuses it, the same two places `unavailable` is held.
    """
    built = sorted({d.platform for d in extra.downloads if d.platform})
    if not built or platform_key() in built:
        return ""
    return (
        f"There is no prebuilt engine for this computer ({platform_key()}). "
        f"It is built for {', '.join(built)}."
    )


def url_allowed(url: str) -> bool:
    """HTTPS anywhere, or plain HTTP to this machine (a local mirror, or the
    tests' fake file server). Nothing else, `file:` included."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme == "https" and parsed.hostname:
        return True
    if parsed.scheme != "http" or not parsed.hostname:
        return False
    if parsed.hostname == "localhost":
        return True
    try:
        return ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        return False


def root_dir() -> Path:
    """`<data dir>/extras`, beside the notes: one place per notebook, and
    removing the data folder removes them with it."""
    from tessellate.core.config import ConfigManager

    return ConfigManager().data_dir / "extras"


def folder(extra) -> Path:
    return root_dir() / extra.id


def is_installed(extra) -> bool:
    """The marker says this version finished, and every file it names is
    there. A disk look, never a network one."""
    target = folder(extra)
    try:
        marker = json.loads((target / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(marker, dict) or marker.get("version") != extra.version:
        return False
    return all((target / name).is_file() for name in marker.get("files") or [])


def source(extra) -> str:
    """Where the first file comes from, for the confirm dialog: a host name."""
    wanted = downloads_for(extra) or list(extra.downloads)
    if not wanted:
        return ""
    return urlparse(wanted[0].url).hostname or ""


#: A folder of the same files somewhere this machine can reach, for a
#: computer with no internet (copy the files over, serve the folder) and for
#: the browser sweep, which installs from a local copy. Only the address
#: changes: the file is still looked up by its own name, still checked
#: against the pinned hash, and the mirror must be HTTPS or this machine.
MIRROR_ENV = "TESSELLATE_EXTRAS_MIRROR"


def effective_url(download: Download) -> str:
    """The pinned URL, or the same file name under `TESSELLATE_EXTRAS_MIRROR`."""
    mirror = os.environ.get(MIRROR_ENV, "").strip().rstrip("/")
    if not mirror:
        return download.url
    return f"{mirror}/{download.url.rsplit('/', 1)[-1]}"


def _open_url(url: str):
    """The one place a download extra touches the network. Proxies come from
    the environment, as they do for pip, so a machine behind one works."""
    request = urllib.request.Request(url, headers={"User-Agent": "Tessellate"})
    return urllib.request.urlopen(request, timeout=60)  # noqa: S310  # scheme checked by url_allowed


class DownloadFailed(Exception):
    """A download that did not land, named by one of `REASONS`' keys.

    It carries a code, not a sentence: what the person reads is looked up in
    `REASONS` by `extras`, so no text that travelled inside an exception
    (a member name out of a `KeyError`, a path) can reach the route that
    shows it (CodeQL py/stack-trace-exposure on /settings/extras)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


#: What each `DownloadFailed` code says. `{label}` is the extra's own label,
#: filled in by the caller from its catalogue entry, never from the error.
REASONS = {
    "not_allowed": "That download address is not allowed.",
    "stopped": "Stopped before it finished.",
    "too_big": (
        "{label}: the file is bigger than the pinned size, so it is not the "
        "file this version expects."
    ),
    "checksum": (
        "{label}: the checksum does not match the pinned one, so the file was "
        "not kept. Try again; if it keeps happening the download is not the "
        "file this version expects."
    ),
    "missing_member": (
        "The archive is missing a file it should have, so it is not the one "
        "this version expects."
    ),
    "bad_archive": "The archive could not be read.",
    "network_code": (
        "{label}: this engine contains network code, so it was not installed. "
        "Tessellate only runs engines that cannot reach the network."
    ),
    "unreadable_engine": (
        "{label}: the engine could not be checked for network code, so it was "
        "not installed."
    ),
    "unsupported": "This one has no download for this computer.",
    "nothing": "Nothing to download.",
}


def reason(code: str, label: str) -> str:
    """The sentence for a `DownloadFailed` code; unknown codes get a plain one."""
    text = REASONS.get(code, "Couldn't download it. See Settings, Logs for why.")
    return text.format(label=label)


def _mb(n: float) -> str:
    return f"{n / 1_000_000:.1f}"


#: Waits before the second and third try of a download that met a server
#: error. GitHub's release downloads answer 502 and 504 now and then (the
#: package check failed three times in a row on one, 2026-11-08), and one
#: blip used to fail the whole install. A 4xx is the address or the file
#: and is not tried again.
_RETRY_WAITS = (2.0, 5.0)
#: A 429 or 503 may say how long to wait (`Retry-After`); the wait is that
#: many seconds, but never more than this, so a server asking for an hour
#: still gets one more try inside half a minute.
_RETRY_AFTER_CAP = 30.0
#: Stop is looked for this often while a wait runs.
_WAIT_SLICE = 0.25


def _retry_after(exc, default: float) -> float:
    """The wait before the next try: the `Retry-After` of a 429 or 503 (seconds
    or an HTTP date) up to `_RETRY_AFTER_CAP`, else `default`."""
    from email.utils import parsedate_to_datetime

    raw = exc.headers.get("Retry-After") if exc.code in (429, 503) and exc.headers is not None else None
    if not raw or not raw.strip():
        return default
    raw = raw.strip()
    try:
        seconds = float(raw)
    except ValueError:
        try:
            seconds = parsedate_to_datetime(raw).timestamp() - time.time()
        except (TypeError, ValueError):
            return default
    if not seconds > 0:  # a past date, a negative number or NaN
        return default
    return min(seconds, _RETRY_AFTER_CAP)


def _wait(seconds: float, state) -> None:
    """Sleep `seconds` in short slices so Stop is heard during the wait, and
    raise `stopped` the moment it is."""
    left = seconds
    while left > 0:
        step = min(_WAIT_SLICE, left)
        time.sleep(step)
        left -= step
        if state.cancelled:
            raise DownloadFailed("stopped")


def _open_retrying(url: str, state):
    """`_open_url`, tried again after a 5xx, a 429 or a connection that could
    not be opened. Only the opening is retried: a body that breaks off
    part-way fails the download, which starts again from the first byte."""
    import urllib.error

    for wait in (*_RETRY_WAITS, None):
        try:
            return _open_url(url)
        except urllib.error.HTTPError as exc:
            if wait is None or not (exc.code >= 500 or exc.code == 429):
                raise
            wait = _retry_after(exc, wait)
            state.log.append(f"{url} answered {exc.code}, trying again in {wait:g} s")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if wait is None:
                raise
            state.log.append(f"{url} unreachable ({exc}), trying again in {wait:g} s")
        if state.cancelled:
            raise DownloadFailed("stopped")
        _wait(wait, state)
    raise AssertionError("unreachable")


def _fetch(download: Download, dest: Path, state, label: str) -> None:
    """Stream one file to `dest`, hashing as it goes; raise on a mismatch."""
    url = effective_url(download)
    if not url_allowed(url):
        raise DownloadFailed("not_allowed")
    digest = hashlib.sha256()
    received = 0
    last = 0.0
    with _open_retrying(url, state) as response, open(dest, "wb") as out:
        while True:
            if state.cancelled:
                raise DownloadFailed("stopped")
            chunk = response.read(_CHUNK)
            if not chunk:
                break
            received += len(chunk)
            if received > download.size:
                raise DownloadFailed("too_big")
            digest.update(chunk)
            out.write(chunk)
            now = time.monotonic()
            if now - last > 0.25:
                last = now
                state.step = f"Downloading {label}: {_mb(received)} of {_mb(download.size)} MB"
    if digest.hexdigest() != download.sha256:
        raise DownloadFailed("checksum")


def _check_engine(download: Download, written: list[str], staging: Path, state) -> None:
    """Refuse a native engine that imports a network call (INBOX 699).

    The names found go to the install log, not into the error: the error
    carries only a code (see `DownloadFailed`)."""
    from tessellate.core import native_imports

    for name in written:
        try:
            found = native_imports.network_calls((staging / name).read_bytes())
        except (native_imports.NotANativeLibrary, OSError) as exc:
            raise DownloadFailed("unreadable_engine") from exc
        if found:
            state.log.append(f"{name} imports network calls: {', '.join(found[:12])}")
            raise DownloadFailed("network_code")
    state.log.append(f"{download.url.rsplit('/', 1)[-1]} imports no network calls")


def _unpack_tree(archive: zipfile.ZipFile, prefix: str, dest: str, staging: Path) -> list[str]:
    """Write every file under `prefix` into `staging/dest`, keeping its path
    below the prefix. A part that is not a plain name (`..`, an empty part, a
    drive letter) fails the install; nothing is written outside `staging`.
    Returns one sentinel (the first file), so the marker stays short."""
    first = ""
    for info in archive.infolist():
        if not info.filename.startswith(prefix) or info.is_dir():
            continue
        parts = info.filename[len(prefix) :].split("/")
        if not all(_TREE_PART_RE.fullmatch(part) and part not in {".", ".."} for part in parts):
            raise DownloadFailed("missing_member")
        target = staging.joinpath(dest, *parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as handle, open(target, "wb") as out:
            shutil.copyfileobj(handle, out)
        first = first or "/".join([dest, *parts])
    if not first:
        raise KeyError(prefix)
    return [first]


def _unpack(download: Download, fetched: Path, staging: Path) -> list[str]:
    """Write the named members into `staging`. Returns the names written."""
    written = []
    if download.unpack == "file":
        name = download.members[0][1]
        fetched.replace(staging / name)
        return [name]
    try:
        #: Decompressed only after `_fetch` checked the hash of what was
        #: downloaded, so what is inflated here is the pinned file and no
        #: other: its unpacked size is whatever that one file holds.
        if download.unpack == "gzip":
            name = download.members[0][1]
            with gzip.open(fetched, "rb") as handle, open(staging / name, "wb") as out:
                shutil.copyfileobj(handle, out)
            written.append(name)
        elif download.unpack == "tar":
            with tarfile.open(fetched, "r:*") as archive:
                for member, name in download.members:
                    info = archive.getmember(member)
                    handle = archive.extractfile(info) if info.isfile() else None
                    if handle is None:
                        raise KeyError(member)
                    with handle, open(staging / name, "wb") as out:
                        shutil.copyfileobj(handle, out)
                    written.append(name)
        else:
            with zipfile.ZipFile(fetched) as archive:
                for member, name in download.members:
                    with archive.open(member) as handle, open(staging / name, "wb") as out:
                        shutil.copyfileobj(handle, out)
                    written.append(name)
                for prefix, dest in download.trees:
                    written += _unpack_tree(archive, prefix, dest, staging)
    except KeyError as exc:
        raise DownloadFailed("missing_member") from exc
    except (tarfile.TarError, zipfile.BadZipFile, gzip.BadGzipFile, EOFError) as exc:
        raise DownloadFailed("bad_archive") from exc
    finally:
        fetched.unlink(missing_ok=True)
    return written


def install(extra, state) -> None:
    """Download, check and unpack every file, then move the folder into
    place. Raises `DownloadFailed` with a reason fit to show."""
    wanted = downloads_for(extra)
    if not wanted:
        raise DownloadFailed("unsupported" if platform_reason(extra) else "nothing")
    root = root_dir()
    root.mkdir(parents=True, exist_ok=True)
    staging = root / f".{extra.id}.staging"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir()
    try:
        files: list[str] = []
        for number, download in enumerate(wanted, start=1):
            label = extra.short_label or extra.label
            if len(wanted) > 1:
                label = f"{label} ({number} of {len(wanted)})"
            fetched = staging / ".download.part"
            with egress.purpose(f"Downloading {label}: {egress.short(download.url.rsplit('/', 1)[-1])}"):
                _fetch(download, fetched, state, label)
            state.step = f"Unpacking {label}"
            unpacked = _unpack(download, fetched, staging)
            if download.inspect_imports:
                state.step = f"Checking {label} for network code"
                _check_engine(download, unpacked, staging, state)
            files += unpacked
            state.log.append(f"{download.url} sha256 {download.sha256} ok")
        (staging / MARKER).write_text(
            json.dumps({"version": extra.version, "files": files, "platform": platform_key()}),
            encoding="utf-8",
        )
        target = folder(extra)
        old = root / f".{extra.id}.old"
        shutil.rmtree(old, ignore_errors=True)
        if target.exists():
            target.replace(old)
        staging.replace(target)
        shutil.rmtree(old, ignore_errors=True)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def uninstall(extra) -> None:
    """Remove the folder. Idempotent: a folder already gone is removed."""
    target = folder(extra)
    if target.exists():
        shutil.rmtree(target)
