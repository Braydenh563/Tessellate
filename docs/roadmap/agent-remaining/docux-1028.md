# docux-1028 (agent branch agent/docux-1028)

Done (one commit, see git log): U7 monospace code (library-lazy.css), U8 blank doc opens in Edit on phone (showNoDocument, setDocView persist option), U10 Image picker plus /media/upload (docImagePick), U11 menu rename plus Numbered list moved, U43 find panel on radius-md with 24px/44px close (moved from 09-editor.css to library-lazy.css, boot CSS down), D7 windowed prose pass (docProseWindow, 30,000 chars).

Measured (sandbox Chromium, 100,800 chars, renderDocProse): before 49 to 97 ms (median 75), after 10 to 12 ms. Close button 24x24 desktop, 44x44 touch. Code .cm-content/.cm-gutters/.cm-line resolve to ui-monospace stack.

Remaining:
- D7 windowing covers rules, spelling, grammar and accessibility; docAiFindings still scans the whole text (cheap string search). Window edge findings across a fence were guarded but not swept on a fence-heavy fixture.
- U43 tick checkboxes (input.library-card-tick, input.doc-list-tick, 3.2px) are not in this brief's scope and were not touched.
- U8 not verified on a template-made document (those are non-empty and keep the stored view).
- Image alt text for a pasted image path (paste of image data into the doc) is not wired; only the Image menu uses the picker.
