"""The log query scrub is linear in the line (sweep 1004).

`_PATH_QUERY` began a match at every slash and scanned to the end of the run
each time, so a line with a `?` early and a long run of slashes after it (an
error message that echoes a path) took quadratic time: 28,000 slashes took
2.4 s, on the thread that writes every log line.
"""

from __future__ import annotations

import time

from tessellate.core import logbuffer


def test_a_long_run_of_slashes_after_a_question_mark_is_not_quadratic():
    text = "what? " + "/" * 20_000
    started = time.process_time()
    assert logbuffer.scrub_query_strings(text) == text
    assert time.process_time() - started < 0.5


def test_the_same_lines_are_still_redacted():
    assert logbuffer.scrub_query_strings("GET /search?q=my+diagnosis&limit=5 HTTP/1.1") == (
        "GET /search?q=[redacted]&limit=5 HTTP/1.1"
    )
    assert logbuffer.scrub_query_strings("GET http://127.0.0.1:8888/a/b?q=x&q=y\" ok") == (
        "GET http://127.0.0.1:8888/a/b?q=[redacted]&q=[redacted]\" ok"
    )
    assert logbuffer.scrub_query_strings("Is it done? yes") == "Is it done? yes"
    assert logbuffer.scrub_query_strings("/x?a=1?b=2") == "/x?a=[redacted]"
