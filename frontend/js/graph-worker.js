// Tessellate: the graph's force simulation, off the main thread.
//
// GRAPH_PLAN.md §4 ("Simulation off the main thread") and §5 Phase 1. The SVG
// renderer this replaces ran `d3.forceSimulation` on the main thread and wrote
// thousands of DOM attributes per tick, so the simulation and the pointer
// fought for the same thread and a drag stuttered. Here the simulation owns a
// worker, and the main thread only ever paints what this posts.
//
// **d3 is vendored, and `importScripts` is what a classic worker has.** The
// app ships `/vendor/d3.v7.min.js` (no CDN: the offline rule), it is a UMD
// bundle, so `importScripts` puts `d3` on this worker's own global. The CSP
// already allows it: `worker-src 'self'` is set in
// `src/tessellate/core/security.py` (checked before writing this, not assumed, 
// a directive missing there fails silently, which is the "policy silently
// refusing the work" shape CLAUDE.md names).
//
// ---------------------------------------------------------------------------
// The protocol, in both directions. Kept small on purpose: every message is
// structured-cloned, so anything that travels per frame has to be a buffer.
//
// In:
//   {type:"init", nodes:[{id,x,y,fx,fy,r}], edges:[{source,target,kind,score}],
//    params:{gravity,spread,lengthByScore}, world:{left,top,right,bottom}, alpha, epoch}
//       Replace the whole simulation. `id` is only used to map the drag/pin
//       messages below onto array indices; positions travel by index alone.
//       `epoch` is echoed on every message this run produces: see "Out".
//   {type:"params", params:{gravity,spread}}      re-tune without a rebuild
//   {type:"drag", phase:"start"|"move"|"end", id, x, y, keep}
//       start -> alphaTarget(0.3) and pin; move -> move the pin; end ->
//       alphaTarget(0) and, unless `keep`, release the pin at once into a
//       low heat (`RELEASE_ALPHA`), so the note settles near where it was put.
//   {type:"freeze", ids:[...]} / {type:"thaw"}
//       Hold everything else still for the length of a drag, the same
//       "aiming at a moving target is not a gesture" fix the SVG renderer
//       carried, kept because drag-to-link still depends on it.
//   {type:"pin", id, x, y} / {type:"unpin", id}   double-click hold / release
//   {type:"reheat", alpha}                        nudge a settled layout
//   {type:"reshuffle", seed, animate}             a new arrangement: see below
//   {type:"stop"}                                 leave the tab
//   {type:"recycle", buffer}                      hand a position buffer back
//
// Out:
//   {type:"tick", positions:Float32Array (transferred), alpha, running, epoch}
//       x,y interleaved, one pair per node, in the order `init` supplied.
//   {type:"end", alpha, epoch}
//                         the layout has settled; no further ticks are coming
//                         until something reheats it.
//
// **Why every message out carries the `epoch` its `init` came with.** Both
// directions of `postMessage` are asynchronous, so `{type:"stop"}` cannot
// unsend a tick that has already been posted: it clears the timer here and
// the tick sitting in the main thread's queue is still delivered afterwards.
// The main thread applies positions *by index*, so a tick from the previous
// simulation landing after the node array has been replaced writes the old
// solution over the new one. That is what a tree drawn as a scatter is, and
// it is why it happened only when the layout was switched while the force
// simulation was still warm. The epoch lets the reader of a message decide
// whether it is still about the graph on screen.
// ---------------------------------------------------------------------------

importScripts("/vendor/d3.v7.min.js");

let simulation = null;
let nodes = [];
let indexById = new Map();
let world = null;
let timer = null;
let dragging = false;
//: **A dropped note settles near where it was put** (INBOX 802, the owner:
//: "drag parts of the graph to different areas of the graph and have it kinda
//: settle into place there"). Released at the drop's full heat, its links
//: and its category's pull took it straight back (a note dropped 286px away
//: was 268px back within a second); held until rest, it never moved again
//: (2026-10-11). It is let go on release into a low heat instead.
//: The heat a released drag leaves the layout at: enough for the dropped
//: note and its neighbours to ease into place, too little for its links to
//: haul it back across the map.
const RELEASE_ALPHA = 0.016;
const RELEASE_ALPHA_MIN = 0.01;
// Performance mode (init.perf): the loop rests twice as long between ticks.
let perf = false;
let ticks = 0;
let epoch = 0; // whose `init` the messages going out belong to (see the protocol note above)
//: A rolling mean of how long one `simulation.tick()` takes, in ms. Reported
//: on every frame because it is the number that decides everything else: it
//: says whether a slow-feeling map is the simulation, the paint, or the
//: machine, and guessing between those three cost a round of theorising.
let tickMs = 0;

//: Buffers handed back by the main thread after it has painted them. A
//: transfer neuters the sender's copy, so without this every frame allocates a
//: fresh Float32Array: 2,000 nodes is 16 KB a frame, 60 times a second, which
//: is a megabyte of garbage a second for nothing. The main thread returns each
//: buffer in a `recycle` message; if the pool is empty (it has fallen behind)
//: we allocate rather than block.
const pool = [];

//: How many posted frames the main thread has not yet recycled. Ticking is
//: cheap and posting is not, so when it is behind we keep simulating and skip
//: the paint: the next frame it does receive is the current truth anyway.
let inFlight = 0;
const MAX_IN_FLIGHT = 2;

//: The physics, and why each number is this number.
//:
//: `velocityDecay 0.4` is the plan's (§5 Phase 1). d3's default is 0.6, which
//: is molasses: a dragged node's neighbours barely move before the step is
//: over, which is exactly the "the physics is tuned for a demo" complaint in
//: §2. 0.4 lets a neighbourhood follow a drag and still settle.
//:
//: `alphaDecay 0.0228` is d3's own default, restored deliberately, the SVG
//: renderer used 0.05 (settle in ~90 ticks) *because* every tick cost it
//: thousands of DOM writes on the main thread. Off the main thread that
//: trade is gone, and a slower decay is what makes the layout look alive.
const VELOCITY_DECAY = 0.4;
const ALPHA_DECAY = 0.0228;

//: **A layout ends, whatever the notebook's size** (audit 2026-10-05, FE-04).
//: At 0.0228 a layout takes about 300 ticks to cool below `alphaMin`; a tick
//: on a 5,000-note map is 70 to 240 ms and the loop rests as long again, so
//: the map was still moving after 30 s and the tab idled at 44% of a core,
//: repainting every tick. Two bounds now:
//:
//: - past `SETTLE_FULL_TICKS_UP_TO` notes the decay is set so the layout
//:   cools in `SETTLE_TICKS_BIG` ticks (d3's own formula for a decay that
//:   reaches alphaMin in n ticks), which a big map can afford;
//: - and whatever the size, `SETTLE_BUDGET_MS` after the last thing that
//:   moved it (an init, a drag released, a reheat), the loop stops and says
//:   `end`, as if it had cooled. Nothing is lost: a drag or a reheat starts it
//:   again from where it stands.
const SETTLE_FULL_TICKS_UP_TO = 1500;
const SETTLE_TICKS_BIG = 120;
const SETTLE_BUDGET_MS = 20000;
let settleFrom = 0;

function alphaDecayFor(count) {
  if (count <= SETTLE_FULL_TICKS_UP_TO) return ALPHA_DECAY;
  const ticks = Math.max(SETTLE_TICKS_BIG, Math.round((300 * SETTLE_FULL_TICKS_UP_TO) / count));
  return 1 - Math.pow(0.001, 1 / ticks);
}
//: The alphaTarget a drag raises the simulation to, and the plan's number.
//: High enough that the neighbourhood reorganises around where you put the
//: node, low enough that the rest of the map is not thrown into the air.
const DRAG_ALPHA = 0.3;
//: **A small pull heats a small part of the map** (INBOX 839, the owner:
//: "small adjustments and graph nodes being pulled in slightly are glitchy and
//: jittery, not smooth"). Raising the target to 0.3 the moment a node is
//: pressed reheated all 34 notes of a test map for an 8px nudge: every one
//: moved more than 2px, the busiest travelled 52px and a frame stepped 3.7px
//: (measured, graphjitter.js). The target now follows how far the node has
//: been carried from where it was pressed: `DRAG_ALPHA_MIN` for a nudge, the
//: full 0.3 once it is `DRAG_FULL_DISTANCE` world units away, eased between,
//: and the alpha only ever rises to it, so a release still decays.
const DRAG_ALPHA_MIN = 0.04;
const DRAG_FULL_DISTANCE = 90;
//: **A dragged note's own neighbours follow it** (graph100-1011, "neighbours
//: barely follow a drag": 20 to 50 of the 340 units the note in hand moved,
//: because each neighbour's pull toward its category outweighed one link). For
//: the length of a drag the notes it links to keep this share of their pull
//: home and are off the tether, and a soft elastic (`carryForce`) draws each
//: toward where it stood relative to the held note; on release both are gone
//: and the layout settles them as before. Measured on the real worker (200
//: notes in 7 categories, six notes of 4 to 6 links dragged 340 units and held
//: 90 ticks): neighbours moved 102 of 340 before, 208 after; 156 against 81
//: once settled after the drop. In the app (graphdrag1018.js, 200 notes, a
//: 308 unit drag held 1.5 s): 0.28 of the distance before, 0.48 after; 0.28
//: against 0.40 once settled (tests/test_graph_neighbours_follow.py).
const FOLLOW_PULL = 0.25;
const CARRY = 0.2;
const carry = { node: null, followers: [] };
function markFollowers(node, on) {
  carry.node = on ? node : null;
  carry.followers = [];
  const links = simulation && simulation.force("link") ? simulation.force("link").links() : [];
  for (const link of links) {
    const other = link.source === node ? link.target : link.target === node ? link.source : null;
    if (!other || typeof other !== "object") continue;
    other.following = on;
    if (on && other.fx == null) carry.followers.push({ node: other, dx: other.x - node.x, dy: other.y - node.y });
  }
}
//: The links alone leave a neighbour behind (40% of the carry at 90 ticks), so
//: while a note is held each follower is also drawn toward where it stood
//: relative to it, a soft elastic, not a rigid carry: the links and the charge
//: still shape the neighbourhood around it.
function carryForce(alpha) {
  const held = carry.node;
  if (!held) return;
  const hx = held.fx != null ? held.fx : held.x;
  const hy = held.fy != null ? held.fy : held.y;
  for (const f of carry.followers) {
    if (f.node.fx != null) continue;
    f.node.vx += (hx + f.dx - f.node.x) * CARRY * alpha;
    f.node.vy += (hy + f.dy - f.node.y) * CARRY * alpha;
  }
}
carryForce.initialize = () => {};
let dragOrigin = null;
function dragHeat(x, y) {
  if (!dragOrigin) return DRAG_ALPHA;
  const t = Math.min(1, Math.hypot(x - dragOrigin.x, y - dragOrigin.y) / DRAG_FULL_DISTANCE);
  return DRAG_ALPHA_MIN + (DRAG_ALPHA - DRAG_ALPHA_MIN) * t * t * (3 - 2 * t);
}
//: **A fresh layout is warmed before it is shown** (INBOX 738, the owner:
//: "the graph always loads in really zoomed in before it rights itself with
//: the fitted zoom"). The notes start on a small spiral and spread over a few
//: hundred ticks; the first fit framed the spiral (k 2.5, the clamp) and the
//: camera then pulled back to k 0.79 as the map spread. Asked for by `init`
//: (`warm`, only while the canvas is still hidden for its first fit), the
//: worker steps without posting until the layout is at rest and untangled
//: (`pending`, `introInto`) or the budget is spent, so the first frame anyone
//: sees is framed on the settled shape. A small or middling notebook is
//: there inside the budget; a big one spends it and eases out the rest of
//: the way, as before. `WARM_ALPHA` (the main thread's own 0.08) is where a
//: live layout's cooling starts to take several ticks a frame (`loop`).
const WARM_MS = 1200;
const WARM_ALPHA = 0.08;
//: **The warm-up is then shown, not skipped** (INBOX 775, the owner: "I
//: prefered the force and movement how the graph used to be, theres no
//: movement to it now" and "when the graph readjusts it just appears
//: there"). Warming out of sight fixed the zoomed-in first frames and took
//: the motion with it: measured on 34 notes, a node travelled 26 px on
//: screen after the reveal, all of it the last drift. With `intro` (the main
//: thread asks for it unless the reader wants less motion) the warm-up's
//: own ticks are kept and played back, one a frame as the live layout
//: steps (the owner, round 2: "look at how the movement is in main"; main's
//: live settle and this playback have the same physics at the same pace),
//: once the camera is framed on where they end (`frame`, posted first).
const INTRO_FRAME_MS = 16;
//: The first frame is held this many frames while the canvas fades in, so
//: the start of the movement is seen rather than spent behind the fade.
const INTRO_HOLD = 8;
//: Positions kept for the playback, in floats: past this a big map's
//: warm-up is not recorded (it spends its budget in a few ticks anyway,
//: and the live layout is what moves).
const INTRO_MAX_FLOATS = 2000000;
const intro = { frames: [], alphas: [], shown: null };

//: **The settled map is the last frame, and the playback flows into it**
//: (the owner, 2026-10-27: "the opening of the graph is very very not
//: plesant to look at all the adjusting and it is very ridgid and
//: mechanical. I want it to be smooth and flowy"). The warm-up now goes all
//: the way: cooled to rest, untangled and cleaned (`settleUntangled`, run in
//: slices by `pending`) before the first post, inside `WARM_MS`. The
//: playback then starts near that map,
//: a little drawn in about its middle (`BLOOM`) behind the fade, or from
//: where the notes stood on a map already showing, and lets the forces move
//: it, one tick a frame, while each frame is drawn toward the settled map by
//: a smoothstep (`frame = physics + (settled - physics) * s`): the forces'
//: own motion at the start, exactly the settled map, at rest, at the end.
//: Nothing ticks after it. A map too big to settle in the budget is shown
//: where the budget left it and cools live, as before.
const BLOOM = 0.9;
const BLOOM_ALPHA = 0.1;
const BLOOM_FRAMES = 60;
//: From where the notes stood (a relayout of a map on screen): more heat and
//: longer, since the way can be the width of the map.
const RESTART_ALPHA = 0.3;
const RESTART_FRAMES = 90;

//: The playback into the settled map the notes now stand on, from where they
//: stood (`startX`, `startY`) or, behind the fade, from the settled map drawn in.
function introInto(startX, startY, record, bloom) {
  intro.frames = [];
  intro.alphas = [];
  const count = bloom ? BLOOM_FRAMES : RESTART_FRAMES;
  if (!record || nodes.length * 2 * (count + INTRO_HOLD) > INTRO_MAX_FLOATS) return;
  const endX = nodes.map((n) => n.x);
  const endY = nodes.map((n) => n.y);
  let cx = 0;
  let cy = 0;
  for (const node of nodes) {
    cx += node.x / nodes.length;
    cy += node.y / nodes.length;
  }
  nodes.forEach((node, i) => {
    if (node.fx != null) return;
    node.x = bloom ? cx + (endX[i] - cx) * BLOOM : startX[i];
    node.y = bloom ? cy + (endY[i] - cy) * BLOOM : startY[i];
  });
  simulation.alpha(bloom ? BLOOM_ALPHA : RESTART_ALPHA);
  // The forces' own path, one tick per frame of playback.
  const path = [];
  const heat = [];
  for (let t = 0; t <= count; t++) {
    path.push(Float32Array.from(nodes.flatMap((n) => [n.x, n.y])));
    heat.push(simulation.alpha());
    simulation.tick();
    clampToWorld();
  }
  //: Walked at an eased pace (`smoothstep` of the time, so the first frames
  //: leave rest slowly: one tick a frame from the start was a 12 px step out
  //: of the hold, 36 notes) and drawn toward the settled map by the same
  //: curve, so the last frames come to rest on it.
  const frames = [];
  const alphas = [];
  for (let f = 0; f <= count; f++) {
    const u = f / count;
    const s = smoothstep(u);
    const at = count * s;
    const k = Math.min(count - 1, Math.floor(at));
    const w = at - k;
    const p = path[k];
    const q = path[k + 1];
    const frame = new Float32Array(nodes.length * 2);
    for (let i = 0; i < frame.length; i++) {
      const x = p[i] + (q[i] - p[i]) * w;
      const end = i % 2 ? endY[(i - 1) / 2] : endX[i / 2];
      frame[i] = x + (end - x) * s;
    }
    frames.push(frame);
    alphas.push(heat[k]);
  }
  nodes.forEach((node, i) => {
    node.x = endX[i];
    node.y = endY[i];
    node.vx = 0;
    node.vy = 0;
  });
  simulation.alpha(0);
  // Framed on where it ends, drawn from where it starts.
  self.postMessage({ type: "frame", epoch, positions: Float32Array.from(endX.flatMap((x, i) => [x, endY[i]])), start: frames[0].slice() });
  for (let i = 0; i < INTRO_HOLD; i++) {
    intro.frames.push(frames[0].slice());
    intro.alphas.push(alphas[0]);
  }
  intro.frames.push(...frames);
  intro.alphas.push(...alphas);
}

//: One frame of the playback. While the main thread is behind, the frame is
//: kept for the next turn rather than dropped.
function introStep() {
  if (inFlight > MAX_IN_FLIGHT) return;
  const frame = intro.frames.shift();
  const alpha = intro.alphas.shift();
  intro.shown = frame.slice();
  inFlight += 1;
  self.postMessage({ type: "tick", epoch, positions: frame, alpha, ticks, tickMs, running: true, intro: true }, [frame.buffer]);
}

