# docdiagram-1111 remaining

Branch of claude/pr216-wb, port 8788, owner items 2026-11-11 (diagram in Documents).
- done: item 1 (foot outside the scroller `.dgm-scroll`, the list column hugs its content; overlap 15 to 0 px, gap 82 to 0 px at 1440 and 1920), item 2 (offer is a `.notice`, one row of 42 px wide; words wrap before buttons; the pair drops under the words below about 24 rem; no overflow down to 240 px; not made in the expanded builder), item 3 (Expand and Collapse in all four toolbars through the embed dialog with the document's io; scroll of list, picture and page put back; focus returns to Expand; hidden under 600 px), help parity (Guide `diagram-lines`, document controls popover), tests/test_diagram_doc_expand_1111.py
- next: none open for the three items
- found, not fixed: at 500 to 760 px wide the offer row is 54 px, the 44 px touch minimum of its buttons (accepted, in the CHANGELOG line); below 200 px wide the offer still overflows; on the base branch three tests fail before this work (test_module_line_caps tool_read/tool_run, test_global_scope_ratchet 8563 over 8560, test_diagram_view_1614 LAZY_MODULES diagramView)
