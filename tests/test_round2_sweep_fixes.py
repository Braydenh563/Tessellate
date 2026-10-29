"""What the round-2 sweeps (errors, docks, contrast, touch at 1440, 1024, 820
and 390) found, held.

- errors.js at 390: the Notes capture strip was cut at the card's edge with
  four tools past it. documents.js is loaded lazily, so before the Library is
  opened the strip has no More and no fit; the phone band's one-row rule now
  applies only to a strip the fit is mounted on.
- touch.js at 820 and 1024 (coarse pointer): a due reminder's toast, taken
  from the top in the 600 to 1100 band, covered all four Notes sub-tabs. Off
  Chat the band's toast is in the desktop's corner, above the status bar.
- contrast.js, light: "Changes notes" (--warn) 4.45:1, "Forget everything
  learned" (--error on --error-soft) 4.34:1 and the suggestions count 4.41:1.
  One step darker each.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "frontend" / "css"


def _css(name: str) -> str:
    return re.sub(r"/\*.*?\*/", "", (CSS / name).read_text(encoding="utf-8"), flags=re.S)


def test_the_phone_band_keeps_one_row_only_where_the_fit_is_mounted() -> None:
    css = _css("05-sidebars-themes.css")
    # Never once More is open (INBOX 665): one row then ran 700px past the
    # strip's border at 390.
    assert re.search(
        r"\.doc-toolbar:not\(\.is-more-open\):has\(> \.doc-toolbar-tools\)\s*\{\s*flex-wrap: nowrap;", css
    )
    assert not re.search(r"\n  \.doc-toolbar \{\s*flex-wrap: nowrap;\s*\}", css)


def test_a_toast_between_600_and_1100_leaves_the_sub_tabs_alone() -> None:
    css = _css("08-consistency.css")
    block = css[css.index("@media (min-width: 600px) and (max-width: 1099.98px)"):]
    block = block[: block.index("\n}\n")]
    assert 'body:not([data-tab="chat"]) #toast-box' in block
    assert "top: auto;" in block and "bottom: calc(var(--status-bar-h)" in block


def test_the_light_warn_and_error_inks_clear_aa_on_the_greys() -> None:
    tokens = _css("00-tokens-shell.css")
    assert "--warn: #8a5003;" in tokens
    assert "--error: #b01a1a;" in tokens
