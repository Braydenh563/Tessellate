"""What every chat backend has to answer, and the parts that don't vary (§6).

Tessellate talked to Ollama and only Ollama. Ollama is not the only thing that
serves a model on localhost any more: LM Studio, llama.cpp's server, Jan and
vLLM all speak the OpenAI shape on some other port, and asking for "LM Studio
support" specifically would have bought one backend instead of all of them.

So the split is by *dialect*, not by product. There are two:

  - Ollama's native `/api/chat`, `ai/ollama_client.py`
  - OpenAI's `/v1/chat/completions`, `ai/openai_client.py`

and every OpenAI-compatible server is the second one with a different base URL.

**This module is the part that is the same either way.** Three kinds of thing
live here:

1. The stream helpers (`_ThinkTagSplitter`, `_ToolTextGate`,
   `extract_text_tool_calls`, `split_thinking`). These were written for Ollama
   but nothing in them is Ollama-specific, they operate on text a model wrote,
   and a model writes `<think>` tags and prose-shaped tool calls whoever is
   serving it. They moved here rather than being copied, and `ollama_client`
   re-exports them so existing imports keep working.
2. `Provider`, the base class: the four questions a backend must answer, and
   the shared implementation of the ones whose answer doesn't depend on the
   dialect (the context ceiling, the preference that overrides it).
3. What the app knows *about models rather than about backends*, the
   known-context table, and how to read a window out of a `/models` catalog.

**Errors deliberately did not get a new name.** `ProviderError` is the same
class `OllamaError` has always been, aliased; every `except OllamaError` in the
routes therefore catches a failing LM Studio too. Introducing a parent class
instead would have been the tidier-looking change and would have silently
stopped those handlers firing for the new provider.
"""

from __future__ import annotations

import ast
import importlib
import json
import re
from collections.abc import Callable
from urllib.parse import urlparse

from tessellate.core import jobruns


#: Returns the user's stored sampling overrides, installed by the app's own
#: wiring so this module never has to import it.
#:
#: `ai/provider.py` is the bottom of the AI stack and `core.deps` is the wiring
#: that builds on it, so importing one from the other is a cycle (CodeQL
#: flagged it) as well as the wrong direction. None means "nothing registered",
#: which is the correct answer for a bare unit test as well as for a process
#: that has not finished wiring: no overrides, so every knob falls through to
#: the model's own recommendation.
_sampling_overrides_getter: Callable[[], object] | None = None


def set_sampling_overrides_getter(getter: Callable[[], object] | None) -> None:
    """Install the accessor `Provider.sampling_overrides` reads through."""
    global _sampling_overrides_getter
    _sampling_overrides_getter = getter


class ProviderError(RuntimeError):
    """The backend is unreachable, or it returned something unusable."""


class ToolsUnsupportedError(ProviderError):
    """The active model can't do tool calls, the caller should fall
    back to plain Q&A, never fail the whole chat. `declared` is True when
    the backend said so itself ("does not support tools"); False when the
    model claims tools but its tool requests failed (INBOX 538), which
    calls for different words."""

    def __init__(self, message: str = "", declared: bool = True) -> None:
        super().__init__(message)
        self.declared = declared


#: Ollama's own words for a model whose template declares no tools. Matched
#: exactly: a 400 that merely mentions "tool" (a bad argument, a thinking
#: option) is a different problem and must not relabel the model (INBOX 538).
NO_TOOLS_PHRASE = "does not support tools"
#: Ollama's 500 when the model wrote a tool call it could not parse: the model
#: *can* call tools and slipped once, so the request is worth one more try.
UNREADABLE_CALL_PHRASE = "error parsing tool call"


def tools_unsupported_message(model: str, declared: bool = True) -> str:
    """INBOX 272 part 1: a failure with a known remedy names it where it
    happened, not two screens away. Agent mode was requested and silently
    downgraded to a plain answer because `model` can't call tools, one
    caller (`ai/agent.py`) turns that into the `{"type": "unsupported"}`
    event and every consumer of it (`routes_chat.py`, `ai/skill_runner.py`,
    two more call sites) forwards this same sentence rather than writing
    its own, so the remedy reads the same everywhere it can be shown. The
    fix is one setting (Settings, Models has the "Can call tools" fact
    beside every installed model), never a download: some small models
    genuinely cannot do this at any size the app would suggest pulling."""
    if not declared:
        return (
            f"'{model}' says it can call tools, but its tool requests failed "
            "twice with this backend, so this answered as a plain question "
            "instead of using Agent mode. Asking again often works; if it "
            "keeps happening, pick another model in Settings, Models."
        )
    return (
        f"'{model}' can't call tools, so this answered as a plain question "
        "instead of using Agent mode. Pick a model whose spec sheet says "
        "“Can call tools: yes” in Settings, Models to use Agent mode "
        "with it."
    )


