"""Preferences, audit-log viewer, data export, and recycle-bin
maintenance.
"""

from __future__ import annotations

import asyncio
import csv
import io
import hashlib
import json
import logging
import importlib
import os
import platform
import re
import sys
import tempfile
import zipfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse, FileResponse

from tessellate.api import paging
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tessellate import __version__
from tessellate.ai import budget as run_budget
from tessellate.ai import librarian, presets, skill_composer, skills
from tessellate.api.routes_categories import CATEGORY_PALETTE_KEYS
from tessellate.core import backup, backup_bundle, deps, embedmodels, events, extras, jobruns, jobs, logbuffer, security
from tessellate.core.config import default_preferences
from tessellate.core.database import AuditLog, Category, Entry, EntryLink, utcnow
from tessellate.core.deps import get_session
from tessellate.entry import importer, manager
from tessellate.search import searxng_manager, websearch
from tessellate.api.this_computer import REFUSAL, is_another_device, this_computer_only

router = APIRouter(tags=["settings"])

#: Routes in this module that must work **before** the notebook is unlocked.
#: Included in `app.py` without the `locked` dependency, deliberately and
#: only for the client-error sink below, see its docstring.
open_router = APIRouter(tags=["settings"])

# Preferences the user may change from the UI, a deliberate allowlist
# so a stray request can't scribble on model settings (those have their
# own validated endpoints in routes_models).
class AvatarStyle(BaseModel):
    """How the person's own generated face is drawn, beyond their name.

    `variant` is which take on the name (0 is the name's own; each shuffle
    moves it on), and the rest override one part each: an empty string
    leaves the part to the name, "none" takes it away, and anything else is
    the part's own key in avatars.js. Short lower-case words only, so a value
    can never be more than a key the drawing code looks up.
    """

    variant: int = Field(default=0, ge=0, le=9999)
    mood: str = Field(default="", max_length=20, pattern=r"^[a-z]*$")
    hair: str = Field(default="", max_length=20, pattern=r"^[a-z]*$")
    outfit: str = Field(default="", max_length=20, pattern=r"^[a-z]*$")
    hat: str = Field(default="", max_length=20, pattern=r"^[a-z]*$")
    eyewear: str = Field(default="", max_length=20, pattern=r"^[a-z]*$")
    hand: str = Field(default="", max_length=20, pattern=r"^[a-z]*$")
    # The skin tone and the hair colour, by name ("fair", "chestnut").
    skin: str = Field(default="", max_length=20, pattern=r"^[a-z]*$")
    hairtone: str = Field(default="", max_length=20, pattern=r"^[a-z]*$")
    # "feminine" or "masculine" chooses the look your face is drawn with;
    # empty leaves it to the name and to Appearance, Face looks.
    look: str = Field(default="", max_length=20, pattern=r"^[a-z]*$")

    @field_validator("hand", "mood", "hair", "outfit", "hat", "eyewear", "skin", "hairtone", "look")
    @classmethod
    def _not_retired(cls, value: str, info) -> str:
        """A part taken out of the drawing is left to the name, not kept."""
        return "" if value in RETIRED_AVATAR_PARTS.get(info.field_name, ()) else value


#: **Parts taken out of the drawing** (INBOX 426 w, 90.png). A style saved
#: before a part was removed keeps naming it: the rude gesture came out of
#: the held things (INBOX 426 j) and a saved `hand: "middlefinger"` left
#: Your look's Holding select empty, a value none of its options has. The
#: frontend owns the lists of parts (avatars.js); the server knows only
#: what has been retired, and drops it both ways: on save (the validator
#: above) and on read (`_clean_avatar_style`), for a style saved before.
RETIRED_AVATAR_PARTS: dict[str, frozenset[str]] = {"hand": frozenset({"middlefinger"})}


def _clean_avatar_style(raw: object) -> dict:
    """A saved style as it may be drawn now: only the parts, each a valid
    word and not retired. A key that is no part, or a value that fails the
    part's own rule, is dropped, not the whole style."""
    if not isinstance(raw, dict):
        return {}
    clean: dict = {}
    for name in AvatarStyle.model_fields:
        if name not in raw:
            continue
        try:
            value = getattr(AvatarStyle(**{name: raw[name]}), name)
        except ValueError:
            continue
        if value == "" and raw[name] != "":
            continue
        clean[name] = value
    return clean


