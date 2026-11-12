"""CHAT_PLAN T6: text transforms on pasted text, no model, no note.
Fixed clock: Sunday 8 November 2026, 10:00."""

from __future__ import annotations

import datetime as dt
import time

import pytest

from tessellate.ai import composer_extra, composer_study, composer_text

NOW = dt.datetime(2026, 11, 8, 10, 0, 0)
DRAFT = "A draft only: nothing was saved or changed._"


def ctx(q: str, **extra) -> composer_study.Ctx:
    return composer_study.Ctx(question=q, notes=extra.pop("notes", []), now=NOW, seed="s", asked=q, **extra)


def said(q: str, **extra) -> str:
    reply = composer_extra.answer(ctx(q, **extra))
    return reply.text if reply else ""


def block(lead: str, result: str, read: str) -> str:
    return f"{lead}\n\n```\n{result}\n```\n\n_Read as {read}. {DRAFT}"


def test_uppercase_after_a_colon():
    assert said("uppercase: hello there") == block("In capitals:", "HELLO THERE", "the text in capitals")


def test_uppercase_without_a_colon():
    assert said("uppercase hello there") == block("In capitals:", "HELLO THERE", "the text in capitals")


def test_make_this_uppercase():
    assert said("make this uppercase: hello there") == block("In capitals:", "HELLO THERE", "the text in capitals")


def test_lowercase():
    assert said("lowercase: Hello THERE") == block("In lower case:", "hello there", "the text in lower case")


def test_title_case_keeps_small_words_down():
    assert said("title case: the lord of the rings") == block("In title case:", "The Lord of the Rings", "the text in title case")


def test_slugify_folds_accents_and_punctuation():
    assert said("slugify My Trip To Lisbon") == block("As a slug:", "my-trip-to-lisbon", "the text as a lower-case slug joined by hyphens")
    assert said("slugify: Café Déjà Vu!") .count("cafe-deja-vu") == 1


def test_reverse_needs_a_delimiter():
    assert said("reverse the text: hello") == block("Reversed:", "olleh", "the text with its letters in reverse order")
    assert said("reverse the order of the queue") == ""


def test_sort_lines_and_comma_items():
    assert said("sort these lines:\nbanana\napple\nCherry") == block("Sorted:", "apple\nbanana\nCherry", "the lines or comma-separated items sorted A to Z")
    assert said("sort these: b, a, c") == block("Sorted:", "a, b, c", "the lines or comma-separated items sorted A to Z")
    assert said("sort my notes by date") == ""


def test_remove_duplicate_lines_keeps_the_first():
    assert said("remove duplicate lines:\nmilk\neggs\nMilk\nbread\neggs") == block(
        "Without duplicates:", "milk\neggs\nbread", "the lines or comma-separated items with repeats removed, first kept")


def test_number_the_lines():
    assert said("number the lines:\nmilk\neggs") == block("Numbered:", "1. milk\n2. eggs", "each line numbered from 1")


def test_quotes_around_the_paste_are_dropped():
    assert said('uppercase: "hello"') .count("\nHELLO\n") == 1


@pytest.mark.parametrize("q", ["uppercase", "sort:", "what is uppercase", "capitals of europe", "uppercase the first letter of each word: x", "reverse", "slugify"])
def test_what_is_not_a_transform_is_left_alone(q):
    assert said(q) == ""


def test_the_answer_ignores_the_model_voice_and_notes():
    private = [{"id": 1, "content": "HELLO the surprise party is secret", "created_at": "2026-11-01", "private": True}]
    plain = said("uppercase: hello there")
    assert said("uppercase: hello there", voice="formal", notes=private) == plain
    assert "surprise" not in plain


def test_a_paste_over_the_cap_is_left_alone():
    assert said("uppercase: " + "a" * 20001) == ""


@pytest.mark.parametrize("text", ["sort:" + " b," * 6000, "sort:" + "\n" * 20000 + "x", "uppercase" + " " * 20000 + "x", "title case: " + "a " * 9000, "remove duplicates:" + "\n".join(str(i % 50) for i in range(6000)), "reverse " + " " * 20000])
def test_a_20k_text_is_linear(text):
    start = time.perf_counter()
    composer_text.answer(ctx(text))
    assert time.perf_counter() - start < 0.5
