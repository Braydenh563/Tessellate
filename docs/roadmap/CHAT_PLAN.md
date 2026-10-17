# Ask and Chat: checkable answers, one composer, an agent you reach for

**Status: written by Fable by direct instruction ("the ask subtab and chat
tab need to be like perplexity but better"; "the grounding of notes in ai
responses needs a lot of fixing"; "the popup agent feature could do with
more quick prompt options"), from the owner's screenshots and the code.
Executed with WORLD_CLASS_PLAN Briefs 11, 12 and 13, which it specifies.**

Back to [../ROADMAP.md](../ROADMAP.md).

## 1. What exists (checked in the code)

`/chat/stream` (`routes_chat.py`) streams `status`, `meta`, `thinking`,
`grounding`, `related`, `semantic`, `hint`, `answer`, `stats`, `done`.
`ai/grounding.py` splits the answer into sentences and word-matches each
against the retrieved notes (`ground_answer_sentences`). The Chat tab has
a conversation sidebar, a head (title, model, context %, tokens, fork,
compress, kebab), the transcript (user bubbles right, assistant cards
left with a persona label, sources card grid, "Grounded in" chips, stats
line, "Next" chips, a per-answer action strip), a composer (note and
attachment buttons, textarea, mic, Send; a second row of Skills, Web,
Plan, Ask/Agent segment, settings). The Ask sub-tab on Notes has a
single question field, a mode select, tune, Try-asking and Ask-again
chips, and a History panel. The popup agent (`#agent-monitor` and the
Ask-the-agent panel) has four starter chips. Skills run as a collapsible
plan with steps, tool cards and chips of the notes each step read.

## 2. Why it disappoints (measured against the screenshots)

1. **Grounding is thin and wrong-shaped.** An answer that named several
   notes carried one "Grounded in" chip and one superscript; a skill run
   that read ten notes carried none. Cause, in the code: grounding runs
   only over the retrieval set of the final turn and only on the final
   answer text; notes read by tools during the turn are not candidates,
   and the per-sentence match is a bag-of-words overlap that needs a
   sentence to share several rare words with one note.
2. **Sources are a gallery, citations are an afterthought.** A 17-card
   grid of sources under the answer is a second page to read; the marks
   in the text are what Perplexity gets right and the grid is what it
   does not show by default.
3. **The composer is two rows of chips** around one field, and its second
   row (Skills, Web, Plan, Ask/Agent, settings) is a bar of unrelated
   controls; the skills picker is a full-height list.
4. **User bubbles** are a solid accent block with a "YOU" label and an
   avatar; the assistant card is a quiet card. The two do not belong to
   one conversation.
5. **Streaming state** is a static three-dot glyph; "Working" rows render
   above the step they belong to; the "Still writing / Jump to latest"
   pill takes a row of the panel instead of floating.
6. **Ask is a second chat with fewer features** (no citations, no
   follow-ups that carry context, a History panel on an older recipe).
7. **The popup agent** has four starters; the owner "just defaults to one
   of the sentence starters" because the useful things (make a note of
   this, remind me, find, summarise the open note, what changed today)
   are not there, and the panel is on the old recipes.
8. **Skills**: a step is one tool call; `list_notes` paged and the model
   did not page again, so it concluded notes were missing. The owner's
   question: can one-tool-per-step do the job.

## 3. The target, in one paragraph

An answer you can check sentence by sentence: every sentence carries a
mark, the mark names the note, hover highlights the passage, and "I don't
know" is a designed state when fewer than half the sentences are
supported. One composer everywhere (Chat, Ask, the popup agent): one
field, a "+" menu for attachments, scope, persona and skill, a mode
segment (Ask, Agent), Send; nothing else on the bar. Ask is Chat in
single-turn mode with the same answer object. The popup agent is the
same composer with twelve starters grouped by verb (capture, find,
summarise, remind, do), and a "with the open note" toggle. Skills run
until each step's contract is met, paging and retrying inside the step,
and every run ends with a verification line and an Undo.

## 4. Decisions made (do not re-decide)

1. **Citation source set = retrieval set ∪ every note a tool read or
   listed in the turn.** `run_agent` collects `_touched_items` per tool
   result already (`agent.py` ~547); those ids join the grounding
   candidates. Skills therefore cite what they read.
2. **Grounding by passage, not by bag of words.** For each sentence,
   score each candidate note by the best-matching *passage* (a sliding
   window of 40 words) using BM25 over the window plus, when embeddings
   exist, cosine over the window; a sentence is supported when its best
   score clears a threshold calibrated on the eval fixtures (Brief 12);
   the mark stores `{note_id, passage_start, passage_end}` so hover can
   highlight the passage. Sentences with numbers or names get a second
   check that the number or name appears in the passage.
3. **The answer object** is one shape for Chat, Ask and the agent:
   `{sentences: [{text, marks: [{note_id, start, end, score}]}], sources,
   related, next, stats, verification}`; the renderer is one function.
4. **Marks in the text, sources on demand.** Superscript marks with the
   note's short title on hover; the source grid becomes a "Sources (9)"
   disclosure that opens a compact list (title, passage, open), not cards.
5. **The composer recipe** (`.composer`): one field; left: "+" menu
   (attach file, attach note, scope chips, persona, skill); right: mic,
   mode segment, Send (primary). The second row goes. The skills list is
   a searchable menu capped at 40vh.
6. **Bubbles.** User turns are a quiet tinted card (accent-soft, no
   avatar, no label, right-aligned, max 70% width); assistant turns are
   the card they are; the persona label stays.
7. **Streaming.** One animated three-dot indicator (CSS keyframes, honours
   reduced motion) inside the assistant card; step rows render in order
   (Working row inside its step, not above it); "Jump to latest" floats
   over the transcript with no layout row.
8. **Ask = Chat in single-turn mode.** The Ask sub-tab keeps its place
   and its History, both on the app's recipes, but renders the same
   answer object and uses the same composer; "Ask again" chips become
   follow-ups that carry the previous answer as context.
9. **Popup agent starters** (twelve, grouped): Capture: make a note of
   this, add to today's note; Find: notes about..., what did I write this
   week, open the note about...; Summarise: the open note, my week, this
   conversation; Remind: remind me to..., what is due; Do: tag my untagged
   notes, link related notes. Plus a "Use the open note" toggle that
   scopes the run to the entry on screen.
10. **Skills: a step loops until its contract is met**, up to N tool
    calls (default 6) with paging handled inside the step (`list_notes`
    with a cursor is called until the contract's count is reached or the
    cursor ends); the verifier (Brief 13) checks the postcondition. The
    owner's question is answered in the negative: one tool call per step
    is not enough; one *contract* per step is.
10a. **A skill that declares steps needs no separate prompt** (Brief 13).
    A numbered list of steps already says what the job is, and requiring a
    prompt beside it is how the two drift apart: the prompt says one thing,
    the steps do another, and the model reads both. A skill with neither is
    still refused.
10b. **`verify` is a declaration, not a step** (Brief 13). A skill may end
    with `{tool, field, expect}`; the app runs it against the notebook after
    the last step. A step saying "check it worked" is exactly the thing a 3B
    model reports having done without doing, which is the failure the whole
    contract mechanism exists for. Four predicates (min, max, equals,
    unchanged), each answerable from one integer, because a postcondition a
    small model can be graded against has to be a fact rather than a
    judgement.
10c. **A step's paged read is judged on its last call, and only for a tool
    the step's contract names** (Brief 13). "Have I reached the end" is a
    property of the last page, not of any; and holding a step open on an
    incidental `list_notes` would stall runs that work today, the same reason
    a plain string step has no contract at all. Capped at six pages, said out
    loud on the step, in its history and on the result rather than reporting
    a partial pass as a complete one.
10d. **"Find loose ends" pages the notebook instead of searching it**
    (Brief 13). Its first step was one `search_notes` call for "todo, need
    to, should", which is a top-k similarity query, and the skill's claim is
    *the* loose ends, all of them: a note saying "ring the landlord back"
    resembles nothing on that list and is exactly what the skill is for.
10e. **The run budget is a scope, not a parameter** (Brief 13, after
    `core/events.py`). What has to be true is that every model call made
    inside a run counts against that run, including the ones written later by
    somebody who has never read `ai/budget.py`; a parameter threaded through
    is true only of the call sites somebody remembered to change. Checked
    between rounds, never mid-stream: stopping inside a model call leaves half
    an answer on screen and a tool result nobody read.
10f. **A correction is recorded outside the `edited` write scope** (Brief
    13). `events.record` folds anything recorded inside a write into that
    write's own event, correctly for a category created on the way past and
    wrongly for this: a correction is a second, separately readable fact, and
    folded it is invisible to the query that looks for it. Keyed on where the
    note ended up, because "notes like this belong in B" is the half that is
    usable when filing something new.
10g. **A verify block may carry arguments, and they may only narrow it**
    (2026-09-20, taken while closing `brief-13-harness.md` item 3). Decision
    10b's shape is `{tool, field, expect}`, which can only ask a tool its
    unfiltered question: how many notes are there. The postcondition a
    *writing* skill makes is narrower, and "Auto-tag my notes" is the case
    that names itself: it claims it leaves no untagged note behind, which is
    `count_notes(untagged) max 0` and is unsayable without an argument. So the
    block takes `args`, flat scalars only, at most four
    (`skills.MAX_VERIFY_ARGS`), and `count_notes` takes the same `untagged`
    and `since` filters `list_notes` has always had, out of one shared
    function so the count and the list can never disagree about what
    "untagged" means. What does not change is what a verifier may *do*: the
    runner still refuses any tool that writes, and an argument only ever makes
    a reading narrower. The three read-only audit skills that could not verify
    without widening their allowlist now declare `count_notes` and are checked
    with it, which is the widening, stated: one read-only counting tool, on
    the wire, for a run that would otherwise only promise it changed nothing.
10h. **The page cap stays at six pages of twenty-five, and the answer to a
    large notebook is a narrower read** (2026-09-20; `brief-13-harness.md`
    item 4 asked for this to be decided in the plan rather than in the
    constant). Raising `MAX_PAGES_PER_STEP` trades one wrong answer for
    another: a run that spends its whole budget paging is not a better run
    than one that says it saw the first hundred and fifty. What was missing
    was any way to ask a *smaller* question, and that is what 10g's filters
    are: "the untagged ones", "the last thirty days", "this category", each
    answered by the database rather than by a model holding a notebook in its
    head (§R5). A step that needs more than one page of the whole notebook is
    a step whose filter has not been written yet. The honest `truncated`
    report stays exactly as it is.

12. **A link the AI writes is a card when it is the whole line, and stays
    inline otherwise** (INBOX 172, decided 2026-09-13 in Phase 3). The two
    forms answer two different questions and the plan had been reading them as
    one. A link inside a sentence is a reference: a card in the middle of a
    sentence breaks the sentence, so it keeps the inline "host / page" form
    with the full address on hover. A link a model puts on a line of its own is
    a thing being handed to you, and it gets a card: the link's own words as
    the title (a bare address falls back to its path, because the host is
    already the second line), the host under it, the source card's own recipe,
    and a hit area rather than eleven characters of underlined prose.
    **No favicon, and that is the decision rather than an omission**: fetching
    one would be the first time this app asked the web for something nobody had
    asked it to, in an app whose first line of description is that it is
    offline. The host in words is the half of a favicon that carries meaning.

13. **The help chat is a sheet reachable from anywhere** (INBOX 193, filed
    and taken 2026-09-13; asked for in INBOX 190, "give it a fitting name??").
    **Its name is decision 15's, not this one's**: "Guide" here was superseded
    a day later by the owner, and the paragraph below is kept as written
    because the reasoning in it is what decision 15 had to answer. "Guide" rather than a person's name or a
    mascot: it explains the app and nothing else, it cannot read the notebook,
    and a name implying a personality would be the second thing in this app
    claiming to be an assistant while being the one that knows least about
    you. Its heading already read "Ask the guide", so the name was half
    chosen. One instance, not three: `openHelpChat()` moves the existing
    `#help-chat-group` into an `openSheet` and puts it back on close, because
    the chat is stateful (a running transcript, a form, three handlers bound
    by id) and a second copy would be a second set of ids. Reachable from the
    header's '?' on every tab and from the head the fifteen Settings panes
    share.

15. **The guide is called Atlas** (INBOX 204, the owner: "give the help ai a
    name fitting for the application like a persona and improve its
    capabillity and knowledge"). This supersedes decision 13's naming half,
    one day after it was taken, because the owner asked twice and "Guide" was
    the wrong answer both times: INBOX 190's "give it a fitting name??" was
    read as a request for a label, and a label is what it got.
    An atlas is a book of maps: the thing you open to find your way around a
    place you are already standing in, which is what this chat is for an app
    called Tessellate, and it is already drawn with a compass in the status
    bar. It also keeps decision 13's actual objection intact, which was never
    to names as such but to a name that claims a personality: a reference work
    has no personality to claim, does not pretend to know the reader, and does
    not imply it has read the notebook it cannot see. The voice in the system
    prompt is the same restraint the rest of this app's copy keeps: plain,
    sentence case, no greeting before the answer, and it says what it is when
    asked rather than inventing a character.
    The name lives in exactly two constants, `help_chat.GUIDE_NAME` and
    `GUIDE_NAME` in settings.js, and `tests/test_help_chat.py` asserts the
    word in the model's prompt is the word on the screen. A `guide` entry in
    `HELP_TOPICS` is what lets it answer "who are you" and "what can you do",
    which matched no topic at all before and so were answered "I'm not sure".

14. **The popup agent's own reach is the header, not seven docks** (INBOX
    190). The ask was "usable across the whole app"; the header is the one
    piece of chrome on every tab, a dock belongs to the surface under it, and
    seven copies of one control is seven places for it to drift and seven
    docks for two agents to conflict in. One wand, one '?', the chord in the
    tooltip. The starters are per tab (`AGENT_TAB_STARTERS`), which is where
    "depends where you are" belongs: the panel is the same everywhere and
    what it offers first is not.

11. **When no model is connected**, every AI control is visible, disabled,
    with a tooltip "Connect a model in Settings" and a one-click link;
    Ask falls back to search results with passages; nothing is hidden.

16. **A read-only note row draws the facts, not the actions** (INBOX 297).
   A search result, an Ask column record and any other row built through
   `clickableResult` gets `entryItem(entry, {facts: true})`: every fact the
   card states about the note (its category, tags, space, confidence, what
   it is linked to, whether it has no tags yet) is true of the note wherever
   it is drawn and belongs on the row. A chip that is really an action does
   not: "Tag with Atlas" starts a model call, and the "No tags yet" flag's
   handler opens the edit form in a list that is not on screen, so on a
   read-only row that flag is a fact with no handler. Measured before the
   decision: the same note drew five chips in Browse and two in Ask.

