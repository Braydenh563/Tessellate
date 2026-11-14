"""INBOX 1734 (the owner, real Windows): a running SearXNG still showed its
setup lines ("Docker isn't installed, so it runs from its own virtualenv...",
"Something is using port 8888...") and Start stayed the primary button, so a
good start read as a failed one. The card now has a running view of one calm
line, a live badge with a dot, and the run-it-yourself disclosure inside it.

The view is a pure function (`refreshSearxngHost.view`), run here in node against
status payloads shaped like `/websearch/searxng/status`."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from tests._js_scope import unwrapped

ROOT = Path(__file__).resolve().parents[1]
JS = unwrapped((ROOT / "frontend" / "js" / "settings-controls.js").read_text(encoding="utf-8"))
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
LAZY_CSS = (ROOT / "frontend" / "css" / "settings-controls-lazy.css").read_text(encoding="utf-8")
needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")

STALE_PORT = (
    "Something is using port 8888, and it isn't answering as SearXNG. "
    "Starting will move to the next free port on its own."
)


def _info(**over) -> dict:
    base = {
        "backend": "source", "docker_installed": False, "state": "running", "responding": True,
        "url": "http://127.0.0.1:8889", "installing": False, "install_error": "", "detail": "",
        "port": {"port": 8888, "free": False, "held_by_searxng": False, "detail": STALE_PORT},
    }
    return {**base, **over}


def _view(info: dict) -> dict:
    match = re.search(r"^refreshSearxngHost\.view = .*?^\};\n", JS, re.S | re.M)
    assert match, "refreshSearxngHost.view is gone from settings-controls.js"
    script = "const refreshSearxngHost = {};\n" + match.group(0) + f"\nprocess.stdout.write(JSON.stringify(refreshSearxngHost.view({json.dumps(info)})));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_a_running_instance_gets_one_calm_line_naming_where_it_runs():
    view = _view(_info())
    assert view["running"] is True
    assert view["status"] == "Running on port 8889, from its own virtualenv."
    assert view["backend"] == "" and view["port"] == "" and view["portError"] is False
    assert "Docker isn't installed" not in json.dumps(view) and "Something is using" not in json.dumps(view)
    docker = _view(_info(backend="docker", docker_installed=True, url="http://127.0.0.1:8888"))
    assert docker["status"] == "Running on port 8888, in Docker."


@needs_node
def test_stop_is_the_action_while_it_runs_and_start_is_not():
    assert 'start.classList.toggle("ghost", running);' in JS
    assert 'stop.classList.toggle("ghost", !running);' in JS
    assert "start.disabled = running;" in JS


@needs_node
def test_the_setup_lines_stay_for_the_not_running_states():
    view = _view(_info(state="stopped", responding=False))
    assert view["running"] is False
    assert view["backend"].startswith("Docker isn't installed, so it runs from its own virtualenv")
    assert view["port"] == STALE_PORT and view["portError"] is True
    assert view["status"] == "Installed and ready: press Start SearXNG."
    # Starting (running, not answering yet) is not "running" either.
    assert _view(_info(responding=False))["running"] is False


def test_the_live_badge_is_the_recipes_dot_and_the_script_sets_it():
    assert 'badge.className = `chip item-label${view.running ? " is-ok is-live" : ""}`' in JS
    rule = LAZY_CSS[LAZY_CSS.index(".item-label.is-live::before {"):][:400]
    assert "var(--ok)" in rule and "border-radius: var(--radius-pill)" in rule
    assert "var(--space-" in rule


def test_the_run_it_yourself_disclosure_lives_inside_the_searxng_card():
    start = INDEX.index('<div class="searxng-host"')
    summary = INDEX.index("Prefer to run it yourself?")
    end = INDEX.index("</section>", start)
    assert start < summary < end
    # The card is still expanded when the disclosure starts (one div more opened
    # than closed since the card's own tag).
    between = INDEX[start:summary]
    assert between.count("<div") == between.count("</div>") + 1
    # The card's own end tag comes after the disclosure's.
    tail = INDEX[summary:end]
    assert tail.index("</details>") < tail.index("</div>")


def test_the_disclosure_body_is_inset_from_its_summary():
    rule = LAZY_CSS[LAZY_CSS.index(".searxng-host > .searxng-diy"):][:600]
    assert "var(--space-" in rule and "padding" in rule


def test_the_live_label_is_in_the_design_recipe_index():
    design = (ROOT / "docs" / "DESIGN.md").read_text(encoding="utf-8")
    assert "`is-live`" in design
