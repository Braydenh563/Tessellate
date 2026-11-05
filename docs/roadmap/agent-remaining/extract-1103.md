# extract-1103 remaining (INBOX 1618)

Done: Extract notes with no model (heading off body, subject split, per-note filing and tags, no self link, honest message, help text).
Left:
- The same audit on the other no-model writers (summaries, titles, tidy): owner's "then the same audit", INBOX 1618, not started.
- Model path untouched: its notes carry no tags, and the commit route ignores `title` (src/tessellate/api/routes_entries.py:4300), so a de-headed note takes its title from its first line when saved.
- Not driven in a browser; checked through the API and unit tests only.
- INBOX 1618 stays open until the audit lands (`python scratchpad/inbox_resolve.py 1618` then).
