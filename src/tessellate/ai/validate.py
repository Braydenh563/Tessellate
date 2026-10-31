"""The validators (CHAT_PLAN "The deterministic foundation", decisions 52 to
54): one set of checks over every answer, the engine's and the model's alike.
The model proposes, the engine decides; a check here only ever reads strings
and parts, so it cannot itself make anything up.

- `source_check`: every number and name in an answer is in what it drew on
  (`ai/source_check.py`, the agent's H2 check, read here for chat too).
- `grounding_marks`: how much of the answer the notebook backs
  (`grounding.support`), with the sentences it does not.
- `maxims`: Grice's maxims as lints over a composed answer's parts
  (decision 52), each finding named by its maxim:
  quantity  a quote or a measured value said twice in one answer;
  quality   a number in the app's own joining words (only quotes, measured
            values, the asked words and computed sentences carry numbers);
  relation  a quoted sentence whose note is not in the grounding rows;
  manner    a capital after a joining comma, a title cut through a word,
            an exclamation mark or "Oops", a doubled space or stop, a
            sentence of the app's own words over forty words.
- `computed_rule`: a computed sentence only in a utility answer, never mixed
  into a claim about the notes, and always saying how the question was read
  ("Read as", or for a sum the expression it worked out; decision 54).
- `slots_missing`: the slots an act needs that a reading did not fill, so
  the act asks one question rather than guessing (decisions 48 and 50).

`report(result, question, notes)` runs all of them on a composed answer;
`check_model_answer(answer, sources, grounding)` on a model's.
`tests/test_validate.py` holds the measures: the maxims lint is 0 over the
showcase and voice evals.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from tessellate.ai import grounding as _grounding, realise, source_check as _source_check

#: Words that are numbers when said in a sentence.
_NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
    "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "twenty": "20", "thirty": "30", "hundred": "100",
}
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?|\b(?:" + "|".join(_NUMBER_WORDS) + r")\b", re.I)
#: A joining phrase that ends in a comma, and the case of what follows it.
_COMMA_END = re.compile(r",\s*$")
_SHOUT = re.compile(r"(?<!\[)!|\boops\b", re.I)
_DOUBLED = re.compile(r"(?<!\n)  +(?!\n)|\.\.(?!\.)|\s[,.;:](?!\d)")
_SENTENCE = re.compile(r"(?<=[.?!:])\s+|\n+")
#: The longest sentence of the app's own words a reader takes in at once.
MAX_APP_WORDS = 40
#: Parts that are the app's own words (decision 52's lint reads them).
APP_KINDS = frozenset({"template"})
#: Parts that may carry a number: a fact, the person's question, or a sum.
NUMBERED_KINDS = frozenset({"address", "confirmed", "quote", "title", "filed", "picture", "measure", "asked", "computed", "help", "web", "reminder", "term"})


@dataclass(frozen=True)
class Finding:
    maxim: str
    rule: str
    text: str

    def as_dict(self) -> dict:
        return {"maxim": self.maxim, "rule": self.rule, "text": self.text}


# --- source check and grounding --------------------------------------------------


def source_check(answer: str, sources: list[str], question: str = "") -> list[str]:
    """The numbers and names in `answer` that none of `sources` contains. A
    `question` about a date, a time or a reminder lets the answer's own
    computed figures through (`source_check.Sources`)."""
    return _source_check.unbacked_claims(answer or "", _source_check.Sources([s for s in sources if s], question))


def grounding_marks(answer: str, rows: list[dict]) -> dict:
    """The support counts for `answer` given its grounding rows."""
    return _grounding.support(answer or "", rows or [])


# --- the maxims (decision 52) -------------------------------------------------------


#: A measured day ("5 September", "5 September 2025"): one value, the date,
#: so a count of five beside it is not the same fact said twice (INBOX 787),
#: and the same day said twice still is.
_DAY = re.compile(r"^\d{1,2} (?:January|February|March|April|May|June|July|August|September|October|November|December)(?: \d{4})?$")


def _values(text: str) -> list[str]:
    if _DAY.match((text or "").strip()):
        return [text.strip()]
    out = []
    for match in _NUMBER.finditer(text or ""):
        said = match.group(0).lower().replace(",", "")
        out.append(_NUMBER_WORDS.get(said, said))
    return out


def _measures_by_sentence(parts: list) -> list[tuple[int, str]]:
    """(sentence index, value) for each number in a measured part. A date in
    a citation ("[your note, 24 September]") is the note's name, not a
    statement, so it is not counted."""
    out, index, cite = [], 0, 0
    for part in parts:
        text = str(part[1])
        if part[0] == "measure" and not cite:
            out.extend((index, v) for v in _values(text))
        if part[0] == "template":
            cite += text.count("[") - text.count("]")
        index += len(_SENTENCE.findall(text))
    return out


def _quantity_findings(parts: list) -> list[Finding]:
    """One fact once: a quote said twice, a measured value said in two sentences."""
    quotes = [str(p[1]).strip().rstrip(".").lower() for p in parts if p[0] == "quote"]
    found = [Finding("quantity", "quote said twice", q[:80]) for q in {q for q in quotes if quotes.count(q) > 1}]
    seen: dict[str, int] = {}
    for sentence, value in _measures_by_sentence(parts):
        if value in seen and seen[value] != sentence and value not in ("1",):
            found.append(Finding("quantity", "measured value said twice", value))
        seen.setdefault(value, sentence)
    return found


def _joining_comma_findings(parts: list) -> list[Finding]:
    found: list[Finding] = []
    for before, after in zip(parts, parts[1:]):
        if before[0] == "template" and _COMMA_END.search(str(before[1])) and after[0] in ("quote", "template"):
            text = str(after[1])
            #: "The Mom Test" after a comma is a title, kept as written: a
            #: capitalised word after the common first one says so.
            second = text.split()[1:2]
            if second and second[0][:1].isupper():
                continue
            if text and realise.after_comma(text) != text:
                found.append(Finding("manner", "capital after a joining comma", text[:60]))
    return found


def _cut_title_findings(parts: list, notes: list[dict] | None) -> list[Finding]:
    titles = {int(n["id"]): _title_of(n) for n in (notes or []) if n.get("id") is not None}
    found: list[Finding] = []
    for part in parts:
        if part[0] == "title" and len(part) > 2 and str(part[1]).endswith("…"):
            whole = titles.get(part[2], "")
            kept = str(part[1])[:-1]
            if whole and whole.startswith(kept) and whole[len(kept):len(kept) + 1].isalnum():
                found.append(Finding("manner", "title cut through a word", str(part[1])))
    return found


def _wording_findings(result: dict, parts: list) -> list[Finding]:
    """How the words read: exclamation, doubled space, a sentence over forty words."""
    found: list[Finding] = []
    text = str(result.get("text") or "")
    app_text = "".join(str(p[1]) for p in parts if p[0] in APP_KINDS)
    if _SHOUT.search(app_text):
        found.append(Finding("manner", "exclamation or Oops", app_text[:60]))
    found.extend(Finding("manner", "doubled space or stop", text[max(0, m.start() - 20):m.end() + 20])
                 for m in _DOUBLED.finditer(text))
    found.extend(Finding("manner", "app sentence over forty words", sentence[:80])
                 for sentence in _app_sentences(parts) if len(sentence.split()) > MAX_APP_WORDS)
    return found


def maxims(result: dict, question: str = "", notes: list[dict] | None = None) -> list[Finding]:
    """Decision 52's lint over one composed answer."""
    parts = result.get("parts") or []
    # quantity: one fact once.
    found = _quantity_findings(parts)
    # quality: numbers only where a fact or the question put them.
    found.extend(Finding("quality", "number in the app's own words", str(part[1])[:80])
                 for part in parts if part[0] in APP_KINDS and _values(str(part[1])))
    # relation: every quote is a grounded sentence of a note the answer cites.
    cited = {row.get("note_id") for row in result.get("grounding") or []}
    found.extend(Finding("relation", "quote with no grounding row", str(part[1])[:80])
                 for part in parts if part[0] == "quote" and len(part) > 2 and part[2] is not None and part[2] not in cited)
    # manner: how the words read.
    found.extend(_joining_comma_findings(parts))
    found.extend(_cut_title_findings(parts, notes))
    found.extend(_wording_findings(result, parts))
    return found


