"""Q25: the welcome's preferences card lists the calibratable choices, each a
real preference the server takes, and is skippable (Skip closes the whole card)."""
from pathlib import Path

from tessellate.api.routes_settings import PreferencesBody

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend/js/onboarding.js").read_text(encoding="utf-8")


def test_every_choice_is_a_preference_the_server_takes():
    for key in ("writing_style", "week_start", "date_order", "before_includes_day"):
        assert f'key: "{key}"' in JS
        assert key in PreferencesBody.model_fields


def test_the_card_is_a_slide_before_the_tour_and_skip_stays():
    assert JS.index("prefs: true") > JS.index("dynamic: true")
    assert 'id="onboarding-skip"' in (ROOT / "frontend/index.html").read_text(encoding="utf-8")


def test_each_choice_has_a_settings_row_too():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    for pid in ("pref-writing-style", "pref-week-start", "pref-date-order", "pref-before-includes-day"):
        assert f'id="{pid}"' in html
