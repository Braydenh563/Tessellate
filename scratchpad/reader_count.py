"""Count the files that read date words or units (CHAT_PLAN "The deterministic
foundation", phase F0, Brief 64).

A reader turns words into a value: a regex pattern (Python string constant or
JS regex literal / new RegExp) that carries a date word or a quantity unit.
A mention is the same word in copy, a help topic or a prompt. The reader count
is the starting ratchet for tests/test_one_reader.py.

    python scratchpad/reader_count.py [--lines] [--mentions] [--json]

Kinds of reader, strongest first:
  pattern  a regex string/literal with a date word or a unit beside a number
  table    a dict/set/list literal of three or more weekday or unit names
  keyword  a membership test or includes() against one date word

The ratchet number is the `pattern` plus `keyword` count outside
ai/recognise.py and entry/timewords.py (the two files allowed to read): a file
that tests a date word and turns it into a window reads, whether or not it
compiles a regex. `table` files are reported beside it, not in it: a table of
weekday or unit words is a stop list or a spelling map unless it carries values.
"""


import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {"src/tessellate/ai/recognise.py", "src/tessellate/entry/timewords.py"}

# Hand verdicts, 2026-10-10 (Brief 64), for the files the scan finds. A new file
# in the scan with no verdict prints "unjudged": judge it, then add it here.
VERDICT = {
    "src/tessellate/ai/note_recency.py": "not a reader: `_TIME_AFTER` is a mask so 'last week' is not taken as 'the last N notes'; it turns no word into a value, recognise reads the window",
    "src/tessellate/ai/act_registry.py": "not a reader: `_WHEN` is a lookahead mask telling 'due' as a time from 'due diligence'; it turns no word into a value, recognise reads the window",
    "src/tessellate/ai/when.py": "reader: words to a date or window (resolve, parse_reminder_text, _AGO)",
    "src/tessellate/ai/reminder_parser.py": "reader: parse_relative, 'in 30 mins' to a datetime",
    "src/tessellate/search/query.py": "reader: today, yesterday, this/last week|month|year, 'N units back' to a date range",
    "src/tessellate/ai/notebook_stats.py": "not a reader since Brief 65: weekday names for the busiest-day answer (windows read by recognise)",
    "src/tessellate/api/routes_vision.py": "reader (keyword): _period, 'this week' in text to a date range",
    "src/tessellate/ai/composer.py": "not a reader since ledger row 453: its cue and window patterns are recognise.looks_dated and without_windows",
    "src/tessellate/ai/question_noise.py": "not a reader: hr, hrs, mins in the slang map",
    "src/tessellate/ai/source_check.py": "not a reader: weekday and month names in a stop list of non-names",
    # Brief 65 (F1), 2026-10-10: the readers above delegate to ai/recognise.py.
    "src/tessellate/ai/realise.py": "not a reader: weekday names for writing a date",
    "src/tessellate/ai/utilities.py": "not a reader: weekday names for writing a date (units and date questions read by recognise)",
    "src/tessellate/ai/factgraph.py": "not a reader: time-unit names a count is not (dates, money, durations read by recognise)",
    # Brief 67 (F3), 2026-10-10.
    # 2026-10-12 (the week-start setting): the three first days a week can start on.
    "src/tessellate/api/routes_settings.py": "not a reader: the week_start choices (monday, saturday, sunday) of a setting",
    "src/tessellate/core/config.py": "not a reader: _WEEK_CHOICES, the week_start setting's first-day names to weekday numbers",
    # 2026-10-18 (C06): the answer panel's calculator.
    "frontend/js/reply-kit.js": "not a reader: REPLY_CALC_PAIRS, the unit pair each converter kind opens on; the sum is read by the server",
    "src/tessellate/ai/composer_digest.py": "not a reader: weekday names for writing a date (the digest's day-of-week phrasing); windows and units read by recognise",
    # 2026-10-26 (grammar K4b): a mask, not a reader. The browser cannot call
    # the recogniser, and nothing here becomes a date, window or quantity.
    "frontend/js/documents.js": "not a reader: the spellcheck's unit mask, which skips the unit straight after a number (10 min, 5 km) so it is not marked as a misspelling",
    # 2026-10-30 (audit 1029 C21): the slot answerer's day and unit names.
    "src/tessellate/ai/composer_slots.py": "not a reader: _WEEKDAYS matches a question's day to a note's written weekday and _UNITS lists a unit's spellings so the note's figure is quoted as written; days are found and judged by recognise (find, names_a_day)",
    "src/tessellate/ai/commands.py": "not a reader: _TIME_FIRST, the words that open a reminder's time part (weekday words included), to split it from the task; the date is read by when, which delegates to recognise",
}

