"""Print, as JSON, every place the Guide names that the live sweep must open.

Run by helpaudit.js (`.venv/bin/python scratchpad/ui-sweeps/helpaudit_claims.py`),
and fine to run alone to read the list. It shares the path parser with
tests/test_help_settings_paths.py so the lint and the sweep can never disagree
about what a "Settings, A, B" path is.

Output:
  paths:   [{"path", "section", "pane", "segments"}] one per distinct
           "Settings, ..." path in the Guide's topics and their meta
  phrases: [{"topic", "sections", "phrases"}] the capitalised control-like
           phrases of every topic that names a Settings pane, checked by the
           sweep against the text of each pane that topic names
  popovers: ids of every `data-help-for` target the static HTML declares
  slash:   the name of every chat "/" command in the registry (the menu has a row for each)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "tests")]

import test_help_settings_paths as lint  # noqa: E402
from tessellate.ai import help_chat  # noqa: E402

#: Words that start a sentence or name the product, never a control.
NOT_CONTROLS = {
    "atlas", "memorymap", "settings", "ollama", "lm studio", "windows", "macos", "linux", "notion", "obsidian",
    "evernote", "apple notes", "markdown", "json", "csv", "pypi", "github", "whisper", "tesseract", "harper",
    "the", "this", "that", "it", "a", "an", "if", "when", "with", "nothing", "nothing left this computer",
    "english", "british", "american", "agent", "chat", "notes", "library", "graph", "timeline", "reminders",
    "dashboard", "ctrl", "alt", "shift", "esc", "enter", "tab",
}
STOP = {
    "and", "or", "to", "of", "the", "a", "an", "in", "on", "is", "for", "from", "with", "then", "are", "it", "you",
    "your", "as", "at", "by", "when", "so", "if", "that", "which", "does", "can", "will", "lists", "shows", "has",
    "have", "this", "they", "them", "also", "again", "once", "until", "while", "turns", "sets", "makes", "gives",
    "keeps", "opens", "starts", "saves", "adds", "picks", "draws", "moves", "runs", "than", "but", "not", "no",
    "any", "all", "each", "every", "one", "two", "same", "other", "only", "just", "now", "here", "there", "what",
    "where", "who", "how", "why", "its", "be", "was", "were", "so", "chooses", "counts", "reads", "lists",
}
LEAD = re.compile(
    r"(?:\bpress(?:ing)?\s+|\bclick(?:ing)?\s+|\btap\s+|\bchoose\s+|\bpick\s+|\btick\s+|\bturn\s+(?:on|off)\s+|"
    r"\bthe\s+|\bhas\s+|\bwith\s+|\bunder\s+|\bshows\s+|\bpicks\s+|\bsets\s+|:\s+|,\s+|\(\s*)"
    r"([A-Z][\w'&/-]*(?:\s+[A-Za-z][\w'&/-]*){0,4})"
)


def _strings(obj):
    yield from lint._strings(obj)


def _phrases(text: str) -> set[str]:
    found: set[str] = set()
    for match in LEAD.finditer(text):
        words = match.group(1).split()
        keep = [words[0]]
        for word in words[1:]:
            if word.lower() in STOP:
                break
            keep.append(word)
        phrase = " ".join(keep).rstrip(".,:;)")
        low = phrase.lower()
        if len(low) < 4 or low in NOT_CONTROLS:
            continue
        found.add(phrase)
    return found


def main() -> None:
    paths = []
    for path in sorted(lint._paths()):
        section, segments = lint._resolve(path)
        if section is None:
            continue
        paths.append({"path": path, "section": section, "pane": next(k for k, v in lint.NAV.items() if v == section), "segments": segments})
    phrases = []
    for topic in help_chat.HELP_TOPICS:
        texts = list(_strings(topic)) + list(_strings(help_chat.TOPIC_META.get(topic["id"], {})))
        text = " ".join(texts).replace(" -> ", ", ")
        sections = set()
        for match in re.finditer(r"Settings, ([^.:;()\n]{1,60})", text):
            section, _ = lint._resolve(match.group(1))
            if section:
                sections.add(section)
        if not sections:
            continue
        body = " ".join(_strings(topic.get("body", "")))
        phrases.append({"topic": topic["id"], "sections": sorted(sections), "phrases": sorted(_phrases(body))})
    popovers = sorted(set(re.findall(r'data-help-for="([^"]+)"', lint.INDEX)))
    from tessellate.ai.slash_table import TABLE

    slash = [usage.split()[0].lstrip("/") for _, usage, _, _ in TABLE]
    print(json.dumps({"paths": paths, "phrases": phrases, "popovers": popovers, "slash": slash}, indent=1))


if __name__ == "__main__":
    main()
