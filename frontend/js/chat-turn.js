// One chat turn and what only it, or opening a saved chat, draws. Moved out of
// chat-attach.js, chat-agent.js and chat.js on 2026-11-01 for the gzip budget
// (boot diet, audit row 21 PF4): `chatSendTurn` (1,164 lines) is reached only by
// a Send, and `agentTimeline`, `addBubble`, the answer's follow-ups, reminder
// offer, memory and question cards, the run controls and the chat timer only by
// that turn, by `openConversation` (sheets-selects.js) or by the palette's agent
// (palette.js), each of which awaits `ensureModule("chatTurn")` first
// (lazy-entries.js). `sendChatMessage` does the same, and the chat box's first
// focus warms it, so Send finds the file in.

//: **A bare "undo" or "redo" typed in chat runs the app's own** (audit 1028
//: E13), as Ctrl+Z does: sent as a question it got the Help line, and the
//: change the person meant to take back stayed.
const CHAT_UNDO_WORDS = /^(undo|redo)( that| it| the (last |previous )?(change|delete|deletion|one))?( please| now)?[.!]*$/i;

async function chatSendTurn(preset, opts = {}) {
  const input = $("chat-input");
  const status = $("chat-status");
  const prep = await chatSendTurn.stage.ask(preset, opts, input);
  if (prep.done) return prep.value;
  const { question, answeringAgent } = prep;
  opts = prep.opts;
  const committed = await chatSendTurn.stage.commit(opts, question, input, status);
  if (committed.done) return;
  const { sentAttachments, sentImages, sentDocuments, sentFiles, sentMediaFiles, sentBoards, sentAttachmentCards } = committed;

  const t = chatSendTurn.stage.open({ opts, question, input, status, answeringAgent, sentAttachments, sentImages, sentDocuments, sentFiles, sentMediaFiles, sentBoards, sentAttachmentCards });
  try {
    await chatSendTurn.stage.stream(t);
  } catch (error) {
    chatSendTurn.stage.fail(t, error);
  } finally {
    chatSendTurn.stage.teardown(t);
  }

  chatSendTurn.stage.paint(t);
  chatSendTurn.stage.settle(t);
  if (!t.answerRaw) {
    chatSendTurn.stage.empty(t);
    return;
  }
  await chatSendTurn.stage.persist(t);
  chatSendTurn.stage.afterAnswer(t);
}


