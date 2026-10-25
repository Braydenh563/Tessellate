# Security policy

## Tessellate's security model, in short

Tessellate is a **local-first, single-user app that runs on your own
machine.** By default it listens on `127.0.0.1` only, so nothing on your network
can reach it, and it never sends your notes to the cloud. Your data lives in a
folder on your disk (`data/` beside a source checkout, or your per-user app
folder when installed). Access to the app is gated behind a password you choose
on first run (bcrypt-hashed, stored locally). On a computer only you use, you can
turn the sign-in off; another device and your private notes still ask for the
password.

Letting another device in is a switch you turn on yourself (Settings, Account &
security). It always requires the password, and the network side is HTTPS with a
certificate generated on your computer. [`docs/PRIVACY.md`](docs/PRIVACY.md)
describes this, what can touch the network, and the browser protections in full.

Because of this design, the most important protections for your notes are the
ones your operating system already provides:

- **Encryption at rest.** The database is a plain SQLite file. If your notes are
  sensitive, enable full-disk encryption (BitLocker on Windows, FileVault on
  macOS, LUKS on Linux). SQLCipher is deliberately *not* bundled: it needs a
  native dependency on every platform for a single-user local file, and disk
  encryption covers the same threat more simply. What the app encrypts on its own
  is **private notes**: AES-GCM under a key derived from your password with
  scrypt.
- **Backups.** The app takes a daily local snapshot into your data folder, and
  Settings can write a full backup, which you can seal with a password. A
  snapshot or an unsealed backup is as sensitive as the database, so keep it
  somewhere you trust.

## Phone and other devices

Off by default. When you turn on "Allow other devices on this network"
(Settings, Account & security, with your password), this is what holds:

**Protected**

- **Encrypted on the network, always.** Other devices reach a separate HTTPS
  port (TLS 1.2 or newer). Plain http on that port only answers with a
  redirect to https; the app itself is never served unencrypted off this
  computer. The plain-http port stays on `127.0.0.1`.
- **A certificate made on this computer.** A small certificate authority in
  `lan-tls/` (folder 0700, keys 0600, re-checked at every start, never in a
  backup) signs the server certificate. It is name-constrained to private
  addresses, `.local` and this computer's own names, so even a stolen key
  cannot vouch for a bank's site on a phone that trusts it. Settings and the
  terminal show both SHA-256 fingerprints: compare them with what the phone
  shows before you trust it.
- **Only networks you allowed.** The port is open only on a network you
  allowed from this computer, only to private or link-local addresses, and
  it closes when the computer moves elsewhere or goes unused for 14 days.
- **The password, and this computer's yes.** Every device signs in with the
  password (eight characters or more before the switch turns on). A new
  device is then held until you press Allow on this computer. Wrong
  passwords earn growing waits per device (an IPv6 device by its /64, so it
  cannot dodge them by changing address) and across all devices together.
- **No browser tricks.** A page on another site cannot use your browser to
  reach the app: the Host check refuses a name that is not this computer's
  (the `TESSELLATE_LOCAL_NAME` `.localhost` name only from this computer
  itself), the Origin check refuses requests another site caused, and the
  session is a header, not a cookie. The one cookie, for pictures and files,
  is `HttpOnly`, `SameSite=Strict` and `Secure` over https.
- **The computer stays the computer's.** A device on the network reads and
  writes notes. It cannot turn the network on, allow a network or a device,
  change where files or backups land, point the app at another server,
  install, update, restore, use the PIN or reset the password.

**Not protected**

- **A lost phone that is still signed in.** Its session lasts until it is
  idle for your sign-in timeout (12 hours by default) and at most 7 days. On
  this computer, Remove the device (Other devices) or choose Lock everywhere
  now; changing the password also ends every other session.
- **Someone who knows your password** and whose device you allowed. Private
  notes open on a device that gave the password.
- **Trusting the warning without comparing fingerprints.** The first visit
  before the certificate is installed can be intercepted on a hostile
  network; the fingerprint check is what tells you it was not.
- **A typed `http://` address on a hostile network**, before the phone has
  seen the app over https once: the redirect itself can be intercepted.
  Open the `https://` address or the QR code Settings shows.
- **A device with the password can still read everything it is shown**, and
  can see that this notebook exists on the network (the version on
  `/health`).

## Supported versions

This is an actively developed `0.x` project. Security fixes land on `main` and
ship in the next release. Please run the latest release, or the latest `main`.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately using GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability):
go to the repository's **Security** tab, then **Report a vulnerability**.

When you report, please include:

- what the issue is and where in the code it lives, if you know;
- steps to reproduce; and
- the impact you think it has.

You will get an acknowledgement, and we will work with you on a fix and a
disclosure timeline. Thank you for helping keep Tessellate safe.

## Scope notes

The app is single-user and local, so multi-tenant data leaks do not apply. Web
threats still do, because a page open in another browser tab can send requests to
`localhost`. The areas most worth scrutiny are:

- the unlock and sign-in flow, sessions, and the wait after wrong passwords;
- the origin and Host checks, the Content-Security-Policy, and the cross-site
  protections that stop another tab or a DNS-rebinding page reaching the app;
- LAN mode: the switch, the self-signed certificate and what a device on the
  network can reach;
- private notes: the key handling, and anything that could leave their words
  readable in a backup, the search index or a saved answer;
- file upload handling and how attachments are served;
- the opt-in web paths (web search, the reader view, page clipping), their
  address checks, and text from outside reaching the agent;
- anything that could let the agent's tools act without the required
  confirmation;
- the installers for optional packages and the update path, which download and run
  code.
