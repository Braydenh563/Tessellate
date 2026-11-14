"""Document comment threads, the browser model (audit 1102 DX24, audit 1028 D26).

The pure functions between `DOC-THREADS-BEGIN` and `DOC-THREADS-END` in
documents-comments.js run here in node, with the comment parser they build on.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "frontend" / "js" / "documents-comments.js"


def _region(text: str, begin: str, end: str) -> str:
    start = text.find(begin)
    stop = text.find(end)
    assert start != -1 and stop > start, f"{begin} / {end} markers missing"
    return text[start + len(begin) : stop]


DRIVER = r"""
const results = [];
const check = (name, ok, detail) => results.push({ name, ok: Boolean(ok), detail: String(detail || '') });
let n = 0;
const ids = () => `t${++n}`;
const NOW = '2026-11-02T09:00:00+00:00';
const LATER = '2026-11-02T10:00:00+00:00';
const stamp = (at = NOW) => ({ author: 'Sam', at, id: ids });
const parse = (t) => docCommentsParse(t);
const apply = (t, e) => t.slice(0, e.from) + e.insert + t.slice(e.to);

// --- keys: the text hash, and the place among remarks that say the same ----
{
  const c = parse('a %%same%% b %%same%% c %%other%%');
  const k = docThreadKeys(c);
  check('keys/one per remark', k.length === 3, k);
  check('keys/the same words differ by place', k[0] !== k[1] && k[0].split('.')[0] === k[1].split('.')[0], k);
  check('keys/other words other hash', k[2].split('.')[0] !== k[0].split('.')[0], k);
}

// --- reconcile -----------------------------------------------------------
{
  const text = 'The ==fox== %%too vague%% ran. %%ask Sam%%';
  const first = docThreadsReconcile([], parse(text), stamp());
  check('reconcile/a record per remark', first.threads.length === 2, first.threads.length);
  check('reconcile/stamped', first.threads[0].author === 'Sam' && first.threads[0].at === NOW, JSON.stringify(first.threads[0]));
  check('reconcile/changed says so', first.changed === true, '');
  check('reconcile/by comment id', first.byComment['c' + parse(text)[0].from].text === 'too vague', '');
  const again = docThreadsReconcile(first.threads, parse(text), stamp(LATER));
  check('reconcile/stable on a second pass', again.changed === false && again.threads.length === 2, again.changed);
  check('reconcile/the first stamp is kept', again.threads[0].at === NOW, again.threads[0].at);
  // a rename of the words around a remark changes nothing
  const renamed = 'Now the ==fox== %%too vague%% sat down. %%ask Sam%% and more';
  const after = docThreadsReconcile(first.threads, parse(renamed), stamp(LATER));
  check('reconcile/surrounding text can change', after.changed === false && after.threads[0].id === first.threads[0].id, '');
}
{
  // legacy remarks load with no author and no time; nothing is claimed
  const r = docThreadsReconcile([], parse('a %%old%%'), { author: '', at: '', id: ids });
  check('legacy/no author', r.threads[0].author === '' && r.threads[0].at === '', JSON.stringify(r.threads[0]));
}
{
  // editing a remark keeps its replies
  const t0 = docThreadsReconcile([], parse('see %%tpyo%%'), stamp()).threads;
  const t1 = docThreadReply(t0, t0[0].id, 'Sam', LATER, 'which one?');
  const edited = docThreadsReconcile(t1, parse('see %%typo here%%'), stamp(LATER));
  check('edit/the thread follows the edited remark', edited.threads.length === 1 && edited.threads[0].replies.length === 1 && edited.threads[0].text === 'typo here', JSON.stringify(edited.threads));
}
{
  // a remark deleted by hand: a thread with replies is kept (resolved), one without goes
  const t0 = docThreadsReconcile([], parse('a %%one%% b %%two%%'), stamp()).threads;
  const t1 = docThreadReply(t0, t0[0].id, 'Sam', LATER, 'yes');
  const gone = docThreadsReconcile(t1, parse('a b'), stamp(LATER));
  check('deleted/replies are never lost', gone.threads.length === 1 && gone.threads[0].resolved === true && gone.threads[0].replies.length === 1, JSON.stringify(gone.threads));
}
{
  // two remarks that say the same keep their own threads
  const t0 = docThreadsReconcile([], parse('%%dup%% x %%dup%%'), stamp()).threads;
  const t1 = docThreadReply(t0, t0[1].id, 'Sam', LATER, 'second');
  const re = docThreadsReconcile(t1, parse('%%dup%% x %%dup%%'), stamp(LATER));
  check('dups/each keeps its own', re.byComment['c' + parse('%%dup%% x %%dup%%')[1].from].replies.length === 1 && re.byComment['c0'].replies.length === 0, '');
}

