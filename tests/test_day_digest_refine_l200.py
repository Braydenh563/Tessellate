"""L-chat-200 (CHAT_PLAN section 2, dashboard row): the day's digest is the
engine's, and a running model may refine the count lines only when every
number and every linked phrase of the engine's line survives; quotes are never
reworded. Fake transport only: real wording quality is unverified."""

from __future__ import annotations


from tessellate.ai import day_digest

LINES = [
    {"part": "due", "kind": "count", "text": "One reminder is due today and 2 are overdue.", "counts": [1, 2], "links": ["One reminder"]},
    {"part": "due", "kind": "quote", "quote": "Call Sam about the deposit", "text": "Call Sam about the deposit"},
]


def test_a_refinement_that_keeps_every_number_and_link_is_taken() -> None:
    out = day_digest.refine(LINES, lambda prompt: "Today you have One reminder due, and 2 are overdue.")
    assert out[0]["text"] == "Today you have One reminder due, and 2 are overdue."
    assert out[0]["engine_text"] == LINES[0]["text"]


def test_quotes_are_never_sent_or_reworded() -> None:
    seen: list[str] = []

    def say(prompt: str) -> str:
        seen.append(prompt)
        return "x 1 2 One reminder"

    out = day_digest.refine(LINES, say)
    assert out[1] == LINES[1]
    assert all("Call Sam" not in p for p in seen)


def test_a_refinement_that_drops_or_adds_a_number_is_refused() -> None:
    for bad in ("One reminder is due and 3 are overdue.", "One reminder is due.", "One reminder is due, 2 overdue, 9 more."):
        assert day_digest.refine(LINES, lambda prompt, bad=bad: bad)[0]["text"] == LINES[0]["text"]


def test_a_model_that_fails_or_rambles_leaves_the_engine_line() -> None:
    def boom(prompt: str) -> str:
        raise RuntimeError("down")

    assert day_digest.refine(LINES, boom) == LINES
    assert day_digest.refine(LINES, lambda p: "One reminder 2 " + "word " * 80)[0]["text"] == LINES[0]["text"]


def test_the_route_refines_only_when_a_model_may_run(client, monkeypatch) -> None:
    plain = client.get("/insights/day", params={"refine": "1"}).json()
    assert all("engine_text" not in line for line in plain["lines"])


def test_the_route_refines_count_lines_when_a_model_runs(client, monkeypatch) -> None:
    from tessellate.api import chat_turn, routes_insights

    monkeypatch.setattr(chat_turn, "model_may_run", lambda: True)
    monkeypatch.setattr(routes_insights.day_digest if hasattr(routes_insights, "day_digest") else day_digest, "compose", lambda session, now: {"lines": [dict(LINES[0])], "empty": ""})

    class _P:
        def chat(self, model, messages, **kw):  # noqa: ANN001
            return {"content": "Today One reminder is due and 2 are overdue."}

    monkeypatch.setattr(routes_insights.deps, "get_ollama", lambda: _P())
    got = client.get("/insights/day", params={"refine": "1"}).json()
    assert got["lines"][0]["text"].startswith("Today One reminder")
    assert client.get("/insights/day").json()["lines"][0]["text"] == LINES[0]["text"]
