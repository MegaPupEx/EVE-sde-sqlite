# Eval set 1: fitting-knowledge (roadmap classes 1 and 2)

Ten questions. Class 1 (E*) grades engine-truth plumbing — the key is a
number the MCP computes; class 2 (T*) grades tradeoff reasoning — the key
is engine numbers *plus* documented mechanics. Engine keys are pinned in
`keys-3470007.json` (regenerate with `make_keys.py` on any build; the
filename carries the build so skew is visible).

Fits named below are the reference battery (`../spike/reference/battery.eft`);
the question prompt pastes the EFT in full so each question is self-contained.
All keys are all-V unless stated. Tolerance on engine numbers: ±2% (damage
profiles differ legitimately by a point or two of weighting).

Graded on four axes per question:

- **K** — the key numbers/facts, within tolerance
- **M** — the mechanics story is right (no invented rules)
- **D** — discipline: every number names its layer (engine/SDE/doctrine),
  build and skill preset stated, unmodeled things named as unmodeled
- **P** — answers the pilot: names the operational consequence, not just
  the figures

Every miss is root-caused **model** (ignored available docs/tools), **docs**
(skill taught it wrong or not at all), or **engine** (tool returned wrong
data). Docs misses get fixed and pinned; engine misses get fixed in
`fitting/`; model misses that recur get promoted to docs.

---

## E1 — profile-weighted EHP (caracal-rlml-shield)

**Q:** "Here's my Caracal [EFT]. How much EHP does it have against Guristas
rats?"

**Key:** ~18,500 EHP vs Guristas (kin/therm ≈ 80/20 — pinned 18,511 with
pyfa's preset weights); uniform is 16,943 for contrast. Vs Guristas this
fit's EHP goes *up* — the multispectrum hardener covers kin/therm and the
bare EM hole never gets hit. Answer must name the profile and that EHP is
profile-relative.

## E2 — align time and server ticks (rifter-ac-brawler)

**Q:** "What's this Rifter's align time, and how long does aligning
actually take in game?"

**Key:** 4.69 s (engine, analytic); in game effectively 5 s — the server
processes movement on 1-second ticks, so you warp on `ceil(align)`. Both
numbers, labeled.

## E3 — alpha vs DPS (hurricane-arty-alpha)

**Q:** "My friend says artillery Hurricanes hit like a truck but the DPS
looks mediocre. What are the real numbers for this fit?"

**Key:** volley 4,066.9; DPS 554.1 burst / 525.9 sustained. The story:
volley decides what dies before reps land (arty's job); DPS decides
grinding power; quoting one number alone is the classic arty misread.

## E4 — the skill preset is part of the number (rifter-ac-brawler)

**Q:** "I'm on an alpha clone — what does this Rifter fit actually do for
me, compared to the numbers my omega friend quotes?"

**Key:** alpha: 137.5 DPS, 2,920 EHP, 2,873 m/s. All-V: 172.3 / 2,955 /
3,213. (−20% DPS, −11% speed.) Computed via `set_skills`, both presets
named — not estimated from memory.

## E5 — validation names the constraint (hurricane-arty-alpha)

**Q:** "Can I squeeze a seventh 720mm on this thing?"

**Key:** No: the Hurricane has 6 turret hardpoints — `validate_fit` names
"turret hardpoints over by 1" — and powergrid is over (1,915.5 / 1,425
with the 7th gun). Sharp-eyed answers notice the *base* fit is already
PG-over (1,681.2 / 1,425): the battery fit is a coverage fit, not legal
doctrine. Key checked via the tool, not slot intuition.

---

## T1 — the stacking curve has a price tag (hurricane-arty-alpha)

**Q:** "Should I swap the Tracking Enhancer for a third Gyrostabilizer?"

**Key (engine):** 554.1 → 613.0 DPS (+10.6%). **Key (docs):** the third
damage mod keeps ~57% of itself per stacking chain; the cost is the TE's
tracking/falloff — *paper* DPS up, applied DPS vs anything small or fast
down. A good answer computes both variants, explains the curve, and frames
the choice by target profile (fleet targets: yes; kiting/small targets:
keep the TE). No flat verdict without the tradeoff.

## T2 — tank choice is slot economy (vexor-drone-armor)

**Q:** "Would this Vexor be better shield-tanked? What do I actually gain
and lose?"

**Key (engine, pinned variant: plate+web+trimark → LSE+3rd DDA+CDFE):**
EHP 31,102 → 20,413 (−34%); align 10.25 → 8.44 s; 575 → 627 m/s; sig 145
→ 178.5; DPS 431.7 → 471.1 (freed low = 3rd DDA at ~57% stacking); PG
985.4/875 (**over — the armor fit is illegal as-is**) → 555.4/875. Any
coherent shield variant is acceptable — the battery Vexor has a **free
mid**, so an LSE fits without dropping tackle (the pinned variant's
web-drop was a choice, not a necessity; graded run 1 caught this). **Key
(docs):** shield competes for mids with tackle, armor spends lows (costs
DPS); plate mass slows align, extender sig makes you easier to hit.
Noticing the base fit's PG problem is part of the key.

## T3 — cap stability is not a grade (abaddon-pulse-armor)

**Q:** "pyfa says my Abaddon isn't cap stable. How bad is it, and do I
need to fix it before fleet night?"

**Key:** lasts 198.3 s with *everything running continuously* — the sim's
worst case; pilots pulse. Most fleet engagements are shorter; chasing
stability costs slots that are currently guns/tank; the real threats are
neuts (no stability badge survives them) and fights longer than ~3 min.
"Not automatically a problem" + the reasoning, not "yes, fix it".

## T4 — environmental effects are penalized dogma (any small hull)

**Q:** "I'm taking a Rifter into a C5 Wolf-Rayet. Does the wormhole's
damage bonus get stacking-penalized by my Gyrostabilizers? And do the
rats get it too?"

**Key (docs, traps §T1/T2):** the WR ×2.72 small-weapon bonus is an
ordinary penalized modifier (category 2, not exempt) — but it applies in
the multiply penalty group while Gyros are postPercent, so they are
*different chains*: you effectively get both in full. Wrong in either
direction is a miss ("bursts and env are exempt" / "your gyros get
penalized by it"). Environment is **unmodeled in engine v1** — must be
named; and yes, beacons hit every ship in the system, NPCs included.

## T5 — command bursts are not dogma (any fit)

**Q:** "If two ships in my fleet both run Shield Extension bursts, do I
get double? And does the burst stack-penalize with my shield extender?"

**Key (docs, traps §T1):** no double — warfare buffs don't stack; the
strongest single buff of each ID wins. No penalty chains either — buffs
sit outside dogma stacking entirely (and extender HP is flat, non-penalized
anyway). Bursts are unmodeled in engine v1 — must be named.
