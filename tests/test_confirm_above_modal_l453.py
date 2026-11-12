"""L453: confirmDialog and promptDialog mount inside the open modal `<dialog>`.

A `showModal()` dialog sits in the top layer above the whole document and makes
everything outside it inert, so a confirm appended to `<body>` opened beneath
the dialog that asked it (and could not be pressed). The help popovers mount
inside the open dialog for the same reason (menus.js `wireHelpPopover`).
"""

from tests._app_js import frontend_text

APP = frontend_text("app.js")


def test_both_dialogs_mount_in_the_open_modal():
    host = APP[APP.index("confirmDialog.host = ") :][:200]
    assert "dialog:modal" in host
    assert APP.count("confirmDialog.host().appendChild(overlay)") == 2
    assert "document.body.appendChild(overlay)" not in APP[APP.index("function confirmDialog(") : APP.index("function wireBackdropClose(")]
