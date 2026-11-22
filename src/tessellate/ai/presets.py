"""Quick, normal, detailed: one dial over the settings a turn actually needs (§11).

**The gap this closes.** The prompt side of a turn is budgeted carefully:
`ai/context.py` rations every part of the input against the model's real
window. The *output* side had one number for everything, `num_predict` was a
flat 1,024 whether the question was "when did I write about beans" or "draft me
a summary of the last month". Output tokens are generated one at a time, so
they cost far more wall-clock each than prompt tokens do: an unbounded or
over-generous reply cap is the single most common reason an answer "takes
ages", and a uniform one means every short question pays for the possibility of
a long answer.

**Why a preset rather than automatic.** Choosing settings *by task* needs a
"how hard is this turn" judgement, which is itself a model call, and it fails
by being wrong confidently rather than obviously. A preset the person picks is
honest about being a preset. Automatic routing can be layered on later; it
cannot be un-layered once someone has learned not to trust it.

**What varies, and why each one.**

- `max_output_tokens`, the direct latency lever, and the reason this exists.
- `temperature`, recalling what you wrote wants the likeliest words; drafting
  and brainstorming want room to move. Sending 0.8 for "when did I write X" is
  asking a fact question to be creative.
- `think`, reasoning models spend output tokens *before* the answer starts.
  On a quick lookup that is the whole latency budget spent on deliberation
  nobody reads.
- `length_hint`, the model has to be told, not only capped. A cap alone
  truncates mid-sentence, which reads as a crash; a hint plus a cap produces a
  short answer that ends.

**Failing closed on a model that can't.** Not every model supports a thinking
toggle, and `think` sent to one that doesn't is either ignored or an error
depending on the backend and its version. So the toggle is only ever sent when
it is being turned *off*, and only where the backend has somewhere to put it, 
turning thinking off on a model with none is a no-op either way, while turning
it on where it isn't supported is the request that fails. Sending nothing is
always the safe direction, because "nothing" means "whatever the model does by
default", which is what happened before this module existed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResponseMode:
    """One preset. Everything a turn's *output* side needs, in one place."""

    #: Stored in preferences and sent by the UI.
    id: str
    #: Shown on the picker.
    label: str
    #: What the user gets, in the tooltip.
    description: str
    #: The reply cap: `num_predict` on Ollama, `max_tokens` on OpenAI.
    max_output_tokens: int
    #: Lower is more literal. None means "whatever the backend defaults to",
    #: which is what every turn got before this existed.
    temperature: float | None
    #: False asks a reasoning model not to think. None never sends the field, 
    #: see the module docstring on failing closed.
    think: bool | None
    #: Appended to the system prompt. A cap without a hint truncates
    #: mid-sentence, which reads as a crash rather than as brevity.
    length_hint: str


MODES: dict[str, ResponseMode] = {
    "quick": ResponseMode(
        id="quick",
        label="Short",
        description="One or two sentences. Fastest: best for looking something up.",
        # Roughly 200 words. Enough for a fact, a date, or a list of note
        # titles, which is what this mode is for.
        max_output_tokens=256,
        temperature=0.2,
        think=False,
        length_hint=(
            " Answer in one or two sentences. Do not explain your "
            "reasoning, and do not add caveats or suggestions unless asked."
        ),
    ),
    "normal": ResponseMode(
        id="normal",
        label="Normal",
        description="The balanced default: a full answer, not a summary.",
        # The value every turn used before presets existed, kept deliberately:
        # the default mode must not change anyone's experience on upgrade.
        max_output_tokens=1024,
        temperature=None,
        think=None,
        # **It used to say nothing at all, and that was the bug.** Reported:
        # *"the normal (balanced) setting writes too concisely, it is closer to
        # the quick setting."* Exactly right, and an empty hint is why, the
        # two neighbouring modes both steer, so with no sentence of its own
        # Normal inherited whatever the base prompt implied, and the base
        # prompt is written for a local model on a budget and leans terse. A
        # default that is the absence of an instruction is not a middle
        # setting; it is whichever end the surrounding text happens to pull to.
        #
        # This asks for the middle explicitly. It does not raise the cap: 1024
        # tokens is ~750 words and the old answers were nowhere near it, so the
        # ceiling was never what was binding, the instruction was.
        length_hint=(
            " Give a complete answer in a short paragraph or two: say what the "
            "notes actually say, with the specifics, rather than summarising "
            "them in a sentence. Stop once the question is answered."
        ),
    ),
    "detailed": ResponseMode(
        id="detailed",
        label="Detailed",
        description="Longer, more thorough answers. Slower: best for drafting.",
        max_output_tokens=3072,
        temperature=0.8,
        think=None,  # let a reasoning model reason; that is the point here
        length_hint=(
            " Be thorough. Work through the relevant notes, draw connections "
            "between them, and explain your reasoning. Add a supporting "
            "sentence for each source note you draw on."
        ),
    ),
}

#: What a turn gets when nobody has said otherwise. `normal` reproduces the
#: behaviour that predates this module exactly.
DEFAULT_MODE = "normal"

