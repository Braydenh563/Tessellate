// The "/" menu draws icons, not characters, and so does a rendered callout.
//
// DOCUMENTS_PLAN 18b. The eight callout kinds carried emoji in `CALLOUT_KINDS`
// (editor.js), read by two places: the "/" menu built a command per kind with
// the emoji in its label, and `renderMarkdown` put the same emoji at the head
// of every callout in every note and document. The menu row was also the only
// menu in the app that set its label with `textContent` rather than through
// `setLabel`, which is why a `ph:` token could not be written there and an
// emoji was reached for instead.
//
// `tests/test_no_glyph_icons.py` holds the characters. This holds the render:
// a token that reaches the DOM as the literal text "ph:note Note box" passes
// every lint and is visibly broken, which is the failure mode a string swap
// invites and the one thing a probe has to check.
const { boot } = require("./lib.js");

let failures = 0;
function ok(label, pass, detail) {
  console.log(`${pass ? "PASS" : "FAIL"}  ${label}  — ${detail}`);
  if (!pass) failures += 1;
}

(async () => {
  const { page, browser } = await boot({ viewport: { width: 1440, height: 900 } });

  await page.evaluate(() => switchTab("notes"));
  await page.waitForTimeout(900);
  //: The sub-tab is pressed rather than called: Notes opens on "Your notes"
  //: and the composer is not in the DOM at all until Capture is chosen, so a
  //: probe that only switches tab finds no textarea to type into.
  await page.evaluate(() => {
    const btn = [...document.querySelectorAll("#notes-subtabs button")]
      .find((b) => /capture/i.test(b.textContent));
    if (btn) btn.click();
  });
  await page.waitForTimeout(800);
  //: Typed for real, not dispatched. The menu opens from a document-level
  //: `input` listener that asks `editorSurfaceFor(event.target)` which of
  //: `EDITOR_SURFACES` the caret is in, so a synthetic event on any other
  //: textarea is ignored, which is what "0 rows" meant the first time.
  const box = (await page.$(".cm-editor .cm-content")) || (await page.$("#entry-content"));
  if (!box) {
    ok("the note composer is on screen", false, "#entry-content not found");
    await browser.close();
    process.exit(1);
  }
  await box.click();
  await page.keyboard.type("/");
  //: Waited for, not slept: the first "/" asks for the editor bundle (editor.js
  //: `editorSurfaceFor`) and the menu opens when it arrives, which on a loaded
  //: machine is longer than any fixed pause.
  await page.waitForSelector(".editor-menu-item", { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(300);
  const menu = await page.evaluate(() => {
    const rows = [...document.querySelectorAll(".editor-menu-item")];
    //: The icon sits in the row's tile since the block menu's redesign
    //: (INBOX 421 b), the name beside it; both are read from the row.
    const labels = rows.map((r) => r.querySelector(".rich-picker-label"));
    const tiles = rows.map((r) => r.querySelector(".rich-picker-tile"));
    return {
      rows: rows.length,
      withIcon: tiles.filter((l) => l && l.querySelector("i.ph")).length,
      literal: labels.filter((l) => l && /ph:[a-z-]/.test(l.textContent)).length,
      //: Every row in this menu is an icon and words. A row whose text opens
      //: with a character outside ASCII is drawing its own icon, which is the
      //: thing DOCUMENTS_PLAN 18b took out of thirty-eight of them.
      glyph: labels.filter((l) => l && /^[^\x20-\x7e]/.test(l.textContent.trim())).length,
      sample: labels.slice(0, 5).map((l, i) => (l ? `${tiles[i]?.querySelector("i.ph")?.className || "-"}|${l.textContent.trim()}` : "-")),
    };
  });
  if (menu.error) {
    ok("the slash menu opens", false, menu.error);
  } else {
    ok("the slash menu opens with rows", menu.rows > 4, `${menu.rows} rows`);
    ok(
      "no row prints an icon token as text",
      menu.literal === 0,
      `${menu.literal} of ${menu.rows} rows show a literal ph: token`
    );
    ok(
      "every row draws a Phosphor icon",
      menu.withIcon === menu.rows,
      `${menu.withIcon} of ${menu.rows} rows carry an <i class="ph">; first rows ${menu.sample.join(" / ")}`
    );
    ok(
      "no row draws a typed character where an icon belongs",
      menu.glyph === 0,
      `${menu.glyph} of ${menu.rows} rows open with a character outside ASCII`
    );

  }

  //: 18c, the two routes that are not "already know that / does something".
  //: Escape first, so the menu this opens is a fresh one.
  await page.keyboard.press("Escape");
  await page.evaluate(() => {
    const box = document.getElementById("entry-content");
    box.value = "";
    box.dispatchEvent(new InputEvent("input", { bubbles: true }));
  });
  await page.waitForTimeout(300);
  const hint = await page.evaluate(() =>
    Object.keys(EDITOR_SURFACES)
      .map((id) => document.getElementById(id))
      .filter((el) => el && el.tagName === "TEXTAREA")
      .map((el) => `${el.id}:${/Press \/ /.test(el.getAttribute("placeholder") || "") ? "hinted" : "SILENT"}`)
  );
  ok(
    "every editing surface says in its placeholder that / opens something",
    hint.length > 0 && hint.every((h) => h.endsWith("hinted")),
    hint.join(" ")
  );

  //: The note composer may have the editor engine mounted over it, in which
  //: case the textarea is behind a `.cm-content` that takes the pointer. Both
  //: are the same surface to `editorSurfaceFor`; only the click target differs.
  const editable = await page.$(".cm-editor .cm-content");
  if (editable) await editable.click();
  else await page.click("#entry-content");
  await page.keyboard.down("Control");
  await page.keyboard.press("/");
  await page.keyboard.up("Control");
  await page.waitForTimeout(500);
  const byChord = await page.evaluate(() => ({
    rows: document.querySelectorAll(".editor-menu-item").length,
    open: editorMenuState.open,
    listed: typeof shortcuts === "object" && !!shortcuts.editorMenu,
  }));
  ok(
    "and the menu opens without typing a slash into the text",
    byChord.open && byChord.rows > 4,
    `open=${byChord.open}, ${byChord.rows} rows`
  );
  ok(
    "the chord is in the rebindable shortcut table, so it is in the cheat sheet",
    byChord.listed,
    `shortcuts.editorMenu present: ${byChord.listed}`
  );
  await page.keyboard.press("Escape");

  //: The other reader of the same table: a callout rendered into a note.
  const callout = await page.evaluate(async () => {
    const host = document.createElement("div");
    document.body.appendChild(host);
    renderMarkdown(host, "> [!warning] Careful\n> Mind the step\n");
    const head = host.querySelector(".callout-head");
    const out = head
      ? {
          icon: head.querySelector("i.ph")?.className || null,
          text: head.textContent.trim(),
        }
      : { icon: null, text: "(no callout rendered)" };
    host.remove();
    return out;
  });
  ok(
    "a rendered callout heads with an icon, not a character",
    !!callout.icon && !/ph:/.test(callout.text),
    `icon ${callout.icon}, head text ${JSON.stringify(callout.text)}`
  );

  await browser.close();
  console.log(failures ? `FAILURES: ${failures}` : "ALL PASS");
  process.exit(failures ? 1 : 0);
})();
