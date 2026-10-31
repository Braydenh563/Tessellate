"""The composed answer's eval (INBOX 725): 25 questions over the showcase notebook.

Not a test module (no `test_` prefix): `tests/test_composer_eval_725.py` holds
the gates and `python -m tests._composer_eval` prints the table the report
quotes. The fixture, `fixtures/composer/showcase_725.json`, is the notebook
`scratchpad/ui-sweeps/seed-showcase.py` writes, read back from its database,
with the notes `/chat/stream` retrieved for each question on that notebook
(ranked, the connected ones marked), so the eval runs the composer on what
the route hands it, deterministically and with no server and no network.

Four measures, each a number:

- **grounded**: the share of an answer's factual parts (quotes, note names,
  measured values, words of the question) that trace back to the notes or the
  question. The rule says 1.0, always.
- **redundancy**: the most two quoted sentences of one answer share (token
  Jaccard over stems). A chat answer does not say a thing twice.
- **readability**: mean words per sentence of the answer as read (markdown
  marks off), and how many different joining phrases it uses.
- **first line**: whether the answer's first line answers the question's
  shape on its own: a figure for a count, a date for a when, the newest day
  and its words for a status, a quote for everything else, a measured count
  or the list for a list.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from tessellate.ai import composer

FIXTURE = Path(__file__).parent / "fixtures" / "composer" / "showcase_725.json"

#: Spelled by its code point: the lint reads this file too.
EM_DASH = chr(0x2014)


def load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def today(data: dict | None = None) -> date:
    return date.fromisoformat((data or load())["today"])


def notes_for(entry: dict, data: dict) -> list[dict]:
    """The notes the route handed the composer for this question, ranked."""
    by_id = {note["id"]: note for note in data["notes"]}
    connected = set(entry.get("connected") or [])
    return [{**by_id[i], "connected": i in connected} for i in entry["notes"] if i in by_id]


def _flat(text: str) -> str:
    return " ".join(text.split())


def _count_word(n: int) -> str:
    words = composer._NUMBER_WORDS
    return words[n] if 0 <= n < len(words) else str(n)


def measured_values(notes: list[dict], on: date) -> set[str]:
    """Every value the app could have measured over these notes: counts (as
    digits and as words) up to the most units any one note holds, and every
    note's day, worded as `_Answer.day` words it."""
    most = max([len(notes)] + [len(composer.read_note(n, 0).sentences) for n in notes if composer.read_note(n, 0)])
    values = {str(n) for n in range(most + 1)}
    values |= {_count_word(n) for n in range(most + 1)}
    values |= {_count_word(n).capitalize() for n in range(most + 1)}
    for note in notes:
        day = date.fromisoformat(str(note["created_at"])[:10])
        month = composer._MONTHS[day.month - 1]
        #: A span by month (INBOX 787's overview: "from July to September").
        values |= {f"{day.day} {month}", f"{day.day} {month} {day.year}", month, f"{month} {day.year}"}
        if day == on:
            values |= {"today", "Today"}
        if (on - day).days == 1:
            values |= {"yesterday", "Yesterday"}
    return values


def _in_note(text: str, content: str) -> bool:
    """A quote as the composer may lightly trim it: the first letter raised
    or lowered, a final stop or an ellipsis off."""
    body = text.rstrip("…").rstrip(".")
    if not body:
        return False
    flat = _flat(content)
    return body[1:] in flat and (body in flat or body[0].lower() + body[1:] in flat or body[0].upper() + body[1:] in flat)


def shifted_failure(part: tuple, content: str, on: date) -> str | None:
    """A sentence said back in the second person (CHAT_PLAN decision 33):
    its original is in the note, and the realiser's rules, run again on it,
    give exactly what was said. None when both hold."""
    from tessellate.ai import realise

    text, original = part[1], part[3]
    again = realise.shift_person(original)
    forms = {f[:1].lower() + f[1:] for f in (again, realise.past_plan(again, date.min, on))}
    if not _in_note(original, content):
        return f"shifted: its original is not in note {part[2]}: {original!r}"
    if text[:1].lower() + text[1:] not in forms:
        return f"shifted: not what the rules give for {original!r}: {text!r}"
    return None


def rederived_insights(question: str, notes: list[dict], on: date) -> set[str]:
    """Every insight line the rules give over these notes for the question's
    subject (CHAT_PLAN decision 32): a measured sentence counts as measured
    only when running the rule again gives it word for word."""
    from tessellate.ai import insights

    terms = composer.subject_terms(question)
    subjects = {composer._asked_span(question, terms), *terms} - {""}
    found = [i for subject in subjects for i in insights.for_subject(subject, notes, on, question)]
    #: After a lead that said the count, a recurrence closes in its short form.
    return {i.text for i in found} | {insights.after_lead(i) for i in found if i.rule == "recurrence"}


