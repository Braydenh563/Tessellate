"""Source text: the project site (docs/index.html) is static marketing copy, so its claims can only be compared, as text, with the code and README that make them true (L-ui-modernisation-72)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
TABLE = (ROOT / "frontend" / "js" / "settings-wiring.js").read_text(encoding="utf-8")


def _site_text() -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", SITE, flags=re.S)
    return re.sub(r"\s+", " ", text)


def test_every_shortcut_the_site_names_is_a_default_in_the_table():
    text = _site_text()
    for shown, key in (("Alt + N", "Alt+N"), ("Ctrl + K", "Ctrl+K"), ("Ctrl + P", "Ctrl+P"), ("Ctrl + Shift + A", "Ctrl+Shift+A")):
        assert shown in text, shown
        assert f'keys: "{key}"' in TABLE, key


def test_the_site_and_readme_name_the_same_downloads_and_start_script():
    for name in ("Tessellate-Setup-", "linux-x86_64.tar.gz", "start-desktop.sh", "--doctor"):
        assert name in SITE and name in README, name
    assert (ROOT / "start-desktop.sh").exists() and (ROOT / "start.sh").exists()