WEEKDAYS = "monday|tuesday|wednesday|thursday|friday|saturday|sunday"
DATE_RE = re.compile(
    r"(?<![a-z])(tomorrow|yesterday|tonight|day after tomorrow|"
    r"(?:next|last|this)\s*(?:week|month|year|" + WEEKDAYS + r")|"
    r"(?:week|month|year)s?\s+ago|days?\s+ago|\bago\b|in\s+\d+\s+days?|"
    + WEEKDAYS + r")(?![a-z])",
    re.I,
)
UNIT_WORDS = (
    r"km|kms|kilomet(?:er|re)s?|miles?|kg|kgs|kilograms?|lbs?|pounds?|"
    r"celsius|fahrenheit|minutes?|mins?|hours?|hrs?"
)
# Case-sensitive: HTML tag names (HR) and constants are not units.
UNIT_RE = re.compile(r"(?<![A-Za-z])(" + UNIT_WORDS + r")(?![A-Za-z])")
NUMBER_MARK = re.compile(r"\\d|\[0-9|\\s\*?[a-z]|\d")  # a digit or a digit class
REGEX_MARK = re.compile(r"\\[bdsw]|\(\?|\||\[[a-z0-9-]+\]|\^|\$")
TABLE_WORD = re.compile(r"^(" + WEEKDAYS + "|" + UNIT_WORDS + r")$", re.I)


def _norm(pattern: str) -> str:
    return pattern.replace("\\b", " ").replace("\\s", " ")


def classify_pattern(pat: str) -> str | None:
    """'date', 'unit' or None for a regex-looking string."""
    if "\n" in pat or "${" in pat or not REGEX_MARK.search(pat):
        return None
    flat = _norm(pat)
    if DATE_RE.search(flat):
        return "date"
    if UNIT_RE.search(flat) and NUMBER_MARK.search(pat):
        return "unit"
    return None


def py_scan(path: Path):
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [], [], [], []
    doc_ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                doc_ids.add(id(body[0].value))
    patterns, tables, keywords, mentions = [], [], [], []
    uses_re = bool(re.search(r"^\s*(import re\b|from re import)", src, re.M))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in doc_ids:
            s = node.value
            kind = classify_pattern(s) if uses_re else None
            if kind:
                patterns.append((node.lineno, kind, s.strip()[:70]))
            elif DATE_RE.search(s) or (UNIT_RE.search(s) and re.search(r"\d", s)):
                mentions.append((node.lineno, "mention", s.strip()[:70]))
        elif isinstance(node, (ast.Dict, ast.Set, ast.List, ast.Tuple)):
            elts = node.keys if isinstance(node, ast.Dict) else node.elts
            words = [e.value for e in elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            hits = [w for w in words if TABLE_WORD.match(w.strip())]
            if len(hits) >= 3 and len(set(h.lower() for h in hits)) >= 3:
                tables.append((node.lineno, "table", ",".join(hits[:4])))
        elif isinstance(node, ast.Compare) and any(isinstance(o, ast.In) for o in node.ops):
            left = node.left
            if isinstance(left, ast.Constant) and isinstance(left.value, str) and DATE_RE.fullmatch(left.value.strip()):
                keywords.append((node.lineno, "keyword", left.value))
    return patterns, tables, keywords, mentions


def _strip_js(src: str) -> str:
    # Blank comments, keep line structure. Strings are left: a regex literal
    # never starts inside one in this code base's style.
    src = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group()), src, flags=re.S)
    out = []
    for line in src.split("\n"):
        m = re.search(r"(?<![:\"'`\\])//(?!.*[\"'`]\s*\)?;?\s*$)", line)
        out.append(line[: m.start()] if m and "://" not in line else line)
    return "\n".join(out)


JS_REGEX = re.compile(r"(?<![\w)\]\"'`/<])/((?:\\.|\[(?:\\.|[^\]\n\\])*\]|[^/\n\\\[])+)/[dgimsuyv]*")
JS_NEW = re.compile(r"new RegExp\(\s*([\"'`])((?:\\.|(?!\1)[^\\\n])*)\1")
JS_STRING = re.compile(r"\"([^\"\n]*)\"|'([^'\n]*)'|`([^`\n]*)`")
JS_INCLUDES = re.compile(r"""\.(?:includes|indexOf)\(\s*["']([a-z ]+)["']""", re.I)


