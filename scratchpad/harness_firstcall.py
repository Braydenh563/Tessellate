"""H4: the required first call, over twenty imperatives and ten questions.

For each request: does `agent._requires_a_call` force it (it should for every
imperative and no question), and what does the real model's first round do,
with the app's own system prompt and the toolbox `_prepare_turn` builds for
the model's tier (forced where the harness forces). Also "two calls in one
reply": requests that need two tools at once, counted by calls in the first
reply. No model needed for the classification line.

    TESSELLATE_EVALS_URL=... TESSELLATE_EVALS_MODEL=... PYTHONPATH=src \\
        .venv/bin/python scratchpad/harness_firstcall.py [--only imperatives,questions,pairs]
"""

import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

import requests

from tessellate.ai import agent
from tessellate.ai import wiring  # noqa: F401
from tessellate.core import deps

logging.disable(logging.WARNING)
URL = os.environ.get("TESSELLATE_EVALS_URL", "")
MODEL = os.environ.get("TESSELLATE_EVALS_MODEL", "")

IMPERATIVES = [
    ("Make a note: buy oat milk and eggs", {"create_note"}),
    ("Make a note that the boiler code is 4471", {"create_note"}),
    ("Note down: call Sam about the van", {"create_note"}),
    ("Jot down the wifi password is pumpkin42", {"create_note"}),
    ("Create a note called Packing list with socks and a torch", {"create_note"}),
    ("Save this: the plumber is free on Thursday", {"create_note"}),
    ("Remind me tomorrow at 9am to call the dentist", {"set_reminder"}),
    ("Remind me in 20 minutes to take the bread out", {"set_reminder"}),
    ("Set a reminder for Friday at 5pm to pay rent", {"set_reminder"}),
    ("Tag my plumber note with urgent", {"search_notes", "tag_note"}),
    ("Tag the dentist note as health", {"search_notes", "tag_note"}),
    ("Pin my dentist note", {"search_notes", "pin_note"}),
    ("Unpin the Snowdon trip note", {"search_notes", "pin_note"}),
    ("Add 'bring a rain jacket' to my Snowdon trip note", {"search_notes", "get_note", "edit_note"}),
    ("Append 'ask about the invoice' to the plumber note", {"search_notes", "get_note", "edit_note"}),
    ("Put 'buy stamps' in my shopping note", {"search_notes", "get_note", "edit_note"}),
    ("Move the plumber note to Home", {"search_notes", "set_category", "move_note"}),
    ("File the dentist note under Health", {"search_notes", "set_category", "move_note"}),
    ("Rename the Snowdon trip note to Snowdon in May", {"search_notes", "edit_note", "rename_note"}),
    ("Mark the reminder to pay rent as done", {"list_reminders", "complete_reminder"}),
]

QUESTIONS = [
    ("How many notes do I have?", {"count_notes"}),
    ("What categories do I have?", {"list_categories"}),
    ("What tags am I using?", {"list_tags"}),
    ("When is the plumber coming?", {"search_notes", None}),
    ("What did I write about Snowdon?", {"search_notes", None}),
    ("Who is my dentist?", {"search_notes", None}),
    ("What reminders do I have this week?", {"list_reminders"}),
    ("Which of my notes are pinned?", {"list_notes", "search_notes"}),
    ("what's in my shopping note", {"search_notes", "get_note", None}),
    ("Do I have anything about boots", {"search_notes", None}),
]

PAIRS = [
    ("Make a note: buy oat milk, and remind me tomorrow at 9am to call the dentist", {"create_note", "set_reminder"}),
    ("How many notes do I have and what categories are there?", {"count_notes", "list_categories"}),
    ("Search my notes for the plumber and for the dentist", {"search_notes"}),
    ("Pin my dentist note and tag it health", {"search_notes", "pin_note", "tag_note"}),
    ("What tags and what categories am I using?", {"list_tags", "list_categories"}),
]


class _Models:
    def chat_model(self):
        return MODEL or "qwen2.5-3b-instruct"

    def utility_model(self):
        return self.chat_model()


class _Window:
    def usable_context(self, model):
        return 8192


def _setup(question, session):
    plan = agent._prepare_turn(
        session, question, [], _Models(), _Window(), style="friendly", profile="", history=None,
        persona_prompt=None, allowed_tools=None, blocked_tools=None, max_rounds=agent.MAX_ROUNDS,
        earned_rounds=agent.EARNED_ROUNDS, mode=None, use_utility_model=False, images=None,
        model_override=None, image_context=None,
    )
    return plan, agent._requires_a_call(question, plan)


def _first_round(question, plan, forced):
    # The tools the harness sends on round one (H4: a forced round keeps the
    # writes and the finders, a question no write). OFFERED=all measures the
    # whole toolbox instead, the before.
    offered = plan.offered
    if os.environ.get("OFFERED") != "all" and hasattr(agent, "_first_round_tools"):
        offered = agent._first_round_tools(question, plan, plan.offered, forced)
    body = {"model": MODEL, "messages": plan.messages, "tools": offered, "max_tokens": 400}
    if forced:
        body["tool_choice"] = "required"
    started = time.monotonic()
    reply = requests.post(f"{URL}/chat/completions", json=body, timeout=1200).json()
    message = reply["choices"][0]["message"]
    calls = [c["function"]["name"] for c in message.get("tool_calls") or []]
    return calls, (message.get("content") or "")[:120], round(time.monotonic() - started, 1)


def main(argv):
    only = set((argv[argv.index("--only") + 1] if "--only" in argv else "imperatives,questions,pairs").split(","))
    deps.init_app_state(data_dir=Path(tempfile.mkdtemp()))
    session_cm = deps.get_db().session()
    session = session_cm.__enter__()
    sets = [("imperatives", IMPERATIVES), ("questions", QUESTIONS), ("pairs", PAIRS)]
    totals = {}
    for name, cases in sets:
        if name not in only:
            continue
        forced_n = right = two = 0
        for question, ok in cases:
            plan, forced = _setup(question, session)
            forced_n += forced
            row = {"q": question, "forced": forced, "tier": plan.tier.name}
            if URL and MODEL:
                calls, text, secs = _first_round(question, plan, forced)
                good = (calls and calls[0] in ok) or (not calls and None in ok)
                right += bool(good)
                two += len(calls) >= 2
                row.update(calls=calls, right=bool(good), s=secs, said=text if not calls else "")
            print(json.dumps(row), flush=True)
        totals[name] = {"cases": len(cases), "forced": forced_n, "right_first": right if URL else None, "two_calls": two if URL else None}
    print("TOTALS", json.dumps(totals))


if __name__ == "__main__":
    main(sys.argv)
