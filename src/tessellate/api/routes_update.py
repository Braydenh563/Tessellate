"""Applying an update automatically, instead of sending someone back through
the browser to download and run the installer by hand, asked for directly:
"I don't want them to have to redownload the installer and go through that
process."

Scoped deliberately narrow, the same way `extras.py`'s allowlist is: this
only ever runs the *official* installer this repo's own release workflow
built and attached to the release `GET /update/check` already found: 
never an arbitrary URL, never a request body naming what to fetch. And it
only offers to at all when `GET /update/check` already said
`can_auto_apply`, a packaged (frozen) Windows install, the one platform
this repo currently ships a silent-installable asset for. `installer.iss`
is a per-user Inno Setup install (`PrivilegesRequired=lowest`) that
overwrites its own install directory unconditionally (`Flags: ignoreversion`
on every file): an ordinary update is exactly the case it already handles,
running it silently is the only new part here.

**Never verified against a real Windows machine or a real release**, same
standing caveat as the console-mode relaunch in `__main__.py`. The shape
(download the official installer, spawn it detached with Inno Setup's own
silent switches, exit so it can overwrite files this process was holding
open) is sound on paper and each piece individually mirrors something
already shipped and tested elsewhere in this codebase (`extras.py`'s
download+verify pattern, `__main__.py`'s detached-spawn-then-exit pattern),
but the actual Win32 mechanics of a real install replacing a real running
app have not been exercised once. If a report comes back either way, that
is the first thing to check, not the code.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from tessellate.core import egress
from tessellate import __version__
from tessellate.api.this_computer import this_computer_only

router = APIRouter(prefix="/update", tags=["system"])
logger = logging.getLogger("tessellate.update")

DOWNLOAD_TIMEOUT = 300  # a ~150MB installer on a slow connection, generously
CHUNK_SIZE = 1 << 16
GITHUB_REPO_API = "https://api.github.com/repos/Braydenh563/Tessellate"
GITHUB_HEADERS = {"Accept": "application/vnd.github+json"}
ASSET_PREFIX = "Tessellate-Setup-"
ASSET_SUFFIX = ".exe"

#: The only hosts an installer may be downloaded from, and the reason is that
#: this file downloads an executable and then runs it.
#:
#: `browser_download_url` comes out of the GitHub API response, which is
#: remote data. TLS means only whoever controls the repo's releases can choose
#: it, and they already ship the app, so this is not a hole that is open
#: today. It is the difference between "trusting the release" and "trusting
#: whatever URL the release names": one asset row pointing somewhere else,
#: through a compromised account or a redirect service, is an arbitrary
#: executable downloaded and run silently, and nothing else in this path would
#: notice (the download is checked for truncation, not for a signature).
#:
#: Both names are needed: the API hands back `github.com/...` release links,
#: which redirect to `objects.githubusercontent.com` for the bytes (measured
#: 2026-09-24 on this repo's v0.3.2 installer). `release-assets.
#: githubusercontent.com` is the host GitHub announced it is moving release
#: downloads to; without it here, the day that redirect changes every in-app
#: update would stop at "couldn't download", with nothing wrong on our side.
ALLOWED_DOWNLOAD_HOSTS = frozenset(
    {
        "github.com",
        "api.github.com",
        "objects.githubusercontent.com",
        "release-assets.githubusercontent.com",
    }
)


def _download_url_is_allowed(url: str) -> bool:
    """https, and one of the release hosts above. Nothing else is fetched."""
    try:
        parsed = urlparse(str(url or ""))
    except ValueError:
        return False
    return parsed.scheme == "https" and (parsed.hostname or "").lower() in ALLOWED_DOWNLOAD_HOSTS

#: Every tag this repo's own release workflow ever creates looks like this
#: (`resolve-version` in release.yml: `v$VERSION`, VERSION always three dot-
#: separated numbers). `POST /apply`'s `tag` query param is client-supplied
#: and was being interpolated straight into a GitHub API URL, flagged by
#: CodeQL as a partial SSRF (`py/partial-ssrf`): the host is fixed, but the
#: *path* wasn't, so a crafted value could still steer the request to a
#: different path than "a release tag" was ever meant to name. Validated
#: against this pattern before it ever reaches a URL, rather than trusting
#: it because the host happens to be hardcoded.
_TAG_RE = re.compile(r"^v\d+\.\d+\.\d+$")

#: How long `_exit_once_launched` waits after the apply thread finishes
#: before calling the real `os._exit`, a module constant specifically so
#: tests can shrink it to ~0. A real, latent test-isolation bug lived here
#: once: a test that mocks `os._exit` returns as soon as `_wait_until_idle`
#: sees `_state.running` go False, but the *watcher* thread is still mid-
#: sleep at that point, by the time it wakes and calls the mocked
#: `os._exit`, `monkeypatch`'s teardown has already reverted it back to the
#: real one, and the real `os._exit(0)` then kills the whole test process a
#: couple of seconds later with no traceback, no summary, just silence.
#: Harmless at the tail of a multi-minute full suite run (the process was
#: about to exit anyway); fatal running this file alone, which is short
#: enough that the delayed bomb detonates mid-run instead. Found by running
#: `pytest tests/test_update.py` alone and getting a truncated run with no
#: failure reported. See EXIT_DELAY_SECONDS's own test-side use.
EXIT_DELAY_SECONDS = 2


def _version_tuple(text: str) -> tuple[int, ...]:
    parts = []
    for piece in text.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def _release_key(text: str) -> tuple:
    """A sortable key for a release tag: the numbers, then final above any
    pre-release of the same numbers, then the pre-release's own parts
    (`beta.2` below `rc.1`, `beta.10` above `beta.9`)."""
    base, _, pre = str(text).strip().lstrip("vV").partition("-")
    parts = tuple((0, int(p)) if p.isdigit() else (1, p) for p in pre.split(".") if p)
    return (_version_tuple(base), 0 if pre else 1, parts)


def _windows_asset(release: dict) -> dict | None:
    for candidate in release.get("assets") or []:
        name = str(candidate.get("name") or "")
        if name.startswith(ASSET_PREFIX) and name.endswith(ASSET_SUFFIX):
            return {
                "name": name,
                "download_url": candidate.get("browser_download_url"),
                "size": candidate.get("size"),
            }
    return None


def _can_auto_apply() -> bool:
    """The one platform this repo's release workflow currently builds a
    *silent-installable* asset for: a packaged (frozen) Windows install.
    Everywhere else (a source checkout, macOS, Linux) this is False."""
    return sys.platform == "win32" and getattr(sys, "frozen", False)


class _ApplyState:
    """One at a time, process-wide, same reasoning as `extras.py`'s
    `_state`: two installers racing each other against the same install
    directory is a way to corrupt it, not a way to go faster."""

    def __init__(self) -> None:
        self.running = False
        self.step = ""
        self.error = ""
        self.done_bytes = 0
        self.total_bytes = 0
        self.outcome = ""  # "" while running, then "launched" | "failed"
        #: Bumped per apply; the exit watcher started with one attempt must
        #: never act on another's outcome (see `_exit_once_launched`).
        self.attempt = 0


_state = _ApplyState()
_lock = threading.Lock()


def reset_for_tests() -> None:
    """Process-global, like `core.extras._state`, tests have to clear it or
    one test's apply attempt leaks into the next one's assertions."""
    global _state
    _state = _ApplyState()
    _reset_source_status_for_tests()


def current() -> dict:
    return {
        "running": _state.running,
        "step": _state.step,
        "error": _state.error,
        "done_bytes": _state.done_bytes,
        "total_bytes": _state.total_bytes,
        "outcome": _state.outcome,
    }


#: github.com -> objects.githubusercontent.com (the module docstring above)
#: is the whole redirect chain any real release download ever needs; a
#: handful of spare hops covers a CDN's own internal bounce without letting
#: a redirect loop hang the download indefinitely.
MAX_DOWNLOAD_REDIRECTS = 5


@egress.labelled(lambda url, *a, **k: f"Downloading an update: {egress.short(url.rsplit('/', 1)[-1])}")
def _download(url: str, dest: Path) -> None:
    """Streamed, with progress on `_state`, the installer is well over a
    typical extras wheel, so a caller polling for "still alive" needs an
    actual number moving, not a static "downloading…" for however long a
    slow connection takes.

    `requests.get(..., allow_redirects=True)` (the default) only checks the
    *first* URL: `_run_apply` validates that one against
    `ALLOWED_DOWNLOAD_HOSTS` before this function ever runs, but every hop
    after that used to be followed unchecked. GitHub's own release flow
    always redirects at least once (github.com to
    objects.githubusercontent.com, the reason both hosts are on the
    allowlist), so this is not a theoretical gap: `allow_redirects=False`
    below, with each `Location` re-validated by hand before it is ever
    fetched, keeps that real redirect working while refusing to follow one
    off the allowlist. Chosen over "follow redirects and check
    `response.url` afterwards" because by the time a response has a final
    `url`, `requests` has already connected to every host on the way there;
    checking first means a disallowed host is never contacted at all.
    """
    current_url = url
    response = None
    for _ in range(MAX_DOWNLOAD_REDIRECTS):
        if not _download_url_is_allowed(current_url):
            logger.warning("refusing to follow an update redirect to an unexpected host")
            raise ValueError("redirected to a disallowed host")
        response = requests.get(
            current_url, stream=True, timeout=DOWNLOAD_TIMEOUT, allow_redirects=False
        )
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()
            response = None
            if not location:
                raise ValueError("redirect with no Location header")
            # Relative Location headers are legal (RFC 7231 7.1.2); resolved
            # against the URL that sent them, same as a browser would.
            current_url = urljoin(current_url, location)
            continue
        break
    else:
        raise ValueError("too many redirects")
    response.raise_for_status()
    _state.total_bytes = int(response.headers.get("Content-Length") or 0)
    written = 0
    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk:
                continue
            f.write(chunk)
            written += len(chunk)
            _state.done_bytes = written
    # A truncated download (connection dropped mid-stream) is worse than an
    # obvious failure: a corrupt installer that silently does nothing, or
    # partway does something, is not a shape of failure this gets to guess
    # about. Only checked when the server actually sent a length, some
    # CDNs omit it, and refusing every such download over a header that was
    # never promised would be its own bug.
    if _state.total_bytes and written < _state.total_bytes:
        # The safe, byte-counts-only text goes straight onto `_state` here,
        # not into the exception that follows, see `_run_apply`'s own
        # except block for why an exception's `str()` never reaches
        # `_state.error` at all, not even one this module wrote itself.
        _state.error = (
            f"Download incomplete: got {written} of {_state.total_bytes} bytes "
            ", check your connection and try again."
        )
        raise OSError("download truncated")


def _run_apply(download_url: str, asset_name: str) -> None:
    # Two distinct failure phases below, caught separately on purpose: a
    # download blocked by a firewall/proxy/antivirus and an installer
    # execution blocked by antivirus/SmartScreen *after* a good download
    # look identical from `except Exception` alone, but need different
    # advice: asked for directly ("handle the case that the new installer
    # download is blocked by browser, firewall or other security").
    if not _download_url_is_allowed(download_url):
        # Refused before anything is written to disk, and named in the log
        # rather than in `_state.error`, which reaches the browser.
        logger.warning("refusing an update download from an unexpected host")
        _state.error = (
            "That update was published with a download link this app does not "
            "recognise, so nothing was downloaded."
        )
        # "failed" rather than a new outcome: the browser switches on this
        # value, and a state it has never seen would render as nothing at all.
        _state.outcome = "failed"
        _state.step = (
            "The update was not downloaded, because its download link does "
            "not point at this app's own releases. Install it from the "
            "releases page instead."
        )
        _state.running = False
        return
    try:
        _state.step = "Downloading the update…"
        tmp_dir = Path(tempfile.mkdtemp(prefix="memorymap-update-"))
        installer_path = tmp_dir / asset_name
        _download(download_url, installer_path)
    except Exception:
        # Full detail to the log only, `_state.error` reaches the browser
        # via GET /apply/status, and an arbitrary exception's own `str()`
        # (a `requests` connection error, a filesystem OSError) can carry a
        # local path or other internal detail. CodeQL: py/stack-trace-
        # exposure, the same shape `core/extras.py`'s own module docstring
        # already documents fixing once, this is the stricter version:
        # never read the caught exception's own text at all, not even
        # conditionally. `_download` already set `_state.error` itself, with
        # a safe, byte-counts-only message, for the one failure in this
        # phase worth naming specifically (a truncated download); anything
        # else falls through to the generic message below.
        logger.exception("update download failed")
        _state.outcome = "failed"
        if not _state.error:
            _state.error = "Download failed: see Settings, Logs for details."
        _state.step = (
            "Couldn't download the update, this can happen if a firewall, "
            "proxy, or antivirus is blocking the download, or if you're "
            "offline. Check your connection and try again from Settings → "
            "About."
        )
        _state.running = False
        return

    try:
        _state.step = "Starting the installer…"
        # Silent, no reboot, no message boxes, this repo's own installer.iss
        # (Inno Setup) supports all three out of the box; nothing in the
        # packaging needed to change for this to work *if* the mechanics
        # below hold up on a real machine.
        #
        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP: independent of this
        # process's own console/job: it must keep running after this
        # process exits, which is the whole point (this app cannot replace
        # its own running .exe/DLLs while they're open; the installer,
        # started fresh and outliving this process, can).
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(  # noqa: S603  # fixed args, path is our own download, no shell
            # /RELAUNCH=1: this process is the running app and is about to
            # exit, so the installer opens it again when it is done
            # (installer.iss, ShouldRelaunch). A silent install otherwise
            # never starts the app: the launch entry is skipifsilent.
            [str(installer_path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH=1"],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        _state.outcome = "launched"
        _state.step = (
            "Installing in the background. Tessellate closes now and reopens "
            "by itself in a minute or two, on the new version."
        )
        logger.info("update installer launched (%s), exiting to let it run", asset_name)
    except (PermissionError, OSError):
        # WinError 5 (access denied) / WinError 1260 (blocked by policy) are
        # exactly the shape antivirus or Windows SmartScreen quarantining a
        # freshly-downloaded, unsigned-looking .exe takes, a plain "failed"
        # message would send someone down a network-troubleshooting dead
        # end for what is actually a security-software decision.
        logger.exception("update installer failed to launch")
        _state.outcome = "failed"
        # Not str(exc): a WinError from Popen/the filesystem can carry a
        # real local path. See the download except block's own comment.
        _state.error = "Couldn't start the installer, see Settings, Logs for details."
        _state.step = (
            "The downloaded update was blocked from running, this is "
            "usually antivirus or Windows SmartScreen quarantining a new "
            "download. Check your antivirus's quarantine/history, allow "
            "the file, and try again, or download the installer manually "
            "from the release page."
        )
    except Exception:
        logger.exception("update apply failed")
        _state.outcome = "failed"
        _state.error = "Update failed: see Settings, Logs for details."
        _state.step = "Couldn't apply the update, see Settings, Logs for why."
    finally:
        _state.running = False


def record_update_choice(config, check: bool) -> None:  # noqa: ANN001  # a ConfigManager
    """The answer to "check for updates automatically?", asked once (the
    owner, 2026-10-05, WORLD_CLASS_PLAN 12 "Decisions made").

    Yes turns the in-app check on, which shows the update bar when a version
    exists. It never turns on the launcher's pull on start (INBOX 1440:
    nothing installs without a press), so "tell me" and "change my code by
    itself" stay different sizes of consequence (core/config.py). No turns
    both off. Either way the question is not asked again; Settings, About
    holds the switches.
    """
    config.set_preference("update_check_enabled", bool(check))
    if not check:
        config.set_preference("auto_update_enabled", False)
    config.set_preference("update_choice_made", True)


def apply_launcher_choice(config) -> None:  # noqa: ANN001  # a ConfigManager
    """Keep the answer start.sh took in the terminal. The launcher asks
    before `.venv` exists, so it cannot write `preferences.json` itself; it
    exports `MM_UPDATE_CHOICE=yes|no` and the app records it at start. An
    answer already on file (from the app, or a switch) is never overwritten,
    and anything but yes or no is no answer at all."""
    value = os.environ.get("MM_UPDATE_CHOICE", "").strip().lower()
    if value not in ("yes", "no") or config.get_preference("update_choice_made", False) is True:
        return
    record_update_choice(config, value == "yes")


class _ChoiceBody(BaseModel):
    check: bool


@router.post("/choice")
def update_choice(body: _ChoiceBody, request: Request) -> dict:
    """The app's one-time question, answered (update-dialogs.js). Yes turns
    on reaching GitHub and installing what it finds: this computer's call,
    so another device may only answer no."""
    from tessellate.core import deps

    if body.check:
        this_computer_only(request)

    config = deps.get_config()
    record_update_choice(config, body.check)
    return {
        "update_choice_made": True,
        "update_check_enabled": config.get_preference("update_check_enabled", False),
        "auto_update_enabled": config.get_preference("auto_update_enabled", False),
    }


def _no_releases() -> dict:
    return {
        "checked": False,
        "reason": "no_releases",
        "message": (
            "No release has been published yet, so there is nothing to "
            "update to. You are on the newest version there is."
        ),
    }


def _update_check_refused(config, manual: bool) -> dict | None:  # noqa: ANN001
    """Why no request should be made at all: the switch is off, or this
    source install follows main. None when the check may go ahead."""
    #: `manual` is the Check for updates button in Settings: a click is the
    #: person asking for this one request, so the switch (which governs the
    #: check made by itself at sign-in) does not refuse it.
    if not manual and not config.get_preference("update_check_enabled", False):
        return {"checked": False, "reason": "disabled"}
    channel = config.get_preference("update_channel", "stable")
    #: "Track the main branch" is a launcher setting: `start.bat` and
    #: `start.sh` pull main instead of a tag on a source install, and that
    #: works. The packaged app has no source to pull and no nightly
    #: installer, so for it the choice reads as stable rather than as
    #: silence (the owner, 2026-09-14).
    if channel == "main" and getattr(sys, "frozen", False):
        channel = "stable"
    if channel == "main":
        #: **A source install on this channel is not broken, it is already
        #: doing it.** Still `checked: false`: there is no *release* to
        #: compare against on this channel and inventing one would be a lie.
        return {
            "checked": False,
            "reason": "channel_source_main",
            "message": (
                "This copy follows the newest changes: start.bat and "
                "start.sh pull them on every launch, so it is already up to "
                "date. Turn off \"Follow the newest changes\" below to be "
                "told about finished releases instead."
            ),
        }
    return None


def _fetch_release_answer(beta: bool):
    """GitHub's answer for the latest release (or the recent list on the beta
    channel), as `(response, None)`, or `(None, the dict to return)`.

    **Three different failures, three different sentences.** A repository
    with no published release answers `/releases/latest` with 404, which is
    "nothing to update to yet", not "unreachable"; rate limiting (60 requests
    an hour for an unauthenticated caller) is the second; no network the third.
    """
    try:
        if beta:
            response = requests.get(
                f"{GITHUB_REPO_API}/releases",
                params={"per_page": 10},
                timeout=4,
                headers=GITHUB_HEADERS,
            )
        else:
            response = requests.get(
                f"{GITHUB_REPO_API}/releases/latest", timeout=4, headers=GITHUB_HEADERS
            )
    except Exception:
        logger.info("update check could not reach GitHub", exc_info=True)
        return None, {
            "checked": False,
            "reason": "unreachable",
            "message": "Couldn't reach GitHub to check for updates.",
        }
    if response.status_code == 404:
        return None, _no_releases()
    if response.status_code in (403, 429):
        return None, {
            "checked": False,
            "reason": "rate_limited",
            "message": (
                "GitHub is rate-limiting this machine. The check will work "
                "again within the hour."
            ),
        }
    return response, None


def _read_release(response, beta: bool):  # noqa: ANN001
    """The release dict out of GitHub's answer, as `(release, None)`, or `(None, the dict to return)`."""
    try:
        response.raise_for_status()
        release = response.json()
        if beta:
            listed = [r for r in release if isinstance(r, dict) and not r.get("draft") and r.get("tag_name")]
            if not listed:
                return None, _no_releases()
            release = max(listed, key=lambda r: _release_key(r["tag_name"]))
        if not isinstance(release, dict):
            raise ValueError("GitHub did not answer with a release")
    except Exception:
        logger.info("update check got an answer it could not read", exc_info=True)
        return None, {
            "checked": False,
            "reason": "unreachable",
            "message": "GitHub answered with something this couldn't read.",
        }
    return release, None


