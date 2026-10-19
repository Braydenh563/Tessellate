"""Running a skill: one step at a time, with progress and a result.

The difference between this and handing the model a numbered list is the
difference between a plan and a job. A list inside one request is a plan the
model is free to ignore, and a 3B model given four instructions at once
reliably does the first, narrates the rest, and reports success. Here each
step is its own bounded agent turn, so:

- the app **knows** which step is running, and the UI ticks them off;
- a step that fails is named, instead of a run that quietly did less than it
  said (roadmap §21's "a skill that fails halfway should say which step");
- each turn carries one instruction and the skill's own few tool schemas
  rather than everything at once, which is what makes this work on the small
  models it is aimed at (§11a);
- what changed is collected as it happens, with the call that would undo it.

A skill with no steps is one turn, exactly what it was before the rebuild.

**A step is a goal, not a turn** (AGENT_SKILLS_REFORM.md, Phase A). One turn per
step fixed "the model did all four instructions at once"; it did not fix the
report that followed it, *"I ran a skill and it ran no tools… the models often
dont even properly complete a step before they are prompted for the next
step."* The cause was that this file decided a step was over when the model
stopped emitting, so a small model narrating "Here is the result of step 2…"
was indistinguishable from one that had done it. A step now carries a contract
(`skills.STEP_EXPECTS`), and a step that has not met it is re-prompted with a
nudge naming the tool rather than ticked off. A step declaring no contract, a
plain string, which is every skill anyone has saved by hand, behaves exactly
as it did before.

**Everything here has to stay lazy.** The events are consumed by a streaming
NDJSON response, so anything that materialises the iterator holds the whole
step back and releases it in one block. That was a real bug (§35H): putting
the first event back with `[first, *events]` looks harmless and is not, the
`*` runs the generator to exhaustion before the list even exists, so a step's
prose, tool chips and all arrived together once the step had finished. Reported
as "the steps don't stream visually as they are written and are instead dumped
once each section of the response is finished". `chain` is the version of that
line which does not.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from itertools import chain
from dataclasses import dataclass
from dataclasses import field as dc_field

from sqlalchemy.orm import Session

from tessellate.ai import agent, budget as run_budget, plan_writes, skills, tools
from tessellate.ai.model_manager import ModelManager
from tessellate.ai.ollama_client import OllamaClient

logger = logging.getLogger("tessellate.skills")

# Rounds a single step may take before it has to earn more. Lower than a free
# chat turn on purpose: a step is one instruction, and a model still looping
# after this many rounds has misunderstood it rather than run out of room.
STEP_ROUNDS = 4

# …and rounds a step can earn by getting somewhere (agent.EARNED_ROUNDS is the
# same idea for an ordinary turn, and the reasoning is written up there).
#
# This is the reported failure seen from inside a run: *"the agent struggles
# with long tasks like skills, then cuts out half way through."* A step such as
# "tag every untagged note" is one instruction and a dozen tool calls, and four
# flat rounds cut it off in the middle every time, with the step ticked off as
# done, because the runner could only see that the turn had produced text.
# Both halves of that are fixed: a step that keeps doing new things keeps
# going, and a step that runs out is marked stalled rather than done.
STEP_EARNED_ROUNDS = 6

# How much of a step's answer is carried into the next step's history. Enough
# to say what it found, not enough to refill the window each time.
STEP_ANSWER_CHARS = 600

# How many touched-note ids one step's summary names before it just says
# "and N more", a step that tags a hundred notes must not spend the whole
# STEP_ANSWER_CHARS budget on ids and leave no room for the model's own words.
MAX_TOUCHED_IDS_NAMED = 15


def _touched_ids(step_changes: list[dict], field: str) -> list[int]:
    return sorted({c[field] for c in step_changes if c.get(field) is not None})


def _touched_clause(label: str, ids: list[int]) -> str:
    """`" [Notes touched this step: #3, #9]"`, or `""` if `ids` is empty."""
    if not ids:
        return ""
    named = ids[:MAX_TOUCHED_IDS_NAMED]
    text = ", ".join(f"#{i}" for i in named)
    if len(ids) > len(named):
        text += f", and {len(ids) - len(named)} more"
    return f" [{label} touched this step: {text}]"


def _step_answer(answer: str, step_changes: list[dict], truncated: str = "") -> str:
    """What the next step's history records for this one: the model's own
    words, plus which notes and documents it actually touched, if any did.

    **Reported, in the shape of "the agent loses the plot half way through a
    job":** a step's own narration ("tagged the relevant notes") is a prose
    summary the model wrote about itself, not a record of what happened, 
    and it is *all* the next step saw. A later step that needed "those notes"
    had nothing but that sentence to work from: too vague to act on, so it
    either re-searched (and could easily find a different set) or guessed.
    The ids in `step_changes` (`agent.py`'s own `change` events, the same
    ones that already back the chat UI's View/Undo buttons) are the ground
    truth of what this step did, appending them is handing the next step
    the same fact a human reading the transcript would have.

    Ids are the right thing to carry between steps even though the system
    prompt tells the model never to show one to the *user*, that rule is
    about what appears in an answer, not about how steps refer to things
    internally, which is exactly how every id-targeting tool (`edit_note`,
    `tag_note`, `link_notes`...) already works.
    """
    summary = _touched_clause("Notes", _touched_ids(step_changes, "note_id")) + _touched_clause(
        "Documents", _touched_ids(step_changes, "document_id")
    )
    # A step that could not finish paging says so here rather than only on the
    # event, because this string is the whole of what the *next* step is told
    # about this one: a later step that reports "every loose end in your
    # notebook" off a sixth of it is the fabrication this run exists to avoid.
    if truncated:
        summary += f" [{truncated}]"
    if not summary:
        return (answer[:STEP_ANSWER_CHARS] if answer else "") or "(nothing said)"
    # Truncate the model's own words first, not the ids, a next step that
    # cannot see what happened is guessing; the prose is what it can afford
    # to lose.
    base = answer[: max(0, STEP_ANSWER_CHARS - len(summary))] if answer else ""
    return (base or "(nothing said)") + summary


#: **What each `verify` predicate means**, keyed by the names
#: `skills.VERIFY_PREDICATES` accepts at save time.
#:
#: The two halves are deliberately in different modules and checked against
#: each other by `tests/test_harness_verifier.py`: `skills.py` is imported by
#: everything and must stay free of app imports, so it owns the vocabulary,
#: and this file owns the evaluation because it is the only thing that can
#: read the notebook. A name in one and not the other is the shape of bug
#: `core/events.py`'s driver table exists to catch: it would be accepted from
#: the user, stored, and then pass silently on every run.
#:
#: `before` is the same reading taken before the first step ran, which is what
#: makes `unchanged` answerable at all: "the notebook has as many notes as it
#: started with" is not a property of a number, it is a property of two.
PREDICATES = {
    "min": lambda got, want, before: got >= want,
    "max": lambda got, want, before: got <= want,
    "equals": lambda got, want, before: got == want,
    "unchanged": lambda got, want, before: (before is not None and got == before) is bool(want),
}


class Verification:
    """Did the run leave the notebook in the state the skill promised?

    **Why a run needs one at all.** Everything else in this file checks that
    the *model* did something: called a tool, changed a note, said words. None
    of that is the same as the job being done, and the gap between them is
    where the reported failures live ("I ran a skill and it ran no tools", "it
    only merged two categories and left it at that"). A verification is the
    one check made against the notebook rather than against the transcript.

    `ok` is False for a run that stopped early even when the skill declares no
    postcondition: a run that did four of its nine steps has not done the job,
    whatever the notebook says, and reporting that as verified would be the
    same silent tick one level up.
    """

    __slots__ = ("ok", "reason", "tool", "field", "expect", "got", "before")

    def __init__(
        self,
        ok: bool,
        reason: str,
        tool: str = "",
        field: str = "",
        expect: dict | None = None,
        got: int | None = None,
        before: int | None = None,
    ) -> None:
        self.ok = ok
        self.reason = reason
        self.tool = tool
        self.field = field
        self.expect = dict(expect or {})
        self.got = got
        self.before = before

    def as_event(self) -> dict:
        return {
            "type": "verification",
            "ok": self.ok,
            "reason": self.reason,
            "tool": self.tool,
            "field": self.field,
            "expect": self.expect,
            "got": self.got,
            "before": self.before,
        }


def _reading(session: Session, block: dict) -> tuple[int | None, str]:
    """The one number a verify block is about, and why it is missing if it is.

    Runs the tool itself rather than trusting anything the model reported: the
    whole value of the verifier is that its answer comes from the notebook.
    Never raises, for the reason `_record_run` does not either: a verification
    that blows up would take a run that did all its work with it.
    """
    name = block.get("tool") or ""
    #: **A verifier may not write.** The one thing that must never happen here
    #: is the check changing what it is checking: `verify` names any known
    #: tool, `_reading` runs it with no arguments twice per run (before the
    #: first step and after the last), and a block naming `delete_note` would
    #: therefore delete on every run of that skill, quietly, as part of
    #: "verifying" it. Refused at the one place the call is actually made
    #: rather than only at save time, because a skill stored before this
    #: existed reaches here without passing `skills.normalise` again.
    if name in tools.WRITE_TOOLS:
        return None, f"{name} changes things, so it cannot check anything"
    try:
        #: The block's own arguments, which are a *scope* and nothing else
        #: (`skills._verify_args`): "how many untagged notes are there" rather
        #: than "how many notes are there". They only ever narrow a reading, so
        #: the paragraph above still holds: a verifier cannot change what it
        #: checks.
        result = tools.execute_tool(session, name, dict(block.get("args") or {}))
    except Exception as exc:  # noqa: BLE001  # a broken check must not break the run
        logger.warning("couldn't run the verifier tool %s", name, exc_info=True)
        return None, f"{name} could not be run ({exc})"
    if not isinstance(result, dict) or "error" in result:
        return None, f"{name} answered with an error"
    named = block.get("field")
    keys = [named] if named else list(skills.VERIFY_COUNT_FIELDS)
    for key in keys:
        value = result.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value, ""
    return None, f"{name} returned no number to check ({', '.join(str(k) for k in keys)})"


def verify(
    session: Session,
    skill: dict,
    before: int | None,
    stopped_reason: str,
) -> Verification:
    """The run's own postcondition, checked against the notebook.

    `stopped_reason` is "" for a run that reached the end. Anything else short
    circuits: there is no point reading a count back out of a notebook a run
    never finished working on, and a `min` that happens to hold over a run
    that stopped at step two is a pass nobody should be shown.
    """
    block = skill.get("verify") or None
    if stopped_reason:
        return Verification(False, stopped_reason, tool=(block or {}).get("tool", ""))
    if not block:
        # No declared postcondition. The honest verification of a skill that
        # promised nothing specific is that every step it does have finished:
        # which, at this point, is true.
        return Verification(True, "every step finished")
    got, why = _reading(session, block)
    if got is None:
        return Verification(False, why, tool=block["tool"], field=block.get("field") or "")
    failures = [
        name
        for name, want in block["expect"].items()
        if not PREDICATES[name](got, want, before)
    ]
    #: The scope goes in the line the user reads, because "count_notes came
    #: back 12" and "count_notes(untagged) came back 12" are different claims
    #: and only one of them is what this skill promised.
    scope = ", ".join(
        name if value is True else f"{name}={value}"
        for name, value in (block.get("args") or {}).items()
    )
    where = (
        f"{block['tool']}{f'({scope})' if scope else ''}"
        f"{'.' + block['field'] if block.get('field') else ''}"
    )
    if failures:
        wanted = ", ".join(f"{name} {block['expect'][name]}" for name in failures)
        return Verification(
            False,
            f"{where} came back {got}, and this skill expects {wanted}",
            tool=block["tool"],
            field=block.get("field") or "",
            expect=block["expect"],
            got=got,
            before=before,
        )
    return Verification(
        True,
        f"{where} came back {got}, as this skill expects",
        tool=block["tool"],
        field=block.get("field") or "",
        expect=block["expect"],
        got=got,
        before=before,
    )


def _record_run(
    session: Session,
    skill: dict,
    changes: list[dict],
    stopped_at: int | None,
    steps: int,
    paused: bool,
) -> None:
    """Write one audit row for a finished skill run.

    **Nothing in this app ever wrote one, and the Library's AI Skills tab has
    a log panel that reads them.** Reported as "I dont think the skill logs
    work in the ai skills section in the library??", correct, and not because
    the panel was broken: `renderSkillLogs` filters `/audit` for
    `entity_type === "skill"`, and a grep for a `log_action` call with that
    entity type returns nothing at all. The panel could only ever say "No
    skill execution logs found". The "features that never ran once" shape from
    CLAUDE.md, one layer down: the reader ran, and the writer did not exist.

    Best-effort and never raises: a run that did real work must not fail at
    the last line over its own bookkeeping. Committed here rather than left to
    the caller, because the caller is a streaming route whose session may be
    closed by the time the generator is exhausted.
    """
    from tessellate.entry.manager import log_action

    outcome = (
        "paused"
        if paused
        else "completed"
        if stopped_at is None
        else f"stopped at step {stopped_at + 1}"
    )
    detail = f"{outcome} · {len(changes)} change(s)"
    if steps:
        detail = f"{outcome} · {steps} step(s) · {len(changes)} change(s)"
    try:
        log_action(
            session,
            "ran",
            "skill",
            None,
            f"{skill.get('name') or 'skill'}, {detail}",
            # The writes the run made are already attributed to the tool that
            # made them (`execute_tool`); this row is the run itself.
            actor=f"ai:{skill.get('name') or 'skill'}",
        )
        session.commit()
    except Exception:  # noqa: BLE001  # bookkeeping must not fail a finished run
        logger.warning("couldn't record the skill run", exc_info=True)
        session.rollback()


#: Event types that mean the turn handed over to somebody else rather than
#: finishing. `ask_user` is the one that reaches a skill run: it stops the turn
#: to put a question to the person, so the step is waiting rather than
#: unfinished, and neither the "nothing happened" branch nor a contract retry
#: should fire on it.
_HANDOVERS = frozenset({"ask", "confirm"})


def _unmet_reason(spec: dict) -> str:
    """One sentence naming the contract that was not met, for the step event.

    Phase D asks for "why did this stall?" in one sentence; this is that
    sentence, and it is written now because the information only exists here.
    """
    named = ", ".join(spec.get("tools") or [])
    if spec.get("expects") == "notes_changed":
        return (
            f"this step had to change something with {named} and nothing changed"
            if named
            else "this step had to change something and nothing changed"
        )
    if spec.get("expects") == "answer_only":
        return "this step had to answer in words and nothing was said"
    return (
        f"this step had to call {named} and it wasn't called"
        if named
        else "this step had to call a tool and none were called"
    )


#: How much of a tool's own result the carried state remembers. One line, so a
#: later step can see *what* the last call came back with without the whole
#: payload being resent on every round of every step after it.
STATE_RESULT_CHARS = 200

#: How many ids or tags the state tracks in total. The state line itself names
#: fewer (see `skills.MAX_STATE_IDS`); this is the ceiling on what a long run
#: accumulates in memory before it starts forgetting the oldest.
MAX_STATE_TRACKED = 40

#: How many note ids a run's `seen_ids` ledger holds (Brief 13). Deliberately
#: far larger than `MAX_STATE_TRACKED`, because the two answer different
#: questions: that one is "which notes is this run talking about", where a
#: forgotten oldest id costs a little precision, and this one is "how much of
#: the notebook has this run actually looked at", where forgetting is the
#: failure. Ints only, and nothing but the count reaches a prompt.
MAX_SEEN_TRACKED = 2000

#: **How many times one step may call its tool to page through a read.**
#: CHAT_PLAN decision 10's "up to N tool calls (default 6)". A step that has
#: paged this many times and still has pages left is reading something far
#: larger than a step was meant to cover; the run says so rather than spending
#: the rest of its budget on page seven.
MAX_PAGES_PER_STEP = 6

#: Argument names that carry tags. A name rule rather than a per-tool table for
#: the same reason `tools.call_example` builds itself from the schema: a tool
#: added later is covered without anyone remembering to come back here.
#:
#: `new` is deliberately **not** in this list, though `rename_tag(old, new)`
#: puts a tag there: `rename_category` has the same argument and puts a
#: category name in it, and this state is read back to the model as fact. A
#: tag that is missing costs a little precision; a category listed as a tag is
#: a wrong fact in the prompt, which is the more expensive of the two. See
#: `_tag_arguments` for the narrow case where `new` is read after all.
_TAG_ARGUMENT_KEYS = ("tags", "tag", "add")


def _tag_arguments(event: dict) -> tuple[str, ...]:
    """Which of a tool call's arguments name tags, for this particular call."""
    if "tag" in str(event.get("tool") or ""):
        # `rename_tag`, `delete_tag`, `tag_note`, the tag tools, where `new`
        # is a tag by definition.
        return (*_TAG_ARGUMENT_KEYS, "new")
    return _TAG_ARGUMENT_KEYS


def _remember(state: dict, key: str, value) -> None:
    """Add one value to a list in the state, keeping order and no duplicates."""
    seen = state.setdefault(key, [])
    if value in seen:
        return
    seen.append(value)
    if len(seen) > MAX_STATE_TRACKED:
        del seen[0]


def _absorb(state: dict, event: dict) -> None:
    """Fold one tool event into the run's structured state.

    **The third structural cause of the reported failure** (see this module's
    header and AGENT_SKILLS_REFORM.md): only prose used to cross a step
    boundary, so a step told to act on "those notes" got a sentence about them
    rather than their ids, and either re-searched, finding a different set , 
    or guessed. What a tool actually touched is already on the event, because
    the chat transcript needs it for the same reason; this keeps it.
    """
    if event.get("type") != "tool":
        return
    for item in event.get("touched") or []:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int):
            continue
        if item.get("kind") == "document":
            _remember(state, "document_ids", item["id"])
        else:
            _remember(state, "note_ids", item["id"])
    arguments = event.get("arguments")
    if isinstance(arguments, dict):
        for key in _tag_arguments(event):
            value = arguments.get(key)
            for tag in value if isinstance(value, list) else [value]:
                if isinstance(tag, str) and tag.strip():
                    _remember(state, "tags", tag.strip())
    if not event.get("ok"):
        # A failed call touched nothing and read nothing. Recording it as
        # "last tool run" would tell the next step a lie in one word.
        return
    # Every note this read returned, uncapped by the chip limit: the ledger a
    # paging step is judged against (`_pages_left`), and the one number the
    # state line carries so the model can tell page one from the whole
    # notebook.
    #
    # A list and a linear membership test rather than a set, deliberately:
    # the whole `state` dict is yielded on the `result` event and serialised
    # straight to NDJSON, and a set there is a `TypeError` at the last line of
    # a run that did everything right. Order is also what makes the ledger
    # readable. Two thousand ints against a page of twenty is nothing.
    ledger = state.setdefault("seen_ids", [])
    for note_id in event.get("seen") or []:
        if not isinstance(note_id, int) or note_id in ledger:
            continue
        if len(ledger) >= MAX_SEEN_TRACKED:
            break
        ledger.append(note_id)
    if event.get("tool"):
        state["last_tool"] = event["tool"]
    summary = event.get("result_summary")
    if isinstance(summary, str) and summary.strip():
        state["last_tool_result"] = summary[:STATE_RESULT_CHARS]


def _absorb_change(state: dict, change: dict) -> None:
    """The ids a *write* touched, kept apart from the ids a read merely saw."""
    for field, key in (("note_id", "note_ids"), ("document_id", "document_ids")):
        if isinstance(change.get(field), int):
            _remember(state, key, change[field])
            _remember(state, "touched", change[field])


def _pages_left(spec: dict, events: list[dict]) -> dict | None:
    """The unfinished page of a read this step made, or None if there is none.

    **CHAT_PLAN decision 10, the half `skill_runner` did not have**: *"a step
    loops until its contract is met, up to N tool calls, with paging handled
    inside the step"*. `list_notes` has always said there is more (`has_more`,
    `next_offset`, and a `note_to_model` spelling out the next call), and the
    runner never read any of it: one call satisfied `tool_called`, the step
    went green, and a "go through every note" step had seen twenty of seventy.

    Judged on the **last** call of the tool rather than on any of them,
    because that is what "have I reached the end" means: a model that paged
    four times has three results saying "more" and a fourth saying "that is
    all", and a rule reading "any" would keep a finished step open for ever.

    Only a tool the step's contract names counts. A step that declares no
    tools declares nothing about what it must read, and holding it open on an
    incidental `list_notes` would stall runs that work today, which is the
    same reason a plain string step has no contract at all.
    """
    named = set(spec.get("tools") or [])
    if not named:
        return None
    for event in reversed(events):
        if event.get("tool") not in named or not event.get("ok"):
            continue
        return event if event.get("more") else None
    return None


def _paging_nudge(event: dict, page: int, of: int) -> str:
    """Tell the model to fetch the next page, with the call already written.

    The same lever `skills.contract_nudge` pulls and for the same measured
    reason: a small model does not need the concept of pagination explained,
    it needs the next call spelled out. The offset comes from the tool's own
    result, so this cannot name a page that does not exist.
    """
    tool = event.get("tool") or "the tool"
    offset = event.get("next_offset")
    where = f" with offset={offset}" if isinstance(offset, int) else " for the next page"
    return (
        f"You have not seen all of them yet: `{tool}` said there is more. "
        f"Call `{tool}` again{where} and keep going until it says there is "
        f"no more. This is page {page} of at most {of}."
    )


def _contract_met(spec: dict, called: set[str], changed: list[dict], answer: str) -> bool:
    """Has this step done what it declared it would?

    The one judgement worth writing down here: a **failed** call still counts
    for `tool_called`. The contract is "you reached for the tool", and a model
    that called it and got an error is not the failure this exists to catch, 
    that model is already handled, by the recovery hints the agent loop feeds
    back and by the run's own "no answer and a failure" branch. Re-prompting
    it would spend two more rounds re-running the same broken call. What this
    catches is the model that wrote *about* the tool and never called it.
    """
    expects = spec.get("expects")
    if not expects:
        return True  # a plain string step: unchecked, exactly as before
    if expects == "answer_only":
        return bool(answer)
    #: **A change that may not be needed.** Words satisfy it, because "they
    #: all hold up" is a real answer to "unlink the ones that do not", and
    #: forcing a call here would fail every honest run with nothing to fix.
    #: What stops that being a licence to narrate is the transcript rather
    #: than the contract: the step says which of the two happened (see
    #: `no_change` where this is reported), so a step that changed nothing
    #: cannot read as one that did.
    if expects == "tool_optional":
        return bool(answer) or bool(called & set(spec.get("tools") or []))
    if expects == "notes_changed":
        return bool(changed)
    named = set(spec.get("tools") or [])
    return bool(called & named) if named else bool(called)


#: **How many times one run may re-plan a step that failed** (PLAN.md §4, A2:
#: "re-plans on a failed step (max 2)").
#:
#: The contract retries above (Phase A) re-send the *same* step with a nudge, 
#: they are for a model that narrated instead of calling. This is the level
#: above: a step that has genuinely failed or stalled is *rewritten* and tried
#: again, so a run bends rather than ending at the first bad step.
#:
#: **The step is rewritten in place, and the rest of the plan is not touched.**
#: That is a deliberate scope call, not a shortcut. `stopped_at` is an index
#: into the step list, and the client turns it into "Resume from step N" by
#: sending the *saved skill's* name back down `/chat/stream`, so a re-plan
#: that inserted, removed or reordered steps would leave `stopped_at` pointing
#: into a list nothing else has, and Resume would silently re-run the wrong
#: step, every one of which writes to the notebook. Rewriting one step keeps
#: every index, every `earlier` marker and Resume exactly as correct as they
#: were. What gets re-planned is *how* to do the step; what does not is the
#: shape of the job.
MAX_REPLANS = 2

REPLAN_PROMPT = (
    "You rewrite ONE step of a plan that has just failed, so it can be tried "
    "again. Reply with the rewritten step and nothing else: one short "
    "instruction, no numbering, no quotes, no explanation. Make it smaller "
    "and more literal than the one that failed, name the single thing to do."
)


def _fallback_replan(step_text: str, spec: dict) -> str:
    """The rewrite when the model cannot supply one.

    Deliberately still a rewrite rather than a bare retry: the step goes back
    with the tool it must call named inside it, which is the same lever the
    contract nudge pulls and the one that actually moves a small model. Kept
    inside `skills.MAX_STEP` so a re-planned step is still a step the plan
    card, the skill editor and a later `normalise` all accept.
    """
    tool = next(iter(spec.get("tools") or []), None)
    call = f" Call {tool} exactly once." if tool else " Do one thing only."
    return f"{step_text.rstrip('.')}.{call}"[: skills.MAX_STEP]


def _replan_step(
    model_manager: ModelManager,
    ollama: OllamaClient,
    skill: dict,
    values: dict | None,
    step_text: str,
    spec: dict,
    reason: str,
) -> str:
    """A rewritten version of one failed step. Never raises, never empty.

    Falls back to `_fallback_replan` on every failure path, offline, a
    transport error, an empty reply, a reply that came back as a paragraph, 
    for the same reason `followups.suggest_followups` returns `[]` on all of
    its: a run that stops because its own recovery could not reach the model
    is a worse outcome than one that retries with a mechanically improved
    instruction.
    """
    fallback = _fallback_replan(step_text, spec)
    if not ollama.is_running():
        return fallback
    named = ", ".join(spec.get("tools") or [])
    goal = skills.fill(skill.get("prompt") or "", skills.input_values(skill, values))
    try:
        reply = ollama.chat(
            model_manager.utility_model(),
            [
                {"role": "system", "content": REPLAN_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"The whole job: {goal[: skills.MAX_GOAL]}\n"
                        f"The step that failed: {step_text}\n"
                        f"What went wrong: {reason}\n"
                        + (f"It must call this tool: {named}\n" if named else "")
                        + "Rewrite the step."
                    ),
                },
            ],
        )
    except Exception:  # noqa: BLE001  # recovery must not itself end the run
        logger.warning("couldn't re-plan a failed step", exc_info=True)
        return fallback
    text = " ".join(str(reply.get("content") or "").split())
    # A model that answered with a paragraph, a refusal or an empty string has
    # not given a step. One line, and shorter than the cap a step is allowed
    # to be: otherwise the "rewrite" is a fresh wall of prose, which is the
    # failure this whole file exists to stop.
    if not text or len(text) > skills.MAX_STEP:
        return fallback
    return text


