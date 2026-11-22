"""The map's find bar reads a topic's note (MINDMAP gap 13, OPEN F3).

Driven in Chromium 2026-11-10: a map topic "Alpha" given the note "Remember the zebra crossing", Find "zebra": 0 matches before, 1 after
(`wbSearchTextFor` returned "alpha" before and "alpha\\nremember the zebra crossing" after).
"""

from tests._app_js import frontend_text

WB = frontend_text("whiteboard.js")


def test_an_object_search_text_ends_with_its_note():
    start = WB.index("function wbSearchTextFor(")
    body = WB[start : start + 2400]
    assert 'const note = typeof data.note === "string" ? `\\n${data.note}` : "";' in body
    assert "${wbPropsText(data.props)}${note}`.toLowerCase()" in body


def test_replace_all_rewrites_a_topic_note():
    # Intent moved (owner, F3 line in s9c-1110: "Replace all does not rewrite topic notes"): Find reads a note, so Replace all writes it, in the same undo step.
    body = WB[WB.index("async function wbBoardReplaceAll") : WB.index("function wbBoardSearchRun")]
    assert "wbReplaceText(own.note" in body
    write = WB[WB.index("function wbReplaceWrite(") :]
    write = write[: write.index("\n}\n")]
    assert "note" in write


def test_replace_all_note_text_is_replaced_in_node():
    import json
    import shutil
    import subprocess

    node = shutil.which("node")
    if not node:
        return

    def fn(n):
        rest = WB[WB.index(f"function {n}(") :]
        return rest[: rest.index("\n}\n") + 3]

    script = (
        fn("wbSearchPattern") + fn("wbReplaceText") + fn("wbReplaceInProps")
        + "const wbSketchSetProps=()=>{};" + fn("wbReplaceWrite")
        + 'const it={data:{content:"a",note:"ship it, Ship"}};'
        + 'const t=wbReplaceText(it.data.content,"ship","send",{});'
        + 'const n=wbReplaceText(it.data.note,"ship","send",{});'
        + 'wbReplaceWrite("object",it,{text:t,values:{count:0},grid:{count:0},note:n});'
        + "console.log(JSON.stringify(it.data));"
    )
    out = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)
    assert out["note"] == "send it, send" and out["content"] == "a"