def is_transient_server_error(exc: Exception) -> bool:
    """A 5xx from the backend itself, not a 4xx: the request was well-formed
    but the server briefly couldn't handle it (a model still swapping in,
    momentary memory pressure): reported live, a chat call failing with a
    plain 500 and then succeeding on the exact same resend. Worth one silent
    retry, unlike a 4xx (bad request, model not found) where trying again
    changes nothing.

    Duck-typed against `.response.status_code` rather than importing
    `requests` here, so both HTTP-backed providers (ollama_client.py,
    openai_client.py) can share this without this module taking on a
    transport dependency it otherwise doesn't have."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return isinstance(status, int) and status >= 500


# --- what the app knows about models, not about backends --------------------

# Ollama's default when a model declares nothing. Everything that budgets
# against the window falls back to this, because being wrong in this direction
# only wastes headroom, while being wrong the other way silently drops the
# system prompt off the front of the context.
DEFAULT_CONTEXT_TOKENS = 4096

# The largest window this app will ask a backend to allocate by default.
#
# A model declaring 128k does not mean asking for 128k is free: the KV cache
# scales with the window, so a 7B at 128k wants several gigabytes that a laptop
# may not have, and the failure is an out-of-memory rather than a slow answer.
# 8k is comfortably more than the app's own worst-case prompt needs and costs a
# fraction of that, so it is the default; anyone with the memory to spare can
# raise it in preferences.
MAX_REQUESTED_CONTEXT = 8192

# Room for the reply. Unset, a backend will happily generate until it decides
# to stop, and a local model that rambles is the single most common reason an
# answer "takes ages", output tokens are generated one at a time, so they cost
# far more wall-clock each than prompt tokens do.
DEFAULT_MAX_OUTPUT_TOKENS = 1024


# Context windows for models whose server won't say. Ollama answers `/api/show`
# and LM Studio answers `/api/v0/models`, but plain llama.cpp and several cloud
# gateways report nothing at all, and the alternative to a table is budgeting
# every one of them against 4,096, which on a 128k model means withholding
# tools for no reason.
#
# Substring-matched against the model id, so `llama3.1:8b-instruct-q4_0` finds
# `llama3.1`. Keep keys as the shortest *unambiguous* prefix.
KNOWN_CONTEXT_WINDOWS: dict[str, int] = {
    # Local-first families: the ones this app is actually run with.
    "llama3.1": 131072,
    "llama3.2": 131072,
    "llama3.3": 131072,
    "llama3": 8192,
    "llama4": 1048576,
    "qwen2.5": 32768,
    "qwen3": 131072,
    "qwen3.5": 262144,
    "gemma2": 8192,
    "gemma3": 131072,
    "gemma4": 131072,
    "phi3": 131072,
    "phi4": 16384,
    "mistral": 32768,
    "mistral-nemo": 131072,
    "mixtral": 32768,
    "codestral": 32768,
    "granite3": 131072,
    "granite4": 131072,
    "deepseek-r1": 65536,
    "deepseek-v3": 65536,
    "smollm2": 8192,
    "tinyllama": 2048,
    "lfm2": 32768,
    # Embedding models, so a mis-selected one is budgeted sanely rather than
    # assumed to be a 128k chat model.
    "nomic-embed-text": 8192,
    "bge-": 512,
    "all-minilm": 512,
    # OpenAI-compatible gateways people point this at.
    "gpt-4o": 128000,
    "gpt-4.1": 1047576,
    "gpt-5": 400000,
    "o3": 200000,
    "o4-mini": 200000,
    "claude-3": 200000,
    "claude-haiku-4": 200000,
    "claude-sonnet-4": 200000,
    "claude-opus-4": 200000,
}


def _squash_separators(text: str) -> str:
    """Drop `-`/`_`/space so `granite4` still finds `granite-4.1-3b-uncensored`.

    Community/fine-tuned imports (a manually `ollama create`d GGUF, an
    uncensored fine-tune pulled from Hugging Face) routinely punctuate a
    family name differently from Ollama's own library naming, `granite4`
    in the library becomes `granite-4.1-3b-uncensored` or `Granite 4.1
    Uncensored` in the wild, and a plain substring match against either of
    those never finds `granite4` at all, even though it's clearly the same
    family. Dots are kept: they carry real version information (`3` vs
    `3.1`) that this app's own table already keys on.
    """
    return re.sub(r"[-_\s]", "", text)


def known_context(model: str) -> int | None:
    """The window this app believes `model` has, or None if it has no idea.

    Matches the *longest* key rather than the first, which is the whole reason
    this is a loop and not a dict lookup: `llama3` and `llama3.1` both match
    `llama3.1:8b`, they differ by 16x, and first-match order would decide which
    one wins by dictionary insertion, a 131k model budgeted at 8k, or worse,
    the other way round.

    The tag (`:8b-q4_0`) and any registry prefix (`hf.co/user/`) are stripped
    first: they say how the model was quantised and where it came from, not how
    much it can hold. Matched with separators squashed out (see
    `_squash_separators`) so a differently-punctuated import of the same
    family, the common shape for a community fine-tune, still finds its
    table entry instead of silently falling through to the flat default.
    """
    name = _squash_separators((model or "").lower())
    bare = _squash_separators(name.split("/")[-1].split(":")[0])
    best_key: str | None = None
    best_context: int | None = None
    for raw_key, window in KNOWN_CONTEXT_WINDOWS.items():
        key = _squash_separators(raw_key)
        if key in bare or key in name:
            if best_key is None or len(key) > len(best_key):
                best_key, best_context = key, window
    return best_context


# Fields a `/models` catalog might report a window under. Every OpenAI-compatible
# server spells it differently, LM Studio says `max_context_length`, vLLM says
# `max_model_len`, llama.cpp nests `n_ctx` under `meta`, OpenRouter says
# `context_length`, so all of them are read rather than one being guessed at.
_CONTEXT_FIELDS = (
    "context_length",
    "context_window",
    "max_context_length",
    "max_model_len",
    "max_seq_len",
)


def context_from_catalog_entry(entry: dict) -> int | None:
    """Read a positive context window out of one `/models` catalog entry."""
    if not isinstance(entry, dict):
        return None
    for field in _CONTEXT_FIELDS:
        value = entry.get(field)
        if isinstance(value, (int, float)) and value > 0:
            return int(value)
    meta = entry.get("meta") or entry.get("model_extra") or {}
    if isinstance(meta, dict):
        # llama.cpp's `n_ctx` is the window the server was actually started
        # with (`-c`), which beats anything the model file declares.
        for field in ("n_ctx", *_CONTEXT_FIELDS):
            value = meta.get(field)
            if isinstance(value, (int, float)) and value > 0:
                return int(value)
    return None


# Model ids that are not chat models. An OpenAI-shaped `/models` list is not
# ordered and routinely puts an embedding model first, so "just use the first
# one" picks something that cannot hold a conversation and fails at the point
# of asking a question rather than at the point of choosing.
_NOT_A_CHAT_MODEL = (
    "embed",
    "embedding",
    "bge-",
    "all-minilm",
    "rerank",
    "whisper",
    "tts-",
    "dall-e",
    "stable-diffusion",
    "clip-",
    "moderation",
)


def first_chat_model(models: list[str]) -> str | None:
    """The first id that looks like something you can chat with."""
    for name in models or []:
        if not any(hint in str(name).lower() for hint in _NOT_A_CHAT_MODEL):
            return name
    return (models or [None])[0]


def detect_provider(base_url: str) -> str:
    """Guess the dialect from the URL, for when the user hasn't said.

    Two rules, in this order, because the second is a catch-all:

      - a `/v1` path means the OpenAI shape, whoever is serving it, this is
        how Ollama's own compatibility surface gets used deliberately;
      - port 11434 with no `/v1` is Ollama's native API.

    Anything else falls back to `openai`, because that is what the long tail
    of servers implements. Guessing wrong is recoverable: the provider is a
    setting, and this only supplies its default.
    """
    try:
        parsed = urlparse((base_url or "").strip())
    except ValueError:
        return "ollama"
    path = (parsed.path or "").rstrip("/")
    if path == "/v1" or path.startswith("/v1/"):
        return "openai"
    if parsed.port == 11434 or path.startswith("/api"):
        return "ollama"
    return "openai" if path else "ollama"


class Provider:
    """The interface `agent.run_agent` and friends are written against.

    Subclasses implement the dialect-specific half, `context_length`,
    `is_running`, `list_models`, and the four generation paths (`chat`,
    `chat_stream`, `chat_tools`, `chat_tools_stream`) plus `embed`. What is
    shared lives here, and it is the part that took the measurements in §11a to
    get right: the ceiling on the window, and the fact that the number the app
    budgets against must be the same number it asks the backend for.
    """

    DEFAULT_CONTEXT_TOKENS = DEFAULT_CONTEXT_TOKENS
    MAX_REQUESTED_CONTEXT = MAX_REQUESTED_CONTEXT
    DEFAULT_MAX_OUTPUT_TOKENS = DEFAULT_MAX_OUTPUT_TOKENS

    #: Shown in Settings, Models and in the support bundle.
    name = "provider"

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Every generation path a backend defines is in the process ledger
        (INBOX 805: "all things that use the ai ... need to be logged"), so a
        new backend or a new caller cannot make a model call nobody sees."""
        super().__init_subclass__(**kwargs)
        for attr, wrap in (
            ("chat", jobruns.model_call),
            ("chat_tools", jobruns.model_call),
            ("chat_stream", jobruns.model_stream),
            ("chat_tools_stream", jobruns.model_stream),
        ):
            method = cls.__dict__.get(attr)
            if callable(method) and not getattr(method, "ledgered", False):
                setattr(cls, attr, wrap(method))

    def context_length(self, model: str) -> int | None:
        """How many tokens this model can hold, or None for "I can't tell".

        None is a real answer and callers handle it: a backend that cannot
        report a window degrades to `DEFAULT_CONTEXT_TOKENS` rather than
        failing the turn. Returning a *made-up* number instead would be worse
        than returning None, because the budget would then be scaled against
        something nobody verified.
        """
        raise NotImplementedError

    @property
    def max_requested_context(self) -> int:
        """The ceiling, overridable by the user who knows their own machine."""
        try:
            # `importlib`, not `from tessellate.core import deps`. That plain
            # import is what CodeQL py/cyclic-import #364 flagged, one hop
            # further along at `ai/embeddings.py:24`: the cycle it named is
            # `ai.embeddings -> ai.ollama_client -> ai.provider -> core.deps
            # -> ai.embeddings`, and this line is its only wrong-direction
            # edge: a provider is a leaf that the container builds, so it
            # has no business importing the container back. Deferring the
            # statement into the function body does not clear the alert
            # (`entry/manager.py` records the same finding); only dropping
            # the `import` statement itself does. Behaviour is unchanged:
            # the module is resolved at call time either way.
            deps = importlib.import_module("tessellate.core.deps")

            wanted = int(
                deps.get_config().get_preference(
                    "max_context_tokens", self.MAX_REQUESTED_CONTEXT
                )
            )
        except Exception:  # noqa: BLE001  # a bad preference must not stop a chat
            return self.MAX_REQUESTED_CONTEXT
        # Floor at the default: below it nothing works, and a typo like 40
        # should not silently make the app unusable.
        return max(self.DEFAULT_CONTEXT_TOKENS, wanted)

    #: A window the user set by hand, for one model, or None for "auto".
    #:
    #: Asked for directly (INBOX 77): "the window itself should be manageable
    #: by the user and auto when set ... a `num_ctx` preference per model in
    #: Settings, Models with Auto (the model file's value) or a number, sent
    #: on every request; the badge shows 'used / window'".
    #:
    #: **Per model and not one global number**, which is what
    #: `max_context_tokens` already was: a machine that runs a 4k model for
    #: quick answers and a 32k one for reading documents needs two answers, and
    #: a single ceiling means the big model is rationed to the small one's
    #: window or the small one is asked for a window it does not have. The
    #: global preference stays as the ceiling over all of them, because it is
    #: what stops a 128k window from being requested on a laptop that would
    #: swap itself to death filling it.
    #:
    #: Keyed by the model name exactly as the picker shows it. A stored entry
    #: for a model that is no longer installed costs nothing and is what makes
    #: the setting survive uninstalling and reinstalling a model.
    def preferred_context(self, model: str) -> int | None:
        """The window this model was set to by hand, or None for auto."""
        if not model:
            return None
        try:
            # The same deferred import the ceiling below uses, for the reason
            # its comment gives at length; `importlib` itself is imported at
            # module level (CodeQL flagged a redundant local import here).
            deps = importlib.import_module("tessellate.core.deps")
            windows = deps.get_config().get_preference("model_context_windows", {})
        except Exception:  # noqa: BLE001  # a bad preference must not stop a chat
            return None
        if not isinstance(windows, dict):
            return None
        raw = windows.get(model)
        #: "auto" is stored as the absence of a number, so a null, an empty
        #: string and the literal word all mean the same thing and none of them
        #: has to be special-cased by whatever writes this.
        if raw in (None, "", "auto"):
            return None
        try:
            wanted = int(raw)
        except (TypeError, ValueError):
            return None
        if wanted <= 0:
            return None
        #: Floored like the global ceiling is, and for the same reason: below
        #: the default nothing works, and a typo like 40 should not quietly
        #: make the app unusable for one model.
        return max(self.DEFAULT_CONTEXT_TOKENS, wanted)

    def usable_context(self, model: str) -> int:
        """The window to budget against, and, on Ollama, to ask for.

        Deliberately the same number in both places. Ollama runs a model at
        `num_ctx`, which is its own default (commonly 4,096) *regardless of
        what the model was trained for*, so reading a 32k context length and
        budgeting against it, without also asking for 32k, would produce
        exactly the overflow the budget exists to prevent.

        On the OpenAI shape there is no `num_ctx` to send: the window is fixed
        when the server loads the model. That makes this number advisory there
        rather than instructive, which is *safe in the direction that matters*
        - the app rations itself to at most what the server reported.
        """
        #: **A hand-set window wins outright, including over the ceiling.**
        #: Someone who types 16384 for a model whose file says 4096 is telling
        #: the app something the file does not know: that they started the
        #: server with `-c 16384`, or that the file is wrong. And
        #: `max_requested_context` is there to stop the app *guessing* its way
        #: to a window a laptop cannot fill, which is not what a number typed
        #: into a box for one named model is. Clamping it would make the
        #: setting look broken in the one case anybody would use it for, a
        #: large model on a machine that can take it, and the person who typed
        #: it can type a smaller one.
        chosen = self.preferred_context(model)
        if chosen:
            return chosen
        declared = self.context_length(model) or self.DEFAULT_CONTEXT_TOKENS
        return max(
            self.DEFAULT_CONTEXT_TOKENS, min(declared, self.max_requested_context)
        )

    def generation_budget(
        self,
        model: str,
        max_output_tokens: int | None = None,
        mode: str | None = None,
    ) -> dict:
        """The neutral settings every backend needs, before dialect.

        §6 called this: either each provider translates a neutral
        `{context_tokens, max_output_tokens}`, or it owns the whole payload, 
        and the agent should not learn four dialects. This is that neutral set;
        `runtime_options` on each subclass is the translation.

        `mode` is a response preset (§11): quick, normal or detailed. An
        explicit `max_output_tokens` still wins over the preset's, because a
        caller that names a number has a reason the preset can't know about.
        """
        from tessellate.ai import presets

        preset = presets.resolve(mode)
        cap = max_output_tokens or preset.max_output_tokens
        return {
            "context_tokens": self.usable_context(model),
            "max_output_tokens": cap + self.thinking_allowance(mode, model),
            **presets.sampling_options(preset),
        }

    #: Tokens a reasoning model may spend deliberating before its answer
    #: starts. **Added to the reply cap rather than taken out of it**, which is
    #: the whole point: the reply cap becomes `num_predict`, and `num_predict`
    #: bounds *everything the model generates*, thinking included. A flat cap
    #: therefore means a model that thinks for 256 tokens has nothing left to
    #: answer with, which is precisely the reported failure (§35A.3): Quick
    #: mode on a thinking model, twice, thought for a while and then emitted no
    #: answer at all.
    THINKING_ALLOWANCE_TOKENS = 1_024

    #: **Detailed asks for more thinking, so it needs more room for it.**
    #: Reported: with "Detailed" selected, some turns came back with no
    #: answer at all (or a much shorter one than the setting promised), the
    #: original fix above gave every preset the *same* flat 1,024-token
    #: allowance, but Detailed's own `length_hint` explicitly asks the model
    #: to "work through the relevant notes, draw connections between them,
    #: and explain your reasoning", inviting a longer thinking trace than
    #: Quick or Normal ever asked for, on a preset whose grounding context is
    #: usually the largest of the three. A verbose reasoning model given more
    #: to think about and the same 1,024-token leash starves its own answer
    #: exactly like §35A.3's Quick-mode case did, just less often, this file
    #: already predicted it: "1,024 shared between deliberation and answer is
    #: the same trap in a larger size" (test_thinking_budget.py). Unused
    #: headroom still costs nothing (see below), so there is no downside to
    #: sizing Detailed's allowance for the reasoning its own prompt invites.
    THINKING_ALLOWANCE_BY_MODE = {"detailed": 3_072}

    def thinking_allowance(self, mode: str | None, model: str) -> int:
        """Headroom for deliberation, unless thinking was actually turned off.

        Keyed on **what was sent**, not on what the model declares. That is
        deliberate: §35C is a report of a thinking model whose capability list
        says otherwise, and the capability list is the only thing
        `request_extras` can consult before deciding to send `think: False`.
        Trusting it twice would mean a model that lies about thinking gets a
        flat cap *and* thinks anyway, the failure above.

        The two ways to be wrong are not symmetric, which settles it:

        - allowance added but unused → the reply *may* run longer than the
          preset intended, and `length_hint` is still telling the model to
          answer in two or three sentences. `num_predict` is a ceiling, not a
          target, so an unused ceiling costs nothing;
        - allowance missing when needed → no answer at all.

        A total failure on one side and a slightly long answer on the other is
        not a close call.
        """
        if self.request_extras(mode, model).get("think") is False:
            return 0
        return self.THINKING_ALLOWANCE_BY_MODE.get(mode or "", self.THINKING_ALLOWANCE_TOKENS)

    def runtime_options(
        self,
        model: str,
        max_output_tokens: int | None = None,
        mode: str | None = None,
    ) -> dict:
        """The dialect-specific options block sent with every generation."""
        raise NotImplementedError

    def sampling_overrides(self) -> dict:
        """The user's own sampling settings, or {}, see `ai/sampling.py`.

        Read here rather than passed in, because every generation path in the
        app goes through `runtime_options` and threading a settings dict
        through all of them would mean each one could forget. Stored sparsely:
        only the fields actually changed, so a model the user has never touched
        still gets its own recommendations for everything else.

        Deliberately tolerant of a bad value. This is a preference file a
        person can edit by hand, and a typo in it should cost that one setting,
        not every generation the app makes.
        """
        # Read through a registered getter, not by importing `core.deps`.
        #
        # CodeQL flagged the direct import as a cycle and it is right about the
        # layering as well as the graph: `ai/provider.py` is the lowest layer
        # of the AI stack, every client builds on it, while `core.deps` is
        # the app's wiring, which reaches back down into this module to build
        # the very object being configured. Deferring the import inside the
        # function hid the cycle from the interpreter without removing it.
        #
        # The getter is installed by whoever does the wiring (see
        # `core/deps.py`), so this module keeps knowing nothing about where
        # settings live, and a test can hand it a plain dict.
        if _sampling_overrides_getter is None:
            return {}
        try:
            stored = _sampling_overrides_getter()
        except Exception:  # noqa: BLE001  # settings must never break a request
            return {}
        return stored if isinstance(stored, dict) else {}

    def request_extras(self, mode: str | None = None, model: str = "") -> dict:
        """Top-level payload fields a preset needs that aren't options.

        Ollama's thinking toggle is one; the OpenAI shape has no standard
        equivalent, so its implementation returns nothing. Empty by default so
        a provider only overrides it if it has something to say.
        """
        return {}

    def is_running(self) -> bool:
        raise NotImplementedError

    def loaded_models(self) -> list[str] | None:
        """What the backend holds in memory, where it can say (None: unknown)."""
        return None

    def unload(self, model: str) -> tuple[bool, str]:
        """Stop the model (rule 5). A server this app did not start keeps its
        own model loaded, so the honest answer is where to stop it."""
        return False, "This server keeps its own model loaded; stop it from the program that runs it."

    def list_models(self) -> list[dict]:
        raise NotImplementedError

    def supports(self, model: str, capability: str) -> bool | None:
        """Can this model do `capability`, True, False, or None for unknown.

        Three answers rather than two, and the third is the important one.
        "This model has no thinking to turn off" and "I cannot tell you whether
        it does" want different behaviour: the first means don't bother, the
        second means send nothing rather than guess. Collapsing them into a
        bool forces a guess at exactly the point where guessing wrong disables
        a working feature.

        The base implementation answers None to everything, which is the safe
        answer for a backend that does not report capabilities at all.
        """
        return None

    def model_spec(self, model: str) -> dict:
        """The model's own specification, flat, for Settings, Models.

        The app knew a context length and nothing else, so the screen could not
        say how big a model was, how it was quantised, or whether it could use
        tools: which is the first thing to check when "agent mode does
        nothing". Every field is optional: a backend that cannot answer returns
        None and the UI omits the row rather than printing "unknown" six times.
        """
        return {
            "name": model,
            "family": None,
            "parameters": None,
            "quantisation": None,
            "context_length": self.context_length(model),
            "usable_context": self.usable_context(model),
            "capabilities": [],
            "supports_tools": self.supports(model, "tools"),
            "supports_thinking": self.supports(model, "thinking"),
        }

    def supports_pull(self) -> bool:
        """Can this backend download models on request?

        Only Ollama can. LM Studio, llama.cpp and vLLM are handed a model that
        is already on disk, so the UI's download panel is meaningless there and
        hides itself rather than offering a button that cannot work.
        """
        return False


