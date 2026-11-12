# Companion rows Cp1 and Cp2 (1112)

Done (one commit per row, tests first with a fixed clock): P7 and P6 (26092ac88), X8 (42e037951), I17 and X18 desk milestone (a7e56bda1), I21 catch mid-air (05b51746d). P36 was driven in a browser and needed no change.

Remaining:
- I17 media playing: bobbing to music needs the Windows audio session (blocked-hardware). The catalogue refuses an in-app-only entry, so `react.media_playing` stays missing on both sides.
- I21 hold still, carry over, tail pull, drag skid, toss up, pointer chase: each needs desk frames that do not exist and a human rater; the catalogue refuses one-sided acts, and `engine.py` and `engine_input.py` sit at their line caps, so a desk hook has to live in `extras.py`.
- I12 and O16 travel art (B65 L9): a redraw judged by eye on real Windows (owner and rater).
- O37 masculine Atlas (E4): the owner's pick (OPEN.md:294).

Not verified: real Windows (the desk `caught` and `note_milestone` rows are tests on a fake transport), the throw-landing path for `caught` in the app (driven with a synthetic press on a real throw flight, 1.9 s to the reaction; a real mouse press raced the flight end), touch.
Found, not fixed: `ReferenceError: renderWebSearchToggle is not defined` at `status.js:2873` (called before `wiring.js` defines it); a guard there adds to the global_scope ratchet, so it needs the call moved, not a `typeof`.
