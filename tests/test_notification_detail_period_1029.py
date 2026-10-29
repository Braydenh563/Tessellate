"""A notification's detail never ends a sentence twice (audit 1029 X18, rank 61).

The embedding notice was built as `${error}. Settings, Models ...`, so an error
that already ended in a period read "..." and ".." in the bell.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

from tests._app_js import JS_DIR

pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="needs node")


def _run(function: str, argument: str) -> str:
    source = (JS_DIR / "status.js").read_text(encoding="utf-8")
    parts = []
    for name in ("withoutEndStop", function):
        match = re.search(rf"^function {name}\(.*?^\}}", source, re.S | re.M)
        assert match, f"{name} is gone from status.js"
        parts.append(match.group(0))
    script = (
        'const EMBEDDING_FALLBACK_MODEL = "nomic-embed-text";\n'
        + "\n".join(parts)
        + f"\nprocess.stdout.write({function}({json.dumps(argument)}));"
    )
    return subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True).stdout


@pytest.mark.parametrize("error", ["The package is missing.", "The package is missing", "The package is missing. ", "The package is missing..."])
def test_the_embedding_detail_has_one_stop_whatever_the_error_ends_with(error):
    detail = _run("embeddingProblemDetail", error)
    assert detail.startswith("The package is missing. Settings, Models can switch it to nomic-embed-text")
    assert ".." not in detail


def test_a_sentence_keeps_a_question_mark_and_an_ellipsis_character():
    assert _run("withoutEndStop", "Is it there?") == "Is it there?"
    assert _run("withoutEndStop", "Loading…") == "Loading…"
    assert _run("withoutEndStop", "  done.  ") == "done"


def test_the_notice_uses_the_one_builder():
    source = (JS_DIR / "status.js").read_text(encoding="utf-8")
    assert "embeddingProblemDetail(error)" in source
    assert "`${error}. Settings, Models" not in source
