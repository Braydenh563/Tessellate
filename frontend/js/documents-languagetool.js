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
  const state = { off: false };
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

  //: Harper's lints plus LanguageTool's that no Harper lint overlaps. Null in,
  //: null out (no checker); a failed or absent second opinion changes nothing.
  async function merge(lints, text) {
    if (lints === null || state.off) return lints;
    const variant = docSpellingVariant();
    const body = await apiJson("/grammar/languagetool", {
      method: "POST",
      body: JSON.stringify({ text, language: LANGUAGE[variant] || "en-US" }),
      silent: true,
    }).catch(() => null);
    if (!body || !body.available) {
      if (body) state.off = true;
      return lints;
    }
    const extra = (body.matches || []).map(asLint).filter((lint) => !lints.some((own) => overlaps(own, lint)));
    return lints.concat(extra);
  }

  //: On the spelling object, which is the page's one handle on the second opinions.
  window.docSpell.languageTool = merge;
})();
