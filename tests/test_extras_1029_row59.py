"""Audit 1029 rank 59 (X20, X24, X25, X27): four small honesty fixes.

- X20: with no model the Writing room's quick-start chips changed the kind and
  said nothing about why Draft would not run; Refine had the reason only in
  its title. A chip now writes that same sentence to the status line.
- X24: "Search by meaning is not working" toasted on every boot with no
  embedder; the toast is now once per browser session (the bell keeps it).
- X25: the greeting's name was cut mid-word with no ellipsis; it is clipped at
  a word with one.
- X27: the margin reader swallowed errors and forgot "Not this" on a date card
  (no source id); errors go to the lag log, and a date card is remembered by
  the day it names.

No clock is read: every function is run with stubs.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
CHAT_AGENT = (JS / "chat-agent.js").read_text(encoding="utf-8")
STATUS = (JS / "status.js").read_text(encoding="utf-8")
DASHBOARD = (JS / "dashboard.js").read_text(encoding="utf-8")
REMINDERS = (JS / "shell-reminders.js").read_text(encoding="utf-8")
MARGIN = (JS / "margin-reader.js").read_text(encoding="utf-8")

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _function(text: str, name: str) -> str:
    start = re.search(rf"\n(?:async )?function {name}\(", text).start() + 1
    return text[start : text.index("\n}\n", start) + 2]


def _run(script: str):
    run = subprocess.run([shutil.which("node"), "-e", script], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


# --- X20 --------------------------------------------------------------------


@needs_node
def test_a_quick_start_chip_says_why_when_no_model_is_connected() -> None:
    script = (
        _function(CHAT_AGENT, "draftChipOfflineNote")
        + """
        const AI_OFFLINE_HINT = "Connect a model in Settings";
        const refine = { dataset: { needsModel: "Refining needs a model connected" } };
        const said = [];
        const setDraftStatus = (text, isError) => said.push([text, !!isError]);
        const $ = () => refine;
        let off = true;
        const aiIsOff = () => off;
        draftChipOfflineNote();
        off = false;
        draftChipOfflineNote();
        console.log(JSON.stringify(said));
        """
    )
    assert _run(script) == [["Refining needs a model connected. Connect a model in Settings.", False]]


def test_every_chip_press_goes_through_the_offline_note() -> None:
    chips = _function(CHAT_AGENT, "renderDraftQuickstarts")
    assert "draftChipOfflineNote()" in chips
    sentence = re.search(r"`\$\{reason\}\. \$\{AI_OFFLINE_HINT\}\.`", STATUS)
    assert sentence, "the Refine title sentence this one must match moved"


# --- X24 --------------------------------------------------------------------


def _nudge() -> str:
    return (
        "const EMBEDDING_FALLBACK_MODEL = 'nomic-embed-text';\n"
        + _function(STATUS, "withoutEndStop")
        + _function(STATUS, "embeddingProblemDetail")
        + _function(STATUS, "embeddingToastDue")
        + _function(STATUS, "nudgeEmbeddingProblem")
    )

#: One page load: a fresh `embeddingNudgeSaid`, the shared `sessionStorage`, two different problems in a row.
_PAGE = """
function page(sessionStorage) {
  let embeddingNudgeSaid = "";
  let modelStatus = { embedding_error: "No embedder is installed" };
  const toasts = [], bell = [];
  const recordNotification = (n) => bell.push(n.key);
  const toastAction = (text) => toasts.push(text);
  const openSettingsModal = () => {};
  %s
  nudgeEmbeddingProblem();
  modelStatus = { embedding_error: "A different problem" };
  nudgeEmbeddingProblem();
  return { toasts: toasts.length, bell: bell.length };
}
"""


@needs_node
def test_the_search_toast_shows_once_per_session_not_once_per_boot() -> None:
    script = (
        _PAGE % _nudge()
        + """
        const data = {};
        const shared = { getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = v; } };
        console.log(JSON.stringify([page(shared), page(shared)]));
        """
    )
    first, second = _run(script)
    assert first["toasts"] == 1, "the first boot of a session says it once, even for a second problem"
    assert second["toasts"] == 0, "a reload in the same session stays quiet"
    assert first["bell"] == second["bell"] == 2, "the bell still records each problem"


@needs_node
def test_blocked_session_storage_still_toasts_once_per_page() -> None:
    script = (
        _PAGE % _nudge()
        + """
        const blocked = { getItem() { throw new Error("blocked"); }, setItem() { throw new Error("blocked"); } };
        console.log(JSON.stringify(page(blocked).toasts));
        """
    )
    # Two different problems in one page load: one toast each, as before this change.
    assert _run(script) == 2
    same = script.replace('modelStatus = { embedding_error: "A different problem" };', "")
    assert _run(same) == 1, "the same problem twice is still said once"


# --- X25 --------------------------------------------------------------------


@needs_node
def test_the_greeting_clips_a_long_name_at_a_word_with_an_ellipsis() -> None:
    name = "Bartholomew Maximilian Featherstonehaugh Ravenscroft the Third of Lower Wickham"
    script = (
        _function(REMINDERS, "clipText")
        + _function(DASHBOARD, "withDisplayName")
        + """
        const GREETING_NAME_MAX = %d;
        let prefsCache = { display_name: %s };
        const long = withDisplayName("Good morning", ".");
        prefsCache = { display_name: "Sam" };
        const short = withDisplayName("Good morning", ".");
        console.log(JSON.stringify({ long, short }));
        """
    )
    limit = int(re.search(r"const GREETING_NAME_MAX = (\d+);", DASHBOARD).group(1))
    out = _run(script % (limit, json.dumps(name)))
    assert out["short"] == "Good morning, Sam."
    greeting_name = out["long"].removeprefix("Good morning, ").removesuffix(".")
    assert greeting_name.endswith("…") and len(greeting_name) <= limit
    kept = greeting_name.removesuffix("…")
    assert name.startswith(kept) and name[len(kept)] == " ", "cut between words"


# --- X27 --------------------------------------------------------------------


@needs_node
def test_a_date_card_is_remembered_by_the_day_it_names() -> None:
    script = (
        _function(MARGIN, "marginCardKey")
        + """
        const date = { kind: "date", when: "2026-11-02T09:00", phrase: "Monday" };
        const note = { kind: "related", source_entry_id: 7 };
        const bare = { kind: "related" };
        console.log(JSON.stringify([marginCardKey(date), marginCardKey(note), marginCardKey(bare)]));
        """
    )
    assert _run(script) == ["date:2026-11-02T09:00", 7, None]


def test_the_dismissal_uses_the_key_and_the_server_gets_only_ids() -> None:
    card = _function(MARGIN, "marginCard")
    assert "const key = marginCardKey(card)" in card and "marginDismissed.add(key)" in card
    ask = _function(MARGIN, "marginAsk")
    assert "!marginDismissed.has(marginCardKey(c))" in ask
    assert "filter(Number.isInteger)" in ask, "date keys are strings and the server's exclude is a list of ids"


@needs_node
def test_a_margin_reader_error_goes_to_the_lag_log() -> None:
    script = (
        _function(MARGIN, "marginLogError")
        + """
        const logged = [];
        const window = { lagNoteError: (message, stack) => logged.push([message, stack]) };
        marginLogError(Object.assign(new Error("boom"), { stack: "Error: boom\\n at x" }));
        const bare = {};
        window.lagNoteError = undefined;
        marginLogError(new Error("no lag log loaded"));
        console.log(JSON.stringify(logged));
        """
    )
    assert _run(script) == [["Margin reader: boom", "Error: boom\n at x"]]


def test_the_margin_reader_no_longer_swallows_in_its_ask() -> None:
    ask = _function(MARGIN, "marginAsk")
    assert "catch (error)" in ask and "marginLogError(error)" in ask
    assert "A margin that cannot read says nothing rather than a toast per pause." in ask, "still no toast per pause"
