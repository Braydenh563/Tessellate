"""The runner's own paged scan and candidate reads (L-chat-62).

A step whose spec carries `scan` (cue phrases) is run here, not by the model:
`list_notes` is paged to the end through the same `execute_tool` a model call
uses, every note seen is matched against the cues in full text, and the
matches become the run's `candidates`. A step with `reads: "candidates"` calls
`get_note` on each of them. Both emit ordinary `tool` and `step` events, so the
plan card, the chips and the run's state read exactly as a model-driven step.

Why: measured on a 1.5B model over the seventy-note loose-ends fixture, the
model called `list_notes` once with invented filters, never paged, stalled
twice and named 2 of 8. Paging and a phrase match need no judgment, and the
skill's claim is *all* the loose ends; the model keeps the judgment that does
need it, in the answer step.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from tessellate.ai import tools
from tessellate.ai.agent_turn import _tool_event
from tessellate.ai.tools._common import _readable
from tessellate.core.database import Entry

#: Pages the runner may read in one scan. A runner page costs no model call,
#: so this is far above `skill_runner.MAX_PAGES_PER_STEP` (a model's paging
#: budget); 40 pages of 25 is a thousand notes.
MAX_SCAN_PAGES = 40
SCAN_PAGE = tools.MAX_LIST_LIMIT
#: Candidates read in full and named in the step's answer.
MAX_CANDIDATES = 20
#: The first line of a candidate in the step's answer, in characters.
LINE_CHARS = 140


def cue_pattern(cues: list[str]) -> re.Pattern:
    """Whole-phrase, case-blind: "must" matches "Must renew", not "mustard"."""
    return re.compile(r"\b(?:" + "|".join(re.escape(c) for c in cues) + r")\b", re.IGNORECASE)


def _first_line(text: str) -> str:
    line = next((part.strip() for part in text.splitlines() if part.strip()), "")
    return line if len(line) <= LINE_CHARS else line[: LINE_CHARS - 1].rstrip() + "…"


def _call(session, run, name: str, args: dict) -> tuple[dict, dict]:
    from tessellate.ai import skill_runner

    result = tools.execute_tool(session, name, args)
    event = _tool_event(name, args, result)
    skill_runner._absorb(run.known, event)
    return result, event


def _scan(setup, run, st) -> Iterator[dict]:
    """Page `list_notes` to the end; the cue matches become `candidates`."""
    pattern = cue_pattern(st.spec["scan"])
    offset, matched, seen = 0, [], 0
    for _page in range(MAX_SCAN_PAGES):
        result, event = _call(setup.session, run, "list_notes", {"offset": offset, "limit": SCAN_PAGE})
        yield event
        if "error" in result:
            return None, str(result["error"])
        for note in result.get("notes") or []:
            seen += 1
            entry = setup.session.get(Entry, note["id"])
            text = _readable(entry) if entry is not None else ""
            if pattern.search(text):
                matched.append((note["id"], _first_line(text)))
        if not result.get("has_more"):
            return (matched, seen, False), ""
        offset = int(result.get("next_offset") or offset + SCAN_PAGE)
    return (matched, seen, True), ""


def _scan_answer(matched: list, seen: int, truncated: bool, cues: list[str]) -> str:
    head = f"I read all {seen} notes" if not truncated else f"I read the first {seen} notes (more were left)"
    if not matched:
        return f"{head}; none says {', '.join(cues)}."
    lines = [f"- #{note_id}: {line}" for note_id, line in matched[:MAX_CANDIDATES]]
    more = f"\n({len(matched) - MAX_CANDIDATES} more not listed.)" if len(matched) > MAX_CANDIDATES else ""
    return f"{head}; {len(matched)} read as unfinished:\n" + "\n".join(lines) + more


def _reads(setup, run) -> Iterator[dict]:
    """`get_note` on each candidate; their full text is the step's answer."""
    parts = []
    for note_id in (run.known.get("candidates") or [])[:MAX_CANDIDATES]:
        result, event = _call(setup.session, run, "get_note", {"note_id": note_id})
        yield event
        if "error" not in result:
            parts.append(f"#{note_id}: {result.get('content') or ''}")
    return "\n\n".join(parts) or "There were no candidates to read."


def run(setup, run, st) -> Iterator[dict]:
    """Run one scanning or reading step; sets `st.outcome` like a model step."""
    from tessellate.ai import skill_runner

    if not run.started:
        yield setup.plan
        run.started = True
    yield {"type": "step", "index": st.index, "state": "running", "text": st.step}
    if st.spec.get("scan"):
        got, error = yield from _scan(setup, run, st)
        if got is None:
            yield skill_runner._halt(run, st, "failed", f"list_notes failed: {error}", replannable=False)
            return
        matched, seen, truncated = got
        run.known["candidates"] = [note_id for note_id, _line in matched]
        run.known["candidate_lines"] = [[note_id, line] for note_id, line in matched[:MAX_CANDIDATES]]
        if truncated:
            run.truncated = True
            st.truncated = f"stopped after {MAX_SCAN_PAGES} pages with more left to read; {seen} notes were seen"
        answer = _scan_answer(matched, seen, truncated, st.spec["scan"])
    else:
        answer = yield from _reads(setup, run)
    yield skill_runner._done_event(st, [], set(st.spec.get("tools") or []))
    run.step_history.append({"question": st.step, "answer": skill_runner._step_answer(answer, [], st.truncated)})
    st.outcome = "done"


def unnamed_line(run, answer: str) -> str:
    """**A small model's answer may drop a candidate; the run's claim is all of
    them.** The candidates the answer did not cite by `#id`, as one closing
    paragraph, or "" when it named every one."""
    left = [
        (note_id, line)
        for note_id, line in run.known.get("candidate_lines") or []
        if not re.search(rf"#\s*{note_id}\b|\bid\s*{note_id}\b", answer)
    ]
    if not left:
        return ""
    return "Also unfinished, from the scan:\n" + "\n".join(f"- #{note_id}: {line}" for note_id, line in left)
