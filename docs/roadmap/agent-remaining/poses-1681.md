# INBOX 1681 audit: poses and resting acts against the owner's list

Counts are drawn variants a viewer can see (an act's `NMB_VARIANTS` row, or Atlas's `ATLAS_LOWER_STATES` rows). "Chosen" is where the pick happens. Before = the head of `claude/next-queue-1102`; after = this branch.

| Owner's word | Plain companions before | Atlas before (both looks) | Chosen by | After (all companions) |
| --- | --- | --- | --- | --- |
| sit | `data-pose=sit` (one picture); `dangle`, `kick` over an edge (1 each) | lower `sit` 3, arms `atlasVariant` 3 | placement (`spot.pose`), `nameMarkBuddyDecide` | `rest` 3, `lounge` 3 added |
| crouch | none | none | none | `crouch` 3 (stand), lower `crouch` 3 |
| lie | `lie` act, `NMB_VARIANTS` 2 but no CSS told them apart | frames lie-1, lie-2, lie; lower `lie` 3 | decide (`lie`, `nap`), `nameMarkBuddyLieDown` | `lie` 3 drawn (other leg bent, a knee up, an arm behind the head) |
| curl (asleep) | pillow lie | lower `curl` 3 | `nameMarkBuddyCurlUp` | unchanged, sway now two periods |
| float | `data-pose=float` loop only | lower `idle` 4 | placement | `drift` 3 (legs crossed, knees tucked, on its back), lower `drift` 3 |
| walk | `nmb-walking` loop (1) | lower `walk` 3 | `nameMarkBuddyGo` | unchanged |
| glide | none | none | none | `glide` 3 (streamlined, arms out, banking), lower `glide` 3 trailing |
| lounge | none | none | none | `lounge` 3 (propped on a hand, a knee up, chin on a hand), lower `lounge` 3 |
| climb | `data-travel=climb` (1, travel only) | lower `walk` | `nameMarkBuddyGo` | `climb` 3 while hanging (left reach, right reach, pull-up), lower `hang` 3 |
| hang | `swing`, `sloth`, `onehand`, `feet`, `peekdown` (1 each) | lower `idle` | decide (pose hang) | plus `climb` 3; lower `hang` 3 |
| rest | stances (Atlas only, 2 per look), `shift`, `tilt` | lower `idle` 4, `think` 3, `sad` 3 | decide | `rest` 3 (weight shifted, arms behind the head, hands behind the back) |

Totals: acts in `NAME_MARK_BUDDY_ACTS` 49 to 55; acts with three or more drawn variants 3 to 10 (`wave`, `hop`, `nap` before); Atlas lower body states 10 to 15, every one with three or more rows and a turn within 4 degrees of the torso.

E6 (2026-11-11) added lower states `lean`, `dangle`, `kick`, `swing` and `sloth` (each with three rows, six or more blended, a turn within 4 degrees) and desk pose rows for the `dangle`, `kick` and `meditate` frames; tests/test_lower_pose_1111.py.

Mechanism: new rows in the existing table, the existing variant pick (`nameMarkBuddyPickVariant`, never the last), the existing 8 to 14 s lower-body re-roll for `hang`. No new timer or frame loop.

Left for 1678 (the deeper mind): choosing among them by mood and context beyond the weights here.
