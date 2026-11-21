"""L-world-class-630: does a real local model pick the browser tools well.

The browser tools (L-world-class-182) are tested against a fake transport in
`tests/test_browser_tools.py`; this is the same check with a real model, the
way `tests/test_harness_evals.py` checks the note tools. The pages are still
fakes, so nothing leaves the machine: only the model is real. Each case is a
fresh turn that starts on a page the browser already has open (the tools keep
one page, as a tab does), so the right first move is the one tool the request
names in plain words. A parked call (the confirm card) counts as the choice:
the model picked it, the guard asked.

    scratchpad/llama-dev.sh serve   # prints the two exports
    pytest -m evals tests/test_browser_tools_evals.py -s
"""

from __future__ import annotations

import json
import os
import time

import pytest

from tests.test_harness_evals import EVALS_MODEL, EVALS_URL, needs_a_model

PAGES = {
    "https://bread.example/": {
        "title": "Bread at home",
        "domain": "bread.example",
        "text": "Bread at home.\nA plain loaf needs flour, water, salt and yeast.\nSourdough uses a starter instead of yeast.",
        "links": [
            {"text": "Sourdough starter guide", "url": "https://bread.example/sourdough"},
            {"text": "Rye bread", "url": "https://bread.example/rye"},
        ],
    },
    "https://bread.example/sourdough": {
        "title": "Sourdough starter guide",
        "domain": "bread.example",
        "text": "Feed the starter every day. Hydration of 100 percent means equal flour and water by weight.",
        "links": [],
    },
    "https://bread.example/rye": {
        "title": "Rye bread",
        "domain": "bread.example",
        "text": "Rye needs a longer proof.",
        "links": [],
    },
}

#: (request, open a page first, the tools any one of which is the right first move).
CASES = [
    ("Open https://bread.example/ and tell me what it says", None, {"browser_open"}),
    ("On the page you have open, find where it mentions hydration", "https://bread.example/sourdough", {"browser_find"}),
    ("Follow the sourdough starter link on the open page", "https://bread.example/", {"browser_follow"}),
    ("Go back to the previous page in the browser", "two", {"browser_back"}),
    ("Read the rest of the page that is open in the browser", "https://bread.example/sourdough", {"browser_read"}),
]


@pytest.fixture()
def browser(app_state, fake_embeddings, monkeypatch):
    from fastapi.testclient import TestClient

    from tessellate.ai.openai_client import OpenAICompatClient
    from tessellate.ai.tools import tool_browser
    from tessellate.api.app import create_app
    from tessellate.core import deps
    from tessellate.search import websearch

    client = OpenAICompatClient(base_url=EVALS_URL)
    if not client.is_running():
        pytest.fail(f"TESSELLATE_EVALS_URL is {EVALS_URL} and nothing is answering there")
    deps.override_ai(ollama=client)
    config = deps.get_config()
    config.set_preference("llm_provider", "openai")
    config.set_preference("llm_base_url", EVALS_URL)
    config.set_preference("chat_model", EVALS_MODEL)
    config.set_preference("web_search_enabled", True)

    def fake(url):
        if url not in PAGES:
            raise websearch.WebSearchError("Couldn't open that page.")
        return {"url": url, **PAGES[url]}

    monkeypatch.setattr(websearch, "fetch_readable", fake)
    return TestClient(create_app()), tool_browser


def _start_on(tool_browser, start) -> None:
    """The page the case starts on; "two" is the guide opened after the front
    page, so there is a page to go back to."""
    from tessellate.core import deps

    tool_browser.reset()
    if start is None:
        return
    with deps.get_db().session() as session:
        for url in ("https://bread.example/", "https://bread.example/sourdough") if start == "two" else (start,):
            _open(session, url)


def _open(session, url: str) -> None:
    from tessellate.ai import tools

    result = tools.execute_tool(session, "browser_open", {"url": url})
    assert "error" not in result, result


@pytest.mark.evals
@needs_a_model
def test_the_model_picks_the_browser_tool_the_request_names(browser):
    client, tool_browser = browser
    rows = []
    for question, start, first_ok in CASES[: int(os.environ.get("CASES", len(CASES)))]:
        _start_on(tool_browser, start)
        started = time.monotonic()
        with client.stream("POST", "/chat/stream", json={"question": question, "use_tools": True}) as response:
            assert response.status_code == 200
            events = [json.loads(line) for line in response.iter_lines() if line]
        moves = [e.get("tool") or e.get("name") for e in events if e.get("type") in ("tool", "confirm")]
        moves = [m for m in moves if m]
        rows.append({"q": question, "first": moves[0] if moves else None, "all": moves, "ok": bool(moves) and moves[0] in first_ok, "s": round(time.monotonic() - started, 1), "said": "".join(e.get("delta", "") for e in events if e.get("type") == "answer")[:160], "events": sorted({e.get("type") for e in events})})
    print(json.dumps({"model": EVALS_MODEL, "rows": rows}, indent=1))
    right = sum(r["ok"] for r in rows)
    assert right >= len(CASES) - 1, rows
