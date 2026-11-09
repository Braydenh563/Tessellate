"""What a composed answer never says (INBOX 1705, the owner's model-off screenshots).

Each rule is on one line of the answer, after it is worded: a quote of text that
is mostly symbols or emoji (it shows as tofu), a quote left unclosed or cut after
a word or two ("described as “A vibrant."), a raw arrow or an inline bold mark in a
sentence, reported speech that keeps its capital ("You said that What..."), and a
"More loosely related to X." heading with nothing after it.
"""

from __future__ import annotations

import re

_QUOTE = re.compile(r"“([^”]*)”")
#: "an arrow" a note uses as a mapping: said as a colon, never raw.
_ARROW = re.compile(r"\s*(?:->|=>|→|⇒)\s*")
#: Bold inside a sentence ("Back in September, **Joke:** Why did"): not a citation "[**Title**]", not a line's own heading.
_INLINE_BOLD = re.compile(r"(?<=[^\s\[*] )\*\*([^*\n]+?)\*\*(?!\])")
_REPORTED = re.compile(
    r"\b((?i:you (?:said|wrote|noted|mentioned|recorded|jotted down|put down) that |your note said that ))"
    r"(What|When|Where|Who|Why|How|Which|The|A|An|This|That|These|Those|Some|It|There|Your|My|Our)\b"
)
#: A cut quote: "described as “A vibrant.” and nothing more": one or two words that stop on a full stop.
_CUT_QUOTE = re.compile(r"(?:described|shown|reads?|says?) (?:as|:)? ?“[^”\s]+(?: [^”\s]+)?\.”?$")
_DANGLING = re.compile(r"^More (?:loosely related to|from) .+\.$")


def mostly_symbols(text: str) -> bool:
    """Whether most of `text` is not letters or digits: emoji, glyphs that show as tofu."""
    chars = [c for c in text if not c.isspace()]
    return bool(chars) and sum(c.isalnum() for c in chars) / len(chars) < 0.5


def _plain_line(line: str) -> str:
    if line.lstrip().startswith(("**", "- ", ">", "#")):
        body = line
    else:
        body = _INLINE_BOLD.sub(r"\1", line)
    body = _ARROW.sub(": ", body) if "->" in body or "=>" in body or "→" in body or "⇒" in body else body
    return _REPORTED.sub(lambda m: m.group(1) + m.group(2).lower(), body)


def line(text: str) -> str:
    """`text` cleaned line by line, or "" when a quote in it is unfit to show."""
    out = []
    for one in text.split("\n"):
        if any(mostly_symbols(q) for q in _QUOTE.findall(one)) or one.count("“") != one.count("”") or _CUT_QUOTE.search(one.strip()):
            return ""
        out.append(_plain_line(one))
    return "\n".join(out)


def paragraphs(parts: list[str]) -> list[str]:
    """`parts` without a "More loosely related to X." heading that nothing follows."""
    return [p for i, p in enumerate(parts) if not (_DANGLING.match(p.strip()) and (i + 1 == len(parts) or _DANGLING.match(parts[i + 1].strip())))]