def _announce_early(run: _RunState, index: int, step: str, announced: bool) -> Iterator[dict]:
    """A later step says it is running before its model call, not after:
    Stop pressed between two steps then lands before the next step's first
    write (row 3; measured, "running" arrived with the step's first tool
    call). The first step still waits, so an unsupported model can fall back."""
    if run.started and not announced:
        yield {"type": "step", "index": index, "state": "running", "text": step}
        return True
    return announced


def _plan_step_tools(session: Session, skill: dict, steps: list[str]) -> list[list[str]]:
    """The tools each planned act step is offered (`_plan_step_offer`)."""
    return plan_writes.plan_tools(session, steps, agent.plan_now()) if skill.get("kind") == "plan" else []


def _plan_step_offer(setup: _RunSetup, index: int, offered: list[str] | None) -> list[str] | None:
    """A planned act step is offered the writes its plan was approved with
    (`plan_writes.step_tools`); anything else keeps what it had."""
    named = (setup.plan.get("step_tools") or [])[index:index + 1]
    return named[0] if offered is None and named and named[0] else offered


def _step_tools(spec: dict, allowed: list[str] | None, small_model: bool) -> list[str] | None:
    """Which tools this one step is offered.

    Ordinarily the skill's whole allowlist, which is already narrow. In
    small-model mode it is **only what the step's contract names**: Phase B:
    a 4B model handed five schemas for a step that needs one picks the wrong
    one often enough to be the reported failure, and every schema not sent is
    room the notes and the question get back. Falls back to the skill's list
    when the step names nothing, because offering no tools at all would make a
    `tool_called` contract impossible to meet.
    """
    if not small_model:
        return allowed
    named = [name for name in (spec.get("tools") or []) if allowed is None or name in allowed]
    return named or allowed


