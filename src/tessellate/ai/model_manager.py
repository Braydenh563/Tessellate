"""Model management (plan §6.5): which models are active, the curated
suggested-models catalog, and the two background jobs, re-indexing
after an embedding switch, and downloading a model with progress.

The janitor, librarian, and embedding service must never hardcode a
model name (plan §4): they ask this module, which reads the user's
saved preferences and falls back to the defaults.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import delete, select

from tessellate.ai.ollama_client import OllamaClient, OllamaError
from tessellate.core.config import ConfigManager
from tessellate.core import jobruns, taskhistory
from tessellate.core.database import DatabaseManager, EmbeddingRecord, Entry
from tessellate.core.logbuffer import safe_value
from tessellate.entry.manager import log_action


class Embedder(Protocol):
    """The two methods the re-index job needs from an embedding service.

    Stated structurally rather than by importing `EmbeddingService`, because
    that import points back at `ai/embeddings.py`, which imports this module, 
    a genuine cycle that a `TYPE_CHECKING` guard hides at runtime without
    removing. Writing down the contract is also the more honest description:
    re-indexing does not need an `EmbeddingService`, it needs something that
    can embed an entry and name its backend, which is what the tests pass.
    """

    def store_for_entry(self, session, entry: Entry) -> bool:
        pass

    def backend_id(self) -> str:
        pass

# Curated catalog, stored as data so it's trivial to edit (plan §6.5).
# There's no Ollama API to browse the online library, hence hardcoded.
#
# **Ordered smallest-first within each purpose, and that is the ordering that
# matters.** Someone reading this list is choosing hardware they already own.
# A list sorted by quality puts the model they cannot run at the top and the
# one they should start with out of sight; sorted by size, the first thing they
# see is the thing most likely to work.
#
# `purpose` says what the model is *for* rather than how good it is. "Strong
# all-rounder" is not a decision anyone can act on; "the smallest one worth
# using: fine on a laptop with no GPU" is.
#
# Sizes are the default quantisation Ollama pulls (usually Q4_K_M) and are
# approximate. They matter more than the parameter count here: a 7B at Q4 and
# a 3B at Q8 land in the same place on an 8 GB machine.
#
# An entry may carry `ram_gb`, the memory the purpose line says it needs
# ("Needs ~16 GB"); without it `model_cards.ram_needed_gb` estimates one from
# the download size. Everything else a card shows (what it is good at, the
# starting pick, whether it fits this computer) is derived in `model_cards`.
#
# This is a hand-maintained list against a registry that moves, so a tag here
# can go stale. That fails safely and legibly: the pull returns Ollama's own
# "model not found" and the Models screen shows it, rather than the app
# pretending to know something it doesn't. Nothing else reads these names.
SUGGESTED_MODELS: dict[str, list[dict]] = {
    # Split by type (text / vision / embedding / moe), asked for directly, 
    # this dict drives the Settings -> Models suggested-downloads list
    # generically (frontend/js/ai-tools.js's renderSuggested() does a plain
    # `Object.entries()` over it and labels each model with its own top-
    # level key), so a new key here needs no frontend change at all. "moe"
    # split out of the old flat "chat" list rather than staying folded into
    # it: a MoE model's RAM/speed trade-off (see its own comment below) is
    # different enough from a dense model's that grouping them together
    # under one label was misleading, not just imprecise.
    # Sizes below were checked against the live Ollama library this session
    # (this file previously had no way to do that, see the vision/ocr
    # groups' own history). Two real tag mistakes, not just size drift, came
    # out of it: "qwen3.5:8b" doesn't exist (the real tag between 4b and 27b
    # is 9b) and "gemma4:26b-a4b" doesn't exist as a plain tag (the model is
    # a MoE *by construction* under the bare "gemma4:26b" tag: the "-a4b"
    # suffix belongs to a more specific quantisation variant, not the
    # ordinary pull). Both would have 404'd for anyone who tried them.
    "text": [
        # --- runs on almost anything, no GPU needed ---
        {"name": "qwen3.5:2b", "size": "~2.7 GB", "purpose": "The lightest one genuinely worth using"},
        {"name": "llama3.2", "size": "~2.0 GB", "purpose": "Fast all-rounder: the default, and a good first choice"},
        {"name": "granite4.1:3b", "size": "~2.1 GB", "purpose": "Strong instruction-following at a small size"},
        {"name": "qwen3.5:4b", "size": "~3.4 GB", "purpose": "Follows instructions closely: good for agent mode"},
        # --- 8 GB of RAM, or any modern GPU ---
        {"name": "llama3.1:8b", "size": "~4.9 GB", "purpose": "Better reasoning and reliable tool calls"},
        {"name": "qwen3.5:9b", "size": "~6.6 GB", "purpose": "Best tool use at this size. Thinks, so slower per answer"},
        {"name": "mistral-nemo", "size": "~7.1 GB", "purpose": "Long-document work: a large context window"},
        {"name": "gemma4:12b", "size": "~7.6 GB", "purpose": "Long-form writing and summarising"},
    ],
    # Mixture-of-experts: big download, small working set. These need the
    # RAM of the model they are named after and run at roughly the speed of
    # the *active* half: 26b holds 26B of weights and computes with roughly
    # 4B of them (it is a MoE model by construction under its own bare tag,
    # not a separate "-a4b" variant: see the note above this dict). That is
    # the one thing worth explaining about them, because judged on download
    # size alone nobody with 16 GB would try one, and they are the best
    # answer for that machine.
    "moe": [
        {"name": "gemma4:e2b", "size": "~7.2 GB", "purpose": "MoE: 2B-class speed with more capability. Try it if bigger models are too slow"},
        {"name": "gemma4:e4b", "size": "~9.6 GB", "purpose": "MoE: noticeably more capable + better writing than the e2b"},
        # Unsloth's quantisation-aware-training GGUFs of the same two models,
        # asked for by name. QAT means the model was fine-tuned *while*
        # quantised rather than squashed afterwards, so a 4-bit copy holds up
        # better than an ordinary 4-bit of the same weights; the point of
        # having them beside the bare tags is that they are roughly half the
        # download for close to the same answers. `hf.co/…` because neither is
        # in Ollama's curated library, the same shape the vision and ocr
        # groups already use for that situation, and the UD-Q4_K_XL tag is
        # Unsloth's own dynamic quant rather than a plain Q4.
        {"name": "hf.co/unsloth/gemma-4-E2B-it-qat-GGUF:UD-Q4_K_XL", "size": "~4.0 GB",
         "purpose": "MoE, quantisation-aware 4-bit: e2b answers at roughly half the download"},
        {"name": "hf.co/unsloth/gemma-4-E4B-it-qat-GGUF:UD-Q4_K_XL", "size": "~5.3 GB",
         "purpose": "MoE, quantisation-aware 4-bit: e4b answers at roughly half the download"},
        # `label`: what the card prints. The pull tag stays "gemma4:26b" (the
        # model is the 26B-A4B one: 26B of weights, about 4B active per word).
        {"name": "gemma4:26b", "label": "gemma4:26b (a4b)", "size": "~19 GB", "purpose": "MoE (a4b): 26B of weights, about 4B working at a time, so far better answers than its speed suggests. Needs ~16 GB", "ram_gb": 16},
        {"name": "qwen3.5:35b-a3b", "size": "~21 GB", "purpose": "MoE: the most capable here, still quick. Needs ~24 GB", "ram_gb": 24},
    ],
    "embedding": [
        {"name": "nomic-embed-text", "size": "~274 MB", "purpose": "Solid general-purpose embeddings"},
        {"name": "mxbai-embed-large", "size": "~670 MB", "purpose": "Higher quality, a little slower"},
        {"name": "bge-m3", "size": "~1.2 GB", "purpose": "Better on long notes and mixed languages"},
    ],
    # Any of these can be picked as the explicit vision-model override in
    # Settings → Models (ModelManager.vision_model()), for chat image
    # captions (ai/captioning.py) and image-carrying chat turns
    # (routes_chat._chat_model_sees_images). Asked for directly.
    #
    # **qwen3-vl's tags were unconfirmed when this list was first written (no
    # live registry access) and have since been checked against the real
    # Ollama library (ollama.com/library/qwen3-vl/tags): 2b/4b/8b/30b/32b/235b
    # all exist, so the hedge on those three entries is gone.** lfm2.5-vl is
    # the opposite finding: checked, and it is **not** a bare Ollama library
    # tag the way qwen3-vl's are: `ollama.com/library/lfm2.5-vl` does not
    # exist (only `lfm2.5`, the text-only sibling, is in the curated
    # library), so the entry below now pulls the GGUF straight from the
    # publisher's own Hugging Face repo, the same `hf.co/…` shape the OCR
    # group below already uses for exactly this situation. glm-4v and
    # deepseek-vl2 were asked about by name but are still not included at
    # all: neither is published under any tag on Ollama's library or as a
    # findable GGUF repo, and this file's own "fails safely" rule (a stale
    # *tag* just 404s cleanly) does not cover suggesting a model that was
    # never offered in the first place.
    "vision": [
        {"name": "moondream", "size": "~1.7 GB", "purpose": "Tiny and fast: the one to try on modest hardware"},
        {"name": "hf.co/LiquidAI/LFM2.5-VL-1.6B-GGUF", "size": "~1.6 GB", "purpose": "Liquid's small vision model, not in Ollama's own library, pulled from its publisher's Hub repo instead"},
        {"name": "qwen3-vl:2b", "size": "~1.9 GB", "purpose": "Smallest of the Qwen-VL line"},
        {"name": "qwen2.5vl:3b", "size": "~2.2 GB", "purpose": "A fallback for the 2B/4B Qwen3-VL entries either side of it, if either is ever pulled from Ollama's library and not this catalogue"},
        {"name": "qwen3-vl:4b", "size": "~3.3 GB", "purpose": "A step up from the 2B"},
        {"name": "minicpm-v", "size": "~5.5 GB", "purpose": "Notably strong at reading text in images"},
        {"name": "llava", "size": "~4.7 GB", "purpose": "General-purpose vision, the longest-established option"},
        {"name": "qwen2.5vl:7b", "size": "~6.0 GB", "purpose": "Strong all-round vision and text reading"},
        {"name": "qwen3-vl:8b", "size": "~6.1 GB", "purpose": "The largest of the small Qwen3-VL tags"},
        {"name": "qwen2.5vl:32b", "size": "~21 GB", "purpose": "The most capable here. Needs ~24 GB", "ram_gb": 24},
    ],
    # Document readers, as opposed to the general vision models above. Asked
    # for by name (deepseek-ocr, glm-ocr, qwen3-vl).
    #
    # **These entries were checked against the live Hugging Face Hub**, unlike
    # the "unconfirmed tag" notes on the vision list above, that session had
    # no registry access and said so. Downloads and file sizes below are read
    # from the repos themselves, so a 404 here would be a repo being deleted
    # rather than a name this file guessed at.
    #
    # `hf.co/…` rather than a bare Ollama tag: Ollama pulls a GGUF straight
    # from the Hub with `ollama pull hf.co/{repo}:{quant}`, and none of these
    # are in Ollama's own curated library. Sizes are the weights plus the
    # mmproj projector that a vision GGUF needs alongside them, Ollama fetches
    # both from the same repo, and quoting only the weights would understate
    # every one of these by several hundred megabytes.
    #
    # Why a separate category rather than more "vision" entries: a general VLM
    # is asked "what is in this picture", and a document reader is asked "give
    # me the text, the tables and the layout". The second is what
    # core/docview.py's scanned-page path wants, and picking moondream for it
    # gets a description of a page instead of the page.
    "ocr": [
        {"name": "hf.co/ggml-org/GLM-OCR-GGUF:Q8_0", "size": "~1.4 GB",
         "purpose": "Best size-to-accuracy here. Tables and layout, 8 languages, start with this one"},
        {"name": "hf.co/PaddlePaddle/PaddleOCR-VL-1.6-GGUF:Q8_0", "size": "~1.8 GB",
         "purpose": "Layout, tables, formulas, charts. Strong on structured pages"},
        {"name": "hf.co/unsloth/Qwen3-VL-4B-Instruct-GGUF:Q4_K_M", "size": "~2.5 GB",
         "purpose": "Reads documents and answers about them, a VLM as well as a reader"},
        {"name": "hf.co/ggml-org/DeepSeek-OCR-GGUF:Q8_0", "size": "~3.6 GB",
         "purpose": "The most accurate on dense and handwritten pages. Needs ~8 GB", "ram_gb": 8},
    ],
}


#: Families whose whole purpose is reading a page, rather than describing a
#: picture. Derived from the `ocr` group above and kept beside it, so adding an
#: entry there is enough to make auto-detect prefer it.
#:
#: Matched as substrings of a lowercased model name because the same weights
#: arrive under many spellings, `glm-ocr`, `hf.co/ggml-org/GLM-OCR-GGUF:Q8_0`,
#: `GLM-OCR:latest`, and the family is the part that never changes.
OCR_MODEL_MARKERS: tuple[str, ...] = (
    "glm-ocr", "glm_ocr",
    "deepseek-ocr", "deepseek_ocr",
    "paddleocr", "paddle-ocr",
    "olmocr", "olm-ocr",
    "got-ocr", "nanonets-ocr", "dots.ocr", "minicpm-o",
)


def is_ocr_model(name: str) -> bool:
    """Is this model a document reader rather than a general vision model?

    Deliberately not "does the name contain 'ocr'": `qwen2.5vl` reads text
    perfectly well and contains no such string, while a chat model called
    `ocr-helper` is not one. A named-family list is wrong in a way that is
    visible and fixable; a substring rule is wrong in a way that is not.
    """
    lowered = (name or "").lower()
    return any(marker in lowered for marker in OCR_MODEL_MARKERS)


#: Below this many billion parameters, a model is "small" for the purposes of
#: how much is asked of it in one turn. 8B is where tool calling stops being a
#: coin flip in this app's own use: the 4B models in the catalogue above narrate
#: instead of calling, and the 8B entries are described there as "reliable tool
#: calls" for exactly that reason. A threshold, not a cliff, everything it
#: gates is a *simplification*, so being wrong in either direction costs
#: clarity rather than capability.
SMALL_MODEL_PARAMS_B = 8.0

#: `qwen3.5:4b`, `granite4.1:3b`, `llama-3.2-3b-instruct`, `qwen3.5:35b-a3b`.
#: The size is written into the tag rather than reported by the API, which is
#: why this is a name rule: reading it costs nothing, works before the model
#: has ever been loaded, and works for every provider the app can talk to
#: (`/api/show` is Ollama's, and llama.cpp/Jan/vLLM answer nothing like it).
_PARAM_TAG = re.compile(r"(?:^|[:\-_/])(\d{1,3}(?:\.\d)?)\s*b(?![a-z0-9])", re.IGNORECASE)


def parameter_count(name: str) -> float | None:
    """Billions of parameters, read off the model's own name: or None.

    **None means "no idea", and every caller has to treat it as such.** A
    model called `llama3.2` genuinely is a 3B, and this returns None for it,
    because the alternative is guessing from a family name and a version
    number that shifts every release. Silence is the honest answer, and the
    one setting that reads this defaults to off when it gets one: narrowing a
    capable model's toolbox on a guess is worse than leaving a small model
    with the full set it was coping with yesterday.

    A mixture-of-experts tag (`qwen3.5:35b-a3b`) reports the *first* number,
    which is the total rather than the active count, deliberate: what the
    active-parameter count predicts is speed, and what this is asked about is
    instruction-following, which tracks the total far better.
    """
    match = _PARAM_TAG.search(str(name or ""))
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:  # pragma: no cover: the regex only matches numbers
        return None


def is_small_model(name: str) -> bool | None:
    """Is a model of this name small enough to need the simplified treatment?

    True / False / **None for "the name doesn't say"**, and the three states
    matter: a caller that collapses None into True narrows every run on an
    unrecognised name, one that collapses it into False never turns on for the
    models this exists for. Every caller in the app treats None as off and
    says so where it does.

    Split out of `ModelManager.chat_model_is_small` (which now calls it) for
    the agent loop: `run_agent` may be running the utility model or an
    explicit override rather than the chat model, so it has to ask about the
    model it is *actually* about to call, not about the preference.
    """
    size = parameter_count(name)
    return None if size is None else size < SMALL_MODEL_PARAMS_B


# --- a model per feature (asked for directly) ---------------------------------
#
# *"allow the user to alter the model they use for that specific feature if
# they wish such as for the write with ai area, the chat tab and document ai
# assistant."*
#
# **A second layer over the roles above, not a replacement for them.** The
# roles (chat, utility, vision, ocr, embedding) say what *kind* of job a model
# is for; a feature override says "this one surface runs on that model". So a
# feature never gets a setting, a route and a control of its own: it gets one
# row in this table naming the role it falls back to, and everything else,
# reading, setting, clearing, the mass reset, Settings' own list and the
# inline picker, is generic over the table. Adding the next feature is a row.
#
# The fallback is a *role*, not a model name, and that is the decision the
# whole thing rests on (decision 5): an unset feature stores nothing and
# resolves through its role at read time. Storing the resolved name instead
# would look identical on the day it was written and then silently leave every
# untouched feature behind on the old model the first time the chat model is
# changed in Settings, with nothing on screen connecting the two events.


@dataclass(frozen=True)
class Feature:
    """One surface that may run on a model of its own."""

    key: str
    #: What Settings calls it. Sentence case, and it names the surface the
    #: user can point at rather than the module behind it.
    label: str
    #: "chat" or "utility": the role getter this feature's override replaces,
    #: and the model it inherits when there is no override.
    role: str
    #: One line for the Settings row, the rest of the explanation belongs in
    #: the section's own '?' popover (DESIGN.md's help recipe).
    note: str


#: The first pass. Three surfaces were named in the ask; the Guide is here
#: because it is the same shape exactly, one surface, one model call, one role
#: to fall back to.
#:
#: **The skills runner is deliberately not a row.** It looked like a fourth
#: candidate and is not: a skill run goes through `agent.run_agent`, the same
#: loop the chat tab's agent mode uses and on the same `chat_model()`, so a
#: "skills" row would have moved only `skill_runner._replan`'s small recovery
#: call and left the model that actually runs every step exactly where it was.
#: A control that changes a thing next to the thing it names is worse than no
#: control. Giving skills a real model of their own means giving `run_agent` a
#: feature of its own to run under, which is a bigger change than this one and
#: belongs in AGENT_SKILLS_REFORM rather than half-done here.
FEATURES: tuple[Feature, ...] = (
    Feature(
        key="chat",
        label="Chat tab",
        role="chat",
        note="Answers in the Chat tab, including agent mode.",
    ),
    #: The Notes tab's Ask box. It shares `/chat/stream` with the Chat tab
    #: and ran on the row above without saying so; a model picker on the Ask
    #: box (the owner, 2026-09-23: "a model dropdown which pairs with the
    #: feature-specific model selections in settings") would then have moved
    #: the Chat tab too. Told apart by `notes_only`, which only the Ask box
    #: sends (`routes_chat._feature_for`).
    Feature(
        key="ask",
        label="Ask tab",
        role="chat",
        note="Answers to questions about your notes in the Ask tab.",
    ),
    Feature(
        key="writing",
        label="Writing room",
        role="chat",
        note="Drafts and revisions on the Notes tab's writing desk.",
    ),
    Feature(
        key="documents",
        label="Document AI assistant",
        role="chat",
        note="Edit, write and remove inside a document.",
    ),
    Feature(
        key="guide",
        label="Guide",
        role="utility",
        note="The help panel that answers questions about this app.",
    ),
)

FEATURES_BY_KEY: dict[str, Feature] = {feature.key: feature for feature in FEATURES}

#: One preference per feature, and an absent or empty value means inherited.
#: Prefixed so `reset_feature_models` and the support bundle can find them all
#: without a second list to keep in step with the table above.
FEATURE_PREF_PREFIX = "feature_model_"

#: **Sentinels, not model names** (INBOX 430: "each feature's select also
#: offers 'Same as chat model' and 'Same as utility model', which follow
#: those settings when they change"). A feature's stored override is usually
#: a specific model, frozen until someone changes it again; these two mean
#: "whatever the chat/utility model setting currently is", re-read live every
#: time the feature resolves rather than copied in at the moment they were
#: picked. That is different from plain "inherited" (an empty override):
#: inherited follows the *role* the feature already falls back to (Guide's
#: role is utility, so its own "Inherited" already tracks the utility
#: model), while these let a feature follow the *other* role's setting on
#: purpose, chat's writing desk pinned to the small utility model, say.
#: Double-underscored so nothing an Ollama registry hands back can ever
#: collide with one (real tags are `name[:tag]`, never a bare `__word__`).
FOLLOW_CHAT_MODEL = "__follow_chat_model__"
FOLLOW_UTILITY_MODEL = "__follow_utility_model__"
FOLLOW_SENTINELS = (FOLLOW_CHAT_MODEL, FOLLOW_UTILITY_MODEL)


def feature_pref_key(feature: str) -> str:
    return f"{FEATURE_PREF_PREFIX}{feature}"


def known_feature(feature: str) -> Feature:
    """The row, or `ValueError`.

    Refused rather than stored: a typo'd key would otherwise save a preference
    nothing ever reads, and the surface it was meant for would go on running
    the global model while Settings showed the override as applied.
    """
    row = FEATURES_BY_KEY.get(feature)
    if row is None:
        logging.getLogger("tessellate.models").warning("no per-feature model for %s", safe_value(feature, 60))
        raise ValueError("That part of the app doesn't have a model of its own to pick.")
    return row


class ModelManager:
    """Reads/writes the active-model preferences."""

    def __init__(self, config: ConfigManager, feature: str | None = None) -> None:
        self._config = config
        #: Which feature's work this manager is answering for, or None for the
        #: app's own preferences. A *view*, not a mode: `for_feature` hands
        #: back a second manager over the same config rather than setting a
        #: flag on this one, so nothing that holds a manager can have the
        #: model it resolves changed underneath it by something elsewhere.
        #:
        #: This is the whole seam. Every module downstream, the agent loop,
        #: the drafter, the help chat, goes on calling `chat_model()` and
        #: `utility_model()` and knows nothing about features; a route hands
        #: it the view for its own surface and the right model arrives.
        self._feature = feature

    def for_feature(self, feature: str) -> "ModelManager":
        """This manager, answering as one feature (decision 1)."""
        known_feature(feature)
        return ModelManager(self._config, feature)

    def _override_for_role(self, role: str) -> str:
        """This view's override, if it replaces *this* role.

        A feature's override lands on the getter for the role it falls back
        to, and only that one. So the Guide, whose role is utility, moves its
        own `utility_model()` and leaves `chat_model()` alone: a surface that
        happens to also use the other role keeps using the app's choice for
        it, which is the honest reading of "the model this feature runs on".
        """
        if not self._feature:
            return ""
        row = FEATURES_BY_KEY.get(self._feature)
        if row is None or row.role != role:
            return ""
        raw = str(self._config.get_preference(feature_pref_key(self._feature), "") or "")
        return self._resolve_override(raw)

    def _resolve_override(self, raw: str) -> str:
        """A stored override, resolved to a real model name or "".

        A plain name passes straight through; a `FOLLOW_*` sentinel is
        resolved through a **plain, feature-less manager**, never through
        `self`, so this reads the app's current chat/utility setting itself
        rather than another feature's override on top of it, and so it is
        re-read every call instead of being fixed to whatever that setting
        was when the sentinel was chosen (the whole point of the sentinel
        over just copying the name in at picker time).
        """
        if raw == FOLLOW_CHAT_MODEL:
            return ModelManager(self._config).chat_model()
        if raw == FOLLOW_UTILITY_MODEL:
            return ModelManager(self._config).utility_model()
        return raw

    # --- feature overrides, read and written through the app's own manager ---

    def feature_override(self, feature: str) -> str:
        """The stored override, or "" for inherited. Never a resolved name."""
        known_feature(feature)
        return str(self._config.get_preference(feature_pref_key(feature), "") or "")

    def feature_model(self, feature: str) -> str:
        """The model this feature would actually run on right now."""
        row = known_feature(feature)
        view = self.for_feature(feature)
        return view.chat_model() if row.role == "chat" else view.utility_model()

    def set_feature_model(self, feature: str, name: str) -> None:
        """Point one feature at a model. An empty name clears the override."""
        known_feature(feature)
        self._config.set_preference(feature_pref_key(feature), (name or "").strip())

    def clear_feature_model(self, feature: str) -> None:
        self.set_feature_model(feature, "")

    def reset_feature_models(self) -> int:
        """Clear every feature override, and say how many there were.

        The count is the point: the mass reset in Settings says what it is
        about to undo, and does nothing when the answer is nothing, rather
        than reporting success over a no-op.
        """
        cleared = 0
        for feature in FEATURES:
            if self.feature_override(feature.key):
                self.clear_feature_model(feature.key)
                cleared += 1
        return cleared

    def feature_rows(self) -> list[dict]:
        """One row per feature, resolved, for Settings and the inline picker.

        Every row carries both facts the UI needs to draw it: the model in
        use, and whether that is this feature's own choice or the role's. A
        row that only carried the name would make "inherited" unsayable.
        """
        rows = []
        for feature in FEATURES:
            override = self.feature_override(feature.key)
            #: Resolved through a plain manager, never through `self`: a view
            #: asked for the rows would otherwise report its own override as
            #: what every row inherits.
            plain = ModelManager(self._config)
            inherits = plain.chat_model() if feature.role == "chat" else plain.utility_model()
            #: What kind of override this is, so the UI can draw the right
            #: option as selected: a `FOLLOW_*` sentinel is not a model name
            #: to show in a select, it is a *third state* alongside "on its
            #: own model" and "inherited" (INBOX 430). `override_value` is
            #: only ever a plain name, never a sentinel, so a caller that
            #: forgets `override_kind` and just prints the value cannot show
            #: the raw sentinel string by accident.
            if not override:
                kind = ""
            elif override == FOLLOW_CHAT_MODEL:
                kind = "chat"
            elif override == FOLLOW_UTILITY_MODEL:
                kind = "utility"
            else:
                kind = "model"
            rows.append(
                {
                    "key": feature.key,
                    "label": feature.label,
                    "note": feature.note,
                    "role": feature.role,
                    "model": self._resolve_override(override) or inherits,
                    "inherits": inherits,
                    "overridden": bool(override),
                    "override_kind": kind,
                    "override_value": override if kind == "model" else None,
                }
            )
        return rows

    def chat_model(self) -> str:
        return self._override_for_role("chat") or self._config.get_preference(
            "chat_model", "llama3.2"
        )

    def served_chat_model(self, provider) -> str:  # noqa: ANN001
        """The chat model the server answers with, for "Answering with"
        (`served_name`); the configured name when the server cannot say."""
        configured = self.chat_model()
        try:
            listed = provider.list_models()
        except Exception:  # noqa: BLE001  # an unreachable list names nothing new
            return configured
        return served_name(configured, listed if isinstance(listed, list) else [])

    def chat_model_is_small(self) -> bool | None:
        """Is the chat model small enough to need the simplified treatment?

        True / False / **None for "the name doesn't say"**, the three states
        matter, the same way `OllamaClient.supports` keeps them apart. A caller
        that collapses None into True narrows every run on an unrecognised
        name; one that collapses it into False never turns on for the models
        this exists for. The one caller (`small_model_mode` = "auto") treats
        None as off and says so.
        """
        return is_small_model(self.chat_model())

    def utility_model(self) -> str:
        """The model for quick background jobs, filing (janitor), the
        weekly digest, tidy suggestions, writing fixes. Defaults
        to the chat model, but the user can point it at a small fast model
        so the big chat model isn't tied up categorising every note."""
        #: An explicit feature override is asked about first, and before the
        #: routing switch. Routing off means "background jobs use the chat
        #: model", which is a default about jobs nobody chose a model for; a
        #: surface the user pointed at a model by hand is not one of those.
        return self.utility_resolution()[0]

    def utility_resolution(self) -> tuple[str, str]:
        """The utility model in use, and why it is that one.

        The reason is one of `override` (this feature's own choice),
        `routing_off` (smart model routing is off, so background jobs share
        the chat model whatever is stored), `unset` (nothing chosen, so the
        chat model) or `chosen`. INBOX 277: Settings used to show only the
        stored preference, and a role that says one model and runs another,
        silently, is how a correct Guide got a bug filed against it. Kept as
        the one place the decision is made, so `utility_model()` and what
        Settings prints cannot disagree.
        """
        override = self._override_for_role("utility")
        if override:
            return override, "override"
        #: The switch moves background jobs; the Guide is a panel you type
        #: into, so it keeps the utility model whatever the switch says (the
        #: owner's decision, 2026-09-24, WORLD_CLASS_PLAN section 20).
        if (
            not self._config.get_preference("smart_model_routing_enabled", True)
            and self._feature != "guide"
        ):
            return self.chat_model(), "routing_off"
        chosen = self._config.get_preference("utility_model", "")
        if not chosen:
            return self.chat_model(), "unset"
        return chosen, "chosen"

    def set_utility_model(self, name: str) -> None:
        # Empty string means "same as chat model".
        self._config.set_preference("utility_model", name or "")

    def vision_model(self) -> str:
        """The explicit vision-model override, or "" for auto-detect.

        Deliberately the *opposite* default from `utility_model()` above:
        every other model preference in this app falls back to "same as
        chat model" when unset, because that is a safe default, the chat
        model can always do the job the utility model does. A chat model
        cannot always see images, so falling back to it here would silently
        turn "attach a photo" into "attach a photo the model ignores" on
        any notebook that hasn't touched this setting. Auto-detect is the
        default specifically *because* it is the useful zero-config
        behaviour for this one preference; a specific model name is an
        explicit choice on top of it, not a second default."""
        return self._config.get_preference("vision_model", "")

    def set_vision_model(self, name: str) -> None:
        # Empty string means "auto-detect", see resolve_vision_model.
        self._config.set_preference("vision_model", name or "")

    def resolve_vision_model(self, ollama, installed: list[dict] | None = None) -> str | None:
        """The model an image-carrying turn should actually use, or None if
        nothing on this backend can.

        An explicit choice always wins, even one `installed` doesn't confirm
        is on disk right now, the same trust `chat_model()` already extends
        (routes_models.py surfaces "not installed" as its own warning rather
        than silently substituting something else). Auto-detect (the
        default) asks each installed model's declared capabilities in turn
        and stops at the first `True`; `OllamaClient.capabilities()` caches
        per model per process, so this costs one real round trip per model
        at most once, not once per chat turn."""
        explicit = self.vision_model()
        if explicit:
            return explicit
        if installed is None:
            try:
                installed = ollama.list_models()
            except OllamaError:
                installed = []
        supports = getattr(ollama, "supports", None)
        if not callable(supports):
            return None
        for entry in installed:
            name = entry.get("name") if isinstance(entry, dict) else None
            if name and supports(name, "vision"):
                return name
        return None

    def ocr_model(self) -> str:
        """The explicit model for *reading text off a page*, or "" for auto.

        Separate from `vision_model` because the two jobs are separate, which
        is not obvious and was asked about directly. Rasterising a PDF does not
        read anything: it turns a page into a picture, and a model still has
        to read the picture. So the same *kind* of model handles a photo and a
        scanned page; what differs is which one is good at it:

        - A general VLM (moondream, llava, qwen2.5vl) is trained to answer
          "what is in this image". Ask it for a scanned invoice and it will
          often describe the invoice instead of transcribing it.
        - A document reader (GLM-OCR, DeepSeek-OCR, PaddleOCR-VL: the `ocr`
          group in SUGGESTED_MODELS) is trained to return the text, the tables
          and the layout, and is usually far smaller for that job.

        Hence three tiers rather than two, and the order matters: an explicit
        OCR model, else an installed document-reader model auto-detected by
        family name, else the vision model the user already chose (if any),
        else whatever else can see. Requiring an OCR model before any OCR
        works would make this a setting people must find before the feature
        does anything, hence the auto-detect tier existing at all.

        The auto-detected reader now outranks an explicit-but-unrelated
        vision-model choice, reversed from an earlier version of this
        function that had it the other way, reported live, directly
        against what that version assumed: "I pressed read text with AI,
        but it used my vision model and not my OCR model" from someone who
        had a real OCR-family model installed and a vision model set for
        chat, never an OCR model. Deferring to the *explicit* choice sounded
        right in the abstract, but in practice it means a document reader
        sitting right there in the installed list is never used for the one
        job it's actually built for, on the strength of a setting that was
        made for an unrelated purpose (chat). An explicit OCR model still
        wins outright: that one really is the deliberate, on-purpose case.
        """
        return self._config.get_preference("ocr_model", "")

    def set_ocr_model(self, name: str) -> None:
        self._config.set_preference("ocr_model", name or "")

    def resolve_ocr_model(
        self,
        ollama,
        installed: list[dict] | None = None,
        vision_fallback: str | None = None,
    ) -> str | None:
        """The model that should read text off an image or a rasterised page.

        See `ocr_model` for why this is not simply `resolve_vision_model`.
        """
        explicit = self.ocr_model()
        if explicit:
            return explicit

        # No explicit OCR model. Asked directly: "what if I have qwen3-vl and
        # glm-ocr available?", and plain vision auto-detect answers that
        # badly, by taking whichever the backend happens to list first. Both
        # can see an image; only one of them is built to transcribe a page.
        # Tried before the vision-model fallback below, not after, see this
        # function's own docstring for why that order flipped.
        #
        # Matched on the family names in SUGGESTED_MODELS["ocr"] rather than
        # on capabilities, because no backend reports "good at OCR", 
        # `capabilities` says `vision` for both, which is exactly why the tie
        # needed breaking here.
        if installed is None:
            try:
                installed = ollama.list_models()
            except OllamaError:
                installed = []
        names = [
            entry.get("name")
            for entry in (installed or [])
            if isinstance(entry, dict) and entry.get("name")
        ]
        for name in names:
            if is_ocr_model(name):
                return name

        # No reader installed. An explicit *vision* model is still a
        # deliberate choice and beats guessing among whatever else can see.
        if self.vision_model():
            return self.vision_model()
        #
        # `vision_fallback` is for the caller that has already resolved it.
        # Resolving it here walks every installed model asking `/api/show`
        # whether it can see, one HTTP round trip each, cached per process but
        # cold on the first poll. `/models/status` needs both answers, and
        # deriving them independently made that poll slow enough to trip the
        # frontend's own 5s abort: reported as
        # `GET /models/status: signal timed out`.
        if vision_fallback is not None:
            return vision_fallback or None
        return self.resolve_vision_model(ollama, installed)

    def embedding_backend(self) -> str:
        """'sentence-transformers' (built-in default) or 'ollama'."""
        return self._config.get_preference("embedding_backend", "sentence-transformers")

    def embedding_model(self) -> str:
        """Only meaningful when the backend is 'ollama'."""
        return self._config.get_preference("embedding_model", "nomic-embed-text")

    def embedding_st_model(self) -> str:
        """The built-in backend's model (INBOX 700), a repo from the allowlist
        in `core/embedmodels.py`. Anything else in the preference, an entry
        since removed or one not offered in one press, reads as the default:
        a repo id is a download, never free text."""
        from tessellate.core import embedfind, embedmodels

        chosen = self._config.get_preference("embedding_st_model", embedmodels.DEFAULT_REPO)
        entry = embedmodels.EMBED_MODELS_BY_REPO.get(chosen)
        if entry is not None:
            return chosen if entry.one_press else embedmodels.DEFAULT_REPO
        #: Or one found on this disk that the engine loads as it is (the
        #: owner's addendum to 700), checked again here: a folder deleted
        #: since reads as the default rather than a model that is not there.
        if isinstance(chosen, str) and chosen and embedfind.usable_repo(chosen):
            return chosen
        return embedmodels.DEFAULT_REPO

    def set_chat_model(self, name: str) -> None:
        # Chat model switches apply instantly, no re-index needed (§6.5).
        self._config.set_preference("chat_model", name)

    def set_embedding_backend(self, backend: str, model: str | None = None) -> None:
        # The caller MUST kick off a re-index after this, vectors from
        # different models are not comparable (§6.5).
        self._config.set_preference("embedding_backend", backend)
        if model and backend == "ollama":
            self._config.set_preference("embedding_model", model)
        elif model:
            self._config.set_preference("embedding_st_model", model)