// --- reply -----------------------------------------------------------------
{
  const t0 = docThreadsReconcile([], parse('a %%b%%'), stamp()).threads;
  const t1 = docThreadReply(t0, t0[0].id, 'Sam', LATER, '  thanks  ');
  check('reply/trimmed, stamped, appended', t1[0].replies.length === 1 && t1[0].replies[0].text === 'thanks' && t1[0].replies[0].at === LATER, JSON.stringify(t1[0].replies));
  check('reply/the input is not changed', t0[0].replies.length === 0, '');
  check('reply/empty is refused', docThreadReply(t0, t0[0].id, 'Sam', LATER, '   ') === t0, '');
}

// --- edit and delete a reply (L318) --------------------------------------------
{
  const t0 = docThreadsReconcile([], parse('a %%b%%'), stamp()).threads;
  const t1 = docThreadReply(docThreadReply(t0, t0[0].id, 'Sam', LATER, 'one'), t0[0].id, 'Sam', LATER, 'two');
  const edited = docThreadEditReply(t1, t1[0].id, 0, '  uno ');
  check('edit/the words change, trimmed, the stamp stays', edited[0].replies[0].text === 'uno' && edited[0].replies[0].at === LATER && edited[0].replies[1].text === 'two', JSON.stringify(edited[0].replies));
  check('edit/the input is not changed', t1[0].replies[0].text === 'one', '');
  check('edit/empty words are refused', docThreadEditReply(t1, t1[0].id, 0, '  ') === t1, '');
  check('edit/an index that is not there is refused', docThreadEditReply(t1, t1[0].id, 5, 'x') === t1, '');
  const gone = docThreadDeleteReply(t1, t1[0].id, 0);
  check('delete/one reply goes, the other stays', gone[0].replies.length === 1 && gone[0].replies[0].text === 'two', JSON.stringify(gone[0].replies));
  check('delete/an index that is not there is refused', docThreadDeleteReply(t1, t1[0].id, 9) === t1, '');
  const kept = docThreadsReconcile(docThreadDeleteReply(docThreadDeleteReply(t1, t1[0].id, 0), t1[0].id, 0), parse('a b'), stamp(LATER));
  check('delete/a thread whose replies are all gone is dropped with its deleted remark', kept.threads.length === 0, JSON.stringify(kept.threads));
}
{
  // a reply on a resolved thread is kept like any other
  const t0 = docThreadsReconcile([], parse('a %%b%%'), stamp()).threads;
  const resolved = [{ ...t0[0], resolved: true, resolved_at: LATER }];
  const t1 = docThreadReply(resolved, resolved[0].id, 'Sam', LATER, 'later note');
  check('resolved/takes a reply and stays resolved', t1[0].resolved === true && t1[0].replies.length === 1, JSON.stringify(t1[0]));
}

// --- resolve and reopen ------------------------------------------------------
function roundTrip(text, which = 0) {
  const comments = parse(text);
  const t0 = docThreadsReconcile([], comments, stamp()).threads;
  const comment = comments[which];
  const rec = t0.find((t) => t.key === docThreadKeys(comments)[which]);
  const resolved = docThreadResolve(t0, rec.id, comment, text, LATER);
  const edit = docCommentResolveEdit(text, comment);
  const gone = apply(text, edit);
  const rec2 = resolved.find((t) => t.id === rec.id);
  const back = apply(gone, docThreadReopenEdit(gone, rec2));
  return { gone, back, rec2, resolved };
}
{
  const r = roundTrip('The ==quick fox== %%too many adjectives%% jumped.');
  check('resolve/the record is kept as resolved', r.rec2.resolved === true && r.rec2.resolved_at === LATER && r.rec2.target === 'quick fox', JSON.stringify(r.rec2));
  check('reopen/the highlight and remark return', r.back === 'The ==quick fox== %%too many adjectives%% jumped.', r.back);
}
{
  const r = roundTrip('One.\n%%a standing note%%\nTwo.');
  check('resolve/own-line flag', r.rec2.own === true, r.rec2.own);
  check('reopen/a standing remark returns to its own line', r.back === 'One.\n%%a standing note%%\nTwo.', JSON.stringify(r.back));
}
{
  const r = roundTrip('A sentence %%a remark%% and more.');
  check('reopen/an inline bare remark returns to the end of its line', r.back === 'A sentence and more. %%a remark%%', JSON.stringify(r.back));
}
{
  const r = roundTrip('The ==quick fox== %%too many%% jumped.');
  const changed = 'A new first paragraph.\n\nThe quick fox jumped, twice.';
  const back = apply(changed, docThreadReopenEdit(changed, r.rec2));
  check('reopen/finds the words after the text moved', back === 'A new first paragraph.\n\nThe ==quick fox== %%too many%% jumped, twice.', JSON.stringify(back));
  const lost = 'Entirely rewritten.';
  const back2 = apply(lost, docThreadReopenEdit(lost, r.rec2));
  check('reopen/the words are gone: the remark still returns', back2.includes('%%too many%%'), JSON.stringify(back2));
}
{
  const r = roundTrip('Fence:\n```\nthe ==code== here\n```\nThe ==code== %%note%% again');
  check('reopen/never inside a code fence', r.back === 'Fence:\n```\nthe ==code== here\n```\nThe ==code== %%note%% again', JSON.stringify(r.back));
}
{
  // reopened, it reconciles back onto the same thread
  const text = 'The ==fox== %%vague%% ran.';
  const comments = parse(text);
  const t0 = docThreadsReconcile([], comments, stamp()).threads;
  const t1 = docThreadReply(t0, t0[0].id, 'Sam', LATER, 'agreed');
  const t2 = docThreadResolve(t1, t1[0].id, comments[0], text, LATER);
  const gone = apply(text, docCommentResolveEdit(text, comments[0]));
  const t3 = docThreadReopen(t2, t2[0].id);
  const back = apply(gone, docThreadReopenEdit(gone, t3[0]));
  const re = docThreadsReconcile(t3, parse(back), stamp(LATER));
  check('reopen/reconcile adopts the returning remark', re.threads.length === 1 && re.threads[0].id === t0[0].id && re.threads[0].resolved === false && re.threads[0].replies.length === 1, JSON.stringify(re.threads));
}

