# throwsmooth-1027 (owner, 2026-10-27: "throwing the companion is now framey, not clean or smooth and glitchy")

- Plan: the flight and its landing are planned at the release (`companionThrowPlan`, frontend/js/companion-throw.js); frames draw the path (`companionThrowAtTime`); one obstacle measure per landing (`nameMarkBuddyMeasureOnce`, avatars.js); `nameMarkBuddyDodge` waits while it flies.
- Tests: tests/test_companion_throw_smooth.py; sweep: throw5.js in the agent's scratch dir (5 directions, rAF dt, jumps, LoAF).
- done: the plan, the one-measure landing, the deferred popup check, the first frame as one step (this commit).
- next (found, not fixed): the landing frame is still 27 to 81ms at 1x CPU (`nameMarkBuddyThrowLand` > `nameMarkBuddyMoveTo` > `nameMarkBuddyBlend`'s getAnimations, avatars.js ~8261, and `nameMarkBuddyAct("land")`); the release task is 17 to 62ms plus selection.js's mouseup forced layout 15 to 30ms.
