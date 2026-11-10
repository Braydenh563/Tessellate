"""A model per feature, layered over the roles that already exist.

Asked for directly: *"allow the user to alter the model they use for that
specific feature if they wish such as for the write with ai area, the chat tab
and document ai assistant. allow these to be easily individually altered and
reset and for there to be a mass reset for all individually altered ai model
preferences."*

The point of the feature is that two surfaces really do run on two different
models, so the assertions below are about **the model that reached the
provider**, not about a setting that round-tripped through the API. A
preference that saves and never reaches `chat()` is the "feature that never ran
once" of CLAUDE.md section 6, and it would pass a round-trip test perfectly.

The other rule with a test of its own is that an unset feature stores nothing
(decision 5): if it stored the resolved name, changing the chat model in
Settings would leave every unset feature behind on the old one, silently, and
nobody would connect the two events.
"""

from __future__ import annotations

import pytest

from tessellate.ai import model_manager as mm
from tessellate.core import deps
from tests._app_js import app_js_text


def _manager(app_state):
    return mm.ModelManager(app_state)


def _save(client, content: str) -> dict:
    """A note, so a chat turn has something to answer from: the librarian
    short-circuits an empty notebook without ever calling the model, and the
    assertions below are all about the model that was called."""
    response = client.post("/entries", json={"content": content})
    assert response.status_code == 201
    return response.json()


def _doc(client, title: str, content: str) -> dict:
    response = client.post("/documents", json={"title": title, "content": content})
    assert response.status_code == 201
    return response.json()


# --- the table ----------------------------------------------------------------


def test_every_feature_falls_back_to_a_role_that_exists():
    """One table, and a new feature is one row in it (decision 1)."""
    assert mm.FEATURES, "the feature table is empty"
    for feature in mm.FEATURES:
        assert feature.role in {"chat", "utility"}, feature.key
        assert feature.label, feature.key
        assert feature.key == feature.key.lower()


def test_the_first_pass_covers_the_three_surfaces_that_were_asked_for():
    keys = {feature.key for feature in mm.FEATURES}
    assert {"chat", "writing", "documents"} <= keys


# --- resolving ----------------------------------------------------------------


def test_an_unset_feature_resolves_to_its_role(app_state):
    manager = _manager(app_state)
    manager.set_chat_model("llama3.2")
    manager.set_utility_model("phi3.5")

    for feature in mm.FEATURES:
        expected = "llama3.2" if feature.role == "chat" else "phi3.5"
        assert manager.feature_model(feature.key) == expected, feature.key
        assert manager.feature_override(feature.key) == ""


def test_an_unset_feature_follows_the_global_model_rather_than_copying_it(app_state):
    """Decision 5: absence is stored, the name is resolved at read time."""
    manager = _manager(app_state)
    manager.set_chat_model("llama3.2")
    assert manager.feature_model("writing") == "llama3.2"

    manager.set_chat_model("qwen3.5:4b")
    assert manager.feature_model("writing") == "qwen3.5:4b"
    assert manager.feature_override("writing") == ""


def test_setting_one_feature_leaves_the_others_inherited(app_state):
    manager = _manager(app_state)
    manager.set_chat_model("llama3.2")
    manager.set_feature_model("writing", "gemma4:12b")

    assert manager.feature_model("writing") == "gemma4:12b"
    assert manager.feature_override("writing") == "gemma4:12b"
    for other in ("chat", "documents"):
        assert manager.feature_model(other) == "llama3.2", other
        assert manager.feature_override(other) == ""
    # And the role's own preference is untouched: an override is a second
    # layer, never a write-through to the setting it falls back to.
    assert manager.chat_model() == "llama3.2"


def test_clearing_one_feature_returns_it_to_inherited(app_state):
    manager = _manager(app_state)
    manager.set_chat_model("llama3.2")
    manager.set_feature_model("documents", "mistral-nemo")
    assert manager.feature_model("documents") == "mistral-nemo"

    manager.clear_feature_model("documents")
    assert manager.feature_override("documents") == ""
    assert manager.feature_model("documents") == "llama3.2"


def test_an_empty_name_clears_rather_than_storing_an_empty_override(app_state):
    manager = _manager(app_state)
    manager.set_feature_model("chat", "gemma4:12b")
    manager.set_feature_model("chat", "   ")
    assert manager.feature_override("chat") == ""


