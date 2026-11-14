// Comments are a section of the document sidebar's Outline tab, not a right-hand
// column and not a tab of their own (DOCUMENTS_PLAN Phase 5 item 1, and the
// measurement in `documents.js`'s own comment: a third tab wrapped the strip).
// This probe asserts the whole loop against a real document: the count, a row
// that lists the words and the remark, pressing a row jumps the editor to it and
// marks the row as where you are, Resolve leaves the words behind, the pin in
// Live opens the tab at that remark, Read view has no remark in it at all, and
// the section is absent when there is nothing in it.
const { boot } = require("./lib.js");

const CONTENT = [
  "Comment probe",
  "",
  "The ==opening claim== %%is this still true after the rewrite?%% needs a check.",
  "",
  "A plain paragraph with nothing said about it.",
  "",
  "%%standing note: fold the last two sections together%%",
  "",
  "The ==second span== %%too long, cut it%% is the other one.",
].join("\n");

const seed = (title, content) => `(async () => {
  const r = await fetch("/documents", {
    method: "POST",
    headers: { "X-Auth-Token": localStorage.getItem("token") || "", "Content-Type": "application/json" },
    body: JSON.stringify({ title: ${JSON.stringify(title)}, content: ${JSON.stringify(content)} }),
  });
  return (await r.json()).id;
})()`;

