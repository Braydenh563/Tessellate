"""INBOX 1773: "Fold every branch", the twin of "Open every folded branch".

It is the level-1 fold (`wbMapFoldToLevel(1)`: one Undo step, saves only the
changed topics), reached from the same four places as its twin."""
from tests._app_js import frontend_text
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent


def _read(*parts):
    return (_REPO.joinpath(*parts)).read_text(encoding="utf-8")


def test_both_menus_carry_the_twin_with_the_twin_icon():
    html = _read("frontend", "index.html")
    assert 'id="wb-map-fold-all"' in html and 'id="wb-side-map-fold"' in html
    row = html[html.index('id="wb-map-fold-all"') :].split("</button>")[0]
    assert "ph-arrows-in-line-vertical" in row and "Fold every branch" in row and "Alt+1" in row
    side = html[html.index('id="wb-side-map-fold"') :].split("</button>")[0]
    assert "ph-arrows-in-line-vertical" in side and "Fold every branch" in side
    assert 'class="ghost small" id="wb-side-map-fold"' in html


def test_the_twin_is_the_level_one_fold_not_new_folding_code():
    wb = frontend_text("whiteboard.js")
    lib = _read("frontend", "js", "whiteboard-library.js")
    mp = frontend_text("whiteboard-map.js")
    assert '$("wb-map-fold-all")?.addEventListener("click", () => wbMapFoldToLevel(1))' in wb
    assert 'getElementById("wb-side-map-fold")?.addEventListener("click", () => wbMapFoldToLevel(1))' in lib
    assert "Fold every branch" in wb and "Fold every branch" in mp
    assert "function wbMapFoldAll" not in mp, "a property of the level fold, not a new global"
    assert "wbMapFoldToLevel.open = " in mp and "wbMapFoldToLevel.sync = " in mp
    assert "Every branch is already folded." in mp and "Folded ${" in mp


def test_enabled_only_when_it_would_change_something():
    mp = frontend_text("whiteboard-map.js")
    sync = mp[mp.index("wbMapFoldToLevel.sync = ") :].split("\n};")[0]
    assert "wb-map-fold-all" in sync and "wb-side-map-fold" in sync
    assert "wb-map-expand-all" in sync and "wb-side-map-expand" in sync
    assert sync.count(".disabled = ") >= 2
    wb = frontend_text("whiteboard.js")
    assert "wbMapFoldToLevel.sync()" in wb
    assert "wbMapFoldToLevel.sync()" in _read("frontend", "js", "whiteboard-library.js")


def test_help_names_the_twin():
    tail = _read("src", "tessellate", "ai", "help_topics_core_tail.py")
    assert "fold every branch" in tail.lower()
