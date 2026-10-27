# meaning94-1011 (Brief 94, INBOX 850, 857)

Status: (a) find by meaning built; (b) autocorrect outside the editor built.

## Left
- Library boxes (Library filter, graph filter) are not on the meaning layer: they search notes through `/read/filter` and the search engine, whose meaning half is the embedding search.
- Brief 86's suggest code (status.js) should call `meaningAlts` for its candidates once it lands beside this.
- Autocorrect's table takes Brief 90's owner typos by hand (73 pairs read from `agent/typos90*-1011`'s `owner_typos.json`, 47 kept: the rest are real words); once that fixture is merged, a test can derive the pairs from it.

## Not verified
- Close in meaning against a real embedding model: no torch in the sandbox; the route is tested with a letter-count embedder and the page with /read/near faked in Chromium.
- Autocorrect with an IME, on a real phone keyboard (its own suggestions fire `insertReplacementText`, which this leaves alone), and in the graph's and Write with the AI's boxes (tagged and served by the same code; the sweep drives Capture, Ask and Chat).

## Found, not fixed
- Help's topics keep their document order when searching, so the best match by name can sit below others in the same filter (help top-3 38/60 against settings 58/60).
