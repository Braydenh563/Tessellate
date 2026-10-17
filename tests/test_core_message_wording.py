"""The messages that `core/`, `ai/`, `entry/` and `search/` write for a person.

`tests/test_server_detail_wording.py` holds every literal `detail=` string in
`src/tessellate/api/`. It cannot see a route that passes a *computed* message
(`detail=str(exc)`, `detail=reason`, `detail=info["error"]`): those sentences
are written elsewhere, and `frontend/js/status.js` `plainHttpError` shows them
in a toast as they arrive (INBOX 472, "found, not fixed"). This reads the
source of each of them with `ast`, applies the same wording rules, and adds
two of its own for the new surface:

- a message never carries a raw exception (`f"... {exc}"`): the exception's
  text is developer detail, so it goes to the log and the person reads a
  fixed sentence;
- an install hint names what to install in plain words, never a `pip` line.

Three more tests pin the routes: every computed `detail=` in the API is on a
reviewed list (a new `detail=str(exc)` has to say which checked source its
text comes from), and no f-string `detail=` carries a raw exception.

A message that has to break a rule is allowlisted with the reason beside it,
never by widening a rule.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from tests.test_server_detail_wording import API, _pieces, collect, label, problems, route_sources

SRC = Path(__file__).resolve().parents[1] / "src" / "tessellate"


@dataclass(frozen=True)
class Source:
    """Where one module writes sentences a person reads.

    `functions` limits `raises` to the bodies of the named functions (a module
    that raises for the model in one place and for the person in another);
    `returns` names functions whose returned text is shown; `consts` are
    module-level names holding a sentence; `assigns` are local names whose
    literal value is shown (`reason = "..."`); `calls` are helper calls that
    take the sentence as an argument (`_bad("...")`); `keywords` are keyword
    arguments that carry one (`ViewedFile(message=...)`).
    """

    path: str
    raises: tuple[str, ...] = ()
    functions: tuple[str, ...] = ()
    returns: tuple[str, ...] = ()
    consts: tuple[str, ...] = ()
    assigns: tuple[str, ...] = ()
    calls: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    why: str = field(default="", compare=False)


SOURCES: tuple[Source, ...] = (
    Source("core/backup.py", raises=("FileNotFoundError", "ValueError"), functions=("restore_backup",)),
    Source("core/syntaxcheck.py", raises=("ValueError",), functions=("check",)),
    Source("ai/insights.py", raises=("ValueError",), functions=("confirm", "dismiss")),
    Source("core/webclip.py", raises=("ClipRefused",)),
    Source(
        "core/security.py",
        raises=("UnsafeUrl",),
        returns=("check_backend_url", "_refuses"),
        consts=("_LOCKED_REASON",),
    ),
    Source(
        "core/ocr.py",
        raises=("ValueError",),
        functions=("set_language",),
        returns=("unavailable_reason",),
    ),
    Source("core/ocr.py", assigns=("reason", "note"), functions=("engine_status",)),
    Source("core/docview.py", returns=("editability",), keywords=("message",)),
    Source("ai/voice.py", raises=("RuntimeError",), consts=("INSTALL_HINT",), returns=("remove_model",)),
    Source("ai/captions.py", raises=("CaptionsError",), consts=("NO_HELPER_HINT", "NOT_LOCAL_HINT")),
    Source("entry/importer.py", raises=("RuntimeError",), consts=("INSTALL_HINT",)),
    Source(
        "entry/manager.py",
        raises=("ValueError", "FileExistsError"),
        functions=(
            "validate_attachment_filename",
            "rename_attachment",
            "rename_tags",
            "rename_category",
            "delete_category",
        ),
    ),
    Source("entry/tidy.py", raises=("ValueError", "LookupError"), functions=("set_auto", "undo")),
    Source("ai/tools/categories.py", raises=("ToolError",)),
    Source(
        "ai/tools/__init__.py",
        raises=("ToolError",),
        functions=("validate_make_plan", "summarise_turns"),
    ),
    Source("ai/facts.py", raises=("ValueError",), functions=("set_switches",)),
    Source("ai/learning.py", raises=("ValueError",), functions=("record",)),
    Source("ai/model_manager.py", raises=("ValueError",), functions=("known_feature",)),
    Source("ai/extractor.py", raises=("ValueError",), functions=("build_extraction",)),
    Source("ai/skills.py", raises=("SkillError",)),
    Source("ai/model_cards.py", returns=("inspect_model_name",), calls=("_bad",)),
    Source("ai/librarian.py", consts=("AI_FAILED_MESSAGE", "OFFLINE_MESSAGE")),
    Source("search/websearch.py", raises=("WebSearchError",)),
    Source("search/searxng_manager.py", raises=("SearxngError",), calls=("_reason",)),
    Source("search/searxng_install.py", raises=("SearxngError",), calls=("_reason",)),
    Source("search/searxng_process.py", raises=("SearxngError",)),
    Source("search/searxng_docker.py", raises=("SearxngError",), calls=("_reason",)),
)

#: (file, text with `{}` for each placeholder) -> why it may break a rule.
ALLOWLIST: dict[tuple[str, str], str] = {
    ("ai/tools/categories.py", "{}"): (
        "re-wraps a ValueError from entry/manager.py rename_category and "
        "delete_category, whose messages are checked above"
    ),
    ("core/webclip.py", "{}"): "UnsafeUrl is a sentence written for a person (core/security.py, checked above)",
    ("search/websearch.py", "{}"): "UnsafeUrl is a sentence written for a person (core/security.py, checked above)",
    ("search/searxng_process.py", "{}"): (
        "re-raises `_install_state['error']`, which was itself the text of a "
        "SearxngError checked in this list"
    ),
    (
        "search/searxng_process.py",
        "Every port Tessellate tried for SearXNG was already in use ({}). Free "
        "one of them, or choose another port with the TESSELLATE_SEARXNG_PORT "
        "setting, and press Start again.",
    ): (
        "the setting's name is the way out a person with every port taken "
        "needs (test_searxng_recovery: 'names them all and the way out'); "
        "there is no Settings control for it to point at instead"
    ),
}

#: Words that are fine in an API error and not in a sentence a person reads.
CORE_JARGON = re.compile(
    r"\b(pip|virtualenv|traceback|stderr|stdout|errno|setup\.py|pyproject\.toml)\b",
    re.IGNORECASE,
)
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")
#: A placeholder that is an exception, or the text of one.
#: `exc.strerror` is the operating system's own one-line reason ("No space left
#: on device"), kept on purpose where the person can act on it (the backup 507).
RAW_HOLE = re.compile(r"^(?:str\()?(?:exc|err|error|e|ex|exception)\)?(?:\.rstrip\([^)]*\))?$")


def _name(call: ast.Call) -> str:
    func = call.func
    return func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")


def _bodies(tree: ast.AST, functions: tuple[str, ...]) -> list[ast.AST]:
    if not functions:
        return [tree]
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in functions]


def _holes(node: ast.AST) -> list[str]:
    """Source of each `{...}` placeholder in an f-string (also through `+` and `if`)."""
    if isinstance(node, ast.JoinedStr):
        return [ast.unparse(p.value) for p in node.values if isinstance(p, ast.FormattedValue)]
    if isinstance(node, ast.BinOp):
        return _holes(node.left) + _holes(node.right)
    if isinstance(node, ast.IfExp):
        return _holes(node.body) + _holes(node.orelse)
    return []


def _shown(node: ast.AST) -> list[ast.AST]:
    """The expressions in `node` that stand for a sentence (a tuple's strings, a call's argument)."""
    if isinstance(node, ast.Tuple):
        out: list[ast.AST] = []
        for item in node.elts:
            out += _shown(item)
        return out
    if isinstance(node, ast.Call):
        return [node.args[0]] if node.args else []
    return [node]


def nodes_of(source: Source, tree: ast.AST) -> list[ast.AST]:
    """Every expression of this source that stands for a sentence."""
    found: list[ast.AST] = []
    if source.consts:
        for node in tree.body:  # type: ignore[attr-defined]
            if isinstance(node, ast.Assign):
                names = {t.id for t in node.targets if isinstance(t, ast.Name)}
                if names & set(source.consts):
                    found.append(node.value)
    scope = _bodies(tree, source.functions)
    for body in scope:
        for node in ast.walk(body):
            if isinstance(node, ast.Call):
                name = _name(node)
                if name in source.raises and node.args:
                    found.append(node.args[0])
                elif name in source.calls and node.args:
                    found.append(node.args[-1] if name == "_reason" else node.args[0])
                elif name in source.keywords or any(k.arg in source.keywords for k in node.keywords):
                    found += [k.value for k in node.keywords if k.arg in source.keywords]
            elif isinstance(node, ast.Assign) and source.assigns:
                names = {t.id for t in node.targets if isinstance(t, ast.Name)}
                if names & set(source.assigns):
                    found.append(node.value)
    if source.returns:
        for fn in _bodies(tree, source.returns):
            for node in ast.walk(fn):
                if isinstance(node, ast.Return) and node.value is not None:
                    found += _shown(node.value)
    return found


def collect_sources() -> list[tuple[str, int, str, list[str]]]:
    """(file, line, text with `{}` holes, hole sources) for every checked sentence."""
    rows = []
    for source in SOURCES:
        tree = ast.parse((SRC / source.path).read_text(encoding="utf-8"))
        for node in nodes_of(source, tree):
            holes = _holes(node)
            for text in _pieces(node):
                # `{host}` in a constant that is filled in with `.format` reads
                # the same as an f-string's `{}` to the rules.
                rows.append((source.path, node.lineno, PLACEHOLDER.sub("{}", text), holes))
            if not _pieces(node):
                # A bare name or a call: `raise ToolError(str(exc))` re-raises
                # text written elsewhere, which has to be named in the allowlist.
                rows.append((source.path, node.lineno, "{}", [ast.unparse(node)]))
    return sorted(set((f, ln, t, tuple(h)) for f, ln, t, h in rows))  # type: ignore[arg-type]


def core_problems(text: str, holes: list[str] | tuple[str, ...] = ()) -> list[str]:
    if not text.strip():
        return []  # "no message": a function that returns "" when nothing is wrong
    why = problems(text) if text != "{}" else []
    if CORE_JARGON.search(text):
        why.append("developer vocabulary")
    if any(RAW_HOLE.search(h) for h in holes):
        why.append("raw exception text")
    return why


def violations(rows=None):
    out = []
    for file, line, text, holes in rows if rows is not None else collect_sources():
        if (file, text) in ALLOWLIST:
            continue
        why = core_problems(text, holes)
        if why:
            out.append((file, line, text, "; ".join(why)))
    return out


def test_every_message_a_person_reads_is_a_plain_sentence():
    bad = violations()
    assert not bad, (
        "these sentences reach a toast through a route's computed `detail`: "
        "sentence case, a full stop, no field names or developer words, no raw "
        "exception text (log it instead), no dashes (INBOX 472). Rewrite, or "
        "allowlist with a reason:\n"
        + "\n".join(f"{f}:{ln}  [{why}]  {text!r}" for f, ln, text, why in bad[:80])
    )


def test_the_allowlist_has_no_stale_entries():
    live = {(file, text) for file, _line, text, _holes in collect_sources()}
    stale = [key for key in ALLOWLIST if key not in live]
    assert not stale, f"allowlist entries that match no message any more: {stale}"
    assert all(ALLOWLIST.values()), "an allowlist entry needs a reason"


def test_the_collector_finds_what_it_is_pointed_at():
    # A ratchet that parses nothing passes forever.
    rows = collect_sources()
    files = {f for f, *_ in rows}
    assert files == {s.path for s in SOURCES}, files ^ {s.path for s in SOURCES}
    assert len(rows) > 150
    sample = ast.parse(
        'INSTALL_HINT = "run pip install x"\n'
        "def f():\n"
        '    raise ValueError(f"broke: {exc}")\n'
    )
    got = [t for src in (Source("x", raises=("ValueError",), consts=("INSTALL_HINT",)),) for t in nodes_of(src, sample)]
    assert len(got) == 2
    assert core_problems("Run pip install x.") == ["developer vocabulary"]
    assert "raw exception text" in core_problems("Broke: {}.", ["exc"])
    assert core_problems("Install the voice package in Settings, then restart the app.") == []


#: Each computed `detail=` in the API, and where its text is written. A row
#: here is a promise that the source is in `SOURCES` above (or is fixed text).
REVIEWED_COMPUTED: dict[tuple[str, str], str] = {
    ("app.py", "detail"): "the handler re-serialises an HTTPException's own detail: every raise site is checked",
    ("routes_auth.py", "problem"): "_new_password_problem in routes_auth.py, one fixed sentence",
    ("routes_auth.py", "detail"): "the new-device gate in routes_auth.py picks one of two fixed sentences",
    ("this_computer.py", "REFUSAL"): "a constant in this_computer.py, one fixed sentence",
    ("routes_settings.py", "REFUSAL"): "api/this_computer.py REFUSAL, one fixed sentence",
    ("routes_auth.py", "NO_PASSWORD_ELSEWHERE"): "one fixed sentence in routes_auth.py",
    ("routes_bench.py", "BUSY"): "a constant in routes_bench.py, checked below",
    ("routes_bench.py", "NOT_RUNNING"): "a constant in routes_bench.py, checked below",
    ("routes_bench.py", "NO_MODELS"): "a constant in routes_bench.py, checked below",
    ("routes_bench.py", "OFF"): "a constant in routes_bench.py, checked below",
    ("routes_board_library.py", "detail"): "_fail's callers pass literals and f-strings of counts and names, which collect() checks",
    ("routes_import.py", "str(exc)"): "TooBig from entry/app_import.py, one fixed sentence",
    ("routes_webclip.py", "NOT_A_PAGE"): "a constant in routes_webclip.py, checked below",
    ("routes_whiteboard.py", "detail"): "one of two literal sentences, chosen by what the XMind archive holds",
    ("routes_backups.py", "str(exc)"): "FileNotFoundError and ValueError from core/backup.py restore_backup",
    ("routes_categories.py", "str(exc)"): "ToolError (ai/tools/categories.py) and ValueError (entry/manager.py)",
    ("routes_captions.py", "str(exc)"): "CaptionsError from ai/captions.py: its hint constants and literal sentences",
    ("routes_recordings.py", "str(exc)"): "RuntimeError from ai/voice.py transcribe",
    ("routes_recordings.py", "voice.INSTALL_HINT"): "ai/voice.py INSTALL_HINT",
    ("routes_chat.py", "str(exc)"): "ToolError from validate_make_plan and summarise_turns",
    ("routes_documents.py", "str(error)"): "ValueError from core/syntaxcheck.py check",
    ("routes_documents.py", "viewed.message or 'There was no readable text in that file.'"): "ViewedFile.message in core/docview.py",
    ("routes_entries.py", "str(exc)"): "ValueError from ai/extractor.py build_extraction",
    ("paging.py", "_BAD"): "a fixed sentence, the constant in api/paging.py",
    ("routes_entries.py", "librarian.AI_FAILED_MESSAGE"): "a constant in ai/librarian.py, checked there",
    ("routes_files.py", "reason"): "core/ocr.py unavailable_reason",
    ("routes_auth.py", "REFUSAL"): "a fixed sentence, the constant in api/this_computer.py",
    ("routes_map_from_notes.py", "str(exc)"): "ValueError from map_from_note_entry in this module: a fixed sentence with the note id",
        ("routes_files.py", "ocr.unavailable_reason('rapidocr')"): "core/ocr.py unavailable_reason",
    ("routes_files.py", "edit_message"): "core/docview.py editability",
    ("routes_files.py", "str(exc)"): "ValueError and FileExistsError from entry/manager.py, ValueError from core/ocr.py set_language",
    ("routes_learned.py", "str(exc)"): "ValueError from ai/learning.py record and ai/facts.py set_switches",
    ("routes_mentions.py", "LINK_UNSAFE_WHY"): "a constant in routes_mentions.py, checked below",
    ("routes_models.py", "str(exc)"): "ValueError from ai/model_manager.py known_feature",
    ("routes_models.py", "reason"): "core/security.py check_backend_url",
    ("routes_models.py", "info['error']"): "ai/model_cards.py inspect_model_name",
    ("routes_settings.py", "importer.INSTALL_HINT"): "entry/importer.py INSTALL_HINT",
    ("routes_tags.py", "str(exc)"): "ValueError from entry/manager.py rename_tags",
    ("routes_tidy.py", "str(exc)"): "ValueError from entry/tidy.py set_auto and LookupError from entry/tidy.py undo",
    ("routes_voice.py", "voice.INSTALL_HINT"): "ai/voice.py INSTALL_HINT",
    ("routes_voice.py", "over_limit_detail"): "the two callers pass literals, which collect() checks",
    ("routes_insights.py", "str(exc)"): "ValueError from ai/insights.py confirm and dismiss",
    ("routes_voice.py", "message"): "the sentences ai/voice.py remove_model returns, checked in SOURCES",
    ("routes_voice.py", "str(exc)"): "RuntimeError from ai/voice.py transcribe",
    ("routes_webclip.py", "WEB_OFF"): "a constant in routes_webclip.py, checked below",
    ("routes_webclip.py", "str(exc)"): "ClipRefused from core/webclip.py",
    ("routes_maintenance.py", "refusal"): "core/maintenance.py SHORTCUT_REFUSALS, fixed sentences keyed by reason",
    ("routes_websearch.py", "str(exc)"): "WebSearchError (search/websearch.py) and SearxngError (search/searxng_*.py)",
}


def _computed_rows():
    return [r for r in collect(computed=True) if r[2].startswith("<computed> ")]


def test_every_computed_route_detail_comes_from_a_checked_source():
    seen = {(f, text[len("<computed> ") :]) for f, _l, text, _s in _computed_rows()}
    new = sorted(seen - set(REVIEWED_COMPUTED))
    assert not new, (
        "a route passes a computed message to the person. Name where its text "
        "is written (and put that source in SOURCES), or use a fixed sentence "
        f"and log the exception: {new}"
    )
    stale = sorted(set(REVIEWED_COMPUTED) - seen)
    assert not stale, f"reviewed entries that match no route any more: {stale}"
    assert all(REVIEWED_COMPUTED.values())


#: (file, placeholder) -> why an f-string `detail` may carry it.
RAW_DETAIL_OK: dict[tuple[str, str], str] = {
    ("routes_settings.py", "exc"): "a SkillError, a sentence written for whoever wrote the skill (ai/skills.py, checked in SOURCES)",
}


def test_no_route_detail_carries_a_raw_exception():
    bad = []
    for path in route_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _name(node) in ("HTTPException", "StarletteHTTPException"):
                for kw in node.keywords:
                    if kw.arg != "detail":
                        continue
                    for hole in _holes(kw.value):
                        if RAW_HOLE.search(hole) and (label(path), hole) not in RAW_DETAIL_OK:
                            bad.append(f"{label(path)}:{kw.value.lineno}")
    assert not bad, f"an f-string `detail` shows an exception's own text; log it and write a sentence: {bad}"


def test_no_route_literal_tells_the_person_to_run_a_command():
    # The literal details are held to the API rules by test_server_detail_wording;
    # the install-hint rule (name what to install, never a `pip` line) is added here.
    bad = [
        f"{f}:{ln}  {text!r}"
        for f, ln, text, _s in collect()
        if CORE_JARGON.search(text) and (f, text) not in ALLOWLIST
    ]
    assert not bad, f"a route detail carries developer vocabulary: {bad}"


@pytest.mark.parametrize("module, name", [("routes_webclip.py", "WEB_OFF"), ("routes_webclip.py", "NOT_A_PAGE"), ("routes_mentions.py", "LINK_UNSAFE_WHY"), ("routes_bench.py", "OFF"), ("routes_bench.py", "BUSY"), ("routes_bench.py", "NO_MODELS"), ("routes_bench.py", "NOT_RUNNING")])
def test_a_route_constant_reads_as_a_sentence(module, name):
    tree = ast.parse((API / module).read_text(encoding="utf-8"))
    texts = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == name for t in node.targets):
            texts += _pieces(node.value)
    assert texts, f"{name} not found"
    assert all(not problems(t) for t in texts), texts


# --- what a route does with an exception: a sentence, and the log keeps the rest


TRANSPORT_TEXT = "HTTPConnectionPool(host='127.0.0.1', port=11434): Max retries exceeded"


def _boom(*_args, **_kwargs):
    from tessellate.ai.ollama_client import OllamaError

    raise OllamaError(f"Chat with 'x' failed: {TRANSPORT_TEXT}")


def _sentence(detail: str) -> None:
    assert TRANSPORT_TEXT not in detail and "OllamaError" not in detail, detail
    assert not problems(detail), (detail, problems(detail))


def test_a_model_failure_in_improve_writing_is_a_sentence(ai_client, monkeypatch, caplog):
    from tessellate.ai import librarian

    caplog.set_level("WARNING")
    monkeypatch.setattr(librarian, "improve_writing", _boom)
    response = ai_client.post("/entries/improve", json={"text": "fix me"})
    assert response.status_code == 502
    assert response.json()["detail"] == librarian.AI_FAILED_MESSAGE
    _sentence(response.json()["detail"])
    assert TRANSPORT_TEXT in caplog.text, "the provider's own text belongs in the log"


def test_a_model_failure_in_generate_title_is_a_sentence(ai_client, monkeypatch, caplog):
    from tessellate.ai import librarian

    caplog.set_level("WARNING")
    note = ai_client.post("/entries", json={"content": "buy milk and eggs"}).json()
    monkeypatch.setattr(librarian, "generate_title", _boom)
    response = ai_client.post(f"/entries/{note['id']}/generate-title")
    assert response.status_code == 502
    _sentence(response.json()["detail"])
    assert TRANSPORT_TEXT in caplog.text


def test_a_model_failure_in_the_chat_summary_is_a_sentence(ai_client, monkeypatch, caplog):
    from tessellate.ai import tools

    caplog.set_level("WARNING")
    monkeypatch.setattr(tools, "summarise_turns", _boom)
    response = ai_client.post("/chat/compress", json={"history": [{"question": "q", "answer": "a"}]})
    assert response.status_code == 503
    _sentence(response.json()["detail"])
    assert TRANSPORT_TEXT in caplog.text


def test_a_model_failure_reading_a_spec_or_removing_a_model_is_a_sentence(
    ai_client, fake_ollama, monkeypatch, caplog
):
    caplog.set_level("WARNING")
    monkeypatch.setattr(fake_ollama, "model_spec", _boom)
    spec = ai_client.get("/models/spec", params={"name": "llama3.2:latest"})
    assert spec.status_code == 502
    _sentence(spec.json()["detail"])

    fake_ollama.installed.append({"name": "spare-model:latest", "size": 500})
    monkeypatch.setattr(fake_ollama, "delete", _boom)
    gone = ai_client.post("/models/delete", json={"name": "spare-model:latest"})
    assert gone.status_code == 502
    _sentence(gone.json()["detail"])
    assert TRANSPORT_TEXT in caplog.text


def test_a_confirmed_tool_that_fails_answers_with_a_sentence_for_the_person(ai_client, caplog):
    caplog.set_level("WARNING")
    response = ai_client.post(
        "/chat/tools/execute", json={"name": "delete_category", "arguments": {"name": "No such category"}}
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    _sentence(detail)
    assert "delete_category" not in detail, "the model-facing text names the tool"
    assert "No such category" in caplog.text, "the model-facing text is kept in the log"


def test_a_clip_that_cannot_be_transcribed_does_not_show_the_exception(client, monkeypatch, caplog):
    from tessellate.ai import voice

    caplog.set_level("WARNING")
    monkeypatch.setattr(voice, "whisper_available", lambda: True)

    def broken(*_a, **_k):
        raise ValueError("/home/someone/.cache/whisper/model.bin is corrupt")

    monkeypatch.setattr(voice, "transcribe", broken)
    response = client.post("/voice/transcribe", files={"file": ("clip.webm", b"fake-audio", "audio/webm")})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "/home/someone" not in detail
    assert not problems(detail)
    assert "/home/someone" in caplog.text


def test_a_document_that_cannot_be_converted_does_not_show_the_exception(client, monkeypatch, caplog):
    from tessellate.api import routes_settings

    caplog.set_level("WARNING")
    monkeypatch.setattr(routes_settings.importer, "markitdown_available", lambda: True)

    def broken(_path):
        raise ValueError("corrupt zip at offset 0x2a")

    monkeypatch.setattr(routes_settings.importer, "convert_to_markdown", broken)
    response = client.post("/import/document", files={"file": ("deck.pptx", b"junk", "application/x")})
    assert response.status_code == 422
    assert "corrupt zip" not in response.json()["detail"]
    assert not problems(response.json()["detail"])
    assert "deck.pptx" in caplog.text


def test_the_install_hints_name_what_to_install():
    from tessellate.ai import voice
    from tessellate.entry import importer

    for hint, name in ((voice.INSTALL_HINT, "Voice notes"), (importer.INSTALL_HINT, "Import documents")):
        assert name in hint and "Settings, Packages" in hint
        assert not core_problems(hint), hint