@router.get("/check")
@egress.labelled("Checking GitHub for a new version")
def check_for_update(manual: bool = False) -> dict:
    """Is a newer release on GitHub than the one running right now?

    Moved here from app.py (was inline) so it lives alongside the rest of
    the update machinery it feeds, `can_auto_apply`/`asset` are exactly
    what `POST /apply` below re-derives for itself rather than trusting.

    The only other opt-in network call in the app besides web search
    (Settings -> About, update_check_enabled: off until switched on, same
    reasoning as web_search_enabled). Never raises: a failed check just
    means "couldn't tell," not something worth a 500 over, and the
    frontend treats {"checked": false} as "say nothing" either way.
    """
    from tessellate.core import deps

    config = deps.get_config()
    refusal = _update_check_refused(config, manual)
    if refusal:
        return refusal
    #: Opt-in beta (OPEN ledger 302): the recent list instead of `latest`,
    #: which never holds a pre-release. Off by default.
    beta = config.get_preference("update_beta", False) is True
    response, failure = _fetch_release_answer(beta)
    if failure:
        return failure
    release, failure = _read_release(response, beta)
    if failure:
        return failure
    latest = str(release.get("tag_name") or "").lstrip("vV")

    update_available = bool(latest) and _release_key(latest) > _release_key(__version__)
    asset = _windows_asset(release) if (update_available and _can_auto_apply()) else None

    return {
        "checked": True,
        "current": __version__,
        "latest": latest,
        "update_available": update_available,
        "prerelease": bool(release.get("prerelease")) or "-" in latest,
        "url": (
            release.get("html_url")
            if beta and str(release.get("html_url") or "").startswith("https://github.com/")
            else "https://github.com/Braydenh563/Tessellate/releases/latest"
        ),
        "can_auto_apply": asset is not None and bool(asset.get("download_url")),
        "asset": asset,
    }


