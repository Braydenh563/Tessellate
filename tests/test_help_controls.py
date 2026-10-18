"""The Guide can answer "what are all the keys and hidden features of X".

INBOX 410, the owner: "what if the user asks the guide for all the hidden
features, keybinds, controls, utility and more for features like the
whiteboard, mindmap and documents editor etc. can it answer those??" Before
this it could not: the whiteboard entry was two sentences with no key in it,
the documents entry named three, and the shortcuts entry still taught the "g"
chord the app had replaced with "m". Each surface now has a controls entry
written from its own handlers and shortcut tables, and a question that asks
for keys, controls or hidden features about a named surface is routed to that
surface's controls entry rather than to its one-paragraph description.
"""

from __future__ import annotations

import re

import pytest

from tessellate.ai import help_chat


def _first(question: str) -> str | None:
    ranked = help_chat._matching_topics(question)
    return ranked[0]["id"] if ranked else None


CONTROLS = {
    "whiteboard-controls",
    "mind-map-controls",
    "documents-controls",
    "graph-controls",
    "chat-controls",
    "notes-controls",
    "library-controls",
    "timeline-controls",
    "reminders-controls",
    "dashboard-controls",
    "hidden-features",
}


def test_every_surface_has_a_controls_entry():
    ids = {topic["id"] for topic in help_chat.HELP_TOPICS}
    assert CONTROLS <= ids, sorted(CONTROLS - ids)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("what are all the whiteboard shortcuts", "whiteboard-controls"),
        ("keyboard shortcuts for the whiteboard", "whiteboard-controls"),
        ("mind map keybinds", "mind-map-controls"),
        ("what are the document editor shortcuts", "documents-controls"),
        ("graph controls", "graph-controls"),
        ("hidden features", "hidden-features"),
        ("does the doc editor have emmet", "code-files"),
    ],
)
def test_a_controls_question_reaches_the_surface_controls_entry(question, expected):
    assert _first(question) == expected, help_chat._matching_topics(question)


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("what is the whiteboard", "whiteboard"),
        ("how do I make a mind map", "mind-maps"),
        ("what does the graph show", "graph"),
        ("how do i set a reminder", "reminders"),
    ],
)
def test_a_plain_question_still_gets_the_description(question, expected):
    """The controls entries are long on purpose; a question that asks what a
    thing is, with no word about keys or controls, is still answered by the
    one-paragraph entry."""
    assert _first(question) == expected, help_chat._matching_topics(question)


def test_a_question_naming_a_chord_finds_the_entry_that_documents_it():
    assert _first("what does F12 do") == "code-files"
    assert _first("what does ctrl shift f do in a document") in {"documents-controls", "code-files"}
    #: A chord an entry claims in its own keywords stays that entry's: Ctrl+P
    #: is Find anything's, however many controls entries mention it.
    assert _first("what does ctrl+p do") == "search"
    assert _first("what does cmd k do") == "command-palette"


def test_the_shortcuts_entry_teaches_the_m_chord_not_the_old_g_one():
    """The chord is "t" (alias "m") then a letter (settings-wiring.js, `TAB_JUMP_KEYS`); the entry
    said "g" for as long as the guide has existed."""
    body = next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == "shortcuts")
    assert "t then a letter" in body
    assert "g then a letter" not in body


def test_controls_entries_follow_the_copy_rules():
    for topic in help_chat.HELP_TOPICS:
        if topic["id"] not in CONTROLS | {"shortcuts", "code-files"}:
            continue
        body = topic["body"]
        assert chr(0x2014) not in body, topic["id"]
        #: A "!" only as a key to type (Emmet's own "!"), never ending a sentence.
        assert not re.search(r"\w!", body), topic["id"]
        assert body[0].isupper(), topic["id"]


# --- Freshness: the guide names every key the app's own tables bind ----------
#
# The entries above are prose, and prose about keys goes stale the day a key
# moves: the shortcuts entry taught "g then a letter" for months after the
# chord became "m". These read the tables the app binds from, the same way
# `test_frontend_shortcuts.py` reads `DEFAULT_SHORTCUTS`, and fail when the
# guide does not name a key. The fix for a failure is a sentence in the entry,
# never a looser match here.

