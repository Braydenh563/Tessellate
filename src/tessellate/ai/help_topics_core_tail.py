"""The Guide's reference, part one, second half: the controls references, the
engine-probe gaps and the rest of `HELP_TOPICS` after the first group.

Moved out of `help_topics_core.py` whole (audit 1028 K24, 3,735 lines there; a
pure move, text and order unchanged). `help_topics_core.HELP_TOPICS` extends
itself with `TAIL_TOPICS` at the point this block used to sit, so the Guide's
order is the one it always had. Data only: no imports, no behaviour.
"""

from __future__ import annotations

#: **A controls reference per surface** (INBOX 410, the owner: "what if the
#: user asks the guide for all the hidden features, keybinds, controls,
#: utility and more for features like the whiteboard, mindmap and documents
#: editor etc. can it answer those??"). It could not: the entries above say
#: what each surface is, in a paragraph, and a question about its keys found
#: that paragraph or the generic shortcuts entry. Each entry below is written
#: from the surface's own code, not from memory of it: its keydown handlers
#: and shortcut tables (`WB_TOOL_KEYS` and the board's keydown handler in
#: whiteboard.js, `DOC_COMMANDS` in documents.js, the graph box's keydown in
#: graph.js), the menus' own labels in index.html, and the help panels the
#: surfaces already show. Dense on purpose: offline, the entry *is* the
#: answer, and a list of keys cut short is a list that is wrong.
#:
#: Their keywords are the words only a controls question uses ("lasso",
#: "emmet", "cross-link", the chords themselves). The surface's own name is
#: deliberately not among them, so "what is the whiteboard" still reaches the
#: one-paragraph entry; `_CONTROLS_FOR` and `_CONTROL_INTENT` below are what
#: send "what are the whiteboard shortcuts" here instead.
TAIL_TOPICS: list[dict] = []
TAIL_TOPICS.extend(
    [
        {
            "id": "whiteboard-controls",
            "keywords": (
                "lasso",
                "highlighter",
                "eraser",
                "connector",
                "snap to grid",
                "snap",
                "grid",
                "pan",
                "zoom",
                "zoom to fit",
                "ctrl plus",
                "ctrl minus",
                "zoom keys",
                "zoom on the selection",
                "board overview",
                "find a card",
                "find and replace",
                "replace all",
                "whole word",
                "regular expression",
                "pattern",
                "tool",
                "select all shapes",
                "select all connectors",
                "select similar",
                "turn 90 degrees",
                "remove from group",
                "copy size",
                "paste size",
                "reverse a connector",
                "auto size",
            ),
            "body": (
                "Whiteboard keys (Library, Boards & maps; Ctrl+Shift+B opens it). "
                "Tools: V or S select, H hand, K lasso, P pen, M highlighter, E "
                "eraser, B fill, L line, A arrow, R rectangle, O circle, G "
                "triangle, D diamond, T text, N sticky note (Ctrl+Enter in one starts the next beside it), F frame, C connector (Shift+C "
                "curved), I image, X delete. An arrow (A) or a line (L) that starts or ends on a shape, card or topic is a "
                "connector bound to it and follows it when it moves. A drawn shape is selected and Select returns (not the pen). Shapes draw corner to corner (Shift: square, circle, 45 degree line, straight pen; Alt: centred). The Shapes flyout has more (star, cloud, cylinder and others). Moving around: the wheel "
                "zooms about the pointer, two trackpad fingers pan, Shift+wheel pans sideways, a pinch "
                "zooms too, a drag on empty canvas boxes (Shift adds), a right or middle drag or Space and drag pans (a plain right-click opens the menu), a drag to an edge pans, Ctrl+= and Ctrl+- zoom the board about the selection's centre (else the view's), "
                "Ctrl+0 fits all (or Shift+1), Ctrl+1 is 100% (numbers and sliders type in), Shift+2 zooms to the selection, Shift+N shows the "
                "overview, / or Ctrl+F finds, Ctrl+H replaces, Tab walks the "
                "items. Ctrl+K also finds select all shapes or connectors, select similar, turn 90 degrees, remove from "
                "the group, copy and paste the size, grow to fit the words, reverse a connector and clear its bends. "
                "Groups nest (Ungroup takes off one level, a double-click goes in); a turn near upright snaps. "
                "Selecting, menus, presenting: Whiteboard selection and menus."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "whiteboard-selection",
            "keywords": (
                "nudge",
                "align",
                "align shapes",
                "align on the whiteboard",
                "distribute",
                "bring forward",
                "send backward",
                "group",
                "ungroup",
                "copy style",
                "paste style",
                "text in a shape",
                "label a shape",
                "flip a shape",
                "resize with the keys",
                "frame",
                "frames",
                "section",
                "region",
                "lock a shape",
                "lock an item",
                "unlock all",
                "locked item",
                "comment on a card",
                "comment on an item",
                "comments on the board",
                "comment thread",
                "present",
                "presentation",
                "slides",
                "slideshow",
                "drag to delete",
                "drop to delete",
                "drag onto delete",
                "trash an item",
                "alignment guides",
                "smart guides",
                "size while drawing",
                "board on a phone",
                "more board commands",
                "whiteboard keys",
                "whiteboard shortcuts",
            ),
            "body": (
                "Whiteboard selection: drag inside a selection's box to move it all; Shift+click adds, Ctrl+A selects all, Ctrl+D "
                "duplicates, Alt-drag copies, Ctrl+V pastes a step along (Ctrl+Shift+V in place), the arrows "
                "nudge (Shift: further; Ctrl+Shift: resize), Shift+H and Shift+V flip, "
                "Shift and drag keeps to one axis, Shift and a corner keeps "
                "proportions, Alt resizes from the centre; a move, resize or box drawn out shows guides "
                "and its size (Alt: none); [ and ] move one step back or forward, Ctrl+[ and Ctrl+] to "
                "the back or front, Ctrl+G groups, Ctrl+Shift+G ungroups, Ctrl+Alt+C and Ctrl+Alt+V copy "
                "and paste a style, Delete (or a bin drop) removes, Esc cancels a drag."
                " Double-click empty board for a text box, double-click a closed shape (or select "
                "it and press Enter) to write in it, right-click (or hold) for the menu, double-"
                "click a line to bend it, select a connector and press Label (or Enter) to"
                " label it. A frame's title drags it and what is inside it, its top handle turns both; a click on a panel's body or a frame's edge selects it; its "
                "menu exports it or fits it to its contents, and a double-click on a resize "
                "handle fits that edge to what it holds; a note, text box or picture fits its content. Ctrl+Shift+L "
                "locks the selection. Right-click an item, "
                "Comment…, starts a thread. View, Present frames: one frame at a "
                "time, the bar lists pages; ? shows every key; Ctrl+K finds any board action by name. Menus: Insert, Edit, "
                "Arrange opens as submenus: Order, Align, Distribute, Tidy, Group, View (panels, background, grid, "
                "snap, zoom) and Board (new, export). Rename a board: Board, Rename."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-laser",
            "keywords": (
                "laser",
                "laser pointer",
                "laser trail",
                "laser colour",
                "pointer while presenting",
                "present with a pointer",
            ),
            "body": (
                "The laser pointer, while presenting a board or a map. Press L, or the pointer button in the "
                "presentation bar, and the cursor becomes a dot that follows your mouse; nothing is drawn on the "
                "board. The small menu beside the button sets the trail (on or off), the look (dot, trail, ring "
                "or spotlight), the ring's pulse (on or off, shown while the look is Ring) and the colour (from the board's colours). Your choice is kept in this browser. "
                "With Reduce motion on, the trail is off and the look holds still."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-history",
            "keywords": (
                "board history",
                "history of the board",
                "time machine",
                "earlier version of the board",
                "go back in time",
                "put the board back",
                "restore the board",
                "what did the board look like",
                "snapshot",
                "snapshots",
                "named version",
                "save a version of the board",
            ),
            "body": (
                "Board, History… (or Ctrl+K, History) puts a slider at the foot of the board. Drag it "
                "back, or press Left, Home and End, and the board is drawn as it was at each moment, a "
                "moment being a run of changes up to two minutes long; the bar says when and what it "
                "added, changed and removed. Nothing can be changed while the past is shown. Put back "
                "restores the whole board as it was then, and the second button only what was selected "
                "when History opened; either is one Undo step and is in the history too. Esc, or the "
                "slider's right end, comes back to now; the number beside it (3 of 12) types in to jump. Changes older than ninety days may be kept only "
                "in summary, and such a moment cannot be shown. Board, Snapshots… names the board as it is "
                "now (Snapshot and the time unless you type a name); each one shows its picture, and "
                "Restore puts the board back as one Undo step."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-templates",
            "keywords": (
                "new board",
                "board templates",
                "map templates",
                "start from a template",
                "template picker",
                "kanban",
                "weekly planner",
                "roadmap",
                "project brief",
                "okr",
                "okrs",
                "swot",
                "eisenhower",
                "pros and cons",
                "lean canvas",
                "five whys",
                "5 whys",
                "fishbone",
                "meeting notes",
                "retrospective",
                "cornell",
                "study notes",
                "mood board",
                "journey map",
                "brainstorm",
                "project plan",
                "goal breakdown",
                "weekly review",
                "essay outline",
            ),
            "body": (
                "New (the Boards and maps dock) opens Untitled board N, its name ready to type "
                "over in the top bar (Enter keeps it, Escape the old one). New's arrow, then From a template (or Board, "
                "New board) opens one dialog: Board or Mind map in the tab "
                "strip under its title, the name, then the templates grouped by purpose (Plan and track, "
                "Weigh and decide, Find the cause, Meet and review, Study and create, then your own), each "
                "with its picture, and the chosen one drawn larger beside the list. A click chooses; Create, "
                "Enter or a double click makes it; the search box narrows the list by name or tag. A board's thirty-eight: Kanban, Weekly planner, Roadmap, "
                "Project brief, OKRs, SWOT analysis, Eisenhower matrix, Pros and cons, Lean canvas, 5 whys, "
                "Fishbone, Flowchart, Class diagram, Entity relationship diagram (tables with crow's foot lines), "
                "Wireframe page, Meeting notes, Retrospective, Study notes (Cornell), Mood board and User "
                "journey map, and for study and home Lecture notes, Revision plan, Essay outline, Timeline, Venn diagram, Brainstorm, Mind map, Study timetable, Habit tracker, Goal setting, Project plan, Reading list, Exam readiness and Daily plan. Each frame is a tinted panel with its title and a hint inside its top; drag the "
                "title to move the frame and what is in it, double-click it to rename. A map's twenty-seven, "
                "among them Lecture notes, Revision plan, Exam preparation, Research project, Presentation,  Brainstorm, Decision, Project plan, Cause and effect, Pros and cons, SWOT map, "
                "Goal breakdown, Weekly review, Study topic, Book notes and Meeting, each drawn in its own "
                "shape; the new map's central topic is its name, laid out the way the picture shows (a "
                "brainstorm round its centre, pros and cons both ways, a fishbone to the left). A new map "
                "that is still just its root offers the same templates as pictures, Start from a template; "
                "the X hides it for that map."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-library",
            "keywords": (
                "object library",
                "shape library",
                "shapes",
                "flowchart",
                "flow chart",
                "icons",
                "stencil",
                "draw.io shapes",
                "bpmn",
                "network shapes",
                "cloud shapes",
                "connection points",
                "preset",
                "template",
                "favourite shapes",
                "recent shapes",
                "sidebar",
                "layers",
                "pages",
                "named layer",
                "hide a layer",
                "lock a layer",
                "page order",
                "presentation order",
                "reorder frames",
                "order of frames",
                "frame order",
                "frames in the presentation",
                "paper size",
                "a4 page",
                "letter page",
                "locked item",
                "unlock",
                "drag a template",
                "map templates",
                "this map tab",
                "map stats",
            ),
            "body": (
                "A board's sidebar (the Sidebar button in its top bar, or the rail on its left edge) has "
                "four tabs: Library, Notes, Layers and Pages; a mind map's has Library, This map (its "
                "facts, its look, open every fold, lay it out again) and Outline. The Library starts with "
                "Templates (38 for boards, 27 for maps; see Board and map templates). Pages lists the "
                "board's frames in presentation order: drag a row or press Alt+Up and Alt+Down to reorder, "
                "Enter goes to the frame, P presents from it, double-click or F2 renames it, and its ⋯ menu has more. "
                "Layers starts with named layers: + adds one "
                "holding the selection; its eye and lock act on all of it. Tinted rows are selected on the board "
                "(the head counts them; Clear drops them), and a frame lists what it holds under its row. A locked item shows a lock when the pointer "
                "is on it; right-click it to unlock it. The Library holds "
                "built-in sets (General shapes, Callouts and notes, Flowchart, UML, Entity relationship, Wireframe, BPMN, C4, Arrows, Frames (a frame, a timeline lane, swimlanes, A4, A3, Letter, 16:9), Cloud and network and Devices and people icons "
                "and 1,530 icons), five draw.io sets (196 shapes "
                "with their own connection points), then Favourites, Recent and your own "
                "libraries; the search field finds any of them by name or tag. Click a tile or press Enter "
                "to place it in the middle of the view, drag it and it lands held where you grabbed it, or Shift+Enter to place "
                "it joined to what is selected; F stars it, and Shift+F10 or a right-click opens its menu "
                "(rename, tags, duplicate, move, delete). Saving your own is in Saving to the library."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-library-saving",
            "keywords": (
                "save to library",
                "save to the library",
                "my shapes",
                "custom shape",
                "saved style",
                "palette",
                "saved branch",
                "import library",
                "export library",
                "save as template",
                "board template",
                "templates in the library",
                "save my own shape",
                "save a shape to the library",
                "save a board as a template",
                "board as a template",
                "uml",
                "class diagram",
                "erd",
                "entity relationship",
                "crow's foot",
                "wireframe",
                "c4",
                "architecture diagram",
            ),
            "body": (
                "To save your own: select things and press "
                "Ctrl+Shift+S, or right-click, Save to the library, for a selection, a drawn shape, a style, a sticky "
                "or text preset, a palette of the selection's colours, or on a mind map a branch; Board, "
                "Save this board as a template keeps the whole board. New board then offers your templates "
                "beside the built-in ones. The library's ⋮ makes a new library, imports a library file and "
                "exports one. A placed item is an ordinary copy: changing the library later never changes "
                "a board. In Agent mode the assistant can search the library and place from it, draw "
                "shapes and frames, and move, edit or delete what is on a board, asking first. "
                "A PNG export joins the image library only when Also add to the image library is ticked in the "
                "export dialog, which opens on Whole board when nothing is selected (On screen is one press away); Board, Show hints brings the first-steps card back (an empty board keeps a one-line cue meanwhile). "
                "For diagrams, the UML set has class, interface, enumeration and package boxes with the six "
                "relations; Entity relationship has entities, attributes and crow's foot lines; Wireframe has "
                "a window, button, input, checkbox, dropdown, image, navigation bar and card. "
                "Insert, Shape picker searches the library at the pointer and Enter places the match there; More, Replace with a library shape "
                "swaps a selected shape's outline and keeps its words and connectors; dragging a copy arrow to empty space opens the picker there."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-format",
            "keywords": (
                "format panel",
                "format",
                "exact position",
                "position",
                "x and y",
                "width and height",
                "aspect ratio",
                "size preset",
                "16:9",
                "square",
                "angle",
                "rotate by",
                "flip",
                "mirror",
                "opacity",
                "transparency",
                "see through",
                "shadow",
                "shadow offset",
                "shadow blur",
                "corner radius",
                "padding",
                "text size in a shape",
                "align text",
                "text direction",
                "right to left",
                "vertical text",
                "text opacity",
                "line shape",
                "line end",
                "line ends",
                "arrowhead",
                "arrow end",
                "diamond end",
                "label position",
                "arrow size",
                "end size",
                "bigger arrowhead",
                "stealth arrow",
                "memorymap arrow",
                "signature arrow",
                "reset style",
                "default style",
                "reset an object",
                "back to default",
                "underline",
                "strikethrough",
                "font family",
                "clear formatting",
                "rounded corners",
                "round corners",
                "curved line",
                "line style",
                "dash pattern",
                "custom dashes",
                "flow animation",
                "marching ants",
                "jump size",
                "connector gap",
                "clear waypoints",
                "clear bends",
                "gradient",
                "hatch",
                "fill style",
                "pattern fill",
                "crop a picture",
                "crop to a circle",
                "trim a picture",
                "rectangle crop",
                "replace a picture",
                "swap an image",
                "picture shape",
                "line jumps",
                "line jump",
                "crossing lines",
                "lines cross",
                "hop over",
            ),
            "body": (
                "The top bar's Format button, Ctrl+Shift+P or View > Format panel opens "
                "the Format panel on the right, with three tabs. Style: line colour, width and pattern, "
                "your own dashes (like 8 4), a line style (sharp, rounded or curved), flow (dashes that move), "
                "fill (gradient, hatch, dots or zigzag), fill and line opacity (presets 0 to 100), opacity, shadow, box corner radii and padding, a picture's crop and trim, and for a connector its line shape (curved, straight or elbow), "
                "its line jumps (an arc, a gap or a "
                "peak over a line under it, of a size you set), a gap to stop short of the shape at each end, its two ends (twenty-one marks, three sizes) "
                "and where its label sits. Text: font (default, serif, monospace, wide sans, handwritten), size, colour, bold, italic, underline, strikethrough, "
                "line and letter spacing, direction (right to left or vertical), text opacity, alignment and vertical place of a box's or shape's words, and for a shape's words a background, outline, outside place, own width, wrap and per-side spacing; Clear text formatting and larger or smaller text are in the command palette. Arrange: Position (X, Y), Size (W, H, with a ratio lock), an Aspect menu (1:1, 4:3, 16:9, A4), "
                "angle, flip, and the order, align, spacing, group and lock buttons. Each group's ? says what its controls do. With "
                "several items selected, a value they differ on reads Mixed. Every "
                "change is one undo step. Reset style (right-click menu or Ctrl+K) restores the defaults. "
                "Colours are in Fill, border and recent colours. Bends, connection points and imports are in Connector bends and importing."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-connectors",
            "keywords": (
                "elbow",
                "entity relation line",
                "isometric line",
                "right angle",
                "orthogonal",
                "connector shape",
                "bend",
                "waypoint",
                "crow's foot",
                "crows foot",
                "er diagram",
                "connection point",
                "connection points",
                "edit connection points",
                "add a connection point",
                "reset connection points",
                "port",
                "ports",
                "anchor point",
                "entity relationship",
                "mermaid",
                "subgraph",
                "sequence diagram",
                "class diagram",
                "state diagram",
                "drawio",
                "draw.io file",
                "open a drawio file",
                "import a flowchart",
                "clone and connect",
                "copy and connect",
                "next shape",
                "copy a shape",
                "connect it to the copy",
                "connect the copy",
                "new note next to",
                "arrows round a card",
                "dimension line",
                "second label",
                "two labels on a connector",
                "measure",
                "measure between",
                "length of a line",
                "show the length",
            ),
            "body": (
                "Every connector takes bends: drag the small ring in the middle "
                "of a run (or double-click the line) to add one, drag a bend to move it, double-click it to "
                "take it out. A straight line runs through its bends, a curved one curves through "
                "them, an elbow turns at right angles round the shapes it joins; Entity relation and "
                "Isometric take no bends; changing the line shape keeps them. "
                "With Select, pointing at a shape, card or text box shows its connection points; drag from one to draw an "
                "elbow connector to whatever you let go on, or to a free end. "
                "Arrange, Edit connection points gives a shape points of its own (press the outline to add, a point to remove); Reset connection points undoes it. "
                "Drag a connector's label by its words to slide "
                "it along the line; Format sets its size, colour, bold, a chip and a second label. With one shape or text box selected, the four arrows round it "
                "(or Alt+Shift and an arrow key) copy it that way and join facing sides with an elbow; View, Connection arrows and Connection points hide them; "
                "a note card's arrows make a new note there instead, joined and ready to type. With two or more selected, Arrange, Tidy and connect joins them in a line or to the first picked. Measure with a dimension line gives its length. Drag a connector's end square onto another shape to re-point it. "
                "Insert, Diagram, Mermaid, draw.io or board SVG brings in a Mermaid flowchart, state, class or "
                "sequence diagram, a .drawio file (pages and swimlanes as frames) or an SVG a board "
                "here exported, as shapes and connectors; Export writes an Outline, a Mermaid flowchart or a .drawio file."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-diagram-tools",
            "keywords": (
                "tidy a diagram",
                "tree layout",
                "lay out as a tree",
                "auto layout",
                "layout a flowchart",
                "zoom to selection",
                "zoom to the selection",
                "zoom to fit the selection",
                "shift+2",
                "change shape",
                "change the shape",
                "swap a shape",
                "turn a rectangle into",
                "replace shape",
                "shrink to fit",
                "text too big for the shape",
                "fit the text",
                "text overflows the shape",
                "link a shape",
                "link to a web page",
                "link a shape to a note",
                "hyperlink on a board",
                "open a shape's link",
                "home key",
                "back to the top left",
                "reset the view",
                "clear labels",
                "shift+delete",
                "delete the labels",
                "replace one match",
                "link to a page",
                "link to a frame",
                "self loop",
                "loop on a shape",
                "connector to itself",
                "parallel connectors",
                "space the connectors",
                "two lines between the same shapes",
                "flip the layout",
                "mirror a diagram",
            ),
            "body": (
                "Shift+2 (or View, Zoom to the selection) frames what is selected, "
                "up to twice its size. Tidy as a tree, in Arrange, Tidy and connect, the selection's More and the right-click "
                "Arrange, lays the selected shapes out along the connectors between them, top to bottom or "
                "left to right: a shape no connector points into is a root, siblings keep their order, and "
                "one Undo takes it back. It is offered once the selection holds a connector. Change the "
                "shape…, in a closed shape's More, the right-click Arrange and Ctrl+K, turns it into another "
                "kind (rectangle, ellipse, diamond, cylinder, cloud and the rest) in the same box, keeping "
                "its text, colours, line and connectors. Link…, in a shape's, text box's or picture's More "
                "and its right-click menu, links it to one of your notes, a page (frame) of this board or a web page (or an app link "
                "from Copy app link); a small mark on its top-left corner opens it, and the same Link… changes or removes it. Fit, in the Format "
                "panel's Text tab for a shape (or Ctrl+K, Shrink the text to fit), makes long words shrink "
                "until they fit inside the shape, never past the size you gave them. "
                "Home goes back to the top left of what is drawn at the zoom you have, and Shift+Home resets the view to 100% there. "
                "Shift+Delete clears the labels of the selected shapes and connectors; one Undo puts them back. "
                "In the find bar (Ctrl+H), Replace changes the current match and moves on; Replace all changes every one. "
                "Arrange, Loop on the shape draws a connector from a shape back to itself; Format, Loop side moves it. "
                "Arrange, Space parallel connectors fans the connectors that join the same two shapes so none hides another "
                "(it leaves a connector with bends of its own alone), and Layout, left to right or top to bottom, "
                "swaps the selected shapes' places across the middle of the group, with their connectors' bends, and turns no shape itself."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-workshop",
            "keywords": (
                "vote",
                "voting",
                "voting dots",
                "dot voting",
                "vote dot",
                "dots on a note",
                "workshop",
                "timer",
                "workshop timer",
                "countdown",
                "time box",
                "timebox",
                "retro",
                "brainstorm",
            ),
            "body": (
                "Voting dots and a timer, for a workshop. Select notes, text boxes, pictures or frames and "
                "choose Board, Workshop, Add a vote dot: each takes a dot, drawn as a count on its top-right "
                "corner, and each press adds one (up to 99). Ctrl+K, Take a vote dot off, removes one; "
                "Clear all vote dots empties the board; one Undo takes back a press. Workshop timer… opens "
                "1, 3, 5, 10, 15 or 30 minutes: a clock under the board's top bar counts down and says "
                "when time is up; its X stops it. The timer is for this window only and is not saved."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "board-paste",
            "keywords": (
                "paste on a board",
                "paste options on a board",
                "board paste special",
                "paste text on the board",
                "paste a spreadsheet",
                "paste as a table on a board",
                "paste as stickies",
                "paste as a mind map branch",
                "paste into a shape",
                "paste without comments",
                "pasted picture size",
                "paste a list onto a map",
            ),
            "body": (
                "Text from another app goes in at once: a web address as a link box, "
                "one line as a text box, a few lines as a sticky each, and rows copied from a spreadsheet as a "
                "table. A Paste options chip then appears under what was made; press Ctrl, then a letter, or "
                "open it: Stickies (S), One text box (T), Bullet list in a shape (B), Mind map branch (M, "
                "indentation is depth, joined by connectors), Table (A, from tabs or CSV) or Plain text (P). "
                "A choice replaces the paste and is one Undo step; Esc, typing or a click closes the chip. "
                "Paste special, in the Edit menu and Ctrl+K, pastes on purpose in one of those forms, and "
                "Paste into the selected shape's text writes the clipboard into the shape or connector. "
                "Paste without comments (Ctrl+Alt+Shift+V, or right-click the canvas) drops copied comment threads; Paste keeps them. "
                "A pasted picture keeps its own size, shrunk only to fit the view, and a picture copied as "
                "markup or an inline image pastes too; one over 50 MB is refused at once, and a picture "
                "that is only a web address is not fetched, because the notebook works offline (save it "
                "and paste the file). On a mind map, lines pasted "
                "with a topic selected become its child branches, indentation as depth, and the chip offers "
                "the lines as one topic instead. If the browser will not let the app read the clipboard, "
                "Paste special applies to your next Ctrl+V."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "mind-map-controls",
            "keywords": (
                "cross-link",
                "cross link",
                "outdent",
                "fold",
                "unfold",
                "radial",
                "ring",
                "opml",
                "freemind",
                "colour by",
                "color by",
                "focus on a branch",
                "tidy",
                "layout of the map",
                "duplicate a topic",
                "copy a topic",
                "undo steps",
                "how many undo",
                "topic before",
                "topic after",
                "move a topic",
                "reorder topics",
                "parent topic",
                "insert a parent",
                "checkbox on a topic",
                "topic a task",
                "tick a topic",
                "number the branches",
                "numbered topics",
                "outline numbers",
                "note on a topic",
                "note behind a topic",
                "comment on a topic",
                "boundary",
                "summary topic",
                "summarise topics",
                "resize a topic",
                "topic size",
                "bigger topic",
                "text size on a topic",
                "topic bar",
                "topic toolbar",
                "several topics",
                "select several topics",
                "many topics at once",
                "bold several topics",
                "fold several branches",
                "show levels",
                "fold to a level",
                "only the first levels",
                "collapse to level",
                "summarise this branch",
                "summarize this branch",
                "summary of a branch",
                "sort branches",
                "sort a topic's branches",
                "alphabetical branches",
            ),
            "body": (
                "Mind map keys (Library, Boards and maps). With a topic selected: Tab adds a child, Enter adds a "
                "topic right after it and Shift+Enter right before it (what you "
                "type next is the new topic's words), Ctrl+D copies it as the "
                "next sibling, Ctrl+Shift and the arrows move it among its "
                "siblings, Shift+Tab outdents it, Ctrl+Enter gives it a new parent, M (Move under…) re-parents it, "
                "the arrow keys walk the tree, "
                "F2 or double-click renames (while typing, Enter breaks the line, Esc "
                "keeps the name, Tab or Ctrl+Enter adds the next topic, / and [[ add "
                "links), Delete removes the topic and "
                "everything under it, C folds or unfolds its branch (or click the "
                "chevron), Alt+1 to Alt+9 show that many levels "
                "(Alt+1: the trunks alone), Alt+= and Alt+- show one more or one less level, Shift+C draws a cross-link to another topic, F shows "
                "only this branch and its neighbours (F again: all), Shift+F10 "
                "opens every action. Ctrl+Z undoes (100 steps, kept across a "
                "reload), Ctrl+Shift+Z redoes. "
                "Right-click a topic for the ring: Add child, Add beside, Fold, "
                "Delete, Move under, Cross-link and More; hold Alt on the ring to remove "
                "instead of add. Dragging a topic onto another moves its whole "
                "branch; double-click a line to label it. A selected topic has "
                "its bar above it: the colour, the text size (minus and plus "
                "round the size it reads, S to XL), and Text, Shape and Branch "
                "line, each a panel of rows: a preview of each look, and a "
                "reset arrow back to following the map. Drag the square on its bottom right corner to resize it; "
                "hold Shift as you drag to scale its text with it. Pick several "
                "topics (drag round them, or Shift-click) and the bar and "
                "the right-click menu act on all of them: colour, bold, tasks, "
                "fold, and a summary when they share a parent. A topic's menu "
                "has Summarise this branch: a few sentences about everything "
                "under it go into the topic's note, yours to change or keep. Ctrl+K finds Sort branches."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "mind-map-features",
            "keywords": (
                "radial",
                "logic chart",
                "timeline layout",
                "fishbone",
                "tree table",
                "colour by",
                "color by",
                "tidy",
                "layout of the map",
                "checkbox on a topic",
                "topic a task",
                "tick a topic",
                "number the branches",
                "numbered topics",
                "outline numbers",
                "note on a topic",
                "note behind a topic",
                "comment on a topic",
                "boundary",
                "summary topic",
                "summarise topics",
                "mind map features",
                "layout picker",
                "present branches",
                "show one more level",
                "marker",
                "markers",
                "priority on a topic",
                "flag a topic",
                "filter by marker",
                "map outline",
                "outline of the map",
                "dim the rest",
                "dim all but",
                "highlight a branch",
                "gantt",
                "gantt chart",
                "start day on a topic",
                "audio note",
                "audio on a topic",
                "recording on a topic",
            ),
            "body": (
                "The layout picker: tree, radial, logic chart, "
                "timeline, fishbone, tree table or free; Tidy lays every unpinned topic out again. "
                "View sets Colour by (branch, category, age, note) and opens every "
                "folded branch (Alt+1: fold every branch); Present branches shows it branch by branch. A topic's menu, "
                "Content, Markers sets a priority (1 to 5), how far along it is, a "
                "flag, a start day, a due day and up to six icons; View, Gantt chart draws "
                "a bar from start to due for each topic with both, and a dragged bar moves its dates; "
                "a topic's menu, Audio note attaches a recording from Recordings, its mic mark plays it; "
                "View, Filter by marker dims every topic "
                "without the one you pick, and View, Dim all but the selected branch "
                "dims everything outside the selected branch and its path to "
                "the centre, following the selection. The sidebar's Outline tab (View, "
                "Outline) lists the map as an indented outline: F2 renames, "
                "Shift+Enter adds a topic, Tab and Shift+Tab move it in and out a level. "
                "A topic's menu makes "
                "it a task: press its box to tick it, and every topic above "
                "counts the done ones (1/2); Markdown exports write tasks as - [ "
                "] and - [x]. View, Number the branches numbers every topic by "
                "its place (1, 1.1, 1.2), and the Markdown and OPML exports keep "
                "the numbers. A topic's menu adds a note behind it: its mark "
                "opens it; on a topic that is one of your notes, Edit the note's text… changes the note itself. "
                "Comment… starts a thread, counted on its corner; its Branch group draws a boundary "
                "round the branch or summarises topics side by side. Templates, import and export: see Mind map import and export."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "mind-map-import-export",
            "keywords": (
                "opml",
                "an opml outline",
                "import an opml",
                "freemind",
                "xmind",
                "import a map",
                "export a map",
                "map template",
                "map as a document",
                "map the headings",
                "suggest branches",
                "branches from my notes",
                "grow the map",
                "expand from my notes",
                "children from notes",
                "write a map as a document",
                "import a mind map",
                "export a mind map",
                "copy a branch as an outline",
                "export one branch",
                "export a branch",
            ),
            "body": (
                "Start from a "
                "template, import an OPML, FreeMind, XMind, Markdown or text outline "
                "(it opens as a tree), paste an indented "
                "list onto a topic to add it as that topic's branch, let the "
                "local AI propose a map from notes you pick, or on a topic choose "
                "Add, Branches from my notes… for up to five children found in your "
                "notes, each saying which note it came from; on a topic that is "
                "one of your notes, Add, Expand from my notes… offers that note's "
                "own headings and the notes it links to (no model needed); "
                "the suggestions appear faded under the topic: Tab takes one, Enter adds "
                "the taken ones, Escape drops them, and Ctrl+Z takes them back; export it as "
                "OPML, FreeMind, XMind, Markdown or text as well as a picture, or write it as "
                "a document (the board menu's Write as a document: branches "
                "become headings, deeper topics lists, notes paragraphs); a "
                "document's menu, Map the headings, goes the other way. One "
                "branch alone: a topic's Branch menu, Copy this branch as an "
                "outline (Markdown, ready to paste) or Export this branch… (a "
                "picture or PDF of it). With a "
                "map open, the command palette (Ctrl+K) lists the map's commands: "
                "add, rename, fold, focus, tidy, layout, look, numbering, present "
                "and export."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "documents-controls",
            "keywords": (
                "outline",
                "split view",
                "live view",
                "source view",
                "read view",
                "suggest changes",
                "suggestion mode",
                "track changes",
                "tracked changes",
                "read aloud",
                "accessibility check",
                "grammar",
                "word goal",
                "typewriter",
                "focus mode",
                "find and replace",
                "replace all",
                "docx",
                "word document",
                "microsoft word",
                "find in every document",
            ),
            "body": (
                "Document editor keys (Library, Documents; Ctrl+Shift+D starts "
                "one). While a document is open, Ctrl+K lists every document "
                "command (on selected text it makes a link) and ? shows the ones with keys. Ctrl+S saves, Ctrl+B "
                "bold, Ctrl+I italic, Ctrl+U underline, Ctrl+E inline code, Ctrl+Shift+S strike "
                "through, Ctrl+1, Ctrl+2, Ctrl+3 or Ctrl+Alt+1 to 6 headings, Ctrl+Shift+8, "
                "Ctrl+Shift+7 and Ctrl+Shift+9 a bulleted, numbered and task list, "
                "Ctrl+; Ctrl+Shift+; Ctrl+' Alt+= and Ctrl+Shift+' open the emoji, "
                "icon, symbol, equation and calculator, "
                "Tab and Shift+Tab "
                "indent and outdent, Ctrl+/ comments the selection (Enter ends the remark), Alt+Up / "
                "Alt+Down moves the block at the caret, and typing / opens "
                "the blocks menu (Citation picks a note or an address). Ctrl+F finds and Ctrl+H (Mac: Cmd+Option+F) replaces (F3 next, "
                "Shift+Enter previous), Ctrl+Alt+G goes to a line, and Ctrl+Shift+F finds in every "
                "document. Views: Edit, where Live renders as you write, Source "
                "is the markdown and Split puts a preview beside it, or Read. The "
                "sidebar's Outline lists the headings, and they fold. Focus mode (the corners button on "
                "the dock, the ⋯ menu on a phone, or F11) hides all but the page, with a "
                "bar for the title, save state, a Sidebar button and Exit. "
                "The formatting toolbar hides: the Formatting "
                "button in the document's bar, Ctrl+Shift+X or the bar's More "
                "menu, Show formatting toolbar, brings it back. In a Live table "
                "the arrows keep the column, Enter goes down, Ctrl+Enter leaves "
                "the table, and "
                "pasted sheet rows fill cells. Right-click a "
                "cell for the table's menu (move, sort, filter, sum, select); the grips on its "
                "edges select, drag and add rows and columns. "
                "Pasting from the "
                "web or Word keeps headings, bold, italics, "
                "lists and links; Ctrl+Shift+V pastes plain text. With nothing "
                "selected, Ctrl+C and Ctrl+X copy and cut the whole line, and "
                "pasting that line puts it above the one you are on."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "documents-list-styles",
            "keywords": (
                "list style",
                "list styles",
                "bullet style",
                "dot points",
                "numbered list style",
                "roman numerals",
                "lettered list",
                "hash tag",
                "tag completion",
            ),
            "body": (
                "List styles (Library, Documents). The arrow beside the List and Numbered "
                "buttons picks the style: dots, circles, squares or dashes, and 1., 1), a. or i. "
                "The marker is kept in the text, so every view and the export read it, and Enter at the end of an a., i. or dash item starts the next one. "
                "A bullet pasted from elsewhere becomes a list item. In a markdown "
                "document, typing # and a letter offers the tags you have used, and "
                "in Read a #tag is a chip: press it to find the documents that have it."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "documents-replace",
            "keywords": (
                "replace in every document",
                "replace across documents",
                "replace all documents",
                "replace in all documents",
                "find and replace everywhere",
                "bulk replace",
            ),
            "body": (
                "Replace in every document (the document's ⋯ menu or Ctrl+K). "
                "Type what to find, and the list shows every document that has "
                "it, with the first match in its line. Untick a document to "
                "leave it out. When more than one document would change, the "
                "first press of Replace all asks and the second does it; the "
                "toast's Undo takes every document back at once. A pattern that "
                "does not read says so before anything runs. The find panel "
                "(Ctrl+F) has All documents and Replace in all beside its match "
                "count: they open these with what you typed, its replacement "
                "and its options."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "spelling-check",
            "keywords": (
                "why is uni flagged",
                "wrong spelling suggestion",
                "bad spelling suggestions",
                "word keeps getting underlined",
                "add to dictionary",
                "my own words",
                "slang flagged",
                "spelling dialect",
                "australian spelling",
            ),
            "body": (
                "Spelling gets a second opinion on this computer. A word is not "
                "flagged when an Australian or British dictionary knows it, or "
                "when your own notes use it twice or more (a private note never "
                "counts). A suggestion that would change more than a third of a "
                "short word is not offered, and the rest come with the commonest "
                'word first. "Add to dictionary" sits beside "Ignore this one" in '
                "a note box and in a document, and keeps the word in your "
                "notebook. The spelling preference (Settings, General, Writing; "
                "or the document dictionary dialog) starts as this computer's "
                "language."
            ),
            "badge": {"label": "Documents", "tab": "documents"},
        },
        {
            "id": "live-view-marks",
            "keywords": (
                "markdown marks",
                "formatting marks",
                "asterisks showing",
                "markdown shows when i click",
                "live preview",
                "show the markdown",
                "hide the markdown",
                "like obsidian",
            ),
            "body": (
                "In a document's Live view (and a note's edit box), a formatted "
                "phrase (bold, italic, code, strike through, a highlight, a link, "
                "a wiki link, an equation) shows its markdown only while the caret "
                "is in it or next to it, and the rest of the line stays rendered. "
                "Every caret and selection counts. A heading, list or quote shows "
                "its mark while the caret is on its line, and a code block while "
                "the caret is in it. Source view shows all of it. A fenced block that "
                "names a language (python, js, html, css, sql and more) is coloured "
                "as that language while you edit it, indents and closes brackets "
                "as it does, and suggests its words as you type; typing the name "
                "after the opening fence lists the languages. The block's corner "
                "shows its title (title=\"fit.py\" on the fence) or language; press it "
                "to pick another language."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "documents-paste",
            "keywords": (
                "paste special",
                "paste options",
                "paste as",
                "paste as plain text",
                "paste as table",
                "paste as code",
                "paste as quote",
                "paste link",
                "paste checklist",
                "match surrounding",
                "keep formatting",
                "text only",
            ),
            "body": (
                "After a paste that changed form (a "
                "web page or Word copy turned to Markdown, several lines, a "
                "spreadsheet's rows, a web address) a Paste options chip appears at "
                "the caret. Press Ctrl, then a letter or the arrows and Enter: Keep "
                "formatting, Text only, Match surrounding, or read the same text as "
                "a table, checklist, quote or code block. One Ctrl+Z undoes the "
                "choice; Esc or typing closes the chip. Paste special, in the "
                "document menu and the palette (F1), pastes on purpose as plain "
                "text, Markdown source, matching the surrounding text, a code block (language guessed), a "
                "quote, a table from a spreadsheet or CSV, a link or a checklist. "
                "A web address pasted over selected words makes a link. If the "
                "browser will not let the app read the clipboard, Paste special "
                "applies to your next Ctrl+V. Right-click in the text for the same "
                "choices under Paste as, beside Cut, Copy, Paste, Turn into and Select all (hold "
                "on a phone); Shift+right-click opens the browser's own menu, with "
                "its spelling suggestions."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "documents-comments",
            "keywords": (
                "document comments",
                "remark",
                "remarks",
                "reply to a remark",
                "edit a reply",
                "delete a reply",
                "resolve a remark",
                "resolved remarks",
                "reopen a remark",
                "comment thread in a document",
                "who wrote a comment",
            ),
            "body": (
                "Select words and choose Style, Comment: "
                "they are highlighted and a remark follows them, kept in the text "
                "as ==words== %%the remark%%, so it opens anywhere else the same. "
                "The sidebar's Outline lists every remark with the words it is "
                "about, who wrote it (your name from Settings, Profile) and when. "
                "Reply on a row adds a line under it; Enter posts, Esc cancels. "
                "A reply has a pencil to reword it and a bin to delete it (Undo "
                "brings it back); a resolved remark can still be replied to. "
                "Resolve takes the remark out of the text and keeps the thread: "
                "Show resolved lists it, and Reopen puts the remark back on its "
                "words (Ctrl+Z right after a resolve does the same). Replies and "
                "bylines are saved with the document but are not in the text, so a "
                "download shows each remark as a footnote and nothing more."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "documents-turn-into",
            "keywords": (
                "turn into",
                "turn a block into",
                "change a paragraph to a heading",
                "convert block",
                "paragraph to heading",
                "paragraph to list",
                "make this a quote",
                "make this a callout",
                "make this a to-do",
            ),
            "body": (
                "Turn into changes the block at the caret, or every line you have "
                "selected, to a paragraph, heading 1 to 3, bulleted, numbered or "
                "to-do list, quote, callout or code block, taking the old marker "
                "off first. Select text and press the swap button on the selection "
                "bar, press Turn into on a phone's formatting bar, or choose Turn "
                "into in the palette (Ctrl+K). One Ctrl+Z puts the block back. A "
                "caret inside a code block is left alone."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "documents-to-note",
            "keywords": (
                "selection to a note",
                "new note from selection",
                "add to note",
                "append to a note",
                "turn a selection into a note",
                "highlight text and make a note",
                "send text to a note",
            ),
            "body": (
                "Select text in a document or a code file and choose New note from "
                "selection to start a note from it, or Add to note to pick an "
                "existing note and append it. Both are on the selection bar (the "
                "note button) and in the right-click menu. The text lands as a "
                "quote, or as a code block in a code file, with a From [[Title]] "
                "line under it that links back to the document. Undo on the "
                "notice, or Ctrl+Z, takes it back."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "documents-features",
            "keywords": (
                "history of a document",
                "word goal",
                "typewriter",
                "footnote",
                "footnotes",
                "page break",
                "newpage",
                "docx",
                "word document",
                "microsoft word",
                "extract notes",
                "ai edit",
                "serif",
                "full width",
                "document statistics",
                "reading ease",
                "change case",
                "sort lines",
                "number headings",
                "insert date",
                "copy as formatted text",
                "text size",
                "line spacing",
            ),
            "body": (
                "Press the counts in the status bar "
                "for Document statistics (words, sentences, reading and speaking "
                "time, reading ease, the words you lean on). The command palette "
                "(F1) changes the selection's case, sorts its lines or drops "
                "duplicates, numbers the headings (1, 1.1) or takes the numbers "
                "off, inserts today's date or the time, and copies the page or the "
                "selection as formatted text to paste into Word or an email. "
                "Text size (Ctrl+wheel too) and spacing: document menu. The document's menus hold History "
                "(every version, and a way back to any), Connections, Extract "
                "notes, AI edit, a word goal, typewriter scrolling, dim all but "
                "this paragraph, serif for reading and full width. With no model "
                "connected, AI edit says why when pressed and "
                "offers Set up a model. Footnotes show "
                "as numbered notes at the foot in Read view, in print and in the "
                "HTML download. A page break (the / menu's Page break, written "
                "\\newpage on its own line) starts what follows on a new page when "
                "the document is printed or saved as a PDF. Writing checks: "
                "spelling against your own dictionary, grammar checked on this "
                "machine, an accessibility check (a skipped heading level, an "
                'image with no description, link text like "click here"), Suggest '
                "changes (tracked changes to accept or reject one at a time or "
                "all at once), Read aloud (Esc stops), autocorrect, and word "
                "suggestions (Tab accepts). Word: Download as .docx is written in "
                "the app and keeps headings, emphasis, "
                "links, nested lists, tables, code (with its language), pictures, "
                "task boxes, footnotes (as Word footnotes), formulas (as Word "
                "equations), diagrams (as pictures), [TOC], callouts and columns (as Word's own) and suggested changes as "
                "Word's tracked changes; a .docx added "
                "in the Library is read with its headings, lists, tables, code "
                "and pictures, its tracked changes as suggestions; other downloads "
                "are .md, .html, a .zip "
                "with images, and print or save as PDF."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        #: L-documents-2: its own entry, the documents entry is at the reply cap.
        {
            "id": "writing-streak",
            "keywords": ("daily goal", "daily word goal", "writing streak", "streak", "words today"),
            "body": (
                "Right-click the counts in a document's status bar (or press the menu key on them) "
                "for the daily word goal: 250, 500, 1,000 or 2,000 words, or none. The bar then adds "
                "how far today is, such as 120 of 500 today. Only words you add to a text document "
                "count, a paste does not, and the tally starts again each day. A day that reaches the goal "
                "adds to your streak; a missed day starts it again from one. The menu's first row "
                "says today's words and the streak. It is counted on this device only. "
                "The per-document word goal beside the counts is separate."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        #: INBOX 486, the owner on a callout: "I have no clue how to use these
        #: things". Its own entry: the documents entry is at the reply cap.
        {
            "id": "callouts",
            "keywords": (
                "callout",
                "callouts",
                "change the kind",
                "note box",
                "warning box",
                "tip box",
                "admonition",
                "collapsible callout",
            ),
            "body": (
                "Callouts: type / in a document or a note and pick Note, Tip, Warning "
                "or another kind. The box is tinted by its kind and its icon names "
                "it; click the icon to change the kind or to make the box fold. The "
                "first line, after the icon, is the title, written like any text, "
                "and the lines under it are the body (an empty body says what goes "
                "there). Source view shows the markdown: > [!tip] Title."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "graph-controls",
            "keywords": (
                "similarity",
                "strength slider",
                "gravity",
                "spread",
                "saved view",
                "save a view",
                "graph view",
                "graph options",
                "display options",
                "trace",
                "unpin a node",
                "pin a node",
                "pin on the graph",
                "pin a note on the graph",
                "cluster glow",
                "label background",
                "entities",
                "hide unlinked",
                "minimap",
                "export as png",
                "lasso",
                "zoom",
                "pan",
                "link reason",
                "why linked",
                "connection",
            ),
            "body": (
                "Click the map, then the arrow keys move between notes, N steps "
                "to the next connected note, Enter or Space opens one, + and - zoom, 0 fits the whole "
                "map, Shift and the arrows pan, Esc leaves. Drag a note to move it (it settles near the "
                "drop); double-click it to pin it, again to free. Hold Alt and drop one note onto another to link "
                "them, double-click empty space to add a note (Private seals it; ? says more), hover a note for its dates, links "
                "and properties, point at a line to light it and click it to see what it is, its reason and "
                "how sure, the two notes, and for a link Edit reason, Two-way (no arrow) and Remove, and "
                "click a legend colour to hide that category. Shift and drag on empty map boxes notes, "
                "and the selection bar can Pin, Unpin, Tag, Link together, Unlink (all undoable with Ctrl+Z) or make"
                " a Mind map of them, built from their links round the picked or most connected note, "
                "with Open on the notice that follows. Options (the gear) opens with View: Layout"
                " (Force, Tree, Radial, Arc, Treemap or Tessellation, in Cells or Hexes), "
                "Shape (Organic, Clusters or Galaxy; the Force layout's own, dimmed under the others), Colour, Size, Match "
                "strength (with Similarity on: higher is closer), Trace, which "
                "finds how two notes connect, and Legend, which hides the key. Then Physics (Unpin all, "
                "Reshuffle layout, Gravity, Spread, Tidy spacing; More graph controls has the rest),"
                " the Show switches (Similarity, Entities, Documents, Boards, Tags, Attachments, "
                "Unwritten links, Hide unlinked), Display (Labels, Label backgrounds, Curved links, "
                "Cluster glow, Arrows, Fit on view change), a Time filter you can play, Groups that paint notes matching some words one "
                "colour, the minimap's position and size, and Reset, which restores the layout, colours, "
                "physics, switches, time filter and minimap, keeping groups and saved views. Saved "
                "views keep the layout, filters and position under a name."
            ),
            "badge": {"label": "Graph", "tab": "graph"},
        },
        #: GRAPH_PLAN 514, Obsidian's graph parity: its own entry, since
        #: graph-controls is near the reply cap.
        {
            "id": "graph-display",
            "keywords": (
                "local graph",
                "focus depth",
                "depth",
                "incoming",
                "outgoing",
                "neighbour links",
                "tags as nodes",
                "unwritten link",
                "unresolved link",
                "ghost node",
                "attachments on the graph",
                "arrows",
                "text fade",
                "link thickness",
                "link force",
                "label background",
                "topic",
                "topics",
                "subjects",
                "outline",
                "colour by topic",
                "rename a topic",
                "drag a topic",
                "move a topic",
                "topic chip",
                "filter links",
                "kind of link",
                "hide links",
                "property chips",
                "note type",
                "colour by type",
            ),
            "body": (
                "Show adds Tags (a node per tag), "
                "Attachments (a node per file or picture) and Unwritten links: each "
                "[[name]] no note answers to is a faint node, and clicking it writes "
                "that note, named in its heading, linked from every note that named "
                "it. Display holds Labels, Label backgrounds (off draws names on a "
                "thin outline), Curved links, Cluster glow, Arrows (off at first: a "
                "spark on each link, its tail toward the note that made it; pointing at a note sends a spark along "
                "its links unless motion is reduced), Fit on view change, Text fade (how far out names stay on a big "
                "map) and Link thickness. Physics adds Link force, Length by "
                "similarity and Group by category. In focus mode a Focus section sets "
                "Depth (1 to 5 links) and Incoming, Outgoing and Neighbour links; "
                "the Local map beside a note has the same four under Options. "
                "Colour: Topic outlines each subject inside a cluster, names it by "
                "the tag, person or word its notes share most, and its legend entry "
                "finds those notes and opens its card, where Summarise asks your "
                "local model for one sentence (with none, Summary (no AI)), "
                "File as a category files its notes under one category, "
                "and the pencil renames it (the arrow brings the found name back). "
                "On the map, drag a topic's name to move all its notes together "
                "(they stay put; Unpin all releases them), double-click it to rename, "
                "click it for its card. A note's card and its panel show its topic; "
                "pressing it opens the graph on that topic. "
                "No note's name is drawn over a topic's name. Filter holds a chip per "
                "kind of link on the map (press one to take those links off, again "
                "to bring them back) and per property value (press to light those "
                "notes). Colour: Note type paints each note its type's colour "
                "(Person, Project, Meeting, Book and Place come built in). "
                "In Trace, a step marked +2 has two more reasons "
                "its notes relate; point at it to read them."
            ),
            "badge": {"label": "Graph", "tab": "graph"},
        },
        #: INBOX 1400, the owner: the graph's controls "aren't really easy to
        #: understand". Its own entry, since graph-controls and graph-display
        #: both sit at the reply budget.
        {
            "id": "graph-options-help",
            "keywords": (
                "what does gravity do",
                "what does spread do",
                "what do the options do",
                "options panel",
                "question mark",
                "what is physics",
                "what is minimap",
                "what does filter do",
                "what is groups",
                "time slider",
                "play through time",
                "tidy spacing",
                "dots on lines",
                "dots overlap lines",
            ),
            "body": (
                "Every section of the graph's Options (View, Physics, Show, Display, Filter, Time, "
                "Groups and Minimap) has a ? beside its name that says in a line what each of its "
                "controls does to the map. Physics shapes only the Force layout; its Tidy spacing "
                "(off by default) keeps dots off the lines but a large notebook settles slower. Show, "
                "Display, Filter, Time, Groups and Minimap fold away; open one to change it, and "
                "Reset to defaults puts them all back."
            ),
            "badge": {"label": "Graph", "tab": "graph"},
        },
        #: GRAPH_PLAN KG4: note properties and note types.
        {
            "id": "properties",
            "keywords": (
                "property",
                "properties",
                "frontmatter",
                "yaml",
                "note type",
                "note types",
                "fields",
                "field",
                "status",
                "metadata",
                "query",
                "live query",
                "type:",
                "prop:",
                "table view",
                "rollup",
                "rollups",
                "roll up",
                "custom metadata",
                "find by property",
                "document cover",
                "document icon",
                "page cover",
            ),
            "body": (
                "A note can carry properties (status: open, owner: Priya), kept "
                "at the top of its own text between two --- lines, the way "
                "Obsidian writes them, so an imported vault keeps them and an "
                "export carries them. They show as a small table under the "
                "note's title, where pressing a value finds every note with it; "
                "a note's panel on the graph shows them too, a value lighting "
                "those notes on the map, with Add or Edit beside its Properties heading. A note's ⋯ has Properties: add, change or remove "
                "one, or pick a Type, and Save rewrites only those lines. Note "
                "types in the command palette makes a kind of note (Meeting: "
                "attendees, date) with fields that are text, a number, a date, a "
                "list, yes/no or another note (the magnifier beside a note field "
                "searches your notes for it); its New note starts with them. A "
                "document's properties panel does the same: with type: Meeting "
                "in its properties, the type's fields it has not written yet "
                "show as empty rows, and a value you enter is written as one "
                "line. Its Add icon and Add cover set an emoji or icon and a colour band, kept as icon: and cover: lines. "
                "A lang property such as fr turns the spelling check off for a "
                "document, because only the English list is installed. "
                "The notes filter asks about them: type:meeting, prop:status=open "
                '(a value with a space in quotes: prop:status="in progress") '
                "(or prop:effort>2), links:[[Kiln plan]], rel:supports, "
                'entity:"Sam Lee", with - before any of them to leave those out; '
                "a bar over the list then shows the same notes as a Table, with "
                "their properties as columns, or lit on the graph. The table's "
                "last row rolls each column up over every match: Count, and Sum, "
                "Min and Max for numbers, Earliest and Latest for dates. On the "
                "graph, View, Colour, Note type paints each note by its type; a "
                "type's ⋮ in Note types has Colour to choose which."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        #: GRAPH_PLAN KG5: the entity layer, its page and its list.
        {
            "id": "entities",
            "keywords": (
                "entity",
                "entities",
                "people",
                "person",
                "people and things",
                "place",
                "places",
                "organisation",
                "who is",
                "other names",
                "alias",
                "aliases",
                "merge names",
                "named together",
            ),
            "body": (
                "Atlas notes the people, places, projects, organisations and things "
                "your notes name, with a kind for each. Show, Entities on the Graph "
                "draws them; two named together in two notes or more are joined. "
                "Click one, or open People and things from the command palette, for "
                "its page: every note that names it with the sentence, what it is "
                "named with, and the dates its notes mention. Its ⋯ sets the Kind, "
                "Renames it, edits Other names (the names it also goes by) and "
                "Merges it into another, moving every mention; Undo in the toast, "
                "or Ctrl+Z, splits the two back as they were. Suggestions, Names "
                'offers the merges that look right ("Sam" and "Sam Lee").'
            ),
            "badge": {"label": "Graph", "tab": "graph"},
        },
        {
            "id": "chat-controls",
            "keywords": (
                "fork",
                "compress",
                "regenerate",
                "plan first",
                "attach a note",
                "checklist",
                "heads up",
                "attach panel",
                "attach a picture",
                "export the chat",
                "stop the answer",
                "stop an answer",
                "source mark",
                "numbers in an answer",
                "numbered",
                "citation number",
                "footnote",
                "evidence",
                "show the evidence",
                "square brackets",
                "note name in an answer",
                "supported",
                "unsupported",
                "from your notes",
                "why this source",
                "queue",
                "queued message",
            ),
            "body": (
                "Enter sends, Shift+Enter starts a new "
                "line; Escape or Ctrl+. stops the answer (what was written stays, with a Continue button), Ctrl+Shift+O starts a new chat, "
                "and one sent mid-answer queues above the box (Edit, Remove). "
                "Ctrl+Shift+G turns agent mode on or off, Ctrl+Shift+P clips a note "
                "to your next question, and Ctrl+Shift+A opens the same agent over "
                "any tab. Typing / in the box opens the chat menu: attach a note, a "
                "document, a file or an image, upload one, Web search, "
                "Plan first, Skills, Commands, "
                "and Agent or Ask mode. The note button beside the box opens Attach: "
                "a tab each for notes, documents, files, images and mind maps, with "
                "a search; the arrows move, Space "
                "or Enter ticks, Enter in the search box is Done. Each message's menu can copy it, edit your "
                "question, regenerate from here (Run again confirms), save it as a note or read it "
                "aloud. Over 20,000 characters stays in the box (Save as a note and ask). The header can fork the conversation, compress the earlier "
                "messages, show how full the model's context is "
                "(press it for what fills it), "
                "switch the model, and export the chat as Markdown. A numbered "
                "source mark in an answer shows a preview of its note on hover or "
                "focus (the passage it came from, whether it supports the sentence "
                "or only partly, and three bars for why: Words it "
                "shares, Meaning, Links), a press "
                "keeps it open, and Open note goes there. A [note name] in square "
                "brackets previews on hover. The button at the end of "
                'Grounded in says how many sentences came from your notes ("9 of '
                '11 from your notes"); it opens the evidence, each sentence beside '
                "the passage it came from, and No note says this beside the ones "
                "none backs. When an agent "
                "answer takes more than one step, a checklist above it ticks off "
                "each round, what it searched or read, then the answer. A number "
                "or name in an answer that nothing it read contains gets a "
                "heads-up under it, so check it first."
            ),
            "badge": {"label": "Chat", "tab": "chat"},
        },
        {
            "id": "chat-context",
            "keywords": (
                "context window", "context pill", "oldest messages", "oldest exchanges", "long chat",
                "model forgot", "forget the start", "forgets earlier", "forgot earlier", "did not see", "no longer fit", "too long to fit",
            ),
            "body": (
                "The context pill in the chat header shows how full the model's "
                "window is; press it for what fills it. When a long chat outgrows "
                "the window, the oldest exchanges are left out of what the model "
                "reads, and a line under the reply says how many. Compress in the "
                "header summarises the earlier messages so the gist stays in view; "
                "a new chat (Ctrl+Shift+O) starts empty."
            ),
            "badge": {"label": "Chat", "tab": "chat"},
        },
        {
            "id": "notes-controls",
            "keywords": (
                "search syntax",
                "search operator",
                "filter syntax",
                "is:favourite",
                "tag:",
                "cat:",
                "exact phrase",
                "select several",
                "batch",
                "move several",
                "several notes",
                "multiple notes",
                "bulk",
                "notes filter",
                "filter notes",
                "blocks menu",
                "slash menu",
                "several notes at once",
                "filter by date",
                "is:draft",
                "title:",
                "before:",
            ),
            "body": (
                "In Capture a thought, Ctrl+Enter saves, "
                "/ (or Ctrl+/) opens the blocks and commands menu, Ctrl+J asks "
                "Atlas to write at the cursor, and selecting text shows an actions "
                "menu (Ctrl+Shift+E from the keyboard). From anywhere, Ctrl+Shift+N "
                "starts a note, Ctrl+D opens today's note and Ctrl+Shift+R records a "
                "meeting. In the list, Up and Down move note to note and Tab walks "
                "that note's buttons. The filter box understands, with no AI: two words (both, "
                'in any order), "a quoted phrase", tag:work, cat:recipes, '
                "#tag, title:, in:, before: and after: (a date such as 2026-09, or a day word such as "
                "today, tuesday, march or 2w; before: leaves "
                "its own day out unless Settings, General, Search counts it), "
                "is:favourite, is:pinned, is:private, is:linked, is:untagged, "
                "is:draft, tags:<2 (also <=, > and >=), has:link (also file, image or "
                "reminder), space:work and kind:note (asked of the search engine), and -word to leave a word "
                "out. is:review lists the filings to check (Atlas's estimate is under 50%, "
                "or it left the note in Uncategorised), each with Accept, Refile and "
                "Split; the Categories widget on the dashboard counts them. Select ticks several notes to move to a category, tag or "
                "delete together, and Select all ticks the whole page; the "
                "selection bar's Tags adds or removes tags on every selected note, "
                "and its ... menu adds to or removes from Favourites, archives, "
                "publishes drafts, removes a tag, moves them to another space or "
                "exports them as Markdown, each undoable. In Agent mode, Atlas can "
                "move chosen notes to a category or a space once you confirm, "
                "and Undo puts them back. Editing a note shows "
                "its words and reading time beside Save."
            ),
            "badge": {"label": "Notes", "tab": "notes"},
        },
        {
            "id": "library-controls",
            "keywords": ("sub-tab", "subtab", "sort the library", "select all", "boards and maps"),
            "body": (
                "The sub-tabs are plain words with a line under the one you are on (Notes and the document sidebar draw theirs the same way): All (everything you have made), "
                "Documents, Boards & maps, Images, Files, Skills, Bookmarks and "
                "Contents. Search, then sort newest first, oldest first, A to Z or "
                "biggest first, and set how many show per page. Tick a card's box "
                "to select it: the bar that appears has Select all, Open, Restore "
                "(for binned items), Delete and Done, and Documents and the gallery "
                "have bars of their own. New (a whiteboard or a mind map), Map from "
                "notes and Import outline sit on Boards & maps; Images takes "
                "uploads of pictures and PDFs."
            ),
            "badge": {"label": "Library", "tab": "library"},
        },
        {
            "id": "timeline-controls",
            "keywords": (
                "time bucket",
                "feed view",
                "table view",
                "calendar view",
                "month view",
                "week view",
                "reschedule",
                "jump to today",
                "density strip",
                "group by",
                "add an event",
            ),
            "body": (
                "Feed shows the newest first, grouped by date; Table shows every "
                "column, sortable; Calendar shows a month, a week (hour rows) or a day: reminders and "
                "meetings at their time, a day's page at the top of its day and a chip with its title for"
                " each note (a dot each where a day is too short). Press a day to open it as a Day view; "
                "a +n opens the day in the feed. Drag a reminder to another day or hour to move it, or "
                "press Alt and an arrow on it (Undo puts it back); the arrows walk the days, Page Up and "
                "Page Down the months, T is today, Enter or Space opens the day (from a Day view, in the "
                "feed); double-click a day or an hour, or press Add or N, to add a reminder or an event (a "
                "meeting note) there. Below a tablet's width the calendar is the month's "
                "rows as a list. Pick the time bucket (Auto, Day, Week, Month or Year; Auto takes the "
                "finest one that keeps the headers few and filled: days for a few weeks of notes, weeks "
                "for a year, months for several years), what rows are grouped by (Category, Tag, Thread, "
                "None or Everything) and show only one group, how far back (the last 3 months, the last "
                "year, everything or a custom range), and which kinds of thing it shows; Jump to today "
                'returns. A note that names a date ("the deadline is next Friday", "2026-10-25") sits on '
                "that day, marked with a clock; a second date shows an arrow chip in the calendar. The "
                "arrow keys walk the rows, Home and End jump to the ends, Enter opens a row where it sits"
                " and Esc closes it; in Select mode Space ticks a row, and the bar moves, tags or deletes"
                " them. The density strip beside the feed shows how much was written when: click or drag "
                "it to go there. Above the feed, the calendar strip shows the last seven days with a dot "
                "under each day that has a page: press a day to open its page or start it (the arrows "
                "beside the month move a week, the month opens a calendar to jump to any earlier day)."
            ),
            "badge": {"label": "Timeline", "tab": "timeline"},
        },
        {
            "id": "reminders-controls",
            "keywords": (
                "magic add",
                "quick set",
                "priority",
                "tonight",
                "this weekend",
                "every",
                "calendar",
                "ics",
                "outlook",
                "google calendar",
            ),
            "body": (
                'Magic add takes a sentence ("Call mum '
                'tomorrow evening, high priority"), then Enter or the sparkle button '
                "(Add from this sentence) works out the time and the "
                'priority. Times like "tomorrow at 5pm", "next Friday", '
                '"tonight", "in 20 minutes" or "every Tuesday" (saved as a weekly repeat) are read with no AI and shown as chips '
                "under the box before Enter (press one to leave it as words); with no "
                "day or time it asks for one rather than guessing, and the AI is asked only for a phrasing those rules miss. Or type the reminder, pick a priority (normal, low or "
                "high) and a repeat (once, daily, weekly or monthly), and use Quick "
                "set: in 30 min, in 1 hour, in 3 hours, tonight 7pm, tomorrow 9am, "
                "tomorrow 2pm, this weekend or next week. A due reminder can be "
                "snoozed one hour or to tomorrow 9am (ten minutes is on its menu; Undo in the toast puts the time back), "
                "edited in place (its early alert too), or ticked "
                "done; completed ones page at the foot. Add to calendar (.ics), on "
                "a reminder's menu, saves it as a calendar file, and Add all to "
                "calendar (.ics) in the More menu saves every upcoming one (each event "
                "carries an alert at its due time, or its early alert); Add to Google "
                "Calendar and Add to Outlook, beside it, open that service's add-event "
                "page filled in, only when you press them, and never with a private "
                "note's words; Import a "
                "calendar (.ics) there reads a calendar file as reminders and names "
                "any event it skipped. Calendar beside List opens the Timeline's "
                "calendar with only reminders, where one drags to another day. Press t "
                "then r to jump here from anywhere."
            ),
            "badge": {"label": "Reminders", "tab": "reminders"},
        },
        {
            "id": "dashboard-controls",
            "keywords": (
                "quick access",
                "customise quick access",
                "highlight a tile",
                "tile colour",
                "quick start",
                "focused view",
                "full view",
                "due today",
                "today at a glance",
                "tools & features",
                "tools and features",
                "dashboard menu",
                "continue where i left off",
            ),
            "body": (
                "Under the greeting is the search box (Ctrl+P), "
                "then Customise and a ... menu. The ... menu is for doing: "
                "Continue (the note you opened or edited last), your two most "
                "recent skills and All skills, Tools & features (a searchable "
                "list of everything the app can do) and Commands (the command "
                "palette). Customise arranges the page: View (Full, Compact or "
                "Focused), Widgets and Edit layout, which show, hide and "
                "rearrange widgets. The Focused view folds Quick access away and "
                "its greeting card holds New note and four tiles for today: what "
                "is due today, today's meetings, the notes to file and the note "
                "you were last in; press one to go there. Customise, and the "
                "... at the right of the Quick access title, have "
                "Edit quick access: Add or arrange opens "
                "a list of every command with the ones on your dashboard "
                "checked and first. Check or uncheck as many as you like (up to "
                "eight), drag a row or press Alt with Up or Down to reorder, "
                "search to narrow it, then Done saves them all at once; a tile's "
                "menu still has Move left, Move right, Highlight and Remove. "
                "The first tile is highlighted in the accent; Highlight gives "
                "any tile the accent, one of twelve colours or No highlight. "
                "Reset highlights clears the colours (the first tile is "
                "highlighted again); Reset quick access goes back to the "
                "defaults. Quick access "
                "starts as New note, Ask your notes, Sketch, Remind me and New "
                "meeting. All of it is "
                "remembered per user. Press t then d to come back here from "
                "anywhere."
            ),
            "badge": {"label": "Dashboard", "tab": "dashboard"},
        },
        {
            "id": "hidden-features",
            "keywords": (
                "hidden feature",
                "hidden",
                "secret",
                "tips",
                "tricks",
                "tips and tricks",
                "power user",
                "easter egg",
                "things i might not know",
                "didn't know",
                "chord",
                "t then",
                "m then",
                "t chord",
                "m chord",
                "every feature",
                "all the features",
            ),
            #: The "m" chord's two tables (`TAB_JUMP_KEYS` and `CHORD_ACTIONS`,
            #: app.js) are written out letter by label, and checked against the
            #: tables, so a letter added there has to be added here.
            "body": (
                "Ctrl+K is the command palette "
                "(jump anywhere, run an action), Ctrl+P is Find anything (notes, "
                "files and actions), and ? lists every shortcut, which Settings, "
                "Keyboard shortcuts rebinds. Press t (or m) then a letter to jump: d (Dashboard), n "
                "(Notes), c (Chat), g (Graph), l (Library), i (Timeline), r "
                "(Reminders), o (OCR workspace); or to act: s (Settings), q (Quick sketch), v (Record "
                "a meeting), a (Guide), p (Popup agent), y (Tray), w (New note), f (Find anything), k (Calculator). A second t, m or Esc closes the panel. "
                "Ctrl+Shift+A opens the agent over any tab, Ctrl+Shift+H asks Atlas "
                "about the app, Ctrl+J writes at the cursor, Ctrl+Shift+E acts on "
                "selected text (so does a right-click on the selection), Ctrl+Shift+K opens the quick sketch pad, and "
                "Ctrl+Alt+R reloads the app clearing cached files. Every menu works "
                "from the keyboard: Down on a menu button opens it, the arrows move, "
                "Home and End jump, typing a few letters jumps to the row that starts "
                "with them, Enter picks, and Esc or Tab closes. Select in Notes, the Timeline and the Library acts "
                "on many items at once, the notes filter takes tag:, cat: and is: "
                "operators, the dashboard's ... menu has Tools & features, which lists everything the "
                "app can do, and each section's ? explains itself."
            ),
            "badge": {"label": "Keyboard shortcuts", "section": "shortcuts"},
        },
    ]
)