//: A playback stopped part way leaves the notes where it showed them, so a
//: drag starts from the map on screen, not from the settled one under it.
function introCancel() {
  if (intro.frames.length && intro.shown && intro.shown.length === nodes.length * 2) {
    untangle.holding = false;
    nodes.forEach((node, i) => {
      if (node.fx != null) return;
      node.x = intro.shown[i * 2];
      node.y = intro.shown[i * 2 + 1];
    });
  }
  intro.frames = [];
  intro.alphas = [];
  intro.shown = null;
}
//: Collide radius = the node's drawn radius + this. The SVG renderer used
//: +24, which on a 2,000-note map is a collision field an order of magnitude
//: wider than the node and pushes the layout into a lattice against its own
//: world walls. Six is "labels do not sit on top of each other".
//:
//: **Twelve on a notebook of up to 100 notes, easing to six by 300** (INBOX 443
//: (1), "uneven spacing"). Measured on the 60-note fixture
//: (`scratchpad/ui-sweeps/graphlook.js`), the spread of each linked dot's gap
//: to its nearest neighbour (coefficient of variation) fell with the pad:
//: 0.44 at 6, 0.40 at 12, 0.32 at 16, while crossings rose 18, 21, 24. Twelve
//: is the knee. The pad shrinks with the count because the collision field is
//: what a big map spends its span on (the +24 above): six is the number that
//: was measured for the 300 to 2,000 note fixtures (a 300-note fixture with
//: links that ignore categories drew 8,188 crossings with the pad at nine and
//: the rest of this pass in, against 6,414 before, so the easing now ends at 300).
const COLLIDE_PAD_MAX = 12;
const COLLIDE_PAD_MIN = 6;
let COLLIDE_PAD = COLLIDE_PAD_MAX;
function collidePadFor(count) {
  const n = Math.max(1, Number(count) || 1);
  if (n <= 100) return COLLIDE_PAD_MAX;
  if (n >= 300) return COLLIDE_PAD_MIN;
  return COLLIDE_PAD_MAX - ((COLLIDE_PAD_MAX - COLLIDE_PAD_MIN) * Math.log2(n / 100)) / Math.log2(3);
}

//: **How far the map spreads, and why it must depend on how many notes there
//: are.** Reported as "the max gravity in the graph is quite separated", and
//: measured before touching anything (35 notes, settled, default sliders:
//: world box 721x760, fit zoom 0.8; 300 notes: 2162x1828, fit zoom 0.3, with
//: 138 of the 300 outside the box at zoom 1).
//:
//: A fixed charge and a fixed link length give a layout whose span grows like
//: the square root of the note count, because that is how many notes have to
//: fit around each other. The fit zoom then falls the same way, and a
//: notebook of any size opens as a field of dots you have to zoom into before
//: it says anything. The layout is *right* at every size; the default view of
//: it is not.
//:
//: So the two dials are scaled by the size of the notebook: below the
//: reference count nothing changes at all, above it the repulsion and the
//: link length come down together, which packs the map without touching the
//: shape a cluster has (that is set by the local balance between the two, and
//: they move together). The floor stops a very large notebook from being
//: squeezed into a mat: past it the fit zoom has to fall, because 5,000
//: circles genuinely do not fit on a screen at 1:1.
const DENSITY_REFERENCE = 40;
const DENSITY_FLOOR = 0.3;
const DENSITY_EXPONENT = 0.42;
//: A flat trim on top of the scaling, for the small maps the reference leaves
//: alone: at 35 notes the fit zoom was 0.8, which is not "a note is a note"
//: either, it is a map framed a fifth smaller than the screen it is on.
const SPREAD_TRIM = 0.78;

//: **A link's kind says how close its ends want to be** (INBOX 443 (1)).
//: Every line but a similarity was one length, so a note filed under another,
//: a hand-made link with a reason and a loose thread all pulled the same.
//: Now: a reasoned link (somebody said why) and a thread reply sit a little
//: closer, an entity or document tie closer still, a filing or a board's
//: reference looser. The factors are small on purpose: the shape is still
//: decided by the links, this only separates the kinds by a tenth or two.
const KIND_LENGTHS = { thread: 0.9, entity: 0.9, document: 0.9, map: 1.1, filing: 1.2 };
function KIND_LENGTH(edge) {
  if (edge.curated) return 0.92;
  return KIND_LENGTHS[edge.kind] || 1;
}
//: Springs weaker for the kinds that are context rather than structure, so a
//: board's reference or a filing line does not drag a cluster out of shape.
const KIND_STRENGTHS = { map: 0.8, filing: 0.6 };
//: d3's own 1/min(degree) stays the base. A floor under it (0.15, 0.3, 0.5)
//: was measured and rejected: 0.5 evened a hub's spokes (length CV 0.38 to
//: 0.27) but took the crossings from 18 to 25, and a crossing reads worse than
//: a spoke a few pixels long.
//: Link force (GRAPH_PLAN 514 (5)): 0.2x at the slider's left, 1x at 50, 2x
//: at the right; set by `tuning`, read here.
let linkScale = 1;
//: **A line between two categories pulls less than a line inside one**
//: (INBOX 693, "clusters by category with clear space between" and "hubs
//: central"), while Group by category is on. A note that bridges two
//: categories was hauling each one's hub out to the cluster's rim, and the
//: two clusters toward each other. Measured on the 692 fixture, the hubs'
//: distance from their cluster's middle (over its mean radius) at 1, 0.5 and
//: 0.3: 0.93, 0.78, 0.55, with the 10th-percentile gap between categories
//: 114, 130, 147. As far as the links back the categories (`groupGather`):
//: on a notebook whose links ignore them, the cross lines are most of the
//: structure and keep their full pull.
const CROSS_STRENGTH = 0.3;
function crossStrength() {
  return 1 - (1 - CROSS_STRENGTH) * groupGather().t;
}
function linkStrength(edge) {
  const a = edge.source.degree || 1;
  const b = edge.target.degree || 1;
  const across = clustered() && edge.source.group !== edge.target.group ? crossStrength() : 1;
  return (1 / Math.min(a, b)) * (KIND_STRENGTHS[edge.kind] || 1) * linkScale * across;
}

function densityScale(count) {
  const n = Math.max(Number(count) || 1, 1);
  return Math.min(1, Math.max(DENSITY_FLOOR, Math.pow(DENSITY_REFERENCE / n, DENSITY_EXPONENT)));
}

//: **A small map spreads further** (INBOX 775, the owner of 34 notes: the
//: bubbles crowd each other, "node radii are large for the spacing"). Below
//: the reference count the dials were left alone, so a map of a few notes
//: was a knot the fit could only zoom into until its clamp (k 2.5): three
//: notes filled a third of the height. The link length and the repulsion
//: grow together as the count falls, up to `SMALL_SPREAD` times at three
//: notes, which keeps a cluster's shape and gives each dot room for its name.
const SMALL_SPREAD = 2.4;
const SMALL_FROM = 3;
function smallSpread(count) {
  const n = Math.max(Number(count) || 1, 1);
  const t = Math.min(1, Math.max(0, (DENSITY_REFERENCE - n) / (DENSITY_REFERENCE - SMALL_FROM)));
  return 1 + (SMALL_SPREAD - 1) * t;
}

//: How much harder the centre pulls on a big notebook. See the forces below
//: for why this exists rather than a deeper cut to the repulsion.
const CENTRE_CEILING = 6;

function centreScale(count) {
  const n = Math.max(Number(count) || 1, 1);
  return Math.min(CENTRE_CEILING, Math.max(1, Math.sqrt(n / DENSITY_REFERENCE)));
}

//: Slider (0-100, default 50) -> force. Kept here rather than on the main
//: thread so the whole physics story is in one file: `gravity` is repulsion
//: (more gravity -> weaker repulsion -> tighter clusters) and `spread` is the
//: link's rest length. Both are 1x at 50, so an untouched notebook lays out
//: exactly as the tuned defaults intend.
function tuning(params) {
  const gravity = Number(params && params.gravity != null ? params.gravity : 50);
  const spread = Number(params && params.spread != null ? params.spread : 50);
  const gravityScale = 0.4 + gravity / 41.7; // 0.4x-2.8x
  const spreadScale = 0.5 + spread / 50; // 0.5x-2.5x
  const density = SPREAD_TRIM * densityScale(nodes.length) * smallSpread(nodes.length);
  //: Reported three times now, most recently "max gravity on the graph
  //: isnt tight enough". Weaker repulsion alone cannot close the gaps
  //: *between* components, nothing links them, so they sit wherever the
  //: initial spiral left them. The centre pull is the only force that
  //: acts across a gap. Cubed rather than squared: `(gravity/50) ** n`
  //: passes through exactly 0.25 at 0 and exactly 1 at 50 for *any* n, so
  //: raising the exponent only steepens the top half of the range, the
  //: half the report is about, and leaves the untouched-default contract
  //: at 50 exact rather than approximate. 0.25x at 0, 1x at 50 (unchanged),
  //: 6.25x at 100 (was 3.25x).
  const pull = 0.25 + 0.75 * (gravity / 50) ** 3;
  const force = Number(params && params.linkForce != null ? params.linkForce : 50);
  linkScale = force <= 50 ? 0.2 + (0.8 * force) / 50 : 1 + (force - 50) / 50;
  return {
    charge: (-340 * density) / gravityScale,
    //: Length by similarity (the Show switch, on by default): a strong
    //: relation reads as a short one, 1.3x the base length at a score of 0
    //: and 0.7x at 1, the same curve the SVG renderer has always used. A
    //: line with no score keeps the base length. Until INBOX 412 this
    //: renderer was never sent a score, so the switch did nothing here.
    linkDistance: (edge) => {
      const base = (edge.kind === "similar" ? 130 : 80) * KIND_LENGTH(edge) * density * spreadScale;
      const score = params && params.lengthByScore === false ? null : edge.score;
      if (typeof score !== "number" || Number.isNaN(score)) return base;
      return base * (1.3 - 0.6 * Math.max(0, Math.min(1, score)));
    },
    //: **A portrait map gets a portrait layout** (INBOX 430, the owner: "fit
    //: the graph to the viewport's shape (more vertical in portrait)").
    //: The pull toward the centre sets each axis's spread (a layout held by a
    //: spring spreads about 1/sqrt of its strength), and the y pull was the
    //: stronger, 0.02 to 0.015, which is a slightly wide cloud: right for a
    //: desktop map, and on a 390x698 phone map measured 344x305, 44% of its
    //: height. In portrait the x pull rises with the square of the map's
    //: aspect, so the cloud comes out the map's shape; a landscape map keeps
    //: the pulls it had. Capped at 4x, past which a column of notes one
    //: node wide is not a map.
    pullX: 0.015 * centreScale(nodes.length) * pull * portraitPull() / Math.sqrt(landscapePull()),
    pullY: 0.02 * centreScale(nodes.length) * pull * Math.sqrt(landscapePull()),
  };
}

//: **A landscape map gets a landscape layout too** (INBOX 1400, the owner:
//: the force view "feels very messy"). The 430 rule shaped portrait only, so
//: on a 1440x900 desktop the 36-note seed came out 0.48 of the canvas wide
//: and 0.80 tall (`gm.js` in the 1026 remaining file): the fit was set by the
//: height and the names had half the width to share. Here the y pull rises
//: and the x pull falls by the same root, so the cloud's overall size holds
//: and only its shape changes, aimed at the canvas's shape and capped at
//: `LANDSCAPE_PULL_MAX` (past which a band of notes is not a map).
const LANDSCAPE_PULL_MAX = 3;
function landscapePull() {
  const aspect = world && Number.isFinite(world.aspect) && world.aspect > 0 ? world.aspect : 1;
  if (aspect >= 1) return 1;
  return Math.min(LANDSCAPE_PULL_MAX, Math.max(1, (0.015 / 0.02) / (aspect * aspect)));
}

function portraitPull() {
  const aspect = world && Number.isFinite(world.aspect) ? world.aspect : 1;
  if (aspect <= 1) return 1;
  //: (0.02 / 0.015) squares the two pulls level, then the aspect's square
  //: shapes it: extent ratio ~ sqrt(pullX / pullY) = aspect.
  return Math.min(4, (0.02 / 0.015) * aspect * aspect);
}

//: **Notes of a category gather** (INBOX 431 (6), the owner: the default
//: layout "looks messy and is distributed weirdly"). Measured on a
//: 150-note, 8-category fixture: every note with no link was pushed out by
//: the repulsion into a sparse ring round the whole map, a quarter of the
//: notes as loose dots with nothing to say where they belong, and a
//: category's notes were spread across the map wherever their links took
//: them. Each category now has a place on a ring round the centre, in order
//: of size, and its notes lean toward it: a loose note firmly (it has
//: nothing else to hold it), a linked one gently (its links still decide
//: its neighbourhood). Off with "Group by category" in the View menu, which
//: puts back the single centre exactly.
//: **Categories gather harder, as far as the links say they are clusters**
//: (INBOX 443 (1)). Measured on the 60-note fixture: of each dot's four nearest
//: dots, 56% shared its colour with the pull at 0.025 and anchors 22 per root
//: of the count out; 89% at 0.05 and 28, with fewer crossings (22 to 18). But
//: on a 300-note fixture whose links ignore categories the same gather doubled
//: the crossings (6,414 to 13,922): a pull toward a place the links do not go
//: is a fight. So the gather scales with `cohesion`, the share of the notebook's
//: links (not similarity lines) that join two notes of one category: the old
//: 0.025 and 22 at or under GROUP_COHESION_LOW, the new 0.05 and 28 at or over
//: GROUP_COHESION_HIGH, a straight line between. The links still decide a
//: neighbourhood's inside; this only decides where it sits.
const GROUP_PULL_BASE = 0.025;
const GROUP_PULL_TOP = 0.05;
const GROUP_RADIUS_BASE = 22;
const GROUP_RADIUS_TOP = 28;
const GROUP_COHESION_LOW = 0.2;
const GROUP_COHESION_HIGH = 0.6;
let cohesion = 1;

function groupCohesion(edges) {
  let joined = 0;
  let same = 0;
  for (const edge of edges) {
    if (edge.kind === "similar") continue;
    joined += 1;
    if (nodes[indexById.get(edge.source)].group === nodes[indexById.get(edge.target)].group) same += 1;
  }
  return joined ? same / joined : 1;
}

function groupGather() {
  const t = Math.max(0, Math.min(1, (cohesion - GROUP_COHESION_LOW) / (GROUP_COHESION_HIGH - GROUP_COHESION_LOW)));
  return {
    t,
    pull: GROUP_PULL_BASE + (GROUP_PULL_TOP - GROUP_PULL_BASE) * t,
    radius: GROUP_RADIUS_BASE + (GROUP_RADIUS_TOP - GROUP_RADIUS_BASE) * t,
  };
}
const GROUP_STRETCH_MAX = 3;

//: **Which categories sit side by side is decided by the lines between
//: them** (INBOX 693, the owner: "cross-cluster links drawn short ... no long
//: arcs spanning the canvas"). The ring was dealt by size, so two categories
//: joined by five lines could sit on opposite sides of the map and every one
//: of those lines crossed it. Now the ring is walked greedily: start at the
//: largest category, and each next place goes to the category with the most
//: lines to the one just placed (and, a little, to the first, since the ring
//: closes), size breaking a tie. A reshuffle starts at a seeded category and
//: lets the seed break near-ties, so it deals a different ring that is still
//: one where neighbours are the categories that talk to each other.
function groupOrder() {
  const sizes = new Map();
  for (const node of nodes) sizes.set(node.group, (sizes.get(node.group) || 0) + 1);
  const bySize = [...sizes.keys()].sort((a, b) => sizes.get(b) - sizes.get(a) || a.localeCompare(b));
  //: **Organic orders its ring by the links too** (INBOX 1400): categories
  //: that share the most lines sit side by side, as Clusters has done, so a
  //: line between two categories crosses the gap between neighbours rather
  //: than the map. Measured with the untangle pass on the 150-note seed
  //: (`off.js`, three layouts): 437 crossings by size, 284 with both. A
  //: reshuffle starts the ring at a seeded category and leans on chance.
  if (bySize.length < 3) return bySize;
  const rand = ring.seed ? seededRandom(ring.seed) : null;
  const link = (a, b) => ring.affinity.get(a < b ? `${a}\u0000${b}` : `${b}\u0000${a}`) || 0;
  const order = [rand ? bySize[Math.floor(rand() * bySize.length)] : bySize[0]];
  const left = new Set(bySize.filter((g) => g !== order[0]));
  while (left.size) {
    const last = order[order.length - 1];
    let pick = null;
    let top = -Infinity;
    for (const group of left) {
      const score = link(last, group) + 0.5 * link(order[0], group) + sizes.get(group) * 1e-3 + (rand ? rand() * 0.6 : 0);
      if (score > top) {
        top = score;
        pick = group;
      }
    }
    order.push(pick);
    left.delete(pick);
  }
  return order;
}

//: **The arrangement's seed** (INBOX 692, the owner: "can you add a resuffle
//: button or feature to the graph to rearrange how the graph sits"). Zero is
//: the default map; a reshuffle picks a new one, and the main thread sends it
//: with every `init` after, so a re-render keeps the categories where the
//: reshuffle dealt them rather than pulling them back round to the default.
//: `turn` is the ring's starting angle, from the same seed.
const ring = { seed: 0, turn: -Math.PI / 2, width: 0, on: true, affinity: new Map(), inner: new Map(), shape: "organic" };

//: **The force layout's shape** (INBOX 693, the owner: "different preferred
//: shapes or ways of structuring the force graph", and of the layout the
//: notebook had: "maybe it or a slightly refined version can be an
//: option"). `params.shape`, one of:
//: - "organic", the default: the forces this layout had before 693 (a loose
//:   tree, categories leaning toward places on a ring, long gentle curves),
//:   with the fixes every shape has: no line through a dot it does not join
//:   (`clearanceForce`), a hub's leaves round it in order (`leafForce`),
//:   loose notes in a close row, room between dots;
//: - "clusters": each category a compact round cluster on a ring with even
//:   gutters (`groupAnchors`), hubs at the middle, bridges on the rim;
//: - "galaxy": one clump, no category places, the best-connected notes
//:   drawn to the middle (`shapeForce`);
//: A fourth, Rings (rings out from the focused or the most-linked note), was
//: built and measured and left out: as forces it either laid a branch along
//: its ring as a line or, with a radial tree as targets, crossed or
//: flattened every other component (graph692.js: fit zoom 0.3 to 0.53, a
//: line through a dot, other components overlapping the root's).
const SHAPES = new Set(["organic", "clusters", "galaxy"]);
function clustered() {
  return ring.shape === "clusters";
}

//: **The category that joins the others stands in the middle** (INBOX 693:
//: "hubs central", and cross-cluster lines short). On the showcase notebook
//: one category (Ideas) is nearly all bridges: its notes link to four other
//: categories and hardly to each other. On the ring its lines crossed the
//: map to every far side; in the middle each runs one ring-radius. Chosen
//: when at least four categories are drawn and one has lines to three or
//: more others, more of them than it has inside itself; the one with the
//: most such lines wins.
function bridgeGroup(groups) {
  if (groups.length < 4) return null;
  let best = null;
  let most = 0;
  for (const group of groups) {
    let across = 0;
    let partners = 0;
    for (const other of groups) {
      if (other === group) continue;
      const count = ring.affinity.get(group < other ? `${group}\u0000${other}` : `${other}\u0000${group}`) || 0;
      across += count;
      if (count) partners += 1;
    }
    if (partners >= 3 && across > (ring.inner.get(group) || 0) && across > most) {
      most = across;
      best = group;
    }
  }
  return best;
}