// The turn's stages, pulled out of `chatSendTurn` in the order it ran them (audit 1028 E44).
// One object on the function rather than top-level names: the shared scope is capped.
chatSendTurn.stage = {
  // The turn's bubbles, its live state and its place in the conversation: everything the stages after it share.
  open(p) {
    const { opts, question, input, status, answeringAgent, sentAttachments, sentImages, sentDocuments, sentFiles, sentMediaFiles, sentBoards, sentAttachmentCards } = p;
    const t = { ...p };
    // Regenerate re-runs the same question without adding a duplicate "you".
    //
    // `displayText` is what the *user* said when the message carries an
    // instruction they did not type, Plan Plan appends one. Showing the appended
    // sentence back to them would read as the app putting words in their mouth,
    // and hiding the request entirely would leave the plan looking as though it
    // came from nowhere; the button they pressed is the explanation.
    const userBubble = opts.skipUserBubble
      ? null
      : addBubble("user", opts.displayText || question, sentAttachmentCards);
    //: A chip's question names the one it was offered under (INBOX 490); a
    //: regenerate keeps what the question it re-asks already had.
    const followupOf = opts.followupOf || (opts.skipUserBubble ? [...$("chat-messages").querySelectorAll(".msg.user")].at(-1)?.dataset.followupOf : "") || null;
    markFollowup(userBubble, followupOf);
    //: **Who answers this question, captured once**, the way `effectiveUseTools`
    //: is below: the picker can move on while this reply is still streaming,
    //: and the bubble's face, the request and the saved turn must all name the
    //: persona that actually answered (the owner: "the avatars need to persist
    //: for what persona was used").
    //: A regenerate in another persona names it (`opts.persona`, E60): this answer only, the picker is left as it was.
    const sentPersona = opts.persona || $("persona-select").value || aiNameNow();
    const { bubble, stepsHolder, recordsHolder, groundingHolder, timeline, paintHooks } = addAssistantBubble(sentPersona);
    bubble.saving = []; // outcomes of cards pressed before the turn is saved wait here (`chatHistoryToSend.settle`)
    // The live counter rides in the bubble it is timing, and leaves with it.
    mountChatTimer(bubble);
    // A newer answer exists, so the previous one's chips stop being the end of
    // the thread: this bubble is, and it has none yet.
    refreshFollowupVisibility();
    // A placeholder until the first event arrives; the first real step evicts it.
    const pending = document.createElement("div");
    pending.className = "agent-step step-pending";
    const pendingLine = progressLine(null, { persona: sentPersona, words: true });
    pending.appendChild(pendingLine);
    stepsHolder.appendChild(pending);
    // The placeholder trails the work rather than vanishing at the first event,
    // so a turn that thinks for a while still shows one live line.
    //: `turnEnded`: `clearPending` appends, and appending a removed node puts it
    //: back, so a late delta after `finally` re-attached "Writing the answer"
    //: under a finished turn. The flag says the turn is over.
    t.turnEnded = false;
    //: Set by the model's first word; see the waiting line below (H8).
    t.heard = false;
    const clearPending = () => {
      t.heard = true;
      if (t.turnEnded) return;
      //: Only when not already last: `onAnswer` calls this per delta, and
      //: re-appending the last child restarts its CSS animation, which froze
      //: the three dots.
      if (stepsHolder.lastElementChild === pending) return;
      stepsHolder.appendChild(pending);
    };
    //: The line's words and shape are driven by `streamChat` itself (`progress:
    //: pendingLine` below), from the events that really arrive (INBOX 649), so
    //: no handler in this turn names a stage of its own.
    // **The turn is marked as generating for its whole length, not just until
    // the first event.** Reported as "none of the generating animations work",
    // and this is the mechanism: `clearPending` above runs on the first event
    // of *any* kind: including `meta`, which this app emits almost
    // immediately, well before the model has produced a word. So the dots
    // appeared for a few hundred milliseconds and then the bubble sat
    // completely still for however long the model actually took, which reads
    // as nothing happening at all.
    //
    // A class on the bubble, cleared in the `finally` that ends the stream, is
    // the state that genuinely lasts as long as the work does, every step
    // that arrives can still evict its own placeholder without taking the
    // "still working" signal down with it.
    bubble.classList.add("is-generating");
    t.meta = null;
    //: This turn's row in the Agent Activity panel, or null while the turn has
    //: done nothing worth a row. **Created lazily, on the first plan or the
    //: first tool call**, and that is deliberate: a plain question with a plain
    //: answer is not a "run", and a row per chat message would rebuild the wall
    //: of text this panel was just taken apart to stop being.
    t.activityRun = null;
    t.toolsActed = false;
    t.stats = null;
    // Captured so the final save below can persist it. Reported directly: the
    // "Grounded in" chips under a direct Q&A answer only ever existed for the
    // live stream: reopening the chat, or leaving the tab and coming back,
    // showed an answer with no sources at all. Same unfixed-until-now shape as
    // raw_results/search_mode/match_info a few lines below, which got exactly
    // this treatment already for the same reported-missing-on-reload reason.
    t.groundingSentences = null;
    t.chatOffer = null;
    //: The screen-aware next step (E52): drawn beside the answer, never in its text.
    t.chatTip = "";
    t.whyLines = null; // the why event (B30), drawn last
    t.groundingSupport = null; // the stream's own support, saved with a composed turn (INBOX 1706)
    t.composedNext = []; // a composed answer's own next questions (INBOX 725)
    t.turnFrame = null; // what the composed answer showed, echoed with the next turn
    //: **Numbered while it streams, as the Ask tab is** (INBOX 320, the
    //: askcite row): the backend sends the rows so far each time a sentence
    //: completes (`grounding_live`), and the markers are put back after every
    //: live paint, which rebuilds the step. The numbering is the final pass's
    //: own (`chatSourcesFrom` over this turn's meta), so a digit that appears
    //: mid-answer is the digit it keeps. The `grounding` event still replaces
    //: these rows when the stream ends.
    t.liveSources = null;
    const placeLiveCitations = () => {
      if (t.groundingSentences?.length) {
        addInlineCitations(
          bubble.querySelectorAll(".bubble-answer"),
          t.groundingSentences,
          t.meta?.raw_results || [],
          t.liveSources
        );
      }
    };
    paintHooks.afterAnswerPaint = placeLiveCitations;
    // INBOX 272 part 1: set when the model couldn't call tools and the turn
    // was silently answered as plain Q&A instead. Captured here, rendered
    // once the stream is over (same reason `groundingSentences` waits: a
    // notice drawn mid-stream would be for a bubble the live renderer is
    // about to rebuild).
    t.toolsUnsupportedEvent = null;
    // Whether the user pressed Stop. An empty answer they asked for needs no
    // explanation; one they didn't ask for does.
    t.miss = undefined;
    t.failure = "";
    t.stopped = false;
    // Set when the agent ends its turn by handing the job to a saved skill.
    // The run can't start from inside the stream, this turn is still holding
    // the input box and the conversation, so it is remembered and started
    // once everything below has run.
    t.handoff = null;
    // Set when the turn ended by asking the person something: the question is
    // the answer, and "the model finished without writing anything" over a
    // question card (INBOX 169, with a screenshot) blamed the model for
    // doing what it was told.
    t.asked = false;
    t.askedQuestion = null;
    // Set when the turn stopped because it ran out of rounds, and, for a skill
    // run: the step it did not get past. Both become a button at the end of the
    // bubble rather than a sentence asking the user to type "carry on".
    t.ranOutOfRounds = false;
    t.stoppedAtStep = null;
    t.pausedForManual = false;
    const startedAt = performance.now();
    const toolEvents = []; // {label, ok}: persisted so chips survive a reload
    //: Everything this turn opened, deduped on kind+id, for the Sources panel.
    //: A Map rather than an array because a turn that reads the same note twice
    //: has one source, not two, and `touched` arrives per tool call.
    const touchedItems = new Map();
    chatController = new AbortController();
    const controller = chatController;
    //: Half-rendered markdown is not read out frame by frame while it streams (E68).
    $("chat-messages").setAttribute("aria-busy", "true");
    //: The app's mark lifts its cells while a turn runs (phone-shell.js).
    syncEmblemBusy();
    //: Atlas looks up to think while a turn runs (avatars.js).
    if (typeof setAtlasMood === "function") setAtlasMood("thinking");

    // --- the turn owns its conversation ----------------------------------------
    // `chatConv` is reassigned by every switch, and saves used to read it live,
    // so a turn that finished after a switch was written into whichever chat was
    // open. `convRef` pins the asking conversation; `viewing()` says whether it
    // is still on screen, the only time this turn may touch the pane.
    const convRef = chatConv;
    const viewing = () => chatConv === convRef;

    // The live nodes, kept: `openConversation` rebuilds the transcript, so coming
    // back re-attaches these same still-streaming elements. Set once here, never
    // by a switch, or the notice names the wrong conversation.
    chatStreaming = {
      conv: convRef,
      title: $("chat-title").textContent || "that chat",
      nodes: [userBubble, bubble].filter(Boolean),
      announced: false,
    };

    // --- checkpointing a long turn --------------------------------------------
    // A row for this turn already exists, so the save at the end has to update
    // it rather than append a second copy of the same exchange.
    t.checkpointed = false;
    t.checkpointInFlight = false;
    //: The checkpoint's own promise, so the save at the end can wait for it.
    //: Without it a fast model finished while the first checkpoint's create
    //: was still in flight, the end save saw no id yet and created a second
    //: conversation: the README's Chat shot listed "What is left before the
    //: Harbor launch?" twice, 43ms apart (INBOX 431 (g)).
    t.checkpointRun = null;

    Object.assign(t, { keepCard(card, mark = card) { mark.act_slot = (t.actCards ||= []).length; t.actCards.push(card); }, userBubble, followupOf, sentPersona, bubble, stepsHolder, recordsHolder, groundingHolder, timeline, paintHooks, pending, pendingLine, startedAt, toolEvents, touchedItems, controller, convRef, viewing, clearPending, placeLiveCitations });
    //: **A new chat gets its row at send time, not at the first agent round.**
    //: A plain answer has no round boundary, so a chat started with one had no
    //: row, and so no entry in the list, until the reply finished: start a new
    //: chat, open another, and the first one could not be reached again until
    //: it was done (the owner, 2026-10-12). The row holds the question and an
    //: empty answer; `openConversation` already drops that partial turn and
    //: puts the live bubbles back (`isStreamingConversation`).
    if (convRef.id === null && !convRef.private) chatSendTurn.stage.checkpointTurn(t);

    // Captured once, not re-read at save time: the toggle can move on to the
    // next message while this one is still streaming, and the meta line and
    // the saved turn must both say what actually answered *this* question.
    //: Agent only when something can call tools: the saved toggle stays on with
    //: no model (renderChatModeSeg greys it), and a turn sent then is Ask's.
    const effectiveUseTools = opts.useTools ?? ($("tools-toggle").checked && !(aiIsOff() && !modelStatus?.tools_engine));
    t.effectiveUseTools = effectiveUseTools;
    return t;
  },

  // The request goes out and the answer streams in, one handler per event the server sends.
  async stream(t) {
    const { opts, question, status, answeringAgent, sentAttachments, sentImages, sentDocuments, sentFiles, sentMediaFiles, sentBoards, sentPersona, pendingLine, controller, convRef, viewing, effectiveUseTools } = t;
    //: A silent model used to leave "Waking the model..." up forever (H8).
    t.slowLoad = setTimeout(() => {
      if (!t.heard && viewing()) status.textContent = "Waiting for the model… Stop, or ask again.";
    }, 8e3);
    await streamChat({
      progress: pendingLine,
      question,
      history: chatHistoryToSend(),
      attempt: opts.attempt,
      persona: sentPersona,
      oneModel: opts.oneModel,
      mode: $("response-mode-select").value || null,
      useTools: effectiveUseTools,
      isPrivate: convRef.private,
      noteIds: sentAttachments,
      imageMediaIds: sentImages,
      documentIds: sentDocuments,
      fileIds: sentFiles,
      mediaFileIds: sentMediaFiles,
      boardIds: sentBoards,
      skill: opts.skill,
      skillInputs: opts.skillInputs,
      skillFromStep: opts.skillFromStep,
      skillOnlyStep: opts.skillOnlyStep,
      skillStepText: opts.skillStepText,
      // Read live rather than captured at launch: a run that started
      // straight-through and is now being Resumed can still be switched to
      // step-by-step, and vice versa.
      skillManual: opts.skillManual ?? Boolean($("skill-manual-toggle")?.checked),
      skillManualNote: opts.skillManualNote,
      plan: opts.plan,
      attachedNotesOnly: opts.attachedNotesOnly,
      answeringAgent,
      signal: controller.signal,
      ...chatSendTurn.stage.onStreamStart(t),
      ...chatSendTurn.stage.onStreamTools(t),
      ...chatSendTurn.stage.onStreamExtras(t),
    });
    if (viewing()) status.textContent = "";
  },
  // Handlers for the opening events: meta, grounding, plan, steps, result.
  onStreamStart(t) {
    const { question, status, bubble, groundingHolder, timeline, toolEvents, clearPending, placeLiveCitations } = t;
    return {
      onMeta: (m) => {
        t.meta = m;
        //: No model runs: the answer is composed from the notes (INBOX 725).
        //: A web reply's second meta (`chat_web.NOT_NOTES`) wakes no model.
        if (!m?.web) status.textContent = m?.composed ? "Composing from your notes, no AI…" : "Waking the model…";
      },
      onRelated: (event) => {
        ensureModule("replyKit").then(() => renderRelatedElsewhere(groundingHolder, event.items)).catch(() => {});
      },
      onUnsupported: (event) => {
        t.toolsUnsupportedEvent = event;
      },
      onGroundingLive: (event) => {
        t.groundingSentences = event.sentences || [];
        t.liveSources = chatSourcesFrom({ meta: t.meta, toolEvents: [], touched: [], sentences: t.groundingSentences });
        placeLiveCitations();
      },
      onGrounding: (event) => {
        t.groundingSentences = event.sentences;
        t.composedNext = Array.isArray(event.next) ? event.next : [];
        t.groundingSupport = event.support || null;
        if (["note", "checklist", "reminder"].includes(t.groundingSupport?.offer?.kind)) t.keepCard({ type: "offer", offer: t.groundingSupport.offer }, t.groundingSupport.offer);
        renderAnswerGrounding(
          groundingHolder,
          event.sentences,
          t.meta?.raw_results || [],
          //: Every prose block of this turn, not the first: see
          //: `addInlineCitations`. A skill run has one per step.
          bubble.querySelectorAll(".bubble-answer"),
          //: The turn's own question, so opening a source here teaches the
          //: search the same thing it learns from the Ask tab.
          question,
          null,
          event.support || null,
          t.meta?.picture_alts || null
        );
        //: Each insight line the answer said carries Confirm and Not right
        //: (CHAT_PLAN decision 60), under the answer, one row each.
        for (const insight of event.insights || []) {
          if (insight.confirmed && insight.rule !== "drift") continue;
          const line = insightLine(insight, insight.in_answer ? (insight.rule === "drift" ? "Is that open plan right?" : "Is that pattern right?") : `Pattern: ${insight.short}.`, (row, verdict, result) => {
            row.textContent = verdict === "confirmed" ? `Confirmed: ${result.line}` : verdict === "done" ? "Marked done" : "Not right: it will not be shown again.";
          }, "muted");
          groundingHolder.appendChild(line);
          //: A digest answer hides this holder (its marks are inline), and the
          //: rows are not citations: show it for them.
          groundingHolder.classList.remove("hidden");
        }
      },
      onPlan: (event) => {
        clearPending();
        timeline.plan(event);
        //: A turn's own card: its tool rows are already in the panel's run.
        if (event.kind === "turn") return chatScrollToEnd();
        // …and the same run as one row in the activity panel. Both are drawn
        // from this one event, so they cannot disagree about how many steps
        // there are or what the run is called.
        t.activityRun = addAgentRun({
          kind: event.kind === "plan" ? "plan" : "skill",
          name: event.skill || "Run",
          icon: event.kind === "plan" ? "ph:compass" : "ph:lightning",
          steps: event.steps || [],
        });
        openPanelForRun(t.activityRun);
        status.textContent =
          event.kind === "plan"
            ? `Working through ${(event.steps || []).length} steps…`
            : `Running “${event.skill}”…`;
        chatScrollToEnd();
      },
      onStep: (event) => {
        clearPending();
        timeline.step(event);
        if (event.kind !== "turn") agentRunStep(t.activityRun, event);
        if (event.state === "running") {
          status.textContent = `Step ${event.index + 1}: ${event.text}`;
        }
        chatScrollToEnd();
      },
      onResult: (event) => {
        clearPending();
        timeline.result(event);
        // Where the run stopped, if it did. A number here means the steps
        // after it never ran.
        t.stoppedAtStep = typeof event.stopped_at === "number" ? event.stopped_at : null;
        t.pausedForManual = Boolean(event.paused);
        // A skill that changed notes has just made the list on screen stale.
        if ((event.changes || []).length) loadEntries();
        chatScrollToEnd();
      },
    };
  },
  // Handlers for the limit, the thinking and answer text, and each tool call.
  onStreamTools(t) {
    const { question, status, bubble, recordsHolder, timeline, toolEvents, touchedItems, clearPending } = t;
    return {
      onLimit: () => {
        // Out of rounds with tools still in flight. Only remembered here: the
        // offer to continue belongs beneath the answer that says it stopped,
        // and that answer has not been written yet.
        t.ranOutOfRounds = true;
      },
      onThinking: (delta) => {
        clearPending();
        timeline.thinking(delta);
        //: Reasoning is still waiting, as far as the reader is concerned:
        //: `streamChat` sets the "thinking" phase (dots) before this runs, so
        //: a turn that thinks *after* writing goes back to dots.
        status.textContent = "The model is thinking…";
        chatScrollToEnd();
      },
      onAnswer: (delta) => {
        clearPending();
        timeline.answer(delta);
        status.textContent = "The model is writing…";
        chatScrollToEnd();
      },
      onTool: (event) => {
        clearPending();
        //: The fallback strips the failed call's own icon token before
        //: prefixing the warning one. `setLabel` only resolves a token at the
        //: start of the string, so `ph:warning ph:books Listed notes` renders
        //: one warning glyph and then prints "ph:books" as literal text: 
        //: the same defect reported in the palette's status line, one branch
        //: over and only reachable when a tool fails.
        const label = event.ok
          ? event.label
          : `ph:warning ${(event.error || event.label || "").replace(/^ph:[\w-]+\s*/, "")}`;
        timeline.tool(toolChip(label, event.ok, event));
        pushAgentChangeUndo(event.change, event);
        //: The same call, filed in the panel under the step that made it. A
        //: second `toolChip` rather than the same node: one element cannot be
        //: in two places, and the panel's copy has to survive the chat being
        //: cleared or the conversation being closed.
        if (!t.activityRun) {
          // An agent turn with no plan is still a run, it is what the report
          // called "agent model activity", and its first tool call is the
          // moment it becomes one.
          t.activityRun = addAgentRun({
            kind: "agent",
            name: agentRunTitle(question),
            icon: "ph:strategy",
          });
          openPanelForRun(t.activityRun);
        }
        agentRunTool(t.activityRun, toolChip(label, event.ok, event));
        toolEvents.push(event); // remember for persistence
        for (const item of event.touched || []) {
          touchedItems.set(`${item.kind}:${item.id}`, item);
        }
        if (event.proposal) {
          // Asked where it was suggested, not in a settings page nobody opens.
          showWaiting(recordsHolder, renderMemoryProposal, event.proposal);
        }
        if (event.ok) t.toolsActed = true;
        if (event.wrote) bubble.dataset.wrote = "1";
        //: A page the model read, or the results of a search it ran, are one
        //: web fold under their step (INBOX 1300 C06, decision 66): the same
        //: fold and in-place reader a composed answer's results use, folded
        //: shut. The Sources panel still lists each page for the citations.
        if (event.ok && event.tool === "read_url") drawAnswerPanels(timeline.holder, [{ web: event.sources, read: true }]);
        if (event.ok && event.tool === "web_search") drawAnswerPanels(timeline.holder, [{ web: event.sources }]);
        status.textContent = "The model is making changes…";
        chatScrollToEnd();
      },
    };
  },
  // Handlers for web sources, charts, panels, the questions the AI asks, offers, tips and stats.
  onStreamExtras(t) {
    const { status, bubble, recordsHolder, timeline, toolEvents, clearPending } = t;
    return {
      //: The web pages an answer from no model read (CHAT_PLAN decision 37).
      onWebSources: (event) => ensureModule("askCompose").then(() => renderWebSources(timeline.holder, event.sources)),
      //: A bar of counts from a no-model answer (CHAT_PLAN decision 59, step
      //: 2), drawn by the Ask box's chart recipe under the answer's line.
      onChart: (event) => ensureModule("askHistory").then(() => {
        const host = document.createElement("div");
        host.className = "ask-chart";
        timeline.holder.appendChild(host);
        drawAskChart(host, event.chart);
        chatScrollToEnd();
      }),
      //: The notebook's cards or the calculator (INBOX 1300 C06), drawn by
      //: the one reply renderer every answer surface shares.
      onPanel: (event) => drawAnswerPanels(timeline.holder, [event]).then(chatScrollToEnd),
      onConfirm: (event) => {
        clearPending();
        //: Waiting cards are output (`showWaiting`); an act's is the answer's own.
        if ((event.type === "act" && !event.cancel && (!event.settle || event.done)) || event.type === "confirm") t.keepCard(event);
        showWaiting(event.type === "act" ? timeline.holder : recordsHolder, renderToolConfirm, event);
        if (event.done) bubble.dataset.wrote = "1"; // an act that ran at once wrote
        if (!event.cancel && !event.done && !event.settle) status.textContent = "Waiting for your confirmation…";
      },
      onAsk: (event) => {
        clearPending();
        showWaiting(recordsHolder, renderAgentQuestion, event);
        status.textContent = "Waiting for your answer…";
        chatAwaitingAgentAnswer = true;
        t.asked = true;
        t.askedQuestion = event.question;
      },
      onRunSkill: (event) => {
        // The model picked a saved skill for this job (§33). Its turn is over;
        // the run starts below, once this one has finished tidying up.
        clearPending();
        timeline.tool(toolChip(event.label, true));
        toolEvents.push({ label: event.label, ok: true });
        status.textContent = `Waiting for you to run “${event.skill}”…`;
        t.handoff = event;
        chatScrollToEnd();
      },
      onRunPlan: (event) => {
        // The model decided the job has several parts and planned it (§35K).
        // Same handover as a skill: the turn is over and the steps run one at
        // a time below, so nothing is left half-done.
        clearPending();
        timeline.tool(toolChip(event.label, true));
        toolEvents.push({ label: event.label, ok: true });
        status.textContent = "Working out the steps…";
        t.handoff = event;
        chatScrollToEnd();
      },
      onCompressReview: (event) => {
        // The model asked to compress the chat (§37I). Unlike run_skill/
        // run_plan this isn't a run to start, it opens the same review
        // panel the manual Compress button fills in, and the summary is
        // used only if the user presses Apply there. Not set on `handoff`:
        // that path always starts something; this one waits for a person.
        clearPending();
        const label = "ph:arrows-in Suggested compressing the earlier messages";
        timeline.tool(toolChip(label, true));
        toolEvents.push({ label, ok: true });
        showCompressReview(event, event.turns);
        status.textContent = "Waiting for you to review the summary…";
        chatScrollToEnd();
      },
      onOffer: (event) => { t.chatOffer = event.offer || null; },
      onFrame: (frame) => { t.turnFrame = frame || null; },
      onTip: (event) => { t.chatTip = event.text || ""; },
      onWhy: (event) => { t.whyLines = event.lines; },
      onStats: (event) => {
        // A round finished. Asked for directly: *"a new chat should be saved
        // after agent turns as well, not after the whole response is
        // complete."* Correct, and the reason is that an agent turn is minutes
        // of work on a local model, closing the window, a stall, or the
        // server going away halfway through used to lose **the entire
        // conversation**, because nothing was written until the last round
        // returned. A checkpoint per round means the worst case is losing the
        // round in progress rather than the thread.
        //
        // Fire-and-forget, and silent: a checkpoint that interrupts the answer
        // to complain about the network would be worse than the data loss it
        // is preventing. The turn's real save still happens at the end and
        // overwrites this with the finished version.
        if (event.round) chatSendTurn.stage.checkpointTurn(t);
        //: The header's context meter, updated live rather than at the end of
        //: the turn: on a long agent run the window fills round by round, and
        //: the number is only useful while there is still a decision to make
        //: about it.
        renderChatContextMeter(event);
        // An agent turn reports once per round, so these accumulate: output
        // tokens and generation time add up, while the prompt size is the
        // largest context the model was given rather than the sum.
        if (!t.stats) {
          t.stats = { ...event };
          return;
        }
        t.stats.model = event.model || t.stats.model;
        t.stats.prompt_tokens = Math.max(t.stats.prompt_tokens || 0, event.prompt_tokens || 0);
        t.stats.output_tokens = (t.stats.output_tokens || 0) + (event.output_tokens || 0);
        t.stats.eval_ms = (t.stats.eval_ms || 0) + (event.eval_ms || 0);
        // The agent tags each round; the highest is how many it took.
        t.stats.round = Math.max(t.stats.round || 0, event.round || 0);
        // The window doesn't change between rounds, but the peak prompt does, 
        // and the peak is the one worth reporting, because it is the round
        // that came closest to overflowing.
        t.stats.context_tokens = event.context_tokens || t.stats.context_tokens;
        // One estimated round makes the whole total an estimate. Reporting a
        // mixed figure as measured would be the dishonest way round.
        if (event.usage_source === "estimated") t.stats.usage_source = "estimated";
      },
    };
  },
  // The stream threw: a Stop is quiet, anything else is marked on the timeline and the status line.
  fail(t, error) {
    const { status, timeline, viewing } = t;
    if (error.name === "AbortError") {
      t.stopped = true;
      if (viewing()) status.textContent = "Stopped.";
    } else {
      // The timeline is this turn's own, detached or not, so it is always
      // marked failed; only the shared status line is conditional.
      //: The step names what failed, in the server's own plain sentence
      //: (owner, 2026-10-17: the old fixed line said nothing). A message
      //: too long to be a sentence, or none, falls back to a line that still
      //: says what to do next.
      t.miss = error instanceof TypeError;
      const said = String(error.message || "").trim();
      timeline.failRunningStep(
        said && said.length <= 160 ? said : "The model stopped before it finished. Try again, or check Settings, Models."
      );
      t.failure = said && said.length <= 160 ? said : "The model stopped before it finished.";
      if (viewing()) {
        status.textContent = error.message;
        status.classList.add("error");
      }
    }
  },
  // Runs however the stream ended: queue released, chrome reset, the run closed.
  teardown(t) {
    const { opts, input, bubble, timeline, pending, controller, convRef, viewing } = t;
    clearTimeout(t.slowLoad);
    //: Until `sendChatMessage` returns, a message sent here is queued, not a second turn racing this save.
    chatQueue.finishing.add(convRef);
    opts.finishing = convRef;
    // Whatever happened, answered, stopped, errored, the turn is no longer
    // generating, so the signal that says it is has to come down here rather
    // than on any one success path.
    bubble.classList.remove("is-generating");
    // The one place the trailing progress line is taken down, the turn is
    // genuinely over here, whether it ended, errored or was aborted. The flag
    // goes up *first*: see `clearPending` for the callback that used to run
    // after this line and put the node straight back.
    t.turnEnded = true;
    pending.remove();
    //: **Every visual "still working" state comes down here, on every exit.**
    //:
    //: Reported with a screenshot of a finished skill run still showing both
    //: the streaming caret and "Writing the answer…". `finalise()` was called
    //: on the success path only, so a turn that ended any other way, an
    //: error, a stop, the round limit, kept the caret blinking on prose that
    //: had stopped arriving. It is idempotent, so calling it here as well
    //: costs nothing and closes every path at once, which is the property the
    //: success-path-only version could never have.
    timeline.finalise?.();
    //: Whatever step group is still open stops saying "Working", see
    //: `agentTimeline.finish`.
    timeline.finish?.();
    //: …and the same for this turn's row in the activity panel, on the same
    //: every-exit reasoning: a row still saying "Running" after the turn
    //: errored or was stopped is the panel telling a lie for the rest of the
    //: session. `stoppedAtStep`/`pausedForManual` come from the `result`
    //: event, so the row can say *how* it ended rather than only that it did.
    const endState = t.stopped
      ? "stalled"
      : t.pausedForManual
        ? "paused"
        : typeof t.stoppedAtStep === "number"
          ? t.activityRun?.steps?.[t.stoppedAtStep]?.state === "failed"
            ? "failed"
            : "stalled"
          : "done";
    endAgentRun(t.activityRun, { state: endState });
    //: The transcript is not a live region (deltas every 66 ms would be read
    //: word by word), so a finished answer is said once (audit 1028 E35).
    if (endState === "done" && viewing()) announce(timeline.text());
    //: …and Atlas's face says how it went, for a moment.
    if (typeof setAtlasMood === "function") {
      setAtlasMood(endState === "done" ? "happy" : endState === "failed" ? "surprised" : "calm", 5000);
    }
    // Only if it is still ours. Switching away and sending a second message
    // installs a new controller, and this line firing late would null it, 
    // leaving Stop wired to nothing while a stream was genuinely running.
    if (chatController === controller) {
      chatController = null;
      matchReasonBadge.reveal();
      $("chat-messages").removeAttribute("aria-busy"); // end, error and Stop all land here
      stopChatTimer();
      syncEmblemBusy();
      // The turn is over: it is saved (or about to be) and a reload of this
      // thread will render it like any other. Re-attaching these nodes after
      // that point would show it twice.
      if (chatStreaming?.conv === convRef) chatStreaming = null;
    }
    // The composer belongs to whatever conversation is on screen. A turn that
    // finishes after the reader has moved on must not re-enable, refocus or
    // re-label the box they are now typing into, releaseChatComposer already
    // put it back when they switched.
    if (viewing()) {
      input.disabled = false;
      show("chat-send");
      //: The focus goes back to the box only from the Stop button (which
      //: took it when the answer began, `sendChatMessage`) or from nowhere:
      //: a reader who moved to the search box or the sidebar while the
      //: answer streamed keeps their place, rather than having the box take
      //: it as the answer ends (the review, 2026-09-27).
      const fromStop = document.activeElement === $("chat-stop") || document.activeElement === document.body;
      hide("chat-stop");
      if (fromStop) input.focus();
    }
  },
  // The finished answer drawn: sources, citations, why trail, footer, resume controls.
  paint(t) {
    const { opts, question, bubble, recordsHolder, timeline, startedAt, toolEvents, touchedItems, effectiveUseTools, clearPending } = t;
    clearPending();
    timeline.finalise();
    //: **The citations go back in after the final render.** Same defect as the
    //: Ask box's, one surface over and for the same reason: `onGrounding` writes
    //: the markers straight into the answer during the stream, and `finalise()`
    //: re-renders every prose step from its raw markdown, throwing all of them
    //: away a few milliseconds later. The grounding event always arrives before
    //: `done`, so this was true of every answer that had any.
    //: Built once, here, and handed to both the citation pass and the panel,
    //: so the digit in the prose and the digit on the row are the same number
    //: by construction rather than by two functions agreeing about order.
    const turnSources = chatSourcesFrom({
      meta: t.meta,
      toolEvents,
      touched: [...touchedItems.values()],
      sentences: t.groundingSentences,
      composed: Boolean(t.meta?.composed),
    });
    //: The page this turn went out to read, for a follow-up about it
    //: (`webFollowUp`, web-clip.js).
    chatWeb.lastUrl = turnSources.find((source) => source.kind === "web" && source.url)?.url || null;
    if (t.groundingSentences?.length) {
      addInlineCitations(
        bubble.querySelectorAll(".bubble-answer"),
        t.groundingSentences,
        t.meta?.raw_results || [],
        turnSources
      );
    }
    const answerEls = bubble.querySelectorAll(".bubble-answer");
    placeAnswerFigures(answerEls, t.meta, question);
    //: Who wrote it (INBOX 1300 C14), as a badge beside the name in the head.
    const head = bubble.querySelector(".msg-role");
    const model = t.stats?.model || t.meta?.answered_by;
    finishReply(answerEls, { composed: t.meta?.composed, head, model, engine: Boolean(t.meta), bubble, unsupported: t.toolsUnsupportedEvent, trimmed: t.stats?.composition?.history_dropped });
    //: An answer's one acting offer, the Ask box's (`digestOffer`): a place's link.
    if (t.chatOffer) ensureModule("askCompose").then(() => digestOffer([...bubble.querySelectorAll(".bubble-answer")].pop(), t.chatOffer)).catch(() => {});
    const answerRaw = timeline.text();
    const thinkingRaw = timeline.thinkingText();
    //: **The Sources panel replaces the old "N matching notes" disclosure here.**
    //: It is a superset, it carries the same retrieved notes and adds the
    //: files and pages the turn read and the things it opened, which had no
    //: home at all. `renderRecordsDetails` stays for the Ask tab, which has one
    //: answer rather than a thread and no tool events to fold in.
    const sourcesPanel = chatSourcesPanel({
      meta: t.meta,
      toolEvents,
      touched: [...touchedItems.values()],
      sources: turnSources,
    });
    if (sourcesPanel) recordsHolder.appendChild(sourcesPanel);
    if (t.chatTip) {
      const tip = document.createElement("p");
      tip.className = "muted answer-tip";
      tip.textContent = t.chatTip;
      recordsHolder.prepend(tip);
    }
    //: Why this answer (B30), the Ask box's own fold, after the sources.
    if (t.whyLines) ensureModule("askCompose").then(() => drawWhyTrail(recordsHolder, t.whyLines)).catch(() => {});
    // INBOX 272 part 1: drawn once the stream is over, same reason
    // `groundingSentences` waits (a notice inserted mid-stream is inside a
    // bubble the live renderer is about to rebuild from raw markdown).
    //: Drawn by `replyFinish` (`finishReply` above), above the facts line.
    // What this answer cost: model, wall-clock time, tokens, speed.
    const elapsedMs = Math.round(performance.now() - startedAt);
    //: For the status bar's AI dot (Placed 2026-09-09 item 99 (c)).
    if (t.stats) {
      lastAnswerFacts = { model: model || "", ms: elapsedMs, used: Number(t.stats.prompt_tokens) || 0, window: Number(t.stats.context_tokens) || 0 };
      renderAiPill();
    }
    // A turn that only ran tools still cost time and tokens, so it gets a meta
    // line too: previously an agent turn with no prose showed nothing at all.
    //: **Who wrote it, in the head** (the owner, 2026-10-10: "should say if the
    //: composer or a specific ai model generated it"; INBOX 1300 C14: "a badge
    //: or smnth similar"): the `replyByline` chip through `finishReply` above,
    //: From your notes, the model, or Composer when the app answered itself.
    //: Stop before the first word left a bubble with a name and no body
    //: (HR9); it says what happened where the answer would have been.
    if (t.stopped && !answerRaw && !toolEvents.length) {
      bubble.append(Object.assign(document.createElement("div"), { className: "msg-meta", textContent: "Stopped before an answer." }));
    }
    if (answerRaw || toolEvents.length) {
      bubble.appendChild(
        messageMetaLine({
          model,
          elapsedMs,
          stats: t.stats,
          toolCount: toolEvents.length,
          rounds: t.stats?.round || 0,
          usedTools: effectiveUseTools,
          stopped: t.stopped,
        })
      );
    }
    // A turn that stopped short offers the way onward, in the two shapes it can
    // take. Not shown when the user pressed Stop, they know why it ended, and
    // not when a skill run finished every step it had.
    // A run that stopped early is exactly the kind of thing you find out about
    // ten minutes later, having walked away from a long job (§36E). The Resume
    // button below is the fix in the moment; this is the record afterwards.
    // A deliberate manual-mode pause is not a failure and not something to
    // notify about ten minutes later, the person is sitting right here
    // waiting for the Continue button, which is the whole point of asking for
    // it. Only an *unplanned* stop (a real failure, or running out of rounds)
    // earns the notification.
    if (!t.stopped && !t.pausedForManual && (t.stoppedAtStep !== null || t.ranOutOfRounds)) {
      recordNotification({
        kind: "run",
        title: opts.skill ? `“${opts.skill}” stopped early` : "A long answer stopped early",
        detail:
          t.stoppedAtStep !== null
            ? `Got as far as step ${t.stoppedAtStep + 1}. Reopen the chat to resume.`
            : "It ran out of rounds. Reopen the chat to continue.",
        key: `run:${opts.skill || "answer"}:${Date.now()}`,
        action: { tab: "chat" },
      });
    }
    //: **A run you stopped can be picked up again** ("cant continue canceled
    //: skills??"): the `!stopped` guard belongs on the notification above, not on
    //: the resume button; Stop means "not right now". A rewrite of the step that
    //: stalled (Phase D) runs that step alone, so the rest can still resume.
    //: Built from this turn's state or, on reopen, the copy saved with the turn.
    const resumeState = {
      skill: opts.skill || null,
      skillInputs: opts.skillInputs || {},
      stopped: t.stopped,
      stoppedAtStep: t.stoppedAtStep,
      pausedForManual: t.pausedForManual,
      ranOutOfRounds: t.ranOutOfRounds,
      hasTools: toolEvents.length,
      cutWords: Boolean(answerRaw), // a plain stopped answer offers Continue (E60)
      useTools: effectiveUseTools,
    };
    appendRunResumeControls(bubble, { ...resumeState, timeline });
    chatScrollToEnd();
    Object.assign(t, { answerRaw, thinkingRaw, turnSources, elapsedMs, resumeState, model });
  },
  // What the turn started or changed: refresh after tool writes, and a skill handed over to the page.
  settle(t) {
    const { recordsHolder } = t;
    if (t.toolsActed) refreshAfterToolChanges(); // the AI changed real data
    if (t.handoff) {
      // Start the run as its own message, down the same path the Skill dropdown
      // uses: so the plan, the ticked steps, the change list and every Undo
      // work here exactly as they do when the user picks the skill themselves.
      // Deferred by a task because this turn is still finishing: it re-enables
      // the input box in `finally`, and the run needs to disable it again.
      //: A plan the model drew waits for Run the plan (row 3: approved once,
      //: with each step's writes listed); a skill the person saved starts.
      const plan = t.handoff;
      //: A skill by sentence or by the model asks the same way (decision 75): a press or a typed yes is the consent.
      //: A typed yes already agreed (`consented`, `ai/consent.py`), so it starts with no card.
      const start = plan.type === "run_plan" ? () => startPlannedRun(plan.goal, plan.steps) : () => startSkill({ name: plan.skill }, plan.inputs || {});
      const ask = plan.type === "run_plan" ? plan : { goal: `Run the skill “${plan.skill}”?`, steps: plan.changes_notes ? ["It can change your notes. Each change can be undone."] : [], runLabel: "Run the skill", running: `Starting “${plan.skill}”`, consent_id: plan.consent_id, ask_label: plan.ask_label };
      if (plan.consented) start();
      else showWaiting(recordsHolder, planProposalCard, ask, start);
    }
  },
  // The model returned nothing: restore the old answer, or say why and offer a way forward.
  empty(t) {
    const { opts, bubble, timeline, model } = t;
    // The model returned nothing. This used to return early and leave the
    // bubble sitting there with the notes disclosure, no answer, no error and
    // no buttons: a dead end with nothing to click and nothing explaining it.
    if (opts.replaceLast) {
      //: No new answer: the old one goes back (audit 1029 H7).
      bubble.remove();
      if (opts.restore) $("chat-messages").appendChild(opts.restore);
      toast("The model returned nothing that time. Try again.", "info");
      return;
    }
    // A turn that ended by starting a skill said nothing on purpose, the run
    // below is the answer. Complaining that the model wrote nothing would be
    // wrong, and the retry button would re-run the choosing turn rather than
    // the skill.
    if (!t.stopped && !t.handoff && !t.asked) {
      const note = document.createElement("p");
      note.className = "muted";
      //: A failed turn says why (the server's own sentence) and offers the
      //: way out: Try again, and Settings, Models (audit 1031 HR2, AI6).
      note.textContent = t.miss
        ? "Can't reach the app. Is it open?"
        : t.failure || "The model wrote nothing. Try again, or ask it another way.";
      timeline.ensureAnswerBox().replaceChildren(note);
      // Retry and delete at minimum, so there's always a way forward.
      (bubble.querySelector(":scope > .msg-role") || bubble).appendChild(
        chatMessageActions([
          { label: "ph:arrow-clockwise", title: "Try again", onClick: () => regenerateLastAnswer() },
          ...(t.failure ? [{ label: "ph:gear", title: "Open Settings, Models", onClick: () => openSettingsModal("models") }] : []),
          { label: "ph:trash", title: "Delete this message", onClick: () => removeChatBubble(bubble) },
        ])
      );
      chatScrollToEnd();
    }
  },
  // The finished turn kept in memory and saved to the conversation, replacing or appending.
  async persist(t) {
    const { opts, question, sentAttachments, sentImages, sentDocuments, sentFiles, sentBoards, followupOf, sentPersona, bubble, timeline, toolEvents, convRef, viewing, effectiveUseTools, answerRaw, thinkingRaw, turnSources, elapsedMs, resumeState, model } = t;
    // Per-message actions: one shared list with the reopened-conversation path,
    // see `assistantMessageActions` for why that matters (it places the row).
    assistantMessageActions({ bubble, text: answerRaw, question });
    bubble.answerSources = t.meta?.raw_results || [];
    if (opts.priorVersions?.length) {
      assistantMessageActions.pager(bubble, [...opts.priorVersions, { text: answerRaw, sources: bubble.answerSources, made_at: new Date().toISOString() }]);
    }

    // Regenerate replaces the last turn; a normal send appends a new one.
    chatHistoryToSend.heldOffer = t.groundingSupport?.offer?.offer_id || "";
    const turnRecord = { question, answer: answerRaw, objects: chatTurnObjects(turnSources), ...(t.turnFrame ? { frame: t.turnFrame } : {}) };
    if (opts.replaceLast && convRef.turns.length) convRef.turns[convRef.turns.length - 1] = turnRecord;
    else convRef.turns.push(turnRecord);
    // Persist the finished turn so the chat survives restarts. A checkpoint
    // still on its way is let land first, so this sees its id and replaces its
    // row rather than racing it to create a second conversation.
    if (t.checkpointRun) await t.checkpointRun;
    try {
      const payload = {
        question,
        answer: answerRaw || (t.askedQuestion ? `Asked: ${t.askedQuestion}` : ""),
        thinking: thinkingRaw || null,
        tools: toolEvents.length ? toolEvents : null,
        // The run in the order it happened, so reopening the chat shows the
        // same step-by-step process rather than a flattened summary.
        steps: timeline.serialise(),
        // What this turn cost, so the conversation can show a running total.
        // Prompt + output, because both were sent through the model.
        tokens: t.stats
          ? (t.stats.prompt_tokens || 0) + (t.stats.output_tokens || 0)
          : null,
        // The whole metadata line, not just its total. `tokens` above is a sum,
        // which is right for the conversation's running total and useless for
        // rebuilding "3.9k/8k window · 12 tok/s · llama3.2", so on reload the
        // line used to vanish and the answer looked like it came from nowhere.
        stats: t.stats || null,
        // §89.4: which mode actually answered this turn (Ask vs. Agent): a
        // conversation can span mode switches, so this has to be per-turn, not
        // read off the toggle's current state on reload.
        used_tools: effectiveUseTools,
        //: Which persona wrote this reply, so reopening the chat draws its face
        //: and not whichever persona the picker shows by then.
        persona: savedPersona(sentPersona),
        //: What the Resume and Edit-step buttons need to exist again after a
        //: reload (`appendRunResumeControls`). Sent only for a turn that has
        //: somewhere to resume *to*: an ordinary answer would otherwise carry
        //: five null fields on every row for the sake of a button it never
        //: draws.
        resume:
          resumeState.stoppedAtStep !== null ||
          resumeState.stopped ||
          resumeState.ranOutOfRounds
            ? resumeState
            : null,
        // How long the answer took, measured here because the client is the only
        // thing that saw the whole turn: the server reports per-round timings,
        // and an agent turn is several rounds plus the tool calls between them.
        elapsed_ms: elapsedMs,
        prior_versions: opts.priorVersions?.length ? opts.priorVersions : null,
        //: For a reload (W1).
        stopped: t.stopped,
        wrote: bubble.dataset.wrote,
        // The "N matching notes" disclosure's own data. Reported: "semantic
        // search results in chat messages keep disappearing" - true on every
        // reload, since none of this was ever saved. Only meaningful for a
        // grounded (non-conversational) turn that actually searched, so
        // omitted rather than sent empty when there's nothing to show.
        raw_results: t.meta?.raw_results?.length ? t.meta.raw_results : null,
        search_mode: t.meta?.search_mode || null,
        match_info: t.meta?.match_info && Object.keys(t.meta.match_info).length ? t.meta.match_info : null,
        connected_ids: t.meta?.connected_ids?.length ? t.meta.connected_ids : null,
        // The "Grounded in" chips' own data: same reasoning as raw_results
        // just above. Only meaningful alongside raw_results (renderAnswerGrounding
        // looks note content up in it), so there's nothing to persist without it.
        sentence_grounding: t.groundingSentences?.length ? t.groundingSentences : null,
        support: t.meta?.composed ? t.groundingSupport : null,
        acts: t.actCards?.length ? t.actCards : null,
        //: What the answer showed and named, so a reopened chat still binds "and the other one" (O4).
        frame: t.turnFrame,
        objects: turnRecord.objects,
        // Which uploads this turn actually used, asked for directly: without
        // this, a sent chat image had no record anywhere that anything still
        // used it, so the Library's "Clean orphaned media" tool (which can
        // only check notes, documents and whiteboard content for `/media/…`
        // references) would delete a real, sent attachment's file the moment
        // someone ran it. Persisting the ids here is what lets media_gc.py
        // recognise them as still in use.
        image_media_ids: sentImages.length ? sentImages : null,
        // Same reason as the ids above, one kind over: a document attached to a
        // message is what lets the bubble draw its chip again on reopen.
        document_ids: sentDocuments.length ? sentDocuments : null,
        file_ids: sentFiles.length ? sentFiles : null,
        // And the notes clipped with the paperclip, which until now were used to
        // build one prompt and then forgotten, the bubble showed no sign the
        // answer had been given a note to read.
        note_ids: sentAttachments.length ? sentAttachments : null,
        board_ids: sentBoards.length ? sentBoards : null,
        followup_of: followupOf,
        //: Who wrote it and why, so a reload draws the badge, note card and Why trail (INBOX 1693).
        by: t.meta && { composed: t.meta.composed, model },
        why: t.whyLines,
        //: The thumbnails' words, so a reopened chat keeps them (INBOX 502).
        picture_alts: t.meta?.picture_alts && Object.keys(t.meta.picture_alts).length ? t.meta.picture_alts : null,
        picture_sizes: t.meta?.picture_sizes && Object.keys(t.meta.picture_sizes).length ? t.meta.picture_sizes : null,
      };
      if (convRef.private) {
      } else if (convRef.id === null) {
        const created = await apiJson("/conversations", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        convRef.id = created.id;
        if (viewing()) {
          $("chat-title").textContent = created.title;
          renderChatUsage(created.tokens);
        }
        // A name typed before the first message was sent beats both the
        // question-derived title and the model's. See `renameCurrentConversation`.
        const namedByHand = applyPendingChatTitle(created.id, viewing());
        // Let the AI name the thread once there's something to name. Silent
        // best-effort: the question-derived title stays if the model can't.
        if (!namedByHand) {
          apiJson(`/conversations/${created.id}/retitle`, { method: "POST", silent: true })
            .then((named) => {
              if (chatConv.id === created.id) $("chat-title").textContent = named.title;
              loadConversationList();
            })
            .catch(() => {});
        }
      } else if (opts.replaceLast || t.checkpointed) {
        // `checkpointed` matters as much as `replaceLast` here: a long agent
        // turn has already written a row for this exchange (see checkpointTurn),
        // so appending would leave the conversation holding the same question
        // twice: once half-finished and once complete.
        const saved = await apiJson(`/conversations/${convRef.id}/turns/last`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
        if (viewing()) renderChatUsage(saved.tokens);
      } else {
        const saved = await apiJson(`/conversations/${convRef.id}/turns`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
        if (viewing()) renderChatUsage(saved.tokens);
      }
      bubble.turnIndex = convRef.turns.length - 1;
      for (const send of bubble.saving.splice(0)) send();
      loadConversationList();
    } catch {
      toast("Couldn't save this chat turn.", true);
    }
  },
  afterAnswer(t) {
    const { question, bubble, answerRaw } = t;
    // Last, and deliberately not awaited: the answer is already on screen and
    // saved, and this is a second model call. See offerFollowups. A composed
    // answer (no model running) brings its own next questions (INBOX 725). One
    // frame later (`CLIP_LIMITS.afterAnswer`), not in the task that painted the answer.
    CLIP_LIMITS.afterAnswer(() => {
      loadRecentQuestions();
      loadMostUsed();
      offerFollowups(bubble, question, answerRaw, t.meta?.composed ? t.composedNext : null);
      offerReminder(bubble, question);
    });
  },

  // A long turn is written as it goes, so a dropped connection loses minutes, not the turn.
  // Write what the turn has so far. Called at each agent round boundary, so a
  // ten-minute run that dies at minute nine leaves nine minutes of work in the
  // conversation instead of nothing.
  //
  // One in flight at a time: rounds can finish close together, and two
  // creates racing each other would make two conversations out of one thread.
  checkpointTurn(t) {
    if (t.checkpointInFlight || t.convRef.private) return t.checkpointRun;
    t.checkpointInFlight = true;
    t.checkpointRun = chatSendTurn.stage.writeCheckpoint(t);
    return t.checkpointRun;
  },
  async writeCheckpoint(t) {
    const { question, opts, timeline, toolEvents, sentImages, sentDocuments, sentFiles, sentMediaFiles, sentAttachments, sentBoards, followupOf, sentPersona, convRef, viewing } = t;
    try {
      const partial = {
        prior_versions: opts.priorVersions?.length ? opts.priorVersions : null,
        question,
        // A turn that ended by asking saves the question as its answer, so a
        // reloaded thread shows what was asked rather than an empty bubble
        // (INBOX 171: "all the ai responses dissappeared"; the question
        // lives in the bubble's output area, which is not a serialised step).
        answer: timeline.text() || (t.askedQuestion ? `Asked: ${t.askedQuestion}` : ""),
        thinking: timeline.thinkingText() || null,
        tools: toolEvents.length ? toolEvents : null,
        steps: timeline.serialise(),
        // No stats or elapsed yet, the turn is not over, and a half-turn's
        // numbers reported as final would be wrong rather than incomplete.
        image_media_ids: sentImages.length ? sentImages : null,
        document_ids: sentDocuments.length ? sentDocuments : null,
        file_ids: sentFiles.length ? sentFiles : null,
        media_file_ids: sentMediaFiles.length ? sentMediaFiles : null,
        note_ids: sentAttachments.length ? sentAttachments : null,
        board_ids: sentBoards.length ? sentBoards : null,
        followup_of: followupOf,
        persona: savedPersona(sentPersona),
      };
      if (convRef.id === null) {
        const created = await apiJson("/conversations", {
          method: "POST",
          body: JSON.stringify(partial),
          silent: true,
        });
        convRef.id = created.id;
        if (viewing()) $("chat-title").textContent = created.title;
        applyPendingChatTitle(created.id, viewing());
        loadConversationList();
      } else if (t.checkpointed || opts.replaceLast) {
        await apiJson(`/conversations/${convRef.id}/turns/last`, {
          method: "PUT",
          body: JSON.stringify(partial),
          silent: true,
        });
      } else {
        await apiJson(`/conversations/${convRef.id}/turns`, {
          method: "POST",
          body: JSON.stringify(partial),
          silent: true,
        });
      }
      t.checkpointed = true;
    } catch {
      // Deliberately silent. This is insurance running behind a live answer;
      // a toast here would interrupt the thing it exists to protect, and the
      // save at the end of the turn reports its own failure.
    } finally {
      t.checkpointInFlight = false;
    }
  },
  // What was typed, joined with the selection and cited page, for the model only.
  async ask(preset, opts, input) {
    const typed = chatTidyTyped((preset ?? input.value).trim());
    if (!typed) {
      //: Pressing Send on an empty box did nothing at all (dog3-1026 row 12).
      if (preset == null) {
        toast("Type a message first.");
        input.focus();
      }
      return { done: true };
    }
    if (preset == null && CHAT_UNDO_WORDS.test(typed)) {
      input.value = "";
      return { done: true, value: chatWriteRecord("chatHistoryTyped", /^undo/i.test(typed)) };
    }

    // Plan mode is applied here, on the way out, rather than by whatever control
    // was pressed: so Send, Enter and a suggestion chip all get planned when the
    // mode is on. `opts.plan` means this message IS a plan already (the plan
    // runner re-sends through here), so it must not be planned again.
    //
    // The user's own words go in the bubble; the planning instruction is appended
    // for the model only. `displayText` already exists for exactly this.
    const planned = opts.plan || opts.skipPlanMode ? null : applyPlanMode(typed);
    let question = planned || typed;
    if (planned && !opts.displayText) opts = { ...opts, displayText: typed };
    //: **The selection joins the question here, and only for the model.** It is
    //: appended after Plan mode's own rewrite for the same reason that rewrite
    //: exists at all: `displayText` is what the user said, and showing them a
    //: block of their own note quoted back at them under their question would
    //: read as the app putting words in their mouth. The chip above the box is
    //: what tells them it is going.
    //:
    //: Re-validated at this moment rather than reused from when it was attached
    //:, see `revalidateSelection` for what changes in between and why sending
    //: stale offsets is the worst of the three outcomes.
    const sentSelection = attachedSelection ? revalidateSelection(attachedSelection) : null;
    if (sentSelection) {
      if (!opts.displayText) opts = { ...opts, displayText: typed };
      question = `${question}\n\n${selectionContextBlock(sentSelection)}`;
    }
    //: A cited web page joins the same way and for the same reason: the model
    //: reads it, the bubble shows only what the user typed, and the chip above
    //: the box is what said it was going.
    if (attachedWebPage) {
      if (!opts.displayText) opts = { ...opts, displayText: typed };
      question = `${question}\n\n${webPageContextBlock(attachedWebPage)}`;
    } else if (chatWeb.lastUrl && (await ensureModule("webClip"))) {
      const page = await webFollowUp(typed, chatWeb.lastUrl);
      if (page) {
        if (!opts.displayText) opts = { ...opts, displayText: typed };
        question = `${question}\n\n${webPageContextBlock(page)}`;
      }
    }
    // Over the server's limit: say so, keep the draft (audit 1028 E8).
    if (question.length > 2e4) return { done: true, value: lazyScript("/js/chat-edit.js").then(() => chatTooLong(typed, !preset)) };
    lastChatQuestion = question;
    if (!opts.replaceLast) regenerateLastAnswer.retries = 0; // a new question is a first ask

    // Consumed once: this send, button click or free-typed reply alike, is
    // the answer to whatever question was pending, and the next one after it
    // is an ordinary message again.
    const answeringAgent = opts.answeringAgent ?? chatAwaitingAgentAnswer;
    chatAwaitingAgentAnswer = false;
    // Whatever is sent while a question card waits is its answer (INBOX 171):
    // the card folds into its chip and cannot send a second one.
    settlePendingAgentQuestion(opts.displayText ?? typed);
    return { typed, question, opts, answeringAgent };
  },

  // The send is committed: staged pictures uploaded, attachments snapshotted, the composer cleared.
  async commit(opts, question, input, status) {
    // **Staged images become real uploads here**, at the moment the message is
    // actually committed: see `attachImageFiles` for why nothing was uploaded
    // when they were attached.
    //
    // Before the snapshot below, because that snapshot reads `img.id` and a
    // staged image has none until this runs. A failure stops the send and says
    // so: a message arriving without the picture it was written about is worse
    // than one that refuses and explains.
    if (!opts.imageMediaIds) {
      try {
        await commitStagedImages();
      } catch (error) {
        toast(error.message || "Couldn't upload the attached image.", true);
        return { done: true };
      }
    }

    // Snapshot the attachments for this message. A regenerate re-uses the same
    // ones; a fresh send clears them, so they don't silently ride along on
    // every later question.
    const sentAttachments = opts.noteIds || attachedNoteIds.slice();
    const sentImages = opts.imageMediaIds || attachedImages.map((img) => img.id);
    const sentDocuments = opts.documentIds || attachedDocuments.map((d) => d.id);
    const sentFiles = opts.fileIds || attachedFiles.filter((f) => typeof f.id === "number").map((f) => f.id);
    const sentMediaFiles = opts.mediaFileIds || attachedFiles.filter((f) => typeof f.id === "string").map((f) => Number(f.id.slice(1)));
    const sentBoards = opts.boardIds || attachedBoards.map((b) => b.id);
    // What the bubble will draw. Built here, while the composer still knows the
    // names and urls: after the clear below there is nothing left to build it
    // from, and a round trip to re-fetch what we already had would show the
    // message without its pictures for as long as that took.
    const sentAttachmentCards = opts.attachmentCards || [
      ...attachedImages.map((img) => ({
        kind: "image",
        id: img.id,
        url: img.url,
        name: img.name || "Attached image",
        // A just-uploaded image has no caption yet, captioning runs in the
        // background once the message commits it. Reopening the chat picks the
        // caption up from `GET /conversations/{id}`, which is where it lands.
        caption: "",
        text: "",
      })),
      ...attachedDocuments.map((d) => ({ kind: d.kind || "document", id: d.id, name: d.name })),
      // Library files: the same card list as the other kinds, so the bubble
      // shows every reference the question was given rather than three of four.
      ...attachedFiles.map((f) => ({ kind: "file", id: f.id, name: f.name })),
      // A mind map, same card list again, the bubble has to show every
      // reference the question was given, and a map is the one whose absence
      // would be least obvious (its outline is invisible in the transcript).
      ...attachedBoards.map((b) => ({ kind: "map", id: b.id, name: b.name })),
      // The paperclip's own attachments. Same card list as the other two kinds
      // so the bubble shows every reference this question was given, not two of
      // the three.
      ...attachedNotes().map((entry) => ({
        kind: "note",
        id: entry.id,
        name: noteLabel(entry, 60),
      })),
    ];
    if (!opts.replaceLast) {
      // Remembered so a regenerate re-runs with the same references, by then
      // the picker has been cleared.
      lastChatAttachments = sentAttachments;
      lastChatImageAttachments = attachedImages.slice();
      lastChatDocumentAttachments = attachedDocuments.slice();
      lastChatFileAttachments = attachedFiles.slice();
      lastChatBoardAttachments = attachedBoards.slice();
      // The staged bytes are on the server now, so the local Blob references
      // are dead weight: an object URL lives as long as the document unless it
      // is revoked, and a chat session sending several images would hold every
      // one of them in memory for the life of the tab. The upload's real url is
      // what the sent bubble draws from, so nothing on screen depends on these.
      for (const image of attachedImages) {
        if (image.objectUrl) URL.revokeObjectURL(image.objectUrl);
        image.objectUrl = null;
      }
      attachedNoteIds = [];
      attachedImages = [];
      attachedDocuments = [];
      attachedFiles = [];
      attachedBoards = [];
      //: Cleared with the rest, and for the same stated reason: a selection that
      //: rode along on every later question would be the app answering about a
      //: paragraph the user stopped talking about three messages ago.
      attachedSelection = null;
      attachedWebPage = null;
      renderAttachments();
      renderImageAttachments();
      renderDocumentAttachments();
      renderFileAttachments();
      renderBoardAttachments();
      renderSelectionAttachment();
      renderWebPageAttachment();
      closeNotePicker();
    }

    //: Same loan as in `openConversation`: `chatEmptyState` can have moved this
    //: element inside `#chat-messages`, and a caller that cleared the pane first
    //: would find it gone.
    $("chat-suggest")?.classList.add("hidden");
    //: A queued send (`keepBox`) leaves the box to what is being typed now.
    if (!opts.keepBox) {
      input.value = "";
      autoGrow(input); // a cleared box must not keep the height of what was in it
      // The draft is gone, so the suggestions about it are too, including the
      // ones that were dismissed, which belonged to that draft and not to the
      // next one.
      resetChatNudge();
    }
    //: The box stays open while the answer streams, so the next message can
    //: be written and queued (INBOX 1321); Escape still stops the answer.
    hide("chat-send");
    show("chat-stop");
    status.classList.remove("error");
    status.textContent = "Searching your notes…";
    startChatTimer();
    return { sentAttachments, sentImages, sentDocuments, sentFiles, sentMediaFiles, sentBoards, sentAttachmentCards };
  },
};

// --- the agent's run, as an ordered timeline --------------------------------------
// A turn used to render into three fixed slots, thinking, then every tool chip,
// then the answer: regardless of when those things actually happened. For a
// multi-step agent run that destroys the one thing worth seeing: the order. A
// model that thought, searched, thought again and then answered looked
// identical to one that answered immediately.
//
// So steps are appended as the events arrive. Consecutive deltas of the same
// kind extend the current step; a different kind starts a new one, which is
// what produces the thinking → tool → tool → answer chain the user follows.
//: `options.afterAnswerPaint` runs after every live paint of a prose step: a
//: paint rebuilds the step from raw markdown, so the citation numbers placed
//: while the answer streams (`grounding_live`, INBOX 320) have to be written
//: again each time, as the Ask tab's own renderer does.
function agentTimeline(holder, options = {}) {
  let current = null; // the step still being written into
  const answerSteps = []; // every prose step, in order
  const thinkingSteps = [];
  const record = []; // a serialisable copy, for persistence

  //: **The step group** ("Finished 5 steps", asked for as Perplexity's):
  //: tool calls behind one line, open while running, closed once the answer
  //: starts. A new group after each answer, so order stays true.
  let group = null;

  const groupSummary = (entry) => {
    const n = entry.count;
    const word = n === 1 ? "step" : "steps";
    setLabel(
      entry.summary,
      entry.done ? `ph:check-circle Finished ${n} ${word}` : `ph:spin Working: ${n} ${word}`,
    );
  };

  const ensureGroup = () => {
    if (group) return group;
    const el = document.createElement("details");
    el.className = "agent-step agent-step-group";
    el.open = true;
    const summary = document.createElement("summary");
    summary.className = "agent-step-group-summary";
    const body = document.createElement("div");
    body.className = "agent-step-group-body";
    el.append(summary, body);
    holder.appendChild(el);
    group = { el, summary, body, count: 0, done: false };
    groupSummary(group);
    return group;
  };

  //: Closed and relabelled, not removed. The steps stay reachable, that is
  //: the difference between a summary and a spinner that ate the evidence.
  const closeGroup = () => {
    if (!group) return;
    group.done = true;
    groupSummary(group);
    group.el.open = false;
    group = null;
  };

  const foldEarlierThinking = () => {
    // Reasoning that has produced output is finished, collapse it so the
    // answer isn't buried under it, but leave it there to reopen.
    for (const step of thinkingSteps) step.el.open = false;
  };

  const startThinking = () => {
    const el = thinkingFold();
    const body = el.querySelector(".thinking");
    holder.appendChild(el);
    current = { kind: "thinking", el, body, raw: "" };
    thinkingSteps.push(current);
    return current;
  };

  const startAnswer = () => {
    //: **Only the step being written wears the caret.** Reported with a
    //: screenshot of an agent run: "the blinking cursor bubbles at the end of
    //: the text stayed at the end of each paragraph and didnt disappear" --
    //: every finished answer step in the run still carried one, so a five-step
    //: run showed five carets and only the last of them meant anything.
    //:
    //: `finalise()` cleared them, but only once the whole run ended. A step is
    //: finished the moment the next one starts, which is here.
    for (const step of answerSteps) step.el.classList.remove("is-streaming", "is-generating");
    foldEarlierThinking();
    //: The steps that led here fold up as the prose begins, which is exactly
    //: what Perplexity does and why its answers read as answers rather than
    //: as logs. Anything the model does *after* this opens a fresh group.
    closeGroup();
    const el = document.createElement("div");
    // **`is-streaming` is the only thing on screen that says the answer is
    // still arriving.** Reported directly: "there are no animations for chat
    // generation." The typing dots that run before the first token are
    // removed the moment one arrives (`clearPending`), and from then until
    // the turn ends the text simply grows, no caret, no cursor, nothing.
    // Every chat interface has this affordance because without it a slow
    // local model producing a token a second is indistinguishable from a
    // finished short answer.
    //
    // A class plus a CSS `::after`, not an appended element: the answer body
    // is re-rendered from scratch on every frame by `liveMarkdownRenderer`,
    // so a real node would be destroyed and recreated ~30 times a second (and
    // would land inside whatever block the markdown happened to end with).
    // A pseudo-element is untouched by that and is removed by `finalise`.
    //: **No `is-generating` on the answer itself.** Reported: "the text is
    //: right up against the overly animated borders as well", with a
    //: screenshot of an answer inside a pulsing ring *inside* a bubble
    //: already wearing one. Two rings around one sentence is one too many,
    //: and the inner one is the redundant one: the bubble's rail says the
    //: turn is working and the caret says this answer is still arriving.
    //: `is-streaming` stays, because that is the caret.
    el.className = "agent-step step-answer bubble-answer is-streaming";
    holder.appendChild(el);
    current = {
      kind: "answer",
      el,
      body: el,
      raw: "",
      render: liveMarkdownRenderer(el, options.afterAnswerPaint || null),
    };
    answerSteps.push(current);
    return current;
  };

  // The plan a skill declared, drawn before anything runs. The timeline has
  // always shown what happened; a skill is the first thing that knows what is
  // *meant* to happen, so it says so up front (roadmap §18).
  const plans = [];
  const startPlan = (plan) => {
    const el = document.createElement("details");
    el.className = "agent-step step-plan";
    el.open = true;
    const summary = document.createElement("summary");
    // A saved skill and a plan the model drew for this one request run through
    // the same code, so the card has to say which it is, "Skill Weekly review" is
    // a job the user set up, "Plan fix my categories" is one the model worked out
    // just now, and confusing the two makes the skill list look like it has
    // entries nobody added.
    //: A turn's own card (`kind: "turn"`, agent.py `_TurnCard`) is a third shape.
    const icon = { plan: "ph:compass", turn: "ph:list-checks" }[plan.kind] || "ph:lightning";
    setLabel(summary, `${icon} ${plan.skill}`);
    el.appendChild(summary);
    const items = [];
    if (plan.steps?.length || plan.kind === "turn") {
      const list = document.createElement("ol");
      list.className = "plan-steps";
      plan.steps.forEach((step, index) => {
        const item = document.createElement("li");
        item.textContent = step;
        if (plan.writes) item.appendChild(planStepWrites(plan.writes[index]));
        list.appendChild(item);
        items.push(item);
      });
      el.appendChild(list);
    }
    if (plan.tools?.length) {
      const line = document.createElement("div");
      line.className = "plan-tools";
      line.textContent = `Tools for this run: ${plan.tools.join(", ")}`;
      el.appendChild(line);
    }
    holder.appendChild(el);
    const entry = { el, items, plan: { ...plan, states: plan.states || {} } };
    plans.push(entry);
    // Replaying a finished run: paint the states it ended with.
    for (const [index, state] of Object.entries(entry.plan.states)) {
      markStep(entry, Number(index), state.state, state.reason, state);
    }
    current = null;
    return el;
  };

  // A step's state, shown on the plan itself. The timeline records what
  // happened; this is the only place that says how far through it got.
  const markStep = (entry, index, state, reason, event = {}) => {
    let item = entry.items[index];
    //: A turn's card grows a row per round; a skill's steps are fixed.
    if (!item && entry.plan.kind === "turn" && event.text) {
      item = document.createElement("li");
      entry.el.querySelector(".plan-steps")?.appendChild(item);
      entry.items[index] = item;
      entry.plan.steps = [...(entry.plan.steps || []), event.text];
    }
    if (!item) return;
    //: `attempt`/`of` ride along with the state so a replayed run shows the
    //: same "attempt 2 of 3" a live one did. They are only present on a
    //: `retrying` event, and an older saved run has neither, which
    //: `stepStateWords` renders as attempt 1 of 1 rather than as a crash.
    entry.plan.states[index] = {
      state,
      reason,
      attempt: event.attempt,
      of: event.of,
      //: The rewritten step travels with the state so a replayed run shows the
      //: instruction that actually ran, not the one that failed.
      text: state === "replanned" ? event.text : entry.plan.states[index]?.text,
    };
    item.className = `plan-step plan-step-${state}`;
    item.dataset.state = state;
    const note = item.querySelector(".plan-step-reason");
    if (note) note.remove();
    //: **A re-planned step is a different step, so the checklist says so.**
    //: The runner rewrites a step it could not finish and runs it again at
    //: the same index; leaving the old wording on screen would make the next
    //: `running` look like a repeat of a step that had already failed, with
    //: no sign that anything changed. `textContent`, never markup: this is
    //: model-written text.
    if ((state === "replanned" || entry.plan.kind === "turn") && event.text) {
      item.textContent = event.text;
      entry.plan.steps = entry.plan.steps.map((old, i) => (i === index ? event.text : old));
    }
    //: **`retrying` says why, in the same words the activity panel uses.**
    //: Phase A's runner re-prompts a step whose contract was not met and emits
    //: this state for each attempt; without the sentence, a step being
    //: re-prompted for the third time is indistinguishable on screen from one
    //: quietly running, which is the "it ran no tools and moved on" report all
    //: over again one layer up. `stalled` gets it for the same reason: it is
    //: the state that *ends* a run, and "why did this stall?" should not need
    //: a second click.
    //: **A finished step with a caveat says it on the row.** `done` carries a
    //: reason in two cases and neither was drawn: a step that ran out of
    //: pages with notes left unread, and one whose change turned out not to
    //: be needed (`no_change`). Both are the same class of thing the states
    //: below already explain: a green tick that means less than it looks
    //: like. The owner's report is the reason this matters, a step that says
    //: "I unlinked the ones that did not hold up" over an untouched notebook
    //: reads exactly like one that did the work.
    if (
      (state === "failed" ||
        state === "stalled" ||
        state === "retrying" ||
        state === "replanned" ||
        state === "done" ||
        state === "paging") &&
      (reason || state === "retrying" || state === "replanned" || state === "paging")
    ) {
      const why = document.createElement("span");
      why.className = "plan-step-reason";
      why.textContent =
        state === "retrying" || state === "replanned" || state === "paging"
          ? `, ${stepStateWords(state, { ...event, reason })}`
          : `, ${reason}`;
      item.appendChild(why);
    }
    //: Each step's diff after (row 3): what it wrote, each with its Undo.
    if (state === "done" && event.changes?.length) {
      const box = document.createElement("div");
      box.className = "plan-step-changes";
      for (const change of event.changes) box.appendChild(changeRow(change));
      item.appendChild(box);
    }
  };

  return {
    holder,
    //: What a step currently says, for Phase D's "edit a step's text and
    //: re-run just that step": the re-planned wording when the runner rewrote
    //: it, the original otherwise, so the box opens on the instruction that
    //: actually ran rather than on the one in the catalogue.
    stepText(index) {
      const entry = plans.at(-1);
      if (!entry) return "";
      return entry.plan.states?.[index]?.text || entry.plan.steps?.[index] || "";
    },
    plan(event) {
      startPlan(event);
    },
    step(event) {
      const entry = plans.at(-1);
      if (entry) markStep(entry, event.index, event.state, event.reason, event);
      // Each step's prose is its own block. Without this, step 2's first
      // sentence lands on the end of step 1's paragraph ("…with no tags.Read
      // them.") because nothing between them closed the step.
      current = null;
    },
    failRunningStep(reason) {
      const entry = plans.at(-1);
      if (!entry) return;
      for (const [index, state] of Object.entries(entry.plan.states)) {
        if (state.state === "running") markStep(entry, Number(index), "failed", reason);
      }
    },
    // What the run actually changed, with the call that puts each one back.
    // Prose claiming something happened is exactly what this replaces.
    result(event, options = {}) {
      const changes = event.changes || [];
      //: **The verification is shown even when nothing changed**, which is
      //: most of the time: half the shipped skills are reports, and "this run
      //: changed nothing" is exactly the claim their verify block checks
      //: (Brief 13). A read-only run used to render nothing at all here, so
      //: the only evidence it had done its job was its own prose.
      const check = event.verification || null;
      if (!changes.length && !check) return;
      const box = document.createElement("div");
      box.className = "skill-result";
      box.dataset.changes = JSON.stringify(changes);
      if (check) box.dataset.verification = JSON.stringify(check);
      const span = event.undo_span || null;
      if (span) box.dataset.undoSpan = JSON.stringify(span);
      if (changes.length) {
        const title = document.createElement("div");
        title.className = "skill-result-title";
        title.textContent = `What changed (${changes.length})`;
        //: **The run's own Undo** (AGENT_SKILLS_REFORM): everything the run
        //: wrote, as one plan to confirm (`undoSkillRun`, note-history.js).
        //: One change has its row's own Undo, so it is offered from two.
        if (span && changes.length > 1) {
          //: The run's Undo puts everything back at once, so the per-write
          //: entries on the app's stack and the rows' own Undo buttons come
          //: off too: left, a later Ctrl+Z (or a row's Undo) would run an
          //: inverse that is already applied (Brief 101b).
          const settleRun = () => {
            for (const change of changes) {
              const action = change.undo ? agentUndoActions.get(JSON.stringify(change.undo)) : null;
              if (action && undoStack.includes(action)) settleUndoFromToast(action);
            }
            for (const row of box.querySelectorAll(".skill-change")) {
              row.classList.add("skill-change-undone");
              row.querySelectorAll("[data-change-undo]").forEach((button) => button.remove());
            }
          };
          const all = smallButton("ph:arrow-counter-clockwise Undo the run", "Put back every note this run changed", () => undoSkillRun(span, all, settleRun));
          title.append(" ", all);
        }
        box.appendChild(title);
        for (const change of changes) box.appendChild(changeRow(change, options));
      }
      if (check) box.appendChild(verificationRow(check));
      //: **What the run spent against its budget** (L55): the result event's `budget`, one muted line under the
      //: changes: "Used 2 of 12 steps, 3,100 of 20,000 tokens, 8 of 90 s." A cap of 0 is no cap and is left out.
      function budgetRow(budget) {
        const caps = budget?.caps || {};
        const part = (used, cap, unit) => (cap > 0 ? `${used.toLocaleString("en")} of ${cap.toLocaleString("en")} ${unit}` : null);
        const parts = [part(budget?.steps ?? 0, caps.steps, "steps"), part(budget?.tokens ?? 0, caps.tokens, "tokens"), part(budget?.seconds ?? 0, caps.seconds, "seconds")].filter(Boolean);
        if (!parts.length) return null;
        const row = document.createElement("div");
        row.className = "skill-budget muted";
        row.textContent = `Used ${parts.join(", ")}.`;
        return row;
      }
      const spent = budgetRow(event.budget);
      if (spent) box.appendChild(spent);
      holder.appendChild(box);
      current = null;
    },
    thinking(delta) {
      const step = current?.kind === "thinking" ? current : startThinking();
      step.raw += delta;
      // The pane has its own max-height and scrollbar; `thinkingPaint` keeps
      // the newest line in view after each paint.
      thinkingPaint(step.el, step.raw);
    },
    answer(delta) {
      const step = current?.kind === "answer" ? current : startAnswer();
      step.raw += delta;
      step.render(step.raw);
    },
    // A tool call is a row inside the current step group, see `ensureGroup`.
    tool(node) {
      foldEarlierThinking();
      const entry = ensureGroup();
      entry.body.appendChild(node);
      entry.count += 1;
      groupSummary(entry);
      current = null; // whatever comes next begins a fresh step
    },
    //: The turn is over: whatever group is still open stops saying "Working".
    //: Called from the stream's `finally`, so it runs on an error and an
    //: abort too: a group left mid-sentence is how a stopped turn ends up
    //: looking like a running one forever.
    finish() {
      closeGroup();
      //: Any trailing progress line still in this holder goes with it. The
      //: turn's own `pending` node is removed by the stream, but a skill run
      //: replayed into a rebuilt bubble can leave one behind, and a "Writing
      //: the answer…" under a finished answer is the exact thing reported.
      for (const stale of holder.querySelectorAll(".step-pending")) stale.remove();
    },
    // Replay a saved run (reopening a conversation).
    replay(steps) {
      for (const step of steps || []) {
        //: `serialise` spreads the plan over `kind`, so a skill's card saves
        //: as "skill" and a turn's as "turn"; both were dropped on reopen.
        if (["plan", "skill", "turn"].includes(step.kind) && Array.isArray(step.steps)) {
          startPlan(step);
          if (plans.at(-1)) plans.at(-1).el.open = false;
        } else if (step.kind === "result") {
          this.result(step);
        } else if (step.kind === "thinking" && step.text) {
          this.thinking(step.text);
          if (current) current.el.open = false;
          current = null;
        } else if (step.kind === "answer" && step.text) {
          const node = startAnswer();
          node.raw = step.text;
          renderMarkdown(node.body, step.text);
          //: A replayed answer has already finished. `startAnswer` builds the
          //: node in its live, mid-stream state, so without this a reloaded
          //: conversation blinks a caret at the end of every answer in it, 
          //: and, now that the two travel together, pulses the generating ring
          //: around all of them forever.
          node.el.classList.remove("is-streaming", "is-generating");
          current = null;
        } else if (step.kind === "tool") {
          //: `step` is passed through, so a replayed tool row keeps the
          //: arguments/result disclosure the live one had. Without it a
          //: reloaded conversation silently lost what each call actually did
          //:, the same turn showed less of itself the second time you looked
          //: at it, which is the shape behind "tools render fine in the chat
          //: initially but then I come back to them after reloading".
          this.tool(toolChip(step.label, step.ok !== false, step));
        }
      }
    },
    noteStep(entry) {
      record.push(entry);
    },
    // Everything the model actually said, for copying, reading aloud and the
    // history sent with the next question.
    text() {
      return answerSteps.map((s) => s.raw).join("\n\n").trim();
    },
    thinkingText() {
      return thinkingSteps.map((s) => s.raw).join("\n\n").trim();
    },
    // Re-render each prose step properly once streaming has finished.
    finalise() {
      //: The live renderer's armed paint is cancelled first: see its own
      //: `stop`. Anything the caller adds to this prose afterwards (the
      //: citation markers) would otherwise be wiped by a timer that was
      //: scheduled before the turn ended.
      for (const step of answerSteps) step.render?.stop?.();
      for (const step of answerSteps) renderMarkdown(step.body, step.raw);
      // The caret goes out with the stream that justified it. Called from
      // every exit path this timeline has, a finished turn, an error, and
      // Stop: because a caret left blinking on an answer that stopped
      // arriving is a worse lie than never having shown one.
      for (const step of answerSteps) step.el.classList.remove("is-streaming", "is-generating");
      foldEarlierThinking();
    },
    // The box to put a message into when the model produced nothing at all.
    ensureAnswerBox() {
      const step = answerSteps.at(-1) || startAnswer();
      //: **Whatever goes in here is already finished.**
      //:
      //: Reported: *"the blinker animation still shows at the end of finished
      //: responses"*, with a screenshot of the caret blinking after "The
      //: model finished without writing anything." That message is written by
      //: the app, after `finalise()` has already run, and `startAnswer` builds
      //: its node in the live, mid-stream state: a caret on a sentence that
      //: was never streaming and no later pass to take it down.
      step.el.classList.remove("is-streaming", "is-generating");
      return step.body;
    },
    // Editing an answer replaces the model's prose with the user's own, so the
    // separate prose steps collapse into the one block they typed. The
    // reasoning and tool steps around them are left alone, those record what
    // actually happened and aren't the user's to rewrite.
    replaceAnswer(markdown) {
      // Same race as `finalise`: an armed paint would put the model's prose
      // back over the text the user just typed.
      for (const step of answerSteps) step.render?.stop?.();
      for (const step of answerSteps.slice(1)) step.el.remove();
      answerSteps.length = Math.min(answerSteps.length, 1);
      const step = answerSteps[0] || startAnswer();
      step.raw = markdown;
      renderMarkdown(step.body, markdown);
      current = null;
      return step.body;
    },
    // The element answer-editing hides while its textarea is open.
    answerElement() {
      return (answerSteps.at(-1) || startAnswer()).el;
    },
    hasAnswer() {
      return answerSteps.some((s) => s.raw.trim());
    },
    // The timeline in the order it happened, for saving with the turn.
    serialise() {
      const out = [];
      //: **Groups are walked into, not over.** Tool rows used to be direct
      //: children of the holder; they are inside a `<details>` now, and a
      //: loop over `holder.children` alone would have silently stopped
      //: saving every tool call, the exact shape of the `.tool-chip-wrap`
      //: regression this function's own comment below already records.
      const walk = (parent) => {
      for (const node of parent.children) {
        if (node.classList.contains("agent-step-group")) {
          walk(node.querySelector(".agent-step-group-body") || node);
          continue;
        }
        if (node.classList.contains("step-plan")) {
          const entry = plans.find((p) => p.el === node);
          // The states go with it, so reopening a chat shows how far the run
          // got rather than an untouched plan.
          if (entry) out.push({ kind: "plan", ...entry.plan });
        } else if (node.classList.contains("skill-result")) {
          out.push({
            kind: "result",
            changes: JSON.parse(node.dataset.changes || "[]"),
            verification: JSON.parse(node.dataset.verification || "null"),
            undo_span: JSON.parse(node.dataset.undoSpan || "null"),
          });
        } else if (node.classList.contains("thinking-fold")) {
          const step = thinkingSteps.find((s) => s.el === node);
          if (step?.raw) out.push({ kind: "thinking", text: step.raw });
        } else if (node.classList.contains("step-answer")) {
          const step = answerSteps.find((s) => s.el === node);
          if (step?.raw) out.push({ kind: "answer", text: step.raw });
        } else if (node.toolStep) {
          //: **Anything that carried its own saved form is saved**, whatever
          //: it is drawn as. The class checks below only know the shapes that
          //: existed when they were written, and a card added later, a
          //: confirmation, a proposal, a question, was silently dropped from
          //: the saved turn, which is one half of "a lot of the steps and
          //: agent process disappears when I come back to it".
          out.push(node.toolStep);
        } else if (node.classList.contains("tool-chip") || node.classList.contains("tool-chip-wrap")) {
          //: `.tool-chip-wrap` has to be matched as well as `.tool-chip`:
          //: `classList.contains` is an exact token match, so once a row that
          //: touched something got wrapped with its chips, this branch stopped
          //: seeing it at all and the call vanished from the reopened chat.
          out.push(
            node.toolStep || {
              kind: "tool",
              label: node.textContent,
              ok: !node.classList.contains("tool-chip-error"),
            },
          );
        }
      }
      };
      walk(holder);
      return out;
    },
  };
}

function renderAgentQuestion(holder, event) {
  const card = document.createElement("div");
  card.className = "tool-confirm agent-ask";
  const text = document.createElement("p");
  setLabel(text, `ph:question ${event.question}`);
  const row = document.createElement("div");
  row.className = "row agent-ask-options";

  let chosen = null;
  let settled = false;
  const buttons = [];
  const other = document.createElement("input");
  other.type = "text";
  other.className = "agent-ask-other-input";
  other.placeholder = "Or write your own answer…";
  other.setAttribute("aria-label", "Your own answer");
  const send = smallButton("ph:paper-plane-right Send answer", "Send this answer", () => submit(), false);
  send.disabled = true;
  const sync = () => {
    send.disabled = !(chosen || other.value.trim());
    for (const button of buttons) {
      button.setAttribute("aria-pressed", button.dataset.option === chosen ? "true" : "false");
    }
  };
  for (const option of event.options || []) {
    const button = smallButton(option, `Choose: ${option}`, () => {
      // A second click on the chosen one clears it, as a toggle does.
      chosen = chosen === option ? null : option;
      if (chosen) other.value = "";
      sync();
    });
    button.dataset.option = option;
    button.setAttribute("aria-pressed", "false");
    buttons.push(button);
    row.appendChild(button);
  }
  other.addEventListener("input", () => {
    if (other.value.trim()) chosen = null;
    sync();
  });
  other.addEventListener("keydown", (keyEvent) => {
    if (keyEvent.key === "Enter") {
      keyEvent.preventDefault();
      submit();
    }
  });
  const settle = (answer) => {
    if (settled) return;
    settled = true;
    if (pendingAgentQuestion?.card === card) pendingAgentQuestion = null;
    card.replaceWith(toolChip(`ph:question ${event.question} → ${answer}`));
  };
  const submit = () => {
    const answer = other.value.trim() || chosen;
    if (!answer || settled) return;
    settle(answer);
    sendChatMessage(answer);
  };
  const otherRow = document.createElement("div");
  otherRow.className = "row agent-ask-other";
  otherRow.append(other, send);
  const note = document.createElement("p");
  note.className = "muted";
  note.textContent = "Pick one or write your own, then send. Typing in the chat bar answers it too.";
  card.append(text, row, otherRow, note);
  holder.appendChild(card);
  pendingAgentQuestion = { card, settle };
  chatScrollToEnd();
}

// The model would like to remember something about you (§39B).
//
// This card is the whole point of the change behind it. `save_user_preference`
// used to write a standing instruction straight into every future system
// prompt: no confirmation, no notice, and the only trace was a list in
// Settings nobody had a reason to open. A model that over-read one sentence
// ("use British English for this one, actually") gave itself a permanent rule
// its user never agreed to, and would then keep obeying it for weeks.
//
// So the tool now *proposes*: the row is written inactive and flagged, it is
// excluded from the prompt, and this card is where it becomes real. Declining
// keeps the row (switched off) on purpose, the tool's duplicate check reads
// every preference, so a kept "no" is what stops the model suggesting the same
// thing again an hour later.
function renderMemoryProposal(holder, proposal) {
  const card = document.createElement("div");
  card.className = "tool-confirm memory-proposal";

  const text = document.createElement("p");
  setLabel(text, "ph:brain Remember this for next time?");

  const quote = document.createElement("blockquote");
  quote.className = "memory-proposal-text";
  quote.textContent = proposal.content;

  const note = document.createElement("p");
  note.className = "muted";
  note.textContent =
    "Saved preferences are added to Atlas's instructions in every later " +
    "conversation. Nothing is in force until you say yes.";

  const row = document.createElement("div");
  row.className = "row";

  let answered = false;
  const answer = async (accept) => {
    if (answered) return;
    answered = true;
    try {
      await apiJson(`/memory/${proposal.id}/answer`, {
        method: "POST",
        body: JSON.stringify({ accept }),
      });
      pushRequestUndo(accept ? "Remembered a preference" : "Declined a preference", `/memory/${proposal.id}`, "PATCH", { proposed: true, active: false }, { proposed: false, active: accept }, () => renderMemorySettings());
    } catch (error) {
      answered = false;
      toast(error.message, true);
      return;
    }
    card.replaceWith(
      toolChip(
        accept
          ? `ph:check-circle Remembered: “${proposal.content}”`
          : "ph:x Not remembered."
      )
    );
    // The Settings list is the other view of the same row; if it happens to
    // be open behind the chat, leaving it stale shows a pending question the
    // user has already answered.
    renderMemorySettings().catch(() => {});
  };

  row.appendChild(
    smallButton("Remember it", "Add this to Atlas's standing instructions", () => answer(true), false)
  );
  row.appendChild(smallButton("No thanks", "Don't save this preference", () => answer(false)));

  card.append(text, quote, note, row);
  holder.appendChild(card);
  chatScrollToEnd();
}

//: **Re-validated at send, not trusted from when it was attached.** This is
//: the part of odysseus's `getSelectionContext()` worth porting exactly
//: (`static/js/document.js`, AGPL: this project is AGPL-3.0, see
//: ANALYSIS.md): between selecting a passage and pressing send, the user can
//: type above it, undo, or edit the note entirely, and stored offsets then
//: point at *different words*. Sending those would hand the model text from a
//: region the user is no longer looking at, attributed to a line number that
//: is now someone else's line: wrong in the most confusing possible way.
//:
//: Three outcomes, and each is said plainly to the model rather than papered
//: over: the offsets still hold; the passage moved (found elsewhere, so the
//: line number is recomputed); or the passage is gone from the surface, in
//: which case the text is still sent, the user asked about it, but with no
//: position claimed at all.
function revalidateSelection(context) {
  //: A reading is a copy of what was read, not a place in a surface.
  if (context.kind === "reading") return { ...context, position: "exact" };
  //: **Through `docSurfaceById`, never `getElementById` alone.** A document
  //: whose CodeMirror engine has mounted keeps `#doc-content` in the markup as
  //: the form's empty value carrier: it is still an `HTMLTextAreaElement` and
  //: its `.value` is still `""`, so reading it directly passed the type check
  //: and then told the model every document passage was `gone` while the
  //: passage was on screen (measured on the branch head by
  //: `scratchpad/ui-sweeps/docsel.js`: "gone" for an untouched selection).
  //: `docSurfaceById` resolves `doc-content` to whichever surface is editing,
  //: and a note box that has mounted the engine the same way.
  //:
  //: Guarded by `typeof`, because documents.js is in the Library's lazy bundle
  //: (`LAZY_MODULES`) and a selection taken from the capture box can be sent
  //: before that bundle has ever loaded; the textarea is the right answer
  //: there anyway.
  const el = document.getElementById(context.surfaceId);
  const surface =
    typeof docSurfaceById === "function"
      ? docSurfaceById(context.surfaceId)
      //: `{ text }` rather than the element itself, so the one line below that
      //: reads the words reads the same property in both branches.
      : el instanceof HTMLTextAreaElement
        ? { text: el.value }
        : null;
  if (!surface || typeof surface.text !== "string") {
    //: The note was closed or the document navigated away from. Nothing to
    //: check against, so nothing is claimed.
    return { ...context, position: "unknown" };
  }
  const value = surface.text;
  if (value.slice(context.start, context.end) === context.text) {
    return { ...context, position: "exact" };
  }
  const found = value.indexOf(context.text);
  if (found === -1) return { ...context, position: "gone" };
  const upToCaret = value.slice(0, found + context.text.length);
  return {
    ...context,
    start: found,
    end: found + context.text.length,
    line: upToCaret.split("\n").length,
    column: upToCaret.length - (upToCaret.lastIndexOf("\n") + 1) + 1,
    position: "moved",
  };
}

// --- "Make this a reminder" under the answer to a dated intention ------------
//
// "I need to call the dentist on Friday" is a reminder said aloud (the owner,
// 2026-10-27; CHAT_PLAN decision 79). `POST /reminders/suggest` reads the
// message by rules alone, so the chip is the same with a model up or down,
// and it makes nothing: one press creates, with the usual Undo. Like the
// follow-ups it is fired after the turn is saved, never awaited, silent on
// every failure, and only drawn if its bubble is still on screen.
async function offerReminder(bubble, question) {
  if (!bubble || !question) return;
  let found = null;
  try {
    const read = await apiJson("/reminders/suggest", {
      method: "POST",
      silent: true,
      body: JSON.stringify({ text: String(question).slice(0, 4000), tz_offset_minutes: -new Date().getTimezoneOffset() }),
    });
    found = read?.suggestion || null;
  } catch {
    return; // an offer that fails is no offer, not an error on a fine answer
  }
  if (!found || !bubble.isConnected) return;
  bubble.querySelector(":scope > .chat-reminder-offer")?.remove();
  const row = document.createElement("div");
  row.className = "chat-reminder-offer";
  const offer = chip(`ph:alarm Make this a reminder: ${found.text}, ${relativeWhen(found.due_at)}${found.guess ? " (a guess)" : ""}`, "", async () => {
    offer.classList.add("hidden");
    try {
      const made = await apiJson("/reminders", {
        method: "POST",
        body: JSON.stringify({
          text: found.text,
          due_at: found.due_at,
          priority: found.priority || "normal",
          recurring: found.recurring || "none",
          alert_minutes: found.alert_minutes ?? null,
        }),
      });
      reminderMadeUndo(made);
      loadReminders();
      row.replaceChildren(Object.assign(document.createElement("span"), { className: "muted", textContent: `Reminder set: ${relativeWhen(made.due_at)}.` }));
    } catch (error) {
      offer.classList.remove("hidden");
      toast(error.message || "Couldn't make that reminder.", true);
    }
  });
  offer.title = "Makes a reminder from what you wrote; nothing is made until you press this";
  row.appendChild(offer);
  bubble.appendChild(row);
  chatScrollToEnd();
}

// --- "what to ask next" chips under a finished answer -------------------------
//
// The empty-state chips (loadChatSuggestions) taught the feature for the first
// question and then went away, which left every turn after it ending on a blank
// box. These are the same idea for the turn you just read.
//
// Three things this must not do, all of which are why it lives out here rather
// than inside the streaming loop:
//
// - **Delay the answer.** It fires after the turn is rendered and saved, and
//   nothing awaits it.
// - **Show an error.** `/chat/followups` returns [] on every failure path
//   including the AI being off, and [] renders nothing at all. A row that says
//   "couldn't suggest anything" is worse than no row.
// - **Attach to the wrong bubble.** The reply can land after the reader has
//   sent another message or opened a different conversation, so the bubble it
//   was asked for has to still be on screen when it does.
async function offerFollowups(bubble, question, answer, given = null) {
  if (!bubble || !question || !answer) return;
  //: `given`: a composed answer's own next questions, already in hand.
  let picks = given || [];
  if (!given) {
    try {
      picks = await apiJson("/chat/followups", {
        method: "POST",
        silent: true,
        body: JSON.stringify({ question: clipFor("followQuestion", question), answer: clipFor("followAnswer", answer) }),
      });
    } catch {
      return; // no honest error state for a suggestion, see the module note
    }
  }
  //: A call's asks arrive mid-stream and are only drawn then (ask-compose.js);
  //: saved here, after the turn, so they cannot race its save (INBOX 1300 C42).
  if (!picks?.length) picks = JSON.parse(bubble.dataset.followups || "[]");
  if (!Array.isArray(picks) || !picks.length) return;
  // `isConnected` is the check that matters: a deleted turn, a cleared chat or
  // a switched conversation all detach the bubble, and appending to a detached
  // node is an invisible leak rather than a visible bug.
  if (!bubble.isConnected) return;
  renderFollowups(bubble, picks);
  // Saved, so they are still there next time. Reported directly: "suggested
  // repsponse continuation prompts in chat doesnt persist and disappears once
  // I switch chat sessions or quit the app", they never persisted because
  // nothing stored them; they lived only on this DOM node.
  //
  // Not awaited and silent, for the same reason the request above is: this is
  // bookkeeping behind a suggestion, and a failed save must not put an error
  // on screen over an answer that is fine.
  saveFollowups(bubble, picks);
}

//: What the model is actually told. Terse on purpose: it rides on every
//: message that carries a selection, and the tool schemas are already the
//: dominant fixed cost of a round (§R5 item 1).
function selectionContextBlock(context) {
  if (context.kind === "reading") {
    return [`The user is asking about the text read (OCR) from ${context.title}:`, "", context.text, ""].join("\n");
  }
  const where =
    context.position === "gone" || context.position === "unknown"
      ? `${context.title} (the user has since edited it, so this passage may no longer be there)`
      : `${context.title}, line ${context.line}, column ${context.column}`;
  const parts = [`The user has selected this passage in ${where}:`, "", context.text, ""];
  const around = [context.before, context.after].some((t) => (t || "").trim());
  if (around) {
    parts.push(
      "Immediately around it, for context only, do not treat it as the question:",
      "",
      `…${context.before}⟦selection⟧${context.after}…`
    );
  }
  return parts.join("\n");
}

//: Upload whatever is still staged, and return the attachment list with real
//: ids. Called at the moment a message is actually sent, the point where the
//: user has committed to it and the server needs to know.
//:
//: A failure here has to stop the send rather than drop the picture quietly:
//: a message that arrives without the image it was written about is worse
//: than one that refuses to send and says why.
async function commitStagedImages() {
  for (const image of attachedImages) {
    if (image.id) continue; // already on the server (a regenerate re-uses these)
    const form = new FormData();
    form.append("file", image.file);
    // No explicit Content-Type: the browser sets its own multipart boundary
    // for a FormData body, and `api()`'s default JSON header would be wrong
    // here: the same reason the editor's own image-drop upload overrides
    // headers rather than merging.
    const uploaded = await apiJson("/media/upload", {
      method: "POST",
      headers: authHeaders(),
      body: form,
    });
    image.id = uploaded.id;
    image.url = uploaded.url;
    image.name = uploaded.filename || image.name;
  }
  return attachedImages;
}

async function saveFollowups(bubble, picks) {
  if (chatConv.id === null) return; // an unsaved chat has no turn to attach to
  // Which turn this bubble is: its index among the assistant bubbles, which is
  // exactly how every other per-turn endpoint in this file addresses one.
  const bubbles = [...$("chat-messages").querySelectorAll(".msg.assistant")];
  const index = bubbles.indexOf(bubble);
  if (index === -1) return;
  const conversationId = chatConv.id;
  await apiJson(`/conversations/${conversationId}/turns/${index}/followups`, {
    method: "PUT",
    silent: true,
    body: JSON.stringify({ followups: picks }),
  }).catch(() => {});
}

function paintChatTimer() {
  const box = chatTimerBox;
  if (!box || document.hidden) return; // a hidden tab paints nothing; the next tick catches up
  const seconds = Math.floor((performance.now() - chatTimerStartedAt) / 1000);
  // Plain seconds under a minute, m:ss above it, "97s" is a number you have
  // to convert, and by then it is the interesting case.
  box.textContent =
    seconds < 60
      ? `${seconds}s`
      : `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

// Put the counter in the bubble this turn is being written into.
function mountChatTimer(bubble) {
  if (!bubble) return;
  chatTimerBox?.remove();
  const box = document.createElement("span");
  box.className = "msg-timer";
  box.setAttribute("aria-hidden", "true"); // the status line already says it aloud
  chatTimerBox = box;
  // Beside the role label, which is the bubble's own header row, it reads as
  // "LIBRARIAN · 4s" rather than as a number floating in the answer.
  (bubble.querySelector(".msg-role") || bubble).appendChild(box);
  paintChatTimer();
}

function startChatTimer() {
  // Started before the bubble exists, the clock has to include the wait for
  // the first byte, which on a cold local model is most of it. `mountChatTimer`
  // gives it somewhere to draw a moment later.
  clearInterval(chatTimerInterval);
  chatTimerStartedAt = performance.now();
  chatTimerInterval = setInterval(paintChatTimer, 1000);
}

function stopChatTimer() {
  clearInterval(chatTimerInterval);
  chatTimerInterval = null;
  // Taken off screen, not left showing: the answer is finished, and its
  // metadata line already carries the final duration. A live-looking counter above a
  // finished answer is the bug this replaced.
  chatTimerBox?.remove();
  chatTimerBox = null;
}

function settlePendingAgentQuestion(answer) {
  if (pendingAgentQuestion) pendingAgentQuestion.settle(answer);
}

// The files a message carried, under the message that carried them.
//
// Reported directly: "images and files uploaded into a chat conversation
// arent rendered with the chat messages, the captions arent viewable…and they
// arent previewable or quick navigatable to their stored location in the
// library or documents etc or viewable in a better environment". All of that
// was true: the composer showed a thumbnail chip until you pressed send, and
// then the picture vanished from the conversation entirely, the ids were
// stored (for the model and for media_gc) and nothing ever drew them again.
//
// `attachments` comes hydrated from `GET /conversations/{id}` on reload and is
// built locally on a live send, so both paths render the same thing.
function chatAttachmentStrip(attachments) {
  if (!attachments || !attachments.length) return null;
  const strip = document.createElement("div");
  strip.className = "msg-attachments";
  const images = attachments.filter((a) => a.kind === "image");

  for (const item of attachments) {
    if (item.kind === "image") {
      const figure = document.createElement("figure");
      figure.className = "msg-attachment msg-attachment-image";
      const img = document.createElement("img");
      img.src = mediaSrc(item.url);
      img.alt = item.caption || item.name || "";
      img.loading = "lazy";
      img.title = "Click to view it full size";
      // An upload deleted from the Library long after this message was sent
      // resolves to a row that no longer has a file. Hiding the broken tile
      // is what the gallery does; saying so is better than a grey box.
      img.addEventListener("error", () => {
        figure.classList.add("msg-attachment-missing");
        img.remove();
        const gone = document.createElement("p");
        gone.className = "muted text-sm";
        gone.textContent = `“${item.name}” isn't in your library any more.`;
        figure.prepend(gone);
      });
      img.addEventListener("click", () =>
        openLightbox(
          images.map((i) => ({
            filename: i.name,
            getUrl: () => mediaSrc(i.url),
            caption: i.caption || "",
            text: i.text || "",
          })),
          images.indexOf(item)
        )
      );
      figure.appendChild(img);

      // The caption, which is the half the report names twice. Shown under
      // the thumbnail rather than only in the lightbox: a picture in a
      // conversation is often referred to by what it shows.
      if (item.caption) {
        const caption = document.createElement("figcaption");
        caption.className = "muted text-sm";
        caption.textContent = item.caption;
        figure.appendChild(caption);
      }

      //: **The other half nothing said out loud.** Asked for directly: "in
      //: the chat, when an image and/or document is captioned and ocr is
      //: used it should be tagged under the image in the chat bubble." The
      //: caption was already shown above; `item.text` (the vision-OCR or
      //: Tesseract reading) was resolved by the backend the whole time
      //: (`_hydrate_attachments` in routes_conversations.py) and handed to
      //: the lightbox on click, but nothing in the bubble itself said a
      //: reading existed at all, so the only way to learn one was there was
      //: to open the picture and look.
      //:
      //: A badge, not the text itself: this app has already learned that
      //: lesson once (`ai/embeddings.py`'s `MAX_MEDIA_TEXT_CHARS` note on why
      //: a whole page of transcription does not belong inline in a note), and
      //: a chat bubble is an even worse place for a page of OCR text to land
      //: uninvited. Same "Read · N words" shape the Files sub-tab's reading
      //: list already uses, so the same fact reads the same way everywhere it
      //: appears.
      if (item.text) {
        const words = wordCount(item.text);
        const badge = document.createElement("button");
        badge.type = "button";
        badge.className = "chip msg-attachment-read-badge";
        setLabel(badge, `ph:scan Read · ${words.toLocaleString()} words`);
        badge.title = "Text was found in this picture, click it to see the page";
        //: Same lightbox call the thumbnail itself uses, so "click the
        //: picture" and "click the badge that says there is text on it" land
        //: on the same place rather than becoming two different doors.
        badge.addEventListener("click", () =>
          openLightbox(
            images.map((i) => ({
              filename: i.name,
              getUrl: () => mediaSrc(i.url),
              caption: i.caption || "",
              text: i.text || "",
            })),
            images.indexOf(item)
          )
        );
        figure.appendChild(badge);
      }

      const actions = document.createElement("div");
      actions.className = "msg-attachment-actions";
      actions.appendChild(
        smallButton("ph:image Library", `Find “${item.name}” in your library`, () =>
          // One helper, because the media view is two sub-tabs now and a PDF
          // has to land on Files rather than on Images. See
          // `focusLibraryFile` in library.js.
          focusLibraryFile(item.name, item.url || item.name)
        )
      );
      figure.appendChild(actions);
      strip.appendChild(figure);
      continue;
    }

    strip.appendChild(notebookCard(item));
  }
  return strip;
}