# --- stream helpers: about what a model wrote, not about who served it -------


#: **Five spellings, because the families do not agree.** Qwen and the
#: DeepSeek distills write `<think>`, several finetunes write `<thinking>`,
#: and `<reasoning>`, `<reason>` and `<thought>` all appear in the wild.
#: Shown raw, a reasoning block reads as garbage; dropped, a useful part of
#: the answer goes with it, so both halves come back and the UI decides.
_THINK_WORDS = ("think", "thinking", "thought", "reason", "reasoning")
_THINK_OPEN_RE = re.compile(r"<\s*(?:%s)\s*>" % "|".join(_THINK_WORDS), re.I)
_THINK_CLOSE_RE = re.compile(r"<\s*/\s*(?:%s)\s*>" % "|".join(_THINK_WORDS), re.I)


class _ThinkTagSplitter:
    """Routes streamed content into thinking and answer pieces.

    The tags arrive split across chunks, so a little state is unavoidable,
    and the spelling is not agreed on between families: `<think>` from Qwen
    and the DeepSeek distills, `<thinking>`, `<reasoning>`, `<reason>` and
    `<thought>` from various finetunes. All five are accepted, in either
    case, and a partly arrived tag is held back rather than emitted as text.

    **The one case a stream cannot fully win.** DeepSeek's chat template
    ends the prompt with an open tag, so the reply starts inside the thought
    and the only tag the model ever writes is the close. Nothing in the
    first chunk distinguishes that from an ordinary answer, and waiting to
    find out would hold the whole reply back, which is worse. So the text is
    streamed as the answer and the stray close tag is dropped when it
    arrives rather than shown as `</think>` in the middle of a sentence.
    `split_thinking` has the whole reply in hand and does separate the two,
    which is why a saved message reads correctly even when the live stream
    put the reasoning in the answer.
    """

    OPEN, CLOSE = "<think>", "</think>"
    OPENS = tuple(f"<{word}>" for word in _THINK_WORDS)
    CLOSES = tuple(f"</{word}>" for word in _THINK_WORDS)
    _LONGEST_CLOSE = max(len(tag) for tag in CLOSES)

    def __init__(self) -> None:
        self._buffer = ""
        self._mode = "start"  # start → thinking? → answer

    @staticmethod
    def _leading(text: str, tags: tuple[str, ...]) -> str | None:
        lowered = text.lower()
        for tag in tags:
            if lowered.startswith(tag):
                return tag
        return None

    @staticmethod
    def _could_become(text: str, tags: tuple[str, ...]) -> bool:
        lowered = text.lower()
        return bool(lowered) and any(tag.startswith(lowered) for tag in tags)

    @classmethod
    def _find_close(cls, text: str) -> tuple[int, int]:
        """(start, length) of the earliest closing tag, or (-1, 0)."""
        lowered = text.lower()
        best, size = -1, 0
        for tag in cls.CLOSES:
            at = lowered.find(tag)
            if at != -1 and (best == -1 or at < best):
                best, size = at, len(tag)
        return best, size

    def feed(self, chunk: str) -> list[dict]:
        self._buffer += chunk
        pieces: list[dict] = []

        if self._mode == "start":
            candidate = self._buffer.lstrip()
            opening = self._leading(candidate, self.OPENS)
            if opening:
                self._mode = "thinking"
                self._buffer = candidate[len(opening) :]
            elif self._could_become(candidate, self.OPENS):
                return pieces  # could still become an opening tag, wait
            else:
                self._mode = "answer"

        if self._mode == "thinking":
            at, size = self._find_close(self._buffer)
            if at != -1:
                pieces.append({"thinking_delta": self._buffer[:at]})
                self._buffer = self._buffer[at + size :]
                self._mode = "answer"
            else:
                # Keep enough back that a half-arrived closing tag is not
                # emitted as thinking text.
                safe = len(self._buffer) - (self._LONGEST_CLOSE - 1)
                if safe > 0:
                    pieces.append({"thinking_delta": self._buffer[:safe]})
                    self._buffer = self._buffer[safe:]
                return pieces

        if self._mode == "answer" and self._buffer:
            # A close with no open before it: drop the tag, keep the text.
            while True:
                at, size = self._find_close(self._buffer)
                if at == -1:
                    break
                self._buffer = self._buffer[:at] + self._buffer[at + size :]
            hold = 0
            for length in range(1, min(self._LONGEST_CLOSE, len(self._buffer) + 1)):
                if self._could_become(self._buffer[-length:], self.CLOSES):
                    hold = length
            if hold:
                emit, self._buffer = self._buffer[:-hold], self._buffer[-hold:]
            else:
                emit, self._buffer = self._buffer, ""
            if emit:
                pieces.append({"content_delta": emit})
        return pieces

    def flush(self) -> list[dict]:
        """The stream ended: emit whatever is left."""
        leftover, self._buffer = self._buffer, ""
        if not leftover:
            return []
        key = "thinking_delta" if self._mode == "thinking" else "content_delta"
        return [{key: leftover}]