def test_a_utility_role_feature_overrides_only_the_utility_side(app_state):
    """The guide runs on the utility model, so its override lands there and
    the chat model it does not use stays exactly where it was."""
    guide = next((f for f in mm.FEATURES if f.key == "guide"), None)
    if guide is None:
        pytest.skip("the guide is not a feature row on this build")
    manager = _manager(app_state)
    manager.set_chat_model("llama3.2")
    manager.set_utility_model("phi3.5")
    manager.set_feature_model("guide", "qwen3.5:2b")

    view = manager.for_feature("guide")
    assert view.utility_model() == "qwen3.5:2b"
    assert view.chat_model() == "llama3.2"
    assert manager.utility_model() == "phi3.5"


def test_an_explicit_override_survives_smart_routing_being_off(app_state):
    """Routing off means "background jobs use the chat model". A feature the
    user pointed at a model by hand is not a background job guess."""
    guide = next((f for f in mm.FEATURES if f.key == "guide"), None)
    if guide is None:
        pytest.skip("the guide is not a feature row on this build")
    app_state.set_preference("smart_model_routing_enabled", False)
    manager = _manager(app_state)
    manager.set_chat_model("llama3.2")
    manager.set_feature_model("guide", "qwen3.5:2b")
    assert manager.for_feature("guide").utility_model() == "qwen3.5:2b"


# --- refusing what is not a feature -------------------------------------------


def test_an_unknown_feature_key_is_refused_rather_than_stored(app_state):
    manager = _manager(app_state)
    with pytest.raises(ValueError):
        manager.set_feature_model("nonesuch", "llama3.2")
    with pytest.raises(ValueError):
        manager.feature_model("nonesuch")
    with pytest.raises(ValueError):
        manager.for_feature("nonesuch")
    # Nothing was written on the way to the refusal.
    assert app_state.get_preference("feature_model_nonesuch", "") == ""


# --- the mass reset -----------------------------------------------------------


def test_the_mass_reset_clears_every_override_and_says_how_many(app_state):
    manager = _manager(app_state)
    manager.set_chat_model("llama3.2")
    manager.set_feature_model("chat", "gemma4:12b")
    manager.set_feature_model("writing", "mistral-nemo")

    assert manager.reset_feature_models() == 2
    for feature in mm.FEATURES:
        assert manager.feature_override(feature.key) == "", feature.key
    assert manager.feature_model("chat") == "llama3.2"


def test_the_mass_reset_is_a_no_op_when_nothing_is_overridden(app_state):
    manager = _manager(app_state)
    assert manager.reset_feature_models() == 0
    assert manager.reset_feature_models() == 0


def test_the_rows_say_which_model_and_whether_it_is_inherited(app_state):
    manager = _manager(app_state)
    manager.set_chat_model("llama3.2")
    manager.set_feature_model("writing", "gemma4:12b")
    rows = {row["key"]: row for row in manager.feature_rows()}

    assert rows["writing"]["model"] == "gemma4:12b"
    assert rows["writing"]["overridden"] is True
    assert rows["chat"]["model"] == "llama3.2"
    assert rows["chat"]["overridden"] is False
    # An inherited row names what it inherits, so Settings can say so without
    # a second lookup per row.
    assert rows["chat"]["inherits"] == "llama3.2"
    assert rows["chat"]["label"]


# --- the API ------------------------------------------------------------------


def test_status_reports_one_row_per_feature(client):
    body = client.get("/models/status").json()
    rows = body["feature_models"]
    assert {row["key"] for row in rows} == {f.key for f in mm.FEATURES}
    assert all(row["overridden"] is False for row in rows)
    assert body["feature_models_overridden"] == 0


def test_setting_a_feature_model_offline_still_saves(client):
    """Ollama is down in this fixture. Clearing must always work, and so must
    setting: the same trust `/models/utility-model` already extends."""
    assert client.post("/models/feature-model", json={"feature": "chat", "name": ""}).status_code == 200


def test_the_api_refuses_an_unknown_feature(client):
    response = client.post(
        "/models/feature-model", json={"feature": "nonesuch", "name": "llama3.2"}
    )
    assert response.status_code == 400