//: mulberry32: small, fast and good enough for placing dots; the point is
//: that it is seeded, so a test (and a person) gets the same map twice.
function seededRandom(seed) {
  let a = seed >>> 0 || 1;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function setRingSeed(seed) {
  ring.seed = Number(seed) >>> 0;
  ring.turn = ring.seed ? -Math.PI / 2 + seededRandom(ring.seed ^ 0x9e3779b9)() * 2 * Math.PI : -Math.PI / 2;
}

//: **Each category's place, sized by the category, with an even gutter
//: between neighbours** (INBOX 693, the owner: "compact round clusters per
//: category ... packed evenly on a ring or grid with consistent gutters ...
//: aspect close to the viewport"). The places were evenly spaced angles on
//: one ring whose radius grew with the whole notebook, so a big category
//: crowded its neighbour and a small one sat in a wide gap. Now each category
//: is given a disc (`GROUP_DISC` times the root of its size: the area a
//: cluster of that many notes takes at the link length), and the ring is the
//: smallest ellipse round which every disc touches its neighbours' with
//: `GROUP_GUTTER` between them. The ellipse is as much wider than tall as
//: the canvas is (within `GROUP_STRETCH_MAX`), so the map fills the view it
//: is fitted to. Both in units of the link length (`unit`), so the sliders
//: and the notebook's size scale the whole arrangement together. Only as far
//: as the links back the categories (`groupGather`): on a notebook whose links
//: ignore them the ring stays round, because stretching it moved a 300-note
//: fixture's crossings 20% for no gain in fill.
//:
//: The numbers, measured on the showcase notebook (graph692.js, 1440x900):
//: discs of 46 and gutters of 70 left 97 world units between categories and
//: the lines between them 316 long on average; 28 and 30 brought those to
//: 61 and 217 with no two dots touching. The map's box came out about 0.7
//: of the canvas's shape when the ring was aimed at the canvas's shape
//: exactly (the clusters are rounder than their ring, and the centre pull
//: is round), so it is aimed `GROUP_ASPECT_GAIN` past it: 1.4 gave 0.81,
//: 1.8 gave 0.89.
const GROUP_DISC = 28;
const GROUP_GUTTER = 30;
const GROUP_ASPECT_GAIN = 1.8;
//: **Grouped, a note's repulsion reaches across its own cluster and no
//: further** (900 otherwise: see `distanceMax` at the force's build). Two
//: clusters a gutter apart pushed each other a whole cluster further, which
//: is what the gutter is for; the places (`groupAnchors`) now set the space
//: between categories and the charge only the space inside one.
const GROUPED_CHARGE_REACH = 250;

//: How much room a category's disc takes: its linked notes count whole, its
//: loose ones half (they sit in a row at the rim, `orbitUpdate`).
function groupDiscs(unit) {
  const weight = new Map();
  for (const node of nodes) weight.set(node.group, (weight.get(node.group) || 0) + (node.degree ? 1 : 0.5));
  const discs = new Map();
  for (const [group, w] of weight) discs.set(group, GROUP_DISC * Math.sqrt(w) * unit);
  return discs;
}

//: Places `radii` round an ellipse of axis ratio `e` (x over y) starting at
//: `turn`, each the given distance (`gaps`) from the one before along the
//: chord, and returns the angles and how far round the last one closes.
function ellipseWalk(rho, e, gaps) {
  const at = (theta) => [rho * e * Math.cos(theta), (rho / e) * Math.sin(theta)];
  const angles = [ring.turn];
  let theta = ring.turn;
  for (let i = 0; i < gaps.length - 1; i++) {
    const [x0, y0] = at(theta);
    let lo = 0;
    let hi = Math.PI;
    for (let k = 0; k < 30; k++) {
      const mid = (lo + hi) / 2;
      const [x1, y1] = at(theta + mid);
      if (Math.hypot(x1 - x0, y1 - y0) < gaps[i]) lo = mid;
      else hi = mid;
    }
    theta += hi;
    angles.push(theta);
  }
  const [xa, ya] = at(theta);
  const [xb, yb] = at(ring.turn);
  // How far the closing chord falls short of (positive) or overruns its gap.
  const closing = theta - ring.turn < 2 * Math.PI ? Math.hypot(xb - xa, yb - ya) - gaps[gaps.length - 1] : -1;
  return { angles, closing, at };
}

//: The ring for `gaps` (centre to centre, neighbour to neighbour, each plus
//: `extra`) on an ellipse of axis ratio `e`: the smallest one that closes.
function ringFor(gaps, e, extra) {
  const spaced = gaps.map((g) => g + extra);
  let lo = 0;
  let hi = spaced.reduce((a, b) => a + b, 0);
  for (let k = 0; k < 40; k++) {
    const rho = (lo + hi) / 2;
    if (ellipseWalk(rho, e, spaced).closing < 0) lo = rho;
    else hi = rho;
  }
  const walk = ellipseWalk(hi, e, spaced);
  walk.rho = hi;
  return walk;
}

//: Organic's category places: the base layout's ring, unchanged (INBOX
//: 443 (1)). Evenly spaced angles on a ring `width` out; a landscape map
//: stretches it along x and squashes it along y by the root of the aspect,
//: as far as the links back the categories (`groupGather`).
function groupAnchorsOrganic(width) {
  const groups = groupOrder();
  const anchors = new Map();
  if (groups.length < 2) return anchors;
  const aspect = world && Number.isFinite(world.aspect) && world.aspect > 0 ? Math.min(world.aspect, 1) : 1;
  const t = groupGather().t;
  const stretchX = 1 + (Math.min(ORGANIC_STRETCH_MAX, 1 / Math.sqrt(aspect)) - 1) * t;
  const squashY = 1 + (Math.max(1 / ORGANIC_STRETCH_MAX, Math.sqrt(aspect)) - 1) * t;
  groups.forEach((group, i) => {
    const angle = ring.turn + (2 * Math.PI * i) / groups.length;
    anchors.set(group, { x: Math.cos(angle) * width * stretchX, y: Math.sin(angle) * width * squashY, r: 0 });
  });
  return anchors;
}
const ORGANIC_STRETCH_MAX = 1.6;

function groupAnchors(unit) {
  if (!clustered()) return groupAnchorsOrganic(unit);
  const view =world && Number.isFinite(world.aspect) && world.aspect > 0 ? 1 / world.aspect : 1;
  const t = groupGather().t;
  const key = `${unit}|${ring.seed}|${view}|${t}`;
  if (ring.cache && ring.cache.key === key) return ring.cache.anchors;
  const all = groupOrder();
  const anchors = new Map();
  ring.cache = { key, anchors };
  if (all.length < 2) return anchors;
  const discs = groupDiscs(unit);
  const middle = bridgeGroup(all);
  const groups = middle ? all.filter((g) => g !== middle) : all;
  const radii = groups.map((g) => discs.get(g));
  const gutter = GROUP_GUTTER * unit;
  const gaps = radii.map((r, i) => r + radii[(i + 1) % radii.length] + gutter);
  const meanR = radii.reduce((a, b) => a + b, 0) / radii.length;
  if (groups.length === 2) {
    // Two categories: side by side along the canvas's longer side.
    const across = view >= 1 ? [1, 0] : [0, 1];
    anchors.set(groups[0], { x: (-across[0] * gaps[0]) / 2, y: (-across[1] * gaps[0]) / 2, r: radii[0] });
    anchors.set(groups[1], { x: (across[0] * gaps[0]) / 2, y: (across[1] * gaps[0]) / 2, r: radii[1] });
    return anchors;
  }
  //: How far the ring's nearest point must be from the middle when a
  //: category stands there: its disc, a gutter and the widest ring disc.
  const clearMiddle = middle ? discs.get(middle) + gutter + Math.max(...radii) : 0;
  let e = 1;
  let walk = null;
  // The ellipse's shape and size, together: the size so the ring closes
  // with every gutter even (and, round a middle category, as much wider
  // than even as clears it, shared by every gutter alike), the shape so the
  // map's box (the ring plus a disc's reach) is the canvas's shape. Three
  // rounds settle both.
  for (let round = 0; round < 3; round++) {
    walk = ringFor(gaps, e, 0);
    if (middle && walk.rho * Math.min(e, 1 / e) < clearMiddle) {
      let lo = 0;
      let hi = clearMiddle * 2 * Math.PI;
      for (let k = 0; k < 30; k++) {
        const mid = (lo + hi) / 2;
        if (ringFor(gaps, e, mid).rho * Math.min(e, 1 / e) < clearMiddle) lo = mid;
        else hi = mid;
      }
      walk = ringFor(gaps, e, hi);
    }
    const aimed = view >= 1 ? view * GROUP_ASPECT_GAIN : view / GROUP_ASPECT_GAIN;
    const target = Math.max(1 / GROUP_STRETCH_MAX, Math.min(GROUP_STRETCH_MAX, aimed));
    // Box width over height is (rho e + R) / (rho / e + R); solve for e.
    const want = 1 + (target - 1) * t;
    const r = meanR / walk.rho;
    // want (1/e + r) = e + r  ->  e^2 + e r (1 - want) - want = 0
    const b = r * (1 - want);
    e = Math.max(1 / GROUP_STRETCH_MAX, Math.min(GROUP_STRETCH_MAX, (-b + Math.sqrt(b * b + 4 * want)) / 2));
  }
  groups.forEach((group, i) => {
    const [x, y] = walk.at(walk.angles[i]);
    anchors.set(group, { x, y, r: radii[i] });
  });
  if (middle) anchors.set(middle, { x: 0, y: 0, r: discs.get(middle) });
  return anchors;
}

//: **Unlinked notes keep an orbit, not a scatter** (INBOX 443 (1), the owner:
//: "the graph shape could look nicer": a few notes floating far from the
//: cluster). Measured on a 60-note, 5-category fixture
//: (`scratchpad/ui-sweeps/graphlook.js`): the ten notes with no link had
//: nothing to hold them but the weak category pull and the repulsion of
//: everything else, so they came to rest wherever those balanced: dots on the
//: map's far edge at uneven distances, which also set the fit and shrank the
//: map. Each now has a seat on a ring just outside the linked cluster. A
//: category's unlinked notes sit together on the arc facing its own place (the
//: same order `groupAnchors` uses), evenly spaced, and a category with more
//: than its arc holds spills onto a second ring a node's width further out. A
//: spring pulls each toward its seat; the repulsion and the collision still
//: act, so the ring is a tidy default rather than a wall. Only the Graph tab
//: turns it on (`params.orbit`): a local map has no unlinked notes to seat.
const ORBIT_EVERY = 8;
const ORBIT_STRENGTH = 0.16;
//: Fewer than this many linked notes is not a cluster to circle.
const ORBIT_MIN_LINKED = 3;
//: The ring hugs the cluster's silhouette rather than a circle: 36 bins of
//: angle round the linked notes' centre, each holding how far the cluster
//: reaches that way. A circle sized by the farthest note floated the seats a
//: whole map-width from the side the cluster is short on (measured: the
//: unlinked notes sat 1.24x the cluster's p90 radius out, on an elongated
//: cluster). The bins are smoothed by their widest neighbour, so a seat clears
//: a bump instead of cutting through it.
const ORBIT_BINS = 36;
//: Clear air between the cluster's outline and a seat's edge, past the seat's
//: own radius and the collide pad.
const ORBIT_CLEAR = 6;
const orbit = { on: false, groupBy: true, tick: 0, items: [], reach: null, cx: 0, cy: 0 };

function orbitReach(linked) {
  let cx = 0;
  let cy = 0;
  for (const node of linked) {
    cx += node.x;
    cy += node.y;
  }
  cx /= linked.length;
  cy /= linked.length;
  const raw = new Array(ORBIT_BINS).fill(0);
  for (const node of linked) {
    const dx = node.x - cx;
    const dy = node.y - cy;
    const bin = Math.floor(((Math.atan2(dy, dx) + Math.PI) / (2 * Math.PI)) * ORBIT_BINS) % ORBIT_BINS;
    raw[bin] = Math.max(raw[bin], Math.hypot(dx, dy) + (node.r || 8));
  }
  // An empty bin takes the nearer of its filled neighbours' reach, so a gap in
  // the cluster's outline is bridged rather than dipping to the centre.
  const mean = raw.reduce((a, b) => a + b, 0) / ORBIT_BINS;
  const smooth = raw.map((_, i) => {
    let best = 0;
    for (let d = -2; d <= 2; d++) best = Math.max(best, raw[(i + d + ORBIT_BINS) % ORBIT_BINS] * (1 - Math.abs(d) * 0.06));
    return best || mean;
  });
  // A light low-pass so neighbouring seats do not jump by a bump's height.
  const reach = smooth.map((_, i) => {
    let sum = 0;
    for (let d = -1; d <= 1; d++) sum += smooth[(i + d + ORBIT_BINS) % ORBIT_BINS];
    return sum / 3;
  });
  return { cx, cy, reach };
}

function orbitRadiusAt(angle) {
  const t = (((angle + Math.PI) / (2 * Math.PI)) % 1 + 1) % 1;
  const pos = t * ORBIT_BINS - 0.5;
  const i0 = Math.floor(pos);
  const f = pos - i0;
  const a = orbit.reach[(i0 + ORBIT_BINS) % ORBIT_BINS];
  const b = orbit.reach[(i0 + 1 + ORBIT_BINS) % ORBIT_BINS];
  return a + (b - a) * f;
}

//: **Grouped, a loose note sits at its own category's rim** (INBOX 693, the
//: owner: "orphans gathered into a tidy group per category or at their
//: cluster's rim"; the rejected screenshot had a category's loose notes as
//: dots strung down the map's edge). The orbit round the whole map spread a
//: category's loose notes over its whole slice of the ring, a map-height of
//: arc for five dots. Now they stand in a close row (one seat apart) on the
//: outer side of their own cluster, just clear of its farthest note, facing
//: away from the map's middle; a category with no linked notes at all is a
//: small round knot (a sunflower) at its own place.
function orbitUpdateGrouped(lone) {
  const anchors = groupAnchors(ring.width);
  const cx = world ? (world.left + world.right) / 2 : 0;
  const cy = world ? (world.top + world.bottom) / 2 : 0;
  let widest = 0;
  for (const node of nodes) widest = Math.max(widest, node.r || 8);
  const seat = 2 * (widest + COLLIDE_PAD);
  const byGroup = new Map();
  for (const node of lone) {
    if (!byGroup.has(node.group)) byGroup.set(node.group, []);
    byGroup.get(node.group).push(node);
  }
  const linked = new Map();
  for (const node of nodes) {
    if (!node.degree) continue;
    if (!linked.has(node.group)) linked.set(node.group, []);
    linked.get(node.group).push(node);
  }
  for (const [group, list] of byGroup) {
    const place = anchors.get(group) || { x: 0, y: 0 };
    list.sort((a, b) => String(a.id).localeCompare(String(b.id)));
    const members = linked.get(group) || [];
    if (!members.length) {
      const golden = Math.PI * (3 - Math.sqrt(5));
      list.forEach((node, i) => {
        const r = seat * 0.62 * Math.sqrt(i + (list.length > 1 ? 0.5 : 0));
        orbit.items.push({ node, x: cx + place.x + Math.cos(i * golden) * r, y: cy + place.y + Math.sin(i * golden) * r });
      });
      continue;
    }
    let mx = 0;
    let my = 0;
    for (const node of members) {
      mx += node.x;
      my += node.y;
    }
    mx /= members.length;
    my /= members.length;
    let reach = 0;
    for (const node of members) reach = Math.max(reach, Math.hypot(node.x - mx, node.y - my) + (node.r || 8));
    const facing = Math.atan2(my - cy, mx - cx);
    const radius = reach + seat * 0.75;
    const perRow = Math.max(1, Math.floor((Math.PI * radius) / seat));
    list.forEach((node, i) => {
      const row = Math.floor(i / perRow);
      const inRow = Math.min(perRow, list.length - row * perRow);
      const r = radius + row * seat;
      const step = seat / r;
      const angle = facing + ((i % perRow) - (inRow - 1) / 2) * step;
      orbit.items.push({ node, x: mx + Math.cos(angle) * r, y: my + Math.sin(angle) * r });
    });
  }
}

function orbitUpdate() {
  if (clustered() && groupOrder().length > 1) {
    orbit.items = [];
    const lone = nodes.filter((node) => node.degree === 0);
    if (lone.length) orbitUpdateGrouped(lone);
    return;
  }
  const lone = [];
  const linked = [];
  let widest = 0;
  for (const node of nodes) {
    widest = Math.max(widest, node.r || 8);
    if (node.degree === 0) lone.push(node);
    else linked.push(node);
  }
  const loneWidest = lone.reduce((m, n) => Math.max(m, n.r || 8), 0);
  orbit.items = [];
  if (!lone.length || linked.length < ORBIT_MIN_LINKED) return;
  const next = orbitReach(linked);
  if (!orbit.reach) orbit.reach = next.reach;
  else orbit.reach = orbit.reach.map((v, i) => v + (next.reach[i] - v) * 0.3);
  orbit.cx = next.cx;
  orbit.cy = next.cy;
  const seat = 2 * (widest + COLLIDE_PAD) + 10;
  const clear = loneWidest + COLLIDE_PAD + ORBIT_CLEAR;
  const order = orbit.groupBy ? groupOrder() : [];
  const slots = order.length > 1 ? order.length : 1;
  const slice = (2 * Math.PI) / slots;
  const directions = slots > 1 ? groupAnchors(1) : null;
  const byGroup = new Map();
  for (const node of lone) {
    const key = slots > 1 ? node.group : "";
    if (!byGroup.has(key)) byGroup.set(key, []);
    byGroup.get(key).push(node);
  }
  for (const [key, list] of byGroup) {
    //: Facing its category's own place: the direction of its anchor, which is
    //: not the ring's angle once the ring has been stretched to the map.
    const place = slots > 1 ? directions.get(key) : null;
    const centre = place ? Math.atan2(place.y, place.x) : -Math.PI / 2;
    list.sort((a, b) => String(a.id).localeCompare(String(b.id)));
    const probe = orbitRadiusAt(centre) + clear;
    const minStep = seat / probe;
    const perRing = Math.max(1, Math.floor((slice * 0.92) / minStep));
    list.forEach((node, i) => {
      const ring = Math.floor(i / perRing);
      const inRing = Math.min(perRing, list.length - ring * perRing);
      // A close row, one seat and a fifth apart, not the whole slice (INBOX
      // 693, "orphans placed tidily rather than floating"): five loose notes
      // were strung down a map-height of arc.
      const step = Math.min(0.5, (slice * 0.92) / inRing, minStep * 1.2);
      const angle = centre + ((i % perRing) - (inRing - 1) / 2) * step;
      const radius = orbitRadiusAt(angle) + clear + ring * seat;
      orbit.items.push({ node, x: orbit.cx + Math.cos(angle) * radius, y: orbit.cy + Math.sin(angle) * radius });
    });
  }
}

function orbitForce(alpha) {
  if (!orbit.on) return;
  if (orbit.tick++ % ORBIT_EVERY === 0) orbitUpdate();
  const k = ORBIT_STRENGTH * (alpha + 0.05);
  for (const item of orbit.items) {
    item.node.vx += (item.x - item.node.x) * k;
    item.node.vy += (item.y - item.node.y) * k;
  }
}
orbitForce.initialize = () => {};

const HUB_PULL = 4;
const HOME_PULL = 1.5;

//: **A line never runs through a note it does not join** (INBOX 693, the
//: owner's screenshot of a link passing behind other notes' dots: "bit of
//: overlap"). Measured on the 692 fixture (`tests/test_graph_layout.py`):
//: 7 (line, dot) pairs where a drawn line crossed a dot it has nothing to do
//: with, and 8 on the showcase notebook in the browser
//: (`scratchpad/ui-sweeps/graph692.js`). Nothing in the forces knew a line
//: was there: the charge and the collision act between dots only.
//:
//: So every line pushes away the dots it passes too close to, and the dot
//: pushes back on the line's two ends (shared by where along the line it
//: sits): the dot steps aside and the line bends round it, which is what
//: "routed round" can mean for a line drawn from end to end. The line is the
//: one the canvas draws: the curve `gcBowPoint` bows (the same side by id,
//: the same seventh of the length, 48 at most) when Curved links is on, the
//: straight line when it is off, cut into four chords. Not scaled by alpha,
//: like the collision: a rule about what may touch has to hold at rest,
//: which is when anyone reads the map closely.
const CLEAR_GAP = 4;
const CLEAR_STRENGTH = 0.6;
const CLEAR_CELL = 40;
const clearPts = new Float64Array(10);
const clear = { curved: true, stamp: 0 };

function clearCurve(a, b) {
  // Drawn straight in every shape but Organic, whose long curves are its
  // look (the canvas's `gcBowPoint`, `_straight`), and when Curved links is off.
  if (!clear.curved || ring.shape !== "organic") {
    clearPts[0] = a.x;
    clearPts[1] = a.y;
    clearPts[2] = b.x;
    clearPts[3] = b.y;
    return 2;
  }
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const bow = Math.min(len * 0.14, 48) * (String(a.id) < String(b.id) ? 1 : -1);
  const cx = (a.x + b.x) / 2 - (dy / len) * bow;
  const cy = (a.y + b.y) / 2 + (dx / len) * bow;
  for (let i = 0; i <= 4; i++) {
    const u = i / 4;
    clearPts[i * 2] = (1 - u) * (1 - u) * a.x + 2 * (1 - u) * u * cx + u * u * b.x;
    clearPts[i * 2 + 1] = (1 - u) * (1 - u) * a.y + 2 * (1 - u) * u * cy + u * u * b.y;
  }
  return 5;
}

//: The nearest point of the drawn line to `node`: [squared distance, x, y,
//: how far along the line (0 at `a`, 1 at `b`)].
const clearNear = [0, 0, 0, 0];
function clearNearest(node, count) {
  clearNear[0] = Infinity;
  for (let i = 1; i < count; i++) {
    const ax = clearPts[i * 2 - 2];
    const ay = clearPts[i * 2 - 1];
    const dx = clearPts[i * 2] - ax;
    const dy = clearPts[i * 2 + 1] - ay;
    const l2 = dx * dx + dy * dy || 1;
    const u = Math.max(0, Math.min(1, ((node.x - ax) * dx + (node.y - ay) * dy) / l2));
    const qx = ax + u * dx;
    const qy = ay + u * dy;
    const d = (node.x - qx) ** 2 + (node.y - qy) ** 2;
    if (d < clearNear[0]) {
      clearNear[0] = d;
      clearNear[1] = qx;
      clearNear[2] = qy;
      clearNear[3] = (i - 1 + u) / (count - 1);
    }
  }
}

function clearPush(node, a, b) {
  const need = (node.r || 8) + CLEAR_GAP;
  if (clearNear[0] >= need * need) return;
  const dist = Math.sqrt(clearNear[0]);
  let nx;
  let ny;
  if (dist > 1e-6) {
    nx = (node.x - clearNear[1]) / dist;
    ny = (node.y - clearNear[2]) / dist;
  } else {
    // Dead on the line: step off it square to the line's direction.
    const len = Math.hypot(b.x - a.x, b.y - a.y) || 1;
    nx = -(b.y - a.y) / len;
    ny = (b.x - a.x) / len;
  }
  const push = (need - dist) * CLEAR_STRENGTH;
  // A held note does not move; whoever is free takes the whole step.
  const along = clearNear[3];
  const nodeFree = node.fx == null ? 1 : 0;
  const aFree = a.fx == null ? 1 - along : 0;
  const bFree = b.fx == null ? along : 0;
  const share = nodeFree + (aFree + bFree) / 2;
  if (!share) return;
  node.vx += (nx * push * nodeFree) / share;
  node.vy += (ny * push * nodeFree) / share;
  a.vx -= (nx * push * aFree) / (2 * share);
  a.vy -= (ny * push * aFree) / (2 * share);
  b.vx -= (nx * push * bFree) / (2 * share);
  b.vy -= (ny * push * bFree) / (2 * share);
}

function clearanceForce() {
  const links = simulation && simulation.force("link") ? simulation.force("link").links() : [];
  if (!links.length) return;
  let widest = 0;
  for (const node of nodes) widest = Math.max(widest, node.r || 8);
  const reach = widest + CLEAR_GAP;
  const grid = new Map();
  for (const node of nodes) {
    const key = Math.floor(node.x / CLEAR_CELL) * 100003 + Math.floor(node.y / CLEAR_CELL);
    const list = grid.get(key);
    if (list) list.push(node);
    else grid.set(key, [node]);
  }
  for (const link of links) {
    const a = link.source;
    const b = link.target;
    const count = clearCurve(a, b);
    clear.stamp += 1;
    //: Chord by chord, not the whole line's box: a note within `reach` of the
    //: line is within it of a chord, so the cells round each chord hold every
    //: note the box did. A long diagonal line's box is mostly empty air (the
    //: 300-note seed: this force was 64% of a tick, 7 of 11 ms).
    for (let c = 1; c < count; c++) {
      const ax = clearPts[c * 2 - 2];
      const ay = clearPts[c * 2 - 1];
      const bx = clearPts[c * 2];
      const by = clearPts[c * 2 + 1];
      const x1 = Math.floor((Math.max(ax, bx) + reach) / CLEAR_CELL);
      const y1 = Math.floor((Math.max(ay, by) + reach) / CLEAR_CELL);
      for (let gx = Math.floor((Math.min(ax, bx) - reach) / CLEAR_CELL); gx <= x1; gx++) {
        for (let gy = Math.floor((Math.min(ay, by) - reach) / CLEAR_CELL); gy <= y1; gy++) {
          const list = grid.get(gx * 100003 + gy);
          if (!list) continue;
          for (const node of list) {
            if (node === a || node === b || node._clear === clear.stamp) continue;
            node._clear = clear.stamp;
            clearNearest(node, count);
            clearPush(node, a, b);
          }
        }
      }
    }
  }
}
clearanceForce.initialize = () => {};

//: **A hub stands in the middle of its own notes** (INBOX 693, "hubs
//: central"). The pull toward the category's place alone could not do it:
//: measured on the 692 fixture, a star's hub sat 1.29x its cluster's mean
//: radius from the cluster's middle, because its lines to the notes that
//: bridge categories drew it inward while its leaves were held out at the
//: category's place, so the cluster read as a fringe hanging off its hub.
//: Each note that is a hub in its category (`node.hub`, at least
//: `HUB_MIN`, with three or more links inside it) now leans toward the middle
//: of its same-category neighbours, as hard as the square of how much of a
//: hub it is: the leaves are where the category's place puts them and the
//: hub stands among them.
const HUB_CENTRE = 0.5;
const HUB_MIN = 0.5;
function hubForce(alpha) {
  if (!clustered()) return;
  for (const node of nodes) {
    if (!node.peers || node.hub < HUB_MIN || node.fx != null) continue;
    let x = 0;
    let y = 0;
    for (const peer of node.peers) {
      x += peer.x;
      y += peer.y;
    }
    const k = HUB_CENTRE * node.hub * node.hub * alpha;
    node.vx += (x / node.peers.length - node.x) * k;
    node.vy += (y / node.peers.length - node.y) * k;
  }
}
hubForce.initialize = () => {};

//: **A note stays within reach of its own category** (INBOX 904 B70, the
//: owner: "why does this node wanna be all the way down there?? the graph
//: force structuring is still a bit messy"). A linked note whose lines go to
//: another category is pulled by them harder than the soft category pull holds
//: it, and came to rest a whole cluster away from its own: measured on a
//: 46-note, 8-category notebook (`scratchpad/ui-sweeps/graph1017-b70.js`), the
//: farthest note stood 3 to 8 times the median nearest-same-category distance
//: from its category, stretching the category's outline across the map with
//: it. This is a leash, not a place: nothing acts inside `TETHER_SLACK` times
//: the category's own typical reach (the median distance of its notes from
//: their median point, never under `TETHER_FLOOR`), and past it the note is drawn
//: back by `TETHER_PULL` of the excess a tick. Not scaled by alpha, like the
//: collision: it is a rule about where a note may be at rest. Loose notes keep
//: their orbit seats, a pin is never moved, and a category of fewer than
//: three has no outline to hold to.
const TETHER_SLACK = 1.4;
const TETHER_FLOOR = 70;
const TETHER_PULL = 0.4;
const TETHER_MIN_GROUP = 3;
const tether = { groups: new Map() };
const median = (values) => {
  const sorted = values.slice().sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
};
function tetherForce() {
  if (!ring.on) return;
  const groups = tether.groups;
  groups.clear();
  for (const node of nodes) {
    let list = groups.get(node.group);
    if (!list) groups.set(node.group, (list = []));
    list.push(node);
  }
  for (const list of groups.values()) {
    if (list.length < TETHER_MIN_GROUP) continue;
    // The middle is the median of each axis, not the mean: the note the leash
    // is holding must not drag the middle toward itself (a mean over four
    // notes let one stray note hold the limit 300 away).
    const cx = median(list.map((n) => n.x));
    const cy = median(list.map((n) => n.y));
    const typical = median(list.map((n) => Math.hypot(n.x - cx, n.y - cy)));
    const limit = Math.max(TETHER_FLOOR, typical * TETHER_SLACK);
    for (const node of list) {
      if (!node.degree || node.fx != null || node.placed || node.following) continue;
      const dx = cx - node.x;
      const dy = cy - node.y;
      const d = Math.hypot(dx, dy);
      if (d <= limit) continue;
      const k = ((d - limit) * TETHER_PULL) / d;
      node.vx += dx * k;
      node.vy += dy * k;
    }
  }
}
tetherForce.initialize = () => {};

//: **A bridge stands on its cluster's rim, facing what it joins** (INBOX
//: 693, the owner: cross-cluster lines "short"). Pulled to the middle of its
//: category's place, a note whose lines go to other categories drew every
//: one of them across its own cluster first. Its place is now offset toward
//: the places of the categories it links to, by as much of its cluster's
//: radius as its lines leave home (`node.away`): a leaf of its own category
//: stays in the middle, a pure bridge stands at the edge nearest its
//: partners. `axis` 0 is x, 1 is y.
const RIM_REACH = 0.85;
function rimOffset(node, anchors, axis) {
  if (!clustered() || !node.outs || !node.away) return 0;
  const home = anchors.get(node.group);
  let dx = 0;
  let dy = 0;
  for (const group of node.outs) {
    const place = anchors.get(group);
    if (!place) continue;
    dx += place.x - home.x;
    dy += place.y - home.y;
  }
  const len = Math.hypot(dx, dy);
  if (!len) return 0;
  return ((axis ? dy : dx) / len) * home.r * RIM_REACH * node.away;
}

//: **Galaxy** (INBOX 693, see `SHAPES`) draws each note toward the middle
//: as hard as the square of how connected it is, so the hubs make the core
//: and the leaves the arms. Loose notes keep the orbit round the outside
//: (`orbitForce`).
const GALAXY_PULL = 0.2;

function shapeForce(alpha) {
  if (ring.shape !== "galaxy") return;
  const cx = world ? (world.left + world.right) / 2 : 0;
  const cy = world ? (world.top + world.bottom) / 2 : 0;
  let most = 1;
  for (const node of nodes) most = Math.max(most, node.degree);
  for (const node of nodes) {
    if (!node.degree) continue;
    const k = GALAXY_PULL * (node.degree / most) ** 2 * alpha;
    node.vx += (cx - node.x) * k;
    node.vy += (cy - node.y) * k;
  }
}
shapeForce.initialize = () => {};

//: **A hub's leaves fan out round it, none crowding the next** (INBOX 693,
//: the owner, of a dense cluster: "stuff like this can get potentially hard
//: to read", leaves packed so tight their lines tangled). Every note with
//: three or more leaves (notes linked to it alone) takes them in the order
//: of their angles round it, and any two neighbours closer than a seat
//: (two collision radii) at the leaves' distance are eased apart along the
//: circle. Spokes from one point in angle order cannot cross each other, so
//: this keeps them apart without moving the fan: setting the leaves evenly
//: all the way round was tried first and turned a category's fan toward its
//: neighbours (purity on the 60-note fixture 0.80 to 0.71, test_graph_look).
const LEAF_PULL = 0.5;
function leafForce(alpha) {
  for (const hub of nodes) {
    const leaves = hub.leaves;
    if (!leaves || leaves.length < 3) continue;
    const at = leaves.map((leaf) => [Math.atan2(leaf.y - hub.y, leaf.x - hub.x), leaf]);
    at.sort((a, b) => a[0] - b[0]);
    let reach = 0;
    let widest = 0;
    for (const [, leaf] of at) {
      reach += Math.hypot(leaf.x - hub.x, leaf.y - hub.y);
      widest = Math.max(widest, leaf.r || 8);
    }
    reach = Math.max(1, reach / at.length);
    const want = (2 * Math.max(widest + COLLIDE_PAD, 2 * widest)) / reach;
    if (want * at.length >= 2 * Math.PI) continue;
    for (let i = 0; i < at.length; i++) {
      const [a0, a] = at[i];
      const [b0, b] = at[(i + 1) % at.length];
      const gap = (((b0 - a0) % (2 * Math.PI)) + 2 * Math.PI) % (2 * Math.PI);
      if (gap >= want) continue;
      // Ease the pair apart along the circle, half each.
      const push = ((want - gap) / 2) * reach * LEAF_PULL * alpha;
      if (a.fx == null) {
        a.vx += Math.sin(a0) * push;
        a.vy -= Math.cos(a0) * push;
      }
      if (b.fx == null) {
        b.vx -= Math.sin(b0) * push;
        b.vy += Math.cos(b0) * push;
      }
    }
  }
}
leafForce.initialize = () => {};

//: Whether categories have places: always for Clusters, never for Galaxy
//: (one clump is its point), and Organic as Group by category
//: says.
function groupingOn(params) {
  if (ring.shape === "clusters") return true;
  if (ring.shape !== "organic") return false;
  return !params || params.groupBy !== false;
}

function applyGrouping(params) {
  if (!simulation || !simulation.force("groupX")) return;
  orbit.on = Boolean(params && params.orbit === true);
  orbit.groupBy = !params || params.groupBy !== false;
  orbit.tick = 0;
  clear.curved = !params || params.curved !== false;
  const on = groupingOn(params);
  const cx = world ? (world.left + world.right) / 2 : 0;
  const cy = world ? (world.top + world.bottom) / 2 : 0;
  const spread = 0.5 + Number(params && params.spread != null ? params.spread : 50) / 50;
  const gather = groupGather();
  // Clusters measures its places in link lengths (`groupAnchors`); Organic
  // keeps the base ring, a radius grown with the root of the note count.
  ring.width =
    (clustered()
      ? SPREAD_TRIM * densityScale(nodes.length) * spread
      : Math.sqrt(nodes.length) * gather.radius * spread) * smallSpread(nodes.length);
  ring.on = on;
  ring.params = params;
  const anchors = on ? groupAnchors(ring.width) : new Map();
  const at = (node) => anchors.get(node.group);
  //: **A category's hub stands at its place** (INBOX 693, "hubs central"):
  //: measured on the 692 fixture, the best-connected note of each category
  //: sat 1.57x its cluster's mean radius from the cluster's middle, dragged
  //: to the edge by its lines to the notes that bridge categories, so a
  //: cluster read as a fringe round nothing. Its pull toward the place rises
  //: with the square of how connected it is within its category (`node.hub`,
  //: 0 to 1), so the leaves are untouched and the hub is the middle the rest
  //: arrange round.
  //: **A note whose lines all leave its category still lives in it** (INBOX
  //: 693, the owner: "small ideas/reading nodes float between clusters with
  //: no clear home"). Its pull home rises with the share of its lines that
  //: go to other categories (`node.away`, 0 to 1), so a bridge stands at the
  //: edge of its own cluster facing the ones it joins, not in the gap.
  //: A note the reader dropped (`placed`) has no home pull: it settles where
  //: it was put, and a reheat's other forces still move it.
  const pull = (node) =>
    at(node) && !node.placed
      ? (node.following ? FOLLOW_PULL : 1) * (node.degree === 0
        ? orbit.on
          ? 0.02
          : 0.12
        : clustered()
          ? gather.pull * (1 + HUB_PULL * node.hub * node.hub) * (1 + HOME_PULL * node.away)
          : gather.pull * (1 + HOME_PULL * node.away))
      : 0;
  simulation
    .force("groupX")
    .x((node) => cx + (at(node) ? at(node).x + rimOffset(node, anchors, 0) : 0))
    .strength(pull);
  simulation
    .force("groupY")
    .y((node) => cy + (at(node) ? at(node).y + rimOffset(node, anchors, 1) : 0))
    .strength(pull);
}

function applyForces(params) {
  if (!simulation) return;
  applyGrouping(params);
  const tuned = tuning(params);
  simulation.force("charge").strength(tuned.charge);
  simulation.force("link").distance(tuned.linkDistance).strength(linkStrength);
  simulation.force("x").strength(tuned.pullX);
  simulation.force("y").strength(tuned.pullY);
}

//: Keep the layout inside its own world. Carried over from the SVG tick
//: handler, and it exists for a reported bug: every drag reheats the
//: simulation, a reheated repulsion pushes the outermost notes further out,
//: and nothing ever pulls them back, after a few drags the edge of the map
//: was off the edge of the box with no way to know it was there. The world is
//: a square sized by the note count (see the main thread's `gcWorldFor`), not
//: the viewport, so the forces and not the walls decide the arrangement.
//: **Reshuffle** (INBOX 692): the categories are dealt round the ring in a
//: new order from a new angle (`setRingSeed`), every note that is not held
//: is given a new starting place near its category's new place (a hub near
//: the middle, a leaf further out, at a seeded random angle), and the layout
//: starts again from there at full heat. The move to the new places is
//: drawn, not jumped: `SHUFFLE_STEPS` frames, each closing a quarter of
//: what is left (an ease-out), before the simulation takes over, so the
//: eye can follow each note to where it went. A pinned note stays put: a
//: pin is the person's own decision about where it goes.
const SHUFFLE_STEPS = 18;
const SHUFFLE_EASE = 0.25;
const shuffle = { left: 0 };

function reshuffle(seed, animate) {
  setRingSeed(seed || 1);
  applyForces(ring.params);
  const rand = seededRandom((Number(seed) >>> 0) ^ 0x85ebca6b);
  const cx = world ? (world.left + world.right) / 2 : 0;
  const cy = world ? (world.top + world.bottom) / 2 : 0;
  const anchors = ring.on ? groupAnchors(ring.width) : new Map();
  const sizes = new Map();
  for (const node of nodes) sizes.set(node.group, (sizes.get(node.group) || 0) + 1);
  for (const node of nodes) {
    if (node.fx != null) continue;
    const at = anchors.get(node.group);
    const size = at ? sizes.get(node.group) : nodes.length;
    const reach = (at ? at.r * 0.8 : 18 * Math.sqrt(size)) * (1 - 0.7 * (node.hub || 0));
    const angle = rand() * 2 * Math.PI;
    const r = reach * Math.sqrt(rand());
    node.tx = cx + (at ? at.x : 0) + Math.cos(angle) * r;
    node.ty = cy + (at ? at.y : 0) + Math.sin(angle) * r;
  }
  orbit.reach = null;
  orbit.tick = 0;
  shuffle.left = animate ? SHUFFLE_STEPS : 1;
  simulation.alphaTarget(0).alpha(1);
}

//: One frame of the drawn move; the last one lands every note exactly.
function shuffleStep() {
  shuffle.left -= 1;
  const last = shuffle.left === 0;
  for (const node of nodes) {
    if (node.tx === undefined) continue;
    node.x = last ? node.tx : node.x + (node.tx - node.x) * SHUFFLE_EASE;
    node.y = last ? node.ty : node.y + (node.ty - node.y) * SHUFFLE_EASE;
    node.vx = 0;
    node.vy = 0;
    if (last) {
      node.tx = undefined;
      node.ty = undefined;
    }
  }
}

//: **A settled map is untangled once** (INBOX 1400 and 1306, the owner: the
//: force view "feels very messy to look at"). The forces only know distance,
//: never whether two lines cross, so a layout at rest keeps every crossing it
//: happened to settle into: 64 on the 36-note seed, 331 on the 150-note one
//: (`gm.js`). Once the layout is at rest, each note tries a few moves that
//: keep the map's shape, and keeps one only when it strictly lowers the count
//: of crossings on the lines it touches:
//: - trading places with one of its `UNTANGLE_NEAR` nearest notes of the same
//:   category (the clusters stay where and what they are), and
//: - a note with one link going round the note it hangs from, at the same
//:   distance, to a free spot (`UNTANGLE_TURNS` tries).
//: At most `UNTANGLE_ROUNDS` rounds and `UNTANGLE_MS` of work; the notes then
//: glide to their places (`shuffleStep`). Pinned and dropped notes stay.
//: Organic, the default shape, only.
const UNTANGLE_NEAR = 6;
const UNTANGLE_TURNS = 16;
const UNTANGLE_MOVE_LINKS = 4;
const UNTANGLE_HUB_RINGS = 4;
const UNTANGLE_ROUNDS = 4;
const UNTANGLE_REACH = 1.2;
const UNTANGLE_RELAX = 0.05;
const UNTANGLE_MS = 200;
const UNTANGLE_MS_PER_NOTE = 2;
const UNTANGLE_MS_MAX = 600;
//: A pass costs more as the map grows (186 notes: a pass needs 730 ms and was
//: cut at 200 with most of its moves unmade), so the budget is
//: `UNTANGLE_MS_PER_NOTE` a note, never under `UNTANGLE_MS` nor over
//: `UNTANGLE_MS_MAX`. The cap is the settle time: each 100 ms of a pass is 100 ms
//: before the map rests (INBOX 1400).
function untangleBudget() {
  return Math.min(UNTANGLE_MS_MAX, Math.max(UNTANGLE_MS, nodes.length * UNTANGLE_MS_PER_NOTE));
}
//: **Up to three passes, with the relax between** (INBOX 1400): the next starts
//: from where the last one's relax rested. 36 notes, mean of 6 layouts offline:
//: 53 and 57 crossings (1440 and 390 wide) with two passes, 50 and 49 with three. Past `UNTANGLE_BIG` notes a pass
//: costs a second of relax for a tenth of the crossings, so there are two; and a
//: pass that gained under `UNTANGLE_MIN_SHARE` of the crossings, or moved
//: nothing, ends them. The passes, their relax and the cleanup run in one go
//: (`settleUntangled`), never one shown glide after another.
const UNTANGLE_PASSES = 3;
const UNTANGLE_BIG = 100;
const UNTANGLE_BIG_PASSES = 2;
const UNTANGLE_MIN_SHARE = 0.03;
function untanglePasses() {
  return nodes.length > UNTANGLE_BIG ? UNTANGLE_BIG_PASSES : UNTANGLE_PASSES;
}
const UNTANGLE_MAX_EDGES = 4000;
const untangle = { holding: false, margin: 0, cleaned: false, widest: 8, edges: [], incident: [], done: false, passes: 0, ea: null, eb: null, xs: null, ys: null, mark: null };

function untangleSetup(edges) {
  untangle.edges = [];
  untangle.incident = nodes.map(() => []);
  untangle.done = false;
  untangle.passes = 0;
  untangle.cleaned = false;
  untangle.holding = false;
  untangle.mark = null;
  if (edges.length > UNTANGLE_MAX_EDGES) return;
  for (const edge of edges) {
    const a = indexById.get(edge.source);
    const b = indexById.get(edge.target);
    if (a === b) continue;
    const at = untangle.edges.length;
    untangle.edges.push([a, b]);
    untangle.incident[a].push(at);
    untangle.incident[b].push(at);
  }
  untangle.ea = Int32Array.from(untangle.edges, (e) => e[0]);
  untangle.eb = Int32Array.from(untangle.edges, (e) => e[1]);
  untangle.xs = new Float64Array(nodes.length);
  untangle.ys = new Float64Array(nodes.length);
}

function segmentsCross(ax, ay, bx, by, cx, cy, dx, dy) {
  const d1 = (dx - cx) * (ay - cy) - (dy - cy) * (ax - cx);
  const d2 = (dx - cx) * (by - cy) - (dy - cy) * (bx - cx);
  const d3 = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax);
  const d4 = (bx - ax) * (dy - ay) - (by - ay) * (dx - ax);
  return d1 * d2 < 0 && d3 * d4 < 0;
}