def trace_failures(result: dict, question: str, notes: list[dict], on: date, asked_from: str = "") -> list[str]:
    """Every part of the answer that is not what it says it is: a template not
    in `PHRASES`, a quote not in the note it names, a measured value nothing
    measured. Empty for an answer that keeps the rule. `asked_from` is any
    earlier question a follow-up was resolved against: its words are the
    person's too."""
    by_id = {note["id"]: note for note in notes}
    failures: list[str] = []
    parts = result["parts"]
    if "".join(part[1] for part in parts) != result["text"]:
        failures.append("the parts are not the whole text")
    templates = set(composer.PHRASES.values())
    measured = measured_values(notes, on) if notes else set()
    for part in parts:
        kind, text = part[0], part[1]
        if kind == "template":
            if text not in templates:
                failures.append(f"not a fixed phrase: {text!r}")
        elif kind in ("quote", "picture"):
            if not _in_note(text, by_id[part[2]]["content"]):
                failures.append(f"{kind} not in note {part[2]}: {text!r}")
        elif kind == "help":
            #: The help register (CHAT_PLAN decision 36): a sentence of the
            #: app's own Help topic it names.
            from tessellate.ai import help_chat

            body = next((t["body"] for t in help_chat.HELP_TOPICS if t["id"] == part[2]), "")
            if text not in body:
                failures.append(f"not in Help topic {part[2]}: {text!r}")
        elif kind == "shifted":
            problem = shifted_failure(part, by_id[part[2]]["content"], on)
            if problem:
                failures.append(problem)
        elif kind == "title":
            first = re.sub(r"[*_`#]", "", by_id[part[2]]["content"].split("\n", 1)[0]).strip()
            if not first.startswith(text.rstrip("…")):
                failures.append(f"not note {part[2]}'s name: {text!r}")
        elif kind == "filed":
            note = by_id[part[2]]
            filed = [str(t).lower() for t in note.get("tags") or []] + [str(note.get("category") or "").lower()]
            if text.lower() not in filed:
                failures.append(f"not a tag of note {part[2]}: {text!r}")
        elif kind == "measure":
            if text not in measured and text not in rederived_insights(question, notes, on):
                failures.append(f"not a measured value: {text!r}")
        elif kind == "address":
            #: A link around a note's name: "[" and "](#/notes/<a note found>)".
            linked = re.fullmatch(r"\]\(#/notes/(\d+)\)", text)
            if text != "[" and not (linked and int(linked.group(1)) in by_id):
                failures.append(f"not a link to a note found: {text!r}")
        elif kind == "term":
            #: A word of the notes as written there, naming a thread or a
            #: name that links them (INBOX 787's overview).
            if not re.search(rf"\b{re.escape(text)}\b", by_id[part[2]]["content"]):
                failures.append(f"not a word of note {part[2]}: {text!r}")
        elif kind == "asked":
            if text.lower() not in f"{question} {asked_from}".lower():
                failures.append(f"not from the question: {text!r}")
        elif kind == "reading":
            #: How a misspelt question was read (Brief 90): the repair, run
            #: again on the question, gives the same words.
            from tessellate.ai import composer_ack, question_noise

            reads = {
                composer_ack.reading_of(question_noise.repair(question_noise.tidy(" ".join(q.split())), known=composer._note_words(notes)))
                for q in (question, asked_from)
                if q
            }
            if text not in reads:
                failures.append(f"not how the question reads: {text!r}")
        elif kind == "confirmed":
            #: The person's own word on an insight (decision 60): its source
            #: is in the line, ", as you told me on <date>." (INBOX 1483).
            if ", as you told me on " not in text:
                failures.append(f"a confirmed line with no source: {text!r}")
        elif kind == "computed":
            #: Worked out from the question alone (CHAT_PLAN decision 41): the
            #: utility, run again, says the same sentence.
            from tessellate.ai import utilities

            again = [t for k, t in (utilities.answer(question, salt=result.get("salt", "")) or []) if k == "computed"]
            if text not in again and not text.startswith(("It is ", "Today is ")):
                failures.append(f"not computed from the question: {text!r}")
        else:
            failures.append(f"unknown part kind {kind!r}")
    for row in result["grounding"]:
        content = by_id[row["note_id"]]["content"]
        span = _flat(content[row["start"]:row["end"]])
        body = row.get("original", row["sentence"]).rstrip("…").rstrip(".")
        if not (span[:1].lower() == body[:1].lower() and span[1:].startswith(body[1:])):
            failures.append(f"row {row['sentence']!r} does not point at its own text: {span!r}")
        if row["sentence"] not in result["text"]:
            failures.append(f"row {row['sentence']!r} is not in the answer")
    if EM_DASH in result["text"] or "!" in result["text"].replace("![", ""):
        failures.append("an em-dash or an exclamation mark")
    return failures


def _factual_parts(result: dict) -> int:
    return sum(1 for part in result["parts"] if part[0] != "template")


def redundancy(result: dict) -> float:
    """The most two quoted sentences in one answer share, token Jaccard."""
    quotes = list(dict.fromkeys(part[1] for part in result["parts"] if part[0] in ("quote", "picture", "shifted")))
    words = [set(composer._words(q)) for q in quotes]
    best = 0.0
    for i, a in enumerate(words):
        for b in words[i + 1:]:
            if a and b:
                best = max(best, len(a & b) / len(a | b))
    return best


_MARKDOWN = re.compile(r"\*\*|^> |^- \[[ x]\] |^- ", re.M)
_SENTENCE_END = re.compile(r"(?<=[.?:])\s+|\n+")


def sentence_lengths(text: str) -> list[int]:
    plain = _MARKDOWN.sub("", text)
    return [len(s.split()) for s in _SENTENCE_END.split(plain) if s.strip()]


def connectives(result: dict) -> set[str]:
    """The joining phrases an answer used: the templates with a word in them."""
    names = {value: key for key, value in composer.PHRASES.items()}
    return {names[p[1]] for p in result["parts"] if p[0] == "template" and re.search(r"[A-Za-z]", p[1])}


_FIGURE = re.compile(r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|fifty|hundred|half)\b", re.I)


