// documents-spell.js: the page's half of the spelling second opinion (INBOX 1731).
//
// The worker (`harper-worker.js`, `spell-second.js`) holds a Hunspell dictionary
// for the dialect and the person's own words. This file is what the page keeps
// for it: the words it sends, and the answers it remembers for the spelling
// check (`docSpellLookup`) and the suggestion menu (`docSuggestAlternatives`) to
// read. Loaded in the Library bundle before documents.js; one closure, and what
// other files call is the `Object.assign` at the foot.
(() => {
  //: `words`: root word to {known, suggestions}. `want`: asked for, not yet
  //: sent. `own`: the server's list (the words the notes use twice, never from a
  //: private note), fetched once per session.
  const second = { words: new Map(), want: new Set(), timer: 0, own: null };

  //: The person's own words to the worker: the notes' list plus the dictionary
  //: they added to. Sent whole, again whenever either changes.
  function docOwnWordsSend() {
    const send = () => docGrammarSend({ type: "own", words: [...(second.own || []), ...docDictionary()] }, false);
    if (second.own) return send();
    second.own = [];
    apiJson("/spelling/own-words", { silent: true })
      .then((body) => {
        second.own = (body && body.words) || [];
        send();
        //: What the worker answered before it had these words is asked again.
        docGrammarCache = { text: null, findings: [] };
        renderDocProse();
      })
      .catch(() => send());
  }

  //: The answer for a root word, or null until the worker has given one.
  function docSecondAnswer(root) {
    return second.words.get(root) || null;
  }

  //: Ask about a word the page's own list does not know; true when it will be
  //: answered. A batch a quarter of a second after the last word, so a pass over
  //: a document is one message.
  function docSecondWant(root) {
    if (second.words.has(root) || second.want.has(root) || !docGrammarEnabled()) return false;
    if (!/^[a-z]+(?:'[a-z]+)*$/.test(root)) return false;
    second.want.add(root);
    clearTimeout(second.timer);
    second.timer = setTimeout(flush, 250);
    return true;
  }

  async function flush() {
    const words = [...second.want].slice(0, 200);
    words.forEach((word) => second.want.delete(word));
    if (!words.length) return;
    const answers = await docGrammarSend({ type: "spell", words, dialect: docSpellingVariant() });
    //: No worker, or a failed one: the page's own list decides, as before.
    for (const word of words) {
      second.words.set(word, (answers && answers[word]) || { known: false, suggestions: [] });
    }
    if (second.want.size) flush();
    docSpellCache.clear();
    renderDocProse();
  }

  //: "Add to dictionary" as a row, for the document's menu and the note's alike.
  function dictionaryRow(word) {
    return {
      kind: "action",
      id: "dictionary",
      //: Short (INBOX 552): the word is the heading above it, and "Add
      //: \u201cword\u201d to dictionary" wrapped onto two lines in a narrow panel.
      label: "ph:book-open-text Add to dictionary",
      title: `Add \u201c${word}\u201d to the dictionary`,
      run: async (close = () => {}) => {
        close();
        await docDictionaryAdd(word);
      },
    };
  }

  window.docSpell = { ownWordsSend: docOwnWordsSend, answer: docSecondAnswer, want: docSecondWant, dictionaryRow };
})();