def run_skill(
    session: Session,
    skill: dict,
    values: dict | None,
    notes: list[dict],
    model_manager: ModelManager,
    ollama: OllamaClient,
    budget: run_budget.RunBudget | None = None,
    **kwargs,
) -> Iterator[dict]:
    """`_run_skill`, with the run's budget open around the whole of it.

    A thin wrapper rather than a `with` inside the body, because the body is
    four hundred lines and re-indenting it would bury this change in a diff
    nobody could review. The scope is what makes the budget true of every
    model call the run makes, including the ones written later by somebody
    who has never read this file: see `ai/budget.py`.

    The scope is entered by the generator, so it is set while the run is
    executing and released when it is exhausted or closed. A `contextvar` set
    inside a generator is visible to its caller between yields, which is
    harmless here (the streaming route makes no model calls of its own) and is
    the same trade `core/events.acting_as` already makes.
    """
    spend = budget if budget is not None else run_budget.RunBudget()
    mark = _event_mark(session)
    with run_budget.spending(spend):
        inner = _run_skill(
            session, skill, values, notes, model_manager, ollama, budget=spend, **kwargs
        )
        try:
            for event in inner:
                if event.get("type") == "result":
                    span = _undo_span(session, mark)
                    if span:
                        event["undo_span"] = span
                yield event
        finally:
            # Stop closes this generator; the run's own must close with it,
            # now, as `yield from` did, not whenever it is collected.
            inner.close()


