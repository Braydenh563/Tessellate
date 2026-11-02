# imgread-1031 (INBOX 1484: an image alignment change read the picture again)

- Cause: `src/tessellate/core/media_process.py` `_due` treated a stored "" reading as unread and its only other guard (`_ASKED`, INBOX 1465) is in memory; `vision_ocr_and_store` and `pdf_vision_ocr_and_store` (`src/tessellate/ai/vision_ocr.py`) had the same falsy check.
- Done: NULL means never read, "" means read and found nothing; `tests/test_image_read_once.py`.
- Left: Tesseract (`core/ocr.py`) and captioning still re-run after a restart for a picture they found nothing in; both are cheap or write text, not changed.
- Not verified: the real vision model, the running app.