//: **The way onward, built in one place so both paths draw the same buttons.**
//:
//: Reported: "the continue step and edit step buttons in the chat arent
//: persistent and disappeared when I came back to the chat". They were built
//: only while the stream was finishing, from local variables (`stopped`,
//: `stoppedAtStep`, the skill and its inputs) that nothing wrote down, so a
//: run you stopped offered Resume until the moment you changed tab and then
//: silently stopped offering it, with the run's work still sitting there and
//: no way back to it. The state is saved on the turn now (`resume` in the
//: turn body) and `openConversation` calls this with it, which is the same
//: shape the Sources panel, the grounding chips and the followups each had
//: to be given for the same reason.
//:
//: One function rather than a copy in the reopen path: the comment on
//: `assistantMessageActions` is about exactly this pair of paths drifting.
function appendRunResumeControls(bubble, spec) {
  if (!bubble || !spec) return;
  const stopped = Boolean(spec.stopped);
  const stoppedAtStep = typeof spec.stoppedAtStep === "number" ? spec.stoppedAtStep : null;
  const pausedForManual = Boolean(spec.pausedForManual);
  const ranOutOfRounds = Boolean(spec.ranOutOfRounds);
  const editStepAction = (index) => ({
    label: `ph:pencil-simple Edit step ${index + 1}`,
    title: "Rewrite this step and run just it, leaving the rest for afterwards",
    onClick: async () => {
      const text = await promptDialog(
        `Rewrite step ${index + 1} and run just that step. Earlier steps are ` +
          "not repeated, and the rest of the skill is left to resume afterwards.",
        spec.timeline?.stepText?.(index) || "",
        { confirmLabel: "Run this step" }
      );
      if (!text || !text.trim()) return false;
      sendChatMessage(`${spec.skill}: step ${index + 1}`, {
        skill: spec.skill,
        skillInputs: spec.skillInputs || {},
        skillOnlyStep: index,
        skillStepText: text.trim(),
        skipPlanMode: true,
      });
      return true;
    },
  });

  if (stopped && stoppedAtStep !== null && spec.skill) {
    bubble.appendChild(
      continueRunControls({
        also: editStepAction(stoppedAtStep),
        label: `ph:play Resume from step ${stoppedAtStep + 1}`,
        hint: "You stopped this. Earlier steps are not repeated.",
        onClick: () =>
          sendChatMessage(`${spec.skill}: from step ${stoppedAtStep + 1}`, {
            skill: spec.skill,
            skillInputs: spec.skillInputs || {},
            skillFromStep: stoppedAtStep,
            skipPlanMode: true,
          }),
      })
    );
  } else if (stopped && (spec.skill || spec.hasTools || spec.cutWords)) {
    //: A stopped run with no step to name, a plain agent turn, or a skill
    //: stopped before its first step finished. It still did work worth not
    //: repeating, so the offer is the same one the round limit gets.
    bubble.appendChild(
      continueRunControls({
        label: spec.skill || spec.hasTools ? "ph:play Resume" : "ph:arrow-right Continue",
        hint: "Picks up from what it had already done.",
        onClick: () =>
          sendChatMessage(
            "Continue from where you stopped. Don't redo what you have " +
              "already done: carry on with what is left, and say when it is " +
              "all finished.",
            { useTools: Boolean(spec.skill || spec.hasTools || spec.useTools) }
          ),
      })
    );
  } else if (!stopped && stoppedAtStep !== null && spec.skill && pausedForManual) {
    bubble.appendChild(
      manualPauseControls({
        onContinue: (note) =>
          sendChatMessage(`${spec.skill}: from step ${stoppedAtStep + 1}`, {
            skill: spec.skill,
            skillInputs: spec.skillInputs || {},
            skillFromStep: stoppedAtStep,
            skillManual: true,
            skillManualNote: note,
            skipPlanMode: true,
          }),
      })
    );
  } else if (!stopped && stoppedAtStep !== null && spec.skill) {
    bubble.appendChild(
      continueRunControls({
        also: editStepAction(stoppedAtStep),
        label: `ph:arrow-clockwise Resume from step ${stoppedAtStep + 1}`,
        hint: "Earlier steps are not repeated.",
        onClick: () =>
          sendChatMessage(`${spec.skill}: from step ${stoppedAtStep + 1}`, {
            skill: spec.skill,
            skillInputs: spec.skillInputs || {},
            skillFromStep: stoppedAtStep,
            skipPlanMode: true,
          }),
      })
    );
  } else if (!stopped && ranOutOfRounds) {
    bubble.appendChild(
      continueRunControls({
        label: "ph:arrow-right Continue",
        hint: "Picks up from what it had already done.",
        onClick: () =>
          sendChatMessage(
            "Continue from where you stopped. Don't redo what you have " +
              "already done: carry on with what is left, and say when it is " +
              "all finished.",
            { useTools: true }
          ),
      })
    );
  }
}