from pathlib import Path  # noqa: E402
from tests._app_js import app_js_text  # noqa: E402

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
_ENTRY = re.compile(r'^\s*(\w+):\s*\{\s*keys:\s*"([^"]+)"', re.MULTILINE)


def _body(topic_id: str) -> str:
    return next(t["body"] for t in help_chat.HELP_TOPICS if t["id"] == topic_id)


def _table(source: str, start: str, end: str = "\n};") -> str:
    at = source.index(start)
    return source[at : source.index(end, at)]


def _named(key: str, body: str) -> bool:
    """A chord is named when it appears as written, or as the entries spell
    two of its keys for a reader ("Alt+Left", "Alt+Up"). A bare key ("/",
    "?") must stand on its own, and a chord must not be the head or tail of a
    longer one ("Ctrl+Z" inside "Ctrl+Shift+Z" is not Ctrl+Z)."""
    shown = key.replace("ArrowLeft", "Left").replace("ArrowRight", "Right")
    shown = shown.replace("↑", "Up").replace("↓", "Down")
    if len(shown) == 1:
        return bool(re.search(rf"(?:^|[\s(]){re.escape(shown)}(?=[\s),.;:])", body))
    return bool(re.search(rf"(?<![\w+]){re.escape(shown)}(?![\w+])", body))


def test_every_global_shortcut_is_in_the_shortcuts_entry():
    app = app_js_text()
    table = dict(_ENTRY.findall(_table(app, "const DEFAULT_SHORTCUTS")))
    assert len(table) > 15, "DEFAULT_SHORTCUTS has moved; this test cannot read it"
    body = _body("shortcuts")
    missing = sorted(f"{name} ({keys})" for name, keys in table.items() if not _named(keys, body))
    assert not missing, f"the shortcuts entry does not name: {missing}"


def test_every_m_chord_letter_is_in_the_hidden_features_entry():
    app = app_js_text()
    tabs = dict(re.findall(r'^\s*(\w): "(\w+)"', _table(app, "const TAB_JUMP_KEYS"), re.MULTILINE))
    actions = dict(
        re.findall(r'^\s*(\w): \{ label: "([^"]+)"', _table(app, "const CHORD_ACTIONS"), re.MULTILINE)
    )
    assert len(tabs) >= 7 and len(actions) >= 5, (tabs, actions)
    body = _body("hidden-features")
    wanted = {f"{k} ({v.capitalize()})" for k, v in tabs.items()} | {f"{k} ({v})" for k, v in actions.items()}
    missing = sorted(w for w in wanted if w not in body)
    assert not missing, f"the hidden features entry does not name: {missing}"


def test_the_m_chord_key_map_is_unchanged_by_the_redesign():
    """INBOX 484 redrew the `m` guide; every key it answers stays what it was.
    The guide's rows are built from these two tables, so a row and its key
    cannot drift; this pins the tables themselves."""
    app = app_js_text()
    tabs = dict(re.findall(r'^\s*(\w): "(\w+)"', _table(app, "const TAB_JUMP_KEYS"), re.MULTILINE))
    actions = dict(
        re.findall(r'^\s*(\w): \{ label: "([^"]+)"', _table(app, "const CHORD_ACTIONS"), re.MULTILINE)
    )
    assert tabs == {
        "d": "dashboard", "n": "notes", "c": "chat", "g": "graph",
        "l": "library", "i": "timeline", "r": "reminders",
    }
    assert actions == {
        "s": "Settings", "q": "Quick sketch", "v": "Record a meeting", "a": "Guide", "p": "Popup agent",
        "o": "OCR workspace",
    }
    hint = app[app.index("function showTabJumpHint(") :]
    hint = hint[: hint.index("\n}\n")]
    assert "Object.entries(TAB_JUMP_KEYS)" in hint and "Object.entries(CHORD_ACTIONS)" in hint


