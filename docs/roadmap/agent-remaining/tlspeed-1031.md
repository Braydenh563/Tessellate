# tlspeed-1031 remaining list

done: `/timeline` read at 5,000 notes measured and trimmed (placement joined once, link counts without note text); 19.5 s not reproduced.

Left:
- The 19.5 s at 4,602 notes is not in the endpoint: 20 ms over HTTP at 5,000 notes (listwin data copy and a seeded notebook with dates, links, meetings), 13 statements. Under concurrency requests queue on the GIL (24 at once finish in 640 ms, 26 ms each), so on a 4-core box at load 8 the Timeline's boot burst of requests is the likelier cause. Not verified in a browser.
- `_density` is the one O(notebook) read left (6 ms at 5,000 for the whole-range GROUP BY, repeated on every cursor page although the client ignores later pages' density). Dropping it from cursor pages changes the response, so it was left; `tests/test_timeline.py::test_a_page_still_carries_the_density_of_the_whole_range` pins the first page only.
- `GET /entries?limit=100` (10 statements, 3 note reads) and `/library` (22 statements, 210 notes clipped) are flat in notebook size at 5,000 notes; nothing to fix. `/library` `_clip` runs 12 regex subs per note (about 18 ms profiled over 210 notes).
- Seed and bench scripts are under /tmp/claude-0 (`tlspeed-seed.py`, `tlspeed-bench.py`, `tlspeed-http.py`), untracked.
