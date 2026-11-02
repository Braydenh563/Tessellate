"""measure-1010 items 5, 6 and the settings help count, static scans of the
repo (formerly measure-keys.py, measure-undo.py, measure-settings-help.py).
    PYTHONPATH=src python scratchpad/ui-sweeps/measure-static.py keys|undo|settings_help
Run from the repo root."""
from pathlib import Path
import collections
import glob
import re
import sys


def keys():
    """measure-1010 item 5: key checks in frontend/js/*.js against DEFAULT_SHORTCUTS.
    python scratchpad/ui-sweeps/measure-keys.py
    A 'check' is a `.key ===|==|!==|!= "X"` comparison (e.key, event.key, ev.key, evt.key ...), counted per occurrence.
    Groups: 'convention' = Escape/Tab/Enter/Arrow*/Home/End/Page*/Backspace/Delete/Space (the keys the table says are
    deliberately not rebindable); 'in table' = a single-character key that is the last key of a DEFAULT_SHORTCUTS chord
    (so it may be the dispatcher itself); 'other' = any other literal (letters, digits, symbols used as local shortcuts)."""

    src = Path("frontend/js/settings-wiring.js").read_text(encoding="utf-8")
    body = src[src.index("const DEFAULT_SHORTCUTS"):]
    body = body[: body.index("\n};")]
    chords = re.findall(r'keys: "([^"]+)"', body)
    last = {c.split("+")[-1].lower() if not c.endswith("++") else "+" for c in chords}
    print("DEFAULT_SHORTCUTS entries:", len(chords), "last keys:", sorted(last))
    CONV = {"escape", "tab", "enter", "arrowup", "arrowdown", "arrowleft", "arrowright", "home", "end", "pageup", "pagedown", "backspace", "delete", " ", "space"}
    pat = re.compile(r'\b(?:e|ev|evt|event|ke|k)\.key\s*(?:===|==|!==|!=)\s*["\']([^"\']*)["\']')
    tot = collections.Counter()
    per = collections.defaultdict(collections.Counter)
    other_keys = collections.defaultdict(collections.Counter)
    for f in sorted(glob.glob("frontend/js/*.js")):
        for m in pat.finditer(Path(f).read_text(encoding="utf-8")):
            k = m.group(1)
            g = "convention" if k.lower() in CONV else ("in table" if k.lower() in last else "other")
            per[f.split("/")[-1]][g] += 1
            tot[g] += 1
            if g != "convention":
                other_keys[f.split("/")[-1]][k] += 1
    for f, c in sorted(per.items(), key=lambda kv: -sum(kv[1].values())):
        print(f"{f:34s} total {sum(c.values()):3d}  convention {c['convention']:3d}  in-table-key {c['in table']:3d}  other {c['other']:3d}")
    print("TOTAL", sum(tot.values()), dict(tot))
    # which other literals
    for f, c in other_keys.items():
        pass


def undo():
    """measure-1010 item 6: every function with 'undo' in its name in frontend/js/*.js, and whether its body calls pushUndo.
    python scratchpad/ui-sweeps/measure-undo.py"""

    rows = []
    for f in sorted(glob.glob("frontend/js/*.js")):
        lines = Path(f).read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(lines):
            m = re.match(r"\s*(?:async\s+)?function\s+(\w*[Uu]ndo\w*)\s*\(", line) or re.match(r"\s*(?:const|let)\s+(\w*[Uu]ndo\w*)\s*=\s*(?:async\s*)?(?:\(|function)", line)
            if not m:
                continue
            ind = len(line) - len(line.lstrip())
            j = i + 1
            while j < len(lines) and not (lines[j].startswith(" " * ind + "}") and len(lines[j]) - len(lines[j].lstrip()) == ind):
                j += 1
            body = "\n".join(lines[i:j + 1])
            rows.append((f.split("/")[-1], i + 1, m.group(1), j - i + 1, "pushUndo" in body))
    for r in rows:
        print("%-26s %5d %-34s %4d lines  calls pushUndo: %s" % r)
    print(len(rows), "functions;", sum(r[4] for r in rows), "call pushUndo")
    callers = {}
    for f in sorted(glob.glob("frontend/js/*.js")):
        n = len(re.findall(r"\bpushUndo\(", Path(f).read_text(encoding="utf-8")))
        if n:
            callers[f.split("/")[-1]] = n
    print("pushUndo( occurrences per file:", callers)


def settings_help():
    """measure-1010 item 4: PreferencesBody keys against Settings help.
    python scratchpad/ui-sweeps/measure-settings-help.py   (from the repo root, PYTHONPATH=src)
    
    For a key, find the control: an element id `$("id")` on a settings-*.js line within 3 lines of the key
    (or a `pref-`/`set-` id in index.html whose name matches the key). The control's block in index.html is the
    text between the previous <h3 and the next <h3 / </section>. 'popover' = a data-help-for in the block;
    'line' = a <p class="muted|hint|help..."> or <small> within 4 lines of the control; else 'none'.
    """
    from tessellate.api.routes_settings import PreferencesBody  # PYTHONPATH=src


    html = Path("frontend/index.html").read_text(encoding="utf-8").split("\n")
    js = {f: Path(f).read_text(encoding="utf-8").split("\n") for f in glob.glob("frontend/js/*.js")}
    keys = list(PreferencesBody.model_fields)
    print("PreferencesBody keys:", len(keys))
    total_help = sum("data-help-for" in line for line in html)
    print("data-help-for in index.html (all):", total_help)

    def ids_for(key):
        out = []
        for f, lines in js.items():
            if not re.search(r"settings|app\.js", f):
                continue
            for i, line in enumerate(lines):
                if re.search(rf"\b{key}\b", line):
                    for m in lines[max(0, i - 3): i + 4]:
                        out += re.findall(r'\$\("((?:pref|set)-[\w-]+)"\)', m)
        return list(dict.fromkeys(out))

    def line_of(idv):
        for i, line in enumerate(html):
            if f'id="{idv}"' in line:
                return i
        return None

    res = {"popover": [], "line": [], "none": [], "nocontrol": []}
    for k in keys:
        ids = ids_for(k)
        ln = [line_of(i) for i in ids if line_of(i) is not None]
        if not ln:
            res["nocontrol"].append(k)
            continue
        L = ln[0]
        a = L
        while a > 0 and "<h3" not in html[a] and "<section" not in html[a]:
            a -= 1
        b = L
        while b < len(html) - 1 and "<h3" not in html[b + 1] and "</section>" not in html[b + 1]:
            b += 1
        block = "\n".join(html[a: b + 1])
        near = "\n".join(html[max(0, L - 4): L + 5])
        if "data-help-for" in block:
            res["popover"].append(k)
        elif re.search(r'<p class="[^"]*(muted|hint|help)|<small|class="help', near):
            res["line"].append(k)
        else:
            res["none"].append(k)
    for t, v in res.items():
        print(t, len(v), v)


if __name__ == "__main__":
    {"keys": keys, "undo": undo, "settings_help": settings_help}[sys.argv[1]]()
