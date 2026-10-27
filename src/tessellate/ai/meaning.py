"""Find by meaning in every search box (Brief 94, INBOX 857).

The owner: "half the time Im trying to find a specific object, feature, or
setting and I cant remember the exact name of it so Im left guessing what it
is called". So every box that searches the app's own things (Settings, the
command palette, Help, the manual, Find anything's action rows) reads a query
as the things it names, each of them a group of words that mean the same
("bin", "trash", "deleted"), with the request's own words dropped ("how do I",
"make", "my") and a word one slip from a known word read as that word (the
composer's typo rule, `question_noise.distance` and `allowance`).

The tables live here and are served once (`GET /read/words`); the matching
runs in the page (`frontend/js/meaning.js`, the same rule) because the rows it
matches are the page's own. `alts` and `holds` here are the same rule for the
server's own lookups (the Guide's fallback, `help_chat._matching_topics`) and
for the tests. `tests/fixtures/meaning_queries_1011.json` is the sixty-query
eval, measured in the browser by `scratchpad/ui-sweeps/meaning94.js`.

**A group is written head first**: its first word is the thing's own name,
and a row holding the head ranks above one holding only another word of the
group ("mascot" finds "Corner companion" before "Atlas and faces").
"""

from __future__ import annotations

import re

from tessellate.ai import question_noise

GROUPS: tuple[tuple[str, ...], ...] = (
    #: The Settings groups (CHAT_PLAN section 2, the settings row); the first
    #: is pinned by tests/test_phrase_filters.py.
    ("dark", "night", "theme", "light mode", "dim", "black"),
    ("text size", "font size", "bigger", "smaller", "zoom", "larger", "scale", "font", "tiny", "huge", "readable"),
    ("password", "lock", "pin", "passcode", "sign in", "log in", "unlock", "login", "locked"),
    ("backup", "back up", "copy", "restore", "export", "save a copy", "snapshot"),
    ("model", "ollama", "llm", "ai", "local model", "brain", "language model"),
    ("battery", "power", "save power", "energy", "laptop", "unplugged", "drain", "charge", "charging"),
    ("privacy", "private", "tracking", "telemetry", "data", "share"),
    ("notification", "notify", "alert", "remind", "sound", "ding", "do not disturb", "dont disturb", "disturb", "mute", "quiet", "popup", "toast"),
    ("spelling", "spellcheck", "spell check", "dictionary", "proofread", "autocorrect", "auto correct", "typo", "mistake", "grammar"),
    ("phone", "mobile", "other device", "lan", "network", "wifi", "tablet", "ipad", "iphone", "android", "device"),
    ("encrypt", "encryption", "vault", "secret", "secure"),
    ("motion", "animation", "reduce motion", "moving", "still", "animated", "movement", "move"),
    ("colour", "color", "accent", "palette", "look", "appearance", "tint", "hue"),
    ("shortcut", "keyboard", "hotkey", "keys", "key binding", "keybinding"),
    ("bin", "delete", "trash", "recycle", "remove", "binned", "rubbish", "garbage", "undelete", "deleted"),
    ("import", "obsidian", "markdown files", "bring in", "vault import", "old notes", "notion", "evernote", "migrate"),
    ("search", "find", "similar", "semantic", "embedding", "meaning", "intent", "vector"),
    ("companion", "mascot", "buddy", "character", "little guy", "guy", "robot", "pet", "creature", "atlas"),
    #: The app's objects and tools by the names people give them.
    ("forget", "forgot", "recovery", "recover", "lost", "reset"),
    ("slow", "laggy", "lag", "sluggish", "performance", "speed up", "freeze", "stutter", "janky"),
    ("background", "wallpaper", "wash", "generative", "backdrop"),
    ("glass", "blur", "blurry", "frosted", "transparent", "translucent", "see-through", "sheen", "opacity"),
    ("whiteboard", "board", "canvas", "drawing", "draw", "sketch", "doodle", "paint"),
    ("mind map", "mindmap", "mind-map", "brainstorm"),
    ("timeline", "calendar", "schedule", "agenda", "diary", "today's note"),
    ("reminder", "todo", "to do", "to-do", "to do list", "task", "checklist", "due"),
    ("timer", "pomodoro", "countdown", "stopwatch", "focus timer"),
    ("count words", "word count", "word counter", "word goal"),
    ("ocr", "scan", "read text", "text in image", "picture", "image", "photo", "tesseract"),
    ("dictate", "dictation", "voice", "speech", "speak", "talk", "voice typing", "transcribe"),
    ("captions", "subtitles", "caption", "transcript"),
    ("statistics", "stats", "how many", "numbers", "streak", "pace"),
    ("writing", "write", "written", "wrote"),
    ("remember", "memory", "memories", "about me", "knows about me", "profile"),
    ("simple", "simpler", "simplify", "minimal", "declutter", "basic", "fewer"),
    ("web", "internet", "online", "offline", "reach out", "connection", "browse the web"),
    ("pull", "download", "install", "fetch"),
)

