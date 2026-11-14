// L-ui-modernisation-49: forced colours and 200% zoom over the seven tabs.
// Forced colours (Windows High Contrast) drops box-shadow and background
// images, so a control drawn only by them vanishes, and a focus ring drawn
// with box-shadow is gone. Checked per tab: each visible button or input has a
// border, words, an icon glyph or an outline when focused. 200% zoom of a
// 1440x900 window is a 720x450 CSS viewport: the page must not scroll sideways
// and no button label may be cut.
//   BASE=http://127.0.0.1:8781 node scratchpad/ui-sweeps/forcedzoom.js   (exit 1 on a finding)
const { boot } = require("./lib");

const TABS = ["dashboard", "notes", "library", "graph", "timeline", "chat", "reminders"];

async function tab(page, t) {
  await page.evaluate((t) => document.querySelector(`#tab-bar [data-tab="${t}"]`)?.click(), t);
  await page.waitForTimeout(1200);
}

(async () => {
  const findings = [];
  {
    const { browser, page } = await boot({ forcedColors: "active" });
    for (const t of TABS) {
      await tab(page, t);
      const r = await page.evaluate(() => {
        const seen = (el) => { const b = el.getBoundingClientRect(); return b.width > 4 && b.height > 4 && b.bottom > 0 && b.top < innerHeight && getComputedStyle(el).visibility !== "hidden"; };
        const bare = [], ringless = [];
        const els = [...document.querySelectorAll("button, [role=button], input:not([type=hidden]), select, textarea")].filter(seen);
        for (const el of els) {
          const s = getComputedStyle(el);
          const border = ["Top", "Right", "Bottom", "Left"].some((k) => parseFloat(s[`border${k}Width`]) > 0 && s[`border${k}Style`] !== "none");
          const words = (el.innerText || el.value || el.placeholder || "").trim().length > 0;
          const glyph = !!el.querySelector("i.ph, svg, img, canvas") || /^ph\b|\bph-/.test(el.className);
          if (!border && !words && !glyph) bare.push(el.id || el.className.toString().slice(0, 40));
        }
        for (const el of els.slice(0, 40)) {
          el.focus({ focusVisible: true });
          if (document.activeElement !== el) continue;
          const s = getComputedStyle(el);
          if ((s.outlineStyle === "none" || parseFloat(s.outlineWidth) === 0) && !el.matches(":focus-visible")) continue;
          const ringed = (n) => { const t = getComputedStyle(n); return t.outlineStyle !== "none" && parseFloat(t.outlineWidth) > 0; };
          //: A field whose box is its wrapper (a search field, the chat composer) rings the wrapper.
          let up = el, wrapRing = false;
          for (let i = 0; i < 3 && up.parentElement; i++) { up = up.parentElement; if (up.matches(":focus-within") && ringed(up)) { wrapRing = true; break; } }
          if (!ringed(el) && !wrapRing) ringless.push(el.id || el.className.toString().slice(0, 40));
        }
        document.activeElement?.blur();
        return { controls: els.length, bare, ringless };
      });
      console.log(`forced ${t}: ${r.controls} controls, bare ${r.bare.length}, no focus outline ${r.ringless.length}`);
      for (const b of r.bare) findings.push(`forced ${t}: a control with no border, words or icon: ${b}`);
      for (const b of r.ringless) findings.push(`forced ${t}: focus shows no outline: ${b}`);
    }
    await browser.close();
  }
  {
    const { browser, page } = await boot({ viewport: { width: 720, height: 450 }, scale: 2 });
    for (const t of TABS) {
      await tab(page, t);
      const r = await page.evaluate(() => {
        const side = document.documentElement.scrollWidth - innerWidth;
        const cut = [...document.querySelectorAll("button")].filter((el) => {
          const b = el.getBoundingClientRect();
          if (b.width < 4 || b.bottom < 0 || b.top > innerHeight || !el.innerText.trim()) return false;
          const s = getComputedStyle(el);
          return s.overflow !== "visible" && el.scrollWidth > el.clientWidth + 1 && s.textOverflow !== "ellipsis" && !el.title;
        }).map((el) => el.id || el.innerText.trim().slice(0, 30));
        return { side, cut };
      });
      console.log(`zoom ${t}: sideways ${r.side}px, cut labels ${r.cut.length}`);
      if (r.side > 0) findings.push(`zoom ${t}: the page scrolls sideways by ${r.side}px`);
      for (const c of r.cut) findings.push(`zoom ${t}: a cut label with no ellipsis or title: ${c}`);
    }
    await browser.close();
  }
  for (const f of findings) console.log(`FAIL ${f}`);
  console.log(findings.length ? `${findings.length} findings` : "PASS: 0 findings");
  process.exit(findings.length ? 1 : 0);
})();
