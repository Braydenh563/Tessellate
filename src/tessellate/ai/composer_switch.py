""""Turn it on" for a tool that is off, with no model (OPEN row 29, INBOX 1351).

Several answers say a part of the app is off or not set up (web search, agent
mode, dictation). "Turn it on", "enable that" or "turn on dictation" then
answers with what the tool is for and a link to the one place its switch is.
Nothing is switched for the person and nothing is run: the link opens the
control and rings it (the web-search "start it" pattern, `composer_extra`).

The wording is the app's own; the "what it does" lines are the Tools and
features rows' own text (`find_it`), so there is no second list of them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tessellate.ai import composer_study


@dataclass(frozen=True)
class Tool:
    key: str
    name: str
    words: re.Pattern
    surface: str
    does: str
    where: str


def _t(key: str, name: str, words: str, surface: str, does: str, where: str) -> Tool:
    return Tool(key, name, re.compile(words, re.I), surface, does, where)


TOOLS: tuple[Tool, ...] = (
    _t("agent", "Agent mode", r"\bagent(?: mode)?\b|\bits tools\b", "reveal:chat-agent-mode",
       "lets Atlas use its tools: search your notes, open a page, create, tag, link and organise", "the Agent switch beside the chat box"),
    _t("dictation", "Dictation", r"\bdictat\w*|\bvoice notes? add-?on\b", "reveal:notes-dictation",
       "types what you say into the capture box", "Capture, with the Voice notes add-on installed"),
    _t("ocr", "OCR workspace", r"\bocr\b|text from (?:a |the )?(?:picture|image|scan)|scanned", "reveal:page-reader",
       "reads the text out of a picture or PDF, page by page", "Library, OCR workspace"),
    _t("memory", "Memory", r"\bmemory\b|what it remembers", "settings:memory",
       "keeps the facts you have told it so answers can use them", "Settings, Memory"),
    _t("skills", "Skills", r"\bskills?\b", "settings:skills",
       "gives the assistant extra ways of working, one switch each", "Settings, Skills"),
    _t("tools", "Tool permissions", r"\btool permissions?\b|\bpermissions?\b", "settings:tools",
       "chooses which tools the assistant may use and which ask first", "Settings, Tool permissions"),
    _t("models", "A chat model", r"\b(?:chat )?model\b|\bollama\b|\bllm\b", "settings:models",
       "adds a local model for open-ended chat; the notes answers need none", "Settings, Models"),
)

_ON = re.compile(
    r"^(?:ok(?:ay)?[, ]+|please[, ]+|can you |could you |how do i |how can i |how to |i want to |i'?d like to |let'?s )*"
    r"(?:turn|switch|flip|put|set|enable|activate)\s+(?P<a>(?:it|that|this|them)\s+(?:on|up)|on\s+(?:it|that|this)|on\s+(?P<t>.+?)|(?P<t2>.+?)\s+on|(?:it|that|this)|(?P<t3>.+?))"
    r"\s*(?:please|for me|now)?\W*$", re.I)
_OFFISH = re.compile(r"\b(?:off|disabled|not (?:on|set up|enabled|installed)|turn (?:it |this )?on|switch(?:ed)? on|opt-?in|enable)\b", re.I)
_BARE = re.compile(r"^(?:it|that|this|them)(?:\s+(?:on|up))?$|^on\s+(?:it|that|this)$", re.I)

PHRASES = {
    "lead": (
        "I can not switch {name} on for you, but it is one control away.",
        "{name} is off, and the switch is yours to flip: I do not change settings on my own.",
        "Turning on {name} is your call, so I will point you to it instead of doing it.",
    ),
    "does": (
        "It {does}.",
        "What it does: it {does}.",
        "With it on, it {does}.",
    ),
    "where": (
        "The switch is in {where}.",
        "You will find it in {where}.",
        "Look in {where}.",
    ),
}


def _named(text: str) -> Tool | None:
    hits = [(m.start(), t) for t in TOOLS if (m := t.words.search(text or ""))]
    return min(hits, key=lambda h: h[0])[1] if hits else None


def tool_for(ctx: composer_study.Ctx) -> Tool | None:
    """The tool a "turn it on" means: the one the question names, else the
    first the last answer says is off."""
    said = " ".join((ctx.asked or ctx.question or "").split())
    found = _ON.match(said)
    if not found:
        return None
    named = (found.group("t") or found.group("t2") or found.group("t3") or "").strip()
    if named and not _BARE.match(named):
        return _named(named)
    last = ctx.last_answer
    return _named(last) if last and _OFFISH.search(last) else None


def answer(ctx: composer_study.Ctx) -> composer_study.Reply | None:
    tool = tool_for(ctx)
    if tool is None:
        return None
    seed = ctx.seed
    pick = composer_study.pick
    text = " ".join((
        pick(seed, "sw-lead", PHRASES["lead"]).format(name=tool.name),
        pick(seed, "sw-does", PHRASES["does"]).format(does=tool.does),
        pick(seed, "sw-where", PHRASES["where"]).format(where=tool.where),
    ))
    label = f"Show me {tool.name}"
    return composer_study.Reply(f"{text}\n\n{label}", offer={"kind": "open", "surface": tool.surface, "label": label})
