// timeline-ticks.js: year and month labels beside the Timeline's density strip
// (TIMELINE_PLAN 10 row 6, VC2). Lazy: `drawTimelineScrubber` (timeline.js)
// asks for it once the strip shows, and it fetches d3 itself, so the boot
// carries no d3 and no label code. The strip is linear in time (newest at the
// top), which is what a time scale is: d3's `scaleTime` puts the ticks, its
// intervals choose how coarse they are, `timeFormat` writes them.
//
// A label is drawn only when there is room for it. The step (day, week,
// month, year) is the finest whose ticks sit at least `TIMELINE_TICK_GAP`
// pixels apart on a strip of this height, so two labels never share a line
// whatever the span: a week of notes reads in days, fourteen months in months,
// a decade in years. Without d3 (the file blocked or offline), the strip is
// what it was: a shape with no labels.

//: A label's line (`--text-xs`, about 11 px) and some air; the months of a
//: 28-day February against a 31-day July differ by 10%, so the gap is chosen
//: with that already taken off: the closest two ticks still clear 12 px.
const TIMELINE_TICK_GAP = 28;
//: Hold the first and last label off the strip's ends, where half of it would
//: be cut by the rounded corner.
const TIMELINE_TICK_EDGE = 7;
//: The d3 formats (built once, d3 loads lazily) and the plan last drawn.
const timelineTickCache = { formats: null, key: "" };

//: The steps, finest first, each with the days one tick stands for (the
//: nominal length, to choose by) and d3's interval (to place by).
function timelineTickSteps() {
  return [
    { step: "day", days: 1, every: d3.timeDay.every(1) },
    { step: "week", days: 7, every: d3.timeMonday },
    { step: "month", days: 30.44, every: d3.timeMonth.every(1) },
    { step: "month", days: 91.3, every: d3.timeMonth.every(3) },
    { step: "month", days: 182.6, every: d3.timeMonth.every(6) },
    { step: "year", days: 365.25, every: d3.timeYear.every(1) },
    { step: "year", days: 730.5, every: d3.timeYear.every(2) },
    { step: "year", days: 1826, every: d3.timeYear.every(5) },
    { step: "year", days: 3652, every: d3.timeYear.every(10) },
  ];
}

//: The label of one tick, by the step it belongs to: the year on a year or a
//: January, else the month; a week by its Monday and a day by its date, both
//: with the month ("Oct 5"), since a strip of one week has no other month in
//: view to say which.
function timelineTickLabel(date, step) {
  timelineTickCache.formats ||= { y: d3.timeFormat("%Y"), m: d3.timeFormat("%b"), w: d3.timeFormat("%b %-d") };
  const f = timelineTickCache.formats;
  if (step === "year") return f.y(date);
  if (step === "month") return date.getMonth() === 0 ? f.y(date) : f.m(date);
  return f.w(date);
}

//: `span` is `timelineDensitySpan()`'s ({newest, oldest, width} in ms),
//: `height` the strip's pixel height. Returns the step chosen and the ticks,
//: top to bottom, each at its pixel `y` with its label and whether it is a
//: month or year start (drawn heavier).
function timelineTickPlan(span, height) {
  const steps = timelineTickSteps();
  const spanDays = span.width / 86400000;
  const chosen = steps.find((s) => (s.days / spanDays) * height >= TIMELINE_TICK_GAP) || steps[steps.length - 1];
  const scale = d3.scaleTime().domain([new Date(span.newest), new Date(span.oldest)]).range([0, height]);
  const ticks = scale
    .ticks(chosen.every)
    .map((date) => ({ date, y: Math.round(scale(date) * 10) / 10 }))
    .filter((t) => t.y >= TIMELINE_TICK_EDGE && t.y <= height - TIMELINE_TICK_EDGE)
    .sort((a, b) => a.y - b.y)
    .map((t) => ({
      y: t.y,
      label: timelineTickLabel(t.date, chosen.step),
      major: chosen.step === "year" || (chosen.step === "month" && t.date.getMonth() === 0) || (chosen.step === "day" && t.date.getDate() === 1),
    }));
  return { step: chosen.step, ticks };
}

//: Draws the labels for the strip as it is now, and again whenever its height
//: changes (a window resize, the dock wrapping). A plan that has not changed
//: is not redrawn: the strip repaints on every density read.
async function timelineTicks() {
  const strip = $("timeline-scrubber");
  if (!strip.dataset.ticksWatched) {
    strip.dataset.ticksWatched = "1";
    if (typeof ResizeObserver === "function") new ResizeObserver(() => timelineTicks()).observe(strip);
  }
  const [loaded] = await Promise.all([lazyScript("/vendor/d3.v7.min.js"), lazyScript("/css/timeline-ticks-lazy.css")]);
  const span = timelineDensitySpan();
  const height = strip.clientHeight;
  if (!loaded || !span || strip.classList.contains("hidden") || height < 60) return;
  const plan = timelineTickPlan(span, height);
  const key = `${plan.step}|${height}|${span.newest}|${span.width}`;
  if (key === timelineTickCache.key && strip.querySelector(".timeline-ticks")) return;
  timelineTickCache.key = key;
  let layer = strip.querySelector(".timeline-ticks");
  if (!layer) {
    layer = document.createElement("div");
    layer.className = "timeline-ticks";
    layer.setAttribute("aria-hidden", "true");
    strip.prepend(layer);
  }
  strip.classList.add("has-ticks");
  layer.replaceChildren(
    ...plan.ticks.map((tick) => {
      const el = document.createElement("span");
      el.className = tick.major ? "timeline-tick is-major" : "timeline-tick";
      el.textContent = tick.label;
      el.style.top = `${tick.y}px`;
      return el;
    }),
  );
}
