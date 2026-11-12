// DOCUMENTS_PLAN Phase 6 item 3: "the first line of text is on screen with
// the keyboard open", the one line of that phase asserted without a keyboard.
//
// **What cannot be measured here, said first.** Headless Chromium raises no
// on-screen keyboard, and nothing in this sandbox can make it. `visualViewport`
// therefore never shrinks on its own, `env(keyboard-inset-height)` is 0, and no
// run here can tell you what a real phone does when a real keyboard opens.
//
// **What can be measured, and is.** Everything between the platform's report
// and the pixels: `initKeyboardInset` reads `visualViewport` and writes
// `--keyboard-inset`; three surfaces read that token (`.chat-dock` and
// `.doc-toolbar` in 07-whiteboard-misc.css, `.thumb-bar` in 09-editor.css);
// and the phone band's layout has to keep the first line of the document above
// whatever is left of the window. So this probe stubs `visualViewport.height`
// and fires the app's own listener, which exercises the whole chain from the
// number the platform would report down to the padding that lands. The only
// thing standing in for the keyboard is the number itself.
//
// A stub is worth saying out loud: `write()` is the app's real function, the
// listener is the app's real listener, and the token, the paddings and the
// geometry that come back are the browser's own. What is fake is 336, and on a
// phone 336 is what the platform would hand over.
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => {
  if (!c) bad += 1;
  console.log(`${c ? "PASS" : "FAIL"}  ${n}${d === undefined ? "" : "  — " + d}`);
};

//: A middling phone keyboard. iOS 390-wide keyboards run 291 to 346 CSS px
//: with the prediction bar; Android's are close. The exact number does not
//: matter to any assertion below, which is the point: they are all relative.
const KEYBOARD = 336;

const DOC = ["# A page to type on", "", "The first line of text, which is the one the phase names.", ""].join("\n");