#: **Presets the app chooses for itself, which the person never picks.**
#: `MODES` above is the picker: routes_chat builds the mode switch from it and
#: routes_settings refuses a preference that is not in it. A surface with its
#: own needs would otherwise have to either add a fourth row to that picker,
#: which puts a mode nobody asked for in front of everybody, or reuse one that
#: is wrong for it. These are keyed the same way and resolve the same way, and
#: they are simply not on the picker.
GUIDE_MODE = "guide"

#: **Short background jobs of the utility model** (CHAT_PLAN 1691, B72):
#: entity names, a title, a caption, a reminder's JSON, speaker names, a
#: tension check, a re-planned step. Nobody reads their reasoning. Measured on
#: Qwen3-0.6B (2026-11-11, seed 7): four such jobs spent 925 tokens thinking
#: and 56 with it off. Normal's cap and temperature, no length hint (the
#: prompts carry their own); only `think` differs.
BACKGROUND_MODE = "background"

#: The model bench (`ai/bench.py`): temperature 0, so the same held-out set on
#: the same model scores the same twice. Measured (2026-11-11, Qwen2.5-1.5B on
#: llama-cpp-python, server default sampling): two runs of 29 tasks scored 0.667
#: and 0.611, one citation task flipping, against a gate of two points.
BENCH_MODE = "bench"

INTERNAL_MODES: dict[str, ResponseMode] = {
    #: The Guide panel (`ai/help_chat.py`): Quick's shape, because a "how do I
    #: save a note" answer is two or three sentences and the low temperature
    #: is what keeps it from inventing a menu that does not exist.
    #:
    #: **Except for `think`, and that is the whole reason this exists.** Quick
    #: sends `think: False`, which is right for a lookup nobody reads the
    #: reasoning of, and it is what made the Guide's thinking box dead markup:
    #: the panel renders `.help-chat-think` from a `thinking` event that could
    #: never arrive, because the mode the turn ran in had turned thinking off
    #: at the backend. The owner, 2026-09-20: "thinking boxes dont render".
    #: `None` here means the field is never sent and the model does whatever
    #: it does, which for a reasoning model is to think and for every other
    #: model is nothing at all, so neither kind is made worse.
    #:
    #: The reply cap is unchanged: `Provider.thinking_allowance` adds its own
    #: headroom on top of `max_output_tokens` when thinking was not turned
    #: off, which is the §35A.3 fix, so the answer is not competing with the
    #: reasoning for the same 256 tokens.
    #:
    #: **And for the reply cap, since INBOX 410.** The Guide now holds a
    #: controls reference per surface, and "what are all the whiteboard
    #: shortcuts" is answered by listing one: the longest entry is about
    #: 1,550 characters, near 520 tokens at the conservative three characters
    #: a token, which Quick's 256 cut off mid-list. 640 holds the longest
    #: entry with room over; a short question still gets a short answer,
    #: because the system prompt asks for one and the cap is a ceiling, not a
    #: target. `tests/test_help_controls.py` checks the cap against the
    #: longest entry, so a longer one raises this or fails.
    GUIDE_MODE: ResponseMode(
        id=GUIDE_MODE,
        label="Guide",
        description="The Guide panel's own preset: Quick's brevity, thinking left to the model.",
        max_output_tokens=640,
        temperature=MODES["quick"].temperature,
        think=None,
        length_hint=MODES["quick"].length_hint,
    ),
    BACKGROUND_MODE: ResponseMode(
        id=BACKGROUND_MODE,
        label="Background",
        description="The app's own short jobs: thinking off, Normal's cap.",
        max_output_tokens=MODES["normal"].max_output_tokens,
        temperature=None,
        think=False,
        length_hint="",
    ),
    BENCH_MODE: ResponseMode(
        id=BENCH_MODE,
        label="Bench",
        description="The model bench: temperature 0 so a rerun matches.",
        max_output_tokens=MODES["normal"].max_output_tokens,
        temperature=0.0,
        think=None,
        length_hint="",
    ),
}


def resolve(mode: str | None) -> ResponseMode:
    """The preset for a name, falling back rather than raising.

    Reached from a preference file the user may have edited by hand and from a
    request body, so an unknown name is a thing to absorb. Falling back to
    `normal` means a typo costs the setting, not the chat.

    `INTERNAL_MODES` is consulted too, so a preset the app picks for one of
    its own surfaces resolves through the one function every dialect already
    calls, rather than through a second path that would have to be kept in
    step with this one.
    """
    name = (mode or "").strip().lower()
    return MODES.get(name) or INTERNAL_MODES.get(name) or MODES[DEFAULT_MODE]


def sampling_options(mode: ResponseMode) -> dict:
    """The parts of a preset that go in the request, omitting what isn't set.

    Omission is load-bearing: a key that is absent means "the backend's own
    default", which is exactly what every turn used before presets existed. A
    key present with a null would instead be an explicit instruction to use
    nothing, which some backends reject and others read as zero.
    """
    options: dict = {}
    if mode.temperature is not None:
        options["temperature"] = mode.temperature
    return options
