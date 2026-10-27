// Audit FEAT-04: an HTML paste into a document keeps headings, emphasis,
// lists and links as Markdown; Ctrl+Shift+V keeps plain text; a code-editor
// copy (coloured spans) stays plain.
//
//   BASE=http://127.0.0.1:8844 PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers \
//   node scratchpad/ui-sweeps/mmdoc1005-richpaste.js
const { boot } = require("./lib.js");

const CASES = [
  {
    name: "web page",
    html: '<h2>Pasted title</h2><p><b>bold</b> and a <a href="https://example.com/x">link</a></p><ul><li>item one</li><li>item two<ul><li>nested</li></ul></li></ul>',
    plain: "Pasted title\nbold and a link\nitem one\nitem two\nnested",
    want: "## Pasted title\n\n**bold** and a [link](https://example.com/x)\n\n- item one\n- item two\n  - nested",
  },
  {
    name: "google docs",
    html: '<meta charset="utf-8"><b style="font-weight:normal;" id="docs-internal-guid-1"><p dir="ltr"><span style="font-weight:700;">Strong</span><span> and </span><span style="font-style:italic;">soft</span></p><ol><li><p><span>first</span></p></li><li><p><span>second</span></p></li></ol></b>',
    plain: "Strong and soft\nfirst\nsecond",
    want: "**Strong** and *soft*\n\n1. first\n2. second",
  },
  {
    name: "unsafe link and script",
    html: '<p>Click <a href="javascript:alert(1)">here</a> <script>alert(2)</script><em>now</em></p><blockquote><p>Quoted</p></blockquote><pre>code  line\n  two</pre>',
    plain: "Click here now\nQuoted\ncode line two",
    want: "Click here *now*\n\n> Quoted\n\n```\ncode  line\n  two\n```",
  },
  {
    name: "code editor copy stays plain",
    html: '<div style="color:#d4d4d4;"><div><span style="color:#569cd6;">const</span> x = 1;</div></div>',
    plain: "const x = 1;",
    want: "const x = 1;",
  },
  {
    name: "a lone bold span (dog3d-1026:7)",
    html: '<span style="font-weight:700">Heavy words</span>',
    plain: "Heavy words",
    want: "**Heavy words**",
  },
  {
    name: "a lone italic span",
    html: '<span style="font-style:italic">Soft words</span>',
    plain: "Soft words",
    want: "*Soft words*",
  },
  {
    name: "a code copy with a bold token stays plain",
    html: '<div style="font-family:Consolas,monospace;white-space:pre;"><div><span style="font-weight:bold;color:#569cd6;">const</span> x = 1;</div></div>',
    plain: "const x = 1;",
    want: "const x = 1;",
  },
  {
    name: "ctrl+shift+v stays plain",
    shift: true,
    html: "<h1>Big</h1><p><b>bold</b></p>",
    plain: "Big\nbold",
    want: "Big\nbold",
  },
];

(async () => {
  const { page, browser } = await boot();
  const errs = [];
  page.on("pageerror", (e) => errs.push(e.message));
  await page.evaluate(async () => {
    const r = await fetch("/documents", {
      method: "POST",
      headers: { "X-Auth-Token": localStorage.getItem("token") || "", "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Paste probe", content: "" }),
    });
    const doc = await r.json();
    switchTab("documents");
    await new Promise((res) => setTimeout(res, 400));
    await openDocument(doc.id);
    await new Promise((res) => setTimeout(res, 1500));
    setDocView("live");
    await new Promise((res) => setTimeout(res, 600));
  });
  const fails = [];
  for (const c of CASES) {
    await page.click(".cm-content");
    await page.keyboard.press("Control+a");
    await page.keyboard.press("Delete");
    if (c.shift) {
      // The keydown that marks the next paste plain, then the paste itself.
      await page.evaluate(() => {
        const el = document.querySelector(".cm-content");
        el.dispatchEvent(new KeyboardEvent("keydown", { key: "V", ctrlKey: true, shiftKey: true, bubbles: true }));
      });
    }
    const got = await page.evaluate(({ html, plain }) => {
      const el = document.querySelector(".cm-content");
      const dt = new DataTransfer();
      dt.setData("text/html", html);
      dt.setData("text/plain", plain);
      el.dispatchEvent(new ClipboardEvent("paste", { clipboardData: dt, bubbles: true, cancelable: true }));
      const view = el.cmView?.view || window.docCm || null;
      return document.querySelector(".cm-content").innerText.replace(/​/g, "");
    }, c);
    const text = await page.evaluate(() => (typeof docText === "function" ? docText() : null));
    const value = text ?? got;
    const ok = value.trim() === c.want;
    console.log(`${ok ? "ok  " : "FAIL"} ${c.name}: ${JSON.stringify(value.trim())}`);
    if (!ok) fails.push(c.name);
  }
  console.log("errors", errs.length, errs.slice(0, 3));
  console.log(fails.length ? "FAIL " + fails.join("; ") : "PASS");
  await browser.close();
})();