# --- background jobs ---------------------------------------------------------
# Simple module-level state: this is a single-process, single-user app.


@dataclass
class Job:
    kind: str  # "reindex" or "pull"
    name: str = ""  # model name for pulls
    total: int = 0  # entries (reindex) or bytes (pull)
    done: int = 0
    status: str = "running"  # running | success | error | cancelled
    error: str = ""
    cancel_requested: bool = False  # cooperative stop (tasks manager)

    def as_dict(self) -> dict:
        return {
            "kind": self.kind,
            "name": self.name,
            "total": self.total,
            "done": self.done,
            "status": self.status,
            "error": self.error,
        }


_lock = threading.Lock()
_reindex_job: Job | None = None
_pull_jobs: dict[str, Job] = {}


def reset_jobs() -> None:
    """Forget finished/failed job records, used between tests."""
    global _reindex_job
    with _lock:
        _reindex_job = None
        _pull_jobs.clear()


def reindex_status() -> dict | None:
    with _lock:
        return _reindex_job.as_dict() if _reindex_job else None


def pull_statuses() -> dict[str, dict]:
    with _lock:
        return {name: job.as_dict() for name, job in _pull_jobs.items()}


def cancel_reindex() -> bool:
    """Ask a running re-index to stop. Cooperative: the worker
    checks the flag between entries. Returns True if one was running."""
    with _lock:
        if _reindex_job is not None and _reindex_job.status == "running":
            _reindex_job.cancel_requested = True
            return True
    return False


