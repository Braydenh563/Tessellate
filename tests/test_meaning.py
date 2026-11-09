"""Find by meaning in every search box (Brief 94, INBOX 857).

The owner: "half the time Im trying to find a specific object, feature, or
setting and I cant remember the exact name of it". One deterministic layer
(`ai/meaning.py`, served by `GET /read/words`, run in the page by
`frontend/js/meaning.js`) reads a query as the things it names: groups of
words meaning the same, the request's words dropped, a slip read as the word
meant. The browser measurement of the sixty-query table is
`scratchpad/ui-sweeps/meaning94.js`; this file pins the rule and its parity.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tessellate.ai import meaning

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend/js"
TABLE = json.loads((ROOT / "tests/fixtures/meaning_queries_1011.json").read_text(encoding="utf-8"))["queries"]


def test_the_eval_table_is_sixty_owner_style_queries():
    assert len(TABLE) == 60
    assert len({row["q"] for row in TABLE}) == 60
    assert all(row["want"] for row in TABLE)
    #: Typos included, the way the owner types.
    assert {"nigth mode", "chnage pasword", "calender", "keybord shortcuts", "speling mistakes"} <= {r["q"] for r in TABLE}


@pytest.mark.parametrize(
    ("query", "label"),
    [
        ("dark mode", "Mode: light, dark or system"),
        ("nigth mode", "Mode: light, dark or system"),
        ("make text bigger", "Text size"),
        ("bin", "Open the bin"),
        ("trash", "Open the bin"),
        ("get my deleted stuff back", "Undo and the bin"),
        ("chnage pasword", "Change your password"),
        ("forgot my password", "If you forget your password"),
        ("too much moving stuff", "Reduce motion"),
        ("battery drain", "Battery-efficient mode"),
        ("the little guy in the corner", "Corner companion"),
        ("keybord shortcuts", "Keyboard shortcuts"),
        ("calender", "Go to Timeline"),
        ("to do list", "Go to Reminders"),
        ("bring in my old notes", "Import from another app"),
        ("dont disturb", "Mute notifications except reminders"),
        ("simpler app", "Simple mode"),
    ],
)
def test_a_misnamed_query_holds_the_thing_it_means(query, label):
    assert meaning.holds(meaning.alts(query), label)


def test_the_request_words_are_dropped_and_a_bare_request_kept():
    assert meaning.alts("how do I make the text bigger")[0][0] == "text"
    assert [g[0] for g in meaning.alts("how do I")] == ["how", "do", "i"]


def test_a_word_said_twice_is_one_thing():
    assert len(meaning.alts("what it remembers about me")) == 1


def test_words_are_matched_at_a_word_start():
    #: "ai" is not in "maintain", "pin" is not in "spinning".
    assert not meaning.holds([["ai"]], "Maintain the index")
    assert not meaning.holds([["pin"]], "A spinning wheel")


def test_the_route_serves_the_table(client):
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    got = client.get("/read/words", headers={"X-Auth-Token": token}).json()
    assert got == meaning.table()
    assert any("trash" in g and "bin" in g for g in got["groups"])
    assert "stuff" in got["filler"]


def test_the_page_runs_the_same_rule():
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    queries = [row["q"] for row in TABLE] + ["how do I", "what the ai remembers about me", "bring in my old notes"]
    #: meaning.js is one closure now (ranked row 37a): its table is private, so the page
    #: is given the server's table the way it asks for it (`apiJson`), and `window` is the
    #: context, so the exports are the globals the callers use. Same rule, same queries.
    script = f"""
const vm = require("vm");
const table = {json.dumps(meaning.table())};
const ctx = {{ apiJson: () => Promise.resolve(table), document: {{ dispatchEvent() {{}} }}, Event, console }};
ctx.window = ctx;
vm.createContext(ctx);
vm.runInContext(require("fs").readFileSync({json.dumps(str(JS / "meaning.js"))}, "utf8"), ctx);
(async () => {{
  vm.runInContext("meaningAsk()", ctx);
  await new Promise((r) => setTimeout(r, 20));
  const out = {{}};
  for (const q of {json.dumps(queries)}) out[q] = vm.runInContext(`meaningAlts(${{JSON.stringify(q)}})`, ctx);
  process.stdout.write(JSON.stringify(out));
}})();
"""
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    page = json.loads(done.stdout)
    for q in queries:
        assert page[q] == meaning.alts(q), q


def test_every_search_box_calls_the_layer():
    app = (JS / "app.js").read_text(encoding="utf-8")
    bundles = app[app.index("const LAZY_MODULES") :]
    assert '"/js/meaning.js", "/js/settings-find.js"' in bundles
    assert '"/js/meaning.js", "/js/app-features.js"' in bundles
    for name in ("settings-find.js", "app-palette.js", "manual.js"):
        assert "meaningAlts(" in (JS / name).read_text(encoding="utf-8"), name


class _Letters:
    """An embedder by letter counts: "bin" is near "Open the bin"."""

    def is_ready(self) -> bool:
        return True

    def embed_many(self, texts):  # noqa: ANN001, ANN201
        import numpy as np

        out = []
        for text in texts:
            row = np.zeros(26, dtype="float32")
            for ch in text.lower():
                if "a" <= ch <= "z":
                    row[ord(ch) - 97] += 1
            out.append(row)
        return out


def test_close_in_meaning_says_when_no_model_is_on(client, monkeypatch):
    from tessellate.core import deps

    class Off:
        def is_ready(self) -> bool:
            return False

    monkeypatch.setattr(deps, "get_embeddings", lambda: Off())
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    got = client.post("/read/near", json={"q": "bin", "texts": ["Open the bin"]}, headers={"X-Auth-Token": token}).json()
    assert got == {"available": False, "near": []}


def test_close_in_meaning_ranks_the_rows_by_cosine(client, monkeypatch):
    from tessellate.core import deps

    monkeypatch.setattr(deps, "get_embeddings", _Letters)
    token = client.post("/auth/setup", json={"password": "first-pass"}).json()["token"]
    texts = ["Zoom in", "Keyboard shortcuts", "Keyboard shortcut list"]
    got = client.post("/read/near", json={"q": "keyboard shortcuts", "texts": texts}, headers={"X-Auth-Token": token}).json()
    assert got["available"] is True
    assert [n["i"] for n in got["near"]][:2] == [1, 2]
    assert all(n["score"] >= meaning.NEAR_FLOOR for n in got["near"])
    assert 0 not in [n["i"] for n in got["near"]]


def test_the_boxes_ask_for_close_in_meaning():
    for name in ("settings-find.js", "app-palette.js"):
        source = (JS / name).read_text(encoding="utf-8")
        assert "meaningNear(" in source, name
        assert "Close in meaning" in source, name