function addBubble(role, text, attachments = null) {
  clearChatEmptyState();
  lazyScript("/js/chat-time.js"); // each message's time; the file stamps bubbles as they appear
  const bubble = document.createElement("div");
  bubble.className = `msg ${role}`;
  //: The words as sent, so ArrowUp in an empty composer can reopen the last
  //: question for editing without reading them back out of the rendered DOM.
  if (role === "user" && typeof text === "string") bubble.dataset.sent = text;
  //: The saved turn this question will be (E49): chat-edit.js cuts from it.
  if (role === "user") bubble.dataset.turn = String(chatConv.turns.length);

  const label = document.createElement("div");
  label.className = "msg-role";
  // **The user's turn is named for a screen reader only.** The owner once
  // asked for a user avatar in the label row, then later had the row hidden
  // (08-consistency.css: on your own side of your own conversation "You"
  // said nothing the alignment did not), so the label is read, not seen.
  if (role === "user") {
    const name = document.createElement("span");
    name.textContent = "You";
    label.append(name);
  } else {
    label.textContent = assistantLabel();
  }
  const body = document.createElement("div");
  body.className = "msg-body";
  //: **A long question is drawn clipped** (warm12-1101): a 20,000-character question reached its
  //: first token about 450 ms after a short one, all of it the browser laying out the whole text in
  //: this bubble. Past `BUBBLE_CLIP` characters the first part shows, cut at a space, with the
  //: notes' "Show more"; what reads the question back reads `dataset.sent`, never this body.
  const BUBBLE_CLIP = 2000;
  const long = role === "user" && typeof text === "string" && text.length > BUBBLE_CLIP * 1.2;
  //: Cut at the last space or line break before the limit; with none near it, never inside a surrogate pair.
  const space = long ? Math.max(text.lastIndexOf(" ", BUBBLE_CLIP), text.lastIndexOf("\n", BUBBLE_CLIP)) : -1;
  const hard = long && /[\ud800-\udbff]/.test(text[BUBBLE_CLIP - 1]) ? BUBBLE_CLIP - 1 : BUBBLE_CLIP;
  const clipped = long ? `${text.slice(0, space > BUBBLE_CLIP * 0.8 ? space : hard).trimEnd()}\u2026` : text;
  body.textContent = long ? clipped : text;
  bubble.append(label, body);
  //: **A question past ten lines folds** (the owner, 2026-11-02, "auto collapse with the see more/see less
  //: at about like 10 lines", as Perplexity does): the body is the notes' clamp (`entry-clamped`, ten lines
  //: for a question in chat.css), faded at its foot, with the notes' "Show more" under it. Whether it
  //: overflows is read once, the frame after the bubble is in the page; a long text is also cut, above.
  if (role === "user" && typeof text === "string") {
    body.classList.add("entry-clamped");
    requestAnimationFrame(() => {
      if (!long && body.scrollHeight <= body.clientHeight + 1) return body.classList.remove("entry-clamped");
      body.classList.add("is-folded");
      const more = document.createElement("button");
      more.type = "button";
      more.className = "entry-more";
      more.textContent = "Show more";
      more.setAttribute("aria-expanded", "false");
      more.addEventListener("click", () => {
        const open = more.getAttribute("aria-expanded") !== "true";
        if (long) body.textContent = open ? text : clipped;
        body.classList.toggle("entry-clamped", !open);
        body.classList.toggle("is-folded", !open);
        more.textContent = open ? "Show less" : "Show more";
        more.setAttribute("aria-expanded", String(open));
      });
      body.after(more);
    });
  }
  //: **The person's own mark** (INBOX 409: "auto generate other icons in
  //: other places like potentially the user chat bubbles"). Generated from
  //: the profile name the way a persona's is, so it is theirs and the same
  //: every time; "You" when no name is set. It sits on the bubble's top
  //: right corner, positioned rather than in the flow, so the bubble's size,
  //: padding and text are exactly what they were (chatmarks.js measures
  //: that): the label row that used to hold an avatar is hidden on purpose.
  if (role === "user") bubble.appendChild(userMarkEl());
  //: **Above the bubble, on its side** (INBOX 1460, the hub's decision: the
  //: way chat apps show what was attached). The strip is the bubble's
  //: previous sibling, not a child, because the bubble's fill is the bubble;
  //: `dropChatBubble` removes it when the bubble goes.
  const strip = chatAttachmentStrip(attachments);

  if (role === "user") {
    bubble.appendChild(
      chatMessageActions([
        { label: "ph:copy", title: "Copy", onClick: (e) => copyToClipboard(text, e.currentTarget) },
        { label: "ph:pencil-simple", title: "Edit this question", onClick: () => lazyScript("/js/chat-edit.js").then(() => editAndResend(bubble, text)) },
        { label: "ph:trash", title: "Delete this message", onClick: () => removeChatBubble(bubble) },
      ])
    );
  }
  if (strip) {
    $("chat-messages").appendChild(strip);
    bubble.cards = strip;
  }
  $("chat-messages").appendChild(bubble);
  chatScrollToEnd();
  return bubble;
}