def test_every_document_command_key_is_in_the_editor_entries():
    docs = (FRONTEND / "js" / "documents.js").read_text(encoding="utf-8")
    table = _table(docs, "const DOC_COMMANDS = [", "\n];")
    #: "none" is a decision recorded in the table, not a key to name.
    #: Read as the string it is: "Ctrl+\\" in the source is the chord Ctrl+\.
    keys = {k.replace("\\\\", "\\") for k in re.findall(r'keys: "([^"]*)"', table) if k and k != "none"}
    assert len(keys) > 15, "DOC_COMMANDS has moved; this test cannot read it"
    body = _body("documents-controls") + " " + _body("code-files")
    missing = sorted(k for k in keys if not all(_named(part.strip(), body) for part in k.split(" / ")))
    assert not missing, f"the documents and code entries do not name: {missing}"


def test_every_whiteboard_tool_key_is_in_the_whiteboard_entry():
    board = (FRONTEND / "js" / "whiteboard.js").read_text(encoding="utf-8")
    tools = re.findall(r'^\s*(\w): "[\w-]+",', _table(board, "const WB_TOOL_KEYS", "\n  };"), re.MULTILINE)
    shifted = re.findall(r'^\s*(\w): "[\w-]+",', _table(board, "const WB_TOOL_SHIFT_KEYS", "\n  };"), re.MULTILINE)
    actions = re.findall(r'^\s*(\w): "[\w-]+",', _table(board, "const WB_ACTION_KEYS", "\n  };"), re.MULTILINE)
    assert len(tools) > 15, "WB_TOOL_KEYS has moved; this test cannot read it"
    body = _body("whiteboard-controls")
    listed = body[body.index("Tools:") : body.index("Moving around")]
    missing = [k.upper() for k in tools + actions if not re.search(rf"\b{k.upper()}\b", listed)]
    missing += [f"Shift+{k.upper()}" for k in shifted if f"Shift+{k.upper()}" not in listed]
    assert not missing, f"the whiteboard entry's tool list does not name: {missing}"


# --- The caps fit a controls answer -------------------------------------------
#
# A controls entry is long by design, and three caps were set when the
# longest entry was a few hundred characters. Measured when the entries
# landed: the offline answer to "what are all the whiteboard shortcuts" is
# 1,627 characters, and the route refused any history turn over 1,000, so the
# question *after* it failed with a 422 ("Something went wrong asking that").
# The client also sends its whole transcript (settings.js never trims
# `helpChatHistory`), and the route refused more than six turns, so the fifth
# question of any conversation failed the same way.


def _longest_offline_answer() -> str:
    return max(
        #: Either view of the answer (INBOX 787): the composed one the panel
        #: keeps, or the help text word for word.
        (
            text
            for t in help_chat.HELP_TOPICS
            for reply in [help_chat.offline_answer(t["id"].replace("-", " ") + " shortcuts")]
            for text in (reply["content"], (reply.get("system") or {}).get("content", ""))
        ),
        key=len,
    )


@pytest.mark.parametrize("route", ["/help/ask", "/help/ask/stream"])
def test_the_question_after_a_controls_answer_is_still_answered(client, route):
    #: The four entries at the reply budget were each split in two (board
    #: library, whiteboard keys, board format, mind map features), so "all the
    #: whiteboard shortcuts" is no longer one long answer; the case this guards
    #: is the longest answer the Guide can still give.
    assert len(_longest_offline_answer()) > help_chat.MAX_MESSAGE_CHARS, "the case this guards is a long answer"
    history = [
        {"role": "user", "content": "what are all the whiteboard shortcuts"},
        {"role": "assistant", "content": _longest_offline_answer()},
    ]
    response = client.post(route, json={"question": "and on the mind map?", "history": history})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("route", ["/help/ask", "/help/ask/stream"])