def _event_mark(session: Session) -> int:
    """The newest event id before a run starts (0 for an empty log)."""
    from sqlalchemy import func, select

    from tessellate.core.database import AuditLog

    return int(session.scalar(select(func.max(AuditLog.id))) or 0)


def _undo_span(session: Session, mark: int) -> dict | None:
    """**A skill run's own Undo** (AGENT_SKILLS_REFORM, placed 2026-10-05).
    Each tool call files its writes under `ai:<tool>@<model>`, so "what this
    run did" is the AI's writes between the run's first event and its last:
    their actors and that span, which `POST /events/undo` takes as one
    (`actors`, `since`, `until`). None when the run wrote nothing. A chat
    turn in another window writing in the same seconds would fall inside the
    span too; the plan the person confirms names every note it would touch."""
    from sqlalchemy import select

    from tessellate.core.database import AuditLog

    rows = session.execute(
        select(AuditLog.id, AuditLog.actor).where(
            AuditLog.id > mark,
            AuditLog.entity_id.is_not(None),
            AuditLog.actor.like("ai:%"),
        )
    ).all()
    if not rows:
        return None
    return {
        "since": mark,
        "until": max(row.id for row in rows),
        "actors": sorted({row.actor for row in rows}),
    }


@dataclass(slots=True)
class _RunSetup:
    """What a run decided before its first step, and never changes after.

    Thirteen values that used to be `_run_skill`'s parameters read off a
    closure. They are a record now for one reason: the per-step stage below is
    a module-level function rather than a closure, which is what let the step
    loop come out of a 682-line function (WORLD_CLASS_PLAN A5).
    """

    skill: dict
    values: dict | None
    #: One parsed contract per step, from `skills.step_specs`.
    specs: list[dict]
    #: The skill's declared tool allowlist, or None for the whole registry.
    allowed: list[str] | None
    small_model: bool
    manual: bool
    manual_note: str | None
    only_step: int | None
    resume_from: int
    #: The `plan` event, yielded lazily by whichever stage runs first.
    plan: dict
    #: One agent turn, bound to this run's notes, style, persona and history.
    turn: Callable[..., Iterator[dict]]
    model_manager: ModelManager
    ollama: OllamaClient