def first_line(result: dict) -> list[tuple]:
    """The parts of the answer's first line."""
    out: list[tuple] = []
    parts = result["parts"]
    #: How a misspelt question was read comes before the answer (Brief 90):
    #: it is not the answer's first line.
    if parts and parts[0][0] == "template" and len(parts) > 2 and parts[1][0] == "reading":
        parts = parts[3:]
    for part in parts:
        if "\n" in part[1]:
            break
        out.append(part)
    return out


def answers_shape(result: dict, shape: str) -> bool:
    """Whether the first line answers the question's shape on its own."""
    line = first_line(result)
    if not line:
        return False
    text = "".join(p[1] for p in line)
    quoted = " ".join(p[1] for p in line if p[0] in ("quote", "picture", "shifted"))
    measures = [p[1] for p in line if p[0] == "measure"]
    dated = any(re.search(r"\d+ [A-Z][a-z]+|today|yesterday", m) for m in measures)
    if text.rstrip().endswith(":") and not quoted and shape not in ("list", "compare", "recent"):
        #: A list the person wrote, introduced by its count ("Your note
        #: **Launch risks** lists three:") with its entries on the lines
        #: below, is the list answer's own layout, whatever was asked.
        return bool(measures) and any(p[0] in ("quote", "shifted") for p in result["parts"][len(line):len(line) + 4])
    if shape == "count":
        return bool(_FIGURE.search(quoted))
    if shape == "when":
        return bool(composer.rec.looks_dated(quoted)) or (dated and bool(quoted))
    if shape == "status":
        return dated and bool(quoted)
    if shape in ("list", "compare", "recent", "recall"):
        return bool(measures) or bool(quoted)
    if shape == "utility":
        return any(p[0] == "computed" for p in line) or any(p[0] == "template" for p in line)
    return bool(quoted)


def run(data: dict | None = None, voice: str = "natural") -> list[dict]:
    """Every question composed, with its measures."""
    data = data or load()
    on = today(data)
    rows = []
    for entry in data["questions"]:
        notes = notes_for(entry, data)
        recent = str(entry.get("search_mode") or "").endswith("recent")
        result = composer.compose(entry["question"], notes, today=on, recent=recent, voice=voice)
        factual = _factual_parts(result)
        failures = trace_failures(result, entry["question"], notes, on)
        lengths = sentence_lengths(result["text"])
        rows.append(
            {
                "question": entry["question"],
                "shape": result["shape"],
                "text": result["text"],
                "result": result,
                "failures": failures,
                "grounded": 1.0 if not factual else (factual - len([f for f in failures if "row" not in f])) / factual,
                "redundancy": redundancy(result),
                "mean_sentence": sum(lengths) / len(lengths) if lengths else 0.0,
                "connectives": connectives(result),
                "first_line": answers_shape(result, result["shape"]),
                "words": len(result["text"].split()),
                "cited": len({row["note_id"] for row in result["grounding"]}),
            }
        )
    return rows


def _tokens(messages: list[dict]) -> tuple[int, int]:
    """(whole prompt, the notes message) in tokens, at the app's own measure
    (`context.CHARS_PER_TOKEN`, the same chars/4 the stats event reports)."""
    from tessellate.ai import context

    total = sum(len(m["content"]) for m in messages) // context.CHARS_PER_TOKEN
    return total, len(messages[-1]["content"]) // context.CHARS_PER_TOKEN


def context_rows(data: dict | None = None) -> list[dict]:
    """The prompt a running model reads for each question, before and after
    the composer's brief (`composer.brief`): the plain librarian prompt the
    Ask box and Chat's Ask mode send (`librarian.build_messages`), unbudgeted
    so the two are measured on the same notes."""
    from tessellate.ai import librarian

    data = data or load()
    rows = []
    for entry in data["questions"]:
        notes = notes_for(entry, data)
        recent = str(entry.get("search_mode") or "").endswith("recent")
        packed = composer.brief(entry["question"], notes, recent=recent)
        before = _tokens(librarian.build_messages(entry["question"], notes))
        after = _tokens(librarian.build_messages(entry["question"], packed["notes"] if packed else notes))
        rows.append(
            {
                "question": entry["question"],
                "notes": notes,
                "brief": packed,
                "prompt_before": before[0],
                "prompt_after": after[0],
                "notes_before": before[1],
                "notes_after": after[1],
            }
        )
    return rows


def context_summary(rows: list[dict]) -> dict:
    total = {key: sum(r[key] for r in rows) for key in ("prompt_before", "prompt_after", "notes_before", "notes_after")}
    return {
        **total,
        "briefed": sum(1 for r in rows if r["brief"]),
        "prompt_saved": round(1 - total["prompt_after"] / total["prompt_before"], 3),
        "notes_saved": round(1 - total["notes_after"] / total["notes_before"], 3),
    }


#: The phrases that join or open: the ones a reader hears as a template when
#: they come twice in one answer (INBOX 741, the owner: "ur note starting
#: with this says this. also ur not starting with this says this").
JOINERS = ("and_join", "on_top", "separately", "elsewhere", "another_note", "later_on", "then_on", "before_that",
           "earlier_on", "and_on", "latest_a", "latest_b", "latest_c", "going_by", "notes_have",
           "open_notes", "open_wrote", "open_put", "open_figure", "open_date", "closest_a", "closest_b")


