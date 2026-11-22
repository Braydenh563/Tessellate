"""The printed manual, as a PDF Chromium makes from it (LEDGER L915).

The manual's `@media print` block (`manual-lazy.css`) exists because the app
shell is a viewport-high box with its overflow hidden, so the printer once got
the first 900 px and nothing past it (owner, 2026-10-12: "only prints one
page"). `test_manual_parity.py` reads the CSS; this prints it. A page shaped
like the app (a clipped shell, a fixed overlay, the manual's own classes and
its real stylesheet) is saved as a PDF: it must run to several pages, carry
the last topic, and carry none of the shell. Skipped where Playwright and its
browser are not installed, as the other browser-backed tests here are.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CSS = (ROOT / "frontend" / "css" / "manual-lazy.css").read_text(encoding="utf-8")
TOPICS = 40
LAST = f"Topic {TOPICS} closing line"

#: The app's own clipping, reduced to the rules that cut the old print off.
SHELL_CSS = """
html, body { height: 100%; margin: 0; overflow: hidden; }
body.modal-open { overflow: hidden; }
.app-shell { height: 100vh; overflow: hidden; }
.modal-overlay { position: fixed; inset: 0; overflow: hidden; display: flex; background: rgba(0,0,0,.4); }
.modal-card { max-height: 90vh; overflow: auto; display: flex; flex-direction: column; }
"""


def _page() -> str:
    topics = "".join(
        f'<article class="manual-topic"><h4>Topic {n}</h4>'
        + "".join(f"<p>Topic {n} paragraph {p}: " + "words that fill a line of the page " * 8 + "</p>" for p in range(4))
        + f"<p>{LAST if n == TOPICS else ''}</p></article>"
        for n in range(1, TOPICS + 1)
    )
    return (
        f"<style>{SHELL_CSS}{CSS}</style>"
        '<body class="modal-open"><div class="app-shell">The app shell: SHELLONLY marker</div>'
        '<div class="modal-overlay manual-overlay"><div class="card modal-card manual-card">'
        '<div class="dialog-head"><span class="dialog-head-actions"><button>Print</button></span></div>'
        '<div class="manual-body"><nav class="manual-contents">Contents</nav>'
        f'<div class="manual-topics"><section class="manual-group"><h3>Group</h3>{topics}</section></div>'
        "</div></div></div></body>"
    )


def _print_to_pdf(tmp_path: Path) -> bytes:
    pdf = tmp_path / "manual.pdf"
    script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setContent({json.dumps(_page())});
  await page.evaluate(() => document.body.classList.add('manual-print'));
  await page.pdf({{ path: {json.dumps(str(pdf))}, format: 'A4' }});
  await browser.close();
}})().catch((e) => {{ console.error(String(e)); process.exit(1); }});
"""
    node = shutil.which("node") or "/opt/node22/bin/node"
    run = subprocess.run(
        [node, "-e", script], capture_output=True, text=True, timeout=90,
        env={"NODE_PATH": "/opt/node22/lib/node_modules", "PLAYWRIGHT_BROWSERS_PATH": "/opt/pw-browsers",
             "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/node22/bin", "HOME": str(tmp_path)},
    )
    if "Executable doesn't exist" in run.stderr or "Cannot find module" in run.stderr or not Path(node).exists():
        pytest.skip("needs playwright and its browser")
    assert run.returncode == 0, run.stderr[-1500:]
    return pdf.read_bytes()


def test_the_manual_prints_every_topic_over_several_pages_and_none_of_the_shell(tmp_path):
    data = _print_to_pdf(tmp_path)
    pages = len(re.findall(rb"/Type\s*/Page[^s]", data))
    #: 40 topics of about 3.5 lines of 8 sentences each is far more than one A4 page: the old
    #: clipped print gave 1 (measured on the shell without the print block).
    assert pages >= 5, f"the manual printed {pages} pages"
    pdftotext = shutil.which("pdftotext")
    if pdftotext:
        (tmp_path / "m.pdf").write_bytes(data)
        text = subprocess.run([pdftotext, "-layout", str(tmp_path / "m.pdf"), "-"], capture_output=True, text=True, check=True).stdout
        assert LAST in text, "the last topic was cut off"
        assert "SHELLONLY" not in text, "the app shell was printed"
        assert "Contents" not in text, "the contents column was printed"


def test_without_the_print_block_the_shell_clips_the_print(tmp_path):
    """The check's own control: the same page with the print rules removed
    prints the old one page, so the test above can fail."""
    global CSS
    kept = CSS
    try:
        CSS = re.sub(r"@media print \{.*\}\s*$", "", CSS, flags=re.S)
        data = _print_to_pdf(tmp_path)
    finally:
        CSS = kept
    assert len(re.findall(rb"/Type\s*/Page[^s]", data)) < 5