def test_the_api_reset_clears_everything_and_reports_the_count(ai_client):
    manager = deps.get_model_manager()
    manager.set_feature_model("chat", "llama3.2:latest")
    manager.set_feature_model("writing", "llama3.2:latest")

    body = ai_client.post("/models/feature-models/reset").json()
    assert body["cleared"] == 2
    assert all(not row["overridden"] for row in body["feature_models"])
    assert ai_client.post("/models/feature-models/reset").json()["cleared"] == 0


# --- the model that actually reached the provider -----------------------------
#
# The four tests this feature exists for. Each one sets one feature's model and
# asserts on `fake_ollama.chat_models`, which is what the fake records when the
# route really called it.


def test_the_chat_tab_runs_on_its_own_model(ai_client, fake_ollama):
    deps.get_model_manager().set_feature_model("chat", "gemma4:12b")
    _save(ai_client, "a scarecrow joke I want to remember")
    ai_client.post("/chat", json={"question": "what jokes have I saved?"})
    assert fake_ollama.chat_models[-1] == "gemma4:12b"


def test_the_writing_desk_runs_on_its_own_model(ai_client, fake_ollama):
    deps.get_model_manager().set_feature_model("writing", "mistral-nemo")
    ai_client.post("/drafts/compose", json={"thoughts": "bread proving takes ages"})
    assert fake_ollama.chat_models[-1] == "mistral-nemo"


def test_the_document_assistant_runs_on_its_own_model(ai_client, fake_ollama):
    deps.get_model_manager().set_feature_model("documents", "qwen3.5:9b")
    document = _doc(ai_client, "Essay", "A long paragraph that needs tightening.")
    ai_client.post(
        f"/documents/{document['id']}/ai-edit", json={"instruction": "tighten this"}
    )
    assert fake_ollama.chat_models[-1] == "qwen3.5:9b"


def test_the_guide_runs_on_its_own_model(ai_client, fake_ollama):
    guide = next((f for f in mm.FEATURES if f.key == "guide"), None)
    if guide is None:
        pytest.skip("the guide is not a feature row on this build")
    deps.get_model_manager().set_feature_model("guide", "qwen3.5:2b")
    ai_client.post("/help/ask", json={"question": "how do I export a note?"})
    assert fake_ollama.chat_models[-1] == "qwen3.5:2b"


def test_two_features_on_two_models_in_one_session(ai_client, fake_ollama):
    """The whole ask in one test: the chat tab and the writing desk really do
    run on different models, one after the other."""
    manager = deps.get_model_manager()
    manager.set_chat_model("llama3.2")
    manager.set_feature_model("chat", "gemma4:12b")
    manager.set_feature_model("writing", "mistral-nemo")

    _save(ai_client, "a scarecrow joke I want to remember")
    ai_client.post("/chat", json={"question": "what jokes have I saved?"})
    chat_model = fake_ollama.chat_models[-1]
    ai_client.post("/drafts/compose", json={"thoughts": "a few loose thoughts"})
    draft_model = fake_ollama.chat_models[-1]

    assert (chat_model, draft_model) == ("gemma4:12b", "mistral-nemo")


def test_a_feature_left_alone_still_follows_the_chat_model_at_the_provider(
    ai_client, fake_ollama
):
    manager = deps.get_model_manager()
    manager.set_chat_model("qwen3.5:4b")
    ai_client.post("/drafts/compose", json={"thoughts": "loose thoughts"})
    assert fake_ollama.chat_models[-1] == "qwen3.5:4b"


# --- INBOX 288: which model a guide turn really runs on ------------------------
#
# The owner: *"also it doesnt use my utility model as my utility model isnt a
# thinking model."* Measured here rather than reasoned about, because the
# report was inferred from a symptom (a thinking box) rather than observed at
# the provider, and the same claim had been recorded as fixed once before.
#
# What the three tests below measure: with smart routing on, both guide routes
# really do reach the utility model. With it off, the guide reaches the *chat*
# model, which is the one configuration that produces exactly the reported
# symptom on a thinking chat model. That switch says "for background tasks",
# and the Guide is a panel the user is sitting in front of, so the model it
# lands on is no longer a guess either way: the Guide is a feature row, and an
# explicit choice beats both defaults.