def lead_in_repeats(result: dict) -> int:
    """How many joining or opening phrases come more than once in an answer."""
    joiners = {composer.PHRASES[k] for k in JOINERS}
    used = [p[1] for p in result["parts"] if p[0] == "template" and p[1] in joiners]
    return len(used) - len(set(used))


def opener(result: dict) -> str:
    """How the answer starts: its first worded phrase, or "(quote)" when it
    starts with the person's own sentence."""
    for part in result["parts"]:
        if part[0] != "template":
            return f"({part[0]})"
        if re.search(r"[A-Za-z]", part[1]):
            return part[1]
    return ""


def joiner_phrases() -> set[str]:
    """Every wording, in either voice, of the joining and opening phrases."""
    from tessellate.ai import composer_tables

    keys = set(JOINERS)
    for voice in composer_tables.VOICES:
        for key in JOINERS:
            keys.update(composer_tables.VOICE_VARIANTS[voice].get(key, ()))
    return {composer.PHRASES[k] for k in keys if k in composer.PHRASES}


def session(data: dict | None = None, turns: int = 20, dialogue: bool = True) -> list[dict]:
    """The showcase's first `turns` questions asked in one conversation
    (CHAT_PLAN decision 34): with `dialogue`, each turn knows the ones before
    (`composer.Dialogue`); without, each is asked alone, the baseline."""
    data = data or load()
    on = today(data)
    talk = composer.Dialogue(salt="eval-session") if dialogue else None
    rows = []
    for entry in data["questions"][:turns]:
        notes = notes_for(entry, data)
        recent = str(entry.get("search_mode") or "").endswith("recent")
        result = composer.compose(entry["question"], notes, today=on, recent=recent, dialogue=talk)
        rows.append({"question": entry["question"], "result": result, "failures": trace_failures(result, entry["question"], notes, on)})
    return rows


def session_summary(rows: list[dict]) -> dict:
    """Variation across one conversation: how many joining or opening phrases
    come more than once in the whole session, and how many different ways
    its answers open."""
    joiners = joiner_phrases()
    used = [p[1] for r in rows for p in r["result"]["parts"] if p[0] == "template" and p[1] in joiners]
    return {
        "turns": len(rows),
        "session_lead_in_repeats": len(used) - len(set(used)),
        "session_openers_distinct": len({opener(r["result"]) for r in rows}),
        "session_grounded": all(not r["failures"] for r in rows),
    }


def regenerations(question: str = "What do my notes say about running?", times: int = 3) -> list[dict]:
    """One question asked again `times` times in one chat (Ask again)."""
    data = load()
    entry = next(e for e in data["questions"] if e["question"] == question)
    notes = notes_for(entry, data)
    return [composer.compose(question, notes, today=today(data), turn=i + 1, salt="eval-again") for i in range(times)]


def summary(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "questions": n,
        "grounded": min(r["grounded"] for r in rows),
        "redundancy_mean": round(sum(r["redundancy"] for r in rows) / n, 3),
        "redundancy_max": round(max(r["redundancy"] for r in rows), 3),
        "mean_sentence_words": round(sum(r["mean_sentence"] for r in rows) / n, 1),
        "connectives_per_answer": round(sum(len(r["connectives"]) for r in rows) / n, 2),
        "connectives_distinct": len(set().union(*(r["connectives"] for r in rows))),
        "first_line_answers": sum(1 for r in rows if r["first_line"]),
        "words_mean": round(sum(r["words"] for r in rows) / n, 1),
        "notes_cited_mean": round(sum(r["cited"] for r in rows) / n, 2),
        "lead_in_repeats": sum(1 for r in rows if lead_in_repeats(r["result"])),
        "openers_distinct": len({opener(r["result"]) for r in rows}),
        #: A note introduced as saying something ("Your note X says:"), the
        #: shape INBOX 741 removed.
        "says_colon": sum(len(re.findall(r"\b(?:says|said): ", r["text"])) for r in rows),
    }


# --- the voice eval (INBOX 741): about a hundred questions -------------------------
#
# The 25 above plus `fixtures/composer/voice_741.json`: casual and indirect
# questions, typos and text-speak, every question kind, follow-ons read
# against the turn before, and a notebook of short untitled jottings (the
# kind "your note starting with ... says" came from). Its notes are retrieved
# here by a fixed lexical stand-in for the route's search (`retrieve`), so the
# eval is deterministic and needs no server; the 25 keep the route's own.

VOICE = Path(__file__).parent / "fixtures" / "composer" / "voice_741.json"


def load_voice() -> dict:
    return json.loads(VOICE.read_text(encoding="utf-8"))


def untitled_notes(voice: dict, on: date) -> list[dict]:
    from datetime import timedelta

    return [
        {"id": n["id"], "content": n["content"], "created_at": (on - timedelta(days=n["days_ago"])).isoformat(), "tags": []}
        for n in voice["untitled"]
    ]


def retrieve(question: str, notes: list[dict], limit: int = 8) -> list[dict]:
    """The notes a search would hand the composer, best first: a question
    word in a note's heading counts double, in its body once, a typo matched
    to the notebook's own words as search does. A stand-in, fixed so the
    eval measures the composer and not the search."""
    views = [v for v in (composer.read_note(n, i) for i, n in enumerate(notes)) if v]
    terms = composer._fit_terms(composer.subject_terms(question), views)
    stems = {composer._stem(t) for t in terms}
    scored = []
    for view in views:
        score = sum(
            2.0 * composer._holds(t, view.title_words) + composer._holds(t, view.words) + 0.5 * composer._holds(t, view.filed_words)
            for t in stems
        )
        if score > 0:
            scored.append((-score, str(view.note.get("created_at")), view.note))
    scored.sort(key=lambda row: (row[0], [-ord(c) for c in row[1]]))
    return [note for _, _, note in scored[:limit]]


