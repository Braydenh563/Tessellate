// doc-agent-review.js: an agent's edit to the open document, marked in the editor itself
// (L-documents-41). Fetched by tool-consent.js beside doc-agent-review-lazy.css when an
// `edit_document` card names the document that is open and its text is the one the edit was
// made against. Each hunk of the card's diff (`docDiffLines`, `docDiffHunks`) is drawn in place:
// the lines it removes struck through with the suggestion mode's own marks (`.cm-suggest-del`),
// the lines it adds under them (`.cm-suggest-ins`), and an Accept and a Reject on the hunk. A bar
// over the text holds Accept all and Reject all. Nothing here saves: the last decision, or either
// "all", calls the card's own Allow or Decline, so the save is the card's press (its consent id,
// the skipped hunks, `core/linediff.py` on the server). The editor is read-only while it asks,
// so the text the hunks point at cannot move under them.

(() => {
  const configured = new WeakSet();
  let parts = null;

  //: The field holding the review on screen (null when none), and the effect that sets it.
  function reviewParts(CM) {
    if (parts) return parts;
    const set = CM.state.StateEffect.define();
    const field = CM.state.StateField.define({
      create: () => null,
      update(value, tr) {
        for (const effect of tr.effects) if (effect.is(set)) value = effect.value;
        //: Only a document opened over it changes the text while it is read-only: the marks would
        //: point at lines that are no longer there, so the review leaves the editor.
        return value && tr.docChanged && !tr.effects.some((effect) => effect.is(set)) ? null : value;
      },
      provide: (f) => [
        CM.view.EditorView.decorations.from(f, (value) => (value ? value.deco : CM.view.Decoration.none)),
        CM.view.EditorView.editable.from(f, (value) => !value),
        CM.state.EditorState.readOnly.from(f, (value) => !!value),
        CM.view.showPanel.from(f, (value) => (value ? value.panel : null)),
      ],
    });
    const lost = CM.view.EditorView.updateListener.of((update) => {
      const was = update.startState.field(field, false);
      if (was && !update.state.field(field, false) && update.docChanged) was.lost();
    });
    parts = { set, field, extension: [field, lost] };
    return parts;
  }

  //: Where each hunk sits in the editor's lines: the lines it removes (0-based, in the text as it
  //: is) and the line its added lines and its two buttons go under.
  function hunkPlaces(ops, hunks) {
    const before = [];
    let line = 0;
    for (const op of ops) {
      before.push(line);
      if (op.op !== "+") line += 1;
    }
    return hunks.map((hunk) => {
      const removed = [];
      const added = [];
      for (let i = hunk.from; i <= hunk.to; i += 1) {
        if (ops[i].op === "-") removed.push(before[i]);
        else added.push(ops[i].text);
      }
      const after = removed.length ? removed.at(-1) : before[hunk.from] - 1;
      return { removed, added, after };
    });
  }

  function docAgentReview({ documentId, before, ops, hunks, skipped, onDecide, onAccept, onReject }) {
    const CM = window.CM6;
    const view = docCmView;
    if (!CM || !view || !hunks.length || currentDoc?.id !== documentId || docStr(view.state.doc) !== before) return null;
    const { set, field, extension } = reviewParts(CM);
    if (!configured.has(view)) {
      view.dispatch({ effects: CM.state.StateEffect.appendConfig.of(extension) });
      configured.add(view);
    }
    if (docView === "rendered") setDocView("live", { persist: false });
    const places = hunkPlaces(ops, hunks);
    //: index -> true (accepted) or false (rejected); an undecided hunk is kept, as on the card.
    const decided = new Map();
    let ended = false;

    const bar = document.createElement("div");
    bar.className = "doc-agent-review-bar";
    bar.setAttribute("role", "region");
    bar.setAttribute("aria-label", "Atlas's suggested changes");
    const said = document.createElement("p");
    said.className = "doc-agent-review-said";
    const actions = document.createElement("div");
    actions.className = "doc-agent-review-actions";
    actions.append(
      smallButton("ph:x-circle Reject all", "Leave the document as it is", () => finish(false)),
      smallButton("ph:checks Accept all", "Save every change Atlas suggests", () => finish(true), false)
    );
    bar.append(said, actions);

    function decide(index, accept) {
      if (ended) return;
      decided.set(index, accept);
      if (accept) skipped.delete(index);
      else skipped.add(index);
      onDecide();
      if (decided.size < hunks.length) return draw();
      if ([...decided.values()].some(Boolean)) return finish(null);
      finish(false);
    }

    //: `true` keeps every change, `false` none (the card's Decline), `null` the ones decided.
    function finish(all) {
      if (ended) return;
      if (all === true) skipped.clear();
      end();
      if (all === false) onReject();
      else onAccept();
    }

    class HunkWidget extends CM.view.WidgetType {
      constructor(index, state) {
        super();
        this.index = index;
        this.state = state;
      }
      eq(other) {
        return other.index === this.index && other.state === this.state;
      }
      toDOM() {
        const wrap = document.createElement("div");
        wrap.className = `doc-agent-hunk is-${this.state}`;
        for (const text of places[this.index].added) {
          const row = document.createElement("div");
          row.className = "doc-agent-hunk-line";
          const ins = document.createElement("span");
          ins.className = "cm-suggest-ins";
          ins.textContent = text || " ";
          row.appendChild(ins);
          wrap.appendChild(row);
        }
        const foot = document.createElement("div");
        foot.className = "doc-agent-hunk-foot";
        const name = document.createElement("span");
        name.className = "muted";
        name.textContent = hunks.length > 1 ? `Change ${this.index + 1} of ${hunks.length}` : "Atlas's change";
        const yes = smallButton("ph:check Accept", "Keep this change", () => decide(this.index, true));
        const no = smallButton("ph:x Reject", "Leave these lines as they are", () => decide(this.index, false));
        yes.setAttribute("aria-pressed", String(this.state === "accepted"));
        no.setAttribute("aria-pressed", String(this.state === "rejected"));
        foot.append(name, yes, no);
        wrap.appendChild(foot);
        return wrap;
      }
    }

    function stateOf(index) {
      if (decided.has(index)) return decided.get(index) ? "accepted" : "rejected";
      return skipped.has(index) ? "rejected" : "open";
    }

    function decorations(doc) {
      const { Decoration } = CM.view;
      const ranges = [];
      places.forEach((place, index) => {
        const state = stateOf(index);
        for (const at of place.removed) {
          const line = doc.line(at + 1);
          ranges.push(Decoration.line({ class: `doc-agent-del-line is-${state}` }).range(line.from));
          if (state !== "rejected" && line.to > line.from) ranges.push(Decoration.mark({ class: "cm-suggest-del" }).range(line.from, line.to));
        }
        const pos = place.after < 0 ? 0 : doc.line(place.after + 1).to;
        ranges.push(Decoration.widget({ widget: new HunkWidget(index, state), block: true, side: place.after < 0 ? -1 : 1 }).range(pos));
      });
      return Decoration.set(ranges, true);
    }

    const panel = () => ({ dom: bar, top: true });
    const review = { deco: null, panel, lost: () => end(true) };

    function draw() {
      if (ended) return;
      const open = hunks.length - decided.size;
      said.textContent = `Atlas suggests ${nounCount(hunks.length, "change")} to this document. ${open === hunks.length ? "Accept or reject each one." : `${open} still to decide.`}`;
      view.dispatch({ effects: set.of({ ...review, deco: decorations(view.state.doc) }) });
    }

    function end(lost = false) {
      if (ended) return;
      ended = true;
      if (!lost && docCmView === view) view.dispatch({ effects: set.of(null) });
    }

    draw();
    const first = places[0];
    view.dispatch({ effects: CM.view.EditorView.scrollIntoView(first.after < 0 ? 0 : view.state.doc.line(first.after + 1).from, { y: "center" }) });

    return {
      //: The card's own toggles changed `skipped`: redraw the marks to match.
      refresh: draw,
      end: () => end(),
      //: After the card's press saved: the editor shows the saved text, and Undo puts back the
      //: text it had, in the editor too (the agent undo alone would leave the editor stale).
      saved(result, ran) {
        end();
        const exec = (body) => apiJson("/chat/tools/execute", { method: "POST", body: JSON.stringify(body) });
        const show = async () => {
          if (currentDoc?.id === documentId) docShowSaved(await apiJson(`/documents/${documentId}`));
        };
        show().catch(() => {});
        if (!result?.undo) return;
        pushUndo(
          String(result.label || "Edited the document").replace(/^ph:[\w-]+\s*/, ""),
          () => exec({ name: result.undo.tool, arguments: result.undo.arguments }).then(show),
          () => exec({ name: "edit_document", arguments: ran }).then(show)
        );
      },
    };
  }

  //: Hung on the card's own entry point, which loaded this file, so the shared scope gains no name.
  drawToolConsent.inEditor = docAgentReview;
})();
