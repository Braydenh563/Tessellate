"""One 12 or 24 hour setting for every clock the app shows (WORLD_CLASS_PLAN
22.2). `time_format` is a preference ("auto" follows the browser's region);
prefs.js turns it into `clockOptions()` and `clockOptions.formatter()`, and every
frontend time formatter takes one of them. The lint is the second test: a new
`toLocaleTimeString`, `timeStyle` or `hour:` that skips them fails here."""

import re
from pathlib import Path

from tessellate.core import config as config_module

ROOT = Path(__file__).resolve().parents[1]
JS = {p.name: p.read_text(encoding="utf-8") for p in sorted((ROOT / "frontend/js").glob("*.js"))}


def test_the_preference_exists_with_an_auto_default():
    assert config_module.DEFAULT_PREFERENCES["time_format"] == "auto"
    routes = (ROOT / "src/tessellate/api/routes_settings.py").read_text(encoding="utf-8")
    assert 'time_format: Literal["auto", "12", "24"] | None = None' in routes
    assert '"time_format": config.get_preference("time_format", "auto")' in routes


def test_the_helpers_pick_the_hour_cycle():
    text = JS["prefs.js"]
    body = text.split("function clockOptions()", 1)[1].split("\n}\n", 1)[0]
    assert '"12"' in body and 'hourCycle: "h12"' in body
    assert '"24"' in body and 'hourCycle: "h23"' in body
    assert "clockOptions.formatter = (options)" in text


def test_every_time_formatter_takes_the_setting():
    bare = []
    for name, text in JS.items():
        if name == "prefs.js":
            continue
        lines = text.split("\n")
        for i, line in enumerate(lines):
            code = line.split("//", 1)[0]
            if not re.search(r"toLocaleTimeString\(|timeStyle|\bhour: *\"|Intl\.DateTimeFormat\(", code):
                continue
            #: A multi-line options object is read a few lines on.
            span = "\n".join(lines[max(0, i - 3):i + 8])
            if "clockOptions()" in span or "clockOptions.formatter(" in span:
                continue
            if "Intl.DateTimeFormat(" in code and not re.search(r"hour|timeStyle", span):
                continue  # a date-only formatter or the time zone name
            if "timeZoneName" in span and "hour" not in span:
                continue
            bare.append(f"{name}:{i + 1}: {line.strip()[:90]}")
    assert not bare, "a clock that ignores the 12 or 24 hour setting:\n" + "\n".join(bare)


def test_settings_has_the_choice_and_the_guide_names_it():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'id="pref-time-format"' in html
    assert 'value="12"' in html.split('id="pref-time-format"', 1)[1][:600]
    assert '{ key: "time_format", id: "pref-time-format" }' in JS["settings-rows.js"]
    assert 'setPreference("time_format"' in JS["settings-controls.js"]
    assert 'prefsCache.time_format' in JS["settings-prefs.js"]
    topics = (ROOT / "src/tessellate/ai/help_topics_more.py").read_text(encoding="utf-8")
    assert "12 or 24 hour" in topics
