// code-colour.js: colour for a fenced code block (the owner, 2026-11-10).
//
// Lazy (lazy-entries.js `codeColour`): navigation.js asks for it only when a
// rendered fence names a language. The parsers are the document editor's own
// vendored CodeMirror bundle, fetched here only if the Documents tab has not
// already warmed it; the colours are `code-colour-lazy.css`, from the same
// tokens as the editor, so both themes follow. Nothing here writes markup:
// the block's text is split into text nodes and spans, so the characters, and
// so Copy and Save, are the ones the renderer kept.

(() => {
  const CODE_COLOUR_MAX = 20000;

  //: A fence's word, folded to the bundle's name for its mode.
  const CODE_COLOUR_NAMES = {
    js: "js", javascript: "js", jsx: "js", mjs: "js", ts: "ts", typescript: "ts", tsx: "ts",
    py: "py", python: "py", css: "css", html: "html", htm: "html", json: "json", jsonc: "json",
    yaml: "yaml", yml: "yaml", md: "md", markdown: "md",
    bash: "bash", sh: "bash", shell: "bash", zsh: "bash", console: "bash",
    sql: "sql", toml: "toml", go: "go", golang: "go", rs: "rust", rust: "rust",
    c: "c", h: "c", cpp: "cpp", "c++": "cpp", cc: "cpp", hpp: "cpp", cs: "cs", csharp: "cs",
    java: "java", kt: "kotlin", kotlin: "kotlin", rb: "ruby", ruby: "ruby",
    xml: "xml", svg: "xml", swift: "swift", r: "r", ini: "ini", properties: "ini",
    diff: "diff", patch: "diff", dockerfile: "dockerfile", docker: "dockerfile",
  };

  let codeColourLoad = null;

  //: The vendored bundle, once: the editor's loader when the Documents code is
  //: here, else the same script tag, so two callers never inject two.
  function codeColourEngine() {
    if (window.CM6) return Promise.resolve(window.CM6);
    if (typeof loadCodeMirror === "function") return loadCodeMirror();
    codeColourLoad ??= new Promise((resolve) => {
      const script = document.createElement("script");
      script.src = "/vendor/codemirror/codemirror.min.js";
      script.async = true;
      script.addEventListener("load", () => resolve(window.CM6 || null));
      script.addEventListener("error", () => resolve(null));
      document.head.appendChild(script);
    });
    return codeColourLoad;
  }

  //: The parser for a fence word, or null for one the bundle has no mode for
  //: (the block then stays plain: a wrong colouring is worse than none).
  function codeColourParser(CM, word) {
    const stream = (mode) => (mode ? CM.language.StreamLanguage.define(mode) : null);
    switch (CODE_COLOUR_NAMES[String(word).toLowerCase()]) {
      case "js": return CM.javascript.javascript({ jsx: true }).language;
      case "ts": return CM.javascript.javascript({ typescript: true }).language;
      case "py": return CM.python.python().language;
      case "css": return CM.css.css().language;
      case "html": return CM.html.html().language;
      case "json": return CM.json.json().language;
      case "yaml": return CM.yaml.yaml().language;
      case "md": return CM.markdown.markdown({ base: CM.markdown.markdownLanguage }).language;
      case "bash": return stream(CM.shell);
      case "sql": return stream(CM.standardSQL);
      case "toml": return stream(CM.toml);
      case "go": return stream(CM.go);
      case "rust": return stream(CM.rust);
      case "c": return stream(CM.c);
      case "cpp": return stream(CM.cpp);
      case "cs": return stream(CM.csharp);
      case "java": return stream(CM.java);
      case "kotlin": return stream(CM.kotlin);
      case "ruby": return stream(CM.ruby);
      case "xml": return stream(CM.xml);
      case "swift": return stream(CM.swift);
      case "r": return stream(CM.r);
      case "ini": return stream(CM.properties);
      case "diff": return stream(CM.diff);
      case "dockerfile": return stream(CM.dockerFile);
      default: return null;
    }
  }

  //: Replace the code element's text with the same text in spans. False when
  //: there is nothing to colour or the text changed under us.
  function codeColourFill(CM, codeEl, text, word) {
    const language = codeColourParser(CM, word);
    if (!language || codeEl.textContent !== text) return false;
    const tree = language.parser.parse(text);
    const frag = document.createDocumentFragment();
    let at = 0;
    const put = (to, cls) => {
      if (to <= at) return;
      const piece = text.slice(at, to);
      if (cls) {
        const span = document.createElement("span");
        span.className = cls;
        span.textContent = piece;
        frag.appendChild(span);
      } else {
        frag.appendChild(document.createTextNode(piece));
      }
      at = to;
    };
    CM.highlight.highlightTree(tree, CM.highlight.classHighlighter, (from, to, cls) => {
      put(from, "");
      put(to, cls);
    });
    put(text.length, "");
    codeEl.replaceChildren(frag);
    return true;
  }

  //: Called by navigation.js after a settle (a streaming reply draws again per
  //: chunk; a block thrown away is not coloured).
  const colourBlock = async (block) => {
    const codeEl = block.querySelector("pre code[data-lang]");
    if (!codeEl || codeEl.dataset.coloured) return;
    const text = codeEl.textContent;
    if (!text || text.length > CODE_COLOUR_MAX) return;
    const CM = await codeColourEngine();
    if (!CM || !block.isConnected) return;
    try {
      if (codeColourFill(CM, codeEl, text, codeEl.dataset.lang)) codeEl.dataset.coloured = "1";
    } catch {
      //: A parser that throws leaves the plain block, which is still right.
    }
  };
  //: No global name (the shared scope only goes down): navigation.js sends
  //: this event from the block once the module is in, and it bubbles here.
  document.addEventListener("codecolour", (event) => colourBlock(event.target));
})();
