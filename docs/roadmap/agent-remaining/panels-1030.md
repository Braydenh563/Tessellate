# panels-1030 remaining (INBOX 1454), branch agent/panels-1030

Done
- fea671a the grip is the card's last row, hung into the padding; 22 of 35 panels had a control under it, 0 now (1440x900 and 1024x768)
- next commit: double-click on the grip resets the size; stored entries are validated on open (fit check and `data-panel-layout`); head press keeps focus and selects nothing; the dim lifts as a drag starts; help text, DESIGN row, CHANGELOG

Remaining
- The grip costs about 12px of height per panel (28px row less the card's 16px bottom padding); a panel adopted by hover rather than by focus shifts by that much once. Measured none on the six panels in `MODE=feel` (they adopt at open); a panel with no focusable control is the case to look at.
- Dynamically built panels (confirm and prompt dialogs, anchored popups) are not in the static `MODE=overlap` list; only the 35 panels in index.html plus the real OCR workspace and Settings were measured.
- Resize is the bottom-right corner only; no edge or other-corner handles (the owner's "very unrefined" may want them).
- Light theme and a touch device were not swept.
