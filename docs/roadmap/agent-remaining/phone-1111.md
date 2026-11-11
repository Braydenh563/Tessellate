# phone-1111 (agent-a1287a4533587d634): remaining

Source: W12 navigation at 390 and the K18 left line. Measured at 390x844 touch (hasTouch, isMobile) and 1440x900, port 8782.

Done:
- W12 (99a6a6b59): Back (page.goBack and history.back) closed 1 of 10 phone overlays before, 10 of 10 after. The bottom-sheet branch of `routerCloseTopOverlay` clicked a `.sheet-close` the dialogs never have; it now clicks the dialog's own X from `OVERLAY_CLOSE_BUTTONS` (note history, connections, bin reader, skill run, board help, meeting, extract, OCR reader, Features, doc-ai). Test: `test_a_dialog_shown_as_a_phone_sheet_closes_by_its_own_x`.
- K18 left line: the `wb-show-captions` pref draws one muted line under a note's own pictures in the graph popup and in the timeline's note view (`imageLayout.caption`, `imageLayout.paintCaptions`; one cached `/media/meta/` lookup per picture; textContent only; attachments say nothing). The popup menu has Show or Hide picture captions. The Format panel's Library row held two buttons that wrapped onto a second line at 390 and at 1440; each now has its own row (Library, Captions). Help: `files-images` topic and the Format popover. Sweep: 18 of 18 at 390 and at 1440, including a pasted picture placed, board-only, and inside the window.

Left:
- The notes list card shows a `.thumb-wrap` thumbnail, not the full picture, so it carries no caption line (a thumbnail is a preview, not the picture).
- The on-screen `#status-back` is under the scrim while an overlay is open, so Back there is the browser's or the router's, not a tap target.
- Not verified: a real phone's hardware Back gesture (emulated with page.goBack and history.back only).
