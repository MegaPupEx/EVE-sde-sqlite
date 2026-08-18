# Eval generation 8 — held-out folklore round 2 (2026-08-18)

Second fresh held-out set: measures whether the zero-call audit rule
added after gen 7 moves the folklore miss rate. Ten new classes — none in
any doc, none in gens 1–7 (gen-7's ten are burned). Keys derived live
against engine build 3470007 (post-restart server, `fhq` ids) + layer-1
SDE; derivation paths noted. Protocol: 10 single-turn subjects, full
stack, sonnet @ medium via workflow.

### Q1 — "I got scrammed in my Rifter — is my MWD dead, or can I still burn out? Would a plain warp disruptor be different?"
KEY: A scram **shuts your MWD off** (and blocks MJD): Warp Scrambler II
carries `activationBlockedStrenght 1` (SDE); a Warp Disruptor has no such
attribute — point = 1 warp-strength only, MWD keeps running. HONESTY
PROBE: the engine does NOT model the shutoff — a projected scram leaves
the panel at full MWD speed (3,213 m/s measured) — so the panel is a
fiction here and the SDE attr is the truth. Full credit: scram-off /
point-no + the engine-fiction flag (or at least no quoting of MWD speed
under scram as real).

### Q2 — "A Griffin is remote sensor boosting me and I run my own Sensor Booster II, both scan-res scripted — penalized or not?"
KEY: **Penalized — remote modifiers join the same stacking chain as your
own.** Rifter scan res: base 825 → local SeBo 1,320 (×1.60) → remote
alone 1,370 (×1.66, projector skills) → both **2,084** = stronger bonus
full, weaker at the 86.9% step (unpenalized product would be 2,192).
Mirror of remote reps (amounts, additive): modifiers penalize, amounts
add. (fhq14/fhq21 projections.)

### Q3 — "Are Reinforced Bulkheads basically a free hull buffer?"
KEY: **+25% hull HP (1,875 → 2,344 on a Rupture), −11% cargo (SDE
`cargoCapacityMultiplier 0.89`), align +5% via mass — and NO speed
penalty** (max velocity unchanged; contrast cargo expanders, which cut
base speed). "Free" fails on the cargo cut — ironic on a hauler.
(fhq19/fhq22 compare + SDE.)

### Q4 — "Does an Ancillary Shield Booster use capacitor?"
KEY: **Not while it has charges — then yes.** Cyclone + Medium ASB
loaded with Navy Cap Booster 150: cap stable 100% (zero draw); same fit
with no charges: cap lasts **75 s** (it runs on cap between reloads at
`capacitorNeed 198`/cycle). Reload is 60 s of no-cap-no-charges. The
folklore "ASBs never use cap" is half true and the wrong half gets you
killed during reload. (fhq16 vs fhq17 compare + SDE.)

### Q5 — "Can I stick a cloak on my Vexor? What does it cost me?"
KEY: Yes — Prototype Cloaking Device I fits any ship with a free high.
Cost while cloaked: **speed −90%** (Vexor 244 → 24.4 m/s) and **scan res
−50%** (350 → 175 mm), both engine-measured; plus a **30 s targeting
delay after decloak** (SDE `cloakingTargetingDelay 30000`; the delay
itself is a game rule the panel can't show). Covert Ops cloaks (no speed
penalty, warp while cloaked) are hull-restricted — this one isn't.

### Q6 — "If I fit both a shield booster and an armor repairer on my Cyclone, do they interfere?"
KEY: **No interference of any kind** — both rep at full value together
(shield 65.7 + armor 60.6 hps, identical to solo-fitted values). The
real dual-tank costs are structural: two slot systems for one ship's
worth of tank, and capacitor — this Cyclone goes from 993 s to **150 s**
cap with both running. (fhq15 with/without.)

### Q7 — "Is there a skill that boosts hull HP the way Hull Upgrades does armor?"
KEY: **Mechanics — +5% hull HP per level.** Rifter: SDE base hull 350 →
438 at all-V (×1.25, engine-visible). Same shape as Hull Upgrades
(armor) and Shield Management (shield). (SDE base vs panel.)

### Q8 — "If I put a range-scripted damp on a sniper, what actually happens on his end?"
KEY: His **max lock range collapses** — scripted Remote Sensor Dampener
II on a test Rupture: 62.5 → **29.6 km** (−53%). Anything he had locked
beyond the new ceiling **breaks lock** (game rule; the engine shows the
new ceiling, not the break). Range script pushes all the ewar into range
suppression; unscripted splits range/scan-res. (fhq3 → fhq22.)

### Q9 — "Do warp speed rigs and low-slot hyperspatial accelerators work together, or penalize each other?"
KEY: **They combine cleanly, because they're different math**: the
accelerator is a FLAT add (`warpSpeedAdd +0.3 AU/s`), the rig a
multiplier (`WarpSBonus +20%`). Rupture: (4.0 + 0.3) × 1.20 = **5.16
AU/s**, engine-exact — no stacking penalty between them. The rig's
drawback is +5% sig at all-V (10% base, halved by rigging skill).
(fhq20 + SDE.)

### Q10 — "Can my Rupture fit a Micro Jump Drive?"
KEY: **No** — the engine's validator rejects it by name ("Medium Micro
Jump Drive cannot be fitted to Rupture"); Medium MJDs are restricted to
battlecruiser-class hulls, Large to battleships. Cruisers have no MJD
option. Full credit is tool-sourced (import + validate), not asserted.
(fhq23.)

Grading note: Q1 and Q8 carry engine-fiction/game-rule boundaries — the
honesty axis. Q2/Q6/Q9 form the modifiers-vs-amounts-vs-flat-adds
triangle: three "do X and Y stack" questions with three different
correct answers, unguessable from one memorized rule.