class _ToolTextGate:
    """Holds back streamed text that might turn out to be a tool call in prose.

    Some small models write ``<tool_call>{...}</tool_call>``, or a bare JSON
    object: instead of using the structured tool_calls field.
    ``extract_text_tool_calls`` recovers those and strips them so they're
    executed rather than shown, but a streaming UI would already have printed
    the text by then. So content is gated until it's clearly *not* one of those
    shapes, released in one go at that moment, and passed straight through from
    then on.

    The cap matters: an answer that genuinely opens with "{" must not be held
    hostage forever, so past MAX_GATE characters the gate gives up and opens.
    """

    MAX_GATE = 1000
    OPENER = "<tool_call>"

    def __init__(self) -> None:
        self._buffer = ""
        self._open = False

    def feed(self, text: str) -> str:
        """Return whatever is safe to show now (possibly "")."""
        if self._open:
            return text
        self._buffer += text
        candidate = self._buffer.lstrip()
        if not candidate:
            return ""
        looks_like_call = (
            candidate.startswith("{")
            or candidate.startswith(self.OPENER)
            # A partially-arrived "<tool_call>", wait for the rest.
            or self.OPENER.startswith(candidate)
        )
        if looks_like_call and len(self._buffer) < self.MAX_GATE:
            return ""
        self._open = True
        held, self._buffer = self._buffer, ""
        return held

    def flush(self) -> str:
        """The stream ended while still gated, hand back what was held."""
        held, self._buffer = self._buffer, ""
        self._open = True
        return held

    @property
    def gated(self) -> bool:
        return not self._open


