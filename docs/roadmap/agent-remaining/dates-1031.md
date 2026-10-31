# dates-1031 (agent dates, branch agent/dates-1031)

Done: 0cb4e72 INBOX 1483: the say-when table leads with the relative time, "when did I" says the date then "about N ago", weekday names for this and last week, no ", from one of your notes" tail, typed faces (":D") dropped like emoji, the confirmed-fact line "..., as you told me on 11 October.", chips in the person's words ("my uni friend", "the bus").
Next: wider composer sweep (35 files), gate --changed; INBOX 1483 resolved to HISTORY.

Found, not fixed:
- "what's the latest on uni" answers with the July note, not the newest (8 October); composer_digest latest-shape pick, not dates.
- Timed-question day leads still say a bare date with no distance: `_heading_line` "On 8 October, " (composer_digest.py ~1725), `_dated_lead` "on {label}, ", the day line "On {date}, {body}." (~3444); `composer_lists._until` "was on 2 October, 9 days ago." (digits). Natural already, not bracketed; left for the owner's call.
- The model path's hints (`routes_chat._note_dates`, `_time_words`) are data, "Thursday 8 October 2026, 09:40" and '"today" meant ..., 23 days ago' (INBOX 441 keeps the exact count); no bracketed distance; a style rule for the model would cost prompt budget, so not added; real inference unverified.