def cancel_pull(name: str) -> bool:
    """Ask a running download to stop."""
    with _lock:
        job = _pull_jobs.get(name)
        if job is not None and job.status == "running":
            job.cancel_requested = True
            return True
    return False


def start_reindex(db: DatabaseManager, embeddings: Embedder) -> bool:
    """Regenerate every non-deleted entry's embedding with the current
    backend, in a background thread. Returns False if one is already
    running. While it runs, old vectors no longer match the new
    backend_id, so semantic search safely falls back to keyword search
    until each entry is re-embedded (§6.5)."""
    global _reindex_job
    with _lock:
        if _reindex_job is not None and _reindex_job.status == "running":
            return False
        _reindex_job = Job(kind="reindex")
        job = _reindex_job
    # On the pool's `batch` lane (F7): one worker, a session of its own
    # (`_reindex_pass` opens it), and the activity panel's row is still the
    # job's own (`reindex_status`), so the pool keeps it off its list.
    from tessellate.core import jobs

    #: Durable (Brief 9) when it is the app's own notebook and embedder: the
    #: row then names `reindex_notebook`, which a launch after a kill runs
    #: again (re-embedding is idempotent: each note's vector is replaced).
    #: Any other pair (a test's fake, a script's database) runs as before
    #: and is not remembered, since a resumed row could not find it.
    if _is_app_pair(db, embeddings):
        queued = jobs.enqueue("reindex", reindex_notebook, name="reindex", dedupe_key="reindex")
    else:
        queued = jobs.enqueue("reindex", _run_reindex, db, embeddings, job, name="reindex")
    if not queued:
        with _lock:
            job.status = "error"
            job.error = "The app is shutting down."
        return False
    return True