def _title_of(note: dict) -> str:
    first = str(note.get("content") or "").lstrip().split("\n", 1)[0]
    return " ".join(first.lstrip("#").split()) if first.lstrip().startswith("#") else str(note.get("title") or "")


def _app_sentences(parts: list) -> list[str]:
    """Sentences made only of the app's words and measured values."""
    out, current, own = [], [], True
    for part in parts:
        for piece in re.split(r"((?<=[.?!])\s+|\n+)", str(part[1])):
            if not piece:
                continue
            if not piece.strip():
                if current and own:
                    out.append("".join(current).strip())
                current, own = [], True
                continue
            current.append(piece)
            own = own and part[0] in ("template", "measure", "asked")
    if current and own:
        out.append("".join(current).strip())
    return [s for s in out if s]


# --- the computed sentence (decision 54) ------------------------------------------


def computed_rule(result: dict, question: str = "") -> list[Finding]:
    parts = result.get("parts") or []
    computed = [str(p[1]) for p in parts if p[0] == "computed"]
    if not computed:
        return []
    if result.get("shape") != "utility":
        return [Finding("quality", "computed sentence in a claim about the notes", computed[0][:60])]
    if any(p[0] in ("quote", "title", "filed", "picture") for p in parts):
        return [Finding("quality", "computed sentence mixed with the notes", computed[0][:60])]
    said = "".join(computed)
    if "Read as" in said:
        return []
    from tessellate.ai import arithmetic

    expr = arithmetic.sum_in(question or "") or ""
    if expr and said.startswith(expr.strip()):
        return []
    return [Finding("manner", "computed sentence with no Read as", said[:60])]


# --- slots (decisions 48 and 50) -----------------------------------------------------


def slots_missing(reading: dict, needed: tuple[str, ...]) -> list[str]:
    """The slots of `needed` that `reading` leaves empty, in order."""
    return [slot for slot in needed if reading.get(slot) in (None, "", [], ())]


# --- the reports ---------------------------------------------------------------------


def report(result: dict, question: str = "", notes: list[dict] | None = None) -> dict:
    """Every check on a composed answer: {"maxims", "computed", "support", "ok"}."""
    found = maxims(result, question, notes) + computed_rule(result, question)
    return {
        "findings": [f.as_dict() for f in found],
        "support": result.get("support") or grounding_marks(result.get("text", ""), result.get("grounding") or []),
        "ok": not found,
    }


def check_model_answer(answer: str, sources: list[str], rows: list[dict] | None = None, question: str = "") -> dict:
    """The same checks on a model's answer, which has no parts: its numbers and
    names against what it drew on, its grounding, and the manner rules that
    read text alone. {"unbacked", "support", "findings", "ok"}."""
    unbacked = source_check(answer, sources, question)
    findings = [Finding("quality", "not in the sources", claim) for claim in unbacked]
    if _SHOUT.search(answer or ""):
        findings.append(Finding("manner", "exclamation or Oops", (answer or "")[:60]))
    return {
        "unbacked": unbacked,
        "support": grounding_marks(answer, rows or []),
        "findings": [f.as_dict() for f in findings],
        "ok": not findings,
    }
