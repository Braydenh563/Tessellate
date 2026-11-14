"""Audit 1028 D35: a document that cannot be fetched says so and the list
goes back to the document still on screen, instead of returning silently."""
from tests._app_js import documents_text


def test_a_failed_fetch_toasts_and_repaints_the_list() -> None:
    text = documents_text()
    start = text.index("async function openDocument(id)")
    body = text[start : start + 4000]
    #: L-documents-47 starts the fetch before the editor bundle and awaits it after; the failure check still follows the awaited result.
    assert "const fetching = apiJson(`/documents/${id}`).catch(() => null);" in body
    fetch = body.index("const doc = await fetching;")
    after = body[fetch : fetch + 600]
    assert "if (!doc) {" in after
    assert "toast(" in after and "renderDocList()" in after
    assert "if (!doc || seq" not in after
