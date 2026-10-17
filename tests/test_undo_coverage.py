"""Rule 1.8 coverage: every call that writes user data offers Undo (INBOX 898).

`test_undo_contract.py` only holds functions *named* undo to the contract, so
a delete, rename, move or tag change that never calls `pushUndo` passed. This
reads every `api(`/`apiJson(`/`fetch(` call in `frontend/js/*.js` whose
options carry a method other than GET, finds the function it sits in (and the
functions around it, up to the first named one) and asks whether that code
reaches the contract: `pushUndo`/`offerUndo`, a helper whose name says undo and
calls them (`offerCategoryUndo`, `chatTitleUndo`, `pushEntryPutUndo`...), or
a surface's own history (`wbPushUndo`, `docUndo`). A call also counts when it
is an argument of such a call (the inverse closure handed to `pushUndo`), when
its function is one of the inverse closures (`undo`, `redo`, `back`...) of a
covered owner, or when every caller of a small helper is covered.

`EXEMPT` is the ratchet: `"file:function": "reason"`. It may only shrink. A
reason starts with a class: `auth`, `read`, `send`, `settings` (has its own
Reset or history), `telemetry`, `job` (starts or stops work, deletes nothing),
`inverse` (is the undo or redo of an act that offers one), `board` (the
board's own history, reached by Ctrl+Z on an open board), `purge` (permanent
by design, behind a confirm that says so). There is no class for a write
that has no undo yet: INBOX 898 closed the last of them, so a new write
offers one or explains here why undo is meaningless. The test also fails on
a line that is no longer needed.

Set `UNDO_COVERAGE_DUMP=1` to print what is uncovered.
"""

from __future__ import annotations

import bisect
import collections
import os
import re
from functools import lru_cache
from pathlib import Path

JS = Path(__file__).resolve().parents[1] / "frontend" / "js"

#: What the contract is, and the surface histories that stand in for it.
SEEDS = {
    "pushUndo", "offerUndo", "settleUndoFromToast", "performUndo",
    "docUndo", "wbUndo", "wbPushUndo", "wbPushDragUndo", "wbPushMoveBatch", "wbPushCall",
    #: Records the board rows before and after its callback and pushes the diff (whiteboard.js).
    "wbRecordGesture",
    #: Chat loads its helpers (chat-undo.js) on the first write and names one.
    "chatWriteRecord",
    #: Takes an act and its inverse and puts the step on the stack (skills.js).
    "batchEach",
}
#: Whole acts that do their write and put the step on the stack themselves, so
#: a caller that hands them the work is covered.
WRAPPERS = {"toastEntityMerge", "graphRemoveLink", "wbBoardMadeStep", "graphPinStep", "wbBoardPutStep", "wbLibPairStep"}
#: Closures that are the inverse of an act, named for it. They take the
#: coverage of the function that owns them.
INVERSE_NAMES = {
    "undo", "redo", "back", "again", "remake", "restoreIt", "binIt", "rebin",
    "restoreThem", "binThem", "drop", "restoreAll", "binAll", "restore",
}
NOT_FUNCTION = {
    "if", "for", "while", "switch", "catch", "with", "return", "typeof", "else",
    "do", "try", "finally", "in", "of", "new", "await", "void", "delete",
    "throw", "case", "yield",
}
CALL = re.compile(r"\b(?:api\.upload|api\.stream|apiJson|api|fetch)\(")
CALLID = re.compile(r"\b([A-Za-z_$][\w$]*)\(")
METHOD = re.compile(r"\bmethod\s*:\s*([^,}\n]+)")


def mask(src: str) -> str:
    """`src` with comments, strings, template text and regex bodies blanked.

    Same length, newlines kept, so offsets and line numbers still line up.
    Code inside a template's `${...}` stays visible.
    """
    n = len(src)
    out = list(src)

    def blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    def code(i: int, until_brace: bool) -> int:
        depth = 0
        prev = ""
        while i < n:
            c = src[i]
            nx = src[i + 1] if i + 1 < n else ""
            if c == "/" and nx == "/":
                j = src.find("\n", i)
                j = n if j < 0 else j
                blank(i, j)
                i = j
                continue
            if c == "/" and nx == "*":
                j = src.find("*/", i + 2)
                j = n if j < 0 else j + 2
                blank(i, j)
                i = j
                continue
            if c in "\"'":
                j = i + 1
                while j < n and src[j] != c and src[j] != "\n":
                    j += 2 if src[j] == "\\" else 1
                blank(i + 1, j)
                i = j + 1
                prev = c
                continue
            if c == "`":
                i = template(i + 1)
                prev = "`"
                continue
            if c == "/" and (prev == "" or prev in "(,=:[!&|?{};+-*%<>~^"):
                j = i + 1
                in_class = False
                while j < n and src[j] != "\n":
                    if src[j] == "\\":
                        j += 2
                        continue
                    if src[j] == "[":
                        in_class = True
                    elif src[j] == "]":
                        in_class = False
                    elif src[j] == "/" and not in_class:
                        break
                    j += 1
                if j < n and src[j] == "/":
                    blank(i + 1, j)
                    i = j + 1
                    prev = "/"
                    continue
            if c == "{":
                depth += 1
            elif c == "}":
                if until_brace and depth == 0:
                    return i + 1
                depth -= 1
            if not c.isspace():
                prev = c
            i += 1
        return i

    def template(i: int) -> int:
        start = i
        while i < n:
            c = src[i]
            if c == "\\":
                blank(i, i + 2)
                i += 2
                continue
            if c == "`":
                blank(start, i)
                return i + 1
            if c == "$" and i + 1 < n and src[i + 1] == "{":
                blank(start, i)
                i = code(i + 2, True)
                start = i
                continue
            i += 1
        return i

    code(0, False)
    return "".join(out)


