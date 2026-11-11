// A rendered block can be changed from where it is drawn (INBOX 421 b:
// "change kind from the rendered block", "a block hover toolbar").
//
// Read view: hovering a callout shows the block bar at its top right; its
// kind button's menu turns a warning into a tip in the text; Delete removes
// a paragraph and Undo puts it back; Edit lands the caret on the block's
// line. A block after a columns block and an embed is found too (its source
// line used to be counted from the wrong zero). Live view: the callout
// label's icon opens the same menu. An embedded document draws as a card in
// both views.
//
//   BASE=http://127.0.0.1:8794 node scratchpad/ui-sweeps/blockbar.js
const { boot } = require("./lib.js");

(async () => {
  const { page, browser } = await boot({});
  let fails = 0;
  const check = (name, ok, detail) => {
    if (!ok) fails += 1;
    console.log(`${ok ? "ok  " : "FAIL"} ${name}${detail !== undefined ? ": " + detail : ""}`);
  };
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message.slice(0, 160)));
  try {
    const ids = await page.evaluate(async () => {
      const headers = { "X-Auth-Token": localStorage.getItem("token") || "", "Content-Type": "application/json" };
      const other = await (await fetch("/documents", { method: "POST", headers, body: JSON.stringify({ title: "Embedded target", content: "Embedded target\n\nThe first words of the embedded document are here." }) })).json();
      const text = [
        "Block bar probe", "",
        "> [!warning] Careful", "> Body.", "",
        "A paragraph to delete.", "",
        ":::columns", "Left", ":::column", "Right", ":::", "",
        "![[Embedded target]]", "",
        "> [!note] Late callout", "> After the columns and the embed.", "",
        "Last paragraph.",
      ].join("\n");
      const doc = await (await fetch("/documents", { method: "POST", headers, body: JSON.stringify({ title: "Block bar probe", content: text }) })).json();
      if (typeof loadDocuments === "function") await loadDocuments();
      switchTab("documents");
      await new Promise((r) => setTimeout(r, 500));
      await openDocument(doc.id);
      await new Promise((r) => setTimeout(r, 1800));
      setDocView("rendered");
      await new Promise((r) => setTimeout(r, 800));
      return { doc: doc.id, other: other.id };
    });
    const text = () => page.evaluate(() => docText());
    const hover = async (sel, nth = 0, words = null) => {
      const box = await page.evaluate(({ sel, nth, words }) => {
        const all = [...document.querySelectorAll(`#doc-preview > ${sel}`)];
        const el = words ? all.find((n) => n.textContent.trim() === words) : all[nth];
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { x: r.left + r.width / 2, y: r.top + Math.min(12, r.height / 2), top: r.top, right: r.right };
      }, { sel, nth, words });
      if (!box) return null;
      await page.mouse.move(box.x - 20, box.y + 4);
      await page.mouse.move(box.x, box.y);
      await page.waitForTimeout(250);
      return box;
    };
    const bar = () => page.evaluate(() => {
      const el = document.getElementById("doc-block-bar");
      if (!el || el.classList.contains("hidden")) return null;
      const r = el.getBoundingClientRect();
      return { top: r.top, right: r.right, buttons: [...el.querySelectorAll("button")].map((b) => b.getAttribute("aria-label")) };
    });

    // --- a callout's kind, from the Read view ----------------------------------
    const c = await hover(".callout");
    let b = await bar();
    check("bar shows on a callout", b && b.buttons.length === 4, JSON.stringify(b && b.buttons));
    check("bar stands in the block's right gutter, level with its top, off the text", b && Math.abs(b.top - c.top) < 4 && b.left >= c.right, b && `bar ${Math.round(b.top)},${Math.round(b.left)} block ${Math.round(c.top)},${Math.round(c.right)}`);
    await page.click("#doc-block-bar .doc-block-kind");
    await page.waitForTimeout(300);
    const tip = await page.evaluate(() => [...document.querySelectorAll(".action-menu:not(.hidden) [role=menuitem], .action-menu:not(.hidden) button")].find((el) => /^\s*Tip\s*$/.test(el.textContent)));
    check("kind menu lists Tip", Boolean(tip));
    await page.evaluate(() => [...document.querySelectorAll(".action-menu:not(.hidden) [role=menuitem], .action-menu:not(.hidden) button")].find((el) => /^\s*Tip\s*$/.test(el.textContent))?.click());
    await page.waitForTimeout(400);
    let t = await text();
    check("kind written to the text", t.includes("> [!tip] Careful") && !t.includes("[!warning]"), JSON.stringify(t.slice(0, 60)));

    // --- delete and undo --------------------------------------------------------
    await hover("p", 0, "A paragraph to delete.");
    const which = await page.evaluate(() => document.getElementById("doc-block-bar") && docBlockBarFor && docBlockBarFor.textContent);
    await page.click('#doc-block-bar button[aria-label="Delete this block"]');
    await page.waitForTimeout(400);
    t = await text();
    check("delete removes the paragraph", !t.includes("A paragraph to delete.") && t.includes("> Body.\n\n:::columns"), `${which} -> ${JSON.stringify(t.slice(30, 90))}`);
    await page.evaluate(() => [...document.querySelectorAll(".toast button")].find((btn) => /undo/i.test(btn.textContent))?.click());
    await page.waitForTimeout(400);
    t = await text();
    check("Undo puts it back", t.includes("> Body.\n\nA paragraph to delete.\n\n:::columns"), JSON.stringify(t.slice(30, 100)));

    // --- a block after columns and an embed is found in the text ----------------
    await page.evaluate(() => document.getElementById("doc-preview").scrollTo(0, 99999));
    await page.waitForTimeout(300);
    await hover(".callout", 1);
    b = await bar();
    check("bar on the late callout", b && b.buttons.length === 4, JSON.stringify(b && b.buttons));
    await page.click("#doc-block-bar .doc-block-kind").catch(() => {});
    await page.waitForTimeout(300);
    await page.evaluate(() => [...document.querySelectorAll(".action-menu:not(.hidden) [role=menuitem], .action-menu:not(.hidden) button")].find((el) => /^\s*Example\s*$/.test(el.textContent))?.click());
    await page.waitForTimeout(400);
    t = await text();
    check("late callout rewritten on its own line", t.includes("> [!example] Late callout") && t.includes("> [!tip] Careful"), JSON.stringify(t.slice(-90)));

    // --- the embedded document is a card ------------------------------------------
    const card = await page.evaluate(() => {
      const el = document.querySelector("#doc-preview .embed-card");
      if (!el) return document.querySelector("#doc-preview .note-embed")?.outerHTML.slice(0, 300) || "no embed";
      return el ? { title: el.querySelector(".embed-card-title")?.textContent, meta: el.querySelector(".embed-card-meta")?.textContent, icon: Boolean(el.querySelector("i.ph")) } : null;
    });
    check("Read: document embed is a card", card && card.title === "Embedded target" && /words/.test(card.meta) && card.icon, JSON.stringify(card));

    // --- Live view: the label's icon opens the same menu --------------------------
    await page.evaluate(async () => {
      setDocView("live");
      await new Promise((r) => setTimeout(r, 800));
      document.querySelector(".cm-content").blur();
      document.querySelector(".cm-scroller").scrollTop = 0;
      await new Promise((r) => setTimeout(r, 300));
    });
    const liveCard = await page.evaluate(() => Boolean(document.querySelector(".cm-editor .embed-card")));
    check("Live: document embed is a card", liveCard);
    const kb = await page.evaluate(() => {
      const el = document.querySelector(".cm-md-callout-kindbtn");
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
    });
    check("Live: callout label has a kind button", Boolean(kb));
    if (kb) {
      await page.mouse.click(kb.x, kb.y);
      await page.waitForTimeout(300);
      await page.evaluate(() => [...document.querySelectorAll(".action-menu:not(.hidden) [role=menuitem], .action-menu:not(.hidden) button")].find((el) => /^\s*Danger\s*$/.test(el.textContent))?.click());
      await page.waitForTimeout(400);
      t = await text();
      check("Live: kind written to the text", t.includes("> [!danger] Careful"), JSON.stringify(t.slice(0, 60)));
    }
    check("no page errors", !errors.length, errors.join(" | "));

    await page.evaluate(async (ids) => {
      const headers = { "X-Auth-Token": localStorage.getItem("token") || "" };
      await fetch(`/documents/${ids.doc}`, { method: "DELETE", headers });
      await fetch(`/documents/${ids.other}`, { method: "DELETE", headers });
    }, ids);
    console.log(fails ? `FAIL: ${fails} check(s)` : "the block bar works");
  } finally {
    await browser.close();
  }
  process.exit(fails ? 1 : 0);
})();