def _balanced_json_objects(text: str) -> list[tuple[int, int, str]]:
    """Every brace-balanced ``{...}`` substring in ``text``, as (start, end,
    substring) triples in the order they open.

    A model's tool-call arguments are routinely themselves an object or
    contain a list of objects, ``{"name": "create_note", "arguments":
    {"title": "x", "tags": ["a", "b"]}}`` is a completely ordinary call, not
    an edge case: so a scanner for this has to track real nesting depth
    rather than assume one flat level. Quoted braces (inside a JSON string
    value) are not counted, so a title like ``"Notes on {curly braces}"``
    can't desync the depth count.
    """
    found: list[tuple[int, int, str]] = []
    i, n = 0, len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_string = False
        escape = False
        j = i
        while j < n:
            ch = text[j]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            elif ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    found.append((i, j + 1, text[i : j + 1]))
                    break
            j += 1
        # Resume scanning right after this object (found) or right after the
        # unmatched '{' (ran off the end unbalanced), either way, before j+1
        # so an object nested immediately inside isn't scanned as if it were
        # top-level too.
        i = j + 1
    return found


# Verbs a model reaches for when it has forgotten the tool's real name, mapped
# to the verb this app actually uses. Reported with a screenshot of the popup
# agent: the model emitted, as plain text, `{"name": "make_note",
# "parameters": {...}}`, and **no note was made**. The text-call salvage
# below was already working; it dropped this one on the only check it could
# not pass, `name in tool_names`, because there is no `make_note`. There is
# `create_note`.
#
# A small model inventing a synonym for a verb is not the same failure as it
# inventing a whole capability, and the two deserve different answers: the
# first is a name to fix, the second is a refusal. So this only ever rewrites
# the *verb* of an otherwise real tool name, and only when exactly one real
# tool comes back: never a guess between `create_note` and `edit_note`.
_VERB_SYNONYMS = {
    "make": "create",
    "add": "create",
    "new": "create",
    "save": "create",
    "write": "create",
    "insert": "create",
    "store": "create",
    "read": "get",
    "open": "get",
    "fetch": "get",
    "show": "get",
    "view": "get",
    "load": "get",
    "find": "search",
    "lookup": "search",
    "query": "search",
    "remove": "delete",
    "destroy": "delete",
    "erase": "delete",
    "update": "edit",
    "change": "edit",
    "modify": "edit",
    "rewrite": "edit",
    "label": "tag",
    "connect": "link",
    "disconnect": "unlink",
}


