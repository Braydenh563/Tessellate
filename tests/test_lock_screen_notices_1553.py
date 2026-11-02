"""INBOX 1553 (the owner): "this pill toggle doesnt have the sliding animation.
also when I loaded up the app, on the login screen there was a notification
saying my 25 minute timer had run out ... shouldnt it have come after I logged
in not before when I was on the lock screen?? should reminders and
notifications of the user's choice or not set as private show on the lock
screen if the user desires??"

Three things, each pinned here:

* (a) a segmented control whose chosen option is `aria-pressed` glides like
  the ones that use `.active` (the Dashboard's focus presets, among six);
* (b) nothing is announced while the lock screen is up or before the session
  is proven: a timer that ran out waits and speaks after the unlock;
* (c) Settings, Account, "Show timers and reminders on the lock screen", off by
  default and kept on this device: the lock card lists timers and the next
  reminders (not marked private) by title and time, never note text.

The clock code runs in node with stubs and a fixed clock (no real time)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


from tests._frozen_clock import FIXED_NOW, freeze_reminder_clock
from tests.test_clock_panel_1551 import CLOCK_PART, HARNESS, needs_node

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend/js"
CSS = ROOT / "frontend/css"
INDEX = (ROOT / "frontend/index.html").read_text(encoding="utf-8")

#: The shared harness, with the lock screen, the session proof and the digest's store added.
LOCK_HARNESS = (
    HARNESS.replace(
        "const sandbox = {",
        "const lockList = { el: null };\n"
        "const state = Object.assign({ locked: false, mode: 'unlock' }, __STATE__);\n"
        "const lock = { classList: { contains: (c) => c === 'hidden' && !state.locked }, get dataset() { return { mode: state.mode }; } };\n"
        "const sandbox = {",
    )
    .replace("prefsCache: {},", "prefsCache: __PREFS_CACHE__,")
    .replace("vm.createContext(sandbox);", "sandbox.window = sandbox; vm.createContext(sandbox);")
    .replace(
        "document: { addEventListener() {} },",
        "document: { addEventListener() {},\n"
        "  getElementById: (id) => (id === 'lock-notices' ? lockList.el : id === 'lock-forgot' ? { after(el) { lockList.el = el; } } : null),\n"
        "  createElement: () => ({ attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, remove() { lockList.el = null; }, replaceChildren(...kids) { this.kids = kids; } }) },",
    )
    .replace("$: (id) => (id === 'lock-overlay' ? null : chip),", "$: (id) => (id === 'lock-overlay' ? lock : chip),")
)


def _run(body: str, stored: dict | None = None, now: int = 1_700_000_000_000, prefs_cache: str = "{}", state: dict | None = None):
    script = (
        LOCK_HARNESS.replace("__STORED__", json.dumps(stored or {}))
        .replace("__NOW__", str(now))
        .replace("__PREFS_CACHE__", prefs_cache)
        .replace("__STATE__", json.dumps(state or {}))
        .replace("__CODE__", json.dumps(CLOCK_PART))
        .replace("__BODY__", body)
    )
    done = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60, env={"TZ": "UTC", "PATH": "/usr/bin:/bin:/usr/local/bin"})
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1])


def _ran_out(minutes: int = 25) -> dict:
    """A page that closed with a 25 minute timer running, opened an hour after it ended."""
    started = 1_700_000_000_000 - 3_600_000
    return {
        "utility-clocks": json.dumps(
            [{"id": "a-0", "kind": "timer", "name": f"{minutes} minute", "start": started, "end": started + minutes * 60_000, "len": minutes * 60_000}]
        )
    }


# --- (b) nothing is announced behind the lock screen ---------------------------

@needs_node
def test_a_timer_that_ran_out_is_not_announced_on_the_lock_screen():
    got = _run("tick(); tick(); out({n: run('utilityClocks.length')});", stored=_ran_out(), state={"locked": True})
    assert got["toasts"] == [] and got["notes"] == [] and got["chimes"] == [], "nothing while locked"
    assert got["n"] == 1, "the timer waits, it is not dropped"


@needs_node
def test_it_is_announced_once_after_the_unlock():
    got = _run(
        "tick(); tick(); const held = toasts.length; state.locked = false; tick(); tick(); tick();"
        "out({n: run('utilityClocks.length'), held});",
        stored=_ran_out(),
        state={"locked": True},
    )
    assert got["held"] == 0
    assert got["toasts"] == ["Time is up: the 25 minute timer has finished."]
    assert len(got["notes"]) == 1 and len(got["chimes"]) == 1
    assert got["n"] == 0


@needs_node
def test_nothing_is_announced_before_the_session_is_proven():
    """At boot the overlay is still hidden while `/auth/status` is on its way, and a
    token left from before a restart is stale: until a request has been accepted
    (the preferences are in) the app is not known to be open."""
    got = _run("tick(); tick(); out({n: run('utilityClocks.length')});", stored=_ran_out(), prefs_cache="null")
    assert got["toasts"] == [] and got["n"] == 1
    late = _run("tick(); sandbox.prefsCache = {}; tick(); out({n: run('utilityClocks.length')});", stored=_ran_out(), prefs_cache="null")
    assert len(late["toasts"]) == 1 and late["n"] == 0


@needs_node
def test_a_password_prompt_over_the_open_app_does_not_hold_the_timer():
    got = _run("tick(); out({});", stored=_ran_out(), state={"locked": True, "mode": "prompt"})
    assert len(got["toasts"]) == 1, "the lock card borrowed for one action is not the lock screen"


# --- (c) the lock screen's list ------------------------------------------------

def _save(rows: list) -> str:
    """The JS call that hands `lockNotices.save` these rows, as a quoted string for `run`."""
    return json.dumps("lockNotices.save(" + json.dumps(rows) + ")")


def _reminder(i: int, text: str, due: str, **extra) -> dict:
    return {"id": i, "text": text, "due_at": due, "done": False, "private": False, "entry_preview": "NOTE TEXT", **extra}


@needs_node
def test_the_digest_keeps_a_title_and_a_time_and_skips_private_and_done_reminders():
    rows = [
        _reminder(1, "Call the dentist", "2023-11-15T09:30:00"),
        _reminder(2, "Tax return", "2023-11-14T12:00:00", private=True),
        _reminder(3, "Old thing", "2023-11-13T12:00:00", done=True),
        _reminder(4, "Pay rent", "2023-11-14T08:00:00", entry_preview="the landlord's number is 555"),
    ]
    got = _run(
        f"sandbox.prefs.set('lock-notices', 'on'); run({_save(rows)});"
        "out({digest: store.get('lock-digest')});"
    )
    digest = json.loads(got["digest"])
    assert [r["t"] for r in digest] == ["Pay rent", "Call the dentist"], "soonest first, no private, no done"
    assert all(set(r) == {"t", "d"} for r in digest), "a title and a time, nothing else"
    assert "555" not in got["digest"] and "NOTE TEXT" not in got["digest"]


@needs_node
def test_the_digest_is_five_rows_at_most_and_is_dropped_when_the_switch_is_off():
    rows = [_reminder(i, f"Thing {i}", f"2023-11-{10 + i:02d}T09:00:00") for i in range(1, 9)]
    got = _run(f"sandbox.prefs.set('lock-notices', 'on'); run({_save(rows)}); out({{digest: store.get('lock-digest')}});")
    assert len(json.loads(got["digest"])) == 5
    off = _run(f"sandbox.prefs.set('lock-digest', '[]'); run({_save(rows)}); out({{has: store.has('lock-digest')}});")
    assert off["has"] is False, "turning it off removes what was kept"


@needs_node
def test_the_lock_list_is_empty_by_default_and_lists_timers_then_reminders_when_on():
    digest = json.dumps([{"t": "Call the dentist", "d": "2023-11-15T09:30:00"}])
    off = _run("out({rows: run('lockNotices.rows()')});", stored={"lock-digest": digest})
    assert off["rows"] == [], "off unless the person turned it on"
    started = 1_700_000_000_000
    clocks = json.dumps(
        [
            {"id": "a-0", "kind": "timer", "name": "25 minute", "start": started, "end": started + 754_000, "len": 1_500_000},
            {"id": "a-1", "kind": "timer", "name": "5 minute", "start": started - 400_000, "end": started - 100_000, "len": 300_000},
            {"id": "a-2", "kind": "stopwatch", "name": "Stopwatch", "start": started - 9_000, "end": started - 9_000},
        ]
    )
    on = _run(
        "out({rows: run('lockNotices.rows()')});",
        stored={"lock-notices": "on", "lock-digest": digest, "utility-clocks": clocks},
        state={"locked": True},
    )
    assert on["rows"][:2] == ["25 minute timer, 12:34 left", "5 minute timer, time is up"], "timers first; a stopwatch is not one"
    assert len(on["rows"]) == 3 and on["rows"][2].startswith("Call the dentist, ") and "15" in on["rows"][2], "then the reminders: a title and a time"


@needs_node
def test_the_lock_card_lists_them_only_while_the_lock_screen_is_up_and_the_switch_is_on():
    started = 1_700_000_000_000
    clocks = json.dumps([{"id": "a-0", "kind": "timer", "name": "25 minute", "start": started, "end": started + 754_000, "len": 1_500_000}])
    digest = json.dumps([{"t": "Call the dentist", "d": "2023-11-15T09:30:00"}])
    stored = {"lock-notices": "on", "lock-digest": digest, "utility-clocks": clocks}
    show = "out({list: lockList.el && lockList.el.kids.map((k) => k.textContent), label: lockList.el && lockList.el.attrs['aria-label']});"
    up = _run(show, stored=stored, state={"locked": True})
    assert up["list"][0] == "25 minute timer, 12:34 left" and up["list"][1].startswith("Call the dentist, ")
    assert up["label"] == "Timers and reminders"
    assert _run("state.locked = false; tick(); " + show, stored=stored, state={"locked": True})["list"] is None, "gone once the app is open"
    assert _run(show, stored={**stored, "lock-notices": "off"}, state={"locked": True})["list"] is None, "off by default"
    assert _run(show, stored=stored, state={"locked": True, "mode": "setup"})["list"] is None, "not on the first-run card"
    assert _run(show, stored=stored, state={"locked": True, "mode": "prompt"})["list"] is None, "not on a password prompt"


# --- the setting and its wiring ------------------------------------------------

def test_the_switch_is_in_settings_off_by_default_and_worded_as_asked():
    box = re.search(r'<input type="checkbox" id="lock-notices-toggle"[^>]*>', INDEX)
    assert box, "a checkbox in Settings"
    assert "checked" not in box.group(0), "off by default"
    around = INDEX[box.start() - 400 : box.end() + 900]
    assert "Show timers and reminders on the lock screen" in around
    assert "never the text of a note" in around or "never note text" in around


def test_the_switch_is_kept_on_this_device_and_wired_with_the_settings_rows():
    rows = (JS / "settings-rows.js").read_text(encoding="utf-8")
    tail = rows[rows.index('$("lock-notices-toggle")'):][:600]
    assert 'prefs.get("lock-notices", null) === "on"' in tail, "off unless turned on"
    assert 'prefs.set("lock-notices", "on")' in tail and 'prefs.remove("lock-notices")' in tail, "the key goes when it is off"
    assert 'ensureModule("utilities").then(() => lockNotices.refresh())' in tail, "turning it on loads the lazy module and fills the list"


def test_the_eager_scripts_carry_none_of_it():
    """The gzip cap: the lock list wraps the two eager functions from the lazy module, and
    the boot scripts keep the lines they had."""
    for name in ("status.js", "settings-wiring.js"):
        assert "lockNotices" not in (JS / name).read_text(encoding="utf-8"), name
    find = (JS / "spaces-find.js").read_text(encoding="utf-8")
    assert 'if (prefs.has("utility-clocks")) ensureModule("utilities")' in find, "the digest's key rides on utility-clocks"
    tools = (JS / "utility-tools.js").read_text(encoding="utf-8")
    assert '["paintReminderList", lockSave], ["showLockScreen", paintLock]' in tools
    assert 'else if (utilityOps.lockOn()) prefs.set("utility-clocks", "[]")' in tools


def test_the_reminders_list_says_which_reminder_is_about_a_private_note(client, monkeypatch):
    """The lock screen's list leaves out a reminder that belongs to a private note
    (`private`, from the note's own flag); a plain one and a standalone one say False."""
    from datetime import timedelta

    from tessellate.core import crypto, deps
    from tessellate.core.database import Entry

    freeze_reminder_clock(monkeypatch)
    session = deps.get_db().session()
    secret = Entry(content=crypto.PREFIX + "not-real-ciphertext", is_private=True)
    plain = Entry(content="buy a birthday present")
    session.add_all([secret, plain])
    session.commit()
    ids = (secret.id, plain.id)
    session.close()
    due = (FIXED_NOW + timedelta(hours=1)).isoformat()
    made = {
        name: client.post("/reminders", json={"text": name, "due_at": due, **({"entry_id": entry_id} if entry_id else {})}).json()
        for name, entry_id in (("secret", ids[0]), ("plain", ids[1]), ("alone", None))
    }
    assert made["secret"]["private"] is True
    assert made["plain"]["private"] is False and made["alone"]["private"] is False
    assert {r["text"]: r["private"] for r in client.get("/reminders").json()} == {"secret": True, "plain": False, "alone": False}


# --- (a) every single-choice strip glides --------------------------------------

#: Each place a segmented control's chosen option is set from script: the glide finds it by
#: `.active`, so the class moves with `aria-pressed` (the strip's fill slides to it).
PRESSED_SETTERS = {
    "dashboard.js": "const chosen = focusTimer.mode",
    "capture-card.js": 'button.setAttribute("aria-pressed", String(button.dataset.mode === next));',
    "documents-history.js": 'other.setAttribute("aria-pressed", other === button ? "true" : "false");',
    "documents-export.js": 'b.setAttribute("aria-pressed", String(setup[key] === value));',
    "math-editor.js": 'b.setAttribute("aria-pressed", String((b.dataset.value === "display") === on));',
}


def test_a_segmented_control_that_sets_aria_pressed_sets_active_beside_it():
    for name, anchor in PRESSED_SETTERS.items():
        text = (JS / name).read_text(encoding="utf-8")
        near = text[text.index(anchor) :][:360]
        assert 'classList.toggle("active"' in near, name


def test_the_first_chosen_version_filter_starts_with_the_glide_marker():
    assert re.search(r'<button type="button" class="active" data-history-filter="all" aria-pressed="true"', INDEX)
