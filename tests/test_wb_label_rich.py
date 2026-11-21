"""L-whiteboard-46: rich text in a drawn shape's label (WHITEBOARD_PLAN section 2, formatted text).

`whiteboard-label-rich.js` draws a label whose data says `label_md: true` through the board's own markdown renderer
and makes the result inert. The pure link rule runs in node; the rendering runs in a real browser (playwright,
skipped where it is not installed) on the app's own `renderMarkdown`, so the `<script>` and `javascript:` checks
are about what a person would see, not about a stub.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests._app_js import frontend_text

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "frontend" / "js"
STUBS = (
    "const wbFmtState = {}; const WB_TEXT_LOOK_KEYS = { shape: [] }, WB_SKETCH_RESET_KEYS = [];"
    "const onSurface = () => {}; const wbFmtApply = () => {}; const wbFmtSketch = (e) => e;"
)


def _node(expr: str):
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    script = STUBS + frontend_text("whiteboard-label-rich.js") + f"\nconsole.log(JSON.stringify({expr}));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(out.stdout)


def test_only_a_stored_true_makes_a_label_rich():
    assert _node("wbFmtState.richLabel.isRich({ label_md: true })") is True
    for old in ("{}", "{ label_md: 'yes' }", "{ label_md: 1 }", "{ label_md: false }", "{ d: 'M0 0', label: '**x**' }"):
        assert _node(f"wbFmtState.richLabel.isRich({old})") is False, "old labels are never read as markdown"
    assert _node("wbFmtState.richLabel.isRich(null)") is False


def test_a_link_keeps_only_web_mail_and_phone_addresses():
    clean = "wbFmtState.richLabel.cleanHref"
    assert _node(f"{clean}('https://example.com/a?b=1')") == "https://example.com/a?b=1"
    assert _node(f"{clean}('mailto:a@b.co')") == "mailto:a@b.co"
    for bad in ("javascript:alert(1)", " JavaScript:alert(1)", "java\\nscript:alert(1)", "java\\tscript:alert(1)", "data:text/html,x", "vbscript:x", "/relative", "#frag", ""):
        assert _node(f"{clean}('{bad}')") == "", bad


def test_list_depth_follows_the_indent_whatever_the_width():
    depths = "wbFmtState.richLabel.listDepths"
    assert _node(f"{depths}('- a\\n  - b\\n    - c\\n- d')") == [0, 1, 2, 0]
    assert _node(f"{depths}('- a\\n    - b\\n        - c\\n    - d')") == [0, 1, 2, 1]
    assert _node(f"{depths}('1. a\\n\\t2. b')") == [0, 1]
    assert _node(f"{depths}('- a\\n```\\n  - not an item\\n```\\n  - b')") == [0, 1], "a fenced line is not an item"
    assert _node(f"{depths}('no list')") == []


def test_it_is_wired_into_the_board_bundle_and_the_panel():
    assert "/js/whiteboard-label-rich.js" in frontend_text("lazy-entries.js")
    layout = frontend_text("whiteboard.js")
    assert "wbFmtState.richLabel?.paint(groupEl, label, area, fontSize)" in layout
    assert "wbFmtState.richLabel?.mark(label, parsed)" in layout
    assert 'id="wb-fmt-lmd"' in (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "innerHTML" not in frontend_text("whiteboard-label-rich.js")


_PAGE = """
const { chromium } = require('playwright');
const fs = require('fs');
const payload = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on('pageerror', (e) => console.error('pageerror', e.message));
  await page.route('http://app.test/', (route) => route.fulfill({ contentType: 'text/html', body: '<div id="host"></div>' }));
  await page.goto('http://app.test/');
  await page.addScriptTag({ content: 'window.onSurface = () => {}; window.$ = () => null;' });
  for (const f of ['settings-body.js', 'app.js', 'prefs.js', 'store.js', 'notes-list.js', 'markdown.js', 'navigation.js', 'chat-agent.js', 'att-chip.js', 'router.js']) {
    await page.addScriptTag({ content: fs.readFileSync(payload.js + f, 'utf8') }).catch(() => {});
  }
  const out = await page.evaluate(({ code, cases }) => {
    let alerts = 0;
    window.alert = () => { alerts += 1; };
    const rich = (0, eval)(code + '; wbFmtState.richLabel;');
    const results = {};
    for (const [name, md] of Object.entries(cases)) {
      const box = document.createElement('div');
      document.getElementById('host').append(box);
      const raw = md.startsWith('HTML:');
      if (raw) box.innerHTML = md.slice(5);
      else renderMarkdown(box, md);
      rich.inert(box);
      if (!raw) rich.indentItems(box, md);
      for (const a of box.querySelectorAll('a')) a.click();
      results[name] = {
        html: box.innerHTML,
        scripts: box.querySelectorAll('script, iframe, img, object, embed, style').length,
        handlers: [...box.querySelectorAll('*')].filter((el) => [...el.attributes].some((x) => /^on/i.test(x.name))).length,
        links: [...box.querySelectorAll('a')].map((a) => ({ href: a.getAttribute('href'), rel: a.rel, target: a.target })),
        lists: box.querySelectorAll('ul, ol').length,
        indented: box.querySelectorAll('li[data-depth]').length,
        strong: box.querySelectorAll('strong, b').length,
        em: box.querySelectorAll('em, i').length,
        text: box.textContent,
      };
    }
    results.alerts = alerts;
    return results;
  }, { code: payload.code, cases: payload.cases });
  console.log(JSON.stringify(out));
  await browser.close();
})();
"""


def _browser(tmp_path, cases: dict[str, str]):
    payload = tmp_path / "payload.json"
    payload.write_text(json.dumps({"js": str(JS) + "/", "code": STUBS + frontend_text("whiteboard-label-rich.js"), "cases": cases}), encoding="utf-8")
    path = tmp_path / "rich.js"
    path.write_text(_PAGE, encoding="utf-8")
    run = subprocess.run(
        ["node", str(path), str(payload)], capture_output=True, text=True,
        env={"NODE_PATH": "/opt/node22/lib/node_modules", "PLAYWRIGHT_BROWSERS_PATH": "/opt/pw-browsers", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/node22/bin", "HOME": str(tmp_path)},
    )
    if "Executable doesn't exist" in run.stderr or "Cannot find module" in run.stderr:
        pytest.skip("needs playwright and its browser")
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_rich_words_render_and_hostile_ones_stay_inert(tmp_path):
    got = _browser(
        tmp_path,
        {
            "rich": "**bold** and *italic*\n\n- one\n    - nested\n- two\n\n[site](https://example.com)",
            "script": "<script>window.alert(1)</script> hello <img src=x onerror=alert(1)> <b onclick=alert(1)>x</b>",
            "jslink": "[click](javascript:alert(1)) and [tab](java\tscript:alert(2)) and <a href=\"javascript:alert(3)\">raw</a>",
            "plain": "no marks here",
            # Raw elements put straight into the box (what a renderer bug would let through): `inert` alone must hold.
            "raw": 'HTML:<p onclick="alert(1)">a</p><a href="javascript:alert(1)" onmouseover="alert(2)">bad</a><a href=" Java&#10;Script:alert(3)">bad2</a>'
            '<a href="https://ok.example/x" onfocus="alert(4)">good</a><script>alert(5)</script><iframe src="javascript:alert(6)"></iframe><img src=x onerror="alert(7)"><svg onload="alert(8)"></svg>',
        },
    )
    raw = got["raw"]
    assert raw["scripts"] == 0 and raw["handlers"] == 0, raw["html"]
    assert raw["links"] == [{"href": "https://ok.example/x", "rel": "noopener noreferrer", "target": "_blank"}], raw["html"]
    assert "javascript" not in raw["html"].lower() and "bad" in raw["text"], raw["html"]
    rich = got["rich"]
    assert rich["strong"] == 1 and rich["em"] == 1 and rich["lists"] >= 1 and rich["indented"] == 1, rich["html"]
    assert "link-card" not in rich["html"] and "<i " not in rich["html"], rich["html"]
    assert rich["strong"] == 1 and rich["em"] == 1 and rich["lists"] >= 1
    assert rich["links"] == [{"href": "https://example.com", "rel": "noopener noreferrer", "target": "_blank"}]
    for name in ("script", "jslink"):
        assert got[name]["scripts"] == 0 and got[name]["handlers"] == 0, got[name]["html"]
        assert not any((link["href"] or "").lower().replace(" ", "").startswith(("javascript", "java")) for link in got[name]["links"]), got[name]["html"]
    assert got["alerts"] == 0, "nothing ran, including a click on every link"
    assert got["plain"]["text"].strip() == "no marks here"


_EXPORT_PAGE = _PAGE.split("  const out = await page.evaluate")[0] + """
  const out = await page.evaluate(({ code, text }) => {
    const NS = 'http://www.w3.org/2000/svg';
    const rich = (0, eval)(code + '; wbFmtState.richLabel;');
    const svg = document.createElementNS(NS, 'svg');
    document.getElementById('host').append(svg);
    const group = document.createElementNS(NS, 'g');
    const label = document.createElementNS(NS, 'text');
    label.setAttribute('class', 'sketch-label');
    label.__wbText = text;
    label.__wbRich = true;
    group.append(label);
    svg.append(group);
    window.renderMarkdown && 0;
    rich.paint(group, label, { cx: 100, cy: 60, w: 200, h: 120 }, 14);
    const clone = group.cloneNode(true);
    rich.exportInto(group, clone);
    return {
      fo: clone.querySelectorAll('foreignObject').length,
      labels: clone.querySelectorAll('.sketch-label').length,
      xml: new XMLSerializer().serializeToString(clone),
      text: clone.querySelector('text') ? clone.querySelector('text').textContent : '',
      bold: [...clone.querySelectorAll('tspan[font-weight="700"]')].map((t) => t.textContent),
      italic: [...clone.querySelectorAll('tspan[font-style="italic"]')].map((t) => t.textContent),
      xs: [...clone.querySelectorAll('tspan[x]')].map((t) => Number(t.getAttribute('x'))),
      ys: [...clone.querySelectorAll('tspan[y]')].map((t) => Number(t.getAttribute('y'))),
    };
  }, { code: payload.code, text: payload.text });
  console.log(JSON.stringify(out));
  await browser.close();
})();
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs node")
def test_a_rich_label_exports_as_drawn_words_not_markdown(tmp_path):
    payload = tmp_path / "payload.json"
    md = "**bold** and *italic* [site](https://example.com)\n\n- one\n    - nested\n- two\n\n<script>alert(1)</script>"
    payload.write_text(json.dumps({"js": str(JS) + "/", "code": STUBS + frontend_text("whiteboard-label-rich.js"), "text": md}), encoding="utf-8")
    path = tmp_path / "export.js"
    path.write_text(_EXPORT_PAGE, encoding="utf-8")
    run = subprocess.run(
        ["node", str(path), str(payload)], capture_output=True, text=True,
        env={"NODE_PATH": "/opt/node22/lib/node_modules", "PLAYWRIGHT_BROWSERS_PATH": "/opt/pw-browsers", "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/node22/bin", "HOME": str(tmp_path)},
    )
    if "Executable doesn't exist" in run.stderr or "Cannot find module" in run.stderr:
        pytest.skip("needs playwright and its browser")
    assert run.returncode == 0, run.stderr
    got = json.loads(run.stdout)
    assert got["fo"] == 0 and got["labels"] == 0, "no foreignObject and no raw-source text in the picture"
    assert "**" not in got["text"] and "](" not in got["text"] and "*italic*" not in got["text"], got["text"]
    assert got["bold"] == ["bold"] and got["italic"] == ["italic"], got
    assert "site" in got["text"], "a link is drawn as its words"
    assert got["text"].count("•") == 3, "three bullets"
    assert len(set(got["ys"])) == len(got["ys"]) and got["ys"] == sorted(got["ys"]), "one row per line, top to bottom"
    assert "<script" not in got["xml"], "the script words are text, never an element"
    assert max(got["xs"]) > min(got["xs"]), "the nested item is indented"


def test_a_list_in_a_quote_does_not_shift_the_depths_around_it(tmp_path):
    got = _browser(tmp_path, {"q": "> - quoted\n\n- a\n  - b\n    - c"})["q"]
    assert got["indented"] == 2, got["html"]