(async () => {
  const { browser, page } = await boot({
    viewport: { width: 390, height: 820 },
    hasTouch: true,
    isMobile: true,
  });
  page.on("pageerror", (e) => console.log("PAGEERROR", e.message));
  //: Chat is built when first visited; its dock is read below.
  await page.evaluate(() => switchTab("chat"));
  await page.waitForTimeout(1800);
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2400);
  await page.evaluate(async (text) => {
    const d = await apiJson("/documents", {
      method: "POST",
      body: JSON.stringify({ title: "A page to type on", content: text }),
    });
    await loadDocuments(d.id);
    setDocView("live");
  }, DOC);
  await page.waitForTimeout(2400);

  const read = () =>
    page.evaluate(() => {
      const css = getComputedStyle(document.documentElement);
      const bar = document.querySelector(".thumb-bar");
      //: By id, not by class. `.doc-toolbar` also matches `#note-toolbar`,
      //: the capture composer's cloned strip, and this probe's first run
      //: measured that one for four assertions without noticing.
      const toolbar = document.getElementById("doc-toolbar");
      const line = document.querySelector(".cm-content .cm-line");
      const pad = (el) => (el ? Math.round(parseFloat(getComputedStyle(el).paddingBottom)) : null);
      const box = (el) => {
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return { top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height) };
      };
      return {
        token: css.getPropertyValue("--keyboard-inset").trim(),
        innerHeight: window.innerHeight,
        visual: Math.round(window.visualViewport.height),
        thumbBarShown: bar ? getComputedStyle(bar).display !== "none" : false,
        thumbBarPad: pad(bar),
        thumbBar: box(bar),
        toolbarPad: pad(toolbar),
        toolbarShown: toolbar ? getComputedStyle(toolbar).display !== "none" : false,
        toolbarCollapsed: toolbar ? toolbar.classList.contains("is-collapsed") : null,
        chatPad: pad(document.querySelector(".chat-dock")),
        firstLine: box(line),
      };
    });

  const before = await read();
  console.log("      no keyboard:", JSON.stringify(before));
  //: The floor case. A token that is anything but 0 with no keyboard is a
  //: padding every desktop pays for nothing, which is the failure mode this
  //: token had once already (`.chat-dock`'s missing base term).
  ok("the token is 0 with no keyboard", before.token === "0px", before.token);
  ok("the phone band shows the thumb bar", before.thumbBarShown === true, JSON.stringify(before.thumbBarShown));
  ok(
    "and the first line of text is on screen",
    before.firstLine && before.firstLine.top >= 0 && before.firstLine.bottom <= before.innerHeight,
    JSON.stringify(before.firstLine)
  );

  //: Now the stub. `visualViewport.height` is a getter on the instance's
  //: prototype, so it is redefined on the object itself and the app's own
  //: listener is fired the way the platform would fire it.
  await page.evaluate((kb) => {
    const vv = window.visualViewport;
    Object.defineProperty(vv, "height", {
      configurable: true,
      get: () => window.innerHeight - kb,
    });
    Object.defineProperty(vv, "offsetTop", { configurable: true, get: () => 0 });
    vv.dispatchEvent(new Event("resize"));
  }, KEYBOARD);
  await page.waitForTimeout(500);

  const after = await read();
  console.log("      keyboard open:", JSON.stringify(after));
  ok("the app writes the covered strip into the token", after.token === `${KEYBOARD}px`, after.token);
  //: The three surfaces that read it. `.thumb-bar` takes the token through a
  //: `max()`, so its padding becomes the inset exactly; the two docks add it
  //: to a base term, so theirs grows by it.
  ok(
    "the thumb bar rides above the keyboard",
    //: Measured where it ends, not how: it may be lifted by its padding or
    //: by its position, and either way its foot must meet the keyboard.
    after.thumbBar && Math.abs(after.thumbBar.bottom - after.visual) <= 2,
    `bottom ${after.thumbBar && after.thumbBar.bottom} against the keyboard's edge at ${after.visual}`
  );
  ok(
    "the chat composer takes the same inset, on top of its own padding",
    after.chatPad - before.chatPad === KEYBOARD,
    `${before.chatPad}px to ${after.chatPad}px`
  );

  //: The phase's own acceptance line, measured against what is left of the
  //: window rather than against the window: with the keyboard up, the visible
  //: area ends at `innerHeight - KEYBOARD`, and the first line has to be above
  //: it or the writer is typing at something they cannot see.
  const visible = after.innerHeight - KEYBOARD;
  ok(
    "the first line of text is still inside the visible viewport",
    after.firstLine && after.firstLine.top >= 0 && after.firstLine.bottom <= visible,
    `line ${JSON.stringify(after.firstLine)} against a visible ${visible}px`
  );
  //: And the bar that rode up must not have landed on the text it belongs to.
  ok(
    "and the thumb bar does not cover it",
    after.firstLine && after.thumbBar && after.firstLine.bottom <= after.thumbBar.top,
    `line bottom ${after.firstLine && after.firstLine.bottom}, bar top ${after.thumbBar && after.thumbBar.top}`
  );

  //: Back to nothing, because a token that never comes back down is a
  //: permanent gap under the composer once the keyboard closes.
  await page.evaluate(() => {
    const vv = window.visualViewport;
    delete vv.height;
    delete vv.offsetTop;
    vv.dispatchEvent(new Event("resize"));
  });
  await page.waitForTimeout(400);
  const closed = await read();
  console.log("      keyboard closed:", JSON.stringify({ token: closed.token, thumbBarPad: closed.thumbBarPad }));
  ok("the token returns to 0 when the keyboard closes", closed.token === "0px", closed.token);
  ok(
    "and the thumb bar comes back down",
    closed.thumbBarPad === before.thumbBarPad,
    `${after.thumbBarPad}px to ${closed.thumbBarPad}px`
  );

  //: The documents formatting strip, in **both** of its states, at a width
  //: where it is on screen (below 600 the thumb bar replaces it, and at every
  //: width it is off until the head's Formatting toggle is pressed).
  //:
  //: Collapsed is not an edge case: it is the strip's default since D1, and
  //: it is where this probe found the fault. `.doc-toolbar.is-collapsed` is
  //: (0,2,0) and the rule carrying the inset was (0,1,0) in a later file, so
  //: the strip rose with the keyboard while expanded and sat under it while
  //: collapsed. Before the fix: expanded 6.4px to 342.4px, collapsed 4px to
  //: 4px. Both states are asserted here so neither can drift again.
  //:
  //: In a context of its own, not a `setViewportSize` on this one: an
  //: `isMobile` context keeps Chromium's mobile viewport, so resizing it to
  //: 820 left the phone band's rules in force and the strip `display: none`
  //: while every number read correctly, which is the sort of half-truth a
  //: sweep is supposed to stop rather than print.
  await browser.close();
  const second = await boot({ viewport: { width: 820, height: 820 } });
  const page2 = second.page;
  page2.on("pageerror", (e) => console.log("PAGEERROR", e.message));
  await page2.evaluate(() => switchTab("documents"));
  await page2.waitForTimeout(2400);
  await page2.evaluate(async (text) => {
    const d = await apiJson("/documents", {
      method: "POST",
      body: JSON.stringify({ title: "A page to type on, wide", content: text }),
    });
    await loadDocuments(d.id);
    setDocView("live");
  }, DOC);
  await page2.waitForTimeout(2400);
  //: The toggle and the measurement are two calls with a wait between them:
  //: pressing it re-renders the strip, and reading `display` in the same tick
  //: reports the state before that render (it read `none` at 820 for two runs
  //: of this probe).
  //: **Only if it is off.** Whether the strip is shown is a remembered
  //: preference, so a blind click is a toggle and not a turn-on: an earlier
  //: run of this probe left it on, and the next run's click turned it off and
  //: then reported the strip as missing. Press it until it is shown, at most
  //: twice, and say which.
  const turnedOn = await page2.evaluate(async () => {
    const el = document.getElementById("doc-toolbar");
    const shown = () => getComputedStyle(el).display !== "none";
    const was = shown();
    for (let press = 0; press < 2 && !shown(); press += 1) {
      document.getElementById("doc-format-toggle").click();
      await new Promise((r) => setTimeout(r, 700));
    }
    return { was, now: shown() };
  });
  console.log("      formatting toggle:", JSON.stringify(turnedOn));
  await page2.waitForTimeout(600);
  const strip = await page2.evaluate((kb) => {
    const el = document.getElementById("doc-toolbar");
    const pad = () => Math.round(parseFloat(getComputedStyle(el).paddingBottom) * 10) / 10;
    const vv = window.visualViewport;
    const open = (on) => {
      if (on) {
        Object.defineProperty(vv, "height", { configurable: true, get: () => window.innerHeight - kb });
        Object.defineProperty(vv, "offsetTop", { configurable: true, get: () => 0 });
      } else {
        delete vv.height;
        delete vv.offsetTop;
      }
      vv.dispatchEvent(new Event("resize"));
    };
    //: The strip is also gated on the document being previewable
    //: (`documents.js` line 135 puts `.hidden` on it for a code file), so
    //: both that and the computed display are reported rather than assumed.
    const out = { hidden: el.classList.contains("hidden"), shown: getComputedStyle(el).display !== "none" };
    //: Borrowed and put back. This probe drives `is-collapsed` by hand to
    //: reach both states, which is a class the app owns, so the state it
    //: found is restored before the last read; without that the final
    //: `display` reported this probe's own leftovers as a finding.
    const wasCollapsed = el.classList.contains("is-collapsed");
    for (const collapsed of [false, true]) {
      el.classList.toggle("is-collapsed", collapsed);
      open(false);
      const shut = pad();
      open(true);
      const up = pad();
      open(false);
      out[collapsed ? "collapsed" : "expanded"] = { shut, up };
    }
    el.classList.toggle("is-collapsed", wasCollapsed);
    //: Read again at the end: six `visualViewport` resize events have gone
    //: through the app's own listener by now, and a strip that did not
    //: survive them would be a finding of its own.
    return { ...out, shownAfterResizes: getComputedStyle(el).display !== "none" };
  }, KEYBOARD);
  console.log("      formatting strip:", JSON.stringify(strip));
  ok(
    "the formatting strip is on screen at 820 once it is turned on",
    strip.shown === true && strip.hidden === false,
    `shown ${strip.shown}, hidden ${strip.hidden}`
  );
  ok(
    "and it is still there after the keyboard has opened and closed",
    strip.shownAfterResizes === true,
    `${strip.shownAfterResizes}`
  );
  //: Rounded to a tenth on both sides: `342.4 - 340` is `2.4000000000000341`
  //: in this engine, and a padding comparison is not the place to discover
  //: binary floating point.
  const gap = (a, b) => Math.round((a - b) * 10) / 10;
  ok(
    "expanded, it rises by the whole inset",
    gap(strip.expanded.up, strip.expanded.shut) === KEYBOARD,
    `${strip.expanded.shut}px to ${strip.expanded.up}px`
  );
  ok(
    "collapsed, it rises by the whole inset too",
    gap(strip.collapsed.up, strip.collapsed.shut) === KEYBOARD,
    `${strip.collapsed.shut}px to ${strip.collapsed.up}px`
  );
  //: And collapsing still buys back the height it is for: the two base terms
  //: differ by `--space-2` minus `--space-1`, keyboard or no keyboard.
  ok(
    "and collapsing still gives its height back",
    strip.collapsed.shut < strip.expanded.shut &&
      gap(strip.expanded.up, strip.collapsed.up) === gap(strip.expanded.shut, strip.collapsed.shut),
    `${strip.collapsed.shut}px against ${strip.expanded.shut}px, and ${strip.collapsed.up}px against ${strip.expanded.up}px`
  );

  console.log("NOT VERIFIED: no real on-screen keyboard exists in this sandbox.");
  console.log("  What stands in for it is the number 336 handed to the app's own listener;");
  console.log("  everything below that number is this browser's real layout.");
  console.log(bad ? `${bad} FAILURES` : "all clear");
  await second.browser.close();
  process.exit(bad ? 1 : 0);
})();