def js_scan(path: Path):
    src = _strip_js(path.read_text(encoding="utf-8"))
    patterns, tables, keywords, mentions = [], [], [], []
    for i, line in enumerate(src.split("\n"), 1):
        found = [m.group(1) for m in JS_REGEX.finditer(line)] + [m.group(2) for m in JS_NEW.finditer(line)]
        hit = False
        for pat in found:
            kind = classify_pattern(pat)
            if kind:
                patterns.append((i, kind, pat[:70]))
                hit = True
        if not hit:
            for m in JS_INCLUDES.finditer(line):
                if DATE_RE.fullmatch(m.group(1).strip()):
                    keywords.append((i, "keyword", m.group(1)))
                    hit = True
            if not hit:
                for lit in JS_STRING.finditer(line):
                    body = lit.group(1) or lit.group(2) or lit.group(3) or ""
                    if DATE_RE.search(body) or (UNIT_RE.search(body) and re.search(r"\d", body)):
                        mentions.append((i, "mention", line.strip()[:70]))
                        break
        words = re.findall(r"""["'](%s)["']""" % (WEEKDAYS + "|" + UNIT_WORDS), line, re.I)
        if len({w.lower() for w in words}) >= 3:
            tables.append((i, "table", ",".join(words[:4])))
    return patterns, tables, keywords, mentions


def collect():
    files = []
    for p in sorted((ROOT / "src/tessellate").rglob("*.py")):
        rel = p.relative_to(ROOT).as_posix()
        if "/vendor/" in rel or "__pycache__" in rel:
            continue
        files.append((rel, p, py_scan))
    for p in sorted((ROOT / "frontend/js").glob("*.js")):
        files.append((p.relative_to(ROOT).as_posix(), p, js_scan))
    result = {}
    for rel, p, fn in files:
        pat, tab, key, men = fn(p)
        if pat or tab or key or men:
            result[rel] = {"pattern": pat, "table": tab, "keyword": key, "mention": men}
    return result


def main(argv):
    res = collect()
    show_lines = "--lines" in argv
    groups = {"pattern": [], "table": [], "keyword": []}
    mention_only = []
    for rel, r in res.items():
        if rel in ALLOWED:
            continue
        for kind in ("pattern", "table", "keyword"):
            if r[kind]:
                groups[kind].append(rel)
                break
        else:
            mention_only.append(rel)
    ratchet = groups["pattern"] + [
        r for r in groups["keyword"] if VERDICT.get(r, "").startswith("reader")
    ]
    out = {
        "ratchet": len(ratchet),
        "ratchet_files": ratchet,
        "ratchet_pattern_files": len(groups["pattern"]),
        "pattern_files": groups["pattern"],
        "table_only_files": groups["table"],
        "keyword_only_files": groups["keyword"],
        "mention_only_files": mention_only,
        "allowed_present": sorted(a for a in ALLOWED if a in res),
    }
    if "--json" in argv:
        print(json.dumps(out, indent=1))
        return
    print(f"RATCHET (pattern + keyword readers, outside the two allowed files): {len(ratchet)}")
    print(f"READER (pattern) files outside recognise.py and timewords.py: {len(groups['pattern'])}")
    for rel in groups["pattern"]:
        print(f"  {rel}")
        for ln, kind, s in res[rel]["pattern"] if show_lines else []:
            print(f"    {ln:5d} {kind:5s} {s}")
    for label, key in (("TABLE-only readers", "table"), ("KEYWORD-only readers", "keyword")):
        print(f"{label}: {len(groups[key])}")
        for rel in groups[key]:
            print(f"  {rel}")
            for ln, kind, s in res[rel][key] if show_lines else []:
                print(f"    {ln:5d} {kind:7s} {s}")
    print("Verdicts:")
    for rel in groups["pattern"] + groups["table"] + groups["keyword"]:
        print(f"  {rel}: {VERDICT.get(rel, 'unjudged')}")
    print(f"MENTION-only files (copy, help, prompts): {len(mention_only)}")
    if "--mentions" in argv:
        for rel in mention_only:
            n = len(res[rel]["mention"])
            print(f"  {rel} ({n}), first line {res[rel]['mention'][0][0]}")
    print("ALLOWED (not counted):", ", ".join(out["allowed_present"]) or "none")


if __name__ == "__main__":
    main(sys.argv[1:])
