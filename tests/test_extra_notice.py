"""One recipe for "this feature needs an optional package" (INBOX 1748, Q27).

The owner: "if they try to use a feature and it needs an optional package, the
notice should show until they install the package and if the package is
uninstalled for some reason then the notice should show again but the user
should be able to close or dismiss them like the no ai model connected
notices."

`extra-notice.js` (lazy) is the only builder; surfaces call
`extraNoticeMount(host, id)`. Dismissal is per package and ends when the
package's state changes.
"""

from __future__ import annotations

from tests._help_text import help_more_text
import re
from pathlib import Path

from tessellate.core import extras

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "frontend" / "js" / "extra-notice.js").read_text(encoding="utf-8")


def _sentences() -> dict[str, str]:
    block = re.search(r"const EXTRA_NOTICE_WHAT = \{(.*?)\n  \};", JS, re.S).group(1)
    #: A hyphenated id ("spell-fr") is a quoted key.
    return dict(re.findall(r'^\s*"?([\w-]+)"?: "([^"]+)",?$', block, re.M))


def test_every_registry_package_has_one_short_sentence() -> None:
    said = _sentences()
    missing = [e.id for e in extras.EXTRAS if e.id not in said]
    assert not missing, f"registry packages with no notice sentence: {missing}"
    assert "searxng" in said
    for ident, sentence in said.items():
        assert len(sentence) < 90, (ident, len(sentence))
        assert "!" not in sentence and chr(0x2014) not in sentence and "Oops" not in sentence, ident
        assert sentence[0].isupper() and sentence.endswith("."), ident


def test_the_notice_is_the_recipe_and_dismissal_ends_on_a_state_change() -> None:
    assert 'setLabel(host, "ph:package")' in JS
    order = [JS.index("host.append(text"), JS.index("host.append(close)")]
    assert order == sorted(order), "icon, sentence, button, then the close last"
    assert 'close.dataset.dismiss = "notice"' in JS
    assert 'close.className = "ghost small icon-only"' in JS
    assert "prefs.setJSON" in JS and "sessionStorage" not in JS, "a dismissal outlives the session"
    #: A package seen present clears its dismissal, so a later uninstall re-shows it.
    check = JS[JS.index("async function extraNoticeCheck") :]
    assert check.index("forget(id)") < check.index("dismissed(id)")
    assert "Object.assign(window, { extraNoticeMount" in JS


def test_surfaces_mount_it_and_nobody_builds_a_second_one() -> None:
    lightbox = (ROOT / "frontend" / "js" / "lightbox-view.js").read_text(encoding="utf-8")
    library = (ROOT / "frontend" / "js" / "library.js").read_text(encoding="utf-8")
    chat = (ROOT / "frontend" / "js" / "chat.js").read_text(encoding="utf-8")
    assert 'extraNoticeMount(doc, "pdfpages")' in lightbox
    assert re.search(r'extraNoticeMount\([^)]*"rapidocr"', library)
    assert 'extraNoticeMount(' in chat and '"searxng"' in chat
    app = (ROOT / "frontend" / "js" / "app.js").read_text(encoding="utf-8")
    assert 'extraNotice: ["/js/extra-notice.js"]' in app
    for path in (ROOT / "frontend" / "js").glob("*.js"):
        if path.name != "extra-notice.js":
            assert "extra-notice-row" not in path.read_text(encoding="utf-8"), path.name


def test_help_and_the_guide_name_the_notice() -> None:
    topic = help_more_text()
    assert "notice with Install" in topic and "Install" in topic
    #: The long half lives in the button's title, as the no-model notice does.
    assert "install.title" in JS
