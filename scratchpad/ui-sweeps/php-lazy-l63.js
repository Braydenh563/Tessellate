// L-documents-63: a .php file fetches php.min.js on its first open and then highlights; a .py file fetches nothing of it.
// Usage (a fresh data dir, so no .php document is restored on boot): BASE=http://127.0.0.1:8819 node php-lazy-l63.js
const { boot } = require("./lib.js");
let bad = 0;
const ok = (n, c, d) => { if (!c) bad += 1; console.log(`${c ? "PASS" : "FAIL"}  ${n}  - ${JSON.stringify(d)}`); };

(async () => {
  const { browser, page } = await boot();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const phpFetches = [];
  page.on("request", (r) => r.url().includes("php.min.js") && phpFetches.push(r.url()));
  await page.evaluate(() => switchTab("documents"));
  await page.waitForTimeout(2000);

  const open = async (title, fileType, content) => {
    await page.evaluate(async ([t, f, c]) => {
      const d = await apiJson("/documents", { method: "POST", body: JSON.stringify({ title: t, content: c, file_type: f }) });
      await loadDocuments(d.id);
    }, [title, fileType, content]);
    await page.waitForTimeout(2000);
  };
  const classes = () => page.evaluate(() => {
    const set = new Set();
    for (const sp of document.querySelectorAll("#doc-editor .cm-content span")) {
      for (const c of sp.classList) if (/^(ͼ|cm-)/.test(c) && !/^cm-bracket/.test(c)) set.add(c);
    }
    const ink = getComputedStyle(document.querySelector("#doc-editor .cm-content")).color;
    const colours = new Set();
    for (const sp of document.querySelectorAll("#doc-editor .cm-content span")) {
      if (/^cm-bracket/.test(sp.className)) continue;
      const c = getComputedStyle(sp).color;
      if (c !== ink) colours.add(c);
    }
    return { classes: set.size, colours: colours.size, php: typeof window.CM6.php, ext: docFileType().ext };
  });

  await open("lazy-a.py", "py", "def f(x):\n    return x + 1\n");
  const py = await classes();
  ok("a .py file fetches no php.min.js and CM6.php is not defined", phpFetches.length === 0 && py.php === "undefined" && py.ext === "py", { phpFetches, py });

  await open("lazy-b.php", "php", "<?php\nfunction greet($name) { return \"hi \" . $name; }\necho greet(\"a\"); // done\n");
  const php = await classes();
  ok("the .php file fetched php.min.js once", phpFetches.length === 1, phpFetches);
  ok("the .php file has highlighted tokens (distinct colours)", php.php === "object" && php.colours >= 3, php);

  await open("lazy-c.php", "php", "<?php echo 1; ?>\n");
  ok("a second .php file does not fetch it again", phpFetches.length === 1, phpFetches);

  // A failed load: drop the global, make the loader fail, open a php file; expect the toast with Try again.
  // (The service worker answers fetches past page.route, so the failure is the loader resolving false, which is what
  // lazyScript does on a script error.)
  await page.evaluate(() => { delete window.CM6.php; const real = window.lazyScript; window.lazyScript = async (f) => (f.includes("php.min.js") ? false : real(f)); });
  await open("lazy-d.py", "py", "x = 1\n");
  await open("lazy-d.php", "php", "<?php echo 2; ?>\n");
  const toastText = await page.evaluate(() => { const t = [...document.querySelectorAll(".toast")].map((e) => e.textContent).join(" | "); return t.includes("The PHP highlighter could not be loaded") && t.includes("Try again") ? true : t; });
  ok("a blocked fetch leaves plain text and shows the toast with Try again", toastText === true && (await classes()).php === "undefined", { toastText });

  ok("no page errors", errors.length === 0, errors);
  await browser.close();
  process.exit(bad ? 1 : 0);
})();
