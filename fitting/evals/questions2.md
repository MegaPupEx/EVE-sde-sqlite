# Eval set 2: the v1.5 surface (env, graphs, projection, bursts, presets, fighters)

Eight questions over the phase-4/v1.5 tools. Engine keys pinned in
`keys2-3424810.json` (regenerate: `make_keys2.py`). Same grading axes as
set 1 (K numbers ±2%, M mechanics, D discipline, P pilot-answer).

**Arms, per the product target:** this generation compares the **layered
stack** (eve-fitting skill + engine) against **bare fit-sim** (engine
access only, no docs) — measuring what the interpretation layer adds on
top of a tool surface that already carries some discipline. Consumer
model: Sonnet; the harness cannot set reasoning effort per-run (noted in
results).

---

## G1 — environment changes the answer (drake-ham-passive)

**Q:** "I rat in my Drake. Just rolled into a C3 with a Wolf-Rayet effect
— what does that do to my tank?"

**Key (engine):** uniform EHP 47,178 → **42,989** (−8.9%); every shield
resist ~5 points worse (em .353→.303, kin .632→.582 …) — Wolf-Rayet's
shield-resist malus, a penalized dogma chain. The armor HP bonus is
irrelevant to a shield Drake. **Key (docs):** the rats get the same
effect (traps §T2); `set_env` touches only the fit it is set on; effective
regen re-quoted vs the new resists.

## G2 — range projection (hurricane-arty-alpha)

**Q:** "How far can my arty Hurricane actually project damage before it
falls off?"

**Key (engine graph):** peak ~562 DPS (ideal target), **half-DPS at
~57 km**; assumptions named (ideal sig, stationary — the summary is a
best case). Good answers quote the summary, not 30 points, and name the
graph-vs-panel wrecking-shot offset if they compare to 554.

## G3 — tracking collapse (hurricane-arty-alpha)

**Q:** "Will my arty Hurricane track a frigate orbiting me at 2 km?"

**Key (engine graph, sig 40 @ 2 km):** no — DPS collapses 562 → **~82 by
150 m/s** of target speed; the 82 plateau is the Warrior IIs keeping up,
not the guns. The answer is drones/web, not artillery.

## G4 — the neut reality check (punisher-pulse-armor)

**Q:** "My Punisher is cap stable at 88%. A Curse lands one Medium Energy
Neutralizer II on me — am I still fine?"

**Key (engine):** stable 87.7% → **dead in 12 s**. Projection is
zero-range/full-strength — say so — but the teaching stands: a stability
badge says nothing about energy warfare (traps §T5). When cap dies this
fit loses guns and prop; its *buffer* armor tank survives — noticing that
this Punisher has no active rep to lose is part of the key (run 2's
sim-only subject spotted it; the original key text had it wrong).

## G5 — burst source and stacking (any shield subject)

**Q:** "Fleet has a Drake and a Vulture that can both run Shield
Extension bursts. Do I want both running it? Which matters?"

**Key (engine):** LSE Caracal shield HP 5,375 base → 6,181 under the
Drake (+15.0%) → **6,302 under the Vulture (+17.25%)**; both at once =
6,302 — strongest wins, bursts never stack (traps §T1). So: the Vulture
runs Shield Extension; the Drake runs a *different* burst.

## G6 — the unknown pilot (rifter-ac-brawler)

**Q:** "I literally just made my character. What will this Rifter
actually do for me?"

**Key (engine + discipline):** lead with the **all-0 floor: 49 DPS,
2,364 EHP, 2,129 m/s** against the all-V ceiling (172.3 / 2,955 /
3,213). A new character also cannot *use* the T2 modules at all
(prerequisites are game knowledge, not engine output — name the layer).
Quoting only all-V numbers is the graded failure.

## G7 — fighters, with the catch named (Thanatos)

**Q:** "How much DPS does one Firbolg squadron add to my Thanatos, and
what's the catch in the number?"

**Key (engine):** **524.3 DPS** (all-V, squadron of 6). Catches, all
named: standard attack only — ability toggles are unmodeled
(`engine_info`); fighters are the first DPS lost (shot down, recalled);
tube/bay limits validated by the engine.

## G8 — the ill-posed single number (any Triglavian hull)

**Q:** "What's the DPS of a Vedmak with three Heavy Entropic
Disintegrators?"

**Key (discipline):** there is no single number — spool-up is
**unmodeled** and Triglavian DPS is a function of ramp time (traps §T11).
A passing answer names the ramp and the unmodeled gap, gives labeled
bounds or declines the flat figure; a failing answer quotes one engine or
memory number as "the DPS".
