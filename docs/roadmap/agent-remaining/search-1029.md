# search-1029: remaining

Done: rank 16 (N1) and rank 17 (N2, N3, N4, N5, N16), see CHANGELOG [Unreleased].

- Rank 7, N13 (open): six endpoints give six note counts. Not started beyond reading. The definitions to reconcile: `/entries/count` (`routes_entries.py:2559`, every row incl. boards and bin), list `X-Total-Count` (`manager.count_entries`, `manager.py:398`, excludes bin and archived), `/diagnostics` (`routes_diag.py:45`, live minus boards, archived kept), `/statistics` (`ai/notebook_stats.py:_notebook_block`), `/categories` (sum of per-category counts), `/graph` nodes. Needs a decision first: are archived, draft and blank notes in "notes"? Then one `count_notes()` in `entry/manager.py` and a parametrised test over all six.
- `title:` and the new `notices` are served only by `/search`; the Notes list and Library parse operators on their own (`notes-list.js`, `ai/filters.py`), where an unknown `is:` value still matches nothing silently.
- `kind:` with an unknown kind is ignored without a notice (query.py has no list of kinds; `search/index.KINDS` would close an import edge).
- A word-boundary mention is ASCII-case-folded by the LIKE prefilter, so a non-ASCII title in a different case ("Ärger" vs "ärger") is still not a mention, as before.
- Link offers keep their own four-character floor (`OFFER_MIN_NAME_CHARS`, `test_link_offers.py::test_a_short_title_is_never_offered`).
