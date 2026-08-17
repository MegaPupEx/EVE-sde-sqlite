# Trap catalogue

Numbered so eval misses can pin them. Each claim names its source; formulas
live in `docs/fitting-formulas.md` (cited as F§n). Engine-verified claims
were checked against pyfa's own data/handlers at build 3424810 and held
unchanged on the refreshed build 3470007 (both 2026-08-17).

## T1 — Command bursts don't stack-penalize; environmental beacons do (mostly)

Two different systems, and the difference decides real answers:

- **Command bursts are warfare buffs** (`dbuffCollections` in the SDE), a
  system *outside* dogma modifiers. Buffs never join stacking chains with
  your modules, and two boosters running the same burst don't add — the
  strongest single buff of each ID wins. Modeled via `set_booster`: the
  booster fit's own hull/skills/mindlink scale the burst (a Vulture's
  burst beats a Drake's), and strongest-wins is computed, not assumed.
- **Wormhole/weather beacons are ordinary dogma modifiers** from category 2
  (Celestial), which is **not** on the exempt list (Ship, Charge, Skill,
  Implant, Subsystem — F§1). pyfa applies them with stacking penalties: a
  black hole's velocity multiplier (×1.86 at C5) lands in the **same
  penalty group as your prop mod's boost**; Pulsar armor-resist and
  Wolf-Rayet shield-resist maluses are penalized chains; a C5 Wolf-Rayet's
  ×2.72 small-weapon damage is penalized too (in the multiply group, so it
  chains with other multipliers, not with your postPercent damage mods).
- **Counterexample — category decides eligibility, the attribute decides.**
  A Pulsar's shield HP ×1.86 hits `shieldCapacity`, a non-penalized
  attribute, and applies in full. "Beacon ⇒ penalized" is too coarse;
  so was the old claim "env/burst effects are stacking-exempt", wrong in
  both halves. (pyfa `eos/effects.py` systemShieldHP vs systemMaxVelocity/
  systemArmorEmResistance, all engine-verified.)
- **"Penalized" does not mean "chains with your modules".** Bonuses and
  penalties are separate chains (F§1): a Wolf-Rayet's shield-resist
  *malus* does not weaken your hardener's *bonus* — each stacks within
  its own direction. Don't tell a pilot the wormhole nerfs their
  hardeners; it nerfs their resists directly.

## T2 — Environmental effects hit NPCs too — and `set_env` hits one fit

In game the beacon projects onto every ship in the system: a Pulsar buffs
the rats' shields and strips their armor resists exactly as it does
yours; factor both sides before calling a site easier or harder. The
engine's `set_env` applies the beacon **only to the fit it is set on** —
a fair A-vs-B or you-vs-them comparison sets the same environment on
every fit involved.

## T3 — Hull resists: every ship has 33%, and the `hull*` attributes lie

