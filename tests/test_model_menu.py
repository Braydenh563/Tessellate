"""The composer's model picker is a search, Recent, one collapsible row per
source and a pin per model (INBOX 1477, the owner's reference picker).

It is the menu `enhanceSelect` already draws for a `.feature-model-select`,
dressed by the lazy model-menu.js: no second picker, and the option rows keep
doing the choosing. The behaviour (typing, Enter, arrows, the pin, Escape) was
driven in a browser; these hold the wiring and the pure functions.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR, frontend_text

needs_node = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _run(body: str) -> object:
    source = (JS_DIR / "model-menu.js").read_text(encoding="utf-8")
    pieces = [
        re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M).group(0)
        for name in ("modelSource", "modelCountLabel")
    ]
    script = "\n".join(pieces) + f"\nprocess.stdout.write(JSON.stringify({body}));"
    return json.loads(subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout)


@needs_node
def test_a_model_is_filed_under_the_source_its_name_says() -> None:
    names = ["gemma3:4b", "hf.co/unsloth/Qwen3-GGUF:Q4", "gpt-oss:120b-cloud", "kimi:cloud"]
    keys = _run(f"{json.dumps(names)}.map((n) => modelSource(n).key)")
    assert keys == ["local", "hf", "cloud", "cloud"]
    assert _run("[modelCountLabel(1), modelCountLabel(4)]") == ["1 model", "4 models"]


def test_the_picker_is_wired_into_every_feature_model_select_and_lazy() -> None:
    selects = frontend_text("sheets-selects.js")
    assert 'select.classList.contains("feature-model-select")' in selects
    assert "enhanceSelect.richMenu?.(menu, select, opener)" in selects
    assert "enhanceSelect.richMenu = decorateModelMenu" in frontend_text("model-menu.js")
    assert 'ensureModule("modelMenu")' in selects
    entries = frontend_text("lazy-entries.js")
    assert 'modelMenu: ["/css/model-menu-lazy.css", "/js/model-menu.js"]' in entries
    index = (JS_DIR.parent / "index.html").read_text(encoding="utf-8")
    assert "model-menu" not in index, "the picker's shape is not a boot script"
    # Pins and recent picks follow the person to a restart or a second browser.
    ai = frontend_text("ai-tools.js")
    assert '"model-pins"' in ai and '"model-recent"' in ai


def test_the_picker_has_search_recent_groups_and_pins_in_that_order() -> None:
    js = frontend_text("model-menu.js")
    assert js.index("menu.replaceChildren(search, state.body)") > 0
    render = js[js.index("function modelMenuRender(") :][:1800]
    assert render.index('"Pinned"') < render.index('"Recent"') < render.index("modelMenuGroup(")
    for needle in ("mm-search-input", "mm-group-head", "mm-pin", "aria-expanded", "aria-pressed", "modelCountLabel("):
        assert needle in js, needle
    # The keyboard: arrows, Enter (the first match) and Escape (back to the opener).
    keys = js[js.index("function modelMenuWalk(") : js.index("function modelMenuSearch(")]
    for key in ("ArrowDown", "ArrowUp", "Home", "End", "Enter", "Escape", "ArrowRight", "ArrowLeft"):
        assert key in keys, key
    assert "closeActionMenus()" in keys


def test_the_picker_sheet_uses_tokens_and_the_shared_rich_picker_row() -> None:
    js = frontend_text("model-menu.js")
    assert "richPickerRow(" in js and 'setAttribute("role", "option")' not in js
    css = (JS_DIR.parent / "css" / "model-menu-lazy.css").read_text(encoding="utf-8")
    assert "position: sticky" in css[css.index(".mm-search {") :][:120]
    assert "min-width: var(--target-min)" in css[css.index(".mm-pin {") :][:260]
    assert "--motion-" not in css, "an interface transition runs on --ui-*"
    assert not re.search(r"\d+px", css), "spacing and size read tokens"