#: The running app's own db, embedder and model client, filled in by
#: `core/deps.py` when it loads (this module cannot import deps: deps imports
#: it, and the import-cycle lint counts a function-body import too).
APP_GETTERS: dict = {}


def _is_app_pair(db: object, embeddings: object) -> bool:
    """True when `db` and `embeddings` are the running app's own, the only
    ones a durable job can find again by name after a restart."""
    try:
        return db is APP_GETTERS["db"]() and embeddings is APP_GETTERS["embeddings"]()
    except Exception:  # noqa: BLE001  # no app state: a script or a test
        return False


def reindex_notebook() -> None:
    """The durable re-index (Brief 9, `jobstore.HANDLERS["reindex"]`): the
    app's notebook and embedder, looked up when it runs. A row resumed at
    launch has no registry entry yet, so it makes one for the panel."""
    global _reindex_job
    with _lock:
        if _reindex_job is None or _reindex_job.status != "running":
            _reindex_job = Job(kind="reindex")
        job = _reindex_job
    _run_reindex(APP_GETTERS["db"](), APP_GETTERS["embeddings"](), job)


def _run_reindex(db: DatabaseManager, embeddings: Embedder, job: Job) -> None:
    """The thread body: the pass itself, recorded as the last "reindex" run
    (INBOX 438). The pass catches its own errors for the job registry, so it
    tells `run` about them rather than raising."""
    with jobruns.job_run("reindex", db=db) as run:
        _reindex_pass(db, embeddings, job, run)