{
  // Ctrl+Z after Resolve: the remark returns and so does its thread
  const text = 'The ==fox== %%vague%% ran.';
  const comments = parse(text);
  const t0 = docThreadsReconcile([], comments, stamp()).threads;
  const t1 = docThreadReply(t0, t0[0].id, 'Sam', LATER, 'agreed');
  const t2 = docThreadResolve(t1, t1[0].id, comments[0], text, LATER);
  const soon = docThreadsReconcile(t2, parse(text), stamp('2026-11-02T10:05:00+00:00'));
  check('undo/the resolved thread comes back with its replies', soon.threads.length === 1 && soon.threads[0].id === t0[0].id && soon.threads[0].resolved === false && soon.threads[0].replies.length === 1, JSON.stringify(soon.threads));
  const late = docThreadsReconcile(t2, parse(text), stamp('2026-11-04T10:00:00+00:00'));
  check('undo/the same words next week are a new thread', late.threads.length === 2 && late.threads.filter((t) => t.resolved).length === 1, JSON.stringify(late.threads.map((t) => [t.id, t.resolved])));
  const load = docThreadsReconcile(t2, parse(text), { author: '', at: '', id: ids });
  check('undo/opening a document never reopens a thread', load.threads.filter((t) => !t.resolved).length === 1 && load.threads.length === 2, load.threads.length);
}

process.stdout.write(JSON.stringify(results));
"""


@pytest.fixture(scope="module")
def thread_checks(tmp_path_factory) -> list[dict]:
    node = shutil.which("node")
    if not node:  # pragma: no cover - node is in the sandbox and in CI
        pytest.skip("node is not available")
    source = JS.read_text(encoding="utf-8")
    model = _region(source, "// DOC-COMMENT-BEGIN", "// DOC-COMMENT-END") + _region(
        source, "// DOC-THREADS-BEGIN", "// DOC-THREADS-END"
    )
    script = tmp_path_factory.mktemp("docthreads") / "run.js"
    script.write_text(model + DRIVER, encoding="utf-8")
    out = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_thread_model_runs_without_a_browser(thread_checks):
    assert len(thread_checks) > 20, "the driver did not reach the end"


def test_threads_reconcile_reply_resolve_and_reopen_as_decided(thread_checks):
    failed = [c for c in thread_checks if not c["ok"]]
    assert not failed, "\n".join(f"{c['name']}: {c['detail']}" for c in failed[:20])


def test_reply_edit_delete_and_resolved_reply_are_wired_into_the_panel() -> None:
    """L318: the model functions have call sites, and a resolved row offers Reply."""
    text = JS.read_text(encoding="utf-8")
    assert "docThreadEditReply(docThreads" in text and "docThreadDeleteReply(before" in text
    assert 'smallButton("ph:pencil-simple", "Edit this reply"' in text
    assert 'smallButton("ph:trash", "Delete this reply"' in text
    resolved = text.split("function docResolvedRow(")[1].split("function docCommentsShell")[0]
    assert "docCommentReplyForm(thread)" in resolved and '"Reply to this comment"' in resolved


def test_reply_form_offers_attach_and_replies_draw_markdown() -> None:
    """L332: the board's Attach, on a document reply (the picker's pick written as markdown)."""
    text = JS.read_text(encoding="utf-8")
    form = text.split("function docCommentReplyForm(")[1].split("function docCommentRow")[0]
    assert 'smallButton("ph:paperclip", "Attach a bookmark, note, document or board"' in form
    assert "pickLibraryItemDialog(" in form and "docReplyAttachMarkdown(chosen)" in form
    assert "function docReplyAttachMarkdown(" in text
    replies = text.split("function docThreadReplies(")[1].split("function docCommentReplyForm")[0]
    assert "renderMarkdown(said, reply.text)" in replies
