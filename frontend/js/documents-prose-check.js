// documents-prose-check.js: the prose check, spelling, word completion and autocorrect.
// Moved out of documents.js whole (L335) and wrapped: only what other files call goes on `window`; nothing here runs at load.
(() => {
  const DOC_CONTRACTION_BASES = {
    re: new Set(["you", "we", "they", "who", "what", "there"]),
    ll: new Set(["i", "you", "we", "they", "he", "she", "it", "that", "there", "who", "what"]),
    ve: new Set(["i", "you", "we", "they", "who", "would", "could", "should", "might", "must"]),
    d: new Set(["i", "you", "we", "they", "he", "she", "it", "that", "there", "who"]),
    m: new Set(["i"]),
  };
  function docSpellContraction(lower) {
    if (/['\u2019]/.test(lower)) return null;
    if (lower.endsWith("nt") && docWordlist.has(`${lower.slice(0, -2)}n't`)) return `${lower.slice(0, -2)}n't`;
    for (const [tail, bases] of Object.entries(DOC_CONTRACTION_BASES)) {
      if (lower.endsWith(tail) && bases.has(lower.slice(0, -tail.length))) return `${lower.slice(0, -tail.length)}'${tail}`;
    }
    if (lower.length > 3 && lower.endsWith("s") && docWordlist.has(lower.slice(0, -1)) && /^(?:what|that|there|here|who|where|when|how|it|he|she|let)$/.test(lower.slice(0, -1))) {
      return `${lower.slice(0, -1)}'s`;
    }
    return null;
  }
  const DOC_CONFIDENT_MIN = 4;
  function docSpellConfident(word) {
    if (!docWordlist) return null;
    const lower = docSpellRoot(word);
    if (lower.length < DOC_CONFIDENT_MIN) return null;
    const swaps = [];
    const drops = [];
    for (const [candidate, rank] of docEditsOnce(lower)) {
      if (rank > DOC_EDIT_DROP) continue;
      if (!docWordlist.has(candidate)) continue;
      (rank === DOC_EDIT_SWAP ? swaps : drops).push(candidate);
    }
    //: A swap outranks a dropped letter rather than competing with it. "tets"
    //: has one of each ("test" and "tet", the Vietnamese new year), and
    //: treating those as a tie left the app with no opinion about the most
    //: ordinary typo there is.
    if (swaps.length === 1) return swaps[0];
    if (!swaps.length && drops.length === 1) return drops[0];
    return null;
  }
  function docSpellTransposed(word) {
    if (!docWordlist) return false;
    const lower = docSpellRoot(word);
    if (lower.length < DOC_CONFIDENT_MIN) return false;
    let swaps = 0;
    for (const [candidate, rank] of docEditsOnce(lower)) {
      if (rank === DOC_EDIT_SWAP && docWordlist.has(candidate)) swaps += 1;
    }
    return swaps === 1;
  }
  function docSpellLookup(word) {
    const key = docSpellRoot(word);
    let answer = docSpellCache.get(key);
    if (answer === undefined) {
      answer = { known: docWordKnown(word), sure: null };
      //: **The second opinion** (INBOX 1731): a word this list does not know is
      //: put to the worker's Hunspell dictionary and to the person's own words.
      //: Until it answers the word is not called a typo, and that answer is not
      //: kept, so the next pass asks again.
      if (!answer.known) {
        const second = docSpell.answer(key);
        if (second) answer.known = second.known;
        else if (docSpell.want(key)) return { known: true, sure: null };
      }
      if (!answer.known) answer.sure = docSpellConfident(word);
      //: Bounded, because a pathological document must not grow this without
      //: limit: cleared wholesale rather than evicted one at a time, which
      //: costs one rebuild on a document with more than 5,000 distinct words.
      if (docSpellCache.size > 5000) docSpellCache.clear();
      docSpellCache.set(key, answer);
    }
    return answer;
  }
  const DOC_PROSE_SKIP = [
    /(^|\n)[ \t]*(```|~~~)[^\n]*\n[\s\S]*?(\n[ \t]*\2[^\n]*|$)/g, // fenced code
    /`[^`\n]+`/g, // inline code
  /\b(?:https?:\/\/|ftp:\/\/|mailto:|www\.)\S+/g, // addresses
  /\]\([^)\n]*\)/g, // a markdown link's destination
  /^\[[^\]\n]+\]:\s*\S+/gm, // a reference link's definition
  /<\/?[A-Za-z][^>\n]*>/g, // an html tag
  /\[\[[^\]\n]*\]\]/g, // a note link: the title is a name, not prose
  //: A callout's own marker. `> [!note]` is syntax, and the space before its
  //: "!" was being reported as a space before punctuation on every callout in
  //: every document.
  /^[ \t]*>[ \t]*\[![A-Za-z]+\]/gm,
  /^---\n[\s\S]*?\n---/g, // frontmatter
  //: Suggestion mode's marks (PROSE-TOOLS): a word proposed for deletion is
  //: on its way out and not worth a finding, and the markers are syntax.
  /\{--[\s\S]*?--\}/g,
  /\{\+\+|\+\+\}/g,
  /\{>>[^<\n]*<<\}/g, // a change's stamp or a reviewer's comment: names and dates are not prose
  //: **Things that are not prose** (INBOX 1357, K11; measured on
  //: `tests/grammar_fixture_1026.json`): an email address, a file path and a
  //: file name, and a unit written after a number. Harper read `/etc/nginx/
    //: conf.d` as "config" and `uni` as a negative prefix, and called "min" and
    //: "mL" words to fix; the dictionary read the host of an address.
    /(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g, // an email address
    /(?<![\w/.:])(?:~|\.{1,2})?(?:\/[\w.\-@+~%]+)+\/?/g, // /etc/hosts, ~/notes/a.md
    /(?<![\w/.-])[\w.-]+(?:\/[\w.-]+){2,}\/?/g, // src/app/main.py
    /(?<![\w/-])[\w-]+\/[\w-]+\.[A-Za-z0-9]{1,5}\b/g, // docs/readme.md
    /\b[A-Za-z]:\\[^\s"'<>|]*/g, // C:\Users\me\notes.txt
  /(?<![\w-])[\w-]+\.(?:md|txt|pdf|png|jpe?g|gif|svg|csv|docx?|xlsx?|pptx?|html?|css|js|ts|py|json|ya?ml|toml|sh|zip)\b/gi, // a file name
  //: A unit straight after a number is a unit and not a word: 10 min, 2 h,
    //: 250 ms, 15 mL, 5 km, 3 x 4, 10am, 3rd, 90%, 37 °C. The number is not
    //: masked, the unit is; a unit with no number before it is prose.
    /(?<=\d)[ \u00a0]?(?:min|mins|h|hr|hrs|sec|secs|s|ms|ns|kg|g|mg|km|m|cm|mm|ml|l|kb|mb|gb|tb|khz|mhz|ghz|hz|kw|w|v|mv|ma|px|pt|dpi|fps|rpm|mph|lb|lbs|oz|ft|kcal|cal|kj|mol|db|x|am|pm|st|nd|rd|th)\b/gi,
    /(?<=\d)[ \u00a0]?(?:%|°[CFKcfk]?|℃|℉)/g,
  ];
  const DOC_PROSE_SKIP_LINK_TEXT = [/!?\[(?!\[)[^\][\n]*\](?=\([^)\n]*\)|\[[^\]\n]*\])/g];
  function docProseSkipMask(text) {
    const link = docCheckLinkText();
    const memo = docProseSkipMask.memo;
    if (memo && memo.link === link && memo.text === text) return memo.mask;
    const mask = new Uint8Array(text.length);
    docProseSkipMask.memo = { text, link, mask };
    const sources = link ? DOC_PROSE_SKIP : DOC_PROSE_SKIP.concat(DOC_PROSE_SKIP_LINK_TEXT);
    for (const source of sources) {
      //: A fresh regex per pass, for the reason the rules' own loop gives:
      //: `lastIndex` survives on a shared object and silently skips half the
      //: document on every second call.
      const pattern = new RegExp(source.source, source.flags);
      let match;
      while ((match = pattern.exec(text)) !== null) {
        if (!match[0].length) {
          pattern.lastIndex += 1;
          continue;
        }
        mask.fill(1, match.index, match.index + match[0].length);
      }
    }
    return mask;
  }
  function docProseFindings(text, lang = docProse.langOf(text)) {
    const found = [];
    //: Kicked off here rather than at load: this is the first moment anything
    //: wants to know whether a word is a word. It returns immediately, and the
    //: pass that arrives with it re-runs this one. Not for an empty editor
    //: (audit 2026-10-05, FE-03): this file's last line paints the tools once
    //: at load, when no document is open, and that pass fetched the 871 KB
    //: word list on every first Library visit with nothing to check.
    if (text.trim()) docLoadWordlist();
    const skip = docProseSkipMask(text);
    //: A span is skipped when it starts inside code or an address. Its start
    //: rather than every character of it: a rule whose match straddles the end
    //: of a code fence is about the code, not the prose after it.
    const skipped = (at) => skip[at] === 1;
    const english = lang === "en";
    for (const rule of DOC_PROSE_RULES) {
      if (!rule.test) continue;
      //: English word lists (repeat, confusion) would misfire on another language.
      if (rule.english && !english) continue;
      //: A fresh regex per pass: these carry `g`, and `lastIndex` survives
      //: between calls on a shared object, which silently skips half the
      //: document on every second run.
      const pattern = new RegExp(rule.test.source, rule.test.flags);
      let match;
      while ((match = pattern.exec(text)) !== null) {
        if (!match[0].length) break; // a zero-width match would loop forever
        if (skipped(match.index)) continue;
        found.push({
          rule: rule.id,
          message: rule.message,
          start: match.index,
          end: match.index + match[0].length,
          text: match[0],
          replacement: rule.fix ? rule.fix(match[0]) : null,
          ...(rule.alternatives ? { alternatives: rule.alternatives(match[0]) } : {}),
        });
      }
    }
    //: Spelling, word by word, so the span is the word and not a substring of a
    //: longer one: a regex over the whole list would flag "ot" inside "not".
    const word = /[A-Za-z']+/g;
    const dictionary = docDictionary();
    const variants = docVariantLookup();
    //: Off for a document whose `lang` is not English (`docProse.langOf`): see `docProse.langNote`.
    const checkWords = english;
    let hit;
    while (checkWords && (hit = word.exec(text)) !== null) {
      if (skipped(hit.index)) continue;
      const lower = hit[0].toLowerCase();
      //: A word in the dictionary is a word. This is the whole point of having
      //: one: the third time a checker flags your project's name, a checker you
      //: cannot answer is a checker you turn off.
      if (dictionary.has(lower)) continue;
      const variant = variants.get(lower);
      if (variant) {
        found.push({
          rule: "variant",
          message: `${DOC_VARIANT_LABEL[docSpellingVariant()] || "US"} spelling: “${variant}”`,
          start: hit.index,
          end: hit.index + hit[0].length,
          text: hit[0],
          replacement:
            hit[0][0] === hit[0][0].toUpperCase()
              ? variant[0].toUpperCase() + variant.slice(1)
              : variant,
        });
        continue;
      }
      const better = DOC_AUTOCORRECT[lower];
      if (better) {
        found.push({
          rule: "spelling",
          message: `“${hit[0]}” is probably “${better}”`,
          start: hit.index,
          end: hit.index + hit[0].length,
          text: hit[0],
          //: Keeps the writer's capitalisation: a typo at the start of a
          //: sentence must not be corrected into a lowercase word.
          replacement: docMatchCase(hit[0], better),
        });
        continue;
      }
      //: A contraction that is also a word ("I cant go", "ill be there"): the
      //: neighbours decide (`autocorrectState.contextual`), and the word is
      //: known to the dictionary, so it is asked before the dictionary is.
      const said = autocorrectState.inText(text, hit.index, hit[0]);
      if (said) {
        found.push({
          rule: "spelling",
          message: `“${hit[0]}” is probably “${said}”`,
          start: hit.index,
          end: hit.index + hit[0].length,
          text: hit[0],
          replacement: said,
        });
        continue;
      }
      //: **Everything else, against the dictionary.** The table above is 42
      //: entries and keeps its place only because it carries the one certain
      //: answer for each of them; this is the check that makes the other
      //: several hundred thousand typos visible. Silent until the word list has
      //: loaded, because a checker that flags every word for a second and then
      //: takes it back is worse than one that waits.
      if (!docWordlistReady()) continue;
      if (!docSpellable(text, hit[0], hit.index, hit.index + hit[0].length)) continue;
      const nameKind = docSpellNameKind(text, hit[0], hit.index);
      if (nameKind === "name" && (docWordKnown(hit[0]) || !docSpellTransposed(hit[0]))) continue;
      const looked = docSpellLookup(hit[0]);
      if (looked.known) continue;
      if (nameKind === "initial" && !looked.sure) continue;
      //: The candidate list is *not* computed here. It costs the square of the
      //: work of one edit when one edit finds nothing, and computing it for
      //: every unknown word on every pass put `docProseFindings` at 29ms over a
      //: 276-character document (measured, 2026-09-12) when the whole pass has
      //: a 300ms budget from keystroke to underline. The menu computes it for
      //: the one word it is about, when it opens.
      //:
      //: The row claims an answer only when there is one to claim
      //: (`docSpellConfident`); otherwise it says what it knows, which is that
      //: the word is not in the dictionary, and the menu offers the candidates.
      //: Saying "probably" about the first of five would be picking one at
      //: random on the writer's behalf.
      const sure = looked.sure;
      found.push({
        rule: "spelling",
        message: sure
          ? `“${hit[0]}” is probably “${sure}”`
          : `“${hit[0]}” is not in the dictionary`,
        start: hit.index,
        end: hit.index + hit[0].length,
        text: hit[0],
        //: `replacement` is what "Fix all" applies without asking, so it is set
        //: only when there is nothing to choose between.
        replacement: sure ? docMatchCase(hit[0], sure) : null,
      });
    }
    //: Another language: its installed spelling pack answers in the worker (documents-spell.js, D30)
    //: and finds nothing until it has, or when no pack is installed.
    if (!english) found.push(...docSpell.packFindings(text, lang, skipped));
    //: Long sentences, measured over the prose only. Code fences and headings
    //: are skipped: a fenced block has no sentences, and a heading that runs
    //: long is a heading, not a run-on.
    //: Headings, list items and table rows are blanked first (same length, so
    //: every offset holds): "- a, b and c" run together over a pasted list was
    //: one 90-word sentence, and a list item is not a sentence anyway (K4b).
    const sentences = docStructuralBlank(text);
    const paragraphBreak = /\n[ \t]*\n/g;
    const chunks = [];
    let last = 0;
    let split;
    while ((split = paragraphBreak.exec(sentences)) !== null) {
      chunks.push([last, split.index]);
      last = split.index + split[0].length;
    }
    chunks.push([last, sentences.length]);
    for (const [at, to] of chunks) {
      const chunk = sentences.slice(at, to);
      if (/^\s*(?:```|~~~|#|\||>)/.test(chunk)) continue;
      let cursor = 0;
      for (const sentence of chunk.split(/(?<=[.!?])\s+/)) {
        const words = (sentence.match(/\S+/g) || []).length;
        if (words > DOC_LONG_SENTENCE_WORDS) {
          found.push({
            rule: "long-sentence",
            message: `${nounCount(words, "word")} in one sentence`,
            start: at + cursor,
            end: at + cursor + sentence.length,
            text: text.slice(at + cursor, at + cursor + sentence.length),
            replacement: null,
          });
        }
        cursor += sentence.length + 1;
      }
    }
    return found
      .filter((finding) => !docProseIgnored.has(docProseKey(finding)))
      .sort((a, b) => a.start - b.start);
  }
  function docCodeProseMask(text, win = null) {
    const CM = window.CM6;
    if (!CM || !docCmView || docCmView.state.doc.length !== text.length) return "";
    const state = docCmView.state;
    const tree = win ? CM.language.syntaxTree(state) : CM.language.ensureSyntaxTree(state, state.doc.length, 50) || CM.language.syntaxTree(state);
    const keep = new Uint8Array(text.length);
    const blank = (from, length) => keep.fill(0, from, from + length);
    tree.iterate({
      ...(win ? { from: win.from, to: win.to } : {}),
      enter(node) {
        if (/Interpolation|Escape|FormatReplacement/i.test(node.name)) {
          blank(node.from, node.to - node.from);
          return false;
        }
        const string = /string|template/i.test(node.name);
        const comment = /comment/i.test(node.name);
        if (!string && !comment) return undefined;
        keep.fill(1, node.from, node.to);
        if (string) {
          const head = /^[rRbBuUfF]{0,3}(?:"""|'''|"|'|`)/.exec(text.slice(node.from, node.from + 6));
          if (head) blank(node.from, head[0].length);
          const tail = /(?:"""|'''|"|'|`)$/.exec(text.slice(Math.max(node.from, node.to - 3), node.to));
          if (tail) blank(node.to - tail[0].length, tail[0].length);
        } else {
          const head = /^(?:\/\/+|\/\*+|#+|--|<!--|;+|%+)/.exec(text.slice(node.from, node.from + 5));
          if (head) blank(node.from, head[0].length);
          const tail = /(?:\*+\/|-->)$/.exec(text.slice(Math.max(node.from, node.to - 4), node.to));
          if (tail) blank(node.to - tail[0].length, tail[0].length);
        }
        return undefined;
      },
    });
    const parts = [];
    for (let i = win ? win.from : 0, end = win ? win.to : text.length; i < end; i += 1) parts.push(keep[i] || text[i] === "\n" ? text[i] : " ");
    return parts.join("");
  }
  function docCodeSpellFindings(text, win = null) {
    if (!text.trim()) return [];
    docLoadWordlist();
    if (!docWordlistReady()) return [];
    const masked = docCodeProseMask(text, win);
    if (!masked.trim()) return [];
    const shift = win ? win.from : 0;
    const found = [];
    const dictionary = docDictionary();
    const word = /[A-Za-z']+/g;
    let hit;
    while ((hit = word.exec(masked)) !== null) {
      const lower = hit[0].toLowerCase();
      if (dictionary.has(lower)) continue;
      const at = hit.index;
      const base = { start: at + shift, end: at + shift + hit[0].length, text: hit[0], rule: "spelling" };
      const better = DOC_AUTOCORRECT[lower] || autocorrectState.inText(masked, at, hit[0]);
      if (better) {
        found.push({ ...base, message: `“${hit[0]}” is probably “${better}”`, replacement: docMatchCase(hit[0], better) });
        continue;
      }
      if (!docSpellable(masked, hit[0], at, at + hit[0].length)) continue;
      const nameKind = docSpellNameKind(masked, hit[0], at);
      if (nameKind === "name" && (docWordKnown(hit[0]) || !docSpellTransposed(hit[0]))) continue;
      const looked = docSpellLookup(hit[0]);
      if (looked.known) continue;
      if (nameKind === "initial" && !looked.sure) continue;
      found.push({
        ...base,
        message: looked.sure ? `“${hit[0]}” is probably “${looked.sure}”` : `“${hit[0]}” is not in the dictionary`,
        replacement: looked.sure ? docMatchCase(hit[0], looked.sure) : null,
      });
    }
    return found.filter((finding) => !docProseIgnored.has(docProseKey(finding)));
  }
  const docProse = {
    //: **The document's language** (audit 1028 D30). The `lang` (or `language`) key of a
    //: leading frontmatter block, reduced to its primary subtag: "en-GB" is "en". Absent
    //: means English, the one list this app ships. Pure, so it is tested alone. A method
    //: here rather than a global (the scope ratchet).
    langOf(text) {
      const block = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text || "");
      if (!block) return "en";
      const key = /^lang(?:uage)?:[ \t]*["']?([A-Za-z]{2,3})/m.exec(block[1]);
      return key ? key[1].toLowerCase() : "en";
    },
    //: Why the checker is quiet for a non-English document: the English list would
    //: flag every word, and no pack for its language is installed (a30h-1102 step 4). With a
    //: pack (D30, documents-spell.js) spelling is checked and the note says so.
    langNote(text) {
      const lang = this.langOf(text);
      if (lang === "en") return "";
      return docSpell.packNote(lang) || `Spelling and grammar are off for this document: its language is set to ${docSpell.langName(lang)}, and only the English checks are installed.`;
    },
    hidden: false,
    panelView: "list",
    win: null,
    timer: null,
    memo: null,
    //: **A key reads the paragraph it edited, not the window** (prose-1101). A
    //: pass made for a keystroke (`typing`) or for an answer to one (`again`)
    //: whose text differs from the last pass's by one small edit inside a
    //: paragraph keeps every finding outside that paragraph (moved by the length
    //: difference) and runs the rules on the paragraph alone; the mask is made
    //: the same way. Typing at 4x in a 5,000-line document read 14,000
    //: characters per key for the rules and the mask, now about 300. What it
    //: does not see (a finding that crosses a paragraph, the sentence before a
    //: blank line) is made good by `settle`: a full pass once the writer pauses,
    //: so the settled findings are the full pass's (`tests/test_prose_near_1101.py`).
    //: Anything that could change a paragraph's neighbours (a new line, a fence,
    //: frontmatter or a suggestion mark's characters, a paste) takes the full pass.
    typing: false,
    dirty: false,
    nearMin: 8000,
    rules(part, again) {
      const key = [docProseIgnored.size, docWordlist ? docWordlist.size : -1, docDictionary().size, docSpellingVariant(), docCheckLinkText(), docSpell.packKey()].join("|");
      const memo = this.memo;
      if (!((again || this.typing) && memo && memo.part === part && memo.key === key)) {
        const near = (this.typing || again) && memo && memo.key === key && part.length >= this.nearMin && memo.part !== part ? this.near(memo, part) : null;
        if (near) {
          this.memo = { part, key, found: near.found, mask: near.mask };
          this.dirty = true;
          this.settle();
        } else {
          const found = docProseFindings(part, docProse.langOf(part));
          //: Kept here, not read back from `docProseSkipMask.memo`: a grammar
          //: answer for an older text replaces that one between two keys.
          this.memo = { part, key, found, mask: part.length >= this.nearMin ? docProseSkipMask(part) : null };
          this.dirty = false;
        }
      }
      return this.memo.found.map((finding) => ({ ...finding }));
    },
    //: The findings and mask of `part` made from the last pass's (`last`), or
    //: null when the edit is not one a paragraph can hold.
    near(last, part) {
      const { part: old, found, mask: before } = last;
      if (!before || before.length !== old.length) return null;
      const limit = Math.min(old.length, part.length);
      let head = 0;
      while (head < limit && old.charCodeAt(head) === part.charCodeAt(head)) head += 1;
      let tail = 0;
      while (tail < limit - head && old.charCodeAt(old.length - 1 - tail) === part.charCodeAt(part.length - 1 - tail)) tail += 1;
      const gone = old.slice(head, old.length - tail);
      const put = part.slice(head, part.length - tail);
      if (gone.length > 200 || put.length > 200 || /[\n`~{}+-]/.test(gone + put)) return null;
      let from = part.lastIndexOf("\n\n", head);
      from = from < 0 ? 0 : from + 2;
      let to = part.indexOf("\n\n", head + put.length);
      if (to < 0) to = part.length;
      if (to - from > 4000) {
        //: A paragraph that long (notes with no blank lines) is read three lines at a time.
        const first = from;
        from = part.lastIndexOf("\n", Math.max(0, head - 1)) + 1;
        if (from > first) from = part.lastIndexOf("\n", from - 2) + 1;
        const next = part.indexOf("\n", head + put.length);
        const after = next < 0 ? -1 : part.indexOf("\n", next + 1);
        to = after < 0 ? to : Math.min(to, after);
      }
      const zone = part.slice(from, to);
      if (/```|~~~/.test(zone)) return null;
      let fences = 0;
      for (const _ of part.slice(0, from).matchAll(/^(?:```|~~~)/gm)) fences += 1;
      if (fences % 2 === 1) return null;
      const shift = part.length - old.length;
      const stop = to - shift;
      const inside = docProseFindings(zone, docProse.langOf(part));
      const mask = new Uint8Array(part.length);
      mask.set(before.subarray(0, from), 0);
      mask.set(docProseSkipMask(zone), from);
      mask.set(before.subarray(stop), to);
      docProseSkipMask.memo = { text: part, link: docCheckLinkText(), mask };
      const out = [];
      for (const finding of found) {
        if (finding.end <= from) out.push(finding);
        else if (finding.start >= stop) out.push(shift ? { ...finding, start: finding.start + shift, end: finding.end + shift } : finding);
      }
      for (const finding of inside) out.push({ ...finding, start: finding.start + from, end: finding.end + from });
      return { found: out.sort((a, b) => a.start - b.start), mask };
    },
    //: **The findings move with the text** (INBOX 1526). `docProseFound` is made
    //: for one text and the pass for the next one is a pause away, so between a
    //: key and that pass every offset past the caret was stale and the plugin
    //: drew none of them: the underlines below the line being typed on went out
    //: and came back 150 ms later. Moved here through the edit's changes instead
    //: (a copy per finding: the grammar cache's own objects are shared with the
    //: list). A finding the edit went into no longer reads its text and is not
    //: drawn; the start moves right of an insertion at it and the end stays left.
    remap(changes) {
      docProseFound = docProseFound.map((finding) => ({
        ...finding,
        start: changes.mapPos(finding.start, 1),
        end: changes.mapPos(finding.end, -1),
      }));
    },
    //: What the marks say, to know whether a repaint would draw anything new.
    sig() {
      return docProseFound.map((f) => `${f.rule}:${f.start}:${f.end}:${f.text}:${f.message}`).join("|");
    },
    painted: null,
    frame: 0,
    //: The full pass, once the writer has paused: when the browser is idle, at
    //: the latest 1.5 s after.
    settle() {
      clearTimeout(this.settleTimer);
      this.settleTimer = setTimeout(() => {
        const run = () => {
          if (this.dirty) renderDocProse();
        };
        if (typeof requestIdleCallback === "function") requestIdleCallback(run, { timeout: 1500 });
        else run();
      }, 700);
    },
  };
  const DOC_PROSE_WINDOW_CHARS = 30000;
  function docCodeWindow(text) {
    if (text.length <= DOC_PROSE_WINDOW_CHARS) return null;
    const ranges = docCmView ? docCmView.visibleRanges : [];
    const mid = ranges.length ? (ranges[0].from + ranges[ranges.length - 1].to) >> 1 : 0;
    const to = Math.min(text.length, Math.max(0, mid - DOC_PROSE_WINDOW_CHARS / 2) + DOC_PROSE_WINDOW_CHARS);
    const start = Math.max(0, to - DOC_PROSE_WINDOW_CHARS);
    const end = to < text.length ? text.indexOf("\n", to) : -1;
    return { from: start ? text.lastIndexOf("\n", start) + 1 : 0, to: end < 0 ? text.length : end };
  }
  function docProseWindow(text) {
    if (text.length <= DOC_PROSE_WINDOW_CHARS) return null;
    const view = 14000;
    let mid = 0;
    try {
      const ranges = docCmView ? docCmView.visibleRanges : [];
      mid = ranges.length ? (ranges[0].from + ranges[ranges.length - 1].to) >> 1 : docCmView ? docCmView.state.selection.main.head : 0;
    } catch {
      mid = 0;
    }
    let to = Math.min(text.length, Math.max(0, mid - view / 2) + view);
    let from = Math.max(0, to - view);
    if (from > 0) {
      //: Cut at a blank line, and never inside a fence: a window that began in
      //: the middle of a code block would read its code as prose. A blank line
      //: more than a view away (a long list, notes with no blank lines at all)
      //: is no cut: the window was then the whole document, 391,000 characters
      //: read on every key, so the cut is the nearest line end instead.
      const cut = text.lastIndexOf("\n\n", from);
      from = cut >= 0 && from - cut < view ? cut + 2 : text.lastIndexOf("\n", from) + 1;
      let open = -1;
      for (const fence of text.slice(0, from).matchAll(/^(?:```|~~~)/gm)) open = open < 0 ? fence.index : -1;
      if (open >= 0) from = open;
    }
    if (to < text.length) {
      const cut = text.indexOf("\n\n", to);
      const line = text.indexOf("\n", to);
      to = cut >= 0 && cut - to < view ? cut : line < 0 ? text.length : line;
    }
    return { from, to };
  }
  function docProseScrolled() {
    if (!docProse.win) return;
    clearTimeout(docProse.timer);
    docProse.timer = setTimeout(() => {
      const ranges = docCmView ? docCmView.visibleRanges : [];
      if (!ranges.length || !docProse.win) return;
      const seen = ranges[0].from < docProse.win.from || ranges[ranges.length - 1].to > docProse.win.to;
      if (seen) renderDocProse();
    }, 250);
  }
  function renderDocProse(again = false) {
    again = again === true;
    const chip = $("doc-prose");
    const count = $("doc-prose-count");
    const panel = $("doc-prose-panel");
    if (!chip || !count || !panel) return;
    //: A code file has no prose. Running these rules over one would flag `==`,
    //: `;;` and every long line, which is noise a programmer cannot turn off
    //: fast enough.
    const isCode = !docFileType().previewable;
    //: The rule findings, then the ones from the prose tools below (grammar,
    //: accessibility), which never claim a span a rule already holds.
    const text = docText();
    //: And Check with AI's findings (`docAiFindings`), located afresh in the
    //: text as it is now, so an applied or edited-away one simply goes.
    //: A long document is checked a window at a time (audit 1028 D7): the pass
    //: walks every rule and word, and at 100k characters that was a visible
    //: pause on each 150ms stop. The window follows the view (`docProseScrolled`).
    const win = isCode ? docCodeWindow(text) : docProseWindow(text);
    docProse.win = win;
    if (isCode) docProseFound = docCodeSpellFindings(text, win);
    else if (win) {
      const part = text.slice(win.from, win.to);
      const near = docProseExtras(part, docProse.rules(part, again));
      for (const finding of near) {
        finding.start += win.from;
        finding.end += win.from;
      }
      docProseFound = near.concat(docAiFindings(text)).sort((a, b) => a.start - b.start);
    } else {
      docProseFound = docProseExtras(text, docProse.rules(text, again)).concat(docAiFindings(text)).sort((a, b) => a.start - b.start);
    }
    if (docProse.hidden) docProseFound = [];
    chip.hidden = isCode;
    count.textContent = docProse.hidden
      ? "Suggestions hidden"
      : docProseFound.length
        ? `${docProseFound.length.toLocaleString("en")} ${docProseFound.length === 1 ? "suggestion" : "suggestions"}${win ? " in view" : ""}`
        : win
          ? "No suggestions in view"
          : "No suggestions";
    chip.classList.toggle("has-findings", docProseFound.length > 0);
    docFocusSyncProse();
    //: A fresh set of findings means a fresh set of marks. The engine is told
    //: through an effect rather than by rebuilding anything: the decorations are
    //: computed from `docProseFound` over the visible lines, so the repaint is a
    //: screenful whatever the document's length.
    docCmRepaintFindings(again);
    renderDocSuggestState();
    if (!panel.classList.contains("hidden")) docProsePanelSoon();
  }
  const DOC_PROSE_PANEL_GAP_MS = 400;
  function docProsePanelSoon() {
    const soon = docProsePanelSoon;
    clearTimeout(soon.timer);
    const wait = docCmView?.hasFocus ? (soon.at || 0) + DOC_PROSE_PANEL_GAP_MS - performance.now() : 0;
    if (!(wait > 0)) {
      soon.at = performance.now();
      renderDocProsePanel();
      return;
    }
    soon.timer = setTimeout(() => {
      soon.at = performance.now();
      renderDocProsePanel();
    }, wait);
  }
  const DOC_FINDING_SKIP = new Set(["long-sentence"]);
  const DOC_FIX_ALL_NEVER = new Set(["ai", "link-offer"]);
  function docFindingKind(finding) {
    if (finding.rule === "spelling") return "spelling";
    if (finding.rule === "grammar" || finding.rule === "confusion") return "grammar";
    //: A claim check's verdict (MINDMAP_PLAN Phase G) rides the same finding: marked
    //: when no note backs it or one says otherwise, quiet when a note supports it.
    if (finding.rule === "ai") {
      const claim = finding.aiItem?.claim;
      if (!claim) return "ai";
      if (claim.verdict === "supported") return "backed";
      return "claim";
    }
    if (DOC_ACCESS_RULES.has(finding.rule)) return "access";
    if (finding.rule === "repeat") return "repeat";
    if (finding.rule === "link-offer") return "link";
    return "style";
  }
  function docProseHeader() {
    const head = document.createElement("div");
    head.className = "row doc-prose-head";
    const title = document.createElement("span");
    title.className = "doc-prose-title";
    //: The name gives way (an ellipsis); the count beside it never does.
    const name = document.createElement("span");
    name.className = "doc-prose-name";
    name.textContent = "Suggestions";
    title.appendChild(name);
    const n = docProseFound.length;
    const count = document.createElement("span");
    count.className = "doc-prose-count";
    count.textContent = n ? String(n) : "";
    count.title = `${nounCount(n, "suggestion")} in this document`;
    title.appendChild(count);
    head.appendChild(title);

    const tools = document.createElement("span");
    tools.className = "row doc-prose-tools";
    const tool = (label, title, run, extra) => {
      const button = smallButton(label, title, run);
      button.classList.add("doc-prose-tool", ...extra.split(" "));
      button.setAttribute("aria-label", title);
      return button;
    };
    //: A model's fix is a judgement to read, never one of "every suggestion that
    //: has one clear answer", so Fix all leaves the `ai` kind alone, and an
    //: offer to link a note (`DOC_FIX_ALL_NEVER`).
    const fixable = docProseFound.filter((f) => f.replacement !== null && !DOC_FIX_ALL_NEVER.has(f.rule));
    if (fixable.length) {
      const all = tool(`ph:magic-wand Fix all ${fixable.length.toLocaleString("en")}`, `Fix all ${fixable.length.toLocaleString("en")}: apply every suggestion that has one clear answer`, () => docProseFixAll(), "doc-prose-fix-all");
      tools.appendChild(all);
    }
    //: **Meaning needs a model** (ROADMAP: its/it's, agreement, tense), and
    //: judging it takes seconds, so it is a button rather than a pass on every
    //: keystroke: it costs nothing until asked for.
    const running = docAiCheck.state === "running";
    tools.appendChild(tool(
      running ? "ph:stop" : "ph:sparkle",
      running
        ? "Stop checking; what it found so far stays"
        : "Check with AI: read for what spelling and grammar rules can't catch (its/it's, agreement, tense, tone, clarity)",
      () => docAiReview(),
      "icon-only doc-prose-ai-run"
    ));
    const right = docProseDockSide() === "right";
    const more = kebabMenu([
      makeMenuItem("ph:sparkle Check with AI", "Read for what the rules can't catch", () => docAiReview()),
      makeMenuItem("ph:seal-check Check claims against my notes", "Mark each sentence supported, contradicted or not found in your notes", () => docAiCheck.claims()),
      makeMenuItem(
        docProse.hidden ? "ph:eye Show suggestions" : "ph:eye-slash Hide all suggestions",
        docProse.hidden ? "Underline and list suggestions again" : "Hide every underline and the list until you show them again",
        () => docProseSetHidden(!docProse.hidden)
      ),
      makeMenuItem(
        `ph:arrow-counter-clockwise Dismissed (${docProseDismissed().length})`,
        "The suggestions you put away in this document, to bring back",
        () => {
          docProse.panelView = "dismissed";
          renderDocProsePanel();
        }
      ),
      makeMenuItem("ph:book-open-text Dictionary", "The words you have told this to accept", () => openDocDictionary()),
      //: Where the panel sits (`applyDocProseDock`); not offered where there is
      //: no choice (a narrow window, focus mode's side panel).
      ...(window.matchMedia(DOC_PROSE_NARROW).matches || docFocusOn() ? [] : [
        makeMenuItem(
          right ? "ph:square-split-vertical Dock at the bottom" : "ph:square-split-horizontal Dock on the right",
          right ? "Dock the suggestions at the bottom" : "Dock the suggestions on the right",
          () => toggleDocProseDock()
        ),
      ]),
    ], "More for the suggestions");
    more.classList.add("doc-prose-more");
    const opener = more.querySelector("button");
    opener.classList.add("doc-prose-tool");
    opener.setAttribute("aria-label", "More for the suggestions");
    tools.appendChild(more);
    tools.appendChild(tool("ph:x", "Close the suggestions", () => closeDocProsePanel(), "icon-only doc-prose-close"));
    head.appendChild(tools);
    return head;
  }
  function docProseSetHidden(hidden) {
    docProse.hidden = hidden;
    docProse.panelView = "list";
    renderDocProse();
    renderDocProsePanel();
  }
  function docProseDismissed() {
    const scope = `${currentDoc && currentDoc.id ? currentDoc.id : "unsaved"}:`;
    const rows = [];
    for (const key of docProseIgnored) {
      if (!key.startsWith(scope)) continue;
      const rest = key.slice(scope.length);
      const cut = rest.indexOf(":");
      if (cut < 0) continue;
      rows.push({ key, rule: rest.slice(0, cut), text: rest.slice(cut + 1) });
    }
    return rows;
  }
  function docProseSideView() {
    const wrap = document.createElement("div");
    wrap.className = "doc-prose-side";
    const line = document.createElement("p");
    line.className = "muted doc-prose-side-line";
    wrap.appendChild(line);
    if (docProse.panelView === "dismissed") {
      const rows = docProseDismissed();
      line.textContent = rows.length
        ? "Put away in this document. Restore one to see it again."
        : "Nothing dismissed in this document.";
      const back = smallButton("ph:arrow-left Back", "Back to the suggestions", () => {
        docProse.panelView = "list";
        renderDocProsePanel();
      });
      back.classList.add("ghost");
      const list = document.createElement("ul");
      list.className = "doc-prose-dismissed";
      for (const row of rows) {
        const item = document.createElement("li");
        item.className = "row doc-prose-dismissed-row";
        const word = document.createElement("span");
        word.className = "doc-prose-dismissed-text";
        word.textContent = row.text;
        word.title = `${row.rule}: ${row.text}`;
        const restore = smallButton("ph:arrow-counter-clockwise Restore", `Show “${row.text}” again`, () => {
          docProseIgnored.delete(row.key);
          if (docProseDismissed().length === 0) docProse.panelView = "list";
          renderDocProse();
          renderDocProsePanel();
        });
        restore.classList.add("ghost");
        item.append(word, restore);
        list.appendChild(item);
      }
      wrap.append(back, list);
      if (rows.length > 1) {
        const all = smallButton("ph:arrow-counter-clockwise Restore all", "Show every dismissed suggestion again", () => {
          for (const row of rows) docProseIgnored.delete(row.key);
          renderDocProse();
          renderDocProsePanel();
        });
        all.classList.add("ghost");
        wrap.appendChild(all);
      }
      return wrap;
    }
    line.textContent = "Suggestions are hidden. The underlines and this list are off until you show them.";
    const show = smallButton("ph:eye Show suggestions", "Underline and list suggestions again", () => docProseSetHidden(false));
    wrap.appendChild(show);
    return wrap;
  }
  function closeDocProsePanel() {
    $("doc-prose-panel")?.classList.add("hidden");
    $("doc-prose")?.setAttribute("aria-expanded", "false");
    docFocusSyncProse();
    //: Focus goes back to the control that opened it, or it lands on the body
    //: and the next Tab starts from the top of the page. In focus mode the
    //: status bar is gone, so that is the floating dock's own button.
    (docFocusOn() ? $("doc-focus-prose") : $("doc-prose"))?.focus();
  }
  function docFocusSyncProse() {
    const button = $("doc-focus-prose");
    if (!button) return;
    const n = docProseFound.length;
    const words = n ? nounCount(n, "suggestion") : "Suggestions";
    const label = $("doc-focus-prose-count");
    if (label) label.textContent = words;
    button.hidden = Boolean($("doc-prose")?.hidden);
    const open = !$("doc-prose-panel")?.classList.contains("hidden");
    button.setAttribute("aria-expanded", String(open));
    button.title = open ? "Close the writing suggestions" : n ? `Writing suggestions: ${words}` : "Writing suggestions";
    button.setAttribute("aria-label", button.title);
  }
  function renderDocProsePanel() {
    const panel = $("doc-prose-panel");
    if (!panel) return;
    panel.replaceChildren();
    //: The header first, always, including on the empty state. Reported:
    //: "there's no close x button." A panel whose only exit is the control that
    //: opened it is a panel you have to remember how to leave, and the empty
    //: state was the one view where that was most likely.
    if (docProse.hidden || docProse.panelView === "dismissed") {
      panel.appendChild(docProseHeader());
      panel.appendChild(docProseSideView());
      return;
    }
    const aiStatus = docAiCheckStatus();
    if (!docProseFound.length) {
      panel.appendChild(docProseHeader());
      if (aiStatus) panel.appendChild(aiStatus);
      //: Quiet: a mark, one line, and what was checked under it.
      const empty = document.createElement("div");
      empty.className = "doc-prose-empty";
      const mark = document.createElement("i");
      mark.className = "ph ph-check-circle doc-prose-empty-mark";
      mark.setAttribute("aria-hidden", "true");
      const said = document.createElement("p");
      said.textContent = "Nothing to flag.";
      const what = document.createElement("p");
      what.className = "muted";
      what.textContent = `Checked for spelling, ${docGrammarEnabled() ? "grammar, " : ""}spacing, sentence length and accessibility; these read the text, not its meaning.`;
      empty.append(mark, said, what);
      const langRow = docSpell.langRow(docText());
      if (langRow) empty.appendChild(langRow);
      panel.appendChild(empty);
      return;
    }
    panel.appendChild(docProseHeader());
    if (aiStatus) panel.appendChild(aiStatus);
    const langRow = docSpell.langRow(docText());
    if (langRow) panel.appendChild(langRow);

    //: **Grouped by kind, with a count on each group** (DOCUMENTS_PLAN Phase 0
    //: item 3). A flat list of twenty rows is twenty separate decisions in
    //: whatever order the document happens to put them; "Spelling 3 / Style 11 /
    //: Repeated words 2" is one look that tells you what kind of pass this
    //: document needs, and it lets you do all of one kind at a time, which is
    //: how anyone actually edits. The order is fixed rather than by size, so the
    //: strongest claim is always at the top and the panel does not reshuffle
    //: itself between two openings.
    for (const [kind, label] of DOC_FINDING_GROUPS) {
      const group = docProseFound.filter((finding) => docFindingKind(finding) === kind);
      if (!group.length) continue;
      const heading = document.createElement("p");
      heading.className = "doc-prose-group";
      const name = document.createElement("span");
      name.textContent = label;
      const count = document.createElement("span");
      count.className = "doc-prose-group-count";
      count.textContent = String(group.length);
      heading.append(name, count);
      panel.appendChild(heading);
      panel.appendChild(docProseGroupList(group));
    }
    if (!panel.dataset.keys) {
      panel.dataset.keys = "1";
      panel.addEventListener("keydown", docProseRowKeys);
    }
    if (docProseFocusAt >= 0) {
      const jumps = panel.querySelectorAll(".doc-prose-jump");
      (jumps[Math.min(docProseFocusAt, jumps.length - 1)] || panel.querySelector(".doc-prose-close"))?.focus({ preventScroll: true });
      docProseFocusAt = -1;
    }
  }
  const DOC_FINDING_GROUPS = [
    ["spelling", "Spelling"],
    ["grammar", "Grammar"],
    ["repeat", "Repeated words"],
    ["style", "Style and spacing"],
    ["access", "Accessibility"],
    ["link", "Links to your notes"],
    //: Claim check (Phase G): what the notebook does not back, then what it does.
    ["claim", "Checked against your notes"],
    ["backed", "Supported by your notes"],
    //: Last: a model's reading is the weakest claim in the panel, and it says
    //: so by where it sits.
    ["ai", "Checked with AI"],
  ];
  const DOC_PROSE_ROWS = 60;
  function docProseRowCollapse(row, control, answers) {
    control.setAttribute("aria-expanded", "false");
    row.removeAttribute("aria-current");
    answers.classList.add("hidden");
    answers.replaceChildren();
    if (row.dataset.keyOpened === "1") control.focus();
    delete row.dataset.keyOpened;
  }
  async function docProseRowAnswers(row, control, finding, opts = {}) {
    const panel = $("doc-prose-panel");
    const answers = row.querySelector(".doc-prose-answers");
    if (!panel || !answers) return;
    //: **Keyboard or pointer, decided by `event.detail`.** A click raised by
    //: Enter or Space on a button reports `detail === 0`; a real press reports
    //: the click count. It is the only signal that separates the two here, and
    //: the whole behaviour below hangs off it, so the caller passes it in rather
    //: than this function reaching for a global event.
    const byKeyboard = opts.keyboard === true;
    const wasOpen = control.getAttribute("aria-expanded") === "true";
    //: One open row, like one open popover. Two sets of answers in one list is
    //: two places the next press could mean something.
    for (const other of panel.querySelectorAll('.doc-prose-jump[aria-expanded="true"]')) {
      //: **Not this row.** The selector matches the row being pressed too when
      //: it is already open, and collapsing it here rather than in the `wasOpen`
      //: branch below meant the branch ran against a row that was already closed
      //: and had already given its focus away: measured as the editor keeping
      //: the ring after Enter closed a row from the keyboard.
      if (other === control) continue;
      const li = other.closest(".doc-prose-row");
      const box = li?.querySelector(".doc-prose-answers");
      //: Another row's answers, so its focus is not this row's business: the
      //: flag goes first, and the collapse leaves focus where it found it.
      if (li) delete li.dataset.keyOpened;
      if (li && box) docProseRowCollapse(li, other, box);
      else other.setAttribute("aria-expanded", "false");
    }
    //: Pressing the row always takes you to the word, open or closing: that is
    //: what the row is for, and it is the half of this the owner asked for
    //: ("it should auto scroll to the issue and temporarily highlight it").
    docProseJump(finding);
    //: **The press that closes decides where focus goes**, not the press that
    //: opened: closing with Enter from the row means the reader is on the row
    //: and wants to stay there, whichever way it was opened. Set before either
    //: branch because the `close` handed to the answers below reads it too, and
    //: that is what a candidate pressed with Enter calls.
    if (byKeyboard) row.dataset.keyOpened = "1";
    else delete row.dataset.keyOpened;
    if (wasOpen) {
      docProseRowCollapse(row, control, answers);
      return;
    }
    control.setAttribute("aria-expanded", "true");
    //: The open row is where you are in the document, so it says so with
    //: `aria-current` and is painted from that attribute (DESIGN.md's recipe for
    //: a list that says where you are), not with a class a screen reader cannot
    //: see.
    row.setAttribute("aria-current", "location");
    const drawn = await docSuggestAnswers(finding, {
      inline: true,
      close: () => docProseRowCollapse(row, control, answers),
      current: () => control.getAttribute("aria-expanded") === "true",
    });
    //: The piece may have been fetched meanwhile: a row closed or replaced by then is left alone.
    if (control.getAttribute("aria-expanded") !== "true") return;
    answers.replaceChildren(drawn);
    answers.classList.remove("hidden");
    //: Brought into view by the panel's own `scrollTop`, never `scrollIntoView`,
    //: which walks every scrolling ancestor including the page (DESIGN.md).
    const box = row.getBoundingClientRect();
    const frame = panel.getBoundingClientRect();
    if (box.bottom > frame.bottom) panel.scrollTop += box.bottom - frame.bottom + 8;
    else if (box.top < frame.top) panel.scrollTop -= frame.top - box.top + 8;
    //: **Focus follows the keyboard into the answers, and only the keyboard.**
    //: Reported (OPEN.md, prose-intelligence.md): "Enter opens the row, focus
    //: stays on the control, the candidates are a Tab away with nothing saying
    //: so." Measured before this: after Enter, `document.activeElement` was the
    //: editor's own `cm-content` (`docProseJump` focuses the surface to show the
    //: word), so the candidates were not one Tab away, they were behind the
    //: whole editor's tab order. The first candidate is the one the panel says
    //: is the best answer, so it is the one that takes the ring.
    if (!byKeyboard) return;
    const first = answers.querySelector("button:not([disabled])");
    if (first) first.focus();
  }
  function docIgnoreLabel(finding) {
    return finding.rule === "link-offer" ? "Never offer a link to this name" : "Ignore in this document";
  }
  function docProseIgnore(finding) {
    //: A link offer is put away by its name, for every document (the switch and
    //: the list of kept names are in Settings, Writing).
    if (finding.rule === "link-offer" && finding.name) {
      docLinkOfferIgnore(finding.name);
      return;
    }
    docProseIgnored.add(docProseKey(finding));
    renderDocProse();
    renderDocProsePanel();
  }
  let docProseFocusAt = -1;
  function docProseRowKeys(event) {
    const jump = event.target.closest?.(".doc-prose-jump");
    const moves = { ArrowDown: 1, ArrowUp: -1, Home: -Infinity, End: Infinity };
    if (!jump || !(event.key in moves)) return;
    event.preventDefault();
    const all = [...event.currentTarget.querySelectorAll(".doc-prose-jump")];
    const to = Math.max(0, Math.min(all.length - 1, all.indexOf(jump) + moves[event.key]));
    all[to]?.focus();
  }
  function docProseGroupList(findings) {
    const list = document.createElement("ul");
    list.className = "doc-prose-list";
    for (const finding of findings.slice(0, DOC_PROSE_ROWS)) {
      const li = document.createElement("li");
      li.className = "doc-prose-row";
      const head = document.createElement("div");
      head.className = "row doc-prose-rowhead";
      const jump = document.createElement("button");
      jump.type = "button";
      jump.className = "doc-prose-jump";
      jump.setAttribute("aria-expanded", "false");
      //: The words, then why: one drawing of a finding, shared with the menu's
      //: own head (`docFindingLine`).
      jump.appendChild(docFindingLine(finding, "row"));
      jump.title = "Show me this in the document, and what can be done about it";
      //: `event.detail === 0` is a press that came from Enter or Space rather
      //: than from a pointer: see `docProseRowAnswers` for what hangs off it.
      jump.addEventListener("click", (event) =>
        docProseRowAnswers(li, jump, finding, { keyboard: event.detail === 0 }));
      head.appendChild(jump);
      //: **One action cell per row** (INBOX 549): accept when there is one clear
      //: answer, then the way to put it away, last on every row: Ignore, or for
      //: a model's finding, Dismiss. Quiet icons of one size, centred on the row.
      const acts = document.createElement("span");
      acts.className = "doc-prose-acts";
      const act = (icon, title, run, extra = "") => {
        const button = smallButton(icon, title, () => {
          docProseFocusAt = [...$("doc-prose-panel").querySelectorAll(".doc-prose-jump")].indexOf(jump);
          run();
        });
        button.classList.add("icon-only", "doc-prose-act", ...extra.split(" ").filter(Boolean));
        button.setAttribute("aria-label", title);
        return button;
      };
      if (finding.aiItem?.claim?.note) {
        const note = finding.aiItem.claim.note;
        acts.appendChild(act("ph:note", `Open the note \u201c${note.title}\u201d`, () => openNoteEditor(note.id), "doc-prose-open-note"));
      }
      if (finding.replacement !== null) {
        acts.appendChild(act("ph:check", `Change it to \u201c${finding.replacement}\u201d`, () => docProseFix(finding), "doc-prose-fix"));
      }
      acts.appendChild(finding.rule === "ai"
        ? act("ph:x", "Dismiss this finding", () => docAiDismiss(finding), "doc-prose-fix doc-prose-dismiss")
        : act("ph:eye-slash", docIgnoreLabel(finding), () => docProseIgnore(finding), "doc-prose-ignore"));
      head.appendChild(acts);
      li.appendChild(head);
      const answers = document.createElement("div");
      answers.className = "doc-prose-answers hidden";
      //: **Escape leaves the answers the way it leaves every other surface in
      //: this app**, and it is wired here, once per row, rather than inside the
      //: open: the block is reused across opens, so a listener added there would
      //: multiply by one per press (the shape `tests/test_frontend_handlers.py`
      //: exists to catch). Stopped from bubbling because the app's own Escape
      //: chain would otherwise close the whole panel from underneath a reader
      //: who only meant to close one row.
      answers.addEventListener("keydown", (event) => {
        if (event.key !== "Escape") return;
        if (jump.getAttribute("aria-expanded") !== "true") return;
        event.stopPropagation();
        event.preventDefault();
        li.dataset.keyOpened = "1";
        docProseRowCollapse(li, jump, answers);
      });
      li.appendChild(answers);
      list.appendChild(li);
    }
    return list;
  }
  const DOC_FLASH_MS = 1600;
  function docProseJump(finding) {
    //: **No view switch.** This used to drop anyone in Live back into Source to
    //: find the word, which throws away the view they were reading in. Live can
    //: show the underline where it is now, so there is nothing to switch to.
    if (docView === "rendered") setDocView(lastEditView);
    const box = docSurface();
    if (!box) return;
    box.focus();
    box.setSelection(finding.start, finding.end);
    if (box.kind === "codemirror") {
      //: **To the middle, not just inside the edge** (DOCUMENTS_PLAN 12 D3).
      //: `setSelection` scrolls the minimum that reveals the range, which puts a
      //: word reached from the panel hard against the bottom of the editor, the
      //: one place where everything that follows (the row's own answers, a menu)
      //: has to be drawn over the text being discussed. Measured before this:
      //: the word at `564..583` in an editor ending at `588`.
      const CM = window.CM6;
      if (CM) {
        docCmView.dispatch({
          effects: CM.view.EditorView.scrollIntoView(finding.start, { y: "center" }),
        });
      }
      return;
    }
    box.blur();
    box.focus();
    box.classList.remove("doc-selection-flash");
    void box.offsetWidth;
    box.classList.add("doc-selection-flash");
    setTimeout(() => box.classList.remove("doc-selection-flash"), DOC_FLASH_MS);
  }
  function docProseApply(text, finding) {
    return text.slice(0, finding.start) + finding.replacement + text.slice(finding.end);
  }
  function docProseFix(finding) {
    const box = docSurface();
    if (!box || finding.replacement === null) return;
    //: Checked against the document as it is *now*, not as it was when the panel
    //: was drawn. Editing while the panel is open moves every span after the
    //: edit, and applying a stale offset would corrupt the document silently, 
    //: which is the one failure a writing aid must never have.
    if (box.value.slice(finding.start, finding.end) !== finding.text) {
      renderDocProse();
      return toast("That text has changed, the list is refreshed.", "info");
    }
    //: Its own step in the editor's history (Ctrl+Z, rule 1.8), never folded
    //: into the typing before it.
    docUndoBreak();
    box.value = docProseApply(box.value, finding);
    markDocDirty();
    box.dispatchEvent(new Event("input", { bubbles: true }));
    renderDocProse();
  }
  function docProseFixAll() {
    const box = docSurface();
    if (!box) return;
    //: Back to front, so each replacement cannot move the offsets of the ones
    //: still to be applied.
    const fixable = docProseFound
      .filter((f) => f.replacement !== null && !DOC_FIX_ALL_NEVER.has(f.rule))
      .sort((a, b) => b.start - a.start);
    let text = box.value;
    let applied = 0;
    for (const finding of fixable) {
      if (text.slice(finding.start, finding.end) !== finding.text) continue;
      text = docProseApply(text, finding);
      applied += 1;
    }
    if (!applied) return toast("Nothing left to fix.", "info");
    docUndoBreak();
    box.value = text;
    markDocDirty();
    box.dispatchEvent(new Event("input", { bubbles: true }));
    renderDocProse();
    toast(`Fixed ${applied}. Ctrl+Z undoes it.`);
  }
  const DOC_COMPLETE_MIN = 3; //: Below three characters almost anything matches.
  const DOC_COMPLETE_MAX = 6;
  let docCompleteMatches = [];
  let docCompleteIndex = 0;
  let docCompleteBox = null;
  function docCompleteEnabled() {
    return $("doc-complete")?.checked !== false;
  }
  function docBuildVocabulary() {
    const counts = new Map();
    const add = (word, weight) => {
      if (word.length < DOC_COMPLETE_MIN + 1) return;
      counts.set(word, (counts.get(word) || 0) + weight);
    };
    for (const word of docText().match(/[A-Za-z][A-Za-z'-]{2,}/g) || []) {
      //: Weighted above the notebook's words: while writing *this* document, the
      //: word you used two paragraphs ago is far likelier than one from a note
      //: last March.
      add(word, 3);
    }
    const entries = typeof allEntries !== "undefined" ? allEntries : [];
    for (const entry of entries.slice(0, 400)) {
      for (const word of String(entry.content || "").slice(0, 400).match(/[A-Za-z][A-Za-z'-]{2,}/g) || []) {
        add(word, 1);
      }
    }
    for (const doc of typeof docList !== "undefined" && Array.isArray(docList) ? docList : []) {
      for (const word of String(doc.title || "").match(/[A-Za-z][A-Za-z'-]{2,}/g) || []) add(word, 2);
    }
    docCompleteWords = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }
  function docWordFragment(box) {
    const at = box.selection().from;
    const line = box.lineAt(at);
    const column = at - line.from;
    const upto = line.text.slice(0, column);
    const after = line.text.slice(column, column + 1);
    if (after && /[A-Za-z]/.test(after)) return null;
    const match = /[A-Za-z][A-Za-z'-]*$/.exec(upto);
    if (!match || match[0].length < DOC_COMPLETE_MIN) return null;
    //: Never inside a wiki link, that autocomplete owns those keystrokes, and
    //: two popups over one caret is worse than either alone.
    if (/\[\[[^\]]*$/.test(upto)) return null;
    return { start: line.from + match.index, fragment: match[0] };
  }
  function hideDocComplete() {
    const list = $("doc-complete-list");
    list?.classList.add("hidden");
    docReturnFromViewport(list);
    docCompleteMatches = [];
    docCompleteBox = null;
    if (typeof docProseGhostSet === "function") docProseGhostSet(null, "");
  }
  function docFillAt(box) {
    if (typeof docFillToken !== "function" || !docProseFillOn()) return null;
    const range = box.selection();
    if (range.from !== range.to) return null;
    const line = box.lineAt(range.from);
    const column = range.from - line.from;
    const tok = docFillToken(line.text.slice(0, column), line.text.slice(column));
    if (!tok) return null;
    //: The "/" menu and the `[[` menu own their keystrokes while open.
    if (typeof editorMenuState === "object" && editorMenuState?.open) return null;
    const options = docFillOptions(tok, {
      now: new Date(),
      locale: undefined,
      name: (typeof prefsCache === "object" && prefsCache?.display_name) || "",
      doc: tok.kind === "toc" ? docText() : "",
      slug: mdHeadingId,
    });
    if (!options.length) return null;
    return { start: line.from + tok.start, options };
  }
  function renderDocComplete(box) {
    const list = $("doc-complete-list");
    if (!list) return hideDocComplete();
    //: **One popup at the caret.** While the "/" menu is open, what is typed
    //: after the slash is its query, not a word to complete: measured, "/warn"
    //: drew the word list's "warning" over the top of the block menu's first
    //: group (INBOX 421 b's screenshot pass).
    if (typeof editorMenuState === "object" && editorMenuState?.open) return hideDocComplete();
    //: The expansions first, and whatever the word switch says: they answer a
    //: trigger the writer typed on purpose, where word suggestions are a guess.
    const fill = docFillAt(box);
    const at = docCompleteEnabled() ? docWordFragment(box) : null;
    let words = [];
    if (at) {
      if (!docCompleteWords) docBuildVocabulary();
      const needle = at.fragment.toLowerCase();
      words = docCompleteWords
        .filter(([word]) => word.toLowerCase().startsWith(needle) && word.toLowerCase() !== needle)
        .slice(0, DOC_COMPLETE_MAX)
        .map(([word]) => ({ word, typed: at.fragment.length }));
    }
    //: A row is `{word, typed}` (the rest of a word) or `{fill, start}` (an
    //: expansion that replaces from `start` to the caret).
    docCompleteMatches = [
      ...(fill ? fill.options.map((option) => ({ fill: option, start: fill.start })) : []),
      ...words,
    ];
    if (!docCompleteMatches.length) return hideDocComplete();

    docCompleteBox = box;
    docCompleteIndex = Math.min(docCompleteIndex, docCompleteMatches.length - 1);
    list.replaceChildren();
    docCompleteMatches.forEach((match, index) => {
      const li = document.createElement("li");
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", String(index === docCompleteIndex));
      li.classList.toggle("active", index === docCompleteIndex);
      if (match.fill) {
        //: The trigger in full strength, what it writes quieter: the same two
        //: inks a word row uses for typed and suggested. A shortcode leads with
        //: its glyph, which is the picker.
        li.classList.add("doc-complete-fill");
        if (match.fill.glyph) {
          const glyph = document.createElement("span");
          glyph.className = "doc-complete-glyph";
          glyph.textContent = match.fill.glyph;
          li.appendChild(glyph);
        }
        const head = document.createElement("b");
        head.textContent = match.fill.label;
        li.appendChild(head);
        if (match.fill.detail) {
          const detail = document.createElement("span");
          detail.className = "doc-complete-detail";
          detail.textContent = match.fill.detail;
          li.appendChild(detail);
        }
      } else {
        const head = document.createElement("b");
        head.textContent = match.word.slice(0, match.typed);
        const rest = document.createElement("span");
        rest.textContent = match.word.slice(match.typed);
        li.append(head, rest);
      }
      li.addEventListener("mousedown", (event) => {
        //: mousedown, not click: the textarea must not lose focus first, or the
        //: selection this writes into is gone by the time it runs.
        event.preventDefault();
        applyDocComplete(box, match);
      });
      list.appendChild(li);
    });
    //: The ghost after the caret, on the engine only: the chosen row's rest, as
    //: the code side draws it (`.cm-ghostText`).
    if (box.kind === "codemirror" && typeof docProseGhostSet === "function") {
      const chosen = docCompleteMatches[docCompleteIndex];
      const caret = box.selection().from;
      const ghost = chosen.fill ? docFillGhost(chosen.fill) : chosen.word.slice(chosen.typed);
      docProseGhostSet(caret, ghost);
    }
    const point = docCaretPoint(box);
    //: Kept on screen: a popup at the caret near the right edge or the bottom of
    //: the window would otherwise open off it, which is the app-wide rule for
    //: every menu here. Out of the card first, for the reason `docLiftToViewport`
    //: gives: this list is placed in viewport coordinates too, so a blurred
    //: ancestor moves it exactly as it moved the word menu.
    docLiftToViewport(list);
    list.classList.remove("hidden");
    const width = list.offsetWidth;
    const height = list.offsetHeight;
    const left = Math.min(point.left, window.innerWidth - width - 8);
    const below = point.bottom + 4;
    const flipped = below + height > window.innerHeight - 8 ? point.top - height - 4 : below;
    //: Clamped at both ends, not just at the top. A caret low in a short window
    //: flips the list above itself, and a list taller than the space above lands
    //: at a negative top, is pulled back to 8, and then draws its last rows off
    //: the bottom of the screen: the bug `placeDocSuggest` already records
    //: fixing on the word menu, in the one other popup that never got it.
    const top = Math.min(
      Math.max(8, flipped),
      Math.max(8, window.innerHeight - 8 - height)
    );
    docPlaceFixed(list, Math.max(8, left), top);
  }
  function applyDocComplete(box, match) {
    if (!match) return hideDocComplete();
    //: A range edit rather than a whole-value rewrite: on the engine that keeps
    //: the completion as one undo step over the fragment it replaced, and it
    //: costs the length of the word rather than the length of the document.
    const caret = box.selection().from;
    if (match.fill) {
      //: Read again at the moment of taking it, the rule `docProseFix` keeps: the
      //: row was drawn a keystroke ago, and a trigger that is no longer before
      //: the caret is not one to replace.
      const now = docFillAt(box);
      if (!now || now.start !== match.start) return hideDocComplete();
      const text = match.fill.text;
      box.replaceRange(match.start, caret, text);
      if (match.fill.select) {
        box.setSelection(match.start + match.fill.select[0], match.start + match.fill.select[1]);
      } else {
        box.setSelection(match.start + text.length);
      }
    } else {
      const at = docWordFragment(box);
      if (!at) return hideDocComplete();
      box.replaceRange(at.start, caret, match.word);
      box.setSelection(at.start + match.word.length);
    }
    hideDocComplete();
    box.focus();
    box.dispatchEvent(new Event("input", { bubbles: true }));
  }
  function docCompleteKeydown(event, box) {
    const list = $("doc-complete-list");
    if (!list || list.classList.contains("hidden")) return false;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      docCompleteIndex =
        (docCompleteIndex + step + docCompleteMatches.length) % docCompleteMatches.length;
      renderDocComplete(box);
      return true;
    }
    //: **Tab for a word, and Enter only for an expansion.** Enter in a document
    //: is a new line, and stealing it for a guessed word is how an autocomplete
    //: becomes the thing you fight. An expansion is different: it answers a
    //: trigger typed on purpose (`lorem`, `today` on its own line, `:smile`),
    //: and "type lorem and press enter" is the ask it exists for. Escape, then
    //: Enter, is still a plain new line.
    const chosen = docCompleteMatches[docCompleteIndex];
    //: In a table cell Tab moves cells and never takes a word (dogfood item 8).
    if (event.key === "Tab" && docTableContext(box)) {
      hideDocComplete();
      return false;
    }
    if (event.key === "Tab" || (event.key === "Enter" && chosen?.fill && !event.shiftKey && !event.ctrlKey && !event.metaKey && !event.altKey)) {
      event.preventDefault();
      applyDocComplete(box, chosen);
      return true;
    }
    if (event.key === "Escape") {
      event.preventDefault();
      hideDocComplete();
      return true;
    }
    return false;
  }
  function docAutocorrectEnabled() {
    //: Never in a code file: `teh` may be a variable, and an editor that rewrote
    //: an identifier as you typed it would be unusable.
    return $("doc-autocorrect")?.checked === true && docFileType().previewable;
  }
  function docAutocorrectAt(box) {
    if (!docAutocorrectEnabled()) return false;
    const caret = box.selection().from;
    //: The caret's line, for the same reason `docWordFragment` reads one: this
    //: runs on every inserted character, and the word it is looking at cannot
    //: begin on a previous line.
    const line = box.lineAt(caret);
    const upto = line.text.slice(0, caret - line.from);
    const match = /([A-Za-z']+)([\s.,;:!?)\]]+)$/.exec(upto);
    if (!match) return false;
    //: Never the tail of a word with an accented letter ("ve" of naïve; D8).
    if (/\p{L}/u.test(upto[match.index - 1] || "")) return false;
    const lower = match[1].toLowerCase();
    //: A word the reader has accepted is never rewritten, whatever the typo list
    //: says. The dictionary is the reader's answer to this feature, and an
    //: autocorrect that ignored it would be the app overruling them mid-sentence.
    if (docDictionary().has(lower)) return false;
    //: And a word put back from the underline's menu (autocorrect.js) is not
    //: rewritten again this session, the same promise the note boxes keep.
    if (typeof autocorrectRefused !== "undefined" && autocorrectRefused.has(lower)) return false;
    let better = DOC_AUTOCORRECT[lower] || docVariantLookup().get(lower);
    //: **The dictionary's own unambiguous answers, on the same terms as the
    //: table's.** The table is 42 strings that are not words in any English
    //: text, which is the bar an automatic replacement has to clear because the
    //: cost of being wrong is that the app silently changed something the
    //: writer meant. `docSpellConfident` holds the same bar against 93,000
    //: words rather than 42: the word is not in any dictionary, and there is
    //: exactly one real word a swap of two letters away (or exactly one a
    //: dropped letter away, when no swap reaches one at all), and it is at
    //: least four letters long because almost every three-letter string is one
    //: edit from several real words. Anything with a choice in it stays a menu.
    if (!better) {
      //: The same refusals the check itself makes: an acronym, an identifier,
      //: a word touching a digit or a path is not prose and must never be
      //: rewritten. The line is the text these offsets are in.
      const at = caret - line.from - match[0].length;
      if (!docSpellable(line.text, match[1], at, at + match[1].length)) return false;
      const looked = docSpellLookup(match[1]);
      if (looked.known) return false;
      better = looked.sure;
    }
    if (!better) return false;
    const replacement = match[1][0] === match[1][0].toUpperCase()
      ? better[0].toUpperCase() + better.slice(1)
      : better;
    const start = caret - match[0].length;
    //: **Its own step in the history, or the toast below is a lie.** Typing is
    //: grouped into one undo entry per burst, so a correction folded into that
    //: burst means Ctrl+Z takes back the whole sentence rather than the
    //: correction. Measured 2026-09-12: one Ctrl+Z after "I ran a tets " left
    //: an empty document. Isolating before the replacement makes the first
    //: Ctrl+Z give back exactly what was typed, which is what the toast says
    //: and the only thing that makes an automatic rewrite acceptable.
    docUndoBreak();
    box.replaceRange(start, caret, replacement + match[2]);
    const next = start + replacement.length + match[2].length;
    box.setSelection(next);
    //: Announced, quietly and once. Software that changes what you typed and
    //: says nothing is the reason people turn autocorrect off, and this one
    //: names both words so a wrong correction is visible rather than found
    //: later.
    toast(`“${match[1]}” → “${replacement}”. Ctrl+Z undoes it.`);
    //: **Highlighted, with a menu on hover or click** (INBOX 904 B04), the same
    //: underline the note boxes get. autocorrect.js is lazy: the first
    //: correction of a visit fetches it (cached, so a promise already settled).
    const typedWord = match[1];
    lazyScript("/js/autocorrect.js").then(() => autocorrectShow(box, start, typedWord, replacement));
    return true;
  }
  const DOC_TOOL_KEYS = {
    autocorrect: "doc-autocorrect",
    complete: "doc-complete",
    //: INBOX 402: VS Code's Alt+Z and "render whitespace", for a code file.
    codeWrap: "doc-code-wrap",
    whitespace: "doc-whitespace",
    //: Brief 42: a name missing here was stored under the key "undefined".
    codeMinimap: "doc-minimap",
    //: L-documents-41: the opt-in Vim keymap, off by default.
    vimKeys: "doc-vim",
    //: Brief 69 (D6): Preview live in the run panel.
    runLive: "doc-run-live",
  };
  function docToolPref(name, fallback) {
    try {
      const stored = prefs.get(DOC_TOOL_KEYS[name], null);
      return stored === null ? fallback : stored === "1";
    } catch {
      return fallback; // private mode: the default shape
    }
  }
  function docSaveToolPref(name, on) {
    try {
      prefs.set(DOC_TOOL_KEYS[name], on ? "1" : "0");
    } catch {
      /* private mode: it just won't be remembered */
    }
  }
  const DOC_PROSE_DEBOUNCE_MS = 150;
  let docProseTimer = null;
  let docVocabTimer = null;
  function docToolsOnInput(box) {
    renderDocCaret();
    renderDocComplete(box);
    //: Debounced, both of them: the prose pass walks the whole document and the
    //: vocabulary re-splits it, and neither is worth doing between two
    //: keystrokes.
    //:
    //: **150ms, down from 400.** The pause is no longer only about when the
    //: *panel* is current. Since Phase 0 it is also when the squiggle appears
    //: under the word you just misspelt, and DOCUMENTS_PLAN's acceptance for
    //: that is 300ms from the keystroke. At 400 the underline could not make it
    //: even with a free pass.
    //:
    //: The work itself is cheap, measured on a 2,629-character document in the
    //: sandbox Chromium: 0.82ms to find the findings and 6.3ms for the whole
    //: `renderDocProse`, which repaints the chip and asks the engine for a
    //: decoration pass over the visible lines. So the number here is almost the
    //: whole
    //: latency, and it is set for headroom rather than for the average: at 200
    //: the sweep measured 284ms end to end against a 300ms bound, which is a
    //: check that would fail on a slower machine while nothing was wrong.
    //: Still well over the gap between two keystrokes of ordinary typing, so
    //: this does not run mid-word.
    //:
    //: **Then an idle moment the next key withdraws** (DX1). On a slow machine
    //: one key's own work outlasted the 150 ms, so the timer fired between two
    //: keys of one burst, the pass (23 ms at 4x CPU in a 3,120-line document)
    //: made the next gap longer still, and it ran on 29 of 60 keys. So the
    //: pause is also counted in this typist's own rhythm: one and a half times
    //: the recent gap between keys (`gap`, under a second), never less than 150.
    const now = performance.now();
    const gap = now - (docToolsOnInput.at || -1e9);
    docToolsOnInput.gap = gap < 1000 ? (docToolsOnInput.gap ? docToolsOnInput.gap * 0.6 + gap * 0.4 : gap) : 0;
    docToolsOnInput.at = now;
    //: Shared with the facts pass and the grammar answer, which read them there.
    scheduleDocFacts.gap = docToolsOnInput.gap;
    docProse.typedAt = now;
    clearTimeout(docProseTimer);
    if (docToolsOnInput.idle) cancelIdleCallback(docToolsOnInput.idle);
    docToolsOnInput.idle = 0;
    const check = () => {
      docToolsOnInput.idle = 0;
      docProse.typing = true;
      try {
        renderDocProse();
      } finally {
        docProse.typing = false;
      }
    };
    docProseTimer = setTimeout(() => {
      if (window.requestIdleCallback) docToolsOnInput.idle = requestIdleCallback(check);
      else check();
    }, Math.max(DOC_PROSE_DEBOUNCE_MS, Math.min(600, 1.5 * docToolsOnInput.gap)));
    clearTimeout(docVocabTimer);
    docVocabTimer = setTimeout(() => {
      docCompleteWords = null;
    }, 1200);
  }
  function docToolsBoxFor(target) {
    //: A surface as well as a node, because half the callers now hold one
    //: already (`applyMarkdown`'s Undo branch is the one that caught this: with
    //: a surface passed to the old element-only check it returned null and the
    //: toolbar's Undo silently fell through to `execCommand`).
    if (target && (target.kind === "textarea" || target.kind === "codemirror")) {
      return target.isDocument ? target : null;
    }
    if (target instanceof HTMLTextAreaElement) {
      return target.id === "doc-content" ? textareaSurface(target) : null;
    }
    return docEventFromCm(target) ? docSurface() : null;
  }

  //: The file's surface: what other files call (L335).
  Object.assign(window, { docSpellContraction, docProseSkipMask, docProse, docProseScrolled, renderDocProse, DOC_FINDING_SKIP, docFindingKind, docProseHeader, docProseDismissed, docFocusSyncProse, renderDocProsePanel, docIgnoreLabel, docProseIgnore, docProseJump, docProseFix, docBuildVocabulary, hideDocComplete, docCompleteKeydown, docAutocorrectAt, DOC_TOOL_KEYS, docToolPref, docSaveToolPref, docToolsOnInput, docToolsBoxFor });
})();