def _syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    groups = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e") and not w.endswith(("le", "ee")) and groups > 1:
        groups -= 1
    return max(1, groups)


def reading_ease(text: str) -> float:
    """Flesch reading ease of the answer as read: 60 to 70 is plain English,
    higher is easier."""
    plain = _MARKDOWN.sub("", text)
    sentences = [s for s in _SENTENCE_END.split(plain) if s.strip()]
    words = plain.split()
    if not sentences or not words:
        return 0.0
    syllables = sum(_syllables(w) for w in words)
    return 206.835 - 1.015 * len(words) / len(sentences) - 84.6 * syllables / len(words)


def run_voice(module=composer) -> list[dict]:  # noqa: ANN001
    """Every voice question composed by `module` (the composer, or an older
    copy of it for a before-and-after), each with its measures, in order, the
    turn before's answer passed where `module.compose` takes one."""
    import inspect

    data = load()
    voice = load_voice()
    on = today(data)
    showcase = [{**n, "connected": False} for n in data["notes"]]
    jottings = untitled_notes(voice, on)
    takes_previous = "previous" in inspect.signature(module.compose).parameters
    rows: list[dict] = []
    previous_text = ""
    for entry in voice["questions"]:
        pool = jottings if entry.get("notebook") == "untitled" else showcase
        question, said, asked_from = entry["question"], "", ""
        if entry.get("previous"):
            before = module.compose(entry["previous"], retrieve(entry["previous"], pool), today=on)
            follow = module.follow_on(question, [{"question": entry["previous"], "answer": before["text"]}])
            if follow:
                question, said, asked_from = follow.question, follow.said, entry["previous"]
        notes = retrieve(question, pool)
        kwargs = {"today": on, "said": said}
        if takes_previous:
            kwargs["previous"] = previous_text
        result = module.compose(question, notes, **kwargs)
        failures = trace_failures(result, question, notes, on, asked_from) if notes else []
        factual = _factual_parts(result)
        untitled_ids = {n["id"] for n in jottings}
        rows.append(
            {
                "category": entry["category"],
                "question": entry["question"],
                "expect": entry["expect"],
                "shape": result["shape"],
                "text": result["text"],
                "result": result,
                "failures": failures,
                "grounded": 1.0 if not factual else (factual - len([f for f in failures if "row" not in f])) / factual,
                "kind_right": result["shape"] == entry["expect"],
                "first_line": answers_shape(result, result["shape"]),
                "words": len(result["text"].split()),
                "mean_sentence": (lambda ls: sum(ls) / len(ls) if ls else 0.0)(sentence_lengths(result["text"])),
                "ease": reading_ease(result["text"]),
                "opener": opener(result),
                "lead_in_repeats": lead_in_repeats(result),
                #: The owner's complaint, counted: a note with no heading named
                #: by its first words.
                "named_by_first_words": sum(1 for p in result["parts"] if p[0] == "title" and p[2] in untitled_ids),
                "says_colon": len(re.findall(r"\b(?:says|said): ", result["text"])),
            }
        )
        previous_text = result["text"]
    return rows


def voice_summary(rows: list[dict]) -> dict:
    n = len(rows)
    by: dict[str, list[int]] = {}
    for r in rows:
        tally = by.setdefault(r["category"], [0, 0])
        tally[0] += r["kind_right"]
        tally[1] += 1
    answered = [r for r in rows if r["result"]["grounding"]]
    return {
        "questions": n,
        "answered": len(answered),
        "grounded": min(r["grounded"] for r in rows),
        "kind_right": sum(r["kind_right"] for r in rows),
        "kind_right_by_category": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by.items())},
        "first_line_answers": sum(1 for r in answered if r["first_line"]),
        "says_colon": sum(r["says_colon"] for r in rows),
        "named_by_first_words": sum(r["named_by_first_words"] for r in rows),
        "lead_in_repeats": sum(1 for r in rows if r["lead_in_repeats"]),
        "openers_distinct": len({r["opener"] for r in rows}),
        #: Two answers in a row opening with the same words: "no template
        #: repeated in a session" (CHAT_PLAN decision 25), said as a count.
        "same_opener_twice_running": sum(
            1 for a, b in zip(rows, rows[1:]) if a["opener"] == b["opener"] and a["opener"] not in ("(quote)", "(asked)")
        ),
        "words_mean": round(sum(r["words"] for r in answered) / max(1, len(answered)), 1),
        "mean_sentence_words": round(sum(r["mean_sentence"] for r in answered) / max(1, len(answered)), 1),
        "reading_ease": round(sum(r["ease"] for r in answered) / max(1, len(answered)), 1),
    }


# --- the noise eval (INBOX 741): questions typed the way people type ---------------
#
# The owner: "does it cover any and ALL typos, maybe use similarity or
# meaning, cover all slang like pls, ty, lol, u, r, wym, etc?". Two sets,
# reported apart because they mean different things:
#
# - **hand**: `fixtures/composer/noise_741.json`, eighty questions written the
#   way people type. The repairs were built against these, so they show what
#   is covered, not how well it generalises.
# - **derived**: every clean question of both evals put through five fixed
#   kinds of noise nobody tuned against (all caps; all lowercase with no
#   punctuation; an emoji after it; one slip to a neighbouring key in its
#   first word; a vowel dropped from its first word). The kind expected is
#   the clean question's own: noise must not change what it asks.