@dataclass(slots=True)
class _RunState:
    """What a run learns while it walks its steps.

    Every field here is read after the loop as well as inside it, which is why
    a step stage that only yielded events would not do: `stopped_at` becomes
    the Resume button, `paused` decides whether that button says Continue, and
    `truncated` is the difference between "I read your notes" and "I read the
    first two hundred of them".
    """

    #: **A copy of the skill's steps**, because re-planning rewrites one in
    #: place and `skill["steps"]` belongs to the caller: a built-in skill's
    #: list *is* the module-level catalogue's own list, so mutating it here
    #: would quietly rewrite that skill for every later run in the process.
    steps: list[str]
    #: The history each step's turn is given, one entry per finished step.
    step_history: list[dict]
    #: Every change the run has made, in order, shared with `_collect`.
    changes: list[dict]
    #: What the run knows so far, as ids rather than prose (`_absorb`).
    known: dict
    started: bool = False
    #: The index the run did not get past, None when it finished.
    stopped_at: int | None = None
    paused: bool = False
    replans: int = 0
    #: Did any step run out of pages before its read ran out of notes?
    truncated: bool = False
    #: The sentence explaining the stop, set the first time a step hits the
    #: run's budget. Read after the loop, several steps later, which is why it
    #: is a run-level string rather than a per-step flag.
    out_of_budget: str = ""


def _count_step() -> None:
    """Charge one step attempt to the run's budget (Phase E, decision 3)."""
    spend = run_budget.current()
    if spend is not None:
        spend.count_step()


def _usage(spend: run_budget.RunBudget | None) -> dict | None:
    return spend.usage() if spend is not None else None


@dataclass
class _StepState:
    """One step's bookkeeping across its attempts, pages and re-plans."""

    index: int
    step: str
    spec: dict
    offered: list
    example: str | None
    attempts: int
    attempt: int = 1
    #: Pages fetched so far, counted apart from `attempt` on purpose: paging is
    #: the step *working*, and spending a contract retry on it would end a step
    #: that is doing exactly what it was asked to.
    pages: int = 1
    #: Set when the step ran out of pages before the read ran out of notes.
    truncated: str = ""
    announced: bool = False
    nudge: str | None = None
    #: "done", "failed", "stalled", or "abort" (the model cannot use tools and
    #: nothing has been shown yet); None while the step is still being tried.
    outcome: str | None = None
    #: Whether the way this step ended is worth re-planning at all, and the one
    #: sentence saying what went wrong: the material `_replan_step` gives the
    #: model, and the reason the `replanned` event carries.
    replannable: bool = True
    fail_reason: str = ""


@dataclass
class _Seen:
    """What one turn of a step did, read off its events."""

    #: Where this step's own changes start in the run's running list, so they
    #: can be told apart from every earlier step's (see _step_answer and the
    #: `notes_changed` contract).
    changes_before: int
    said: list[str] = dc_field(default_factory=list)
    failures: list[str] = dc_field(default_factory=list)
    ran_out: bool = False
    called: set[str] = dc_field(default_factory=set)
    #: Every tool event of the turn, in order, so the paging check can ask what
    #: the *last* call of the step's own tool came back with.
    tool_events: list[dict] = dc_field(default_factory=list)
    ran_any_tool: bool = False
    handed_over: bool = False
    went_offline: bool = False


def _begin_step(setup: _RunSetup, index: int, step: str) -> _StepState:
    spec = setup.specs[index]
    offered = _plan_step_offer(setup, index, _step_tools(spec, setup.allowed, setup.small_model))
    example = tools.call_example(spec["tools"][0]) if setup.small_model and spec.get("tools") else None
    attempts = spec.get("retries", skills.DEFAULT_STEP_RETRIES) + 1
    return _StepState(index=index, step=step, spec=spec, offered=offered, example=example, attempts=attempts)


def _turn_instruction(setup: _RunSetup, run: _RunState, st: _StepState) -> str:
    instruction = skills.step_instruction(
        setup.skill, setup.values, st.index, state=run.known, only_tools=st.offered, example=st.example
    )
    # Folded into the instruction, not appended to `step_history`: this is what
    # the user is asking for as part of *this* step, not a fact about an
    # earlier one, and a history entry is something the model may or may not
    # weigh against everything else in the window.
    if setup.manual_note and st.index == setup.resume_from:
        instruction = f"Before this step, the person running this added: “{setup.manual_note}”\n\n{instruction}"
    if st.nudge:
        # First, and on its own line: this is a correction, and a correction
        # buried under three paragraphs of restated context is one a small
        # model reads as more context.
        instruction = f"{st.nudge}\n\n{instruction}"
    return instruction


def _halt(run: _RunState, st: _StepState, state: str, reason: str, fail_reason: str = "", replannable: bool = True) -> dict:
    """End the step as `failed` or `stalled`: the event to show, with the run's
    `stopped_at` (what Resume picks up from) and the re-plan inputs set."""
    run.stopped_at = st.index
    st.replannable = replannable
    if fail_reason:
        st.fail_reason = fail_reason
    st.outcome = state
    return {"type": "step", "index": st.index, "state": state, "text": st.step, "reason": reason}


def _open_turn(setup: _RunSetup, run: _RunState, st: _StepState):
    """Start one model turn. Returns its events, or None when the step ended
    before it began (the model cannot use tools)."""
    instruction = _turn_instruction(setup, run, st)
    st.announced = yield from _announce_early(run, st.index, st.step, st.announced)
    events = setup.turn(
        instruction,
        run.step_history,
        f"I couldn't finish step {st.index + 1}: I used every round it had without reaching an answer.",
        st.offered,
    )
    first = next(events, None)
    if first is not None and first.get("type") == "unsupported":
        if not run.started:
            # Nothing has been shown yet, so the caller can still fall back to
            # a plain answer. Once a step has run, it cannot. An explicit stop
            # (outcome "abort"), not a bare return: a None would run this same
            # step again for ever (CodeQL, mixed implicit and explicit returns).
            st.outcome = "abort"
            yield first
            return None
        # INBOX 272 part 1: `first["message"]` (set once, in ai/agent.py)
        # already names the remedy; only an older event shape (or a test
        # double) falls back to the bare fact. Not re-plannable: no rewording
        # of a step gives a model back the ability to call tools.
        reason = first.get("message") or "The model stopped being able to use tools part-way through."
        yield _halt(run, st, "failed", reason, replannable=False)
        return None
    if not run.started:
        yield setup.plan
        run.started = True
    if not st.announced:
        st.announced = True
        yield {"type": "step", "index": st.index, "state": "running", "text": st.step}
    return chain([first], events) if first else events


