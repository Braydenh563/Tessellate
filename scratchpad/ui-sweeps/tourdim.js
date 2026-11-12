// The tour's dim covers the whole window, including the scrollbar gutter.
//
// The owner, twice, with screenshots: "I pressed next after starting the tour
// and then the popup dissapeared and everything dimmed except for a small
// strip on the right", and again after trying it in a browser rather than the
// desktop app, which ruled out a stale cache.
//
// The four dim panels are `position: fixed`, so they are laid out against the
// window, but they were sized from `document.documentElement.clientWidth`,
// which stops at the scrollbar. The gutter was left uncovered: a bright band
// at the right edge, the full height of the window.
//
// **Headless Chromium cannot see this on its own**: it draws overlay
// scrollbars that take no space, so clientWidth and innerWidth agree and the
// gutter is 0. That is why every earlier sweep of this surface passed. So this
// probe forces a classic scrollbar, which is what Windows gives, and then
// measures that nothing is left uncovered.
//
// **And the first two versions of this probe measured the wrong thing**, which
// is why the owner reported it a third time ("the whole tour is completely and
// utterly broken", 2026-09-21). The four panels were transparent: the dim was
// `.tour-spot`'s own `box-shadow`, spread 100vmax, and a rectangle check over
// the panels could not see it at all. The panels now paint the dim
// (04-chat-dock-appearance.css), so the rectangle check below is finally a
// check of the dim, and the pixel pass after it proves the rectangles and the
// paint agree. The second pass also catches what no rectangle can: the step
// card was a translucent `.card`, and the dashboard clock read straight
// through the step's own text.
const { boot } = require("./lib.js");

let failures = 0;
function ok(label, pass, detail) {
  console.log(`${pass ? "PASS" : "FAIL"}  ${label}  — ${detail}`);
  if (!pass) failures += 1;
}