// Crossing pairs with at least one line in `mine` (a list of edge indices).
function crossingsOn(mine) {
  const list = untangle.edges;
  const count0 = list.length;
  const mark = untangle.mark || (untangle.mark = new Uint8Array(count0));
  const ea = untangle.ea;
  const eb = untangle.eb;
  const xs = untangle.xs;
  const ys = untangle.ys;
  for (let i = 0; i < nodes.length; i++) {
    xs[i] = nodes[i].x;
    ys[i] = nodes[i].y;
  }
  for (const i of mine) mark[i] = 1;
  let count = 0;
  for (const i of mine) {
    const a = ea[i];
    const b = eb[i];
    const ax = xs[a];
    const ay = ys[a];
    const bx = xs[b];
    const by = ys[b];
    const loX = Math.min(ax, bx);
    const hiX = Math.max(ax, bx);
    const loY = Math.min(ay, by);
    const hiY = Math.max(ay, by);
    for (let j = 0; j < count0; j++) {
      if (j === i) continue;
      const c = ea[j];
      const d = eb[j];
      if (c === a || c === b || d === a || d === b) continue;
      // A pair inside `mine` is met twice: count it from its lower index.
      if (j < i && mark[j]) continue;
      const cx = xs[c];
      const cy = ys[c];
      const dx = xs[d];
      const dy = ys[d];
      if ((cx < loX && dx < loX) || (cx > hiX && dx > hiX) || (cy < loY && dy < loY) || (cy > hiY && dy > hiY)) continue;
      if (segmentsCross(ax, ay, bx, by, cx, cy, dx, dy)) count += 1;
    }
  }
  for (const i of mine) mark[i] = 0;
  return count;
}

