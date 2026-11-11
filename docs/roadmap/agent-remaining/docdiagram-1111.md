# docdiagram-1111 remaining

Branch of claude/pr216-wb, port 8788, owner items 2026-11-11 (diagram in Documents).
- done: item 1 (foot outside the scroller `.dgm-scroll`, pane hugs content; overlap 15 to 0 px, gap 82 to 1 px at 1440 and 1920), item 2 (offer is a `.notice`, one row 42 px wide, words wrap before buttons), item 3 (Expand and Collapse in both toolbars through the embed dialog with the document's io; scroll of list, picture and page put back; focus returns to Expand), help parity (diagram-reading topic, document controls popover), tests/test_diagram_doc_expand_1111.py
- next: none open for the three items
- found, not fixed: at 500 to 760 wide the offer row is 54 px, not 42, because the touch-size button minimum (44 px) applies; the offer also shows inside the expanded dialog; below 300 px wide the row's words and buttons overflow