//: Builds a reply's actions and puts them in its head row, at its end, in its
//: flow (CHAT_PLAN B2: "actions in the head"): hung under the bubble or
//: floated over its corner, a row lay over text (B2's review); a question's
//: row stays under its bubble.
assistantMessageActions.models = [];
apiJson("/models/status", { cacheMs: 600, silent: true })
  .then((s) => Object.assign(assistantMessageActions.models, (s.installed_models || []).map((m) => m.name), { current: s.chat_model }))
  .catch(() => {});

//: L165: every version of an answer is kept; the pager (answer-versions.js) shows past one.
assistantMessageActions.versionsOf = function (bubble) {
  if (bubble?.versions?.length) return bubble.versions;
  if (!bubble || bubble.answerText === undefined) return [];
  return [{ text: bubble.answerText, sources: bubble.answerSources || [], made_at: bubble.dataset.madeAt || new Date().toISOString() }];
};

assistantMessageActions.pager = function (bubble, versions) {
  bubble.versions = versions;
  bubble.querySelector(".answer-version-pager")?.remove();
  if (!(versions.length > 1)) return;
  const pager = document.createElement("div");
  pager.className = "answer-version-pager row";
  pager.setAttribute("role", "group");
  pager.setAttribute("aria-label", "Versions of this answer");
  const label = document.createElement("span");
  label.className = "muted";
  label.setAttribute("aria-live", "polite");
  let at = versions.length - 1;
  const show = (to) => {
    at = Math.max(0, Math.min(versions.length - 1, to));
    const version = versions[at];
    const el = [...bubble.querySelectorAll(".bubble-answer")].pop();
    if (el) {
      el.replaceChildren();
      renderMarkdown(el, version.text);
    }
    bubble.answerText = version.text;
    const old = bubble.querySelector(".chat-sources");
    const panel = chatSourcesPanel({ meta: { raw_results: version.sources || [] }, sources: chatSourcesFrom({ meta: { raw_results: version.sources || [] } }) });
    if (old) (panel ? old.replaceWith(panel) : old.remove());
    else if (panel) bubble.querySelector(".msg-body, .agent-steps")?.after(panel);
    label.textContent = `${at + 1} of ${versions.length}`;
    previous.disabled = at === 0;
    next.disabled = at === versions.length - 1;
  };
  const previous = smallButton("ph:caret-left", "Earlier version", () => show(at - 1));
  const next = smallButton("ph:caret-right", "Later version", () => show(at + 1));
  pager.append(previous, label, next);
  bubble.appendChild(pager);
  show(at);
};