//: A whole category turns or mirrors about its middle when that lowers the
//: crossings on its lines: its links out then face the categories they join.
const UNTANGLE_TURN_STEPS = 8;
function untangleGroups(still) {
  const groups = new Map();
  nodes.forEach((node, i) => {
    if (still(node)) return;
    if (!groups.has(node.group)) groups.set(node.group, []);
    groups.get(node.group).push(i);
  });
  let gained = 0;
  for (const members of groups.values()) {
    if (members.length < 2) continue;
    const lines = [...new Set(members.flatMap((i) => untangle.incident[i]))];
    if (!lines.length) continue;
    const x0 = members.map((i) => nodes[i].x);
    const y0 = members.map((i) => nodes[i].y);
    const cx = x0.reduce((a, b) => a + b, 0) / members.length;
    const cy = y0.reduce((a, b) => a + b, 0) / members.length;
    const before = crossingsOn(lines);
    let best = before;
    let bestAt = null;
    for (let mirror = 0; mirror < 2; mirror++) {
      for (let step = 0; step < UNTANGLE_TURN_STEPS; step++) {
        if (!mirror && !step) continue;
        const angle = (2 * Math.PI * step) / UNTANGLE_TURN_STEPS;
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);
        members.forEach((i, k) => {
          const dx = (mirror ? -1 : 1) * (x0[k] - cx);
          const dy = y0[k] - cy;
          nodes[i].x = cx + dx * cos - dy * sin;
          nodes[i].y = cy + dx * sin + dy * cos;
        });
        const after = crossingsOn(lines);
        if (after < best) {
          best = after;
          bestAt = members.map((i) => [nodes[i].x, nodes[i].y]);
        }
      }
    }
    members.forEach((i, k) => {
      nodes[i].x = bestAt ? bestAt[k][0] : x0[k];
      nodes[i].y = bestAt ? bestAt[k][1] : y0[k];
    });
    gained += before - best;
  }
  return gained;
}

function untangleFree(node, x, y, gap) {
  // `wide` is the farthest any note can matter, so most notes are turned down on one comparison each.
  const wide = gap + Math.max(untangle.widest, node.r || 8);
  if (nodeGrid.live && wide <= nodeGrid.cell) {
    // The cleanup's grid: the 3 by 3 cells round (x, y) hold every note within `wide` (a cell is wider).
    for (const j of nodeGridNear(x, y)) {
      const other = nodes[j];
      if (other === node) continue;
      const dx = other.x - x;
      const dy = other.y - y;
      const need = gap + Math.max(other.r || 8, node.r || 8);
      if (dx * dx + dy * dy < need * need) return false;
    }
    return true;
  }
  for (let i = 0; i < nodes.length; i++) {
    const other = nodes[i];
    const dx = other.x - x;
    if (dx >= wide || dx <= -wide || other === node) continue;
    const dy = other.y - y;
    if (dy >= wide || dy <= -wide) continue;
    const need = gap + Math.max(other.r || 8, node.r || 8);
    if (dx * dx + dy * dy < need * need) return false;
  }
  return true;
}

//: **A uniform grid of notes** (INBOX 1400, round 6). `untangleFree` and
//: `untangleLineOver` asked every note about every candidate spot, and the
//: step-off tries up to 128 spots a note: at 400 notes that was a third of the
//: cleanup's clock. A dense array of cells (the map is clamped to its world, so
//: no hash is needed) with each note on a linked list of its cell; a cell is
//: `NODE_GRID_FILL` of the reach a note can matter from, so the 3 by 3 cells
//: round a spot hold every note that can touch it. The step-off moves one note at
//: a time, so a move is `nodeGridMove`. A spot outside the cells it was built over
//: is clamped to the edge cell, the same way a note is, so near stays near.
const NODE_GRID_FILL = 0.75;
const NODE_GRID_MIN = 16;
const NODE_GRID_CELLS = 40000;
const nodeGrid = { live: false, cell: 0, across: 0, down: 0, x0: 0, y0: 0, head: null, next: null, at: null, seen: null, stamp: 0, found: [] };

function nodeGridCell(u, v) {
  const grid = nodeGrid;
  return Math.min(grid.down - 1, Math.max(0, v)) * grid.across + Math.min(grid.across - 1, Math.max(0, u));
}

function nodeGridBuild(reach) {
  const grid = nodeGrid;
  let loX = Infinity;
  let hiX = -Infinity;
  let loY = Infinity;
  let hiY = -Infinity;
  for (const node of nodes) {
    if (node.x < loX) loX = node.x;
    if (node.x > hiX) hiX = node.x;
    if (node.y < loY) loY = node.y;
    if (node.y > hiY) hiY = node.y;
  }
  let cell = Math.max(NODE_GRID_MIN, Math.ceil(reach / NODE_GRID_FILL));
  while (((hiX - loX) / cell + 1) * ((hiY - loY) / cell + 1) > NODE_GRID_CELLS) cell *= 2;
  grid.cell = cell;
  grid.x0 = loX;
  grid.y0 = loY;
  grid.across = Math.floor((hiX - loX) / cell) + 1;
  grid.down = Math.floor((hiY - loY) / cell) + 1;
  grid.head = new Int32Array(grid.across * grid.down).fill(-1);
  grid.next = new Int32Array(nodes.length);
  grid.at = new Int32Array(nodes.length);
  if (!grid.seen || grid.seen.length < nodes.length) grid.seen = new Uint32Array(nodes.length);
  for (let i = 0; i < nodes.length; i++) {
    const at = nodeGridCell(Math.floor((nodes[i].x - loX) / cell), Math.floor((nodes[i].y - loY) / cell));
    grid.next[i] = grid.head[at];
    grid.head[at] = i;
    grid.at[i] = at;
  }
  grid.live = true;
}

// The note at `i` moved: it goes to the list of the cell it stands in now.
function nodeGridMove(i) {
  const grid = nodeGrid;
  const to = nodeGridCell(Math.floor((nodes[i].x - grid.x0) / grid.cell), Math.floor((nodes[i].y - grid.y0) / grid.cell));
  const from = grid.at[i];
  if (to === from) return;
  if (grid.head[from] === i) grid.head[from] = grid.next[i];
  else {
    let j = grid.head[from];
    while (grid.next[j] !== i) j = grid.next[j];
    grid.next[j] = grid.next[i];
  }
  grid.next[i] = grid.head[to];
  grid.head[to] = i;
  grid.at[i] = to;
}

// The notes in the 3 by 3 cells round (x, y), each once. The list is reused by the next call.
function nodeGridNear(x, y) {
  const grid = nodeGrid;
  const found = grid.found;
  found.length = 0;
  const u = Math.floor((x - grid.x0) / grid.cell);
  const v = Math.floor((y - grid.y0) / grid.cell);
  for (let b = Math.max(0, Math.min(grid.down - 1, v) - 1); b <= Math.min(grid.down - 1, Math.max(0, v) + 1); b++) {
    for (let a = Math.max(0, Math.min(grid.across - 1, u) - 1); a <= Math.min(grid.across - 1, Math.max(0, u) + 1); a++) {
      for (let j = grid.head[b * grid.across + a]; j >= 0; j = grid.next[j]) found.push(j);
    }
  }
  return found;
}

// How many cells the box covers.
function nodeGridCovers(loX, hiX, loY, hiY) {
  const grid = nodeGrid;
  const u0 = Math.min(grid.across - 1, Math.max(0, Math.floor((loX - grid.x0) / grid.cell)));
  const u1 = Math.min(grid.across - 1, Math.max(0, Math.floor((hiX - grid.x0) / grid.cell)));
  const v0 = Math.min(grid.down - 1, Math.max(0, Math.floor((loY - grid.y0) / grid.cell)));
  const v1 = Math.min(grid.down - 1, Math.max(0, Math.floor((hiY - grid.y0) / grid.cell)));
  return (u1 - u0 + 1) * (v1 - v0 + 1);
}

// The notes in the cells the box covers (a note outside the box may be among them). The list is reused by the next call.
function nodeGridBox(loX, hiX, loY, hiY) {
  const grid = nodeGrid;
  const found = grid.found;
  found.length = 0;
  const u0 = Math.min(grid.across - 1, Math.max(0, Math.floor((loX - grid.x0) / grid.cell)));
  const u1 = Math.min(grid.across - 1, Math.max(0, Math.floor((hiX - grid.x0) / grid.cell)));
  const v0 = Math.min(grid.down - 1, Math.max(0, Math.floor((loY - grid.y0) / grid.cell)));
  const v1 = Math.min(grid.down - 1, Math.max(0, Math.floor((hiY - grid.y0) / grid.cell)));
  for (let v = v0; v <= v1; v++) {
    for (let u = u0; u <= u1; u++) {
      for (let j = grid.head[v * grid.across + u]; j >= 0; j = grid.next[j]) found.push(j);
    }
  }
  return found;
}

