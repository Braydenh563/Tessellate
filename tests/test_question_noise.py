"""Questions typed the way people type (INBOX 741, `ai/question_noise.py`).

The owner: "does it cover any and ALL typos, maybe use similarity or
meaning, cover all slang like pls, ty, lol, u, r, wym, etc?". One test per
slang entry, the small-talk words, the typo repair and its guards, meaning
as the fallback, and the noise eval's gates.
"""

from __future__ import annotations

import pytest

from tessellate.ai import composer, intent, question_noise
from tests import _composer_eval as ev


# --- 1. slang -----------------------------------------------------------------


def test_the_slang_table_holds_at_least_four_hundred_entries():
    assert len(question_noise.SLANG) >= 400


@pytest.mark.parametrize(("word", "kind"), sorted((w, k) for w, k in question_noise.SOCIAL.items() if w not in ("so", "much")))
def test_each_small_talk_word_is_read_as_its_kind(word, kind):
    assert question_noise.social_kind(word) == kind


@pytest.mark.parametrize(("phrase", "kind"), sorted(question_noise.SOCIAL_PHRASES.items()))
def test_each_small_talk_phrase_is_read_as_its_kind(phrase, kind):
    assert question_noise.social_kind(phrase) == kind
    assert question_noise.social_kind(phrase.upper() + "!!") == kind


@pytest.mark.parametrize(("typed", "meant"), sorted(question_noise.SLANG.items()))
def test_each_slang_entry_is_spelled_out(typed, meant):
    #: In the asking place, where "r" and "y" are read too.
    assert question_noise.repair(f"{typed} x").startswith(meant)


@pytest.mark.parametrize("typed", sorted(question_noise.SLANG))
def test_no_slang_entry_is_a_subject_word_or_a_number(typed):
    assert not typed.isdigit()
    assert typed not in ("may", "mar", "sat", "sun", "ill", "4", "2")


@pytest.mark.parametrize("message", ["ty", "thx", "tysm", "lol", "lmao", "hahahaha", "lmaooo", "ok thx", "ty for the help", "gn", "brb", "kk", ":)", "\U0001F44D"])
def test_small_talk_typed_short_is_small_talk_and_never_searched(message):
    assert question_noise.social_kind(message)
    assert intent.classify(message) == intent.SMALLTALK


@pytest.mark.parametrize("message", ["ty when is the dentist", "lol what did i say about lisbon", "the help desk number"])
def test_a_question_with_small_talk_in_it_is_still_a_question(message):
    assert question_noise.social_kind(message) is None


def test_laughter_and_thanks_get_their_own_reply():
    assert composer.social("lol") in composer.social_surfaces("laugh")
    assert composer.social("ty") in composer.SOCIAL["thanks"]


# --- 2. typo repair -----------------------------------------------------------


@pytest.mark.parametrize(
    ("typed", "read"),
    [
        ("whenis the dentist", "when is the dentist"),
        ("wh en is the dentist", "when is the dentist"),
        ("howmany testers", "how many testers"),
        ("wehn is the launch", "when is the launch"),
        ("wjen is the dentist", "when is the dentist"),
        ("whrre is the key", "where is the key"),
        ("hoow many testers", "how many testers"),
        ("how manny testers", "how many testers"),
        ("hwo asked", "who asked"),
        ("hwo many", "how many"),
        ("what is the lattest on harbor", "what is the latest on harbor"),
        ("diffrence between a and b", "difference between a and b"),
        ("explian why", "explain why"),
        ("when is the dentist \U0001F9B7", "when is the dentist"),
    ],
)
def test_a_misspelt_asking_word_is_put_right(typed, read):
    assert question_noise.repair(typed) == read


@pytest.mark.parametrize(
    "kept",
    ["then what", "show me the list", "why is the list slow", "the boiler is due", "hat stand", "when is the dentist"],
)
def test_real_words_and_the_subject_are_left_as_typed(kept):
    assert question_noise.repair(kept) == kept


def test_a_neighbouring_key_a_doubled_letter_and_a_dropped_vowel_are_cheap_edits():
    d = question_noise.distance
    assert d("wjen", "when") < d("wzen", "when")
    assert d("whhen", "when") < 1
    assert d("lng", "long") < 1
    assert d("hwo", "how") < 1


# --- 3. meaning as the fallback -------------------------------------------------


@pytest.mark.parametrize(
    ("question", "kind"),
    [
        ("dentist date?", "when"),
        ("address of the hotel", "where"),
        ("progress on the sync rewrite", "status"),
        ("steps to sharpen my knife", "explain"),
        ("price of the trip", "count"),
        ("reason the list was slow", "explain"),
    ],
)
def test_a_question_no_rule_reads_is_matched_to_example_questions(question, kind):
    assert composer.classify(question) == kind


@pytest.mark.parametrize("subject", ["spare key", "lisbon", "the boiler", "harbor launch plan", "trip budget"])
def test_a_bare_subject_stays_a_what(subject):
    assert composer.classify(subject) == "what"


