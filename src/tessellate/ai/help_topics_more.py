"""The Guide's reference, part two: every Settings section, the companion, the
faces, and the app's layout, plus how each entry is laid out as an answer.

INBOX 430 (the owner): "expand the help content massively, covering every
tab, setting and feature", after the Guide told him the corner companion was
"a feature within the Ask tab". It had nothing to say about the companion at
all, so a model with no reference guessed. The rule stays the one
`help_chat.HELP_TOPICS` states: an entry is the model's only source of facts
about the app, so each one here was written from the running app's own
controls and their own wording (Settings, section by section), not from
memory of what the app used to do.

`MORE_TOPICS` joins `HELP_TOPICS` (help_chat.py); `TOPIC_META` gives every
entry, old and new, the parts the system answer is laid out from
(`help_chat.system_answer`): a title, the path to where it lives, the steps
where there are steps, and the settings row a link opens (`target`, the row's
id, which `openSettingsModal(section, target)` scrolls to and lights).
"""

from __future__ import annotations

from tessellate.ai.help_topics_more_mid import MID_TOPICS

MORE_TOPICS: list[dict] = [
    {
        "id": "graph-categories",
        "keywords": (
            "graph category", "category on the graph", "select a category", "select a whole category",
            "category header", "category name on the graph", "treemap category", "tessellation category",
            "frame a category", "category menu graph", "select all notes in a category",
        ),
        "body": (
            "On the Graph, in the Treemap and Tessellation layouts, each category's name bar is a "
            "control. Point at it and it lights with a rim and a pointing hand. Click it to select "
            "every note in that category (Shift adds to what is selected), and the selection bar acts "
            "on them all, as it does after a lasso. Double-click it to zoom to that category. "
            "Right-click it, or hold it on a phone, for its menu: Select its notes, Frame it, "
            "Rename, Colour, Merge into, Split, Delete and Manage categories, the same as the Notes "
            "sidebar. From the keyboard, click the map, press C to step through the categories "
            "(Shift and C goes back), Enter to select the one lit, Esc to let it go. In Tree and "
            "Radial, the category's own dot does the same."
        ),
        "badge": {"label": "Graph", "tab": "graph"},
    },
    {
        "id": "companion",
        "keywords": (
            "companion", "corner companion", "buddy", "mascot", "sidekick",
            "little character", "character in the corner", "call back",
            "call it back", "hide the companion", "show the companion",
            "companion size", "the little guy", "rub the companion", "flip the companion",
        ),
        "body": (
            "The corner companion is a small character with a place of its own, "
            "like a house cat: it perches on a panel or a toolbar and rides with it "
            "as the page scrolls. Switching pages does not move it; it stays with "
            "its page, out of sight while you are elsewhere. After a few "
            "minutes apart it may walk over to you, and now and then it "
            "goes out for a while and comes back (Reduce actions on Normal). Stay "
            "here on every page in its menu keeps it in view on all of them. It keeps "
            "quiet company while you type, plays when you idle, naps when you "
            "are away. Choose who it is in "
            "Settings, Appearance, Atlas and faces, Corner companion: Off, "
            "You, The chat's persona, Atlas, or Your own character (a name and "
            "parts of its own). Companion size is Small, Medium or Large, or "
            "drag the handle at its corner (double-click it "
            "for Medium again); the size is marked On this device, so a phone "
            "keeps its own. Drag it onto a panel and that page "
            "keeps it there on this device; Tab to it and an arrow key "
            "moves it 16 pixels (Shift 64); throw it and it flies and stays put. "
            "Rub it and it leans in; tickle its belly, click its nose or shake it "
            "while carried and it giggles, sneezes or turns over dizzy "
            "(switches under What it does on its own). Hover anything it wears for what and why. "
            "Its large view (double-click it) has a "
            "row of things to ask of it: wave, cheer, hop, stretch, shrug or "
            "wiggle, and Atlas also juggles stars, reads its map and "
            "meditates. Right-click it, or press Shift+F10 on it, for its "
            "menu: Say hello, Enlarge, Stay here on every page, Let it choose "
            "its spot here, a size, Quieter (only blinks and looks; Livelier undoes it), "
            "Call back and reset its place, and Hide. "
            "Ctrl+Shift+Y, the command palette and Find anything show or hide "
            "it from anywhere, and the palette's Focus companion puts the keyboard on it. If it "
            "is ever out of reach, Call back (in the setting, its menu or the palette) brings it back."
        ),
        "badge": {"label": "Corner companion", "section": "appearance", "target": "avatar-buddy-row"},
    },
    {
        "id": "companion-activities",
        "keywords": (
            "what the companion does", "companion push-ups", "companion lifts weights",
            "companion drinks tea", "companion snack", "companion fishing",
            "companion activities", "companion hobbies", "companion journal", "companion stargazing",
            "companion blanket nap", "companion waters a plant", "companion puzzle",
            "companion nods", "companion little dance", "companion poses proud", "companion tiptoes",
            "companion sneezes", "companion hiccups", "companion hugs itself", "companion taps a foot",
            "companion chases a firefly", "companion counts stars", "companion naps on a card", "companion waves at the pointer",
            "companion looks down", "companion daydreams", "companion tinkers", "companion miffed face",
            "companion smirk", "pat the companion", "pet the companion", "companion bonk", "swipe the companion", "companion twirl", "companion cloud", "companion grabs an edge",
            "companion eats dinner", "companion blows bubbles", "companion knits", "companion rides the wind",
        ),
        "body": (
            "On its own, Atlas does the same small things as the desktop companion: "
            "push-ups, dumbbells, tea, a biscuit, fishing, a journal, the stars, a nap (a blanket draped over a pillow, "
            "a small z rising, the rings dimmed to a faint halo and slowed until it wakes), watering a plant and a puzzle, "
            "a bowl of dinner, bubbles from a wand and knitting a strand of starlight, each with its eyes on the prop, and short "
            "gestures: a nod, a little dance, posing proud, a look down and tiptoeing, then a daydream, "
            "pacing, a made-up game, tinkering with a gear and dusting off, and a sneeze, a hiccup, a hug "
            "round itself and a foot tap, then a firefly chase, a little pile of stars counted, a nap on a note card and a wave at the pointer. A shake or a pout leaves it "
            "miffed for a moment, and a shrug a smirk. "
            "The loud ones (push-ups, dumbbells) wait for a lull. They are one group, \"Atlas does the "
            "desk companion's routines\", under Settings, Appearance, Corner companion, "
            "What it does on its own; Quieter keeps "
            "it to blinks and looks. Pat its head with slow dabs and it enjoys it (Lean into a rub or a pat), "
            "a fast swipe across it makes it twirl once (Turn upside down when shaken, twirl at a fast swipe), "
            "a hard throw into the top bar bonks it before it falls, and a long way across the page is sometimes a ride on a "
            "cloud or in a bubble. The hour counts: tea and stretches lean to the morning, bubbles, dancing and a snack to the afternoon, "
            "dinner and knitting to the evening, and the loud ones hold off at night. A long way for Atlas is sometimes a ride on a gust of motes that curls a spiral when it sets off and settles in a small eddy; on the desktop its floating trips do the same. None of it with Motion off. To take hold of a panel's edge it leaps up from its feet and grabs."
        ),
        "badge": {"label": "Corner companion", "section": "appearance", "target": "avatar-buddy-row"},
    },
    {
        "id": "companion-remarks",
        "keywords": (
            "companion says something", "companion speech bubble", "companion talks",
            "what the companion says", "companion remarks", "companion messages",
            "companion popup messages", "companion mentions my notes",
            "companion reminder", "stop the companion talking",
        ),
        "body": (
            "Now and then, a few times a day at most, the corner companion says "
            "something from your notes in its speech bubble: a reminder that is due, "
            "a note from this day in an earlier year, something you left open, or "
            "a quiet day. It is written from your notes with no model, never from a "
            "private note, and never the same line twice. It stays quiet with "
            "Motion off, while you carry it, or while it sleeps. To stop it, turn off "
            "Say something from your notes in Settings, Appearance, Atlas and faces, "
            "Corner companion, What it does on its own."
        ),
        "badge": {"label": "Corner companion", "section": "appearance", "target": "avatar-buddy-row"},
    },
    {
        "id": "companion-habits",
        "keywords": (
            "companion habits", "companion reactions", "companion reacts to search",
            "companion tilts its head", "companion double take", "companion shakes itself",
            "companion winces", "atlas looks around", "atlas hums", "companion mood time of day",
            "companion stretch at dusk", "companion morning wave", "atlas breathing",
            "stop the companion reacting",
        ),
        "body": (
            "Now and then the corner companion reacts to what you do: a puzzled tilt "
            "when a search finds nothing and a nod when the next one does, a double "
            "take when the pointer rushes past it, a shake once you put it down after "
            "carrying it a while, a nod on the hour and a stretch at dusk, a sleepy wave "
            "at your first key of the morning, a wave when you come back after ten "
            "minutes away, a shiver when the battery is low, a glance when the window is "
            "resized or goes fullscreen and a look back when it leaves, a nod when a long "
            "run of typing stops, a small nod when you send a chat message, and a small wince when a note goes to the bin. The desktop "
            "companion does the same on your desk. Atlas breathes quicker after a walk or a "
            "carry and blinks slower when sleepy, lets out a breath a moment after a start, "
            "its eyes take tiny steps while it looks at something, and its tail and trailing wisps "
            "swing down and back up after a landing. Any companion looks at a popup that "
            "lands on it before it steps out of the way, and cheers once for each round "
            "number your note count passes, such as 100, on the desk too. Catch it "
            "in the air with a click while it falls and it clutches, then relaxes once it lands. Atlas "
            "also has rare habits of its own: a look around, a hum, a settling breath "
            "and a second look at the pointer, each at most once in three minutes. "
            "Its "
            "moods follow the part of the day, brighter in the morning and quieter in "
            "the evening. None of it happens while you type, while Motion is reduced, "
            "or over something else it is doing. To stop it, turn off Little habits and "
            "reactions in Settings, Appearance, Atlas and faces, Corner companion, What "
            "it does on its own."
        ),
        "badge": {"label": "Corner companion", "section": "appearance", "target": "avatar-buddy-row"},
    },
    {
        "id": "companion-travel",
        "keywords": (
            "companion portal", "companion puff of smoke", "companion vanishes",
            "companion walks off the screen", "companion ducks under the bar",
            "companion moves too much", "companion distracting", "companion travels",
            "companion sneezes", "companion grooms", "companion sighs",
            "companion tumbles across the screen", "companion falls from the top",
            "showy entrances", "companion entrance", "companion settles",
            "companion in the way", "companion covers my text", "companion covers the button",
        ),
        "body": (
            "The corner companion travels rarely and never while you type or "
            "carry it. It never sits on a menu, a popup, the field you are "
            "typing in or the line your caret is on, and when the pointer rests "
            "on a control beside it, it steps aside. Drop it on a board shape or a mind map topic and it sits on its top edge, moving with the pan and zoom. Atlas and the animals "
            "decide the same way: Atlas keeps more room and plays less, a cat "
            "or an owl keeps its distance, a dog or a fox wanders more. When it has somewhere far to go it takes a calm way: it "
            "opens a portal and walks through (its pick for a long way, and its way out of a hard throw), vanishes in a puff of smoke or a "
            "burst of sparkles, rides a small cloud, floats over in a bubble, walks "
            "off one side of the window and comes in at the other. Never the "
            "same way twice in a row. On a new page it fades in where it rests "
            "or takes a few steps in its corner, and a new view in the same tab "
            "crossfades it to its new spot, and it glances at the new page rather "
            "than crossing it. Arriving it gives a little at the knees, waking it "
            "rises, and after a reaction it breathes out, never the same way twice "
            "running. To have it glide, walk on, tumble "
            "or drop in instead, turn on Showy entrances in Settings, "
            "Appearance, Atlas and faces. The rest of the time it sits, looks around, "
            "stretches, yawns, grooms, sniffs, sighs or shakes itself off. With "
            "Motion off, or Interface animations off, it only fades or "
            "stays put. Two seconds after your last move it can go still to save "
            "power: Motion at rest, in the same place, keeps it always alive, "
            "alive on mains power only (the default), or still when idle. "
            "To keep it still, set Corner companion to Off in "
            "Settings, Appearance, Atlas and faces."
        ),
        "badge": {"label": "Corner companion", "section": "appearance", "target": "avatar-buddy-row"},
    },
    {
        "id": "companion-throw",
        "keywords": (
            "throw the companion", "flick the companion", "throwing the companion",
            "companion splat", "companion climbs", "companion hangs from the top bar",
            "companion went off the screen", "companion lies down", "companion slips off",
            "companion went off the top", "companion tumbles",
        ),
        "body": (
            "Throw the corner companion by letting go of it while it is still "
            "moving fast. It flies, bounces off the window's edges and stays "
            "where it lands, and now and then something else happens: it "
            "catches the top bar and hangs from it, grabs a panel's top edge "
            "and climbs on, catches the end of a panel as it falls past or "
            "slides off one and pulls itself up, splats against a side of the "
            "window and slides "
            "down to the panel below, or goes off one side and comes back on "
            "the other. How you throw it chooses: a soft toss lands near, a hard "
            "one sideways can go far or into a corner, and a hard one upwards "
            "can leave the top of the window and fall back in. A panel only "
            "catches it when it comes down slowly, and it may land, slide off "
            "or tumble and get up. It lands by how it was turned: on its feet, or flat on its back or belly, "
            "skidding a little, lying a moment and getting up to shake it off. On its feet it comes down soft after a short fall, in a stumble after a longer one and in a forward roll after a fast one. A side of the window squashes it flat for a moment as it bounces off, and holds it flat while it slides. A long drop makes it flail. Carry the panel it stands on, or scroll a list under it, fast and it is shaken off with a flail, then looks worried or miffed for a few seconds (not with Motion off). Once down it settles in its own way: sitting with its "
            "legs dangling or kicking, lying down, stretching, or swinging "
            "from the bar. Wherever it ends, it never covers a button: come "
            "down on one and it moves only to the nearest clear place. With "
            "Motion off, it simply appears where it lands."
        ),
        "badge": {"label": "Corner companion", "section": "appearance", "target": "avatar-buddy-row"},
    },
    {
        "id": "what-is-atlas",
        "keywords": (
            "what is atlas", "who is atlas", "what does atlas do", "what can atlas do", "about atlas",
            "meet atlas", "atlas assistant",
        ),
        "body": (
            "Atlas is the assistant inside Tessellate. It answers questions from your notes and cites them, "
            "files new notes, sets reminders, finds, tags, moves and links notes (a change that cannot be "
            "taken back waits for your Confirm), and opens the part of the app you name. Ask lives in Notes, "
            "Chat has its own tab, and Ctrl+Shift+A opens it over any tab, where its paperclip, a drop or a paste adds files as chips. With no model connected it "
            "answers from your notes by itself."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    },
    {
        "id": "atlas-look",
        "keywords": (
            "atlas look", "atlas style", "classic globe", "globe", "atlas character",
            "atlas's face", "atlas mood", "atlas moods", "masculine", "feminine",
            "what does atlas look like", "change atlas", "atlas avatar",
            "assistant avatar", "app emblem", "reply avatar", "chat avatar", "app logo",
        ),
        "body": (
            "Atlas is drawn as a small character of starlight with rings "
            "round its head, or, if you prefer, as the classic glowing globe: "
            "Settings, Appearance, Atlas and faces, Atlas style. Atlas look "
            "picks Masculine or Feminine, or Auto, which follows Face looks "
            "when that is set to one look and your own face's look otherwise; "
            "it is used everywhere Atlas appears, the dashboard mark and the "
            "chat's replies included. Assistant avatar, in the same place, swaps "
            "the face on the assistant's chat replies, the popup agent and the "
            "guide between Atlas and the app's animated emblem (it holds still "
            "under Motion off or with Interface animations off); other "
            "personas keep their own faces. "
            "Atlas's face follows the app's mood: "
            "thinking while an answer runs, happy when it lands, worried at an "
            "error, sleepy late at night. Enlarge, in the companion's menu or "
            "on any face, shows the full drawing; right-click the companion "
            "there to change who it is, its look or its size."
        ),
        "badge": {"label": "Atlas look", "section": "appearance", "target": "atlas-look-row"},
    },
    {
        "id": "faces",
        "keywords": (
            "avatar", "avatars", "generated face", "profile picture", "face looks",
            "avatar animation", "faces follow", "follow the pointer", "persona face",
            "dashboard mark", "faces", "blinking", "my face",
        ),
        "body": (
            "Every person, persona and chat gets a generated face, drawn from "
            "its name: a name that says a mood (\"sleepy wizard\") or an animal "
            "gets that face, and any other name still gets a character of its "
            "own, the same one every time, and each character wears a mood in "
            "its own way. Settings, Appearance, Atlas and faces: Avatar "
            "animation (Always, On hover, Off) lets faces blink and act out "
            "their mood, Faces follow the pointer turns eyes and heads toward "
            "your mouse, Face looks sets hair, brows and jaw (Neutral, "
            "Masculine, Feminine; never read from a name), and Dashboard mark "
            "swaps the dashboard's logo for a face. Your own face is in "
            "Settings, Profile, Your look: Shuffle redraws it, and Choose parts "
            "yourself sets any part by hand. Motion off stops the animation."
        ),
        "badge": {"label": "Atlas and faces", "section": "appearance", "target": "avatar-motion-row"},
    },
    {
        "id": "profile",
        "keywords": (
            "profile", "my profile", "my name", "display name", "your look",
            "shuffle", "change my name", "what to call me", "greeting name",
            "call me", "what you call me", "call me by", "make atlas call me",
        ),
        "body": (
            "Settings, Profile is you, kept on this computer: Your name (shown "
            "in the greeting and on your mark), Your look (your face, drawn "
            "from your name; Shuffle redraws it and Back to my name's own "
            "undoes that, Choose parts yourself sets each part), and About me, "
            "which Atlas reads for more personal answers only while \"Let Atlas "
            "read your name and About me\" is on. Delete my profile data clears "
            "it; answers just get less personal. Telling Atlas \"call me Sam\" "
            "sets Your name for you."
        ),
        "badge": {"label": "Profile", "section": "preferences"},
    },
    {
        "id": "tools-setting",
        "keywords": (
            "tools it can use", "which tools", "turn off a tool", "disable a tool",
            "small model mode", "run budget", "tool list", "tokens per step",
            "tools offered", "using a tool", "use a tool", "stop atlas using",
            "cut that reply short", "model size", "does atlas do sums",
        ),
        "body": (
            "Settings, Tools it can use also has Use these tools from another "
            "app: a snippet to paste into an MCP client such as Claude Desktop, "
            "with a Copy button; that client can also read your notes (never "
            "a private one) and use your skills as prompts. It reads only until "
            "you tick Let that app add and change notes. "
            "A number Atlas would work out (a sum, a percentage, a conversion, a "
            "count of days) comes from the app's own calculator, Calculate, and a "
            "date in your words from Read text, so a small model computes "
            "nothing in its head; Check answer finds any number its answer "
            "says that the notes do not, and Propose act shows a change as "
            "a card you confirm. "
            "Settings, Tools it can use lists the actions Atlas may take in "
            "Agent mode, grouped as Reads your notebook, Asks you first "
            "and Reaches the web; turn one off and it is never "
            "offered, or a whole group with its Turn all off. Every change "
            "asks you first, with a card to Confirm or a typed yes, and once Atlas has read a web page, "
            "a file, or a note clipped or imported from outside, every web request asks too. How many are offered at once: Only "
            "what the message needs (the default) or Always send all of them, "
            "if Atlas ever misses a tool you asked for. Small model mode offers "
            "a small model one tool at a time (Auto decides from the model's "
            "name, On, Off). Run budget caps what one skill run may spend, in "
            "tokens per step and in seconds; 0 means no limit. A skill may also "
            "cap its own tool calls and steps; a run that passes a cap stops, "
            "says which, and keeps its changes for Undo. With small model mode "
            "on, a skill measured below 80% on small models shows Needs a "
            "larger model, with why. In Agent mode "
            "the model's size, read from its name, decides how many tools it "
            "sees and how long one step may write: under 3B and up to 8B get "
            "a short toolbox and a reply that runs long is cut short, 8B and "
            "up get everything."
        ),
        "badge": {"label": "Tools it can use", "section": "tools"},
    },
    {
        "id": "context-window",
        "keywords": (
            "context window", "context size", "context length", "num ctx",
            "window too small", "bigger window", "tokens window", "n ctx",
        ),
        "body": (
            "Settings, Models, Context window is how much the model can hold at "
            "once. Empty means auto: the model's own window, held back only by "
            "how much free memory the cache for that window would need, and the "
            "line under the box says the number in use and why. A number you "
            "type for a model always wins. With llama.cpp the server sets the "
            "window when it loads the model, so Tessellate follows the number "
            "the server reports; start it with a larger -c for more."
        ),
        "badge": {"label": "Models", "section": "models"},
    },
    {
        "id": "learned",
        "keywords": (
            "what it learned", "learned", "worked out", "derived", "forget everything learned",
            "learned from you", "filing accuracy",
            "read my notes now", "export what it learned", "check what it learned", "retired", "flagged",
            "while you were away", "disagree", "contradict", "answered later",
        ),
        "body": (
            "Settings, What it learned is what Atlas worked out by itself while "
            "reading your notes (a claim a note makes, a question it leaves "
            "open, two claims in different notes that disagree, a question a "
            "later note answers), where What it remembers is what you told it. "
            "The Dashboard's While you were away card counts each kind from the "
            "last read; a pair shows the other sentence under it, a button to "
            "open the other note and, for a disagreement, one to link the two "
            "notes as disagreeing. Every row "
            "says which note it came from, which model decided it and how sure "
            "it was. Edit a row and no later run overwrites it; delete one and "
            "it is never worked out again. What may run switches each kind off; "
            "Read my notes now runs it. Check what it learned, on the bar, re-reads "
            "every claim and question against its note as the note says it now: it "
            "retires what no longer holds, each with its reason and an Undo (a note "
            "edited or deleted; a note tagged joke, quote, fiction, test or draft, "
            "or a sentence inside a quote or a list of questions and answers; a "
            "sentence you marked wrong; a repeat), and flags what needs your eye "
            "(two notes that disagree, a date that has passed), marked on the row "
            "with a Check this line. It also runs after each background pass, as a "
            "job in Settings, Background tasks with its lines, and as the skill "
            "Check what it learned. Export what it learned and Forget "
            "everything learned act on all of it and never touch your notes. "
            "The Learned from you line under the title counts your corrections "
            "and gives filing accuracy, the share of the notes Atlas filed that "
            "you left where it put them, older half of the last 200 against newer. "
            "Under it, Clear answers marked not right forgets every answer you marked not right "
            "in Chat; those marks are kept only on this device."
        ),
        "badge": {"label": "What it learned", "section": "learned"},
    },
    {
        "id": "make-a-diagram",
        "keywords": (
            "make a diagram", "draw a diagram", "diagram of", "a diagram", "create a diagram",
            "diagram without a model", "flowchart", "draw a flowchart", "chart of my plan",
            "plan as a diagram", "map out", "visualise my notes", "visualize my notes",
        ),
        "body": (
            "With no model, two places make a diagram. Library tab, Create, New mind map "
            "opens a map you type into (Tab adds a child, Enter a sibling), and its "
            "templates, Trip plan among them, start you with branches in place. "
            "Insert, Diagram, Mermaid diagram on a board takes a few lines of text and draws a "
            "flowchart, sequence, state, Gantt or pie chart live. A note's menu, under AI actions, "
            "Make a mind map, builds a map from that note's headings and lists. "
            "The Writing room's diagram needs a model for anything beyond a rule-made "
            "flowchart, timeline or mind map. "
            "A diagram on a board can follow a Library diagram: it redraws from it, and if that "
            "diagram is deleted the board keeps its last picture and says so."
        ),
        "badge": {"label": "Mind maps", "tab": "library"},
    },
    {
        "id": "open-questions",
        "keywords": (
            "open questions", "questions view", "unanswered", "undecided", "still undecided",
            "answered by", "mark answered", "drop a question", "ask about these",
            "find questions", "generate questions", "read notes now",
            "questions without a model", "i wonder", "need to find out",
            "questions my notes leave open", "leave open", "left open", "unanswered questions",
            "questions in my notes", "questions i have not answered", "questions i haven't answered",
            "still unanswered", "left unanswered", "unanswered in my notes",
        ),
        "body": (
            "Notes, Questions lists the questions your notes ask in passing, "
            "your own ones only (not a quote, a prompt list, a script's line or "
            "a joke answered on the next line), "
            "found when Atlas reads your notes (Read notes now, which says how many it "
            "read and found, or on its own "
            "with background tasks on), grouped by note, newest note first: "
            "Open, Answered or Dropped, picked in the bar with a count on each. A "
            "note that asks any says so on its card (2 open questions); pressing "
            "that shows only its questions. A row says when it was asked; when a "
            "later note answers it, the row "
            "says so with the sentence, and pressing that line opens the note. "
            "Mark answered asks which note answers it and links the two notes; "
            "Drop puts a question aside; Reopen brings either back. With no "
            "model the reading is by rule: a sentence ending in a question mark, "
            "or one that says I wonder, not sure if, need to find out, should I "
            "or how do I; a later note on the same thing that states it marks "
            "it answered. Ask about "
            "these opens Ask answering from the notes with open questions only "
            "(Ask all notes under the box goes back). The Dashboard's While you "
            "were away card counts the open ones and names the oldest."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    {
        "id": "general-settings",
        "keywords": (
            "smart quotes", "link offers", "offer links", "auto clear",
            "empty the bin", "delete old chats", "chat history", "mute notifications",
            "general settings", "seasons", "hemisphere", "southern hemisphere", "summer", "winter",
            "my birthday", "on my birthday", "date order", "day first", "month first", "before:", "first run preferences",
        ),
        "body": (
            "Settings, General. Calendar: First day of the week, and Seasons, which half of the year "
            "summer, winter, spring and autumn mean (northern or southern hemisphere; automatic follows "
            "your language and region, so en-AU, en-NZ and en-ZA read summer as December to February), "
            "and Dates like 3/4 mean (day first or month first; automatic follows your region), "
            "and My birthday, which \"on my birthday\" in a reminder uses. "
            "Search: Count the day itself in before: searches (off, before:2026-03-10 stops at the 9th). "
            "The welcome's last card offers the same three choices once, and Skip passes them by. "
            "Bin: auto-clear binned notes, documents, reminders and OCR readings after a "
            "number of days. Chat history: delete saved chats after a number "
            "of days (0 keeps every chat; pinned chats are never deleted). "
            "Notifications: mute everything except reminders. Writing: smart "
            "quotes and dashes in documents, Check link text (spelling and grammar skip the words "
            "of a link unless it is on), Kinds of suggestion in a document's writing sheet (switch off style, "
            "punctuation, capital letters or word choice), and offers to turn a named note or document into a link "
            "(switch them off there, or press Never offer a link to this name on one offer; Offer them "
            "again brings every kept name back). Answer style moved to Settings, "
            "Personas, and Search relevance to Settings, Search and index."
        ),
        "badge": {"label": "General", "section": "general"},
    },
    {
        "id": "search-index",
        "keywords": (
            "search relevance", "minimum similarity", "above-average margin",
            "search engine", "semantic search", "embedding model", "re-index",
            "embedding models", "multilingual search", "change embedding model",
            "pull a model", "pull a model by name", "found on this computer",
            "uninstall embedding model", "reinstall embedding model", "cached models",
            "files missing", "model files incomplete",
            "rebuild search index", "search index", "search is wrong",
            "too many results", "too few results", "search feels too strict",
            "download search by meaning", "no thanks", "refuse download", "turn on search by meaning",
            "cancel install", "fastembed", "130 mb download", "search model download",
        ),
        "body": (
            (
                "Settings, Search and index. Search engine: the built-in one (recommended, about 300 MB "
                "of memory while open) or an Ollama model such as nomic-embed-text. "
                "The built-in one needs the fastembed package (ONNX Runtime, no PyTorch) and a small model "
                "from huggingface.co, about 130 MB in all. Nothing is downloaded without a yes: the first time a "
                "save needs it Tessellate asks once, with Download and No thanks, and search uses "
                "keywords until you say yes. The switch Download search by meaning turns it on later, "
                "or off (downloaded, it reads Repair search by meaning by itself); Settings, Packages keeps a manual Install. Changing the engine re-reads every note in the background "
                "(Background tasks shows it, with Stop); search uses the current model until "
                "the new one has read every note. Embedding models lists the choices, from MiniLM "
                "(smallest, fastest) and BGE Small (the default) to multilingual ones (Multilingual E5, "
                "BGE M3, Qwen3), with each one's size, languages, context and licence, and its state "
                "(Downloaded with its size on disk, Not downloaded, or Files missing, with Reinstall; "
                "Settings, Packages points here): Use switches in one press, and a model under other "
                "terms (EmbeddingGemma) links to them instead; each row's ⋮ has Use, Install or "
                "Reinstall, and Uninstall (refused on the model in use). Found on this computer lists "
                "embedding models already here (the Hugging Face cache, Ollama, LM Studio), with Use "
                "where Tessellate can load them and why not where it cannot. Pull a model by name takes a"
                " Hugging Face repo (owner/name) or an Ollama name and checks it online only when you "
                "press Pull. Search index: Rebuild search index after an update or a restore, or if "
                "search stops finding notes you know are there. Search relevance: Minimum similarity and "
                "Above-average margin; raise them for fewer, surer results, lower them if search feels "
                "too strict, and Reset to default undoes both."
            )
        ),
        "badge": {"label": "Search and index", "section": "searchindex"},
    },
    {
        "id": "search-engine-moved",
        "keywords": (
            "search engine moved", "engine moved", "upgraded from pytorch", "old search engine",
            "pytorch", "torch", "sentence-transformers", "old search files", "old model files",
            "remove old models", "free disk space", "why download again", "download again",
        ),
        "body": (
            (
                "After an upgrade from a version that ran search by meaning on PyTorch, the question about "
                "downloading it says the engine moved. The old model files do not work with the new engine, "
                "so it is one download (about 130 MB for BGE Small) that replaces them, asked first, with "
                "keyword search working meanwhile. Notes made with BGE Small or Multilingual E5 Small keep "
                "their search data; notes made with any other model are read again in the background. Once "
                "the new model is ready, Settings, Search and index, Old search files lists the old model "
                "folders with their sizes and Remove deletes one; in the packaged app it also removes PyTorch "
                "and sentence-transformers. Nothing else changes."
            )
        ),
        "badge": {"label": "Search and index", "section": "searchindex"},
    },
    {
        "id": "answer-style",
        "keywords": (
            "answer style", "concise", "detailed", "shorter answers",
            "longer answers", "friendly", "professional wording", "formal wording",
            "natural wording", "wording when no model", "composer voice",
            "voice", "playful", "plain answers", "neutral", "how atlas sounds",
            "insight", "patterns in answers", "what atlas adds",
            "long text in an answer", "wall of text", "folded text",
        ),
        "body": (
            "Settings, Personas, Answer style: how Atlas words its answers, "
            "Friendly (the default), Concise or Detailed, whichever persona is "
            "active. Below it, How Atlas sounds with no model picks the voice "
            "it answers from your notes in without a model: Warm and concise "
            "(the default), Neutral, Playful or Plain, with a sample under it. "
            "The facts and the sources are the same in every voice. What "
            "Atlas adds of its own sets whether an answer about a topic ends "
            "with a pattern from your notes: Nothing, One line (the default) "
            "or Everything it finds; each Not right raises the bar. A long "
            "block in an answer from no model (the text read from a picture, "
            "say) is folded to one line, its first sentence and its length; "
            "press it to read the whole. A model's own answer is never folded; "
            "only its thinking is, under Thinking."
        ),
        "badge": {"label": "Answer style", "section": "personas", "target": "pref-style"},
    },
    {
        "id": "wrap-lines",
        "keywords": (
            "wrap lines", "wrap text", "wrap a table", "wrap code", "wrap a code block",
            "table scrolls sideways", "code scrolls sideways", "long lines in code",
            "wide table", "horizontal scroll", "don't wrap",
        ),
        "body": (
            "A wide table or a code block in an answer (and in a note's Read view) "
            "scrolls sideways. The Wrap lines button in the card's top bar, beside "
            "Copy, breaks the long lines instead, so nothing scrolls; Don't wrap "
            "(the same button, pressed) puts the scrolling back, which is what you "
            "want for code you mean to paste. Tables and code remember their own "
            "choice for the next one."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    },
    {
        "id": "background-tasks",
        "keywords": (
            "background tasks", "running now", "what is it doing", "job", "jobs",
            "battery", "battery-efficient", "save power", "quit the app",
            "quit tessellate", "quit memorymap", "stop the server", "close the app properly",
            "last run", "last ran", "background jobs", "job history", "did it run",
            "run now", "night shift", "stop a job", "cancel a job", "scheduled pass",
            "process log", "what did it do", "who started it",
            "what ran overnight", "when did i last back up",
        ),
        "body": (
            "Settings, Background tasks shows what the app is doing right now "
            "(re-indexing, downloading a model, installing packages, setting up "
            "search), each running job with a progress bar (a moving one when "
            "it cannot count its steps), how long it has run and who started it, "
            "with Stop on the jobs that can stop safely, and what has finished "
            "since it started, with how long it took. Every run, a chat answer "
            "or an Agent turn too, has its lines in a fold: what it searched, "
            "each tool it called, done; live while it runs. Background jobs lists every kind of job, the never-run "
            "ones too, with when it last ran and how it went; each scheduled "
            "pass (autonomous background AI, the night shift, the daily backup, "
            "resurfacing, the embeddings backfill, housekeeping) also says when "
            "it runs by itself and has Run now. Beside each "
            "control (Back up now, Rebuild search index, Find duplicates, the "
            "importers) a line reads, for example, \"Last run 2h ago, "
            "succeeded, 412 notes indexed\", with the exact time on hover; a "
            "failure says why in a few words. Ask \"what ran overnight\" or "
            "\"when did I last back up\" and the answer comes from these "
            "records, with times. Autonomous background AI is here "
            "too. Battery-efficient "
            "mode pauses background AI, heavy graph work and the moving "
            "artwork. Quit Tessellate stops the app and its server properly, so "
            "the next start finds its port free."
        ),
        "badge": {"label": "Background tasks", "section": "tasks"},
    },
    {
        "id": "health",
        "keywords": (
            "health", "is my notebook ok", "integrity", "integrity check", "corrupt",
            "corruption", "last backup", "last error", "data folder size", "how big",
            "is it healthy", "check the database",
        ),
        "body": (
            "Settings, About, Health says how the notebook is, each line dated: "
            "the last backup and when it was taken, the data folder's size, Files on disk (a bar of the notebook, attached files, pictures, backups and optional features), what "
            "is running now, the last error in the log, and Integrity, whose "
            "Check now has the database check itself and counts the search index "
            "beside your notes. The palette's Health goes straight there. The "
            "app also gives the notebook file a quick check each time it starts, "
            "and if that fails it says so and points to the newest backup in "
            "Settings, Import & export."
        ),
        "badge": {"label": "About", "section": "about"},
    },
    {
        "id": "data-folder-check",
        "keywords": (
            "deleted files", "deleted a folder", "deleted my data folder", "missing file", "file missing",
            "data folder check", "check and repair", "repair", "deleted the database", "notebook file missing",
            "restore after deleting", "preferences.json", "robust",
        ),
        "body": (
            "Each start checks the data folder, and Settings, About, Health, Data "
            "folder check, Check and repair runs it again. A missing uploads, media "
            "or backups folder is made again, empty, and a missing backups folder "
            "gets a fresh backup. A settings file the app cannot read is kept beside "
            "itself and the defaults are used. A deleted or damaged notebook file is "
            "never replaced on its own: the lock screen offers the newest backup "
            "that holds notes, Restore backup or Start a new notebook, and a "
            "damaged file is kept aside. Attached files that are gone are listed "
            "with their notes; a full backup file holds them. Nothing is deleted."
        ),
        "badge": {"label": "About", "section": "about"},
    },
    {
        "id": "maintenance",
        "keywords": (
            "maintenance", "check this computer", "doctor", "doctor.sh", "doctor.bat", "start --doctor",
            "reinstall", "reinstall on next start", "rebuild", "venv", "reinstall.sh", "tools.sh",
            "launcher logs", "open the launcher logs", "desktop shortcut", "make a desktop shortcut",
            "uninstall", "remove the app", "how do i uninstall",
        ),
        "body": (
            "Settings, About, Maintenance runs the launcher's own actions from "
            "the app. Check this computer runs the checks doctor.sh and "
            "doctor.bat print (Python, free disk, the port, the model server, "
            "the notes folder, the last launch) plus the search model and other "
            "devices, each row with a tick, a warning or a cross and what to do. "
            "Reinstall on next start rebuilds the app's Python environment the "
            "next time start.sh or start.bat opens the app, the same as "
            "reinstall.sh; your notes, settings and models are not touched, and "
            "Cancel takes it back. A copy from the installer has no environment "
            "to rebuild: its Repair shortcut is the way. Open the launcher logs "
            "opens the folder the launcher writes to, and Make a desktop "
            "shortcut makes the one start --shortcut makes. Uninstall… never "
            "removes anything itself: it shows the steps and the command for "
            "this computer with Copy, and Export my notes first. These work "
            "only on the computer the app runs on; on a phone they are off."
        ),
        "badge": {"label": "About", "section": "about", "target": "maintenance-group"},
    },
    {
        "id": "activity",
        "keywords": (
            "activity", "activity panel", "what is running", "stop a job", "stop it",
            "stop the model", "unload the model", "free memory", "model in memory",
            "stop generating", "stop the answer", "agent runs", "running jobs",
        ),
        "body": (
            "Activity lists every job running now: indexing, a model loading or "
            "answering, imports, reading text, transcribing, backups and the "
            "agent's passes, each with a bar, its lines and Stop where it can stop "
            "part way; every model call is listed, on its own or inside the job "
            "that made it. Under it, what finished in the last half hour says how "
            "it ended, how long it took and when, with its lines. While anything runs, the status bar's job slot says how "
            "many and names the newest. Open Activity from it, its agent runs count, the chat's ⋯ menu (Activity and past runs), or the "
            "palette (Activity). Its two tabs carry a glyph and a count, and each part is a card "
            "headed by a glyph and a title. Its Agent runs tab lists each run this session "
            "with its steps, and the log is in its menu. Stop the model, in the "
            "menu and in Settings, Models, stops any answer "
            "and unloads the model from memory (Ollama drops it at once; the chat's Stop reaches the model too); a server "
            "this app did not start keeps its own model, and the message says so."
        ),
        "badge": {"label": "Models", "section": "models"},
    },
    {
        "id": "packages",
        "keywords": (
            "packages", "package", "pip", "install a feature", "optional feature",
            "extra", "extras", "dictation model", "embedding model", "markitdown",
            "bundle", "bundles", "reinstall", "uninstall", "install several",
        ),
        "body": (
            "Settings, Packages lists what Tessellate can do with one more "
            "package installed: nothing there is needed to write, search, tag "
            "or organise notes, each one switches on a feature that is "
            "otherwise off, downloaded from PyPI to this machine. Bundles "
            "group the packages one kind of work needs (Documents, Vision, AI, "
            "Voice, Desktop, Code, Languages): a bundle's Install fetches what is "
            "missing, and its ⋮ reinstalls or removes them all. Tick packages "
            "to install, reinstall or remove several at once from the bar "
            "above the list; they run one after another and one that fails "
            "does not stop the rest; a bundle's row shows each of its packages "
            "as it goes, waiting, installing or done. A feature that needs a missing "
            "package shows a notice with Install; once pressed the button turns to Undo, which stops the download or removes the package again; its x hides it until that package changes. A notice that names Settings, Packages "
            "(a feature that is not installed) has an Open Packages button that scrolls to "
            "that package's row. An installed package's ⋮ has Reinstall "
            "(for a feature that is on but not working) and Remove (the "
            "packaged app keeps its Desktop window, so that row has Reinstall "
            "only), and its row shows its version and size on disk. How an install went "
            "(and pip's log) is shown under the package it was about. A package with "
            "no build for your computer says Not for this computer and has no tick. Dictation and "
            "embedding models, and LanguageTool, have their own topic (Models in Packages)."
        ),
        "badge": {"label": "Packages", "section": "extras"},
    },
    {
        "id": "package-models",
        "keywords": (
            "dictation model", "whisper size", "model size", "skip silence", "dictation language",
            "words to expect", "embedding model", "embedding models", "languagetool", "java",
        ),
        "body": (
            "Dictation model size runs from "
            "Tiny (fastest) to Medium (most accurate); each size says whether it "
            "is on this computer, a size that is not downloads the first time "
            "you dictate with it (choosing it asks first, and nothing downloads "
            "until then), and Remove this size frees the disk. Skip silence before "
            "transcribing (on) stops Whisper writing words into the quiet around "
            "a clip; Dictation language skips the guess; Words to expect lists "
            "names and terms it should spell your way. Embedding models lists "
            "the built-in models on this machine, each downloaded once and kept; "
            "which one search uses is chosen in Settings, Search and index. "
            "LanguageTool, a second grammar checker (252 MB), needs Java already "
            "installed and runs only while you write."
        ),
        "badge": {"label": "Packages", "section": "extras"},
    },
    {
        "id": "answer-offers",
        "keywords": (
            "offer", "offers", "remind you to", "save it as a checklist", "gather them",
            "track in a table", "typing yes", "no thanks", "story over many notes", "counting chart",
        ),
        "body": (
            "An answer from your notes can end with one offer as a link: Remind you to..., Save it as a checklist note, "
            "Start a list of films to watch next, Note the first as your pick, Gather them into one note, Track your "
            "lifts in a table. Press it and it is done, with Undo; in Chat, typing yes does the same for any of them "
            "(the app keeps the note the link would make), and no thanks drops it. "
            "A story over many notes tells the ones it read and says so at the end (That tells five of the twelve; ask for a month or a tag to see the rest). "
            "A counting question in Ask (how many notes per category this month) also gets "
            "a chart from your notes, with its numbers and Save as PNG."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    },
    {
        "id": "spelling-packs",
        "keywords": (
            "spelling pack", "spelling packs", "french spelling", "german spelling",
            "spanish spelling", "spellcheck in french", "spell check another language",
            "document language", "lang key", "spelling off for this document",
        ),
        "body": (
            "A document is checked as English unless its properties set a "
            "language (a lang key, such as fr). For French, German and Spanish, "
            "Settings, Packages offers a spelling pack each (about 340 KB, "
            "kept on this computer); the Suggestions panel of such a document "
            "also has an Install button. Once installed, spelling is checked in "
            "that language and grammar stays English. Add a word to the "
            "dictionary as usual to stop it being flagged."
        ),
        "badge": {"label": "Packages", "section": "extras"},
    },
    {
        "id": "import-export",
        "keywords": (
            "import markdown", "import a folder", "import a pdf", "import word",
            "import as a document", "slide deck", "merge duplicates",
            "tidy up duplicates", "full backup", "restore a full backup", "mmenc", "seal a backup",
            "export csv", "export json", "exports folder", "zip",
        ),
        "body": (
            "Settings, Import & export. Export your data as JSON, CSV, Markdown "
            "or a full backup (the database, media and attached files as one "
            "file, sealed with a password if you type one: a .mmenc, else a "
            ".zip); Restore a full backup, just below, reads either back and "
            "replaces the notebook after a safety snapshot; Open exports "
            "folder and Save exports to set where files land. Tidy up "
            "duplicates finds notes that say much the same thing, no AI "
            "needed, and merging keeps every tag and bins the rest. Import "
            "markdown files or a folder (Obsidian frontmatter is understood; a "
            "preview lists the files first, so you can untick any), "
            "or a PDF, Word file or slide deck, one note per chapter or slide. "
            "The four import groups (Import markdown, Import a document, Import "
            "from another app, Web clipper) are folded: press a heading to open "
            "it, and the ? beside it opens it too. "
            "To keep a file whole as a document you can edit instead, open "
            "Library, Documents, the more menu, Import a file as a document. "
            "Backups: Back up now, and how many to keep; one is also taken "
            "each day the app starts. Restore first says how many notes and "
            "documents the backup holds against now, and snapshots first, so even a "
            "restore can be undone. A line above the list gives the schedule, when "
            "it last ran and whether that worked, and when the next is due; in the "
            "desktop app, Also copy each backup to sends a second copy to a folder "
            "you choose, such as an external drive. Each backup row says when in words, marks "
            "the newest Latest, and says what made it (the daily backup, Back "
            "up now, before an update or a restore), its size and whether it "
            "was checked. App cache, at the bottom: Clear app cache "
            "reloads the app with fresh files and never touches your notes."
        ),
        "badge": {"label": "Import & export", "section": "data"},
    },
    {
        "id": "settings-reset",
        "keywords": (
            "reset a setting", "reset to default", "default setting", "changed setting",
            "reset section", "export settings", "import settings", "settings file",
            "copy my settings", "move my settings", "this browser", "which settings sync",
        ),
        "body": (
            "A setting changed from its default shows a bar at its left edge and "
            "a reset button at the end of its row, which puts that one setting "
            "back; Reset N changes, in the section's title bar, puts back every "
            "changed setting in that section. Performance mode, Text size, "
            "Density, Zoom and the companion's size, marked On this device, are "
            "kept only on the device you set them on (a phone and a computer "
            "each have their own zoom); the rest, your colours and fonts "
            "included, are kept in your notebook and follow you to every "
            "browser you sign in from. Settings, "
            "Import & export, Your settings: Export settings saves every setting "
            "as one .json file (no notes in it); Import settings reads one back, "
            "applies each setting it can, adds its skills, personas and templates "
            "to yours by name, says which it skipped and why, and offers Undo."
        ),
        "badge": {"label": "Import & export", "section": "data"},
    },
    {
        "id": "logs",
        "keywords": (
            "logs", "log", "support bundle", "report a bug", "bug report", "error report",
            "send a report", "email support", "send you my logs", "diagnostics", "copy diagnostics",
            "something is slow", "app is laggy", "lag report",
        ),
        "body": (
            "Settings, Logs shows what happened, for when something did not "
            "work: filter by source and level, follow new lines, copy or clear "
            "them. A filter only hides records, never deletes them: Show them clears "
            "the filters, scrolling up draws older ones and the circular arrow "
            "reads the log again now. The ? beside the three dots in its bar says what each control "
            "does. The support bundle collects the logs and the app's state; "
            "Email it opens a message to support with the bundle to attach. "
            "To send the logs for something slow or broken, open the three dots in "
            "the Logs bar and press Copy diagnostics (or Save diagnostics as file), "
            "or run Copy diagnostics from the palette: one plain-text report of lag "
            "with its cause, errors, slow routes and how big the notebook is, with "
            "no note text, that you paste into a message."
        ),
        "badge": {"label": "Logs", "section": "logs"},
    },
    {
        "id": "find-anything",
        "keywords": (
            "find anything", "ctrl p", "finder", "find a note fast", "find a file",
            "jump to a note", "saved searches", "find a chat",
        ),
        "body": (
            "Find anything (Ctrl+P, or the magnifying glass in the status bar) searches notes, "
            "files, documents, chats and actions in one box as you type: Enter opens "
            "the top result, the arrows move, Esc closes, and the star keeps the "
            "search as a row under Saved searches in the Notes sidebar. Sort has Best "
            "match, Group by category (a note under its category, the rest under "
            "their kind), Newest first and Oldest first. Its '?' lists "
            "the operators. The kind chips under the box scroll sideways when they do "
            "not fit: a thin bar on a mouse or trackpad, an arrow at the end that has "
            "more, a swipe on touch. It lists the command "
            "palette's actions too, so \"dark\" finds Toggle light/dark, after the "
            "notes and files. The command palette (Ctrl+K) sends what you type "
            "here: its last row, Search everything for, opens this box with "
            "the words already searched. As you type it suggests your recent searches, "
            "then note titles, tags and categories, with the best match in grey: Tab or "
            "Right takes it, and Settings, General, Search turns it off."
        ),
        "badge": {"label": "Keyboard shortcuts", "section": "shortcuts"},
    },
    {
        "id": "background-art",
        "keywords": (
            "animated background", "background animation", "moving background",
            "wallpaper", "background style", "constellation", "fireflies",
            "rain background", "lightest background", "background cost",
            "wander", "drift", "pen strokes", "paused background",
        ),
        "body": (
            "Settings, Appearance, Animated background: Style is a card per "
            "art, lightest first, each with a preview and its cost, Light, "
            "Medium or Heavy, from what one frame takes; picking a card turns "
            "the background on. Wander draws pen strokes that walk and fade; "
            "Drift is slow colour noise. A background that has been paused for "
            "20 seconds (hidden window, idle, covered) becomes a picture of itself "
            "and carries on when you come back. Movement sets how much it moves and Intensity "
            "how strong it is. Page background in Theme & colour sets the "
            "colour under it. Performance mode and Battery-efficient mode both "
            "stop it, and so does Motion off. The dashboard's constellation "
            "moves only while it is on; off, it is a still picture."
        ),
        "badge": {"label": "Animated background", "section": "appearance", "target": "bg-style-row"},
    },
    {
        "id": "themes",
        "keywords": (
            "save a theme", "my own theme", "custom css", "text size",
            "corner rounding", "zoom level", "colour scheme", "color scheme",
            "build a scheme", "border style", "shadow", "interface animations",
        ),
        "body": (
            "Settings, Appearance. Themes: each theme is a tile of four overlapping dots (the page, its card, the accent and the ink) over its name; press the eye in a theme's corner to see it on the whole app, then Apply or Cancel, "
            "press Random theme for a whole theme at random, save and switch your own, or Export look and Import look to move one between devices as a JSON file (an import skips what it cannot read and says which, with Undo). Theme & "
            "colour: Palette (Mix palette, accent and density picks those three at random, with Undo), Mode (light, dark or system), Accent colour or a "
            "custom one (a colour a button's words cannot be read on is "
            "offered at the nearest shade that can), Page background, and "
            "Build a scheme from one colour. "
            "Typography & layout: Text size, Font (System, Serif, Mono, Arial, "
            "or Readable, the Atkinson Hyperlegible face), Density, Line spacing and Line width (Tight, Normal or Roomy, and Narrow, Standard or Wide, for notes and documents you read), Corner rounding, "
            "Zoom, Border style and Shadow intensity (Text size, Density and Zoom "
            "are marked On this device: a phone and a computer each keep their "
            "own, while colours and fonts follow you). Effects & accessibility: "
            "Performance mode, the glass's sheen, blur and opacity, Progress "
            "indicators, Motion (Follow the system, Always on or Off: it stills "
            "Atlas, the background art, the graph and the whiteboard when your "
            "browser asks for reduced motion, and Always on keeps them moving "
            "anyway) and Interface animations (on by default: "
            "a button's press, menus and dialogs opening, a chevron turning, a "
            "tab's sliding marker, even with Motion off bar a menu's spring and "
            "its rows arriving in turn; off makes them instant) with Reveal "
            "replies under it (a reply no model wrote rises into place). Advanced has "
            "Custom CSS. Ctrl+Shift+L "
            "switches light and dark from anywhere."
        ),
        "badge": {"label": "Appearance", "section": "appearance"},
    },
    {
        "id": "tabs-overview",
        "keywords": (
            "tabs", "what tabs", "overview", "getting started", "where do i start",
            "what is tessellate", "what is memorymap", "what does this app do", "tour of the app",
            "parts of the app",
        ),
        "body": (
            "Tessellate is a notebook on your own computer, where a local AI files your notes "
            "and answers questions about them. It has seven tabs along the top. Dashboard: your day at a "
            "glance and quick actions. Notes: capture and your notes list. "
            "Chat: ask and let the agent act on your notes. Graph: how notes "
            "connect. Library: documents, whiteboards, mind maps, files and "
            "everything else in one place. Timeline: everything by date. "
            "Reminders: what is due. Settings (the gear, or Ctrl+,) holds the "
            "rest, and Atlas the guide (this chat) answers how-to questions "
            "from any tab. Press t then a letter to jump between tabs (o opens the OCR workspace, y the tray, w a new note, f Find anything, k the calculator), and "
            "Settings, Help starts the guided tour."
        ),
        "badge": {"label": "Help", "section": "help"},
    },
    {
        "id": "phone-nav",
        "keywords": (
            "phone", "on my phone", "mobile", "bottom bar", "tab bar", "bottom tabs",
            "more button", "where is the graph on my phone", "where is the timeline",
            "phone menu", "app menu",
        ),
        "body": (
            "On a phone the tabs are a bar along the bottom: Dashboard, Notes, "
            "Chat, Library and More, last. More opens a sheet: Graph, Timeline "
            "and Reminders first, then Ask the agent, Commands, Guide, Agent "
            "activity while the agent runs, and Settings. More is lit while one "
            "of its pages is showing, and carries the count of reminders due. "
            "Press the tab you are on again to go back to the top of its page. "
            "The bar shrinks to icons while you scroll down and gets its words "
            "back on the way up. The app menu (the three dots at the top right) "
            "holds Forward, Recent places, Redo, Find, light or dark, the "
            "Settings window, Lock, and Quit; Back and Undo sit in the top bar."
        ),
        "badge": {"label": "Help", "section": "help"},
    },
    {
        "id": "settings-overview",
        "keywords": (
            "settings", "where are the settings", "open settings", "find a setting",
            "search settings", "preferences", "cant remember what its called",
            "find by meaning",
        ),
        "body": (
            "Settings opens from the gear in the top bar or Ctrl+,. Its sections "
            "are grouped: AI (Models, Search and index, Personas, Skills, Tools "
            "it can use, What it remembers, What it learned, Web search), "
            "Notebook (Profile, General, Templates, Import & export), Look and "
            "feel (Appearance, Keyboard shortcuts), Privacy and security "
            "(Account & security, Privacy), System (Packages, Background tasks, "
            "Logs) and Help and About. The search box at the top of the list "
            "finds a setting by any word in it or by what it does, with words "
            "that mean the same (\"night\" or \"darker\" finds the theme, "
            "\"battery\" the battery-efficient mode, \"back up\" Backups, "
            "\"the little guy in the corner\" the companion, and a slip such as "
            "\"chnage pasword\" the password), and "
            "lists the matching settings under it, each opening where it sits; with "
            "an embedding model on (Settings, Search and index), up to three more found by "
            "meaning follow under Close in meaning. A long section lists its "
            "groups under its own name in that list: press one to go to it, and "
            "the one you are reading is marked as you scroll. On a phone the "
            "section picker holds the same groups under the section you are in. "
            "A section with several folded groups has Expand all at the top of "
            "its page (Collapse all once every group is open)."
        ),
        "badge": {"label": "General", "section": "general"},
    },
    {
        "id": "lock",
        "keywords": (
            "auto-lock", "auto lock", "change my password", "reset password",
            "other devices", "on my phone", "another computer", "sessions",
            "lock everywhere", "re-encrypt", "new key", "rotate key",
            "recovery key", "make a recovery key",
        ),
        "body": (
            "Settings, Account & security. Signing in: ask for a password when "
            "the app opens (private notes and other devices always ask). Other "
            "devices: let a phone or computer on your network open the app, "
            "always with your password, over https on port 8443, and only on "
            "networks you trusted (the wifi icon in the status bar, Alt+L). "
            "Ask before a new device signs in holds one until you Allow; "
            "Allowed devices have Remove. Loosening "
            "needs your password. The first "
            "visit warns that the certificate is not trusted: compare its "
            "SHA-256 fingerprint with the one under the switch before you "
            "continue, and Regenerate certificate makes a new one. Trust this certificate on your phone downloads it, and its ? says how to install it on iPhone and Android. If this computer's address changes, the app makes a new certificate straight away. Change your password (private "
            "notes move across; a new one needs at least 8 characters, and an "
            "easy one gets a warning). Re-encrypt private notes (Settings, Account & security) makes "
            "a new encryption key and moves every private note onto it, so an old "
            "backup stops opening them; every other session is signed out. Sessions: Auto-lock when idle, from 5 minutes "
            "to 12 hours, and Lock everywhere now; the lock in the top bar "
            "locks at once. "
            "Recovery key: Make a recovery key (or Replace it) "
            "asks your password and shows a key once, to copy or download and "
            "keep away from this computer; the old one stops working. Forgot "
            "your password? on the lock screen, on this computer only, has two "
            "paths: the recovery key and a new password keeps private notes "
            "and hands you a new key; I don't have it asks for a six-digit code Tessellate prints in its terminal or log (ten minutes, one use) and then resets the password like "
            "python -m tessellate --reset-password, which keeps ordinary notes, "
            "documents, boards and settings, leaves private notes sealed for "
            "good, and turns other devices off."
        ),
        "badge": {"label": "Account & security", "section": "account"},
    },
    {
        "id": "model-bench",
        "keywords": (
            "model bench", "test my models", "which model is best", "compare models",
            "best model for my notes", "benchmark", "try my models",
        ),
        "body": (
            "Settings, Models, Test my models runs your installed models on your "
            "own notes and recommends one. Tick the models to compare and press "
            "Run the test: each model files a sample of the notes you filed "
            "yourself, answers a question about each one from three notes shown "
            "to it, and calls a search tool five times. Every row shows Filing, "
            "Answers and Tools as a percentage, how long an answer took and how "
            "many tokens it used, with the first few things it got wrong, so you "
            "can check the recommendation. Use this one makes that model answer "
            "in chat. Stop ends a run, and a stopped run makes no "
            "recommendation. It needs at least six filed notes, runs entirely on "
            "this computer, and can be switched off in Settings, What it "
            "learned, What may run, Model bench."
        ),
        "badge": {"label": "Test my models", "section": "models", "target": "bench-box"},
    },
    {
        "id": "margin-reader",
        "keywords": (
            "margin reader", "margin", "notes beside my writing", "related notes while writing",
            "did I write this before", "contradiction while writing", "second reader",
        ),
        "body": (
            "The margin reader reads with you while you write a document. Turn "
            "it on from the document's menu, While you write, Margin reader. A "
            "column to the right of the editor then shows at most three cards "
            "about the paragraph the caret is in, a moment after you stop "
            "typing: Repeats (you already wrote this in another note), Differs "
            "(the same thing with a different number or a not, or what the "
            "model judges a disagreement), Answers (it answers an open question "
            "from your notes), Date (a time in the paragraph, with Make a "
            "reminder) and Related. Each card has Open and Not this; nothing is "
            "ever written into your text. In a note's edit form the margin "
            "button beside the word count is the same switch, and the cards "
            "sit under the text. It is off until you turn it on, "
            "remembered on this device, and can be switched off everywhere in "
            "Settings, What it learned, What may run, Margin reader."
        ),
        "badge": {"label": "What it learned", "section": "learned"},
    },
    {
        "id": "web-clipper-bookmark",
        "keywords": (
            "bookmarklet", "clip to tessellate", "clip to memorymap", "clip a page from my browser", "browser extension",
            "save this page", "clipper bookmark", "keep a web page", "clip a web page",
            "from my browser", "clip from the browser",
        ),
        "body": (
            "Settings, Import & export, Web clipper has a bookmark called Clip to "
            "Tessellate (typing clipper in the command palette opens it). Drag it to your browser's bookmarks bar (or press Copy the "
            "bookmark and make a bookmark with it as the address). On any page, "
            "press it: a small Tessellate window opens beside the page with its "
            "title and address, and Save as a note keeps the page's main text, or "
            "only the text you had selected. Your own browser sends the page, so "
            "nothing is fetched from the web: it works with web search off and on "
            "pages you signed in to see. No browser extension is needed. A clipped "
            "note opens with properties (source, site, author, published and the day "
            "you clipped it, whichever the page names), so you can find and sort "
            "clips by them. Atlas treats its text as someone else's words "
            "and never follows instructions in it, and clipping the same page again "
            "points you to the note it made the first time."
        ),
        "badge": {"label": "Web clipper", "section": "data", "target": "web-clip-box"},
    },
    {
        "id": "import-apps",
        "keywords": (
            "import from notion", "notion", "evernote", "enex", "apple notes", "obsidian vault",
            "import from another app", "move my notes from", "switch from notion", "switch from evernote",
            "import report", "what was skipped", "memorymap folder", "stop the import",
        ),
        "body": (
            "Settings, Import & export, Import from another app has five buttons: "
            "From Notion (choose the zip from Notion's Export, Markdown & CSV), "
            "From Obsidian (choose the vault folder), From Evernote (choose the "
            ".enex files you exported), From Apple Notes (choose the folder an "
            "exporter app wrote, one HTML, Markdown or text file per note) and "
            "From a Tessellate folder (the zip Export notebook folder writes, every "
            "field back as it was). "
            "Choosing opens a preview: every note it found with its first words "
            "and a tick (a note already here starts unticked), Select all or none, "
            "then Import N. Closing it imports nothing. After the import, the "
            "toast's Undo moves exactly those notes to the recycle bin. Folders and notebooks become categories, "
            "tags and dates come along where the app wrote them, and links between "
            "Notion pages become wiki links. Each note remembers where it came from, "
            "so importing the same export again adds nothing twice; the toast counts imported, skipped and failed. Imported text is treated as someone else's "
            "words: Atlas never follows instructions written in it. A note's day "
            "comes from the export where it says one with its year: a daily "
            "note named 2024-03-14, a date: or Created: line; that is its day "
            "on the Timeline, and \"tomorrow\" in it means the day after it was "
            "written. The import's summary names the people and places it read. "
            "Every import keeps a report of what it read, wrote, skipped and found "
            "already here, each skipped file named with why: See the report when it "
            "ends, or Report in the Activity panel. "
            "A long import shows in the Activity panel with Stop; the notes made "
            "before Stop stay."
        ),
        "badge": {"label": "Import from another app", "section": "data", "target": "import-app-box"},
    },
    {
        "id": "simple-mode",
        "keywords": (
            "simple mode", "fewer tabs", "hide tabs", "hide the tabs", "tabs i do not need", "too many tabs", "simpler", "beginner",
            "where did the graph go", "where did the timeline go", "where are reminders",
        ),
        "body": (
            "Settings, General, Simple mode: Show only Dashboard, Notes, Chat and "
            "Library. It hides the Graph, Timeline and Reminders tabs, the "
            "Library's Boards & maps, What it learned and the advanced response "
            "settings until you want them. Nothing is turned off: every hidden "
            "place still opens from the command palette (Ctrl+K), and reminders "
            "still ring. It is remembered on this device; turn it off in the "
            "same place to bring the tabs back."
        ),
        "badge": {"label": "Simple mode", "section": "general", "target": "simple-mode-box"},
    },
    {
        "id": "usage-ledger",
        "keywords": (
            "what you use", "what i use", "usage", "most used", "never use", "unused features",
            "is it tracking me", "telemetry", "analytics",
        ),
        "body": (
            "Settings, General, What you use counts each tab you open and each "
            "command you run from the palette, on this computer only, in a small "
            "file in your data folder: names and dates, never what you typed, "
            "and never sent anywhere (there is no telemetry). It lists your most "
            "used tabs and commands and the ones not used in 90 days, and the "
            "command palette lists the commands you use most first. Clear the "
            "counts forgets every one."
        ),
        "badge": {"label": "What you use", "section": "general", "target": "usage-box"},
    },
    #: Brief 89: the Statistics page and the palette's small tools, each
    #: written from the controls' own words (statistics.js, utility-tools.js).
    {
        "id": "statistics",
        "keywords": (
            "statistics", "stats", "notes per month", "word count of my notebook", "notebook statistics",
            "this week", "weekly review", "week in review", "growth per month", "usage statistics",
        ),
        "body": (
            "Statistics counts your notebook with no model: notes, words, tags, "
            "categories, documents, links and notes with no link, a chart of notes "
            "made per month over the last year, reminders made, done, open and late, "
            "and what you use on this computer (features used, uses counted, and "
            "the ones not used lately). The charts answer you: hover or focus a point "
            "or bar for its period and exact value, move between them with the arrow "
            "keys, and click or press Enter to open it (a month opens the Timeline "
            "there, a feature bar opens that feature). The counts open what they count, "
            "the Range menu sets how far back the growth chart goes (3 months, a "
            "year, or since the first note), and each week row has a small line of "
            "this week's days against last week's. The Ask about your statistics box at "
            "the top answers from the same counts with no model: try Summarise my "
            "month, What do I use most? or Am I writing more than last month?, or ask "
            "how many notes you wrote in July, or when you wrote your first or newest note. Clear (shown once there is an answer) empties the box. This week compares notes made, words "
            "written and reminders done since Monday with the whole of last week. "
            "Open it from the Statistics button under the Dashboard's Activity "
            "heatmap (or a click on the heatmap), the This week card's All "
            "statistics, or Statistics in the command palette (Ctrl+K). Ask "
            "\"notebook stats\" or type /stats in Chat, Ask or the popup agent and "
            "the answer carries the figures as cards with small charts, and Open "
            "Statistics in their head. Private and binned notes are not counted."
        ),
        "badge": {"label": "Dashboard", "tab": "dashboard"},
    },
    {
        "id": "calculator",
        "keywords": (
            "calculator", "open the calculator", "get to the calculator", "do a sum", "keypad", "unit converter",
            "convert units", "currency converter", "work out a sum",
            "calculator and equations", "equation tab", "insert as equation",
        ),
        "body": (
            "Calculator and equations is one dialog with three tabs: Sum, "
            "Units and Equation. Open it from the command palette "
            "(Ctrl+K, Calculator and equations, or Convert units for the "
            "Units tab; both are also in the / menu), by typing /calc with "
            "nothing after it, with Open the calculator under an answer that "
            "worked something out, or with Alt+= in a note, a document, a "
            "board's text, Chat or Ask, which opens it on the Equation tab over "
            "that box. Sum takes a sum typed or keyed (12 * (3 + 4), 15% of "
            "80, 5 km to miles), shows a preview as you type and says how it "
            "read it; Enter or = keeps it in History. Scientific adds trig, logs, powers, roots, a "
            "factorial, pi and e, Degrees or Radians and a memory (MC, MR, "
            "M+, M-), worked out with no model. "
            "Each answer has Copy, and each tab has a History under "
            "its fields (the last twenty, kept on this device): press a row to "
            "put it back in the fields, or Copy it, Edit it (the next keep "
            "replaces that row) or Remove it; Clear empties the list and Undo "
            "brings it back. "
            "Every tab ends in the same row: a line saying where Insert writes, "
            "then Copy, Insert as equation (Sum and Units; the sum with its "
            "result as an equation) and Insert. When the dialog was opened from "
            "a text box, Insert writes there; with none open the line says so "
            "and Copy is the way out. The keypad is one Tab stop: the "
            "arrow keys move around it. Units picks a kind (length, "
            "weight, currency and more), an amount and two units, with a swap "
            "button; currency rates are set by hand and dated, not today's rate. "
            "Time zone takes a time and two places (09:00, London, Tokyo), "
            "offline. "
            "The Equation tab is the equation editor (see Equation editor): when "
            "an equation is made of numbers, its value is shown under it, as in "
            "Sum. The arrow keys, Home and End move "
            "between the tabs. The Dashboard's Calculator widget draws "
            "Sum and Units on the page, with Copy but no Insert; Convert is "
            "Units alone."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    },
    {
        "id": "currency-rates",
        "keywords": (
            "currency rates", "exchange rates", "edit the rates", "rates table",
            "currency table", "update the currency", "exchange rate",
        ),
        "body": (
            "Currency conversions ('50 usd in eur', Units, /calc) read one table and "
            "say its date in the answer, for example 'at the rates from 1 October'. "
            "Nothing is fetched. To change it, open Settings, Search and index, "
            "Currency rates: pick the day the rates are from, then write one line per "
            "currency, a code and how many units of it make one US dollar (EUR 0.92). "
            "Save rates keeps it; a code you leave out keeps its built-in rate. Reset "
            "to the built-in table puts back the rates this version shipped with."
        ),
        "badge": {"label": "Search and index", "section": "searchindex", "target": "currency-rates-group"},
    },
    {
        #: INBOX 1481: a chat that is not kept (chat-private.js, `ChatRequest.private`).
        "id": "chat-private",
        "keywords": (
            "private chat", "incognito", "temporary chat", "not saved", "off the record",
            "chat without history", "no memory", "private session", "discard a chat",
        ),
        "body": (
            "A private chat is a chat that is not kept. Start one from the gear "
            "under the message box (Private chat), from the chat's ⋯ menu "
            "(Private chat), or from the command palette (Ctrl+K, Private chat). "
            "A Private mark in the chat's head says it is on, and the empty chat "
            "says: Private chat. Nothing here is saved or remembered. While it "
            "is on, the chat is not saved in the chat list and does not come "
            "back after a reload, the question is not offered again under Ask "
            "again, the notes it read are not counted as used, and the AI "
            "neither reads what it was taught (Settings, What it remembers, and "
            "what you said of insights and sentences) nor can save anything "
            "new about you. It still answers from your notes, and Agent mode "
            "still works on them. New chat, opening another chat, Delete this "
            "chat or closing the page asks once to discard a private chat that "
            "has messages; the same switch ends an empty one. Save this chat as "
            "a document, in the chat's ⋯ menu, keeps a copy if you want one."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    },
    {
        #: INBOX 1727: membership is the privacy (private-spaces.js, routes_private_spaces.py).
        "id": "private-spaces",
        "keywords": (
            "private space", "vault space", "lock a space", "locked space", "unlock private spaces",
            "make a space private", "seal a space", "secret space", "new notes start private", "private by default",
        ),
        "body": (
            "A private space seals everything in it with your vault password, "
            "as a private note is: its notes, documents and boards. Turn on "
            "Private in New space, or in Edit space (the pencil beside a space "
            "in the picker); turning it on asks once with the count of what "
            "gets sealed. A locked private space shows its name with a lock and "
            "nothing else: its notes, documents and boards are out of search, "
            "the graph, the timeline, the dashboard, exports and Atlas, and a "
            "reminder from it says A private reminder. Opening it asks for your "
            "vault password, or your PIN or Windows Hello on this computer; one password opens "
            "every private space. They lock again after the idle minutes in "
            "Settings, Account & security (Lock private spaces when idle, ten "
            "by default) and always when the window closes. Inside one, a "
            "note's Make private is locked on: Move it out of this space to "
            "share it. Moving notes out asks Keep it private (the default) or "
            "Make it ordinary, and a note that was private before it came in "
            "stays private. Turning Private off asks the same. Atlas reads a "
            "private space's notes only in a chat opened inside it while it "
            "is unlocked, and that chat is sealed with them, as are its "
            "reminders. A link from an ordinary note to one inside shows as A "
            "private note while it is locked. A locked private space cannot "
            "be deleted or brought back with Undo. An export leaves it out "
            "unless it is unlocked and you ask, and backups keep it encrypted. "
            "New notes start private (Account & security, off by default) seals "
            "each new note from its first save, unfiled and unindexed. Make all "
            "notes private, beside it, locks every ordinary note after a confirm, "
            "and the Private row in the Notes sidebar lists them."
        ),
        "badge": {"label": "Account & security", "section": "account"},
    },
    {
        "id": "timer",
        "keywords": (
            "timer", "countdown", "stopwatch", "pomodoro", "set a timer", "start a timer",
            "stop the timer", "time how long", "clock", "alarm", "set an alarm", "laps", "pause a timer",
            "lock screen timers", "show reminders on the lock screen",
        ),
        "body": (
            "The Clock is one window for timers, a stopwatch and alarms. Chat opens "
            "it for \"set a timer for 25 minutes\". Open it "
            "from the command palette (Ctrl+K): Start a timer, Start a "
            "stopwatch or Set an alarm, or from the \"/\" menu in Chat, or by "
            "pressing the timer chip in the status bar, which opens the panel "
            "and never stops the clock. Type a length in the palette, such as "
            "timer 10 minutes, 90s timer or countdown 2h, and Enter starts it. "
            "Drag its title bar to move it or its corner to resize it. "
            "Timer: press 5, 10, 15, 25 or 45 minutes, or type a length (10, "
            "90s, 1h30m or 1:30) and press Start. Several timers can run at "
            "once, each with Pause, Resume, Reset and Stop in the Running list "
            "(a stopped one comes back with Undo), and they survive a reload. "
            "When one runs out it says so, notifies and chimes (Sound at the "
            "end turns the chime off). Stopwatch: Start counts up, Lap writes "
            "down the time so far and the lap, Pause holds it and Reset puts it "
            "back to its start. Alarm: pick a time and a label and press Set "
            "alarm; it makes an ordinary reminder, today or tomorrow. The "
            "Dashboard's Clock widget (Customise, Widgets) draws the same tabs "
            "on the page, over the same running clocks; the Stopwatch widget "
            "is the stopwatch alone (Start, Pause, Lap, Reset, with the laps "
            "listed) and the Alarm widget is the alarm alone (a time and a "
            "label, kept as a reminder). The "
            "Dashboard's Focus timer is a separate ring timer: 5, 15, 25, 50 or "
            "60 minutes, or type any length from 1 to 180 (minus and plus step "
            "one minute below 10 and five above), a chime at the end, Breaks, "
            "and the minutes focused today. While the app is locked nothing is "
            "announced; a timer that ran out speaks after you unlock. Settings, "
            "Account & security, Show timers and reminders on the lock screen "
            "(off by default) lists timers and the next few reminders by "
            "title and time, except private notes', never a note's text."
        ),
        "badge": {"label": "Dashboard", "tab": "dashboard"},
    },
    {
        #: WORLD_CLASS_PLAN 25c: the dashboard's first steps (first-run.js).
        "id": "first-steps",
        "keywords": (
            "first steps", "start in three steps", "sample notebook", "sample notes", "example notes",
            "remove the sample notes", "demo notes", "try it out", "hide these steps", "get started", "setup popup", "closed the welcome", "checklist",
            "hide get started", "mark all as done", "show get started", "hide first steps", "show first steps", "three steps to a working notebook", "fold the first steps",
        ),
        "body": (
            "A new notebook's Dashboard shows First steps, a card titled Three steps to a working notebook with a checklist: 1. Your name, "
            "2. Write a note, 3. Ask your notebook, with a bar showing how many are done. Each is ticked "
            "when it is done, and none of them needs an AI model: Ask answers from your notes' own "
            "words, and saving your first note offers Ask about it beside "
            "Saved. The caret folds the steps to one line. The card's ... menu holds Try a sample notebook, which adds eight example notes, tagged "
            "sample-notebook, to explore (ask \"where is the spare key?\", see two "
            "linked notes in the Graph); it is offered until you write your own "
            "first note. Remove the sample notes moves them all to the bin, where "
            "Restore brings one back, and takes away the categories they made. The steps leave once all three are done and "
            "the sample notes are gone. Mark all as done ticks every step and puts the card away; Hide first steps "
            "hides the card and the dock's First steps button. Settings, Help (Show first steps), Customise, the hide notice's Show again or the palette (Ctrl+K, Show first steps) brings them back. "
            "Until then the dashboard's First steps menu (beside Customise) lists the same three, ticked as "
            "they are done, with Take the tour and Replay the welcome, and the same checklist "
            "is the first row of the notifications bell until all three are done."
        ),
        "badge": {"label": "Dashboard", "tab": "dashboard"},
    },
    {
        #: WORLD_CLASS_PLAN 25c: the Guide's topics as one page (manual.js).
        "id": "manual",
        "keywords": (
            "manual", "user manual", "user guide", "documentation", "docs", "handbook",
            "print the help", "read all the help", "every help topic", "help page",
        ),
        "body": (
            "The manual is every topic Atlas answers from, on one page: Ctrl+K or "
            "Find anything, Open the manual; Settings, Help, Open the manual; or "
            "Open the manual in the Guide's More actions menu. It can also sit on "
            "the dashboard as a quick link (Quick access, Customise). "
            "The contents on the left jump to a group, the search box keeps only "
            "the topics that hold every word you type or what the words mean "
            "(\"trash\" keeps the bin's topic), those whose name holds them "
            "first, and the printer button "
            "prints what is shown (or saves it as a PDF). It is made from the "
            "Guide's own topics, so the two never disagree. What changed in each "
            "version is under Settings, About, What's new."
        ),
        "badge": {"label": "Help", "section": "help"},
    },
    {
        "id": "live-captions",
        "keywords": (
            "live captions", "captions", "subtitles", "live transcription", "transcribe live",
            "write what i say", "speech to text live", "stop the captions",
            "how do i get live captions", "where are live captions", "open live captions",
        ),
        "body": (
            "Press Captions in Library, Recordings, or Live captions in a Voice "
            "note before you record; it is also in Tools and features, Audio, "
            "and in the command palette (Ctrl+K, type captions); Edit quick access "
            "can add it to the Dashboard as a tile. A bar appears "
            "over whatever you are looking at and writes what the microphone "
            "hears, on this computer, never over the internet. The bottom line "
            "is still being written; the three above it are done. Copy takes "
            "everything said so far, and Stop (or the palette row again) saves "
            "it as a note tagged captions. Translate, once the offline translator is "
            "installed (Settings, Packages), writes each finished line in Spanish "
            "under the captions; the note keeps what was said. Keep the audio of live "
            "captions (off until you turn it on, in Settings, General, Microphone) makes Stop "
            "save the audio too, in Library, Recordings, with the lines as its transcript. "
            "While a voice note records, the same "
            "captions write its words into the dialog as you speak, and the "
            "full transcript replaces them after. Captions need the Live captions "
            "bundle: Settings, Packages, Install on Live captions fetches the speech "
            "engine and a 32 MB English model in one click, and the first caption "
            "starts it on this computer (it stops when you have finished with it). "
            "On a computer with no build for it (an Intel Mac, Windows on Arm) the "
            "row says so. Without it the buttons are not shown and nothing is recorded."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    {
        "id": "audio-overview",
        "keywords": (
            "audio overview", "natural voice", "read my notes aloud", "podcast", "brief before a meeting", "meeting brief",
            "make an audio overview", "piper", "read aloud voice", "listen to my notes",
        ),
        "body": (
            "Make an audio overview in the command palette (Ctrl+K) reads your notes aloud and saves the reading as a "
            "recording in Library, Recordings, marked overview, with its lines timed like a transcript. Say what it is "
            "about (notes holding those words; empty means the newest notes) and how long (about 1, 3 or 5 minutes); "
            "tick A brief before a meeting for a short run-down of those notes instead. Nothing is added to your words: "
            "it is your own sentences under a fixed frame (First, Next, Last), with no AI model, and private and binned "
            "notes are never read. Stop ends it and keeps nothing. It needs the Natural voice package (Settings, "
            "Packages: an engine and a 64 MB voice, fetched once, then everything runs on this computer). With it "
            "installed, Settings, General, Read aloud, Voice can switch an answer's Read aloud from this browser's "
            "voices to the natural one; the speaking speed applies to the browser's voices only. "
            "Browser voice, in the same place, picks which of this computer's own voices speaks, in chat and in "
            "documents (Automatic follows the page's language)."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    {
        "id": "folder-sync",
        "keywords": (
            "sync", "sync between computers", "sync folder", "two computers", "usb stick", "syncthing", "no server",
            "merge notes", "another computer", "sync conflict", "edited on both",
        ),
        "body": (
            "Sync between computers (Settings, Import & export; or the command palette, Ctrl+K) has two ways in with "
            "one result: Sync over the home network (Two computers) when both are on the same network, and Sync through "
            "a folder when they are not: a USB stick, a Syncthing folder or a cloud drive's folder on each computer. "
            "Press Sync through a folder, type the folder and a sync passphrase (at least 8 characters, the same on "
            "every computer; it is never saved) and press Sync now. Each computer writes only its own file there, "
            "encrypted, and reads the others'; press it on each computer to bring them level. Notes, documents, boards "
            "and attached files travel; private notes never go into the folder, and a note, document or board made "
            "private after it was shared is withdrawn from the other computer, with its History there (one changed "
            "there is kept and says so). A change made on both computers keeps "
            "the later one and the other words stay in History, so nothing is lost; a note moved to the bin on one "
            "lands in the other's bin, and a file removed on one is removed on the other. A file that cannot be opened "
            "(a different passphrase) is counted and left alone. A notebook folder copied to another computer has the "
            "same sync id and is refused, and so is a second copy writing the same file in the folder: on one copy, press "
            "Make a new sync id (Settings, Import & export, Sync between computers; computers paired with it pair again), "
            "then sync again. "
            "The last-synced line under the group says when and which way."
        ),
        "badge": {"label": "Import & export", "section": "data"},
    },
    {
        "id": "count-words",
        "keywords": (
            "word count", "count words", "character count", "how many words", "reading time",
            "count the selection", "how long is this",
        ),
        "body": (
            "Select text in any editor (a note, the Capture box, a document) and "
            "run Count words from the command palette (Ctrl+K): it says the "
            "words, the characters with and without spaces, and the reading "
            "time, counted the way wc counts. With nothing selected it counts "
            "the whole editor you were in. The Capture box and a document also "
            "show a running count as you type; a document leaves out its "
            "Markdown marks, code and comments, and so matches its Document "
            "statistics."
        ),
        "badge": {"label": "Notes", "tab": "notes"},
    },
    {
        "id": "translate-offline",
        "keywords": (
            "translate this", "translate offline", "offline translation", "translate without a model",
            "translate to spanish", "bergamot", "ai free translation",
        ),
        "body": (
            "Select a passage in a note, a document or a reading and run "
            "Translate this from the command palette (Ctrl+K): it turns "
            "English into Spanish on this computer, with no model, in about a "
            "second, and Copy or Replace the selection puts it to use. With "
            "nothing selected it takes the whole editor you were in. It needs "
            "Translate offline, a 27 MB download in Settings, Packages "
            "(Languages); until then the row says so and opens that page. "
            "In a document, a flagged word's Translate this passage uses it "
            "too once installed, and asks your model in the chat before. "
            "Other languages: the Writing room translates with your model."
        ),
        "badge": {"label": "Packages", "section": "extras"},
    },
    {
        "id": "insert-template",
        "keywords": (
            "insert template", "insert a template", "text snippet", "reusable text", "boilerplate",
            "template into a note", "paste a template",
        ),
        "body": (
            "Type insert template (or template and part of its name) in the "
            "command palette (Ctrl+K) to list your templates; Enter puts the one "
            "you choose where your cursor was, in any editor, with {date}, "
            "{{time}} and {{clipboard}} filled in. With no editor open it goes "
            "into the Capture box. The templates, yours and the built-in ones, "
            "are in Settings, Templates, where you write, edit and reset them."
        ),
        "badge": {"label": "Templates", "section": "templates"},
    },
    {
        "id": "capture-anywhere",
        "keywords": (
            "capture from anywhere", "global hotkey", "global shortcut", "system shortcut",
            "capture without opening", "note from another app", "--capture",
        ),
        "body": (
            "Settings, Keyboard shortcuts, Capture from anywhere shows the command "
            "for this install (tessellate --capture, with its full path) and a "
            "Copy button. Give that command a key in your system's own keyboard "
            "settings: on Windows a desktop shortcut with it as the target and a "
            "Shortcut key, on macOS a Shortcuts action, on Linux a custom keyboard "
            "shortcut. Pressing the key over any app opens a one-line box on the "
            "Tessellate that is already running; Enter saves the note, filed like "
            "any other, and the box closes. On a phone, Share to Tessellate does "
            "the same."
        ),
        "badge": {"label": "Capture from anywhere", "section": "shortcuts", "target": "capture-anywhere-box"},
    },
    {
        "id": "running-copies",
        "keywords": (
            "running copies", "other copies", "another copy", "second copy",
            "port in use", "port 8000", "already running", "shut down a copy",
            "close another copy", "stuck copy", "next free port",
        ),
        "body": (
            "Settings, About, Running copies lists the other copies of "
            "Tessellate running on this computer, each with its port, when it "
            "started and its data folder, and says so when there are none. "
            "Shut down asks that copy to quit the way its own Quit does. This "
            "copy is marked and has no Shut down; use Quit for it. When the "
            "launcher finds its usual port taken it uses the next free one, "
            "so a copy left running in the background is found here. Only "
            "copies that are really running are listed: a leftover from a "
            "copy that crashed is removed when the list opens, and Shut down "
            "on one just clears it."
        ),
        "badge": {"label": "Running copies", "section": "about", "target": "running-copies-group"},
    },
    {
        "id": "install-app",
        "keywords": (
            "install", "install the app", "install as an app", "add to home screen",
            "home screen", "pwa", "own window", "app icon", "share sheet",
            "share to tessellate", "share to memorymap", "not running on this computer", "offline page",
        ),
        "body": (
            "Settings, About, Install as an app gives Tessellate its own window "
            "and icon, and adds it to your phone's share sheet, so a page or a "
            "selection shared to it lands in Capture. The button appears only "
            "when your browser offers the install and the app is not installed "
            "yet; on an iPhone, tap Share, then Add to Home Screen. It is the "
            "same app, still served by the copy running on this computer. When "
            "that copy is not running, the installed app shows a page saying "
            "Tessellate is not running on this computer, with a Retry button, "
            "never an empty notebook: open Tessellate from the Start menu or "
            "the launcher, then press Retry."
        ),
        "badge": {"label": "Install as an app", "section": "about", "target": "about-install"},
    },
    {
        "id": "desktop-companion",
        "keywords": (
            "desktop companion", "companion on the desktop", "companion outside the app",
            "companion in the corner of the screen", "desktop pet", "quick note from the desktop",
            "companion when the window is closed", "show desktop companion",
        ),
        "body": (
            "In the desktop app on Windows and Linux (X11) the companion lives on your desktop while the window is "
            "minimised or in the tray, and goes when it opens. Atlas floats like a wind spirit (others walk the bottom) and sleeps "
            "when you are away, can be picked up and thrown (it tumbles and lands; a hard throw up catches the top, a harder one flies out of sight), "
            "hangs from the top, and peeks up from behind the taskbar, a screen edge or a smaller window. It keeps to a home spot by an "
            "edge for minutes, alive in place, and makes a few trips an hour: walking, running, "
            "out at one edge and in at the other, or through a portal. Let go gently near a title bar and it hangs, "
            "then pulls itself up, swings down or lets go with a start (one hand, on a long hang). Sometimes it climbs onto the top of a window, "
            "dangles its legs over the edge, rides it when you move it and hops off "
            "if you close it (Roam over windows turns that off), and"
            " when a reminder falls due it brings you a card to click. It steps aside for full screen and follows Companion movement "
            "in Appearance (still when Fades only or Windows animation effects are off). Turn it on, on the computer"
            " Tessellate runs on: Settings, Appearance, Show the companion on the desktop, or the tray icon's menu. It works while the desktop app runs. Click it for Quick note (pictures and files wait as removable chips until Save), "
            "Quick search, New reminder, Open today, Open Tessellate, Come here, Take a nap, Sit on a window"
            " or Hide for 10 minutes. Right-click it for Companion (Atlas masculine or feminine, your own or a saved one, summoned once),"
            " Stay here or Roam, Activity (Calm, Usual or Lively; calm takes fewer trips), Settings or Turn off; settings keep it open. Drag it. Menu: Small, Medium, Large; or pull its corner handle (bottom right while it hangs), double-click to reset. Locked, it "
            "shows only Open Tessellate. On Wayland it stays in the app."
        ),
        "badge": {"label": "Desktop companion", "section": "appearance", "target": "desktop-companion-row"},
    },
    {
        "id": "desktop-companion-moods",
        "keywords": (
            "desktop companion sad", "companion lonely", "companion left alone", "companion welcome back",
            "companion confused", "companion dropped near a window", "desktop companion moods",
        ),
        "body": (
            'The companion on the desktop shows how things are going. Leave it alone for fifteen minutes, with no pointer near it and nothing happening, and it looks sad once; it never does while it sleeps or while you type. Come back after ten minutes away and it waves. Let go of it just short of a window top (a drop, not a throw) and, once it is on the floor, it looks confused. With Motion off it stays still.'
        ),
        "badge": {"label": "Desktop companion", "section": "appearance", "target": "desktop-companion-row"},
    },
]

MORE_TOPICS.extend(MID_TOPICS)

#: How each entry is laid out as a system answer. `title` heads it, `path`
#: says where it lives, `steps` are there when there is something to do in
#: order. An entry with no meta is laid out from its id and body alone.
TOPIC_META: dict[str, dict] = {
    "open-questions": {"title": "Open questions", "path": "Notes tab, Questions"},
    "make-a-diagram": {"title": "Making a diagram", "path": "Library tab, Create"},
    "capture": {"title": "Capturing a note", "path": "Notes tab", "steps": (
        "Open the Notes tab (t then n).", "Type into Capture a thought.", "Press Save: a local AI files it and suggests tags.")},
    "ask-chat": {"title": "Asking and chatting", "path": "Chat tab, or Ctrl+Shift+A over any tab"},
    "skills": {"title": "Skills", "path": "Settings, Skills"},
    "graph": {"title": "The graph", "path": "Graph tab"},
    "reminders": {"title": "Reminders", "path": "Reminders tab", "steps": (
        "Open the Reminders tab (t then r).", "Type into Remind me to, with a time such as \"tomorrow at 5pm\".",
        "Press Add; pick a priority or a repeat first if you like.")},
    "dashboard": {"title": "The dashboard", "path": "Dashboard tab"},
    "library": {"title": "The Library", "path": "Library tab"},
    "documents": {"title": "Documents", "path": "Library tab, Documents"},
    "whiteboard": {"title": "Whiteboards", "path": "Library tab, Boards & maps"},
    "timeline": {"title": "The Timeline", "path": "Timeline tab"},
    "memory": {"title": "What it remembers", "path": "Settings, What it remembers"},
    "spaces": {"title": "Spaces", "path": "The picker at the top of the sidebar"},
    "appearance": {"title": "Appearance", "path": "Settings, Appearance"},
    "statusbar": {"title": "The status bar", "path": "Settings, Appearance, Status bar"},
    "shortcuts": {"title": "Keyboard shortcuts", "path": "Settings, Keyboard shortcuts"},
    "models": {"title": "Models", "path": "Settings, Models"},
    "model-bench": {"title": "Test my models", "path": "Settings, Models, Test my models", "target": "bench-box"},
    "margin-reader": {"title": "The margin reader", "path": "A document's menu, While you write, Margin reader"},
    "web-clipper-bookmark": {"title": "Clip a page from your browser", "path": "Settings, Import & export, Web clipper", "target": "web-clip-box"},
    "import-apps": {"title": "Import from another app", "path": "Settings, Import & export, Import from another app", "target": "import-app-box"},
    "simple-mode": {"title": "Simple mode", "path": "Settings, General, Simple mode", "target": "simple-mode-box"},
    "usage-ledger": {"title": "What you use", "path": "Settings, General, What you use", "target": "usage-box"},
    "statistics": {"title": "Statistics", "path": "Dashboard, Activity heatmap, Statistics"},
    "chat-private": {"title": "Private chat", "path": "Chat, the gear under the message box, Private chat"},
    "private-spaces": {"title": "Private spaces", "path": "The space picker, the pencil beside a space, Private"},
    "timer": {"title": "Clock: timer, stopwatch and alarm", "path": "Command palette, Start a timer; the status bar's timer"},
    "calculator": {"title": "Calculator and equations", "path": "Command palette, Calculator and equations; Alt+= in a text box; /calc in Chat"},
    "manual": {"title": "The manual", "path": "Settings, Help, Open the manual"},
    "first-steps": {"title": "First steps and the sample notebook", "path": "Dashboard, First steps"},
    "live-captions": {"title": "How do I get live captions", "path": "Library, Recordings, Captions"},
    "audio-overview": {"title": "Make an audio overview of my notes", "path": "Command palette, Make an audio overview"},
    "folder-sync": {"title": "Sync through a folder", "path": "Settings, Import & export, Sync between computers", "target": "sync-group"},
    "count-words": {"title": "Count words", "path": "Command palette, Count words"},
    "translate-offline": {"title": "Translate this, offline", "path": "Command palette, Translate this"},
    "insert-template": {"title": "Insert a template", "path": "Command palette, insert template"},
    "capture-anywhere": {"title": "Capture from anywhere", "path": "Settings, Keyboard shortcuts, Capture from anywhere", "target": "capture-anywhere-box"},
    "install-app": {"title": "Install as an app", "path": "Settings, About, Install as an app"},
    "running-copies": {"title": "Running copies", "path": "Settings, About, Running copies", "target": "running-copies-group"},
    "storage": {"title": "Where your data lives", "path": "Settings, Import & export"},
    "websearch": {"title": "Web search", "path": "Settings, Web search"},
    "privacy": {"title": "Privacy", "path": "Settings, Privacy"},
    "undo-bin": {"title": "Undo and the bin", "path": "the bin: the Library's Include the bin, or Ctrl+Z right after"},
    "autonomous": {"title": "Autonomous background AI", "path": "Settings, Background tasks"},
    "guide": {"title": "Atlas, the guide", "path": "Status bar, the compass (Ctrl+Shift+H)"},
    "command-palette": {"title": "The command palette", "path": "Ctrl+K"},
    "security": {"title": "Account and security", "path": "Settings, Account & security"},
    "troubleshooting": {"title": "When something does not work", "path": "Settings, Models, then Settings, Logs", "steps": (
        "Open Settings, Models and check a model is connected.", "Start Ollama, LM Studio or a llama.cpp server, pick a model and press Connect.", "Looks out of date or broken after an update: open Settings, Import & export and press Clear app cache.", "Still stuck: open Settings, Logs and press Email it under the support bundle.")},
    "tour": {"title": "The guided tour", "path": "Settings, Help", "steps": (
        "Open Settings, Help, or press Ctrl+K and choose Take the guided tour.", "Press Start the tour for all of it, or a part's row (its name over what it covers) for just that part.", "Next and Back move through it; Finish ends it.")},
    "personas": {"title": "Personas", "path": "Settings, Personas"},
    "templates": {"title": "Templates", "path": "Settings, Templates"},
    "updates": {"title": "Updates", "path": "Settings, About"},
    "name": {"title": "The name, formerly MemoryMap AI", "path": "Settings, About"},
    "notifications": {"title": "Notifications", "path": "The bell in the top bar"},
    "companion": {"title": "The corner companion", "path": "Settings, Appearance, Atlas and faces, Corner companion", "steps": (
        "Open Settings, Appearance, Atlas and faces.", "Pick who it is under Corner companion.", "Right-click it on the page for its menu; Ctrl+Shift+Y shows or hides it.")},
    "image-viewer": {"title": "The picture and PDF viewer", "path": "Library, open a picture or PDF"},
    "companion-throw": {"title": "Throwing the companion", "path": "Settings, Appearance, Atlas and faces, Corner companion"},
    "companion-travel": {"title": "How the companion moves", "path": "Settings, Appearance, Atlas and faces, Corner companion"},
    "companion-remarks": {"title": "What the companion says", "path": "Settings, Appearance, Atlas and faces, Corner companion"},
    "companion-habits": {"title": "The companion's habits and reactions", "path": "Settings, Appearance, Atlas and faces, Corner companion"},
    "companion-activities": {"title": "What the companion does on its own", "path": "Settings, Appearance, Atlas and faces, Corner companion"},
    "desktop-companion": {"title": "The companion on the desktop", "path": "On the computer Tessellate runs on, Settings, Appearance, Corner companion, Show the companion on the desktop"},
    "desktop-companion-moods": {"title": "When the desktop companion looks sad, glad or confused", "path": "On the computer Tessellate runs on, Settings, Appearance, Corner companion, Show the companion on the desktop"},
    "what-is-atlas": {"title": "What Atlas does", "path": "The Chat tab, or Ctrl+Shift+A over any tab"},
    "atlas-look": {"title": "How Atlas looks", "path": "Settings, Appearance, Atlas and faces, Atlas style and Atlas look"},
    "faces": {"title": "Generated faces", "path": "Settings, Appearance, Atlas and faces"},
    "profile": {"title": "Your profile", "path": "Settings, Profile"},
    "tools-setting": {"title": "Tools it can use", "path": "Settings, Tools it can use"},
    "learned": {"title": "What it learned", "path": "Settings, What it learned"},
    "general-settings": {"title": "General settings", "path": "Settings, General"},
    "currency-rates": {"title": "Currency rates", "path": "Settings, Search and index, Currency rates"},
    "search-index": {"title": "Search and index", "path": "Settings, Search and index"},
    "search-engine-moved": {"title": "Old search files", "path": "Settings, Search and index, Old search files"},
    "answer-style": {"title": "Answer style", "path": "Settings, Personas, Answer style"},
    "background-tasks": {"title": "Background tasks", "path": "Settings, Background tasks"},
    "health": {"title": "Health", "path": "Settings, About, Health"},
    "data-folder-check": {"title": "Deleted files and the data folder check", "path": "Settings, About, Health, Data folder check"},
    "maintenance": {"title": "Maintenance", "path": "Settings, About, Maintenance", "steps": (
        "Open Settings, About and find Maintenance.", "Check this computer shows one row per check, each with what to do.", "Reinstall on next start rebuilds the app's Python environment when the launcher next opens it; your notes are not touched.", "Uninstall… shows the steps and the command, with Export my notes first.")},
    "activity": {"title": "Activity", "path": "The status bar's job slot, or the palette, Activity"},
    "packages": {"title": "Packages", "path": "Settings, Packages"},
    "import-export": {"title": "Import and export", "path": "Settings, Import & export"},
    "logs": {"title": "Logs and reporting a problem", "path": "Settings, Logs", "steps": (
        "Open Settings, Logs.", "Open the three dots and press Copy diagnostics, then paste it into your message.", "For a bug that is not about speed, press Email it under the support bundle and attach the bundle.")},
    "find-anything": {"title": "Find anything", "path": "Ctrl+P, or the magnifying glass in the status bar"},
    "background-art": {"title": "The animated background", "path": "Settings, Appearance, Animated background"},
    "themes": {"title": "Themes, colour and type", "path": "Settings, Appearance"},
    "appearance-panel": {"title": "The Appearance panel", "path": "Ctrl+K, Appearance, or right-click the light and dark button"},
    "tabs-overview": {"title": "The app at a glance", "path": "The tabs along the top"},
    "phone-nav": {"title": "The app on a phone", "path": "The bar along the bottom, then More"},
    "settings-overview": {"title": "Finding your way round Settings", "path": "The gear in the top bar, or Ctrl+,"},
    "lock": {"title": "Passwords and locking", "path": "Settings, Account & security"},
    #: Titles for the entries that had none (INBOX 448): Settings, Help lists
    #: every entry by its title, and an id read aloud ("Files images") is not one.
    "files-images": {"title": "Pictures, scans and PDFs", "path": "Library tab, Images and Files"},
    "archive": {"title": "Archiving", "path": "Each item's own menu, and the Library's Archived filter"},
    "voice": {"title": "Dictation, recordings and read aloud", "path": "Notes tab, the microphone; Library, Recordings"},
    "meetings": {"title": "Meeting notes", "path": "Dashboard, New meeting; a meeting's meeting chip"},
    "extract-notes": {"title": "Split text into notes", "path": "Notes tab, Writing room, More, Split into notes"},
    "favourites": {"title": "Favourites", "path": "A note's star"},
    "ocr-workspace": {"title": "The OCR workspace", "path": "Read text, on any image or PDF"},
    "document-history": {"title": "A document's history", "path": "A document's ... menu, History"},
    "writing-checks": {"title": "Spelling, grammar and wording", "path": "The document editor"},
    "spelling-check": {"title": "How spelling is checked", "path": "A flagged word in a document or a note box"},
    "notebook-questions": {"title": "Questions about your notebook", "path": "Chat tab, or Ask on the Notes tab"},
    "studyhelp": {"title": "Study help with no model", "path": "Chat tab, or Ask on the Notes tab"},
    "contradictions": {"title": "Notes that disagree", "path": "Dashboard tab"},
    "write-with-atlas": {"title": "Writing room", "path": "Notes tab, Writing room"},
    "search": {"title": "Searching everything", "path": "Ctrl+P, or the dashboard's search box"},
    "links": {"title": "Linking notes", "path": "Type [[ in a note"},
    "performance": {"title": "When the app feels slow", "path": "Settings, Appearance"},
    "translate": {"title": "Translating", "path": "Notes tab, Writing room"},
    "tags-categories": {"title": "Tags and categories", "path": "A note's own row, or Capture's Filing menu"},
    "code-files": {"title": "Code documents", "path": "Library tab, Documents"},
    "code-completions": {"title": "Completions and snippets in code", "path": "A code document, as you type"},
    "code-tabs": {"title": "Tabs for open code files", "path": "A code document, the strip above the editor"},
    "code-run": {"title": "Running, previewing and testing code", "path": "A code document, Run", "steps": (
        "Open a code document (.js, .ts, .sql, .py, .html, .css, .svg).",
        "Press Run, or Ctrl+Shift+Enter.",
        "Read the Output panel under the editor; Line N goes to the line.",
        "Ctrl+Shift+Y opens the Console tab: type a line and press Enter. It runs in its own worker, apart from any page the file shows. A line still running after 10 seconds is stopped, and the console says so; the output above stays.", "On a CSV document, Query as SQL opens a new SQL document that selects its first 50 rows as a table, and runs it.")},
    "code-panel": {"title": "The code panel: assistant, snippets and text sections", "path": "A code document, Assistant or Snippets (beside Run); a text document, Sections"},
    "debugger": {"title": "Debugging code", "path": "A code document, the gutter beside a line number, F5", "steps": (
        "Open a JavaScript, TypeScript or Python document.",
        "Click beside a line number, or press F9 on it, for a breakpoint.",
        "Press F5; at the stop, F10, F11 and Shift+F11 step, F5 continues.",
        "Read Variables, Watch and the Call stack in the panel's Debug tab.")},
    "mind-maps": {"title": "Mind maps", "path": "Library tab, Boards & maps"},
    "whiteboard-controls": {"title": "Whiteboard keys: tools and moving around", "path": "Library tab, Boards & maps"},
    "whiteboard-selection": {"title": "Whiteboard keys: selection, menus and presenting", "path": "Library tab, Boards & maps"},
    "board-laser": {"title": "The laser pointer while presenting", "path": "A board or map, View, Present, then the pointer button or L"},
    "board-history": {"title": "A board's history, and putting it back", "path": "A board, Board, History…"},
    "board-library": {"title": "The board's library, layers and pages", "path": "A board, the Sidebar button in its top bar"},
    "board-library-saving": {"title": "Saving to the board's library", "path": "A board, Ctrl+Shift+S or right-click, Library"},
    "board-templates": {"title": "Board and map templates", "path": "Library tab, Boards & maps, New's arrow, From a template"},
    "board-format": {"title": "The board's Format panel", "path": "A board, Ctrl+Shift+P or the selection's More menu"},
    "board-connectors": {"title": "Connector bends, connection points and importing diagrams", "path": "A board, Insert, Diagram, Mermaid, draw.io or board SVG"},
    "board-workshop": {"title": "Voting dots and a workshop timer", "path": "A board, Board menu, Workshop"},
    "board-diagram-tools": {"title": "Diagram tools: zoom to the selection, Home, tidy as a tree, change a shape, link a shape, shrink text to fit, clear labels", "path": "A board, Arrange, View, or a selection's More"},
    "board-paste": {"title": "Paste on a board or map: options and Paste special", "path": "A board, Edit, Paste in other ways, Paste special"},
    "mind-map-controls": {"title": "Mind map keys and controls", "path": "Library tab, Boards & maps"},
    "documents-controls": {"title": "Document editor keys and controls", "path": "Library tab, Documents"},
    "documents-replace": {"title": "Replace in every document", "path": "Library tab, Documents, document menu"},
    "live-view-marks": {"title": "Markdown marks in Live view", "path": "Library tab, Documents, Edit, Live"},
    "documents-features": {"title": "Document editor features", "path": "Library tab, Documents"},
    "writing-streak": {"title": "Daily word goal and writing streak", "path": "Library tab, Documents, right-click the status bar counts"},
    "documents-list-styles": {"title": "List styles: dots, circles, squares, dashes and numbering", "path": "Library tab, Documents, List and Numbered buttons"},
    "documents-paste": {"title": "Paste options and Paste special", "path": "Library tab, Documents, document menu"},
    "documents-comments": {"title": "Comments in a document", "path": "Library tab, Documents, sidebar Outline, Comments"},
    "documents-to-note": {"title": "Selection to a note: start a note or add to one", "path": "Library tab, Documents, select text, note button or right-click"},
    "documents-turn-into": {"title": "Turn into: change a block to a heading, list, quote or code", "path": "Library tab, Documents, select text, Turn into"},
    "mind-map-features": {"title": "Mind map features", "path": "Library tab, Boards & maps"},
    "mind-map-import-export": {"title": "Mind map templates, import and export", "path": "Library tab, Boards & maps"},
    "mind-map-study": {"title": "Study the map", "path": "Library tab, Boards & maps, a map's board menu"},
    "mind-map-look": {"title": "How a map's topics look", "path": "Library tab, Boards & maps, a map"},
    "emoji-and-icons": {"title": "Emoji, icons and symbols", "path": "A document's Insert menu, Ctrl+K, the note editor strip; the smiley on a board's or map's tool dock; a topic's Text menu"},
    "board-comments": {"title": "Comments on boards and maps", "path": "An item's right-click menu, Comment…"},
    "sticky-notes": {"title": "Sticky notes and text boxes", "path": "A board's tool dock, Add"},
    "callouts": {"title": "Callouts", "path": "Library tab, Documents"},
    "graph-controls": {"title": "Graph keys and controls", "path": "Graph tab"},
    "graph-display": {"title": "More graph controls", "path": "Graph tab, Options"},
    "graph-categories": {"title": "Categories on the graph", "path": "Graph tab, Map, Tessellation, Tree, Radial"},
    "graph-options-help": {"title": "What the Options sections do", "path": "Graph tab, Options"},
    "graph-draft-map": {"title": "Draft from notes and the map of meaning", "path": "Graph tab, Options, View"},
    "properties": {"title": "Note properties and types", "path": "a note's ⋯, Properties; or the command palette, Note types"},
    "entities": {"title": "People and things", "path": "Graph tab, an entity; or the command palette, People and things"},
    "chat-controls": {"title": "Chat keys and controls", "path": "Chat tab"},
    "context-window": {"title": "How much the chat model reads at once", "path": "Settings, Models"},
    "chat-context": {"title": "When a chat outgrows the window", "path": "Chat tab, the context pill in the header"},
    "wrap-lines": {"title": "Wrap lines in tables and code", "path": "Chat tab, a table or code block"},
    "notes-controls": {"title": "Notes keys, filters and selection", "path": "Notes tab"},
    "library-controls": {"title": "Library controls", "path": "Library tab"},
    "timeline-controls": {"title": "Timeline controls", "path": "Timeline tab"},
    "reminders-controls": {"title": "Reminders controls", "path": "Reminders tab"},
    "dashboard-controls": {"title": "Dashboard controls", "path": "Dashboard tab"},
    "hidden-features": {"title": "Hidden features and power keys", "path": "Everywhere"},
    "quick-note": {"title": "Quick note", "path": "Alt+N, from any tab"},
    "package-models": {"title": "Models in Packages", "path": "Settings, Packages"},
    "spelling-packs": {"title": "Spelling in other languages", "path": "Settings, Packages, or a document's Suggestions panel"},
    "answer-offers": {"title": "Offers and charts in an answer", "path": "Chat tab, or Ask on the Notes tab"},
    "editor-offers": {"title": "Offers while you write", "path": "Notes, Capture, or a note's Edit form"},
    "quick-add": {"title": "Dates and tags read as you type", "path": "Reminders, Quick note, New meeting, Timeline search, the command palette"},
    "note-outbox": {"title": "Saving while the server is away", "path": "Notes tab, above Capture"},
    "attachments": {"title": "Pictures and files in a note", "path": "Capture, or a note being edited"},
    "chat-attach-cards": {"title": "Notes and files attached to a chat message", "path": "Chat, above the box and above a sent message"},
    "chat-model-picker": {"title": "Choosing the model for a box", "path": "Chat, Ask and Writing, beside the mode buttons"},
    "chat-list": {"title": "Finding and sorting your saved chats", "path": "Chat tab, the Chats list"},
    "queued-messages": {"title": "Messages that wait their turn", "path": "Chat, the popup agent or the Guide, the box while a reply is written"},
    "filing": {"title": "How a note is filed", "path": "A note's card, beside its category"},
    "filing-settings": {"title": "Filing switches, and asking when unsure", "path": "Settings, Background tasks; Capture, the Filing options menu"},
    "suggested-tags": {"title": "Suggested tags", "path": "A note's card"},
    "tag-manager": {"title": "Managing tags", "path": "Notes tab, the ... menu, Manage tags"},
    "tidy": {"title": "Tidy: reviews with no AI", "path": "Notes tab, the broom in the dock"},
    "manage-categories": {"title": "Managing categories", "path": "Notes tab, the Categories head in the sidebar"},
    "note-history": {"title": "A note's history", "path": "A note's menu, History"},
    "notes-list": {"title": "Sorting and browsing notes", "path": "Notes tab, Your notes"},
    "card-content": {"title": "What a note's card draws", "path": "Notes tab, a note's card"},
    "addresses": {"title": "Every view has an address", "path": "The browser's address bar"},
    "bookmarks": {"title": "Bookmarks", "path": "Library tab, Bookmarks"},
    "contents": {"title": "Contents, the notebook's outline", "path": "Library tab, Contents"},
    "answers-from-notes": {"title": "Answers from your notes, no AI", "path": "Notes tab, Ask, the AI switch", "steps": (
        "Open Ask on the Notes tab.", "Turn the AI switch off beside the answer length.", "Ask: the answer is quoted from your notes, with no AI.")},
    "ask-answerer": {"title": "Who answers plain Ask", "path": "Settings, Models, Who answers plain Ask"},
    "follow-up-trail": {"title": "Where a follow-up came from", "path": "Chat tab, or Ask in the Notes tab, under an answer"},
    "why-this-answer": {"title": "Why this answer", "path": "Chat tab, the popup agent, or Ask in the Notes tab, under an answer"},
    "line-verdicts": {"title": "Wrong fact and Pin as true", "path": "Ask or Chat, a numbered mark in an answer"},
    "answer-menu": {"title": "Regenerate, This answer is wrong and Edit", "path": "Chat, the three dots under an answer"},
    "answer-pictures": {"title": "Pictures in answers", "path": "Chat tab, or Ask in the Notes tab, Cites under the answer"},
    "library-skills": {"title": "Skills in the Library", "path": "Library tab, Skills"},
    "object-move": {"title": "Moving, copying and carrying cards", "path": "Notes tab, or Library tab, drag a card or press Ctrl+C; the tray in the status bar"},
    "ocr-engine": {"title": "Tesseract and the reading language", "path": "The OCR workspace, the reader button"},
    "time-and-recency": {"title": "Dates and recent notes in answers", "path": "Chat tab, or Ask on the Notes tab"},
    "model-downloads": {"title": "Downloading a model", "path": "Settings, Models, Suggested downloads"},
    "accessibility": {"title": "Accessibility and zoom", "path": "Settings, Keyboard shortcuts and Appearance"},
    "movable-panels": {"title": "Moving and resizing panels", "path": "Any panel with a title row, on a computer with a mouse"},
}

#: **How Settings, Help lists the entries** (INBOX 448 (1)). The page used to
#: hold thirteen hand-written topics beside this table's sixty, kept in step by
#: hand, and they had drifted (it still taught "g then a letter" for the tab
#: chord). It is drawn from this table now (`GET /help/topics`, settings-find.js
#: `renderHelpTopics`), in these groups and this order, so a new entry shows
#: on the page the moment it exists; `tests/test_help_coverage.py` fails when an
#: entry is in no group, or in two.
HELP_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("Getting started", (
        "tabs-overview", "phone-nav", "first-steps", "tour", "guide", "manual", "hidden-features", "shortcuts",
        "command-palette", "find-anything", "find-a-place", "search", "addresses", "settings-overview", "settings-reset", "install-app", "running-copies", "name",
    )),
    ("Writing notes", (
        "capture", "quick-note", "quick-add", "editor-offers", "autocorrect", "share-note", "capture-anywhere", "note-outbox", "attachments", "quick-sketch", "notes-controls",
        "notes-list", "card-content", "note-history", "links", "favourites", "templates",
        "write-with-atlas", "translate", "translate-offline", "extract-notes", "voice", "live-captions", "audio-overview", "folder-sync", "meetings",
    )),
    ("Filing, tags and categories", (
        "tags-categories", "filing", "filing-settings", "suggested-tags", "tag-manager", "manage-categories", "tidy",
    )),
    ("Asking Atlas", (
        "ask-chat", "chat-typos", "answers-from-notes", "ask-answerer", "chat-controls", "chat-context", "context-window", "chat-private", "chat-attach-cards", "chat-model-picker", "chat-list", "queued-messages", "wrap-lines", "slash-commands", "chat-acts", "answer-offers", "tasks", "nicknames", "follow-up-trail", "why-this-answer", "line-verdicts", "answer-menu", "answer-pictures", "time-and-recency", "notebook-questions", "studyhelp",
        "contradictions", "skills", "personas", "answer-style", "memory", "learned", "open-questions",
    )),
    ("Documents and code", (
        "documents", "documents-controls", "spelling-check", "diagram-builder", "diagram-blocks", "diagram-reading", "diagram-kinds", "diagram-elsewhere", "diagram-ai", "diagram-lines", "documents-replace", "live-view-marks", "documents-features", "documents-list-styles", "writing-streak", "documents-paste", "documents-comments", "documents-turn-into", "documents-to-note", "callouts", "equation-editor", "equation-numbers", "document-graph", "document-base", "document-synced", "document-board", "document-history", "writing-checks", "code-files", "code-completions", "code-tabs", "code-run",
        "debugger", "code-panel", "margin-reader",
    )),
    ("Boards and maps", (
        "whiteboard", "whiteboard-controls", "whiteboard-selection", "board-laser", "board-history", "board-library", "board-library-saving", "board-templates", "board-format", "board-connectors", "board-diagram-tools", "board-workshop", "board-paste", "make-a-diagram", "mind-maps", "mind-map-controls", "mind-map-features", "mind-map-import-export", "mind-map-study", "mind-map-look", "emoji-and-icons",
        "board-comments", "sticky-notes",
        "mind-map-structure", "mind-map-lines", "mind-map-callouts", "board-current-layer", "board-keyboard-create", "board-hand-drawn", "board-tables", "board-shape-points", "board-mermaid", "board-edit-data", "board-colours",
    )),
    ("Library and files", (
        "library", "library-controls", "bookmarks", "web-clipper-bookmark", "contents", "library-skills",
        "files-images", "image-viewer", "ocr-workspace", "ocr-engine", "object-move", "archive", "undo-bin",
    )),
    ("Graph, Timeline, Reminders and Dashboard", (
        "graph", "graph-controls", "graph-display", "graph-categories", "graph-options-help", "graph-draft-map", "entities", "properties", "timeline", "timeline-controls", "reminders",
        "reminders-controls", "dashboard", "dashboard-controls", "patterns", "notifications", "spaces", "private-spaces", "statistics",
    )),
    ("Small tools", (
        "timer", "calculator", "currency-rates", "count-words", "insert-template",
    )),
    ("Look and feel", (
        "appearance", "appearance-panel", "themes", "simple-mode", "accessibility", "movable-panels", "performance", "background-art",
        "statusbar", "companion", "companion-travel", "companion-remarks", "companion-habits", "companion-activities", "companion-throw", "atlas-look", "faces",
    )),
    ("Models and the AI", (
        "models", "what-is-atlas", "model-downloads", "model-bench", "tools-setting", "autonomous", "websearch",
        "search-index", "search-engine-moved", "packages", "package-models", "spelling-packs",
    )),
    ("Privacy and your data", (
        "privacy", "security", "encryption", "lock", "phone", "lan-networks", "address-names", "two-computers", "delete-data", "storage", "import-export", "import-apps", "usage-ledger", "background-tasks", "activity", "health", "data-folder-check",
    )),
    ("Settings and support", (
        "profile", "general-settings", "desktop-companion", "desktop-companion-moods", "updates", "maintenance", "logs", "troubleshooting", "credits",
    )),
]


#: The acts Chat does from a sentence: generated from the act registry
#: (`ai/act_registry.py`, CHAT_PLAN decision 53), so a new act is in the Guide the
#: moment it is in the registry, and a renamed one cannot drift.
#: The Guide's gaps from the engine probe (CHAT_PLAN section 2, the help
#: row; `archive/agent-remaining/engine-probe-1010.md`): the phone, two computers,
#: encryption, deleting your data and sharing a note had no topic of their
#: own. `tests/test_guide_gaps.py` holds the probe's table at 1.0.
MORE_TOPICS.extend([
    {
        "id": "address-names",
        "keywords": ("custom domain", "domain name", "localhost", "tessellate.localhost", "short name", "reverse proxy",
                     "caddy", "nginx", "traefik", "my own domain", "address names", "allowed hosts", "rename localhost"),
        "body": (
            "Settings, Account & security, Address names. The short name opens the app at name.localhost on "
            "this computer (no DNS or hosts file; browsers answer every .localhost name themselves). The app "
            "accepts only that one, and only from this computer. It is a new address, so you sign in once and "
            "per-browser settings start fresh; the window and tray use it from the next launch. A domain "
            "name is for a reverse proxy (Caddy, nginx, Traefik) that ends https and forwards to the app: "
            "list the name the proxy serves, such as notes.example.com, and the app accepts it. The app does "
            "not get a certificate or open your router; the proxy does that. Adding a domain asks for your "
            "password; removing one does not. TESSELLATE_LOCAL_NAME and TESSELLATE_ALLOWED_HOSTS still work "
            "and win over the saved values."
        ),
        "badge": {"label": "Account & security", "section": "account"},
    },
    {
        "id": "phone",
        "keywords": ("phone", "on my phone", "mobile", "iphone", "android", "tablet", "ipad", "use it on my phone",
                     "open it on my phone", "install on my phone", "phone storage", "runs on my phone",
                     "public wifi", "public network", "allow a device", "new device"),
        "body": (
            (
                "Your phone opens this computer's notebook over your own network: turn on Allow other "
                "devices on this network (Settings, Account & security, Other devices), then open the "
                "large address it shows (Copy is beside it, and QR code shows a code the phone's camera "
                "opens; Other addresses folds the rest) on the phone and sign in with your password. On "
                "an iPhone, press Install the certificate on the lock screen, then, in the iPhone's own "
                "Settings app, General, VPN and Device Management to install it and About, Certificate "
                "Trust Settings to trust it; its ? has the steps. The phone's first sign-in waits until "
                "you choose Allow on this computer (a notice with Allow and Deny); allowed devices are "
                "listed with Remove. On a network you have not trusted (a cafe, an airport) nothing can "
                "reach the notebook until you trust it: the wifi icon in the status bar (Alt+L) says "
                "open, closed or off, and its panel has the switch, the address and the trusted and "
                "untrusted networks. A phone's hotspot works too, with no restart. If the phone cannot "
                "connect, both must be on the same Wi-Fi (not a guest one), this computer's firewall must"
                " let the app in (on Windows, Other devices shows the one line to paste into an "
                "administrator Command Prompt, for private networks only), and on an iPhone the browser "
                "needs Local Network on (the iPhone's Settings app, Privacy & Security, Local Network) "
                "with any VPN or ad-blocking app (AdGuard's local VPN) paused. The phone reads and writes"
                " the same notebook, and a note changed on one shows on the other within seconds; nothing"
                " goes through the internet, so the computer has to be on. A phone never makes this "
                "computer act: installing, downloading a model, restoring a backup, quitting, opening a "
                "folder and the settings that point this computer elsewhere say Not available on this "
                "device, and an export downloads to the phone itself."
            )
        ),
        "badge": {"label": "Account & security", "section": "account"},
    },
    {
        "id": "two-computers",
        "keywords": ("two computers", "another computer", "second computer", "sync", "syncing", "laptop and desktop",
                     "move to a new computer", "new computer", "other computer", "use it on two"),
        "body": (
            "One notebook lives on one computer, in its data folder (Settings, Import "
            "& export shows where). To move to a new computer, save a full backup and "
            "restore it there, or copy the data folder while the app is closed. To use "
            "one notebook from a second computer, open it over your network: Settings, "
            "Account & security, Other devices. To keep two notebooks level, Sync "
            "between computers (Settings, Import & export) has two ways in with one "
            "result. Sync over the home network: turn on other devices on the other "
            "computer, type its address and password here and press Pair, check that "
            "the certificate it names matches Other devices there and press Pair again "
            "(the password is sent only then), Allow this computer there, and press Sync now. Sync through a folder, for "
            "computers not on the same network: see Sync through a folder. Notes, "
            "documents, boards and attached files come over; a change made on both "
            "keeps the later one and the other words go to History. Pairing while both "
            "notebooks are unlocked lets each open the other's private notes, which "
            "stay encrypted on both, and the paired notebook keeps your key: Remove in "
            "Other devices ends its pass but cannot take the key back. Private notes never go into a folder."
        ),
        "badge": {"label": "Import & export", "section": "data"},
    },
    {
        "id": "encryption",
        "keywords": ("encrypted", "encryption", "is my data encrypted", "encrypt my notes", "is it secure", "secure",
                     "who can read my notes"),
        "body": (
            "Private notes are encrypted at rest with a key made from your unlock "
            "password; without it their words cannot be read from the data folder. "
            "Other notes are stored as they are written, in the data folder on your "
            "computer, so your disk's own encryption is what keeps them. A full "
            "backup can be sealed with a password (Settings, Import & export). A "
            "recovery key (Settings, Account & security) opens private notes if the "
            "password is forgotten, and Re-encrypt private notes makes a new key."
        ),
        "badge": {"label": "Account & security", "section": "account"},
    },
    {
        "id": "delete-data",
        "keywords": ("delete my data", "delete everything", "erase my data", "remove my data", "wipe", "uninstall",
                     "start over", "delete all my notes"),
        "body": (
            "A deleted note, document or reminder goes to the bin first: Undo or the "
            "bin's Restore brings it back, and the bin clears itself after the time "
            "set in Settings, General, Bin (or Empty the bin at once). Everything "
            "else is in the data folder (Settings, Import & export shows where): to "
            "erase the notebook, save a backup if you want one, close the app and "
            "delete that folder, then uninstall. Nothing is kept anywhere else."
        ),
        "badge": {"label": "General", "section": "general"},
    },
    {
        "id": "share-note",
        "keywords": ("share a note", "share this note", "send a note", "share", "sharing", "give someone a note",
                     "email a note", "export one note", "export a note", "export this note", "export a single note",
                     "download a note", "download this note", "download .md", "save a note as markdown"),
        "body": (
            "Three ways, none through a server: the note's menu, Download .md, "
            "saves it as a Markdown file to send; copy its "
            "address (every view has one) for anyone opening this notebook with "
            "you; or let them open the notebook from their phone or computer on "
            "your network (Settings, Account & security, Other devices)."
        ),
        "badge": {"label": "Import & export", "section": "data"},
    },
])
#: INBOX 896, 900: the status bar's Other devices icon and its networks,
#: a topic of its own so "lock" stays under the reply budget.
MORE_TOPICS.append({
    "id": "lan-networks",
    "keywords": ("wifi icon", "lan icon", "lan mode", "trusted network", "untrusted network",
                 "trust a network", "trust this network", "stop trusting", "forget a network",
                 "turn off other devices", "other devices off", "lan off"),
    "body": (
        "The wifi icon in the status bar, on this computer only, says whether other "
        "devices on your network can open the app: green open, amber closed on this "
        "network (one you have not trusted, or no network at all), plain off. Press "
        "it, or Alt+L, for its panel (a sheet on a phone-sized window): the switch, "
        "the address to type, Trust this network, and two lists, one row per "
        "network, named by its Wi-Fi name where this computer can read it, its "
        "address range under it. Trusted networks have Stop trusting and Forget; "
        "Untrusted networks, every network the app saw and stayed closed on, have "
        "Trust (asks your password) and Forget, always on the row. The "
        "switch applies at once, with no restart: off closes the port and signs "
        "every other device out, and when the wifi drops or you join a network you "
        "have not trusted the port closes by itself. Left on and unused for 14 days, "
        "it turns itself off and says so in the bell. Each time a phone opens the "
        "app, the privacy receipt lists it as a connection coming in, with its "
        "address only. A phone can never turn it on, trust a network or loosen a "
        "setting: those say Not available on this device."
    ),
    "badge": {"label": "Account & security", "section": "account"},
})
TOPIC_META.update({
    "address-names": {"title": "A name instead of localhost", "path": "Settings, Account & security, Address names"},
    "lan-networks": {"title": "Other devices and networks", "path": "The wifi icon in the status bar, or Settings, Account & security, Other devices"},
    "phone": {"title": "On your phone", "path": "Settings, Account & security, Other devices"},
    "two-computers": {"title": "Two computers", "path": "Settings, Import & export", "target": "sync-group"},
    "settings-reset": {"title": "Resetting and moving your settings", "path": "Settings, Import & export, Your settings",
                       "target": "settings-file-group"},
    "encryption": {"title": "What is encrypted", "path": "Settings, Account & security"},
    "delete-data": {"title": "Deleting your data", "path": "Settings, General, Bin"},
    "share-note": {"title": "Sharing a note", "path": "A note's menu, Download .md"},
})


#: canvasdepth2 (INBOX 797, round 2): the map's and the board's newer tools,
#: in topics of their own because `mind-map-features` and the board's own
#: entries are at the reply budget.
MORE_TOPICS.extend([
    {
        "id": "mind-map-structure",
        "keywords": (
            "structure of a branch", "branch structure", "branch layout", "org chart branch",
            "fishbone branch", "one branch as", "lay out one branch", "logic chart branch",
            "different layout for a branch", "xmind structure", "filter the more sheet",
            "find a command on a map", "boundary round selected topics", "boundary round several topics",
        ),
        "body": (
            "A branch can have its own structure, as in XMind: a topic's menu, "
            "Structure, lays the branch under it out as a logic chart, an org chart, "
            "a tree table, a timeline, a fishbone, both sides, a tree to the right "
            "or left, or radial, while the rest of the map keeps its layout. The "
            "branch is laid out as one block, so nothing else overlaps it; Follow "
            "the map's layout takes it back. Ctrl+Z undoes it in one step. To find any command of a board or map by name, "
            "type in the filter field at the top of the More sheet. To box topics that are not one branch, select them (Ctrl-click or a box) and choose Draw a boundary round the selected topics in the topic's menu or Ctrl+K."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "mind-map-lines",
        "keywords": (
            "straight lines on a map", "map line style", "lines arent straight", "curved lines",
            "elbow lines", "which side a line leaves", "side of a topic", "line end side",
            "pin a line to a side", "topic shape", "hexagon topic", "diamond topic", "cloud topic",
            "circle topic", "chevron topic", "underline topic", "core idea shape",
        ),
        "body": (
            "Beside a map's Layout picker, the line style picker draws every line "
            "Curved, Straight or Elbow (right angles with rounded corners); a "
            "topic's own line Shape in its strip still wins. Point at a line, or "
            "select a topic, and each end of its line shows a hollow dot: drag it "
            "round the topic to choose the side the line leaves or enters, in any "
            "layout, and it stays on that side when either topic moves. "
            "Double-click the dot, or the topic's menu, Lines, Line ends: back to "
            "Auto, to let the layout choose again. A topic's Box picker offers "
            "Rounded, Pill, Box, Ellipse, Circle, Hexagon, Diamond, Cloud, Chevron, Underline and "
            "Plain, the words kept inside the shape. Ctrl+Z undoes each change."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "mind-map-callouts",
        #: No "votes": one typo from "notes", so "unlink two notes" read as this topic; "vote" matches its plural.
        "keywords": (
            "callout", "callout on a topic", "bubble over a topic", "speech bubble on a map",
            "add a callout", "remove the callout", "labels on a topic", "label a topic",
            "tags on a topic", "labels under a topic", "vote", "voting", "stamp",
            "stamps", "reaction", "thumbs up a topic", "grammar on a topic",
            "agreement error in a label",
        ),
        "body": (
            "A callout is a few words in a bubble over a topic, as in XMind: a "
            "topic's menu, Topic, Add a callout… writes it; double-click the bubble "
            "to change it, or Remove the callout in the same menu. Add labels… in "
            "the same group writes up to eight short tags, separated by commas, "
            "drawn as a row under the topic's words; double-click the row to "
            "change them. Stamps, in the topic's menu, adds a vote, a heart, a "
            "star, an agree, a question or a hot, each with its count after the "
            "labels; press a stamp on the topic to add yours, and press it "
            "again takes yours back. Each stamp has a menu (the three dots "
            "beside it): Remove one takes one off the count, Clear all takes "
            "the stamp off, and Undo brings either back. Clear the stamps, in "
            "the topic's menu, takes them all off. The map makes room for all three when it is "
            "laid out, and the exports keep them. A label with a verb that does not "
            "agree (He have a plan) gets a double line, and the topic's menu offers "
            "the fix as one Undo step; it is checked on this computer."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "board-current-layer",
        "keywords": (
            "current layer", "draw on a layer", "draw on this layer", "new things on a layer",
            "active layer", "which layer", "layer new items go on", "layer to the front", "send layer to back", "duplicate a layer",
        ),
        "body": (
            "The current layer, as in draw.io: in a board's sidebar, Layers, press a "
            "named layer's name and everything new (drawn, typed, pasted, imported "
            "or placed from the library) goes on it; the row is tinted while it is "
            "current. Press the name again, or its ⋯ menu's Stop drawing on it, "
            "for no layer. A hidden or locked layer takes nothing new. Undo brings "
            "a deleted item back on the layer it was on. The same menu has Bring the "
            "layer to the front, Send the layer to the back (its items keep their "
            "order) and Duplicate the layer (a copy on a new layer, one Undo)."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "board-keyboard-create",
        "keywords": (
            "keyboard only board", "make a sticky with the keyboard", "enter on a board",
            "place a text box without a mouse", "edit a sticky with enter", "board without a mouse",
        ),
        "body": (
            "Making and writing on a board without a pointer: press N, T or F to hold "
            "the Sticky note, Text or Frame tool, then Enter to drop one in the middle "
            "of the view (Insert, Sticky note does too). Tab walks the items; Enter on a selected "
            "text box or sticky puts the caret at the end of its words, and Enter on a "
            "selected shape writes in it. Escape leaves the words."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "board-hand-drawn",
        "keywords": (
            "hand-drawn", "hand drawn", "sketchy", "rough lines", "excalidraw look",
            "sketch style", "drawn by hand", "wobbly lines",
        ),
        "body": (
            "The hand-drawn look, as in Excalidraw: a board's View menu, Hand-drawn "
            "look, draws every shape and connector with rough strokes, the same "
            "each time it is drawn. One shape can differ: its Format panel's Style "
            "tab has Hand-drawn. The pen and the highlighter are drawn as you drew "
            "them, and a mind map keeps its own lines. Exports keep the look."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "board-tables",
        "keywords": (
            "table", "tables", "add a table", "table on a board", "rows and columns",
            "add a row", "add a column", "delete a row", "delete a column", "grid of cells",
            "connect to a table row", "table row connection point",
        ),
        "body": (
            "A table on a board, as in draw.io: Insert, Table places three rows of "
            "three cells, the first a header. Double-click a cell to type in it; "
            "Tab and Shift+Tab go to the next and previous cell, Enter keeps the "
            "words, Escape drops them. Right-click the table for Add a row below or "
            "above, Add a column to the right or left, Widen or Narrow this column, "
            "Equal column widths, Delete this row or column (at the cell you "
            "pressed last) and First row as a header. Resize it by its handles; "
            "columns share the width equally until you widen or narrow one. "
            "Pointing at a table while you drag a connector's end shows a connection point at each side of every row, so "
            "a connector can join one row; add or delete a row and the connectors on the rows below it stay on the same row."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "board-shape-points",
        "keywords": (
            "edit shape points", "edit polygon points", "move a corner of a shape", "add a corner to a shape",
            "take a corner out", "reshape a polygon", "change the corners of a shape", "edit points",
        ),
        "body": (
            "Edit shape points, in a straight-sided shape's More, the right-click Arrange and Ctrl+K, shows a square "
            "handle on each corner. Drag a handle to move that corner (it snaps to the grid when the grid is on), "
            "press the outline to add a corner there and drag it, press a corner without moving to take it out "
            "(three stay). The connectors on the shape follow. Each change is one Undo, Escape during a drag puts the corner "
            "back, and Escape otherwise finishes. A shape with curves, an open line or two outlines has no corners to edit."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "board-mermaid",
        "keywords": (
            "mermaid on a board", "live diagram", "mermaid diagram on the board", "edit a mermaid diagram",
            "flowchart on a board", "diagram object", "pie chart on a board", "gantt on a board",
            "diagram fill", "diagram opacity", "solid diagram boxes",
        ),
        "body": (
            "A live Mermaid diagram on a board: Insert, Diagram, Diagram builder... opens the "
            "block editor on a sample; Done places it at its drawing's shape. "
            "It is any Mermaid diagram (flowchart, sequence, class, state, Gantt, pie "
            "and the rest), drawn as a note draws it and redrawn with the theme. "
            "Select it and the Format panel's Style tab sets its Fill colour, Fill opacity "
            "and Line opacity (0, 25, 50, 75, 100; 100 is a fully solid fill), and the boxes redraw. "
            "Double-click it to change it in the block editor (Source is one button away); "
            "a mistake shows the reason in the "
            "box instead of a picture. Turn into shapes, in the editor's ... menu, replaces "
            "a flowchart, state, class or sequence diagram with shapes and connectors "
            "you can move one by one (Ctrl+Z puts the diagram back). Insert, Diagram, Mermaid, "
            "draw.io or board SVG brings a diagram in as shapes straight away; a Mermaid style line's fill and stroke colour the shape, a linkStyle stroke its connector."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "diagram-builder",
        "keywords": (
            "diagram builder", "where is the diagram builder", "new diagram", "make a diagram", "mermaid",
            "mmd", "flowchart", "insert a diagram", "diagram in a note", "diagram on a board", "mind map diagram",
        ),
        "body": (
            "The Diagram builder makes a flowchart, mind map, timeline or sequence diagram from "
            "blocks. Mermaid is only its file format. Every door is the same row, "
            "Diagram builder, with the same icon; in Documents and the Library's document list it is the flow arrow button beside New. Ctrl+K, Diagram builder, and Find anything, Tools "
            "and features and Quick access list it too. Over a note, a document or a Chat box, "
            "Insert (or / then diagram) opens the builder and Done saves a diagram file and writes a link to it, "
            "[[Title]] after a !, which draws the diagram. Over a board or a mind map, Insert, Diagram, Diagram builder adds a diagram object "
            "to double-click later. Anywhere else, and in the Library's Create, New, Diagram, it "
            "opens the builder empty, and Done saves it as a new diagram file; Open an existing diagram there lists yours. Cancel changes nothing. "
            "On a flowchart, the picture outlines the block you point at and the ones picked. "
            "You can drag a shape from the Add strip onto the picture (onto a block to add it after that block and connect them), "
            "drag a block on the picture to move it, and drag on empty space to pick the blocks you touch (Shift adds, Shift+click toggles, Space and drag, or right-drag, pans). "
            "Drop onto a group's box to add or move into it. Pick or point at a block and its four round handles show: drag the round handle on any side to another block "
            "or a group to connect them, or to empty space for a new connected block; a click on one adds a joined block (Enter, then click, connects; Escape cancels). "
            "Double-click a block, an arrow or a group's border or title to rename it in place; click a group's border or title to pick it. Right-click any of them (long press on a phone) for a menu; a picked arrow takes Enter to change its words and Delete, and a dot at either end drags to another block. A connector row's words (or Enter) go to its block; its ... opens the menu."
        ),
        "badge": {"label": "Documents", "tab": "documents"},
    },
    {
        "id": "diagram-blocks",
        "keywords": (
            "diagram blocks", "edit a diagram", "mermaid blocks", "blocks view", "drag a diagram",
            "join two blocks", "nest a block", "diagram without typing", "flowchart blocks",
            "diagram keyboard", "mmd", "diagram file", "add a block", "add a box", "add a shape to a diagram",
        ),
        "body": (
            "Add a block: N, a shelf tile or Add; /diagram opens the builder in a document. "
            "Picture opens first, "
            "blocks at its left. List gives the blocks list the room instead; "
            "Source and Split show text; Ctrl+Z undoes "
            "either. Add shows the last shape you used: press it to add one, or press its arrow "
            "for every shape and its key. Connect to... on a block draws an "
            "arrow: pick a block, or type a new name to make it. Drag a block: "
            "another's top or bottom puts it before or after, its middle joins "
            "them, a group's body takes it inside. A block's "
            "connector reads Start to Next and its label. "
            "The shape swatch picks it. A divider sizes the blocks and the picture (drag or "
            "arrows; Shift for more). Direction (a menu) turns the flow (... on a phone). An empty one lists "
            "three steps: Add a shape, Name it, Connect it. "
            "The corner bar zooms (Zoom in, Zoom out, Fit), as do Ctrl+wheel and a pinch; "
            "its percentage is typeable and 100% is the drawing's own size; Shift+arrow keys pan. "
            "Shift+click picks a range, Ctrl+click adds one; Escape lets go of the pick; a bar offers Delete, "
            "Duplicate, Box them, Select all, Clear; any picked grip moves all. "
            "Press or drag a block from the shelf onto the picture to join the nearest box (touch: hold); long press one for its menu. "
            "Keys "
            "on a block: arrows walk, Enter renames, N adds a Box, 1 to 9 the other shapes, Shift+N the last one, G adds a group, C or J joins, "
            "K colours, ? lists keys, Delete removes, Alt+Up and Alt+Down reorder, Alt+Right nests, Alt+Left lifts. "
            "Suggest (... on a phone) starts one: "
            "Templates (then Use this template), "
            "From my notes "
            "and Describe it (a model; dimmed with none). A blank diagram becomes "
            "the suggestion; else blocks arrive as ghosts: "
            "Tab takes one, Shift+Tab lets it go, Enter adds those taken and "
            "Escape drops them; Ctrl+Z undoes the whole addition. "
            "Kind asks before it clears blocks. More: next topic."
        ),
        "badge": {"label": "Documents", "tab": "documents"},
    },
    {
        "id": "diagram-reading",
        "keywords": (
            "diagram list order", "flow order", "diagram indent", "connector rows", "org chart blocks",
            "diagram too small", "turn it sideways", "diagram direction", "diagram fit", "blocks list phone",
        ),
        "body": (
            "The list says Your blocks, in the order the chart flows; its foot has Add block and Connect. A block sits under the one that points at it, "
            "indented where it branches (a straight run of steps stays flush), and a block made by Connect to... lands under its siblings, so an org chart reads like the chart. "
            "Add block joins the new box to the picked (or last) one. Alt+Up and Alt+Down swap a block with its neighbour in the chain (a branch says to drag its grip). "
            "A block's arrows share one line under it; press one for its menu: the line (arrow, line, dotted, thick, Both ways), Colour… and Reverse direction. "
            "With two or more blocks picked, the bar also has Colour (K) and Connect, which draws an arrow from the first picked to the second. "
            "Fit stops at readable text (11 px) and the picture scrolls past it. In the picture an arrow key picks the box that way, reading aloud its name and arrows, and Shift with an arrow moves the picture. A tall chart in a wide pane offers Turn it sideways once; Direction is a menu of Down, Right, Up and Left, and Shift turns it back one step. "
            "[ and ] fold the list and the picture to a rail. On a phone, once there is an arrow (another kind: a block), Blocks list opens the list as a sheet. "
            "In Source, Tab indents and Shift+Tab takes it back, Escape leaves the text, Ctrl+Z steps the blocks' history, and a red line number is the line an error names; its note has Undo the last edit. Ctrl+Space lists words; Enter takes one. "
            "In the bar Left and Right walk the buttons; the ... menu has the look, Save as PNG and Save to Library. On the picture Enter names the picked box, Shift+Enter adds a joined box and Alt+Enter a sister, Ctrl+D copies, Ctrl+A picks all, Delete removes, Ctrl+F or / finds by name, and a double press on empty space adds a box. "
            "The New diagram window's Title names the document Done makes (blank dates it) and the files you export."
        ),
        "badge": {"label": "Documents", "tab": "documents"},
    },
    {
        "id": "diagram-kinds",
        "keywords": (
            "mind map blocks", "timeline blocks", "sequence diagram blocks", "mermaid mind map",
            "mermaid timeline", "mermaid sequence", "sequence diagram", "diagram kinds",
        ),
        "body": (
            "Kind, in the Title row (first in the toolbar elsewhere), is a menu of Flowchart, Sequence, Mind map and Timeline, "
            "each with a small picture; one starts an empty diagram of that kind. Box this block (its ... menu) or Box them (picked blocks) "
            "adds a group round. "
            "Blocks draw flowcharts, mind maps, timelines and sequence diagrams: the source's "
            "first word says which, and the bar offers that kind's blocks. A mind map has a branch "
            "and a leaf (B and N) under its centre; a second Branch in a row sits beside it. A timeline has a section, a period and an event "
            "(S, P and E), events inside their period. A sequence diagram has an actor, "
            "participant, message, reply, async, lost, note, loop, alt, opt, parallel, critical and break (A, P, M, R, Y, X, T, "
            "L, G, O, U, C and B); a first message adds the two participants it needs, an alt its else and a parallel box its and. The pane works as a flowchart's: "
            "drag a block to move or nest it, double-click a name, the ... menu, "
            "arrows, Enter, Delete, Alt+arrows, Ctrl+Z. A line the "
            "blocks do not show stays put, and a diagram they cannot read (a second mind "
            "map centre, a sequence box, more than 120 blocks) opens in Source with its picture. "
            "On a sequence, mind map or timeline picture a press picks a part, a double press, Enter or F2 renames it, Delete removes it, "
            "Alt+Up or Down moves it; a mind map or timeline part dragged onto another lands before, after or in it. On a sequence "
            "a head dragged sideways reorders, a drag from one lifeline to another adds a message, and the + at a gap opens the Add menu; "
            "from the keyboard, Insert in the blocks list adds a step under the selected one, + on the picture. "
            "A suggestion of its own kind arrives as ghosts to take; "
            "one of another kind says so and is left out when the diagram has blocks, and replaces a blank one. Hand-drawn look, in the ... menu, sketches any; Clean look takes it back."
        ),
        "badge": {"label": "Documents", "tab": "documents"},
    },
    {
        "id": "diagram-elsewhere",
        "keywords": (
            "edit as blocks", "diagram in a document", "mermaid figure", "open as a diagram",
            "diagram in chat", "embed a diagram", "export a diagram", "diagram png", "diagram svg",
            "copy as mermaid", "diagram on a board", "zoom a diagram", "add a block on a phone",
        ),
        "body": (
            "The block editor opens wherever a Mermaid diagram is drawn. In a document's Live view, "
            "a diagram has an Edit as blocks button on its corner (always there on a touch screen): "
            "it opens the editor in a window you can move and size, and Done puts the changes back "
            "between that diagram's own fence marks and nothing else. Cancel, Escape and the X "
            "ask before dropping changes. On a board, double-click a diagram object. In Chat or Ask, "
            "a reply's diagram has Open as a diagram under it. "
            "Type ![[name]] in a note or a document to draw that diagram there, with a "
            "line that opens it. The ... menu in the editor's bar has Save as SVG, Save as PNG, "
            "Copy as picture, Copy as Mermaid and Copy as SVG. A diagram's Library card "
            "has the same pictures in its menu; its page has Export in its head, and Download .mmd, in the ... menu, saves the text. Source, beside Cancel, shows "
            "the text with the picture; a diagram the blocks cannot draw, or one over 120 blocks, opens there. "
            "/diagram and a board's Insert list your diagrams, then New diagram: an empty builder whose Done embeds that file. "
            "The palette's New diagram window opens on a three-box starter; Clear, in the ... menu, empties it. "
            "On the last box, Tab adds a joined box; on any other, Tab moves on. Shift+Tab selects its source, F6 leaves the blocks and Ctrl+Enter keeps the diagram. "
            "The Keys button in its foot, or ? outside a text field, lists every key. "
            "On a phone, and in Sequence, Mind map and Timeline, the shapes are one Add button that opens a sheet of them; pinch to "
            "zoom, drag to move, double tap to fit. Save to Library, in the ... menu "
            "and on a diagram's corner beside Edit as blocks, keeps a copy as a diagram in the Library; "
            "a notice offers to replace the fence with a link, or to link a board's diagram to it; "
            "nothing changes until you press it. Attach a Library diagram to Chat and the model "
            "reads its source; its card opens it."
        ),
        "badge": {"label": "Documents", "tab": "documents"},
    },
    {
        "id": "diagram-ai",
        "keywords": (
            "ai in the diagram builder", "ask the diagram", "change a diagram with words", "diagram suggestions",
            "fix my diagram", "diagram versions", "compare diagram versions", "restore a diagram version",
            "diagram history", "ai diagram edit",
        ),
        "body": (
            "Ask, at the top of a flowchart's blocks list, changes it from a sentence: add Refund after In stock? No, "
            "rename Warehouse to Fulfilment, connect one block to another, move a block into a group, or remove one. "
            "With no model a rule reads it; with a model on, the model writes the same kind of change. "
            "It shows first: what it does, and a picture of both with added in green, removed in red and dotted, "
            "and changed in amber. Apply makes it (Ctrl+Z undoes it in one step); Discard leaves the diagram as it was. "
            "Suggestions, under Ask, opens like a fold (its arrow turns) and lists what looks wrong: an arrow out of a decision with no words, a decision with "
            "one way out, a block with no way out or joined to nothing, blocks with the same words (one row numbers them), a group "
            "holding one block. Each row's button shows its fix the same way. A mind map, timeline or sequence has Ask too (add Rent under Budget, add event Launch under 2024, add message Pay from Shop to Bank; rename, move and remove work too), and Suggestions: a topic repeated, a period with no events, a participant that never sends. On a diagram document every Apply is "
            "a named version (AI: added Refund). Versions..., in the ... menu, lists them: tick two to Compare, or "
            "one to compare it with now, and Restore puts one back; Named only hides the plain saves. "
            "Suggest, Templates, on a diagram with blocks, offers Add its blocks (as ghosts) or Replace the diagram, which Ctrl+Z undoes."
        ),
        "badge": {"label": "Documents", "tab": "documents"},
    },
    {
        "id": "board-edit-data",
        "keywords": (
            "edit data", "custom properties", "properties on a shape", "data on a shape",
            "named values", "metadata on a shape", "shape data", "add a property",
            "placeholder", "placeholders", "%name%", "tooltip", "hover text", "show a value in a label",
        ),
        "body": (
            "Edit data, as in draw.io: select one shape, line, connector, text box, "
            "picture, frame or table and open the Format panel's Data tab (or Edit "
            "data in the command palette). Add a property gives a name and a "
            "value; a name starts with a letter. Changes save as you leave a field, "
            "each one Undo step, and the values stay with the item. Type %name% in a "
            "shape's or connector's words to show that value there (a name it does not "
            "have stays as typed). %date% shows today's date and %page% the title of the "
            "frame the item sits in, unless the item has a value of that name. A shape or connector can take a Tooltip, shown "
            "when the pointer rests on it. Find on the board reads the values too. "
            "Style as text (Ctrl+E) shows the item's look as JSON; Apply style checks it and saves it as one Undo step."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
    {
        "id": "board-colours",
        "keywords": (
            "opacity", "transparency", "hex", "rgb", "custom colour", "border colour", "border color", "fill colour", "fill color", "same colour",
            "same colour as the fill", "match the border", "swap colours", "recent colours",
            "eyedropper", "eye dropper", "pick a colour from the board", "colour picker",
            "change the colour of a shape", "outline colour",
        ),
        "body": (
            "Colours on a board: every colour button (a shape's Fill and Border on its "
            "bar and in the Format panel, text, and the draw colour) opens one menu. "
            "For a shape it names both, Fill and Border, with a dot of each: press "
            "the other to set it instead. Same as fill (or Same as border) makes "
            "them one colour and Swap trades them, each one Undo step. Recent "
            "holds your last eight picks on this device, above the board's colours. "
            "Palettes you saved from the Library show below the board's colours, one row each, then 24 preset and 40 more colours. "
            "Custom takes a colour typed or pasted: a hex box (#rgb, #rrggbb, "
            "#rrggbbaa, rgb() or hsl()) and Red, Green and Blue boxes. Opacity, "
            "a slider and a number, sets how solid that colour is: the fill's for "
            "a Fill, the line's for a Border or line, the text's for text. "
            "Filled off keeps the fill's colour and Filled on brings it back; "
            "From screen (where the browser has it) takes any colour on the screen. "
            "Pick from the board is the "
            "eyedropper: the next click takes a colour instead of doing what it "
            "would, from a shape (its fill, or its border with Alt or Take a shape's border), "
            "a line, a text box or any colour button, and Escape stops it. A fill "
            "that is off shows dimmed; picking a colour turns it on. Ctrl+Alt+D "
            "(Set as default style) keeps the selected shape's, connector's, text box's or pen stroke's look "
            "as the board's default for new ones; Clear the default style undoes it."
        ),
        "badge": {"label": "Library", "tab": "library"},
    },
])
TOPIC_META.update({
    "board-edit-data": {"title": "Edit data on a board item", "path": "A board's Format panel, Data"},
    "board-colours": {"title": "Fill, border and recent colours on a board", "path": "A shape's bar, Fill or Border"},
    "board-tables": {"title": "Tables on a board", "path": "A board's Insert menu, Table"},
    "board-shape-points": {"title": "Edit the corners of a shape", "path": "A board, a shape's More, Edit shape points"},
    "board-mermaid": {"title": "Live Mermaid diagrams on a board", "path": "A board's Insert menu, Diagram, Diagram builder..."},
    "diagram-builder": {"title": "The Diagram builder", "path": "Ctrl+K, Diagram builder; Insert in a note, a document or a board; Library, Create, New diagram"},
    "diagram-blocks": {"title": "Editing a diagram as blocks", "path": "A diagram document, Blocks"},
    "diagram-reading": {"title": "Reading a diagram: list order, fit and direction", "path": "A diagram document, Blocks"},
    "diagram-kinds": {"title": "Mind maps, timelines and sequence diagrams as blocks", "path": "A diagram document, Blocks"},
    "diagram-elsewhere": {"title": "Editing a diagram in a document, on a board or from a reply, and saving its picture", "path": "A diagram in Live view, Edit as blocks"},
    "diagram-ai": {"title": "Asking the diagram builder for a change, its suggestions and versions", "path": "A diagram's blocks list, Ask; the ... menu, Versions..."},
    "board-hand-drawn": {"title": "The hand-drawn look", "path": "A board's View menu, Hand-drawn look"},
    "board-current-layer": {"title": "The current layer", "path": "A board's sidebar, Layers"},
    "board-keyboard-create": {"title": "Making and writing without a mouse", "path": "A board, Keys and controls"},
    "mind-map-structure": {"title": "A structure per branch", "path": "A map topic's menu, Structure"},
    "mind-map-lines": {"title": "Map line style, line ends and topic shapes", "path": "A map, Layout, the line style picker"},
    "mind-map-callouts": {"title": "Callouts, labels and stamps on a topic", "path": "A map topic's menu, Topic"},
})


def _act_topic() -> dict:
    from tessellate.ai import act_registry

    return act_registry.guide_topic()


MORE_TOPICS.append({
    "id": "find-a-place",
    "title": "Finding where something is",
    "keywords": ("can't find", "cant find", "how do i get to", "show me link", "where did it go", "lost a button", "find a setting"),
    "badge": {"label": "Notes", "tab": "notes"},
    "body": (
        "Ask where something is, in Ask or Chat: \"where is the bin\", \"I can't find dark mode\", \"how do I get to backups\". "
        "The answer says where it lives and gives a Show me link that opens it and rings the control, as a row of Tools and "
        "features does. When two places could be meant, each has its own link. Any row of Tools and features, any Settings "
        "section and any tab can be found this way, typos and all."
    ),
})
TOPIC_META["find-a-place"] = {"title": "Finding where something is", "path": "Notes tab, Ask your notebook"}
MORE_TOPICS.append({
    "id": "nicknames",
    "title": "Calling Atlas by any name",
    "keywords": ("nickname", "call you", "call atlas", "your name", "lil bro", "what can i call you"),
    "badge": {"label": "Chat", "tab": "chat"},
    "body": (
        "Call Atlas whatever you like, a nickname or a word you just made up: \"hey lil bro, what's on today\", "
        "\"what's due this week, broski\". The name is taken off before the question is read, so it is never "
        "searched or corrected. A message that is only a name is a call: Atlas answers and offers three things to ask."
    ),
})
TOPIC_META["nicknames"] = {"title": "Calling Atlas by any name", "path": "Chat tab"}
MORE_TOPICS.append(_act_topic())
TOPIC_META["chat-acts"] = {"title": "Things Chat does for you", "path": "Chat tab"}
MORE_TOPICS.append({
    "id": "tasks",
    "title": "Tasks in Chat",
    "keywords": (
        "add a task", "tick off", "complete a task", "cancel a task", "delete a task", "remove a task",
        "snooze a task", "push back a task", "postpone a task", "undo a task", "untick", "tasks in chat",
    ),
    "badge": {"label": "Chat", "tab": "chat"},
    "body": (
        "A task is a reminder or an open checklist line (- [ ]) in a note, and Chat handles both from one sentence, with no model. "
        "Add: \"add a task to read chapter 5 tomorrow\" sets a reminder, and asks once for the time if you leave it out. "
        "Complete: \"tick off buy milk\" or \"mark the dentist task as done\" ticks the reminder or the checklist line. "
        "Untick: \"untick buy milk\" or \"mark buy milk not done\" reopens a ticked one, and \"undo that\" right after a tick does the same. "
        "Cancel: \"cancel the dentist task\" or \"remove buy milk from my tasks\" puts a reminder in the bin and takes a "
        "checklist line out of its note. "
        "Snooze: \"snooze the dentist task until Friday\" or \"push buy milk to tomorrow 5pm\" moves a reminder to the new time; "
        "a checklist line has no time, so only reminders can be snoozed. "
        "If more than one task fits the words, Chat asks which one before it changes anything, and a name that fits only in part "
        "is asked about too. Each of these waits for Confirm (press it, or type yes or go ahead; Cancel or no drops it), then has Undo on the card, or Ctrl+Z: a ticked task is reopened, a cancelled "
        "one comes back from the bin, a snoozed reminder returns to its old time. Small typos in the sentence are read through. "
        "A card, or an offer such as Gather them, stays in its chat when you leave and come back: a waiting one lasts about half an hour, then shows as expired, and an answered one shows what was done."
    ),
})
TOPIC_META["tasks"] = {"title": "Tasks in Chat", "path": "Chat tab"}


#: A slip read in context (INBOX 1745): `ai/typo_context.py`.
MORE_TOPICS.append({
    "id": "chat-typos",
    "title": "How Chat reads a slip",
    "badge": {"label": "Chat", "tab": "chat"},
    "keywords": (
        "did you mean", "misread my word", "wrong word typo", "form for from", "skull for skill", "chat read my typo",
    ),
    "body": (
        "Chat reads a slip by the sentence around it, the words your notebook uses (note titles, tags, people and "
        "lists) and what the last answer was about, so \"notes form last week\" is from and \"fill in the form\" "
        "stays form. When two readings stay close it answers the likelier and offers the other as a Did you mean "
        "chip; press it to ask again with that word. A word that is one of your own titles or tags is left as it is. "
        "A numeric date like 11/09 follows your locale, and a fraction is a rating only beside a rating word."
    ),
})
TOPIC_META["chat-typos"] = {"title": "How Chat reads a slip", "path": "Chat tab"}


#: Autocorrect outside the editor (Brief 94, INBOX 850): autocorrect.js.
MORE_TOPICS.append({
    "id": "autocorrect",
    "keywords": (
        "autocorrect", "auto correct", "autocorrection", "turn off autocorrect",
        "fix my typos", "it changed my word", "undo a correction", "corrected my word",
    ),
    "body": (
        "Autocorrect fixes a clear typo, such as teh, as you finish the "
        "word, and puts back a missing apostrophe (havent, ive, dont, youre and the rest "
        "become haven't, I've, don't, you're; ill, id, cant and wont only where "
        "the words around them say so), in the note boxes, the chat and Ask composers, the reminder boxes and the titles. "
        "The corrected word is underlined for five seconds: rest the pointer on "
        "it or click it for a small menu to keep it, put back what you typed, "
        "or edit the word (a document gets the same underline), "
        "or press Backspace or Ctrl+Z straight after to put it back, and "
        "the toast carries Undo too. A word you put back is left alone for the "
        "rest of the session, and a word in your dictionary never changes. It "
        "never runs in code, links, tags or search boxes. Turn it off in "
        "Settings, General, Writing; a document has its own switch in the "
        "editor's ... menu."
    ),
    "badge": {"label": "General", "section": "general", "target": "pref-autocorrect"},
})
TOPIC_META["autocorrect"] = {"title": "Autocorrect", "path": "Settings, General, Writing", "target": "pref-autocorrect"}


#: The credits (uiset, 2026-10-11): Settings, Help, Credits, drawn from
#: frontend/credits.json, which scripts/build_credits.py writes from THIRD_PARTY.md.
MORE_TOPICS.append({
    "id": "credits",
    "keywords": (
        "credits", "open source", "libraries", "third party", "third-party",
        "attribution", "built with", "what is it built on", "licences", "licenses",
    ),
    "body": (
        "Settings, Help, Credits lists the libraries and data Tessellate is "
        "built on, each with its licence and a link to its source: the ones in "
        "the server, the ones in the app, the optional downloads and the "
        "whiteboard's shapes. Tessellate itself is AGPL-3.0."
    ),
    "badge": {"label": "Help", "section": "help", "target": "credits-fold"},
})
TOPIC_META["credits"] = {"title": "Credits and licences", "path": "Settings, Help, Credits", "target": "credits-fold"}


#: Patterns (INBOX 904 B84, the owner: "Do the patterns ever change?? What's
#: the meaning or use of them?? Can I view them"), with the line that opens.
MORE_TOPICS.append({
    "id": "patterns",
    "keywords": (
        "patterns", "pattern", "what are patterns", "times since", "weeks running", "keeps coming up",
        "patterns line", "do patterns change", "see the patterns",
        "confirmed patterns", "edit a pattern", "manage patterns", "remove a pattern",
    ),
    "body": (
        "Patterns are what your notes keep coming back to, counted from the notes "
        "themselves with no AI: a subject that came up again and again (\"university "
        "came up 4 times since 16 July\"), one written about every week, a plan "
        "still open, a decision you went back on, or a busy week. They change as you write, "
        "since each is counted again whenever the dashboard draws. Press the "
        "pattern on the dashboard's line to see the notes behind it; Notes, Tidy "
        "lists every pattern whole. Its ... menu has Confirm, which says it as a "
        "fact from then on, and Not right, which never shows it or anything like "
        "it again. A plan still open also has Done: it removes your Confirm and "
        "never shows that plan again, and a later note that shares the plan's "
        "words does the same on its own. A confirmed pattern's ... menu has Edit "
        "(your own words, or what it is about; its tag still reaches it), Not right "
        "and Remove, each with an Undo, and a plan's Done; Settings, What it remembers lists every confirmed pattern with "
        "the day you confirmed it and its notes, to manage them in one place."
    ),
    "badge": {"label": "Dashboard", "tab": "dashboard"},
})
#: Slash commands (O6, `ai/slash.py`): written from the registry, so a command
#: added there is in this topic, `/help` and the "/" menu at once.
def _slash_commands_topic() -> dict:
    from tessellate.ai.slash_table import TABLE

    listed = " ".join(f"{usage}: {summary}" for _, usage, summary, _ in TABLE)
    return {
        "id": "slash-commands",
        "keywords": ("slash commands", "slash command", "commands", "exact answers", "chat commands", "type a command", "agent popup commands"),
        "body": (
            "Type a command in the chat box or the Agent popup's box for an exact answer from your notes, with no AI. "
            f"{listed} Typing / opens a menu with a row for each command; one that takes words "
            "fills the box with its name and waits for them. Asking in plain words "
            "(\"which notes have no tags\") runs the same command. /categories and /tags draw "
            "a bar for each, and /recent, /today and /made draw a small timeline of when; a day "
            "with nothing in it says where your notes run and draws that. A note named "
            "in any reply (Chat, Ask, the popup agent, the Guide) previews on hover "
            "or focus, and a reply that gives one to three notes shows each as a "
            "card under it; press a card to open the note."
        ),
        "badge": {"label": "Chat", "tab": "chat"},
    }


MORE_TOPICS.append(_slash_commands_topic())
TOPIC_META["slash-commands"] = {"title": "Slash commands", "path": "Chat tab, type / in the box, Commands"}


TOPIC_META["patterns"] = {"title": "Patterns", "path": "The dashboard's line under the greeting, and Notes, Tidy"}


#: INBOX 1352: the quick sketch pad rebuilt as a paint pad (sketch-pad.js).
MORE_TOPICS.append({
    "id": "quick-sketch",
    "keywords": (
        "quick sketch", "sketch pad", "draw a picture", "paint", "drawing tools" "remove a recent colour", "delete a custom colour",
        "brush", "pencil", "eraser", "highlighter", "bucket fill", "paint bucket",
        "eyedropper", "colour picker", "draw a rectangle", "draw a circle",
        "polygon", "annotate a picture", "draw on a picture", "download png",
    ),
    "body": (
        "Quick sketch (q, Ctrl+Shift+K, or Sketch on the dashboard) is a paint "
        "pad. The tools are down the left, each with a letter: S select, P "
        "pencil, B brush, H highlighter, E eraser, L line, A arrow, R "
        "rectangle, O ellipse, G polygon, T text, F fill, I colour picker. A "
        "shape is drawn corner to corner; Shift makes it a square or circle "
        "and snaps a line to 45 degrees, Alt draws it from the centre, and "
        "Escape cancels it; with the Text tool Escape places the text. The "
        "bar holds the ink and fill colours (X swaps them), the palette and "
        "a custom colour (the last six you picked show as recent colours; "
        "the small x on one, or Delete on it, takes it off, with an Undo; the plus saves the current colour again), the size ([ and ] change it; for Text it is the "
        "text size), outline, fill or both for shapes, Undo, Redo (Ctrl+Shift+Z "
        "or Ctrl+Y), Clear and a More menu (a picture under the ink, the paper "
        "colour). On a narrow window the palette, size and style are under "
        "Colour, size and style. Ctrl and the wheel zoom, 0 fits the page. "
        "Save as note adds the sketch to a new note once something is drawn, and the toast has an Open button; "
        "Download PNG saves the picture; a picture's Annotate opens it here."
    ),
    "badge": {"label": "Notes", "tab": "notes"},
})
TOPIC_META["quick-sketch"] = {"title": "Quick sketch", "path": "Notes, the sketch button; q or Ctrl+Shift+K anywhere"}


#: DOCUMENTS_PLAN item 11 (OPEN F1, s9-1110): equation numbers and references.
MORE_TOPICS.append({
    "id": "equation-numbers",
    "keywords": (
        "equation number", "number an equation", "label an equation", "eqref", "ref equation",
        "refer to an equation", "cite an equation", "cross reference", "tag equation", "label{",
    ),
    "body": (
        "Type \\label{name} inside a display equation ($$ ... $$) to number it: the first "
        "labelled equation is (1), the next (2). Add \\tag{A} to choose the number yourself. "
        "\\eqref{name}, or \\ref{name}, written anywhere in the same document, shows that "
        "number in parentheses, in Live and Read view, and follows the equation if the "
        "numbers change. A name that no equation carries reads (?). Typing \\ref{ or \\eqref{ lists the labels with their numbers. A $$ or \\begin{equation} block over several lines is drawn as the formula in Live too; click it for the source. A \\begin{equation} block numbers itself in Read view, \\begin{equation*} does not."
    ),
    "badge": {"label": "Documents", "tab": "documents"},
})
TOPIC_META["equation-numbers"] = {"title": "Numbering and citing equations", "path": "A document, Live or Read view"}


#: DOCUMENTS_PLAN 16: the graph block (documents-graph.js).
MORE_TOPICS.append({
    "id": "document-graph",
    "keywords": (
        "graph", "graph block", "plot", "plot a function", "y = f(x)", "function graph",
        "curve", "slider", "desmos", "axes", "```graph",
    ),
    "body": (
        "Type /graph in a document, or write a code block marked graph, to plot a function. "
        "One line is one curve: y = sin(a x), f(x) = x^2 / 10, or just x^3 - x. Up to six curves. "
        "A line such as a = 2 [0, 5] makes a slider named a, from 0 to 5, that the curves can use; "
        "add a third number for the step. x: -5..5 and y: -2 to 2 set the axes, "
        "title: Waves adds a heading, and a line starting with # is a note to yourself. "
        "Read and Live draw it as a picture; in Live, move the caret into the block (or press the pencil) "
        "to edit the text. Hover or touch the plot to read a value, drag to pan, Ctrl and the wheel or the plus and "
        "minus buttons to zoom, and the third button, or 0, to reset. A line it cannot read is listed under the plot with the reason, "
        "and the rest still draw. Nothing is run: only numbers, x, the slider names and the usual functions are understood."
    ),
    "badge": {"label": "Documents", "tab": "documents"},
})
TOPIC_META["document-graph"] = {"title": "Graph a function in a document", "path": "A document, the / menu, Graph"}


#: DOCUMENTS_PLAN gap row 6: the base block (documents-base.js), a read-only table of notes by property.
MORE_TOPICS.append({
    "id": "document-base",
    "keywords": (
        "base", "notes table", "database view", "table of notes", "properties table", "query notes",
        "```base", "bases", "obsidian bases",
    ),
    "body": (
        "Type /notes table in a document, or write a code block marked base, to list the notes that share a property. "
        "type: Book lists the notes whose properties say type: Book. where: status = read narrows it (any number of "
        "these, all must hold; a list property matches any of its values). columns: author, rating chooses what to show, "
        "sort: rating desc orders it (numbers and dates sort as such), and limit: 50 caps the rows at 300. "
        "The first column is the note's name: press it to open the note. The table is read-only: a value is changed in "
        "the note's own properties, and the refresh button reads the notes again. Private notes never appear. "
        "It is a table only; boards and calendars are not built."
    ),
    "badge": {"label": "Documents", "tab": "documents"},
})
TOPIC_META["document-base"] = {"title": "A table of notes in a document", "path": "A document, the / menu, Notes table"}


#: OPEN W18 (s9-1110): the diagram's line shape, spacing and page menu.
MORE_TOPICS.append({
    "id": "diagram-lines",
    "keywords": (
        "curved arrows", "straight arrows", "stepped arrows", "arrow lines", "line shape",
        "diagram spacing", "compact spacing", "roomy spacing", "diagram page menu", "diagram minimap", "diagram overview",
        "expand a diagram", "full screen diagram",
    ),
    "body": (
        "A flowchart's ... menu sets how arrows are drawn (Straight lines, Curved lines, "
        "Stepped lines, Usual lines) and how far apart the blocks sit (Compact, Roomy, "
        "Normal spacing). Both are kept in the diagram's own text as front matter and Undo "
        "takes them back; the picture is then drawn by the dagre layout. Wrap long lines, in the ... menu or by the Wrap button beside Source, folds long Source lines onto the next row and hides their numbers. A diagram's page "
        "menu keeps Download or print, Connections and History, and leaves out the "
        "writing switches, Read aloud and Extract notes. Export, beside Picture, List and "
        "Source, saves it as a PNG or an SVG, or copies it as a picture, as Mermaid or as SVG. "
        "A picture larger than its pane (zoomed in, or a big diagram at Fit) shows a small overview in "
        "its lower left corner: press or drag it to move the picture. A phone pans by finger instead. "
        "Expand, at the end of the toolbar of a diagram in a document, opens it full screen with the same saving; Collapse or Escape returns to the document where you left it."
    ),
    "badge": {"label": "Documents", "tab": "documents"},
})
TOPIC_META["diagram-lines"] = {"title": "Arrow lines, spacing, the page menu and the overview of a diagram", "path": "A diagram document, the ... menu"}


#: DOCUMENTS_PLAN 16: the guided equation editor (math-editor.js).
MORE_TOPICS.append({
    "id": "equation-editor",
    "keywords": (
        "equation", "equations", "equation editor", "write an equation",
        "maths", "math", "formula", "fraction", "square root", "greek letter",
        "symbol", "integral", "matrix", "latex", "tex", "alt+=", "alt equals",
        "common formulas", "quadratic formula", "arrows", "relations", "sets and logic",
    ),
    "body": (
        "The equation editor is the Equation tab of Calculator and equations "
        "(see that topic). It opens from /equation in a note, a document, a "
        "board's text or the Chat box, from a document's Insert menu, or with "
        "Alt+= there and in the Ask box, or Ctrl+K, Insert equation, each over "
        "the box you were in; Ctrl+K, Calculator and equations opens the same "
        "dialog on Sum, and the shortcuts list has it under Tools. The "
        "equation is drawn as it will read, with "
        "dotted boxes where things go: click a box to fill it, Tab goes to the "
        "next one and the arrows move through the equation. Backspace in an "
        "empty box selects its whole structure, and a second removes it. Type it plainly: "
        "a/b makes a fraction, ^ and _ a power or a subscript, and LaTeX such "
        "as \\frac or \\alpha turns into the symbol as you type it. The "
        "palette inserts the structures Word offers (fraction, script, "
        "radical, integral, large operator, bracket, function, accent, limit "
        "and log, operator, matrix), braces and labelled arrows, common "
        "formulas and symbols: Greek in "
        "lower and upper case, operators, relations, arrows, sets and logic, "
        "calculus and function names; a selection goes into the first box. The "
        "LaTeX button shows the same equation as raw TeX to edit directly, and "
        "the two stay in step. A row of groups above the palette jumps to one "
        "and marks the one in view; Pin, then a tile, makes it a favourite at "
        "the top, and Recent the last ones. A drawn equation in a note or a document is "
        "edited where it stands: click it, Enter or a click outside keeps the "
        "change as one undo step, Escape leaves it as it was. Inline sits in "
        "the sentence, Display on its own line; Ctrl+Enter inserts, and with no "
        "box behind the dialog Insert is off and Copy copies the equation. An "
        "equation made of numbers shows its value under the field. It writes "
        "TeX between dollar signs, so the note stays plain text. On a touch "
        "screen the field offers its own keyboard."
    ),
    "badge": {"label": "Library", "tab": "library"},
})
TOPIC_META["equation-editor"] = {"title": "Equation editor", "path": "Calculator and equations, Equation tab; type /equation, or Alt+=, in a note, a document, a board's text or Chat"}


#: DOCUMENTS_PLAN 26 (decision 82): a block shown in two documents, edited in either (documents-synced.js).
MORE_TOPICS.append({
    "id": "document-synced",
    "keywords": (
        "synced block", "synced blocks", "transclusion", "transclude", "embed a paragraph", "block embed",
        "link to this block", "edit an embedded block", "same paragraph in two documents", "![[",
    ),
    "body": (
        "A paragraph can live in one document and be shown in others. In its own document, put the caret in it and "
        "choose Link to this block in the / menu: it gets a short id at the end of its last line. In another document "
        "write ![[Document title#^the-id]] and the paragraph appears there, quoted, with a line naming where it comes "
        "from (press it to open that document). Hover the quote and press the pencil to change the paragraph where "
        "you are: Save writes it into the document it lives in, so there is only ever one copy, every other place that "
        "shows it follows, and that document's History has the change. Other edits to that document in the meantime "
        "stay; if the paragraph itself was changed somewhere else, Save is refused and your text stays in the box. A paragraph is one block: a blank line in it is "
        "not allowed, and an empty one cannot be saved. In the document the paragraph lives in, the pencil is not "
        "shown: there the text is simply the text."
    ),
    "badge": {"label": "Documents", "tab": "documents"},
})
TOPIC_META["document-synced"] = {"title": "A paragraph shown in two documents", "path": "A document, the / menu, Link to this block"}

#: DOCUMENTS_PLAN 26, gap row 10: a board shown in a document is edited from it (documents-board.js).
MORE_TOPICS.append({
    "id": "document-board",
    "keywords": (
        "board in a document", "embed a board", "edit a board here", "whiteboard in a document", "mind map in a document",
        "![[board", "![[map", "edit here", "canvas block",
    ),
    "body": (
        "A whiteboard or a mind map can sit in a document as a card: choose Board or mind map in the / menu, or write "
        "![[board:12]] with the board's number. Press the card to open the board in the Library, or press Edit "
        "here under it to change the board without leaving the document. The board opens in a dialog over the document "
        "with its own toolbar, and its changes are saved as you make them, as on the Library page. Press the X, or "
        "Escape when the board has nothing of its own to cancel (a menu, a selection, full screen), to close the panel: "
        "the card shows the board as it now is and the Edit here button has the focus again. The Library keeps one board "
        "window, so while the panel is open the board is in it and not in the Library; closing puts the Library back as it "
        "was, on the board it had open or on its list of boards. The other way: a board's Board menu, Write as a document, "
        "makes a draft with a heading for each frame and a paragraph for each sticky, text box or note card in it."
    ),
    "badge": {"label": "Documents", "tab": "documents"},
})
TOPIC_META["document-board"] = {"title": "A board shown in a document", "path": "A document, a board card, Edit here"}
