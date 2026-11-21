"""The parsers that run inside `core/parse_sandbox.py`'s child
(L-world-class-321): PDFium for a PDF's pages, markitdown for an Office file.

Called by name (``tessellate.core.parse_jobs:pdf_page``) from
`core/pdfpages.py` and `entry/importer.py`, never imported by the server for
its own use. Standard library at the top only, like `core/parse_child.py`,
so a cold child is not paying for the app's imports; arguments and answers
are plain data (str, int, bytes, None), because that is all the wire carries.
"""

from __future__ import annotations

import io


def pdf_page_count(path: str) -> int:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(path)
    try:
        return len(document)
    finally:
        document.close()


def pdf_page(path: str, index: int, greyscale: bool, scale: float, max_pixels: int) -> bytes | None:
    """One page as PNG bytes; None if the page is past the end or larger than
    `max_pixels` at `scale` (a 40 KB PDF can declare a page a metre wide)."""
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(path)
    try:
        if not 0 <= index < len(document):
            return None
        page = document[index]
        try:
            width, height = page.get_size()
            if (width * scale) * (height * scale) > max_pixels:
                return None
            image = page.render(scale=scale).to_pil()
        finally:
            page.close()
    finally:
        document.close()
    try:
        if greyscale:
            # Greyscale before PNG: a scanned page carries no colour worth
            # keeping for a vision model, and this is roughly a third of the
            # bytes for it to encode. The page *viewer* keeps colour.
            image = image.convert("L")
        buffer = io.BytesIO()
        #: **No recompression pass.** `optimize=True` was 340 of the 456 ms a
        #: page took (measured, a letter page at 2x) for 3% fewer bytes.
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        image.close()


def markdown(path: str) -> str:
    from markitdown import MarkItDown

    result = MarkItDown().convert(path)
    return (result.text_content or "").strip()