//: **What the passes leave on a line is cleared once, at the end** (INBOX 1400).
//: `untangleFree` looks at notes only, so three passes left 7 notes on lines
//: (`tests/test_graph_layout.py`). A check on every move kept them off but cost
//: the passes a fifth of their gain (36 notes, mean of 6 layouts: 61 crossings
//: with it, 50 without), so the passes move freely and `untangleCleanup` clears
//: what they and the relax left. `untangleNear` says whether a note is within
//: its radius and `untangle.margin` of a line: the curve the canvas draws
//: (`clearCurve`) or the chord (a hub's lines are drawn straight).
const UNTANGLE_LINE_BOW = 30;
function untangleChordD2(note, a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const u = Math.max(0, Math.min(1, ((note.x - a.x) * dx + (note.y - a.y) * dy) / (dx * dx + dy * dy || 1)));
  return (note.x - a.x - u * dx) ** 2 + (note.y - a.y - u * dy) ** 2;
}

// `clearPts` holds the drawn curve of the line (`points` of them): is the note within `need` of it or of the chord?
function untangleNearCurve(note, a, b, points, need) {
  clearNearest(note, points);
  return Math.min(untangleChordD2(note, a, b), clearNear[0]) < need * need;
}

function untangleNear(note, a, b) {
  const d2 = untangleChordD2(note, a, b);
  const need = (note.r || 8) + untangle.margin;
  // The curve bows at most `UNTANGLE_LINE_BOW` from its chord: a note farther than that is not near, and the curve is not built.
  const far = need + UNTANGLE_LINE_BOW;
  if (d2 >= far * far) return false;
  return untangleNearCurve(note, a, b, clearCurve(a, b), need);
}

//: **A uniform grid of line segments** (INBOX 1400, round 5). Asking every
//: line about every note made the cleanup cost 220 to 320 ms at 186 notes for
//: no gain, so it was skipped above `UNTANGLE_BIG` and about 45 notes stayed on
//: lines. Each line (its chord and, when drawn curved, its 5-point curve) is
//: filed in the cells a sample every half cell along it falls in; a cell is
//: `LINE_GRID_FILL` of the reach a note can be from a line it overlaps (the
//: widest note plus the largest margin), so the lines that can touch a note are
//: all in the 3 by 3 cells round it. The grid is a list of candidates only:
//: `untangleNear` still decides. It is exact while the notes stand where they
//: did when `lineGridBuild` ran, so it is rebuilt after a note moves and
//: `lineGrid.live` is cleared when the cleanup ends (`untangleOnLine` then scans).
const LINE_GRID_FILL = 0.75;
const LINE_GRID_MIN = 32;
const LINE_GRID_ROW = 1048576;
const lineGrid = { live: false, cell: 0, cells: new Map(), seen: null, stamp: 0, found: [], pts: null, count: null, box: null };

function lineGridAdd(k, x0, y0, x1, y1) {
  const grid = lineGrid;
  const cell = grid.cell;
  const dx = x1 - x0;
  const dy = y1 - y0;
  const steps = Math.max(1, Math.ceil(Math.hypot(dx, dy) / (cell / 2)));
  for (let s = 0; s <= steps; s++) {
    const key = Math.floor((x0 + (dx * s) / steps) / cell) * LINE_GRID_ROW + Math.floor((y0 + (dy * s) / steps) / cell);
    let list = grid.cells.get(key);
    if (!list) grid.cells.set(key, (list = []));
    // Samples of one line run cell to cell: only the last entry can repeat.
    if (list[list.length - 1] !== k) list.push(k);
  }
}

// Keep the points line `k` is drawn through where it stands now, for `lineGridTouches`; the cells are untouched.
function lineCurveFile(k) {
  const grid = lineGrid;
  const points = clearCurve(nodes[untangle.ea[k]], nodes[untangle.eb[k]]);
  const at = k * 10;
  let loX = Infinity;
  let hiX = -Infinity;
  let loY = Infinity;
  let hiY = -Infinity;
  for (let i = 0; i < points; i++) {
    const x = clearPts[i * 2];
    const y = clearPts[i * 2 + 1];
    grid.pts[at + i * 2] = x;
    grid.pts[at + i * 2 + 1] = y;
    if (x < loX) loX = x;
    if (x > hiX) hiX = x;
    if (y < loY) loY = y;
    if (y > hiY) hiY = y;
  }
  grid.count[k] = points;
  grid.box[k * 4] = loX;
  grid.box[k * 4 + 1] = hiX;
  grid.box[k * 4 + 2] = loY;
  grid.box[k * 4 + 3] = hiY;
  return points;
}

// File line `k` where it stands now: its points, and the cells its chord and curve pass through.
function lineGridFile(k) {
  const points = lineCurveFile(k);
  for (let i = 1; i < points; i++) lineGridAdd(k, clearPts[i * 2 - 2], clearPts[i * 2 - 1], clearPts[i * 2], clearPts[i * 2 + 1]);
  // The chord is the line unless it is drawn curved, and then it is filed too.
  if (points > 2) lineGridAdd(k, nodes[untangle.ea[k]].x, nodes[untangle.ea[k]].y, nodes[untangle.eb[k]].x, nodes[untangle.eb[k]].y);
}

function lineGridBuild(reach) {
  const grid = lineGrid;
  const count = untangle.ea.length;
  grid.cell = Math.max(LINE_GRID_MIN, Math.ceil(reach / LINE_GRID_FILL));
  grid.cells.clear();
  if (!grid.seen || grid.seen.length < count) {
    grid.seen = new Uint32Array(count);
    grid.pts = new Float64Array(count * 10);
    grid.count = new Uint8Array(count);
    grid.box = new Float64Array(count * 4);
    grid.stamp = 0;
  }
  for (let k = 0; k < count; k++) lineGridFile(k);
  grid.live = true;
}

// The lines of the note at `i` moved with it: file them again. The cells
// they left keep their entry (a candidate that is not near is turned down by `lineGridTouches`).
function lineGridRefile(i) {
  for (const k of untangle.incident[i]) lineGridFile(k);
}

// `untangleNear` for line `k` from the points filed with it: the same distance to the curve and the chord, no curve rebuilt.
function lineGridTouches(note, k) {
  const grid = lineGrid;
  const need = (note.r || 8) + untangle.margin;
  const at = k * 10;
  const bx = k * 4;
  if (note.x < grid.box[bx] - need || note.x > grid.box[bx + 1] + need || note.y < grid.box[bx + 2] - need || note.y > grid.box[bx + 3] + need) return false;
  const pts = grid.pts;
  const last = at + grid.count[k] * 2 - 2;
  const need2 = need * need;
  let prevX = pts[at];
  let prevY = pts[at + 1];
  for (let i = at + 2; i <= last; i += 2) {
    const dx = pts[i] - prevX;
    const dy = pts[i + 1] - prevY;
    const u = Math.max(0, Math.min(1, ((note.x - prevX) * dx + (note.y - prevY) * dy) / (dx * dx + dy * dy || 1)));
    if ((note.x - prevX - u * dx) ** 2 + (note.y - prevY - u * dy) ** 2 < need2) return true;
    prevX = pts[i];
    prevY = pts[i + 1];
  }
  if (grid.count[k] > 2) {
    const dx = pts[last] - pts[at];
    const dy = pts[last + 1] - pts[at + 1];
    const u = Math.max(0, Math.min(1, ((note.x - pts[at]) * dx + (note.y - pts[at + 1]) * dy) / (dx * dx + dy * dy || 1)));
    if ((note.x - pts[at] - u * dx) ** 2 + (note.y - pts[at + 1] - u * dy) ** 2 < need2) return true;
  }
  return false;
}

// The lines that may be within the grid's reach of (x, y), each once. The list is reused by the next call.
function lineGridNear(x, y) {
  const grid = lineGrid;
  const cx = Math.floor(x / grid.cell);
  const cy = Math.floor(y / grid.cell);
  const found = grid.found;
  found.length = 0;
  grid.stamp += 1;
  for (let u = cx - 1; u <= cx + 1; u++) {
    for (let v = cy - 1; v <= cy + 1; v++) {
      const list = grid.cells.get(u * LINE_GRID_ROW + v);
      if (!list) continue;
      for (let at = 0; at < list.length; at++) {
        const k = list[at];
        if (grid.seen[k] === grid.stamp) continue;
        grid.seen[k] = grid.stamp;
        found.push(k);
      }
    }
  }
  return found;
}

// `lineGridNear` and the test in one walk that stops at the first line over the note at `i`: a spot in a crowded map is mostly on one.
function lineGridHit(i) {
  const grid = lineGrid;
  const node = nodes[i];
  const cx = Math.floor(node.x / grid.cell);
  const cy = Math.floor(node.y / grid.cell);
  grid.stamp += 1;
  for (let u = cx - 1; u <= cx + 1; u++) {
    for (let v = cy - 1; v <= cy + 1; v++) {
      const list = grid.cells.get(u * LINE_GRID_ROW + v);
      if (!list) continue;
      for (let at = 0; at < list.length; at++) {
        const k = list[at];
        if (grid.seen[k] === grid.stamp) continue;
        grid.seen[k] = grid.stamp;
        if (untangle.ea[k] !== i && untangle.eb[k] !== i && lineGridTouches(node, k)) return true;
      }
    }
  }
  return false;
}

// Does a line the note at `i` does not join pass over it?
function untangleOnLine(i) {
  const node = nodes[i];
  const ea = untangle.ea;
  const eb = untangle.eb;
  if (lineGrid.live) return lineGridHit(i);
  for (let k = 0; k < ea.length; k++) {
    const a = nodes[ea[k]];
    const b = nodes[eb[k]];
    if (a !== node && b !== node && untangleNear(node, a, b)) return true;
  }
  return false;
}

// Does a line of the note at `i` pass over a note it does not join?
function untangleLineOver(i) {
  const ea = untangle.ea;
  const eb = untangle.eb;
  const reach = untangle.widest + untangle.margin + UNTANGLE_LINE_BOW;
  for (const k of untangle.incident[i]) {
    const a = nodes[ea[k]];
    const b = nodes[eb[k]];
    const loX = Math.min(a.x, b.x) - reach;
    const hiX = Math.max(a.x, b.x) + reach;
    const loY = Math.min(a.y, b.y) - reach;
    const hiY = Math.max(a.y, b.y) + reach;
    // The notes in the line's box: the cells it covers when they are fewer than the notes, else all of them.
    const near = nodeGrid.live && nodeGridCovers(loX, hiX, loY, hiY) < nodes.length / 3 ? nodeGridBox(loX, hiX, loY, hiY) : null;
    let points = 0;
    for (let c = 0, count = near ? near.length : nodes.length; c < count; c++) {
      const other = near ? nodes[near[c]] : nodes[c];
      if (other === a || other === b || other.x < loX || other.x > hiX || other.y < loY || other.y > hiY) continue;
      const need = (other.r || 8) + untangle.margin;
      const far = need + UNTANGLE_LINE_BOW;
      if (untangleChordD2(other, a, b) >= far * far) continue;
      // The curve is built once for the line, when the first note is near its chord, not once for each note.
      if (!points) points = clearCurve(a, b);
      if (untangleNearCurve(other, a, b, points, need)) return true;
    }
  }
  return false;
}

//: **What is left on a line is pushed off it, once, at the end** (INBOX 1400).
//: The notes that stand on a line when the last relax rests stay there: the clearance
//: force is a push the links pull back, and in a crowded category no ring of
//: spots round the note is both clear of lines and of notes (tried; 5 of 13
//: stayed). So the last step is a projection, not a force: up to
//: `UNTANGLE_CLEAN_ITERS` times, each note nearer a line than its radius and
//: `UNTANGLE_CLEAN_MARGIN` steps straight off it (the note that is free, else
//: the line's two ends), and notes pushed into each other part. Nothing
//: pulls back, and no note travels past `UNTANGLE_CLEAN_FAR`. Half the turns
//: of round 4 (60): 6 layouts offline left 15 notes on lines at 186 notes with 30
//: and 18 with 60, 1.3 and 1.5 at 36, so the later turns cost time and moved nothing.
const UNTANGLE_CLEAN_ITERS = 30;
const UNTANGLE_CLEAN_MARGIN = 3;
const UNTANGLE_CLEAN_FAR = 40;
const UNTANGLE_CLEAN_SLACK = 12;
//: A note between two lines closer than its width cannot be pushed off one
//: without the other: it steps to the nearest spot, in rings round where it
//: stands, that is clear of every line and note, at the fewest crossings it
//: adds (at most `UNTANGLE_CLEAN_COST`; a note on a line reads worse).
const UNTANGLE_CLEAN_RINGS = 8;
const UNTANGLE_CLEAN_TURNS = 16;
const UNTANGLE_CLEAN_COST = 3;
const UNTANGLE_CLEAN_SWEEPS = 3;
// The squared distance from the note to line `k`, from the points filed with it (the chord too when it is drawn curved).
function lineGridGap(note, k) {
  const grid = lineGrid;
  const count = grid.count[k];
  for (let i = 0; i < count * 2; i++) clearPts[i] = grid.pts[k * 10 + i];
  clearNearest(note, count);
  return Math.min(clearNear[0], untangleChordD2(note, nodes[untangle.ea[k]], nodes[untangle.eb[k]]));
}

//: **Nearest first** (round 6). The step-off ran in index order and is cut by
//: its clock, so the notes the clock reached late stayed on their lines whatever
//: they needed. The notes on a line are ordered by how far into it they stand
//: (the radius and margin less the distance to the line, the deepest of the lines
//: it is on): the shallow ones cost one ring each, so more notes are off a
//: line when the clock runs out. Needs the line grid.
function untangleStepOrder(free) {
  const ea = untangle.ea;
  const eb = untangle.eb;
  const order = [];
  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    if (!free(node)) continue;
    const need = (node.r || 8) + untangle.margin;
    let deepest = 0;
    for (const k of lineGridNear(node.x, node.y)) {
      if (ea[k] === i || eb[k] === i || !lineGridTouches(node, k)) continue;
      deepest = Math.max(deepest, need - Math.sqrt(lineGridGap(node, k)));
    }
    if (deepest > 0) order.push([deepest, i]);
  }
  order.sort((p, q) => p[0] - q[0] || p[1] - q[1]);
  return order.map((entry) => entry[1]);
}

function untangleStepOff(i) {
  const node = nodes[i];
  const mine = untangle.incident[i];
  const x0 = node.x;
  const y0 = node.y;
  const before = mine.length ? crossingsOn(mine) : 0;
  const step = (node.r || 8) + CLEAR_GAP;
  let best = null;
  let cost = UNTANGLE_CLEAN_COST + 1;
  for (let ring = 1; ring <= UNTANGLE_CLEAN_RINGS; ring++) {
    for (let t = 0; t < UNTANGLE_CLEAN_TURNS; t++) {
      const angle = (2 * Math.PI * t) / UNTANGLE_CLEAN_TURNS;
      node.x = x0 + Math.cos(angle) * step * ring;
      node.y = y0 + Math.sin(angle) * step * ring;
      if (!untangleInside(node) || !untangleFree(node, node.x, node.y, COLLIDE_PAD / 2)) continue;
      if (untangleOnLine(i) || untangleLineOver(i)) continue;
      const added = mine.length ? crossingsOn(mine) - before : 0;
      if (added < cost) {
        cost = added;
        best = [node.x, node.y];
      }
    }
    if (best && cost <= 0) break;
  }
  node.x = best ? best[0] : x0;
  node.y = best ? best[1] : y0;
}

