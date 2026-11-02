# submenu-1031 remaining

Done:
- 7f32056: INBOX 1470, an image press drags at once, a finger lifts a card after 350 ms, the drag yields to the long-press menu.
- 1233fd0: INBOX 1469, submenu rows nest as a level on narrow or touch, picture card 15 to 10 rows, Copy and arrange, Copy, History and export folds.

Next:
- Note card row menu is still 11 rows (`entryOverflowMenu`, frontend/js/menus.js): fold one more group or accept.
- Drive the 720 to 819 px popover case with a real pointer (stacked level there now, not driven).
- Real iOS and a real device for the touch lift (only CDP touch driven).