@router.get("/releases")
@egress.labelled("Listing the versions on GitHub")
def list_releases() -> dict:
    """Recent GitHub releases, for a "pick a specific version" control in
    Settings: asked for directly. Only meaningful on the one install type
    that can actually apply one of these silently; everywhere else this is
    an honestly empty list rather than a picker that does nothing when used."""
    from tessellate.core import deps

    config = deps.get_config()
    if not config.get_preference("update_check_enabled", False):
        return {"available": False, "reason": "disabled", "releases": []}
    if config.get_preference("update_channel", "stable") == "main":
        return {"available": False, "reason": "channel_unavailable", "releases": []}
    if not _can_auto_apply():
        return {"available": False, "reason": "not_supported", "releases": []}
    try:
        response = requests.get(
            f"{GITHUB_REPO_API}/releases",
            params={"per_page": 10},
            timeout=4,
            headers=GITHUB_HEADERS,
        )
        response.raise_for_status()
        releases = response.json()
    except Exception:
        logger.info("release list fetch failed", exc_info=True)
        return {"available": False, "reason": "unreachable", "releases": []}

    out = []
    for release in releases:
        asset = _windows_asset(release)
        if not asset or not asset.get("download_url"):
            continue  # a source-only tag (no installer attached) can't be applied here
        tag = str(release.get("tag_name") or "")
        out.append(
            {
                "tag": tag,
                "version": tag.lstrip("vV"),
                "name": release.get("name") or tag,
                "published_at": release.get("published_at"),
                "prerelease": bool(release.get("prerelease")),
            }
        )
    return {"available": True, "current": __version__, "releases": out}


