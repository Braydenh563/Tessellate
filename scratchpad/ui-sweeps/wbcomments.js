// WHITEBOARD_PLAN decision 17: a comment thread on a board item and a topic.
//
// A sticky, a note card and a rectangle on a board. The sticky's right-click
// menu offers "Comment…", which opens the thread beside it with the focus in
// the box; Enter posts, the Comment button posts, and the sticky wears a count
// mark up and right of its corner (clear of the resize handle), the number
// right. Escape closes; Ctrl+Z takes the last comment back; the mark opens the
// thread again and a trash button deletes one. The card's thread survives a
// fresh read; the mark follows the card through a drag and stays its screen
// size at 2x; a locked item's mark still takes the press; a shape takes one.
// On a map, a topic's menu offers it too. Contrast of the mark and the popover
// inside the window.
//
//   BASE=http://127.0.0.1:8809 SCRATCH=/tmp/x THEME=light VW=1440 VH=900 \
//   PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers node scratchpad/ui-sweeps/wbcomments.js
const { boot } = require("./lib.js");

let pass = 0;
let fail = 0;
function ok(label, good, detail) {
  if (good) pass += 1;
  else fail += 1;
  console.log(`${good ? "OK  " : "FAIL"} ${label}${detail ? "  " + detail : ""}`);
}
function lum([r, g, b]) {
  const f = (c) => {
    const v = c / 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
const ratio = (a, b) => {
  const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};
const rgb = (s) => {
  const parts = (String(s).match(/[\d.]+/g) || []).slice(0, 3).map(Number);
  return String(s).startsWith("color(srgb") ? parts.map((v) => v * 255) : parts;
};
const VW = Number(process.env.VW || 1440);
const VH = Number(process.env.VH || 900);
const S = VW < 600 ? 0.55 : 1;
const OY = VW < 600 ? 150 : 0;

(async () => {
  const phone = VW < 600;
  const { browser, page } = await boot({
    viewport: { width: VW, height: VH },
    ...(phone ? { hasTouch: true, isMobile: true } : {}),
  });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.evaluate(() => document.querySelector('[data-tab="library"]').click());
  await page.waitForTimeout(500);
  await page.evaluate(() => document.querySelector('[data-target="library-view-whiteboard"]').click());
  await page.waitForTimeout(700);
  const boardId = await page.evaluate(async () =>
    (await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `Comments sweep ${Date.now()}` }) })).id
  );
  await page.evaluate((bid) => openWhiteboardBoard(bid), boardId);
  await page.waitForTimeout(1500);
  await page.keyboard.press("Escape");

  const ids = await page.evaluate(async ([S, OY]) => {
    if (S < 1) d3.select("#whiteboard-container").call(wbZoom.transform, d3.zoomIdentity.scale(0.5));
    else d3.select("#whiteboard-container").call(wbZoom.transform, d3.zoomIdentity);
    const t = d3.zoomTransform(document.getElementById("whiteboard-container"));
    const at = (sx, sy) => [t.invertX(sx), t.invertY(sy)];
    const [sx, sy] = at(80 * S, 220 * S + OY);
    const sticky = await wbCreateObject("text", { content: "Talk", bg: "#fff4a3" }, sx, sy, (150 * S) / t.k, (100 * S) / t.k);
    const note = await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: "Comment sweep card" }) });
    const [cx, cy] = at(330 * S, 220 * S + OY);
    const card = await apiJson("/whiteboard/nodes", { method: "POST", body: JSON.stringify({ entry_id: note.id, board_id: window.currentBoardId, x: cx, y: cy, z: 1 }) });
    if (typeof allEntries !== "undefined" && !allEntries.some((e) => e.id === note.id)) allEntries.push(note);
    const [rx, ry] = at(120 * S, 420 * S + OY);
    const d = `M${rx},${ry} L${rx + 120},${ry} L${rx + 120},${ry + 70} L${rx},${ry + 70} Z`;
    const rect = await apiJson("/whiteboard/sketches", {
      method: "POST",
      body: JSON.stringify({ data: JSON.stringify({ d, color: "#333333", width: 2, shape: "rect" }), board_id: window.currentBoardId }),
    });
    await fetchWhiteboardState();
    renderWhiteboardNow();
    return { sticky: sticky.id, card: card.id, rect: rect.id };
  }, [S, OY]);
  await page.waitForTimeout(600);
  const stickySel = `.wb-object[data-id="${ids.sticky}"]`;
  const cardSel = `.node-card[data-id="${ids.card}"]`;

  const look = (kind, id) =>
    page.evaluate(([kind, id, sel]) => {
      const list = { node: "nodes", object: "objects", sketch: "sketches" }[kind];
      const item = wbState[list].find((i) => i.id === id);
      const pin = document.querySelector(`.wb-comment-pin[data-comment-key="${kind}:${id}"] .wb-comment-mark`);
      const r = pin?.getBoundingClientRect();
      const el = document.querySelector(sel);
      const er = el?.getBoundingClientRect();
      const panel = document.getElementById("wb-comments");
      const pr = panel?.getBoundingClientRect();
      return {
        count: wbItemComments(kind, item).length,
        mark: r ? { x: r.left + r.width / 2, y: r.top + r.height / 2, left: r.left, bottom: r.bottom, w: r.width, h: r.height, text: pin.textContent.trim() } : null,
        item: er ? { right: er.right, top: er.top } : null,
        panel: pr ? { left: pr.left, right: pr.right, top: pr.top, bottom: pr.bottom, rows: panel.querySelectorAll(".wb-comment").length, focus: panel.contains(document.activeElement) } : null,
      };
    }, [kind, id, kind === "sketch" ? `.sketch-group[data-id="${id}"] .sketch-path` : kind === "node" ? `.node-card[data-id="${id}"]` : `.wb-object[data-id="${id}"]`]);

  // 1. The sticky's menu.
  const sr = await page.evaluate((sel) => {
    const r = document.querySelector(sel).getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  }, stickySel);
  await page.mouse.click(sr.x, sr.y);
  await page.waitForTimeout(300);
  await page.mouse.click(sr.x, sr.y, { button: "right" });
  await page.waitForTimeout(400);
  const rows = await page.evaluate(() => [...document.querySelectorAll(".wb-ctx-menu:not(.hidden) .menu-item")].map((b) => b.textContent.trim()));
  ok("the item menu offers Comment…", rows.includes("Comment…"), JSON.stringify(rows));
  await page.evaluate(() => [...document.querySelectorAll(".wb-ctx-menu:not(.hidden) .menu-item")].find((b) => b.textContent.trim() === "Comment…")?.click());
  await page.waitForTimeout(400);
  let s = await look("object", ids.sticky);
  ok("the thread opens with the focus in its box", Boolean(s.panel?.focus), JSON.stringify(s.panel));
  ok("an empty thread opens on the box, the button hidden", await page.evaluate(() => !document.querySelector("#wb-comments .wb-comments-composer").hidden && document.querySelector("#wb-comments .wb-comments-new").hidden));
  await page.keyboard.type("Is this the final date?");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(700);
  //: INBOX 570: after a post the box folds back behind "New comment".
  const folded = await page.evaluate(() => ({
    composer: document.querySelector("#wb-comments .wb-comments-composer").hidden,
    focus: document.activeElement?.classList.contains("wb-comments-new"),
    name: document.querySelector("#wb-comments .wb-comments-new").textContent.trim(),
  }));
  ok("a post folds the box back to a focused New comment", folded.composer && folded.focus && folded.name === "New comment", JSON.stringify(folded));
  await page.keyboard.press("Enter");
  await page.waitForTimeout(200);
  ok("New comment opens the box, focused", await page.evaluate(() => document.activeElement?.classList.contains("wb-comments-box")));
  await page.keyboard.type("Not this one");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  const escaped = await page.evaluate(() => ({
    open: Boolean(document.getElementById("wb-comments")),
    composer: document.querySelector("#wb-comments .wb-comments-composer")?.hidden,
    focus: document.activeElement?.classList.contains("wb-comments-new"),
  }));
  ok("Escape in the box cancels it, the thread stays open", escaped.open && escaped.composer && escaped.focus, JSON.stringify(escaped));
  await page.evaluate(() => document.querySelector("#wb-comments .wb-comments-new").click());
  await page.waitForTimeout(150);
  ok("a cancelled draft is gone", await page.evaluate(() => document.querySelector("#wb-comments .wb-comments-box").value === ""));
  await page.evaluate(() => document.querySelector("#wb-comments .wb-comments-cancel").click());
  await page.waitForTimeout(150);
  ok("Cancel folds the box away", await page.evaluate(() => document.querySelector("#wb-comments .wb-comments-composer").hidden));
  await page.evaluate(() => document.querySelector("#wb-comments .wb-comments-new").click());
  await page.waitForTimeout(150);
  await page.keyboard.type("Second line");
  await page.evaluate(() => document.querySelector("#wb-comments .wb-comments-post").click());
  await page.waitForTimeout(700);
  s = await look("object", ids.sticky);
  ok("Enter and the Post button each post", s.count === 2 && s.panel?.rows === 2, JSON.stringify({ count: s.count, rows: s.panel?.rows }));
  ok("the sticky wears a mark that says 2", s.mark?.text === "2", JSON.stringify(s.mark));
  const corner = s.mark && s.item ? { dx: s.mark.left - s.item.right, dy: s.item.top - s.mark.bottom } : null;
  ok("the mark sits up and right of the corner, clear of it", corner && corner.dx >= 0 && corner.dx <= 10 && corner.dy >= 0 && corner.dy <= 10, JSON.stringify(corner));
  ok("the thread is inside the window", s.panel && s.panel.left >= 0 && s.panel.right <= VW && s.panel.top >= 0 && s.panel.bottom <= VH, JSON.stringify(s.panel));
  if (process.env.SHOT) await page.screenshot({ path: `${process.env.SCRATCH}/wbcomments-${VW}-${process.env.THEME || "light"}.png` });
  const typedKeysStayed =await page.evaluate((id) => wbState.objects.some((o) => o.id === id), ids.sticky);
  ok("typing in the thread did nothing to the board", typedKeysStayed);
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  s = await look("object", ids.sticky);
  ok("Escape closes the thread", !s.panel);
  await page.evaluate(() => document.getElementById("whiteboard-container").focus());
  await page.keyboard.press("Control+z");
  await page.waitForTimeout(800);
  s = await look("object", ids.sticky);
  ok("Ctrl+Z takes the last comment back", s.count === 1 && s.mark?.text === "1", JSON.stringify({ count: s.count, mark: s.mark?.text }));

  // 2. The mark opens it; the trash deletes.
  await page.mouse.click(s.mark.x, s.mark.y);
  await page.waitForTimeout(400);
  s = await look("object", ids.sticky);
  ok("the mark opens the thread", s.panel?.rows === 1, JSON.stringify(s.panel));
  await page.evaluate(() => document.querySelector("#wb-comments .wb-comment [aria-label=\"Delete this comment\"]").click());
  await page.waitForTimeout(800);
  s = await look("object", ids.sticky);
  ok("the trash deletes it and the mark goes", s.count === 0 && !s.mark, JSON.stringify(s));
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);

  // 2b. The owner, 2026-10-10: "there's no way to edit a comment"; links in
  // comments; replies and resolve. A link alone on a line is the link card;
  // Reply nests; Edit keeps the words and says "edited"; Resolve folds the
  // thread and the mark becomes a tick; "/" in the box opens the editor menu.
  await page.evaluate((id) => wbOpenComments("object", id), ids.sticky);
  await page.waitForTimeout(300);
  await page.keyboard.type("See the spec");
  await page.keyboard.press("Shift+Enter");
  await page.keyboard.type("https://example.com/specs/board-comments");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(700);
  let rr = await page.evaluate(() => {
    const row = document.querySelector("#wb-comments .wb-comment");
    const card = row?.querySelector(".link-card");
    return { card: Boolean(card), href: card?.getAttribute("href"), title: card?.querySelector(".link-card-title")?.textContent };
  });
  ok("a link alone on its line is drawn as the link card", rr.card && rr.href === "https://example.com/specs/board-comments", JSON.stringify(rr));
  await page.evaluate(() => document.querySelector('#wb-comments .wb-comment [aria-label="Reply"]').click());
  await page.waitForTimeout(200);
  rr = await page.evaluate(() => ({ replying: !document.querySelector("#wb-comments .wb-comments-replying").hidden, focus: document.activeElement?.id }));
  ok("Reply opens the box, saying what it answers", rr.replying && rr.focus === "wb-comments-box", JSON.stringify(rr));
  await page.keyboard.type("Agreed");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(700);
  rr = await page.evaluate((id) => {
    const thread = wbState.objects.find((o) => o.id === id).data.comments;
    const reply = document.querySelector("#wb-comments .wb-comment-reply");
    const top = document.querySelector("#wb-comments .wb-comment:not(.wb-comment-reply)");
    return { n: thread.length, replyTo: thread[1]?.reply_to === thread[0]?.id, indent: reply && top ? Math.round(reply.getBoundingClientRect().left - top.getBoundingClientRect().left) : null };
  }, ids.sticky);
  ok("the reply is kept against its comment and drawn one step in", rr.n === 2 && rr.replyTo && rr.indent >= 8, JSON.stringify(rr));
  await page.evaluate(() => document.querySelector('#wb-comments .wb-comment-reply [aria-label="Edit this comment"]').click());
  await page.waitForTimeout(200);
  rr = await page.evaluate(() => ({ focus: document.activeElement?.id, value: document.activeElement?.value }));
  ok("Edit opens the comment's own words, focused", rr.focus === "wb-comments-edit" && rr.value === "Agreed", JSON.stringify(rr));
  await page.keyboard.press("End");
  await page.keyboard.type(", with [[Comment sweep card]]");
  await page.waitForTimeout(250);
  const linkMenu = await page.evaluate(() => typeof editorMenuState !== "undefined" && editorMenuState.open);
  if (linkMenu) await page.keyboard.press("Escape");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(700);
  rr = await page.evaluate((id) => {
    const c = wbState.objects.find((o) => o.id === id).data.comments[1];
    const row = document.querySelector("#wb-comments .wb-comment-reply");
    return { text: c.text, edited: Boolean(c.edited), meta: row?.querySelector("time")?.textContent, chip: Boolean(row?.querySelector(".wb-comment-text a, .wb-comment-text button, .wb-comment-text .wiki-link")) };
  }, ids.sticky);
  ok("Enter keeps the edit and the row says edited", /Agreed, with \[\[Comment sweep card\]\]/.test(rr.text) && rr.edited && /edited/.test(rr.meta || ""), JSON.stringify(rr));
  ok("a [[link]] in a comment is drawn as a link", rr.chip, JSON.stringify(rr));
  await page.evaluate(() => document.querySelector('#wb-comments .wb-comment:not(.wb-comment-reply) [aria-label="Resolve this comment"]').click());
  await page.waitForTimeout(700);
  s = await look("object", ids.sticky);
  rr = await page.evaluate(() => {
    const fold = document.querySelector("#wb-comments .wb-comments-resolved");
    const mark = document.querySelector(".wb-comment-pin .wb-comment-mark.is-resolved");
    return { fold: fold?.querySelector("summary")?.textContent, mark: Boolean(mark), label: mark?.getAttribute("aria-label") };
  });
  ok("Resolve folds the thread and the mark becomes a tick", rr.fold === "1 resolved" && rr.mark, JSON.stringify(rr));
  await page.evaluate(() => document.querySelector('#wb-comments [aria-label="Reopen this comment"]').click());
  await page.waitForTimeout(700);
  rr = await page.evaluate(() => ({ fold: Boolean(document.querySelector("#wb-comments .wb-comments-resolved")), text: document.querySelector(".wb-comment-pin .wb-comment-mark")?.textContent }));
  ok("Reopen brings it back and the mark counts it", !rr.fold && rr.text === "2", JSON.stringify(rr));
  await page.evaluate(() => document.querySelector("#wb-comments .wb-comments-new").click());
  await page.waitForTimeout(200);
  ok("the box has an Attach button", await page.evaluate(() => Boolean(document.querySelector("#wb-comments .wb-comments-attach:not([hidden])"))));
  await page.keyboard.type("/");
  await page.waitForTimeout(400);
  rr = await page.evaluate(() => ({
    open: typeof editorMenuState !== "undefined" && editorMenuState.open,
    rows: [...document.querySelectorAll("#editor-menu [role=option]")].map((o) => o.textContent.trim().slice(0, 24)).slice(0, 12),
  }));
  ok('"/" in the comment box opens the link and emoji menu', rr.open && rr.rows.some((t) => /Bookmark link/.test(t)) && !rr.rows.some((t) => /Heading/.test(t)), JSON.stringify(rr));
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(200);
  await page.evaluate(async (id) => { const o = wbState.objects.find((x) => x.id === id); const d = { ...o.data }; delete d.comments; o.data = d; await wbSaveObject(o); }, ids.sticky);
  await page.evaluate(() => wbCloseComments());
  await page.waitForTimeout(300);

  // 3. The card: kept through a fresh read, followed through a drag, constant size at 2x.
  await page.evaluate(async (id) => {
    wbOpenComments("node", id);
    const box = document.querySelector("#wb-comments .wb-comments-box");
    box.value = "Card note";
    document.querySelector("#wb-comments .wb-comments-post").click();
  }, ids.card);
  await page.waitForTimeout(800);
  await page.keyboard.press("Escape");
  await page.evaluate(async () => {
    await fetchWhiteboardState();
    renderWhiteboardNow();
  });
  await page.waitForTimeout(500);
  let c = await look("node", ids.card);
  ok("the card's thread survives a fresh read", c.count === 1 && c.mark?.text === "1", JSON.stringify({ count: c.count, mark: c.mark }));
  const cr = await page.evaluate((sel) => {
    const r = document.querySelector(sel).getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + 30 };
  }, cardSel);
  await page.mouse.move(cr.x, cr.y);
  await page.mouse.down();
  await page.mouse.move(cr.x + (phone ? -60 : 60), cr.y + 40, { steps: 6 });
  await page.waitForTimeout(120);
  const mid = await look("node", ids.card);
  await page.mouse.up();
  await page.waitForTimeout(700);
  const midGap = mid.mark && mid.item ? Math.abs(mid.mark.left - mid.item.right) + Math.abs(mid.item.top - mid.mark.bottom) : null;
  ok("the mark follows the card during a drag", midGap !== null && midGap <= 20, String(midGap));
  c = await look("node", ids.card);
  const before = c.mark ? { w: c.mark.w, h: c.mark.h } : null;
  await page.evaluate(() => {
    const el = document.getElementById("whiteboard-container");
    const t = d3.zoomTransform(el);
    d3.select(el).call(wbZoom.transform, d3.zoomIdentity.translate(t.x, t.y).scale(t.k * 2));
  });
  await page.waitForTimeout(600);
  c = await look("node", ids.card);
  ok("the mark keeps its screen size at twice the zoom", before && c.mark && Math.abs(c.mark.w - before.w) <= 1.5 && Math.abs(c.mark.h - before.h) <= 1.5, JSON.stringify({ before, after: c.mark && { w: c.mark.w, h: c.mark.h } }));
  await page.evaluate(() => {
    const el = document.getElementById("whiteboard-container");
    const t = d3.zoomTransform(el);
    d3.select(el).call(wbZoom.transform, d3.zoomIdentity.translate(t.x, t.y).scale(t.k / 2));
  });
  await page.waitForTimeout(600);

  // 4. A locked card's mark still takes the press; a shape takes a thread.
  await page.evaluate(async (id) => {
    await wbSetLocked([["node", wbState.nodes.find((n) => n.id === id)]], true);
    renderWhiteboardNow();
  }, ids.card);
  await page.waitForTimeout(400);
  c = await look("node", ids.card);
  const hit = await page.evaluate(([x, y]) => Boolean(document.elementFromPoint(x, y)?.closest(".wb-comment-mark")), [c.mark.x, c.mark.y]);
  ok("a locked card's mark still takes the press", hit, await page.evaluate(([x, y]) => { const e = document.elementFromPoint(x, y); return `${x},${y} ${e?.tagName}.${e?.className} #${e?.id}`; }, [c.mark.x, c.mark.y]));
  await page.evaluate(async (id) => {
    const rect = wbState.sketches.find((s) => s.id === id);
    await wbSaveSketchProps(rect, { comments: [{ id: "x1", text: "Shape remark", at: new Date().toISOString() }] }); wbPaintCommentMarks();
  }, ids.rect);
  await page.waitForTimeout(400);
  const r = await look("sketch", ids.rect);
  ok("a shape takes a thread and wears the mark", r.count === 1 && r.mark?.text === "1", JSON.stringify(r.mark));

  // 5. The mark's ink on its pill.
  const inks = await page.evaluate(() => {
    const m = document.querySelector(".wb-comment-mark");
    const cs = getComputedStyle(m);
    return { fg: cs.color, bg: cs.backgroundColor };
  });
  const cratio = ratio(rgb(inks.fg), rgb(inks.bg));
  ok("the mark's number reads on its pill (4.5:1)", cratio >= 4.5, `${cratio.toFixed(2)} ${JSON.stringify(inks)}`);

  // 6. A map topic's menu.
  const mapId = await page.evaluate(async () =>
    (await apiJson("/whiteboard/boards", { method: "POST", body: JSON.stringify({ name: `Comments map ${Date.now()}`, type: "map", layout: "tree-right" }) })).id
  );
  await page.evaluate((bid) => openWhiteboardBoard(bid), mapId);
  await page.waitForTimeout(1500);
  await page.keyboard.press("Escape");
  const topic = await page.evaluate(async () => {
    const root = wbMapIndex().roots[0] || (await wbMapCreateNode({ parentId: null, text: "Trip" }));
    const a = await wbMapCreateNode({ parentId: root.id, text: "Pack" });
    await wbMapTidy({ quiet: true });
    renderWhiteboardNow();
    if (typeof wbZoomToFit === "function") wbZoomToFit();
    return a.id;
  });
  await page.waitForTimeout(700);
  const menuRows = await page.evaluate((id) => {
    selectWbItem("object", id);
    const menu = wbBuildContextMenu("object");
    return [...menu.querySelectorAll("[role=menuitem], .menu-item")].map((b) => b.textContent.trim());
  }, topic);
  ok("a topic's menu offers Comment…", menuRows.some((t) => t.includes("Comment…")), JSON.stringify(menuRows));
  await page.evaluate((id) => {
    wbCloseContextMenu();
    wbOpenComments("object", id);
    document.querySelector("#wb-comments .wb-comments-box").value = "Which bag?";
    document.querySelector("#wb-comments .wb-comments-post").click();
  }, topic);
  await page.waitForTimeout(800);
  await page.keyboard.press("Escape");
  const t = await look("object", topic);
  ok("a topic takes a thread and wears the mark", t.count === 1 && t.mark?.text === "1", JSON.stringify(t.mark));

  ok("no page errors", errors.length === 0, errors.join(" | "));
  console.log(`\n${pass}/${pass + fail} at ${VW}x${VH} ${process.env.THEME || "light"}`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})();
