# The design system

Everything visual in this app is built from the tokens below. This document is
the contract: **new features use these, and `tests/test_style_scale.py` fails
the build if they don't.**

## Why this exists

Reported, after a round of real use:

> *"the way spacing, alignment and margins of all the ui features in each tab
> aren't consistent and it changes each tab. I want the UI across the
> application to be very professional, consistent and clean. not to look like
> it is just a bunch of ai generated slop features joined together."*

That was accurate, and the cause was structural rather than cosmetic. Each tab
was built in its own session, reaching for whatever value looked right at the
time, and `style.css` grew past 5,000 lines with nothing shared underneath it.
Measured before any of this was fixed:

| | Before | After |
| --- | ---: | ---: |
| Distinct spacing values | 25+ | 9 |
| Distinct font sizes | 37 | 10 (+3 hero one-offs) |
| Distinct corner radii | 12 hard-coded px | 3 tiers, all derived |
| Page gutter treatments | 4 across 7 tabs | 1 |

**None of those numbers is the point on its own.** Seven values between 0.3rem
and 0.6rem all mean "a small gap"; nine font sizes between 0.74rem and 0.85rem
all mean "slightly smaller than body text". Two things that are *almost* the
same size, next to each other, is exactly what reads as unconsidered, nothing
lines up, and no value means anything because every one is slightly its own.

---

## The tokens

All defined in `:root` in `frontend/css/00-tokens-shell.css`: the first of
the eleven stylesheets (`00-tokens-shell.css` to `10-responsive.css`) that one
`style.css` was split into, so every later file's `var()` calls have it loaded
before they need it.

### Spacing: `--space-1` … `--space-9`

```
--space-1: 0.25rem    --space-4: 0.6rem     --space-7: 1.25rem
--space-2: 0.4rem     --space-5: 0.8rem     --space-8: 1.5rem
--space-3: 0.5rem     --space-6: 1rem       --space-9: 2rem
```

Use for every `margin`, `padding`, `gap`, `row-gap` and `column-gap`.

Every step is wrapped in `calc(… * var(--density))`, so the density setting
(Settings, Appearance: compact / comfortable / spacious) tightens or loosens
the **whole interface** with one multiplier. It used to be nine rules in two
places, each re-stating literal paddings for the four components somebody
remembered, `.card`, `.layout`, `.dash-hero`, `.entry-list li`: so "compact"
tightened those four and left every dialog, chip row, toolbar and settings pane
at comfortable. **A density rule that names a component is that regression
coming back**, and the lint says so.

The scale was **extracted, not invented**: the nine steps are the modes of the
distribution that was already in the file, which is why adopting it moved 311
values by no more than 0.1rem each. It is deliberately denser at the small end,
because that is where interface spacing actually lives.

### Type: `--text-xs` … `--text-display`

```
--text-xs:      0.7rem    badges, counters
--text-sm:      0.75rem   dense metadata, small caps labels
--text-base:    0.8rem    secondary UI text
--text-md:      0.85rem   the workhorse, chips, list rows, controls
--text-lg:      0.92rem   form labels, settings copy
--text-body:    1rem      prose, card titles
--text-h3:      1.15rem   panel headings
--text-h2:      1.3rem
--text-h1:      1.5rem   (was 1.7rem; INBOX 446 (5))
--text-display: 2.2rem
```

**The interface's own size is `--text-lg`** (INBOX 446 (5)): `body` sets
it, so anything without a size of its own (a tab label, an empty state, a
sidebar row, inherited prose) draws at 14.7px, not the browser's 16px
default. A note's preview in the list is `--text-lg` too. `--text-body`
stays for a document's prose and a card title, which say so explicitly.

**A size is written as its token, never as the rem it equals** (Phase 13
decision 11, Brief 57): `font-size: 0.8rem` is `var(--text-base)`. The four
commonest literals (`0.8rem` 48 uses, `0.85rem` 34, `0.92rem` 25, `0.75rem`
25) were the ramp's own values, mapped value for value (no size moved; the
plan's wording "0.75rem to --text-xs" would have shrunk them, the ramp says
0.75rem is `--text-sm`). `em` sizes inside a run of text stay relative. Lint:
`test_a_font_size_on_the_ramp_is_written_as_its_token`.

Sizes above `--text-display` exist for three single hero elements and are
allow-listed individually in the lint. **A display size is a one-off, not a step
other components may reach for**: if a fourth thing wants 2.4rem, that is a
sign it should be using `--text-display` instead.

### Corners: derived from the user's setting

```
--radius-sm:   calc(var(--radius) * 0.3)   chips, inputs, small controls
--radius-md:   calc(var(--radius) * 0.6)   buttons, inner panels
--radius-lg:   calc(var(--radius) * 0.8)   cards, dialogs
--radius-pill: 999px                       pills, round buttons
```

`--radius` is a **user preference** (Settings, Appearance, 2–16px across the
built-in themes). Before this, ~90 declarations used literal pixels, so choosing
square corners squared the cards and left every chip, popup and button rounded.
Deriving the tiers makes the whole interface respond to one setting, which is a
behaviour fix as much as a consistency one.

The multipliers are chosen so each tier lands within a pixel of the value it
replaced at the default 14px. **Never pin a tier to a constant**: the lint
checks for this, because doing so silently disconnects the slider again.

### Controls inside a rounded container