#: Words of a request that name no thing ("how do I turn off the animations",
#: "get my deleted stuff back"): dropped, so the rest must match. A query of
#: nothing but these keeps them all.
FILLER = frozenset(
    """a an the my me i to of for in on off how do does can where is are it
    change set make turn stop disable enable switch want please settings
    setting option options notes note notebook everything all
    from with and or get got stuff thing things back ive im dont cant wont
    too much very really little lot lots which what why when who use using
    go app apps there this that these those be been being have has had
    some any just more less again way show find access""".split()
)

_WORD = re.compile(r"[a-z0-9][a-z0-9']*")


def words_of(text: str) -> list[str]:
    """Lower-cased words, an apostrophe dropped ("I've" is "ive"), a hyphen a
    break ("battery-efficient" is two words)."""
    return [w.replace("'", "") for w in _WORD.findall(text.lower())]


def stem(word: str) -> str:
    """The word without a plural or tense ending, for matching at a word
    start ("deleted" holds "delet", which "delete" starts with)."""
    for end, keep in (("ies", 3), ("ing", 5), ("ed", 4), ("es", 4), ("s", 3)):
        if word.endswith(end) and len(word) - len(end) >= keep:
            return word[: -len(end)]
    return word


def _group_of(word: str) -> tuple[str, ...] | None:
    root = stem(word)
    for group in GROUPS:
        for said in group:
            if " " in said:
                continue
            if word == said or root == stem(said):
                return group
    return None


def _vocabulary(extra: set[str] | frozenset[str] = frozenset()) -> set[str]:
    out = set(FILLER) | set(extra)
    for group in GROUPS:
        for said in group:
            out.update(said.split())
    return out


def fold_typo(word: str, vocab: set[str]) -> str | None:
    """The known word a slip of `word` was meant to be, or None."""
    if word in vocab or len(word) < 4 or word.isdigit():
        return None
    room = question_noise.allowance(word)
    best, best_d = None, room + 1e-9
    for known in vocab:
        if abs(len(known) - len(word)) > 2 or known[0] != word[0] and known[:2] != word[1::-1]:
            continue
        d = question_noise.distance(word, known)
        if d < best_d:
            best, best_d = known, d
    return best


def _take_phrases(rest: str) -> tuple[list[list[str]], str]:
    """The groups named by a whole phrase, and the text left once they are taken out."""
    out: list[list[str]] = []
    for group in GROUPS:
        #: Longest first, every one: "to do list" before "to do", and "bring
        #: in my old notes" is one thing however many of its phrases it says.
        phrases = [p for p in sorted(group, key=len, reverse=True) if " " in p and f" {p} " in rest]
        for phrase in phrases:
            rest = rest.replace(f" {phrase} ", " ", 1)
        if phrases:
            out.append(list(group))
    return out, rest