class _SourceUpdateState:
    """One instance, one module-level `global`, instead of four loose
    bool/str variables: the same `_ApplyState` shape this file already
    uses above for the apply flow. CodeQL flagged the four-loose-variables
    version as `py/unused-global-variable` (a note, not a real defect: each
    one *is* read, just only within this same function across separate
    calls): collecting them onto one object sidesteps that shape entirely,
    the same way `_ApplyState`/`_state` already does for `_run_apply`."""

    def __init__(self) -> None:
        self.env_checked = False
        self.just_updated = False
        self.from_version = ""
        self.to_version = ""


_source_state = _SourceUpdateState()


def _reset_source_status_for_tests() -> None:
    global _source_state
    _source_state = _SourceUpdateState()


@router.get("/source-status")
def source_update_status() -> dict:
    """Did `start.sh`/`start.bat` just `git pull` in a real update before
    launching this process? Those scripts already auto-update on every
    launch (self-update block, step 0), this only reports that fact so
    the frontend can show the same "just updated" popup the packaged-
    Windows auto-apply flow shows, asked for directly: "if the app auto
    updates, I want a Popup to show ... after they login."

    Reads a plain env var the launcher scripts set, no network call, so
    this is always safe offline, and self-clears after the first read in
    this process's lifetime so re-opening a second tab, or polling again
    later in the same session, doesn't repeat the popup.
    """
    if not _source_state.env_checked:
        _source_state.env_checked = True
        # start.bat's own subroutine leaves the quotes from
        # `__version__ = "0.1.3"` on rather than fight cmd.exe's quoting
        # rules for embedding a literal `"` inside `set "VAR=..."`, see
        # start.bat's :read_version. start.sh already strips them via sed.
        from_v = os.environ.get("MM_UPDATED_FROM", "").strip().strip('"')
        to_v = os.environ.get("MM_UPDATED_TO", "").strip().strip('"')
        _source_state.just_updated = bool(to_v and from_v != to_v)
        _source_state.from_version = from_v
        _source_state.to_version = to_v
    if _source_state.just_updated:
        _source_state.just_updated = False  # one shot
        return {
            "just_updated": True,
            "from": _source_state.from_version,
            "to": _source_state.to_version,
        }
    return {"just_updated": False, "from": "", "to": ""}


