# wbcolour-1011 (agent remaining list)

Owner, 2026-10-11: whiteboard colours (recent row, fill and border together,
eyedropper), multi-select shared properties, more shapes and arrow options.

- [x] Step 1: arrow ends (open triangle, filled circle, crow's foot named; plain line takes ends; tool chooses the mark).
- [x] Step 2: more shapes in the shape flyout (whiteboard.js WB_FILLABLE_SHAPES ~1302, flyout index.html ~6955).
- [x] Step 3: colour popover: Recent row, palette, Fill/Border pair, Match, Swap, eyedropper (whiteboard-format.js).
- [x] Step 4: Format panel on a multi-selection: shared fields, Mixed state (whiteboard-format.js wbFormatSync).
- [x] Step 5: help (Guide topics, manual parity), DESIGN recipe, sweeps.

done: d6dc943f1 (step 1), c9712e1ab (step 2), steps 3 to 5 in one commit (the colour well and the Mixed state share wbFormatSync and wbWriteColourPair)
next: none; final report
