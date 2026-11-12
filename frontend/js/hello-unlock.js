// hello-unlock.js: Windows Hello unlock (INBOX 1727), loaded with
// private-spaces.js (`LAZY_MODULES.privateSpaces`) and reached through it:
// `privateSpaces("hello", "lock")` from the lock screen, `("space", asked)`
// from the private-space card, `("settings", facts)` from Settings,
// Account & security. No name of its own in the shared scope.
//
// The browser half of api/routes_hello.py: a platform credential with the
// PRF extension, whose output the server uses as the key around the vault
// key (core/hellostore.py). This file only carries bytes between the
// authenticator and the server; it never sees the vault key. Shown only on
// this computer, at a localhost address, in a browser with a platform
// authenticator; the password is always beside it.
(() => {
  const enc = (buf) =>
    btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  const dec = (text) => Uint8Array.from(atob(text.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
  //: Every call here is an auth step (enrol, unlock, remove): no user data to undo.
  function helloPost(path, body) {
    return apiJson(path, { method: "POST", body: body ? JSON.stringify(body) : undefined, ownsAuthErrors: true, silent: true });
  }

  //: A platform authenticator that verifies the person, at a host name (browsers
  //: refuse an IP address as the RP id), and no "no" from the browser about PRF.
  let known = null;
  async function supported() {
    known ??= (async () => {
      if (!window.PublicKeyCredential || !navigator.credentials) return false;
      if (/^[\d.]+$|:/.test(location.hostname)) return false;
      try {
        if (!(await PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable())) return false;
        const caps = await PublicKeyCredential.getClientCapabilities?.();
        return caps?.["extension:prf"] !== false;
      } catch {
        return false;
      }
    })();
    return known;
  }

  const prfOf = (cred) => cred.getClientExtensionResults?.().prf?.results?.first;
  const NO_PRF = "This browser can't use Windows Hello to unlock. Use your password.";

  function assertionBody(ticket, cred) {
    const r = cred.response;
    return {
      ticket,
      credential_id: enc(cred.rawId),
      client_data_json: enc(r.clientDataJSON),
      authenticator_data: enc(r.authenticatorData),
      signature: enc(r.signature),
      prf: enc(prfOf(cred)),
    };
  }

  async function getAssertion(begin) {
    const cred = await navigator.credentials.get({
      publicKey: {
        challenge: dec(begin.challenge),
        rpId: begin.rp_id,
        allowCredentials: [{ type: "public-key", id: dec(begin.credential_id) }],
        userVerification: "required",
        timeout: 60e3,
        extensions: { prf: { eval: { first: dec(begin.prf_salt) } } },
      },
    });
    if (!prfOf(cred)) throw new Error(NO_PRF);
    return cred;
  }

  //: Cancelling the Windows dialog is not an error worth more than a line.
  const said = (error) =>
    error?.name === "NotAllowedError" ? new Error("Windows Hello was cancelled. Try again, or use your password.") : error;

  // --- the lock card --------------------------------------------------------------

  //: The card is one element in several modes, so CSS shows the button
  //: (01-forms-settings.css): `for-lock` on the lock screen's unlock mode,
  //: `for-space` on a prompt while the private-space card asks. Any other
  //: prompt (private notes, sign-in off) never shows it.
  function button() {
    let btn = $("lock-hello");
    if (btn) return btn;
    btn = document.createElement("button");
    btn.type = "button";
    btn.id = "lock-hello";
    btn.className = "ghost";
    const glyph = document.createElement("i");
    glyph.className = "ph ph-fingerprint ph-lead";
    glyph.setAttribute("aria-hidden", "true");
    btn.append(glyph, "Unlock with Windows Hello");
    $("lock-submit").after(btn);
    btn.addEventListener("click", press);
    return btn;
  }

  async function press() {
    const btn = $("lock-hello");
    const space = $("lock-overlay").dataset.mode === "prompt";
    $("lock-error").textContent = "";
    setBusy(btn, true, "Waiting for Windows Hello…");
    try {
      const begin = await helloPost("/auth/hello/begin");
      const body = assertionBody(begin.ticket, await getAssertion(begin));
      if (space) {
        await helloPost("/private-spaces/unlock-hello", body);
        setBusy(btn, false);
        settleLockPrompt(true);
        return;
      }
      lockOpened(await helloPost("/auth/hello/unlock", body), "unlock");
    } catch (error) {
      lockFailed(said(error));
    }
    setBusy(btn, false);
  }

  //: Each lock screen says whether this computer has it (`/auth/status`).
  async function offerLock(here) {
    const on = Boolean(here) && (await supported());
    if (on || $("lock-hello")) button().classList.toggle("for-lock", on);
  }

  //: The private-space card: the button for as long as this prompt asks.
  async function offerSpace(asked) {
    if (!(await supported())) return;
    const btn = button();
    btn.classList.add("for-space");
    asked.finally(() => btn.classList.remove("for-space"));
  }

  // --- Settings, Account & security -------------------------------------------------

  const HELP = [
    "Windows Hello (your face, fingerprint or Windows PIN) unlocks the app and your private spaces on this computer only. Your password always works too, and phones and other devices always need it.",
    "Hello's own key, kept by Windows, locks a copy of your notebook's key, so nothing in your notebook or its backups gets easier to open. Changing your password, re-encrypting private notes or restoring a backup turns it off.",
    "It needs a browser that offers Windows Hello's PRF extension, with the app opened at a localhost address. Where it is missing, this switch is hidden.",
  ];

  function mountSettings() {
    if ($("account-hello-group")) return;
    const group = document.createElement("div");
    group.className = "settings-group";
    group.id = "account-hello-group";
    const head = document.createElement("div");
    head.className = "row help-head";
    const title = document.createElement("h3");
    title.textContent = "Unlock with Windows Hello";
    const help = document.createElement("button");
    help.type = "button";
    help.className = "icon-only ghost small graph-help-toggle";
    help.setAttribute("data-help-for", "hello-help");
    help.setAttribute("aria-controls", "hello-help");
    help.setAttribute("aria-expanded", "false");
    help.title = "About Windows Hello unlock";
    help.setAttribute("aria-label", help.title);
    const mark = document.createElement("i");
    mark.className = "ph ph-question";
    mark.setAttribute("aria-hidden", "true");
    help.appendChild(mark);
    head.append(title, help);
    const line = document.createElement("p");
    line.className = "muted";
    line.id = "account-hello-state";
    const body = document.createElement("div");
    body.className = "help-body hidden";
    body.id = "hello-help";
    body.setAttribute("role", "dialog");
    body.setAttribute("aria-label", "About Windows Hello unlock");
    for (const text of HELP) {
      const p = document.createElement("p");
      p.textContent = text;
      body.appendChild(p);
    }
    const row = document.createElement("label");
    row.className = "setting-check";
    row.id = "account-hello-row";
    row.htmlFor = "account-hello-switch";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.id = "account-hello-switch";
    input.setAttribute("role", "switch");
    const words = document.createElement("span");
    words.textContent = "Unlock with Windows Hello";
    row.append(input, words);
    const status = document.createElement("span");
    status.className = "status";
    status.id = "account-hello-status";
    status.setAttribute("role", "status");
    group.append(head, line, body, row, status);
    $("account-pin-group").after(group);
    initHelpToggles(head);
    input.addEventListener("change", () => (input.checked ? enrol(input) : forget(input)));
  }

  async function renderSettings(facts) {
    if (!facts || !$("account-pin-group")) return;
    mountSettings();
    const ok = await supported();
    const usable = ok && facts.available && facts.here;
    $("account-hello-row").classList.toggle("hidden", !usable);
    $("account-hello-switch").checked = Boolean(facts.set);
    $("account-hello-state").textContent = !facts.here
      ? "Windows Hello can be turned on only on the computer this notebook runs on."
      : /^[\d.]+$|:/.test(location.hostname) && facts.available
        ? "Windows Hello needs localhost."
        : !ok
        ? "This browser can't use Windows Hello here. The ? says what it needs."
        : !facts.available
          ? "This computer has no protected store for Windows Hello, so the password is the only way in here."
          : facts.set
            ? "On: the lock screen and private spaces offer Windows Hello on this computer."
            : "Unlock on this computer with your face, fingerprint or Windows PIN.";
  }

  async function createCredential(begin) {
    const salt = dec(begin.prf_salt);
    const cred = await navigator.credentials.create({
      publicKey: {
        challenge: dec(begin.create_challenge),
        rp: { id: begin.rp_id, name: "Tessellate" },
        user: { id: dec(begin.user_id), name: begin.user_name, displayName: begin.user_name },
        pubKeyCredParams: [
          { type: "public-key", alg: -7 },
          { type: "public-key", alg: -257 },
        ],
        authenticatorSelection: { authenticatorAttachment: "platform", userVerification: "required", residentKey: "discouraged" },
        attestation: "none",
        timeout: 60e3,
        extensions: { prf: { eval: { first: salt } } },
      },
    });
    const ext = cred.getClientExtensionResults?.().prf;
    if (!ext?.enabled && !ext?.results?.first) throw new Error(NO_PRF);
    const body = {
      ticket: begin.ticket,
      credential_id: enc(cred.rawId),
      client_data_json: enc(cred.response.clientDataJSON),
      attestation_object: enc(cred.response.attestationObject),
    };
    if (ext.results?.first) return { ...body, prf: enc(ext.results.first) };
    //: Windows Hello gives the PRF output only on a get: a first unlock, here.
    const got = await getAssertion({ ...begin, challenge: begin.get_challenge, credential_id: body.credential_id });
    return { ...body, prf: enc(prfOf(got)), assertion: assertionBody(begin.get_ticket, got) };
  }

  async function enrol(input) {
    const status = $("account-hello-status");
    status.textContent = "";
    input.checked = false;
    const done = await askPasswordPrompt({
      title: "Unlock with Windows Hello",
      message: "Enter your password, then confirm with Windows Hello.",
      submitLabel: "Continue",
      submit: async (password) => {
        const begin = await helloPost("/auth/hello/enrol/begin", { current_password: password });
        try {
          await helloPost("/auth/hello/enrol/finish", await createCredential(begin));
        } catch (error) {
          throw said(error);
        }
      },
    });
    if (!done) return;
    status.textContent = "Windows Hello unlocks this computer now.";
    renderAccount().catch(() => {});
  }

  async function forget(input) {
    const status = $("account-hello-status");
    try {
      await helloPost("/auth/hello/forget");
      $("lock-hello")?.classList.remove("for-lock");
      status.textContent = "Windows Hello is off. The lock screen asks for your password or PIN.";
    } catch (error) {
      input.checked = true;
      status.textContent = error.message;
    }
    renderAccount().catch(() => {});
  }

  function hello(where, arg) {
    if (where === "lock") return offerLock(arg);
    if (where === "space") return offerSpace(arg);
    if (where === "settings") return renderSettings(arg);
  }

  Object.assign(privateSpaces.actions, { hello });
})();