def _open_of(m: str, close: int) -> int:
    depth = 0
    for i in range(close, -1, -1):
        if m[i] == ")":
            depth += 1
        elif m[i] == "(":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _word_before(m: str, k: int) -> tuple[str, int]:
    while k >= 0 and m[k].isspace():
        k -= 1
    e = k + 1
    while k >= 0 and (m[k].isalnum() or m[k] in "_$"):
        k -= 1
    return m[k + 1:e], k


def functions(m: str) -> list[tuple[int, int, str | None]]:
    """(open brace, close brace, name or None) of every braced function body."""
    stack: list[int] = []
    found = []
    for i, c in enumerate(m):
        if c == "{":
            stack.append(i)
            continue
        if c != "}" or not stack:
            continue
        b = stack.pop()
        j = b - 1
        while j >= 0 and m[j].isspace():
            j -= 1
        name = None
        is_fn = False
        if j >= 1 and m[j - 1:j + 1] == "=>":
            is_fn = True
            k = j - 2
            while k >= 0 and m[k].isspace():
                k -= 1
            if k >= 0 and m[k] == ")":
                k = _open_of(m, k) - 1
            else:
                _, k = _word_before(m, k)
            while k >= 0 and m[k].isspace():
                k -= 1
            if k >= 4 and m[k - 4:k + 1] == "async":
                k -= 5
            while k >= 0 and m[k].isspace():
                k -= 1
            if k >= 0 and m[k] in "=:":
                name, _ = _word_before(m, k - 1)
        elif j >= 0 and m[j] == ")":
            ident, _ = _word_before(m, _open_of(m, j) - 1)
            if ident == "function":
                is_fn = True
            elif ident and ident not in NOT_FUNCTION and not ident[0].isdigit():
                is_fn = True
                name = ident
        if is_fn:
            found.append((b, i, name or None))
    found.sort(key=lambda f: (f[0], -f[1]))
    return found


def _direct_ids(m: str, f, funcs) -> set[str]:
    """Names called in `f` outside the functions nested inside it."""
    b, e, _ = f
    inner = sorted(g for g in funcs if g is not f and b < g[0] and g[1] < e)
    ids: set[str] = set()
    pos = b
    for g in inner:
        if g[0] >= pos:
            ids.update(CALLID.findall(m[pos:g[0]]))
            pos = g[1]
    ids.update(CALLID.findall(m[pos:e]))
    return ids


