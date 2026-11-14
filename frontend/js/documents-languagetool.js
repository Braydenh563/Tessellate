// documents-languagetool.js: LanguageTool's findings beside Harper's (INBOX 1731 (f)).
//
// LanguageTool is an optional download (Settings, Packages). When it is not
// installed the server says so once and this file asks nothing more for the
// session; when it is, the text goes to a program on this computer (loopback,
// never beyond) and its grammar matches are merged with Harper's lints. A
// match on a span Harper already has is dropped, so one problem is one
// underline. Loaded in the Library bundle after documents-prose.js; what other
// files call is `docSpell.languageTool`.
(() => {
  //: `off`: the server said it is not installed (or has no Java); asked again
  //: only after a reload, which is also what installing it asks for.
  //: `warm`: the program has answered once this session; until then a check
  //: waits for Java to start (12.3 s measured), which the status line says.
  const state = { off: false, warm: false };
  const STARTING = "Starting the second grammar checker, which takes a few seconds the first time.";
  const LANGUAGE = { us: "en-US", uk: "en-GB", au: "en-AU", ca: "en-CA" };

  //: A match as a Harper lint, so the rest of the pipeline treats both alike.
  function asLint(match) {
    return {
      kind: "LanguageTool",
      start: match.start,
      end: match.end,
      message: match.message,
      suggestions: (match.suggestions || []).map((text) => ({ kind: "Replace", text })),
    };
  }

  function overlaps(a, b) {
    return a.start < b.end && b.start < a.end;
  }

  //: What the last check learned, by paragraph text: a paragraph that did not
  //: change is not sent again. `null` until a first check (which sends it all).
  let seen = null;

  //: The paragraphs of `text` as {text, at}; blank ones carry nothing to check.
  function paragraphs(text) {
    const out = [];
    let at = 0;
    for (const part of text.split("\n")) {
      if (part.trim()) out.push({ text: part, at });
      at += part.length + 1;
    }
    return out;
  }

  async function ask(text, language) {
    //: A second opinion while typing, not a person's action: a failed check
    //: returns null and the caller keeps Harper's lints alone.
    let body;
    const line = !state.warm && $("doc-status");
    const told = line && !line.textContent && !line.classList.contains("error");
    if (told) line.textContent = STARTING;
    try {
      body = await apiJson("/grammar/languagetool", { method: "POST", body: JSON.stringify({ text, language }), silent: true });
    } catch {
      return null;
    } finally {
      if (told && line.textContent === STARTING) line.textContent = "";
    }
    if (body && !body.available) state.off = true;
    if (body && body.available) state.warm = true;
    return body && body.available ? body.matches || [] : null;
  }

  //: Matches for each paragraph (relative to it): remembered ones for those
  //: unchanged since the last check, one request for the touched ones joined by
  //: newlines (the whole text when none is remembered), their matches mapped
  //: back by offset. Null when the ask failed.
  async function matchesByParagraph(text, paras, language) {
    const known = seen && seen.language === language ? seen.byText : new Map();
    const touched = paras.filter((p, i) => !known.has(p.text) && paras.findIndex((q) => q.text === p.text) === i);
    const fresh = new Map();
    if (touched.length) {
      const whole = !known.size;
      let joinedAt = 0;
      for (const p of touched) {
        p.joined = whole ? p.at : joinedAt;
        joinedAt += p.text.length + 1;
        fresh.set(p.text, []);
      }
      const found = await ask(whole ? text : touched.map((p) => p.text).join("\n"), language);
      if (found === null) return null;
      for (const m of found) {
        const p = touched.find((q) => m.start >= q.joined && m.start < q.joined + q.text.length + 1);
        if (!p || m.end > p.joined + p.text.length) continue;
        fresh.get(p.text).push({ ...m, start: m.start - p.joined, end: m.end - p.joined });
      }
    }
    seen = { language, byText: new Map(paras.map((p) => [p.text, known.get(p.text) || fresh.get(p.text)])) };
    return seen.byText;
  }

  //: Harper's lints plus LanguageTool's that no Harper lint overlaps. Null in,
  //: null out (no checker); a failed or absent second opinion changes nothing.
  async function merge(lints, text) {
    if (lints === null || state.off) return lints;
    const language = LANGUAGE[docSpellingVariant()] || "en-US";
    const paras = paragraphs(text);
    const byText = await matchesByParagraph(text, paras, language);
    if (!byText) return lints;
    const all = [];
    for (const p of paras) {
      for (const m of byText.get(p.text)) all.push({ ...m, start: m.start + p.at, end: m.end + p.at });
    }
    //: Not over Harper's, and not over one already kept: LanguageTool can
    //: report two rules on the same words, which would be two underlines.
    const extra = [];
    for (const lint of all.map(asLint)) {
      if (!lints.some((own) => overlaps(own, lint)) && !extra.some((own) => overlaps(own, lint))) extra.push(lint);
    }
    return lints.concat(extra);
  }

  //: On the spelling object, which is the page's one handle on the second opinions.
  window.docSpell.languageTool = merge;
})();