def _guide_model(client, fake_ollama, streamed: bool = False) -> str:
    fake_ollama.chat_models.clear()
    body = {"question": "how do I export a note?"}
    if streamed:
        with client.stream("POST", "/help/ask/stream", json=body) as response:
            list(response.iter_lines())
    else:
        client.post("/help/ask", json=body)
    assert fake_ollama.chat_models, "the guide turn never reached the provider"
    return fake_ollama.chat_models[-1]


def test_the_guide_reaches_the_utility_model(ai_client, fake_ollama):
    manager = deps.get_model_manager()
    manager.set_chat_model("qwen3.5:9b")
    manager.set_utility_model("llama3.2")
    assert _guide_model(ai_client, fake_ollama) == "llama3.2"
    assert _guide_model(ai_client, fake_ollama, streamed=True) == "llama3.2"


def test_with_smart_routing_off_the_guide_keeps_the_utility_model(ai_client, fake_ollama):
    """INBOX 288's cause, decided by the owner 2026-09-24 (WORLD_CLASS_PLAN
    section 20): the routing switch moves background jobs, and the Guide is
    an interactive panel, so it stays on the utility model either way."""
    manager = deps.get_model_manager()
    manager.set_chat_model("qwen3.5:9b")
    manager.set_utility_model("llama3.2")
    deps.get_config().set_preference("smart_model_routing_enabled", False)
    assert _guide_model(ai_client, fake_ollama) == "llama3.2"
    assert _guide_model(ai_client, fake_ollama, streamed=True) == "llama3.2"


def test_the_guide_row_pins_the_model_whatever_routing_says(ai_client, fake_ollama):
    """The way out of both defaults: an explicit model for this one panel."""
    manager = deps.get_model_manager()
    manager.set_chat_model("qwen3.5:9b")
    manager.set_feature_model("guide", "llama3.2")
    deps.get_config().set_preference("smart_model_routing_enabled", False)
    assert _guide_model(ai_client, fake_ollama) == "llama3.2"
    assert _guide_model(ai_client, fake_ollama, streamed=True) == "llama3.2"


# --- INBOX 430: "Same as chat model" / "Same as utility model" ---------------
#
# A third state alongside "on its own model" and "inherited": a feature can be
# pinned to whichever role it does NOT already fall back to, and unlike a
# plain model name it has to keep tracking that setting when it changes,
# never freeze at the name that setting held the moment it was picked
# (decision 5's reasoning applied to the other role too).


def test_a_chat_role_feature_can_follow_the_utility_model(app_state):
    """Writing's role is chat, so this is the "other" role for it: pinned to
    utility on purpose (a small fast model for a feature that is usually the
    big chat model)."""
    manager = _manager(app_state)
    manager.set_chat_model("llama3.2")
    manager.set_utility_model("phi3.5")
    manager.set_feature_model("writing", mm.FOLLOW_UTILITY_MODEL)

    assert manager.feature_model("writing") == "phi3.5"
    assert manager.feature_override("writing") == mm.FOLLOW_UTILITY_MODEL
    # The role it actually falls back to (chat) is untouched.
    assert manager.chat_model() == "llama3.2"


def test_a_utility_role_feature_can_follow_the_chat_model(app_state):
    guide = next((f for f in mm.FEATURES if f.key == "guide"), None)
    if guide is None:
        pytest.skip("the guide is not a feature row on this build")
    manager = _manager(app_state)
    manager.set_chat_model("llama3.2")
    manager.set_utility_model("phi3.5")
    manager.set_feature_model("guide", mm.FOLLOW_CHAT_MODEL)

    view = manager.for_feature("guide")
    assert view.utility_model() == "llama3.2"
    # The role guide does not use stays exactly where it was.
    assert manager.utility_model() == "phi3.5"


def test_following_a_role_tracks_it_live_rather_than_freezing_the_name(app_state):
    """The whole point of the sentinel over just copying the name in: change
    the setting afterwards and the feature moves with it, the same guarantee
    plain "inherited" already gives (decision 5), extended to the other
    role."""
    manager = _manager(app_state)
    manager.set_chat_model("llama3.2")
    manager.set_utility_model("phi3.5")
    manager.set_feature_model("writing", mm.FOLLOW_UTILITY_MODEL)
    assert manager.feature_model("writing") == "phi3.5"

    manager.set_utility_model("qwen3.5:2b")
    assert manager.feature_model("writing") == "qwen3.5:2b"
    assert manager.feature_override("writing") == mm.FOLLOW_UTILITY_MODEL