def _reindex_pass(
    db: DatabaseManager, embeddings: Embedder, job: Job, run: "jobruns.Run"
) -> None:
    started = time.monotonic()
    session = db.session()
    try:
        # The keyword index first: it is the fast half (no model call per
        # note), it is what search answers from while the vectors below are
        # being redone, and until this it could not be rebuilt at all short of
        # deleting its table. A failure here is logged and the re-embed still
        # runs, because half a rebuild is better than none.
        from tessellate.search import index as search_index

        try:
            search_index.rebuild(session)
            session.commit()
        except Exception:  # noqa: BLE001  # see above
            session.rollback()
            logging.getLogger("tessellate.search").warning(
                "keyword index rebuild failed", exc_info=True
            )
        entries = list(
            session.scalars(select(Entry).where(Entry.is_deleted == False))  # noqa: E712
        )
        job.total = len(entries)
        #: `ai/embeddings.py`'s batch size, read from the loaded module (it is
        #: always loaded by the time a re-index runs): an import of it here,
        #: even inside the function, is the cycle `tests/test_no_import_cycles.py`
        #: counts, since that module imports this one.
        import sys

        EMBED_BATCH = int(getattr(sys.modules.get("tessellate.ai.embeddings"), "EMBED_BATCH", 16))

        #: A stand-in that only knows `store_for_entry` (the contract `Embedder`
        #: states, and what the tests pass) is walked one note at a time.
        store_batch = getattr(embeddings, "store_for_entries", None)
        for start in range(0, len(entries), EMBED_BATCH):
            if job.cancel_requested:  # user quit it from the tasks manager
                job.status = "cancelled"
                run.cancel(f"stopped after {job.done} of {job.total} notes")
                taskhistory.record(
                    "reindex",
                    "Re-indexing your notes",
                    "cancelled",
                    f"stopped after {job.done} of {job.total}",
                    duration_ms=(time.monotonic() - started) * 1000,
                )
                return
            batch = entries[start : start + EMBED_BATCH]
            # Drop the stale vectors first so a failed re-embed never
            # leaves an old-model vector looking current.
            session.execute(
                delete(EmbeddingRecord).where(
                    EmbeddingRecord.entry_id.in_([entry.id for entry in batch])
                )
            )
            session.commit()
            if store_batch is not None:
                store_batch(session, batch)  # one batched encode; a miss is skipped
            else:
                for entry in batch:
                    embeddings.store_for_entry(session, entry)  # False = skip, keep going
            job.done += len(batch)
        log_action(
            session,
            "reindexed",
            "embeddings",
            detail=f"{job.done} entries -> {embeddings.backend_id()}",
        )
        session.commit()
        job.status = "success"
        run.result = f"{job.done} notes indexed"
        taskhistory.record(
            "reindex",
            "Re-indexing your notes",
            "completed",
            f"{job.done} notes re-embedded with {embeddings.backend_id()}",
            duration_ms=(time.monotonic() - started) * 1000,
        )
    except Exception as exc:  # a failed job must report, never crash the app
        # The job row and the task history carry `str(exc)`, one line; the
        # traceback is what says where a re-index died, and it went nowhere.
        logging.getLogger("tessellate.search").warning("re-index failed", exc_info=True)
        job.status = "error"
        job.error = str(exc)
        #: A sentence on the last-run line, not the exception: its text can carry
        #: a path or a library's wording (ledger 1547). The log has the traceback.
        run.fail("The re-index stopped before it finished. The log has the reason.")
        # The ending that mattered most and was hardest to see: a re-index that
        # dies halfway used to leave exactly the same empty screen as one that
        # finished, with the reason only in the log console.
        taskhistory.record(
            "reindex",
            "Re-indexing your notes",
            "failed",
            str(exc),
            duration_ms=(time.monotonic() - started) * 1000,
        )
    finally:
        session.close()