function assistantMessageActions({ bubble, text, question, onEdit, message }) {
  const off = aiIsOff();
  bubble.answerText = text;
  //: Both are local here, not top-level: the shared scope has a name cap (test_global_scope_ratchet).
  //: **Not right on an answer** (audit 1028 E59): one correction per note it cited, against
  //: the question; the next question like it reads those notes last (and leaves them out
  //: after a second mark), composed and model answers alike, since the search is shared.
  //: The undo is the corrections' own Delete; the redo marks again.
  async function markAnswerNotRight(bubble, question) {
    const ids = [...new Set([...bubble.querySelectorAll(".chat-source-card[data-note-id]")].map((card) => Number(card.dataset.noteId)).filter(Number.isInteger))].slice(0, 12);
    if (!ids.length) return;
    const post = () => apiJson("/learned/answer-verdict", { method: "POST", body: JSON.stringify({ question, entry_ids: ids }) });
    try {
      let made = await post();
      bubble.dataset.notRight = "1";
      //: Said once (L225): what is kept, where, and how to clear it.
      const first = !localStorage.getItem("notRightNoted");
      localStorage.setItem("notRightNoted", "1");
      offerUndo(
        "Marked an answer not right",
        first ? "Stored only on this device. Clear it in Settings, Learned." : "Marked not right. Those notes come last for a question like this.",
        async () => {
          await Promise.all(made.ids.map((id) => api(`/learned/corrections/${id}`, { method: "DELETE" })));
          delete bubble.dataset.notRight;
        },
        async () => {
          made = await post();
          bubble.dataset.notRight = "1";
        }
      );
    } catch (error) {
      toast(error.message, true);
    }
  }

  //: The "Regenerate as…" submenu: one row per persona the picker offers. With no
  //: model the composer answers in the persona's voice too, so it works there as well;
  //: a running turn is refused by `regenerateFrom`.
  function regenerateAsItems(bubble) {
    const names = [...($("persona-select")?.options || [])].map((option) => option.value).filter(Boolean);
    if (names.length < 2) return null;
    return {
      label: "ph:users-three",
      title: "Regenerate as…",
      items: names.map((name) => ({
        label: `ph:user ${name}`,
        title: `Answer this question again as ${name}`,
        run: () => regenerateFromBubble(bubble, { persona: name }),
      })),
    };
  }

  //: Regenerate with (L165): this answer only, on the same model, another, or none.
  function regenerateWithItems(bubble) {
    const run = (oneModel) => () => regenerateFromBubble(bubble, { oneModel });
    const known = assistantMessageActions.models;
    const others = known.filter((name) => name !== known.current);
    return {
      label: "ph:cpu",
      title: "Regenerate with…",
      items: [
        { label: "ph:arrow-clockwise Same model", title: "Answer again with the same model", run: run(known.current || "") },
        ...others.map((name) => ({ label: `ph:cpu ${name}`, title: `Answer this once with ${name}`, run: run(name) })),
        { label: "ph:notebook Without a model", title: "Answer from your notes alone, no model", run: run("composer") },
      ],
    };
  }

  const row = chatMessageActions([
    {
      label: "ph:copy",
      title: "Copy message",
      onClick: async (e) => {
        const button = e.currentTarget;
        await ensureModule("gestureKit"); // chatTurnTranscript lives there, off the boot scripts
        copyToClipboard(chatTurnTranscript(bubble, text), button);
      },
    },
    {
      label: "ph:arrow-clockwise",
      title: "Regenerate from here",
      onClick: () => regenerateFromBubble(bubble),
    },
    off ? null : {
      label: "ph:scissors",
      title: "Rewrite this shorter",
      onClick: () =>
        rewriteAnswerWith(
          "Rewrite your last answer to be shorter, keep every fact, cut the padding.",
          "Make that shorter."
        ),
    },
    off ? null : {
      label: "ph:student",
      title: "Explain it more simply",
      onClick: () =>
        rewriteAnswerWith(
          "Explain your last answer again in plain language, short sentences, no jargon.",
          "Explain that more simply."
        ),
    },
    {
      label: "ph:git-branch",
      title: "Fork the conversation from here",
      onClick: () => forkFromBubble(bubble),
    },
    //: **Regenerate in another persona** (audit 1028 E60): once, for this answer; the picker stays where it was.
    regenerateAsItems(bubble),
    regenerateWithItems(bubble),
    {
      label: "ph:speaker-high",
      title: "Read aloud",
      speak: true,
      //: Turns to Stop reading for as long as it speaks, the icon button and the same
      //: item in the ⋯ menu alike (both carry `data-speak`, chatMessageActions).
      onClick: () => {
        const said = speakText(text);
        const paint = (on) => {
          for (const row of document.querySelectorAll("[data-speak]")) {
            row.title = on ? "Stop reading" : "Read aloud";
            setLabel(row, `ph:${on ? "stop" : "speaker-high"}${row.classList.contains("menu-item") ? ` ${row.title}` : ""}`);
            row.setAttribute("aria-label", row.title);
          }
        };
        if (said) said.onstart = () => paint(true);
        if (said) said.onend = said.onerror = () => paint(false);
      },
    },
    {
      label: "ph:note-pencil",
      title: "Save this answer as a draft note",
      onClick: () => saveChatAnswerAsNote(question, text),
    },
    //: Under a sentence there is no outline to draw (the server says 422).
    String(text || "").trim().split(/\s+/).length < 4 ? null : { label: "ph:tree-structure", title: "Mind map this", onClick: () => chatKeep("map", text) },
    { label: "ph:alarm", title: "Set a reminder from this answer", onClick: () => reminderFromChatAnswer(text) },
    //: **This answer is wrong, on the whole answer** (audit 1028 E59; not worded "Not right", that pair is status.js's): only where it cites a note, and never in a private chat (nothing is learned there).
    !chatConv?.private && question && bubble.querySelector(".chat-source-card[data-note-id]")
      ? { label: "ph:thumbs-down", title: "This answer is wrong", onClick: () => markAnswerNotRight(bubble, question) }
      : null,
    ...(onEdit ? [{ label: "ph:pencil-simple", title: "Edit this answer", onClick: onEdit }] : []),
    {
      label: "ph:trash",
      title: "Delete this message",
      danger: true,
      onClick: () => deleteChatTurn(bubble),
    },
  ]);
  //: A reopened turn (L165): its sources and, past one version, the pager.
  if (message) {
    bubble.answerSources = message.raw_results || [];
    if (message.versions?.length > 1) assistantMessageActions.pager(bubble, message.versions);
  }
  return (bubble.querySelector(":scope > .msg-role") || bubble).appendChild(row);
}

