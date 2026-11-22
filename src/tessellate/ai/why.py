"""Why this answer (CHAT_PLAN B30, INBOX 805): how an answer was made, as a
job's lines.

The owner: "all information and processes across the app need to be 100%
transparent". An answer was a block of text with nothing to say how it came
to be: what the question was read as, which notes were searched and which
were used, who wrote it (Atlas from the notes, or a model) and in what
shape, and how long it took. Each of those is one line here, stamped with
the seconds since the question arrived, the way a background job's log
reads, and the Ask box draws them in a fold under the answer.

Pure: the route measures and counts, this says it in words.
"""

from __future__ import annotations

#: What the question was read as (`ai/intent.py`).
INTENTS = {
    "notes": "a question about your notes",
    "smalltalk": "small talk",
    "about_app": "a question about the app",
    "utility": "something to work out (a sum, a date, a conversion)",
    "act": "something to do",
}

#: How the notes were found (`SEARCH_MODE_LABELS` in capture-ask.js says the
#: same in the results column's chip).
SEARCHES = {
    "hybrid": "by meaning and keywords",
    "semantic": "by meaning",
    "keyword": "by keywords",
    "recent": "newest first",
    "dated": "by the date asked about",
    "category": "in the category the question names",
    "outside_range": "by subject, outside the time asked about",
}

#: The answer's shape (`composer_digest`'s kinds, decision 70).
SHAPES = {
    "overview": "an overview, grouped by when you wrote each note",
    "likes": "what you liked, the strongest first",
    "fact": "the one line that answers it",
    "when": "a date, from the note that names it",
    "count": "a total, the amounts added up",
    "opinion": "your verdict and the reasons you gave",
    "who": "the people your notes name",
    "left": "what is still to do",
    "compare": "the two side by side",
    "more": "the rest the last answer left out",
    "this": "a summary of what is open",
    "web": "one line from each page read",
}


def _secs(value: float) -> float:
    return round(max(0.0, value), 2)


def _search_say(say, intent: str, mode, matched: int, scoped: bool, loading: bool) -> bool:
    """The "searched" line, when the question went to the notes. Whether it did."""
    retrieval = intent in ("notes",) or matched > 0
    if not retrieval:
        return False
    how = SEARCHES.get(str(mode or "").rsplit("+", 1)[-1].rsplit("_recent", 1)[0], "")
    where = "Read only the notes you pointed it at" if scoped else "Searched your notes"
    #: The first question after a launch reads words while the search
    #: model loads behind it, rather than waiting for it (27 s, measured).
    later = "; the search by meaning was still loading, so it read words only" if loading else ""
    if matched:
        found = f"{matched} {'note' if matched == 1 else 'notes'} matched"
        say("searched", f"{where}{f' {how}' if how and not scoped else ''}: {found}{later}.")
    else:
        say("searched", f"{where}: nothing matched{later}.")
    return True


def _answer_say(say, composed: bool, model, matched: int, context: bool) -> None:
    """Who wrote the answer, and whether it was handed the app's own."""
    if composed:
        say("answered", "Atlas's assistant wrote it from your notes, with no model: every line comes from a note it cites.")
    elif model:
        say("answered", f"The model, {model}, wrote it{' from the notes found' if matched else ''}.")
        if context:
            say("answered", "It was handed the app's own answer as a fact to use, not as the reply.")
    else:
        say("answered", "Atlas worked it out itself, with no model.")


def lines(
    *,
    intent: str,
    mode: str | None,
    matched: int,
    used: int,
    when: str | None = None,
    scoped: bool = False,
    composed: bool,
    model: str | None = None,
    shape: str | None = None,
    context: bool = False,
    loading: bool = False,
    read_by: str = "",
    marks: dict[str, float],
) -> list[dict]:
    """`[{"at": seconds, "text": words}]`, oldest first. `marks` holds the
    seconds since the question at "read", "searched", "answered" and "done";
    `shape` is a digest kind (`digest:overview` or `overview`), None for a
    model's prose; `context` says the model was handed the app's own answer
    (decision 75)."""
    out: list[dict] = []

    def say(at: str, text: str) -> None:
        out.append({"at": _secs(marks.get(at, 0.0)), "text": text})

    #: A composed answer can read notes the search count never saw (a summary
    #: of one named note): a note the answer used was matched (audit 1028 E72).
    matched = max(matched, used)
    reading = INTENTS.get(intent, "a question")
    say("read", f"Read the question as {reading}{f', for {when}' if when else ''}.")
    #: A reading the app does itself (what changed since yesterday) found the
    #: notes: the trail names that step, never "nothing matched" (INBOX 1569).
    if read_by:
        say("searched", read_by)
        retrieval = False
    else:
        retrieval = _search_say(say, intent, mode, matched, scoped, loading)
    kind = (shape or "").split(":", 1)[-1]
    _answer_say(say, composed, model, matched, context)
    if kind in SHAPES:
        say("answered", f"Shaped as {SHAPES[kind]}.")
    if retrieval and matched:
        cited = f"Cited {used} of the {matched}" if used else "Cited none of them by line"
        say("done", f"{cited}{'; the rest are in the column beside it' if used and used < matched else ''}.")
    took = marks.get("done", 0.0)
    #: The footer under the answer times the whole wait; this times the work (INBOX 1569).
    say("done", f"Done in {_secs(took):.2f} s of work here; the time under the answer is the whole wait.")
    return out
