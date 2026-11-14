"""L-chat-141 (CHAT_PLAN decision 69): ghost-text completions in the chat box,
from the person's own tags, titles and recent searches. No model, one switch."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "frontend" / "js"
SRC = (JS / "chat-ghost.js").read_text(encoding="utf-8")


def _rest(text, pool):
    script = (
        "const w={};global.window=w;global.prefs={set(){},get:()=>'on'};"
        + SRC
        + f";console.log(JSON.stringify(w.chatGhostRest({json.dumps(text)},{json.dumps(pool)})))"
    )
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_completes_the_last_word_from_a_tag_or_title():
    pool = ["sourdough", "Weekly review"]
    assert _rest("how is my sour", pool) == "dough"
    assert _rest("show the weekly rev", pool) == "iew"


def test_nothing_for_short_words_code_multiline_or_a_finished_word():
    pool = ["sourdough"]
    assert _rest("so", pool) == ""
    assert _rest("`sour", pool) == ""
    assert _rest("line one\nsour", pool) == ""
    assert _rest("sourdough", pool) == ""
    assert _rest("sour ", pool) == ""


def test_it_is_lazy_one_switch_and_accept_rate_kept():
    app = (JS / "app.js").read_text(encoding="utf-8")
    assert 'chatGhost: ["/js/chat-ghost.js"]' in app
    ask = (JS / "capture-ask.js").read_text(encoding="utf-8")
    assert 'ensureModule("chatGhost").then(() => openChatGhost(box))' in ask
    assert 'prefs.get("searchSuggest", "on") !== "off"' in SRC
    assert "chatGhostTally" in SRC and '"Tab"' in SRC and '"Escape"' in SRC
