"""Two social turns the chat words itself (INBOX 1485, the owner: "make the
understanding, social skills and stuff better"): a ping that may have been
a search ("test"), and a repair after a reply that missed ("not what I
asked"). Neither is ever searched for; the route counts and re-reads."""

from __future__ import annotations

import hashlib
import re

from tessellate.ai import intent, realise, repair_turn
from tessellate.search import query as query_understanding

#: After a ping's own line: was it a search, and how many notes would answer.
PING_ASK: dict[str, tuple[str, ...]] = {
    "natural": (
        "Did you mean to search? {count} {verb} “{subject}”.",
        "Were you after a search? {count} {verb} “{subject}”.",
        "Or was that a search? {count} {verb} “{subject}”.",
    ),
    "professional": (
        "Was a search intended? {count} {verb} “{subject}”.",
        "Did you intend a search? {count} {verb} “{subject}”.",
    ),
}

#: A miss owned, saying what the last message was read as.
REPAIR_LEAD: dict[str, tuple[str, ...]] = {
    "natural": ("Sorry, I read “{asked}” as {read_as}.", "Sorry, I took “{asked}” for {read_as}."),
    "professional": ("Sorry, “{asked}” was read as {read_as}.", "Sorry, “{asked}” was taken for {read_as}."),
}
REPAIR_BARE = {"natural": "Sorry, I misread “{asked}”.", "professional": "Sorry, “{asked}” was misread."}
REPAIR_ASK = {"natural": "What were you after?", "professional": "What did you want to find?"}
REPAIR_NOTHING = {"natural": "Sorry about that. What did you mean?", "professional": "Sorry about that. What did you want to find?"}

#: The word a ping is about when it says "test" ("testing 123" is "test").
_PING_WORD = re.compile(r"\btest", re.I)


def _voice(voice: str) -> str:
    return "professional" if voice == "professional" else "natural"


def _pick(lines: tuple[str, ...], key: str) -> str:
    return lines[int(hashlib.sha1(key.encode()).hexdigest(), 16) % len(lines)]


def with_act_ran(said: str, kind: str | None, last: dict) -> str:
    """A goodbye after a card the person confirmed names what ran (C2); a card only proposed is not named."""
    ran = str(last.get("done_act") or "").strip().rstrip(".")
    return f"{said} Just done: {ran}." if kind == "bye" and ran else said


def ping_subject(message: str) -> str:
    """"test" when a ping says it, else "" ("is this working" names nothing)."""
    return "test" if _PING_WORD.search(message or "") else ""


def ping(said: str, count: int, subject: str, voice: str = "natural", seed: str = "") -> str:
    """The ping's own first sentence (`said`, "Loud and clear."), then whether
    a search was meant and how many notes `subject` would find: "Loud and
    clear. Did you mean to search? Three notes mention “test”."""
    if not subject or count <= 0:
        return said
    head = re.match(r".+?[.?](?=\s|$)", said)
    noun = realise.count_noun(count, "note")
    ask = _pick(PING_ASK[_voice(voice)], f"ping|{seed}|{said}").format(
        count=noun[:1].upper() + noun[1:], verb="mentions" if count == 1 else "mention", subject=subject
    )
    return f"{head.group(0) if head else said} {ask}"


def ping_asks(subject: str) -> list[str]:
    """The chip a ping offers: the notes it counted."""
    return [f"Show my notes about {subject}"] if subject and query_understanding.is_chip_subject(subject) else []


def read_as(last: dict) -> str:
    """What the last reply took its message for, from the reply itself: notes
    named, a web search, or a short line with neither (small talk); "" when
    it cannot be told."""
    answer = str(last.get("answer") or "")
    low = answer.lower()
    if last.get("objects") or "#/notes/" in answer:
        return "a search of your notes"
    if "search the web" in low or "web search" in low or "search service" in low:
        return "a web search"
    #: A short reply is small talk only when the message before was (a notes
    #: answer of one line is not).
    return "small talk" if answer and len(answer) <= 160 and intent.classify(str(last.get("question") or "")) == intent.SMALLTALK else ""


def bare_no(message: str, last: dict) -> bool:
    """A bare "no" or "nope" after a reply that asked nothing says the reply
    missed (INBOX 1668 b); after a question it is that question's answer."""
    bare = " ".join(re.findall(r"[a-z]+", (message or "").lower())) in ("no", "nope", "nah", "no no", "nope nope")
    return bare and not str(last.get("answer") or "").rstrip().endswith("?")


def answers_offer(message: str, last: dict) -> bool:
    """"No, I don't want that" after a reply that ended in a question: the
    answer to it, not a complaint (INBOX 1668 b, review)."""
    return str(last.get("answer") or "").rstrip().endswith("?") and repair_turn.is_refusal(message)


def missed(message: str, kind: str | None, last: dict) -> bool:
    """Whether the message says the last reply missed: a correction, or a
    bare "no" after a reply that asked nothing; not a refusal of an offer."""
    return (kind == "repair" and not answers_offer(message, last)) or bare_no(message, last)


def heard(message: str, kind: str | None, last: dict) -> str:
    """The words the small-talk reply answers: a refusal of an offer is the
    offer's "no" ("no, I don't want that")."""
    return "no" if kind == "repair" and answers_offer(message, last) else message


def repaired_turn(history: list[dict], last: dict) -> dict:
    """The turn a correction is about: the last that was not itself a
    correction, so a second complaint repairs the ask, not the first complaint."""
    return next((t for t in reversed(history) if not repair_turn.is_repair(str(t.get("question") or ""))), last)


def repair(asked: str, last: dict, better: str, voice: str = "natural", seed: str = "") -> str:
    """The reply to "not what I asked": the miss owned in a sentence, what
    `asked` (the message before) was read as, then the better reading of it
    (`better`) or a question when there is none."""
    said = _voice(voice)
    if not asked.strip():
        return REPAIR_NOTHING[said]
    shown = realise.cut_title(asked, 60)
    taken = read_as(last)
    lead = _pick(REPAIR_LEAD[said], f"repair|{seed}|{asked}").format(asked=shown, read_as=taken) if taken else REPAIR_BARE[said].format(asked=shown)
    return f"{lead} {better or REPAIR_ASK[said]}"
