"""Paths + user preferences for the whole app.

Why a single class: every part of the app must agree on where the
database lives and what the user has chosen (build plan §4). `deps.py`
creates exactly ONE instance of this at startup; nothing else should
construct it.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any

from dotenv import load_dotenv

from tessellate.core.atomic_io import atomic_write_json

# Defaults for every user-changeable preference. Stored as data in one
# place so the future Preferences screen has one list to show.
DEFAULT_PREFERENCES: dict[str, Any] = {
    "chat_model": "llama3.2",  # any installed Ollama model
    "embedding_backend": "sentence-transformers",  # or "ollama"
    "embedding_model": "nomic-embed-text",  # only used when backend == "ollama"
    "recycle_bin_days": 30,
    # Where a generated export (graph PNG, chat export, whiteboard PNG, see
    # routes_files.py's save_generated_file) is written. Empty means the
    # default, `data_dir/exports`; validated at save time (PUT /preferences),
    # not at export time, so a bad path is a rejected preference rather than
    # a lost file. Asked for directly, alongside the "Open exports folder"
    # button: "a configurable save location for exported images."
    "export_save_dir": "",
    # A second place each backup is copied to (an external drive, a synced
    # folder), so one disk failing does not take the notebook and every backup
    # with it. Empty means backups stay in `data_dir/backups` only. Validated
    # at save time like `export_save_dir`.
    "backup_copy_dir": "",
    # Semantic search relevance (search_manager.py). Defaults match that
    # module's own MIN_SIMILARITY/RELATIVE_Z_MARGIN constants, kept here
    # too, as plain values rather than an import, so Settings -> Preferences
    # can offer a real "reset to default" without importing search_manager
    # into config.py.
    "search_min_similarity": 0.25,
    "search_relative_z_margin": 0.5,
    # The user's IANA timezone, e.g. "Australia/Brisbane". Reported by the
    # browser on startup, because the browser is the only thing that knows
    # where the person actually is, the server may well be running in UTC
    # (a container, a NAS), and "remind me in ten minutes" resolved against
    # the wrong clock lands hours out. Empty means "fall back to the server's
    # own zone", which is correct for the ordinary case of both on one laptop.
    "timezone": "",
    # Web search is one of the two features that can leave the machine (the
    # other is the update check below), so it is off
    # until asked for, and which engine answers is the user's choice rather
    # than something inferred from whether a SearXNG address happens to be
    # filled in. See `search/websearch.PROVIDERS`.
    "web_search_enabled": False,
    # Asked for directly, alongside the Windows installer: since a release
    # only ships when someone remembers to tag one, nothing ever told a
    # person running an installed build that a newer version existed. The
    # only other opt-in network call in the app, off by default for the
    # same reason web_search_enabled is: "100% offline" (Settings -> About)
    # has to stay true until someone deliberately switches it off, not
    # something the app quietly does anyway for a good reason. Checks
    # GitHub's own releases API for the latest tag; nothing about the
    # notebook itself is ever sent.
    "update_check_enabled": False,
    # Separate from update_check_enabled on purpose: "tell me a new version
    # exists" and "download and run an installer without me clicking
    # anything in a browser" are different sizes of consequence, asked for
    # directly ("the option to turn auto update off entirely"), with its own
    # switch rather than folding it into the check preference, so someone
    # can want the notification without ever wanting the second part. Off by
    # default for the same reason the check itself is: this is opt-in, not
    # opt-out, the first time.
    "auto_update_enabled": False,
    # **Ask once** (the owner, 2026-10-05, WORLD_CLASS_PLAN 12, "Decisions
    # made"): has the person answered "check for updates automatically?" yet,
    # in the terminal (start.sh) or in the app. Until it is True the launchers
    # leave the checkout alone and nothing about updating touches the
    # network; the answer sets the two switches above and this, once. Turning
    # either switch in Settings is an answer too (`update_preferences`).
    "update_choice_made": False,
    # "stable" (tagged GitHub releases) or "main" (asked for directly: track
    # the main branch and update on every push to it). "main" is accepted as
    # a real, storable choice, the Settings toggle isn't fake, but
    # routes_update.py's own check honestly reports it as not yet available
    # for the GitHub-releases flow rather than pretending to find updates
    # that don't exist: that would need a second release pipeline (a rolling
    # nightly build published on every main-branch push) this repo does not
    # have yet, and building that blind, unreviewed, was judged a larger and
    # riskier undertaking than the rest of this feature, see HANDOVER.md.
    #
    # This literal value only ever applies to a packaged (frozen) Windows
    # install: ConfigManager._load_preferences overrides it to "main" for
    # every other install type before merging in whatever the user has
    # actually saved, since a source checkout already tracks main for real
    # via start.sh/start.bat's own `git pull` on every launch.
    "update_channel": "stable",
    # Also offer pre-releases (a beta or release candidate) when checking for
    # a new version. Off: only finished releases (routes_update.check).
    "update_beta": False,
    # Bring the user's own SearXNG up with the app. Off by default: starting a
    # container is not something a local-first app does unasked.
    "searxng_autostart": False,
    # Install `sentence-transformers` (about 2 GB with PyTorch) on its own the
    # first time search by meaning finds it missing (ai/embeddings.py). On by
    # default because the built-in engine is the default engine; the owner:
    # "the user should be able to cancel or refuse the auto install", so off
    # means it is never started, search stays on keywords, and Settings,
    # Packages keeps its manual Install.
    "semantic_auto_install": True,
    # Whisper's options (ai/voice.py `options_from`, Brief 87 step 2): skip
    # the silence and hum around a clip (Silero VAD, no download); a language
    # ("" detects it); names and terms to expect, as Whisper's prompt.
    "voice_skip_silence": True,
    "voice_language": "",
    "voice_vocabulary": "",
    "searxng_url": "",
    "search_provider": "auto",
    # Which dialect the chat backend speaks (§6). "ollama" is the native
    # `/api` shape; "openai" is `/v1/chat/completions`, which is what LM
    # Studio, llama.cpp, Jan and vLLM all serve, one setting covers all of
    # them, because the only thing that differs between them is the URL.
    "llm_provider": "ollama",
    # Empty means "the default for that provider", OLLAMA_URL for Ollama,
    # LM Studio's port for the OpenAI shape. Stored rather than derived so
    # switching provider and back doesn't forget a custom address.
    "llm_base_url": "",
    # Only ever needed by a hosted gateway; local servers ignore it. Kept out
    # of the support bundle by the same redaction that hides other secrets.
    "llm_api_key": "",
    # How much effort a chat turn is worth by default (§11): "quick", "normal"
    # or "detailed". One dial over the reply cap, the temperature, the thinking
    # toggle and a length hint, see `ai/presets.py`. "normal" reproduces the
    # behaviour that predates presets exactly, so upgrading changes nothing
    # until someone chooses otherwise.
    "response_mode": "normal",
    # Keep the AI on this machine. ON by default, and the default is the point:
    # "100% offline, on your machine" is a promise the app keeps rather than
    # one it reminds you that you are breaking. With this on, a backend address
    # that is not local or LAN is refused outright, see
    # `core.security.check_backend_url`. Turning it off is a deliberate act
    # with a visible switch, for someone who genuinely wants a hosted API.
    "local_only_ai": True,
    # --- the background librarian (§39) ---------------------------------------
    # Off by default and deliberately so: it runs the agent against the whole
    # notebook with nobody watching, which is a thing to opt into rather than
    # discover.
    "autonomous_tasks_enabled": False,
    "auto_tag_enabled": True,
    "auto_link_enabled": True,
    "auto_dedupe_enabled": True,
    # ROADMAP.md item 34. Off by default like the other three, and for the
    # same reason: but also because unlike tag/link/dedupe, this one adds a
    # whole new kind of thing to the notebook (an entity) rather than
    # changing an existing note, which deserves an even more deliberate opt-in.
    "auto_entities_enabled": False,
    # ROADMAP.md item 31. Off by default for the same reason as entities
    # above: this one makes a judgement call about which notes count as
    # "forgotten" rather than performing a request the user already made
    # (tag/link/dedupe are all reactions to a note's own content).
    "auto_stale_review_enabled": False,
    # ANALYSIS.md §60 item 2, the one real feature gap the odysseus read
    # found: nothing in this app turns an offhand mention in ordinary chat
    # into a filed note. Off by default, and this is the *most* deliberate
    # opt-in of the five: the other four react to notes the user wrote, and
    # this one decides on its own that something said in passing was worth
    # keeping. It writes drafts rather than notes for the same reason, see
    # `ai/passive_capture.py`.
    "auto_capture_enabled": False,
    "autonomous_tasks_interval_hours": 6,
    #: Skip the expensive extras, similarity edges on the graph, the
    #: background pass: on a laptop running off its battery.
    "battery_efficient_mode": False,
    #: Let background work use the (smaller, faster) utility model instead of
    #: tying up the chat model. Off means everything uses the chat model.
    "smart_model_routing_enabled": True,
    # How long a session can be idle before the user must log in again.
    "session_idle_ttl_minutes": 720,
    #: The desktop launcher's console window (start.bat/start-desktop.bat
    #: open one; the packaged installer's build has none to show at all).
    #: "Dev view" (console visible, True) is the default a fresh install
    #: starts on: asked for directly, reversing an earlier default in this
    #: same app: "dev view is the default on install and the user will be
    #: presented with a popup option to change it just after install."
    #: "User view" (False) is the one that hides it, genuinely never
    #: creates a console at all when the app supports that (see
    #: __main__.py's pythonw.exe relaunch), rather than trying to hide one
    #: that already exists. Read by __main__.py before the window opens,
    #: and kept in sync with the tray's own live toggle and Settings.
    "show_console_on_startup": True,
    #: Whether the first-run "Dev view or User view?" prompt has already
    #: been shown, so it asks exactly once per install rather than on every
    #: launch. Distinct from show_console_on_startup itself so a later
    #: change via Settings/tray doesn't make the intro reappear.
    "console_view_intro_seen": False,
    #: Single instance by default: a second launch of the desktop app brings
    #: the running window forward. On, it opens another window onto the SAME
    #: running server instead (never a second server on one data directory,
    #: core/instance_lock.py). Advanced, off by default.
    "new_window_on_launch": False,
}


DB_NAME = "tessellate.db"
OLD_DB_NAME = "memorymap.db"  # brand: keep, the name before the rename


def _adopt_old_db(data_dir: Path) -> Path:
    """Rename a notebook from before the rename once, with its sidecars.

    The -wal file holds committed rows not yet checkpointed, so it moves
    with the database or those rows are lost. If the move fails (a file
    held open on Windows), the old name keeps working.
    """
    new, old = data_dir / DB_NAME, data_dir / OLD_DB_NAME
    if new.exists() or not old.exists():
        return new
    try:
        for suffix in ("-wal", "-shm", "-journal"):
            side = data_dir / (OLD_DB_NAME + suffix)
            if side.exists():
                os.replace(side, data_dir / (DB_NAME + suffix))
        os.replace(old, new)
    except OSError:
        for suffix in ("-wal", "-shm", "-journal"):
            moved = data_dir / (DB_NAME + suffix)
            if moved.exists() and not (data_dir / (OLD_DB_NAME + suffix)).exists():
                os.replace(moved, data_dir / (OLD_DB_NAME + suffix))
        return old
    return new


def _default_data_dir() -> str:
    """Where notes live when nothing else says otherwise.

    `"data"` (relative to the current directory) is right for every way this
    app has run until now: cloned from git, `./start.sh`'d, or run from a
    source checkout in tests, the working directory is always the repo, and
    "data" next to it is obvious and easy to find.

    A PyInstaller-frozen, installed build breaks that assumption twice over.
    `sys.frozen` distinguishes it from every case above (never true running
    from source, so this can't change behaviour for the existing git-clone
    workflow or the test suite at all). And an installed app's own folder is
    Program Files, or wherever else it happens to run from, not writable by
    a standard Windows account, and not something a reinstall or an update
    should be trusted to leave alone. The OS-standard per-user data location
    is both writable and survives a reinstall; an explicit
    `TESSELLATE_DATA_DIR` always overrides this regardless of how the app is
    running.
    """
    if not getattr(sys, "frozen", False):
        return "data"
    if sys.platform == "win32":
        base = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = str(Path.home() / "Library" / "Application Support")
    else:
        base = os.getenv("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    # An install from before the rename keeps its notes in the old folder,
    # used while it exists and the new one does not, so an update never opens
    # an empty notebook beside the person's own. Nothing is moved.
    # installer.iss's DataDir follows the same rule.
    old, new = Path(base) / "MemoryMap AI", Path(base) / "Tessellate"  # brand: keep
    if old.is_dir() and not new.exists():
        return str(old)
    return str(new)


def resolved_data_dir() -> Path:
    """The data directory, for code that runs before (or without) a
    `ConfigManager`: the launcher's log file, the desktop window's profile,
    the Repair shortcut. The same answer `ConfigManager` gives, without
    creating anything.

    **Why this exists.** Those three read `TESSELLATE_DATA_DIR` with a bare
    `"data"` fallback, which is right for a source checkout and wrong for the
    installed Windows app, where the notes are in `%APPDATA%\\MemoryMap AI`
    and nothing sets the variable. The packaged build's log and window
    profile landed in `data\\` under whatever folder Windows started it in
    (the install folder, or `System32`, which a standard account cannot
    write), and the Start Menu's "Repair Tessellate" cleared a folder that
    held nothing, so the repair repaired nothing. Every packaging smoke set
    the variable, which is why none of them saw it.
    """
    return Path(os.getenv("TESSELLATE_DATA_DIR") or _default_data_dir()).resolve()


def _owner_only(folder: Path) -> None:
    """The notebook folder readable by its owner alone (SEC-13, security audit
    2026-10-05): the database, its WAL, backups and uploads were 0644 in a
    0755 folder, so any account on a shared Unix machine could copy them.
    0700 on the folder closes everything under it, whatever each file's own
    mode. Only for a folder that is a notebook (new, empty, or holding the
    database), never one somebody pointed the app at that is something else.
    Best effort: a filesystem without Unix modes just keeps its own rules."""
    if os.name != "posix":
        return
    try:
        if folder.stat().st_mode & 0o077:
            folder.chmod(0o700)
    except OSError:
        pass  # not ours to change (another owner, a read-only mount)


def default_preferences() -> dict[str, Any]:
    """What a notebook that never saved a preference reads.

    Shared by the load below and by Settings' reset (GET /preferences/defaults),
    so a reset puts back exactly what a fresh install is given.
    """
    prefs = dict(DEFAULT_PREFERENCES)
    # A source checkout (git clone + start.sh/start.bat) updates on every
    # launch via `git pull` on whatever branch is checked out: that IS
    # tracking main. Defaulting such an install to "stable" would point
    # its *other* update path (routes_update.py's GitHub-releases check)
    # at a channel that install has no way to actually apply anyway
    # (can_auto_apply requires a frozen Windows build), so it would just
    # silently do nothing useful. A packaged Windows install has the
    # opposite situation, no git pull, no main branch to track: so it
    # keeps "stable", the one channel it can act on. Overridden below by
    # whatever the user has actually saved, the moment they have ever
    # touched the setting themselves.
    source_install = not getattr(sys, "frozen", False)
    prefs["update_channel"] = "main" if source_install else "stable"
    return prefs


class ConfigManager:
    """Knows the app's folders, files, and saved preferences."""

    def __init__(self, data_dir: str | os.PathLike[str] | None = None) -> None:
        # .env lets a user relocate their data without touching code.
        load_dotenv()
        import tessellate

        tessellate._adopt_old_environment()  # a .env from before the rename
        self.data_dir = Path(
            data_dir or os.getenv("TESSELLATE_DATA_DIR") or _default_data_dir()
        ).resolve()
        notebook = (
            not self.data_dir.exists()
            or (self.data_dir / DB_NAME).exists()
            or (self.data_dir / OLD_DB_NAME).exists()
            or not any(self.data_dir.iterdir())  # made empty for the app to fill
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if notebook:
            _owner_only(self.data_dir)

        self.db_path = _adopt_old_db(self.data_dir)
        self.preferences_path = self.data_dir / "preferences.json"
        # Attached files live next to the data dir, so wiping
        # one without the other can't happen by accident.
        self.uploads_dir = self.data_dir / "uploads"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")

        self._preferences = self._load_preferences()

    def _load_preferences(self) -> dict[str, Any]:
        """Merge saved preferences over the defaults.

        A missing or corrupt preferences file must never stop the app
        from starting: we just fall back to defaults.
        """
        prefs = default_preferences()
        # `auto_update_enabled` used to default on for a source checkout
        # (INBOX 221), so the launchers pulled on every launch of a clone
        # nobody had asked. The owner's decision of 2026-10-05, "Ask once":
        # off for every install until the person answers, which
        # `update_choice_made` records (routes_update.record_update_choice).
        if self.preferences_path.exists():
            try:
                prefs.update(json.loads(self.preferences_path.read_text()))
            except (OSError, json.JSONDecodeError) as exc:
                # Starting on defaults is the right behaviour; doing it
                # silently is not. Every setting the user has ever chosen has
                # just reverted, and without this line the only clue is that
                # the app "forgot" everything.
                logging.getLogger("tessellate.config").warning(
                    "couldn't read %s (%s): starting from the default "
                    "preferences; your saved settings are not lost unless "
                    "something writes over the file",
                    self.preferences_path.name,
                    type(exc).__name__,
                )
        return prefs

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self._preferences.get(key, default)

    def all_preferences(self) -> dict[str, Any]:
        """Every setting, as a copy, for the support bundle to redact.

        A copy rather than the live dict: a caller that only means to read
        should not be able to edit the app's settings by accident.
        """
        return dict(self._preferences)

    def merge_preferences(self, values: dict[str, Any]) -> None:
        """Set many settings with one atomic write (a restored backup's)."""
        if not values:
            return
        self._preferences.update(values)
        atomic_write_json(self.preferences_path, self._preferences)

    def unset_preference(self, key: str) -> None:
        """Put a setting back to never set, so its default applies again."""
        if key in self._preferences:
            del self._preferences[key]
            atomic_write_json(self.preferences_path, self._preferences)

    def set_preference(self, key: str, value: Any) -> None:
        """Change a preference and persist it to disk immediately,
        so a crash never loses a settings change.

        Written atomically (temp file + fsync + rename): `preferences.json`
        sits outside the database's own transaction boundary and holds
        `llm_api_key` plus every setting the user has ever changed, so a
        plain truncate-and-write here is the one place in the app where a
        `kill -9` or power loss mid-write could corrupt live state.
        """
        self._preferences[key] = value
        atomic_write_json(self.preferences_path, self._preferences)


def days_from_today(day, today) -> str:  # noqa: ANN001
    """'8 days ago', 'today', 'in 3 days': a resolved date said relative to the
    reader's today, for every prompt that hands a model a note's time words
    (INBOX 441: a two-week-old note's "this Friday" read as this week's). A
    small model computes weekday distances badly; it reads this correctly."""
    gap = (day - today).days
    if gap == 0:
        return "today"
    if gap in (1, -1):
        return "tomorrow" if gap == 1 else "yesterday"
    return f"in {gap} days" if gap > 0 else f"{-gap} days ago"


_WEEK_CHOICES = {"monday": 0, "saturday": 5, "sunday": 6}


def week_first_day(config: "ConfigManager") -> int:
    """The person's first day of the week as Python's weekday (0 Monday).

    Their choice in Settings wins; on "auto" it is the day the browser's
    locale reports (`week_start_locale`), and Monday when it reported none.
    """
    choice = str(config.get_preference("week_start", "auto") or "auto")
    if choice in _WEEK_CHOICES:
        return _WEEK_CHOICES[choice]
    try:
        reported = int(config.get_preference("week_start_locale", 0))
    except (TypeError, ValueError):
        return 0
    return reported if 0 <= reported <= 6 else 0


def user_now(config: "ConfigManager | None") -> datetime:
    """Right now, on the user's own clock.

    Everything is *stored* in UTC, that part is not negotiable, since a
    notebook has to survive its owner changing timezone. But anything the AI
    reasons about ("in ten minutes", "tomorrow at 9", "what did I save today")
    has to be resolved against the wall clock the user is actually reading, or
    it silently lands hours out.

    Falls back to the server's local zone when no timezone has been reported,
    which is right for the ordinary case of app and browser on one machine,
    and when there are no settings yet (a prompt built before the app starts).
    """
    name = str(config.get_preference("timezone", "") or "").strip() if config else ""
    if name:
        try:
            return datetime.now(ZoneInfo(name))
        except (ZoneInfoNotFoundError, ValueError):
            # A stale or hand-edited zone name must never break the app.
            logging.getLogger("tessellate.config").warning(
                "unknown timezone %r in preferences; using the server's", name
            )
    return datetime.now(timezone.utc).astimezone()