class TemplateItem(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    content: str = Field(max_length=2000)
    # Optional one-liner shown in the Settings list and as the entry-template
    # option's tooltip: same shape as SkillItem.description below.
    description: str = Field(default="", max_length=200)


# The names BUILTIN_TEMPLATES in app.js ships (tests/test_notes_extras_api.py
# pins the two sets to each other). The templates themselves (their markdown
# bodies) only ever lived in the frontend; Wave B never gave the server a
# reason to know their content. A `custom_templates` item carrying one of
# these names is that built-in's *edit* (INBOX 409, "templates cant be
# edited"): the persona shape, where an override lives under the shipped
# name in the same list as the person's own and removing it is the reset.
# `_validated_templates` used to refuse these names outright, which is what
# made the built-ins uneditable; now the only collision it refuses is two
# items with one name.
BUILTIN_TEMPLATE_NAMES = {"Journal", "Recipe", "Contact", "Meeting"}


#: The em dash, kept as a lookup rather than written literally so this file
#: (and `tests/test_no_em_dashes.py`, which reads every file under `src/`)
#: passes its own rule the same way `tests/test_no_em_dashes.py` reads its
#: own copy of the character.
_EM_DASH = chr(0x2014)


class PersonaItem(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    prompt: str = Field(min_length=1, max_length=2000)
    #: The words that rotate beside the thinking dots while this persona is
    #: answering (the owner: rotating "thinking words" like Claude Code's,
    #: "customisable per persona"). Empty (the default for every persona that
    #: has never set one) means "use the app's default list, or the built-in
    #: persona's own list"; frontend/js/sheets-selects.js resolves which. Stored
    #: here rather than in localStorage for the same reason the writing
    #: dictionary is: a list built by hand should survive a cleared browser
    #: and travel with the daily backup.
    thinking_words: list[str] = Field(default_factory=list)

    @field_validator("thinking_words")
    @classmethod
    def _bounded_thinking_words(cls, words: list[str]) -> list[str]:
        cleaned = [w.strip() for w in words if w.strip()]
        if not cleaned:
            return []  # "use the default list", not "a list of nothing"
        if not (8 <= len(cleaned) <= 40):
            raise ValueError(
                f"thinking words: 8 to 40 items, got {len(cleaned)} (or leave it empty "
                "to use the default list)"
            )
        for word in cleaned:
            if len(word) > 40:
                raise ValueError(f'thinking word "{word}" is longer than 40 characters')
            if "!" in word:
                raise ValueError(f'thinking word "{word}" must not use an exclamation mark')
            if _EM_DASH in word:
                raise ValueError(f'thinking word "{word}" must not use an em dash')
            #: A loose sentence-case check: reject a word typed in
            #: ALL CAPS (the app's own copy rule, CLAUDE.md section 2 item
            #: 6), which is the one case this can tell apart from a
            #: deliberate acronym or a proper noun without a dictionary.
            if word.isupper():
                raise ValueError(f'thinking word "{word}" reads as shouting, not sentence case')
        return cleaned


class SuggestThinkingWordsBody(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    prompt: str = Field(min_length=1, max_length=2000)


@router.post("/personas/suggest-thinking-words")
def suggest_persona_thinking_words(body: SuggestThinkingWordsBody) -> dict:
    """"Suggest with AI" in the persona editor: about sixteen thinking
    words in this persona's own voice, from its prompt, the same
    utility-model-completion shape `POST /suggest-tags` uses. Takes the name
    and prompt directly (not a saved persona) so this works for one not
    saved yet, same reasoning `POST /suggest-tags` gives for taking a
    draft's text rather than a saved `Entry`.
    """
    try:
        words = librarian.suggest_thinking_words(
            body.name, body.prompt, deps.get_model_manager(), deps.get_ollama()
        )
    except Exception:
        logging.getLogger("tessellate.personas").warning(
            "thinking-word suggestions failed", exc_info=True
        )
        words = []
    return {"thinking_words": words}


class DraftTemplateBody(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    description: str = Field(default="", max_length=200)
    current: str = Field(default="", max_length=2000)


@router.post("/templates/draft")
def draft_template(body: DraftTemplateBody) -> dict:
    """"Draft with Atlas" in Settings, Templates: a body from the name and
    the one line, or another take on the one in the box. A model that is
    down answers with an empty body and a reason, never an error page."""
    try:
        text = librarian.draft_template(
            body.name, body.description, body.current, deps.get_model_manager(), deps.get_ollama()
        )
    except Exception as exc:  # noqa: BLE001 - said in the panel, logged here
        logging.getLogger("tessellate.templates").warning("template draft failed", exc_info=True)
        return {"content": "", "reason": librarian.model_error_message(deps.get_model_manager().utility_model(), exc)}
    return {"content": text, "reason": "" if text else "The model wrote nothing. Try again."}


class CustomThemeItem(BaseModel):
    """One saved look: the appearance settings the browser would have applied.

    `values` is deliberately a free-form string map rather than a model with a
    field per setting. The appearance controls live entirely in the frontend
    and are the only thing that knows what a key means, pinning the list here
    would mean a saved theme could not carry a setting added later without a
    matching server change, for a value the server never reads.

    It is *bounded* rather than trusted: a cap on how many keys, and on how
    long each is, so a stored theme cannot become an arbitrary blob in the
    preferences file.
    """

    name: str = Field(min_length=1, max_length=30)
    values: dict[str, str] = Field(default_factory=dict)
    preset: str = Field(default="", max_length=40)

    @field_validator("values")
    @classmethod
    def _bounded(cls, values: dict) -> dict:
        if len(values) > 40:
            raise ValueError("a theme carries at most 40 settings")
        for key, value in values.items():
            if len(str(key)) > 40 or len(str(value)) > 200:
                raise ValueError("theme settings must be short strings")
        return values


class SkillInput(BaseModel):
    """One value a skill asks for before it runs (§21)."""

    name: str = Field(min_length=1, max_length=24)
    label: str = Field(default="", max_length=60)
    required: bool = True
    default: str = Field(default="", max_length=skills.MAX_INPUT_VALUE)


class SkillItem(BaseModel):
    """A named, repeatable job over the notebook (§21).

    `prompt` alone is the whole of a pre-rebuild skill, and still valid, the
    steps, tools and inputs are what make it a job rather than a saved
    sentence. The real rules live in `ai/skills.normalise`, which the route
    applies as well, so the tool path and the settings path can't drift.
    """

    name: str = Field(min_length=1, max_length=skills.MAX_NAME)
    prompt: str = Field(min_length=1, max_length=skills.MAX_PROMPT)
    description: str = Field(default="", max_length=skills.MAX_DESCRIPTION)
    # When this skill applies. What makes it findable by the model rather than
    # only by the person who remembered writing it (§33).
    when_to_use: str = Field(default="", max_length=skills.MAX_WHEN)
    steps: list[str] = Field(default_factory=list, max_length=skills.MAX_STEPS)
    tools: list[str] = Field(default_factory=list, max_length=skills.MAX_TOOLS)
    inputs: list[SkillInput] = Field(default_factory=list, max_length=skills.MAX_INPUTS)
    #: **The postcondition** (CHAT_PLAN decision 10b). Measured 2026-09-20,
    #: while building the editor's own control for it: a skill saved through
    #: Settings arrived here with its block and left without one, because a
    #: field this model does not declare is dropped before `normalise` ever
    #: sees it. So "the editor round-trips it" was true of the stored shape
    #: and not of the wire. Left as a loose dict on purpose: the rules are
    #: `skills.verify_spec`'s, which is the one place that knows the
    #: predicates and answers in a sentence the person can act on, and a
    #: second model here would be a second set of rules to drift from it.
    verify: dict | None = None
    # Pre-rebuild flag the UI still reads; derived on save from steps/tools.
    useTools: bool = False  # noqa: N815  # the stored key, kept for old skills


class PreferencesBody(BaseModel):
    #: Settings to put back to "never set" (their default), which a value cannot
    #: say: Settings, Recent changes uses it to undo a first change (INBOX 898).
    unset: list[Annotated[str, Field(min_length=1, max_length=80)]] | None = Field(default=None, max_length=64)
    recycle_bin_days: int | None = Field(default=None, ge=1, le=365)
    # 0 means "keep everything", which is the default, see
    # `autonomous.purge_old_conversations` for why this is opt-in rather than
    # on with a sensible number. `ge=0`, not `ge=1`, so switching it back off
    # is expressible.
    conversation_retention_days: int | None = Field(default=None, ge=0, le=3650)
    # Empty string resets to the default (data_dir/exports). Validated in
    # update_preferences (_validated_export_dir): must be an absolute,
    # existing, writable directory, checked at save time rather than at
    # export time when a bad path means a lost file.
    export_save_dir: str | None = Field(default=None, max_length=500)
    backup_copy_dir: str | None = Field(default=None, max_length=500)
    search_min_similarity: float | None = Field(default=None, ge=0, le=1)
    search_relative_z_margin: float | None = Field(default=None, ge=0, le=3)
    communication_style: Literal["friendly", "concise", "detailed"] | None = None
    #: The register the composer writes its connecting words in when no model
    #: answers (`ai/composer_tables.py`): plain and friendly, or formal.
    composer_voice: Literal["natural", "professional", "playful", "plain"] | None = None
    #: The first day of the week for the Statistics page: the person's pick,
    #: or "auto" to follow the locale the browser reports (`week_start_locale`,
    #: a Python weekday, 0 Monday to 6 Sunday).
    week_start: Literal["auto", "monday", "saturday", "sunday"] | None = None
    week_start_locale: int | None = Field(default=None, ge=0, le=6)
    #: Which half of the year "summer" and "last winter" mean: the person's
    #: pick, or "auto" to follow the locale the browser reports (`season_locale`).
    season_hemisphere: Literal["auto", "north", "south"] | None = None
    season_locale: str | None = Field(default=None, max_length=35)
    #: Minutes of no use after which the search-by-meaning model is dropped from
    #: memory (decision 62; it loads again on the next search or save). 0 keeps it.
    embedder_idle_unload_minutes: int | None = Field(default=None, ge=0, le=1440)

    #: What Atlas volunteers past the answer (CHAT_PLAN decision 73).
    insight_level: Literal["off", "one", "all"] | None = None
    #: **The writing checker's own two settings.** Both belong on the server
    #: rather than in `localStorage`, and the reason is the same for each: a
    #: dictionary you have to rebuild when you clear your browser data is a
    #: dictionary nobody adds to, and a spelling variant that differs between
    #: the desktop shell and a browser tab is a checker that contradicts
    #: itself. Asked for directly: *"adding to dictionary (a way to manage that
    #: dictionary), auto correct spelling (us, uk spelling etc)"*.
    #:
    #: Bounded, because this is a list a client writes to freely: 2,000 words
    #: is far more than anyone adds by hand and small enough that the whole
    #: list can be sent to the editor on load, which is what lets the check run
    #: on every keystroke without a request.
    writing_dictionary: list[str] | None = Field(default=None, max_length=2000)
    #: `off` means "do not have an opinion about which side of the Atlantic
    #: this document is on", the honest default for a notebook that does not
    #: know who is writing in it.
    spelling_variant: Literal["off", "uk", "us", "au", "ca", "in"] | None = None
    #: The grammar checker (Harper, run in the browser; INBOX 401). On by
    #: default: it costs nothing until a prose document or note box is open,
    #: and nothing on the main thread even then.
    grammar_check: bool | None = None
    #: Curly quotes and a dash from two hyphens as you type in a prose
    #: document (the autofill ask, 2026-09-24). Off by default: software that
    #: changes what was typed without being asked is the thing people turn off
    #: first, so this one asks.
    smart_punctuation: bool | None = None
    #: Documents offer to turn a named note or document into a link (VC5), and
    #: the names the writer put away with "Never offer a link to this name".
    #: The list is bounded because a client writes to it freely.
    link_offers: bool | None = None
    check_link_text: bool | None = None
    link_offer_ignored: list[Annotated[str, Field(max_length=200)]] | None = Field(default=None, max_length=500)
    #: Autocorrect in the note boxes, the chat and Ask composers and the
    #: titles (Brief 94, autocorrect.js). On by default, unlike the line above:
    #: it changes only strings that are not words, says so, and puts each back
    #: with one key.
    autocorrect: bool | None = None
    # Display name for the dashboard greeting (empty string clears it).
    display_name: str | None = Field(default=None, max_length=60)
    # Optional context about the user for the librarian.
    # profile_enabled is the opt-out switch; the delete button in the UI
    # simply saves an empty string.
    user_profile: str | None = Field(default=None, max_length=2000)
    profile_enabled: bool | None = None
    # Capture templates: user-defined prefills for the note box.
    custom_templates: list[TemplateItem] | None = Field(default=None, max_length=20)
    # Personas: custom system prompts + which one is active.
    personas: list[PersonaItem] | None = Field(default=None, max_length=20)
    active_persona: str | None = Field(default=None, max_length=40)
    # Independent override for just the dashboard greeting, empty clears it
    # back to "same as active_persona", the same clear-with-empty-string
    # convention display_name above already uses.
    dashboard_persona: str | None = Field(default=None, max_length=40)
    # Saved appearance looks. Server-side rather than in the browser because a
    # theme someone built by hand is a thing they would be upset to lose to a
    # cleared cache: and here it rides along in the daily backup too.
    custom_themes: list[CustomThemeItem] | None = Field(default=None, max_length=20)
    # Dashboard layout: widget order + hidden widgets.
    dashboard_layout: "DashboardLayout | None" = None
    #: The dashboard's Quick access tiles, in order: stable ids (the five
    #: defaults' names, or `tab:x` / `reveal:x` for a command from the
    #: catalogue), at most `QUICK_ACCESS_MAX`. `[]` is "never arranged", the
    #: same convention `dashboard_layout` uses, so Reset writes `[]` and the
    #: frontend falls back to its default five. Declared here because a field
    #: Pydantic does not know about is silently dropped.
    dashboard_quick_access: list[str] | None = Field(default=None, max_length=32)
    #: A highlight per Quick access tile, tile id to a key (INBOX 589): one of
    #: the category palette's twelve, "accent", or "none". A tile with no entry
    #: takes its position's default (the first is the accent, the rest plain),
    #: so `{}` is "never chosen". Cleaned by `_validated_quick_tints`.
    dashboard_quick_tints: dict[str, object] | None = None
    # User-defined skills, and whether the chat AI may use tools.
    skills: list[SkillItem] | None = Field(default=None, max_length=30)
    tools_enabled: bool | None = None
    # The local-AI lock (§33). On by default; see core.config.
    local_only_ai: bool | None = None
    # Which tools each turn is offered: "auto" reads the question and sends
    # what it plausibly needs (§11a: the schemas are most of the per-round
    # cost); "all" sends the whole registry, as it always did.
    tool_focus: Literal["auto", "all"] | None = None
    #: Small-model mode for skill runs: each step is offered only the tools its
    #: own contract names, plus a worked example of the call. "auto" decides
    #: from the chat model's name (see `model_manager.parameter_count`, which
    #: answers "no idea" for a name with no size in it, and no idea means
    #: off). Declared here for the reason the comments above give: a field
    #: Pydantic does not know about is silently dropped, so a setting that is
    #: never declared is a switch that never saves.
    small_model_mode: Literal["auto", "on", "off"] | None = None
    #: **What one skill run may spend** (Brief 13). A run is many turns and
    #: every one of them starts its own fresh round allowance, so the only
    #: bound on a run that goes wrong used to be how long the person was
    #: willing to watch it. Zero in either field means "no limit on this one",
    #: which is a real answer for a ten-step audit over four thousand notes on
    #: hardware somebody is happy to give an hour to.
    run_budget_tokens: int | None = Field(default=None, ge=0)
    run_budget_seconds: int | None = Field(default=None, ge=0)
    # One of the two features that can go online, off unless the user opts in.
    # The other is `update_check_enabled` below. Counted, not assumed: see
    # `tests/test_offline_promise.py`, which fails if a third appears and the
    # copy still says two.
    web_search_enabled: bool | None = None
    # The other opt-in network call (Settings -> About): see core.config.
    update_check_enabled: bool | None = None
    # Separate switch: "notify me" vs. "download and run the installer
    # without asking each time", see core.config's own comment.
    auto_update_enabled: bool | None = None
    update_channel: Literal["stable", "main"] | None = None
    update_beta: bool | None = None
    searxng_autostart: bool | None = None
    # Whether the app may install search by meaning itself: see core.config.
    semantic_auto_install: bool | None = None
    session_idle_ttl_minutes: int | None = Field(default=None, ge=1)
    # The desktop launcher's console window: see core.config's own comment.
    show_console_on_startup: bool | None = None
    # Whether the first-run Dev-view/User-view prompt has already been
    # shown. Missing from this model entirely was its own bug: a PUT for a
    # field Pydantic doesn't know about is silently dropped rather than
    # rejected, so the prompt would have recorded nothing and reappeared on
    # every single launch: caught live, before this ever shipped, by the
    # same round of testing that found show_console_on_startup missing from
    # GET /preferences.
    console_view_intro_seen: bool | None = None
    #: Whether the desktop window's X button hides to the tray (default) or
    #: quits. Declared here for the reason the comment above gives: a field
    #: Pydantic does not know about is silently dropped, so a setting that is
    #: never declared is a switch that never saves.
    close_to_tray: bool | None = None
    #: Whether a second desktop launch opens another window onto the running
    #: server rather than bringing the running window forward. Read by
    #: __main__.py before any window opens (core/instance_lock.py).
    new_window_on_launch: bool | None = None
    #: The person's own face: a shuffle and per-part overrides (AvatarStyle).
    avatar_style: AvatarStyle | None = None
    #: Which status-bar slots the user has switched off. **The list of what is
    #: hidden, not what is shown**, see `STATUS_SLOTS` in spaces-find.js: a slot added
    #: in a later version then appears by default for everyone, instead of
    #: being invisible to every user who ever opened that settings screen.
    status_bar_hidden: list[str] | None = None
    #: Opt-in, unlike status_bar_hidden above: a clock is not one of the
    #: permanent landmarks STATUS_SLOTS lists, so it defaults to off rather
    #: than appearing for everyone the moment this shipped. Asked for
    #: directly ("show the current time in the status bar").
    status_bar_clock: bool | None = None
    #: One-shot: the tray balloon explaining where the window went has been
    #: shown. Written by the launcher, not the browser, but declared so the
    #: value round-trips rather than being dropped by a later PUT.
    tray_hide_explained: bool | None = None

    #: The context window the user set by hand, per model, keyed by the model
    #: name exactly as the picker shows it. Asked for directly (INBOX 77): "the
    #: window itself should be manageable by the user and auto when set". A
    #: model with no entry, or an entry of null, is on auto: the app reads the
    #: window from the model file or the server's own catalog, which is what it
    #: has always done.
    #:
    #: Declared here for the reason half the comments in this class give: a
    #: field Pydantic does not know about is dropped without complaint, so an
    #: undeclared setting is a control that looks saved and is not.
    model_context_windows: dict[str, int | None] | None = None

    # Optional self-hosted SearXNG instance; empty string = use DuckDuckGo.
    searxng_url: str | None = Field(default=None, max_length=200)
    # Which engine answers: "auto" | "searxng" | "duckduckgo". Validated
    # rather than free text, so a bad value is rejected at the door instead of
    # sitting in preferences quietly meaning "auto" forever.
    search_provider: str | None = None
    # "Remember what I chose" for the Quick/Normal/Detailed response-mode
    # picker (setResponseMode in app.js): was never declared here at all,
    # so the PUT it fires on every change returned 200 while silently
    # dropping the value; the dropdown looked like it saved (it updates its
    # own <select> client-side regardless) but reverted to presets.DEFAULT_MODE
    # on the very next reload.
    response_mode: str | None = None
    # Autonomous Tasks settings. These were declared twice, once here with
    # bare types and once above with the validated ones, and Pydantic silently
    # keeps the last definition, so the bounds below were the only ones that
    # ever applied. One copy, the validated one.
    autonomous_tasks_enabled: bool | None = None
    auto_tag_enabled: bool | None = None
    auto_link_enabled: bool | None = None
    auto_dedupe_enabled: bool | None = None
    # ROADMAP.md item 31's stale/orphaned-note review. Missing from here was
    # the same shape of bug Tier 1 item 4a already found and fixed for eight
    # other preferences: the Settings checkbox (#pref-auto-stale-review)
    # calls setPreference exactly like its tag/link/dedupe siblings, but
    # Pydantic silently drops any key this model doesn't declare: so every
    # PUT that turned the toggle on was a no-op the whole time, and the
    # autonomous pass could never actually pick up any candidates no matter
    # what the checkbox showed.
    auto_stale_review_enabled: bool | None = None
    #: ANALYSIS.md §60 item 2. Declared here as well as in the response and
    #: `_AUTONOMOUS_PREFS` below: the comment above this block records what
    #: happens when it is not: Pydantic drops the key, every PUT that turns it
    #: on is a silent no-op, and the checkbox shows a state the backend never
    #: had.
    auto_capture_enabled: bool | None = None
    autonomous_tasks_interval_hours: int | None = Field(default=None, ge=1, le=168)
    autonomous_tasks_model: str | None = Field(default=None, max_length=100)
    filing_wait_seconds: int | None = Field(default=None, ge=5, le=60)
    #: **Four filing and image switches Settings has always shown and never
    #: saved** (found 2026-10-04 with INBOX 509): they were missing here, so
    #: pydantic dropped them on the way in and the checkbox snapped back on
    #: the next load. `tests/test_preferences_roundtrip.py` now compares
    #: every key the frontend sends with this body.
    ai_first_filing: bool | None = None
    #: WORLD_CLASS 23, decision 6: health, money, relationships, the law and
    #: identity are suggested, not filed, unless this is on.
    auto_file_sensitive: bool | None = None
    #: WORLD_CLASS_PLAN section 17 row 3 (`librarian.FILING_STYLES`).
    filing_style: Literal["topic", "project", "time"] | None = None
    background_filing: bool | None = None
    auto_caption_images: bool | None = None
    auto_read_image_text: bool | None = None
    #: INBOX 509: the search model loads at launch (the first note files at
    #: once) or on first use (a lighter start; the first note waits for it).
    warm_search_model_at_launch: bool | None = None
    #: Decision 62: the search model goes after an idle hour (default on).
    battery_efficient_mode: bool | None = None
    smart_model_routing_enabled: bool | None = None
    # Asked directly: a way to quiet toasts and the notifications panel for
    # background jobs, agent runs and general activity while a due reminder
    # still gets through either way.
    notifications_muted_except_reminders: bool | None = None
    #: Where the AI's own activity is announced: "toasts" (a passing notice
    #: *and* a row in the notifications centre, the behaviour this app has
    #: always had) or "centre" (the row only).
    #:
    #: Asked for directly: *"make an option for agent activity notifications to
    #: be hidden and not show up as toast notifications but somewhere else."*
    #: Distinct from `notifications_muted_except_reminders`, which is a
    #: blanket mute that also stops the row being recorded, this is about
    #: *where* an activity notice lands, not whether it happens.
    agent_activity_notices: str | None = Field(default=None, pattern="^(toasts|centre)$")
    # Agent tools the user has switched off (by tool name).
    #: Room for every tool and the ones still to come: the cap was 50 while the
    #: catalogue was already 58, so the 51st switch in Settings was refused.
    disabled_tools: list[str] | None = Field(default=None, max_length=300)
    # Which faster-whisper model size the dictation buttons load. Read by
    # `routes_voice.py` since the feature shipped; nothing ever let a user set
    # it, so every install has silently run "base" regardless of the box's
    # speed or the length of what's being dictated.
    voice_model: Literal["tiny", "base", "small", "medium"] | None = None
    #: Brief 87 step 2: Whisper's options (ai/voice.py `options_from`).
    voice_skip_silence: bool | None = None
    #: "" detects the language; the codes are `voice.LANGUAGES`.
    voice_language: Literal[
        "", "en", "es", "fr", "de", "it", "pt", "nl", "pl", "sv", "da", "no", "fi",
        "ru", "uk", "tr", "ar", "hi", "ja", "zh", "ko",
    ] | None = None
    voice_vocabulary: str | None = Field(default=None, max_length=200)
    # The user's IANA timezone, reported by the browser at startup. Anything
    # the AI reasons about in time ("in 10 minutes", "tomorrow at 9") is
    # resolved against this, because the server may be running in UTC while
    # the person is not. Validated on the way in, an unknown zone name would
    # otherwise sit in preferences and silently fall back forever.
    timezone: str | None = Field(default=None, max_length=64)
    # The interface's own local state, theme, palette, corner rounding,
    # whether onboarding has been seen (§35E). A flat map of short strings,
    # deliberately: this is the browser's `localStorage` mirrored so that a
    # shell which does not persist it still remembers. Validated for *shape*
    # rather than for meaning, the keys are the frontend's business and it
    # would be worse to have the server reject a setting the UI has just added
    # than to store a key nobody reads.
    ui_state: dict[str, str] | None = None

    @field_validator("ui_state")
    @classmethod
    def _small_ui_state(cls, value: dict | None) -> dict | None:
        """A bounded map. Nothing here should ever be large, and a preference
        file that can be grown without limit from the browser is a way to fill
        a disk."""
        if value is None:
            return value
        if len(value) > 80:
            raise ValueError("Too many interface settings")
        for key, item in value.items():
            if len(str(key)) > 40 or len(str(item)) > 400:
                raise ValueError(f"Interface setting {key!r} is too long")
        return value

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str | None) -> str | None:
        if not value:
            return value
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown timezone {value!r}") from exc
        return value

    @field_validator("search_provider")
    @classmethod
    def _known_provider(cls, value: str | None) -> str | None:
        """Rejected at the door rather than normalised away, so a UI sending
        the wrong name finds out instead of silently getting "auto"."""
        if value is None:
            return value
        if value not in websearch.PROVIDERS:
            raise ValueError(
                f"Unknown search provider {value!r}: expected one of "
                + ", ".join(sorted(websearch.PROVIDERS))
            )
        return value

    @field_validator("response_mode")
    @classmethod
    def _known_response_mode(cls, value: str | None) -> str | None:
        """Same reasoning as `_known_provider` above: `_resolve_mode` would
        happily fall back to the default for a bad value at read time, which
        is right for a value already sitting in storage, but rejecting a
        bad one at the door means the picker finds out immediately rather
        than saving a typo that silently never takes effect."""
        if value is None:
            return value
        if value not in presets.MODES:
            raise ValueError(
                f"Unknown response mode {value!r}: expected one of "
                + ", ".join(sorted(presets.MODES))
            )
        return value

    # Named filters the user has saved from the Notes tab.
    saved_searches: list["SavedSearch"] | None = Field(default=None, max_length=30)
    # Named searches from the search box, its rows in the Notes sidebar
    # (search.js): the box searches every kind, a saved filter only notes.
    saved_finds: list["SavedSearch"] | None = Field(default=None, max_length=30)


class SavedSearch(BaseModel):
    """A named filter, e.g. {"name": "This week's work", "query": "tag:work"}."""

    name: str = Field(min_length=1, max_length=40)
    query: str = Field(min_length=1, max_length=200)


#: **The cap has to be bigger than the catalogue, and it was not.**
#:
#: Found by measuring, not by reading: reordering a widget on the dashboard
#: produced `PUT /preferences 422` and nothing moved. `order` carries *every*
#: widget, visible and hidden, and the dashboard has grown past twenty of
#: them, so every save of a full layout was rejected outright. Nothing in the
#: UI said so (`saveDashLayout` swallows the failure to keep a dead preference
#: from breaking the page), which is why "a better way to manage and rearrange
#: widgets" was reported as a design problem: rearranging did not persist at
#: all.
#:
#: 64 rather than "the current number of widgets": a bound exists here to stop
#: a malformed request storing an unbounded list, not to enforce the
#: catalogue's size: and a limit that has to be raised every time a widget is
#: added is a limit that will be forgotten again. `tests/test_dashboard_layout_cap.py`
#: fails the build if the catalogue ever approaches it.
DASHBOARD_LAYOUT_MAX = 64


class DashboardLayout(BaseModel):
    order: list[str] = Field(default_factory=list, max_length=DASHBOARD_LAYOUT_MAX)
    hidden: list[str] = Field(default_factory=list, max_length=DASHBOARD_LAYOUT_MAX)
    # Widgets the user has set to span two grid columns.
    wide: list[str] = Field(default_factory=list, max_length=DASHBOARD_LAYOUT_MAX)
    # Widgets the user has set back to one column. Separate from `wide`
    # because an empty `wide` reads as "never chosen" and brings the default
    # wide widgets back: the heatmap's Narrow, the only default, undid itself.
    narrow: list[str] = Field(default_factory=list, max_length=DASHBOARD_LAYOUT_MAX)
    # Older layouts stored the same thing as {"stats": "wide"}. Kept so a
    # layout saved before the switch still loads; the frontend folds it into
    # `wide` and writes the list form back on the next save.
    sizes: dict[str, str] = Field(default_factory=dict)


#: Quick access holds eight tiles at most (the row is five across at the
#: desktop width; more would wrap). The request model's own cap is looser so a
#: stale client sending nine is cleaned here rather than failing the whole
#: save, which is the same reason `_validated_context_windows` cleans.
QUICK_ACCESS_MAX = 8


def _validated_quick_access(value: object) -> list[str]:
    """Strings only, trimmed, no repeats, short, and at most `QUICK_ACCESS_MAX`.

    Whether an id still names anything is the frontend's question (a command
    can be renamed away by a later version, and the tile then simply is not
    drawn); the server only keeps the stored list from becoming a blob.
    """
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    for item in value:
        key = item.strip() if isinstance(item, str) else ""
        if key and len(key) <= 80 and key not in cleaned:
            cleaned.append(key)
    return cleaned[:QUICK_ACCESS_MAX]


#: The keys a tile's highlight may be: the category swatches (one palette for
#: every colour a person picks), the theme's accent, and an explicit "none"
#: (which is how the first tile turns its default accent off).
QUICK_TINT_KEYS = frozenset(("accent", "none")) | frozenset(CATEGORY_PALETTE_KEYS)


def _validated_quick_tints(value: object) -> dict[str, str]:
    """Known keys only, short ids, and a bounded map.

    The value ends up in a CSS custom property (`--quick-tint`, through a
    lookup in the frontend), so nothing but a palette key is ever stored. The
    frontend prunes ids that left the row; the cap only keeps a stale map from
    growing without end.
    """
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, str] = {}
    for raw_id, tint in value.items():
        tile = raw_id.strip() if isinstance(raw_id, str) else ""
        if tile and len(tile) <= 80 and isinstance(tint, str) and tint in QUICK_TINT_KEYS:
            cleaned[tile] = tint
        if len(cleaned) >= 32:
            break
    return cleaned


@router.get("/preferences")
def get_preferences() -> dict:
    return _preferences_from(deps.get_config())


#: A config that never saved a preference: the install's defaults
#: (`config.default_preferences`) under the fallbacks `_preferences_from` reads
#: with, so Settings' reset (GET /preferences/defaults) can never disagree with
#: what a fresh notebook is given.
class _FreshConfig:
    def __init__(self) -> None:
        self._prefs = default_preferences()

    def get_preference(self, key: str, default: object = None) -> object:
        return self._prefs.get(key, default)


def _preferences_from(config) -> dict:
    return {
        "recycle_bin_days": config.get_preference("recycle_bin_days", 30),
        "ai_first_filing": config.get_preference("ai_first_filing", True),
        "auto_file_sensitive": config.get_preference("auto_file_sensitive", False),
        "filing_style": config.get_preference("filing_style", "topic"),
        "background_filing": config.get_preference("background_filing", True),
        "auto_caption_images": config.get_preference("auto_caption_images", True),
        "auto_read_image_text": config.get_preference("auto_read_image_text", True),
        "filing_wait_seconds": config.get_preference("filing_wait_seconds", None),
        "warm_search_model_at_launch": config.get_preference("warm_search_model_at_launch", True),
        "conversation_retention_days": config.get_preference("conversation_retention_days", 0),
        "export_save_dir": config.get_preference("export_save_dir", ""),
        "backup_copy_dir": config.get_preference("backup_copy_dir", ""),
        "search_min_similarity": config.get_preference("search_min_similarity", 0.25),
        "search_relative_z_margin": config.get_preference("search_relative_z_margin", 0.5),
        "communication_style": config.get_preference("communication_style", "friendly"),
        "composer_voice": config.get_preference("composer_voice", "natural"),
        "week_start": config.get_preference("week_start", "auto"),
        "week_start_locale": config.get_preference("week_start_locale", 0),
        "season_hemisphere": config.get_preference("season_hemisphere", "auto"),
        "season_locale": config.get_preference("season_locale", ""),
        "embedder_idle_unload_minutes": config.get_preference("embedder_idle_unload_minutes", 60),
        "insight_level": config.get_preference("insight_level", "one"),
        "writing_dictionary": config.get_preference("writing_dictionary", []),
        "spelling_variant": config.get_preference("spelling_variant", "off"),
        "grammar_check": config.get_preference("grammar_check", True),
        "smart_punctuation": config.get_preference("smart_punctuation", False),
        "link_offers": config.get_preference("link_offers", True),
        "check_link_text": config.get_preference("check_link_text", False),
        "link_offer_ignored": config.get_preference("link_offer_ignored", []),
        "autocorrect": config.get_preference("autocorrect", True),
        "display_name": config.get_preference("display_name", ""),
        #: Echoed so Settings can draw the boxes with what is in them rather
        #: than empty, which is the bug this file's other comments keep
        #: recording: a preference that saves and does not come back reads as
        #: one that did not save.
        "model_context_windows": config.get_preference("model_context_windows", {}),
        # Saved correctly and honoured correctly (routes_auth.py's three
        # idle-timeout checks all read it) but never once echoed back here, 
        # the same shape of bug Tier 1 item 4a already fixed for eight other
        # preferences. Settings → Account's timeout field showed its HTML
        # default on every reload no matter what had actually been saved and
        # was actually in effect, which reads as "my setting didn't save."
        "session_idle_ttl_minutes": config.get_preference("session_idle_ttl_minutes", 720),
        "user_profile": config.get_preference("user_profile", ""),
        "profile_enabled": config.get_preference("profile_enabled", False),
        "custom_templates": config.get_preference("custom_templates", []),
        "personas": config.get_preference("personas", []),
        "custom_themes": config.get_preference("custom_themes", []),
        "active_persona": config.get_preference("active_persona", "Atlas"),
        "dashboard_persona": config.get_preference("dashboard_persona", ""),
        "dashboard_layout": config.get_preference(
            "dashboard_layout", {"order": [], "hidden": []}
        ),
        "dashboard_quick_access": config.get_preference("dashboard_quick_access", []),
        "dashboard_quick_tints": config.get_preference("dashboard_quick_tints", {}),
        "skills": config.get_preference("skills", []),
        "tools_enabled": config.get_preference("tools_enabled", True),
        "local_only_ai": config.get_preference("local_only_ai", True),
        "tool_focus": config.get_preference("tool_focus", "auto"),
        "small_model_mode": config.get_preference("small_model_mode", "auto"),
        "run_budget_tokens": config.get_preference(
            "run_budget_tokens", run_budget.DEFAULT_TOKENS
        ),
        "run_budget_seconds": config.get_preference(
            "run_budget_seconds", run_budget.DEFAULT_SECONDS
        ),
        "web_search_enabled": config.get_preference("web_search_enabled", False),
        "update_check_enabled": config.get_preference("update_check_enabled", False),
        "auto_update_enabled": config.get_preference("auto_update_enabled", False),
        "update_choice_made": config.get_preference("update_choice_made", False) is True,
        "update_channel": config.get_preference("update_channel", "stable"),
        "update_beta": config.get_preference("update_beta", False) is True,
        "searxng_url": config.get_preference("searxng_url", ""),
        "searxng_autostart": config.get_preference("searxng_autostart", False),
        "semantic_auto_install": config.get_preference("semantic_auto_install", False),
        "semantic_choice_made": config.get_preference("semantic_choice_made", False) is True,
        "search_provider": websearch.normalise_provider(
            config.get_preference("search_provider", websearch.DEFAULT_PROVIDER)
        ),
        "response_mode": config.get_preference("response_mode", presets.DEFAULT_MODE),
        "disabled_tools": config.get_preference("disabled_tools", []),
        "voice_model": config.get_preference("voice_model", "base"),
        "voice_skip_silence": config.get_preference("voice_skip_silence", True),
        "voice_language": config.get_preference("voice_language", ""),
        "voice_vocabulary": config.get_preference("voice_vocabulary", ""),
        "saved_searches": config.get_preference("saved_searches", []),
        "saved_finds": config.get_preference("saved_finds", []),
        # Echoed back so the browser can tell whether the zone it just
        # detected is already the stored one, and skip a pointless write on
        # every startup.
        "timezone": config.get_preference("timezone", ""),
        # Everything the interface keeps in localStorage, the theme, the
        # palette, corner rounding, whether onboarding has been seen (§35E).
        #
        # **Reported as two bugs and it is one:** *"the theme resets to default
        # on every start"* and *"onboarding shows every time"*. Both were kept
        # in localStorage and nowhere else, and the desktop shell does not
        # reliably persist it: pywebview is a different browser with its own
        # profile, and if that profile is not stable across launches then every
        # setting stored there is a setting the app forgets.
        #
        # The browser still writes localStorage first: it is synchronous, it
        # works with the server unreachable, and it is what every existing
        # `appearancePref` read already goes through. This is the copy that
        # survives, seeded back on first load when the local one is empty.
        "ui_state": config.get_preference("ui_state", {}),
        # Reported (indirectly, this session): a preference that saves
        # correctly and is honoured correctly, `autonomous.py` and
        # `model_manager.py` both read these straight from storage, but
        # this response never echoed any of them back, so every Settings
        # checkbox bound to one of these showed unchecked again the moment
        # the page reloaded or the panel reopened, regardless of what was
        # actually saved. Defaults match the ones each reader already uses,
        # so a profile that never touched these sees the same value the
        # backend would have assumed anyway.
        "autonomous_tasks_enabled": config.get_preference("autonomous_tasks_enabled", False),
        "auto_tag_enabled": config.get_preference("auto_tag_enabled", True),
        "auto_link_enabled": config.get_preference("auto_link_enabled", True),
        "auto_dedupe_enabled": config.get_preference("auto_dedupe_enabled", True),
        "auto_stale_review_enabled": config.get_preference("auto_stale_review_enabled", False),
        "auto_capture_enabled": config.get_preference("auto_capture_enabled", False),
        "autonomous_tasks_interval_hours": config.get_preference(
            "autonomous_tasks_interval_hours", 6
        ),
        "autonomous_tasks_model": config.get_preference("autonomous_tasks_model", ""),
        "battery_efficient_mode": config.get_preference("battery_efficient_mode", False),
        "smart_model_routing_enabled": config.get_preference(
            "smart_model_routing_enabled", True
        ),
        "notifications_muted_except_reminders": config.get_preference(
            "notifications_muted_except_reminders", False
        ),
        "agent_activity_notices": config.get_preference("agent_activity_notices", "toasts"),
        # Same shape of bug as the autonomous-prefs block above, on the same
        # checkbox this session already restyled: PUT /preferences has always
        # accepted show_console_on_startup (PreferencesBody's own field), but
        # this response never echoed it back, so prefsCache.show_console_
        # on_startup was always undefined, the Settings checkbox always
        # rendered unchecked regardless of what was actually saved, and the
        # first-run Dev-view/User-view intro (console_view_intro_seen, gated
        # on this same response) would have shown on every single launch.
        "show_console_on_startup": config.get_preference("show_console_on_startup", True),
        "console_view_intro_seen": config.get_preference("console_view_intro_seen", False),
        # Default True, matching `_on_closing` in __main__.py: the two must
        # agree or the checkbox shows the opposite of what the window does.
        "close_to_tray": config.get_preference("close_to_tray", True),
        # Default False, matching `_run_desktop` in __main__.py.
        "new_window_on_launch": config.get_preference("new_window_on_launch", False),
        "avatar_style": _clean_avatar_style(config.get_preference("avatar_style", {})),
        "status_bar_hidden": config.get_preference("status_bar_hidden", []),
        "status_bar_clock": config.get_preference("status_bar_clock", False),
    }


#: Preferences the autonomous loop reads at the top of each pass. Changing
#: any of these should take effect on the loop's next tick, not its next
#: *scheduled* tick, which could be hours away, so writing one of these
#: wakes the loop early instead of leaving it asleep on a stale value.
_AUTONOMOUS_PREFS = frozenset(
    {
        "autonomous_tasks_enabled",
        "battery_efficient_mode",
        "autonomous_tasks_interval_hours",
        "auto_tag_enabled",
        "auto_link_enabled",
        "auto_dedupe_enabled",
        "auto_stale_review_enabled",
        "auto_capture_enabled",
    }
)


#: Preference keys that never reach the audit log (Library → Activity).
#: Reported directly: "idk what the go is with all the 'Edited your
#: settings' stuff", a click that toggles a status-bar icon or drags a
#: corner-rounding slider produced the exact same "Edited your settings"
#: row as changing the model backend or the auto-lock timeout, so the one
#: feed meant to answer "what did I actually do" was mostly cosmetic noise
#: with the real changes buried in it. `ui_state` alone is most of that
#: noise: it is the interface's *entire* look (theme, palette, corners,
#: zoom, shadow, glass, motion, see its own docstring above) behind one
#: key, so every appearance tweak wrote a row. The rest here are one-shot
#: internal bookkeeping (`*_intro_seen`, `tray_hide_explained`) or the two
#: status-bar toggles (§ this session): never a change a person would
#: describe as "something I did", only as "how it looks/behaves".
#: `set_preference` still runs for all of them; only the audit row is
#: skipped, so nothing about what is saved or restored changes.
_QUIET_PREFERENCE_KEYS = frozenset(
    {
        "ui_state",
        "status_bar_hidden",
        "status_bar_clock",
        "console_view_intro_seen",
        "tray_hide_explained",
    }
)


#: The audit log is kept for ever and shown in Activity, so a setting's words
#: go into it only when they are a short plain value. A name, a profile, a
#: dictionary of the person's words, a whole skill or persona were each copied
#: in full at every save (the profile was the one exception).
_PERSONAL_PREFERENCE_KEYS = frozenset({"user_profile", "display_name"})


def _preference_detail(key: str, value: object) -> str:
    #: A short list of short words (disabled_tools=['find_contradictions']) is
    #: a setting, not the person's words, and Activity is where it is checked.
    short_list = (
        isinstance(value, list)
        and len(value) <= 12
        and all(isinstance(v, str) and len(v) <= 40 for v in value)
        and key not in {"writing_dictionary", "link_offer_ignored", "skills", "personas"}
    )
    plain = short_list or isinstance(value, (bool, int, float)) or (isinstance(value, str) and len(value) <= 80)
    if key in _PERSONAL_PREFERENCE_KEYS or not plain:
        return f"{key}=…"
    return f"{key}={value}"


#: One window per model, cleaned at the door.
#:
#: Written by hand into a number box, so it is exactly the kind of value that
#: arrives as "", "auto", "16k", a negative, or a number somebody meant as
#: megabytes. Anything that is not a positive integer is stored as `None`,
#: which is this setting's own spelling of "auto", rather than rejected: a
#: single bad box must not fail the whole Settings save and lose the other
#: fields the same PUT carries.
#:
#: The upper bound is a sanity rail rather than a policy. A window is tokens,
#: and two million is past every model that exists; a number above it is a typo
#: or a paste, and honouring it would have the app build a prompt it then spends
#: a minute failing to send.
_MAX_SETTABLE_CONTEXT = 2_000_000


def _validated_context_windows(value: object) -> dict[str, int | None]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, int | None] = {}
    for name, window in value.items():
        key = str(name).strip()
        #: A model name is a short identifier; a long one is not a model, and
        #: the preferences file is not a place to let one accumulate.
        if not key or len(key) > 200:
            continue
        try:
            wanted = int(window)
        #: OverflowError: JSON's `1e999` is infinity, which has no int.
        except (TypeError, ValueError, OverflowError):
            cleaned[key] = None
            continue
        cleaned[key] = wanted if 0 < wanted <= _MAX_SETTABLE_CONTEXT else None
    return cleaned


#: Preferences that point this computer somewhere, start or install
#: something on it, let it go online, or change how its own window behaves.
#: Another device may move one only the safe way (the value given), or not at
#: all (None): the owner, 2026-10-11, "I need maximum trust ... proper
#: security for the lan". `searxng_url` aims this computer at any address on
#: its own network; `export_save_dir` picks where files land on its disk;
#: `backup_copy_dir` where every backup is copied (on Windows a UNC path
#: there is an SMB connection carrying the owner's sign-in, lansec-1025).
_THIS_COMPUTER_PREFERENCES: dict[str, object] = {
    "export_save_dir": None,
    "backup_copy_dir": None,
    "update_beta": False,
    "searxng_url": None,
    "update_channel": None,
    "show_console_on_startup": None,
    "close_to_tray": None,
    "new_window_on_launch": None,
    "searxng_autostart": False,
    "semantic_auto_install": False,
    "auto_update_enabled": False,
    "update_check_enabled": False,
    "web_search_enabled": False,
    "local_only_ai": True,
    "session_idle_ttl_minutes": "shorter",
}


def _refused_elsewhere(request: Request | None, key: str, value: object, current: dict) -> bool:
    """Whether another device is asking to loosen a this-computer setting."""
    if key not in _THIS_COMPUTER_PREFERENCES or request is None or not is_another_device(request):
        return False
    before = current.get(key)
    if value == before:
        return False
    safe = _THIS_COMPUTER_PREFERENCES[key]
    if safe == "shorter":
        try:
            return int(value) > int(before or 720)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return True
    return safe is None or value != safe


def _validated_preference(key: str, value):  # noqa: ANN001, ANN202
    """The value as it is stored. A skill saved from the editor goes through
    exactly what `save_skill` goes through, so a skill the AI can write is a
    skill the UI can write, and neither can store one that won't run."""
    check = {
        "skills": _validated_skills,
        "custom_templates": _validated_templates,
        "export_save_dir": _validated_export_dir,
        "backup_copy_dir": _validated_backup_copy_dir,
        "dashboard_quick_access": _validated_quick_access,
        "dashboard_quick_tints": _validated_quick_tints,
        "model_context_windows": _validated_context_windows,
    }.get(key)
    return check(value) if check else value


def _apply_preference(config, session: Session, key: str, value) -> None:
    """One validated preference written, with the side effects its key carries."""
    value = _validated_preference(key, value)
    config.set_preference(key, value)
    if key in ("season_hemisphere", "season_locale"):
        from tessellate.ai import recognise

        recognise.configure_hemisphere(
            config.get_preference("season_hemisphere", "auto"), config.get_preference("season_locale", "")
        )
    if key == "semantic_auto_install":
        # Either answer settles the ask-once question (frontend/js/semantic-notice.js).
        config.set_preference("semantic_choice_made", True)
        if value:
            # A yes starts the download now, as a visible task, rather than
            # at the next save: reset the "not allowed" state and embed once.
            service = deps.get_embeddings()
            service.reset_failure_state()
            from tessellate.core import jobs

            jobs.enqueue("embed-warm", service.embed_text, "warm up", name="search by meaning")
    if key in ("update_check_enabled", "auto_update_enabled"):
        # Either switch is an answer to the ask-once question (routes_update).
        config.set_preference("update_choice_made", True)
    if key == "warm_search_model_at_launch" and value:
        # Switched on mid-session: load it now rather than at the next
        # launch. Idempotent, so a model already warm costs nothing.
        from tessellate.ai import embeddings

        embeddings.start_warmup(deps.get_embeddings(), deps.get_db().session)
    if key in _QUIET_PREFERENCE_KEYS:
        return
    manager.log_action(session, "edited", "preferences", detail=_preference_detail(key, value))


def _wake_autonomous(config, changed_keys: set) -> None:
    """Wake the librarian after one of its settings changed; stop a pass that was switched off."""
    from tessellate.ai import autonomous

    #: **Switching it off stops the pass that is running, not only the next
    #: one.** Reported: "autonomous background agent tasks need to be fixed
    #: as I have accidentally turned them on multiple times and then I cant
    #: quit them, and then I turn battery saver mode on to try and stop
    #: them". Both are true of the code as it was: `wake()` only shortens
    #: the *sleep* between passes, and the enabled/battery checks run at the
    #: top of a pass, so a pass already walking the notebook read neither
    #: until it finished, which for a large notebook is many minutes of an
    #: agent the user has just told to stop.
    #:
    #: `request_stop()` sets the same flag the Quit button in the tasks
    #: panel sets, and `_run_optimization` checks it between every step, so
    #: the pass ends at its next checkpoint. Only on the way *off*: turning
    #: the librarian on, or changing its interval, should not kill a pass
    #: that is midway through being useful.
    turned_off = "autonomous_tasks_enabled" in changed_keys and not config.get_preference(
        "autonomous_tasks_enabled", False
    )
    battery_on = "battery_efficient_mode" in changed_keys and config.get_preference(
        "battery_efficient_mode", False
    )
    if turned_off or battery_on:
        autonomous.request_stop()
    autonomous.wake()


@router.put("/preferences")
def update_preferences(
    body: PreferencesBody, request: Request, session: Session = Depends(get_session)
) -> dict:
    config = deps.get_config()
    current = get_preferences()
    if any(_refused_elsewhere(request, k, v, current) for k, v in body.model_dump(exclude_none=True).items()):
        raise HTTPException(status_code=403, detail=REFUSAL)
    changed_keys = set()
    values = body.model_dump(exclude_none=True)
    for key in values.pop("unset", None) or []:
        if key in values:
            continue
        config.unset_preference(key)
        changed_keys.add(key)
    for key, value in values.items():
        _apply_preference(config, session, key, value)
        changed_keys.add(key)
    session.commit()
    if changed_keys & _AUTONOMOUS_PREFS:
        _wake_autonomous(config, changed_keys)
    return get_preferences()


@router.get("/preferences/defaults")
def get_preference_defaults() -> dict:
    """What every preference is in a notebook that never set it (Settings' reset)."""
    return _preferences_from(_FreshConfig())


#: The file Settings, Import and export writes, so a file of something else
#: (a notebook export, a skill) is refused by name rather than half-read.
SETTINGS_FILE_KIND = "memorymap-settings"
SETTINGS_FILE_VERSION = 1

#: Preferences that describe this computer or this install's own bookkeeping,
#: not a choice a person would carry to another one: the detected time zone, a
#: folder path on this disk, and the one-time "seen it" flags.
_NOT_EXPORTED = frozenset(
    {"timezone", "week_start_locale", "season_locale", "export_save_dir", "backup_copy_dir", "console_view_intro_seen", "tray_hide_explained"}
)


#: Lists a settings file adds to rather than replaces (OPEN row 558): an
#: item with the same name is the file's, every other one stays. Undo sends
#: `replace_lists` so the list it puts back is the one that was there.
_MERGED_LISTS = {"skills": 30, "personas": 20, "custom_templates": 20}


def _merged_list(current: object, incoming: list, cap: int) -> list:
    names = {str(item.get("name") or "").strip().lower() for item in incoming if isinstance(item, dict)}
    kept = [
        item
        for item in (current if isinstance(current, list) else [])
        if isinstance(item, dict) and str(item.get("name") or "").strip().lower() not in names
    ]
    return [*incoming, *kept][:cap]


def _exportable_keys() -> list[str]:
    return [key for key in PreferencesBody.model_fields if key not in _NOT_EXPORTED]


@router.get("/preferences/export")
def export_preferences() -> dict:
    """Every setting a person chose, as one JSON document to keep or move."""
    current = get_preferences()
    return {
        "kind": SETTINGS_FILE_KIND,
        "version": SETTINGS_FILE_VERSION,
        "app_version": __version__,
        "exported_at": utcnow().isoformat(timespec="seconds"),
        "preferences": {key: current[key] for key in _exportable_keys() if key in current},
    }


def _settings_file_preferences(payload: dict) -> dict:
    """The `preferences` of a settings file, or the 422 saying why it is not one."""
    if payload.get("kind") != SETTINGS_FILE_KIND:
        raise HTTPException(status_code=422, detail="That file is not a Tessellate settings file.")
    version = payload.get("version")
    if not isinstance(version, int) or version > SETTINGS_FILE_VERSION:
        raise HTTPException(
            status_code=422,
            detail="That settings file is from a newer version of Tessellate; update this one first.",
        )
    incoming = payload.get("preferences")
    if not isinstance(incoming, dict):
        raise HTTPException(status_code=422, detail="That settings file holds no settings.")
    return incoming


def _import_skip_reason(request: Request, key: str, value, current: dict, exportable: set) -> str:
    """Why an imported key is left out, or "" when it may be applied."""
    if _refused_elsewhere(request, key, value, current):
        return "only the computer Tessellate runs on can change this"
    if key in _NOT_EXPORTED:
        return "belongs to the computer it came from"
    if key not in exportable:
        return "not a setting this version has"
    try:
        PreferencesBody.model_validate({key: value})
    except ValueError:
        return "not a value this setting takes"
    return ""


@router.post("/preferences/import")
def import_preferences(payload: dict, request: Request, session: Session = Depends(get_session)) -> dict:
    """Apply a settings file, key by key, and say what was skipped and why.

    Each key is validated alone: one bad value (a file edited by hand, a key a
    newer version added) is reported and skipped rather than failing the whole
    file, so the rest still arrives. The writes go through `update_preferences`,
    so an imported value is cleaned exactly as one typed into Settings is.
    """
    incoming = _settings_file_preferences(payload)
    exportable = set(_exportable_keys())
    current = get_preferences()
    valid: dict[str, object] = {}
    skipped: list[dict[str, str]] = []
    unchanged = 0
    for key, value in list(incoming.items())[:400]:
        why = _import_skip_reason(request, key, value, current, exportable)
        if why:
            skipped.append({"key": key, "reason": why})
            continue
        if key in _MERGED_LISTS and isinstance(value, list) and not payload.get("replace_lists"):
            value = _merged_list(current.get(key), value, _MERGED_LISTS[key])
        if value is not None and current.get(key) != value:
            valid[key] = value
        else:
            unchanged += 1
    if valid:
        update_preferences(body=PreferencesBody.model_validate(valid), request=request, session=session)
    return {
        "applied": sorted(valid),
        "unchanged": unchanged,
        "skipped": skipped,
        "preferences": get_preferences(),
    }


@router.post("/system/console-mode", dependencies=[Depends(this_computer_only)])
def set_console_mode(
    body: dict, background_tasks: BackgroundTasks, session: Session = Depends(get_session)
) -> dict:
    """Switch Dev view / User view *live*, not just for the next launch, 
    asked for directly: togglable from Settings as well as the tray. Saves
    the preference the same way PUT /preferences would, then (desktop app,
    Windows only) restarts the whole process into the new console mode via
    __main__.restart_in_console_mode.

    The restart itself runs as a FastAPI background task, which the ASGI
    server only invokes *after* this response has actually gone out, doing
    it inline would mean `os._exit(0)` races the response itself off the
    wire, and the frontend's toast would never show ("did it even work?").
    A relaunch this can't reach (not the desktop app, not Windows, no
    pythonw.exe next to this interpreter) still saves the preference; the
    caller just won't see it take effect until the next launch, same as any
    other preference.

    Only restarts when the value actually changes, the first-run intro
    prompt calls this unconditionally with whatever was picked, and picking
    the option that already matches the current mode (the default, most of
    the time) must not restart the app the user just opened.
    """
    show_console = bool(body.get("show_console_on_startup"))
    config = deps.get_config()
    already = bool(config.get_preference("show_console_on_startup", True))
    config.set_preference("show_console_on_startup", show_console)
    manager.log_action(
        session, "edited", "preferences", detail=f"show_console_on_startup={show_console}"
    )
    session.commit()

    restarting = False
    if (
        show_console != already
        and os.getenv("TESSELLATE_DESKTOP") == "1"
        and sys.platform == "win32"
    ):
        # `importlib`, not an `import` statement: `tessellate.__main__` imports
        # `api.app`, which imports this module, so a statement here closes a
        # CodeQL py/cyclic-import loop: and deferring it into the function
        # body does not clear that, only dropping the statement does. The
        # desktop entry point is the caller here, not a dependency.
        restart_in_console_mode = _desktop_entry().restart_in_console_mode

        restarting = True
        background_tasks.add_task(restart_in_console_mode, not show_console)
    return {"show_console_on_startup": show_console, "restarting": restarting}


def _desktop_entry():
    """The desktop entry module, the one actually running.

    `sys.modules["__main__"]` first: a packaged build runs `__main__.py` as
    `__main__`, and PyInstaller bundles no second copy under the name
    `tessellate.__main__` (nothing imports it by that name, so its analysis
    never sees it), so `import_module` alone raised there and Settings'
    Restart answered 500. From source, `python -m tessellate` is the same
    module under the same key, and reusing it avoids importing a second copy
    of the launcher. The import is the fallback for everything else (tests,
    `uvicorn --factory`), where the running `__main__` is not ours.
    """
    running = sys.modules.get("__main__")
    if running is not None and hasattr(running, "restart_in_console_mode"):
        return running
    return importlib.import_module("tessellate.__main__")


@router.post("/system/restart", dependencies=[Depends(this_computer_only)])
def restart_app(background_tasks: BackgroundTasks) -> dict:
    """A plain restart, on request rather than tied to any one preference
    changing: ROADMAP item C, asked for directly. Several extras only take
    effect after a restart and the app said so without ever offering one;
    `restart_in_console_mode` already IS a generic "spawn a replacement
    process and exit this one," console-mode switching is just its first
    caller. This is the second: same mechanism, current console visibility
    preserved rather than flipped.

    `restart_app` in `__main__.py` starts a new copy that waits for this
    one to exit, then this one exits; the page waits for it and reloads.
    """
    #: Every launch the launcher made (INBOX 872: browser or desktop, any
    #: system, source or packaged), not only the desktop app on Windows. A bare
    #: `uvicorn --factory` or the tests have no launcher to start a new copy.
    if os.getenv("TESSELLATE_LAUNCHED") != "1" and os.getenv("TESSELLATE_DESKTOP") != "1":
        return {"restarting": False}
    background_tasks.add_task(_desktop_entry().restart_app)  # same cycle break
    return {"restarting": True}


def _validated_skills(raw: list[dict]) -> list[dict]:
    """Every skill, normalised: or a 422 naming the one that's wrong."""
    from tessellate.ai import tools

    known = set(tools.TOOLS)
    shipped = {skill["name"] for skill in skills.builtins()}
    out = []
    for item in raw:
        try:
            skill = skills.normalise(item, known)
        except skills.SkillError as exc:
            raise HTTPException(
                status_code=422,
                # A `SkillError` is a sentence written for whoever wrote the
                # skill (ai/skills.py, held by tests/test_core_message_wording.py).
                detail=f"{exc} “{item.get('name', '?')}” was not saved.",
            ) from exc
        if skill["name"] in shipped:
            raise HTTPException(
                status_code=422,
                detail=f"“{skill['name']}” is a built-in skill. Pick another name.",
            )
        out.append(skill)
    return out


def _validated_templates(raw: list[dict]) -> list[dict]:
    """Every saved template, name-checked, or a 422 naming the collision.

    Two items cannot share a name. Rejecting (rather than de-duping, the way
    `addSkill` on the frontend quietly does for skills) was the deliberate
    choice here: silently dropping a *different* saved template because its
    name was reused would be a surprise deletion of someone's own text,
    which a skill's shorter prompt doesn't risk in the same way. A name that
    is a built-in's is not a collision: it is how a built-in is edited
    (`BUILTIN_TEMPLATE_NAMES` above), and there can be one such edit per
    built-in for the same reason there can be one template per name.
    """
    seen: set[str] = set()
    out = []
    for item in raw:
        name = (item.get("name") or "").strip()
        if name in seen:
            raise HTTPException(
                status_code=422,
                detail=f"“{name}” is already used by another template.",
            )
        seen.add(name)
        out.append(item)
    return out


def _validated_export_dir(raw: str) -> str:
    """An absolute, existing, writable directory, or a 422 saying which
    check failed. Empty string always passes (resets to the default,
    `data_dir/exports`). Checked here, at save time, rather than at export
    time: a bad path caught now is a rejected preference; caught later it's
    a lost file, discovered only when the next export silently goes nowhere
    the user can find.
    """
    value = raw.strip()
    if not value:
        return ""
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise HTTPException(status_code=422, detail="Use a full path, not a relative one.")
    if not path.is_dir():
        raise HTTPException(status_code=422, detail=f"{path} isn't a folder that exists.")
    if not os.access(path, os.W_OK):
        raise HTTPException(status_code=422, detail=f"{path} isn't writable.")
    return str(path)


def _validated_backup_copy_dir(raw: str) -> str:
    """The second place a backup is copied to: the export folder's checks
    (absolute, exists, writable; empty clears it), and not the app's own
    backups folder, which would copy each file onto itself."""
    value = _validated_export_dir(raw)
    if value:
        own = os.path.realpath(backup.backups_dir(deps.get_config().data_dir))
        if os.path.realpath(value) == own:
            raise HTTPException(status_code=422, detail="That is already where backups are kept. Choose another folder.")
    return value


def _small_class(config) -> bool:
    return skills.small_class(config)


@router.get("/skills")
def list_skills() -> dict:
    """Everything runnable: the shipped skills and the user's own.

    The built-ins used to be a list in `app.js`, which meant the server could
    not resolve a skill the user had just clicked, and every field added to a
    skill had to be added in two places. Served from here for the same reason
    the web-search providers are: the interface cannot then offer something
    the API would reject.
    """
    from tessellate.ai import tools

    from tessellate.ai import skill_folder
    from tessellate.api.routes_debug import shown_path

    config = deps.get_config()
    catalog = []
    #: Phase E, decision 2: on a small model, a skill measured below the bar
    #: is labelled with why, rather than offered and hoped.
    rates = skills.measured_rates() if _small_class(config) else {}
    for skill in skills.catalog(config, set(tools.TOOLS)):
        # "This one changes things" is a different question from "this one
        # uses tools", and the UI marks it as such. A skill with steps but no
        # declared tools could do anything, so it counts.
        catalog.append(
            {
                **skill,
                "changes": bool(set(skill["tools"]) & tools.WRITE_TOOLS)
                or (not skill["tools"] and bool(skill["steps"])),
                "needs_larger_model": skills.larger_model_reason(skill["name"], rates) if rates else "",
                #: Runs with no model, composed from the notes (O7, `ai/skill_composer.py`).
                "composer": skill_composer.can_run(skill),
            }
        )
    where = skill_folder.folder(config)
    return {
        "skills": catalog,
        #: The user skills folder (B8): where to drop a `.md` skill, and every
        #: file there that did not load, with why, so a file that is not in
        #: the menu says so rather than being silently absent.
        "folder": {
            "path": shown_path(where) if where else "",
            "problems": skills.folder_skills(config, set(tools.TOOLS))[1],
        },
        "limits": {
            "skills": skills.MAX_SKILLS,
            "steps": skills.MAX_STEPS,
            "tools": skills.MAX_TOOLS,
            "inputs": skills.MAX_INPUTS,
        },
    }


# --- the memory stream (ROADMAP §39B) ---------------------------------------------
#
# What the AI has been told to remember, and the ability to un-tell it.
#
# `save_user_preference` lets the model write standing instructions that it
# then receives in its own system prompt on every later turn. That is a useful
# feature and a slightly alarming one, because it shipped with no way to see
# the list: the assistant's behaviour could change permanently, for a reason
# the user could not inspect, edit or undo. A rule you cannot read is
# indistinguishable from the model simply behaving oddly.
#
# So: list them, switch one off, delete one. `active` is a toggle rather than
# only a delete because "stop doing this for now" and "you never should have
# saved that" are different intentions, and the agent already filters on it.


class PreferenceBody(BaseModel):
    content: str | None = Field(default=None, max_length=200)
    active: bool | None = None
    #: Undo of answering a proposal (INBOX 898) puts the question back; Redo
    #: answers it again by sending `proposed: false` with the verdict.
    proposed: bool | None = None


class ProposalAnswer(BaseModel):
    """Yes or no to a preference the model suggested."""

    accept: bool


def _preference_out(row) -> dict:  # noqa: ANN001  # a UserPreference
    return {
        "id": row.id,
        "content": row.content,
        "active": bool(row.active),
        # Waiting for an answer, the model wrote it, the user has not said
        # yes. A third state, not "off": it is out of the prompt *and* the UI
        # shows it as a question rather than as a switch someone flipped.
        "proposed": bool(getattr(row, "proposed", False)),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


#: One page of the memory stream. Bounded because only the *active*
#: preferences are capped (`MAX_ACTIVE_PREFERENCES`): the switched-off ones
#: and the model's unanswered proposals accumulate for the life of the
#: notebook, and they are in this list too.
#:
#: The default is the maximum here for the reason `GALLERY_PAGE_SIZE` records
#: at length: the one caller (`app.js` 27411) reads the whole object and
#: cannot page it, because the response is `{preferences, ...}` rather than an
#: array. A thousand standing instructions is far past any real notebook and
#: is a bound the app fixes, which is what this class of flaw is about.
MEMORY_PAGE_SIZE = 1000
MEMORY_PAGE_SIZE_MAX = 1000


@router.get("/memory")
def list_memory(
    response: Response,
    limit: int = Query(default=MEMORY_PAGE_SIZE, ge=1, le=MEMORY_PAGE_SIZE_MAX),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    session: Session = Depends(get_session),
) -> dict:
    """A page of what the AI has been told to remember, newest first."""
    offset = paging.start(cursor, offset)
    from tessellate.ai import memory
    from tessellate.core.database import UserPreference

    total = session.scalar(select(func.count(UserPreference.id))) or 0
    rows = list(
        session.scalars(
            select(UserPreference)
            .order_by(UserPreference.created_at.desc(), UserPreference.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    paging.finish(response, offset, limit, total)
    return {
        "preferences": [_preference_out(r) for r in rows],
        "total": total,
        # The UI says which of these actually reach the model. Only the active
        # ones do, and only until the character budget runs out, newest first,
        # so a long-standing list quietly stops including its oldest entries.
        # Showing the budget beats letting someone wonder why rule 41 is ignored.
        "budget_chars": memory.MEMORY_STREAM_BUDGET_CHARS,
        "in_prompt": len(memory.persona_with_memory(session, "").strip()),
    }


@router.post("/memory", status_code=201)
def add_memory(body: PreferenceBody, session: Session = Depends(get_session)) -> dict:
    """Write a standing instruction by hand.

    `save_user_preference` lets the *model* add one when you tell it something
    in conversation. This is the other direction, and it is the one people
    reach for first: "I want it to always do X" is a thing you know before you
    have had the conversation that would teach it.

    Same limits as the tool, deliberately, the cap exists because every active
    preference is replayed into the system prompt on every round, and that is
    true whoever typed it.
    """
    from tessellate.ai.tools import MAX_ACTIVE_PREFERENCES
    from tessellate.core.database import UserPreference

    text_ = (body.content or "").strip()
    if not text_:
        raise HTTPException(status_code=422, detail="A preference can't be empty.")

    active = list(
        session.scalars(
            select(UserPreference).where(UserPreference.active == True)  # noqa: E712
        )
    )
    if any((row.content or "").strip().lower() == text_.lower() for row in active):
        raise HTTPException(status_code=409, detail="That one is already saved.")
    if len(active) >= MAX_ACTIVE_PREFERENCES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"There are already {len(active)} saved preferences, which is the "
                "limit. Turn one off before adding another."
            ),
        )

    row = UserPreference(content=text_)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _preference_out(row)


@router.post("/memory/{preference_id}/answer")
def answer_memory_proposal(
    preference_id: int, body: ProposalAnswer, session: Session = Depends(get_session)
) -> dict:
    """Accept or decline a preference the model suggested.

    Asked for directly: "can the ai pick up things and suggest the user adds it
    as a preference in that section with an accept or deny or similar popup??"
    - and the shape of the old behaviour is why that is the right question.
    `save_user_preference` used to write a standing instruction into every
    future system prompt with no confirmation at all, so a model that misread
    one sentence gave itself a permanent rule its user never agreed to.

    **Declining does not delete the row**, and that is deliberate: the
    duplicate check in `_save_user_preference` looks at *every* preference, so
    a kept row is what stops the model proposing the same thing again an hour
    later. It reads as an ordinary switched-off preference afterwards, which
    it is: and can be switched on if the user changes their mind.

    Answering something that is not a proposal is a no-op rather than an
    error: two windows, two clicks, one of them second.
    """
    from tessellate.core.database import UserPreference

    row = deps.get_or_404(session, UserPreference, preference_id, "That preference could not be found.")
    if not getattr(row, "proposed", False):
        return _preference_out(row)
    row.proposed = False
    row.active = bool(body.accept)
    session.commit()
    session.refresh(row)
    return _preference_out(row)


@router.patch("/memory/{preference_id}")
def update_memory(
    preference_id: int, body: PreferenceBody, session: Session = Depends(get_session)
) -> dict:
    from tessellate.core.database import UserPreference

    row = deps.get_or_404(session, UserPreference, preference_id, "That preference could not be found.")
    if body.content is not None:
        text_ = body.content.strip()
        if not text_:
            raise HTTPException(status_code=422, detail="A preference can't be empty.")
        row.content = text_
    if body.active is not None:
        row.active = body.active
    if body.proposed is not None and hasattr(row, "proposed"):
        row.proposed = body.proposed
    session.commit()
    session.refresh(row)
    return _preference_out(row)


@router.delete("/memory/{preference_id}")
def forget_memory(preference_id: int, session: Session = Depends(get_session)) -> dict:
    from tessellate.core.database import UserPreference

    row = deps.get_or_404(session, UserPreference, preference_id, "That preference could not be found.")
    session.delete(row)
    session.commit()
    return {"status": "ok"}


@router.get("/audit")
def audit_log(
    limit: int = Query(default=100, ge=1, le=500),
    entity_type: str = Query(default="", max_length=40),
    id: int | None = Query(default=None),  # noqa: A002
    session: Session = Depends(get_session),
) -> list[dict]:
    """The activity log, newest first (viewer in the UI).

    `entity_type` filters *before* the limit, and that ordering is the whole
    reason it exists. The Library's AI Skills tab asked for 20 rows and then
    filtered them in the browser for skill runs, so on any notebook where the
    last twenty things that happened were note edits, a real history of skill
    runs rendered as "No skill execution logs found". Reported as the skill
    logs not working. Filtering in SQL means the limit counts the rows you
    asked for rather than the rows you are about to throw away.

    `id` is the Library Activity card's own "view the whole thing", its own
    list comes from `_activity()` (routes_library.py), which clips `detail`
    to `ACTIVITY_DETAIL_CHARS` so a long one doesn't blow out the card grid.
    This route never clips (`detail` below is the raw column), so re-fetching
    one row by id is what a click-to-expand needs, without a second endpoint.
    """
    query = select(AuditLog)
    if id is not None:
        query = query.where(AuditLog.id == id)
    elif entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    rows = session.scalars(query.order_by(AuditLog.id.desc()).limit(limit))
    return [
        {
            "id": row.id,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "actor": row.actor or events.ACTOR_USER,
            "detail": row.detail,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


#: A spreadsheet runs a cell that opens with one of these as a formula, and an
#: audit trail carries free text a person (or a web page the agent read) wrote.
_CSV_FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")

#: One page of the export, and the most one call may ask for: the list
#: endpoints' recipe (`limit`, `offset`, `X-Total-Count`), with a ceiling
#: because "bounded by the retention rule" has been wrong before and a file of
#: a million rows is a file nobody opens. A caller with more walks `offset`.
AUDIT_EXPORT_MAX_ROWS = 100_000

#: The columns, in order: when, who, what, which kind of thing, which one, and
#: its title (the log's own one-line description of it). No payload, ever.
AUDIT_EXPORT_COLUMNS = ["time", "actor", "action", "entity kind", "entity id", "title"]


def _csv_safe(value: object) -> object:
    """A cell that cannot be read as a formula (the OWASP CSV-injection rule)."""
    if isinstance(value, str) and value.startswith(_CSV_FORMULA_LEAD):
        return "'" + value
    return value


def _not_private_events(query):
    """Drop every event about a private note, and the vault's own.

    The file leaves the app, and a private note exists so that nothing about
    what it says does. An event on one carries its title or a clip of it in
    `detail`; the vault's events (unlocking, re-keying) say that private notes
    exist and when they were opened. Neither is part of a hand-over file.

    Two ways an event is about a private note: the note is still there and
    private (looked up by id), or it was purged, and its id matches nothing
    any more. A purge seals the events it leaves behind with a `private` flag
    in their payload (`manager.seal_private_events`), and that flag is the
    second test. `is_(True)` rather than `== True`, so an event with no
    payload at all (SQL null) is kept rather than dropped by a null compare.
    """
    private_ids = select(Entry.id).where(Entry.is_private == True)  # noqa: E712
    return query.where(
        AuditLog.entity_type != "vault",
        ~(
            AuditLog.entity_type.in_(("entry", "note", "entries"))
            & AuditLog.entity_id.in_(private_ids)
        ),
        ~AuditLog.payload["private"].as_boolean().is_(True),
    )


@router.get("/audit/export.csv")
def audit_export_csv(
    limit: int = Query(default=AUDIT_EXPORT_MAX_ROWS, ge=1, le=AUDIT_EXPORT_MAX_ROWS),
    offset: int = Query(default=0, ge=0),
    cursor: str | None = paging.cursor_param(),
    entity_type: str = Query(default="", max_length=40),
    session: Session = Depends(get_session),
) -> Response:
    """The activity log as a file a professional can hand over: who, what, when.

    Oldest first (a trail reads forward), six columns, and never a payload
    value: a payload holds whole note texts. Events about private notes are
    left out (`_not_private_events`). Every cell is defanged against CSV
    formula injection (`_csv_safe`): the log carries free text a person, or a
    web page the agent read, wrote. `limit` and `offset` page it and
    `X-Total-Count` is the size of the same filtered set. The export is itself
    logged, so the trail records who took it.
    """
    offset = paging.start(cursor, offset)
    query = _not_private_events(select(AuditLog))
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(query.order_by(AuditLog.id).limit(limit).offset(offset))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(AUDIT_EXPORT_COLUMNS)
    for row in rows:
        writer.writerow(
            [
                _csv_safe(value)
                for value in (
                    row.created_at.isoformat(),
                    row.actor or events.ACTOR_USER,
                    row.action,
                    row.entity_type,
                    row.entity_id if row.entity_id is not None else "",
                    row.detail or "",
                )
            ]
        )
    manager.log_action(session, "exported", "data", detail="audit csv")
    session.commit()
    exported = Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=tessellate-activity.csv",
            "X-Total-Count": str(total),
        },
    )
    #: The list recipe's next-page cursor, beside `X-Total-Count`.
    paging.finish(exported, offset, limit, total)
    return exported


def _feed_item(row: AuditLog) -> dict:
    """One event as the feed reports it: what happened, not what it stored."""
    span = events.snapshot_span(row)
    item = {
        "id": row.id,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "actor": row.actor or events.ACTOR_USER,
        "detail": row.detail,
        # A snapshot's `after` is the whole state, not the fields this event
        # set, so naming them would be a lie about what changed.
        "changed": [] if span else sorted((row.payload or {}).get("after", {}) or {}),
        #: How many events this row stands for, absent on an ordinary one.
        "snapshot": span,
        #: Its values were dropped by the compactor; the row is still a fact.
        "compacted": events.is_compacted(row),
        "created_at": row.created_at.isoformat(),
    }
    #: A restore by an undo names the events it reversed, so the Recent
    #: activity widget can stop offering to undo what is already undone.
    undid = (row.payload or {}).get("undid") if row.action == "restored" else None
    if isinstance(undid, list):
        item["undid"] = [i for i in undid if isinstance(i, int)]
    return item


class UndoBody(BaseModel):
    #: Whose changes: `system:librarian`, `ai:<tool>`, `system:<job>`.
    actor: str = Field(default="", max_length=80)
    #: Or several, as one: a skill run's tools (its result's `undo_span`).
    actors: list[str] = Field(default_factory=list, max_length=40)
    #: Undo what they did after this event id (the feed's cursor).
    since: int = Field(default=0, ge=0)
    #: And up to this one, inclusive (a run's last event); 0 for no bound.
    until: int = Field(default=0, ge=0)
    #: On by default: the first answer is always the plan, never the change.
    dry_run: bool = True
    #: Put back the actor's fields even on a note changed since by someone else.
    force: bool = False


@router.post("/events/undo")
def undo_actor(body: UndoBody, session: Session = Depends(get_session)) -> dict:
    """Undo what one actor did since a point in the log (`events.undo`).

    "Undo auto-filing" and a skill run's Undo (Brief 13) both come down to
    this: the actor's changes after a mark, each field put back to what it was
    before the actor's first change. A dry run by default, so the plan a
    person is shown is the plan that runs. The person is not an actor this
    undoes: their own history is the per-note History sheet, one change at a
    time, where they can see what they are putting back.
    """
    names = [a for a in body.actors if a] or ([body.actor] if body.actor else [])
    if not names or any(len(a) > 80 for a in names):
        raise HTTPException(status_code=422, detail="Say whose changes to undo.")
    if events.ACTOR_USER in names:
        raise HTTPException(status_code=400, detail="Undo works on the AI's changes, not yours.")
    result = events.undo(
        session,
        body.actor if not body.actors else names,
        body.since,
        until_id=body.until or None,
        apply=not body.dry_run,
        force=body.force,
    )
    if not body.dry_run:
        session.commit()
    return result


@router.get("/events")
def event_feed(
    since: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    entity_type: str = Query(default="", max_length=40),
    include_quiet: bool = Query(default=False),
    tail: int = Query(default=0, ge=0, le=100),
    session: Session = Depends(get_session),
) -> dict:
    """The event log forwards, for anything that follows what happens here.

    `tail=N` is where a follower starts: the newest N events (after `since`
    and the filters), still oldest first, with the cursor after the last. A
    strip opening for the first time wants the last few things that
    happened, and without it the only way in was the first hundred events of
    the notebook's life, or `/audit` backwards and a cursor worked out by
    hand. It is the Dashboard's Recent activity widget's first read.

    `/audit` reads backwards from now, which is what a viewer wants and what
    a feed cannot use: a poller has to ask "what has happened since the last
    thing I saw" and get it in the order it happened. So this is ascending
    from `since` (exclusive), with `cursor` to pass back next time, and it
    is what a Dashboard or Timeline activity strip should read instead of
    scanning the notes table for recency (WORLD_CLASS_PLAN B1).

    Payloads are not returned: they carry whole field values, which for a
    note is its entire text, and a feed that ships every version of every
    note is a different thing from a feed. `changed` names the fields each
    event set, which is what a strip renders, and `/entries/{id}/history`
    has the values when something actually needs them.

    **A compacted event says what it is instead of naming fields.** The
    compactor (`events.compact`) folds a run of old events into one
    snapshot whose `after` holds the entity's whole state at that point, so
    reading `after` off it named every field of the note and reported one
    change as having set all of them at once, which never happened. Such a
    row reports `changed: []` and a `snapshot` count of the events it
    stands for; the rows behind it, whose values were dropped, report
    `compacted: true`. Both are the honest answer to "what happened here",
    and both are what a strip needs to render a run of folded history as
    one line rather than as a burst of edits.
    """
    query = select(AuditLog).where(AuditLog.id > since)
    #: One type or a comma list: a strip about the notebook's content wants
    #: notes, documents, boards and reminders, and not the preference toggles
    #: and model downloads that would otherwise fill its last ten rows.
    types = [part.strip() for part in entity_type.split(",") if part.strip()]
    if types:
        query = query.where(AuditLog.entity_type.in_(types))
    if not include_quiet:
        query = query.where(AuditLog.action.notin_(sorted(events.QUIET_ACTIONS)))
    if tail:
        rows = list(session.scalars(query.order_by(AuditLog.id.desc()).limit(tail)))[::-1]
    else:
        rows = list(session.scalars(query.order_by(AuditLog.id.asc()).limit(limit)))
    return {"items": [_feed_item(row) for row in rows], "cursor": rows[-1].id if rows else since}


@router.delete("/audit")
def clear_audit_log(
    entity_type: str = Query(..., max_length=40),
    session: Session = Depends(get_session),
) -> dict:
    """Asked for directly: a "Clear" button for the AI Skills sidebar's own
    log list. `entity_type` is required, not optional: this deliberately
    cannot clear the whole audit trail (note edits, deletes, private-note
    decryption events: real accountability history, not a scrollback
    buffer someone would want to blank), only one filtered slice of it at a
    time, the same scope `GET /audit?entity_type=` already reads."""
    deleted = session.query(AuditLog).filter(AuditLog.entity_type == entity_type).delete()
    session.commit()
    return {"deleted": deleted}


@router.post("/recycle-bin/empty")
def empty_recycle_bin(session: Session = Depends(get_session)) -> dict:
    from tessellate.entry import bin as other_bin

    removed = manager.empty_recycle_bin(
        session, uploads_dir=deps.get_config().uploads_dir
    )
    #: The bin's documents and reminders go with its notes (5 item 10).
    removed += other_bin.empty(session)
    return {"removed": removed}


# --- optional extras ---------------------------------------------------------


@router.get("/extras")
def list_extras() -> dict:
    """What can be installed, and what already is.

    The install itself reports through /tasks like every other background job,
    so this is only the catalogue and the current state.
    """
    state = extras.current()
    bulk = extras.bulk_status()
    return {
        "extras": extras.status(),
        "bundles": extras.bundles(),
        #: A bulk action is running between two of its packages too, when
        #: `state` is idle for a moment: the screen keeps polling through it.
        "running": state.running or bulk["running"],
        "installing": state.extra_id if state.running else "",
        "step": state.step,
        "outcome": state.outcome,
        "log": list(state.log),
        "bulk": bulk,
    }


class ExtrasBulkBody(BaseModel):
    """A bulk action: ids from the allowlist, or one bundle's id. Never a
    package spec: `core/extras.start_bulk` refuses any id it does not hold."""

    action: str = Field(max_length=20)
    ids: list[str] = Field(default_factory=list, max_length=50)
    bundle: str = Field(default="", max_length=40)


@router.post("/extras/bulk", dependencies=[Depends(this_computer_only)])
def bulk_extras(body: ExtrasBulkBody) -> dict:
    """Install, remove or reinstall several extras, one after another, as one
    background job (INBOX 595). Each package reports its own outcome in
    `GET /extras`'s `bulk.items`; one failing does not stop the rest."""
    started, message = extras.start_bulk(body.action, body.ids, bundle=body.bundle)
    return {"started": started, "message": message}


@router.post("/extras/{extra_id}/install", dependencies=[Depends(this_computer_only)])
def install_extra(extra_id: str, reinstall: bool = False) -> dict:
    """Start installing one extra **from the allowlist**.

    The path names an entry in `core/extras.py`; the package spec handed to pip
    is never anything the client sent. That is the whole security property here
    - `pip install <a name from a request body>` is arbitrary code execution by
    design, and validating the string afterwards does not fix it.
    """
    started, message = extras.start(extra_id, reinstall=reinstall)
    return {"started": started, "message": message}


@router.post("/extras/{extra_id}/uninstall", dependencies=[Depends(this_computer_only)])
def uninstall_extra(extra_id: str) -> dict:
    """Remove one extra, by the same allowlist id the install uses."""
    started, message = extras.remove(extra_id)
    return {"started": started, "message": message}


# --- embedding models ---------------------------------------------------------


@router.get("/embedding-models")
def list_embedding_models() -> dict:
    """Which embedding models are on this machine, and what they cost.

    `can_download` is here rather than left for the client to infer: without
    `huggingface_hub` (which arrives with the semantic-search extra) every
    button on this screen would start something that cannot finish, and a
    disabled button with a reason beats a download that fails on an ImportError.
    """
    state = embedmodels.current()
    return {
        "models": embedmodels.status(),
        "cache": str(embedmodels.cache_root()),
        "can_download": embedmodels.can_download(),
        "running": state.running,
        "downloading": state.model_id if state.running else "",
        "step": state.step,
        "outcome": state.outcome,
        "log": list(state.log),
    }


class EmbeddingChoiceBody(BaseModel):
    #: A catalogue id (`core/embedmodels.catalogue`), never a repo or a path.
    id: str = Field(max_length=80)


@router.get("/embedding-models/choices")
def embedding_model_choices() -> dict:
    """Settings, Models' list (INBOX 700): every model on offer with its
    facts, which one search uses now, and a switch in progress."""
    from tessellate.core import embedswitch

    manager = deps.get_model_manager()
    backend = manager.embedding_backend()
    model = manager.embedding_model() if backend == "ollama" else manager.embedding_st_model()
    from tessellate.core import embedfind

    choices = embedmodels.catalogue()
    #: Which Ollama rows are pulled already, for Install against Reinstall
    #: and Uninstall (the owner's second addendum). Ollama's local list only.
    ollama = deps.get_ollama()
    try:
        pulled = {str(m.get("name", "")) for m in (ollama.list_models() or [])} if ollama.is_running() else set()
    except Exception:  # noqa: BLE001  # Ollama down: nothing is pulled as far as this screen knows
        pulled = set()
    for row in choices:
        if row["backend"] == "ollama":
            row["downloaded"] = row["model"] in pulled or f"{row['model']}:latest" in pulled
    return {
        "choices": choices,
        #: Where the built-in models are kept, said in words under the list.
        "cache": str(embedmodels.cache_root()),
        #: Already on this computer, outside the catalogue (the owner's
        #: addendum): a read-only scan, offline.
        "found": embedfind.found(deps.get_ollama()),
        "current": {"backend": backend, "model": model},
        "switch": embedswitch.status(),
    }


@router.post("/embedding-models/use", dependencies=[Depends(this_computer_only)])
def use_embedding_model(body: EmbeddingChoiceBody) -> dict:
    """Switch search to one catalogue entry, in the background. An entry
    whose licence or loading rules forbid one press is refused here too,
    not only by its missing button."""
    from tessellate.core import embedswitch

    from tessellate.core import embedfind

    if body.id.startswith("found"):
        resolved = embedfind.resolve(body.id, deps.get_ollama())
    else:
        resolved = embedmodels.resolve_choice(body.id)
    if resolved is None:
        raise HTTPException(status_code=400, detail="That model can't be switched to from here.")
    started, message = embedswitch.start(*resolved)
    return {"started": started, "message": message}


class EmbeddingPullBody(BaseModel):
    name: str = Field(max_length=200)


@router.post("/embedding-models/pull", dependencies=[Depends(this_computer_only)])
def pull_embedding_model(body: EmbeddingPullBody) -> dict:
    """Pull a model by name (INBOX 700, the owner's second addendum).

    A Hugging Face repo is checked against the Hub's metadata, on this click
    and never before, and fetched only if the built-in engine can load it
    (`embedmodels.start_typed` says why not otherwise). An Ollama name goes
    to Ollama's own pull, a Background task with its bytes. Either way the
    model then appears under Found on this computer, with Use."""
    from tessellate.ai import model_cards, model_manager

    kind, name = embedmodels.parse_typed_name(body.name)
    if kind is None:
        return {"started": False, "message": name, "source": ""}
    if kind == "hf":
        started, message = embedmodels.start_typed(name)
        return {"started": started, "message": message, "source": "huggingface"}
    #: An Ollama name is checked by the rules of "Download another model".
    info = model_cards.inspect_model_name(name)
    if not info.get("valid"):
        return {"started": False, "message": info.get("error") or "That is not a model name.", "source": ""}
    name = info["name"]
    ollama = deps.get_ollama()
    try:
        running = ollama.is_running()
        installed = {str(m.get("name", "")) for m in (ollama.list_models() or [])} if running else set()
    except Exception:  # noqa: BLE001  # an Ollama that cannot answer is one that is not there
        running, installed = False, set()
    if not running:
        return {"started": False, "message": "Ollama isn't running. Start it and try again.", "source": "ollama"}
    if name in installed or f"{name}:latest" in installed:
        return {"started": False, "message": f"{name} is already in Ollama: it is under Found on this computer.", "source": "ollama"}
    if not model_manager.start_pull(ollama, name):
        return {"started": False, "message": f"{name} is already downloading.", "source": "ollama"}
    return {"started": True, "message": f"Pulling {name} into Ollama. Background tasks shows its progress.", "source": "ollama"}


@router.post("/embedding-models/{model_id}/download", dependencies=[Depends(this_computer_only)])
def download_embedding_model(model_id: str, reinstall: bool = False) -> dict:
    """Fetch one model **from the allowlist** in `core/embedmodels.py`.

    Same property as the extras installer: the repo id handed to the hub is
    never anything the client sent. A repo id from a request is a path that
    gets fetched and written to disk.

    A reinstall removes first, because that is the state the button exists for
    - a half-finished download leaves a directory that looks installed and
    loads as a corrupt model, and fetching over the top of it resumes the same
    broken snapshot.
    """
    if reinstall:
        started, message = embedmodels.reinstall(model_id)
    else:
        started, message = embedmodels.start(model_id)
    return {"started": started, "message": message}


@router.delete("/embedding-models/{model_id}", dependencies=[Depends(this_computer_only)])
def remove_embedding_model(model_id: str) -> dict:
    """Delete one model from the cache, by the same allowlist id."""
    removed, message = embedmodels.remove(model_id)
    return {"removed": removed, "message": message}


@router.get("/logs")
def server_logs(limit: int = Query(default=200, ge=1, le=logbuffer.MAX_RECORDS)) -> list[dict]:
    """Recent server-side log records for the Settings → Logs viewer."""
    return logbuffer.recent(limit=limit)


class ClientError(BaseModel):
    """One thing that went wrong in the browser, on its way to the terminal."""

    message: str = Field(max_length=2000)
    #: Where it happened, when the browser knows: "app.js:6088:12". Free text
    #: because a stack frame's shape differs per engine and none of it is
    #: parsed: it is read by a person.
    source: str = Field(default="", max_length=500)
    #: "error" | "unhandledrejection" | "csp", what kind of failure this was,
    #: since the three need different first questions asked about them.
    kind: str = Field(default="error", max_length=40)


@open_router.post("/logs/client", status_code=204)
def record_client_error(body: ClientError, response: Response) -> None:
    """Put a browser-side failure into the same log everything else uses.

    Asked for directly: *"can you make any other erros like what aoppeared on
    the loading screen appear in the logs as well?? the terminal and logs need
    to capture everything."*

    The gap was real and had just cost a session. A JavaScript error aborts
    the rest of the file it is in, so the app can hang on its loading screen
    with **nothing** in the terminal, nothing in Settings → Logs, and the only
    record sitting in a browser console nobody opens, least of all in the
    desktop shell, which has no obvious way to open one. The crash that
    prompted this (`Cannot access 'captureStagedFiles' before initialization`)
    was invisible to every log this app keeps.

    Deliberately `logger.error`, not a new channel: `logbuffer`'s handler is
    already attached to the root logger, so this reaches the terminal, the
    Settings → Logs viewer and `/logs/stream` at once, with no new plumbing to
    keep in step. The `[browser]` prefix is what tells a reader the failure
    happened on the other side of the wire, which changes what they should
    look at next.

    **On `open_router`, outside the unlock gate, on purpose.** This has to
    work *before* unlock: the loading-screen hang it exists for happens with
    the lock overlay still up, and a crash report that needs a token cannot
    describe the failure that stopped the token from ever being used. Every
    other route in this module stays behind `locked`.

    What it accepts is bounded instead of authenticated: three short strings,
    length-capped by the schema, appended to a ring buffer that already caps
    itself at `MAX_RECORDS`, reachable only from an origin the CSP pins to
    `'self'` on a server that binds to localhost. The worst an abuser of it
    can do is push older lines out of a 500-record buffer on their own
    machine.
    """
    # **Through `safe_value`, not raw.** Everything in this payload is
    # attacker-shaped by construction: it is text the browser was handed by
    # whatever failed, and a message containing a newline would draw a forged
    # second row in the Settings → Logs viewer while control characters can
    # rewrite what a terminal shows. `logbuffer.sanitise` runs at the ring
    # buffer and so protects the viewer only; the terminal sees the raw
    # record, which is exactly why this module's own helper exists and says
    # to clean at the call site.
    logger = logging.getLogger("tessellate.browser")
    kind = logbuffer.safe_value(body.kind, limit=40)
    message = logbuffer.safe_value(body.message, limit=logbuffer.MAX_MESSAGE_CHARS)
    where = f" ({logbuffer.safe_value(body.source, limit=200)})" if body.source else ""
    logger.error("[browser/%s] %s%s", kind, message, where)
    response.status_code = 204


@router.get("/logs/stats")
def server_log_stats(
    limit: int = Query(default=200, ge=1, le=logbuffer.MAX_RECORDS),
) -> dict:
    """How complete the log above actually is.

    A separate call rather than a wrapper around the records, so the shape of
    /logs stays a plain list for everything already reading it.
    """
    return logbuffer.stats(limit=limit)


@router.delete("/logs")
def clear_server_logs() -> dict:
    logbuffer.clear()
    return {"cleared": True}


# How long a single stream lives before it hands over to the browser's own
# reconnect, and how often it looks for new records. The cap is not a
# limitation to work around, EventSource reconnects on its own and resends
# Last-Event-ID, so the handover is seamless, and a stream that lives forever
# is a resource nothing ever reclaims when a tab is left open for a week.
LOG_STREAM_SECONDS = 10 * 60
LOG_STREAM_POLL = 0.7
LOG_STREAM_HEARTBEAT = 15


@router.get("/logs/stream")
async def stream_server_logs(request: Request, after: int = 0) -> StreamingResponse:
    """A live log feed, so the Logs screen reads like a terminal.

    Asked for directly: the screen should behave "like the terminal running in
    the background", not a list you refresh by hand.

    **NDJSON over fetch rather than the EventSource the roadmap suggested.**
    EventSource cannot set request headers, and this app authenticates with
    `X-Auth-Token`, so an EventSource here would simply 401. The usual way
    round that is to put the token in the query string, which is a bad trade
    anywhere and a farcical one on the endpoint that serves the log: the token
    would be written into the very records it is protecting. `fetch` carries
    the header, and NDJSON matches the chat and digest streams the app already
    has, so the browser-side reader is the one that already exists.

    Polling the ring buffer rather than registering a subscriber on it. That
    sounds like the lazier choice and is the more robust one: a subscriber
    registry means the logging handler pushes into per-connection queues, so a
    slow or dead reader can block or grow unboundedly *inside logging itself*, 
    and a logging path that can stall is a far worse failure than a console
    running 700ms behind. One reader, one process, one deque.
    """

    async def lines() -> AsyncIterator[str]:
        cursor = after
        loop = asyncio.get_running_loop()
        started = loop.time()
        last_sent = started
        # An immediate first line, so the reader knows the stream is live
        # before anything has been logged, and learns where it is starting
        # from, which is what makes "dropped" meaningful on the client.
        yield json.dumps(
            {"type": "open", "cursor": cursor, "latest": logbuffer.latest_seq()}
        ) + "\n"
        while True:
            if await request.is_disconnected():
                return
            now = loop.time()
            # Drain BEFORE checking the deadline. The other order loses every
            # record that arrived in the last poll interval of the connection:
            # the client reconnects from its cursor and those records are
            # inside the buffer but behind it, so they are never sent at all.
            for record in logbuffer.since(cursor):
                cursor = record.get("seq", cursor)
                yield json.dumps({"type": "record", "record": record}) + "\n"
                last_sent = now
            if now - started > LOG_STREAM_SECONDS:
                # Hand back to the client's own reconnect rather than holding a
                # connection open forever for a tab left open all week.
                yield json.dumps({"type": "reconnect", "cursor": cursor}) + "\n"
                return
            if now - last_sent > LOG_STREAM_HEARTBEAT:
                # Keeps the connection from being reaped as idle, and doubles
                # as the client's proof that the server is still there rather
                # than merely quiet.
                yield json.dumps({"type": "ping", "cursor": cursor}) + "\n"
                last_sent = now
            await asyncio.sleep(LOG_STREAM_POLL)

    return StreamingResponse(
        lines(),
        media_type="application/x-ndjson",
        headers={
            # Same reasoning as the chat stream: stop a reverse proxy buffering
            # a stream whose whole value is arriving promptly.
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )


# Preferences safe to put in a file the user will send to a stranger.
#
# An allowlist, not a denylist, and that choice is the whole design. A denylist
# has to predict every sensitive key anyone will ever add; this one only has to
# name the ones that help diagnose a bug. Anything not here is reported by
# name, type and size, "persona_prompt: string, 412 chars", which is enough
# to tell whether a setting is involved without disclosing what it says.
DIAGNOSTIC_PREFERENCES = frozenset(
    {
        "ai_enabled",
        "tools_enabled",
        "chat_model",
        "utility_model",
        "embedding_backend",
        "embedding_model",
        "embedding_st_model",
        "recycle_bin_days",
        "conversation_retention_days",
        "timezone",
        "week_start",
        "web_search_enabled",
        "searxng_autostart",
        "search_provider",
        "thinking_enabled",
        "guided_mode",
        "auto_categorise",
        # Which backend answered is the first question any "the AI is broken"
        # report needs. `llm_api_key` is deliberately NOT here, it stays
        # described-not-disclosed like every other secret.
        "llm_provider",
        "llm_base_url",
        "local_only_ai",
        # How long answers were asked to be, which is the first thing to check
        # in a "the AI is slow" or "the AI is too terse" report (§11).
        "response_mode",
    }
)


def _redacted_preferences(preferences: dict) -> dict:
    """Diagnostic settings verbatim; everything else described, not disclosed."""
    kept: dict = {}
    withheld: dict = {}
    for key, value in sorted(preferences.items()):
        if key in DIAGNOSTIC_PREFERENCES:
            # An address is kept, a password typed into it is not (SEC-12).
            kept[key] = security.without_userinfo(value) if key.endswith("_url") and isinstance(value, str) else value
            continue
        shape = type(value).__name__
        if isinstance(value, str):
            withheld[key] = f"{shape}, {len(value)} chars"
        elif isinstance(value, (list, dict)):
            withheld[key] = f"{shape}, {len(value)} items"
        else:
            withheld[key] = shape
    return {"included": kept, "withheld": withheld}


BUNDLE_README = """Tessellate: support bundle
=============================

What this is
------------
A snapshot of what the app can see about itself, collected so you can attach
it to a bug report. Everything in it was already on this machine and already
visible somewhere in the app; this file only gathers it into one place.

Nothing was sent anywhere. This file was written to your disk and it is
entirely your choice whether to share it.

What is in it
-------------
  logs.json         the recent server log, exactly as Settings -> Logs shows
  preferences.json  your settings, with free-text ones withheld (see below)
  status.json       app version, platform, and the state of Ollama, the
                    embedding model and SearXNG
  counts.json       how many notes, categories and documents exist, numbers
                    only, never their contents

What is NOT in it
-----------------
  · No note, document, chat or reminder content of any kind.
  · No password, and nothing derived from one.
  · No private-note data, encrypted or otherwise.
  · Free-text settings (display name, personas, custom prompts) are listed by
    name and length only, under "withheld" in preferences.json.

Worth a glance before you send it
---------------------------------
Log messages can quote things you typed, a chat question, or the title of a
page you opened. Open logs.json and skim it if that matters to you.
"""


@router.get("/support-bundle")
def support_bundle(session: Session = Depends(get_session)) -> Response:
    """Everything a bug report needs, in one file, collected locally.

    Asked for indirectly ("an interface for managing the application… errors
    etc") and echoed by an outside review. Deliberately *not* crash reporting:
    nothing is transmitted, the file lands on disk, and the user decides
    whether it ever goes anywhere. That distinction is why this was accepted
    and opt-in telemetry was not.
    """
    config = deps.get_config()
    buffer = io.BytesIO()

    def _safely(collect, fallback):
        """A bundle that half-collects is far better than one that 500s.

        The moment this is most needed is when something is already broken, so
        any single probe failing must not take the whole file with it.
        """
        try:
            return collect()
        except Exception as exc:  # noqa: BLE001  # the reason IS the diagnostic
            return {"error": f"{type(exc).__name__}: {exc}", **fallback}

    status_payload = {
        "app_version": __version__,
        "generated_at": utcnow().isoformat(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "data_dir": str(config.data_dir),
        "models": _safely(_models_status_snapshot, {"models": None}),
        "searxng": _safely(lambda: searxng_manager.status(config.data_dir), {}),
        "logs": logbuffer.stats(),
    }
    counts = _safely(
        lambda: {
            "entries": session.scalar(select(func.count(Entry.id))) or 0,
            "entries_deleted": session.scalar(
                select(func.count(Entry.id)).where(Entry.is_deleted == True)  # noqa: E712
            )
            or 0,
            "entries_private": session.scalar(
                select(func.count(Entry.id)).where(Entry.is_private == True)  # noqa: E712
            )
            or 0,
            "categories": session.scalar(select(func.count(Category.id))) or 0,
            "links": session.scalar(select(func.count(EntryLink.id))) or 0,
        },
        {},
    )

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", BUNDLE_README)
        archive.writestr(
            "logs.json", json.dumps(logbuffer.recent(logbuffer.MAX_RECORDS), indent=2)
        )
        archive.writestr(
            "preferences.json",
            json.dumps(_redacted_preferences(config.all_preferences()), indent=2),
        )
        archive.writestr("status.json", json.dumps(status_payload, indent=2, default=str))
        archive.writestr("counts.json", json.dumps(counts, indent=2))

    manager.log_action(session, "exported", "data", detail="support bundle")
    session.commit()
    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=tessellate-support-bundle.zip"
        },
    )


def _models_status_snapshot() -> dict:
    """The model/AI state, without importing the models router's response."""
    ollama = deps.get_ollama()
    model_manager = deps.get_model_manager()
    embeddings = deps.get_embeddings()
    return {
        "ollama_running": ollama.is_running(),
        "chat_model": model_manager.chat_model(),
        "utility_model": model_manager._config.get_preference("utility_model", ""),
        "embedding_backend": model_manager.embedding_backend(),
        "active_embedding_model": embeddings.active_model(),
        "embedding_ready": embeddings.is_ready(),
        "embedding_error": embeddings.last_error,
    }


def _export_rows(session: Session) -> tuple[list[Category], list[Entry], list[EntryLink]]:
    """Everything the user owns, including binned entries, an export
    should never silently drop data."""
    categories = list(session.scalars(select(Category).order_by(Category.id)))
    entries = list(session.scalars(select(Entry).order_by(Entry.id)))
    links = list(session.scalars(select(EntryLink).order_by(EntryLink.id)))
    return categories, entries, links



@router.get("/export/backup")
def export_backup(background_tasks: BackgroundTasks):
    import os
    config = deps.get_config()
    fd, tmp_path = tempfile.mkstemp(suffix=".zip", prefix="memorymap_backup_")
    os.close(fd)

    def cleanup():
        try:
            os.remove(tmp_path)
        except OSError:
            pass  # already gone, or never got written, nothing left to clean up

    background_tasks.add_task(cleanup)
    #: **A snapshot, not the live file** (audit 2026-10-05, ARCH-18): the
    #: database runs in WAL mode, so zipping the main file alone lost what
    #: was saved last (measured, three notes and none of them in the zip,
    #: with `integrity_check` passing). `backup_bundle.build_zip` copies a
    #: consistent whole through SQLite's backup API, and adds `uploads/` to
    #: `media/`. The same zip is what `POST /backups/bundle` seals with a
    #: password and `POST /backups/bundle/restore` reads back.
    backup_bundle.build_zip(config.data_dir, config.db_path, Path(tmp_path))
    return FileResponse(tmp_path, media_type="application/zip", filename="memorymap_backup.zip", background=background_tasks)

@router.get("/export/json")

def export_json(session: Session = Depends(get_session)) -> Response:
    categories, entries, links = _export_rows(session)
    payload = {
        "app": "Tessellate",
        "version": __version__,
        "exported_at": utcnow().isoformat(),
        "categories": [{"id": c.id, "name": c.name} for c in categories],
        "entries": [],
        "links": [],
    }

    category_names = manager.bulk_category_names(session, entries)

    for e in entries:
        payload["entries"].append({
            "id": e.id,
            # Exports decrypt while the app is unlocked. An export is for
            # taking your notes elsewhere, and ciphertext with no key is
            # not your notes. (The app's own backups keep private notes
            # encrypted, and since SEC-03 carry none of their words in the
            # search index either: `backup.strip_leftovers`.)
            "content": manager.readable_content(e),
            "category": category_names.get(e.category_id, manager.UNCATEGORISED),
            "tags": manager.entry_tags(e),
            "ai_confidence": e.ai_confidence,
            # Said, so a note decrypted for the export is not mistaken for an
            # ordinary one by whatever reads the file next (SEC-14).
            "is_private": bool(e.is_private),
            "created_at": e.created_at.isoformat(),
            "updated_at": e.updated_at.isoformat(),
            # `is_deleted` is not decoration and not derivable from
            # `deleted_at`: an export is what a re-import reads, and without
            # this flag every note in the recycle bin comes back as a live
            # note. It went missing when this block was rewritten as a loop.
            "is_deleted": e.is_deleted,
            "deleted_at": e.deleted_at.isoformat() if e.deleted_at else None,
        })

    payload["links"] = [
        {
            "id": link.id,
            "source_entry_id": link.source_entry_id,
            "target_entry_id": link.target_entry_id,
            # GRAPH_PLAN KG3: a link is its kind, its reason and its
            # properties as much as its two ends.
            "reason": link.reason,
            "link_type": link.link_type,
            "props": link.props,
        }
        for link in links
    ]
    payload["relation_types"] = [
        {k: v for k, v in kind.items() if k != "description"}
        for kind in manager.relation_types(session).values()
    ]
    manager.log_action(session, "exported", "data", detail="json")
    session.commit()
    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=tessellate-export.json"},
    )


def _slug(text: str, length: int = 30) -> str:
    """A filesystem-safe slice of a note's first words."""
    cleaned = re.sub(r"[^\w\s-]", "", text)[:length].strip()
    return re.sub(r"[\s]+", "-", cleaned) or "note"


def build_markdown_export(session: Session, ids: list[int] | None = None) -> bytes:
    """The zip itself, as bytes, with nothing HTTP about it.

    Lifted out of the route below so `python -m tessellate --export PATH`
    writes exactly the same archive the Settings button downloads, rather
    than a second implementation that drifts. uninstall.sh and
    uninstall.bat call that entry point for `--export`, which is the whole
    point: someone removing the app should be able to take their notes out
    first, from a terminal, with no browser and no running server.

    The audit line is written here rather than in the route so a CLI export
    is recorded too: "where did this zip come from" is the same question
    either way.
    """
    _categories, entries, _links = _export_rows(session)
    #: A selection (WORLD_CLASS_PLAN 5 item 6, section 8 row 30): the same
    #: files the whole export writes, for these notes only.
    if ids is not None:
        wanted = set(ids)
        entries = [entry for entry in entries if entry.id in wanted]
    category_names = manager.bulk_category_names(session, entries)
    
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for entry in entries:
            cat_name = category_names.get(entry.category_id, manager.UNCATEGORISED)
            folder = (
                "_recycle-bin"
                if entry.is_deleted
                else _slug(cat_name, 40)
            )
            tags = manager.entry_tags(entry)
            front = [
                "---",
                f"category: {cat_name}",
                f"created: {entry.created_at.isoformat()}",
            ]
            if tags:
                front.append(f"tags: [{', '.join(tags)}]")
            if entry.pinned:
                front.append("pinned: true")
            readable = manager.readable_content(entry)
            #: KG4: the note's own properties join the app's in one block.
            from tessellate.entry import properties as note_properties

            end = note_properties.block_end(readable)
            if end:
                front.extend(line for line in readable[:end].rstrip("\n").split("\n")[1:-1] if line.strip())
                readable = readable[end:].lstrip("\n")
            front.append("---")
            body = "\n".join(front) + f"\n\n{readable}\n"
            archive.writestr(f"{folder}/{entry.id}-{_slug(readable)}.md", body)
    detail = "markdown" if ids is None else f"markdown, {len(entries)} selected"
    manager.log_action(session, "exported", "data", detail=detail)
    session.commit()
    return buffer.getvalue()


@router.get("/export/markdown")
def export_markdown(
    session: Session = Depends(get_session),
    ids: str = Query(default="", max_length=6000, description="Comma-separated note ids; empty for every note"),
) -> Response:
    """A zip of Obsidian-friendly .md files: one file per note, one
    folder per category, YAML frontmatter carrying the metadata. Binned
    notes go under _recycle-bin/, exports never silently drop data. With
    `ids`, only those notes (the Notes selection's Export)."""
    chosen = [int(part) for part in ids.split(",") if part.strip().isdigit()] if ids.strip() else None
    return Response(
        content=build_markdown_export(session, chosen),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=tessellate-markdown.zip"},
    )


MAX_IMPORT_BYTES = 1024 * 1024  # a single markdown note, not a novel
#: `import_markdown` below had a per-file size cap but no cap on how many
#: files one request could carry, each one does its own `create_entry` +
#: `session.commit()`, so a request with an unbounded file count ran
#: unbounded work. Same instinct as `MAX_DOCUMENT_IMPORT_NOTES` just below:
#: a real "import my Obsidian vault" drag-and-drop is at most a few hundred
#: files, so this is generous headroom, not a real-world ceiling.
MAX_IMPORT_FILES = 500


#: The keys the app reads into its own fields (and writes on export); every
#: other key stays in the note's text as a property (GRAPH_PLAN KG4).
_APP_KEYS = {"category", "tags", "created", "updated", "pinned"}


def _exported_created(values: list[str] | None):
    """The `created:` the export wrote, as the naive UTC the database holds,
    or None when it is absent, unreadable, or in the future (a vault from
    elsewhere may use any date format; only a clean past ISO stamp is trusted)."""
    from datetime import datetime, timezone

    if not values:
        return None
    try:
        parsed = datetime.fromisoformat(values[0].strip())
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed if parsed <= datetime.now(timezone.utc).replace(tzinfo=None) else None


def _keep_exported_state(session: Session, entry, meta: dict) -> None:
    """Put back the date and pin an exported note carried."""
    if meta.get("created"):
        entry.created_at = meta["created"]
    if meta.get("pinned"):
        entry.pinned = True
    if meta.get("created") or meta.get("pinned"):
        session.commit()


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """(metadata, content). `category` and `tags` become the note's own
    fields; `created` and `updated` are the export's and are dropped; every
    other key stays at the top of the note as its properties (KG4), lines
    as written, so an imported vault keeps them. Imports must never eat
    someone's text."""
    from tessellate.entry import properties as note_properties

    end = note_properties.block_end(text)
    if not end:
        return {}, text
    found, body = note_properties.split(text)
    meta: dict = {}
    if found.get("category"):
        meta["category"] = found["category"][0]
    if "tags" in found:
        meta["tags"] = [t for t in found["tags"] if t]
    # What this app's own export wrote (audit 2026-10-10, item 1): a note
    # exported and imported again kept its words and lost its date and pin,
    # so the timeline reshuffled to "everything today".
    stamp = _exported_created(found.get("created"))
    if stamp is not None:
        meta["created"] = stamp
    if (found.get("pinned") or [""])[0].lower() == "true":
        meta["pinned"] = True
    kept: list[str] = []
    skipping = False
    for line in text[:end].rstrip("\n").split("\n")[1:-1]:
        head = line.partition(":")[0].strip().lower()
        if line[:1] not in (" ", "\t", "-") and ":" in line:
            skipping = head in _APP_KEYS
        if not skipping:
            kept.append(line)
    body = body.lstrip("\n")
    if any(line.strip() for line in kept):
        return meta, "---\n" + "\n".join(kept) + "\n---\n" + body
    return meta, body



class ImportDirectoryRequest(BaseModel):
    path: str

def _validated_import_directory(path_value: str) -> Path:
    """The one place `import_directory`'s request path is turned into a
    real, checked filesystem path, both the route and the background job
    it schedules use this, and both pass its *return value* on, never the
    original string.

    CodeQL flags the raw `req.path` reaching file I/O as "uncontrolled
    data used in a path expression", correct about the data flow, but
    this route's whole job is letting the already-authenticated owner of
    this single-user, local-only notebook pick any folder on their own
    machine to import from (the Obsidian-vault-import feature). There is
    no narrower base directory to confine it to without breaking that.
    What this *can* do, and didn't before: reject a null byte outright
    (the one thing no legitimate path contains), confirm the path
    genuinely resolves to an existing directory before anything reads
    from it, and, the part a first pass at this missed, make sure the
    resolved, checked `Path` is what actually gets used downstream rather
    than the original unchecked string living on past this function.
    """
    if not path_value or "\x00" in path_value:
        raise ValueError("Invalid directory path")
    # Normalised with `realpath` and confined by a prefix test before the
    # disk is touched at all: the form CodeQL's path-injection query knows
    # as a guard (a `Path.resolve(strict=True)` first is itself a read of
    # an unchecked path, and `is_relative_to` is not recognised).
    # The guard is spelled out here rather than behind a helper: CodeQL only
    # counts a `startswith` that sits in the same function as the read.
    real = os.path.normpath(os.path.realpath(path_value))
    root = _import_root_for(real)
    if not root or not real.startswith(root):
        raise ValueError("Outside the folders an import may read")
    p = Path(real)
    if not p.is_dir():
        raise ValueError("Invalid directory path")
    # **Inside home or the data folder, judged after `resolve`** (WORLD_CLASS
    # _PLAN §12, S3). "There is no narrower base directory" above was written
    # for the owner at their own keyboard; for anyone holding a token over a
    # network, this route was a read of any folder the server can see. Home
    # is where a vault lives; the data folder is where the app itself puts
    # things. Checked on the resolved path, so a symlink in home that points
    # at `/etc` is judged by where it lands, not by where it sits.
    return p


def _import_roots() -> list[str]:
    """The folders a directory import may read from, as real paths."""
    roots = []
    for candidate in (Path.home(), deps.get_config().data_dir):
        try:
            roots.append(os.path.realpath(candidate))
        except OSError:
            continue
    return roots


def _under_root(real: str, root: str) -> bool:
    """Is the real path `real` the folder `root` or somewhere inside it?"""
    return real == root or real.startswith(root.rstrip(os.sep) + os.sep)


def _import_root_for(real: str) -> str:
    """The import root `real` lies in (separator-aware), or "" for none."""
    for root in _import_roots():
        if _under_root(real, root):
            return root
    return ""


def _inside(root: Path, f: Path) -> bool:
    """Does `f`, symlinks followed, still lie inside `root`?

    The walk below reads every `.md` under the chosen folder, and a symlink
    inside it can point anywhere: `innocent.md -> ~/.ssh/config.md`, or a
    linked folder. The folder was checked; what it links to was not, so
    each file is checked by where it resolves.
    """
    real = os.path.realpath(f)
    return _under_root(real, os.path.realpath(root)) and os.path.isfile(real)


def _run_directory_import(directory_path: str):
    """The background task: the import, recorded as the last "import" run
    (INBOX 438), because a 202 Accepted answers nobody about how it went."""
    with jobruns.job_run("import", origin="you") as run:
        _import_directory_files(directory_path, run)


#: Stands for "this path is a private note": matched without its text.
_PRIVATE = object()


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _already_imported(session) -> dict:  # noqa: ANN001
    """Every live note that came from a vault file: its path in the vault ->
    the hashes of its text, or `_PRIVATE` when its text is encrypted."""
    from sqlalchemy import select

    from tessellate.core.database import Entry

    known: dict = {}
    rows = session.execute(
        select(Entry.source_path, Entry.content, Entry.is_private).where(
            Entry.source_path != "", Entry.is_deleted.is_(False)
        )
    )
    for path, content, private in rows:
        if private:
            known[path] = _PRIVATE
        elif known.get(path) is not _PRIVATE:
            known.setdefault(path, set()).add(_text_hash((content or "").strip()))
    return known


def _import_directory_files(directory_path: str, run: "jobruns.Run"):
    try:
        p = _validated_import_directory(directory_path)
    except ValueError:
        run.fail("That folder is not inside your home folder or the data folder.")
        return
    with deps.get_db().session() as session:
        imported = 0
        skipped = 0
        skipped_oversize = 0
        already = 0
        made = []
        known = _already_imported(session)
        for f in p.rglob("*.md"):
            if not _inside(p, f):
                skipped += 1
                continue
            try:
                #: `import_markdown` (the upload path just below) has always
                #: capped a file at `MAX_IMPORT_BYTES` before reading it; this
                #: path read whole files with no ceiling at all, so a
                #: multi-gigabyte `.md` dropped into the vault by mistake was
                #: read into memory in full. `stat()` first and reuse the
                #: same constant, so a directory import can't be a bigger
                #: attack surface than the upload form sitting right next to
                #: it in the settings page.
                if f.stat().st_size > MAX_IMPORT_BYTES:
                    skipped += 1
                    skipped_oversize += 1
                    continue
                text = f.read_text(encoding="utf-8")
                meta, body = _parse_frontmatter(text)
                if not body.strip():
                    skipped += 1
                    continue
                try:
                    relative = f.relative_to(p).as_posix()[:500]
                except ValueError:
                    relative = f.name[:500]
                #: **Running it again is safe** (SEC-10, audit 2026-10-05): a
                #: file whose path in the vault and whose text are already a
                #: note is passed over, so "import again" finishes an import
                #: that was cut off instead of doubling what got in. A note
                #: made private since is matched on its path alone: its text
                #: is encrypted, and a second, readable copy is the one thing
                #: an import must never make of it.
                seen = known.get(relative)
                if seen is not None and (seen is _PRIVATE or _text_hash(body.strip()) in seen):
                    already += 1
                    continue
                #: **The file's own text, unchanged.** An earlier attempt at
                #: this prepended `# <filename>` so the note would carry its
                #: vault name: and three existing tests caught it, rightly:
                #: an importer that edits what it imports is a data-loss bug
                #: waiting to be reported, and this app's own rule is that a
                #: note has no separate title, its opening words *are* its
                #: name. The filename is preserved on `source_path` instead,
                #: where `find_by_wiki_name` reads it, so `[[wiki links]]`
                #: resolve without a single character of the note changing.
                entry = manager.create_entry(
                    session,
                    body.strip(),
                    category_name=meta.get("category") or manager.UNCATEGORISED,
                    tags=meta.get("tags") or [],
                    ai_confidence=100 if meta.get("category") else 0,
                )
                #: Relative to the vault root, never absolute, see
                #: `Entry.source_path`. `as_posix` so a vault imported on
                #: Windows and one imported on Linux group identically.
                entry.source_path = relative
                if meta.get("category"):
                    entry.user_filed = True
                _keep_exported_state(session, entry, meta)
                deps.store_quietly(session, entry)
                imported += 1
                made.append(entry)
                known.setdefault(relative, set()).add(_text_hash(body.strip()))
                if imported % 50 == 0:
                    session.commit()
            except Exception:
                # Counted on the activity line below, and now said: which
                # file, and why. A skip used to be a number with no reason.
                logging.getLogger("tessellate.import").warning(
                    "skipped %s while importing a folder", f.name, exc_info=True
                )
                skipped += 1
                #: A failed flush leaves the session refusing every later
                #: statement until it is rolled back, so one bad file used to
                #: end the import for every file after it (SEC-10). Each note
                #: before it is already committed by `create_entry`.
                session.rollback()
        #: The importer runs as a background task (202 Accepted, no
        #: synchronous response), so a skipped file has nowhere to be
        #: reported except this activity-log line: unlike `import_markdown`,
        #: which can hand its skip list straight back in the response body,
        #: this is the only place the count and the reason reach anyone.
        #: Firing on `skipped` too, not just `imported`, matters here: a
        #: directory whose files were all oversize used to leave no trace
        #: at all, imported stayed 0 and the whole run vanished silently.
        _link_imported(session, made)
        if imported > 0 or skipped > 0 or already > 0:
            detail = f"markdown dir x{imported}"
            if already:
                detail += f", {already} already in"
            if skipped:
                detail += f", skipped {skipped}"
                if skipped_oversize:
                    limit_mb = MAX_IMPORT_BYTES // (1024 * 1024)
                    detail += f" ({skipped_oversize} over {limit_mb} MB)"
            manager.log_action(session, "imported", "data", detail=detail)
            session.commit()
            run.result = (
                f"imported {imported} note{'' if imported == 1 else 's'} from a folder"
                + (f", {already} already in" if already else "")
                + (f", skipped {skipped}" if skipped else "")
            )
            #: A whole vault arriving at once is exactly the "large change"
            #: the rebuild suggestion exists for, see `mark_index_stale`.
            if imported > 0:
                deps.mark_index_stale(imported)
        else:
            run.result = "no markdown files found in that folder"

@router.post("/import/directory", status_code=202, dependencies=[Depends(this_computer_only)])
def import_directory(req: ImportDirectoryRequest):
    try:
        p = _validated_import_directory(req.path)
    except ValueError:
        raise HTTPException(
            400,
            "Choose a folder that exists inside your home folder or the notebook's data folder.",
        ) from None
    # The validated, resolved path, not req.path, is what the background
    # job and the response both carry from here on.
    canonical_path = str(p)
    # On the pool, not a request task: the job is remembered, so a quit
    # part-way is finished at the next launch (Brief 9). One folder waiting
    # twice is one job.
    jobs.enqueue(
        "import", _run_directory_import, canonical_path, name=p.name, dedupe_key=("import", canonical_path)
    )
    return {"status": "started", "path": canonical_path}

@router.post("/import/markdown", status_code=201)

def import_markdown(
    files: list[UploadFile], session: Session = Depends(get_session)
) -> dict:
    """Turn uploaded .md files into notes (Obsidian-friendly: the same
    frontmatter the export writes is understood on the way back in)."""
    if len(files) > MAX_IMPORT_FILES:
        raise HTTPException(
            status_code=422,
            detail=f"{len(files)} files at once is more than one import handles "
            f"({MAX_IMPORT_FILES} max): split it into smaller batches.",
        )
    with jobruns.job_run("import", origin="you") as run:
        result = _import_markdown_files(files, session)
        run.result = f"imported {result['imported']} note{'' if result['imported'] == 1 else 's'}" + (
            f", skipped {len(result['skipped'])}" if result["skipped"] else ""
        )
    return result


def _link_imported(session: Session, entries: list) -> None:
    """Join up the `[[wiki links]]` an import brought in, both ways.

    After every file is a note, so a link to a file later in the same batch
    resolves (`sync_wiki_links` only links names that exist), and
    `resolve_links_to` links notes already here that named one of the new
    ones. Before this, an imported vault had no links at all until each note
    was saved again (tests/test_import_markdown_links.py)."""
    for entry in entries:
        manager.sync_wiki_links(session, entry)
        manager.resolve_links_to(session, entry)
    session.commit()


def _import_markdown_files(files: list[UploadFile], session: Session) -> dict:
    imported = 0
    skipped: list[str] = []
    #: The notes this import made, so the client's Undo can bin exactly
    #: these (INBOX 464 (18): choosing the files starts the import now).
    ids: list[int] = []
    made = []
    #: **Choosing the same files again adds nothing** (the folder importer's
    #: rule, SEC-10, and the README's promise): a file whose name or path and
    #: whose text are already a note is passed over; an edited one comes in.
    known = _already_imported(session)
    already = 0
    for file in files:
        raw = file.file.read(MAX_IMPORT_BYTES + 1)
        name = file.filename or "note.md"
        if len(raw) > MAX_IMPORT_BYTES:
            skipped.append(f"{name}: larger than 1 MB")
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            skipped.append(f"{name}: not a text file")
            continue
        meta, body = _parse_frontmatter(text)
        if not body.strip():
            skipped.append(f"{name}: empty")
            continue
        #: The path, not the text, see the directory importer above for why
        #: nothing here rewrites the file's own content. A browser sends the
        #: relative path as the filename when the picker was a directory
        #: picker, and the bare name otherwise; both are relative, which is
        #: the only kind stored.
        relative = name.lstrip("/")[:500]
        seen = known.get(relative)
        if seen is not None and (seen is _PRIVATE or _text_hash(body.strip()) in seen):
            already += 1
            continue
        entry = manager.create_entry(
            session,
            body.strip(),
            category_name=meta.get("category") or manager.UNCATEGORISED,
            tags=meta.get("tags") or [],
            ai_confidence=100 if meta.get("category") else 0,
        )
        entry.source_path = relative
        if meta.get("category"):
            entry.user_filed = True  # the file said where it belongs
            session.commit()
        _keep_exported_state(session, entry, meta)
        deps.store_quietly(session, entry)
        imported += 1
        ids.append(entry.id)
        made.append(entry)
        known.setdefault(relative, set()).add(_text_hash(body.strip()))
    _link_imported(session, made)
    detail = f"markdown x{imported}" + (f", {already} already in" if already else "")
    manager.log_action(session, "imported", "data", detail=detail)
    session.commit()
    deps.mark_index_stale(imported)
    return {"imported": imported, "skipped": skipped, "ids": ids, "already": already}


#: A PDF or slide deck, not a video, well past what a document-conversion
#: library is for.
MAX_DOCUMENT_IMPORT_BYTES = 20 * 1024 * 1024
#: A very long deck splits into one note per slide; a sane ceiling on how
#: many notes one upload can create, the same instinct as `tools.py`'s
#: MAX_PLAN_STEPS: a huge number here is usually a converter emitting one
#: heading per page rather than someone wanting 200 new notes at once.
MAX_DOCUMENT_IMPORT_NOTES = 25


@router.post("/import/document", status_code=201)
def import_document(file: UploadFile, session: Session = Depends(get_session)) -> dict:
    """Turn an uploaded PDF/Word/slide file into one or more notes, via
    markitdown (§37G): the button `core/extras.py`'s `documents` extra
    installed for and had nothing behind, until this.

    One note per top-level heading when the converted markdown has more than
    one (a deck, a document with real chapters); the whole file as one note
    otherwise: `import_markdown`'s "each file becomes a note" for the common
    case, once markitdown has turned it into something with that shape.
    """
    if not importer.markitdown_available():
        raise HTTPException(status_code=503, detail=importer.INSTALL_HINT)

    data = file.file.read(MAX_DOCUMENT_IMPORT_BYTES + 1)
    if len(data) > MAX_DOCUMENT_IMPORT_BYTES:
        raise HTTPException(status_code=413, detail="That file is larger than 20 MB.")
    if not data:
        raise HTTPException(status_code=400, detail="That file is empty.")

    suffix = Path(file.filename or "document").suffix[:12] or ".txt"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as saved:
        saved.write(data)
        saved.flush()
        try:
            text = importer.convert_to_markdown(Path(saved.name))
        except Exception as exc:  # a file markitdown can't parse must not 500
            #: Background jobs shows this row to a person, so it is a plain
            #: sentence with the file's name; the converter's own words (a
            #: path, a library's message) stay in the log with the traceback
            #: (final scan, item 5).
            jobruns.note_finished(
                "import",
                "failed",
                f"Couldn't read {logbuffer.safe_value(file.filename or 'that file', 80)}. "
                "It may be damaged or in a format that can't be converted.",
            )
            logging.getLogger("tessellate.import").warning(
                "couldn't convert %s", logbuffer.safe_value(file.filename, 80), exc_info=True
            )
            raise HTTPException(
                status_code=422,
                detail="Couldn't read that file. It may be damaged or in a format that can't be converted.",
            ) from exc

    all_sections = importer.split_into_sections(text)
    if not all_sections:
        jobruns.note_finished(
            "import", "failed", f"{file.filename or 'That file'} had no readable text in it"
        )
        raise HTTPException(
            status_code=422, detail="That file had no readable text in it."
        )
    sections = all_sections[:MAX_DOCUMENT_IMPORT_NOTES]

    with jobruns.job_run("import", origin="you") as run:
        ids = _create_document_notes(session, sections, Path(file.filename or "document").name)
        imported = len(ids)
        run.result = f"imported {imported} note{'' if imported == 1 else 's'} from {file.filename or 'a document'}"
    manager.log_action(
        session, "imported", "data", detail=f"document x{imported} ({file.filename})"
    )
    session.commit()
    return {
        "imported": imported,
        "truncated": len(all_sections) > len(sections),
        "filename": file.filename,
        "ids": ids,
    }


def _create_document_notes(session: Session, sections: list[str], source_name: str = "") -> list[int]:
    """The ids of the notes made, one per section (the client's Undo bins
    exactly these). Each keeps the file's name as its `source_path`, as the
    other importers do, which is also what marks it as text from outside for
    the agent's injection guard (SEC-02)."""
    ids: list[int] = []
    for section in sections:
        entry = manager.create_entry(
            session,
            section,
            category_name="Imports",
            tags=["imported"],
            ai_confidence=100,
        )
        entry.user_filed = True  # this file said where it came from, not the janitor
        entry.source_path = (source_name or "document")[:500]
        session.commit()
        deps.store_quietly(session, entry)
        ids.append(entry.id)
    return ids



# web search (routes_websearch.py) and backups (routes_backups.py) moved out

@router.get("/export/csv")
def export_csv(session: Session = Depends(get_session)) -> Response:
    _categories, entries, _links = _export_rows(session)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["id", "content", "category", "tags", "ai_confidence", "created_at", "is_deleted"]
    )
    
    category_names = manager.bulk_category_names(session, entries)
    
    for e in entries:
        writer.writerow(
            [
                e.id,
                manager.readable_content(e),
                category_names.get(e.category_id, manager.UNCATEGORISED),
                "|".join(manager.entry_tags(e)),
                e.ai_confidence,
                e.created_at.isoformat(),
                e.is_deleted,
            ]
        )
    manager.log_action(session, "exported", "data", detail="csv")
    session.commit()
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tessellate-export.csv"},
    )
