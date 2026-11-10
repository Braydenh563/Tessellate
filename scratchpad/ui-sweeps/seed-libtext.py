"""Give the seeded uploads the readings INBOX 279's screenshots show.

`seed-libtext.js` uploads the files; this writes what a vision model would
have written, because there is none in the sandbox and the shape under test is
the rendered card, not the inference. Two things go in:

* the images get a caption, a caption model, a vision reading and its model,
  which is every rank the image card's foot can carry;
* the PDFs get fourteen `page_reads` rows each, so `pages_read` is 14 and the
  joined reading is long enough for the Files block's word count to be a real
  number rather than a handful.

    python scratchpad/ui-sweeps/seed-libtext.py /tmp/mm-dens/memorymap.db
"""

import sqlite3
import sys

db = sys.argv[1] if len(sys.argv) > 1 else "/tmp/mm-dens/memorymap.db"
con = sqlite3.connect(db)

CAPTION = (
    "A printed notice board behind glass, listing opening hours and three "
    "membership rates in a serif face"
)
OCR = (
    "Rates and opening hours\n"
    "Monday to Friday, nine until six. Saturday, ten until four.\n"
    "Day rate twenty two pounds, week rate ninety, month rate two hundred and eighty.\n"
    "Members pay the week rate for a day pass on any weekday before noon."
)

PAGE = (
    "Section {n}. The rates in this handbook apply from the first of the month "
    "and are reviewed every spring. A member who joins part way through a month "
    "pays a pro rata share of the month rate, counted in whole days from the "
    "day the form is signed rather than from the first visit. Concessions are "
    "listed overleaf and are not cumulative: where two apply, the larger one is "
    "taken and the other is recorded but not charged against."
)

images = con.execute(
    "SELECT id, original_name FROM media_uploads WHERE original_name LIKE '%.png' ORDER BY id"
).fetchall()
for index, (media_id, name) in enumerate(images):
    # The third image is left bare on purpose: a card with nothing read is the
    # short foot the design has to keep short.
    if name.startswith("plain"):
        continue
    con.execute(
        "UPDATE media_uploads SET caption = ?, caption_model = ?, vision_ocr_text = ?, "
        "vision_ocr_model = ? WHERE id = ?",
        (CAPTION, "qwen3-vl:4b", OCR, "GLM-OCR-GGUF:Q8_0", media_id),
    )
    if index == 1:
        # One card with Tesseract's reading as well, which is the second box
        # inside the fold.
        con.execute(
            "UPDATE media_uploads SET ocr_text = ? WHERE id = ?",
            ("RATES AND OPENING HOURS\nMon-Fri 9-6  Sat 10-4", media_id),
        )

files = con.execute(
    "SELECT id FROM media_uploads WHERE original_name LIKE '%.pdf' ORDER BY id"
).fetchall()
for (media_id,) in files:
    con.execute("DELETE FROM page_reads WHERE kind = 'upload' AND source_id = ?", (media_id,))
    for page in range(1, 15):
        con.execute(
            "INSERT INTO page_reads (kind, source_id, page, reader, model, text, caption, "
            "caption_model, regions, created_at) VALUES ('upload', ?, ?, 'vision', ?, ?, '', '', '[]', "
            "datetime('now'))",
            (media_id, page, "qwen3-vl:4b", PAGE.format(n=page)),
        )

con.commit()
print(
    "images",
    len(images),
    "files",
    len(files),
    "page rows",
    con.execute("SELECT COUNT(*) FROM page_reads").fetchone()[0],
)
con.close()