def _note_event(seen: _Seen, run: _RunState, event: dict) -> None:
    kind = event["type"]
    if kind == "answer":
        seen.said.append(event["delta"])
        if event.get("offline"):
            seen.went_offline = True
    elif kind == "tool":
        seen.ran_any_tool = True
        seen.tool_events.append(event)
        if event.get("tool"):
            seen.called.add(event["tool"])
        if not event.get("ok"):
            seen.failures.append(str(event.get("error") or event.get("label")))
    elif kind == "limit":
        # The step used every round it had and was still calling tools.
        # Whatever it says next is a stopping notice, not the step's result.
        seen.ran_out = True
        #: **A budget stop is not a rounds stop.** Out of rounds means "this
        #: step is bigger than a step": Resume it, split it, try again. Out of
        #: budget means the *run* is over, so re-planning this step would spend
        #: rounds the run does not have on a call that would be refused.
        if event.get("reason") == "budget":
            run.out_of_budget = str(event.get("detail") or "the run's budget ran out")
    elif kind in _HANDOVERS:
        # `ask_user` ends the turn by handing the question to the person. It
        # never reaches here as a tool event, so a contract check would see a
        # step that called nothing and re-prompt a model that is correctly
        # waiting for an answer only the user can give.
        seen.handed_over = True


def _observe_turn(run: _RunState, source) -> Iterator[dict]:  # noqa: ANN001
    seen = _Seen(changes_before=len(run.changes))
    for event in _collect(source, run.changes, run.known):
        _note_event(seen, run, event)
        yield event
    return seen


_OFFLINE_REASON = "Ollama isn't reachable: check Settings → Models and try again."
_RAN_OUT_REASON = "ran out of rounds before finishing, Resume continues from here, or split this step into two smaller ones"
#: **Say what to do about it, not only what happened.** Reported: *"skills are
#: too hard for small ais and things go wrong often."* One empty turn from a
#: small model is the most common way a run stops, and it usually passes on the
#: next attempt, which the Resume button already does from this step.
_SAID_NOTHING_REASON = (
    "the model didn't respond: no answer and no tool call. "
    "Resume picks up from this step; a smaller model often "
    "gets it on the second attempt, and Manual mode lets you "
    "steer each step."
)


def _stop_reason(run: _RunState, seen: _Seen, answer: str):
    """(state, reason, fail_reason, replannable) when the turn ended the step
    outright, else None. The order is load-bearing."""
    if seen.went_offline:
        # **Tier 1 section 3.** Ollama died mid-round, and the agent's own
        # answer for that is a real sentence of prose, which used to satisfy the
        # "did this step say something" check and get ticked done; the run then
        # repeated the identical failure on every later step. Not retried: the
        # notebook will not come back online between two attempts a second
        # apart, and the re-plan call would need the model that went away.
        return "failed", _OFFLINE_REASON, "", False
    if run.out_of_budget:
        #: Checked before `ran_out`, which a budget stop also sets: the two
        #: arrive together and only one of them is the reason. Nothing to
        #: re-plan: a rewritten step is not a cheaper one, it is another turn.
        return "stalled", run.out_of_budget, "", False
    if seen.ran_out:
        # **Stalled, not done.** The runner could only see that the turn
        # produced text, and the "I ran out of rounds" notice is text, so a step
        # cut off mid-job was ticked green and the next ran on half-finished
        # work. `stopped_at` is what Resume picks up from.
        #
        # **Not re-plannable, and this is the sharpest line in the mechanism.**
        # A step that ran out of rounds was *doing the job* and got cut off;
        # rewritten and run again, the model has no context about what it
        # already tagged, answers in prose, and the step goes green over a job
        # still half finished (`tests/test_long_runs.py` catches it). The honest
        # ending is stop, and let Resume carry on with the notebook as it stands.
        return "stalled", _RAN_OUT_REASON, "it used every round it had without finishing", False
    # A step that ran no tools and said nothing did not happen. Anything else is
    # reported as done: the model's own words are the record, and calling a step
    # failed because a tool errored mid-way would be wrong when it recovered.
    if not answer and seen.failures:
        return "failed", seen.failures[-1], f"a tool failed: {seen.failures[-1]}", True
    # **The other half of the reported bug.** A turn can end with no answer, no
    # tool call and no failure at all, which fell straight through to "done" and
    # made the skill's progress list lie. Deliberately *not* folded into the
    # contract retry: this is a model that produced nothing, not one that did the
    # wrong thing, and the two want different words.
    if not answer and not seen.ran_any_tool and not seen.handed_over:
        return "failed", _SAID_NOTHING_REASON, "the model said nothing and called no tool", True
    return None


def _truncation_note(run: _RunState) -> str:
    return (
        f"stopped after {MAX_PAGES_PER_STEP} pages with more left "
        f"to read; {len(run.known.get('seen_ids') or [])} notes were seen"
    )


def _done_event(st: _StepState, step_changes: list[dict], called: set[str]) -> dict:
    #: What the step wrote, each with its Undo, drawn under the step when it
    #: ticks (AGENT_SKILLS_REFORM "Deepened 2026-10-10" row 3).
    done: dict = {"type": "step", "index": st.index, "state": "done", "text": st.step, "changes": step_changes}
    #: **A step that could have changed something and did not says so.** Nine
    #: shipped steps name a tool and declare `answer_only`, so a model that
    #: writes "I used unlink_notes..." without calling anything would tick the
    #: step green over an untouched notebook. The contract cannot forbid that
    #: without failing every honest run with nothing to fix, so `no_change` is
    #: drawn as a caveat on the row instead.
    if st.spec.get("expects") == "tool_optional" and not (set(st.spec.get("tools") or []) & called):
        done["no_change"] = True
        done["reason"] = "nothing was changed in this step"
    if st.truncated:
        done["reason"] = st.truncated
        done["truncated"] = True
    return done


def _judge_turn(run: _RunState, st: _StepState, seen: _Seen) -> Iterator[dict]:
    """Decide what the turn means for the step: sets `st.outcome` when the step
    is over, and leaves it None when the step is to be tried again."""
    answer = "".join(seen.said).strip()
    step_changes = run.changes[seen.changes_before :]
    stop = _stop_reason(run, seen, answer)
    if stop is not None:
        state, reason, fail_reason, replannable = stop
        yield _halt(run, st, state, reason, fail_reason, replannable)
        return
    #: **More pages to read: the step is not over** (CHAT_PLAN decision 10).
    #: Checked before the contract because the two say different things: the
    #: contract is "you never reached for the tool", this is "you reached for it
    #: and stopped a quarter of the way through". The event says `paging`, as
    #: `retrying` does, because what the person watches is progress, not a fault.
    page = None if seen.handed_over else _pages_left(st.spec, seen.tool_events)
    if page is not None and st.pages < MAX_PAGES_PER_STEP:
        st.pages += 1
        st.nudge = _paging_nudge(page, st.pages, MAX_PAGES_PER_STEP)
        yield {
            "type": "step",
            "index": st.index,
            "state": "paging",
            "text": st.step,
            "page": st.pages,
            "of": MAX_PAGES_PER_STEP,
            "seen": len(run.known.get("seen_ids") or []),
        }
        return
    #: **Out of pages with more still to read.** Said out loud three times: on
    #: the step event, in the step's history so the next step knows, and through
    #: `result.truncated` so the run does not report a partial pass as complete.
    if page is not None:
        run.truncated = True
        st.truncated = _truncation_note(run)
    if seen.handed_over or _contract_met(st.spec, seen.called, step_changes, answer):
        yield _done_event(st, step_changes, seen.called)
        run.step_history.append({"question": st.step, "answer": _step_answer(answer, step_changes, st.truncated)})
        st.outcome = "done"
        return
    if st.attempt < st.attempts:
        # **Re-prompted, not skipped.** A small model that narrated the step
        # instead of doing it is told, literally, which call to make; the UI
        # shows it retrying rather than ticked.
        st.attempt += 1
        st.nudge = skills.contract_nudge(st.spec, st.attempt, st.attempts)
        yield {
            "type": "step",
            "index": st.index,
            "state": "retrying",
            "text": st.step,
            "attempt": st.attempt,
            "of": st.attempts,
            "reason": _unmet_reason(st.spec),
        }
        return
    # Out of attempts. Stalled: never `done`, which is the whole point.
    reason = (
        f"{_unmet_reason(st.spec)} after {st.attempts} attempt(s). Resume "
        "continues from here: or, if there was genuinely nothing "
        "to do in this step, skip past it by resuming from the next."
    )
    yield _halt(run, st, "stalled", reason, _unmet_reason(st.spec))


