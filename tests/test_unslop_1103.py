"""The 1103 unslop audit's twelve findings, held at source level.

Each test names the finding (docs/roadmap/agent-remaining/unslop-1103.md) and
the one fact in the stylesheet or markup that, if it drifts back, reproduces
it. The measured numbers live in the commit bodies.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_DIR = ROOT / "frontend" / "css"


def _css(name: str) -> str:
    text = (CSS_DIR / name).read_text(encoding="utf-8")
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _rules(css: str):
    for match in re.finditer(r"(?:(?<=[{}])|\A)([^{}]+)\{([^{}]*)\}", css):
        yield " ".join(match.group(1).split()), match.group(2)


def _body(css: str, selector: str) -> str:
    return "\n".join(b for s, b in _rules(css) if selector in [x.strip() for x in s.split(",")])


def test_1_reminder_time_is_its_own_phone_line():
    """Beside the words the time took 185px of 301 and left 48px for the text."""
    css = _css("08-consistency.css")
    grid = _body(css, "#reminder-groups .entry-list li > .entry-meta")
    assert '"tick text"' in grid and '"tick when"' in grid and '"acts acts"' in grid