NOISE = Path(__file__).parent / "fixtures" / "composer" / "noise_741.json"

#: The neighbour a slipped finger hits instead, one per letter, fixed.
_SLIP = dict(zip("abcdefghijklmnopqrstuvwxyz", "snvsrgfjokjkbmplwtdyibeczt"))


def _noisy(question: str) -> list[tuple[str, str]]:
    first, _, rest = question.partition(" ")
    variants = [
        ("caps", question.upper()),
        ("lower_no_punctuation", re.sub(r"[^\w\s'-]", "", question.lower())),
        ("emoji", f"{question} \U0001F914"),
    ]
    if len(first) >= 3 and first[1].isalpha():
        slipped = first[0] + _SLIP.get(first[1].lower(), first[1]) + first[2:]
        variants.append(("slip", f"{slipped} {rest}".strip()))
    vowels = [i for i, c in enumerate(first) if c.lower() in "aeiou" and i > 0]
    if len(first) >= 4 and vowels:
        dropped = first[: vowels[0]] + first[vowels[0] + 1 :]
        variants.append(("dropped_vowel", f"{dropped} {rest}".strip()))
    return variants


def run_noise(module=composer) -> list[dict]:  # noqa: ANN001
    """Every noisy question classified by `module`, against the kind expected."""
    rows: list[dict] = []
    for entry in json.loads(NOISE.read_text(encoding="utf-8"))["questions"]:
        got = module.classify(entry["question"])
        rows.append({"set": "hand", "kind": "hand", "question": entry["question"], "expect": entry["expect"], "got": got})
    clean = [e["question"] for e in load()["questions"]] + [
        e["question"] for e in load_voice()["questions"] if e["category"] in ("kinds", "untitled") and e["expect"] != "multi"
    ]
    for question in clean:
        expect = composer.classify(question)
        for kind, noisy in _noisy(question):
            rows.append({"set": "derived", "kind": kind, "question": noisy, "expect": expect, "got": module.classify(noisy)})
    for row in rows:
        row["right"] = row["got"] == row["expect"]
    return rows


def noise_summary(rows: list[dict]) -> dict:
    out: dict[str, str] = {}
    for key in ("hand", "derived"):
        subset = [r for r in rows if r["set"] == key]
        out[key] = f"{sum(r['right'] for r in subset)}/{len(subset)}"
    kinds: dict[str, list[int]] = {}
    for r in rows:
        if r["set"] == "derived":
            tally = kinds.setdefault(r["kind"], [0, 0])
            tally[0] += r["right"]
            tally[1] += 1
    out["derived_by_noise"] = {k: f"{v[0]}/{v[1]}" for k, v in sorted(kinds.items())}
    return out


def run_conversation() -> list[dict]:
    """Every conversational turn of `noise_741.json`, in order, each replied
    to with the turn before's reply passed in, as Chat does: the kind of
    reply, whether a search would have fired, and the reply itself."""
    from tessellate.ai import intent

    rows: list[dict] = []
    previous = ""
    last_question = "What is the latest on the sync rewrite?"
    for entry in json.loads(NOISE.read_text(encoding="utf-8"))["conversation"]:
        message, expect = entry["message"], entry["expect"]
        small = intent.classify(message) == intent.SMALLTALK
        if expect.startswith("question:"):
            got = "smalltalk" if small else f"question:{composer.classify(message)}"
            reply = ""
        else:
            got = composer.social_kind(message) if small else "searched"
            reply = composer.social(message, "smalltalk", previous, last_question) if small else ""
        rows.append({"message": message, "expect": expect, "got": got, "right": got == expect, "searched": not small, "reply": reply})
        previous = reply or previous
    return rows


def conversation_summary(rows: list[dict]) -> dict:
    social = [r for r in rows if not r["expect"].startswith("question:")]
    replies = [r["reply"] for r in social if r["reply"]]
    return {
        "turns": len(rows),
        "right_kind": f"{sum(r['right'] for r in rows)}/{len(rows)}",
        "searched_small_talk": sum(1 for r in social if r["searched"]),
        "same_reply_twice_running": sum(1 for a, b in zip(replies, replies[1:]) if a == b),
        "distinct_replies": len(set(replies)),
    }


def run_did_you_mean() -> dict:
    """How often "Did you mean ...?" is offered over the hand-written noisy
    questions, and how often the reading answered or the one offered is the
    kind the question asked for."""
    data = load()
    on = today(data)
    pool = [{**n, "connected": False} for n in data["notes"]]
    fired = right = right_without = 0
    for entry in json.loads(NOISE.read_text(encoding="utf-8"))["questions"]:
        question = entry["question"]
        result = composer.compose(question, retrieve(question, pool), today=on)
        chips = [n for n in result["next"] if n.startswith("Did you mean")]
        if not chips:
            continue
        fired += 1
        follow = composer.follow_on(chips[0], [{"question": question, "answer": result["text"]}])
        offered = composer.classify(follow.question) if follow else None
        right += result["shape"] == entry["expect"] or offered == entry["expect"]
        right_without += result["shape"] == entry["expect"]
    total = len(json.loads(NOISE.read_text(encoding="utf-8"))["questions"])
    return {"questions": total, "fired": fired, "right_with_offer": right, "right_without_offer": right_without}