def test_following_survives_smart_routing_being_off(app_state):
    """`utility_model()` falls to the chat model when routing is off and
    nothing chose a model by hand; a feature that explicitly asked to follow
    utility is exactly that hand-made choice, not a background-job guess, so
    it keeps tracking utility_model()'s own answer (which itself falls to
    chat with routing off) rather than being treated as unset."""
    manager = _manager(app_state)
    manager.set_chat_model("llama3.2")
    manager.set_feature_model("writing", mm.FOLLOW_UTILITY_MODEL)
    app_state.set_preference("smart_model_routing_enabled", False)
    assert manager.feature_model("writing") == "llama3.2"

    manager.set_utility_model("phi3.5")
    app_state.set_preference("smart_model_routing_enabled", True)
    assert manager.feature_model("writing") == "phi3.5"


def test_the_rows_carry_the_follow_kind_not_the_raw_sentinel(app_state):
    """`model` is always a real name a select can show; the sentinel itself
    is only in `override_kind`, so a caller that ignores that field cannot
    print `__follow_utility_model__` into the UI by accident."""
    manager = _manager(app_state)
    manager.set_chat_model("llama3.2")
    manager.set_utility_model("phi3.5")
    manager.set_feature_model("writing", mm.FOLLOW_UTILITY_MODEL)
    manager.set_feature_model("documents", "gemma4:12b")
    rows = {row["key"]: row for row in manager.feature_rows()}

    assert rows["writing"]["override_kind"] == "utility"
    assert rows["writing"]["override_value"] is None
    assert rows["writing"]["model"] == "phi3.5"
    assert rows["writing"]["overridden"] is True

    assert rows["documents"]["override_kind"] == "model"
    assert rows["documents"]["override_value"] == "gemma4:12b"

    assert rows["chat"]["override_kind"] == ""
    assert rows["chat"]["override_value"] is None
    assert rows["chat"]["overridden"] is False


def test_a_sentinel_is_never_confused_with_an_installed_model_name(app_state):
    """A real Ollama tag can never collide with either sentinel (both are
    double-underscored), so a feature can always tell "follow a role" apart
    from "someone genuinely installed a model with this exact name"."""
    assert mm.FOLLOW_CHAT_MODEL not in {"llama3.2", "phi3.5", "gemma4:12b"}
    assert mm.FOLLOW_UTILITY_MODEL not in {"llama3.2", "phi3.5", "gemma4:12b"}
    assert mm.FOLLOW_CHAT_MODEL != mm.FOLLOW_UTILITY_MODEL


def test_the_api_accepts_the_sentinel_even_though_it_is_not_an_installed_model(
    ai_client, fake_ollama
):
    """The install check that refuses a typo'd model name (`/utility-model`'s
    own rule, reused here) must not also refuse the one value that means "I
    am deliberately not naming an installed model"."""
    response = ai_client.post(
        "/models/feature-model",
        json={"feature": "writing", "name": mm.FOLLOW_UTILITY_MODEL},
    )
    assert response.status_code == 200
    row = next(r for r in response.json()["feature_models"] if r["key"] == "writing")
    assert row["override_kind"] == "utility"


def test_status_exposes_the_two_sentinels_for_the_frontend(client):
    """The frontend sends these values back verbatim; exposed here so it
    never has to hardcode a string that only means something because it
    matches this module's own constant."""
    body = client.get("/models/status").json()
    assert body["feature_model_follow"] == {
        "chat": mm.FOLLOW_CHAT_MODEL,
        "utility": mm.FOLLOW_UTILITY_MODEL,
    }