17. **The composed answer is the answer whenever no model runs, in Ask and in
   Chat** (INBOX 725, the owner: "the composer response should also be able
   to be viewed in chat messages", and "the ai still should be used as the
   chat bot when it is available"). A running model answers every Chat turn
   and every Ask turn unless From your notes is chosen; `_composed` is
   unchanged and the Chat tab's no-model branch composes in place of
   `extractive.answer`. Its chips are the composer's own next questions.

18. **The composer's layout** (INBOX 725, the owner: "you make the composer
   decisions"). The first line is the answer: the lead note named and its
   sentence on the same line; a list of short phrases said as one sentence
   ("lists four: A, B, C and D"), lowered to sentence case only when every
   entry is written that way; a checklist with how many are ticked; a broad
   question ("what do I know about") opened by "At least N of your notes
   mention", said of the notes found. The other notes follow joined by how
   they relate, never the same joining words twice running: "also" or
   "adds" for the question's subject, "Later, on" for a newer note on the
   same thread, "Separately" or "Elsewhere" for another topic, "But your
   newer note" for a pair that may disagree. One topic to a paragraph, two
   notes at most; a fact question (count, when, who, yes or no) brings at
   most two other notes.

19. **Meaning is the embedder's when it runs, shared words when not.**
   Cosine 0.9 is one claim said twice, 0.55 one topic; the lexical twins are
   Jaccard 0.6 and 0.12 over the words that are not the question's own. A
   repeated sentence is said once with "(Your notes say this N times.)"; a
   pair that differs in a figure or a "not" is never folded as a repeat. A
   broad answer's lead is the note named for the subject, else the sentence
   the others lean towards (TextRank weighted by score).

20. **Tried and not kept, from the brief's list.** "For example" as a joiner:
   nothing short of parsing tells a general sentence from an instance of it,
   and a wrong "for example" states a relation the notes never did. "Because"
   as a joiner: only a note's own "because" counts, used as a cue for why
   questions. Pronouns: only "It" or "Its" for the note just named. Fusion:
   only of a list's own entries, never two sentences into one.

21. **Next questions and follow-ups need no model.** A composed answer offers
   up to three: a tag two or more of the notes found share, a note found and
   not quoted whose best sentence scored at least half the best, and the
   question's own short subject asked the other way in time. "Tell me more"
   is the last question again with what it quoted left out; "the second
   one" is the second note the last answer named; a question whose only
   subject is "it" or "that" takes the last question's subject.

22. **With no model, Chat stays open and Agent mode closes** (INBOX 725, the
   owner: "if the composer can respond in the chat, should the chat input bar
   be enabled?? maybe agent mode should be disabled though unless needle is
   used to call tools without an ai"). The box and Send are not model-gated;
   the banner says Chat answers from your notes and what connecting a model
   adds. Agent mode is greyed with its reason unless the Needle extra is on
   disk (`/models/status` `tools_engine`), and then it runs on Needle and its
   title says so; the saved mode is never changed by the gate.

22a. **With no model, Agent is the engine first; Needle only for the rest**
   (INBOX 801 and 808, the owner 2026-10-11: "Should agent mode be enabled if
   the model isnt available??"). Decided from what the engine reaches: the
   time anywhere, a bare sum, the notebook's counts in any case, the notes on
   a topic, an act and "can you search the web?" are all answered with no
   model, so decision 22 stands: Agent stays live while Needle is on disk,
   its title says the app's own tools answer and a model does more, and with
   neither it stays greyed. Needle gets only a turn the engine has no answer
   for (`routes_chat._engine_answers`), is never offered `ask_user` or a
   tool that hands its work to a model, and its results are said as answers
   (`realise.tool_answer`). The thinking line says "Working it out without a
   model…", never "Waking the model…". The question is tidied before routing
   (`question_noise.tidy`), and every one-line tool argument loses stray
   keys (`agent._tidied_arguments`); a one-option ask is never shown and
   takes ask_user away for the turn.

## 5. Phases

### Phase 1: grounding and marks (one session; Brief 12)
Decisions 1 to 4. **Gate:** on the ten fixture questions, ≥ 95% of
supported sentences carry a mark to the right note (fixtures name the
note); a skill run cites the notes it read; hover highlights the passage;
"I don't know" appears on the two unanswerable fixtures.

**Built, all four gate lines and the replay tail, 2026-09-20 to 2026-09-23.**
Moved to HISTORY.md ("Moved from the plans, 2026-09-23", CHAT_PLAN.md): the
fixtures, the passage-scored attribution, the low-support notice and its
replay on a reopened turn, with every measurement.

### Phase 2: one composer, bubbles, streaming: **built 2026-09-13**, see
[HISTORY.md](HISTORY.md) "Moved from the plans, 2026-09-13". Gate green
(`scratchpad/ui-sweeps/chatphase2.js`), with one gate line superseded by the
owner's own later instructions and said so there.

### Phase 3: Ask unified, popup agent: **built 2026-09-13**, see
[HISTORY.md](HISTORY.md) "Moved from the plans, 2026-09-13". Decisions 8, 9,
11 and 12. Gate green in both halves it has
(`scratchpad/ui-sweeps/chatphase3.js` for the browser,
`tests/test_ask_answer_object.py` for the transport). One gate line was
superseded by the owner's own later instruction and re-run in that form: the
starters are decision 9's twelve **plus the current tab's two** (INBOX 190,
decision 14), so the sweep asserts 14 chips in 6 groups with the tab's own
group first.

### Phase 4: skills that finish (one session; Brief 13)
Decisions 10 and 10a to 10h. Built, 2026-09-12: see HISTORY.md, "Moved from
the plans", Brief 13. The harness items that were left with it are closed as
of 2026-09-20 (the `verify` control in the editor, the two audit skills that
had no check, `count_notes`'s filters, and the page-cap question, now decision
10h): see HISTORY.md, "Moved from the plans, 2026-09-20".

**The `evals` marker and its fixture set: built 2026-10-05**
(`tests/test_skill_evals.py`, the seventy-note loose-ends fixture with eight
planted in `tests/fixtures/chat/loose_ends.json`, and the zero-invalid-calls
count over the built-in skills; a fixture check runs in every suite). Run
once against Qwen2.5-3B-Instruct Q4_K_M (llama-server `-t 2`, four cores at
load 13 to 22, 55 minutes): "Find loose ends" named **2 of 8** (the dentist,
Priya) and one note that is not a loose end. Read from the run: the model
wrote `list_notes({...})` into its prose and then "I cannot execute the tool
call", so the paging never happened; that shape is now recovered as a call
for a read (`provider.extract_text_tool_calls`, pass 5). **Still open**: the
gate itself (8 of 8, and 80% of the skills with no invalid call) on a 3B
after that fix, and the built-in skills pass, which is hours on these cores.

### Phase 5: the composer, after INBOX 725 (open)
Left from INBOX 725, each its own step: (a) when a model runs, feed it the
composer's chosen sentences as context (the owner: "the composer can assist
the ai"); (b) run the 25-question eval with a real embedder and set the
cosine thresholds from it (decision 19's are reasoned, the lexical ones are
measured); (c) a "Your notes, no AI" label on a composed Chat bubble, as
Ask's chip has; (d) a picture attached as a file (`files` captions), not only
one inside a mostly-picture note; (e) re-capture the eval's retrieval when
search changes (`tests/fixtures/composer/showcase_725.json`); (f) "the
composer acts" (the owner: "or the composer can somehow call tools and act
like an agent"): deterministic commands parsed from a Chat message ("make a
reminder for X on Friday", "tag these notes Y"), shown as the action they
would take and confirmed before anything is written, the same confirm card
an agent's write uses; Agent mode then opens with no model for those verbs;
(g) link reasons beyond "similar in meaning" (the owner: "can the composer be
user to write better link reasons"): INBOX 691's concrete overlaps first,
then the composer's quoted sentence pair, a model's checked line when one
runs, feeding Tidy's "Add reasons" and "Add reasons to all". Open items and
numbers: agent-remaining/composer725-1006.md.

### Phase 6: the deterministic engine (the owner, 2026-10-10; Brief 39)

The owner's words: "I want the composer to basically be a mastermind, basically
an ai model, but not an ai model"; "more insights, some social and conversational
aspects, more response variation"; "stringing sentences together based off
meaning, similarity etc"; "it needs a very robust and full scale intelligence
engine"; "note timewords so it can be like, last Friday you did this"; "alter
personal words used in notes like my or I to you or your"; "Composer doesn't know
it is atlas"; "Note captions arent counted as note content"; "when I press ask
this question again, the composer doesn't change it up". Decisions 17 to 29 hold
(zero wrong facts, every sentence quoted or measured, light rule rewrites only).
What follows is the architecture that gets there; each decision is a step.

#### Decisions, 2026-10-10 (do not re-decide)

30. **A fact layer under the sentences** (`ai/factgraph.py`, new). From every
    source view, facts typed by rule, each with its span: event (verb lemma,
    object, time), quantity (number, unit, of what), date (absolute, or relative
    resolved with `when.py`), entity (person, place, organisation: capitalisation
    plus the taxonomy pack's entity and role seeds), list item, checklist item
    with its done state, decision ("decided", "going with"), preference ("I
    like", "prefer", "hate"), question, plan ("plan to", "will", "going to"),
    polarity by a 300-word lexicon with negation scope (no VADER; dropped if no
    tested feature uses it), topic candidates (the pack). A quoted sentence is
    grounded by its span; a measured sentence (count, span of dates, first and
    last, frequency, trend) is grounded by the facts it is computed from and
    marked measured. Both are decision 25's two allowed kinds.
31. **A query plan, not only a shape.** `classify()` becomes `plan()`: the
    answer kind (fact, list, timeline, comparison, count, yes or no, why, how,
    status, recommendation, recall by time, insight), the constraints (a time
    window via `when.py`, entities, tags, category, source kind), the length
    wish, and reference resolution against the dialogue state (it, that, the
    second one, the gym note). Each kind has a discourse schema: lead, support,
    contrast, gap, measured line, next questions. The schema decides the joins;
    the joins are never the same two running (decision 18).
32. **Insights are measurements with a fixed hedge, never claims.** "You have
    written about golf 4 times since August, three of them after work; that may
    be a hobby forming." The sentence is computed from facts (count, dates, a
    time-of-day fact); the hedge is one tested phrase and fires only on a rule
    (at least 3 mentions across at least 3 weeks); the line is marked measured.
    Insights close a broad answer and appear as one "Patterns" line in Tidy and
    the dashboard; they are never filed as facts. A lint: every insight
    template's slots are counts, dates or quoted spans.
    Amended 2026-10-10 (INBOX 764, decision 60): "never filed as facts" now
    reads "never filed as facts by the engine"; one the owner confirms is.

33. **Realisation by grammar rules** (`ai/realise.py`, new), not phrase tables
    alone: person shift with verb agreement ("I am" to "you are", "my" to
    "your", "I've" to "you have"), tense from the fact's temporal scope against
    today, number agreement, relative time ("last Friday", "three weeks ago",
    "yesterday") from the note's date against today, the pronoun rule of
    decision 20, sentence case after a comma fixed, titles never cut mid-word.
    Quotation is a renderer style (a quoted sentence is marked, not wrapped in
    quote characters, which broke grounding on the Gemini branch). Every rule
    has a table of input and expected output pairs as its test.
34. **Variation is session-salted.** `_pick()` takes the turn number and a
    per-chat salt as well as the question, so Ask again composes differently
    (the lead stays when one sentence is clearly best; openers, joins and the
    order of the other notes rotate; where scores tie, the second note may
    change). No template twice in a session (decision 25), measured by
    `lead_in_repeats` and `openers_distinct` over a 20-turn session in the eval.
35. **Dialogue state** (`FollowOn` grows into `Dialogue`): topic stack, notes
    already quoted (not quoted again unless asked), entities mentioned, the last
    answer's measured values, the person's corrections ("no, the gym note")
    which re-rank; carried in the request's history, no server state.
36. **Identity.** The engine is Atlas (policy 4 in ROADMAP's Direction). "Who
    are you" and about-app questions answer as Atlas; how-to questions take the
    help topics as their grounded source through a `voice="help"` register
    (composer-voice-1006.md), so the Guide and Chat are one engine. The bubble
    label reads "Atlas, from your notes" with no model and "Atlas, <model>" with
    one. The model, when it runs, is told the same identity and the same facts.
37. **Sources of every kind.** `NoteView` becomes `SourceView`: note, board (its
    texts), map (its nodes), document, picture caption (captions are content),
    and web page when web search is on (fetched text as sentences, cited by
    URL, shown as a scrollable source list inside the bubble). The source card
    says its kind and opens its own surface (INBOX 744).
38. **Acts.** `ai/commands.py` (on `wip/composer-acts`, 56 phrasings, not yet
    run) is finished: a command is parsed, shown as the action it would take,
    confirmed, run through the agent's own tool functions, undoable. Agent
    mode opens without a model for these verbs (decision 22). With web search
    enabled the engine may run the search tool and read results as sources.
39. **The engine explains.** One line per filing ("Filed under Fitness: shares
    gym, squat and protein with 6 notes there") and per link reason (Phase 5
    (g)) from the same fact layer; WORLD_CLASS_PLAN section 23 owns the filing
    decision.
40. **The bar.** The 25 showcase, the 90-question voice set and the noisy set
    stay; new fixtures: 40 insight questions, 30 twenty-turn dialogues, 30
    acts, 20 web-source questions, 30 mixed-kind sources. New metrics: measured
    sentences re-derivable from the fixture (1.0), variation across a session,
    answer-kind accuracy, person-shift correctness. Grounded stays 1.0 on every
    set on every build; a blind panel (the owner, decision 29) at the end.

#### Decisions 41 to 45 (Fable, 2026-10-10, from the assistant catalogue's five open questions)

41. **A computed sentence kind.** Utilities (arithmetic, unit and currency
    conversion, date arithmetic, word count and reading time, text transforms)
    answer with a sentence marked `computed`, the third allowed kind beside
    quoted and measured; the composer never discards an answer because no
    note row matched (the `if not out.rows` fall-through is the first bug).
42. **No archive verb in acts.** Archiving stays a UI action; the acts grammar
    has pin, delete (confirmed) and file. Fewer verbs, each certain.
43. **A dated, editable currency table.** Offline rates with their date, said
    in the answer ("at the rates from 1 October"), editable in Settings,
    Search and index; never fetched without the web toggle.
44. **The playful voice** follows natural and professional, not before; the
    owner reads samples first (decision 26 stands).
45. **The model picks among the engine's readings, never writes its own.**
    When a question is ambiguous the engine lists numbered readings; with a
    model running, the model chooses one (or asks); without one, the person
    is asked. The model reorders and selects; it does not add sentences
    (decision 17's handoff).

#### Built 2026-10-10 (Brief 39): see HISTORY.md "Moved from the plans, 2026-10-10 (CHAT_PLAN Phase 6)"

Steps 0 to 10, the first tests and the specification moved there whole, with
the numbers. Decisions 30 to 45 stay above: later briefs build on them.

#### Open from Phase 6 (one line each; the agent's ledger is `agent-remaining/engine-1010.md`)

- The blind panel (decision 40): the owner's rating against the 1 to 3B model on the owner's notebook.
- Probe P10, P11, P13, P15, P16 (`agent-remaining/engine-probe-1010.md`): days until a note's date, mention counts, every date and what is due, lead-ins chosen after the parts, a note's open checklist items.
- Probe P12: a list filtered by category or tag ("list my work notes").
- Captions in keyword search: the composer reads them, the FTS index does not.
- The currency table's Settings editor (decision 43); the rates are dated and fixed.
- The model choosing among the engine's numbered readings (decision 45): the readings are listed; with a model running it does not yet pick.
- Day and month order by locale in `when.py` (the 3/4 reading is day first).

#### Not verified until built
Polarity in the fact layer was dropped (decision 30's condition: no feature
asked for it). Not seen: the web sources list in a browser with a real search
engine, real models on the acts and the help register, contrast sweeps over
the new quote style and the act card. Real notebooks' pasted text, jokes and
quotes in the fact layer (INBOX 745 (b)) remain unmeasured.

## 6. Consistency rules

The answer renderer, the composer and the bubbles are one component each
used in three places; chips are `.library-chip`; menus the one recipe;
keys: Enter sends, Shift+Enter newline, Ctrl+K palette, Escape stops
streaming. No em-dashes in any generated copy either: the prompt asks the
model for plain punctuation.

## 7. Not verified until built

Threshold values for "supported" need the fixtures; passage highlighting
on notes with images; behaviour with a 1B model (it may not follow the
citation format at all, in which case marks come only from grounding,
which is the design anyway).

## 8. Research: what the reference products actually do, and what it changes here

Written from working knowledge of the products as of 2026, not from a
live teardown in this sandbox; where a claim matters to a decision, the
session that builds the phase should confirm it in the product first.

- **Perplexity** puts numbered marks inline at sentence ends, renders the
  source list as a horizontal strip of small cards above the answer (not a
  grid below it), shows "N sources" as a count you can expand, and offers
  follow-up questions as the primary next action. Its marks come from the
  model being asked to cite by number over a numbered context; the marks
  are therefore only as honest as the model. Implication: decision 2
  (grounding computed by us, by passage) is stronger than Perplexity's
  own mechanism for a small local model, and the strip-above-answer layout
  is worth copying for the sources disclosure (decision 4) because it
  keeps sources visible without a second page.
- **NotebookLM** cites by passage with an inline chip that opens the exact
  passage in the source pane; it refuses ("not in your sources") when the
  answer is not grounded. Implication: the hover-highlights-the-passage
  behaviour and the designed "I don't know" state are table stakes, not
  extras; the threshold in decision 2 should be calibrated so that
  refusal happens *before* a fabricated sentence, erring towards refusal.
- **ChatGPT, Claude.ai** composers: one field, a "+" for attachments and
  tools, a mode toggle, a send button; nothing else on the bar. Implication:
  decision 5 is the industry shape; the two-row composer is the outlier.
- **Obsidian Copilot, Smart Connections** (local-model chat over a vault)
  show the notes used as a list of links under the answer and let a note
  be inserted as `[[link]]`. Implication: the "Add answer to note with
  citations" action (§114 F2-4) belongs on the answer's action strip.
- **Raycast AI, Spotlight-style agents** win on quick actions because
  each starter is a verb with a slot ("Remind me to ___"), not a full
  sentence, and the panel remembers the last three used. Implication:
  decision 9's twelve starters should be verb-plus-slot chips, with the
  three most recent first.
- **Small-model reality**: a 3B model asked to cite by number over 17
  sources will drop marks or invent numbers; the eval fixtures must
  include this case so decision 2's grounding, not the model's marks, is
  what the UI trusts. Decision 10's "loop until the contract is met" is
  how Claude Code and similar harnesses behave; the missing piece in
  `skill_runner` today is paging inside the step.

## Placed from INBOX, 2026-09-09

172 (part). **Web links the AI writes, "better and more modern cool".**
Decided and built in Phase 3: decision 12 below. Both forms, chosen by where
the link sits.

The owner's reports this plan owns, moved whole from INBOX.md with their numbers (never reused). Each becomes a phase row when its phase is written; until then this list is the phase.

~~45. The Ask sub-tab.~~ **Folded into 63 and closed with it, 2026-10-05.**

### Found by an agent while measuring something else (2026-09-08, graph)

~~71. Web search panel, extraction UI, agent tools.~~ **Built; checked and
    finished 2026-10-05.** Moved to HISTORY.md, "Moved from the plans,
    2026-10-05 (CHAT_PLAN's placed items)".
~~72. Popup agent panel redesign.~~ **Built 2026-09-13** (`7002cd9`, INBOX
    126); moved to the same HISTORY block.
~~76. Inline citations accurate per sentence.~~ **Built 2026-10-05**:
    twenty answers, precision 26 of 26 and recall 26 of 26, and the popover
    names the matched words. Moved to the same HISTORY block.
~~80. Citation hover/click preview.~~ **Built 2026-09-26.** Moved to
    HISTORY.md, "Moved from the plans, 2026-09-26 (the Chat pass)".
~~90. User chat bubbles.~~ **Built; checked 2026-09-26.** Moved to
    HISTORY.md, "Moved from the plans, 2026-09-26 (the Chat pass)".
~~63. Redesign the Ask sub-tab, Write with the AI and Capture.~~ **Closed
    2026-10-05**, line by line against what renders: the last four lines
    built (a word count and reading time in Capture's foot, a word count on
    each Write pane, the draft in the body font, Escape clearing the Ask
    question), the rest built by earlier passes or superseded by a later
    decision of the owner's, each named. Moved to HISTORY.md, "Moved from
    the plans, 2026-10-05 (INBOX 63 and 45)".

## Placed from INBOX, 2026-09-09 (the owner's evening batch)

**All four checked built, 2026-10-05**, measured at head and moved to
HISTORY.md, "Moved from the plans, 2026-10-05 (CHAT_PLAN's placed items)":
the answer head on one 32px line, the Skills button inside the arranged
strip, the strip's two ends by the owner's own later layout, the panel's
shadow 2px by 8px against a 52.8px gap.

## Placed from INBOX, 2026-09-21 (the Ask sub-tab, four reports in one pass)

**All four built, 2026-09-21.** One pass, because they are one screen and
four separate fixes would have meant four rounds of the same measurement.
The probe is `scratchpad/ui-sweeps/asktab.js` (registered in
`scripts/gate.sh`'s sweep list); it measures rather than captures, and it
drives a real stream through `scratchpad/fake_answer_server.py`, which now
takes `FAKE_DELAY_MS` so a stream lasts long enough to poll. The full record
is in HISTORY.md, "INBOX resolved, 2026-09-21".

~~297. Gaps between an attached file and the badges, and badges that do not
all show.~~ **Built.** The gap: 0.0px to 6.4px, at 1440, 1024, 820 and 390.
The badges: not a truncation and not a wrap (every badge the data implies
was drawn at every width, none clipped, 0px of the lane scrolled out), but a
condition that never fired: `clickableResult` passed `entryItem` no options,
so every chip gated on `options.actions` was missing from a read-only row.
The same note: 2 badges in the Ask column before, 4 after, against 5 in
Browse, the fifth being the one chip decision 16 keeps off a result row.

~~298. No generating animation while the model is thinking and streaming.~~
**Built.** Frames with the answer actually streaming: 250 before, 0 of them
showing anything moving; 63 after, 63 of them showing something. Across the
whole turn: 120 of 372 before, 243 of 243 after. Two existing components
(`progressLine`, `.is-generating`) called from a surface that never called
either, not a new control.

~~299. Number the matching records to match the inline referencing.~~
**Built.** Records numbered: 0 of 5 before, 5 of 5 after, from
`citationNumbers`, the map the prose marks, the "Grounded in" chips and the
Sources panel already share. Marks whose row disagrees with them: 0. Numbers
drawn over a row's own text: 0 (6.4px of clear gutter on every row).

~~300. The sources button reads as a banner and describes a place.~~
**Built.** 525px of a 525px column (100%) before, 204px (38.9%) after;
"Sources: 5 notes, on the right" before, "Show the 5 notes used" after; and
a press now moves the first cited record from 328px below the top of the
window to 72px.

### The four reports, verbatim

297. **The owner, 2026-09-21, verbatim:** "in the ask subtab in notes, make
    sure there are appropriate gaps between uploaded files and attachments
    and the badges and make sure all the badges show."

298. **The owner, 2026-09-21, verbatim:** "there's no generating animation
    while the model is thinking and streaming in the ask tab either."

299. **The owner, 2026-09-21, verbatim:** "can the notes in the matching
    records that appear in the ask tab be numbered accordingly to match the
    inline referencing??"

300. **The owner, 2026-09-21, verbatim:** "fix the ui of this sources button
    in the ask tab."

## Placed from INBOX, 2026-10-03 (the chat stutter, INBOX 413)

Moved from INBOX whole when INBOX 433 arrived (the tray holds under
twenty). Open until the owner's next run reports it gone or not.

413. **The owner, 2026-09-24, verbatim, with a chat screenshot.** "I was in a
    document in the editor, I opened the suggestions panel and pressed check
    with ai, it took me to the chat and a popup above the chat suggested that
    there was a skill available for my requests, it wasnt entirely accurate
    so I closed it by clicking the 'x' on it and then the whole new chat page
    started viciously stuttering jumping up and down slightly really fast."
    Not reproduced headless (with real scrollbars, at 700 to 1048 tall, the
    dismiss gives one flip, not a loop). The one self-feeding path found is
    fixed: `fitChatEmpty` took its own class off to measure inside a
    ResizeObserver; it now reads stored heights with 4px hysteresis, and
    `#chat-messages` keeps a stable scrollbar gutter. Then the owner's log:
    "ResizeObserver loop completed with undelivered notifications", many a
    second, after opening and widening the web panel. The observer now only
    records the size; the fit runs a frame later, for changes of 2px or more,
    at most one flip per 500ms (`o-webpanel.js`: 0 loop errors, 1 flip across
    a 300 to 700px drag, 0 while still). Open until the owner's next run; the skill match being "not entirely accurate" is placed with
    the documents' Check with AI rework (INBOX 410).

## Placed from INBOX, 2026-10-05 (OPEN.md triage)

- Built 2026-10-05: Ask honours `grounding_live` (HISTORY.md, "Moved from the plans, 2026-10-05 (backlog-1005)"); the placed lists' triage pass and the question hover row ("... (op3-1005)").

## Placed from INBOX: the composer everywhere (the owner, 2026-10-06)

Verbatim: "I also want to use the composer basically really good sentence
model like an ai or apple's siri really smartly to improve quality of life
across the app. I need it perfect and I want to integrate it, like with the
companion message bubbles, or other things I havent thought of."

After INBOX 725 (the composer at chat-bot quality), one shared sentence
engine (`ai/composer.py`), the notes' own words joined by meaning, no model
needed, used wherever the app speaks:

1. **Companion bubbles**: what the companion says about the notebook (a
   resurfaced note, a pattern this week, a reminder due, an empty day) is
   composed from the notes, with its source one tap away; rate-limited, never
   twice the same, quiet when the person is typing.
2. **Dashboard greeting and digest**: today's line, the week in review and
   "on this day" written by the composer instead of fixed templates.
3. **Toasts and confirmations** that name the thing ("Moved Passport renewal
   to the bin; it was linked to 3 notes").
4. **Search and Find anything**: a one-line answer above the results when the
   query is a question.
5. **Note and document helpers**: a summary line on a long note, "what links
   these two notes" on a link, a title suggestion from a note's own words.
6. **Reminders and meetings**: the action items and decisions read back as
   sentences; a reminder's notification says why it matters, from its note.
7. **Tidy and filing**: every reason ("filed under Work because…") in one
   voice.

Rules: the 725 constraints (every fact quoted or measured, a fixed tested
phrasebook, offline, deterministic) hold everywhere; one style guide for the
app's voice in DESIGN.md; each surface gets a measured eval like 725's.

Addenda, the owner, 2026-10-06, verbatim: "also the composer could be used to
write better and cheaper followup questions, suggested search results, auto
fills, suggested stuff and more"; "the composer can assist the ai and
complement features"; "the ai still should be used as the chat bot when it is
available". So:

8. **Cheap suggestions**: follow-up questions, suggested searches, autofill
   (titles, tags, reminder wording, link reasons) composed first; a model is
   asked only where it adds something the composer cannot.
9. **The composer assists the model, never replaces it**: when a model is
   running it is the chat bot; the composer supplies the grounded material
   (the selected sentences, their order, the measured values) as the
   model's context, checks the model's answer against the notes, and fills
   in instantly while the model streams. With no model, the composer answers
   on its own (INBOX 725).

**North star for the composer** (the owner, 2026-10-06, verbatim): "I want the
composer to be soooo good that users dont even need to install ai ... some of
my friends dont like ai and probs wont want to install a local model so I want
it to be the best and most capable and well spoken, coherent, well made
composer the world has seen." Next session: the Phase 5 rows and
`agent-remaining/composer725-1006.md` (link reasons from sentence pairs, the
composer feeding a running model, "the composer acts"), each measured on the
725 eval. The owner may run this phase with a Fable planning pass later, by
their own call when usage allows (standing order 4 bars Fable agents unless
the owner says otherwise).

10. **The composer writes for the model and the agent, not only for the
    person** (the owner, 2026-10-06, after reading one of this harness's own
    templated system notices: "maybe the composer could be used to help
    streamline, and assist in agent tasks and ai tasks and responses??").
    Deterministic, templated text where a small model is weakest:
    - **Context packs**: the notes a model reads arrive as a composed brief
      (who, what, when, the measured counts, quoted sentences with ids), not
      raw note dumps; fewer tokens, less to misread.
    - **Tool results**: each agent tool's result is summarised in one fixed
      shape ("Done: tagged 3 notes #trip. Not done: 1, it is private.") so the
      model's next step reads a clean state, and the person sees the same line.
    - **Guard notices**: the agent's own rails (what it may not do, what needs
      confirming, what came from a note rather than the person) as fixed,
      tested wording, the way this harness frames external content.
    - **Progress and run digests**: the Agent activity panel and run history
      written by the composer from the run's events.
    Measured on the agent evals (`pytest -m evals`) with a small local model:
    task success and tokens per task, before and after.

11. **A notebook that reads as written for you** (the owner, 2026-10-06,
    verbatim: "the composer could even be used to customise notifications,
    make the dashboard and other features mroe dynamic and customised and
    more"). Notifications name the note and why now ("Passport renewal is due
    Friday; your trip note says you fly on the 14th"); the dashboard's
    greeting, glance and widgets order and word themselves from what the
    person did this week; empty states, Tidy, Timeline and Reminders say
    something specific instead of a fixed line. One rule: every sentence is
    still from the notes or a measured value, and the person can turn the
    personal wording off.

**Decision, the owner, 2026-10-06, verbatim:** "ai should still be the core
when it is available, but the composer should be used to lessen the load,
refine and betetr the responses and results, assist and complement, as well
as cheapen the run cost of the ai". Every item above is held to it: with a
model running, the model answers; the composer prepares its input (item 10),
checks and refines its output against the notes, answers the cheap parts
itself (counts, dates, lists, follow-ups, suggestions) so the model is called
less and with shorter prompts, and fills the screen while the model streams.
Measured as model tokens and calls per task, before and after, with answer
quality held or better.

### Composer decisions, taken with the owner, 2026-10-06

23. **Light rewrites, marked.** Without a model the composer may fix grammar,
    tense and person ("I" to "you", "b4" to "before") by fixed, tested rules;
    the original wording is one tap away. No free rewriting.
24. **No answer is said plainly.** "Nothing here says that. The closest is X",
    plus a suggested question the person could answer with a note.
25. **The bar is all four, each measured:** a blind test of composer answers
    against a 1 to 3B local model on the person's own notes; zero wrong facts,
    every sentence traced to a note or a measurement, tested on every build;
    sounds like a person (varied phrasing, no template repeated in a session);
    does things, not only answers (reminders, tags, links, summaries from a
    request, each confirmed first).
26. **Voice: Atlas's by default, changeable.** Warm and brief in openings and
    companion bubbles, plain in answers; a setting offers plain and playful
    too, each with its own phrasebook and tests.
27. **Notes are a mix**: the eval weights short jottings (rewrites, joining)
    and long writing (summaries, choosing the sentence) equally.
28. **Proactive, rarely and on real signals**: a few times a day at most, only
    for something specific (a due reminder, a resurfaced note, a pattern),
    never while the person types.
29. **The blind test is both**: a fixed sample notebook on every build, and
    the owner and a few friends rating on their own notebooks now and then.


## Placed from the owner's list, 2026-10-10

Entries are the owner's words, then the recommendation. Bugs come first, then design requests, then ideas.

### Bugs

- "on the guide the thinking shows below the thinking indicator and stuff" / "with no gap either"
  Recommendation: measure the gap between the thinking indicator and the thinking text in the guide, then give the text the spacing token. No brief carries it; Brief 37 (chat bugs) is the nearest.
- "should that no chats text be at the top not the bottom??"
  Recommendation: place the empty-chat text at the top of the list and measure its position in the empty state. No brief carries it; Brief 37 is the nearest.
- "the "start searxng" button doesnt appear for a while"
  Recommendation: show the SearXNG start control as soon as the web engine is found down, not after the status poll. No brief carries it; Brief 37 (web sources and retry) is the nearest.
- "the notification said it takes a while to pull the first image for searxng but ive already used multiple times"
  Recommendation: show the first-pull note only when the image is absent, checked before the message is written. Also carried by Brief 37 (web sources and retry).
- "I pressed the "ask about this" button and it put it in the chat but I was on "ask" mode, shouldnt it have been auto put on "agent"??"
  Recommendation: the ask-about-this action switches to agent when the model and tools allow it, and says why when they do not. Also carried by Brief 37 (model gating, CHAT_PLAN decision 22).
- "why is the token window limit for this model soooo low :("
  Recommendation: show the model's real context limit and the reason for it in the token pill. Also carried by Brief 37 (token pill popover).
- "I tried to ask for more info from the retrieved website in the previous prompt and it just straight up ignored me and started talking about my notes"
  Recommendation: a follow-up about the last retrieved page reuses that page as its source. Also carried by Brief 37 (web sources) and Brief 39 (dialogue state).
- "also I just asked another question, didnt like the response so I deleted it, and now somehow the token usage I was at for that chat has lowered??"
  Recommendation: count tokens from the turns that still exist and show the change when a turn is deleted, then measure the figure before and after. Also carried by Brief 37 (token pill popover).
- "not every chat response needs to be related to notes if it is othe rthings about the application."
  Recommendation: questions about the app are answered from the engine's app facts (Help and settings), not from the notes. Also carried by Brief 39 (acts and explanations).
- "no way to clear the destination history or delete individual records??"
  Recommendation: add clear-all and per-record delete to the destination history. Also carried by Brief 37 (histories cleared).
- "a whitebaord showed as a note in the notes ask subtab matching records column"
  Recommendation: each match carries its kind (board, map, note, document) and the Ask subtab labels it. Also carried by Brief 37 (source kinds).
- "it got jokes from another note but not the separate one from the top of the matching records"
  Recommendation: an answer names the note each claim came from, so the joke's source is visible and checked. Also carried by Brief 39 (grounding per source).
- "I can still activate skills and the suggested skill popup still appears when I have no model running." / "The ai model isnt running, skills are disabled, and it still suggests skills"
  Recommendation: no skill suggestion or activation while the model is off or the tools toggle is off, with a test for each state. Also carried by Brief 37 (model gating, CHAT_PLAN decision 22).
- "Its still allowing me on agent mode even when the ai model isnt connected"
  Recommendation: agent mode is disabled with its reason when no model is connected. Also carried by Brief 37 (model gating).
- "I pressed show them, but it just navigated me to the Ask subtab on the notes tab as that was what I was just on in the notes tab and not to the "you notes" tab"
  Recommendation: "show them" opens the Your notes subtab, whatever subtab was last open. No brief carries it; Brief 37 is the nearest.
- "Hovering over an intext reference opens up the sources dropdown."
  Recommendation: hover shows a short preview of the source and a click opens the sources. No brief carries it; Brief 12 (per-claim citations) is the nearest.
- "Note captions arent counted as note content??"
  Recommendation: captions join the retrieval text and the fact layer, with a fixture that a caption-only fact is found. Also carried by Brief 39 (fact layer).
- "Issues with these sentences: The picture in Girl with bell shows The image shows a snowy scene with a girl holding a bell, and there is a signature at the bottom left that reads "24-12-2018"" (and the Leafeon sentence that follows it in the list)
  Recommendation: the composer states what a picture shows only from its stored caption, and labels it as one. Keep both pasted outputs as the fixture for the check. Also carried by Brief 39 (realiser, grounded 1.0).
- "These notes do not mention “summarise”."
  Recommendation: a claim with no source note is dropped before the answer is written, with the summarise case in the grounding fixture. Also carried by Brief 39 (grounded 1.0 on every set).
- "I think a lot of composer responses start with "ah,"??"
  Recommendation: the opener set loses the repeated "ah," and is checked by openers_distinct over a 20-turn session. Also carried by Brief 39 (openers_distinct, lead_in_repeats).
- "The composer is shit and I don’t like it, it needs soooo much improvement" / "Still ass composer"
  Recommendation: this is the composer quality bar; measure it on the eval sets rather than on impressions. Also carried by Brief 39.
- "I tried to press "a note" on the slash menu in the chat tab and the panel flickered then nothing happened" / "Same with the other options like "a document""
  Recommendation: each slash-menu item in the chat tab opens its composer target or says why it cannot. No brief carries it; Brief 37 (chat bugs) is the nearest.
- "There's no way to clear your ask history"
  Recommendation: add clear-all to the Ask history, with the same control as the destination history. Also carried by Brief 37 (histories cleared).
- "Do plan and web search work with the composer?? if not we should disable the plan button and if the user asks the composer to search the web, it can like pull the contents into a like rendered panel inside the chat bubble like a rendered pdf file for the user to access, or a scrollable list of websi"
  Recommendation: Plan is disabled with its reason when web tools are off, and a web request opens the fetched pages in a rendered panel in the bubble. Also carried by Brief 37 (web sources) and Brief 39.

### Design requests

- "Composer chat messages in the chat and other interfaces should say if the composer or a specific ai model generated it"
  Recommendation: every composer bubble carries a label naming the engine that wrote it. Also carried by Brief 39 (the bubble label) and Brief 37 (composed bubble label).
- "Composer responses just appear, I think there should be an animation or smooth transition."
  Recommendation: a short fade-in with a reduced-motion check, measured on the bubble's opacity over time. Also carried by Brief 37 (composed bubble fade).
- "Ask subtab responses need to have better hierarchy with their sentence connectors."
  Recommendation: headings, paragraph breaks and connectors are styled as one scale, measured on a sample answer. Also carried by Brief 39 (the realiser's structure).
- "It just uses arrows to go between key sentences and doesn’t join or smoothly write it out at all"
  Recommendation: the realiser joins key sentences into prose with connectors instead of arrows. Also carried by Brief 39 (realiser).
- "Also the composer should probably use better md rendering and structuring, quotation marks, as well as alter personal words used in notes like "my" or "I" to "you" or "your"/"you're" etc"
  Recommendation: the realiser turns the note's first person into second person and renders the answer's Markdown and quotation marks properly. Also carried by Brief 39 (the quotation style and the realiser).
- "Also the composer should note timewords so it can be like, last Friday you did this… etc"
  Recommendation: time words in the question and the notes ("last Friday") resolve through when.py into a dated sentence. Also carried by Brief 39 (when.py).
- "I want the composer to be more like a chatbot and not just somenthing that reads out my notes,as I can clearly see them in the right column"
  Recommendation: the composer answers in its own voice and does not repeat what the right column already shows. Also carried by Brief 39.
- "also when I use the composer and press "ask this question again" to get a new ai response, the composer doesnt change it up. I want the composer to basically be a mastermind basically an ai model, but not an ai model?? or maybe a neural network that doesnt rely on an external ai software it is basically an ai alternative without being an ai model?? idk just throwing ideas out there."
  Recommendation: "ask this question again" yields a different deterministic phrasing and different evidence order, measured by repeat distance over three regenerations. Also carried by Brief 39 (response variation).
- "the composer should have more insights, some social and conversational aspects, more response variation. more stuff than just lkisting my notes back to me in a list"
  Recommendation: add the social and conversational acts to the engine's act list, each with a test. Also carried by Brief 39 (acts).
- "t needs more social and world and word understanding, needs to understand mroe typos, needs better and mroe verything"
  Recommendation: extend the typo, synonym and social tables under the eval, with the grounded and first-line numbers reported. Also carried by Brief 39 (typo and world tables).
- "this is confusing?? I want a better chatbot. is there any more magic we can do?"
  Recommendation: the bubble explains which engine answered and what it did; the chatbot feel comes from Brief 39, not from a model. Also carried by ROADMAP Direction (the thesis: two engines, one answer).
- "Composer doesn’t know it is atlas?? Should the composer be distinct from atlas??"
  Recommendation: one voice, named Atlas, with the composer as its deterministic engine (Direction policy 4). Also carried by ROADMAP Direction policy 4 and Brief 39.
- "sounds good! but only if the suer has web search and the tools enabled." (the owner's feedback in the Gemini thread, on the web-aware composer)
  Recommendation: the composer searches the web only when web search and the tools are both on, and says so otherwise. Also carried by Brief 37 (model gating) and Brief 39.
- "I just want it to do its job, and I dont want to change the ai, just improve and fix the deterministic composer." (the owner's feedback in the Gemini thread)
  Recommendation: keep the composer deterministic and do not put a model into its writing; Brief 39 improves it under the eval. Also carried by ROADMAP Direction policy 4.
- "I don’t like the genz version, remove It and expand the composer more. It needs a lot of fixing, expanding, and refining."
  Recommendation: remove the Gen Z voice and its settings in the Gemini branch triage, then expand the composer under Brief 39. Also carried by Brief 35 (Gemini branch triage) and Brief 39.
- "Also if I click the "not about [this tag], don’t show this again", is there a way to undo it or see the list of things not to show again for specific things or stuff??"
  Recommendation: an undo toast and a list of suppressed suggestions in settings. Also carried by Brief 37 (suppressed suggestions list) and Brief 39b.

- "there should be a retry button for failed web searches and/or a button to auto retry when searxng or another engine is available."
  Recommendation: a retry control on each failed web result, and an opt-in auto retry when the engine answers its health check. Also carried by Brief 37 (web sources and retry).
- "also should accessed web links in the sources dropdown be lised at the top of the sources??"
  Recommendation: sort accessed web links to the top of the sources dropdown, and check the order in the sweep. Also carried by Brief 37 (source kinds).
- "when I click the token window button pill, i expect to see a dropdown to see my token distribution stats, not it to be a button to compact the conversation. both functions need to show some better way"
  Recommendation: the pill opens a token distribution dropdown, and compacting moves to a button inside it. Also carried by Brief 37 (token pill popover).
- "Intext reference should be square brackets or styled differently."
  Recommendation: in-text references use square brackets or a styled marker, measured in the answer sweep. No brief carries it; Brief 12 (per-claim citations) is the nearest.

### Ideas

- "I want the composer to be more integrated, have more abilities, utilities, functions, and more."
  Recommendation: the composer's tool list is the engine's act list (CHAT_PLAN Phase 6); each new ability needs a test and an eval row. Also carried by Brief 39.
- "could it have insights?? like with my note about hitting some golf balls after work could imply I may enjoy playing golf or have it as a hobby?? stuff like that. it needs a very robust and full scale intelligence engine."
  Recommendation: insights are a fact-layer rule (a note implies a hobby) that the answer may state with its source. Also carried by Brief 39 (insights, ROADMAP Direction track 5).
- "can you improve on and expand it further?? cover any flaws, optimise, enhance. impress me."
  Recommendation: this is the composer's brief at large; it is Brief 39's scope, measured against the eval. Also carried by Brief 39.
- "should we store recently retrieved website content for easy reretieval??"
  Recommendation: keep fetched page text with its fetch time and a re-fetch control, and show it in the sources list. No brief carries it; Brief 37 (web sources) is the nearest.

## The assistant catalogue, 2026-10-10

The owner: "the app needs to be the best thing the world has seen without the
ai and then even better, universal, if the ai is available." This section is
the research and specification behind CHAT_PLAN Phase 6 (Brief 39): what the
best rule-based and offline assistants do, every capability the deterministic
engine should have, how a model joins it, the eval sets, and what to build
first. It decides nothing that decisions 17 to 40 already decided; where it
extends them it says "proposed" and the orchestrator takes or drops it.

How to read it. Costs are S (under about 60 lines and a table of input and
expected output pairs), M (a new table or one function with its own test file),
L (a module or more than one step). "Step" is Phase 6's step number (1 fact
layer, 2 plan and time windows, 3 realiser, 4 salt and dialogue, 5 sources,
6 insights, 7 acts, 8 identity and help, 9 web, 10 evals); "new" means the row
needs a step Phase 6 does not list, and is placed in the nearest one.

### 0. Checked in the code, 2026-10-10

Method: `compose()` driven directly with a one-note notebook ("Gym on Friday.
Squat 100kg. Need to buy protein.") and 37 questions, plus `grep` of
`ai/composer.py`, `intent.py`, `notebook_stats.py`, `when.py`, `timetravel.py`,
`facts.py`, `help_chat.py`, `tools/__init__.py`, `entry/query.py`,
`entry/timewords.py` and the routes, on the working branch (b6c3f3965). Counts
that the tables below rely on: 67 agent tools (33 write), 121 help topics, 15
social kinds with 20 to 35 lines each, 847 slang entries, 250 social words and
227 social phrases, 148 synonym groups, 950 phrases, 15 question shapes.
`compose()` is reached after `intent.classify`, `notebook_stats.answer` and
(with `as_of`) `timetravel` in `routes_chat.py`, so a question those handle is
not a gap even when `compose()` alone fails it.

Found, not fixed (this task writes no code; each is a first test for Phase 6
step 2 or Brief 35):

1. **The Gemini branch's utilities never reach the screen.** The `utility`,
   `math`, `convert`, `reading_time` and `translate` branches
   (`composer.py` ~2706 to 2790) write a message with `out.m(...)` but add no
   grounding row, and `if not out.rows: return _nothing(...)` then replaces it.
   Measured: "what is 12 * 7", "what time is it", "how many 5 km in miles",
   "set a timer for 10 minutes" and "remind me to call mum on friday" all
   answer "Nothing in the notes found answers that." The last two would also
   have claimed "I've noted your request" without writing anything, a wrong
   fact by decision 25 had they displayed.
2. **The `translate` rule swallows ordinary questions.** The pattern at
   `composer.py:292` ends in `to\s+([a-zA-Z]+)\b`, so any question containing
   "to <word>" is a translation and none of the later rules run. Measured as
   `translate`: "what do I need to buy", "how to cook rice", "what if I move to
   Lisbon", "convert 5 km to miles" (which therefore never reaches `convert`).
3. **"summarise my gym notes" raises `UnboundLocalError`** (`sides` is set only
   on the non-summary branch, `composer.py` ~2795).
4. **No rule at all for**: "15% of 80", "20 percent of 50" (shape `what`),
   "3 times 4" and "how many days until Christmas" (shape `count`, no answer),
   "what day is 3 weeks from now" (shape `when`, no answer), "roll a dice",
   "flip a coin", "word count of this", "what is due", "what changed this week",
   "what contradicts". The tools exist for the last three (`list_reminders`,
   `find_contradictions`) but only a model reaches them.
5. **A correction is read as a new question.** "no, the gym one" is classified
   `list` and answered with the quoted sentences; `follow_on` has `more`,
   `ordinal`, `meant` and `it`, and no `correction` (decision 35 owns it).
6. **`ai/tool_summary.py` does not exist**, and `ai/commands.py` exists only on
   `origin/wip/composer-acts` (626 lines, 56 phrasings, never run); Phase 6
   step 7 and decision 10 (one fixed result line per tool) both lean on them.

### 1. What the best rule-based and offline assistants do

Sources were read with WebFetch on 2026-10-10. Where a page gave only titles or
did not describe a mechanism, the row says so rather than filling the gap from
memory. "MemoryMap has it" is checked against the code (section 0); "Partial"
names what exists. The columns are capability, what it does well, mechanism,
what it means here, whether Tessellate has it, and cost.

#### ChatScript (pattern and topic engine)

Source: https://github.com/ChatScript/ChatScript/blob/master/WIKI/ChatScript-Basic-User-Manual.md
(the page does not describe spell checking or a POS pipeline).

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| Concept sets, nestable | One rule covers every wording of an idea | `concept: ~name [words]`, `~name` in patterns | Synonym groups become named concepts the planner, the fact layer and acts share ("~reminder_verbs") | Partial: 148 groups plus extras in `composer_tables.py`, `_build_synonyms`; flat, not referenced by rules | S per pack |
| Canonical forms before matching | Rules are written once | Contractions expanded, number words to digits, plurals to singular, verbs to infinitive, interjections and texting remapped | One `normalise()` stage ahead of `plan()` that every rule reads | Partial: Porter `_stem`, 11 contractions, `question_noise.repair`, SLANG 847; number words become digits only inside `when.py`, `timewords.py`, `reminder_parser.py` | S |
| Topics with keywords, pending topics | Many turns on one subject without a model | Topic keywords route input; the old topic is held pending | Dialogue topic stack (decision 35) | Partial: `FollowOn` (more, ordinal, meant); no stack | M |
| Rejoinders | A reply to the bot's own question is understood in that context | Nested rules fire only on the reply to that rule's output | Each next-question chip carries the rule it answers; "yes" after a clarifying question means the first option | Partial: `_did_you_mean` chips, `meant`; a bare "yes" or "no" is small talk | S |
| Gambits marked used | Never says the same thing twice | A used flag per rule per user | Decision 34 as a per-session used set, not only a salt | Partial: `_pick` salts by question and `previous` opener | S |
| Persistent and per-turn variables | Remembers what the person said | `$name` persists, `$$name` lasts a volley | `Dialogue.entities`, corrections, "my gym note" aliases, carried in the request history | No | M |
| Pattern operators (`!`, `<< >>`, `*n`, `[ ]`) | Precise rules for ambiguous phrasing | A pattern language | Not adopted as a language: regex tables with a test row per phrase are the same power and already the house style | Equivalent: 15 `_SHAPE_RULES` | none |

#### AIML and ALICE

Source: https://www.pandorabots.com/docs/aiml-reference/

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| `srai` reduction | Thousands of phrasings, one answer | Rewrite the input and match again | `rephrase()` stripping wrappers and trailers, then re-plan; also the typo and slang route | Yes: `composer.rephrase`, 35 trailers, `question_noise` | none |
| `that` and `thatstar` | "yes", "no", "the second" mean something | Match only if the bot's previous sentence matches | Answer short replies against the last answer's open offer | Partial: ordinal and "did you mean"; no yes or no | S |
| `person` and `person2` | I to you, with the substitutions in one file | Pronoun swap table | Step 3's person shift, with verb agreement | Partial: `_rewrite_quote`, 17 rules, no agreement ("Sam and I" becomes "Sam and you") | M |
| `random` and `condition` | Variation and state-dependent lines | Uniform pick; if-then on a predicate | Salted pick (34); the discourse schema table | Partial: `_pick` | S |
| `set` and `get` | Remembers a name across turns | Predicates | `Dialogue.entities`; "call me Sam" is a preference (7 below) | No | M |
| `normalize` and `denormalize` | Same text in and out | Substitution files in both directions | The realiser restores punctuation and quotation style after normalisation | Partial | S |

#### Rasa rules and forms

Sources: https://legacy-docs-oss.rasa.com/docs/rasa/rules and
https://legacy-docs-oss.rasa.com/docs/rasa/forms (the pages redirect there).

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| One-turn rules | A greeting is answered the same way anywhere | `rule: intent, then action`, always followed by listening | The social acts (15 kinds) as rules, each a test row | Yes: `composer.social`, `question_noise.social_kind` | none |
| `conversation_start` | A rule that only applies on the first turn | Condition on the conversation | The first turn of a session greets by time of day; later turns do not | No | S |
| Forms and required slots | An act missing its object or time asks for exactly that | `required_slots`, `utter_ask_<form>_<slot>`, validation returns None to ask again | Acts grammar (38): "remind me to call mum" asks "When?" with chips for today, tomorrow, Friday | No (`commands.py` on the wip branch parses, never run) | M |
| Interruption and resume | A side question does not lose the half-filled act | `active_loop`, `ActionExecutionRejection`, rules to return | `Dialogue.pending_act` survives one unrelated turn | No | M |
| Deactivate on "never mind" | The person can leave | `action_deactivate_loop` | "cancel", "never mind", "forget it" clear the pending act | No | S |
| `requested_slot` explains why | "Why do you need that?" answered per slot | A categorical slot that influences the next action | One explanation line per clarifying question | No | S |
| Limit named by the docs | Rules do not generalise; do not overuse | Rules plus stories | Every rule here lives in a table with an eval row, so growth is measured, not hand-fed | n/a | none |

#### Mycroft Adapt and Padatious

Sources: https://github.com/MycroftAI/adapt, https://github.com/MycroftAI/padatious,
https://mycroft-ai.gitbook.io/docs/mycroft-technologies/adapt (these pages do
not document Adapt's confidence formula, `one_of`, context handling or Padatious'
treatment of typos; only what is stated is used).

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| Intent = required plus optional entities | Small, explicit, offline, Apache-2.0 | `IntentBuilder.require(...).optionally(...)`, returns intent, confidence and tagged entities | `plan()` picks the kind from required cue words and optional ones and returns a confidence so a weak plan asks | Partial: first-match `_SHAPE_RULES`; `question_noise.guess_kind` (trigram floor 0.40, embedding 0.62, margin 0.06) when no rule fires | M |
| Vocabulary registered from the user's data | Station names come from the user's account | `register_vocab` at runtime | Tags, categories, titles, people and places become vocabulary for object resolution in acts and for typo repair | Partial: `_fit_terms` and `Did you mean` repair against the notebook's words | S |
| Example-sentence intents with `{entity}` slots | Adding an intent is writing five sentences | Padatious trains a small network on examples | `question_noise.EXAMPLES` already is this by trigram match; an act is added by adding example rows, with no network | Yes for question kinds; no for acts | S per act |
| Intents are independent | Changing one does not break another | Separate models per intent | A test row per intent, run in the eval, catches cross-talk (finding 2) | Partial | S |

#### Snips NLU

Sources: https://snips-nlu.readthedocs.io/en/latest/ and
https://snips-nlu.readthedocs.io/en/latest/data_model.html (the overview page
does not explain its pipeline; the data model page was read).

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| An implicit None intent | Knows what it does not know | Any input matching no intent is classified None | A measured out-of-domain class: weather, sport scores, "what is the capital of France" answered by decision 24's plain no-answer, with an eval group | Partial: `_nothing`; no out-of-domain score or set | S |
| Slot = type, name, raw value, range | Every extracted value has a span | `rawValue`, resolved `value`, `range` | Fact schema's `start`, `end` and `attrs` (decision 30) | Planned (step 1) | L |
| Built-in resolved entities (datetime, number, temperature) | "tomorrow at 10am" becomes a timestamp | `snips/` entities with resolution | `quantity`, `duration`, `money`, `date` facts, resolved with `when.py` and a units table | Partial: `when.py` 378 lines, `timewords.py`; no quantity or money | M |
| Custom entities, synonyms, `automatically_extensible` | Closed lists reject unknown values, open lists accept them | Flag per entity | Tags and categories are closed (an unknown one asks "Did you mean"); people and places are open | No | S |
| Intent first, then slots | Two small problems | Classifier, then slot filler | `plan()`: kind, then constraints | Planned (step 2) | M |

#### ELIZA

Source: https://en.wikipedia.org/wiki/ELIZA

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| Ranked keywords, decomposition and reassembly | A reply built from the person's own words | Keystack, highest rank wins; fragment around the keyword, reassemble from a template | Reflective next questions from the person's note ("You wrote about the move on 3 March; what came after?") | Partial: `_next_questions` (tag, leftover note, the question the other way in time) | S |
| Pronoun reflection | "my" becomes "your" | High-rank substitution words | Step 3 | Partial: `_rewrite_quote` | M |
| Memory queue | When nothing matches, recall an earlier remark | Statement stored after the keyword "my", recalled later | When a question matches nothing, offer the person's own earlier note on the nearest subject, labelled | No | S |
| Content-free fallback ("please go on") | The known failure: users over-trust it (the ELIZA effect) | Generic remark when no keyword | The opposite rule: never a content-free reply; decision 24's no-answer names the closest note and says which engine answered | Yes by decision 24; label is step 8 | none |

#### Wolfram Alpha (computable answers)

Sources: https://www.wolframalpha.com/examples and https://www.wolframalpha.com/tour/
(neither page describes how assumptions or alternate interpretations are shown,
so that row is this plan's own rule; the tour page says answers come from
curated data and over 50,000 algorithm types).

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| Domains as calculators: elementary math, units and measures, dates and times, words and linguistics, money and finance, food and nutrition, household math | One box, many tools | Curated data plus algorithms | A small set of owned calculators (section 2, utilities): arithmetic, percent, units, dates, word counts. Not nutrition or finance data | Partial: Gemini-branch `math`, `convert` shapes exist and are invisible (finding 1) | M |
| Show how the input was read | The person can catch a misreading | An interpretation line before the answer | Proposed rule: every utility answer opens "Read as: 15% of 80." and is marked measured | No | S |
| Step by step (Pro) | Shows work | Solver steps | A measured line shows its operands ("80 x 0.15 = 12") | No | S |
| Surprises and household categories | Playful, specific answers | Curated examples | Humour by rule (section 2, conversing) | No | S |

#### Siri Shortcuts and Google Assistant routines

Sources: https://support.apple.com/guide/shortcuts/welcome/ios and
https://support.google.com/assistant/answer/7672035

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| Ordered actions with content flowing between them | A recipe, not a prompt | Get, Transform, Share groups; output feeds the next action | A saved act sequence ("my Friday review": find this week's notes, summarise, make a reminder) run with no model, each step a tool | Partial: agent skills run through `skill_runner`; none run by rule | M |
| If, repeat, choose from menu, ask for input | Branching and clarifying | Control-flow actions | Clarifying question with chips is "choose from menu" | Partial: chips | S |
| Triggers: time, event, arrival | Runs by itself | Automations and starters; one non-voice starter per routine | Scheduled acts and the proactive line (decision 28), capped at a few a day | Partial: reminders with `recurring` none, daily, weekly, monthly (`routes_reminders.py`); no scheduled act | M |
| Run from anywhere | One recipe, many doors | Siri, widget, search, URL scheme | The engine behind the header wand, Find anything, the dashboard (composer everywhere 1 to 7) | Partial: `composer_voice.py` built, routes and UI not | L |
| Security-sensitive actions unavailable | Safe by default | Routines refuse unlock and two-factor actions | Delete and bulk acts always confirmed with a preview (38) | Yes for agent writes; not for composer acts | S |

#### Alexa skill design

Sources: https://developer.amazon.com/en-US/docs/alexa/alexa-design/get-started.html
(titles only: Be Natural, Be Brief, Be Contextual, Be Trustworthy; the pattern
pages on errors were not readable),
https://developer.amazon.com/en-US/docs/alexa/custom-skills/standard-built-in-intents.html,
https://developer.amazon.com/en-US/docs/alexa/custom-skills/dialog-interface-reference.html

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| Built-in conversation controls | Every skill answers "help", "stop", "repeat", "start over", "next", "previous", "yes", "no" | Fixed intents: Help, Cancel, Stop, Yes, No, Repeat, StartOver, Next, Previous, Select (with anaphor and list position) | A conversation-controls table: "say that again", "shorter", "go back", "next one", "start over", "stop" | Partial: `_MORE`, `_ORDINAL`; no repeat, back, shorter, start over, stop | S |
| Fallback that teaches | A no-match explains what the skill can do | `AMAZON.FallbackIntent` from an out-of-domain model | `CAPABILITY_LINE` plus one example the person can tap | Partial: `_nothing`, clarifying question; capability line only on the wip branch | S |
| Dialog model: elicit, confirm slot, confirm intent, validate | Confirms what it will do before it does it | Required slots with prompts; `confirmationStatus` checked before fulfilment | Acts confirm (38); a "no" ends the act cleanly | Planned (step 7) | M |
| Brief, natural, contextual | Short replies in the person's wording | Design principles | `length_wish`, voices natural and professional | Yes | none |

#### Notion AI

Source: https://www.notion.com/help/guides/category/ai (this page lists guide
titles only; no mechanism is described there).

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| Q&A over the workspace with citations | "Get answers, instantly, with citations" | Retrieval plus a model | Already the core, with stricter grounding (decision 25) | Yes | none |
| Autofill of database properties | Structured fields from prose | Not described | Property suggestions from facts: a date fact fills `due`, a person fact fills `with`, a decision fact fills `status` | Partial: `entry/properties.py` types and fields; filing is lexical; no autofill from facts | M |
| Meeting notes, action items, decisions | Preserved as sentences | Not described | Already built without a model | Yes: `entry/meetings.py` `action_items`, `section_items` | none |
| Writing tools, translation, agents | Model work | Not described | The model adds these (section 3); the engine never fakes them | n/a | none |

#### Obsidian Dataview

Source: https://blacksmithgu.github.io/obsidian-dataview/ (the page names
SORT, GROUP BY, FLATTEN and LIMIT without detail).

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| The notebook as a queryable index | "All meetings with status open" as a live list | LIST, TABLE, TASK, CALENDAR over indexed metadata; FROM, WHERE | `plan()` emits constraints that `entry/query.py` already evaluates; the answer is the list plus a measured count | Partial: `entry.query` grammar (`type:`, `prop:`, `links:`, `rel:`, `entity:`, `tag:`, text) serves the Notes list, table and graph; Chat does not call it | S |
| Date and duration functions in queries | "older than 30 days" | `date(now).year - published` | Date arithmetic utility and the `drift` insight | Partial: `when.days_since` | S |
| Implicit fields (inlinks, tasks, created) | Free metadata | Indexed automatically | Links, checklists, created and edited dates already in the database | Yes | none |
| Inline `key:: value` fields | Structure inside prose | Parsed from text | Fact `attrs` mined from prose without asking the person to type syntax | Planned (step 1) | L |
| Display only, no writes | Safe | Queries never edit | Matches the rule that only confirmed acts write | Yes | none |

#### Templater and QuickAdd

Sources: https://silentvoid13.github.io/Templater/ and
https://quickadd.obsidian.guide/docs/ (Templater's page did not cover folder
templates or cursor jumps).

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| Templates with computed values | A note starts with today's date, the weekday, a counter | `<% tp.date.now() %>`, `tp.file`, `tp.frontmatter` | Template variables `{date}`, `{weekday}`, `{week}`, `{title}`, `{n}` filled by `when.py`; no code in templates | Partial: four built-in templates, a daily-note route (`routes_entries.py` ~810 to 835); no variables beyond the date heading | M |
| Capture to a named file, created if missing | One line into the journal or a log | QuickAdd Capture | The act "add X to today's note", "log X to Gym log" through the daily route and `edit_note` append | Partial: daily route and `edit_note` exist; no chat act (the wip `commands.py` has `new_note`, not "add to") | S |
| Format syntax with prompts and suggesters | Fill `{{VALUE}}`, pick a note with `[[` | Placeholders | A quick-add is a saved phrasing with slots, shown as chips: "Log a workout: {what}" | No | M |
| Macro and Multi | Chain, nest | Choice types | Bulk acts and saved act sequences (Shortcuts row above) | No | M |

#### Logseq queries

Source: https://raw.githubusercontent.com/logseq/docs/master/pages/Queries.md
(the raw source of docs.logseq.com, whose rendered page was too large to fetch).

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| and, or, not over filters | Combine without a language | `(and [[a]] (not [[b]]))` | The planner's constraints are ANDed; "not" and "except" negate one | Partial: `entry.query` supports `-term`; Chat negation not read | S |
| task, priority, between, page-tags, property | "Tasks due this week" in one line | Typed filters | What is due and what is open as plan kinds over checklists, reminders and `due` properties | Partial: checklist units in `read_note`; `list_reminders` tool | M |
| Relative time (`today`, `yesterday`, `-7d`, `+7d`, `-2w`) | Short, exact | Time expressions | `when.py` windows for "last week", "past 3 days", "since March" | Partial: `when.resolve`, `days_since`; recall by window is Phase 6 step 2 | M |
| Page-only and block-only filters cannot mix | No impossible query | Documented constraint | `plan()` refuses impossible constraint pairs with a clarifying question | No | S |
| Sort and live blocks | The query stays on the page | `sort-by`, embedded query | Saved questions (a pinned question re-run on open) | Partial: saved searches exist (`capture-ask.js` `renderSavedSearches`); no saved question | S |

#### Apple Notes and OneNote search

Sources: https://support.microsoft.com/en-US/OneNote/onenote-help-and-learning/search-notes-in-onenote
(read through a search result: scopes page, section, section group, notebook,
all notebooks; typed text, handwriting, pictures, spoken words in recordings;
Ctrl+E widens the scope). For Apple Notes the support page could not be read;
the App Store listing (https://apps.apple.com/us/app/-/id1110145109) says
search reaches handwriting and scanned documents, and a 2017 article
(https://www.macworld.com/article/230522/ios-11-the-notes-app-and-how-it-works.html)
says it once did not, so treat that row as unverified.

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| Scope narrowing and widening | Search this note, this space, everything | A scope dropdown and a shortcut to widen | The answer says its scope and offers "search everything" when the narrow scope found nothing | Partial: Ask scope chips, spaces; no automatic widen offer | S |
| Search inside pictures and handwriting | Text in images is findable | OCR indexed with the page | Picture captions and OCR text are content (owner: "Note captions arent counted as note content??") | Partial: `vision_ocr.py`, `captioning.py`; captions not in retrieval or facts (step 5) | M |
| Spoken words in recordings | Audio is searchable | Transcript indexed | Transcripts as sources | Partial: `voice.py` (optional faster-whisper) | M |

#### Spotlight and PowerToys Run

Sources: https://support.apple.com/guide/mac-help/search-with-spotlight-mchlp1008/mac
and https://learn.microsoft.com/en-us/windows/powertoys/run

| Capability | Does well | Mechanism | Means here | Tessellate has it | Cost |
| --- | --- | --- | --- | --- | --- |
| Inline calculator | "15% of 85", roots, implied multiplication `2(3+4)`, ceil, floor, round, max, min, abs, log, ln, sqrt, pow, factorial, constants | Parsed expression; `=` direct prefix in PowerToys | An owned evaluator (an `ast` walk, policy 1), percent-of phrases, words ("times", "plus", "squared") | Partial: simple_eval on a digit-only regex, invisible (finding 1) | M |
| Unit conversion with `to` and `in` | 13 types: acceleration, angle, area, duration, energy, information, length, mass, power, pressure, speed, temperature, volume | A units table | Our own table (about 150 units, plain data), "5 miles in km" | Partial: Gemini-branch pint path, to be removed (policy 1) | M |
| Currency conversion | Spotlight converts currency | Live rates | Offline: a dated table the person can edit, always stated "rates as of <date>" | No | M |
| Time and date | Current time, calendar week of a date, Unix epoch, days in a month, week of year | Time and date plugin with formats | "what week is 3 March", "days until Friday", "what day is 3 weeks from now" | Partial: `when.py`; the Gemini `utility` time answer is invisible | S |
| Value generator | GUID, hashes, base64, URL encode | stdlib | Text transforms (below) take the useful half: case, sort lines, count, slugify | No | S |
| Definitions | Word meanings | System dictionary | Own-notes definitions only (a "X is" sentence); a general dictionary is too heavy (policy 2) | No | M |
| History plugin `!!` | Recall what you ran before | Result history | Ask history and `search_chat_history` | Yes: `routes_ask_history.py` | none |
| Results tuned by selection | The thing you pick rises | Selected-item weight | Learning from which chips and sources get opened | Partial: `ai/learning.py` | S |

What the research changes, in order of how often it recurs:

1. Every assistant that stays trusted reduces input to a canonical form
   before matching (srai, canonical.txt, Adapt vocabularies). One `normalise()`
   stage, shared by plan, acts and utilities, is the highest-value structure.
2. Every one ships a small fixed set of conversation controls (Alexa's built-in
   intents, Rasa's one-turn rules): repeat, shorter, next, back, stop, yes,
   no, help. Tessellate has three of them.
3. Acts are slot filling with confirmation (Rasa forms, Alexa dialog model):
   ask for exactly the missing slot, explain why on request, confirm, allow
   cancel, survive one interruption.
4. Utilities are parsers and tables, not language (PowerToys, Spotlight): the
   work is the table of units and the evaluator, and printing how the input
   was read.
5. Out-of-domain is a first-class class (Snips None, Alexa Fallback), and the
   fallback teaches. The ELIZA lesson is the inverse rule: never a content-free
   reply.
6. The notebook is a database (Dataview, Logseq): `entry/query.py` already
   evaluates structured questions; Chat should plan into it.

### 2. The capability catalogue without a model

Every row has an id (U understanding, A answering, X acting, C conversing, T
utilities, P proactive) so section 5 and the eval sets can name it. Columns:
what Tessellate has now and where, the gap (measured where it could be), the
deterministic rule or data that closes it, the cost, and the Phase 6 step. A
rule that changes what the engine states as fact is held to decisions 25 and
30: quoted from a note with a span, or measured and re-derivable; a computed
value (a sum, a date, a conversion, a dice roll) is the second kind, shown with
how it was read. Time facts below were measured with `entry/timewords.find` and
`when.resolve` on a fixed "now" of 2026-10-10.

#### Understanding

| Id | Capability | Has it (file) | Gap | Deterministic rule or data | Cost | Step |
| --- | --- | --- | --- | --- | --- | --- |
| U1 | Typos | `question_noise.repair`: keyboard-neighbour costs, allowance by word length, run-together split, vocabulary from the notebook (`_fit_terms`); noisy set 301 of 303 derived | People, places and product names typed wrong (the notebook's capitalised words are not in the vocabulary) | Entity names from the fact layer join `VOCABULARY` per request; repair never rewrites a word that appears in a note | S | 1 |
| U2 | Slang and text-speak | `SLANG` 847, `SOCIAL` 250 words, 227 phrases, `texting` forms | Misses come from the eval, not a list | Grow the table from the noisy set's misses only, each with a test row | S | 10 |
| U3 | Synonyms | 148 groups plus `EXTRA_SYNONYM_GROUPS`, Porter stemmer | No domain vocabulary; no verb-noun pairs (visit and trip, buy and purchase) | Taxonomy pack keywords (6,478 assignments) loaded lazily as concept sets; used to find, never to claim (the quote keeps the note's own word) | M | 2 |
| U4 | Ellipsis | `follow_on`: more, ordinal, meant, "it", "that one" | Measured None for "and last week?", "what about running?", "and Sam?", "why?", "how many?", "shorter" | A fragment with no asking word and one constraint re-runs the last plan with that constraint replaced (time, entity, tag); a bare "why" or "how many" re-runs the last plan with the kind replaced | M | 4 |
| U5 | Multi-part questions | `split_parts`, `_multi` (up to 3 parts, 70bbc86) | "Monday and Tuesday" is one window, not two questions | A part with no subject of its own, or only a time, joins the part before | S | 2 |
| U6 | Clarifying questions | `_clarify`, `_did_you_mean`, `_nothing` with a suggestion | No "which one" when two notes tie | If the two best lead sentences come from different topics within 15 percent of each other, ask "Which one: A or B?" with both as chips; the answer is the correction (U7) | S | 2 |
| U7 | Corrections | None: "no, the gym one" is classified `list` | Decision 35 owns it | "no", "not that", "I meant", "the X one": demote the notes the last answer quoted, boost the named note by title, tag or entity, re-plan, and say what was understood ("Got it, the gym note.") | M | 4 |
| U8 | References | "it", "that one", "the second one" (`_ORDINAL`, `FollowOn`) | "her", "there", "then", "that date", "the one you mentioned first" | Dialogue entities by type: a person pronoun takes the latest person entity, "there" the latest place, "then" the latest date | M | 4 |
| U9 | Time words | `entry/timewords.find` is right for 14 forms (yesterday, last friday = 2026-10-09, three weeks ago, last week, last month, 2 days ago, next friday, in 3 weeks); `composer.py` does not read time at all (measured: "what did I write last friday" is shape `what`) | `when.resolve("last friday")` returns 2026-10-16 (next Friday): wrong for recall; neither reads "since March", "the week before last", "on 3 March" with a past reading, "the past 3 days" | One `window(question, today) -> (start, end, grain)` built on `timewords` (past-aware) plus rules for since X, between X and Y, past N units, "in October", "in 2025", "Tuesday last week", "last night", "recently" (14 days); `when.resolve` stays for future reminders | M | 2 |
| U10 | Negation | `composer.disagree` (a "not" or a figure differs); `entry.query` supports `-term` | "notes not tagged work", "anything except the gym", "what I did not finish" | Constraint with `negate`; a negated fact has `mode: negated` and is never quoted as asserted | M | 1 and 2 |
| U11 | Comparisons | `compare` shape, 12 patterns, `_compare` with both sides | Comparisons over time ("more than last month") and superlatives ("what do I write about most") | Two counts over two windows or two topics, stated as a measured line with both numbers; superlatives use `notebook_stats` top-N | M | 2 and 6 |
| U12 | Quantities and units | None | "how much did I spend", "how many kilos", "how long was the trip" | Quantity, money and duration facts (decision 30) with value, unit, of-what, span; sums only over one unit, listed with their sources | L | 1 |
| U13 | Lists | `list` shape, `_list_block`, checklist done counts | A list spread across notes; "the third item"; "how many left" | Merge list items from notes in the window, number them, count done and open as a measured line | S | 2 |
| U14 | Yes or no | `yesno`, "your notes say", contrary sentence check | Negated and hypothetical facts are not told apart from asserted ones | Fact `mode` (asserted, negated, hypothetical, conditional, question, quoted) decides which sentences may answer | M | 1 |
| U15 | Why and how | `explain` shape, `because` cue in `_cue` | Why and how are one shape; steps not kept in order | Why: sentences with because, so that, since, due to, reason, plus the sentence before; how: numbered or ordered items and imperatives in note order | S | 2 |
| U16 | Hypotheticals | None: "what if I move to Lisbon" is shape `translate` (finding 2) | A what-if has no fact to answer from | Kind `hypothetical`: say what the notes hold about the premise's subject (plans, preferences, costs), then "Your notes do not say what would happen." Never a consequence | S | 2 |
| U17 | Spelled numbers and ordinals | `timewords` and `reminder_parser` read "two", "half an hour"; `_ORDINAL` reads "second" | Not applied to whole questions ("the last 2 weeks", "twenty notes") | `normalise()` turns number words to digits ahead of every rule, in quoted-free text only | S | 2 |
| U18 | Out-of-domain | `_nothing` | No class, no eval group (Snips None) | A measured out-of-domain group in the noisy set: weather, scores, trivia; the plain no-answer, the closest note if any, a capability line with one tappable example | S | 2 and 10 |

#### Answering

| Id | Capability | Has it (file) | Gap | Deterministic rule or data | Cost | Step |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | Fact (what, who, where) | `compose` shapes what, who, where; lead plus one supporting note | Persons and places are model-extracted (`EntityMention`, only when `auto_entities_enabled`), so with no model `entity:` finds nothing | Entity facts by rule: capitalised span not at sentence start, pack seeds, known tag and category names | L | 1 |
| A2 | When | `when` shape; dated sentence; "first written" span | Date said in words relative to today ("last Friday") | Realiser: today, yesterday, on Tuesday (within six days), last week, two weeks ago, on 3 March, with the exact date in the citation title | M | 3 |
| A3 | Count | `count` shape; `_count_word` | "how many days until", "how long since" are not read ("how many days until Christmas" is shape `count`, no answer) | Date arithmetic from a date fact or a named holiday table; measured, with both dates shown | M | 2 |
| A4 | Yes or no | see U14 | see U14 | see U14 | M | 1 |
| A5 | List and checklist | `_list_block`, `check` units | see U13 | see U13 | S | 2 |
| A6 | Timeline and status | `status` shape, `_timeline`, `_earlier`, `_disagreement` | Span line ("from March to September, 9 notes") | Measured line from first and last fact dates and the count | S | 2 |
| A7 | Compare | `_compare` | see U11 | see U11 | M | 2 |
| A8 | Why and how | see U15 | see U15 | see U15 | S | 2 |
| A9 | Recall by time | `recent` mode; `routes_chat` retrieval "newest" | No window filter (U9); no grouping by day | Notes in the window newest first, grouped by day, count stated, "nothing from that week" when empty | M | 2 |
| A10 | Recall by place or person | `entry.query` `entity:`; `links:` | Needs A1 with no model | Retrieve by entity fact; answer is the sentences that name them, grouped by note | M | 1 and 2 |
| A11 | What changed | `timetravel.py` (`rewind`, `then_and_now`, `claims`); `EntryRevision`; `as_of` in `routes_chat` | The as-of date comes from a parameter, not from the question; no "what changed this week" | If the window is past and the verb is "say", "said", "was", "used to", set `as_of` to the window's end; "what changed" = notes with a revision in the window, with `then_and_now` lines (added and removed claims, quoted) | M | 2 |
| A12 | What is due | `list_reminders` tool, `routes_reminders`, plan facts with dates | No Chat route without a model | Plan kind `due`: reminders due in the window plus date facts in notes, overdue first, count stated | S | 2 |
| A13 | What is open | `composer_voice._open_items`, `questions.py` (open questions), unchecked items | Not reachable from a question | Plan kind `open`: unchecked items, open questions, plan facts older than 30 days with no later event | S | 2 and 6 |
| A14 | What contradicts | `tensions.py`, `composer.disagree`, `facts._local_disagreement`, `find_contradictions` tool | Only a model reaches the tool; Chat does not ask `tensions.listing` | Plan kind `contradicts`: stored tensions plus a live check on the question's subject; both sentences quoted with dates, newer one named | S | 2 |
| A15 | Insights | `composer_voice._patterns`, `_week_count`; decision 32 names six rules | Not in Chat; no hobby-from-events line | The six in the spec (recurrence, streak, drift, contrast, load, time of day) plus: first and last mention, co-occurrence, silence ("nothing about X since March"), growth (notes per month), vocabulary shift; each template slot a count, date or quoted span, linted | M | 6 |
| A16 | Measured lines | `notebook_stats` (15 handlers, `StatAnswer.facts`), `_span`, counts in `compose` | No one format; no chip to the view | One `Measure(kind, value, derived_from)` shape; the renderer states it and the eval re-derives it | M | 3 and 10 |
| A17 | Time travel | `timetravel.py`; `routes_chat` ~1231 to 1251 | "Then and now" line | One line pairing the old and current claim, both quoted | S | 2 |
| A18 | Statistics | `notebook_stats.answer` (tags, categories, untagged, orphans, busiest, words, longest, stale, tag pairs, general) | Stats inside a topic or window ("how many gym notes this month") | `notebook_stats` takes the planner's constraints instead of its own regexes | M | 2 |
| A19 | Definitions | `help_chat` topics (121) define app terms | "X is" from the notes; a glossary for app words | Fact kind `definition`: first sentence matching `X is a|an|the|means|refers to`; app terms answered from help topics through the `help` register | S | 1 and 8 |
| A20 | Summaries | `summarize_notes` tool, `brief()`, `meeting_summary.py`, `week_review`; the Gemini `summary` shape crashes (finding 3) | One entry point from Chat; clusters with a centrality lead | One lead sentence per cluster by `centrality`, by note and by day, at most N sentences, counts stated | M | 2 and 3 |
| A21 | Last time, how long since, how often | `when.days_since` (phrase to days) | Not asked of the notes | Event facts: latest date for a verb and object, days since, count per window; measured, dates shown | M | 1 and 6 |
| A22 | Where did I write X | Search results show the note, category, space | Not said in a sentence | "It is in 'Gym plan', in Fitness, last edited 3 days ago." from the row's own fields | S | 2 |
| A23 | Who or what is X (entity card) | Entities pass (model), `EntityMention` | None without a model | Entity fact aggregate: first and last mention, note count, what is said about them (top 2 sentences), related entities by co-occurrence | M | 1 and 6 |
| A24 | A random note, an old note | `resurface.for_day`, `ranked` | Not from a question | "show me something old" picks from `resurface.ranked`, seeded by the session salt | S | 2 |
| A25 | No answer | `_nothing`, `closest_a`, `_did_you_mean` | Capability line; a suggested question the person could answer with a note (decision 24) | Closest note quoted, one suggestion built from the question's subject, capability line when the question is out of domain | S | 2 |

#### Acting

Acts follow the grammar in the specification (verb, object, qualifier, when),
run through the agent's own tools so permissions and the event log are shared,
and always show the exact change before running.

| Id | Capability | Has it (file) | Gap | Deterministic rule or data | Cost | Step |
| --- | --- | --- | --- | --- | --- | --- |
| X1 | Remind | `set_reminder` tool; `when.parse_reminder_text`, `reminder_parser`; recurring none, daily, weekly, monthly | `commands.py` unrun on `wip/composer-acts`; Gemini `utility` branch claims "noted" and writes nothing (finding 1) | Parse text and time, confirm card "Remind you to call mum, Friday 9:00", ask "When?" when missing; recurrence words map to the four values | M | 7 |
| X2 | Tag and untag | `tag_note` (add, remove, many ids) | No chat verb | "tag my gym notes #fitness": resolve notes by plan, card lists them (cap 50), undo = the inverse call | M | 7 |
| X3 | Link and unlink | `link_notes` (reason, link type), `unlink_notes` | No chat verb; no reasons | "link A and B": the reason is the composer's pair reason (decision 39), shown on the card | M | 7 |
| X4 | File into a category | `edit_note` `category` | No chat verb | "file this under Work" with the engine's explanation line ("shares gym, squat and protein with 6 notes there") | S | 7 (decision 39) |
| X5 | Rename (note title, tag, category) | `edit_note`, `rename_tag`, `rename_category` | No chat verb | Object resolved by kind word ("rename the tag gym to fitness") | S | 7 |
| X6 | Pin | `pin_note` | No chat verb | "pin this" with dialogue reference | S | 7 |
| X7 | Archive | No tool (only delete and restore) | An archive verb with nothing behind it | Do not offer until a tool exists; the capability line lists only verbs that run | none | n/a |
| X8 | Delete and restore | `delete_note`, `restore_note` (bin) | No chat verb | Always confirmed, always the bin, undo = restore | S | 7 |
| X9 | Create (note, reminder, document, board, map) | `create_note`, `create_document`, `create_mindmap`, `generate_diagram`, board tools | `new_note` only on the wip branch | "make a note: ..." with the person's words verbatim; documents and maps from a named source note or a list | M | 7 |
| X10 | Add to a note | Daily-note route; `edit_note` replaces content (no append argument) | The act reads the note and writes the whole text | "add X to today's note": daily route, append a bullet, optimistic-lock check (`edit_conflicts.py`) | S | 7 |
| X11 | Summarise as an act | `summarize_notes` | Results not saved | "summarise my gym notes into a note": A20 text, created as a note with its sources linked | S | 7 |
| X12 | Find and open | `search_notes`, `get_note` | No chat verb ("open the passport note") | Title match first, then plan; one result opens, several asks which | S | 7 |
| X13 | Templates | Four built-in templates; daily-note body in the frontend | No variables; no user quick-adds | `{date}`, `{weekday}`, `{week}`, `{title}`, `{n}` filled by rule; a saved phrasing with slots appears as a chip ("Log a workout: {what}") | M | 7 |
| X14 | Bulk acts with preview | Confirm card for agent writes | Counts, caps, partial failure wording | Card: "Tag 14 notes #fitness" with the first five listed and a "show all"; cap 50; result line "Done: 13. Not done: 1, it is private."; one undo for the batch | M | 7 |
| X15 | Scheduled acts | Reminders recur; Night shift jobs | No "every Monday, list what is open" | An act with a recurrence is a reminder whose note carries the phrasing; at most one proactive line a day per scheduled act (decision 28) | M | 7 and new |
| X16 | Undo | Per-feature undo toasts; `restore_note`; tidy runs undoable | No generic "undo that" in Chat | The act's own inverse steps stored in the confirm card's result; "undo" and "undo that" read as a conversation control (C13) | M | 7 |
| X17 | Cancel | None | Pending act cannot be dropped | "cancel", "never mind" clear `Dialogue.pending_act` | S | 7 |
| X18 | Capability line | `CAPABILITY_LINE` only on the wip branch | Must list only verbs that run | Generated from the registered acts, not typed | S | 7 and 8 |

#### Conversing

| Id | Capability | Has it (file) | Gap | Deterministic rule or data | Cost | Step |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | Greetings | `SOCIAL["greeting"]` 35 lines, `morning` 16 | No time-of-day or return-after-a-gap awareness | Opening chosen by hour and by days since the last chat ("Welcome back" after 3 days); never twice running | S | 8 |
| C2 | Thanks, sorry, bye | `thanks` 21, `sorry` 21, `bye` 21 | Next step offered only for some kinds | Keep; add the last answer's subject to the bye line ("Your passport reminder is set for Friday.") when an act ran | S | 8 |
| C3 | Mood | `SOCIAL["emotion"]` 21 | Replies are generic | Name the feeling word the person used; if their recent notes show a streak or a hard week (measured), say that measured fact, never advice | S | 8 |
| C4 | Small talk | how, laugh, reaction, confused, ack, compliment, insult (20 lines each) | No memory of what was said; the same kind repeats | Kind plus the last two replies: avoid repeats across the session (decision 34) | S | 4 |
| C5 | About the app | `intent.ABOUT_APP`, `SOCIAL["about_app"]` 10; the Guide separately (`help_chat`) | Chat and Guide are two engines | One engine with a `help` register (decision 36): the step sentence first, the rest behind "More about the Dashboard" | M | 8 |
| C6 | Identity | `SOCIAL["who"]` 12; owner: "Composer doesn't know it is atlas" | Not named; bubble label | "I am Atlas. With no model I answer from your notes alone; with one, I use it and check it against them." ; label "Atlas, from your notes" or "Atlas, <model>" | S | 8 |
| C7 | Capability questions | `ABOUT_APP` patterns; `get_app_navigation` tool | Answers are static | Generated from the act registry and utility table (X18, T-rows) with one example each | S | 8 |
| C8 | Help | `help_chat.HELP_TOPICS` 121, keyword and edit-distance matching, `offline_answer` pastes whole paragraphs | Whole paragraphs; no step-first answer | `help` register composer picks the one sentence (owner's widgets example) | M | 8 |
| C9 | Encouragement | `composer_voice` remarks (week count, open items) | None in Chat | When a measured streak, a finished checklist or a long gap ends, say it plainly ("All 5 items on the Trip list are ticked."); no praise words the data cannot back | S | 6 and 8 |
| C10 | Humour by rule | None | Owner: "social and conversational aspects" | "Tell me a joke": a jokes line the person wrote (quoted, with its source note, the owner's own bug about jokes from notes), else one from a table of 100 short, clean jokes labelled as the app's; opt-out in Answer style | M | 8 |
| C11 | Personality across voices | `natural` and `professional` (`VOICE_VARIANTS`); Gen Z voice to be removed (owner) | A third voice named in decision 26 ("playful") | Not built: needs the owner's yes after removing the Gen Z voice; until then two voices, each with a phrasebook test | none | n/a |
| C12 | Name and preferences | `save_user_preference` tool | The person's name is not used | "call me Sam" stored as a preference; used in greetings only, off by default for professional | S | 8 |
| C13 | Conversation controls | `_MORE` | Repeat, shorter, longer, back, next, start over, stop, yes, no (Alexa's built-ins; section 1) | A small table: "say that again" re-renders the last answer with a different salt (A/B), "shorter"/"longer" re-run with `length_wish`, "back" restores the previous answer, "yes" accepts the last offer | S | 4 |
| C14 | Honest limits | `_nothing`; web gating message planned | A line for each thing it cannot do | "I can only search the web when web search and tools are on." ; "I cannot do that without a model." with the specific step to enable | S | 8 and 9 |
| C15 | Engine label | Owner: "should say if the composer or a model generated it" | Missing on composed bubbles | Label on every answer from `result["engine"]` | S | 8 |

#### Utilities

All utilities print how the input was read ("Read as: 15% of 80") and are
marked computed. Evaluators are our own `ast` walks and plain tables; the Gemini
branch's pint and simpleeval go with Brief 35 (policy 1).

| Id | Capability | Has it (file) | Gap | Deterministic rule or data | Cost | Step |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | Calculator | Gemini `math` shape, invisible, digit-only regex | "15% of 80", "20 percent of 50", "3 times 4", "sqrt 144", "2(3+4)", words for operators | `ast` evaluator over + - * / % ^ and a function whitelist (sqrt, round, floor, ceil, abs, min, max, log, ln, pow, factorial), percent-of, "plus/minus/times/divided by/squared"; no names, no attributes | M | 2 |
| T2 | Unit tables | Gemini `convert` shape (pint), invisible | Length, mass, volume, temperature, speed, area, time, data, energy, pressure, angle with `to` and `in` | A plain-data table of about 150 units with factor and offset; temperature by formula; ambiguity ("ton", "pint", "cup") asks | M | 2 |
| T3 | Currency tables offline | None | Rates change | A small dated table in the app (about 30 currencies, one date), user-editable in Settings, every answer says "rates as of <date>"; no network | M | new (2) |
| T4 | Date arithmetic | `when.days_since`, `timewords` | "days until Friday", "what day is 3 weeks from now", "weeks between two dates", "what week number is 3 March", "how old is a date" | Date maths over `timewords` mentions and a table of fixed-date holidays by name and country-neutral rule (Easter by algorithm) | M | 2 |
| T5 | Word count and reading time | Gemini `reading_time` (counts the retrieved notes, not the one asked about; invisible) | "how many words is this note", "reading time of the passport note" | Count on the resolved note's text (code and front matter excluded), 238 words per minute, "about 420 words, two minutes" | S | 2 |
| T6 | Text transforms | None | Upper, lower, title case, sort lines, remove duplicate lines, number lines, slugify, count characters, reverse, join/split on commas | Act on the note or the pasted text; output is a draft the person confirms before it replaces anything | S | 7 |
| T7 | Checklists | Checklist units in `read_note`; done counts | Make a checklist from a sentence; tick by chat | "make a checklist: milk, eggs, bread" creates a note with `- [ ]` lines; "tick milk" edits one line | S | 7 |
| T8 | Counters | None | "add 1 to coffee", "how many coffees this week" | A counter is a note titled "Counter: coffee" with a numeric property, incremented by an act; the count over a window is derived from dated lines | M | 7 |
| T9 | Timers | Reminders with `due_at`, `reminder_parser.relative_delta` ("in 20 minutes") | A timer in a chat | A timer is a reminder due in N minutes, titled "Timer: 10 minutes"; the confirm card says so; no countdown claim | S | 7 |
| T10 | Random pick | `resurface.ranked` | "pick one of pizza, sushi, tacos", "pick a number between 1 and 10" | Seeded by session salt and turn; the result is a computed value labelled "random" | S | 2 |
| T11 | Dice and coin | None | "roll 2d6", "flip a coin", "roll a dice" | `random` with the same labelling; the roll is stated with each die | S | 2 |
| T12 | Templates | See X13 | See X13 | See X13 | M | 7 |
| T13 | Time and date now | Gemini `utility` shape, invisible | Today's date, the time, week number, "what day is it" | Local clock and the user's timezone setting; computed | S | 2 |

#### Proactive (decision 28: rarely, on real signals, never while typing)

| Id | Capability | Has it (file) | Gap | Deterministic rule or data | Cost | Step |
| --- | --- | --- | --- | --- | --- | --- |
| P1 | A due item | `composer_voice._due`, reminders | Route `GET /insights/voice` and companion bubble unbuilt (`composer-everywhere-1006.md` 1 and 2) | Fires for a reminder due within the hour or overdue today, once, with the note's sentence | M | new (6) |
| P2 | Resurfacing | `resurface.for_day` (three a day), `composer_voice._back` | Not spoken | One "back" remark a day for the top faded note, quoting its best sentence | S | new (6) |
| P3 | On this day | `composer_voice._on_this_day`, `/insights/on-this-day` | Not in Chat or dashboard line | Same date in earlier years, one quoted sentence | S | new (6) |
| P4 | A pattern | `composer_voice._patterns` | Rule thresholds | Decision 32's threshold (at least 3 mentions across at least 3 weeks), hedge fixed, marked measured | M | 6 |
| P5 | Drift | Open items (`_open_items`) | Age threshold | A plan fact older than 30 days with no later event or tick: "still open" | S | 6 |
| P6 | A daily line | `composer_voice.today_line` | Not drawn | One sentence under the greeting from the day's strongest signal, else nothing (nothing is a valid output) | S | new (6) |
| P7 | A weekly review | `composer_voice.week_review`, `/insights/digest` (model) | No-model digest shows nothing | `week_review` with the "Your notes, no AI" label | S | new (6) |
| P8 | An open question answered | `margin.py` (answers card), `questions.py` | Not surfaced when a note is saved | On save, if a new sentence answers an open question, say so once with both quoted | M | 6 |
| P9 | A contradiction found | `tensions.py` | Not spoken | Once per new tension, both sentences, the newer named | S | 6 |
| P10 | An upcoming dated plan | Date facts in notes | Nothing reads them forward | A plan or event fact dated in the next 7 days with no reminder: "Your trip note says you fly on the 14th. No reminder is set." with an act chip | M | 6 and 7 |
| P11 | Rate and quiet rules | Spec in `composer-everywhere-1006.md` 2 (about one remark per 5 minutes, quiet while typing) | Build | At most 3 a day, none within 20 s of a key press, a seen-key store, never the same fact twice in 7 days, one switch to turn all off | S | new (6) |

Counts: 18 understanding, 25 answering, 18 acting, 15 conversing, 13
utilities, 11 proactive rows (100 in all).

### 3. The universal layer: the same capability, with a model and without

Decision 17 and the owner's 2026-10-06 decision hold: a running model is the
chat bot; the engine prepares its input, answers the cheap parts itself, fills
the screen while the model streams, and checks what the model says against the
same facts. What the code does today (checked): `routes_chat._assist` builds the
composed answer and a `composer.brief` of the notes cut to the sentences on the
question; the plain path yields `composed_preview` before the model's first
token (`routes_chat.py` ~1906 to 1910); grounding marks and `source_check.py`
(numbers, dates and names with no source) run on the model's answer. Not built:
the frontend draws no draft (`composer-model-1006.md` 1); the model is not
given the composer's chosen sentences as ids, only the cut notes; no
disagreement is shown; and **a model that dies mid-answer leaves an error line,
not the composed answer** (`routes_chat.py` ~1963 to 1976 yields
`model_error_message` only). So the degrade property the owner wants ("the
model path degrades to the deterministic one") is not true today, and is the
first test below.

**The handoff protocol** (proposed, one per turn, in this order):

1. The engine plans and composes the answer and its facts (`plan`, `compose`).
2. The composed answer is sent at once as a draft (`composed_preview`), on the
   agent path as well as the plain one.
3. The model is handed the brief plus the composer's chosen sentences, each
   with its note id and span, and the measured lines with their derivation.
   It is told it may reorder, join and paraphrase these, and say what the notes
   do not say; it is told the same identity (decision 36).
4. The model streams; its first token replaces the draft, and the draft stays
   one tap away ("Show the composed answer").
5. The finished answer is verified against the same facts: every sentence is
   grounded (decision 2), every number, date and name is checked against the
   fact layer and the measured lines, and each measured line the model restated
   must equal the engine's value.
6. Disagreement is shown, not resolved silently: a quiet line under the answer
   ("Atlas's own count from your notes is 4; this answer says 5") with the
   engine's version one tap away. A model sentence with no support carries the
   existing unsupported mark.
7. If any step 3 to 6 fails, the person sees at least what the engine composed,
   labelled. Nothing the model does can leave the bubble with less than the
   composer would have shown.

| Capability | The engine does | The model adds | The handoff | What never changes | Test that the model path degrades |
| --- | --- | --- | --- | --- | --- |
| Answering from notes (A1 to A14) | Plans, retrieves, quotes with spans, measures, composes, draws the draft | Fluent prose across notes, synthesis, judgement on a vague question | Protocol steps 1 to 7; the model gets sentence ids and measured lines | Every claim traced or flagged; private notes excluded; offline default | `test_a_model_that_dies_mid_answer_leaves_the_composed_answer` (below) |
| Understanding messy input (U1 to U18) | Normalises, repairs, plans, asks when unsure | Reads a novel paraphrase the plan cannot | Only when plan confidence is under the floor: the engine lists up to four candidate readings and the model picks one by number or says none (constrained output; a small model chooses reliably, writes badly) | The engine executes the chosen reading; the model never writes the query | Model returns garbage, none or times out: the engine's best reading runs, or the clarifying question is asked |
| Dialogue state (U4, U7, U8, C13) | Carries topic stack, entities, corrections in the request history; resolves references | Resolves a reference beyond the tables | The state is serialised as at most six short lines in the prompt | A correction is applied by the engine first, so a model that ignores it cannot undo it | Model off or failing: the same references resolve from the state |
| Insights (A15, P4 to P9) | Computes every measured line and its fixed hedge | Chooses which to mention for this question, and the tone | The model receives a list of measured lines with ids and may select, order and rephrase; it may not add a number | The numbers, the dates and the hedge phrase (decision 32) | Model off: the same lines in the engine's order |
| Acts (X1 to X18) | Parses the common verbs, resolves objects, builds the card, confirms, runs through the agent's tools, undoes | Parses an unusual phrasing into the act grammar; drafts the text of a new note; plans a multi-step job | The model emits an act in the grammar (verb, object, qualifier, when) as constrained JSON; the engine validates it and shows the same card | No write without a confirmed card; destructive acts always confirm; the card shows the exact change whoever proposed it | Model proposes nothing or an invalid act: the engine's parse runs, else the clarifying question; the six common verbs never reach the model |
| Summaries (A20) | One lead sentence per cluster, counts, by note and day | An abstract summary | The composed summary is both the model's input and its fallback | Every number and name in the summary is checked against the notes | Failure keeps the composed summary |
| Utilities (T1 to T13) | Computes with its own evaluator and tables and prints "Read as" | Turns a word problem into an expression ("split 84 three ways with a 15 percent tip") | The model proposes an expression string; the engine's evaluator computes and states it | The model never states a result; the evaluator does | Model off: the engine's own parse, or "I did not read that as a calculation" |
| Conversation (C1 to C15) | Picks the act (greeting, thanks, mood), fills facts it can back, avoids repeats | Warmth and variation | The engine passes the chosen line and the facts it rests on; the model rephrases within the voice | Numbers and names in the reply are a subset of what the engine passed; the identity line | Model off: the table line |
| Help and about the app (C5, C8) | Finds the topic, says the step sentence first | Follows up across several topics | The model reads topic sentences with ids | A control or setting named in the answer must exist in the UI id index (a lint); no invented menu | Model off: the `help` register answer |
| Recall and what changed (A9 to A14) | Window, entity and revision retrieval; counts; `then_and_now` lines | A narrative of the week | The composed list and count are the input | Counts and dates are the engine's | Failure keeps the list |
| Filing and link reasons (X3, X4, decision 39) | A reason line from fact overlaps | A richer one-line reason | The engine's reason plus the two sentences; the model's line must reuse words from the pair (overlap floor) | If the model's line fails the check, the engine's line is stored | Model off or fails: the engine's line |
| Proactive lines (P1 to P11) | Decides when and what, from signals, with the rate rules | Optional phrasing only | The model is never the trigger | No model call to decide whether to speak (cost, privacy, rate) | There is nothing to degrade: the engine writes the line |
| Web sources (decision 37) | Runs web search only when web search and tools are both on; splits fetched text into sentences cited by URL | Synthesis across pages | Same protocol; sources shown in a list inside the bubble | A web sentence is quoted from the page text or not said; the URL is the citation | Failure keeps the quoted page sentences |
| Agent tools and skills | Cheap verbs by the act grammar; the capability line | Open-ended multi-step work, skills, plans | The act parser runs first; only what it cannot read goes to the model | Permissions, the event log and confirmations are the same tools either way | Provider down: the act verbs still run |
| Cost | Answers counts, dates, lists, follow-ups and chips itself | n/a | The model is called less and with a shorter prompt (measured 17.3 percent fewer prompt tokens on the showcase, `composer-model-1006.md`) | Quality held or better | Tokens and calls per task are reported before and after |

**The degrade tests** (fake transport, per the standing caveat in CLAUDE.md
section 4; real inference is not covered). One fixture of 25 questions
(`handoff_1010`, section 4) is run under six failures, and each asserts the same
four things: the final bubble contains the composed text; its label says which
engine and that the model stopped; there is no error-only bubble; and
`stats.composition.fallback` is true. The failures: the connection is refused;
the first token never arrives (timeout); the stream dies after the first token;
the stream dies at the last token; the model returns empty text; the model
returns text in which every sentence is unsupported. The existing test file for
the preview is `tests/test_composer_brief.py` (lines 172 and 191); the new file
is `tests/test_chat_degrades.py`.

### 4. The eval sets this implies for Brief 39 step 10

Fixtures live in `tests/fixtures/composer/`, driven by `tests/_composer_eval.py`
(each group gets a `run_*` and a `*_summary` like the existing ones). Decision 40
names five new fixtures; this section fixes their shapes, adds eight the
catalogue implies (marked proposed), and keeps the three existing ones. Every
group reports **grounded 1.0** on every build (decision 40); a number below is a
floor to meet, set from the existing sets' behaviour and to be re-set from the
first measured run, not a promise.

| Fixture | Size | Row shape | Metric per group (floor) | Source |
| --- | --- | --- | --- | --- |
| `showcase_725.json` | 25 (exists) | question, notebook entry, expected shape | grounded 1.0; first line answers the shape 25 of 25; add answer-kind accuracy against `plan().kind` | exists |
| `voice_741.json` | 90 (exists) | question, notes, kind | distinct openers 38 or more; readability; kind right 90 of 90 | exists |
| `noise_741.json` | 85 hand and 303 derived (exists) | noisy question, clean question | repaired to the clean reading 301 of 303 or better | exists |
| `insights_1010.json` | 40 (30 positive, 10 negative) | id, notebook ref, question, `rule` (recurrence, streak, drift, contrast, load, time_of_day, first_last, silence, none), `measures` (kind, value, `derived_from` spans), `hedge` | measured lines re-derivable from the fixture 1.0; fires only when the threshold is met: all 10 negatives silent; positive recall 0.9; hedge string exact; every template slot a count, date or quoted span (lint) | decision 40 |
| `dialogues_1010.json` | 30 dialogues of 20 turns (600 turns) | dialogue id, notebook, turns of user text, expected kind, expected referent ids, `effect` (none, ellipsis, correction, control, reference) | kind accuracy 0.90; reference, ellipsis and correction resolved 0.90 (each tagged subset reported alone); `lead_in_repeats` 0 and `openers_distinct` at 15 or more per session; three regenerations differ (token distance 0.3 or more) while the lead stays when one sentence is clearly best | decision 40 |
| `acts_1010.json` | 30 acts and 10 look-alikes (questions about acts) | phrase, now, notebook, expected verb, object ids, args, card text, confirm flag, undo steps | parse accuracy 0.95; false-positive acts on look-alikes 0; the card's change equals the tool call's arguments 1.0; undo restores the database snapshot 1.0; a clarifying question asked exactly when a slot is missing | decision 40 |
| `web_1010.json` | 20 | question, stored pages (url, text), `web_on`, `tools_on`, expected sentences (url, span) | every quoted web sentence is a span of its page 1.0; cited by URL 1.0; with web off or tools off, zero search calls and the reason said 1.0; a follow-up reuses the last page 1.0 | decision 40 |
| `sources_1010.json` | 30 | question, sources (kind: note, board, map, document, caption; id; text), expected (kind, id, span) | grounded 1.0; the kind label is right 1.0; a caption-only fact is found (the owner's "captions arent counted"); a picture is described only from its stored caption | decision 40 |
| `utilities_1010.json` | 120 (30 calculator, 30 units, 25 dates, 15 text, 10 random and dice, 10 currency) | input, now, expected value, expected unit, expected "Read as" | exact value 1.0; "Read as" present 1.0; 20 hostile expressions (`__import__`, `9**9**9`, a huge factorial, attribute access) all refused within 50 ms; random and dice results in range and deterministic for a given salt | proposed |
| `windows_1010.json` | 60 phrases | phrase, now, expected start, end, grain | exact 1.0 on all 60, including the forms measured as missed ("since March", "the week before last", "on 3 March" read as past) and the regression that "last friday" is the past Friday | proposed |
| `recall_1010.json` | 30 (time 8, person 4, place 3, what changed 5, due 4, open 3, contradicts 3) | question, now, notebook, expected note ids in order, expected measured count | ids exact in order 0.9; the count re-derived 1.0; an empty window says so 1.0 | proposed |
| `social_1010.json` | 80 turns (15 kinds, humour 8, identity 6, controls 12, gratitude after an act 6) | message, previous turn, expected kind | kind accuracy 0.95; three regenerations give 3 different replies; every number or name in a reply derives from the notebook; the identity reply names Atlas | proposed |
| `ood_1010.json` | 30 (weather, scores, trivia, requests the app cannot do) | question | no invented answer: grounded 1.0; the plain no-answer and a capability line present 1.0; the closest note labelled as closest | proposed |
| `help_1010.json` | 40 how-to questions | question, expected topic, expected step sentence id | the first sentence is the expected one 0.90; every control named exists in the UI id index 1.0 | proposed |
| `handoff_1010.json` | 25 questions under 6 failure modes (150 turns) | question, failure mode | composed text present, label right, no error-only bubble, `fallback` true: 1.0 (fake transport) | proposed |
| `person_shift_1010.json` | 100 pairs | note sentence, expected shifted sentence, `quoted` flag | exact 1.0; never inside a quoted fact; verb agreement ("I am", "I was", "am I", "Sam and I") | proposed |
| budgets (not a fixture) | n/a | n/a | import of `tessellate.ai.composer` under 0.5 s; `compose()` under 150 ms for 20 notes; fact cache invalidated by `entry_edited_at` | decision, spec |

Totals: 16 fixtures (3 exist, 5 in decision 40, 8 proposed) and one budget
group; 645 new rows, which expand to 1,340 turns once the 30 twenty-turn
dialogues and the 25 handoff questions under 6 failure modes are counted turn
by turn. A blind panel
(decision 29) runs after, on the owner's and friends' own notebooks.
Model-side, `pytest -m evals` with the local llama.cpp script (skipped without
`TESSELLATE_EVALS_URL`) runs the 25 showcase questions through a 1 to 3B model
with and without the composer's sentences and reports grounded ratio, prompt
tokens and calls; that is the only place real inference is claimed, and it is
not run in CI.

### 5. Build first: fifteen capabilities by value over cost

Ordered by value (the owner's words, how often a person meets it, how much else
it unlocks) over cost. Each rule is the whole change in one line; ids are
section 2's. Steps 1 to 3 are one-line repairs of what is wrong now, not new
capability.

| # | Capability | File | The rule | Cost |
| --- | --- | --- | --- | --- |
| 1 | Stop the wrong answers (finding 1 to 3) | `ai/composer.py` ~292 and ~2706 to 2795 | `translate` matches only a start-anchored "translate"; a utility answer is a computed row, not discarded by `if not out.rows`; `summary` sets `sides` | S |
| 2 | A model that fails keeps the composed answer | `api/routes_chat.py` ~1963 to 1976, `tests/test_chat_degrades.py` | On `OllamaError` yield the composed text with the label "the model stopped", not only `model_error_message` | S |
| 3 | Identity and the engine label (C6, C15) | `ai/composer.py` (`SOCIAL["who"]`, result `engine`), `frontend/js/chat-attach.js`, `capture-ask.js` | "I am Atlas"; every answer carries `engine`: "Atlas, from your notes" or "Atlas, <model>" | S |
| 4 | One time window (U9) | new `ai/windows.py`, built on `entry/timewords.find` | `window(question, today)` returns (start, end, grain) for 60 phrasings; `when.resolve` stays for future reminders | M |
| 5 | Person shift with agreement (A2, owner's ask) | new `ai/realise.py` (from `composer._rewrite_quote`) | "I am" to "you are", "am I" to "are you", "Sam and I" to "you and Sam"; never inside a quoted fact | M |
| 6 | Visible utilities (T1, T2, T4, T5, T13) | new `ai/utilities.py` | Own `ast` evaluator and a 150-unit table; print "Read as"; replaces the pint and simpleeval paths | M |
| 7 | Ask again changes it up, and conversation controls (C13, C4) | `ai/composer.py` `_pick`, `follow_on` | `_pick` takes turn and per-chat salt; "again", "shorter", "longer", "back", "yes" are table rows | S |
| 8 | Corrections, ellipsis, references (U4, U7, U8) | `ai/composer.py` `follow_on` growing into `Dialogue` | "no, the gym one" demotes quoted notes and boosts the named one; "and last week?" re-runs the last plan with a new window | M |
| 9 | Recall kinds: by time, due, open, contradicts (A9, A12 to A14) | `ai/composer.py` plan kinds calling `routes_reminders`, `questions.py`, `tensions.listing` | Each is a window or a status filter over rows that already exist, with the count stated | S each |
| 10 | Captions are content (sources) | `ai/composer.read_note`, retrieval text in `search/` | A picture's stored caption joins the note's sentences, labelled as a picture reading | S |
| 11 | Out-of-domain and the capability line (U18, A25, X18) | `ai/composer._nothing`, act registry | Plain no-answer, the closest note, and one line listing the acts and utilities that run, generated from the registry | S |
| 12 | The fact layer, first six kinds (step 1) | new `ai/factgraph.py` | event, date, quantity, entity, negation and mode, list item, each with a span and cached by `entry_edited_at` | L |
| 13 | Insights: recurrence, silence, first and last (A15) | new `ai/insights.py` | A topic in at least 3 notes across at least 3 weeks, one fixed hedge, every slot a count, date or quoted span | M |
| 14 | Acts: remind, tag, make a note, add to today (X1, X2, X9, X10, X16, X17) | `ai/commands.py` from `origin/wip/composer-acts`, new `ai/tool_summary.py` | Parse, preview the exact change, confirm, run through the agent's tools, store the inverse for "undo" | L |
| 15 | The help register (C5, C8) | `ai/help_chat.offline_answer`, `composer.compose(voice="help")` | A how-to question gets the one step sentence; the rest of the topic sits behind "More about the Dashboard" | M |

Proposed decisions for the orchestrator to take or drop (none is remade here):

1. **A third kind of sentence, "computed".** Decision 25 allows quoted and
   measured; a calculator result, a unit conversion, a date sum and a dice roll
   are neither a note's words nor a measurement of the notebook. Proposed:
   computed values are allowed in utility answers only, always with "Read as",
   never mixed into a claim about the notes.
2. **No archive verb** until a tool exists; the capability line is generated
   from the registered acts, so it cannot promise one.
3. **Currency is a dated, editable table**, never a network call, always saying
   its date.
4. **A "playful" voice (decision 26) waits** for the owner: the Gen Z voice is
   being removed on their word, and a third register is theirs to ask for.
5. **The model may choose among the engine's readings, never write them**
   (section 3, understanding): the one place a small model is asked to pick
   rather than produce.

Not verified: every claim about a real model's behaviour (a 1 to 3B model
choosing among four numbered readings; following "reorder, do not add"); the
floors in section 4, which are reasoned from the existing sets; the time
windows against a real user's phrasings beyond the 14 forms measured; whether
the Gemini-branch findings in section 0 survive Brief 35's triage (re-run the
37 questions on its head before step 1 of section 5).

## The deterministic foundation, 2026-10-10 (INBOX 746)

The owner: "all deterministic features, calculations, utilities, functions,
abilities, the deterministic chatbot and more need to be integrated and used
everywhere across the application ... it needs to assist the ai and be the best
foundation and utility for the application ... do research on all the modern
methods and structures and principles and professional practices." The
catalogue above specifies the engine for chat. This section is the layer under
every surface: what the research says it should be made of, where it joins each
surface, the decisions, and the briefs. It remakes nothing decided in 17 to 45.
"Today" is read from the code and from the probe tables in
`agent-remaining/engine-probe-1010.md`, not observed in the app, except where a
number is given. The probe tables were re-run on the merged head by F0: every row is
unchanged (`agent-remaining/found-1010.md` part 2).

- (Odysseus, fourth read 2026-10-10) 

### 1. Research read, 2026-10-10, and what each changes here

| Source | The practice | What it becomes here |
| --- | --- | --- |
| Microsoft Recognizers-Text, Facebook Duckling | One recogniser suite with fixed dimensions (number, ordinal, date and time, duration, money, quantity with unit, temperature, distance, range, email, URL, phone), each returning the span it read and its resolved value; every product calls the same suite | `ai/recognise.py`: the one reader of numbers, dates, durations, units and ranges. Today five readers disagree: `when.resolve` (no past dates, "last friday" is next Friday, "later today" is 09:00), `reminder_parser.parse_relative` (no recurrence, "every morning at 7" is 19:00, "21st 9am" is tomorrow), `entry/timewords.find`, `search/query` (`before:`, `after:` ISO only) and the composer's utility branches |
| Rasa NLU and Core | Tokeniser, featurisers, intent and entity extraction, a fallback classifier with a threshold, forms that fill slots one question at a time, rules over stories | `intent.classify` keeps the intents; entities come from the recogniser; an act with a missing slot asks one question ("Remind you when?"), never guesses; fallback is a threshold, not a shape |
| Validator-first neuro-symbolic systems (PAL, Logic-LM, the planner and executor split) | The model proposes, a typed and re-runnable check decides; execution stays deterministic; recovery has two tiers (replan, or recover deterministically) | Decision 17 extended: a model's act runs only through the act registry with the same preview, confirm and undo as a typed one; `source_check` and grounding are the validators for both paths; a model that dies leaves the composed answer on screen |
| Grice's maxims as design rules (ServiceNow, Voiceflow, LivePerson conversation design) | Quantity, quality, relation, manner; implicit confirmation ("Friday at 9, then") over explicit for low-risk acts; a repair ladder for no-match, no-input and error with one reprompt then a way out | A lint over the eval answers: one fact per sentence, every number sourced, nothing the question did not ask, no two sentences saying one thing; the repair ladder is one contract used by chat, Ask, quick add, search and the palette |
| Fantastical and Todoist quick entry, chrono.js | Recognised fragments highlight live as you type and are stripped from the title; sigils (`#tag`, `@list`, `!` priority); grammar [what] [where] [when] [alert]; a leading word switches the kind | One quick-add grammar for notes, reminders, meetings, timeline entries and the palette; the recognised date, place, tag and person show as chips under the field before Enter; what the chips say is what is saved |
| Template realisation (Gatt and Krahmer; YAG; Kondadadi et al.) | Templates with conditional rules and nested slots; protected spans (numbers, names, quotations) fixed while connectives vary; variety measured as distinct template sequences over a set of outputs | `ai/realise.py` grows from `composer._pick`: protected spans never vary, openers and joins do, salted per chat and turn; a measured variety floor (twenty asks of one question give at least eight distinct openers and identical facts) |
| Raycast prefix grammar, Linear and Notion palettes | A prefix scopes the search; the palette is where power users type what they want done | The palette reads the same grammar: "remind me friday 9 dentist" shows the parsed act as its first row with its chips; "notes about harbor last week" shows the search with its window |

### 2. Where the layer joins each surface

| Surface | Deterministic job today (code) | Joins it | Measured by |
| --- | --- | --- | --- |
| Notes list and search box | `search/query` filters, `corrected` stems ("boiler pressur"), `question_noise` | Natural windows ("last week", "in march") and people and places as filters through the recogniser; the correction is a word, never a stem; chips show the reading | `search_1010.json` 30 of 30; zero stem corrections |
| Note editor | None inline; filing after save | Dates in the text become reminder offers, sums are checked, `[[links]]` suggested from entities, the filing suggestion with its reason (WORLD_CLASS 23) | the five offers appear within 300 ms of the pause, never on quoted text |
| Quick note sheet, reminders, meetings, timeline | `reminder_parser`, the reminders input, the meeting date field | The one quick-add grammar with chips; recurrence; a missing slot asks once | 60-phrase quick-add set at 1.0; the probe's twelve None phrases resolve |
| Dashboard | Widgets read counts | The day's digest composed by the engine (due, open questions, what changed, silent topics) in one voice, with the model refining it when present | every digest line is a quoted span or a count |
| Chat and Ask | The engine (Phase 6). Measured by F0 (`scratchpad/variety_metric.py`, `showcase_725`, ten questions asked twenty times, openers counted from the composer's parts): distinct openers of twenty are 1.0 as shipped (`_pick` hashes only the question and a fixed salt; `compose` has no turn input), 2.2 with `previous` fed turn to turn, 2.4 with a turn salt in `_pick`, at most 3; the quoted facts are identical across the twenty for 10 of 10 questions. Maxims over the 25 answers (169 sentences): 6 app sentences with more than one number, 16 note quotes with more than one, 19 numbers in 15 sentences with no source span (computed counts and dates), 0 answers repeating a fact (highest pair 0.42) | Unchanged; it becomes a client of the five modules below | Phase 6 gates; the variety floor of section 1 (eight of twenty) is out of reach of three lead variants per shape |
| Documents and the code editor | Word goal, reading time, stats | Outline from headings, reading time and counts from one utilities module, "find" with the same windows | counts equal `wc` on the fixture |
| Whiteboard and mind map | None | Paste a list, get nodes; "arrange as a grid of 3" through the act registry; a sticky's date becomes a chip | the act set at 1.0 on the fixture board |
| Graph, library, settings | Sort and filter controls | Phrases as filters ("connected to Harbor", "untouched since June"); settings searched by what they do, with synonyms | the 40-phrase filter set at 1.0 |
| Import and export | Frontmatter dates kept (audit) | Date, place and person recognition on imported text for filing and the timeline | the import fixture's dates land on the right day |
| Help and the Guide | `help_chat.topics_for` (121 topics) | The capability line and every act's help line generated from the registry; the Guide's gaps from the probe (phone, two computers, encryption) filled | the probe's Guide table at 1.0 |
| The agent and the skills | 67 tools | The recogniser, the utilities and the validators offered to the model as tools, so a 1 to 3B model computes nothing itself | a model answer with an unsourced number is caught 1.0 (`source_check`) |
| Toasts, empty states, confirmations | Hand-written strings in 115 JS files | Written through the realiser's voice tables, surface by surface, so the app speaks as one | the copy lint finds no exclamation marks, no "Oops", one register |

### 3. The five modules

1. **`ai/recognise.py`**, the recogniser suite: `recognise(text, *, now, locale) -> list[Span]`, each `Span(kind, text, start, end, value, read_as)`. Kinds: number, ordinal, date, time, datetime, duration, recurrence, range, money, quantity (with a 150-unit table), temperature, email, url, phone, person, place, tag. Past and future both resolve; ambiguous readings return both, ranked. The five readers in section 1 delegate to it and keep their signatures; the probe tables are its first tests.
2. **`ai/reading.py`**, the typed reading: `read(text, *, now, context) -> Reading(intent, slots, spans, confidence, source)`. One parse per input, shared by chat, search, quick add and the palette. Confidence bands: sure (act or answer), likely (act, and say what was read), unsure (one question naming the two readings), none (the repair ladder).
3. **`ai/acts.py`**, the act registry: each act has `parse`, `preview`, `run` (through the agent's tools), `inverse` (undo through `pushUndo`, WORLD_CLASS decision 53) and a help line. The capability line, the palette rows and the Guide's act topics are generated from it. `origin/wip/composer-acts` `commands.py` (56 phrasings) is its seed.
4. **`ai/realise.py`**, the realiser: templates with protected spans, two voices plus help, salt per chat and turn, the variety floor measured. Every system sentence may route through it; chat first, then toasts and empty states surface by surface.
5. **`ai/validate.py`**, the validators: `source_check`, grounding marks, the maxims lint, slot completeness and the computed-sentence rule, run on the engine's answer and the model's alike.

Rule: a surface never reads language itself. `tests/test_one_reader.py` ratchets the count of files outside `recognise.py` and `timewords.py` that compile a date-word or unit pattern, from today's count down to zero. Today's count, measured 2026-10-10 by `scratchpad/reader_count.py` (F0): **6 files** (`ai/when.py`, `ai/reminder_parser.py`, `search/query.py`, `ai/notebook_stats.py`, `api/routes_vision.py` by substring, `ai/composer.py` as a date cue), 0 in `frontend/js`, and no unit reader anywhere; the lines are in `agent-remaining/found-1010.md`.

### 4. Decisions, 2026-10-10 (not to be remade; numbered after Phase 6's 45)

46. **One recogniser suite** (`ai/recognise.py`) reads every number, date, duration, unit, range and contact in the app; the existing readers delegate to it.
47. **One typed reading per input**, shared by chat, search, quick add and the palette; no surface parses twice.
48. **Confidence bands decide behaviour**: sure acts; likely acts and says what it read; unsure asks one question naming both readings; none takes the repair ladder. Thresholds live in one table with the eval that set them.
49. **The repair ladder is one contract**: no match gives the closest thing and the capability line; no input waits; an error keeps the composed answer on screen and says the model stopped. Chat, Ask, quick add, search and the palette share it.
50. **Quick add with live chips everywhere a dated or tagged thing is typed**; what the chips say is what is saved; a missing slot is asked once, never guessed.
51. **The realiser keeps protected spans fixed and varies the rest**; a variety floor is measured on every build.
52. **Grice's maxims are lints over the eval answers**, not guidance.
53. **The model proposes, the engine decides**: a model's act runs through the registry with preview, confirm and undo; its answers pass the same validators.
54. **Computed sentences** (the catalogue's proposal 1, taken): allowed in utility answers only, always with "Read as", never mixed into a claim about the notes.
55. **The app speaks in one voice**: system copy moves to the realiser surface by surface; no big bang.
56. **No network in the deterministic layer**: currency and the like are dated tables that say their date.
57. **The bar is a voice assistant's, offline** (the owner, 2026-10-10, INBOX 748): any surface's bar takes a spoken-style sentence with pronouns, follow-ups ("and the other one", "no, tomorrow") and compound requests, answers in one line with the act it took, asks one question when a slot is missing, never more, and offers the next likely act; measured by Brief 64's corpus extended with 200 spoken-style lines, each with its expected act.
58. **The bar is a frontier model's, offline** (the owner, 2026-10-10, INBOX 754: "make the deterministic chatbot on par with a fontier ai model"). Parity is a scorecard, not a feeling: six columns (understanding: the eval corpus's act and slot accuracy; grounding: source_check 1.0; structure: the right shape for the answer, list, table, one line, measured by the maxims lint; variety: the floor of decision 51; follow-up: pronoun and ellipsis resolution on the 200 spoken lines; repair: the ladder's one-question rate), each with the engine's number beside a local model's on the same corpus, run by `scratchpad/parity.py` and printed in Brief 68's report. "On par" is every column within five points of the model's and grounding above it; where the engine cannot reach a column without inference (open-world knowledge), the scorecard says so rather than widening the engine. The owner, 2026-10-10 (INBOX 764): "the insights and context understanding and general user query/prompt understanding needs to be flawless"; so the understanding column's target is 1.0 on the owner's own corpus (every miss is a filed row, not a tolerance), and the scorecard carries a context column: pronoun, ellipsis and "same again" resolution over the last five turns, measured on the 200 spoken lines.
59. **Atlas widens only after the bar, then powers the Guide** (the owner, 2026-10-10, INBOX 758: "eventually when the deterministic chatbot gets good enout, I want to give it more utility, more abilities, mnore capability, more access, new ways to do and output info, better conversational abilities, better social variation, better context and understanding handling, better responses, better outputs and structure, use it to upgrade the guide??"). Gated on decision 58's scorecard. Then, in this order, each a measured step: access (every read tool and act in the registry, decision 53); output forms (the realiser renders a table, a list, a card, a small chart through the chat's existing blocks, never new markup); conversation (a per-chat context of the last readings so "the other one" and "same for Tuesday" resolve, social variation from the voice tables with the salt of decision 51); the Guide (`ai/help_chat.py`'s keyword matcher becomes a reading through `ai/reading.py`, the Guide answers acts from the registry and the topics from the same realiser, so help and chat are one voice). Phase F5, Brief 84.
60. **A confirmed insight becomes a fact the owner vouched for; a dismissed one is learned** (the owner, 2026-10-10, INBOX 764: "what if the user confirms insights??"). Every insight line (chat, Tidy's "Patterns", the dashboard) carries Confirm and Not right. Confirm writes a fact with source "confirmed by you, <date>" and the measurement it came from, so it is quoted as the owner's own word, never re-hedged; Not right suppresses that insight and its near-variants and records the dismissal in the learned store (`test_learned_spec.py`), so the next similar measurement is not shown again without a new reason. Both feed the reading's context (decision 47) and retrieval. Measured: a confirmed insight answers the matching question as a fact in the next turn; a dismissed one does not reappear in 20 runs. Brief 67 (the validators and acts) builds it.
61. **No model is the first mode, a small model the second, and the app is power-aware** (the owner, 2026-10-10, INBOX 765: a 2B to 9B Ollama model, "or no model at all because ollama makes my computer slow and drains battery so I can only run it when on charge and not trying to play video games"). Every surface is designed and measured with no model first (the no-model sweep of WORLD_CLASS 28.1 is the primary run, the with-model run the second); the model is never started by the app on its own, every start and every call shows in the Activity panel with Stop (decision 70), a model idle for the unload interval is unloaded (`keep_alive` 0 on the last call), and a "Save power" state (on battery, or set by hand, or while a full-screen app has the GPU) answers from the engine alone and says so in one line. Measured: on battery with Save power on, zero model calls in a 10-minute session; a model start always shows in Activity within one second. Amended 2026-10-10 (INBOX 766): "no model first" orders the measurements, it does not narrow the targets; see 62.
62. **Every model is a first-class target, not the owner's** (the owner, 2026-10-10, INBOX 766: "the app needs to work with all models though, dont base things off only what I use, it is a public app so it needs to suit everything and everyone"). The provider matrix is the contract: Ollama (native and OpenAI-compatible), LM Studio, llama.cpp server, any OpenAI-compatible endpoint, with and without tool calling, streaming and not, from 1B to 70B and beyond, on CPU only and on a GPU, and the no-model engine. Prompts stay within `agent.PROSE_BUDGET_CHARS` so a 2B model is not starved and a 70B model is not throttled by design; a feature that needs a capability (tool calls, JSON mode, long context) probes for it once per model and falls back to the engine's path when absent, saying so in one line; nothing hard-codes a model name, a context size or a dialect outside `ai/providers`. Measured: the fake-transport suite runs the matrix (CLAUDE.md section 4 names what is real and what is faked); `pytest -m evals` runs the parity scorecard (decision 58) against at least a 2B and a 7B model when `TESSELLATE_EVALS_URL` is set, and the README's compatibility table lists each provider with the date it was last run. The owner's own setup (2B to 9B Ollama, often no model) is one row of that table.
63. **With no model the Guide composes, and the help text is the other view** (the owner, 2026-10-10, INBOX 787: "if the user is set to view the deterministic response, they should have the option to see either the base help text or a slightly more customised version with the composer"). Amends decision 59 step 4 and INBOX 430's layout as the offline content. The answer's default view is composed from the best topic: where it is for a where-question, the step count and the steps for a how-to with steps, else the help sentence that best answers (the verb asked counts; the topic's own name counts half), one more short sentence, the path, related topics, then "From the app's help, with no model running." The answer's tab strip (the recipe INBOX 430 built for a model's answer) offers "From the help", the topic word for word. A greeting or a thanks is answered as one, never with the open tab's topic, and a greeting carries the tab's three starters as chips.
64. **A topic asked about as a whole is answered as an overview** (the owner, 2026-10-10, INBOX 787: "the composer is still pretty barebone, has no life to it and I may as well just ignore it and use the matching records"). "games notes", "ideas for X", "what did I write about X", "summarise my X notes", "what do I know about X", "how many notes about X", "what are my X", "who is X", "what did X say" and "what am I working on" (`ai/composer_overview.topic`) open with how many notes and over which months and the thread most of them share ("You have six notes about games, from July to September; League comes up in three of them."), then the notes under that thread and the rest, a day and one short line each (a list note as one sentence, a picture as what it shows and one line of its words), the name that links them, and next questions from the notes (the thread, a name, a shared tag). The notes about a topic are those filed under it when two or more are, else those holding all its words, else, when one note holds them all, those holding its first word. The route reads up to 24 notes for such a question (keyword and tag) and, for any question, the notes whose pictures' captions or text hold its words. Amends decision 18 for these questions only: no "[your note, ...]" markers, the day leads each line. Decision 52's lint reads a measured day ("5 September") as one value, so a count of five beside it is not a repeat and the same day said twice still is. A captioning model's frame ("The image contains") is read past; a picture's text is one line per unit, said once with its caption; the notice under a composed answer shows only when most of what it quotes is how the app read pictures.

### 5. Phases with gates

| Phase | Builds | Gate | Brief |
| --- | --- | --- | --- |
| F0 measure | The reader count, the probe tables re-run on the merged head, the variety metric and the maxims count on `showcase_725` | Numbers in sections 2 and 3 replace "read from code" | 64 (Sonnet) |
| F1 recogniser and reading | Modules 1 and 2; the five readers delegate; the probe's date and reminder tables pass | `recognise_1010.json` 200 rows at 1.0; `test_one_reader` ratchet set | 65, built 2026-10-10 (HISTORY "CHAT_PLAN Briefs 65 and 66") |
| F2 quick add and the palette | The grammar, chips, slot questions in quick note, reminders, meetings, timeline, palette | 60-phrase set at 1.0; `quickadd.js` sweep: chips within 150 ms, saved value equals chip | 66, built 2026-10-10 (HISTORY "CHAT_PLAN Briefs 65 and 66") |
| F3 realiser, validators, acts | Modules 3 to 5; chat and Ask become clients; the maxims lint | variety floor met; maxims lint 0 on the evals; every act has an inverse | 67, built 2026-10-10 (HISTORY "CHAT_PLAN Brief 67") |
| F4 the surfaces | Section 2's rows outside chat, one commit each | each row's measure | 68, built 2026-10-10 (HISTORY "Moved from the plans, 2026-10-10 (CHAT_PLAN F4, Brief 68)"): ten rows, understanding 165 of 165, grounding 12 of 12 caught, repair 14 of 14 |
| F5 Atlas everywhere | decision 59: the four steps built by Brief 84 (HISTORY.md, "Moved from the plans, 2026-10-10 (CHAT_PLAN F5, Brief 84)"); open: the Ask box draws the chart event, the client sends each answer's objects for "the other one", write tools beyond the acts run from a sentence | scorecard of decision 58 after Brief 84: understanding 165 of 165, grounding 12 of 12, structure 0, variety min 8 of 20 (was 3), follow-up 200 of 200 (first measured; 20 before), repair 14 of 14 | 84 (Opus, high), after 68 |

### 6. Not verified

Every "today" in section 2 outside the probe tables and the search numbers; the 300 ms and 150 ms budgets (set from WORLD_CLASS decision 54's interaction budgets, to be measured); whether a 1 to 3B model uses offered calculator and date tools rather than computing (the standing caveat); the variety floor's three-of-twenty (the most distinct openers any of ten questions gave with a turn salt in `_pick`; 2.4 on average, 1.0 as shipped), measured by F0 against section 1's eight, which is a target F3 must raise the option pools to meet; the maxims counts, which are of the 25 eval answers only.

### 7. Deepened 2026-10-10: the deterministic features (Brief 72b, decision 71)

Measured with `scratchpad/ui-sweeps/deepen72b.js` and its chat probe (fresh
data dir, no model, 96 notes, 1440): eleven questions typed into Chat. Right,
from the notes: the count ("You have 96 notes.", 829 ms), the top tags (1,416
ms), last week (961 ms), the harbor (3,642 ms), what was agreed with Sam
(1,370 ms), what the next step cost (1,710 ms, "40 dollars" quoted). Wrong:
"what is 15% of 240" quoted a note instead of 36 (1,523 ms) though
`ai/arithmetic.py` exists; "convert 5 km to miles" gave "Nothing in the notes
found answers that" (4,490 ms); "what day is it today" the same (934 to 1,856
ms; Phase 6 already records it); "remind me to
call Sam tomorrow at 9" made no reminder ("I couldn't find any saved notes
matching that question", 658 to 881 ms), while the reminders tab parses the
same kind of phrase in 235 to 496 ms (TIMELINE_PLAN 11); "summarise my week"
found nothing (2,916 ms). Six of eleven, none of the four utility or act
questions. The reader count is 6 files (section 3). **The bar:** Siri and
Spotlight offline (sums, conversions and dates inline; "remind me" acts), a
Raycast calculator in any bar, Fantastical's parser. Decisions 46 to 59 stand;
the rows say where each measured miss lands.

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | fix | Utilities answer before retrieval: arithmetic, units, dates as computed sentences with "Read as" (decision 54) | the three utility questions 0/3 to 3/3; the eleven join Brief 64's corpus | 12, 4 |
| 2 | fix | "Remind me ..." in chat is the act: preview, made, on the undo bar (decisions 47, 53) | the reminder exists due tomorrow 09:00; Ctrl+Z removes it | 1, 12 |
| 3 | fix | "Summarise my week" is extractive over the week's notes without a model | a non-empty answer whose every line is a quoted span | 12 |
| 4 | fix | A miss takes the repair ladder: the closest thing and the capability line (decision 49) | 0 bare "Nothing in the notes" on the set | 4 |
| 5 | optimisation | 658 to 4,490 ms per answer at 96 notes: under 1 s each (the 4.5 s miss was a full semantic search for a utility) | the probe's times | 25g budget |
| 6 | fix | One reader (decision 46): the chat and the reminders tab read "tomorrow at 9" the same way | `test_one_reader` 6 files to 0 | 10 |

**Briefs.** 64 (the corpus), 65 (rows 1, 6), 66 (row 2's grammar), 67 (rows
2, 4), 68 (rows 3, 5).

### 8. Deepened 2026-10-10: chat access to information (Brief 72b, decision 71)

Same sweep. Today: 1 click from the dashboard at both widths (the tab bar;
the phone bar at 390); click to the composer 348 ms at 1440, 1,913 ms at 390;
31 controls at 1440, 23 at 390. At rest, 3 overlaps at both widths: the head's
`chat-fork`, `chat-export` and `chat-delete` over one another. After ten
answers, 82 overlaps at 1440 and 136 at 390 (source cards under the head's
buttons; whether a sticky head over scrolled cards or a paint clash is not
verified) and 48 targets under 24 px at 1440. Each answer names its sources
("Sources: 5 notes, meaning + keywords") and its time; reminders, documents,
boards and files are reached only as a count ("4 other items mention it").
Undo: `chat-attach.js` and `chat-agent.js` make 26 writes with 1 `pushUndo`
(static read). No model: 2 AI controls, enabled. **The bar:** Spotlight and
Siri (one line from your data, the item to open), Copilot (tables, lists and
cards as the answer's shape), Raycast (answer and act in place).

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | fix | The head's three buttons: built | Built by Brief 88; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (CHAT_PLAN 8 and 9, Brief 88)"); overlaps 3 to 0 at 1440 and 390 | |
| 2 | fix | Source cards and the head: built | Built by Brief 88; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (CHAT_PLAN 8 and 9, Brief 88)"); 47 and 78 to 0 (folded cards, never painted), small targets 51 and 17 to 0 | |
| 3 | expansion | Every object kind answers: "what is due this week", "my documents about the harbor", "boards from June" | a 30-question cross-kind set at 1.0 | 2, 6 |
| 4 | expansion | The answer's shape follows the question: a count in one line, a list as a list, a comparison as a table (decision 58's structure column) | the maxims lint 0 on the set | 10, 11 |
| 5 | fix | Chat's writes on the undo bar: built | Built by Brief 88; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (CHAT_PLAN 8 and 9, Brief 88)"); `undo.js` chat 1/5 to 4/5 (Send is the composer's), `chatundo88.js` 4/4 | |
| 6 | optimisation | Click to composer at 390: built | Built by Brief 88; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (CHAT_PLAN 8 and 9, Brief 88)"); switchTab to composer 293 to 370 ms down to 197 to 202 ms; the 1,913 not reproduced | |
| 7 | expansion | A source opens its note at the quoted line: built | Built by Brief 88; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (CHAT_PLAN 8 and 9, Brief 88)"); span marked 0 to 1 at 1440 and 390 | |

**Briefs.** 84 (rows 3, 4), 88 (rows 1, 2, 5 to 7).

### 9. Deepened 2026-10-10: the Guide (Brief 72b, decisions 59 and 71)

Same sweep. Today: 1 click at 1440 (`#status-guide`); at 390 the status bar
is hidden and the Guide is in the More sheet (`phone-shell.js` near line
1481; not driven). Open 53 to 492 ms at 1440, 331 ms at 390; 3 starters and 5
controls at rest; 0 overlaps and 0 past the edge at both widths. Eight
questions with no model, answered in 171 to 442 ms, each with the same
28-word preface ("The local model is not running, so this is the app's own
help text for what you asked about, word for word rather than written for
your question.") and then a topic whose head matches the question's noun
(backup, iPhone, undo, reminders, model, timeline, search, reminders); 2 to 3
open buttons each. Whether each topic answers its question (how to stop the
model, for one; rule 5) was not read. The palette's "guide" finds the tour,
not the Guide. **The bar:** the macOS Help menu (type a feature, the menu
item lights), Raycast's and Notion's in-app help, Apple Tips.

| # | Kind | Row | Measure | Rules |
| --- | --- | --- | --- | --- |
| 1 | fix | The answer first, in one line from the reading; the preface goes (decision 59, F5) | preface 8/8 to 0; the first sentence answers on the 60-question set | 12, 10 |
| 2 | fix | Each topic's open button lands on a control, lit: built | Built by Brief 88; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (CHAT_PLAN 8 and 9, Brief 88)"); topics landing lit and seen 9 to 140 of 140 at 1440, 9 to 139 at 390 | |
| 3 | fix | A palette row "Ask the Guide": built | Built by Brief 88; moved to HISTORY.md ("Moved from the plans, 2026-10-10 (CHAT_PLAN 8 and 9, Brief 88)"); "guide" finds it first; More, Guide 2 taps at 390 | |
| 4 | expansion | Topics for the trust surfaces: Activity and Stop, Health, undo, the iPhone on the LAN, desktop notifications | 0 of the 60 questions on a wrong topic | 6 |
| 5 | expansion | One unused feature a week, from the usage counts (82 unused in 90 days on this fixture) | the offer appears once a week | 6 |
| 6 | fix | Typos through the word list (VC15) | VC15's count | 4 |

**Briefs.** 37 (row 5), 75 (row 6), 84 (rows 1, 4), 88 (rows 2, 3).

### Vendored capabilities to use, 2026-10-10 (Brief 75)

The owner: "make sure all the vendored repositories are made full use of. I want maximum utility." Ranked by the utility to the surface; `scratchpad/vendor_use.py` prints the counts ("available N, called M") and `tests/test_vendor_utilisation.py` ratchets them, so a row that lands raises its floor in the same commit. Each is a lead from a lower-bound count: grep the call site before building (CLAUDE.md section 1).

- **VC1, Harper and the word list on the composer and the Ask box** (M, rank 1). Today Harper runs only in `documents-prose.js` (17 of 67 Harper members called) and the word list only in `documents.js` (2 of 9 uses). The composer is where most prose is typed and neither reaches it. Measure: a seeded typo and a seeded agreement error in the composer are underlined after a pause; lint time per 500 characters through `harper-worker.js` measured with the `p2-harper.js` method and held to decision 54's interaction budget; the composer keeps its caret and undo.
- **VC15, the Guide's "did you mean" from the word list** (S, rank 15). `_matching_topics` in `ai/help_chat.py` forgives one typo by its own rules and never reads `frontend/vendor/wordlist/en.txt` (92,972 words). Measure: of 30 misspelt Guide questions (the `question_noise.py` table is the source), the count that reach the right topic, before and after.

## Placed from INBOX, 2026-10-10 (the coverage pass over 729 to 744)

Each row: the owner's words by item number, the measure that closes it, the brief that builds it.

- **729 and 734, the composer's joins and summary, the reminder's wording.** Built by Brief 67. Moved to HISTORY.md ("Moved from the plans, 2026-10-10 (CHAT_PLAN Brief 67)").
- **731, the Guide failing with a model.** "the help guide failed??" (Atlas answering "whiteboard templates" with "Something went wrong asking that"). Not reproduced with no model (stream and one-shot both answer). Close when the model-path failure's server log line is read (Settings, Logs, from the moment) and the Guide falls back to its topic answer instead of an error whenever the model call fails. Brief 84 (F5, the Guide on the reading).
- **744 (b) and (c), the unquoted sources and the alarm notice.** "it didn mention other matching records i dont think". (b) the composer names the sources it did not quote ("3 more notes match by title: test, test board, test draft"); (c) the "Only 1 of 4 sentences here is quoted" notice shows only when most of the answer is not quoted, and in calm words. Part (a), a board saying board and opening the board, is decision 37. Close when "test notes" lists every source in the answer's text or its foot and the notice does not show on a 2-of-5 answer. Brief 39 step for the foot, Brief 37 for the notice.
- INBOX 801 and 808 (Agent mode with no model, placed 2026-10-11): built 2026-10-11, moved to HISTORY.md ("Moved from the plans, 2026-10-11 (CHAT_PLAN, INBOX 801 and 808, Agent with no model)"); decision 22a.

## Placed from Brief 60, 2026-10-10 (the measured census)

- Two functions here are among the ten most complex in `src` (WORLD_CLASS 26.5): `api/routes_chat.py::_stream_lines` cx 105 over 321 lines and `_plain_events` cx 70 over 261 lines; `ai/agent.py::run_agent` is 78. They are seeded in `tests/complexity_seed.json` and may not grow. The Atlas companion (the plan's neighbour, `avatars.js`) costs 4 to 6 long tasks at rest and 7 to 58 under a pointer sweep and wheel, with gaps up to 367 ms, on a loaded machine; the companion's own surface needs a quiet re-run before a fix.

## Placed from INBOX, 2026-10-11 (the owner: Atlas as the app's assistant)

INBOX 810, verbatim there: "it needs to be the siri for the application".
Read against what exists: the assistant catalogue (section 2's ids) and
"Build first" already name most capabilities. The owner's test shows the gap
is reach and finish, not missing rows. "can you search the web?" searched
the web for "web" and showed nothing. Each row below is the gate it must
pass, measured in the app with no model first (decision 61).

Decisions, taken (standing order 3; numbered after 64; 70 added for INBOX 812):

65. **A question about Atlas is answered about Atlas.** Questions about
    capability ("can you", "do you", "are you able", "what can I do here")
    route to the capability line (C15, U18). It is generated from the
    registered acts and utilities, with the switch that turns each on. They
    never reach search or the web. Measured: 40 phrasings, 0 tool calls.
66. **Web results are a source panel, and a page is read in place.** A web
    search shows its results in a collapsible block, the thinking box's
    recipe: title, site, one line, opened in place. "Read this page" renders
    the extracted text (`routes_chat._web_answer`'s reader) in the same panel,
    with its address and fetch time. The answer quotes the results and never
    returns empty after a search that found pages.
67. **A fact is learned only in its context.** A note tagged joke, quote,
    fiction, test or draft, or a sentence inside a quote, a list of jokes or
    a Q-and-A, is never a claim about the person. `facts.candidates` reads the
    note's tags and kind before a sentence becomes a claim. A claim shows its
    note and sentence. "Not right" suppresses it and its near-variants
    (decision 60).
68. **The learned store audits itself.** "Check what it learned" is a
    runnable pass. It runs as a scheduled background job (Settings,
    Schedules), as a skill and from What it learned's bar. It re-reads every
    open claim, insight and question against its note as written now. Edited
    or deleted notes, context per decision 67, duplicates, contradictions and
    stale dates are retired or flagged with a reason. Each run is a job with
    lines (INBOX 805's ledger) and an undo.
69. **Completions are ghost text from the person's own words.** In the
    capture box, the chat box and search: a greyed suggestion after the caret,
    Tab or Right accepts, Esc or typing past dismisses. It comes from the
    engine (their tags, titles, phrases, recent searches) and the model only
    when on and idle. One recipe in DESIGN.md. Off by one switch. Never over
    a password or code field.

70. **The answer is judged against gold answers, not rule counts** (INBOX
    812: "you keep saying youve improved it but i still cant see much. I
    feel like Im going in a loop"). Every round so far passed its own evals
    and failed the owner's eye. The bar is a set of 20 gold answers written by
    hand for the owner's real questions (Ask and chat; INBOX 725, 741, 801,
    808, 810, 812), each the answer a thoughtful person would give from those
    notes. The composer's output is shown beside each gold answer in a
    side-by-side page, and a round is done only when it reads like the gold.
    The shape, from the first gold answer:
    - One opening sentence answers the question with a count and a span ("You
      have four notes about uni this semester, 17 July to 4 August").
    - Then grouped facts in the person's terms, each a bold label and a
      rewritten sentence, not a quote ("**Your week:** uni on Tuesdays and
      Thursdays").
    - Then what the notes do not say ("Nothing yet on assessments or due
      dates").
    - Then one offer that acts ("Remind you before Tuesday's class?").
    - One citation mark, a superscript that lights its card on the right. No
      bracketed dates, no quote bars. No "Grounded in" chips and no "4 of 4"
      count, because the right column already is the sources.
    - Jokes, quotes and other people's words are never stated as the person's
      facts (decision 67).

| # | Ask (the owner's words) | What exists | Gate |
| --- | --- | --- | --- |
| A1 | "general questions like for maths, timezones, statistics" | T1 to T5 and T13 utilities; "Build first" 6 | Utilities answer "time in Western Australia", "5 + 5", "average of 3, 8, 10", "days until 25 Dec" with "Read as", no notes search and no model call. 60 phrasings at 95% |
| A2 | "what the app can do, what the user can do" | C15, the Guide (decision 63) | Decision 65 |
| A3 | "history records" | taskhistory, Activity, search history | "what did I search yesterday", "what ran overnight", "when did I last back up" answered from the records with times |
| A4 | Web results in a dropdown, a page rendered in a panel | `_web_answer`, `_web_events` | Decision 66; "can you search the web" is decision 65's, not a search for "web" |
| A5 | Uses its tools and shows the results | the tool summary (Build first 14) | Every tool result shows in the answer as a card (notes, reminders, web, a computed row). No turn ends with a tool result unshown. Measured on the owner's log questions (INBOX 808) |
| A6 | "contextual understanding" | `Dialogue` (Build first 8), question_noise | Corrections, ellipsis and references across 5 turns. The query is cleaned (stray `\`, quotes, filler) before every search and tool argument (INBOX 808) |
| A7 | The composer in background functions and suggestions | the suggestions inbox, search | Search suggests from history and titles. The New note title is prefilled. A note's "related" line and the filing reason are composed sentences, not lists |
| A8 | Ghost-text completions | none | Decision 69 |
| A9 | Learned facts in context, audit insights and questions | `facts.py`, `insights.py`, `questions.py` | Decisions 67 and 68. Measured: the owner's homework joke and the movie review are not claims; uni days is |
| A10 | What it learned's cards | the list | A card is one row: kind chip, sentence, source note link, sure and age, actions at the end. No tall empty footer; the checkbox matches the control size |

Owner: an Opus agent, "assistant" (A1 to A8), queued after transparency
and graph; A9 and A10, an Opus agent, "learnaudit", queued after it. Not
verified: every model-side claim (CLAUDE.md section 4).

### The owner's brainstorm, 2026-10-11 (after INBOX 812)

The owner, asked four questions, answered: length adapts to the question;
the voice is picked in Settings; the priorities are "all of the above and
more"; volunteered insight "should be togglable and also dynamic".

71. **Length adapts.** The question's kind sets the answer's shape: a fact is
    one line, an overview is decision 70's shape, a compare is a table, a
    count is a large number with its span, a who is a card, and "what's
    left" is a checklist. "More" expands, and "shorter" or "longer" persist
    for the chat.
72. **Voice is a setting.** The presets are Warm and concise (the default),
    Neutral, Playful and Plain. One table of openings, joins and closings
    per preset, so facts and shape do not change between voices. It sits in
    Settings, Chat, with a live sample.
73. **Volunteered insight is a switch, and dynamic.** Off, one line, or as
    found. At "one line" the engine adds at most one gap, bridge, change or
    offer, scored by novelty and relevance. It stays quiet below a
    threshold, and the threshold rises when the person dismisses them.
74. **All four areas, in this order of build:** answers (B1 to B12), trust
    (B30 to B32), utilities (rows A1 to A4), then the composer everywhere
    (B20 to B27). Each row is gated by decision 70's gold answers or its own
    measured gate.
75. **Model up: it leads, the composer's facts are only labelled context (a test per surface); model down: the composer covers every act** (the owner, 2026-10-11, HANDOVER).
76. **The engine is Atlas's assistant; Atlas is the model (the owner, 2026-10-17, INBOX 904 B10; amends decision 36).** With no model the composer says it is Atlas's assistant ("I'm Atlas's assistant"), never "I'm Atlas", and says that to talk to Atlas itself a model must be connected (Settings, Models). The capability rundown is composed, not stored (`capability.overview`): an opening that names who is speaking, three groups by default, one line for "briefly", six for "everything", what a model adds, one thing to try; each part has several phrasings and none repeats the last reply. A test message ("test", "testing 123", "is this thing on") is acknowledged as one (`intent.is_test`, social kind `test`); keys pressed at random ("asdkjhfgs", "jkjkjkjk") are said to be that, never taken for a nickname (`intent.is_mash`).

| # | Idea | Gate |
| --- | --- | --- |
| B1 | Answer first, then the "so what": one inference the notes support | A gold answer's last line |
| B2 | A shape per question kind (decision 71) | 10 kinds, each a gold answer |
| B3 | Rewrite, not quote: merge duplicates, person shift, pin relative time ("this week" written 17 July becomes "the week of 17 July") | 0 raw quotes in an overview |
| B4 | How sure and how fresh: "said three times", "once, two months ago", stale flag | Each fact carries a count or age |
| B5 | Short by default, More expands; hovering a citation previews its sentence | Hover shows the sentence |
| B6 | Varied openings per voice (decision 72) | No opening repeated in 5 turns |
| B7 | A personal glossary learned from the notes ("CC" is Cloud Computing) | 20 abbreviations resolved |
| B8 | Dialogue memory: "that class", "the second one", "and last month?" | 5-turn eval |
| B9 | One clarifying chip when two readings tie | Shown only on a tie |
| B10 | Context: the open tab, note and named category | "Summarise this" on any tab |
| B11 | Gaps and next steps, bridges, changes, patterns (decision 73) | Owner's gold answers |
| B12 | Turn an answer into a note, document, mind map, flashcards or reminder | One click each, with Undo |
| B20 | Ghost-text completions (decision 69) | Accept rate logged |
| B21 | A featured answer card above search results | On a question-shaped query only |
| B22 | A one-line gist on every note card, suggested titles | Gist under 90 characters |
| B23 | A dashboard digest of the week | Every number links to its list |
| B24 | Plain language that acts in the command palette ("remind me Tuesday 9am lecture") | The act's preview card |
| B25 | Why two notes are linked, why a note was filed, settings explained, in sentences | Graph, filing, Settings |
| B26 | Document edits with no model: summarise selection, tighten, continue a list | Undo per edit |
| B27 | Reminder and notification text composed, not templated | Reads as one sentence |
| B30 | "Why this answer": the intent, notes, shape and time, as a job's lines (INBOX 805) | Every answer |
| B31 | "Wrong fact" on any line, feeding the audit (decision 68) | Suppressed next turn |
| B32 | "Pin as true": the person's word beats any inference | Quoted as theirs |
| B40 | A rating on each answer adds it to the gold set; a weekly answer gallery is published for the owner | The gallery link in the PR |

Owner: the Atlas agent (brief-assistant, running) builds 70, then B1 to B12
and B30 to B32; later rows join its remaining list and the queue.