function untangleCleanup() {
  // Each half of the cleanup (the pushes, the step-offs) gets half of what a pass gets.
  const half = untangleBudget() / 2;
  const until = Date.now() + half;
  const free = (node) => node.fx == null && !node.placed;
  const startX = nodes.map((n) => n.x);
  const startY = nodes.map((n) => n.y);
  const ea = untangle.ea;
  const eb = untangle.eb;
  // The (line, note) pairs near enough to matter and the note pairs near
  // enough to meet, found once: a push moves a note a few steps, not across the map.
  untangleReach();
  untangle.margin = UNTANGLE_CLEAN_MARGIN + UNTANGLE_CLEAN_SLACK;
  lineGridBuild(untangle.widest + untangle.margin);
  // Line by line, then note by note, as the pushes below were tuned in that order.
  const pairs = [];
  let stuck = false;
  for (let m = 0; m < nodes.length; m++) {
    const node = nodes[m];
    for (const k of lineGridNear(node.x, node.y)) {
      if (ea[k] !== m && eb[k] !== m && lineGridTouches(node, k)) pairs.push(k * nodes.length + m);
    }
  }
  pairs.sort((p, q) => p - q);
  // A line's drawn points are kept with it (`lineCurveFile`) and filed again only when one of its ends moved: `stale`.
  const stale = new Uint8Array(ea.length);
  const touched = (idx) => {
    for (const k of untangle.incident[idx]) stale[k] = 1;
  };
  untangle.margin = UNTANGLE_CLEAN_MARGIN;
  for (let i = 0; i < nodes.length && !stuck; i++) stuck = untangleOnLine(i);
  const meet = [];
  const spread = (node) => Math.max((node.r || 8) + COLLIDE_PAD, 2 * (node.r || 8));
  for (let i = 0; stuck && i < nodes.length; i++) {
    for (let j = i + 1; j < nodes.length; j++) {
      // The collision force's own radii: a smaller gap would be pushed back open by the next tick.
      const need = spread(nodes[i]) + spread(nodes[j]);
      if (Math.hypot(nodes[i].x - nodes[j].x, nodes[i].y - nodes[j].y) < need + 2 * UNTANGLE_CLEAN_SLACK) meet.push([i, j, need]);
    }
  }
  for (let iter = 0; stuck && iter < UNTANGLE_CLEAN_ITERS && Date.now() < until; iter++) {
    let moved = false;
    for (const at of pairs) {
      const k = Math.floor(at / nodes.length);
      const m = at % nodes.length;
      const a = nodes[ea[k]];
      const b = nodes[eb[k]];
      const node = nodes[m];
      const need = (node.r || 8) + untangle.margin;
      if (stale[k]) {
        lineCurveFile(k);
        stale[k] = 0;
      }
      if (!lineGridTouches(node, k)) continue;
      // The nearest point of the drawn line (curve or chord, whichever is nearer), from the points filed with it.
      for (let c = 0; c < lineGrid.count[k] * 2; c++) clearPts[c] = lineGrid.pts[k * 10 + c];
      clearNearest(node, lineGrid.count[k]);
      let qx = clearNear[1];
      let qy = clearNear[2];
      let d = Math.sqrt(clearNear[0]);
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const u = Math.max(0, Math.min(1, ((node.x - a.x) * dx + (node.y - a.y) * dy) / (dx * dx + dy * dy || 1)));
      const cd = Math.hypot(node.x - a.x - u * dx, node.y - a.y - u * dy);
      if (cd < d) {
        d = cd;
        qx = a.x + u * dx;
        qy = a.y + u * dy;
      }
      let nx = node.x - qx;
      let ny = node.y - qy;
      const len = Math.hypot(nx, ny);
      if (len > 1e-6) {
        nx /= len;
        ny /= len;
      } else {
        const chord = Math.hypot(dx, dy) || 1;
        nx = -dy / chord;
        ny = dx / chord;
      }
      const push = need - d + 1;
      if (free(node)) {
        node.x += nx * push;
        node.y += ny * push;
        touched(m);
      } else if (free(a) || free(b)) {
        const share = (free(a) ? 1 : 0) + (free(b) ? 1 : 0);
        if (free(a)) {
          a.x -= (nx * push) / share;
          a.y -= (ny * push) / share;
          touched(ea[k]);
        }
        if (free(b)) {
          b.x -= (nx * push) / share;
          b.y -= (ny * push) / share;
          touched(eb[k]);
        }
      } else continue;
      moved = true;
    }
    // Notes pushed into each other part, except in the last quarter of the
    // turns: the lines have the last word, nothing ticks after them (`untangle.holding`).
    if (iter < UNTANGLE_CLEAN_ITERS * 0.75) {
      for (const [pi, qi, need] of meet) {
        const p = nodes[pi];
        const q = nodes[qi];
        const dx = q.x - p.x;
        const dy = q.y - p.y;
        const d = Math.hypot(dx, dy);
        if (d >= need) continue;
        const nx = d > 1e-6 ? dx / d : 1;
        const ny = d > 1e-6 ? dy / d : 0;
        const gap = need - d;
        const share = (free(p) ? 1 : 0) + (free(q) ? 1 : 0);
        if (!share) continue;
        if (free(p)) {
          p.x -= (nx * gap) / share;
          p.y -= (ny * gap) / share;
          touched(pi);
        }
        if (free(q)) {
          q.x += (nx * gap) / share;
          q.y += (ny * gap) / share;
          touched(qi);
        }
        moved = true;
      }
    }
    if (!moved) break;
  }
  // A note that travelled too far is put back: the point is to clear a line, not to move the map.
  nodes.forEach((node, i) => {
    if (Math.hypot(node.x - startX[i], node.y - startY[i]) > UNTANGLE_CLEAN_FAR) {
      node.x = startX[i];
      node.y = startY[i];
    }
  });
  untangle.margin = 1;
  untangleReach();
  lineGridBuild(untangle.widest + UNTANGLE_CLEAN_MARGIN + UNTANGLE_CLEAN_SLACK);
  nodeGridBuild(untangle.widest + COLLIDE_PAD / 2 + UNTANGLE_CLEAN_MARGIN);
  const stepUntil = Date.now() + half;
  // A sweep that moved a note may have opened room for one it could not move: the notes still on a line go again while the clock lasts.
  for (let sweep = 0, any = true; any && sweep < UNTANGLE_CLEAN_SWEEPS && Date.now() < stepUntil; sweep++) {
    any = false;
    for (const i of untangleStepOrder(free)) {
      if (Date.now() >= stepUntil) break;
      // An earlier step may have cleared this one's line.
      if (!untangleOnLine(i)) continue;
      const x0 = nodes[i].x;
      const y0 = nodes[i].y;
      untangleStepOff(i);
      // It moved: its lines are filed again and it is in another cell for the next note.
      if (nodes[i].x !== x0 || nodes[i].y !== y0) {
        lineGridRefile(i);
        nodeGridMove(i);
        any = true;
      }
    }
  }
  lineGrid.live = false;
  nodeGrid.live = false;
  untangle.margin = 0;
  untangle.holding = untangleGlide(startX, startY) > 0;
  return untangle.holding ? 1 : 0;
}

// A moved note stays inside its category's reach (the farthest of its notes
// from their middle when the pass began), so a move never stretches the map.
function untangleReach() {
  const groups = new Map();
  for (const node of nodes) {
    if (!groups.has(node.group)) groups.set(node.group, []);
    groups.get(node.group).push(node);
  }
  untangle.reach = new Map();
  untangle.widest = nodes.reduce((w, n) => Math.max(w, n.r || 8), 0);
  for (const [group, list] of groups) {
    const cx = list.reduce((a, n) => a + n.x, 0) / list.length;
    const cy = list.reduce((a, n) => a + n.y, 0) / list.length;
    const far = list.reduce((a, n) => Math.max(a, Math.hypot(n.x - cx, n.y - cy)), 0);
    untangle.reach.set(group, { cx, cy, far });
  }
}
function untangleInside(node) {
  const home = untangle.reach && untangle.reach.get(node.group);
  return !home || Math.hypot(node.x - home.cx, node.y - home.cy) <= home.far * UNTANGLE_REACH;
}

function untangleLayout() {
  // Organic only: Clusters places its hubs at each category's heart and its
  // bridges on the rim (`hubForce`, `rimOffset`), Galaxy by degree; a move
  // here would undo what those shapes are for.
  if (untangle.done || !untangle.edges.length || ring.shape !== "organic") return 0;
  untangle.done = true;
  const until = Date.now() + untangleBudget();
  const still = (node) => node.fx != null || node.placed;
  const startX = nodes.map((n) => n.x);
  const startY = nodes.map((n) => n.y);
  untangleReach();
  untangle.total = crossingsOn(untangle.edges.map((_, i) => i));
  untangle.gain = 0;
  for (let round = 0; round < UNTANGLE_ROUNDS && Date.now() < until; round++) {
    let gained = untangleGroups(still);
    for (let i = 0; i < nodes.length && Date.now() < until; i++) {
      const node = nodes[i];
      const mine = untangle.incident[i];
      if (still(node) || !mine.length) continue;
      // Trade places with a near note of the same category.
      const near = [];
      for (let j = 0; j < nodes.length; j++) {
        const other = nodes[j];
        if (j === i || other.group !== node.group || still(other)) continue;
        near.push([Math.hypot(other.x - node.x, other.y - node.y), j]);
      }
      near.sort((p, q) => p[0] - q[0]);
      for (const [, j] of near.slice(0, UNTANGLE_NEAR)) {
        const other = nodes[j];
        const both = [...new Set([...mine, ...untangle.incident[j]])];
        const before = crossingsOn(both);
        if (!before) continue;
        [node.x, other.x] = [other.x, node.x];
        [node.y, other.y] = [other.y, node.y];
        const after = crossingsOn(both);
        if (after < before) {
          gained += before - after;
          continue;
        }
        [node.x, other.x] = [other.x, node.x];
        [node.y, other.y] = [other.y, node.y];
      }
      // A note with few links tries spots round each note it joins, at the
      // distance it stands from it now; a well-linked one, spots across its
      // category's reach (where its lines cross least is where it belongs).
      const before = crossingsOn(mine);
      if (!before) continue;
      const x0 = node.x;
      const y0 = node.y;
      let best = before;
      let bestAt = null;
      if (mine.length > UNTANGLE_MOVE_LINKS) {
        const home = untangle.reach.get(node.group);
        if (!home) continue;
        for (let ring = 1; ring <= UNTANGLE_HUB_RINGS; ring++) {
          const r = (home.far * UNTANGLE_REACH * ring) / UNTANGLE_HUB_RINGS;
          for (let t = 0; t < UNTANGLE_TURNS; t++) {
            const angle = (2 * Math.PI * t) / UNTANGLE_TURNS;
            node.x = home.cx + Math.cos(angle) * r;
            node.y = home.cy + Math.sin(angle) * r;
            const after = crossingsOn(mine);
            if (after < best && untangleFree(node, node.x, node.y, COLLIDE_PAD)) {
              best = after;
              bestAt = [node.x, node.y];
            }
          }
        }
        node.x = bestAt ? bestAt[0] : x0;
        node.y = bestAt ? bestAt[1] : y0;
        if (bestAt) gained += before - best;
        continue;
      }
      for (const line of mine) {
        const other = nodes[untangle.ea[line] === i ? untangle.eb[line] : untangle.ea[line]];
        const reach = Math.max(1, Math.hypot(x0 - other.x, y0 - other.y));
        const from = Math.atan2(y0 - other.y, x0 - other.x);
        for (let t = mine.length === 1 ? 1 : 0; t < UNTANGLE_TURNS; t++) {
          const angle = from + (2 * Math.PI * t) / UNTANGLE_TURNS;
          node.x = other.x + Math.cos(angle) * reach;
          node.y = other.y + Math.sin(angle) * reach;
          const after = crossingsOn(mine);
          if (after < best && untangleInside(node) && untangleFree(node, node.x, node.y, COLLIDE_PAD)) {
            best = after;
            bestAt = [node.x, node.y];
          }
        }
      }
      node.x = bestAt ? bestAt[0] : x0;
      node.y = bestAt ? bestAt[1] : y0;
      if (bestAt) gained += before - best;
    }
    untangle.gain += gained;
    if (!gained) break;
  }
  return untangleGlide(startX, startY);
}

// The move is shown, not jumped: back to the start, then a glide (`shuffleStep`).
function untangleGlide(startX, startY) {
  let moved = 0;
  nodes.forEach((node, i) => {
    if (node.x === startX[i] && node.y === startY[i]) return;
    moved += 1;
    node.tx = node.x;
    node.ty = node.y;
    node.x = startX[i];
    node.y = startY[i];
  });
  return moved;
}

//: **Settled, untangled and cleaned before anything is shown** (the owner,
//: 2026-10-27: "a bunch of nodes started individually rearranging themselves
//: sliding instantly into position one after the other and then it just
//: stayed like that"). The passes waited for rest and each glided its moves
//: in 12 frames, the first closing a quarter of the way (134 px in one frame
//: on the 36-note seed, 37 frames over 20 px), with a relax, a second pass, a
//: third and the cleanup after it: four bursts over 4 s, 10.6 s to rest at
//: 300 notes (`graphopen.js`). Now the cooling, every pass with its relax and
//: the cleanup run here in one go, nothing posted, and whoever called shows
//: the result as one motion. False when `until` came first (a big map): the
//: live loop cools the rest and calls this again at rest.
function landTargets() {
  for (const node of nodes) {
    if (node.tx === undefined) continue;
    node.x = node.tx;
    node.y = node.ty;
    node.tx = undefined;
    node.ty = undefined;
  }
}

function coolToRest(until) {
  while (simulation.alpha() >= simulation.alphaMin() && Date.now() < until) {
    simulation.tick();
    ticks += 1;
    clampToWorld();
  }
  return simulation.alpha() < simulation.alphaMin();
}

//: Passes not yet run, or the cleanup after them. A drag marks them spent.
function untangleOwed() {
  return !untangle.done || (untangle.passes > 0 && (untangle.passes < untanglePasses() || !untangle.cleaned));
}

//: `deadline`: a pass or cleanup that would not end by then is not begun,
//: and the answer is "late" (the opening shows the map at rest and goes on
//: out of sight, `pendingStep`).
function settleUntangled(until, deadline) {
  if (!coolToRest(until)) return false;
  const late = () => deadline && Date.now() + untangleBudget() > deadline;
  while (!untangle.done || (untangle.passes > 0 && untangle.passes < untanglePasses())) {
    if (late()) return "late";
    untangle.done = false;
    if (!untangleLayout()) break;
    landTargets();
    untangle.passes += 1;
    if (untangle.gain < Math.max(2, untangle.total * UNTANGLE_MIN_SHARE)) untangle.passes = UNTANGLE_PASSES;
    // A low heat lets the collision and the line clearance settle what the
    // moves brought close (a swap can put a hub where a small note stood).
    simulation.alpha(UNTANGLE_RELAX);
    if (!coolToRest(until)) return false;
  }
  untangle.done = true;
  if (untangle.passes > 0 && !untangle.cleaned) {
    if (late()) return "late";
    untangle.cleaned = true;
    if (untangleCleanup()) landTargets();
  }
  for (const node of nodes) {
    node.vx = 0;
    node.vy = 0;
  }
  //: The cleanup has the last word: no tick after it (a tick would let the
  //: links draw the notes it pushed off a line back onto it).
  untangle.holding = true;
  return true;
}

//: **One motion to the settled map, every note together** (the same report:
//: "I want it to be smooth and flowy"). A layout untangled at rest, after a
//: change of settings, a reshuffle or a big map's live settle, moves from
//: where it stands to where `settleUntangled` put it along one smoothstep:
//: from rest, to rest, no first frame that jumps and no last one that snaps.
//: 45 frames is 0.75 s; a swap of 100 px peaks at 3.3 px a frame.
const SETTLE_GLIDE_FRAMES = 45;
const settleGlide = { left: 0, sx: null, sy: null };

function settleGlideFrom(startX, startY) {
  let moved = 0;
  nodes.forEach((node, i) => {
    if (node.x === startX[i] && node.y === startY[i]) return;
    moved += 1;
    node.tx = node.x;
    node.ty = node.y;
  });
  if (!moved) return 0;
  settleGlide.sx = Float64Array.from(startX);
  settleGlide.sy = Float64Array.from(startY);
  settleGlide.left = SETTLE_GLIDE_FRAMES;
  settleGlideStep();
  return moved;
}

function smoothstep(u) {
  return u <= 0 ? 0 : u >= 1 ? 1 : u * u * (3 - 2 * u);
}

function settleGlideStep() {
  settleGlide.left -= 1;
  const e = smoothstep(1 - settleGlide.left / SETTLE_GLIDE_FRAMES);
  nodes.forEach((node, i) => {
    if (node.tx === undefined) return;
    node.x = settleGlide.sx[i] + (node.tx - settleGlide.sx[i]) * e;
    node.y = settleGlide.sy[i] + (node.ty - settleGlide.sy[i]) * e;
    if (settleGlide.left === 0) {
      node.tx = undefined;
      node.ty = undefined;
    }
  });
}

//: Stopped where it is: a drag or new settings act on the map on screen.
function settleGlideCancel() {
  if (!settleGlide.left) return;
  settleGlide.left = 0;
  for (const node of nodes) {
    node.tx = undefined;
    node.ty = undefined;
  }
}

//: **The settle out of sight runs in slices** (`PENDING_SLICE_MS` a turn),
//: so the worker still hears a drag or new settings while it works, and
//: nothing is posted until it is done: the screen keeps what it showed (the
//: map at rest, or nothing behind the first fade). Nobody watches it cool,
//: so it cools faster than a live layout (`PENDING_TICKS` from full heat to
//: rest, d3's formula, against about 300 live, where the slow decay is what
//: makes the motion look alive). Done, it hands over: the opening's playback
//: (`introInto`) or the one glide (`settleGlideFrom`). An opening that has
//: not settled by `WARM_MS` is shown where it got to and cools live; any
//: other is cut at `PENDING_MAX_MS`, the passes it has not run given up.
const PENDING_SLICE_MS = 12;
const PENDING_TICKS = 150;
const PENDING_MAX_MS = 4000;
const pending = { on: false, open: false, record: false, bloom: false, from: 0, sx: null, sy: null, alpha: 0, untangle: null };

function pendingStart(open, record, bloom) {
  pending.on = true;
  pending.open = open;
  pending.record = record;
  pending.bloom = bloom;
  pending.from = Date.now();
  pending.sx = nodes.map((n) => n.x);
  pending.sy = nodes.map((n) => n.y);
  pending.alpha = simulation.alpha();
  pending.untangle = { done: untangle.done, passes: untangle.passes, cleaned: untangle.cleaned };
  simulation.alphaDecay(1 - Math.pow(0.001, 1 / PENDING_TICKS));
}

function pendingEnd() {
  pending.on = false;
  simulation.alphaDecay(alphaDecayFor(nodes.length));
}

//: Called off by a message: the notes go back to where the screen shows
//: them, at the heat they had, and the passes are owed again.
function pendingCancel() {
  if (!pending.on) return;
  pendingEnd();
  nodes.forEach((node, i) => {
    node.tx = undefined;
    node.ty = undefined;
    if (node.fx != null) return;
    node.x = pending.sx[i];
    node.y = pending.sy[i];
    node.vx = 0;
    node.vy = 0;
  });
  simulation.alpha(pending.alpha);
  Object.assign(untangle, pending.untangle);
  untangle.holding = false;
}

function pendingStep() {
  const done = settleUntangled(Date.now() + PENDING_SLICE_MS, pending.open ? pending.from + WARM_MS : 0);
  if (done === true) {
    pendingEnd();
    if (pending.open) introInto(pending.sx, pending.sy, pending.record, pending.bloom);
    else settleGlideFrom(pending.sx, pending.sy);
    return;
  }
  const spent = Date.now() - pending.from;
  if (pending.open && (done === "late" || (spent > WARM_MS && untangle.passes > 0))) {
    // Cooled but not untangled by the budget (300 notes): shown as it
    // stands, the rest worked out of sight and glided to (`settleGlideFrom`).
    pending.open = false;
    pending.sx = nodes.map((n) => n.x);
    pending.sy = nodes.map((n) => n.y);
    pending.alpha = simulation.alpha();
    pending.untangle = { done: untangle.done, passes: untangle.passes, cleaned: untangle.cleaned };
    post(false);
  } else if (pending.open && spent > WARM_MS) {
    // Too big to cool out of sight: shown as it is, the rest cooled live.
    pendingEnd();
    untangle.holding = false;
    post(false);
  } else if (!pending.open && spent > PENDING_MAX_MS) {
    pendingEnd();
    untangle.done = true;
    untangle.passes = UNTANGLE_PASSES;
    untangle.cleaned = true;
    untangle.holding = false;
    landTargets();
    settleGlideFrom(pending.sx, pending.sy);
  }
}

function clampToWorld() {
  if (!world) return;
  for (const node of nodes) {
    const pad = (node.r || 8) + 12;
    node.x = Math.max(world.left + pad, Math.min(world.right - pad, node.x));
    node.y = Math.max(world.top + pad, Math.min(world.bottom - pad, node.y));
  }
}