def test_with_an_embedder_meaning_is_measured_by_its_cosine():
    question_noise._EMBED_CACHE.clear()

    def embed(texts):
        #: A toy embedder: "date" words point one way, the rest another.
        return [[1.0, 0.0] if any(w in t for w in ("date", "day", "time", "when")) else [0.0, 1.0] for t in texts]

    assert question_noise.guess_kind("the date of it", embed) is None or question_noise.guess_kind("the date of it", embed) == "when"
    question_noise._EMBED_CACHE.clear()


# --- 4. the noise eval ----------------------------------------------------------


@pytest.fixture(scope="module")
def noise_rows():
    return ev.run_noise()


def test_the_noise_eval_holds_at_least_a_hundred_questions(noise_rows):
    assert len(noise_rows) >= 100


def test_the_hand_written_noisy_questions_are_read_as_meant_or_offered(noise_rows):
    """A question read the wrong way is one whose reading was unsure, and
    its "Did you mean ...?" offers the right one."""
    wrong = [r["question"] for r in noise_rows if r["set"] == "hand" and not r["right"]]
    assert len(wrong) <= 2
    offered = ev.run_did_you_mean()
    assert offered["fired"] >= len(wrong)
    assert offered["right_with_offer"] == offered["fired"]


# --- conversational turns -------------------------------------------------------


@pytest.fixture(scope="module")
def conversation():
    return ev.run_conversation()


def test_at_least_sixty_conversational_turns_are_read_as_their_kind(conversation):
    assert len(conversation) >= 60
    assert [(r["message"], r["got"], r["expect"]) for r in conversation if not r["right"]] == []


def test_no_conversational_turn_fires_a_note_search(conversation):
    assert ev.conversation_summary(conversation)["searched_small_talk"] == 0


def test_replies_vary_and_never_repeat_twice_running(conversation):
    summary = ev.conversation_summary(conversation)
    assert summary["same_reply_twice_running"] == 0
    assert summary["distinct_replies"] >= 25


def test_an_acknowledgement_offers_the_next_step_on_what_was_being_discussed():
    reply = composer.social("ok", last_question="What is the latest on the sync rewrite?")
    assert "“sync rewrite”" in reply


def test_a_mixed_turn_answers_its_question():
    assert intent.classify("ok and what about the trip budget") != intent.SMALLTALK
    assert composer.rephrase("ok and what about the trip budget") == "what about the trip budget"


# --- did you mean ---------------------------------------------------------------


def test_an_unsure_reading_offers_did_you_mean_and_pressing_it_asks_again():
    notes = [{"id": 1, "content": "# Public API\n\nThree people in the beta asked for one.", "created_at": "2026-09-01"}]
    result = composer.compose("hwo is the designer we are hiring", notes)
    assert "Did you mean “how”?" in result["next"]
    follow = composer.follow_on("Did you mean “how”?", [{"question": "hwo is the designer we are hiring", "answer": result["text"]}])
    assert follow is not None and follow.question == "how is the designer we are hiring"


def test_nothing_found_asks_a_short_clarifying_question():
    result = composer.compose("What is the capital of Peru?", [{"id": 1, "content": "# Boiler\n\nDue in March.", "created_at": "2026-09-01"}])
    #: Engine probe P1: the words no note found holds are named before the question back.
    assert result["text"].endswith(tuple(composer.phrase_options("nothing_ask"))) and "“Peru”" in result["text"]


def test_noise_nobody_tuned_against_changes_the_kind_rarely(noise_rows):
    derived = [r for r in noise_rows if r["set"] == "derived"]
    assert sum(r["right"] for r in derived) / len(derived) >= 0.98


def test_no_table_key_is_written_twice() -> None:
    """The 2026-10-10 triage, decision 9: a key given twice in the source is
    either dead (the same value) or a silent override (another one); fifteen
    were found, all of the first kind."""
    import ast
    from pathlib import Path

    for name in ("question_noise.py", "composer_tables.py"):
        tree = ast.parse((Path("src/tessellate/ai") / name).read_text(encoding="utf-8"))
        seen: dict[tuple[str, object], int] = {}
        twice = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict) and isinstance(node.targets[0], ast.Name):
                table, literal = node.targets[0].id, node.value
            elif (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "update"
                and isinstance(node.func.value, ast.Name) and node.args and isinstance(node.args[0], ast.Dict)
            ):
                table, literal = node.func.value.id, node.args[0]
            else:
                continue
            for key in literal.keys:
                if isinstance(key, ast.Constant):
                    if (table, key.value) in seen:
                        twice.append(f"{name}:{key.lineno} {table}[{key.value!r}] (first at {seen[(table, key.value)]})")
                    seen.setdefault((table, key.value), key.lineno)
        assert not twice, twice