def start_pull(client: OllamaClient, name: str) -> bool:
    """Download a model via Ollama in a background thread. Returns False
    if that model is already downloading."""
    with _lock:
        existing = _pull_jobs.get(name)
        if existing is not None and existing.status == "running":
            return False
        job = Job(kind="pull", name=name)
        _pull_jobs[name] = job
    #: On the pool's `download` lane, not a thread of its own (Brief 9).
    #: Durable when the client is the app's own: a launch after a quit
    #: mid-download pulls again, and Ollama keeps the layers it has, so the
    #: second pull carries on rather than starting over.
    from tessellate.core import jobs

    if _is_app_client(client):
        queued = jobs.enqueue("pull", pull_model, name, name=name, dedupe_key=("pull", name))
    else:
        queued = jobs.enqueue("pull", _run_pull, client, name, job, name=name)
    if not queued:
        with _lock:
            job.status = "error"
            job.error = "The app is shutting down."
        return False
    return True


def _is_app_client(client: object) -> bool:
    try:
        return client is APP_GETTERS["ollama"]()
    except Exception:  # noqa: BLE001  # no app state: a script or a test
        return False


def pull_model(name: str) -> None:
    """The durable pull (Brief 9, `jobstore.HANDLERS["pull"]`): the app's
    own model client, looked up when it runs."""
    with _lock:
        job = _pull_jobs.get(name)
        if job is None or job.status != "running":
            job = _pull_jobs[name] = Job(kind="pull", name=name)
    _run_pull(APP_GETTERS["ollama"](), name, job)