All published ships carry 33% structure resists (bare resonance 0.67, all
four types) with nothing fitted. The `hullEmDamageResonance` family is the
**module side** of the Damage Control effect, not the ship's stat — a DC II
multiplies the bare 0.67 by 0.6 → 59.8% hull resists. Read the panel's
`resists.hull`, never raw `hull*` attributes. (Layer-1 verified; the SDE
skill's gotchas-dogma has the full modifier table.)

## T4 — EHP without a damage profile is a number about nothing

EHP is profile-weighted per layer (F§2); the panel default is uniform
25/25/25/25, pyfa's convention. Always name the profile, and use the real
one — shield's structural hole is kinetic/thermal (Guristas), armor's is
EM (Sansha/Blood). NPC weights table: `reading-stats.md`.

## T5 — Cap stability: the cliff is at 25%, and the sim assumes worst case

Recharge peaks at 25% fill and falls on *both* sides (F§6) — a stable
point always sits above 25%, and stable-at-30% means a sliver of margin,
not "good". Below the peak, drain > recharge compounds and the cap
cascades to empty. The engine's number comes from pyfa's event simulation
with **every fitted module running continuously** — pilots who pulse prop
and reps do better than the panel; neuts do worse, and no `stable` badge
accounts for them.

## T6 — Burst vs sustained DPS: the reload is the fit

`dps` ignores reload, `dps_sustained` models clip + reload (F§3). The gap
is the weapon system's character: RLML Caracal 298 burst / 179 sustained
(~24 s of fire, 35 s reload — a burst weapon with a long unarmed window);
ancillary reps triple while paste lasts, then reload for 60 s; lasers
never reload crystals (panel omits `dps_sustained` when equal); a module
whose forced downtime ≥ its reload time reloads for free. Quote the number
matching the fight length asked about, and name the reload window for
clip weapons.

## T7 — The server runs on 1-second ticks

Engine outputs are continuous math; the server quantizes. Align: you warp
on the tick after crossing 75% velocity — `ceil(align_time_s)` in
practice, so 3.9 s vs 4.1 s is a real difference and 4.2 vs 4.9 is not
(F§7). Missile flight: a 3.4 s flight time means 60%/40% between two
discrete ranges, so missile "range" is a probability band, not an edge
(F§5). Quote the engine number *and* the tick behavior when the question
is operational ("can I align out before he locks me").

## T8 — Prop modules: mass first, then boost — and `online` gives nothing

The MWD adds its 50t-class `massAddition` *before* the boost divides by
mass (F§7): a plated ship gains less speed from the same MWD, on top of
aligning slower. MWD sig bloom (~+450%) is stack-penalized but effectively
full on its own. Module states matter: `active` is the boosted state;
`online` merely powers it (a MWD set `online` gives base speed) —
`edit_fit` state ops distinguish them, and stats move accordingly.

## T9 — Drones: three limits, and only two are in the data

Bay volume caps what you carry, bandwidth caps what launches, and the
pilot's Drones skill caps **5 active** — the skill cap is in neither ship
attribute. Drone DPS is inside panel `dps` (broken out as `dps_drones`;
fighters as `dps_fighters`, standard attack only) and is the first DPS
you lose: drones get shot, left behind, or exceed control range. Say when
a quoted DPS depends on drones or fighters staying alive.

## T10 — Fitting headroom: validate after calculation, expect 0.01 skew

CPU/PG needs and outputs are dogma-modified (weapon upgrade skills, ship
bonuses) — legality is checked on final values, which is what
`validate_fit` does. pyfa rounds cpu/pg to 2 decimals at every step
(F§1); an independent calculation can disagree with the panel by 0.01 —
that is rounding, not a data bug.

## T11 — Spool-up weapons make "DPS" a function, not a number

Triglavian damage ramps per cycle to a cap (F§3) and the v1 engine does
not model it (`unmodeled`). For those hulls, give DPS at named spool
levels or decline the single figure — pyfa's own NPC profiles ship as
"0% / 50% / 100% spool" variants for the same reason.

## T12 — Every number has a skill preset in it

Presets: `all-0` (no skills — the floor), `alpha` (the byte-exact
Alpha-clone set), `all-5` (the import default, pyfa's convention). The
all-0-to-all-5 gap is double-digit on most panels (damage, fitting and
cap skills all stack up). A number quoted without its preset is
unanchored — name it every time, and re-run `set_skills` rather than
estimating the delta. **Default assumption: an omega pilot at all-V,
labeled.** Switch to `alpha`/`all-0` when the question signals it
("alpha friendly", "brand new character") — and for alpha requests,
check `required_skills`' `alpha_blocked` before recommending modules. Note `validate_fit` checks fitting resources and slots only — it
does **not** check skill prerequisites: `required_skills(fit)` returns
the training-queue ends (implied prerequisites pruned; `full=true` for
the whole closure) and flags `alpha_blocked` — skills an alpha clone
cannot train high enough, computed from the SDE's `cloneGrades` set, not
from folklore. Alpha usability is data; quote the tool, not memory.

## T13 — Three builds can disagree: engine, SDE, CCP

The engine's data build (`engine_info().engine_build`), layer 1's
`meta.sdeBuildNumber`, and CCP's live build are three separate things;
any pair can skew after a patch (the spike caught pyfa's bundle a full
balance patch behind on day one). Check once per session; when they
differ, name the build behind every affected number. `fitting/adapter/`
rebuilds the engine's db at the current SDE build when it matters.

## T14 — Layer-1 raw-attribute traps carry into fitting

When you drop below the engine to raw SDE values: attribute 51 `speed` is
rate of fire in **milliseconds**, resonance is **inverted** (0.4 = 60%
resist), and `agility` is the inertia modifier, not agility. The panel
has already converted all of these; mixing panel values with raw SDE
values in one calculation is how sign errors are born. (Full list: eve-sde
skill, gotchas-dogma.)

## T15 — Abyssal modules: the roll is the data, and it rides in the EFT

A mutated module's stats live in the *roll*, not the type — 'Abyssal
Gyrostabilizer' names a container, and the engine rejects it bare. The
EFT dialect (pyfa's, engine-supported): the fitted line carries the
**base** item name plus an ` [N]` reference; a trailing section maps each
N to base item, mutaplasmid, and `attr value` pairs — **absolute** rolled
values, not multipliers. Three consequences: a killboard paste without
its mutation section silently reverts every abyssal to the base T2/faction
module (ask for the full export); rolls outside the mutaplasmid's band are
clamped by the engine to the band edge (a "god roll" claim that exceeds
the range is fake or mis-transcribed — say which value was used); and
unrolled attributes still carry the mutaplasmid's own baseline values, so
a mutated module is never just "base + one attribute". Export → reimport
round-trips exactly; quote stats from the built fit, never from the roll
text. Roll *feasibility* ("what could this roll to") is data-layer SQL:
layer 1 stores the bands in `dynamicItemAttributes` (JSON `attributeIDs`
of `{_key, min, max}` per mutaplasmid, applicable/resulting types in
`inputOutputMapping`); the engine's db has the same data as
`mutaplasmids`/`mutaplasmidAttributes`. Band × base attribute is the
reachable window — enumerate candidates in SQL, then build only the
winner in the engine to verify it in fit context (ship bonuses and heat
land on top of the roll).
