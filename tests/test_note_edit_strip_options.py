"""The note edit form's formatting strip is a clone of the capture strip. The
colour selects carry their options into the clone, so wiring the clone must
clear them first or each colour is listed twice (measured in Chromium with
`scratchpad/ui-sweeps/editstrip.js`: 17 options on the clone, 9 on the source).
"""

from tests._app_js import documents_text



def test_wiring_a_cloned_strip_clears_the_colour_options_first():
    text = documents_text()  # moved into the documents pieces (L-documents-117)
    clear = "for (const old of [...select.options]) if (old.value) old.remove();"
    add = "select.appendChild(option);"
    assert text.count(clear) == 1
    assert text.index(clear) < text.index(add, text.index(clear))
