"""The apostrophe-less contraction family (INBOX 1582, the owner: "it didnt pick
up my misspell of \"havent\"", "or ive").

One table drives the notes' autocorrect and the document editor's check, so the
whole family is tested here, not two words: every member is corrected to its
contraction with "I" capitalised, the four that are also words (ill, id, cant,
wont) only where their neighbours say which they are, and the real words that
sit next to the family (its, lets, were, well, wed, shed, shell, hell) never.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests import _js_scope
from tests._app_js import documents_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend/js"

#: word typed -> the contraction it is corrected to (the family the owner named, and the rest).
FAMILY = {
    "havent": "haven't", "ive": "I've", "dont": "don't", "isnt": "isn't", "im": "I'm", "youre": "you're",
    "theyre": "they're", "shouldnt": "shouldn't", "wouldnt": "wouldn't", "couldnt": "couldn't",
    "didnt": "didn't", "doesnt": "doesn't", "wasnt": "wasn't", "werent": "weren't", "arent": "aren't",
    "hasnt": "hasn't", "hadnt": "hadn't", "mustnt": "mustn't", "neednt": "needn't", "aint": "ain't",
    "youve": "you've", "weve": "we've", "theyve": "they've", "youll": "you'll", "theyll": "they'll",
    "itll": "it'll", "thatll": "that'll", "wholl": "who'll", "thats": "that's", "whats": "what's",
    "theres": "there's", "heres": "here's", "whos": "who's", "wouldve": "would've", "couldve": "could've",
    "shouldve": "should've", "mightve": "might've", "mustve": "must've", "youd": "you'd", "theyd": "they'd",
}

#: (text up to and including the finishing space, text after the word, what it becomes or None).
CONTEXT = [
    # cant and wont follow a subject
    ("I cant ", " go there", "can't"),
    ("she just wont ", " listen", "won't"),
    ("They said it cant ", "", "can't"),
    ("Cant ", " believe it", "Can't"),
    ("there wont ", " be time", "won't"),
    # ill and id open a clause and take the verb of "I'll go", "I'd like"
    ("ok ill ", " be there", "I'll"),
    ("Ill ", " call you later", "I'll"),
    ("and ill ", " see", "I'll"),
    ("Id ", " like that", "I'd"),
    ("i think id ", " rather not", "I'd"),
    # the words they are, left alone
    ("the cant ", " of the age", None),
    ("a religious cant ", " and nothing else", None),
    ("as is his wont ", ", he left", None),
    ("She was ill ", " in bed", None),
    ("Ill ", " health kept him home", None),
    ("He felt ill. ", "", None),
    ("the user id ", " is required", None),
    ("My id ", " card", None),
    ("Id ", " is the first column", None),
    ("ill ", "", None),  # typing: the next word is not there yet
    ("id ", "", None),
]

#: Real words beside the family: never touched, in any position.
REAL_WORDS = ["its", "lets", "were", "well", "wed", "shed", "shell", "hell", "hed", "ill", "id", "cant", "wont", "we", "he"]


#: autocorrect.js is one closure now (ranked row 37a); the tests call its private names, so they read it as it was before it was wrapped (`_js_scope.unwrapped`): same code, same assertions.
def _node(calls: list[str]) -> list:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = f"""
const vm = require("vm");
const ctx = {{
  console, prefsCache: {{ writing_dictionary: [] }},
  document: {{ addEventListener() {{}} }},
  window: {{ addEventListener() {{}} }},
}};
vm.createContext(ctx);
vm.runInContext({json.dumps(_js_scope.unwrapped((JS / "autocorrect.js").read_text(encoding="utf-8")))}, ctx);
const out = [];
for (const call of {json.dumps(calls)}) out.push(vm.runInContext(call, ctx) ?? null);
process.stdout.write(JSON.stringify(out));
"""
    done = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_whole_family_is_corrected_as_it_is_typed():
    calls, wants = [], []
    for typed, made in FAMILY.items():
        for lead in ("", "I think "):
            calls.append(f"autocorrectFind({json.dumps(lead + typed + ' ')})")
            wants.append(made)
        # at the head of a sentence the capital is kept
        calls.append(f"autocorrectFind({json.dumps(typed.capitalize() + ' ')})")
        wants.append(made[0].upper() + made[1:])
    got = _node(calls)
    wrong = {c: (g and g["fixed"], w) for c, g, w in zip(calls, got, wants, strict=True) if not g or g["fixed"] != w}
    assert not wrong, wrong


def test_every_member_ends_on_any_word_ending_key():
    calls = [f"autocorrectFind({json.dumps('so havent' + end)})" for end in (" ", ".", ",", "!", "\n", ")")]
    assert all(g and g["fixed"] == "haven't" for g in _node(calls))


def test_the_four_that_are_also_words_wait_for_their_neighbours():
    calls = [f"autocorrectFind({json.dumps(lead)}, {json.dumps(ahead or None)})" for lead, ahead, _ in CONTEXT]
    got = _node(calls)
    wrong = {}
    for (lead, ahead, want), found in zip(CONTEXT, got, strict=True):
        made = found["fixed"] if found else None
        if made != want:
            wrong[f"{lead!r} + {ahead!r}"] = (made, want)
    assert not wrong, wrong


def test_the_document_check_reads_the_same_neighbours():
    cases = [
        ("I cant go there", "cant", "can't"),
        ("Ill be there, ok.", "Ill", "I'll"),
        ("Well, id rather not.", "id", "I'd"),
        ("It was the cant of the age.", "cant", ""),
        ("He is ill and tired.", "ill", ""),
        ("Nobody wed them.", "wed", ""),
        ("The user id is shown.", "id", ""),
    ]
    calls = [f"autocorrectState.inText({json.dumps(t)}, {t.index(w)}, {json.dumps(w)})" for t, w, _ in cases]
    got = _node(calls)
    assert [g or "" for g in got] == [want for _, _, want in cases]


def test_real_words_beside_the_family_are_never_in_the_table():
    table = set(_node(["Object.keys(AUTOCORRECT_TYPOS)"])[0])
    assert not set(REAL_WORDS) & table
    for word in REAL_WORDS:
        # alone, with no neighbours that make it a contraction, nothing happens
        assert _node([f"autocorrectFind({json.dumps('so the ' + word + ' ')}, ' of it')"])[0] is None, word


def test_no_member_of_the_family_is_a_word_in_the_list():
    words = set((ROOT / "frontend/vendor/wordlist/en.txt").read_text(encoding="utf-8").split())
    assert not set(FAMILY) & words, sorted(set(FAMILY) & words)


def test_the_document_editor_asks_the_same_reader_in_both_passes():
    docs = documents_text()
    assert docs.count("autocorrectState.inText(") == 2
    assert "const DOC_AUTOCORRECT = AUTOCORRECT_TYPOS;" in docs


def test_the_tidy_pass_knows_every_unambiguous_member():
    from tessellate.ai import composer_tidy

    missing = {k: v for k, v in FAMILY.items() if composer_tidy._APOSTROPHES.get(k) != v}
    assert not missing, missing


def test_the_word_ending_keys_are_still_defined():
    # The listeners read these when a key is typed, not when the file loads, so a lost declaration
    # shows only as a page error on the first keystroke (it did, once, while this was written).
    assert _node(["typeof AUTOCORRECT_ENDS", "typeof autocorrectRefused", "typeof autocorrectState.contextual"]) == [
        "object", "object", "function",
    ]