def resolve_tool_name(name: object, tool_names: set[str]) -> object:
    """A real tool name for what the model wrote, or what it wrote unchanged.

    Only the verb is ever rewritten, and only to a single unambiguous match, 
    see `_VERB_SYNONYMS`. Anything this cannot resolve is returned untouched
    so the caller's own `name in tool_names` check still refuses it.
    """
    if not isinstance(name, str) or name in tool_names:
        return name
    cleaned = re.sub(r"[^a-z0-9_]+", "_", name.strip().lower()).strip("_")
    if not cleaned:
        return name
    if cleaned in tool_names:
        return cleaned
    head, _, rest = cleaned.partition("_")
    if not rest:
        return name
    swapped = f"{_VERB_SYNONYMS.get(head, head)}_{rest}"
    if swapped in tool_names:
        return swapped
    # Same noun, singular/plural swapped: `create_notes` for `create_note`,
    # `list_note` for `list_notes`. Cheap, and a real thing small models do.
    for candidate in (swapped.rstrip("s"), f"{swapped}s"):
        if candidate in tool_names:
            return candidate
    return name


#: **Every dialect a local model actually speaks when it writes a call as
#: text.** The structured `tool_calls` field is the happy path; everything
#: below is for a model that narrates the call instead, which is most of the
#: small ones, and a model that gets the dialect wrong is indistinguishable
#: to the user from a model that ignored the tool: the note never gets made
#: and the app cheerfully says it did something. The shapes, with the
#: families that emit them:
#:
#:   - `<tool_call>{"name": ..., "arguments": {...}}</tool_call>`: Qwen,
#:     Hermes, Granite and Phi, the last two often with the `<|tool_call|>`
#:     pipe spelling and sometimes a list inside one pair of tags.
#:   - a bare or fenced JSON object naming a tool: Gemma, Mistral behind its
#:     `[TOOL_CALLS]` marker, Llama behind `<|python_tag|>`.
#:   - the name *outside* the JSON: `<function=name>{...}</function>` from
#:     Llama 3, and `function<|tool_sep|>name` followed by a fenced object
#:     from DeepSeek, whose real markers are full-width pipes and not the
#:     ASCII ones.
#:   - a Python call rather than JSON: `[get_weather(city="Paris")]` inside
#:     LFM2's `<|tool_call_start|>` block, and `print(get_weather(...))`
#:     inside the ```tool_code fence Gemma's own docs recommend.
#:
#: Each marker below is a real special token from one of those templates.
_CALL_MARKER_RE = re.compile(
    r"<\s*\|?\s*/?\s*(?:python_tag|tool[_\u2581]?(?:calls?|sep|response|outputs?)"
    r"(?:[_\u2581](?:begin|end|start))?)\s*\|?\s*>"
    r"|<[\uff5c][^<>]*tool[^<>]*[\uff5c]>"
    r"|\[/?TOOL_CALLS\]",
    re.I,
)

#: The name sits outside the JSON in both of these, so the object that
#: follows is the arguments rather than the whole call.
_NAMED_CALL_RE = re.compile(
    r"<\s*function\s*=\s*([\w.\-]+)\s*>"
    r"|function\s*<\s*[|\uff5c][^<>]*sep[^<>]*[|\uff5c]\s*>\s*([\w.\-]+)",
    re.I,
)

#: The debris a lifted call leaves behind: the closing half of Llama's
#: `<function=...>` wrapper, a fence with nothing left inside it, and the
#: empty brackets of LFM2's one-element list.
_CALL_DEBRIS_RE = re.compile(
    r"</\s*function\s*>|```[a-zA-Z_]*\s*```|\[\s*,?\s*\]|\bprint\s*\(\s*\)"
)


def _first_json_object_after(text: str, start: int, window: int = 4000) -> tuple[int, int, str] | None:
    """The first brace-balanced object at or after ``start``, if it is near.

    The window exists so a name with no object of its own cannot reach
    forward and adopt an unrelated one later in the message.
    """
    for begin, end, blob in _balanced_json_objects(text[start : start + window]):
        return start + begin, start + end, blob
    return None


