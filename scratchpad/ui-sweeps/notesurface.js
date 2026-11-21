// DOCUMENTS_PLAN Phase 8: one editor everywhere, measured in a browser.
//
// The lint (`tests/test_note_surface.py`) can see that a note textarea is in
// the factory's table and that the table is complete. What it cannot see is
// whether the engine actually mounts under a real capture box, whether the
// textarea under it still carries the value every save path reads, and
// whether the three things the phase promises (the same toolbar, the same
// shortcuts, the same word popup) reach a note the way they reach a document.
// That is this file.
//
//   BASE=http://127.0.0.1:8793 node scratchpad/ui-sweeps/notesurface.js
const { boot } = require("./lib.js");

let failures = 0;
const ok = (name, condition, detail) => {
  if (!condition) failures += 1;
  console.log(`${condition ? "PASS" : "FAIL"}  ${name}${detail === undefined ? "" : `  — ${detail}`}`);
};

(async () => {
  const { browser, page } = await boot();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message.slice(0, 160)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text().slice(0, 160)); });

  // --- the capture box ------------------------------------------------------
  // One note to edit later, saved through the app's own capture form rather
  // than through a guessed endpoint.
  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(600);
  // Capture is a sub-tab of Notes, not the tab's first pane.
  await page.evaluate(() => {
    const tab = [...document.querySelectorAll("#notes-subtabs button")]
      .find((b) => b.dataset.section === "capture");
    if (tab) tab.click();
  });
  await page.waitForTimeout(600);
  const before = await page.evaluate(() => {
    const box = document.getElementById("entry-content");
    return { exists: !!box, mounted: !!box.closest(".note-surface") };
  });
  ok("capture starts as the textarea it always was", before.exists && !before.mounted,
    JSON.stringify(before));

  await page.click("#entry-content");
  await page.waitForTimeout(1800);
  const mounted = await page.evaluate(() => {
    const box = document.getElementById("entry-content");
    const wrap = box.closest(".note-surface");
    const view = wrap ? wrap.querySelector(".cm-content") : null;
    const r = wrap ? wrap.getBoundingClientRect() : null;
    const br = box.getBoundingClientRect();
    return {
      wrapped: !!wrap,
      hasView: !!view,
      focused: document.activeElement === view || (view && view.contains(document.activeElement)),
      size: wrap ? wrap.className : null,
      // Top-left and width, not height: the capture box's own autogrow writes
      // an inline `height` on every input and that beats a stylesheet, so the
      // mirror ends early. What has to match is where it *starts*, because
      // that is what a popup positioned off this element reads.
      overlaid: r ? Math.abs(br.left - r.left) <= 2 && Math.abs(br.top - r.top) <= 2
        && Math.abs(br.width - r.width) <= 4 : null,
      rects: r ? { box: [+br.left.toFixed(1), +br.top.toFixed(1), +br.width.toFixed(1)],
        wrap: [+r.left.toFixed(1), +r.top.toFixed(1), +r.width.toFixed(1)] } : null,
      opacity: getComputedStyle(box).opacity,
      tabindex: box.getAttribute("tabindex"),
    };
  });
  ok("the engine mounts on the first focus", mounted.wrapped && mounted.hasView, JSON.stringify(mounted));
  ok("the caret lands in the view", mounted.focused, String(mounted.focused));
  ok("the textarea is laid over the view at zero opacity",
    mounted.overlaid && mounted.opacity === "0" && mounted.tabindex === "-1",
    `${mounted.overlaid} / ${mounted.opacity} / ${mounted.tabindex}`);

  // Typing reaches the textarea every save path reads.
  // A second line, and the caret left on it: Live reveals the syntax on the
  // line the caret is in (the same rule the document follows), so a check
  // that reads the first line with the caret still in it measures the reveal
  // rather than the rendering. The first version of this file did exactly
  // that and reported Live as off.
  await page.keyboard.type("A note about **markdown** and a [[link]]\nsecond line");
  await page.waitForTimeout(400);
  const typed = await page.evaluate(() => {
    const box = document.getElementById("entry-content");
    return { value: box.value, surfaceText: asSurface(box).text, kind: asSurface(box).kind, id: asSurface(box).id };
  });
  ok("the textarea carries what was typed into the view",
    typed.value === "A note about **markdown** and a [[link]]\nsecond line",
    JSON.stringify(typed.value));
  ok("asSurface resolves the textarea to the view",
    typed.kind === "codemirror" && typed.id === "entry-content", `${typed.kind}/${typed.id}`);

  // The same decorations as a document: the bold marks are drawn, not shown.
  const live = await page.evaluate(() => {
    const wrap = document.getElementById("entry-content").closest(".note-surface");
    const strong = wrap.querySelector(".cm-md-strong");
    const wiki = wrap.querySelector(".cm-md-wiki");
    return {
      strong: strong ? strong.textContent : null,
      strongWeight: strong ? getComputedStyle(strong).fontWeight : null,
      wiki: wiki ? wiki.textContent : null,
      lineText: wrap.querySelector(".cm-line").textContent,
    };
  });
  ok("Live decorations are on in a note", live.strong === "markdown" && Number(live.strongWeight) >= 600,
    JSON.stringify(live));
  ok("the syntax is hidden the way it is in a document",
    !/\*\*/.test(live.lineText) && !/\[\[/.test(live.lineText), JSON.stringify(live.lineText));

  // The same shortcuts: Ctrl+B wraps the selection.
  await page.evaluate(() => {
    const s = asSurface(document.getElementById("entry-content"));
    const at = s.text.indexOf("note");
    s.setSelection(at, at + 4);
    s.focus();
  });
  await page.keyboard.press("Control+b");
  await page.waitForTimeout(250);
  await page.waitForTimeout(150);
  const bolded = await page.evaluate(() => document.getElementById("entry-content").value);
  ok("Ctrl+B is bold in a note", bolded.includes("**note**"), JSON.stringify(bolded.slice(0, 40)));

  // The same toolbar: the capture strip's buttons act on the view.
  const beforeList = bolded;
  await page.evaluate(() => {
    const button = document.querySelector('#note-toolbar [data-md="ul"]');
    if (button) button.click();
  });
  await page.waitForTimeout(250);
  const listed = await page.evaluate(() => document.getElementById("entry-content").value);
  ok("the capture toolbar writes into the view", listed !== beforeList && /^- /m.test(listed),
    JSON.stringify(listed.slice(0, 40)));

  // The same word popup: the "/" menu opens off a typed slash.
  await page.evaluate(() => {
    const s = asSurface(document.getElementById("entry-content"));
    s.focus();
    s.setSelection(s.text.length, s.text.length);
  });
  await page.keyboard.type(" /");
  await page.waitForTimeout(500);
  const slash = await page.evaluate(() => {
    const menu = document.getElementById("editor-menu");
    return {
      open: menu ? !menu.classList.contains("hidden") : false,
      items: menu ? menu.querySelectorAll(".editor-menu-item").length : 0,
    };
  });
  ok("the / menu opens in a note", slash.open && slash.items > 4, JSON.stringify(slash));
  await page.keyboard.press("Escape");

  // A script writing the value reaches the view (this is what saving a note
  // does, and the half a mirror gets wrong).
  const cleared = await page.evaluate(() => {
    const box = document.getElementById("entry-content");
    box.value = "";
    return {
      value: box.value,
      view: asSurface(box).text,
      lines: box.closest(".note-surface").querySelectorAll(".cm-line").length,
    };
  });
  ok("clearing the textarea clears the view", cleared.view === "" && cleared.value === "",
    JSON.stringify(cleared));

  // The whole point of the mirror, end to end: a note typed into the view is
  // what `saveEntry` sends, and clearing the box afterwards clears the view
  // with it. Both halves through the app's own save, not through the adapter.
  // Through the surface, not a click on the element: the mirror is laid over
  // the view with `pointer-events: none`, so a click on it lands nowhere (and
  // times out), which is the mirror doing exactly what it should.
  await page.evaluate(() => asSurface(document.getElementById("entry-content")).focus());
  await page.waitForTimeout(400);
  await page.keyboard.type("A note saved through the engine.");
  await page.waitForTimeout(300);
  const savedNote = await page.evaluate(async () => {
    await saveEntry();
    const box = document.getElementById("entry-content");
    const response = await fetch("/entries?limit=3", { headers: { "X-Auth-Token": authToken() } });
    const rows = await response.json();
    const list = Array.isArray(rows) ? rows : rows.items || [];
    return { stored: list.length ? list[0].content : null, box: box.value, view: asSurface(box).text };
  });
  ok("a note typed into the view is what the app saves",
    savedNote.stored === "A note saved through the engine.", JSON.stringify(savedNote.stored));
  ok("and saving clears the box and the view together",
    savedNote.box === "" && savedNote.view === "", JSON.stringify(savedNote));

  // A note to edit, through the app's own endpoint (`/entries`; `/notes`
  // answered 405 and cost a run), then the browse sub-tab it is listed in.
  await page.evaluate(async () => {
    await apiJson("/entries", { method: "POST", body: JSON.stringify({ content: "An older note to edit" }) });
    if (typeof loadEntries === "function") await loadEntries();
  });
  await page.evaluate(() => {
    const tab = [...document.querySelectorAll("#notes-subtabs button")]
      .find((b) => b.dataset.section === "browse");
    if (tab) tab.click();
  });
  await page.waitForTimeout(900);

  // --- the note edit form, built in script ---------------------------------
  const opened = await page.evaluate(async () => {
    // Whatever this app calls its own note list, the edit form is opened by
    // the function the cards' buttons call, and an id from the list the app
    // already holds. Guessing an endpoint here cost one run (POST /notes
    // answered 405).
    // `allEntries` is the list the app already holds and the note slice plus a
    // re-render is how every card in it opens its edit form (app.js).
    const list = typeof allEntries !== "undefined" && Array.isArray(allEntries) ? allEntries : [];
    const note = list.find((entry) => !entry.is_board);
    if (!note) return "no note to edit";
    setEditingNote(note.id);
    renderEntries();
    return "the note slice";
  });
  await page.waitForTimeout(900);
  const editBox = await page.$("#entry-edit-content");
  if (editBox) {
    await page.click("#entry-edit-content");
    await page.waitForTimeout(1200);
    const state = await page.evaluate(() => {
      const box = document.getElementById("entry-edit-content");
      const wrap = box ? box.closest(".note-surface") : null;
      return {
        wrapped: !!wrap,
        size: wrap ? wrap.className : null,
        value: box ? box.value : null,
        kind: box ? asSurface(box).kind : null,
      };
    });
    ok("the edit form mounts the same surface", state.wrapped && state.kind === "codemirror",
      JSON.stringify(state));
    ok("the edit form's surface is the inline size",
      state.size && state.size.includes("note-surface-inline"), state.size);
  } else {
    ok("the edit form opened", false, `opener: ${opened}`);
  }

  // --- 8b: the graph's two note boxes and the two Write-with-AI panes ------
  //
  // Each of these had a bare textarea. What is measured is the same three
  // things in each: the engine mounts, the textarea under it still carries
  // the text, and what the box is for still decides the size and whether the
  // markdown renders (the thoughts pane deliberately does not).
  const others = [
    { id: "draft-text", live: true },
    { id: "draft-thoughts", live: false },
    { id: "graph-popup-content", live: true },
    { id: "graph-new-content", live: true },
  ];
  for (const box of others) {
    // The page's CSP forbids `unsafe-eval`, so an opener cannot be shipped in
    // as a function string: the branch goes inside the evaluate instead.
    await page.evaluate((id) => {
      if (id.startsWith("draft")) {
        switchTab("notes");
        if (typeof showNotesSection === "function") showNotesSection("writing-room");
        return;
      }
      switchTab("graph");
      const panel = document.getElementById(
        id === "graph-popup-content" ? "graph-popup" : "graph-new"
      );
      if (panel) panel.classList.remove("hidden");
    }, box.id).catch(() => {});
    await page.waitForTimeout(700);
    const reachable = await page.evaluate((id) => {
      const el = document.getElementById(id);
      return !!el && !!el.offsetParent;
    }, box.id);
    if (!reachable) {
      ok(`${box.id} is reachable to measure`, false, "not on screen in this sandbox");
      continue;
    }
    await page.click(`#${box.id}`);
    await page.waitForTimeout(1200);
    await page.keyboard.type("a **word** here");
    await page.waitForTimeout(400);
    const state = await page.evaluate((id) => {
      const el = document.getElementById(id);
      const wrap = el.closest(".note-surface");
      return {
        mounted: !!wrap,
        value: el.value,
        kind: asSurface(el).kind,
        rendered: wrap ? !!wrap.querySelector(".cm-md-strong") : false,
        lines: wrap ? [...wrap.querySelectorAll(".cm-line")].map((l) => l.textContent).join("|") : null,
      };
    }, box.id);
    ok(`${box.id} mounts the surface and keeps its value`,
      state.mounted && state.kind === "codemirror" && state.value.includes("**word**"),
      JSON.stringify(state));
    // The caret is in the line it typed, so Live reveals its own syntax
    // there: what this reads is whether the decorations exist at all, which
    // is the difference between the draft (Live on) and the thoughts pane
    // above it (Live off, the plan's own split).
    ok(`${box.id} renders markdown where it should (${box.live})`,
      state.rendered === box.live, `rendered ${state.rendered}`);
  }

  console.log(`console errors: ${errors.length}${errors.length ? " " + JSON.stringify(errors.slice(0, 3)) : ""}`);
  if (errors.length) failures += 1;
  await browser.close();
  console.log(failures ? `FAIL (${failures})` : "ALL PASS");
  process.exit(failures ? 1 : 0);
})();
