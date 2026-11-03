// The arrows of a `.scroll-row` (INBOX 1578, DESIGN.md's recipe index), lazy: only a
// chip row that overflows needs them, and `syncEdgeFade` (shell-reminders.js)
// fetches this file for the first one (`ensureModule("scrollRow")`) and calls
// `scrollRowArrows` from then on.

//: The arrows of a `.scroll-row` (INBOX 1578): one at each end with more behind
//: it, siblings of the row placed over its faded ends, out of the tab order.
function scrollRowArrows(bar, overflows) {
  let start = bar.nextElementSibling;
  if (!start?.classList.contains("scroll-row-arrow")) {
    if (!overflows) return;
    const host = bar.parentElement;
    if (getComputedStyle(host).position === "static") host.classList.add("scroll-row-host");
    const arrow = (side) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "scroll-row-arrow icon-only ghost small";
      button.dataset.side = side === 1 ? "end" : "start";
      button.tabIndex = -1;
      button.setAttribute("aria-hidden", "true");
      button.append(Object.assign(document.createElement("i"), { className: `ph ph-caret-${side === 1 ? "right" : "left"}` }));
      button.addEventListener("click", () => {
        const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
        bar.scrollBy({ left: side * bar.clientWidth * 0.8, behavior: calm ? "auto" : "smooth" });
      });
      return button;
    };
    start = arrow(-1);
    bar.after(start, arrow(1));
  }
  const end = start.nextElementSibling;
  start.hidden = !bar.classList.contains("fade-start");
  end.hidden = !bar.classList.contains("fade-end");
  start.style.top = end.style.top = `${bar.offsetTop + bar.clientHeight / 2}px`;
  start.style.left = `${bar.offsetLeft}px`;
  end.style.left = `${bar.offsetLeft + bar.offsetWidth}px`;
}
