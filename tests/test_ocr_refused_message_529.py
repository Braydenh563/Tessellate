"""A Read that cannot run says why on the page, not only in a toast (L529).

Found driving the OCR workspace: on a PDF page with no reader, Read's press went
through `ocrRefusedPress`, which only toasted, so `#ocr-message` stayed empty
while a picture's press wrote it (ocr717.js "a read that cannot run says what
to do", 1440 and 390).
"""
import re
from pathlib import Path

# library.js is fetched with the Library, after the boot scripts app_js_text reads.
LIBRARY = Path(__file__).resolve().parents[1] / "frontend" / "js" / "library.js"


def _body(name: str) -> str:
    js = LIBRARY.read_text(encoding="utf-8")
    start = js.index(f"function {name}(")
    end = js.index("\n}\n", start)
    return js[start:end]


def test_a_refused_read_writes_the_message_line():
    body = _body("ocrRefusedPress")
    assert re.search(r'\$\("ocr-message"\)\.textContent\s*=\s*button\.title', body), body
    assert 'classList.remove("hidden")' in body, body