@router.post("/apply", dependencies=[Depends(this_computer_only)])
@egress.labelled(lambda tag=None, *a, **k: f"Fetching version {tag or 'latest'} from GitHub")
def apply_update(tag: str | None = None) -> dict:
    """Download the official installer for `tag` (or the latest release
    when omitted) and hand off to it. Never accepts a URL from the request
    body: only ever an asset this endpoint itself just looked up by tag
    name, the same "never trust client-cached data for the thing about to
    run an executable" reasoning the latest-only version always used."""
    from tessellate.core import deps

    if tag is not None and not _TAG_RE.match(tag):
        # Never reaches a URL otherwise, see _TAG_RE's own comment.
        raise HTTPException(status_code=400, detail="Not a valid release tag.")

    config = deps.get_config()
    if not config.get_preference("update_check_enabled", False):
        raise HTTPException(
            status_code=403,
            detail="Turn on 'Check GitHub for a newer version' in Settings → "
            "About first: this needs to know a release actually exists.",
        )
    # No `auto_update_enabled` guard (INBOX 1440): this request is the press on
    # the update bar's or Settings' Update button, the consent itself. That
    # switch now only decides whether a launcher copy pulls code on start.
    if not _can_auto_apply():
        raise HTTPException(
            status_code=409,
            detail="Automatic updates are only available for the packaged "
            "Windows app right now. Download the new version from the "
            "release page instead.",
        )
    with _lock:
        if _state.running:
            raise HTTPException(status_code=409, detail="An update is already being applied.")
        # A fresh check, not the one the popup already has cached client-
        # side: the release may have moved on, and this is the one request
        # in the whole flow that is about to run an executable, so it gets
        # its own source of truth rather than trusting a payload the client
        # could (even accidentally, via a stale page) send stale.
        #
        # Always one of these two *fixed* URLs, `tag` (already validated
        # against _TAG_RE above) never gets interpolated into a request URL
        # at all, not even a validated one: when a tag is given, the release
        # is found by matching `tag_name` in the plain `/releases` listing's
        # own response instead. Belt-and-suspenders on top of the _TAG_RE
        # check: CodeQL (py/partial-ssrf) flagged the interpolated version
        # even with that validation in place, so this removes the
        # client-influenced value from the URL entirely rather than trust
        # a sanitizer its data-flow analysis doesn't recognise.
        url = f"{GITHUB_REPO_API}/releases" if tag else f"{GITHUB_REPO_API}/releases/latest"
        try:
            response = requests.get(url, timeout=4, headers=GITHUB_HEADERS)
            response.raise_for_status()
            body = response.json()
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail="Couldn't reach GitHub to fetch the update. Check your "
                "internet connection and try again.",
            ) from exc
        if tag:
            release = next((r for r in body if r.get("tag_name") == tag), None)
            if release is None:
                raise HTTPException(status_code=404, detail="No release found for that tag.")
        else:
            release = body
        asset = _windows_asset(release)
        download_url = asset.get("download_url") if asset else None
        if not download_url:
            raise HTTPException(
                status_code=502,
                detail="That release has no Windows installer attached.",
            )
        _state.attempt += 1
        attempt = _state.attempt
        watched = _state
        _state.running = True
        _state.outcome = ""
        _state.error = ""
        _state.step = "Starting…"
        _state.done_bytes = 0
        _state.total_bytes = 0
    threading.Thread(
        target=_run_apply, args=(download_url, asset["name"]), daemon=True, name="update-apply"
    ).start()
    threading.Thread(
        target=_exit_once_launched, args=(watched, attempt), daemon=True, name="update-exit-watch"
    ).start()
    return {"started": True}