def test_a_long_conversation_keeps_being_answered(ai_client, fake_ollama, route):
    """Ten turns, as the panel sends them after five questions: the route
    keeps the most recent `MAX_HISTORY_TURNS`, which is all the prompt ever
    used, rather than refusing the question."""
    fake_ollama.librarian_reply = "Tab adds a child."
    history = [
        {"role": "user" if n % 2 == 0 else "assistant", "content": f"turn {n}"} for n in range(10)
    ]
    response = ai_client.post(route, json={"question": "how do I add a branch?", "history": history})
    assert response.status_code == 200, response.text
    sent = [m["content"] for m in fake_ollama.chat_calls[-1] if m["role"] in ("user", "assistant")]
    assert "turn 9" in sent and "turn 3" not in sent
    assert len(sent) == help_chat.MAX_HISTORY_TURNS + 1


def test_a_history_turn_is_still_bounded(client):
    over = "x" * (help_chat.MAX_HISTORY_TURN_CHARS + 1)
    response = client.post(
        "/help/ask", json={"question": "q", "history": [{"role": "assistant", "content": over}]}
    )
    assert response.status_code == 422


def test_the_history_cap_holds_the_longest_answer_the_guide_gives():
    assert len(_longest_offline_answer()) <= help_chat.MAX_HISTORY_TURN_CHARS


def test_the_guide_can_write_out_a_whole_controls_entry():
    """Online, the reply cap decides whether "list the whiteboard keys" ends
    mid-list. Four characters a token is the usual English estimate; keys and
    punctuation run denser, so three is the conservative one."""
    from tessellate.ai import presets

    longest = max(len(t["body"]) for t in help_chat.HELP_TOPICS)
    assert presets.resolve(presets.GUIDE_MODE).max_output_tokens >= longest / 3


def test_both_guide_routes_answer_in_the_guide_preset(ai_client, fake_ollama, monkeypatch):
    """`answer` asked for "quick" while `answer_stream` asked for the Guide's
    own preset, so the fallback path had Quick's cap and no thinking."""
    from tessellate.ai import presets

    modes: list[str | None] = []
    original = type(fake_ollama).chat

    def recording(self, model, messages, mode=None):
        modes.append(mode)
        return original(self, model, messages, mode=mode)

    monkeypatch.setattr(type(fake_ollama), "chat", recording)
    fake_ollama.librarian_reply = "Tab adds a child."
    assert ai_client.post("/help/ask", json={"question": "mind map keys"}).status_code == 200
    assert modes and modes[-1] == presets.GUIDE_MODE


def test_no_guide_topic_sits_at_the_reply_budget():
    """The four entries that sat at 1,917 to 1,919 of the 1,920 characters the
    Guide's reply cap holds (board library, whiteboard keys, board format, mind
    map features) are each two topics along their natural seam, so a later help
    edit has room: every body is under 1,600."""
    from tessellate.ai import presets

    budget = presets.resolve(presets.GUIDE_MODE).max_output_tokens * 3
    by_id = {t["id"]: len(t["body"]) for t in help_chat.HELP_TOPICS}
    for first, second in (
        ("board-library", "board-library-saving"),
        ("whiteboard-controls", "whiteboard-selection"),
        ("board-format", "board-connectors"),
        ("mind-map-features", "mind-map-import-export"),
    ):
        assert first in by_id and second in by_id, (first, second)
        assert by_id[first] < 1600 and by_id[second] < 1600, (first, by_id[first], second, by_id[second])
    assert max(by_id.values()) < budget


def test_no_guide_topic_sits_within_twenty_characters_of_the_reply_budget():
    """Five topics sat at 1,905 to 1,918 of the 1,920 characters the Guide's
    reply cap holds (ask-chat, chat-controls, lock, answers-from-notes,
    code-files), so any help edit for a new control had to cut something
    first. Trimmed to under 1,900 (OPEN row 1368); the next help edit that
    needs room takes it from a topic's second half into a topic of its own."""
    over = {t["id"]: len(t["body"]) for t in help_chat.HELP_TOPICS if len(t["body"]) >= 1900}
    assert not over, over
