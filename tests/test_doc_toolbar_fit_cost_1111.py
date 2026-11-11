"""A strip nobody can see is not fitted (INBOX 1716 lag log: `fitDocToolbarRow` 489 ms).

Fitting writes classes on the strip and then reads its width, so every call is a style recalculation and
a layout of the page. A window resize or a mode change fitted every strip, the hidden ones too, and with the
Library Images tab drawn (33,000 nodes) that was 242 ms over 8 calls at 4x CPU (max 120) against 33 to 41 ms
on a small page. A hidden strip is fitted when it is shown: the width observer sees it go from 0 to its width.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = (ROOT / "frontend" / "js" / "documents.js").read_text(encoding="utf-8")


def _fn(name: str, end: str = "\n}\n") -> str:
    body = DOCS[DOCS.index(f"function {name}("):]
    return body[: body.index(end)]


def test_a_hidden_strip_is_left_alone_before_any_write() -> None:
    fit = _fn("fitDocToolbarRow")
    first_write = min(i for i in (fit.index("classList.remove"), fit.index("more.hidden = true")))
    guard = fit.index("getClientRects().length")
    assert guard < first_write, "the visibility read comes before the first class write"
    assert "if (!bar.getClientRects().length) return;" in fit


def test_all_strips_are_checked_before_any_is_fitted() -> None:
    fit_all = _fn("fitDocToolbars")
    assert "getClientRects().length" in fit_all and "filter(" in fit_all, "reads first, so a hidden strip is not paid for the visible one's writes"


def test_a_mode_change_fits_each_strip_once() -> None:
    apply = _fn("applyDocToolbarMode")
    assert "fitDocToolbarRow(bar)" not in apply, "fitDocToolbars() at the end fits them, after the layout button moved"
    assert "fitDocToolbars();" in apply


def test_the_fold_is_one_batch_then_a_check() -> None:
    fit = _fn("fitDocToolbarRow")
    assert "docToolbarFoldFrom(lefts, row.left, row.right, edge)" in fit
    batch = fit.index("for (let i = items.length - 1; i >= from; i--) fold(items[i]);")
    rest = fit.index("for (let i = from - 1; i >= 0 && !fit")
    assert fit.index("const lefts = ") < batch < rest, "positions read once, folded together, then any still over one by one"
    assert "items[i].classList.add" not in fit, "no class write per item inside a loop that reads"


HARNESS = r"""
const src = require("fs").readFileSync(0, "utf8");
const fn = new Function(src + "; return docToolbarFoldFrom;")();
// The row the way the browser lays it out: items in a nowrap flex with a gap, the group after the last one.
// `old` is the loop it replaces: fold from the end, one at a time, until the group's right edge is inside.
let bad = 0, cases = 0, over = 0;
let seed = 12345;
const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
for (let n = 0; n < 4000; n++) {
  const count = 1 + Math.floor(rnd() * 24);
  const gap = Math.floor(rnd() * 8);
  const start = Math.floor(rnd() * 20);
  const widths = Array.from({ length: count }, () => (rnd() < 0.15 ? 0 : 16 + Math.floor(rnd() * 70)));
  const toolsWidth = 20 + Math.floor(rnd() * 120);
  const layout = (folded) => {
    let x = start, lefts = [];
    for (let i = 0; i < count; i++) {
      if (i >= folded || widths[i] === 0) { lefts.push(null); continue; }
      lefts.push(x); x += widths[i] + gap;
    }
    return { lefts, left: x, right: x + toolsWidth };
  };
  const edge = start + Math.floor(rnd() * 900);
  const full = layout(count);
  if (full.right <= edge + 0.5) continue;
  cases++;
  // old: the largest start whose fold leaves the group inside the edge (0 when none does)
  let real = 0;
  for (let f = count - 1; f >= 0; f--) if (layout(f).right <= edge + 0.5) { real = f; break; }
  // new: the batch start from the unfolded measurement; it may fold fewer than the loop (never more)
  const from = fn(full.lefts, full.left, full.right, edge);
  if (from < real) bad++;
  if (from > real + 1) over++;
}
console.log(JSON.stringify({ cases, bad, behind: over }));
"""


def test_the_batch_never_folds_more_than_the_one_by_one_loop() -> None:
    import json
    import re
    import subprocess

    src = re.search(r"function docToolbarFoldFrom\(.*?\n}\n", DOCS, re.S)
    assert src, "docToolbarFoldFrom is missing"
    done = subprocess.run(["node", "-e", HARNESS], input=src.group(0), capture_output=True, text=True, check=True, timeout=60)
    out = json.loads(done.stdout)
    assert out["cases"] > 1000, out
    assert out["bad"] == 0, f"the batch folded a tool the loop would have left: {out}"
    assert out["behind"] == 0, f"the batch stops at most one tool short of the loop: {out}"