def _call_end(content: str, paren: int) -> int:
    """The index just past the `)` that closes the `(` at `paren`, or -1.
    Parentheses inside a quoted string do not count."""
    depth, in_string, quote, escape = 0, False, "", False
    for index in range(paren, len(content)):
        char = content[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                in_string = False
            continue
        if char in "\"'":
            in_string, quote = True, char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return index + 1
    return -1


def _literal_keywords(node: ast.Call) -> dict:
    """The keyword arguments of a call that are plain literals."""
    arguments: dict = {}
    for keyword in node.keywords:
        if keyword.arg is None:
            continue
        try:
            arguments[keyword.arg] = ast.literal_eval(keyword.value)
        except (ValueError, SyntaxError):
            continue
    return arguments


def _python_style_calls(content: str, tool_names: set[str]) -> list[tuple[int, int, dict]]:
    """Calls written as Python rather than JSON, as (start, end, call).

    Only keyword arguments are read, and only literals: `ast.literal_eval`
    on each value, never `eval` on the call. A tool in this app takes a
    named-argument object, so a positional argument has nowhere to go and is
    dropped rather than guessed at.
    """
    found: list[tuple[int, int, dict]] = []
    for name in sorted(tool_names):
        for match in re.finditer(rf"\b{re.escape(name)}\s*\(", content):
            end = _call_end(content, match.end() - 1)
            if end == -1:
                continue
            try:
                node = ast.parse(content[match.start() : end], mode="eval").body
            except SyntaxError:
                continue
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            found.append((match.start(), end, {"name": node.func.id, "arguments": _literal_keywords(node)}))
    return found


#: The write tools' names, set by `tessellate.ai.tools` as it loads; read by
#: the prose-call recovery below, which takes only reads without a marker.
_WRITE_TOOLS: dict[str, frozenset[str] | None] = {"names": None}


def set_write_tools(names) -> None:  # noqa: ANN001
    _WRITE_TOOLS["names"] = frozenset(names)

#: What one recovery pass finds: the calls, and the text each came from, to be
#: cut out of the answer.
_Recovered = tuple[list[dict], list[str]]


def _calls_in_blob(blob: str, tool_names: set[str]) -> list[dict]:
    """The calls one JSON blob holds: an object or a list, either shape."""
    try:
        data = loads_lenient(blob)
    except ValueError:
        return []
    found: list[dict] = []
    for item in data if isinstance(data, list) else [data]:
        if not isinstance(item, dict):
            continue
        # Accept {"name","arguments"} and OpenAI-ish {"function":{...}}.
        fn = item.get("function") if isinstance(item.get("function"), dict) else item
        name = fn.get("name") if isinstance(fn, dict) else None
        name = resolve_tool_name(name, tool_names)
        if name in tool_names:
            args = fn.get("arguments") or fn.get("parameters") or {}
            if isinstance(args, str):
                try:
                    args = loads_lenient(args)
                except ValueError:
                    args = {}
            found.append({"name": name, "arguments": args if isinstance(args, dict) else {}})
    return found


def _tagged_calls(content: str, tool_names: set[str]) -> _Recovered:
    """1) explicit <tool_call>…</tool_call> blocks (Qwen/Hermes style). The
    object inside is found by scanning from the opening tag rather than a
    `.*?` regex, which stops at the first `}`, the *first nested one* the
    moment `arguments` is itself an object, well short of the call's own
    close."""
    calls: list[dict] = []
    removals: list[str] = []
    for tag_match in re.finditer(r"<tool_call>\s*(.*?)\s*</tool_call>", content, re.S):
        # All of them, not just the first: a model that puts more than one
        # call inside one pair of tags (`<tool_call>[{...}, {...}]</tool_call>`,
        # or just two objects back to back) still means every call, not only
        # the first it wrote.
        for _start, _end, blob in _balanced_json_objects(tag_match.group(1)):
            found = _calls_in_blob(blob, tool_names)
            if found:
                calls.extend(found)
                removals.append(tag_match.group(0))
    return calls, removals


def _bare_json_calls(content: str, tool_names: set[str]) -> _Recovered:
    """2) a bare top-level JSON object naming a known tool. `_balanced_json_
    objects` only ever emits the outermost `{...}` at each position (it
    jumps past a whole matched span rather than re-entering it), so a
    call's own nested `arguments` object is never separately offered as a
    second, spurious call."""
    calls: list[dict] = []
    removals: list[str] = []
    for _start, _end, blob in _balanced_json_objects(content):
        if '"name"' not in blob:
            continue
        found = _calls_in_blob(blob, tool_names)
        if found:
            calls.extend(found)
            removals.append(blob)
    return calls, removals


def _named_calls(content: str, tool_names: set[str]) -> _Recovered:
    """3) the name outside the JSON: Llama's `<function=name>{...}</function>`
    and DeepSeek's `function<|tool_sep|>name` followed by its object. The
    object here is the *arguments*, not the call, so it carries no "name"
    key and pass 2 skips it on purpose rather than by accident."""
    calls: list[dict] = []
    removals: list[str] = []
    for match in _NAMED_CALL_RE.finditer(content):
        name = resolve_tool_name(match.group(1) or match.group(2), tool_names)
        if name not in tool_names:
            continue
        nearby = _first_json_object_after(content, match.end())
        if nearby is None:
            continue
        _begin, end, blob = nearby
        try:
            arguments = loads_lenient(blob)
        except ValueError:
            continue
        if not isinstance(arguments, dict):
            continue
        calls.append({"name": name, "arguments": arguments})
        removals.append(content[match.start() : end])
    return calls, removals


def _python_calls(content: str, tool_names: set[str]) -> _Recovered:
    """4) a Python call rather than JSON, which is what LFM2 emits inside
    `<|tool_call_start|>` and what Gemma's own documented recipe puts in a
    ```tool_code fence. Gated on one of those markers being present: a
    model that merely *mentions* `create_note(title="x")` in prose is
    explaining itself, not calling anything, and this app's chat does that
    far more often than it writes Python."""
    if not (_CALL_MARKER_RE.search(content) or "tool_code" in content):
        return [], []
    found = _python_style_calls(content, tool_names)
    return [call for _b, _e, call in found], [content[begin:end] for begin, end, _c in found]


def _prose_read_calls(content: str, tool_names: set[str]) -> _Recovered:
    """5) a read written with its JSON arguments in prose, `list_notes({...})`
    (Qwen2.5-3B, the loose-ends eval, 2026-10-05: it wrote the call, then
    "I cannot execute the tool call as I am a text-based AI"). A JSON object
    as the one argument is the schema's own shape, which a model describing
    a tool rarely writes; still, a description taken as a call must cost a
    round and never a change, so only the reads are taken without a
    marker. The write list is the tools module's, which registers it here
    when it loads (`set_write_tools`): importing it from here closed an
    import cycle through the whole tools package (ARCH-10's ratchet). Not
    registered, nothing is taken, since a write must never pass as a read."""
    writes = _WRITE_TOOLS["names"]
    reads = set() if writes is None else {name for name in tool_names if name not in writes}
    calls: list[dict] = []
    removals: list[str] = []
    for match in re.finditer(r"\b([a-z_]{3,40})\s*\(\s*(?=\{)", content):
        name = match.group(1)
        if name not in reads:
            continue
        nearby = _first_json_object_after(content, match.end() - 1, window=2000)
        if nearby is None or nearby[0] != match.end():
            continue
        _begin, end, blob = nearby
        close = re.match(r"\s*\)", content[end:])
        if not close:
            continue
        try:
            arguments = loads_lenient(blob)
        except ValueError:
            continue
        if isinstance(arguments, dict):
            calls.append({"name": name, "arguments": arguments})
            removals.append(content[match.start() : end + close.end()])
    return calls, removals


#: The recovery passes in the order they are tried; the first to find a call wins.
_RECOVERY_PASSES = (_tagged_calls, _bare_json_calls, _named_calls, _python_calls, _prose_read_calls)


def extract_text_tool_calls(
    content: str, tool_names: set[str]
) -> tuple[list[dict], str]:
    """Recover tool calls that a model wrote as TEXT instead of using the
    structured tool_calls field (bug: small models narrate/emit
    calls in prose, so notes the AI 'creates' never actually get made).

    Handles both an explicit ``<tool_call>{...}</tool_call>`` wrapper and a
    bare JSON object that names a known tool, nested objects and arrays in
    ``arguments`` included, via `_balanced_json_objects` rather than a regex
    that only matched a single flat level (a call with, say, a `tags` list
    or a nested `arguments` object silently failed to recover, arguably the
    single most common shape a real tool call takes, and reported live as
    "the ai didn't actually call any tools"). Returns (calls, cleaned_text)
    where cleaned_text has the recovered JSON removed so it isn't shown to
    the user."""
    calls: list[dict] = []
    cleaned = content
    for recover in _RECOVERY_PASSES:
        found, removals = recover(content, tool_names)
        calls.extend(found)
        for text in removals:
            cleaned = cleaned.replace(text, "")
        if calls:
            break

    # The markers themselves are special tokens, never prose, so once a call
    # has been lifted out they are noise in the answer: `<|python_tag|>` or a
    # fence left empty by the removal above is exactly the debris a user
    # reads as the app being broken. Only on a hit, so an answer that happens
    # to quote one of these is left alone.
    if calls:
        cleaned = _CALL_MARKER_RE.sub("", cleaned)
        # Twice, because the debris nests: Gemma's recipe is a `print(...)`
        # inside a ```tool_code fence, and the fence only reads as empty once
        # the emptied `print()` around the lifted call has gone.
        for _ in range(2):
            cleaned = _CALL_DEBRIS_RE.sub("", cleaned)

    return calls, cleaned.strip()


def _ns_to_ms(value) -> int | None:
    """Ollama reports durations in nanoseconds; milliseconds read better."""
    try:
        return round(int(value) / 1_000_000)
    except (TypeError, ValueError):
        return None


def split_thinking(text: str) -> tuple[str, str | None]:
    """Separate a thinking model's reasoning from its answer.

    Three shapes, not one, and the two this gained are the ones that were
    reaching users as raw text:

    - A closing tag with no opening one. DeepSeek's own chat template ends
      the prompt with `<think>`, so the model's reply *begins* inside the
      thought and the only tag it ever writes is the close. Requiring both
      tags, which is what this did, handed the entire chain of reasoning to
      the user as the answer with a stray `</think>` in the middle of it.
    - An opening tag with no closing one, which is what a reply cut short by
      a token limit looks like. Everything after the tag is thought, and the
      answer is whatever came before it, usually empty.

    More than one block is folded together rather than only the first, since
    a model that thinks twice is not a model whose second thought belongs in
    its answer.
    """
    thoughts: list[str] = []
    answer: list[str] = []
    position = 0
    while True:
        opened = _THINK_OPEN_RE.search(text, position)
        closed = _THINK_CLOSE_RE.search(text, position)
        if closed and (opened is None or closed.start() < opened.start()):
            thoughts.append(text[position : closed.start()])
            position = closed.end()
            continue
        if opened is None:
            answer.append(text[position:])
            break
        answer.append(text[position : opened.start()])
        closing = _THINK_CLOSE_RE.search(text, opened.end())
        if closing is None:
            thoughts.append(text[opened.end() :])
            break
        thoughts.append(text[opened.end() : closing.start()])
        position = closing.end()
    thinking = "\n\n".join(part.strip() for part in thoughts if part.strip()).strip()
    return "".join(answer).strip(), thinking or None



def _unfence(text: str) -> str:
    """The inside of a ```json ... ``` fence, by string ops (no regex for a
    CodeQL to call polynomial), or `text` itself."""
    if not text.startswith("```"):
        return text
    body = text[3:].lstrip("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ").rstrip()
    return (body[:-3] if body.endswith("```") else body).strip()

#: A comma left before a closing brace or bracket: `{"a": 1,}`.
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


def _close_open_json(text: str) -> str:
    """`text` with an unterminated string and any unclosed brackets closed, in
    the order they opened: the shape of a call cut off by the output cap."""
    stack: list[str] = []
    in_string = escape = False
    for ch in text:
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]" and stack:
            stack.pop()
    tail = '"' if in_string else ""
    return text.rstrip().rstrip(",") + tail + "".join(reversed(stack))