(async () => {
  const { page, browser } = await boot({});
  const errs = [];
  page.on("console", (m) => { if (m.type() === "error") errs.push(m.text().slice(0, 160)); });
  page.on("pageerror", (e) => errs.push("PAGEERROR " + e.message.slice(0, 160)));
  const fails = [];
  const openOutline = async () => page.evaluate(async () => {
    document.querySelector('#doc-sidebar-tabs button[data-section="outline"]').click();
    await new Promise((r) => setTimeout(r, 500));
  });

  console.log("seeded: " + await page.evaluate(async (content) => {
    const r = await fetch("/documents", {
      method: "POST",
      headers: { "X-Auth-Token": localStorage.getItem("token") || "", "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Comment probe", content }),
    });
    const doc = await r.json();
    switchTab("documents");
    await new Promise((res) => setTimeout(res, 400));
    await openDocument(doc.id);
    await new Promise((res) => setTimeout(res, 2500));
    return JSON.stringify({ comments: document.querySelectorAll("#doc-comments .doc-comment-item").length });
  }, CONTENT));

  // 1. The section, its count, and the rows.
  await openOutline();
  const listed = await page.evaluate(() => {
    const rows = [...document.querySelectorAll("#doc-comments .doc-comment-item")];
    const wrap = document.getElementById("doc-comments-wrap");
    const sidebar = document.getElementById("doc-sidebar").getBoundingClientRect();
    const wr = wrap.getBoundingClientRect();
    const order = [...document.querySelectorAll("#doc-sidebar-outline > div")].map((d) => d.id);
    return {
      order,
      headCount: document.getElementById("doc-comments-count").textContent,
      wrapVisible: !wrap.classList.contains("hidden"),
      wrapH: Math.round(wr.height),
      rows: rows.length,
      rowH: rows.map((r) => Math.round(r.getBoundingClientRect().height)),
      insideSidebar: rows.every((r) => {
        const rr = r.getBoundingClientRect();
        return rr.left >= sidebar.left - 1 && rr.right <= sidebar.right + 1;
      }),
      overflowsX: rows.some((r) => r.scrollWidth > r.clientWidth + 1),
      first: rows[0] ? {
        context: rows[0].querySelector(".doc-comment-context").textContent,
        body: rows[0].querySelector(".doc-comment-body").textContent,
        kind: rows[0].querySelector(".doc-comment-kind").className,
        actions: rows[0].querySelectorAll(".doc-comment-resolve").length,
        headOneLine: (() => {
          const h = rows[0].querySelector(".doc-comment-head").getBoundingClientRect();
          return h.height <= 32;
        })(),
      } : null,
      standing: rows[1] ? rows[1].querySelector(".doc-comment-context").textContent : null,
      bodyClamped: rows[0] ? getComputedStyle(rows[0].querySelector(".doc-comment-body")).webkitLineClamp : null,
      // The tab strip is the thing a third tab broke. One line, still.
      strip: (() => {
        const el = document.getElementById("doc-sidebar-tabs");
        const r = el.getBoundingClientRect();
        const tabs = [...el.querySelectorAll("button")];
        return {
          h: Math.round(r.height),
          tabs: tabs.length,
          oneLine: new Set(tabs.map((b) => Math.round(b.getBoundingClientRect().top))).size === 1,
          overflows: el.scrollWidth > el.clientWidth + 1,
        };
      })(),
    };
  });
  console.log("listed -> " + JSON.stringify(listed));
  if (listed.rows !== 3) fails.push(`${listed.rows} rows for three comments`);
  if (listed.headCount !== "3") fails.push("the count does not say 3");
  if (!listed.wrapVisible) fails.push("the comments section did not show");
  if (listed.order.indexOf("doc-comments-wrap") !== listed.order.indexOf("doc-outline-wrap") + 1) fails.push(`comments is at ${listed.order.indexOf("doc-comments-wrap")}, not straight after the outline`);
  if (!listed.insideSidebar) fails.push("a row is wider than the sidebar");
  if (listed.overflowsX) fails.push("a row scrolls sideways");
  if (listed.first && !/highlighter/.test(listed.first.kind)) fails.push("an anchored comment is not drawn as a highlight");
  if (listed.first && listed.first.actions !== 1) fails.push("no Resolve on the row");
  if (listed.first && !listed.first.headOneLine) fails.push("the subject line and its action do not share a line");
  if (!listed.strip.oneLine || listed.strip.overflows) fails.push(`the tab strip is ${listed.strip.h}px over more than one line`);
  if (Math.max(...listed.rowH) > 100) fails.push(`a row is ${Math.max(...listed.rowH)}px tall`);

  // 2. Pressing a row jumps the editor to it and marks the row.
  const jumped = await page.evaluate(async () => {
    const rows = [...document.querySelectorAll("#doc-comments .doc-comment-item")];
    rows[0].querySelector(".doc-comment-open").click();
    await new Promise((r) => setTimeout(r, 700));
    const sel = docSurface()?.selection?.();
    return {
      current: document.querySelectorAll("#doc-comments .doc-comment-item[aria-current]").length,
      currentIsFirst: rows[0].hasAttribute("aria-current"),
      view: docView,
      selection: sel ? docText().slice(sel.from, sel.to) : null,
      floating: [...document.querySelectorAll("#doc-suggest-menu")]
        .filter((m) => !m.classList.contains("hidden")).length,
      bg: getComputedStyle(rows[0]).backgroundColor,
    };
  });
  console.log("row pressed -> " + JSON.stringify(jumped));
  if (jumped.current !== 1 || !jumped.currentIsFirst) fails.push("the pressed row does not say it is current");
  if (!/opening claim/.test(jumped.selection || "")) fails.push(`the editor did not select the remark (${jumped.selection})`);
  if (jumped.floating) fails.push("a floating surface opened from a comment row");
  if (jumped.bg === "rgba(0, 0, 0, 0)") fails.push("the current row is not painted");

  // 3. The pin in Live opens the tab at that remark.
  const pin = await page.evaluate(async () => {
    document.querySelector('#doc-sidebar-tabs button[data-section="list"]').click();
    await new Promise((r) => setTimeout(r, 400));
    const box = docSurface(); if (box) box.setSelection(0, 0);
    await new Promise((r) => setTimeout(r, 400));
    const pins = [...document.querySelectorAll(".doc-comment-pin")];
    const marks = document.querySelectorAll(".cm-md-commented").length;
    const lineH = (() => {
      const lines = [...document.querySelectorAll(".cm-line")];
      const withPin = lines.find((l) => l.querySelector(".doc-comment-pin"));
      const without = lines.find((l) => !l.querySelector(".doc-comment-pin") && l.textContent.trim());
      return { withPin: withPin ? Math.round(withPin.getBoundingClientRect().height) : null,
               without: without ? Math.round(without.getBoundingClientRect().height) : null };
    })();
    if (!pins.length) return JSON.stringify({ pins: 0, marks, lineH });
    const pr = pins[pins.length - 1].getBoundingClientRect();
    pins[pins.length - 1].click();
    await new Promise((r) => setTimeout(r, 600));
    return JSON.stringify({
      pins: pins.length,
      marks,
      lineH,
      pinBox: { w: Math.round(pr.width), h: Math.round(pr.height) },
      opened: !document.getElementById("doc-sidebar-outline").classList.contains("hidden"),
      current: document.querySelectorAll("#doc-comments .doc-comment-item[aria-current]").length,
    });
  });
  console.log("pin -> " + pin);
  {
    const p = JSON.parse(pin);
    if (p.pins !== 3) fails.push(`${p.pins} pins for three comments`);
    if (p.marks !== 2) fails.push(`${p.marks} commented highlights for two anchored comments`);
    if (!p.opened) fails.push("the pin did not open the tab the comments are in");
    if (p.current !== 1) fails.push("the pin did not mark its row");
    if (p.lineH.withPin !== p.lineH.without) fails.push(`a line with a pin is ${p.lineH.withPin}px against ${p.lineH.without}px`);
  }

  // 4. Read view has no remark in it; the count leaves them out.
  const read = await page.evaluate(async () => {
    const counts = document.getElementById("doc-counts").textContent;
    setDocView("rendered");
    await new Promise((r) => setTimeout(r, 800));
    const preview = document.getElementById("doc-preview").textContent;
    setDocView("live");
    await new Promise((r) => setTimeout(r, 500));
    return JSON.stringify({
      counts,
      leaksRemark: /still true after the rewrite|fold the last two|too long, cut it/.test(preview),
      keepsWords: /opening claim/.test(preview),
      leaksMarkers: /%%/.test(preview),
    });
  });
  console.log("read view -> " + read);
  {
    const r = JSON.parse(read);
    if (r.leaksRemark) fails.push("a remark is rendered in Read view");
    if (!r.keepsWords) fails.push("Read view lost the words a comment was about");
    if (r.leaksMarkers) fails.push("Read view shows the %% markers");
  }

  // 4b. A print carries the remarks as footnotes, which is the one half of
  // Phase 5 item 1 ("exported as footnotes") that no test could see: the server
  // export is covered by tests/test_doc_comments.py, the *printed* one is this
  // flag and the pane it redraws. `window.print()` is not called (it blocks on a
  // dialog no sweep can dismiss); what is asserted is the render it triggers.
  const printed = await page.evaluate(async () => {
    docPrintComments = true;
    setDocView("rendered");
    await new Promise((r) => setTimeout(r, 800));
    renderDocPreview();
    await new Promise((r) => setTimeout(r, 400));
    const withFootnotes = document.getElementById("doc-preview").textContent;
    //: Footnotes draw as raised numbers since FEAT-03 (mdFootnotesFinish), so
    //: the marker is the raised reference, not the literal "c1" it once was.
    const raised = Boolean(document.querySelector("#doc-preview sup a, #doc-preview .footnotes li"));
    docPrintComments = false;
    renderDocPreview();
    await new Promise((r) => setTimeout(r, 400));
    const after = document.getElementById("doc-preview").textContent;
    setDocView("live");
    await new Promise((r) => setTimeout(r, 500));
    return JSON.stringify({
      carriesRemarks: /still true after the rewrite/.test(withFootnotes),
      marker: /c1/.test(withFootnotes) || raised,
      keepsWords: /opening claim/.test(withFootnotes),
      clearsAfter: !/still true after the rewrite/.test(after),
    });
  });
  console.log("print -> " + printed);
  {
    const r = JSON.parse(printed);
    if (!r.carriesRemarks) fails.push("a print would drop the remarks rather than footnote them");
    if (!r.marker) fails.push("no footnote marker in the printed pane");
    if (!r.keepsWords) fails.push("the printed pane lost the words a comment was about");
    if (!r.clearsAfter) fails.push("the remarks stayed in Read view after the print");
  }

  // 5. Contrast on the rows, from the painted pixels rather than from a
  // compositing walk: these surfaces are translucent over a gradient and the
  // walk bottoms out on `body`, which is not what is painted (prosepanel.js
  // records the same, and the number it gives for the app's own `.doc-hint`).
  const theme = process.env.THEME || "light";
  const shot = `${require("os").tmpdir()}/doccomments-${theme}.png`;
  await openOutline();
  const samples = await page.evaluate(async () => {
    const rows = [...document.querySelectorAll("#doc-comments .doc-comment-item")];
    if (rows[0]) rows[0].querySelector(".doc-comment-open").click();
    await new Promise((r) => setTimeout(r, 500));
    const pick = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const cs = getComputedStyle(el);
      return { color: cs.color, size: parseFloat(cs.fontSize), weight: parseInt(cs.fontWeight, 10) };
    };
    const boxOf = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { left: r.left, right: r.right, top: r.top, bottom: r.bottom };
    };
    const plain = "#doc-comments .doc-comment-item:not([aria-current])";
    const current = "#doc-comments .doc-comment-item[aria-current]";
    return [
      { name: "context", box: boxOf(plain), text: pick(`${plain} .doc-comment-context`) },
      { name: "body", box: boxOf(plain), text: pick(`${plain} .doc-comment-body`) },
      { name: "current body", box: boxOf(current), text: pick(`${current} .doc-comment-body`) },
      { name: "current context", box: boxOf(current), text: pick(`${current} .doc-comment-context`) },
      { name: "count", box: boxOf("#doc-comments-wrap h3"), text: pick("#doc-comments-count") },
    ];
  });
  await page.screenshot({ path: shot });
  const { execFileSync } = require("child_process");
  const lum = (rgb) => {
    const f = rgb.map((v) => { const c = v / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
    return 0.2126 * f[0] + 0.7152 * f[1] + 0.0722 * f[2];
  };
  const pixel = (x, y) => {
    const out = execFileSync("python3", ["scratchpad/pngpixel.py", shot, String(Math.round(x)), String(Math.round(y))], { encoding: "utf8" });
    //: The last parenthesised triple: the first line is the file and its size,
    //: which a naive scan for numbers reads as a colour.
    const m = out.trim().match(/\((\d+),\s*(\d+),\s*(\d+)\)\s*$/);
    if (!m) throw new Error("pngpixel said: " + out.trim());
    return [Number(m[1]), Number(m[2]), Number(m[3])];
  };
  const ratios = [];
  for (const s of samples) {
    if (!s.box || !s.text) continue;
    // A point inside the row with no glyph on it: the right-hand inset, past
    // where the subject ellipsises and under the action's own line.
    const bg = pixel(s.box.right - 4, s.box.bottom - 4);
    const fg = (s.text.color.match(/[\d.]+/g) || []).slice(0, 3).map(Number);
    const ratio = (Math.max(lum(fg), lum(bg)) + 0.05) / (Math.min(lum(fg), lum(bg)) + 0.05);
    ratios.push({ name: s.name, ratio: Math.round(ratio * 100) / 100, size: s.text.size, weight: s.text.weight });
  }
  console.log("contrast (" + theme + ") -> " + JSON.stringify(ratios));
  for (const r of ratios) {
    const large = r.size >= 24 || (r.size >= 18.66 && r.weight >= 700);
    const need = large ? 3 : 4.5;
    if (r.ratio < need) fails.push(`${r.name} contrast ${r.ratio}:1 under ${need}:1`);
  }

  // 6. Resolve leaves the words and takes the remark.
  const resolved = await page.evaluate(async () => {
    const before = docText();
    const rows = [...document.querySelectorAll("#doc-comments .doc-comment-item")];
    rows[0].querySelector(".doc-comment-resolve").click();
    await new Promise((r) => setTimeout(r, 700));
    return JSON.stringify({
      was: rows.length,
      now: document.querySelectorAll("#doc-comments .doc-comment-item").length,
      keptWords: /opening claim/.test(docText()),
      tookRemark: !/still true after the rewrite/.test(docText()),
      tookHighlight: !/==opening claim==/.test(docText()),
      changed: docText() !== before,
      count: document.getElementById("doc-comments-count").textContent,
    });
  });
  console.log("resolve -> " + resolved);
  {
    const r = JSON.parse(resolved);
    if (r.now !== r.was - 1) fails.push("resolving did not drop the row");
    if (!r.keptWords) fails.push("resolving took the words with the remark");
    if (!r.tookRemark) fails.push("resolving left the remark in the text");
    if (!r.tookHighlight) fails.push("resolving left the highlight markers behind");
    if (r.count !== "2") fails.push(`the count says ${r.count} after resolving one of three`);
  }

  // 6b. A thread (DOCUMENTS_PLAN DX24t): a reply, a reload, the resolved shelf, Reopen.
  const threaded = await page.evaluate(async () => {
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    const rows = () => [...document.querySelectorAll("#doc-comments .doc-comment-item")];
    const id = currentDoc.id;
    const first = rows()[0];
    const bylineBefore = first.querySelector(".doc-comment-who")?.textContent || "";
    first.querySelector(".doc-comment-reply-open").click();
    await wait(200);
    const input = document.querySelector("#doc-comments .doc-comment-reply-input");
    const sidebar = document.getElementById("doc-sidebar").getBoundingClientRect();
    const box = input.getBoundingClientRect();
    const focused = document.activeElement === input;
    // L332: Attach writes the picked link into the field; the form still fits the sidebar.
    const attachBtn = input.form.querySelector("button[title^='Attach']");
    const realPick = window.pickLibraryItemDialog;
    window.pickLibraryItemDialog = async () => ({ kind: "link", label: "Example", row: { url: "https://example.com/a" } });
    attachBtn?.click();
    await wait(200);
    const attachedValue = input.value;
    const formBox = input.form.getBoundingClientRect();
    window.pickLibraryItemDialog = realPick;
    input.value = "Will do, thanks";
    input.form.requestSubmit();
    await wait(300);
    const replied = rows()[0].querySelectorAll(".doc-comment-reply").length;
    await wait(2200);
    const server = await (await fetch(`/documents/${id}`, { headers: { "X-Auth-Token": localStorage.getItem("token") || "" } })).json();
    return JSON.stringify({
      id,
      bylineBefore,
      attachedValue,
      attachFits: !!attachBtn && formBox.right <= sidebar.right + 1,
      focused,
      inputInside: box.left >= sidebar.left && box.right <= sidebar.right,
      inputW: Math.round(box.width),
      replied,
      saved: server.threads.length,
      serverReplies: server.threads.map((t) => t.replies.length),
      resolvedOnServer: server.threads.filter((t) => t.resolved).length,
      rowH: rows().map((r) => Math.round(r.getBoundingClientRect().height)),
    });
  });
  console.log("thread -> " + threaded);
  const th = JSON.parse(threaded);
  if (!th.focused) fails.push("Reply did not put the caret in its field");
  if (th.attachedValue !== "[Example](https://example.com/a) ") fails.push("Attach did not write the link: " + th.attachedValue);
  if (!th.attachFits) fails.push("the reply form with Attach leaves the sidebar");
  if (!th.inputInside) fails.push("the reply field leaves the sidebar");
  if (th.replied !== 1) fails.push("the reply is not listed under its remark");
  if (th.resolvedOnServer !== 1) fails.push("the resolved thread is not kept on the server");
  if (!th.serverReplies.includes(1)) fails.push("the reply was not saved");

  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  if (await page.locator("#lock-password").isVisible().catch(() => false)) {
    await page.fill("#lock-password", "testpassword123");
    await page.click("#lock-submit");
    await page.waitForTimeout(2500);
  }
  const reopened = await page.evaluate(async (id) => {
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    switchTab("documents");
    await wait(500);
    await openDocument(id);
    await wait(2500);
    document.querySelector('#doc-sidebar-tabs button[data-section="outline"]').click();
    await wait(500);
    const rows = () => [...document.querySelectorAll("#doc-comments .doc-comment-item")];
    const afterReload = { rows: rows().length, replies: document.querySelectorAll("#doc-comments .doc-comment-reply").length };
    const toggle = document.getElementById("doc-comments-resolved-toggle");
    const toggleText = toggle.textContent;
    const shelfHiddenFirst = document.getElementById("doc-comments-resolved").classList.contains("hidden");
    toggle.click();
    await wait(200);
    const shelf = [...document.querySelectorAll("#doc-comments-resolved .doc-comment-item")];
    const shelfInfo = { rows: shelf.length, context: shelf[0]?.querySelector(".doc-comment-context")?.textContent, expanded: toggle.getAttribute("aria-expanded") };
    // A resolved row also has Reply (first in the row since resolved threads can be answered); Reopen is the last action.
    shelf[0].querySelector(".doc-comment-action:last-of-type, [title^=\"Reopen\"]").click();
    await wait(700);
    return JSON.stringify({
      afterReload,
      toggleText,
      shelfHiddenFirst,
      shelfInfo,
      backInText: docText().includes("==opening claim== %%is this still true after the rewrite?%%"),
      rowsNow: rows().length,
      shelfNow: document.querySelectorAll("#doc-comments-resolved .doc-comment-item").length,
      toggleHidden: document.getElementById("doc-comments-resolved-toggle").classList.contains("hidden"),
    });
  }, th.id);
  console.log("reload + reopen -> " + reopened);
  {
    const r = JSON.parse(reopened);
    if (r.afterReload.rows !== 2 || r.afterReload.replies !== 1) fails.push("the reply did not survive a reload");
    if (!/1 resolved/.test(r.toggleText) || !r.shelfHiddenFirst) fails.push("the resolved shelf is not folded behind its toggle");
    if (r.shelfInfo.rows !== 1 || r.shelfInfo.context !== "opening claim" || r.shelfInfo.expanded !== "true") fails.push("the resolved shelf does not list the thread");
    if (!r.backInText || r.rowsNow !== 3) fails.push("Reopen did not put the remark back");
    if (r.shelfNow !== 0 || !r.toggleHidden) fails.push("a reopened thread is still on the resolved shelf");
  }

  // 7. A document with no comments has no section at all.
  const empty = await page.evaluate(async () => {
    const r = await fetch("/documents", {
      method: "POST",
      headers: { "X-Auth-Token": localStorage.getItem("token") || "", "Content-Type": "application/json" },
      body: JSON.stringify({ title: "No comments", content: "Nothing said about anything here.\n" }),
    });
    const doc = await r.json();
    await openDocument(doc.id);
    await new Promise((res) => setTimeout(res, 1500));
    const wrap = document.getElementById("doc-comments-wrap");
    return JSON.stringify({
      rows: document.querySelectorAll("#doc-comments .doc-comment-item").length,
      wrapHidden: wrap.classList.contains("hidden"),
      wrapH: Math.round(wrap.getBoundingClientRect().height),
      headCount: document.getElementById("doc-comments-count").textContent,
    });
  });
  console.log("no comments -> " + empty);
  {
    const e = JSON.parse(empty);
    if (e.rows) fails.push("rows listed for a document with no comments");
    if (!e.wrapHidden || e.wrapH) fails.push(`the empty section takes ${e.wrapH}px`);
    if (e.headCount) fails.push("a count is shown for zero comments");
  }

  // 8. Commenting on the selection, the way the Highlight menu does it.
  const made = await page.evaluate(async () => {
    const box = docSurface();
    box.setSelection(8, 12);
    await new Promise((r) => setTimeout(r, 200));
    applyMarkdown("annotate");
    await new Promise((r) => setTimeout(r, 600));
    const sel = docSurface().selection();
    const text = docText();
    const typed = text.slice(0, sel.from) + "check this" + text.slice(sel.to);
    return JSON.stringify({
      text: text.slice(0, 60),
      caretInRemark: /%%%%/.test(text) && sel.from === text.indexOf("%%%%") + 2,
      wouldRead: typed.slice(0, 60),
      // An empty remark is not a comment yet, so nothing is listed for it.
      comments: document.querySelectorAll("#doc-comments .doc-comment-item").length,
      menuItem: Boolean(document.querySelector('[data-md="annotate"]')),
    });
  });
  console.log("annotate -> " + made);
  {
    const m = JSON.parse(made);
    if (!m.caretInRemark) fails.push("the caret is not inside the new remark");
    if (m.comments) fails.push("an empty remark was listed as a comment");
    if (!m.menuItem) fails.push("no Comment item in the toolbar");
  }

  console.log("console errors: " + errs.length + (errs.length ? " " + JSON.stringify(errs.slice(0, 4)) : ""));
  if (errs.length) fails.push(`${errs.length} console errors`);
  await browser.close();
  if (fails.length) { console.log("FAIL\n- " + fails.join("\n- ")); process.exit(1); }
  console.log("PASS");
})();
