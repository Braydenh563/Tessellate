"""L-chat-35: every suggested button starts with a capital (the owner, 2026-11-13:
"the suggested buttons dont start with a capital letter", of the Guide chip
"tag the knife note with kitchen"). Two checks: the Guide's own replies, as the
panel gets them, and a lint over every literal chip list in the AI layer, so a
new source is caught the day it is written."""

from __future__ import annotations

import ast
from pathlib import Path

from tessellate.ai import help_chat

AI = Path(__file__).resolve().parents[1] / "src" / "tessellate" / "ai"

#: Questions whose Guide replies carry chips with no model.
QUESTIONS = (
    "what can atlas change",
    "what can you do to my notes",
    "give me some ideas",
    "what should I ask in chat",
    "ideas for reminders",
    "how do I set a reminder?",
    "when is my dentist appointment",
    "how do I use the app",
    "help",
    "hello",
)


class _Down:
    def is_running(self):
        return False


class _Manager:
    def utility_model(self):
        return ""

    def chat_model(self):
        return ""


def _cased(asks) -> list[str]:
    return [a for a in asks or [] if a and a[:1].isalpha() and not a[:1].isupper()]


def test_every_guide_reply_offers_chips_in_sentence_case():
    for q in QUESTIONS:
        for reply in (help_chat.offline_answer(q), help_chat.answer(q, _Manager(), _Down())):
            assert not _cased(reply.get("asks")), (q, reply.get("asks"))
        done = list(help_chat.answer_stream(q, _Manager(), _Down()))[-1]
        assert not _cased(done.get("asks")), (q, done.get("asks"))


def test_the_atlas_reply_names_the_tag_example_with_a_capital():
    reply = help_chat.answer("what can atlas change", _Manager(), _Down())
    assert "Tag the knife note with kitchen" in reply["asks"]


#: Constants that are chip lists. `_ASKS` alone is the common name for an intent
#: pattern table, so the chip names are listed rather than guessed from "ASKS".
_CHIP_NAMES = {"ASKS", "STARTERS", "CALL_ASKS", "_DETAIL_ASKS"}


def _is_chip_name(name: str) -> bool:
    return name in _CHIP_NAMES or name.endswith("CHIPS")


def _literal_chips(tree: ast.AST):
    """String literals in a list or tuple given as the value of an `asks` key or name."""
    for node in ast.walk(tree):
        values = []
        if isinstance(node, ast.Dict):
            values = [v for k, v in zip(node.keys, node.values) if isinstance(k, ast.Constant) and k.value == "asks"]
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(t, ast.Name) and _is_chip_name(t.id) for t in targets):
                values = [node.value]
        for value in values:
            yield from _chip_strings(value)


def _chip_strings(node: ast.AST):
    """The strings a chip list holds: list or tuple items, through a dict's values (never its keys)."""
    if isinstance(node, ast.Dict):
        for v in node.values:
            yield from _chip_strings(v)
    elif isinstance(node, (ast.List, ast.Tuple)):
        for item in node.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str) and item.value[:1].isalpha():
                yield item
            else:
                yield from _chip_strings(item)


def test_no_literal_chip_starts_lower_case():
    bad = []
    for path in sorted(AI.rglob("*.py")):
        for const in _literal_chips(ast.parse(path.read_text(encoding="utf-8"))):
            if not const.value[:1].isupper():
                bad.append(f"{path.name}:{const.lineno} {const.value!r}")
    assert not bad, "a chip starts lower case:\n  " + "\n  ".join(bad)


def test_no_chip_list_holds_an_act_example_as_typed():
    """An act's `example` is lower case as typed (prose quotes it); a chip takes `.chip`."""
    bad = []
    for path in sorted(AI.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    if isinstance(k, ast.Constant) and k.value == "asks":
                        bad += [f"{path.name}:{a.lineno}" for a in ast.walk(v) if isinstance(a, ast.Attribute) and a.attr == "example"]
    assert not bad, bad
