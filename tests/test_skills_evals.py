"""AGENT_SKILLS_REFORM Phase D, judged by a real model rather than by a fake.

CLAUDE.md section 4 is the reason this file exists and the reason it is shaped
the way it is. Every other provider test in this project runs against a fake
transport, so the one thing none of them can say is how a real small model
behaves when the runner re-prompts it, resumes it, or hands it a reworded step.
Phase D's acceptance line is exactly that claim:

    A five-step built-in skill run against a small local model completes every
    step or reports precisely which contract failed: no step marked done
    without its contract met.

**How this stays out of everybody's way.** `scratchpad/llama-dev.sh serve`
prints two environment variables, TESSELLATE_EVALS_URL and
TESSELLATE_EVALS_MODEL. They are read here at import, while the module is being
collected, and without them every eval in it is skipped, so CI, the ordinary
suite and `scripts/gate.sh --full` never need a model, a binary or a network.
Nothing here imports the script or shells out to it: the seam is those two
strings and nothing else, and the last test in this file is what keeps it that
way. To run these:

    bash scratchpad/llama-dev.sh serve 8092      # prints the two exports
    export TESSELLATE_EVALS_URL=... TESSELLATE_EVALS_MODEL=...
    .venv/bin/python -m pytest -m evals tests/

**A set variable with nothing behind it is a failure, not a skip.** Setting
these says "I have a model and I want it judged". If the server is then not
answering, skipping would report green for work nobody did, which is the exact
dishonesty the rest of this file is written against. It fails, and names the
command that starts one.

**What a real model can and cannot make these tests assert.** The assertions
here are the runner's guarantees, which hold whatever the model says: a step is
never ticked without its contract, a stalled step carries one sentence naming
the contract it missed, a resume starts where it was asked to, a single-step
re-run runs one step and pauses. Whether a 1.5B model *succeeds* at the
notebook work is not a guarantee and is not asserted: that number belongs in a
report, not in a pass or fail.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests._repo_files import repo_files

ROOT = Path(__file__).resolve().parents[1]

#: Set by `scratchpad/llama-dev.sh serve`, and by nothing else. Read once, at
#: import, so the decision is made while the module is being collected and no
#: test ever touches the network to find out whether it can run.
EVALS_URL = os.environ.get("TESSELLATE_EVALS_URL", "").strip()
EVALS_MODEL = os.environ.get("TESSELLATE_EVALS_MODEL", "").strip()

#: Applied per test rather than to the module.
#:
#: `pytest.skip(allow_module_level=True)` was the first shape here and it is
#: the wrong one, for a reason the gate found rather than a matter of taste: a
#: module that collects nothing makes pytest exit 5 ("no tests ran"), and
#: `scripts/gate.sh --changed` selects exactly this file when it is the file
#: that changed, reads the 5 as a failure, and turns the gate red over a file
#: that is behaving correctly. The seam test below is collected either way,
#: which is what keeps the exit code honest; these four are marked `evals` so
#: `pytest -m evals` selects them and an ordinary run reports them skipped.
needs_a_model = pytest.mark.skipif(
    not (EVALS_URL and EVALS_MODEL),
    reason=(
        "no real model: run 'bash scratchpad/llama-dev.sh serve' and export "
        "TESSELLATE_EVALS_URL and TESSELLATE_EVALS_MODEL to run these"
    ),
)
#: The five-step built-in the acceptance line is written about. Its steps
#: declare all three contract kinds (`tool_called`, `notes_changed`,
#: `answer_only`), which is what makes it the one worth running.
SKILL = "Auto-tag my notes"

#: Enough notes for the skill to have something to do, few enough that a 1.5B
#: model on a CPU finishes a run in minutes rather than in an afternoon.
NOTES = 3


@pytest.fixture()
def real_model(app_state, fake_embeddings):
    """The app's own OpenAI-compatible client, pointed at the served model.

    `fake_embeddings` and not a real embedding model: semantic search is not
    what Phase D is about, and pulling a second model in would make every
    failure here ambiguous between the two.
    """
    from tessellate.ai.openai_client import OpenAICompatClient
    from tessellate.core import deps

    client = OpenAICompatClient(base_url=EVALS_URL)
    if not client.is_running():
        pytest.fail(
            f"TESSELLATE_EVALS_URL is {EVALS_URL} and nothing is answering "
            "there. Start one with: bash scratchpad/llama-dev.sh serve"
        )
    deps.override_ai(ollama=client)
    config = deps.get_config()
    config.set_preference("llm_provider", "openai")
    config.set_preference("llm_base_url", EVALS_URL)
    config.set_preference("chat_model", EVALS_MODEL)
    return client


@pytest.fixture()
def notebook(real_model):
    """A TestClient over a notebook of untagged notes, wired to that model."""
    from fastapi.testclient import TestClient

    from tessellate.api.app import create_app
    from tessellate.core import deps
    from tessellate.entry import manager

    with deps.get_db().session() as session:
        for index in range(NOTES):
            manager.create_entry(
                session,
                f"note {index}: chase up the invoice from the plumber",
                "Work",
                [],
            )
    return TestClient(create_app())


def _run(client, **body) -> list[dict]:
    """One skill run over `/chat/stream`, as the app itself runs one."""
    with client.stream(
        "POST", "/chat/stream", json={"question": SKILL, "skill": SKILL, **body}
    ) as response:
        assert response.status_code == 200
        return [json.loads(line) for line in response.iter_lines() if line]


def _steps(events: list[dict]) -> list[dict]:
    return [event for event in events if event.get("type") == "step"]


def _final_state(events: list[dict]) -> dict[int, dict]:
    """The last event each step index reached, which is its outcome.

    A step emits `running`, then perhaps `retrying` or `replanned`, then one of
    `done`, `stalled` or `failed`; only the last of those is what happened.
    """
    last: dict[int, dict] = {}
    for event in _steps(events):
        last[event["index"]] = event
    return last


def _tools_called(events: list[dict]) -> dict[int, set[str]]:
    """Which tools each step actually called, read off the same tool events
    the transcript draws, so this checks the run rather than the runner's
    private bookkeeping."""
    called: dict[int, set[str]] = {}
    index = -1
    for event in events:
        if event.get("type") == "step":
            index = event["index"]
        elif event.get("type") == "tool" and event.get("tool"):
            called.setdefault(index, set()).add(event["tool"])
    return called


@pytest.mark.evals
@needs_a_model
def test_no_step_is_ticked_without_its_contract(notebook):
    """The acceptance line, checked against what the run actually did.

    Step 1 and 3 expect `list_tags` and `get_note`; step 4 expects the
    notebook to have changed; step 5 expects words. A `done` on any of them
    with none of that behind it is the failure this whole reform exists to
    stop, and it is the failure a fake transport cannot produce, because a
    fake always says what it was scripted to say.
    """
    from tessellate.ai import skills, tools
    from tessellate.core import deps

    events = _run(notebook)
    outcomes = _final_state(events)
    assert outcomes, "the run produced no steps at all"
    called = _tools_called(events)

    catalog = skills.catalog(deps.get_config(), set(tools.TOOLS))
    skill = next(item for item in catalog if item["name"] == SKILL)
    specs = skills.step_specs(skill)
    assert len(specs) == 5, "this eval is written about the five-step built-in"

    for index, event in sorted(outcomes.items()):
        spec = specs[index]
        if event["state"] != "done":
            # An unfinished answer is fine, and is half of what the acceptance line asks
            # for. What is not fine is a step that stops without saying why.
            assert event.get("reason"), (
                f"step {index + 1} ended as {event['state']} with no reason; "
                "Phase D's whole point is that it says which contract failed"
            )
            continue
        if spec.get("expects") == "tool_called":
            wanted = set(spec.get("tools") or [])
            assert not wanted or (called.get(index, set()) & wanted), (
                f"step {index + 1} was ticked done, expects one of {sorted(wanted)}, "
                f"and called {sorted(called.get(index, set()))}"
            )


@pytest.mark.evals
@needs_a_model
def test_a_notes_changed_step_ticks_only_when_the_notebook_changed(notebook):
    """The one contract a model cannot talk its way past.

    Step 4 of this skill declares `notes_changed`. A small model narrating "I
    have tagged all three notes" is the report's own symptom, and the only
    honest judge of it is the notebook: if the step says done, tags exist.
    """
    from tessellate.core import deps
    from tessellate.core.database import Entry

    events = _run(notebook)
    outcomes = _final_state(events)
    step = outcomes.get(3)
    if step is None:
        # An earlier step stalled, which the test above has already judged on
        # its own terms. There is no notes_changed contract to report on, and
        # asserting one here would be a failure about a different step.
        pytest.skip(
            "the run stopped before step 4: "
            + ", ".join(
                f"step {index + 1} {event['state']}"
                for index, event in sorted(outcomes.items())
            )
        )

    with deps.get_db().session() as session:
        tagged = sum(1 for entry in session.query(Entry).all() if entry.tags)

    if step["state"] == "done":
        assert tagged > 0, (
            "step 4 declares notes_changed and was ticked done over a notebook "
            "where nothing is tagged"
        )
    else:
        assert "tag_note" in step.get("reason", ""), (
            "a stalled notes_changed step has to name the tool it wanted: "
            f"got {step.get('reason')!r}"
        )


@pytest.mark.evals
@needs_a_model
def test_a_resume_starts_where_it_was_asked_to(notebook):
    """Phase D's first recovery move, against a real model.

    `skill_from_step` is what the Resume control sends. The steps before it are
    marked `earlier` rather than re-run, which is the difference between
    resuming a run and running it again over a notebook the first attempt
    already wrote to.
    """
    events = _run(notebook, skill_from_step=4)
    outcomes = _final_state(events)
    assert {index: event["state"] for index, event in outcomes.items() if index < 4} == {
        0: "earlier",
        1: "earlier",
        2: "earlier",
        3: "earlier",
    }, f"steps before the resume point were not marked earlier: {outcomes}"
    assert 4 in outcomes and outcomes[4]["state"] != "earlier", (
        "the step resumed from did not run"
    )


@pytest.mark.evals
@needs_a_model
def test_one_reworded_step_runs_alone_and_the_run_pauses(notebook):
    """Phase D's third recovery move, against a real model.

    A step written for a bigger model is fixed by rewording it, and the point
    of `skill_only_step` is to find out whether the rewording worked without
    re-running the four steps that write to the notebook. Three things have to
    hold: only that step runs, the model is given the new wording rather than
    the catalogue's, and the run reports as paused, because the rest of the
    skill is still there to carry on with.
    """
    reworded = "Call tag_note on note 1 with the tag invoices."
    events = _run(notebook, skill_only_step=3, skill_step_text=reworded)
    outcomes = _final_state(events)

    assert [outcomes[index]["state"] for index in range(3)] == ["earlier"] * 3
    # The step's *first* event, not its last. A step that misses its contract
    # is re-planned, and the `replanned` event carries the model's own rewrite
    # of the instruction, so the last event for this index is often neither the
    # catalogue's wording nor ours. That is the re-plan working; what has to be
    # true is that the step the run opened with is the one the person typed.
    opened = next(
        event
        for event in _steps(events)
        if event["index"] == 3 and event["state"] == "running"
    )
    assert opened["text"] == reworded, (
        "the step that ran was drawn with the catalogue's wording, not the "
        "rewrite: a card showing one instruction beside a step running another "
        "is the drift this reform exists to stop"
    )
    assert 4 not in outcomes, "a single-step run carried on past its step"

    result = next(event for event in events if event.get("type") == "result")
    if outcomes[3]["state"] == "done":
        # The step did what it was reworded to do, so the run is waiting for
        # the person rather than broken, and Resume picks up at the next step.
        assert result["paused"] is True, "a finished single-step run is a pause"
        assert result["stopped_at"] == 4, (
            "the pause has to offer the next step, so Resume picks up after "
            f"the one that was re-run: got {result['stopped_at']}"
        )
    else:
        # The rewrite did not work either, which is a real answer and the
        # reason a person would run one step at a time in the first place.
        # What must still hold is that the run stopped *at* that step and said
        # why, rather than pausing over a step that did not happen.
        assert result["paused"] is False and result["stopped_at"] == 3, (
            "a stalled single-step run must stop at its own step, not pause "
            f"past it: {result['paused']}, {result['stopped_at']}"
        )
        assert outcomes[3].get("reason"), "and it must say which contract failed"


# --- Phase E: a success rate per skill, on the fixtures --------------------
#
# AGENT_SKILLS_REFORM decision 1. Every case in `tests/fixtures/skills/` runs
# on the eval model under small model mode and is scored pass, partial or fail
# with the step that failed (`tests/_skill_fixtures.py`). A skill marked
# `small_class` must pass all three (the plan's gate); the rest are reported,
# not asserted, because whether a 1.5B model *succeeds* at a nine-step job is
# a number for the table, not a guarantee. `TESSELLATE_EVALS_SKILLS` (comma
# separated names) narrows the set; `TESSELLATE_EVALS_RATES` names a file the
# table is written to, in `ai/data/skill_rates.json`'s shape, to copy in.

from tests import _skill_fixtures as fx  # noqa: E402

WANTED = {name.strip() for name in os.environ.get("TESSELLATE_EVALS_SKILLS", "").split(",") if name.strip()}
RATES_OUT = os.environ.get("TESSELLATE_EVALS_RATES", "").strip()
SKILL_FIXTURES = fx.load_all()
FIXTURE_CASES = [
    (name, case)
    for name, data in sorted(SKILL_FIXTURES.items())
    for case in data["cases"]
    if not WANTED or name in WANTED
]


def _record(name: str, report: dict) -> None:
    """Add one case to the rates file, recomputing that skill's row."""
    path = Path(RATES_OUT)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.setdefault("threshold", fx.SMALL_CLASS_BAR)
    small = data.setdefault("classes", {}).setdefault("small", {"model": EVALS_MODEL, "skills": {}})
    reports = data.setdefault("reports", {}).setdefault(name, [])
    reports[:] = [r for r in reports if r["case"] != report["case"]] + [report]
    small["skills"][name] = fx.rates(reports)
    path.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