def _run_pull(client: OllamaClient, name: str, job: Job) -> None:
    started = time.monotonic()
    try:
        # Ollama streams progress lines with completed/total bytes (§6.5).
        for update in client.pull(name):
            if job.cancel_requested:  # user quit it from the tasks manager
                job.status = "cancelled"
                taskhistory.record(
                    "pull",
                    f"Downloading {name}",
                    "cancelled",
                    name=name,
                    duration_ms=(time.monotonic() - started) * 1000,
                )
                return
            if update.get("error"):
                raise OllamaError(update["error"])
            if update.get("total"):
                job.total = int(update["total"])
                job.done = int(update.get("completed", job.done))
        job.status = "success"
        taskhistory.record(
            "pull",
            f"Downloaded {name}",
            "completed",
            name=name,
            duration_ms=(time.monotonic() - started) * 1000,
        )
    except OllamaError as exc:
        # Surface the failure so the UI can offer a retry, never leave
        # a half-download looking installed (§6.5).
        job.status = "error"
        job.error = str(exc)
        taskhistory.record(
            "pull",
            f"Downloading {name}",
            "failed",
            str(exc),
            name=name,
            duration_ms=(time.monotonic() - started) * 1000,
        )


#: Names that are not a general chat model: reading text, pictures only,
#: embeddings. Matched as words in the model's name.
_NOT_CHAT = ("ocr", "embed", "vl", "vision", "llava", "moondream", "minicpm-v", "rerank")
#: The largest a model may be (on disk) to be chosen without asking.
_CHOOSE_MAX_BYTES = 10 * 1024**3


