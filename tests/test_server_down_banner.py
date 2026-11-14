"""The server-down banner (WORLD_CLASS_PLAN 22.1 item 6, status.js/app.js).

"The server can go away. Only the log view says 'reconnecting'... everywhere
else a stopped backend shows as buttons that do nothing." `api()`'s own
`fetch()` catch block already told a real network failure apart from a
timeout or an intentional abort; this gives that one case a banner (the
existing toast recipe, `.toast`/`.toast-action`, held open rather than timed
out) with a Retry action, backed by a backoff poll against `/health`, and
clears on the next successful request or a successful poll.
"""

from __future__ import annotations

from tests._app_js import app_js_text


def _function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\n}\n", start)]


def test_a_real_network_failure_raises_the_banner_not_a_timeout() -> None:
    """`api()`'s catch block distinguishes an intentional abort, a slow
    answer (TimeoutError) and an actual dropped connection; only the last
    one means the server is not there, so only it calls `noteServerDown`."""
    app = app_js_text()
    api_fn = _function(app, "api")
    call_site = api_fn[api_fn.index("catch (networkErr)") :]
    assert 'networkErr?.name !== "AbortError" && networkErr?.name !== "TimeoutError"' in call_site
    assert "noteServerDown();" in call_site
    assert "throw networkErr;" in call_site


def test_every_successful_response_clears_it() -> None:
    """`fetch()` returning at all, whatever HTTP status, means the server
    answered; `noteServerUp` is called before the 401/error branches so a
    401 (an expired session, not a dead server) still clears the banner."""
    app = app_js_text()
    api_fn = _function(app, "api")
    up_index = api_fn.index("noteServerUp();")
    status_index = api_fn.index('response.status === 401')
    assert up_index < status_index


def test_the_banner_reuses_the_toast_recipe_with_no_new_css() -> None:
    """DESIGN.md's recipe for a notification with an action button is
    `toastAction`/`toast`; the server-down banner is built from the same
    `.toast`/`.toast-action`/`toastCloseButton` pieces rather than a
    bespoke element, so no new banner CSS is needed."""
    app = app_js_text()
    banner = _function(app, "showServerDownBanner")
    assert 'note.className = "toast error server-down-toast"' in banner
    assert 'button.className = "small toast-action"' in banner
    assert "toastCloseButton(note" in banner


def test_no_duplicate_banners_and_no_duplicate_retry_loops() -> None:
    """A dozen in-flight requests failing at once must raise one banner and
    start one retry loop, not one each."""
    app = app_js_text()
    banner = _function(app, "showServerDownBanner")
    assert "if (serverDownNote && serverDownNote.isConnected) return message;" in banner
    schedule = _function(app, "scheduleServerDownRetry")
    assert "if (serverDownRetryTimer) return;" in schedule


def test_retry_backs_off_and_is_capped() -> None:
    app = app_js_text()
    schedule = _function(app, "scheduleServerDownRetry")
    assert "serverDownRetryDelay = Math.min(serverDownRetryDelay * 2, SERVER_DOWN_RETRY_MAX_MS);" in schedule
    assert "const SERVER_DOWN_RETRY_MIN_MS = 3000;" in app
    assert "const SERVER_DOWN_RETRY_MAX_MS = 30000;" in app


def test_recovery_resets_the_backoff_and_cancels_the_pending_retry() -> None:
    app = app_js_text()
    up = _function(app, "noteServerUp")
    assert "serverDownRetryDelay = SERVER_DOWN_RETRY_MIN_MS;" in up
    assert "clearTimeout(serverDownRetryTimer);" in up
    assert "dismissToast(serverDownNote);" in up


def test_manual_retry_button_polls_health_immediately() -> None:
    app = app_js_text()
    banner = _function(app, "showServerDownBanner")
    assert "retryServerNow()" in banner
    retry = _function(app, "retryServerNow")
    assert "pollServerHealth();" in retry


def test_poll_health_hits_the_open_health_route_with_a_timeout() -> None:
    """`/health` is open (no auth token needed) and answers before the lock
    screen, the same route the startup probe already uses."""
    app = app_js_text()
    poll = _function(app, "pollServerHealth")
    assert 'fetch("/health"' in poll
    assert "AbortSignal.timeout(4000)" in poll


def test_a_write_while_the_server_is_down_is_refused_with_the_banners_message() -> None:
    """LEDGER L-world-class-99 (22.1.6): a write is not sent into a dead
    server, it is refused at once with the banner's own words, as the
    TypeError the held-note paths already treat as "the server is gone"
    (`noteServerGone`); the refusal also asks the health poll to look now,
    so a server that came back clears the banner without the 30 s backoff."""
    app = app_js_text()
    api_fn = _function(app, "api")
    before_fetch = api_fn[: api_fn.index("response = await fetch(")]
    assert "serverUnreachable" in before_fetch and "retryServerNow();" in before_fetch
    assert "throw new TypeError(showServerDownBanner());" in before_fetch
    assert "readOnly" in before_fetch
    banner = _function(app, "showServerDownBanner")
    assert "return message;" in banner and "text.textContent = message;" in banner
    assert "networkErr.message = showServerDownBanner();" in api_fn


def test_sign_in_and_health_are_never_refused_by_the_banner() -> None:
    """They are how the app finds out the server is back."""
    api_fn = _function(app_js_text(), "api")
    before_fetch = api_fn[: api_fn.index("response = await fetch(")]
    assert "/auth/" in before_fetch and "/health" in before_fetch