def _add_word(out: list[list[str]], word: str) -> None:
    """One more word: it joins the thing it already names, or is a new thing."""
    group = _group_of(word)
    #: Said twice ("what it remembers about me") is one thing.
    same = next((g for g in out if group and group[0] in g), None)
    if same is not None:
        #: Every word typed for the thing counts as typed ("which ai
        #: model" holds "model" as closely as "ai").
        if word in same:
            same.remove(word)
        same.insert(0, word)
        return
    found = [word] if stem(word) == word else [word, stem(word)]
    out.append(found + [w for w in (group or ()) if w not in found])


def alts(query: str, vocab: set[str] | frozenset[str] = frozenset()) -> list[list[str]]:
    """The things `query` names, each as the words that mean it."""
    known = _vocabulary(vocab)
    said = [fold_typo(w, known) or w for w in words_of(query)]
    out, rest = _take_phrases(f" {' '.join(said)} ")
    left = rest.split()
    named = [w for w in left if w not in FILLER]
    for word in named if (named or out) else left:
        _add_word(out, word)
    return out


#: A word held whole, or with an ending ("delet" in "deleted"), never as the
#: start of another word ("memory" is not in "Tessellate").
_ENDING = "(?:s|es|ed|d|e|ing|ings|er|ers|ion|ions|ly|y)?"


def _text(text: str) -> str:
    return f" {' '.join(words_of(text))} "


def _at(group: list[str], lowered: str) -> int:
    for index, word in enumerate(group):
        if re.search(f" {re.escape(word.replace('-', ' '))}{_ENDING}(?= )", lowered):
            return index
    return -1


def missing(things: list[list[str]], text: str) -> int:
    """How many of the things named `text` does not hold."""
    lowered = _text(text)
    return sum(1 for group in things if _at(group, lowered) < 0)


def holds(things: list[list[str]], text: str) -> bool:
    """Every thing named has a word of its group in `text`."""
    return missing(things, text) == 0


def closeness(things: list[list[str]], text: str) -> float:
    """1 per thing held by the word as typed, a half by the next word of its
    group, a third by the one after."""
    lowered = _text(text)
    return sum(1 / (1 + _at(g, lowered)) for g in things if _at(g, lowered) >= 0)


#: The rows' vectors, by text: Settings sends the same few hundred labels on
#: every keystroke, and each is embedded once per process.
_VECTORS: dict[str, object] = {}
_VECTORS_CAP = 4000
NEAR_FLOOR = 0.45
NEAR_TOP = 5


def near(query: str, texts: list[str], embed_many) -> list[dict]:  # noqa: ANN001
    """**Close in meaning** (Brief 94): with an embedding model on, the rows
    whose text is nearest the query by cosine, best first, at most
    `NEAR_TOP` and none under `NEAR_FLOOR`. `embed_many` is the embedder's."""
    import numpy as np

    fresh = [t for t in dict.fromkeys(texts) if t not in _VECTORS]
    if len(_VECTORS) + len(fresh) > _VECTORS_CAP:
        _VECTORS.clear()
        fresh = list(dict.fromkeys(texts))
    vectors = embed_many([query, *fresh])
    if not vectors or vectors[0] is None:
        return []
    _VECTORS.update({text: vector for text, vector in zip(fresh, vectors[1:]) if vector is not None})
    asked = np.asarray(vectors[0], dtype="float32")
    asked = asked / (np.linalg.norm(asked) or 1.0)
    scored = []
    for index, text in enumerate(texts):
        vector = _VECTORS.get(text)
        if vector is None:
            continue
        row = np.asarray(vector, dtype="float32")
        score = float(asked @ (row / (np.linalg.norm(row) or 1.0)))
        if score >= NEAR_FLOOR:
            scored.append({"i": index, "score": round(score, 3)})
    scored.sort(key=lambda item: -item["score"])
    return scored[:NEAR_TOP]


def table() -> dict:
    """What `GET /read/words` serves."""
    return {"groups": [list(g) for g in GROUPS], "filler": sorted(FILLER)}