**A control inside a rounded container takes a corner that sits inside it:
fully round, or the container's corner minus its padding, and its hover fill,
pressed fill and focus ring all follow it** (INBOX 683, the owner: "the square
active goes out of the circular pill"). Outlines follow `border-radius` in
current Chromium; a box-shadow ring must use the same corner. The button corner
(`--radius-md`) is for a button on a surface, not for one inside a capsule: a
rounded square drawn in a pill is the tell.

| The container | The control's corner | Token |
| --- | --- | --- |
| A pill or a round well (`--radius-pill`): the table bar's "Copy, more, close", the board's zoom pill, the selection bar | Fully round | `--radius-in-pill` |
| A choice-control track (`--radius-choice`) padded by one `--space-1`: the timeline's week well | The track's corner minus that padding, never under the button corner | `--radius-in-choice` |
| A button-cornered strip (`--radius-md`) padded by one `--space-1`: the graph's zoom strip | The strip's corner minus that padding, never under the chip corner | `--radius-in-md` |
| A bare tab in a `.tabs-line` strip (no container; INBOX 682) | The button corner, on all four corners | `--radius-md` |

`--radius-inner` is **not** this token: it is a painted *surface's* corner
inside a card, and it is 0 below a 12px corner setting, which is what drew
"Copy | ... | X" as three rectangles in a capsule. A container that clips
(`overflow: hidden`) cuts its controls' focus rings to a line; pad it and let
it overflow instead (the graph zoom strip did). The check:
`tests/test_ui_recipes.py` (`test_a_control_in_a_rounded_container_takes_the_container_tokens`),
`scratchpad/ui-sweeps/radius682.js` (container and child corner at rest, hover
and keyboard focus, light and dark, 1440 and 390).

### The page shell: `--page-gutter`, `--page-top`, `--page-bottom`

```
--page-gutter: clamp(var(--space-3), 1.2vw, var(--space-6))   /* 16px at 1440 */
--page-top:    var(--page-gutter)
--page-bottom: var(--page-gutter)
```

All four edges are one number (INBOX 425: "there is a lot of space lost
because of these margins and floating panels"); the gutter was 2rem a side
and 2rem at the bottom before that.

Applied once, by `.tab-page`. Seven tabs previously drew four different
gutters: the side inset was 2rem in five separate rules, but the space above
the first element was 1rem on Notes and Chat, 0 on Documents, and 0.8rem on
the Dashboard, Reminders and Graph, **each on top of `.tab-page`'s own
0.8rem**, so content began 1.8rem down one tab and 0.8rem down the next.

> **The rule:** a page's own container sets its internal `gap` and nothing
> else. The distance from the window belongs to the shell.

The narrow-screen tightening happens once, in a single media query on `:root`.
Per-page media queries shrinking to different numbers is how the desktop drift
got faithfully reproduced on mobile.

### Colour

The palette is already tokenised and theme-aware, every one of these has a
light and a dark value, and the lint enforces that:

```
--ink   --muted   --border   --card   --accent   --accent-soft   --chip-bg
--accent-text
--ok / --ok-soft      --warn / --warn-soft      --error / --error-soft
```

**Words in the accent are `--accent-text`, never `--accent`** (0.3.3). The
accent is picked as a fill, and a fill colour fails as text: measured over
every palette, accent and mode, the raw accent was under 4.5:1 as a word on
228 of 348 combinations (rose on paper, 3.35:1 for a link). `--accent-text`
is the accent pulled to a readable lightness in each mode (`oklch(from ...)`
in `00-tokens-shell.css`, the accent itself where the browser lacks relative
colour), lowest 4.71:1. Links, an accent label, a count in the accent: the
token. Borders, rings, fills and `accent-color`: the accent itself.
`tests/test_accent_text.py` fails on a `color:` that reaches the raw accent,
in a stylesheet or in a CodeMirror theme object.

**Never write `var(--token, #fallback)` for a colour.** That pattern looks like
a safety net and is the opposite of one:

- If the token *doesn't* exist, the fallback is what renders, silently, in
  both themes. `var(--danger, #e2534b)` appeared in six rules and `--danger` was
  declared nowhere, so all six ignored dark mode entirely while looking
  perfectly correct in the stylesheet. The theme-aware `--error` had existed
  the whole time and is a different red in dark mode.
- If the token *does* exist, the fallback is dead code that would let a rename
  keep working while quietly showing the wrong colour.

`var(--text-muted, inherit)` was the same bug, quieter: the token was never
declared, so the text simply inherited and was never muted at all.

Fallbacks are allowed for font stacks and numeric defaults (`--mono`,
`--ui-font`, `--bg-art-opacity`) and for two tokens that legitimately fall back
to another token. Everything else is caught.

Literal colours are still correct in exactly one place: the sketch palette,
where the hex value *is* the data, and the accent presets, which are
definitions.

**A field and a track** (decided 2026-10-05, op4-1005, OPEN.md consistency
and docks). A text field's fill, `--field-inset`, is a recess; a `.seg`
track's, `--chip-bg`, is a tint. They are two tones in both themes, the field
the deeper: dark draws the field in black (0.28) and the track in white
(0.08); light had both at `rgba(31, 36, 48, 0.07)`, so a dock's search field
and the segment beside it read as one material. Light's field is 0.10 now,
the light `--border`'s weight and one step deeper than every light palette's
chip tint (0.05 to 0.08). Measured: `contrast.js` at 1440 and 390, light, the
same one finding before and after (a "Built-in" tag in Settings, Skills, at
4.27:1 at both values). Lint: `tests/test_style_scale.py`
(`test_a_field_is_deeper_than_a_track_in_both_themes`).

### Elevation: `--shadow-sm`, `--shadow-md`, `--shadow-lg`

```
--shadow-sm   resting cards, list-row hover, message bubbles
--shadow-md   floating panels, dropdowns, active/lifted tabs (= --glass-shadow)
--shadow-lg   a dragged card, a dialog's own depth, the "off the surface" tier
```

Added by the apple-design audit (ROADMAP §35L) after finding twelve
hand-written `box-shadow` values, six-plus different blur radii, opacities
from 0.05 to 0.5, one tinted family (`rgba(31, 38, 135, …)`, matching
`--glass-shadow`) and one flat-black family living side by side. Most of the
flat-black ones never adapted in dark mode the way `--glass-shadow` already
did, because they weren't built from it. All three tiers are dark-mode-aware
(`--shadow-sm`/`--shadow-lg` scale off `--shadow-intensity`, the same knob
Settings, Appearance already drives; `--shadow-md` is `--glass-shadow`,
already themed). Two literal shadows remain on purpose: the lightbox image's
(its backdrop is always near-black regardless of theme, so a themed shadow
would be wrong there) and the accent-glow on the CTA button family, which
carries the user's chosen accent colour via `color-mix()` rather than the
neutral elevation scale, a coloured glow, not a depth cue.

**What the shadow slider means** (decided 2026-10-05, op4-1005, OPEN.md
visual-c). Settings, Appearance's shadow strength runs 0 to 50% in 5% steps
and means strength from none (0%) through the look as it ships (5%, the
default) to the strongest each theme's ink usefully draws (50%), every step
moving every layer and none of them opaque before the top. Two derived
halves, each 0 to 1, carry it: `--shadow-low` (0% to the default) and
`--shadow-t` (the default to 50%); a layer is `calc(base * var(--shadow-low)
+ rise * var(--shadow-t))`, base its value at the default and base + rise at
most 1 (dark's layers reach 0.9, light's `--shadow-lg` 0.75, light's
`--shadow-sm` and `--glass-shadow` stay the slider itself). Before: dark's
layers were 7 to 11 times the slider and opaque from 9 to 14%, light's
`--shadow-lg` from 35%, and all twenty palettes' `--glass-shadow` (the
default palette's included) were literals the slider never reached, so
`--shadow-md` did not move at all. Measured (a probe at every step, light and
dark): every layer rises at every step, and 5% reads exactly what it did.
Lint: `tests/test_style_scale.py`
(`test_the_shadow_slider_reaches_every_layer_and_none_clamps`).

### Motion: `--motion-fast`, `--motion-base`, `--motion-slow`

```
--motion-fast: 0.12s   hover/press feedback, checkbox/toggle state
--motion-base: 0.16s   the default: colour, background, border, opacity
--motion-slow: 0.2s    a bigger move, panel/sidebar open, card lift
```

Same extraction method as the spacing/type scales: ten distinct transition
durations in the wild (0.08s-0.25s, one written as `120ms`) collapsed to the
three that were actually the modes of that distribution. Applied to every
`transition:` duration in `frontend/css/*.css`; `animation:` keyframe timings
(entrance/exit effects tuned to their own motion, not interactive feedback)
were deliberately left alone rather than mechanically swept, since a
keyframe's duration is part of what makes that specific effect read right,
not a value drifting for no reason.

**A menu leaves the way it came** (perfpolish, then the motion pass):
`.action-menu.hidden` fades and shrinks back to 0.96 over `--ui-exit`
(opacity, scale, and `display` as a discrete transition, so every close path,
which is one class, gets it with no JS), takes no press while it goes, and a
menu moved to the body goes home after the exit (`restoreEscapedMenuAfterExit`,
`menuExitMs` in menus.js). Interface animations off makes it instant; reduced
motion does not. `scratchpad/ui-sweeps/kebabfirst.js` samples every frame.

**The curves, and the rule that holds all of this (INBOX 399 (4)).** Three
curves beside the three durations: `--ease-out` (`cubic-bezier(0.2, 0.8, 0.2,
1)`, the default: a control that answers the pointer arrives at once and
settles), `--ease-in-out` (a thing that travels between two resting places)
and `--ease-spring` (one overshoot, for a knob or a pop, never a surface; the
switches' knob uses it). Every `transition` names a duration token and a curve
token, or `linear`; never `transition: all`; an item with no curve runs on
`ease` and fails the lint too. `tests/test_motion_tokens.py`. Measured before:
125 transitions on `ease`, eleven raw durations, four hand-written curves.

**A hover is a colour, never a `filter`** (INBOX 405). `button:hover` was
`filter: brightness(1.07)` on every button: too small to read as a state, and a
compositing layer per hover that re-rasterised the text (the chat's "Jump to
latest" pill flickered in the desktop window). A solid button goes one step
deeper, `--accent-surface-hover`, through `--button-ground` so only buttons
that kept the solid ground receive it; any other ground takes `--hover-veil` as
a `background-image` or a background. `scratchpad/ui-sweeps/f2-hover.js` forces
`:hover` on every drawn button of every tab and lists those that change
nothing: 101 of 571 with the filter gone, 0 after (the selected segment and
tab excepted, which need none).

**Not done, said plainly:** motion is a user setting (`prefers-reduced-motion`)
that only some components still honour, each with its own `@media` block,
see "What is not done yet" below. There is no gesture-driven motion anywhere
in the app yet (drag/resize move the DOM directly; nothing hands off release
velocity into a spring), so nothing here contradicts the apple-design skill's
"avoid fixed-duration transitions for anything gesture-driven", that rule
doesn't apply until something *is* gesture-driven.

**What moves, and what never does (INBOX 459 (2)).** The owner asked for
"cheap css animations to things like the horizontal pill selectors and
sidebars ... but dont over do it". Motion here says one thing: *this is the
same thing, somewhere else now*. So a selection travels, a panel arrives from
the edge it lives on, and nothing moves to decorate.

- **A selection that moves between options** slides (the owner,
  2026-10-04 and 2026-10-05: "a slight css sliding animation ... cheap but
  looks professional", "Also like the smooth slide across tabs"): one
  indicator per strip, the strip's own `::before`, placed on the chosen
  option by `glideStrip` (shell-reminders.js) through `--glide-x/y/w/h` and
  moved from where it was drawn by a `transform` animation (translate and
  scale from its top left corner) on `--ui-slow`, `--ease-in-out`; the
  label's colour changes on the same clock. **One recipe for every strip**:
  the top bar's tabs and every `.seg` as a fill, the sub-tab strips
  (`.tabs-line`) as their 2px line, the Settings sections as a fill and a
  pane's groups as their rail; a family's own corner, fill or ring is
  `--glide-radius`, `--glide-fill`, `--glide-ring`. A strip is wired the
  first time the pointer or the focus reaches it (the top bar at boot, a
  pane's groups when they are built); until then the option's own fill
  draws it. It replaced a CSS-anchored `::before` whose four insets were the
  app's one layout property in motion and which an engine without
  `anchor-scope` drew with no glide. Measured
  (`scratchpad/ui-sweeps/motion1005.js`, 1440): 167 to 211ms in motion,
  10 or 11 frames between, `transform` only, lands on the option to 0px,
  and to 0px again after a resize; with Interface animations off, 0ms and 0
  frames.
- **A sidebar folding to its rail** sets its column at once, as before; its
  contents leave toward the rail (`--motion-fast`) and arrive from it
  (`--motion-slow`) by `opacity` and `transform`, the hover-peek the same way
  after its wait, and the rail's sideways name fades in as they go. Focus
  mode's two side panels come in from their window edge (`@starting-style`,
  `opacity` and `translate`); closing is instant. Measured
  (`scratchpad/ui-sweeps/sidemotion.js`): opacity and transform only, and no
  layouts the control does not have (14 against 14 on Notes, 2 against 1 on
  Chat, per fold).
- **A page arriving** (a tab switch) fades in over `--ui-fast` (120ms, the
  motion pass of 2026-10-05; a sub-tab's panel does not, since
  `@starting-style` cannot tell a section switch from its page arriving and
  the two fades nested) by `opacity` alone, **from 0.4, never from nothing** (INBOX 580): from 0 the
  first three or four frames of every switch were the bare window, the
  flash that read as a glitch (`scratchpad/ui-sweeps/smooth1005-tabs.js`:
  13 of 14 switches had a blank frame, now 0). The page leaving does not
  fade, so two pages are never on screen at once. Measured with the fade
  from 0 over `--motion-fast` (the numbers still hold for the shape): no
  layouts of its own; 20 switches by real clicks, 305 to 321 layouts with
  the whole pass against 140 with it off (the glide's share), frame p95 33
  to 50ms either way in this sandbox, which is its CPU, not the pass. With
  glass on, a glass pixel converges smoothly through the fade and ends
  where it rests (slowed 20x: 242 to 249, no step at the end; background
  art off).
- **A heavy page's first visit** (Graph, Library, Documents, whose code is
  fetched the first time): the page's markup waits hidden under one
  `.skeleton` the size of the page (`tabPlaceholder`, navigation.js;
  `.tab-loading`), and when the code and the first draw are in (800ms at
  most) the skeleton fades as the page fades in (`.tab-revealing`,
  `--motion-base`). Loading is never shown raw.
- **A popup arriving** (Settings, the palettes, Find anything, a confirm:
  every `.modal-overlay`, `.lock-overlay` but the lock screen, and
  `#palette-overlay`): the scrim fades in over `--ui-base` and what
  stands on it rises one step (`--space-2`) from 0.985 over `--ui-slow`,
  `--ease-out`, all `@starting-style`, under `:where()` so a dialog with
  motion of its own keeps it; a sheet rises from its bottom edge
  (`--space-6`). **It leaves the same way back, faster** (the motion pass):
  `.hidden` fades the scrim and sinks the card over `--ui-exit` (100ms)
  while `display` holds (`allow-discrete`) with no pointer on it; a dialog
  removed from the page rather than hidden simply goes.
- **The opening** (INBOX 577): whatever covers the window when the app
  starts (the splash, or the lock screen once the password is in, its
  button saying "Opening…") stays up while the first tab draws, then fades
  once over `--motion-slow` over a finished page (`curtainShell`,
  shell-reminders.js; at most 1.5s). Nothing late may push that page: a
  line written after a fetch keeps its line box while empty (`:empty::before
  { content: "\a0" }`), a mark drawn by script keeps its room
  (`min-block-size`), an empty-state line waits with its list's skeletons,
  a card that gains a part after a fetch waits unseen for it (700ms at
  most) and fades in whole. `scratchpad/ui-sweeps/smooth1005-boot.js`
  (GATE=1): visible layout shift 0 at boot (0.073 with sign-in off before),
  and the companion's head never changes size by more than 2% between two
  frames after it first shows.
- **The companion arrives at its own size**: after the curtain lifts, by a
  move and a fade; an entrance never squashes or grows it (that was "the
  head goes large then small then large again"), and a keyframe
  `transform` on a part of Atlas restates that part's resting transform in
  every frame (the hello nod dropped the head's 0.76 scale for 0.9s). Its
  paced animations hold still for the 400ms a tab or Settings takes to
  arrive (`uiSettlingUntil`).
- **A menu or popover grows from what opened it** (the motion pass,
  2026-10-05; it was a `clip-path` circle): `.action-menu`, a dock's
  `<details>` menu and a help popover fade in (`ui-fade`) and scale from
  0.96 (`ui-grow`) out of the corner nearest their opener
  (`--menu-origin-x/y`; a popover's caret) over `--ui-base`; an action menu
  closes back the same way over `--ui-exit`. **The grow starts 1ms late**,
  with no backwards fill: every placement measure taken before the first
  frame (the flip, the escape to `<body>`, the cap) sees the box at full
  size, while the fade already holds it invisible, so a transform is never
  measured into a placement. A menu that escaped to `<body>` goes home on
  close after its exit (`afterMenuExit`, menus.js: moving a node cancels
  its transition).
- **The press**: every button and button chip scales to 0.97 and takes its
  ground a step deeper (the hover's step on a solid ground, the hover veil
  on any other) on `--ui-fast`, through the one `button:active` rule.
- **A focus ring eases in**: buttons and summaries carry a transparent 2px
  ring at rest, so the focus changes only `outline-color`, on `--ui-fast`
  (not under forced colours, where a transparent outline shows).
- **A hover eases**: a row or a card that changes ground or edge under the
  pointer does it over `--ui-base` (a zero-specificity rule for list rows
  and the row families without a transition of their own); a hover is a
  colour, and **no interface transition animates `box-shadow`** (the motion
  pass: a shadow changes at once; `tests/test_cheap_animations.py`).
- **A list settles in where its skeleton was**: `clearSkeletons`
  (notes-list.js), which every skeleton's owner calls, gives the list
  `.ui-settle` for that one swap; its rows fade up a step, `--ui-step`
  (30ms) apart for the first eight and together after that. **Not added:**
  a row fading in or out later. The lists re-render whole on a filter
  keystroke, so CSS cannot tell a new row from a redrawn one, and every row
  fading on every keystroke is the decoration this section rules out.
- **A toast** is one card in one stack (`toastStack`, status.js): the
  newest nearest the corner, the cards `--space-2` apart, positions measured,
  changed and played back by `translate` over `--ui-base`; an arrival rides
  in by the distance the others move, so no two cards cross. It fades in and
  leaves in place (a fade and a slight shrink over `--ui-exit`), and the
  stack closes the gap. The same words of the same kind inside 4 s are one
  card with a count, "×3", its timer restarted (`toastMerge`); an Undo
  merges only with the same Undo. Three show; the rest fold into one
  "+N more" card that opens the bell, and a folded notice is filed there.
  Reduced motion never slides the stack (`toastReduced`); the fades are the
  polish set's and follow Interface animations (the owner, 2026-10-11).
- **Never:** a width, height, margin or padding in motion; a page's own
  scroll; anything on first paint (a transition needs a before, and a strip
  or panel drawn for the first time has none); a loop.
- **Interface animations, a switch of its own** (the owner, 2026-10-05:
  "make them happen even with reduced motion but with a separate toggle in
  the appearance settings with it automatically on ... just make sure they
  are cheap"). **The decision, not to be remade:** the polish set (a press,
  a menu, popover, dialog or sheet opening and closing, a tab's indicator
  and panel, a list settling, a toast, a focus ring, a hover) plays **even
  when the system asks for reduced motion or Appearance's Reduce motion is
  on**, for as long as Settings, Appearance, Effects & accessibility,
  Interface animations is on, which it is by default. Off, every one of
  them is instant. It is `data-ui-motion="on|off"` on the root
  (theme-boot.js before first paint, `applyAppearance` after, the `ui-motion`
  key in prefs.js), and the polish reads the `--ui-*` tokens
  (00-tokens-shell.css: `--ui-fast`, `--ui-base`, `--ui-slow`, `--ui-exit`,
  `--ui-step`), which are the `--motion-*` scale when on and `0s` when off;
  the reduced-motion blankets in motion-still.css (a sheet that matches only while the OS hint or a switch is on) still the animations but
  leave transitions to the switch. **The large decorative motion keeps
  reduced motion and its own settings**: Atlas and the faces, the
  background art, the graph's simulation and the whiteboard (the blankets
  still zero their transitions under either reduced-motion switch). The
  app's mark answers both: Reduce motion or Interface animations off holds
  its final frame, and the system hint alone does not. Performance mode does not touch the switch: the
  polish is the compositor's and cheap, which is the condition it was asked
  for on. `tests/test_motion_tokens.py` holds it (no reduced-motion block
  names a polish recipe, every `/* --- motion:` section reads `--ui-*`,
  the blankets ask the switch); `scratchpad/ui-sweeps/motion1005.js`
  measures it.

The recipe row is "Motion" in the index below; `tests/test_motion_recipes.py`
holds it.

---

## Glass & materials

Every floating or resting surface in the app commits to one of two opacity
tiers, this was itself the subject of a full audit (a user-supplied
checklist's Part B) that found and fixed real drift, so the rule below is
enforced, not aspirational.

```
--card          55% opaque: a page surface, meant to be seen *through*
--modal-bg      96-98% opaque: floats over arbitrary content, must stay legible
--glass-blur    18px: the one blur radius; do not hand-pick a px value
--glass-shadow  the one popup/floating shadow (= --shadow-md)
--glass-border  the one glass-surface border colour
```

**The rule:** anything that floats *over* other content, a popup, a
dropdown menu, a folded-away options panel, a toolbar strip drawn on top of
a canvas, declares all four together: `background: var(--modal-bg)`,
`backdrop-filter: blur(var(--glass-blur)) saturate(150%)` (+ `-webkit-`
mirror), `box-shadow: var(--glass-shadow)`, `border: 1px solid
var(--glass-border)`. A page-level surface that content scrolls *inside*,
a card, a sidebar, uses `--card` instead. Mixing the two, or picking a
one-off blur radius or shadow, is the bug this section exists to prevent:
found live in `.whiteboard-floating-panel`, `.graph-trace`/`.graph-options`,
and `.timeline-band` (three different blur radii, 8px, 12px, and the
18px token, across three tabs was the most visible version of the
problem), all fixed by conforming to the rule above rather than by
inventing a third option.

### Surface tiers, and the border budget

Measured before this existed, on Settings, Tools it can use: the modal drew
a hairline, the group inside it drew a hairline, and all 54 rows inside the
group drew one more, three nested boxes, each saying "this is a thing" with
the same 1px line, so none of them said anything. Skills, Personas, Templates
and the Notes list had the same shape at two deep.

```
--surface-1  the pane: .card, .modal-card, a popover. Glass, and the only
             tier that may carry a hairline or a rim.
--surface-2  a group inside a pane (.settings-group, .entry-list li). A faint
             ink tint, no border.
--surface-3  a row inside a group, or a hover (.provider-option, a list
             inside a settings group). One step deeper.
--divider    the line *between* rows in a list (.setting-row, .extras-row).
             Lighter than --border: a separator, not an edge.
```

**The rule:** a line on the outermost surface only; everything inside it is
grouped by tone and whitespace. Inner rows keep a `1px solid transparent`
border so their geometry does not move and so `[data-contrast="on"]` can
colour the line back in (`02-chat-graph.css`). A selected row is a fill
(`--accent-soft`), never a fill plus an accent edge, the edge was the
innermost of the three lines above. `--surface-2` is tinted with ink rather
than white on purpose: a white tint (`--inner`) is invisible on the
near-white modal, which is where most groups live.

A sticky row inside a tinted group (`.tool-filter-row`) has to composite the
tint over the opaque modal colour, not paint the modal colour alone,
otherwise it shows as a lighter slab inside the group.

### Where the blur is allowed to be

Measured at 1366x768 (`scratchpad/ui-sweeps/weight.js`, INBOX 49): with
every `.card` blurred, the blurred area at rest was 32% of the viewport on
the dashboard and over 80% on the notes, chat and graph tabs, a full-screen
filter pass per scroll on an integrated GPU, and all it blurred was the
page art, which is already a soft gradient. So a content panel (`.card`,
`.dash-hero`, `.sidebar-panel`, the status bar) keeps the fill, the border
and the rim and has **no `backdrop-filter`**. Blur belongs where something
scrolls under a surface or where the surface floats over content: the top
bar, the sticky sub-tab strips, `.card.glass`, the dialogs, popovers,
docks, the graph's zoom pill, `.scroll-top`. With the animated background
on, the cards frost it again (`:root[data-bg-art="on"] .card`): that is
the one place a card blur shows something, and the owner asked for it. The gate, kept by
`tests/test_perf_mode.py` and the sweep: under 10% of the viewport blurred
at rest on every tab (measured 6 to 10% after). **A dialog the size of the
window whose own pane scrolls blurs nothing** (Settings): a blur is redrawn
on every frame anything inside its surface moves, and Settings' overlay and
card were two window-sized passes, 83 to 100ms a scrolled frame with glass
on against 16.7 without (`scratchpad/ui-sweeps/scrolljump.js`); the overlay
keeps its dim and the card takes `--modal-bg-opaque`.

**Performance mode** (Settings, Effects & accessibility; the `perf`
preference, `auto | on | off`) takes the rest off: `data-glass="off"`,
`data-motion="reduced"` and the graph worker resting twice as long between
ticks, without rewriting the person's own glass and motion choices. "Auto"
turns it on for a machine reporting 2 cores or 4 GB or fewer, or an OS
`prefers-reduced-transparency` setting, and says so once in a toast.
`theme-boot.js` resolves the same rule before first paint.

### Turning it off

`:root[data-glass="off"]` is a standing user preference (Settings →
Appearance), not a special case to special-case around. It swaps `--card`
to `--modal-bg`'s opaque value and zeroes `backdrop-filter` on an explicit
selector list, currently 35+ selectors covering every popup, toolbar and
floating panel named above. **Adding a new glass surface means adding it to
that list too**: a panel missing from it stays glassy even with the
setting switched off, which is how three of the Part B violations were
found (the fix and the fallback drifted independently because they lived in
different rules).

### Palettes

Eight curated palettes, each with an explicit light and dark pair,
`:root[data-palette="X"]` / `:root[data-palette="X"][data-mode="dark"]`:
**Aurora** (default, no attribute needed), **Parchment**, **Sage**,
**Ocean**, **Lagoon**, **Ember**, **Plum**, **Carbon**. Carbon is the
"quiet, non-glassy" option some users want, it does not override
`--glass-opacity`/`--glass-blur` itself (it is still built from the same
glass system as the other seven), so reaching that quiet, flat look is
**Carbon palette + the Glass-off toggle together**, not a hard-coded
exception baked into one palette. Composing two orthogonal settings this
way is deliberate: a palette-specific override would be a second, competing
mechanism for the same effect the toggle already provides everywhere else.

---

## The recipe index: use these, nothing else

The owner, after a run of "the menu is crushed", "the panel clips", "the
buttons feel separate": every one of those came from a surface built by
hand instead of from the recipe the rest of the app uses. A new piece of
UI starts here. If the need is not in this table, the recipe is added to
this table and its lint in the same commit as the feature, never after.

| You need | Use | Guarded by |
| --- | --- | --- |
| A field that grows with what is typed, above an action foot (Save, Send, Apply, Done: INBOX 1357, "fix the class": Save went off the screen after 18 to 30 lines) | **Cap the field, pin the foot.** The field scrolls inside `max-height: min(22rem, 45vh)` (no token: the custom-property count only falls), one grouped rule in library-lazy.css for every note box in a `.note-composer`, `.answer-editor textarea`, `.msg-edit textarea` and `.wb-comments-box`; a plain `autogrow` textarea is capped by `autoGrow` (35vh, 480px); the caret stays in view because the editor (CodeMirror) or the textarea scrolls to it inside the cap. The foot is `position: sticky; bottom: 0` on the card's ground (`.note-edit-foot`, `#capture .capture-commit-row`, the graph popups' save row), so a tall header above the field cannot push it out either. A fixed-rows field (a dialog's `rows="4"`) needs neither. A per-id cap (`#capture ...`) is the case-fix this replaced. Measure by typing 60 lines at 1440x900 and 390x844 and reading the foot's `getBoundingClientRect().bottom` against the window | `tests/test_ui_recipes.py` (`test_a_growing_field_has_one_cap_and_every_composer_uses_it`, `test_every_note_editor_says_how_it_is_bounded` places every `NOTE_SURFACES` id, `test_a_textarea_sized_from_its_text_is_capped` places every `.rows = Math.` file, `test_the_foot_under_a_growing_field_is_pinned_to_the_scroll`) |
| A share of a whole shown as one bar (where the disk went: the notebook, files, pictures, backups, optional features) | `.storage-bar` (`role="img"`, its `aria-label` the legend's words) holding one `.storage-seg[data-kind]` per kind, each `flex-grow` its bytes set through the CSSOM (the CSP refuses a style attribute) and a `min-width` so a sliver shows; under it `.storage-legend`, an `li` per kind with a `.storage-swatch` and the size in words, and a `Together` total. One hue in five weights, so no kind borrows a status colour and the bar is never read by colour alone. Its styles are `settings-data-lazy.css`, loaded by `renderStorageBreakdown`, never the boot sheet | `tests/test_storage_footprint.py` (`test_the_storage_bar_is_one_recipe`), `scratchpad/ui-sweeps/storagebar.js` |
| A dialog of choices that each make something (a template, a starting shape) | the choices as quiet rows (`button.ghost.doc-template-choice`, `role="radio"` in a `role="radiogroup"` list: name over a one-line hint) in a `.doc-template-body` grid beside a preview column that shows **what the chosen row would create**, rendered by the same function that creates it (`showDocTemplatePreview` through `docTemplateFill` and `renderMarkdown`), inert and `aria-hidden` because every row already says what it is; the preview is clipped with a fade, never a second scroller, and left out below 44rem. **Choosing is not making** (INBOX 410): a click chooses a row, drawn from `aria-checked` on `--accent-soft` with the name in `--accent` and a check glyph (never the fill alone; the pointer's row is the ghost tint), and only the dialog's one filled button (Use this template, after Cancel), Enter on the list or a double click makes it; the arrows walk the rows with a roving tab stop, the first row is chosen on open so one Enter still works, and the preview follows the choice rather than the pointer. The Capture box's note templates are the same dialog (`#note-template-dialog`, `openNoteTemplateDialog` in app.js), its preview the text `noteTemplateFill` would write | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/doctplpreview.js`, `scratchpad/ui-sweeps/templatepick.js`, `tests/test_note_template_picker.py`, `scratchpad/ui-sweeps/notetemplatepick.js` |
| A row elsewhere that names a control (Tools and features, the palette, Find anything's actions, a deep link) | the row declares `tab`, `reveal` or `act`, never a closure; a `reveal` names one entry in `REVEAL_TARGETS` (settings-panes.js), which `revealFeature` opens (tab, lazy bundle, the menu, panel or dialog the control is in) and rings with `flashRevealed` (`.feature-reveal`, the same ring as `.flash-target.flash`); a feature the notebook cannot show yet rings the control that makes one (`fallback`), never nothing | `tests/test_catalogue_reveal.py`, `scratchpad/ui-sweeps/deeplinks.js` |
| A second-level tab strip (Notes: Your notes, Capture, Writing room, Ask, Questions; Library: All to Contents; the document sidebar's Documents and Outline; INBOX 522) | `.tabs-line` on a `role="tablist"` (never `.seg`, never in a card): words on the page, a hairline under the strip (an inset shadow, so a scrolling strip clips it with its own padding box), a 2px `--accent-text` line under the chosen tab (`::after`, a `transform`, so no weight change and no neighbour moves), quiet hover a grey 2px underline and ink (no box, Phase 12), one height `max(--control-h-dense, --target-min)`, one `--space-1` gap, one `--space-5` padding, **no icons** (aria carries the meaning; the strips were icon on Notes and bare on Library). A sticky strip is bare at rest and takes the card's glass only under `[data-scrolled="1"]`. **The top bar keeps its pills and `.tab-glide`**: the frame is a well, the level under it is text, so two levels never read as one. The top bar's well hugs its tabs in every layout (`#tab-bar` never has a flex grow; centring is auto margins) The documents sidebar's strip, under a 14rem content box, sits under the collapse toggle with `--space-2` side room per tab (a container query, FE-19). | `tests/test_ui_recipes.py` (`test_every_second_level_strip_is_a_tabs_line`, `test_a_tabs_line_is_never_boxed_again`, `test_the_top_bar_well_never_grows_to_fill_the_gap`), `scratchpad/ui-sweeps/subtabsdepth2.js subtabs`, `subtabsdepth2.js subtabs2`, `tabstretch2.js` |
| A sentence an answer says from a note (an answer composed from the notes, in Ask and Chat; CHAT_PLAN decision 33) | the grounding row's `said` ("quoted", or "shifted" for a sentence said back to its writer with `original` kept), drawn by `markSaidSentences` (ask-compose.js) as `.said` / `.said-shifted` (ask-compose-lazy.css, loaded with it): a 2px inset rule and the muted ink, the note's own words as the hover text of a shifted one. **Never quotation marks added to the text**: they are not the note's, and they broke grounding when the Gemini branch added them | `tests/test_realise_ui.py` |
| A connection with the sentence it is said in (a document's Backlinks and Unlinked mentions; a note's Connections column and sheet, GRAPH_PLAN KG1) | `docBacklinkContext(row)` (menus.js): the server's `context` with `hit_start` and `hit_end` marked by a `<mark>` on the found-text recipe, two lines then an ellipsis (`.doc-backlink-context`), under its `.connection-row` or `.doc-backlink-title`; an action goes under it in `.doc-backlink-foot` as a `smallButton` (`.doc-backlink-action`); a write sends the offsets to the server, which refuses a span that moved (409) rather than guessing | `tests/test_note_backlinks_kg1.py`, `tests/test_doc_backlinks.py`, `scratchpad/ui-sweeps/kg1rail.js`, `docbacklinks.js` |
| Suggestions a person decides one by one (links to add, tensions, names to merge, link types: GRAPH_PLAN KG9) | **One sheet, never a panel per kind**: `openSuggestionsInbox(kind)` (suggestions-inbox.js, lazy) on `openSheet` with the dialog head and its '?', the kinds as one `<select id="inbox-kind">` (four, worded and counted: INBOX 670, never a `.seg`), each row carrying its count, "Links (3)", the panes following its value; under it one line of description and the kind's rows. **Links** (INBOX 1329): one bar over the list, the one bulk button (Link all above 70%), a `kebabMenu` of the Atlas passes (Suggest reasons, Explain your existing links) and the job line cut to its line; each row (`.link-suggestion`) a grid of the two note names (one line each, ellipsis, whole in the title; stacked below 600), one facts line (the score bar, then the reasons cut to the line, each percentage in its title), and one actions cell centred on the row (Add a reason quiet in the muted ink, Link the one edged button, a quiet X; their own line below 600), the reason field under all of it when asked for. The other kinds (`.inbox-row`: a title, the sentence via `docBacklinkContext` when there is one, the reasons each with its percentage (`.link-suggestion-why`), then a foot of a confidence chip, the one accept as a `smallButton` and a dismiss X). A decided row leaves, the count drops and the focus moves to the next row; an accept or a dismissal is a correction (`/learned/corrections` or the kind's own route), never browser state. A new kind of suggestion is a tab here. **A thing's own page** (an entity, `openEntityPage` in entity-page.js) is the same sheet: the name as the title, its facts as the `sub` line, a `kebabMenu` of its edits before the close, then `.entity-section`s under quiet headings, mentions as `.inbox-row`s with the sentence marked | `tests/test_suggestions_inbox_kg9.py`, `tests/test_ui_recipes.py` (`test_a_suggested_link_is_two_names_a_facts_line_and_one_action_cell`), `tests/test_entities_kg5.py`, `scratchpad/ui-sweeps/kg9inbox.js`, `kg5entity.js` |
| Changes a rule proposes in bulk, ticked and applied together (Tidy's reviews: weak links, stray tags, notes without a category, duplicates; INBOX 691) | **The suggestions inbox's sheet with the Attach picker's rows**: `openTidySheet(review)` (tidy.js, lazy) on `openSheet` with the dialog head and its '?', the reviews as an overview of rows (`button.note-picker-row.tidy-overview-row`: glyph, name, one `finds` line, count or a muted "Nothing to tidy", the empty ones last; pressing one opens the review with a back button, INBOX 718; never a dropdown, so every issue is in view), a review's one line of description naming what its button changes (the button's words are plain verbs, `TIDY_APPLY` in tidy.js, and the description says them), a tool row (the review's level as a `<select>`, its Apply automatically switch on a bare `label.setting-check.tidy-auto` with no fill in any state, one door to the tool it belongs with), then the rows as `label.note-picker-row` with the real checkbox visually hidden: the name, a muted line saying why it is listed, and a third line in `--accent-text` saying what Apply would do. A row the rule found but cannot change is listed (`.is-off`, not tickable) so the count stays honest. The foot: the ticked count, All and None, then **the one filled button, worded with the verb and the number** ("Remove 3 links"). Every apply is one Undo (toast, Ctrl+Z, and the sheet's Recent runs); the server recomputes the rows rather than trusting the ids. The entry point is a glyph in the dock's icon run with its count on the corner (`.tab-badge` in the accent) | `tests/test_tidy.py`, `tests/test_tidy_ui.py`, `scratchpad/ui-sweeps/tidy691.js` |
| A card about a group drawn on a canvas (a graph topic, KG6) | a panel in the graph overlay's column on its shared shell (`.graph-overlay .graph-topic` beside `.graph-trace-result`, the glass rule in 08-consistency.css), right-aligned at `min(24rem, 100%)`: a head grid of a colour dot, the name and the icon tools (rename, close) on one row with the quiet count as a muted line under the name (the count never shares the row: it wrapped as soon as the rename field took the name's room), the rename field in the name's cell at the buttons' height with Save and Cancel icon buttons where the tools were (their mousedown kept off the field so Cancel is not a blur); one muted line of facts; the answer with `aria-live`; a model step behind its own `smallButton` with a Stop while it runs (an `AbortController`), never on open. Opened from the group's legend entry, closed by the X or by leaving the mode that drew it | `tests/test_topic_summary_kg6.py`, `scratchpad/ui-sweeps/kg6summary.js` |
| A card about one dot on a canvas (a graph note's hover card; INBOX 1300 C11, "hover over ... graph nodes and see their values and dates") | **The hover card**, `gcHoverCardFrame` (graph-canvas.js) once a frame: `#graph-hovercard.graph-hovercard`, `role="tooltip"`, the canvas `aria-describedby` it while shown; for the note under the pointer, else the one the arrow keys are on; beside the dot (flipped and clamped inside the map), hidden while a drag or pan moves the map and while the note's popup is open. What it says is `gcHoverCardFacts` (pure, its clock passed in): the title over a colour dot, the category, then a `dl` grid of Created, Edited (a person's last edit, `edited_at`; left out until there is one), Links, Views, Words, the note's properties under a hairline, the tags, the closest matches, and a muted hint line. Opaque `--modal-bg-opaque` (words over the map never read through; not glass), `--radius-md`, `--shadow-md`, `--text-sm`, no pointer. **Never the canvas's native `title`** for a note on the tab (a pane keeps it). The click still opens the popup, whose info line carries the same dates | `tests/test_graph_hover_card.py`, `tests/test_ui_recipes.py` (`test_a_dot_on_the_graph_answers_with_its_hover_card`), `d2/probe-hover.js` (session scratchpad) |
| A verdict on a sentence the app said (Confirm / Not right on a pattern; INBOX 782, the owner: "redesign the confirm and not right buttons ... and any other similar instances") | **One compact pair on the sentence's own row**: `insightLine(insight, text, onDone)` (status.js) draws the words (`.insight-text`) and `.insight-verdicts` at the row's end, two quiet `.insight-verdict` buttons (a check and a cross with their words; no edge, no fill at rest, the veil on hover), wrapping under the words on a narrow screen. Chat and Tidy's Patterns call `insightLine`, and a cited line's peek calls it with its own `send` (`citationVerdictRow`, CHAT_PLAN B31 and B32: Not right is Wrong fact, Confirm is Pin as true, one row above the peek's foot); the dashboard's ⋯ takes the same two `INSIGHT_VERDICT_ITEMS`. Never two full-size bordered buttons under the sentence, never a second wording of the pair | `tests/test_ui_recipes.py` (`test_an_insights_verdicts_are_one_compact_pair_on_the_sentences_row`) |
| A suggestion a person does not want (a Tidy row; INBOX 783, "how do I delete a suggestion??") | **Dismiss for good**: a quiet cross (`button.tidy-dismiss`) beside the row's label, not inside it, that asks the server to remember (`POST /tidy/{key}/dismiss`, kept in the `tidy_dismissed` preference per review) so the row is not listed, counted or applied again; the toast's Undo is `.../undismiss`. Quiet at rest, full on the row's hover and focus, always full under a finger | `tests/test_tidy.py`, `tests/test_tidy_ui.py` |
| What a note or document is joined to (the Connections sheet and the Notes column; INBOX 784, "redesign Connections ... as a list recipe") | **One list recipe**, `connectionRowEl` (menus.js): a glyph, the title and a muted subline (the link's kind, the category or day, the reason) in one quiet `button.connection-row` with the veil on hover and no edge per row; a section head is a small caps label with its count at the end (`.connection-heading`, `.connection-count`); when more than one kind is present the tally is a row of `.chip`s at the top (`.connection-stats`). The sheet's head carries **Open in the sidebar** (`#connections-dock`, a note on a window wide enough for the column), which docks the same answer as the Notes column (`dockConnectionsInRail`) | `tests/test_connection_row_cues.py`, `tests/test_notes_rail.py` |
| A card about a group drawn on a canvas (a graph topic, KG6) | a panel in the graph overlay's column on its shared shell (`.graph-overlay .graph-topic` beside `.graph-trace-result`, the glass rule in 08-consistency.css), right-aligned at `min(24rem, 100%)`: a head of a colour dot, the name, a quiet count and an icon X; one muted line of facts; the answer with `aria-live`; a model step behind its own `smallButton` with a Stop while it runs (an `AbortController`), never on open. Opened from the group's legend entry, closed by the X or by leaving the mode that drew it | `tests/test_topic_summary_kg6.py`, `scratchpad/ui-sweeps/kg6summary.js` |
| A named region on the graph canvas (a topic, GRAPH_PLAN KG6) | `gcDrawTopicHulls` (graph-canvas.js): a convex hull of the region's dots padded by radius plus 10, dashed 1.5px at 0.45 and filled at 0.06 in the region's colour, under the links; its name in `--ink` on a `--card` plate at 0.88 edged in the colour (never the colour as text: a light hue is under 3:1), above the hull's top point and clamped to its width; full tab only, behind a colour rule rather than a switch | `tests/test_topics_kg6.py`, `scratchpad/ui-sweeps/kg6topics.js` |
| A short list you check, put in order and save once (Quick access's manager, `quickAccessManage` in quick-access.js; INBOX 524) | The Attach picker's rows (`note-picker-row`, `note-picker-check`, the real checkbox visually hidden) in two groups inside one `space-dialog`: **what is on is checked and first, in its order**, the rest below, a count in each heading. A tick changes a draft; **nothing is saved until Done** (Cancel, X, Escape and the backdrop keep what was there), and a cap refuses with a message rather than a disabled row. The search narrows both groups and stays. Order by **drag, Alt+Up and Alt+Down on a row, and two small move buttons** (the single-pointer alternative to a drag, WCAG 2.5.7; always shown under `(hover: none)`); the list is one tab stop that the arrows walk and Enter is Done. The pure helpers (`quickAccessMoved`, `quickAccessReslotted`) are tested in node | `tests/test_quick_access.py`, `scratchpad/ui-sweeps/quickmanage.js`, `quickdrag.js` |
| A tab or sub-tab's control bar | `.dock` with `.dock-identity`, `.dock-find`, `.dock-arrange` (both `.dock-group`s), `.dock-actions`, in that order; seven controls at most, one filled. **Past seven the arrange zone folds into the ⋯** ("Sort and view") at every width, as it does below 1100 (`foldDockArrange`, `DOCK_FOLD_PAST`, phone-shell.js). **The grammar** (INBOX 621, the owner: the bars "dont feel professional or modern and more demo/vibe coded"): the title is the page head, the zone's `h2` with **no divider after it**; a count beside it is quiet muted text (`.dock-chip`: no edge, no fill, tabular figures), never a pill; search is `div.search-field.dock-search` holding a `.search-field-icon` magnifier and the `input.search-field-input`, a subtle `--field-inset` fill with **no edge at rest** and the accent edge and ring on focus, and a sort `<select>` beside it takes the same quiet inset; every segmented control is the one `.seg` well (one fill, one chosen state); the actions zone is its worded ghosts (weight 500), then the icon-only ghosts as **one trailing run** (32px, 44 under touch; refresh, help, more), then **the one filled action, last**. No hairline anywhere in the bar: zones are parted by `--space-6`, twice the gap inside one (`--space-4` below 600, where they stack) | `tests/test_dock_grammar.py` (zone order, one filled and last, the icon run, a wrapped search with its icon, no zone hairline, a quiet count, an edgeless field), `scratchpad/ui-sweeps/dockgrammar621.js` (every dock at 1440 and 390, light and dark: title divider, hairlines, count pill, field edge and icon, icon size and run, filled last, one segment style), `scratchpad/ui-sweeps/docks.js` |
| A palette of many tools (a drawing bar, where every control is a tool rather than one of seven choices) | `.wb-tool-section` around one `.wb-tool-section-label` and one `.wb-tool-section-row`, all of them in one bar; the group boundary is the hairline `.wb-tool-section + .wb-tool-section` draws in `--divider`, and nothing sits in the bar outside a section. Used by the whiteboard rail. **The sketch pad's bar is a `.dock` instead** (INBOX 839, the owner: "improve and modernise/professionalise and make consistent the design of the quick sketch panel"): `data-dock-name="sketch"`, one `.dock-arrange` run of tools on a single row of `--control-h-lg` controls with every name in a tooltip and no group labels, the ink as one chip (`#sketch-ink-chip`, a dot in the colour in use) that opens its seven swatches (`#sketch-palette`, closing on a pick, Escape and a press elsewhere), and undo, redo, clear, picture and paper as `.dock-actions`, on a borderless `--field-inset` ground. Measured at 1440: one row, all 32px, no labels (21 controls at 28px and five labels before); at 390: 162px tall in three rows (326px in five before) (`scratchpad/ui-sweeps/sketch620.js`) | `tests/test_ui_recipes.py` |
| Text typed in place on the board (a text box, a topic, a shape's text) | `wbBeginTextEdit(el)` makes the element a plain-text editor and focuses it, `wbEditedText(el)` reads it back with its line breaks, `wbEndTextEdit(el)` (or removing the element) ends it; Enter and Escape finish, Shift+Enter breaks the line, the editor's own keydown stops propagation so the board's keys never act on what is typed. A shape's text is an SVG `<text class="sketch-label">` in the shape's own group (`wbPaintShapeLabel`), typed through `.wb-shape-label-editor` in the card layer (WHITEBOARD_PLAN decision 12); a connector's label (`.wb-link-label`, decision 13) is typed through the same editor, `wbOpenSketchLabelEditor`, one line; a frame's title (`.wb-frame-title`, decision 14) is typed through `wbBeginTextEdit` too, Enter keeps, Escape restores | `tests/test_ui_recipes.py` (`test_board_text_is_made_editable_in_one_place`), `scratchpad/ui-sweeps/wbshapetext.js` |
| A region of the board that holds what is in it (a frame) | an object of kind `frame` (`wbCreateFrame`), its title in `content`, drawn as `.wb-object-frame`: an edge in the muted ink and a `.wb-frame-title` above it, no fill, so the drawing layer under the card layer shows through; its inside is `pointer-events: none`, the title and the handles take the pointer. Stacked below everything (`wbFrameZ`); a drag carries what lies wholly inside it (`wbFrameDragOrigin` into the bulk mover), a frame inside it included, Ctrl moves it alone; its menu's Export this frame… selects it and everything inside (`wbExportFrame`) and opens the export dialog on Selection; nothing is clipped (WHITEBOARD_PLAN decision 18); its rotate grip turns what lies wholly inside it by the same angle about the frame's centre (`wbFrameTurnOrigin`, one Undo step), Ctrl turns the frame alone (WHITEBOARD_PLAN decision 42); a double-click on that grip stands the frame and its contents upright (`wbResetRotation`); no style or order controls on the bar; the export draws it first. The F key, the rail's Add section and the Insert menu, board only (`WB_BOARD_ONLY_TOOLS`) | `tests/test_ui_recipes.py` (`test_a_frame_is_one_kind_reached_three_ways`), `scratchpad/ui-sweeps/wbframes.js` |
| An item held in place on the board (lock) | the class `.wb-locked` (painted from state by `wbPaintLocks` after every render), one rule: `#whiteboard-container .wb-locked, .wb-locked *` take no pointer, so no gesture reaches it and none needs its own guard; what selects without the pointer asks `wbIsLocked` (Select all, marquee, lasso, a group's click, a frame's drag). Lock is the item menu's Lock and Ctrl+Shift+L; Unlock is the board's right-click menu (the press goes through the item to it) and Ctrl+Shift+L with nothing selected. A card keeps the flag in its `locked` column, a sketch and an object in their data. Not on maps (WHITEBOARD_PLAN decision 15) | `tests/test_ui_recipes.py` (`test_a_locked_item_is_out_of_reach_in_one_way`), `scratchpad/ui-sweeps/wblock.js` |
| Deleting by dragging onto a target (a card, a box, a shape or a map topic, or the selection it belongs to; INBOX 660) | **One target for the three item drags**: `wbBeginGesture(restore, true)` marks the drag a move; past 6px of travel `.wb-trash` (built once by `wbTrashTarget`: a `.whiteboard-floating-panel` pill, so on the glass-off list, `aria-hidden`, no pointer of its own) shows at the canvas's foot, centred, above the edge auto-pan's 3.5rem band; the pointer within 8px of it sets the gesture's `overTrash`, turns it to `--error` with a ring and "Release to delete" (said in the board's live region) and holds the edge pan still. Each drag's end asks `wbTrashTake` first, while it still holds its origin: a hit puts the move back (`restore`), marks the gesture cancelled so nothing is saved, and `wbTrashDelete` deletes what was carried through the selection's own deletes inside one `wbRecordGesture` (a topic takes its branch), with `toastAction(..., "Undo")`. Escape and a drop elsewhere are the gesture's own; keyboard people keep Delete. Styles in library-lazy.css | `tests/test_ui_recipes.py` (`test_drag_to_delete_is_one_target_on_the_three_drags`), `scratchpad/ui-sweeps/wbtrash660.js` |
| A region or a note drawn round topics on a map (a boundary, a summary) | `wbRenderMapStructure` (whiteboard-map.js), after `wbRenderMapEdges` on every render and on the selection bar's frame: `.wb-map-boundaries` (first in the zoom group, under the lines) holds one `.wb-map-boundary` path per topic carrying `data.boundary` (rounded, dashed, cloud) round the box of its showing branch padded by 12, its label above the top edge; `.wb-map-summaries` (after the lines) holds a `.wb-map-summary-brace` beyond the run's branches on the side away from the parent and the words past its tip. Colour is the branch colour as `--wb-boundary`; words in the line label's recipe; no pointer. Made and changed from the topic menu's Branch group (and a multi-selection's Summarise these topics…) through `wbMapSetStructure`, the topic's one undo step; in the image export as drawn (MINDMAP_PLAN decisions 19, 20) | `tests/test_ui_recipes.py` (`test_a_maps_boundaries_and_summaries_are_drawn_in_one_pass`), `scratchpad/ui-sweeps/mapstructure.js` |
| A marker on a map topic (a priority, progress, a flag, an icon) | `wbMapPaintMarkers` (whiteboard-map.js), from the paint pass (`wbPaintMapNodeStyle`), into the topic's one `.wb-map-markers` row before its icon and label: a `.wb-map-mark-priority` badge (the number on `--accent`, 1 on `--error`, 2 on `--warn`), a `.wb-map-mark-progress` pie (a conic fill to `--progress`), the flag in `--error`, then up to six glyphs from `WB_MAP_MARKER_ICONS`, a fixed set from the vendored Phosphor font, **never emoji**; the row is one `role="img"` whose label says them all. Set in one help popover (`wbMapOpenMarkers`: `.seg` rows for Priority, Progress and Flag, a grid of pressed-state icon buttons) through `wbMapSetNodeStyle`, one undo step each; View, Filter by marker (`wbMapChooseMarkerFilter`) dims the rest (`.wb-map-filtered-out`) and says so in the focus bar's shell (`#wb-map-filter`). Content: a look reset keeps them; OPML and FreeMind carry them as `_priority`, `_progress`, `_flag`, `_markers` (MINDMAP_PLAN decision 34) | `tests/test_ui_recipes.py` (`test_a_topics_markers_are_one_row_from_one_icon_set`), `scratchpad/ui-sweeps/mmd2-1005-markers.js` |
| A sticky note against a text box on a board | A sticky is `data.sticky` (or the legacy yellow with the `#e8d56a` edge, `wbIsSticky`): `.wb-sticky`, paper in `bg` (`--wb-paper`), no drawn edge, `--wb-sticky-shadow`, a folded corner (`::after`, the tip in `--wb-board-bg`). A text box has no fill, no blur, no lift and a faint dashed edge. A sticky's bar starts with the `paper` group, one `.wb-paper-trigger` dropdown button (current paper as a dot, `aria-haspopup`) opening the colour popover with a `swatchPicker` of `WB_STICKY_PAPERS`; a text box's bar has none | `scratchpad/ui-sweeps/wbstickylook.js` |
| A colour on a board (the colour well: a fill, a border, a line, text, the draw colour) | an `input[type="color"].wb-color-picker` whose click opens one `.action-menu.wb-colour-menu` (`wbOpenColourMenu`, whiteboard-format.js), never the browser's dialog first: a head naming the field; for a pair (`WB_COLOUR_PAIRS`: a shape's fill and border, a text box's fill and edge, the tool's fill and draw colour) a `.tabs-line.popup-kinds` tab strip of Fill and Border with a dot of each (the one being set `aria-selected`), Same as and Swap as one `wbRecordGesture` each; Recent (the last eight picks, per device, `localStorage` in try/catch) over the board palette, both from `swatchPicker`; Pick from the board (the eyedropper: the next press takes a colour from a field, a swatch, a shape, a line or a text box and never reaches what is under it, with a Take a shape's border box shown while it is on, and Alt for the same) and More colours (`showPicker`). On the bar and in Format the fill sits before the border and both are labelled; a fill that is off is dimmed (`.wb-colour-off`), never disabled. Before: setting a border to its fill took the browser dialog and a copied hex, and the owner could not; after: two clicks (the border, Same as fill) | `tests/test_wb_colour.py`, `scratchpad/ui-sweeps/wbcolour-well.js` |
| Some of a text box's or sticky's words set apart (a size, a font, a text colour, a highlight; INBOX 1403) | **A run**, `{{size=24 font=serif ink=red hl=yellow|words}}`, written in the text itself (`MD_RUN` in documents.js, one alternative of `INLINE_MD` in notes-list.js, so save, search, undo, export and the AI read it with no new column): values are checked on the way out (`mdRunParse`: a size 8 to 200, a face from `MD_RUN_FONTS`, the eight `MD_COLOURS`), drawn by `mdRunNode` with classes (`.text-ink-*`, `mark.text-highlight-*`, the colour on a span inside the mark) and CSSOM for size and face, never a `style` attribute; the control is the selection bar's **Text style** (`Aa`, `[data-board-run]`, text boxes and stickies only, `wbSelectionBarFit`), which opens the colour popover's own element (`wbOpenRunMenu`: Size and Font as `.wb-colour-actions` button rows, Text colour and Highlight as `swatchPicker`s, and Text settings for the whole box, which opens the Format panel's Text tab), every press `mousedown`-prevented so the box keeps its edit, and each pick one `wbRunApply` through `wbSpliceEditable` (the browser's Undo holds it); the export writes a run as its own `<tspan>` (`wbSvgRunLines`) | `tests/test_wb_runs_1027.py`, `scratchpad/ui-sweeps/wb1027-runs.js` |
| A comment thread on a board item or a map topic | `comments` (`{id, text, at}`) in the item's own data, a card's in its `comments` column; `wbPaintCommentMarks` draws one `.wb-comment-pin` per commented item in `#wb-comment-marks` (in the card layer, above every item, a zero-size pin at the top-right corner scaled back to screen size by `WB_INV_ZOOM_GRIPS`) holding the accent `.wb-comment-mark` pill with the count, after every render and on the selection bar's frame so it follows a drag. The mark, the item menu's Comment… and a topic's Topic group open `wbOpenComments` in the help popover's shell (`.help-popover.wb-comments`, `placeHelpPopover`): the thread oldest first, each reply one step in under what it answers (`reply_to`), each row's words through `renderMarkdown` (a link alone on a line is the `.link-card`, `[[a note]]` the note chip), its time ("edited" once `edited` is set) and quiet icon buttons Reply, Edit (in place, Enter keeps), Resolve (`resolved`; folded into one "N resolved" disclosure, the mark a tick when nothing is open) and Delete (with its replies); one box with Attach (`pickLibraryItemDialog`) and the editor's "/" and "[[" menu (context "comment", `EDITOR_BOARD_ROWS`), Enter posts. Every change through `wbSetComments`, one undo step. Hidden while presenting; not exported (WHITEBOARD_PLAN decision 17) | `tests/test_ui_recipes.py` (`test_a_comment_thread_is_one_popover_reached_three_ways`), `scratchpad/ui-sweeps/wbcomments.js` |
| Suggestions offered under a map topic to take or drop (Branches from my notes, Expand from my notes; MINDMAP_PLAN, ghost topics) | **Ghost topics**, `wbMapBranchPicker` (whiteboard-map.js): `.wb-ghosts` (a `role="group"` fixed on `<body>` at the topic's screen box, no blur, its layer 22 set from the script) holding one `.wb-ghost` (a toggle button, `aria-pressed`, faded, dashed) per suggestion. Tab takes the one in focus (`.is-taken` firms it up), Shift+Tab lets go, Enter adds the taken ones (the one in focus when none), Escape drops all, a click toggles; a wheel, resize or press outside drops them. Resolves with the taken rows into `wbMapAddChosenBranches`, one Undo step. Styled in `library-lazy.css`, out of the boot budget | `tests/test_ui_recipes.py` (`test_ghost_topics_are_one_lazy_layer_with_four_keys`) |
| Presenting a board's frames, or a map's branches | View, Present frames (`data-wb-fn="present"`, board only) or, on a map, Present branches (the same `data-wb-fn` on a `data-wb-surface="map"` row; its steps from `wbMapPresentSteps`: the whole map, then each trunk's branches; MINDMAP_PLAN decision 21): `wbStartPresenting` puts the board full screen and the host class `.wb-presenting` hides every control but `#wb-present-bar` (a `.whiteboard-floating-panel` centred at the foot: Previous, the count as a polite live region, Next, End) and takes the pointer off both drawing layers. Frames in reading order (`wbFramesInOrder`), each fitted above the bar's own strip; the keys are taken on the window in the capture phase (arrows, Space, Page Up and Down, Home, End, Escape), so no board key acts; Escape puts the camera, the window and the focus back (WHITEBOARD_PLAN decision 16) | `tests/test_ui_recipes.py` (`test_presenting_is_one_mode_with_one_bar`), `scratchpad/ui-sweeps/wbpresent.js` |
| Showing a canvas as it was (a board's History, WHITEBOARD_PLAN decision 33) | The presenting recipe's mode and bar, not a second one: Board, History… (`data-wb-cmd="history"`) puts the presenting host class `.wb-presenting` on (whose rule spares any `.wb-present-bar`), which hides every control but `#wb-history-bar` (a `.whiteboard-floating-panel.wb-present-bar`: a range slider from the oldest moment to now, the moment's words as a polite live region, Put back, Put back the selection, End) and takes the pointer off both drawing layers; the past is drawn by the board's own render (`wbState` swapped for the moment's rows), the keys are taken on the window in the capture phase, and a write to `/whiteboard/` is refused before it is sent (`wbHistGuard`). Closing reads the board afresh | `tests/test_board_history.py` (`test_history_is_the_presenting_mode_with_its_own_bar`), `scratchpad/ui-sweeps/wbhistory.js` |
| A disclosure that opens a list under it ("36 claims", "1 open question") | **A row, not a boxed button** (INBOX 803): `button.ghost.disclosure-row` (01-forms-settings.css), the full width, a caret then the words from the leading edge, no face and no edge, the row's `--hover-veil` under the pointer or the keyboard; the caret turns 90 degrees with `aria-expanded` | `tests/test_ui_recipes.py` (`test_a_disclosure_is_a_row_not_a_boxed_button`) |
| A filter that carries a count (the graph's kinds of link, its properties) | **A chip, not a button** (INBOX 803: "No kind 31" was a row of filled, bordered buttons, every kind on by default): `chip(label, "tag graph-filter-chip", onClick)` with its count after the words in `.library-chip-count`, `aria-pressed`; a filter that is on by default and turned off keeps its place struck through (`.is-off`, the Read as row's toggle), one that lights a set takes the chosen row's accent edge (`.is-lit`) | `tests/test_ui_recipes.py` (`test_a_counted_filter_is_a_chip`) |
| An action repeated on every row of a list (a shortcut's rebind, a task's Run now, a backup's Restore and Delete, a learned fact's Edit) | **Row actions** (INBOX 810): `rowActions(actions, ariaLabel)` in sheets-selects.js, each action a kebabMenu item (`label`, `title`, `run`, `danger`). At rest a quiet text button (`button.ghost.quiet`: `--text` ink, no edge, no face, weight 500); under the pointer or the keyboard the ghost tint and the focus ring, never under a 24px target. A destructive one (`.quiet.danger`) waits in `--muted` and turns `--error` on `--error-soft` only when aimed at. **Three or more fold into the row's ⋯** behind the first. A shortcut's keys are its own rebind button (`button.shortcut-key` holding the `<kbd>`, title "Change" or "Cancel"), so there is no Change column. The bordered tonal button stays only for an action that stands alone in a section's footer, and a surface has one filled primary | `tests/test_ui_recipes.py` (`test_a_rows_repeated_action_is_quiet_and_three_fold_into_its_menu`, `test_a_shortcuts_keys_are_its_rebind_button`), `$S/g57/walls.js` (columns of the same tonal words) |
| A set of things to start, each with what it covers (Help's tours of the app) | **Rows, not a wall** (INBOX 804): one filled button for the whole set (`#tour-start-btn`, Start the tour) and a quiet second beside it (`.quiet`, Replay the welcome), then a `ul` of quiet rows (`button.ghost.tour-row`), each the item's name over its one-line description (`.tour-row-blurb`, `--muted`, `--text-sm`), two columns where the pane is wide enough for the line to stay one line. A tooltip is never seen on a touch screen, so the description is on the row | `tests/test_ui_recipes.py` (`test_a_set_to_start_is_rows_with_their_descriptions_not_a_wall`), `$S/g57/walls.js` (6+ tonal buttons in a block) |
| A question box with suggested asks (the documents assistant) | **One composer, one height** (INBOX 804): the field is the search field's well (`.search-field.doc-assist-form`, its input `.search-field-input`) with the send inside it at its end, and the suggested asks and the no-model tools are quiet chips (`--chip-bg`, no edge, the ghost tint under the pointer or the keyboard); all three at `--control-h`, `--target-min` under a finger | `$S/g57/p803.js` (heights), `tests/test_ui_recipes.py` |
| A control in a bar (`.dock`, the Ask composer, the chat strip) | **Bar controls** (INBOX 813): **one bar select**, the dock's edgeless `--field-inset` at the bar's own `--control-h` (08-consistency.css, one rule for `.dock`, `.ask-composer` and `.chat-dock-controls`); **one filter trigger**, a `details.dock-menu` summary of the funnel, the word in a `.dock-word` and the caret, the word leaving below 600 so the icon stands alone (the same clip for every dock); **one view order**, list then grid (rows then cards); icon buttons quiet, the one primary filled and last, and no outlined control inside a bar | `tests/test_ui_recipes.py` (`test_a_bar_has_one_select_one_filter_trigger_and_one_view_order`), `tests/test_dock_grammar.py`, `$S/g57/bars.js` |
| What a button does under the pointer or the keyboard (every button family: icon-only, ghost, plain, status item, interactive chip, row; INBOX 784/788) | **One hover for every button**: a quiet fill from the recipe's tokens (`--ghost-btn-bg` on an icon or tonal button, `--chip-bg` on a status item, `--hover-veil` on a row or an interactive chip), the glyph or label to full ink, the button radius, eased on `--ui-fast`, the same under `:focus-visible` (declared in the same rule, "Hover and focus are one state"). The filled button goes one step deeper (`--accent-surface-hover`); a field or a card shows its edge instead; a sub-tab strip item shows its 2px line (rule 5); the accent colour is never a hover. Measured by `scratchpad/ui-sweeps/hoverbox.js` (the treatments across the header, seven tabs and Settings at 1440 and 390) | `tests/test_ui_recipes.py` (`test_every_button_answers_hover_with_the_same_quiet_box`) |
| A popup panel a person can put where it suits them (INBOX 1427, "make all popup panels draggable?? and resizable?") | **`panelMovable`**: give the panel the dialog head (`.dialog-head` inside a `dialog` or `[role="dialog"]`; the box that moves is the dialog or its direct-child card whatever wraps the head, so a head inside a wrapper moves with its body, INBOX 1448) and `js/panel-movable.js` (lazy, `LAZY_MODULES.panelMovable`) does the rest, with nothing per panel: drag the head to move (`translate`, one rect read at pointer-down), the corner grip `.panel-grip` to resize (the card is the scroll box, so content scrolls inside; minimum 280 by 160), the grip as the keyboard route for WCAG 2.5.7 (arrows move 16px, Shift and arrows resize, Home resets), a double-click on the head, Home on the grip, or the head's reset button `.panel-reset` ("Put back in the middle", shown only while the panel is moved, resized or docked) resets. **Docking (INBOX 1434)**: the head dragged within 24px of a screen edge shows `.panel-snap-preview` (one reused top-layer element, click-through, `--accent-soft` and `--radius-lg`, no blur) and the release fills the zone from `panelZoneRect` (halves, bottom half, quarters, maximise at the top middle third; inset `--space-3`; kept inside the top bar and status bar); `panelSnapZone` and `panelZoneRect` are pure and tested in node; the window is read at pointer-down so a move reads no layout; a dock is stored as the fifth item of the panel's entry and re-fitted on open and on resize; `data-panel-zones="left right max"` limits a panel's zones; Settings, Appearance, "Panels open where you left them" (`panel-pos`, default on) off means every panel opens centred. Position and size are kept per panel id (`id`, else the overlay's `id` or `data-sheet`, else the title) in `localStorage["tessellate.panels"]`, clamped to the window on first touch and on window resize so the head never leaves the screen. Only on a fine pointer at 600px or wider; a phone keeps its sheet. A panel that must stay put says `data-panel-fixed`; a popup with no head cannot be moved and is listed with its reason | `tests/test_ui_recipes.py` (`test_every_popup_panel_opts_in_to_panel_movable_or_says_why_not`: `PANEL_FIXED_HTML` and `PANEL_FIXED_JS` may only shrink), `tests/test_panel_movable.py` (clamp, size, keys and storage run in node) |
| A page of settings a person adjusts while watching the app (INBOX 1435, the owner: Settings, Appearance is "very large, and hard to navigate" and each change meant closing Settings) | **`appearancePanel`** (`openAppearancePanel`, appearance-panel.js, lazy as `LAZY_MODULES.appearancePanel`): a non-modal `[role="dialog"]` with the dialog head, no scrim and no focus trap, on `panelMovable` (drag, resize, dock) at the floating panels' layer (40, shared with the model panel: level with the top bar, over every bar the page pins, under menus, dialogs and toasts; INBOX 1453), a sheet at the foot below 600. **The page's own nodes are moved into it, never copied** (every id, listener and `LOOK_ROWS` row stays, so the appearance sync rule holds with one set of controls); Settings keeps its title bar and a line, `.appearance-popped`, with "Bring it back here". Its rows are styled by `appearance-panel-lazy.css`, generated by `scripts/appearance_panel_css.py` from the boot sheets' `#settings-modal` rules under `#appearance-panel` (a test fails when it is stale), then `appearance-panel-own-lazy.css`. **The strip** (`.appearance-strip`, `nav`, quiet `ghost small` buttons, the section in view `aria-current`) is outside the scroller so it is always in view: a press opens the section's fold and scrolls to it, the last section pressed is remembered on the device (`appearance-panel-section`), and `appearanceSectionAt` (pure, tested in node) says which section is in view. **Peek** is a worded ghost with `aria-pressed` that fades the ground with `color-mix` of `--panel`, never element opacity, so controls stay sharp, and ends with the panel. **Per-control reset** is the page's own `.setting-reset`, painted with `paintSettingRow`. Opened from the palette ("Appearance"), a right-click on the top bar's light and dark button, and "Pop out" in Settings, Appearance's title bar (which closes Settings). A new settings page that wants a panel hosts its nodes the same way | `tests/test_appearance_panel.py`, `tests/test_ui_recipes.py` (`test_the_appearance_panel_recipe_is_in_the_index_and_the_guide`) |
| A column beside a list that a person may want wider or narrower (INBOX 1443, the owner: "the connections sidebar also cant be resized"; the Connections column) | **`notesRailResize`** (notes-rail-spy.js, lazy with the rail): the width is the layout's inline `grid-auto-columns` (the rail is its implicit third track; removed, the stylesheet's own clamp is back), so the list reflows with no script and no new token. The handle is `.notes-rail-resize`, a `role="separator"` sibling after the rail on column 3 (not inside the rail, which scrolls), hidden with the rail by `#notes-rail[hidden] ~`. Drag moves it through pointer capture; the keyboard route for WCAG 2.5.7 is on the handle: Left widens and Right narrows by 16px, Home or a double-click resets. `notesRailClamp` (pure, tested in node) holds 240 to 560px and never lets the list drop under its 600px reading width. Kept per device in localStorage (`notesRailWidth`, try/catch). Only on a fine pointer at 600px or wider; the rail itself is drawn from 1280. A sidebar that is a real grid track uses `makeSidebarResizable` instead | `tests/test_notes_rail_resize.py`, `tests/test_ui_recipes.py` (`test_the_notes_rail_resize_recipe_is_in_the_index`) |
| A menu behind a button | `kebabMenu(items, ariaLabel)` in sheets-selects.js (positions, clamps, escapes clipping, closes on outside click) or `details.dock-menu` in markup. **Past five rows it is grouped**: an item carries `group`, a name, and the menu draws a hairline (`.menu-sep`, `role="separator"`) wherever that name changes. The name is not printed, because a heading over every three rows makes a ten-row menu seventeen rows tall and what makes a list scannable is the break rather than the word; an item with no `group` behaves exactly as before, so a short menu declares nothing. **An item with `items` is a submenu**: the row flies its own list out beside it (`buildMenuGroupButton`, menus.js: clamped to the window, escaped from a clipping ancestor, opened in place in the phone's sheet), for a choice of several settings behind one row (the companion's Companion, Atlas look, Size and Settings). **Below 600 it is an action sheet**: `openKebabSheet` moves the menu into the sheet recipe (rows full width at the thumb, groups and keyboard kept, a group row opening in place) and puts it back on close; the note row's own ⋯ (`entryOverflowMenu`) does the same, and a menu at the pointer stays at the pointer. **Every menu keeps the keys**: ↓ and ↑ on an open menu's button land on its first and last row, ↑ ↓ Home End walk the rows, Escape closes it and gives the focus back to its button, and a menu that closes with the focus inside it hands the focus back rather than dropping it on `body`. A built menu gets this from `wireMenuKeyboard` (options count as rows, and the menu owns its Escape); a `details` menu or a menu written in markup gets it from app.js's one delegated handler (`menuRowsOf`), so a new one needs no wiring of its own. **No gap at the ends**: the first and last things in a menu sit one menu padding from its edge; a `.dock-menu-section`'s own padding spaces it from the hairline between sections and is dropped at the menu's first and last edge (`menus.js` measures the inset). **One left column**: a section label, a select in a section and a row's icon start on the row recipe's `--space-5`, and a row's leading icon is a 1.25em box so the labels after it line up. **A long label is cut, never shrunk** (the owner, mono: "there's some overflowing text"): the row and its words flex with min-width 0, the words end in an ellipsis inside the row's padding, and a cut row carries its full words (and its hint) in a title on hover or focus (`menuRowFits`, both builders) | `tests/test_ui_recipes.py` (hand-built menus may not multiply; a long menu is grouped), `tests/test_menu_keyboard.py`, `tests/test_font_matrix.py`, `scratchpad/ui-sweeps/menus.js`, `fontmatrix.js` |
| A dock's one filled action that has a choice inside it (the Boards and maps dock's New: Whiteboard or Mind map) | A `details.doc-dock-menu.dock-menu.dock-menu-flip` in the actions zone whose `summary.small.dock-menu-primary` is the filled control (a plus, the word in a `.toolbar-word` span, a `.dock-menu-caret`; the summary's own `aria-label` is its name at a phone's width) and whose rows are `button.doc-dock-menu-item`s keeping the ids the standalone buttons had, so every caller that presses them still can. Each row is its icon, then a `.dock-menu-item-text` holding the word and under it one muted line saying what it makes (`.dock-menu-item-hint`, `--text-xs`, `--muted`): a tooltip is never seen on a touch screen. One menu instead of two create buttons: a dock holds one filled action, and a second kind of the same thing is a row, not a neighbour. Used by Boards and maps (WORLD_CLASS_PLAN 507) | `tests/test_dock_help_507.py`, `tests/test_dock_grammar.py` |
| A dock's one filled action whose common case is one press and whose other cases are a choice (the OCR workspace's Read: this page, or every page, or a range) | **A split button**: `div.split-button` holding the filled `button.split-button-main` (the default press, its word in the button) and a `.split-button-slot` that `kebabMenu` fills, its opener given `.split-button-caret`, a caret glyph and an aria-label naming the other cases (`ocrSyncReadMenu`), so the menu keeps the recipe's placement, escape and keys. One pill: the halves share the dock's `--control-h`, each keeps its outer corners, and the seam is a hairline in the fill's own ink. The split is the dock's one filled control (the grammar lint counts it as one, last in the row), and it hands the fill over like any primary (`ocrStageRead`: Read, then Save as note, both halves together). A rare case (a page range) asks when it is chosen (`promptDialog`), never a bare field in the row | `tests/test_dock_grammar.py`, `tests/test_ocr_workspace_717.py`, `scratchpad/ui-sweeps/ocr717.js` |
| A toolbar with more tools than one row holds (the formatting strips; a dock in a dialog, the OCR workspace's) | A dock in a dialog stays one row and **folds into its own ⋯**: `ocrFitDock` measures the row on every width change and folds by priority (`data-fold`, a word first, then whole controls, the reader's name last) and the ⋯ (`ocrSyncToolsMenu`) offers each folded control as a row. A formatting strip wraps (the default), or, in its one-row mode and on a phone, it stays one row and **folds what does not fit** behind a More disclosure in the strip's own end group: `fitDocToolbarRow` (documents.js) measures the row on every width change (`ResizeObserver`), folds tools from the end with `.doc-toolbar-over` until the group ends inside the strip, and More (`.doc-toolbar-more`, `aria-expanded`, titled with the count) wraps the strip to show them in place, the real controls with their own menus rather than copies. **Never a sideways scroller and never a pinned group over the tools**: the scroller hid everything past the edge behind a scrollbar, and the sticky group sat on Insert (INBOX 426 a). Measured by `scratchpad/ui-sweeps/doctoolbarfit.js`: every control inside the strip and none overlapping, at 360, 768, 1024, 1280 and 1600 | `tests/test_doc_toolbar_reach.py`, `scratchpad/ui-sweeps/doctoolbarfit.js` |
| A list you manage (rows you select, several at once, and act on: the Manage categories panel, and the tag manager, `openTagsSheet` in tag-manager.js, which reuses its classes) | a `role="grid"` `aria-multiselectable="true"` of quiet rows (`role="row"`, `aria-selected`), **never a listbox**: an option may hold nothing interactive and each row carries its ⋯ (axe-core's nested-interactive, INBOX 433). The first cell (`role="gridcell"`, the roving stop, named "Work, 3 notes") holds a colour dot or icon, the name (ellipsised) and its note count as quiet muted text after it ("Hobbies · 10", never a pill: INBOX 466); the last cell is a ghost `kebabMenu` shown on hover or focus and always under `(hover: none)`, reached with Right and left with Left; a roving tab stop (arrows, Home, End), Space selects, Enter opens the row's content, F2 renames, Delete deletes, the context-menu key opens the ⋯; a click selects (Ctrl or Shift adds). Selected rows raise a sticky footer of what can be done to them together. Above the list, one tool row: a filter field, the Sort by select (Name, Most notes, Recently used; remembered), one `.library-chip` toggle for the hardly used (Used once, Empty) and the one create action, all at one height; under it, look-alike names (`manageLookAlikes`: case, spaces, hyphens and a plural set aside) as one Merge each, three at most, with Not now. The count after a name is a quiet button that opens its notes (`manageCountButton`), out of the tab order. These helpers live in tag-manager.js and the categories panel loads it first (INBOX 504). The card sizes to its content up to its cap and the list is its only scroller. Head: the reference dialog head | `tests/test_nested_interactive.py`, `tests/test_manual_parity.py`, `scratchpad/ui-sweeps/catgrid.js`, `catpanel.js` (session scratchpad) |
| A choice among colours (the Manage categories Colour item) | **The swatch picker**, `swatchPicker` in categories-panel.js, opened by `pickCategoryColour` in a sheet under a one-line preview (a dot and the name). A `role="radiogroup"` of round swatches, six to a row, and one worded Automatic below that clears the choice. Each swatch is a `role="radio"` button with `aria-checked`, an `aria-label` and a `title` that name the colour, painted by `--swatch` through the CSSOM (never `style=`). The checked one is a Tab stop; arrows, Home and End move the focus and the check together, Enter, Space or a click commits and closes, Escape leaves the choice as it was. The checked swatch is a ring in `--ink` outside a gap in the card's ground, so the choice is a shape and not only a colour, and the focus ring sits outside it. **The hues are `CATEGORY_PALETTE` (notes-list.js), twelve that each clear 3:1 as a dot on the lightest and darkest ground of both themes**, so one hex serves light and dark; the server keeps the same keys (`CATEGORY_PALETTE_KEYS`) and refuses anything but a key or `#rrggbb`. A chosen colour is read through `categoryColour(name, automatic)` and nothing else: dots and chips are painted by `paintCategoryDot` (so a later choice repaints them where they stand), the graph's scale by `graphCategoryScale`, the dashboard by `categoryColour`; a change fires `categorycolours` and the map and dashboard redraw. A new row of colours is this recipe with its own palette, never a second row of buttons: `swatchPicker` takes `palette` (key to colour) and `none` (the worded choice's name), and Quick access's tile Highlight (`quickAccessPickTint`, quick-access.js; INBOX 589) passes the accent ahead of the twelve and "No highlight", seven to a row (five below 600) | `tests/test_ui_recipes.py` (only `swatchPicker` draws a swatch; every swatch is named; focus and checked are visible), `tests/test_category_colour.py` (contrast, every surface asks the one function), `scratchpad/ui-sweeps/catcolour.js` |
| A list of choices picked by typing or browsing (the "/" block menu, the command palette, a suggest list) | **The rich picker**, rich-picker.js, taken out of the "/" menu (the owner: "I reallllllyyyy like the design of this popup panel menu for the / commands. can we do more similar design styles elsewhere in the app??"). A `.rich-picker-list` (`role="listbox"`, the one scroller, a thin scrollbar, overscroll contained) of rows built by `richPickerRow({icon, label, about, keys, query})`: a 2rem square outlined icon tile (`tint` wears a callout kind's ink, `face` puts a face in it), a title over one muted line of what it does, the typed letters marked, and a right-aligned keycap holding the way to do it without the picker (the markdown the row writes, or the chord that runs it, read from the live `shortcuts` table). Groups are `richPickerGroup(name)`, pinned while their rows scroll. One row is `.active` (a soft accent fill, rounded): the keyboard and the pointer both move it, and there is no separate `:hover` fill, so two rows are never lit. A `.rich-picker-preview` pane beside the list, filled by `richPickerPreview`, **only where a preview says something** (the block it writes, what a command does and its key, a note's first lines) and only from 44rem up. The picker keeps its own position, width and keyboard code; the row, the group, the keycap and the pane are the recipe's. A dialog whose choices are walked by Tab takes the same row as a button (`richPickerRow({tag: "button", role: null})`, the Library's Create picker), filled on hover and focus instead. Drawn by the "/" and "[[" menu, the command palette (keycaps from `chord`, a registry name, or the tab's M-letter jump; the line from the row's `about` or the same `reveal`'s line in `featureCatalog`) the Library's Create picker and the `m` guide (`chordGuideGroup`: Go to and Do as button rows, each keycap drawn as a key in one column, the current tab marked, a hint line at the foot, on the popover shell). A list that opens from a typed token ("/", "[[") is the editor menu in every surface, placed at the caret by `editorPlaceMenu`, never a list in the flow under the box. Find anything's rows are search results (a rendered two-line snippet, a date) and keep their own shape. Not for a menu behind a button or at the pointer: that stays `kebabMenu` | `tests/test_ui_recipes.py` (only rich-picker.js stamps the anatomy's classes; every listed picker draws through `richPickerRow`; hand-built `role="option"` rows may only fall), `scratchpad/ui-sweeps/slashmenu.js`, `richpicker.js` (every converted picker at 1440 and 390, light and dark) |
| A dialog that picks one thing, or several, from the notebook (a note, a document, a file, a bookmark, a picture; INBOX 548) | **The picker dialog**, `pickerDialog` in selection.js, never the confirm alert's card with a bare input: the `.dialog-head` (the title, the icon X last), a `.tabs-line.popup-kinds.picker-kinds` strip of sources when there are several, **spanning the dialog** (INBOX 715 over the segmented well of INBOX 572: no pills in popups; it scrolls when the words do not fit), each tab carrying its `.seg-count` (what matches the words typed; on a phone under its name), one Tab stop, the arrows and Home and End walk it, and the source chosen last is remembered; one line of description when it needs one, the `.search-field` well, then the list at one height for every source and every state, on a thin scrollbar with no arrows. **A row never shrinks** (`flex: none`): every row is `--pick-row-h` (56px), 8px apart, the tile centred in it, the fill and the accent edge of the lit row on the whole row; a title is clipped by the row's ellipsis, never by a character count; a row's tile says its type (a file by `attachmentIconClass`, a bookmark by `bookmarkKind`). Nothing there or nothing matching is the empty state recipe (`pickerListState`: icon, title, one sentence). **One thing**: `pickerListbox`, the field a combobox over a `role="listbox"` of `richPickerRow`s (a 2rem tile, the name over one muted line of facts: a note's category and when, a document's words, a file's size or where it is used, a bookmark's site), Down and Up light a row, Enter or a click takes it, no foot. **Several**: the Attach picker's `notePickerRow`s and the dialog foot (the count, Cancel, the one filled button, off until a tick). Pictures keep their grid. Used by `pickEntryDialog`, `pickLibraryItemDialog`, `pickNotesDialog`, `pickMediaDialog` | `tests/test_ui_recipes.py` (`test_every_notebook_picker_is_the_picker_dialog`, `test_a_picker_row_never_shrinks_and_its_sources_span_the_dialog`), `scratchpad/ui-sweeps/pickers.js` (four dialogs with a full list at 1440 and 390, light and dark: no tile over another row, tiles centred within 1px, one row height, equal filled segments, no text spilling, one dialog height while filtering) |
| A menu at the pointer (right-click, long-press) | `openMenuAtPoint(items, ariaLabel, x, y)` in markdown.js: the same `kebabMenu`, given a one-pixel transparent anchor in a `.pointer-menu-host` parked where the pointer was | `tests/test_ui_recipes.py` (a pointer-anchored menu is the recipe, not a second menu shape) |
| A board action (anything a board's menus, right-click, palette or a key does) | **One row in `WB_COMMANDS`** (whiteboard-commands.js): id, words, icon, key, group, surface, what it needs. A top-bar menu row names it with `data-wb-cmd` and says its words (`menu` where the group head says the rest) and key; the right-click menu takes the row from `wbCommandMenuRow(id)`; the palette's "This board" group is `wbPaletteCommands` and the shortcut sheet's section `renderWbShortcutSheet`. A row that does not apply now is `aria-disabled` and its press toasts why (`wbRunCommand`), never a dead button | `tests/test_wb_commands.py`, `scratchpad/ui-sweeps/wb1005-zorder.js` |
| A sheet of a surface's keys and gestures (the board's "?", INBOX 566) | The dialog recipe (`.modal-overlay` > `.card.modal-card` with the dialog head, its '?' and X), one muted line, a `.search-field` that filters as you type, and sections of rows: `li.wb-help-row`, a grid of the icon, the words (`minmax(0, 1fr)`, `overflow-wrap: anywhere`, the only track that gives) and a key column of fixed width (`--wb-help-keys-w`) whose `kbd` caps wrap inside it, so a label can never run under its keys; two columns of sections while the card is wide, one below 48rem, the list scrolling inside the card. Rows that name a command read it from the surface's command table | `tests/test_wb_help_sheet.py`, `scratchpad/ui-sweeps/wb1005-help.js` |
| A side panel with tabs on a canvas (the board's sidebar: Library, Notes, Layers, Pages, Outline) | `#wb-sidebar`, a `.card.glass` floating at the canvas's left edge between its top bar and its tool rail: a vertical `role="tablist"` rail of icon-only tabs (`title` and `aria-label`, one tab stop, Up and Down walk it, `aria-selected` on `--accent-soft`), and beside it one `role="tabpanel"` with a head (the tab's name, its actions, the dialog-head X) over sections shown by `data-side-panel`; a tab pressed twice closes the panel to the rail; below 600 the rail hides while closed and the open panel spans the board with its tabs a row (`wbOpenSidebar`, whiteboard-library.js) | `tests/test_ui_recipes.py` (closes, glass), `scratchpad/ui-sweeps/wb1005-library.js` |
| A canvas's properties panel (the board's Format panel; WHITEBOARD_PLAN decision 19) | `#wb-format`, the sidebar's mirror: a `.card.glass` on the canvas's right edge between its top bar and tool rail, hidden until asked for (Ctrl+Shift+P, claimed from the app by `wbOwnsChord`; the bar's More menu; View; the palette). A dialog head (the name, the X last), a `.tabs-line` of three words (Style, Text, Arrange; one tab stop, Left, Right, Home and End walk it), one `role="tabpanel"` of `.wb-fmt-row`s: a two-track grid, the label's track fixed so every control starts on one line, each row tagged `data-fmt` and shown only for the kinds that take it (`WB_FMT_FIELDS`); on/off is the bar's `.wb-snap-label` switch; command buttons come from `WB_COMMANDS`, never hand-written, under their group's name. Every change goes through `wbFmtApply` inside `wbRecordGesture`, one undo step. Below 600 it spans the board | `tests/test_wb_format.py`, `scratchpad/ui-sweeps/wb1005-format.js` |
| A canvas's contextual bar (the board's `.wb-context` over a selection; INBOX 1354: "those popup toolbars stretch nearly the whole width of the screen") | One row, at most `min(40rem, calc(100% - var(--space-6)))` wide. A bar that would wrap folds its later groups into its More menu (`wbFoldContextBar`, in `WB_CTX_FOLD.order`), planned from one read of the widths (`wbFoldPlan`) and checked once, never a read per group; the More menu is the 304px popover. **What folds is one labelled grid** (INBOX 1403: pills wrapping onto ragged rows, a stray rule, an indented orphan): every folded group is a row, its `data-fold-label` in the first column (3.5rem) and its controls, in a `.wb-fold-controls` wrapper, in the second; the caps group is two `.wb-fold-row`s, Start and End; the wrappers are `display: contents` on the bar, so the same markup lays out as before; the menu is 20rem wide while the grid is in it; a new group in `WB_CTX_FOLD.order` carries its own `data-fold-label` | `tests/test_wb2_1025.py`, `tests/test_wb_fold_grid_1027.py`, `scratchpad/ui-sweeps/paint1026-barwidth.js`, `scratchpad/ui-sweeps/wb1027-moremenu.js` |
| A grid of things you place (the board library's tiles) | `.wb-lib-grid` of `div.wb-lib-tile[role="option"]` inside one `role="listbox"`: a thumbnail drawn from what the tile places with DOM calls (`wbLibThumb`: nothing stored, nothing to sanitise), the name in two lines at most, a star when it is a favourite; the active tile is the list's one tab stop and the arrows walk the grid; a click or Enter places, Shift+Enter places joined, F stars, a drag drops it on the canvas, and the rest is the tile's menu by right-click or Shift+F10 through `openMenuAtPoint`, never a ⋯ inside the option | `tests/test_ui_recipes.py` (`HAND_BUILT_OPTION_ROWS`), `tests/test_board_library.py`, `scratchpad/ui-sweeps/wb1005-library.js` |
| An icon or an emoji, picked or dragged (a map topic's icon, a sticker on a board or a map, an insert in the note or document editor; MINDMAP_PLAN decisions 43 to 46) | **The one picker**, `pickIconOrEmoji({anchor, onPick, modes, keepOpen, title})` (editor.js), which fetches icon-picker.js and icon-picker.css on first use and calls its `openIconPicker(`: a `.help-popover.icon-picker` lifted to <body> and placed by `placeHelpPopover` (centred when the anchor is off screen), the dialog head, a `.search-field`, a `.seg` of Emoji and Icons, and one `role="listbox"` of `role="option"` tiles under pinned group heads, Recent first (twenty, this device). Arrows move by tile and by row, Enter or Space picks, Escape closes and focus goes back to the opener (or its menu's button); no key leaves the panel. Icons are the vendored Phosphor names off its own stylesheet, emoji the curated `ICON_EMOJI_SOURCE`; nothing fetched. Every tile drags as text (`:ph-name:` or the emoji) and as `application/x-memorymap-icon`. Never a second emoji grid or icon list | `tests/test_icon_picker.py`, `tests/test_ui_recipes.py` (`HAND_BUILT_OPTION_ROWS`) |
| An equation, typed or picked (a note, a document, a board's text, the Chat and Ask boxes; DOCUMENTS_PLAN 16) | **The one equation editor**, `openMathEditor({target, anchor})` (math-editor.js, lazy, behind its stand-in in lazy-entries.js): the icon picker's shell (`.help-popover.math-editor` on <body>, the dialog head with its '?' and X), a `.tabs-line.popup-kinds` of Inline and Display, a TeX box over a live preview drawn by `docMathRender`, a `.search-field`, the palette's groups under pinned heads (ghost-button tiles, never `role="option"`), and the dialog foot (Cancel, the filled Insert). It writes `$...$` or `$$...$$` and nothing else; a surface is a thin caller, never a second palette | `tests/test_math_editor.py`, `scratchpad/ui-sweeps/mathedit.js` |
| A diagram drawn from text (a ```mermaid fence in Read, Live, print, export, chat and Ask) | **`mermaidDrawIn(container)`** (mermaid-draw.js, lazy, behind its stand-in in lazy-entries.js): the vendored Mermaid runs in the hidden same-origin frame of mermaid-frame.js with its own policy, takes the app's colours, redraws on a theme switch, and leaves an unreadable fence as code with one line of reason; a surface never loads Mermaid itself | `tests/test_mermaid_frame.py`, `tests/test_doc_mermaid.py` |
| A tree of what is on a canvas, in paint order (the Layers tab) | `#wb-layers-tree[role="tree"]`: a quiet `.wb-layer-head` per layer, then `li[role="treeitem"][aria-level]` rows on the row recipe (glyph, name, the eye and the lock as pointer conveniences shown on hover, on focus and when they are on; `aria-hidden` and out of the tab order, their keys H and L instead), `aria-selected` from the board's selection; Enter selects and brings it on screen, Alt+Up and Alt+Down or a drag restack within its layer, F2 renames, Delete deletes (`wbRenderLayers`) | `scratchpad/ui-sweeps/wb1005-library.js`, `scratchpad/ui-sweeps/wb1005-layers.js` |
| The keys and clicks a list is expected to keep (a row or card that has its own ⋯) | Nothing per list: app.js's delegated section "the conventions a list is expected to keep". A right-click, or a hold on a phone, on a row in `ROW_MENU_HOSTS` opens that row's own ⋯ items at the pointer (`kebabMenu` keeps them on `wrap.rowMenu`), except on a field, a link or a text selection; F2 runs the row's own Rename; the arrow keys, Home and End move between the items of an `ARROW_NAV_LISTS` list by where they are drawn; Shift+click on a tick sets the run since the last tick; and while a select bar is showing (or the Notes select mode is on) Escape, Ctrl+A and Delete press that bar's own Done, Select all and Delete, never from inside a field. A new list with a ⋯ joins by its selector in those tables, not by a listener of its own | `tests/test_library_pass2.py`, `scratchpad/ui-sweeps/listconventions.js` |
| A menu bar over a canvas (the board's Insert, Edit, Arrange, View, Board) | One `.wb-board-menu-wrap` per menu: a `[data-wb-menu-toggle]` ghost button carrying `aria-haspopup`, `aria-expanded` and `aria-controls`, and a `.wb-board-menu` written in markup rather than built by `kebabMenu`, because its rows are not all commands (the View menu holds a colour well, a grid select and four switches, which a command list cannot carry). What markup must not decide is the ARIA: `wbStampMenuRoles` (whiteboard.js) stamps every row at boot, `.wb-menu-item` as `menuitem`, `.wb-menu-section` as `group`, a row wrapping a native control as `none`, and `wireMenuKeyboard` then gives the menu the arrows, Home, End and an Escape that hands the focus back to its toggle. Measured before that existed: five menus, `role="menu"` on each and nought `role="menuitem"` inside, ArrowDown moving no focus. UI_MODERNISATION_PLAN Phase 8 makes this bar the seven-control ceiling's one exception, and the exception is the toggles only: everything else in the bar still answers to seven, which is six today | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/wbtopbar.js` |
| A right-click on a phone | `wireLongPress(target, handler, {selector})` in navigation.js: touch only, 500ms, cancelled by a move, and it swallows the `mousedown`, `mouseup` and `click` that the lift synthesises, so a hold does one thing rather than two (measured on the graph: holding a node opened its menu and lifting the finger opened that node's panel in front of it, taking the focus with it). What it opens is `openMenuAtPoint`, which asks for the focus again on the next frame, because Chromium takes it straight back out while the gesture is still in flight. Every `contextmenu` listener in app.js, documents.js and graph-canvas.js is counted against a `wireLongPress` call in the same file | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/graphphone.js` |
| A selection bubble (the editor's format bar `#selection-bar`, the ⋯ popup `.selection-popup`; any new bubble that follows a text selection) | **Brought back by a right-click on the selection** (the owner, 2026-10-11): `selectionRestoreOnContextMenu` in selection.js, the one `contextmenu` listener for every bubble, shows the bar (`selectionBarShow`) or the popup (`syncSelectionPopup`) at the pointer only while the click lands on a non-empty selection inside the surface that owns it (a textarea or field by being inside it, rendered or CodeMirror text by being under the selection's rects, 4px of slack), and `preventDefault`s then; otherwise the browser's menu stays. A menu another handler opened (`defaultPrevented`) wins and touch is left to the system. A new bubble is shown from that helper, not by a listener of its own | `tests/test_ui_recipes.py` (`test_a_selection_bubble_returns_on_one_right_click_helper`), `scratchpad/ui-sweeps/selrestore1011.js` |
| A canvas on a phone (the graph, the board, the map) | One finger belongs to the tool in hand (draw, select, marquee); **two fingers are always the camera**, pan and zoom, whatever the tool is, because no tool in this app is drawn with two and a phone otherwise has to go and find a Pan tool before it can move the view (measured on the board: a pinch scaled it by 1.000 with Select in hand). A hold is the right-click (`wireLongPress`), and a hold on empty canvas is the gesture that needs a modifier key on a desktop (the graph's lasso). A palette of tools is a sheet below 600, holding the rail's own markup moved in and put back on close, never a second copy of it | `scratchpad/ui-sweeps/graphphone.js`, `scratchpad/ui-sweeps/wbphone.js` |
| The top bar on a phone | Three controls below 600: the space switcher, notifications and one `kebabMenu` (`#header-more`, `initPhoneHeaderMore` in phone-shell.js) holding theme, Settings, Lock and Quit; the four desktop buttons are hidden by 10-responsive.css's Phase 11 band, never removed. Every control in it, and every menu row below 820, is `--target-min` tall | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/phonehead.js` |
| A primary action on a phone | The dock's one filled button, floated: its id in `FAB_IDS` (phone-shell.js), and `floatPrimaryActions` moves it out of the dock onto the page as `.dock-fab` below 600 (fixed, bottom right, above the tab bar and the safe area, pill radius, `--target-min`) and back above. It hides while the surface it opens is already showing (`.tab-page:has(#capture:not(.hidden)) > #notes-new-note.dock-fab`) | `scratchpad/ui-sweeps/phonecapture.js` |
| A swipe on a phone row | `initRowSwipe(list, {right, left})` (phone-shell.js), touch only, below 600: the row's children slide on `--swipe-x`, the row's own `::before` (`--accent-soft`) and `::after` (`--error-soft`) fill the gap with the words the row carries in `data-swipe-right` and `data-swipe-left` (a direction with no word never arms), the underlay saturates past `ROW_SWIPE_ARM` (88px), and a lift-off past it presses the row's own control: a note's star (`.favourite-btn`) or the menu's own `binNoteWithUndo`; a reminder's Done checkbox. A swipe is never the only way to an action and never a second copy of one; `touch-action: pan-y` leaves the vertical drag to the page | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/phoneswipe.js` |
| A sidebar on a phone | Below 600 the sidebar is the edge sheet it already is below 820, parked fully off screen, and it opens from a `.dock-nav` button at the leading edge of its own dock's head (`mountPhoneSidebarOpeners` in phone-shell.js, one row per `SIDEBAR_IDS` entry), never from a rail: the page beside it takes the full width. Above 600 the tablet keeps the 52px rail and the sheet's own toggle | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/phonesidebar.js` |
| A menu item | `makeMenuItem("ph:icon Label", title, run)` | same |
| A long list you find a row in by typing (more than twelve rows: the keyboard shortcuts, the space menu; row 1643) | **`listFilter(list, {label, threshold, rows, inside})`** in sheets-selects.js: one `.search-field.list-filter` before the list (or at its head, `inside`, for a popup that is its own list), shown only past `threshold` rows (12), hiding the rows whose words miss (the `hidden` attribute, marked `.list-filter-miss`, since a list's own row rule outranks a class) and saying so in one muted row (`.list-filter-empty`); Escape clears it before it closes anything; the owner calls `refresh()` after each redraw. Never a hand-built "Filter ..." field | `tests/test_ui_recipes.py` (`test_a_long_list_is_typed_to_through_the_one_recipe`, `HAND_BUILT_FILTERS` only shrinks) |
| The notebook's privacy verdict in the top bar (the Local chip; row 1641) | `button#privacy-chip.ghost.small.privacy-chip` in the header's first cluster: the receipt's verdict for this launch (`GET /privacy/verdict`) as an icon and one word (Local, Local network, Online with the icon in `--warn`), muted, at the bar's height; hidden until the first answer; one press opens Settings, Privacy; the word goes below 1100px and the chip is a `live` row of `#header-more` below 600 | `tests/test_ui_recipes.py` (`test_the_local_chip_shows_the_privacy_verdict_and_opens_the_record`), `tests/test_privacy_receipt.py` |
| The address of an object (a note, document, board, map, chat), to open it in the app | **Copy app link**: `appLinkMenuItem(kind, id)` (router.js) in the object's own ⋯, in the copy group beside Copy title; a markup menu (the document editor's, the board's Board menu) has one button calling `copyObjectAddress(kind, id)`. The address is `routeHashFor` (the router's one table) behind origin and path. A `[[wiki link]]` row is named **Copy wiki link**, so the two are never "Copy link". A pasted address of this origin and a known route renders as a same-window link (`appAddressHash`, router.js; drawn by notes-list.js) | `tests/test_router.py` |
| A card or row that opens something and carries controls of its own (a tick, a ⋯) | **the accessible card**: the card is a plain box (an `<article>`, never `role="button"` and never a Tab stop), and its title is the one control that opens it, made by `cardOpener(title, open, name)` (menus.js): a button by role, a Tab stop, Enter and Space. `.card-open::after` stretches the title's press over the card (08-consistency.css), so a click anywhere still opens it; the host is `position: relative` and `isolation: isolate`, and its own controls are lifted above the overlay at `z-index: 2`. The host keeps its click listener and each control stops its own press. A control inside a control is what axe-core's `nested-interactive` (WCAG 4.1.2) counted 35 times on the Library's cards (INBOX 433). Used by the Library's cards, the board cards and the Documents rows; the arrow keys move between `.card-open`s (`ARROW_NAV_LISTS`) | `tests/test_nested_interactive.py`, `scratchpad/ui-sweeps/cardopen.js`, `axe.js` |
| A recorder (the voice note and meeting dialog; UI_MODERNISATION V7) | **One large control**: `#meeting-record` at `--control-h-lg` times 1.4 on `--radius-pill` (Record, then Stop), the clock beside it at `--text-h2`, the level line under them (a still meter with reduced motion), Pause, Marker and Discard as ghost buttons at the dialog's control height; the device as a chip (`#meeting-mic > summary`, `--chip-bg` on `--radius-md`) folding out the microphone controls; after saving, `#meeting-done`: the first lines on `--surface-2` and the one filled Open | `tests/test_recordings_library.py` |
| A dropdown of values | a plain `<select>`; `enhanceSelect` restyles every one at boot | `tests/test_frontend_handlers.py` |
| A picker in a toolbar that is an action, not a setting (a colour to apply, whose resting text is only its own name) | the same `<select>` with `data-select-icon="ph-…"`: `enhanceSelect` puts the icon in the opener and `.select-opener-icon` clips the word (never `display: none`), so the face is an icon and a caret and the name is still the select's `aria-label`, its `title` the hover text. A worded button in a strip that has to hold one row carries its word in a `.toolbar-word` span, clipped the same way below the band where the row would wrap, and takes the icon-only square there. **A dock's sort when the dock must hold one row** (Library, AI skills, INBOX 599) is the same picker: it keeps the dock's inset and drops a worded select's 9rem floor, and a segment's words are `.toolbar-word`s that leave a dock under 58rem (the dock is the container, `.dock:has(.toolbar-word)`), leaving each cell its glyph and count | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/notetoolbar.js`, `scratchpad/ui-sweeps/settingsheads.js` |
| Focus on a `<select>` | `focusSelect(select)` in sheets-selects.js. **Never `select.focus()`**: `enhanceSelect` takes the native control out of the tab order (`tabindex="-1"`, `aria-hidden`), so the direct call focuses an aria-hidden element or nothing at all, silently. Measured across seven tabs: all thirteen reachable selects would have taken the focus onto the hidden control. The same goes for a `keydown` bound to a select, which never fires. | `scratchpad/ui-sweeps/selectfocus.js` (it cannot be a lint: what decides is what the variable holds at runtime, not what the source says) |
| A choice between drawings (the board's line ends: Start and End, INBOX 792) | A `<select>` whose `<option>`s sit in `<optgroup>`s and carry `data-menu-class="wb-cap wb-cap-<kind>"`: the shared select opener draws the groups, and each row leads with `.wb-cap::before`, a mask of the drawing in the row's ink (`--wb-cap`, a data-URI SVG of the renderer's own path; the Start list adds `wb-cap-start`, the same drawing turned round). The closed face keeps the word (`Start: `, `End: `) in a `::before`, so the rows do not repeat it | `tests/test_wb_line_ends.py` |
| Help longer than one line | one line in place, the rest behind a `data-help-for` '?' button and a `.help-body` popover | `tests/test_ui_signatures.py` |
| The model's reasoning, anywhere it is shown (Chat, the popup agent, Ask, the Guide, the writing room) | **The one Thinking fold**, `thinkingFold()` in chat-agent.js (`thinkingFoldIn(host)` for a fixed host in the page): a `details.agent-step.thinking-fold` whose `summary.fold-summary` is the steps and sources folds' own disclosure (an icon and the word Thinking, `--text-sm`, muted, a hover ground) and whose `.thinking` body is the steps fold's rail in the body face, muted, capped at 12rem and scrolling. Open while the model reasons, folded when a tool runs or the answer starts. Never a second builder, a fold in the markup or a surface's own body style (INBOX 457) | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/bubbleparts.js` |
| The web pages an answer read (CHAT_PLAN decision 66) | **One fold under the answer**, `renderWebSources(holder, sources)` in ask-compose.js: a `details.agent-step.web-fold` whose `summary.fold-summary` is the Thinking fold's disclosure ("Web results: 3 pages", `ph:globe`), open as one inset panel like it; **a card a page** (`li.web-result-card`, INBOX 1300 C06: a globe tile, the title a `button.linklike.card-open` whose press covers the card and reads the page **in place**, a ghost icon link to the browser above that press, its site and two muted lines), the reader (`readWebPage`) the page's blocks as Markdown (`webPageMarkdown`) under its title, its address as a link and one facts line (site, words, minutes, when it was read), Back to results. The list caps at 22rem, the reader at `min(32rem, 60dvh)`, each scrolling. `{ read: true }` is a page the model read (`read_url`): the fold's summary names the page and opening it reads it, the same reader. Never a page's markup, an iframe or a second list builder | `tests/test_ui_recipes.py` (`test_web_results_are_one_fold_read_in_place`), `scratchpad/ui-sweeps/webfold.js` |
| An answer's sources ("Grounded in", Ask and Chat) | **One native fold**, `renderAnswerGrounding` in capture-ask.js for both tabs: `details.agent-step.grounding-fold` whose `summary.fold-summary` is the heading ("Grounded in" and the source count, the disclosure caret drawn in reply-kit-lazy.css), open by default and remembered per browser (`prefs` key `grounding-fold`); the numbered source chips are its `.grounding-body`, each badge the bare digit centred by the grid (no trailing period); the evidence button stays below the fold. Never a second builder for Chat | `tests/test_grounding_1323.py` |
| How an answer was made (CHAT_PLAN B30, INBOX 805) | **One fold under the answer**, `renderAskWhy(lines)` in capture-ask.js into `#ask-why`, the last thing in the answer's foot: a `details.agent-step.why-fold`, shut, whose `summary.fold-summary` is the Thinking fold's disclosure ("Why this answer", `ph:path`), open as one inset panel like it (its open rules are the Thinking fold's, joined). Its body is `ol.why-lines`, a job's lines from the stream's `why` event (`ai/why.py`): each a `.why-at` seconds column in tabular figures, then the words, muted at `--text-sm`. Never markup, never a second builder | `tests/test_ui_recipes.py` (`test_why_this_answer_is_one_fold_built_once`), `scratchpad/ui-sweeps/whyfold.js` |
| An answer's shape by its kind (CHAT_PLAN decision 71) | **Markdown first, two lifts after**: a comparison arrives as a Markdown table and what is left as `- [ ]` lines, rendered by the one renderer; `digestShape(answerEl, support.shape)` in ask-compose.js then draws a count's leading figure large (`span.digest-figure`, `--text-h2`, 700) and wraps a who answer in one card (`div.digest-card`, `--surface-2`, `--border`, `--radius-md`, `--space-3`, its head `ph:user` and the name through `setLabel`), leaving the offer line outside. A long overview's lines past five arrive cited and fold behind one `button.linklike.digest-more` ("Show five more", `ph:caret-down`, `aria-expanded`) placed where they start, found by their bold labels (`support.more.labels`) or, for a line said as prose, the words it opens with (`support.more.starts`); pressed, they show and the first takes focus. Built from the rendered text so the citation marks keep their places; never a second answer renderer | `tests/test_ui_recipes.py` (`test_answer_shape_is_lifted_in_one_place`), `tests/test_gold_answers.py`, `scratchpad/ui-sweeps/shapes.js`, `scratchpad/ui-sweeps/digestmore.js` |
| An assistant's answer bubble (Chat, the popup agent) | The head (avatar and name, `.msg-role`), then one `.agent-steps` column holding the thinking fold, the steps fold and the answer in that order with the column's gap between them and no margins of their own, then the Sources panel (`chatSourcesPanel`: cards in Chat and Ask, one-line rows through its `row` hook in the popup agent, keyed on kind and id so a note found and then opened is one row), then the one muted facts line (`messageMetaLine`, a long model id cut short with the whole id on its title), then the action row, which hangs under the bubble in room of its own and never over what follows (INBOX 458) | `scratchpad/ui-sweeps/bubbleparts.js` |
| A pane that follows a stream (a transcript, a reasoning body) | `keepAtBottom(el)` in chat-agent.js on every write, never `scrollTop = scrollHeight`: it follows only while the reader is at the bottom, lets go the moment they wheel, drag or key upward, and follows again once they are back at the bottom (INBOX 458) | `scratchpad/ui-sweeps/bubbleparts.js` |
| A larger preview of a library tile (the whiteboard's elements library; INBOX 1301 D8) | `wbLibPeekOpen` in whiteboard-library.js: a `.help-popover.wb-lib-peek` lifted to `<body>` and set against `#wb-sidebar`'s outer edge, level with the tile and clamped on screen (no caret: it sits beside, not above). Opens after 300 ms of mouse hover or at once on keyboard focus (`:focus-visible`); never for a touch pointer; closes on leave, Escape (captured and spent, so the sidebar stays), a press, a scroll, a re-render and `dragstart`. `pointer-events: none`, so it never stands between the pointer and a tile. Never a native `title` on the same tile | `tests/test_ui_recipes.py` (`test_the_library_peek_is_the_help_popover_shell_and_closes_on_drag`) |
| A preview of a cited source (what a numbered mark in an answer stands for) | `openCitationPeek` in capture-ask.js: a `.help-popover.citation-peek` lifted to `<body>` and placed by `placeHelpPopover`, so the shell, caret, tier and flip are the help popover's and only the content is its own. One at a time; hover or focus shows it while the pointer or focus stays, a press keeps it (and on touch is the only way in); Escape (captured and spent, so a streaming answer is not also stopped), a press elsewhere, or the mark scrolling out of its transcript closes it. The whole preview (number, title, the grounded passage marked in its context, as characters) is one button that opens the note, with the note's facts and a worded Open beside it in the foot. A mark never navigates on its own press. **A cited note's pictures** sit beside its numbered chip under Grounded in (`groundingThumbs` in capture-ask.js, INBOX 502): one `.answer-grounding-item` of the chip and up to three `button.answer-grounding-thumb` squares (2rem, `--target-min` under a coarse pointer), lazy, alt from the server's `picture_alts` (caption, else the reading) or the Markdown alt, each opening the note's pictures in the lightbox; a `+n` for the rest | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/citepeek.js` |
| A date picked from a month (the Timeline strip's month label) | `renderTimelineMonthPop` in timeline.js: a static `.timeline-monthpop` panel wired once with `wireHelpPopover` to a `button[aria-haspopup="dialog"]`, so the shell, caret, tier and Escape are the help popover's. The grid is a `role="group"` of buttons with one Tab stop (roving `tabindex`): arrows a day or a week, Home and End the week's ends, Page Up and Page Down a month, Escape returns the focus to the button. A day past today is `disabled`, the days already on screen are tinted, a dot marks a day with a page; a day is 44px under a coarse pointer at 390 (the panel's width is its own, nothing else). A pick moves what is on screen and focuses it; it does not act. **The strip it serves is one header row** (INBOX 543): the month between its two arrows as one group (the month quiet, a fixed width so the later arrow never moves), then the seven days as one `.seg`-style well (`--chip-bg`, `--radius-choice`, flat segments) spanning the rest of the row; today's number filled `--accent-surface` with `--on-accent`, a `--accent` dot for a day with a page; one Tab stop, left and right a day, Home and End the ends, past an end the window walks a day; below the well's 34rem (a container query) each day stacks its weekday over its number | `tests/test_daily_strip.py`, `scratchpad/ui-sweeps/daystrip.js` |
| A calendar of days (the Timeline's Calendar view, and the reminders tab's Calendar, which opens it filtered to reminders) | `timeline-calendar.js`, lazy, with `timeline-calendar-lazy.css`: one grid of DOM cells (no SVG) built by `timelineCalCell`; a month cell is a fixed height holding its head (the number, the day page as a `smallButton`) and as many one-line chips as `timelineCalFit` measures room for (timed rows first, then the written notes with their titles), the last slot "+n more" when some are left; a cell too short for a chip beside its "+n" (`.is-dots`) shows the written notes as dots up to six and then a count, and keeps `TIMELINE_CAL_ROWS` timed rows; a press on a cell's own ground, Enter or Space opens the day (`timelineCalPick`: the Day view, or from it the feed); the week and the day are the heads and an all-day row over 24 hour rows in their own pane, each hour two lines. Rows are `smallButton`s (ghost, no edge, one line, ellipsis), a reminder's on `--accent-soft`; today's cell on `--accent-soft`, its number filled `--accent-surface`. One tab stop per period (roving `tabindex`, the month picker's keys plus T, Enter and N); a day's own buttons join the tab order only on the focused day. Drag is HTML drag and drop on one delegated listener per event on the view's box; every drop is on the undo bar and a refused one says why. Month at 1024, week at 768, below that the period as the feed's rows. The span is a `.seg` of three. Adding on a day is one sheet (`timeline-cal-add.js`, lazy, through `timelineCalAdd`; `openSheet`): a double click on a day or an hour (a single press waits `TIMELINE_CAL_DOUBLE_MS` before it opens the day), the head's Add (the way in without a double click) or N; Reminder and Event are a `.tabs-line.popup-kinds`, each kind its own words box with quick add's chips, the Day and Time fields the date-field recipe, a chip naming a day or a time moving them and a time alone keeping the pressed day | `tests/test_timeline_cal_add.py`, `scratchpad/ui-sweeps/caladd.js`, `tests/test_ui_recipes.py` (`test_one_calendar_grid_of_dom_cells`), `scratchpad/ui-sweeps/calendar.js` |
| A date or a time in a form (a reminder's due date and time, the Timeline's custom range, Ask's as-of day; Phase 12 decision 5) | `enhanceDateField(input)` in sheets-selects.js, run at boot over every `input[type=date]` and `input[type=time]` in the page: the native field stays the value (a `.value` write repaints the face, `.focus()` lands on it), the face is the select recipe's opener with a calendar or clock icon, the panel is the help popover shell holding the month pop's grid above (one Tab stop, arrows, Page Up and Down) or the day's times every 15 minutes in the person's clock, a typed phrase read by `ai/when` (`POST /reminders/when`), Today or Now, and Clear. A field built after boot stays native (the map topic's due date) | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/datefield.js` |

| Why a thing was chosen, as up to three measured reasons (an evidence card, a cited passage) | `evidenceSignals` / `evidenceBlock` in capture-ask.js: a `.evidence-signals` grid of name, a 4px `.evidence-signal-track` on `--border` with an `--accent` fill set by `el.style.width`, and the percent in tabular figures, each `--text-xs` `--muted`; the track is `role="img"` with the name and percent as its label. **A signal the app did not measure is left out, never drawn empty** (an empty bar reads as "no match"). A verdict line above it (`.evidence-verdict`, `--ink` when supported, `--muted` when partly). The evidence view (`renderEvidenceView`) is the same block on `.answer-evidence-card`s beside each sentence, one column below 600 | `tests/test_evidence_spec.py`, `scratchpad/ui-sweeps/evidence.js` |
| What a field's words were read as (a day, a time, a repeat, a person, a #tag, a window), under the field as it is typed: the Reminders box, Quick note, a new meeting's title, the Timeline's search, the palette (CHAT_PLAN decision 50) | **`quickAddAttach(field, surface, opts)`** (quickadd.js, lazy): one `.qa-chips` row (`role="group"`, "Read as") after the field or `opts.after`, each kind the surface saves as a quiet `chip(..., "tag qa-chip")` with its icon, a toggle (`aria-pressed`; off is struck through in place, `.is-off`), `data-kind` and `data-value` (what the save carries); the one question (`.qa-ask`, `role="status"`) at the row's end when a needed slot is missing (`quickAddAsk`), never a guess. The save reads `await quickAddSlots(field)` (`null` with no reading: the surface's old path). The reading is the server's (`GET /read`); a surface never reads language itself | `tests/test_ui_recipes.py` (`test_what_a_field_was_read_as_is_one_chip_row`), `tests/test_quickadd.py`, `scratchpad/ui-sweeps/quickadd.js` |
| A reading beside the text being written (the margin reader's cards, WORLD_CLASS_PLAN I2) | `.doc-margin` (margin-reader.js): a column inside `.doc-source-wrap`'s row, holding at most three `.doc-margin-card`s on `--surface-2` with no border, each a kind label (`chip item-label`, `is-warn` for Differs), one sentence, a muted reason and ghost small actions; the stack starts level with its paragraph through `--doc-margin-offset`, and below 60rem the column goes under the editor with no offset. Nothing is ever written into the text | `tests/test_margin_reader_spec.py` |
| A link you drag to the browser's bookmarks bar (the web clipper's Clip to Tessellate, row 24) | `a.web-clip-bookmarklet`: an object, not a button: a dashed `--border` edge, `--accent-text` ink, `cursor: grab`, on `--control-h`, its `javascript:` address written at runtime (web-clip.js) and a press inside the app answered with a sentence; beside it a ghost Copy. The window it opens (`clip.html`, `.clip-page`, `.clip-card`) is the app's own tokens and button ramp: one filled Save, a ghost Close | `tests/test_webclip_page.py` |
| A group of settings folded away until it is wanted | `details.settings-fold`: the `<summary>` carries the group's own label and **no control**: a button in a summary is a control inside a control (axe-core's nested-interactive, WCAG 4.1.2; INBOX 433). A head's '?' is the first child of a `div.fold-help-wrap` around the fold, `button.graph-help-toggle.fold-help`, and the summary keeps `<span class="fold-help-slot" aria-hidden="true">` where it was; `placeFoldHelp` (settings.js) draws the button over its slot, so the head looks exactly as it did (`scratchpad/ui-sweeps/foldhelp.js`). The graph's "Unpin all" is the one action left in a summary, a ratchet in `tests/test_nested_interactive.py`. The flat resting summary, the chevron and the hover fill come from 08-consistency.css's disclosure rules, which name the families by class, so a fold added to one of those four rules and not the others has no chevron or no hover. Open is remembered where it is a property of how the surface is used rather than of one visit. **A whole group of a long pane folds the same way**: `details.settings-group.settings-fold` with a unique `data-fold-key`, the group's `h3` in the `<summary>` (and its one '?' beside it, as above), the first group `open` in the markup; `wireSettingsFolds` (settings.js) keeps each key's open state per browser, a '?' in a closed head opens its group, and a deep link through `openSettingsModal` opens the fold it lands in. Closed, a group is one 51px row. Used by Settings' advanced groups, by the long panes (Appearance, Keyboard shortcuts, Extras, Skills) and by the graph's options panel, whose three tuned-once sections (Physics, Groups, Minimap) are folds | `tests/test_ui_recipes.py` |
| A disclosure marker (the thing that says a row folds: a Settings fold, the help accordion, a task log, the Library's Contents, notes and outlines) | **One caret**: Phosphor `ph-caret-down` at 1em of its row, in the row's own colour, turned `rotate(-90deg)` while closed and upright when open, on `--motion-fast` (none under reduced motion). In markup it is `<i class="ph ph-caret-down contents-caret">`; on a `<summary>` it is the `::before` that 08-consistency.css's disclosure rule draws ("The chevron the native marker was hiding"), so a new fold family joins that rule's list rather than drawing its own. Never a triangle or chevron built from borders (INBOX 464 (14): a 5x6px border triangle in Settings beside the Library's 16px caret). **A row that opens in place** (the Notes rows view, INBOX 676) has a button rather than a summary: one ghost icon button (`.row-expand`), the same in both states (`aria-expanded` never fills it), whose `ph-caret-down` turns `rotate(180deg)` open on `--ui-base`; the row's height animates in place from its current height (`toggleRowExpanded`, `--ui-slow`), so a second press turns back mid-way | `tests/test_disclosure_marker.py`, `tests/test_rows_676.py`, `scratchpad/ui-sweeps/rows676.js` |
| Choosing files to bring in (an import, an upload) | **One step**: a ghost button carrying the verb ("Import files", "Import a folder", "Upload") over a hidden `input[type="file"]` it clicks; choosing the files starts the work. The picker's own Cancel is the way out before; after, a toast with Undo puts it back, for an import by binning exactly the notes it made (`undoImport` in settings-data.js, from the ids `/import/markdown` and `/import/document` return), through `offerUndo` so the toast, the status bar and Ctrl+Z are one entry and it can be redone. Never the browser's own "Choose files" box beside a second button that does the work (INBOX 464 (18): three imports in Settings, Data were two steps each) | `tests/test_import_one_step.py` |
| An on/off setting | `label.setting-check` with the switch first. **The switch stands on the group's text edge**: in a Settings group the row hangs its padding and edge outside the column (08-consistency.css, INBOX 464), so the switch lines up with the head, labels and hints and the hover fill bleeds into the group's padding; measured before, all 130 switch rows sat 9px inside the column. A checkbox `.check-row` is the same row: no fill when on (08-consistency.css), a `--divider` hairline between rows, `--space-4` from the switch to its label, and the switch first in the markup | `scratchpad/ui-sweeps/switches.js`, `scratchpad/ui-sweeps/switchdepth2.js switchalign`, `scratchpad/ui-sweeps/togglerows.js`, `tests/test_ui_recipes.py` |
| A setting changed from its default (any Settings row; WORLD_CLASS_PLAN decision 52) | the row is named once, in `SETTING_ROWS` or `LOOK_ROWS` (settings-rows.js), never marked by hand: the row carries `.setting-modified`, a 2px `--accent-text` bar (the accent at a contrast that reads) drawn by `::before` in the gutter one `--space-3` outside the text edge (so the label and the switch keep their place, and the bar never touches the text), and an icon-only `.setting-reset` at its end that sets the control to its default and fires the control's own event, so the reset saves through the one path the control already has; a pane with changes gets one ghost "Reset N changes" in its title bar. A look setting the notebook does not keep carries the "On this device" `.setting-scope` chip (performance mode, and the sizes in `DEVICE_ONLY_KEYS`: zoom, text size, density, companion size) | `tests/test_settings_rows.py`, `tests/test_ui_recipes.py` (`test_a_changed_setting_is_marked_by_the_rows_recipe`), `scratchpad/ui-sweeps/settingsrows.js` |
| Asking for the password for one action (unlocking private notes, turning sign-in off) | `askPasswordPrompt({title, message, submitLabel, submit})` in app.js: the lock screen's own card in `data-mode="prompt"`, lifted above the dialogs (`.lock-prompt`, z-index 1045), with "Not now" and Escape as the way out; `submit` throws to put its message under the field. Never a second password form: the `type="password"` fields are the lock card's, Change password's three, the sealed backup's two, and the new password and its confirmation on the "Forgot your password?" card (INBOX 663), which sets a password without the old one | `tests/test_lock_boundary.py` |
| Two or three short exclusive choices, always in view (a view mode, a setting, a pair of verbs) | `.seg` with `aria-pressed`. **Only these** (INBOX 665, the owner: "i dont really like these multi pill elements exept in some small cases like the little view mode 2 pill ones"): four or more choices, worded choices carrying counts (Questions' Open, Answered, Dropped; AI skills' kinds), or a set that wraps is a `<select>` (the row below) or, for a look, previews (the row after it). A `.seg` of four or more written in index.html is named in `SEG_OF_FOUR_PLACED` with where it is placed; the one that stays (INBOX 670) is the Attach picker's five sources, which the picker row below pins as equal segments carrying a count each. Settings' Font and Density, the Graph's Layout and the suggestions inbox's kinds are lists | `tests/test_ui_signatures.py`, `tests/test_ui_recipes.py` (`test_a_pill_well_holds_two_or_three_choices`), `scratchpad/seg665_inventory.py` |
| A visual choice in a popup (a map topic's box, edge bar, fill, line weight and bend, alignment and icon; a marker's priority, progress and flag) | **Previews**, `.wb-map-picks` (`wbMapPickRow`, `wbMapMarkerSeg` in whiteboard-map.js): a `role="group"` row of `button.ghost.small.icon-only.wb-map-pick`, each drawing what it makes (an inline SVG on a 20 by 14 box in `currentColor`, a Phosphor glyph, or the mark itself through its one painter), its words as its `aria-label` and `title`, on one line beside its name in a shared label column (`5rem`), one control height (a menu row's 32, 44 below 820 and under touch, where the name goes over its row), never wrapping; the chosen one `--accent-surface` behind `--on-accent`. **Following the map is not a peer**: it is the trailing `.wb-map-pick-follow` reset glyph, `--muted` like every reset in a door and on the bar (`#wb-map-reset`), disabled while the topic follows. The look the map gives takes the chosen state like any other (one selected look: `.is-inherited` is a hook, never a ring, a border or a grey fill). A selected option and a topic's own look paint at once while the topic stays selected, and a door never opens on the topic it edits (`wbMapStripMenuOffTopic`: where it is, above the bar, beside the topic, under it, over it; 0px intersection). A palette (the icon slot's twelve) is `.is-grid`, six to a row by design. A size on a bar is the Stepper (`wbMapSizeStepper`) | `tests/test_map_node_controls.py`, `tests/test_ui_recipes.py` (`test_a_visual_choice_is_a_row_of_previews`), `scratchpad/ui-sweeps/seg665.js`, `scratchpad/ui-sweeps/mapfixmenu.js` |
| A way back in without the password ("Forgot your password?", INBOX 663) | the lock card's twin, `#lock-forgot-card` in `#lock-overlay`, shown in the lock card's place (`openForgotPassword`, account-recovery.js, lazy with recovery-lazy.css): the dialog head with its '?' and a Back close, a `.seg` of the two paths (the recovery key; the reset), each path's one action spanning the field like Unlock, the error line under it. A destructive path is armed by a typed word (`RESET`), never a checkbox. Answers this computer only, and says so before anything is typed on another device (`reset_here`) | `tests/test_forgot_password.py`, `tests/test_forgot_password_ui.py`, `scratchpad/ui-sweeps/forgotpw.js` |
| A secret shown once (a recovery key) | `#recovery-key-dialog`, a `.space-dialog` with the shared head: one muted line saying where to keep it, the secret in `.recovery-key-value` (monospace, `--text-lg`, select-all), Copy and Download .txt as ghost buttons, one filled "I've saved it". The secret is written in when it opens and cleared on `close`; never in a `title`, an `aria-label` or storage (`showRecoveryKey`, account-recovery.js) | `tests/test_forgot_password_ui.py` |
| An address another device types (Settings, Other devices; the privacy receipt's Who can open this app; INBOX 867, the owner: "can this be better styled and easier to read??") | `renderLanAddresses(holder, state)` (settings-controls.js, with lan-lazy.css): a short status sentence above it, then the first address alone on its line in `code.lan-address` (monospace, `--text-lg`, select-all, the secret's box) with a ghost Copy beside it, and the rest under a `button.ghost.disclosure-row` "Other addresses (n)". The server orders them (`netbind.order_addresses`: the network's own interface first, virtual adapters out, IPv6 last), so both surfaces draw one list one way; never a run-on sentence of addresses | `tests/test_ui_recipes.py` (`test_an_address_for_another_device_is_one_block_drawn_by_one_renderer`) |
| Two to four exclusive choices | `.seg` with `aria-pressed` | `tests/test_ui_signatures.py` |
| A popup that chooses a kind (what it lists or makes: the New board dialog's Board or Mind map, the icon picker's Emoji or Icons) | **A tab strip under the head, never a floating pill** (INBOX 715, the owner: "i dont like pills like that in popups"): a `.tabs-line.popup-kinds` with `role="tablist"`, the popup's full width, its tabs `role="tab"` with `aria-selected` and words only, one tab stop, Left and Right and Home and End walking it, the board's Format panel's strip in a popup. A `.seg` stays only for a setting's value or a view of one pane (the row above); the pills still in popups are named in `SEG_IN_POPUPS` and `SEG_BUILT_IN_SCRIPT` with what each is, the kind switches among them placed, and the lists only shrink | `tests/test_ui_recipes.py` (`test_a_popup_chooses_a_kind_with_a_tab_strip`), `tests/test_board_templates_715.py`, `scratchpad/ui-sweeps/board715.js` |
| Two to four toggles that belong to one question (a filter set that is always all of them, none of them removable), in a row with space for them | `.seg.seg-multi`: the same well, `aria-pressed` on **every** segment rather than on one, never wrapping, the word beside the icon above 1200 and hidden (not dropped) below it so the accessible name is the same at every width. Not a row of chips: a chip is a filter you can take off | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/timelinedock.js` |
| The same set in a row that is already full, or whose labels are words rather than glyphs | A `details.dock-menu` whose summary is a ghost button saying what the filter is set to ("Kinds: all", "Kinds: notes, boards"), holding one `.doc-dock-menu-check` row per member (icon, word, checkbox). One width at every zoom, where a well of four is as wide as its four labels: the Timeline's was 441px of a dock that also holds a search box, a view switch and Options, and at 150% zoom it collided with them (INBOX 214). The rows are `.doc-dock-menu-check` so the menu stays open while you tick them, and a `change` handler, not `click`, since a checkbox inside its own `<label>` fires both | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/chrome214kinds.js` |
| A brief confirmation | `toast(text)`; with one action, `toastAction(text, label, fn, { go })` (an opener passes `go`, see the toast row below) | |
| A message about something the app expects (a field left empty, nothing to act on yet, an add-on or model that is off, a limit, a capability the browser lacks) versus a fault | **`toast(text, "info")`** for the expected situation: a plain toast, no "Report this", not silenced by "mute notifications", one short sentence that says what to do next. **`toast(text, true)`** only for a fault (a failed request, a network error, an exception); the helper shows a request the server refused with a 4xx as plain by itself (`toast.refused`, set in `api()`). A new red toast with a message of its own is listed with its reason in the test | `tests/test_error_toasts.py` |
| A notification row (the bell's panel) | **One block** (INBOX 811): the unread dot and the icon share the leading column (`.notif-dot` absolute in the row's start padding, so a read row's icon does not move), then the text column: the title, the description, and **the meta line** (`.notif-foot`): the time, and the row's action at its end as a quiet text button (`button.ghost.small.quiet.notif-cta`, `--notif-line` tall). **The read circle and remove cross are the row's right-edge column** (`.notif-row-actions`, the grid's third column, centred on the row; INBOX 874, the owner: "should the x and tick buttons ... be at the bottom of the notification?? I thought they were in the middle or top right??"), drawn at rest at every width, never on the meta line and never hidden until hover (a gap that appears is the INBOX 523 complaint); an action that has run or lapsed is meta text (`.notif-cta-state`: "Done", "Undo expired"), never a disabled button. Every first line is `--notif-line`, so dot, icon and title share a centre; padding `--space-3` on all four sides | `tests/test_notification_actions.py`, `scratchpad/ui-sweeps/notif874.js`, `scratchpad/ui-sweeps/notif1005-sweep.js` |
| The state of an optional engine a surface depends on (Tesseract for the OCR workspace: can it run, in which language, and one action when it cannot) | **A dot on the button that uses it, and the engine line in its popover** (INBOX 717): in the OCR workspace the reader button carries `.ocr-engine-dot` (`is-ok`, `is-warn`, `is-busy` while installing; its title and aria-label say the state in words, `ocrSyncReaderButton`), and its `details.dock-menu` holds the reader choice, RapidOCR's "not installed" line with an Install that opens its Packages row (`revealFeature("extra-row", id)`), and **the engine line**, mounted with `popover: true` (a quiet `.ocr-engine-status` line instead of the chip, the language label over its select, no Manage button: Manage is a row of the dock's ⋯). Elsewhere **the engine line**, `ocrEngineMount(host, {readers, settings, popover, onChange, onPaint})` in ocr-engine.js (a lazy piece): one `.ocr-engine-line` of a state chip (an `item-label is-ok` chip when ready, `.ocr-engine-chip` with `is-warn` when not), one muted sentence that names the cause and what still works, and **the one control that fits the state**: the language `select` when it can run, a filled Install button when it cannot, a `progress` bar with the installer's own step while it installs (followed from `GET /extras`, the Packages panel's source), and Try again plus the reason when it fails. The status is the server's (`ocr.engine_status`, carried by `GET /ocr-readers`), never inferred from an installer's exit code, and the same object draws the workspace's line and, as `settings: true`, only the language choice in the Packages row, which keeps its own Install, Reinstall and Remove: one place manages it, the other shows it. A read that cannot run says so and says what to do (`ocrChooseReader`: the other engine takes it and the message names both, or an instruction); it never answers with a success over nothing | `tests/test_ocr_engine_ui.py`, `tests/test_ocr_engine.py`, `scratchpad/ui-sweeps/ocrflow.js` |
| Something is working on it (an AI call, a download, a long read: any inline wait that is not a skeleton and not the chat's reply dots) | **One ring, `.spinner`**, drawn by `spinnerEl()` or, inside any label, the `ph:spin` marker: `setLabel(el, "ph:spin Reading…")`, `chip("ph:spin Filing…")`. It is 1.15em of the text beside it (the size `.ph` gives an icon), a `--spinner-stroke` (2px) border, `--accent-text` (the one colour that holds contrast on the page and on `--accent-soft`; `currentColor` made a 2px ring in a muted line vanish; the only two exceptions are a filled button, where it takes the button's text colour because accent on accent would vanish, and a danger button, whose ring is its red like its icons), one turn per `--spinner-turn` (0.9s). **Reduced motion** keeps the ring and pulses its opacity (`--spinner-pulse`, 1.8s), never a frozen ring and never a swapped glyph; progress motion "always" still turns it. **A button** is busy through `setBusy(button, true, "Saving…")` and `setBusy(button, false)`, which disables it, sets `aria-busy`, puts the ring first and puts back exactly what was there; never `disabled` plus a hand-set label. **Copy**: sentence case, one real `…` or none, never `...`, no em-dash; "Saving…" for a write that settles at once may stay words, anything that waits on a model, the network or a download carries the ring. Not this recipe: the skeleton (`showSkeletons`), the chat reply dots (`typingDots`, the model's answer on its way, in a bubble), the companion's poses, the boot splash | `tests/test_spinner_recipe.py` (no second turn keyframe, no `circle-notch`, no `...`, no hand-set `aria-busy` on a button, every animation name has a `@keyframes`), `scratchpad/ui-sweeps/spinners.js` |
| When a job last ran and how it went (a maintenance action, a background pass, an import) | **The last-run line**: `<p class="status job-line" role="status" data-job-line="<kind>"></p>` beside the job's control (or `jobLineEl(kind)` for a control built at runtime), filled by `refreshJobRuns` in settings.js from `GET /jobs/last-runs`, one record per kind kept by `core/jobruns.py`. Quiet `.status` text, "Last run 2h ago · succeeded · 412 notes indexed", the exact time and the duration on hover; **red (`.error`) only on a failure, and then it says why**; a stop is "stopped", never red; running is the `.spinner` ring and "Running…" (the line polls itself while it shows). A new job adds its kind to `jobruns.KINDS`, wraps its work in `with job_run(kind) as run:` and sets `run.result`; the Background jobs overview lists it with no frontend change | `tests/test_job_runs.py` (every line names a known kind; every kind is written by a job), `scratchpad/ui-sweeps/joblines.js` |
| The result of a check on this computer (Settings, About, Maintenance's Check this computer: the launcher doctor's rows) | **The Health group's row with a mark**: `maintenanceDoctorRow(row)` (settings-controls.js) builds a `.setting-row.doctor-row`, its `.setting-label` led by one `i.doctor-mark` (`is-ok` a check circle in `--ok`, `is-warn` a warning in `--warn`, `is-x` a cross circle in `--error`: the glyph differs, never the colour alone, and its `aria-label` says it in words) then the row's name, the fix under it as the label's `small.muted`, the value as `.setting-control.muted` that takes the remaining width and wraps a path (`overflow-wrap: anywhere`); the verdict and the time go in the group's one `.status` line above the rows. The rows are the server's (`GET /system/doctor`, core/doctor.py), never worked out in the page | `tests/test_ui_recipes.py` (`test_a_check_result_row_is_the_health_row_with_a_mark`), `tests/test_maintenance.py` |
| A dialog | `.card.modal-card` (settings-sized) or `.card.space-dialog` (small), opened through the app's modal helpers, never a bare `<dialog>` with its own chrome | `tests/test_ui_signatures.py` |
| A sheet (a panel that arrives from an edge, which is what a phone gets instead of a column) | `openSheet({label, name, build})` in phone-shell.js: a `.modal-overlay.sheet-overlay` holding a `.card.modal-card.sheet-card`, so the scrim, the z-index tier and the backdrop press are the dialog's own. It comes from the bottom edge at every width, names itself in an `h2.sheet-title` with an X (`.sheet-close`) beside it in a `.sheet-head`, closes on that X, on Escape (captured) and on a backdrop press, takes focus on open and hands it back to the opener on close, leaves with a `--motion-fast` fade (`.sheet-leaving`, added by `close`, which removes the overlay when the transition is over and at once under reduced motion; `onGone` runs then), holds its rows in a `.sheet-list` of full-width `.sheet-row` buttons at `--target-min`, and pads its foot with `env(safe-area-inset-bottom, 0px)`. Two sheets predate the recipe (`.sidebar-sheet-open`, `.graph-popup-sheet`) and are the only hand-built ones allowed. They stay hand-built on purpose, and the reason is the recipe's own boundary: `openSheet` builds a **modal bottom** sheet out of nothing, and those two are **in-place** sheets, elements already on the page that become one inside a band. Moving them onto it would cost each the thing it was built for (the sidebar keeps a rail on screen with its opener on it, which is the way back; the graph's is deliberately not modal, so the map it came from stays visible). What an in-place sheet does share is the dismissal, through `wireInPlaceSheetDismissal` in sheets-selects.js: captured Escape, a press outside, and focus back on the opener. One variant exists, `corner` (Atlas, the guide panel): a chat is a column, so above 600px it takes a reading width and **floats**, one inset on both edges, all four corners on `--radius`, and its foot padded like a card rather than with `.sheet-card`'s home-indicator inset; below 601px it is the bottom sheet again, because in a 390px window the corner is the window. It is also the one **modeless** sheet (`modal: false`): above 600px no scrim, presses pass to the app, no `aria-modal`, and Escape closes it only from inside it, so an answer that says "Open the Reminders tab" can be read against the tab. A variant that touches an edge keeps the edge sheet's geometry; one that does not, does not. A second variant, `page` (the note opened on a phone, `openNotePage` in phone-shell.js; the Library reader below 600, `ocrPhonePage`): the whole screen, no cap, no rounded top, the close relabelled as a back chevron, and the surface's own actions in a `.thumb-bar` at its foot, **moved** there from wherever the wide layout keeps them and moved back above 600, never a second copy. A surface that already is a `.modal-overlay` dialog takes the variant's two classes rather than being rebuilt on `openSheet`, and the stamping is written in app.js whatever file owns the surface: the variant class is the loophole otherwise, and `tests/test_ui_recipes.py` fails any other file that writes one | `tests/test_ui_recipes.py` (hand-built sheets may not multiply; the corner variant floats), `scratchpad/ui-sweeps/phonemore.js`, `scratchpad/ui-sweeps/guidepanel.js` |
| A bar of actions above the on-screen keyboard (what a phone gets instead of a toolbar it cannot reach) | `.thumb-bar`: fixed to the bottom edge, `role="toolbar"` with its own label, shown by a `max-width: 600px` block and nothing else, every control at 44px, and its bottom padding a `max()` of `env(keyboard-inset-height)`, `var(--keyboard-inset)` (app.js writes it from `visualViewport` once, for everything) and `env(safe-area-inset-bottom)`. **Never its own `visualViewport` listener.** Used by the documents editor's phone bar | `tests/test_ui_recipes.py` |
| A floating panel over a canvas | `.card.glass` plus the panel on the `[data-glass="off"]` list | `tests/test_ui_recipes.py` |
| A full-screen viewer of a file (the lightbox: a picture, a PDF's pages, a document; INBOX 1300 C30) | **Two `.dock`s on `--modal-bg` floating over the scrim**, never controls in a row under the content: the top bar (`.lightbox-topbar`) is the identity (the name as an `h2` that ends in an ellipsis, "2 of 5" as its `.dock-chip`, kept at a phone's width) and the file's icon-only ghosts as one run (Copy text when there is a reading, Download, Open in a new tab, Details as an `aria-pressed` toggle, the '?' on `data-help-for`, the ⋯ `kebabMenu`, Close last); the foot (`.lightbox-bottom`) holds the view's dock (zoom out, the readout against the picture's own pixels, zoom in, Fit, 1:1, Rotate; a PDF's page stepper) and, for more than one file, the filmstrip above it (48px tiles, one tab stop, the current one ringed in `--accent`, a picture's tile fetched when it scrolls into the strip). Below 600 the side arrows move into the dock and the picture takes the width. Wheel and pinch zoom about the pointer, drag pans, double-click is Fit and actual size, a press's zoom eases on `--ui-slow` (none under reduced motion); keys + - 0 1 R I, arrows, Escape, taken in the capture phase so a menu or popover over it keeps its own Escape. The bars fade only for a mouse resting on the picture (2.6 s), never after a key, with a focus ring showing, with a menu open, or under reduced motion. Its CSS is `lightbox-lazy.css` | `tests/test_ui_recipes.py` (`test_the_file_viewer_is_two_docks_and_a_filmstrip`), `tests/test_lightbox.py`, `scratchpad/ui-sweeps/lightbox1300.js`, `scratchpad/ui-sweeps/lightboxfit.js` |
| Styles only a lazy bundle's surfaces draw (a board's or the documents editor's own panels) | `frontend/css/library-lazy.css`, loaded with the Library bundle (`LAZY_MODULES.library`; `ensureModule` gives a `.css` file a `<link>`), never a boot stylesheet, which the boot budget holds. Linked after every boot file, so only new surfaces go there, never an override of a boot rule; listed last in `tests/_css_paths.py` so every CSS lint reads it | `tests/test_lazy_css.py`, `tests/test_boot_budget.py` |
| One surface given the whole window (the documents editor's focus mode) | A class on the tab page (`#tab-documents.doc-focus`): `position: fixed; inset: 0` over the top bar and the tab strip, every other band of chrome `display: none`, the content at its own measure and centred, and no blur on a window-sized card. What is left is **one** floating `.card.glass` pill (`#doc-focus-bar`, `role="toolbar"`): what this is, its one live fact, and a **worded Exit**. **Nothing the page offers is out of reach from it** (INBOX 426 a, b): a Tools toggle (`#doc-focus-tools`, `aria-pressed`) brings back the dock and the formatting strip in their own places, and a Suggestions toggle (`#doc-focus-prose`, `aria-expanded`) opens the writing panel as a side panel fixed to the window's right edge while the page gives up that room, and a Sidebar toggle (`#doc-focus-sidebar`, `aria-pressed`, INBOX 453 (1)) is its mirror on the left: the document list and outline as a panel fixed to the window's left edge on the solid modal ground, the page giving up the room, both panels starting at `--doc-focus-panel-top`, under the pill; below 600 the three keep their icons and their names move to `aria-label` and title, and the pill gives up the word count (400) then the save state (340) before it overflows. Escape closes the sidebar first and leaves the mode on the next press; below 720 opening one side panel closes the other. It fades by opacity alone after an idle wait, comes back on a pointer move, a hover or a keyboard focus, and stops animating under reduced motion. Escape leaves only when nothing else spent it (`defaultPrevented`, `activeOverlay()`, an open menu); a key that has a meaning there (F11) is scoped to the page being shown. Remembered in `sessionStorage` (the mode, Tools and Sidebar), never for good: a fresh launch never opens chrome-less; the restore runs after the file has loaded (`onDomReady`), not inline, where a `const` further down the file threw into the swallowing `catch`. The browser's Fullscreen API is an extra button on the pill, shown only where `document.fullscreenEnabled` | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/docfocus.js` |
| A grip you drag on a canvas (a resize corner, a link's end, a line's waypoint) | A circle or box filled in the thing's own colour and stroked in `var(--card)`, `cursor: move`, and **`transform-box: fill-box; transform-origin: center; transform: scale(var(--wb-inv-zoom))`**, which is what keeps a grip one size to the hand at every zoom (a link's bend grip was the one that did not: 24px across at 2x against 12px at 1x). It takes the pointer only while it is revealed, by selecting what it belongs to or by pointing at it: an invisible grip with `pointer-events: auto` swallows the press meant for the line under it, which has now happened twice, to the mid-line `+` and to the map's own waypoint. Its `pointerdown` stops propagating, or the canvas pans under the drag, and it carries a `<title>` saying both its gestures. Used by `.wb-resize-handle`, `.wb-link-endpoint-handle`, `.wb-link-bend-handle`, `.wb-link-waypoint-handle` and `.wb-link-waypoint-add` (a connector's bends, on every line style: filled, and a hollow ring to add one; a map cross-link keeps `.wb-link-bend-handle`), `.wb-clone-grip` (clone and connect), `.wb-map-edge-handle`; in a document, `.cm-md-image-grip` on a picture in Live (no zoom to undo there, so no scale; 24px on a touch screen; a slider to the keys, DOCUMENTS_PLAN decision 8) | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/mindmapcurve.js` |
| A ring of actions around a canvas item (a radial) | A pie menu: `.wb-map-radial` cut into `.wb-map-radial-slot` **sectors**, never buttons laid on a band (the owner: "not just buttons sitting ontop of it"). Each slot is a button the size of the whole ring, placed with `left`/`top` from `--wb-radial-outer` and **never** with `translate` (the press cue owns it), clipped to its wedge by the `clip-path: path()` `wbFitMapRadialBand` writes, which also clips its hit area; its icon and word are a `.wb-map-radial-face` at the wedge's middle. The ring's `::before` annulus shows through a 1.5px gap and a 1px rim as the dividers. The hole holds the item (`wbSizeMapRadial` sizes it from the item's box) and a ring slid in from an edge pans the board with it, so the hole never loses its item. Hover and focus fill the sector; focus also gets the edge the ring draws (`wbMarkMapRadialSector`), because an outline is clipped away. `role="toolbar"`: the arrows walk the sectors (an arrow with the ring open enters it), Enter or Space runs one, Escape closes and hands the focus back to the board. A menu opened from a sector hangs from the sector's own box (`wbMapRadialSectorRect`), never the button's, which is the whole ring | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/mapradialfit.js`, `scratchpad/ui-sweeps/mapradialmore.js` |
| Any surface that blurs | on the `[data-glass="off"]` list, radius from `--glass-blur`, never a px | `tests/test_ui_recipes.py`, `tests/test_style_scale.py` |
| A control added to the bottom status bar | one of the bar's three zones, in this order: `state` (what the app is holding or doing, left end, the only zone that shrinks), `tools` (the doorways: the palette hint, the agent, the guide, Find, the clock) and `control` (back, forward, history, undo, redo). **A new control goes in `tools`**, which is the only zone that grows, and it grows leftwards from `control`, which owns the right end and has fixed membership. In `tools`, Commands is the one worded doorway; every other doorway is an icon whose word is visually hidden, named by `aria-label` and explained by `title` (INBOX 618, `scratchpad/ui-sweeps/bars618.js`), and the counts in `state` take the item's muted ink at weight 500. Written as `data-status-zone` on a direct child of `#status-bar`; nothing sits in the bar outside a zone. The rule exists because the bar was a flat list and every control added to it was appended at the right end: measured at 1440, that had pushed undo and redo 391px and the navigation group 467px off the end, which is what the owner reported (INBOX 307). Below 600 the bar is not on screen: `dockPhoneStatus` (phone-shell.js) moves Back, Undo and the AI dot into the header, every other control is a row of the header menu through `PHONE_STATUS_ROWS` (the row presses the bar's own button) or, for Reminders, Ask the agent and Guide, the tab bar's More sheet, and the bar comes back only while a job, an activity, offline or power saver is showing, so **a new control also gets a `PHONE_STATUS_ROWS` entry** | `tests/test_status_bar_grammar.py`, `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/uitrio.js`, `scratchpad/ui-sweeps/phonechrome.js` |
| A button | the ramp below: filled (one per surface), ghost, icon-only with `aria-label` | `tests/test_dock_grammar.py` |
| Stepper (a value moved by a fixed unit: a reminder's time by 15 minutes or a day) | `<div class="stepper" role="group" aria-label="Move the time by …">`: a `button.ghost.small.icon-only.stepper-btn` minus, a `.stepper-unit` naming the unit ("15 min"), a plus; each button with its own `aria-label` and `title` ("15 minutes earlier"). One quiet pill (`--btn-quiet-bg`, the hairline as an inward outline so the pill is the buttons' 32px), no dividers; round ghost buttons, the tint on hover and a deeper one pressed. Arrow keys nudge while it is focused, Shift+arrow by the larger unit; the readout it changes fades in (`.stepper-fresh`). Two steppers sit in a `.stepper-pair`, which wraps as a unit | `tests/test_ui_recipes.py` (`test_the_quiet_button_recipe_holds`) |
| A Clear control on a box people type into (Capture, Quick note, Ask, Chat, the popup agent) | `button.ghost.icon-only.small.field-clear.hidden#<box>-clear` with `ph-eraser`, `aria-label="Clear"` and `title="Clear"`, in the box's own foot or row (Capture: `.note-composer-foot`, left of the count; Quick note: left of its action row; Ask, Chat and the agent: right after the field), never a floating control. `frontend/js/field-clear.js` (lazy) shows it only while the box holds something and wipes the words (Capture also its title, tags and staged files); the **Undo** is `toastAction("Cleared.", "Undo", ...)`, or a `.link-button` on the status line where a modal dialog or the agent overlay would cover the toast. Undo puts the words back in front of anything typed since. Escape is not touched | `tests/test_field_clear.py`, `scratchpad/ui-sweeps/` (session scratchpad) |
| An icon beside words (a button, a chip, a badge, a menu row, a facts line) | the label grammar, `setLabel(el, "ph:icon Words")` (or `<i class="ph ph-icon ph-lead">` before words in markup): the host is a flex row with `align-items: center` and a `gap` token, the icon `line-height: 1` at 1.15em. **The icon lands on the words' cap-height centre, in whatever font the page is drawn in** (INBOX 592). This is the one vertical target for an icon beside words, chips and badges included: every sweep measures against it (`iconalign.js`'s `cap`, `badgealign.js`'s `dy`), and the x-height band INBOX 503 measured against is retired (it read a cap-aligned icon 1.5px high on a skill's facts and asked for the wrong fix). A flex row centres the words' box, whose middle is the font's ascent-and-descent middle: on the capitals in DejaVu Sans, 0.064em above them in Segoe UI, so every earlier fix measured right in the sandbox and high on Windows. `measureLabelOptics` (settings.js) reads that gap from the live font into `--ph-cap-dy` and `.ph-lead`/`.ph-trail` move by it (`translate`, which an inline icon ignores: in running text `.ph`'s `vertical-align` already puts it there from the baseline); `--ph-ink-dy` corrects the few glyphs whose ink is off their em box's centre. Every fact on one line is untrimmed words, so they share a centre. Never `text-box` on a label's words, never a per-family `translate` on its icon | `tests/test_icon_label_align.py`, `scratchpad/ui-sweeps/iconalign.js` (`FONT=segoe` draws in Segoe UI's vertical metrics) |
| A chip | `.chip`; a chip is a fact, never an action (an action is a button). **A fact has no edge and no hover** (WORLD_CLASS_PLAN 1.2); a chip you press is `chip(text, cls, onClick)`, a `.chip-interactive` with a button's role, and any edge or hover tone it takes is written on that class, never on `.chip` (`tests/test_consistency_contract.py`; two keep an edge by decision, the label recipe and a suggested tag, `META_EDGED`). **Its words are always a `.ph-text` span** (`chip()` wraps bare text), never trimmed (INBOX 592: words trimmed in a chip and untrimmed beside it, the date on a note's facts line, sat 2px apart in Segoe UI); its icon is the label recipe's (the next row), one `--space-1` gap between them, a `:where(.chip)` height floor of 1.125rem that every family's own floor beats. A new chip family states its own floor if its height was its line box. Never a hand-set `translate` on a chip's icon | `tests/test_badge_recipe.py`, `scratchpad/ui-sweeps/badgealign.js` (every chip family by ink at 3x: the icon against its words' cap-height centre, icon and words against the chip's centre, gap, padding, rows of chips; `badgetry.sh` tries a stylesheet in another UI font first) |
| A board or a map drawn large in a dashboard widget | `dashMapFeature(board)` (dash-boards.js): one `button.dash-board-feature`, the whole picture the press, the picture from `mapPreview(board, {size: "card"})` and nothing else, its height from `dashMapFeatureHeight` (the map's natural height at the widget's width, at least 96px, at most 168px for a map of six topics or fewer and 320px otherwise, fitted whole past that), the name and `mapCountLabel` under it in the rows' own type. The widget's body does not scroll (INBOX 553(d)) | `tests/test_dash_map_feature.py`, `scratchpad/ui-sweeps/mmdoc1005-dashmap.js` |
| Another surface of the app embedded in somebody's text (a board or a map as an object in a note or a document) | one `.note-embed` frame, the same dashed frame a transcluded note wears, because the reader has to be able to see that this is not their own writing. Inside it the whole card is one `<button>` (`.board-embed-open`, padding on the button rather than the frame, or the press stops short of the edge it is drawn inside), the picture comes from `mapPreview(board, {size: "card"})` and nothing else, the facts line is `.library-file-meta` carrying `mapCountLabel`, and the reference is written by `boardEmbedMarkdown` so the "/" menu and the board's own "Add to a note" cannot spell the same object two ways. **A target that is gone leaves a tombstone**, `.board-embed-gone` naming what was there, never a card that quietly disappears: the reference carries its title for exactly this. And a miss is not a tombstone until the index has been refreshed once (`loadMapBoardIndex(true)`), because a board made a minute ago is missing from an index built before it | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/noteobject.js` |
| A fact on a facts line that is also the way in (the picture card's reading) | `.library-chip` on a `<button>`, sitting on the line beside the facts it belongs to. It opens the surface where the thing can be read, **never the card it is on**: a 180px tile has no room to hold a transcription, and a `<details>` that tried took the card from 240.7px to 416.3px and set the height of its five neighbours with it (INBOX 279). Its size comes from its own class, because a rule led by a facts line's handle may not carry a `font-size`: that rank is `.library-file-meta`'s alone | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/libreadingfoot.js` |
| A dialog's head (any modal or popup panel) | **The Documents AI assistant's head is the reference** (the owner, 2026-09-27: "I actually reallly like the design of the document editor's ai assistant popup panel. especially with the design of the close, history,a nd tooltip buttons"): the title, then its `data-help-for` '?' right beside it, then, pushed right, an all-icon group of `button.icon-only.ghost.small.dialog-head-btn` (history or other tools, Close last), each `aria-label`led and `title`d, a visible `:focus-visible` ring, 32px on desktop and 44px under touch/coarse pointer (`--dialog-head-btn-size`, its own token: `--target-min` drives ~150 other rules across the app, so raising its floor was not this task's to do). Below: a `.tabs-line` tab strip when the dialog chooses a kind (never a pill: the row "A popup that chooses a kind"), one line of description, then the input row with one filled action. `.dialog-head` / `.dialog-head-actions` / `.dialog-head-btn` (08-consistency.css), rolled out to doc-ai, Notifications, Earlier versions, Connections, the bin, Keyboard shortcuts, Tools & features, Meeting notes, Improve writing, Quick sketch, Settings (`settings-close`) and now the chat attach popup (`note-picker-close`), which had neither a name nor a way out of its own before. **A dialog built in script takes `dialogHead(title, close)`** (selection.js, INBOX 548): the notebook pickers, How are these connected, Manage this connection, Manage groups, Review the map, Export this board and a map's facts; the confirm alert's `row confirm-head` is left only to `promptDialog` (a question), held by `CONFIRM_HEAD_DIALOGS`; `scratchpad/ui-sweeps/dialogheads.js`. **Sticky in a scrolling card** (C12): `.modal-card > .dialog-head` is `position: sticky; top: 0` on `--modal-bg-opaque`, its rest position kept by a negative top margin and matching padding of `--card-pad-y`; `scratchpad/ui-sweeps/dialogheadsticky.js` (Statistics head 17px at rest and after a 400px scroll, was -383). **One row at every width** (INBOX 552): the actions never wrap or shrink and the title gives way with an ellipsis first (08-consistency.css, overriding a card head row's wrap); the same for the writing Suggestions panel's head, whose Dictionary and dock side sit in its ⋯; `scratchpad/ui-sweeps/headrow.js` (every head's buttons on the title's centre line at 390 and 1440) | the dialog-head ratchet in `tests/test_ui_recipes.py` |
| A search field with a leading icon (a real input that filters in place, not a fake field that opens a dialog like `#dash-find`) | `.search-field` (the well: border, ground, inset, one `:focus-within` ring) holding a `.search-field-icon` glyph and a `.search-field-input`, which turns its own box off so there is one field, not a box in a box (with two classes, `.search-field > .search-field-input`, at rest, hover and focus: one class lost to `input[type="search"]` whenever the field was not focused and drew a second, offset box, INBOX 485) ("the bar is the field", the Finder's recipe, 07-whiteboard-misc.css). Generalised from the Web panel's `#web-query`/`#web-stop`-keyed `.web-search-field` (03-dashboard-widgets.css) when the chat attach popup needed the same shape and a second copy keyed to new ids would have been the wrong fix; the Web panel keeps its own ids for now, unmigrated | `scratchpad/ui-sweeps/chatattach.js`, `attachkeys.js`, `tests/test_ui_recipes.py` |
| What a search box suggests as you type (every box that carries `data-search-scope`; the Brief 86 owner question "should searches suggest auto completions??"; CHAT_PLAN decision 69) | **The suggest list**, `search-suggest.js` (lazy: the first focus of a scoped box loads it): a `.search-suggest` card lifted to <body> under (or over) the field, opaque, holding one `role="listbox"` of rich picker rows (`richPickerRow`, grouped Recent searches, Notes, Tags, Categories under `richPickerGroup`) and, only when a recent search is shown, a foot with one `.link-button` "Clear recent searches" and the key that removes one. The box stays focused (a combobox): Down and Up light a row, Enter takes a lit row and otherwise leaves Enter to the box, Escape closes the list before anything behind it, Shift+Delete removes a lit recent search. **Ghost text** is the rest of the best completion (`.search-suggest-ghost`, the muted colour, fixed over the box line, aria-hidden), taken by Tab or by Right at the end of the words. A recent search carries its own pointer-only x (`aria-hidden`, never a button inside an option) and the foot is the keyboard route. Recents are `searchRecent` in prefs.js, one list per scope (the notes boxes share one), kept on this device; Settings, Import & export, Clear and forget clears them everywhere. Suggestions come from the notes already in the page, never fetched, and one switch (Settings, General, Search) turns them off | `tests/test_search_suggest_lists.py`, `scratchpad/ui-sweeps/searchsuggest86.js` (1440 and 390: rows, ghost text at the caret, the keys, Escape order in Find anything) |
| A Settings change, or a clear, that can be taken back (the owner 2026-10-11: "undo thing in settings??"; Brief 86 c) | **Nothing per control.** Every change is noted from one place: the `apiJson` wrapper in status.js hands each `/preferences` answer to settings-data.js (lazy), which diffs it against the last (`settingsPrefsSeen`) and reads the look settings from its `ui_state` copy (`noteSettingChange`). One notice carries the Undo for ten seconds; the control's own toast, found by its running enter animation, makes way for it. The last twenty are kept on this device and listed in Settings, Import & export, **Recent changes** (`#recent-changes-list`: the words, when, one quiet text action from `rowActions` that turns into Do again, never wrapping, an undone row struck through); a value that was never set or is too big to keep is listed with "can't be undone", never a dead button. A clear (Clear and forget: `.setting-row`s, each saying what it removes and how much in its own line) goes through `settingsClearDone`: `offerUndo` for ten seconds plus its row in the list. Undo and Redo are `settingsHistoryApply`, which sets `settingsHistoryBusy` so its own write is not noted again | `tests/test_settings_recent_changes.py`, `tests/test_clear_app_cache.py`, `scratchpad/ui-sweeps/settingsclear86.js` (1440 and 390) |
| A popup window or panel (a dialog, a sheet, a floating panel, a popover: the owner, 2026-10-03, INBOX 456: "make sure all the popup windows and panels are the same design and style") | **Three tiers, each with one shell, and the head above for the first two.** **Dialog and sheet** (a scrim, a head, a way out: `.modal-card`, `.space-dialog`, `.sheet-card`, the two palettes): `--radius` (a sheet's bottom corners 0), a 1px `--glass-border`, `--glass-shadow`, `--card-pad-y`/`--card-pad-x`, the dim behind it is `var(--scrim)` and nothing else (it was four values, and Find anything painted the opaque page and hid the app), an inset of `--space-8` from the window at every width (a native `<dialog>` is `max-width: calc(100vw - 2 * var(--space-8))`, so it is the same width as a `.modal-overlay` one on a phone), and a small dialog is `min(34rem, ...)` unless it names its own width. **Panel** (floats over the page with no scrim and still has a head and a way out: the notifications panel, the agent activity panel, the node popup, the guided tour's card, the board overview, the Attach picker): `--radius`, `--panel-pad` (`--space-5`) on every side, the same head. **A multi-select picker** (the Attach picker, INBOX 467 and 485) is that panel at one height for every source, with a `.seg` of sources (each tab carrying a count of what it holds), a `.search-field`, and rows drawn by one renderer (`notePickerRow`): a leading tile (`richPickerTile`, the file's own glyph) or the picture, the name over one muted line of facts (a note's category is a dot in its own colour and quiet text, `.note-picker-category`, never a filled chip; then when, size, where it is used), and a check ring at the right edge that fills with the accent when the row is on, the row taking `--accent-soft`; the real checkbox is in the row, visually hidden, so Space ticks it. Pictures are a grid of the pictures. The list is one tab stop: arrows walk it (and the grid by its columns, and the tabs), Enter is Done, Escape closes. Loading, empty (with its one action) and "showing 60 of N" are rows in the list's place. The dialog footer (`.space-dialog-actions`: the count at the left in quiet text, a ghost Clear, the one filled Done); on a phone it is a sheet of fixed height with the strip on one row. **Every dialog's foot is that row** (INBOX 599, the popup census's foot fields): `row right space-dialog-actions`, `small` buttons (the confirm alert's 32px, 44 under touch), ghosts first and the one filled action last, at the right; a bulk-action row above a list (the bin's Restore) is a toolbar, not a foot. **Popover** (anchored to what opened it, no head, no way out of its own: menus, the help popover, the chat model panel, the clock, a '?' panel): the one popover shell, `--radius-lg`, because it is the smaller surface. **The head is `.dialog-head`** for all of the first two tiers: the title is `.dialog-head-title` (16px, 600, `--ink`, on any tag: `.card h3` is the 12px uppercase eyebrow and a head written as an `h3` or a `strong` used to inherit it), its '?' and every utility and the Close are `.dialog-head-btn` (32px, 44 under touch), **Close last, always an icon**: a worded Cancel in a head (the skill runner's) is the X, and a form's own Cancel stays in its foot as well. A small dialog's markup is `<div class="dialog-head"><h2 class="dialog-head-title">…</h2><span class="dialog-head-actions"><button … data-close-dialog="id">`. `openSheet` stamps all of it on every sheet. Not tiers on purpose: the welcome wizard (it is slides, not a head), the confirm alert (a question and its answers), the Ctrl+K palette (an input and a list), the lightbox (a media viewer on its own dark ground, 82% black, with a round white X: a picture is not a card) and the in-page columns (Ask history, the notes rail, the Web panel, the board's Library), which are cards in the page and keep the panel-head recipe | `tests/test_ui_recipes.py` (every small dialog opens with the head; every popup `*-close` is `dialog-head-btn`, with the in-page closes frozen in `IN_PAGE_CLOSE_DRIFT`; the last declared radius of every dialog and panel is `--radius`; the panel tier is padded `--panel-pad`; every dim is `--scrim`), `scratchpad/ui-sweeps/popupinv.js` (42 surfaces at 1440 and 390, light and dark; `popupcmp.py` counts the distinct values per property), `scratchpad/popup-inventory.md` |
| A panel head inside a card (a title with something to do beside it) | `h3.panel-head`: **a title, never the eyebrow** (row 1586: `--text-body`, 600, `--ink`, the dialog title's voice; the board's `h3.wb-sidebar-title` too; a label over one group inside a panel, such as the document sidebar's Linked from, stays the `.card h3` eyebrow); identity, then **at most one** chip, then an all-icon `aria-label`led action group; the row is `nowrap` and the chip is the only zone that may shrink (it ellipsises, with the whole phrase on its `title`). Every ancestor between the chip and the card needs `min-width: 0` or the head simply grows past its column | `tests/test_ui_recipes.py` (`test_a_panel_head_is_a_title_and_not_the_eyebrow`), `scratchpad/ui-sweeps/askhead.js` |
| A side pane that searches and reads (the chat tab's Web panel) | The `h3.panel-head` recipe whose one fact is a state **dot** (`.web-engine-dot`, `role="img"`, its words on the `title` and the `aria-label`, never a chip) and whose actions are a `kebabMenu` of the engine's commands and the close; one `.web-search-field` well holding the glyph, the input with its own box turned off (the Finder's "the bar is the field") and a Stop that shows only while something is loading, Enter searching and ArrowDown handing the focus to the list; results on the list-row recipe (a letter tile for the site, never a fetched favicon, then source, title and snippet, one kebab that is also the right-click); and a reader that is the pane's **one** scroller: a back link and the address's tools over the title, one action row of the filled primary and icons, and the page as prose at `--doc-measure` with no box drawn round it. Ctrl+F there is the app's find bar scoped to the page (`openGlobalFind({scope})`), not a second find | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/webpanel.js`, `scratchpad/ui-sweeps/webpanelflow.js` |
| A list row you can act on without leaving the list (a finding in the writing panel) | the row is a `<li>` holding a head row and one `.doc-prose-answers` box: the control carries `aria-expanded`, the row takes `aria-current="location"` and is painted from it, one row is open at a time, the answers are the same controls the matching popover draws (one builder, never a second set), and the open row is brought into view with the list's own `scrollTop`. A list row never opens a popover over the content it is about | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/prosepanel.js` |
| A sidebar row (a left rail: Notes categories, Chats, the Documents list, the Settings sections; INBOX 702) | hover is neutral, `--row-hover-bg`, never an accent tint; the current row may carry the accent, `--accent-soft`, and hovering it changes nothing (a rail may add its own edge or title colour, never a second fill); the row's ⋯ is a plain ghost icon: no fill at rest or while the row is hovered, `--ghost-btn-bg` only under its own pointer, drawn at `--radius-md` so the fill stays inside the row (the one rule in `08-consistency.css`). The Documents rows are cards with a resting `--surface-2` fill and keep their own hover tier. Measured before: Notes hovered an accent tint, Chats 6% ink, the Settings list `--accent-soft` | `tests/test_ui_recipes.py` (`test_a_rail_row_hovers_neutral_and_the_current_row_is_the_only_accent`, `test_every_rail_is_a_known_rail`, `test_a_rail_rows_menu_is_a_plain_ghost_icon_that_fills_on_its_own_hover`) |
| Overflow and menu icons (INBOX 706) | `⋯` (`ph-dots-three`, the meatball) is an item's overflow in a horizontal row, a card or a bar of controls, and is `kebabMenu`'s default; `⋮` (`ph-dots-three-vertical`, the kebab) is the overflow at the end of a row in a vertical list or in a narrow column, asked for with `kebabMenu(items, label, { vertical: true })` (the rails' rows, Manage categories and tags, reminders, packages, the connection and type lists, the board sidebar's head); `⊞` (`ph-dots-nine`) only switches between apps or spaces and `☰` (`ph-list`) only opens navigation: the app has neither yet, so neither is drawn, and the Cards/Rows toggle's second state is `ph-rows`. The circled and outlined variants of the dots are not used, and the dots mean overflow and nothing else (a dashed line is `ph-rectangle-dashed`, a section break `ph-asterisk`). Other glyphs that mean two things today, left as they are: `ph-squares-four` (a board, the card view, Widgets, three columns), `ph-columns` (split preview, two columns, distribute across), `ph-rows` (the list view, narrow and wide, one toolbar row, distribute down), `ph-list-checks` (a plan, the evidence, background tasks, the All filter) | `tests/test_icon_conventions.py` |
| AI and agent icons (INBOX 723) | One glyph per meaning, from the table under Icons: `ph-sparkle` is the AI doing a thing for you (describe, read, Ask, suggest, draft, rewrite, file by meaning, the "AI off" mark with its slash); `ph-strategy` (a play drawn up, then made) is the agent, which plans and acts in steps on your behalf (Agent mode, the popup agent, Agent activity, a run), drawn only in the places the lint lists; `ph-lightning` is Skills; `ph-magic-wand` is tidy or fix by rule, no model (Fix all, Autocorrect, a map's auto alignment); `ph-brain` is what it remembers; `ph-asterisk` is a section break. `ph-robot` and `ph-star-four` are not drawn. A new AI control takes the sparkle, a new agent surface is a line in `AGENT_ICON_PLACES` | `tests/test_icon_conventions.py` |
| A ⋯ or ⋮ that opens a menu (INBOX 722) | `kebabMenu` gives its opener the one class, `kebab-opener`, and `08-consistency.css` styles it once: a plain ghost icon, no fill, edge or shadow at rest, `--ghost-btn-bg` only under its own pointer or while its menu is open, drawn at `--radius-md`. No surface dresses its own ⋯: a note card, a Library line, a chat row, a Documents row and a Settings package draw the same control. Measured before: the Library's lines and cards kept a resting `--shadow-sm` on a transparent button (a visible outline, a dark ring in dark), while the other surfaces drew none. | `tests/test_ui_recipes.py` (`test_the_kebab_opener_is_one_shared_ghost_icon_styled_once`) |
| An icon-only button: a '?' (`data-help-for`), a ⋯, a close, a toolbar tool (the owner, 2026-10-10: "Some tooltip buttons are circles and some are rounded squares. Should they have backgrounds or borders that are visible?") | **One shape**: the corner is `--radius-md`, never a circle; no fill and no visible edge at rest (a `1px solid transparent` border keeps the geometry for high contrast); the ghost tint (`--ghost-btn-bg`) only under its own pointer, while its menu or popover is open, or when it is a pressed toggle. The '?' (`.graph-help-toggle`, `.setting-hint-toggle`, `#wb-help-btn`) is the same button: measured at 1440 before, five '?' were 50% circles beside thirty-five rounded squares, because only the docks' rule gave theirs the corner. A round control is a pill-shaped field or stepper (`--radius-pill`), not an icon button | `tests/test_chat_transcript.py` (`test_every_help_button_has_the_icon_button_corner`) |
| A row of icon-only actions where a finger cannot hover for the tooltip (the graph node panel's footer; the owner, 2026-10-11, INBOX 883 and 884: the buttons "wrap onto like 3 different rows when on phone" and "i have no clue what the buttons do as I cant hover over them") | **Words, then a ⋯**: below 600 or under `(hover: none)` the row is one line, the one or two most-used actions as buttons that carry their word (`ph:note-pencil Open`, `ph:link Link`) and every other action a labelled row in one `kebabMenu` at the row's end, which is the phone's action sheet. Never a row of bare icons that a finger cannot name, and never a second row. The actions are one list (`graphPopupActionList`, graph.js) drawn in either shape, so the two cannot disagree; the icon-only row stays for a pointer, where the tooltip is the label | `tests/test_graph_popup_phone.py`, `scratchpad/ui-sweeps/graphpopupphone.js` |
| A row with a control that shows on hover (a Library line's tick, a rail row's ⋮, a Documents reference's insert and remove) | the control has its icon before it is pressed (an unchecked tick draws a faint check; INBOX 722: a blank square next to the ⋯ read as a broken control) and a `title`; and it never reserves room at rest: a Rows line's thumbnail follows the title and a rail's ⋮ is absolutely placed over the row's right end (the end of the words fades under it, `mask-image`), so the icon, the title and the meta sit at the row's own padding. Measured before: a Rows line's icon 63px in once one row had a picture; a chat's title 34px, a Documents title 33px short of the padding edge with no ⋮ showing | `tests/test_ui_recipes.py` (`test_a_library_row_reserves_no_leading_slot_for_a_thumbnail`, `test_the_library_hover_tick_shows_its_check_and_names_itself`, `test_a_rail_rows_title_takes_the_full_width_and_its_menu_overlays_it`) |
| A diagnostic card on code (an error, a warning or a hint on hover, with its quick fix; the owner, 2026-10-10: "poorly designed and spaced") | The theme's `.cm-diagnostic` in `docCmTheme` (documents.js): a **severity glyph** (a Phosphor character in the kind's ink: `x-circle` error, `warning`, `info`; never the colour alone), the message as the card's one line of ink, the fix **on its own row** under the message, indented to its edge, as a button at `--control-h-dense` (a second fix sits beside the first), `--space-3` by `--space-4` of padding, the opaque tooltip ground with `--radius-md` and `--shadow-md`, and a `--space-1` shift away from the line it is about (the library sets only top and left, so `.cm-tooltip-above` and `.cm-tooltip-below` carry the gap). Measured before: message and fix on one line, a 3px edge the only sign of severity, 1px between the card and its line | `scratchpad/ui-sweeps/doccodevs.js`, `scratchpad/ui-sweeps/docsui1010.js` |
| A popup placed in the window's own coordinates (a menu at a word, a completion list at the caret, a toolbar dropdown) | it is a child of `body` while it is open and goes back on a comment placeholder when it closes, and its position is **set, measured and corrected by the difference** (`docPlaceFixed` in documents.js, `clampToolbarMenu`'s second pass in app.js), never trusted. **And it is anchored to the thing it is about, asked again, never to an element held from the gesture** (INBOX 421 c): a press that moves the caret makes the Live view redraw that line, and a held element is then detached and measures `0,0,0,0`, which put the word menu at the top of the window. `docFindingAnchor` asks the live mark, then the engine's coordinates for the finding's span, and a rect with nothing in it opens nothing; the menu re-anchors on the engine's own update (`docScheduleSuggestFollow`), and a caret the engine has not drawn (`coordsAt(...).offscreen`) is scrolled into view before a popup is placed at it. A `position: fixed` element takes its frame from the nearest ancestor carrying a `filter`, `transform` or `backdrop-filter`, and `.card` carries one whenever the background art is on: measured with the art on, a word menu asked for `left 952` and drew at `1245`, 45px past the right edge of the window, inside a stacking context no z-index could lift it out of | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/spellwide.js`, `scratchpad/ui-sweeps/menuanchor.js` |
| Files dragged in from outside the window (a drop anywhere in the app) | **The drop veil**, `fileDropVeil` in file-drop.js (lazy, `LAZY_MODULES.fileDrop`, loaded by the one `dragenter` stub in settings-wiring.js): a `.drop-veil` fixed over the window inset by `--space-3`, a 2px dashed `--accent` edge on `--radius-lg`, `--accent-soft` for the ground, one `.drop-veil-card` on `--modal-bg` with an icon and one line. `pointer-events: none` so the drag keeps reaching what is under it, **no blur** (the glass-off list), `role="status"` so the line is spoken, hidden when `dragover` goes quiet for 400 ms or on drop/dragend. It takes only drops nothing else took (`defaultPrevented`): a textarea, the whiteboard, a note row and the documents list defend their own. Pictures and PDFs are uploaded `direct` to Images, anything else is imported as a document | `tests/test_file_drop.py`, `tests/test_ui_recipes.py` (`test_the_drop_veil_takes_no_press_and_has_no_blur`) |
| A glass panel over a board or mind map that pans (the owner, 2026-10-12: a trackpad pan "slow and laggy" with a tool panel showing) | **No blur over moving pixels**: a backdrop blur re-samples what is under it every frame, so each pan or zoom step marks the view (`wbMarkMoving`, whiteboard.js: `#wb-canvas-view.wb-moving` for `WB_MOVING_MS` after the last step) and library-lazy.css drops `backdrop-filter` on `.wb-topbar`, `.whiteboard-floating-panel`, `.wb-map-strip` and `.wb-sidebar` meanwhile; a new blurred panel in that view joins the `:is()` list. Measured on a 57-topic map, a wheel step every frame for 2 s, Glass on with a topic selected: 85 frames (p95 50 ms, max 167) to 113 (p95 16.7), the Glass-off figure is 117 | `tests/test_wb_pan_blur.py` |
| One feature drawn on several surfaces (the writing suggestions: the underline, the word menu, the panel, the dictionary) | one name in the copy, one builder per drawn object (`docFindingLine` for a finding: the kind dot in that kind's underline colour, the flagged words, then the reason, in that order everywhere; `docSuggestAnswers` for its answers), and one scope each: the underline says **where**, the menu answers **this occurrence**, the panel answers **the document**, the dialog holds the **standing rules**. No surface does another's job, and a second copy of either builder is how the four came to disagree in the first place | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/prosepanel.js` |
| A list that says where you are in something (an outline, a page strip) | the row you are on takes `aria-current` (`"location"` inside a document) and is painted **from that attribute**, `--accent-soft` plus a weight step, never colour alone and never a fill plus an accent edge (the owner's "accent bar" for the Documents outline, 2026-10-10, was not taken: this row is the recipe); **an outline is a tree**: depth moves the whole row (chevron and text) one step on the row's `--tree-depth`, so a chevron stands just left of its own heading at every level, the fill covers the row, each block's heading is one row with its count on the right edge the rows' own counts end on, and the first block sits on the tab strip; if the list scrolls, the marked row is brought into view by adjusting that box's own `scrollTop`, never `scrollIntoView` (it walks every scrolling ancestor, the page included) | `tests/test_ui_recipes.py` |
| A row in a list | `.timeline-row`'s shape, on `--row-h` and `--row-gap`: a grid of mark, content and actions, the content column the only one that grows, a transparent 1px border so the hairline it gains under the pointer moves nothing, and the ground arriving with the pointer rather than an edge drawn around every row. **A row's actions are one right-hand cell, centred on the whole row** (`align-self: center`) and always shown: never hidden until the pointer arrives, never hugging the card's top corner, and on a phone on their own line below the content rather than over the tick (Settings' templates, skills and personas, Reminders). A row with a mark and a title over one line of facts is the Library's Contents (`.contents-row`, INBOX 496): the mark a 2rem square, the facts `metaLine` | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/badges.js` |
| A note that is only on this device (saved while the server was away, waiting in the outbox) | **The pending note row**: `li.pending-note` at the top of `#entry-list`, drawn by `renderPendingNoteRows` in quick-note.js with the saved card's own title, text and `#tag` chips, one `chip item-label` that says "Waiting to save" (`ph:cloud-slash`, a title that says where it is kept), and **no actions that need the server** (no menu, no buttons). It is redrawn on every write to the outbox and goes when the note is sent; hidden under a filter. Not a toast: a note that is not saved yet has to be seen where the saved ones are | `tests/test_pending_note_rows.py` |
| A long list (hundreds of rows in one scroller) | each row takes `content-visibility: auto` with `contain-intrinsic-size: auto <its median height>` (07-whiteboard-misc.css, beside the board's culling), so a row more than half a window off screen is not styled, laid out or painted, and `auto` remembers the height it last drew at. Never on a row being edited, holding an open `<details>` or holding focus (containment clips what the row paints, and an editor's toolbar menu opens past it); a row's own menus are fine, `kebabMenu` sends them to `<body>`. Built with a date or a number in it, the row uses a formatter made once, never `toLocale*String` per row (each call builds a new `Intl.DateTimeFormat`). And a script that measures many rows reads them all and then writes them all, never both per row | `tests/test_css_invalidation.py`, `scratchpad/ui-sweeps/f2-trace.js` |
| A file attached to a note (a note's own file, a file its text links, a picture staged in Capture, a file waiting for Save, the read-only copy in a document, the graph's panel or the timeline) | `attachmentCard(spec)` in notes-list.js (`fileCard(name, url, size)` for a read-only surface): one `.att-card`, whatever the kind. A tile (the picture, or the kind's glyph on a tint of `--att-tint`), the whole name on up to two lines (`-webkit-line-clamp: 2`, `overflow-wrap: anywhere`, the full name on the `title`; never one line cut mid-word), and one facts line (`library-file-meta att-card-meta`: kind, size, the day it was added). **The card is the button that opens the file** (the lightbox for a picture or a document, a native player opening out under the card for a recording); everything else is one `kebabMenu`, grouped: Open, Download, Rename, Describe with AI (disabled with its reason when `aiIsOff()`), Edit description, Annotate a copy (pictures), Copy as a link, Remove. Rename and Remove appear only where the file is written down (`textarea` + `markdown`, or `attachment` + `onChange`); removing from a note's text offers Undo and deletes the bytes only once nothing uses them. Several cards sit in an `.att-cards` grid. What a click does is the lazy piece attachment-actions.js (`attachmentAction`), off the boot budget | `tests/test_attachment_cards.py`, `scratchpad/ui-sweeps/attachcards.js` |
| A file waiting on the next message of a chat surface (the Chat composer's images, documents and files; the popup agent's files; attach-1026 A1) | `attachmentChip(spec)` in chat-attach.js, the one `.att-chip`: a 2.25rem tile (the picture, or the kind's glyph from `attachmentIconClass` on `--accent-soft`), the name with its extension kept (`.att-chip-stem` takes the ellipsis, `.att-chip-ext` never shrinks, the full name on the `title`), one facts line (`att-chip-facts`: kind and size from `fileKindLabel` and `formatFileSize`, `Uploading 40%` while `state` is `uploading`, the reason when it is `error`), a 3px `progress.att-chip-bar` along the foot only while uploading, and a `att-chip-x` (`--target-min` square, `ph:x`, an `aria-label` naming the file) that is left out while the chip uploads. The chip's `title` says whether anything was saved: a staged file is held in the browser and nothing reaches the app until Send, so removing it leaves nothing to delete. The strip is `.chat-attachments`. Not this recipe: a note, map or selection chip (a one-line `.attachment-chip`), a note's attachment (`attachmentCard`) | `tests/test_ui_recipes.py` (`test_one_attachment_chip_serves_chat_and_the_popup_agent`), `scratchpad/ui-sweeps/attachchips.js` |
| One line of facts about the thing a row or card names | `.library-file-meta` plus a handle of its own: short statements, dot separators, `--text-xs`, `--muted`, one rank. Never a block per fact, which is what all three of the Library's "this needs a redesign" reports turned out to be | `tests/test_ui_recipes.py` |
| A bar of actions for the things you have selected | `.library-contextbar.selectbar`: the count first, every action inside one `.library-contextbar-end` group, and `position: sticky` at `--selectbar-top` so the bar stays with you while the selection lasts. The ground is the accent tint stacked over `--modal-bg-opaque`, never the tint alone: a 14% wash reads right at rest and turns into a window once the list scrolls under it | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/selstick.js` |
| Two versions of the same text, and what changed between them | `docRenderDiff(host, ops)` over `docDiffLines` in documents.js: one `.doc-diff-line` per line inside the app's `.diff-viewer` box, a marker column so every line starts on one edge, unchanged runs counted in a `.doc-diff-gap` rather than printed, `.diff-added` / `.diff-removed` for the ink (the same two colours the chat's before/after card uses), and a `.doc-diff-hunk-head` per change where a change can be kept or skipped. One builder: the history dialog and the AI edit panel are the same object at two moments, and a second builder is how they would come to disagree about what a change is | `tests/test_document_diff.py` |
| Empty state | `.empty-state` with one sentence and one action | |
| An empty line in a small panel (a short list with nothing in it, in a glance panel, a Settings section or a sidebar group) | `p.muted.empty-line` (07-whiteboard-misc.css): one sentence, `--muted`, `--text-md`, start-aligned, `margin: var(--space-3) 0`, no icon; at most one inline ghost action after it. `.empty-state`, a centred block with 2rem of padding, is for a surface whose whole content area is empty; in a 384px panel it pushes the panel's own controls apart. Decided 2026-10-05 (op4-1005, OPEN.md visual-c): fourteen such lines drew in four type sizes (11.2 to 14.72px) and five margins; the agent panel's line, already on `--text-md`, became the recipe. A heading's hint rule in Settings does not pull an empty line up under the heading (`:not(.empty-line)`) | `tests/test_ui_recipes.py` (every `<p id="...-empty">` is one of the two recipes, or named in a list that only shrinks) |
| A mark generated from a name (a persona, the person) | `nameMark(seed, size)` in app.js: deterministic from the name, drawn as SVG from the categorical palette, never fetched. A persona's goes through `fillPersonaMark`; an assistant reply in the chat draws its writer's (saved per turn) through `paintPersonaAvatar`, which keeps the live emblem for the app's own voice. **The person's** is seeded by `userMarkSeed()` (the profile's display name, or "You"), and its holder carries `data-user-mark="<size>"` so `paintUserMarks()` redraws every one of them at once when the preferences arrive or are saved: the chat's own bubbles (`.msg-user-mark`), the Settings head and the profile's head (`.profile-mark`). Never a `ph-user` glyph, an `<img>` or a second builder | `tests/test_ui_recipes.py` |
| A notice: one line the app says about what is on screen (the search index is stale, this answer is mostly the model) | `.notice`, with `.notice-warn` for something worth doubting (08-consistency.css). An icon from the vendored set as its first child, through `setLabel`, then one short line. A notice annotates what is beside it; an error is a toast, help is `data-help-for`, and `.empty-state` replaces content rather than annotating it. Two tones and no more, because a third needs a rule for when to use it. Neither tone uses a warn *fill*: a filled band over an answer reads as a failed answer, and an answer with less behind it than usual is not a failure. Added 2026-09-21 with CHAT_PLAN Phase 1's low-support line, which was the second surface to need one; the first, `.reindex-stale`, was built inline and now uses this | `tests/test_ui_recipes.py` |
| A notice that can be closed (the "No model is connected" lines above Chat and Ask) | The notice's own row with an icon-only ghost button as its **last child**, `class="ghost small icon-only"` and `data-dismiss="notice"` (no rule of its own: it sits after the row's last control, and boot CSS is at its cap), `setLabel(button, "ph:x")`, a `title` and an `aria-label` that say how long it stays hidden. Pressing it hides that one notice **for the app session**, not for good: `sessionStorage` (with a plain Set beside it for a profile that refuses storage, every access in a `try`), never `localStorage`, so a new session shows it again (`dismissAiOffline` in status.js, opted into with `{ dismissible: true }` on `renderAiOfflineNotice`). Only a line that is information rather than a fault gets one: an error is never closed away. Added 2026-10-06 with INBOX 732, the first notice the owner asked to be able to hide. The update bar (INBOX 1440, `showUpdateBar` in update-dialogs.js) is the same recipe in a `.notice` under the top bar, closed for one version through the seen key instead of the session | `tests/test_inbox_732_733.py`, `tests/test_update_bar_1440.py` |
| A reply no model wrote, arriving (Chat, Ask, the popup agent, the Guide; INBOX 1300 C28) | **One reveal**, `replyReveal` in reply-kit.js, run by `replyFinish` when the stream says `composed` (the Guide's offline turn says so too): each block of the reply rises 4px from transparent over 200ms, 60ms after the one before (eight at most), with Web Animations on opacity and translate only; Reduce motion makes it a 120ms fade with no lift and no stagger; Interface animations off, or Settings, Appearance, Reveal replies off (`reply-motion`, on this device), and it appears. A model's reply streams and takes none. Never a surface's own reveal | `tests/test_reply_cards.py` |
| A long block in a reply (a paragraph, quote or code block over 600 characters, such as text read from a picture; INBOX 1300 C08) | `replyFoldLong` in reply-kit.js, the first step of `replyFinish`: **the web fold's look**, a shut `details.agent-step.long-fold` whose `summary.fold-summary` is `ph:text-align-left`, the block's first sentence cut with an ellipsis and its word count; open, the block itself in the same inset panel, capped at `min(24rem, 50dvh)` and scrolling. The words are moved, never rewritten or dropped | `tests/test_reply_cards.py` |
| A code block or a table in rendered markdown (a reply in Chat, Ask and the popup agent, a note's Read view; the owner, 2026-10-27: "can you add a button to toggle wrap text in tables or code blocks??") | **One card head** (`.code-block > .code-bar`: the kind as `.code-lang`, then one `.code-actions` shell): icon-only items first, then worded ones, the ⋯ last. **Wrapping is an icon toggle in the shell, beside Copy**, never a row of the ⋯: `wrapToggle(kind, apply, keep)` in markdown.js builds it (`button.code-copy.wrap-toggle`, `ph:text-align-left`, one `aria-label` "Wrap lines", `aria-pressed` while wrapping, its title "Wrap lines" or "Don't wrap", the pressed state the accent's soft fill), and a press is remembered per kind in the prefs store (`wrap-code`, `wrap-table`) for the cards drawn after it. Code wraps through `.code-block[data-wrap="on"] pre` (`pre-wrap`, `overflow-wrap: anywhere`); a table through `data-table-view="fit"` (fixed layout, cells wrapping), the same attribute its full view starts at, which does not change what the next bubble starts as. Nothing scrolls sideways while it is on. A new switch for the card goes in the same shell as a `code-copy` button, and the one builder is the only place that makes the toggle | `tests/test_wrap_toggle.py`, `scratchpad/ui-sweeps/wraptoggle.js`, `wrapnote.js`, `wrapfull.js` |
| A note a reply names (Chat, Ask, the popup agent, the Guide; INBOX 1300 C07) | `replyFinish` in reply-kit.js, reached by `finishReply` (capture-ask.js) once a reply's words are final: every `#/notes/N` link shows **the citation peek** on hover or focus (`openCitationPeek`, its number slot empty and so not drawn, named "Preview of" the note), and a reply that gives one to three notes carries them under its words as **the document embed's card** (`.embed-card`: a tile, the first line as the title, a facts line, what follows; the card is the one button that opens the note) in a borderless `.reply-notes` panel. A list of more is left to the peek. Never a second peek or card builder | `tests/test_reply_cards.py` |
| A panel the app draws under an answer (the notebook's figures, the calculator; INBOX 1300 C06) | `renderReplyPanel(holder, event)` in reply-kit.js (lazy `replyKit`), from the stream's `panel` event (`reply_panel`, routes_chat.py), sent whoever writes the words (CHAT_PLAN decision 75). The Ask chart's card (`.reply-panel`: an edge, `--radius-lg`, `--space-3`), a head of icon and name with its one way on at the right (a ghost small button), then its content. The figures are `.reply-stat` cards (icon, figure, what it counts, one muted line, a small chart: `.reply-spark`, `.reply-meter`, `.reply-compare`, each a theme token and filled by a transform). Chat draws it as it arrives; Ask and the popup agent once the answer is final, all through `drawAnswerPanels` (capture-ask.js, to `replyDrawAll`). The calculator is the sheet recipe (`openSheet`, name `calculator`): a `.tabs-line.popup-kinds` of two modes, a live `output`, a four-column keypad of ghost buttons with = the filled one, one Tab stop walked by the arrows | `tests/test_reply_cards.py` |
| A chart answering a question (a count or a trend over the notebook) | `renderAskChart` in ask-chart.js (the drawing alone is `drawAskChart`, which also draws a Chat answer's bar of counts from a `chart` stream event under its line): one `.ask-chart` card above the answer it belongs to, a head of the title (what was counted, over what), a quiet total and Save as PNG, then the SVG (bars for a category or a tag, a line for time) and the same numbers as a `<table>` in a "The numbers" fold. Every mark takes its colour from a class (`.ask-chart-bar`, `.ask-chart-line`, `.ask-chart-grid`, `.ask-chart-axis`) over the theme's tokens, never a hex in the script, so both themes hold; the PNG writes the resolved colours onto a copy. The SVG is `role="img"` with a label pointing at the table, which is what a screen reader reads. The numbers come from the records (`POST /charts/question`), never from the model | `tests/test_vision_rows_row11.py` |
| An icon-only control | a `title` as well as an `aria-label`, saying the same thing. An `aria-label` alone answers a screen reader and nobody else: somebody looking at a row of glyphs with a mouse has no way to find out what any of them do short of pressing one. A control that is disabled says why in that title too, since a greyed thing with no reason reads as the app being broken rather than as something not being ready | `scratchpad/ui-sweeps/vibecheck.js` |
| A surface whose data did not arrive | `surfaceFailed(el, what, retry)` in navigation.js, on the surface's own `.empty-state` element, cleared by `surfaceRecovered(el)` on the next good read; `loadSurface(el, what, run)` wraps a loader that throws. Never the empty state, which is a claim about the person's notes that a failed request is no basis for: measured with every request failing, four surfaces said "Your notebook is empty" over a full notebook and the dashboard printed "0 this week". A figure that could not be read is an en-dash with the reason on its `title`, never 0 | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/vibefail.js` |
| A guided tour of the interface (a card that points at a real control, over a dimmed page) | a step in `TOUR_SECTIONS` (tour.js): a selector, a side and one sentence, in a section. The card is `.card.tour-card`, `role="dialog" aria-modal="true"` so app.js's own Tab trap holds focus in it, placed by the window-coordinates rule above (set, measured, corrected, and **measured again every frame the card is up**, `tourWatchFrame`: a control that moves with no scroll or resize, content loading above it or a layer settling, is followed, and a layer drawn anywhere but where it was asked is placed again), flipped to the opposite side and clamped rather than ever covering the control it names, and a step whose element is missing, hidden **or not really on screen** is dropped from the run so the "3 of 7" counter renumbers rather than promising a step that is not coming. **A cut-out is never drawn outside the window**: a hole placed off the page leaves the dim with nothing to surround, which is what a target off the right edge produced (INBOX 280, measured at 2000x1140: `right - left` went negative, `width: -994px` was dropped as invalid, and the cut-out kept the previous step's 708px width at x 2994). `tourSpotlight` checks the clamped box before writing it and answers whether it drew one; when it did not, the card is centred and nothing is dimmed. Each step switches to its target's tab and Notes sub-tab first and then **waits** for the target to be on screen (`tourWaitForTarget`, up to 1.5s of frames), because a tab's content is fetched after `switchTab` resolves and a step measured too early is dropped for having nothing to point at, which from outside reads as a tour that never leaves the page you were on. Which tab is showing is asked of the pressed tab button, never of `localStorage` alone. The dim is a **cut-out**, and it is painted by **four `.tour-block-panel`s around the hole**, not by one sheet and not by a shadow cast out of the hole. `#tour-spot` paints no background and draws only the ring, so the described control is the page itself at full strength; the four panels carry `var(--scrim)`, take the presses so a step cannot be taken out from under its own card, and leave the hole pressable (a tour that says "press Save" and eats the press teaches that Save is broken). **The dim belongs on the panels because that is the only shape a probe can read.** It used to be `#tour-spot`'s own `box-shadow` spread 100vmax, whose reach depended on `vmax` and on its own corner radius inflated by the spread; `tourdim.js` and `test_ui_recipes.py` were both green while the owner photographed an undimmed band three times, because both were checking the four rectangles and the four rectangles were transparent. The panels are laid out from the same box as the cut-out and sized from `max(clientWidth, innerWidth)` so the scrollbar gutter is covered, and `tourdim.js` now walks `elementsFromPoint` over the window. **The step card is opaque**, `linear-gradient(var(--card), var(--card))` on `var(--modal-bg-opaque)`, the app's recipe for a surface whose legibility cannot depend on what is behind it: a plain `.card` is a 55% fill and the dashboard clock read through the step's own text. The way out is visible: an icon-only `.ghost.small` X in the card's head, `aria-label="Close the tour"`, beside the count, with Skip on the actions row and Escape both still ending the same run. **Before every step the tour closes whatever is open over the page** (`tourClearTheWay`: Settings, the palettes, the features browser, the shortcut sheet, every `openSheet` sheet through its own X, open dock menus) **and a control with something else drawn over it is not on screen** (`tourCovered`, five points through `elementsFromPoint`, skipping the tour's own layers): with the Atlas guide open every step used to light the guide instead of its control, which is what "broken on all the slides except the first one" was. A control that moves behind another one at a narrow width names it as the step's `or`, with an `orText` that says where it went (Settings and Timeline are in More on a phone), and a chrome step that is not drawn at this size at all is left out before the count is written, so the counter never changes mid-run. **On a phone the card is a sheet**, the window's width less its gutters, docked to the edge away from the control (`tourSheetPlace`). Keys aimed at a field outside the card are the field's, because the lit control can be typed in. A new subject is a section in that one table (the replay buttons in Settings, help and guide build themselves from it), never a second tour. **Sections chain and walk in** (INBOX 398): every main feature has a section of three to five cards on its own controls, never on its tab button; a run starts at a section and plays every later one, the count is per section ("Graph", "2 of 4"), and a section's last card offers "Next: Chat" as the primary with Finish as the ghost. A step says what it needs rather than doing it by hand: `tab`, `notes`, `library` (a sub-tab), `wb` (the boards list, or the newest board or map opened, never one made), `settings` (the modal opened at a section and kept open for that section's steps only), `need` (a question about the notebook, settled as the section starts so its count never changes), `unless` with `unlessText` (what a card says instead when that answer is no: the maps section with no map says so on its one card) and `media` (a step that exists on one side of a breakpoint). A control inside a closed `<details>` counts as hidden (a dock folds controls into its ⋯ below 1100 and 600, and the folded list keeps a layout box while nothing is painted), so such a step names the menu it folds into as its `or`, with words that say so; a settings step opens the `details.settings-fold` its control is in, and the tour folds it again when it ends | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/tour.js`, `tourdim.js` (the dim is painted, at every point), `toursteps.js` (every step of every section at 1440 and 390); `tour.js` walks every step of every section at 1440x900, 1184x760 and 390x844, with overlays open, a resize across the phone breakpoint and typing in the lit control |
| Two panes showing one document (a source pane beside its rendered pane) | the two are kept on the same place by a **line-to-block map**, never by a scroll fraction. `renderMarkdown` (navigation.js) stamps every block it draws with the source line it came from (`data-src-line`); `docScrollAnchors` (documents.js) pairs each stamp with that line's top in the editor (CodeMirror's `lineBlockAt`, which answers for the whole document, not `coordsAtPos`, which answers null off screen) and the block's own **rect, corrected by the pane's rect and scroll**, in the preview, never `offsetTop`, which is taken from the nearest positioned ancestor and ran 218px past the truth at 1440, 230px at 1024 and 146px with the sidebar collapsed (INBOX 281); the sync interpolates between the two nearest pairs and carries the end segments' slopes outwards. The stamps count lines in the string the preview rendered, so the title prefix and the stripped frontmatter are undone through `docPreviewLineShift`. A fraction is exact at both ends and wrong in the middle, because a picture is one line of source and four hundred pixels of preview and every such block shifts everything below it in one pane only: measured on a five-section document, the preview was 282, 292, 266, 404 and 550px out at the five headings, growing downwards. With the map: 0, 75, 0, 0, 0. The fraction stays as the fallback for a surface with no line map of its own | `tests/test_ui_recipes.py` |
| Line numbers beside text (Capture, the note edit form, the documents editor; INBOX 590) | An editor view numbers itself: `lineNumbers()` and `highlightActiveLineGutter()` (`docCmGutter`, `noteSurfaceGutter` in documents.js), styled once in `docCmTheme`; a plain textarea gets `mountGutterFor`'s `.doc-gutter`, which only copies the box's row metrics. Either way: no box of its own (no border, radius or fill), figures at 0.8 of the text (`--text-xs` in the textarea column) in muted tabular figures, right-aligned, each on its line's baseline, and the caret's line in the body ink while the box has the focus. Never a second column beside an editor that numbers itself | `tests/test_line_gutter_look.py`, `scratchpad/ui-sweeps/gutter.js` |
| A bottom panel under an editor with tabs (the code editor's Output, Problems, Tests, Console and Debug; the owner, 2026-10-10: "the code ide and its panels need a design fix") | **One compact head row**, the dock recipe (`.cm-run-head.dock`): the tabs left as `.tabs-line`, the run's state as a **chip** after them (`.cm-run-status`: a fact, no edge, no hover, absent when empty), the actions right as **icon-only ghost buttons** whose words are the `title` and `aria-label` (never worded buttons: eight of them wrapped the head onto a second row). The head is a strip under the panel's own top edge, not a second boxed bar. The body is padded, and **an empty pane says what fills it** (`data-empty` on the log, drawn by `:empty::before`), never a blank slab. **The console is one line**: the prompt, then a borderless field in the editor's face (`--mono`, 0.92rem) at `--control-h`, with `--space-1` above and below it so its 2px ring never meets the rule over the line (INBOX 804), under the log (the app's field rule used to outrank it: a 42px bordered box). The footer and the keys line stand on the editor's column (`--doc-code-cap`, a registered length taking the editor's own `78ch`), and a code file's keys line names code chords, not bold and italics (`.doc-hint-code`, shown by `#tab-documents.doc-is-code`) | `scratchpad/ui-sweeps/ide-shell.js`, `scratchpad/ui-sweeps/docsui1010.js` |
| A syntax error or a completion list in a code document | CodeMirror's own linter, lint gutter and completion list, mounted by `docCodeTools` (documents.js) for code types only and never in Plain, and restyled in `docCmTheme` onto the tokens: the underline is the prose findings' wavy line in the kind's ink (`--error`, `--warn`, dotted `--muted` for a note), the gutter mark a dot in the same ink outside the line numbers, the hover and the list on `--modal-bg-opaque` because words laid over code must not read through, the chosen row `--accent-soft`. Checked where a real parser is: the browser for JSON (`docJsonErrorAt`), JavaScript, TypeScript and CSS (the Lezer tree), the server for Python, TOML, XML and YAML (`POST /documents/check-syntax`); never by running the file. **A fix for one** is an `action` on its diagnostic: drawn by the hover card as a `.cm-diagnosticAction` button on `--accent-soft` (never the library's dark slab), and listed at the caret by Alt+Enter through `openMenuAtPoint` with the two formats beneath, fixes first; never on Ctrl+., which the shortcut registry gives to stopping an answer. A fix is recomputed from the text when chosen (`docCodeFixNow`), never applied from offsets taken at lint time. **Pairs and Enter** are `closeBrackets` and the indent service in the same compartment (`docCodeEditing`), so they follow the file type and Plain exactly as the diagnostics do. **The list opens as you type** in a code type (`docCompletionExtras`, same compartment; prose keeps an inert completer): the language's own rows, Emmet rows in HTML where markup starts a line or follows a tag and in CSS where a declaration starts (detail "Emmet", the expansion previewed in `.cm-completionInfo` on `--modal-bg-opaque`), and after a CSS property's `: ` that property's own values only. The chosen row's rest is drawn after the caret as `.cm-ghostText` in `--muted`, taken with Tab; Enter stays the list's, Escape closes both. **A colour value** in CSS (and an HTML file's `<style>`) has a `.cm-color-swatch` before it, found from the tree: 0.8em square in the colour on a `--border` hairline at `--radius-inner`, and a click opens the browser's own colour picker, the pick written back in the value's own form (`docCssColorFormat`). **A name's one line** (a CSS property, an HTML element or attribute) is on the diagnostics' own hover card as `.cm-hover-doc`: the name in code type, the line in `--text`, a property's values in `--muted`; the lines are this app's own words (`DOC_HOVER_*`), never MDN's. **Indentation guides** are a `--border` hairline at the left edge of each indent step of the leading whitespace (`.cm-indent-guide`, one mark per step, never stepped in `ch`, which is not the code face's space); **bracket pairs** take `.cm-bracket-0` to `-2` by depth, `--accent`, `--syntax-keyword` and `--warn` each mixed 70% with `--text`, and a bracket in a string, comment, regex or HTML text is not one. **A code file's outline and breadcrumb are its symbols** (`docCodeSymbols`, the headings' own shape and rows), which jump and never move. **Sticky scroll** pins the enclosing scopes' first lines as `.cm-sticky`, an overlay on `--modal-bg-opaque` with a `--border` hairline and `--shadow-sm`, laid over the scroller rather than a panel (a panel resizes the scroller and the text jumps), each row column for column over the code. **Run** (`#doc-code-run`, a ghost small button beside Format, Ctrl+Shift+Enter) opens `.cm-run-panel` under the editor: a head row of ghost small worded buttons (Run again, Stop, Clear, Close) with the status in `--muted`, an HTML file's page in a sandboxed frame above a code-type log, rows on a `--border` hairline, errors and warnings in `--error`/`--warn` on their soft grounds, each row's `Line N` a link back; the code runs only in `/documents/run-sandbox` (`api/run_sandbox.py`), never in the app's own origin. **Format** is one ghost `#doc-code-format` button in the document's dock, shown for code types where the markdown strip is hidden (the two swap in `syncDocFileType`), with Shift+Alt+F and a palette row reaching the same `docFormatCode`: refused with a toast naming the line when the file does not parse, one undo step when it does | `tests/test_ui_recipes.py`, `tests/test_syntax_check.py`, `tests/test_code_editing.py`, `tests/test_code_completion.py`, `scratchpad/ui-sweeps/doccode.js`, `scratchpad/ui-sweeps/doccodeedit.js`, `scratchpad/ui-sweeps/doccomplete.js`, `scratchpad/ui-sweeps/doccodevs.js`, `scratchpad/ui-sweeps/doccodevs2.js` |
| Text the editor writes for you in a prose document (an expansion, a shortcode, a closing pair) | one more row kind in the prose list that already exists (`#doc-complete-list`, `renderDocComplete`), never a second popup at the caret: `li.doc-complete-fill` with the trigger in `<b>` and what it writes as `.doc-complete-detail` in `--muted` at `--text-xs` (a shortcode leads with `.doc-complete-glyph`), expansions above word rows; the chosen row's first line drawn after the caret as the code side's `.cm-ghostText`; Tab takes any row and **Enter only an expansion** (a guessed word never takes Enter). A trigger that is also a common word (`now`, `date`, `todo`, `hr`) counts only on a line of its own; `lorem` and `:shortcode` count anywhere. The strings are the `PROSE-FILL` region of documents-prose.js, pure, run in node. Pairs and smart punctuation are one `inputHandler`, never inside code, smart punctuation off unless Settings, Preferences turns it on | `tests/test_prose_autofill.py`, `scratchpad/ui-sweeps/proseautofill.js` |
| A menu that inserts a block where you are writing (the "/" menu, in every editing surface) | the one `#editor-menu` popup (editor.js): a `#editor-menu-list` listbox of rows from `editorBlockRows`, grouped in `EDITOR_GROUP_ORDER` (Recent, Basic, Structure, Callouts, Media, Embeds, Advanced, AI, Templates) under pinned `.editor-menu-group` headings; a row is the shared rich picker row (`richPickerRow`, rich-picker.js: `.rich-picker-tile` for the icon, `.rich-picker-label` over one `.rich-picker-about` line, and the markdown it writes as `.rich-picker-keys`); `#editor-menu-preview` beside the list from 44rem renders the row's `sample` through `renderMarkdown`, inert. Search is `editorFuzzyRank`; arrows, Home and End, Tab and Shift+Tab between groups, Enter, Escape; the pointer moves the highlight only when it moves. A block needing a second choice asks in the same popup (the code block's `` ``` `` language step), never a dialog. A new block is a row in `editorBlockRows` plus its spelling below, in notes and documents alike unless it needs a document to mean anything | `tests/test_md_blocks.py`, `scratchpad/ui-sweeps/slashmenu.js`, `scratchpad/ui-sweeps/slashicons.js` |
| A block in somebody's markdown (a callout, columns, a contents list, a rule, a cited quote, display maths, an embedded document) | a spelling any other markdown reader shows legibly (`> [!kind]`, `:::columns`, `[TOC]`, `***`, `> -- Name`, `$$ $$`, `![[Title]]`), parsed only in the `MD-BLOCKS` region of app.js and drawn by its one builder (`mdCalloutElement`, `mdColumnsElement`, `mdTocElement` and `mdFillTocs`, `mdRuleElement`, `mdQuoteElement`, `mdMathElement`, `mdDocumentCard`), which the note card, `renderMarkdown` and the document's Live view all call, each passing its own text renderer. A callout kind is a row in `CALLOUT_KINDS` (icon, label, one line, aliases) and one ink in 05-sidebars-themes.css set as `--callout-accent` and mixed from the palette tokens; the tint, edge and icon tile are derived from it. **In the Live view a callout shows its kind once** (INBOX 486): the icon with a caret is the kind picker (`calloutMenuItems`), the first line's own text is the title (the kind's name stands in, muted, only when there is none), `>` and `[!kind]` never show there whatever the caret does (Source shows them), and an empty body carries a hint (`calloutHint`, "Write the note") that is not text; the "/" row writes the kind's name as the title and leaves the body empty with the caret in it. The HTML export's stylesheet (`DOC_EXPORT_CSS`) styles each block too | `tests/test_md_blocks.py`, `scratchpad/ui-sweeps/blocksrender.js`, `callouthead.js` |
| Acting on a rendered block (change its kind, fold, edit, copy, delete) | the block bar (`docBlockBarShow`, documents.js): a solid `.doc-block-bar` of `smallButton`s at the block's top right while the pointer is on it, lifted to body and placed by `docPlaceFixed`; the callout's kind is its own tile opening `calloutMenuItems` through `openMenuAtPoint`, the same list the Live view's `.cm-md-callout-kindbtn` opens. Every change is written through the surface after checking the source line is the block, and a delete offers Undo in its toast | `scratchpad/ui-sweeps/blockbar.js` |
| Spacing, type, radius, shadow, motion | the tokens above; a px in a stylesheet is a lint failure | `tests/test_style_scale.py` |
| A transition, a hover | a `--ui-*` duration for anything of the interface (`--motion-*` only for the decorative surfaces: Atlas, the graph, the whiteboard, the progress indicators) and an `--ease-*` curve on every transition, never `all`, never `box-shadow`; a hover is a colour (`--accent-surface-hover` for a solid button, `--hover-veil` over any other ground), never a `filter` | `tests/test_motion_tokens.py`, `scratchpad/ui-sweeps/f2-hover.js` |
| Motion (a selection that moves, a panel that opens) | **What moves is the compositor's**: `opacity`, `transform`/`translate`/`scale`, a colour, on the `--motion-*` tokens. **A selection** is the one indicator recipe (08-consistency.css, "motion: one sliding indicator for every strip"): the strip's `::before` placed on the chosen option by `glideStrip` (shell-reminders.js) and moved by a `transform` animation on `--ui-slow`; a strip gets it by being a `.seg`, a `.tabs-line` or joining `GLIDE_STRIPS`, and a family whose chosen option has its own corner or fill sets `--glide-radius`, `--glide-fill`, `--glide-ring` there. No inset moves anywhere. **A panel** keeps its column or placement instant and moves only its contents: `aside[data-resizable]`'s children by `opacity` and `transform` toward the rail, a fixed side panel by `@starting-style` from its edge. **A page** fades in from 0.4 (`.tab-page`, `--ui-fast`, `opacity`; never from 0, which is a blank frame) and leaves at once; a heavy page's first visit is one page-sized skeleton that fades as the page does (`tabPlaceholder`). **A popup** fades its scrim in (`--ui-base`) and rises its card a step from 0.985 (`--ui-slow`), one `:where()` recipe for every overlay, and leaves the same way over `--ui-exit`. **A menu or popover** fades and grows from 0.96 out of its opener's corner (`ui-fade`, `ui-grow` 1ms late so no placement measures a transform), closing back over `--ui-exit`. **A press** is `scale: 0.97` and a deeper ground; **a focus ring** eases its colour; **a hover** eases a colour, never a shadow; **a list** settles in where its skeleton was (`.ui-settle`); **a toast** arrives from its edge and the others slide (`toastStack`). **The opening** is one curtain lifted once over a drawn first tab (`curtainShell`), and nothing that arrives late may move what is drawn: a late line keeps its line box, a script-drawn mark its room, a part that comes after a fetch is waited for unseen. **Never** a width or height in motion, nothing on first paint. **Governed by Interface animations** (`data-ui-motion`, the `--ui-*` tokens), not by reduced motion: on, it plays under reduced motion; off, it is instant | `tests/test_motion_recipes.py`, `tests/test_cheap_animations.py`, `tests/test_smooth_boot.py`, `scratchpad/ui-sweeps/motion1005.js`, `sidemotion.js`, `smooth1005-boot.js`, `smooth1005-tabs.js` |
| A notification (toast) | `toast`, `toastAction` or `toastProgress` in status.js. **Two rows** (INBOX 584, 847: "notification buttons are still in line with the x close button"): the first is `.toast-msg` and the close, the second is `.toast-actions` (one wrapper from `toastActions(...buttons)`, never a button appended to the toast itself) under the message and left-aligned with its words, so the close is alone in its corner and no action's box shares its row at 1440 or 390. Each action is `toastActionButton`'s `small .toast-action`, **a quiet text action** (INBOX 811: `--accent-text`, weight 600, no edge and no face at rest, the ghost tint under the pointer or the keyboard; the error toast's Report this the same). Spaced only by the grid's gaps (no part carries its own margin; never a bare link after the words); every control is `--toast-ctl` (`--target-min`) tall and the message's first line is padded to centre on the close, so a wrapped message keeps the close beside its first line; up to 30rem wide, the message `text-wrap: pretty`, so a sentence and its Undo stay one line on a desktop and a wrap never leaves one word alone. **Every action is kept** (INBOX 585): `toastAction(text, label, fn, { go })` records a row in the bell with the same label; `go` is plain data (`{ open: "entry"|"conversation"|"doc"|"board"|"reminder"|"capture", id }`, `{ tab }`, `{ settings, focus }`) re-resolved by id when pressed, so an opener works after a reload; an action with no `go` is one-shot (Done once pressed, Expired after a reload; an Undo only while its `pushUndo` entry is on the stack, or five minutes); `{ record: false }` only for a notice already recorded. It arrives and leaves by fading with 4px of travel (`toast-in`, `toast-out`, on `translate`), and every way out goes through `dismissToast`, never `note.remove()`, so none of them vanishes between two frames. **A toast yields to the focused control it covers** (WCAG 2.4.11): status.js's `focusin` listener puts `is-yielding` on `#toast-box` when a toast overlaps the control Tab just reached, and `#toast-box.is-yielding > .toast` fades to 0.12 and takes no clicks until focus moves off it; the box itself takes no clicks beside a narrow toast below 1100px, only its toasts do | `scratchpad/ui-sweeps/f2-skel.js`, `scratchpad/ui-sweeps/zoom.js` | `scratchpad/ui-sweeps/f2-skel.js` |
| A list whose first rows are on their way | `showSkeletons(list, n)` before the fetch and `clearSkeletons(list)` after it (app.js): the `.skeleton` placeholders at the height of the list's own rows, `aria-busy` while they show, only ever into an empty list; the list's own render replaces them. Never a spinner or a blank card where the shape of the content is known. A dashboard widget mounts with two (`mountWidgetBody`) and they go the moment it draws anything of its own; no body ever says "Loading…" (INBOX 596). A Settings pane's list that fills from a request does the same (Packages, Skills, Tools, Personas, Backups, Privacy, Account: `showSkeletons` before the await, `clearSkeletons` after it, so a failed request leaves nothing busy) | `scratchpad/ui-sweeps/f2-skel.js`, `scratchpad/ui-sweeps/skeletons.js`, `scratchpad/ui-sweeps/settings-skeletons.js`, `tests/test_lazy_skeletons_598.py` |
| A surface whose code or data is on its way (a lazy tab's first visit: Graph, Library, Documents; the dashboard's grid while it fills unseen) | **Its own outline, then its name** (INBOX 598): a lazy tab gets an entry in `TAB_SKELETONS` (navigation.js), a page-shaped set of `.skeleton` pieces built by `tabSkeletonPiece` and `tabSkeletonBar` (a dock, then the graph's canvas and dots, the library's chips and tiles, the documents list and the open page), and past `TAB_SKELETON_NAME_MS` (400) a `role="status"` line with the ring in the dock's middle: "Opening the graph…". The placeholder is stretched over the page (`align-self: stretch`; centred, it shrank to a line across the middle). The dashboard's grid, hidden while it fills, has `dashFillingSkeleton` over its own box; a return to the dashboard keeps what is drawn and swaps each widget in when it has drawn again (`refreshDashWidgets`), never an empty frame. Never one page-sized box, never a word alone | `tests/test_lazy_skeletons_598.py` (a `TAB_MODULES` tab without an outline fails), `scratchpad/ui-sweeps/loading598.js` (4x CPU, held bundles) |
| An animation of anything | `transform` and `opacity`, never `width`, `height`, `top`, `left`, `margin` or `padding`. A bar that fills is a full-width box scaled from a left origin inside a track that clips (`.boot-splash-progress-fill`, 00-tokens-shell.css), never a box that grows: measured, the width version cost 121 layouts for one 2.4s crawl and the scaled one costs none. A box that genuinely does change size with content in it keeps its transition and states the reason in a comment on the line above, as `#phone-tab-dock` does | `tests/test_cheap_animations.py`, `scratchpad/ui-sweeps/animcost.js` |
| Copy | sentence case, no em-dashes, no exclamation marks, one line per section (a Settings pane's own description is at most 88 characters, which is one line at its 68ch cap) | `tests/test_no_em_dashes.py`, `tests/test_settings_pane_intro.py`, `scratchpad/ui-sweeps/paneintro.js` |
| A note's edit form (the Notes list's Edit, INBOX 606) | **One composition on the capture box's recipes**: the title, the formatting strip and the text in one `.note-composer` (edge, ground and focus ring on the surface; the strip's collapsed word hidden, its tools beside Source); a meta row of the tags as `.chip.tag`s in a `.search-field` well with one input (Enter or a comma makes a chip, a press removes one, Backspace in an empty field takes the last; a taken suggestion arrives as "tag, ") and the category as the card's own category chip opening a menu of the categories; a foot (`.note-edit-foot`) with Attach a link as a quiet icon at its left and Cancel then the one filled Save at its right; Related above the foot as a label line and one row per note, the note's words and a quiet + to link it. Below 600 the New note button stays off the form | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/noteeditform.js` |
| A Settings pane's head | **The pane's dock** (INBOX 599): `div.dock.settings-pane-title` as the pane's first child, a `.dock-identity` holding the pane's `h3` (16px 600, the dock title; never the 12px `.card h3` eyebrow) and a `.dock-actions` holding its `data-help-for` '?' last. A pane with no head in the markup gets the same shape from `ensureSettingsPaneTitle` (settings.js). The dock is what sticks at the top of the pane on `--modal-bg-opaque`; the section's index is not in it but in the sidebar, under the pane's own link (the row below, INBOX 622). **A pane that makes things carries its New in the dock** (`button.ghost.small.settings-pane-new[data-opens=<the form's first field>]`, `data-cancel` naming the form's Cancel edit; one listener in settings.js opens the fold and focuses the field), before the '?'; a ghost, because the form's own Add is the page's one filled button; below 600 it is its plus on the title's row with the links under both (Personas, Skills, Templates) | `tests/test_ui_recipes.py`, `tests/test_settings_pane_actions.py`, `scratchpad/ui-sweeps/settingsheads.js`, `scratchpad/ui-sweeps/settingsnav.js`, `scratchpad/ui-sweeps/paneacts.js` |
| A long Settings section's own index (its group heads, for a pane of three or more) | **The sidebar's second level** (INBOX 622, the owner: "idk if this navigation is the right way to go about it"; it was a strip of links in the pane's dock that scrolled sideways, with a scrollbar and a clipped last label): `settingsIndexBuild` (settings-find.js, loaded on the first open of Settings) writes the pane's `h3` group heads as `button.settings-nav-group`s in a `div.settings-nav-groups[role=group]` straight after the pane's own `#settings-nav` link, indented and a step smaller, the Quiet tier. A press scrolls the pane's own `scrollTop` to the head just under its sticky dock (never `scrollIntoView`) and focuses the head; the head you are at is marked from `aria-current="location"` (ink, a weight step and a 2px accent rail at the leading edge, never colour alone and never a second fill beside the pane's), tracked on scroll. **One short block, not a column** (INBOX 698): the block opens with an "On this page" head and a `.linklike` toggle ("Show all N sections" / "Show fewer", `aria-expanded`, remembered per device under `settings-nav-sections`), and shows only the link being read until asked, so an open page pushes the next one down by a few rows, not thirteen (Help: 463px before, 113px). **The sidebar follows the page** (INBOX 680): when the marked link changes `settingsNavFollow` scrolls the sidebar's own `scrollTop` to the nearest edge (smooth only with Interface animations and motion on; never focus; skipped while the pointer is over the sidebar or it was scrolled in the last 600ms). **A group heading ("Help and About") is a label** (INBOX 697): `--text-xs`, muted, no hover, no pointer, and a press on it opens its group's first page. Hidden while the sidebar searches. On a phone the jump list (`#settings-jump`) gains the same groups as indented `pane#index` options under the pane's option, and follows the scroll too. **Nothing in Settings scrolls sideways**: a snippet or command wraps (`.setup-snippet`, `#settings-modal .code-block`) and a fold's name wraps | `tests/test_ui_recipes.py`, `tests/test_settings_no_sideways.py` (no Settings rule scrolls on x; the index is the sidebar's), `scratchpad/ui-sweeps/settingsnav697.js` (heading against row, a press on a heading, row to next row, the toggle), `scratchpad/ui-sweeps/settingsfollow680.js` (the current link stays inside the sidebar), `scratchpad/ui-sweeps/settingsnav.js` (every pane at 1440 and 390: nothing scrolls sideways; a press lands under the dock; the current group tracks the scroll; the jump list follows) |
| The settings a typed word matches (the search field in Settings' nav) | `ul.settings-results` under the field, one `button.settings-result` per setting (its own words over `Section · Group`), capped at eight, rows the Quiet tier; a press opens the section and rings the setting with `flashRevealed`, the way a catalogue row lands. Down from the field walks the rows, Enter opens the first. The section filter above them stays: the two answer different questions | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/settingsnav.js` |
| A model you can download, install or use (the Models screen's suggested downloads, and any model named by hand) | **The model card**, `article.model-card` built by `buildModelCard` (settings-models.js): a surface-3 tile in the group's surface-2 (no border), the name (`h5`), the group's starting pick as a `.chip` beside it, one line of purpose, one `.library-file-meta` line of facts (size on disk, the memory it asks for), what it is good at, the fit chip (`Fits`, `Tight fit`, `Too big here`, estimated from this computer's memory by the server, never in the client), what it is doing now (`Installed`, `In use for chat`), and a foot with **one primary action** (Download, Use for chat, Retry, or Cancel download while it runs) and a `kebabMenu` for the rest (Copy name, Remove). Cards are grouped by purpose under an `h4` and one line, in a `.model-grid`; the group's starting pick is the one filled button in its group, every other primary is tonal. A download shows its progress inline (`progress.model-progress` with a decimal "34% 1.0 GB of 3.0 GB") and is cancelled from the same card. Cards are **kept, not rebuilt, on every poll** (a signature per card; progress updates in place), or the open menu and the focus inside it are lost | `tests/test_ui_recipes.py`, `tests/test_model_cards.py`, `scratchpad/ui-sweeps/modelcards.js` |
| A model named by hand (Download another model) | One field and a Check name button under the cards; the answer is a sentence in `#custom-model-note` saying what the name is (an Ollama library model, a community model, a Hugging Face repository), where it downloads from and any warning, and the card for it, the same card as above, so progress and Cancel are the same. The check is `POST /models/inspect`, the same function `/models/pull` refuses with (`model_cards.inspect_model_name`): no network, no claim of a size | `tests/test_model_cards.py`, `scratchpad/ui-sweeps/modelcards.js` |
| A group head in Settings (the heading that names a whole `.settings-group`, e.g. "Model per feature", "Which ones it may use") | an `h3`/`h4` at `--text-lg`/650/`var(--text)`, sentence case, with a muted `--divider` line under the head (`#settings-modal .settings-group h3/h4`, 01-forms-settings.css). **Not** the `.card h3` eyebrow (12px, uppercase, muted): that recipe is for a minor label under a card's own title, and a `.settings-group` sits inside `.modal-card` so it inherited the eyebrow by descent alone, the same weak style as every subordinate label in the app on the one heading someone's eye has to land on when scanning a long page. **Inside its group**: a head after the pane title stands in a `.settings-group` (or a fold, a dock, the profile head), never loose on the pane (INBOX 464: ten were, at 12px) | `tests/test_style_scale.py`, `tests/test_settings_group_heads.py`, `scratchpad/ui-sweeps/groupheads.js` |
| Words in the accent colour (a link, an accent label) | `color: var(--accent-text)`, never `var(--accent)`, which stays for fills, borders and rings (Colour, above) | `tests/test_accent_text.py`, `scratchpad/ui-sweeps/accenttext.js` |
| The edge of anything you aim at that is not text (a text field, a select opener, a selected segment or option, an interactive chip, an icon on a fill) | **3:1 against the ground it stands on, through tokens only** (WCAG 1.4.11; INBOX 464). A field, a select opener and a suggestion chip draw `border: 1px solid var(--control-edge)` (a step stronger than `--ghost-btn-border`, the quiet button's measured hairline, because a field also sits on a settings group's grey well; `[data-contrast="on"]` makes it `--ink`); its hover is `color-mix(in srgb, var(--accent-text) 60%, var(--control-edge))`, never a pale accent mix, which measured 2.3:1 and was weaker than the resting edge. A selected segment (flat looks) is its 11% fill **plus** `box-shadow: inset 0 0 0 1px var(--control-edge)`; the tint alone measured 1.25:1. A chosen radio option row (`.check-row`, `.provider-option`) carries `inset 0 0 0 1px var(--accent-text)` because its input is hidden and the tint (1.15:1) was the only cue. A tab strip's active tab may rely on a heavier weight instead of a ring. An icon is never dimmed by `opacity` (`.ph-trail` was 0.7 and a muted caret measured 2.8:1): it takes its label's colour, or `--muted`. **Counted apart, a decision rather than a failure**: the borderless writing surfaces (the note title and body, the Ask line, the Writing room's tags and instruction, a document's title) have no edge of their own; the card or composer around them and their focus ring carry them, and `contrastui.js` lists them as `field-bare` so the list stays visible | `scratchpad/ui-sweeps/contrastui.js` (icons, SVG icons, focus rings, fields, checks, toggles, selected states, chips, text outside `.tab-page`; every tab, sub-tab, Settings section and main overlay, 1440 and 390, both themes, `CONTRAST=on`), `tests/test_control_edge.py` |
| The app's mark in an empty state or a head | an element with an id on `EMBLEM_SLOTS` (phone-shell.js), drawn by `renderBrandLogo` (`renderEmblem`, then `emblemArt`): favicon.svg's three hexagon cells, cloned from `#emblem-template` (index.html) on the favicon's tile in the accent's colours (`EMBLEM_COLOURS`); one geometry holds every copy (`tests/test_brand_mark.py`). It moves only by CSS on its own layers (`.emblem-art`, 03-dashboard-widgets.css): the lifted cell settles in once when first shown, then breathes slowly; while the AI works (`syncEmblemBusy`) the cells lift and resettle in turn. Reduce motion or Interface animations off holds the final frame. Never a generic icon standing in for the mark, never a second drawing of it | `tests/test_emblem_slots.py`, `tests/test_brand_mark.py` |
| Atlas, anywhere it is drawn | `atlasAvatar(size, mood)` for head and shoulders, `atlasDraw(size, mood, level)` for the figure (atlas.js), or a `data-atlas-avatar="<px>"` host that `atlasDressMarks` fills, which keeps a plain icon as its fallback in the markup; each follows Settings, Appearance, Atlas style and Atlas look at once. Never a picture of Atlas, which would not follow either. Its gradients live in shared `svg.atl-defs` hosts, so a drawing moved out of the document loses its fill | `tests/test_name_mood.py`, `tools/avatar-lab.html` (every mood, pose and size on one page) |
| The assistant's head on a reply or a guide mark | `paintAssistantAvatar(holder, size)` (chat-agent.js; a reply head goes through `paintPersonaAvatar`, which sends the app's own voice here and keeps every other persona's generated face). It reads Settings, Appearance, Assistant avatar (`atlas`, the default, or `emblem`: the app's mark, `emblemArt` with `head`, assistant-avatar.js, breathing but left out of the lift, still under Reduce motion or Interface animations off) and repaints the open heads when it changes. The same head (`.msg-role.msg-role-assistant`: face, then name) opens Ask's answer (`.answer-title`), the writing room's draft (`.draft-head-label`; static `[data-assistant-head]` holders, `paintAssistantHeads`) and every guide row (`assistantHeadRow`), in the row the old title or label held, so no row grows. Never `atlasAvatar`/`atlasDraw` or a second emblem for a reply head | `tests/test_ui_recipes.py` (`test_an_assistant_head_asks_one_function_for_its_face`) |
| A character on the page (the corner companion) | the one companion, `#nm-buddy` (avatars.js): it chooses its own perch from the page's ledges and obstacles, rides with the panel it is on, and is placed, sized, recalled and hidden from its own menu and Appearance's Corner companion. A new surface does nothing for it: controls (buttons, fields, tabs, links, an editor) are kept clear by `NAME_MARK_BUDDY_NEVER_COVER`, and a new kind of control it must not sit on joins that list rather than moving the companion by hand. **It never sits on the air** (INBOX 582): what it sits, stands or hangs on is asked of the page under it (`nameMarkBuddySupported`: a visible edge within 2px), after a scroll, a canvas pan or zoom, a release, a view change and every 1.5s at rest, and when it has gone it chooses again at once; what is drawn on a board, a map or the graph is never a perch. **Over a board it is in the board** (INBOX 1300 C19, C20): put over the canvas rather than on a panel or the bars, its band takes the raised step (`nmb-canvas`, z 2), under the board's rail, top bar and Format panel, and its size follows the board's zoom (`nameMarkBuddyCanvasZoom`, down to 0.4 of its own, never above it); the open Format panel and sidebar are popups it steps out of (`NMB_POPUPS`). **It stacks with its perch**: perched on something that scrolls under a bar, it goes under that bar with it (`.nm-buddy-shutter`, `nameMarkBuddyRideClip`); perched on the bar itself it stays in front. **Enlarged, it is itself**: a double-click moves the companion's own element into its large view (`nameMarkBuddyVisit`), still doing what it was doing, and home again on Close; never a second drawing of it | `tests/test_companion_motion.py`, `tests/test_companion_stacking.py`, `tests/test_companion_toggle.py`, `scratchpad/ui-sweeps/companionscroll.js`, `companionpin.js`, `companionmenu.js`, `companionstack.js`, `companiontoggle.js`, `companionchat.js`, `companionviewer.js`, `companionfade.js`, `smooth1005-perch.js` |
| A row of facts about a card where some facts open a list (a skill's "3 steps", "4 tools") | One `.skill-card-facts` row, every fact one `--skill-fact-h` box on one baseline: a plain fact is a `.chip`, a fact that opens is a `button.skill-fact-toggle` carrying `aria-expanded` and `aria-controls` and a trailing caret that turns. What it opens is a `.skill-fact-panel` *after* the row at the card's full width, never inside it, so opening one never moves another fact (INBOX 450: a `<details>` in the row pushed "4 tools" onto a line of its own). A list of identifiers in a panel is `code.skill-tool-token`, the code chip, at the fact height. Cards of uneven height are dealt into columns in reading order (`skillColumnCount`, like `libraryColumnCount`), never a grid whose rows stretch to their tallest card | `tests/test_ui_recipes.py`, `scratchpad/ui-sweeps/skills450.js` |
| A note's details line (category, score, tags, suggestions, the dates it mentions, links, the time) | **One line, never two**: `.entry-meta.note-meta` is `nowrap`, and `fitNoteMetas` (note-cards.js, one shared `ResizeObserver`, every line reset, read and folded in three passes so a list costs two layouts) folds what does not fit from the end: suggestions then tags into one "+N" chip (`.note-meta-more`, a press lists them through `openMenuAtPoint`, each row doing what its chip does), then the word facts keep their icon and lose their words (`.is-icon`, the words on the `title`), then they ellipsise; the category gives way last. **The time is the line's last fact at its right edge on every card**, never in the head row (the corner is the actions', and a time that faded there on hover was INBOX 446). **The line is the card's last part in card view** (INBOX 760): the card is a column flex and `.entry-meta` has the last `order`, so the wiki-link row, the why line and the review answers built after it sit above it and the gap under the time is the card's padding on every card (it was 48 to 113px on a card with links against 7px with none); "· edited" keeps its space as a no-break space in `.entry-edited`'s text (a plain leading space collapses in the date's flex box) A new fact on the line is a `.chip` with a `ph:` icon, so it can fold | `tests/test_note_meta_line.py`, `tests/test_ui_recipes.py` (`test_a_note_cards_details_line_ends_the_card...`), `scratchpad/ui-sweeps/carddate.js`, `scratchpad/ui-sweeps/notemeta.js`, `scratchpad/ui-sweeps/notemetamore.js` |
| A word saying where an item came from ("Built-in", "Edited", "Yours", "you set this", "from the model", "default"), **or what state it is in** ("Installed", "Stopped", "Not ready yet", "Fits", "Tight fit", "In use for chat", "confirms first", "online": INBOX 461 (1)) | `chip item-label`, 11px muted type on a **tinted pill without an edge** (`--chip-bg` at `--radius-pill`, `border: 0`; INBOX 553 (c), the owner's decision of 2026-10-05, matching the meta chips), one line, on every surface; `is-yours` takes the accent tint and ink for "you made or changed this" (and "in use"), `is-ok` the ok tint and icon for ready, `is-warn` the warn tint and ink for a request to look. The tone is the tint, never an edge. The Files tiles' "Read · N words" and a chat attachment's reading badge are this label too. Beside a heading it centres on the heading's text (measured within 0.7px by `badgeinv.js`). Not this recipe: a count (a number pill), a reading badge laid over a picture (it needs a ground), a fact on a facts line (`.chip.item-fact`), and the dashboard's "Editing layout", which is words by the owner's call. A model card's labels are a row of their own above its actions, one line (INBOX 468). A named item in a list (Settings' templates, skills, personas) is the row (title, label, facts, description) beside its actions, which are a right-hand column centred on the whole item and always shown | `tests/test_badge_recipe.py` (`test_a_status_label_is_a_tinted_pill_without_an_edge`), `scratchpad/ui-sweeps/badges.js`, `scratchpad/ui-sweeps/badgeinv.js`, `scratchpad/ui-sweeps/modelcardfoot.js` |
| Who wrote a reply (INBOX 1300 C14: From your notes, the model, Composer, From the help) | **The byline badge**: one `chip item-label answer-model` beside the assistant's name in the reply's head, drawn by `replyByline` (reply-kit.js) through `finishReply`'s `head` on Chat, the popup agent and the Guide; Ask's `#answered-by` is the same chip over its answer. Its title says it in full; a long model id ends in an ellipsis at `min(16rem, 50%)`. Never words after the name | `tests/test_reply_cards.py` |
| A control that acts on the computer Tessellate runs on (installs, downloads a model, restores a backup, starts a server, quits, points the app at another address) | `data-this-computer` on the control's smallest block (`="hide"` for a bar button with no room for a line). On another device (`/health` says `this_computer: false`) `markOtherDevice` (skills.js) puts `data-other-device` on `<html>`, one `.this-computer-note` line before each block reading `THIS_COMPUTER_ONLY` (the server's own refusal, "Not available on this device. Do it on the computer Tessellate runs on."), dims its controls like `button:disabled`, and a press toasts that line instead of acting; `?` toggles inside still open. The route carries `this_computer_only` (`api/this_computer.py`) whatever the page does | `tests/test_ui_recipes.py`, `tests/test_this_computer_only.py`, `tests/test_other_device_limits.py` |

The sweeps that say whether a new surface matches the rest are
`errors.js`, `contrast.js` (text), `contrastui.js` (everything that is not
text: icons, edges, focus rings, selected states), `docks.js`, `touch.js`,
`menus.js` and `kebab-viewport.js` under `scratchpad/ui-sweeps/`; a UI change is not
done until they are green and its numbers are in the commit message.

## Taken from Liquid Glass and the Human Interface Guidelines (2026-09-09)

Read from Apple's own pages (the Liquid Glass overview, "Adopting Liquid
Glass", and the HIG's materials, layout, toolbars, menus, sheets,
popovers, typography, colour, motion, buttons, tab bars, sidebars, search
and accessibility pages). What transfers to a web app with its own tokens,
what we already do, and what we deliberately leave.

### The one idea worth the most

Liquid Glass "forms a distinct functional layer for controls and
navigation elements that floats above the content layer". "Don't use
Liquid Glass in the content layer." "Use Liquid Glass effects sparingly ...
limit these effects to the most important functional elements." That is
INBOX 49's decision word for word: blur on the top bar, the sub-tab
strips, docks, menus, popovers and dialogs; never on a content card. The
one exception Apple names is ours too: "controls in the content layer with
a transient interactive element like sliders and toggles ... take on a
Liquid Glass appearance when a person activates it" (the switch knob and
the slider thumb light up on drag, nothing else in a card blurs).

### Rules adopted, with the token or recipe they land on

1. **Two glass variants.** Regular: "blurs and adjusts the luminosity of
   background content to maintain legibility of text"; use it "when
   components have a significant amount of text, such as alerts, sidebars,
   or popovers". Clear: "highly translucent ... for components that float
   above media backgrounds", with "a dark dimming layer of 35% opacity"
   when the content behind is bright. Ours: `--glass-filter` is the regular
   variant (blur plus saturate plus a luminosity lift); `--glass-filter-clear`
   (blur only) is the clear one, for a panel over the animated background
   or an image; take one of the two tokens, never a literal. A
   `.glass-clear` class (`--card` at 30%, paired with a `--glass-scrim` of
   35% ink when light) is added with the first surface that floats over
   media, in that commit. Never a third variant: `tests/test_ui_recipes.py`
   freezes the literals and fails on a new one.
2. **Scroll edge effect.** "Optimize for legibility when content scrolls
   beneath controls": the bar over a scroll region fades a soft edge under
   itself as content passes. Ours: `.dock`, `.notes-subtabs`,
   `.library-subtabs` and `header#top-bar` take a 16px `box-shadow` in
   `--scroll-edge`, shown only while the region is scrolled
   (`data-scrolled="1"`, set by one listener in app.js on the single bar
   whose bottom edge is against the top of the region that scrolled: it
   picks by measuring, because three bars can be stacked over one list and
   only the last of them has anything passing behind it). **A shadow, not
   the `::after` gradient this rule was first written as**: an absolutely
   positioned pseudo-element extends its bar's scrollable overflow, which
   turned `#notes-subtabs` into a 60/44 vertical scroller, and clipping it
   back hides the gradient with it. Built, INBOX 100.
3. **Concentric corners.** "Rounded shapes that are concentric to their
   containers": an inner radius is the outer radius minus the padding
   between them. Ours: `--radius-inner: calc(var(--radius) - var(--space-3))`
   and a lint that a `.card` child with its own radius uses it. INBOX 101.
   **The rollout, decided 2026-10-05** (op4-1005, OPEN.md popup-redesigns):
   it applies to a *surface* (a painted box: a well, a preview, a swatch, a
   fold body) nested inside a rounded, painted container **closer to its
   edge than the container's own radius**. A control (button, field, chip,
   segment, stepper, or an interactive row: a summary, a check row) keeps its tier, since controls are sized by the control
   recipe, not by what holds them; a surface inset by the container's radius
   or more is a separate shape and keeps its tier; a popover is not nested.
   Measured with a probe over the six tabs and every Settings section at the
   largest corner setting (16px): no surface inside a `.card` was out of
   concentric; outside cards, three kinds were (`.theme-preview` and
   `.theme-swatch` in a theme card, `.setup-snippet` in an accordion, drawn at
   8.8 to 9.6px inside a 12.8px corner 9px away) and take `--radius-inner`
   now. Lint: `tests/test_style_scale.py`
   (`test_the_nested_surfaces_are_concentric`).
4. **Vibrant colour on glass.** "Use vibrant colors on top of materials";
   "Use color sparingly, especially on glass"; "Avoid applying a similar
   color to toolbar item labels and content layer backgrounds". Ours:
   `--text` on a blurred surface already measures 14 to 15:1 (no
   `--text-on-glass` token was needed); accent only on the one filled
   control per surface.
5. **Toolbars group by function, icons over text.** "Group items that
   perform similar actions ... maintain consistent groupings"; "don't mix
   text and icons across items that share a background"; "Provide an
   accessibility label for every icon"; "Use the prominent style for key
   actions such as Done or Submit" (one). Ours: the dock grammar (four
   zones parted by space, never a hairline; seven controls; one filled, last) is this rule; the
   lint holds it; a group is all icons or all text, never mixed.
6. **Menus.** "Prefer listing important or frequently used menu items
   first"; "Use menu item icons sparingly and with purpose"; "Consider
   using a checkmark to show that an attribute is currently in effect";
   "Show people when a menu item is unavailable"; "Prefer displaying a menu
   near the content it controls"; and, new: "an action sheet originates
   from the element that initiates the action". Ours: `kebabMenu` orders
   by frequency, the check mark on-state exists, disabled items stay
   visible and dimmed, and every menu anchors to its opener (never the
   screen edge).
7. **Buttons.** "Keep the number of prominent buttons to one or two per
   view"; "Use style, not size, to distinguish the preferred choice";
   "Don't assign the primary role to a button that performs a destructive
   action"; help buttons are "circular, consistently sized buttons that
   contain a question mark" and "avoid displaying text that introduces a
   help button". Ours: the ramp, Bin is never filled, the `data-help-for`
   '?' is round and unlabelled.
8. **Sheets and popovers.** "Show one popover at a time"; "Make a popover
   only big enough to display its contents"; "Avoid displaying popovers in
   compact views" (a sheet on a phone instead); half sheets are "inset
   from the edge of the display to allow content to peek through" and go
   opaque at full height. Ours: one popover open at a time (the outside
   click closes the rest), popovers become bottom sheets under 640px, a
   sheet has `--space-3` inset and the regular glass until it fills the
   height, then `--modal-bg`.
9. **Lists breathe.** "Organizational components like lists, tables, and
   forms have a larger row height and padding. Sections have an increased
   corner radius to match the curvature of controls." Ours: `--row-h`
   steps up one token at comfortable density; `.settings-group` radius is
   `--radius-lg`. (Apple also moved section headers to title case; we keep
   sentence case, the owner's rule.)
10. **Tab bar and sidebar.** "Use a tab bar to support navigation, not to
    provide actions"; "Don't disable or hide tab bar buttons"; "Consider
    automatically hiding and revealing a sidebar when its container window
    resizes"; tab bars can "recede when a person scrolls". Ours: the phone
    tab bar shrinks to icons on scroll down and returns on scroll up
    (UI Phase 9); the sidebar auto-hides under 1100px and is never hidden
    by default on desktop.
11. **Search.** "Place search at the top when there's no bottom toolbar";
    "Use tokens to filter by common search terms"; "Consider showing
    suggested search terms". Ours: INBOX 99e's operators become tokens in
    the Notes search box, suggestions under it.
12. **Motion.** "Don't add motion for the sake of adding motion";
    "Consider using fades when you need to relocate an object"; controls
    "fluidly morph into menus and popovers". Ours: a button that opens a
    menu scales the menu from the button's rect (`--motion-base`, spring
    easing), a fade for anything that moves more than its own width, and
    every one of these is governed by the Interface animations switch
    (`data-ui-motion`, the `--ui-*` tokens), and the large movement (Atlas,
    the background art, the graph and the whiteboard) stills under Reduce
    motion and Performance mode.
13. **Accessibility settings are inputs, not exceptions.** "People can ...
    turn on accessibility settings that reduce transparency or motion";
    "Make sure all your app's colors work well in light, dark, and
    increased contrast contexts"; "Let people use the keyboard alone".
    Ours: `prefers-reduced-transparency` turns Performance mode on,
    `prefers-contrast` sets `data-contrast`, every menu and dialog walks
    by keyboard (contrast.js and touch.js are the gates).
14. **Extra-large controls.** Controls "feature an option for an
    extra-large size, allowing more space for labels". Ours:
    no token of its own: the composers' controls take `--control-h-body`, and
    under a coarse pointer every control is held to the 44px floor
    (`--target-min`), the phone sheet's primary action and the capture Save
    included.

### Deliberately not taken

Refraction and lensing (a displacement filter on every glass surface is
the one effect measured as too costly on an integrated GPU; the lit rim
stands in for it), layered app icons, the background extension effect
under sidebars (our sidebar is a content panel, not glass), title-case
section headers.

### Where this went

The five items this section once queued are built: the scroll edge effect, the
concentric radius token (`--radius-inner`), the clear glass variant
(`--glass-filter-clear`), menus that open out of the control that opened them, and the
phone tab bar that recedes on scroll. What is still open is in
[UI_MODERNISATION_PLAN.md](roadmap/UI_MODERNISATION_PLAN.md).

## Buttons: the ramp

Three tiers, and a view should be readable from them alone:

| Tier | Recipe | Use |
| --- | --- | --- |
| **Filled** | `button`: accent fill, `--on-accent` text, the accent glow | The one action a surface is *for*. One per card or dialog, a dashboard of widgets has one per widget (Save, Start), not one for the page. A Settings page is one surface however many groups it has: one filled at most, the rest `ghost` (`tests/test_ui_recipes.py`; Import & export had five). A dialog whose action changes with its stage (Suggest then Replace, Record then Save) writes the later button `ghost` and hands the one fill over with `stagePrimary(first, later, laterTurn)` (app.js); `tests/test_consistency_contract.py` holds every modal and pane to one, with no allowance. |
| **Tonal** (quiet since 2026-09-27) | `button.ghost`: a `--btn-quiet-bg` face (the field's white in light, a breath of white in dark), a 1px `--ghost-btn-border` edge measured to 3:1 against its ground, no shadow; `--ghost-btn-bg` under the pointer, `--ghost-btn-bg-hover` pressed, a 2px accent ring on focus-visible; a 32px floor (`--button-min-h`, 44 under touch). An `.icon-only`/`.icon-button` standing alone is a ghost: no fill, no edge, the glyph in `--muted`, the tint and `--ink` on hover | An action that stands on its own in a dialog or a Settings group (Cancel beside the filled one, a row's Reinstall). |
| **Quiet** | the same button inside something that already frames it, a dock, **any `.card` that is not a dialog** (one rule, `:where(.card) button.ghost` in 01-forms-settings.css; INBOX 803, the owner: "Im still iffy about the design use of these buttons styles in some places"), a card's `.entry-actions` run, a floating whiteboard panel: no fill, no edge, no shadow, weight 500, the leading icon's accent as the cue, the tint under the pointer or the keyboard | A card's secondary actions (a dashboard widget's "Find links to add"), a panel's suggested actions (the code assistant's tools), a toolbar inside a card (the editor's Format, Assistant, Snippets beside its one filled Run). The container is the affordance; the tint is the state. |
| **Plain** | tab-bar buttons, `.linklike`, `.status-item`: no fill at rest, a tint on hover | Navigation and inline actions that sit in running text or a strip that is already a well. |

**The tonal/quiet split is the answer to one report made three times**, most
recently "all the buttons need to actually look like buttons with affordance,
not just shapes with text in them". The edge was tried, then removed on a
real measurement (22 outlined-and-shadowed buttons in one Notes toolbar,
beside outlined inputs and an outlined card, is three lines of texture), then
asked for again, because removing it left every button in the app a flat tint:
a silhouette with no rim, which is precisely a shape with text in it.

Both measurements are right and they are about different buttons. So the
split is not what the button is, it is **whether anything already frames
it**. On its own, a button draws its own edge and its own small lift. In a
dock, a whiteboard panel, or a run of row actions on a card, the frame is
already drawn and the button stays quiet until the pointer arrives. Measured
after the split: the 52 outlined boxes a note list put on screen went to 0,
and the largest remaining run of tonal buttons anywhere is 5.
`[data-contrast="on"]` puts an edge on the quiet tier too.
`tests/test_ui_recipes.py` pins the tonal recipe so a fourth pass cannot
flatten it again.

**The tonal tier draws no shadow, and the reason is dark mode.**
`--shadow-sm` is seven times heavier in dark than in light, because a shadow
over a #0e1017 page has almost no contrast to work with, and it was sized
for a panel. Under a 28px control it measures `rgba(0, 0, 0, 0.35)`, and
eight of those in one strip is a row of dark rims: reported as "the border
shadow on elements like these are too strong". The hairline is what makes a
tonal button read as pressable; a lift is what made it read as heavy. The
filled tier keeps its glow, and there is one of those per surface.

A selected toggle (`.active`) is the filled recipe: on is the accent, not a
darker tonal.

**Segmented controls are two things, and they are drawn differently on
purpose.** A *tab strip* (`[role="tablist"]`: the tab bar, the Notes and
Library sub-tabs) sits on the surface, the tab bar is a `--field-inset`
well, the sub-tab strips are `.tabs-line` (text and a 2px line, no box; see
the recipe index). A *choice control* (`.seg`,
`.segmented-control`: view toggles, sort, Ask/Agent) is a `--chip-bg` well
with no edge, whatever else it is inside. Measured: 28 `.seg` groups were
already that, and the Graph's layout/colour pickers plus the chat dock's
mode switch were the three drawn as cards, now conformed, not given a
third recipe.

**A segmented track's corner comes from this table and nowhere else.**
Measured 2026-09-21 and 2026-09-23 (`scratchpad/ui-sweeps/segradius.js`):
five track radii, none written down, so every new toggle picked the nearest
token. `tests/test_ui_recipes.py` (`test_a_segmented_track_is_rounded_by_the_table`)
fails a rule that rounds a track any other way.

| Where the control stands | Track radius | At the default 14px |
| --- | --- | --- |
| A choice control on its own: a form, a card, a popup, the document view and history toggles, the assistant's verbs | `--radius-choice` | 15.4px |
| A boxed tab strip (the OCR rail's `#ocr-rail-switch`; the tab bar is on the same token; the Notes and Library strips are `.tabs-line` now and have no track) | `--radius-strip` | 11.2px |
| Inside a `.dock` bar: the bar's corner, which its buttons already use | `--radius-md` | 8.4px |
| Inside the chat dock, where every control is a pill | `--radius-pill` | 999px |
| A `.tabs-line` strip (`#notes-subtabs`, `#library-subtabs`, `#doc-sidebar-tabs`) | `0` | 0 |

The tabs *inside* a `.tabs-line` strip are buttons and take `--radius-md` on all four corners for their hover fill and focus ring (INBOX 682); the chosen tab is the strip's 2px line and never a box, in every look, so no `.tabs-line` is also a `.seg` (that class gave `#doc-sidebar-tabs` the flat looks' filled, edged, square-cornered choice-control slab).

The third row is the one-corner-per-row rule (08-consistency.css): a 15.4px
well beside 8.4px buttons in the same bar was two radii in one strip, which
is what that rule was written to remove. So the toolbar toggles keep the
bar's corner rather than folding into the choice row, and the chat dock's
pills are the same rule in a row of pills.

**Pills are rare, and never dashed.** The owner, 2026-09-23 (INBOX 394 h):
"are these pills a sign of ai vibe coding??" Yes: a fully round capsule on
every control is one of the clearest generated-UI tells, a dashed one most of
all. Measured before (`scratchpad/ui-sweeps/pills.js`, 1440, light): 90
controls in 14 groups drawn as capsules, including the Library's kind row and
the Boards filter (navigation), the Write tab's starters and the dashboard's
Jump to row (actions), and every category and fact chip. The rule:

| What it is | Corner |
| --- | --- |
| A navigation or filter row you pick one of (`.library-chip`: the Library kinds, the Boards filter, Reminders' Open/All/Done) | `--radius-md`, the button's corner, with the selected one filled |
| An action (the Write tab's starters) | `--radius-md`: it is a button |
| A label: a category, a tag, a fact (`.chip`, `.dock-chip`, the skill facts, a legend entry) | `--radius-sm` |
| A capsule | Only where `PILL_CONTROLS` in `tests/test_ui_recipes.py` names it with its reason: the chat composer's row, a round icon button, a floating bar over a canvas, a count badge, a switch |

A dashed edge means an empty slot you can fill (a drop zone, an unset trace
end), never "this one is special": a skill is marked by its lightning icon.
A chip does not lift on hover; its tone changes.

**A choice control's selected segment is `--accent-surface` behind
`--on-accent`, with no shadow, whichever of the two forms it is.** The
radio-backed form (`.segmented-control`: `#doc-ai-verb`, `#graph-layout`) is
the same object as the button-backed one (`.seg`) and the recipe index has no
room for a second reading of it. Reported as INBOX 107d, "I want to get rid of
and redesign these mini menu bars ... they desperately need a modern redesign
or alternative". Measured beside `#doc-view-seg` on one screen before
(`scratchpad/ui-sweeps/segbars.js`): track radius 8.4px against 15.4px,
padding 2.4px against 4px, segments 26px tall at 12px type against 28px at
16px, and a selected state of `rgba(79,109,245,0.14)` behind `--ink` plus a
`0 2px 8px` drop shadow, against a solid accent behind white. A 14% tint
behind body-coloured text is not a selected state you can see across a popup,
and a segment inset in a well does not cast a shadow out of it. The answer to
"redesign or alternative" was neither: it was `.seg`'s numbers. What stays
particular to the radio form is only the plumbing, the visually hidden
`input[type="radio"]` that gives the group its native arrow-key navigation.

**Form rows share a label column.** `--form-label-col` (9rem; `-wide`, 11rem,
for Search relevance) is the width every `.setting-label` reserves, so the
controls in adjacent rows start on one edge.

## Icons

Phosphor (`<i class="ph ph-*">`) is the default for every icon in the app.
One deliberate, narrower exception: **download/export actions use a plain
Unicode arrow glyph** (`⬇`, `⭳`) instead, chat export, both document
export buttons, the whiteboard export button, and the settings support-
bundle download all do this consistently. It reads as inconsistent seen in
isolation; checked across all five call sites before touching any of them,
it is the app's actual (if quiet) convention for this one action family,
not drift, leave it alone rather than "fixing" it to Phosphor.

**The AI and the agent: one glyph per meaning** (INBOX 723, the owner:
"make sure all the icons for the ai are consistent. also can you use a better
icon for the agent?? i dont like the robot"). Before: five glyphs for the AI
and no rule, so "Ask Atlas" wore a sparkle in one menu and a wand in the next.

| Glyph | Means | Where |
| --- | --- | --- |
| `ph-sparkle` | The AI does a thing for you | Describe with AI, Read text with AI, Ask (Notes' tab, its AI switch, Chat's mode), AI suggestions and composed answers, Draft, Refine, AI edit, Name with Atlas, File by meaning, Semantic search, the "AI off" mark (slashed) |
| `ph-strategy` | The agent: plans, then acts in steps on your behalf | Agent mode (toggle, segment, palette row), the popup agent (status bar, its head and input, More on a phone), Agent activity (title, status bar runs), a run's notification, a past turn answered in Agent mode |
| `ph-lightning` | Skills | The Skills picker, a skill's run, Settings, Skills |
| `ph-magic-wand` | Tidy or fix automatically, by rule, no model | Fix all (prose), Autocorrect as I type, a map's auto alignment |
| `ph-brain` | What it remembers about you | Settings, What it remembers; "Remember this for next time?"; the memory tool's results |
| `ph-asterisk` | A section break | The editor's insert menu |

Not drawn: `ph-robot` (the agent's old glyph) and `ph-star-four` (it read as
a second sparkle; Atlas's look is `ph-coat-hanger`). `tests/test_icon_conventions.py`
fails on either, and on the agent glyph anywhere not listed.

**Deliberately not taken: a per-glyph optical offset** (decided 2026-10-05,
op4-1005, OPEN.md holepoke). An icon is centred by its box (the one ink
nudge every icon-only control shares, `ee6289d`: mean glyph ink -0.19px).
A few glyphs still draw high in their em box (the status bar's back and
history carets 1.0px, the chat header's, the Timeline view switch's and the
lock's 0.63px, measured by a session script that was not kept): that is the glyph's own shape, and a table
of offsets per glyph would be a second icon set to keep in step with every
Phosphor update, for under a pixel at the app's own zoom.

---

## Hierarchy

Levels must be **visibly ordered**, and they were not: `h2` ranged 0.92–1.15rem
depending on where it sat while `h3` was a flat 0.92rem, so in the sidebar a
section title was the same size as the subsections beneath it.

| Level | Size | Treatment |
| --- | --- | --- |
| `.card h2` | `--text-body` | weight 600, tight tracking, **a heading: names a thing** (was 650, which a font with static weights, Segoe UI and most system faces, resolves to Bold 700: every card title drew a step heavier than designed) |
| `.card h3`, `.eyebrow`, `.nav-group-label`, `.launch-label` | `--text-sm` | weight 600, muted, uppercase, 0.04em, **an eyebrow: labels a section of controls** |
| `h4.setting-subhead` | `--text-md` | weight 600, sentence case, a subdivision inside an eyebrow's group |
| `.dash-getting-started h2` | `--text-h3` | titles a whole panel, not a card |

**Eyebrow vs heading.** An eyebrow labels a *section of controls* (THEMES,
WHICH ONES IT MAY USE, THE AI, START SOMETHING); a heading names a *thing*
(All notes, Recently added, a note's title). They are never both capitals,
a subdivision under an eyebrow is `h4.setting-subhead` in sentence case, not
a second run of caps (About → Updates was two stacked caps labels of the
same weight before this, and read as rivals). There is one eyebrow recipe,
measured: the app had two (12px/600/0.04em on cards, 11.2px/700/0.06em at
75% opacity on the Settings nav and the dashboard launch rows) doing the
same job in two voices. The one place caps sit directly over a title is the
dashboard hero's wordmark kicker, which is branding, not a section label.

Note that `h3` is **smaller** than `h2`, not one step down from it. Small caps
carry the distinction, which frees the size to drop, two sizes 0.08rem apart
cannot signal a level change on their own, and trying to make them was what
made the old hierarchy invisible.

**Use weight, colour and case before reaching for another size step.** The type
scale has ten steps because an interface needs ten *sizes*, not ten *levels*.

---

## Decided 2026-10-10, lints pending (UI_MODERNISATION_PLAN Phase 13)

New UI follows these now; the ratchets land with Briefs 57 and 58. A rule
whose lint has landed moves to its own section and leaves this list.

- No new rule in `08-consistency.css` or `10-responsive.css` (a rule lives
  with its component).
- One primary action per surface. Three notification channels: toast, the
  undo bar, the panel.

## The stylesheet's grammar (Phase 13a, Brief 57, 2026-10-11)

The decisions of UI_MODERNISATION_PLAN 13.3 whose lints have landed. Each
names its lint; the substitutions that brought the stylesheet to it were
value for value, so nothing rendered differently except where a hover or a
focus was unified.

### Slow moves things (decision 14)

Every transition's duration was already a token (`test_motion_tokens.py`).
What was left is which token: `--motion-slow` (`--ui-slow`) is for a surface
entering, leaving or moving; a colour, ground or edge changing is feedback and
runs on `--ui-fast` (a hover, the button recipe) or `--ui-base` (a state). Five
hovers and one step dot ran their colour on slow (the segmented control, the
skills sidebar toggle, the skill card and the board card's edge, the
onboarding dots): 200ms to 120ms (160ms for the dots). The one exception is a
label whose colour follows the glide moving under it (`.has-glide`). A
one-shot interface animation (a message arriving, the agent monitor sliding
in, a log row fading in) takes a token too, so Interface animations reach it;
loops, the companion and the laser trail keep their own timing as part of the
drawing. Lints: `test_a_colour_change_never_runs_on_the_slow_token`,
`test_an_interface_animation_that_plays_once_runs_on_a_token`.

### Hover and focus are one state (decision 15)

A `:hover` is declared with its keyboard twin **in the same rule**, so the two
can never drift apart:

```css
.row:hover,
.row:is(:focus-visible, :has(:focus-visible)) { background: var(--hover-veil); }
```

`X:hover` matches X and every ancestor of the pointer, so the faithful twin is
X reached by the keyboard or holding such a focus: a row lights when Tab
reaches the button inside it, as it does under the pointer. Inside a `:has()`
(which cannot nest) the twin is `:focus-visible` alone. Exempt by shape: a
field's `:hover:not(:focus)` and a pseudo-element's own hover (scrollbar
thumb, the file button). Measured: 462 hover selectors, 253 alone before, 0
after. The press is the base rule's alone (`button:active`, a 3% `scale` and
the deeper ground); a family does not add its own (`.graph-zoom-btn`'s
`scale(0.94)` came out). Lint: `tests/test_hover_focus_pairs.py`; sweep:
`scratchpad/ui-sweeps/focusbox.js` (per Tab stop, does focus show the hover's
fill and ink).

### Circles are faces, colours and drawn shapes (decision 17)

`border-radius: 50%` is for a face (avatars, the companion and its parts), a
colour you pick (swatches, the colour inputs) and a drawing's own round shape
(a map node's ellipse, the map core, the radial's ring, a range thumb). A round
dot, a spinner or a small round button is `var(--radius-pill)` on a square
box, which draws the same circle: 58 rules before, 31 moved, 27 left. Four of
those are round controls the pill rule does not let be capsules (the agent
rail's step dots, the board's tool buttons, the category dot on a note's and a
timeline row's chip), listed by name in `CIRCLES_LEFT` for 13c. Lint:
`test_a_circle_is_a_face_a_colour_or_a_drawn_shape`.

### Colour lives in two files (decision 10)

A hex or `rgb()` is written in `00-tokens-shell.css` or
`05-sidebars-themes.css`; every other file names a token. The fourteen accent
presets (`:root[data-accent=...]`, 42 literals) were theme definitions in
`02-chat-graph.css` and moved whole to the head of the themes file (nothing
between the two places sets their properties, so the cascade is unchanged).
The 198 left (240 before) are counted per file and may only fall; the
largest are 08-consistency.css (64), 02-chat-graph.css (46) and
library-lazy.css (33). Lint:
`test_colour_literals_live_in_the_two_colour_files`.

### A token is read, and the count only falls (decision 9)

Every custom property is read by a `var()`, a script, the markup or the
server; the nine nothing read were deleted (432 declared before, 423 after,
by `$S/grammar57-subst.py 9`, which recomputes the dead set on each run). The
decision's target is about 200: a new token needs a recipe that uses it twice
or retires another. Lints: `test_every_declared_token_is_read`,
`test_the_token_count_only_falls` (`TOKEN_BUDGET`).

### Layers: no new literal (decision 12)

The decision's scale (`--layer-raised` 2, `--layer-sticky` 10, `--layer-dock`
20, `--layer-popover` 40, `--layer-sheet` 50, `--layer-modal` 60,
`--layer-toast` 70, `--layer-lock` 80) is not substituted yet: 115 literal
z-indexes above 2 hold 49 distinct values from 3 to 100000, about thirty of
them global layers, and folding them into eight changes what stacks over
what (the lock screen is 50 today, under the toasts). The order map is in
`archive/agent-remaining/grammar57-1011.md`; until it lands the count only falls.
Lint: `test_no_new_literal_layer` (`Z_LITERALS_LEFT`).

### Shadows are the elevation tokens and the focus ring (decision 13)

An outer, blurred shadow is `--shadow-sm`, `--shadow-md` (`--glass-shadow`)
or `--shadow-lg`; an inset edge or a spread-only ring is not elevation and is
not counted. 19 hand-written drop shadows are left, each a different blur
that a token would visibly change; they only fall. Lint:
`test_a_drop_shadow_is_an_elevation_token` (`DROP_SHADOWS_LEFT`).

### `!important` only falls (decision 16)

171 at the design review, 128 when Brief 57 measured: most are the motion
switches overriding every element's own animation, print, and the
companion's states. Each goes by specificity; none is added. Lint:
`test_important_only_falls` (`IMPORTANT_LEFT`).

## Density, hover and WCAG 2.2: the ten rules taken (Phase 12, 2026-10-10)

Research recorded before any CSS moved (UI_MODERNISATION_PLAN Phase 12
decision 9). Sources: the vendored ui-ux-pro-max skill's UX guidelines
(searched: touch target size, touch spacing, hover vs tap, focus not
obscured, dragging movements, consistent help, accessible authentication),
Fluent 2's size ramp (24, 32, 40) and 4px spacing ramp, VS Code's workbench
(35px title bar, 22px list rows, 28px toolbar actions), Teams' sub-menu bars
and icon hover, Apple's 44pt touch floor, and WCAG 2.2's new criteria. Each
rule names the number it sets and where it lives.

| # | Rule | Number | Lives in |
| --- | --- | --- | --- |
| 1 | Three control heights: dense for docks, toolbars and sub-menu bars; default for forms and menus; touch under a coarse pointer | 28, 32, 40 (`--control-h-dense`, `--control-h-lg`, `--control-h-touch`) | `00-tokens-shell.css`; a dock sets `--control-h: var(--control-h-dense)` |
| 2 | The top bar is one row of one height | bar 44 (`--topbar-h`), its squares and tab strip 36, tabs 32 | `header#top-bar`, `#tab-bar` |
| 3 | Gaps sit on a 4px grid; a finger gets at least 8 between targets (ux: touch spacing) | 4, 8, 12, 16 | `--space-*` |
| 4 | **Amended 2026-10-10 (INBOX 784/788, the owner: "not all buttons have the same hover states").** Every button answers hover and focus with the one quiet fill: an icon button as a labelled one (`--ghost-btn-bg`, `--chip-bg` on a status item), a row or an interactive chip the veil (`--hover-veil`), the glyph to full ink; the accent colour is for the chosen thing, never for hover. Was: an icon colours its glyph and has no box (Teams) | quiet fill, ink | `01-forms-settings.css`, lint in `test_ui_recipes.py` |
| 5 | A sub-menu bar item (a `.tabs-line` tab) marks hover with a 2px underline, the selected one with the accent underline | 2px | `.tabs-line` |
| 6 | One radius per class: pill for chips and segments, the button radius for buttons and help triggers, the panel radius for panels and menus; circles are avatars, the companion and swatches only | `--radius-pill`, `--radius-md`, `--radius-lg` | lint in `test_ui_recipes.py` |
| 7 | Target size (2.5.8): every target at least 24 by 24, ours floored at 28 with a pointer and 44 under touch | 24 / 28 / 44 (`--target-min`) | `touch.js`, `axe.js` |
| 8 | Focus visible (2.4.7, 2.4.11, 2.4.13): a 2px ring at 3:1 against its ground, never hidden behind a sticky bar | 2px, 3:1 | the base `:focus-visible`, `--ring-room` |
| 9 | Contrast: text 4.5:1, UI edges and glyphs 3:1 | 4.5, 3 | `contrast.js` |
| 10 | Dragging (2.5.7), consistent help (3.2.6), redundant entry (3.3.7), accessible authentication (3.3.8): every drag has a menu or key alternative; help is the `?` at the section head; a value asked twice is filled the second time; the lock field allows paste and a password manager (`autocomplete="current-password"`) | 0 drag-only actions | the recipes for boards, maps and reorders; `#lock-password` |

## Adding a feature

1. **Reach for a token first.** If you are typing a rem value into a `margin`,
   `padding`, `gap`, `font-size` or `border-radius`, stop, there is almost
   certainly a step for it.
2. **A page goes in `.tab-page`** and sets only its internal `gap`.
3. **A panel is a `.card`.** It brings its own padding, radius and shadow. Do
   not re-specify them.
4. **A group of choices is `.check-row`**, not bare labels, each option gets a
   hit area, a hover and a selected state, so the group is scannable without
   hunting for a filled dot.
5. **Confirming something destructive is `confirmDialog(...)`**, never
   `window.confirm`: the desktop shell does not reliably implement it, and a
   button gated behind one that returns `undefined` silently does nothing.
6. **Run the lint.** `pytest tests/test_style_scale.py`.

### When a token genuinely doesn't fit

Add the value to the relevant `ALLOWED` set in `tests/test_style_scale.py`
**with the reason**. There are three entries there today, two indent steps for
the document outline, which must stay evenly spaced relative to each other
rather than land on a scale built for gaps between unrelated things, and a
negative pull-back that cancels a list's own indent exactly.

Being made to write the reason is the entire mechanism. An entry with a vague
reason is a value that should have been snapped to the scale.

---

## Why the lint matters more than the conversion

The conversion is a one-off. Without something that fails, the next tab built
in the next session reaches for whatever looks right at the time, and the drift
starts again, which is exactly how it got here, over six tabs and as many
sessions.

`tests/test_style_scale.py` checks:

- every spacing value is on the scale;
- every font size is on the scale;
- no corner radius is hard-coded in pixels;
- the corner tiers stay expressed in terms of `--radius`;
- no page container draws its own outer gutter;
- the page shell is declared once and used;
- no colour token is used with a fallback;
- every semantic colour has a dark-mode value.

It strips CSS comments before scanning, because the comments in this file
explain layout decisions and therefore quote lengths, `test_frontend_ids.py`
had to learn the same lesson about markup comments quoting ids.

---

## Surfaces, tiles, chips and the popover shell (UI modernisation, Phases 1-3)

Added by the modernisation pass; every rule here was measured before and
after in Chromium (`scratchpad/ui-sweeps/`), and `tests/test_ui_signatures.py`
ratchets the counts so they cannot drift back.

- **Two card sizes, as tokens.** `.card` sets `--card-pad-y`/`--card-pad-x`
  (panel: `--space-6`/`--space-7`, was `--space-7`/`--space-8` before INBOX 446 (5)); `.card.compact`, `.sidebar-panel` and
  `.dash-widget` set both to `--space-6`. Anything that has to cancel the
  padding to reach the card edge (the sidebar head row) references the token,
  never a step. The 720px block tightens the tokens, not `padding`.
- **A card inside a card is a tone** (`--surface-2`, transparent edge, no
  shadow, no blur), never a second bordered pane.
- **One head row.** `.card > .row:has(> h2)` is `--control-h-lg` tall with
  `--space-5` under it, and the `h2` drops its own bottom margin. The sidebar
  collapse toggle is `--control-h-lg` square, so the sidebar head, the
  Library head and a widget head are one height.
- **The shell's inset is `--page-gutter` everywhere**: the top bar, the
  status bar and the page share one x for the logo, the first card and the
  first status item.
- **Rows have two gaps.** `--space-3` inside a control group, `--space-4`
  between groups. The two 60-control formatting strips (`.doc-toolbar`,
  `.note-toolbar`) are the one `--space-1` exception.
- **One button radius**: `--radius-md`, from the base `button` rule. Tiles
  (`.quick-link`, `.start-step`) are one recipe: `--card` fill,
  `--glass-border`, `--radius-md`, no shadow, `--accent-soft` on hover; a tile
  inside a card is `--surface-2`.
- **The interactive filter chip** (`.library-chip`, the chat composer's
  Skills/Web/Plan): `--chip-bg` tint, transparent 1px edge, pill radius;
  active is the filled recipe. Not an outlined pill.
- **The floating control** (`.scroll-top`, `.graph-zoom`): `--card` fill,
  `--glass-border`, `--glass-shadow`, `--radius-md`; the buttons inside a
  strip are plain. **The help dot** is the one round icon button, on purpose
  (every "?" in the app is it).
- **One popover shell.** `.action-menu`, `.select-menu`, the toolbar menus,
  the nav-history menu, the chat model panel, the help popover and the AI
  status popup share one rule at the end of `07-whiteboard-misc.css`:
  `--modal-bg-opaque`, `--border`, `--radius-lg`, `--glass-shadow`, no blur.
  The notifications panel takes that ground, edge and shadow but is a
  **panel** (`--radius`, `--panel-pad`, the dialog head): see "A popup
  window or panel" in the recipe index. Opaque because CLAUDE.md records the ghost-text
  bug the 96% tint caused over the note editor. A new floating surface joins
  that selector list; it does not declare its own shell.
- **Glass is material, not effect.** `backdrop-filter` stays on the top bar,
  status bar, sidebars, sub-tab strips, panels and floating controls, and is
  off on dashboard widgets and library cards (measured 28 → 4 blurred layers
  on the Dashboard, 25 → 5 on the Library). Background art defaults to 45%.
- **One control size.** Text fields and selects read `--text-md` from the
  base rule; a textarea is a writing surface and reads `--text-body`.
- **Hover changes tone, never position.** No `translateY`/`scale` on hover;
  no transitions on `left/top/width/height` except a progress bar filling.
- **One focus ring**: the base `:focus-visible` (2px `--accent`, 2px offset).
- **A ring is never cut off** (INBOX 685): the ring reaches `--ring-room`
  (4px) past a control, so a container that clips (`overflow` other than
  visible, `contain: paint`) and holds a control flush to its edge leaves that
  room, as padding with the same negative margin (it scrolls) or
  `overflow-clip-margin` (it clips), or draws the ring inside the control
  (`outline-offset: -2px`, `--on-accent` on a chosen segment) when its children
  fill it edge to edge (a tab strip, a list of rows, a pill). Never by hiding
  the ring. A pill track with an edge hands its inside to its segments, and a
  clipped single line keeps a line box of 1.25 or a clip margin. The containers
  are listed in 08-consistency.css "Ring room" and held by
  `tests/test_ring_room.py`; `scratchpad/ui-sweeps/clip685.js` finds the next.

## Control height

```
--control-h-dense: 1.75rem /* 28px: docks, toolbars, sub-menu bars (Phase 12) */
--control-h-lg: 2rem    /* 32px, was 2.25rem (INBOX 446 (5)): forms, menus */
--control-h-touch: 2.5rem /* 40px: a dock under a coarse pointer */
--topbar-h:     2.75rem /* 44px, the top bar (was 64) */
--control-h-body: 2.25rem /* 36px, the composers' rows (Capture, Writing room, Ask, Chat, a document's AI card), was a literal 2.5rem */
--target-min:   1.75rem /* 28px; 2.75rem (44px) under a coarse pointer or below 820 */
```

**Measured against native references** (`scratchpad/ui-sweeps/density.js`,
1440x900): 36px was the commonest control on every tab, against 28 to 32px
in Apple Notes, Things, Linear and Obsidian. The top bar's tabs and the
Notes and Library sub-tab strips are segmented controls with their labels at
`--text-md`; the top bar is 44px (Phase 12; was 64, before that 56). (Corrected 2026-10-05, audit
FE-15: these segments measure 36px, not `--target-min`.)

**The heights each role takes, measured** (audit 2026-10-05, FE-15,
a height census at 1440 over every tab and Settings pane). This is the contract
a new control is held to; a role gaining a height is a finding.

| Role | Height | Where |
| --- | --- | --- |
| Icon-only button | 28 (`--target-min`) | everywhere outside a dock |
| Any control in a dock | the dock's `--control-h`, 28 (`--control-h-dense`; 40 under touch) | one height per bar |
| A dock's segment | 24, inset to the bar's 28 (FE-14, Phase 12) | view toggles, Edit and Read |
| Ghost or filled button | 32 | dialogs, cards, panes |
| Tab strip | 36 (the top bar's tabs 32 in a 2px well) | the top bar |
| Sub-tab strip (`.tabs-line`) | 28 (`--control-h-dense`; 44 under touch), hover a grey 2px underline | Notes, Library, the document sidebar |
| Chip | 24 painted, a 28 target (`::after` overhang, FE-14) | categories, tags |

One more thing has to match for a row of controls to read as a strip rather
than as a pile: **their height.** The chat dock declares `--control-h` and
every select, button and segmented control in it is that tall.

It is deliberately *not* a spacing token. A hit target is a control's own size
(the role `--radius` plays for corners), and snapping it to a gap step would
make it move with the density setting, which is not what density is for.

The failure it prevents is the one this whole document is about: the segmented
control brought its own padding and stood four pixels taller than the selects
beside it. Nothing lines up, no edge agrees with another, and the row reads as
assembled rather than designed, the "slop features joined together" complaint
in miniature, at four pixels.

### And zero the margins, not just the heights

Reported after the first attempt, which had matched the heights and looked
fine in the stylesheet: *"some are higher or lower than each other and
different heights."*

**A margin on a flex item is centred with the item.** `.seg` carries
`margin-bottom: 0.5rem` from the stacked forms it was built for, and under
`align-items: center` those 8px do not become a gap, they sit the control 4px
*above* its neighbours and make its group 8px taller, which pushes the next
group 4px down in turn. Two visible offsets, from one declaration in a rule
three thousand lines away.

> **The rule:** a row of controls neutralises the outside spacing its controls
> arrive with (`margin: 0`), and the row's own `gap` is the only thing between
> them. Anything else means every control added later has to be checked
> against every base rule that might have given it a margin.

The same applies to a control's own vertical padding: keep it horizontally,
give it up vertically, and let the declared height decide.

Where a row's box grows (a chat composer with an autogrowing textarea), align
to `end` rather than `center`, so the buttons stay level with the line the
caret is on instead of drifting up the side of it.

### Where this is applied

The pixel figures in this list (45px, 36.8px, 2.3rem, 40px) are what each
row measured on the day it was fixed, at the old 36px control; the rule they
illustrate stands, and every one of these rows now reads `--control-h`
(32px) or `--control-h-body` (36px).

Not every toolbar has been through this yet, treat a row that hasn't as a
gap, not as a deliberate exception, and give it its own `--control-h` before
adding a control to it:

- `.chat-dock-controls` (`04-chat-dock-appearance.css`), the original.
- `.graph-toolbar` (`03-dashboard-widgets.css`), shared by the Graph and
  Timeline tabs' primary rows. Added after measuring a real ~15px gap
  between the search/select controls (45px, from the global form-field rule)
  and the buttons beside them (~30px), close enough to pass a glance, wrong
  enough to fail a ruler. Covers `select`, `input[type=text|search]`,
  `button`, and `.segmented-control` so a text input, a select, a button and
  a segmented radio group can all sit in the same row and read as one strip.
- `.graph-options` / `#timeline-options` (`03-dashboard-widgets.css`), the
  folded-away "tuned once" panels behind each tab's Options button. Only
  `button` is height-locked here; sliders and switches are deliberately their
  own native size rather than stretched to match, since forcing a slider
  thumb to a button's hit-box height would misrepresent it as clickable
  chrome rather than a drag control.
- `.library-toolbar` (`00-tokens-shell.css`), shared by the Library tab and
  the Notes tab's "All entries" row (`#browse` in `index.html`; same class,
  reused markup). The rule covered `.library-search`, `select`, `.seg` and
  `.seg button`, but Notes' own toolbar adds two plain `<button class="ghost
  small">`s (`#select-btn`, `#search-help`) that Library's own toolbar
  doesn't have, not inside a `.seg`, so the selector list missed them.
  Measured at 30.39px against the row's 36.8px (`2.3rem`) `--control-h`,
  the same failure shape as `.graph-toolbar`, just the buttons short instead
  of the inputs tall. Fixed by widening `.seg button` to plain `button`,
  which covers both without duplicating a rule.
- `.capture-field-row` (`07-whiteboard-misc.css`), `.draft-controls`
  (`04-chat-dock-appearance.css`) and `.ask-query-row`
  (`07-whiteboard-misc.css`), the Notes tab's Capture, Write-with-AI and
  Ask panels, none audited before this round. All three had the same
  three-heights-on-one-row shape: a `select`/`input` at the global 45.19px
  form-field height, a plain `button` at 40px, and a `.ghost` button at 42px
  (the border, under `box-sizing: border-box`). `2.5rem` (40px) rather than
  the toolbars' `2.3rem`, since these rows carry full-size `Save`/`Draft it`
  actions, not a `.small` toolbar strip.
- `#batch-bar` (`02-chat-graph.css`), the Notes tab's select-mode batch
  action row (`Move to…` / Move / Tag / Delete / Done). The category select
  (45.19px), `.small` `Move` (28.39px) and `.ghost.small` `Tag`/`Delete`/
  `Done` (30.39px) were three more heights on one row. `2rem` here, since
  every control is already `.small`.
- `#reminder-magic-row` (`05-sidebars-themes.css`), the Reminders tab's
  natural-language add row. Smaller than the others (it was a 44px
  `textarea.autogrow` against a 42px `.ghost` `Add` button, 2px) but the same
  shape, fixed by matching the button's height to the textarea's own
  `min-height: 2.75rem`: both are 44px now, and `textarea.autogrow`'s floor is
  shared with the capture box, which has its own 11rem floor above it.
  The tab's main `.reminder-form` row and the filter `.seg` were already
  correct, checked, not assumed, before moving on.

`.doc-toolbar`'s two rows (`04-chat-dock-appearance.css`), the Documents
editor's metadata/actions row and its formatting-button row, named as an
open question in an earlier HANDOVER entry, were measured and are
**already correct**, not a missed instance. The formatting row's buttons are
uniform 29.19px. The metadata row's title input (45.19px) sits beside a
`row space-between`-justified stats/actions group, not edge-to-edge with
it, a `space-between` title-left/actions-right header, not a strip of
controls sharing one boundary, so a height difference there doesn't read as
misalignment the way it does within `.doc-actions` itself (which is
internally uniform, all `.ghost.small`).

---

## What is not done yet

Recorded honestly, because this document should not read as further along than
it is.

- **The test suite cannot see the interface.** Spacing, type, corners and the
  recipe index are held by lints (`tests/test_style_scale.py`,
  `tests/test_ui_recipes.py` and the others named above), and the standing
  sweeps in `scratchpad/ui-sweeps/` measure a running app with
  `getComputedStyle` and `getBoundingClientRect`. A change to a surface is
  still driven in a real browser before it is called done. **Look at what you
  change; it costs a minute.**
- **Reduced motion is honoured per component.** Density is a multiplier over
  the spacing scale and duration is the `--motion-*` scale above, but
  `prefers-reduced-motion` is still a set of `@media` blocks in the stylesheets
  that need one, not a single rule.
- **Documents has no tab of its own, on purpose.** It was a tab once and moved
  back: the complaint it answered was about being conflated with the Library's
  catch-all view, so Documents now has a view of its own inside the Library. The
  tab bar holds seven tabs and is at the width where another one hurts, so a
  new top-level surface needs a decision about what it absorbs, or how the bar
  overflows, before it is built.
- **Per-surface design work is in the plans.** The Documents, Graph, Timeline,
  Whiteboard, Chat and Mind map plans in `docs/roadmap/` each say what exists,
  what disappoints and what comes next; this file holds the rules they are
  held to, not their backlogs.

---

## The principles this system is an implementation of

Added after a direct instruction: *"I shouldnt be having to tell you to
consider all these ui/ux principles, they should be part of design.md and
you should be sticking to them throughout development."*

That is correct, and the four sections above (spacing, type, corners,
control height) are already three of the four classical CARP principles
wearing implementation names. Naming them, adding the fourth, and, where
possible, giving each a **number a session can measure itself against** is
what this section is for. A principle with no measurement is a preference;
a principle with one is a check.

### C: Contrast

Contrast is what makes a thing look like what it is. The palette carries it
(`--ink` vs `--muted`, `--accent` vs `--chip-bg`), and the failure mode here
has never been "not enough colour", it is **two things that differ slightly
for no reason**, which reads as an accident rather than a distinction.

> **The rule:** if two things are different, make them clearly different. If
> they are the same kind of thing, make them identical. Nothing in between.

Text contrast is 4.5:1 minimum for body copy (WCAG AA), 3:1 for large text
and for the boundary of a control you are meant to find. `--muted` on
`--card` is the pair to check when adding a theme. **Dim by colour, never by
`opacity`**: a label at 0.6 or 0.75 opacity over a light card fell to 3.2 to
4.2:1 (INBOX 433); `--muted` is the quiet colour that still passes.

**Non-text contrast is measured too** (WCAG 1.4.11, 3:1; INBOX 464, "there is
still some colour contrast issues"). `contrast.js` reads text only; `contrastui.js`
reads icon glyphs (with the opacity of every ancestor folded in), icon-sized
SVGs, focus rings (also a wrapper that takes the ring), field, select and
checkbox edges, toggle tracks, a selected segment against its well, interactive
chip edges, and the text outside `.tab-page` (the header, the tab bar). Same
ground rule as `contrast.js` (translucent layers composited, a gradient ground
counted as skipped, never passed), hover read off (the pointer is parked), no
transitions. Run it at 1440 and 390, `THEME=dark`, `CONTRAST=on`, and
`LOOK=<preset>` for the other looks. Measured on the default look, same data, before
and after (INBOX 464): 1440 light 79 findings (37 field edges, 25 selected
states, 6 bare writing surfaces, 6 chips, 3 focus rings, 1 SVG icon, 1 icon),
1440 dark 74, 390 light 51, 390 dark 49, `CONTRAST=on` 79 and 74; after, 0 in
every category except the 4 to 6 bare writing surfaces, which are counted
apart (recipe index, "The edge of anything you aim at").

**WCAG 2.2 AA is the bar** (the level Australian government guidance points
to). Three sweeps check it against a running app, each saying what it cannot
see: `scratchpad/ui-sweeps/axe.js` (axe-core over every tab, sub-tab and
Settings section, both themes), `zoom.js` (200% and 400% reflow, WCAG text
spacing, focus not obscured) and `srtree.js` (Chromium's accessibility tree:
landmarks, headings, live regions, the skip link, dialog focus). No real screen
reader runs in the sandbox; what NVDA, JAWS or VoiceOver say aloud is not
verified by any of them. `tests/test_a11y_wcag22.py` pins what they found.

### A: Alignment

**The weakest part of this app, measured.** Count the distinct left edges of
every visible element wider than 120px on a screen; a composed layout has
two to four. Measured at 1440×900:

| Screen | Distinct left edges |
| --- | ---: |
| Dashboard | **37** |
| Graph | **35** |
| Notes | **32** |
| Library | **25** |
| Reminders | **16** |
| Chat | 13 |
| Timeline | 9 |

Thirty-seven means essentially nothing lines up with anything, and it is the
most likely single cause of *"it feels fake and unprofessional but I cant
place it"*, misalignment is felt long before it is seen.

> **The rule:** every element sits on an edge something else already
> established. A new element that needs a new left edge is a sign the layout
> wants a grid, not that the element wants a margin.

This is the acceptance criterion for the shell work in
[roadmap/REDESIGN.md](roadmap/REDESIGN.md) §R6 item 6: **if a change does not
reduce that count, it did not fix the thing it was for.**

### R: Repetition

The token scales *are* repetition, and `tests/test_style_scale.py` enforces
them. The gap they did not cover was **control size**, because a class can
be consistent in its declarations and still render at five heights.

Measured before `--target-min` existed: `button.small` (the most-used
control class in the app) rendered at **19, 24, 25, 26 and 30px**, decided
entirely by whether a given button held an icon, a word, or both. Five
heights for one class.

> **The rule:** a control class declares a height (or a floor). Content never
> decides how tall a control is.

### P: Proximity

Related things sit together; unrelated things get a gap. The failure here is
the one the Library screen had: six stat tiles and, directly beneath them,
the same six filters as chips, *adjacent* but not related, because they
were the same control twice.

> **The rule:** before adding a control, find the one that already does it.
> Proximity is meaningless if the neighbours are duplicates.

---

## Voice

One voice, so labels do not read as three people's work (UI modernisation,
Phase 6). Measured before this was written: "No saved chats yet, ask
something!" beside "Nothing of this kind yet." beside "Your notebook is
empty, capture a thought to begin": three tones for one situation.

- **Sentence case** everywhere except eyebrows (`.card h3`, the nav group
  labels), which are the one uppercase recipe.
- **Verbs on buttons**: "Save current look", "Reset to default", "Add",
  "Move to bin". Never "OK", never a noun on its own where a verb fits.
- **No exclamation marks.** Nothing in this app is that exciting.
- **An empty state is one component**: `.empty-state` with an `.empty-icon`,
  an `.empty-title` that says what *would* be here, one sentence saying how
  to get it, and, where a single action exists, one button. Not a grey
  line.
- **Errors say what to do next**, inline under the control that failed;
  toasts are for background work finishing. "Ollama isn't reachable: check
  Settings, Models and try again." (the exact string `skill_runner.py`
  raises), not "Error".
- **Say the thing, not the mechanism.** "Reading the model's own
  specification…" is fine; "Fetching /models/spec" is not.
- **The notebook is "your notebook"; the model is "the AI" or "the model",
  never "I".** The app narrates; the model speaks in the chat and nowhere
  else.

### Glossary: one word per thing

The audit of 2026-10-05 (UX-20) found one object under three names: "Move to
bin", "Moved to the recycle bin.", "Include the bin", a Settings heading
"Recycle bin". The words below are the ones the interface uses; a new string
uses them, and `tests/test_ux1005_copy.py` holds the first of them as a lint.

| Thing | Say | Not |
| --- | --- | --- |
| Where deleted things wait | **the bin** ("Move to bin", "Moved to the bin.", Settings' heading "Bin") | "recycle bin", "trash" (both stay as palette keywords, so typing them still finds it) |
| A tree of topics round one idea, each topic a note | **mind map** | "concept map" (MINDMAP_PLAN 15 row 2 retired the second name; `tests/test_terms.py` holds it over `index.html`, the palette and create rows and the Guide) |
| Notes, Ask: an answer quoted from your notes | **Ask** | "Ask AI" for a no-model surface |
| The tool-calling assistant over any tab (the status bar's Agent button, Ctrl+Shift+A) | **Agent** | "Ask" |
| The app's own help assistant | **Atlas** or **the Guide** | "the agent" |

## Two columns of reading: the Ask results grid

Decided 2026-10-05 (op4-1005, OPEN.md ask-head-ocr). A panel that holds
prose to read, an answer beside its sources, is two columns only from 1100
(UI_MODERNISATION_PLAN Phase 9's band, where the sidebar opens) and one
column below it. Measured (`#chat-results` with two columns): each half was
262px at 820, 360 at 1024 and 397 at 1099, 30 to 45 characters a line, and
the answer's head ellipsised a model id; from 1100 a half is 363 to 529px.
The breakpoint is `@media (max-width: 1099.98px)` on `.chat-grid`
(01-forms-settings.css), on the Phase 9 set `tests/test_breakpoints.py`
holds. A future two-column reading surface takes the same band.

## Hit targets: `--target-min`

```
--target-min: 1.75rem   /* 28px, the floor under every interactive thing */
```

**Icon-only buttons are measured, not listed** (0.3.3): a button with an
icon and no words is only recognisable in a browser, so
`scratchpad/ui-sweeps/iconfloor.js` (in `gate.sh --sweeps`) walks every tab,
a document, a board and Settings in a touch context and fails on any under
44px: 296 measured at 1024, 106 at 390, none under.

Distinct from `--control-h`, and the difference matters: `--control-h` is a
**strip's** declared height, scoped per toolbar, and exists so a row reads as
one strip. `--target-min` is a **global floor** that applies to a control
wherever it sits, including the many that belong to no strip.

WCAG 2.2 AA ("Target Size (Minimum)", 2.5.8) sets 24×24 CSS px. 28px clears
it with room for a border. Measured violations before this token existed:

- `#semantic-search-toggle`, `#library-semantic-toggle`,
  `#library-show-binned`: **32×18**.
- The reminder rows' checkboxes, **13×13**, barely half the floor and
  genuinely fiddly with a trackpad.

**A finger gets 44px wherever it is** (INBOX 392). The token is 2.75rem
below 820 **or under a coarse pointer at any width**: every touch-floor
block is written `@media (max-width: 819.98px), (pointer: coarse)`, because
width is a proxy for the pointer and it fails at 1024, which is an iPad in
landscape (measured with a touch context at 1024x768: search boxes, sub-tabs
and dock buttons at 36px, status items at 28). A block that also changes
layout stays width-only; the floor is split out of it. A mouse at 1024 keeps
28. `tests/test_ui_recipes.py` holds the `:root` declaration to that query.

A `min-height`, never a `height`, so a strip declaring a taller
`--control-h` still wins and a control that wraps to two lines still grows.
**Not a spacing token**, for the reason the control-height section already
gives: a hit target must not move with the density setting.

The one deliberate exception is a control drawn by a sibling, the switch
pattern, where the input is clipped to nothing and the switch is the real
target. Those are excepted by name in `01-forms-settings.css`, not by
accident.

**The painted switches are still 32×18.4, and that is honest rather than a
gap** (MODERNISATION_AUDIT.md Brief 8 measured the three ids above at
32×18.4 after this section first claimed them fixed). The pill's paint must
stay that size, a `min-height` on the input made it a 32×28 slab with the
knob adrift, reported within the hour, so the *target* is a transparent
`::before` on the input that overhangs the pill by 6.4px above and below
(`07-whiteboard-misc.css`): `elementFromPoint` 4px outside the pill returns
the input, and the pill looks exactly as it did.

**An interactive chip is the same pattern** (audit 2026-10-05, FE-14): the
category, "Add tags" and references chips on a card paint 24px, a row of
pills, and take `--target-min` through a transparent `::after` overhang
(`.chip-interactive::after`, `01-forms-settings.css`; `inset-block`, no
transform). A chip that shrinks with its row is clipped across only
(`overflow: clip visible`), or the overhang is clipped with it.
`scratchpad/ui-sweeps/perf2-1005-chipfloor.js` measures the target with
`elementFromPoint`: 0 under the floor at 1440, light and dark.

**One overhang rule, three users** (audit 1029 rank 46): `.chip-interactive`,
"Show more" (`.entry-more`) and a card's menu buttons (`#entry-list
.menu-wrap > button`) share the `::after` in `01-forms-settings.css`, on both
axes. A chip that is clipped across (`overflow: clip visible`) keeps it; a
`hidden` one cuts it off. Wrapped pills keep `--target-min` minus their paint
apart under a coarse pointer (`#entry-list .entry-links`), or the overhangs
steal each other's box. A search well's input stretches to the well
(`align-self: stretch`), the graph's hit slop is 20px under a coarse pointer
(`GC_SLOP_PX`, 6 otherwise), and the legend is one Tab stop with arrow keys.

---

## Motion: and the one rule that is not optional

Durations come from the `--motion-*` scale. Beyond that:

> **Every indefinite animation needs a `prefers-reduced-motion` branch, and
> the branch keeps the information.** Stopping a spinner is right; removing
> the thing it was telling you is not.

Both animations added in this pass follow it: the working ring (`.spinner`)
keeps its place and breathes instead of turning (a slow opacity pulse, the
one movement that travels nowhere), and the streaming caret stays visible and
stops blinking. Someone who asked for less motion is the person least able to
infer "this is still loading" from text quietly appearing. The ring used to
be swapped for a still "…" here, which took the sign away with the motion.

### And the one that costs money on someone else's phone

> **An animation moves `transform` or `opacity`. It does not move `width`,
> `height`, `top`, `left`, `margin` or `padding`.**

Those six make the browser lay the whole page out again on every frame, and
the frames an animation runs on are the ones already least affordable: a cold
boot, a scroll on a phone, a laptop on battery. `transform` and `opacity` are
handed to the compositor, which does not lay anything out.

The difference is measured here, not assumed. `scratchpad/ui-sweeps/animcost.js`
counts the layouts the boot splash's progress bar forces over its 2.4s crawl:
121 when the bar animated `width`, 0 once it became a full-width box scaled
from a left origin, with the same painted geometry to the tenth of a pixel.

The recipe for a bar that fills, since that is the case this keeps coming up
for: the **track** keeps the geometry, the border, the rounded ends and
`overflow: hidden`; the **fill** is `width: 100%` with no radius of its own and
`transform: scaleX(<fraction>)` from `transform-origin: left`. The fill must
not carry the rounded ends, because a scaled box scales its radius into an
ellipse.

`tests/test_cheap_animations.py` fails a `transition` or `@keyframes` that
names one of those properties. The way past it is a reason in a `/* ... */`
comment on the line above, and there is one in the app: `#phone-tab-dock`
(10-responsive.css) really does change size with content inside it, where
`translateY` would take the bottom off a 44px touch target and `scaleY` would
squash the icons. `box-shadow` is not covered, on purpose, and the lint's own
docstring says why.