function post(final) {
  if (inFlight > MAX_IN_FLIGHT && !final) return;
  const wanted = nodes.length * 2;
  let buffer = pool.pop();
  if (!buffer || buffer.length !== wanted) buffer = new Float32Array(wanted);
  for (let i = 0; i < nodes.length; i++) {
    buffer[i * 2] = nodes[i].x;
    buffer[i * 2 + 1] = nodes[i].y;
  }
  inFlight += 1;
  self.postMessage(
    {
      type: "tick",
      epoch,
      positions: buffer,
      alpha: simulation ? simulation.alpha() : 0,
      // How many times the simulation has stepped since `init`. Posted because
      // a frame the main thread paints and a step the worker takes are no
      // longer the same event, and a slow layout could otherwise be either
      // "the simulation is crawling" or "the paint is dropping frames" with no
      // way to tell which from the outside. It is one integer per frame.
      ticks,
      tickMs,
      running: !final,
    },
    [buffer.buffer]
  );
}

const LIVE_STEP_MS = 8;
const LIVE_MAX_STEPS = 40;

function stopLoop() {
  if (timer !== null) {
    clearTimeout(timer);
    timer = null;
  }
}

//: One tick per frame, self-scheduled. A dedicated worker has no
//: `requestAnimationFrame` (that lives on the window and, for a worker, only
//: inside an OffscreenCanvas context), so the 60 Hz cadence the plan asks for
//: is a timeout that subtracts the time the tick itself took.
function loop() {
  timer = null;
  if (!simulation) return;
  if (pending.on) {
    pendingStep();
    timer = setTimeout(loop, pending.on ? 0 : 16);
    return;
  }
  if (intro.frames.length) {
    introStep();
    timer = setTimeout(loop, INTRO_FRAME_MS);
    return;
  }
  if (shuffle.left > 0) {
    shuffleStep();
    clampToWorld();
    post(false);
    timer = setTimeout(loop, 16 * (perf ? 2 : 1));
    return;
  }
  if (settleGlide.left > 0) {
    settleGlideStep();
    post(false);
    timer = setTimeout(loop, 16 * (perf ? 2 : 1));
    return;
  }
  //: Untangled and cleaned is the last thing (`settleUntangled`): the map
  //: ends where it put the notes, with no tick after.
  if (untangle.holding) {
    untangle.holding = false;
    post(true);
    self.postMessage({ type: "end", alpha: simulation.alpha(), epoch });
    return;
  }
  const started = Date.now();
  //: **A cheap tick is not one a frame** (INBOX 1400: the map took 4.5 to
  //: 5.8 s to come to rest, `gm.js`). Once nothing is held, ticks that cost
  //: little run together up to `LIVE_STEP_MS` a frame, so the last of the
  //: cooling, motion too small to follow, takes a few frames, not a few
  //: hundred. Only the cooling of a new layout (an init, a reshuffle, new
  //: settings: the runs `untangle` waits on); a drag and the ease after a
  //: drop keep one tick a frame, their pace is the pointer's.
  const quick = !dragging && untangleOwed() && simulation.alpha() < WARM_ALPHA;
  let steps = 0;
  do {
    simulation.tick();
    ticks += 1;
    steps += 1;
  } while (quick && steps < LIVE_MAX_STEPS && Date.now() - started < LIVE_STEP_MS && simulation.alpha() >= simulation.alphaMin());
  const cost = Date.now() - started;
  tickMs = ticks === steps ? cost / steps : tickMs * 0.9 + (cost / steps) * 0.1;
  clampToWorld();
  const overBudget = !dragging && Date.now() - settleFrom > SETTLE_BUDGET_MS;
  const settled = !dragging && (simulation.alpha() < simulation.alphaMin() || overBudget);
  //: At rest and not yet untangled: the passes, their relax and the cleanup
  //: run out of sight (`pending`) and the map moves to the result in one glide.
  if (settled && !dragging && untangleOwed()) {
    post(false);
    pendingStart(false, false, false);
    timer = setTimeout(loop, 0);
    return;
  }
  if (settled) {
    post(true);
    self.postMessage({ type: "end", alpha: simulation.alpha(), epoch });
    return;
  }
  post(false);
  // **The worker yields as much time as it took, and this is the measurement
  // that made the whole feature work.**
  //
  // The obvious loop is "tick, then sleep whatever is left of the 16 ms
  // frame". On a notebook where a tick costs less than a frame that is right.
  // On the 2,000-note fixture a tick costs 74 ms, so there is never anything
  // left, the loop re-enters immediately, and the worker holds its thread flat
  // out for as long as the layout is hot. Measured in Chromium: an *idle*
  // 2,000-note map (nothing being dragged, the simulation merely still
  // cooling) ran the page at 2.5 fps with the main thread only 13% busy, 
  // the renderer simply could not get scheduled. The same map once the
  // simulation stopped ran at 58.7 fps with 9 ms frames. So the simulation
  // was not competing with the paint for the main thread any more; it was
  // competing with it for the CPU, which moving it to a worker does nothing
  // about on its own.
  //
  // A duty cycle fixes it: yield roughly as long as the tick took, so the
  // simulation gets about half a core and the renderer gets the other half.
  // On a machine where a tick is cheap this changes nothing (the `16 - cost`
  // branch wins). On a big notebook it halves how fast the layout converges
  // and hands back a map you can actually drag while it does, which is the
  // right trade during a drag, because the thing being looked at is the
  // pointer, not the convergence.
  //
  // The share is stricter while a drag is in flight. Then the frame the person
  // is actually watching is the one following their pointer, and a
  // neighbourhood that reorganises at 10 Hz under a pointer that tracks at
  // 60 Hz looks right; the reverse does not.
  const share = dragging ? 2 : 1;
  // Performance mode: the yield doubles, so the simulation takes at most a
  // quarter of a core and a small laptop keeps its frames for the paint.
  const rest = perf ? 2 : 1;
  timer = setTimeout(
    loop,
    (cost >= 12 ? Math.min(120, cost * share) : Math.max(4, 16 - cost)) * rest
  );
}

//: Every message that moves the layout comes through here, so this is where
//: the settle budget starts again.
function run() {
  settleFrom = Date.now();
  if (timer === null && simulation) timer = setTimeout(loop, 0);
}

//: Anything the person does stops the playback where it is: a drag, a pin,
//: a reshuffle act on the live layout, from where the notes are on screen.
//: The settle glide stops the same way, and the hold with it: the message
//: moves the map again.
const INTRO_KEEPS = new Set(["recycle", "init"]);

self.onmessage = (event) => {
  const message = event.data || {};
  if (!INTRO_KEEPS.has(message.type)) {
    introCancel();
    settleGlideCancel();
    pendingCancel();
    untangle.holding = false;
  }
  switch (message.type) {
    case "init": {
      stopLoop();
      dragging = false;
      carry.node = null;
      carry.followers = [];
      perf = message.perf === true;
      epoch = message.epoch || 0;
      ticks = 0;
      inFlight = 0;
      pool.length = 0;
      nodes = (message.nodes || []).map((n) => ({
        id: n.id,
        x: Number.isFinite(n.x) ? n.x : undefined,
        y: Number.isFinite(n.y) ? n.y : undefined,
        vx: 0,
        vy: 0,
        fx: n.fx == null ? null : n.fx,
        fy: n.fy == null ? null : n.fy,
        r: n.r || 8,
        group: n.group || "",
        degree: 0,
      }));
      //: A restored view's saved notes, held where they were seeded from the
      //: first step and released by the page's `thaw` once the notes it never
      //: saved have settled (graph-canvas.js, `held`).
      (message.nodes || []).forEach((n, i) => {
        const node = nodes[i];
        if (!n.held || node.fx != null || node.x === undefined) return;
        node.fx = node.x;
        node.fy = node.y;
        node.frozenByDrag = true;
      });
      indexById = new Map(nodes.map((n, i) => [n.id, i]));
      world = message.world || null;
      orbit.reach = null;
      orbit.items = [];
      COLLIDE_PAD = collidePadFor(nodes.length);
      const edges = (message.edges || [])
        .filter((e) => indexById.has(e.source) && indexById.has(e.target))
        .map((e) => ({ source: e.source, target: e.target, kind: e.kind, score: e.score, curated: e.curated === true }));
      for (const edge of edges) {
        const a = nodes[indexById.get(edge.source)];
        const b = nodes[indexById.get(edge.target)];
        a.degree += 1;
        b.degree += 1;
      }
      cohesion = groupCohesion(edges);
      untangleSetup(edges);
      // Each note's leaves: the notes linked to it and to nothing else (`leafForce`).
      for (const edge of edges) {
        const a = nodes[indexById.get(edge.source)];
        const b = nodes[indexById.get(edge.target)];
        if (a === b) continue;
        if (b.degree === 1 && a.degree > 1) (a.leaves || (a.leaves = [])).push(b);
        if (a.degree === 1 && b.degree > 1) (b.leaves || (b.leaves = [])).push(a);
      }
      // How many lines join each pair of categories (`groupOrder`).
      ring.affinity = new Map();
      ring.cache = null;
      ring.inner = new Map();
      for (const edge of edges) {
        const a = nodes[indexById.get(edge.source)].group;
        const b = nodes[indexById.get(edge.target)].group;
        if (a === b) {
          ring.inner.set(a, (ring.inner.get(a) || 0) + 1);
          continue;
        }
        const key = a < b ? `${a}\u0000${b}` : `${b}\u0000${a}`;
        ring.affinity.set(key, (ring.affinity.get(key) || 0) + 1);
      }
      //: How much of a hub each note is within its own category (0 to 1):
      //: its links to notes of the same category over the most any note of
      //: that category has. See `HUB_PULL`.
      const within = new Map();
      for (const edge of edges) {
        const a = nodes[indexById.get(edge.source)];
        const b = nodes[indexById.get(edge.target)];
        if (a === b) continue;
        if (a.group !== b.group) {
          // The categories it reaches out to (`rimOffset`).
          (a.outs || (a.outs = [])).push(b.group);
          (b.outs || (b.outs = [])).push(a.group);
          continue;
        }
        a.inner = (a.inner || 0) + 1;
        b.inner = (b.inner || 0) + 1;
        (a.peers || (a.peers = [])).push(b);
        (b.peers || (b.peers = [])).push(a);
        within.set(a.group, Math.max(within.get(a.group) || 0, a.inner, b.inner));
      }
      for (const node of nodes) {
        node.hub = within.get(node.group) ? (node.inner || 0) / within.get(node.group) : 0;
        node.away = node.degree ? 1 - (node.inner || 0) / node.degree : 0;
        if (node.peers && node.peers.length < 3) node.peers = null;
      }
      setRingSeed(message.seed);
      // Before the link force is built: its strengths read it (`crossStrength`).
      ring.shape = SHAPES.has(message.params && message.params.shape) ? message.params.shape : "organic";
      ring.on = groupingOn(message.params);
      shuffle.left = 0;
      const tuned = tuning(message.params);
      simulation = d3
        .forceSimulation(nodes)
        .velocityDecay(VELOCITY_DECAY)
        .alphaDecay(alphaDecayFor(nodes.length))
        .force(
          "link",
          d3
            .forceLink(edges)
            .id((d) => d.id)
            .distance(tuned.linkDistance)
            .strength(linkStrength)
        )
        .force(
          "charge",
          d3
            .forceManyBody()
            .strength(tuned.charge)
            // **`distanceMax` is the single biggest cost lever on a big
            // notebook, and it is a modelling choice as well as a speed one.**
            // Without it every note repels every other note however far apart
            // they are, which is both the expensive half of the Barnes-Hut
            // traversal and wrong: two notes a whole screen apart having a
            // measurable opinion about each other is what collapses a graph
            // into one round blob and hides its clusters (§2.2, "gravity that
            // pulls everything into one clump" is the same defect from the
            // other side). Beyond this radius the force is simply zero, so a
            // cluster is shaped by its own members. 900 is roughly a screen at
            // the fitted zoom and about ten times the link distance.
            .distanceMax(clustered() ? GROUPED_CHARGE_REACH : 900)
            // d3's default is 0.9. A slightly coarser Barnes-Hut approximation
            // costs accuracy nobody can see at this node size and buys a real
            // fraction of the per-tick cost on thousands of nodes.
            .theta(1.1)
        )
        // **A weak centre, not a strong one, and weak relative to how many
        // notes it is holding.** §2's complaint is "gravity that pulls
        // everything into one clump": a strong centring force flattens the
        // structure the repulsion just produced. These two are strong enough
        // that a detached cluster drifts back into frame eventually and weak
        // enough that clusters keep their shape.
        //
        // The scaling is the other half of `densityScale`, and it is the dial
        // that actually decides the *total* span: trimming the repulsion alone
        // runs into the collision radius (measured on the 300-note fixture:
        // the median nearest-neighbour gap was already down at 33px against a
        // collide diameter of 26, so there was nothing left to squeeze out of
        // it) while the centre keeps pulling the whole cloud in without
        // changing anything about how a cluster is arranged inside itself. It
        // is 1x up to the reference count, so a small notebook is untouched.
        .force("x", d3.forceX(0).strength(tuned.pullX))
        .force("y", d3.forceY(0).strength(tuned.pullY))
        .force("groupX", d3.forceX(0).strength(0))
        .force("groupY", d3.forceY(0).strength(0))
        .force("orbit", orbitForce)
        .force("clear", clearanceForce)
        .force("hub", hubForce)
        .force("tether", tetherForce)
        .force("carry", carryForce)
        .force("shape", shapeForce)
        .force("leaf", leafForce)
        .force(
          "collide",
          // At least a radius of air each side (INBOX 693, "minimum node gap of
          // about 2 node radii"): a big hub was only its pad from its neighbour.
          d3.forceCollide().radius((d) => Math.max((d.r || 8) + COLLIDE_PAD, 2 * (d.r || 8)))
        )
        // d3 starts its own timer on construction; every tick here is driven
        // by `loop` instead, so that one is turned off immediately.
        .stop();
      if (world) {
        const cx = (world.left + world.right) / 2;
        const cy = (world.top + world.bottom) / 2;
        simulation.force("x").x(cx);
        simulation.force("y").y(cy);
      }
      applyGrouping(message.params);
      simulation.alpha(message.alpha == null ? 1 : message.alpha);
      // New notes: a playback, glide or settle of the old ones is dropped, not restored.
      intro.frames = [];
      intro.alphas = [];
      intro.shown = null;
      settleGlide.left = 0;
      pending.on = false;
      untangle.holding = false;
      if (message.warm) pendingStart(true, message.intro === true, message.bloom === true);
      run();
      break;
    }
    case "params":
      untangle.done = false;
      untangle.passes = 0;
      untangle.cleaned = false;
      untangle.holding = false;
      applyForces(message.params);
      if (simulation) simulation.alpha(Math.max(simulation.alpha(), 0.3));
      run();
      break;
    case "drag": {
      if (!simulation) break;
      const index = indexById.get(message.id);
      if (index === undefined) break;
      const node = nodes[index];
      if (message.phase === "start") {
        dragging = true;
        // A note the reader moves is not followed by a reshuffle of others.
        untangle.done = true;
        untangle.passes = UNTANGLE_PASSES;
        untangle.cleaned = true;
        untangle.holding = false;
        dragOrigin = { x: node.x, y: node.y };
        markFollowers(node, true);
        if (ring.params) applyGrouping(ring.params);
        const heat = dragHeat(message.x, message.y);
        simulation.alphaTarget(heat).alpha(Math.max(simulation.alpha(), heat));
        node.fx = message.x;
        node.fy = message.y;
      } else if (message.phase === "move") {
        node.fx = message.x;
        node.fy = message.y;
        const heat = dragHeat(message.x, message.y);
        simulation.alphaTarget(heat).alpha(Math.max(simulation.alpha(), heat));
      } else {
        dragging = false;
        dragOrigin = null;
        markFollowers(node, false);
        if (message.keep && ring.params) applyGrouping(ring.params);
        // alphaTarget(0) rather than a stop: the release is meant to *decay*,
        // which is what makes the neighbourhood settle after you let go
        // instead of freezing mid-rearrangement.
        simulation.alphaTarget(0);
        //: **Moved is not pinned** (the owner, 2026-10-11: "moving nodes
        //: keeps them stuck there, they should only be stuck in place if I
        //: double click on them ... if the user moves them, they should
        //: settle into place in that general position"; GRAPH_PLAN decision
        //: 2026-10-11). Held at the drop until the map rested, it was
        //: let go into a layout with no heat left and never moved again.
        //: Now it is let go on release into a layout cooled to a low heat
        //: (`RELEASE_ALPHA`): its links settle it near the drop, not back
        //: where it came from (graphdragsettle.js: under 60px from the drop).
        if (!message.keep) {
          node.fx = null;
          node.fy = null;
          simulation.alpha(Math.min(Math.max(simulation.alpha(), RELEASE_ALPHA_MIN), RELEASE_ALPHA));
          //: A note the reader put somewhere is on its leash no longer: the
          //: tether is a rule for where the layout leaves a note, and it
          //: pulled a dropped one 296px back toward its category.
          node.placed = true;
          if (ring.params) applyGrouping(ring.params);
        }
      }
      run();
      break;
    }
    case "freeze":
      for (const id of message.ids || []) {
        const index = indexById.get(id);
        if (index === undefined) continue;
        const node = nodes[index];
        if (node.fx != null) continue; // already held by the user
        node.fx = node.x;
        node.fy = node.y;
        node.frozenByDrag = true;
      }
      run();
      break;
    case "thaw":
      for (const node of nodes) {
        if (!node.frozenByDrag) continue;
        node.fx = null;
        node.fy = null;
        node.frozenByDrag = false;
      }
      run();
      break;
    case "pin": {
      const index = indexById.get(message.id);
      if (index === undefined) break;
      nodes[index].fx = message.x;
      nodes[index].fy = message.y;
      run();
      break;
    }
    case "unpin": {
      const index = indexById.get(message.id);
      if (index === undefined) break;
      nodes[index].fx = null;
      nodes[index].fy = null;
      if (simulation) simulation.alpha(Math.max(simulation.alpha(), 0.2));
      run();
      break;
    }
    case "reheat":
      if (!simulation) break;
      simulation.alpha(Math.max(simulation.alpha(), message.alpha || 0.3));
      run();
      break;
    case "reshuffle":
      if (!simulation) break;
      untangle.done = false;
      untangle.passes = 0;
      untangle.cleaned = false;
      untangle.holding = false;
      reshuffle(message.seed, message.animate !== false);
      run();
      break;
    case "stop":
      stopLoop();
      dragging = false;
      carry.node = null;
      carry.followers = [];
      break;
    case "recycle":
      inFlight = Math.max(0, inFlight - 1);
      if (message.buffer && pool.length < 3) pool.push(new Float32Array(message.buffer));
      break;
    default:
      break;
  }
};
