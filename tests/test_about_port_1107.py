"""The owner, 2026-11-07: "it should be shown in settings which port the app is running on in like the about page".
About's version line names the address the page was served from, and the Guide's version topic says so."""

from __future__ import annotations

from pathlib import Path

from tessellate.ai.help_chat import HELP_TOPICS

ROOT = Path(__file__).resolve().parents[1]


def test_about_names_the_address_and_port_in_use():
    js = (ROOT / "frontend" / "js" / "settings.js").read_text(encoding="utf-8")
    fill = js[js.index('const aboutHealth = await apiJson("/health")') :][:700]
    assert "location.host" in fill and "Running at" in fill and '$("about-version").textContent' in fill


def test_the_guide_says_where_to_find_the_port():
    topic = next(t for t in HELP_TOPICS if "Settings, About says which version" in t["body"])
    assert "port" in topic["body"] and "port" in topic["keywords"]