function renderRecordsDetails(holder, meta) {
  if (!meta.raw_results.length) return;
  const details = document.createElement("details");
  const summary = document.createElement("summary");
  summary.className = "muted";
  const label = SEARCH_MODE_LABELS[meta.search_mode] || meta.search_mode;
  summary.textContent = `${meta.raw_results.length} matching note${
    meta.raw_results.length === 1 ? "" : "s"
  } (${label}): click one to open it`;
  // The tune-sensitivity shortcut used to live here too, repeated on every
  // single message's own disclosure. Reported directly: it belongs as one
  // persistent control (`#chat-tune-search`, wired near the Chat dock's
  // other "how it answers" settings) instead of message metadata.
  details.appendChild(summary);
  const list = document.createElement("ul");
  //: The Ask tab's Matching records card (`replyRecordCards`), one card for
  //: both tabs; `.records-cards` lets its CSS reach this list too.
  list.className = "entry-list records-cards";
  // Same provenance badges as the Ask tab (matchReasonBadge / renderRawResults
  // above): the backend's "meta" SSE event already carries match_info and
  // connected_ids for a chat turn, same shape as an Ask turn's; this just
  // hadn't been wired up here, so a chat search result showed no reason at
  // all while the identical Ask result did.
  const connected = new Set(meta.connected_ids || []);
  const matchInfo = meta.match_info || {};
  const scored = everyRowScored(meta.raw_results, matchInfo, connected);
  for (const entry of meta.raw_results) {
    const row = clickableResult(entry);
    const badge = matchReasonBadge(matchInfo[entry.id], scored);
    if (badge) {
      if (connected.has(entry.id)) row.classList.add("result-connected");
      if (matchInfo[entry.id]?.type === "connected_2hop") row.classList.add("result-connected-2hop");
      placeResultBadge(row, badge);
    }
    list.appendChild(row);
  }
  details.appendChild(list);
  holder.appendChild(details);
  matchReasonBadge.hold(list);
  ensureModule("replyKit").then(() => replyRecordCards(list, meta.raw_results, matchInfo, scored)).then(() => matchReasonBadge.hold(list)).catch(() => {});
}

