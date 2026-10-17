"""An error toast is for a fault, and only a fault (the owner's end-to-end pass,
INBOX 648 and its sweep: about a hundred calls showed the red style and
"Report this" for a normal situation, so a person pressing Dictate without the
voice add-on, Compress on an empty chat or Add on an empty reminder thought the
app was broken; the classification table is
docs/roadmap/archive/agent-remaining/toasts-1006.md).

The rule, enforced here because nothing else can see it:

- `toast(message, true)` is the red toast with "Report this", which mails the
  owner a support bundle. It is for a real fault: a failed request, a network
  error, an exception. A failed request that the server refused with a 4xx is
  shown plain at run time by the helper itself (`toast.refused`), so the many
  `toast(error.message, true)` catch blocks need no per-site edit.
- `toast(message, "info")` is the plain toast for a situation the app expects:
  a check on what the person entered or picked, an empty state, an add-on or
  model that is off, a limit set on purpose, a capability the browser lacks.
  It never carries "Report this" and it ignores "mute notifications", because
  it answers something the person just pressed.

So a call that passes `true` with a message of its own (a literal, not a
failed request's `.message`) must be listed in `FAULTS` below with the reason
it is a fault. Adding a new one without a reason fails; the usual right answer
is `"info"`.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"

#: Calls whose message is an expected situation: each must be an "info" toast.
#: Keyed by file, then the first argument's source text (whitespace folded).
EXPECTED = {
    'improve-panel.js': [
        '"Write something first, then improve it."',
    ],
    'ai-tools.js': [
        '"Pick an embedding model first, e.g. nomic-embed-text."',
    ],
    'app.js': [
    ],
    'ask-history.js': [
        '"That question is no longer in your history."',
    ],
    'attachment-actions.js': [
        '`Describing a file needs the local AI. ${AI_OFFLINE_HINT}.`',
    ],
    'capture-ask.js': [
        '"Couldn\'t read the clipboard, so that part of the template is empty."',
    ],
    'companion-menu.js': [
        '"Give the companion a name first."',
        '`You can keep ${NMB_PRESET_MAX} saved companions: delete one first.`',
    ],
    'categories-panel.js': [
        '"Name the new category first."',
        '"Tick the notes to move first."',
    ],
    'chat-attach.js': [
        '"The model returned nothing that time. Try again."',
    ],
    'chat.js': [
        '"Turn on Web search first, reading a page needs it."',
    ],
    'documents-code.js': [
        '`Emmet cannot read "${abbr}" as an abbreviation.`',
        '"Formatting is for code documents."',
        '"Select the lines to format first."',
        'refusal',
        '"The text changed while it was being checked. Format again."',
        'result.error',
        '"That fix no longer applies: the text has changed since it was offered."',
    ],
    'documents-prose.js': [
        '"That text has changed since it was checked."',
        '"Save the document first."',
        '"This window has no speech voices to read with."',
    ],
    'documents.js': [
        '`${what} is not available here.`',
        '"That section cannot go inside itself."',
        '"Give the document a title first, a block link is named by it."',
        '"Put the caret in a paragraph first."',
        '"That block is not in this document any more."',
        '`Nothing called "${name}" yet.`',
        '"Open a document first."',
        '"Full screen is not available in this window."',
        '"That text has changed, the list is refreshed."',
        '"Nothing left to fix."',
        '"Save the document first."',
        '(body && body.message) || "No other wordings came back for that one."',
        '"Nothing to discuss yet."',
        '"Nothing to check yet."',
        '"One word at a time: letters, with an apostrophe or hyphen inside."',
        '"No words found in that file. One word per line."',
        '"The dictionary is empty, so there is nothing to export."',
    ],
    'graph.js': [
        '`That ${isDocument ? "document" : "note"} is not on the graph right now: a filter or the view may be hiding it.`',
        '"Nothing to export yet."',
    ],
    'library.js': [
        '"A note can\'t be linked to itself."',
        'chosen.said',
        '"There is nothing to ask about yet. Read the page first."',
        '"There is nothing to copy yet."',
        '"There is nothing to save yet."',
        'updated.message || (image._isImage ? "No description was written. Is a vision model running in Settings > Models?" : "No description was written. Check a model is running in Settings > Models.")',
        '"A bookmark needs a URL."',
    ],
    'lightbox-actions.js': [
        '"Nothing in the Library gallery yet, upload one from Library → Files & Images first."',
    ],
    'media.js': [
        '"Microphone access was blocked, allow it in your browser."',
        '"This browser has no text-to-speech voices."',
    ],
    'note-edit-panels.js': [
        '"A note needs some text. To remove it, use Move to bin in its menu."',
    ],
    'note-panels.js': [
        'draftFirst ? "A draft can\'t be linked to a saved note. Save the draft first." : "A saved note can\'t be linked to a draft. Save the draft first."',
    ],
    'pick-row.js': [
        'shape.full || "That\'s as many as one message can carry."',
    ],
    'questions-view.js': [
        '"Reading is paused in Settings, What it learned."',
    ],
    'selection.js': [
        '"Extracting notes needs the local AI."',
    ],
    'settings-controls.js': [
        '"No skills found in that file."',
        '"No personas found in that file."',
        '"Restart isn\'t available in this build, close and reopen Tessellate by hand."',
    ],
    'settings-models.js': [
        '"Couldn\'t copy it from here."',
        '`${state.installed} is in use for ${state.roles.join(" and ")}. Choose another model there first.`',
    ],
    'settings-packages.js': [
        'body.running ? busy : "Nothing here is installed yet."',
        'body.running ? busy : extra.unavailable',
        'busy',
    ],
    'settings-wiring.js': [
        '"Only images can be attached to a chat message right now."',
    ],
    'quick-note.js': [
        '"Couldn\'t read the clipboard here. Paste into Capture instead."',
        '"There is no text on the clipboard to save."',
    ],
    'settings.js': [
        '"Nothing to copy: the filters above are hiding every record."',
        '"Give the look a name first."',
        '`You can keep ${MAX_CUSTOM_THEMES} saved looks: delete one first.`',
    ],
    'sheets-selects.js': [
        '"An empty answer isn\'t a correction: delete the message instead."',
    ],
    'shell-reminders.js': [
        '"A reminder needs text and a time."',
    ],
    'skills.js': [
        '`“${skill.name}” needs ${item.label || item.name}.`',
        '"Tick some notes first."',
    ],
    'suggestions-inbox.js': [
        '"Marked what I could, Atlas isn\'t running, so none could be put into words yet."',
        '"Atlas isn\'t running, so no reasons could be guessed."',
    ],
    'tag-manager.js': [
        '"Type a tag to add, or tick one to remove."',
    ],
    'usage-ledger.js': [
        '"Couldn\'t copy here. Select the command and copy it."',
    ],
    'whiteboard-interchange.js': [
        '"That SVG was not exported from a board here, so it has no board inside it. Insert it as a picture instead."',
    ],
    'whiteboard-library.js': [
        '"That file is too large to be a library (8 MB at most)."',
        '"That file is not a Tessellate library."',
    ],
    'whiteboard-map.js': [
        '"That topic\'s link is not a web address."',
        '"A topic\'s link has to be an http, https or mailto address."',
        '"That file is not a picture."',
        '`That branch has ${subtree.length} topics: copying stops at ${WB_MAP_COPY_MAX}.`',
        '`"${wbMapLabel(source)}" is already under "${wbMapLabel(target)}": turn the cross-link around first.`',
        '"A summary covers topics side by side under one parent."',
        '"That day has gone: pick a later due date for a reminder."',
    ],
    'whiteboard.js': [
        '"The default board keeps the theme\'s look. Make a board of your own to give it one."',
        '`A thread holds ${WB_COMMENTS_MAX} comments. Delete one first.`',
        '"There is nothing in the outline to build."',
        '"That file is empty."',
        '`That outline is ${content.length.toLocaleString()} characters: the limit is ${WB_MAX_IMPORT_CHARS.toLocaleString()}.`',
        '"Allow pop-ups to export as PDF, it opens Print, then Save as PDF."',
        '"The default board cannot change kind. Make a new board to start a mind map."',
        '"Drop a note from the Library onto the board. That was not a note."',
        '"Drop an outline to import it: OPML, FreeMind, XMind, Markdown or plain text."',
    ],
}

#: Rule 4 (2026-10-10): situations the app expects, moved here from FAULTS.
EXPECTED_RULE4 = {'settings-wiring.js': ['body.warning'], 'attachment-actions.js': ['"That upload is no longer in the Library; it may have been deleted."',
        '"That file is no longer in the Library; it may have been deleted."'], 'documents-code.js': ['"Formatting needs the code editor, which has not loaded."'], 'whiteboard-library.js': ['"That icon is not in the library\'s set."'], 'documents.js': ['"The chat isn\'t available right now."'], 'library.js': ['"The chat isn\'t available right now."'], 'documents-prose.js': ['`Reading stopped: ${event.error || "the voice did not answer"}.`']}
for _name, _messages in EXPECTED_RULE4.items():
    EXPECTED.setdefault(_name, []).extend(_messages)

#: Calls that keep the error style with a literal message, with why each is a
#: fault. Anything that passes `true` and is not a failed request's own
#: `.message` has to appear here.
FAULTS = {
    'app.js': {
        '"Can\'t reach the Tessellate server. Is it running?"': 'network failure: the server cannot be reached',
    },
    'chat-attach.js': {
        '"Couldn\'t save this chat turn."': 'saving a chat turn failed after the model answered: lost data',
        '"Couldn\'t delete that message."': 'delete request failed',
        '"Couldn\'t delete this chat."': 'delete request failed',
    },
    'documents-code.js': {
        '"Emmet could not be loaded, so nothing was wrapped."': 'the Emmet module failed to load: a broken asset',
    },
    'documents.js': {
        '"The Word writer could not be loaded."': 'the lazy script failed to load: a file missing from the install or a broken fetch',
        '"Couldn\'t open that version."': 'fetching a saved version failed',
        '"The code panel could not be loaded."': 'the lazy script failed to load: a file missing from the install or a broken fetch',
    },
    'graph-canvas.js': {
        '"The moved notes were not pinned where you left them."': 'the pin save after a group drag failed: the places shown are not the places kept',
    },
    'library.js': {
        '`The topic was not renamed: ${e?.message || e}.`': 'the rename request failed: the name shown is not the name kept',
        '`${failed} item${failed === 1 ? "" : "s"} couldn\'t be restored.`': 'a bulk restore partly failed',
        '`${failed} item${failed === 1 ? "" : "s"} couldn\'t be deleted.`': 'a bulk delete partly failed',
        '`${failed} document${failed === 1 ? "" : "s"} couldn\'t be deleted.`': 'a bulk delete partly failed',
        '"That region couldn\'t be cut out of the page."': 'cutting the region out of the page image failed',
        '`${failed} board${failed === 1 ? "" : "s"} couldn\'t be deleted.`': 'a bulk delete partly failed',
        '`${failed} bookmark${failed === 1 ? "" : "s"} couldn\'t be deleted.`': 'a bulk delete partly failed',
    },
    'lightbox-view.js': {
        '"Couldn\'t save that file."': 'saving the file failed',
    },
    'lightbox-actions.js': {
        '"Couldn\'t load the Library gallery."': 'loading the gallery failed',
    },
    'menus.js': {
        '"Couldn\'t read this note."': 'reading a note failed',
    },
    'note-properties.js': {
        '"Couldn\'t read this note\'s properties."': "reading a note's properties failed",
    },
    'settings-controls.js': {
        '(status && status.textContent) || "Couldn\'t apply the update."': "the update step failed; the text is the step's own error",
        'status.textContent || "Couldn\'t install that version."': "the install step failed; the text is the step's own error",
        'wentAway ? "The app hasn\'t come back yet. Start it again by hand." : "The app didn\'t restart. Close and reopen it by hand."': "the restart did not happen or the app did not return; Try again restarts it",
    },
    'settings-health.js': {
        '"Couldn\'t save that setting."': 'saving a setting failed',
        '"Couldn\'t reset that setting."': 'resetting a setting failed',
    },
    'settings.js': {
        '"Couldn\'t reset those settings."': 'resetting settings failed',
    },
    'shell-reminders.js': {
        "`Couldn't delete ${left.length} of the reminders.`": 'a bulk delete partly failed',
        "`Couldn't bring back ${left.length} of the reminders.`": 'a bulk restore partly failed',
    },
    'update-dialogs.js': {
        'progress.textContent || "Couldn\'t apply the update."': "the update step failed; the text is the step's own error",
    },
    'whiteboard.js': {
        'voiceLine("failed", { what: "undo that" })': 'undo threw an exception',
        'voiceLine("failed", { what: "redo that" })': 'redo threw an exception',
        'voiceLine("failed", { what: "read that file" })': 'reading the chosen file threw',
        'voiceLine("failed", { what: "add that note to the board", why: why })': 'creating the node on the server failed',
    },
}

#: Calls whose second argument is computed. Each is pinned to what it computes.
DYNAMIC = {
    "status.js": {"isError"},  # agentActivityNotice and toast(): passes the caller's flag through
    "ai-tools.js": {'!/already running/i.test(error.message || "")'},  # a 409 "already running" is plain
    #: A failed request is red; the server's own refusal (started or removed false) is a plain notice.
    "settings-packages.js": {'result.failed ? true : result.started ? false : "info"', 'result.failed ? true : result.removed ? false : "info"'},
    "suggestions-inbox.js": {"linked < sure.length"},  # a partial link run
    "whiteboard.js": {"Boolean(left)"},  # a clear that left items behind
    "library.js": {'described?.caption ? false : "info"'},  # no caption written is plain
}


def _calls(src: str):
    """(line, [argument source, ...]) for every `toast(` call, parens balanced,
    strings and template literals skipped."""
    out = []
    for m in re.finditer(r"(?<![\w.$])toast\(", src):
        if src[max(0, m.start() - 9) : m.start()] == "function ":
            continue
        i, depth, cur, args, n = m.end(), 1, m.end(), [], len(src)
        while i < n and depth:
            c = src[i]
            if c in "'\"":
                q = c
                i += 1
                while i < n and src[i] != q:
                    i += 2 if src[i] == "\\" else 1
            elif c == "`":
                i += 1
                tdepth = 0
                while i < n:
                    if src[i] == "\\":
                        i += 2
                        continue
                    if src[i] == "`" and tdepth == 0:
                        break
                    if src[i : i + 2] == "${":
                        tdepth += 1
                        i += 2
                        continue
                    if src[i] == "}" and tdepth:
                        tdepth -= 1
                    i += 1
            elif c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
                if depth == 0:
                    args.append(src[cur:i])
                    break
            elif c == "," and depth == 1:
                args.append(src[cur:i])
                cur = i + 1
            i += 1
        args = [re.sub(r"\s+", " ", a).strip() for a in args]
        out.append((src.count("\n", 0, m.start()) + 1, args))
    return out


def _all_calls():
    for path in sorted(JS.glob("*.js")):
        for line, args in _calls(path.read_text(encoding="utf-8")):
            yield path.name, line, args


def _flag(args):
    return args[1] if len(args) > 1 else ""


def test_expected_situations_are_plain_toasts():
    seen = {name: set() for name in EXPECTED}
    for name, line, args in _all_calls():
        if name in EXPECTED and args and args[0] in EXPECTED[name]:
            seen[name].add(args[0])
            assert _flag(args) == '"info"', (
                f"{name}:{line} {args[0][:60]}: an expected situation must be "
                'toast(message, "info"), not the red error toast with Report this'
            )
    for name, messages in EXPECTED.items():
        missing = set(messages) - seen[name]
        assert not missing, f"{name}: stale entry in EXPECTED (renamed or removed): {sorted(missing)[:3]}"


def test_a_red_toast_with_its_own_message_names_its_fault():
    """The only `true` calls that need no entry are a failed request's own
    message (`error.message`, `err.message`, `e.message`): those are faults, and
    a 4xx refusal among them is shown plain by the helper."""
    unlisted = []
    for name, line, args in _all_calls():
        flag = _flag(args)
        if flag != "true":
            continue
        message = args[0]
        if re.search(r"\b(?:e|err|error)\.message\b", message):
            continue
        if message in FAULTS.get(name, {}):
            continue
        unlisted.append(f"{name}:{line} {message[:70]}")
    assert not unlisted, (
        "an error toast (red, with Report this) is for a fault only. If this is a "
        'situation the app expects (an entry check, an empty state, an add-on that is '
        'off), use toast(message, "info"). If it really is a fault, add it to FAULTS '
        "in this file with the reason:\n  " + "\n  ".join(unlisted)
    )


def test_every_fault_entry_still_exists_and_has_a_reason():
    live = {(n, a[0]) for n, _l, a in _all_calls() if _flag(a) == "true"}
    for name, entries in FAULTS.items():
        for message, reason in entries.items():
            assert reason.strip(), f"{name}: {message[:50]} has no reason"
            assert (name, message) in live, f"{name}: stale FAULTS entry {message[:60]}"


def test_a_computed_flag_is_one_of_the_known_ones():
    for name, line, args in _all_calls():
        flag = _flag(args)
        if flag in ("", "true", "false", '"info"') or flag.startswith("{"):
            continue
        assert flag in DYNAMIC.get(name, set()), (
            f"{name}:{line}: toast(..., {flag[:60]}) computes its error flag; "
            "list it in DYNAMIC with why, or make it a plain info toast"
        )


def test_report_this_has_one_home_and_the_helper_gates_it():
    homes = [p.name for p in JS.glob("*.js") if '"Report this"' in p.read_text(encoding="utf-8")]
    assert homes == ["status.js"], homes
    status = (JS / "status.js").read_text(encoding="utf-8")
    body = status[status.index("function toast(") : status.index("\n}\n", status.index("function toast(")) + 3]
    # "info" and a refused (4xx) message both downgrade to a plain, mute-proof toast
    # before the error branch that adds the button.
    assert 'isError === "info"' in body and "toast.refused" in body
    assert body.index("toast.refused") < body.index('"Report this"')
    assert "toast.refused = new Set();" in status
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert "if (response.status < 500) toast.refused.add(errMsg);" in app


# --- Rule 4: an error explains and offers (WORLD_CLASS_PLAN 28.1) -----------

#: Literal faults whose one action is the default, Open the logs (Settings,
#: Logs, where the why is written), because no retry or alternative fits the
#: call site yet. A ratchet: it only shrinks. Every other literal fault passes
#: `{ action: [label, fn] }` of its own.
LOGS_ACTION_CAP = 24


def test_every_error_toast_offers_one_action():
    status = (JS / "status.js").read_text(encoding="utf-8")
    body = status[status.index("function toast(") : status.index("\n}\n", status.index("function toast(")) + 3]
    assert 'action || ["Open the logs", () => openSettingsModal("logs")]' in body, (
        "an error toast without a caller's action must get Open the logs"
    )
    assert body.index("toastActionButton(note, label") < body.index('"Report this"')


def test_a_literal_fault_carries_its_own_action_or_is_counted():
    defaulted = []
    for name, line, args in _all_calls():
        if _flag(args) != "true" or re.search(r"\b(?:e|err|error)\.message\b", args[0]):
            continue
        if len(args) > 2 and "action:" in args[2]:
            continue
        defaulted.append(f"{name}:{line}")
    assert len(defaulted) <= LOGS_ACTION_CAP, (
        f"{len(defaulted)} literal error toasts fall back to Open the logs (cap {LOGS_ACTION_CAP}): "
        "give the new one { action: [\"Try again\", fn] } or an alternative:\n  " + "\n  ".join(defaulted)
    )


def test_api_retries_a_network_failure_of_a_read_before_saying_so():
    app = (JS / "app.js").read_text(encoding="utf-8")
    body = app[app.index("async function api(") : app.index("\napi.retries = 0;")]
    assert "attempt < 2 && networkErr instanceof TypeError" in body
    assert "/^(GET|HEAD)$/.test(fetchOptions.method" in body, "a write must never be resent"
    assert "api.retries++" in body