def _statement_end(m: str, start: int) -> int:
    """Where the statement that holds `start` ends: a `;` at its own depth."""
    depth = 0
    for i in range(start, len(m)):
        c = m[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if depth < 0:
                return i
        elif c == ";" and depth == 0:
            return i
    return len(m)


def _call_end(m: str, start: int) -> int:
    depth, i = 1, start
    while i < len(m) and depth:
        if m[i] == "(":
            depth += 1
        elif m[i] == ")":
            depth -= 1
        i += 1
    return i


def _parents(funcs) -> list[int]:
    """Index of each function's enclosing function (-1 at the top)."""
    parent, stack = [], []
    for idx, f in enumerate(funcs):
        while stack and funcs[stack[-1]][1] < f[0]:
            stack.pop()
        parent.append(stack[-1] if stack else -1)
        stack.append(idx)
    return parent


@lru_cache(maxsize=1)
def analyse():
    """(sites, helpers). A site is (file, function, line, method, covered)."""
    files = {}
    for path in sorted(JS.glob("*.js")):
        src = path.read_text(encoding="utf-8")
        m = mask(src)
        funcs = functions(m)
        files[path.name] = (src, m, funcs, _parents(funcs), [f[0] for f in funcs])
    direct = {}
    by_name: dict[str, set[str]] = collections.defaultdict(set)
    for fn, (src, m, funcs, _, _) in files.items():
        for f in funcs:
            ids = _direct_ids(m, f, funcs)
            direct[(fn, f[0])] = ids
            if f[2]:
                by_name[f[2]] |= ids
    helpers = set(SEEDS)
    #: A function named for an undo that puts the step on the stack itself, or
    #: through another such function (taken to a fixed point, so a wrapper of
    #: `pushTokenUndo` counts as the helper it is).
    grew = True
    while grew:
        grew = False
        for fn, (_, _, funcs, parent, _) in files.items():
            for f in funcs:
                if f[2] and "ndo" in f[2] and f[2] not in helpers and direct[(fn, f[0])] & helpers:
                    helpers.add(f[2])
                    grew = True
    helpers |= WRAPPERS
    helper_call = re.compile(r"\b(" + "|".join(sorted(map(re.escape, helpers))) + r")\(")

    def chain_of(fn, pos):
        _, _, funcs, parent, starts = files[fn]
        i = bisect.bisect_left(starts, pos) - 1
        while i >= 0 and not (funcs[i][0] < pos < funcs[i][1]):
            i = parent[i]
            if i < 0:
                break
        out = []
        while i >= 0:
            out.append(funcs[i])
            i = parent[i]
        return out

    #: Where each helper call's arguments end, so "inside `pushUndo(...)`" is a lookup.
    arg_spans: dict[str, list[tuple[int, int]]] = {}
    for fn, (src, m, *_rest) in files.items():
        arg_spans[fn] = [(c.end(), _call_end(m, c.end())) for c in helper_call.finditer(m)]

    def inside_helper_call(fn, pos):
        return any(a <= pos < b for a, b in arg_spans[fn])

    def in_same_statement(fn, pos):
        """`api(...).then((r) => { pushUndo(...) })`: the contract in a callback of the call's own chain."""
        m = files[fn][1]
        end = min(_statement_end(m, pos), pos + 1500)
        return any(pos <= a <= end for a, _ in arg_spans[fn])

    def reaches(fn, pos, strict=False):
        """Does the code around `pos`, up to its first real function, reach the contract?

        `strict` (a helper's caller) looks only at the function the use sits in:
        a big builder that offers an undo for one thing must not excuse every
        other thing it wires.
        """
        if inside_helper_call(fn, pos) or (not strict and in_same_statement(fn, pos)):
            return True
        if strict:
            #: Near, and in the same function: the contract call follows the use
            #: within a screenful, the way `await put(x); offerUndo(...)` does.
            inner = next(iter(chain_of(fn, pos)), None)
            lo, hi = (inner[0], inner[1]) if inner else (0, len(files[fn][1]))
            return any(
                max(lo, pos - 200) <= a <= min(hi, pos + 1200) for a, _ in arg_spans[fn]
            )
        for f in chain_of(fn, pos):
            if direct[(fn, f[0])] & helpers:
                return True
            if f[2] and f[2] not in INVERSE_NAMES:
                return False
        return False

    # Raw call sites first; the helper-callers rule needs every use of a name.
    raw = []
    for fn, (src, m, *_rest) in files.items():
        for c in CALL.finditer(m):
            end = _call_end(m, c.end())
            if c.group(0).startswith("api.upload"):
                value = '"POST"'  # api.upload is a POST by definition (app.js)
            else:
                mm = METHOD.search(src, c.end(), end)
                if not mm:
                    continue
                value = mm.group(1).strip()
            if value in ('"GET"', "'GET'"):
                continue
            funcs = files[fn][2]
            chain = [funcs.index(f) for f in chain_of(fn, c.start())]
            owner_i = next((i for i in chain if funcs[i][2]), None)
            named_i = next((i for i in chain if funcs[i][2] and funcs[i][2] not in INVERSE_NAMES), None)
            #: Or the step is pushed in a callback a screenful further down the
            #: same function: `send(x).then(() => pushUndo(...))`.
            near = next(iter(chain_of(fn, c.start())), None)
            hi = near[1] if near else len(m)
            ahead = any(c.start() <= a <= min(hi, c.start() + 1000) for a, _ in arg_spans[fn])
            raw.append((fn, c.start(), named_i, owner_i, value, reaches(fn, c.start()) or ahead))

    #: Where each name is written, for the helper-callers rule below.
    wanted = {files[r[0]][2][r[2]][2] for r in raw if r[2] is not None and not r[5]}
    ident = re.compile(r"(?<![\w$.])([A-Za-z_$][\w$]*)\b(?!\s*:)")
    where: dict[str, dict[str, list[int]]] = {}
    for fn, (src, m, *_rest) in files.items():
        found = collections.defaultdict(list)
        for hit in ident.finditer(m):
            if hit.group(1) in wanted:
                before = m[max(0, hit.start() - 9):hit.start()]
                if not before.endswith(("function ", "function*", "const ", "let ", "var ")):
                    found[hit.group(1)].append(hit.start())
        where[fn] = found
    callers_ok: dict[tuple[str, int], bool] = {}

    def all_callers_reach(fn, fi):
        """Every use of this helper sits in code that reaches the contract.

        A helper nested in another function is only visible there, so only
        that function's text is searched; a top-level one is a global.
        """
        key = (fn, fi)
        if key not in callers_ok:
            funcs, parent = files[fn][2], files[fn][3]
            name = funcs[fi][2]
            if parent[fi] == -1:
                hits = [(f, p) for f, found in where.items() for p in found.get(name, [])]
            else:
                lo, hi = funcs[parent[fi]][0], funcs[parent[fi]][1]
                hits = [(fn, p) for p in where[fn].get(name, []) if lo < p < hi]
            callers_ok[key] = bool(hits) and all(reaches(f, p, strict=True) for f, p in hits)
        return callers_ok[key]

    sites = []
    for fn, pos, named_i, owner_i, value, covered in raw:
        funcs = files[fn][2]
        if not covered and named_i is not None and all_callers_reach(fn, named_i):
            covered = True
        name = funcs[named_i][2] if named_i is not None else funcs[owner_i][2] if owner_i is not None else None
        if name is None:
            #: A handler with no name of its own is told apart by what it calls.
            first = re.sub(r"\s+", " ", files[fn][0][pos:pos + 80].split(",")[0].split("(", 1)[-1]).strip(" \"'`")
            name = f"(anonymous {first[:36]})"
        sites.append((fn, name, files[fn][0].count("\n", 0, pos) + 1, value[:40], covered))
    return sites, helpers


def uncovered() -> dict[str, list[int]]:
    sites, _ = analyse()
    out: dict[str, list[int]] = collections.defaultdict(list)
    for fn, name, line, _, covered in sites:
        if not covered:
            out[f"{fn}:{name}"].append(line)
    return dict(out)


EXEMPT: dict[str, str] = {
    "lan-watch.js:lanAnswerDevice": "auth: a sign-in decision for a device; Other devices lists it again to remove",
    "lan-watch.js:lanDismissSwitchedOff": "settings: dismisses a notice; nothing of the person's is changed",
    "meaning.js:meaningNear": "read: asks which words are near the typed ones, shown as a filter",
    "meetings.js:enhanceRecording": "send: part of finishing a recording; the cleaned copy becomes the take and the save is the step",
    "meetings.js:startRecordingTranscription": "job: starts or stops work or a model; deletes no user data",
    "meetings.js:stopRecordingTranscription": "job: starts or stops work or a model; deletes no user data",
    "settings-controls.js:(anonymous /auth/pin)": "auth: sign-in, recovery or lock; no user data",
    "settings-controls.js:(anonymous /auth/pin/forget)": "auth: sign-in, recovery or lock; no user data",
    "settings-controls.js:makeMaintenanceShortcut": "job: starts or stops work or a model; deletes no user data",
    "settings-controls.js:openMaintenanceFolder": "read: opens the launcher logs folder; writes nothing",
    "settings-controls.js:setMaintenanceReinstall": "settings: a setting with its own Reset or the settings history",
    "settings-data.js:saveBackupCopyDir": "settings: a setting with its own Reset or the settings history",
    "tag-suggest.js:noteTagChoices": "read: asks the model for tag suggestions, shown for review",
    "wiring.js:(anonymous /preferences)": "settings: a setting with its own Reset or the settings history",
    "wiring.js:(anonymous /graph/unpin-all)": "settings: the map's pinned positions are view state; pinning again is the way back",
    "usage-ledger.js:(anonymous /usage)": "telemetry: telemetry or a background warm-up; no user data",
    "status.js:(anonymous /preferences)": "settings: a setting with its own Reset or the settings history",
    "settings.js:(anonymous /models/sampling)": "settings: a setting with its own Reset or the settings history",
    "settings.js:(anonymous /debug/health/integrity)": "telemetry: telemetry or a background warm-up; no user data",
    "settings-data.js:(anonymous /suggestions/dismissed/clear)": "settings: clears the dismissed-suggestions list, a preference",
    "settings-controls.js:(anonymous /websearch/searxng/stop)": "job: starts or stops work or a model; deletes no user data",
    "settings-controls.js:(anonymous /websearch/searxng/start)": "job: starts or stops work or a model; deletes no user data",
    "settings-controls.js:(anonymous /websearch/searxng/reinstall)": "job: starts or stops work or a model; deletes no user data",
    "settings-controls.js:(anonymous /websearch/detect-searxng${query})": "job: starts or stops work or a model; deletes no user data",
    "settings-controls.js:(anonymous /templates/draft)": "read: asks the model to draft a template, shown for review",
    "settings-controls.js:(anonymous /tasks/trigger-autonomous)": "job: starts a background pass",
    "settings-controls.js:(anonymous /tasks/history/clear)": "telemetry: clears the list of finished background tasks",
    "settings-controls.js:(anonymous /tasks/autonomous/last/clear)": "telemetry: clears the last background-run note",
    "settings-controls.js:(anonymous /system/console-mode)": "job: starts or stops work or a model; deletes no user data",
    "settings-controls.js:(anonymous /preferences)": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:(anonymous /files/open-exports-folder)": "job: starts or stops work or a model; deletes no user data",
    "settings-controls.js:(anonymous /backups/retention)": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:(anonymous /auth/password-on-open)": "auth: sign-in, recovery or lock; no user data",
    "settings-controls.js:(anonymous /auth/lock-all)": "auth: sign-in, recovery or lock; no user data",
    "settings-controls.js:(anonymous /auth/lan-certificate)": "auth: sign-in, recovery or lock; no user data",
    "settings-controls.js:lanSwitch": "auth: sign-in, recovery or lock; no user data",
    "settings-controls.js:(anonymous /activity/model/stop)": "job: starts or stops work or a model; deletes no user data",
    "navigation.js:(anonymous /search/warm)": "telemetry: telemetry or a background warm-up; no user data",
    "model-bench.js:(anonymous /models/bench/stop)": "job: starts or stops work or a model; deletes no user data",
    "library.js:(anonymous /recycle-bin/empty)": "purge: Empty bin is permanent by design, behind a confirm that says so",
    "library.js:(anonymous /entries/${id}/purge)": "purge: Delete for good is permanent by design, behind a confirm that says so",
    "library.js:(anonymous /audit?entity_type=skill)": "telemetry: clears a skill's run log, not the person's data",
    "library.js:(anonymous ${base}/page-caption?page=${ocrWorks)": "read: reads a page's caption, shown for review",
    "library.js:(anonymous ${base}/ocr-page-read?page=${page}&r)": "read: reads a page's text, shown for review",
    "documents.js:(anonymous /preferences)": "settings: a setting with its own Reset or the settings history",
    "dashboard.js:(anonymous /recordings/recover)": "job: starts or stops work or a model; deletes no user data",
    "app.js:(anonymous path)": "read: the api.upload shorthand itself; each caller is scanned as its own site",
    "whiteboard.js:wbPlaceUploadedImage": "board: the image is placed by wbCreateObject, which pushes the board's create step; the file stays in the Library",
    "whiteboard.js:wbApplyHistoryEntry": "inverse: applies the board history's own undo and redo",
    "whiteboard.js:initWhiteboard": "board: the background image is set through wbSetBackground, which pushes the board step; the file stays in the Library",
    "whiteboard-map.js:wbMapTakePicture": "board: the picture is set on the topic through wbMapSetNodeStyle, which pushes the board step; the file stays in the Library",
    "tidy.js:tidyRunLinkReasons": "job: starts a background pass",
    "meetings.js:nameRecordingSpeakers": "read: asks the model to name speakers, shown for review",
    "library.js:ocrRunRegion": "read: reads a region of a picture, shows the text for review",
    "chat.js:compressChatContext": "read: asks the model to shorten the chat's context; writes nothing",
    "graph.js:graphPinSave": "inverse: the one door for pin writes; each caller pushes its pin step (graphPinStep) and graphSetPin replays it for Undo and Redo",
    "whiteboard.js:wbRestoreLinks": "inverse: draws a deleted item's links again for the board history's own Undo",
    "whiteboard-map.js:wbMapRestoreRows": "inverse: puts back a deleted branch for the board history's own Undo and Redo",
    "whiteboard-map.js:wbMapAdoptProvisional": "board: gives a topic already on the board's history (its create step is remapped to the server id)",
    "settings-wiring.js:commitCaptureImages": "send: uploads the pictures of a note being saved; the save is the step (Undo bins the note)",
    "library.js:noteRead": "telemetry: opening a saved link marks it read, as visiting a page does; reading is not an edit",
    "chat-undo.js:chatPut": "inverse: the chat undo helpers' own PUT",
    "batch-space.js:batchSpaceRequest": "inverse: the move request itself; batchMoveToSpace pushes the step with the answer's old places",
    "settings-controls.js:restoreFullBackup": "job: a confirmed restore that snapshots the current notebook first; the snapshot is the way back",
    "meetings.js:meetingTakeAppend": "job: uploads the audio chunks of a take in progress; Discard is the take's own undo",
    "media.js:toggleDictation": "read: transcribes speech into the box being typed in",
    "documents.js:docAiReview": "read: asks the model to check a document, shows a result",
    "capture-ask.js:streamChatEvents": "send: streams the Ask box's answer; the question is kept in Ask history",
    "account-recovery.js:onMake": "auth: sign-in, recovery or lock; no user data",
    "account-recovery.js:saveRecoveryKeyFile": "auth: sign-in, recovery or lock; no user data",
    "account-recovery.js:submit": "auth: sign-in, recovery or lock; no user data",
    "account-recovery.js:submitPasswordReset": "auth: sign-in, recovery or lock; no user data",
    "account-recovery.js:submitRecovery": "auth: sign-in, recovery or lock; no user data",
    "activity-panel.js:stopActivityJob": "job: starts or stops work or a model; deletes no user data",
    "activity-panel.js:stopActivityModel": "job: starts or stops work or a model; deletes no user data",
    "activity-panel.js:stopAllActivity": "job: starts or stops work or a model; deletes no user data",
    "ai-tools.js:applyEmbeddingBackend": "settings: a setting with its own Reset or the settings history",
    "ai-tools.js:applyFeatureModel": "settings: a setting with its own Reset or the settings history",
    "chat-tasks.js:renderTasks": "job: starts or stops work or a model; deletes no user data",
    "improve-panel.js:runImprove": "read: reads or asks the model; shows a result, writes nothing",
    "ai-tools.js:saveUiState": "settings: a setting with its own Reset or the settings history",
    "ai-tools.js:wireReindexButton": "job: starts or stops work or a model; deletes no user data",
    "app-palette.js:openPalette": "telemetry: telemetry or a background warm-up; no user data",
    "app.js:lockNow": "auth: sign-in, recovery or lock; no user data",
    "app.js:startApp": "telemetry: telemetry or a background warm-up; no user data",
    "app.js:startWithoutPassword": "auth: sign-in, recovery or lock; no user data",
    "ask-chart.js:renderAskChart": "read: reads or asks the model; shows a result, writes nothing",
    "ask-compose.js:renderActCard": "read: reads or asks the model; shows a result, writes nothing",
    "attachment-actions.js:caption": "read: asks the model for a caption shown for review",
    "attachment-actions.js:describe": "read: asks the model for a description shown for review",
    "boot-guard.js:report": "telemetry: telemetry or a background warm-up; no user data",
    "captions.js:captionSendNext": "read: reads or asks the model; shows a result, writes nothing",
    "captions.js:startLiveCaptions": "read: reads or asks the model; shows a result, writes nothing",
    "captions.js:stopLiveCaptions": "read: reads or asks the model; shows a result, writes nothing",
    "capture-ask.js:renderAnswerGrounding": "telemetry: a click on a source records that the note was opened after the question, to rank later answers; there is nothing to take back",
    "ask-compose.js:renderAskFollowups": "read: reads or asks the model; shows a result, writes nothing",
    "capture-ask.js:scheduleCaptureTagSuggestions": "read: reads or asks the model; shows a result, writes nothing",
    "categories-panel.js:propose": "read: asks for a split proposal",
    "chat-agent.js:renderToolConfirm": "send: runs a tool the agent asked for, in the chat's own turn history",
    "chat-attach.js:commitStagedImages": "send: uploads the pictures of a chat message at the moment it is sent; the message is in the chat's own turn history",
    "chat-attach.js:offerFollowups": "read: reads or asks the model; shows a result, writes nothing",
    "chat-attach.js:openExtractPreview": "read: reads or asks the model; shows a result, writes nothing",
    "chat-attach.js:saveFollowups": "telemetry: stores suggested follow-up chips",
    "chat-attach.js:sendChatMessage": "send: a chat message, kept by the chat's own turn history",
    "chat-attach.js:writeCheckpoint": "send: a chat message, kept by the chat's own turn history",
    "chat.js:setResponseMode": "settings: a setting with its own Reset or the settings history",
    "chat.js:setWebSearxngRunning": "job: starts or stops work or a model; deletes no user data",
    "dash-night.js:renderNightCard": "job: starts or stops work or a model; deletes no user data",
    "dashboard.js:saveDashLayout": "settings: a setting with its own Reset or the settings history",
    "dashboard.js:saveQuickAccess": "settings: a setting with its own Reset or the settings history",
    "dashboard.js:saveQuickTints": "settings: a setting with its own Reset or the settings history",
    "dashboard.js:streamDigest": "read: reads or asks the model; shows a result, writes nothing",
    "dashboard.js:undoActorFrom": "inverse: reverses an actor's changes through /events/undo (existing UNFOLDED entry)",
    "date-field.js:foot": "read: reads or asks the model; shows a result, writes nothing",
    "documents-code.js:docFormatRemoteRefusal": "read: reads or asks the model; shows a result, writes nothing",
    "documents-code.js:docRemoteDiagnostics": "read: reads or asks the model; shows a result, writes nothing",
    "documents-codekit.js:docAssistAsk": "read: reads or asks the model; shows a result, writes nothing",
    "documents-word.js:docWordUploadPicture": "job: a picture inside a Word file being imported goes to the media store; the imported document is the step (Undo bins it)",
    "documents.js:docDesktopFullscreenToggle": "job: starts or stops work or a model; deletes no user data",
    "documents.js:docDictionaryWrite": "settings: a setting with its own Reset or the settings history",
    "documents.js:docPutFields": "board: document field write; its callers push their own undo",
    "documents.js:docSuggestAnswers": "read: reads or asks the model; shows a result, writes nothing",
    "documents.js:ensureDocumentExists": "board: creates the document being typed into; the editor's history starts there",
    "documents.js:openDocAiHistory": "inverse: reverts an AI edit from its log, which is itself the undo",
    "documents.js:runDocAiEdit": "read: asks the model for a revision shown for review; accepting it pushes pushDocAiUndo",
    "documents.js:saveDocument": "board: the document editor's autosave; typing is the editor's own docUndo history",
    "editor.js:inlineAiSubmit": "read: asks the model for a revision shown for review; accepting it is an editor change with the document's own history",
    "embed-choices.js:embedChoiceInstall": "job: starts or stops work or a model; deletes no user data",
    "embed-choices.js:embedChoiceUninstall": "job: starts or stops work or a model; deletes no user data",
    "embed-choices.js:embedChoiceUse": "settings: a setting with its own Reset or the settings history",
    "embed-choices.js:embedPullTyped": "job: starts or stops work or a model; deletes no user data",
    "first-run.js:firstStepName": "settings: a setting with its own Reset or the settings history",
    "first-run.js:firstStepsSample": "job: starts or stops work or a model; deletes no user data",
    "graph-canvas.js:gcShowTopic": "read: reads a topic summary",
    "graph.js:openGraphLinkPanel": "read: reads or asks the model; shows a result, writes nothing",
    "help-chat.js:helpChatStreamTurn": "read: reads or asks the model; shows a result, writes nothing",
    "library.js:analyseMediaRow": "read: asks the model to read a picture",
    "library.js:libraryActions": "purge: Delete for good in the bin is permanent by design, behind a confirm that says so",
    "library.js:ocrReadRange": "read: reads or asks the model; shows a result, writes nothing",
    "lightbox-view.js:buildMoreMenu": "read: menu of analysis actions on a picture",
    "lightbox-actions.js:reevaluateEntry": "read: asks the model to re-check a note, applied through renderReevaluateResult",
    "lightbox.js:renderInlineAction": "read: asks the model about a note",
    "margin-reader.js:marginAsk": "read: reads or asks the model; shows a result, writes nothing",
    "meetings.js:meetingSummarise": "read: asks the model for a summary",
    "meetings.js:meetingTakeBegin": "job: opens the recording's object when a take starts; the finished recording is the step (Undo bins it)",
    "model-bench.js:benchRow": "settings: a setting with its own Reset or the settings history",
    "model-bench.js:runModelBench": "job: starts or stops work or a model; deletes no user data",
    "navigation.js:usageFlush": "telemetry: telemetry or a background warm-up; no user data",
    "note-cards.js:entryItem": "job: stops the background filing pass on a note; the note's category changes are edits with their own Undo",
    "note-history.js:toggleThenAndNow": "read: reads a comparison",
    "note-history.js:undoSkillRun": "inverse: reverses a skill run's writes after a confirm (existing UNFOLDED entry)",
    "ocr-engine.js:ocrEngineLanguagePicker": "settings: a setting with its own Reset or the settings history",
    "ocr-engine.js:ocrEngineStartInstall": "job: starts or stops work or a model; deletes no user data",
    "onboarding.js:maybeShowConsoleViewIntro": "settings: a setting with its own Reset or the settings history",
    "onboarding.js:renderOnboardingActions": "job: starts or stops work or a model; deletes no user data",
    "phone-shell.js:clearAppCache": "job: starts or stops work or a model; deletes no user data",
    "notifications.js:openExportsFromNotification": "job: starts or stops work or a model; deletes no user data",
    "phone-shell.js:quitApp": "auth: sign-in, recovery or lock; no user data",
    "questions-view.js:initQuestionsView": "job: starts or stops work or a model; deletes no user data",
    "quickadd.js:noteOffersFetch": "read: reads or asks the model; shows a result, writes nothing",
    "reminder-notify.js:showReminderNotification": "telemetry: telemetry or a background warm-up; no user data",
    "search.js:persistSavedFinds": "settings: a setting with its own Reset or the settings history",
    "semantic-notice.js:semanticDecline": "job: starts or stops work or a model; deletes no user data",
    "semantic-notice.js:semanticOnboardingOffer": "job: starts or stops work or a model; deletes no user data",
    "semantic-notice.js:semanticSetAutoInstall": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:addPersona": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:applyBackendChoice": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:applyChatModel": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:applyOcrModel": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:applyUtilityModel": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:applyVisionModel": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:deleteProfile": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:exportFullBackup": "job: starts or stops work or a model; deletes no user data",
    "settings-controls.js:resetAllFeatureModels": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:restartMemoryMap": "job: starts or stops work or a model; deletes no user data",
    "settings-controls.js:runEmbeddingFallback": "job: starts or stops work or a model; deletes no user data",
    "settings-controls.js:saveExportSaveDir": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:saveModelContextWindow": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:saveRunBudget": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:saveWebSearchSettings": "settings: a setting with its own Reset or the settings history",
    "settings-controls.js:submit": "auth: sign-in, recovery or lock; no user data",
    "settings-data.js:backupNow": "job: starts or stops work or a model; deletes no user data",
    "settings-data.js:importDirectory": "job: starts or stops work or a model; deletes no user data",
    "settings-data.js:run": "job: a confirmed restore that snapshots the current notebook first; deleting a backup file is housekeeping",
    "settings-data.js:settingsHistoryApply": "settings: a setting with its own Reset or the settings history",
    "settings-models.js:checkCustomModel": "read: reads or asks the model; shows a result, writes nothing",
    "settings-models.js:modelCancel": "job: starts or stops work or a model; deletes no user data",
    "settings-models.js:modelDownload": "job: starts or stops work or a model; deletes no user data",
    "settings-models.js:modelRemove": "job: starts or stops work or a model; deletes no user data",
    "settings-packages.js:voiceModelsWire": "job: removes a downloaded dictation model behind a confirm that names the size freed; deletes no user data and it downloads again on the next dictation",
    "settings-models.js:modelUse": "settings: picks the active model",
    "settings-models.js:run": "settings: a setting with its own Reset or the settings history",
    "settings-panes.js:changePassword": "auth: sign-in, recovery or lock; no user data",
    "settings-panes.js:reportTimezone": "settings: a setting with its own Reset or the settings history",
    "settings-panes.js:savePrefs": "settings: a setting with its own Reset or the settings history",
    "settings-panes.js:saveSearchProvider": "settings: a setting with its own Reset or the settings history",
    "settings-panes.js:setPreference": "settings: a setting with its own Reset or the settings history",
    "settings-wiring.js:persistSavedSearches": "settings: a setting with its own Reset or the settings history",
    "settings-wiring.js:lockRequest": "auth: sign-in, recovery or lock; no user data",
    "settings.js:clearLogs": "telemetry: telemetry or a background warm-up; no user data",
    "settings.js:deleteSavedTheme": "settings: a setting with its own Reset or the settings history",
    "settings.js:learnedRunNow": "job: starts or stops work or a model; deletes no user data",
    "settings.js:learnedSetSwitch": "settings: a setting with its own Reset or the settings history",
    "settings.js:renderJobOverview": "job: starts or stops work or a model; deletes no user data",
    "settings-health.js:renderSamplingRows": "settings: a setting with its own Reset or the settings history",
    "settings-health.js:save": "settings: a setting with its own Reset or the settings history",
    "settings.js:saveCurrentLook": "settings: a setting with its own Reset or the settings history",
    "personas-pane.js:renderPersonas": "read: reads or asks the model; shows a result, writes nothing",
    "personas-pane.js:savePersonaList": "settings: a setting with its own Reset or the settings history",
    "shell-reminders.js:refreshMediaSession": "auth: sign-in, recovery or lock; no user data",
    "skills.js:onchange": "settings: a setting with its own Reset or the settings history",
    "skills.js:saveFile": "job: writes an export the person asked for to the exports folder, as a download does; it deletes nothing",
    "skills.js:saveSkillList": "settings: a setting with its own Reset or the settings history",
    "skills.js:saveToolSwitch": "settings: a setting with its own Reset or the settings history",
    "spaces-find.js:saveTemplateList": "settings: a setting with its own Reset or the settings history",
    "status.js:insightSend": "settings: a verdict on an insight, either way reversible by the other verdict",
    "status.js:setChatMode": "settings: a setting with its own Reset or the settings history",
    "status.js:toggleNotificationMute": "settings: a setting with its own Reset or the settings history",
    "suggestions-inbox.js:fillReasons": "read: reads or asks the model; shows a result, writes nothing",
    "suggestions-inbox.js:inboxLinksPane": "read: reads or asks the model; shows a result, writes nothing",
    "tag-manager.js:drawTurnedDown": "settings: turned-down tag suggestions list, a preference",
    "tidy.js:tidyHistory": "inverse: undoes a past tidy run from the history list",
    "tidy.js:tidyTools": "settings: a setting with its own Reset or the settings history",
    "update-dialogs.js:applyUpdateNow": "job: installs an update, with its own confirm",
    "update-dialogs.js:askUpdateChoiceOnce": "settings: a setting with its own Reset or the settings history",
    "usage-ledger.js:renderUsage": "telemetry: telemetry or a background warm-up; no user data",
    "vault-unlock.js:unlockPrivateNotes": "auth: sign-in, recovery or lock; no user data",
    "whiteboard-history.js:build": "board: board snapshot list, the board's version history",
    "whiteboard-history.js:wbSnapshotRow": "board: board snapshot list, the board's version history",
    "whiteboard-map.js:wbMapSummariseBranch": "read: asks the model for a summary",
    "whiteboard.js:uploadToLibrary": "job: a board export saved to the Library as a picture; the Library's Delete (with Undo) removes it",
    "whiteboard.js:wbCreateCopies": "board: low-level board create; its callers push wbPushUndo",
    "whiteboard.js:wbPaintStickyDates": "read: reads dates out of sticky text",
    "whiteboard.js:wbSaveMapBulkMove": "board: low-level board save; its callers push wbPushUndo",
    "whiteboard.js:wbSaveNode": "board: low-level board save; its callers push wbPushUndo",
    "whiteboard.js:wbSaveObject": "board: low-level board save; its callers push wbPushUndo",
    "whiteboard.js:wbSaveSketchProps": "board: low-level board save; its callers push wbPushUndo",
    "wiring.js:applyPendingChatTitle": "send: names a chat as its first message creates it; renaming a chat afterwards has Undo",
}


def test_scanner_sees_the_writes():
    sites, helpers = analyse()
    assert len(sites) > 600, "the scanner lost the mutating calls"
    assert {"pushUndo", "offerUndo", "offerCategoryUndo", "pushEntryPutUndo"} <= helpers
    assert sum(1 for s in sites if s[4]) > 100


def test_every_write_offers_undo_or_is_exempt():
    left = {k: v for k, v in uncovered().items() if k not in EXEMPT}
    if os.environ.get("UNDO_COVERAGE_DUMP"):
        for key, lines in sorted(uncovered().items()):
            print(key, lines)
    assert not left, (
        "These functions send a POST/PUT/PATCH/DELETE without reaching the undo "
        "contract (pushUndo/offerUndo or a helper built on them). Offer an Undo "
        "with a working redo, or explain why not in EXEMPT:\n"
        + "\n".join(f"  {k} (line {v[0]})" for k, v in sorted(left.items()))
    )


def test_exempt_only_shrinks():
    now = uncovered()
    stale = sorted(k for k in EXEMPT if k not in now)
    assert not stale, "Remove from EXEMPT, they now offer undo or are gone:\n  " + "\n  ".join(stale)


def test_exempt_reasons_are_classed():
    classes = ("auth", "read", "send", "settings", "telemetry", "job", "inverse", "board", "purge")
    bad = [k for k, v in EXEMPT.items() if not v.startswith(tuple(c + ":" for c in classes))]
    assert not bad, "EXEMPT reasons start with a class and a colon:\n  " + "\n  ".join(bad)


# --- every step carries a redo (owner, 2026-10-11) ----------------------------
#
# "Make sure everything that can be undone and be redone as well." A step on
# the stack with no redo (or one that does nothing) turns Ctrl+Shift+Z into a
# no-op after that Undo. The calls that take the redo as an argument are held
# to passing a real one; the kit helpers and the board history build theirs.

#: name -> how many arguments make the call complete (the redo is the last).
REDO_ARGS = {"pushUndo": 3, "offerUndo": 4, "offerCategoryUndo": 3, "wbPushCall": 3}
#: `file:line: reason`. Shrink-only, like EXEMPT; empty on purpose.
NO_REDO: dict[str, str] = {}
_EMPTY_FN = re.compile(r"^(null|undefined|noop|\(\)\s*=>\s*(\{\s*\}|null|undefined)|async\s*\(\)\s*=>\s*\{\s*\})$")


def redo_gaps() -> list[str]:
    found = []
    call = re.compile(r"(?<![\w$.])(" + "|".join(REDO_ARGS) + r")\(")
    for path in sorted(JS.glob("*.js")):
        src = path.read_text(encoding="utf-8")
        m = mask(src)
        for hit in call.finditer(m):
            end = _call_end(m, hit.end())
            args, depth, start = [], 0, hit.end()
            for i in range(hit.end(), end - 1):
                c = m[i]
                if c in "([{":
                    depth += 1
                elif c in ")]}":
                    depth -= 1
                elif c == "," and depth == 0:
                    args.append(src[start:i].strip())
                    start = i + 1
            tail = src[start:end - 1].strip()
            if tail:
                args.append(tail)
            need = REDO_ARGS[hit.group(1)]
            line = src.count("\n", 0, hit.start()) + 1
            #: The definition itself (`function pushUndo(label, undo, redo)`) is not a call.
            if m[max(0, hit.start() - 9):hit.start()].endswith(("function ", "function*")):
                continue
            if len(args) < need:
                found.append(f"{path.name}:{line}: {hit.group(1)} has no redo")
            elif _EMPTY_FN.match(args[need - 1]):
                found.append(f"{path.name}:{line}: {hit.group(1)} redo does nothing")
    return found


def test_every_step_on_the_stack_has_a_redo():
    left = [g for g in redo_gaps() if g not in NO_REDO]
    assert not left, (
        "These steps put an Undo on the stack with no working Redo. Pass the redo "
        "(the same act again, or its inverse's inverse):\n  " + "\n  ".join(left)
    )


def test_no_redo_list_only_shrinks():
    now = set(redo_gaps())
    stale = sorted(k for k in NO_REDO if k not in now)
    assert not stale, "Remove from NO_REDO, they now carry a redo:\n  " + "\n  ".join(stale)


# --- the stand-alone windows (INBOX 898) ----------------------------------------
#
# capture.html and clip.html save a note in a window of their own, through one
# `call` the scanner cannot read as a write. They announce the note to the app
# window (which puts it on its Undo stack) or offer their own Undo.


def test_the_standalone_windows_put_what_they_save_on_an_undo():
    frontend = JS.parent
    for name in ("capture.js", "clip.js"):
        text = (JS / name).read_text(encoding="utf-8")
        assert "standaloneUndo.announce(" in text and "standaloneUndo.offer(" in text, name
    for page in ("capture.html", "clip.html"):
        html = (frontend / page).read_text(encoding="utf-8")
        assert html.index("standalone-undo.js") < html.index('/js/' + page.replace(".html", ".js")), page
    kit = (JS / "standalone-undo.js").read_text(encoding="utf-8")
    assert "note-made" in kit and "/restore" in kit, "Undo bins the note and Redo restores it"
    #: The app window's half: it answers, so the other window can close.
    app_side = (JS / "quick-note.js").read_text(encoding="utf-8")
    assert "note-made-ack" in app_side and "pushEntryCreateUndo(" in app_side


# --- two faults the live check found (INBOX 898) ----------------------------------
#
# Both are in the shared history machinery, so both are held by name: they were
# invisible to every static test and to every sweep that pressed Ctrl+Z once.


def test_ctrl_z_belongs_to_a_board_only_while_the_board_is_showing():
    status = (JS / "status.js").read_text(encoding="utf-8")
    body = status[status.index("function boardHistoryActive()"):][:900]
    assert "getClientRects().length" in body, (
        "an open board's view keeps no `hidden` class when another tab covers it, "
        "so without a visibility test Ctrl+Z on Notes walks the board's history"
    )


def test_a_history_remap_translates_each_id_once():
    board = (JS / "whiteboard.js").read_text(encoding="utf-8")
    remap = board[board.index("function wbRemapUndoIds("):][:3500]
    assert "wbRemapSeen" in remap and "once(" in remap, (
        "items brought back reuse the ids just deleted (8 comes back as 9 and 9 as 8); "
        "a second translation of an already translated id duplicates and drops steps"
    )
    assert 'wbRemapSeen.set(made, new Set(["id"]))' in board, "a recreated item's own step is already in the new ids"