def _replan_or_stop(setup: _RunSetup, run: _RunState, st: _StepState) -> Iterator[dict]:
    #: **Re-plan, then try the step again** (PLAN.md section 4 A2). Bounded by
    #: `MAX_REPLANS` per *run*, not per step: two rewrites is where a run that
    #: keeps failing is telling you something about the job rather than the
    #: wording, and an unbounded loop would be a model rewriting its own
    #: instructions forever over a notebook it cannot act on.
    if not (st.replannable and run.replans < MAX_REPLANS):
        return "stop"
    run.replans += 1
    revised = _replan_step(setup.model_manager, setup.ollama, setup.skill, setup.values, st.step, st.spec, st.fail_reason)
    run.steps[st.index] = revised
    yield {
        "type": "step",
        "index": st.index,
        "state": "replanned",
        "text": revised,
        "attempt": run.replans,
        "of": MAX_REPLANS,
        "reason": st.fail_reason,
    }
    # It is no longer where the run stopped, it is about to be tried again, and
    # a `stopped_at` left behind would offer a Resume for a step still running.
    run.stopped_at = None
    return "again"


def _after_done(setup: _RunSetup, run: _RunState, index: int) -> str:
    # Manual mode: the same stop-and-resume machinery `stopped_at` already gives
    # a failed/stalled step, used deliberately here instead of a second
    # mechanism: the difference is only `paused`, so the client can render
    # "waiting for you" rather than "something broke". Nothing to pause for
    # after the last step; that's just the run ending.
    #
    # **One step, and then stop** (`only_step`) is reported as a pause for the
    # same reason: the person asked for this step and got it, and the rest of
    # the skill is still there to carry on with.
    if (setup.manual or setup.only_step is not None) and index + 1 < len(run.steps):
        run.stopped_at = index + 1
        run.paused = True
        return "stop"
    return "stop" if setup.only_step is not None else "next"


def _run_one_step(setup: _RunSetup, run: _RunState, index: int) -> Iterator[dict]:
    """One step of a run: its attempts, its contract, and what to do next.

    Yields the same events `_run_skill` yields, and **returns the loop's next
    move**: "next" to advance, "again" to run this index again (a re-planned
    step, which is the whole reason that loop is a `while` and not a `for`),
    "stop" to end the run where it is. A return value rather than a raised
    signal because all three are ordinary outcomes; the caller reads as the
    three-line loop it always was.

    Lifted whole out of `_run_skill` with no behaviour change
    (WORLD_CLASS_PLAN A5). The order of the checks inside is load-bearing and
    each one's comment says why it is where it is.
    """
    step = run.steps[index]
    _count_step()
    st = _begin_step(setup, index, step)
    while st.outcome is None:
        source = yield from _open_turn(setup, run, st)
        if source is None:
            break
        seen = yield from _observe_turn(run, source)
        yield from _judge_turn(run, st, seen)
    if st.outcome == "abort":
        return "stop"
    if st.outcome != "done":
        return (yield from _replan_or_stop(setup, run, st))
    return _after_done(setup, run, index)