@pytest.mark.evals
@needs_a_model
@pytest.mark.parametrize("name, case", FIXTURE_CASES, ids=[f"{n}:{c['id']}" for n, c in FIXTURE_CASES])
def test_a_skill_fixture_on_the_eval_model(real_model, name, case):
    from fastapi.testclient import TestClient

    from tessellate.api.app import create_app
    from tessellate.core import deps

    deps.get_config().set_preference("small_model_mode", "on")
    report = fx.run_case(TestClient(create_app()), name, case)
    if RATES_OUT:
        _record(name, report)
    print(f"{name}:{case['id']} {report['outcome']} {report['checks']} "
          f"step {report['failed_step']} {report['reason']!r} {report['seconds']}s "
          f"first step {report['first_step_seconds']}s")
    if SKILL_FIXTURES[name]["small_class"]:
        assert report["outcome"] == "pass", (
            f"{name} is marked for the small class and {case['id']} came back "
            f"{report['outcome']} on {EVALS_MODEL}: {report['checks']}, first "
            f"unfinished step {report['failed_step']} ({report['reason']})"
        )


# --- the seam itself, which does not need a model ---------------------------


def test_the_evals_seam_is_the_only_thing_that_reaches_the_runner():
    """The hard rules of WORLD_CLASS_PLAN 9, made executable.

    They are easy to write down and easy to break later without noticing: a
    helper that shells out to the script "just to start one", a mode of the
    gate that runs it, a variable renamed on one side of the seam. Each of
    those turns the suite into something that needs a gigabyte of model to go
    green, which is the one outcome the whole arrangement exists to prevent.
    """
    script = ROOT / "scratchpad" / "llama-dev.sh"
    assert script.exists(), "scratchpad/llama-dev.sh is what sets these variables"
    body = script.read_text(encoding="utf-8")
    for name in ("TESSELLATE_EVALS_URL", "TESSELLATE_EVALS_MODEL"):
        assert name in body, f"{name} is read here and has to be printed there"
        assert name in Path(__file__).read_text(encoding="utf-8")

    # Nothing in tests/ runs the script or imports anything it builds.
    offenders = [
        path.name
        for path in repo_files(ROOT / "tests", patterns=("test_*.py",))
        if "llama-dev" in path.read_text(encoding="utf-8")
        and path.name != Path(__file__).name
    ]
    assert offenders == [], f"these tests reach for the dev runner: {offenders}"

    # And no mode of the merge gate calls it, including --full.
    gate = (ROOT / "scripts" / "gate.sh").read_text(encoding="utf-8")
    assert "llama-dev" not in gate, "the gate must never need a model"

    # `evals` is a registered marker, so `pytest -m evals` is a selection
    # rather than a typo that silently matches nothing.
    assert "evals:" in (ROOT / "pytest.ini").read_text(encoding="utf-8")
