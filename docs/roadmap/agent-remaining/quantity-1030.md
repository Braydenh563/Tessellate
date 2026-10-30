# quantity-1030 remaining list (agent `quantity-1030`, branch agent/quantity-1030)

- done: steps 1 to 3 (money onto measures, status words of any quantity, differences); CHAT_PLAN row moved to HISTORY; fable-eye F1, F4, F5, F11, F12 fixed (marked in fable-eye-1030.md).
- open (CHAT_PLAN item 1): "X compared to Y" and "versus" are taken by `composer.compare_sides` before the digest (`composer_digest.py:3319` `_kind_if_mine`); a goal with no doing in the ask sums every distance; a difference with no unit, doing or comparative naming its dimension is declined.
- open (F12, second half): when a subject matches nothing the answer still says "no amounts spent on X", not the total with "I could not tell which were X".
- open (F1): the scan keeps the newest 400 hits (`composer_money.SCAN_HITS`); past that the oldest spending drops without a word.
- changed outside my files: `routes_chat.py:1691` (one line: the money scan calls `composer_money.recorded_notes`).
