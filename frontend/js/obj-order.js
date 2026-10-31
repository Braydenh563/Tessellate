// obj-order.js: the stored "Custom order" of a list and the arithmetic of a
// drop (INBOX 1467, part 2). Lazy, loaded by obj-ref.js. Pure except for the
// preference reads: obj-reorder.js owns the pointer and the page.
//
// A list's custom order is a list of object keys (`note:12`, `document:3`),
// kept as a preference beside the sort it joins (`notes-sort` and its kin are
// browser preferences in this app, so the order is too: the same lifetime as
// the choice that shows it). The order is **not** a copy of what was on
// screen: the screen can be a filtered or paged slice, so a drop rewrites only
// the places those items already held (`objMergeOrder`), and everything else
// keeps the place it had.

//: Rank of keys the stored order has never seen. Below every listed key, so a
//: new object appears at the top, where "newest first" would have put it.
const OBJ_UNLISTED = -1;
const OBJ_ORDER_LIMIT = 5000;

const objOrderCache = new Map();

function objOrderKey(scope) {
  return `order-${scope}`;
}

function objOrderLoad(scope) {
  return prefs.json(objOrderKey(scope), []).filter((key) => typeof key === "string");
}

function objOrderSave(scope, keys) {
  objOrderCache.delete(scope);
  return prefs.setJSON(objOrderKey(scope), keys.slice(0, OBJ_ORDER_LIMIT));
}

//: Where a key sits in a scope's stored order: its index, or `OBJ_UNLISTED`.
function objOrderRank(scope, key) {
  if (!objOrderCache.has(scope)) objOrderCache.set(scope, new Map(objOrderLoad(scope).map((k, i) => [k, i])));
  return objOrderCache.get(scope).get(key) ?? OBJ_UNLISTED;
}

//: A comparator for a list's sort table: `keyOf(item)` is the item's key.
function objOrderCmp(scope, keyOf) {
  return (a, b) => objOrderRank(scope, keyOf(a)) - objOrderRank(scope, keyOf(b));
}

//: `keys` with the one at `from` taken out and put at `to` (an index in the
//: list that remains, so `to` is where it ends up).
function objMoveKey(keys, from, to) {
  const out = keys.slice();
  const [moved] = out.splice(from, 1);
  out.splice(Math.max(0, Math.min(out.length, to)), 0, moved);
  return out;
}

//: The stored order after a drop. `before` and `after` are the visible keys
//: in screen order before and after the move (the same set). Items the stored
//: order lacks are added where they were on screen, then the places the
//: visible items hold are handed out again in the new order, so a slice's
//: reorder leaves every item that was off screen exactly where it was.
function objMergeOrder(stored, before, after) {
  const seen = new Set(stored);
  const full = stored.concat(before.filter((key) => !seen.has(key)));
  const shown = new Set(after);
  const slots = [];
  full.forEach((key, index) => shown.has(key) && slots.push(index));
  after.forEach((key, i) => (full[slots[i]] = key));
  return full;
}

//: Whether the rectangles lay out in more than one column, so "before" means
//: left of the middle rather than above it.
function objIsGrid(rects) {
  return rects.some((a, i) => rects.some((b, j) => i < j && a.top < b.bottom - 1 && b.top < a.bottom - 1));
}

//: Whether a pointer at (x, y) is on the leading side of a rectangle: above
//: the middle in a column of rows, left of it in a grid (and above or below it
//: when the pointer sits in the gap between grid rows).
function objBefore(r, x, y, grid) {
  if (!grid) return y < (r.top + r.bottom) / 2;
  if (y < r.top) return true;
  return y > r.bottom ? false : x < (r.left + r.right) / 2;
}

//: The index at which a dragged item would be inserted among `rects` (the
//: other items in order, 0 to n), for a pointer at (x, y): the nearest
//: rectangle decides, and the item goes before it or after it.
function objInsertIndex(rects, x, y) {
  let best = 0;
  let bestGap = Infinity;
  rects.forEach((r, i) => {
    const gap = Math.hypot(Math.max(r.left - x, 0, x - r.right), Math.max(r.top - y, 0, y - r.bottom));
    if (gap < bestGap) [best, bestGap] = [i, gap];
  });
  return rects.length && !objBefore(rects[best], x, y, objIsGrid(rects)) ? best + 1 : best;
}