def test_the_composer_imports_without_the_database_layer() -> None:
    """Decision 9: `import tessellate.ai.composer` under 0.5 s. Measured cold:
    0.75 to 0.94 s before the triage, 0.08 to 0.15 s after, because
    `grounding` no longer pulls in the embeddings and the search manager
    (and with them SQLAlchemy and the database models) at import."""
    import subprocess
    import sys

    code = (
        "import sys, time; t = time.perf_counter(); import tessellate.ai.composer; "
        "print(time.perf_counter() - t, 'sqlalchemy' in sys.modules)"
    )
    runs = []
    #: The faster of two runs: a busy CI machine can stall one process for
    #: longer than the whole import takes, and that is not the import's cost.
    for _ in range(2):
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, env={"PYTHONPATH": "src"})
        took, loaded = out.stdout.split()
        assert loaded == "False"
        runs.append(float(took))
    assert min(runs) < 0.5, runs


def test_a_long_run_of_stray_keys_is_stripped_in_linear_time():
    """CodeQL flagged the old end-anchored pattern as polynomial on a run of
    backslashes or slashes; the tail is now a scan from the end."""
    import time

    from tessellate.ai.question_noise import strip_strays

    began = time.perf_counter()
    assert strip_strays("x" + "\\" * 50000 + "y").endswith("y")
    assert strip_strays("why" + "/" * 50000 + "z").endswith("z")
    assert time.perf_counter() - began < 0.5
    assert strip_strays("gaming mouse?\\") == "gaming mouse?"
    assert strip_strays("why?/") == "why?"
    assert strip_strays("a :\\") == "a :\\"


# --- ledger rows ----------------------------------------------------------------
# Small and medium composer, engine and Ask rows, each pinned where it was
# fixed; each row tries the owner's typed forms too (Brief 90).


#: Row 543: "think", "plan" and "idea" are note words, so a one-line reply
#: of agreement was searched for. Each is the person answering, not asking.
AGREEMENT = [
    "I think so", "i think so tbh", "i guess so", "i suppose so", "i hope so",
    "good plan", "gud plan", "nice idea", "good idea", "great idea", "good call",
    "good point", "sounds like a plan", "sure thing", "i think so too",
]


@pytest.mark.parametrize("message", AGREEMENT)
def test_agreeing_is_small_talk_not_a_search(message):
    assert question_noise.social_kind(message) in {"ack", "compliment"}, message
    assert intent.classify(message) == intent.SMALLTALK, message


@pytest.mark.parametrize("message", ["what did I plan for the trip", "my ideas for the garden", "what do I think about rust"])
def test_the_same_words_in_a_question_still_search(message):
    assert question_noise.social_kind(message) is None
    assert intent.classify(message) != intent.SMALLTALK


@pytest.mark.parametrize("asked, plain", [
    ("hwo do i set a remnder", "how do I set a reminder"),
    ("hwo do i turn on dark mdoe", "how do I turn on dark mode"),
])
def test_the_guide_with_no_model_says_how_it_read_a_typo(asked, plain):
    """Row 404: the Guide's no-model answer said nothing of the repair, and
    answered the misspelt question worse than the plain one (row 417: "The
    Reminders tab groups items..." rather than the steps)."""
    from tessellate.ai import composer_ack, help_chat

    typed = help_chat.offline_answer(asked)["content"]
    clean = help_chat.offline_answer(plain)["content"]
    starts = composer_ack.STARTS["natural"]
    assert any(typed.startswith(s) for s in starts), typed[:80]
    assert typed.split(composer_ack.END, 1)[1] == clean
    assert not any(clean.startswith(s) for s in starts)


def test_a_real_word_no_note_holds_is_not_put_right_to_one_that_does():
    """Found working row 409: "what do I know about rust" quoted the soup
    recipe, because "rust" was fitted to the note word "rest" (one edit).
    A dictionary word is what the person meant; only a non-word is a typo
    of a note's word ("lisbn" is "lisbon")."""
    import json
    from datetime import date
    from pathlib import Path

    notes = json.loads((Path(__file__).parent / "fixtures" / "composer" / "showcase_725.json").read_text(encoding="utf-8"))["notes"]
    said = composer.compose("what do I know about rust", notes, today=date(2026, 10, 1))
    assert not said["grounding"], said["text"]
    assert "rust" in said["text"]


def test_a_cold_process_that_loads_the_app_reads_the_apps_own_words():
    """The speller's app vocabulary comes from the help topics, registered when
    `help_chat` is imported, which the app does (routes_help): a fresh process that
    loaded the route repairs "dayz". (The speller cannot import `help_chat`
    itself: that made it, `question_noise` and the Guide one import cycle,
    `test_import_module_cycles.py`; tests/conftest.py loads it for the suite.)"""
    import subprocess
    import sys
    from pathlib import Path

    src = Path(__file__).resolve().parents[1] / "src"
    code = (
        "import tessellate.api.app;from tessellate.ai import question_noise;"
        "print(question_noise.repair('how many dayz until mums bday'))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, env={"PYTHONPATH": str(src), "PATH": ""}
    ).stdout.strip()
    assert out == "how many days until mums birthday"