def test_a_feature_following_utility_reaches_the_new_model_at_the_provider(
    ai_client, fake_ollama
):
    """The four-tests-this-feature-exists-for pattern above, extended to the
    "follow" state: the writing desk really does move to the model the
    utility setting names, including after it changes."""
    manager = deps.get_model_manager()
    manager.set_chat_model("llama3.2")
    manager.set_utility_model("phi3.5")
    manager.set_feature_model("writing", mm.FOLLOW_UTILITY_MODEL)

    ai_client.post("/drafts/compose", json={"thoughts": "a few loose thoughts"})
    assert fake_ollama.chat_models[-1] == "phi3.5"

    manager.set_utility_model("qwen3.5:2b")
    ai_client.post("/drafts/compose", json={"thoughts": "a second draft"})
    assert fake_ollama.chat_models[-1] == "qwen3.5:2b"


# --- the Ask box, a feature of its own (2026-09-23) ----------------------------
#
# The owner: "I want to be able to change the model I use within the features
# themselves using a model dropdown which pairs with the feature-specific model
# selections in settings." The Notes tab's Ask box and the Chat tab share
# `/chat/stream`, so the Ask box ran on the "Chat tab" row without saying so:
# a picker on the Ask box that wrote the chat row would have moved the Chat tab
# too. It is its own row, told apart by the `notes_only` flag the Ask box
# already sends and the Chat tab never does.


def _stream(client, **body) -> None:
    with client.stream("POST", "/chat/stream", json=body) as response:
        list(response.iter_lines())


def test_the_ask_box_is_a_feature_row(client):
    rows = {row["key"]: row for row in client.get("/models/status").json()["feature_models"]}
    assert rows["ask"]["label"] == "Ask tab"
    assert rows["ask"]["role"] == "chat"


def test_the_ask_box_runs_on_its_own_model_and_the_chat_tab_on_its(ai_client, fake_ollama):
    manager = deps.get_model_manager()
    manager.set_chat_model("llama3.2")
    manager.set_feature_model("ask", "qwen3.5:4b")
    manager.set_feature_model("chat", "gemma4:12b")
    _save(ai_client, "a scarecrow joke I want to remember")

    _stream(ai_client, question="what jokes have I saved?", notes_only=True, use_tools=False)
    assert fake_ollama.chat_models[-1] == "qwen3.5:4b"
    _stream(ai_client, question="what jokes have I saved?", use_tools=False)
    assert fake_ollama.chat_models[-1] == "gemma4:12b"


def test_an_unset_ask_box_follows_the_chat_model_not_the_chat_tab(ai_client, fake_ollama):
    """Inherits through its role, like every row: a Chat tab override is that
    tab's choice and does not leak into the Ask box."""
    manager = deps.get_model_manager()
    manager.set_chat_model("llama3.2")
    manager.set_feature_model("chat", "gemma4:12b")
    _save(ai_client, "a scarecrow joke I want to remember")
    _stream(ai_client, question="what jokes have I saved?", notes_only=True, use_tools=False)
    assert fake_ollama.chat_models[-1] == "llama3.2"


def test_every_in_surface_picker_names_a_real_feature_and_a_real_control():
    """`FEATURE_MODEL_SELECTS` (app.js) pairs a `<select>` with a row of the
    table above. A key that is not a row would post a feature the API refuses,
    and an id that is not in the page would be a picker that never drew: both
    silent in the browser, so both pinned here."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    app = app_js_text()
    page = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    block = re.search(r"const FEATURE_MODEL_SELECTS = \[(.*?)\];", app, re.S)
    assert block, "FEATURE_MODEL_SELECTS is gone from app.js"
    pairs = re.findall(r'\["([\w-]+)",\s*"(\w+)"\]', block.group(1))
    assert {key for _, key in pairs} >= {"chat", "ask", "writing"}
    for element_id, key in pairs:
        assert key in mm.FEATURES_BY_KEY, key
        assert f'id="{element_id}"' in page, element_id


def test_the_chat_sheet_leaves_out_same_as_chat_model():
    """On the Chat tab's own sheet "Same as chat model" is the Default row said
    twice (wc2-1110); the other features keep it, and "Same as utility model"
    stays for all."""
    text = app_js_text()
    start = text.index("function openFeatureModelSheet(key)")
    body = text[start : start + 4000]
    guard = body.index('if (key !== "chat")')
    chat_row = body.index('"Same as chat model",')
    utility_row = body.index('"Same as utility model",')
    assert guard < chat_row < utility_row