// Delete one Q&A exchange: its assistant bubble AND the user bubble just
// above it, from the screen, memory, and the saved conversation.
async function deleteChatTurn(assistantBubble) {
  if (chatController) return; // don't edit a chat mid-stream
  const bubbles = [...$("chat-messages").querySelectorAll(".msg.assistant")];
  const index = bubbles.indexOf(assistantBubble);
  if (index === -1) return;
  if (!(await confirmDialog("Delete this message?"))) return;

  let result = null;
  if (chatConv.id !== null) {
    try {
      const id = chatConv.id;
      result = await apiJson(`/conversations/${id}/turns/${index}`, {
        method: "DELETE",
      });
      chatWriteRecord("chatTurnUndo", id, index, result);
      if (result.conversation_deleted) {
        newChatConversation();
        loadConversationList();
        return restoreFocusTo($("chat-input"));
      }
    } catch {
      toast("Couldn't delete that message.", true);
      return;
    }
  }
  // The user bubble is the one immediately before this assistant bubble.
  const userBubble = assistantBubble.previousElementSibling;
  //: Later questions move up one saved turn (E49).
  for (let node = assistantBubble; (node = node.nextElementSibling); ) if (node.dataset.turn) node.dataset.turn -= 1;
  if (userBubble?.classList.contains("user")) dropChatBubble(userBubble);
  assistantBubble.remove();
  chatConv.turns.splice(index, 1);
  //: The chat counts the turns that are left, said at once (L-chat-19, the owner: "the token
  //: usage I was at for that chat has lowered??"); the undo toast says the change.
  if (result && Number.isFinite(result.tokens)) renderChatUsage(result.tokens);
  else renderChatTurnCount();
  //: The meter read the last turn's prompt: with that turn gone it describes nothing left.
  if (index === bubbles.length - 1) renderChatContextMeter(null);
  // The turn below is the end of the thread now, so its saved chips come back.
  refreshFollowupVisibility();
  if (!$("chat-messages").querySelector(".msg")) renderChatEmptyState();
  loadConversationList();
  restoreFocusTo($("chat-input")); //: the opener went with the message (AI14)
}

// The offer to carry on, shown under a turn that stopped before it was done.
//
// Reported twice in the same breath: *"the agent struggles with long tasks
// like skills then cuts out half way through and has to restart, or it hits a
// limit for tool calls."* Both ended in a paragraph telling the user to ask it
// to continue: so continuing meant typing the request out again from memory,
// and resuming a six-step skill meant re-running the three steps that had
// already changed the notebook. This is one button for each case.
//: `also` is a second, quieter action on the same row (Phase D's "edit a
//: step's text and re-run just that step"). A row rather than a menu because
//: there are two of them and both are the answer to the same question, "this
//: run stopped, now what": one carries on, the other changes the step that
//: stopped it and tries that alone.
function continueRunControls({ label, hint, onClick, also = null }) {
  const row = document.createElement("div");
  row.className = "run-continue";
  const button = document.createElement("button");
  button.type = "button";
  button.className = "small";
  // continueRunControls is called with "ph:arrow-clockwise Resume from step N".
  setLabel(button, label);
  button.addEventListener("click", () => {
    // One press only: a second would start a duplicate run over the same
    // notes, and every step of it writes.
    button.disabled = true;
    onClick();
  });
  row.appendChild(button);
  if (also) {
    const second = document.createElement("button");
    second.type = "button";
    second.className = "ghost small";
    setLabel(second, also.label);
    second.title = also.title || "";
    second.addEventListener("click", () => {
      second.disabled = true;
      //: Re-enabled when the dialog is dismissed without a rewrite, because
      //: nothing ran and the offer is still good. The primary above cannot do
      //: this: pressing it starts a run there and then.
      Promise.resolve(also.onClick()).then((ran) => {
        if (!ran) second.disabled = false;
      });
    });
    row.appendChild(second);
  }
  if (hint) {
    const why = document.createElement("span");
    why.className = "muted";
    why.textContent = hint;
    row.appendChild(why);
  }
  return row;
}

//: **Fork from this point in the conversation.** The server already copies a
//: conversation up to a turn (`POST /conversations/{id}/fork`, `up_to`), this
//: is the door to it from the message you are actually looking at, which is
//: where "try a different direction from here" is decided.
async function forkFromBubble(bubble) {
  if (!chatConv || chatConv.id === null) {
    return toast("Nothing to fork yet, ask something first.");
  }
  //: Which turn this is: count the assistant bubbles before it. `up_to` is a
  //: turn index on the server, and a turn is one question and its answer.
  const bubbles = [...$("chat-messages").querySelectorAll(".msg.assistant")];
  const index = bubbles.indexOf(bubble);
  if (index === -1) return;
  try {
    const fork = await apiJson(`/conversations/${chatConv.id}/fork`, {
      method: "POST",
      body: JSON.stringify({ up_to: index + 1 }),
    });
    await loadConversationList();
    chatWriteRecord("chatForkUndo", fork);
    toastAction(`Forked at this message → “${fork.title}”.`, "Open it", () =>
      openConversation(fork.id), { go: { open: "conversation", id: fork.id } }
    );
  } catch (error) {
    toast(error.message || "Couldn't fork from here.", true);
  }
}

// Manual (step-through) mode's pause card: a text box to add what the agent
// missed or answer a question it raised, and a Continue button, the answer
// to "a manual mode" asked for directly, and the single most-requested
// unbuilt thing on the roadmap. `onContinue(note)` gets whatever was typed,
// or an empty string if nothing was.
function manualPauseControls({ onContinue }) {
  const row = document.createElement("div");
  row.className = "run-continue run-continue-manual";
  const note = document.createElement("input");
  note.type = "text";
  note.placeholder = "Add anything before the next step (optional)…";
  note.maxLength = 500;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "small";
  setLabel(button, "ph:play Continue");
  button.addEventListener("click", () => {
    button.disabled = true;
    note.disabled = true;
    onContinue(note.value.trim());
  });
  note.addEventListener("keydown", (e) => {
    if (e.key === "Enter") button.click();
  });
  const why = document.createElement("span");
  why.className = "muted";
  why.textContent = "Paused: step by step mode.";
  row.append(why, note, button);
  return row;
}

function markFollowup(userBubble, ref) {
  if (!userBubble || !ref) return;
  userBubble.dataset.followupOf = ref;
  userBubble.querySelector(":scope > .chat-trail")?.remove();
  const chain = followupChain(userBubble);
  if (!chain.length) return;
  const trail = followupTrail(chain.map((b) => b.dataset.sent), (i) => {
    const target = chain[i];
    if (!target.isConnected) return;
    target.scrollIntoView({ behavior: reducedMotionWanted() ? "auto" : "smooth", block: "center" });
    target.classList.remove("flash");
    void target.offsetWidth; // restart the highlight on a second press
    target.classList.add("flash-target", "flash");
    clearTimeout(target.flashTimer);
    target.flashTimer = setTimeout(() => target.classList.remove("flash"), 2700);
  });
  userBubble.querySelector(":scope > .msg-body")?.before(trail);
}

// Remove a message from the live transcript. A saved conversation stores
// question/answer pairs, so deleting either half drops the whole exchange, 
// otherwise the missing half would reappear on reopening the chat.
// Deleting from a user bubble drops the same exchange as deleting from the
// answer below it, so both buttons route through one implementation.
function removeChatBubble(bubble) {
  const assistant = bubble.classList.contains("user")
    ? bubble.nextElementSibling
    : bubble;
  if (!assistant?.classList.contains("assistant")) return;
  return deleteChatTurn(assistant);
}
