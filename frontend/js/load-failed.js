// load-failed.js: the failed-load state (navigation.js `surfaceFailed`), moved out of the
// boot scripts (2026-10-28, the gzip budget). A stand-in in lazy-entries.js
// loads it; it is also fetched a few seconds after boot, so the page that
// needs it because the server has just gone away already has it.
// `_surfaceFailedContents` and `surfaceRecovered` stay in navigation.js, which
// every successful load calls.

function surfaceFailed(el, what, retry) {
  if (!el) return;
  //: Saved once. A second failure while already failed must not capture the
  //: failure message as "the original contents", which would make the real
  //: empty state unrecoverable for the rest of the session.
  if (!_surfaceFailedContents.has(el)) {
    _surfaceFailedContents.set(el, { nodes: [...el.childNodes], display: el.style.display });
  }
  el.classList.add("is-failed");
  el.classList.remove("hidden");
  //: **And any inline `display` it is carrying.** The graph's empty state is
  //: hidden with `style.display = "none"` rather than the class, deliberately
  //: ("inline display beats every stylesheet rule", graph.js), so removing
  //: `hidden` left the failure message in the document at 0 by 0 pixels:
  //: present to every assertion and invisible to every reader. Measured, and
  //: exactly the kind of fix that reports itself as working.
  el.style.display = "";
  el.replaceChildren();
  const icon = document.createElement("i");
  icon.className = "ph ph-warning-circle empty-icon";
  icon.setAttribute("aria-hidden", "true");
  const title = document.createElement("p");
  title.className = "empty-title";
  title.textContent = `Could not load ${what}`;
  const body = document.createElement("p");
  //: Says what is and is not true, because the first thing a person fears
  //: here is that the notes are gone.
  body.textContent =
    "Nothing has been lost: the app could not read its own data just now.";
  el.append(icon, title, body);
  if (typeof retry === "function") {
    const again = document.createElement("button");
    again.type = "button";
    again.className = "ghost small";
    setLabel(again, "ph:arrow-clockwise Try again");
    again.addEventListener("click", () => {
      surfaceRecovered(el);
      retry();
    });
    el.appendChild(again);
  }
  el.setAttribute("role", "alert");
}