def choose_installed_chat_model(installed: list[dict]) -> str | None:
    """The chat model to use when the stored one is not installed (the owner,
    2026-10-07: "the app should detect and smart choose the available models
    if the user has one or more on first launch"): the largest general chat
    model up to 10 GB on disk, else None."""
    def is_chat(name: str) -> bool:
        words = set(re.split(r"[^a-z0-9.]+", name.lower()))
        return not any(word in words or name.lower().startswith(word) for word in _NOT_CHAT)

    fits = [m for m in installed if m.get("name") and is_chat(m["name"]) and int(m.get("size") or 0) <= _CHOOSE_MAX_BYTES]
    if not fits:
        return None
    return max(fits, key=lambda m: int(m.get("size") or 0))["name"]


def is_installed_name(name: str, installed: list[dict]) -> bool:
    """Whether `name` is among the installed models, `llama3.2` matching an
    installed `llama3.2:latest` as Ollama itself resolves it."""
    if not name:
        return False
    names = {str(m.get("name") or "") for m in installed}
    return name in names or f"{name}:latest" in names


def choose_chat_model_if_missing(config: ConfigManager, installed: list[dict]) -> str | None:
    """The stored chat model is not installed (a fresh install's default
    `llama3.2`): store the best one that is, and return its name. None when
    the stored one is installed, or nothing installed fits. The one rule
    behind the launch step and the filing warm-up (101c), so neither loads a
    name the person never chose."""
    current = config.get_preference("chat_model", "llama3.2")
    if is_installed_name(current, installed):
        return None
    chosen = choose_installed_chat_model(installed)
    if chosen:
        config.set_preference("chat_model", chosen)
        #: Said once in the app, with Change (the owner, 2026-10-07: "Say once
        #: what was chosen and why"): `/models/status` carries it until a
        #: model is picked by hand.
        config.set_preference(
            "chat_model_chosen_why", f"{current} is not installed, and it is the largest chat model you have"
        )
        logging.getLogger("tessellate.startup").info("chat model %s is not installed; using %s", current, chosen)
    return chosen


def served_name(configured: str, listed: list[dict]) -> str:
    """The model a turn is answered with (bug sweep 2026-10-12): the
    configured one when the server has it, else the server's only model,
    since a server serving one model (llama.cpp) answers with it whatever
    name is sent. A GGUF path is named by its file."""
    names = [str(e.get("name") or e.get("id") or e.get("model") or "") for e in listed if isinstance(e, dict)]
    names = [n for n in names if n]
    if any(n == configured or n.removesuffix(":latest") == configured.removesuffix(":latest") for n in names):
        return configured
    if len(names) != 1:
        return configured
    only = names[0]
    if only.lower().endswith(".gguf"):
        only = only.replace("\\", "/").rsplit("/", 1)[-1][: -len(".gguf")]
    return only