# --- CHAT_PLAN Phase 6, decision 40: the five new eval sets -------------------------
#
# Each set is a fixture in `fixtures/composer/` (written by a seeded generator;
# every expected value is worked out from the row itself, never by running
# the engine) with a `run_*` and a `*_summary`; `tests/test_engine_dialogue.py`
# holds the floors.

FIXTURES = Path(__file__).parent / "fixtures" / "composer"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def run_insights() -> list[dict]:
    """Each insight row: the line the engine says, and the line the row's own
    numbers give (the template filled from `expect`, not from the engine)."""
    from tessellate.ai import composer_tables, insights

    data = _fixture("insights_1010.json")
    on = date.fromisoformat(data["today"])
    out = []
    for row in data["rows"]:
        expect = row["expect"]
        if row["rule"] == "drift":
            said = [i.text for i in insights.notebook(row["notes"], on, limit=5) if i.rule == "drift"]
        else:
            result = composer.compose(row["question"], row["notes"], today=on)
            #: A recurrence after a lead that said its count closes in its short
            #: form (`insights.after_lead`, decision 52): ends with the hedge.
            hedges = tuple(f"{h}." for h in composer_tables.INSIGHT_HEDGES.values())
            said = [p[1] for p in result["parts"] if p[0] == "measure" and (len(p[1]) > 30 or p[1].lower().endswith(hedges))]
        wanted = None
        short = None
        if expect and row["rule"] == "recurrence":
            after = f", {_count_word(expect['after'])} of them after work" if expect["after"] >= 3 else ""
            wanted = composer_tables.INSIGHT_TEMPLATES["recurrence"].format(
                subject=row["subject"], count=expect["count"], since=expect["since"], after=after, hedge=expect["hedge"])
            tail = after.lstrip(", ")
            short = f"{tail[:1].upper()}{tail[1:]}; {expect['hedge']}." if tail else f"{expect['hedge'][:1].upper()}{expect['hedge'][1:]}."
        elif expect and row["rule"] == "streak":
            wanted = composer_tables.INSIGHT_TEMPLATES["streak"].format(subject=row["subject"], weeks=expect["weeks"])
        elif expect and row["rule"] == "drift":
            wanted = composer_tables.INSIGHT_TEMPLATES["drift"].format(plan=expect["plan"], since=expect["since"])
        out.append({"id": row["id"], "positive": row["positive"], "said": said, "wanted": wanted, "short": short,
                    "right": (wanted in said or (short is not None and short in said)) if row["positive"] else not said})
    return out


def insights_summary(rows: list[dict]) -> dict:
    positives = [r for r in rows if r["positive"]]
    negatives = [r for r in rows if not r["positive"]]
    return {
        "rows": len(rows),
        "positive_recall": round(sum(r["right"] for r in positives) / len(positives), 3),
        "negatives_silent": sum(r["right"] for r in negatives),
        "negatives": len(negatives),
        #: Every line said is one the row's numbers give, word for word.
        "measured_rederived": all(not r["said"] or r["said"][0] in (r["wanted"], r["short"]) for r in rows if r["positive"]),
    }


def run_dialogues() -> list[dict]:
    """Thirty conversations of twenty turns over the showcase notebook: each
    terse turn's reading (`follow_on`'s kind) against the row's, every answer
    traced, and the variation inside each conversation."""
    data = _fixture("dialogues_1010.json")
    show = load()
    on = today(show)
    entries = show["questions"]
    out = []
    for dialogue in data["dialogues"]:
        talk = composer.Dialogue(salt=dialogue["id"])
        turns = []
        for turn in dialogue["turns"]:
            entry = entries[turn["base"]]
            notes = notes_for(entry, show)
            follow = composer.follow_on(turn["text"], talk.history) if talk.history else None
            got = follow.kind if follow else None
            if turn["effect"] == "social":
                turns.append({**turn, "got": got, "right": got is None, "failures": []})
                continue
            result = composer.compose(turn["text"], notes, today=on, dialogue=talk)
            read = follow.question if follow else turn["text"]
            turns.append({**turn, "got": got, "right": got == turn["kind"], "failures": trace_failures(result, read, notes, on, turn["text"]), "result": result})
        answered = [t for t in turns if "result" in t]
        joiners = joiner_phrases()
        used = [p[1] for t in answered for p in t["result"]["parts"] if p[0] == "template" and p[1] in joiners]
        out.append({
            "id": dialogue["id"],
            "turns": turns,
            "lead_in_repeats": len(used) - len(set(used)),
            "openers_distinct": len({opener(t["result"]) for t in answered}),
        })
    return out


def dialogues_summary(rows: list[dict]) -> dict:
    turns = [t for r in rows for t in r["turns"]]
    tagged = {}
    for effect in ("none", "ellipsis", "control", "reference", "correction", "social"):
        group = [t for t in turns if t["effect"] == effect]
        if group:
            tagged[effect] = round(sum(t["right"] for t in group) / len(group), 3)
    return {
        "dialogues": len(rows),
        "turns": len(turns),
        "kind_accuracy": round(sum(t["right"] for t in turns) / len(turns), 3),
        "by_effect": tagged,
        "grounded": all(not t["failures"] for t in turns),
        "lead_in_repeats_max": max(r["lead_in_repeats"] for r in rows),
        "openers_distinct_min": min(r["openers_distinct"] for r in rows),
    }