(async () => {
  const { page, browser } = await boot({ viewport: { width: 1400, height: 900 } });

  // A page that needs a scrollbar. Set through `el.style.x =` rather than an
  // injected stylesheet: this app's content security policy refuses inline
  // styles outright, which is CLAUDE.md's "a policy silently refusing the
  // work", and `page.addStyleTag` is exactly that refusal.
  await page.evaluate(() => {
    switchTab("dashboard");
    document.documentElement.style.overflowY = "scroll";
  });
  await page.waitForTimeout(700);

  const out = await page.evaluate(async () => {
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    openTour("basics");
    await wait(800);
    document.getElementById("tour-next").click();
    await wait(800);

    const de = document.documentElement;
    const win = { w: window.innerWidth, h: window.innerHeight };
    const boxes = ["tour-block-top", "tour-block-bottom", "tour-block-left", "tour-block-right"]
      .map((id) => document.getElementById(id).getBoundingClientRect());
    const spot = document.getElementById("tour-spot").getBoundingClientRect();

    // Sample the window on a grid. Every point is either inside the cut-out
    // (the one place meant to stay bright) or inside a dim panel.
    const holes = [];
    for (let x = 2; x < win.w; x += 7) {
      for (let y = 2; y < win.h; y += 7) {
        const lit = x >= spot.left && x <= spot.right && y >= spot.top && y <= spot.bottom;
        if (lit) continue;
        const covered = boxes.some(
          (b) => x >= b.left && x <= b.right && y >= b.top && y <= b.bottom && b.width > 0 && b.height > 0
        );
        if (!covered) holes.push(`${x},${y}`);
      }
    }
    return {
      gutter: win.w - de.clientWidth,
      clientWidth: de.clientWidth,
      innerWidth: win.w,
      holes: holes.length,
      firstHoles: holes.slice(0, 4),
      cardHidden: document.getElementById("tour-card").classList.contains("hidden"),
      //: The contract itself, read off the running source, because a browser
      //: with overlay scrollbars cannot demonstrate it by measurement.
      sizedFromWindow: /innerWidth/.test(openTour.inspect.blockPanels.toString()),
    };
  });

  //: **Reported, not asserted, and the distinction matters.** If this browser
  //: draws overlay scrollbars the gutter is 0, the two widths agree, and the
  //: coverage check below passes whether or not the fix is present. So the
  //: gutter is printed every run: a 0 here means this run did not exercise the
  //: owner's case, and the source check that follows is what stands in for it.
  console.log(
    `      gutter ${out.gutter}px (client ${out.clientWidth} of window ${out.innerWidth})` +
      (out.gutter === 0 ? "  <- overlay scrollbars: the gutter case is not exercised" : "")
  );
  ok(
    "the dim is sized from the window, not from the content box",
    out.sizedFromWindow,
    out.sizedFromWindow
      ? "tourBlockPanels reads innerWidth"
      : "tourBlockPanels reads only clientWidth, so a scrollbar gutter stays bright"
  );
  ok(
    "no part of the window is left undimmed outside the cut-out",
    out.holes === 0,
    out.holes ? `${out.holes} uncovered points, first ${out.firstHoles.join(" ")}` : "0 uncovered points"
  );
  ok("and the card is still on screen", !out.cardHidden, `hidden=${out.cardHidden}`);

  //: The paint, not the geometry, and asked of the hit stack rather than of
  //: pixels. A rectangle that is laid out correctly and paints nothing passes
  //: every check above; so does one that something else draws over, which is
  //: the shape of the owner's band at the right edge. `elementsFromPoint`
  //: answers both at once: at every point outside the cut-out, a painted
  //: `.tour-block-panel` has to be in the stack, and it has to be above
  //: whatever of the page is under it (the array is front to back, so the
  //: panel's index against the first page element is the whole test).
  const paint = await page.evaluate(() => {
    const spot = document.getElementById("tour-spot").getBoundingClientRect();
    const card = document.getElementById("tour-card").getBoundingClientRect();
    const w = window.innerWidth;
    const h = window.innerHeight;
    const near = (r, x, y, pad) =>
      x >= r.left - pad && x <= r.right + pad && y >= r.top - pad && y <= r.bottom + pad;

    let sampled = 0;
    const bare = [];
    const buried = [];
    let minAlpha = 1;
    for (let x = 3; x < w - 3; x += 9) {
      for (let y = 3; y < h - 3; y += 9) {
        if (near(spot, x, y, 6) || near(card, x, y, 2)) continue;
        sampled += 1;
        const stack = document.elementsFromPoint(x, y);
        const at = stack.findIndex((el) => el.classList.contains("tour-block-panel"));
        if (at < 0) {
          if (bare.length < 5) bare.push(`${x},${y}`);
          continue;
        }
        // Nothing of the page may sit in front of the panel.
        const front = stack.slice(0, at).filter((el) => !el.id.startsWith("tour-"));
        if (front.length && buried.length < 5) buried.push(`${x},${y} under ${front[0].id || front[0].className}`);
        const bg = getComputedStyle(stack[at]).backgroundColor;
        //: Chromium serialises a mixed colour as `color(srgb r g b / a)`, which the
        //: rgba-only parse read as alpha 0 (L-general-14).
        const m = bg.match(/rgba?\(([^)]+)\)/);
        const c = bg.match(/^color\([^/)]+(?:\/\s*([\d.]+))?\)$/);
        const a = m ? (m[1].split(",")[3] === undefined ? 1 : parseFloat(m[1].split(",")[3])) : c ? (c[1] === undefined ? 1 : parseFloat(c[1])) : 0;
        if (a < minAlpha) minAlpha = a;
      }
    }
    return { sampled, bare, buried, minAlpha };
  });
  ok(
    "a painted dim panel is in front at every point outside the cut-out",
    paint.sampled > 500 && paint.bare.length === 0 && paint.buried.length === 0,
    `${paint.sampled} points; ${paint.bare.length} with no panel${paint.bare.length ? " (" + paint.bare.join(" ") + ")" : ""}; ` +
      `${paint.buried.length} with the page in front${paint.buried.length ? " (" + paint.buried.join("; ") + ")" : ""}`
  );
  ok(
    "and the panel it finds actually paints something",
    paint.minAlpha > 0.2,
    `smallest panel background alpha ${paint.minAlpha}`
  );

  //: The card's own ground. A `.card` is a 55% fill, and over a dimmed page
  //: that let the dashboard clock read through the step text (measured
  //: 2026-09-21, step 4 of the basics tour at 1400x900).
  const cardOpaque = await page.evaluate(() => {
    const el = document.getElementById("tour-card");
    const cs = getComputedStyle(el);
    // Opaque in either notation Chromium serialises: `rgb(...)` (never
    // `rgba`), or `color(srgb r g b)` with no `/ alpha`, which is what a
    // `color-mix` in the ground computes to. The first draft accepted only
    // `rgb(` and failed a solid white card as `color(srgb 1 1 1)`.
    const bg = cs.backgroundColor;
    return { bg, img: cs.backgroundImage, solid: /^rgb\(/.test(bg) || /^color\(srgb [^/]+\)$/.test(bg) };
  });
  ok(
    "the step card has an opaque ground",
    cardOpaque.solid,
    `background-color ${cardOpaque.bg}`
  );

  await browser.close();
  console.log(failures ? `FAILURES: ${failures}` : "ALL PASS");
  process.exit(failures ? 1 : 0);
})();