@router.get("/apply/status")
def apply_status() -> dict:
    return current()


def _exit_once_launched(watched: _ApplyState | None = None, attempt: int | None = None) -> None:
    """Once the installer has actually been launched, this process has to
    get out of its way, its own .exe/DLLs are what the installer needs to
    overwrite. Polled rather than exited directly from `_run_apply`: the
    HTTP response for `POST /apply` (and every `/apply/status` poll after
    it) has to actually reach the browser first, or the UI never learns the
    install started before the process vanishes out from under it. One of
    these per apply attempt (started alongside `_run_apply` above), not a
    long-lived background loop: it exits itself the moment this attempt
    resolves either way.
    """
    # Bound when the watcher starts, not when it fires: a test that mocks
    # `os._exit` for one apply keeps its mock here even after its teardown
    # reverts the module attribute, so a watcher still asleep cannot fire the
    # real exit into a later test (CI, 2026-09-26: an xdist worker died two
    # seconds into an unrelated test after a "launched" apply elsewhere).
    #
    # And it watches its own attempt only (CI, the same day, again): the loop
    # polls every half second, so a watcher whose attempt had already failed
    # could still be asleep when the next attempt started, wake to see that
    # one running, and act on its "launched" with the exit it was started
    # with, which was not the one the new attempt's caller had arranged.
    exit_now = os._exit
    state = watched if watched is not None else _state
    mine = attempt if attempt is not None else state.attempt

    def still_mine() -> bool:
        return state is _state and state.attempt == mine

    while state.running and still_mine():
        time.sleep(0.5)
    if still_mine() and state.outcome == "launched":
        time.sleep(EXIT_DELAY_SECONDS)  # let the last status poll's response actually go out
        if still_mine():
            # The notebook's lock goes before the exit that skips every
            # `finally`: the installer the person reopens the app after must
            # not find a lock naming this pid (core/instance_lock.py).
            from tessellate.core import instance_lock

            instance_lock.release()
            exit_now(0)