def run_acts() -> list[dict]:
    from datetime import datetime

    from tessellate.ai import commands

    data = _fixture("acts_1010.json")
    now = datetime.fromisoformat(data["now"])
    out = []
    for act in data["acts"]:
        cmd = commands.parse(act["phrase"], now)
        got = (cmd.verb, cmd.object, cmd.confirm) if cmd else None
        out.append({"phrase": act["phrase"], "got": got, "right": got == (act["verb"], act["object"], act["confirm"]), "lookalike": False})
    for phrase in data["lookalikes"]:
        cmd = commands.parse(phrase, now)
        out.append({"phrase": phrase, "got": cmd and cmd.verb, "right": cmd is None, "lookalike": True})
    return out


def acts_summary(rows: list[dict]) -> dict:
    acts = [r for r in rows if not r["lookalike"]]
    looks = [r for r in rows if r["lookalike"]]
    return {
        "acts": len(acts),
        "parse_accuracy": round(sum(r["right"] for r in acts) / len(acts), 3),
        "lookalikes": len(looks),
        "false_positive_acts": sum(not r["right"] for r in looks),
    }


def run_web() -> list[dict]:
    data = _fixture("web_1010.json")
    on = date.fromisoformat(data["today"])
    out = []
    for row in data["rows"]:
        sources = [{"id": -(i + 1), "kind": "web", "url": p["url"], "content": f"{p['title']}\n\n{p['text']}"} for i, p in enumerate(row["pages"])]
        result = composer.compose(row["question"], sources, today=on)
        pages = {p["url"]: p for p in row["pages"]}
        spans = all(g.get("url") in pages and g["sentence"].rstrip(".") in pages[g["url"]]["text"] for g in result["grounding"])
        out.append({
            "id": row["id"],
            "answered": bool(result["grounding"]),
            "spans": spans and bool(result["grounding"]),
            "by_url": all(g.get("kind") == "web" and g.get("url") for g in result["grounding"]),
            "first_right": bool(result["grounding"]) and result["grounding"][0].get("url") == row["answer_url"],
        })
    return out


def web_summary(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "rows": n,
        "web_spans": round(sum(r["spans"] for r in rows) / n, 3),
        "cited_by_url": round(sum(r["by_url"] for r in rows) / n, 3),
        "first_from_the_right_page": round(sum(r["first_right"] for r in rows) / n, 3),
    }


def run_sources() -> list[dict]:
    data = _fixture("sources_1010.json")
    on = date.fromisoformat(data["today"])
    out = []
    for row in data["rows"]:
        result = composer.compose(row["question"], row["sources"], today=on)
        first = result["grounding"][0] if result["grounding"] else {}
        expect = row["expect"]
        out.append({
            "id": row["id"],
            "kind_right": first.get("kind") == expect["kind"] and first.get("note_id") == expect["id"],
            "said_right": first.get("said") == expect["said"],
            "failures": trace_failures(result, row["question"], row["sources"], on),
        })
    return out


def sources_summary(rows: list[dict]) -> dict:
    n = len(rows)
    return {
        "rows": n,
        "kind_right": round(sum(r["kind_right"] for r in rows) / n, 3),
        "caption_and_quote_right": round(sum(r["said_right"] for r in rows) / n, 3),
        "grounded": all(not r["failures"] for r in rows),
    }


def phase6_report() -> dict:
    return {
        "insights": insights_summary(run_insights()),
        "dialogues": dialogues_summary(run_dialogues()),
        "acts": acts_summary(run_acts()),
        "web": web_summary(run_web()),
        "sources": sources_summary(run_sources()),
    }


if __name__ == "__main__":  # pragma: no cover - the report's table
    import sys

    rows = run()
    for row in rows:
        if "-v" in sys.argv:
            print(f"#### {row['question']} [{row['shape']}]\n\n{row['text']}\n")
        print(
            f"- {row['question']} [{row['shape']}] first line {'yes' if row['first_line'] else 'no'}, "
            f"redundancy {row['redundancy']:.2f}, {row['mean_sentence']:.1f} words a sentence, "
            f"{len(row['connectives'])} connectives{', FAIL ' + '; '.join(row['failures']) if row['failures'] else ''}"
        )
    print(json.dumps(summary(rows), indent=1))
    print(json.dumps(context_summary(context_rows()), indent=1))
    print(json.dumps({"alone": session_summary(session(dialogue=False)), "in_one_chat": session_summary(session())}, indent=1))
    if "--phase6" in sys.argv:
        print(json.dumps(phase6_report(), indent=1))


    if "--voice" in sys.argv:
        voice_rows = run_voice()
        for row in voice_rows:
            if "-v" in sys.argv:
                print(f"#### [{row['category']}] {row['question']} [{row['shape']}, expected {row['expect']}]\n\n{row['text']}\n")
            if row["failures"] or not row["kind_right"]:
                print(f"- {row['question']}: {row['shape']} (expected {row['expect']}) {'; '.join(row['failures'])}")
        print(json.dumps(voice_summary(voice_rows), indent=1))
    if "--noise" in sys.argv:
        noise_rows = run_noise()
        for row in noise_rows:
            if not row["right"]:
                print(f"- [{row['set']}/{row['kind']}] {row['question']!r}: {row['got']} (expected {row['expect']})")
        print(json.dumps(noise_summary(noise_rows), indent=1))
        conversation = run_conversation()
        for row in conversation:
            if not row["right"]:
                print(f"- {row['message']!r}: {row['got']} (expected {row['expect']})")
        print(json.dumps(conversation_summary(conversation), indent=1))
        print(json.dumps(run_did_you_mean(), indent=1))