def _run_skill(
    session: Session,
    skill: dict,
    values: dict | None,
    notes: list[dict],
    model_manager: ModelManager,
    ollama: OllamaClient,
    style: str = "friendly",
    profile: str = "",
    history: list[dict] | None = None,
    persona_prompt: str | None = None,
    start_at: int = 0,
    only_step: int | None = None,
    step_text: str | None = None,
    manual: bool = False,
    manual_note: str | None = None,
    small_model: bool | None = None,
    budget: run_budget.RunBudget | None = None,
) -> Iterator[dict]:
    """Yields the agent's own event types, plus three of its own:

    {"type": "plan", "skill", "steps", "step_specs", "tools", "small_model"}
                                                    - before anything runs
    {"type": "step", "index", "state", "text"}, running | retrying | done
                                                      | failed | stalled
                                                      | earlier
    {"type": "result", "changes": [...], "stopped_at": int|None, "paused": bool,
     "state": {...}}, what actually changed,
                                                      where it stopped, and the
                                                      ids the run gathered

    The first event is either "unsupported" (the model can't call tools, so
    the caller should fall back to plain Q&A) or "plan", the same contract
    `run_agent` has, so the route's fallback works unchanged.

    `start_at` resumes: steps before it are marked `earlier` and not re-run.
    That is the answer to "it cuts out half way through and has to restart", 
    restarting a six-step run to reach step four means doing steps one to three
    again, and every one of them writes to the notebook.

    `manual` is the other half of that same request, asked for directly and
    explicitly, and never built until now: **"skills producing network
    errors, or models that cannot run them" and "a manual mode"**, a pause
    after every completed step with a Continue button, so a person can add
    what the agent missed or answer a question it raised before the next
    step starts, rather than the run barrelling on regardless. Reuses the
    exact same stop-and-resume machinery `start_at` already has for a
    failure: a pause is not a new code path, it's the same one with
    `result.paused = True` so the caller can tell "stopped because it's
    waiting for you" from "stopped because something went wrong" and render
    each one differently. `manual_note` is what the user typed at that
    pause; folded into the very next step's own instruction (not into
    history, which the model may or may not weigh, this is read as part of
    what it's being asked to do right now).

    `small_model` is Phase B of the skills reform: one tool per step and a
    worked example of the call. None means "decide from the model", which is
    read off the chat model's own name: see `model_manager.parameter_count`,
    and note that an unrecognised name means *off*.

    **The step contract is Phase A**, and it is the difference between this
    and what was here before: a step is over when its declared condition is
    met, not when the model stops emitting. A step that has not met it is
    re-prompted with a nudge naming the tool, up to its own `retries`, and
    only then marked `stalled`. It is never silently `done`, that was the
    reported bug, and the reason a run "ran no tools" and still ticked green.
    """
    #: **The reading the verifier compares against, taken before any step
    #: runs.** `unchanged` is the postcondition of every read-only skill in
    #: the catalogue, and it is a claim about two numbers rather than one, so
    #: the first has to be taken while the claim is still true by definition.
    #: One extra tool call per run that declares a verify block, and none at
    #: all for one that does not.
    before_reading: int | None = None
    if skill.get("verify"):
        before_reading, _why = _reading(session, skill["verify"])
    steps = skill.get("steps") or []
    specs = skills.step_specs(skill)
    #: **Run one step, optionally reworded** (AGENT_SKILLS_REFORM.md Phase D:
    #: "edit a step's text and re-run just that step"). The other two thirds of
    #: recovery were already here, `start_at` resumes and `_unmet_reason` says
    #: in one sentence which contract was not met, and this is the third: a run
    #: that stalled on step 4 because the step was written for a bigger model
    #: is fixed by rewriting step 4, and the only way to find out whether the
    #: rewrite works was to run the whole skill again, every earlier step of
    #: which writes to the notebook.
    #:
    #: The text is overridden here rather than in the caller so the `plan` event
    #: below carries the step that is actually about to run: a plan card
    #: showing the old wording beside a step running the new one is the drift
    #: this reform exists to stop. The step's *contract* is untouched, which is
    #: the point of separating the two: rewording an instruction must not
    #: quietly drop the condition it has to meet.
    if only_step is not None:
        only_step = min(max(0, only_step), len(steps) - 1) if steps else None
    if only_step is not None and step_text:
        steps = list(steps)
        steps[only_step] = step_text
        specs = list(specs)
        specs[only_step] = {**specs[only_step], "text": step_text}
        skill = {**skill, "steps": steps, "step_specs": specs}
    allowed = skill.get("tools") or None
    if small_model is None:
        # "Auto": the model's own name is the only size hint available before a
        # request is made, and it is free. `chat_model_is_small` answers None
        # when the name says nothing, and None means off, narrowing a capable
        # model's toolbox on a guess is the worse mistake of the two.
        small_model = bool(model_manager.chat_model_is_small())
    plan = {
        "type": "plan",
        "skill": skill["name"],
        # Strings, for ever: `plan.steps` is rendered straight into `<li>`
        # textContent by the frontend, so anything else here is a plan card
        # full of "[object Object]". The contracts travel beside it.
        "steps": steps,
        "step_specs": specs,
        "tools": skill.get("tools") or [],
        "small_model": bool(small_model),
        # Which shape of run this is, so the UI can title it. A saved skill and
        # a plan the model drew for one request (§35K) both run through here.
        "kind": skill.get("kind") or "skill",
        #: Where this run actually begins, which a single-step re-run moves
        #: (Phase D): the plan card draws its earlier steps from this, so a
        #: card that read 0 while the run started at step 2 would show two
        #: steps as pending that were never going to run.
        "start_at": only_step if only_step is not None else max(0, start_at),
        #: Each step's writes, listed before the first runs (row 3).
        "writes": agent._plan_writes(session, steps),
        "step_tools": _plan_step_tools(session, skill, steps),
    }
    changes: list[dict] = []
    # What the run knows so far, as ids rather than as prose, carried into
    # every later step's instruction and returned with the result.
    state: dict = {}

    def turn(
        question: str,
        turn_history: list[dict],
        note: str | None,
        offered: list[str] | None = allowed,
    ) -> Iterator[dict]:
        return agent.run_agent(
            session,
            question,
            notes,
            model_manager,
            ollama,
            style=style,
            profile=profile,
            history=turn_history,
            persona_prompt=persona_prompt,
            allowed_tools=offered,
            # A run may not start another run. A skill that *declares* its
            # tools is already safe (`skills.NEVER_IN_A_SKILL` refuses these at
            # save time), but a skill with no allowlist, and every ad-hoc plan
            #, is offered the whole registry, `make_plan` included. A plan
            # step that plans again would nest runs with fresh rounds each.
            blocked_tools=tools.RUN_STARTERS,
            max_rounds=STEP_ROUNDS if steps else agent.MAX_ROUNDS,
            earned_rounds=STEP_EARNED_ROUNDS if steps else agent.EARNED_ROUNDS,
            exhausted_note=note,
            # The run draws its own card; a step's rounds are not a second one.
            show_plan=False,
        )

    if not steps:
        # No steps declared: one turn on the whole instruction, as before.
        events = turn(skills.run_instruction(skill, values), list(history or []), None)
        first = next(events, None)
        if first is None:
            yield plan
            return
        if first.get("type") == "unsupported":
            yield first
            return
        yield plan
        for event in _collect(chain([first], events), changes, state):
            yield event
        # No steps to resume from, so no `stopped_at`: a stepless skill is one
        # turn, and re-running it is the only way to continue it. The turn's
        # own `limit` event is still there, and the chat's Continue button
        # reads that.
        # One turn, so the only way it can have stopped early is the budget;
        # `_collect` has already passed the `limit` event through to the
        # caller, and the verification is what says so in the result.
        spent_out = bool(budget and budget.stopped)
        checked = verify(session, skill, before_reading, budget.stopped if spent_out else "")
        yield checked.as_event()
        _record_run(session, skill, changes, None, 0, False)
        yield {
            "type": "result",
            "changes": changes,
            "stopped_at": None,
            "steps": 0,
            "paused": False,
            "truncated": False,
            "stopped_by": "budget" if spent_out else "",
            "verification": checked.as_event(),
            "undo_available": all(change.get("undo") for change in changes),
            "state": state,
            "budget": _usage(budget),
        }
        return

    #: A single-step run starts at that step, whatever `start_at` said: the two
    #: are the same mechanism and naming a step is the more specific request.
    resume_from = only_step if only_step is not None else min(max(0, start_at), len(steps))
    setup = _RunSetup(
        skill=skill,
        values=values,
        specs=specs,
        allowed=allowed,
        small_model=small_model,
        manual=manual,
        manual_note=manual_note,
        only_step=only_step,
        resume_from=resume_from,
        plan=plan,
        turn=turn,
        model_manager=model_manager,
        ollama=ollama,
    )
    run = _RunState(
        steps=list(steps),
        step_history=list(history or []),
        changes=changes,
        known=state,
    )
    for index in range(resume_from):
        # Done in the run this one is resuming, so it is neither re-run nor
        # claimed as this run's work. The plan card shows it ticked in a
        # quieter state, because a step somebody watched succeed ten
        # minutes ago is not the same as one this run just did.
        if not run.started:
            yield plan
            run.started = True
        yield {"type": "step", "index": index, "state": "earlier", "text": run.steps[index]}
    index = resume_from
    #: A `while`, not a `for`: a re-planned step is run again at the same
    #: index with new text, and "again" without advancing is what that is.
    while index < len(run.steps):
        move = yield from _run_one_step(setup, run, index)
        if move == "stop":
            break
        if move == "next":
            index += 1

    if not run.started:  # every step failed before producing anything
        yield plan
    #: **Why the run ended, in one word for the app and one sentence for the
    #: person.** `stopped_at` alone cannot tell a budget stop from a stalled
    #: step from a manual pause, and all three want a different button.
    stopped_by = (
        "budget"
        if run.out_of_budget
        else "paused"
        if run.paused
        else "step"
        if run.stopped_at is not None
        else ""
    )
    checked = verify(
        session,
        skill,
        before_reading,
        run.out_of_budget
        or (
            f"the run stopped at step {run.stopped_at + 1} of {len(run.steps)}, so its "
            "postcondition was not checked"
            if run.stopped_at is not None and not run.paused
            else "the run is paused part-way through, so its postcondition was "
            "not checked"
            if run.paused
            else ""
        ),
    )
    yield checked.as_event()
    _record_run(session, skill, run.changes, run.stopped_at, len(run.steps), run.paused)
    # `stopped_at` is the index the run did not get past, None when it
    # finished. The client turns it into "Resume from step N", which is the
    # difference between carrying on and doing the first half again. `paused`
    # tells it which reason: waiting for the user (manual mode) rather than a
    # failure: Resume becomes Continue, and it's not reported as an error.
    yield {
        "type": "result",
        "changes": run.changes,
        "stopped_at": run.stopped_at,
        "steps": len(run.steps),
        "paused": run.paused,
        # A step somewhere in this run stopped paging with more to read, so
        # the run saw part of the notebook rather than all of it.
        "truncated": run.truncated,
        # "" when the run reached the end; "budget", "paused" or "step"
        # otherwise. The `verification` is repeated here as well as on its own
        # event because a client that reads only the result (a replay, the
        # skill log) must not have to reconstruct it.
        "stopped_by": stopped_by,
        "verification": checked.as_event(),
        # Can everything this run did be put back? A run that changed nothing
        # trivially can; a change with no undo call beside it cannot, and that
        # is the one case where offering the button would be a lie.
        "undo_available": all(change.get("undo") for change in run.changes),
        # The ids the run gathered, so whatever picks it up next, a Resume, a
        # follow-up question, Phase C's run view: can talk about "those notes"
        # with the same precision the steps did.
        "state": run.known,
        # What the run spent against each cap (Phase E, decision 3), so a
        # budget stop names the cap it met and a finished run its headroom.
        "budget": _usage(budget),
    }


def _collect(events: Iterator[dict], changes: list[dict], state: dict) -> Iterator[dict]:
    """Pass events through, keeping the changes and the state for the result."""
    for event in events:
        if event.get("change"):
            changes.append(event["change"])
            _absorb_change(state, event["change"])
        _absorb(state, event)
        yield event