#: Deeper than any argument a tool takes. Checked before parsing because
#: where `json.loads` gives up differs by Python version: 3.11 raises
#: RecursionError at 5,000 nested objects, 3.12 and later parse them.
JSON_MAX_DEPTH = 200


def _json_too_deep(raw: str, limit: int = JSON_MAX_DEPTH) -> bool:
    """True when brackets outside strings nest past `limit`: one pass."""
    depth = 0
    in_string = escaped = False
    for ch in raw:
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch in "[{":
            depth += 1
            if depth > limit:
                return True
        elif ch in "]}":
            depth -= 1
    return False


def loads_lenient(text: str) -> object:
    """JSON a small model wrote, read the way it meant it (INBOX 527).

    Measured before this existed: none of five ordinary slips survived
    (a trailing comma, single quotes, Python's True, a fence, a call cut
    off by the output cap). Each became `{}`, and the model was told its
    arguments were "missing something" with no hint that it was the JSON.
    Tried in order, strictest first, so valid JSON is never reinterpreted:
    as written; the first object of several; trailing commas dropped;
    a Python literal (`ast.literal_eval`, literals only); brackets closed.
    Raises ValueError when none of them reads. **A runaway `[[[[` is one that
    does not** (sweep 1004): past a few thousand levels `json.loads` raises
    RecursionError, which is not a ValueError, and a small model looping on a
    bracket ended the whole turn instead of failing one tool call.
    """
    raw = _unfence(str(text).strip())
    if _json_too_deep(raw):
        raise ValueError("JSON nested too deeply")
    try:
        return json.loads(raw)
    except (ValueError, RecursionError):
        pass  # not strict JSON: try the leading value alone
    try:
        return json.JSONDecoder().raw_decode(raw)[0]
    except (ValueError, RecursionError):
        pass  # no leading value either: try the repairs below
    tidy = _TRAILING_COMMA_RE.sub(r"\1", raw)
    for attempt in (tidy, _close_open_json(tidy)):
        try:
            return json.loads(attempt)
        except (ValueError, RecursionError):
            pass  # a Python literal (single quotes, True) is the last reading
        try:
            return ast.literal_eval(attempt)
        except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
            pass  # this repair did not read; the next one, or the error below
    raise ValueError("not JSON, even read leniently")


def normalise_tool_calls(raw_calls: list[dict]) -> list[dict]:
    """`[{"function": {...}}]` in either dialect -> `[{"name", "arguments"}]`.

    The OpenAI shape sends `arguments` as a JSON *string* where Ollama sends an
    object: but Ollama models are inconsistent among themselves and some send
    the string too, which is why this already handled both before there was a
    second provider. One dialect fewer to add.

    A string read with `loads_lenient`; one that still does not read, or reads
    as something other than an object, comes back with `invalid_arguments`
    (what the model wrote, clipped) so the agent loop can say *the JSON* was
    wrong rather than run the tool with nothing.
    """
    calls: list[dict] = []
    for item in raw_calls or []:
        function = item.get("function") or {}
        arguments = function.get("arguments") or {}
        invalid = None
        if isinstance(arguments, str):
            try:
                arguments = loads_lenient(arguments)
            except ValueError:
                invalid = function.get("arguments")
                arguments = {}
        if not isinstance(arguments, dict):
            invalid = invalid or str(function.get("arguments"))
            arguments = {}
        call = {"name": function.get("name", ""), "arguments": arguments}
        if invalid is not None:
            call["invalid_arguments"] = str(invalid)[:300]
        calls.append(call)
    return calls


def offered_tool_names(tools: list[dict]) -> set[str]:
    """The names in a tool schema list, for text-call recovery to match on."""
    return {
        t.get("function", {}).get("name") for t in tools or [] if isinstance(t, dict)
    }


__all__ = [
    "ProviderError",
    "ToolsUnsupportedError",
    "NO_TOOLS_PHRASE",
    "UNREADABLE_CALL_PHRASE",
    "Provider",
    "DEFAULT_CONTEXT_TOKENS",
    "MAX_REQUESTED_CONTEXT",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "KNOWN_CONTEXT_WINDOWS",
    "known_context",
    "context_from_catalog_entry",
    "first_chat_model",
    "detect_provider",
    "extract_text_tool_calls",
    "normalise_tool_calls",
    "loads_lenient",
    "offered_tool_names",
    "split_thinking",
]
